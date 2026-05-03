#!/usr/bin/env python3
import argparse
import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


def load_validator():
    validator_path = Path(__file__).with_name("validate-work-item-state.py")
    spec = importlib.util.spec_from_file_location("validate_work_item_state", validator_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load validator from {validator_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_time(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def read_events(item: Path) -> list[dict[str, Any]]:
    ledger = item / "agent-runs.jsonl"
    if not ledger.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
    return events


def stale_running_errors(item: Path, now: datetime, stale_after: timedelta) -> list[str]:
    if stale_after.total_seconds() <= 0:
        return []
    errors: list[str] = []
    for event in read_events(item):
        if event.get("status") != "running":
            continue
        run_id = event.get("runId", "<unknown>")
        updated_at = event.get("updatedAt")
        if not isinstance(updated_at, str) or not updated_at.strip():
            errors.append(f"{run_id}: running event has no updatedAt for stale check")
            continue
        try:
            updated = parse_time(updated_at)
        except ValueError as exc:
            errors.append(f"{run_id}: invalid updatedAt for stale check: {exc}")
            continue
        age = now - updated
        if age > stale_after:
            hours = age.total_seconds() / 3600
            errors.append(f"{run_id}: stale running agent ({hours:.1f}h since updatedAt)")
    return errors


def iter_work_items(active_dir: Path) -> list[Path]:
    if not active_dir.exists():
        return []
    return sorted(path for path in active_dir.iterdir() if path.is_dir())


def command_check(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    active_dir = (root / args.active_dir).resolve()
    items = iter_work_items(active_dir)
    if not items:
        print(f"RESULT: PASS (no active work-items: {active_dir})")
        return 0

    validator = load_validator()
    now = parse_time(args.now) if args.now else datetime.now(UTC)
    stale_after = timedelta(hours=args.stale_hours)
    failed = 0

    for item in items:
        errors = validator.validate_work_item(item)
        errors.extend(stale_running_errors(item, now, stale_after))
        label = item.name
        if errors:
            failed += 1
            print(f"FAIL {label}:")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"PASS {label}")

    if failed:
        print(f"RESULT: FAIL ({failed}/{len(items)} active work-items failed)")
        return 1

    print(f"RESULT: PASS ({len(items)} active work-items)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check all active Orchestrarium work-item ledgers.")
    parser.add_argument("--root", type=Path, default=Path("."), help="Repository root. Defaults to the current directory.")
    parser.add_argument(
        "--active-dir",
        default="work-items/active",
        help="Active work-item directory relative to --root. Defaults to work-items/active.",
    )
    parser.add_argument(
        "--stale-hours",
        type=float,
        default=0.0,
        help="Report running events older than this many hours. Use 0 to disable stale checks.",
    )
    parser.add_argument("--now", help="UTC-ish timestamp for deterministic stale checks. Defaults to current UTC.")
    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return command_check(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
