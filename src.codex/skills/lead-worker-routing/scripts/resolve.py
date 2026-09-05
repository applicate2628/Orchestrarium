#!/usr/bin/env python3
"""Resolve one provider-neutral Orchestrarium Version 1 worker route.

This compatibility facade preserves the reviewed Version 1 selection core while
adding request identity, launch-boundary, native-host, JSON-shape, and safe-file
hardening. It remains a pure resolver and never launches a provider.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

_BASE_PATH = Path(__file__).with_name("_resolver_base.py")
_BASE_SPEC = importlib.util.spec_from_file_location(
    "_orchestrarium_lead_worker_routing_v1_base", _BASE_PATH
)
if _BASE_SPEC is None or _BASE_SPEC.loader is None:
    raise RuntimeError(f"cannot load {_BASE_PATH}")
_BASE = importlib.util.module_from_spec(_BASE_SPEC)
sys.modules[_BASE_SPEC.name] = _BASE
_BASE_SPEC.loader.exec_module(_BASE)

REQUEST_FIELDS = _BASE.REQUEST_FIELDS
CANDIDATE_FIELDS = _BASE.CANDIDATE_FIELDS
LEAD_HOSTS = _BASE.LEAD_HOSTS
V1_PROVIDERS = _BASE.V1_PROVIDERS
PROVIDER_FAMILIES = _BASE.PROVIDER_FAMILIES
PROVIDER_RUNTIMES = _BASE.PROVIDER_RUNTIMES
MUTATION_CLASSES = _BASE.MUTATION_CLASSES
MUTATION_RANK = _BASE.MUTATION_RANK
PROVIDER_MUTATION_CEILING = _BASE.PROVIDER_MUTATION_CEILING
AVAILABILITY_IDS = _BASE.AVAILABILITY_IDS
AVAILABILITY_FAILURE_CLASS = _BASE.AVAILABILITY_FAILURE_CLASS
AVAILABILITIES = _BASE.AVAILABILITIES
TOKEN = _BASE.TOKEN
MAX_CANDIDATES = _BASE.MAX_CANDIDATES
MAX_PRIORITY = _BASE.MAX_PRIORITY
MAX_REQUEST_BYTES = _BASE.MAX_REQUEST_BYTES

MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 8192
REQUEST_FINGERPRINT_ALGORITHM = "sha256-canonical-json-v1"


class DuplicateJsonKeyError(ValueError):
    """Raised when a request JSON object repeats a key."""


class UnsafeRequestFileError(ValueError):
    """Raised when the request path is not a stable ordinary file."""


class RequestTooLargeError(ValueError):
    """Raised when the request exceeds the fixed byte budget."""


class InvalidJsonStructureError(ValueError):
    """Raised when JSON uses non-standard constants or exceeds shape limits."""


def _request_fingerprint(request: dict[str, object]) -> str:
    canonical = json.dumps(
        request,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(canonical).hexdigest()


def _decorate_decision(
    decision: dict[str, object],
    *,
    request_fingerprint: str | None,
) -> dict[str, object]:
    selected = decision.get("status") == "selected"
    result = dict(decision)
    result["requestFingerprintAlgorithm"] = REQUEST_FINGERPRINT_ALGORITHM
    result["requestFingerprint"] = request_fingerprint
    result["requiresAdapterAdmission"] = selected
    result["executionAuthorized"] = False
    return result


def _prepare_selection_request(
    request: dict[str, object],
) -> tuple[dict[str, object], set[str]]:
    """Return a base-compatible copy plus candidates needing a typed rejection."""

    prepared = dict(request)
    prepared_candidates: list[dict[str, object]] = []
    foreign_native: set[str] = set()
    lead_host = request.get("leadHost")
    candidates = request.get("candidates")
    if not isinstance(candidates, list):
        return prepared, foreign_native

    for candidate_value in candidates:
        if not isinstance(candidate_value, dict):
            prepared_candidates.append(candidate_value)
            continue
        candidate = dict(candidate_value)
        provider = candidate.get("provider")
        runtime = candidate.get("runtime")
        candidate_id = candidate.get("candidateId")
        if (
            isinstance(provider, str)
            and isinstance(runtime, str)
            and isinstance(candidate_id, str)
            and runtime.endswith("-native")
            and provider != lead_host
        ):
            foreign_native.add(candidate_id)
            candidate["runtime"] = f"{provider}-foreign-native-denied"
        prepared_candidates.append(candidate)
    prepared["candidates"] = prepared_candidates
    return prepared, foreign_native


def _restore_typed_native_rejections(
    decision: dict[str, object],
    foreign_native: set[str],
) -> None:
    rejections = decision.get("rejections")
    if not isinstance(rejections, list):
        return
    for rejection in rejections:
        if (
            isinstance(rejection, dict)
            and rejection.get("candidateId") in foreign_native
            and rejection.get("stableId")
            == "E_LEAD_WORKER_V1_PROVIDER_RUNTIME_MISMATCH"
        ):
            rejection["stableId"] = (
                "E_LEAD_WORKER_V1_NATIVE_RUNTIME_HOST_MISMATCH"
            )


def resolve_v1_worker_route(request: dict[str, object]) -> dict[str, object]:
    """Return one exact nonauthorizing candidate route or a typed decision."""

    if not _BASE._validate_request(request):
        return _decorate_decision(
            _BASE.resolve_v1_worker_route(request),
            request_fingerprint=None,
        )

    request_fingerprint = _request_fingerprint(request)
    prepared, foreign_native = _prepare_selection_request(request)
    decision = _BASE.resolve_v1_worker_route(prepared)
    _restore_typed_native_rejections(decision, foreign_native)
    return _decorate_decision(
        decision,
        request_fingerprint=request_fingerprint,
    )


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(key)
        result[key] = value
    return result


def _parse_json(text: str) -> object:
    def reject_constant(value: str) -> None:
        raise InvalidJsonStructureError(value)

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
            raise InvalidJsonStructureError("request JSON shape exceeds limits")
        if isinstance(value, dict):
            stack.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list):
            stack.extend((item, depth + 1) for item in value)
    return parsed


def _is_reparse_metadata(metadata: os.stat_result) -> bool:
    return bool(
        getattr(metadata, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _entry_signature(metadata: os.stat_result, *, leaf: bool) -> tuple[int, ...]:
    identity = (
        metadata.st_mode,
        metadata.st_dev,
        metadata.st_ino,
        getattr(metadata, "st_file_attributes", 0),
    )
    if not leaf:
        return identity
    return identity + (
        metadata.st_size,
        getattr(metadata, "st_mtime_ns", 0),
        getattr(metadata, "st_birthtime_ns", 0),
        getattr(metadata, "st_ctime_ns", 0),
    )


def _is_junction(path: Path) -> bool:
    checker = getattr(os.path, "isjunction", None)
    return bool(checker and checker(path))


def _lexical_absolute_chain(path: Path) -> list[Path]:
    absolute = Path(os.path.abspath(os.fspath(path)))
    anchor = Path(absolute.anchor)
    chain = [anchor]
    cursor = anchor
    for component in absolute.parts[1:]:
        cursor /= component
        chain.append(cursor)
    return chain


def _snapshot_request_path(path: Path) -> list[tuple[Path, tuple[int, ...]]]:
    chain = _lexical_absolute_chain(path)
    snapshots: list[tuple[Path, tuple[int, ...]]] = []
    for index, component in enumerate(chain):
        try:
            metadata = os.lstat(component)
        except OSError as exc:
            raise UnsafeRequestFileError(str(path)) from exc
        is_leaf = index == len(chain) - 1
        if (
            stat.S_ISLNK(metadata.st_mode)
            or _is_reparse_metadata(metadata)
            or _is_junction(component)
            or (is_leaf and not stat.S_ISREG(metadata.st_mode))
            or (not is_leaf and not stat.S_ISDIR(metadata.st_mode))
        ):
            raise UnsafeRequestFileError(str(path))
        snapshots.append(
            (component, _entry_signature(metadata, leaf=is_leaf))
        )
    return snapshots


def _assert_path_snapshot(
    snapshots: list[tuple[Path, tuple[int, ...]]],
    original_path: Path,
) -> None:
    for index, (component, expected) in enumerate(snapshots):
        try:
            metadata = os.lstat(component)
        except OSError as exc:
            raise UnsafeRequestFileError(str(original_path)) from exc
        is_leaf = index == len(snapshots) - 1
        if (
            stat.S_ISLNK(metadata.st_mode)
            or _is_reparse_metadata(metadata)
            or _is_junction(component)
            or _entry_signature(metadata, leaf=is_leaf) != expected
        ):
            raise UnsafeRequestFileError(str(original_path))


def _read_file_bytes(path: Path) -> bytes:
    snapshots = _snapshot_request_path(path)
    absolute_path = snapshots[-1][0]
    before_signature = snapshots[-1][1]
    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor: int | None = None
    try:
        descriptor = os.open(absolute_path, flags)
        opened = os.fstat(descriptor)
        opened_signature = _entry_signature(opened, leaf=True)
        # Windows path and descriptor APIs can give ctime different meanings.
        # Full same-API snapshots below still bind it independently on both sides.
        comparable = slice(None, -1) if os.name == "nt" else slice(None)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened_signature[comparable] != before_signature[comparable]
        ):
            raise UnsafeRequestFileError(str(path))
        chunks: list[bytes] = []
        observed = 0
        while observed <= MAX_REQUEST_BYTES:
            chunk = os.read(
                descriptor,
                min(64 * 1024, MAX_REQUEST_BYTES + 1 - observed),
            )
            if not chunk:
                break
            chunks.append(chunk)
            observed += len(chunk)
        if observed > MAX_REQUEST_BYTES:
            raise RequestTooLargeError(str(path))
        after_opened = os.fstat(descriptor)
        if _entry_signature(after_opened, leaf=True) != _entry_signature(
            opened, leaf=True
        ):
            raise UnsafeRequestFileError(str(path))
        _assert_path_snapshot(snapshots, path)
        return b"".join(chunks)
    except (RequestTooLargeError, UnsafeRequestFileError):
        raise
    except OSError as exc:
        raise UnsafeRequestFileError(str(path)) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _read_request(path: str) -> object:
    if path == "-":
        data = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        if len(data) > MAX_REQUEST_BYTES:
            raise RequestTooLargeError("stdin")
    else:
        data = _read_file_bytes(Path(path))
    return _parse_json(data.decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-file", required=True)
    args = parser.parse_args(argv)
    try:
        request = _read_request(args.request_file)
    except DuplicateJsonKeyError:
        result = _BASE._invalid_request(
            {}, "E_LEAD_WORKER_V1_REQUEST_JSON_DUPLICATE_KEY"
        )
        result = _decorate_decision(result, request_fingerprint=None)
    except UnsafeRequestFileError:
        result = _decorate_decision(
            _BASE._invalid_request({}, "E_LEAD_WORKER_V1_REQUEST_FILE_UNSAFE"),
            request_fingerprint=None,
        )
    except RequestTooLargeError:
        result = _decorate_decision(
            _BASE._invalid_request({}, "E_LEAD_WORKER_V1_REQUEST_TOO_LARGE"),
            request_fingerprint=None,
        )
    except OSError:
        result = _decorate_decision(
            _BASE._invalid_request({}, "E_LEAD_WORKER_V1_REQUEST_IO_FAILED"),
            request_fingerprint=None,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        InvalidJsonStructureError,
        RecursionError,
        ValueError,
    ):
        result = _decorate_decision(
            _BASE._invalid_request({}, "E_LEAD_WORKER_V1_REQUEST_JSON_INVALID"),
            request_fingerprint=None,
        )
    else:
        result = resolve_v1_worker_route(request)
    json.dump(result, sys.stdout, sort_keys=True, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0 if result["status"] == "selected" else 2


if __name__ == "__main__":
    raise SystemExit(main())
