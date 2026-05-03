import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "scripts" / "agent-run-ledger.py"
VALIDATOR = ROOT / "scripts" / "validate-work-item-state.py"


def run_ledger(work_item: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(LEDGER), "--work-item", str(work_item), *args],
        text=True,
        capture_output=True,
    )


def run_validator(work_item: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), "--work-item", str(work_item)],
        text=True,
        capture_output=True,
    )


def valid_status() -> str:
    return "\n".join(
        [
            "# Status",
            "",
            "## Current state",
            "**Primary task status**: open",
            "Track agent execution automation.",
            "",
            "## Active agents",
            "- none",
            "",
            "## Completed agents",
            "- none",
            "",
            "## Next action",
            "Continue from ledger helper validation.",
            "",
        ]
    )


def prepare_valid_work_item(tmp_path: Path) -> Path:
    item = tmp_path / "work-items" / "active" / "ledger-helper"
    (item / "reviews").mkdir(parents=True)
    (item / "status.md").write_text(valid_status(), encoding="utf-8")
    (item / "reviews" / "qa.md").write_text("PASS\n", encoding="utf-8")
    return item


def test_append_records_event_and_validator_passes(tmp_path: Path):
    item = prepare_valid_work_item(tmp_path)

    result = run_ledger(
        item,
        "append",
        "--run-id",
        "run-append-001",
        "--role",
        "qa-engineer",
        "--execution-role",
        "internal",
        "--status",
        "completed",
        "--gate",
        "PASS",
        "--scope",
        "scripts/agent-run-ledger.py",
        "--artifact",
        "reviews/qa.md",
        "--evidence",
        "command:pytest tests/test_agent_run_ledger.py -q",
        "--started-at",
        "2026-05-03T10:00:00Z",
        "--updated-at",
        "2026-05-03T10:05:00Z",
    )

    assert result.returncode == 0, result.stderr
    validator = run_validator(item)
    assert validator.returncode == 0, validator.stderr
    lines = (item / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["runId"] == "run-append-001"
    assert event["evidence"][0]["kind"] == "command"


def test_append_rolls_back_invalid_pass_without_evidence(tmp_path: Path):
    item = prepare_valid_work_item(tmp_path)

    result = run_ledger(
        item,
        "append",
        "--run-id",
        "run-invalid-001",
        "--role",
        "qa-engineer",
        "--execution-role",
        "internal",
        "--status",
        "completed",
        "--gate",
        "PASS",
        "--scope",
        "scripts/agent-run-ledger.py",
        "--artifact",
        "reviews/qa.md",
        "--started-at",
        "2026-05-03T10:00:00Z",
        "--updated-at",
        "2026-05-03T10:05:00Z",
    )

    assert result.returncode == 1
    assert "PASS gate requires evidence" in result.stderr
    assert not (item / "agent-runs.jsonl").exists()


def test_init_adds_missing_status_sections_without_clobbering_existing_text(tmp_path: Path):
    item = tmp_path / "work-items" / "active" / "legacy-item"
    item.mkdir(parents=True)
    original = "# Legacy status\n\nKeep this operator note.\n"
    (item / "status.md").write_text(original, encoding="utf-8")

    result = run_ledger(
        item,
        "init",
        "--primary-task",
        "Migrate legacy work item.",
        "--stage",
        "Recovery",
    )

    assert result.returncode == 0, result.stderr
    text = (item / "status.md").read_text(encoding="utf-8")
    assert original.strip() in text
    for heading in (
        "## Current state",
        "## Active agents",
        "## Completed agents",
        "## Next action",
    ):
        assert heading in text
    assert (item / "agent-runs.jsonl").exists()
