#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


STATUS_VALUES = {"planned", "running", "completed", "revise", "blocked", "cancelled"}
GATE_VALUES = {"PASS", "REVISE", "BLOCKED:dependency", "BLOCKED:prerequisite", "RETURN(role)", "advisory", "none"}
EXECUTION_ROLES = {"main", "lead", "internal", "consultant", "external-worker", "external-reviewer", "external-brigade"}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def load_jsonl(path: Path, errors: list[str]) -> list[dict]:
    if not path.exists():
        fail(errors, f"missing ledger: {path}")
        return []
    events = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            fail(errors, f"{path}:{line_no}: invalid JSON: {exc.msg}")
            continue
        if not isinstance(event, dict):
            fail(errors, f"{path}:{line_no}: event must be an object")
            continue
        events.append(event)
    if not events:
        fail(errors, f"ledger has no events: {path}")
    return events


def validate_event(event: dict, item: Path, seen: set[str], errors: list[str]) -> None:
    required = ["schemaVersion", "runId", "workItem", "role", "executionRole", "status", "gate", "scope", "startedAt", "updatedAt"]
    for key in required:
        if key not in event:
            fail(errors, f"event missing required field: {key}")

    run_id = event.get("runId")
    if isinstance(run_id, str):
        if run_id in seen:
            fail(errors, f"duplicate runId: {run_id}")
        seen.add(run_id)

    if event.get("schemaVersion") != 1:
        fail(errors, f"{run_id}: schemaVersion must be 1")
    if event.get("status") not in STATUS_VALUES:
        fail(errors, f"{run_id}: invalid status {event.get('status')!r}")
    if event.get("gate") not in GATE_VALUES:
        fail(errors, f"{run_id}: invalid gate {event.get('gate')!r}")
    if event.get("executionRole") not in EXECUTION_ROLES:
        fail(errors, f"{run_id}: invalid executionRole {event.get('executionRole')!r}")
    if not isinstance(event.get("scope"), list) or not event.get("scope"):
        fail(errors, f"{run_id}: scope must be a non-empty list")

    gate = event.get("gate")
    status = event.get("status")
    artifact = event.get("artifact")
    evidence = event.get("evidence")

    if gate == "PASS":
        if status != "completed":
            fail(errors, f"{run_id}: PASS gate requires completed status")
        if not artifact:
            fail(errors, f"{run_id}: PASS gate requires artifact")
        elif not (item / artifact).exists():
            fail(errors, f"{run_id}: artifact does not exist: {artifact}")
        if not isinstance(evidence, list) or not evidence:
            fail(errors, f"{run_id}: PASS gate requires evidence")

    if gate == "REVISE" and status not in {"revise", "completed"}:
        fail(errors, f"{run_id}: REVISE gate requires revise or completed status")
    if isinstance(gate, str) and gate.startswith("BLOCKED") and status != "blocked":
        fail(errors, f"{run_id}: BLOCKED gate requires blocked status")


def validate_status(item: Path, events: list[dict], errors: list[str]) -> None:
    status_path = item / "status.md"
    if not status_path.exists():
        fail(errors, f"missing status.md: {status_path}")
        return
    text = status_path.read_text(encoding="utf-8")
    for section in ["## Current state", "## Active agents", "## Completed agents", "## Next action"]:
        if section not in text:
            fail(errors, f"status.md missing section: {section}")

    running_events = [event for event in events if event.get("status") == "running"]
    if running_events and "Primary task status**: closed" in text:
        fail(errors, "status.md cannot be closed while ledger has running agents")


def validate_work_item(item: Path) -> list[str]:
    errors: list[str] = []
    events = load_jsonl(item / "agent-runs.jsonl", errors)
    seen: set[str] = set()
    for event in events:
        validate_event(event, item, seen, errors)
    validate_status(item, events, errors)
    return errors


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-item", required=True, help="Path to one work-items/active/<item> directory")
    args = parser.parse_args(argv)

    item = Path(args.work_item).resolve()
    errors = validate_work_item(item)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print(f"RESULT: FAIL ({len(errors)} errors)")
        return 1
    print(f"RESULT: PASS ({item})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
