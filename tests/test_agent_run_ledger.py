import json
import hashlib
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


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


def load_ledger_module():
    spec = importlib.util.spec_from_file_location("agent_run_ledger", LEDGER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def minimal_staged_status() -> str:
    return """---
template: staged
status: active
started: 2026-07-31T10:00:00Z
updated: 2026-07-31T10:05:00Z
---

Task: Keep the staged ledger contract aligned.
Current step: Record the implementation run.
Last result: Staged work item admitted.
Next action: Append the implementation verdict.
Scope boundary: Work-item lifecycle scripts and focused tests.
Owner: toolchain-engineer
Integration owner: lead
Evidence gate: Focused and full lifecycle suites.
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
    marker = load_ledger_module().APPEND_SUCCESS_MARKER
    assert marker == "RESULT: PASS append"
    assert result.stdout == f"{marker} ({item / 'agent-runs.jsonl'})\n"
    assert result.stderr == ""
    validator = run_validator(item)
    assert validator.returncode == 0, validator.stderr
    lines = (item / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["runId"] == "run-append-001"
    assert event["evidence"][0]["kind"] == "command"


def test_kimi_unsupported_effort_is_durable_and_validator_accepted(tmp_path: Path):
    item = prepare_valid_work_item(tmp_path)
    common = (
        "--role", "qa-engineer",
        "--execution-role", "external-reviewer",
        "--assigned-role", "qa-engineer",
        "--provider", "kimi",
        "--model", "kimi-code/k3",
        "--effort", "unsupported",
        "--status", "completed",
        "--gate", "PASS",
        "--scope", "provider provenance fixture",
        "--artifact", "reviews/qa.md",
        "--evidence", "command:provider-provenance-fixture",
        "--started-at", "2026-08-27T10:00:00Z",
        "--updated-at", "2026-08-27T10:00:00Z",
    )
    launch = run_ledger(
        item,
        "append",
        "--run-id", "dispatch-kimi-unsupported",
        "--event-kind", "launch",
        *common,
    )
    assert launch.returncode == 0, launch.stderr
    terminal = run_ledger(
        item,
        "append",
        "--run-id", "evidence-kimi-unsupported",
        "--event-kind", "terminal",
        "--launch-run-id", "dispatch-kimi-unsupported",
        "--terminal-class", "external-nonauthorizing",
        "--authorizing", "false",
        "--actual-execution-path", "direct-external-cli",
        "--artifact-identity", "sha256:" + "a" * 64,
        "--external-dispatch-id", "dispatch-kimi-unsupported",
        "--external-evidence-run-id", "evidence-kimi-unsupported",
        "--effort-mapping-loss", "no-native-effort-control",
        "--evidence", "command:provider-result-envelope-flushed",
        *common,
    )
    assert terminal.returncode == 0, terminal.stderr
    validator = run_validator(item)
    assert validator.returncode == 0, validator.stderr
    events = [
        json.loads(line)
        for line in (item / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["effort"] for event in events] == ["unsupported", "unsupported"]


def test_staged_init_and_append_preserve_status_bytes(tmp_path: Path):
    item = tmp_path / "work-items" / "active" / "staged-ledger"
    (item / "reviews").mkdir(parents=True)
    status_path = item / "status.md"
    original = minimal_staged_status().encode("utf-8")
    status_path.write_bytes(original)
    (item / "reviews" / "qa.md").write_text("PASS\n", encoding="utf-8")

    initialized = run_ledger(item, "init")

    assert initialized.returncode == 0, initialized.stderr
    assert status_path.read_bytes() == original
    appended = run_ledger(
        item,
        "append",
        "--run-id",
        "run-staged-append-001",
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
        "2026-07-31T10:00:00Z",
        "--updated-at",
        "2026-07-31T10:05:00Z",
    )

    assert appended.returncode == 0, appended.stderr
    assert status_path.read_bytes() == original
    validator = run_validator(item)
    assert validator.returncode == 0, validator.stderr


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


def test_append_writes_valid_terminal_scratch_evidence(tmp_path: Path):
    item = prepare_valid_work_item(tmp_path)
    launch = run_ledger(
        item,
        "append",
        "--run-id", "scratch-launch-001",
        "--role", "platform-engineer",
        "--execution-role", "internal",
        "--status", "running",
        "--gate", "none",
        "--scope", "scratch lifecycle",
        "--event-kind", "launch",
        "--started-at", "2026-08-09T00:00:00Z",
        "--updated-at", "2026-08-09T00:00:00Z",
    )
    assert launch.returncode == 0, launch.stderr
    entry = {
        "entryId": "capture",
        "path": ".scratch/work-items/ledger-helper/scratch-terminal-001/capture",
        "disposition": "retain",
        "reason": "Explicitly retained test evidence.",
        "canonicalPointer": "reviews/qa.md",
    }
    terminal = run_ledger(
        item,
        "append",
        "--run-id", "scratch-terminal-001",
        "--role", "platform-engineer",
        "--execution-role", "internal",
        "--status", "completed",
        "--gate", "PASS",
        "--scope", "scratch lifecycle",
        "--artifact", "reviews/qa.md",
        "--evidence", "command:focused scratch test",
        "--event-kind", "terminal",
        "--launch-run-id", "scratch-launch-001",
        "--scratch-evidence-json", json.dumps(entry),
        "--started-at", "2026-08-09T00:01:00Z",
        "--updated-at", "2026-08-09T00:01:00Z",
    )
    assert terminal.returncode == 0, terminal.stderr
    events = [json.loads(line) for line in (item / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert events[-1]["schemaVersion"] == 2
    assert events[-1]["scratchEvidence"] == [entry]


def test_append_rejects_duplicate_keys_in_scratch_evidence_json(tmp_path: Path):
    item = prepare_valid_work_item(tmp_path)
    result = run_ledger(
        item,
        "append",
        "--run-id", "scratch-terminal-duplicate",
        "--role", "platform-engineer",
        "--execution-role", "internal",
        "--status", "completed",
        "--gate", "PASS",
        "--scope", "scratch lifecycle",
        "--artifact", "reviews/qa.md",
        "--evidence", "command:focused scratch test",
        "--event-kind", "terminal",
        "--launch-run-id", "scratch-launch-001",
        "--scratch-evidence-json",
        '{"entryId":"capture","entryId":"shadow","path":"x","disposition":"retain","reason":"r","canonicalPointer":"reviews/qa.md"}',
        "--started-at", "2026-08-09T00:01:00Z",
        "--updated-at", "2026-08-09T00:01:00Z",
    )

    assert result.returncode == 1
    assert "duplicate JSON key" in result.stderr
    assert not (item / "agent-runs.jsonl").exists()


def test_append_rejects_nested_duplicate_keys_in_scratch_evidence_json(tmp_path: Path):
    item = prepare_valid_work_item(tmp_path)
    result = run_ledger(
        item,
        "append",
        "--run-id", "scratch-terminal-nested-duplicate",
        "--role", "platform-engineer",
        "--execution-role", "internal",
        "--status", "completed",
        "--gate", "PASS",
        "--scope", "scratch lifecycle",
        "--artifact", "reviews/qa.md",
        "--evidence", "command:focused scratch test",
        "--event-kind", "terminal",
        "--launch-run-id", "scratch-launch-001",
        "--scratch-evidence-json",
        '{"entryId":"capture","path":"x","disposition":"delete","reason":"r","canonicalPointer":"reviews/qa.md","proof":{"kind":"git-object-set","kind":"accepted-artifact"}}',
        "--started-at", "2026-08-09T00:01:00Z",
        "--updated-at", "2026-08-09T00:01:00Z",
    )

    assert result.returncode == 1
    assert "duplicate JSON key: kind" in result.stderr
    assert not (item / "agent-runs.jsonl").exists()


def test_scratch_evidence_raw_utf8_bytes_are_bounded_before_json_parse():
    ledger = load_ledger_module()
    validator = ledger.load_validator()
    maximum = validator.MAX_SCRATCH_EVIDENCE_JSON_BYTES
    raw = '{"entryId":"' + ("é" * ((maximum // 2) + 1))

    assert len(raw) < maximum
    assert len(raw.encode("utf-8")) > maximum
    with pytest.raises(ValueError, match=r"maximum raw UTF-8 length"):
        ledger.parse_scratch_evidence_json(raw, validator)


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


def test_init_and_append_reject_non_active_lifecycle_paths_without_mutation(tmp_path: Path):
    archived = tmp_path / "work-items" / "archive" / "2026-08" / "archived-ledger"
    nested = tmp_path / "work-items" / "active" / "active-ledger" / "nested"
    for item in (archived, nested):
        (item / "reviews").mkdir(parents=True)
        status_path = item / "status.md"
        original_status = valid_status().encode("utf-8")
        status_path.write_bytes(original_status)
        (item / "reviews" / "qa.md").write_text("PASS\n", encoding="utf-8")

        initialized = run_ledger(item, "init")
        assert initialized.returncode == 1, (item, initialized.stdout, initialized.stderr)
        assert "current work-items/active/<item> directory" in initialized.stderr
        assert status_path.read_bytes() == original_status
        assert not (item / "agent-runs.jsonl").exists()

        appended = append_valid(item, f"reject-{item.name}")
        assert appended.returncode == 1, (item, appended.stdout, appended.stderr)
        assert "current work-items/active/<item> directory" in appended.stderr
        assert status_path.read_bytes() == original_status
        assert not (item / "agent-runs.jsonl").exists()


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


def test_rollup_counts_duplicate_key_ledger_line_as_malformed(tmp_path: Path):
    item = prepare_valid_work_item(tmp_path)
    (item / "agent-runs.jsonl").write_text(
        '{"runId":"first","runId":"second"}\n',
        encoding="utf-8",
    )

    result = run_ledger(item, "rollup")

    assert result.returncode == 0, result.stderr
    assert "malformed lines: 1" in result.stdout
    assert "total runs: 0" in result.stdout


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


def _prepare_recovery_writer_item(tmp_path: Path) -> tuple[Path, bytes, str]:
    item = prepare_valid_work_item(tmp_path)
    revise = {
        "schemaVersion": 2, "runId": "run-writer-revise", "workItem": item.name,
        "role": "architecture-reviewer", "executionRole": "external-reviewer",
        "status": "revise", "gate": "REVISE", "scope": ["fixture"],
        "artifact": "reviews/qa.md", "lane": "architecture", "effort": "high",
        "provider": "codex", "findingClass": "correctness",
        "startedAt": "2026-08-17T00:00:00Z", "updatedAt": "2026-08-17T00:00:00Z",
    }
    bad = {
        "schemaVersion": 2, "runId": "run-writer-invalid-closer", "workItem": item.name,
        "role": "architecture-reviewer", "executionRole": "main",
        "status": "completed", "gate": "PASS", "scope": ["fixture"],
        "artifact": "reviews/qa.md", "lane": "architecture", "effort": "high",
        "provider": "codex", "closesRunIds": [revise["runId"]],
        "evidence": [{"kind": "review", "ref": "author self-close"}],
        "startedAt": "2026-08-17T00:01:00Z", "updatedAt": "2026-08-17T00:01:00Z",
    }
    revise_line = json.dumps(revise, ensure_ascii=False, separators=(",", ":")).encode()
    bad_line = json.dumps(bad, ensure_ascii=False, separators=(",", ":")).encode()
    old = revise_line + b"\n" + bad_line + b"\n"
    (item / "agent-runs.jsonl").write_bytes(old)
    return item, old, hashlib.sha256(bad_line).hexdigest()


def _run_recovery(item: Path, digest: str, *extra: str) -> subprocess.CompletedProcess:
    return run_ledger(
        item,
        "recover-invalid-closure",
        "--run-id", "run-writer-recovery-control",
        "--target-run-id", "run-writer-invalid-closer",
        "--target-event-sha256", digest,
        "--evidence", f"manual-check:run-writer-invalid-closer {digest}",
        "--started-at", "2026-08-17T00:02:00Z",
        "--updated-at", "2026-08-17T00:02:00Z",
        *extra,
    )


def test_recover_invalid_closure_preserves_exact_prefix_and_phase_failures(tmp_path: Path):
    item, old, digest = _prepare_recovery_writer_item(tmp_path)
    wrong = _run_recovery(item, "0" * 64)
    assert wrong.returncode != 0
    assert (item / "agent-runs.jsonl").read_bytes() == old
    assert "ledger-recovery:target-digest-mismatch" in wrong.stdout
    result = _run_recovery(item, digest)
    current = (item / "agent-runs.jsonl").read_bytes()
    assert result.returncode == 0, result.stdout
    assert current.startswith(old) and len(current) > len(old)
    assert result.stdout.count("RESULT: PASS recover-invalid-closure (") == 1
    assert not (item / "agent-runs.jsonl.lock").exists()
    assert not (item / "agent-runs.jsonl.tmp").exists()


def test_closure_recovery_v3_coexistence_and_writer_refusal(tmp_path: Path):
    item, old, digest = _prepare_recovery_writer_item(tmp_path)
    v3 = {"schemaVersion": 3, "eventId": "v3-event", "operationId": "v3-operation", "fingerprint": "1" * 64, "priorHead": "GENESIS", "recordedAt": "2026-08-17T00:00:00Z", "eventType": "solution-bootstrap", "payload": {}}
    before = old + json.dumps(v3, separators=(",", ":")).encode() + b"\n"
    (item / "agent-runs.jsonl").write_bytes(before)
    result = _run_recovery(item, digest)
    assert result.returncode != 0
    assert "legacy V1/V2 writer refuses a ledger containing schemaVersion 3" in result.stdout
    assert (item / "agent-runs.jsonl").read_bytes() == before


def test_recover_invalid_closure_marker_requires_exact_readback(tmp_path: Path):
    item, old, digest = _prepare_recovery_writer_item(tmp_path)
    result = _run_recovery(item, digest, "--inject-failure", "post-replace-readback")
    assert result.returncode != 0
    assert "ledger-recovery:post-commit-readback-indeterminate" in result.stdout
    assert "RESULT: PASS recover-invalid-closure (" not in result.stdout
    committed = (item / "agent-runs.jsonl").read_bytes()
    assert committed.startswith(old) and len(committed) > len(old)


def test_append_persists_typed_external_nonauthorizing_terminal(tmp_path: Path):
    """Provider evidence cannot be mistaken for an authorizing lifecycle close."""

    item = prepare_valid_work_item(tmp_path)
    result = run_ledger(
        item,
        "append",
        "--run-id", "run-external-evidence-001",
        "--role", "external-reviewer",
        "--execution-role", "external-reviewer",
        "--assigned-role", "qa-engineer",
        "--provider", "kimi",
        "--status", "completed",
        "--gate", "PASS",
        "--scope", "provider evidence",
        "--artifact", "reviews/qa.md",
        "--evidence", "artifact:reviews/qa.md",
        "--terminal-class", "external-nonauthorizing",
        "--authorizing", "false",
        "--actual-execution-path", "direct-external-cli",
        "--artifact-identity", "sha256:" + "a" * 64,
        "--external-dispatch-id", "dispatch-external-001",
        "--external-evidence-run-id", "run-external-evidence-001",
        "--effort-mapping-loss", "no-native-effort-control",
        "--started-at", "2026-08-24T10:00:00Z",
        "--updated-at", "2026-08-24T10:00:00Z",
    )

    assert result.returncode == 0, result.stderr
    event = json.loads((item / "agent-runs.jsonl").read_text(encoding="utf-8"))
    assert event["terminalClass"] == "external-nonauthorizing"
    assert event["authorizing"] is False
    assert event["closesRunIds"] == []
    assert event["assignedRole"] == "qa-engineer"
    assert event["artifactIdentity"] == "sha256:" + "a" * 64
    assert event["externalDispatchId"] == "dispatch-external-001"
    assert event["externalEvidenceRunId"] == "run-external-evidence-001"
    assert event["effortMappingLoss"] == "no-native-effort-control"
    validated = run_validator(item)
    assert validated.returncode == 0, validated.stdout


def test_append_accepts_codex_external_terminal_without_extended_provenance_ids(tmp_path: Path):
    """Codex evidence is the actual terminal/launch pair, not a fabricated dispatch id."""

    item = prepare_valid_work_item(tmp_path)
    common = [
        "--work-item", str(item), "append", "--role", "external-reviewer",
        "--execution-role", "external-reviewer", "--assigned-role", "qa-engineer",
        "--provider", "codex", "--model", "gpt-5.6-sol", "--effort", "high",
        "--scope", "provider evidence", "--artifact", "reviews/qa.md",
    ]
    launch = run_ledger(
        item,
        *common,
        "--run-id", "run-codex-launch-001", "--status", "running", "--gate", "none",
        "--event-kind", "launch",
    )
    terminal = run_ledger(
        item,
        *common,
        "--run-id", "run-codex-terminal-001", "--status", "completed", "--gate", "PASS",
        "--event-kind", "terminal", "--launch-run-id", "run-codex-launch-001",
        "--terminal-class", "external-nonauthorizing", "--authorizing", "false",
        "--actual-execution-path", "direct-external-cli", "--artifact-identity", "sha256:" + "c" * 64,
        "--evidence", "artifact:reviews/qa.md",
    )

    assert launch.returncode == 0, launch.stderr
    assert terminal.returncode == 0, terminal.stderr
    events = [json.loads(line) for line in (item / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert "externalDispatchId" not in events[-1]
    assert "externalEvidenceRunId" not in events[-1]
    assert events[-1]["runId"] == "run-codex-terminal-001"
    assert events[-1]["launchRunId"] == "run-codex-launch-001"
    validated = run_validator(item)
    assert validated.returncode == 0, validated.stdout


@pytest.mark.parametrize(
    "encoded",
    (
        "{\"not\":\"an-array\"}",
        "[\"--model\", 7]",
        "[\"--prompt\", \"secret body\"]",
        "[\"--api-key=secret\"]",
    ),
)
def test_append_rejects_malformed_or_unsafe_launch_flag_binding(
    tmp_path: Path, encoded: str
) -> None:
    item = prepare_valid_work_item(tmp_path)
    result = run_ledger(
        item,
        "append",
        "--run-id", "run-launch-flags-invalid-001",
        "--role", "external-reviewer",
        "--execution-role", "external-reviewer",
        "--assigned-role", "qa-engineer",
        "--provider", "codex",
        "--model", "gpt-5.6-sol",
        "--effort", "high",
        "--status", "running",
        "--gate", "none",
        "--scope", "provider evidence",
        "--event-kind", "launch",
        "--launch-flags-json", encoded,
    )

    assert result.returncode != 0
    ledger = item / "agent-runs.jsonl"
    assert not ledger.exists() or ledger.read_text(encoding="utf-8") == ""


def test_terminal_launch_flags_must_match_the_referenced_launch(tmp_path: Path) -> None:
    item = prepare_valid_work_item(tmp_path)
    common = [
        "--work-item", str(item), "append", "--role", "external-reviewer",
        "--execution-role", "external-reviewer", "--assigned-role", "qa-engineer",
        "--provider", "codex", "--model", "gpt-5.6-sol", "--effort", "high",
        "--scope", "provider evidence", "--artifact", "reviews/qa.md",
    ]
    base_flags = [
        "--model", "gpt-5.6-sol", "-c", "model_reasoning_effort=high", "--sandbox",
    ]
    launch = run_ledger(
        item,
        *common,
        "--run-id", "run-flags-launch-001", "--status", "running", "--gate", "none",
        "--event-kind", "launch", "--launch-flags-json",
        json.dumps([*base_flags, "read-only"]),
    )
    terminal = run_ledger(
        item,
        *common,
        "--run-id", "run-flags-terminal-001", "--status", "completed", "--gate", "PASS",
        "--event-kind", "terminal", "--launch-run-id", "run-flags-launch-001",
        "--terminal-class", "external-nonauthorizing", "--authorizing", "false",
        "--actual-execution-path", "direct-external-cli",
        "--artifact-identity", "sha256:" + "d" * 64,
        "--evidence", "artifact:reviews/qa.md", "--launch-flags-json",
        json.dumps([*base_flags, "workspace-write"]),
    )

    assert launch.returncode == 0, launch.stderr
    assert terminal.returncode != 0
    events = [
        json.loads(line)
        for line in (item / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["runId"] for event in events] == ["run-flags-launch-001"]


def test_internal_final_closer_binds_one_external_evidence_tuple(tmp_path: Path):
    """Only a distinct internal final reviewer can discharge the matching gate."""

    item = prepare_valid_work_item(tmp_path)
    work_item = item.name
    events = [
        {
            "schemaVersion": 2, "runId": "run-open-internal-gate-001",
            "workItem": work_item, "role": "qa-engineer", "executionRole": "internal",
            "status": "revise", "gate": "REVISE", "scope": ["provider evidence review"],
            "artifact": "reviews/qa.md", "lane": "provider-evidence", "effort": "high",
            "startedAt": "2026-08-24T10:00:00Z", "updatedAt": "2026-08-24T10:00:00Z",
        },
        {
            "schemaVersion": 2, "runId": "run-external-evidence-002",
            "workItem": work_item, "role": "external-reviewer", "executionRole": "external-reviewer",
            "assignedRole": "qa-engineer", "provider": "kimi", "status": "completed", "gate": "PASS",
            "scope": ["provider evidence"], "artifact": "reviews/qa.md",
            "terminalClass": "external-nonauthorizing", "authorizing": False,
            "actualExecutionPath": "direct-external-cli", "artifactIdentity": "sha256:" + "b" * 64,
            "externalDispatchId": "dispatch-external-002",
            "externalEvidenceRunId": "run-external-evidence-002", "closesRunIds": [],
            "effortMappingLoss": "no-native-effort-control",
            "evidence": [{"kind": "artifact", "ref": "reviews/qa.md"}],
            "startedAt": "2026-08-24T10:01:00Z", "updatedAt": "2026-08-24T10:01:00Z",
        },
        {
            "schemaVersion": 2, "runId": "run-internal-closer-001",
            "workItem": work_item, "role": "architecture-reviewer", "executionRole": "internal",
            "assignedRole": "architecture-reviewer", "status": "completed", "gate": "PASS",
            "scope": ["provider evidence review"], "artifact": "reviews/qa.md",
            "lane": "provider-evidence", "effort": "high",
            "terminalClass": "internal-authorizing", "authorizing": True,
            "actualExecutionPath": "internal", "artifactIdentity": "sha256:" + "b" * 64,
            "externalDispatchId": "dispatch-external-002",
            "externalEvidenceRunId": "run-external-evidence-002",
            "closerRunId": "run-internal-closer-001",
            "targetTuple": {
                "workItem": work_item, "assignedInternalRole": "qa-engineer",
                "artifactIdentity": "sha256:" + "b" * 64,
                "externalDispatchId": "dispatch-external-002",
            },
            "closesRunIds": ["run-open-internal-gate-001"],
            "evidence": [{"kind": "review", "ref": "reviews/qa.md"}],
            "startedAt": "2026-08-24T10:02:00Z", "updatedAt": "2026-08-24T10:02:00Z",
        },
    ]
    (item / "agent-runs.jsonl").write_text(
        "".join(json.dumps(event, separators=(",", ":")) + "\n" for event in events),
        encoding="utf-8",
    )

    validated = run_validator(item)
    assert validated.returncode == 0, validated.stdout


def test_internal_closer_binds_actual_codex_terminal_and_launch_without_extended_ids(tmp_path: Path):
    """A Codex closer uses the terminal ledger identity, never a dispatch-shaped alias."""

    item = prepare_valid_work_item(tmp_path)
    work_item = item.name
    artifact = "sha256:" + "d" * 64
    events = [
        {
            "schemaVersion": 2, "runId": "run-codex-open-gate-001", "workItem": work_item,
            "role": "qa-engineer", "executionRole": "internal", "status": "revise",
            "gate": "REVISE", "scope": ["provider evidence review"], "artifact": "reviews/qa.md",
            "lane": "provider-evidence", "effort": "high",
            "startedAt": "2026-08-25T10:00:00Z", "updatedAt": "2026-08-25T10:00:00Z",
        },
        {
            "schemaVersion": 2, "runId": "run-codex-launch-002", "workItem": work_item,
            "role": "external-reviewer", "executionRole": "external-reviewer", "assignedRole": "qa-engineer",
            "provider": "codex", "status": "running", "gate": "none", "eventKind": "launch",
            "scope": ["provider evidence"], "artifact": "reviews/qa.md", "effort": "high",
            "startedAt": "2026-08-25T10:01:00Z", "updatedAt": "2026-08-25T10:01:00Z",
        },
        {
            "schemaVersion": 2, "runId": "run-codex-terminal-002", "workItem": work_item,
            "role": "external-reviewer", "executionRole": "external-reviewer", "assignedRole": "qa-engineer",
            "provider": "codex", "status": "completed", "gate": "PASS", "eventKind": "terminal",
            "launchRunId": "run-codex-launch-002", "scope": ["provider evidence"], "artifact": "reviews/qa.md",
            "effort": "high", "terminalClass": "external-nonauthorizing", "authorizing": False,
            "actualExecutionPath": "direct-external-cli", "artifactIdentity": artifact, "closesRunIds": [],
            "evidence": [{"kind": "artifact", "ref": "reviews/qa.md"}],
            "startedAt": "2026-08-25T10:02:00Z", "updatedAt": "2026-08-25T10:02:00Z",
        },
        {
            "schemaVersion": 2, "runId": "run-codex-closer-002", "workItem": work_item,
            "role": "architecture-reviewer", "executionRole": "internal", "assignedRole": "architecture-reviewer",
            "status": "completed", "gate": "PASS", "scope": ["provider evidence review"],
            "artifact": "reviews/qa.md", "lane": "provider-evidence", "effort": "high",
            "terminalClass": "internal-authorizing", "authorizing": True, "actualExecutionPath": "internal",
            "artifactIdentity": artifact, "externalEvidenceRunId": "run-codex-terminal-002",
            "closerRunId": "run-codex-closer-002",
            "targetTuple": {"workItem": work_item, "assignedInternalRole": "qa-engineer", "artifactIdentity": artifact},
            "closesRunIds": ["run-codex-open-gate-001"], "evidence": [{"kind": "review", "ref": "reviews/qa.md"}],
            "startedAt": "2026-08-25T10:03:00Z", "updatedAt": "2026-08-25T10:03:00Z",
        },
    ]
    (item / "agent-runs.jsonl").write_text(
        "".join(json.dumps(event, separators=(",", ":")) + "\n" for event in events), encoding="utf-8"
    )

    validated = run_validator(item)

    assert validated.returncode == 0, validated.stdout
    events[2]["status"] = "revise"
    events[2]["gate"] = "REVISE"
    (item / "agent-runs.jsonl").write_text(
        "".join(json.dumps(event, separators=(",", ":")) + "\n" for event in events), encoding="utf-8"
    )
    revised = run_validator(item)
    assert revised.returncode != 0
    assert "internal closer does not bind" in revised.stdout


def test_concurrent_process_appends_preserve_each_complete_event(tmp_path: Path):
    """Two real writers contend on one ledger without losing an admitted row."""
    item = prepare_valid_work_item(tmp_path)
    children = []
    expected_ids = {"concurrent-writer-0", "concurrent-writer-1"}
    try:
        for run_id in sorted(expected_ids):
            children.append(subprocess.Popen(
                [sys.executable, str(LEDGER), "--work-item", str(item), "append",
                 "--run-id", run_id, "--role", "qa-engineer", "--execution-role", "internal",
                 "--status", "completed", "--gate", "PASS", "--scope", "ledger serialization",
                 "--artifact", "reviews/qa.md", "--evidence", "command:concurrent-ledger-fixture",
                 "--started-at", "2026-09-05T00:00:00Z",
                 "--updated-at", "2026-09-05T00:00:00Z"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            ))
        for child in children:
            stdout, stderr = child.communicate(timeout=40)
            assert child.returncode == 0, stdout + stderr
        rows = [json.loads(line) for line in (item / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()]
        assert len(rows) == len(expected_ids)
        assert {row["runId"] for row in rows} == expected_ids
        assert not (item / "agent-runs.jsonl.lock").exists()
        assert not (item / "agent-runs.jsonl.tmp").exists()
        checked = run_validator(item)
        assert checked.returncode == 0, checked.stdout + checked.stderr
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=10)
