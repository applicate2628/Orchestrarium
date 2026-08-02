#!/usr/bin/env python3
import argparse
import importlib.util
import json
import re
import sys
from dataclasses import dataclass
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


def load_lifecycle_owner():
    owner_path = Path(__file__).with_name("mutate-work-item.py")
    spec = importlib.util.spec_from_file_location("mutate_work_item", owner_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load lifecycle owner from {owner_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


REQUIRED_SENTINEL_DEPENDENCY_ID = "required-sentinel-dependency-unavailable"
REQUIRED_SENTINEL_CONTRACT_ID = "required-sentinel-contract-mismatch"
REQUIRED_SENTINEL_CALL_ID = "required-sentinel-call-failed"


@dataclass(frozen=True)
class RequiredSentinelDependency:
    """One composition-root result for every verdict-bearing sentinel use."""

    module: Any | None
    resolve_epic_locations: Any | None
    delivery_action_validation_errors: Any | None
    failure_id: str | None
    candidate_labels: tuple[str, ...]
    candidate_failures: tuple[str, ...]

    @property
    def available(self) -> bool:
        return self.failure_id is None

    def diagnostic(self) -> str:
        tried = ", ".join(self.candidate_labels)
        details = "; ".join(self.candidate_failures)
        return f"{self.failure_id}: tried {tried}; {details}"


def load_required_sentinels() -> RequiredSentinelDependency:
    """Load the sentinel owner once for required validation and optional reporting.

    The two logical candidates preserve the source and installed layouts. Import
    and contract failures remain data until ``command_check`` decides the process
    verdict; no candidate cause is swallowed on total failure.
    """
    candidates = (
        ("installed-sibling", Path(__file__).with_name("workitem_sentinels.py")),
        (
            "source-universal-hooks",
            Path(__file__).parent / "universal-hooks" / "scripts" / "workitem_sentinels.py",
        ),
    )
    failures: list[str] = []
    saw_contract_mismatch = False
    for label, candidate in candidates:
        if not candidate.is_file():
            failures.append(f"{label}: missing")
            continue
        try:
            spec = importlib.util.spec_from_file_location("workitem_sentinels", candidate)
            if spec is None or spec.loader is None:
                raise ImportError("unable to create import specification")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as exc:
            failures.append(f"{label}: {type(exc).__name__}: {exc}")
            continue

        required = {
            "resolve_epic_locations": getattr(module, "resolve_epic_locations", None),
            "delivery_action_validation_errors": getattr(
                module, "delivery_action_validation_errors", None
            ),
        }
        missing = sorted(name for name, capability in required.items() if not callable(capability))
        if missing:
            saw_contract_mismatch = True
            failures.append(f"{label}: missing callable(s): {', '.join(missing)}")
            continue
        return RequiredSentinelDependency(
            module=module,
            resolve_epic_locations=required["resolve_epic_locations"],
            delivery_action_validation_errors=required["delivery_action_validation_errors"],
            failure_id=None,
            candidate_labels=tuple(label for label, _path in candidates),
            candidate_failures=(),
        )

    failure_id = (
        REQUIRED_SENTINEL_CONTRACT_ID
        if saw_contract_mismatch
        else REQUIRED_SENTINEL_DEPENDENCY_ID
    )
    return RequiredSentinelDependency(
        module=None,
        resolve_epic_locations=None,
        delivery_action_validation_errors=None,
        failure_id=failure_id,
        candidate_labels=tuple(label for label, _path in candidates),
        candidate_failures=tuple(failures),
    )


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


def blocked_by_notes(
    item: Path,
    root: Path,
    lifecycle: Any,
    is_valid_slug: Any,
) -> list[str]:
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
    unresolved_targets: list[str] = []
    dangling: list[str] = []
    duplicate: list[str] = []
    invalid: list[str] = []
    for token in match.group(1).split(","):
        slug = token.strip().strip("`")
        if not slug or slug.lower() == "none" or slug.startswith("<"):
            continue
        if not is_valid_slug(slug):
            invalid.append(slug)
            continue
        try:
            state = lifecycle.work_item_dependency_state(root, slug)
        except lifecycle.LifecycleError as exc:
            if exc.failure_id == "WI-REFERENCE-MISSING":
                unresolved_targets.append(slug)
                dangling.append(slug)
                continue
            if exc.failure_id == "WI-CATEGORY-DUAL-LOCATION":
                unresolved_targets.append(slug)
                duplicate.append(slug)
                continue
            raise
        if state == "open":
            open_targets.append(slug)
    notes: list[str] = []
    if open_targets:
        notes.append(f"blocked-by: {', '.join(open_targets)} (open Depends-on)")
    if unresolved_targets:
        notes.append(
            f"blocked-by: {', '.join(unresolved_targets)} (unresolved Depends-on)"
        )
    if dangling:
        notes.append(f"dangling Depends-on: {', '.join(dangling)} (no matching work-item)")
    if duplicate:
        notes.append(
            f"duplicate Depends-on: {', '.join(duplicate)} (multiple matching work-items)"
        )
    if invalid:
        notes.append(f"invalid Depends-on: {', '.join(invalid)}")
    return notes


def _read_status_text(item: Path) -> str:
    status = item / "status.md"
    try:
        return status.read_text(encoding="utf-8", errors="replace") if status.is_file() else ""
    except OSError:
        return ""


def epic_link_notes(
    item: Path,
    active_dir: Path,
    resolve_epic_locations: Any,
    is_valid_slug: Any,
) -> list[str]:
    """Validate a child's Epic link through the sentinel-owned resolver.

    The resolver distinguishes a missing epic from a duplicate location and
    never selects one ambiguous copy. These diagnostics are document validity
    failures in ``command_check`` rather than adoption-only hints.
    """
    text = _read_status_text(item)
    match = EPIC_RE.search(text)
    if not match:
        return []
    slug = match.group(1).strip().strip("`")
    if not slug or slug.lower() == "none" or slug.startswith("<"):
        return []
    if not is_valid_slug(slug):
        return [f"invalid Epic: {slug}"]
    epics_dir = active_dir.parent / "epics"
    try:
        resolution = resolve_epic_locations(epics_dir, slug)
    except Exception as exc:
        return [
            f"unresolved Epic: {slug} (epic location resolver failed: "
            f"{type(exc).__name__}: {exc})"
        ]
    if resolution["state"] == "missing":
        return [
            f"dangling Epic: {slug} (no matching work-items/epics/{slug}.md "
            f"or work-items/epics/archive/<YYYY-MM>/{slug}.md)"
        ]
    if resolution["state"] == "duplicate":
        rendered = ", ".join(
            path.relative_to(active_dir.parent).as_posix()
            for path in resolution["locations"]
        )
        return [f"duplicate Epic: {slug} resolves to multiple locations ({rendered})"]
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


def next_action_line(item: Path, validator=None) -> str:
    """First non-empty content line under the '## Next action' section of status.md,
    for the still-open enumeration. Returns a loud marker (never silence) on a missing
    file/section — open work must stay visible. The heading match is EXACT so
    '## Next actionable' does not false-trigger (codex ff-review); a sub-heading inside
    the section is skipped rather than mistaken for the action; long content is
    ellipsis-truncated. Output-encoding safety (non-ASCII content on a non-UTF-8 console)
    is owned at the stream level in main(), not here."""
    status = item / "status.md"
    if not status.is_file():
        return "(no status.md)"
    try:
        text = status.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "(status.md unreadable)"
    staged_fields = validator.staged_status_fields(text) if validator is not None else None
    if staged_fields is not None:
        content = staged_fields.get("next action", "").strip()
        if not content:
            return "(no Next action field content)"
        return (content[:157] + "...") if len(content) > 160 else content
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if not in_section:
            if stripped.lower().rstrip(": ") in ("## next action", "## next actions"):
                in_section = True
            continue
        if stripped.startswith("## "):  # next top-level section ends the block
            break
        if stripped.startswith("#"):  # a sub-heading inside the section is not the action
            continue
        content = stripped.lstrip("-*").strip()
        if content:
            return (content[:157] + "...") if len(content) > 160 else content
    return "(no ## Next action content)"


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
    lifecycle = load_lifecycle_owner()
    is_valid_slug = lifecycle.is_valid_slug
    try:
        lifecycle.audit_categories(root)
    except lifecycle.LifecycleError as exc:
        failed += 1
        print(f"FAIL category lifecycle: {exc.failure_id}: {exc}")
    global_notes = epic_adoption_notes(items, active_dir)
    sentinel_dependency = load_required_sentinels()
    delivery_errors: dict[str, list[str]] = {}
    if not sentinel_dependency.available:
        failed += 1
        print("FAIL checker dependency:")
        print(f"  - {sentinel_dependency.diagnostic()}")
    else:
        delivery_validator = sentinel_dependency.delivery_action_validation_errors
        assert callable(delivery_validator)
        try:
            delivery_errors = delivery_validator(active_dir)
        except Exception as exc:
            failed += 1
            print("FAIL checker dependency:")
            print(
                f"  - {REQUIRED_SENTINEL_CALL_ID}: "
                f"delivery_action_validation_errors failed: {type(exc).__name__}: {exc}"
            )

    telemetry: dict[str, int] = {}
    for item in items:
        errors = validator.validate_work_item(
            item,
            strict_revise=not args.no_strict_revise,
            telemetry=telemetry,
        )
        errors.extend(stale_running_errors(item, now, stale_after))
        errors.extend(delivery_errors.get(item.name, []))
        resolver = sentinel_dependency.resolve_epic_locations
        if callable(resolver):
            errors.extend(epic_link_notes(item, active_dir, resolver, is_valid_slug))
        # Informational notes (aging, blocked-by) are NOT failures: a blocked or
        # aging active item is expected state, not a defect, so they never flip
        # the exit code or the RESULT line.
        notes = item_aging_notes(item, today, args.max_age_days)
        notes.extend(blocked_by_notes(item, root, lifecycle, is_valid_slug))
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

    # Sentinel findings, reported informationally (S4 seam). This NEVER
    # affects `failed` / the RESULT line: the sentinel registry answers "has
    # the process failed?" at the always-on Stop path, this validator answers
    # "does this document conform?" on demand -- two different questions, one
    # owner each (design.md §3.2). A sentinel RESOLVE/NOTICE surfaces here
    # purely as an extra signal for a human running this checker by hand (a
    # third tier, HALT, was designed and then withdrawn before release --
    # design.md §0.9/§1.0 -- so it is never a value `finding.severity` takes).
    sentinels = sentinel_dependency.module
    if sentinels is not None:
        build_context = getattr(sentinels, "build_context", None)
        evaluate_all = getattr(sentinels, "evaluate_all", None)
        missing_optional = sorted(
            name
            for name, capability in (
                ("build_context", build_context),
                ("evaluate_all", evaluate_all),
            )
            if not callable(capability)
        )
        if missing_optional:
            print(
                "info: sentinel optional reporting unavailable: missing callable(s): "
                + ", ".join(missing_optional)
            )
        else:
            try:
                # Runtime evaluation is informational here; document validity was
                # handled above through the registry-owned delivery parser.
                sentinel_ctx = build_context(str(root))
                for finding in evaluate_all(sentinel_ctx):
                    first_line = finding.message.splitlines()[0] if finding.message else ""
                    print(f"info: sentinel {finding.id} ({finding.severity}): {first_line}")
            except Exception as exc:
                print(
                    "info: sentinel optional reporting failed: "
                    f"{type(exc).__name__}: {exc}"
                )

    # Archival must not launder open obligations (decision item 3; fable impl gate
    # REVISE-1): an archived item's ledger is still scanned for open v2 REVISEs.
    # v2-scoping keeps historical v1 archives quiet.
    if not args.no_strict_revise:
        for ledger in sorted(archive_dir.rglob("agent-runs.jsonl")):
            arch_errors: list[str] = []
            events = validator.load_jsonl(ledger, arch_errors)
            # Canonical position-aligned validation, scoped to schemaVersion-2 events.
            # The validator marks skipped legacy positions ineligible without adding
            # diagnostics, preserving the archive epoch while avoiding caller drift.
            event_validity = validator.derive_event_validity(
                events,
                ledger.parent,
                arch_errors,
                validate_schema_version=2,
            )
            open_revise, _open_launches = validator.validate_closure(
                events,
                arch_errors,
                telemetry,
                event_validity=event_validity,
            )
            if open_revise or arch_errors:
                failed += 1
                print(f"FAIL {ledger.parent.name} (ARCHIVED):")
                for error in arch_errors:
                    print(f"  - {error}")
                for event in open_revise:
                    print(
                        f"  - open REVISE obligation survived archival: {event.get('runId')} "
                        f"(lane={event.get('lane')!r}) — archival does not discharge a review verdict"
                    )

    if args.telemetry and telemetry:
        counters = ", ".join(f"{k}={v}" for k, v in sorted(telemetry.items()))
        print(f"TELEMETRY: {counters}")

    # Forcing function (bug 2026-07-18-false-completion-claim-validator-pass-conflated-with-done):
    # a green RESULT means "valid state + no open ledger obligations", NOT "all closed / done".
    # Always surface every active item + its Next action so a PASS can never be quoted as
    # completion while real unstarted work remains.
    if items:
        # Header is verdict-neutral (prints on PASS and FAIL runs alike): a check result
        # of ANY kind is state, never completion, while these items remain open.
        print("STILL OPEN - these active work-items are NOT closed (a check result is state, not completion):")
        for item in items:
            print(f"  - {item.name} -- Next action: {next_action_line(item, validator)}")

    if failed:
        print(f"RESULT: FAIL ({failed} failures across active+archived work-items)")
        return 1

    if not items:
        print(f"RESULT: PASS (no active work-items: {active_dir}; archive scan clean)")
        return 0
    print(
        f"RESULT: PASS - valid state only, NOT completion: {len(items)} active work-item(s) "
        f"STILL OPEN (see 'STILL OPEN' list above; a done-claim must reconcile each one's Next action)"
    )
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
    # Output-encoding guard at the owner (the stdout stream), not per-string: this tool
    # prints arbitrary status.md content (Next-action previews) that routinely contains
    # non-ASCII (em-dashes, arrows). On a non-UTF-8 console (e.g. cp866) an unguarded
    # print would raise UnicodeEncodeError and kill the whole report. Replace
    # un-encodable characters instead of crashing — closes the class for every print path.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")  # type: ignore[union-attr]
            except (ValueError, OSError):
                pass
    parser = build_parser()
    args = parser.parse_args(argv)
    return command_check(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
