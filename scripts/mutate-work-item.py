#!/usr/bin/env python3
"""Single synchronous owner for the work-items physical lifecycle V1.

The reusable API raises ``LifecycleError``.  Only ``main`` translates a failure
into a process exit code.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable


README_BEGIN = "<!-- BEGIN GENERATED WORK-ITEMS STATUS -->"
README_END = "<!-- END GENERATED WORK-ITEMS STATUS -->"
TRIAL_OWNER = "work-items-lifecycle-v1-trial"
TRIAL_MARKER = ".work-items-lifecycle-v1-trial.json"
MIGRATION_OWNER = "work-items-lifecycle-v1-migration"
MIGRATION_SCHEMA_VERSION = 1
MIGRATION_DIGEST_ALGORITHMS = {
    "file": "sha256-file-bytes-v1",
    "directory": "sha256-tree-entries-v1",
}
V1_TERMINALIZATION_OWNER = "work-items-lifecycle-v1-terminalization"
V1_TERMINALIZATION_SCHEMA_VERSION = 2
V1_TERMINALIZATION_AUTHORIZATION = "operator-authorized-v1-terminalization"
V1_TERMINALIZATION_FAILURE = "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"
LEGACY_RETIREMENT_OWNER = "work-items-lifecycle-v1-legacy-retirement"
LEGACY_RETIREMENT_SCHEMA_VERSION = 1
LEGACY_RETIREMENT_FILE = "legacy-retirement.json"
LEGACY_CLEANUP_OWNER = "work-items-lifecycle-v1-legacy-candidate-cleanup"
LEGACY_CLEANUP_SCHEMA_VERSION = 1
LEGACY_CLEANUP_FILE = "legacy-candidate-cleanup.json"
CURRENT_IDENTITY_NORMALIZATION_OWNER = "work-items-lifecycle-v1-current-identity-normalization"
CURRENT_IDENTITY_NORMALIZATION_SCHEMA_VERSION = 1
WORK_ITEM_SCHEMA_KEY = "Lifecycle-schema"
WORK_ITEM_SCHEMA_VALUE = "work-items-physical-v1"
WORK_ITEM_SCHEMA_MARKER = f"{WORK_ITEM_SCHEMA_KEY}: {WORK_ITEM_SCHEMA_VALUE}"
LEGACY_READ_CLASSIFICATION = "WI-LEGACY-READ-COMPAT"
README_SECTIONS = (
    "Current focus",
    "Next actions",
    "Blockers",
    "Roadmap and milestones",
    "Recently completed",
)
UTC_INSTANT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)*$")
OPTIONAL_RELATION_ABSENCE_MARKERS = frozenset({"none"})
FIELD_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\*\*)?([A-Za-z][A-Za-z0-9 -]*?)(?:\*\*)?\s*:\s*(.*?)\s*$"
)
FENCED_CODE_OPEN_RE = re.compile(
    r"^ {0,3}(?P<fence>`{3,}|~{3,})(?P<info>[^\r\n]*)$"
)
WORK_ITEM_SCHEMA_OCCURRENCE_RE = re.compile(
    r"^\s*(?:-\s*)?(?:\*\*)?(lifecycle-schema)(?:\*\*)?\s*:\s*(.*?)\s*$",
    re.IGNORECASE,
)


class LifecycleError(RuntimeError):
    def __init__(self, failure_id: str, message: str):
        super().__init__(message)
        self.failure_id = failure_id


@dataclass(frozen=True)
class Category:
    name: str
    current_root: str
    current_kind: str
    current_statuses: frozenset[str]
    terminal_statuses: frozenset[str]


CATEGORIES = {
    "work-item": Category(
        "work-item",
        "",
        "work-item",
        frozenset({"candidate", "active", "blocked"}),
        frozenset({"closed", "cancelled", "completed"}),
    ),
    "bug": Category(
        "bug",
        "bugs",
        "flat",
        frozenset({"open", "triaged", "accepted"}),
        frozenset({"fixed", "resolved", "refuted", "superseded", "closed"}),
    ),
    "decision": Category(
        "decision",
        "decisions",
        "flat",
        frozenset({"proposed", "accepted"}),
        frozenset({"dropped", "superseded", "reverted", "no-longer-governing"}),
    ),
    "lesson": Category(
        "lesson",
        "lessons",
        "flat",
        frozenset({"open", "applied"}),
        frozenset({"dropped", "superseded", "archived"}),
    ),
    "roadmap": Category(
        "roadmap",
        "roadmaps",
        "flat",
        frozenset({"draft", "active"}),
        frozenset({"superseded", "archived"}),
    ),
    "epic": Category(
        "epic",
        "epics",
        "flat",
        frozenset({"active"}),
        frozenset({"closed", "cancelled", "archived"}),
    ),
}
CATEGORY_ALIASES = {
    "work-items": "work-item",
    "workitem": "work-item",
    "bugs": "bug",
    "decisions": "decision",
    "lessons": "lesson",
    "roadmaps": "roadmap",
    "epics": "epic",
}


@dataclass
class ReadmeEntry:
    section: str
    logical_reference: str
    label: str
    link: Path
    checked: bool
    detail: str = ""
    source_paths: list[Path] = field(default_factory=list)
    classification: str | None = None


@dataclass(frozen=True)
class CategoryAdmission:
    category: str
    current_reader: str
    terminal_validator: str
    utc_field_owner: str
    negative_fixture: str
    utc_field: str
    detail_field: str
    evidence_field: str


def _work_items_root(root: Path) -> Path:
    root = root.resolve()
    return root if root.name == "work-items" else root / "work-items"


def is_valid_slug(slug: str) -> bool:
    """Return whether *slug* satisfies the canonical lifecycle identity grammar."""
    return isinstance(slug, str) and SLUG_RE.fullmatch(slug) is not None


def _validate_slug(slug: str) -> None:
    if not is_valid_slug(slug):
        raise LifecycleError("WI-INVALID-SLUG", f"invalid bare slug: {slug!r}")


def _authoritative_markdown_lines(text: str) -> Iterable[tuple[int, str]]:
    """Yield positioned Markdown lines that can own lifecycle fields.

    Fenced code is evidence/content, not record metadata.  Reject an opened
    fence without a valid close so malformed Markdown cannot silently widen or
    shrink the authoritative field surface.
    """
    fence_char: str | None = None
    fence_length = 0
    for line_number, line in enumerate(text.splitlines(), start=1):
        if fence_char is not None:
            closing = re.fullmatch(
                rf" {{0,3}}{re.escape(fence_char)}{{{fence_length},}}[ \t]*",
                line,
            )
            if closing:
                fence_char = None
                fence_length = 0
            continue

        opening = FENCED_CODE_OPEN_RE.fullmatch(line)
        if opening:
            fence = opening.group("fence")
            info = opening.group("info")
            if fence[0] == "`" and "`" in info:
                yield line_number, line
                continue
            fence_char = fence[0]
            fence_length = len(fence)
            continue
        yield line_number, line

    if fence_char is not None:
        raise LifecycleError(
            "WI-CATEGORY-MARKDOWN-INVALID",
            "unterminated fenced code block in lifecycle record",
        )


def _authoritative_field_occurrences(
    text: str,
) -> tuple[tuple[int, str, str, str], ...]:
    occurrences: list[tuple[int, str, str, str]] = []
    for line_number, line in _authoritative_markdown_lines(text):
        match = FIELD_RE.fullmatch(line)
        if match:
            occurrences.append(
                (
                    line_number,
                    match.group(1).strip().casefold(),
                    match.group(2).strip(),
                    line,
                )
            )
    return tuple(occurrences)


def _parse_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for _line_number, name, value, _line in _authoritative_field_occurrences(text):
        fields[name] = value
    return fields


def _validate_canonical_candidate_header(data: bytes) -> None:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LifecycleError(
            "WI-CATEGORY-STATUS-INVALID",
            "canonical candidate header must be UTF-8",
        ) from exc

    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        closing = next(
            (index for index, line in enumerate(lines[1:], start=2) if line.strip() == "---"),
            None,
        )
        if closing is None:
            raise LifecycleError(
                "WI-CATEGORY-STATUS-INVALID",
                "canonical candidate frontmatter is unterminated",
            )
        header_start, header_end = 2, closing - 1
        malformed_header_end = header_end
    else:
        header_start, header_end = 1, 0
        for line_number, line in enumerate(lines, start=1):
            if not FIELD_RE.fullmatch(line):
                break
            header_end = line_number
        malformed_header_end = 0
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                break
            malformed_header_end = line_number

    occurrences = _authoritative_field_occurrences(text)
    statuses = [
        (line_number, value)
        for line_number, name, value, _line in occurrences
        if name == "status"
    ]
    malformed_status = any(
        re.match(
            r"^\s*(?:-\s*)?(?:\*\*)?status(?:\*\*)?(?:\s|$)",
            line,
            re.IGNORECASE,
        )
        and not FIELD_RE.fullmatch(line)
        for line_number, line in _authoritative_markdown_lines(text)
        if header_start <= line_number <= malformed_header_end
    )
    if (
        malformed_status
        or len(statuses) != 1
        or not (header_start <= statuses[0][0] <= header_end)
        or statuses[0][1] != "candidate"
    ):
        raise LifecycleError(
            "WI-CATEGORY-STATUS-INVALID",
            "canonical candidate header requires exactly one 'status: candidate' field",
        )


def _terminalization_authoritative_field_occurrences(
    text: str, utc_field: str = "Terminal-at"
) -> tuple[str, ...]:
    authoritative = {utc_field.casefold(), "v1-migration-evidence"}
    occurrences: list[str] = []
    for _line_number, line in _authoritative_markdown_lines(text):
        match = FIELD_RE.fullmatch(line)
        if match:
            name = match.group(1).strip().casefold()
            if name in authoritative:
                occurrences.append(name)
    return tuple(occurrences)


def _schema_marker_occurrences(data: bytes, member: str) -> tuple[tuple[str, str, str], ...]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LifecycleError(
            "WI-CATEGORY-SCHEMA-INVALID",
            f"{member} schema marker source must be UTF-8",
        ) from exc
    occurrences: list[tuple[str, str, str]] = []
    for _line_number, line in _authoritative_markdown_lines(text):
        match = WORK_ITEM_SCHEMA_OCCURRENCE_RE.fullmatch(line)
        if match:
            occurrences.append((line, match.group(1), match.group(2)))
    return tuple(occurrences)


def _require_canonical_schema_marker(
    occurrences: tuple[tuple[str, str, str], ...],
    member: str,
) -> None:
    if len(occurrences) != 1 or occurrences[0] != (
        WORK_ITEM_SCHEMA_MARKER,
        WORK_ITEM_SCHEMA_KEY,
        WORK_ITEM_SCHEMA_VALUE,
    ):
        raise LifecycleError(
            "WI-CATEGORY-SCHEMA-INVALID",
            f"{member} must contain exactly one canonical {WORK_ITEM_SCHEMA_MARKER!r}",
        )


def _stamp_schema_marker(data: bytes, member: str) -> bytes:
    occurrences = _schema_marker_occurrences(data, member)
    if occurrences:
        _require_canonical_schema_marker(occurrences, member)
        return data
    separator = b"" if data.endswith(b"\n") else b"\n"
    return data + separator + WORK_ITEM_SCHEMA_MARKER.encode("utf-8") + b"\n"


def _optional_relation_values(
    value: str | None,
    *,
    comma_separated: bool,
) -> tuple[str, ...]:
    if value is None:
        return ()
    normalized = value.strip()
    if (
        not normalized
        or normalized in OPTIONAL_RELATION_ABSENCE_MARKERS
    ):
        return ()
    if comma_separated:
        return tuple(part.strip() for part in normalized.split(","))
    return (normalized,)


def _strict_utc(value: str) -> datetime:
    if not UTC_INSTANT_RE.fullmatch(value):
        raise LifecycleError(
            "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
            f"terminal instant must be strict UTC YYYY-MM-DDTHH:MM:SSZ: {value!r}",
        )
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise LifecycleError(
            "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
            f"invalid terminal instant: {value!r}",
        ) from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise LifecycleError(
            "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
            f"non-canonical terminal instant: {value!r}",
        )
    return parsed


def archive_month(terminal_instant: str) -> str:
    return _strict_utc(terminal_instant).strftime("%Y-%m")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        temp_path = None
        if path.read_bytes() != data:
            raise LifecycleError("WI-ATOMIC-BYTE-CHECK", f"byte check failed: {path}")
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass


def _canonical_category(reference: str) -> tuple[Category, str]:
    if reference.count(":") != 1:
        raise LifecycleError(
            "WI-REFERENCE-INVALID",
            f"reference must be category-qualified as <category>:<bare-slug>: {reference!r}",
        )
    category_name, slug = reference.split(":", 1)
    category_name = CATEGORY_ALIASES.get(category_name, category_name)
    category = CATEGORIES.get(category_name)
    if category is None:
        raise LifecycleError("WI-REFERENCE-INVALID", f"unknown category: {category_name!r}")
    _validate_slug(slug)
    return category, slug


def _category_locations(root: Path, category: Category, slug: str) -> list[Path]:
    work_items = _work_items_root(root)
    locations: list[Path] = []
    if category.current_kind == "work-item":
        backlog = work_items / "backlog" / f"{slug}.md"
        active = work_items / "active" / slug
        if backlog.is_file():
            locations.append(backlog)
        if active.is_dir():
            locations.append(active)
        archive = work_items / "archive"
        if archive.is_dir():
            locations.extend(
                sorted(
                    month / slug
                    for month in archive.iterdir()
                    if month.is_dir() and (month / slug).is_dir()
                )
            )
    else:
        current = work_items / category.current_root / f"{slug}.md"
        if current.is_file():
            locations.append(current)
        archive = work_items / category.current_root / "archive"
        if archive.is_dir():
            locations.extend(
                sorted(
                    month / f"{slug}.md"
                    for month in archive.iterdir()
                    if month.is_dir() and (month / f"{slug}.md").is_file()
                )
            )
    return locations


def resolve_category(root: Path, reference: str) -> Path:
    category, slug = _canonical_category(reference)
    locations = _category_locations(root, category, slug)
    if len(locations) > 1:
        raise LifecycleError(
            "WI-CATEGORY-DUAL-LOCATION",
            f"{reference} has {len(locations)} physical locations",
        )
    if not locations:
        raise LifecycleError("WI-REFERENCE-MISSING", f"no physical location for {reference}")
    return locations[0].resolve()


def work_item_dependency_state(root: Path, slug: str) -> str:
    """Resolve one dependency through the lifecycle owner.

    Physical location owns the state: backlog and active records are open,
    while only a dated archive record is done. Missing and duplicate identities
    retain ``resolve_category``'s stable fail-closed errors.
    """
    location = resolve_category(root, f"work-item:{slug}")
    archive = (_work_items_root(root) / "archive").resolve()
    return "done" if archive in location.parents else "open"


def resolve_legacy_path(root: Path, legacy_path: str) -> Path:
    candidate = Path(legacy_path)
    if candidate.is_absolute():
        raise LifecycleError("WI-REFERENCE-INVALID", "legacy path must be relative")
    repo_root = _work_items_root(root).parent.resolve()
    resolved = (repo_root / candidate).resolve()
    if resolved != repo_root and repo_root not in resolved.parents:
        raise LifecycleError("WI-REFERENCE-INVALID", "legacy path escapes repository")
    if not resolved.exists():
        raise LifecycleError(
            "WI-LEGACY-LINK-UNMAPPED",
            f"legacy path is absent and has no incoming-link inventory: {legacy_path}",
        )
    return resolved


def _relative_link(work_items: Path, path: Path) -> str:
    return Path(os.path.relpath(path, work_items)).as_posix()


def _status_entry(root: Path, item: Path) -> ReadmeEntry:
    status_path = item / "status.md"
    if not status_path.is_file():
        raise LifecycleError("WI-CATEGORY-STATUS-MISSING", f"missing status.md: {item}")
    text = status_path.read_text(encoding="utf-8")
    fields = _parse_fields(text)
    status = fields.get("status", "")
    if status in CATEGORIES["work-item"].terminal_statuses:
        raise LifecycleError(
            "WI-CATEGORY-TERMINAL-IN-CURRENT",
            f"terminal work-item remains active: {item.name}",
        )
    if status not in {"active", "blocked"}:
        raise LifecycleError(
            "WI-CATEGORY-STATUS-INVALID", f"active work-item has invalid status {status!r}: {item}"
        )
    section = "Blockers" if status == "blocked" or fields.get("blocker") else "Current focus"
    label = fields.get("task") or item.name
    detail = fields.get("blocker", "") if section == "Blockers" else fields.get("current step", "")
    entry = ReadmeEntry(
        section,
        f"work-item:{item.name}",
        label,
        status_path,
        False,
        detail,
        [status_path],
    )
    progressive: list[str] = []
    for field_name, category in (("roadmap", "roadmap"), ("epic", "epic")):
        related_values = _optional_relation_values(
            fields.get(field_name),
            comma_separated=False,
        )
        if not related_values:
            continue
        related_slug = related_values[0]
        _validate_slug(related_slug)
        related = resolve_category(root, f"{category}:{related_slug}")
        entry.source_paths.append(related)
        progressive.append(
            f"[{field_name}]({_relative_link(_work_items_root(root), related)})"
        )
    progressive.append(f"[work item]({_relative_link(_work_items_root(root), status_path)})")
    suffix = " → ".join(progressive)
    entry.detail = " — ".join(part for part in (entry.detail, suffix) if part)
    return entry


def _legacy_retirement_entry(item: Path, metadata: Path) -> ReadmeEntry:
    try:
        payload = json.loads(metadata.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LifecycleError(
            "WI-LEGACY-RETIREMENT-INVALID",
            f"invalid legacy retirement metadata: {metadata}",
        ) from exc
    expected_scalars = {
        "schemaVersion": LEGACY_RETIREMENT_SCHEMA_VERSION,
        "owner": LEGACY_RETIREMENT_OWNER,
        "kind": "legacy-backlog-retirement",
        "slug": item.name,
        "status": "rejected-before-admission",
        "admissionHistory": "never-admitted",
    }
    if not isinstance(payload, dict) or any(
        payload.get(key) != value for key, value in expected_scalars.items()
    ):
        raise LifecycleError(
            "WI-LEGACY-RETIREMENT-INVALID",
            f"legacy retirement identity differs: {item}",
        )
    terminal_at = payload.get("terminalAt")
    if not isinstance(terminal_at, str):
        raise LifecycleError(
            "WI-LEGACY-RETIREMENT-INVALID", f"missing terminalAt: {metadata}"
        )
    _strict_utc(terminal_at)
    if archive_month(terminal_at) != item.parent.name:
        raise LifecycleError(
            "WI-CATEGORY-ARCHIVE-MONTH-MISMATCH",
            f"{item.name} belongs in archive/{archive_month(terminal_at)}",
        )
    disposition = payload.get("productDisposition")
    if not isinstance(disposition, str) or not disposition.strip():
        raise LifecycleError(
            "WI-LEGACY-RETIREMENT-INVALID",
            f"missing product disposition: {metadata}",
        )
    if payload.get("syntheticTransitions") != []:
        raise LifecycleError(
            "WI-LEGACY-RETIREMENT-INVALID",
            f"legacy retirement must not synthesize lifecycle transitions: {metadata}",
        )
    incoming = payload.get("incomingLinks")
    try:
        _validate_incoming_link_snapshot(f"work-item:{item.name}", incoming, label="stored")
    except LifecycleError as exc:
        raise LifecycleError(
            "WI-LEGACY-RETIREMENT-INVALID",
            f"invalid incoming-link inventory: {metadata}",
        ) from exc
    rows = payload.get("sourceFiles")
    if not isinstance(rows, list) or not rows:
        raise LifecycleError(
            "WI-LEGACY-RETIREMENT-INVALID", f"missing source file inventory: {metadata}"
        )
    sources: list[Path] = [metadata]
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise LifecycleError(
                "WI-LEGACY-RETIREMENT-INVALID", f"invalid source row: {metadata}"
            )
        relative = row.get("path")
        if not isinstance(relative, str) or relative in seen:
            raise LifecycleError(
                "WI-LEGACY-RETIREMENT-INVALID", f"duplicate source path: {metadata}"
            )
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts or relative == LEGACY_RETIREMENT_FILE:
            raise LifecycleError(
                "WI-LEGACY-RETIREMENT-INVALID", f"unsafe source path: {relative!r}"
            )
        source = item / candidate
        if source.is_symlink() or not source.is_file():
            raise LifecycleError(
                "WI-LEGACY-RETIREMENT-INVALID", f"missing source payload: {relative}"
            )
        data = source.read_bytes()
        if (
            row.get("byteLength") != len(data)
            or row.get("sha256") != hashlib.sha256(data).hexdigest()
        ):
            raise LifecycleError(
                "WI-LEGACY-RETIREMENT-INVALID", f"source digest differs: {relative}"
            )
        seen.add(relative)
        sources.append(source)
    actual = {
        path.relative_to(item).as_posix()
        for path in item.rglob("*")
        if path.is_file() and path != metadata
    }
    if actual != seen:
        raise LifecycleError(
            "WI-LEGACY-RETIREMENT-INVALID",
            f"source inventory does not cover the retirement payload: {item}",
        )
    # Retirement is immutable, but its former backlog paths must not remain in
    # mutable records.  The stored inventory is evidence from the transition;
    # this fresh owner-level scan catches a later plain-text citation that the
    # original Markdown/link scanner could not see.  Archived consumers are
    # historical evidence and intentionally do not participate.
    work_items = item.parents[2]
    current_incoming = _incoming_link_result(
        work_items.parent,
        sources,
        f"work-item:{item.name}",
        literal_path_references=(
            f"{work_items.name}/backlog/{item.name}/{relative}"
            for relative in seen
        ),
        mutable_consumers_only=True,
        scan_markdown_links=False,
    )
    try:
        _validate_incoming_link_snapshot(
            f"work-item:{item.name}", current_incoming, label="current"
        )
    except LifecycleError as exc:
        raise LifecycleError(
            "WI-LEGACY-RETIREMENT-INVALID",
            f"mutable record retains a retired backlog path: {item}",
        ) from exc
    return ReadmeEntry(
        "Recently completed",
        f"work-item:{item.name}",
        f"Rejected before admission: {item.name}",
        metadata,
        True,
        disposition.strip().splitlines()[0],
        sources,
        "WI-LEGACY-RETIRED-BEFORE-ADMISSION",
    )


def _archived_work_item_entry(item: Path) -> ReadmeEntry:
    retirement = item / LEGACY_RETIREMENT_FILE
    if retirement.is_file():
        if (item / "status.md").exists() or (item / "closure.md").exists():
            raise LifecycleError(
                "WI-LEGACY-RETIREMENT-INVALID",
                f"direct legacy retirement must not carry active/closure history: {item}",
            )
        return _legacy_retirement_entry(item, retirement)
    closure = item / "closure.md"
    if not closure.is_file():
        raise LifecycleError(
            "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
            f"archived work-item lacks closure.md: {item}",
        )
    status = item / "status.md"
    closure_data = closure.read_bytes()
    status_data = status.read_bytes() if status.is_file() else b""
    closure_markers = _schema_marker_occurrences(closure_data, "closure.md")
    status_markers = _schema_marker_occurrences(status_data, "status.md")
    fields = _parse_fields(closure_data.decode("utf-8"))
    sources = [closure]
    if status.is_file():
        sources.append(status)

    if not closure_markers and not status_markers:
        return ReadmeEntry(
            "Recently completed",
            f"work-item:{item.name}",
            fields.get("outcome") or item.name,
            closure,
            True,
            fields.get("residual risk", ""),
            sources,
            LEGACY_READ_CLASSIFICATION,
        )

    _require_canonical_schema_marker(status_markers, "status.md")
    _require_canonical_schema_marker(closure_markers, "closure.md")
    closed = fields.get("closed", "")
    _validate_closure(closure_data, closed)
    expected_month = archive_month(closed)
    if expected_month != item.parent.name:
        raise LifecycleError(
            "WI-CATEGORY-ARCHIVE-MONTH-MISMATCH",
            f"{item.name} belongs in archive/{expected_month}, not {item.parent.name}",
        )
    status_fields = _parse_fields(status_data.decode("utf-8"))
    status_value = status_fields.get("status", "")
    if status_value in CATEGORIES["work-item"].current_statuses:
        raise LifecycleError(
            "WI-CATEGORY-CURRENT-IN-ARCHIVE",
            f"work-item:{item.name} has current status in archive",
        )
    if status_value not in CATEGORIES["work-item"].terminal_statuses:
        raise LifecycleError(
            "WI-CATEGORY-STATUS-INVALID",
            f"work-item:{item.name} has invalid archived V1 status {status_value!r}",
        )
    return ReadmeEntry(
        "Recently completed",
        f"work-item:{item.name}",
        fields.get("outcome") or item.name,
        closure,
        True,
        fields.get("residual risk", ""),
        sources,
    )


def collect_readme_entries(root: Path) -> list[ReadmeEntry]:
    work_items = _work_items_root(root)
    entries: list[ReadmeEntry] = []

    backlog = work_items / "backlog"
    if backlog.is_dir():
        for path in sorted(backlog.glob("*.md")):
            fields = _parse_fields(path.read_text(encoding="utf-8"))
            status = fields.get("status")
            if status and status != "candidate":
                failure = (
                    "WI-CATEGORY-TERMINAL-IN-CURRENT"
                    if status in CATEGORIES["work-item"].terminal_statuses
                    else "WI-CATEGORY-STATUS-INVALID"
                )
                raise LifecycleError(
                    failure,
                    f"backlog work-item has invalid current status {status!r}: {path.stem}",
                )
            entries.append(
                ReadmeEntry(
                    "Next actions",
                    f"work-item:{path.stem}",
                    fields.get("task") or path.stem,
                    path,
                    False,
                    fields.get("next action", ""),
                    [path],
                )
            )

    active = work_items / "active"
    if active.is_dir():
        for item in sorted(path for path in active.iterdir() if path.is_dir()):
            entries.append(_status_entry(root, item))

    roadmaps = work_items / "roadmaps"
    if roadmaps.is_dir():
        for path in sorted(roadmaps.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            fields = _parse_fields(text)
            if fields.get("format") != "roadmap-v1":
                continue
            status = fields.get("status", "")
            if status not in {"draft", "active"}:
                raise LifecycleError(
                    "WI-CATEGORY-TERMINAL-IN-CURRENT",
                    f"terminal V1 roadmap remains current: {path.stem}",
                )
            entries.append(
                ReadmeEntry(
                    "Roadmap and milestones",
                    f"roadmap:{path.stem}",
                    fields.get("milestones-or-horizon") or path.stem,
                    path,
                    False,
                    fields.get("order", ""),
                    [path],
                )
            )

    archive = work_items / "archive"
    if archive.is_dir():
        archived: list[ReadmeEntry] = []
        for month in sorted((path for path in archive.iterdir() if path.is_dir()), reverse=True):
            for item in sorted((path for path in month.iterdir() if path.is_dir()), reverse=True):
                archived.append(_archived_work_item_entry(item))
        entries.extend(archived)

    seen: set[str] = set()
    for entry in entries:
        if entry.logical_reference in seen:
            raise LifecycleError(
                "WI-CATEGORY-DUAL-LOCATION",
                f"duplicate README logical reference: {entry.logical_reference}",
            )
        seen.add(entry.logical_reference)
    order = {section: index for index, section in enumerate(README_SECTIONS)}
    return sorted(entries, key=lambda entry: (order[entry.section], entry.logical_reference))


def _input_digest(entries: Iterable[ReadmeEntry], work_items: Path) -> str:
    inputs: dict[str, bytes] = {}
    for entry in entries:
        for path in entry.source_paths:
            logical_path = _relative_link(work_items, path)
            inputs[logical_path] = path.read_bytes()
    digest = hashlib.sha256()
    for logical_path, data in sorted(inputs.items()):
        encoded = logical_path.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def _canonical_timestamp(entries: Iterable[ReadmeEntry]) -> str:
    instants: list[str] = []
    for entry in entries:
        for path in entry.source_paths:
            if path.name == LEGACY_RETIREMENT_FILE:
                try:
                    value = json.loads(path.read_text(encoding="utf-8")).get("terminalAt")
                except (OSError, UnicodeError, json.JSONDecodeError, AttributeError) as exc:
                    raise LifecycleError(
                        "WI-LEGACY-RETIREMENT-INVALID",
                        f"cannot read terminal instant: {path}",
                    ) from exc
                if isinstance(value, str) and UTC_INSTANT_RE.fullmatch(value):
                    _strict_utc(value)
                    instants.append(value)
                continue
            fields = _parse_fields(path.read_text(encoding="utf-8"))
            for key in ("updated", "closed", "terminal-at"):
                value = fields.get(key)
                if value and UTC_INSTANT_RE.fullmatch(value):
                    _strict_utc(value)
                    instants.append(value)
    return max(instants, default="none")


def _default_static_guide() -> str:
    return (
        "# Work items\n\n"
        "Read this page for current delivery status. Make lifecycle changes through "
        "`scripts/mutate-work-item.py`, then follow the generated links for detail.\n\n"
    )


def _static_guide(readme: Path, *, allow_marker_bootstrap: bool = False) -> str:
    if not readme.exists():
        return _default_static_guide()
    text = readme.read_text(encoding="utf-8")
    begin_count = text.count(README_BEGIN)
    end_count = text.count(README_END)
    if allow_marker_bootstrap and begin_count == 0 and end_count == 0:
        return _default_static_guide()
    if begin_count != 1 or end_count != 1 or text.index(README_BEGIN) > text.index(README_END):
        raise LifecycleError(
            "WI-README-MARKERS",
            "existing README must contain exactly one ordered generated marker pair",
        )
    return text[: text.index(README_BEGIN)].rstrip() + "\n\n"


def render_readme_bytes(
    root: Path,
    *,
    allow_marker_bootstrap: bool = False,
    static_guide_override: str | None = None,
) -> bytes:
    work_items = _work_items_root(root)
    entries = collect_readme_entries(root)
    lines = [
        README_BEGIN,
        "Read-model: work-items-readme-v1",
        "Ordered sources: backlog|active|roadmaps|archive",
        f"Canonical changes through: {_canonical_timestamp(entries)}",
        f"Canonical input digest: sha256:{_input_digest(entries, work_items)}",
        "",
    ]
    by_section = {section: [] for section in README_SECTIONS}
    for entry in entries:
        by_section[entry.section].append(entry)
    for section in README_SECTIONS:
        lines.extend((f"## {section}", ""))
        for entry in by_section[section]:
            marker = "x" if entry.checked else " "
            link = _relative_link(work_items, entry.link)
            detail_parts = [
                part for part in (entry.detail, entry.classification) if part
            ]
            detail = f" — {' — '.join(detail_parts)}" if detail_parts else ""
            lines.append(f"- [{marker}] [{entry.label}]({link}){detail}")
        lines.append("")
    lines.append(README_END)
    static_guide = (
        static_guide_override
        if static_guide_override is not None
        else _static_guide(
            work_items / "README.md",
            allow_marker_bootstrap=allow_marker_bootstrap,
        )
    )
    return (
        static_guide
        + "\n".join(lines)
        + "\n"
    ).encode("utf-8")


def refresh_readme(root: Path, *, allow_marker_bootstrap: bool = False) -> str:
    work_items = _work_items_root(root)
    expected = render_readme_bytes(
        root,
        allow_marker_bootstrap=allow_marker_bootstrap,
    )
    readme = work_items / "README.md"
    _atomic_write(readme, expected)
    observed = render_readme_bytes(root)
    if observed != expected or readme.read_bytes() != expected:
        raise LifecycleError("WI-README-STALE", "README byte verification failed")
    return hashlib.sha256(expected).hexdigest()


def reset_readme_static_guide(root: Path, expected_readme_sha256: str) -> str:
    if not re.fullmatch(r"[0-9A-Fa-f]{64}", expected_readme_sha256):
        raise LifecycleError(
            "WI-README-REPAIR-TARGET-MISMATCH",
            "expected README SHA-256 must be exactly 64 hexadecimal characters",
        )
    work_items = _work_items_root(root)
    readme = work_items / "README.md"
    if not readme.is_file():
        raise LifecycleError(
            "WI-README-MARKERS",
            "static-guide repair requires an existing marker-owned README",
        )
    _static_guide(readme)
    current = readme.read_bytes()
    desired = render_readme_bytes(
        root,
        static_guide_override=_default_static_guide(),
    )
    current_hash = hashlib.sha256(current).hexdigest()
    expected_hash = expected_readme_sha256.casefold()
    if current_hash != expected_hash:
        if current == desired:
            return current_hash
        raise LifecycleError(
            "WI-README-REPAIR-TARGET-MISMATCH",
            "README bytes differ from the explicitly targeted repair input",
        )
    if current == desired:
        return current_hash
    _atomic_write(readme, desired)
    observed = render_readme_bytes(root)
    if observed != desired or readme.read_bytes() != desired:
        raise LifecycleError(
            "WI-README-STALE",
            "README static-guide repair failed complete-byte verification",
        )
    return hashlib.sha256(desired).hexdigest()


def check_readme(root: Path) -> None:
    readme = _work_items_root(root) / "README.md"
    if not readme.is_file() or readme.read_bytes() != render_readme_bytes(root):
        raise LifecycleError("WI-README-STALE", "README does not match canonical inputs")


def _preflight_readme(root: Path) -> None:
    """Validate current canonical inputs and README marker ownership before mutation."""

    render_readme_bytes(root)


def _preflight_readme_markers(root: Path) -> None:
    """Validate README ownership when the current tree is intentionally terminal."""

    _static_guide(_work_items_root(root) / "README.md")


def _validator_module():
    path = Path(__file__).with_name("validate-work-item-state.py")
    spec = importlib.util.spec_from_file_location("work_item_state_validator", path)
    if spec is None or spec.loader is None:
        raise LifecycleError("WI-VALIDATOR-LOAD", f"cannot load validator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _agent_run_ledger_module():
    path = Path(__file__).with_name("agent-run-ledger.py")
    try:
        spec = importlib.util.spec_from_file_location("agent_run_ledger", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"no import specification or loader for {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as exc:
        raise LifecycleError(
            "WI-LEDGER-BOOTSTRAP-INVALID",
            f"cannot load ledger helper {path}: {exc}",
        ) from exc


def _staged_admission_ledger_bytes(slug: str, status_data: bytes) -> bytes:
    """Build the settled Lead admission event from the already-validated status."""

    started_at = _parse_fields(status_data.decode("utf-8"))["started"]
    ledger = _agent_run_ledger_module()
    args = argparse.Namespace(
        work_item=Path(slug),
        run_id=f"{slug}-lifecycle-start",
        work_item_name=slug,
        role="lead",
        execution_role="main",
        assigned_role=None,
        provider=None,
        model=None,
        status="completed",
        gate="none",
        scope=["candidate -> active lifecycle admission"],
        prompt_file=None,
        artifact=None,
        evidence=None,
        evidence_json=None,
        started_at=started_at,
        updated_at=started_at,
        notes=None,
        event_kind="standalone",
        launch_run_id=None,
        closes=None,
        artifact_revision=None,
        lane=None,
        effort=None,
        finding_class=None,
    )
    try:
        event = ledger.build_event(args)
        return (ledger.serialize_event(event) + "\n").encode("utf-8")
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise LifecycleError("WI-LEDGER-BOOTSTRAP-INVALID", str(exc)) from exc


def _validate_active_status_bytes(data: bytes) -> None:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LifecycleError("WI-CATEGORY-STATUS-INVALID", "status must be UTF-8") from exc
    fields = _parse_fields(text)
    if fields.get("status") not in {"active", "blocked"}:
        raise LifecycleError(
            "WI-CATEGORY-STATUS-INVALID", "active status must be active or blocked"
        )
    template = fields.get("template")
    if template == "quick-fix":
        errors: list[str] = []
        _validator_module().validate_quick_fix_status(text, errors)
        if errors:
            raise LifecycleError("WI-CATEGORY-STATUS-INVALID", "; ".join(errors))
        return
    if template != "staged":
        raise LifecycleError(
            "WI-CATEGORY-STATUS-INVALID", "V1 status template must be quick-fix or staged"
        )
    required = {
        "started",
        "updated",
        "task",
        "current step",
        "last result",
        "next action",
        "scope boundary",
        "owner",
        "integration owner",
        "evidence gate",
    }
    missing = sorted(required - set(fields))
    if missing:
        raise LifecycleError(
            "WI-CATEGORY-STATUS-INVALID", f"staged status missing fields: {', '.join(missing)}"
        )
    for slug in _optional_relation_values(
        fields.get("depends-on"),
        comma_separated=True,
    ):
        if ":" in slug:
            raise LifecycleError(
                "WI-DEPENDENCY-NON-WORK-ITEM",
                "Depends-on accepts bare work-item slugs only",
            )
        _validate_slug(slug)


def create_candidate(root: Path, slug: str, data: bytes, *, inject_readme_failure: bool = False) -> Path:
    _validate_slug(slug)
    work_items = _work_items_root(root)
    if _category_locations(root, CATEGORIES["work-item"], slug):
        raise LifecycleError("WI-CATEGORY-DUAL-LOCATION", f"slug already exists: {slug}")
    _preflight_readme(root)
    target = work_items / "backlog" / f"{slug}.md"
    _atomic_write(target, data)
    if inject_readme_failure:
        raise LifecycleError("WI-README-STALE", "injected failure after canonical success")
    try:
        refresh_readme(root)
    except LifecycleError as exc:
        if exc.failure_id == "WI-README-STALE":
            raise
        raise LifecycleError("WI-README-STALE", str(exc)) from exc
    return target


def _legacy_backlog_source(root: Path, slug: str) -> Path:
    _validate_slug(slug)
    locations = _category_locations(root, CATEGORIES["work-item"], slug)
    if locations:
        raise LifecycleError(
            "WI-CATEGORY-DUAL-LOCATION", f"canonical work-item identity already exists: {slug}"
        )
    source = _work_items_root(root) / "backlog" / slug
    if source.is_symlink() or not source.is_dir():
        raise LifecycleError(
            "WI-INVALID-TARGET", f"legacy backlog folder is missing: {slug}"
        )
    return source


def _legacy_source_rows(source: Path) -> list[tuple[str, bytes, str]]:
    rows: list[tuple[str, bytes, str]] = []
    for path in sorted(source.rglob("*"), key=lambda item: item.relative_to(source).as_posix()):
        if path.is_symlink():
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-PAYLOAD", f"symbolic-link source is not admitted: {path}"
            )
        if path.is_dir():
            continue
        if not path.is_file():
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-PAYLOAD", f"unsupported legacy source: {path}"
            )
        relative = path.relative_to(source).as_posix()
        if relative == LEGACY_RETIREMENT_FILE:
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-PAYLOAD",
                f"legacy source uses reserved owner metadata name: {relative}",
            )
        data = path.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-PAYLOAD", f"legacy source is not UTF-8 text: {path}"
            ) from exc
        rows.append((relative, data, text))
    if not rows:
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-PAYLOAD", f"legacy backlog folder is empty: {source}"
        )
    return rows


def _candidate_with_legacy_appendices(
    candidate_data: bytes,
    rows: Iterable[tuple[str, bytes, str]],
) -> bytes:
    try:
        candidate_data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-PAYLOAD", "candidate input must be UTF-8 text"
        ) from exc
    result = bytearray(candidate_data)
    if not result.endswith(b"\n"):
        result.extend(b"\n")
    result.extend(b"\n## Preserved legacy source appendices\n")
    for relative, data, text in rows:
        longest = max((len(match.group(0)) for match in re.finditer(r"`+", text)), default=0)
        fence = "`" * max(3, longest + 1)
        header = (
            f"\n### `{relative}`\n\n"
            f"Source SHA-256: `{hashlib.sha256(data).hexdigest()}`\n\n"
            f"Source byte length: `{len(data)}`\n\n"
            f"{fence}markdown\n"
        ).encode("utf-8")
        result.extend(header)
        result.extend(data)
        if not data.endswith(b"\n"):
            result.extend(b"\n")
        result.extend(f"{fence}\n".encode("utf-8"))
    return bytes(result)


def _restore_readme_snapshot(readme: Path, before: bytes | None) -> None:
    if before is None:
        readme.unlink(missing_ok=True)
    else:
        _atomic_write(readme, before)


def _preflight_legacy_transition_admission(
    root: Path,
    source: Path,
    reference: str,
) -> dict:
    """Reject a legacy transition before it can orphan a physical consumer."""
    incoming = _incoming_link_result(root, {source}, reference)
    _validate_incoming_link_snapshot(reference, incoming, label="legacy transition")
    return incoming


def _legacy_cleanup_metadata(
    slug: str,
    target: Path,
    transaction: Path,
    converted: bytes,
    rows: Iterable[tuple[str, bytes, str]],
) -> bytes:
    payload = {
        "schemaVersion": LEGACY_CLEANUP_SCHEMA_VERSION,
        "owner": LEGACY_CLEANUP_OWNER,
        "slug": slug,
        "transactionId": transaction.name,
        "canonicalTarget": f"{target.parent.name}/{target.name}",
        "candidateSha256": hashlib.sha256(converted).hexdigest(),
        "sourceFiles": [
            {
                "path": relative,
                "byteLength": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
            for relative, data, _text in rows
        ],
    }
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _legacy_cleanup_sidecar(backlog: Path, transaction_id: str) -> Path:
    return backlog / f".legacy-candidate-cleanup.{transaction_id.removeprefix('.')}.json"


def _validated_legacy_cleanup_residue(
    backlog: Path, slug: str, target: Path
) -> tuple[Path | None, Path, str]:
    prefix = f".{slug}.legacy-candidate."
    parent = backlog.resolve()
    residues = sorted(path for path in backlog.glob(f"{prefix}*") if path.name.startswith(prefix))
    if len(residues) > 1:
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"committed cleanup requires exactly one owned residue for {slug}, found {len(residues)}",
        )
    residue = residues[0] if residues else None
    if residue is not None and (
        residue.is_symlink() or not residue.is_dir() or residue.resolve().parent != parent
    ):
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"unsafe committed-cleanup residue for {slug}: {residue}",
        )
    sidecar_prefix = f".legacy-candidate-cleanup.{slug}.legacy-candidate."
    sidecars = sorted(backlog.glob(f"{sidecar_prefix}*.json"))
    markers = list(sidecars)
    if residue is not None:
        embedded_marker = residue / LEGACY_CLEANUP_FILE
        if embedded_marker.exists() or embedded_marker.is_symlink():
            markers.append(embedded_marker)
    if len(markers) != 1:
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"committed cleanup requires exactly one owner marker for {slug}, found {len(markers)}",
        )
    marker = markers[0]
    if marker.is_symlink() or not marker.is_file() or marker.resolve().parent not in {parent, residue}:
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"unsafe owner cleanup marker for {slug}: {marker}",
        )
    if marker.parent == backlog:
        transaction_id = "." + marker.name.removeprefix(".legacy-candidate-cleanup.").removesuffix(
            ".json"
        )
    elif residue is not None and marker.parent == residue:
        transaction_id = residue.name
    else:
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"owner cleanup marker has no transaction parent for {slug}: {marker}",
        )
    if not transaction_id.startswith(prefix) or (residue is not None and transaction_id != residue.name):
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"owner cleanup marker transaction differs from residue for {slug}: {marker}",
        )
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"invalid owner cleanup marker for {slug}: {marker}",
        ) from exc
    expected = {
        "schemaVersion": LEGACY_CLEANUP_SCHEMA_VERSION,
        "owner": LEGACY_CLEANUP_OWNER,
        "slug": slug,
        "transactionId": transaction_id,
        "canonicalTarget": f"{target.parent.name}/{target.name}",
        "candidateSha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    }
    if not isinstance(payload, dict) or any(payload.get(key) != value for key, value in expected.items()):
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"owner cleanup marker differs from committed candidate for {slug}",
        )
    candidate_text = target.read_text(encoding="utf-8")
    rows = payload.get("sourceFiles")
    if not isinstance(rows, list) or not rows:
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"owner cleanup marker has no source inventory for {slug}",
        )
    expected_files: dict[str, tuple[int, str]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise LifecycleError(
                "WI-LEGACY-CLEANUP-REPLAY-INVALID",
                f"owner cleanup marker has invalid source row for {slug}",
            )
        relative = row["path"]
        candidate = Path(relative)
        byte_length = row.get("byteLength")
        digest = row.get("sha256")
        if (
            candidate.is_absolute()
            or ".." in candidate.parts
            or not relative
            or relative in expected_files
            or not isinstance(byte_length, int)
            or byte_length < 0
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
        ):
            raise LifecycleError(
                "WI-LEGACY-CLEANUP-REPLAY-INVALID",
                f"owner cleanup marker source inventory is invalid for {slug}",
            )
        expected_files[relative] = (byte_length, digest)
        source_identity = (
            f"### `{relative}`\n\n"
            f"Source SHA-256: `{digest}`\n\n"
            f"Source byte length: `{byte_length}`\n\n"
        )
        if source_identity not in candidate_text:
            raise LifecycleError(
                "WI-LEGACY-CLEANUP-REPLAY-INVALID",
                f"owner cleanup marker source identity is not committed for {slug}: {relative}",
            )
    source_root = residue / "source" if residue is not None else None
    actual_files: set[str] = set()
    if residue is not None:
        for path in residue.rglob("*"):
            if path.is_symlink() or not (path.is_dir() or path.is_file()):
                raise LifecycleError(
                    "WI-LEGACY-CLEANUP-REPLAY-INVALID",
                    f"owner cleanup residue contains unsafe path for {slug}: {path}",
                )
            if path == marker:
                continue
            try:
                relative = path.relative_to(source_root).as_posix()
            except ValueError as exc:
                raise LifecycleError(
                    "WI-LEGACY-CLEANUP-REPLAY-INVALID",
                    f"owner cleanup residue contains unowned path for {slug}: {path}",
                ) from exc
            if path.is_dir():
                continue
            expected_file = expected_files.get(relative)
            data = path.read_bytes()
            if expected_file is None or expected_file != (len(data), hashlib.sha256(data).hexdigest()):
                raise LifecycleError(
                    "WI-LEGACY-CLEANUP-REPLAY-INVALID",
                    f"owner cleanup residue source differs for {slug}: {relative}",
                )
            actual_files.add(relative)
    if not actual_files <= expected_files.keys():
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"owner cleanup residue has unowned files for {slug}",
        )
    return residue, marker, transaction_id


def _finish_committed_legacy_cleanup(
    backlog: Path,
    residue: Path | None,
    marker: Path,
    transaction_id: str,
) -> None:
    if residue is not None:
        source = residue / "source"
        if source.exists():
            shutil.rmtree(source)
        sidecar = _legacy_cleanup_sidecar(backlog, transaction_id)
        if marker.parent == residue:
            os.replace(marker, sidecar)
            marker = sidecar
        residue.rmdir()
    marker.unlink()


def _committed_cleanup_failure(target: Path, residue: Path, cause: BaseException) -> LifecycleError:
    return LifecycleError(
        "WI-LEGACY-CLEANUP-AFTER-COMMIT",
        f"state=committed target={target} residue={residue}: {cause}",
    )


def _replay_legacy_candidate_cleanup(root: Path, slug: str, candidate_data: bytes) -> Path | None:
    """Remove exactly one safe residue without replaying a committed conversion."""

    work_items = _work_items_root(root)
    backlog = work_items / "backlog"
    source = backlog / slug
    target = backlog / f"{slug}.md"
    if source.exists() or not target.is_file():
        return None
    canonical = _category_locations(root, CATEGORIES["work-item"], slug)
    if canonical != [target]:
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"committed cleanup has ambiguous canonical identity for {slug}",
        )
    candidate_prefix = candidate_data if candidate_data.endswith(b"\n") else candidate_data + b"\n"
    if not target.read_bytes().startswith(candidate_prefix + b"\n## Preserved legacy source appendices\n"):
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"committed cleanup target does not match requested conversion input: {target}",
        )
    check_readme(root)
    residue, marker, transaction_id = _validated_legacy_cleanup_residue(backlog, slug, target)
    target_before = target.read_bytes()
    readme = work_items / "README.md"
    readme_before = readme.read_bytes()
    try:
        _finish_committed_legacy_cleanup(backlog, residue, marker, transaction_id)
    except OSError as exc:
        raise _committed_cleanup_failure(target, residue, exc) from exc
    if (residue is not None and residue.exists()) or marker.exists() or target.read_bytes() != target_before or readme.read_bytes() != readme_before:
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"committed cleanup replay changed canonical state for {slug}",
        )
    return target


def convert_legacy_candidate(
    root: Path,
    slug: str,
    candidate_data: bytes,
    *,
    inject_readme_failure: bool = False,
) -> Path:
    _validate_slug(slug)
    replay = _replay_legacy_candidate_cleanup(root, slug, candidate_data)
    if replay is not None:
        return replay
    source = _legacy_backlog_source(root, slug)
    _preflight_legacy_transition_admission(root, source, f"work-item:{slug}")
    rows = _legacy_source_rows(source)
    _validate_canonical_candidate_header(candidate_data)
    converted = _candidate_with_legacy_appendices(candidate_data, rows)
    _preflight_readme(root)
    work_items = _work_items_root(root)
    readme = work_items / "README.md"
    readme_before = readme.read_bytes() if readme.is_file() else None
    target = work_items / "backlog" / f"{slug}.md"
    transaction = Path(tempfile.mkdtemp(prefix=f".{slug}.legacy-candidate.", dir=target.parent))
    staged_source = transaction / "source"
    staged_candidate = transaction / target.name
    cleanup_marker = transaction / LEGACY_CLEANUP_FILE
    committed = False
    try:
        _atomic_write(staged_candidate, converted)
        _atomic_write(
            cleanup_marker,
            _legacy_cleanup_metadata(slug, target, transaction, converted, rows),
        )
        os.replace(source, staged_source)
        os.replace(staged_candidate, target)
        if inject_readme_failure:
            raise LifecycleError("WI-README-STALE", "injected legacy conversion failure")
        refresh_readme(root)
        if source.exists() or target.read_bytes() != converted:
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-PAYLOAD", "legacy candidate byte verification failed"
            )
        check_readme(root)
        # The flat candidate, regenerated read-model, and byte check form the
        # irreversible commit point. Its appendices carry every staged legacy
        # byte, so disposal of the no-longer-authoritative transaction copy
        # cannot roll this committed transition back.
        committed = True
        try:
            _finish_committed_legacy_cleanup(target.parent, transaction, cleanup_marker, transaction.name)
        except OSError as exc:
            raise _committed_cleanup_failure(target, transaction, exc) from exc
    except BaseException:
        if not committed:
            if target.exists():
                target.unlink()
            if staged_source.exists() and not source.exists():
                os.replace(staged_source, source)
            _restore_readme_snapshot(readme, readme_before)
            if staged_candidate.exists():
                staged_candidate.unlink()
            cleanup_marker.unlink(missing_ok=True)
            transaction.rmdir()
        raise
    return target


def retire_legacy_backlog(
    root: Path,
    slug: str,
    disposition_data: bytes,
    terminal_instant: str,
    *,
    inject_readme_failure: bool = False,
) -> Path:
    source = _legacy_backlog_source(root, slug)
    reference = f"work-item:{slug}"
    incoming = _preflight_legacy_transition_admission(root, source, reference)
    rows = _legacy_source_rows(source)
    try:
        disposition = disposition_data.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise LifecycleError(
            "WI-LEGACY-RETIREMENT-INVALID", "product disposition must be UTF-8 text"
        ) from exc
    if not disposition:
        raise LifecycleError(
            "WI-LEGACY-RETIREMENT-INVALID", "product disposition must not be empty"
        )
    month = archive_month(terminal_instant)
    _preflight_readme(root)
    work_items = _work_items_root(root)
    metadata_payload = {
        "schemaVersion": LEGACY_RETIREMENT_SCHEMA_VERSION,
        "owner": LEGACY_RETIREMENT_OWNER,
        "kind": "legacy-backlog-retirement",
        "slug": slug,
        "status": "rejected-before-admission",
        "terminalAt": terminal_instant,
        "productDisposition": disposition,
        "admissionHistory": "never-admitted",
        "syntheticTransitions": [],
        "sourceFiles": [
            {
                "path": relative,
                "byteLength": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
            for relative, data, _text in rows
        ],
        "incomingLinks": incoming,
    }
    metadata_data = (
        json.dumps(metadata_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    readme = work_items / "README.md"
    readme_before = readme.read_bytes() if readme.is_file() else None
    archive = work_items / "archive"
    month_dir = archive / month
    target = month_dir / slug
    if target.exists():
        raise LifecycleError("WI-CATEGORY-DUAL-LOCATION", f"archive target exists: {target}")
    transaction = Path(tempfile.mkdtemp(prefix=f".{slug}.legacy-retire.", dir=source.parent))
    staged_source = transaction / "source"
    created_archive = not archive.exists()
    created_month = not month_dir.exists()
    try:
        os.replace(source, staged_source)
        _atomic_write(staged_source / LEGACY_RETIREMENT_FILE, metadata_data)
        month_dir.mkdir(parents=True, exist_ok=True)
        os.replace(staged_source, target)
        if inject_readme_failure:
            raise LifecycleError("WI-README-STALE", "injected legacy retirement failure")
        refresh_readme(root)
        _legacy_retirement_entry(target, target / LEGACY_RETIREMENT_FILE)
    except BaseException:
        if target.exists() and not staged_source.exists():
            os.replace(target, staged_source)
        (staged_source / LEGACY_RETIREMENT_FILE).unlink(missing_ok=True)
        if staged_source.exists() and not source.exists():
            os.replace(staged_source, source)
        _restore_readme_snapshot(readme, readme_before)
        if created_month and month_dir.is_dir() and not any(month_dir.iterdir()):
            month_dir.rmdir()
        if created_archive and archive.is_dir() and not any(archive.iterdir()):
            archive.rmdir()
        raise
    finally:
        shutil.rmtree(transaction, ignore_errors=True)
    return target


def start_item(root: Path, slug: str, status_data: bytes, *, inject_readme_failure: bool = False) -> Path:
    _validate_slug(slug)
    _validate_active_status_bytes(status_data)
    is_staged = _parse_fields(status_data.decode("utf-8")).get("template") == "staged"
    admission_ledger = _staged_admission_ledger_bytes(slug, status_data) if is_staged else None
    work_items = _work_items_root(root)
    locations = _category_locations(root, CATEGORIES["work-item"], slug)
    backlog = work_items / "backlog" / f"{slug}.md"
    if locations != [backlog]:
        failure = "WI-CATEGORY-DUAL-LOCATION" if len(locations) > 1 else "WI-INVALID-TARGET"
        raise LifecycleError(failure, f"start requires exactly one backlog candidate: {slug}")
    _preflight_readme(root)
    active_parent = work_items / "active"
    active_parent.mkdir(parents=True, exist_ok=True)
    target = active_parent / slug
    temp = Path(tempfile.mkdtemp(prefix=f".{slug}.", dir=active_parent))
    moved_candidate = temp / "admission.md"
    committed = False
    try:
        os.replace(backlog, moved_candidate)
        _atomic_write(temp / "status.md", status_data)
        if admission_ledger is not None:
            _atomic_write(temp / "agent-runs.jsonl", admission_ledger)
            errors = _validator_module().validate_work_item(temp)
            if errors:
                raise LifecycleError("WI-LEDGER-BOOTSTRAP-INVALID", "; ".join(errors))
        os.replace(temp, target)
        committed = True
    finally:
        if not committed:
            if moved_candidate.exists() and not backlog.exists():
                backlog.parent.mkdir(parents=True, exist_ok=True)
                os.replace(moved_candidate, backlog)
            shutil.rmtree(temp, ignore_errors=True)
    if inject_readme_failure:
        raise LifecycleError("WI-README-STALE", "injected failure after canonical success")
    try:
        refresh_readme(root)
    except LifecycleError as exc:
        raise LifecycleError("WI-README-STALE", str(exc)) from exc
    return target


def update_status(root: Path, slug: str, status_data: bytes, *, inject_readme_failure: bool = False) -> Path:
    _validate_active_status_bytes(status_data)
    target = resolve_category(root, f"work-item:{slug}")
    if target.parent.name != "active" or not target.is_dir():
        raise LifecycleError("WI-INVALID-TARGET", "status update requires an active work-item")
    _preflight_readme(root)
    status = target / "status.md"
    _atomic_write(status, status_data)
    if inject_readme_failure:
        raise LifecycleError("WI-README-STALE", "injected failure after canonical success")
    try:
        refresh_readme(root)
    except LifecycleError as exc:
        raise LifecycleError("WI-README-STALE", str(exc)) from exc
    return status


def _validate_closure(data: bytes, terminal_instant: str) -> None:
    try:
        fields = _parse_fields(data.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise LifecycleError("WI-CATEGORY-TERMINAL-EVIDENCE-MISSING", "closure must be UTF-8") from exc
    required = {"closed", "outcome", "evidence", "residual risk"}
    missing = sorted(key for key in required if not fields.get(key))
    if missing:
        raise LifecycleError(
            "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
            f"closure missing fields: {', '.join(missing)}",
        )
    if fields["closed"] != terminal_instant:
        raise LifecycleError(
            "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
            "closure Closed does not match requested terminal instant",
        )
    _strict_utc(fields["closed"])


def _terminalize_status(data: bytes) -> bytes:
    if _schema_marker_occurrences(data, "status.md"):
        raise LifecycleError(
            "WI-CATEGORY-SCHEMA-INVALID",
            "active status must not contain a lifecycle schema marker",
        )
    text = data.decode("utf-8")
    replaced, count = re.subn(
        r"(?im)^(\s*status\s*:\s*)(active|blocked)\s*$",
        r"\1completed",
        text,
        count=1,
    )
    if count != 1:
        raise LifecycleError(
            "WI-CATEGORY-STATUS-INVALID",
            "active V1 status has no single active/blocked status field",
        )
    return _stamp_schema_marker(replaced.encode("utf-8"), "status.md")


def _validate_item_before_close(item: Path) -> None:
    validator = _validator_module()
    ledger = item / "agent-runs.jsonl"
    status_text = (item / "status.md").read_text(encoding="utf-8")
    v1_staged = _parse_fields(status_text).get("template") == "staged"
    if ledger.exists():
        errors = validator.validate_work_item(
            item,
            validate_status_file=not v1_staged,
        )
        if v1_staged:
            _validate_active_status_bytes(status_text.encode("utf-8"))
    else:
        errors = []
        validator.validate_status(item, [], errors)
        if v1_staged:
            errors = []
            _validate_active_status_bytes(status_text.encode("utf-8"))
    if errors:
        raise LifecycleError("WI-LEDGER-UNSETTLED", "; ".join(errors))


def close_item(
    root: Path,
    slug: str,
    closure_data: bytes,
    terminal_instant: str,
    *,
    inject_readme_failure: bool = False,
) -> Path:
    _validate_slug(slug)
    month = archive_month(terminal_instant)
    _validate_closure(closure_data, terminal_instant)
    archived_closure_data = _stamp_schema_marker(closure_data, "closure.md")
    work_items = _work_items_root(root)
    locations = _category_locations(root, CATEGORIES["work-item"], slug)
    if len(locations) > 1:
        raise LifecycleError("WI-CATEGORY-DUAL-LOCATION", f"duplicate slug: {slug}")
    if len(locations) == 1 and "archive" in locations[0].parts:
        archived = locations[0]
        _archived_work_item_entry(archived)
        existing = archived / "closure.md"
        if (
            not existing.is_file()
            or existing.read_bytes() != archived_closure_data
            or archived.parent.name != month
        ):
            raise LifecycleError("WI-IMMUTABLE-ARCHIVE", f"archived identity differs: {slug}")
        if inject_readme_failure:
            raise LifecycleError("WI-README-STALE", "injected failure after canonical success")
        refresh_readme(root)
        return archived
    active = work_items / "active" / slug
    if locations != [active]:
        raise LifecycleError("WI-INVALID-TARGET", f"close requires one active item: {slug}")
    _validate_item_before_close(active)
    _preflight_readme(root)
    closure_path = active / "closure.md"
    prior_closure = closure_path.read_bytes() if closure_path.exists() else None
    status_path = active / "status.md"
    prior_status = status_path.read_bytes()
    _atomic_write(closure_path, archived_closure_data)
    _atomic_write(status_path, _terminalize_status(prior_status))
    target = work_items / "archive" / month / slug
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.replace(active, target)
    except BaseException:
        if prior_closure is None:
            try:
                closure_path.unlink()
            except FileNotFoundError:
                pass
        else:
            _atomic_write(closure_path, prior_closure)
        _atomic_write(status_path, prior_status)
        raise
    if inject_readme_failure:
        raise LifecycleError("WI-README-STALE", "injected failure after canonical success")
    try:
        refresh_readme(root)
    except LifecycleError as exc:
        raise LifecycleError("WI-README-STALE", str(exc)) from exc
    return target


def reopen_item(
    root: Path,
    archived_slug: str,
    successor_slug: str,
    status_data: bytes,
    *,
    inject_readme_failure: bool = False,
) -> Path:
    archived = resolve_category(root, f"work-item:{archived_slug}")
    if "archive" not in archived.parts:
        raise LifecycleError("WI-INVALID-TARGET", "reopen source must be archived")
    _validate_slug(successor_slug)
    _validate_active_status_bytes(status_data)
    fields = _parse_fields(status_data.decode("utf-8"))
    if fields.get("reopens") != archived_slug:
        raise LifecycleError(
            "WI-CATEGORY-STATUS-INVALID",
            f"successor must declare Reopens: {archived_slug}",
        )
    if _category_locations(root, CATEGORIES["work-item"], successor_slug):
        raise LifecycleError("WI-CATEGORY-DUAL-LOCATION", "successor slug already exists")
    _preflight_readme(root)
    active_parent = _work_items_root(root) / "active"
    active_parent.mkdir(parents=True, exist_ok=True)
    target = active_parent / successor_slug
    temp = Path(tempfile.mkdtemp(prefix=f".{successor_slug}.", dir=active_parent))
    committed = False
    try:
        _atomic_write(temp / "status.md", status_data)
        os.replace(temp, target)
        committed = True
    finally:
        if not committed:
            shutil.rmtree(temp, ignore_errors=True)
    if inject_readme_failure:
        raise LifecycleError("WI-README-STALE", "injected failure after canonical success")
    try:
        refresh_readme(root)
    except LifecycleError as exc:
        raise LifecycleError("WI-README-STALE", str(exc)) from exc
    return target


def audit_categories(root: Path) -> tuple[str, ...]:
    work_items = _work_items_root(root)
    allowed_roots = {"backlog", "active", "archive"}
    allowed_roots.update(
        category.current_root
        for category in CATEGORIES.values()
        if category.current_kind == "flat"
    )
    if work_items.is_dir():
        unknown_roots = sorted(
            path.name
            for path in work_items.iterdir()
            if path.is_dir() and path.name not in allowed_roots
        )
        if unknown_roots:
            noun = "directory" if len(unknown_roots) == 1 else "directories"
            raise LifecycleError(
                "WI-CATEGORY-UNKNOWN-ROOT",
                f"unknown top-level work-items {noun}: " + ", ".join(unknown_roots),
            )
    legacy_read_compatible: list[str] = []
    for category in CATEGORIES.values():
        slugs: set[str] = set()
        if category.current_kind == "work-item":
            slugs.update(path.stem for path in (work_items / "backlog").glob("*.md"))
            slugs.update(path.name for path in (work_items / "active").glob("*") if path.is_dir())
            archive = work_items / "archive"
        else:
            current = work_items / category.current_root
            slugs.update(path.stem for path in current.glob("*.md"))
            archive = current / "archive"
        if archive.is_dir():
            for month in archive.iterdir():
                if not month.is_dir():
                    continue
                if category.current_kind == "work-item":
                    slugs.update(path.name for path in month.iterdir() if path.is_dir())
                else:
                    slugs.update(path.stem for path in month.glob("*.md"))
        for slug in slugs:
            locations = _category_locations(root, category, slug)
            if len(locations) > 1:
                raise LifecycleError(
                    "WI-CATEGORY-DUAL-LOCATION",
                    f"{category.name}:{slug} has {len(locations)} locations",
                )
            if not is_valid_slug(slug):
                if len(locations) != 1 or "archive" not in locations[0].parts:
                    _validate_slug(slug)
                legacy = locations[0]
                if category.name == "work-item":
                    entry = _archived_work_item_entry(legacy)
                    if entry.classification == LEGACY_READ_CLASSIFICATION:
                        fields = _parse_fields((legacy / "closure.md").read_text(encoding="utf-8"))
                        closed = fields.get("closed", "")
                        if not closed or not fields.get("outcome"):
                            raise LifecycleError(
                                "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
                                f"legacy archive lacks terminal evidence: {legacy}",
                            )
                        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", closed) or closed[:7] != legacy.parent.name:
                            raise LifecycleError(
                                "WI-CATEGORY-ARCHIVE-MONTH-MISMATCH",
                                f"{category.name}:{slug} does not match archive month",
                            )
                else:
                    instant = _validate_flat_terminal(category, legacy.read_bytes())
                    if legacy.parent.name != archive_month(instant):
                        raise LifecycleError(
                            "WI-CATEGORY-ARCHIVE-MONTH-MISMATCH",
                            f"{category.name}:{slug} belongs in archive/{archive_month(instant)}",
                        )
                legacy_read_compatible.append(
                    legacy.relative_to(work_items).as_posix()
                )
                continue
            if category.current_kind == "flat" and locations:
                path = locations[0]
                fields = _parse_fields(path.read_text(encoding="utf-8"))
                status = fields.get("status", "")
                archived = "archive" in path.parts
                if archived and status in category.current_statuses:
                    raise LifecycleError(
                        "WI-CATEGORY-CURRENT-IN-ARCHIVE",
                        f"{category.name}:{slug} has current status in archive",
                    )
                if not archived and status in category.terminal_statuses:
                    raise LifecycleError(
                        "WI-CATEGORY-TERMINAL-IN-CURRENT",
                        f"{category.name}:{slug} has terminal status in current root",
                    )

    active = work_items / "active"
    if active.is_dir():
        for item in sorted(path for path in active.iterdir() if path.is_dir()):
            fields = _parse_fields((item / "status.md").read_text(encoding="utf-8"))
            if fields.get("status") in CATEGORIES["work-item"].terminal_statuses:
                raise LifecycleError(
                    "WI-CATEGORY-TERMINAL-IN-CURRENT",
                    f"work-item:{item.name} has terminal status in active/",
                )
    return tuple(sorted(legacy_read_compatible))


def audit(root: Path) -> tuple[str, ...]:
    legacy_read_compatible = audit_categories(root)
    check_readme(root)
    return legacy_read_compatible


def _validate_flat_terminal(category: Category, data: bytes) -> str:
    try:
        fields = _parse_fields(data.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise LifecycleError(
            "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING", "terminal record must be UTF-8"
        ) from exc
    status = fields.get("status", "")
    if status not in category.terminal_statuses:
        raise LifecycleError(
            "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
            f"{category.name} status {status!r} is not terminal",
        )
    admission = _admission_for(category.name)
    utc_field = admission.utc_field.casefold()
    evidence_fields = (
        admission.detail_field.casefold(),
        admission.evidence_field.casefold(),
    )
    missing = [name for name in (utc_field, *evidence_fields) if not fields.get(name)]
    if missing:
        raise LifecycleError(
            "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
            f"{category.name} terminal record missing: {', '.join(missing)}",
        )
    _strict_utc(fields[utc_field])
    return fields[utc_field]


def _normalization_fail(failure_id: str, message: str) -> LifecycleError:
    return LifecycleError(failure_id, message)


def _normalization_bound_source(
    root: Path, category: Category, relative: str, *, must_exist: bool = True
) -> Path:
    work_items = _work_items_root(root)
    relative_path = Path(relative)
    if (
        relative_path.is_absolute()
        or len(relative_path.parts) < 2
        or relative_path.parts[0] != "work-items"
    ):
        raise _normalization_fail(
            "WI-IDENTITY-NORMALIZE-SOURCE",
            "normalization source must be repository-relative under work-items",
        )
    within_work_items = Path(*relative_path.parts[1:]).as_posix()
    requested = work_items.resolve() / Path(within_work_items)
    try:
        resolved = _terminalization_bound_path(
            work_items, within_work_items, label="normalization source"
        )
    except LifecycleError as exc:
        raise _normalization_fail("WI-IDENTITY-NORMALIZE-SOURCE", str(exc)) from exc
    source = requested
    expected_parent = (work_items / category.current_root).resolve()
    if (
        category.current_kind != "flat"
        or source.parent.resolve() != expected_parent
        or source.resolve() != resolved
        or source.suffix != ".md"
        or (must_exist and not source.is_file())
    ):
        raise _normalization_fail(
            "WI-IDENTITY-NORMALIZE-SOURCE",
            "normalization source must be one mutable flat record in its category current root",
        )
    return source


def _normalization_scratch_path(root: Path, path: Path, *, label: str) -> Path:
    try:
        return _bound_repository_scratch_path(root, path, label=label, allow_absolute=True)
    except LifecycleError as exc:
        raise _normalization_fail("WI-IDENTITY-NORMALIZE-INVENTORY", str(exc)) from exc


def _normalization_exact_file(path: Path) -> bool:
    return path.parent.is_dir() and any(
        child.name == path.name and child.is_file() for child in path.parent.iterdir()
    )


def _normalization_current_files(work_items: Path) -> list[Path]:
    files: set[Path] = set((work_items / "backlog").glob("*.md"))
    files.update(path / "status.md" for path in (work_items / "active").glob("*") if path.is_dir())
    for category in CATEGORIES.values():
        if category.current_kind == "flat":
            files.update((work_items / category.current_root).glob("*.md"))
    return sorted(path for path in files if path.is_file())


def _normalization_authoritative_line_numbers(text: str) -> frozenset[int]:
    return frozenset(
        line_number for line_number, _line in _authoritative_markdown_lines(text)
    )


def _normalization_replace_id(text: str, old_slug: str, new_slug: str) -> tuple[str, int]:
    authoritative = _normalization_authoritative_line_numbers(text)
    lines = text.splitlines(keepends=True)
    count = 0
    for index, line in enumerate(lines, start=1):
        if index not in authoritative:
            continue
        body = line.rstrip("\r\n")
        ending = line[len(body) :]
        match = FIELD_RE.fullmatch(body)
        if not (
            match
            and match.group(1).strip().casefold() == "id"
            and match.group(2).strip() == old_slug
        ):
            continue
        value_start, value_end = match.span(2)
        raw_value = match.group(2)
        leading = len(raw_value) - len(raw_value.lstrip())
        trailing = len(raw_value) - len(raw_value.rstrip())
        replacement = raw_value[:leading] + new_slug
        if trailing:
            replacement += raw_value[len(raw_value) - trailing :]
        lines[index - 1] = body[:value_start] + replacement + body[value_end:] + ending
        count += 1
    return "".join(lines), count


def _normalization_replace_live_mentions(
    text: str, old_slug: str, new_slug: str
) -> tuple[str, int]:
    """Rewrite live current-record mentions but preserve fenced evidence bytes."""
    authoritative = _normalization_authoritative_line_numbers(text)
    lines = text.splitlines(keepends=True)
    count = 0
    for index, line in enumerate(lines, start=1):
        if index not in authoritative:
            continue
        count += line.count(old_slug)
        lines[index - 1] = line.replace(old_slug, new_slug)
    return "".join(lines), count


def _normalization_authoritative_markdown_links(
    text: str,
) -> Iterable[MarkdownLocalLink]:
    """Yield normalization links only from lifecycle-authoritative Markdown lines."""
    authoritative = _normalization_authoritative_line_numbers(text)
    for link in _markdown_local_links(text):
        line_number = text.count("\n", 0, link.href_start) + 1
        if line_number in authoritative:
            yield link


def _normalization_snapshot(
    root: Path,
    category: Category,
    source: Path,
    target_slug: str,
) -> tuple[dict, dict[Path, bytes]]:
    work_items = _work_items_root(root)
    old_slug = source.stem
    target = work_items / category.current_root / f"{target_slug}.md"
    planned: dict[Path, bytes] = {}
    kinds: dict[Path, set[str]] = {}

    current_files = frozenset(_normalization_current_files(work_items))
    markdown_files = sorted(
        path for path in work_items.rglob("*.md") if path.name != "README.md"
    )
    for path in markdown_files:
        try:
            before = path.read_bytes()
            text = before.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise _normalization_fail(
                "WI-IDENTITY-NORMALIZE-INVENTORY",
                f"cannot classify Markdown consumer: {path}",
            ) from exc

        physical_replacements: list[tuple[int, int, str]] = []
        for link in _normalization_authoritative_markdown_links(text):
            href_parts = _local_markdown_href_parts(link.href)
            if href_parts is None:
                continue
            filesystem_href, suffix = href_parts
            if (path.parent / filesystem_href).resolve() != source.resolve():
                continue
            if path not in current_files:
                raise _normalization_fail(
                    "WI-IDENTITY-NORMALIZE-INVENTORY",
                    f"physical consumer is not mutable current state: {path}",
                )
            new_href = Path(os.path.relpath(target, path.parent)).as_posix() + suffix
            physical_replacements.append((link.href_start, link.href_end, new_href))
        if physical_replacements:
            for start, end, value in reversed(physical_replacements):
                text = text[:start] + value + text[end:]
            kinds.setdefault(path, set()).add("physical-link")

        if path not in current_files:
            continue
        after = text
        if path == source:
            after, count = _normalization_replace_id(after, old_slug, target_slug)
            if count != 1:
                raise _normalization_fail(
                    "WI-IDENTITY-NORMALIZE-INVENTORY",
                    "source must contain exactly one authoritative id matching its physical slug",
                )
            kinds.setdefault(path, set()).add("authoritative-id")
        after, live_count = _normalization_replace_live_mentions(
            after, old_slug, target_slug
        )
        if live_count:
            kinds.setdefault(path, set()).add("live-reference")
        if after.encode("utf-8") != before:
            planned[path] = after.encode("utf-8")

    if source not in planned:
        raise _normalization_fail(
            "WI-IDENTITY-NORMALIZE-INVENTORY", "normalization source produced no identity change"
        )
    rows = []
    for path in sorted(planned):
        before = path.read_bytes()
        after = planned[path]
        rows.append(
            {
                "path": path.relative_to(work_items).as_posix(),
                "kinds": sorted(kinds[path]),
                "beforeSha256": hashlib.sha256(before).hexdigest(),
                "afterSha256": hashlib.sha256(after).hexdigest(),
            }
        )
    inventory = {
        "schemaVersion": CURRENT_IDENTITY_NORMALIZATION_SCHEMA_VERSION,
        "owner": CURRENT_IDENTITY_NORMALIZATION_OWNER,
        "workItemsRoot": str(work_items.resolve()),
        "category": category.name,
        "source": source.relative_to(work_items.parent).as_posix(),
        "targetSlug": target_slug,
        "oldIdentity": f"{category.name}:{old_slug}",
        "newIdentity": f"{category.name}:{target_slug}",
        "rows": rows,
    }
    return inventory, planned


def write_current_identity_normalization_inventory(
    root: Path,
    category_name: str,
    source_relative: str,
    target_slug: str,
    inventory_path: Path,
) -> dict:
    category = CATEGORIES.get(CATEGORY_ALIASES.get(category_name, category_name))
    if category is None:
        raise LifecycleError("WI-REFERENCE-INVALID", f"unknown category: {category_name!r}")
    _validate_slug(target_slug)
    source = _normalization_bound_source(root, category, source_relative)
    if is_valid_slug(source.stem):
        raise _normalization_fail(
            "WI-IDENTITY-NORMALIZE-SOURCE", "source identity is already canonical"
        )
    fields = _parse_fields(source.read_text(encoding="utf-8"))
    if fields.get("status", "") not in category.current_statuses:
        raise _normalization_fail(
            "WI-IDENTITY-NORMALIZE-SOURCE", "source does not carry a current admitted status"
        )
    inventory, _planned = _normalization_snapshot(root, category, source, target_slug)
    destination = _normalization_scratch_path(root, inventory_path, label="normalization inventory")
    _atomic_write(destination, (json.dumps(inventory, indent=2, sort_keys=True) + "\n").encode())
    return inventory


def _normalization_expected_receipt_rows(
    root: Path,
    category: Category,
    inventory: object,
    source: Path,
    target: Path,
) -> list[dict[str, str]]:
    """Derive the one complete receipt row sequence from the canonical inventory."""
    work_items = _work_items_root(root)
    source_repo_relative = source.relative_to(work_items.parent).as_posix()
    source_work_items_relative = source.relative_to(work_items).as_posix()
    target_work_items_relative = target.relative_to(work_items).as_posix()
    if (
        not isinstance(inventory, dict)
        or inventory.get("schemaVersion")
        != CURRENT_IDENTITY_NORMALIZATION_SCHEMA_VERSION
        or inventory.get("owner") != CURRENT_IDENTITY_NORMALIZATION_OWNER
        or inventory.get("workItemsRoot") != str(work_items.resolve())
        or inventory.get("category") != category.name
        or inventory.get("source") != source_repo_relative
        or inventory.get("targetSlug") != target.stem
        or not isinstance(inventory.get("rows"), list)
    ):
        raise _normalization_fail(
            "WI-IDENTITY-NORMALIZE-RECOVERY",
            "normalization inventory binding differs during replay",
        )

    expected: list[dict[str, str]] = []
    before_paths: set[str] = set()
    after_paths: set[str] = set()
    digest_re = re.compile(r"^[0-9a-f]{64}$")
    for row in inventory["rows"]:
        if (
            not isinstance(row, dict)
            or set(row) != {"path", "kinds", "beforeSha256", "afterSha256"}
            or not isinstance(row.get("path"), str)
            or not isinstance(row.get("kinds"), list)
            or not all(isinstance(kind, str) for kind in row["kinds"])
            or not isinstance(row.get("beforeSha256"), str)
            or not digest_re.fullmatch(row["beforeSha256"])
            or not isinstance(row.get("afterSha256"), str)
            or not digest_re.fullmatch(row["afterSha256"])
        ):
            raise _normalization_fail(
                "WI-IDENTITY-NORMALIZE-RECOVERY",
                "normalization inventory row is invalid during replay",
            )
        before_path = row["path"]
        try:
            _terminalization_bound_path(
                work_items, before_path, label="normalization receipt preimage"
            )
        except LifecycleError as exc:
            raise _normalization_fail(
                "WI-IDENTITY-NORMALIZE-RECOVERY", str(exc)
            ) from exc
        after_path = (
            target_work_items_relative
            if before_path == source_work_items_relative
            else before_path
        )
        if before_path in before_paths or after_path in after_paths:
            raise _normalization_fail(
                "WI-IDENTITY-NORMALIZE-RECOVERY",
                "normalization inventory rows are duplicated or collide",
            )
        before_paths.add(before_path)
        after_paths.add(after_path)
        expected.append(
            {
                "beforePath": before_path,
                "afterPath": after_path,
                "beforeSha256": row["beforeSha256"],
                "afterSha256": row["afterSha256"],
            }
        )
    if source_work_items_relative not in before_paths:
        raise _normalization_fail(
            "WI-IDENTITY-NORMALIZE-RECOVERY",
            "normalization inventory omits the authoritative source row",
        )
    return expected


def _normalization_replay(
    root: Path,
    category: Category,
    inventory_bytes: bytes,
    receipt: Path,
    source: Path,
    target: Path,
) -> bool:
    if not receipt.is_file() or _normalization_exact_file(source) or not _normalization_exact_file(target):
        return False
    try:
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        inventory = json.loads(inventory_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _normalization_fail("WI-IDENTITY-NORMALIZE-RECOVERY", "invalid normalization receipt") from exc
    work_items = _work_items_root(root)
    if (
        not isinstance(payload, dict)
        or payload.get("schemaVersion") != CURRENT_IDENTITY_NORMALIZATION_SCHEMA_VERSION
        or payload.get("owner") != CURRENT_IDENTITY_NORMALIZATION_OWNER
        or payload.get("inventorySha256") != hashlib.sha256(inventory_bytes).hexdigest()
        or payload.get("source") != source.relative_to(work_items.parent).as_posix()
        or payload.get("target") != target.relative_to(work_items).as_posix()
        or not isinstance(payload.get("rows"), list)
    ):
        raise _normalization_fail("WI-IDENTITY-NORMALIZE-RECOVERY", "normalization receipt binding differs")
    expected_rows = _normalization_expected_receipt_rows(
        root, category, inventory, source, target
    )
    if payload["rows"] != expected_rows:
        raise _normalization_fail(
            "WI-IDENTITY-NORMALIZE-RECOVERY",
            "normalization receipt row set is incomplete, duplicated, or tampered",
        )
    for row in expected_rows:
        path = _terminalization_bound_path(work_items, row["afterPath"], label="normalization replay")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row.get("afterSha256"):
            raise _normalization_fail("WI-IDENTITY-NORMALIZE-RECOVERY", "normalization settled bytes differ")
    readme = work_items / "README.md"
    if not readme.is_file() or hashlib.sha256(readme.read_bytes()).hexdigest() != payload.get("readmeSha256"):
        raise _normalization_fail("WI-IDENTITY-NORMALIZE-RECOVERY", "normalization README differs")
    return True


def normalize_current_identity(
    root: Path,
    category_name: str,
    source_relative: str,
    target_slug: str,
    inventory_path: Path,
    receipt_path: Path,
    *,
    inject_failure_at: str | None = None,
) -> tuple[Path, bool]:
    category = CATEGORIES.get(CATEGORY_ALIASES.get(category_name, category_name))
    if category is None:
        raise LifecycleError("WI-REFERENCE-INVALID", f"unknown category: {category_name!r}")
    _validate_slug(target_slug)
    work_items = _work_items_root(root)
    source = _normalization_bound_source(root, category, source_relative, must_exist=False)
    target = work_items / category.current_root / f"{target_slug}.md"
    inventory_file = _normalization_scratch_path(root, inventory_path, label="normalization inventory")
    receipt = _normalization_scratch_path(root, receipt_path, label="normalization receipt")
    try:
        inventory_bytes = inventory_file.read_bytes()
        inventory = json.loads(inventory_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _normalization_fail("WI-IDENTITY-NORMALIZE-INVENTORY", "invalid normalization inventory") from exc
    if not _normalization_exact_file(source):
        if _normalization_replay(
            root, category, inventory_bytes, receipt, source, target
        ):
            return target, True
        raise _normalization_fail(
            "WI-IDENTITY-NORMALIZE-RECOVERY", "source is absent without a complete settled receipt"
        )
    if receipt.exists():
        raise _normalization_fail(
            "WI-IDENTITY-NORMALIZE-RECOVERY",
            "receipt exists while legacy source is still present",
        )
    if is_valid_slug(source.stem):
        raise _normalization_fail("WI-IDENTITY-NORMALIZE-SOURCE", "source identity is already canonical")
    locations = _category_locations(root, category, source.stem)
    if locations != [source]:
        raise LifecycleError("WI-CATEGORY-DUAL-LOCATION", "source identity is not physically unique")
    fields = _parse_fields(source.read_text(encoding="utf-8"))
    if fields.get("status", "") not in category.current_statuses:
        raise _normalization_fail(
            "WI-IDENTITY-NORMALIZE-SOURCE", "source does not carry a current admitted status"
        )
    target_locations = _category_locations(root, category, target_slug)
    if _normalization_exact_file(target) or any(
        not (location.is_file() and os.path.samefile(location, source))
        for location in target_locations
    ):
        raise LifecycleError("WI-CATEGORY-DUAL-LOCATION", "normalization target already exists")
    expected, planned = _normalization_snapshot(root, category, source, target_slug)
    if inventory != expected:
        raise _normalization_fail(
            "WI-IDENTITY-NORMALIZE-INVENTORY", "inventory is incomplete, stale, or differently classified"
        )
    readme = work_items / "README.md"
    readme_before = readme.read_bytes() if readme.is_file() else None
    preimages = {path: path.read_bytes() for path in planned}
    inventory_sha = hashlib.sha256(inventory_bytes).hexdigest()
    moved = False
    move_temp: Path | None = None
    try:
        for path in sorted(planned):
            _atomic_write(path, planned[path])
        if inject_failure_at == "after-rewrites":
            raise RuntimeError("injected normalization failure after rewrites")
        temp_dir = Path(tempfile.mkdtemp(prefix=f".{target_slug}.normalize.", dir=source.parent))
        move_temp = temp_dir / source.name
        os.replace(source, move_temp)
        os.replace(move_temp, target)
        temp_dir.rmdir()
        move_temp = None
        moved = True
        if inject_failure_at == "after-move":
            raise RuntimeError("injected normalization failure after move")
        readme_sha = refresh_readme(root)
        if inject_failure_at == "after-readme":
            raise RuntimeError("injected normalization failure after README")
        resolved = resolve_category(root, f"{category.name}:{target_slug}")
        if resolved != target.resolve() or _normalization_exact_file(source) or not _normalization_exact_file(target):
            raise RuntimeError("normalization final identity check failed")
        for path, after in planned.items():
            final_path = target if path == source else path
            if (
                not final_path.is_file()
                or hashlib.sha256(final_path.read_bytes()).hexdigest()
                != hashlib.sha256(after).hexdigest()
            ):
                raise RuntimeError(
                    f"normalization final byte check failed: {final_path}"
                )
        audit(root)
        rows = _normalization_expected_receipt_rows(
            root, category, inventory, source, target
        )
        payload = {
            "schemaVersion": CURRENT_IDENTITY_NORMALIZATION_SCHEMA_VERSION,
            "owner": CURRENT_IDENTITY_NORMALIZATION_OWNER,
            "inventorySha256": inventory_sha,
            "source": source_relative,
            "target": target.relative_to(work_items).as_posix(),
            "readmeSha256": readme_sha,
            "rows": rows,
        }
        _atomic_write(receipt, (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode())
        if not _normalization_replay(
            root, category, inventory_bytes, receipt, source, target
        ):
            raise RuntimeError("normalization settled receipt verification failed")
        return target, False
    except BaseException as exc:
        try:
            if move_temp is not None and move_temp.exists():
                os.replace(move_temp, source)
                move_temp.parent.rmdir()
            elif moved and _normalization_exact_file(target) and not _normalization_exact_file(source):
                temp_dir = Path(tempfile.mkdtemp(prefix=f".{source.stem}.rollback.", dir=source.parent))
                rollback_temp = temp_dir / target.name
                os.replace(target, rollback_temp)
                os.replace(rollback_temp, source)
                temp_dir.rmdir()
            for path, before in preimages.items():
                _atomic_write(path, before)
            if readme_before is None:
                if readme.exists():
                    readme.unlink()
            else:
                _atomic_write(readme, readme_before)
            if receipt.exists():
                receipt.unlink()
        except BaseException as rollback_exc:
            raise _normalization_fail(
                "WI-IDENTITY-NORMALIZE-ROLLBACK", f"rollback failed: {rollback_exc}"
            ) from exc
        raise _normalization_fail("WI-IDENTITY-NORMALIZE-ROLLBACK", str(exc)) from exc


CATEGORY_ADMISSION_TABLE = (
    CategoryAdmission(
        "work-item",
        "mutate-work-item:_category_locations",
        "mutate-work-item:_validate_closure",
        "closure.md:Closed",
        "work_item_terminal_evidence_missing",
        "Closed",
        "Outcome",
        "Evidence",
    ),
    CategoryAdmission(
        "bug",
        "mutate-work-item:_category_locations",
        "mutate-work-item:_validate_flat_terminal",
        "bug:Terminal-at",
        "bug_terminal_evidence_missing",
        "Terminal-at",
        "Resolution",
        "Evidence",
    ),
    CategoryAdmission(
        "decision",
        "mutate-work-item:_category_locations",
        "mutate-work-item:_validate_flat_terminal",
        "decision:Terminal-at",
        "decision_terminal_evidence_missing",
        "Terminal-at",
        "Rationale",
        "Evidence",
    ),
    CategoryAdmission(
        "lesson",
        "mutate-work-item:_category_locations",
        "mutate-work-item:_validate_flat_terminal",
        "lesson:Terminal-at",
        "lesson_terminal_evidence_missing",
        "Terminal-at",
        "Disposition",
        "Evidence",
    ),
    CategoryAdmission(
        "roadmap",
        "mutate-work-item:_category_locations",
        "mutate-work-item:_validate_flat_terminal",
        "roadmap:Terminal-at",
        "roadmap_terminal_evidence_missing",
        "Terminal-at",
        "Disposition",
        "Evidence",
    ),
    CategoryAdmission(
        "epic",
        "mutate-work-item:_category_locations",
        "mutate-work-item:_validate_flat_terminal",
        "epic:Closed",
        "epic_terminal_evidence_missing",
        "Closed",
        "Outcome",
        "Evidence",
    ),
)


def _admission_for(category_name: str) -> CategoryAdmission:
    rows = [row for row in CATEGORY_ADMISSION_TABLE if row.category == category_name]
    if len(CATEGORY_ADMISSION_TABLE) != 6 or len(rows) != 1:
        raise LifecycleError(
            "CATEGORY-MIGRATION-ADMISSION-GATE",
            f"category admission table is incomplete or duplicated: {category_name}",
        )
    row = rows[0]
    if not all(
        (
            row.category,
            row.current_reader,
            row.terminal_validator,
            row.utc_field_owner,
            row.negative_fixture,
            row.utc_field,
            row.detail_field,
            row.evidence_field,
        )
    ):
        raise LifecycleError(
            "CATEGORY-MIGRATION-ADMISSION-GATE",
            f"category admission row has a missing cell: {category_name}",
        )
    return row


def _move_terminal_category(root: Path, reference: str) -> Path:
    category, slug = _canonical_category(reference)
    _admission_for(category.name)
    locations = _category_locations(root, category, slug)
    if len(locations) > 1:
        raise LifecycleError("WI-CATEGORY-DUAL-LOCATION", f"duplicate slug: {reference}")
    if len(locations) != 1:
        raise LifecycleError("WI-INVALID-TARGET", f"missing category record: {reference}")
    source = locations[0]
    if category.name == "work-item":
        closure = source / "closure.md"
        if not closure.is_file():
            raise LifecycleError(
                "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING", "work-item lacks closure.md"
            )
        if "archive" in source.parts:
            _archived_work_item_entry(source)
            refresh_readme(root)
            return source
        fields = _parse_fields(closure.read_text(encoding="utf-8"))
        instant = fields.get("closed", "")
        closure_data = closure.read_bytes()
        _validate_closure(closure_data, instant)
        terminal_closure = _stamp_schema_marker(closure_data, "closure.md")
        target = _work_items_root(root) / "archive" / archive_month(instant) / slug
        if not source.is_dir() or source.parent.name != "active":
            raise LifecycleError("WI-INVALID-TARGET", "work-item migration requires active/")
        _validate_item_before_close(source)
        status = source / "status.md"
        terminal_status = _terminalize_status(status.read_bytes())
    else:
        instant = _validate_flat_terminal(category, source.read_bytes())
        target = (
            _work_items_root(root)
            / category.current_root
            / "archive"
            / archive_month(instant)
            / source.name
        )
        if "archive" in source.parts:
            if source != target:
                raise LifecycleError(
                    "WI-CATEGORY-ARCHIVE-MONTH-MISMATCH",
                    f"{reference} is not in archive/{archive_month(instant)}",
                )
            refresh_readme(root)
            return source
    _preflight_readme_markers(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise LifecycleError("WI-CATEGORY-DUAL-LOCATION", f"archive target exists: {target}")
    if category.name == "work-item":
        prior_status = status.read_bytes()
        prior_closure = closure.read_bytes()
        _atomic_write(status, terminal_status)
        _atomic_write(closure, terminal_closure)
    try:
        os.replace(source, target)
    except BaseException:
        if category.name == "work-item":
            _atomic_write(status, prior_status)
            _atomic_write(closure, prior_closure)
        raise
    try:
        refresh_readme(root)
    except LifecycleError as exc:
        raise LifecycleError("WI-README-STALE", str(exc)) from exc
    return target


def migrate_legacy(
    root: Path, reference: str, *, incoming_links_inventory: Path | None
) -> Path:
    category, _slug = _canonical_category(reference)
    _admission_for(category.name)
    if incoming_links_inventory is None or not incoming_links_inventory.is_file():
        raise LifecycleError(
            "WI-LEGACY-LINK-UNMAPPED",
            f"legacy move requires an incoming-link inventory: {reference}",
        )
    try:
        inventory = json.loads(incoming_links_inventory.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleError("WI-LEGACY-LINK-UNMAPPED", "invalid incoming-link inventory") from exc
    if not isinstance(inventory, dict) or inventory.get("reference") != reference:
        raise LifecycleError(
            "WI-LEGACY-LINK-UNMAPPED", "incoming-link inventory is not target-bound"
        )
    return _move_terminal_category(root, reference)


def _payload_digest(path: Path) -> tuple[str, str]:
    if path.is_symlink():
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-PAYLOAD",
            f"symbolic-link payload is not admitted: {path}",
        )
    if path.is_file():
        return (
            MIGRATION_DIGEST_ALGORITHMS["file"],
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
    if not path.is_dir():
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-PAYLOAD",
            f"payload is not a file or directory: {path}",
        )
    digest = hashlib.sha256()
    digest.update(b"sha256-tree-entries-v1\0")
    for entry in sorted(path.rglob("*"), key=lambda item: item.relative_to(path).as_posix()):
        if entry.is_symlink():
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-PAYLOAD",
                f"symbolic-link tree entry is not admitted: {entry}",
            )
        relative = entry.relative_to(path).as_posix().encode("utf-8")
        if entry.is_dir():
            digest.update(b"D")
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
        elif entry.is_file():
            data = entry.read_bytes()
            digest.update(b"F")
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
            digest.update(len(data).to_bytes(8, "big"))
            digest.update(data)
        else:
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-PAYLOAD",
                f"unsupported tree entry: {entry}",
            )
    return MIGRATION_DIGEST_ALGORITHMS["directory"], digest.hexdigest()


def _selected_migration_records(root: Path) -> list[tuple[Category, str, Path]]:
    work_items = _work_items_root(root)
    selected: list[tuple[Category, str, Path]] = []
    active = work_items / "active"
    if active.is_dir():
        for item in sorted(path for path in active.iterdir() if path.is_dir()):
            status = item / "status.md"
            fields = (
                _parse_fields(status.read_text(encoding="utf-8", errors="replace"))
                if status.is_file()
                else {}
            )
            if (item / "closure.md").is_file() or fields.get("status") in CATEGORIES[
                "work-item"
            ].terminal_statuses:
                selected.append((CATEGORIES["work-item"], item.name, item))
    for category in CATEGORIES.values():
        if category.current_kind != "flat":
            continue
        current = work_items / category.current_root
        if not current.is_dir():
            continue
        for path in sorted(current.glob("*.md")):
            fields = _parse_fields(path.read_text(encoding="utf-8", errors="replace"))
            if fields.get("status") in category.terminal_statuses:
                selected.append((category, path.stem, path))
    return sorted(selected, key=lambda item: (item[0].name, item[1]))


def _planned_migration_target(
    root: Path,
    category: Category,
    slug: str,
    source: Path,
) -> tuple[str, Path]:
    locations = _category_locations(root, category, slug)
    if locations != [source]:
        failure = "WI-CATEGORY-DUAL-LOCATION" if len(locations) > 1 else "WI-INVALID-TARGET"
        raise LifecycleError(
            failure,
            f"{category.name}:{slug} does not resolve to its selected source",
        )
    return _validated_migration_payload_target(root, category, slug, source)


def _validated_migration_payload_target(
    root: Path,
    category: Category,
    slug: str,
    payload: Path,
) -> tuple[str, Path]:
    if category.name == "work-item":
        closure = payload / "closure.md"
        if not closure.is_file():
            raise LifecycleError(
                "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
                f"work-item:{slug} lacks closure.md",
            )
        fields = _parse_fields(closure.read_text(encoding="utf-8"))
        instant = fields.get("closed", "")
        _validate_closure(closure.read_bytes(), instant)
        _validate_item_before_close(payload)
        target = _work_items_root(root) / "archive" / archive_month(instant) / slug
    else:
        instant = _validate_flat_terminal(category, payload.read_bytes())
        target = (
            _work_items_root(root)
            / category.current_root
            / "archive"
            / archive_month(instant)
            / f"{slug}.md"
        )
    return instant, target


MARKDOWN_LINK_RE = re.compile(
    r"\[(?P<label>[^\]\r\n]+)\]\(\s*(?:<(?P<angle>[^<>()\s\r\n]+)>|(?P<bare>[^()\s\r\n]+))\s*\)"
)


@dataclass(frozen=True)
class MarkdownLocalLink:
    label: str
    href: str
    href_start: int
    href_end: int


def _markdown_local_links(text: str) -> Iterable[MarkdownLocalLink]:
    """Yield only complete, closed, local Markdown link destinations."""
    for match in MARKDOWN_LINK_RE.finditer(text):
        href = match.group("angle") or match.group("bare")
        yield MarkdownLocalLink(
            label=match.group("label"),
            href=href,
            href_start=match.start("angle") if match.group("angle") is not None else match.start("bare"),
            href_end=match.end("angle") if match.group("angle") is not None else match.end("bare"),
        )


URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def _local_markdown_href_parts(href: str) -> tuple[str, str] | None:
    """Split one local href into filesystem identity and preserved suffix."""
    if (
        not href
        or href.startswith(("#", "/", "\\"))
        or URI_SCHEME_RE.match(href)
    ):
        return None
    suffix_offsets = [offset for marker in ("#", "?") if (offset := href.find(marker)) >= 0]
    split_at = min(suffix_offsets) if suffix_offsets else len(href)
    filesystem_identity = href[:split_at]
    if not filesystem_identity:
        return None
    return filesystem_identity, href[split_at:]


def _markdown_href_resolves(base: Path, href: str, expected: Path) -> bool:
    parts = _local_markdown_href_parts(href)
    return parts is not None and (base / parts[0]).resolve() == expected.resolve()


def _incoming_link_result(
    root: Path,
    owned_paths: Iterable[Path],
    reference: str,
    *,
    literal_path_references: Iterable[str] = (),
    mutable_consumers_only: bool = False,
    scan_markdown_links: bool = True,
) -> dict:
    work_items = _work_items_root(root)
    physical: list[dict[str, str]] = []
    logical: list[dict[str, str]] = []
    owned_resolved = frozenset(path.resolve() for path in owned_paths)
    if not owned_resolved:
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-INVENTORY",
            f"incoming-link scan has no owned paths for {reference}",
        )
    literal_paths = tuple(sorted(set(literal_path_references)))
    if any(not path or path.startswith(("/", "\\")) for path in literal_paths):
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-INVENTORY",
            f"incoming-link scan has invalid literal path for {reference}",
        )
    literal_patterns = tuple(
        (
            literal_path,
            re.compile(
                rf"(?<![A-Za-z0-9_.\\/-]){re.escape(literal_path).replace('/', r'[\\/]')}(?![A-Za-z0-9_.\\/-])"
            ),
        )
        for literal_path in literal_paths
    )

    def belongs_to_owned(path: Path) -> bool:
        return any(
            path == owned or owned in path.parents
            for owned in owned_resolved
        )

    for consumer in sorted(path for path in work_items.rglob("*") if path.is_file()):
        if consumer.name in {"README.md", "index.md"}:
            continue
        consumer_resolved = consumer.resolve()
        if belongs_to_owned(consumer_resolved):
            continue
        try:
            consumer_bytes = consumer.read_bytes()
            text = consumer_bytes.decode("utf-8")
        except (OSError, UnicodeError):
            continue
        consumer_rel = consumer.relative_to(work_items).as_posix()
        if mutable_consumers_only and "archive" in Path(consumer_rel).parts:
            continue
        if reference in text:
            logical.append(
                {"consumer": consumer_rel, "kind": "logical", "value": reference}
            )
        if scan_markdown_links:
            for link in _markdown_local_links(text):
                raw = link.href
                href_parts = _local_markdown_href_parts(raw)
                if href_parts is None:
                    continue
                candidate = (consumer.parent / href_parts[0]).resolve()
                if belongs_to_owned(candidate):
                    physical.append(
                        {
                            "consumer": consumer_rel,
                            "kind": "physical",
                            "value": raw,
                        }
                    )
        for literal_path, literal_pattern in literal_patterns:
            if literal_pattern.search(text):
                physical.append(
                    {
                        "consumer": consumer_rel,
                        "kind": "physical",
                        "value": literal_path,
                    }
                )
    references = sorted(
        physical + logical,
        key=lambda item: (item["consumer"], item["kind"], item["value"]),
    )
    if physical:
        result = "unmapped"
    elif logical:
        result = "logical-only"
    else:
        result = "clear"
    return {"result": result, "references": references}


def _validate_incoming_link_snapshot(reference: str, snapshot: dict, *, label: str) -> None:
    if not isinstance(snapshot, dict):
        raise LifecycleError(
            "WI-LEGACY-LINK-UNMAPPED",
            f"{label} incoming-link inventory is invalid for {reference}",
        )
    result = snapshot.get("result")
    links = snapshot.get("references")
    if result not in {"clear", "logical-only"} or not isinstance(links, list):
        raise LifecycleError(
            "WI-LEGACY-LINK-UNMAPPED",
            f"{label} incoming links are not logical-only for {reference}",
        )
    expected_result = "logical-only" if links else "clear"
    if result != expected_result:
        raise LifecycleError(
            "WI-LEGACY-LINK-UNMAPPED",
            f"{label} incoming-link result differs from its rows for {reference}",
        )
    seen: set[tuple[str, str, str]] = set()
    for link in links:
        if (
            not isinstance(link, dict)
            or not isinstance(link.get("consumer"), str)
            or link.get("kind") != "logical"
            or link.get("value") != reference
        ):
            raise LifecycleError(
                "WI-LEGACY-LINK-UNMAPPED",
                f"{label} incoming link is not category-qualified logical for {reference}",
            )
        identity = (link["consumer"], link["kind"], link["value"])
        if identity in seen:
            raise LifecycleError(
                "WI-LEGACY-LINK-UNMAPPED",
                f"{label} incoming-link inventory repeats a row for {reference}",
            )
        seen.add(identity)


def _validate_incoming_link_compatibility(
    root: Path,
    reference: str,
    planned: dict,
    current: dict,
    *,
    resolved_location: Path,
) -> None:
    for label, snapshot in (("planned", planned), ("current", current)):
        _validate_incoming_link_snapshot(reference, snapshot, label=label)
    try:
        resolved = resolve_category(root, reference)
    except LifecycleError as exc:
        raise LifecycleError(
            "WI-LEGACY-LINK-UNMAPPED",
            f"logical reference does not resolve uniquely: {reference}",
        ) from exc
    if resolved != resolved_location.resolve():
        raise LifecycleError(
            "WI-LEGACY-LINK-UNMAPPED",
            f"logical reference resolves outside the migration payload: {reference}",
        )


def build_migration_inventory(root: Path) -> dict:
    work_items = _work_items_root(root)
    rows: list[dict] = []
    for category, slug, source in _selected_migration_records(root):
        reference = f"{category.name}:{slug}"
        algorithm, input_hash = _payload_digest(source)
        admission_row = _admission_for(category.name)
        row = {
            "reference": reference,
            "category": category.name,
            "source": source.relative_to(work_items).as_posix(),
            "target": None,
            "terminalInstant": None,
            "inputSha256": input_hash,
            "digestAlgorithm": algorithm,
            "incomingLinks": None,
            "admission": {
                "result": "admitted",
                "reader": admission_row.current_reader,
                "validator": admission_row.terminal_validator,
                "utcOwner": admission_row.utc_field_owner,
                "negativeFixture": admission_row.negative_fixture,
            },
        }
        try:
            instant, target = _planned_migration_target(
                root, category, slug, source
            )
            row["terminalInstant"] = instant
            row["target"] = target.relative_to(work_items).as_posix()
        except LifecycleError as exc:
            row["admission"] = {
                "result": "denied",
                "failureId": exc.failure_id,
                "reason": str(exc),
            }
        owned_paths = {source}
        if row["target"] is not None:
            owned_paths.add(work_items / Path(row["target"]))
        row["incomingLinks"] = _incoming_link_result(
            root,
            owned_paths,
            reference,
        )
        rows.append(row)
    return {
        "schemaVersion": MIGRATION_SCHEMA_VERSION,
        "owner": MIGRATION_OWNER,
        "workItemsRoot": str(work_items.resolve()),
        "digestAlgorithms": dict(MIGRATION_DIGEST_ALGORITHMS),
        "rows": rows,
    }


def write_migration_inventory(root: Path, output: Path) -> dict:
    _static_guide(
        _work_items_root(root) / "README.md",
        allow_marker_bootstrap=True,
    )
    inventory = build_migration_inventory(root)
    _atomic_write(
        output,
        (json.dumps(inventory, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    for row in inventory["rows"]:
        admission = row["admission"]
        if admission.get("result") != "admitted":
            raise LifecycleError(
                admission.get("failureId", "CATEGORY-MIGRATION-ADMISSION-GATE"),
                admission.get("reason", f"unadmitted row: {row['reference']}"),
            )
        if row["incomingLinks"].get("result") == "unmapped":
            raise LifecycleError(
                "WI-LEGACY-LINK-UNMAPPED",
                f"physical incoming links remain for {row['reference']}",
            )
    return inventory


def _load_migration_inventory(root: Path, inventory_path: Path) -> dict:
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-INVENTORY",
            f"invalid migration inventory: {inventory_path}",
        ) from exc
    work_items = _work_items_root(root)
    if (
        not isinstance(inventory, dict)
        or inventory.get("schemaVersion") != MIGRATION_SCHEMA_VERSION
        or inventory.get("owner") != MIGRATION_OWNER
        or inventory.get("workItemsRoot") != str(work_items.resolve())
        or inventory.get("digestAlgorithms") != MIGRATION_DIGEST_ALGORITHMS
        or not isinstance(inventory.get("rows"), list)
    ):
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-INVENTORY",
            "migration inventory schema or target binding differs",
        )
    return inventory


def _terminalization_fail(message: str) -> LifecycleError:
    return LifecycleError(V1_TERMINALIZATION_FAILURE, message)


def _terminalization_has_reparse(path: Path) -> bool:
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError as exc:
        raise _terminalization_fail(f"cannot inspect terminalization path: {path}") from exc
    return path.is_symlink() or bool(
        attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _terminalization_bound_path(
    work_items: Path,
    relative: str,
    *,
    label: str,
) -> Path:
    if not isinstance(relative, str) or not relative:
        raise _terminalization_fail(f"{label} path is missing")
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise _terminalization_fail(f"{label} path escapes work-items: {relative!r}")
    root = work_items.resolve()
    cursor = work_items
    if _terminalization_has_reparse(cursor):
        raise _terminalization_fail(f"work-items root is a link or reparse point: {cursor}")
    for part in relative_path.parts:
        cursor = cursor / part
        if cursor.exists() or cursor.is_symlink():
            if _terminalization_has_reparse(cursor):
                raise _terminalization_fail(
                    f"{label} path contains a link or reparse point: {cursor}"
                )
    resolved = cursor.resolve()
    if resolved != root and root not in resolved.parents:
        raise _terminalization_fail(f"{label} path escapes work-items: {relative!r}")
    return resolved


def _bound_repository_scratch_path(
    root: Path,
    path: str | Path,
    *,
    label: str,
    allow_absolute: bool,
) -> Path:
    candidate = Path(path) if isinstance(path, (str, Path)) else Path()
    if not candidate.parts or ".." in candidate.parts:
        raise _terminalization_fail(f"{label} path is unsafe")
    repo_root = _work_items_root(root).parent.resolve()
    if candidate.is_absolute():
        if not allow_absolute:
            raise _terminalization_fail(f"{label} path must be repository-relative")
        try:
            relative = candidate.relative_to(repo_root)
        except ValueError as exc:
            raise _terminalization_fail(f"{label} path escapes the repository") from exc
    else:
        relative = candidate
    if len(relative.parts) < 2 or relative.parts[0] != ".scratch":
        raise _terminalization_fail(f"{label} must be a file under repository .scratch")
    if _terminalization_has_reparse(repo_root):
        raise _terminalization_fail(f"repository root is a link or reparse point: {repo_root}")
    cursor = repo_root
    for part in relative.parts:
        cursor = cursor / part
        if (cursor.exists() or cursor.is_symlink()) and _terminalization_has_reparse(cursor):
            raise _terminalization_fail(
                f"{label} path contains a link or reparse point: {cursor}"
            )
    resolved = cursor.resolve()
    scratch = (repo_root / ".scratch").resolve()
    if resolved == scratch or scratch not in resolved.parents:
        raise _terminalization_fail(f"{label} escapes repository .scratch")
    return resolved


def _bound_physical_receipt(root: Path, relative: str) -> Path:
    return _bound_repository_scratch_path(
        root,
        relative,
        label="physical-relocation receipt",
        allow_absolute=False,
    )


def _physical_relocation_admission(
    root: Path,
    reference: str,
    incoming: object,
    *,
    receipt_path: Path | None = None,
) -> tuple[list[dict], dict | None]:
    if not isinstance(incoming, dict) or not isinstance(incoming.get("references"), list):
        raise _terminalization_fail(f"incoming-link inventory is invalid for {reference}")
    links = incoming["references"]
    physical: list[dict] = []
    logical: list[dict] = []
    for link in links:
        if (
            not isinstance(link, dict)
            or not isinstance(link.get("consumer"), str)
            or not isinstance(link.get("value"), str)
        ):
            raise _terminalization_fail(f"incoming-link row is invalid for {reference}")
        if link.get("kind") == "physical":
            physical.append(link)
        elif link.get("kind") == "logical" and link["value"] == reference:
            logical.append(link)
        else:
            raise _terminalization_fail(f"incoming-link kind or identity differs for {reference}")
    if not physical:
        expected_result = "logical-only" if logical else "clear"
        if incoming.get("result") != expected_result or "physicalRelocation" in incoming:
            raise _terminalization_fail(
                f"incoming-link result differs from its rows for {reference}"
            )
        return links, None
    if len(physical) != 1 or logical or incoming.get("result") != "physical-relocation":
        raise _terminalization_fail(
            f"physical relocation requires one exact incoming link for {reference}"
        )
    admission = incoming.get("physicalRelocation")
    required = {
        "source",
        "label",
        "href",
        "expectedIdentity",
        "sourceSha256",
        "targetSha256",
        "receipt",
    }
    if not isinstance(admission, dict) or set(admission) != required:
        raise _terminalization_fail(
            f"physical-relocation admission shape differs for {reference}"
        )
    source_relative = admission.get("source")
    source_parts = Path(source_relative).parts if isinstance(source_relative, str) else ()
    if (
        source_relative != physical[0]["consumer"]
        or admission.get("href") != physical[0]["value"]
        or admission.get("expectedIdentity") != reference
        or not isinstance(admission.get("label"), str)
        or not admission["label"]
        or not re.fullmatch(r"[0-9a-f]{64}", str(admission.get("sourceSha256", "")))
        or not re.fullmatch(r"[0-9a-f]{64}", str(admission.get("targetSha256", "")))
        or len(source_parts) < 4
        or source_parts[-3] != "archive"
        or not re.fullmatch(r"\d{4}-\d{2}", source_parts[-2])
    ):
        raise _terminalization_fail(
            f"physical-relocation tuple differs for {reference}"
        )
    bound_receipt = _bound_physical_receipt(root, admission["receipt"])
    if receipt_path is not None and bound_receipt != receipt_path.resolve():
        raise _terminalization_fail(
            f"physical-relocation receipt binding differs for {reference}"
        )
    return links, admission


def _plan_v1_link_relocations(
    root: Path,
    planned: list[dict],
    terminal_at: str,
    receipt_path: Path,
) -> tuple[list[dict], list[dict]]:
    work_items = _work_items_root(root)
    admissions: list[tuple[dict, dict]] = []
    for item in planned:
        _links, admission = _physical_relocation_admission(
            root,
            item["reference"],
            item["incomingLinks"],
            receipt_path=receipt_path,
        )
        if admission is not None:
            admissions.append((item, admission))
    if len(admissions) > 1:
        raise _terminalization_fail("only one exact physical relocation is admitted")
    consumer_plans: list[dict] = []
    receipt_links: list[dict] = []
    for item, admission in admissions:
        consumer_relative = admission["source"]
        consumer = _terminalization_bound_path(
            work_items, consumer_relative, label="physical-link consumer"
        )
        if consumer.suffix.casefold() != ".md" or not consumer.is_file():
            raise _terminalization_fail(
                f"physical-link consumer is not a Markdown file: {consumer_relative}"
            )
        if consumer == item["source"]:
            raise _terminalization_fail(
                f"physical-link consumer is also moving: {consumer_relative}"
            )
        before = consumer.read_bytes()
        before_sha256 = hashlib.sha256(before).hexdigest()
        if admission["sourceSha256"] != before_sha256:
            raise _terminalization_fail(
                f"physical-link consumer hash changed: {consumer_relative}"
            )
        if admission["targetSha256"] != item["beforeSha256"]:
            raise _terminalization_fail(
                f"physical-link target hash changed: {item['reference']}"
            )
        try:
            text = before.decode("utf-8")
        except UnicodeError as exc:
            raise _terminalization_fail(
                f"physical-link consumer is not UTF-8 Markdown: {consumer_relative}"
            ) from exc

        matches = [
            link
            for link in _markdown_local_links(text)
            if link.label == admission["label"] and link.href == admission["href"]
        ]
        if len(matches) != 1:
            raise _terminalization_fail(
                f"physical Markdown tuple is missing or duplicated: {consumer_relative}"
            )
        href_parts = _local_markdown_href_parts(admission["href"])
        if href_parts is None or not _markdown_href_resolves(
            consumer.parent, admission["href"], item["source"]
        ):
            raise _terminalization_fail(
                f"physical Markdown href resolves outside expected identity: {consumer_relative}"
            )
        new_path = Path(os.path.relpath(item["target"], consumer.parent)).as_posix()
        new_href = new_path + href_parts[1]
        if not _markdown_href_resolves(consumer.parent, new_href, item["target"]):
            raise _terminalization_fail(
                f"relocated href does not resolve to target: {consumer_relative}"
            )
        after_text = (
            text[:matches[0].href_start]
            + new_href
            + text[matches[0].href_end:]
        )
        after = after_text.encode("utf-8")
        after_sha256 = hashlib.sha256(after).hexdigest()
        consumer_plans.append(
            {
                "consumer": consumer,
                "consumerRelative": consumer_relative,
                "before": before,
                "beforeSha256": before_sha256,
                "after": after,
                "afterSha256": after_sha256,
            }
        )
        receipt_links.append(
            {
                "source": consumer_relative,
                "label": admission["label"],
                "oldHref": admission["href"],
                "newHref": new_href,
                "expectedIdentity": item["reference"],
                "finalTarget": item["targetRelative"],
                "sourceBeforeSha256": before_sha256,
                "sourceAfterSha256": None,
                "targetBeforeSha256": item["afterSha256"],
                "targetAfterSha256": None,
                "terminalAt": terminal_at,
            }
        )
    return consumer_plans, receipt_links


def _expected_physical_relocation_receipt(
    root: Path,
    reference: str,
    admission: dict,
    source: Path,
    target: Path,
    target_before_sha256: str,
    terminal_at: str,
    *,
    settled: bool,
) -> dict:
    """Derive the one receipt relation allowed by an admitted physical link."""
    work_items = _work_items_root(root)
    consumer_relative = admission["source"]
    consumer = _terminalization_bound_path(
        work_items, consumer_relative, label="physical-link consumer"
    )
    if not consumer.is_file():
        raise _terminalization_fail(
            f"physical-link consumer is missing: {consumer_relative}"
        )
    href_parts = _local_markdown_href_parts(admission["href"])
    if href_parts is None:
        raise _terminalization_fail(
            f"physical Markdown href is not local: {consumer_relative}"
        )
    expected_href = Path(os.path.relpath(target, consumer.parent)).as_posix() + href_parts[1]
    current_href = expected_href if settled else admission["href"]
    resolved_target = target if settled else source
    try:
        current = consumer.read_bytes()
        text = current.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise _terminalization_fail(
            f"physical-link consumer is not UTF-8 Markdown: {consumer_relative}"
        ) from exc
    matches = [
        link
        for link in _markdown_local_links(text)
        if link.label == admission["label"]
        and link.href == current_href
        and _markdown_href_resolves(consumer.parent, link.href, resolved_target)
    ]
    if len(matches) != 1:
        raise _terminalization_fail(
            f"physical Markdown tuple is missing or duplicated: {consumer_relative}"
        )
    if settled:
        link = matches[0]
        source_before = hashlib.sha256(
            (
                text[:link.href_start]
                + admission["href"]
                + text[link.href_end:]
            ).encode("utf-8")
        ).hexdigest()
        source_after: str | None = hashlib.sha256(current).hexdigest()
        target_after: str | None = hashlib.sha256(target.read_bytes()).hexdigest()
    else:
        source_before = hashlib.sha256(current).hexdigest()
        source_after = None
        target_after = None
    payload = target if settled else source
    if (
        source_before != admission["sourceSha256"]
        or hashlib.sha256(payload.read_bytes()).hexdigest() != target_before_sha256
        or (settled and target_after != target_before_sha256)
    ):
        raise _terminalization_fail(
            f"physical-relocation evidence differs for {reference}"
        )
    return {
        "source": consumer_relative,
        "label": admission["label"],
        "oldHref": admission["href"],
        "newHref": expected_href,
        "expectedIdentity": reference,
        "finalTarget": target.relative_to(work_items).as_posix(),
        "sourceBeforeSha256": source_before,
        "sourceAfterSha256": source_after,
        "targetBeforeSha256": target_before_sha256,
        "targetAfterSha256": target_after,
        "terminalAt": terminal_at,
    }


def _terminalization_receipt_path(root: Path, path: Path) -> Path:
    return _bound_repository_scratch_path(
        root,
        path,
        label="terminalization receipt",
        allow_absolute=True,
    )


def _terminalization_replay(
    root: Path,
    inventory: dict,
    inventory_sha256: str,
    terminal_at: str,
    authorization_marker: str,
    receipt_path: Path,
) -> tuple[int, bool] | None:
    if not receipt_path.exists():
        return None
    if not receipt_path.is_file():
        raise _terminalization_fail(
            f"terminalization receipt is not a file: {receipt_path}"
        )
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _terminalization_fail(
            f"existing terminalization receipt is invalid: {receipt_path}"
        ) from exc
    work_items = _work_items_root(root)
    expected_header = {
        "schemaVersion": V1_TERMINALIZATION_SCHEMA_VERSION,
        "owner": V1_TERMINALIZATION_OWNER,
        "workItemsRoot": str(work_items.resolve()),
        "inventorySha256": inventory_sha256,
        "terminalAt": terminal_at,
        "authorizationMarker": authorization_marker,
        "rowCount": len(inventory["rows"]),
        "linkCount": sum(
            1
            for inventory_row in inventory["rows"]
            if isinstance(inventory_row, dict)
            for link in (inventory_row.get("incomingLinks") or {}).get("references", [])
            if isinstance(link, dict) and link.get("kind") == "physical"
        ),
    }
    if not isinstance(receipt, dict) or any(
        receipt.get(key) != value for key, value in expected_header.items()
    ):
        raise _terminalization_fail(
            "existing terminalization receipt does not match this exact operation"
        )
    receipt_rows = receipt.get("rows")
    if not isinstance(receipt_rows, list) or len(receipt_rows) != len(
        inventory["rows"]
    ):
        raise _terminalization_fail(
            "existing terminalization receipt row set differs"
        )
    inventory_references = sorted(
        row.get("reference") for row in inventory["rows"] if isinstance(row, dict)
    )
    receipt_references = sorted(
        row.get("reference") for row in receipt_rows if isinstance(row, dict)
    )
    if inventory_references != receipt_references:
        raise _terminalization_fail(
            "existing terminalization receipt references differ"
        )
    inventory_by_reference = {
        row.get("reference"): row for row in inventory["rows"] if isinstance(row, dict)
    }
    receipt_pairs: set[tuple[str, str]] = set()
    for row in receipt_rows:
        if not isinstance(row, dict):
            raise _terminalization_fail(
                "existing terminalization receipt contains an invalid row"
            )
        inventory_row = inventory_by_reference.get(row.get("reference"))
        if not isinstance(inventory_row, dict):
            raise _terminalization_fail(
                f"terminalization receipt has no inventory row: {row.get('reference')}"
            )
        source = _terminalization_bound_path(
            work_items, row.get("source"), label="receipt source"
        )
        target = _terminalization_bound_path(
            work_items, row.get("target"), label="receipt target"
        )
        category, slug = _canonical_category(row["reference"])
        expected_target = (
            work_items
            / category.current_root
            / "archive"
            / archive_month(terminal_at)
            / f"{slug}.md"
        ).resolve()
        source_exists = source.is_file()
        target_exists = target.is_file()
        payload = source if source_exists else target
        if (
            row.get("source") != inventory_row.get("source")
            or row.get("beforeSha256") != inventory_row.get("inputSha256")
            or source_exists == target_exists
            or target != expected_target
            or row.get("afterSha256")
            != hashlib.sha256(payload.read_bytes()).hexdigest()
            or _category_locations(root, category, slug) != [payload]
        ):
            raise _terminalization_fail(
                f"terminalized payload differs from receipt: {row.get('reference')}"
            )
        receipt_pairs.add((row["source"], row["target"]))
    receipt_link_rows = [
        (receipt_row, receipt_row["physicalRelocation"])
        for receipt_row in receipt_rows
        if isinstance(receipt_row, dict)
        and isinstance(receipt_row.get("physicalRelocation"), dict)
    ]
    if len(receipt_link_rows) != expected_header["linkCount"]:
        raise _terminalization_fail("existing terminalization receipt link set differs")
    seen_link_rows: set[tuple[str, str, str, str]] = set()
    for owner_row, link in receipt_link_rows:
        if not isinstance(link, dict) or link.get("terminalAt") != terminal_at:
            raise _terminalization_fail("existing terminalization receipt link row is invalid")
        consumer = _terminalization_bound_path(
            work_items, link.get("source"), label="receipt link consumer"
        )
        new_target = _terminalization_bound_path(
            work_items, link.get("finalTarget"), label="receipt new target"
        )
        before_sha256 = link.get("sourceBeforeSha256")
        after_sha256 = link.get("sourceAfterSha256")
        target_before_sha256 = link.get("targetBeforeSha256")
        target_after_sha256 = link.get("targetAfterSha256")
        old_href = link.get("oldHref")
        new_href = link.get("newHref")
        label = link.get("label")
        identity = link.get("expectedIdentity")
        old_target_relative = next(
            (
                old
                for old, new in receipt_pairs
                if new == link.get("finalTarget")
            ),
            None,
        )
        old_target = (
            _terminalization_bound_path(
                work_items, old_target_relative, label="receipt old target"
            )
            if old_target_relative is not None
            else None
        )
        pending = old_target is not None and old_target.is_file() and not new_target.exists()
        settled = old_target is not None and not old_target.exists() and new_target.is_file()
        if (
            old_target is None
            or not isinstance(before_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", before_sha256)
            or not isinstance(target_before_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", target_before_sha256)
            or (pending and (after_sha256 is not None or target_after_sha256 is not None))
            or (
                settled
                and (
                    not isinstance(after_sha256, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", after_sha256)
                    or not isinstance(target_after_sha256, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", target_after_sha256)
                    or hashlib.sha256(new_target.read_bytes()).hexdigest()
                    != target_after_sha256
                )
            )
            or not isinstance(old_href, str)
            or not isinstance(new_href, str)
            or not isinstance(label, str)
            or not isinstance(identity, str)
            or not (pending or settled)
            or not consumer.is_file()
            or hashlib.sha256(consumer.read_bytes()).hexdigest()
            != (before_sha256 if pending else after_sha256)
        ):
            raise _terminalization_fail(
                f"terminalized link differs from receipt: {link.get('source')}"
            )
        key = (link["source"], old_href, new_href, link["finalTarget"])
        if key in seen_link_rows:
            raise _terminalization_fail("terminalization receipt repeats a physical link")
        seen_link_rows.add(key)
        try:
            text = consumer.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise _terminalization_fail(
                f"terminalized link consumer is unreadable: {link.get('source')}"
            ) from exc
        expected_href = old_href if pending else new_href
        expected_target = old_target if pending else new_target
        resolved_matches = [
            link
            for link in _markdown_local_links(text)
            if link.label == label
            and link.href == expected_href
            and _markdown_href_resolves(consumer.parent, link.href, expected_target)
        ]
        if len(resolved_matches) != 1:
            raise _terminalization_fail(
                f"terminalized Markdown href is missing: {link.get('source')}"
            )
        owner_reference = owner_row["reference"]
        owner_inventory_row = inventory_by_reference[owner_reference]
        _links, admission = _physical_relocation_admission(
            root,
            owner_reference,
            owner_inventory_row.get("incomingLinks"),
            receipt_path=receipt_path,
        )
        if admission is None or link != _expected_physical_relocation_receipt(
            root,
            owner_reference,
            admission,
            old_target,
            new_target,
            owner_row["afterSha256"],
            terminal_at,
            settled=settled,
        ):
            raise _terminalization_fail(
                f"terminalized physical-relocation receipt differs: {link.get('source')}"
            )
    return len(receipt_rows), True


def _preflight_v1_terminalization_rows(
    root: Path,
    inventory: dict,
    terminal_at: str,
    receipt_path: Path,
) -> tuple[list[dict], list[dict], list[dict]]:
    _strict_utc(terminal_at)
    work_items = _work_items_root(root)
    planned: list[dict] = []
    seen_sources: set[Path] = set()
    seen_targets: set[Path] = set()
    for row in inventory["rows"]:
        if not isinstance(row, dict):
            raise _terminalization_fail("terminalization inventory row is not an object")
        category_name = row.get("category")
        try:
            category, slug = _canonical_category(row.get("reference", ""))
        except LifecycleError as exc:
            raise _terminalization_fail(str(exc)) from exc
        if category.current_kind != "flat":
            raise _terminalization_fail(
                f"unsupported V1 terminalization category: {category_name!r}"
            )
        admission_row = _admission_for(category.name)
        if category.name != category_name:
            raise _terminalization_fail(
                f"category tuple differs for {row.get('reference')}"
            )
        admission = row.get("admission")
        if (
            not isinstance(admission, dict)
            or admission.get("result") != "denied"
            or admission.get("failureId") != V1_TERMINALIZATION_FAILURE
        ):
            raise _terminalization_fail(
                f"row is not denied solely for missing terminal evidence: "
                f"{row.get('reference')}"
            )
        incoming = row.get("incomingLinks")
        _incoming_rows, physical_relocation = _physical_relocation_admission(
            root,
            row["reference"],
            incoming,
            receipt_path=receipt_path,
        )
        if row.get("target") is not None or row.get("terminalInstant") is not None:
            raise _terminalization_fail(
                f"denied row already has a target or terminal instant: "
                f"{row.get('reference')}"
            )
        source = _terminalization_bound_path(
            work_items, row.get("source"), label="terminalization source"
        )
        expected_source = (
            work_items / category.current_root / f"{slug}.md"
        ).resolve()
        if source != expected_source or source in seen_sources:
            raise _terminalization_fail(
                f"source binding is ambiguous for {row.get('reference')}"
            )
        seen_sources.add(source)
        try:
            locations = _category_locations(root, category, slug)
        except OSError as exc:
            raise _terminalization_fail(
                f"cannot resolve locations for {row.get('reference')}"
            ) from exc
        if locations != [source] or not source.is_file():
            raise _terminalization_fail(
                f"current location is ambiguous for {row.get('reference')}"
            )
        target_relative = (
            Path(category.current_root)
            / "archive"
            / archive_month(terminal_at)
            / source.name
        ).as_posix()
        target = _terminalization_bound_path(
            work_items, target_relative, label="terminalization target"
        )
        if target in seen_targets or target.exists():
            raise _terminalization_fail(
                f"terminalization target is ambiguous for {row.get('reference')}"
            )
        seen_targets.add(target)
        if row.get("digestAlgorithm") != MIGRATION_DIGEST_ALGORITHMS["file"]:
            raise _terminalization_fail(
                f"unsupported digest algorithm for {row.get('reference')}"
            )
        before = source.read_bytes()
        before_sha256 = hashlib.sha256(before).hexdigest()
        if row.get("inputSha256") != before_sha256:
            raise _terminalization_fail(
                f"input payload hash changed for {row.get('reference')}"
            )
        try:
            text = before.decode("utf-8")
        except UnicodeError as exc:
            raise _terminalization_fail(
                f"terminal record is not UTF-8: {row.get('reference')}"
            ) from exc
        fields = _parse_fields(text)
        status = fields.get("status", "")
        if status not in category.terminal_statuses:
            raise _terminalization_fail(
                f"current status is not terminal for {row.get('reference')}: "
                f"{status!r}"
            )
        detail_field = admission_row.detail_field
        conflicting = tuple(
            dict.fromkeys(
                _terminalization_authoritative_field_occurrences(
                    text, admission_row.utc_field
                )
            )
        )
        if conflicting:
            raise _terminalization_fail(
                f"authoritative terminal field already exists for "
                f"{row.get('reference')}: {', '.join(conflicting)}"
            )
        current_links = _incoming_link_result(
            root,
            {source},
            row["reference"],
        )
        expected_current_links = (
            {
                "result": "unmapped",
                "references": incoming["references"],
            }
            if physical_relocation is not None
            else incoming
        )
        if current_links != expected_current_links:
            raise _terminalization_fail(
                f"incoming-link inventory changed for {row.get('reference')}"
            )
        separator = b"\n" if before.endswith(b"\n") else b"\n\n"
        proof = (
            "Historical terminal time is unknown; preserved pre-V1 input "
            f"SHA-256 `{before_sha256}`; original terminal status `{status}`; "
            "explicit operator-authorized V1 migration."
        )
        appended_lines = [f"{admission_row.utc_field}: {terminal_at}"]
        if not fields.get(detail_field.casefold()):
            appended_lines.append(
                f"{detail_field}: Pre-V1 terminal status `{status}` is preserved "
                "during operator-authorized V1 physical migration."
            )
        if not fields.get(admission_row.evidence_field.casefold()):
            appended_lines.append(f"{admission_row.evidence_field}: {proof}")
        appended_lines.append(f"V1-Migration-Evidence: {proof}")
        appended = ("\n".join(appended_lines) + "\n").encode("utf-8")
        after = before + separator + appended
        planned.append(
            {
                "reference": row["reference"],
                "sourceRelative": row["source"],
                "source": source,
                "targetRelative": target_relative,
                "target": target,
                "category": category,
                "slug": slug,
                "incomingLinks": incoming,
                "status": status,
                "before": before,
                "beforeSha256": before_sha256,
                "after": after,
                "afterSha256": hashlib.sha256(after).hexdigest(),
            }
        )
    planned = sorted(planned, key=lambda item: item["reference"])
    source_set = {item["source"] for item in planned}
    target_set = {item["target"] for item in planned}
    if source_set & target_set:
        raise _terminalization_fail("terminalization source and target sets overlap")
    consumers, receipt_links = _plan_v1_link_relocations(
        root, planned, terminal_at, receipt_path
    )
    return planned, consumers, receipt_links


def terminalize_v1_inventory(
    root: Path,
    inventory_path: Path,
    *,
    terminal_at: str,
    authorization_marker: str,
    receipt_path: Path,
    inject_failure_after: int | None = None,
) -> tuple[int, bool]:
    """Add V1 evidence and preserve exact relocation admission; never move records."""
    if authorization_marker != V1_TERMINALIZATION_AUTHORIZATION:
        raise _terminalization_fail(
            "explicit operator-authorized V1 terminalization marker is required"
        )
    _strict_utc(terminal_at)
    receipt = _terminalization_receipt_path(root, receipt_path)
    try:
        inventory_bytes = inventory_path.read_bytes()
        inventory = _load_migration_inventory(root, inventory_path)
    except LifecycleError as exc:
        raise _terminalization_fail(str(exc)) from exc
    except OSError as exc:
        raise _terminalization_fail(
            f"cannot read terminalization inventory: {inventory_path}"
        ) from exc
    inventory_sha256 = hashlib.sha256(inventory_bytes).hexdigest()
    replay = _terminalization_replay(
        root,
        inventory,
        inventory_sha256,
        terminal_at,
        authorization_marker,
        receipt,
    )
    if replay is not None:
        return replay
    planned, consumers, receipt_links = _preflight_v1_terminalization_rows(
        root, inventory, terminal_at, receipt
    )
    links_by_identity = {
        link["expectedIdentity"]: link for link in receipt_links
    }
    receipt_payload = {
        "schemaVersion": V1_TERMINALIZATION_SCHEMA_VERSION,
        "owner": V1_TERMINALIZATION_OWNER,
        "workItemsRoot": str(_work_items_root(root).resolve()),
        "inventorySha256": inventory_sha256,
        "terminalAt": terminal_at,
        "authorizationMarker": authorization_marker,
        "rowCount": len(planned),
        "linkCount": len(receipt_links),
        "rows": [
            {
                "reference": item["reference"],
                "source": item["sourceRelative"],
                "target": item["targetRelative"],
                "terminalAt": terminal_at,
                "originalStatus": item["status"],
                "beforeSha256": item["beforeSha256"],
                "afterSha256": item["afterSha256"],
                **(
                    {"physicalRelocation": links_by_identity[item["reference"]]}
                    if item["reference"] in links_by_identity
                    else {}
                ),
            }
            for item in planned
        ],
    }
    receipt_bytes = (
        json.dumps(receipt_payload, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    mutated_items: list[dict] = []
    try:
        for index, item in enumerate(planned, start=1):
            if item["source"].read_bytes() != item["before"]:
                raise _terminalization_fail(
                    f"payload changed after preflight: {item['reference']}"
                )
            _atomic_write(item["source"], item["after"])
            mutated_items.append(item)
            if inject_failure_after == index:
                raise _terminalization_fail(
                    f"injected terminalization failure after row {index}"
                )
        _atomic_write(receipt, receipt_bytes)
        for consumer in consumers:
            if consumer["consumer"].read_bytes() != consumer["before"]:
                raise _terminalization_fail(
                    f"terminalization rewrote consumer: {consumer['consumerRelative']}"
                )
        for item in planned:
            if (
                not item["source"].is_file()
                or item["target"].exists()
                or item["source"].read_bytes() != item["after"]
                or _category_locations(root, item["category"], item["slug"])
                != [item["source"]]
            ):
                raise _terminalization_fail(
                    f"terminalization identity check failed: {item['reference']}"
                )
    except Exception as exc:
        rollback_failures: list[str] = []
        for item in reversed(mutated_items):
            try:
                _atomic_write(item["source"], item["before"])
            except Exception as rollback_exc:
                rollback_failures.append(
                    f"{item['reference']}: {rollback_exc}"
                )
        if receipt.exists():
            try:
                receipt.unlink()
            except OSError as rollback_exc:
                rollback_failures.append(f"receipt: {rollback_exc}")
        if rollback_failures:
            raise _terminalization_fail(
                "terminalization rollback failed: " + "; ".join(rollback_failures)
            ) from exc
        if isinstance(exc, LifecycleError):
            raise
        raise _terminalization_fail(
            f"terminalization transaction failed: {exc}"
        ) from exc
    return len(planned), False


def _bound_inventory_path(work_items: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-INVENTORY", "inventory path is missing"
        )
    path = (work_items / Path(relative)).resolve()
    root = work_items.resolve()
    if path != root and root not in path.parents:
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-INVENTORY",
            f"inventory path escapes work-items: {relative}",
        )
    return path


def _terminalization_receipt_for_migration(
    root: Path,
    inventory_path: Path,
    inventory: dict,
) -> tuple[Path, bytes, dict]:
    admissions = [
        row["incomingLinks"]["physicalRelocation"]
        for row in inventory["rows"]
        if isinstance(row, dict)
        and isinstance(row.get("incomingLinks"), dict)
        and isinstance(row["incomingLinks"].get("physicalRelocation"), dict)
    ]
    if len(admissions) != 1:
        raise LifecycleError(
            "WI-LEGACY-LINK-UNMAPPED",
            "migration requires exactly one physical-relocation admission",
        )
    receipt_path = _bound_physical_receipt(root, admissions[0].get("receipt"))
    try:
        receipt_bytes = receipt_path.read_bytes()
        receipt = json.loads(receipt_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-INVENTORY",
            f"physical-relocation receipt is invalid: {receipt_path}",
        ) from exc
    inventory_sha256 = hashlib.sha256(inventory_path.read_bytes()).hexdigest()
    work_items = _work_items_root(root)
    if (
        not isinstance(receipt, dict)
        or receipt.get("schemaVersion") != V1_TERMINALIZATION_SCHEMA_VERSION
        or receipt.get("owner") != V1_TERMINALIZATION_OWNER
        or receipt.get("workItemsRoot") != str(work_items.resolve())
        or receipt.get("inventorySha256") != inventory_sha256
        or receipt.get("authorizationMarker") != V1_TERMINALIZATION_AUTHORIZATION
        or receipt.get("rowCount") != len(inventory["rows"])
        or receipt.get("linkCount") != 1
        or not isinstance(receipt.get("rows"), list)
        or len(receipt["rows"]) != len(inventory["rows"])
        or not isinstance(receipt.get("terminalAt"), str)
    ):
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-INVENTORY",
            "physical-relocation receipt binding differs",
        )
    _strict_utc(receipt["terminalAt"])
    return receipt_path, receipt_bytes, receipt


def _preflight_terminalized_inventory_rows(
    root: Path,
    inventory_path: Path,
    inventory: dict,
) -> tuple[list[dict], list[dict], Path, bytes, dict]:
    work_items = _work_items_root(root)
    receipt_path, receipt_bytes, receipt = _terminalization_receipt_for_migration(
        root, inventory_path, inventory
    )
    replay = _terminalization_replay(
        root,
        inventory,
        hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
        receipt["terminalAt"],
        V1_TERMINALIZATION_AUTHORIZATION,
        receipt_path,
    )
    if replay is None:
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-INVENTORY", "terminalization receipt is missing"
        )
    receipt_rows = {row.get("reference"): row for row in receipt["rows"] if isinstance(row, dict)}
    if len(receipt_rows) != len(inventory["rows"]):
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-INVENTORY", "terminalization receipt repeats a row"
        )
    plans: list[dict] = []
    consumers: list[dict] = []
    seen_sources: set[Path] = set()
    seen_targets: set[Path] = set()
    for row in inventory["rows"]:
        reference = row.get("reference") if isinstance(row, dict) else None
        receipt_row = receipt_rows.get(reference)
        admission = row.get("admission") if isinstance(row, dict) else None
        if (
            not isinstance(row, dict)
            or not isinstance(receipt_row, dict)
            or not isinstance(admission, dict)
            or admission.get("result") != "denied"
            or admission.get("failureId") != V1_TERMINALIZATION_FAILURE
        ):
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-INVENTORY",
                f"terminalized inventory row is invalid: {reference}",
            )
        category, slug = _canonical_category(reference)
        if row.get("category") != category.name:
            raise LifecycleError(
                "CATEGORY-MIGRATION-ADMISSION-GATE",
                f"category tuple differs for {reference}",
            )
        source = _bound_inventory_path(work_items, row.get("source"))
        target = _bound_inventory_path(work_items, receipt_row.get("target"))
        if source in seen_sources or target in seen_targets:
            raise LifecycleError(
                "WI-CATEGORY-DUAL-LOCATION", "terminalized inventory repeats a source or target"
            )
        seen_sources.add(source)
        seen_targets.add(target)
        source_exists = source.is_file()
        target_exists = target.is_file()
        if source_exists == target_exists:
            raise LifecycleError(
                "WI-CATEGORY-DUAL-LOCATION", f"terminalized location differs for {reference}"
            )
        payload = source if source_exists else target
        payload_sha256 = hashlib.sha256(payload.read_bytes()).hexdigest()
        if (
            receipt_row.get("source") != row.get("source")
            or receipt_row.get("beforeSha256") != row.get("inputSha256")
            or receipt_row.get("afterSha256") != payload_sha256
            or receipt_row.get("terminalAt") != receipt["terminalAt"]
        ):
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-PAYLOAD", f"terminalized payload changed for {reference}"
            )
        instant, expected_target = _validated_migration_payload_target(
            root, category, slug, payload
        )
        if instant != receipt["terminalAt"] or target != expected_target.resolve():
            raise LifecycleError(
                "WI-CATEGORY-ARCHIVE-MONTH-MISMATCH", f"terminalized target differs for {reference}"
            )
        if _category_locations(root, category, slug) != [payload]:
            raise LifecycleError(
                "WI-CATEGORY-DUAL-LOCATION", f"terminalized identity differs for {reference}"
            )
        incoming = row.get("incomingLinks")
        _links, physical = _physical_relocation_admission(
            root, reference, incoming, receipt_path=receipt_path
        )
        plan = {
            "row": row,
            "reference": reference,
            "category": category,
            "slug": slug,
            "source": source,
            "target": target,
            "pending": source_exists,
            "beforeSha256": receipt_row["afterSha256"],
            "receiptRow": receipt_row,
        }
        if physical is None:
            current_links = _incoming_link_result(root, {source, target}, reference)
            _validate_incoming_link_compatibility(
                root,
                reference,
                incoming,
                current_links,
                resolved_location=payload,
            )
        elif source_exists:
            planned_consumers, planned_links = _plan_v1_link_relocations(
                root,
                [
                    {
                        "reference": reference,
                        "sourceRelative": row["source"],
                        "source": source,
                        "targetRelative": receipt_row["target"],
                        "target": target,
                        "incomingLinks": incoming,
                        "beforeSha256": row["inputSha256"],
                        "afterSha256": receipt_row["afterSha256"],
                    }
                ],
                receipt["terminalAt"],
                receipt_path,
            )
            if planned_links != [receipt_row.get("physicalRelocation")]:
                raise LifecycleError(
                    "WI-LEGACY-LINK-UNMAPPED",
                    f"physical-relocation receipt differs for {reference}",
                )
            consumers.extend(planned_consumers)
        plans.append(plan)
    source_set = {plan["source"] for plan in plans}
    target_set = {plan["target"] for plan in plans}
    if source_set & target_set:
        raise LifecycleError("WI-CATEGORY-DUAL-LOCATION", "source and target sets overlap")
    return sorted(plans, key=lambda plan: plan["reference"]), consumers, receipt_path, receipt_bytes, receipt


def _preflight_inventory_rows(
    root: Path,
    inventory: dict,
) -> list[tuple[dict, Path, Path, bool]]:
    work_items = _work_items_root(root)
    planned: list[tuple[dict, Path, Path, bool]] = []
    seen_sources: set[Path] = set()
    seen_targets: set[Path] = set()
    for row in inventory["rows"]:
        if not isinstance(row, dict):
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-INVENTORY", "inventory row is not an object"
            )
        admission = row.get("admission")
        if not isinstance(admission, dict) or admission.get("result") != "admitted":
            raise LifecycleError(
                (admission or {}).get(
                    "failureId", "CATEGORY-MIGRATION-ADMISSION-GATE"
                ),
                (admission or {}).get("reason", "inventory row is not admitted"),
            )
        incoming = row.get("incomingLinks")
        if not isinstance(incoming, dict) or incoming.get("result") not in {
            "clear",
            "logical-only",
        }:
            raise LifecycleError(
                "WI-LEGACY-LINK-UNMAPPED",
                f"incoming links are not mapped for {row.get('reference')}",
            )
        category, slug = _canonical_category(row.get("reference", ""))
        if row.get("category") != category.name:
            raise LifecycleError(
                "CATEGORY-MIGRATION-ADMISSION-GATE",
                f"category tuple differs for {row.get('reference')}",
            )
        source = _bound_inventory_path(work_items, row.get("source"))
        target = _bound_inventory_path(work_items, row.get("target"))
        if source in seen_sources or target in seen_targets:
            raise LifecycleError(
                "WI-CATEGORY-DUAL-LOCATION", "inventory repeats a source or target"
            )
        seen_sources.add(source)
        seen_targets.add(target)
        source_exists = source.exists()
        target_exists = target.exists()
        if source_exists == target_exists:
            raise LifecycleError(
                "WI-CATEGORY-DUAL-LOCATION",
                f"pre-migration location differs for {row.get('reference')}",
            )
        payload = source if source_exists else target
        locations = _category_locations(root, category, slug)
        if locations != [payload]:
            raise LifecycleError(
                "WI-CATEGORY-DUAL-LOCATION",
                f"resolved location differs for {row.get('reference')}",
            )
        algorithm, digest = _payload_digest(payload)
        if (
            row.get("digestAlgorithm") != algorithm
            or row.get("inputSha256") != digest
        ):
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-PAYLOAD",
                f"migration payload changed for {row.get('reference')}",
            )
        instant, expected_target = _validated_migration_payload_target(
            root, category, slug, payload
        )
        if (
            row.get("terminalInstant") != instant
            or target != expected_target.resolve()
        ):
            raise LifecycleError(
                "WI-CATEGORY-ARCHIVE-MONTH-MISMATCH",
                f"planned target differs for {row.get('reference')}",
            )
        current_links = _incoming_link_result(
            root,
            {source, target},
            row["reference"],
        )
        _validate_incoming_link_compatibility(
            root,
            row["reference"],
            incoming,
            current_links,
            resolved_location=payload,
        )
        planned.append((row, source, target, source_exists))
    source_set = {source for _row, source, _target, _pending in planned}
    target_set = {target for _row, _source, target, _pending in planned}
    if source_set & target_set:
        raise LifecycleError(
            "WI-CATEGORY-DUAL-LOCATION", "source and target sets overlap"
        )
    return sorted(planned, key=lambda item: item[0]["reference"])


def apply_migration_inventory(
    root: Path,
    inventory_path: Path,
    *,
    render_readme: bool,
    byte_check: bool,
) -> tuple[int, str | None]:
    inventory = _load_migration_inventory(root, inventory_path)
    has_physical_relocation = any(
        isinstance(row, dict)
        and isinstance(row.get("incomingLinks"), dict)
        and isinstance(row["incomingLinks"].get("physicalRelocation"), dict)
        for row in inventory["rows"]
    )
    if has_physical_relocation:
        plans, consumers, receipt_path, receipt_before, receipt_payload = (
            _preflight_terminalized_inventory_rows(root, inventory_path, inventory)
        )
        work_items = _work_items_root(root)
        readme = work_items / "README.md"
        readme_before = readme.read_bytes() if readme.is_file() else None
        written_consumers: list[dict] = []
        moved: list[dict] = []
        created_directories: set[Path] = set()
        try:
            for consumer in consumers:
                if consumer["consumer"].read_bytes() != consumer["before"]:
                    raise LifecycleError(
                        "WI-LEGACY-LINK-UNMAPPED",
                        f"consumer changed after preflight: {consumer['consumerRelative']}",
                    )
                _atomic_write(consumer["consumer"], consumer["after"])
                written_consumers.append(consumer)
            for plan in plans:
                if not plan["pending"]:
                    continue
                if (
                    not plan["source"].is_file()
                    or plan["target"].exists()
                    or hashlib.sha256(plan["source"].read_bytes()).hexdigest()
                    != plan["beforeSha256"]
                ):
                    raise LifecycleError(
                        "WI-CATEGORY-MIGRATION-PAYLOAD",
                        f"payload changed after preflight: {plan['reference']}",
                    )
                cursor = plan["target"].parent
                while cursor != work_items and not cursor.exists():
                    created_directories.add(cursor)
                    cursor = cursor.parent
                plan["target"].parent.mkdir(parents=True, exist_ok=True)
                os.replace(plan["source"], plan["target"])
                moved.append(plan)
            readme_hash: str | None = None
            if render_readme:
                readme_hash = refresh_readme(root, allow_marker_bootstrap=True)
            if byte_check and (
                not readme.is_file() or readme.read_bytes() != render_readme_bytes(root)
            ):
                raise LifecycleError(
                    "WI-README-STALE", "README differs from an immediate fresh render"
                )
            for plan in plans:
                if (
                    plan["source"].exists()
                    or not plan["target"].is_file()
                    or hashlib.sha256(plan["target"].read_bytes()).hexdigest()
                    != plan["beforeSha256"]
                    or _category_locations(root, plan["category"], plan["slug"])
                    != [plan["target"]]
                ):
                    raise LifecycleError(
                        "WI-CATEGORY-DUAL-LOCATION",
                        f"migration identity check failed: {plan['reference']}",
                    )
            consumers_by_source = {
                consumer["consumerRelative"]: consumer for consumer in consumers
            }
            for row in receipt_payload["rows"]:
                evidence = row.get("physicalRelocation")
                if not isinstance(evidence, dict):
                    continue
                consumer = consumers_by_source.get(evidence.get("source"))
                if consumer is None:
                    if not isinstance(evidence.get("sourceAfterSha256"), str):
                        raise LifecycleError(
                            "WI-LEGACY-LINK-UNMAPPED",
                            "settled physical relocation lacks receipt evidence",
                        )
                    continue
                if (
                    consumer["consumer"].read_bytes() != consumer["after"]
                    or not _markdown_href_resolves(
                        consumer["consumer"].parent,
                        evidence["newHref"],
                        _bound_inventory_path(work_items, evidence["finalTarget"]),
                    )
                ):
                    raise LifecycleError(
                        "WI-LEGACY-LINK-UNMAPPED",
                        "migrated Markdown href does not resolve to final target",
                    )
                evidence["sourceAfterSha256"] = consumer["afterSha256"]
                final_target = _bound_inventory_path(work_items, evidence["finalTarget"])
                evidence["targetAfterSha256"] = hashlib.sha256(
                    final_target.read_bytes()
                ).hexdigest()
            _atomic_write(
                receipt_path,
                (json.dumps(receipt_payload, indent=2, sort_keys=True) + "\n").encode(
                    "utf-8"
                ),
            )
            return len(plans), readme_hash
        except Exception as exc:
            rollback_failures: list[str] = []
            for plan in reversed(moved):
                try:
                    if plan["target"].exists() and not plan["source"].exists():
                        plan["source"].parent.mkdir(parents=True, exist_ok=True)
                        os.replace(plan["target"], plan["source"])
                except Exception as rollback_exc:
                    rollback_failures.append(
                        f"{plan['reference']}: {rollback_exc}"
                    )
            for consumer in reversed(written_consumers):
                try:
                    _atomic_write(consumer["consumer"], consumer["before"])
                except Exception as rollback_exc:
                    rollback_failures.append(
                        f"{consumer['consumerRelative']}: {rollback_exc}"
                    )
            try:
                _restore_readme_snapshot(readme, readme_before)
            except Exception as rollback_exc:
                rollback_failures.append(f"README: {rollback_exc}")
            try:
                _atomic_write(receipt_path, receipt_before)
            except Exception as rollback_exc:
                rollback_failures.append(f"receipt: {rollback_exc}")
            for directory in sorted(
                created_directories, key=lambda path: len(path.parts), reverse=True
            ):
                try:
                    if directory.is_dir() and not any(directory.iterdir()):
                        directory.rmdir()
                except OSError as rollback_exc:
                    rollback_failures.append(f"directory {directory}: {rollback_exc}")
            if rollback_failures:
                raise LifecycleError(
                    "WI-CATEGORY-MIGRATION-INVENTORY",
                    "physical-relocation rollback failed: " + "; ".join(rollback_failures),
                ) from exc
            if isinstance(exc, LifecycleError):
                raise
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-INVENTORY",
                f"physical-relocation transaction failed: {exc}",
            ) from exc
    planned = _preflight_inventory_rows(root, inventory)
    for _row, source, target, pending in planned:
        if not pending:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, target)
    readme_hash: str | None = None
    if render_readme:
        readme_hash = refresh_readme(root, allow_marker_bootstrap=True)
    if byte_check:
        readme = _work_items_root(root) / "README.md"
        if not readme.is_file() or readme.read_bytes() != render_readme_bytes(root):
            raise LifecycleError(
                "WI-README-STALE", "README differs from an immediate fresh render"
            )
    for _row, source, target, _pending in planned:
        if source.exists() or not target.exists():
            raise LifecycleError(
                "WI-CATEGORY-DUAL-LOCATION",
                "source-target disjointness failed after migration",
            )
    return len(planned), readme_hash


def verify_migration_inventory(root: Path, inventory_path: Path) -> int:
    inventory = _load_migration_inventory(root, inventory_path)
    work_items = _work_items_root(root)
    if any(
        isinstance(row, dict)
        and isinstance(row.get("incomingLinks"), dict)
        and isinstance(row["incomingLinks"].get("physicalRelocation"), dict)
        for row in inventory["rows"]
    ):
        plans, _consumers, _receipt_path, _receipt_bytes, _receipt = (
            _preflight_terminalized_inventory_rows(root, inventory_path, inventory)
        )
        for plan in plans:
            if (
                plan["pending"]
                or not plan["target"].is_file()
                or plan["source"].exists()
                or hashlib.sha256(plan["target"].read_bytes()).hexdigest()
                != plan["beforeSha256"]
                or _category_locations(root, plan["category"], plan["slug"])
                != [plan["target"]]
            ):
                raise LifecycleError(
                    "WI-CATEGORY-DUAL-LOCATION",
                    f"settled physical relocation differs for {plan['reference']}",
                )
        check_readme(root)
        return len(plans)
    for row in inventory["rows"]:
        source = _bound_inventory_path(work_items, row.get("source"))
        target = _bound_inventory_path(work_items, row.get("target"))
        if source.exists() or not target.exists():
            raise LifecycleError(
                "WI-CATEGORY-DUAL-LOCATION",
                f"source/target state differs for {row.get('reference')}",
            )
        algorithm, digest = _payload_digest(target)
        if (
            algorithm != row.get("digestAlgorithm")
            or digest != row.get("inputSha256")
        ):
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-PAYLOAD",
                f"target payload hash differs for {row.get('reference')}",
            )
        category, _slug = _canonical_category(row.get("reference", ""))
        if row.get("category") != category.name:
            raise LifecycleError(
                "CATEGORY-MIGRATION-ADMISSION-GATE",
                f"category tuple differs for {row.get('reference')}",
            )
        instant = row.get("terminalInstant")
        if target.parent.name != archive_month(instant):
            raise LifecycleError(
                "WI-CATEGORY-ARCHIVE-MONTH-MISMATCH",
                f"target month differs for {row.get('reference')}",
            )
        if resolve_category(root, row["reference"]) != target:
            raise LifecycleError(
                "WI-LEGACY-LINK-UNMAPPED",
                f"logical reference does not resolve to target: {row['reference']}",
            )
        current_links = _incoming_link_result(
            root,
            {source, target},
            row["reference"],
        )
        _validate_incoming_link_compatibility(
            root,
            row["reference"],
            row.get("incomingLinks"),
            current_links,
            resolved_location=target,
        )
    check_readme(root)
    return len(inventory["rows"])


def reopen_category_record(
    root: Path,
    archived_reference: str,
    successor_slug: str,
    current_data: bytes,
) -> Path:
    category, archived_slug = _canonical_category(archived_reference)
    _admission_for(category.name)
    if category.name == "work-item":
        return reopen_item(root, archived_slug, successor_slug, current_data)
    archived = resolve_category(root, archived_reference)
    if "archive" not in archived.parts:
        raise LifecycleError("WI-INVALID-TARGET", "reopen source must be archived")
    _validate_flat_terminal(category, archived.read_bytes())
    _validate_slug(successor_slug)
    if _category_locations(root, category, successor_slug):
        raise LifecycleError("WI-CATEGORY-DUAL-LOCATION", "successor slug already exists")
    try:
        text = current_data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LifecycleError("WI-CATEGORY-STATUS-INVALID", "successor must be UTF-8") from exc
    fields = _parse_fields(text)
    if fields.get("status") not in category.current_statuses:
        raise LifecycleError(
            "WI-CATEGORY-STATUS-INVALID",
            f"{category.name} successor status must be current",
        )
    if fields.get("reopens") != archived_slug:
        raise LifecycleError(
            "WI-CATEGORY-STATUS-INVALID",
            f"successor must declare Reopens: {archived_slug}",
        )
    _preflight_readme(root)
    target = _work_items_root(root) / category.current_root / f"{successor_slug}.md"
    _atomic_write(target, current_data)
    try:
        refresh_readme(root)
    except LifecycleError as exc:
        raise LifecycleError("WI-README-STALE", str(exc)) from exc
    return target


def _fixture_status(item: dict) -> str:
    return (
        "---\n"
        "template: staged\n"
        f"status: {item['status']}\n"
        "started: 2026-07-31T00:00:00Z\n"
        f"updated: {item['updated']}\n"
        "---\n\n"
        f"Task: {item['task']}\n"
        f"Current step: {item.get('currentStep', 'Continue.')}\n"
        "Last result: Fixture materialized.\n"
        f"Next action: {item.get('nextAction', 'Continue.')}\n"
        "Scope boundary: Trial fixture only.\n"
        "Owner: toolchain-engineer\n"
        "Integration owner: toolchain-engineer\n"
        "Evidence gate: five-item trial\n"
        + (f"Blocker: {item['blocker']}\n" if item.get("blocker") else "")
        + (f"Roadmap: {item['roadmap']}\n" if item.get("roadmap") else "")
        + (f"Epic: {item['epic']}\n" if item.get("epic") else "")
    )


def _trial_expected_files(fixture: dict) -> set[str]:
    expected = {
        "work-items/README.md",
    }
    supporting_epics = fixture.get("supportingEpics", [])
    if not isinstance(supporting_epics, list):
        raise LifecycleError("WI-TRIAL-FIXTURE", "supportingEpics must be a list")
    for epic in supporting_epics:
        if not isinstance(epic, dict) or not isinstance(epic.get("slug"), str):
            raise LifecycleError("WI-TRIAL-FIXTURE", "supporting epic requires a slug")
        _validate_slug(epic["slug"])
        expected.add(f"work-items/epics/{epic['slug']}.md")

    items = fixture.get("items")
    if not isinstance(items, list) or len(items) != 5:
        raise LifecycleError("WI-TRIAL-FIXTURE", "fixture must contain exactly five items")
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("slug"), str):
            raise LifecycleError("WI-TRIAL-FIXTURE", "trial item requires a slug")
        slug = item["slug"]
        _validate_slug(slug)
        kind = item.get("kind")
        if kind in {"active", "blocked"}:
            expected.add(f"work-items/active/{slug}/status.md")
        elif kind == "backlog":
            expected.add(f"work-items/backlog/{slug}.md")
        elif kind == "roadmap":
            expected.add(f"work-items/roadmaps/{slug}.md")
        elif kind == "archived":
            closed = item.get("closed")
            if not isinstance(closed, str):
                raise LifecycleError("WI-TRIAL-FIXTURE", "archived item requires Closed")
            expected.add(
                f"work-items/archive/{archive_month(closed)}/{slug}/closure.md"
            )
        else:
            raise LifecycleError("WI-TRIAL-FIXTURE", f"unknown trial kind: {kind}")
    return expected


def _trial_expected_directories(files: set[str]) -> set[str]:
    directories: set[str] = set()
    for value in files:
        parent = Path(value).parent
        while parent != Path("."):
            directories.add(parent.as_posix())
            parent = parent.parent
    return directories


def _trial_tree(root: Path) -> tuple[dict[str, str], set[str]]:
    files: dict[str, str] = {}
    directories: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise LifecycleError(
                "WI-TRIAL-NOT-OWNED",
                f"trial root contains an unowned symbolic link: {relative}",
            )
        if path.is_dir():
            directories.add(relative)
        elif path.is_file():
            if relative == TRIAL_MARKER:
                continue
            files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            raise LifecycleError(
                "WI-TRIAL-NOT-OWNED",
                f"trial root contains an unsupported entry: {relative}",
            )
    return files, directories


def _prove_completed_trial(
    root: Path,
    fixture_bytes: bytes,
    expected_files: set[str],
) -> None:
    marker_path = root / TRIAL_MARKER
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleError(
            "WI-TRIAL-NOT-OWNED",
            f"non-empty trial root lacks a valid ownership receipt: {root}",
        ) from exc
    expected_keys = {
        "schemaVersion",
        "owner",
        "fixtureSha256",
        "files",
        "directories",
    }
    if not isinstance(marker, dict) or set(marker) != expected_keys:
        raise LifecycleError("WI-TRIAL-NOT-OWNED", "trial ownership receipt shape differs")
    fixture_hash = hashlib.sha256(fixture_bytes).hexdigest()
    expected_directories = _trial_expected_directories(expected_files)
    if (
        marker.get("schemaVersion") != 1
        or marker.get("owner") != TRIAL_OWNER
        or marker.get("fixtureSha256") != fixture_hash
        or set(marker.get("files", {})) != expected_files
        or set(marker.get("directories", [])) != expected_directories
    ):
        raise LifecycleError(
            "WI-TRIAL-NOT-OWNED",
            "trial ownership receipt is not target-bound to this exact fixture/output",
        )
    actual_files, actual_directories = _trial_tree(root)
    if actual_files != marker["files"] or actual_directories != expected_directories:
        raise LifecycleError(
            "WI-TRIAL-NOT-OWNED",
            "trial root bytes or membership differ from the completed ownership receipt",
        )


def _write_trial_receipt(
    root: Path,
    fixture_bytes: bytes,
    expected_files: set[str],
) -> None:
    actual_files, actual_directories = _trial_tree(root)
    expected_directories = _trial_expected_directories(expected_files)
    if set(actual_files) != expected_files or actual_directories != expected_directories:
        raise LifecycleError(
            "WI-TRIAL-OUTPUT",
            "trial output membership differs from the owned five-item manifest",
        )
    receipt = {
        "schemaVersion": 1,
        "owner": TRIAL_OWNER,
        "fixtureSha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "files": actual_files,
        "directories": sorted(actual_directories),
    }
    _atomic_write(
        root / TRIAL_MARKER,
        (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )


def run_trial(root: Path, fixture_path: Path) -> tuple[str, str]:
    fixture_bytes = fixture_path.read_bytes()
    fixture = json.loads(fixture_bytes.decode("utf-8"))
    if not isinstance(fixture, dict):
        raise LifecycleError("WI-TRIAL-FIXTURE", "fixture must be an object")
    expected_files = _trial_expected_files(fixture)
    if root.exists() and any(root.iterdir()):
        _prove_completed_trial(root, fixture_bytes, expected_files)
    root.mkdir(parents=True, exist_ok=True)
    items = fixture.get("items")
    assert isinstance(items, list)
    work_items = _work_items_root(root)
    for epic in fixture.get("supportingEpics", []):
        _atomic_write(
            work_items / "epics" / f"{epic['slug']}.md",
            (
                "---\n"
                "status: active\n"
                f"updated: {epic['updated']}\n"
                "---\n\n"
                f"# {epic['title']}\n"
            ).encode("utf-8"),
        )
    for item in items:
        kind = item["kind"]
        slug = item["slug"]
        _validate_slug(slug)
        if kind in {"active", "blocked"}:
            _atomic_write(
                work_items / "active" / slug / "status.md",
                _fixture_status(item).encode("utf-8"),
            )
        elif kind == "backlog":
            _atomic_write(
                work_items / "backlog" / f"{slug}.md",
                (
                    f"Task: {item['task']}\n"
                    f"Next action: {item['nextAction']}\n"
                    f"updated: {item['updated']}\n"
                ).encode("utf-8"),
            )
        elif kind == "roadmap":
            _atomic_write(
                work_items / "roadmaps" / f"{slug}.md",
                (
                    "format: roadmap-v1\n"
                    "status: active\n"
                    "owner: product-manager\n"
                    f"outcomes: {item['outcomes']}\n"
                    f"order: {item['order']}\n"
                    f"milestones-or-horizon: {item['milestone']}\n"
                    "review-trigger: trial completion\n"
                    "retention: archive monthly\n"
                    f"updated: {item['updated']}\n"
                ).encode("utf-8"),
            )
        elif kind == "archived":
            _atomic_write(
                work_items
                / "archive"
                / archive_month(item["closed"])
                / slug
                / "closure.md",
                (
                    f"Closed: {item['closed']}\n"
                    f"Outcome: {item['outcome']}\n"
                    "Evidence: five-item trial\n"
                    f"Residual risk: {item['residualRisk']}\n"
                ).encode("utf-8"),
            )
        else:
            raise LifecycleError("WI-TRIAL-FIXTURE", f"unknown trial kind: {kind}")
    first = refresh_readme(root)
    first_bytes = (work_items / "README.md").read_bytes()
    second = refresh_readme(root)
    second_bytes = (work_items / "README.md").read_bytes()
    if first != second or first_bytes != second_bytes:
        raise LifecycleError("WI-README-NONDETERMINISTIC", "repeat render differs")
    text = second_bytes.decode("utf-8")
    checkbox_lines = [line for line in text.splitlines() if line.startswith("- [")]
    if len(checkbox_lines) != 5 or any(
        not (line.startswith("- [ ]") or line.startswith("- [x]")) for line in checkbox_lines
    ):
        raise LifecycleError("WI-TRIAL-COUNT", "trial did not render five canonical checkboxes")
    positions = [text.index(f"## {section}") for section in README_SECTIONS]
    if positions != sorted(positions):
        raise LifecycleError("WI-TRIAL-SECTIONS", "README section order differs")
    if not all(token in text for token in ("[roadmap](", "[epic](", "[work item](")):
        raise LifecycleError("WI-TRIAL-LINKS", "progressive links are incomplete")
    _write_trial_receipt(root, fixture_bytes, expected_files)
    return first, second


def _read_arg_file(path: str) -> bytes:
    return Path(path).read_bytes()


def _add_root(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default=".", help="Repository or work-items root")


def _add_injection(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--inject-readme-failure",
        choices=("after-canonical",),
        help=argparse.SUPPRESS,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("candidate", "start", "update", "close", "reopen"):
        command = sub.add_parser(name)
        _add_root(command)
        _add_injection(command)
        command.add_argument("--slug", required=True)
        if name == "candidate":
            command.add_argument("--file", required=True)
        elif name in {"start", "update"}:
            command.add_argument("--status-file", required=True)
        elif name == "close":
            command.add_argument("--closure-file", required=True)
            command.add_argument("--terminal-instant", required=True)
        else:
            command.add_argument("--successor-slug", required=True)
            command.add_argument("--status-file", required=True)
    convert_legacy = sub.add_parser("convert-legacy-candidate")
    _add_root(convert_legacy)
    _add_injection(convert_legacy)
    convert_legacy.add_argument("--slug", required=True)
    convert_legacy.add_argument("--file", required=True)
    retire_legacy = sub.add_parser("retire-legacy-backlog")
    _add_root(retire_legacy)
    _add_injection(retire_legacy)
    retire_legacy.add_argument("--slug", required=True)
    retire_legacy.add_argument("--disposition-file", required=True)
    retire_legacy.add_argument("--terminal-instant", required=True)
    refresh = sub.add_parser("refresh")
    _add_root(refresh)
    refresh.add_argument("--reset-static-guide", action="store_true")
    refresh.add_argument("--expected-readme-sha256")
    resolve = sub.add_parser("resolve")
    _add_root(resolve)
    target = resolve.add_mutually_exclusive_group(required=True)
    target.add_argument("--reference")
    target.add_argument("--legacy-path")
    audit_parser = sub.add_parser("audit")
    _add_root(audit_parser)
    audit_mode = audit_parser.add_mutually_exclusive_group()
    audit_mode.add_argument("--output")
    audit_mode.add_argument("--verify-migration")
    migrate = sub.add_parser("migrate")
    _add_root(migrate)
    migrate_mode = migrate.add_mutually_exclusive_group(required=True)
    migrate_mode.add_argument("--reference")
    migrate_mode.add_argument("--inventory")
    migrate.add_argument("--incoming-links-inventory")
    migrate.add_argument("--apply-admitted", action="store_true")
    migrate.add_argument("--render-readme", action="store_true")
    migrate.add_argument("--byte-check", action="store_true")
    terminalize = sub.add_parser("terminalize-v1")
    _add_root(terminalize)
    terminalize.add_argument("--inventory", required=True)
    terminalize.add_argument("--terminal-at", required=True)
    terminalize.add_argument("--authorization-marker", required=True)
    terminalize.add_argument("--receipt", required=True)
    normalize = sub.add_parser(
        "normalize-current-identity",
        help="Atomically replace one noncanonical current flat-record identity",
    )
    _add_root(normalize)
    normalize.add_argument("--category", required=True, help="Lifecycle category")
    normalize.add_argument(
        "--source",
        required=True,
        help="Repository-relative source path under work-items/",
    )
    normalize.add_argument(
        "--target-slug", required=True, help="Canonical replacement slug"
    )
    normalize.add_argument(
        "--inventory", required=True, help="Repository .scratch/ inventory path"
    )
    normalize.add_argument(
        "--receipt", help="Repository .scratch/ settled receipt path"
    )
    normalize.add_argument(
        "--prepare-only",
        action="store_true",
        help="Write the exact byte-bound inventory without mutating work-items",
    )
    normalize.add_argument(
        "--inject-failure-at",
        choices=("after-rewrites", "after-move", "after-readme"),
        help=argparse.SUPPRESS,
    )
    trial = sub.add_parser("trial")
    _add_root(trial)
    trial.add_argument("--fixture", required=True)
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root)
    try:
        if args.command == "candidate":
            result = create_candidate(
                root,
                args.slug,
                _read_arg_file(args.file),
                inject_readme_failure=bool(args.inject_readme_failure),
            )
            print(result)
        elif args.command == "convert-legacy-candidate":
            result = convert_legacy_candidate(
                root,
                args.slug,
                _read_arg_file(args.file),
                inject_readme_failure=bool(args.inject_readme_failure),
            )
            print(result)
        elif args.command == "retire-legacy-backlog":
            result = retire_legacy_backlog(
                root,
                args.slug,
                _read_arg_file(args.disposition_file),
                args.terminal_instant,
                inject_readme_failure=bool(args.inject_readme_failure),
            )
            print(result)
        elif args.command == "start":
            result = start_item(
                root,
                args.slug,
                _read_arg_file(args.status_file),
                inject_readme_failure=bool(args.inject_readme_failure),
            )
            print(result)
        elif args.command == "update":
            result = update_status(
                root,
                args.slug,
                _read_arg_file(args.status_file),
                inject_readme_failure=bool(args.inject_readme_failure),
            )
            print(result)
        elif args.command == "close":
            result = close_item(
                root,
                args.slug,
                _read_arg_file(args.closure_file),
                args.terminal_instant,
                inject_readme_failure=bool(args.inject_readme_failure),
            )
            print(result)
        elif args.command == "reopen":
            result = reopen_item(
                root,
                args.slug,
                args.successor_slug,
                _read_arg_file(args.status_file),
                inject_readme_failure=bool(args.inject_readme_failure),
            )
            print(result)
        elif args.command == "refresh":
            if args.reset_static_guide:
                if not args.expected_readme_sha256:
                    raise LifecycleError(
                        "WI-README-REPAIR-TARGET-MISMATCH",
                        "--reset-static-guide requires --expected-readme-sha256",
                    )
                readme_hash = reset_readme_static_guide(
                    root,
                    args.expected_readme_sha256,
                )
            else:
                if args.expected_readme_sha256:
                    raise LifecycleError(
                        "WI-README-REPAIR-TARGET-MISMATCH",
                        "--expected-readme-sha256 requires --reset-static-guide",
                    )
                readme_hash = refresh_readme(root)
            print(f"README-SHA256: {readme_hash}")
        elif args.command == "resolve":
            if args.reference:
                print(resolve_category(root, args.reference))
            else:
                print(f"WI-LEGACY-READ-COMPAT {resolve_legacy_path(root, args.legacy_path)}")
        elif args.command == "audit":
            if args.output:
                inventory = write_migration_inventory(root, Path(args.output))
                print(f"migration_rows={len(inventory['rows'])}")
            elif args.verify_migration:
                rows = verify_migration_inventory(
                    root, Path(args.verify_migration)
                )
                print(f"migration_rows={rows}")
            else:
                for legacy_path in audit(root):
                    print(f"{LEGACY_READ_CLASSIFICATION} {legacy_path}")
            print("AUDIT: PASS")
        elif args.command == "migrate":
            if args.inventory:
                if not (
                    args.apply_admitted
                    and args.render_readme
                    and args.byte_check
                ):
                    raise LifecycleError(
                        "WI-CATEGORY-MIGRATION-INVENTORY",
                        "inventory migration requires --apply-admitted, "
                        "--render-readme, and --byte-check",
                    )
                rows, readme_hash = apply_migration_inventory(
                    root,
                    Path(args.inventory),
                    render_readme=args.render_readme,
                    byte_check=args.byte_check,
                )
                print("MIGRATION: PASS")
                print(f"migration_rows={rows}")
                print("readme_byte_check=PASS")
                print("source_target_disjoint=PASS")
                if readme_hash:
                    print(f"readme_sha256={readme_hash}")
            else:
                if args.apply_admitted or args.render_readme or args.byte_check:
                    raise LifecycleError(
                        "WI-CATEGORY-MIGRATION-INVENTORY",
                        "bulk migration flags require --inventory",
                    )
                migrate_legacy(
                    root,
                    args.reference,
                    incoming_links_inventory=(
                        Path(args.incoming_links_inventory)
                        if args.incoming_links_inventory
                        else None
                    ),
                )
        elif args.command == "terminalize-v1":
            rows, replay = terminalize_v1_inventory(
                root,
                Path(args.inventory),
                terminal_at=args.terminal_at,
                authorization_marker=args.authorization_marker,
                receipt_path=Path(args.receipt),
            )
            if replay:
                print(f"TERMINALIZE-V1: PASS rows={rows} replay=true")
            else:
                print(
                    f"TERMINALIZE-V1: PASS rows={rows} "
                    f"marker={args.authorization_marker}"
                )
        elif args.command == "normalize-current-identity":
            if args.prepare_only:
                if args.receipt:
                    raise LifecycleError(
                        "WI-IDENTITY-NORMALIZE-INVENTORY",
                        "--prepare-only does not accept --receipt",
                    )
                inventory = write_current_identity_normalization_inventory(
                    root,
                    args.category,
                    args.source,
                    args.target_slug,
                    Path(args.inventory),
                )
                print(f"NORMALIZE-CURRENT-IDENTITY: INVENTORY rows={len(inventory['rows'])}")
            else:
                if not args.receipt:
                    raise LifecycleError(
                        "WI-IDENTITY-NORMALIZE-INVENTORY",
                        "normalization apply requires --receipt",
                    )
                target, replay = normalize_current_identity(
                    root,
                    args.category,
                    args.source,
                    args.target_slug,
                    Path(args.inventory),
                    Path(args.receipt),
                    inject_failure_at=args.inject_failure_at,
                )
                print(
                    "NORMALIZE-CURRENT-IDENTITY: PASS "
                    f"target={target} replay={'true' if replay else 'false'}"
                )
        elif args.command == "trial":
            first, second = run_trial(root, Path(args.fixture))
            print("TRIAL: PASS")
            print("items=5")
            print(f"sections={'|'.join(README_SECTIONS)}")
            print(f"readme_sha256_1={first}")
            print(f"readme_sha256_2={second}")
        return 0
    except LifecycleError as exc:
        print(f"{exc.failure_id}: {exc}")
        return 1
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"WI-IO: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
