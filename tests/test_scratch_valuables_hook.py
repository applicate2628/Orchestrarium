"""Tests for the scratch-valuables SessionStart hook's Python brain
(`scripts/universal-hooks/scripts/check-scratch-valuables.py`).

This file covers what is UNIQUE to the hook and not already exercised by
`tests/test_cleanup_engine.py` (which tests the same algorithm mirrored in
`scripts/maintenance/cleanup.py`): the presentation-layer threshold-
summarization (`_build_message`), the hook's own `main()` end-to-end
envelope handling, and a light regression pass over the mirrored scan
(git-uniqueness primary predicate, junction safety, zero mutation) to catch
drift between the two intentionally-duplicated implementations.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "scripts" / "universal-hooks" / "scripts" / "check-scratch-valuables.py"
SPEC = importlib.util.spec_from_file_location("scratch_valuables_hook", HOOK)
assert SPEC is not None and SPEC.loader is not None
hook = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = hook
SPEC.loader.exec_module(hook)


def _init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)


def _make_valuable(path: str, age_days: float, size: int = 10) -> dict:
    return {"path": path, "age_days": age_days, "size": size}


# ---------------------------------------------------------------------------
# Threshold-summarization (presentation layer, built on top of the already
# git-unique candidate list)
# ---------------------------------------------------------------------------


def test_under_threshold_lists_every_candidate_individually_longest_lingering_first():
    # `valuables` arrives newest-first (index 0 = lowest age_days), matching
    # _scan_valuables's return contract: file0.md is newest (age=0), the
    # last entry is oldest (age=SUMMARIZE_THRESHOLD-1).
    valuables = [_make_valuable(f"file{i}.md", age_days=float(i)) for i in range(hook.SUMMARIZE_THRESHOLD)]

    message = hook._build_message(valuables)

    assert "summarized by top-level" not in message
    assert "longest-lingering first" in message
    for item in valuables:
        assert item["path"] in message
    # The OLDEST (highest age_days) file must print before the newest one --
    # the operator's stated risk is data that lingered LONG, and
    # newest-first anti-selects for exactly the file that matters.
    oldest_path = max(valuables, key=lambda v: v["age_days"])["path"]
    newest_path = min(valuables, key=lambda v: v["age_days"])["path"]
    assert message.index(oldest_path) < message.index(newest_path)


def test_over_threshold_summarizes_by_top_level_directory_and_leads_with_longest_lingering():
    # More than SUMMARIZE_THRESHOLD candidates, spread across a few top-level
    # .scratch/ subdirectories, sorted newest-first like _scan_valuables.
    valuables = []
    for i in range(hook.SUMMARIZE_THRESHOLD + 10):
        directory = "alpha" if i % 2 == 0 else "beta"
        valuables.append(_make_valuable(f"{directory}/file{i:03d}.md", age_days=float(100 - i)))
    valuables.sort(key=lambda v: v["age_days"])  # newest (lowest age) first, like scan_valuables

    message = hook._build_message(valuables)

    assert "summarized by top-level" in message
    assert "alpha:" in message
    assert "beta:" in message
    assert "Longest-lingering" in message
    assert "Most recently modified" in message
    # The listed window is capped, not a flat dump of every path.
    listed_paths = [item["path"] for item in valuables]
    individually_listed = sum(1 for p in listed_paths if p in message)
    assert individually_listed <= hook.MAX_RECENT_LISTED
    # The single OLDEST candidate (the operator's actual risk shape) MUST be
    # listed, and the "Longest-lingering" label must come before it.
    oldest = valuables[-1]
    newest = valuables[0]
    assert oldest["path"] in message
    assert newest["path"] in message
    assert message.index("Longest-lingering") < message.index(oldest["path"])
    # Longest-lingering leads the message ahead of most-recently-modified.
    assert message.index("Longest-lingering") < message.index("Most recently modified")


def test_summarization_threshold_boundary_exactly_at_threshold_is_full_list():
    valuables = [_make_valuable(f"file{i}.md", age_days=float(i)) for i in range(hook.SUMMARIZE_THRESHOLD)]

    message = hook._build_message(valuables)

    assert "summarized by top-level" not in message


def test_summarization_threshold_boundary_one_over_summarizes():
    valuables = [_make_valuable(f"file{i}.md", age_days=float(i)) for i in range(hook.SUMMARIZE_THRESHOLD + 1)]

    message = hook._build_message(valuables)

    assert "summarized by top-level" in message


def test_directory_grouping_counts_files_directly_under_scratch_root_separately():
    valuables = (
        [_make_valuable(f"root-file{i}.md", age_days=float(i)) for i in range(hook.SUMMARIZE_THRESHOLD + 5)]
    )

    message = hook._build_message(valuables)

    assert "(.scratch root):" in message


def test_directory_summary_is_capped_to_top_n_with_a_more_tail():
    # One file each in more than DIR_SUMMARY_TOP_N distinct top-level
    # directories: the by-directory summary itself must not grow unbounded
    # (it is re-injected as additionalContext at every SessionStart).
    directory_count = hook.DIR_SUMMARY_TOP_N + 8
    valuables = [
        _make_valuable(f"dir{i:03d}/file.md", age_days=float(i))
        for i in range(directory_count)
    ]

    message = hook._build_message(valuables)

    named_directories = sum(1 for i in range(directory_count) if f"dir{i:03d}:" in message)
    assert named_directories <= hook.DIR_SUMMARY_TOP_N
    assert "more director" in message
    remaining = directory_count - hook.DIR_SUMMARY_TOP_N
    assert f"{remaining} more director" in message


# ---------------------------------------------------------------------------
# main() end-to-end (stdin envelope -> stdout JSON), mirroring the actual
# hook wrapper contract
# ---------------------------------------------------------------------------


def _run_main_with_envelope(monkeypatch, capsys, envelope: dict) -> tuple[int, str]:
    monkeypatch.setattr(hook, "read_stdin_utf8", lambda: json.dumps(envelope))
    exit_code = hook.main()
    captured = capsys.readouterr()
    return exit_code, captured.out


def test_main_is_silent_when_scratch_has_no_candidates(tmp_path: Path, monkeypatch, capsys):
    (tmp_path / hook.SCRATCH_DIRNAME).mkdir()

    exit_code, out = _run_main_with_envelope(monkeypatch, capsys, {"cwd": str(tmp_path)})

    assert exit_code == 0
    assert out == ""


def test_main_emits_context_for_a_unique_valuable(tmp_path: Path, monkeypatch, capsys):
    _init_git_repo(tmp_path)
    scratch = tmp_path / hook.SCRATCH_DIRNAME
    scratch.mkdir()
    (scratch / "unique.md").write_text("genuinely unique content", encoding="utf-8")

    exit_code, out = _run_main_with_envelope(monkeypatch, capsys, {"cwd": str(tmp_path)})

    assert exit_code == 0
    payload = json.loads(out)
    context = payload["hookSpecificOutput"]["additionalContext"]
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "unique.md" in context


def test_main_is_silent_for_a_dispatched_subagent(tmp_path: Path, monkeypatch, capsys):
    _init_git_repo(tmp_path)
    scratch = tmp_path / hook.SCRATCH_DIRNAME
    scratch.mkdir()
    (scratch / "unique.md").write_text("genuinely unique content", encoding="utf-8")

    exit_code, out = _run_main_with_envelope(
        monkeypatch, capsys, {"cwd": str(tmp_path), "agent_id": "abc"}
    )

    assert exit_code == 0
    assert out == ""


# ---------------------------------------------------------------------------
# Light regression pass over the mirrored scan (drift check against
# scripts/maintenance/cleanup.py's algorithm)
# ---------------------------------------------------------------------------


def test_scan_git_uniqueness_predicate_matches_cleanup_engine_shape(tmp_path: Path):
    _init_git_repo(tmp_path)
    scratch = tmp_path / hook.SCRATCH_DIRNAME
    scratch.mkdir()
    (scratch / "unique.md").write_text("genuinely unique content", encoding="utf-8")
    (scratch / "noise.log").write_text("unique but junk extension", encoding="utf-8")

    result = hook._scan_valuables(scratch)

    assert [item["path"] for item in result] == ["unique.md"]


@pytest.mark.parametrize(
    "dirname", ["__pycache__", "node_modules", ".pytest_cache", ".mypy_cache", ".ruff_cache"]
)
def test_unambiguous_cache_directory_is_pruned_at_any_depth(tmp_path: Path, dirname: str):
    # Regression: a prior direct-child-only version of this rule leaked
    # nested cache-directory files into the flagged set. Mirrors the
    # equivalent test in tests/test_cleanup_engine.py.
    _init_git_repo(tmp_path)
    scratch = tmp_path / hook.SCRATCH_DIRNAME
    nested = scratch / "reviews" / "some-snapshot" / "tests" / dirname
    nested.mkdir(parents=True)
    (nested / "compiled.pyc").write_text("cached bytecode", encoding="utf-8")

    result = hook._scan_valuables(scratch)

    assert result == []


@pytest.mark.parametrize("dirname", ["build", "dist", ".cache"])
def test_ambiguous_directory_name_nested_deeper_is_not_pruned(tmp_path: Path, dirname: str):
    _init_git_repo(tmp_path)
    scratch = tmp_path / hook.SCRATCH_DIRNAME
    nested = scratch / "plans" / dirname
    nested.mkdir(parents=True)
    (nested / "notes.md").write_text("hand-authored content", encoding="utf-8")

    result = hook._scan_valuables(scratch)

    assert [item["path"] for item in result] == [f"plans/{dirname}/notes.md"]


def test_scan_falls_back_to_age_gate_when_not_a_git_repository(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(hook, "_find_git_root", lambda start: None)
    scratch = tmp_path / hook.SCRATCH_DIRNAME
    scratch.mkdir()
    old_path = scratch / "old.md"
    old_path.write_text("anything", encoding="utf-8")
    old_timestamp = (
        __import__("datetime").datetime.now(__import__("datetime").timezone.utc) - timedelta(days=30)
    ).timestamp()
    os.utime(old_path, (old_timestamp, old_timestamp))

    result = hook._scan_valuables(scratch)

    assert [item["path"] for item in result] == ["old.md"]


def test_junction_is_never_followed_or_flagged(tmp_path: Path):
    _init_git_repo(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "target.md").write_text("outside content", encoding="utf-8")
    scratch = tmp_path / hook.SCRATCH_DIRNAME
    scratch.mkdir()
    junction = scratch / "junction-dir"

    if os.name != "nt":
        pytest.skip("junction test is Windows-only")
    result = subprocess.run(
        [
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            "New-Item", "-ItemType", "Junction", "-Path", str(junction), "-Target", str(outside),
        ],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0 or not os.path.isjunction(junction):
        pytest.skip("junction creation is unavailable on this host")

    scan_result = hook._scan_valuables(scratch)

    assert scan_result == []
    assert (outside / "target.md").exists()


def test_zero_mutation_of_working_tree_and_git_object_store(tmp_path: Path):
    _init_git_repo(tmp_path)
    scratch = tmp_path / hook.SCRATCH_DIRNAME
    scratch.mkdir()
    (scratch / "unique.md").write_text("genuinely unique content", encoding="utf-8")

    def snapshot() -> dict:
        entries = {}
        for dirpath, _dirnames, filenames in os.walk(tmp_path):
            for name in filenames:
                full = Path(dirpath) / name
                entries[str(full.relative_to(tmp_path))] = (full.stat().st_mtime, full.stat().st_size)
        return entries

    before = snapshot()
    hook._scan_valuables(scratch)
    hook._scan_valuables(scratch)
    after = snapshot()

    assert before == after


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
