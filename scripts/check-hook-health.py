#!/usr/bin/env python3
"""Read-only validation for installed Orchestrarium hook registrations."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import queue
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Iterable


CODEX_TRUST_MODES = frozenset({"report", "require"})
INVENTORY_NAME = "codex-hook-inventory.json"
FAILURE_ENVELOPE_MAX_BYTES = 4096
FAILURE_CAUSE_MAX_BYTES = 2048
HEALTH_FAILURE_IDS = frozenset(
    {"E_HOOK_INVENTORY_TARGET_INVALID", "E_HOOK_HEALTH_FAILED"}
)
MAX_STDOUT_BYTES = 2 * 1024 * 1024
MAX_STDOUT_LINE_BYTES = 256 * 1024
MAX_STDOUT_MESSAGES = 256
MAX_HOOK_PATH_LINKS = 64
_CHILD_ENV_KEYS = frozenset(
    {
        "COMSPEC",
        "LANG",
        "LC_ALL",
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "TEMP",
        "TERM",
        "TMP",
        "TMPDIR",
        "WINDIR",
    }
)


class _HookHealthFailure(ValueError):
    severity = "fatal"

    def __init__(self, stable_id: str, context: str, cause: str) -> None:
        self.stable_id = stable_id
        self.context = context
        self.cause = cause
        super().__init__(f"{stable_id}: {cause}")


class _InventoryAuthority:
    def __init__(
        self,
        *,
        target: Path,
        resolved_target: Path,
        inventory: Path,
        logical_parent_identity: tuple[int, int, int, int],
        link_chain: tuple[
            tuple[str, tuple[int, int, int, int], str, str], ...
        ],
        target_identity: tuple[int, int, int, int],
        parent_identity: tuple[int, int, int, int],
        inventory_identity: tuple[int, int, int, int] | None,
    ) -> None:
        self.target = target
        self.resolved_target = resolved_target
        self.inventory = inventory
        self.logical_parent_identity = logical_parent_identity
        self.link_chain = link_chain
        self.target_identity = target_identity
        self.parent_identity = parent_identity
        self.inventory_identity = inventory_identity


def _failure_envelope_bytes(failure: _HookHealthFailure) -> bytes:
    stable_id = failure.stable_id
    context = failure.context
    cause = failure.cause
    valid = (
        stable_id in HEALTH_FAILURE_IDS
        and context in {"inventory", "health"}
        and ((stable_id == "E_HOOK_INVENTORY_TARGET_INVALID") == (context == "inventory"))
        and len(cause.encode("utf-8", errors="strict")) <= FAILURE_CAUSE_MAX_BYTES
    )
    if not valid:
        stable_id = "E_HOOK_HEALTH_FAILED"
        context = "health"
        cause = "failure-envelope-limit"
    payload = json.dumps(
        {
            "schemaVersion": 1,
            "severity": "fatal",
            "stableId": stable_id,
            "context": context,
            "cause": cause,
        },
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8", errors="strict") + b"\n"
    if len(payload) > FAILURE_ENVELOPE_MAX_BYTES:
        return _failure_envelope_bytes(
            _HookHealthFailure(
                "E_HOOK_HEALTH_FAILED", "health", "failure-envelope-limit"
            )
        )
    return payload


def _write_failure_envelope(failure: _HookHealthFailure) -> None:
    payload = _failure_envelope_bytes(failure)
    binary = getattr(sys.stderr, "buffer", None)
    if binary is None:
        sys.stderr.write(payload.decode("utf-8"))
        sys.stderr.flush()
        return
    binary.write(payload)
    binary.flush()


def _lexical_absolute(path: Path) -> Path:
    value = os.path.abspath(os.path.expanduser(str(path)))
    if os.name == "nt":
        if value.startswith("\\\\?\\UNC\\"):
            value = "\\\\" + value[8:]
        elif value.startswith("\\\\?\\"):
            value = value[4:]
    return Path(value)


def _path_identity(path: Path) -> tuple[int, int, int, int]:
    metadata = path.lstat()
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        getattr(metadata, "st_file_attributes", 0),
    )


def _is_link_or_reparse(metadata: os.stat_result) -> bool:
    return bool(
        stat.S_ISLNK(metadata.st_mode)
        or (
            getattr(metadata, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        )
    )


def _same_path(first: Path, second: Path) -> bool:
    return os.path.normcase(str(first)) == os.path.normcase(str(second))


def _path_walk(path: Path) -> tuple[Path, list[str]]:
    if not path.is_absolute() or not path.anchor:
        raise ValueError(f"hooks target path is not absolute: {path}")
    return Path(path.anchor), list(path.parts[1:])


def _link_kind(path: Path, metadata: os.stat_result) -> str | None:
    if stat.S_ISLNK(metadata.st_mode):
        return "symlink"
    is_junction = getattr(os.path, "isjunction", lambda _path: False)
    if is_junction(path):
        return "junction"
    if _is_link_or_reparse(metadata):
        raise ValueError(f"hooks target contains unsupported reparse component: {path}")
    return None


def _resolve_hooks_target(
    target: Path, *, allow_missing_ordinary: bool
) -> tuple[
    Path,
    tuple[tuple[str, tuple[int, int, int, int], str, str], ...],
    tuple[int, int, int, int] | None,
]:
    selected_target = _lexical_absolute(target)
    current, pending = _path_walk(selected_target)
    seen: set[str] = set()
    links: list[tuple[str, tuple[int, int, int, int], str, str]] = []
    while pending:
        candidate = current / pending.pop(0)
        try:
            metadata = candidate.lstat()
        except FileNotFoundError:
            if allow_missing_ordinary and not links:
                return selected_target, (), None
            raise ValueError(f"hooks target link chain is dangling: {selected_target}")

        kind = _link_kind(candidate, metadata)
        if kind is not None:
            if len(links) >= MAX_HOOK_PATH_LINKS:
                raise ValueError("hooks target link chain exceeds bounded depth")
            key = os.path.normcase(str(candidate))
            if key in seen:
                raise ValueError(f"hooks target link cycle detected at {candidate}")
            seen.add(key)
            try:
                raw_target = os.readlink(candidate)
            except OSError as exc:
                raise ValueError(f"cannot read hooks target link {candidate}: {exc}") from exc
            links.append(
                (str(candidate), _path_identity(candidate), raw_target, kind)
            )
            next_target = Path(raw_target)
            resolved_component = _lexical_absolute(
                next_target
                if next_target.is_absolute()
                else candidate.parent / next_target
            )
            combined = resolved_component.joinpath(*pending)
            current, pending = _path_walk(combined)
            continue
        if pending:
            if not stat.S_ISDIR(metadata.st_mode):
                raise ValueError(f"hooks target parent is not a directory: {candidate}")
            current = candidate
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("hooks target link chain does not resolve to an ordinary file")
        return candidate, tuple(links), _path_identity(candidate)

    if allow_missing_ordinary and not links:
        return selected_target, (), None
    raise ValueError(f"hooks target path is incomplete: {selected_target}")


def _inventory_authority(
    target: Path,
    inventory_path: Path | None,
    *,
    for_write: bool,
) -> _InventoryAuthority:
    try:
        selected_target = _lexical_absolute(target)
        resolved_target, link_chain, target_identity = _resolve_hooks_target(
            selected_target, allow_missing_ordinary=False
        )
        assert target_identity is not None
        logical_parent = selected_target.parent
        parent = resolved_target.parent
        exact_inventory = parent / INVENTORY_NAME
        selected_inventory = _lexical_absolute(
            inventory_path if inventory_path is not None else exact_inventory
        )
        if os.path.normcase(str(selected_inventory)) != os.path.normcase(
            str(exact_inventory)
        ):
            raise ValueError("inventory must be the exact hooks-target sibling")
        inventory_identity = None
        try:
            inventory_metadata = selected_inventory.lstat()
        except FileNotFoundError:
            if not for_write:
                raise ValueError("hook inventory is missing")
        else:
            if _is_link_or_reparse(inventory_metadata) or not stat.S_ISREG(
                inventory_metadata.st_mode
            ):
                raise ValueError("hook inventory is not an ordinary file")
            inventory_identity = _path_identity(selected_inventory)
        return _InventoryAuthority(
            target=selected_target,
            resolved_target=resolved_target,
            inventory=selected_inventory,
            logical_parent_identity=_path_identity(logical_parent),
            link_chain=link_chain,
            target_identity=target_identity,
            parent_identity=_path_identity(parent),
            inventory_identity=inventory_identity,
        )
    except _HookHealthFailure:
        raise
    except (OSError, ValueError) as exc:
        raise _HookHealthFailure(
            "E_HOOK_INVENTORY_TARGET_INVALID", "inventory", str(exc)
        ) from exc


def _require_same_hook_target_authority(
    authority: _InventoryAuthority, current: _InventoryAuthority
) -> None:
    if current.logical_parent_identity != authority.logical_parent_identity:
        raise _HookHealthFailure(
            "E_HOOK_INVENTORY_TARGET_INVALID",
            "inventory",
            "hooks target logical parent identity changed",
        )
    if current.link_chain != authority.link_chain:
        raise _HookHealthFailure(
            "E_HOOK_INVENTORY_TARGET_INVALID",
            "inventory",
            "hooks target symlink identity or target changed",
        )
    if not _same_path(current.resolved_target, authority.resolved_target):
        raise _HookHealthFailure(
            "E_HOOK_INVENTORY_TARGET_INVALID",
            "inventory",
            "resolved hooks target changed",
        )
    if current.target_identity != authority.target_identity:
        raise _HookHealthFailure(
            "E_HOOK_INVENTORY_TARGET_INVALID",
            "inventory",
            "resolved hooks target identity changed",
        )
    if current.parent_identity != authority.parent_identity:
        raise _HookHealthFailure(
            "E_HOOK_INVENTORY_TARGET_INVALID",
            "inventory",
            "hooks target parent identity changed",
        )


def _recheck_inventory_authority(
    authority: _InventoryAuthority, *, for_write: bool
) -> _InventoryAuthority:
    current = _inventory_authority(
        authority.target, authority.inventory, for_write=for_write
    )
    _require_same_hook_target_authority(authority, current)
    if (
        authority.inventory_identity is not None
        and current.inventory_identity != authority.inventory_identity
    ):
        raise _HookHealthFailure(
            "E_HOOK_INVENTORY_TARGET_INVALID",
            "inventory",
            "hook inventory identity changed",
        )
    return current


def _event_identity(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _command_identity(argv: list[str], host_os: str) -> str:
    """Return the host-normalized command component of an owned identity."""
    values = [value.replace("\\", "/") for value in argv]
    if host_os == "windows":
        values = [value.casefold() for value in values]
    return "\0".join(values)


def _source_identity(path: Path | str, host_os: str) -> str:
    value = str(Path(path).expanduser().resolve(strict=False)).replace("\\", "/")
    return value.casefold() if host_os == "windows" else value


def canonical_identity(
    event: str,
    argv: list[str],
    host_os: str,
    *,
    matcher: str | None,
    source_path: Path | str,
) -> str:
    """Return the complete host-registration fingerprint used for trust admission."""
    return json.dumps(
        {
            "event": _event_identity(event),
            "matcher": matcher,
            "handlerType": "command",
            "command": _command_identity(argv, host_os),
            "sourcePath": _source_identity(source_path, host_os),
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _host_identity(record: dict[str, Any], host_os: str) -> str:
    event = record.get("eventName")
    matcher = record.get("matcher")
    handler_type = record.get("handlerType")
    command = record.get("command")
    source_path = record.get("sourcePath")
    if (
        not isinstance(event, str)
        or matcher is not None and not isinstance(matcher, str)
        or not isinstance(handler_type, str)
        or not isinstance(command, str)
        or not isinstance(source_path, str)
    ):
        raise ValueError(
            "FAIL CODEX_HOOK_LIST_MALFORMED: hook record lacks fingerprint fields"
        )
    if handler_type != "command":
        raise ValueError("FAIL CODEX_HOOK_LIST_MALFORMED: owned hook has non-command handler type")
    argv = _split_windows_command(command) if host_os == "windows" else shlex.split(command)
    if not argv:
        raise ValueError("FAIL CODEX_HOOK_LIST_MALFORMED: hook command is empty")
    return canonical_identity(
        event,
        argv,
        host_os,
        matcher=matcher,
        source_path=source_path,
    )


def resolve_codex_command(value: str | None = None) -> list[str]:
    """Resolve one absolute command prefix that both inventory and launch can reuse."""
    resolved = shutil.which(value or "codex")
    if not resolved:
        candidate = Path(value).expanduser() if value else None
        if candidate is None or not candidate.is_file():
            raise ValueError("FAIL CODEX_HOOK_LIST_UNAVAILABLE: codex executable is unavailable")
        resolved = str(candidate.resolve())
    path = Path(resolved).resolve()
    if not path.is_file():
        raise ValueError("FAIL CODEX_HOOK_LIST_UNAVAILABLE: codex executable is unavailable")
    if path.suffix.casefold() == ".py":
        return [str(Path(sys.executable).resolve()), str(path)]
    if os.name == "nt" and path.suffix.casefold() in {".cmd", ".bat"}:
        comspec = Path(os.environ.get("COMSPEC", "C:/Windows/System32/cmd.exe")).resolve()
        if not comspec.is_file():
            raise ValueError("FAIL CODEX_HOOK_LIST_UNAVAILABLE: command processor is unavailable")
        return [str(comspec), "/d", "/s", "/c", str(path)]
    return [str(path)]


def _minimal_codex_env(codex_home: Path) -> dict[str, str]:
    child = {key: value for key, value in os.environ.items() if key.upper() in _CHILD_ENV_KEYS}
    child["CODEX_HOME"] = str(codex_home)
    return child


def _codex_hooks_list(
    *,
    codex_command: list[str],
    codex_home: Path,
    query_cwd: Path,
    timeout: float = 15,
) -> list[dict[str, Any]]:
    """Ask the Codex host for its current hook admission inventory, read-only."""
    if not codex_command or not Path(codex_command[0]).is_absolute():
        raise ValueError("FAIL CODEX_HOOK_LIST_UNAVAILABLE: Codex command is not absolute")
    initialize = {
        "id": 1,
        "method": "initialize",
        "params": {
            "clientInfo": {"name": "orchestrarium-hook-health", "version": "1"},
            "capabilities": {},
        },
    }
    hooks_list = {
        "id": 2,
        "method": "hooks/list",
        "params": {"cwds": [str(query_cwd.resolve())]},
    }
    process: subprocess.Popen[bytes] | None = None
    readers: list[threading.Thread] = []
    messages: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=MAX_STDOUT_MESSAGES)
    reader_errors: queue.Queue[BaseException] = queue.Queue(maxsize=1)
    response: dict[str, Any] | None = None
    try:
        process = subprocess.Popen(
            [*codex_command, "app-server", "--listen", "stdio://"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=query_cwd,
            env=_minimal_codex_env(codex_home),
        )
        assert process.stdin is not None and process.stdout is not None and process.stderr is not None

        def record_reader_error(exc: BaseException) -> None:
            try:
                reader_errors.put_nowait(exc)
            except queue.Full:
                pass

        def read_stdout() -> None:
            total_bytes = 0
            message_count = 0
            while True:
                line = process.stdout.readline(MAX_STDOUT_LINE_BYTES + 1)
                if not line:
                    return
                if len(line) > MAX_STDOUT_LINE_BYTES:
                    record_reader_error(ValueError("stdout line limit exceeded"))
                    return
                total_bytes += len(line)
                if total_bytes > MAX_STDOUT_BYTES:
                    record_reader_error(ValueError("stdout byte limit exceeded"))
                    return
                try:
                    decoded = json.loads(line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    record_reader_error(exc)
                    return
                if not isinstance(decoded, dict):
                    record_reader_error(ValueError("JSON-RPC message is not an object"))
                    return
                message_count += 1
                if message_count > MAX_STDOUT_MESSAGES:
                    record_reader_error(ValueError("stdout message limit exceeded"))
                    return
                try:
                    messages.put_nowait(decoded)
                except queue.Full:
                    record_reader_error(ValueError("stdout message queue limit exceeded"))
                    return

        def drain_stderr() -> None:
            # Drain to prevent child blockage; diagnostics intentionally discard
            # provider text so credentials and machine-local state cannot leak.
            while process.stderr.read(8192):
                pass

        readers = [
            threading.Thread(target=read_stdout, daemon=True),
            threading.Thread(target=drain_stderr, daemon=True),
        ]
        for reader in readers:
            reader.start()

        def read_response(identifier: int) -> dict[str, Any]:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    reader_error = reader_errors.get_nowait()
                except queue.Empty:
                    reader_error = None
                if reader_error is not None:
                    raise ValueError("FAIL CODEX_HOOK_LIST_BOUNDS: stdout intake rejected") from reader_error
                try:
                    message = messages.get(timeout=min(0.05, max(0.001, deadline - time.monotonic())))
                except queue.Empty:
                    return_code = process.poll()
                    if return_code is not None:
                        raise ChildProcessError(f"app-server exited with code {return_code}")
                    continue
                if message.get("id") == identifier:
                    if "error" in message:
                        raise ValueError(
                            f"FAIL CODEX_HOOK_LIST_PROTOCOL_ERROR: request {identifier} failed"
                        )
                    if not isinstance(message.get("result"), dict):
                        raise ValueError(
                            f"FAIL CODEX_HOOK_LIST_MALFORMED: request {identifier} result is missing"
                        )
                    return message
            raise subprocess.TimeoutExpired([*codex_command, "app-server"], timeout)

        process.stdin.write((json.dumps(initialize) + "\n").encode("utf-8"))
        process.stdin.flush()
        read_response(1)
        process.stdin.write((json.dumps({"method": "initialized"}) + "\n").encode("utf-8"))
        process.stdin.flush()
        process.stdin.write((json.dumps(hooks_list) + "\n").encode("utf-8"))
        process.stdin.flush()
        response = read_response(2)
        return_code = process.poll()
        if return_code not in {None, 0}:
            raise ChildProcessError(f"app-server exited with code {return_code}")
        try:
            reader_error = reader_errors.get_nowait()
        except queue.Empty:
            reader_error = None
        if reader_error is not None:
            raise ValueError("FAIL CODEX_HOOK_LIST_BOUNDS: stdout intake rejected") from reader_error
    except (ChildProcessError, OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("FAIL CODEX_HOOK_LIST_UNAVAILABLE: app-server query failed") from exc
    finally:
        if process is not None:
            if process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        process.kill()
                        process.wait(timeout=5)
                    except (OSError, subprocess.TimeoutExpired):
                        pass
            else:
                try:
                    process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass
        for reader in readers:
            reader.join(timeout=5)
    if not isinstance(response, dict) or not isinstance(response.get("result"), dict):
        raise ValueError("FAIL CODEX_HOOK_LIST_MALFORMED: hooks/list response is missing")
    data = response["result"].get("data")
    if not isinstance(data, list):
        raise ValueError("FAIL CODEX_HOOK_LIST_MALFORMED: hooks/list data is not an array")
    records: list[dict[str, Any]] = []
    for scope in data:
        if not isinstance(scope, dict) or not isinstance(scope.get("hooks"), list):
            raise ValueError("FAIL CODEX_HOOK_LIST_MALFORMED: hooks/list scope is malformed")
        for record in scope["hooks"]:
            if not isinstance(record, dict):
                raise ValueError("FAIL CODEX_HOOK_LIST_MALFORMED: hook record is not an object")
            records.append(record)
    return records


def _reconcile_codex_trust(
    *,
    rows: list[tuple[str, str, list[str], str | None]],
    target: Path,
    host_os: str,
    mode: str,
    touched_identities: set[str],
    codex_command: list[str],
    codex_home: Path,
    query_cwd: Path,
) -> list[str]:
    if mode not in CODEX_TRUST_MODES:
        raise ValueError(f"unsupported Codex trust mode: {mode}")
    owned = {
        canonical_identity(
            event,
            argv,
            host_os,
            matcher=matcher,
            source_path=target,
        )
        for event, _stem, argv, matcher in rows
    }
    invalid_touched = sorted(touched_identities - owned)
    if invalid_touched:
        raise ValueError(
            "FAIL CODEX_HOOK_TRANSACTION_IDENTITY_INVALID: " + ", ".join(invalid_touched)
        )
    host_matches: dict[str, list[dict[str, Any]]] = {identity: [] for identity in owned}
    owned_without_source = {
        json.dumps(
            {key: value for key, value in json.loads(identity).items() if key != "sourcePath"},
            separators=(",", ":"),
            sort_keys=True,
        ): identity
        for identity in owned
    }
    for record in _codex_hooks_list(
        codex_command=codex_command,
        codex_home=codex_home,
        query_cwd=query_cwd,
    ):
        try:
            identity = _host_identity(record, host_os)
        except ValueError:
            # Foreign handlers are outside this pack. A malformed record that
            # claims our exact source is not foreign and fails closed.
            source_path = record.get("sourcePath")
            if isinstance(source_path, str) and _source_identity(source_path, host_os) == _source_identity(target, host_os):
                raise
            continue
        if identity in host_matches:
            host_matches[identity].append(record)
            continue
        without_source = json.dumps(
            {key: value for key, value in json.loads(identity).items() if key != "sourcePath"},
            separators=(",", ":"),
            sort_keys=True,
        )
        if without_source in owned_without_source:
            raise ValueError(
                "FAIL CODEX_HOOK_LIST_SOURCE_MISMATCH: "
                + owned_without_source[without_source]
            )
    messages: list[str] = []
    pending: list[str] = []
    for identity in sorted(owned):
        matching = host_matches[identity]
        if not matching:
            raise ValueError(f"FAIL CODEX_HOOK_LIST_MISSING: {identity}")
        if len(matching) != 1:
            raise ValueError(f"FAIL CODEX_HOOK_LIST_DUPLICATE: {identity}")
        record = matching[0]
        status = record.get("trustStatus")
        current_hash = record.get("currentHash")
        enabled = record.get("enabled")
        if (
            not isinstance(status, str)
            or not isinstance(current_hash, str)
            or not current_hash
            or not isinstance(enabled, bool)
        ):
            raise ValueError(f"FAIL CODEX_HOOK_LIST_MALFORMED: {identity}")
        if not enabled:
            raise ValueError(f"FAIL CODEX_HOOK_TRUST_DISABLED: {identity}")
        if status == "trusted":
            messages.append(f"PASS CODEX_HOOK_TRUST_TRUSTED {identity}")
            continue
        if status not in {"untrusted", "modified"}:
            raise ValueError(
                f"FAIL CODEX_HOOK_TRUST_UNEXPECTED: {identity} status={status} hash={current_hash}"
            )
        if mode == "report" and identity in touched_identities:
            pending.append(f"{identity} status={status} hash={current_hash}")
            continue
        if mode == "report":
            raise ValueError(
                f"FAIL CODEX_HOOK_TRUST_PREEXISTING_DRIFT: {identity} status={status} hash={current_hash}"
            )
        discriminator = "UNTRUSTED" if status == "untrusted" else "MODIFIED"
        raise ValueError(
            f"FAIL CODEX_HOOK_TRUST_{discriminator}: {identity} status={status} hash={current_hash}"
        )
    if pending:
        messages.append("PENDING_MANUAL_TRUST " + "; ".join(pending))
    return messages


def owned_canonical_identities(
    *, target: Path, platform: str, host_os: str, repo_root: Path
) -> set[str]:
    """Return the current owned registration identities without host interaction."""
    data = _load(target)
    expected = _manifest_stems(repo_root, platform)
    return {
        canonical_identity(
            event,
            argv,
            host_os,
            matcher=matcher,
            source_path=target,
        )
        for event, _stem, argv, matcher in _iter_owned_hooks(data, expected, platform, host_os)
    }


def write_codex_inventory(
    *,
    target: Path,
    specs: Iterable[tuple[str, Path, str, str | None]],
    inventory_path: Path,
    host_os: str,
) -> None:
    """Atomically persist the generated Codex-only expected registration set."""
    temporary: Path | None = None
    try:
        authority = _inventory_authority(target, inventory_path, for_write=True)
        spec_rows = list(specs)
        stems = {marker for marker, _script, _event, _matcher in spec_rows}
        if len(stems) != len(spec_rows):
            raise ValueError("duplicate Codex hook marker in installer specifications")
        data = _load(authority.target)
        rows = list(_iter_owned_hooks(data, stems, "codex", host_os))
        by_stem: dict[str, list[tuple[str, str, list[str], str | None]]] = {
            stem: [] for stem in stems
        }
        for row in rows:
            by_stem[row[1]].append(row)
        invalid = sorted(
            stem for stem, matches in by_stem.items() if len(matches) != 1
        )
        if invalid:
            raise ValueError(
                "Codex inventory generation requires one registration per marker: "
                + ", ".join(invalid)
            )
        hooks = []
        for marker, _script, expected_event, expected_matcher in spec_rows:
            event, _stem, argv, matcher = by_stem[marker][0]
            if (
                _event_identity(event) != _event_identity(expected_event)
                or matcher != expected_matcher
            ):
                raise ValueError(
                    f"Codex inventory registration shape mismatch: {marker}"
                )
            hooks.append(
                {
                    "stem": marker,
                    "identity": canonical_identity(
                        event,
                        argv,
                        host_os,
                        matcher=matcher,
                        source_path=authority.target,
                    ),
                }
            )
        payload = {
            "schemaVersion": 1,
            "sourcePath": _source_identity(authority.target, host_os),
            "hooks": sorted(hooks, key=lambda item: item["stem"]),
        }
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{authority.inventory.name}.",
            suffix=".tmp",
            dir=authority.inventory.parent,
        )
        temporary = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        _recheck_inventory_authority(authority, for_write=True)
        os.replace(temporary, authority.inventory)
        temporary = None
        written = _inventory_authority(
            authority.target, authority.inventory, for_write=False
        )
        _require_same_hook_target_authority(authority, written)
    except _HookHealthFailure:
        raise
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise _HookHealthFailure(
            "E_HOOK_INVENTORY_TARGET_INVALID", "inventory", str(exc)
        ) from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _load_codex_inventory(
    inventory_path: Path,
    *,
    target: Path,
    host_os: str,
) -> tuple[set[str], set[str]]:
    try:
        authority = _inventory_authority(target, inventory_path, for_write=False)
        data = _load(authority.inventory)
        if data.get("schemaVersion") != 1:
            raise ValueError("Codex hook inventory schema is unsupported")
        if data.get("sourcePath") != _source_identity(authority.target, host_os):
            raise ValueError(
                "Codex hook inventory sourcePath does not match the selected config"
            )
        hooks = data.get("hooks")
        if not isinstance(hooks, list) or not hooks:
            raise ValueError("Codex hook inventory is empty or malformed")
        stems: set[str] = set()
        identities: set[str] = set()
        for hook in hooks:
            if not isinstance(hook, dict):
                raise ValueError("Codex hook inventory entry is malformed")
            stem = hook.get("stem")
            identity = hook.get("identity")
            if not isinstance(stem, str) or not stem or not isinstance(identity, str):
                raise ValueError("Codex hook inventory entry lacks stem or identity")
            if stem in stems or identity in identities:
                raise ValueError("Codex hook inventory contains duplicate entries")
            payload = json.loads(identity)
            if not isinstance(payload, dict) or set(payload) != {
                "command",
                "event",
                "handlerType",
                "matcher",
                "sourcePath",
            }:
                raise ValueError("Codex hook inventory identity is incomplete")
            stems.add(stem)
            identities.add(identity)
        _recheck_inventory_authority(authority, for_write=False)
        return stems, identities
    except _HookHealthFailure:
        raise
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise _HookHealthFailure(
            "E_HOOK_INVENTORY_TARGET_INVALID", "inventory", str(exc)
        ) from exc


def _manifest_stems(repo_root: Path, platform: str) -> set[str]:
    manifest_path = repo_root / "scripts" / "universal_hooks_manifest.py"
    if manifest_path.is_file():
        spec = importlib.util.spec_from_file_location("universal_hooks_manifest", manifest_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"could not load hook manifest: {manifest_path}")
        manifest = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = manifest
        spec.loader.exec_module(manifest)
    else:
        raise ValueError(f"hook manifest is unavailable: {manifest_path}")

    return set(manifest.registered_hook_stems(platform))


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"registration file does not exist: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"registration root is not an object: {path}")
    return data


def _split_windows_command(command: str) -> list[str]:
    return [
        token[1:-1].replace("''", "'")
        if len(token) >= 2 and token[0] == token[-1] and token[0] in {"'", '"'}
        else token
        for token in shlex.split(command, posix=False)
    ]


def _command_argv(hook: dict[str, Any], platform: str, host_os: str) -> list[str]:
    command = hook.get("command")
    if not isinstance(command, str) or not command:
        raise ValueError("hook command is missing")
    args = hook.get("args")
    if platform == "claude":
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            raise ValueError("Claude hook args must be a string array")
        return [command, *args]
    if args is not None:
        raise ValueError("Codex hook entry unexpectedly contains args")
    return (
        _split_windows_command(command)
        if host_os == "windows"
        else shlex.split(command)
    )


def _iter_owned_hooks(
    data: dict[str, Any],
    stems: set[str],
    platform: str,
    host_os: str,
) -> Iterable[tuple[str, str, list[str], str | None]]:
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        raise ValueError("'hooks' key is not an object")
    for event, entries in hooks.items():
        if not isinstance(entries, list):
            raise ValueError(f"hooks.{event} is not an array")
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            matcher = entry.get("matcher")
            if matcher is not None and not isinstance(matcher, str):
                raise ValueError(f"hooks.{event} matcher is not a string")
            commands = entry.get("hooks")
            if not isinstance(commands, list):
                continue
            for command_hook in commands:
                if not isinstance(command_hook, dict):
                    continue
                # `_command_argv` enforces the exec shape this pack's own
                # installer writes (Claude: `command` plus a string-array
                # `args`). Third-party tools registering into the same
                # settings.json need not use that shape -- a real one on this
                # machine registers `{"command": "codegraph prompt-hook"}` with
                # no `args` at all, which is valid for the runtime and simply
                # not ours. Parsing used to run BEFORE the stem filter, so one
                # foreign entry failed the whole health check and reported the
                # operator's fully converted, working registration as broken.
                # An entry `_command_argv` cannot parse is NOT proof it was
                # never ours: a command-only entry with no `args` key -- the
                # exact shape a foreign tool is allowed to use -- also fails
                # to parse on the Claude platform even when its command
                # string names one of THIS pack's own manifest stems (e.g. a
                # mis-registered or hand-edited duplicate). Silently skipping
                # that entry would let it fire this pack's own hook a second
                # time without the duplicate check ever seeing it, because a
                # skipped entry never becomes a counted row. So an unparseable
                # entry is interrogated before it is skipped: the raw entry is
                # serialized and searched for an owned manifest stem. Naming
                # one is fatal (loud failure, naming the stem) precisely
                # because it cannot be verified as safe; naming none means it
                # cannot be ours and is skipped. This narrows what the checker
                # polices to what the pack installs -- it does not weaken any
                # check on an owned, parseable entry.
                try:
                    argv = _command_argv(command_hook, platform, host_os)
                except ValueError:
                    raw = json.dumps(command_hook)
                    named_stems = sorted(stem for stem in stems if stem in raw)
                    if named_stems:
                        raise ValueError(
                            "entry names owned hook stem(s) but could not be "
                            "parsed as this pack's exec shape: "
                            + ", ".join(named_stems)
                        )
                    continue
                joined = "\0".join(argv)
                matches = sorted(stem for stem in stems if stem in joined)
                if len(matches) == 1:
                    yield event, matches[0], argv, matcher


def _resolve_executable(value: str, host_os: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        if not candidate.is_file():
            raise ValueError(f"registered executable is missing: {candidate}")
        if host_os == "windows" and candidate.suffix.lower() != ".exe":
            raise ValueError(f"registered Windows executable is not a .exe: {candidate}")
        if host_os == "posix" and not os.access(candidate, os.X_OK):
            raise ValueError(f"registered executable is not executable: {candidate}")
        return candidate
    resolved = shutil.which(value)
    if not resolved:
        raise ValueError(f"registered wrapper executable is unavailable: {value}")
    return Path(resolved)


def _target_path(argv: list[str]) -> Path | None:
    for raw in reversed(argv[1:]):
        value = raw.strip("'\"")
        candidate = Path(value)
        if candidate.suffix.lower() in {".py", ".ps1", ".sh"}:
            return candidate
    return None


def _synthetic_envelope(event: str, stem: str, scratch_root: Path) -> str:
    transcript_path: Path | None = None
    if stem in {"check-bugfix-discipline", "check-git-push-gate"}:
        transcript_path = scratch_root / f"{stem}.jsonl"
        user_text = (
            "the login page is broken, fix it"
            if stem == "check-bugfix-discipline"
            else "push these changes"
        )
        transcript_path.write_text(
            json.dumps(
                {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": [{"type": "text", "text": user_text}],
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
    if event == "PreToolUse":
        payload = {
            "hookEventName": event,
            "tool_name": "Edit",
            "tool_input": {},
        }
        if stem == "check-git-push-gate":
            payload["tool_name"] = "Bash"
            payload["tool_input"] = {"command": "git push"}
        if stem == "check-mcp-momentum":
            payload["tool_name"] = "Bash"
            payload["tool_input"] = {"command": "rg -n 'def health_probe' src/"}
        if transcript_path is not None:
            payload["transcript_path"] = str(transcript_path)
    elif event == "Stop":
        payload = {"hookEventName": event, "last_assistant_message": "done"}
    elif event == "SessionStart":
        payload = {"hookEventName": event, "source": "startup"}
    else:
        payload = {"hookEventName": event, "prompt": "health check"}
    return json.dumps(payload)


def verify_config(
    *,
    target: Path,
    platform: str,
    host_os: str,
    repo_root: Path,
    verify_fires: bool,
    codex_trust_mode: str | None = None,
    touched_identities: set[str] | None = None,
    inventory_path: Path | None = None,
    codex_command: list[str] | None = None,
    codex_home: Path | None = None,
    query_cwd: Path | None = None,
) -> list[str]:
    data = _load(target)
    inventory_identities: set[str] | None = None
    if inventory_path is not None:
        if platform != "codex":
            raise ValueError("generated hook inventory is Codex-only")
        expected, inventory_identities = _load_codex_inventory(
            inventory_path,
            target=target,
            host_os=host_os,
        )
    else:
        expected = _manifest_stems(repo_root, platform)
    rows = list(_iter_owned_hooks(data, expected, platform, host_os))
    if inventory_identities is not None:
        actual_identities = {
            canonical_identity(
                event,
                argv,
                host_os,
                matcher=matcher,
                source_path=target,
            )
            for event, _stem, argv, matcher in rows
        }
        if actual_identities != inventory_identities:
            raise _HookHealthFailure(
                "E_HOOK_INVENTORY_TARGET_INVALID",
                "inventory",
                "Codex hook registration drifted from generated inventory",
            )
    counts: dict[str, int] = {stem: 0 for stem in expected}
    messages: list[str] = []
    with tempfile.TemporaryDirectory(prefix="orchestrarium-hook-health-") as scratch:
        scratch_root = Path(scratch)
        foreign_cwd = scratch_root / "foreign-cwd"
        foreign_cwd.mkdir()
        for event, stem, argv, _matcher in rows:
            counts[stem] += 1
            executable = _resolve_executable(argv[0], host_os)
            target_path = _target_path(argv)
            if target_path is not None:
                if not target_path.is_absolute():
                    raise ValueError(f"registered target is not absolute for {stem}: {target_path}")
                if not target_path.is_file():
                    raise ValueError(f"registered target is missing for {stem}: {target_path}")
            if verify_fires:
                hook_env: dict[str, str] | None = None
                if stem == "check-mcp-momentum":
                    synthetic_home = scratch_root / "synthetic-mcp-home"
                    synthetic_home.mkdir(exist_ok=True)
                    if platform == "claude":
                        (synthetic_home / ".agents-mode.yaml").write_text(
                            "mcpMode: force\n", encoding="utf-8"
                        )
                    hook_env = os.environ.copy()
                    hook_env["HOME"] = str(synthetic_home)
                    hook_env["USERPROFILE"] = str(synthetic_home)
                completed = subprocess.run(
                    [str(executable), *argv[1:]],
                    input=_synthetic_envelope(event, stem, scratch_root),
                    capture_output=True,
                    text=True,
                    timeout=15,
                    cwd=foreign_cwd,
                    env=hook_env,
                )
                if completed.returncode != 0:
                    raise ValueError(
                        f"{stem} failed to fire (exit {completed.returncode}): "
                        f"{completed.stderr.strip()}"
                    )
                if stem in {"check-bugfix-discipline", "check-git-push-gate"}:
                    if '"permissionDecision"' not in completed.stdout or '"deny"' not in completed.stdout:
                        raise ValueError(
                            f"{stem} fired without its expected deny payload: "
                            f"{completed.stdout.strip()}"
                        )
                if stem == "check-mcp-momentum":
                    try:
                        payload = json.loads(completed.stdout)
                        specific = payload["hookSpecificOutput"]
                    except (KeyError, TypeError, json.JSONDecodeError) as exc:
                        raise ValueError(
                            "check-mcp-momentum fired without its expected decision"
                        ) from exc
                    event_ok = specific.get("hookEventName") == "PreToolUse"
                    if platform == "claude":
                        decision_ok = (
                            specific.get("permissionDecision") == "deny"
                            and "[MCP-FORCE-1]"
                            in str(specific.get("permissionDecisionReason"))
                        )
                    else:
                        decision_ok = "mcp-momentum" in str(
                            specific.get("additionalContext")
                        )
                    if not event_ok or not decision_ok:
                        raise ValueError(
                            "check-mcp-momentum fired without its expected decision"
                        )
            messages.append(f"PASS {platform} {event} {stem}")
    missing = sorted(stem for stem, count in counts.items() if count == 0)
    duplicates = sorted(stem for stem, count in counts.items() if count > 1)
    if missing:
        raise ValueError("missing registered hooks: " + ", ".join(missing))
    if duplicates:
        raise ValueError("duplicate registered hooks: " + ", ".join(duplicates))
    if codex_trust_mode is not None:
        if platform != "codex":
            raise ValueError("Codex trust reconciliation is only valid for platform=codex")
        messages.extend(
            _reconcile_codex_trust(
                rows=rows,
                target=target,
                host_os=host_os,
                mode=codex_trust_mode,
                touched_identities=touched_identities or set(),
                codex_command=codex_command
                or resolve_codex_command(os.environ.get("CODEX_BIN")),
                codex_home=(codex_home or target.parent).expanduser().resolve(),
                query_cwd=(query_cwd or Path.cwd()).expanduser().resolve(),
            )
        )
    return messages


def _default_checks(repo_root: Path) -> list[tuple[Path, str, Path]]:
    home = Path.home()
    return [
        (home / ".claude" / "settings.json", "claude", home / ".claude" / "agents"),
        (home / ".codex" / "hooks.json", "codex", home / ".codex" / "skills" / "lead"),
    ]


def _codex_inventory_sidecar(target: Path) -> Path:
    """Locate the inventory beside the final ordinary Codex hooks target."""

    try:
        resolved_target, _link_chain, _target_identity = _resolve_hooks_target(
            target, allow_missing_ordinary=True
        )
        return resolved_target.parent / INVENTORY_NAME
    except _HookHealthFailure:
        raise
    except (OSError, ValueError) as exc:
        raise _HookHealthFailure(
            "E_HOOK_INVENTORY_TARGET_INVALID", "inventory", str(exc)
        ) from exc


def _leftover_wrappers(
    installed_root: Path,
    repo_root: Path,
    platform: str,
) -> list[Path]:
    stems = _manifest_stems(repo_root, platform)
    leftovers: list[Path] = []
    for subdir in ("scripts", "hooks"):
        for stem in sorted(stems):
            for extension in (".ps1", ".sh"):
                candidate = installed_root / subdir / f"{stem}{extension}"
                if candidate.is_file():
                    leftovers.append(candidate)
    return leftovers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", help="Explicit settings.json or hooks.json")
    parser.add_argument("--platform", choices=("claude", "codex"))
    parser.add_argument("--host-os", choices=("posix", "windows"))
    parser.add_argument("--installed-root", help="Provider root containing scripts/ and hooks/")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--verify-fires", action="store_true")
    parser.add_argument("--codex-trust-mode", choices=sorted(CODEX_TRUST_MODES))
    parser.add_argument("--inventory", help="Generated Codex hook inventory")
    parser.add_argument("--codex-command-json", help="Exact resolved Codex command prefix as JSON")
    parser.add_argument("--codex-home", help="Effective CODEX_HOME used by the selected runtime")
    parser.add_argument("--query-cwd", help="Exact cwd used for hooks/list scope resolution")
    parser.add_argument(
        "--touched-identity",
        action="append",
        default=[],
        help="Ephemeral canonical identity created or replaced by this install transaction",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()
    host_os = args.host_os or ("windows" if os.name == "nt" else "posix")
    try:
        codex_command: list[str] | None = None
        if args.codex_command_json:
            decoded_command = json.loads(args.codex_command_json)
            if (
                not isinstance(decoded_command, list)
                or not decoded_command
                or not all(isinstance(value, str) and value for value in decoded_command)
                or not Path(decoded_command[0]).is_absolute()
            ):
                raise ValueError("--codex-command-json must contain a nonempty absolute command")
            codex_command = decoded_command
        if args.target or args.platform:
            if not args.target or not args.platform:
                raise ValueError("--target and --platform must be supplied together")
            checks = [
                (
                    Path(args.target).expanduser(),
                    args.platform,
                    Path(args.installed_root).expanduser() if args.installed_root else None,
                )
            ]
        else:
            checks = _default_checks(repo_root)
        for target, platform, installed_root in checks:
            inventory_path = Path(args.inventory).expanduser() if args.inventory else None
            if platform == "codex" and args.codex_trust_mode and inventory_path is None:
                inventory_path = _codex_inventory_sidecar(target)
                if not inventory_path.is_file():
                    raise _HookHealthFailure(
                        "E_HOOK_INVENTORY_TARGET_INVALID",
                        "inventory",
                        f"installed Codex hook inventory is missing: {inventory_path}",
                    )
            for message in verify_config(
                target=target,
                platform=platform,
                host_os=host_os,
                repo_root=repo_root,
                verify_fires=args.verify_fires,
                codex_trust_mode=args.codex_trust_mode,
                touched_identities=set(args.touched_identity),
                inventory_path=inventory_path,
                codex_command=codex_command,
                codex_home=Path(args.codex_home).expanduser() if args.codex_home else None,
                query_cwd=Path(args.query_cwd).expanduser() if args.query_cwd else None,
            ):
                print(message)
            if installed_root is not None:
                for wrapper in _leftover_wrappers(installed_root, repo_root, platform):
                    print(f"WARN leftover hook wrapper: {wrapper}")
        return 0
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        subprocess.TimeoutExpired,
    ) as exc:
        failure = (
            exc
            if isinstance(exc, _HookHealthFailure)
            else _HookHealthFailure("E_HOOK_HEALTH_FAILED", "health", str(exc))
        )
        _write_failure_envelope(failure)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
