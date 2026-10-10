#!/usr/bin/env python3
import argparse
import hashlib
import importlib.util
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path, PurePosixPath, PureWindowsPath
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
@dataclass(frozen=True)
class RequiredSentinelDependency:
    """One composition-root result for every verdict-bearing sentinel use."""

    module: Any | None
    resolve_epic_locations: Any | None
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
        }
        missing = sorted(name for name, capability in required.items() if not callable(capability))
        if missing:
            saw_contract_mismatch = True
            failures.append(f"{label}: missing callable(s): {', '.join(missing)}")
            continue
        return RequiredSentinelDependency(
            module=module,
            resolve_epic_locations=required["resolve_epic_locations"],
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


def unsettled_launch_run_ids(item: Path, context: Any, validator: Any) -> set[str]:
    """Return valid lifecycle launches without a valid terminal settlement.

    ``validate_closure`` owns the terminal-to-launch relation.  The stale check
    consumes that reduction instead of maintaining a second interpretation of
    ``eventKind`` and ``launchRunId``.
    """
    validity_errors: list[str] = []
    _active_positions, _validity, _open_revise, open_launches = (
        validator._reduce_effective_current_state(
        context.rows,
        item,
        validity_errors,
        None,
        context=context,
        )
    )
    if validity_errors:
        return set()
    return {
        run_id
        for event in open_launches
        if isinstance((run_id := event.get("runId")), str)
    }


def stale_running_errors(
    item: Path, now: datetime, stale_after: timedelta, validator: Any
) -> list[str]:
    if stale_after.total_seconds() <= 0:
        return []
    errors: list[str] = []
    root = validator.repo_root_for(item)
    if root is None:
        return errors
    selected_ledger = (item / "agent-runs.jsonl").absolute()
    selected_identity = selected_ledger.relative_to(root.absolute()).as_posix()
    context = validator.load_effective_ledger_view(
        root, item, selected_identity
    )
    if context.observation.activation_state == "invalid":
        return errors
    events = [row.event for row in context.rows]
    unsettled_launches = unsettled_launch_run_ids(item, context, validator)
    compatibility_active = context.view is not None
    for event in events:
        if event.get("status") != "running":
            continue
        run_id = event.get("runId", "<unknown>")
        if (
            compatibility_active
            and run_id not in unsettled_launches
        ) or (
            not compatibility_active
            and event.get("schemaVersion") == 2
            and run_id not in unsettled_launches
        ):
            continue
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
    *, root_input_role: str = "caller-root", original_root: Path | None = None, binding_evidence: tuple = (),
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
            if root_input_role == "caller-root" and original_root is None and not binding_evidence:
                state = lifecycle.work_item_dependency_state(root, slug)
            else:
                state = lifecycle.work_item_dependency_state(root, slug, _input_role=root_input_role,
                    _original_root=root if original_root is None else original_root, _binding_evidence=binding_evidence)
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
        if stripped.startswith("## "):
            break
        if stripped.startswith("#"):
            continue
        content = stripped.lstrip("-*").strip()
        if content:
            return (content[:157] + "...") if len(content) > 160 else content
    return "(no ## Next action content)"


def command_check(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    active_dir = (root / args.active_dir).resolve()
    items = iter_work_items(active_dir)

    validator = load_validator()
    now = parse_time(args.now) if args.now else datetime.now(UTC)
    today = now.date()
    stale_after = timedelta(hours=args.stale_hours)
    archive_dir = active_dir.parent / "archive"
    failed = 0
    lifecycle = load_lifecycle_owner()
    is_valid_slug = lifecycle.is_valid_slug
    base_root = None
    base_evidence = ()
    try:
        identity = getattr(lifecycle, "project_root_identity", None)
        if not callable(identity):
            raise lifecycle.LifecycleError("WI-LIFECYCLE-LOCK-IDENTITY", "paired project identity API unavailable")
        base_root, _base_work_items, base_evidence = identity(args.root,
            known_work_items_root=(args.root / args.active_dir).parent)
        lifecycle.audit_categories(base_root, _input_role="repository-root",
            _original_root=args.root, _binding_evidence=base_evidence)
    except lifecycle.LifecycleError as exc:
        failed += 1
        print(f"FAIL category lifecycle: {exc.failure_id}: {exc}")

    if base_root is not None:
        transfer_errors = validator.validate_obligation_transfer_ownership(base_root)
        if transfer_errors:
            failed += 1
            print("FAIL obligation transfer ownership:")
            for error in transfer_errors:
                print(f"  - {error}")

    global_notes = epic_adoption_notes(items, active_dir)
    sentinel_dependency = load_required_sentinels()
    if not sentinel_dependency.available:
        failed += 1
        print("FAIL checker dependency:")
        print(f"  - {sentinel_dependency.diagnostic()}")

    telemetry: dict[str, int] = {}
    for item in items:
        errors = validator.validate_work_item(
            item,
            strict_revise=not args.no_strict_revise,
            telemetry=telemetry,
        )
        errors.extend(stale_running_errors(item, now, stale_after, validator))
        resolver = sentinel_dependency.resolve_epic_locations
        if callable(resolver):
            errors.extend(epic_link_notes(item, active_dir, resolver, is_valid_slug))
        notes = item_aging_notes(item, today, args.max_age_days)
        if base_root is not None:
            notes.extend(blocked_by_notes(item, base_root, lifecycle, is_valid_slug,
                root_input_role="repository-root", original_root=args.root, binding_evidence=base_evidence))
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
                sentinel_ctx = build_context(str(root))
                for finding in evaluate_all(sentinel_ctx):
                    first_line = finding.message.splitlines()[0] if finding.message else ""
                    print(f"info: sentinel {finding.id} ({finding.severity}): {first_line}")
            except Exception as exc:
                print(
                    "info: sentinel optional reporting failed: "
                    f"{type(exc).__name__}: {exc}"
                )

    if not args.no_strict_revise and not args.active_only:
        try:
            acquire = getattr(lifecycle, "archive_entity_inventory", None)
            if not callable(acquire):
                raise RuntimeError("paired lifecycle archive inventory API is unavailable")
            inventory = acquire((args.root / args.active_dir).parent, input_role="work-items-root")
            if not isinstance(inventory, lifecycle.ArchiveEntityInventory):
                raise RuntimeError("lifecycle archive inventory contract is unavailable")
            observed_archive = inventory.archive_absent if inventory.archive_absent is not None else inventory.directories[0][0]
            if observed_archive != archive_dir:
                raise RuntimeError("lifecycle archive inventory does not match the requested archive scope")
            for item in inventory.logical_work_item_paths:
                ledger = item / "agent-runs.jsonl"
                if not lifecycle._ledger_location_lexically_exists(ledger):
                    continue
                arch_errors, open_revise, _open_launches = validator.validate_archived_ledger_obligations(
                    item, telemetry=telemetry
                )
                if open_revise or arch_errors:
                    failed += 1
                    print(f"FAIL {item.name} (ARCHIVED):")
                    for error in arch_errors:
                        print(f"  - {error}")
                    for event in open_revise:
                        print(
                            f"  - open REVISE obligation survived archival: {event.get('runId')} "
                            f"(lane={event.get('lane')!r}) — archival does not discharge a review verdict"
                        )
            inventory.verify()
        except (lifecycle.LifecycleError, OSError, AttributeError, IndexError, RuntimeError) as exc:
            failed += 1
            print(f"FAIL archived lifecycle inventory: {getattr(exc, 'failure_id', type(exc).__name__)}: {exc}")

    if args.telemetry and telemetry:
        counters = ", ".join(f"{k}={v}" for k, v in sorted(telemetry.items()))
        print(f"TELEMETRY: {counters}")

    if items:
        print("STILL OPEN - these active work-items are NOT closed (a check result is state, not completion):")
        for item in items:
            print(f"  - {item.name} -- Next action: {next_action_line(item, validator)}")

    if failed:
        print(f"RESULT: FAIL ({failed} failures across active+archived work-items)")
        return 1

    if not items:
        if args.active_only:
            print(
                f"RESULT: PASS (no active work-items: {active_dir}; "
                "archive obligation scan skipped)"
            )
            return 0
        print(f"RESULT: PASS (no active work-items: {active_dir}; archive scan clean)")
        return 0
    if args.active_only:
        print("info: publication scope active-only; archive obligation scan skipped")
    print(
        f"RESULT: PASS - valid state only, NOT completion: {len(items)} active work-item(s) "
        f"STILL OPEN (see 'STILL OPEN' list above; a done-claim must reconcile each one's Next action)"
    )
    return 0


class GoalInputError(ValueError):
    """One bounded failure in the opt-in Goal input contract."""

    def __init__(self, code: str, detail: str, ref: dict | None = None, *, root_id=None, item=None):
        super().__init__(detail)
        self.code, self.ref = code, ref
        self.root_id, self.item = root_id, item


def _goal_object(value: Any, fields: str, label: str) -> dict:
    if not isinstance(value, dict) or set(value) != set(fields.split()):
        raise GoalInputError("GC-SCOPE", f"{label}: exact object fields required")
    return value


def _goal_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GoalInputError("GC-SCOPE", f"{label}: nonempty string required")
    return value


def _goal_strings(value: Any, label: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise GoalInputError("GC-SCOPE", f"{label}: list required")
    values = [_goal_text(entry, label) for entry in value]
    if len(set(values)) != len(values):
        raise GoalInputError("GC-SCOPE", f"{label}: duplicate ID")
    return values


def _goal_ref(value: Any) -> dict:
    ref = _goal_object(value, "rootId workItem path sha256", "reference")
    _goal_text(ref["rootId"], "reference rootId")
    if ref["workItem"] is not None:
        _goal_text(ref["workItem"], "reference workItem")
    path = _goal_text(ref["path"], "reference path")
    if ("\\" in path or PurePosixPath(path).is_absolute() or PureWindowsPath(path).drive
        or any(part in {"", ".", ".."} for part in path.split("/"))):
        raise GoalInputError("GC-REFERENCE", "reference path is not confined POSIX relative", ref)
    if not isinstance(ref["sha256"], str) or re.fullmatch(r"[0-9a-f]{64}", ref["sha256"]) is None:
        raise GoalInputError("GC-REFERENCE", "reference digest must be lowercase SHA-256", ref)
    return ref


def _goal_pair(value: Any, label: str) -> dict:
    pair = _goal_object(value, "rootId slug", label)
    _goal_text(pair["rootId"], label)
    _goal_text(pair["slug"], label)
    return pair


def _goal_rules(value: Any, criterion_ids: list[str]) -> dict:
    rules = _goal_object(value, "emptyActiveCriterion settlementCriterion", "rules")
    if any(entry is not None and entry not in criterion_ids for entry in rules.values()):
        raise GoalInputError("GC-SCOPE", "rule criterion is outside original criteria")
    return rules


def _goal_block(data: bytes, kind: str, validator: Any) -> tuple[dict, bytes]:
    opening = f"<!-- orchestrarium-goal-{kind}:v1 -->".encode()
    closing = f"<!-- /orchestrarium-goal-{kind}:v1 -->".encode()
    try:
        data.decode("utf-8")
        if (data.count(opening) != 1 or data.count(closing) != 1
            or data.count(f"<!-- orchestrarium-goal-{kind}:".encode()) != 1
            or data.count(f"<!-- /orchestrarium-goal-{kind}:".encode()) != 1):
            raise ValueError("exactly one marker pair required")
        start, end = data.index(opening), data.index(closing)
        if end <= start:
            raise ValueError("marker order differs")
        value = validator.decode_json_object(data[start + len(opening):end], source=f"Goal {kind}",
                                             maximum_bytes=validator.MAX_TRANSFER_LEDGER_BYTES)
    except (ValueError, UnicodeError) as exc:
        raise GoalInputError("GC-SCOPE", f"Goal {kind}: {exc}") from exc
    return value, data[:start]


def _goal_root_profile(owner: Any, root_id: str, root: Path, goal: dict, original: dict) -> dict:
    """Derive task applicability from acquired topology and root-matching authority."""
    expected = any(row["rootId"] == root_id for row in original["originalMembers"] + goal["members"])
    expected |= goal["goalItem"]["rootId"] == root_id
    refs = [goal["admission"], goal["coverage"]["inventory"], goal["coverage"]["audit"]]
    refs.extend(row["admission"] for row in goal["roots"])
    refs.extend(row[key] for row in goal["members"] for key in ("acceptance", "receipt") if row[key] is not None)
    refs.extend(original[key] for key in ("previousAdmission", "amendment") if original[key] is not None)
    refs.extend(row["authority"] for row in original["unresolvedRoots"])
    for criterion in goal["criteria"]:
        if criterion["acceptance"] is not None:
            refs.append(criterion["acceptance"])
        refs.extend(criterion["checks"] + criterion["sourcePins"])
        for action in criterion["actions"]:
            expected |= action["rootId"] == root_id and (action["item"] is not None or action["kind"] == "item-close")
            if action["evidence"] is not None:
                refs.append(action["evidence"])
    for value in refs:
        ref = _goal_ref(value)
        expected |= ref["rootId"] == root_id and (ref["workItem"] is not None or PurePosixPath(ref["path"]).parts[0] == "work-items")
    try:
        owner._lifecycle_reject_unreduced_reparse(root, failure_id="WI-GOAL-ROOT",
                                                message="Goal root crosses a link or reparse point")
        topology = owner._resolve_project_topology(root)
        work_items = topology.work_items
        owner._lifecycle_reject_unreduced_reparse(work_items, failure_id="WI-GOAL-ROOT",
                                                message="Goal task domain crosses a link or reparse point")
        try:
            work_items.lstat()
        except FileNotFoundError:
            present = False
        else:
            present = True
            if not work_items.is_dir():
                raise GoalInputError("GC-REFERENCE", "declared task domain is not a directory", root_id=root_id)
    except (OSError, owner.LifecycleError) as exc:
        raise GoalInputError("GC-REFERENCE", f"task-domain acquisition failed: {getattr(exc, 'failure_id', type(exc).__name__)}: {exc}", root_id=root_id) from exc
    if expected and not present:
        raise GoalInputError("GC-REFERENCE", "expected task domain is unavailable", root_id=root_id)
    if not present and any(row["id"] == root_id for row in original["unresolvedRoots"]):
        raise GoalInputError("GC-SCOPE", "preservation root authority remains unresolved", root_id=root_id)
    return {"kind": "managed" if present else "preservation-only", "workItems": work_items}


def _require_complete_archive_inventory(read_model: dict, root_id: str) -> None:
    inventory = read_model.get("archiveInventory")
    valid = (isinstance(inventory, dict) and set(inventory) == {
        "schemaVersion", "acquisitionComplete", "classificationComplete", "unbound"}
        and type(inventory["schemaVersion"]) is int and inventory["schemaVersion"] == 1
        and type(inventory["acquisitionComplete"]) is bool
        and type(inventory["classificationComplete"]) is bool
        and isinstance(inventory["unbound"], list))
    if not valid:
        raise GoalInputError("GC-REFERENCE", "WI-ARCHIVE-ENTITY-UNBOUND: archive observation missing or ill-typed", root_id=root_id)
    if not inventory["acquisitionComplete"] or not inventory["classificationComplete"] or inventory["unbound"]:
        raise GoalInputError("GC-REFERENCE", "WI-ARCHIVE-ENTITY-UNBOUND: archive classification remains incomplete", root_id=root_id)


def evaluate_goal_completion(coordinator_root: Path, goal_record: Path, *, phase: str = "observe") -> dict:
    """Read-only composition of admitted scope, physical owners and accepted proof.

    Root owns semantic acceptance. This query binds those inputs and reports
    eligibility; it never closes items, edits evidence or invokes a native Goal.
    """
    result = {
        "schema": "orchestrarium-goal-result", "version": 1, "admissionId": None,
        "phase": phase, "decision": "unverified", "criteria": [], "roots": [], "members": [], "causes": [],
        "quote": {"contractSha256": None, "admissionSha256": None,
                  "evaluatorSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "references": []},
    }
    captures = []
    roots: dict[str, Path] = {}
    referenced: set[tuple] = set()
    profile_observations = {}
    pending = False

    def cause(code: str, detail: str, root_id=None, item=None, ref=None):
        result["causes"].append({"code": code, "rootId": root_id, "item": item, "ref": ref, "detail": detail})

    def capture(path: Path):
        try:
            snapshot = owner._capture_file_snapshot(path, failure_id="WI-GOAL-REFERENCE",
                                                    maximum_bytes=validator.MAX_TRANSFER_LEDGER_BYTES)
        except (OSError, ValueError, owner.LifecycleError) as exc:
            raise GoalInputError("GC-REFERENCE", f"cannot acquire reference: {exc}") from exc
        captures.append(snapshot)
        return snapshot.data

    def item_path(root_id: str, slug: str) -> Path:
        if root_id not in roots or not owner.is_valid_slug(slug):
            raise GoalInputError("GC-REFERENCE", "unknown root or invalid work-item slug")
        locations = owner._category_locations(roots[root_id], owner.CATEGORIES["work-item"], slug)
        if len(locations) != 1 or not locations[0].is_dir():
            raise GoalInputError("GC-REFERENCE", "work-item has no unique active/archive location")
        return locations[0].resolve()

    def resolve_ref(value: Any) -> tuple[Path, bytes]:
        ref = _goal_ref(value)
        if ref["rootId"] not in roots:
            raise GoalInputError("GC-REFERENCE", "reference root is unavailable", ref)
        base = roots[ref["rootId"]]
        if ref["workItem"] is not None:
            base = item_path(ref["rootId"], ref["workItem"])
            path_errors: list[str] = []
            path = validator.resolve_work_item_path(base, ref["path"], "Goal reference", result["admissionId"], path_errors)
            if path_errors or path is None or path != (base / ref["path"]).resolve():
                raise GoalInputError("GC-REFERENCE", "reference is not item-relative", ref)
        else:
            path = (base / ref["path"]).resolve()
        if path != base.resolve() and base.resolve() not in path.parents:
            raise GoalInputError("GC-REFERENCE", "reference escapes admitted owner", ref)
        try:
            data = capture(path)
        except GoalInputError as exc:
            exc.ref = ref
            raise
        if hashlib.sha256(data).hexdigest() != ref["sha256"]:
            raise GoalInputError("GC-DRIFT", "reference digest differs from acquired bytes", ref)
        identity = tuple(ref[key] for key in ("rootId", "workItem", "path", "sha256"))
        if identity not in referenced:
            referenced.add(identity)
            result["quote"]["references"].append(dict(ref))
        return path, data

    def admission(value: Any, seen: set[tuple]) -> dict:
        ref = _goal_ref(value)
        identity = tuple(ref[key] for key in ("rootId", "workItem", "path", "sha256"))
        if identity in seen:
            raise GoalInputError("GC-SCOPE", "admission chain is cyclic", ref)
        seen.add(identity)
        _path, data = resolve_ref(ref)
        obj, human = _goal_block(data, "admission", validator)
        _goal_object(obj, "schema version admissionId revision humanSha256 previousAdmission amendment criterionIds rootIds goalItem originalMembers unresolvedRoots rules", "admission")
        if (obj["schema"] != "orchestrarium-goal-admission" or type(obj["version"]) is not int
            or obj["version"] != 1 or type(obj["revision"]) is not int or obj["revision"] < 1):
            raise GoalInputError("GC-SCOPE", "admission schema/revision unsupported", ref)
        _goal_text(obj["admissionId"], "admissionId")
        if obj["humanSha256"] != hashlib.sha256(human).hexdigest():
            raise GoalInputError("GC-DRIFT", "admission human prefix differs", ref)
        _goal_strings(obj["criterionIds"], "admission criterionIds", nonempty=True)
        _goal_strings(obj["rootIds"], "admission rootIds", nonempty=True)
        _goal_pair(obj["goalItem"], "admission goalItem")
        _goal_rules(obj["rules"], obj["criterionIds"])
        if not isinstance(obj["originalMembers"], list) or not isinstance(obj["unresolvedRoots"], list):
            raise GoalInputError("GC-SCOPE", "admission member/unresolved lists required", ref)
        pairs = []
        for row in obj["originalMembers"]:
            pair = _goal_pair(row, "original member")
            if pair["rootId"] not in obj["rootIds"]:
                raise GoalInputError("GC-SCOPE", "original member root omitted", ref)
            pairs.append((pair["rootId"], pair["slug"]))
        if len(set(pairs)) != len(pairs) or (obj["goalItem"]["rootId"], obj["goalItem"]["slug"]) not in pairs:
            raise GoalInputError("GC-SCOPE", "original member/goal binding invalid", ref)
        unresolved = set()
        for row in obj["unresolvedRoots"]:
            _goal_object(row, "id authority", "unresolved root")
            if row["id"] not in obj["rootIds"] or row["id"] in unresolved:
                raise GoalInputError("GC-SCOPE", "unresolved root binding invalid", ref)
            unresolved.add(row["id"])
            resolve_ref(row["authority"])
        if obj["revision"] == 1:
            if obj["previousAdmission"] is not None or obj["amendment"] is not None:
                raise GoalInputError("GC-SCOPE", "first admission cannot claim amendment", ref)
        else:
            previous = admission(obj["previousAdmission"], seen)
            resolve_ref(obj["amendment"])
            if (obj["revision"] != previous["revision"] + 1 or obj["admissionId"] != previous["admissionId"]
                or obj["goalItem"] != previous["goalItem"] or obj["rules"] != previous["rules"]
                or not set(previous["criterionIds"]) <= set(obj["criterionIds"])
                or not set(previous["rootIds"]) <= set(obj["rootIds"])
                or not {(row["rootId"], row["slug"]) for row in previous["originalMembers"]} <= set(pairs)):
                raise GoalInputError("GC-SCOPE", "admission amendment shrinks or changes original authority", ref)
        return obj

    try:
        if phase not in {"observe", "preclose", "final"}:
            raise GoalInputError("GC-SCOPE", "unsupported Goal phase")
        validator, owner = load_validator(), load_lifecycle_owner()
        coordinator = owner._work_items_root(Path(coordinator_root)).parent.resolve()
        record = Path(goal_record)
        record = record.resolve() if record.is_absolute() else (coordinator / record).resolve()
        if coordinator not in record.parents:
            raise GoalInputError("GC-REFERENCE", "Goal record is outside explicit coordinator")
        data = capture(record)
        result["quote"]["contractSha256"] = hashlib.sha256(data).hexdigest()
        goal, _prefix = _goal_block(data, "contract", validator)
        _goal_object(goal, "schema version admissionId admission criterionIds coordinatorRootId roots goalItem members criteria rules coverage", "Goal")
        if goal["schema"] != "orchestrarium-goal-completion" or type(goal["version"]) is not int or goal["version"] != 1:
            raise GoalInputError("GC-SCOPE", "unsupported Goal schema/version")
        result["admissionId"] = _goal_text(goal["admissionId"], "admissionId")
        _goal_text(goal["coordinatorRootId"], "coordinatorRootId")
        criterion_ids = _goal_strings(goal["criterionIds"], "criterionIds", nonempty=True)
        _goal_pair(goal["goalItem"], "goalItem")
        _goal_rules(goal["rules"], criterion_ids)
        if not isinstance(goal["roots"], list) or not goal["roots"]:
            raise GoalInputError("GC-SCOPE", "covered roots required")
        root_ids = []
        physical = set()
        for row in goal["roots"]:
            _goal_object(row, "id locator identity admission", "covered root")
            root_id = _goal_text(row["id"], "root ID")
            if root_id in root_ids:
                raise GoalInputError("GC-SCOPE", "duplicate root ID")
            root_ids.append(root_id)
            root_result = {"id": root_id, "identity": None, "active": [], "taskDomain": "unverified"}
            result["roots"].append(root_result)
            locator = Path(_goal_text(row["locator"], "root locator"))
            candidate = locator if locator.is_absolute() else coordinator / locator
            try:
                owner._lifecycle_reject_unreduced_reparse(candidate, failure_id="WI-GOAL-ROOT",
                                                        message="Goal root crosses a link or reparse point")
            except owner.LifecycleError as exc:
                raise GoalInputError("GC-REFERENCE", f"{exc.failure_id}: {exc}", root_id=root_id) from exc
            canonical = owner._work_items_root(candidate).parent.resolve()
            if str(canonical) != _goal_text(row["identity"], "root identity") or canonical in physical:
                raise GoalInputError("GC-SCOPE", "root identity differs or repeats", row["admission"])
            physical.add(canonical)
            if not canonical.is_dir():
                raise GoalInputError("GC-REFERENCE", "covered root is unavailable", row["admission"], root_id=root_id)
            roots[root_id] = canonical
            root_result["identity"] = str(canonical)
        if roots.get(goal["coordinatorRootId"]) != coordinator or goal["goalItem"]["rootId"] not in roots:
            raise GoalInputError("GC-SCOPE", "coordinator/goal root binding differs")
        for row in goal["roots"]:
            resolve_ref(row["admission"])
        original = admission(goal["admission"], set())
        result["quote"]["admissionSha256"] = goal["admission"]["sha256"]
        if any(goal[key] != original[key] for key in ("admissionId", "criterionIds", "goalItem", "rules")) or root_ids != original["rootIds"]:
            raise GoalInputError("GC-SCOPE", "Goal differs from independent original admission")
        if original["unresolvedRoots"]:
            row = original["unresolvedRoots"][0]
            raise GoalInputError("GC-SCOPE", "original root authority remains unresolved", row["authority"], root_id=row["id"])
        locations = owner._category_locations(coordinator, owner.CATEGORIES["epic"], record.stem)
        if len(locations) != 1 or locations[0].resolve() != record:
            raise GoalInputError("GC-REFERENCE", "Goal epic is not uniquely located")
        if phase == "final":
            if record.parent.parent != (coordinator / "work-items" / "epics" / "archive"):
                cause("GC-ACTIVE", "Goal epic terminal/readback remains pending", goal["coordinatorRootId"])
                pending = True
            else:
                owner._validate_flat_terminal(owner.CATEGORIES["epic"], data)
                if owner._parse_fields(data.decode("utf-8")).get("status") not in {"closed", "archived"}:
                    raise GoalInputError("GC-OUTCOME", "cancelled epic is not Goal delivery")
        coverage = _goal_object(goal["coverage"], "inventory audit pending", "coverage")
        resolve_ref(coverage["inventory"])
        resolve_ref(coverage["audit"])
        if _goal_strings(coverage["pending"], "coverage pending"):
            cause("GC-CRITERION", "coverage retains pending original variants")
            pending = True
        if not isinstance(goal["criteria"], list) or not isinstance(goal["members"], list):
            raise GoalInputError("GC-SCOPE", "criterion/member lists required")
        criteria = {}
        pending_actions = []
        action_ids = set()
        for row in goal["criteria"]:
            _goal_object(row, "id state acceptance checks sourcePins actions", "criterion")
            cid = _goal_text(row["id"], "criterion ID")
            if cid not in criterion_ids or cid in criteria or not isinstance(row["state"], str) or row["state"] not in {"verified", "pending", "unverified"}:
                raise GoalInputError("GC-SCOPE", "criterion identity/state differs")
            criteria[cid] = row
            local_causes = []
            if row["acceptance"] is not None:
                resolve_ref(row["acceptance"])
            if row["state"] == "verified" and row["acceptance"] is None:
                raise GoalInputError("GC-CRITERION", "verified criterion lacks accepted evidence")
            for key in ("checks", "sourcePins"):
                if not isinstance(row[key], list):
                    raise GoalInputError("GC-SCOPE", "criterion reference lists required")
                for ref in row[key]:
                    resolve_ref(ref)
                if row["state"] == "verified" and not row[key]:
                    raise GoalInputError("GC-CRITERION", "verified criterion lacks checks/current pins")
            if not isinstance(row["actions"], list):
                raise GoalInputError("GC-SCOPE", "criterion actions required")
            for action in row["actions"]:
                _goal_object(action, "id kind rootId item state evidence", "action")
                aid = _goal_text(action["id"], "action ID")
                if (aid in action_ids or not isinstance(action["kind"], str) or action["kind"] not in {"check", "git", "resource", "item-close", "other"}
                    or not isinstance(action["state"], str) or action["state"] not in {"settled", "pending", "unverified"}
                    or (action["rootId"] is not None and (not isinstance(action["rootId"], str) or action["rootId"] not in roots))
                    or (action["item"] is not None and (not isinstance(action["item"], str) or not owner.is_valid_slug(action["item"])))):
                    raise GoalInputError("GC-SCOPE", "action binding/type differs")
                action_ids.add(aid)
                if action["evidence"] is not None:
                    resolve_ref(action["evidence"])
                if action["state"] == "settled" and action["evidence"] is None:
                    raise GoalInputError("GC-CRITERION", "settled action lacks accepted evidence")
                if action["state"] != "settled":
                    pending_actions.append(action)
                    local_causes.append("GC-CRITERION")
                    cause("GC-CRITERION", f"required action remains {action['state']}: {aid}", action["rootId"], action["item"])
                    if action["state"] == "unverified":
                        raise GoalInputError("GC-CRITERION", "required action remains unverified")
            if row["state"] == "unverified":
                raise GoalInputError("GC-CRITERION", "criterion remains unverified")
            if row["state"] != "verified" or local_causes:
                pending = True
                local_causes.append("GC-CRITERION")
                if row["state"] != "verified":
                    cause("GC-CRITERION", f"criterion remains {row['state']}: {cid}")
            result["criteria"].append({"id": cid, "state": "pending" if local_causes else row["state"], "causes": sorted(set(local_causes))})
        if set(criteria) != set(criterion_ids):
            raise GoalInputError("GC-SCOPE", "original criterion omitted")
        result["criteria"].sort(key=lambda row: criterion_ids.index(row["id"]))
        members = {}
        for row in goal["members"]:
            _goal_object(row, "rootId slug outcome acceptance receipt", "member")
            _goal_text(row["rootId"], "member rootId")
            _goal_text(row["slug"], "member slug")
            key = (row["rootId"], row["slug"])
            if key in members or row["rootId"] not in roots or not owner.is_valid_slug(row["slug"]) or not isinstance(row["outcome"], str) or row["outcome"] not in {"delivered", "pending", "unverified"}:
                raise GoalInputError("GC-SCOPE", "member binding/type differs")
            members[key] = row
        original_pairs = {(row["rootId"], row["slug"]) for row in original["originalMembers"]}
        if not original_pairs <= set(members):
            raise GoalInputError("GC-SCOPE", "original member omitted")
        if not set(members) <= original_pairs:
            raise GoalInputError("GC-SCOPE", "added member lacks additive admission amendment")
        active_pairs = set()
        for root_row in result["roots"]:
            root_id, root = root_row["id"], roots[root_row["id"]]
            chain = owner._capture_path_parent_chain(root / "work-items", "WI-GOAL-ROOT")
            profile = _goal_root_profile(owner, root_id, root, goal, original)
            work_items = profile["workItems"]
            identity = owner._lifecycle_file_identity(work_items.lstat()) if profile["kind"] == "managed" else None
            root_row["taskDomain"] = profile["kind"]
            contract = work_items / owner.ROOT_CONTRACT_FILE
            contract_present = owner._ledger_location_lexically_exists(contract)
            profile_observations[root_id] = (chain, profile["kind"], identity, contract_present)
            if contract_present:
                contract_data = capture(contract)
                resolve_ref({"rootId": root_id, "workItem": None, "path": "work-items/" + owner.ROOT_CONTRACT_FILE,
                             "sha256": hashlib.sha256(contract_data).hexdigest()})
            if profile["kind"] == "preservation-only":
                continue
            active = iter_work_items(work_items / "active")
            root_row["active"] = [path.name for path in active]
            for path in active:
                key = (root_id, path.name)
                active_pairs.add(key)
                if key not in members:
                    members[key] = {"rootId": root_id, "slug": path.name, "outcome": "pending", "acceptance": None, "receipt": None}
                    cause("GC-SCOPE", "discovered active member requires retained admission", root_id, path.name)
                    pending = True
            try:
                read_model = owner.observe_readme(root)
            except owner.LifecycleError as exc:
                raise GoalInputError("GC-DRIFT", f"{exc.failure_id}: {exc}", root_id=root_id) from exc
            _require_complete_archive_inventory(read_model, root_id)
            if read_model["observedSha256"] is not None:
                resolve_ref({"rootId": root_id, "workItem": None, "path": "work-items/README.md", "sha256": read_model["observedSha256"]})
            if not read_model["matches"]:
                raise GoalInputError("GC-DRIFT", "WI-README-STALE: covered read-model differs", root_id=root_id)
            for error in validator.validate_obligation_transfer_ownership(root):
                cause("GC-OBLIGATION", error, root_id)
        for key, row in members.items():
            root_id, slug = key
            path = item_path(root_id, slug)
            active = key in active_pairs
            profile = "unverified"
            if row["acceptance"] is not None:
                resolve_ref(row["acceptance"])
            if row["outcome"] == "unverified" or (row["outcome"] == "delivered" and row["acceptance"] is None):
                raise GoalInputError("GC-OUTCOME", "member lacks accepted useful-outcome proof")
            if row["outcome"] == "pending":
                cause("GC-OUTCOME", "member useful outcome remains pending", root_id, slug)
                pending = True
            if active:
                if row["receipt"] is not None:
                    raise GoalInputError("GC-RECEIPT", "active member cannot claim owner-close receipt")
                observation = validator._obligations_observation(path, None, True, {})
                if observation["ledgerSha256"] is not None:
                    resolve_ref({"rootId": root_id, "workItem": slug, "path": "agent-runs.jsonl", "sha256": observation["ledgerSha256"]})
                for error in observation["diagnostics"]:
                    cause("GC-OBLIGATION", error, root_id, slug)
                if observation["obligations"] is None:
                    cause("GC-OBLIGATION", "selected obligation acquisition unavailable", root_id, slug)
                elif any(observation["obligations"].values()):
                    cause("GC-OBLIGATION", "effective obligations remain open", root_id, slug)
                cause("GC-ACTIVE", "covered member remains active", root_id, slug)
                pending = True
            else:
                entry = owner._archived_work_item_entry(path)
                closure_path = path / "closure.md"
                closure_bytes = capture(closure_path)
                closure_fields = owner._parse_fields(closure_bytes.decode("utf-8"))
                profile = "legacy-read-compatible" if entry.classification == owner.LEGACY_READ_CLASSIFICATION else "modern"
                if row["outcome"] != "delivered" or not closure_fields.get("outcome"):
                    raise GoalInputError("GC-OUTCOME", "archival alone is not delivered outcome")
                if profile == "modern":
                    status_text = capture(path / "status.md").decode("utf-8")
                    status_fields = owner._parse_fields(status_text)
                    if status_fields.get("status") not in {"closed", "completed"}:
                        raise GoalInputError("GC-OUTCOME", "cancel/park/supersession is not delivery")
                    if row["receipt"] is None:
                        raise GoalInputError("GC-RECEIPT", "modern member lacks required owner receipt")
                    receipt_path, _receipt = resolve_ref(row["receipt"])
                    if receipt_path != path / owner.BUG_DISPOSITIONS_RECEIPT:
                        raise GoalInputError("GC-RECEIPT", "member receipt is not actual close receipt")
                    try:
                        owner._verify_archived_bug_dispositions(roots[root_id], path, closure_bytes, closure_fields.get("closed", ""))
                    except owner.LifecycleError as exc:
                        raise GoalInputError("GC-RECEIPT", f"{exc.failure_id}: {exc}", row["receipt"]) from exc
                elif row["receipt"] is not None:
                    resolve_ref(row["receipt"])
                resolve_ref({"rootId": root_id, "workItem": slug, "path": "closure.md", "sha256": hashlib.sha256(closure_bytes).hexdigest()})
                if (path / "agent-runs.jsonl").exists():
                    errors, reviews, launches = validator.validate_archived_ledger_obligations(path)
                    for error in errors:
                        cause("GC-OBLIGATION", error, root_id, slug)
                    if reviews or launches:
                        cause("GC-OBLIGATION", "archived effective obligations remain open", root_id, slug)
                elif profile == "modern" and not validator.is_quick_fix_status(status_text):
                    cause("GC-OBLIGATION", "required archived ledger acquisition unavailable", root_id, slug)
            result["members"].append({"rootId": root_id, "slug": slug,
                "state": "active" if active else "delivered-closed", "proofProfile": profile})
        for root_row in result["roots"]:
            root_id = root_row["id"]
            chain, kind, identity, contract_present = profile_observations[root_id]
            try:
                owner._verify_captured_parent_chain(chain, "WI-GOAL-DRIFT")
                current = _goal_root_profile(owner, root_id, roots[root_id], goal, original)
                current_identity = owner._lifecycle_file_identity(current["workItems"].lstat()) if current["kind"] == "managed" else None
                current_contract = owner._ledger_location_lexically_exists(current["workItems"] / owner.ROOT_CONTRACT_FILE)
                if current["kind"] != kind or current_identity != identity or current_contract != contract_present:
                    raise GoalInputError("GC-DRIFT", "task-domain observation changed", root_id=root_id)
            except (owner.LifecycleError, OSError, GoalInputError) as exc:
                root_row["taskDomain"] = "unverified"
                raise GoalInputError("GC-DRIFT", f"task-domain recheck failed: {exc}", root_id=root_id) from exc
        for snapshot in captures:
            try:
                owner._verify_captured_file(snapshot, "WI-GOAL-DRIFT")
            except owner.LifecycleError as exc:
                raise GoalInputError("GC-DRIFT", str(exc)) from exc
        if any(row["code"] == "GC-OBLIGATION" for row in result["causes"]):
            result["decision"] = "unverified"
        elif phase == "preclose":
            goal_key = (goal["goalItem"]["rootId"], goal["goalItem"]["slug"])
            terminal_criteria = {entry for entry in goal["rules"].values() if entry is not None}
            for row in result["criteria"]:
                if row["id"] in terminal_criteria:
                    row["state"] = "pending"
                    if "GC-ACTIVE" not in row["causes"]:
                        row["causes"].append("GC-ACTIVE")
            # Pending last-close actions do not undo separately verified proof.
            # The action predicate below admits only the exact coordinator close.
            substantive = all(row["state"] == "verified" for cid, row in criteria.items() if cid not in terminal_criteria)
            final_actions = all(action["kind"] == "item-close" and (action["rootId"], action["item"]) == goal_key for action in pending_actions)
            accepted_outcomes = all(row["outcome"] == "delivered" for row in members.values())
            if (active_pairs == {goal_key} and substantive and final_actions and accepted_outcomes
                and not coverage["pending"] and set(members) <= original_pairs):
                result["decision"] = "ready-for-last-close"
            else:
                result["decision"] = "continue"
        elif phase == "final" and not pending and not active_pairs:
            result["decision"] = "eligible"
        else:
            result["decision"] = "continue"
    except GoalInputError as exc:
        cause(exc.code, str(exc), root_id=exc.root_id, item=exc.item, ref=exc.ref)
        result["decision"] = "unverified"
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        cause("GC-REFERENCE", f"Goal observation unavailable: {type(exc).__name__}: {exc}")
        result["decision"] = "unverified"
    except Exception as exc:
        # Preserve downstream owner failure identity without making it a new engine.
        cause("GC-REFERENCE", f"{getattr(exc, 'failure_id', type(exc).__name__)}: {exc}")
        result["decision"] = "unverified"
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check all active Orchestrarium work-item ledgers.")
    parser.add_argument("--root", type=Path, default=Path("."), help="Repository root. Defaults to the current directory.")
    parser.add_argument("--goal", type=Path, help="Explicit enrolled epic record for read-only Goal observation.")
    parser.add_argument("--goal-phase", choices=("observe", "preclose", "final"), default="observe")
    parser.add_argument("--json", action="store_true", help="JSON-only Goal result; requires --goal.")
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
        "--active-only",
        action="store_true",
        help=(
            "Validate current active items without the periodic archived-ledger "
            "obligation scan. Intended for the repository publication gate; the "
            "default remains the full active+archive audit."
        ),
    )
    parser.add_argument(
        "--max-age-days",
        type=float,
        default=0.0,
        help="Report (informational) active items whose <date>- dir prefix is older than this many days. Use 0 to disable.",
    )
    return parser


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")  # type: ignore[union-attr]
            except (ValueError, OSError):
                pass
    parser = build_parser()
    args = parser.parse_args(argv)
    explicit = {argument.split("=", 1)[0] for argument in argv if argument.startswith("--")}
    if args.goal is not None:
        if "--root" not in explicit or not args.json:
            parser.error("Goal mode requires explicit --root, --goal and --json")
        if explicit & {"--active-only", "--active-dir", "--no-strict-revise"}:
            parser.error("Goal mode cannot narrow original covered state")
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        result = evaluate_goal_completion(args.root, args.goal, phase=args.goal_phase)
        print(json.dumps(result, ensure_ascii=True))
        return 0 if result["decision"] in {"eligible", "ready-for-last-close"} else 1
    if args.json or "--goal-phase" in explicit:
        parser.error("--json/--goal-phase require --goal")
    return command_check(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
