from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
HOOKS = (
    ROOT / "scripts" / "universal-hooks" / "scripts" / "check-scratch-valuables.py",
    ROOT / "src.codex" / "skills" / "lead" / "scripts" / "check-scratch-valuables.py",
    ROOT / "src.claude" / "agents" / "scripts" / "check-scratch-valuables.py",
)


def load_hook(path: Path, suffix: str):
    spec = importlib.util.spec_from_file_location(f"scratch_watchdog_{suffix}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_repo(path: Path, *, git_file: bool = False) -> Path:
    path.mkdir(parents=True)
    git_entry = path / ".git"
    if git_file:
        git_entry.write_text("gitdir: ../git-data\n", encoding="utf-8")
    else:
        git_entry.mkdir()
    return path


@pytest.mark.parametrize("hook_index", range(len(HOOKS)))
def test_repository_root_resolution_is_bounded_and_unambiguous(
    tmp_path: Path, hook_index: int
) -> None:
    hook = load_hook(HOOKS[hook_index], str(hook_index))
    outer = make_repo(tmp_path / "outer")
    fixture_root = outer / ".scratch" / "pytest"
    workspace = fixture_root / "workspace"
    repo = make_repo(workspace / "repo", git_file=hook_index % 2 == 1)
    nested = repo / "nested" / "work"
    nested.mkdir(parents=True)

    exact = hook.resolve_repository_root(
        {"cwd": str(repo)}, time.monotonic() + 10
    )
    assert exact.status == "selected"
    assert exact.root == repo

    containing = hook.resolve_repository_root(
        {"cwd": str(nested)}, time.monotonic() + 10
    )
    assert containing.status == "selected"
    assert containing.root == repo

    direct_child = hook.resolve_repository_root(
        {"cwd": str(workspace)}, time.monotonic() + 10
    )
    assert direct_child.status == "selected"
    assert direct_child.root == repo

    make_repo(workspace / "second")
    ambiguous = hook.resolve_repository_root(
        {"cwd": str(workspace)}, time.monotonic() + 10
    )
    assert ambiguous.status == "ambiguous"
    assert ambiguous.root is None
    assert ambiguous.candidate_count == 2

    missing = fixture_root / "empty"
    missing.mkdir()
    not_found = hook.resolve_repository_root(
        {"cwd": str(missing)}, time.monotonic() + 10
    )
    assert not_found.status == "none"
    assert not_found.root is None

    limited = hook.resolve_repository_root(
        {"cwd": str(workspace)}, time.monotonic() - 1
    )
    assert limited.status == "budget-limited"
    assert limited.root is None


@pytest.mark.parametrize("hook_index", range(len(HOOKS)))
def test_repository_root_resolution_rejects_link_components(
    tmp_path: Path, hook_index: int
) -> None:
    hook = load_hook(HOOKS[hook_index], f"link_{hook_index}")
    repo = make_repo(tmp_path / "repo")
    link = tmp_path / "repo-link"
    try:
        link.symlink_to(repo, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("directory symlinks are unavailable")

    result = hook.resolve_repository_root(
        {"cwd": str(link)}, time.monotonic() + 10
    )
    assert result.status == "unsafe"
    assert result.root is None

    workspace = tmp_path / "workspace"
    selected = make_repo(workspace / "selected")
    unrelated = workspace / "unrelated-link"
    unrelated.symlink_to(repo, target_is_directory=True)
    parent_result = hook.resolve_repository_root(
        {"cwd": str(workspace)}, time.monotonic() + 10
    )
    assert parent_result.status == "selected"
    assert parent_result.root == selected


@pytest.mark.parametrize("hook_index", range(len(HOOKS)))
def test_root_resolution_and_scan_share_one_deadline(
    tmp_path: Path, hook_index: int
) -> None:
    hook = load_hook(HOOKS[hook_index], f"deadline_{hook_index}")
    repo = make_repo(tmp_path / "repo")
    scratch = repo / ".scratch"
    scratch.mkdir()
    (scratch / "candidate.txt").write_text("candidate", encoding="utf-8")
    report = hook.ScanReport()

    valuables = hook._scan_valuables(
        scratch,
        deadline=time.monotonic() - 1,
        report=report,
    )

    assert valuables == []
    assert report.walk_truncated
    assert report.budget_limited


def test_universal_hook_mirrors_are_generated_byte_identically() -> None:
    canonical = HOOKS[0].read_bytes()
    assert HOOKS[1].read_bytes() == canonical
    assert HOOKS[2].read_bytes() == canonical


def test_real_hook_entrypoint_stays_within_end_to_end_budget(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    repo = workspace / "repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    scratch = repo / ".scratch"
    scratch.mkdir()
    for index in range(240):
        candidate = scratch / f"valuable-{index:03d}.txt"
        candidate.write_text(f"valuable {index}\n", encoding="utf-8")
        os.utime(candidate, (1, 1))

    started = time.perf_counter()
    result = subprocess.run(
        [sys.executable, str(HOOKS[0])],
        input=json.dumps({"cwd": str(workspace)}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=2,
    )
    elapsed = time.perf_counter() - started

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    message = payload["hookSpecificOutput"]["additionalContext"]
    assert "[scratch watchdog budget]" in message
    assert elapsed <= 0.30, f"hook took {elapsed:.3f}s"
