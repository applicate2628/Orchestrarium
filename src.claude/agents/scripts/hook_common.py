"""Shared helpers for Orchestrarium hook scripts."""

from __future__ import annotations

import json
import hashlib
import os
import re
import stat
import sys
from pathlib import Path
from contextlib import contextmanager
from typing import Callable, NamedTuple

# Harness-injected spans that ride inside user-role transcript entries but are
# NOT typed by the human (system reminders, async task notifications, captured
# local-command stdout). They are dense with words like "fix", "error",
# "broken", "regression" that come from governance text / tool output, so
# matching bug-trigger phrases against them causes false positives. Stripped
# before any trigger match. See last_genuine_user_message.
_INJECTED_SPAN_RE = re.compile(
    r"<system-reminder>.*?</system-reminder>"
    r"|<task-notification>.*?</task-notification>"
    r"|<local-command-stdout>.*?</local-command-stdout>",
    re.DOTALL | re.IGNORECASE,
)

NO_OBSERVED_FAILURE = "NO_OBSERVED_FAILURE"
EXPLICIT_FAILURE = "EXPLICIT_FAILURE"
AMBIGUOUS_STATUS = "AMBIGUOUS_STATUS"


class CorrelatedToolResult(NamedTuple):
    """One immutable, field-addressed result correlated to a provider call.

    ``execution_status`` records only whether a supported provider surface
    exposes an execution failure. It is not the tool's semantic verdict and
    ``NO_OBSERVED_FAILURE`` is not proof of success.
    """

    call_id: str
    output_text: str
    execution_status: str


class ModelShellCommandOccurrence(NamedTuple):
    """One provider call whose typed input contains a shell command."""

    call_id: str
    tool_name: str | None
    command_text: str


class NativeControlCall(NamedTuple):
    """A native call's correlation and input carrier, without executing it."""

    call_id: str
    tool_name: str
    input_kind: str
    input_text: str


class NativeControlResult(NamedTuple):
    """Original text-block boundaries; these bytes confer no authority."""

    call_id: str
    text_blocks: tuple[str, ...]


class NativeCommandObservation(NamedTuple):
    """Typed Core or app-server command item; never status-looking stdout."""

    item_id: str
    command: str
    cwd: str
    status: str
    exit_code: int | None
    process_id: str | None
    output: str | None
    completed: bool
    thread_id: str
    turn_id: str
    source: str
    argv: tuple[str, ...] = ()


def _native_file_uri_path(value: object) -> str | None:
    """Convert the Core PathUri file form using Python 3.10's stdlib port.

    Opaque PathUri forms and another platform's file paths are unavailable,
    never guessed into a local operation. Percent decoding happens once.
    """
    if type(value) is not str or not value or "\0" in value:
        return None
    from urllib.parse import urlsplit, unquote_to_bytes
    from urllib.request import url2pathname
    try:
        uri = urlsplit(value)
        if uri.scheme != "file" or uri.query or uri.fragment or uri.username is not None or uri.password is not None:
            return None
        if re.search(r"%(?![0-9a-fA-F]{2})", uri.path):
            return None
        if os.name != "nt" and uri.netloc not in {"", "localhost"}:
            return None
        unquote_to_bytes(uri.path).decode("utf-8", errors="strict")
        encoded_path = ("//" + uri.netloc + uri.path) if uri.netloc not in {"", "localhost"} else uri.path
        path = url2pathname(encoded_path)
        if not Path(path).is_absolute() or "\0" in path:
            return None
        if os.name != "nt" and re.match(r"^/[A-Za-z]:/", path):
            return None
        return path
    except (ValueError, OSError, UnicodeError):
        return None


def extract_native_command_observation(entry: object) -> NativeCommandObservation | None:
    """Normalize published Core JSONL and app-server notification shapes.

    Core's argument vector remains an argument vector. Model tool calls and
    arbitrary JSON tool output are never upgraded into native completion.
    """
    if not isinstance(entry, dict):
        return None
    if entry.get("type") == "event_msg":
        payload = entry.get("payload")
        if not isinstance(payload, dict) or payload.get("type") not in {"item_started", "item_completed"}:
            return None
        item = payload.get("item")
        if not isinstance(item, dict) or item.get("type") != "CommandExecution":
            return None
        argv = item.get("command")
        if not isinstance(argv, list) or not argv or any(type(word) is not str or "\0" in word for word in argv):
            return None
        if not argv[0] or type(item.get("id")) is not str or not item["id"]:
            return None
        if any(type(payload.get(key)) is not str or not payload[key] for key in ("thread_id", "turn_id")):
            return None
        if not isinstance(item.get("parsed_cmd"), list):
            return None
        cwd = _native_file_uri_path(item.get("cwd"))
        if cwd is None:
            return None
        statuses = {"in_progress": "inProgress", "completed": "completed", "failed": "failed", "declined": "declined"}
        sources = {"agent": "agent", "user_shell": "userShell", "unified_exec_startup": "unifiedExecStartup", "unified_exec_interaction": "unifiedExecInteraction"}
        status, source = statuses.get(item.get("status")), sources.get(item.get("source"))
        if status is None or source is None:
            return None
        code, process_id, output = item.get("exit_code"), item.get("process_id"), item.get("aggregated_output")
        if code is not None and type(code) is not int:
            return None
        if process_id is not None and type(process_id) is not str:
            return None
        if output is not None and type(output) is not str:
            return None
        completed = payload["type"] == "item_completed"
        if completed and type(payload.get("completed_at_ms", 0)) is not int:
            return None
        return NativeCommandObservation(
            item["id"], "", cwd, status, code, process_id, output, completed,
            payload["thread_id"], payload["turn_id"], source, tuple(argv),
        )
    if entry.get("method") not in {"item/started", "item/completed"}:
        return None
    params = entry.get("params")
    if not isinstance(params, dict):
        return None
    item = params.get("item")
    if not isinstance(item, dict) or item.get("type") != "commandExecution":
        return None
    if any(type(item.get(key)) is not str or not item[key] for key in ("id", "command", "cwd")):
        return None
    if any(type(params.get(key)) is not str or not params[key] for key in ("threadId", "turnId")):
        return None
    if item.get("status") not in {"inProgress", "completed", "failed", "declined"}:
        return None
    source = item.get("source", "agent")
    if source not in {"agent", "userShell", "unifiedExecStartup", "unifiedExecInteraction"}:
        return None
    if not isinstance(item.get("commandActions"), list):
        return None
    code, process_id, output = item.get("exitCode"), item.get("processId"), item.get("aggregatedOutput")
    if code is not None and type(code) is not int:
        return None
    if process_id is not None and type(process_id) is not str:
        return None
    if output is not None and type(output) is not str:
        return None
    completed = entry["method"] == "item/completed"
    if completed and type(params.get("completedAtMs")) is not int:
        return None
    return NativeCommandObservation(
        item["id"], item["command"], item["cwd"], item["status"], code,
        process_id, output, completed, params["threadId"], params["turnId"], source,
    )


def extract_native_control_calls(entry: object) -> tuple[NativeControlCall, ...]:
    if not isinstance(entry, dict):
        return ()
    payload = entry.get("payload")
    if isinstance(payload, dict) and payload.get("type") in {"function_call", "custom_tool_call"}:
        call_id, name = payload.get("call_id"), payload.get("name")
        key = "arguments" if payload["type"] == "function_call" else "input"
        value = payload.get(key)
        if all(isinstance(value, str) and value for value in (call_id, name)) and isinstance(value, str):
            kind = "json" if key == "arguments" else "raw"
            return (NativeControlCall(call_id, name, kind, value),)
        return ()
    if not is_assistant_message(entry):
        return ()
    message = entry.get("message")
    content = entry.get("content", message.get("content") if isinstance(message, dict) else None)
    if not isinstance(content, list):
        return ()
    result: list[NativeControlCall] = []
    for item in content:
        if not isinstance(item, dict) or item.get("type") != "tool_use":
            continue
        call_id, name, value = item.get("id"), item.get("name"), item.get("input")
        if all(isinstance(value, str) and value for value in (call_id, name)) and isinstance(value, dict):
            result.append(NativeControlCall(call_id, name, "json", json.dumps(value)))
    return tuple(result)


def extract_native_control_results(entry: object) -> tuple[NativeControlResult, ...]:
    """Project supported original result carriers, never a flattened repr."""
    if not isinstance(entry, dict):
        return ()

    def blocks(value: object) -> tuple[str, ...]:
        if isinstance(value, str):
            return (value,)
        if not isinstance(value, list):
            return ()
        return tuple(
            item["text"] for item in value
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        )

    payload = entry.get("payload")
    if isinstance(payload, dict) and payload.get("type") in {"function_call_output", "custom_tool_call_output"}:
        call_id = payload.get("call_id")
        if isinstance(call_id, str) and call_id:
            return (NativeControlResult(call_id, blocks(payload.get("output"))),)
        return ()
    if entry.get("type") == "function_call_output":
        call_id = entry.get("call_id")
        if isinstance(call_id, str) and call_id:
            return (NativeControlResult(call_id, blocks(entry.get("output"))),)
        return ()
    message = entry.get("message")
    content = entry.get("content", message.get("content") if isinstance(message, dict) else None)
    if not isinstance(content, list):
        return ()
    return tuple(
        NativeControlResult(item["tool_use_id"], blocks(item.get("content")))
        for item in content
        if isinstance(item, dict) and item.get("type") == "tool_result"
        and isinstance(item.get("tool_use_id"), str) and item["tool_use_id"]
    )


_CODEX_EXIT_STATUS_RE = re.compile(r"Exit code: ([+-]?[0-9]+)\Z")


def _codex_execution_status(output_text: str) -> str:
    """Normalize the observed Codex 0.145.0 leading shell-status adapter.

    This is observed installed/runtime behavior, not an official stable
    Codex application programming interface. Only the first logical line of
    the already stripped-and-trimmed output participates. A recognized but
    malformed prefix is ambiguous; a later status-looking line is body text.
    """
    first_line = output_text.splitlines()[0] if output_text else ""
    match = _CODEX_EXIT_STATUS_RE.fullmatch(first_line)
    if match:
        return NO_OBSERVED_FAILURE if int(match.group(1), 10) == 0 else EXPLICIT_FAILURE
    if first_line.startswith("Exit code:"):
        return AMBIGUOUS_STATUS
    return NO_OBSERVED_FAILURE


def read_stdin_utf8() -> str:
    """Read stdin as raw bytes and decode UTF-8 explicitly.

    Why this exists: on Windows with a non-UTF-8 system codepage (e.g. cp1251
    on Russian locale) `sys.stdin.read()` decodes via the system codepage,
    which mangles Cyrillic characters in the hook envelope. The hook then
    fails to detect bug-trigger or passive-polling phrases in Russian and
    silently returns 0 (allow), making the structural enforcement invisible
    to operators who use Russian in user messages. Reading raw bytes from
    `sys.stdin.buffer` and decoding UTF-8 with `errors="replace"` bypasses
    the system-codepage layer entirely. Fails open: returns empty string on
    any error.
    """
    try:
        raw = sys.stdin.buffer.read()
    except Exception:
        try:
            return sys.stdin.read()
        except Exception:
            return ""
    if isinstance(raw, bytes):
        # utf-8-sig strips a leading UTF-8 BOM if present (PowerShell can prepend
        # one when piping stdin to a native command), otherwise decodes as plain
        # UTF-8; a stray BOM would otherwise make json.loads reject the envelope
        # and the hook silently no-op on a wrapper-mediated install path.
        return raw.decode("utf-8-sig", errors="replace")
    return str(raw or "")


def parse_envelope(stdin_text: str) -> dict:
    """Decode a hook JSON envelope; malformed input fails open as empty."""
    try:
        data = json.loads(stdin_text)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


class AcquiredToolInput(NamedTuple):
    """Lossless invocation identity and supported payload facts, without policy."""

    raw_name: str | None
    operation: str | None
    targets: tuple[str, ...]
    command: str | None
    resolved: bool


_PATCH_FILE_HEADER = re.compile(r"^\*\*\* (?:Add|Update|Delete|Move) File: (.+)$")
_PATCH_MOVE_HEADER = re.compile(r"^\*\*\* Move to: (.+)$")
_DIRECT_FILE_TOOLS = frozenset({"edit", "write", "notebookedit"})
_SHELL_TOOLS = frozenset({"bash", "powershell", "shell_command", "exec_command"})


def _patch_targets(patch: str) -> tuple[str, ...] | None:
    """Recognize the existing strict frame and affected paths, not full hunks."""
    lines = patch.splitlines()
    if len(lines) < 3 or lines[0] != "*** Begin Patch" or lines[-1] != "*** End Patch":
        return None
    targets: list[str] = []
    in_file = False
    for line in lines[1:-1]:
        file_header = _PATCH_FILE_HEADER.fullmatch(line)
        move_header = _PATCH_MOVE_HEADER.fullmatch(line)
        if file_header or move_header:
            if move_header and not in_file:
                return None
            target = (file_header or move_header).group(1)
            if not target or target != target.strip():
                return None
            targets.append(target)
            in_file = True
        elif not in_file or not (line.startswith(("@@", "+", "-", " ")) or line == "*** End of File"):
            return None
    return tuple(targets) if targets else None


def normalize_tool_operation(name: object) -> str | None:
    """Recognize the declared qualified-name grammar independently of payload."""
    if not isinstance(name, str) or not name.strip():
        return None
    if any(not part or part != part.strip() for part in name.split(".")):
        return None
    operation = name.rsplit(".", 1)[-1].lower()
    return operation if operation in _DIRECT_FILE_TOOLS | _SHELL_TOOLS | {"apply_patch"} else None


def _acquire_shell_command(operation: str | None, payload: object) -> str | None:
    """Select one declared carrier; ambiguous presence never has priority."""
    if not isinstance(payload, dict):
        return None
    present = [key for key in ("cmd", "command") if key in payload]
    allowed = ("cmd", "command") if operation == "exec_command" else ("command",)
    if len(present) != 1 or present[0] not in allowed:
        return None
    command = payload[present[0]]
    return command if isinstance(command, str) and command.strip() else None


def acquire_tool_input(name: object, payload: object) -> AcquiredToolInput:
    """Acquire supported tool identity and payload without guessing on ambiguity."""
    raw_name = name if isinstance(name, str) and name.strip() else None
    if not isinstance(payload, dict):
        return AcquiredToolInput(raw_name, None, (), None, False)
    operation = normalize_tool_operation(name)
    if operation is None:
        return AcquiredToolInput(raw_name, None, (), None, False)
    if operation == "apply_patch":
        keys = [key for key in ("command", "patch", "input") if key in payload]
        if len(keys) != 1 or not isinstance(payload[keys[0]], str):
            return AcquiredToolInput(name, operation, (), None, False)
        targets = _patch_targets(payload[keys[0]])
        return AcquiredToolInput(name, operation, targets or (), None, targets is not None)
    if operation in _SHELL_TOOLS:
        command = _acquire_shell_command(operation, payload)
        if command is None:
            return AcquiredToolInput(name, operation, (), None, False)
        return AcquiredToolInput(name, operation, (), command, True)
    targets = tuple(value.strip() for key in ("file_path", "notebook_path", "path")
                    if isinstance((value := payload.get(key)), str) and value.strip())
    return AcquiredToolInput(name, operation, targets, None, bool(targets))


HISTORY_STATUS_FOUND = "found"
HISTORY_STATUS_ABSENT = "absent"
HISTORY_STATUS_UNREADABLE = "unreadable"
HISTORY_STATUS_IDENTITY_DRIFT = "identity-drift"
HISTORY_STATUS_INVALID = "invalid"
HISTORY_STATUS_LIMIT = "limit"
HISTORY_STATUS_RESOURCE_UNAVAILABLE = "resource-unavailable"
HISTORY_STATUSES = (
    HISTORY_STATUS_FOUND,
    HISTORY_STATUS_ABSENT,
    HISTORY_STATUS_UNREADABLE,
    HISTORY_STATUS_IDENTITY_DRIFT,
    HISTORY_STATUS_INVALID,
    HISTORY_STATUS_LIMIT,
    HISTORY_STATUS_RESOURCE_UNAVAILABLE,
)



class NativeHistorySourceError(OSError):
    """Selected native-source acquisition/currentness, not body execution."""


class NativeHistoryIdentity(NamedTuple):
    logical_path: str
    resolved_path: str
    namespace: tuple[tuple[str, int, int, int, str | None], ...]
    file_identity: tuple[int, int, int]


def _native_history_identity(path: Path) -> NativeHistoryIdentity:
    try:
        logical = Path(os.path.abspath(path))
        namespace = []
        for node in (*reversed(logical.parents), logical):
            observed = node.lstat()
            reparse = bool(getattr(observed, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
            link = os.readlink(node) if stat.S_ISLNK(observed.st_mode) or reparse else None
            namespace.append((str(node), observed.st_dev, observed.st_ino, stat.S_IFMT(observed.st_mode), link))
        resolved = logical.resolve(strict=True)
        observed = logical.stat()
        if not stat.S_ISREG(observed.st_mode):
            raise OSError("native history source is not a regular file")
        return NativeHistoryIdentity(str(logical), str(resolved), tuple(namespace), (observed.st_dev, observed.st_ino, stat.S_IFMT(observed.st_mode)))
    except OSError as exc:
        raise NativeHistorySourceError("native history source unavailable") from exc


class HeldNativeHistorySource(NamedTuple):
    path: Path
    stream: object
    identity: NativeHistoryIdentity

    def assert_current(self) -> None:
        try:
            observed = os.fstat(self.stream.fileno())
            descriptor = (observed.st_dev, observed.st_ino, stat.S_IFMT(observed.st_mode))
            if descriptor != self.identity.file_identity or _native_history_identity(self.path) != self.identity:
                raise OSError("native history source association changed")
        except OSError as exc:
            raise NativeHistorySourceError("native history source association changed") from exc


@contextmanager
def hold_native_history_source(transcript_path: str):
    """Own one selected source through receiving; allow same-file appends.

    The descriptor and logical/resolved namespace witness live only for this
    operation. No directory timestamps or perpetual inode promise are used.
    Existing complete-history acquisition still proves each read's bytes.
    """
    path = Path(transcript_path)
    identity = _native_history_identity(path)
    try:
        stream = path.open("rb")
    except OSError as exc:
        raise NativeHistorySourceError("native history source unavailable") from exc
    with stream:
        source = HeldNativeHistorySource(path, stream, identity)
        source.assert_current()
        yield source
        source.assert_current()


def read_transcript_history(
    transcript_path: str,
    *,
    byte_cap: int | None,
    record_cap: int | None,
    line_byte_cap: int | None,
    on_record: Callable[[dict, bytes], None] | None = None,
) -> tuple[list[dict], str]:
    """Acquire complete JSONL history, either bounded or as a finite stream.

    Bounded callers keep their historical byte, record and line limits and
    receive the decoded list. The publication reducer supplies ``on_record``
    with all three caps set to ``None``: this mode binds one initial file
    frontier, streams complete strict records to the callback without keeping
    an all-history list, then verifies a second complete digest and the same
    descriptor/path identity before reporting success. A resource failure is
    distinct from malformed content and never returns partial authority.
    """
    if not transcript_path:
        return [], HISTORY_STATUS_ABSENT
    if on_record is None:
        if (
            type(byte_cap) is not int
            or type(record_cap) is not int
            or type(line_byte_cap) is not int
            or byte_cap <= 0
            or record_cap <= 0
            or line_byte_cap <= 0
        ):
            return [], HISTORY_STATUS_LIMIT
    elif byte_cap is not None or record_cap is not None or line_byte_cap is not None:
        return [], HISTORY_STATUS_LIMIT

    tp = Path(transcript_path)
    if on_record is not None:
        try:
            if not tp.is_file():
                return [], HISTORY_STATUS_UNREADABLE
            path_before = tp.stat()
            with tp.open("rb") as stream:
                before = os.fstat(stream.fileno())
                identity_fields = ("st_dev", "st_ino", "st_mode")
                if tuple(getattr(before, name) for name in identity_fields) != tuple(
                    getattr(path_before, name) for name in identity_fields
                ):
                    return [], HISTORY_STATUS_IDENTITY_DRIFT

                frontier = before.st_size
                total_bytes = 0
                first_digest = hashlib.sha256()
                line_buffer = bytearray()
                def consume_line(raw_line: bytes) -> str | None:
                    if not raw_line.strip():
                        return None
                    try:
                        entry = json.loads(raw_line.decode("utf-8", errors="strict"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        return HISTORY_STATUS_INVALID
                    if not isinstance(entry, dict):
                        return HISTORY_STATUS_INVALID
                    on_record(entry, raw_line)
                    return None

                while total_bytes < frontier:
                    chunk = stream.read(min(1024 * 1024, frontier - total_bytes))
                    if not chunk:
                        return [], HISTORY_STATUS_IDENTITY_DRIFT
                    total_bytes += len(chunk)
                    first_digest.update(chunk)
                    line_buffer.extend(chunk)
                    while True:
                        newline = line_buffer.find(b"\n")
                        if newline < 0:
                            break
                        raw_line = bytes(line_buffer[: newline + 1])
                        del line_buffer[: newline + 1]
                        status = consume_line(raw_line)
                        if status is not None:
                            return [], status
                if line_buffer:
                    status = consume_line(bytes(line_buffer))
                    if status is not None:
                        return [], status
                if stream.read(1):
                    return [], HISTORY_STATUS_IDENTITY_DRIFT

                first_stat = os.fstat(stream.fileno())
                stream.seek(0)
                second_digest = hashlib.sha256()
                verified_bytes = 0
                while verified_bytes < frontier:
                    chunk = stream.read(min(1024 * 1024, frontier - verified_bytes))
                    if not chunk:
                        return [], HISTORY_STATUS_IDENTITY_DRIFT
                    verified_bytes += len(chunk)
                    second_digest.update(chunk)
                if stream.read(1):
                    return [], HISTORY_STATUS_IDENTITY_DRIFT
                second_stat = os.fstat(stream.fileno())
                path_after = tp.stat()
        except (MemoryError, RecursionError):
            return [], HISTORY_STATUS_RESOURCE_UNAVAILABLE
        except OSError:
            return [], HISTORY_STATUS_UNREADABLE

        stable_fields = (
            "st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns"
        )
        initial = tuple(getattr(before, name) for name in stable_fields)
        path_initial = tuple(getattr(path_before, name) for name in stable_fields)
        binding_fields = ("st_dev", "st_ino", "st_mode", "st_size")
        if (
            total_bytes != frontier
            or verified_bytes != frontier
            or initial != tuple(getattr(first_stat, name) for name in stable_fields)
            or initial != tuple(getattr(second_stat, name) for name in stable_fields)
            or path_initial
            != tuple(getattr(path_after, name) for name in stable_fields)
            or tuple(getattr(before, name) for name in binding_fields)
            != tuple(getattr(path_before, name) for name in binding_fields)
            or first_digest.digest() != second_digest.digest()
        ):
            return [], HISTORY_STATUS_IDENTITY_DRIFT
        return [], HISTORY_STATUS_FOUND

    try:
        if not tp.is_file():
            return [], HISTORY_STATUS_UNREADABLE
        if tp.stat().st_size > byte_cap:
            return [], HISTORY_STATUS_LIMIT
    except (MemoryError, RecursionError):
        return [], HISTORY_STATUS_RESOURCE_UNAVAILABLE
    except Exception:
        return [], HISTORY_STATUS_UNREADABLE

    entries: list[dict] = []
    total_bytes = 0
    try:
        with tp.open("rb") as stream:
            for raw_line in stream:
                total_bytes += len(raw_line)
                if total_bytes > byte_cap or len(raw_line) > line_byte_cap:
                    return [], HISTORY_STATUS_LIMIT
                if not raw_line.strip():
                    continue
                if len(entries) >= record_cap:
                    return [], HISTORY_STATUS_LIMIT
                try:
                    line = raw_line.decode("utf-8", errors="strict").strip()
                    entry = json.loads(line)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    return [], HISTORY_STATUS_INVALID
                if not isinstance(entry, dict):
                    return [], HISTORY_STATUS_INVALID
                entries.append(entry)
    except Exception:
        return [], HISTORY_STATUS_UNREADABLE

    return entries, HISTORY_STATUS_FOUND


def last_genuine_user_text(transcript_path: str, *, byte_cap: int) -> tuple[str, str]:
    """The CURRENT TURN boundary's own typed text -- the boundary-message
    PROJECTION of `scan_current_turn_boundary` (defined further down this
    module, after the boundary-detection helpers it delegates to; forward
    reference is safe because this function is only ever CALLED after the
    whole module has finished loading). See `scan_current_turn_boundary` for
    the full bounded-REVERSE-scan rationale, the delegation to
    `slice_current_turn` for boundary detection, and the complete status
    vocabulary in `TURN_BOUNDARY_STATUSES`.

    Returns `(text, status)`:

      text   -- the boundary entry's human-typed content when
                `status == STATUS_FOUND` (possibly "" if the message itself
                was empty, which cannot happen for a real typed message but
                is defensive); "" for every other status
      status -- one of `TURN_BOUNDARY_STATUSES`

    THIS USED TO BE its OWN independent bounded-reverse-scan loop, byte for
    byte identical to `current_turn_entries`'s except for which half of the
    boundary it kept -- see work-items/bugs/2026-07-26-two-owners-of-the-
    current-turn-boundary-in-one-module.md. Both functions now derive from
    the single scan in `scan_current_turn_boundary`, so the byte-cap
    doubling mechanics and the status vocabulary each have exactly one
    definition instead of two that merely happened to match.

    Current transcript-boundary consumers and this module's test suite rely on
    this exact signature and status vocabulary."""
    entry, _after_entries, status = scan_current_turn_boundary(transcript_path, byte_cap=byte_cap)
    if status != STATUS_FOUND:
        return "", status
    return extract_user_typed_text(entry), status


def slice_current_turn(entries: list[dict]) -> tuple[dict | None, list[dict]]:
    """Return the last GENUINE user-typed entry and the entries after it.

    Delegates to `last_genuine_user_message` so the boundary skips tool_result
    entries and harness injections (compact-summary / isMeta), matching every
    other transcript-slicing caller in this module.

    A prior version used `is_user_message` directly as the boundary predicate.
    In Claude Code a tool_result is ALSO recorded as `{"type":"user",...}`, so
    in any tool-using turn the boundary landed on the trailing tool_result
    instead of the human's real last message -- the "current turn" collapsed to
    just the entries after that tool_result, silently discarding every actual
    tool call the turn made before it. That defeated any caller trying to find
    a probe/action within "the current turn" (confirmed: the passive-polling
    Stop guard's probe-allowance never saw a real tool_result in its own test
    suite, which is exactly what masked this)."""
    result = last_genuine_user_message(entries)
    return result[0], result[2]


def extract_text(entry: object) -> str:
    """Pull human-readable text out of a transcript entry across shapes."""
    if not isinstance(entry, dict):
        return ""

    # Direct content field (string or list-of-blocks)
    content = entry.get("content")
    if content is None:
        msg = entry.get("message")
        if isinstance(msg, dict):
            content = msg.get("content")
    if content is None:
        # Codex rollout shape: the message is nested under `payload`, e.g.
        # {"type":"response_item","payload":{"type":"message","role":"user",
        #  "content":[{"type":"input_text","text":"..."}]}}.
        payload = entry.get("payload")
        if isinstance(payload, dict):
            content = payload.get("content")

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                parts.append(str(item))
                continue
            # Text block
            if "text" in item:
                parts.append(str(item["text"]))
            # Tool use: name + input
            if "name" in item:
                parts.append(str(item["name"]))
            if "input" in item:
                try:
                    parts.append(json.dumps(item["input"]))
                except Exception:
                    parts.append(str(item["input"]))
            # Tool result: content
            if "content" in item and not isinstance(item.get("content"), str):
                parts.append(extract_text({"content": item["content"]}))
            elif isinstance(item.get("content"), str):
                parts.append(item["content"])
        return "\n".join(parts)

    # Codex transcript: top-level command / output strings
    for key in ("command", "output", "stdout", "stderr", "text"):
        v = entry.get(key)
        if isinstance(v, str):
            return v

    return ""


def is_user_message(entry: dict) -> bool:
    """Detect a user message across Claude Code + Codex transcript shapes."""
    # Claude Code transcript: {"type":"user","message":{"role":"user",...}}
    if entry.get("type") == "user":
        return True
    # Bare role field
    if entry.get("role") == "user":
        return True
    # Nested message
    msg = entry.get("message")
    if isinstance(msg, dict) and msg.get("role") == "user":
        return True
    # Codex rollout shape: {"type":"response_item","payload":{"type":"message","role":"user",...}}.
    # Only a payload message with role=user counts; function_call / function_call_output
    # payloads (Codex tool I/O) have no role=="user" and are correctly excluded.
    payload = entry.get("payload")
    if isinstance(payload, dict) and payload.get("type") == "message" and payload.get("role") == "user":
        return True
    return False


def strip_injected_spans(text: str) -> str:
    """Remove harness-injected spans (system-reminder / task-notification /
    local-command-stdout) so only human-typed text remains for matching."""
    return _INJECTED_SPAN_RE.sub(" ", text or "")


def is_compact_summary(entry: object) -> bool:
    """Is this user-role entry the harness's post-compaction continuation prompt?

    Claude Code records it with `role=user` and real prose, so every text-shaped
    genuine-user test passes it — but no human typed it. The harness did, and it
    quotes the whole prior session back: file paths, error output, and an
    "Errors and fixes" section listing every defect the session touched.

    That makes it the WORST possible input to a trigger-phrase matcher, and the
    failure is self-amplifying: the more bug-fixing a session did, the more bug
    vocabulary the summary carries, so the guard is most certain to misfire on
    exactly the sessions that worked hardest. It also fires at the worst moment
    -- immediately after compaction, on every edit, until the next human message.
    Reproduced: a synthetic continuation prompt carrying only summary prose drove
    a `permissionDecision: deny` on an unrelated test edit. The live transcript
    that reproduced it carried 21 of these entries.

    Detected by the harness's own `isCompactSummary` flag rather than by matching
    the preamble's wording: the flag is structural, the wording is not ours and
    can change under us. `isMeta` covers the sibling harness-authored user entries
    for the same reason.

    Fails OPEN by design: an entry without the flag is treated as genuine. A
    missed summary costs a false positive the operator can override; a summary
    misread as human costs nothing but noise, while wrongly discarding a REAL bug
    report would silently disarm the guard.
    """
    if not isinstance(entry, dict):
        return False
    return bool(entry.get("isCompactSummary") or entry.get("isMeta"))


def extract_user_typed_text(
    entry: object, *, preserve_outer_whitespace: bool = False
) -> str:
    """The human-typed text of a user entry only.

    Excludes tool_result and tool_use blocks (those are tool I/O recorded under
    role=user in Claude Code, not anything the human typed), skips the harness's
    post-compaction continuation prompt (see `is_compact_summary`), and strips
    harness-injected spans. Returns "" for an entry that carries no genuine
    user text (e.g. a pure tool_result or a pure task-notification).

    The default trims outer whitespace. Explicit True preserves layout after
    the same selection/filtering, for consumers with syntax-sensitive input.
    """
    if type(preserve_outer_whitespace) is not bool:
        raise TypeError("preserve_outer_whitespace must be a bool")
    if not isinstance(entry, dict):
        return ""
    if is_compact_summary(entry):
        return ""
    content = entry.get("content")
    if content is None:
        msg = entry.get("message")
        if isinstance(msg, dict):
            content = msg.get("content")
    if content is None:
        payload = entry.get("payload")  # Codex rollout shape (see extract_text)
        if isinstance(payload, dict):
            content = payload.get("content")
    text = ""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                parts.append(str(item))
                continue
            if item.get("type") in ("tool_result", "tool_use"):
                continue  # tool I/O, not human-typed
            if "text" in item:
                parts.append(str(item["text"]))
        text = "\n".join(parts)
    if not text:
        # Codex transcript shape: a user entry may carry its text at the top
        # level. Only `text` is human-typed here; `command`/`output`/`stdout`/
        # `stderr` are tool I/O and must NOT be treated as a user message.
        top = entry.get("text")
        if isinstance(top, str):
            text = top
    filtered = strip_injected_spans(text)
    return filtered if preserve_outer_whitespace else filtered.strip()


def last_genuine_user_message(entries: list[dict]) -> tuple[dict | None, str, list[dict]]:
    """Most recent GENUINE user-typed message, its typed text, and the entries
    after it (the true current turn).

    Walks in reverse and skips user-role entries that carry no human-typed text
    (pure tool_result blocks, pure system-reminder / task-notification
    injections). This is what makes bug-trigger matching see the human's actual
    last message instead of the most recent tool_result — fixing both the false
    positive (a tool_result/notification full of trigger words) and the false
    negative (a real bug report buried behind many tool_result entries). Returns
    (None, "", after) when no genuine user message is in scope."""
    after: list[dict] = []
    for entry in reversed(entries):
        if is_user_message(entry):
            typed = extract_user_typed_text(entry)
            if typed:
                after.reverse()
                return entry, typed, after
        after.append(entry)
    after.reverse()
    return None, "", after


def is_assistant_message(entry: object) -> bool:
    """Detect an assistant-authored message across Claude + Codex shapes."""
    if not isinstance(entry, dict):
        return False
    if entry.get("type") == "assistant" or entry.get("role") == "assistant":
        return True
    msg = entry.get("message")
    if isinstance(msg, dict) and msg.get("role") == "assistant":
        return True
    payload = entry.get("payload")
    if isinstance(payload, dict) and payload.get("type") == "message" and payload.get("role") == "assistant":
        return True
    return False


def extract_assistant_prose(entry: object) -> str:
    """Assistant-authored PROSE text only — no tool_use blocks (and their
    inputs), no tool output. Used for diagnostic signals, never user override
    authority; edited/read file content and tool output are not assistant prose."""
    if not is_assistant_message(entry):
        return ""
    content = entry.get("content")
    if content is None:
        msg = entry.get("message")
        if isinstance(msg, dict):
            content = msg.get("content")
    if content is None:
        payload = entry.get("payload")
        if isinstance(payload, dict):
            content = payload.get("content")
    if isinstance(content, str):
        return strip_injected_spans(content).strip()
    parts: list[str] = []
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") != "tool_use" and "text" in item:
                parts.append(str(item["text"]))
    return strip_injected_spans("\n".join(parts)).strip()


def extract_model_tool_calls(entry: object) -> str:
    """The model's own tool CALLS only — Claude tool_use name+input, Codex
    `payload.function_call` name+arguments. NOT assistant prose, NOT tool
    OUTPUT (tool_result, function_call_output). Used to detect an /agents-bugfix
    INVOCATION as a discipline signal without letting broad signal words
    (`diagnostic`, `hypothesis`, ...) that merely appear inside arbitrary
    tool-call input (e.g. a file the model edits) count as discipline — only a
    narrow invocation regex is matched against this text by the caller."""
    payload = entry.get("payload") if isinstance(entry, dict) else None
    if isinstance(payload, dict) and payload.get("type") == "function_call":
        # Codex model tool call (the call, not its output).
        return strip_injected_spans(f"{payload.get('name', '')} {payload.get('arguments', '')}").strip()
    if not is_assistant_message(entry):
        return ""
    content = entry.get("content")
    if content is None:
        msg = entry.get("message")
        if isinstance(msg, dict):
            content = msg.get("content")
    parts: list[str] = []
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "tool_use":
                if "name" in item:
                    parts.append(str(item["name"]))
                if "input" in item:
                    try:
                        parts.append(json.dumps(item["input"]))
                    except Exception:
                        parts.append(str(item["input"]))
    return strip_injected_spans(" ".join(parts)).strip()


def extract_model_tool_calls_with_ids(entry: object) -> list[tuple[str, str]]:
    """Like `extract_model_tool_calls`, but returns a list of `(call_id,
    call_text)` pairs — one per distinct model tool CALL in this entry — so a
    caller can correlate a SPECIFIC invocation with its SPECIFIC result (see
    `extract_tool_outputs_with_ids`), instead of merely knowing that some call
    and some result both occurred somewhere in the turn.

    `call_id` is the Claude `tool_use` block's own `id`, or the Codex
    `function_call` payload's `call_id` — verified against real transcripts on
    this installation (a Claude tool_use block carries `id`; its answering
    tool_result carries the SAME value under `tool_use_id`. A Codex
    `function_call` payload carries `call_id`; its answering
    `function_call_output` carries the SAME value under `call_id`). A tool
    call with no id is skipped — it cannot be correlated to anything, and
    skipping (not fabricating an id) is the fail-closed direction: an
    uncorrelatable call can never open a caller's correlated-evidence gate.

    A SIBLING to `extract_model_tool_calls` — not a replacement. That function
    stays byte-unchanged for its own caller (check-bugfix-discipline.py, an
    invocation-only signal that never needed correlation). This function
    exists because joining two independent per-entry haystacks (one for all
    calls, one for all outputs, `\\n`-joined across the whole turn) lets an
    UNRELATED tool result satisfy a result check that no scan ever produced —
    e.g. a `Read` of a file that happens to quote the scanner's own clean-
    result text (this very module's test fixtures do) would satisfy an
    uncorrelated check with zero scan output at all. Demonstrated live against
    the shipped hook (adversarial gate finding, 2026-07-26): an empty-index
    scan plus an unrelated `Read` of a file containing the clean-result string
    ALLOWed under haystack-joining and must DENY under id correlation."""
    pairs: list[tuple[str, str]] = []
    if not isinstance(entry, dict):
        return pairs
    payload = entry.get("payload")
    if isinstance(payload, dict) and payload.get("type") in {"function_call", "custom_tool_call"}:
        call_id = payload.get("call_id")
        if isinstance(call_id, str) and call_id:
            arguments = payload.get("arguments", payload.get("input", ""))
            text = strip_injected_spans(f"{payload.get('name', '')} {arguments}").strip()
            pairs.append((call_id, text))
        return pairs
    if not is_assistant_message(entry):
        return pairs
    content = entry.get("content")
    if content is None:
        msg = entry.get("message")
        if isinstance(msg, dict):
            content = msg.get("content")
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "tool_use":
                continue
            call_id = item.get("id")
            if not isinstance(call_id, str) or not call_id:
                continue
            parts: list[str] = []
            if "name" in item:
                parts.append(str(item["name"]))
            if "input" in item:
                try:
                    parts.append(json.dumps(item["input"]))
                except Exception:
                    parts.append(str(item["input"]))
            pairs.append((call_id, strip_injected_spans(" ".join(parts)).strip()))
    return pairs


def extract_tool_outputs_with_ids(entry: object) -> list[CorrelatedToolResult]:
    """The correlation-half counterpart to `extract_model_tool_calls_with_ids`:
    returns immutable `CorrelatedToolResult` records for this entry's tool
    OUTPUT — Claude `tool_result` content keyed by its own `tool_use_id`, or
    Codex `payload.function_call_output` (and its Codex top-level fallback
    shape) output keyed by its own `call_id`. NOT tool CALLS, NOT assistant
    prose, NOT user text. An output with no id is skipped — uncorrelatable,
    so it can never satisfy a caller's correlated check (fail-closed).

    Claude's optional Boolean `tool_result.is_error` is official provider
    behavior: exact `True` is an explicit failure, exact `False` or absence
    means no failure was observed, and any present non-Boolean is ambiguous.
    For Codex, only the observed installed/runtime 0.145.0 leading
    `Exit code: N` wrapper line is normalized; this repository does not claim
    that prefix as an official or stable Codex contract. Output text retains
    the existing injected-span stripping plus outer-trim semantics."""
    results: list[CorrelatedToolResult] = []
    if not isinstance(entry, dict):
        return results
    payload = entry.get("payload")
    if isinstance(payload, dict) and payload.get("type") in {"function_call_output", "custom_tool_call_output"}:
        call_id = payload.get("call_id")
        if isinstance(call_id, str) and call_id:
            output_text = strip_injected_spans(str(payload.get("output", ""))).strip()
            results.append(CorrelatedToolResult(
                call_id, output_text, _codex_execution_status(output_text),
            ))
        return results
    # Codex top-level fallback shape (mirrors extract_text's own fallback).
    if entry.get("type") == "function_call_output":
        call_id = entry.get("call_id")
        if isinstance(call_id, str) and call_id:
            output_text = strip_injected_spans(str(entry.get("output", ""))).strip()
            results.append(CorrelatedToolResult(
                call_id, output_text, _codex_execution_status(output_text),
            ))
        return results

    content = entry.get("content")
    if content is None:
        msg = entry.get("message")
        if isinstance(msg, dict):
            content = msg.get("content")
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "tool_result":
                continue
            call_id = item.get("tool_use_id")
            if not isinstance(call_id, str) or not call_id:
                continue
            inner = item.get("content")
            if isinstance(inner, str):
                text = inner
            elif inner is not None:
                text = extract_text({"content": inner})
            else:
                text = ""
            output_text = strip_injected_spans(text).strip()
            if "is_error" not in item or item.get("is_error") is False:
                execution_status = NO_OBSERVED_FAILURE
            elif item.get("is_error") is True:
                execution_status = EXPLICIT_FAILURE
            else:
                execution_status = AMBIGUOUS_STATUS
            results.append(CorrelatedToolResult(call_id, output_text, execution_status))
    return results


def extract_model_shell_command_occurrences(
    entry: object,
) -> list[ModelShellCommandOccurrence]:
    """Return typed shell-command occurrences with provider tool identity.

    Like `extract_model_tool_calls_with_ids`, this returns the RAW SHELL
    COMMAND STRING for each shell-executing tool call, keyed by call id and
    retaining the actual provider tool name --
    NOT a flattened `"<tool name> <full JSON input>"` blob. A consumer that
    needs to parse the command the same way a live PreToolUse envelope's
    `tool_input["command"]` would be parsed (shlex tokenization, command-
    position / execution-vs-mention detection) cannot work from the
    flattened blob at all -- `Bash {"command": "bash x.sh", "description":
    "..."}` is not a parseable shell command, the flattening was only ever
    meant for keyword search, not structural analysis.

    Both recorded protocols use the shared strict carrier selection. Declared
    exec_command names support cmd or command, never both; other recorded names
    retain the historical command carrier. Missing/unknown names stay typed
    unsupported provenance, not an invented dialect or publication credit.
    Codex function_call arguments must be JSON text containing an object;
    Claude tool_use input is its recorded object. The actual raw name and call
    ID remain attached to each acquired occurrence.

    Ambiguous, unavailable or unsupported carriers are skipped. A call with no
    id, same as the sibling extractors, is skipped entirely
    -- fail-closed: an uncorrelatable call can never be credited as a scan
    execution by a caller keying off this function's output."""
    occurrences: list[ModelShellCommandOccurrence] = []
    if not isinstance(entry, dict):
        return occurrences
    payload = entry.get("payload")
    if isinstance(payload, dict) and payload.get("type") == "function_call":
        call_id = payload.get("call_id")
        if isinstance(call_id, str) and call_id:
            name = payload.get("name")
            raw_args = payload.get("arguments")
            command = None
            if isinstance(raw_args, str):
                try:
                    parsed = json.loads(raw_args)
                except Exception:
                    parsed = None
                command = _acquire_shell_command(normalize_tool_operation(name), parsed)
            if command:
                occurrences.append(ModelShellCommandOccurrence(
                    call_id,
                    name if isinstance(name, str) and name else None,
                    strip_injected_spans(command),
                ))
        return occurrences
    if not is_assistant_message(entry):
        return occurrences
    content = entry.get("content")
    if content is None:
        msg = entry.get("message")
        if isinstance(msg, dict):
            content = msg.get("content")
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "tool_use":
                continue
            call_id = item.get("id")
            if not isinstance(call_id, str) or not call_id:
                continue
            input_obj = item.get("input")
            name = item.get("name")
            command = _acquire_shell_command(normalize_tool_operation(name), input_obj)
            if command is not None:
                occurrences.append(ModelShellCommandOccurrence(
                    call_id,
                    name if isinstance(name, str) and name else None,
                    strip_injected_spans(command),
                ))
    return occurrences


# Status vocabulary for `scan_current_turn_boundary` and its two
# projections (`current_turn_entries`, `last_genuine_user_text`) -- defined
# ONCE here so neither projection can restate it as a second literal set
# that quietly drifts from this one (see work-items/bugs/2026-07-26-two-
# owners-of-the-current-turn-boundary-in-one-module.md). Existing callers
# that compare against the raw string ("found", "absent", ...) are
# unaffected: these constants ARE those exact strings, not a new
# representation of them.
STATUS_FOUND = "found"
STATUS_ABSENT = "absent"
STATUS_UNREADABLE = "unreadable"
STATUS_INVALID = "invalid"
STATUS_LIMIT = "limit"
STATUS_RESOURCE_UNAVAILABLE = "resource-unavailable"
STATUS_NOT_IN_WINDOW = "not-in-window"
TURN_BOUNDARY_STATUSES = (
    STATUS_FOUND,
    STATUS_ABSENT,
    STATUS_UNREADABLE,
    STATUS_INVALID,
    STATUS_LIMIT,
    STATUS_RESOURCE_UNAVAILABLE,
    STATUS_NOT_IN_WINDOW,
)
CURRENT_TURN_BYTE_CAP = 8 * 1024 * 1024


def scan_current_turn_boundary(
    transcript_path: str,
    *,
    byte_cap: int | None,
    boundary_only: bool = False,
) -> tuple[dict | None, list[dict], str]:
    """Return one bounded snapshot of the current turn.

    This is the only production I/O owner for current-turn evidence.
    `current_turn_entries` and `last_genuine_user_text` are thin projections;
    semantic boundary detection remains delegated to `slice_current_turn` and
    therefore to `last_genuine_user_message`.

    Returns `(boundary_entry, after_entries, status)`:

      boundary_entry -- the last genuine user-typed transcript entry (dict),
                         or None when status != STATUS_FOUND
      after_entries  -- entries strictly AFTER boundary_entry, in original
                         (forward) order; [] when status != STATUS_FOUND, or
                         when the boundary is the very last record in the
                         window
      status         -- one of TURN_BOUNDARY_STATUSES:
          STATUS_FOUND          -- a valid boundary is inside the snapshot
          STATUS_ABSENT         -- transcript_path is empty/None
          STATUS_UNREADABLE     -- path/open/seek/read failed
          STATUS_INVALID        -- retained complete data is invalid
          STATUS_LIMIT          -- one record spans the bounded snapshot
          STATUS_NOT_IN_WINDOW  -- valid snapshot has no genuine boundary

    The normal mode reads at most ``byte_cap`` bytes and returns the existing
    bounded current-turn slice. The publication-only ``boundary_only`` mode
    uses input-derived reads: it reverse-selects the latest genuine user,
    parses that user's complete suffix without retaining an ``after`` list,
    and seals the selected range twice against one finite file frontier. Any
    non-found result returns no partial boundary or later-entry data."""
    if not transcript_path:
        return None, [], STATUS_ABSENT
    if boundary_only:
        if byte_cap is not None:
            return None, [], STATUS_LIMIT
        return _scan_current_turn_boundary_only(transcript_path)
    if type(byte_cap) is not int or byte_cap <= 0:
        return None, [], STATUS_LIMIT
    tp = Path(transcript_path)
    try:
        if not tp.is_file():
            return None, [], STATUS_UNREADABLE
        with tp.open("rb") as stream:
            stream.seek(0, 2)
            file_size = stream.tell()
            if file_size <= byte_cap:
                stream.seek(0)
                raw = stream.read(file_size)
                payload = raw
                begins_at_record_boundary = True
            else:
                stream.seek(file_size - byte_cap)
                raw = stream.read(byte_cap)
                if len(raw) != byte_cap:
                    return None, [], STATUS_UNREADABLE
                sentinel, payload = raw[:1], raw[1:]
                begins_at_record_boundary = sentinel == b"\n"
    except (MemoryError, RecursionError):
        return None, [], STATUS_RESOURCE_UNAVAILABLE
    except Exception:
        return None, [], STATUS_UNREADABLE

    if not begins_at_record_boundary:
        first_newline = payload.find(b"\n")
        if first_newline < 0:
            return None, [], STATUS_LIMIT
        payload = payload[first_newline + 1 :]

    lines = payload.split(b"\n")
    if payload.endswith(b"\n"):
        lines.pop()

    entries: list[dict] = []
    for raw_line in lines:
        if not raw_line.strip():
            continue
        try:
            line = raw_line.decode("utf-8", errors="strict")
            entry = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None, [], STATUS_INVALID
        if not isinstance(entry, dict):
            return None, [], STATUS_INVALID
        entries.append(entry)

    boundary_entry, after_entries = slice_current_turn(entries)
    if boundary_entry is None:
        return None, [], STATUS_NOT_IN_WINDOW
    return boundary_entry, after_entries, STATUS_FOUND


def _scan_current_turn_boundary_only(
    transcript_path: str,
) -> tuple[dict | None, list[dict], str]:
    """Select and seal only the current-user suffix for publication checks.

    The reverse pass stops at the latest genuine user record and never parses
    the older prefix. The subsequent forward pass binds that selected record
    to the complete suffix before the independent digest pass. A nonzero
    boundary is framed by the LF immediately before it; that byte is captured
    during reverse selection and re-read before each seal.
    """
    try:
        tp = Path(transcript_path)
        if not tp.is_file():
            return None, [], STATUS_UNREADABLE
        path_before = tp.stat()
        with tp.open("rb") as stream:
            before = os.fstat(stream.fileno())
            identity_fields = ("st_dev", "st_ino", "st_mode")
            if tuple(getattr(before, name) for name in identity_fields) != tuple(
                getattr(path_before, name) for name in identity_fields
            ) or not stat.S_ISREG(before.st_mode):
                return None, [], STATUS_UNREADABLE

            frontier = before.st_size
            cursor = frontier
            later_chunks: list[bytes] = []
            boundary_entry: dict | None = None
            boundary_offset: int | None = None
            boundary_record_length: int | None = None
            boundary_record_digest: bytes | None = None
            captured_predecessor: bytes | None = None

            def parse_record(raw_record: bytes) -> tuple[dict | None, str | None]:
                if not raw_record.strip():
                    return None, None
                try:
                    entry = json.loads(raw_record.decode("utf-8", errors="strict"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    return None, STATUS_INVALID
                if not isinstance(entry, dict):
                    return None, STATUS_INVALID
                return entry, None

            while cursor > 0 and boundary_entry is None:
                chunk_start = max(0, cursor - 1024 * 1024)
                stream.seek(chunk_start)
                chunk = stream.read(cursor - chunk_start)
                if len(chunk) != cursor - chunk_start:
                    return None, [], STATUS_UNREADABLE
                end = len(chunk)
                while end > 0:
                    separator = chunk.rfind(b"\n", 0, end)
                    if separator < 0:
                        if end:
                            later_chunks.append(chunk[:end])
                        cursor = chunk_start
                        break
                    raw_record = chunk[separator + 1 : end] + b"".join(
                        reversed(later_chunks)
                    )
                    record_start = chunk_start + separator + 1
                    later_chunks.clear()
                    entry, invalid = parse_record(raw_record)
                    if invalid is not None:
                        return None, [], invalid
                    if (
                        entry is not None
                        and is_user_message(entry)
                        and extract_user_typed_text(entry)
                    ):
                        boundary_entry = entry
                        boundary_offset = record_start
                        boundary_record_length = len(raw_record)
                        boundary_record_digest = hashlib.sha256(raw_record).digest()
                        captured_predecessor = b"\n" if record_start > 0 else None
                        break
                    end = separator
                    cursor = chunk_start + separator

            if boundary_entry is None and later_chunks:
                raw_record = b"".join(reversed(later_chunks))
                entry, invalid = parse_record(raw_record)
                if invalid is not None:
                    return None, [], invalid
                if (
                    entry is not None
                    and is_user_message(entry)
                    and extract_user_typed_text(entry)
                ):
                    boundary_entry = entry
                    boundary_offset = 0
                    boundary_record_length = len(raw_record)
                    boundary_record_digest = hashlib.sha256(raw_record).digest()
                    captured_predecessor = None

            if boundary_entry is None or boundary_offset is None:
                return None, [], STATUS_NOT_IN_WINDOW

            after_selection = os.fstat(stream.fileno())
            path_after_selection = tp.stat()
            stable_fields = (
                "st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns"
            )
            initial = tuple(getattr(before, name) for name in stable_fields)
            path_initial = tuple(getattr(path_before, name) for name in stable_fields)
            binding_fields = ("st_dev", "st_ino", "st_mode", "st_size")
            if (
                initial != tuple(getattr(after_selection, name) for name in stable_fields)
                or path_initial
                != tuple(getattr(path_after_selection, name) for name in stable_fields)
                or tuple(getattr(before, name) for name in binding_fields)
                != tuple(getattr(path_before, name) for name in binding_fields)
            ):
                return None, [], STATUS_UNREADABLE

            first_digest = hashlib.sha256()
            if captured_predecessor is not None:
                stream.seek(boundary_offset - 1)
                predecessor = stream.read(1)
                if predecessor != captured_predecessor:
                    return None, [], STATUS_INVALID
                first_digest.update(predecessor)
            else:
                stream.seek(0)

            first_bytes = bytearray()
            first_total = boundary_offset
            record_start = boundary_offset
            latest_user_offset: int | None = None
            latest_user_entry: dict | None = None

            def accept_forward_record(raw_record: bytes, start: int) -> str | None:
                nonlocal latest_user_offset, latest_user_entry
                if not raw_record.strip():
                    return None
                if start == boundary_offset and (
                    len(raw_record) != boundary_record_length
                    or hashlib.sha256(raw_record).digest() != boundary_record_digest
                ):
                    return STATUS_INVALID
                try:
                    entry = json.loads(raw_record.decode("utf-8", errors="strict"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    return STATUS_INVALID
                if not isinstance(entry, dict):
                    return STATUS_INVALID
                if is_user_message(entry) and extract_user_typed_text(entry):
                    latest_user_offset, latest_user_entry = start, entry
                return None

            while first_total < frontier:
                chunk = stream.read(min(1024 * 1024, frontier - first_total))
                if not chunk:
                    return None, [], STATUS_UNREADABLE
                first_total += len(chunk)
                first_digest.update(chunk)
                first_bytes.extend(chunk)
                while True:
                    newline = first_bytes.find(b"\n")
                    if newline < 0:
                        break
                    raw_record = bytes(first_bytes[:newline])
                    del first_bytes[: newline + 1]
                    status = accept_forward_record(raw_record, record_start)
                    if status is not None:
                        return None, [], status
                    record_start += newline + 1
            if first_bytes:
                status = accept_forward_record(bytes(first_bytes), record_start)
                if status is not None:
                    return None, [], status
            if latest_user_offset != boundary_offset or latest_user_entry != boundary_entry:
                return None, [], STATUS_INVALID
            if stream.read(1):
                return None, [], STATUS_UNREADABLE
            first_stat = os.fstat(stream.fileno())
            path_after_first = tp.stat()
            if (
                initial != tuple(getattr(first_stat, name) for name in stable_fields)
                or path_initial
                != tuple(getattr(path_after_first, name) for name in stable_fields)
                or tuple(getattr(before, name) for name in binding_fields)
                != tuple(getattr(path_before, name) for name in binding_fields)
            ):
                return None, [], STATUS_UNREADABLE

            second_digest = hashlib.sha256()
            if captured_predecessor is not None:
                stream.seek(boundary_offset - 1)
                predecessor = stream.read(1)
                if predecessor != captured_predecessor:
                    return None, [], STATUS_INVALID
                second_digest.update(predecessor)
            else:
                stream.seek(0)
            second_total = boundary_offset
            while second_total < frontier:
                chunk = stream.read(min(1024 * 1024, frontier - second_total))
                if not chunk:
                    return None, [], STATUS_UNREADABLE
                second_total += len(chunk)
                second_digest.update(chunk)
            if stream.read(1):
                return None, [], STATUS_UNREADABLE
            second_stat = os.fstat(stream.fileno())
            path_after_second = tp.stat()
            if (
                initial != tuple(getattr(second_stat, name) for name in stable_fields)
                or path_initial
                != tuple(getattr(path_after_second, name) for name in stable_fields)
                or tuple(getattr(before, name) for name in binding_fields)
                != tuple(getattr(path_before, name) for name in binding_fields)
                or first_total != frontier
                or second_total != frontier
                or first_digest.digest() != second_digest.digest()
            ):
                return None, [], STATUS_INVALID

            return boundary_entry, [], STATUS_FOUND
    except (MemoryError, RecursionError):
        return None, [], STATUS_RESOURCE_UNAVAILABLE
    except OSError:
        return None, [], STATUS_UNREADABLE


def current_turn_entries(transcript_path: str, *, byte_cap: int) -> tuple[list[dict], str]:
    """The CURRENT TURN's entries -- the after-boundary PROJECTION of
    `scan_current_turn_boundary` (see that function for the full bounded-
    REVERSE-scan rationale, the delegation to `slice_current_turn` for
    boundary detection, and the complete status vocabulary in
    `TURN_BOUNDARY_STATUSES`).

    Returns `(entries, status)`:

      entries -- every parsed record strictly AFTER the boundary, in
                 original (forward) order, when `status == STATUS_FOUND`
                 (possibly [] if the boundary is the very last record in the
                 window); [] for every other status
      status  -- one of `TURN_BOUNDARY_STATUSES`

    Existing callers relying on this exact signature and status vocabulary:
    `dispatch_sentinels.py` (the round-depth observer) and this module's own
    test suite."""
    _boundary_entry, after_entries, status = scan_current_turn_boundary(transcript_path, byte_cap=byte_cap)
    return after_entries, status


def emit_advisory(envelope: object, message: str, *, default_event: str = "PreToolUse") -> None:
    """Deliver a warn-only advisory to the MODEL, never the operator terminal.

    Writes ``{"hookSpecificOutput": {"hookEventName": <event>, "additionalContext":
    message}}`` as one line of JSON to stdout and returns (the caller still exits
    0 itself -- this function does not exit the process). This REPLACES the
    stderr-plus-exit-1 delivery every warn-only PreToolUse audit in this pack used
    before it, which was measured to reach NOBODY: on Claude Code 2.1.220 a
    non-blocking exit-1's stderr lands in the transcript record but is
    model-invisible, and on Codex CLI 0.145.0 the non-2-exit branch never even
    copies stderr (the operator console shows a bare "PreToolUse Failed" label).
    `hookSpecificOutput.additionalContext` on `PreToolUse`, by contrast, was
    measured to reach the model on BOTH runtimes when emitted on stdout with exit
    0. See work-items/bugs/2026-07-26-mcp-reminder-uses-the-once-per-session-form-
    its-sibling-calls-broken.md for the full falsification-controlled measurement.

    THE EVENT NAME TRAP (why `default_event` exists but is a FALLBACK, never a
    hardcoded override): Claude Code silently discards the ENTIRE
    `hookSpecificOutput` object when `hookEventName` does not match the event that
    ACTUALLY fired -- measured, with the runtime emitting "Hook returned incorrect
    event name: expected 'PreToolUse' but got 'PostToolUse'". `envelope`'s own
    `hook_event_name` field is therefore read FIRST and used verbatim whenever
    present; `default_event` is used ONLY when the envelope carries no
    `hook_event_name` at all (e.g. a hand-built test envelope that omits it).
    Every current caller of this helper is registered exclusively on `PreToolUse`,
    which is why that is the documented default -- it is not a license for a
    caller to skip reading the envelope's own field.

    Exit-0 framing bonus: this also drops the misleading `hook_non_blocking_error`
    label a warn-only audit's exit-1 form carried on the runtime's own transcript
    -- a warn-only audit allowing its own tool call should never present as an
    error. Fails open: any exception here is swallowed, matching the fail-open
    posture of every caller.
    """
    event = envelope.get("hook_event_name") if isinstance(envelope, dict) else None
    if not isinstance(event, str) or not event:
        event = default_event
    payload = {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": message,
        }
    }
    try:
        print(json.dumps(payload, ensure_ascii=True))
    except Exception:
        pass


def emit_session_start_context(message: str) -> None:
    """Emit a SessionStart `hookSpecificOutput` context block as compact,
    literal-UTF-8 JSON -- the byte-parity contract this pack's Python
    SessionStart reminders (mcp-usage-reminder.py, agents-mode-reminder.py)
    were historically checked against their hand-authored shell siblings:
    ``{"hookSpecificOutput":{"hookEventName":"SessionStart",
    "additionalContext":"..."}}``, no separator whitespace, and a literal
    (non-escaped) UTF-8 em-dash rather than `\\u2014` -- verified byte-for-byte
    against a captured legacy reminder-wrapper run on 2026-07-27 (the shell
    heredoc form matches once its own CRLF-vs-LF line ending, which is a
    platform artifact of `[Console]::Out.WriteLine` vs a bash heredoc, not a
    content difference, is set aside).

    DELIBERATELY NOT `emit_advisory` above: that function hardcodes
    `ensure_ascii=True` and default `json.dumps` spacing for its own PreToolUse
    audit callers (a different, already-shipped contract this function must
    not silently change), and always reads `envelope.get("hook_event_name")`
    -- every caller of THIS function is a SessionStart reminder with no such
    envelope-declared variability, so the event name is hardcoded here,
    matching every SessionStart reminder's own historical shell source (none of
    which read `hook_event_name` from an envelope either).

    UTF-8 SAFETY: reconfigures stdout to UTF-8 before writing, mirroring the
    `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8` line every
    legacy SessionStart reminder set at its own top. Without this, a
    non-UTF-8 system codepage (e.g. `cp437`, which cannot encode U+2014) can
    raise `UnicodeEncodeError` on a literal em-dash and silently drop the
    whole reminder -- confirmed empirically: `'\\u2014'.encode('cp437')`
    raises, `'\\u2014'.encode('cp1251')` does not, so this is a real,
    codepage-dependent failure mode, not a theoretical one. `reconfigure` is
    itself wrapped in its own `try`/`except` (it is a Python 3.7+
    `TextIOWrapper` method; absent or failing, the write is attempted anyway
    under whatever encoding stdout already had).

    Fails open: any exception here (including the write itself) is
    swallowed; the caller still exits 0."""
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": message,
        }
    }
    try:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    except Exception:
        pass
