#!/usr/bin/env python3
import argparse
import hashlib
import importlib.util
import json
import os
import re
import stat
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


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
SETTLE_SUCCESS_MARKER = "RESULT: PASS settle-launch"
SETTLE_ALREADY_MARKER = "RESULT: PASS already-settled"
RECOVERY_SUCCESS_MARKER = "RESULT: PASS recover-invalid-closure"
INVALID_CURRENT_DISPOSITION_SUCCESS_MARKER = "RESULT: PASS dispose-invalid-current"
NONCANONICAL_HISTORY_SUCCESS_MARKER = "RESULT: PASS recover-noncanonical-history"


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
            "routing belongs to the selected workflow, not executionRole)"
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


class LedgerNoncanonicalRecoveryError(RuntimeError):
    def __init__(self, failure_id: str, message: str):
        super().__init__(message)
        self.failure_id = failure_id


def _noncanonical_fail(failure_id: str, message: str) -> None:
    raise LedgerNoncanonicalRecoveryError(
        f"WI-LEDGER-NONCANONICAL-{failure_id}", message
    )


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


def _normalize_noncanonical_sha256(value: str) -> str:
    try:
        value.encode("ascii", errors="strict")
    except UnicodeEncodeError:
        _noncanonical_fail("DRIFT", "expected ledger digest is not ASCII hexadecimal")
    if re.fullmatch(r"[0-9A-Fa-f]{64}", value, re.ASCII) is None:
        _noncanonical_fail("DRIFT", "expected ledger digest must be SHA-256")
    return value.lower()


def _strict_noncanonical_inputs(operation_id: str, recorded_at: str) -> None:
    if re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", operation_id, re.ASCII
    ) is None:
        _noncanonical_fail("IDENTITY-BEARING", "operation id is not bounded")
    if re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z",
        recorded_at,
        re.ASCII,
    ) is None:
        _noncanonical_fail("MALFORMED", "recorded-at is not strict UTC")


def _has_valid_v3_identity(event: dict[str, Any], validator: Any) -> bool:
    event_id = event.get("eventId")
    operation_id = event.get("operationId")
    fingerprint = event.get("fingerprint")
    prior_head = event.get("priorHead")
    return bool(
        isinstance(event_id, str)
        and validator.SCRATCH_IDENTIFIER_RE.fullmatch(event_id)
        and len(event_id) <= 128
        and isinstance(operation_id, str)
        and validator.SCRATCH_IDENTIFIER_RE.fullmatch(operation_id)
        and len(operation_id) <= 128
        and isinstance(fingerprint, str)
        and validator.SHA256_RE.fullmatch(fingerprint)
        and (
            prior_head == "GENESIS"
            or (
                isinstance(prior_head, str)
                and validator.SHA256_RE.fullmatch(prior_head)
            )
        )
    )


def _validate_noncanonical_history(
    item: Path, ledger_bytes: bytes, validator: Any
) -> tuple[dict[str, Any], ...]:
    parse_errors: list[str] = []
    events = validator.load_jsonl(
        item / "agent-runs.jsonl", parse_errors, None, ledger_bytes
    )
    if parse_errors:
        _noncanonical_fail("MALFORMED", "; ".join(parse_errors))

    for event in events:
        event_errors: list[str] = []
        if validator.validate_event(dict(event), item, set(), event_errors):
            _noncanonical_fail(
                "CURRENT-EVENT", "history contains a current-schema-valid event"
            )
        schema_version = event.get("schemaVersion")
        if schema_version in (1, 2, 3):
            _noncanonical_fail(
                "CURRENT-EVENT", f"history declares schemaVersion {schema_version}"
            )
        run_id = event.get("runId")
        if isinstance(run_id, str) and run_id.strip() and len(run_id) >= 8:
            _noncanonical_fail(
                "IDENTITY-BEARING", "history contains a valid V1/V2 runId identity"
            )
        if _has_valid_v3_identity(event, validator):
            _noncanonical_fail(
                "IDENTITY-BEARING", "history contains a complete valid V3 identity"
            )
    return tuple(events)


def _noncanonical_history_marker(
    item: Path,
    expected_sha256: str,
    original_bytes: bytes,
    operation_id: str,
    recorded_at: str,
) -> dict[str, Any]:
    history_name = f"agent-runs.history.{expected_sha256}.jsonl"
    return {
        "schemaVersion": 2,
        "runId": f"ledger-history-{operation_id}",
        "workItem": item.name,
        "role": "lead",
        "executionRole": "main",
        "status": "completed",
        "gate": "none",
        "scope": ["ledger-recovery:noncanonical-history-seal"],
        "eventKind": "standalone",
        "startedAt": recorded_at,
        "updatedAt": recorded_at,
        "notes": (
            f"opaqueHistoryPath={history_name} "
            f"opaqueHistorySha256={expected_sha256} "
            f"opaqueHistoryBytes={len(original_bytes)} authority=none"
        ),
    }


def _noncanonical_is_reparse(metadata: os.stat_result) -> bool:
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(metadata, "st_file_attributes", 0) & flag)


def _noncanonical_file_identity(metadata: os.stat_result) -> tuple[int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        getattr(metadata, "st_file_attributes", 0),
    )


def _noncanonical_open_ordinary(
    path: Path,
    *,
    writable: bool,
    failure_id: str = "HISTORY-CONFLICT",
) -> tuple[int, os.stat_result]:
    try:
        before = path.lstat()
    except OSError as exc:
        _noncanonical_fail(failure_id, str(exc))
    if (
        not stat.S_ISREG(before.st_mode)
        or stat.S_ISLNK(before.st_mode)
        or _noncanonical_is_reparse(before)
    ):
        _noncanonical_fail(failure_id, f"linked or non-ordinary path: {path.name}")
    flags = (os.O_RDWR if writable else os.O_RDONLY) | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        _noncanonical_fail(failure_id, str(exc))
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or _noncanonical_is_reparse(opened)
            or _noncanonical_file_identity(before) != _noncanonical_file_identity(opened)
        ):
            _noncanonical_fail(failure_id, f"path identity changed while opening: {path.name}")
        return descriptor, opened
    except BaseException:
        os.close(descriptor)
        raise


def _noncanonical_read_owned_bytes(path: Path, *, failure_id: str) -> bytes:
    descriptor, opened = _noncanonical_open_ordinary(
        path, writable=False, failure_id=failure_id
    )
    if getattr(opened, "st_nlink", 1) != 1:
        os.close(descriptor)
        _noncanonical_fail(failure_id, f"path has extra hardlinks: {path.name}")
    try:
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            return stream.read()
    except OSError as exc:
        _noncanonical_fail(failure_id, str(exc))
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _read_exact_history_blob(path: Path, expected_sha256: str) -> bytes | None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        _noncanonical_fail("HISTORY-CONFLICT", str(exc))
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or _noncanonical_is_reparse(metadata)
    ):
        _noncanonical_fail("HISTORY-CONFLICT", "history blob is linked or non-ordinary")
    # A crash after os.link() but before staging cleanup leaves exactly the
    # history name plus its owned staging name on the same inode. Admit only that
    # known two-link crash state; an arbitrary external hardlink is not authority.
    links = getattr(metadata, "st_nlink", 1)
    if links != 1:
        staging = path.parent / f".{path.name}.tmp"
        try:
            staging_metadata = staging.lstat()
        except OSError as exc:
            _noncanonical_fail("HISTORY-CONFLICT", "history blob has an unowned hardlink")
        if (
            links != 2
            or not stat.S_ISREG(staging_metadata.st_mode)
            or stat.S_ISLNK(staging_metadata.st_mode)
            or _noncanonical_is_reparse(staging_metadata)
            or (metadata.st_dev, metadata.st_ino) != (staging_metadata.st_dev, staging_metadata.st_ino)
        ):
            _noncanonical_fail("HISTORY-CONFLICT", "history blob has an unowned hardlink")
    descriptor, _opened = _noncanonical_open_ordinary(path, writable=False)
    try:
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            value = stream.read()
    except OSError as exc:
        _noncanonical_fail("HISTORY-CONFLICT", str(exc))
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if hashlib.sha256(value).hexdigest() != expected_sha256:
        _noncanonical_fail("HISTORY-CONFLICT", "history blob digest changed")
    return value


def _cleanup_owned_history_staging(history_path: Path, staging: Path) -> None:
    try:
        staging_metadata = staging.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        _noncanonical_fail("HISTORY-CONFLICT", str(exc))
    try:
        history_metadata = history_path.lstat()
    except OSError as exc:
        _noncanonical_fail("HISTORY-CONFLICT", str(exc))
    if (
        not stat.S_ISREG(history_metadata.st_mode)
        or stat.S_ISLNK(history_metadata.st_mode)
        or _noncanonical_is_reparse(history_metadata)
        or not stat.S_ISREG(staging_metadata.st_mode)
        or stat.S_ISLNK(staging_metadata.st_mode)
        or _noncanonical_is_reparse(staging_metadata)
        or getattr(history_metadata, "st_nlink", 1) != 2
        or getattr(staging_metadata, "st_nlink", 1) != 2
        or (history_metadata.st_dev, history_metadata.st_ino)
        != (staging_metadata.st_dev, staging_metadata.st_ino)
    ):
        _noncanonical_fail(
            "HISTORY-CONFLICT", "reserved history staging path conflicts"
        )
    try:
        staging.unlink()
    except OSError as exc:
        _noncanonical_fail("HISTORY-CONFLICT", str(exc))


def _write_exact_staging_file(path: Path, expected: bytes) -> None:
    def accept_existing() -> None:
        descriptor, opened = _noncanonical_open_ordinary(path, writable=False)
        if getattr(opened, "st_nlink", 1) != 1:
            os.close(descriptor)
            _noncanonical_fail("HISTORY-CONFLICT", f"staging path has extra hardlinks: {path.name}")
        try:
            with os.fdopen(descriptor, "rb") as stream:
                actual = stream.read()
        except OSError as exc:
            _noncanonical_fail("HISTORY-CONFLICT", str(exc))
        if actual != expected:
            _noncanonical_fail("HISTORY-CONFLICT", f"staging path conflicts: {path.name}")

    try:
        path.lstat()
    except FileNotFoundError:
        pass
    except OSError as exc:
        _noncanonical_fail("HISTORY-CONFLICT", str(exc))
    else:
        accept_existing()
        return

    descriptor = None
    flags = os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or _noncanonical_is_reparse(opened)
            or getattr(opened, "st_nlink", 1) != 1
        ):
            _noncanonical_fail("HISTORY-CONFLICT", f"created staging path is not ordinary: {path.name}")
        with os.fdopen(descriptor, "w+b") as stream:
            descriptor = None
            stream.write(expected)
            stream.flush()
            os.fsync(stream.fileno())
            stream.seek(0)
            if stream.read() != expected:
                _noncanonical_fail("HISTORY-CONFLICT", f"staging readback changed: {path.name}")
    except FileExistsError:
        accept_existing()
    except OSError as exc:
        _noncanonical_fail("HISTORY-CONFLICT", str(exc))
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _publish_noncanonical_history_blob(
    item: Path, history_path: Path, expected_sha256: str, original_bytes: bytes
) -> None:
    staging = item / f".{history_path.name}.tmp"
    existing = _read_exact_history_blob(history_path, expected_sha256)
    if existing is not None:
        if existing != original_bytes:
            _noncanonical_fail("HISTORY-CONFLICT", "history blob bytes changed")
        _cleanup_owned_history_staging(history_path, staging)
        return
    _write_exact_staging_file(staging, original_bytes)
    try:
        try:
            os.link(staging, history_path, follow_symlinks=False)
        except FileExistsError:
            existing = _read_exact_history_blob(history_path, expected_sha256)
            if existing is None:
                _noncanonical_fail(
                    "HISTORY-CONFLICT", "history publication raced without a file"
                )
        published = _read_exact_history_blob(history_path, expected_sha256)
        if published != original_bytes:
            _noncanonical_fail("HISTORY-CONFLICT", "history blob bytes changed")
    except OSError as exc:
        _noncanonical_fail("HISTORY-CONFLICT", str(exc))
    _cleanup_owned_history_staging(history_path, staging)


def _noncanonical_recovery_state(
    item: Path,
    expected_sha256: str,
    operation_id: str,
    recorded_at: str,
    validator: Any,
) -> tuple[str, bytes, Path, bytes]:
    ledger_path = item / "agent-runs.jsonl"
    history_path = item / f"agent-runs.history.{expected_sha256}.jsonl"
    current = _noncanonical_read_owned_bytes(ledger_path, failure_id="DRIFT")
    history = _read_exact_history_blob(history_path, expected_sha256)
    original = history if history is not None else current
    _validate_noncanonical_history(item, original, validator)
    marker = _noncanonical_history_marker(
        item, expected_sha256, original, operation_id, recorded_at
    )
    marker_bytes = (serialize_event(marker) + "\n").encode("utf-8")
    if current == marker_bytes and history is not None:
        return "applied", original, history_path, marker_bytes
    if current == original and hashlib.sha256(current).hexdigest() == expected_sha256:
        return "original", original, history_path, marker_bytes
    return "other", original, history_path, marker_bytes


def _validate_noncanonical_marker_candidate(
    item: Path, candidate: Path, validator: Any
) -> None:
    errors = validator.validate_work_item(
        item, ledger_path=candidate, strict_revise=False
    )
    if errors:
        _noncanonical_fail("CANDIDATE-INVALID", "; ".join(errors))


def _command_apply_noncanonical_history(
    item: Path,
    expected_sha256: str,
    operation_id: str,
    recorded_at: str,
    validator: Any,
    inject_failure: str | None,
) -> tuple[bool, Path]:
    state, original, history_path, marker_bytes = _noncanonical_recovery_state(
        item, expected_sha256, operation_id, recorded_at, validator
    )
    if state == "applied":
        return True, history_path
    if state != "original":
        _noncanonical_fail("DRIFT", "ledger digest or recovery marker changed")

    ledger_path = item / "agent-runs.jsonl"
    candidate = ledger_path.with_suffix(".jsonl.tmp")
    replaced = False
    try:
        _write_exact_staging_file(candidate, marker_bytes)
        _validate_noncanonical_marker_candidate(item, candidate, validator)
        _publish_noncanonical_history_blob(
            item, history_path, expected_sha256, original
        )
        if inject_failure == "post-history-publish":
            print("FAIL: injected post-history-publish interruption", file=sys.stderr)
            return False, history_path
        if inject_failure == "pre-ledger-replace":
            print("FAIL: injected pre-ledger-replace interruption", file=sys.stderr)
            return False, history_path
        os.replace(candidate, ledger_path)
        replaced = True
        if inject_failure == "post-ledger-replace-readback":
            _noncanonical_fail(
                "READBACK-INDETERMINATE", "injected post-replace readback failure"
            )
        actual = _noncanonical_read_owned_bytes(
            ledger_path, failure_id="READBACK-INDETERMINATE"
        )
        if actual != marker_bytes:
            _noncanonical_fail("READBACK-INDETERMINATE", "marker readback changed")
    except OSError as exc:
        if replaced:
            _noncanonical_fail("READBACK-INDETERMINATE", str(exc))
        _noncanonical_fail("CANDIDATE-INVALID", str(exc))
    finally:
        if not replaced:
            candidate.unlink(missing_ok=True)
    return False, history_path


def _command_rollback_noncanonical_history(
    item: Path,
    expected_sha256: str,
    operation_id: str,
    recorded_at: str,
    validator: Any,
    inject_failure: str | None,
) -> tuple[bool, Path]:
    state, original, history_path, marker_bytes = _noncanonical_recovery_state(
        item, expected_sha256, operation_id, recorded_at, validator
    )
    if state == "original":
        if history_path.exists():
            return True, history_path
        _noncanonical_fail("ROLLBACK-NOT-EMPTY", "recovery marker is absent")
    if state != "applied":
        _noncanonical_fail(
            "ROLLBACK-NOT-EMPTY", "rollback is frozen after a later append"
        )

    ledger_path = item / "agent-runs.jsonl"
    current = _noncanonical_read_owned_bytes(
        ledger_path, failure_id="ROLLBACK-NOT-EMPTY"
    )
    if current != marker_bytes:
        _noncanonical_fail(
            "ROLLBACK-NOT-EMPTY", "rollback is frozen after a later append"
        )
    candidate = ledger_path.with_suffix(".jsonl.tmp")
    replaced = False
    try:
        _write_exact_staging_file(candidate, original)
        if inject_failure == "pre-ledger-replace":
            print("FAIL: injected pre-ledger-replace interruption", file=sys.stderr)
            return False, history_path
        os.replace(candidate, ledger_path)
        replaced = True
        if inject_failure == "post-ledger-replace-readback":
            _noncanonical_fail(
                "READBACK-INDETERMINATE", "injected rollback readback failure"
            )
        actual = _noncanonical_read_owned_bytes(
            ledger_path, failure_id="READBACK-INDETERMINATE"
        )
        if actual != original:
            _noncanonical_fail("READBACK-INDETERMINATE", "rollback readback changed")
    except OSError as exc:
        if replaced:
            _noncanonical_fail("READBACK-INDETERMINATE", str(exc))
        _noncanonical_fail("CANDIDATE-INVALID", str(exc))
    finally:
        if not replaced:
            candidate.unlink(missing_ok=True)
    return False, history_path


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


def command_recover_noncanonical_history(args: argparse.Namespace) -> int:
    item = active_work_item(args, "recover-noncanonical-history")
    if item is None or not item.exists():
        print(f"FAIL: missing work item: {item}", file=sys.stderr)
        return 1
    try:
        expected_sha256 = _normalize_noncanonical_sha256(
            args.expected_ledger_sha256
        )
        _strict_noncanonical_inputs(args.operation_id, args.recorded_at)
        validator = load_validator()
        if not args.apply_admitted and not args.rollback_admitted:
            state, _original, history_path, marker_bytes = _noncanonical_recovery_state(
                item,
                expected_sha256,
                args.operation_id,
                args.recorded_at,
                validator,
            )
            if state == "other":
                _noncanonical_fail("DRIFT", "ledger digest or recovery marker changed")
            marker_errors: list[str] = []
            marker_event = json.loads(marker_bytes)
            validator.validate_event(marker_event, item, set(), marker_errors)
            validator.validate_status(item, [marker_event], marker_errors)
            if marker_errors:
                _noncanonical_fail("CANDIDATE-INVALID", "; ".join(marker_errors))
            print(
                f"{NONCANONICAL_HISTORY_SUCCESS_MARKER} action=preflight "
                f"state={state} history={history_path.name}"
            )
            return 0
        try:
            with ledger_write_lock(item):
                if args.apply_admitted:
                    replay, history_path = _command_apply_noncanonical_history(
                        item,
                        expected_sha256,
                        args.operation_id,
                        args.recorded_at,
                        validator,
                        args.inject_failure,
                    )
                    action = "apply"
                else:
                    replay, history_path = _command_rollback_noncanonical_history(
                        item,
                        expected_sha256,
                        args.operation_id,
                        args.recorded_at,
                        validator,
                        args.inject_failure,
                    )
                    action = "rollback"
        except LedgerWriteLockError as exc:
            _noncanonical_fail("LOCKED", str(exc))
        if args.apply_admitted and args.inject_failure in {
            "post-history-publish",
            "pre-ledger-replace",
        }:
            return 1
        if args.rollback_admitted and args.inject_failure == "pre-ledger-replace":
            return 1
        print(
            f"{NONCANONICAL_HISTORY_SUCCESS_MARKER} action={action} "
            f"replay={str(replay).lower()} history={history_path.name}"
        )
        return 0
    except LedgerNoncanonicalRecoveryError as exc:
        print(f"FAIL: {exc.failure_id}: {exc}", file=sys.stderr)
        return 1


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


def _append_event_transaction(
    item: Path, validator: Any, event_factory: Any
) -> bool:
    """Append one validator-approved event, or report an idempotent no-op.

    The factory runs while the ledger lock is held so a launch lookup and its
    terminal append observe one indivisible ledger state.
    """
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
        event = event_factory(previous)
        if event is None:
            return False
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
            raise ValueError("; ".join(errors))
        os.replace(candidate, ledger_path)
    finally:
        os.close(lock_fd)
        lock_path.unlink(missing_ok=True)

    return True


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
        _append_event_transaction(item, validator, lambda _previous: event)
    except ValueError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print(f"{APPEND_SUCCESS_MARKER} ({item / 'agent-runs.jsonl'})")
    return 0


def _settlement_event(
    args: argparse.Namespace, launch: dict[str, Any], validator: Any
) -> dict[str, Any]:
    if args.status in {"planned", "running"}:
        raise ValueError(
            "WI-LEDGER-SETTLE-TARGET: terminal status must not be planned or running"
        )

    immutable = {
        "work_item_name": launch.get("workItem"),
        "role": launch.get("role"),
        "execution_role": launch.get("executionRole"),
        "assigned_role": launch.get("assignedRole"),
        "provider": launch.get("provider"),
        "model": launch.get("model"),
        "scope": launch.get("scope"),
        "prompt_file": launch.get("promptFile"),
        "effort": launch.get("effort"),
        "launch_flags_json": (
            json.dumps(launch["launchFlags"], separators=(",", ":"))
            if "launchFlags" in launch
            else None
        ),
    }
    if not isinstance(immutable["work_item_name"], str) or not isinstance(
        immutable["role"], str
    ) or not isinstance(immutable["execution_role"], str) or not isinstance(
        immutable["scope"], list
    ):
        raise ValueError(
            "WI-LEDGER-SETTLE-TARGET: launch lacks immutable event metadata"
        )

    terminal = argparse.Namespace(**vars(args), **immutable)
    terminal.event_kind = "terminal"
    terminal.closes = None
    return build_event(terminal, validator)


def _settle_launch_from_ledger(
    previous: str, args: argparse.Namespace, validator: Any
) -> dict[str, Any] | None:
    try:
        events = [json.loads(line) for line in previous.splitlines() if line.strip()]
    except json.JSONDecodeError as exc:
        raise ValueError(
            "WI-LEDGER-SETTLE-TARGET: existing ledger is not valid JSONL"
        ) from exc
    launches = [event for event in events if event.get("runId") == args.launch_run_id]
    if len(launches) != 1 or launches[0].get("eventKind") != "launch":
        raise ValueError(
            "WI-LEDGER-SETTLE-TARGET: launch must identify one V2 launch event"
        )
    terminals = [
        event
        for event in events
        if event.get("eventKind") == "terminal"
        and event.get("launchRunId") == args.launch_run_id
    ]
    if len(terminals) > 1:
        raise ValueError(
            "WI-LEDGER-SETTLE-TARGET: launch has multiple terminal events"
        )

    event = _settlement_event(args, launches[0], validator)
    if terminals:
        if terminals[0] == event:
            return None
        raise ValueError(
            "WI-LEDGER-SETTLE-CONFLICT: launch already has a different terminal event"
        )
    return event


def command_settle_launch(args: argparse.Namespace) -> int:
    item = active_work_item(args, "settle-launch")
    if item is None or not item.exists():
        print(f"FAIL: missing work item: {item}", file=sys.stderr)
        return 1
    validator = load_validator()
    try:
        appended = _append_event_transaction(
            item,
            validator,
            lambda previous: _settle_launch_from_ledger(previous, args, validator),
        )
    except ValueError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    if appended:
        print(f"{SETTLE_SUCCESS_MARKER} ({item / 'agent-runs.jsonl'})")
    else:
        print(f"{SETTLE_ALREADY_MARKER} ({item / 'agent-runs.jsonl'})")
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
    decoded, _ = _read_ledger(item, validator)
    if any(event.get("schemaVersion") == 3 for event in decoded):
        print("FAIL: legacy V1/V2 writer refuses a ledger containing schemaVersion 3")
        return 1

    def validate_candidate(candidate: Path, _expected: bytes) -> list[str]:
        return validator.validate_work_item(
            item, ledger_path=candidate, strict_revise=False
        )

    return _commit_recovery_append(
        item,
        event,
        validate_candidate,
        RECOVERY_SUCCESS_MARKER,
        args.inject_failure,
    )


def _commit_recovery_append(
    item: Path,
    event: dict[str, Any],
    validate_candidate: Callable[[Path, bytes], list[str] | tuple[str, ...]],
    success_marker: str,
    inject_failure: str | None,
    *,
    replay_detector: Callable[[bytes], bool] | None = None,
) -> int:
    """Commit one validated recovery row through the existing atomic append path."""

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
        if replay_detector is not None and replay_detector(previous):
            print(f"{success_marker} ({ledger_path})")
            return 0
        line = (serialize_event(event) + "\n").encode("utf-8")
        prefix = b"" if not previous or previous.endswith(b"\n") else b"\n"
        expected = previous + prefix + line
        with candidate.open("xb") as stream:
            stream.write(expected)
            stream.flush()
        errors = validate_candidate(candidate, expected)
        if errors:
            for error in errors:
                print(f"FAIL: {error}")
            print(f"RESULT: FAIL ({len(errors)} errors)")
            return 1
        if inject_failure == "pre-replace":
            print("FAIL: ledger-recovery:pre-replace-injected")
            return 1
        os.replace(candidate, ledger_path)
        replaced = True
        if inject_failure == "post-replace-readback":
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
    print(f"{success_marker} ({ledger_path})")
    return 0


def command_dispose_invalid_current(args: argparse.Namespace) -> int:
    item = active_work_item(args, "dispose-invalid-current")
    if item is None or not item.exists():
        print(f"FAIL: missing work item: {item}")
        return 1
    validator = load_validator()
    try:
        manifest_bytes = args.ledger_manifest.read_bytes()
    except OSError as exc:
        print(f"FAIL: WI-LEDGER-COMPAT-SUFFIX-DISPOSITION-TARGET: {exc}")
        return 1
    decoded, _malformed = _read_ledger(item, validator)
    existing = [event for event in decoded if event.get("runId") == args.run_id]
    existing_disposition = existing[0] if len(existing) == 1 else None
    if (
        isinstance(existing_disposition, dict)
        and existing_disposition.get("invalidationMode")
        == "invalid-current-nonauthorizing"
        and args.started_at is None
        and args.updated_at is None
    ):
        started_at = existing_disposition.get("startedAt")
        updated_at = existing_disposition.get("updatedAt")
    else:
        started_at = args.started_at or utc_timestamp()
        updated_at = args.updated_at or started_at
    event = {
        "schemaVersion": 2,
        "runId": args.run_id,
        "workItem": item.name,
        "role": "lead",
        "executionRole": "main",
        "status": "completed",
        "gate": "none",
        "scope": ["ledger-recovery:invalid-current-nonauthorizing"],
        "eventKind": "closure-invalidation",
        "invalidationMode": "invalid-current-nonauthorizing",
        "invalidatesRawLineOrdinal": args.target_raw_line_ordinal,
        "invalidatesRunId": args.target_run_id,
        "invalidatesEventSha256": args.target_event_sha256,
        "authorizing": False,
        "evidence": [parse_evidence(value) for value in args.evidence],
        "startedAt": started_at,
        "updatedAt": updated_at,
    }

    def validate_candidate(_candidate: Path, expected: bytes) -> tuple[str, ...]:
        return validator.validate_invalid_current_disposition_candidate(
            item,
            expected,
            event,
            ledger_manifest_bytes=manifest_bytes,
        )

    def is_replay(previous: bytes) -> bool:
        replay_errors: list[str] = []
        current = validator.load_jsonl(
            item / "agent-runs.jsonl", replay_errors, None, previous
        )
        return not replay_errors and any(candidate == event for candidate in current) and not (
            validator.validate_invalid_current_disposition_candidate(
                item,
                previous,
                event,
                ledger_manifest_bytes=manifest_bytes,
            )
        )

    return _commit_recovery_append(
        item,
        event,
        validate_candidate,
        INVALID_CURRENT_DISPOSITION_SUCCESS_MARKER,
        args.inject_failure,
        replay_detector=is_replay,
    )


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

    settle = subparsers.add_parser(
        "settle-launch",
        help="Append one terminal event derived from a unique open V2 launch.",
    )
    settle.add_argument("--launch-run-id", required=True)
    settle.add_argument("--run-id", required=True)
    settle.add_argument("--status", required=True)
    settle.add_argument("--gate", required=True)
    settle.add_argument("--artifact")
    settle.add_argument("--evidence", action="append")
    settle.add_argument("--evidence-json", action="append")
    settle.add_argument("--scratch-evidence-json", action="append")
    settle.add_argument("--started-at", required=True)
    settle.add_argument("--updated-at", required=True)
    settle.add_argument("--notes")
    settle.add_argument(
        "--terminal-class",
        choices=["external-nonauthorizing", "internal-authorizing"],
    )
    settle.add_argument("--authorizing", choices=["true", "false"])
    settle.add_argument(
        "--actual-execution-path", choices=["direct-external-cli", "internal"]
    )
    settle.add_argument("--artifact-identity")
    settle.add_argument("--external-dispatch-id")
    settle.add_argument("--external-evidence-run-id")
    settle.add_argument("--effort-mapping-loss")
    settle.add_argument("--closer-run-id")
    settle.add_argument("--target-tuple-json")
    settle.set_defaults(func=command_settle_launch)

    recovery = subparsers.add_parser("recover-invalid-closure", help="Append one digest-bound V2 closure invalidation")
    recovery.add_argument("--run-id", required=True)
    recovery.add_argument("--target-run-id", required=True)
    recovery.add_argument("--target-event-sha256", required=True)
    recovery.add_argument("--evidence", action="append", required=True)
    recovery.add_argument("--started-at")
    recovery.add_argument("--updated-at")
    recovery.add_argument("--inject-failure", choices=["pre-replace", "post-replace-readback"], help=argparse.SUPPRESS)
    recovery.set_defaults(func=command_recover_invalid_closure)

    disposition = subparsers.add_parser(
        "dispose-invalid-current",
        help="Append one exact nonauthorizing invalid-current suffix disposition",
    )
    disposition.add_argument("--run-id", required=True)
    disposition.add_argument("--target-run-id", required=True)
    disposition.add_argument("--target-raw-line-ordinal", type=int, required=True)
    disposition.add_argument("--target-event-sha256", required=True)
    disposition.add_argument("--ledger-manifest", type=Path, required=True)
    disposition.add_argument("--evidence", action="append", required=True)
    disposition.add_argument("--started-at")
    disposition.add_argument("--updated-at")
    disposition.add_argument(
        "--inject-failure",
        choices=["pre-replace", "post-replace-readback"],
        help=argparse.SUPPRESS,
    )
    disposition.set_defaults(func=command_dispose_invalid_current)

    noncanonical = subparsers.add_parser(
        "recover-noncanonical-history",
        help="Seal one exact noncanonical ledger as inert history and start a canonical ledger",
    )
    noncanonical.add_argument("--expected-ledger-sha256", required=True)
    noncanonical.add_argument("--operation-id", required=True)
    noncanonical.add_argument("--recorded-at", required=True)
    action = noncanonical.add_mutually_exclusive_group()
    action.add_argument("--apply-admitted", action="store_true")
    action.add_argument("--rollback-admitted", action="store_true")
    noncanonical.add_argument(
        "--inject-failure",
        choices=[
            "post-history-publish",
            "pre-ledger-replace",
            "post-ledger-replace-readback",
        ],
        help=argparse.SUPPRESS,
    )
    noncanonical.set_defaults(func=command_recover_noncanonical_history)

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
