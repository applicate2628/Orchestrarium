#!/usr/bin/env python3
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence
PIN_PATH = 'baseline/orchestrarium-v1/baseline-pin.json'
DISPOSITIONS_PATH = 'baseline/orchestrarium-v1/reviewed-dispositions.json'
OBJECT_ID = re.compile('[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?')
SHA256 = re.compile('[0-9a-f]{64}')
FOCUSED_TESTS = ('tests/test_orche_baseline_pin.py', 'tests/test_orche_pytest_baseline.py', 'tests/test_orche_baseline_inventory.py', 'tests/test_orche_target_effect_baseline.py', 'tests/test_orche_command_baseline.py', 'tests/test_orche_capability_baseline.py', 'tests/test_orche_verifier_isolation.py', 'tests/test_orche_review_regressions.py')
IGNORED_EXECUTABLE_PATHS = (':(glob)tests/**', ':(glob)**/conftest.py', ':(glob)scripts/**', ':(glob)**/*.py', ':(glob)**/*.pyc', ':(glob)**/*.pyo', ':(glob)**/__pycache__/**', ':(glob)**/*.sh', ':(glob)**/*.ps1', ':(glob)**/pyproject.toml', ':(glob)**/pytest.ini', ':(glob)**/tox.ini', ':(glob)**/setup.cfg', ':(exclude,glob).scratch/**', ':(exclude,glob)node_modules/**', ':(exclude,glob).venv/**', ':(exclude,glob)venv/**')

class VerificationError(RuntimeError):
    pass

class VerificationBlocked(RuntimeError):
    pass

@dataclass(frozen=True)
class ExternalTools:
    python: Path
    git: Path
    bash: Path

@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    log_path: Path
    timed_out: bool = False
    launch_error: str | None = None

@dataclass(frozen=True)
class ValidatorSpec:
    name: str
    kind: str
    arguments: tuple[str, ...]
    success_pattern: str
    failure_pattern: str
    volatile_patterns: tuple[str, ...] = ()
VALIDATORS = (ValidatorSpec('agents-spine', 'python', ('scripts/validate-agents-spine.py', '--spine', 'shared/AGENTS.shared.md'), '(?m)^RESULT: PASS$', '(?m)^RESULT: FAIL$'), ValidatorSpec('codex-pack', 'bash', ('src.codex/skills/lead/scripts/validate-skill-pack.sh',), '(?m)^VALIDATION PASSED(?: \\(with warnings\\))?$', '(?m)^VALIDATION FAILED(?: \\(with warnings\\))?$'), ValidatorSpec('claude-pack', 'bash', ('src.claude/agents/scripts/validate-skill-pack.sh',), '(?m)^VALIDATION PASSED(?: \\(with warnings\\))?$', '(?m)^VALIDATION FAILED$'), ValidatorSpec('gemini-pack', 'bash', ('src.gemini/scripts/validate-pack.sh',), '(?m)^PASS: Gemini .+ tree present at .+$', '(?m)^FAIL: .+$'), ValidatorSpec('qwen-pack', 'bash', ('src.qwen/scripts/validate-pack.sh',), '(?m)^PASS: Qwen .+ tree present at .+$', '(?m)^FAIL: .+$'), ValidatorSpec('agents-mode-docs', 'python', ('scripts/sync-agents-mode-docs.py', '--root', '.', '--check'), '(?m)^PASS: agents-mode docs are synced$', '(?m)^FAIL: .+ is not synced$'), ValidatorSpec('universal-hooks', 'python', ('scripts/sync-universal-hooks.py', '--check'), '(?m)^PASS: universal-hooks canon in sync with both mirrors$', '(?m)^FAIL: [0-9]+ mirrored file\\(s\\) drifted from scripts/universal-hooks/ canon\\..*$'), ValidatorSpec('agents-mode-installers', 'python', ('scripts/validate-agents-mode-installers.py', '--root', '.'), '(?m)^PASS: agents-mode installer regression validated$', '(?m)^FAIL: .+$', ('agents-mode-installer-regression[/\\\\][0-9a-f]{32}',)))

def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n'

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def exact_ref(value: str, *, label: str) -> str:
    if not OBJECT_ID.fullmatch(value):
        raise VerificationError(f'{label} must be an exact 40- or 64-character hexadecimal object ID')
    return value.lower()

def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False

def resolve_external_executable(value: Path, *, label: str, worktrees: Sequence[Path]) -> Path:
    try:
        resolved = value.expanduser().resolve(strict=True)
    except OSError as exc:
        raise VerificationError(f'cannot resolve {label} executable {value}: {exc}') from exc
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise VerificationError(f'{label} executable is not executable: {resolved}')
    for root in worktrees:
        if _inside(resolved, root):
            raise VerificationError(f'{label} executable resolves inside tested worktree: {resolved}')
    return resolved

def build_sanitized_env(*, tools: ExternalTools, lane_root: Path, extra: Mapping[str, str] | None=None) -> dict[str, str]:
    lane_root.mkdir(parents=True, exist_ok=True)
    directories = {'HOME': lane_root / 'home', 'USERPROFILE': lane_root / 'home', 'APPDATA': lane_root / 'appdata', 'LOCALAPPDATA': lane_root / 'localappdata', 'XDG_CONFIG_HOME': lane_root / 'xdg-config', 'XDG_CACHE_HOME': lane_root / 'xdg-cache', 'XDG_DATA_HOME': lane_root / 'xdg-data', 'XDG_STATE_HOME': lane_root / 'xdg-state', 'CODEX_HOME': lane_root / 'codex', 'CLAUDE_CONFIG_DIR': lane_root / 'claude', 'GEMINI_HOME': lane_root / 'gemini', 'QWEN_CODE_HOME': lane_root / 'qwen', 'KIMI_CODE_HOME': lane_root / 'kimi', 'TMPDIR': lane_root / 'tmp'}
    for directory in directories.values():
        directory.mkdir(parents=True, exist_ok=True)
    gitconfig = lane_root / 'gitconfig'
    gitconfig.write_text('', encoding='utf-8')
    path_dirs = list(dict.fromkeys([os.fspath(tools.python.parent), os.fspath(tools.git.parent), os.fspath(tools.bash.parent), '/usr/local/bin', '/usr/bin', '/bin']))
    env = {'PATH': os.pathsep.join(path_dirs), 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1', 'PYTHONNOUSERSITE': '1', 'PYTHONSAFEPATH': '1', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.fspath(gitconfig), 'CI': '1', **{key: os.fspath(path) for key, path in directories.items()}}
    if extra:
        env.update(extra)
    return env

def _run_git(tools: ExternalTools, env: Mapping[str, str], repo: Path, *arguments: str, text: bool=True, input_data: bytes | None=None) -> str | bytes:
    try:
        result = subprocess.run([os.fspath(tools.git), '-C', os.fspath(repo), *arguments], env=dict(env), input=input_data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=text, check=False)
    except OSError as exc:
        raise VerificationError(f'cannot launch selected Git executable: {exc}') from exc
    if result.returncode != 0:
        stderr = result.stderr if text else result.stderr.decode('utf-8', errors='replace')
        raise VerificationError(f"git -C {repo} {' '.join(arguments)} failed ({result.returncode}): {stderr.strip()}")
    return result.stdout

def _git_exit(tools: ExternalTools, env: Mapping[str, str], repo: Path, *arguments: str) -> int:
    try:
        return subprocess.run([os.fspath(tools.git), '-C', os.fspath(repo), *arguments], env=dict(env), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode
    except OSError as exc:
        raise VerificationError(f'cannot launch selected Git executable: {exc}') from exc

def assert_clean_worktree(repo: Path, *, expected_ref: str, tools: ExternalTools, env: Mapping[str, str], expected_tree: str | None=None) -> None:
    actual_ref = str(_run_git(tools, env, repo, 'rev-parse', 'HEAD')).strip().lower()
    if actual_ref != expected_ref:
        raise VerificationError(f'worktree HEAD mismatch for {repo}: expected={expected_ref}, actual={actual_ref}')
    if expected_tree is not None:
        actual_tree = str(_run_git(tools, env, repo, 'rev-parse', 'HEAD^{tree}')).strip().lower()
        if actual_tree != expected_tree:
            raise VerificationError(f'worktree tree mismatch for {repo}: expected={expected_tree}, actual={actual_tree}')
    status_text = str(_run_git(tools, env, repo, 'status', '--porcelain=v1', '--untracked-files=all'))
    if status_text:
        raise VerificationError(f'dirty worktree: {repo}\n{status_text.rstrip()}')
    ignored = bytes(_run_git(tools, env, repo, 'ls-files', '--others', '--ignored', '--exclude-standard', '-z', '--', *IGNORED_EXECUTABLE_PATHS, text=False))
    ignored_paths = sorted((item.decode('utf-8', errors='surrogateescape') for item in ignored.split(b'\x00') if item))
    if ignored_paths:
        raise VerificationError(f'ignored executable, test, configuration, or bytecode input in {repo}:\n' + '\n'.join(ignored_paths))
    flag_data = bytes(_run_git(tools, env, repo, 'ls-files', '-v', '-z', text=False))
    hidden_flags: list[str] = []
    for record in flag_data.split(b'\x00'):
        if not record:
            continue
        decoded = record.decode('utf-8', errors='surrogateescape')
        tag, _, path = decoded.partition(' ')
        if tag != 'H':
            hidden_flags.append(f'{tag} {path}')
    if hidden_flags:
        raise VerificationError(f'hidden or non-normal index flags in {repo}:\n' + '\n'.join(hidden_flags))
    if _git_exit(tools, env, repo, 'diff-files', '--quiet', '--') != 0:
        raise VerificationError(f'tracked worktree bytes differ from the index: {repo}')
    if _git_exit(tools, env, repo, 'diff-index', '--cached', '--quiet', 'HEAD', '--') != 0:
        raise VerificationError(f'index differs from HEAD: {repo}')


__all__ = [name for name in globals() if not name.startswith("__")]
