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


# Legacy executionRole values are READ-mapped by the validator (old ledgers keep
# validating) but must never be WRITTEN into a new event — the retired
# main|lead duality would otherwise resurface on the wire. Mirrors
# scripts/validate-work-item-state.py LEGACY_EXECUTION_ROLES.
LEGACY_EXECUTION_ROLES = {"lead": "main"}


def build_event(args: argparse.Namespace) -> dict[str, Any]:
    if args.execution_role in LEGACY_EXECUTION_ROLES:
        canonical = LEGACY_EXECUTION_ROLES[args.execution_role]
        raise ValueError(
            f"--execution-role {args.execution_role!r} is a retired legacy value; "
            f"new events must use {canonical!r} (the one main-conversation identity — "
            "orchestration weight belongs in status.md 'orchestration:', not here)"
        )
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


def _read_ledger(item: Path) -> tuple[list[dict[str, Any]], int]:
    """Return (events, malformed_line_count). A corrupt or non-object JSONL line
    is skipped but COUNTED so the rollup can surface it — an audit surface
    (evidence coverage) must not silently under-count corrupt input."""
    ledger = item / "agent-runs.jsonl"
    events: list[dict[str, Any]] = []
    malformed = 0
    if not ledger.exists():
        return events, malformed
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
        else:
            malformed += 1
    return events, malformed


def _iter_active_items(active_dir: Path) -> list[Path]:
    if not active_dir.is_dir():
        return []
    return sorted(path for path in active_dir.iterdir() if path.is_dir())


def command_init(args: argparse.Namespace) -> int:
    if args.work_item is None:
        print("FAIL: init requires --work-item", file=sys.stderr)
        return 1
    item = args.work_item.resolve()
    item.mkdir(parents=True, exist_ok=True)
    ensure_status_sections(item, args)
    (item / "agent-runs.jsonl").touch(exist_ok=True)
    print(f"RESULT: PASS init ({item})")
    return 0


def command_append(args: argparse.Namespace) -> int:
    if args.work_item is None:
        print("FAIL: append requires --work-item", file=sys.stderr)
        return 1
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


def _fmt_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "(none)"


def command_rollup(args: argparse.Namespace) -> int:
    """Aggregate agent-runs.jsonl events for one work-item (--work-item) or across
    all active items (--root). Read-only summary; never mutates a ledger."""
    if args.work_item is not None:
        items = [args.work_item.resolve()]
    else:
        active_dir = (args.root.resolve() / args.active_dir).resolve()
        items = _iter_active_items(active_dir)

    total = 0
    malformed_total = 0
    by_role: dict[str, int] = {}
    by_execution_role: dict[str, int] = {}
    by_gate: dict[str, int] = {}
    by_status: dict[str, int] = {}
    with_evidence = 0
    per_item: list[tuple[str, int]] = []

    for item in items:
        events, malformed = _read_ledger(item)
        malformed_total += malformed
        per_item.append((item.name, len(events)))
        for event in events:
            total += 1
            for field, bucket in (
                ("role", by_role),
                ("executionRole", by_execution_role),
                ("gate", by_gate),
                ("status", by_status),
            ):
                key = str(event.get(field, "<none>"))
                if field == "executionRole":
                    # legacy read-mapping (lead -> main): ONE owner must roll up
                    # into ONE audit bucket even across pre-rename ledger lines
                    key = LEGACY_EXECUTION_ROLES.get(key, key)
                bucket[key] = bucket.get(key, 0) + 1
            evidence = event.get("evidence")
            if isinstance(evidence, list) and evidence:
                with_evidence += 1

    if args.json:
        print(json.dumps(
            {
                "items": len(items),
                "totalRuns": total,
                "byRole": by_role,
                "byExecutionRole": by_execution_role,
                "byGate": by_gate,
                "byStatus": by_status,
                "evidenceCoverage": {"withEvidence": with_evidence, "total": total},
                "malformedLines": malformed_total,
                "perItem": dict(per_item),
            },
            ensure_ascii=False, indent=2,
        ))
        return 0

    scope = items[0].name if (args.work_item is not None and items) else f"{len(items)} active items"
    print(f"=== agent-run ledger rollup ({scope}) ===")
    print(f"total runs: {total}")
    print(f"by role: {_fmt_counts(by_role)}")
    print(f"by execution-role: {_fmt_counts(by_execution_role)}")
    print(f"by gate: {_fmt_counts(by_gate)}")
    print(f"by status: {_fmt_counts(by_status)}")
    print(f"evidence coverage: {with_evidence}/{total}")
    print(f"malformed lines: {malformed_total}")
    if args.work_item is None and per_item:
        print("per-item runs: " + ", ".join(f"{name}={count}" for name, count in per_item))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialize, append, and roll up Orchestrarium agent-run ledger events.")
    parser.add_argument(
        "--work-item",
        type=Path,
        help="Path to one work-items/active/<item> directory. Required for init/append; optional for rollup (omit to roll up all active items via --root).",
    )
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

    rollup = subparsers.add_parser("rollup", help="Aggregate ledger events (one work-item via --work-item, or all active via --root)")
    rollup.add_argument("--root", type=Path, default=Path("."), help="Repository root for an all-active rollup (when --work-item is omitted).")
    rollup.add_argument("--active-dir", default="work-items/active", help="Active dir relative to --root. Defaults to work-items/active.")
    rollup.add_argument("--json", action="store_true", help="Emit the rollup as JSON instead of a human-readable summary.")
    rollup.set_defaults(func=command_rollup)
    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
