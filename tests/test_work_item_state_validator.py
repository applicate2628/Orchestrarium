import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate-work-item-state.py"


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
        "model": "gpt-5.4-xhigh",
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


def test_pass_without_evidence_fails(tmp_path: Path) -> None:
    item = tmp_path / "work-items" / "active" / "agent-execution-tracking"
    write(item / "status.md", valid_status())
    write(item / "reviews" / "qa.md", "# QA\n\nGate: PASS\n")
    write(item / "agent-runs.jsonl", json.dumps(ledger_event(evidence=[])) + "\n")

    result = run_validator(item)

    assert result.returncode == 1
    assert "PASS gate requires evidence" in result.stdout
