#!/usr/bin/env python3
"""Fail-closed parity validation for generated provider-prompt projections."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
import stat
import sys
import types
from pathlib import Path
from typing import Any, Sequence


STABLE_ID = "E_TRANSPORT_PROJECTION_PARITY"
SCHEMA_VERSION = 1
TRANSPORT_FILES = (
    "provider_prompt.py",
    "invoke-codex-prompt.py",
    "invoke-claude-prompt.py",
    "invoke-kimi-prompt.py",
    "invoke-grok-prompt.py",
    "external-prompt-governance.md",
)
EXTERNAL_GOVERNANCE_BEGIN = "<!-- BEGIN ORCHESTRARIUM EXTERNAL GOVERNANCE V1 -->"
EXTERNAL_GOVERNANCE_END = "<!-- END ORCHESTRARIUM EXTERNAL GOVERNANCE V1 -->"
_TOP_KEYS = frozenset({"schemaVersion", "packRevision", "files"})
_FILE_KEYS = frozenset({"source", "sha256", "destination"})
_AUTHORED_SOURCE_PATHS = {
    name: Path("scripts") / name for name in TRANSPORT_FILES
}
_AUTHORED_SOURCE_PATHS["external-prompt-governance.md"] = (
    Path("shared") / "external-prompt-governance.md"
)
_PACKED_RUNTIME_DESTINATIONS = {
    name: Path("scripts") / name for name in TRANSPORT_FILES
}
_CROSS_HOST_MARKERS = (
    "from scripts.provider_prompt",
    "src.claude/agents/scripts/provider_prompt",
    "src.codex/skills/lead/scripts/provider_prompt",
)
_LINKED_RUNTIME_SUBROOTS_SHA256 = (
    "a2194fcb49b26e354552279d03b00e2e3bf1231268e0948070949fc411a8a432"
)


class ProjectionParityError(ValueError):
    """One projection is absent, drifted, or outside its manifest contract."""


@dataclass
class _BoundOrdinaryFile:
    """A no-follow descriptor bound to the path identity checked before opening."""

    path: Path
    descriptor: int
    identity: tuple[int, int, int, int]

    def read_bytes(self) -> bytes:
        chunks: list[bytes] = []
        while True:
            chunk = os.read(self.descriptor, 1024 * 1024)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)

    def close(self) -> None:
        os.close(self.descriptor)


def _fail(detail: str) -> ProjectionParityError:
    return ProjectionParityError(f"{STABLE_ID}: {detail}")


def _is_reparse(metadata: os.stat_result) -> bool:
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(metadata, "st_file_attributes", 0) & flag)


def _identity(metadata: os.stat_result) -> tuple[int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        getattr(metadata, "st_file_attributes", 0),
    )


def _walk_ordinary_components(path: Path, label: str) -> None:
    absolute = Path(os.path.abspath(path))
    chain = tuple(reversed((absolute, *absolute.parents)))
    for component in chain:
        try:
            metadata = component.lstat()
        except OSError as exc:
            raise _fail(f"{label} component is missing or unreadable") from exc
        if stat.S_ISLNK(metadata.st_mode) or _is_reparse(metadata):
            raise _fail(f"{label} component is a symlink or reparse point")


def _open_ordinary_leaf(path: Path, label: str) -> _BoundOrdinaryFile:
    """Bind one ordinary regular leaf without following a changed identity."""

    path = Path(path)
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise _fail(f"{label} is missing or unreadable") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or _is_reparse(metadata)
    ):
        raise _fail(f"{label} is missing or not an ordinary file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise _fail(f"{label} cannot open without following links") from exc
    try:
        opened = os.fstat(descriptor)
        if _identity(metadata) != _identity(opened):
            raise _fail(f"{label} identity changed while opening")
        return _BoundOrdinaryFile(path, descriptor, _identity(opened))
    except BaseException:
        os.close(descriptor)
        raise


def _open_ordinary_file(path: Path, label: str) -> _BoundOrdinaryFile:
    """Open one fully ordinary path without following a changed leaf identity."""

    path = Path(path)
    _walk_ordinary_components(path, label)
    return _open_ordinary_leaf(path, label)


def _load_manifest(path: Path) -> dict[str, Any]:
    bound = _open_ordinary_file(path, "manifest")
    try:
        raw = bound.read_bytes()
    except OSError as exc:
        raise _fail("manifest cannot be read from its bound handle") from exc
    finally:
        bound.close()
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _fail("manifest is not valid UTF-8 JSON") from exc
    if not isinstance(manifest, dict) or set(manifest) != _TOP_KEYS:
        raise _fail("manifest top-level shape")
    if manifest.get("schemaVersion") != SCHEMA_VERSION:
        raise _fail("manifest schema version")
    revision = manifest.get("packRevision")
    if not isinstance(revision, str) or not revision.strip():
        raise _fail("manifest pack revision")
    files = manifest.get("files")
    if not isinstance(files, dict) or tuple(files) != TRANSPORT_FILES:
        raise _fail("manifest must bind the complete ordered transport set")
    return manifest


def _validate_record(name: str, record: Any) -> tuple[Path, Path, str]:
    if not isinstance(record, dict) or set(record) != _FILE_KEYS:
        raise _fail(f"manifest record shape for {name}")
    expected_source = _AUTHORED_SOURCE_PATHS[name]
    expected_destination = _PACKED_RUNTIME_DESTINATIONS[name]
    digest = record.get("sha256")
    if (
        record.get("source") != expected_source.as_posix()
        or record.get("destination") != expected_destination.as_posix()
        or not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise _fail(f"manifest binding for {name}")
    return expected_source, expected_destination, digest


def _validate_bound_bytes(
    bound: _BoundOrdinaryFile, expected_digest: str, label: str
) -> None:
    try:
        payload = bound.read_bytes()
    except OSError as exc:
        raise _fail(f"{label} cannot be read from its bound handle") from exc
    if hashlib.sha256(payload).hexdigest() != expected_digest:
        raise _fail(f"{label} digest drift")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _fail(f"{label} is not UTF-8") from exc
    if any(marker in text for marker in _CROSS_HOST_MARKERS):
        raise _fail(f"{label} cross-host import")


def _read_bound_bytes(path: Path, label: str) -> bytes:
    bound = _open_ordinary_file(path, label)
    try:
        return bound.read_bytes()
    except OSError as exc:
        raise _fail(f"{label} cannot be read from its bound handle") from exc
    finally:
        bound.close()


def _same_lexical_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(
        os.path.abspath(right)
    )


def _linked_runtime_subroots_module() -> Any:
    """Load the installed sibling that owns linked global-runtime authority."""

    path = Path(__file__).with_name("linked_runtime_subroots.py")
    bound = _open_ordinary_file(path, "Claude linked runtime authority")
    try:
        payload = bound.read_bytes()
    except OSError as exc:
        raise _fail("Claude linked runtime authority cannot be read from its bound handle") from exc
    finally:
        bound.close()
    if hashlib.sha256(payload).hexdigest() != _LINKED_RUNTIME_SUBROOTS_SHA256:
        raise _fail("Claude linked runtime authority digest drift")

    module_name = "_orchestrarium_provider_prompt_linked_runtime_subroots"
    module = types.ModuleType(module_name)
    module.__file__ = str(path)
    sys.modules[module_name] = module
    try:
        exec(compile(payload, str(path), "exec"), module.__dict__)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        raise _fail("Claude linked runtime authority is unavailable") from exc
    return module


def _bind_global_claude_agents_authority(install_root: Path) -> Any | None:
    """Bind only the installer-approved global logical Claude agents root."""

    logical_root = Path(install_root) / ".claude" / "agents"
    try:
        return _linked_runtime_subroots_module().LinkedRuntimeSubrootAuthority.bind(
            logical_root,
            scope="global",
            trusted_global_roots=(logical_root,),
        )
    except (AttributeError, OSError, ValueError) as exc:
        raise _fail("Claude linked runtime authority is unavailable") from exc


def _assert_current_claude_agents_authority(authority: Any) -> None:
    try:
        authority.assert_current()
    except (OSError, ValueError) as exc:
        raise _fail("Claude linked runtime authority changed") from exc


def _open_projection_file(
    projection_root: Path,
    label: str,
    name: str,
    claude_agents_authority: Any | None,
) -> _BoundOrdinaryFile:
    if claude_agents_authority is None:
        return _open_ordinary_file(projection_root / name, f"{label}/{name}")
    if label != "claude-host":
        raise _fail("linked Claude authority was assigned to a non-Claude projection")
    try:
        leaf = claude_agents_authority.ordinary_file(Path("scripts") / name)
    except (OSError, ValueError) as exc:
        raise _fail(f"{label}/{name} linked runtime authority") from exc
    return _open_ordinary_leaf(leaf, f"{label}/{name}")


def extract_external_governance_projection(shared_spine: Path) -> bytes:
    """Extract the one marked canonical policy block without normalizing its bytes."""

    raw = _read_bound_bytes(shared_spine, "shared governance")
    try:
        lines = raw.decode("utf-8", errors="strict").splitlines(keepends=True)
    except UnicodeDecodeError as exc:
        raise _fail("shared governance is not UTF-8") from exc
    begin = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == EXTERNAL_GOVERNANCE_BEGIN]
    end = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == EXTERNAL_GOVERNANCE_END]
    if len(begin) != 1 or len(end) != 1 or begin[0] >= end[0] - 1:
        raise _fail("shared governance extraction markers")
    return "".join(lines[begin[0] + 1 : end[0]]).encode("utf-8")


def _validate_external_governance_projection(source_root: Path) -> None:
    expected = extract_external_governance_projection(
        Path(source_root) / "shared" / "AGENTS.shared.md"
    )
    actual = _read_bound_bytes(
        Path(source_root) / _AUTHORED_SOURCE_PATHS["external-prompt-governance.md"],
        "source/external-prompt-governance.md",
    )
    if actual != expected:
        raise _fail("external governance projection drift")


def validate_projection_manifest(
    manifest_path: Path,
    source_root: Path,
    projections: Sequence[tuple[str, Path]],
    *,
    claude_agents_authority: Any | None = None,
) -> dict[str, Any]:
    """Validate one source set and every named local projection without mutation."""

    manifest = _load_manifest(Path(manifest_path))
    source_root = Path(source_root)
    normalized: list[tuple[str, Path]] = []
    labels: set[str] = set()
    for label, root in projections:
        if not label or label in labels:
            raise _fail("projection label is empty or duplicated")
        labels.add(label)
        normalized.append((label, Path(root)))
    if not normalized:
        raise _fail("no projection was supplied")
    if claude_agents_authority is not None:
        expected_root = claude_agents_authority.logical_root / "scripts"
        claude_roots = [
            root for label, root in normalized if label == "claude-host"
        ]
        if (
            len(claude_roots) != 1
            or not _same_lexical_path(claude_roots[0], expected_root)
        ):
            raise _fail("linked Claude authority projection root")

    files = manifest["files"]
    _validate_external_governance_projection(source_root)
    bindings: list[tuple[_BoundOrdinaryFile, str, str]] = []
    try:
        if claude_agents_authority is not None:
            _assert_current_claude_agents_authority(claude_agents_authority)
        for name in TRANSPORT_FILES:
            authored_source, packed_destination, digest = _validate_record(
                name, files[name]
            )
            bindings.append(
                (_open_ordinary_file(source_root / authored_source, f"source/{name}"), digest, f"source/{name}")
            )
            if packed_destination != Path("scripts") / name:
                raise _fail(f"packed runtime destination for {name}")
            for label, projection_root in normalized:
                bindings.append(
                    (
                        _open_projection_file(
                            projection_root,
                            label,
                            name,
                            (
                                claude_agents_authority
                                if label == "claude-host"
                                else None
                            ),
                        ),
                        digest,
                        f"{label}/{name}",
                    )
                )
        for bound, digest, label in bindings:
            _validate_bound_bytes(bound, digest, label)
        if claude_agents_authority is not None:
            _assert_current_claude_agents_authority(claude_agents_authority)
    finally:
        for bound, _digest, _label in bindings:
            bound.close()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "packRevision": manifest["packRevision"],
        "files": list(TRANSPORT_FILES),
        "projections": [label for label, _root in normalized],
    }


def _projection(value: str) -> tuple[str, Path]:
    label, separator, raw_path = value.partition("=")
    if not separator or not label or not raw_path:
        raise argparse.ArgumentTypeError("projection must be LABEL=PATH")
    return label, Path(raw_path)


def validate_source_manifest(manifest_path: Path, source_root: Path) -> dict[str, Any]:
    """Validate only authored root bytes; installed state is not consulted."""

    manifest = _load_manifest(Path(manifest_path))
    files = manifest["files"]
    _validate_external_governance_projection(source_root)
    bindings: list[tuple[_BoundOrdinaryFile, str, str]] = []
    try:
        for name in TRANSPORT_FILES:
            authored_source, _packed_destination, digest = _validate_record(
                name, files[name]
            )
            bindings.append(
                (_open_ordinary_file(Path(source_root) / authored_source, f"source/{name}"), digest, f"source/{name}")
            )
        for bound, digest, label in bindings:
            _validate_bound_bytes(bound, digest, label)
    finally:
        for bound, _digest, _label in bindings:
            bound.close()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "packRevision": manifest["packRevision"],
        "files": list(TRANSPORT_FILES),
        "projections": [],
    }


def _scoped_layout(
    scope: str, source_root: Path, install_root: Path | None
) -> tuple[Path, Path, tuple[tuple[str, Path], ...]]:
    source_root = Path(source_root)
    manifest = source_root / "shared" / "provider-prompt-projections.v1.json"
    if scope == "source":
        if install_root is not None:
            raise _fail("source scope does not accept an install root")
        return manifest, source_root, ()
    if install_root is None:
        raise _fail(f"{scope} scope requires an install root")
    root = Path(install_root)
    return (
        manifest,
        source_root,
        (
            ("canonical", root / ".agents" / "skills" / "lead" / "scripts"),
            ("claude-host", root / ".claude" / "agents" / "scripts"),
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require", action="store_true")
    parser.add_argument("--scope", choices=("source", "project", "global"))
    parser.add_argument("--install-root", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--projection", action="append", type=_projection, default=[])
    args = parser.parse_args(argv)
    if not args.require:
        parser.error("--require is mandatory")
    try:
        if args.scope is not None:
            if args.source_root is None or args.manifest is not None or args.projection:
                raise _fail("scoped mode requires source root only, plus install root when installed")
            manifest, source_root, projections = _scoped_layout(
                args.scope, args.source_root, args.install_root
            )
            result = (
                validate_source_manifest(manifest, source_root)
                if args.scope == "source"
                else validate_projection_manifest(
                    manifest,
                    source_root,
                    projections,
                    claude_agents_authority=(
                        _bind_global_claude_agents_authority(args.install_root)
                        if args.scope == "global"
                        else None
                    ),
                )
            )
        elif args.manifest is not None and args.source_root is not None and args.projection:
            manifest = args.manifest
            source_root = args.source_root
            projections = tuple(args.projection)
            result = validate_projection_manifest(
                manifest,
                source_root,
                projections,
            )
        else:
            raise _fail(
                "explicit scope is required, or provide manifest, source root, and projections"
            )
    except (OSError, ProjectionParityError) as exc:
        detail = str(exc)
        if not detail.startswith(f"{STABLE_ID}:"):
            detail = f"{STABLE_ID}: {detail}"
        sys.stderr.write(detail + "\n")
        return 1
    json.dump(result, sys.stdout, sort_keys=True, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
