import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check-work-items-state.py"


def run_checker(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(root), *args],
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
            "",
            "## Active agents",
            "- none",
            "",
            "## Completed agents",
            "- none",
            "",
            "## Next action",
            "Continue.",
            "",
        ]
    )


def ledger_event(**updates):
    event = {
        "schemaVersion": 1,
        "runId": "run-check-001",
        "workItem": "active-item",
        "role": "qa-engineer",
        "executionRole": "internal",
        "status": "completed",
        "gate": "PASS",
        "scope": ["tests/test_work_items_state_checker.py"],
        "artifact": "reviews/qa.md",
        "evidence": [{"kind": "command", "ref": "pytest -q"}],
        "startedAt": "2026-05-03T10:00:00Z",
        "updatedAt": "2026-05-03T10:05:00Z",
    }
    event.update(updates)
    return event


def write_valid_item(root: Path, name: str = "active-item", event: dict | None = None) -> Path:
    item = root / "work-items" / "active" / name
    (item / "reviews").mkdir(parents=True)
    (item / "status.md").write_text(valid_status(), encoding="utf-8")
    (item / "reviews" / "qa.md").write_text("PASS\n", encoding="utf-8")
    (item / "agent-runs.jsonl").write_text(json.dumps(event or ledger_event(workItem=name)) + "\n", encoding="utf-8")
    return item


def test_checker_passes_when_no_active_directory_exists(tmp_path: Path):
    result = run_checker(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "no active work-items" in result.stdout


def test_checker_validates_all_active_items(tmp_path: Path):
    write_valid_item(tmp_path, "valid-item")
    bad = tmp_path / "work-items" / "active" / "bad-item"
    bad.mkdir(parents=True)
    (bad / "status.md").write_text(valid_status(), encoding="utf-8")

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert "PASS valid-item" in result.stdout
    assert "FAIL bad-item" in result.stdout
    assert "missing ledger" in result.stdout


def status_with_depends(dep_value: str) -> str:
    return valid_status().replace(
        "**Primary task status**: open",
        "**Primary task status**: open\n**Depends-on**: " + dep_value,
    )


def write_item_with_status(root: Path, name: str, status_text: str) -> Path:
    item = root / "work-items" / "active" / name
    (item / "reviews").mkdir(parents=True)
    (item / "status.md").write_text(status_text, encoding="utf-8")
    (item / "reviews" / "qa.md").write_text("PASS\n", encoding="utf-8")
    (item / "agent-runs.jsonl").write_text(json.dumps(ledger_event(workItem=name)) + "\n", encoding="utf-8")
    return item


# --- aging report (B2): informational, never a failure ----------------------

def test_aging_flags_old_item_as_info(tmp_path: Path):
    write_valid_item(tmp_path, "2026-01-01-old-item")
    result = run_checker(tmp_path, "--max-age-days", "30", "--now", "2026-06-13T00:00:00Z")
    assert result.returncode == 0, result.stdout  # aging is info, not a failure
    assert "PASS 2026-01-01-old-item" in result.stdout
    assert "info: aging" in result.stdout


def test_aging_not_flagged_for_recent_item(tmp_path: Path):
    write_valid_item(tmp_path, "2026-06-10-recent-item")
    result = run_checker(tmp_path, "--max-age-days", "30", "--now", "2026-06-13T00:00:00Z")
    assert result.returncode == 0
    assert "aging" not in result.stdout


def test_aging_disabled_by_default(tmp_path: Path):
    write_valid_item(tmp_path, "2026-01-01-old-item")
    result = run_checker(tmp_path)  # no --max-age-days -> default 0 -> disabled
    assert result.returncode == 0
    assert "aging" not in result.stdout


# --- blocker-state (B2): informational, never a failure ---------------------

def test_blocked_by_open_target_is_info_not_failure(tmp_path: Path):
    write_valid_item(tmp_path, "dep-target")  # exists, valid, not done
    write_item_with_status(tmp_path, "blocked-item", status_with_depends("dep-target"))
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout  # blocked is expected state, not a failure
    assert "info: blocked-by: dep-target" in result.stdout


def test_dangling_depends_on_reported(tmp_path: Path):
    write_item_with_status(tmp_path, "item-x", status_with_depends("ghost-item"))
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "dangling Depends-on: ghost-item" in result.stdout


def test_blocked_by_done_target_not_reported(tmp_path: Path):
    arch = tmp_path / "work-items" / "archive" / "2026-05" / "done-dep"
    arch.mkdir(parents=True)
    (arch / "status.md").write_text("State: closed\n", encoding="utf-8")
    write_item_with_status(tmp_path, "item-y", status_with_depends("done-dep"))
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "blocked-by" not in result.stdout


def test_depends_on_none_no_note(tmp_path: Path):
    write_item_with_status(tmp_path, "item-z", status_with_depends("none"))
    result = run_checker(tmp_path)
    assert result.returncode == 0
    assert "blocked-by" not in result.stdout
    assert "dangling" not in result.stdout


def test_checker_reports_stale_running_agent_when_threshold_is_enabled(tmp_path: Path):
    write_valid_item(
        tmp_path,
        "stale-item",
        ledger_event(
            runId="run-stale-001",
            workItem="stale-item",
            status="running",
            gate="none",
            artifact="",
            evidence=[],
            updatedAt="2026-05-03T08:00:00Z",
        ),
    )

    result = run_checker(tmp_path, "--stale-hours", "1", "--now", "2026-05-03T10:30:00Z")

    assert result.returncode == 1
    assert "stale running agent" in result.stdout


def test_done_predicate_twin_not_drifted():
    # The state-checker re-implements the archival hook's DONE_STATE regex (no
    # shared import across the hook/script boundary). Guard against silent drift:
    # the distinctive pattern line must appear verbatim in BOTH files.
    line = r'r"\s*\*{0,3}\s*:\s*\*{0,3}\s*(?:closed|done|complete|completed|archived)(?![\w-])"'
    hook = (ROOT / "src.claude" / "agents" / "scripts" / "check-work-items-archival-stop.py").read_text(encoding="utf-8")
    checker = CHECKER.read_text(encoding="utf-8")
    assert line in hook, "hook DONE_STATE pattern changed — update the twin in check-work-items-state.py"
    assert line in checker, "check-work-items-state.py DONE_STATE pattern drifted from the hook"
