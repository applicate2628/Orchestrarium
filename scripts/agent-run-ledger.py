#!/usr/bin/env python3
import argparse
import importlib.util
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


STATUS_SECTIONS = {
    "## Current state": lambda args: "\n".join(
        [
            "**Primary task status**: open",
            f"Primary task: {args.primary_task}",
            f"Current stage: {args.stage}",
        ]
    ),
    "## Active agents": lambda _args: "- none",
    "## Completed agents": lambda _args: "- none",
    "## Next action": lambda _args: "Append the next agent run event.",
}


def load_validator():
    validator_path = Path(__file__).with_name("validate-work-item-state.py")
    spec = importlib.util.spec_from_file_location("validate_work_item_state", validator_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load validator from {validator_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_run_id(role: str) -> str:
    safe_role = re.sub(r"[^a-zA-Z0-9-]+", "-", role).strip("-") or "agent"
    return f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}-{safe_role}"


def parse_evidence(value: str) -> dict[str, str]:
    if ":" not in value:
        raise ValueError("--evidence must use KIND:REF")
    kind, ref = value.split(":", 1)
    return {"kind": kind.strip(), "ref": ref.strip()}


def parse_evidence_json(value: str) -> dict[str, Any]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("--evidence-json must be a JSON object")
    return parsed


def ensure_status_sections(item: Path, args: argparse.Namespace) -> None:
    status_path = item / "status.md"
    if status_path.exists():
        text = status_path.read_text(encoding="utf-8")
    else:
        text = "# Status\n"

    additions: list[str] = []
    for heading, body_factory in STATUS_SECTIONS.items():
        if heading not in text:
            additions.append(f"{heading}\n{body_factory(args)}\n")

    if additions:
        separator = "\n" if text.endswith("\n") else "\n\n"
        text = text + separator + "\n".join(additions)
        if not text.endswith("\n"):
            text += "\n"
        status_path.write_text(text, encoding="utf-8")


def build_event(args: argparse.Namespace) -> dict[str, Any]:
    started_at = args.started_at or utc_timestamp()
    updated_at = args.updated_at or started_at
    event: dict[str, Any] = {
        "schemaVersion": 1,
        "runId": args.run_id or default_run_id(args.role),
        "workItem": args.work_item_name or args.work_item.name,
        "role": args.role,
        "executionRole": args.execution_role,
        "status": args.status,
        "gate": args.gate,
        "scope": args.scope,
        "startedAt": started_at,
        "updatedAt": updated_at,
    }

    optional_fields = {
        "assignedRole": args.assigned_role,
        "provider": args.provider,
        "model": args.model,
        "promptFile": args.prompt_file,
        "artifact": args.artifact,
        "notes": args.notes,
    }
    for key, value in optional_fields.items():
        if value is not None:
            event[key] = value

    evidence: list[dict[str, Any]] = []
    for value in args.evidence or []:
        evidence.append(parse_evidence(value))
    for value in args.evidence_json or []:
        evidence.append(parse_evidence_json(value))
    if evidence:
        event["evidence"] = evidence

    return event


def restore_ledger(path: Path, previous: str | None) -> None:
    if previous is None:
        if path.exists():
            path.unlink()
    else:
        path.write_text(previous, encoding="utf-8")


def command_init(args: argparse.Namespace) -> int:
    item = args.work_item.resolve()
    item.mkdir(parents=True, exist_ok=True)
    ensure_status_sections(item, args)
    (item / "agent-runs.jsonl").touch(exist_ok=True)
    print(f"RESULT: PASS init ({item})")
    return 0


def command_append(args: argparse.Namespace) -> int:
    item = args.work_item.resolve()
    if not item.exists():
        print(f"FAIL: missing work item: {item}", file=sys.stderr)
        return 1

    try:
        event = build_event(args)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    ledger_path = item / "agent-runs.jsonl"
    previous = ledger_path.read_text(encoding="utf-8") if ledger_path.exists() else None
    prefix = "" if not previous or previous.endswith("\n") else "\n"
    line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    ledger_path.write_text(f"{previous or ''}{prefix}{line}\n", encoding="utf-8")

    validator = load_validator()
    errors = validator.validate_work_item(item)
    if errors:
        restore_ledger(ledger_path, previous)
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        print(f"RESULT: FAIL ({len(errors)} errors)", file=sys.stderr)
        return 1

    print(f"RESULT: PASS append ({ledger_path})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialize and append Orchestrarium agent-run ledger events.")
    parser.add_argument("--work-item", required=True, type=Path, help="Path to one work-items/active/<item> directory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Create missing status sections and an empty agent-runs.jsonl")
    init.add_argument("--primary-task", default="Unspecified.", help="Primary task text for a new or migrated status.md")
    init.add_argument("--stage", default="Unspecified.", help="Current stage text for a new or migrated status.md")
    init.set_defaults(func=command_init)

    append = subparsers.add_parser("append", help="Append one validated event to agent-runs.jsonl")
    append.add_argument("--run-id", help="Stable unique run identifier. Defaults to timestamp plus role.")
    append.add_argument("--work-item-name", help="Ledger workItem value. Defaults to the work-item directory name.")
    append.add_argument("--role", required=True, help="Actual role that produced the event.")
    append.add_argument("--execution-role", required=True, help="Execution role accepted by validate-work-item-state.py.")
    append.add_argument("--assigned-role", help="Assigned or replaced internal role, when applicable.")
    append.add_argument("--provider", help="Requested or resolved external provider, when applicable.")
    append.add_argument("--model", help="Model or profile used, when known.")
    append.add_argument("--status", required=True, help="Agent run status.")
    append.add_argument("--gate", required=True, help="Gate verdict.")
    append.add_argument("--scope", action="append", required=True, help="Scoped file, artifact, or responsibility. Repeatable.")
    append.add_argument("--prompt-file", help="Prompt file path, when a provider-backed launch used one.")
    append.add_argument("--artifact", help="Artifact path relative to the work item.")
    append.add_argument("--evidence", action="append", help="Evidence in KIND:REF form. Repeatable.")
    append.add_argument("--evidence-json", action="append", help="Evidence as a JSON object. Repeatable.")
    append.add_argument("--started-at", help="ISO-like start timestamp. Defaults to current UTC.")
    append.add_argument("--updated-at", help="ISO-like update timestamp. Defaults to started-at.")
    append.add_argument("--notes", help="Short operational note.")
    append.set_defaults(func=command_append)
    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
