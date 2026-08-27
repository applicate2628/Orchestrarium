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
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


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
    "closerRunId",
    "targetTuple",
}
EVIDENCE_ALLOWED_FIELDS = {"kind", "ref", "result"}
AGENT_RUN_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "shared" / "schemas" / "agent-runs.schema.json"
AGENT_RUN_SCHEMA = json.loads(AGENT_RUN_SCHEMA_PATH.read_text(encoding="utf-8"))
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

    recovery_fields = {"invalidatesRunId", "invalidatesEventSha256"}
    if event_kind == "closure-invalidation":
        if schema_version != 2:
            fail(errors, f"{run_id}: closure-invalidation requires schemaVersion 2")
        fixed = {
            "role": "lead",
            "executionRole": "main",
            "status": "completed",
            "gate": "none",
            "scope": ["ledger-recovery:closure-invalidation"],
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
        for forbidden in ("launchRunId", "closesRunIds", "artifact", "scratchEvidence"):
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
        if artifact_path is not None and not artifact_path.exists() and not authorized_missing:
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
        for key in sorted(typed_terminal_fields & set(event)):
            fail(errors, f"{run_id}: {key} requires terminalClass")

    for key in ("artifactIdentity", "externalDispatchId", "externalEvidenceRunId", "effortMappingLoss", "closerRunId"):
        if key in event and (not isinstance(event.get(key), str) or not event[key].strip()):
            fail(errors, f"{run_id}: {key} must be a non-empty string")
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

    return len(errors) == error_count_on_entry


def validate_event(event: dict, item: Path, seen: set[str], errors: list[str]) -> bool:
    """Validate a public ledger event without any historical exception."""
    return _validate_event(event, item, seen, errors)


def derive_event_validity(
    events: list[dict],
    item: Path,
    errors: list[str],
    *,
    validate_schema_version: int | None = None,
) -> list[bool]:
    """Return one validation result per input position.

    When a schema version is selected, other positions remain aligned but are
    ineligible without emitting diagnostics. This preserves the archive scanner's
    intentional legacy epoch while keeping validation state validator-owned.
    """
    seen: set[str] = set()
    event_validity: list[bool] = []
    for event in events:
        if (
            validate_schema_version is not None
            and event.get("schemaVersion") != validate_schema_version
        ):
            event_validity.append(False)
            continue
        event_validity.append(
            validate_event(event, item, seen, errors)
        )
    return event_validity


def derive_archived_event_validity(
    events: list[dict],
    item: Path,
    errors: list[str],
    authorizations: dict[int, HistoricalArtifactAuthorization],
    *,
    rows: tuple[LedgerProjectionRowV1, ...],
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
        event_is_valid = _validate_event(
            event, item, seen, errors, historical_artifact_authorization=authorization
        )
        validity.append(event_is_valid)
        # Historical artifact evidence makes this row diagnostically complete,
        # never an authority for closure, invalidation, or terminal settlement.
        closure_validity.append(event_is_valid and authorization is None)
    return validity, closure_validity


def validate_closure(
    events: list[dict],
    errors: list[str],
    telemetry: dict[str, int] | None = None,
    *,
    event_validity: list[bool] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Ledger-level REVISE-closure validation (decision 2026-07-16-review-verdict-closure,
    minimal slice). Returns (open_v2_revise_events, open_launch_events) — obligations never discharged/settled events (never discharged by a valid
    closer). Closure is derived ONLY from the closesRunIds relation — never from
    role/scope/artifact string matching (proven unstable by live replay in the design loop).
    """
    tel = telemetry if telemetry is not None else {}

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
    for pos, event in enumerate(events):
        if event_validity is not None and (
            len(event_validity) != len(events) or not event_validity[pos]
        ):
            continue
        if event.get("eventKind") != "terminal":
            continue
        rid = event.get("runId")
        launch_id = event.get("launchRunId")
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
        if event_validity is not None and not event_validity[target[0]]:
            fail(errors, f"{rid}: launchRunId {launch_id} references an invalid launch event")
            bump("lifecycle-invalid-launch-ref")
            continue
        if launch_id in terminals_by_launch:
            fail(errors, f"{rid}: duplicate terminal for launch {launch_id} (first: {terminals_by_launch[launch_id]})")
            bump("lifecycle-duplicate-terminal")
        else:
            terminals_by_launch[launch_id] = rid if isinstance(rid, str) else "<invalid>"

    discharged: dict[str, str] = {}  # target runId -> closer runId
    for pos, event in enumerate(events):
        # A caller-provided false validity bit is a complete settlement
        # boundary: the row keeps its per-event diagnostics but may not become
        # a terminal, closer, or evidence authority in this reduction.
        if event_validity is not None and (
            len(event_validity) != len(events) or not event_validity[pos]
        ):
            continue
        gate = event.get("gate")
        # Privileged waiver authorization consumes explicit validation state at
        # the event's ledger position. Missing/misaligned state is invalid;
        # rendered diagnostics and attacker-controlled runIds carry no authority.
        security_validity: list[bool] | None = None
        if gate == SECURITY_REVIEWER_WAIVER_GATE:
            if (
                event_validity is None
                or len(event_validity) != len(events)
                or not event_validity[pos]
            ):
                continue
            security_validity = event_validity
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
            if target.get("gate") != "REVISE":
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
                        if event_validity is not None:
                            typed_close_ok = typed_close_ok and event_validity[evidence_pos]
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
                if isinstance(t_art, str) and t_art.strip():
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
        event for event in events
        if event.get("schemaVersion") == 2
        and event.get("gate") == "REVISE"
        and event.get("runId") not in discharged
    ]
    tel["open-revise"] = tel.get("open-revise", 0) + len(open_revise)
    # Unsettled launches (no terminal) are strict-mode blockers too: a lost terminal
    # must not make a possibly-REVISE run invisible to the push gate.
    open_launches = [
        event for event in events
        if event.get("eventKind") == "launch"
        and isinstance(event.get("runId"), str)
        and event["runId"] not in terminals_by_launch
    ]
    tel["open-launches"] = tel.get("open-launches", 0) + len(open_launches)
    return open_revise, open_launches


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
    if selected_ledger != canonical_ledger:
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
) -> tuple[list[dict], dict[str, int], list[str]]:
    """Read verified immutable legacy rows through closed shape-only profiles."""
    counters = {"manifest-apply": 0, "manifest-revoke": 0, "manifest-projected": 0}
    errors: list[str] = []
    target = _projection_target_identity(item, selected_ledger, errors)
    if target is None:
        return events, counters, errors
    root, _relative_item = target
    work_items = root / "work-items"
    manifests = work_items / LEGACY_PROJECTION_MANIFEST_DIR
    registry = work_items / LEGACY_PROJECTION_REGISTRY
    candidate_input = manifest_blobs is not None or registry_bytes is not None
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
    ledger = selected_ledger
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
            registry_lines = registry.read_bytes().splitlines(keepends=True)
            manifest_inputs = [(path.name, None, str(path)) for path in sorted(manifests.iterdir())]
        except OSError as exc:
            _projection_fail(errors, "manifest", f"cannot read projection input: {exc}")
            return events, counters, errors
        registry_source = str(registry)
    manifest_by_id: dict[str, tuple[dict, bytes]] = {}
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
    active: dict[tuple[str, int], tuple[dict, bytes, dict]] = {}
    operation_ids: set[str] = set()
    apply_lines: dict[str, tuple[tuple[str, int], bytes]] = {}
    seen_group_ids: set[str] = set()
    current_group_id: str | None = None
    history_groups: dict[str, list[dict]] = {}
    for ordinal, physical in enumerate(registry_lines, start=1):
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
) -> tuple[tuple[LedgerProjectionRowV1, ...], dict[str, int], list[str]]:
    """Apply the existing manifest owner while retaining physical row identity."""
    events = _row_events(rows)
    projected, counters, errors = project_manifest_bound_legacy_ledger_projections(
        events, _row_metadata(rows), item, selected_ledger, ledger_bytes,
        manifest_blobs=manifest_blobs, registry_bytes=registry_bytes,
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
    )
    effective_metadata = _row_metadata(effective_rows)
    inactive = resolve_closure_invalidations(
        effective_events, closure_validity, effective_metadata, errors, telemetry
    )
    active_positions = [
        pos
        for pos in range(len(effective_events))
        if pos not in inactive
    ]
    active_events = [effective_events[pos] for pos in active_positions]
    active_validity = [closure_validity[pos] for pos in active_positions]
    open_revise, open_launches = validate_closure(
        active_events, errors, telemetry, event_validity=active_validity
    )
    if telemetry is not None:
        for name, value in {**migration_counters, **projection_counters}.items():
            telemetry[f"ledger-migration-{name}"] = value
    return errors, open_revise, open_launches


def validate_status(item: Path, events: list[dict], errors: list[str]) -> None:
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

    running_events = [event for event in events if event.get("status") == "running"]
    if running_events and "Primary task status**: closed" in text:
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
    events: list[dict],
    event_validity: list[bool],
    raw_metadata: list[dict[str, object]],
    errors: list[str],
    telemetry: dict[str, int] | None = None,
) -> set[int]:
    """Return whole-event positions excluded only from V1/V2 relation reduction."""
    tel = telemetry if telemetry is not None else {}
    inactive: set[int] = set()
    positions: dict[str, list[int]] = {}
    for pos, event in enumerate(events):
        run_id = event.get("runId")
        if isinstance(run_id, str):
            positions.setdefault(run_id, []).append(pos)

    for pos, recovery in enumerate(events):
        if recovery.get("eventKind") != "closure-invalidation":
            continue
        if pos >= len(event_validity) or not event_validity[pos]:
            continue
        recovery_id = recovery.get("runId")
        target_id = recovery.get("invalidatesRunId")
        candidates = positions.get(target_id, []) if isinstance(target_id, str) else []
        if len(candidates) != 1 or candidates[0] >= pos:
            fail(errors, f"{recovery_id}: ledger-recovery:target-identity requires exactly one earlier event for {target_id!r}")
            continue
        target_pos = candidates[0]
        target = events[target_pos]
        if target_pos in inactive or target.get("eventKind") == "closure-invalidation":
            fail(errors, f"{recovery_id}: ledger-recovery:topology forbids duplicate, chain, cycle, or correction target {target_id}")
            continue
        if target.get("schemaVersion") != 2 or target.get("eventKind") == "launch" or not isinstance(target.get("closesRunIds"), list):
            fail(errors, f"{recovery_id}: ledger-recovery:target-ineligible {target_id}")
            continue
        if target_pos >= len(event_validity) or not event_validity[target_pos]:
            fail(errors, f"{recovery_id}: ledger-recovery:target-per-event-invalid {target_id}")
            continue
        recorded_digest = raw_metadata[target_pos].get("sha256") if target_pos < len(raw_metadata) else None
        if recovery.get("invalidatesEventSha256") != recorded_digest:
            fail(errors, f"{recovery_id}: ledger-recovery:target-digest-mismatch {target_id}")
            continue

        # Reuse the one C1-C5 evaluator: adding the candidate target to its
        # already-active prefix must introduce a relation diagnostic. No copied
        # C-rule logic is maintained in this recovery owner.
        before_positions = [index for index in range(target_pos) if index not in inactive]
        with_positions = before_positions + [target_pos]
        before_events = [events[index] for index in before_positions]
        with_events = [events[index] for index in with_positions]
        before_validity = [event_validity[index] for index in before_positions]
        with_validity = [event_validity[index] for index in with_positions]
        before_errors: list[str] = []
        with_errors: list[str] = []
        validate_closure(before_events, before_errors, event_validity=before_validity)
        validate_closure(with_events, with_errors, event_validity=with_validity)
        introduced = with_errors[len(before_errors):] if with_errors[: len(before_errors)] == before_errors else with_errors
        if not introduced:
            fail(errors, f"{recovery_id}: ledger-recovery:target-authoritative {target_id}")
            continue
        inactive.add(target_pos)
        tel["recovery-accepted"] = tel.get("recovery-accepted", 0) + 1
    return inactive


def validate_work_item(
    item: Path,
    ledger_path: Path | None = None,
    strict_revise: bool = True,
    telemetry: dict[str, int] | None = None,
    validate_status_file: bool = True,
    projection_manifest_blobs: dict[str, bytes] | None = None,
    projection_registry_bytes: bytes | None = None,
) -> list[str]:
    """ledger_path: candidate-validation seam — validate THIS file instead of the live
    ledger (the atomic-write flow validates its temp candidate before os.replace).
    strict_revise: open v2 REVISE obligations are errors (decision item 3: a validation
    tool's job is failing); pass False only for triage sessions.
    """
    errors: list[str] = []
    selected_ledger = ledger_path or (item / "agent-runs.jsonl")
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
    )
    errors.extend(projection_errors)
    effective_rows, migration_counters, migration_errors = _project_migration_rows(shape_rows, item)
    errors.extend(migration_errors)
    effective_events = _row_events(effective_rows)
    if ledger_path is not None and any(event.get("schemaVersion") == 3 for event in events):
        fail(errors, "legacy V1/V2 writer refuses a ledger containing schemaVersion 3")
    event_validity = derive_event_validity(effective_events, item, errors)
    _, v3_errors = reduce_v3_events(events)
    errors.extend(v3_errors)
    validate_scratch_ownership(effective_events, item, errors)
    effective_metadata = _row_metadata(effective_rows)
    inactive = resolve_closure_invalidations(effective_events, event_validity, effective_metadata, errors, telemetry)
    active_positions = [pos for pos in range(len(effective_events)) if pos not in inactive]
    active_events = [effective_events[pos] for pos in active_positions]
    active_validity = [event_validity[pos] for pos in active_positions]
    raw_errors: list[str] = []
    raw_open_revise, raw_open_launches = validate_closure(effective_events, raw_errors, event_validity=event_validity)
    open_revise, open_launches = validate_closure(
        active_events,
        errors,
        telemetry,
        event_validity=active_validity,
    )
    if telemetry is not None:
        for name, value in migration_counters.items():
            telemetry[f"ledger-migration-{name}"] = value
        for name, value in projection_counters.items():
            telemetry[f"ledger-migration-{name}"] = value
        reopened_revise = max(0, len(open_revise) - len(raw_open_revise))
        reopened_launch = max(0, len(open_launches) - len(raw_open_launches))
        if reopened_revise:
            telemetry["recovery-reopened-revise"] = telemetry.get("recovery-reopened-revise", 0) + reopened_revise
        if reopened_launch:
            telemetry["recovery-reopened-launch"] = telemetry.get("recovery-reopened-launch", 0) + reopened_launch
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
        validate_status(item, events, errors)
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
