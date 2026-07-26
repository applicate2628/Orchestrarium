import json
import os
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


def test_pass_surfaces_active_items_and_denies_completion(tmp_path: Path):
    """Forcing function (bug 2026-07-18-false-completion-claim-validator-pass-conflated-with-done):
    a green RESULT must never read as 'all closed'. The checker prints every active item + its
    Next action, and the RESULT line itself says valid-state-not-completion — so a PASS cannot be
    quoted as completion while active work remains."""
    write_valid_item(tmp_path, "active-item")
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "STILL OPEN" in result.stdout
    assert "active-item -- Next action: Continue." in result.stdout
    assert "NOT completion" in result.stdout
    # and the empty case must not claim completion falsely either — it says 'no active work-items'
    empty = run_checker(tmp_path / "does-not-exist")
    assert "no active work-items" in empty.stdout
    assert "STILL OPEN" not in empty.stdout  # no items => no STILL OPEN block


def test_forcing_function_survives_non_ascii_next_action_on_narrow_console(tmp_path: Path):
    """The enumeration prints ARBITRARY status content; a non-ASCII Next action (em-dash,
    arrow) must NOT crash the report on a non-UTF-8 console. The stream-level errors=replace
    guard in main() owns this — replacing the em-dash in one string literal would not
    (fable + codex ff-review: the crash class lives in the interpolated data)."""
    item = write_valid_item(tmp_path, "unicode-item")
    (item / "status.md").write_text(
        valid_status().replace("Continue.", "Run probe 1 — then reconcile → close."),
        encoding="utf-8",
    )
    env = {**os.environ, "PYTHONIOENCODING": "cp866"}
    result = subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(tmp_path)],
        text=True, capture_output=True, encoding="cp866", errors="replace", env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr  # no UnicodeEncodeError
    assert "unicode-item" in result.stdout
    assert "STILL OPEN" in result.stdout


def test_next_actionable_heading_does_not_false_match(tmp_path: Path):
    """Exact heading match: a '## Next actionable' section must NOT be read as the
    '## Next action' section (codex ff-review — the old startswith accepted it)."""
    item = write_valid_item(tmp_path, "actionable-item")
    (item / "status.md").write_text(
        "# Status\n\n## Current state\n**Primary task status**: open\n\n"
        "## Active agents\n- none\n\n## Completed agents\n- none\n\n"
        "## Next actionable\nWRONG heading content\n\n"
        "## Next action\nCORRECT action content\n",
        encoding="utf-8",
    )
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "CORRECT action content" in result.stdout
    assert "WRONG heading content" not in result.stdout


def status_with_depends(dep_value: str) -> str:
    return valid_status().replace(
        "**Primary task status**: open",
        "**Primary task status**: open\n**Depends-on**: " + dep_value,
    )


def status_with_epic(epic_value: str) -> str:
    return valid_status().replace(
        "**Primary task status**: open",
        "**Primary task status**: open\n**Epic**: " + epic_value,
    )


def status_with_no_epic_rationale() -> str:
    return valid_status().replace(
        "**Primary task status**: open",
        "**Primary task status**: open\n**No-epic rationale**: standalone fixes",
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


# --- epic visibility: informational, never a failure ------------------------

def test_dangling_epic_reported(tmp_path: Path):
    write_item_with_status(tmp_path, "item-epic", status_with_epic("2026-06-18-missing-epic"))
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "dangling Epic: 2026-06-18-missing-epic" in result.stdout


def test_existing_epic_not_reported(tmp_path: Path):
    epics = tmp_path / "work-items" / "epics"
    epics.mkdir(parents=True)
    (epics / "2026-06-18-demo.md").write_text("---\nstatus: active\n---\n", encoding="utf-8")
    write_item_with_status(tmp_path, "item-epic", status_with_epic("2026-06-18-demo"))
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "dangling Epic" not in result.stdout


def test_multiple_active_items_without_epics_surface_adoption_prompt(tmp_path: Path):
    write_valid_item(tmp_path, "item-a")
    write_valid_item(tmp_path, "item-b")
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "no work-items/epics/ directory for multiple active items" in result.stdout


def test_no_epic_rationale_suppresses_adoption_prompt(tmp_path: Path):
    write_item_with_status(tmp_path, "item-a", status_with_no_epic_rationale())
    write_valid_item(tmp_path, "item-b")
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "no work-items/epics/ directory" not in result.stdout


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


def test_archive_scan_propagates_security_reviewer_waiver_validity(tmp_path: Path, subtests):
    def archived_case(case_name: str, *, invalid: bool = False, legacy_waiver: bool = False):
        root = tmp_path / case_name
        item_name = f"archived-{case_name}"
        item = root / "work-items" / "archive" / "2026-07" / item_name
        (item / "reviews").mkdir(parents=True)
        (item / "reviews" / "security.md").write_text("PASS\n", encoding="utf-8")
        target_id = f"run-archive-{case_name}-target"
        waiver_id = f"run-archive-{case_name}-waiver"
        target = ledger_event(
            schemaVersion=2,
            runId=target_id,
            workItem=item_name,
            role="security-reviewer",
            executionRole="external-reviewer",
            status="revise",
            gate="REVISE",
            artifact="reviews/security.md",
            lane=f"archive-{case_name}",
            findingClass="security",
        )
        waiver = ledger_event(
            schemaVersion=1 if legacy_waiver else 2,
            runId=waiver_id,
            workItem=item_name,
            role="security-reviewer",
            executionRole="internal",
            status="completed",
            gate="WAIVED:security-reviewer",
            scope=[] if invalid else ["archive security review"],
            artifact="reviews/security.md",
            evidence=[{
                "kind": "manual-check",
                "ref": f"security-reviewer waives {target_id}",
            }],
            closesRunIds=[target_id],
        )
        (item / "agent-runs.jsonl").write_text(
            "\n".join(json.dumps(event) for event in (target, waiver)) + "\n",
            encoding="utf-8",
        )
        return run_checker(root), target_id, waiver_id

    with subtests.test(case="legal version-2 waiver"):
        result, target_id, _waiver_id = archived_case("legal")

        assert result.returncode == 0, result.stdout
        assert f"open REVISE obligation survived archival: {target_id}" not in result.stdout
        assert "archive scan clean" in result.stdout

    with subtests.test(case="invalid version-2 waiver"):
        result, target_id, waiver_id = archived_case("invalid", invalid=True)

        assert result.returncode == 1
        assert f"{waiver_id}: scope must be a non-empty list" in result.stdout
        assert f"open REVISE obligation survived archival: {target_id}" in result.stdout

    with subtests.test(case="legacy version-1 waiver"):
        result, target_id, waiver_id = archived_case("legacy", legacy_waiver=True)

        assert result.returncode == 1
        assert f"open REVISE obligation survived archival: {target_id}" in result.stdout
        assert f"{waiver_id}: field closesRunIds requires schemaVersion 2" not in result.stdout


def test_done_predicate_twin_not_drifted():
    # The state-checker re-implements the SEN-0 archival-orphan invariant's
    # DONE_STATE regex (no shared import across the sentinel/validator
    # boundary — workitem_sentinels.py must never be imported BY the
    # validator's twin logic, only the reverse; design.md §3.2). Guard against
    # silent drift: the distinctive pattern line must appear verbatim in BOTH
    # files. As of the sentinel-registry migration
    # (2026-07-25-review-round-cap-enforcement), the regex's owning file is
    # `workitem_sentinels.py`, not `check-work-items-archival-stop.py` (now a
    # thin adapter that imports it) — the twin-check follows the regex to its
    # new home rather than the file that used to hold it.
    line = r'r"\s*\*{0,3}\s*:\s*\*{0,3}\s*(?:closed|done|complete|completed|archived)(?![\w-])"'
    sentinels = (ROOT / "src.claude" / "agents" / "scripts" / "workitem_sentinels.py").read_text(encoding="utf-8")
    checker = CHECKER.read_text(encoding="utf-8")
    assert line in sentinels, "workitem_sentinels.py DONE_STATE pattern changed — update the twin in check-work-items-state.py"
    assert line in checker, "check-work-items-state.py DONE_STATE pattern drifted from workitem_sentinels.py"
