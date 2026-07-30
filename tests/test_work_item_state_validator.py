import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate-work-item-state.py"
CONTRACT_CHECK = ROOT / "scripts" / "check-agent-run-ledger-contract.py"


def load_validator_module():
    spec = importlib.util.spec_from_file_location("validate_work_item_state_direct", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_validator(work_item: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), "--work-item", str(work_item)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def run_contract_check() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CONTRACT_CHECK), "--root", str(ROOT)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def valid_status() -> str:
    # Legacy status shape: older work items carry `orchestrator: main | lead`. Kept as a
    # labeled legacy fixture; canonical_status() below covers the current field.
    return """---
template: full-delivery
orchestrator: lead
started: 2026-05-03
updated: 2026-05-03 14:24
---

## Current state

- **Primary task**: add agent run tracking
- **Primary task status**: active
- **Interruption marker**: none
- **Stage**: QA
- **Main conv role**: reviewing artifact
- **Last accepted artifact**: reviews/qa.md
- **Open obligations before closeout**: none

## Active agents

| Agent | Role | Status | Launched |
| --- | --- | --- | --- |

## Completed agents

| Agent | Role | Result | Artifact |
| --- | --- | --- | --- |
| qa-001 | qa-engineer | PASS | reviews/qa.md |

## Next action

Close the stage after publication gate.
"""


def canonical_status() -> str:
    # Canonical status shape: current field is `orchestration: light | full-lead`.
    return valid_status().replace("orchestrator: lead", "orchestration: full-lead")


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


def ledger_event(**overrides):
    event = {
        "schemaVersion": 1,
        "runId": "2026-05-03T14-20-00Z-qa-001",
        "workItem": "agent-execution-tracking",
        "role": "qa-engineer",
        "executionRole": "internal",
        "assignedRole": "qa-engineer",
        "provider": "codex",
        "model": "gpt-5.6-sol-xhigh",
        "status": "completed",
        "gate": "PASS",
        "scope": ["scripts/validate-work-item-state.py"],
        "promptFile": ".scratch/prompts/qa-001.md",
        "artifact": "reviews/qa.md",
        "evidence": [{"kind": "command", "ref": "pytest tests/test_work_item_state_validator.py -q", "result": "passed"}],
        "startedAt": "2026-05-03T14:20:00Z",
        "updatedAt": "2026-05-03T14:24:00Z",
        "notes": "happy path",
    }
    event.update(overrides)
    return event


def test_pass_ledger_with_artifact_and_evidence(tmp_path: Path) -> None:
    item = tmp_path / "work-items" / "active" / "agent-execution-tracking"
    write(item / "status.md", valid_status())
    write(item / "reviews" / "qa.md", "# QA\n\nGate: PASS\n")
    write(item / "agent-runs.jsonl", json.dumps(ledger_event()) + "\n")

    result = run_validator(item)

    assert result.returncode == 0, result.stdout
    assert "RESULT: PASS" in result.stdout


def test_pass_ledger_with_canonical_orchestration_field(tmp_path: Path) -> None:
    item = tmp_path / "work-items" / "active" / "agent-execution-tracking"
    write(item / "status.md", canonical_status())
    write(item / "reviews" / "qa.md", "# QA\n\nGate: PASS\n")
    write(item / "agent-runs.jsonl", json.dumps(ledger_event()) + "\n")

    result = run_validator(item)

    assert result.returncode == 0, result.stdout
    assert "RESULT: PASS" in result.stdout


def test_quick_fix_minimal_status_fails_when_each_required_field_is_omitted(tmp_path: Path) -> None:
    validator = load_validator_module()
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
        item = tmp_path / "work-items" / "active" / f"missing-quick-fix-field-{index}"
        status = minimal_quick_fix_status().replace(required_line + "\n", "", 1)
        write(item / "status.md", status)

        errors: list[str] = []
        validator.validate_status(item, [], errors)

        assert errors, required_line
        assert any("quick-fix status.md" in error for error in errors), (required_line, errors)


def test_quick_fix_minimal_status_accepts_blank_lines_but_no_other_content(tmp_path: Path) -> None:
    validator = load_validator_module()
    valid_item = tmp_path / "work-items" / "active" / "valid-quick-fix"
    valid = minimal_quick_fix_status().replace(
        "- **Current step**",
        "\n\n- **Current step**",
        1,
    )
    write(valid_item / "status.md", valid)

    valid_errors: list[str] = []
    validator.validate_status(valid_item, [], valid_errors)

    assert valid_errors == []

    malformed_statuses = {
        "extra-frontmatter": minimal_quick_fix_status().replace(
            "updated: 2026-07-30 10:00\n",
            "updated: 2026-07-30 10:00\nowner: lead\n",
            1,
        ),
        "duplicate-lifecycle-field": minimal_quick_fix_status().replace(
            "updated: 2026-07-30 10:00\n",
            "updated: 2026-07-30 10:00\nupdated: 2026-07-30 10:01\n",
            1,
        ),
        "wrong-template": minimal_quick_fix_status().replace(
            "template: quick-fix",
            "template: full-delivery",
            1,
        ),
        "duplicate-recovery-fact": (
            minimal_quick_fix_status()
            + "- **Task**: Duplicate recovery fact.\n"
        ),
        "research-heading": minimal_quick_fix_status() + "## Research\nUnexpected.\n",
        "plan-heading": minimal_quick_fix_status() + "## Plan\nUnexpected.\n",
        "arbitrary-prelude": minimal_quick_fix_status().replace(
            "- **Task**",
            "Unexpected prelude.\n- **Task**",
            1,
        ),
    }
    for name, status in malformed_statuses.items():
        item = tmp_path / "work-items" / "active" / name
        write(item / "status.md", status)
        errors: list[str] = []

        validator.validate_status(item, [], errors)

        assert errors, name
        assert any("quick-fix status.md" in error for error in errors), (name, errors)


def test_duplicate_template_with_full_status_headings_stays_on_quick_fix_validation(
    tmp_path: Path,
) -> None:
    validator = load_validator_module()
    item = tmp_path / "work-items" / "active" / "duplicate-template-with-full-headings"
    status = minimal_quick_fix_status().replace(
        "template: quick-fix\n",
        "template: quick-fix\ntemplate: full-delivery\n",
        1,
    )
    status += "\n## Current state\n\n## Active agents\n\n## Completed agents\n\n## Next action\n"
    write(item / "status.md", status)

    errors: list[str] = []
    validator.validate_status(item, [], errors)

    assert "quick-fix status.md duplicate lifecycle field: template" in errors


def test_complete_quick_fix_quartet_with_full_headings_stays_strict_without_valid_template(
    tmp_path: Path,
) -> None:
    validator = load_validator_module()
    cases = {
        "missing-template": (
            minimal_quick_fix_status().replace("template: quick-fix\n", "", 1),
            "quick-fix status.md missing lifecycle field: template",
        ),
        "wrong-template": (
            minimal_quick_fix_status().replace(
                "template: quick-fix",
                "template: full-delivery",
                1,
            ),
            "quick-fix status.md lifecycle field template must be quick-fix",
        ),
    }
    full_headings = "\n## Current state\n\n## Active agents\n\n## Completed agents\n\n## Next action\n"
    for name, (status, expected_error) in cases.items():
        item = tmp_path / "work-items" / "active" / name
        write(item / "status.md", status + full_headings)
        errors: list[str] = []

        validator.validate_status(item, [], errors)

        assert expected_error in errors, (name, errors)


def test_full_status_with_last_result_fact_alone_remains_full(tmp_path: Path) -> None:
    validator = load_validator_module()
    for name, status in (
        ("legacy-full", valid_status()),
        ("canonical-full", canonical_status()),
    ):
        item = tmp_path / "work-items" / "active" / name
        status = status.replace(
            "## Next action",
            "- **Last result**: Full-delivery checkpoint.\n\n## Next action",
            1,
        )
        write(item / "status.md", status)
        errors: list[str] = []

        validator.validate_status(item, [], errors)

        assert errors == [], (name, errors)


def test_schema_contract_check_exercises_validator_negative_cases() -> None:
    result = run_contract_check()

    assert result.returncode == 0, result.stdout
    assert "RESULT: PASS" in result.stdout


def test_schema_contract_includes_security_reviewer_waiver_gate() -> None:
    schema = json.loads(
        (ROOT / "shared" / "schemas" / "agent-runs.schema.json").read_text(encoding="utf-8")
    )
    gate_values = {
        value
        for branch in schema["properties"]["gate"]["oneOf"]
        for value in branch.get("enum", [])
    }

    assert "WAIVED:security-reviewer" in gate_values


def test_legacy_execution_role_lead_still_reads(tmp_path: Path) -> None:
    # F25 legacy READ-mapping: a ledger written before the main|lead collapse may
    # carry executionRole "lead"; it validates (reads as "main" — same owner).
    item = tmp_path / "work-items" / "active" / "agent-execution-tracking"
    write(item / "status.md", valid_status())
    write(item / "reviews" / "qa.md", "# QA\n\nGate: PASS\n")
    write(item / "agent-runs.jsonl", json.dumps(ledger_event(executionRole="lead")) + "\n")

    result = run_validator(item)

    assert result.returncode == 0, result.stdout
    assert "RESULT: PASS" in result.stdout


def test_unknown_execution_role_fails(tmp_path: Path) -> None:
    # ...but the legacy mapping is not an escape hatch: a value outside the
    # canonical enum and the legacy map still fails.
    item = tmp_path / "work-items" / "active" / "agent-execution-tracking"
    write(item / "status.md", valid_status())
    write(item / "reviews" / "qa.md", "# QA\n\nGate: PASS\n")
    write(item / "agent-runs.jsonl", json.dumps(ledger_event(executionRole="foo")) + "\n")

    result = run_validator(item)

    assert result.returncode == 1
    assert "invalid executionRole" in result.stdout


def test_pass_without_evidence_fails(tmp_path: Path) -> None:
    item = tmp_path / "work-items" / "active" / "agent-execution-tracking"
    write(item / "status.md", valid_status())
    write(item / "reviews" / "qa.md", "# QA\n\nGate: PASS\n")
    write(item / "agent-runs.jsonl", json.dumps(ledger_event(evidence=[])) + "\n")

    result = run_validator(item)

    assert result.returncode == 1
    assert "PASS gate requires evidence" in result.stdout


def test_pass_artifact_must_stay_inside_work_item(tmp_path: Path) -> None:
    item = tmp_path / "work-items" / "active" / "agent-execution-tracking"
    write(item / "status.md", valid_status())
    write(tmp_path / "outside.md", "# Outside\n")
    write(item / "agent-runs.jsonl", json.dumps(ledger_event(artifact="../../../outside.md")) + "\n")

    result = run_validator(item)

    assert result.returncode == 1
    assert "artifact escapes the work item" in result.stdout


def test_pass_evidence_entry_requires_kind_and_ref(tmp_path: Path) -> None:
    item = tmp_path / "work-items" / "active" / "agent-execution-tracking"
    write(item / "status.md", valid_status())
    write(item / "reviews" / "qa.md", "# QA\n\nGate: PASS\n")
    write(item / "agent-runs.jsonl", json.dumps(ledger_event(evidence=[{"kind": "unknown"}])) + "\n")

    result = run_validator(item)

    assert result.returncode == 1
    assert "invalid kind" in result.stdout
    assert "requires ref" in result.stdout


def test_evidence_entry_rejects_unexpected_fields(tmp_path: Path) -> None:
    item = tmp_path / "work-items" / "active" / "agent-execution-tracking"
    write(item / "status.md", valid_status())
    write(item / "reviews" / "qa.md", "# QA\n\nGate: PASS\n")
    evidence = [{"kind": "command", "ref": "pytest -q", "extra": "unexpected"}]
    write(item / "agent-runs.jsonl", json.dumps(ledger_event(evidence=evidence)) + "\n")

    result = run_validator(item)

    assert result.returncode == 1
    assert "unexpected field" in result.stdout


def test_required_string_min_lengths_match_schema(tmp_path: Path) -> None:
    item = tmp_path / "work-items" / "active" / "agent-execution-tracking"
    write(item / "status.md", valid_status())
    write(item / "reviews" / "qa.md", "# QA\n\nGate: PASS\n")
    write(
        item / "agent-runs.jsonl",
        json.dumps(ledger_event(runId="x", startedAt="1", updatedAt="2")) + "\n",
    )

    result = run_validator(item)

    assert result.returncode == 1
    assert "runId must be at least 8 characters" in result.stdout
    assert "startedAt must be at least 10 characters" in result.stdout
    assert "updatedAt must be at least 10 characters" in result.stdout


def test_return_gate_accepts_concrete_role(tmp_path: Path) -> None:
    item = tmp_path / "work-items" / "active" / "agent-execution-tracking"
    write(item / "status.md", valid_status())
    write(item / "agent-runs.jsonl", json.dumps(ledger_event(gate="RETURN(security-engineer)", artifact="", evidence=[])) + "\n")

    result = run_validator(item)

    assert result.returncode == 0, result.stdout
    assert "RESULT: PASS" in result.stdout


def test_unexpected_field_fails(tmp_path: Path) -> None:
    item = tmp_path / "work-items" / "active" / "agent-execution-tracking"
    write(item / "status.md", valid_status())
    write(item / "reviews" / "qa.md", "# QA\n\nGate: PASS\n")
    write(item / "agent-runs.jsonl", json.dumps(ledger_event(unexpected="value")) + "\n")

    result = run_validator(item)

    assert result.returncode == 1
    assert "unexpected field" in result.stdout


def test_artifact_type_error_is_reported_without_crashing(tmp_path: Path) -> None:
    item = tmp_path / "work-items" / "active" / "agent-execution-tracking"
    write(item / "status.md", valid_status())
    write(item / "agent-runs.jsonl", json.dumps(ledger_event(artifact=123)) + "\n")

    result = run_validator(item)

    assert result.returncode == 1
    assert "artifact must be a string" in result.stdout
    assert "TypeError" not in result.stdout


def test_closed_status_with_running_agent_fails(tmp_path: Path) -> None:
    item = tmp_path / "work-items" / "active" / "agent-execution-tracking"
    closed = valid_status().replace("Primary task status**: active", "Primary task status**: closed")
    write(item / "status.md", closed)
    write(item / "agent-runs.jsonl", json.dumps(ledger_event(status="running", gate="none", artifact="", evidence=[])) + "\n")

    result = run_validator(item)

    assert result.returncode == 1
    assert "cannot be closed while ledger has running agents" in result.stdout


def test_duplicate_run_id_fails(tmp_path: Path) -> None:
    item = tmp_path / "work-items" / "active" / "agent-execution-tracking"
    write(item / "status.md", valid_status())
    event = ledger_event()
    write(item / "reviews" / "qa.md", "# QA\n\nGate: PASS\n")
    write(item / "agent-runs.jsonl", json.dumps(event) + "\n" + json.dumps(event) + "\n")

    result = run_validator(item)

    assert result.returncode == 1
    assert "duplicate runId" in result.stdout


def test_blocked_gate_requires_blocked_status(tmp_path: Path) -> None:
    item = tmp_path / "work-items" / "active" / "agent-execution-tracking"
    write(item / "status.md", valid_status())
    write(item / "agent-runs.jsonl", json.dumps(ledger_event(status="completed", gate="BLOCKED:dependency", artifact="", evidence=[])) + "\n")

    result = run_validator(item)

    assert result.returncode == 1
    assert "BLOCKED gate requires blocked status" in result.stdout


# --- resolver family: archiving an item must not break its own ledger's artifact
# paths (bug 2026-07-26-archiving-an-item-breaks-its-own-ledger-artifact-paths.md).
# The ledger records `work-items/active/<slug>/...` while the item lives under
# active/; the mandatory close step MOVES the directory to
# archive/<YYYY-MM>/<slug>/ without ever touching the ledger (append-only audit
# record). These tests perform the real move (shutil.move), not a simulation --
# the entry is explicit that the failure mode is only visible from a test that
# performs a move.

def test_resolve_work_item_path_finds_artifact_after_real_archive_move(tmp_path: Path) -> None:
    module = load_validator_module()
    slug = "2026-07-25-review-round-cap-enforcement"
    active_item = tmp_path / "work-items" / "active" / slug
    write(active_item / "design.md", "# Design\n")

    archived_item = tmp_path / "work-items" / "archive" / "2026-07" / slug
    archived_item.parent.mkdir(parents=True)
    shutil.move(str(active_item), str(archived_item))

    recorded_value = f"work-items/active/{slug}/design.md"
    errors: list[str] = []
    resolved = module.resolve_work_item_path(archived_item, recorded_value, "artifact", "run-001", errors)

    assert not errors, errors
    assert resolved is not None
    assert resolved.exists()
    assert resolved == (archived_item / "design.md").resolve()


def test_close_move_does_not_break_previously_valid_pass_gate(tmp_path: Path) -> None:
    """End-to-end reproduction via the CLI: closing an item correctly (active/ ->
    archive/<YYYY-MM>/) must not turn its own already-valid PASS gate into a FAIL,
    and the fix must not require touching the ledger."""
    slug = "close-move-item"
    item = tmp_path / "work-items" / "active" / slug
    write(item / "status.md", valid_status())
    write(item / "design.md", "# Design\n")
    ledger_text = json.dumps(ledger_event(artifact=f"work-items/active/{slug}/design.md")) + "\n"
    write(item / "agent-runs.jsonl", ledger_text)

    # Sanity: valid while still active.
    pre_move = run_validator(item)
    assert pre_move.returncode == 0, pre_move.stdout

    archived_item = tmp_path / "work-items" / "archive" / "2026-07" / slug
    archived_item.parent.mkdir(parents=True)
    shutil.move(str(item), str(archived_item))
    # The ledger travels with the directory move, untouched byte-for-byte.
    assert (archived_item / "agent-runs.jsonl").read_text(encoding="utf-8") == ledger_text

    result = run_validator(archived_item)

    assert result.returncode == 0, result.stdout
    assert "RESULT: PASS" in result.stdout
    # The move must not have rewritten the ledger's recorded path.
    assert (archived_item / "agent-runs.jsonl").read_text(encoding="utf-8") == ledger_text


def test_stale_active_path_with_no_matching_archive_still_fails(tmp_path: Path) -> None:
    """Regression guard: the archive-fallback must not swallow a genuinely missing
    artifact. If no archive/*/<slug>/ directory contains the recorded tail, the
    PASS gate still fails exactly as before."""
    item = tmp_path / "work-items" / "active" / "missing-artifact-item"
    write(item / "status.md", valid_status())
    write(
        item / "agent-runs.jsonl",
        json.dumps(ledger_event(artifact="work-items/active/missing-artifact-item/design.md")) + "\n",
    )
    # No design.md is ever written, and no archive/ directory exists.

    result = run_validator(item)

    assert result.returncode == 1
    assert "artifact does not exist" in result.stdout


def test_archive_fallback_does_not_match_wrong_slug(tmp_path: Path) -> None:
    """The archive-fallback keeps the same slug segment from the recorded path --
    an artifact recorded under one slug must not resolve against a
    similarly-shaped archived tail that belongs to a different slug."""
    module = load_validator_module()
    other_slug = "some-other-item"
    write(tmp_path / "work-items" / "archive" / "2026-07" / other_slug / "design.md", "# Design\n")

    item = tmp_path / "work-items" / "active" / "missing-artifact-item"
    item.mkdir(parents=True)
    errors: list[str] = []
    resolved = module.resolve_work_item_path(
        item, "work-items/active/missing-artifact-item/design.md", "artifact", "run-001", errors
    )

    assert resolved is None or not resolved.exists()
