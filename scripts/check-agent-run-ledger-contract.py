#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


STATUS_TEXT = """---
template: full-delivery
orchestrator: lead
started: 2026-05-03
updated: 2026-05-03 14:24
---

## Current state

- **Primary task**: validate agent run ledger
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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def ledger_event(**updates: object) -> dict[str, object]:
    event: dict[str, object] = {
        "schemaVersion": 1,
        "runId": "2026-05-03T14-20-00Z-qa-001",
        "workItem": "agent-execution-tracking",
        "role": "qa-engineer",
        "executionRole": "internal",
        "status": "completed",
        "gate": "PASS",
        "scope": ["scripts/validate-work-item-state.py"],
        "artifact": "reviews/qa.md",
        "evidence": [{"kind": "command", "ref": "pytest -q", "result": "passed"}],
        "startedAt": "2026-05-03T14:20:00Z",
        "updatedAt": "2026-05-03T14:24:00Z",
    }
    event.update(updates)
    return event


def check_schema(root: Path) -> None:
    schema_path = root / "shared" / "schemas" / "agent-runs.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    props = schema["properties"]
    evidence_items = props["evidence"]["items"]

    require(schema.get("additionalProperties") is False, "schema must reject top-level extra fields")
    require(props["runId"].get("minLength") == 8, "schema must require runId minLength 8")
    require(props["startedAt"].get("minLength") == 10, "schema must require startedAt minLength 10")
    require(props["updatedAt"].get("minLength") == 10, "schema must require updatedAt minLength 10")
    require(evidence_items.get("additionalProperties") is False, "schema must reject extra evidence fields")
    require(set(evidence_items.get("required", [])) == {"kind", "ref"}, "schema must require evidence kind/ref")


def run_validator_case(root: Path, base: Path, name: str, event: dict[str, object], expect_pass: bool, fragments: tuple[str, ...] = ()) -> None:
    item = base / name
    validator = root / "scripts" / "validate-work-item-state.py"
    (item / "reviews").mkdir(parents=True)
    (item / "status.md").write_text(STATUS_TEXT, encoding="utf-8")
    (item / "reviews" / "qa.md").write_text("# QA\n\nGate: PASS\n", encoding="utf-8")
    (item / "agent-runs.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(validator), "--work-item", str(item)],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if expect_pass and proc.returncode != 0:
        raise AssertionError(f"{name} should pass:\n{proc.stdout}")
    if not expect_pass and proc.returncode == 0:
        raise AssertionError(f"{name} should fail:\n{proc.stdout}")
    for fragment in fragments:
        require(fragment in proc.stdout, f"{name} output missed {fragment!r}:\n{proc.stdout}")


def check_validator(root: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        run_validator_case(root, base, "valid", ledger_event(), True)
        run_validator_case(
            root,
            base,
            "extra-evidence-field",
            ledger_event(evidence=[{"kind": "command", "ref": "pytest -q", "extra": "unexpected"}]),
            False,
            ("unexpected field",),
        )
        run_validator_case(
            root,
            base,
            "short-required-strings",
        ledger_event(runId="x", startedAt="1", updatedAt="2"),
        False,
        (
            "runId must be at least 8 characters",
            "startedAt must be at least 10 characters",
            "updatedAt must be at least 10 characters",
        ),
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Orchestrarium repository root")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    check_schema(root)
    check_validator(root)
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
