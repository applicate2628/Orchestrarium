from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "scripts" / "universal-hooks" / "scripts" / "check-publication-safety.py"


def _git(repo: Path, *args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert _git(repo, "init").returncode == 0
    assert _git(repo, "config", "user.name", "Test User").returncode == 0
    assert _git(repo, "config", "user.email", "test@example.invalid").returncode == 0
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    assert _git(repo, "add", "base.txt").returncode == 0
    assert _git(repo, "commit", "-m", "base").returncode == 0
    head = _git(repo, "rev-parse", "HEAD")
    assert head.returncode == 0
    return repo, head.stdout.strip()


def _stage_gitlink(
    repo: Path,
    commit: str,
    path: str = "vendor/submodule",
) -> None:
    result = _git(
        repo,
        "update-index",
        "--add",
        "--cacheinfo",
        f"160000,{commit},{path}",
    )
    assert result.returncode == 0, result.stderr


def _scan(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(SCANNER)],
        cwd=repo,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_cached_scan_accepts_clean_staged_gitlink(tmp_path: Path) -> None:
    repo, head = _repo(tmp_path)
    _stage_gitlink(repo, head)

    result = _scan(repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "PS-INPUT-REFUSAL" not in result.stdout + result.stderr


def test_cached_scan_accepts_gitlink_with_nonlocal_target_commit(tmp_path: Path) -> None:
    repo, _head = _repo(tmp_path)
    missing_commit = "f" * 40
    assert _git(repo, "cat-file", "-e", missing_commit).returncode != 0
    _stage_gitlink(repo, missing_commit)

    result = _scan(repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "PS-INPUT-REFUSAL" not in result.stdout + result.stderr


def test_cached_scan_still_checks_gitlink_path(tmp_path: Path) -> None:
    repo, head = _repo(tmp_path)
    _stage_gitlink(repo, head, ".env")

    result = _scan(repo)

    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "class=filename-env" in output
    assert "PS-INPUT-REFUSAL" not in output


def test_cached_scan_still_refuses_regular_entry_with_nonblob_object(tmp_path: Path) -> None:
    repo, head = _repo(tmp_path)
    staged = _git(
        repo,
        "update-index",
        "--add",
        "--cacheinfo",
        f"100644,{head},not-a-blob.txt",
    )
    assert staged.returncode == 0, staged.stderr

    result = _scan(repo)

    output = result.stdout + result.stderr
    assert result.returncode == 2, output
    assert "PS-INPUT-REFUSAL" in output


def test_cached_scan_continues_past_gitlink_and_blocks_other_staged_leak(tmp_path: Path) -> None:
    repo, head = _repo(tmp_path)
    _stage_gitlink(repo, head)
    (repo / "leak.txt").write_text("AKIA" + ("A" * 16) + "\n", encoding="utf-8")
    assert _git(repo, "add", "leak.txt").returncode == 0

    result = _scan(repo)

    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "PS-FINDING-CONTENT" in output
    assert "PS-INPUT-REFUSAL" not in output
