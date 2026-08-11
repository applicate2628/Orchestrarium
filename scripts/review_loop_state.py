#!/usr/bin/env python3
"""Transactional state owner for governed Orchestrarium review loops.

New formal loops use schema V2 and cannot expose launch receipts until a
frozen artifact and the complete round admission have been atomically written,
read back, and validated.  Legacy V1 records remain readable by the repository
validator but are never mutated implicitly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable


REVIEW_LOOP_ROUND_CAP = 3
JSON_NESTING_LIMIT = 128
LANES = ("surgical", "deep", "scout")
VERDICT_LANES = ("surgical", "deep")
FAILURE_KINDS = ("error", "died", "limit")
OUTCOMES = ("converged", "drift", "deadlock")
RECEIPT_EVENT = "ORCHESTRARIUM_REVIEW_LOOP_STATE_V2"
PORTABLE_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
SNAPSHOT_REVISION = re.compile(r"^sha256:[0-9a-f]{64}$")
GIT_REVISION = re.compile(r"^git:[0-9a-f]{40,64}$")

TOP_FIELDS = {
    "schema_version", "loop_id", "objective", "scope", "runtime_root",
    "status", "operations", "rounds",
}
ROUND_FIELDS = {
    "round", "phase", "diff", "artifact", "surgical", "deep", "scout",
    "lane_failures", "evidence",
}
ARTIFACT_FIELDS = {"kind", "revision", "snapshot", "source"}
ATTEMPT_BASE_FIELDS = {"attempt_id", "artifact_revision", "state"}
VERDICT_RESULT_FIELDS = {
    "verdict", "blockers", "rationale", "root_proven", "scope_unchanged",
    "verification_adequate",
}
SCOUT_RESULT_FIELDS = {"findings", "reconciliation"}
FAILURE_FIELDS = {
    "lane", "attempt_id", "artifact_revision", "failure", "redispatched_as",
}
OPERATION_FIELDS = {"id", "fingerprint", "receipt"}


class StateError(RuntimeError):
    def __init__(self, failure_id: str, detail: str = "") -> None:
        super().__init__(detail)
        self.failure_id = failure_id
        self.detail = detail

    def __str__(self) -> str:
        return f"{self.failure_id}: {self.detail}" if self.detail else self.failure_id


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_yaml(text: str) -> tuple[Any | None, str | None]:
    try:
        import yaml  # type: ignore
    except Exception:
        return None, "ledger looks like YAML but PyYAML is not importable"
    try:
        return yaml.safe_load(text), None
    except Exception as exc:
        return None, f"YAML parse error: {exc}"


def _decode_bounded_json(text: str) -> tuple[Any | None, str | None]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"JSON parse error: {exc}"
    except RecursionError:
        return None, "JSON nesting exceeds the supported limit"
    pending: list[tuple[Any, int]] = [(data, 0)]
    while pending:
        value, depth = pending.pop()
        if depth > JSON_NESTING_LIMIT:
            return None, "JSON nesting exceeds the supported limit"
        if isinstance(value, dict):
            pending.extend((child, depth + 1) for child in value.values())
        elif isinstance(value, list):
            pending.extend((child, depth + 1) for child in value)
    return data, None


def load_ledger(path: str | Path) -> tuple[Any | None, str | None]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"cannot read ledger: {exc}"
    suffix = Path(path).suffix.casefold()
    if suffix == ".json":
        return _decode_bounded_json(text)
    if suffix in {".yaml", ".yml"}:
        return _load_yaml(text)
    data, error = _decode_bounded_json(text)
    return (data, None) if error is None else _load_yaml(text)


def validate_v1(data: Any, cap: int = REVIEW_LOOP_ROUND_CAP) -> list[str]:
    """Preserve the former development validator's V1 structural contract."""
    if not isinstance(data, dict):
        return ["ledger root must be a mapping/object"]
    errors: list[str] = []
    pinned: dict[str, Any] = {}
    for key in ("objective", "scope", "runtime_root"):
        value = data.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"top-level pinned anchor '{key}' is missing or empty")
        else:
            pinned[key] = value
    rounds = data.get("rounds")
    if not isinstance(rounds, list) or not rounds:
        return errors + ["'rounds' must be a non-empty list"]
    if len(rounds) > cap:
        errors.append(f"round count {len(rounds)} exceeds cap {cap}")
    for index, rnd in enumerate(rounds):
        label = f"round[{index}]"
        if not isinstance(rnd, dict):
            errors.append(f"{label}: each round must be a mapping")
            continue
        number = rnd.get("round")
        if number is not None:
            label = f"round {number}"
            if not isinstance(number, int) or number < 1 or number > cap:
                errors.append(f"{label}: 'round' must be an integer in 1..{cap}")
        for key, value in pinned.items():
            if key in rnd and rnd[key] != value:
                errors.append(f"{label}: pinned anchor '{key}' differs from top-level")
        if not _nonempty(rnd.get("diff")):
            errors.append(f"{label}: per-round 'diff' is missing or empty")
        attempts: dict[str, str] = {}
        for lane in LANES:
            block = rnd.get(lane)
            if not isinstance(block, dict):
                errors.append(f"{label}: missing or invalid angle '{lane}'")
                continue
            attempt = block.get("attempt_id")
            if not _nonempty(attempt):
                errors.append(f"{label}: angle '{lane}' is missing a non-empty 'attempt_id'")
            else:
                attempts[lane] = attempt.strip()
            if lane in VERDICT_LANES:
                verdict = block.get("verdict")
                if not isinstance(verdict, str) or verdict.upper() not in {"PASS", "REVISE"}:
                    errors.append(f"{label}: angle '{lane}' verdict must be PASS or REVISE")
                blockers = block.get("blockers")
                if not (isinstance(blockers, list) and blockers) and not _nonempty(block.get("rationale")):
                    errors.append(f"{label}: angle '{lane}' is a bare verdict")
            else:
                if not isinstance(block.get("findings"), list):
                    errors.append(f"{label}: 'scout.findings' must be a list")
                if "verdict" in block:
                    errors.append(f"{label}: 'scout' must not carry a verdict")
        if len(set(attempts.values())) != len(attempts):
            errors.append(f"{label}: angle attempt_id values must be unique")
        failures = rnd.get("lane_failures")
        if not isinstance(failures, list):
            errors.append(f"{label}: 'lane_failures' is required and must be a list")
            continue
        for position, failure in enumerate(failures):
            prefix = f"{label} lane_failures[{position}]"
            if not isinstance(failure, dict):
                errors.append(f"{prefix}: each lane_failure must be a mapping")
                continue
            if set(failure) != {"lane", "attempt_id", "failure", "redispatched_as"}:
                errors.append(f"{prefix}: fields are invalid")
            lane = failure.get("lane")
            if lane not in LANES or failure.get("failure") not in FAILURE_KINDS:
                errors.append(f"{prefix}: lane or failure kind is invalid")
            if not _nonempty(failure.get("attempt_id")) or not _nonempty(failure.get("redispatched_as")):
                errors.append(f"{prefix}: attempt identifiers must be non-empty")
            elif lane in attempts and failure["redispatched_as"].strip() != attempts[lane]:
                errors.append(f"{prefix}: redispatched_as must equal the current lane attempt")
    return errors


def _fields(value: dict[str, Any], allowed: set[str], label: str, errors: list[str]) -> None:
    for key in sorted(set(value) - allowed):
        errors.append(f"{label}.{key}: unexpected field")


def validate_v2(data: Any, cap: int = REVIEW_LOOP_ROUND_CAP, require_terminal: bool = False) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["root: expected object"]
    _fields(data, TOP_FIELDS, "root", errors)
    if data.get("schema_version") != 2:
        errors.append("schema_version: expected 2")
    if not _nonempty(data.get("loop_id")) or not PORTABLE_ID.fullmatch(data.get("loop_id", "")):
        errors.append("loop_id: expected portable non-empty identifier")
    for key in ("objective", "scope", "runtime_root"):
        if not _nonempty(data.get(key)):
            errors.append(f"{key}: expected non-empty string")
    status = data.get("status")
    if status not in {"running", *OUTCOMES}:
        errors.append("status: invalid value")
    if require_terminal and status == "running":
        errors.append("status: terminal state required")
    operations = data.get("operations")
    seen_ops: set[str] = set()
    if not isinstance(operations, list):
        errors.append("operations: expected list")
    else:
        for index, operation in enumerate(operations):
            label = f"operations[{index}]"
            if not isinstance(operation, dict):
                errors.append(f"{label}: expected object")
                continue
            _fields(operation, OPERATION_FIELDS, label, errors)
            if set(operation) != OPERATION_FIELDS:
                errors.append(f"{label}: id, fingerprint, and receipt are required")
            op_id = operation.get("id")
            if not _nonempty(op_id) or op_id in seen_ops:
                errors.append(f"{label}.id: expected unique non-empty string")
            else:
                seen_ops.add(op_id)
            if not _nonempty(operation.get("fingerprint")) or not isinstance(operation.get("receipt"), dict):
                errors.append(f"{label}: invalid fingerprint or receipt")
    rounds = data.get("rounds")
    if not isinstance(rounds, list) or not rounds:
        return errors + ["rounds: expected non-empty list"]
    if len(rounds) > cap:
        errors.append(f"rounds: count exceeds cap {cap}")
    for index, rnd in enumerate(rounds, 1):
        label = f"rounds[{index - 1}]"
        if not isinstance(rnd, dict):
            errors.append(f"{label}: expected object")
            continue
        _fields(rnd, ROUND_FIELDS, label, errors)
        if set(rnd) != ROUND_FIELDS:
            errors.append(f"{label}: required round fields are missing")
        if rnd.get("round") != index:
            errors.append(f"{label}.round: expected {index}")
        phase = rnd.get("phase")
        if phase not in {"admitted", "collecting", "complete"}:
            errors.append(f"{label}.phase: invalid value")
        if not _nonempty(rnd.get("diff")):
            errors.append(f"{label}.diff: expected non-empty string")
        artifact = rnd.get("artifact")
        revision = None
        if not isinstance(artifact, dict):
            errors.append(f"{label}.artifact: expected object")
        else:
            _fields(artifact, ARTIFACT_FIELDS, f"{label}.artifact", errors)
            revision = artifact.get("revision")
            kind = artifact.get("kind")
            if kind == "snapshot":
                if not isinstance(revision, str) or not SNAPSHOT_REVISION.fullmatch(revision):
                    errors.append(f"{label}.artifact.revision: invalid snapshot revision")
                if not _nonempty(artifact.get("snapshot")):
                    errors.append(f"{label}.artifact.snapshot: required")
            elif kind == "git-commit":
                if not isinstance(revision, str) or not GIT_REVISION.fullmatch(revision):
                    errors.append(f"{label}.artifact.revision: invalid git revision")
                if "snapshot" in artifact:
                    errors.append(f"{label}.artifact.snapshot: forbidden for git commit")
            else:
                errors.append(f"{label}.artifact.kind: invalid value")
        current_attempts: dict[str, str] = {}
        for lane in LANES:
            block = rnd.get(lane)
            lane_label = f"{label}.{lane}"
            if not isinstance(block, dict):
                errors.append(f"{lane_label}: expected object")
                continue
            allowed = ATTEMPT_BASE_FIELDS | (VERDICT_RESULT_FIELDS if lane in VERDICT_LANES else SCOUT_RESULT_FIELDS)
            _fields(block, allowed, lane_label, errors)
            attempt = block.get("attempt_id")
            if not _nonempty(attempt):
                errors.append(f"{lane_label}.attempt_id: required")
            else:
                current_attempts[lane] = attempt
            if block.get("artifact_revision") != revision:
                errors.append(f"{lane_label}.artifact_revision: must equal round revision")
            state = block.get("state")
            if state not in {"admitted", "running", "complete"}:
                errors.append(f"{lane_label}.state: invalid value")
            if state == "complete":
                if lane in VERDICT_LANES:
                    verdict = block.get("verdict")
                    if verdict not in {"PASS", "REVISE"}:
                        errors.append(f"{lane_label}.verdict: required")
                    if not (isinstance(block.get("blockers"), list) and block["blockers"]) and not _nonempty(block.get("rationale")):
                        errors.append(f"{lane_label}: bare verdict")
                    for key in ("root_proven", "scope_unchanged", "verification_adequate"):
                        if not _nonempty(block.get(key)):
                            errors.append(f"{lane_label}.{key}: required")
                else:
                    if not isinstance(block.get("findings"), list) or not isinstance(block.get("reconciliation"), list):
                        errors.append(f"{lane_label}: findings and reconciliation lists required")
            elif set(block) != ATTEMPT_BASE_FIELDS:
                errors.append(f"{lane_label}: result fields are legal only when complete")
        if len(set(current_attempts.values())) != len(current_attempts):
            errors.append(f"{label}: attempt IDs must be unique")
        failures = rnd.get("lane_failures")
        if not isinstance(failures, list):
            errors.append(f"{label}.lane_failures: expected list")
        else:
            for failure_index, failure in enumerate(failures):
                failure_label = f"{label}.lane_failures[{failure_index}]"
                if not isinstance(failure, dict):
                    errors.append(f"{failure_label}: expected object")
                    continue
                _fields(failure, FAILURE_FIELDS, failure_label, errors)
                lane = failure.get("lane")
                if lane not in LANES or failure.get("failure") not in FAILURE_KINDS:
                    errors.append(f"{failure_label}: invalid lane or failure")
                if not _nonempty(failure.get("attempt_id")):
                    errors.append(f"{failure_label}.attempt_id: required")
                if failure.get("artifact_revision") != revision:
                    errors.append(f"{failure_label}.artifact_revision: mismatch")
                redispatched = failure.get("redispatched_as")
                if redispatched is not None and redispatched != current_attempts.get(lane):
                    errors.append(f"{failure_label}.redispatched_as: must name current lane attempt")
                if phase == "complete" and not _nonempty(redispatched):
                    errors.append(f"{failure_label}.redispatched_as: required before completion")
        if not isinstance(rnd.get("evidence"), list):
            errors.append(f"{label}.evidence: expected list")
        if phase == "complete" and any(isinstance(rnd.get(lane), dict) and rnd[lane].get("state") != "complete" for lane in LANES):
            errors.append(f"{label}: complete round has incomplete lane")
    return errors


def validate_record(data: Any, cap: int = REVIEW_LOOP_ROUND_CAP, require_v2: bool = False, require_terminal: bool = False) -> tuple[list[str], bool]:
    is_v2 = isinstance(data, dict) and data.get("schema_version") == 2
    if require_v2 and not is_v2:
        return ["RLSTATE_MIGRATION_REQUIRED"], False
    return (validate_v2(data, cap, require_terminal), True) if is_v2 else (validate_v1(data, cap), False)


def _repo_root(start: Path) -> Path:
    current = start.resolve(strict=False)
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    raise StateError("RLSTATE_PATH_ESCAPE", "repository root not found")


def _is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    return (
        path.is_symlink()
        or bool(getattr(info, "st_file_attributes", 0) & 0x400)
        or (hasattr(os.path, "isjunction") and os.path.isjunction(path))
    )


def _require_local_path(path: Path, root: Path, base: Path) -> Path:
    absolute = Path(os.path.abspath(path))
    root_absolute = Path(os.path.abspath(root))
    base_absolute = Path(os.path.abspath(base))
    try:
        base_absolute.relative_to(root_absolute)
        absolute.relative_to(base_absolute)
    except ValueError as exc:
        raise StateError("RLSTATE_PATH_ESCAPE", "path is outside the allowed local root") from exc
    try:
        relative_to_root = absolute.relative_to(root_absolute)
    except ValueError as exc:
        raise StateError("RLSTATE_PATH_ESCAPE", "path escapes repository") from exc
    cursor = root_absolute
    for part in relative_to_root.parts:
        cursor = cursor / part
        if _is_reparse(cursor):
            raise StateError("RLSTATE_PATH_ESCAPE", "link or reparse boundary rejected")
    try:
        resolved_root = root_absolute.resolve(strict=True)
        resolved_base = base_absolute.resolve(strict=False)
        resolved_path = absolute.resolve(strict=False)
        resolved_base.relative_to(resolved_root)
        resolved_path.relative_to(resolved_base)
        resolved_path.relative_to(resolved_root)
    except (OSError, ValueError) as exc:
        raise StateError("RLSTATE_PATH_ESCAPE", "resolved path escapes the allowed local root") from exc
    return absolute


def _state_context(state_arg: str | Path) -> tuple[Path, Path, Path]:
    raw = Path(state_arg)
    root = _repo_root(Path.cwd())
    state = raw if raw.is_absolute() else root / raw
    reviews = root / ".scratch" / "reviews"
    state = _require_local_path(state, root, reviews)
    return root, reviews, state


def _require_open_identity(
    path: Path,
    descriptor: int,
    root: Path,
    base: Path,
) -> Path:
    admitted = _require_local_path(path, root, base)
    try:
        path_info = admitted.stat(follow_symlinks=False)
        handle_info = os.fstat(descriptor)
    except OSError as exc:
        raise StateError("RLSTATE_PATH_ESCAPE", "open resource identity is unavailable") from exc
    if (
        _is_reparse(admitted)
        or not stat.S_ISREG(handle_info.st_mode)
        or (path_info.st_dev, path_info.st_ino)
        != (handle_info.st_dev, handle_info.st_ino)
    ):
        raise StateError("RLSTATE_PATH_ESCAPE", "open resource identity changed")
    return admitted


def _relative(path: Path, root: Path) -> str:
    return path.absolute().relative_to(root.absolute()).as_posix()


def _read_input(path: str | Path, label: str) -> str:
    try:
        value = Path(path).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise StateError("RLSTATE_INVALID", f"{label} input is unreadable") from exc
    if not value:
        raise StateError("RLSTATE_INVALID", f"{label} input is empty")
    return value


def _fingerprint(command: str, payload: dict[str, Any]) -> str:
    encoded = json.dumps({"command": command, "payload": payload}, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _attempt_id(lane: str, round_number: int) -> str:
    return f"{lane}-r{round_number}-{uuid.uuid4().hex[:12]}"


def _receipt(command: str, root: Path, state: Path, data: dict[str, Any], rnd: dict[str, Any], **extra: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "event": RECEIPT_EVENT,
        "command": command,
        "state": _relative(state, root),
        "loop_id": data["loop_id"],
        "round": rnd["round"],
        "artifact_revision": rnd["artifact"]["revision"],
    }
    result.update(extra)
    return result


def _load_v2(state: Path, root: Path, reviews: Path) -> dict[str, Any]:
    state = _require_local_path(state, root, reviews)
    data, error = load_ledger(state)
    if error:
        raise StateError("RLSTATE_INVALID", error)
    if not isinstance(data, dict) or data.get("schema_version") != 2:
        raise StateError("RLSTATE_MIGRATION_REQUIRED", "V1 is read-only")
    errors = validate_v2(data)
    if errors:
        raise StateError("RLSTATE_INVALID", errors[0])
    return data


def _verify_artifacts(data: dict[str, Any], root: Path) -> None:
    for rnd in data["rounds"]:
        artifact = rnd["artifact"]
        revision = artifact["revision"]
        if artifact["kind"] == "snapshot":
            snapshot = _require_local_path(root / artifact["snapshot"], root, root / ".scratch" / "reviews")
            if not snapshot.is_file() or "sha256:" + _sha256(snapshot) != revision:
                raise StateError("RLSTATE_ARTIFACT_MUTATED", f"round={rnd['round']}")
        else:
            object_id = revision.removeprefix("git:")
            check = subprocess.run(
                ["git", "-C", str(root), "cat-file", "-t", object_id],
                text=True, capture_output=True, check=False,
            )
            if check.returncode != 0 or check.stdout.strip() != "commit":
                raise StateError("RLSTATE_ARTIFACT_MUTATED", f"round={rnd['round']}")


class _Lock:
    def __init__(self, path: Path, root: Path, reviews: Path) -> None:
        self.path = path
        self.root = root
        self.reviews = reviews
        self.fd: int | None = None
        self.locked = False

    def __enter__(self) -> "_Lock":
        self.path = _require_local_path(self.path, self.root, self.reviews)
        _require_local_path(self.path.parent, self.root, self.reviews)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path = _require_local_path(self.path, self.root, self.reviews)
        self.fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            self.path = _require_open_identity(
                self.path,
                self.fd,
                self.root,
                self.reviews,
            )
            if os.fstat(self.fd).st_size == 0:
                os.write(self.fd, b"\0")
                os.fsync(self.fd)
            os.lseek(self.fd, 0, os.SEEK_SET)
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise StateError(
                    "RLSTATE_LOCKED", "state lock is owned by a live process"
                ) from exc
            self.locked = True
            return self
        except BaseException:
            os.close(self.fd)
            self.fd = None
            raise

    def __exit__(self, exc_type: type[BaseException] | None, *_args: Any) -> None:
        unlock_error: OSError | None = None
        try:
            if self.fd is not None and self.locked:
                os.lseek(self.fd, 0, os.SEEK_SET)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(self.fd, fcntl.LOCK_UN)
        except OSError as error:
            unlock_error = error
        finally:
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
            self.locked = False
        if unlock_error is not None and exc_type is None:
            raise unlock_error


def _fsync_directory(path: Path) -> None:
    if os.name == "nt" or not hasattr(os, "O_DIRECTORY"):
        return
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _referenced_owned_paths(data: dict[str, Any], root: Path, reviews: Path) -> set[Path]:
    referenced: set[Path] = set()
    if data.get("schema_version") != 2:
        return referenced
    for rnd in data["rounds"]:
        snapshot = rnd["artifact"].get("snapshot")
        if snapshot:
            referenced.add(_require_local_path(root / snapshot, root, reviews))
    for operation in data["operations"]:
        backup = operation["receipt"].get("backup")
        if backup:
            referenced.add(_require_local_path(root / backup, root, reviews))
    return referenced


def _recovery_record(
    state: Path,
    root: Path,
    reviews: Path,
    *,
    allow_absent: bool,
) -> dict[str, Any] | None:
    state = _require_local_path(state, root, reviews)
    if not state.exists():
        if allow_absent:
            return None
        raise StateError("RLSTATE_RECOVERY_REQUIRED", "state is missing")
    data, error = load_ledger(state)
    if error:
        raise StateError("RLSTATE_RECOVERY_REQUIRED", "state cannot be validated")
    errors, _is_v2 = validate_record(data)
    if errors or not isinstance(data, dict):
        raise StateError("RLSTATE_RECOVERY_REQUIRED", "state cannot be validated")
    return data


def _recover_owned_resources(
    state: Path,
    root: Path,
    reviews: Path,
    *,
    allow_absent: bool,
) -> dict[str, int]:
    state = _require_local_path(state, root, reviews)
    data = _recovery_record(
        state,
        root,
        reviews,
        allow_absent=allow_absent,
    )
    try:
        referenced = _referenced_owned_paths(data, root, reviews) if data else set()
    except StateError as exc:
        if exc.failure_id == "RLSTATE_PATH_ESCAPE":
            raise
        raise StateError(
            "RLSTATE_RECOVERY_REQUIRED", "state resource references are invalid"
        ) from exc
    state_parent = _require_local_path(state.parent, root, reviews)
    artifact_dir = _require_local_path(state_parent / "artifacts", root, reviews)
    backup = _require_local_path(state.with_name(state.name + ".v1-backup"), root, reviews)
    candidates: dict[str, list[Path]] = {
        "pending": list(state_parent.glob(f".{state.name}.*.tmp")),
        "snapshots": (
            list(artifact_dir.glob(".round-*.tmp"))
            + list(artifact_dir.glob("round-*-*.snapshot"))
            if artifact_dir.is_dir()
            else []
        ),
        "backups": [backup],
    }
    recovered = {kind: 0 for kind in candidates}
    for kind, paths in candidates.items():
        for candidate in paths:
            candidate = _require_local_path(candidate, root, reviews)
            absolute = candidate.absolute()
            if absolute in referenced or not (candidate.is_file() or candidate.is_symlink()):
                continue
            try:
                candidate = _require_local_path(candidate, root, reviews)
                candidate.unlink()
            except OSError as exc:
                raise StateError(
                    "RLSTATE_RECOVERY_REQUIRED", "owned transient cleanup failed"
                ) from exc
            recovered[kind] += 1
    if sum(recovered.values()):
        print(
            "RLSTATE_RECOVERED: "
            + " ".join(f"{kind}={recovered[kind]}" for kind in ("pending", "snapshots", "backups")),
            file=sys.stderr,
        )
    return recovered


def _cleanup_if_unreferenced(state: Path, root: Path, reviews: Path, path: Path) -> None:
    path = _require_local_path(path, root, reviews)
    if not path.exists():
        return
    state = _require_local_path(state, root, reviews)
    if not state.exists():
        path = _require_local_path(path, root, reviews)
        path.unlink(missing_ok=True)
        return
    data, error = load_ledger(state)
    if error or not isinstance(data, dict):
        return
    errors, _is_v2 = validate_record(data)
    if errors:
        return
    try:
        referenced = _referenced_owned_paths(data, root, reviews)
    except StateError:
        return
    if path.absolute() not in referenced:
        path = _require_local_path(path, root, reviews)
        path.unlink(missing_ok=True)


def _atomic_write(
    state: Path,
    root: Path,
    reviews: Path,
    data: dict[str, Any],
) -> dict[str, Any]:
    errors = validate_v2(data)
    if errors:
        raise StateError("RLSTATE_INVALID", errors[0])
    state = _require_local_path(state, root, reviews)
    _require_local_path(state.parent, root, reviews)
    state.parent.mkdir(parents=True, exist_ok=True)
    state = _require_local_path(state, root, reviews)
    handle, temp_name = tempfile.mkstemp(prefix=f".{state.name}.", suffix=".tmp", dir=state.parent)
    temp = Path(temp_name)
    try:
        temp = _require_open_identity(temp, handle, root, reviews)
        stream = os.fdopen(handle, "w", encoding="utf-8", newline="\n")
        handle = -1
        with stream:
            json.dump(data, stream, indent=2, sort_keys=True, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temp = _require_local_path(temp, root, reviews)
        state = _require_local_path(state, root, reviews)
        os.replace(temp, state)
        _fsync_directory(state.parent)
        state = _require_local_path(state, root, reviews)
        committed, error = load_ledger(state)
        if error or validate_v2(committed):
            raise StateError("RLSTATE_COMMIT_UNCERTAIN", "state read-back validation failed")
        return committed
    finally:
        if handle >= 0:
            os.close(handle)
        try:
            temp = _require_local_path(temp, root, reviews)
            temp.unlink()
        except FileNotFoundError:
            pass


def _operation(data: dict[str, Any], operation_id: str, fingerprint: str) -> dict[str, Any] | None:
    if not _nonempty(operation_id):
        raise StateError("RLSTATE_INVALID", "operation id is required")
    for operation in data["operations"]:
        if operation["id"] != operation_id:
            continue
        if operation["fingerprint"] != fingerprint:
            raise StateError("RLSTATE_OPERATION_CONFLICT", "operation id was already used")
        return operation["receipt"]
    return None


def _commit_operation(
    state: Path,
    root: Path,
    reviews: Path,
    data: dict[str, Any],
    operation_id: str,
    fingerprint: str,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    data["operations"].append({"id": operation_id, "fingerprint": fingerprint, "receipt": receipt})
    _atomic_write(state, root, reviews, data)
    return receipt


def _freeze_snapshot(source_arg: str | Path, root: Path, reviews: Path, loop_id: str, round_number: int) -> tuple[dict[str, Any], Path | None]:
    source_raw = Path(source_arg)
    source = source_raw if source_raw.is_absolute() else root / source_raw
    source = _require_local_path(source, root, root)
    if not source.is_file() or _is_reparse(source):
        raise StateError("RLSTATE_PATH_ESCAPE", "artifact source must be a regular repository file")
    artifact_dir = _require_local_path(reviews / loop_id / "artifacts", root, reviews)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir = _require_local_path(artifact_dir, root, reviews)
    handle, temp_name = tempfile.mkstemp(prefix=f".round-{round_number}.", suffix=".tmp", dir=artifact_dir)
    temp = Path(temp_name)
    created: Path | None = None
    try:
        temp = _require_open_identity(temp, handle, root, reviews)
        outgoing = os.fdopen(handle, "wb")
        handle = -1
        with outgoing, source.open("rb") as incoming:
            shutil.copyfileobj(incoming, outgoing)
            outgoing.flush()
            os.fsync(outgoing.fileno())
        digest = _sha256(temp)
        destination = _require_local_path(
            artifact_dir / f"round-{round_number}-{digest}.snapshot",
            root,
            reviews,
        )
        if destination.exists():
            if _sha256(destination) != digest:
                raise StateError("RLSTATE_INVALID", "snapshot destination collision")
        else:
            temp = _require_local_path(temp, root, reviews)
            destination = _require_local_path(destination, root, reviews)
            os.replace(temp, destination)
            created = destination
            _fsync_directory(artifact_dir)
        return ({
            "kind": "snapshot",
            "revision": f"sha256:{digest}",
            "snapshot": _relative(destination, root),
            "source": _relative(source, root),
        }, created)
    except BaseException:
        if created is not None:
            created = _require_local_path(created, root, reviews)
            created.unlink(missing_ok=True)
        raise
    finally:
        if handle >= 0:
            os.close(handle)
        try:
            temp = _require_local_path(temp, root, reviews)
            temp.unlink()
        except FileNotFoundError:
            pass


def _freeze_git(revision_arg: str, root: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", f"{revision_arg}^{{commit}}"],
        text=True, capture_output=True, check=False,
    )
    object_id = result.stdout.strip().casefold()
    if result.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40,64}", object_id):
        raise StateError("RLSTATE_INVALID", "git revision does not resolve to a commit")
    return {"kind": "git-commit", "revision": f"git:{object_id}"}


def _new_round(number: int, diff: str, artifact: dict[str, Any]) -> dict[str, Any]:
    revision = artifact["revision"]
    return {
        "round": number,
        "phase": "admitted",
        "diff": diff,
        "artifact": artifact,
        **{
            lane: {
                "attempt_id": _attempt_id(lane, number),
                "artifact_revision": revision,
                "state": "admitted",
            }
            for lane in LANES
        },
        "lane_failures": [],
        "evidence": [],
    }


def _round(data: dict[str, Any], number: int) -> dict[str, Any]:
    if number < 1 or number > len(data["rounds"]):
        raise StateError("RLSTATE_INVALID", f"round={number} does not exist")
    return data["rounds"][number - 1]


def _attempt(rnd: dict[str, Any], lane: str, attempt_id: str) -> dict[str, Any]:
    if lane not in LANES:
        raise StateError("RLSTATE_ATTEMPT_MISMATCH", "lane is invalid")
    block = rnd[lane]
    if block["attempt_id"] != attempt_id:
        raise StateError("RLSTATE_ATTEMPT_MISMATCH", f"round={rnd['round']} lane={lane}")
    return block


def _mutate(args: argparse.Namespace, command: str, payload: dict[str, Any], transition: Callable[[dict[str, Any], Path, Path, Path], dict[str, Any]]) -> dict[str, Any]:
    root, reviews, state = _state_context(args.state)
    _require_local_path(state.parent, root, reviews)
    state.parent.mkdir(parents=True, exist_ok=True)
    state = _require_local_path(state, root, reviews)
    with _Lock(state.with_name(state.name + ".lock"), root, reviews):
        _recover_owned_resources(state, root, reviews, allow_absent=False)
        data = _load_v2(state, root, reviews)
        fingerprint = _fingerprint(command, payload)
        replay = _operation(data, args.operation_id, fingerprint)
        if replay is not None:
            return replay
        if data["status"] != "running":
            raise StateError("RLSTATE_INVALID", "terminal review-loop state is immutable")
        _verify_artifacts(data, root)
        receipt = transition(data, root, reviews, state)
        return _commit_operation(
            state,
            root,
            reviews,
            data,
            args.operation_id,
            fingerprint,
            receipt,
        )


def command_begin(args: argparse.Namespace) -> dict[str, Any]:
    root, reviews, state = _state_context(args.state)
    if not PORTABLE_ID.fullmatch(args.loop_id or ""):
        raise StateError("RLSTATE_INVALID", "loop id is not portable")
    expected_parent = reviews / args.loop_id
    if state.parent.absolute() != expected_parent.absolute():
        raise StateError("RLSTATE_PATH_ESCAPE", "state must belong to its loop directory")
    anchors = {
        "objective": _read_input(args.objective_file, "objective"),
        "scope": _read_input(args.scope_file, "scope"),
        "runtime_root": _read_input(args.runtime_root_file, "runtime_root"),
        "diff": _read_input(args.diff_file, "diff"),
    }
    source_identity = (
        {"artifact_file": _sha256(Path(args.artifact_file))}
        if args.artifact_file else {"git_revision": args.git_revision}
    )
    fingerprint = _fingerprint("begin", {"loop_id": args.loop_id, **anchors, **source_identity})
    _require_local_path(state.parent, root, reviews)
    state.parent.mkdir(parents=True, exist_ok=True)
    state = _require_local_path(state, root, reviews)
    created_snapshot: Path | None = None
    with _Lock(state.with_name(state.name + ".lock"), root, reviews):
        _recover_owned_resources(state, root, reviews, allow_absent=True)
        if state.exists():
            data = _load_v2(state, root, reviews)
            replay = _operation(data, args.operation_id, fingerprint)
            if replay is not None:
                return replay
            raise StateError("RLSTATE_OPERATION_CONFLICT", "state already exists")
        try:
            if args.artifact_file:
                artifact, created_snapshot = _freeze_snapshot(args.artifact_file, root, reviews, args.loop_id, 1)
            else:
                artifact = _freeze_git(args.git_revision, root)
            rnd = _new_round(1, anchors.pop("diff"), artifact)
            data = {
                "schema_version": 2,
                "loop_id": args.loop_id,
                **anchors,
                "status": "running",
                "operations": [],
                "rounds": [rnd],
            }
            receipt = _receipt(
                "begin", root, state, data, rnd,
                attempts={lane: rnd[lane]["attempt_id"] for lane in LANES},
            )
            return _commit_operation(
                state,
                root,
                reviews,
                data,
                args.operation_id,
                fingerprint,
                receipt,
            )
        except BaseException:
            if created_snapshot is not None:
                _cleanup_if_unreferenced(
                    state, root, reviews, created_snapshot
                )
            raise


def command_mark_running(args: argparse.Namespace) -> dict[str, Any]:
    payload = {"round": args.round, "lane": args.lane, "attempt_id": args.attempt_id}
    def transition(data: dict[str, Any], root: Path, _reviews: Path, state: Path) -> dict[str, Any]:
        rnd = _round(data, args.round)
        block = _attempt(rnd, args.lane, args.attempt_id)
        if block["state"] != "admitted":
            raise StateError("RLSTATE_INVALID", "only an admitted attempt may start")
        block["state"] = "running"
        rnd["phase"] = "collecting"
        return _receipt("mark-running", root, state, data, rnd, lane=args.lane, attempt_id=args.attempt_id)
    return _mutate(args, "mark-running", payload, transition)


def command_record_result(args: argparse.Namespace) -> dict[str, Any]:
    try:
        result_text = Path(args.result_file).read_text(encoding="utf-8")
    except OSError as exc:
        raise StateError("RLSTATE_INVALID", "result JSON is unreadable or invalid") from exc
    result, parse_error = _decode_bounded_json(result_text)
    if parse_error is not None:
        detail = (
            "result JSON nesting exceeds the supported limit"
            if parse_error == "JSON nesting exceeds the supported limit"
            else "result JSON is unreadable or invalid"
        )
        raise StateError("RLSTATE_INVALID", detail)
    payload = {"round": args.round, "lane": args.lane, "attempt_id": args.attempt_id, "artifact_revision": args.artifact_revision, "result": result}
    def transition(data: dict[str, Any], root: Path, _reviews: Path, state: Path) -> dict[str, Any]:
        rnd = _round(data, args.round)
        if args.artifact_revision != rnd["artifact"]["revision"]:
            raise StateError("RLSTATE_REVISION_MISMATCH", f"round={args.round} lane={args.lane} attempt={args.attempt_id}")
        block = _attempt(rnd, args.lane, args.attempt_id)
        if block["state"] not in {"admitted", "running"} or not isinstance(result, dict):
            raise StateError("RLSTATE_INVALID", "result cannot be recorded for this attempt")
        allowed = VERDICT_RESULT_FIELDS if args.lane in VERDICT_LANES else SCOUT_RESULT_FIELDS
        if set(result) - allowed:
            raise StateError("RLSTATE_INVALID", "result has unexpected fields")
        block.update(result)
        block["state"] = "complete"
        rnd["phase"] = "collecting"
        errors = validate_v2(data)
        if errors:
            raise StateError("RLSTATE_INVALID", errors[0])
        return _receipt("record-result", root, state, data, rnd, lane=args.lane, attempt_id=args.attempt_id)
    return _mutate(args, "record-result", payload, transition)


def command_record_failure(args: argparse.Namespace) -> dict[str, Any]:
    payload = {"round": args.round, "lane": args.lane, "attempt_id": args.attempt_id, "artifact_revision": args.artifact_revision, "failure": args.failure}
    def transition(data: dict[str, Any], root: Path, _reviews: Path, state: Path) -> dict[str, Any]:
        rnd = _round(data, args.round)
        if args.artifact_revision != rnd["artifact"]["revision"]:
            raise StateError("RLSTATE_REVISION_MISMATCH", f"round={args.round} lane={args.lane} attempt={args.attempt_id}")
        block = _attempt(rnd, args.lane, args.attempt_id)
        if block["state"] not in {"admitted", "running"}:
            raise StateError("RLSTATE_INVALID", "completed attempt cannot become a failure")
        if any(item["attempt_id"] == args.attempt_id for item in rnd["lane_failures"]):
            raise StateError("RLSTATE_INVALID", "failure is already recorded")
        rnd["lane_failures"].append({
            "lane": args.lane, "attempt_id": args.attempt_id,
            "artifact_revision": args.artifact_revision, "failure": args.failure,
        })
        rnd["phase"] = "collecting"
        return _receipt("record-failure", root, state, data, rnd, lane=args.lane, attempt_id=args.attempt_id)
    return _mutate(args, "record-failure", payload, transition)


def command_admit_retry(args: argparse.Namespace) -> dict[str, Any]:
    payload = {"round": args.round, "lane": args.lane, "failed_attempt_id": args.failed_attempt_id}
    def transition(data: dict[str, Any], root: Path, _reviews: Path, state: Path) -> dict[str, Any]:
        rnd = _round(data, args.round)
        failure = next((item for item in rnd["lane_failures"] if item["lane"] == args.lane and item["attempt_id"] == args.failed_attempt_id), None)
        if failure is None or "redispatched_as" in failure:
            raise StateError("RLSTATE_ATTEMPT_MISMATCH", "failed attempt is absent or already retried")
        if rnd[args.lane]["attempt_id"] != args.failed_attempt_id:
            raise StateError("RLSTATE_ATTEMPT_MISMATCH", "failed attempt is no longer current")
        attempt_id = _attempt_id(args.lane, args.round)
        revision = rnd["artifact"]["revision"]
        rnd[args.lane] = {"attempt_id": attempt_id, "artifact_revision": revision, "state": "admitted"}
        failure["redispatched_as"] = attempt_id
        return _receipt("admit-retry", root, state, data, rnd, lane=args.lane, attempt_id=attempt_id)
    return _mutate(args, "admit-retry", payload, transition)


def command_complete_round(args: argparse.Namespace) -> dict[str, Any]:
    payload = {"round": args.round}
    def transition(data: dict[str, Any], root: Path, _reviews: Path, state: Path) -> dict[str, Any]:
        rnd = _round(data, args.round)
        if any(rnd[lane]["state"] != "complete" for lane in LANES):
            raise StateError("RLSTATE_UNRESOLVED_FAILURE", "not every lane has a substantive result")
        if any(not _nonempty(item.get("redispatched_as")) for item in rnd["lane_failures"]):
            raise StateError("RLSTATE_UNRESOLVED_FAILURE", "failed lane lacks a successful retry")
        rnd["phase"] = "complete"
        return _receipt("complete-round", root, state, data, rnd)
    return _mutate(args, "complete-round", payload, transition)


def command_next_round(args: argparse.Namespace) -> dict[str, Any]:
    diff = _read_input(args.diff_file, "diff")
    root, reviews, state = _state_context(args.state)
    source_identity = {"artifact_file": _sha256(Path(args.artifact_file))} if args.artifact_file else {"git_revision": args.git_revision}
    payload = {"diff": diff, **source_identity}
    created: Path | None = None
    def transition(data: dict[str, Any], root: Path, reviews: Path, state: Path) -> dict[str, Any]:
        nonlocal created
        prior = data["rounds"][-1]
        if prior["phase"] != "complete" or not any(prior[lane].get("verdict") == "REVISE" for lane in VERDICT_LANES):
            raise StateError("RLSTATE_INVALID", "next round requires a complete REVISE round")
        number = len(data["rounds"]) + 1
        if number > REVIEW_LOOP_ROUND_CAP:
            raise StateError("RLSTATE_INVALID", "round cap exceeded")
        if args.artifact_file:
            artifact, created = _freeze_snapshot(args.artifact_file, root, reviews, data["loop_id"], number)
        else:
            artifact = _freeze_git(args.git_revision, root)
        rnd = _new_round(number, diff, artifact)
        data["rounds"].append(rnd)
        return _receipt("next-round", root, state, data, rnd, attempts={lane: rnd[lane]["attempt_id"] for lane in LANES})
    try:
        return _mutate(args, "next-round", payload, transition)
    except BaseException:
        if created is not None:
            _cleanup_if_unreferenced(state, root, reviews, created)
        raise


def command_close(args: argparse.Namespace) -> dict[str, Any]:
    payload = {"outcome": args.outcome}
    def transition(data: dict[str, Any], root: Path, _reviews: Path, state: Path) -> dict[str, Any]:
        rnd = data["rounds"][-1]
        if rnd["phase"] != "complete":
            raise StateError("RLSTATE_INVALID", "terminal outcome requires a complete round")
        if args.outcome == "converged":
            if any(rnd[lane].get("verdict") != "PASS" for lane in VERDICT_LANES):
                raise StateError("RLSTATE_INVALID", "converged requires a complete PASS round")
            if rnd["scout"].get("findings") and len(rnd["scout"].get("reconciliation", [])) < len(rnd["scout"]["findings"]):
                raise StateError("RLSTATE_INVALID", "scout findings remain unreconciled")
        elif not any(rnd[lane].get("verdict") == "REVISE" for lane in VERDICT_LANES):
            raise StateError("RLSTATE_INVALID", f"{args.outcome} requires a complete REVISE round")
        data["status"] = args.outcome
        return _receipt("close", root, state, data, rnd, outcome=args.outcome)
    return _mutate(args, "close", payload, transition)


def command_validate(args: argparse.Namespace) -> dict[str, Any]:
    root, reviews, state = _state_context(args.state)
    state = _require_local_path(state, root, reviews)
    data, error = load_ledger(state)
    if error:
        raise StateError("RLSTATE_INVALID", error)
    errors, is_v2 = validate_record(data, cap=args.cap, require_v2=args.require_v2, require_terminal=args.require_terminal)
    if errors:
        failure = errors[0] if errors[0].startswith("RLSTATE_") else "RLSTATE_INVALID"
        raise StateError(failure, errors[0] if failure == "RLSTATE_INVALID" else "")
    if not is_v2:
        print("RLSTATE_V1_READ_ONLY", file=sys.stderr)
    return {"event": RECEIPT_EVENT if is_v2 else "RLSTATE_V1_READ_ONLY", "command": "validate", "valid": True, "schema_version": 2 if is_v2 else 1}


def command_migrate_v1(args: argparse.Namespace) -> dict[str, Any]:
    root, reviews, state = _state_context(args.state)
    _require_local_path(state.parent, root, reviews)
    state.parent.mkdir(parents=True, exist_ok=True)
    state = _require_local_path(state, root, reviews)
    with _Lock(state.with_name(state.name + ".lock"), root, reviews):
        _recover_owned_resources(state, root, reviews, allow_absent=False)
        state = _require_local_path(state, root, reviews)
        original = state.read_bytes()
        try:
            data = json.loads(original.decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise StateError("RLSTATE_INVALID", "V1 JSON is unreadable") from exc
        if isinstance(data, dict) and data.get("schema_version") == 2:
            fingerprint = _fingerprint("migrate-v1", {"round_revision": args.round_revision})
            replay = _operation(data, args.operation_id, fingerprint)
            if replay is not None:
                return replay
            raise StateError("RLSTATE_OPERATION_CONFLICT", "state is already V2")
        errors = validate_v1(data, args.cap)
        if errors:
            raise StateError("RLSTATE_INVALID", errors[0])
        revisions: dict[int, str] = {}
        for item in args.round_revision:
            try:
                number_text, revision = item.split("=", 1)
                revisions[int(number_text)] = revision
            except (ValueError, TypeError) as exc:
                raise StateError("RLSTATE_INVALID", "round revision must be N=revision") from exc
        if set(revisions) != set(range(1, len(data["rounds"]) + 1)):
            raise StateError("RLSTATE_INVALID", "every V1 round requires an explicit revision")
        backup = _require_local_path(
            state.with_name(state.name + ".v1-backup"),
            root,
            reviews,
        )
        if backup.exists():
            raise StateError("RLSTATE_OPERATION_CONFLICT", "migration backup already exists")
        try:
            backup = _require_local_path(backup, root, reviews)
            try:
                descriptor = os.open(
                    backup,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
                    0o600,
                )
            except FileExistsError as exc:
                _require_local_path(backup, root, reviews)
                raise StateError(
                    "RLSTATE_OPERATION_CONFLICT", "migration backup already exists"
                ) from exc
            try:
                backup = _require_open_identity(backup, descriptor, root, reviews)
            except BaseException:
                os.close(descriptor)
                raise
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(original)
                stream.flush()
                os.fsync(stream.fileno())
            _fsync_directory(backup.parent)
            operations: list[dict[str, Any]] = []
            rounds: list[dict[str, Any]] = []
            for number, old in enumerate(data["rounds"], 1):
                revision = revisions[number]
                if not GIT_REVISION.fullmatch(revision):
                    raise StateError("RLSTATE_INVALID", "migration currently requires authoritative git:<full-object-id> revisions")
                _freeze_git(revision.removeprefix("git:"), root)
                artifact = {"kind": "git-commit", "revision": revision}
                rnd = _new_round(number, old["diff"], artifact)
                for lane in LANES:
                    old_block = old[lane]
                    migrated_block: dict[str, Any] = {
                        "attempt_id": old_block["attempt_id"],
                        "artifact_revision": revision,
                        "state": "complete",
                    }
                    if lane in VERDICT_LANES:
                        migrated_block["verdict"] = old_block["verdict"].upper()
                        if _nonempty(old_block.get("rationale")):
                            migrated_block["rationale"] = old_block["rationale"]
                        if isinstance(old_block.get("blockers"), list):
                            migrated_block["blockers"] = old_block["blockers"]
                        for key in (
                            "root_proven",
                            "scope_unchanged",
                            "verification_adequate",
                        ):
                            value = old_block.get(key)
                            migrated_block[key] = (
                                value if _nonempty(value) else "legacy-v1-not-recorded"
                            )
                    else:
                        migrated_block["findings"] = old_block["findings"]
                        reconciliation = old_block.get("reconciliation")
                        migrated_block["reconciliation"] = (
                            reconciliation if isinstance(reconciliation, list) else []
                        )
                    rnd[lane] = migrated_block
                rnd["lane_failures"] = [{**entry, "artifact_revision": revision} for entry in old["lane_failures"]]
                rnd["evidence"] = old.get("evidence", [])
                rnd["phase"] = "complete"
                rounds.append(rnd)
            migrated = {
                "schema_version": 2, "loop_id": state.parent.name,
                "objective": data["objective"], "scope": data["scope"],
                "runtime_root": data["runtime_root"], "status": "running",
                "operations": operations, "rounds": rounds,
            }
            fingerprint = _fingerprint("migrate-v1", {"round_revision": args.round_revision})
            receipt = _receipt("migrate-v1", root, state, migrated, rounds[-1], backup=_relative(backup, root))
            operations.append({"id": args.operation_id, "fingerprint": fingerprint, "receipt": receipt})
            _atomic_write(state, root, reviews, migrated)
        except BaseException:
            _cleanup_if_unreferenced(state, root, reviews, backup)
            raise
        return receipt


def command_rollback_migration(args: argparse.Namespace) -> dict[str, Any]:
    root, reviews, state = _state_context(args.state)
    with _Lock(state.with_name(state.name + ".lock"), root, reviews):
        _recover_owned_resources(state, root, reviews, allow_absent=False)
        data = _load_v2(state, root, reviews)
        if len(data["operations"]) != 1 or data["operations"][0]["receipt"].get("command") != "migrate-v1":
            raise StateError("RLSTATE_OPERATION_CONFLICT", "migration is not the latest and only V2 operation")
        receipt_path = Path(args.migration_receipt)
        try:
            supplied = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StateError("RLSTATE_INVALID", "migration receipt is unreadable") from exc
        if supplied != data["operations"][0]["receipt"]:
            raise StateError("RLSTATE_OPERATION_CONFLICT", "migration receipt mismatch")
        backup = _require_local_path(
            root / supplied["backup"],
            root,
            root / ".scratch" / "reviews",
        )
        if not backup.is_file():
            raise StateError("RLSTATE_INVALID", "V1 backup is missing")
        backup = _require_local_path(backup, root, reviews)
        state = _require_local_path(state, root, reviews)
        os.replace(backup, state)
        _fsync_directory(state.parent)
        return {"event": "RLSTATE_V1_READ_ONLY", "command": "rollback-migration", "state": _relative(state, root)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def state_parser(name: str, *, operation: bool = False) -> argparse.ArgumentParser:
        item = sub.add_parser(name)
        item.add_argument("--state", required=True)
        if operation:
            item.add_argument("--operation-id", required=True)
        return item

    begin = state_parser("begin", operation=True)
    begin.add_argument("--loop-id", required=True)
    begin.add_argument("--objective-file", required=True)
    begin.add_argument("--scope-file", required=True)
    begin.add_argument("--runtime-root-file", required=True)
    begin.add_argument("--diff-file", required=True)
    artifact = begin.add_mutually_exclusive_group(required=True)
    artifact.add_argument("--artifact-file")
    artifact.add_argument("--git-revision")

    running = state_parser("mark-running", operation=True)
    running.add_argument("--round", type=int, required=True)
    running.add_argument("--lane", choices=LANES, required=True)
    running.add_argument("--attempt-id", required=True)

    result = state_parser("record-result", operation=True)
    result.add_argument("--round", type=int, required=True)
    result.add_argument("--lane", choices=LANES, required=True)
    result.add_argument("--attempt-id", required=True)
    result.add_argument("--artifact-revision", required=True)
    result.add_argument("--result-file", required=True)

    failure = state_parser("record-failure", operation=True)
    failure.add_argument("--round", type=int, required=True)
    failure.add_argument("--lane", choices=LANES, required=True)
    failure.add_argument("--attempt-id", required=True)
    failure.add_argument("--artifact-revision", required=True)
    failure.add_argument("--failure", choices=FAILURE_KINDS, required=True)

    retry = state_parser("admit-retry", operation=True)
    retry.add_argument("--round", type=int, required=True)
    retry.add_argument("--lane", choices=LANES, required=True)
    retry.add_argument("--failed-attempt-id", required=True)

    complete = state_parser("complete-round", operation=True)
    complete.add_argument("--round", type=int, required=True)

    next_round = state_parser("next-round", operation=True)
    next_round.add_argument("--diff-file", required=True)
    next_artifact = next_round.add_mutually_exclusive_group(required=True)
    next_artifact.add_argument("--artifact-file")
    next_artifact.add_argument("--git-revision")

    close = state_parser("close", operation=True)
    close.add_argument("--outcome", choices=OUTCOMES, required=True)

    validate = state_parser("validate")
    validate.add_argument("--cap", type=int, default=REVIEW_LOOP_ROUND_CAP)
    validate.add_argument("--require-v2", action="store_true")
    validate.add_argument("--require-terminal", action="store_true")

    migrate = state_parser("migrate-v1", operation=True)
    migrate.add_argument("--cap", type=int, default=REVIEW_LOOP_ROUND_CAP)
    migrate.add_argument("--round-revision", action="append", default=[], required=True)

    rollback = state_parser("rollback-migration")
    rollback.add_argument("--migration-receipt", required=True)
    return parser


COMMANDS: dict[str, Callable[[argparse.Namespace], dict[str, Any]]] = {
    "begin": command_begin,
    "mark-running": command_mark_running,
    "record-result": command_record_result,
    "record-failure": command_record_failure,
    "admit-retry": command_admit_retry,
    "complete-round": command_complete_round,
    "next-round": command_next_round,
    "close": command_close,
    "validate": command_validate,
    "migrate-v1": command_migrate_v1,
    "rollback-migration": command_rollback_migration,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        receipt = COMMANDS[args.command](args)
    except KeyboardInterrupt:
        print("RLSTATE_CANCELLED", file=sys.stderr)
        return 130
    except (StateError, OSError, ValueError) as exc:
        if isinstance(exc, StateError):
            print(str(exc), file=sys.stderr)
        else:
            print(f"RLSTATE_INVALID: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


def validator_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Structural validator for review-loop-state V1/V2 records")
    parser.add_argument("ledger", nargs="?")
    parser.add_argument("--cap", type=int, default=REVIEW_LOOP_ROUND_CAP)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        good = {
            "objective": "o", "scope": "s", "runtime_root": "r",
            "rounds": [{
                "round": 1, "diff": "initial",
                "surgical": {"attempt_id": "s1", "verdict": "PASS", "rationale": "specific"},
                "deep": {"attempt_id": "d1", "verdict": "PASS", "rationale": "specific"},
                "scout": {"attempt_id": "c1", "findings": []}, "lane_failures": [],
            }],
        }
        redispatch = json.loads(json.dumps(good))
        redispatch["rounds"][0]["scout"]["attempt_id"] = "c2"
        redispatch["rounds"][0]["lane_failures"] = [{
            "lane": "scout",
            "attempt_id": "c1",
            "failure": "died",
            "redispatched_as": "c2",
        }]
        good_cases = {
            "sample-good": good,
            "sample-good-redispatch": redispatch,
        }

        def changed(mutator: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
            candidate = json.loads(json.dumps(good))
            mutator(candidate)
            return candidate

        def unresolved(candidate: dict[str, Any]) -> None:
            candidate["rounds"][0]["lane_failures"] = [{
                "lane": "scout",
                "attempt_id": "old-c",
                "failure": "died",
                "redispatched_as": "",
            }]

        def wrong_lane(candidate: dict[str, Any]) -> None:
            candidate["rounds"][0]["lane_failures"] = [{
                "lane": "scout",
                "attempt_id": "old-c",
                "failure": "died",
                "redispatched_as": "s1",
            }]

        bad_cases = {
            "sample-bad": {"objective": "o", "scope": "s", "rounds": []},
            "null-verdict": changed(lambda item: item["rounds"][0]["surgical"].update(verdict=None)),
            "missing-lane": changed(lambda item: item["rounds"][0].pop("deep")),
            "null-findings": changed(lambda item: item["rounds"][0]["scout"].update(findings=None)),
            "unresolved-failure": changed(unresolved),
            "wrong-lane-redispatch": changed(wrong_lane),
            "missing-attempt-id": changed(lambda item: item["rounds"][0]["deep"].pop("attempt_id")),
            "duplicate-attempt-id": changed(lambda item: item["rounds"][0]["deep"].update(attempt_id="s1")),
        }
        failures = [
            f"{name} ledger was rejected but should pass"
            for name, ledger in good_cases.items()
            if validate_v1(ledger, args.cap)
        ]
        failures.extend(
            f"{name} ledger was accepted but should be rejected"
            for name, ledger in bad_cases.items()
            if not validate_v1(ledger, args.cap)
        )
        if failures:
            print("SELF-TEST FAIL")
            for failure in failures:
                print(f"  {failure}")
            return 1
        print("SELF-TEST PASS")
        for name in good_cases:
            print(f"  {name}: accepted (0 structural errors)")
        for name, ledger in bad_cases.items():
            print(f"  {name}: rejected ({len(validate_v1(ledger, args.cap))} structural error(s))")
        return 0
    if not args.ledger:
        parser.error("a ledger path is required unless --self-test is given")
    data, error = load_ledger(args.ledger)
    if error:
        print(f"FAIL: {error}")
        return 1
    errors, is_v2 = validate_record(data, args.cap)
    if errors:
        print(f"FAIL: review-loop-state ledger has {len(errors)} structural error(s):")
        for error_text in errors:
            print(f"  - {error_text}")
        return 1
    if not is_v2:
        print("WARNING: RLSTATE_V1_READ_ONLY")
    print("PASS: review-loop-state ledger is structurally valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
