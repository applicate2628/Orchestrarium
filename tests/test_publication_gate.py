"""Staged-target probes; observed source is only the publication gate.

The scanner is an explicit fixture stub. Git operations mutate only tmp_path,
never the source checkout or the separately owned lifecycle implementation.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "check-publication-gate.py"
DATED = "# Release Notes\n\n## 2026-10-05\n\n- Explain the operator workflow improvement: café, проверка.\n"
UNRELEASED = DATED + "\n## Unreleased\n\n- Pending workflow change.\n"


def _env() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               PYTHONDONTWRITEBYTECODE="1")
    return env


def _git(repo: Path, *args: str, input_text: str | None = None) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], env=_env(),
        input=input_text.encode("utf-8") if input_text is not None else None,
        capture_output=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    return proc.stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "core.autocrlf", "false")
    scanner = tmp_path / "src.codex/skills/lead/scripts/check-publication-safety.py"
    scanner.parent.mkdir(parents=True)
    scanner.write_text("raise SystemExit(0)\n", encoding="utf-8")
    return tmp_path


def _stage(repo: Path, path: str, content: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")
    _git(repo, "add", "--", path)


def _gate(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(GATE), *args], cwd=repo, env=_env(),
        text=True, encoding="utf-8", capture_output=True, check=False,
    )


@pytest.mark.parametrize("working_notes", [UNRELEASED, None], ids=["unstaged-unreleased", "working-copy-absent"])
def test_valid_indexed_notes_ignore_working_copy(repo: Path, working_notes: str | None) -> None:
    _stage(repo, "scripts/changed.py", "# Synthetic release-relevant change\n")
    _stage(repo, "RELEASE_NOTES.md", DATED)
    tree = _git(repo, "write-tree")
    paths = _git(repo, "diff", "--cached", "--name-only", "--diff-filter=ACMRTUXB", "-z", "--")
    assert paths == b"RELEASE_NOTES.md\0scripts/changed.py\0"
    assert _git(repo, "show", ":RELEASE_NOTES.md") == DATED.encode("utf-8")
    baseline = _gate(repo)
    if working_notes is None:
        (repo / "RELEASE_NOTES.md").unlink()
    else:
        (repo / "RELEASE_NOTES.md").write_text(working_notes, encoding="utf-8")
    divergent = _gate(repo)
    assert _git(repo, "write-tree") == tree
    print(f"SAMPLE paths={paths!r}; tree={tree.decode().strip()}; baseline={baseline.returncode}; divergent={divergent.returncode}; diagnostic={divergent.stderr.strip()!r}")
    assert baseline.returncode == divergent.returncode == 0, divergent.stderr


def test_invalid_indexed_notes_rejected_with_valid_working_copy(repo: Path) -> None:
    _stage(repo, "scripts/changed.py", "# Synthetic release-relevant change\n")
    _stage(repo, "RELEASE_NOTES.md", UNRELEASED)
    tree = _git(repo, "write-tree")
    baseline = _gate(repo)
    (repo / "RELEASE_NOTES.md").write_text(DATED, encoding="utf-8")
    divergent = _gate(repo)
    assert _git(repo, "write-tree") == tree
    assert _git(repo, "show", ":RELEASE_NOTES.md") == UNRELEASED.encode("utf-8")
    print(f"SAMPLE invalid-index tree={tree.decode().strip()}; baseline={baseline.returncode}; divergent={divergent.returncode}; output={divergent.stdout.strip()!r}")
    assert baseline.returncode == divergent.returncode == 1
    assert "'## Unreleased' bucket" in divergent.stderr


def test_scanner_failure_precedes_exemption_and_notes(repo: Path) -> None:
    _stage(repo, "scripts/changed.py", "# Synthetic change\n")
    scanner = repo / "src.codex/skills/lead/scripts/check-publication-safety.py"
    scanner.write_text("raise SystemExit(7)\n", encoding="utf-8")
    assert _gate(repo, "--release-notes-exempt", "reviewed local hygiene").returncode == 7


def test_no_staged_paths(repo: Path) -> None:
    result = _gate(repo)
    assert result.returncode == 0, result.stderr
    assert "no staged tracked changes" in result.stdout


def test_local_only_path_class_is_exempt(repo: Path) -> None:
    _stage(repo, ".reports/result.md", "Synthetic summary\n")
    result = _gate(repo)
    assert result.returncode == 0, result.stderr
    assert "exempt by path class" in result.stdout


def test_reviewer_exemption_requires_nonempty_reason(repo: Path) -> None:
    _stage(repo, "scripts/changed.py", "# Synthetic change\n")
    valid = _gate(repo, "--release-notes-exempt", "reviewed local hygiene")
    invalid = _gate(repo, "--release-notes-exempt", " ")
    assert valid.returncode == 0, valid.stderr
    assert "explicitly exempted by reviewer" in valid.stdout
    assert invalid.returncode == 2
    assert "requires a non-empty reason" in invalid.stderr


def test_work_items_remain_forbidden_even_with_exemption(repo: Path) -> None:
    _stage(repo, "work-items/active/example/status.md", "Synthetic local task\n")
    result = _gate(repo, "--release-notes-exempt", "reviewed local hygiene")
    assert result.returncode == 1
    assert "local-only task memory" in result.stderr


def test_working_notes_do_not_satisfy_missing_staged_notes(repo: Path) -> None:
    _stage(repo, "scripts/changed.py", "# Synthetic change\n")
    (repo / "RELEASE_NOTES.md").write_text(DATED, encoding="utf-8")
    result = _gate(repo)
    assert result.returncode == 1
    assert "release-relevant staged changes require" in result.stderr


@pytest.mark.parametrize(("notes", "diagnostic"), [
    ("# Release Notes\n", "at least one top-level"),
    (DATED + "\n## 2026-10-05\n", "duplicate dated section"),
    ("## 2026-10-04\n- Earlier change.\n\n" + DATED, "reverse-chronological order"),
])
def test_indexed_structure_errors_remain_visible(repo: Path, notes: str, diagnostic: str) -> None:
    _stage(repo, "scripts/changed.py", "# Synthetic change\n")
    _stage(repo, "RELEASE_NOTES.md", notes)
    result = _gate(repo)
    assert result.returncode == 1
    assert diagnostic in result.stderr


def test_staged_notes_must_add_explanatory_content(repo: Path) -> None:
    _stage(repo, "scripts/changed.py", "# Synthetic change\n")
    _stage(repo, "RELEASE_NOTES.md", "## 2026-10-05\n- Earlier change.\n")
    _git(repo, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
         "-c", "core.hooksPath=" + os.devnull, "commit", "-m", "synthetic baseline")
    _stage(repo, "scripts/changed.py", "# Second synthetic change\n")
    _stage(repo, "RELEASE_NOTES.md", "# Release Notes\n\n## 2026-10-05\n- Earlier change.\n")
    result = _gate(repo)
    assert result.returncode == 1
    assert "must add a dated section or at least one explanatory bullet" in result.stderr


def test_unreadable_indexed_notes_do_not_fall_back_to_working_copy(repo: Path) -> None:
    _stage(repo, "scripts/changed.py", "# Synthetic change\n")
    _stage(repo, "RELEASE_NOTES.md", DATED)
    blob = _git(repo, "rev-parse", ":RELEASE_NOTES.md").decode().strip()
    _git(repo, "update-index", "--index-info", input_text=(
        "0 " + "0" * 40 + "\tRELEASE_NOTES.md\n" +
        "".join(f"100644 {blob} {stage}\tRELEASE_NOTES.md\n" for stage in (1, 2, 3))
    ))
    result = _gate(repo)
    assert result.returncode == 1
    assert "could not read staged RELEASE_NOTES.md" in result.stderr


def test_invalid_indexed_utf8_remains_visible_with_valid_working_copy(repo: Path) -> None:
    _stage(repo, "scripts/changed.py", "# Synthetic change\n")
    (repo / "RELEASE_NOTES.md").write_bytes(DATED.encode("utf-8") + b"\xff\n")
    _git(repo, "add", "--", "RELEASE_NOTES.md")
    (repo / "RELEASE_NOTES.md").write_text(DATED, encoding="utf-8")
    result = _gate(repo)
    assert result.returncode == 1
    assert "must be valid UTF-8" in result.stderr


def test_indexed_crlf_notes_keep_dated_section_interpretation(repo: Path) -> None:
    _stage(repo, "scripts/changed.py", "# Synthetic change\n")
    (repo / "RELEASE_NOTES.md").write_bytes(DATED.replace("\n", "\r\n").encode("utf-8"))
    _git(repo, "add", "--", "RELEASE_NOTES.md")
    (repo / "RELEASE_NOTES.md").unlink()
    result = _gate(repo)
    assert result.returncode == 0, result.stderr
