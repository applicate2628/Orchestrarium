#!/usr/bin/env python3
import argparse
import importlib.util
import json
import re
import sys
from datetime import UTC, date, datetime, timedelta
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


DIR_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-")
SLUG_RE = re.compile(r"^[A-Za-z0-9][\w.-]*$")
DONE_STATE_LINE_RE = re.compile(
    r"(?im)^\s*>?\s*\*{0,3}\s*(?:current\s+)?(?:state|status|stage|outcome)"
    r"\s*\*{0,3}\s*:\s*\*{0,3}\s*(?:closed|done|complete|completed|archived)(?![\w-])"
)
DEPENDS_ON_RE = re.compile(r"(?im)^\s*-?\s*\*{0,2}Depends-on\*{0,2}\s*:\s*(.+?)\s*$")
EPIC_RE = re.compile(r"(?im)^\s*-?\s*\*{0,2}Epic\*{0,2}\s*:\s*(.+?)\s*$")
NO_EPIC_RE = re.compile(r"(?im)^\s*-?\s*\*{0,2}No-epic rationale\*{0,2}\s*:")


def item_aging_notes(item: Path, today: date, max_age_days: float) -> list[str]:
    """Informational: flag an active item whose <date>- dir prefix is older than
    max_age_days. Aging is a staleness SIGNAL, not a failure."""
    if max_age_days <= 0:
        return []
    match = DIR_DATE_RE.match(item.name)
    if not match:
        return []
    try:
        created = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return []
    age_days = (today - created).days
    if age_days > max_age_days:
        return [f"aging: active {age_days}d (since {created.isoformat()}, threshold {max_age_days:.0f}d)"]
    return []


def _slug_archived(slug: str, archive_dir: Path) -> bool:
    try:
        for cand in [archive_dir / slug, *archive_dir.glob(f"*/{slug}")]:
            if cand.is_dir():
                return True
    except OSError:
        return False
    return False


def _slug_done(slug: str, active_dir: Path, archive_dir: Path) -> bool:
    if _slug_archived(slug, archive_dir):
        return True
    item = active_dir / slug
    try:
        if (item / "closure.md").is_file():
            return True
        status = item / "status.md"
        if status.is_file() and DONE_STATE_LINE_RE.search(status.read_text(encoding="utf-8", errors="replace")):
            return True
    except OSError:
        return False
    return False


def _slug_exists(slug: str, active_dir: Path, archive_dir: Path) -> bool:
    try:
        if (active_dir / slug).is_dir():
            return True
    except OSError:
        return False
    return _slug_archived(slug, archive_dir)


def blocked_by_notes(item: Path, active_dir: Path, archive_dir: Path) -> list[str]:
    """Informational: open Depends-on blockers + dangling targets for an active
    item. A blocked item is EXPECTED state, NOT a failure (so this never flips the
    exit code) — it mirrors the /agents-status governance derivation in a script."""
    status = item / "status.md"
    try:
        text = status.read_text(encoding="utf-8", errors="replace") if status.is_file() else ""
    except OSError:
        return []
    match = DEPENDS_ON_RE.search(text)
    if not match:
        return []
    open_targets: list[str] = []
    dangling: list[str] = []
    for token in match.group(1).split(","):
        slug = token.strip().strip("`")
        if not slug or slug.lower() == "none" or slug.startswith("<") or not SLUG_RE.match(slug):
            continue
        if not _slug_exists(slug, active_dir, archive_dir):
            dangling.append(slug)
        elif not _slug_done(slug, active_dir, archive_dir):
            open_targets.append(slug)
    notes: list[str] = []
    if open_targets:
        notes.append(f"blocked-by: {', '.join(open_targets)} (open Depends-on)")
    if dangling:
        notes.append(f"dangling Depends-on: {', '.join(dangling)} (no matching work-item)")
    return notes


def _read_status_text(item: Path) -> str:
    status = item / "status.md"
    try:
        return status.read_text(encoding="utf-8", errors="replace") if status.is_file() else ""
    except OSError:
        return ""


def epic_link_notes(item: Path, active_dir: Path) -> list[str]:
    """Informational: surface a child work-item that claims a missing epic.

    Missing epics are adoption/routing signals, not validity failures. The
    production hook only catches lifecycle drift for already-created epics, so
    this checker provides the status-surface prompt for bad or dangling links.
    """
    text = _read_status_text(item)
    match = EPIC_RE.search(text)
    if not match:
        return []
    slug = match.group(1).strip().strip("`")
    if not slug or slug.lower() == "none" or slug.startswith("<"):
        return []
    if not SLUG_RE.match(slug):
        return [f"invalid Epic: {slug}"]
    epic_path = active_dir.parent / "epics" / f"{slug}.md"
    if not epic_path.is_file():
        return [f"dangling Epic: {slug} (no matching work-items/epics/{slug}.md)"]
    return []


def epic_adoption_notes(items: list[Path], active_dir: Path) -> list[str]:
    """Informational: nudge multi-item initiatives toward an epic or rationale."""
    if len(items) < 2:
        return []
    epics_dir = active_dir.parent / "epics"
    if epics_dir.is_dir():
        return []
    saw_epic_or_rationale = False
    for item in items:
        text = _read_status_text(item)
        if EPIC_RE.search(text) or NO_EPIC_RE.search(text):
            saw_epic_or_rationale = True
            break
    if saw_epic_or_rationale:
        return []
    return [
        "no work-items/epics/ directory for multiple active items; "
        "if they serve one initiative, admit an epic or record No-epic rationale"
    ]


def iter_work_items(active_dir: Path) -> list[Path]:
    if not active_dir.exists():
        return []
    return sorted(path for path in active_dir.iterdir() if path.is_dir())


def command_check(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    active_dir = (root / args.active_dir).resolve()
    items = iter_work_items(active_dir)
    # NOTE: no early return on empty active/ — the archive laundering scan below must
    # run regardless (fable impl-gate r2 F1: archiving the LAST active item is the
    # natural laundering terminal state and used to bypass the scan entirely).

    validator = load_validator()
    now = parse_time(args.now) if args.now else datetime.now(UTC)
    today = now.date()
    stale_after = timedelta(hours=args.stale_hours)
    archive_dir = active_dir.parent / "archive"
    failed = 0
    global_notes = epic_adoption_notes(items, active_dir)

    telemetry: dict[str, int] = {}
    for item in items:
        errors = validator.validate_work_item(
            item,
            strict_revise=not args.no_strict_revise,
            telemetry=telemetry,
        )
        errors.extend(stale_running_errors(item, now, stale_after))
        # Informational notes (aging, blocked-by) are NOT failures: a blocked or
        # aging active item is expected state, not a defect, so they never flip
        # the exit code or the RESULT line.
        notes = item_aging_notes(item, today, args.max_age_days)
        notes.extend(blocked_by_notes(item, active_dir, archive_dir))
        notes.extend(epic_link_notes(item, active_dir))
        label = item.name
        if errors:
            failed += 1
            print(f"FAIL {label}:")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"PASS {label}")
        for note in notes:
            print(f"  info: {note}")
    for note in global_notes:
        print(f"info: {note}")

    # Archival must not launder open obligations (decision item 3; fable impl gate
    # REVISE-1): an archived item's ledger is still scanned for open v2 REVISEs.
    # v2-scoping keeps historical v1 archives quiet.
    if not args.no_strict_revise:
        for ledger in sorted(archive_dir.rglob("agent-runs.jsonl")):
            arch_errors: list[str] = []
            events = validator.load_jsonl(ledger, arch_errors)
            open_revise, _open_launches = validator.validate_closure(events, [], telemetry)
            if open_revise:
                failed += 1
                print(f"FAIL {ledger.parent.name} (ARCHIVED):")
                for event in open_revise:
                    print(
                        f"  - open REVISE obligation survived archival: {event.get('runId')} "
                        f"(lane={event.get('lane')!r}) — archival does not discharge a review verdict"
                    )

    if args.telemetry and telemetry:
        counters = ", ".join(f"{k}={v}" for k, v in sorted(telemetry.items()))
        print(f"TELEMETRY: {counters}")

    if failed:
        print(f"RESULT: FAIL ({failed} failures across active+archived work-items)")
        return 1

    if not items:
        print(f"RESULT: PASS (no active work-items: {active_dir}; archive scan clean)")
        return 0
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
    parser.add_argument("--telemetry", action="store_true", help="Print closure rule-fire counters (incl. deferred-rule audit counters).")
    parser.add_argument(
        "--no-strict-revise",
        action="store_true",
        help="Do not FAIL on open v2 REVISE obligations (triage sessions only; the default is strict per decision 2026-07-16-review-verdict-closure).",
    )
    parser.add_argument(
        "--max-age-days",
        type=float,
        default=0.0,
        help="Report (informational) active items whose <date>- dir prefix is older than this many days. Use 0 to disable.",
    )
    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return command_check(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
