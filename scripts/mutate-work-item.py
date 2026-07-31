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
V1_TERMINALIZATION_SCHEMA_VERSION = 1
V1_TERMINALIZATION_AUTHORIZATION = "operator-authorized-v1-terminalization"
V1_TERMINALIZATION_FAILURE = "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"
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
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
OPTIONAL_RELATION_ABSENCE_MARKERS = frozenset({"none"})
FIELD_RE = re.compile(
    r"^\s*(?:-\s*)?(?:\*\*)?([A-Za-z][A-Za-z0-9 -]*?)(?:\*\*)?\s*:\s*(.*?)\s*$"
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


def _work_items_root(root: Path) -> Path:
    root = root.resolve()
    return root if root.name == "work-items" else root / "work-items"


def _validate_slug(slug: str) -> None:
    if not SLUG_RE.fullmatch(slug):
        raise LifecycleError("WI-INVALID-SLUG", f"invalid bare slug: {slug!r}")


def _parse_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        match = FIELD_RE.fullmatch(line)
        if match:
            fields[match.group(1).strip().casefold()] = match.group(2).strip()
    return fields


def _terminalization_authoritative_field_occurrences(text: str) -> tuple[str, ...]:
    authoritative = {"terminal-at", "v1-migration-evidence"}
    occurrences: list[str] = []
    for line in text.splitlines():
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
    for line in text.splitlines():
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


def _archived_work_item_entry(item: Path) -> ReadmeEntry:
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


def start_item(root: Path, slug: str, status_data: bytes, *, inject_readme_failure: bool = False) -> Path:
    _validate_slug(slug)
    _validate_active_status_bytes(status_data)
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


def audit_categories(root: Path) -> None:
    work_items = _work_items_root(root)
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
def audit(root: Path) -> None:
    audit_categories(root)
    check_readme(root)


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
    utc_field = "closed" if category.name == "epic" else "terminal-at"
    evidence_fields = {
        "bug": ("resolution", "evidence"),
        "decision": ("rationale", "evidence"),
        "lesson": ("disposition", "evidence"),
        "roadmap": ("disposition", "evidence"),
        "epic": ("outcome", "evidence"),
    }[category.name]
    missing = [name for name in (utc_field, *evidence_fields) if not fields.get(name)]
    if missing:
        raise LifecycleError(
            "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
            f"{category.name} terminal record missing: {', '.join(missing)}",
        )
    _strict_utc(fields[utc_field])
    return fields[utc_field]


CATEGORY_ADMISSION_TABLE = (
    CategoryAdmission(
        "work-item",
        "mutate-work-item:_category_locations",
        "mutate-work-item:_validate_closure",
        "closure.md:Closed",
        "work_item_terminal_evidence_missing",
    ),
    CategoryAdmission(
        "bug",
        "mutate-work-item:_category_locations",
        "mutate-work-item:_validate_flat_terminal",
        "bug:Terminal-at",
        "bug_terminal_evidence_missing",
    ),
    CategoryAdmission(
        "decision",
        "mutate-work-item:_category_locations",
        "mutate-work-item:_validate_flat_terminal",
        "decision:Terminal-at",
        "decision_terminal_evidence_missing",
    ),
    CategoryAdmission(
        "lesson",
        "mutate-work-item:_category_locations",
        "mutate-work-item:_validate_flat_terminal",
        "lesson:Terminal-at",
        "lesson_terminal_evidence_missing",
    ),
    CategoryAdmission(
        "roadmap",
        "mutate-work-item:_category_locations",
        "mutate-work-item:_validate_flat_terminal",
        "roadmap:Terminal-at",
        "roadmap_terminal_evidence_missing",
    ),
    CategoryAdmission(
        "epic",
        "mutate-work-item:_category_locations",
        "mutate-work-item:_validate_flat_terminal",
        "epic:Closed",
        "epic_terminal_evidence_missing",
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


MARKDOWN_LINK_RE = re.compile(r"\]\(\s*<?([^)>#?\s]+)")


def _incoming_link_result(
    root: Path,
    owned_paths: Iterable[Path],
    reference: str,
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
            text = consumer.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        consumer_rel = consumer.relative_to(work_items).as_posix()
        if reference in text:
            logical.append(
                {"consumer": consumer_rel, "kind": "logical", "value": reference}
            )
        for match in MARKDOWN_LINK_RE.finditer(text):
            raw = match.group(1)
            if "://" in raw or raw.startswith("#"):
                continue
            candidate = (consumer.parent / raw).resolve()
            if belongs_to_owned(candidate):
                physical.append(
                    {"consumer": consumer_rel, "kind": "physical", "value": raw}
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


def _validate_incoming_link_compatibility(
    root: Path,
    reference: str,
    planned: dict,
    current: dict,
    *,
    resolved_location: Path,
) -> None:
    for label, snapshot in (("planned", planned), ("current", current)):
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
                    f"{label} incoming link is not category-qualified logical "
                    f"for {reference}",
                )
            identity = (
                link["consumer"],
                link["kind"],
                link["value"],
            )
            if identity in seen:
                raise LifecycleError(
                    "WI-LEGACY-LINK-UNMAPPED",
                    f"{label} incoming-link inventory repeats a row for {reference}",
                )
            seen.add(identity)
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


def _terminalization_receipt_path(path: Path) -> Path:
    resolved = path.resolve()
    if ".scratch" not in resolved.parts:
        raise _terminalization_fail(
            "terminalization receipt must be caller-specified under .scratch"
        )
    return resolved


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
    for row in receipt_rows:
        if not isinstance(row, dict):
            raise _terminalization_fail(
                "existing terminalization receipt contains an invalid row"
            )
        source = _bound_inventory_path(work_items, row.get("source"))
        if (
            not source.is_file()
            or row.get("afterSha256")
            != hashlib.sha256(source.read_bytes()).hexdigest()
        ):
            raise _terminalization_fail(
                f"terminalized payload differs from receipt: {row.get('reference')}"
            )
    return len(receipt_rows), True


def _preflight_v1_terminalization_rows(
    root: Path,
    inventory: dict,
    terminal_at: str,
) -> list[dict]:
    _strict_utc(terminal_at)
    work_items = _work_items_root(root)
    planned: list[dict] = []
    seen_sources: set[Path] = set()
    for row in inventory["rows"]:
        if not isinstance(row, dict):
            raise _terminalization_fail("terminalization inventory row is not an object")
        category_name = row.get("category")
        if category_name not in {"bug", "decision"}:
            raise _terminalization_fail(
                f"unsupported V1 terminalization category: {category_name!r}"
            )
        try:
            category, slug = _canonical_category(row.get("reference", ""))
        except LifecycleError as exc:
            raise _terminalization_fail(str(exc)) from exc
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
        if not isinstance(incoming, dict) or incoming.get("result") not in {
            "clear",
            "logical-only",
        }:
            raise _terminalization_fail(
                f"incoming links are not admitted for {row.get('reference')}"
            )
        if row.get("target") is not None or row.get("terminalInstant") is not None:
            raise _terminalization_fail(
                f"denied row already has a target or terminal instant: "
                f"{row.get('reference')}"
            )
        source = _bound_inventory_path(work_items, row.get("source"))
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
        detail_field = "Resolution" if category_name == "bug" else "Rationale"
        conflicting = tuple(
            dict.fromkeys(_terminalization_authoritative_field_occurrences(text))
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
        if current_links != incoming:
            raise _terminalization_fail(
                f"incoming-link inventory changed for {row.get('reference')}"
            )
        separator = b"\n" if before.endswith(b"\n") else b"\n\n"
        proof = (
            "Historical terminal time is unknown; preserved pre-V1 input "
            f"SHA-256 `{before_sha256}`; original terminal status `{status}`; "
            "explicit operator-authorized V1 migration."
        )
        appended_lines = [f"Terminal-at: {terminal_at}"]
        if not fields.get(detail_field.casefold()):
            appended_lines.append(
                f"{detail_field}: Pre-V1 terminal status `{status}` is preserved "
                "during operator-authorized V1 physical migration."
            )
        if not fields.get("evidence"):
            appended_lines.append(f"Evidence: {proof}")
        appended_lines.append(f"V1-Migration-Evidence: {proof}")
        appended = ("\n".join(appended_lines) + "\n").encode("utf-8")
        after = before + separator + appended
        planned.append(
            {
                "reference": row["reference"],
                "sourceRelative": row["source"],
                "source": source,
                "status": status,
                "before": before,
                "beforeSha256": before_sha256,
                "after": after,
                "afterSha256": hashlib.sha256(after).hexdigest(),
            }
        )
    return sorted(planned, key=lambda item: item["reference"])


def terminalize_v1_inventory(
    root: Path,
    inventory_path: Path,
    *,
    terminal_at: str,
    authorization_marker: str,
    receipt_path: Path,
    inject_failure_after: int | None = None,
) -> tuple[int, bool]:
    """Add V1 terminal evidence transactionally; never move canonical records."""
    if authorization_marker != V1_TERMINALIZATION_AUTHORIZATION:
        raise _terminalization_fail(
            "explicit operator-authorized V1 terminalization marker is required"
        )
    _strict_utc(terminal_at)
    receipt = _terminalization_receipt_path(receipt_path)
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
    planned = _preflight_v1_terminalization_rows(root, inventory, terminal_at)
    receipt_payload = {
        "schemaVersion": V1_TERMINALIZATION_SCHEMA_VERSION,
        "owner": V1_TERMINALIZATION_OWNER,
        "workItemsRoot": str(_work_items_root(root).resolve()),
        "inventorySha256": inventory_sha256,
        "terminalAt": terminal_at,
        "authorizationMarker": authorization_marker,
        "rowCount": len(planned),
        "rows": [
            {
                "reference": item["reference"],
                "source": item["sourceRelative"],
                "originalStatus": item["status"],
                "beforeSha256": item["beforeSha256"],
                "afterSha256": item["afterSha256"],
            }
            for item in planned
        ],
    }
    receipt_bytes = (
        json.dumps(receipt_payload, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    written: list[dict] = []
    try:
        for index, item in enumerate(planned, start=1):
            if item["source"].read_bytes() != item["before"]:
                raise _terminalization_fail(
                    f"payload changed after preflight: {item['reference']}"
                )
            _atomic_write(item["source"], item["after"])
            written.append(item)
            if inject_failure_after == index:
                raise _terminalization_fail(
                    f"injected terminalization failure after row {index}"
                )
        _atomic_write(receipt, receipt_bytes)
    except Exception as exc:
        rollback_failures: list[str] = []
        for item in reversed(written):
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
        "work-items/index.md",
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
    _atomic_write(work_items / "index.md", b"# Compatibility snapshot only\n\nignored\n")
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
                audit(root)
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
