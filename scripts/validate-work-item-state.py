#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path


STATUS_VALUES = {"planned", "running", "completed", "revise", "blocked", "cancelled"}
GATE_VALUES = {"PASS", "REVISE", "BLOCKED:dependency", "BLOCKED:prerequisite", "advisory", "none"}
EXECUTION_ROLES = {"main", "lead", "internal", "consultant", "external-worker", "external-reviewer", "external-brigade"}
EVIDENCE_KINDS = {"command", "artifact", "visual", "review", "manual-check", "log"}
RETURN_GATE_RE = re.compile(r"^RETURN\([a-z][a-z-]*\)$")
MIN_LENGTHS = {
    "runId": 8,
    "workItem": 1,
    "role": 1,
    "startedAt": 10,
    "updatedAt": 10,
}
ALLOWED_FIELDS = {
    "schemaVersion",
    "runId",
    "workItem",
    "role",
    "executionRole",
    "assignedRole",
    "provider",
    "model",
    "status",
    "gate",
    "scope",
    "promptFile",
    "artifact",
    "evidence",
    "startedAt",
    "updatedAt",
    "notes",
}
EVIDENCE_ALLOWED_FIELDS = {"kind", "ref", "result"}


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


def resolve_work_item_path(item: Path, value: object, label: str, run_id: object, errors: list[str]) -> Path | None:
    if not isinstance(value, str):
        fail(errors, f"{run_id}: {label} must be a string")
        return None
    if not value.strip():
        fail(errors, f"{run_id}: {label} must be a non-empty relative path")
        return None

    candidate = Path(value)
    if candidate.is_absolute():
        fail(errors, f"{run_id}: {label} must be relative to the work item: {value}")
        return None

    item_root = item.resolve()
    resolved = (item_root / candidate).resolve()
    if resolved != item_root and item_root not in resolved.parents:
        fail(errors, f"{run_id}: {label} escapes the work item: {value}")
        return None

    return resolved


def validate_evidence(evidence: object, run_id: object, errors: list[str], require_non_empty: bool) -> None:
    if not isinstance(evidence, list):
        fail(errors, f"{run_id}: evidence must be a list")
        return
    if not evidence:
        if require_non_empty:
            fail(errors, f"{run_id}: PASS gate requires evidence")
        return

    for index, entry in enumerate(evidence, start=1):
        if not isinstance(entry, dict):
            fail(errors, f"{run_id}: evidence[{index}] must be an object")
            continue
        for key in sorted(set(entry) - EVIDENCE_ALLOWED_FIELDS):
            fail(errors, f"{run_id}: evidence[{index}] has unexpected field: {key}")
        if entry.get("kind") not in EVIDENCE_KINDS:
            fail(errors, f"{run_id}: evidence[{index}] has invalid kind {entry.get('kind')!r}")
        if not isinstance(entry.get("ref"), str) or not entry.get("ref", "").strip():
            fail(errors, f"{run_id}: evidence[{index}] requires ref")
        if "result" in entry and not isinstance(entry.get("result"), str):
            fail(errors, f"{run_id}: evidence[{index}].result must be a string")


def validate_event(event: dict, item: Path, seen: set[str], errors: list[str]) -> None:
    required = ["schemaVersion", "runId", "workItem", "role", "executionRole", "status", "gate", "scope", "startedAt", "updatedAt"]
    for key in required:
        if key not in event:
            fail(errors, f"event missing required field: {key}")

    for key in sorted(set(event) - ALLOWED_FIELDS):
        fail(errors, f"unexpected field: {key}")

    run_id = event.get("runId")
    if isinstance(run_id, str):
        if run_id in seen:
            fail(errors, f"duplicate runId: {run_id}")
        seen.add(run_id)
    else:
        fail(errors, f"{run_id}: runId must be a string")

    if event.get("schemaVersion") != 1:
        fail(errors, f"{run_id}: schemaVersion must be 1")
    for key, min_length in MIN_LENGTHS.items():
        value = event.get(key)
        if not isinstance(value, str) or not value.strip():
            fail(errors, f"{run_id}: {key} must be a non-empty string")
        elif len(value) < min_length:
            fail(errors, f"{run_id}: {key} must be at least {min_length} characters")
    for key in ["assignedRole", "provider", "model", "promptFile", "notes"]:
        if key in event and not isinstance(event.get(key), str):
            fail(errors, f"{run_id}: {key} must be a string")
    if event.get("status") not in STATUS_VALUES:
        fail(errors, f"{run_id}: invalid status {event.get('status')!r}")
    gate = event.get("gate")
    if not isinstance(gate, str) or (gate not in GATE_VALUES and not RETURN_GATE_RE.fullmatch(gate)):
        fail(errors, f"{run_id}: invalid gate {event.get('gate')!r}")
    if event.get("executionRole") not in EXECUTION_ROLES:
        fail(errors, f"{run_id}: invalid executionRole {event.get('executionRole')!r}")
    if not isinstance(event.get("scope"), list) or not event.get("scope"):
        fail(errors, f"{run_id}: scope must be a non-empty list")
    elif any(not isinstance(scope, str) or not scope.strip() for scope in event["scope"]):
        fail(errors, f"{run_id}: scope items must be non-empty strings")

    status = event.get("status")
    artifact = event.get("artifact")
    evidence = event.get("evidence")

    artifact_path = None
    if artifact:
        artifact_path = resolve_work_item_path(item, artifact, "artifact", run_id, errors)
    elif "artifact" in event and not isinstance(artifact, str):
        fail(errors, f"{run_id}: artifact must be a string")

    if evidence is not None:
        validate_evidence(evidence, run_id, errors, gate == "PASS")

    if gate == "PASS":
        if status != "completed":
            fail(errors, f"{run_id}: PASS gate requires completed status")
        if not artifact:
            fail(errors, f"{run_id}: PASS gate requires artifact")
        if artifact_path is not None and not artifact_path.exists():
            fail(errors, f"{run_id}: artifact does not exist: {artifact}")
        if evidence is None:
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
