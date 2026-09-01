#!/usr/bin/env python3
import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
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


# Post-commit stdout contract for consumers that need to distinguish a durable
# append from a rejected or rolled-back attempt. Keep the text in this writer.
APPEND_SUCCESS_MARKER = "RESULT: PASS append"
RECOVERY_SUCCESS_MARKER = "RESULT: PASS recover-invalid-closure"


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


def parse_evidence_json(value: str, validator: Any) -> dict[str, Any]:
    return validator.decode_json_object(value, source="--evidence-json")


def parse_scratch_evidence_json(value: str, validator: Any) -> dict[str, Any]:
    return validator.decode_json_object(
        value.encode("utf-8"),
        source="--scratch-evidence-json",
        maximum_bytes=validator.MAX_SCRATCH_EVIDENCE_JSON_BYTES,
    )


def parse_launch_flags_json(value: str, validator: Any) -> list[str]:
    raw = value.encode("utf-8", errors="strict")
    if len(raw) > validator.LAUNCH_FLAGS_MAX_TOTAL_BYTES:
        raise ValueError("--launch-flags-json exceeds byte limit")
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("--launch-flags-json must be valid JSON") from exc
    if not isinstance(decoded, list):
        raise ValueError("--launch-flags-json must be a JSON array")
    return decoded


def ensure_status_sections(item: Path, args: argparse.Namespace, validator: Any) -> list[str]:
    status_path = item / "status.md"
    if status_path.exists():
        text = status_path.read_text(encoding="utf-8")
    else:
        text = "# Status\n"

    if validator.is_quick_fix_status_candidate(text):
        errors: list[str] = []
        validator.validate_quick_fix_status(text, errors)
        return errors

    if validator.is_staged_status(text):
        errors = []
        validator.validate_staged_status(text, errors)
        return errors

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
    return []


# Legacy executionRole values are READ-mapped by the validator (old ledgers keep
# validating) but must never be WRITTEN into a new event — the retired
# main|lead duality would otherwise resurface on the wire. Mirrors
# scripts/validate-work-item-state.py LEGACY_EXECUTION_ROLES.
LEGACY_EXECUTION_ROLES = {"lead": "main"}


def build_event(args: argparse.Namespace, validator: Any | None = None) -> dict[str, Any]:
    if validator is None:
        validator = load_validator()
    if args.execution_role in LEGACY_EXECUTION_ROLES:
        canonical = LEGACY_EXECUTION_ROLES[args.execution_role]
        raise ValueError(
            f"--execution-role {args.execution_role!r} is a retired legacy value; "
            f"new events must use {canonical!r} (the one main-conversation identity — "
            "orchestration weight belongs in status.md 'orchestration:', not here)"
        )
    started_at = args.started_at or utc_timestamp()
    updated_at = args.updated_at or started_at
    # schemaVersion 2 when any v2 closure/lifecycle field is present; 1 otherwise
    # (the validator rejects v2 fields on v1 events, and strict open-REVISE scoping
    # keys on schemaVersion 2 — see decision 2026-07-16-review-verdict-closure).
    v2 = any(
        value is not None
        for value in (
            getattr(args, "event_kind", None),
            getattr(args, "launch_run_id", None),
            getattr(args, "closes", None),
            getattr(args, "artifact_revision", None),
            getattr(args, "lane", None),
            getattr(args, "effort", None),
            getattr(args, "finding_class", None),
            getattr(args, "scratch_evidence_json", None),
            getattr(args, "terminal_class", None),
            getattr(args, "authorizing", None),
            getattr(args, "actual_execution_path", None),
            getattr(args, "artifact_identity", None),
            getattr(args, "external_dispatch_id", None),
            getattr(args, "external_evidence_run_id", None),
            getattr(args, "effort_mapping_loss", None),
            getattr(args, "launch_flags_json", None),
            getattr(args, "closer_run_id", None),
            getattr(args, "target_tuple_json", None),
        )
    )
    event: dict[str, Any] = {
        "schemaVersion": 2 if v2 else 1,
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
        # v2 closure/lifecycle fields
        "eventKind": getattr(args, "event_kind", None),
        "launchRunId": getattr(args, "launch_run_id", None),
        "closesRunIds": getattr(args, "closes", None),
        "artifactRevision": getattr(args, "artifact_revision", None),
        "lane": getattr(args, "lane", None),
        "effort": getattr(args, "effort", None),
        "findingClass": getattr(args, "finding_class", None),
        "terminalClass": getattr(args, "terminal_class", None),
        "actualExecutionPath": getattr(args, "actual_execution_path", None),
        "artifactIdentity": getattr(args, "artifact_identity", None),
        "externalDispatchId": getattr(args, "external_dispatch_id", None),
        "externalEvidenceRunId": getattr(args, "external_evidence_run_id", None),
        "effortMappingLoss": getattr(args, "effort_mapping_loss", None),
        "closerRunId": getattr(args, "closer_run_id", None),
    }
    for key, value in optional_fields.items():
        if value is not None:
            event[key] = value
    if getattr(args, "authorizing", None) is not None:
        event["authorizing"] = args.authorizing == "true"
    if getattr(args, "launch_flags_json", None) is not None:
        event["launchFlags"] = parse_launch_flags_json(
            args.launch_flags_json, validator
        )
    if getattr(args, "target_tuple_json", None) is not None:
        event["targetTuple"] = validator.decode_json_object(
            args.target_tuple_json,
            source="--target-tuple-json",
        )
    if event.get("terminalClass") == "external-nonauthorizing":
        event["closesRunIds"] = []

    evidence: list[dict[str, Any]] = []
    for value in args.evidence or []:
        evidence.append(parse_evidence(value))
    for value in args.evidence_json or []:
        evidence.append(parse_evidence_json(value, validator))
    if evidence:
        event["evidence"] = evidence

    scratch_evidence = [
        parse_scratch_evidence_json(value, validator)
        for value in (getattr(args, "scratch_evidence_json", None) or [])
    ]
    if scratch_evidence:
        event["scratchEvidence"] = scratch_evidence

    return event


def serialize_event(event: dict[str, Any]) -> str:
    """Render one canonical compact JSONL event without its line terminator."""

    return json.dumps(event, ensure_ascii=False, separators=(",", ":"))


class LedgerMigrationError(RuntimeError):
    def __init__(self, failure_id: str, message: str):
        super().__init__(message)
        self.failure_id = failure_id


@dataclass(frozen=True)
class StagedLegacyMigration:
    staged_bytes: bytes
    receipt_facts: dict[str, Any]


def _migration_fail(failure_id: str, message: str) -> None:
    raise LedgerMigrationError(failure_id, message)


def _strict_migration_inputs(operation_id: str, recorded_at: str) -> None:
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", operation_id, re.ASCII) is None:
        _migration_fail("WI-LEDGER-MIGRATION-TARGET-IDENTITY", "operation id is not bounded")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z", recorded_at, re.ASCII) is None:
        _migration_fail("WI-LEDGER-MIGRATION-TARGET-IDENTITY", "recorded-at is not strict UTC")


def stage_invalid_finding_class_migration(
    item: Path,
    target_run_id: str,
    target_event_sha256: str,
    expected_ledger_sha256: str,
    operation_id: str,
    recorded_at: str,
) -> StagedLegacyMigration:
    """Build and validate one append-only migration anchor without replacing the ledger."""

    return stage_legacy_obligation_migration(
        item, target_run_id, target_event_sha256, expected_ledger_sha256,
        operation_id, recorded_at, "invalid-finding-class",
    )


def stage_legacy_scratch_evidence_migration(
    item: Path,
    target_run_id: str,
    target_event_sha256: str,
    expected_ledger_sha256: str,
    operation_id: str,
    recorded_at: str,
) -> StagedLegacyMigration:
    return stage_legacy_obligation_migration(
        item, target_run_id, target_event_sha256, expected_ledger_sha256,
        operation_id, recorded_at, "remove-string-scratch-evidence",
    )


def stage_legacy_obligation_migration(
    item: Path,
    target_run_id: str,
    target_event_sha256: str,
    expected_ledger_sha256: str,
    operation_id: str,
    recorded_at: str,
    normalization_kind: str,
) -> StagedLegacyMigration:
    _strict_migration_inputs(operation_id, recorded_at)
    for value, failure_id in (
        (target_event_sha256, "WI-LEDGER-MIGRATION-TARGET-DIGEST"),
        (expected_ledger_sha256, "WI-LEDGER-MIGRATION-LEDGER-DRIFT"),
    ):
        if re.fullmatch(r"[0-9a-f]{64}", value, re.ASCII) is None:
            _migration_fail(failure_id, "digest must be lowercase SHA-256")
    item = Path(item)
    ledger_path = item / "agent-runs.jsonl"
    try:
        before = ledger_path.read_bytes()
    except OSError as exc:
        _migration_fail("WI-LEDGER-MIGRATION-LEDGER-DRIFT", str(exc))
    before_sha = hashlib.sha256(before).hexdigest()
    if before_sha != expected_ledger_sha256:
        _migration_fail("WI-LEDGER-MIGRATION-LEDGER-DRIFT", "ledger digest changed")

    validator = load_validator()
    row = validator.LEGACY_MIGRATION_NORMALIZATIONS.get(normalization_kind)
    if row is None:
        _migration_fail("WI-LEDGER-MIGRATION-NORMALIZATION-KIND", "normalization kind is not closed")
    metadata: list[dict[str, Any]] = []
    parse_errors: list[str] = []
    events = validator.load_jsonl(ledger_path, parse_errors, metadata)
    if any(event.get("schemaVersion") == 3 for event in events):
        _migration_fail("WI-LEDGER-MIGRATION-V3-UNSUPPORTED", "V3 ledger is not writable by this migration")
    if parse_errors:
        _migration_fail("WI-LEDGER-MIGRATION-DEFECT-CLASS", "; ".join(parse_errors))
    positions = [index for index, event in enumerate(events) if event.get("runId") == target_run_id]
    if len(positions) != 1:
        _migration_fail("WI-LEDGER-MIGRATION-TARGET-IDENTITY", "target is missing or non-unique")
    target_pos = positions[0]
    target = events[target_pos]
    raw_digest = metadata[target_pos].get("sha256") if target_pos < len(metadata) else None
    if raw_digest != target_event_sha256:
        _migration_fail("WI-LEDGER-MIGRATION-TARGET-DIGEST", "target digest changed")
    if (
        target.get("schemaVersion") != 2
        or target.get("eventKind") != "terminal"
        or target.get("eventKind") in {validator.LEGACY_MIGRATION_KIND, "closure-invalidation"}
    ):
        _migration_fail("WI-LEDGER-MIGRATION-TARGET-INELIGIBLE", "target is not an eligible V2 terminal")
    if normalization_kind == "invalid-finding-class":
        if target.get("gate") != "REVISE":
            _migration_fail("WI-LEDGER-MIGRATION-TARGET-INELIGIBLE", "finding-class target is not REVISE")
        if "findingClass" not in target or target.get("findingClass") in validator.FINDING_CLASSES:
            _migration_fail("WI-LEDGER-MIGRATION-DEFECT-CLASS", "target finding class is already valid")
        replacement = {**target, "findingClass": "legacy-unclassified"}
        diagnostic_id = validator.LEDGER_EVENT_FINDING_CLASS_INVALID
        receipt_finding_class = "legacy-unclassified"
    else:
        if not isinstance(target.get("scratchEvidence"), str):
            _migration_fail("WI-LEDGER-MIGRATION-DEFECT-CLASS", "target scratchEvidence is not a string")
        replacement = {key: value for key, value in target.items() if key != "scratchEvidence"}
        diagnostic_id = validator.LEDGER_EVENT_SCRATCH_EVIDENCE_INVALID
        receipt_finding_class = target.get("findingClass")
    replacement_errors: list[str] = []
    validator.validate_event(replacement, item, set(), replacement_errors)
    if replacement_errors:
        _migration_fail(
            "WI-LEDGER-MIGRATION-DEFECT-CLASS",
            "target has diagnostics besides the selected normalization: " + "; ".join(replacement_errors),
        )
    relation_events = list(events)
    relation_events[target_pos] = replacement
    relation_error = validator.migration_terminal_launch_relation_error(relation_events, target_pos, item)
    if relation_error is not None:
        _migration_fail("WI-LEDGER-MIGRATION-TARGET-INELIGIBLE", relation_error)
    for event in events:
        if event.get("eventKind") == validator.LEGACY_MIGRATION_KIND and event.get("migrationAction") == "apply" and event.get("migratesRunId") == target_run_id:
            _migration_fail("WI-LEDGER-MIGRATION-TOPOLOGY", "target already has a migration apply")

    anchor_run_id = f"ledger-migration-{operation_id}"
    if any(event.get("runId") == anchor_run_id for event in events):
        _migration_fail("WI-LEDGER-MIGRATION-TOPOLOGY", "anchor run id already exists")
    anchor = {
        "schemaVersion": 2,
        "runId": anchor_run_id,
        "workItem": target["workItem"],
        "role": "lead",
        "executionRole": "main",
        "status": "completed",
        "gate": "none",
        "scope": row["scope"],
        "eventKind": "legacy-obligation-migration",
        "migrationAction": "apply",
        "normalizationKind": normalization_kind,
        "migratesRunId": target_run_id,
        "migratesEventSha256": target_event_sha256,
        "replacementEvent": replacement,
        "evidence": [{"kind": "manual-check", "ref": row["evidence"].format(target=target_run_id, digest=target_event_sha256)}],
        "startedAt": recorded_at,
        "updatedAt": recorded_at,
    }
    anchor_bytes = serialize_event(anchor).encode("utf-8")
    prefix = b"" if not before or before.endswith(b"\n") else b"\n"
    staged = before + prefix + anchor_bytes + b"\n"
    if not staged.startswith(before) or staged[: len(before)] != before:
        _migration_fail("WI-LEDGER-MIGRATION-CANDIDATE-INVALID", "candidate does not preserve prefix")
    candidate_path: Path | None = None
    try:
        descriptor, candidate_name = tempfile.mkstemp(prefix=".ledger-migration-", suffix=".jsonl", dir=item)
        candidate_path = Path(candidate_name)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(staged)
            stream.flush()
        parse_errors: list[str] = []
        candidate_metadata: list[dict[str, Any]] = []
        candidate_events = validator.load_jsonl(candidate_path, parse_errors, candidate_metadata)
        _effective, _counters, projection_errors = validator.project_legacy_obligation_migrations(
            candidate_events, candidate_metadata, item
        )
        if parse_errors or projection_errors:
            _migration_fail("WI-LEDGER-MIGRATION-CANDIDATE-INVALID", "; ".join(parse_errors + projection_errors))
    finally:
        if candidate_path is not None:
            candidate_path.unlink(missing_ok=True)

    after_sha = hashlib.sha256(staged).hexdigest()
    anchor_sha = hashlib.sha256(anchor_bytes).hexdigest()
    replacement_sha = hashlib.sha256(serialize_event(replacement).encode("utf-8")).hexdigest()
    facts = {
        "schemaVersion": 1,
        "status": "committed",
        "operationId": operation_id,
        "targetRunId": target_run_id,
        "targetEventSha256": target_event_sha256,
        "anchorRunId": anchor_run_id,
        "anchorEventSha256": anchor_sha,
        "beforeLedgerBytes": len(before),
        "beforeLedgerSha256": before_sha,
        "afterLedgerBytes": len(staged),
        "afterLedgerSha256": after_sha,
        "replacementEventSha256": replacement_sha,
        "normalizationKind": normalization_kind,
        "diagnosticId": diagnostic_id,
        "sourcePath": f"work-items/active/{item.name}/agent-runs.jsonl",
        "receiptPath": f"work-items/active/{item.name}/ledger-migration-receipts/{operation_id}.json",
        "recordedAt": recorded_at,
    }
    if receipt_finding_class is not None:
        facts["findingClass"] = receipt_finding_class
    return StagedLegacyMigration(staged, facts)


def restore_ledger(path: Path, previous: str | None) -> None:
    if previous is None:
        if path.exists():
            path.unlink()
    else:
        path.write_text(previous, encoding="utf-8")


def _read_ledger(item: Path, validator: Any | None = None) -> tuple[list[dict[str, Any]], int]:
    """Return (events, malformed_line_count). A corrupt or non-object JSONL line
    is skipped but COUNTED so the rollup can surface it — an audit surface
    (evidence coverage) must not silently under-count corrupt input."""
    ledger = item / "agent-runs.jsonl"
    events: list[dict[str, Any]] = []
    malformed = 0
    if not ledger.exists():
        return events, malformed
    validator = validator or load_validator()
    with ledger.open("r", encoding="utf-8", newline="") as stream:
        line_no = 0
        while True:
            raw = stream.readline(validator.MAX_LEDGER_LINE_CHARS + 2)
            if raw == "":
                break
            line_no += 1
            complete_line = raw.endswith("\n")
            line = raw.rstrip("\r\n")
            if len(line) > validator.MAX_LEDGER_LINE_CHARS or (
                not complete_line and len(raw) > validator.MAX_LEDGER_LINE_CHARS
            ):
                while raw and not raw.endswith("\n"):
                    raw = stream.readline(validator.MAX_LEDGER_LINE_CHARS + 2)
                malformed += 1
                continue
            if not line.strip():
                continue
            if len(events) >= validator.MAX_LEDGER_EVENTS:
                malformed += 1
                break
            try:
                events.append(
                    validator.decode_json_object(
                        line,
                        source=f"{ledger}:{line_no}",
                    )
                )
            except ValueError:
                malformed += 1
    return events, malformed


class LedgerWriteLockError(RuntimeError):
    pass


@contextmanager
def ledger_write_lock(item: Path):
    """The existing per-item writer lock, reusable by the lifecycle owner."""

    lock_path = Path(item) / "agent-runs.jsonl.lock"
    lock_fd = None
    for _attempt in range(50):
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(lock_fd, f"pid={os.getpid()} at={utc_timestamp()}\n".encode())
            break
        except FileExistsError:
            time.sleep(0.1)
    if lock_fd is None:
        holder = ""
        try:
            holder = lock_path.read_text(encoding="utf-8").strip()
        except OSError:
            pass
        raise LedgerWriteLockError(
            f"ledger locked ({lock_path}; holder: {holder or 'unknown'}); no automatic takeover"
        )
    try:
        yield
    finally:
        os.close(lock_fd)
        lock_path.unlink(missing_ok=True)


def _iter_active_items(active_dir: Path) -> list[Path]:
    if not active_dir.is_dir():
        return []
    return sorted(path for path in active_dir.iterdir() if path.is_dir())


def active_work_item(args: argparse.Namespace, command: str) -> Path | None:
    """Return one resolved current item, rejecting every non-active lifecycle path."""

    if args.work_item is None:
        print(f"FAIL: {command} requires --work-item", file=sys.stderr)
        return None

    item = args.work_item.resolve()
    work_items = next((parent for parent in item.parents if parent.name == "work-items"), None)
    active_root = work_items / "active" if work_items is not None else None
    if active_root is None or item.parent != active_root:
        print(
            f"FAIL: {command} requires a current work-items/active/<item> directory; "
            f"refusing non-active lifecycle path: {item}",
            file=sys.stderr,
        )
        return None
    return item


def command_init(args: argparse.Namespace) -> int:
    item = active_work_item(args, "init")
    if item is None:
        return 1
    item.mkdir(parents=True, exist_ok=True)
    validator = load_validator()
    errors = ensure_status_sections(item, args, validator)
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        print(f"RESULT: FAIL ({len(errors)} errors)", file=sys.stderr)
        return 1
    (item / "agent-runs.jsonl").touch(exist_ok=True)
    print(f"RESULT: PASS init ({item})")
    return 0


def command_append(args: argparse.Namespace) -> int:
    item = active_work_item(args, "append")
    if item is None:
        return 1
    if not item.exists():
        print(f"FAIL: missing work item: {item}", file=sys.stderr)
        return 1

    validator = load_validator()
    try:
        event = build_event(args, validator)
    except ValueError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    ledger_path = item / "agent-runs.jsonl"
    # Kill-safe old-or-new transaction (decision 2026-07-16-review-verdict-closure):
    # lock -> read -> merge -> write TEMP (same dir) -> validate the CANDIDATE ->
    # os.replace -> unlock. NO automatic stale-lock takeover (the ABA reclamation
    # race is unfixable without fencing): on timeout we fail closed with a manual
    # recovery diagnostic. Power-loss durability is explicitly NOT claimed.
    lock_path = item / "agent-runs.jsonl.lock"
    lock_fd = None
    for _attempt in range(50):  # ~5s bounded retry
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(lock_fd, f"pid={os.getpid()} at={utc_timestamp()}\n".encode())
            break
        except FileExistsError:
            time.sleep(0.1)
    if lock_fd is None:
        holder = ""
        try:
            holder = lock_path.read_text(encoding="utf-8").strip()
        except OSError:
            pass
        print(
            f"FAIL: ledger locked ({lock_path}; holder: {holder or 'unknown'}). "
            "No automatic takeover — verify the holder pid is dead, remove the lock file, retry.",
            file=sys.stderr,
        )
        return 1

    try:
        previous = ledger_path.read_text(encoding="utf-8") if ledger_path.exists() else ""
        prefix = "" if not previous or previous.endswith("\n") else "\n"
        line = serialize_event(event)
        candidate = ledger_path.with_suffix(".jsonl.tmp")
        with candidate.open("w", encoding="utf-8", newline="") as fh:
            fh.write(f"{previous}{prefix}{line}\n")
            fh.flush()

        # strict_revise=False: the helper RECORDS events (including REVISE verdicts
        # themselves); closure strictness is the checker's and the gates' job.
        errors = validator.validate_work_item(item, ledger_path=candidate, strict_revise=False)
        if errors:
            candidate.unlink(missing_ok=True)
            for error in errors:
                print(f"FAIL: {error}", file=sys.stderr)
            print(f"RESULT: FAIL ({len(errors)} errors)", file=sys.stderr)
            return 1
        os.replace(candidate, ledger_path)
    finally:
        os.close(lock_fd)
        lock_path.unlink(missing_ok=True)

    print(f"{APPEND_SUCCESS_MARKER} ({ledger_path})")
    return 0


def command_recover_invalid_closure(args: argparse.Namespace) -> int:
    item = active_work_item(args, "recover-invalid-closure")
    if item is None or not item.exists():
        print(f"FAIL: missing work item: {item}")
        return 1
    validator = load_validator()
    started_at = args.started_at or utc_timestamp()
    event = {
        "schemaVersion": 2,
        "runId": args.run_id,
        "workItem": item.name,
        "role": "lead",
        "executionRole": "main",
        "status": "completed",
        "gate": "none",
        "scope": ["ledger-recovery:closure-invalidation"],
        "eventKind": "closure-invalidation",
        "invalidatesRunId": args.target_run_id,
        "invalidatesEventSha256": args.target_event_sha256,
        "evidence": [parse_evidence(value) for value in args.evidence],
        "startedAt": started_at,
        "updatedAt": args.updated_at or started_at,
    }
    ledger_path = item / "agent-runs.jsonl"
    lock_path = item / "agent-runs.jsonl.lock"
    lock_fd = None
    for _attempt in range(50):
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(lock_fd, f"pid={os.getpid()} at={utc_timestamp()}\n".encode())
            break
        except FileExistsError:
            time.sleep(0.1)
    if lock_fd is None:
        print(f"FAIL: ledger locked ({lock_path}); no automatic takeover")
        return 1
    candidate = ledger_path.with_suffix(".jsonl.tmp")
    replaced = False
    try:
        previous = ledger_path.read_bytes() if ledger_path.exists() else b""
        decoded, _ = _read_ledger(item, validator)
        if any(event.get("schemaVersion") == 3 for event in decoded):
            print("FAIL: legacy V1/V2 writer refuses a ledger containing schemaVersion 3")
            return 1
        line = (serialize_event(event) + "\n").encode("utf-8")
        prefix = b"" if not previous or previous.endswith(b"\n") else b"\n"
        expected = previous + prefix + line
        with candidate.open("xb") as stream:
            stream.write(expected)
            stream.flush()
        errors = validator.validate_work_item(item, ledger_path=candidate, strict_revise=False)
        if errors:
            for error in errors:
                print(f"FAIL: {error}")
            print(f"RESULT: FAIL ({len(errors)} errors)")
            return 1
        if args.inject_failure == "pre-replace":
            print("FAIL: ledger-recovery:pre-replace-injected")
            return 1
        os.replace(candidate, ledger_path)
        replaced = True
        if args.inject_failure == "post-replace-readback":
            print("FAIL: ledger-recovery:post-commit-readback-indeterminate")
            return 1
        try:
            actual = ledger_path.read_bytes()
        except OSError:
            print("FAIL: ledger-recovery:post-commit-readback-indeterminate")
            return 1
        if (
            len(actual) != len(expected)
            or hashlib.sha256(actual).digest() != hashlib.sha256(expected).digest()
            or not actual.startswith(previous)
            or not actual.endswith(line)
        ):
            print("FAIL: ledger-recovery:post-commit-readback-indeterminate")
            return 1
    except (OSError, ValueError) as exc:
        print(f"FAIL: ledger-recovery:store-error: {exc}")
        return 1
    finally:
        if not replaced:
            candidate.unlink(missing_ok=True)
        os.close(lock_fd)
        lock_path.unlink(missing_ok=True)
    print(f"{RECOVERY_SUCCESS_MARKER} ({ledger_path})")
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

    validator = load_validator()
    for item in items:
        events, malformed = _read_ledger(item, validator)
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
    append.add_argument(
        "--scratch-evidence-json",
        action="append",
        help="Terminal scratch-evidence ownership entry as a JSON object. Repeatable.",
    )
    append.add_argument("--started-at", help="ISO-like start timestamp. Defaults to current UTC.")
    append.add_argument("--updated-at", help="ISO-like update timestamp. Defaults to started-at.")
    append.add_argument("--notes", help="Short operational note.")
    # v2 closure/lifecycle fields (decision 2026-07-16-review-verdict-closure, minimal slice)
    append.add_argument("--event-kind", choices=["launch", "terminal", "standalone"], help="v2 lifecycle discriminator.")
    append.add_argument("--launch-run-id", help="On a terminal event: the runId of the launch it settles.")
    append.add_argument(
        "--closes",
        action="append",
        help=(
            "runId of an earlier REVISE this PASS/WAIVED:user/"
            "WAIVED:security-reviewer event discharges. Repeatable."
        ),
    )
    append.add_argument("--artifact-revision", help="Revision of the reviewed artifact at review time (git sha or content digest).")
    append.add_argument("--lane", help="Review angle label (e.g. architecture-adversarial).")
    append.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max", "unsupported"], help="Typed declared reasoning-effort tier, or unsupported when an external provider exposes no native effort control.")
    append.add_argument("--finding-class", choices=["publication-safety", "security", "correctness", "performance", "other"], help="REVISE finding classification (publication-safety/security are non-user-waivable).")
    append.add_argument("--terminal-class", choices=["external-nonauthorizing", "internal-authorizing"], help="Typed durable terminal authority class.")
    append.add_argument("--authorizing", choices=["true", "false"], help="Whether this terminal may authorize lifecycle closure.")
    append.add_argument("--actual-execution-path", choices=["direct-external-cli", "internal"], help="Actual terminal execution path.")
    append.add_argument("--artifact-identity", help="Frozen identity of the reviewed artifact.")
    append.add_argument("--external-dispatch-id", help="Frozen external dispatch identity.")
    append.add_argument("--external-evidence-run-id", help="External evidence run consumed by an internal closer.")
    append.add_argument("--effort-mapping-loss", help="Frozen external provider effort-mapping disposition.")
    append.add_argument("--launch-flags-json", help="Exact resolved provider argv flags as a JSON array of strings.")
    append.add_argument("--closer-run-id", help="Distinct internal closer run identity.")
    append.add_argument("--target-tuple-json", help="Exact external target tuple as a JSON object.")
    append.set_defaults(func=command_append)

    recovery = subparsers.add_parser("recover-invalid-closure", help="Append one digest-bound V2 closure invalidation")
    recovery.add_argument("--run-id", required=True)
    recovery.add_argument("--target-run-id", required=True)
    recovery.add_argument("--target-event-sha256", required=True)
    recovery.add_argument("--evidence", action="append", required=True)
    recovery.add_argument("--started-at")
    recovery.add_argument("--updated-at")
    recovery.add_argument("--inject-failure", choices=["pre-replace", "post-replace-readback"], help=argparse.SUPPRESS)
    recovery.set_defaults(func=command_recover_invalid_closure)

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
