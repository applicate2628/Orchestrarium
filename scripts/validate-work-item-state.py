#!/usr/bin/env python3
import argparse
import hashlib
import importlib.util
import json
import os
import re
import stat as stat_module
import sys
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
EVENT_KINDS = {"launch", "terminal", "standalone"}
EFFORT_ORDER = ["low", "medium", "high", "xhigh", "max"]  # ordered, ascending strength
FINDING_CLASSES = {"publication-safety", "security", "correctness", "performance", "other"}
PROTECTED_CLASSES = {"publication-safety", "security"}  # non-user-waivable (spine: $security-reviewer only)
V2_ONLY_FIELDS = {
    "eventKind",
    "launchRunId",
    "closesRunIds",
    "artifactRevision",
    "lane",
    "effort",
    "findingClass",
    "scratchEvidence",
}
# Canonical executionRole values (mirrors shared/schemas/agent-runs.schema.json).
# There is exactly ONE main-conversation identity: "main". The main conversation
# also holds the Lead role — orchestration weight is the status.md
# `orchestration: light | full-lead` field, never a second executionRole value.
EXECUTION_ROLES = {"main", "internal", "consultant", "external-worker", "external-reviewer", "external-brigade"}
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
}
EVIDENCE_ALLOWED_FIELDS = {"kind", "ref", "result"}
AGENT_RUN_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "shared" / "schemas" / "agent-runs.schema.json"
AGENT_RUN_SCHEMA = json.loads(AGENT_RUN_SCHEMA_PATH.read_text(encoding="utf-8"))
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


def load_jsonl(path: Path, errors: list[str]) -> list[dict]:
    if not path.exists():
        fail(errors, f"missing ledger: {path}")
        return []
    events: list[dict] = []
    try:
        stream = path.open("r", encoding="utf-8", newline="")
    except OSError as exc:
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
                event = decode_json_object(line, source=f"{path}:{line_no}")
            except ValueError as exc:
                fail(errors, str(exc))
                continue
            events.append(event)
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


def validate_event(event: dict, item: Path, seen: set[str], errors: list[str]) -> bool:
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

    if "scratchEvidence" in event:
        validate_scratch_evidence(event, item, artifact_path, run_id, errors)

    if gate == "PASS":
        if status != "completed":
            fail(errors, f"{run_id}: PASS gate requires completed status")
        if not artifact:
            fail(errors, f"{run_id}: PASS gate requires artifact")
        if artifact_path is not None and not artifact_path.exists():
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
    if "closesRunIds" in event:
        closes = event.get("closesRunIds")
        if not isinstance(closes, list) or not closes or any(
            not isinstance(x, str) or len(x) < 8 for x in closes
        ):
            fail(errors, f"{run_id}: closesRunIds must be a non-empty list of runId strings")
        elif len(set(closes)) != len(closes):
            fail(errors, f"{run_id}: closesRunIds must not contain duplicates")
        if gate not in CLOSURE_GATES:
            fail(
                errors,
                f"{run_id}: closesRunIds is only legal on PASS, {USER_WAIVER_GATE}, "
                f"or {SECURITY_REVIEWER_WAIVER_GATE} events",
            )
    for key in ("artifactRevision", "lane"):
        if key in event and (not isinstance(event.get(key), str) or not event[key].strip()):
            fail(errors, f"{run_id}: {key} must be a non-empty string")
    if "effort" in event and event.get("effort") not in EFFORT_ORDER:
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
        event_validity.append(validate_event(event, item, seen, errors))
    return event_validity


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
        if launch_id in terminals_by_launch:
            fail(errors, f"{rid}: duplicate terminal for launch {launch_id} (first: {terminals_by_launch[launch_id]})")
            bump("lifecycle-duplicate-terminal")
        else:
            terminals_by_launch[launch_id] = rid if isinstance(rid, str) else "<invalid>"

    discharged: dict[str, str] = {}  # target runId -> closer runId
    for pos, event in enumerate(events):
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


def validate_work_item(
    item: Path,
    ledger_path: Path | None = None,
    strict_revise: bool = True,
    telemetry: dict[str, int] | None = None,
    validate_status_file: bool = True,
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
    events = [] if ledger_free_quick_fix else load_jsonl(selected_ledger, errors)
    event_validity = derive_event_validity(events, item, errors)
    validate_scratch_ownership(events, item, errors)
    open_revise, open_launches = validate_closure(
        events,
        errors,
        telemetry,
        event_validity=event_validity,
    )
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
