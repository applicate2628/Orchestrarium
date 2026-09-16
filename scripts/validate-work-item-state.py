#!/usr/bin/env python3
import argparse
import base64
import copy
import hashlib
import io
import importlib.util
import itertools
import json
import os
import re
import stat as stat_module
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Literal, Mapping, Sequence


STATUS_VALUES = {"planned", "running", "completed", "revise", "blocked", "cancelled"}
USER_WAIVER_GATE = "WAIVED:user"
SECURITY_REVIEWER_WAIVER_GATE = "WAIVED:security-reviewer"
GATE_VALUES = {
    "PASS",
    "REVISE",
    "BLOCKED:dependency",
    "BLOCKED:prerequisite",
    "advisory",
    "none",
    USER_WAIVER_GATE,
    SECURITY_REVIEWER_WAIVER_GATE,
}
CLOSURE_GATES = {"PASS", USER_WAIVER_GATE, SECURITY_REVIEWER_WAIVER_GATE}
# --- v2 REVISE-closure vocabulary (decision 2026-07-16-review-verdict-closure, minimal slice) ---
EVENT_KINDS = {"launch", "terminal", "standalone", "closure-invalidation", "legacy-obligation-migration"}
EFFORT_ORDER = ["low", "medium", "high", "xhigh", "max"]  # ordered, ascending strength
DECLARED_EFFORTS = frozenset((*EFFORT_ORDER, "unsupported"))
FINDING_CLASSES = {"publication-safety", "security", "correctness", "performance", "other", "legacy-unclassified"}
PROTECTED_CLASSES = {"publication-safety", "security", "legacy-unclassified"}  # non-user-waivable (spine: $security-reviewer only)
LEGACY_MIGRATION_KIND = "legacy-obligation-migration"
LEGACY_MIGRATION_SCOPE = ["ledger-migration:invalid-finding-class"]
LEGACY_MIGRATION_NORMALIZATIONS = {
    "invalid-finding-class": {
        "scope": ["ledger-migration:invalid-finding-class"],
        "evidence": "invalid-finding-class {target} {digest} -> legacy-unclassified",
    },
    "remove-string-scratch-evidence": {
        "scope": ["ledger-migration:remove-string-scratch-evidence"],
        "evidence": "remove-string-scratch-evidence {target} {digest} -> scratchEvidence absent",
    },
}
LEDGER_EVENT_FINDING_CLASS_INVALID = "LEDGER-EVENT-FINDING-CLASS-INVALID"
LEDGER_EVENT_SCRATCH_EVIDENCE_INVALID = "LEDGER-EVENT-SCRATCH-EVIDENCE-INVALID"
LEGACY_MIGRATION_V3_UNSUPPORTED = "WI-LEDGER-MIGRATION-V3-UNSUPPORTED"
V2_ONLY_FIELDS = {
    "eventKind",
    "launchRunId",
    "closesRunIds",
    "artifactRevision",
    "lane",
    "effort",
    "findingClass",
    "scratchEvidence",
    "invalidatesRunId",
    "invalidatesEventSha256",
    "invalidationMode",
    "invalidatesRawLineOrdinal",
    "migrationAction",
    "normalizationKind",
    "migratesRunId",
    "migratesEventSha256",
    "revokesMigrationRunId",
    "revokesMigrationEventSha256",
    "replacementEvent",
    "terminalClass",
    "authorizing",
    "actualExecutionPath",
    "artifactIdentity",
    "externalDispatchId",
    "externalEvidenceRunId",
    "effortMappingLoss",
    "launchFlags",
    "closerRunId",
    "targetTuple",
}
V3_ALLOWED_FIELDS = {
    "schemaVersion",
    "eventId",
    "operationId",
    "fingerprint",
    "priorHead",
    "recordedAt",
    "eventType",
    "payload",
}
V3_REQUIRED_FIELDS = V3_ALLOWED_FIELDS
# Canonical executionRole values (mirrors shared/schemas/agent-runs.schema.json).
# There is exactly ONE main-conversation identity: "main". The main conversation
# also holds the Lead role — orchestration weight is the status.md
# `orchestration: light | full-lead` field, never a second executionRole value.
EXECUTION_ROLES = {"main", "internal", "consultant", "external-worker", "external-reviewer", "external-brigade", "none"}
# Legacy READ-mapping: ledgers written before 2026-07-11 may carry "lead" as the
# executionRole; it reads as "main" (same owner). Read-side acceptance only —
# NEW writes must use "main" (scripts/agent-run-ledger.py rejects legacy values).
LEGACY_EXECUTION_ROLES = {"lead": "main"}
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
    # v2 closure fields
    "eventKind",
    "launchRunId",
    "closesRunIds",
    "artifactRevision",
    "lane",
    "effort",
    "findingClass",
    "scratchEvidence",
    "invalidatesRunId",
    "invalidatesEventSha256",
    "invalidationMode",
    "invalidatesRawLineOrdinal",
    "migrationAction",
    "normalizationKind",
    "migratesRunId",
    "migratesEventSha256",
    "revokesMigrationRunId",
    "revokesMigrationEventSha256",
    "replacementEvent",
    "terminalClass",
    "authorizing",
    "actualExecutionPath",
    "artifactIdentity",
    "externalDispatchId",
    "externalEvidenceRunId",
    "effortMappingLoss",
    "launchFlags",
    "closerRunId",
    "targetTuple",
}
EVIDENCE_ALLOWED_FIELDS = {"kind", "ref", "result"}
AGENT_RUN_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "shared" / "schemas" / "agent-runs.schema.json"
AGENT_RUN_SCHEMA = json.loads(AGENT_RUN_SCHEMA_PATH.read_text(encoding="utf-8"))
_LAUNCH_FLAGS_SCHEMA = AGENT_RUN_SCHEMA["properties"]["launchFlags"]
LAUNCH_FLAGS_MAX_COUNT = _LAUNCH_FLAGS_SCHEMA["maxItems"]
LAUNCH_FLAGS_MAX_TOKEN_BYTES = 2048
LAUNCH_FLAGS_MAX_TOTAL_BYTES = 16 * 1024
_MODEL_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$", re.ASCII)
_CLAUDE_TOOL_LIST = re.compile(
    r"^[A-Za-z][A-Za-z0-9_*:-]*(?:,[A-Za-z][A-Za-z0-9_*:-]*)*$",
    re.ASCII,
)
_CODEX_SANDBOXES = frozenset({"read-only", "workspace-write", "danger-full-access"})
_CLAUDE_IO_FORMATS = frozenset({"text", "json", "stream-json"})
_CLAUDE_PERMISSION_MODES = frozenset(
    {"default", "acceptEdits", "plan", "dontAsk", "bypassPermissions"}
)
V3_EVENT_TYPES = set(AGENT_RUN_SCHEMA["properties"]["eventType"]["enum"])
_SCRATCH_SCHEMA = AGENT_RUN_SCHEMA["properties"]["scratchEvidence"]
_SCRATCH_ITEM_SCHEMA = _SCRATCH_SCHEMA["items"]
_SCRATCH_PROPERTIES = _SCRATCH_ITEM_SCHEMA["properties"]
_JSONL_SCHEMA = AGENT_RUN_SCHEMA["x-orchestrarium-jsonl"]
SCRATCH_EVIDENCE_ALLOWED_FIELDS = set(_SCRATCH_PROPERTIES)
SCRATCH_EVIDENCE_REQUIRED_FIELDS = set(_SCRATCH_ITEM_SCHEMA["required"])
SCRATCH_PROOF_FIELDS = {
    alternative["properties"]["kind"]["const"]: set(alternative["required"])
    for alternative in _SCRATCH_PROPERTIES["proof"]["oneOf"]
}
MAX_SCRATCH_EVIDENCE_ENTRIES = _SCRATCH_SCHEMA["maxItems"]
MAX_SCRATCH_EVIDENCE_JSON_BYTES = _SCRATCH_SCHEMA["x-orchestrarium-maxRawUtf8Bytes"]
MAX_SCRATCH_ENTRY_ID_LENGTH = _SCRATCH_PROPERTIES["entryId"]["maxLength"]
MAX_SCRATCH_PATH_LENGTH = _SCRATCH_PROPERTIES["path"]["maxLength"]
MAX_SCRATCH_REASON_LENGTH = _SCRATCH_PROPERTIES["reason"]["maxLength"]
MAX_SCRATCH_POINTER_LENGTH = _SCRATCH_PROPERTIES["canonicalPointer"]["maxLength"]
_ACCEPTED_ARTIFACT_SCHEMA = next(
    alternative
    for alternative in _SCRATCH_PROPERTIES["proof"]["oneOf"]
    if alternative["properties"]["kind"]["const"] == "accepted-artifact"
)
MAX_SCRATCH_PRODUCER_LENGTH = _ACCEPTED_ARTIFACT_SCHEMA["properties"]["producer"]["maxLength"]
MAX_SCRATCH_REPRODUCE_LENGTH = _ACCEPTED_ARTIFACT_SCHEMA["properties"]["reproduce"]["maxLength"]
MAX_LEDGER_LINE_CHARS = _JSONL_SCHEMA["maxLineChars"]
MAX_LEDGER_LINE_BYTES = _JSONL_SCHEMA["maxLineBytes"]
MAX_LEDGER_EVENTS = _JSONL_SCHEMA["maxEvents"]
MAX_JSON_NESTING_DEPTH = _JSONL_SCHEMA["maxNestingDepth"]
MAX_TRANSFER_RECEIPT_BYTES = 4 * 1024 * 1024
SCRATCH_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", re.ASCII)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.ASCII)
QUICK_FIX_TEMPLATE = "quick-fix"
STAGED_TEMPLATE = "staged"
QUICK_FIX_LIFECYCLE_FIELDS = ("template", "status", "started", "updated")
QUICK_FIX_RECOVERY_FIELDS = ("Task", "Current step", "Last result", "Next action")
FULL_STATUS_SECTIONS = ("## Current state", "## Active agents", "## Completed agents", "## Next action")
QUICK_FIX_FACT_RE = re.compile(
    r"\s*-\s*\*\*(Task|Current step|Last result|Next action)\*\*\s*:\s*(.*?)\s*",
    re.IGNORECASE,
)
QUICK_FIX_RECOVERY_FIELD_BY_CASEFOLD = {
    field.casefold(): field for field in QUICK_FIX_RECOVERY_FIELDS
}
_LIFECYCLE_OWNER = None
_SOLUTION_ATTEMPT_OWNER = None


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def validate_launch_profile(
    provider: object, flags: object
) -> tuple[tuple[str, ...], str, str]:
    """Validate persisted flags independently at the corruptible ledger boundary."""

    if (
        not isinstance(flags, list)
        or len(flags) > LAUNCH_FLAGS_MAX_COUNT
        or provider not in {"codex", "claude", "kimi"}
    ):
        raise ValueError("invalid launch flags")
    frozen: list[str] = []
    total = 0
    for token in flags:
        if not isinstance(token, str) or "\x00" in token or "\r" in token or "\n" in token:
            raise ValueError("invalid launch flags")
        encoded = token.encode("utf-8", errors="strict")
        total += len(encoded)
        if len(encoded) > LAUNCH_FLAGS_MAX_TOKEN_BYTES or total > LAUNCH_FLAGS_MAX_TOTAL_BYTES:
            raise ValueError("invalid launch flags")
        frozen.append(token)
    exact = tuple(frozen)
    if provider == "kimi":
        if exact:
            raise ValueError("invalid launch flags")
        return exact, "kimi-code/k3", "unsupported"

    model = ""
    effort = ""
    index = 0
    while index < len(exact):
        token = exact[index]
        if provider == "codex":
            if token == "--model" and index + 1 < len(exact):
                value = exact[index + 1]
                if _MODEL_TOKEN.fullmatch(value) is None:
                    raise ValueError("invalid launch flags")
                model = value
                index += 2
                continue
            if token == "-c" and index + 1 < len(exact):
                matched = re.fullmatch(
                    r'model_reasoning_effort="?(low|medium|high|xhigh|max)"?',
                    exact[index + 1],
                )
                if matched is None:
                    raise ValueError("invalid launch flags")
                effort = matched.group(1)
                index += 2
                continue
            if token == "--sandbox" and index + 1 < len(exact):
                if exact[index + 1] not in _CODEX_SANDBOXES:
                    raise ValueError("invalid launch flags")
                index += 2
                continue
            raise ValueError("invalid launch flags")

        if token == "-p":
            index += 1
            continue
        if token == "--model" and index + 1 < len(exact):
            value = exact[index + 1]
            if _MODEL_TOKEN.fullmatch(value) is None:
                raise ValueError("invalid launch flags")
            model = value
            index += 2
            continue
        if token == "--effort" and index + 1 < len(exact):
            value = exact[index + 1]
            if value not in EFFORT_ORDER:
                raise ValueError("invalid launch flags")
            effort = value
            index += 2
            continue
        if token in {"--input-format", "--output-format"} and index + 1 < len(exact):
            if exact[index + 1] not in _CLAUDE_IO_FORMATS:
                raise ValueError("invalid launch flags")
            index += 2
            continue
        if token == "--permission-mode" and index + 1 < len(exact):
            if exact[index + 1] not in _CLAUDE_PERMISSION_MODES:
                raise ValueError("invalid launch flags")
            index += 2
            continue
        if token in {
            "--tools", "--allowedTools", "--allowed-tools",
            "--disallowedTools", "--disallowed-tools",
        } and index + 1 < len(exact):
            if _CLAUDE_TOOL_LIST.fullmatch(exact[index + 1]) is None:
                raise ValueError("invalid launch flags")
            index += 2
            continue
        if token == "--setting-sources" and index + 1 < len(exact):
            if exact[index + 1] != "user":
                raise ValueError("invalid launch flags")
            index += 2
            continue
        raise ValueError("invalid launch flags")
    return exact, model, effort


def _kimi_empty_flags_resolved_effort(event: Mapping[str, object]) -> bool:
    return (
        event.get("provider") == "kimi"
        and event.get("launchFlags") == []
        and event.get("model") == "kimi-code/k3"
        and event.get("effort") in {"high", "max"}
    )


def load_lifecycle_owner():
    global _LIFECYCLE_OWNER
    if _LIFECYCLE_OWNER is not None:
        return _LIFECYCLE_OWNER
    owner_path = Path(__file__).with_name("mutate-work-item.py")
    spec = importlib.util.spec_from_file_location(
        "work_item_lifecycle_owner_for_validation",
        owner_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load lifecycle owner from {owner_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _LIFECYCLE_OWNER = module
    return module


def load_solution_attempt_owner():
    global _SOLUTION_ATTEMPT_OWNER
    if _SOLUTION_ATTEMPT_OWNER is not None:
        return _SOLUTION_ATTEMPT_OWNER
    owner_path = Path(__file__).with_name("solution_attempt") / "reducer.py"
    spec = importlib.util.spec_from_file_location(
        "solution_attempt_reducer_for_validation",
        owner_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load solution-attempt owner from {owner_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _SOLUTION_ATTEMPT_OWNER = module
    return module


def staged_status_fields(text: str) -> dict[str, str] | None:
    """Return lifecycle-owner parsed fields only for an explicit staged V1 status."""
    fields = load_lifecycle_owner()._parse_fields(text)
    return fields if fields.get("template") == STAGED_TEMPLATE else None


def is_staged_status(text: str) -> bool:
    return staged_status_fields(text) is not None


def validate_staged_status(text: str, errors: list[str]) -> None:
    """Validate staged V1 through the lifecycle owner; do not duplicate its field contract."""
    lifecycle = load_lifecycle_owner()
    try:
        lifecycle._validate_active_status_bytes(text.encode("utf-8"))
    except lifecycle.LifecycleError as exc:
        fail(errors, str(exc))


def is_quick_fix_status(text: str) -> bool:
    document = split_status_document(text)
    if document is None:
        return False
    frontmatter_lines, _ = document
    for line in frontmatter_lines:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip().lower() == "template" and value.strip() == QUICK_FIX_TEMPLATE:
            return True
    return False


def is_quick_fix_status_candidate(text: str) -> bool:
    if is_quick_fix_status(text):
        return True
    document = split_status_document(text)
    if document is None:
        return False
    _, body_lines = document
    recovery_fields = {
        QUICK_FIX_RECOVERY_FIELD_BY_CASEFOLD[match.group(1).casefold()]
        for line in body_lines
        if (match := QUICK_FIX_FACT_RE.fullmatch(line)) is not None
    }
    if all(field in recovery_fields for field in QUICK_FIX_RECOVERY_FIELDS):
        return True
    if any(section in text for section in FULL_STATUS_SECTIONS):
        return False
    return bool(recovery_fields)


def split_status_document(text: str) -> tuple[list[str], list[str]] | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return lines[1:index], lines[index + 1 :]
    return None


def validate_quick_fix_status(text: str, errors: list[str]) -> None:
    document = split_status_document(text)
    if document is None:
        fail(errors, "quick-fix status.md must contain closed frontmatter")
        return
    frontmatter_lines, body_lines = document

    lifecycle: dict[str, list[str]] = {}
    for line in frontmatter_lines:
        if not line.strip():
            continue
        if ":" not in line:
            fail(errors, f"quick-fix status.md unexpected frontmatter content: {line.strip()}")
            continue
        key, value = line.split(":", 1)
        lifecycle.setdefault(key.strip().lower(), []).append(value.strip())

    for field in QUICK_FIX_LIFECYCLE_FIELDS:
        values = lifecycle.get(field, [])
        if not values or not values[0]:
            fail(errors, f"quick-fix status.md missing lifecycle field: {field}")
        if len(values) > 1:
            fail(errors, f"quick-fix status.md duplicate lifecycle field: {field}")
    for field in lifecycle:
        if field not in QUICK_FIX_LIFECYCLE_FIELDS:
            fail(errors, f"quick-fix status.md unexpected lifecycle field: {field}")

    template_values = lifecycle.get("template", [])
    if len(template_values) == 1 and template_values[0] != QUICK_FIX_TEMPLATE:
        fail(errors, f"quick-fix status.md lifecycle field template must be {QUICK_FIX_TEMPLATE}")
    status_values = lifecycle.get("status", [])
    if len(status_values) == 1 and status_values[0] != "active":
        fail(errors, "quick-fix status.md lifecycle field status must be active")

    recovery: dict[str, list[str]] = {}
    for line in body_lines:
        if not line.strip():
            continue
        match = QUICK_FIX_FACT_RE.fullmatch(line)
        if match is None:
            fail(errors, f"quick-fix status.md unexpected nonblank content: {line.strip()}")
            continue
        field = QUICK_FIX_RECOVERY_FIELD_BY_CASEFOLD[match.group(1).casefold()]
        recovery.setdefault(field, []).append(match.group(2).strip())

    for field in QUICK_FIX_RECOVERY_FIELDS:
        values = recovery.get(field, [])
        if not values or not values[0]:
            fail(errors, f"quick-fix status.md missing recovery field: {field}")
        if len(values) > 1:
            fail(errors, f"quick-fix status.md duplicate recovery field: {field}")


class DuplicateJsonKeyError(ValueError):
    pass


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _json_depth(value: object) -> int:
    maximum = 0
    stack: list[tuple[object, int]] = [(value, 0)]
    while stack:
        current, depth = stack.pop()
        maximum = max(maximum, depth)
        if maximum > MAX_JSON_NESTING_DEPTH:
            return maximum
        if isinstance(current, dict):
            stack.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            stack.extend((item, depth + 1) for item in current)
    return maximum


def decode_json_object(
    raw: str | bytes,
    *,
    source: str,
    maximum_chars: int | None = None,
    maximum_bytes: int | None = None,
) -> dict:
    """Canonical bounded strict decoder for ledger and CLI JSON objects."""

    if maximum_chars is not None and len(raw) > maximum_chars:
        raise ValueError(f"{source}: JSON exceeds maximum length {maximum_chars}")
    if maximum_bytes is not None:
        raw_bytes = raw if isinstance(raw, bytes) else raw.encode("utf-8")
        if len(raw_bytes) > maximum_bytes:
            raise ValueError(
                f"{source}: JSON exceeds maximum raw UTF-8 length {maximum_bytes} bytes"
            )
        raw = raw_bytes
    try:
        value = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except DuplicateJsonKeyError as exc:
        raise ValueError(f"{source}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{source}: invalid JSON: {exc.msg}") from exc
    except UnicodeDecodeError as exc:
        raise ValueError(f"{source}: invalid UTF-8 JSON") from exc
    except RecursionError as exc:
        raise ValueError(f"{source}: JSON nesting exceeds parser limit") from exc
    if _json_depth(value) > MAX_JSON_NESTING_DEPTH:
        raise ValueError(f"{source}: JSON nesting exceeds parser limit")
    if not isinstance(value, dict):
        raise ValueError(f"{source}: JSON value must be an object")
    return value


def load_jsonl(
    path: Path,
    errors: list[str],
    raw_metadata: list[dict[str, object]] | None = None,
    source_bytes: bytes | None = None,
) -> list[dict]:
    if not path.exists():
        fail(errors, f"missing ledger: {path}")
        return []
    events: list[dict] = []
    if source_bytes is None:
        try:
            source_bytes = path.read_bytes()
        except OSError as exc:
            fail(errors, f"cannot read ledger: {path}: {exc}")
            return []
    try:
        stream = io.StringIO(source_bytes.decode("utf-8", errors="strict"), newline="")
    except UnicodeDecodeError as exc:
        fail(errors, f"cannot read ledger: {path}: {exc}")
        return []
    with stream:
        line_no = 0
        while True:
            raw = stream.readline(MAX_LEDGER_LINE_CHARS + 2)
            if raw == "":
                break
            line_no += 1
            complete_line = raw.endswith("\n")
            line = raw.rstrip("\r\n")
            if len(line) > MAX_LEDGER_LINE_CHARS or (
                not complete_line and len(raw) > MAX_LEDGER_LINE_CHARS
            ):
                while raw and not raw.endswith("\n"):
                    raw = stream.readline(MAX_LEDGER_LINE_CHARS + 2)
                fail(errors, f"{path}:{line_no}: event exceeds bounded line length")
                continue
            if not line.strip():
                continue
            if len(events) >= MAX_LEDGER_EVENTS:
                fail(errors, f"ledger exceeds bounded event count: {path}")
                break
            try:
                event = decode_json_object(
                    line,
                    source=f"{path}:{line_no}",
                    maximum_bytes=MAX_LEDGER_LINE_BYTES,
                )
            except ValueError as exc:
                fail(errors, str(exc))
                continue
            events.append(event)
            if raw_metadata is not None:
                if raw.endswith("\r\n"):
                    digest_text = raw[:-2]
                elif raw.endswith("\n"):
                    digest_text = raw[:-1]
                else:
                    digest_text = raw
                raw_metadata.append(
                    {
                        "line": line_no,
                        "sha256": hashlib.sha256(digest_text.encode("utf-8")).hexdigest(),
                        "bytes": len(digest_text.encode("utf-8")),
                    }
                )
    if not events:
        fail(errors, f"ledger has no events: {path}")
    return events


def repo_root_for(item: Path) -> Path | None:
    """The repository root that owns this work item.

    Every work item lives under `<root>/work-items/...` (active/ or
    archive/<YYYY-MM>/), so the parent of the `work-items` directory is the
    root. Returns None when the item is not under a `work-items` tree.
    """

    for parent in item.resolve().parents:
        if parent.name == "work-items":
            return parent.parent
    return None


def _resolve_active_slug_in_archive(root: Path, candidate: Path) -> Path | None:
    """Retry a recorded `work-items/active/<slug>/<tail>` path under
    `work-items/archive/<YYYY-MM>/<slug>/<tail>`.

    The ledger records an artifact path while the item lives under active/; the
    mandatory close step (owned by the lead contract + knowledge-archivist
    mechanics) moves the item directory to archive/<YYYY-MM>/ WITHOUT touching
    the ledger -- the ledger is an append-only audit record of what was true
    when written, and rewriting historical entries to match the new location is
    the one response this bug class forbids (see
    work-items/bugs/2026-07-26-archiving-an-item-breaks-its-own-ledger-artifact-
    paths.md). The slug segment is stable across the move, so the same tail can
    be relocated by searching the archive month directories for it. This is an
    append-only artifact-tail compatibility lookup across an active-to-dated-
    archive move, not a second dependency-state resolver. Canonical work-item
    identity and dependency state are owned by `resolve_category` and
    `work_item_dependency_state` in `scripts/mutate-work-item.py`.
    """
    parts = candidate.parts
    if len(parts) < 3 or parts[0] != "work-items" or parts[1] != "active":
        return None
    slug = parts[2]
    tail = parts[3:]
    archive_dir = root / "work-items" / "archive"
    if not archive_dir.is_dir():
        return None
    try:
        month_dirs = sorted(path for path in archive_dir.iterdir() if path.is_dir())
    except OSError:
        return None
    for month_dir in month_dirs:
        candidate_path = month_dir.joinpath(slug, *tail)
        if candidate_path.exists():
            return candidate_path.resolve()
    return None


def resolve_work_item_path(item: Path, value: object, label: str, run_id: object, errors: list[str]) -> Path | None:
    """Resolve a recorded path, work-item-relative FIRST, repo-root-relative second.

    A review's artifact is often a repository file rather than a copy inside the
    work item (reviewing `scripts/maintenance/cleanup.py` is the ordinary case
    for an implementation gate). Resolving work-item-relative only made such a
    verdict unrecordable: the PASS closer failed the artifact-exists check and
    the reviewer's verdict was dropped, leaving the obligation open forever.
    Both roots stay inside the repository; absolute paths and escapes are still
    rejected.
    """

    if not isinstance(value, str):
        fail(errors, f"{run_id}: {label} must be a string")
        return None
    if not value.strip():
        fail(errors, f"{run_id}: {label} must be a non-empty relative path")
        return None

    candidate = Path(value)
    if candidate.is_absolute():
        fail(errors, f"{run_id}: {label} must be a relative path: {value}")
        return None

    item_root = item.resolve()
    resolved = (item_root / candidate).resolve()
    if resolved == item_root or item_root in resolved.parents:
        if resolved.exists():
            return resolved
        # Fall through: the same relative string may name a repository file.
    elif resolved != item_root:
        # The string escapes the work item; only the repo-root reading can be
        # legitimate, and it is checked below.
        resolved = None

    root = repo_root_for(item)
    if root is not None:
        from_root = (root / candidate).resolve()
        if from_root == root or root in from_root.parents:
            if from_root.exists() or resolved is None:
                return from_root
            # The repo-root reading faithfully reconstructs a `work-items/active/
            # <slug>/...` path that no longer exists because the item was closed
            # (moved to archive/<YYYY-MM>/<slug>/) after the ledger recorded it.
            # No additional search *root* fixes this -- the recorded path itself
            # names the stale location. Retry the same tail under the slug's
            # archived location before giving up.
            archived = _resolve_active_slug_in_archive(root, candidate)
            if archived is not None:
                return archived

    if resolved is None:
        fail(errors, f"{run_id}: {label} escapes the work item and the repository: {value}")
        return None
    return resolved


def resolve_scratch_pointer(
    item: Path, value: object, label: str, run_id: object, errors: list[str]
) -> Path | None:
    """Resolve scratch evidence only inside this exact work-item identity."""

    failure = "WI-SCRATCH-POINTER-OUTSIDE-ITEM"
    if not isinstance(value, str) or not value.strip() or not _safe_repo_relative(value):
        fail(errors, f"{failure}: {run_id}: {label} must be item-relative")
        return None
    item_root = item.resolve()
    candidate = item_root.joinpath(*PurePosixPath(value).parts)
    current = item_root
    try:
        for part in PurePosixPath(value).parts:
            current = current / part
            info = os.lstat(current)
            if stat_module.S_ISLNK(info.st_mode) or (
                getattr(info, "st_file_attributes", 0)
                & getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            ):
                fail(errors, f"{failure}: {run_id}: {label} crosses a link or reparse point")
                return None
    except OSError:
        fail(errors, f"{failure}: {run_id}: {label} does not exist inside this item")
        return None
    resolved = candidate.resolve()
    if item_root not in resolved.parents or not resolved.is_file():
        fail(errors, f"{failure}: {run_id}: {label} must name a file inside this item")
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


def _bounded_nonempty_string(
    value: object,
    *,
    maximum: int,
    label: str,
    run_id: object,
    errors: list[str],
) -> bool:
    if not isinstance(value, str) or not value.strip():
        fail(errors, f"{run_id}: {label} must be a non-empty string")
        return False
    if len(value) > maximum:
        fail(errors, f"{run_id}: {label} exceeds maximum length {maximum}")
        return False
    return True


def _safe_repo_relative(value: str) -> bool:
    if "\\" in value:
        return False
    candidate = PurePosixPath(value)
    return not candidate.is_absolute() and value == candidate.as_posix() and ".." not in candidate.parts


_LEGACY_PROJECTION_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", re.ASCII)


def confine_legacy_projection_path(
    root: Path,
    value: object,
    *,
    prefix: tuple[str, ...] = (),
    leaf_kind: str | None = None,
    allow_missing_leaf: bool = False,
    failure_id: str = "WI-LEDGER-MIGRATION-TARGET-IDENTITY",
) -> Path:
    """Return one pre-dereference repository-relative projection capability.

    This is intentionally the only projection parser that converts a parsed
    path string into a filesystem path.  It performs lexical validation and an
    lstat-only component walk before a caller may probe or read content.
    """
    if (
        not isinstance(value, str)
        or not value
        or "\x00" in value
        or "\\" in value
        or ":" in value
        or value.startswith("/")
        or value.startswith("//")
    ):
        raise ValueError(f"{failure_id}: unsafe projection path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts) or tuple(parts[:len(prefix)]) != prefix:
        raise ValueError(f"{failure_id}: projection path escapes its structural scope")
    root = Path(root)
    if not root.is_absolute():
        raise ValueError(f"{failure_id}: projection repository root is not absolute")
    candidate = root.joinpath(*parts)
    cursor = root
    try:
        root_info = os.lstat(cursor)
    except OSError as exc:
        raise ValueError(f"{failure_id}: projection repository root is unavailable") from exc
    if stat_module.S_ISLNK(root_info.st_mode) or bool(getattr(root_info, "st_file_attributes", 0) & getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
        raise ValueError(f"{failure_id}: projection repository root is linked")
    for index, part in enumerate(parts, start=1):
        cursor = cursor / part
        try:
            info = os.lstat(cursor)
        except FileNotFoundError:
            if allow_missing_leaf:
                return candidate
            raise ValueError(f"{failure_id}: projection path component is unavailable")
        except OSError as exc:
            raise ValueError(f"{failure_id}: projection path component is unavailable") from exc
        if stat_module.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            raise ValueError(f"{failure_id}: projection path contains a link or reparse point")
    if leaf_kind == "file" and not stat_module.S_ISREG(info.st_mode):
        raise ValueError(f"{failure_id}: projection path is not a regular file")
    if leaf_kind == "directory" and not stat_module.S_ISDIR(info.st_mode):
        raise ValueError(f"{failure_id}: projection path is not a directory")
    return candidate


def confine_legacy_projection_identifier(value: object, *, failure_id: str = "WI-LEDGER-MIGRATION-TARGET-IDENTITY") -> str:
    if not isinstance(value, str) or _LEGACY_PROJECTION_IDENTIFIER_RE.fullmatch(value) is None:
        raise ValueError(f"{failure_id}: unsafe projection identifier")
    return value


def validate_scratch_evidence(
    event: dict,
    item: Path,
    artifact_path: Path | None,
    run_id: object,
    errors: list[str],
) -> None:
    entries = event.get("scratchEvidence")
    if not isinstance(entries, list) or not entries or len(entries) > MAX_SCRATCH_EVIDENCE_ENTRIES:
        fail(errors, f"{run_id}: scratchEvidence must be a non-empty bounded list")
        return
    if event.get("schemaVersion") != 2:
        fail(errors, f"{run_id}: scratchEvidence requires schemaVersion 2")
    if event.get("eventKind") != "terminal":
        fail(errors, f"{run_id}: scratchEvidence requires eventKind terminal")
    if event.get("status") != "completed" or event.get("gate") != "PASS":
        fail(errors, f"{run_id}: scratchEvidence requires completed PASS owner")
    if not isinstance(run_id, str) or not SCRATCH_IDENTIFIER_RE.fullmatch(run_id):
        fail(errors, f"{run_id}: scratchEvidence owner runId is not namespace-safe")
        return

    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    normalized_paths: list[str] = []
    for index, entry in enumerate(entries, start=1):
        label = f"scratchEvidence[{index}]"
        if not isinstance(entry, dict):
            fail(errors, f"{run_id}: {label} must be an object")
            continue
        unexpected = sorted(set(entry) - SCRATCH_EVIDENCE_ALLOWED_FIELDS)
        missing = sorted(SCRATCH_EVIDENCE_REQUIRED_FIELDS - set(entry))
        for key in unexpected:
            fail(errors, f"{run_id}: {label} has unexpected field: {key}")
        for key in missing:
            fail(errors, f"{run_id}: {label} missing required field: {key}")

        entry_id = entry.get("entryId")
        if not _bounded_nonempty_string(
            entry_id,
            maximum=MAX_SCRATCH_ENTRY_ID_LENGTH,
            label=f"{label}.entryId",
            run_id=run_id,
            errors=errors,
        ):
            continue
        assert isinstance(entry_id, str)
        if not SCRATCH_IDENTIFIER_RE.fullmatch(entry_id):
            fail(errors, f"{run_id}: {label}.entryId is not namespace-safe")
        folded_id = entry_id.casefold()
        if folded_id in seen_ids:
            fail(errors, f"{run_id}: scratchEvidence entryId collision: {entry_id}")
        seen_ids.add(folded_id)

        path_value = entry.get("path")
        if _bounded_nonempty_string(
            path_value,
            maximum=MAX_SCRATCH_PATH_LENGTH,
            label=f"{label}.path",
            run_id=run_id,
            errors=errors,
        ):
            assert isinstance(path_value, str)
            expected = f".scratch/work-items/{item.name}/{run_id}/{entry_id}"
            if not _safe_repo_relative(path_value) or path_value != expected:
                fail(errors, f"{run_id}: {label}.path must equal its exact owner namespace")
            folded_path = path_value.casefold()
            if folded_path in seen_paths:
                fail(errors, f"{run_id}: scratchEvidence path collision: {path_value}")
            seen_paths.add(folded_path)
            normalized_paths.append(folded_path)

        disposition = entry.get("disposition")
        if disposition not in {"retain", "delete"}:
            fail(errors, f"{run_id}: {label}.disposition must be retain or delete")
        _bounded_nonempty_string(
            entry.get("reason"),
            maximum=MAX_SCRATCH_REASON_LENGTH,
            label=f"{label}.reason",
            run_id=run_id,
            errors=errors,
        )

        pointer = entry.get("canonicalPointer")
        pointer_path = None
        if _bounded_nonempty_string(
            pointer,
            maximum=MAX_SCRATCH_POINTER_LENGTH,
            label=f"{label}.canonicalPointer",
            run_id=run_id,
            errors=errors,
        ):
            assert isinstance(pointer, str)
            pointer_path = resolve_scratch_pointer(
                item, pointer, f"{label}.canonicalPointer", run_id, errors
            )
            if pointer_path is not None and not pointer_path.is_file():
                fail(errors, f"{run_id}: {label}.canonicalPointer must name a file")

        proof = entry.get("proof")
        if disposition == "retain":
            if "proof" in entry:
                fail(errors, f"{run_id}: {label}.proof is forbidden for retain")
            continue
        if not isinstance(proof, dict):
            fail(errors, f"{run_id}: {label}.proof is required for delete")
            continue
        kind = proof.get("kind")
        expected_fields = SCRATCH_PROOF_FIELDS.get(kind)
        if expected_fields is None:
            fail(errors, f"{run_id}: {label}.proof has invalid kind {kind!r}")
            continue
        for key in sorted(set(proof) - expected_fields):
            fail(errors, f"{run_id}: {label}.proof has unexpected field: {key}")
        for key in sorted(expected_fields - set(proof)):
            fail(errors, f"{run_id}: {label}.proof missing required field: {key}")
        if kind == "accepted-artifact":
            artifact_sha = proof.get("artifactSha256")
            if not isinstance(artifact_sha, str) or not SHA256_RE.fullmatch(artifact_sha):
                fail(errors, f"{run_id}: {label}.proof artifactSha256 must be lowercase SHA-256")
            if pointer != event.get("artifact") or pointer_path != artifact_path:
                fail(errors, f"{run_id}: {label}.proof must bind the accepted event artifact")
            producer = proof.get("producer")
            if not _bounded_nonempty_string(
                producer,
                maximum=MAX_SCRATCH_PRODUCER_LENGTH,
                label=f"{label}.proof.producer",
                run_id=run_id,
                errors=errors,
            ):
                pass
            elif not _safe_repo_relative(producer):
                fail(errors, f"{run_id}: {label}.proof producer must be repository-relative")
            else:
                repo_root = repo_root_for(item)
                if repo_root is None or not (repo_root / producer).is_file():
                    fail(errors, f"{run_id}: {label}.proof producer does not exist")
            _bounded_nonempty_string(
                proof.get("reproduce"),
                maximum=MAX_SCRATCH_REPRODUCE_LENGTH,
                label=f"{label}.proof.reproduce",
                run_id=run_id,
                errors=errors,
            )

    for index, path in enumerate(normalized_paths):
        for other in normalized_paths[index + 1 :]:
            if path.startswith(other + "/") or other.startswith(path + "/"):
                fail(errors, f"{run_id}: scratchEvidence paths must not overlap")


def scratch_tombstone_name(slug: str, run_id: str, entry_id: str) -> str:
    token = hashlib.sha256(f"{slug}/{run_id}/{entry_id}".encode("utf-8")).hexdigest()[:16]
    return f".{entry_id}.orchestrarium-delete-{token}"


def validate_scratch_ownership(events: list[dict], item: Path, errors: list[str]) -> None:
    """Enforce ledger-wide, case-insensitive scratch and tombstone ownership."""

    owners: dict[str, str] = {}
    for event in events:
        run_id = event.get("runId")
        if not isinstance(run_id, str):
            continue
        for entry in event.get("scratchEvidence", []):
            if not isinstance(entry, dict):
                continue
            path = entry.get("path")
            entry_id = entry.get("entryId")
            if not isinstance(path, str) or not isinstance(entry_id, str):
                continue
            identity = f"{run_id}/{entry_id}/{entry.get('disposition')}"
            original_key = path.casefold()
            candidate = PurePosixPath(path)
            tombstone = candidate.with_name(
                scratch_tombstone_name(item.name, run_id, entry_id)
            ).as_posix()
            for key in (original_key, tombstone.casefold()):
                previous = owners.get(key)
                if previous is not None:
                    fail(
                        errors,
                        "WI-SCRATCH-OWNERSHIP-CONFLICT: "
                        f"{identity} collides with {previous}",
                    )
                else:
                    owners[key] = identity


def has_security_reviewer_authority(event: dict) -> bool:
    return (
        event.get("role") == "security-reviewer"
        or event.get("assignedRole") == "security-reviewer"
    )


def validate_security_reviewer_waiver_closer(
    event: dict,
    artifact_path: Path | None,
    run_id: object,
    errors: list[str],
) -> None:
    """Validate every closer-side dimension of security-reviewer waiver authority."""

    if not has_security_reviewer_authority(event):
        fail(
            errors,
            f"{run_id}: {SECURITY_REVIEWER_WAIVER_GATE} authority dimension requires "
            "security-reviewer in role or assignedRole",
        )

    execution_role = event.get("executionRole")
    if execution_role in LEGACY_EXECUTION_ROLES:
        execution_role = LEGACY_EXECUTION_ROLES[execution_role]
    if execution_role not in {"external-reviewer", "internal"}:
        fail(
            errors,
            f"{run_id}: {SECURITY_REVIEWER_WAIVER_GATE} executionRole dimension requires "
            "reviewer-side executionRole (external-reviewer|internal)",
        )

    artifact = event.get("artifact")
    if (
        not isinstance(artifact, str)
        or not artifact.strip()
        or artifact_path is None
        or not artifact_path.exists()
    ):
        fail(
            errors,
            f"{run_id}: {SECURITY_REVIEWER_WAIVER_GATE} artifact dimension requires "
            "a non-empty existing artifact",
        )


def validate_waiver_fields(
    event: dict,
    gate: str,
    run_id: object,
    status: object,
    authorization: str,
    errors: list[str],
) -> None:
    """Validate the shared, target-bound shape of a typed waiver disposition."""

    if status != "completed":
        fail(errors, f"{run_id}: {gate} requires completed status")
    if "closesRunIds" not in event:
        fail(errors, f"{run_id}: {gate} requires closesRunIds")
    entries = event.get("evidence") if isinstance(event.get("evidence"), list) else []
    manual_refs = " ".join(
        entry.get("ref", "")
        for entry in entries
        if (
            isinstance(entry, dict)
            and entry.get("kind") == "manual-check"
            and isinstance(entry.get("ref"), str)
        )
    )
    if not manual_refs:
        fail(
            errors,
            f"{run_id}: {gate} requires a manual-check evidence entry with {authorization}",
        )
        return

    # The authorization must NAME the exact obligations it waives (design:
    # target-bound evidence; unrelated authorization text is not authority).
    closes = event.get("closesRunIds") if isinstance(event.get("closesRunIds"), list) else []
    for target_id in closes:
        if not isinstance(target_id, str):
            continue
        # Exact token identity, not substring: 'run-x-extra' in the evidence
        # must NOT authorize target 'run-x' (Sol impl-gate r2 prefix collision).
        token_re = re.compile(rf"(?<![\w.-]){re.escape(target_id)}(?![\w.-])")
        if not token_re.search(manual_refs):
            fail(
                errors,
                f"{run_id}: {gate} manual-check evidence does not name target "
                f"{target_id} exactly — authorization must be target-bound",
            )


def validate_v3_event(event: dict, seen: set[str], errors: list[str]) -> bool:
    error_count_on_entry = len(errors)
    event_id = event.get("eventId")
    for key in sorted(V3_REQUIRED_FIELDS - set(event)):
        fail(errors, f"V3 event missing required field: {key}")
    for key in sorted(set(event) - V3_ALLOWED_FIELDS):
        fail(errors, f"unexpected V3 field: {key}")

    if not isinstance(event_id, str) or not SCRATCH_IDENTIFIER_RE.fullmatch(event_id) or len(event_id) > 128:
        fail(errors, f"{event_id}: eventId must be a bounded namespace-safe string")
    else:
        identity = f"v3:{event_id.casefold()}"
        if identity in seen:
            fail(errors, f"duplicate eventId: {event_id}")
        seen.add(identity)
    operation_id = event.get("operationId")
    if (
        not isinstance(operation_id, str)
        or not SCRATCH_IDENTIFIER_RE.fullmatch(operation_id)
        or len(operation_id) > 128
    ):
        fail(errors, f"{event_id}: operationId must be a bounded namespace-safe string")
    if not isinstance(event.get("fingerprint"), str) or not SHA256_RE.fullmatch(event["fingerprint"]):
        fail(errors, f"{event_id}: fingerprint must be 64 lowercase hex characters")
    prior_head = event.get("priorHead")
    if prior_head != "GENESIS" and (
        not isinstance(prior_head, str) or not SHA256_RE.fullmatch(prior_head)
    ):
        fail(errors, f"{event_id}: priorHead must be GENESIS or 64 lowercase hex characters")
    recorded_at = event.get("recordedAt")
    if not isinstance(recorded_at, str) or re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z",
        recorded_at,
        re.ASCII,
    ) is None:
        fail(errors, f"{event_id}: recordedAt must be a strict UTC timestamp")
    if event.get("eventType") not in V3_EVENT_TYPES:
        fail(errors, f"{event_id}: invalid eventType {event.get('eventType')!r}")
    if not isinstance(event.get("payload"), dict):
        fail(errors, f"{event_id}: payload must be an object")
    return len(errors) == error_count_on_entry


@dataclass(frozen=True)
class HistoricalArtifactAuthorization:
    """A single raw V2 PASS position which may have a missing archived artifact."""

    raw_line_ordinal: int
    raw_line_sha256: str
    event_sha256: str
    run_id: str
    artifact: str
    artifact_revision_sha256: str


@dataclass(frozen=True)
class LedgerProjectionRowV1:
    """One immutable effective-ledger row bound to its physical source row."""

    event: dict
    raw_line_ordinal: int
    raw_line_sha256: str
    raw_event_sha256: str
    transformation: str = "raw"
    obligation_id: str | None = None
    predecessor_operation_id: str | None = None


@dataclass(frozen=True)
class WorkItemObligationRowV1:
    """One currently open lifecycle obligation with its immutable source identity."""

    run_id: str
    event: Mapping[str, object]
    raw_line_ordinal: int
    raw_line_sha256: str
    raw_event_sha256: str
    projected_event_sha256: str
    source_kind: str
    obligation_id: str | None
    predecessor_operation_id: str | None


@dataclass(frozen=True)
class WorkItemObligationStateV1:
    open_revise: tuple[WorkItemObligationRowV1, ...]
    open_launches: tuple[WorkItemObligationRowV1, ...]


@dataclass(frozen=True)
class LedgerCompatibilityArtifactSetV1:
    ledger_bytes_by_path: Mapping[str, bytes]
    h1_manifest_path: str
    h1_manifest_bytes: bytes
    ledger_manifest_path: str
    ledger_manifest_bytes: bytes
    registry_bytes: bytes
    receipt_bytes_by_path: Mapping[str, bytes]
    participant_locations_by_path: Mapping[str, object] = field(default_factory=dict)


class _LedgerH1AcquisitionError(RuntimeError):
    def __init__(self, failure_id: str, logical_ledger_path: str) -> None:
        super().__init__(failure_id, logical_ledger_path)
        self.failure_id = failure_id
        self.logical_ledger_path = logical_ledger_path


@dataclass(frozen=True)
class LedgerAuthorityV1:
    launch_eligible: bool
    terminal_eligible: bool
    revise_target_eligible: bool
    closer_eligible: bool
    artifact_evidence_eligible: bool


@dataclass(frozen=True)
class RuntimeLedgerRowV1:
    event: Mapping[str, object]
    raw_line_ordinal: int
    raw_line_sha256: str
    raw_body_sha256: str
    projected_event_sha256: str
    epoch: Literal["raw", "sealed-prefix", "strict-suffix", "disposed-suffix", "transferred"]
    authority: LedgerAuthorityV1


@dataclass(frozen=True)
class LedgerEventValidityV1:
    current_schema_valid: bool
    authority: LedgerAuthorityV1


@dataclass(frozen=True)
class SuffixDispositionNoticeV1:
    notice_id: Literal["WI-LEDGER-COMPAT-SUFFIX-DISPOSED-NONAUTHORIZING"]
    ledger_path: str
    raw_line_ordinal: int
    raw_line_sha256: str
    run_id: str
    disposition_run_id: str
    disposition_line_ordinal: int


@dataclass(frozen=True)
class LedgerCompatibilityObservationV1:
    activation_state: Literal["inactive", "active", "revoked", "invalid"]
    failure_ids: tuple[str, ...]
    diagnostics: tuple[str, ...]
    disposition_notices: tuple[SuffixDispositionNoticeV1, ...] = ()


@dataclass(frozen=True)
class LedgerCompatibilityViewV1:
    wire: Mapping[str, object]
    projected_view_sha256: str
    reduction: Mapping[str, object]


@dataclass(frozen=True)
class LedgerValidationContextV1:
    selected_ledger_path: str
    rows: tuple[RuntimeLedgerRowV1, ...]
    view: LedgerCompatibilityViewV1 | None
    observation: LedgerCompatibilityObservationV1
    group_open_revise_ids: tuple[str, ...]
    group_open_launch_ids: tuple[str, ...]
    invocation_token: object


@dataclass(frozen=True)
class _LedgerInvocationTokenV1:
    rows_by_path: Mapping[str, tuple[RuntimeLedgerRowV1, ...]]
    h1_projection_partition: tuple[
        str, str, str, str, tuple[tuple[int, str], ...]
    ]


_NO_LEDGER_AUTHORITY = LedgerAuthorityV1(False, False, False, False, False)


def _sealed_context_is_bound(
    rows: Sequence[RuntimeLedgerRowV1],
    context: LedgerValidationContextV1 | None,
    errors: list[str],
) -> bool:
    if not any(row.epoch in {"sealed-prefix", "disposed-suffix"} for row in rows):
        return True
    valid = bool(
        isinstance(context, LedgerValidationContextV1)
        and context.rows is rows
        and context.observation.activation_state == "active"
        and context.view is not None
        and context.selected_ledger_path == context.view.wire.get("ledgerPath")
        and isinstance(context.invocation_token, _LedgerInvocationTokenV1)
        and context.invocation_token.rows_by_path.get(context.selected_ledger_path)
        is context.rows
    )
    if not valid:
        fail(
            errors,
            "WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS: sealed-prefix rows require their exact receipt-minted validation context",
        )
    return valid


def _runtime_rows_from_projection(
    rows: Sequence[LedgerProjectionRowV1], *, epoch: Literal["raw", "strict-suffix"] = "raw"
) -> tuple[RuntimeLedgerRowV1, ...]:
    return tuple(
        RuntimeLedgerRowV1(
            MappingProxyType(copy.deepcopy(row.event)),
            row.raw_line_ordinal,
            row.raw_line_sha256,
            row.raw_line_sha256,
            hashlib.sha256(_canonical_projection_bytes(row.event)).hexdigest(),
            "transferred" if row.transformation == "transferred" else epoch,
            _NO_LEDGER_AUTHORITY,
        )
        for row in rows
    )


def _runtime_rows_from_events(
    events: Sequence[Mapping[str, object]],
) -> tuple[RuntimeLedgerRowV1, ...]:
    return tuple(
        RuntimeLedgerRowV1(
            MappingProxyType(copy.deepcopy(dict(event))),
            position,
            hashlib.sha256(_canonical_projection_bytes(event)).hexdigest(),
            hashlib.sha256(_canonical_projection_bytes(event)).hexdigest(),
            hashlib.sha256(_canonical_projection_bytes(event)).hexdigest(),
            "raw",
            _NO_LEDGER_AUTHORITY,
        )
        for position, event in enumerate(events, start=1)
    )


def _capture_obligation_state(
    sink: list[WorkItemObligationStateV1] | None,
    rows: Sequence[LedgerProjectionRowV1] | Sequence[RuntimeLedgerRowV1],
    open_revise: Sequence[Mapping[str, object]],
    open_launches: Sequence[Mapping[str, object]],
) -> None:
    if sink is None:
        return

    rows_by_run_id = {
        row.event.get("runId"): row
        for row in rows
        if isinstance(row.event.get("runId"), str)
    }

    def bound(events: Sequence[Mapping[str, object]]) -> tuple[WorkItemObligationRowV1, ...]:
        result: list[WorkItemObligationRowV1] = []
        for event in events:
            run_id = event.get("runId")
            row = rows_by_run_id.get(run_id)
            if not isinstance(run_id, str) or row is None:
                continue
            if isinstance(row, LedgerProjectionRowV1):
                raw_event_sha256 = row.raw_event_sha256
                projected_event_sha256 = hashlib.sha256(
                    _canonical_projection_bytes(row.event)
                ).hexdigest()
                source_kind = row.transformation
            else:
                raw_event_sha256 = row.raw_body_sha256
                projected_event_sha256 = row.projected_event_sha256
                source_kind = row.epoch
            result.append(WorkItemObligationRowV1(
                run_id,
                MappingProxyType(copy.deepcopy(dict(row.event))),
                row.raw_line_ordinal,
                row.raw_line_sha256,
                raw_event_sha256,
                projected_event_sha256,
                source_kind,
                getattr(row, "obligation_id", None),
                getattr(row, "predecessor_operation_id", None),
            ))
        return tuple(result)

    sink.append(WorkItemObligationStateV1(bound(open_revise), bound(open_launches)))


def _validity_from_boolean_events(
    rows: Sequence[RuntimeLedgerRowV1], valid: Sequence[bool]
) -> tuple[LedgerEventValidityV1, ...]:
    """Adapt already-owned historical validity into the five closure axes."""

    result = []
    for row, is_valid in zip(rows, valid):
        event = row.event
        mask = LedgerAuthorityV1(
            bool(is_valid and event.get("eventKind") == "launch"),
            bool(is_valid and event.get("eventKind") == "terminal"),
            bool(is_valid and event.get("schemaVersion") == 2 and event.get("gate") == "REVISE"),
            bool(is_valid and event.get("gate") in CLOSURE_GATES and event.get("closesRunIds")),
            bool(is_valid and ("artifact" in event or "evidence" in event)),
        )
        result.append(LedgerEventValidityV1(bool(is_valid), mask))
    return tuple(result)


def _ledger_projection_rows(
    events: list[dict], raw_metadata: list[dict[str, object]], errors: list[str]
) -> tuple[LedgerProjectionRowV1, ...]:
    """Bind parsed events to physical identity once, before any projection."""
    if len(events) != len(raw_metadata):
        _projection_fail(errors, "identity", "raw event identity cardinality differs")
        return ()
    rows: list[LedgerProjectionRowV1] = []
    identities: set[tuple[int, str]] = set()
    for position, (event, metadata) in enumerate(zip(events, raw_metadata), start=1):
        line = metadata.get("line", position)
        line_sha256 = metadata.get("sha256")
        if (
            type(line) is not int
            or line < 1
            or not isinstance(line_sha256, str)
            or SHA256_RE.fullmatch(line_sha256) is None
            or (line, line_sha256) in identities
        ):
            _projection_fail(errors, "topology", "duplicate or invalid raw event identity")
            return ()
        identities.add((line, line_sha256))
        rows.append(
            LedgerProjectionRowV1(
                copy.deepcopy(event), line, line_sha256,
                hashlib.sha256(_canonical_projection_bytes(event)).hexdigest(),
            )
        )
    return tuple(rows)


def _row_metadata(rows: tuple[LedgerProjectionRowV1, ...]) -> list[dict[str, object]]:
    return [{"line": row.raw_line_ordinal, "sha256": row.raw_line_sha256} for row in rows]


def _row_events(rows: tuple[LedgerProjectionRowV1, ...]) -> list[dict]:
    return [row.event for row in rows]


def _validate_event(
    event: dict,
    item: Path,
    seen: set[str],
    errors: list[str],
    *,
    historical_artifact_authorization: HistoricalArtifactAuthorization | None = None,
    legacy_archived_review_pointer_compat: bool = False,
    telemetry: dict[str, int] | None = None,
) -> bool:
    if event.get("schemaVersion") == 3:
        return validate_v3_event(event, seen, errors)
    error_count_on_entry = len(errors)
    required = ["schemaVersion", "runId", "workItem", "role", "executionRole", "status", "gate", "scope", "startedAt", "updatedAt"]
    for key in required:
        if key not in event:
            fail(errors, f"event missing required field: {key}")

    for key in sorted(set(event) - ALLOWED_FIELDS):
        fail(errors, f"unexpected field: {key}")

    run_id = event.get("runId")
    if isinstance(run_id, str):
        folded_run_id = run_id.casefold()
        if folded_run_id in seen:
            fail(errors, f"duplicate runId: {run_id}")
        seen.add(folded_run_id)
    else:
        fail(errors, f"{run_id}: runId must be a string")

    schema_version = event.get("schemaVersion")
    if schema_version not in (1, 2):
        fail(errors, f"{run_id}: schemaVersion must be 1 or 2")
    if schema_version == 1:
        for key in sorted(V2_ONLY_FIELDS & set(event)):
            fail(errors, f"{run_id}: field {key} requires schemaVersion 2")
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
    execution_role = event.get("executionRole")
    if execution_role in LEGACY_EXECUTION_ROLES:
        execution_role = LEGACY_EXECUTION_ROLES[execution_role]  # legacy read-mapping (lead -> main)
    if execution_role not in EXECUTION_ROLES:
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

    event_kind = event.get("eventKind")
    if "scratchEvidence" in event:
        validate_scratch_evidence(event, item, artifact_path, run_id, errors)

    recovery_fields = {
        "invalidatesRunId",
        "invalidatesEventSha256",
        "invalidationMode",
        "invalidatesRawLineOrdinal",
    }
    if event_kind == "closure-invalidation":
        if schema_version != 2:
            fail(errors, f"{run_id}: closure-invalidation requires schemaVersion 2")
        invalidation_mode = event.get("invalidationMode")
        invalid_current = invalidation_mode == "invalid-current-nonauthorizing"
        fixed = {
            "role": "lead",
            "executionRole": "main",
            "status": "completed",
            "gate": "none",
            "scope": [
                "ledger-recovery:invalid-current-nonauthorizing"
                if invalid_current
                else "ledger-recovery:closure-invalidation"
            ],
        }
        for key, wanted in fixed.items():
            if event.get(key) != wanted:
                fail(errors, f"{run_id}: closure-invalidation requires {key}={wanted!r}")
        target_id = event.get("invalidatesRunId")
        digest = event.get("invalidatesEventSha256")
        if not isinstance(target_id, str) or len(target_id) < 8:
            fail(errors, f"{run_id}: invalidatesRunId must be a runId string")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            fail(errors, f"{run_id}: invalidatesEventSha256 must be lowercase SHA-256")
        if invalid_current:
            if (
                type(event.get("invalidatesRawLineOrdinal")) is not int
                or event["invalidatesRawLineOrdinal"] < 1
            ):
                fail(errors, f"{run_id}: invalidatesRawLineOrdinal must be a positive integer")
            if event.get("authorizing") is not False:
                fail(errors, f"{run_id}: invalid-current disposition requires authorizing=false")
            if not isinstance(event.get("evidence"), list) or not event["evidence"]:
                fail(errors, f"{run_id}: invalid-current disposition requires evidence")
        elif invalidation_mode is not None or "invalidatesRawLineOrdinal" in event:
            fail(errors, f"{run_id}: invalid-current disposition mode is invalid")
        forbidden_fields = {
            "launchRunId", "closesRunIds", "artifact", "scratchEvidence",
        }
        if invalid_current:
            forbidden_fields |= {
                "artifactRevision", "terminalClass", "actualExecutionPath",
                "closerRunId", "targetTuple", "migrationAction",
                "normalizationKind", "migratesRunId", "migratesEventSha256",
                "revokesMigrationRunId", "revokesMigrationEventSha256",
                "replacementEvent",
            }
        for forbidden in sorted(forbidden_fields):
            if forbidden in event:
                fail(errors, f"{run_id}: closure-invalidation forbids {forbidden}")
        refs = [entry.get("ref", "") for entry in event.get("evidence", []) if isinstance(entry, dict) and entry.get("kind") == "manual-check"]
        tokens = " ".join(refs).split()
        if target_id not in tokens or digest not in tokens:
            fail(errors, f"{run_id}: closure-invalidation manual-check must name exact target and digest tokens")
    elif recovery_fields & set(event):
        for key in sorted(recovery_fields & set(event)):
            fail(errors, f"{run_id}: {key} requires eventKind closure-invalidation")

    migration_fields = {
        "migrationAction", "normalizationKind", "migratesRunId", "migratesEventSha256",
        "revokesMigrationRunId", "revokesMigrationEventSha256", "replacementEvent",
    }
    if event_kind == LEGACY_MIGRATION_KIND:
        fixed = {
            "schemaVersion": 2, "role": "lead", "executionRole": "main",
            "status": "completed", "gate": "none",
        }
        for key, wanted in fixed.items():
            if event.get(key) != wanted:
                fail(errors, f"{run_id}: migration control requires {key}={wanted!r}")
        action = event.get("migrationAction")
        if action == "apply":
            required_fields = {"migratesRunId", "migratesEventSha256", "replacementEvent", "evidence"}
            forbidden_fields = {"revokesMigrationRunId", "revokesMigrationEventSha256", "invalidatesRunId", "invalidatesEventSha256"}
            for key in sorted(required_fields - set(event)):
                fail(errors, f"{run_id}: migration apply requires {key}")
            for key in sorted(forbidden_fields & set(event)):
                fail(errors, f"{run_id}: migration apply forbids {key}")
            target_id = event.get("migratesRunId")
            digest = event.get("migratesEventSha256")
            replacement = event.get("replacementEvent")
            normalization_kind = event.get("normalizationKind", "invalid-finding-class")
            row = LEGACY_MIGRATION_NORMALIZATIONS.get(normalization_kind)
            if row is None or event.get("scope") != row["scope"]:
                fail(errors, f"{run_id}: migration normalizationKind requires exact closed mapping")
            if not isinstance(target_id, str) or len(target_id) < 8:
                fail(errors, f"{run_id}: migratesRunId must be a runId string")
            if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
                fail(errors, f"{run_id}: migratesEventSha256 must be lowercase SHA-256")
            if not isinstance(replacement, dict):
                fail(errors, f"{run_id}: replacementEvent must be an object")
            else:
                if migration_fields & set(replacement) or recovery_fields & set(replacement):
                    fail(errors, f"{run_id}: replacementEvent cannot be a control event")
                replacement_errors: list[str] = []
                validate_event(replacement, item, set(), replacement_errors)
                for message in replacement_errors:
                    fail(errors, f"{run_id}: replacementEvent invalid: {message}")
            tokens = " ".join(
                entry.get("ref", "") for entry in event.get("evidence", [])
                if isinstance(entry, dict) and entry.get("kind") == "manual-check"
            ).split()
            if target_id not in tokens or digest not in tokens:
                fail(errors, f"{run_id}: migration apply evidence must bind target and digest")
        elif action == "revoke":
            required_fields = {"revokesMigrationRunId", "revokesMigrationEventSha256", "evidence"}
            forbidden_fields = {"migratesRunId", "migratesEventSha256", "replacementEvent", "invalidatesRunId", "invalidatesEventSha256"}
            for key in sorted(required_fields - set(event)):
                fail(errors, f"{run_id}: migration revoke requires {key}")
            for key in sorted(forbidden_fields & set(event)):
                fail(errors, f"{run_id}: migration revoke forbids {key}")
            target_id = event.get("revokesMigrationRunId")
            digest = event.get("revokesMigrationEventSha256")
            if "normalizationKind" in event:
                fail(errors, f"{run_id}: migration revoke forbids normalizationKind")
            if not isinstance(target_id, str) or len(target_id) < 8:
                fail(errors, f"{run_id}: revokesMigrationRunId must be a runId string")
            if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
                fail(errors, f"{run_id}: revokesMigrationEventSha256 must be lowercase SHA-256")
            tokens = " ".join(
                entry.get("ref", "") for entry in event.get("evidence", [])
                if isinstance(entry, dict) and entry.get("kind") == "manual-check"
            ).split()
            if target_id not in tokens or digest not in tokens:
                fail(errors, f"{run_id}: migration revoke evidence must bind apply and digest")
        else:
            fail(errors, f"{run_id}: migrationAction must be apply or revoke")
        for forbidden in ("launchRunId", "closesRunIds", "artifact", "scratchEvidence"):
            if forbidden in event:
                fail(errors, f"{run_id}: migration control forbids {forbidden}")
    elif migration_fields & set(event):
        for key in sorted(migration_fields & set(event)):
            fail(errors, f"{run_id}: {key} requires eventKind {LEGACY_MIGRATION_KIND}")

    compatible_missing_review_pointer = False
    if gate == "PASS":
        if status != "completed":
            fail(errors, f"{run_id}: PASS gate requires completed status")
        if not artifact:
            fail(errors, f"{run_id}: PASS gate requires artifact")
        authorized_missing = (
            historical_artifact_authorization is not None
            and historical_artifact_authorization.run_id == run_id
            and historical_artifact_authorization.artifact == artifact
            and historical_artifact_authorization.artifact_revision_sha256 == event.get("artifactRevision")
            and historical_artifact_authorization.event_sha256
            == hashlib.sha256(_canonical_projection_bytes(event)).hexdigest()
        )
        missing_artifact = artifact_path is not None and not artifact_path.exists()
        compatible_missing_review_pointer = (
            missing_artifact
            and not authorized_missing
            and legacy_archived_review_pointer_compat
        )
        if missing_artifact and not authorized_missing and not compatible_missing_review_pointer:
            fail(errors, f"{run_id}: artifact does not exist: {artifact}")
        if evidence is None:
            fail(errors, f"{run_id}: PASS gate requires evidence")

    if gate == "REVISE" and status not in {"revise", "completed"}:
        fail(errors, f"{run_id}: REVISE gate requires revise or completed status")
    if isinstance(gate, str) and gate.startswith("BLOCKED") and status != "blocked":
        fail(errors, f"{run_id}: BLOCKED gate requires blocked status")

    # --- v2 per-event field checks (closure semantics are ledger-level, see validate_closure) ---
    event_kind = event.get("eventKind")
    if "eventKind" in event and event_kind not in EVENT_KINDS:
        fail(errors, f"{run_id}: invalid eventKind {event_kind!r}")
    if "launchRunId" in event:
        if not isinstance(event.get("launchRunId"), str) or len(event["launchRunId"]) < 8:
            fail(errors, f"{run_id}: launchRunId must be a string of >= 8 chars")
        if event_kind != "terminal":
            fail(errors, f"{run_id}: launchRunId is only legal on eventKind terminal")
    if event_kind == "terminal" and "launchRunId" not in event:
        fail(errors, f"{run_id}: eventKind terminal requires launchRunId")
    terminal_class = event.get("terminalClass")
    typed_terminal_fields = {
        "terminalClass", "authorizing", "actualExecutionPath", "artifactIdentity",
        "externalDispatchId", "externalEvidenceRunId", "effortMappingLoss", "closerRunId", "targetTuple",
    }
    if terminal_class is not None and terminal_class not in {
        "external-nonauthorizing", "internal-authorizing",
    }:
        fail(errors, f"{run_id}: invalid terminalClass {terminal_class!r}")
    if terminal_class is not None:
        for key in ("authorizing", "actualExecutionPath"):
            if key not in event:
                fail(errors, f"{run_id}: typed terminal requires {key}")
        if not isinstance(event.get("authorizing"), bool):
            fail(errors, f"{run_id}: authorizing must be a boolean")
        if terminal_class == "external-nonauthorizing":
            required = {"assignedRole", "closesRunIds"}
            for key in sorted(required - set(event)):
                fail(errors, f"{run_id}: external terminal requires {key}")
            if event.get("authorizing") is not False:
                fail(errors, f"{run_id}: external terminal requires authorizing=false")
            if event.get("actualExecutionPath") != "direct-external-cli":
                fail(errors, f"{run_id}: external terminal requires direct-external-cli")
            if event.get("executionRole") not in {
                "external-worker", "external-reviewer", "consultant", "none",
            }:
                fail(errors, f"{run_id}: external terminal has invalid executionRole")
            if event.get("closesRunIds") != []:
                fail(errors, f"{run_id}: external terminal requires empty closesRunIds")
            provider = event.get("provider")
            extended = {"externalDispatchId", "externalEvidenceRunId", "effortMappingLoss"}
            if provider in {"codex", "claude"}:
                for key in sorted(extended & set(event)):
                    fail(errors, f"{run_id}: {provider} external terminal forbids {key}")
            elif provider in {"kimi", "grok"}:
                for key in sorted(extended - set(event)):
                    fail(errors, f"{run_id}: {provider} external terminal requires {key}")
                if event.get("externalEvidenceRunId") != run_id:
                    fail(errors, f"{run_id}: external terminal evidence run must equal its runId")
            else:
                fail(errors, f"{run_id}: external terminal provider must be codex, claude, kimi, or grok")
        elif terminal_class == "internal-authorizing":
            required = {
                "assignedRole", "artifactIdentity", "externalEvidenceRunId",
                "closerRunId", "targetTuple", "closesRunIds",
            }
            for key in sorted(required - set(event)):
                fail(errors, f"{run_id}: internal terminal requires {key}")
            if event.get("authorizing") is not True:
                fail(errors, f"{run_id}: internal terminal requires authorizing=true")
            if event.get("actualExecutionPath") != "internal":
                fail(errors, f"{run_id}: internal terminal requires internal execution path")
            if event.get("executionRole") != "internal":
                fail(errors, f"{run_id}: internal terminal requires executionRole=internal")
            if event.get("role") != event.get("assignedRole"):
                fail(errors, f"{run_id}: internal terminal role must equal assignedRole")
            try:
                resolver_path = Path(__file__).with_name("resolve-agents-mode.py")
                spec = importlib.util.spec_from_file_location(
                    "_ledger_role_policy_resolver", resolver_path
                )
                if spec is None or spec.loader is None:
                    raise ValueError("resolver unavailable")
                resolver = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(resolver)
                policy, _ = resolver.load_role_policy(Path(__file__).resolve().parents[1])
                final_roles = policy["finalAuthorizingRoles"]
            except (ImportError, OSError, TypeError, ValueError):
                final_roles = []
            if event.get("assignedRole") not in final_roles:
                fail(errors, f"{run_id}: internal terminal requires a canonical final-authorizing role")
            if event.get("closerRunId") != run_id:
                fail(errors, f"{run_id}: closerRunId must equal this internal terminal runId")
            if len(event.get("closesRunIds", [])) != 1:
                fail(errors, f"{run_id}: internal terminal closes exactly one gate")
            target_tuple = event.get("targetTuple")
            if isinstance(target_tuple, dict):
                for field, expected in (
                    ("workItem", event.get("workItem")),
                    ("artifactIdentity", event.get("artifactIdentity")),
                ):
                    if target_tuple.get(field) != expected:
                        fail(errors, f"{run_id}: targetTuple {field} must bind this closer")
                if "externalDispatchId" in event and target_tuple.get("externalDispatchId") != event.get("externalDispatchId"):
                    fail(errors, f"{run_id}: targetTuple externalDispatchId must bind this closer")
            if event.get("closerRunId") in {
                event.get("externalEvidenceRunId"), event.get("externalDispatchId")
            } or event.get("closerRunId") in (event.get("closesRunIds") or []):
                fail(errors, f"{run_id}: closerRunId must be distinct from target and evidence identities")
            if "externalDispatchId" in event and event.get("externalDispatchId") == event.get("externalEvidenceRunId"):
                fail(errors, f"{run_id}: externalDispatchId and externalEvidenceRunId must be distinct")
    elif typed_terminal_fields & set(event):
        disposition_authorizing = (
            event_kind == "closure-invalidation"
            and event.get("invalidationMode") == "invalid-current-nonauthorizing"
        )
        unexpected_typed = typed_terminal_fields & set(event)
        internal_closer_identity = (
            event.get("schemaVersion") == 2
            and unexpected_typed == {"artifactIdentity"}
            and event.get("executionRole") == "internal"
            and status == "completed"
            and gate == "PASS"
            and isinstance(event.get("closesRunIds"), list)
            and len(event["closesRunIds"]) == 1
            and (
                (event_kind == "standalone" and "launchRunId" not in event)
                or (
                    event_kind == "terminal"
                    and isinstance(event.get("launchRunId"), str)
                )
            )
        )
        if disposition_authorizing:
            unexpected_typed -= {"authorizing"}
        if internal_closer_identity:
            unexpected_typed -= {"artifactIdentity"}
        for key in sorted(unexpected_typed):
            fail(errors, f"{run_id}: {key} requires terminalClass")

    for key in ("artifactIdentity", "externalDispatchId", "externalEvidenceRunId", "effortMappingLoss", "closerRunId"):
        if key in event and (not isinstance(event.get(key), str) or not event[key].strip()):
            fail(errors, f"{run_id}: {key} must be a non-empty string")
    if "launchFlags" in event:
        launch_flags = event.get("launchFlags")
        try:
            frozen_flags, derived_model, derived_effort = validate_launch_profile(
                event.get("provider"), launch_flags
            )
        except (UnicodeEncodeError, ValueError):
            fail(errors, f"{run_id}: launchFlags must be one bounded safe argv string array")
        else:
            if launch_flags != list(frozen_flags):
                fail(errors, f"{run_id}: launchFlags must preserve exact token order")
            if (
                not _kimi_empty_flags_resolved_effort(event)
                and (
                    event.get("model") != derived_model
                    or event.get("effort") != derived_effort
                )
            ):
                fail(errors, f"{run_id}: launchFlags must bind the declared model and effort")
        if event_kind not in {"launch", "terminal"} or event.get("provider") not in {
            "codex", "claude", "kimi"
        }:
            fail(errors, f"{run_id}: launchFlags require an external launch/terminal event")
    if "targetTuple" in event:
        target_tuple = event.get("targetTuple")
        wanted = {"workItem", "assignedInternalRole", "artifactIdentity"}
        allowed = wanted | {"externalDispatchId"}
        if not isinstance(target_tuple, dict) or set(target_tuple) not in (wanted, allowed) or any(
            not isinstance(target_tuple.get(key), str) or not target_tuple[key].strip()
            for key in wanted
        ):
            fail(errors, f"{run_id}: targetTuple must contain exactly the frozen target fields")

    if "closesRunIds" in event:
        closes = event.get("closesRunIds")
        external_empty_closes = terminal_class == "external-nonauthorizing" and closes == []
        if not isinstance(closes, list) or (not closes and not external_empty_closes) or any(
            not isinstance(x, str) or len(x) < 8 for x in closes
        ):
            fail(errors, f"{run_id}: closesRunIds must be a non-empty list of runId strings")
        elif len(set(closes)) != len(closes):
            fail(errors, f"{run_id}: closesRunIds must not contain duplicates")
        if not external_empty_closes and gate not in CLOSURE_GATES:
            fail(
                errors,
                f"{run_id}: closesRunIds is only legal on PASS, {USER_WAIVER_GATE}, "
                f"or {SECURITY_REVIEWER_WAIVER_GATE} events",
            )
    for key in ("artifactRevision", "lane"):
        if key in event and (not isinstance(event.get(key), str) or not event[key].strip()):
            fail(errors, f"{run_id}: {key} must be a non-empty string")
    if "effort" in event and event.get("effort") not in DECLARED_EFFORTS:
        fail(errors, f"{run_id}: invalid effort {event.get('effort')!r}")
    if "findingClass" in event and event.get("findingClass") not in FINDING_CLASSES:
        fail(errors, f"{run_id}: invalid findingClass {event.get('findingClass')!r}")

    if gate == USER_WAIVER_GATE:
        # Typed user disposition (decision item 4): sole legal terminal status is
        # 'completed'; it must name its exact targets; and the user's explicit
        # authorization must be carried as manual-check evidence. Free-text notes
        # carry no authority.
        validate_waiver_fields(
            event,
            gate,
            run_id,
            status,
            "the user's authorization",
            errors,
        )

    if gate == SECURITY_REVIEWER_WAIVER_GATE:
        validate_waiver_fields(
            event,
            gate,
            run_id,
            status,
            "the security-reviewer's authorization",
            errors,
        )
        validate_security_reviewer_waiver_closer(event, artifact_path, run_id, errors)

    event_is_valid = len(errors) == error_count_on_entry
    if event_is_valid and compatible_missing_review_pointer and telemetry is not None:
        key = "archive-legacy-review-pointer-compat"
        telemetry[key] = telemetry.get(key, 0) + 1
    return event_is_valid


def validate_event(event: dict, item: Path, seen: set[str], errors: list[str]) -> bool:
    """Validate a public ledger event without any historical exception."""
    return _validate_event(event, item, seen, errors)


def _launch_profile_is_exact(event: Mapping[str, object]) -> bool:
    if "launchFlags" not in event:
        return True
    flags = event.get("launchFlags")
    try:
        frozen, model, effort = validate_launch_profile(event.get("provider"), flags)
    except (UnicodeEncodeError, ValueError):
        return False
    return flags == list(frozen) and (
        _kimi_empty_flags_resolved_effort(event)
        or (event.get("model") == model and event.get("effort") == effort)
    )


def _derive_authority_masks(
    rows: Sequence[RuntimeLedgerRowV1], current_validity: Sequence[bool], item: Path
) -> tuple[LedgerAuthorityV1, ...]:
    """Derive five independent authority axes from exact raw event fields."""

    positions: dict[str, list[int]] = {}
    for pos, row in enumerate(rows):
        run_id = row.event.get("runId")
        if isinstance(run_id, str) and run_id:
            positions.setdefault(run_id, []).append(pos)

    launch_eligible = [False] * len(rows)
    for pos, row in enumerate(rows):
        event = row.event
        run_id = event.get("runId")
        current_ok = pos < len(current_validity) and current_validity[pos]
        historical_ok = row.epoch in {"sealed-prefix", "transferred"}
        launch_eligible[pos] = bool(
            (current_ok or historical_ok)
            and isinstance(run_id, str)
            and run_id
            and len(positions.get(run_id, ())) == 1
            and (row.epoch != "sealed-prefix" or event.get("workItem") == item.name)
            and event.get("eventKind") == "launch"
            and event.get("status") == "running"
            and "launchRunId" not in event
            and _launch_profile_is_exact(event)
        )

    terminal_eligible = [False] * len(rows)
    settled: set[str] = set()
    for pos, row in enumerate(rows):
        event = row.event
        run_id = event.get("runId")
        launch_id = event.get("launchRunId")
        current_ok = pos < len(current_validity) and current_validity[pos]
        historical_ok = row.epoch in {"sealed-prefix", "transferred"}
        launch_positions = positions.get(launch_id, ()) if isinstance(launch_id, str) else ()
        target_pos = launch_positions[0] if len(launch_positions) == 1 else None
        target = rows[target_pos].event if target_pos is not None else None
        flags_match = False
        if target is not None:
            if "launchFlags" not in target:
                flags_match = "launchFlags" not in event
            else:
                flags_match = (
                    event.get("launchFlags") == target.get("launchFlags")
                    and _launch_profile_is_exact(event)
                )
        eligible = bool(
            (current_ok or historical_ok)
            and isinstance(run_id, str)
            and run_id
            and len(positions.get(run_id, ())) == 1
            and (row.epoch != "sealed-prefix" or event.get("workItem") == item.name)
            and event.get("eventKind") == "terminal"
            and isinstance(event.get("status"), str)
            and event.get("status") != "running"
            and target_pos is not None
            and target_pos < pos
            and launch_eligible[target_pos]
            and launch_id not in settled
            and flags_match
        )
        terminal_eligible[pos] = eligible
        if eligible:
            settled.add(launch_id)

    masks: list[LedgerAuthorityV1] = []
    for pos, row in enumerate(rows):
        event = row.event
        current_ok = pos < len(current_validity) and current_validity[pos]
        if event.get("eventKind") == "closure-invalidation":
            masks.append(_NO_LEDGER_AUTHORITY)
            continue
        if row.epoch == "sealed-prefix":
            isolated_errors: list[str] = []
            individually_current = _validate_event(
                dict(event), item, set(), isolated_errors
            )
        else:
            individually_current = current_ok
        revise = bool(
            (current_ok or row.epoch in {"sealed-prefix", "transferred"})
            and event.get("schemaVersion") == 2
            and event.get("gate") == "REVISE"
            and isinstance(event.get("runId"), str)
            and len(positions.get(event.get("runId"), ())) == 1
        )
        closer = bool(
            individually_current
            and event.get("gate") in CLOSURE_GATES
            and isinstance(event.get("closesRunIds"), list)
            and event.get("closesRunIds")
        )
        artifact = bool(
            individually_current and ("artifact" in event or "evidence" in event)
        )
        masks.append(
            LedgerAuthorityV1(
                launch_eligible[pos], terminal_eligible[pos], revise, closer, artifact
            )
        )
    return tuple(masks)


def derive_event_validity(
    rows: Sequence[RuntimeLedgerRowV1],
    item: Path,
    errors: list[str],
    *,
    validate_schema_version: int | None = None,
    context: LedgerValidationContextV1 | None = None,
) -> tuple[LedgerEventValidityV1, ...]:
    """Validate current epochs and retain sealed-prefix authority independently."""

    if rows and isinstance(rows[0], Mapping):
        rows = _runtime_rows_from_events(rows)  # existing read-only caller compatibility
    if not _sealed_context_is_bound(rows, context, errors):
        return tuple(
            LedgerEventValidityV1(False, _NO_LEDGER_AUTHORITY) for _row in rows
        )
    seen: set[str] = set()
    current: list[bool] = []
    for row in rows:
        event = row.event
        if row.epoch in {"sealed-prefix", "disposed-suffix", "transferred"} or (
            validate_schema_version is not None
            and event.get("schemaVersion") != validate_schema_version
        ):
            current.append(False)
            continue
        current.append(_validate_event(dict(event), item, seen, errors))
    masks = _derive_authority_masks(rows, current, item)
    return tuple(
        LedgerEventValidityV1(current_schema_valid=value, authority=mask)
        for value, mask in zip(current, masks)
    )


def derive_archived_event_validity(
    events: list[dict],
    item: Path,
    errors: list[str],
    authorizations: dict[int, HistoricalArtifactAuthorization],
    *,
    rows: tuple[LedgerProjectionRowV1, ...],
    telemetry: dict[str, int] | None = None,
) -> tuple[list[bool], list[bool]]:
    """Return diagnostics validity plus the stricter closure-eligibility mask."""
    if len(rows) != len(events):
        _projection_fail(errors, "identity", "archived validity rows differ from effective events")
        return [False] * len(events), [False] * len(events)
    seen: set[str] = set()
    validity: list[bool] = []
    closure_validity: list[bool] = []
    for position, event in enumerate(events):
        if event.get("schemaVersion") != 2:
            validity.append(False)
            closure_validity.append(False)
            continue
        row = rows[position]
        authorization = authorizations.get(row.raw_line_ordinal)
        has_historical_authorization = authorization is not None
        if authorization is not None:
            unchanged_raw_position = (
                row.transformation == "raw"
                and row.raw_line_sha256 == authorization.raw_line_sha256
                and row.raw_event_sha256 == authorization.event_sha256
                and hashlib.sha256(_canonical_projection_bytes(event)).hexdigest()
                == authorization.event_sha256
            )
            if not unchanged_raw_position:
                _projection_fail(errors, "identity", "historical artifact authorization cannot apply to projected or migrated event")
                authorization = None
        artifact = event.get("artifact")
        artifact_parts = (
            PurePosixPath(artifact).parts
            if isinstance(artifact, str) and _safe_repo_relative(artifact)
            else ()
        )
        legacy_archived_review_pointer_compat = (
            row.transformation == "raw"
            and not has_historical_authorization
            and event.get("gate") == "PASS"
            and "scratchEvidence" not in event
            and len(artifact_parts) > 2
            and artifact_parts[:2] == (".scratch", "reviews")
        )
        event_is_valid = _validate_event(
            event,
            item,
            seen,
            errors,
            historical_artifact_authorization=authorization,
            legacy_archived_review_pointer_compat=legacy_archived_review_pointer_compat,
            telemetry=telemetry,
        )
        validity.append(event_is_valid)
        # Historical artifact evidence makes this row diagnostically complete,
        # never an authority for closure, invalidation, or terminal settlement.
        closure_validity.append(event_is_valid and authorization is None)
    return validity, closure_validity


def _validate_closure_authority(
    rows: Sequence[RuntimeLedgerRowV1],
    errors: list[str],
    telemetry: dict[str, int] | None = None,
    *,
    validity: Sequence[LedgerEventValidityV1] | None = None,
    event_validity: Sequence[LedgerEventValidityV1] | Sequence[bool] | None = None,
) -> tuple[list[Mapping[str, object]], list[Mapping[str, object]]]:
    """Ledger-level REVISE-closure validation (decision 2026-07-16-review-verdict-closure,
    minimal slice). Returns (open_v2_revise_events, open_launch_events) — obligations never discharged/settled events (never discharged by a valid
    closer). Closure is derived ONLY from the closesRunIds relation — never from
    role/scope/artifact string matching (proven unstable by live replay in the design loop).
    """
    tel = telemetry if telemetry is not None else {}
    if rows and isinstance(rows[0], Mapping):
        rows = _runtime_rows_from_events(rows)  # protected cross-script reader compatibility
    if validity is None:
        validity = event_validity
    if validity is not None and validity and isinstance(validity[0], bool):
        validity = _validity_from_boolean_events(rows, validity)
    if validity is None:
        fail(errors, "WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS: typed validity is required")
        return [], []
    if len(rows) != len(validity):
        fail(errors, "WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS: row/validity cardinality differs")
        return [], []
    events = [row.event for row in rows]

    def axis(position: int, name: str) -> bool:
        return bool(getattr(validity[position].authority, name))

    def bump(rule: str) -> None:
        tel[rule] = tel.get(rule, 0) + 1

    index: dict[str, tuple[int, dict]] = {}
    positions_by_run_id: dict[str, list[tuple[int, dict]]] = {}
    for pos, event in enumerate(events):
        rid = event.get("runId")
        if isinstance(rid, str):
            positions_by_run_id.setdefault(rid, []).append((pos, event))
            if rid not in index:
                index[rid] = (pos, event)

    # Lifecycle integrity (only when eventKind is used): one terminal per launch,
    # terminal references an earlier launch.
    terminals_by_launch: dict[str, str] = {}
    relation_terminals_by_launch: dict[str, str] = {}
    for pos, event in enumerate(events):
        terminal_eligible = axis(pos, "terminal_eligible")
        launch_id = event.get("launchRunId")
        current_relation_diagnostic = bool(
            validity[pos].current_schema_valid
            and rows[pos].epoch in {"raw", "strict-suffix"}
            and event.get("eventKind") == "terminal"
        )
        if not terminal_eligible and not current_relation_diagnostic:
            continue
        if event.get("eventKind") != "terminal":
            continue
        rid = event.get("runId")
        if not isinstance(launch_id, str):
            continue  # per-event check already failed it
        bump("lifecycle-terminal-checked")
        target = index.get(launch_id)
        if target is None or target[0] >= pos:
            fail(errors, f"{rid}: launchRunId {launch_id} does not reference an earlier event")
            bump("lifecycle-dangling-launch")
            continue
        if target[1].get("eventKind") != "launch":
            fail(errors, f"{rid}: launchRunId {launch_id} references a non-launch event")
            bump("lifecycle-nonlaunch-ref")
            continue
        target_is_valid_launch = (
            axis(target[0], "launch_eligible")
            if not current_relation_diagnostic
            or rows[target[0]].epoch == "sealed-prefix"
            else validity[target[0]].current_schema_valid
        )
        if not target_is_valid_launch:
            fail(errors, f"{rid}: launchRunId {launch_id} references an invalid launch event")
            bump("lifecycle-invalid-launch-ref")
            continue
        launch_flags = target[1].get("launchFlags")
        terminal_flags = event.get("launchFlags")
        if launch_flags is not None or terminal_flags is not None:
            if launch_flags is None or terminal_flags is None or launch_flags != terminal_flags:
                fail(errors, f"{rid}: launchFlags must equal the referenced launch binding")
                bump("lifecycle-launch-flags-mismatch")
                continue
        if launch_id in relation_terminals_by_launch:
            fail(errors, f"{rid}: duplicate terminal for launch {launch_id} (first: {relation_terminals_by_launch[launch_id]})")
            bump("lifecycle-duplicate-terminal")
            continue
        relation_terminals_by_launch[launch_id] = (
            rid if isinstance(rid, str) else "<invalid>"
        )
        if terminal_eligible:
            terminals_by_launch[launch_id] = (
                rid if isinstance(rid, str) else "<invalid>"
            )

    discharged: dict[str, str] = {}  # target runId -> closer runId
    for pos, event in enumerate(events):
        # A caller-provided false validity bit is a complete settlement
        # boundary: the row keeps its per-event diagnostics but may not become
        # a terminal, closer, or evidence authority in this reduction.
        if not axis(pos, "closer_eligible"):
            continue
        gate = event.get("gate")
        # Privileged waiver authorization consumes explicit validation state at
        # the event's ledger position. Missing/misaligned state is invalid;
        # rendered diagnostics and attacker-controlled runIds carry no authority.
        security_validity: list[bool] | None = None
        if gate == SECURITY_REVIEWER_WAIVER_GATE:
            security_validity = [
                entry.current_schema_valid or entry.authority.revise_target_eligible
                for entry in validity
            ]
        closes = event.get("closesRunIds")
        if not isinstance(closes, list) or not closes:
            continue
        rid = event.get("runId")
        if security_validity is not None:
            eligible_targets: list[str] = []
            preflight_failed = False
            for target_id in closes:
                if not isinstance(target_id, str):
                    preflight_failed = True
                    continue  # closer validity already carries the shape diagnostic
                bump("closure-checked")
                target_positions = positions_by_run_id.get(target_id, [])
                if len(target_positions) != 1:
                    fail(
                        errors,
                        f"{rid}: {SECURITY_REVIEWER_WAIVER_GATE} target identity dimension "
                        f"requires exactly one ledger event for {target_id}; "
                        f"found {len(target_positions)}",
                    )
                    bump("security-waiver-target-identity-fail")
                    preflight_failed = True
                    continue
                target_pos, target = target_positions[0]
                if target_pos >= pos:
                    fail(
                        errors,
                        f"{rid}: closesRunIds target {target_id} does not reference "
                        "an earlier event (C1)",
                    )
                    bump("C1-fail")
                    preflight_failed = True
                    continue
                if not security_validity[target_pos]:
                    fail(
                        errors,
                        f"{rid}: {SECURITY_REVIEWER_WAIVER_GATE} target validity dimension "
                        f"cannot discharge {target_id}: target event is invalid",
                    )
                    bump("security-waiver-target-validity-fail")
                    preflight_failed = True
                    continue
                if target.get("gate") != "REVISE":
                    fail(
                        errors,
                        f"{rid}: closesRunIds target {target_id} is not a REVISE event (C2)",
                    )
                    bump("C2-fail")
                    preflight_failed = True
                    continue
                if target_id in discharged:
                    fail(
                        errors,
                        f"{rid}: REVISE {target_id} already discharged by "
                        f"{discharged[target_id]} (C2 unique discharge)",
                    )
                    bump("C2-duplicate-discharge")
                    preflight_failed = True
                    continue
                if "findingClass" in target:
                    finding_class = target.get("findingClass")
                    if finding_class not in PROTECTED_CLASSES:
                        if finding_class in FINDING_CLASSES - PROTECTED_CLASSES:
                            fail(
                                errors,
                                f"{rid}: {SECURITY_REVIEWER_WAIVER_GATE} "
                                f"findingClass dimension cannot discharge {target_id}: "
                                "classified non-protected findingClass "
                                f"{finding_class!r}",
                            )
                        else:
                            fail(
                                errors,
                                f"{rid}: {SECURITY_REVIEWER_WAIVER_GATE} "
                                f"findingClass dimension cannot discharge {target_id}: "
                                f"unsupported findingClass {finding_class!r}",
                            )
                        bump("security-waiver-finding-class-fail")
                        preflight_failed = True
                        continue
                eligible_targets.append(target_id)

            if preflight_failed:
                continue
            for target_id in eligible_targets:
                discharged[target_id] = rid if isinstance(rid, str) else "<invalid>"
                bump("closure-accepted")
            continue

        for target_id in closes:
            if not isinstance(target_id, str):
                continue
            bump("closure-checked")
            entry = index.get(target_id)
            # C1: target exists and is EARLIER in the ledger.
            if entry is None or entry[0] >= pos:
                fail(errors, f"{rid}: closesRunIds target {target_id} does not reference an earlier event (C1)")
                bump("C1-fail")
                continue
            target = entry[1]
            # C2: target is an open REVISE; one obligation, one closer.
            if target.get("gate") != "REVISE" or not axis(entry[0], "revise_target_eligible"):
                fail(errors, f"{rid}: closesRunIds target {target_id} is not a REVISE event (C2)")
                bump("C2-fail")
                continue
            if target_id in discharged:
                fail(errors, f"{rid}: REVISE {target_id} already discharged by {discharged[target_id]} (C2 unique discharge)")
                bump("C2-duplicate-discharge")
                continue
            # C5 hard boundary: protected finding classes are non-user-waivable.
            if gate == USER_WAIVER_GATE and target.get("findingClass") not in (FINDING_CLASSES - PROTECTED_CLASSES):
                # Fail closed two ways: a PROTECTED class is non-user-waivable, and an
                # UNCLASSIFIED (or unknown) finding is treated as protected — omission
                # must never be the cheaper path around the boundary.
                fail(errors, f"{rid}: {USER_WAIVER_GATE} cannot discharge finding {target_id} (findingClass={target.get('findingClass')!r}: protected or unclassified) — $security-reviewer authority only (C5)")
                bump("C5-protected-waiver-fail")
                continue
            # C3 (PASS closers): identity + authority + strength against the target.
            if gate == "PASS":
                if event.get("terminalClass") == "internal-authorizing":
                    target_tuple = event.get("targetTuple")
                    evidence_id = event.get("externalEvidenceRunId")
                    evidence_positions = (
                        positions_by_run_id.get(evidence_id, [])
                        if isinstance(evidence_id, str)
                        else []
                    )
                    target_role = target.get("assignedRole") or target.get("role")
                    typed_close_ok = (
                        isinstance(target_tuple, dict)
                        and target_tuple.get("assignedInternalRole") == target_role
                        and target.get("executionRole") == "internal"
                        and target.get("terminalClass") != "external-nonauthorizing"
                        and target.get("workItem") == target_tuple.get("workItem")
                        and len(evidence_positions) == 1
                    )
                    if typed_close_ok:
                        evidence_pos, evidence_event = evidence_positions[0]
                        typed_close_ok = (
                            evidence_pos < pos
                            and evidence_event.get("terminalClass")
                            == "external-nonauthorizing"
                            and evidence_event.get("authorizing") is False
                            and evidence_event.get("closesRunIds") == []
                            and evidence_event.get("workItem")
                            == target_tuple.get("workItem")
                            and evidence_event.get("assignedRole")
                            == target_tuple.get("assignedInternalRole")
                            and evidence_event.get("artifactIdentity")
                            == target_tuple.get("artifactIdentity")
                            and event.get("artifactIdentity")
                            == evidence_event.get("artifactIdentity")
                        )
                        if evidence_event.get("provider") in {"codex", "claude"}:
                            launch_id = evidence_event.get("launchRunId")
                            launch_positions = (
                                positions_by_run_id.get(launch_id, [])
                                if isinstance(launch_id, str) else []
                            )
                            typed_close_ok = typed_close_ok and (
                                evidence_event.get("eventKind") == "terminal"
                                and evidence_event.get("status") == "completed"
                                and evidence_event.get("gate") == "PASS"
                                and "externalDispatchId" not in evidence_event
                                and "externalEvidenceRunId" not in evidence_event
                                and "externalDispatchId" not in event
                                and set(target_tuple) == {
                                    "workItem", "assignedInternalRole", "artifactIdentity"
                                }
                                and len(launch_positions) == 1
                                and launch_positions[0][0] < evidence_pos
                                and launch_positions[0][1].get("eventKind") == "launch"
                                and launch_positions[0][1].get("workItem")
                                == evidence_event.get("workItem")
                                and launch_positions[0][1].get("provider")
                                == evidence_event.get("provider")
                                and launch_positions[0][1].get("assignedRole")
                                == evidence_event.get("assignedRole")
                                and launch_positions[0][1].get("executionRole")
                                == evidence_event.get("executionRole")
                            )
                        else:
                            typed_close_ok = typed_close_ok and (
                                evidence_event.get("externalDispatchId")
                                == target_tuple.get("externalDispatchId")
                                and event.get("externalDispatchId")
                                == evidence_event.get("externalDispatchId")
                            )
                        typed_close_ok = typed_close_ok and axis(
                            evidence_pos, "artifact_evidence_eligible"
                        )
                    if not typed_close_ok:
                        fail(errors, f"{rid}: internal closer does not bind one valid frozen external evidence tuple (C3)")
                        bump("C3-external-tuple-fail")
                        continue
                    discharged[target_id] = rid if isinstance(rid, str) else "<invalid>"
                    bump("closure-accepted")
                    continue
                closer_exec = event.get("executionRole")
                if closer_exec in LEGACY_EXECUTION_ROLES:
                    closer_exec = LEGACY_EXECUTION_ROLES[closer_exec]
                # Reviewer-side ONLY (design; governance: consultant is advisory-only and
                # never a gate authority; brigade is a dispatch surface, not a verdict role).
                if closer_exec not in {"external-reviewer", "internal"}:
                    fail(errors, f"{rid}: closer executionRole {event.get('executionRole')!r} cannot discharge a review verdict — reviewer-side (external-reviewer|internal) only (C3)")
                    bump("C3-executionrole-fail")
                    continue
                t_art, c_art = target.get("artifact"), event.get("artifact")
                t_assigned = target.get("assignedRole")
                t_identity = target.get("artifactIdentity")
                external_professional_close = (
                    target.get("role") == target.get("executionRole")
                    and target.get("role") in {"external-worker", "external-reviewer"}
                    and target.get("terminalClass") == "external-nonauthorizing"
                    and target.get("closesRunIds") == []
                    and isinstance(t_assigned, str)
                    and bool(t_assigned.strip())
                    and isinstance(t_art, str)
                    and bool(t_art.strip())
                    and isinstance(t_identity, str)
                    and bool(t_identity.strip())
                    and event.get("executionRole") == "internal"
                )
                if external_professional_close:
                    closer_assigned = event.get("assignedRole")
                    if event.get("role") != t_assigned or (
                        closer_assigned is not None and closer_assigned != t_assigned
                    ):
                        fail(errors, f"{rid}: closer profession does not match {target_id} (C3-external-profession-fail)")
                        bump("C3-external-profession-fail")
                        continue
                    if event.get("scope") != target.get("scope"):
                        fail(errors, f"{rid}: closer scope does not match {target_id} (C3-external-scope-fail)")
                        bump("C3-external-scope-fail")
                        continue
                    c_identity = event.get("artifactIdentity")
                    if not isinstance(c_identity, str) or not c_identity.strip() or c_identity != t_identity:
                        fail(errors, f"{rid}: closer artifact identity does not match {target_id} (C3-external-artifact-identity-fail)")
                        bump("C3-external-artifact-identity-fail")
                        continue
                    if not isinstance(c_art, str) or not c_art.strip() or c_art == t_art:
                        fail(errors, f"{rid}: closer report is not distinct from {target_id} (C3-external-report-fail)")
                        bump("C3-external-report-fail")
                        continue
                elif isinstance(t_art, str) and t_art.strip():
                    if not isinstance(c_art, str) or c_art != t_art:
                        fail(errors, f"{rid}: closer artifact {c_art!r} != target artifact {t_art!r} (C3)")
                        bump("C3-artifact-fail")
                        continue
                t_lane, c_lane = target.get("lane"), event.get("lane")
                if isinstance(t_lane, str) and t_lane.strip():
                    if not isinstance(c_lane, str) or c_lane != t_lane:
                        fail(errors, f"{rid}: closer lane {c_lane!r} != target lane {t_lane!r} (C3)")
                        bump("C3-lane-fail")
                        continue
                if not external_professional_close:
                    t_role = target.get("role")
                    if event.get("role") != t_role and event.get("assignedRole") != t_role:
                        fail(errors, f"{rid}: closer lacks authority over {target_id} (role/assignedRole != {t_role!r}) (C3)")
                        bump("C3-authority-fail")
                        continue
                # Audit counters for the DEFERRED cathedral (fable impl gate): observe,
                # without enforcing, how often the deferred rules would have mattered.
                if target.get("provider") != event.get("provider"):
                    bump("audit-cross-provider-closure")
                t_rev, c_rev = target.get("artifactRevision"), event.get("artifactRevision")
                if isinstance(t_rev, str) and isinstance(c_rev, str) and t_rev != c_rev:
                    bump("audit-artifact-revision-drift")
                t_eff, c_eff = target.get("effort"), event.get("effort")
                if t_eff in EFFORT_ORDER:
                    # Totality (fail closed): a target that declares its tier cannot be
                    # closed by an undeclared-tier closer — omission is not a bypass.
                    if c_eff not in EFFORT_ORDER:
                        fail(errors, f"{rid}: target declares effort {t_eff} but closer omits effort (C3 totality)")
                        bump("C3-effort-omitted-fail")
                        continue
                    if (
                        target.get("provider") == event.get("provider")
                        and EFFORT_ORDER.index(c_eff) < EFFORT_ORDER.index(t_eff)
                    ):
                        fail(errors, f"{rid}: closer effort {c_eff} < target effort {t_eff} (C3 same-provider tier)")
                        bump("C3-effort-fail")
                        continue
            discharged[target_id] = rid if isinstance(rid, str) else "<invalid>"
            bump("closure-accepted")

    # Open v2 REVISE obligations. Scoped to schemaVersion 2 on purpose: the pre-existing
    # v1 ledgers migrate by hand with user sign-off (fable minimal-slice gate) instead of
    # retroactively failing every historical item.
    open_revise = [
        event for pos, event in enumerate(events)
        if axis(pos, "revise_target_eligible")
        and event.get("runId") not in discharged
    ]
    tel["open-revise"] = tel.get("open-revise", 0) + len(open_revise)
    # Unsettled launches (no terminal) are strict-mode blockers too: a lost terminal
    # must not make a possibly-REVISE run invisible to the push gate.
    open_launches = [
        event for pos, event in enumerate(events)
        if axis(pos, "launch_eligible")
        and isinstance(event.get("runId"), str)
        and event["runId"] not in terminals_by_launch
    ]
    tel["open-launches"] = tel.get("open-launches", 0) + len(open_launches)
    return open_revise, open_launches


def validate_closure(
    rows: Sequence[RuntimeLedgerRowV1],
    errors: list[str],
    telemetry: dict[str, int] | None = None,
    *,
    validity: Sequence[LedgerEventValidityV1] | None = None,
    event_validity: Sequence[LedgerEventValidityV1] | Sequence[bool] | None = None,
    context: LedgerValidationContextV1 | None = None,
) -> tuple[list[Mapping[str, object]], list[Mapping[str, object]]]:
    """Reduce authority only from raw rows or their exact receipt-minted context."""

    if rows and not isinstance(rows[0], Mapping) and not _sealed_context_is_bound(
        rows, context, errors
    ):
        return [], []
    return _validate_closure_authority(
        rows,
        errors,
        telemetry,
        validity=validity,
        event_validity=event_validity,
    )


def migration_terminal_launch_relation_error(events: list[dict], target_pos: int, item: Path) -> str | None:
    """Return the exact terminal/launch relation failure for a migration target."""
    target = events[target_pos]
    launch_id = target.get("launchRunId")
    if not isinstance(launch_id, str):
        return "migration target has no launchRunId"
    launches = [
        (pos, event) for pos, event in enumerate(events[:target_pos])
        if event.get("runId") == launch_id
    ]
    if len(launches) != 1 or launches[0][1].get("eventKind") != "launch":
        return "migration target does not reference one earlier launch"
    launch_errors: list[str] = []
    validate_event(launches[0][1], item, set(), launch_errors)
    if launch_errors:
        return "migration target launch is not individually valid"
    terminals = [
        pos for pos, event in enumerate(events)
        if event.get("eventKind") == "terminal" and event.get("launchRunId") == launch_id
    ]
    if terminals != [target_pos]:
        return "migration target launch has duplicate or mismatched terminal"
    return None


LEGACY_PROJECTION_MANIFEST_DIR = "legacy-ledger-projection-manifests"
LEGACY_PROJECTION_REGISTRY = "legacy-ledger-projections.jsonl"
LEGACY_HISTORICAL_DISPOSITIONS = "legacy-ledger-historical-dispositions"
LEGACY_PROJECTION_PROFILE_REGISTRY = {
    ("canonical-v0-shape", 1),
    ("attempt-pair-v0", 1),
    ("review-summary-v0", 1),
}
LEGACY_PROJECTION_IDS = {
    "profile": "WI-LEDGER-MIGRATION-PROFILE-UNSUPPORTED",
    "manifest": "WI-LEDGER-MIGRATION-MANIFEST-INVALID",
    "identity": "WI-LEDGER-MIGRATION-TARGET-IDENTITY",
    "ledger": "WI-LEDGER-MIGRATION-LEDGER-DRIFT",
    "digest": "WI-LEDGER-MIGRATION-TARGET-DIGEST",
    "replacement": "WI-LEDGER-MIGRATION-REPLACEMENT-MISMATCH",
    "topology": "WI-LEDGER-MIGRATION-TOPOLOGY",
    "settlement": "WI-LEDGER-MIGRATION-SETTLEMENT-FORBIDDEN",
}
_LEGACY_ROLE_MAP = {"qa": "qa-engineer", "analysis": "analyst", "lead": "lead"}
_LEGACY_EXECUTION_ROLE_MAP = {"lead": "main", "main": "main", "internal": "internal"}
_STRICT_UTC_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z", re.ASCII)


def _projection_fail(errors: list[str], kind: str, detail: str) -> None:
    fail(errors, f"{LEGACY_PROJECTION_IDS[kind]}: {detail}")


_LEDGER_H1_POLICY = "2026-08-28-ledger-h1-compatibility-boundary"
_LEDGER_H1_PROFILE = "sealed-active-prefix-v1"
_LEDGER_H1_H1_MANIFEST = "work-items/decision-h1-compatibility.json"
_LEDGER_H1_MANIFEST_DIR = "work-items/legacy-ledger-projection-manifests"
_LEDGER_H1_REGISTRY = "work-items/legacy-ledger-projections.jsonl"
_LEDGER_H1_RECEIPT_DIR = "work-items/legacy-ledger-projection-receipts"


def _ledger_h1_live_participants_exist(root: Path) -> bool:
    """Detect an exact root/archive set or one invalid observed topology."""

    try:
        return _resolve_ledger_h1_artifact_set_location(root) is not None
    except _LedgerH1AcquisitionError:
        return True


def _resolve_ledger_h1_artifact_set_location(root: Path):
    lifecycle = load_lifecycle_owner()
    try:
        return lifecycle.resolve_ledger_h1_artifact_set_location(root)
    except lifecycle.LifecycleError as exc:
        raise _LedgerH1AcquisitionError(
            exc.failure_id,
            _LEDGER_H1_H1_MANIFEST,
        ) from exc


def _ledger_h1_digest(domain: str, value: object) -> str:
    return hashlib.sha256(
        domain.encode("ascii") + b"\0" + _canonical_projection_bytes(value)
    ).hexdigest()


def _ledger_h1_authority_wire(authority: LedgerAuthorityV1) -> dict[str, bool]:
    return {
        "launchEligible": authority.launch_eligible,
        "terminalEligible": authority.terminal_eligible,
        "reviseTargetEligible": authority.revise_target_eligible,
        "closerEligible": authority.closer_eligible,
        "artifactEvidenceEligible": authority.artifact_evidence_eligible,
    }


def _ledger_h1_parse_lines(
    raw: bytes, source: str, errors: list[str]
) -> tuple[list[dict[str, object]], list[bytes]]:
    if not isinstance(raw, bytes) or not raw:
        fail(errors, f"WI-LEDGER-MIGRATION-LEDGER-DRIFT: {source} is empty or not bytes")
        return [], []
    physical = raw.splitlines(keepends=True)
    if (
        len(physical) > MAX_LEDGER_EVENTS
        or any(not line.endswith(b"\n") or not line[:-1].strip() for line in physical)
    ):
        fail(errors, f"WI-LEDGER-MIGRATION-LEDGER-DRIFT: {source} has invalid physical lines")
        return [], []
    events: list[dict[str, object]] = []
    for ordinal, line in enumerate(physical, start=1):
        body = line[:-1]
        if len(body) > MAX_LEDGER_LINE_BYTES:
            fail(errors, f"{source}:{ordinal}: event exceeds bounded line length")
            continue
        try:
            text = body.decode("utf-8", errors="strict")
            events.append(
                decode_json_object(
                    text, source=f"{source}:{ordinal}", maximum_bytes=MAX_LEDGER_LINE_BYTES
                )
            )
        except (UnicodeDecodeError, ValueError) as exc:
            fail(errors, str(exc))
    return events, physical


def _ledger_h1_runtime_rows(
    ledger_path: str,
    raw: bytes,
    prefix_line_count: int | None,
    item: Path,
    errors: list[str],
) -> tuple[RuntimeLedgerRowV1, ...]:
    events, physical = _ledger_h1_parse_lines(raw, ledger_path, errors)
    if len(events) != len(physical):
        return ()
    rows = tuple(
        RuntimeLedgerRowV1(
            MappingProxyType(copy.deepcopy(event)),
            ordinal,
            hashlib.sha256(line).hexdigest(),
            hashlib.sha256(line.rstrip(b"\r\n")).hexdigest(),
            _ledger_h1_digest(
                "orchestrarium:ledger-h1:projected-event:v1", event
            ),
            (
                "raw"
                if prefix_line_count is None
                else "sealed-prefix" if ordinal <= prefix_line_count else "strict-suffix"
            ),
            _NO_LEDGER_AUTHORITY,
        )
        for ordinal, (event, line) in enumerate(zip(events, physical), start=1)
    )
    current = [False] * len(rows)
    masks = _derive_authority_masks(rows, current, item)
    return tuple(
        RuntimeLedgerRowV1(
            row.event,
            row.raw_line_ordinal,
            row.raw_line_sha256,
            row.raw_body_sha256,
            row.projected_event_sha256,
            row.epoch,
            mask,
        )
        for row, mask in zip(rows, masks)
    )


def _ledger_h1_view_wire(
    entry: Mapping[str, object], rows: Sequence[RuntimeLedgerRowV1]
) -> tuple[dict[str, object], tuple[str, ...], tuple[str, ...]]:
    prefix_rows = list(rows[: entry["prefixLineCount"]])
    eligible = {
        row.event["runId"]
        for row in prefix_rows
        if row.authority.launch_eligible and isinstance(row.event.get("runId"), str)
    }
    settled = {
        row.event["launchRunId"]
        for row in prefix_rows
        if row.authority.terminal_eligible
        and isinstance(row.event.get("launchRunId"), str)
    }
    validity = tuple(
        LedgerEventValidityV1(False, row.authority) for row in prefix_rows
    )
    reduction_errors: list[str] = []
    open_revise_rows, _ = _validate_closure_authority(
        prefix_rows, reduction_errors, validity=validity
    )
    open_revises = {
        row["runId"]
        for row in open_revise_rows
        if isinstance(row.get("runId"), str)
    }
    sort_ids = lambda values: sorted(values, key=lambda value: value.encode("utf-8"))
    reduction = {
        "effectiveRowCount": len(prefix_rows),
        "eligibleLaunchRunIds": sort_ids(eligible),
        "settledLaunchRunIds": sort_ids(settled),
        "openLaunchRunIds": sort_ids(eligible - settled),
        "openReviseRunIds": sort_ids(open_revises),
    }
    wire_rows = []
    for row in prefix_rows:
        authority = _ledger_h1_authority_wire(row.authority)
        wire_rows.append(
            {
                "ledgerPath": entry["ledgerPath"],
                "rawLineOrdinal": row.raw_line_ordinal,
                "rawLineSha256": row.raw_line_sha256,
                "projectedEventSha256": row.projected_event_sha256,
                "authority": authority,
                "authorityMaskSha256": _ledger_h1_digest(
                    "orchestrarium:ledger-h1:authority-mask:v1", authority
                ),
            }
        )
    wire = {
        "schemaVersion": 1,
        "profileId": _LEDGER_H1_PROFILE,
        "profileVersion": 1,
        "ledgerPath": entry["ledgerPath"],
        "prefixLineCount": entry["prefixLineCount"],
        "prefixByteLength": entry["prefixByteLength"],
        "prefixSha256": entry["prefixSha256"],
        "rows": wire_rows,
        "reduction": reduction,
    }
    return wire, tuple(reduction["openReviseRunIds"]), tuple(reduction["openLaunchRunIds"])


def _ledger_h1_invalid_contexts(
    root: Path,
    artifacts: LedgerCompatibilityArtifactSetV1,
    failure_ids: Sequence[str],
    diagnostics: Sequence[str],
) -> Mapping[str, LedgerValidationContextV1]:
    token = object()
    contexts: dict[str, LedgerValidationContextV1] = {}
    for ledger_path, raw in artifacts.ledger_bytes_by_path.items():
        item = root.joinpath(*PurePosixPath(ledger_path).parts[:-1])
        row_errors: list[str] = []
        rows = _ledger_h1_runtime_rows(ledger_path, raw, 0, item, row_errors)
        contexts[ledger_path] = LedgerValidationContextV1(
            ledger_path,
            tuple(
                RuntimeLedgerRowV1(
                    row.event,
                    row.raw_line_ordinal,
                    row.raw_line_sha256,
                    row.raw_body_sha256,
                    row.projected_event_sha256,
                    "raw",
                    _NO_LEDGER_AUTHORITY,
                )
                for row in rows
            ),
            None,
            LedgerCompatibilityObservationV1(
                "invalid",
                tuple(dict.fromkeys(failure_ids)),
                tuple((*diagnostics, *row_errors)),
            ),
            (),
            (),
            token,
        )
    return MappingProxyType(contexts)


_INVALID_CURRENT_DISPOSITION_MODE = "invalid-current-nonauthorizing"
_INVALID_CURRENT_DISPOSITION_NOTICE = (
    "WI-LEDGER-COMPAT-SUFFIX-DISPOSED-NONAUTHORIZING"
)


def _invalid_current_disposition_target(
    rows: Sequence[RuntimeLedgerRowV1],
    item: Path,
    prefix_line_count: int,
    disposition_position: int,
    disposition_event: Mapping[str, object],
    errors: list[str],
) -> int | None:
    """Return one exact invalid non-control suffix target for writer and reader."""

    failure_id = "WI-LEDGER-COMPAT-SUFFIX-DISPOSITION-TARGET"
    ordinal = disposition_event.get("invalidatesRawLineOrdinal")
    target_run_id = disposition_event.get("invalidatesRunId")
    target_sha256 = disposition_event.get("invalidatesEventSha256")
    if (
        type(ordinal) is not int
        or ordinal <= prefix_line_count
        or ordinal < 1
        or ordinal > len(rows)
        or ordinal - 1 >= disposition_position
    ):
        fail(errors, f"{failure_id}: target ordinal is outside the earlier strict suffix")
        return None
    target_position = ordinal - 1
    target = rows[target_position]
    event = target.event
    run_positions = [
        position
        for position, row in enumerate(rows)
        if row.event.get("runId") == target_run_id
    ]
    if (
        target.epoch not in {"strict-suffix", "raw"}
        or target.raw_line_sha256 != target_sha256
        or event.get("runId") != target_run_id
        or len(run_positions) != 1
    ):
        fail(errors, f"{failure_id}: target ordinal/hash/runId identity differs")
        return None
    if event.get("eventKind") in {
        "launch",
        "closure-invalidation",
        LEGACY_MIGRATION_KIND,
    } or any(
        field in event
        for field in (
            "migrationAction",
            "migratesRunId",
            "revokesMigrationRunId",
            "invalidationMode",
        )
    ):
        fail(errors, f"{failure_id}: target control/lifecycle kind is ineligible")
        return None
    target_errors: list[str] = []
    _validate_event(dict(event), item, set(), target_errors)
    if not target_errors:
        fail(errors, f"{failure_id}: target is current-schema valid")
        return None
    return target_position


def _suffix_manifest_entry(
    item: Path,
    ledger_manifest_bytes: bytes,
    errors: list[str],
) -> tuple[dict[str, object], str] | None:
    manifest = _projection_json_object(
        ledger_manifest_bytes.rstrip(b"\n"), "ledger compatibility manifest", errors
    )
    required = {
        "schemaVersion", "manifestId", "policyDecision", "profiles", "entries",
        "openReviseIdentitySha256", "openReviseOracleSha256",
    }
    if (
        manifest is None
        or set(manifest) != required
        or manifest.get("schemaVersion") != 2
        or manifest.get("policyDecision") != _LEDGER_H1_POLICY
        or not isinstance(manifest.get("entries"), list)
    ):
        fail(errors, "WI-LEDGER-COMPAT-SUFFIX-DISPOSITION-TARGET: ledger manifest is invalid")
        return None
    target = _projection_target_identity(
        item, item / "agent-runs.jsonl", errors
    )
    if target is None:
        fail(errors, "WI-LEDGER-COMPAT-SUFFIX-DISPOSITION-TARGET: work item has no safe repository identity")
        return None
    _root, work_item = target
    ledger_path = f"{work_item}/agent-runs.jsonl"
    entries = [
        entry
        for entry in manifest["entries"]
        if isinstance(entry, dict)
        and entry.get("workItem") == work_item
        and entry.get("ledgerPath") == ledger_path
    ]
    if len(entries) != 1:
        fail(errors, "WI-LEDGER-COMPAT-SUFFIX-DISPOSITION-TARGET: manifest target is missing or non-unique")
        return None
    entry = entries[0]
    if (
        entry.get("profileId") != _LEDGER_H1_PROFILE
        or entry.get("profileVersion") != 1
        or type(entry.get("prefixLineCount")) is not int
        or entry["prefixLineCount"] < 1
        or type(entry.get("prefixByteLength")) is not int
        or entry["prefixByteLength"] < 1
        or not isinstance(entry.get("prefixSha256"), str)
        or SHA256_RE.fullmatch(entry["prefixSha256"]) is None
    ):
        fail(errors, "WI-LEDGER-COMPAT-SUFFIX-DISPOSITION-TARGET: manifest prefix entry is invalid")
        return None
    return entry, ledger_path


def validate_invalid_current_disposition_candidate(
    item: Path,
    ledger_bytes: bytes,
    disposition_event: Mapping[str, object],
    *,
    ledger_manifest_bytes: bytes,
) -> tuple[str, ...]:
    """Validate one preactivation append or exact replay without granting authority."""

    errors: list[str] = []
    selected = _suffix_manifest_entry(item, ledger_manifest_bytes, errors)
    if selected is None or not isinstance(ledger_bytes, bytes):
        return tuple(errors)
    entry, ledger_path = selected
    boundary = entry["prefixByteLength"]
    prefix = ledger_bytes[:boundary]
    if (
        len(prefix) != boundary
        or not prefix.endswith(b"\n")
        or len(prefix.splitlines(keepends=True)) != entry["prefixLineCount"]
        or hashlib.sha256(prefix).hexdigest() != entry["prefixSha256"]
    ):
        fail(errors, "WI-LEDGER-COMPAT-SUFFIX-DISPOSITION-TARGET: sealed prefix differs")
        return tuple(errors)
    rows = _ledger_h1_runtime_rows(
        ledger_path, ledger_bytes, entry["prefixLineCount"], item, errors
    )
    disposition_errors: list[str] = []
    _validate_event(dict(disposition_event), item, set(), disposition_errors)
    if disposition_errors:
        errors.extend(
            f"WI-LEDGER-COMPAT-SUFFIX-DISPOSITION-INVALID: {message}"
            for message in disposition_errors
        )
        return tuple(errors)
    exact_positions = [
        position
        for position, row in enumerate(rows)
        if dict(row.event) == dict(disposition_event)
    ]
    disposition_position = exact_positions[0] if len(exact_positions) == 1 else len(rows)
    run_id = disposition_event.get("runId")
    target_identity = (
        disposition_event.get("invalidatesRawLineOrdinal"),
        disposition_event.get("invalidatesRunId"),
        disposition_event.get("invalidatesEventSha256"),
    )
    for position, row in enumerate(rows):
        event = row.event
        if event.get("invalidationMode") != _INVALID_CURRENT_DISPOSITION_MODE:
            if event.get("runId") == run_id:
                fail(errors, "WI-LEDGER-COMPAT-SUFFIX-DISPOSITION-CONFLICT: disposition runId is reused")
            continue
        existing_identity = (
            event.get("invalidatesRawLineOrdinal"),
            event.get("invalidatesRunId"),
            event.get("invalidatesEventSha256"),
        )
        if position != disposition_position and (
            event.get("runId") == run_id or existing_identity == target_identity
        ):
            fail(errors, "WI-LEDGER-COMPAT-SUFFIX-DISPOSITION-CONFLICT: target or disposition differs from existing row")
    _invalid_current_disposition_target(
        rows,
        item,
        entry["prefixLineCount"],
        disposition_position,
        disposition_event,
        errors,
    )
    return tuple(errors)


def _apply_active_suffix_dispositions(
    rows: tuple[RuntimeLedgerRowV1, ...],
    item: Path,
    ledger_path: str,
    prefix_line_count: int,
) -> tuple[
    tuple[RuntimeLedgerRowV1, ...],
    tuple[SuffixDispositionNoticeV1, ...],
    tuple[str, ...],
]:
    errors: list[str] = []
    targets: dict[int, tuple[int, Mapping[str, object]]] = {}
    for disposition_position, row in enumerate(rows):
        event = row.event
        if event.get("invalidationMode") != _INVALID_CURRENT_DISPOSITION_MODE:
            continue
        disposition_run_id = event.get("runId")
        if sum(
            other.event.get("runId") == disposition_run_id for other in rows
        ) != 1:
            fail(
                errors,
                "WI-LEDGER-COMPAT-SUFFIX-DISPOSITION-CONFLICT: disposition runId is not unique",
            )
            continue
        disposition_errors: list[str] = []
        _validate_event(dict(event), item, set(), disposition_errors)
        if disposition_errors:
            errors.extend(
                f"WI-LEDGER-COMPAT-SUFFIX-DISPOSITION-INVALID: {message}"
                for message in disposition_errors
            )
            continue
        target_position = _invalid_current_disposition_target(
            rows,
            item,
            prefix_line_count,
            disposition_position,
            event,
            errors,
        )
        if target_position is None:
            continue
        if target_position in targets:
            fail(errors, "WI-LEDGER-COMPAT-SUFFIX-DISPOSITION-CONFLICT: target has more than one disposition")
            continue
        targets[target_position] = (disposition_position, event)
    if errors:
        return rows, (), tuple(errors)
    effective = list(rows)
    notices: list[SuffixDispositionNoticeV1] = []
    for target_position, (disposition_position, disposition_event) in targets.items():
        target = rows[target_position]
        effective[target_position] = RuntimeLedgerRowV1(
            target.event,
            target.raw_line_ordinal,
            target.raw_line_sha256,
            target.raw_body_sha256,
            target.projected_event_sha256,
            "disposed-suffix",
            _NO_LEDGER_AUTHORITY,
        )
        notices.append(
            SuffixDispositionNoticeV1(
                _INVALID_CURRENT_DISPOSITION_NOTICE,
                ledger_path,
                target.raw_line_ordinal,
                target.raw_line_sha256,
                str(target.event.get("runId")),
                str(disposition_event.get("runId")),
                rows[disposition_position].raw_line_ordinal,
            )
        )
    notices.sort(
        key=lambda notice: (
            notice.ledger_path.encode("utf-8"),
            notice.raw_line_ordinal,
            notice.disposition_line_ordinal,
        )
    )
    return tuple(effective), tuple(notices), ()


def _ledger_h1_candidate_group(
    root: Path, artifacts: LedgerCompatibilityArtifactSetV1
) -> Mapping[str, LedgerValidationContextV1]:
    failures: list[str] = []
    diagnostics: list[str] = []

    def reject(failure_id: str, detail: str) -> None:
        failures.append(failure_id)
        diagnostics.append(f"{failure_id}: {detail}")

    byte_fields = (
        artifacts.h1_manifest_bytes,
        artifacts.ledger_manifest_bytes,
        artifacts.registry_bytes,
    )
    if (
        not isinstance(artifacts.ledger_bytes_by_path, Mapping)
        or not artifacts.ledger_bytes_by_path
        or any(
            not isinstance(path, str)
            or not _safe_repo_relative(path)
            or not isinstance(raw, bytes)
            for path, raw in artifacts.ledger_bytes_by_path.items()
        )
        or any(not isinstance(value, bytes) or not value for value in byte_fields)
        or not isinstance(artifacts.receipt_bytes_by_path, Mapping)
        or not artifacts.receipt_bytes_by_path
        or any(
            not isinstance(path, str)
            or not _safe_repo_relative(path)
            or not isinstance(raw, bytes)
            or not raw
            for path, raw in artifacts.receipt_bytes_by_path.items()
        )
        or not isinstance(artifacts.participant_locations_by_path, Mapping)
    ):
        reject("WI-LEDGER-COMPAT-ACTIVATION-PARTIAL", "candidate artifact set is incomplete or has wrong member types")
        return _ledger_h1_invalid_contexts(root, artifacts, failures, diagnostics)

    manifest = _projection_json_object(
        artifacts.ledger_manifest_bytes.rstrip(b"\n"), artifacts.ledger_manifest_path, diagnostics
    )
    manifest_fields = {
        "schemaVersion", "manifestId", "policyDecision", "profiles", "entries",
        "openReviseIdentitySha256", "openReviseOracleSha256",
    }
    receipt_fields = {
        "schemaVersion", "receiptId", "state", "operationGroupId", "policyDecision",
        "ledgerManifestPath", "ledgerManifestSha256", "h1ManifestPath", "h1ManifestSha256",
        "memberOperationIds", "memberRecordSha256", "registryBeforeSha256",
        "registryAfterSha256", "recordedAt",
    }
    if manifest is None or set(manifest) != manifest_fields:
        reject("WI-LEDGER-MIGRATION-MANIFEST-INVALID", "ledger compatibility manifest shape is invalid")
        return _ledger_h1_invalid_contexts(root, artifacts, failures, diagnostics)
    profiles = manifest.get("profiles")
    entries = manifest.get("entries")
    if (
        manifest.get("schemaVersion") != 2
        or manifest.get("policyDecision") != _LEDGER_H1_POLICY
        or not isinstance(manifest.get("manifestId"), str)
        or SCRATCH_IDENTIFIER_RE.fullmatch(manifest["manifestId"]) is None
        or profiles != [{"profileId": _LEDGER_H1_PROFILE, "profileVersion": 1}]
        or not isinstance(entries, list)
        or len(entries) != 2
    ):
        reject("WI-LEDGER-MIGRATION-MANIFEST-INVALID", "ledger compatibility manifest identity/profile is invalid")
        return _ledger_h1_invalid_contexts(root, artifacts, failures, diagnostics)
    entry_fields = {
        "entryId", "profileId", "profileVersion", "workItem", "ledgerPath",
        "prefixLineCount", "prefixByteLength", "prefixSha256", "projectedViewSha256",
    }
    if any(not isinstance(entry, dict) or set(entry) != entry_fields for entry in entries):
        reject("WI-LEDGER-MIGRATION-MANIFEST-INVALID", "ledger compatibility entry shape is invalid")
        return _ledger_h1_invalid_contexts(root, artifacts, failures, diagnostics)
    ledger_paths = [entry["ledgerPath"] for entry in entries]
    sorted_paths = sorted(ledger_paths, key=lambda value: value.encode("utf-8") if isinstance(value, str) else b"")
    if ledger_paths != sorted_paths or len(set(ledger_paths)) != 2:
        reject("WI-LEDGER-COMPAT-MEMBER-ORDER", "manifest entries are not uniquely UTF-8 sorted")
    if set(artifacts.ledger_bytes_by_path) != set(ledger_paths):
        reject("WI-LEDGER-COMPAT-ACTIVATION-PARTIAL", "candidate ledger keys differ from manifest entries")
    location_records = artifacts.participant_locations_by_path
    if location_records and set(location_records) != set(ledger_paths):
        reject(
            "WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS",
            "participant location keys differ from manifest entries",
        )
    manifest_sha = hashlib.sha256(artifacts.ledger_manifest_bytes).hexdigest()
    h1_sha = hashlib.sha256(artifacts.h1_manifest_bytes).hexdigest()
    if (
        artifacts.h1_manifest_path != _LEDGER_H1_H1_MANIFEST
        or artifacts.ledger_manifest_path
        != f"{_LEDGER_H1_MANIFEST_DIR}/{manifest['manifestId']}.json"
    ):
        reject("WI-LEDGER-MIGRATION-MANIFEST-INVALID", "manifest paths are not canonical")

    entry_rows: dict[str, tuple[RuntimeLedgerRowV1, ...]] = {}
    views: dict[str, LedgerCompatibilityViewV1] = {}
    revise_identities: list[str] = []
    open_launch_ids: set[str] = set()
    physical_items_by_path: dict[str, Path] = {}
    for entry in entries:
        path = entry.get("ledgerPath")
        work_item = entry.get("workItem")
        if (
            not isinstance(path, str)
            or not isinstance(work_item, str)
            or path != f"{work_item}/agent-runs.jsonl"
            or PurePosixPath(work_item).parts[:2] != ("work-items", "active")
            or len(PurePosixPath(work_item).parts) != 3
            or entry.get("profileId") != _LEDGER_H1_PROFILE
            or entry.get("profileVersion") != 1
            or not isinstance(entry.get("entryId"), str)
            or not isinstance(entry.get("prefixLineCount"), int)
            or entry.get("prefixLineCount", 0) < 1
            or not isinstance(entry.get("prefixByteLength"), int)
            or entry.get("prefixByteLength", 0) < 1
            or not isinstance(entry.get("prefixSha256"), str)
            or SHA256_RE.fullmatch(entry["prefixSha256"]) is None
            or not isinstance(entry.get("projectedViewSha256"), str)
            or SHA256_RE.fullmatch(entry["projectedViewSha256"]) is None
        ):
            reject("WI-LEDGER-MIGRATION-MANIFEST-INVALID", "manifest entry identity or seal type is invalid")
            continue
        raw = artifacts.ledger_bytes_by_path.get(path)
        if not isinstance(raw, bytes):
            continue
        boundary = entry["prefixByteLength"]
        prefix = raw[:boundary]
        if (
            len(prefix) != boundary
            or not prefix.endswith(b"\n")
            or len(prefix.splitlines(keepends=True)) != entry["prefixLineCount"]
            or hashlib.sha256(prefix).hexdigest() != entry["prefixSha256"]
        ):
            reject("WI-LEDGER-MIGRATION-LEDGER-DRIFT", f"sealed prefix differs for {path}")
            continue
        physical_work_item = work_item
        physical_ledger_path = path
        if location_records:
            supplied_location = location_records.get(path)
            lifecycle = load_lifecycle_owner()
            try:
                fresh_location = lifecycle.resolve_work_item_ledger_location(
                    root,
                    logical_work_item=work_item,
                    logical_ledger_path=path,
                )
            except lifecycle.LifecycleError as exc:
                reject(
                    "WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS",
                    f"participant location cannot be re-resolved for {path}: {exc.failure_id}",
                )
                continue
            if supplied_location != fresh_location:
                reject(
                    "WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS",
                    f"participant location metadata differs for {path}",
                )
                continue
            physical_work_item = getattr(fresh_location, "physical_work_item", None)
            physical_ledger_path = getattr(fresh_location, "physical_ledger_path", None)
            if (
                getattr(fresh_location, "logical_work_item", None) != work_item
                or getattr(fresh_location, "logical_ledger_path", None) != path
                or not isinstance(physical_work_item, str)
                or not _safe_repo_relative(physical_work_item)
                or not isinstance(physical_ledger_path, str)
                or not _safe_repo_relative(physical_ledger_path)
                or physical_ledger_path
                != f"{physical_work_item}/agent-runs.jsonl"
                or PurePosixPath(physical_work_item).name
                != PurePosixPath(work_item).name
            ):
                reject(
                    "WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS",
                    f"participant logical and physical identities differ for {path}",
                )
                continue
        item = root.joinpath(*PurePosixPath(physical_work_item).parts)
        physical_ledger = root.joinpath(*PurePosixPath(physical_ledger_path).parts)
        identity_errors: list[str] = []
        identity = _projection_target_identity(
            item,
            physical_ledger,
            identity_errors,
            require_ledger=bool(location_records),
        )
        if identity is None or identity[1] != physical_work_item:
            reject("WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS", f"unsafe manifest target {work_item}")
            diagnostics.extend(identity_errors)
            continue
        physical_items_by_path[path] = item
        rows = _ledger_h1_runtime_rows(path, raw, entry["prefixLineCount"], item, diagnostics)
        if not rows:
            continue
        wire, open_revises, open_launches = _ledger_h1_view_wire(entry, rows)
        projected_digest = _ledger_h1_digest(
            "orchestrarium:ledger-h1:projected-view:v1", wire
        )
        if projected_digest != entry["projectedViewSha256"]:
            reject("WI-LEDGER-MIGRATION-REPLACEMENT-MISMATCH", f"projected view differs for {path}")
            continue
        entry_rows[path] = rows
        views[path] = LedgerCompatibilityViewV1(
            MappingProxyType(wire), projected_digest, MappingProxyType(wire["reduction"])
        )
        logical_work_item = item.name
        revise_rows = [
            row
            for row in rows
            if row.event.get("runId") in open_revises
        ]
        if any(row.event.get("workItem") != logical_work_item for row in revise_rows):
            reject(
                "WI-LEDGER-MIGRATION-REPLACEMENT-MISMATCH",
                f"open-REVISE logical work-item identity differs for {path}",
            )
            continue
        revise_identities.extend(
            f"{logical_work_item}\0{run_id}" for run_id in open_revises
        )
        open_launch_ids.update(open_launches)

    revise_identities.sort(key=lambda value: value.encode("utf-8"))
    identity_payload = "\n".join(revise_identities).encode("utf-8")
    oracle = {
        "schemaVersion": 1,
        "ledgerPrefixes": [
            {"ledgerPath": entry["ledgerPath"], "prefixSha256": entry["prefixSha256"]}
            for entry in entries
        ],
        "openReviseIdentities": revise_identities,
    }
    if (
        hashlib.sha256(identity_payload).hexdigest() != manifest.get("openReviseIdentitySha256")
        or _ledger_h1_digest(
            "orchestrarium:ledger-h1:open-revise-oracle:v1", oracle
        ) != manifest.get("openReviseOracleSha256")
    ):
        reject("WI-LEDGER-MIGRATION-REPLACEMENT-MISMATCH", "group open-REVISE oracle differs")

    registry_lines = artifacts.registry_bytes.splitlines(keepends=True)
    parsed_registry: list[dict[str, object] | None] = []
    for ordinal, line in enumerate(registry_lines, start=1):
        if not line.endswith(b"\n"):
            reject("WI-LEDGER-COMPAT-ACTIVATION-PARTIAL", "registry has a nonterminated line")
            parsed_registry.append(None)
            continue
        parsed_registry.append(
            _projection_json_object(line[:-1], f"candidate registry:{ordinal}", diagnostics)
        )
    receipts: dict[str, dict[str, object]] = {}
    for receipt_path, receipt_bytes in artifacts.receipt_bytes_by_path.items():
        receipt = _projection_json_object(
            receipt_bytes.rstrip(b"\n"), receipt_path, diagnostics
        )
        if receipt is None or set(receipt) != receipt_fields:
            reject("WI-LEDGER-COMPAT-RECEIPT-INVALID", f"receipt {receipt_path} shape is invalid")
            continue
        receipts[receipt_path] = receipt

    sealed_positions = [
        position
        for position, record in enumerate(parsed_registry)
        if isinstance(record, dict)
        and (
            record.get("profileId") == _LEDGER_H1_PROFILE
            or record.get("policyDecision") == _LEDGER_H1_POLICY
        )
    ]
    groups: list[tuple[int, list[dict[str, object]], list[bytes]]] = []
    cursor = 0
    while cursor < len(sealed_positions):
        start = sealed_positions[cursor]
        first = parsed_registry[start]
        group_id = first.get("operationGroupId") if isinstance(first, dict) else None
        positions: list[int] = []
        while (
            cursor < len(sealed_positions)
            and sealed_positions[cursor] == start + len(positions)
            and isinstance(parsed_registry[sealed_positions[cursor]], dict)
            and parsed_registry[sealed_positions[cursor]].get("operationGroupId") == group_id
        ):
            positions.append(sealed_positions[cursor])
            cursor += 1
        records = [parsed_registry[position] for position in positions]
        groups.append(
            (
                start,
                [record for record in records if isinstance(record, dict)],
                [registry_lines[position] for position in positions],
            )
        )
    if len(groups) not in {1, 2}:
        reject("WI-LEDGER-COMPAT-ACTIVATION-PARTIAL", "sealed-prefix registry history must contain apply and optional revoke")

    expected_receipt_paths: set[str] = set()
    apply_records: list[dict[str, object]] = []
    apply_lines: list[bytes] = []
    final_state = "invalid"
    for group_index, (start, records, lines) in enumerate(groups):
        state = "apply" if group_index == 0 else "revoke"
        if len(records) != 2 or len(lines) != 2:
            reject("WI-LEDGER-COMPAT-ACTIVATION-PARTIAL", f"{state} group is not one contiguous two-member group")
            continue
        expected_group = "g-" + _ledger_h1_digest(
            "orchestrarium:ledger-h1:registry-group:v1",
            [state, _LEDGER_H1_POLICY, manifest_sha, h1_sha, [entry["entryId"] for entry in entries]],
        )
        before = b"".join(registry_lines[:start])
        after = b"".join(registry_lines[: start + 2])
        member_ids: list[str] = []
        member_hashes = [hashlib.sha256(line).hexdigest() for line in lines]
        base_fields = {
            "schemaVersion", "operationId", "operationGroupId", "groupMemberIndex",
            "groupMemberCount", "state", "profileId", "profileVersion", "policyDecision",
            "manifestId", "manifestSha256", "manifestEntryId", "h1ManifestPath",
            "h1ManifestSha256", "workItem", "ledgerPath", "prefixLineCount",
            "prefixByteLength", "prefixSha256", "projectedViewSha256", "recordedAt",
        }
        fields = base_fields | (
            {"revokeOfOperationId", "revokeOfOperationGroupId", "revokeOfRecordSha256"}
            if state == "revoke"
            else set()
        )
        recorded_at = records[0].get("recordedAt")
        for index, (record, entry) in enumerate(zip(records, entries), start=1):
            expected_operation = "m:" + _ledger_h1_digest(
                "orchestrarium:ledger-h1:activation-member:v1",
                [expected_group, index, entry["entryId"]],
            )
            member_ids.append(expected_operation)
            exact = {
                "schemaVersion": 2,
                "operationId": expected_operation,
                "operationGroupId": expected_group,
                "groupMemberIndex": index,
                "groupMemberCount": 2,
                "state": state,
                "profileId": _LEDGER_H1_PROFILE,
                "profileVersion": 1,
                "policyDecision": _LEDGER_H1_POLICY,
                "manifestId": manifest["manifestId"],
                "manifestSha256": manifest_sha,
                "manifestEntryId": entry["entryId"],
                "h1ManifestPath": artifacts.h1_manifest_path,
                "h1ManifestSha256": h1_sha,
                "workItem": entry["workItem"],
                "ledgerPath": entry["ledgerPath"],
                "prefixLineCount": entry["prefixLineCount"],
                "prefixByteLength": entry["prefixByteLength"],
                "prefixSha256": entry["prefixSha256"],
                "projectedViewSha256": entry["projectedViewSha256"],
                "recordedAt": recorded_at,
            }
            if state == "revoke" and index <= len(apply_records):
                exact.update(
                    {
                        "revokeOfOperationId": apply_records[index - 1]["operationId"],
                        "revokeOfOperationGroupId": apply_records[index - 1]["operationGroupId"],
                        "revokeOfRecordSha256": hashlib.sha256(apply_lines[index - 1]).hexdigest(),
                    }
                )
            if set(record) != fields or record != exact:
                reject("WI-LEDGER-COMPAT-MEMBER-ORDER", f"registry {state} member {index} binding differs")
        if (
            not isinstance(recorded_at, str)
            or _STRICT_UTC_RE.fullmatch(recorded_at) is None
            or [record.get("groupMemberIndex") for record in records] != [1, 2]
        ):
            reject("WI-LEDGER-COMPAT-MEMBER-ORDER", f"registry {state} group order or timestamp differs")
        receipt_id = "r-" + _ledger_h1_digest(
            "orchestrarium:ledger-h1:receipt-id:v1",
            [state, expected_group, hashlib.sha256(before).hexdigest(), hashlib.sha256(after).hexdigest()],
        )
        receipt_path = f"{_LEDGER_H1_RECEIPT_DIR}/{receipt_id}.json"
        expected_receipt_paths.add(receipt_path)
        expected_receipt = {
            "schemaVersion": 2,
            "receiptId": receipt_id,
            "state": state,
            "operationGroupId": expected_group,
            "policyDecision": _LEDGER_H1_POLICY,
            "ledgerManifestPath": artifacts.ledger_manifest_path,
            "ledgerManifestSha256": manifest_sha,
            "h1ManifestPath": artifacts.h1_manifest_path,
            "h1ManifestSha256": h1_sha,
            "memberOperationIds": member_ids,
            "memberRecordSha256": member_hashes,
            "registryBeforeSha256": hashlib.sha256(before).hexdigest(),
            "registryAfterSha256": hashlib.sha256(after).hexdigest(),
            "recordedAt": recorded_at,
        }
        if receipts.get(receipt_path) != expected_receipt:
            reject("WI-LEDGER-COMPAT-RECEIPT-INVALID", f"{state} receipt is missing or differs")
        if state == "apply":
            apply_records = records
            apply_lines = lines
            final_state = "active"
        elif apply_records:
            final_state = "revoked"

    if set(artifacts.receipt_bytes_by_path) != expected_receipt_paths:
        reject("WI-LEDGER-COMPAT-RECEIPT-INVALID", "candidate receipt paths differ from registry-derived paths")

    if failures or set(entry_rows) != set(ledger_paths) or set(views) != set(ledger_paths):
        if not failures:
            reject("WI-LEDGER-COMPAT-ACTIVATION-PARTIAL", "not every manifest ledger projected")
        return _ledger_h1_invalid_contexts(root, artifacts, failures, diagnostics)

    disposition_notices_by_path: dict[
        str, tuple[SuffixDispositionNoticeV1, ...]
    ] = {}
    if final_state == "active":
        for entry in entries:
            path = entry["ledgerPath"]
            item = physical_items_by_path.get(
                path,
                root.joinpath(*PurePosixPath(entry["workItem"]).parts),
            )
            effective_rows, notices, disposition_errors = (
                _apply_active_suffix_dispositions(
                    entry_rows[path],
                    item,
                    path,
                    entry["prefixLineCount"],
                )
            )
            entry_rows[path] = effective_rows
            disposition_notices_by_path[path] = notices
            for message in disposition_errors:
                failures.append(message.split(":", 1)[0])
                diagnostics.append(message)
        if failures:
            return _ledger_h1_invalid_contexts(
                root, artifacts, failures, diagnostics
            )

    h1_projection_partition = (
        artifacts.ledger_manifest_path,
        manifest_sha,
        _LEDGER_H1_REGISTRY,
        hashlib.sha256(artifacts.registry_bytes).hexdigest(),
        tuple(
            (start + offset + 1, hashlib.sha256(line).hexdigest())
            for start, _records, lines in groups
            for offset, line in enumerate(lines)
        ),
    )

    if final_state == "revoked":
        token = _LedgerInvocationTokenV1(
            MappingProxyType({}), h1_projection_partition
        )
        contexts = {
            path: LedgerValidationContextV1(
                path,
                tuple(
                    RuntimeLedgerRowV1(
                        row.event,
                        row.raw_line_ordinal,
                        row.raw_line_sha256,
                        row.raw_body_sha256,
                        row.projected_event_sha256,
                        "raw",
                        _NO_LEDGER_AUTHORITY,
                    )
                    for row in entry_rows[path]
                ),
                None,
                LedgerCompatibilityObservationV1("revoked", (), ()),
                (),
                (),
                token,
            )
            for path in ledger_paths
        }
        return MappingProxyType(contexts)

    token = _LedgerInvocationTokenV1(
        MappingProxyType(dict(entry_rows)), h1_projection_partition
    )
    open_launch_tuple = tuple(sorted(open_launch_ids, key=lambda value: value.encode("utf-8")))
    contexts = {
        path: LedgerValidationContextV1(
            path,
            entry_rows[path],
            views[path],
            LedgerCompatibilityObservationV1(
                "active", (), (), disposition_notices_by_path.get(path, ())
            ),
            tuple(revise_identities),
            open_launch_tuple,
            token,
        )
        for path in ledger_paths
    }
    return MappingProxyType(contexts)


def _ledger_h1_acquisition_failure_context(
    error: _LedgerH1AcquisitionError,
) -> LedgerValidationContextV1:
    diagnostic = (
        f"{error.failure_id}: H1 participant location failed for "
        f"{error.logical_ledger_path}"
    )
    return LedgerValidationContextV1(
        error.logical_ledger_path,
        (),
        None,
        LedgerCompatibilityObservationV1(
            "invalid", (error.failure_id,), (diagnostic,)
        ),
        (),
        (),
        object(),
    )


def _load_live_ledger_h1_artifacts(
    root: Path,
) -> LedgerCompatibilityArtifactSetV1 | None:
    """Acquire one complete live participant set without interpreting authority."""

    location = _resolve_ledger_h1_artifact_set_location(root)
    if location is None:
        return None
    physical_base = root.joinpath(*PurePosixPath(location.physical_base).parts)
    participants = (
        physical_base / Path(_LEDGER_H1_H1_MANIFEST).name,
        physical_base / Path(_LEDGER_H1_MANIFEST_DIR).name,
        physical_base / Path(_LEDGER_H1_REGISTRY).name,
        physical_base / Path(_LEDGER_H1_RECEIPT_DIR).name,
    )
    h1_path, manifest_dir, registry_path, receipt_dir = participants
    if (
        not h1_path.is_file()
        or not manifest_dir.is_dir()
        or not registry_path.is_file()
        or not receipt_dir.is_dir()
        or any(_is_link_or_reparse(path) for path in participants)
    ):
        return None
    try:
        registry_bytes = registry_path.read_bytes()
        registry_lines = registry_bytes.splitlines(keepends=True)
        acquisition_errors: list[str] = []
        parsed = [
            _projection_json_object(
                line[:-1], f"{registry_path}:{ordinal}", acquisition_errors
            )
            if line.endswith(b"\n")
            else None
            for ordinal, line in enumerate(registry_lines, start=1)
        ]
        sealed_positions = [
            position
            for position, record in enumerate(parsed)
            if isinstance(record, dict)
            and (
                record.get("profileId") == _LEDGER_H1_PROFILE
                or record.get("policyDecision") == _LEDGER_H1_POLICY
            )
        ]
        if len(sealed_positions) not in {2, 4}:
            return None
        groups: list[tuple[int, list[dict[str, object]]]] = []
        cursor = 0
        while cursor < len(sealed_positions):
            start = sealed_positions[cursor]
            first = parsed[start]
            group_id = first.get("operationGroupId") if isinstance(first, dict) else None
            positions: list[int] = []
            while (
                cursor < len(sealed_positions)
                and sealed_positions[cursor] == start + len(positions)
                and isinstance(parsed[sealed_positions[cursor]], dict)
                and parsed[sealed_positions[cursor]].get("operationGroupId") == group_id
            ):
                positions.append(sealed_positions[cursor])
                cursor += 1
            records = [parsed[position] for position in positions]
            if len(records) != 2 or not all(isinstance(record, dict) for record in records):
                return None
            groups.append((start, records))
        manifest_ids = {
            record.get("manifestId")
            for _start, records in groups
            for record in records
        }
        if len(manifest_ids) != 1:
            return None
        manifest_id = next(iter(manifest_ids))
        if not isinstance(manifest_id, str) or SCRATCH_IDENTIFIER_RE.fullmatch(manifest_id) is None:
            return None
        manifest_relative = f"{_LEDGER_H1_MANIFEST_DIR}/{manifest_id}.json"
        h1_relative = _LEDGER_H1_H1_MANIFEST
        receipt_bytes_by_path: dict[str, bytes] = {}
        for start, records in groups:
            state = records[0].get("state")
            group_id = records[0].get("operationGroupId")
            if state not in {"apply", "revoke"} or not isinstance(group_id, str):
                return None
            before_sha = hashlib.sha256(b"".join(registry_lines[:start])).hexdigest()
            after_sha = hashlib.sha256(b"".join(registry_lines[: start + 2])).hexdigest()
            receipt_id = "r-" + _ledger_h1_digest(
                "orchestrarium:ledger-h1:receipt-id:v1",
                [state, group_id, before_sha, after_sha],
            )
            receipt_relative = f"{_LEDGER_H1_RECEIPT_DIR}/{receipt_id}.json"
            receipt_path = receipt_dir / f"{receipt_id}.json"
            if (
                receipt_path.parent != receipt_dir
                or not receipt_path.is_file()
                or _is_link_or_reparse(receipt_path)
            ):
                return None
            receipt_bytes_by_path[receipt_relative] = receipt_path.read_bytes()
        manifest_path = manifest_dir / f"{manifest_id}.json"
        if (
            manifest_path.parent != manifest_dir
            or not manifest_path.is_file()
            or _is_link_or_reparse(manifest_path)
        ):
            return None
        manifest_bytes = manifest_path.read_bytes()
        manifest = _projection_json_object(
            manifest_bytes.rstrip(b"\n"), manifest_path, acquisition_errors
        )
        if not isinstance(manifest, dict) or not isinstance(
            manifest.get("entries"), list
        ):
            return None
        ledger_bytes_by_path: dict[str, bytes] = {}
        participant_locations_by_path: dict[str, object] = {}
        lifecycle = load_lifecycle_owner()
        for entry in manifest["entries"]:
            ledger_relative = (
                entry.get("ledgerPath") if isinstance(entry, dict) else None
            )
            logical_work_item = (
                entry.get("workItem") if isinstance(entry, dict) else None
            )
            if (
                not isinstance(ledger_relative, str)
                or not _safe_repo_relative(ledger_relative)
                or not isinstance(logical_work_item, str)
                or not _safe_repo_relative(logical_work_item)
            ):
                return None
            try:
                location = lifecycle.resolve_work_item_ledger_location(
                    root,
                    logical_work_item=logical_work_item,
                    logical_ledger_path=ledger_relative,
                )
            except lifecycle.LifecycleError as exc:
                raise _LedgerH1AcquisitionError(
                    exc.failure_id, ledger_relative
                ) from exc
            physical_ledger_path = getattr(location, "physical_ledger_path", None)
            if not isinstance(physical_ledger_path, str) or not _safe_repo_relative(
                physical_ledger_path
            ):
                return None
            ledger_path = root.joinpath(*PurePosixPath(physical_ledger_path).parts)
            if not ledger_path.is_file() or _is_link_or_reparse(ledger_path):
                return None
            ledger_bytes_by_path[ledger_relative] = ledger_path.read_bytes()
            participant_locations_by_path[ledger_relative] = location
        return LedgerCompatibilityArtifactSetV1(
            MappingProxyType(ledger_bytes_by_path),
            h1_relative,
            h1_path.read_bytes(),
            manifest_relative,
            manifest_bytes,
            registry_bytes,
            MappingProxyType(receipt_bytes_by_path),
            MappingProxyType(participant_locations_by_path),
        )
    except OSError:
        return None


def _load_effective_ledger_group(
    root: Path,
    *,
    compatibility_artifacts: LedgerCompatibilityArtifactSetV1 | None = None,
) -> Mapping[str, LedgerValidationContextV1]:
    """Load and validate one receipt-bound two-ledger group without caching."""

    if compatibility_artifacts is None:
        try:
            compatibility_artifacts = _load_live_ledger_h1_artifacts(root)
        except _LedgerH1AcquisitionError as exc:
            context = _ledger_h1_acquisition_failure_context(exc)
            return MappingProxyType({exc.logical_ledger_path: context})
        if compatibility_artifacts is None:
            return MappingProxyType({})
    return _ledger_h1_candidate_group(Path(root), compatibility_artifacts)


def _ledger_h1_selection_failure(
    selected_ledger_path: str,
    diagnostic: str,
) -> LedgerValidationContextV1:
    return LedgerValidationContextV1(
        selected_ledger_path,
        (),
        None,
        LedgerCompatibilityObservationV1(
            "invalid",
            ("WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS",),
            (diagnostic,),
        ),
        (),
        (),
        object(),
    )


def _classify_ledger_h1_selection(
    item_relative: str,
    selected_ledger_path: str,
    artifacts: LedgerCompatibilityArtifactSetV1,
    contexts: Mapping[str, LedgerValidationContextV1],
) -> tuple[str, object | LedgerValidationContextV1 | None]:
    """Classify one selection only after its complete H1 group is validated."""

    invalid_contexts = [
        context
        for context in contexts.values()
        if context.observation.activation_state == "invalid"
    ]
    if invalid_contexts:
        return "invalid", invalid_contexts[0]
    exact_matches: list[object] = []
    intersections = 0
    for location in artifacts.participant_locations_by_path.values():
        item_match = item_relative in {
            getattr(location, "logical_work_item", None),
            getattr(location, "physical_work_item", None),
        }
        ledger_match = selected_ledger_path in {
            getattr(location, "logical_ledger_path", None),
            getattr(location, "physical_ledger_path", None),
        }
        if item_match and ledger_match:
            exact_matches.append(location)
        elif item_match or ledger_match:
            intersections += 1
    if len(exact_matches) == 1 and intersections == 0:
        location = exact_matches[0]
        context_key = getattr(location, "logical_ledger_path", None)
        context = contexts.get(context_key)
        if context is not None:
            return "member", location
    if exact_matches or intersections:
        return "invalid", _ledger_h1_selection_failure(
            selected_ledger_path,
            "WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS: selected item and ledger partially, multiply, or cross-match H1 participants",
        )
    return "ordinary-nonmember", None


def load_effective_ledger_view(
    root: Path,
    item: Path,
    selected_ledger_path: str,
    *,
    compatibility_artifacts: LedgerCompatibilityArtifactSetV1 | None = None,
) -> LedgerValidationContextV1:
    """Return the selected raw or receipt-activated effective ledger context."""

    root = Path(root)
    resolved_artifacts = compatibility_artifacts
    if resolved_artifacts is None and _ledger_h1_live_participants_exist(root):
        try:
            resolved_artifacts = _load_live_ledger_h1_artifacts(root)
        except _LedgerH1AcquisitionError as exc:
            return _ledger_h1_acquisition_failure_context(exc)
    physical_selected_path = selected_ledger_path
    context_key = selected_ledger_path
    selection_classification = "ordinary-nonmember"
    contexts: Mapping[str, LedgerValidationContextV1] = MappingProxyType({})
    if resolved_artifacts is not None:
        contexts = _load_effective_ledger_group(
            root, compatibility_artifacts=resolved_artifacts
        )
        try:
            item_relative = Path(item).absolute().relative_to(root.absolute()).as_posix()
        except ValueError:
            item_relative = ""
        selection_classification, selection = _classify_ledger_h1_selection(
            item_relative,
            selected_ledger_path,
            resolved_artifacts,
            contexts,
        )
        if selection_classification == "invalid":
            assert isinstance(selection, LedgerValidationContextV1)
            return selection
        if selection_classification == "member":
            location = selection
            physical_selected_path = getattr(location, "physical_ledger_path")
            context_key = getattr(location, "logical_ledger_path")
    selected = root.joinpath(*PurePosixPath(physical_selected_path).parts)
    identity_errors: list[str] = []
    identity = _projection_target_identity(item, selected, identity_errors)
    token = object()
    if identity is None or physical_selected_path != f"{identity[1]}/agent-runs.jsonl":
        diagnostic = "WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS: selected ledger identity is invalid"
        return LedgerValidationContextV1(
            selected_ledger_path, (), None,
            LedgerCompatibilityObservationV1("invalid", ("WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS",), tuple((*identity_errors, diagnostic))),
            (), (), token,
        )
    if context_key in contexts:
        return contexts[context_key]
    if (
        compatibility_artifacts is not None
        and selection_classification != "ordinary-nonmember"
    ):
        diagnostic = "WI-LEDGER-COMPAT-ACTIVATION-PARTIAL: selected ledger is absent from candidate group"
        return LedgerValidationContextV1(
            selected_ledger_path, (), None,
            LedgerCompatibilityObservationV1("invalid", ("WI-LEDGER-COMPAT-ACTIVATION-PARTIAL",), (diagnostic,)),
            (), (), token,
        )
    if resolved_artifacts is None and _ledger_h1_live_participants_exist(root):
        diagnostic = "WI-LEDGER-COMPAT-ACTIVATION-INCOMPLETE: compatibility participants exist without one valid receipt-bound group"
        return LedgerValidationContextV1(
            selected_ledger_path, (), None,
            LedgerCompatibilityObservationV1("invalid", ("WI-LEDGER-COMPAT-ACTIVATION-INCOMPLETE",), (diagnostic,)),
            (), (), token,
        )
    try:
        raw = selected.read_bytes()
    except OSError as exc:
        diagnostic = f"cannot read ledger: {selected}: {exc}"
        return LedgerValidationContextV1(
            selected_ledger_path, (), None,
            LedgerCompatibilityObservationV1("inactive", (), (diagnostic,)),
            (), (), token,
        )
    parse_errors: list[str] = []
    rows = _ledger_h1_runtime_rows(selected_ledger_path, raw, None, item, parse_errors)
    return LedgerValidationContextV1(
        selected_ledger_path, rows, None,
        LedgerCompatibilityObservationV1("inactive", (), tuple(parse_errors)),
        (), (), token,
    )


def _is_link_or_reparse(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except OSError:
        return True
    return stat_module.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _projection_target_identity(
    item: Path,
    selected_ledger: Path,
    errors: list[str],
    *,
    require_ledger: bool = False,
) -> tuple[Path, str] | None:
    """Return the one ordinary active/archive identity admissible for projection."""
    # Do not resolve `item`: resolution would erase an in-tree symlink before
    # the component lstat walk below can reject it.
    lexical_item = Path(item).absolute()
    root = next((parent.parent for parent in lexical_item.parents if parent.name == "work-items"), None)
    if root is None:
        _projection_fail(errors, "identity", "projection target has no repository root")
        return None
    try:
        relative = lexical_item.relative_to(root)
    except ValueError:
        _projection_fail(errors, "identity", "projection target escapes its repository root")
        return None
    parts = relative.parts
    active = len(parts) == 3 and parts[:2] == ("work-items", "active")
    archived = (
        len(parts) == 4
        and parts[:2] == ("work-items", "archive")
        and re.fullmatch(r"\d{4}-\d{2}", parts[2]) is not None
    )
    if not (active or archived) or not all(isinstance(part, str) and part for part in parts):
        _projection_fail(errors, "identity", "projection target must be one active or monthly archived work-item")
        return None
    canonical_ledger = lexical_item / "agent-runs.jsonl"
    transactional_ledger = canonical_ledger.with_suffix(".jsonl.tmp")
    selected_ledger = Path(selected_ledger).absolute()
    if selected_ledger not in {canonical_ledger, transactional_ledger}:
        _projection_fail(errors, "ledger", "candidate ledger path differs from immutable live ledger identity")
        return None
    for index in range(1, len(parts) + 1):
        if _is_link_or_reparse(root.joinpath(*parts[:index])):
            _projection_fail(errors, "identity", "projection target crosses a link or reparse point")
            return None
    # lstat deliberately happens even for a dangling symlink.  Archive readers
    # and writers must reject it before any content read.
    if require_ledger and _is_link_or_reparse(canonical_ledger):
        _projection_fail(errors, "identity", "ledger is missing, linked, or a reparse point")
        return None
    if not require_ledger and canonical_ledger.exists() and _is_link_or_reparse(canonical_ledger):
        _projection_fail(errors, "identity", "ledger is a link or reparse point")
        return None
    if selected_ledger == transactional_ledger and _is_link_or_reparse(transactional_ledger):
        _projection_fail(errors, "identity", "transactional ledger is missing, linked, or a reparse point")
        return None
    return root, relative.as_posix()


def classify_legacy_projection_target(
    item: Path, selected_ledger: Path, errors: list[str], *, require_ledger: bool = False
) -> tuple[Path, str] | None:
    """Public owner seam for no-follow active/archive projection target checks."""
    return _projection_target_identity(item, selected_ledger, errors, require_ledger=require_ledger)


def _projection_json_object(raw: bytes, source: Path | str, errors: list[str]) -> dict | None:
    try:
        decoded = raw.decode("utf-8", errors="strict")
        return decode_json_object(decoded, source=str(source), maximum_bytes=max(len(raw), 1))
    except (UnicodeDecodeError, ValueError) as exc:
        _projection_fail(errors, "manifest", f"{source}: {exc}")
        return None


def _canonical_projection_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _strict_shape(value: object, required: set[str], allowed: set[str], errors: list[str], label: str) -> bool:
    if not isinstance(value, dict):
        _projection_fail(errors, "manifest", f"{label} must be an object")
        return False
    missing = required - set(value)
    unknown = set(value) - allowed
    if missing or unknown:
        _projection_fail(errors, "manifest", f"{label} has invalid fields missing={sorted(missing)} unknown={sorted(unknown)}")
        return False
    return True


def _projection_profile_key(profile_id: object, profile_version: object, errors: list[str], label: str) -> tuple[str, int] | None:
    if not isinstance(profile_id, str) or type(profile_version) is not int:
        _projection_fail(errors, "profile", f"{label} profileId/profileVersion must be string/integer")
        return None
    return profile_id, profile_version


def _profile_projection(profile: tuple[str, int], raws: list[dict], item: Path, entry: dict, errors: list[str]) -> list[dict] | None:
    profile_id, _ = profile
    if profile_id == "canonical-v0-shape":
        if len(raws) != 1:
            _projection_fail(errors, "topology", "canonical-v0-shape requires exactly one raw line")
            return None
        raw = raws[0]
        required = {"runId", "workItem", "role", "executionRole", "status", "gate", "scope", "evidence", "started", "updated"}
        allowed = required | {
            "artifact", "lane", "eventKind", "findingClass", "scratchEvidence", "launchRunId",
        }
        if not _strict_shape(raw, required, allowed, errors, "canonical-v0-shape raw event"):
            return None
        if not isinstance(raw["role"], str):
            _projection_fail(errors, "profile", "canonical-v0-shape role must be a string")
            return None
        role = _LEGACY_ROLE_MAP.get(raw["role"], raw["role"])
        execution_role = _LEGACY_EXECUTION_ROLE_MAP.get(raw["executionRole"])
        if role not in {"lead", "analyst", "qa-engineer", "architect", "planner"} or execution_role is None:
            _projection_fail(errors, "profile", "canonical-v0-shape role mapping is not closed")
            return None
        if not all(isinstance(raw.get(key), str) and raw[key].strip() for key in required):
            _projection_fail(errors, "replacement", "canonical-v0-shape requires non-empty scalar fields")
            return None
        if raw["status"] not in STATUS_VALUES or raw["gate"] not in GATE_VALUES:
            _projection_fail(errors, "profile", "canonical-v0-shape status or gate is unsupported")
            return None
        projected = {
            "schemaVersion": 2, "runId": raw["runId"], "workItem": raw["workItem"], "role": role,
            "executionRole": execution_role, "status": raw["status"], "gate": raw["gate"],
            "scope": [raw["scope"]], "evidence": [{"kind": "manual-check", "ref": raw["evidence"]}],
            "startedAt": raw["started"], "updatedAt": raw["updated"],
        }
        for key in ("artifact", "lane", "eventKind", "findingClass", "scratchEvidence", "launchRunId"):
            if key in raw:
                projected[key] = raw[key]
        return [projected]
    if profile_id == "attempt-pair-v0":
        if len(raws) != 2:
            _projection_fail(errors, "topology", "attempt-pair-v0 requires both raw lines atomically")
            return None
        allowed = {"attemptId", "state", "role", "task", "scope", "evidence", "artifact", "started", "updated"}
        required = {"attemptId", "state", "role", "task", "scope", "evidence", "started", "updated"}
        if any(not _strict_shape(raw, required, allowed, errors, "attempt-pair-v0 raw event") for raw in raws):
            return None
        if raws[0]["attemptId"] != raws[1]["attemptId"] or raws[0]["state"] not in {"pending", "running"} or raws[1]["state"] not in {"completed", "interrupted"}:
            _projection_fail(errors, "topology", "attempt-pair-v0 requires one ordered attempt and exact raw outcome")
            return None
        if not isinstance(raws[0]["role"], str) or not isinstance(raws[1]["role"], str):
            _projection_fail(errors, "profile", "attempt-pair-v0 role must be a string")
            return None
        role = _LEGACY_ROLE_MAP.get(raws[0]["role"], raws[0]["role"])
        if role not in {"lead", "analyst", "qa-engineer", "architect", "planner"} or raws[1]["role"] != raws[0]["role"]:
            _projection_fail(errors, "profile", "attempt-pair-v0 role mapping is not closed")
            return None
        prefix = f"legacy-attempt-{raws[0]['attemptId']}"
        return [
            {"schemaVersion": 2, "runId": f"{prefix}-start", "workItem": item.name, "role": role, "executionRole": "main", "status": "running", "gate": "none", "scope": [raws[0]["scope"]], "evidence": [{"kind": "manual-check", "ref": raws[0]["evidence"]}], "startedAt": raws[0]["started"], "updatedAt": raws[0]["updated"]},
            {"schemaVersion": 2, "runId": f"{prefix}-outcome", "workItem": item.name, "role": role, "executionRole": "main", "status": "completed" if raws[1]["state"] == "completed" else "cancelled", "gate": "none", "scope": [raws[1]["scope"]], "evidence": [{"kind": "manual-check", "ref": raws[1]["evidence"]}], "startedAt": raws[1]["started"], "updatedAt": raws[1]["updated"]},
        ]
    if profile_id == "review-summary-v0":
        if len(raws) != 1:
            _projection_fail(errors, "topology", "review-summary-v0 requires exactly one raw line")
            return None
        raw = raws[0]
        required = {"stage", "role", "task", "artifact", "result", "timestamp"}
        if not _strict_shape(raw, required, required | {"evidence"}, errors, "review-summary-v0 raw event"):
            return None
        if not isinstance(raw["role"], str):
            _projection_fail(errors, "profile", "review-summary-v0 role must be a string")
            return None
        role = _LEGACY_ROLE_MAP.get(raw["role"], raw["role"])
        result = raw["result"]
        if role not in {"qa-engineer", "architect", "analyst"} or result not in {"PASS", "REVISE"}:
            _projection_fail(errors, "profile", "review-summary-v0 role/result mapping is not closed")
            return None
        root = repo_root_for(item)
        try:
            artifact = confine_legacy_projection_path(
                root if root is not None else Path(),
                (item.relative_to(root).as_posix() + "/" + raw["artifact"]) if root is not None and isinstance(raw.get("artifact"), str) else "",
                prefix=("work-items",), leaf_kind="file" if result == "PASS" else None,
                allow_missing_leaf=result == "PASS",
            )
        except (ValueError, TypeError):
            _projection_fail(errors, "identity", "review-summary-v0 artifact is outside the owning work item")
            return None
        if artifact.parent != item and item not in artifact.parents:
            _projection_fail(errors, "identity", "review-summary-v0 artifact is outside the owning work item")
            return None
        artifact_digest = entry.get("artifactSha256")
        if result == "PASS" and (not artifact.is_file() or not isinstance(artifact_digest, str) or digest_file(artifact) != artifact_digest):
            _projection_fail(errors, "digest", "review-summary-v0 PASS requires existing exact artifact digest")
            return None
        return [{"schemaVersion": 2, "runId": f"legacy-review-{hashlib.sha256(raw['task'].encode('utf-8')).hexdigest()[:16]}", "workItem": item.name, "role": role, "executionRole": "main", "status": "completed" if result == "PASS" else "revise", "gate": result, "scope": [raw["stage"]], "evidence": [{"kind": "artifact", "ref": raw["artifact"]}], "artifact": raw["artifact"], "startedAt": raw["timestamp"], "updatedAt": raw["timestamp"]}]
    _projection_fail(errors, "profile", f"unsupported projection profile {profile_id!r}")
    return None


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_manifest_bound_legacy_ledger_projections(
    events: list[dict], raw_metadata: list[dict[str, object]], item: Path,
    selected_ledger: Path, ledger_bytes: bytes,
    manifest_blobs: dict[str, bytes] | None = None,
    registry_bytes: bytes | None = None,
    validated_h1_partition: tuple[
        str, str, str, str, tuple[tuple[int, str], ...]
    ] | None = None,
) -> tuple[list[dict], dict[str, int], list[str]]:
    """Read verified immutable legacy rows through closed shape-only profiles."""
    counters = {"manifest-apply": 0, "manifest-revoke": 0, "manifest-projected": 0}
    errors: list[str] = []
    candidate_input = manifest_blobs is not None or registry_bytes is not None
    if validated_h1_partition is not None and candidate_input:
        fail(
            errors,
            "WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS: validated H1 partition cannot be combined with caller-supplied legacy projection inputs",
        )
        return events, counters, errors
    if not candidate_input and repo_root_for(item) is None:
        return events, counters, errors
    target = _projection_target_identity(item, selected_ledger, errors)
    if target is None:
        return events, counters, errors
    root, relative_item = target
    work_items = root / "work-items"
    manifests = work_items / LEGACY_PROJECTION_MANIFEST_DIR
    registry = work_items / LEGACY_PROJECTION_REGISTRY
    owned_registry_rows: dict[int, str] = {}
    if validated_h1_partition is not None:
        (
            excluded_path,
            excluded_sha256,
            excluded_registry_path,
            excluded_registry_sha256,
            excluded_rows,
        ) = validated_h1_partition
        excluded_parts = PurePosixPath(excluded_path).parts
        if (
            len(excluded_parts) != 3
            or excluded_parts[:2]
            != ("work-items", LEGACY_PROJECTION_MANIFEST_DIR)
            or Path(excluded_parts[2]).name != excluded_parts[2]
            or not excluded_parts[2].endswith(".json")
            or SHA256_RE.fullmatch(excluded_sha256) is None
            or excluded_registry_path
            != f"work-items/{LEGACY_PROJECTION_REGISTRY}"
            or SHA256_RE.fullmatch(excluded_registry_sha256) is None
            or len(excluded_rows) not in {2, 4}
            or any(
                type(ordinal) is not int
                or ordinal < 1
                or SHA256_RE.fullmatch(row_sha256) is None
                for ordinal, row_sha256 in excluded_rows
            )
            or tuple(sorted(excluded_rows)) != excluded_rows
            or len({ordinal for ordinal, _digest in excluded_rows})
            != len(excluded_rows)
        ):
            fail(
                errors,
                "WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS: validated H1 projection partition is unsafe",
            )
            return events, counters, errors
    if candidate_input and (manifest_blobs is None or registry_bytes is None):
        _projection_fail(errors, "manifest", "candidate projection requires both manifest blobs and registry bytes")
        return events, counters, errors
    if not candidate_input:
        try:
            manifests = confine_legacy_projection_path(
                root, f"work-items/{LEGACY_PROJECTION_MANIFEST_DIR}", prefix=("work-items",), allow_missing_leaf=True,
                failure_id="WI-LEDGER-MIGRATION-MANIFEST-INVALID",
            )
            registry = confine_legacy_projection_path(
                root, f"work-items/{LEGACY_PROJECTION_REGISTRY}", prefix=("work-items",), allow_missing_leaf=True,
                failure_id="WI-LEDGER-MIGRATION-COMMIT-INDETERMINATE",
            )
        except ValueError as exc:
            _projection_fail(errors, "identity", f"projection live input is unsafe: {exc}")
            return events, counters, errors
        if not manifests.exists() and not registry.exists():
            return events, counters, errors
        if not manifests.is_dir() or not registry.is_file() or _is_link_or_reparse(manifests) or _is_link_or_reparse(registry):
            _projection_fail(errors, "manifest", "projection manifest directory or registry is missing or unsafe")
            return events, counters, errors
    ledger = root.joinpath(*PurePosixPath(relative_item).parts, "agent-runs.jsonl")
    if candidate_input:
        assert manifest_blobs is not None and registry_bytes is not None
        manifest_inputs: list[tuple[str, bytes, str]] = []
        for name, raw in manifest_blobs.items():
            if not isinstance(name, str) or Path(name).name != name or not name.endswith(".json") or not isinstance(raw, bytes):
                _projection_fail(errors, "manifest", "candidate manifest blobs require safe json filenames and bytes")
                continue
            manifest_inputs.append((name, raw, f"candidate:{name}"))
        registry_lines = registry_bytes.splitlines(keepends=True)
        registry_source = "candidate:legacy-ledger-projections.jsonl"
    else:
        try:
            registry_raw = registry.read_bytes()
            registry_lines = registry_raw.splitlines(keepends=True)
            manifest_inputs = [(path.name, None, str(path)) for path in sorted(manifests.iterdir())]
        except OSError as exc:
            _projection_fail(errors, "manifest", f"cannot read projection input: {exc}")
            return events, counters, errors
        registry_source = str(registry)
        if validated_h1_partition is not None:
            if (
                registry.relative_to(root).as_posix()
                != validated_h1_partition[2]
                or hashlib.sha256(registry_raw).hexdigest()
                != validated_h1_partition[3]
            ):
                fail(
                    errors,
                    "WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS: validated H1 registry snapshot differs",
                )
                return events, counters, errors
            owned_registry_rows = dict(validated_h1_partition[4])
    manifest_by_id: dict[str, tuple[dict, bytes]] = {}
    excluded_matches = 0
    for name, raw, source in manifest_inputs:
        path = manifests / name
        if not candidate_input:
            try:
                path = confine_legacy_projection_path(
                    root, f"work-items/{LEGACY_PROJECTION_MANIFEST_DIR}/{name}",
                    prefix=("work-items", LEGACY_PROJECTION_MANIFEST_DIR), leaf_kind="file",
                    failure_id="WI-LEDGER-MIGRATION-MANIFEST-INVALID",
                )
            except ValueError as exc:
                _projection_fail(errors, "manifest", f"unsafe manifest path {name}: {exc}")
                continue
            if path.suffix != ".json":
                _projection_fail(errors, "manifest", f"unsafe manifest path {name}")
                continue
            raw = path.read_bytes()
        assert isinstance(raw, bytes)
        if validated_h1_partition is not None:
            relative_path = path.relative_to(root).as_posix()
            if (
                relative_path == validated_h1_partition[0]
                and hashlib.sha256(raw).hexdigest() == validated_h1_partition[1]
            ):
                excluded_matches += 1
                continue
        manifest = _projection_json_object(raw, source, errors)
        required = {"schemaVersion", "manifestId", "profiles", "entries"}
        if manifest is None or not _strict_shape(manifest, required, required, errors, f"manifest {name}"):
            continue
        if manifest["schemaVersion"] != 1 or not isinstance(manifest["manifestId"], str) or name != f"{manifest['manifestId']}.json":
            _projection_fail(errors, "manifest", f"manifest identity does not match create-only filename {name}")
            continue
        if manifest["manifestId"] in manifest_by_id:
            _projection_fail(errors, "manifest", f"duplicate manifestId {manifest['manifestId']}")
            continue
        profile_keys: set[tuple[str, int]] = set()
        manifest_valid = isinstance(manifest["profiles"], list) and isinstance(manifest["entries"], list)
        if not manifest_valid:
            _projection_fail(errors, "manifest", f"manifest {name} profiles and entries must be arrays")
            continue
        for profile_row in manifest["profiles"]:
            if not _strict_shape(profile_row, {"profileId", "profileVersion"}, {"profileId", "profileVersion"}, errors, f"manifest {name} profile"):
                manifest_valid = False
                continue
            key = _projection_profile_key(profile_row["profileId"], profile_row["profileVersion"], errors, f"manifest {name}")
            if key is None:
                manifest_valid = False
                continue
            if key not in LEGACY_PROJECTION_PROFILE_REGISTRY:
                _projection_fail(errors, "profile", f"manifest {name} names unsupported profile {key!r}")
                manifest_valid = False
            elif key in profile_keys:
                _projection_fail(errors, "manifest", f"manifest {name} repeats profile {key!r}")
                manifest_valid = False
            profile_keys.add(key)
        entry_ids: set[str] = set()
        entry_required = {"entryId", "profileId", "profileVersion", "workItem", "ledgerPath", "ledgerSha256", "rawLineOrdinals", "rawLineSha256", "projectedEvents", "projectedEventSha256"}
        for entry in manifest["entries"]:
            if not _strict_shape(entry, entry_required, entry_required | {"artifactSha256"}, errors, f"manifest {name} entry"):
                manifest_valid = False
                continue
            entry_key = _projection_profile_key(entry["profileId"], entry["profileVersion"], errors, f"manifest {name} entry")
            entry_id = entry["entryId"]
            if entry_key is None or not isinstance(entry_id, str) or entry_id in entry_ids or entry_key not in profile_keys:
                _projection_fail(errors, "manifest", f"manifest {name} entry identity/profile binding is invalid")
                manifest_valid = False
                continue
            entry_ids.add(entry_id)
        if not manifest_valid:
            continue
        manifest_by_id[manifest["manifestId"]] = (manifest, raw)
    if validated_h1_partition is not None and excluded_matches != 1:
        fail(
            errors,
            "WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS: validated H1 manifest partition did not match exactly once",
        )
        return events, counters, errors
    active: dict[tuple[str, int], tuple[dict, bytes, dict]] = {}
    operation_ids: set[str] = set()
    apply_lines: dict[str, tuple[tuple[str, int], bytes]] = {}
    seen_group_ids: set[str] = set()
    current_group_id: str | None = None
    history_groups: dict[str, list[dict]] = {}
    if any(
        ordinal > len(registry_lines)
        or hashlib.sha256(registry_lines[ordinal - 1]).hexdigest() != row_sha256
        for ordinal, row_sha256 in owned_registry_rows.items()
    ):
        fail(
            errors,
            "WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS: validated H1 registry row partition differs",
        )
        return events, counters, errors
    for ordinal, physical in enumerate(registry_lines, start=1):
        if ordinal in owned_registry_rows:
            continue
        record = _projection_json_object(physical.rstrip(b"\r\n"), f"{registry_source}:{ordinal}", errors)
        required = {"schemaVersion", "operationId", "state", "profileId", "profileVersion", "manifestId", "manifestSha256", "manifestEntryId", "workItem", "ledgerPath", "ledgerSha256", "rawLineOrdinal", "rawLineSha256", "projectedEvent", "projectedEventSha256", "recordedAt"}
        if record is None:
            continue
        version = record.get("schemaVersion")
        if version == 1:
            allowed = required | {"revokeOfOperationId", "revokeOfRecordSha256"}
        elif version == 2:
            required = required | {"operationGroupId", "groupMemberIndex", "groupMemberCount"}
            allowed = required | {"revokeOfOperationId", "revokeOfRecordSha256", "revokeOfOperationGroupId"}
        else:
            _projection_fail(errors, "manifest", f"projection registry line {ordinal} schemaVersion is unsupported")
            continue
        if not _strict_shape(record, required, allowed, errors, f"projection registry line {ordinal}"):
            continue
        record = dict(record)
        if version == 1:
            # Backward-compatible singleton only; a legacy multi-row group was
            # never published and cannot be inferred from a string prefix.
            record.update({"operationGroupId": record["operationId"], "groupMemberIndex": 1, "groupMemberCount": 1})
        elif (
            not isinstance(record["operationGroupId"], str)
            or not isinstance(record["groupMemberIndex"], int)
            or not isinstance(record["groupMemberCount"], int)
            or record["groupMemberIndex"] < 1
            or record["groupMemberIndex"] > record["groupMemberCount"]
        ):
            _projection_fail(errors, "topology", f"projection registry line {ordinal} group metadata is invalid")
            continue
        record["_registryOrdinal"] = ordinal
        group_key = record["operationGroupId"].casefold()
        if current_group_id != group_key:
            if group_key in seen_group_ids:
                _projection_fail(errors, "topology", f"projection group {record['operationGroupId']} is reused in complete history")
                continue
            seen_group_ids.add(group_key)
            current_group_id = group_key
        history_groups.setdefault(group_key, []).append(record)
        if not isinstance(record["operationId"], str) or record["operationId"] in operation_ids:
            _projection_fail(errors, "topology", f"duplicate or invalid operationId at registry line {ordinal}")
            continue
        operation_ids.add(record["operationId"])
        profile = _projection_profile_key(record["profileId"], record["profileVersion"], errors, f"registry line {ordinal}")
        if profile is None or profile not in LEGACY_PROJECTION_PROFILE_REGISTRY:
            _projection_fail(errors, "profile", f"registry line {ordinal} names unsupported profile")
            continue
        if not isinstance(record["manifestId"], str):
            _projection_fail(errors, "manifest", f"registry line {ordinal} manifestId must be a string")
            continue
        manifest_pair = manifest_by_id.get(record["manifestId"])
        if manifest_pair is None or record["manifestSha256"] != hashlib.sha256(manifest_pair[1]).hexdigest():
            _projection_fail(errors, "manifest", f"registry line {ordinal} manifest digest mismatch")
            continue
        manifest, _ = manifest_pair
        entries = [entry for entry in manifest.get("entries", []) if isinstance(entry, dict) and entry.get("entryId") == record["manifestEntryId"]]
        if len(entries) != 1:
            _projection_fail(errors, "identity", f"registry line {ordinal} does not bind one manifest entry")
            continue
        entry = entries[0]
        entry_required = {"entryId", "profileId", "profileVersion", "workItem", "ledgerPath", "ledgerSha256", "rawLineOrdinals", "rawLineSha256", "projectedEvents", "projectedEventSha256"}
        if not _strict_shape(entry, entry_required, entry_required | {"artifactSha256"}, errors, f"manifest entry {record['manifestEntryId']}"):
            continue
        if any(record.get(key) != entry.get(key) for key in ("profileId", "profileVersion", "workItem", "ledgerPath", "ledgerSha256")):
            _projection_fail(errors, "identity", f"registry line {ordinal} differs from manifest target")
            continue
        profile_rows = [
            row for row in manifest.get("profiles", [])
            if isinstance(row, dict) and row == {"profileId": entry["profileId"], "profileVersion": entry["profileVersion"]}
        ]
        if len(profile_rows) != 1:
            _projection_fail(errors, "profile", f"manifest entry {entry['entryId']} does not bind one closed profile")
            continue
        if record["workItem"] != item.relative_to(root).as_posix() or record["ledgerPath"] != ledger.relative_to(root).as_posix():
            continue
        if record["ledgerSha256"] != hashlib.sha256(ledger_bytes).hexdigest():
            _projection_fail(errors, "ledger", f"registry line {ordinal} ledger digest drift")
            raw_ordinal = record.get("rawLineOrdinal")
            raw_lines = ledger_bytes.splitlines(keepends=True)
            if not isinstance(raw_ordinal, int) or raw_ordinal < 1 or raw_ordinal > len(raw_lines) or hashlib.sha256(raw_lines[raw_ordinal - 1]).hexdigest() != record.get("rawLineSha256"):
                _projection_fail(errors, "digest", f"registry line {ordinal} raw physical line digest drift")
            continue
        raw_ordinals = entry["rawLineOrdinals"]
        raw_digests = entry["rawLineSha256"]
        projected_events = entry["projectedEvents"]
        projected_digests = entry["projectedEventSha256"]
        if not all(isinstance(value, list) for value in (raw_ordinals, raw_digests, projected_events, projected_digests)) or not (len(raw_ordinals) == len(raw_digests) == len(projected_events) == len(projected_digests)):
            _projection_fail(errors, "manifest", f"manifest entry {entry['entryId']} has non-parallel bindings")
            continue
        if (
            not raw_ordinals
            or any(type(value) is not int or value < 1 for value in raw_ordinals)
            or len(set(raw_ordinals)) != len(raw_ordinals)
            or any(not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None for value in (*raw_digests, *projected_digests))
            or any(not isinstance(value, dict) for value in projected_events)
        ):
            _projection_fail(errors, "manifest", f"manifest entry {entry['entryId']} bindings are not one unique typed set")
            continue
        if version == 1 and len(raw_ordinals) != 1:
            _projection_fail(errors, "topology", f"legacy v1 projection line {ordinal} cannot infer multi-row membership")
            continue
        if version == 2:
            expected_ids = [
                record["operationGroupId"] if len(raw_ordinals) == 1 else "m:" + hashlib.sha256(
                    json.dumps([record["operationGroupId"], index, len(raw_ordinals)], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                ).hexdigest()
                for index in range(1, len(raw_ordinals) + 1)
            ]
            member_index = record["groupMemberIndex"] - 1
            if (
                record["groupMemberCount"] != len(raw_ordinals)
                or record["operationId"] != expected_ids[member_index]
            ):
                _projection_fail(errors, "topology", f"projection registry line {ordinal} group member identity differs")
                continue
        try:
            raw_index = raw_ordinals.index(record["rawLineOrdinal"])
        except ValueError:
            _projection_fail(errors, "identity", f"registry line {ordinal} raw ordinal is not manifest-bound")
            continue
        if raw_index >= len(raw_digests) or raw_index >= len(projected_events) or raw_index >= len(projected_digests) or record["rawLineSha256"] != raw_digests[raw_index] or record["projectedEvent"] != projected_events[raw_index] or record["projectedEventSha256"] != projected_digests[raw_index] or hashlib.sha256(_canonical_projection_bytes(record["projectedEvent"])).hexdigest() != record["projectedEventSha256"]:
            _projection_fail(errors, "digest", f"registry line {ordinal} target or projected digest mismatch")
            continue
        if record["state"] == "revoke":
            target = record.get("revokeOfOperationId")
            applied = apply_lines.get(target) if isinstance(target, str) else None
            raw_key = (record["ledgerPath"], record["rawLineOrdinal"])
            active_row = active.get(raw_key)
            if applied is None or active_row is None or record.get("revokeOfRecordSha256") != hashlib.sha256(applied[1]).hexdigest() or applied[0] != raw_key or active_row[0].get("operationId") != target:
                _projection_fail(errors, "topology", f"registry line {ordinal} revoke is not bound to its exact apply line")
                continue
            if version == 2 and record.get("revokeOfOperationGroupId") != active_row[0].get("operationGroupId"):
                _projection_fail(errors, "topology", f"registry line {ordinal} revoke group does not bind its apply group")
                continue
            active.pop(raw_key)
            counters["manifest-revoke"] += 1
            continue
        if record["state"] != "apply":
            _projection_fail(errors, "manifest", f"registry line {ordinal} has invalid apply/revoke state")
            continue
        raw_key = (record["ledgerPath"], record["rawLineOrdinal"])
        if raw_key in active:
            _projection_fail(errors, "topology", f"registry line {ordinal} creates more than one active projection for a raw line")
            continue
        active[raw_key] = (record, physical, entry)
        apply_lines[record["operationId"]] = (raw_key, physical)
        counters["manifest-apply"] += 1
    for group_key, members in history_groups.items():
        first = members[0]
        count = first["groupMemberCount"]
        if (
            len(members) != count
            or [member["groupMemberIndex"] for member in members] != list(range(1, count + 1))
            or [member["_registryOrdinal"] for member in members] != list(range(members[0]["_registryOrdinal"], members[0]["_registryOrdinal"] + count))
            or any(
                member["state"] != first["state"]
                or member["manifestId"] != first["manifestId"]
                or member["manifestEntryId"] != first["manifestEntryId"]
                or member["groupMemberCount"] != count
                for member in members
            )
        ):
            _projection_fail(errors, "topology", f"projection group {first['operationGroupId']} is not one complete ordered historical group")
            continue
        if first["state"] == "revoke" and (
            any(member.get("revokeOfOperationGroupId") != first.get("revokeOfOperationGroupId") for member in members)
            or any(member.get("revokeOfOperationId") is None for member in members)
        ):
            _projection_fail(errors, "topology", f"projection revoke group {first['operationGroupId']} has inconsistent apply binding")
    lines = ledger_bytes.splitlines(keepends=True)
    replacement_by_line: dict[int, dict] = {}
    entries_active: dict[tuple[str, str], list[tuple[dict, dict]]] = {}
    for (_, raw_ordinal), (record, _, entry) in active.items():
        entries_active.setdefault((record["manifestId"], record["manifestEntryId"]), []).append((record, entry))
        if not isinstance(raw_ordinal, int) or raw_ordinal < 1 or raw_ordinal > len(lines):
            _projection_fail(errors, "identity", "active projection raw ordinal is outside ledger")
            continue
        if hashlib.sha256(lines[raw_ordinal - 1]).hexdigest() != record["rawLineSha256"]:
            _projection_fail(errors, "digest", f"raw physical line digest drift at ordinal {raw_ordinal}")
    groups_active: dict[str, list[tuple[dict, dict]]] = {}
    for bindings in entries_active.values():
        for binding in bindings:
            groups_active.setdefault(binding[0]["operationGroupId"], []).append(binding)
    for group_id, bindings in groups_active.items():
        first_record, first_entry = bindings[0]
        count = first_record["groupMemberCount"]
        if (
            len(bindings) != count
            or {record["groupMemberIndex"] for record, _entry in bindings} != set(range(1, count + 1))
            or sorted(record["_registryOrdinal"] for record, _entry in bindings) != list(range(min(record["_registryOrdinal"] for record, _entry in bindings), min(record["_registryOrdinal"] for record, _entry in bindings) + count))
            or any(
                record["state"] != first_record["state"]
                or record["manifestId"] != first_record["manifestId"]
                or record["manifestEntryId"] != first_record["manifestEntryId"]
                or record["groupMemberCount"] != count
                for record, _entry in bindings
            )
        ):
            _projection_fail(errors, "topology", f"projection group {group_id} is partial or inconsistent")
            continue
        ordered = sorted(bindings, key=lambda pair: pair[0]["groupMemberIndex"])
        if [record["rawLineOrdinal"] for record, _entry in ordered] != first_entry["rawLineOrdinals"]:
            _projection_fail(errors, "topology", f"projection group {group_id} ordinal order differs from its manifest entry")
    for (_, entry_id), bindings in entries_active.items():
        entry = bindings[0][1]
        if len(bindings) != len(entry["rawLineOrdinals"]):
            _projection_fail(errors, "topology", f"manifest entry {entry_id} is only partially active")
            continue
        raws: list[dict] = []
        for raw_ordinal in entry["rawLineOrdinals"]:
            try:
                raw_event = _projection_json_object(lines[raw_ordinal - 1].rstrip(b"\r\n"), f"{ledger}:{raw_ordinal}", errors)
            except IndexError:
                raw_event = None
            if raw_event is None:
                _projection_fail(errors, "identity", f"manifest entry {entry_id} raw line is unavailable")
                break
            raws.append(raw_event)
        if len(raws) != len(entry["rawLineOrdinals"]):
            continue
        profile = _projection_profile_key(entry["profileId"], entry["profileVersion"], errors, f"manifest entry {entry_id}")
        if profile is None:
            continue
        calculated = _profile_projection(profile, raws, item, entry, errors)
        if calculated is None or calculated != entry["projectedEvents"]:
            _projection_fail(errors, "replacement", f"manifest entry {entry_id} projected event is not deterministic")
            continue
        if any(
            "closesRunIds" in event
            or event.get("gate") == "PASS" and raw.get("gate") == "REVISE"
            or event.get("eventKind") == "terminal" and raw.get("eventKind") != "terminal"
            for event, raw in zip(calculated, raws)
        ):
            _projection_fail(errors, "settlement", f"manifest entry {entry_id} crosses the settlement boundary")
            continue
        for raw_ordinal, projected in zip(entry["rawLineOrdinals"], calculated):
            replacement_by_line[raw_ordinal] = projected
            counters["manifest-projected"] += 1
    effective = [
        replacement_by_line.get(metadata.get("line"), event)
        for event, metadata in zip(events, raw_metadata)
    ]
    return effective, counters, errors


def _project_manifest_rows(
    rows: tuple[LedgerProjectionRowV1, ...],
    item: Path,
    selected_ledger: Path,
    ledger_bytes: bytes,
    *,
    manifest_blobs: dict[str, bytes] | None = None,
    registry_bytes: bytes | None = None,
    validated_h1_partition: tuple[
        str, str, str, str, tuple[tuple[int, str], ...]
    ] | None = None,
) -> tuple[tuple[LedgerProjectionRowV1, ...], dict[str, int], list[str]]:
    """Apply the existing manifest owner while retaining physical row identity."""
    events = _row_events(rows)
    projected, counters, errors = project_manifest_bound_legacy_ledger_projections(
        events, _row_metadata(rows), item, selected_ledger, ledger_bytes,
        manifest_blobs=manifest_blobs,
        registry_bytes=registry_bytes,
        validated_h1_partition=validated_h1_partition,
    )
    if len(projected) != len(rows):
        _projection_fail(errors, "identity", "manifest projection changed ledger cardinality")
        return rows, counters, errors
    return (
        tuple(
            row if event is row.event else LedgerProjectionRowV1(
                copy.deepcopy(event), row.raw_line_ordinal, row.raw_line_sha256,
                row.raw_event_sha256, "manifest-projected",
            )
            for row, event in zip(rows, projected)
        ),
        counters,
        errors,
    )


def validate_manifest_bound_irrecoverable_disposition(
    disposition: object, archive_identity: str, archive_item: Path
) -> list[str]:
    """Validate a read-only exact archived-artifact disposition; never applies one."""
    errors: list[str] = []
    required = {"schemaVersion", "archiveIdentity", "workItem", "missingPath", "disposition", "expectedDigest", "searchReceipt", "survivingArtifacts", "approvedBy", "approvedAt"}
    if not _strict_shape(disposition, required, required, errors, "irrecoverable disposition"):
        return errors
    assert isinstance(disposition, dict)
    if not isinstance(archive_identity, str) or not archive_identity.strip() or disposition["schemaVersion"] != 1 or disposition["archiveIdentity"] != archive_identity or disposition["disposition"] != "irrecoverable" or disposition["expectedDigest"] != "unknown":
        _projection_fail(errors, "manifest", "irrecoverable disposition must bind exact archive identity and unknown digest")
    if not isinstance(disposition["missingPath"], str) or not disposition["missingPath"].strip() or "*" in disposition["missingPath"] or not _safe_repo_relative(disposition["missingPath"]):
        _projection_fail(errors, "manifest", "irrecoverable disposition requires one exact missing path")
    if not isinstance(disposition["workItem"], str) or not disposition["workItem"].startswith("work-items/archive/"):
        _projection_fail(errors, "manifest", "irrecoverable disposition requires an exact archived work-item")
    else:
        root = repo_root_for(archive_item)
        expected = archive_item.relative_to(root).as_posix() if root is not None else None
        try:
            confined_archive = confine_legacy_projection_path(
                root if root is not None else Path(), disposition["workItem"], prefix=("work-items", "archive"), leaf_kind="directory"
            )
        except ValueError:
            confined_archive = None
        if expected != disposition["workItem"] or confined_archive != archive_item or "archive" not in archive_item.parts:
            _projection_fail(errors, "identity", "irrecoverable disposition work-item does not bind the observed archive")
    try:
        missing = confine_legacy_projection_path(
            root if 'root' in locals() and root is not None else Path(),
            (archive_item.relative_to(root).as_posix() + "/" + disposition["missingPath"]) if 'root' in locals() and root is not None and isinstance(disposition["missingPath"], str) else "",
            prefix=("work-items", "archive"), allow_missing_leaf=True,
        )
    except (ValueError, TypeError):
        missing = None
        _projection_fail(errors, "identity", "irrecoverable disposition missing path is unsafe")
    if missing is not None and missing.exists():
        _projection_fail(errors, "identity", "irrecoverable disposition missing path exists in observed archive")
    if not isinstance(disposition["searchReceipt"], str) or not disposition["searchReceipt"].strip() or not isinstance(disposition["approvedBy"], str) or not disposition["approvedBy"].strip() or not isinstance(disposition["approvedAt"], str) or _STRICT_UTC_RE.fullmatch(disposition["approvedAt"]) is None:
        _projection_fail(errors, "manifest", "irrecoverable disposition requires audit evidence and strict approval timestamp")
    artifacts = disposition["survivingArtifacts"]
    if not isinstance(artifacts, list) or not artifacts or any(not isinstance(row, dict) or set(row) != {"path", "sha256"} or not isinstance(row["path"], str) or not _safe_repo_relative(row["path"]) or not isinstance(row["sha256"], str) or SHA256_RE.fullmatch(row["sha256"]) is None for row in artifacts):
        _projection_fail(errors, "manifest", "irrecoverable disposition requires exact canonical surviving artifacts")
    elif all(isinstance(row, dict) and isinstance(row.get("path"), str) and isinstance(row.get("sha256"), str) for row in artifacts):
        for row in artifacts:
            try:
                path = confine_legacy_projection_path(
                    root if 'root' in locals() and root is not None else Path(),
                    (archive_item.relative_to(root).as_posix() + "/" + row["path"]) if 'root' in locals() and root is not None else "",
                    prefix=("work-items", "archive"), leaf_kind="file",
                )
            except ValueError:
                _projection_fail(errors, "identity", f"irrecoverable disposition surviving artifact is unsafe: {row['path']}")
                continue
            if digest_file(path) != row["sha256"]:
                _projection_fail(errors, "digest", f"irrecoverable disposition surviving artifact is not exact: {row['path']}")
    return errors


def archived_ledger_identity(work_item: str, ledger_sha256: str) -> str:
    """Portable archive identity: only immutable repository-relative facts enter it."""
    return hashlib.sha256(
        b"orchestrarium-archive-v1\0"
        + work_item.encode("utf-8")
        + b"\0"
        + ledger_sha256.encode("ascii")
    ).hexdigest()


def obligation_transfer_id(
    archive_identity: str,
    raw_line_ordinal: int,
    raw_line_sha256: str,
    raw_event_sha256: str,
    run_id: str,
) -> str:
    return hashlib.sha256(
        b"orchestrarium-obligation-v1\0"
        + archive_identity.encode("ascii") + b"\0"
        + str(raw_line_ordinal).encode("ascii") + b"\0"
        + raw_line_sha256.encode("ascii") + b"\0"
        + raw_event_sha256.encode("ascii") + b"\0"
        + run_id.encode("utf-8")
    ).hexdigest()


def _transfer_status_relation(item: Path, errors: list[str]) -> tuple[str, str] | None:
    status = item if item.is_file() else item / "status.md"
    if not status.is_file():
        return None
    try:
        text = status.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeError) as exc:
        fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: transfer status is unreadable: {exc}")
        return None
    values: dict[str, list[str]] = {"continues": [], "obligation-transfer": []}
    for line in text.splitlines():
        match = re.fullmatch(r"\s*([A-Za-z][A-Za-z0-9 _-]*)\s*:\s*(.*?)\s*", line)
        if match and match.group(1).strip().casefold() in values:
            values[match.group(1).strip().casefold()].append(match.group(2).strip())
    if not any(values.values()):
        return None
    if any(len(values[name]) != 1 or not values[name][0] for name in values):
        fail(errors, "WI-OBLIGATION-TRANSFER-OWNER: transfer status relation is missing or duplicated")
        return None
    return values["continues"][0], values["obligation-transfer"][0]


def _transfer_receipt_candidates(root: Path, errors: list[str]) -> tuple[Path, ...]:
    archive_root = root / "work-items" / "archive"
    if not os.path.lexists(archive_root):
        return ()
    if _is_link_or_reparse(archive_root) or not archive_root.is_dir():
        fail(
            errors,
            "WI-OBLIGATION-TRANSFER-OWNER: transfer archive root is unavailable, linked, or a reparse point",
        )
        return ()

    def children(directory: Path) -> tuple[Path, ...]:
        try:
            return tuple(sorted(directory.iterdir(), key=lambda item: item.name.encode("utf-8")))
        except OSError as exc:
            fail(
                errors,
                f"WI-OBLIGATION-TRANSFER-OWNER: transfer archive component is unreadable: {exc}",
            )
            return ()

    candidates: list[Path] = []
    for month in children(archive_root):
        if _is_link_or_reparse(month):
            fail(
                errors,
                "WI-OBLIGATION-TRANSFER-OWNER: transfer archive component is a link or reparse point",
            )
            continue
        if not month.is_dir():
            continue
        for item in children(month):
            if _is_link_or_reparse(item):
                fail(
                    errors,
                    "WI-OBLIGATION-TRANSFER-OWNER: transfer archive component is a link or reparse point",
                )
                continue
            if not item.is_dir():
                continue
            receipt = item / "lifecycle-transition-receipt.json"
            if os.path.lexists(receipt):
                candidates.append(receipt)
    return tuple(candidates)


def _transfer_authority_metadata(root: Path, path: Path) -> os.stat_result:
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("transfer authority path escapes repository") from exc
    confined = confine_legacy_projection_path(
        root,
        relative,
        prefix=("work-items", "archive"),
        leaf_kind="file",
        failure_id="WI-OBLIGATION-TRANSFER-OWNER",
    )
    return os.lstat(confined)


def _transfer_stat_key(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        getattr(metadata, "st_mtime_ns", int(metadata.st_mtime * 1_000_000_000)),
    )


def _read_transfer_authority_bytes(
    root: Path, path: Path, *, maximum_bytes: int | None = None
) -> bytes:
    before = _transfer_authority_metadata(root, path)
    if maximum_bytes is not None and before.st_size > maximum_bytes:
        raise ValueError(
            f"JSON exceeds maximum raw UTF-8 length {maximum_bytes} bytes"
        )
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if _transfer_stat_key(opened) != _transfer_stat_key(before):
            raise ValueError("transfer authority descriptor identity differs")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            raw = stream.read(maximum_bytes + 1 if maximum_bytes is not None else -1)
            after = os.fstat(stream.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if maximum_bytes is not None and len(raw) > maximum_bytes:
        raise ValueError(
            f"JSON exceeds maximum raw UTF-8 length {maximum_bytes} bytes"
        )
    path_after = _transfer_authority_metadata(root, path)
    if (
        len(raw) != before.st_size
        or _transfer_stat_key(after) != _transfer_stat_key(before)
        or _transfer_stat_key(path_after) != _transfer_stat_key(before)
    ):
        raise ValueError("transfer authority changed during read")
    return raw


def _transfer_receipts(
    root: Path, errors: list[str]
) -> dict[str, tuple[Path, dict, Path]]:
    receipts: dict[str, tuple[Path, dict, Path]] = {}
    for path in _transfer_receipt_candidates(root, errors):
        try:
            payload = decode_json_object(
                _read_transfer_authority_bytes(
                    root, path, maximum_bytes=MAX_TRANSFER_RECEIPT_BYTES
                ),
                source=str(path),
                maximum_bytes=MAX_TRANSFER_RECEIPT_BYTES,
            )
        except (OSError, ValueError) as exc:
            fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: transfer receipt is unreadable: {exc}")
            continue
        if payload.get("schemaVersion") != 2 or payload.get("owner") != "mutate-work-item:archive-with-successor-v2":
            continue
        operation_id = payload.get("operationId")
        if not isinstance(operation_id, str) or not operation_id or operation_id in receipts:
            fail(errors, "WI-OBLIGATION-TRANSFER-OWNER: transfer operation identity is duplicate or invalid")
            continue
        obligations = payload.get("obligations")
        if not isinstance(obligations, list):
            fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: transfer receipt {operation_id} has no obligation rows")
            continue
        archive_path = payload.get("archivePath")
        ledger_sha256 = payload.get("ledgerSha256")
        archive = path.parent
        try:
            physical_archive_path = archive.relative_to(root).as_posix()
        except ValueError:
            fail(
                errors,
                f"WI-OBLIGATION-TRANSFER-OWNER: receipt location escapes repository: {operation_id}",
            )
            continue
        if not isinstance(archive_path, str) or archive_path != physical_archive_path:
            fail(
                errors,
                f"WI-OBLIGATION-TRANSFER-OWNER: receipt location differs: {operation_id}",
            )
            continue
        if (
            not isinstance(ledger_sha256, str)
            or SHA256_RE.fullmatch(ledger_sha256) is None
            or payload.get("archiveIdentity")
            != archived_ledger_identity(physical_archive_path, ledger_sha256)
        ):
            fail(errors, f"WI-OBLIGATION-TRANSFER-DRIFT: transfer receipt {operation_id} archive identity differs")
            continue
        ledger = archive / "agent-runs.jsonl"
        try:
            physical_ledger_sha = hashlib.sha256(
                _read_transfer_authority_bytes(root, ledger)
            ).hexdigest()
        except (OSError, ValueError) as exc:
            fail(errors, f"WI-OBLIGATION-TRANSFER-DRIFT: transfer ledger is unavailable: {exc}")
            continue
        if physical_ledger_sha != ledger_sha256:
            fail(errors, f"WI-OBLIGATION-TRANSFER-DRIFT: transfer ledger digest differs: {operation_id}")
            continue
        receipts[operation_id] = (path, payload, archive)
    return receipts

def validate_transfer_receipt_obligation_coverage(
    root: Path,
    receipt: Mapping[str, object],
    archive: Path,
) -> list[str]:
    """Bind one settled transfer receipt to the archive's canonical open state."""

    errors: list[str] = []
    states: list[WorkItemObligationStateV1] = []
    source_errors = validate_work_item(
        archive,
        strict_revise=False,
        validate_status_file=False,
        obligation_state_out=states,
    )
    if source_errors or len(states) != 1:
        errors.extend(source_errors)
        fail(
            errors,
            "WI-OBLIGATION-TRANSFER-OWNER: source obligation state is invalid",
        )
        return errors
    if states[0].open_launches:
        fail(
            errors,
            "WI-OBLIGATION-TRANSFER-COVERAGE: settled transfer source has open launches",
        )
        return errors

    obligations = receipt.get("obligations")
    archive_identity = receipt.get("archiveIdentity")
    if (
        not isinstance(obligations, list)
        or not isinstance(archive_identity, str)
        or SHA256_RE.fullmatch(archive_identity) is None
    ):
        fail(
            errors,
            "WI-OBLIGATION-TRANSFER-COVERAGE: settled transfer receipt obligation shape differs",
        )
        return errors

    row_fields = {
        "runId",
        "rawLineOrdinal",
        "rawLineSha256",
        "rawEventSha256",
        "projectedEventSha256",
        "obligationId",
        "predecessorOperationId",
    }
    declared: dict[tuple[str, int], tuple[object, ...]] = {}
    for row in obligations:
        if (
            not isinstance(row, dict)
            or set(row) != row_fields
            or not isinstance(row.get("runId"), str)
            or type(row.get("rawLineOrdinal")) is not int
            or row["rawLineOrdinal"] < 1
        ):
            fail(
                errors,
                "WI-OBLIGATION-TRANSFER-COVERAGE: settled transfer receipt obligation row differs",
            )
            return errors
        position = (row["runId"], row["rawLineOrdinal"])
        if position in declared:
            fail(
                errors,
                "WI-OBLIGATION-TRANSFER-COVERAGE: settled transfer receipt obligation position is duplicate",
            )
            return errors
        declared[position] = (
            row.get("rawLineSha256"),
            row.get("rawEventSha256"),
            row.get("projectedEventSha256"),
            row.get("obligationId"),
            row.get("predecessorOperationId"),
        )

    expected: dict[tuple[str, int], tuple[object, ...]] = {}
    for row in states[0].open_revise:
        position = (row.run_id, row.raw_line_ordinal)
        obligation_id = row.obligation_id
        if obligation_id is None:
            obligation_id = obligation_transfer_id(
                archive_identity,
                row.raw_line_ordinal,
                row.raw_line_sha256,
                row.raw_event_sha256,
                row.run_id,
            )
        expected[position] = (
            row.raw_line_sha256,
            row.raw_event_sha256,
            row.projected_event_sha256,
            obligation_id,
            row.predecessor_operation_id,
        )

    if set(declared) != set(expected) or len(expected) != len(states[0].open_revise):
        fail(
            errors,
            "WI-OBLIGATION-TRANSFER-COVERAGE: settled transfer receipt does not exactly cover archived open REVISE rows",
        )
    elif declared != expected:
        fail(
            errors,
            "WI-OBLIGATION-TRANSFER-DRIFT: settled transfer receipt obligation bindings differ",
        )
    return errors


def _resolve_transferred_obligation(
    root: Path,
    receipts: Mapping[str, tuple[Path, dict, Path]],
    operation_id: str,
    obligation: dict,
    errors: list[str],
    visiting: frozenset[str],
) -> LedgerProjectionRowV1 | None:
    if operation_id in visiting:
        fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: transfer cycle at {operation_id}")
        return None
    receipt_entry = receipts.get(operation_id)
    if receipt_entry is None:
        fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: transfer receipt is absent: {operation_id}")
        return None
    _path, receipt, archive = receipt_entry
    predecessor = obligation.get("predecessorOperationId")
    obligation_id = obligation.get("obligationId")
    if predecessor is not None:
        if not isinstance(predecessor, str):
            fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: predecessor operation is invalid: {operation_id}")
            return None
        predecessor_entry = receipts.get(predecessor)
        if predecessor_entry is None:
            fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: predecessor receipt is absent: {predecessor}")
            return None
        predecessor_receipt = predecessor_entry[1]
        if predecessor_receipt.get("requestSuccessorSlug") != receipt.get("workItem"):
            fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: predecessor does not own source: {operation_id}")
            return None
        matches = [
            row for row in predecessor_receipt.get("obligations", [])
            if isinstance(row, dict) and row.get("obligationId") == obligation_id
        ]
        if len(matches) != 1:
            fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: predecessor obligation is absent or duplicate: {operation_id}")
            return None
        inherited = _resolve_transferred_obligation(
            root, receipts, predecessor, matches[0], errors, visiting | {operation_id}
        )
        if inherited is None:
            return None
        binding = (
            inherited.event.get("runId"), inherited.raw_line_ordinal,
            inherited.raw_line_sha256, inherited.raw_event_sha256,
            hashlib.sha256(_canonical_projection_bytes(inherited.event)).hexdigest(),
        )
        declared = (
            obligation.get("runId"), obligation.get("rawLineOrdinal"),
            obligation.get("rawLineSha256"), obligation.get("rawEventSha256"),
            obligation.get("projectedEventSha256"),
        )
        if declared != binding:
            fail(errors, f"WI-OBLIGATION-TRANSFER-DRIFT: inherited obligation binding differs: {operation_id}")
            return None
        return LedgerProjectionRowV1(
            dict(inherited.event), inherited.raw_line_ordinal, inherited.raw_line_sha256,
            inherited.raw_event_sha256, "transferred", obligation_id, predecessor,
        )

    states: list[WorkItemObligationStateV1] = []
    validation_errors = validate_work_item(
        archive,
        strict_revise=False,
        validate_status_file=False,
        obligation_state_out=states,
    )
    if validation_errors or len(states) != 1:
        errors.extend(validation_errors)
        fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: source obligation state is invalid: {operation_id}")
        return None
    declared_binding = (
        obligation.get("runId"), obligation.get("rawLineOrdinal"),
        obligation.get("rawLineSha256"), obligation.get("rawEventSha256"),
        obligation.get("projectedEventSha256"),
    )
    matches = [
        row for row in states[0].open_revise
        if (
            row.run_id, row.raw_line_ordinal, row.raw_line_sha256,
            row.raw_event_sha256, row.projected_event_sha256,
        ) == declared_binding
    ]
    if len(matches) != 1:
        fail(errors, f"WI-OBLIGATION-TRANSFER-DRIFT: source obligation binding differs: {operation_id}")
        return None
    row = matches[0]
    expected_id = obligation_transfer_id(
        receipt["archiveIdentity"], row.raw_line_ordinal, row.raw_line_sha256,
        row.raw_event_sha256, row.run_id,
    )
    if obligation_id != expected_id:
        fail(errors, f"WI-OBLIGATION-TRANSFER-DRIFT: obligation identity differs: {operation_id}")
        return None
    return LedgerProjectionRowV1(
        dict(row.event), row.raw_line_ordinal, row.raw_line_sha256,
        row.raw_event_sha256, "transferred", obligation_id, None,
    )


def _inherited_transfer_rows(item: Path, errors: list[str]) -> tuple[LedgerProjectionRowV1, ...]:
    relation = _transfer_status_relation(item, errors)
    if relation is None:
        return ()
    root = repo_root_for(item)
    if root is None:
        fail(errors, "WI-OBLIGATION-TRANSFER-OWNER: successor has no repository root")
        return ()
    source_slug, operation_id = relation
    receipts = _transfer_receipts(root, errors)
    entry = receipts.get(operation_id)
    if entry is None:
        fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: successor receipt is absent: {operation_id}")
        return ()
    receipt = entry[1]
    successor_slug = receipt.get("requestSuccessorSlug")
    item_matches_successor = (
        successor_slug == item.name
        or (
            isinstance(successor_slug, str)
            and item.parent.name == "active"
            and item.name.startswith(f".{successor_slug}.")
        )
    )
    if receipt.get("workItem") != source_slug or not item_matches_successor:
        fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: successor relation differs: {operation_id}")
        return ()
    result: list[LedgerProjectionRowV1] = []
    seen_ids: set[str] = set()
    seen_run_ids: set[str] = set()
    for obligation in receipt["obligations"]:
        if not isinstance(obligation, dict):
            fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: obligation row is invalid: {operation_id}")
            continue
        obligation_id = obligation.get("obligationId")
        run_id = obligation.get("runId")
        if (
            not isinstance(obligation_id, str)
            or not isinstance(run_id, str)
            or obligation_id in seen_ids
            or run_id in seen_run_ids
        ):
            fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: duplicate obligation owner: {operation_id}")
            continue
        seen_ids.add(obligation_id)
        seen_run_ids.add(run_id)
        resolved = _resolve_transferred_obligation(
            root, receipts, operation_id, obligation, errors, frozenset()
        )
        if resolved is not None:
            result.append(LedgerProjectionRowV1(
                dict(resolved.event),
                resolved.raw_line_ordinal,
                resolved.raw_line_sha256,
                resolved.raw_event_sha256,
                "transferred",
                resolved.obligation_id,
                operation_id,
            ))
    return tuple(result)


def validate_obligation_transfer_ownership(root: Path) -> list[str]:
    """Audit every transferred obligation as one non-branching ownership chain."""

    root = Path(root).resolve()
    errors: list[str] = []
    receipts = _transfer_receipts(root, errors)
    rows_by_operation: dict[str, dict[str, dict]] = {}
    children: dict[tuple[str, str], list[str]] = {}
    origins: dict[str, list[str]] = {}
    for operation_id, (_receipt_path, receipt, archive) in receipts.items():
        errors.extend(
            validate_transfer_receipt_obligation_coverage(root, receipt, archive)
        )
        operation_rows: dict[str, dict] = {}
        for row in receipt.get("obligations", []):
            if not isinstance(row, dict):
                fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: invalid obligation row: {operation_id}")
                continue
            obligation_id = row.get("obligationId")
            predecessor = row.get("predecessorOperationId")
            if not isinstance(obligation_id, str) or obligation_id in operation_rows:
                fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: duplicate obligation identity: {operation_id}")
                continue
            operation_rows[obligation_id] = row
            if predecessor is None:
                origins.setdefault(obligation_id, []).append(operation_id)
            elif isinstance(predecessor, str):
                children.setdefault((predecessor, obligation_id), []).append(operation_id)
            else:
                fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: invalid predecessor: {operation_id}")
        rows_by_operation[operation_id] = operation_rows

    for operation_id, operation_rows in rows_by_operation.items():
        for obligation_id, row in operation_rows.items():
            cursor = operation_id
            current = row
            visited: set[str] = set()
            while current.get("predecessorOperationId") is not None:
                if cursor in visited:
                    fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: obligation ownership cycle: {obligation_id}")
                    break
                visited.add(cursor)
                predecessor = current.get("predecessorOperationId")
                if not isinstance(predecessor, str):
                    break
                prior = rows_by_operation.get(predecessor, {}).get(obligation_id)
                if prior is None:
                    break
                cursor = predecessor
                current = prior

    for obligation_id, origin_operations in origins.items():
        if len(origin_operations) != 1:
            fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: obligation has multiple origins: {obligation_id}")
            continue
        operation_id = origin_operations[0]
        visited: set[str] = set()
        while True:
            if operation_id in visited:
                fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: obligation ownership cycle: {obligation_id}")
                break
            visited.add(operation_id)
            row = rows_by_operation.get(operation_id, {}).get(obligation_id)
            if row is None:
                fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: obligation chain row is absent: {operation_id}")
                break
            if _resolve_transferred_obligation(
                root, receipts, operation_id, row, errors, frozenset()
            ) is None:
                break
            next_operations = children.get((operation_id, obligation_id), [])
            if len(next_operations) > 1:
                fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: obligation ownership branches: {obligation_id}")
                break
            if not next_operations:
                successor_slug = receipts[operation_id][1].get("requestSuccessorSlug")
                if not isinstance(successor_slug, str):
                    fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: current owner is absent: {obligation_id}")
                    break
                work_items = root / "work-items"
                locations = []
                backlog = work_items / "backlog" / f"{successor_slug}.md"
                active = work_items / "active" / successor_slug
                if backlog.is_file():
                    locations.append(backlog)
                if active.is_dir():
                    locations.append(active)
                locations.extend(path for path in (work_items / "archive").glob(f"*/{successor_slug}") if path.is_dir())
                if len(locations) != 1:
                    fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: current owner location is absent or duplicate: {obligation_id}")
                elif locations[0].is_dir() and locations[0].parent.parent.name == "archive":
                    state: list[WorkItemObligationStateV1] = []
                    terminal_errors = validate_work_item(
                        locations[0], strict_revise=False, validate_status_file=False,
                        obligation_state_out=state,
                    )
                    errors.extend(terminal_errors)
                    if len(state) != 1 or any(
                        open_row.obligation_id == obligation_id
                        for open_row in state[0].open_revise
                    ):
                        fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: unresolved obligation has a terminal owner: {obligation_id}")
                elif _transfer_status_relation(locations[0], errors) != (
                    receipts[operation_id][1].get("workItem"),
                    operation_id,
                ):
                    fail(
                        errors,
                        f"WI-OBLIGATION-TRANSFER-OWNER: current owner relation differs: {obligation_id}",
                    )
                break
            next_operation = next_operations[0]
            next_receipt = receipts.get(next_operation)
            if next_receipt is None or next_receipt[1].get("workItem") != receipts[operation_id][1].get("requestSuccessorSlug"):
                fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: successor/source chain differs: {obligation_id}")
                break
            operation_id = next_operation

    for (predecessor, obligation_id), next_operations in children.items():
        if predecessor not in rows_by_operation or obligation_id not in rows_by_operation[predecessor]:
            fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: predecessor obligation is absent: {obligation_id}")
        if len(next_operations) > 1:
            fail(errors, f"WI-OBLIGATION-TRANSFER-OWNER: obligation ownership branches: {obligation_id}")
    return errors


def _sha256_text(value: object) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


_HISTORICAL_DISPOSITION_MAX_BYTES = 64 * 1024
_HISTORICAL_RECOVERED_MAX_BYTES = 32 * 1024
_HISTORICAL_DISPOSITION_MAX_FILES = 1024


def historical_artifact_disposition_resource_caps() -> tuple[int, int]:
    """Return the one validator-owned byte and entry caps for disposition storage."""
    byte_cap = _HISTORICAL_DISPOSITION_MAX_BYTES
    entry_cap = _HISTORICAL_DISPOSITION_MAX_FILES
    if (
        type(byte_cap) is not int
        or type(entry_cap) is not int
        or byte_cap < 1
        or entry_cap < 1
    ):
        raise ValueError("historical artifact disposition resource caps are invalid")
    return byte_cap, entry_cap


def historical_artifact_disposition_storage_identity() -> str:
    """Return the sole canonical, repository-relative disposition storage name."""
    return LEGACY_HISTORICAL_DISPOSITIONS


def historical_artifact_disposition_id(
    archive_identity: str,
    raw_line_ordinal: int,
    raw_line_sha256: str,
    event_sha256: str,
    missing_path: str,
    artifact_revision_sha256: str,
) -> str:
    """State-independent create-only identity for one historical artifact."""
    fields = (
        archive_identity, str(raw_line_ordinal), raw_line_sha256, event_sha256,
        missing_path, artifact_revision_sha256,
    )
    return hashlib.sha256(
        b"orchestrarium-historical-artifact-disposition-v2\0"
        + b"\0".join(field.encode("utf-8") for field in fields)
    ).hexdigest()


def _historical_approval_payload(disposition: dict) -> bytes:
    fields = (
        "schemaVersion", "dispositionId", "archiveIdentity", "workItem", "ledgerSha256",
        "rawLineOrdinal", "rawLineSha256", "runId", "eventSha256", "missingPath",
        "artifactRevisionSha256", "state", "searchReceiptSha256", "approvedBy", "approvedAt",
    )
    return _canonical_projection_bytes({field: disposition[field] for field in fields})


def _historical_missing_artifact_path(root: Path, work_item: str, missing_path: str) -> Path:
    """Resolve only an archive-item-relative missing leaf through the no-follow owner."""
    return confine_legacy_projection_path(
        root,
        f"{work_item}/{missing_path}",
        prefix=("work-items", "archive"),
        allow_missing_leaf=True,
        failure_id="WI-LEDGER-MIGRATION-TARGET-IDENTITY",
    )


def _valid_historical_search_receipt(receipt: object) -> bool:
    required = {
        "schemaVersion", "tool", "toolVersion", "reachableRefs", "reflogs",
        "unreachableObjects", "inventorySha256",
    }
    local_errors: list[str] = []
    if not _strict_shape(receipt, required, required, local_errors, "historical search receipt"):
        return False
    if receipt.get("schemaVersion") != 1:
        return False
    if not all(
        isinstance(receipt.get(field), str) and receipt[field].strip() and len(receipt[field]) <= 256
        for field in ("tool", "toolVersion")
    ) or not _sha256_text(receipt.get("inventorySha256")):
        return False
    for field in ("reachableRefs", "reflogs", "unreachableObjects"):
        value = receipt.get(field)
        if not isinstance(value, dict) or set(value) != {"status", "count"}:
            return False
        if value.get("status") != "complete" or type(value.get("count")) is not int or not 0 <= value["count"] <= 10_000_000:
            return False
    return True


def validate_historical_artifact_disposition_v2(
    disposition: object,
    archive_item: Path,
    ledger_bytes: bytes,
    events: list[dict],
    raw_metadata: list[dict[str, object]],
) -> tuple[HistoricalArtifactAuthorization | None, list[str]]:
    """Return one exact missing PASS artifact exception, never a closure authority."""
    errors: list[str] = []
    ledger = archive_item / "agent-runs.jsonl"
    target = _projection_target_identity(archive_item, ledger, errors, require_ledger=True)
    if target is None:
        return None, errors
    _root, work_item = target
    if not work_item.startswith("work-items/archive/"):
        _projection_fail(errors, "identity", "historical artifact disposition requires a monthly archive")
        return None, errors
    common = {
        "schemaVersion", "dispositionId", "archiveIdentity", "workItem", "ledgerSha256",
        "rawLineOrdinal", "rawLineSha256", "runId", "eventSha256", "missingPath",
        "artifactRevisionSha256", "state",
    }
    if not isinstance(disposition, dict) or disposition.get("schemaVersion") != 2:
        _projection_fail(errors, "manifest", "historical artifact disposition must use schemaVersion 2")
        return None, errors
    text_identity_fields = (
        "dispositionId", "archiveIdentity", "workItem", "ledgerSha256", "rawLineSha256",
        "runId", "eventSha256", "missingPath", "artifactRevisionSha256",
    )
    if (
        type(disposition.get("rawLineOrdinal")) is not int
        or disposition["rawLineOrdinal"] < 1
        or any(not isinstance(disposition.get(field), str) for field in text_identity_fields)
    ):
        _projection_fail(errors, "identity", "historical artifact disposition identity fields have invalid types")
        return None, errors
    state = disposition.get("state")
    recovered = {"contentBytesBase64", "contentBytesSha256"}
    irrecoverable = {
        "searchReceipt", "searchReceiptSha256", "approvedBy", "approvedAt",
        "approvalStatementSha256",
    }
    required = common | (recovered if state == "content-recovered" else irrecoverable if state == "irrecoverable-approved" else set())
    if not _strict_shape(disposition, required, required, errors, "historical artifact disposition"):
        return None, errors
    try:
        disposition_id = confine_legacy_projection_identifier(disposition["dispositionId"])
    except ValueError:
        _projection_fail(errors, "identity", "historical artifact disposition id is unsafe")
        return None, errors
    ledger_sha256 = hashlib.sha256(ledger_bytes).hexdigest()
    if (
        disposition["workItem"] != work_item
        or disposition["ledgerSha256"] != ledger_sha256
        or disposition["archiveIdentity"] != archived_ledger_identity(work_item, ledger_sha256)
    ):
        _projection_fail(errors, "identity", "historical artifact disposition archive identity drift")
    if not all(_sha256_text(disposition.get(key)) for key in ("rawLineSha256", "eventSha256", "artifactRevisionSha256")):
        _projection_fail(errors, "digest", "historical artifact disposition hashes must be SHA-256")
    if not isinstance(disposition.get("missingPath"), str) or not disposition["missingPath"].strip() or not _safe_repo_relative(disposition["missingPath"]):
        _projection_fail(errors, "identity", "historical artifact disposition missing path is unsafe")
    elif disposition.get("dispositionId") != historical_artifact_disposition_id(
        disposition.get("archiveIdentity", ""), disposition.get("rawLineOrdinal", 0),
        disposition.get("rawLineSha256", ""), disposition.get("eventSha256", ""),
        disposition["missingPath"], disposition.get("artifactRevisionSha256", ""),
    ):
        _projection_fail(errors, "identity", "historical artifact disposition id is not deterministic")
    candidates = [
        (event, metadata)
        for event, metadata in zip(events, raw_metadata)
        if metadata.get("line") == disposition.get("rawLineOrdinal")
    ]
    if len(candidates) != 1:
        _projection_fail(errors, "identity", "historical artifact disposition does not bind one raw ledger line")
        return None, errors
    event, metadata = candidates[0]
    if (
        metadata.get("sha256") != disposition.get("rawLineSha256")
        or hashlib.sha256(_canonical_projection_bytes(event)).hexdigest() != disposition.get("eventSha256")
        or event.get("schemaVersion") != 2
        or event.get("status") != "completed"
        or event.get("gate") != "PASS"
        or event.get("runId") != disposition.get("runId")
        or event.get("artifact") != disposition.get("missingPath")
        or event.get("artifactRevision") != disposition.get("artifactRevisionSha256")
    ):
        _projection_fail(errors, "identity", "historical artifact disposition does not bind one raw V2 PASS artifact")
        return None, errors
    try:
        observed_path = _historical_missing_artifact_path(_root, work_item, event["artifact"])
    except ValueError:
        observed_path = None
    if observed_path is None or observed_path.exists():
        _projection_fail(errors, "identity", "historical artifact disposition target is not an exact missing artifact")
    if state == "content-recovered":
        encoded = disposition.get("contentBytesBase64")
        max_encoded = 4 * ((_HISTORICAL_RECOVERED_MAX_BYTES + 2) // 3) + 4
        if not isinstance(encoded, str) or len(encoded) > max_encoded:
            recovered_bytes = None
        else:
            try:
                recovered_bytes = base64.b64decode(encoded, validate=True)
            except (ValueError, TypeError):
                recovered_bytes = None
        if (
            recovered_bytes is None
            or len(recovered_bytes) > _HISTORICAL_RECOVERED_MAX_BYTES
            or not _sha256_text(disposition.get("contentBytesSha256"))
            or hashlib.sha256(recovered_bytes).hexdigest() != disposition.get("contentBytesSha256")
            or disposition.get("contentBytesSha256") != disposition.get("artifactRevisionSha256")
        ):
            _projection_fail(errors, "digest", "content-recovered disposition bytes are not exact")
    else:
        receipt = disposition.get("searchReceipt")
        if (
            not _valid_historical_search_receipt(receipt)
            or not _sha256_text(disposition.get("searchReceiptSha256"))
            or disposition.get("searchReceiptSha256") != hashlib.sha256(_canonical_projection_bytes(receipt)).hexdigest()
        ):
            _projection_fail(errors, "manifest", "irrecoverable disposition search receipt is incomplete or drifted")
        if (
            not isinstance(disposition.get("approvedBy"), str)
            or not disposition["approvedBy"].strip()
            or len(disposition["approvedBy"]) > 256
            or not isinstance(disposition.get("approvedAt"), str)
            or _STRICT_UTC_RE.fullmatch(disposition["approvedAt"]) is None
            or not _sha256_text(disposition.get("approvalStatementSha256"))
            or disposition.get("approvalStatementSha256") != hashlib.sha256(_historical_approval_payload(disposition)).hexdigest()
        ):
            _projection_fail(errors, "manifest", "irrecoverable disposition approval is incomplete or drifted")
    if errors:
        return None, errors
    return HistoricalArtifactAuthorization(
        disposition["rawLineOrdinal"], disposition["rawLineSha256"], disposition["eventSha256"],
        event["runId"], event["artifact"], disposition["artifactRevisionSha256"],
    ), errors


def authorized_historical_missing_artifacts(
    archive_item: Path,
    ledger_bytes: bytes,
    events: list[dict],
    raw_metadata: list[dict[str, object]],
) -> tuple[dict[int, HistoricalArtifactAuthorization], list[str]]:
    """Read V2 create-only dispositions; V1 files are intentionally nonauthorizing."""
    errors: list[str] = []
    ledger = archive_item / "agent-runs.jsonl"
    target = _projection_target_identity(archive_item, ledger, errors, require_ledger=True)
    if target is None:
        return {}, errors
    root, work_item = target
    try:
        directory = confine_legacy_projection_path(
            root,
            f"work-items/{LEGACY_HISTORICAL_DISPOSITIONS}",
            prefix=("work-items",),
            allow_missing_leaf=True,
            failure_id="WI-LEDGER-MIGRATION-MANIFEST-INVALID",
        )
    except ValueError as exc:
        _projection_fail(errors, "identity", f"historical artifact disposition directory is unsafe: {exc}")
        return {}, errors
    if not directory.exists():
        return {}, errors
    if not directory.is_dir() or _is_link_or_reparse(directory):
        _projection_fail(errors, "manifest", "historical artifact disposition directory is unsafe")
        return {}, errors
    authorized: dict[int, HistoricalArtifactAuthorization] = {}
    entries = list(itertools.islice(directory.iterdir(), _HISTORICAL_DISPOSITION_MAX_FILES + 1))
    if len(entries) > _HISTORICAL_DISPOSITION_MAX_FILES:
        _projection_fail(errors, "manifest", "historical artifact disposition directory exceeds resource cap")
        return {}, errors
    for path in sorted(entries):
        if path.suffix != ".json" or _is_link_or_reparse(path) or not path.is_file():
            _projection_fail(errors, "manifest", "historical artifact disposition path is unsafe")
            continue
        try:
            if os.lstat(path).st_size > _HISTORICAL_DISPOSITION_MAX_BYTES:
                _projection_fail(errors, "manifest", "historical artifact disposition exceeds resource cap")
                continue
            raw = path.read_bytes()
        except OSError:
            _projection_fail(errors, "manifest", "historical artifact disposition cannot be read safely")
            continue
        payload = _projection_json_object(raw, path, errors)
        if payload is None:
            continue
        if payload.get("schemaVersion") == 1:
            continue
        if payload.get("schemaVersion") != 2:
            _projection_fail(errors, "manifest", f"historical artifact disposition {path.name} has unsupported schema")
            continue
        disposition_id = payload.get("dispositionId")
        try:
            disposition_id = confine_legacy_projection_identifier(disposition_id)
        except ValueError:
            _projection_fail(errors, "identity", f"historical artifact disposition {path.name} id is unsafe")
            continue
        if path.name != f"{disposition_id}.json":
            _projection_fail(errors, "identity", f"historical artifact disposition filename differs from dispositionId")
            continue
        if payload.get("workItem") != work_item:
            continue
        exception, disposition_errors = validate_historical_artifact_disposition_v2(
            payload, archive_item, ledger_bytes, events, raw_metadata
        )
        errors.extend(disposition_errors)
        if exception is None:
            continue
        if exception.raw_line_ordinal in authorized:
            _projection_fail(errors, "topology", "more than one disposition authorizes one missing artifact")
            continue
        authorized[exception.raw_line_ordinal] = exception
    return authorized, errors


def validate_archived_ledger_obligations(
    item: Path, telemetry: dict[str, int] | None = None
) -> tuple[list[str], list[dict], list[dict]]:
    """Validate one immutable monthly archive through the normal projection owners.

    Historical rows not admitted through a manifest stay outside the V2 epoch.
    This reader never writes the archive, registry, or any disposition.
    """
    errors: list[str] = []
    ledger = item / "agent-runs.jsonl"
    target = _projection_target_identity(item, ledger, errors, require_ledger=True)
    if target is None:
        return errors, [], []
    _root, relative_item = target
    if not relative_item.startswith("work-items/archive/"):
        _projection_fail(errors, "identity", "archived obligation validation requires a monthly archive")
        return errors, [], []
    try:
        ledger_bytes = ledger.read_bytes()
    except OSError as exc:
        fail(errors, f"cannot read ledger: {ledger}: {exc}")
        return errors, [], []
    raw_metadata: list[dict[str, object]] = []
    events = load_jsonl(ledger, errors, raw_metadata, ledger_bytes)
    rows = _ledger_projection_rows(events, raw_metadata, errors)
    shaped_rows, projection_counters, projection_errors = _project_manifest_rows(
        rows, item, ledger, ledger_bytes
    )
    errors.extend(projection_errors)
    effective_rows, migration_counters, migration_errors = _project_migration_rows(shaped_rows, item)
    errors.extend(migration_errors)
    effective_events = _row_events(effective_rows)
    runtime_rows = _runtime_rows_from_projection(effective_rows)
    historical_authorizations, disposition_errors = authorized_historical_missing_artifacts(
        item, ledger_bytes, events, raw_metadata
    )
    errors.extend(disposition_errors)
    # V1 rows that were not replaced by the manifest are historical input only.
    event_validity, closure_validity = derive_archived_event_validity(
        effective_events,
        item,
        errors,
        historical_authorizations,
        rows=effective_rows,
        telemetry=telemetry,
    )
    typed_closure_validity = _validity_from_boolean_events(
        runtime_rows, closure_validity
    )
    inactive = resolve_closure_invalidations(
        runtime_rows,
        typed_closure_validity,
        errors,
        telemetry,
        context=None,
    )
    active_positions = [
        pos
        for pos in range(len(effective_events))
        if pos not in inactive
    ]
    active_rows = [runtime_rows[pos] for pos in active_positions]
    active_validity = tuple(
        typed_closure_validity[pos] for pos in active_positions
    )
    open_revise, open_launches = validate_closure(
        active_rows, errors, telemetry, validity=active_validity
    )
    if telemetry is not None:
        for name, value in {**migration_counters, **projection_counters}.items():
            telemetry[f"ledger-migration-{name}"] = value
    return errors, open_revise, open_launches


def validate_status(
    item: Path,
    context: LedgerValidationContextV1 | Sequence[Mapping[str, object]],
    errors: list[str],
    *,
    current_open_launch_ids: Sequence[str] | None = None,
) -> None:
    if isinstance(context, LedgerValidationContextV1) and not _sealed_context_is_bound(
        context.rows, context, errors
    ):
        return
    status_path = item / "status.md"
    if not status_path.exists():
        fail(errors, f"missing status.md: {status_path}")
        return
    text = status_path.read_text(encoding="utf-8")
    if is_quick_fix_status_candidate(text):
        validate_quick_fix_status(text, errors)
        return
    if is_staged_status(text):
        validate_staged_status(text, errors)
        return
    for section in FULL_STATUS_SECTIONS:
        if section not in text:
            fail(errors, f"status.md missing section: {section}")

    if not isinstance(context, LedgerValidationContextV1):
        # Backward-compatible direct helper calls remain diagnostic-only. The
        # authorizing validate_work_item path always supplies the typed context.
        open_launch_ids = tuple(
            event.get("runId", "")
            for event in context
            if event.get("status") == "running"
        )
    elif context.view is not None:
        if current_open_launch_ids is None:
            fail(
                errors,
                "WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS: active status validation requires the current closure result",
            )
            return
        open_launch_ids = current_open_launch_ids
    else:
        open_launch_ids = context.group_open_launch_ids
    if open_launch_ids and "Primary task status**: closed" in text:
        fail(errors, "status.md cannot be closed while ledger has running agents")


def project_legacy_obligation_migrations(
    events: list[dict], raw_metadata: list[dict[str, object]], item: Path
) -> tuple[list[dict], dict[str, int], list[str]]:
    """Project valid V2 legacy-class anchors without mutating raw ledger history."""
    counters = {"raw": len(events), "apply": 0, "revoke": 0, "projected": 0}
    if any(event.get("schemaVersion") == 3 for event in events) and any(
        event.get("eventKind") == LEGACY_MIGRATION_KIND for event in events
    ):
        return events, counters, [LEGACY_MIGRATION_V3_UNSUPPORTED]

    errors: list[str] = []
    positions: dict[str, list[int]] = {}
    for pos, event in enumerate(events):
        run_id = event.get("runId")
        if isinstance(run_id, str):
            positions.setdefault(run_id, []).append(pos)

    active: dict[int, dict] = {}
    applies: dict[str, tuple[int, dict]] = {}
    revoked: set[str] = set()
    fatal_control_identity = False
    control_seen = {
        str(event["runId"]).casefold()
        for event in events
        if event.get("eventKind") != LEGACY_MIGRATION_KIND
        and isinstance(event.get("runId"), str)
    }
    migration_fields = {
        "migrationAction", "normalizationKind", "migratesRunId", "migratesEventSha256",
        "revokesMigrationRunId", "revokesMigrationEventSha256", "replacementEvent",
    }
    for pos, anchor in enumerate(events):
        kind = anchor.get("eventKind")
        if kind != LEGACY_MIGRATION_KIND:
            if migration_fields & set(anchor):
                errors.append(f"{anchor.get('runId')}: migration control fields require {LEGACY_MIGRATION_KIND}")
            continue
        control_errors: list[str] = []
        run_id = anchor.get("runId")
        identity_collision = isinstance(run_id, str) and run_id.casefold() in control_seen
        validate_event(anchor, item, control_seen, control_errors)
        if control_errors:
            errors.extend(control_errors)
            fatal_control_identity = fatal_control_identity or identity_collision
            continue
        action = anchor.get("migrationAction")
        if action not in {"apply", "revoke"}:
            errors.append(f"{anchor.get('runId')}: migrationAction must be apply or revoke")
            continue
        counters[action] += 1
        fixed = {
            "schemaVersion": 2, "role": "lead", "executionRole": "main",
            "status": "completed", "gate": "none",
        }
        if any(anchor.get(key) != wanted for key, wanted in fixed.items()):
            errors.append(f"{anchor.get('runId')}: migration control requires fixed Lead/main authority")
            continue
        if action == "apply":
            normalization_kind = anchor.get("normalizationKind", "invalid-finding-class")
            row = LEGACY_MIGRATION_NORMALIZATIONS.get(normalization_kind)
            if row is None or anchor.get("scope") != row["scope"]:
                errors.append(f"{anchor.get('runId')}: migration normalization kind/scope is invalid")
                continue
            target_id = anchor.get("migratesRunId")
            target_digest = anchor.get("migratesEventSha256")
            candidates = positions.get(target_id, []) if isinstance(target_id, str) else []
            if len(candidates) != 1 or candidates[0] >= pos:
                errors.append(f"{anchor.get('runId')}: migration target must be one unique earlier event")
                continue
            target_pos = candidates[0]
            target = events[target_pos]
            if target.get("schemaVersion") != 2 or target.get("eventKind") != "terminal" or target.get("eventKind") in {LEGACY_MIGRATION_KIND, "closure-invalidation"}:
                errors.append(f"{anchor.get('runId')}: migration target is not an eligible V2 terminal")
                continue
            recorded = raw_metadata[target_pos].get("sha256") if target_pos < len(raw_metadata) else None
            if target_digest != recorded:
                errors.append(f"{anchor.get('runId')}: migration target digest mismatch")
                continue
            if normalization_kind == "invalid-finding-class":
                if target.get("gate") != "REVISE":
                    errors.append(f"{anchor.get('runId')}: finding-class target is not REVISE")
                    continue
                if "findingClass" not in target or target.get("findingClass") in FINDING_CLASSES:
                    errors.append(f"{anchor.get('runId')}: migration target diagnostic set is not {{{LEDGER_EVENT_FINDING_CLASS_INVALID}}}")
                    continue
                normalized = {**target, "findingClass": "legacy-unclassified"}
            else:
                if not isinstance(target.get("scratchEvidence"), str):
                    errors.append(f"{anchor.get('runId')}: migration target does not carry string scratchEvidence")
                    continue
                normalized = {key: value for key, value in target.items() if key != "scratchEvidence"}
            candidate_errors: list[str] = []
            validate_event(normalized, item, set(), candidate_errors)
            if candidate_errors:
                errors.append(f"{anchor.get('runId')}: migration target retains another invalid diagnostic")
                continue
            relation_events = list(events)
            relation_events[target_pos] = normalized
            relation_error = migration_terminal_launch_relation_error(relation_events, target_pos, item)
            if relation_error is not None:
                errors.append(f"{anchor.get('runId')}: {relation_error}")
                continue
            replacement = anchor.get("replacementEvent")
            if replacement != normalized:
                errors.append(f"{anchor.get('runId')}: replacementEvent does not match closed normalization")
                continue
            if anchor.get("evidence") != [{"kind": "manual-check", "ref": row["evidence"].format(target=target_id, digest=target_digest)}]:
                errors.append(f"{anchor.get('runId')}: migration evidence does not match closed normalization")
                continue
            if target_pos in active:
                errors.append(f"{anchor.get('runId')}: migration topology permits one apply per target")
                active.pop(target_pos, None)
                continue
            active[target_pos] = replacement
            applies[str(anchor.get("runId"))] = (target_pos, replacement, normalization_kind)
        else:
            apply_id = anchor.get("revokesMigrationRunId")
            apply_digest = anchor.get("revokesMigrationEventSha256")
            candidates = positions.get(apply_id, []) if isinstance(apply_id, str) else []
            if len(candidates) != 1 or candidates[0] >= pos or apply_id in revoked:
                errors.append(f"{anchor.get('runId')}: revoke must target one unique earlier active apply")
                continue
            apply_pos = candidates[0]
            apply_event = events[apply_pos]
            recorded = raw_metadata[apply_pos].get("sha256") if apply_pos < len(raw_metadata) else None
            if apply_event.get("eventKind") != LEGACY_MIGRATION_KIND or apply_event.get("migrationAction") != "apply" or apply_digest != recorded:
                errors.append(f"{anchor.get('runId')}: revoke must bind an earlier apply digest")
                continue
            applied = applies.get(str(apply_id))
            if applied is None:
                errors.append(f"{anchor.get('runId')}: revoke target apply is not active")
                continue
            row = LEGACY_MIGRATION_NORMALIZATIONS[applied[2]]
            if anchor.get("scope") != row["scope"] or anchor.get("evidence") != [{"kind": "manual-check", "ref": f"revoke {apply_id} {apply_digest}"}]:
                errors.append(f"{anchor.get('runId')}: revoke does not match referenced normalization")
                continue
            active.pop(applied[0], None)
            revoked.add(str(apply_id))

    if fatal_control_identity:
        counters["projected"] = 0
        return events, counters, errors
    effective = [
        active.get(pos, event)
        for pos, event in enumerate(events)
        if event.get("eventKind") != LEGACY_MIGRATION_KIND
    ]
    counters["projected"] = len(active)
    return effective, counters, errors


def _project_migration_rows(
    rows: tuple[LedgerProjectionRowV1, ...], item: Path
) -> tuple[tuple[LedgerProjectionRowV1, ...], dict[str, int], list[str]]:
    """Apply legacy migration without renumbering surviving physical sources."""
    events = _row_events(rows)
    effective, counters, errors = project_legacy_obligation_migrations(
        events, _row_metadata(rows), item
    )
    surviving = tuple(
        row for row in rows if row.event.get("eventKind") != LEGACY_MIGRATION_KIND
    )
    if len(effective) != len(surviving):
        # A rejected control topology deliberately returns the raw event list.
        if len(effective) == len(rows) and all(event is row.event for row, event in zip(rows, effective)):
            return rows, counters, errors
        _projection_fail(errors, "identity", "migration projection changed surviving row cardinality")
        return rows, counters, errors
    return (
        tuple(
            row if event is row.event else LedgerProjectionRowV1(
                copy.deepcopy(event), row.raw_line_ordinal, row.raw_line_sha256,
                row.raw_event_sha256, "migration-replaced",
            )
            for row, event in zip(surviving, effective)
        ),
        counters,
        errors,
    )


def reduce_v3_events(events: list[dict]) -> tuple[dict | None, list[str]]:
    """Reduce only V3 control events; legacy events remain readable, non-authorizing input."""

    v3_events = [event for event in events if event.get("schemaVersion") == 3]
    if not v3_events:
        return None, []
    owner = load_solution_attempt_owner()
    state: dict | None = None
    errors: list[str] = []
    for event in v3_events:
        result = owner.reduce_solution_attempt(state, event)
        if result.get("changed") is True and result.get("result") in {
            owner.OK,
            owner.CLASS_REJECTED,
        }:
            state = result.get("state")
            continue
        fail(
            errors,
            f"V3 event {event.get('eventId')}: reducer denied event with "
            f"{result.get('result')}",
        )
    return state, errors


def validate_solution_attempt_gate_binding(binding: object) -> dict[str, object]:
    """Validate an exact settled snapshot without granting lifecycle authority."""

    denied = {"result": "SOL-E001-STATE-INVALID", "eligible": False}
    required = {
        "owner",
        "routeEnabled",
        "routeBinding",
        "expectedRouteBinding",
        "launchState",
        "finalSnapshot",
        "expectedFinalSnapshot",
    }
    if not isinstance(binding, dict) or set(binding) != required:
        return denied
    if binding.get("owner") != "agent_run_store.commit_operation":
        return denied

    digest = re.compile(r"^[0-9a-f]{64}$", re.ASCII)
    route_binding = binding.get("routeBinding")
    expected_route_binding = binding.get("expectedRouteBinding")
    if binding.get("routeEnabled") is not True:
        return {"result": "SOL-E007-ENFORCEMENT-UNAVAILABLE", "eligible": False}
    if not all(
        isinstance(value, str) and digest.fullmatch(value) is not None
        for value in (route_binding, expected_route_binding)
    ) or route_binding != expected_route_binding:
        return {"result": "SOL-E007-ENFORCEMENT-UNAVAILABLE", "eligible": False}
    if binding.get("launchState") != "REAPED":
        return denied

    final_snapshot = binding.get("finalSnapshot")
    expected_snapshot = binding.get("expectedFinalSnapshot")
    if not all(
        isinstance(value, str) and digest.fullmatch(value) is not None
        for value in (final_snapshot, expected_snapshot)
    ):
        return denied
    if final_snapshot != expected_snapshot:
        return {"result": "SOL-E006-RECEIPT-STALE", "eligible": False}
    return {"result": "SOL-OK", "eligible": True}


def resolve_closure_invalidations(
    rows: Sequence[RuntimeLedgerRowV1],
    validity: Sequence[LedgerEventValidityV1],
    errors: list[str],
    telemetry: dict[str, int] | None = None,
    *,
    context: LedgerValidationContextV1 | None = None,
) -> set[int]:
    """Return whole-event positions excluded only from V1/V2 relation reduction."""
    if len(rows) != len(validity):
        fail(errors, "WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS: invalidation row/validity cardinality differs")
        return set()
    if not _sealed_context_is_bound(rows, context, errors):
        return set()
    tel = telemetry if telemetry is not None else {}
    inactive: set[int] = set()
    positions: dict[str, list[int]] = {}
    for pos, row in enumerate(rows):
        event = row.event
        run_id = event.get("runId")
        if isinstance(run_id, str):
            positions.setdefault(run_id, []).append(pos)

    for pos, recovery_row in enumerate(rows):
        recovery = recovery_row.event
        if recovery.get("eventKind") != "closure-invalidation":
            continue
        if recovery.get("invalidationMode") == _INVALID_CURRENT_DISPOSITION_MODE:
            continue
        active_context = context is not None and context.observation.activation_state == "active"
        if not validity[pos].current_schema_valid or (
            active_context and recovery_row.epoch != "strict-suffix"
        ):
            continue
        recovery_id = recovery.get("runId")
        target_id = recovery.get("invalidatesRunId")
        candidates = positions.get(target_id, []) if isinstance(target_id, str) else []
        if len(candidates) != 1 or candidates[0] >= pos:
            fail(errors, f"{recovery_id}: ledger-recovery:target-identity requires exactly one earlier event for {target_id!r}")
            continue
        target_pos = candidates[0]
        target_row = rows[target_pos]
        target = target_row.event
        if target_pos in inactive or target.get("eventKind") == "closure-invalidation":
            fail(errors, f"{recovery_id}: ledger-recovery:topology forbids duplicate, chain, cycle, or correction target {target_id}")
            continue
        if target.get("schemaVersion") != 2 or target.get("eventKind") == "launch" or not isinstance(target.get("closesRunIds"), list):
            fail(errors, f"{recovery_id}: ledger-recovery:target-ineligible {target_id}")
            continue
        target_individually_valid = (
            validity[target_pos].authority.closer_eligible
            if active_context and target_row.epoch == "sealed-prefix"
            else validity[target_pos].current_schema_valid
        )
        if not target_individually_valid:
            fail(errors, f"{recovery_id}: ledger-recovery:target-per-event-invalid {target_id}")
            continue
        if recovery.get("invalidatesEventSha256") != target_row.raw_body_sha256:
            fail(errors, f"{recovery_id}: ledger-recovery:target-digest-mismatch {target_id}")
            continue

        # Reuse the one C1-C5 evaluator: adding the candidate target to its
        # already-active prefix must introduce a relation diagnostic. No copied
        # C-rule logic is maintained in this recovery owner.
        before_positions = [index for index in range(target_pos) if index not in inactive]
        with_positions = before_positions + [target_pos]
        before_rows = tuple(rows[index] for index in before_positions)
        with_rows = tuple(rows[index] for index in with_positions)
        before_validity = tuple(validity[index] for index in before_positions)
        with_validity = tuple(validity[index] for index in with_positions)
        before_errors: list[str] = []
        with_errors: list[str] = []
        _validate_closure_authority(
            before_rows,
            before_errors,
            validity=before_validity,
        )
        _validate_closure_authority(
            with_rows,
            with_errors,
            validity=with_validity,
        )
        introduced = with_errors[len(before_errors):] if with_errors[: len(before_errors)] == before_errors else with_errors
        if not introduced:
            fail(errors, f"{recovery_id}: ledger-recovery:target-authoritative {target_id}")
            continue
        inactive.add(target_pos)
        tel["recovery-accepted"] = tel.get("recovery-accepted", 0) + 1
    return inactive


def _reduce_effective_current_state(
    rows: Sequence[RuntimeLedgerRowV1],
    item: Path,
    errors: list[str],
    telemetry: dict[str, int] | None,
    *,
    context: LedgerValidationContextV1 | None,
) -> tuple[
    tuple[int, ...],
    tuple[LedgerEventValidityV1, ...],
    list[Mapping[str, object]],
    list[Mapping[str, object]],
]:
    """Own validity, invalidation, and one effective closure reduction."""

    if not _sealed_context_is_bound(rows, context, errors):
        return (), (), [], []
    validity = derive_event_validity(rows, item, errors, context=context)
    baseline_errors: list[str] = []
    baseline_revise, baseline_launches = _validate_closure_authority(
        rows, baseline_errors, validity=validity
    )
    inactive = resolve_closure_invalidations(
        rows, validity, errors, telemetry, context=context
    )
    active_positions = tuple(
        position for position in range(len(rows)) if position not in inactive
    )
    active_rows = tuple(rows[position] for position in active_positions)
    active_current_validity = tuple(
        validity[position].current_schema_valid for position in active_positions
    )
    active_masks = _derive_authority_masks(active_rows, active_current_validity, item)
    active_validity = tuple(
        LedgerEventValidityV1(current_schema_valid, authority)
        for current_schema_valid, authority in zip(
            active_current_validity, active_masks
        )
    )
    effective_validity = [
        LedgerEventValidityV1(entry.current_schema_valid, _NO_LEDGER_AUTHORITY)
        for entry in validity
    ]
    for position, row_validity in zip(active_positions, active_validity):
        effective_validity[position] = row_validity
    open_revise, open_launches = _validate_closure_authority(
        active_rows, errors, telemetry, validity=active_validity
    )
    if telemetry is not None:
        reopened_revise = max(0, len(open_revise) - len(baseline_revise))
        reopened_launch = max(0, len(open_launches) - len(baseline_launches))
        if reopened_revise:
            telemetry["recovery-reopened-revise"] = (
                telemetry.get("recovery-reopened-revise", 0) + reopened_revise
            )
        if reopened_launch:
            telemetry["recovery-reopened-launch"] = (
                telemetry.get("recovery-reopened-launch", 0) + reopened_launch
            )
    return active_positions, tuple(effective_validity), open_revise, open_launches


def validate_work_item(
    item: Path,
    ledger_path: Path | None = None,
    strict_revise: bool = True,
    telemetry: dict[str, int] | None = None,
    validate_status_file: bool = True,
    projection_manifest_blobs: dict[str, bytes] | None = None,
    projection_registry_bytes: bytes | None = None,
    compatibility_artifacts: LedgerCompatibilityArtifactSetV1 | None = None,
    obligation_state_out: list[WorkItemObligationStateV1] | None = None,
) -> list[str]:
    """ledger_path: candidate-validation seam — validate THIS file instead of the live
    ledger (the atomic-write flow validates its temp candidate before os.replace).
    strict_revise: open v2 REVISE obligations are errors (decision item 3: a validation
    tool's job is failing); pass False only for triage sessions.
    """
    errors: list[str] = []
    if compatibility_artifacts is not None and (
        ledger_path is not None
        or projection_manifest_blobs is not None
        or projection_registry_bytes is not None
    ):
        fail(
            errors,
            "WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS: compatibility artifacts cannot be mixed with older candidate inputs",
        )
        return errors
    selected_ledger = ledger_path or (item / "agent-runs.jsonl")
    root = repo_root_for(item)
    live_compatibility_observed = bool(
        root is not None
        and _ledger_h1_live_participants_exist(root)
    )
    effective_compatibility_artifacts = compatibility_artifacts
    validated_h1_partition: tuple[
        str, str, str, str, tuple[tuple[int, str], ...]
    ] | None = None
    selected_identity: str | None = None
    if live_compatibility_observed and effective_compatibility_artifacts is None:
        assert root is not None
        target = _projection_target_identity(item, selected_ledger, errors)
        if target is None:
            return errors
        selected_identity = f"{target[1]}/agent-runs.jsonl"
        try:
            live_artifacts = _load_live_ledger_h1_artifacts(root)
        except _LedgerH1AcquisitionError as exc:
            errors.extend(
                _ledger_h1_acquisition_failure_context(exc).observation.diagnostics
            )
            return errors
        if live_artifacts is None:
            fail(
                errors,
                "WI-LEDGER-COMPAT-ACTIVATION-INCOMPLETE: active compatibility candidate inputs are unavailable",
            )
            return errors
        live_contexts = _load_effective_ledger_group(
            root, compatibility_artifacts=live_artifacts
        )
        classification, selection = _classify_ledger_h1_selection(
            target[1],
            selected_identity,
            live_artifacts,
            live_contexts,
        )
        if classification == "invalid":
            assert isinstance(selection, LedgerValidationContextV1)
            errors.extend(selection.observation.diagnostics)
            return errors
        if classification == "ordinary-nonmember":
            live_compatibility_observed = False
            tokens = {id(context.invocation_token): context.invocation_token for context in live_contexts.values()}
            if len(tokens) != 1:
                fail(
                    errors,
                    "WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS: validated H1 group has no unique invocation token",
                )
                return errors
            token = next(iter(tokens.values()))
            if not isinstance(token, _LedgerInvocationTokenV1):
                fail(
                    errors,
                    "WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS: validated H1 group invocation token is invalid",
                )
                return errors
            validated_h1_partition = token.h1_projection_partition
        else:
            if ledger_path is None:
                selected_identity = getattr(
                    selection, "logical_ledger_path", selected_identity
                )
                effective_compatibility_artifacts = live_artifacts
            else:
                try:
                    candidate_bytes = selected_ledger.read_bytes()
                except OSError as exc:
                    fail(errors, f"cannot read ledger: {selected_ledger}: {exc}")
                    return errors
                candidate_ledgers = dict(live_artifacts.ledger_bytes_by_path)
                candidate_ledgers[selected_identity] = candidate_bytes
                effective_compatibility_artifacts = LedgerCompatibilityArtifactSetV1(
                    MappingProxyType(candidate_ledgers),
                    live_artifacts.h1_manifest_path,
                    live_artifacts.h1_manifest_bytes,
                    live_artifacts.ledger_manifest_path,
                    live_artifacts.ledger_manifest_bytes,
                    live_artifacts.registry_bytes,
                    live_artifacts.receipt_bytes_by_path,
                    live_artifacts.participant_locations_by_path,
                )
    if effective_compatibility_artifacts is not None or live_compatibility_observed:
        if root is None:
            fail(errors, "WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS: work item has no repository root")
            return errors
        if selected_identity is None:
            selected_identity = selected_ledger.absolute().relative_to(root.absolute()).as_posix()
        context = load_effective_ledger_view(
            root,
            item,
            selected_identity,
            compatibility_artifacts=effective_compatibility_artifacts,
        )
        errors.extend(context.observation.diagnostics)
        if telemetry is not None and context.observation.disposition_notices:
            key = "ledger-compat-suffix-disposed-nonauthorizing"
            telemetry[key] = telemetry.get(key, 0) + len(
                context.observation.disposition_notices
            )
        if context.view is None:
            if context.observation.activation_state == "revoked":
                raw_events = [dict(row.event) for row in context.rows]
                _, v3_errors = reduce_v3_events(raw_events)
                errors.extend(v3_errors)
                validate_scratch_ownership(raw_events, item, errors)
                _active_positions, _validity, open_revise, open_launches = (
                    _reduce_effective_current_state(
                        context.rows,
                        item,
                        errors,
                        telemetry,
                        context=context,
                    )
                )
                _capture_obligation_state(
                    obligation_state_out, context.rows, open_revise, open_launches
                )
                if strict_revise:
                    for event in open_launches:
                        fail(
                            errors,
                            f"unsettled launch: {event.get('runId')} (lane={event.get('lane')!r}) — no terminal event; a lost verdict must not be invisible to the gate (re-settle or cancel it)",
                        )
                    for event in open_revise:
                        fail(
                            errors,
                            f"open REVISE obligation: {event.get('runId')} (lane={event.get('lane')!r}, artifact={event.get('artifact')!r}) — closes only on re-verification PASS (closesRunIds) or a typed disposition, never on author belief or validator green",
                        )
                if validate_status_file:
                    validate_status(item, context, errors)
            return errors
        _active_positions, _validity, open_revise, open_launches = (
            _reduce_effective_current_state(
                context.rows,
                item,
                errors,
                telemetry,
                context=context,
            )
        )
        _capture_obligation_state(
            obligation_state_out, context.rows, open_revise, open_launches
        )
        if strict_revise:
            for event in open_launches:
                fail(
                    errors,
                    f"unsettled launch: {event.get('runId')} (lane={event.get('lane')!r}) — no terminal event; a lost verdict must not be invisible to the gate (re-settle or cancel it)",
                )
            for event in open_revise:
                fail(
                    errors,
                    f"open REVISE obligation: {event.get('runId')} (lane={event.get('lane')!r}, artifact={event.get('artifact')!r}) — closes only on re-verification PASS (closesRunIds) or a typed disposition, never on author belief or validator green",
                )
        if validate_status_file:
            validate_status(
                item,
                context,
                errors,
                current_open_launch_ids=tuple(
                    event["runId"]
                    for event in open_launches
                    if isinstance(event.get("runId"), str)
                ),
            )
        return errors
    status_path = item / "status.md"
    status_text = status_path.read_text(encoding="utf-8") if status_path.exists() else ""
    # V1 keeps an undelegated quick-fix ledger-free.  A staged/full item and an
    # explicitly supplied candidate ledger retain the exact fail-closed behavior.
    ledger_free_quick_fix = (
        ledger_path is None
        and not selected_ledger.exists()
        and is_quick_fix_status(status_text)
    )
    raw_metadata: list[dict[str, object]] = []
    ledger_bytes = b""
    if not ledger_free_quick_fix:
        try:
            ledger_bytes = selected_ledger.read_bytes()
        except OSError as exc:
            fail(errors, f"cannot read ledger: {selected_ledger}: {exc}")
        events = load_jsonl(selected_ledger, errors, raw_metadata, ledger_bytes)
    else:
        events = []
    rows = _ledger_projection_rows(events, raw_metadata, errors)
    shape_rows, projection_counters, projection_errors = _project_manifest_rows(
        rows, item, selected_ledger, ledger_bytes,
        manifest_blobs=projection_manifest_blobs,
        registry_bytes=projection_registry_bytes,
        validated_h1_partition=validated_h1_partition,
    )
    errors.extend(projection_errors)
    native_effective_rows, migration_counters, migration_errors = _project_migration_rows(shape_rows, item)
    errors.extend(migration_errors)
    native_effective_events = _row_events(native_effective_rows)
    if ledger_path is not None and any(event.get("schemaVersion") == 3 for event in events):
        fail(errors, "legacy V1/V2 writer refuses a ledger containing schemaVersion 3")
    _, v3_errors = reduce_v3_events(events)
    errors.extend(v3_errors)
    validate_scratch_ownership(native_effective_events, item, errors)
    inherited_rows = _inherited_transfer_rows(item, errors)
    effective_rows = inherited_rows + native_effective_rows
    effective_events = _row_events(effective_rows)
    runtime_rows = _runtime_rows_from_projection(effective_rows)
    active_positions, event_validity, open_revise, open_launches = (
        _reduce_effective_current_state(
            runtime_rows,
            item,
            errors,
            telemetry,
            context=None,
        )
    )
    _capture_obligation_state(
        obligation_state_out, effective_rows, open_revise, open_launches
    )
    active_events = [effective_events[pos] for pos in active_positions]
    active_rows = [runtime_rows[pos] for pos in active_positions]
    active_validity = [event_validity[pos] for pos in active_positions]
    if telemetry is not None:
        for name, value in migration_counters.items():
            telemetry[f"ledger-migration-{name}"] = value
        for name, value in projection_counters.items():
            telemetry[f"ledger-migration-{name}"] = value
    if strict_revise:
        for event in open_launches:
            fail(
                errors,
                f"unsettled launch: {event.get('runId')} (lane={event.get('lane')!r}) — no terminal "
                f"event; a lost verdict must not be invisible to the gate (re-settle or cancel it)",
            )
        for event in open_revise:
            fail(
                errors,
                f"open REVISE obligation: {event.get('runId')} (lane={event.get('lane')!r}, "
                f"artifact={event.get('artifact')!r}) — closes only on re-verification PASS "
                f"(closesRunIds) or a typed disposition, never on author belief or validator green",
            )
    is_monthly_archive = (
        len(item.parts) >= 3
        and item.parent.parent.name == "archive"
        and re.fullmatch(r"\d{4}-\d{2}", item.parent.name) is not None
    )
    closure_path = item / "closure.md"
    archived_v1_closure = False
    if is_monthly_archive and closure_path.is_file():
        closure_text = closure_path.read_text(encoding="utf-8", errors="replace")
        archived_v1_closure = all(
            re.search(rf"(?im)^\s*{re.escape(field)}\s*:\s*\S", closure_text)
            for field in ("Closed", "Outcome", "Evidence", "Residual risk")
        )
    if validate_status_file and not (is_monthly_archive and archived_v1_closure):
        context = LedgerValidationContextV1(
            selected_ledger.absolute().relative_to(root.absolute()).as_posix() if root is not None else str(selected_ledger),
            tuple(active_rows),
            None,
            LedgerCompatibilityObservationV1("inactive", (), ()),
            tuple(
                sorted(
                    (
                        f"{item.relative_to(root).as_posix()}\0{event.get('runId')}"
                        for event in open_revise
                        if root is not None and isinstance(event.get("runId"), str)
                    ),
                    key=lambda value: value.encode("utf-8"),
                )
            ),
            tuple(
                sorted(
                    {
                        event["runId"]
                        for event in open_launches
                        if isinstance(event.get("runId"), str)
                    }
                    | {
                        event["runId"]
                        for event, row_validity in zip(active_events, active_validity)
                        if row_validity.current_schema_valid
                        and event.get("status") == "running"
                        and isinstance(event.get("runId"), str)
                    },
                    key=lambda value: value.encode("utf-8"),
                )
            ),
            object(),
        )
        validate_status(item, context, errors)
    return errors


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-item", required=True, help="Path to one work-items/active/<item> directory")
    parser.add_argument("--ledger-path", help="Validate this candidate ledger file instead of the item's live agent-runs.jsonl")
    parser.add_argument("--no-strict-revise", action="store_true", help="Do not fail on open v2 REVISE obligations (triage only)")
    parser.add_argument("--telemetry", action="store_true", help="Print closure rule-fire counters")
    args = parser.parse_args(argv)

    item = Path(args.work_item).resolve()
    telemetry: dict[str, int] = {}
    errors = validate_work_item(
        item,
        ledger_path=Path(args.ledger_path).resolve() if args.ledger_path else None,
        strict_revise=not args.no_strict_revise,
        telemetry=telemetry,
    )
    if args.telemetry and telemetry:
        counters = ", ".join(f"{k}={v}" for k, v in sorted(telemetry.items()))
        print(f"TELEMETRY: {counters}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print(f"RESULT: FAIL ({len(errors)} errors)")
        return 1
    print(f"RESULT: PASS ({item})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
