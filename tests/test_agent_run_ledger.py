import json
import shutil
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


def minimal_quick_fix_status() -> str:
    return """---
template: quick-fix
status: active
started: 2026-07-30 10:00
updated: 2026-07-30 10:00
---

- **Task**: Correct quick-fix recovery.
- **Current step**: Initialize the execution ledger.
- **Last result**: Quick-fix admitted.
- **Next action**: Run the implementation lane.
"""


def prepare_valid_work_item(tmp_path: Path) -> Path:
    item = tmp_path / "work-items" / "active" / "ledger-helper"
    (item / "reviews").mkdir(parents=True)
    (item / "status.md").write_text(valid_status(), encoding="utf-8")
    (item / "reviews" / "qa.md").write_text("PASS\n", encoding="utf-8")
    return item


def append_unclassified_revise(item: Path) -> subprocess.CompletedProcess:
    return run_ledger(
        item,
        "append",
        "--run-id",
        "run-security-revise-001",
        "--role",
        "security-reviewer",
        "--execution-role",
        "internal",
        "--status",
        "revise",
        "--gate",
        "REVISE",
        "--scope",
        "scripts/validate-work-item-state.py",
        "--artifact",
        "reviews/qa.md",
        "--event-kind",
        "standalone",
        "--started-at",
        "2026-07-18T10:00:00Z",
        "--updated-at",
        "2026-07-18T10:05:00Z",
    )


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


def test_append_accepts_security_reviewer_waiver_and_discharges_revise(tmp_path: Path):
    item = prepare_valid_work_item(tmp_path)
    revise = append_unclassified_revise(item)
    assert revise.returncode == 0, revise.stderr

    waiver = run_ledger(
        item,
        "append",
        "--run-id",
        "run-security-waiver-001",
        "--role",
        "security-reviewer",
        "--execution-role",
        "internal",
        "--status",
        "completed",
        "--gate",
        "WAIVED:security-reviewer",
        "--scope",
        "scripts/validate-work-item-state.py",
        "--artifact",
        "reviews/qa.md",
        "--closes",
        "run-security-revise-001",
        "--evidence",
        "manual-check:security-reviewer waives run-security-revise-001",
        "--started-at",
        "2026-07-18T10:10:00Z",
        "--updated-at",
        "2026-07-18T10:15:00Z",
    )

    assert waiver.returncode == 0, waiver.stderr
    validator = run_validator(item)
    assert validator.returncode == 0, validator.stdout + validator.stderr
    events = [
        json.loads(line)
        for line in (item / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["gate"] for event in events] == ["REVISE", "WAIVED:security-reviewer"]


def test_malformed_security_reviewer_waiver_rolls_back_atomically(tmp_path: Path):
    item = prepare_valid_work_item(tmp_path)
    revise = append_unclassified_revise(item)
    assert revise.returncode == 0, revise.stderr
    ledger = item / "agent-runs.jsonl"
    original = ledger.read_bytes()
    base = (
        "append",
        "--role",
        "security-reviewer",
        "--execution-role",
        "internal",
        "--gate",
        "WAIVED:security-reviewer",
        "--scope",
        "scripts/validate-work-item-state.py",
        "--started-at",
        "2026-07-18T10:10:00Z",
        "--updated-at",
        "2026-07-18T10:15:00Z",
    )
    cases = (
        (
            "run-security-no-closes",
            ("--status", "completed", "--evidence", "manual-check:security-reviewer waiver"),
            "requires closesRunIds",
        ),
        (
            "run-security-no-manual",
            ("--status", "completed", "--closes", "run-security-revise-001"),
            "requires a manual-check evidence entry",
        ),
        (
            "run-security-wrong-status",
            (
                "--status",
                "cancelled",
                "--closes",
                "run-security-revise-001",
                "--evidence",
                "manual-check:security-reviewer waives run-security-revise-001",
            ),
            "requires completed status",
        ),
    )

    for run_id, extra, expected in cases:
        result = run_ledger(item, *base, "--run-id", run_id, *extra)

        assert result.returncode == 1, (run_id, result.stdout, result.stderr)
        assert expected in result.stderr, (run_id, result.stderr)
        assert ledger.read_bytes() == original, run_id
        assert not ledger.with_suffix(".jsonl.tmp").exists(), run_id
        assert not (item / "agent-runs.jsonl.lock").exists(), run_id


def run_rollup_root(root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(LEDGER), "rollup", "--root", str(root), *extra],
        text=True, capture_output=True,
    )


def append_valid(item: Path, run_id: str) -> subprocess.CompletedProcess:
    return run_ledger(
        item, "append",
        "--run-id", run_id,
        "--role", "qa-engineer", "--execution-role", "internal",
        "--status", "completed", "--gate", "PASS",
        "--scope", "scripts/agent-run-ledger.py", "--artifact", "reviews/qa.md",
        "--evidence", "command:pytest",
        "--started-at", "2026-05-03T10:00:00Z", "--updated-at", "2026-05-03T10:05:00Z",
    )


def make_second_item(tmp_path: Path, name: str) -> Path:
    item = tmp_path / "work-items" / "active" / name
    (item / "reviews").mkdir(parents=True)
    (item / "status.md").write_text(valid_status(), encoding="utf-8")
    (item / "reviews" / "qa.md").write_text("PASS\n", encoding="utf-8")
    return item


# --- B3: ledger rollup -------------------------------------------------------

def test_rollup_single_item_counts_events(tmp_path: Path):
    item = prepare_valid_work_item(tmp_path)
    assert append_valid(item, "rollup-001").returncode == 0
    assert append_valid(item, "rollup-002").returncode == 0
    result = run_ledger(item, "rollup")
    assert result.returncode == 0, result.stderr
    assert "total runs: 2" in result.stdout
    assert "PASS=2" in result.stdout
    assert "evidence coverage: 2/2" in result.stdout


def test_rollup_all_active_aggregates(tmp_path: Path):
    i1 = prepare_valid_work_item(tmp_path)
    assert append_valid(i1, "rollup-i1-01").returncode == 0
    i2 = make_second_item(tmp_path, "item-two")
    assert append_valid(i2, "rollup-i2-01").returncode == 0
    result = run_rollup_root(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "2 active items" in result.stdout
    assert "total runs: 2" in result.stdout
    assert "per-item runs:" in result.stdout


def test_rollup_json_shape(tmp_path: Path):
    item = prepare_valid_work_item(tmp_path)
    assert append_valid(item, "rollup-001").returncode == 0
    result = run_rollup_root(tmp_path, "--json")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["totalRuns"] == 1
    assert data["byGate"]["PASS"] == 1
    assert data["evidenceCoverage"] == {"withEvidence": 1, "total": 1}


def test_rollup_empty_ledger(tmp_path: Path):
    item = prepare_valid_work_item(tmp_path)
    (item / "agent-runs.jsonl").write_text("", encoding="utf-8")
    result = run_ledger(item, "rollup")
    assert result.returncode == 0, result.stderr
    assert "total runs: 0" in result.stdout


def test_rollup_surfaces_malformed_ledger_lines(tmp_path: Path):
    item = prepare_valid_work_item(tmp_path)
    assert append_valid(item, "rollup-001").returncode == 0
    with (item / "agent-runs.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("{ this is not valid json\n")
    result = run_ledger(item, "rollup")
    assert result.returncode == 0, result.stderr
    assert "malformed lines: 1" in result.stdout
    assert "total runs: 1" in result.stdout  # the one valid event is still counted


# --- F25: one main-conversation identity on the wire --------------------------

def test_append_rejects_legacy_execution_role_lead(tmp_path: Path):
    # NEW writes must use "main": the retired main|lead duality survives only as
    # the validator's READ-mapping for pre-existing ledgers, never on a new line.
    item = prepare_valid_work_item(tmp_path)
    result = run_ledger(
        item, "append",
        "--run-id", "legacy-write-001",
        "--role", "lead", "--execution-role", "lead",
        "--status", "completed", "--gate", "PASS",
        "--scope", "scripts/agent-run-ledger.py", "--artifact", "reviews/qa.md",
        "--evidence", "command:pytest",
        "--started-at", "2026-07-11T10:00:00Z", "--updated-at", "2026-07-11T10:05:00Z",
    )
    assert result.returncode == 1
    assert "retired legacy value" in result.stderr
    assert "'main'" in result.stderr
    assert not (item / "agent-runs.jsonl").exists()


def test_rollup_maps_legacy_lead_into_main_bucket(tmp_path: Path):
    # ONE owner rolls up into ONE audit bucket even when old ledger lines still
    # carry the legacy "lead" value (read-mapping lead -> main).
    item = prepare_valid_work_item(tmp_path)
    legacy = {
        "schemaVersion": 1, "runId": "legacy-lead-0001", "workItem": "ledger-helper",
        "role": "lead", "executionRole": "lead", "status": "completed", "gate": "none",
        "scope": ["status.md"], "startedAt": "2026-05-03T10:00:00Z", "updatedAt": "2026-05-03T10:05:00Z",
    }
    current = dict(legacy, runId="current-main-0001", executionRole="main")
    (item / "agent-runs.jsonl").write_text(
        json.dumps(legacy) + "\n" + json.dumps(current) + "\n", encoding="utf-8"
    )
    result = run_rollup_root(tmp_path, "--json")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["byExecutionRole"] == {"main": 2}


def test_init_requires_work_item_guard():
    result = subprocess.run([sys.executable, str(LEDGER), "init"], text=True, capture_output=True)
    assert result.returncode == 1
    assert "init requires --work-item" in result.stderr


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


def test_init_rejects_each_malformed_quick_fix_field_without_modifying_status(tmp_path: Path):
    required_lines = (
        "template: quick-fix",
        "status: active",
        "started: 2026-07-30 10:00",
        "updated: 2026-07-30 10:00",
        "- **Task**: Correct quick-fix recovery.",
        "- **Current step**: Initialize the execution ledger.",
        "- **Last result**: Quick-fix admitted.",
        "- **Next action**: Run the implementation lane.",
    )
    for index, required_line in enumerate(required_lines):
        item = tmp_path / "work-items" / "active" / f"malformed-quick-fix-{index}"
        item.mkdir(parents=True)
        status = minimal_quick_fix_status().replace(required_line + "\n", "", 1)
        (item / "status.md").write_text(status, encoding="utf-8")

        result = run_ledger(item, "init")

        assert result.returncode == 1, (required_line, result.stdout, result.stderr)
        assert "quick-fix status.md" in result.stderr
        assert (item / "status.md").read_text(encoding="utf-8") == status
        assert not (item / "agent-runs.jsonl").exists()


def test_init_rejects_wrong_quick_fix_template_without_modifying_status(tmp_path: Path):
    item = tmp_path / "work-items" / "active" / "wrong-quick-fix-template"
    item.mkdir(parents=True)
    status = minimal_quick_fix_status().replace(
        "template: quick-fix",
        "template: full-delivery",
        1,
    )
    (item / "status.md").write_text(status, encoding="utf-8")

    result = run_ledger(item, "init")

    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "lifecycle field template must be quick-fix" in result.stderr
    assert (item / "status.md").read_text(encoding="utf-8") == status
    assert not (item / "agent-runs.jsonl").exists()


def test_init_rejects_quick_fix_quartet_with_full_headings_and_bad_template_atomically(
    tmp_path: Path,
):
    cases = {
        "missing-template": minimal_quick_fix_status().replace(
            "template: quick-fix\n",
            "",
            1,
        ),
        "wrong-template": minimal_quick_fix_status().replace(
            "template: quick-fix",
            "template: full-delivery",
            1,
        ),
    }
    full_headings = "\n## Current state\n\n## Active agents\n\n## Completed agents\n\n## Next action\n"
    for name, status in cases.items():
        item = tmp_path / "work-items" / "active" / f"quick-fix-quartet-init-{name}"
        item.mkdir(parents=True)
        status += full_headings
        status_path = item / "status.md"
        status_path.write_text(status, encoding="utf-8")
        ledger = item / "agent-runs.jsonl"

        result = run_ledger(item, "init")

        assert result.returncode == 1, (name, result.stdout, result.stderr)
        assert "quick-fix status.md" in result.stderr, (name, result.stderr)
        assert status_path.read_text(encoding="utf-8") == status, name
        assert not ledger.exists(), name
        assert not ledger.with_suffix(".jsonl.tmp").exists(), name
        assert not (item / "agent-runs.jsonl.lock").exists(), name


def test_append_rejects_malformed_quick_fix_without_modifying_ledger(tmp_path: Path):
    item = tmp_path / "work-items" / "active" / "malformed-quick-fix-append"
    (item / "reviews").mkdir(parents=True)
    (item / "status.md").write_text(
        minimal_quick_fix_status() + "## Research\nUnexpected.\n",
        encoding="utf-8",
    )
    (item / "reviews" / "qa.md").write_text("PASS\n", encoding="utf-8")
    ledger = item / "agent-runs.jsonl"
    ledger.write_text("", encoding="utf-8")

    result = append_valid(item, "malformed-quick-fix-append-001")

    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "quick-fix status.md unexpected nonblank content" in result.stderr
    assert ledger.read_text(encoding="utf-8") == ""
    assert not ledger.with_suffix(".jsonl.tmp").exists()
    assert not (item / "agent-runs.jsonl.lock").exists()


def test_append_rejects_quick_fix_quartet_with_full_headings_and_bad_template_atomically(
    tmp_path: Path,
):
    cases = {
        "missing-template": minimal_quick_fix_status().replace(
            "template: quick-fix\n",
            "",
            1,
        ),
        "wrong-template": minimal_quick_fix_status().replace(
            "template: quick-fix",
            "template: full-delivery",
            1,
        ),
    }
    full_headings = "\n## Current state\n\n## Active agents\n\n## Completed agents\n\n## Next action\n"
    for name, status in cases.items():
        item = tmp_path / "work-items" / "active" / f"quick-fix-quartet-append-{name}"
        (item / "reviews").mkdir(parents=True)
        status += full_headings
        status_path = item / "status.md"
        status_path.write_text(status, encoding="utf-8")
        (item / "reviews" / "qa.md").write_text("PASS\n", encoding="utf-8")
        ledger = item / "agent-runs.jsonl"
        ledger.write_text("", encoding="utf-8")
        original_ledger = ledger.read_bytes()

        result = append_valid(item, f"quick-fix-quartet-append-{name}-001")

        assert result.returncode == 1, (name, result.stdout, result.stderr)
        assert "quick-fix status.md" in result.stderr, (name, result.stderr)
        assert status_path.read_text(encoding="utf-8") == status, name
        assert ledger.read_bytes() == original_ledger, name
        assert not ledger.with_suffix(".jsonl.tmp").exists(), name
        assert not (item / "agent-runs.jsonl.lock").exists(), name


def test_minimal_quick_fix_status_operates_through_ledger_qa_and_archive(tmp_path: Path):
    slug = "quick-fix-recovery"
    item = tmp_path / "work-items" / "active" / slug
    (item / "reviews").mkdir(parents=True)
    status_text = minimal_quick_fix_status()
    (item / "status.md").write_text(status_text, encoding="utf-8")
    (item / "reviews" / "qa.md").write_text("Gate: PASS\n", encoding="utf-8")

    initialized = run_ledger(item, "init")
    assert initialized.returncode == 0, initialized.stderr
    assert (item / "status.md").read_text(encoding="utf-8") == status_text

    implemented = run_ledger(
        item,
        "append",
        "--run-id",
        "run-quick-fix-implementer-001",
        "--role",
        "platform-engineer",
        "--execution-role",
        "external-worker",
        "--assigned-role",
        "platform-engineer",
        "--status",
        "completed",
        "--gate",
        "none",
        "--scope",
        "scripts/agent-run-ledger.py",
        "--started-at",
        "2026-07-30T10:01:00Z",
        "--updated-at",
        "2026-07-30T10:05:00Z",
    )
    assert implemented.returncode == 0, implemented.stderr

    reviewed = run_ledger(
        item,
        "append",
        "--run-id",
        "run-quick-fix-qa-001",
        "--role",
        "qa-engineer",
        "--execution-role",
        "external-reviewer",
        "--assigned-role",
        "qa-engineer",
        "--status",
        "completed",
        "--gate",
        "PASS",
        "--scope",
        "quick-fix lifecycle",
        "--artifact",
        "reviews/qa.md",
        "--evidence",
        "command:focused lifecycle tests",
        "--started-at",
        "2026-07-30T10:06:00Z",
        "--updated-at",
        "2026-07-30T10:08:00Z",
    )
    assert reviewed.returncode == 0, reviewed.stderr
    assert (item / "status.md").read_text(encoding="utf-8") == status_text

    active_validation = run_validator(item)
    assert active_validation.returncode == 0, active_validation.stdout
    assert "RESULT: PASS" in active_validation.stdout

    (item / "closure.md").write_text(
        "# Closure\n\nOutcome: delivered\n\nClosed: 2026-07-30\n",
        encoding="utf-8",
    )
    archived_item = tmp_path / "work-items" / "archive" / "2026-07" / slug
    archived_item.parent.mkdir(parents=True)
    shutil.move(str(item), str(archived_item))

    archived_validation = run_validator(archived_item)
    assert archived_validation.returncode == 0, archived_validation.stdout
    assert "RESULT: PASS" in archived_validation.stdout
    assert len((archived_item / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()) == 2
