import importlib.util
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "scripts" / "maintenance" / "cleanup.py"
SPEC = importlib.util.spec_from_file_location("cleanup_engine", ENGINE)
assert SPEC is not None and SPEC.loader is not None
cleanup = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cleanup
SPEC.loader.exec_module(cleanup)

NOW = datetime(2026, 7, 16, 12, 34, 56, tzinfo=timezone.utc)


def write_file(root: Path, relative: str, *, age_days: float, text: str = "data") -> Path:
    path = root / Path(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    timestamp = (NOW - timedelta(days=age_days)).timestamp()
    os.utime(path, (timestamp, timestamp))
    return path


def write_active_reference(root: Path, text: str, name: str = "status.md") -> Path:
    return write_file(
        root,
        f"work-items/active/live-item/{name}",
        age_days=0,
        text=text,
    )


def outcome(report, relative: str) -> str:
    return next(
        action.outcome
        for action in report.actions
        if action.relative_path.as_posix() == relative
    )


def test_sweep_dry_run_then_apply_preserves_rename_xor_and_readme(tmp_path: Path):
    source = write_file(tmp_path, ".scratch/jobs/result.out", age_days=8, text="payload")

    dry_run = cleanup.run_sweep(tmp_path, now=NOW)

    assert source.read_text(encoding="utf-8") == "payload"
    assert dry_run.run_dir is None
    assert outcome(dry_run, ".scratch/jobs/result.out") == "would-move"
    assert dry_run.telemetry.eligible.count == 1
    assert not (tmp_path / ".scratch/_trash").exists()

    applied = cleanup.run_sweep(tmp_path, apply=True, now=NOW)

    assert applied.run_dir == tmp_path / ".scratch/_trash/2026-07-16/123456"
    destination = applied.run_dir / ".scratch/jobs/result.out"
    assert source.exists() is False
    assert destination.read_text(encoding="utf-8") == "payload"
    assert cleanup.classify_transition(source, destination) == "destination-only"
    assert outcome(applied, ".scratch/jobs/result.out") == "moved"
    readme = tmp_path / ".scratch/_trash/README.md"
    assert "wipeable zone" in readme.read_text(encoding="utf-8")


def test_transition_table_classifies_all_four_states(tmp_path: Path):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.write_text("source", encoding="utf-8")
    assert cleanup.classify_transition(source, destination) == "source-only"
    destination.write_text("destination", encoding="utf-8")
    assert cleanup.classify_transition(source, destination) == "both"
    source.unlink()
    assert cleanup.classify_transition(source, destination) == "destination-only"
    destination.unlink()
    assert cleanup.classify_transition(source, destination) == "neither"


def test_same_injected_timestamp_reservations_get_unique_run_directories(tmp_path: Path):
    first = cleanup.reserve_run_dir(tmp_path, now=NOW)
    second = cleanup.reserve_run_dir(tmp_path, now=NOW)

    assert first.name == "123456"
    assert second.name == "123456-2"
    assert first.parent == second.parent == tmp_path / ".scratch/_trash/2026-07-16"


def test_restore_preserves_repository_relative_path(tmp_path: Path):
    live = write_file(tmp_path, ".scratch/nested/result.err", age_days=8, text="restore-me")
    sweep = cleanup.run_sweep(tmp_path, apply=True, now=NOW)
    assert sweep.run_dir is not None

    restored = cleanup.run_restore(tmp_path, sweep.run_dir, apply=True, now=NOW)

    assert live.read_text(encoding="utf-8") == "restore-me"
    assert outcome(restored, ".scratch/nested/result.err") == "restored"
    assert not (sweep.run_dir / ".scratch/nested/result.err").exists()


def test_restore_occupied_live_target_skips_without_clobbering(tmp_path: Path):
    run_dir = tmp_path / ".scratch/_trash/2026-07-01/010203"
    quarantined = write_file(
        tmp_path,
        ".scratch/_trash/2026-07-01/010203/.scratch/data/value.out",
        age_days=8,
        text="quarantined",
    )
    live = write_file(tmp_path, ".scratch/data/value.out", age_days=0, text="live")

    report = cleanup.run_restore(tmp_path, run_dir, apply=True, now=NOW)

    assert live.read_text(encoding="utf-8") == "live"
    assert quarantined.read_text(encoding="utf-8") == "quarantined"
    assert outcome(report, ".scratch/data/value.out") == "skipped-occupied"
    assert report.telemetry.blocked.count == 1


def test_run_lock_contention_fails_closed(tmp_path: Path):
    lock = tmp_path / ".scratch/_trash/.janitor.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("pid=4242 at=2026-07-16T12:00:00+00:00\n", encoding="utf-8")

    with pytest.raises(cleanup.JanitorLockError, match="already running"):
        cleanup.run_sweep(tmp_path, now=NOW)

    assert lock.exists()


def test_run_lock_is_released_after_engine_exception(tmp_path: Path):
    def fail_inside_lock():
        raise RuntimeError("injected engine failure")

    with pytest.raises(RuntimeError, match="injected engine failure"):
        cleanup.run_sweep(tmp_path, now=NOW, operation_hook=fail_inside_lock)

    assert not (tmp_path / ".scratch/_trash/.janitor.lock").exists()


def test_stale_lock_diagnostic_requires_manual_recovery_and_never_takes_over(tmp_path: Path):
    lock = tmp_path / ".scratch/_trash/.janitor.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("pid=999999 at=2026-01-01T00:00:00+00:00\n", encoding="utf-8")

    with pytest.raises(cleanup.JanitorLockError) as caught:
        cleanup.run_purge(tmp_path, apply=True, now=NOW)

    message = str(caught.value)
    assert "pid=999999" in message
    assert "No automatic takeover" in message
    assert "remove the lock file" in message
    assert lock.exists()


def test_failed_locked_file_rename_is_skipped_and_reported(tmp_path: Path, monkeypatch):
    source = write_file(tmp_path, ".scratch/locked.out", age_days=8)
    real_rename = cleanup.os.rename

    def locked_rename(old, new):
        if Path(old) == source:
            raise PermissionError("injected sharing violation")
        return real_rename(old, new)

    monkeypatch.setattr(cleanup.os, "rename", locked_rename)

    report = cleanup.run_sweep(tmp_path, apply=True, now=NOW)

    assert source.exists()
    assert outcome(report, ".scratch/locked.out") == "skipped-rename-failed"
    assert any("sharing violation" in message for message in report.messages)


def test_purge_uses_date_component_not_mtime(tmp_path: Path):
    old_run = tmp_path / ".scratch/_trash/2026-07-08/010101"
    recent_run = tmp_path / ".scratch/_trash/2026-07-15/020202"
    old_file = write_file(
        tmp_path,
        ".scratch/_trash/2026-07-08/010101/.scratch/old.out",
        age_days=0,
    )
    recent_file = write_file(
        tmp_path,
        ".scratch/_trash/2026-07-15/020202/.scratch/recent.out",
        age_days=100,
    )
    assert old_file.exists() and recent_file.exists()

    report = cleanup.run_purge(tmp_path, apply=True, now=NOW)

    assert not old_run.exists()
    assert recent_run.exists()
    assert any(action.outcome == "purged" for action in report.actions)
    assert any(action.outcome == "retained" for action in report.actions)


def test_purge_skips_and_reports_non_dated_directory(tmp_path: Path):
    non_dated = tmp_path / ".scratch/_trash/manual-notes"
    write_file(tmp_path, ".scratch/_trash/manual-notes/keep.txt", age_days=100)

    report = cleanup.run_purge(tmp_path, apply=True, now=NOW)

    assert non_dated.exists()
    assert outcome(report, ".scratch/_trash/manual-notes") == "skipped-non-dated"
    assert any("non-dated" in message for message in report.messages)


def test_purge_is_dry_run_by_default(tmp_path: Path):
    run_dir = tmp_path / ".scratch/_trash/2026-07-01/010101"
    write_file(tmp_path, ".scratch/_trash/2026-07-01/010101/.scratch/old.out", age_days=0)

    report = cleanup.run_purge(tmp_path, now=NOW)

    assert run_dir.exists()
    assert any(action.outcome == "would-purge" for action in report.actions)


@pytest.mark.parametrize(
    "reference",
    [
        ".scratch/results/task6-confirm-alpha.out",
        r".scratch\results\task6-confirm-alpha.out",
        "task6-confirm-*.out",
        "task6-confirm-{alpha,beta}.out",
    ],
    ids=["exact", "backslash", "glob", "brace"],
)
def test_reference_grammar_pins_exact_backslash_glob_and_brace(
    tmp_path: Path, reference: str
):
    artifact = write_file(
        tmp_path,
        ".scratch/results/task6-confirm-alpha.out",
        age_days=8,
    )
    write_active_reference(tmp_path, f"evidence: {reference}\n")

    result = cleanup.evaluate_eligibility(tmp_path, artifact, now=NOW)

    assert result.eligible is False
    assert result.reason == "live reference"
    assert result.report.telemetry.pinned.count == 1
    assert result.report.telemetry.pinned_set_size == 1


def test_live_report_bare_readme_basename_does_not_pin_scratch_copy(tmp_path: Path):
    artifact = write_file(
        tmp_path,
        ".scratch/extract-x/README.md",
        age_days=8,
    )
    write_file(
        tmp_path,
        ".reports/2026-07/live-report.md",
        age_days=0,
        text="README.md\n",
    )

    result = cleanup.evaluate_eligibility(tmp_path, artifact, now=NOW)

    assert result.eligible is True
    assert result.report.telemetry.pinned.count == 0


def test_live_report_prose_word_head_does_not_pin_matching_basename(tmp_path: Path):
    artifact = write_file(tmp_path, ".scratch/x/HEAD", age_days=8)
    write_file(
        tmp_path,
        ".reports/2026-07/live-report.md",
        age_days=0,
        text="HEAD\n",
    )

    result = cleanup.evaluate_eligibility(tmp_path, artifact, now=NOW)

    assert result.eligible is True
    assert result.report.telemetry.pinned.count == 0


def test_live_report_full_path_still_pins_scratch_copy(tmp_path: Path):
    artifact = write_file(
        tmp_path,
        ".scratch/extract-x/README.md",
        age_days=8,
    )
    write_file(
        tmp_path,
        ".reports/2026-07/live-report.md",
        age_days=0,
        text=".scratch/extract-x/README.md\n",
    )

    result = cleanup.evaluate_eligibility(tmp_path, artifact, now=NOW)

    assert result.eligible is False
    assert result.reason == "live reference"


def test_bare_timestamped_stem_still_pins_prompt_sibling_triple(tmp_path: Path):
    stem = "cleanup-v3-20260716-123456"
    paths = [
        write_file(
            tmp_path,
            f".scratch/codex-prompts/{stem}{suffix}",
            age_days=8,
        )
        for suffix in (".md", ".out", ".err")
    ]
    write_active_reference(tmp_path, f"evidence: {stem}\n")

    results = [cleanup.evaluate_eligibility(tmp_path, path, now=NOW) for path in paths]

    assert [result.eligible for result in results] == [False, False, False]
    assert all(result.reason == "live reference" for result in results)


def test_task6_output_glob_still_pins(tmp_path: Path):
    artifact = write_file(
        tmp_path,
        ".scratch/results/task6-confirm-alpha.out",
        age_days=8,
    )
    write_active_reference(tmp_path, "task6-confirm-*.out\n")

    result = cleanup.evaluate_eligibility(tmp_path, artifact, now=NOW)

    assert result.eligible is False
    assert result.reason == "live reference"


def test_markdown_emphasis_does_not_pin_an_uncited_artifact(tmp_path: Path):
    artifact = write_file(
        tmp_path,
        ".scratch/arch-delta/bold-italic-artifact.md",
        age_days=8,
    )
    write_active_reference(tmp_path, "This has **bold** and *italic* emphasis only.\n")

    result = cleanup.evaluate_eligibility(tmp_path, artifact, now=NOW)

    assert result.eligible is True
    assert result.report.telemetry.pinned.count == 0


@pytest.mark.parametrize(
    ("reference", "relative", "expected_eligible"),
    [
        (".scratch/*", ".scratch/a/b.md", True),
        (".scratch/*", ".scratch/b.md", False),
        (".scratch/**", ".scratch/a/b.md", False),
    ],
    ids=[
        "star-stops-at-separator",
        "star-matches-one-level",
        "double-star-crosses-separator",
    ],
)
def test_glob_matching_is_separator_aware(
    tmp_path: Path,
    reference: str,
    relative: str,
    expected_eligible: bool,
):
    artifact = write_file(tmp_path, relative, age_days=8)
    write_active_reference(tmp_path, f"evidence: {reference}\n")

    result = cleanup.evaluate_eligibility(tmp_path, artifact, now=NOW)

    assert result.eligible is expected_eligible


@pytest.mark.parametrize("reference", ["?", "*", "**"])
def test_bare_wildcard_token_pins_nothing(tmp_path: Path, reference: str):
    artifact = write_file(tmp_path, ".scratch/x", age_days=8)
    write_active_reference(tmp_path, f"{reference}\n")

    result = cleanup.evaluate_eligibility(tmp_path, artifact, now=NOW)

    assert result.eligible is True
    assert result.report.telemetry.pinned.count == 0


def test_glob_without_a_literal_segment_pins_nothing(tmp_path: Path):
    artifact = write_file(tmp_path, ".scratch/x", age_days=8)
    write_active_reference(tmp_path, "*/*\n")

    result = cleanup.evaluate_eligibility(tmp_path, artifact, now=NOW)

    assert result.eligible is True
    assert result.report.telemetry.pinned.count == 0


def test_sibling_triple_reference_pins_md_out_and_err_as_one_set(tmp_path: Path):
    paths = [
        write_file(
            tmp_path,
            f".scratch/codex-prompts/task6-confirm-xyz{suffix}",
            age_days=8,
        )
        for suffix in (".md", ".out", ".err")
    ]
    write_active_reference(
        tmp_path,
        "prompt `.scratch/codex-prompts/task6-confirm-xyz.md` with sibling `.out`/`.err`\n",
    )

    results = [cleanup.evaluate_eligibility(tmp_path, path, now=NOW) for path in paths]

    assert [result.eligible for result in results] == [False, False, False]
    assert all(result.reason == "live reference" for result in results)


def test_directory_is_not_eligible_when_a_descendant_is_pinned(tmp_path: Path):
    directory = tmp_path / ".scratch/tree"
    write_file(tmp_path, ".scratch/tree/free.out", age_days=8)
    write_file(tmp_path, ".scratch/tree/pinned.out", age_days=8)
    write_active_reference(tmp_path, ".scratch/tree/pinned.out\n")

    result = cleanup.evaluate_eligibility(tmp_path, directory, now=NOW)

    assert result.eligible is False
    assert result.report.telemetry.eligible.count == 1
    assert result.report.telemetry.pinned.count == 1


def test_unreadable_reference_file_fails_closed_for_every_artifact(tmp_path: Path, monkeypatch):
    artifact = write_file(tmp_path, ".scratch/free.out", age_days=8)
    unreadable = write_active_reference(tmp_path, "unrelated text\n", name="unreadable.md")
    real_read_text = Path.read_text

    def injected_read_text(self, *args, **kwargs):
        if self == unreadable:
            raise PermissionError("injected unreadable reference")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", injected_read_text)

    report = cleanup.run_sweep(tmp_path, now=NOW)

    assert artifact.exists()
    assert report.telemetry.eligible.count == 0
    assert report.telemetry.blocked.count == 1
    assert report.errors and "injected unreadable reference" in report.errors[0]


def test_archived_work_item_citation_is_not_live(tmp_path: Path):
    artifact = write_file(tmp_path, ".scratch/archive-only.out", age_days=8)
    write_file(
        tmp_path,
        "work-items/archive/2026-07/old-item/status.md",
        age_days=0,
        text=".scratch/archive-only.out\n",
    )

    result = cleanup.evaluate_eligibility(tmp_path, artifact, now=NOW)

    assert result.eligible is True


def test_report_citation_expires_at_reference_liveness_ceiling(tmp_path: Path):
    artifact = write_file(tmp_path, ".scratch/report-only.out", age_days=8)
    write_file(
        tmp_path,
        ".reports/2026-04/old-report.md",
        age_days=90,
        text=".scratch/report-only.out\n",
    )

    result = cleanup.evaluate_eligibility(tmp_path, artifact, now=NOW)

    assert result.eligible is True


def test_artifact_over_90_days_is_eligible_despite_live_reference(tmp_path: Path):
    artifact = write_file(tmp_path, ".scratch/hard-ceiling.out", age_days=91)
    write_active_reference(tmp_path, ".scratch/hard-ceiling.out\n")

    result = cleanup.evaluate_eligibility(tmp_path, artifact, now=NOW)

    assert result.eligible is True
    assert "hard ceiling" in result.reason
    assert result.report.telemetry.pinned_set_size == 1


def test_work_item_staleness_report_uses_newest_file_mtime(tmp_path: Path):
    write_file(tmp_path, ".scratch/young.out", age_days=1)
    write_file(tmp_path, "work-items/active/stale/status.md", age_days=20)
    write_file(tmp_path, "work-items/active/recent/status.md", age_days=20)
    write_file(tmp_path, "work-items/active/recent/notes.md", age_days=2)

    report = cleanup.build_sweep_plan(tmp_path, now=NOW)

    assert report.stale_work_items == [Path("work-items/active/stale")]


def test_telemetry_reports_counts_volumes_pinned_set_and_age_histogram(tmp_path: Path):
    write_file(tmp_path, ".scratch/eligible.out", age_days=8, text="1234")
    write_file(tmp_path, ".scratch/pinned.out", age_days=8, text="12345")
    write_file(tmp_path, ".scratch/young.out", age_days=1, text="123456")
    write_active_reference(tmp_path, ".scratch/pinned.out\n")

    report = cleanup.build_sweep_plan(tmp_path, now=NOW)

    assert (report.telemetry.eligible.count, report.telemetry.eligible.bytes) == (1, 4)
    assert (report.telemetry.pinned.count, report.telemetry.pinned.bytes) == (1, 5)
    assert (report.telemetry.blocked.count, report.telemetry.blocked.bytes) == (1, 6)
    assert report.telemetry.pinned_set_size == 1
    assert report.telemetry.age_histogram[">7-14d"].count == 2
    assert report.telemetry.age_histogram["0-7d"].count == 1


def test_symlink_is_pruned_from_sweep_when_supported(tmp_path: Path):
    outside = write_file(tmp_path, "outside.out", age_days=100)
    link = tmp_path / ".scratch/link.out"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable on this host")

    report = cleanup.run_sweep(tmp_path, apply=True, now=NOW)

    assert link.exists()
    assert outside.exists()
    assert report.telemetry.eligible.count == 0
    assert any("pruned link/reparse point" in message for message in report.messages)


def test_quarantine_subtree_is_pruned_without_enumerating_it(tmp_path: Path, monkeypatch):
    write_file(tmp_path, ".scratch/live-scope.out", age_days=8)
    trash = tmp_path / ".scratch/_trash"
    trash.mkdir(parents=True)
    real_scandir = cleanup.os.scandir

    def guarded_scandir(path):
        if Path(path) == trash:
            raise AssertionError("sweep entered excluded quarantine subtree")
        return real_scandir(path)

    monkeypatch.setattr(cleanup.os, "scandir", guarded_scandir)

    report = cleanup.run_sweep(tmp_path, now=NOW)

    assert report.telemetry.eligible.count == 1


def test_eligible_json_cli_uses_exit_0_1_and_2_with_error_schema(
    tmp_path: Path, monkeypatch, capsys
):
    monkeypatch.setattr(cleanup, "_utc_now", lambda: NOW)
    old = write_file(tmp_path, ".scratch/old.out", age_days=8)
    young = write_file(tmp_path, ".scratch/young.out", age_days=1)

    eligible_code = cleanup.main(
        ["eligible", "--path", str(old), "--json", "--root", str(tmp_path)]
    )
    eligible_output = json.loads(capsys.readouterr().out)
    assert eligible_code == 0
    assert eligible_output["eligible"] is True
    assert set(eligible_output["telemetry"]) == {
        "eligible",
        "pinned",
        "blocked",
        "pinnedSetSize",
        "ageHistogram",
    }

    ineligible_code = cleanup.main(
        ["eligible", "--path", str(young), "--json", "--root", str(tmp_path)]
    )
    ineligible_output = json.loads(capsys.readouterr().out)
    assert ineligible_code == 1
    assert ineligible_output["eligible"] is False

    error_code = cleanup.main(
        ["eligible", "--path", ".scratch/missing.out", "--json", "--root", str(tmp_path)]
    )
    captured = capsys.readouterr()
    error_output = json.loads(captured.err)
    assert error_code == 2
    assert captured.out == ""
    assert error_output["ok"] is False
    assert error_output["error"]["code"] == "cleanup_error"
