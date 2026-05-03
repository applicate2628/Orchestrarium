import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate-work-item-state.py"
CONTRACT_CHECK = ROOT / "scripts" / "check-agent-run-ledger-contract.py"


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


def ledger_event(**overrides):
    event = {
        "schemaVersion": 1,
        "runId": "2026-05-03T14-20-00Z-qa-001",
        "workItem": "agent-execution-tracking",
        "role": "qa-engineer",
        "executionRole": "internal",
        "assignedRole": "qa-engineer",
        "provider": "codex",
        "model": "gpt-5.5-xhigh",
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


def test_schema_contract_check_exercises_validator_negative_cases() -> None:
    result = run_contract_check()

    assert result.returncode == 0, result.stdout
    assert "RESULT: PASS" in result.stdout


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
