#!/usr/bin/env python3
"""Resolve non-authorizing Orchestrarium instruction overlays for one agent lane."""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
MAX_CATALOG_BYTES = 256 * 1024
MAX_POLICY_BYTES = 128 * 1024
MAX_CONFIG_BYTES = 64 * 1024
MAX_RENDERED_BYTES = 256 * 1024
MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 8192
OVERLAY_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")
LANE_ID = re.compile(r"[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*\Z")
PROVIDERS = frozenset({"codex", "claude", "kimi"})
TARGETS = frozenset(
    {"main-agent", "internal-subagent", "external-worker", "external-reviewer", "consultant"}
)
PROVIDER_TARGETS = {
    "codex": TARGETS,
    "claude": TARGETS,
    "kimi": frozenset({"external-reviewer"}),
}
PROPAGATION_KEY = {
    "main-agent": "mainAgent",
    "internal-subagent": "internalSubagent",
    "external-worker": "externalWorker",
    "external-reviewer": "externalReviewer",
    "consultant": "consultant",
}
PRECEDENCE = (
    "hard-governance-and-safety",
    "explicit-user-requirements",
    "role-contract",
    "project-policy",
    "optional-policy-overlays",
    "task-prompt",
)
FRAME_BEGIN = "ORCHESTRARIUM_OPTIONAL_POLICY_OVERLAYS_V1"
FRAME_END = "END_ORCHESTRARIUM_OPTIONAL_POLICY_OVERLAYS_V1"
RESERVED_MARKERS = (FRAME_BEGIN, FRAME_END, "BEGIN_POLICY_OVERLAY", "END_POLICY_OVERLAY")
USER_KEY = "policyOverlays"
ALLOW_KEY = "allowedPolicyOverlays"
DENY_KEY = "deniedPolicyOverlays"
LIST_LINE = re.compile(r"^(?P<key>[A-Za-z][A-Za-z0-9]*):\s*\[(?P<items>[^\]]*)\]\s*(?:#.*)?$")
KEY_LINE = re.compile(r"^(?P<key>[A-Za-z][A-Za-z0-9]*):")


class PolicyOverlayError(RuntimeError):
    """Fail-closed overlay input or projection error."""


class DuplicateJsonKeyError(ValueError):
    """Raised when a catalog object repeats a key."""


class InvalidJsonStructureError(ValueError):
    """Raised when catalog JSON is non-standard or exceeds shape limits."""


@dataclass(frozen=True)
class ResolvedPolicyOverlay:
    overlay_id: str
    source_kind: str
    instruction_path: str
    instructions: str
    authorizing: bool
    provider: str
    lane: str
    target: str


def _is_reparse(info: os.stat_result) -> bool:
    return bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _ordinary_dir(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    return stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode) and not _is_reparse(info)


def _file_signature(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_size,
        getattr(info, "st_mtime_ns", 0),
        getattr(info, "st_ctime_ns", 0),
        getattr(info, "st_file_attributes", 0),
    )


def _read_regular(path: Path, limit: int, *, label: str) -> bytes:
    fd = -1
    try:
        before = path.lstat()
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or _is_reparse(before)
            or before.st_size > limit
        ):
            raise PolicyOverlayError(f"{label} must be a bounded ordinary file: {path}")
        flags = (
            os.O_RDONLY | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        )
        fd = os.open(path, flags)
        opened = os.fstat(fd)
        if _file_signature(before) != _file_signature(opened):
            raise PolicyOverlayError(f"{label} changed while opening: {path}")
        chunks: list[bytes] = []
        size = 0
        while True:
            chunk = os.read(fd, min(64 * 1024, limit + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > limit:
                raise PolicyOverlayError(f"{label} exceeds {limit} bytes: {path}")
        if (
            _file_signature(opened) != _file_signature(os.fstat(fd))
            or _file_signature(opened) != _file_signature(path.lstat())
        ):
            raise PolicyOverlayError(f"{label} changed while reading: {path}")
        return b"".join(chunks)
    except OSError as exc:
        raise PolicyOverlayError(f"cannot read {label} {path}: {exc}") from exc
    finally:
        if fd >= 0:
            os.close(fd)


def _root(policy_root: Path | None) -> Path:
    candidate = Path(policy_root) if policy_root is not None else Path(__file__).resolve().parents[1]
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise PolicyOverlayError(f"cannot resolve policy-overlay root {candidate}: {exc}") from exc
    if not _ordinary_dir(candidate) or not _ordinary_dir(resolved):
        raise PolicyOverlayError(f"policy-overlay root is not an ordinary directory: {candidate}")
    return resolved


def _contained(root: Path, relative: str, *, label: str, limit: int) -> tuple[Path, bytes]:
    if (
        not isinstance(relative, str)
        or not relative
        or "\x00" in relative
        or "\\" in relative
        or relative.startswith("/")
    ):
        raise PolicyOverlayError(f"invalid instruction path for {label}: {relative!r}")
    parts = relative.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise PolicyOverlayError(f"invalid instruction path for {label}: {relative!r}")
    current = root
    for part in parts:
        current /= part
        if current.exists() or current.is_symlink():
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
                raise PolicyOverlayError(f"{label} path contains a link: {current}")
    try:
        resolved = current.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise PolicyOverlayError(f"instruction path for {label} escapes its root: {relative}") from exc
    return resolved, _read_regular(resolved, limit, label=label)


def _optional(base: Path, relative: str, *, label: str) -> Path | None:
    try:
        base = Path(base).resolve(strict=True)
    except OSError as exc:
        raise PolicyOverlayError(f"cannot inspect {label} base {base}: {exc}") from exc
    if not _ordinary_dir(base):
        raise PolicyOverlayError(f"{label} base is not an ordinary directory: {base}")
    current = base
    parts = Path(relative).parts
    for index, part in enumerate(parts):
        current /= part
        if not (current.exists() or current.is_symlink()):
            return None
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
            raise PolicyOverlayError(f"{label} path contains a link: {current}")
        if index < len(parts) - 1 and not stat.S_ISDIR(info.st_mode):
            raise PolicyOverlayError(f"{label} parent is not a directory: {current}")
    try:
        resolved = current.resolve(strict=True)
        resolved.relative_to(base)
    except (OSError, ValueError) as exc:
        raise PolicyOverlayError(f"{label} path escapes its base: {current}") from exc
    _read_regular(resolved, MAX_CONFIG_BYTES, label=label)
    return resolved


def _ids(value: Any, *, label: str, allowed: frozenset[str] | None = None, pattern=None) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item for item in value)
        or len(value) != len(set(value))
    ):
        raise PolicyOverlayError(f"{label} must be a non-empty unique string array")
    result = tuple(value)
    if allowed is not None and any(item not in allowed for item in result):
        raise PolicyOverlayError(f"{label} contains unsupported values: {result!r}")
    if pattern is not None and any(not pattern.fullmatch(item) for item in result):
        raise PolicyOverlayError(f"{label} contains invalid identifiers: {result!r}")
    return result


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(key)
        result[key] = value
    return result


def _parse_json(text: str) -> object:
    def reject_constant(value: str) -> None:
        raise InvalidJsonStructureError(f"non-standard JSON constant: {value}")

    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_constant=reject_constant,
        )
    except RecursionError as exc:
        raise InvalidJsonStructureError("maximum parser depth exceeded") from exc

    stack: list[tuple[object, int]] = [(parsed, 1)]
    observed_nodes = 0
    while stack:
        value, depth = stack.pop()
        observed_nodes += 1
        if depth > MAX_JSON_DEPTH or observed_nodes > MAX_JSON_NODES:
            raise InvalidJsonStructureError("catalog JSON shape exceeds limits")
        if isinstance(value, dict):
            stack.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list):
            stack.extend((item, depth + 1) for item in value)
    return parsed


def _load_catalog(root: Path) -> dict[str, dict[str, Any]]:
    _, raw = _contained(root, "policy-overlays.v1.json", label="policy overlay catalog", limit=MAX_CATALOG_BYTES)
    try:
        data = _parse_json(raw.decode("utf-8", errors="strict"))
    except DuplicateJsonKeyError as exc:
        raise PolicyOverlayError(
            f"invalid policy overlay catalog: duplicate JSON key {exc.args[0]!r}"
        ) from exc
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        InvalidJsonStructureError,
        ValueError,
    ) as exc:
        raise PolicyOverlayError(f"invalid policy overlay catalog: {exc}") from exc
    if not isinstance(data, dict) or set(data) != {
        "schemaVersion", "defaultSelection", "selectionSyntax", "conflictPolicy",
        "precedence", "overlays", "compatibilityPackages",
    }:
        raise PolicyOverlayError("policy overlay catalog fields are invalid")
    if (
        type(data["schemaVersion"]) is not int
        or data["schemaVersion"] != SCHEMA_VERSION
        or data["defaultSelection"] != "none"
    ):
        raise PolicyOverlayError("policy overlay catalog version/default is invalid")
    if data["selectionSyntax"] != "comma-separated-identifiers-v1" or data["conflictPolicy"] != "reject-selection":
        raise PolicyOverlayError("policy overlay selection/conflict contract is invalid")
    if not isinstance(data["precedence"], list) or tuple(data["precedence"]) != PRECEDENCE:
        raise PolicyOverlayError("policy overlay precedence contract is invalid")
    compatibility = data["compatibilityPackages"]
    ponytail = compatibility.get("ponytail") if isinstance(compatibility, dict) else None
    if ponytail != {
        "repository": "DietrichGebert/ponytail",
        "ownership": "external-host-managed",
        "required": False,
    }:
        raise PolicyOverlayError("Ponytail compatibility declaration is invalid")

    raw_overlays = data["overlays"]
    if not isinstance(raw_overlays, dict) or not raw_overlays:
        raise PolicyOverlayError("overlays must be a non-empty object")
    result: dict[str, dict[str, Any]] = {}
    for overlay_id, record in raw_overlays.items():
        if not isinstance(overlay_id, str) or not OVERLAY_ID.fullmatch(overlay_id):
            raise PolicyOverlayError(f"invalid overlay id: {overlay_id!r}")
        if not isinstance(record, dict) or set(record) != {
            "source", "providers", "lanes", "targets", "propagation", "conflicts", "order", "authorizing"
        }:
            raise PolicyOverlayError(f"invalid overlay record: {overlay_id}")
        source = record["source"]
        if not isinstance(source, dict) or set(source) != {"kind", "path"} or source.get("kind") != "builtin":
            raise PolicyOverlayError(f"invalid overlay source: {overlay_id}")
        path = source.get("path")
        if not isinstance(path, str):
            raise PolicyOverlayError(f"invalid overlay source path: {overlay_id}")
        _contained(root, path, label=f"{overlay_id} instructions", limit=MAX_POLICY_BYTES)
        providers = _ids(record["providers"], label=f"{overlay_id}.providers", allowed=PROVIDERS)
        lanes = _ids(record["lanes"], label=f"{overlay_id}.lanes", pattern=LANE_ID)
        targets = _ids(record["targets"], label=f"{overlay_id}.targets", allowed=TARGETS)
        if record["authorizing"] is not False:
            raise PolicyOverlayError(f"optional overlay may not be authorizing: {overlay_id}")
        if any(not any(target in PROVIDER_TARGETS[p] for target in targets) for p in providers):
            raise PolicyOverlayError(f"overlay has no supported provider target: {overlay_id}")
        propagation = record["propagation"]
        if (
            not isinstance(propagation, dict)
            or set(propagation) != set(PROPAGATION_KEY.values())
            or any(
                not isinstance(value, str)
                or value not in {"lane-filtered", "explicit-only", "never"}
                for value in propagation.values()
            )
        ):
            raise PolicyOverlayError(f"invalid propagation contract: {overlay_id}")
        if any((target in targets) == (propagation[key] == "never") for target, key in PROPAGATION_KEY.items()):
            raise PolicyOverlayError(f"overlay target/propagation mismatch: {overlay_id}")
        conflicts = record["conflicts"]
        if (
            not isinstance(conflicts, list)
            or any(not isinstance(item, str) or not OVERLAY_ID.fullmatch(item) for item in conflicts)
            or len(conflicts) != len(set(conflicts))
            or overlay_id in conflicts
        ):
            raise PolicyOverlayError(f"invalid overlay conflicts: {overlay_id}")
        order = record["order"]
        if type(order) is not int or order < 0:
            raise PolicyOverlayError(f"invalid overlay order: {overlay_id}")
        result[overlay_id] = {
            "source": {"kind": "builtin", "path": path},
            "providers": providers, "lanes": lanes, "targets": targets,
            "propagation": dict(propagation), "conflicts": tuple(conflicts),
            "order": order, "authorizing": False,
        }
    if len({record["order"] for record in result.values()}) != len(result):
        raise PolicyOverlayError("policy overlay order values must be unique")
    for overlay_id, record in result.items():
        for conflict in record["conflicts"]:
            if conflict not in result or overlay_id not in result[conflict]["conflicts"]:
                raise PolicyOverlayError(f"invalid or asymmetric conflict: {overlay_id}/{conflict}")
    return result


__all__ = (
    "SCHEMA_VERSION",
    "MAX_CATALOG_BYTES",
    "MAX_POLICY_BYTES",
    "MAX_CONFIG_BYTES",
    "MAX_RENDERED_BYTES",
    "MAX_JSON_DEPTH",
    "MAX_JSON_NODES",
    "OVERLAY_ID",
    "LANE_ID",
    "PROVIDERS",
    "TARGETS",
    "PROVIDER_TARGETS",
    "PROPAGATION_KEY",
    "PRECEDENCE",
    "FRAME_BEGIN",
    "FRAME_END",
    "RESERVED_MARKERS",
    "USER_KEY",
    "ALLOW_KEY",
    "DENY_KEY",
    "LIST_LINE",
    "KEY_LINE",
    "PolicyOverlayError",
    "DuplicateJsonKeyError",
    "InvalidJsonStructureError",
    "ResolvedPolicyOverlay",
    "_is_reparse",
    "_ordinary_dir",
    "_file_signature",
    "_read_regular",
    "_root",
    "_contained",
    "_optional",
    "_ids",
    "_strict_object",
    "_parse_json",
    "_load_catalog",
)
