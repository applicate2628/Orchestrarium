import importlib.util
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate-work-item-state.py"
CONTRACT_CHECK = ROOT / "scripts" / "check-agent-run-ledger-contract.py"


def load_validator_module():
    spec = importlib.util.spec_from_file_location("validate_work_item_state_direct", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_contract_check_module():
    spec = importlib.util.spec_from_file_location("agent_run_ledger_contract_direct", CONTRACT_CHECK)
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


def minimal_staged_status() -> str:
    return """---
template: staged
status: active
started: 2026-07-31T00:00:00Z
updated: 2026-07-31T00:00:00Z
---

Task: Keep the staged ledger contract strict.
Current step: Validate the ledger.
Last result: Candidate created.
Next action: Run the lifecycle oracle.
Scope boundary: State validator only.
Owner: qa-engineer
Integration owner: qa-engineer
Evidence gate: focused validator test
Reopens: 2026-07-30-predecessor
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


def solution_capsule() -> dict:
    return {
        "version": 1,
        "declarationSetId": "declaration-one",
        "objects": [
            {
                "decisionObjectId": "object-one",
                "mutationSurfaces": ["scripts/example.py"],
                "solutionClasses": ["class-one"],
                "initialClassId": "class-one",
                "initialAttemptId": "attempt-one",
                "guardIds": [
                    "mutation-surface-subset",
                    "no-new-dependency",
                    "no-new-contract-risk-owner",
                    "forbidden-mechanism-tag",
                    "required-oracle",
                    "item-specific-stop",
                ],
            }
        ],
        "baseline": "b" * 64,
        "author": "accepted-admission-run",
    }


def v3_event(**overrides) -> dict:
    event = {
        "schemaVersion": 3,
        "eventId": "solution-event-0001",
        "operationId": "solution-operation-0001",
        "fingerprint": "1" * 64,
        "priorHead": "GENESIS",
        "recordedAt": "2026-08-13T07:30:00Z",
        "eventType": "solution-bootstrap",
        "payload": {"capsule": solution_capsule()},
    }
    event.update(overrides)
    return event


def test_staged_missing_and_empty_ledgers_remain_invalid(tmp_path: Path) -> None:
    for name, ledger_text, diagnostic in (
        ("missing", None, "missing ledger"),
        ("empty", "", "ledger has no events"),
    ):
        item = tmp_path / "work-items" / "active" / f"staged-{name}-ledger"
        write(item / "status.md", minimal_staged_status())
        if ledger_text is not None:
            write(item / "agent-runs.jsonl", ledger_text)

        result = run_validator(item)

        assert result.returncode == 1
        assert diagnostic in result.stdout


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


def test_quick_fix_status_exact_fixture(tmp_path: Path) -> None:
    validator = load_validator_module()
    item = tmp_path / "work-items" / "active" / "quick-fix-exact"
    write(item / "status.md", minimal_quick_fix_status())

    assert validator.validate_work_item(item) == []

    write(
        item / "status.md",
        minimal_quick_fix_status().replace(
            "updated: 2026-07-30 10:00\n",
            "updated: 2026-07-30 10:00\nowner: lead\n",
            1,
        ),
    )
    errors = validator.validate_work_item(item)
    assert "quick-fix status.md unexpected lifecycle field: owner" in errors


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


def test_agent_run_schema_is_valid_draft_2020_12() -> None:
    schema = json.loads(
        (ROOT / "shared" / "schemas" / "agent-runs.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)


def test_scratch_evidence_schema_activates_declared_proof_polarity() -> None:
    schema = json.loads(
        (ROOT / "shared" / "schemas" / "agent-runs.schema.json").read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema["properties"]["scratchEvidence"]["items"])
    base = {
        "entryId": "entry-one",
        "path": ".scratch/work-items/item/run/entry-one",
        "reason": "bounded evidence",
        "canonicalPointer": "implementation.md",
    }
    retain = {**base, "disposition": "retain"}
    delete = {
        **base,
        "disposition": "delete",
        "proof": {"kind": "git-object-set"},
    }
    assert list(validator.iter_errors(retain)) == []
    assert list(validator.iter_errors(delete)) == []
    assert list(validator.iter_errors({**retain, "proof": {"kind": "git-object-set"}}))
    missing_proof = dict(delete)
    missing_proof.pop("proof")
    assert list(validator.iter_errors(missing_proof))


def test_agent_run_schema_discriminates_legacy_and_v3_shapes() -> None:
    schema = json.loads(
        (ROOT / "shared" / "schemas" / "agent-runs.schema.json").read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema)
    legacy_v1 = ledger_event()
    legacy_v2 = ledger_event(schemaVersion=2, eventKind="standalone")
    control_v3 = v3_event()
    assert list(validator.iter_errors(legacy_v1)) == []
    assert list(validator.iter_errors(legacy_v2)) == []
    assert list(validator.iter_errors(control_v3)) == []
    assert list(validator.iter_errors({**legacy_v1, "eventId": "mixed-shape"}))
    assert list(validator.iter_errors({**control_v3, "runId": "mixed-shape-run"}))
    assert "legacy-obligation-migration" in schema["properties"]["eventKind"]["enum"]
    assert "legacy-unclassified" in schema["properties"]["findingClass"]["enum"]
    assert "replacementEvent" in schema["properties"]


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


def test_expand_contract_and_reader_floor(tmp_path: Path) -> None:
    validator = load_validator_module()
    item = tmp_path / "work-items" / "active" / "reader-floor"
    write(item / "status.md", valid_status())
    write(item / "reviews" / "qa.md", "# QA\n\nGate: PASS\n")

    v1 = ledger_event(runId="reader-floor-v1-0001")
    v2_revise = ledger_event(
        schemaVersion=2,
        runId="reader-floor-v2-revise-0001",
        status="revise",
        gate="REVISE",
        eventKind="standalone",
        lane="correctness",
        effort="high",
        findingClass="correctness",
    )
    v2_closer = ledger_event(
        schemaVersion=2,
        runId="reader-floor-v2-closer-0001",
        eventKind="standalone",
        closesRunIds=["reader-floor-v2-revise-0001"],
        lane="correctness",
        effort="high",
    )
    v3 = v3_event()
    lines = [v1, v2_revise, v2_closer, v3]
    write(item / "agent-runs.jsonl", "".join(json.dumps(row) + "\n" for row in lines))

    result = run_validator(item)
    assert result.returncode == 0, result.stdout
    assert "RESULT: PASS" in result.stdout

    events = validator.load_jsonl(item / "agent-runs.jsonl", [])
    state, errors = validator.reduce_v3_events(events)
    assert errors == []
    assert state is not None
    assert state["declarationSetId"] == "declaration-one"
    assert state["head"] == "1" * 64

    closure_errors: list[str] = []
    validity = validator.derive_event_validity(events, item, closure_errors)
    open_revise, _ = validator.validate_closure(
        events,
        closure_errors,
        event_validity=validity,
    )
    assert closure_errors == []
    assert open_revise == []


def test_v3_duplicate_unknown_and_malformed_fields_fail_closed(tmp_path: Path) -> None:
    item = tmp_path / "work-items" / "active" / "v3-negative"
    write(item / "status.md", valid_status())
    cases = {
        "duplicate": json.dumps(v3_event()).replace(
            '"schemaVersion": 3,',
            '"schemaVersion": 3, "schemaVersion": 3,',
            1,
        ),
        "unknown": json.dumps(v3_event(unexpected="field")),
        "bad-fingerprint": json.dumps(v3_event(fingerprint="not-a-digest")),
        "bad-prior-head": json.dumps(v3_event(priorHead="guess-the-head")),
        "bad-event-type": json.dumps(v3_event(eventType="heuristic-retry")),
    }
    expected = {
        "duplicate": "duplicate JSON key",
        "unknown": "unexpected V3 field",
        "bad-fingerprint": "fingerprint must be 64 lowercase hex characters",
        "bad-prior-head": "priorHead must be GENESIS or 64 lowercase hex characters",
        "bad-event-type": "invalid eventType",
    }
    for name, raw in cases.items():
        write(item / "agent-runs.jsonl", raw + "\n")
        result = run_validator(item)
        assert result.returncode == 1, (name, result.stdout)
        assert expected[name] in result.stdout, (name, result.stdout)


def test_v3_decoder_enforces_utf8_depth_and_event_count_bounds(tmp_path: Path) -> None:
    validator = load_validator_module()
    with pytest.raises(ValueError, match="maximum raw UTF-8 length"):
        validator.decode_json_object(
            json.dumps({"value": "\u00e9" * 20}),
            source="v3-byte-bound",
            maximum_bytes=20,
        )
    deep: object = "leaf"
    for _ in range(validator.MAX_JSON_NESTING_DEPTH + 1):
        deep = {"nested": deep}
    with pytest.raises(ValueError, match="nesting exceeds"):
        validator.decode_json_object(json.dumps(deep), source="v3-depth-bound")

    item = tmp_path / "work-items" / "active" / "v3-count-bound"
    write(item / "status.md", valid_status())
    repeated = json.dumps(v3_event()) + "\n"
    write(
        item / "agent-runs.jsonl",
        repeated * (validator.MAX_LEDGER_EVENTS + 1),
    )
    result = run_validator(item)
    assert result.returncode == 1
    assert "ledger exceeds bounded event count" in result.stdout


def test_raw_v1_v2_are_readable_but_do_not_create_v3_authorization() -> None:
    validator = load_validator_module()
    events = [
        ledger_event(runId="legacy-readable-v1-0001"),
        ledger_event(
            schemaVersion=2,
            runId="legacy-readable-v2-0001",
            eventKind="standalone",
        ),
    ]
    state, errors = validator.reduce_v3_events(events)
    assert errors == []
    assert state is None


def test_old_writer_refuses_v3_without_down_conversion_or_byte_change(tmp_path: Path) -> None:
    item = tmp_path / "work-items" / "active" / "old-writer-v3-refusal"
    write(item / "status.md", valid_status())
    original = json.dumps(v3_event(), sort_keys=True, separators=(",", ":")) + "\n"
    write(item / "agent-runs.jsonl", original)
    command = [
        sys.executable,
        str(ROOT / "scripts" / "agent-run-ledger.py"),
        "--work-item",
        str(item),
        "append",
        "--run-id",
        "legacy-writer-attempt-0001",
        "--role",
        "qa-engineer",
        "--execution-role",
        "internal",
        "--status",
        "blocked",
        "--gate",
        "BLOCKED:dependency",
        "--scope",
        "reader-floor",
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert result.returncode == 1, result.stdout
    assert "legacy V1/V2 writer refuses a ledger containing schemaVersion 3" in result.stdout
    assert (item / "agent-runs.jsonl").read_text(encoding="utf-8") == original
    assert not (item / "agent-runs.jsonl.tmp").exists()


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


def test_ledger_closure_archive_fixture(tmp_path: Path) -> None:
    slug = "ledger-closure-archive"
    item = tmp_path / "work-items" / "active" / slug
    write(item / "status.md", valid_status())
    write(item / "design.md", "# Design\n")
    ledger_text = json.dumps(
        ledger_event(artifact=f"work-items/active/{slug}/design.md")
    ) + "\n"
    write(item / "agent-runs.jsonl", ledger_text)
    archived = tmp_path / "work-items" / "archive" / "2026-07" / slug
    archived.parent.mkdir(parents=True)
    shutil.move(str(item), str(archived))

    result = run_validator(archived)

    assert result.returncode == 0, result.stdout
    assert (archived / "agent-runs.jsonl").read_text(encoding="utf-8") == ledger_text

    unsettled = tmp_path / "work-items" / "active" / "unsettled-revise"
    write(unsettled / "status.md", valid_status())
    write(unsettled / "reviews" / "qa.md", "# QA\n")
    revise = ledger_event(
        schemaVersion=2,
        runId="unsettled-revise-run",
        status="revise",
        gate="REVISE",
        eventKind="standalone",
        findingClass="correctness",
    )
    write(unsettled / "agent-runs.jsonl", json.dumps(revise) + "\n")
    rejected = run_validator(unsettled)
    assert rejected.returncode == 1
    assert "open REVISE obligation" in rejected.stdout


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


def test_closure_recovery_post_first_use_reader_floor(tmp_path: Path) -> None:
    fixture = ROOT / "tests" / "fixtures" / "agent-run-ledger" / "closure-invalidation-v2"
    item = tmp_path / "work-items" / "active" / "closure-invalidation-v2"
    shutil.copytree(fixture, item)
    result = run_validator(item)
    expected = json.loads((fixture / "expected.json").read_text(encoding="utf-8"))
    assert result.returncode == 0, result.stdout
    assert expected["openRevise"] == 0 and expected["openLaunches"] == 0


def test_model_ranking_migration_boundary_and_sibling_inventory(tmp_path: Path) -> None:
    fixture = ROOT / "tests" / "fixtures" / "agent-run-ledger" / "closure-invalidation-v2"
    item = tmp_path / "work-items" / "active" / "closure-invalidation-v2"
    shutil.copytree(fixture, item)
    lines = (item / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines]
    events[1]["findingClass"] = "inline-sufficient"
    target_line = json.dumps(events[1], ensure_ascii=False, separators=(",", ":"))
    target_digest = hashlib.sha256(target_line.encode()).hexdigest()
    events[2]["invalidatesEventSha256"] = target_digest
    events[2]["evidence"] = [{"kind": "manual-check", "ref": f"fixture-invalid-closer {target_digest}"}]
    (item / "agent-runs.jsonl").write_text("\n".join(json.dumps(event, ensure_ascii=False, separators=(",", ":")) for event in events) + "\n", encoding="utf-8", newline="")
    result = run_validator(item)
    assert result.returncode != 0
    assert "ledger-recovery:target-per-event-invalid" in result.stdout
    assert "inline-sufficient" in result.stdout


def test_closure_recovery_schema_contract_runbook_and_rollup_parity(tmp_path: Path) -> None:
    schema = json.loads((ROOT / "shared" / "schemas" / "agent-runs.schema.json").read_text(encoding="utf-8"))
    assert "closure-invalidation" in schema["properties"]["eventKind"]["enum"]
    assert "invalidatesRunId" in schema["properties"]
    assert "invalidatesEventSha256" in schema["properties"]
    result = run_contract_check()
    assert result.returncode == 0, result.stdout
    assert result.stdout.rstrip().endswith("RESULT: PASS")

    checker = load_contract_check_module()
    relative_paths = [
        "docs/work-item-execution-tracking.md",
        *checker.RECOVERY_POINTERS,
    ]

    def copy_documentation(destination: Path) -> None:
        for relative in relative_paths:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)

    for index, token in enumerate(checker.RECOVERY_RUNBOOK_TOKENS):
        case = tmp_path / f"missing-token-{index}"
        copy_documentation(case)
        runbook = case / "docs" / "work-item-execution-tracking.md"
        runbook.write_text(runbook.read_text(encoding="utf-8").replace(token, ""), encoding="utf-8")
        with pytest.raises(AssertionError, match="recovery runbook"):
            checker.check_recovery_documentation(case)

    for index, (relative, pointer) in enumerate(checker.RECOVERY_POINTERS.items()):
        missing_link = tmp_path / f"missing-link-{index}"
        copy_documentation(missing_link)
        pointer_path = missing_link / relative
        pointer_path.write_text(pointer_path.read_text(encoding="utf-8").replace(pointer, ""), encoding="utf-8")
        with pytest.raises(AssertionError, match="must point"):
            checker.check_recovery_documentation(missing_link)

        duplicate_procedure = tmp_path / f"duplicate-procedure-{index}"
        copy_documentation(duplicate_procedure)
        duplicate_path = duplicate_procedure / relative
        duplicate_path.write_text(
            duplicate_path.read_text(encoding="utf-8") + "\n```text\nrecover-invalid-closure\n```\n",
            encoding="utf-8",
        )
        with pytest.raises(AssertionError, match="must not duplicate"):
            checker.check_recovery_documentation(duplicate_procedure)


def _historical_implementation_lane_receipts() -> Path:
    """Optional local historical evidence, not fresh product execution coverage."""
    root = ROOT / ".scratch" / "work-items" / "2026-08-17-fix-append-only-invalid-ledger-event-recovery" / "lead-append-only-scratch-retain-20260821-r1-terminal" / "implementation-lane-baseline"
    if not root.exists():
        raise unittest.SkipTest(
            "optional 2026-08-21 implementation-lane receipts are absent from this checkout"
        )
    return root


def test_implementation_lane_replays_dirty_declared_producer_delta() -> None:
    root = _historical_implementation_lane_receipts()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schemaVersion"] == 2
    assert len(manifest["entries"]) == 77
    assert len(manifest["declaredPaths"]["paths"]) == 13
    assert manifest["exclusiveLane"]["producerWriteObserved"] is False
    probes = json.loads((root / "negative-probes.json").read_text(encoding="utf-8"))
    assert len(probes["results"]) == 7
    assert {row["failureId"] for row in probes["results"]} == {"lane-evidence:path", "lane-evidence:cap", "lane-evidence:identity", "lane-evidence:corrupt", "lane-evidence:baseline-drift"}
    assert probes["producerWrites"] == 0


def test_implementation_lane_forbids_external_side_effects() -> None:
    root = _historical_implementation_lane_receipts()
    commands = json.loads((root / "commands.jsonl").read_text(encoding="utf-8"))
    processes = json.loads((root / "process-network-attempts.jsonl").read_text(encoding="utf-8"))
    call_path = json.loads((root / "call-path-observation.json").read_text(encoding="utf-8"))
    assert len(commands["deniedClasses"]) == 12
    assert commands["forbiddenAttempts"] == []
    assert processes["networkAttempts"] == processes["forbiddenAttempts"] == processes["activePids"] == []
    assert call_path["forbiddenEdges"] == []
    assert call_path["claimBoundary"] == "no claim about arbitrary unobserved installed/runtime state"


class _UnittestAdapter(unittest.TestCase):
    """Run existing pytest-style functions under the plan's unittest CLI."""


def _adapt_test(function):
    def method(self):
        if function.__code__.co_argcount == 0:
            function()
            return
        with tempfile.TemporaryDirectory() as directory:
            function(Path(directory))

    method.__name__ = function.__name__
    return method


_PYTEST_ONLY_RECOVERY_TESTS = {
    "test_closure_recovery_post_first_use_reader_floor",
    "test_model_ranking_migration_boundary_and_sibling_inventory",
    "test_closure_recovery_schema_contract_runbook_and_rollup_parity",
    "test_implementation_lane_replays_dirty_declared_producer_delta",
    "test_implementation_lane_forbids_external_side_effects",
}

for _name, _function in tuple(globals().items()):
    if _name.startswith("test_") and _name not in _PYTEST_ONLY_RECOVERY_TESTS and callable(_function):
        setattr(_UnittestAdapter, _name, _adapt_test(_function))
