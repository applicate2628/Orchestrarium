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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

PIN_PATH = "baseline/orchestrarium-v1/baseline-pin.json"
DISPOSITIONS_PATH = "baseline/orchestrarium-v1/reviewed-dispositions.json"
OBJECT_ID = re.compile(r"[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?")
SHA256 = re.compile(r"[0-9a-f]{64}")
FOCUSED_TESTS = (
    "tests/test_orche_baseline_pin.py",
    "tests/test_orche_pytest_baseline.py",
    "tests/test_orche_baseline_inventory.py",
    "tests/test_orche_target_effect_baseline.py",
    "tests/test_orche_command_baseline.py",
    "tests/test_orche_capability_baseline.py",
    "tests/test_orche_verifier_isolation.py",
    "tests/test_orche_review_regressions.py",
)
IGNORED_EXECUTABLE_PATHS = (
    ":(glob)tests/**",
    ":(glob)**/conftest.py",
    ":(glob)scripts/**",
    ":(glob)**/*.py",
    ":(glob)**/*.pyc",
    ":(glob)**/*.pyo",
    ":(glob)**/__pycache__/**",
    ":(glob)**/*.sh",
    ":(glob)**/*.ps1",
    ":(glob)**/pyproject.toml",
    ":(glob)**/pytest.ini",
    ":(glob)**/tox.ini",
    ":(glob)**/setup.cfg",
    ":(exclude,glob).scratch/**",
    ":(exclude,glob)node_modules/**",
    ":(exclude,glob).venv/**",
    ":(exclude,glob)venv/**",
)


class VerificationError(RuntimeError):
    pass


class VerificationBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class ExecutableIdentity:
    path: Path
    device: int
    inode: int
    mode: int
    uid: int
    gid: int
    size: int
    mtime_ns: int
    ctime_ns: int
    sha256: str


def _capture_executable_identity(path: Path) -> ExecutableIdentity:
    canonical = path.expanduser().resolve(strict=True)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(canonical, flags)
    except OSError as exc:
        raise VerificationError(f"cannot open selected executable {canonical}: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or not (before.st_mode & 0o111):
            raise VerificationError(f"selected executable is not a regular executable: {canonical}")
        digest = hashlib.sha256()
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            digest.update(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    stable_before = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_uid,
        before.st_gid,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    stable_after = (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_uid,
        after.st_gid,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if stable_before != stable_after:
        raise VerificationError(f"selected executable changed while hashing: {canonical}")
    return ExecutableIdentity(
        path=canonical,
        device=before.st_dev,
        inode=before.st_ino,
        mode=before.st_mode,
        uid=before.st_uid,
        gid=before.st_gid,
        size=before.st_size,
        mtime_ns=before.st_mtime_ns,
        ctime_ns=before.st_ctime_ns,
        sha256=digest.hexdigest(),
    )


def _verify_executable_identity(identity: ExecutableIdentity) -> None:
    current = _capture_executable_identity(identity.path)
    if current != identity:
        raise VerificationError(
            "selected verifier executable changed after preflight: "
            f"{identity.path}; expected_sha256={identity.sha256}, actual_sha256={current.sha256}"
        )


@dataclass(frozen=True)
class ExternalTools:
    python: Path
    git: Path
    bash: Path
    python_identity: ExecutableIdentity = field(init=False, repr=False)
    git_identity: ExecutableIdentity = field(init=False, repr=False)
    bash_identity: ExecutableIdentity = field(init=False, repr=False)

    def __post_init__(self) -> None:
        python_identity = _capture_executable_identity(self.python)
        git_identity = _capture_executable_identity(self.git)
        bash_identity = _capture_executable_identity(self.bash)
        object.__setattr__(self, "python", python_identity.path)
        object.__setattr__(self, "git", git_identity.path)
        object.__setattr__(self, "bash", bash_identity.path)
        object.__setattr__(self, "python_identity", python_identity)
        object.__setattr__(self, "git_identity", git_identity)
        object.__setattr__(self, "bash_identity", bash_identity)

    def identity_for(self, executable: str | os.PathLike[str]) -> ExecutableIdentity:
        supplied = Path(os.path.abspath(os.fspath(executable)))
        for identity in (
            self.python_identity,
            self.git_identity,
            self.bash_identity,
        ):
            if supplied == identity.path:
                return identity
        raise VerificationError(f"command does not use a selected verifier executable: {supplied}")

    def verify(self, executable: str | os.PathLike[str]) -> None:
        _verify_executable_identity(self.identity_for(executable))

    def verify_all(self) -> None:
        for identity in (
            self.python_identity,
            self.git_identity,
            self.bash_identity,
        ):
            _verify_executable_identity(identity)

    def assert_outside(self, worktrees: Sequence[Path]) -> None:
        labels = (
            ("Python", self.python_identity),
            ("Git", self.git_identity),
            ("Bash", self.bash_identity),
        )
        for label, identity in labels:
            for root in worktrees:
                if _inside(identity.path, root):
                    raise VerificationError(
                        f"{label} executable resolves inside tested worktree: {identity.path}"
                    )


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


VALIDATORS = (
    ValidatorSpec(
        "agents-spine",
        "python",
        ("scripts/validate-agents-spine.py", "--spine", "shared/AGENTS.shared.md"),
        r"(?m)^RESULT: PASS$",
        r"(?m)^RESULT: FAIL$",
    ),
    ValidatorSpec(
        "codex-pack",
        "bash",
        ("src.codex/skills/lead/scripts/validate-skill-pack.sh",),
        r"(?m)^VALIDATION PASSED(?: \(with warnings\))?$",
        r"(?m)^VALIDATION FAILED(?: \(with warnings\))?$",
    ),
    ValidatorSpec(
        "claude-pack",
        "bash",
        ("src.claude/agents/scripts/validate-skill-pack.sh",),
        r"(?m)^VALIDATION PASSED(?: \(with warnings\))?$",
        r"(?m)^VALIDATION FAILED$",
    ),
    ValidatorSpec(
        "gemini-pack",
        "bash",
        ("src.gemini/scripts/validate-pack.sh",),
        r"(?m)^PASS: Gemini .+ tree present at .+$",
        r"(?m)^FAIL: .+$",
    ),
    ValidatorSpec(
        "qwen-pack",
        "bash",
        ("src.qwen/scripts/validate-pack.sh",),
        r"(?m)^PASS: Qwen .+ tree present at .+$",
        r"(?m)^FAIL: .+$",
    ),
    ValidatorSpec(
        "agents-mode-docs",
        "python",
        ("scripts/sync-agents-mode-docs.py", "--root", ".", "--check"),
        r"(?m)^PASS: agents-mode docs are synced$",
        r"(?m)^FAIL: .+ is not synced$",
    ),
    ValidatorSpec(
        "universal-hooks",
        "python",
        ("scripts/sync-universal-hooks.py", "--check"),
        r"(?m)^PASS: universal-hooks canon in sync with both mirrors$",
        r"(?m)^FAIL: [0-9]+ mirrored file\(s\) drifted from scripts/universal-hooks/ canon\..*$",
    ),
    ValidatorSpec(
        "agents-mode-installers",
        "python",
        ("scripts/validate-agents-mode-installers.py", "--root", "."),
        r"(?m)^PASS: agents-mode installer regression validated$",
        r"(?m)^FAIL: .+$",
        (r"agents-mode-installer-regression[/\\][0-9a-f]{32}",),
    ),
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_ref(value: str, *, label: str) -> str:
    if not OBJECT_ID.fullmatch(value):
        raise VerificationError(
            f"{label} must be an exact 40- or 64-character hexadecimal object ID"
        )
    return value.lower()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_external_executable(
    value: Path, *, label: str, worktrees: Sequence[Path]
) -> Path:
    try:
        identity = _capture_executable_identity(value)
    except VerificationError as exc:
        raise VerificationError(f"cannot accept {label} executable {value}: {exc}") from exc
    for root in worktrees:
        if _inside(identity.path, root):
            raise VerificationError(
                f"{label} executable resolves inside tested worktree: {identity.path}"
            )
    return identity.path


def build_sanitized_env(
    *,
    tools: ExternalTools,
    lane_root: Path,
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    lane_root.mkdir(parents=True, exist_ok=True)
    directories = {
        "HOME": lane_root / "home",
        "USERPROFILE": lane_root / "home",
        "APPDATA": lane_root / "appdata",
        "LOCALAPPDATA": lane_root / "localappdata",
        "XDG_CONFIG_HOME": lane_root / "xdg-config",
        "XDG_CACHE_HOME": lane_root / "xdg-cache",
        "XDG_DATA_HOME": lane_root / "xdg-data",
        "XDG_STATE_HOME": lane_root / "xdg-state",
        "CODEX_HOME": lane_root / "codex",
        "CLAUDE_CONFIG_DIR": lane_root / "claude",
        "GEMINI_HOME": lane_root / "gemini",
        "QWEN_CODE_HOME": lane_root / "qwen",
        "KIMI_CODE_HOME": lane_root / "kimi",
        "TMPDIR": lane_root / "tmp",
    }
    for directory in directories.values():
        directory.mkdir(parents=True, exist_ok=True)
    gitconfig = lane_root / "gitconfig"
    gitconfig.write_text("", encoding="utf-8")
    path_dirs = list(
        dict.fromkeys(
            [
                os.fspath(tools.python.parent),
                os.fspath(tools.git.parent),
                os.fspath(tools.bash.parent),
                "/usr/local/bin",
                "/usr/bin",
                "/bin",
            ]
        )
    )
    env = {
        "PATH": os.pathsep.join(path_dirs),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUTF8": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONSAFEPATH": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.fspath(gitconfig),
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "CI": "1",
        **{key: os.fspath(path) for key, path in directories.items()},
    }
    if extra:
        env.update(extra)
    return env


def build_repository_env(
    *, tools: ExternalTools, lane_root: Path, repo_root: Path
) -> dict[str, str]:
    resolved_repo = repo_root.resolve(strict=True)
    if not resolved_repo.is_dir():
        raise VerificationError(f"repository import root is not a directory: {resolved_repo}")
    return build_sanitized_env(
        tools=tools,
        lane_root=lane_root,
        extra={"PYTHONPATH": os.fspath(resolved_repo)},
    )


def _resolve_git_dir(repo: Path) -> Path:
    resolved_repo = repo.resolve(strict=True)
    marker = resolved_repo / ".git"
    try:
        metadata = marker.lstat()
    except OSError as exc:
        raise VerificationError(f"cannot inspect worktree Git marker {marker}: {exc}") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise VerificationError(f"worktree Git marker must not be a symlink: {marker}")
    if stat.S_ISDIR(metadata.st_mode):
        return marker.resolve(strict=True)
    if not stat.S_ISREG(metadata.st_mode):
        raise VerificationError(f"worktree Git marker is not a directory or gitfile: {marker}")
    try:
        text = marker.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise VerificationError(f"cannot read worktree gitfile {marker}: {exc}") from exc
    lines = text.splitlines()
    if len(lines) != 1 or not lines[0].startswith("gitdir: "):
        raise VerificationError(f"malformed worktree gitfile: {marker}")
    raw = Path(lines[0][len("gitdir: ") :])
    git_dir = (resolved_repo / raw).resolve(strict=True) if not raw.is_absolute() else raw.resolve(strict=True)
    if not git_dir.is_dir():
        raise VerificationError(f"worktree gitdir is not a directory: {git_dir}")
    return git_dir


def _git_command(tools: ExternalTools, repo: Path, *arguments: str) -> list[str]:
    resolved_repo = repo.resolve(strict=True)
    git_dir = _resolve_git_dir(resolved_repo)
    overrides = (
        ("core.worktree", os.fspath(resolved_repo)),
        ("core.bare", "false"),
        ("core.fsmonitor", "false"),
        ("core.untrackedCache", "false"),
        ("core.ignoreStat", "false"),
        ("core.fileMode", "true"),
        ("core.checkStat", "default"),
        ("core.trustctime", "true"),
        ("core.sparseCheckout", "false"),
        ("core.sparseCheckoutCone", "false"),
        ("core.symlinks", "true"),
        ("core.hooksPath", "/dev/null"),
        ("core.attributesFile", "/dev/null"),
        ("core.excludesFile", "/dev/null"),
        ("diff.external", ""),
        ("diff.trustExitCode", "false"),
        ("status.showUntrackedFiles", "all"),
    )
    command = [
        os.fspath(tools.git),
        "--no-replace-objects",
        f"--git-dir={git_dir}",
        f"--work-tree={resolved_repo}",
    ]
    for key, value in overrides:
        command.extend(("-c", f"{key}={value}"))
    command.extend(arguments)
    return command


def _run_git(
    tools: ExternalTools,
    env: Mapping[str, str],
    repo: Path,
    *arguments: str,
    text: bool = True,
    input_data: bytes | None = None,
) -> str | bytes:
    tools.verify(tools.git)
    try:
        result = subprocess.run(
            _git_command(tools, repo, *arguments),
            env=dict(env),
            input=input_data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=text,
            check=False,
        )
    except OSError as exc:
        raise VerificationError(f"cannot launch selected Git executable: {exc}") from exc
    if result.returncode != 0:
        stderr = result.stderr if text else result.stderr.decode("utf-8", errors="replace")
        raise VerificationError(
            f"trusted Git command failed ({result.returncode}): {' '.join(arguments)}: {stderr.strip()}"
        )
    return result.stdout


def _git_exit(
    tools: ExternalTools, env: Mapping[str, str], repo: Path, *arguments: str
) -> int:
    tools.verify(tools.git)
    try:
        return subprocess.run(
            _git_command(tools, repo, *arguments),
            env=dict(env),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
    except OSError as exc:
        raise VerificationError(f"cannot launch selected Git executable: {exc}") from exc



def _assert_safe_local_config(
    tools: ExternalTools, env: Mapping[str, str], repo: Path
) -> None:
    raw = bytes(
        _run_git(
            tools,
            env,
            repo,
            "config",
            "--local",
            "--null",
            "--list",
            "--no-includes",
            text=False,
        )
    )
    dangerous_exact = {
        "core.worktree",
        "core.fsmonitor",
        "core.untrackedcache",
        "core.ignorestat",
        "core.sparsecheckout",
        "core.sparsecheckoutcone",
        "core.hookspath",
        "core.attributesfile",
        "core.excludesfile",
        "core.checkstat",
        "core.trustctime",
        "core.symlinks",
        "diff.external",
        "diff.trustexitcode",
        "status.showuntrackedfiles",
        "extensions.worktreeconfig",
    }
    dangerous_prefixes = (
        "include.",
        "includeif.",
        "filter.",
        "alias.",
    )
    dangerous: list[str] = []
    for record in raw.split(b"\x00"):
        if not record:
            continue
        key_raw, separator, _value = record.partition(b"\n")
        if not separator:
            raise VerificationError("malformed local Git configuration record")
        try:
            key = key_raw.decode("utf-8").lower()
        except UnicodeDecodeError as exc:
            raise VerificationError("local Git configuration key is not UTF-8") from exc
        is_external_diff = key.startswith("diff.") and key.endswith(".command")
        is_external_merge = key.startswith("merge.") and key.endswith(".driver")
        is_submodule_ignore = key.startswith("submodule.") and key.endswith(".ignore")
        if (
            key in dangerous_exact
            or key.startswith(dangerous_prefixes)
            or is_external_diff
            or is_external_merge
            or is_submodule_ignore
        ):
            dangerous.append(key)
    if dangerous:
        raise VerificationError(
            "unsafe repository-local Git configuration is forbidden for trusted checks: "
            + ", ".join(sorted(set(dangerous)))
        )

def assert_clean_worktree(
    repo: Path,
    *,
    expected_ref: str,
    tools: ExternalTools,
    env: Mapping[str, str],
    expected_tree: str | None = None,
) -> None:
    resolved_repo = repo.resolve(strict=True)
    _assert_safe_local_config(tools, env, resolved_repo)
    actual_top = Path(
        str(_run_git(tools, env, resolved_repo, "rev-parse", "--show-toplevel")).strip()
    ).resolve(strict=True)
    if actual_top != resolved_repo:
        raise VerificationError(
            f"trusted Git worktree binding mismatch: expected={resolved_repo}, actual={actual_top}"
        )
    actual_git_dir = Path(
        str(_run_git(tools, env, resolved_repo, "rev-parse", "--absolute-git-dir")).strip()
    ).resolve(strict=True)
    expected_git_dir = _resolve_git_dir(resolved_repo)
    if actual_git_dir != expected_git_dir:
        raise VerificationError(
            f"trusted Git directory binding mismatch: expected={expected_git_dir}, actual={actual_git_dir}"
        )
    actual_ref = str(_run_git(tools, env, resolved_repo, "rev-parse", "HEAD")).strip().lower()
    if actual_ref != expected_ref:
        raise VerificationError(
            f"worktree HEAD mismatch for {resolved_repo}: expected={expected_ref}, actual={actual_ref}"
        )
    if expected_tree is not None:
        actual_tree = str(
            _run_git(tools, env, resolved_repo, "rev-parse", "HEAD^{tree}")
        ).strip().lower()
        if actual_tree != expected_tree:
            raise VerificationError(
                f"worktree tree mismatch for {resolved_repo}: expected={expected_tree}, actual={actual_tree}"
            )
    status_text = str(
        _run_git(
            tools,
            env,
            resolved_repo,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--ignore-submodules=none",
        )
    )
    if status_text:
        raise VerificationError(f"dirty worktree: {resolved_repo}\n{status_text.rstrip()}")
    ignored = bytes(
        _run_git(
            tools,
            env,
            resolved_repo,
            "ls-files",
            "--others",
            "--ignored",
            "--exclude-standard",
            "-z",
            "--",
            *IGNORED_EXECUTABLE_PATHS,
            text=False,
        )
    )
    ignored_paths = sorted(
        item.decode("utf-8", errors="surrogateescape")
        for item in ignored.split(b"\x00")
        if item
    )
    if ignored_paths:
        raise VerificationError(
            f"ignored executable, test, configuration, or bytecode input in {resolved_repo}:\n"
            + "\n".join(ignored_paths)
        )
    flag_data = bytes(
        _run_git(tools, env, resolved_repo, "ls-files", "-v", "-z", text=False)
    )
    hidden_flags: list[str] = []
    for record in flag_data.split(b"\x00"):
        if not record:
            continue
        decoded = record.decode("utf-8", errors="surrogateescape")
        tag, _, path = decoded.partition(" ")
        if tag != "H":
            hidden_flags.append(f"{tag} {path}")
    if hidden_flags:
        raise VerificationError(
            f"hidden or non-normal index flags in {resolved_repo}:\n"
            + "\n".join(hidden_flags)
        )
    if (
        _git_exit(
            tools,
            env,
            resolved_repo,
            "diff-files",
            "--quiet",
            "--ignore-submodules=none",
            "--",
        )
        != 0
    ):
        raise VerificationError(f"tracked worktree bytes differ from the index: {resolved_repo}")
    if (
        _git_exit(
            tools,
            env,
            resolved_repo,
            "diff-index",
            "--cached",
            "--quiet",
            "--ignore-submodules=none",
            "HEAD",
            "--",
        )
        != 0
    ):
        raise VerificationError(f"index differs from HEAD: {resolved_repo}")


__all__ = [name for name in globals() if not name.startswith("__")]
