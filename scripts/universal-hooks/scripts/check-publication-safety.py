#!/usr/bin/env python3
"""Fail-closed publication-safety scanner for tracked, range, and path inputs."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from enum import Enum
import hashlib
import importlib.util
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import quote

_GIT_EXECUTABLE = globals().get("__injected_git_executable__", "git")


_POSIX_PROCESS_GROUP_CONTRACT_V1 = "orchestrarium.posix-process-group.module.v1"


def _valid_posix_process_group_module(module: object) -> bool:
    try:
        marker = getattr(module, "POSIX_PROCESS_GROUP_MODULE_CONTRACT_V1")
        contract = getattr(module, "posix_process_group_module_contract_v1")
        owner_type = getattr(module, "PosixProcessGroupOwnerV1")
        error_type = getattr(module, "PosixProcessGroupError")
        returned = contract()
    except BaseException:
        return False
    return (
        marker == _POSIX_PROCESS_GROUP_CONTRACT_V1
        and returned == (marker, owner_type, error_type)
        and isinstance(owner_type, type)
        and isinstance(error_type, type)
        and issubclass(error_type, RuntimeError)
    )


def _load_posix_process_group_module():
    module_name = "_orchestrarium_posix_process_group_v1"
    injected = globals().get("__injected_posix_process_group_module__")
    if injected is not None:
        if (
            getattr(injected, "__name__", None) != module_name
            or getattr(injected, "__file__", None)
            != "<closure>/process_supervision/posix_process_group.py"
            or sys.modules.get(module_name) is not injected
            or tuple(getattr(injected, "__all__", ()))
            != (
                "PosixProcessGroupClosureV1",
                "PosixProcessGroupError",
                "PosixProcessGroupOwnerV1",
            )
            or not _valid_posix_process_group_module(injected)
        ):
            raise RuntimeError("POSIX process-group injected contract mismatch")
        return injected
    script = Path(__file__).resolve()
    candidates = [
        script.parent / "process_supervision" / "posix_process_group.py"
    ]
    if (
        script.parent.name == "scripts"
        and script.parent.parent.name == "universal-hooks"
    ):
        candidates.append(
            script.parents[2]
            / "process_supervision"
            / "posix_process_group.py"
        )
    elif (
        script.parents[0].name == "scripts"
        and script.parents[1].name == "lead"
        and script.parents[2].name == "skills"
        and script.parents[3].name == "src.codex"
    ):
        candidates.append(
            script.parents[4]
            / "scripts"
            / "process_supervision"
            / "posix_process_group.py"
        )
    elif (
        script.parents[0].name == "scripts"
        and script.parents[1].name == "agents"
        and script.parents[2].name == "src.claude"
    ):
        candidates.append(
            script.parents[3]
            / "scripts"
            / "process_supervision"
            / "posix_process_group.py"
        )
    available = tuple(path for path in candidates if path.is_file())
    if len(available) != 1:
        raise RuntimeError("POSIX process-group helper unavailable or ambiguous")
    existing = sys.modules.get(module_name)
    if existing is not None:
        if not _valid_posix_process_group_module(existing):
            raise RuntimeError("POSIX process-group helper identity mismatch")
        return existing
    spec = importlib.util.spec_from_file_location(module_name, available[0])
    if spec is None or spec.loader is None:
        raise RuntimeError("POSIX process-group helper unavailable or ambiguous")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    if not _valid_posix_process_group_module(module):
        sys.modules.pop(module_name, None)
        raise RuntimeError("POSIX process-group helper identity mismatch")
    return module


_POSIX_PROCESS_GROUP = _load_posix_process_group_module()
PosixProcessGroupError = _POSIX_PROCESS_GROUP.PosixProcessGroupError
PosixProcessGroupOwnerV1 = _POSIX_PROCESS_GROUP.PosixProcessGroupOwnerV1


_SCANNER_EXEMPT_PATHS = frozenset({
    "scripts/universal-hooks/scripts/check-publication-safety.py",
    "src.codex/skills/lead/scripts/check-publication-safety.py",
    "src.claude/agents/scripts/check-publication-safety.py",
})
_SIMPLE_PATTERNS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    re.compile(r"ANTHROPIC_[A-Z_]*(?:KEY|TOKEN)[^A-Za-z0-9_]?\s*[:=]"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"BEGIN RSA PRIVATE KEY"),
    re.compile(r"BEGIN OPENSSH PRIVATE KEY"),
    re.compile(r"BEGIN PRIVATE KEY"),
    re.compile(r"private_key"),
    re.compile(r"secret_key"),
    re.compile(r"/private/var/folders/"),
    re.compile(r"/var/folders/"),
    re.compile(r"^Human:\s*"),
    re.compile(r"^Assistant:\s*"),
    re.compile(r"^\$\s+"),
    re.compile(r"^>>>\s+"),
    re.compile(r"\[[0-9]{2}:[0-9]{2}:[0-9]{2}\]"),
)
_VALUE = r"[A-Za-z0-9_./+=-]"
_DIGIT_SHAPE = rf"(?:{_VALUE}{{5,}}[0-9]{_VALUE}*|{_VALUE}*[0-9]{_VALUE}{{5,}})"
_QUOTED = rf"""["'`!@#$%^&*?|](?:{_VALUE}{{12,}}|{_DIGIT_SHAPE})["'`!@#$%^&*?|]"""
_BARE = rf"(?:[A-Za-z0-9_+/=-]{{5,}}[0-9][A-Za-z0-9_+/=-]*|[A-Za-z0-9_+/=-]*[0-9][A-Za-z0-9_+/=-]{{5,}})"
_KEYWORDS = (
    ("password", r"password", "Password", "PASSWORD"),
    ("secret", r"secret", "Secret", "SECRET"),
    ("token", r"token", "Token", "TOKEN"),
    ("api-key", r"api[_-]?key", "ApiKey", "APIKEY"),
)
_VALUE_RULES = tuple(
    (
        family,
        re.compile(
            rf"(?:(?<![A-Za-z])(?i:{keyword})|(?<=[a-z]){title}|"
            rf"(?<=[A-Z]){title}|(?<=[A-Za-z]){upper})"
            rf"\s*[:=]\s*(?:{_QUOTED}|{_BARE})",
        ),
    )
    for family, keyword, title, upper in _KEYWORDS
)
_VALUE_PATTERNS = tuple(pattern for _family, pattern in _VALUE_RULES)
_SCANNER_REGEX_CATALOG_LINE = re.compile(
    r"""re\.compile\([rubfRUBF]*(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')\),?"""
)

_MAX_COMMITS = 10_000
_MAX_OBJECTS = 100_000
_MAX_BLOBS = 50_000
_MAX_SUBJECTS = 1_000_000
_MAX_BLOB_PATHS = 50_000
_MAX_PATH_BYTES = 4_096
_MAX_MESSAGE_BYTES = 1_048_576
_MAX_AGGREGATE_MESSAGE_BYTES = 16_777_216
_MAX_COMMIT_TREE_BYTES = 1_048_576
_MAX_TREE_CACHE_BYTES = 64 * 1_048_576
_MAX_BLOB_BYTES = 64 * 1_048_576
_MAX_AGGREGATE_BLOB_BYTES = 512 * 1_048_576
_MAX_LINE_BYTES = 8 * 1_048_576
_MAX_PARENT_GRAPH_BYTES = 16 * 1_048_576
_MAX_FINDINGS = 32
_READ_CHUNK_BYTES = 64 * 1_024
_SCAN_DEADLINE_SECONDS = 240.0
_MAX_TREE_VISITS = _MAX_SUBJECTS
_MAX_TREE_FRONTIER = _MAX_OBJECTS
_MAX_TREE_CACHE_ENTRIES = _MAX_OBJECTS
_MAX_REMOTE_REFS = 256
_RECEIPT_DOMAIN = b"publication-safety-range-receipt-v3"
_OBJECT_REQUEST_TIMEOUT_SECONDS = 5.0
OBJECT_REAP_ATTEMPT_SECONDS = 3.0
_PROCESS_TREE_CLEANUP_SECONDS = 3.0
OBJECT_REAP_MAX_ATTEMPTS = 2
_SCANNER_REFUSAL_IDS = frozenset({
    "PS-MSG-RANGE",
    "PS-MSG-READ",
    "PS-MSG-SPAWN",
    "PS-MSG-READ-TIMEOUT",
    "PS-MSG-REAP",
    "PS-MSG-FRAME",
    "PS-MSG-DECODE",
    "PS-MSG-LIMIT",
    "PS-MSG-COVERAGE",
    "PS-MSG-TIP-CHANGED",
})
_REFUSAL_PHASES = {
    "PS-MSG-RANGE": "selection",
    "PS-MSG-READ": "reader",
    "PS-MSG-SPAWN": "reader",
    "PS-MSG-READ-TIMEOUT": "reader",
    "PS-MSG-REAP": "cleanup",
    "PS-MSG-FRAME": "frame",
    "PS-MSG-DECODE": "decode",
    "PS-MSG-LIMIT": "limit",
    "PS-MSG-COVERAGE": "coverage",
    "PS-MSG-TIP-CHANGED": "binding",
    "PS-INPUT-REFUSAL": "input",
}


@dataclass(frozen=True)
class GitObjectFormat:
    name: str
    hex_length: int
    raw_length: int
    oid_re: re.Pattern[str]

    def matches(self, value: str) -> bool:
        return self.oid_re.fullmatch(value) is not None

    def list_byte_cap(self, count_cap: int) -> int:
        return count_cap * (self.hex_length + 1)


_SHA1_OBJECT_FORMAT = GitObjectFormat(
    "sha1", 40, 20, re.compile(r"[0-9a-f]{40}")
)
_SHA256_OBJECT_FORMAT = GitObjectFormat(
    "sha256", 64, 32, re.compile(r"[0-9a-f]{64}")
)
_SUPPORTED_OBJECT_FORMATS = {
    value.name: value for value in (_SHA1_OBJECT_FORMAT, _SHA256_OBJECT_FORMAT)
}


@dataclass(frozen=True)
class RangeRequest:
    remote: str
    destination: str
    source: str


@dataclass(frozen=True)
class RemoteRefTip:
    refname: bytes
    oid: str
    peeled_oid: str | None = None


@dataclass(frozen=True)
class RangeSelection:
    remote: str
    destination: str
    source: str
    tip: str
    expected_oids: tuple[str, ...]
    object_oids: tuple[str, ...] = ()
    object_format: GitObjectFormat = _SHA1_OBJECT_FORMAT
    destination_oid: str | None = None
    expected_parents: tuple[tuple[str, tuple[str, ...]], ...] = ()


@dataclass(frozen=True)
class ScanSubject:
    kind: str
    locator: str
    raw: bytes


@dataclass(frozen=True)
class Finding:
    failure_id: str
    subject_kind: str
    locator: str
    line: int
    detector_class: str


@dataclass(frozen=True)
class Refusal:
    failure_id: str
    phase: str
    reason: str


def _refusal(failure_id: str, reason: str, *, phase: str | None = None) -> Refusal:
    return Refusal(failure_id, phase or _REFUSAL_PHASES.get(failure_id, "input"), reason)


@dataclass(frozen=True)
class ObjectReadSuccess:
    requested_oid: str
    returned_oid: str
    object_type: str
    raw: bytes


@dataclass(frozen=True)
class ObjectClassification:
    requested_name: str
    returned_oid: str | None
    object_type: str | None


@dataclass(frozen=True)
class CoverageProof:
    expected_oids: tuple[str, ...]
    requested_oids: tuple[str, ...]
    acquired_oids: tuple[str, ...]
    scanned_message_oids: tuple[str, ...]
    expected_counter: tuple[tuple[str, int], ...]
    requested_counter: tuple[tuple[str, int], ...]
    acquired_counter: tuple[tuple[str, int], ...]
    scanned_counter: tuple[tuple[str, int], ...]
    expected_count: int
    requested_count: int
    acquired_count: int
    scanned_count: int
    coverage_digest: str


class CoverageEvent(str, Enum):
    REQUESTED = "requested"
    ACQUIRED = "acquired"
    SCANNED = "scanned"


class CoverageRecorder:
    """Single live owner of object-message multiplicity evidence."""

    def __init__(
        self,
        expected_oids: Iterable[str],
        observer: Callable[[CoverageEvent, str], None] | None = None,
        fault_port: "CoverageFaultPort | None" = None,
    ) -> None:
        self.expected_oids = tuple(expected_oids)
        self._events: dict[CoverageEvent, list[str]] = {
            event: [] for event in CoverageEvent
        }
        self._observer = observer
        self._fault_port = fault_port

    def record(self, event: CoverageEvent, oid: str) -> None:
        rows = ((event, oid),) if self._fault_port is None else self._fault_port.transform(event, oid)
        for observed_event, observed_oid in rows:
            self._events[observed_event].append(observed_oid)
            if self._observer is not None:
                self._observer(observed_event, observed_oid)

    def proof(self) -> CoverageProof | Refusal:
        return _build_coverage_proof(
            self.expected_oids,
            self._events[CoverageEvent.REQUESTED],
            self._events[CoverageEvent.ACQUIRED],
            self._events[CoverageEvent.SCANNED],
        )


class ReaderState(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    FINALIZING = "finalizing"
    REAP_PENDING = "reap-pending"
    REAPED = "reaped"
    SPAWN_FAILED = "spawn-failed"


@dataclass(frozen=True)
class CoverageFaultPort:
    """Test-only event transformer; production composition never supplies one."""

    transform_event: Callable[[CoverageEvent, str], Iterable[tuple[CoverageEvent, str]]]

    def transform(self, event: CoverageEvent, oid: str) -> tuple[tuple[CoverageEvent, str], ...]:
        return tuple(self.transform_event(event, oid))


@dataclass(frozen=True)
class TransportObservation:
    ownership: str
    terminal_fact: str
    observed: bool
    failure_phase: str | None
    observed_at_monotonic_tick: float


@dataclass(frozen=True)
class ChildObservation:
    identity: str
    return_code: int | None
    terminal_observed: bool
    observed_at_monotonic_tick: float


@dataclass(frozen=True)
class FinalizerObservation:
    task_identity: str
    completion_observed: bool
    cancelled: bool
    exception_observed: bool
    observed_at_monotonic_tick: float


@dataclass(frozen=True)
class ReaderReapCertificate:
    session_id: str
    attempts_used: int
    owned_child_identity: str
    owned_finalizer_identity: str
    child: ChildObservation
    stdin: TransportObservation
    stdout: TransportObservation
    finalizer: FinalizerObservation
    cleanup_errors: tuple[str, ...]
    verified_at_monotonic_tick: float
    terminal_state: ReaderState

    @property
    def returncode(self) -> int | None:
        return self.child.return_code

    @property
    def complete(self) -> bool:
        participant_ticks = (
            self.child.observed_at_monotonic_tick,
            self.stdin.observed_at_monotonic_tick,
            self.stdout.observed_at_monotonic_tick,
            self.finalizer.observed_at_monotonic_tick,
        )
        return (
            self.terminal_state is ReaderState.REAPED
            and 1 <= self.attempts_used <= OBJECT_REAP_MAX_ATTEMPTS
            and self.child.identity == self.owned_child_identity
            and self.child.return_code is not None
            and self.child.terminal_observed
            and self.stdin.ownership == "owned"
            and self.stdin.terminal_fact == "input-closed"
            and self.stdin.observed
            and self.stdout.ownership == "owned"
            and self.stdout.terminal_fact == "output-eof"
            and self.stdout.observed
            and self.finalizer.task_identity == self.owned_finalizer_identity
            and self.finalizer.completion_observed
            and not self.finalizer.cancelled
            and not self.finalizer.exception_observed
            and not self.cleanup_errors
            and self.verified_at_monotonic_tick > max(participant_ticks)
        )


ReapCertificate = ReaderReapCertificate


@dataclass(frozen=True)
class DecodedMessage:
    text: str
    raw_size: int


@dataclass(frozen=True)
class CommitRecord:
    root_tree: str
    parents: tuple[str, ...]
    message: DecodedMessage


@dataclass(frozen=True)
class TreeEntry:
    kind: str
    name: bytes
    oid: str


@dataclass(frozen=True)
class RangeReceiptV3:
    commits: int
    commit_set: str
    objects: int
    object_set: str
    blobs: int
    blob_set: str
    blob_bytes: int
    text: int
    binary: int
    subjects: int
    subject_set: str
    paths: int
    path_set: str
    remote: str
    destination: str
    source: str
    tip: str


@dataclass(frozen=True)
class HistoryProof:
    commit_ids: tuple[str, ...]
    object_ids: tuple[str, ...]
    blob_ids: tuple[str, ...]
    blob_bytes: int
    text_blobs: int
    binary_blobs: int
    subjects: tuple[tuple[str, bytes, str], ...]
    paths: tuple[tuple[str, bytes], ...]
    commit_set: str
    object_set: str
    blob_set: str
    subject_set: str
    path_set: str


@dataclass(frozen=True)
class ScanOutcome:
    kind: str
    mode: str
    file_count: int = 0
    findings: tuple[Finding, ...] = ()
    refusal: Refusal | None = None
    selection: RangeSelection | None = None
    coverage: CoverageProof | None = None
    reap_certificate: ReaderReapCertificate | None = None
    history: HistoryProof | None = None


def _run_git(
    args: list[str],
    *,
    text: bool = False,
    timeout: float | None = None,
    owned: bool = False,
) -> subprocess.CompletedProcess:
    if owned:
        return _run_owned_process(
            [_GIT_EXECUTABLE, *args], text=text, timeout=timeout
        )
    return subprocess.run(
        [_GIT_EXECUTABLE, *args],
        capture_output=True,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
        timeout=timeout,
    )


def _owned_process_group_kwargs() -> dict[str, object]:
    """Create one independently addressable process tree for a bounded child."""
    return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}


def _windows_process_rows() -> tuple[tuple[int, int], ...] | None:
    """Return one Toolhelp process snapshot without launching another process."""
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = (
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        )

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = (
        wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)
    )
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = (
        wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)
    )
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    invalid_handle = ctypes.c_void_p(-1).value
    if snapshot == invalid_handle:
        return None
    rows: list[tuple[int, int]] = []
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            return None
        while True:
            rows.append((int(entry.th32ProcessID), int(entry.th32ParentProcessID)))
            if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                break
    finally:
        kernel32.CloseHandle(snapshot)
    return tuple(rows)


def _windows_terminate_pid(pid: int, timeout: float) -> None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (
        wintypes.DWORD, wintypes.BOOL, wintypes.DWORD
    )
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
    kernel32.TerminateProcess.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(0x0001 | 0x00100000, False, pid)
    if not handle:
        return
    try:
        kernel32.TerminateProcess(handle, 1)
        milliseconds = max(1, min(0xFFFFFFFE, int(timeout * 1000)))
        kernel32.WaitForSingleObject(handle, milliseconds)
    finally:
        kernel32.CloseHandle(handle)


class _OwnedProcessSettlement:
    """One owner for terminate, direct-reap ordering, and group-empty proof."""

    def __init__(self, pid: int) -> None:
        self.pid = pid
        self._known_windows_pids = {pid}

    def _windows_live_members(self) -> set[int] | None:
        rows = _windows_process_rows()
        if rows is None:
            return None
        changed = True
        while changed:
            changed = False
            for child_pid, parent_pid in rows:
                if (
                    parent_pid in self._known_windows_pids
                    and child_pid not in self._known_windows_pids
                ):
                    self._known_windows_pids.add(child_pid)
                    changed = True
        return {
            process_pid
            for process_pid, _parent_pid in rows
            if process_pid in self._known_windows_pids
        }

    def terminate(self, deadline: float) -> bool:
        live = self._windows_live_members()
        if live is None:
            return False
        for process_pid in sorted(live, reverse=True):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            _windows_terminate_pid(process_pid, min(0.1, remaining))
        return True

    def verify_empty(self, deadline: float) -> bool:
        while True:
            live = self._windows_live_members()
            if live is None:
                return False
            if not live:
                return True
            if time.monotonic() >= deadline:
                return False
            if not self.terminate(deadline):
                return False
            time.sleep(0.01)


def _run_owned_process(
    argv: list[str],
    *,
    text: bool = False,
    timeout: float | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run a bounded process and settle its whole owned tree on timeout."""
    process_group_owner: PosixProcessGroupOwnerV1 | None = None
    try:
        process_kwargs: dict[str, object]
        if os.name == "nt":
            process_kwargs = _owned_process_group_kwargs()
        else:
            process_group_owner = PosixProcessGroupOwnerV1.acquire()
            process_kwargs = process_group_owner.popen_kwargs
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=text,
            encoding="utf-8" if text else None,
            errors="replace" if text else None,
            env=env,
            **process_kwargs,
        )
        if process_group_owner is not None:
            process_group_owner.bind_process_group(process.pid)
    except BaseException:
        if process_group_owner is not None:
            try:
                process_group_owner.close()
            except PosixProcessGroupError:
                pass
        raise
    expired: subprocess.TimeoutExpired | None = None
    pending_error: BaseException | None = None
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        expired = exc
        stdout, stderr = None, None
    except BaseException as exc:
        pending_error = exc
        stdout, stderr = None, None
    cleanup_deadline = time.monotonic() + _PROCESS_TREE_CLEANUP_SECONDS
    if os.name == "nt":
        settlement = _OwnedProcessSettlement(process.pid)
        termination_started = settlement.terminate(cleanup_deadline)
        if process.poll() is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        try:
            remaining = max(0.0, cleanup_deadline - time.monotonic())
            stdout, stderr = process.communicate(timeout=remaining)
        except subprocess.TimeoutExpired:
            termination_started = False
        group_settled = (
            termination_started
            and process.poll() is not None
            and settlement.verify_empty(cleanup_deadline)
        )
    else:
        assert process_group_owner is not None
        try:
            closure = process_group_owner.settle(
                _PROCESS_TREE_CLEANUP_SECONDS,
                direct_process=process,
            )
            group_settled = closure.complete
        except PosixProcessGroupError:
            group_settled = False
        if group_settled:
            try:
                remaining = max(0.0, cleanup_deadline - time.monotonic())
                stdout, stderr = process.communicate(timeout=remaining)
            except (subprocess.TimeoutExpired, OSError, ValueError):
                group_settled = False
    if not group_settled:
        raise RuntimeError("owned process group did not settle")
    if pending_error is not None:
        raise pending_error
    if expired is not None:
        raise subprocess.TimeoutExpired(
            expired.cmd, expired.timeout, output=stdout, stderr=stderr
        ) from None
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)


def _range_git_argv(*args: str) -> tuple[str, ...]:
    """Build a replacement-disabled Git command for pushed-object inspection."""
    return (_GIT_EXECUTABLE, "--no-replace-objects", *args)


def _run_range_git(
    args: list[str], *, text: bool = False, timeout: float | None = None
) -> subprocess.CompletedProcess:
    return _run_git(
        ["--no-replace-objects", *args],
        text=text,
        timeout=timeout,
        owned=True,
    )


async def _acquire_posix_process_group_owner() -> PosixProcessGroupOwnerV1:
    task = asyncio.create_task(
        asyncio.to_thread(PosixProcessGroupOwnerV1.acquire)
    )
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        owner = await task
        await asyncio.to_thread(owner.close)
        raise


class _AsyncioDirectProcessObservation:
    """Passive thread-safe observation of asyncio's exclusive direct-child reap."""

    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self._process = process
        self._terminal = threading.Event()
        self._returncode: int | None = None
        self._task = asyncio.create_task(self._observe())

    async def _observe(self) -> int:
        returncode = await self._process.wait()
        self._returncode = returncode
        self._terminal.set()
        return returncode

    @property
    def task(self) -> asyncio.Task[int]:
        return self._task

    def poll(self) -> int | None:
        return self._returncode if self._terminal.is_set() else None

    def wait(self, timeout: float | None = None) -> int:
        if not self._terminal.wait(timeout):
            raise subprocess.TimeoutExpired(("asyncio-direct-child",), timeout)
        assert self._returncode is not None
        return self._returncode


async def _create_owned_async_process(
    argv: tuple[str, ...],
    **kwargs,
) -> tuple[
    asyncio.subprocess.Process,
    PosixProcessGroupOwnerV1 | None,
    _AsyncioDirectProcessObservation | None,
]:
    process_group_owner: PosixProcessGroupOwnerV1 | None = None
    direct_observation: _AsyncioDirectProcessObservation | None = None
    process_kwargs: dict[str, object]
    if os.name == "nt":
        process_kwargs = _owned_process_group_kwargs()
    else:
        process_group_owner = await _acquire_posix_process_group_owner()
        process_kwargs = process_group_owner.popen_kwargs
    try:
        process = await asyncio.create_subprocess_exec(
            *argv, **kwargs, **process_kwargs
        )
        if process_group_owner is not None:
            process_group_owner.bind_process_group(process.pid)
            direct_observation = _AsyncioDirectProcessObservation(process)
        return process, process_group_owner, direct_observation
    except BaseException:
        if process_group_owner is not None:
            try:
                await asyncio.to_thread(process_group_owner.close)
            except PosixProcessGroupError:
                pass
        raise


async def _drain_owned_async_reader(
    reader: asyncio.StreamReader | None,
    deadline: float,
) -> bool:
    if reader is None:
        return True
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            chunk = await asyncio.wait_for(
                reader.read(_READ_CHUNK_BYTES), timeout=remaining
            )
            if not chunk:
                return True
    except (asyncio.TimeoutError, OSError, ValueError):
        return False


async def _wait_owned_async_direct(
    process: asyncio.subprocess.Process,
    direct_observation: _AsyncioDirectProcessObservation | None,
    timeout: float,
) -> int:
    if os.name == "nt":
        return await asyncio.wait_for(process.wait(), timeout=timeout)
    if direct_observation is None:
        raise RuntimeError("POSIX direct-process observation is unavailable")
    return await asyncio.wait_for(
        asyncio.shield(direct_observation.task), timeout=timeout
    )


async def _settle_owned_async_process(
    process: asyncio.subprocess.Process,
    process_group_owner: PosixProcessGroupOwnerV1 | None,
    direct_observation: _AsyncioDirectProcessObservation | None,
    timeout_seconds: float = _PROCESS_TREE_CLEANUP_SECONDS,
    *,
    drain_readers: tuple[asyncio.StreamReader | None, ...] = (),
) -> bool:
    cleanup_deadline = time.monotonic() + timeout_seconds
    if os.name == "nt":
        settlement = _OwnedProcessSettlement(process.pid)
        termination_started = await asyncio.to_thread(
            settlement.terminate, cleanup_deadline
        )
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        try:
            remaining = max(0.0, cleanup_deadline - time.monotonic())
            await asyncio.wait_for(process.wait(), timeout=remaining)
        except Exception:
            return False
        if not termination_started or process.returncode is None:
            return False
        return await asyncio.to_thread(
            settlement.verify_empty, cleanup_deadline
        )

    if process_group_owner is None or direct_observation is None:
        return False
    remaining = max(0.000001, cleanup_deadline - time.monotonic())
    settle_task = asyncio.create_task(
        asyncio.to_thread(
            process_group_owner.settle,
            remaining,
            direct_process=direct_observation,
        )
    )
    cancelled: asyncio.CancelledError | None = None
    try:
        closure = await asyncio.shield(settle_task)
    except asyncio.CancelledError as exc:
        cancelled = exc
        closure = await settle_task
    except PosixProcessGroupError:
        return False
    drained = True
    for reader in drain_readers:
        if not await _drain_owned_async_reader(reader, cleanup_deadline):
            drained = False
    observed_returncode = direct_observation.poll()
    complete = (
        closure.complete
        and closure.lock_released
        and observed_returncode is not None
        and process.returncode == observed_returncode
        and direct_observation.task.done()
        and drained
    )
    if cancelled is not None:
        raise cancelled
    return complete


def _repo_root() -> Path:
    proc = _run_git(["rev-parse", "--show-toplevel"], text=True)
    if proc.returncode:
        raise RuntimeError("not inside a git repository")
    return Path(proc.stdout.strip())


def _manual_path_finder(script: Path):
    """Compose the canonical classifier for direct diagnostic invocation only.

    The authoritative gate child injects the already-captured callable and never
    reaches this filesystem path.
    """
    module_path = script.parent.parent / "hooks" / "check-machine-local-path.py"
    namespace = {"__name__": "_publication_path_owner", "__file__": str(module_path)}
    try:
        source = module_path.read_bytes()
        exec(compile(source, str(module_path), "exec"), namespace)
        finder = namespace["find_machine_paths"]
    except (OSError, KeyError, TypeError, SyntaxError) as exc:
        raise RuntimeError("cannot compose path owner") from exc
    if not callable(finder):
        raise RuntimeError("cannot compose path owner")
    return finder


def _path_finder(script: Path):
    injected = globals().get("__injected_find_machine_paths__")
    return injected if callable(injected) else _manual_path_finder(script)


def _intentional_scanner_line(line: str) -> bool:
    stripped = line.strip()
    return (
        not stripped
        or stripped.startswith("#")
        or _SCANNER_REGEX_CATALOG_LINE.fullmatch(stripped) is not None
    )


def _safe_locator(path: str, subject_kind: str) -> str:
    value = Path(path).name if subject_kind == "path-blob" else path
    return "".join(
        char if 32 <= ord(char) < 127 else f"\\x{ord(char):02x}"
        for char in value.replace("\\", "/")
    )


def _content_hits(
    text: str,
    path: str,
    find_machine_paths,
    *,
    subject_kind: str = "tracked-blob",
    max_findings: int | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    normalized_path = path.replace("\\", "/")
    scanner = (
        subject_kind != "commit-message"
        and normalized_path in _SCANNER_EXEMPT_PATHS
    )
    locator = _safe_locator(path, subject_kind)
    for line_number, line in enumerate(text.splitlines(), 1):
        if max_findings is not None and len(findings) >= max_findings:
            break
        if scanner and _intentional_scanner_line(line):
            continue
        for index, pattern in enumerate(_SIMPLE_PATTERNS):
            if pattern.search(line):
                findings.append(Finding(
                    "PS-FINDING-COMMIT-MESSAGE" if subject_kind == "commit-message" else "PS-FINDING-CONTENT",
                    subject_kind,
                    locator,
                    line_number,
                    f"simple-{index + 1}",
                ))
                if max_findings is not None and len(findings) >= max_findings:
                    break
                break
        else:
            for family, pattern in _VALUE_RULES:
                if pattern.search(line):
                    findings.append(Finding(
                        "PS-FINDING-COMMIT-MESSAGE" if subject_kind == "commit-message" else "PS-FINDING-CONTENT",
                        subject_kind,
                        locator,
                        line_number,
                        f"value-{family}",
                    ))
                    if max_findings is not None and len(findings) >= max_findings:
                        break
                    break
        if max_findings is not None and len(findings) >= max_findings:
            continue
        if find_machine_paths(line):
            findings.append(Finding(
                "PS-FINDING-COMMIT-MESSAGE" if subject_kind == "commit-message" else "PS-FINDING-CONTENT",
                subject_kind,
                locator,
                line_number,
                "machine-path",
            ))
    return findings


def _is_binary(raw: bytes) -> bool:
    return b"\0" in raw


def _tracked_files() -> tuple[list[str], dict[str, bytes]]:
    names = _run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMRTUXB", "-z", "--"])
    if names.returncode:
        raise RuntimeError("could not enumerate staged tracked files")
    paths = [part.decode("utf-8", "surrogateescape") for part in names.stdout.split(b"\0") if part]
    blobs: dict[str, bytes] = {}
    for path in paths:
        proc = _run_git(["show", f":{path}"])
        if proc.returncode:
            raise RuntimeError(f"could not read staged content for {path!r}")
        blobs[path] = proc.stdout
    return paths, blobs


def _length_frame(value: bytes) -> bytes:
    return len(value).to_bytes(8, "big") + value


def _digest_frames(domain: bytes, rows: Iterable[bytes]) -> str:
    digest = hashlib.sha256(_length_frame(_RECEIPT_DOMAIN) + _length_frame(domain))
    for row in rows:
        digest.update(_length_frame(row))
    return digest.hexdigest()


def _commit_set_digest(commit_ids: Iterable[str]) -> str:
    return _digest_frames(
        b"commit-set",
        (value.lower().encode("ascii") for value in commit_ids),
    )


def _oid_set_digest(domain: bytes, object_ids: Iterable[str]) -> str:
    return _digest_frames(
        domain,
        (value.lower().encode("ascii") for value in sorted(object_ids)),
    )


def _remaining_seconds(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise subprocess.TimeoutExpired("publication-safety-range", 0)
    return remaining


def _detect_git_object_format(timeout: float | None = None) -> GitObjectFormat:
    proc = _run_range_git(
        ["rev-parse", "--show-object-format"], text=True, timeout=timeout
    )
    rows = proc.stdout.splitlines()
    if proc.returncode or len(rows) != 1:
        raise ValueError("object-format")
    try:
        return _SUPPORTED_OBJECT_FORMATS[rows[0]]
    except KeyError as exc:
        raise ValueError("object-format") from exc


def _resolve_commit(
    revision: str,
    timeout: float | None = None,
    *,
    object_format: GitObjectFormat = _SHA1_OBJECT_FORMAT,
) -> str:
    if not revision:
        raise ValueError("revision")
    proc = _run_range_git(
        [
            "rev-parse", "--verify", "--end-of-options",
            f"{revision}^{{commit}}",
        ],
        text=True,
        timeout=timeout,
    )
    if proc.returncode:
        raise ValueError("revision")
    rows = proc.stdout.splitlines()
    if len(rows) != 1:
        raise ValueError("revision")
    oid = rows[0].lower()
    if not object_format.matches(oid):
        raise ValueError("revision")
    return oid


def _graft_overlay_present(timeout: float | None = None) -> bool:
    proc = _run_range_git(
        ["rev-parse", "--git-path", "info/grafts"], text=True, timeout=timeout
    )
    rows = proc.stdout.splitlines()
    if proc.returncode or len(rows) != 1 or not rows[0]:
        raise ValueError("graft-path")
    graft_path = Path(rows[0])
    try:
        with graft_path.open("rb") as stream:
            return bool(stream.read(1))
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ValueError("graft-path") from exc


async def _read_git_lines_bounded(
    argv: tuple[str, ...],
    *,
    byte_cap: int,
    line_cap: int,
    deadline: float,
    accepted_codes: frozenset[int],
    env: dict[str, str] | None = None,
) -> tuple[int, tuple[bytes, ...]] | Refusal:
    process_group_owner: PosixProcessGroupOwnerV1 | None = None
    direct_observation: _AsyncioDirectProcessObservation | None = None
    try:
        (
            process,
            process_group_owner,
            direct_observation,
        ) = await _create_owned_async_process(
            argv,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return _refusal("PS-MSG-SPAWN", "selection")
    if process.stdout is None:
        if not await _settle_owned_async_process(
            process, process_group_owner, direct_observation
        ):
            return _refusal("PS-MSG-REAP", "selection-child")
        return _refusal("PS-MSG-READ", "selection-pipe")

    rows: list[bytes] = []
    pending = bytearray()
    total_bytes = 0
    refusal: Refusal | None = None
    try:
        while refusal is None:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                refusal = _refusal("PS-MSG-READ-TIMEOUT", "deadline")
                break
            try:
                chunk = await asyncio.wait_for(
                    process.stdout.read(_READ_CHUNK_BYTES), timeout=remaining
                )
            except asyncio.TimeoutError:
                refusal = _refusal("PS-MSG-READ-TIMEOUT", "deadline")
                break
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > byte_cap:
                refusal = _refusal("PS-MSG-LIMIT", "selection-bytes")
                break
            pending.extend(chunk)
            while refusal is None:
                newline = pending.find(b"\n")
                if newline < 0:
                    if len(pending) > line_cap:
                        refusal = _refusal("PS-MSG-FRAME", "selection-line")
                    break
                raw = bytes(pending[:newline])
                del pending[:newline + 1]
                if len(raw) > line_cap:
                    refusal = _refusal("PS-MSG-FRAME", "selection-line")
                else:
                    rows.append(raw)
        if refusal is None and pending:
            if len(pending) > line_cap:
                refusal = _refusal("PS-MSG-FRAME", "selection-line")
            else:
                rows.append(bytes(pending))
    except asyncio.CancelledError:
        refusal = _refusal("PS-MSG-READ", "cancelled")
    except Exception:
        refusal = _refusal("PS-MSG-READ", "selection")

    if refusal is None:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            refusal = _refusal("PS-MSG-READ-TIMEOUT", "deadline")
        else:
            try:
                await _wait_owned_async_direct(
                    process, direct_observation, remaining
                )
            except asyncio.TimeoutError:
                refusal = _refusal("PS-MSG-READ-TIMEOUT", "deadline")
            except Exception:
                refusal = _refusal("PS-MSG-READ", "selection-wait")

    if not await _settle_owned_async_process(
        process,
        process_group_owner,
        direct_observation,
        drain_readers=(process.stdout,),
    ):
        return _refusal("PS-MSG-REAP", "selection-child")
    if refusal is not None:
        return refusal
    if process.returncode not in accepted_codes:
        return _refusal("PS-MSG-RANGE", "selection-child")
    return process.returncode, tuple(rows)


def _destination_ref(destination: str) -> str:
    return destination if destination.startswith("refs/") else f"refs/heads/{destination}"


_REMOTE_PROBE_ALIAS_PREFIX = "publication-safety-probe://"
_REMOTE_PROBE_NONCE_BYTES = 32
_REMOTE_PROBE_NONCE_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _remote_probe_binding(
    push_destination: str,
) -> tuple[str, dict[str, str]] | Refusal:
    try:
        nonce = secrets.token_hex(_REMOTE_PROBE_NONCE_BYTES)
        if not isinstance(nonce, str) or not _REMOTE_PROBE_NONCE_PATTERN.fullmatch(nonce):
            return _refusal("PS-MSG-RANGE", "remote-binding")
        remote_alias = _REMOTE_PROBE_ALIAS_PREFIX + nonce
        child_env = os.environ.copy()
        raw_count = child_env.get("GIT_CONFIG_COUNT")
        if raw_count is None:
            config_count = 0
        elif not re.fullmatch(r"(?:0|[1-9][0-9]{0,3})", raw_count):
            return _refusal("PS-MSG-RANGE", "remote-binding")
        else:
            config_count = int(raw_count, 10)
        if config_count > 1024:
            return _refusal("PS-MSG-RANGE", "remote-binding")
        for index in range(config_count):
            if (
                f"GIT_CONFIG_KEY_{index}" not in child_env
                or f"GIT_CONFIG_VALUE_{index}" not in child_env
            ):
                return _refusal("PS-MSG-RANGE", "remote-binding")
        if (
            f"GIT_CONFIG_KEY_{config_count}" in child_env
            or f"GIT_CONFIG_VALUE_{config_count}" in child_env
        ):
            return _refusal("PS-MSG-RANGE", "remote-binding")
        child_env.update({
            "GIT_CONFIG_COUNT": str(config_count + 1),
            f"GIT_CONFIG_KEY_{config_count}": f"url.{push_destination}.insteadOf",
            f"GIT_CONFIG_VALUE_{config_count}": remote_alias,
        })
    except Exception:
        return _refusal("PS-MSG-RANGE", "remote-binding")
    return remote_alias, child_env


async def _unique_push_destination(
    remote: str, *, deadline: float
) -> str | Refusal:
    result = await _read_git_lines_bounded(
        _range_git_argv("remote", "get-url", "--push", "--all", remote),
        byte_cap=(2 * _MAX_PATH_BYTES) + 2,
        line_cap=_MAX_PATH_BYTES,
        deadline=deadline,
        accepted_codes=frozenset({0}),
    )
    if isinstance(result, Refusal):
        return result
    _returncode, rows = result
    if len(rows) != 1 or not rows[0]:
        return _refusal("PS-MSG-RANGE", "push-destination")
    try:
        return rows[0].decode("utf-8", "strict")
    except UnicodeDecodeError:
        return _refusal("PS-MSG-RANGE", "push-destination")


async def _remote_destination_oid(
    push_destination: str,
    destination: str,
    *,
    deadline: float,
    object_format: GitObjectFormat,
) -> str | None | Refusal:
    destination_ref = _destination_ref(destination)
    try:
        encoded_ref = destination_ref.encode("utf-8", "strict")
    except UnicodeError:
        return _refusal("PS-MSG-RANGE", "destination-ref")
    if len(encoded_ref) > _MAX_PATH_BYTES:
        return _refusal("PS-MSG-LIMIT", "destination-ref")
    line_cap = object_format.hex_length + 1 + len(encoded_ref)
    binding = _remote_probe_binding(push_destination)
    if isinstance(binding, Refusal):
        return binding
    remote_alias, child_env = binding
    result = await _read_git_lines_bounded(
        _range_git_argv(
            "ls-remote", "--refs", "--exit-code", remote_alias, destination_ref
        ),
        byte_cap=line_cap + 1,
        line_cap=line_cap,
        deadline=deadline,
        accepted_codes=frozenset({0, 2}),
        env=child_env,
    )
    if isinstance(result, Refusal):
        return result
    returncode, rows = result
    if returncode == 2 and not rows:
        return None
    if returncode != 0 or len(rows) != 1:
        return _refusal("PS-MSG-RANGE", "destination-remote")
    parts = rows[0].split(b"\t")
    if len(parts) != 2 or parts[1] != encoded_ref:
        return _refusal("PS-MSG-FRAME", "destination-remote")
    try:
        oid = parts[0].decode("ascii").lower()
    except UnicodeDecodeError:
        return _refusal("PS-MSG-FRAME", "destination-remote")
    if not object_format.matches(oid):
        return _refusal("PS-MSG-FRAME", "destination-remote")
    return oid


def _parse_remote_ref_tip_oids(
    rows: tuple[bytes, ...], object_format: GitObjectFormat
) -> tuple[RemoteRefTip, ...] | Refusal:
    if not rows:
        return _refusal("PS-MSG-RANGE", "remote-refs")
    if len(rows) > 2 * _MAX_REMOTE_REFS:
        return _refusal("PS-MSG-LIMIT", "remote-ref-count")
    line_cap = object_format.hex_length + 1 + _MAX_PATH_BYTES + len(b"^{}")
    refs: dict[bytes, str] = {}
    peeled_refs: dict[bytes, str] = {}
    for raw in rows:
        if len(raw) > line_cap:
            return _refusal("PS-MSG-FRAME", "remote-ref")
        parts = raw.split(b"\t")
        if len(parts) != 2:
            return _refusal("PS-MSG-FRAME", "remote-ref")
        raw_oid, raw_ref = parts
        is_peeled = raw_ref.endswith(b"^{}")
        base_ref = raw_ref[:-3] if is_peeled else raw_ref
        if is_peeled and not base_ref.startswith(b"refs/tags/"):
            return _refusal("PS-MSG-FRAME", "remote-ref")
        if not _valid_remote_refname(base_ref):
            return _refusal("PS-MSG-FRAME", "remote-ref")
        try:
            oid = raw_oid.decode("ascii").lower()
        except UnicodeDecodeError:
            return _refusal("PS-MSG-FRAME", "remote-ref")
        destination = peeled_refs if is_peeled else refs
        if not object_format.matches(oid) or base_ref in destination:
            return _refusal("PS-MSG-FRAME", "remote-ref")
        destination[base_ref] = oid
    if len(refs) > _MAX_REMOTE_REFS:
        return _refusal("PS-MSG-LIMIT", "remote-ref-count")
    if not refs:
        return _refusal("PS-MSG-RANGE", "remote-refs")
    if any(refname not in refs for refname in peeled_refs):
        return _refusal("PS-MSG-FRAME", "remote-ref")
    return tuple(
        RemoteRefTip(refname, oid, peeled_refs.get(refname))
        for refname, oid in refs.items()
    )


def _valid_remote_refname(raw_ref: bytes) -> bool:
    if (
        not raw_ref.startswith(b"refs/")
        or len(raw_ref) > _MAX_PATH_BYTES
        or raw_ref.endswith((b"/", b"."))
        or b".." in raw_ref
        or b"@{" in raw_ref
    ):
        return False
    components = raw_ref.split(b"/")
    if any(
        not component or component.startswith(b".") or component.endswith(b".lock")
        for component in components
    ):
        return False
    forbidden = b" ~^:?*[\\"
    return all(byte >= 0x20 and byte != 0x7F and byte not in forbidden for byte in raw_ref)


async def _remote_ref_tip_oids(
    push_destination: str,
    *,
    deadline: float,
    object_format: GitObjectFormat,
) -> tuple[RemoteRefTip, ...] | Refusal:
    base_line_cap = object_format.hex_length + 1 + _MAX_PATH_BYTES
    peeled_line_cap = base_line_cap + len(b"^{}")
    binding = _remote_probe_binding(push_destination)
    if isinstance(binding, Refusal):
        return binding
    remote_alias, child_env = binding
    result = await _read_git_lines_bounded(
        _range_git_argv("ls-remote", remote_alias, "refs/*"),
        byte_cap=_MAX_REMOTE_REFS * (base_line_cap + peeled_line_cap + 2),
        line_cap=peeled_line_cap,
        deadline=deadline,
        accepted_codes=frozenset({0}),
        env=child_env,
    )
    if isinstance(result, Refusal):
        return result
    _returncode, rows = result
    return _parse_remote_ref_tip_oids(rows, object_format)


async def _local_remote_commit_tip_oids(
    remote_tip_oids: tuple[RemoteRefTip, ...],
    *,
    deadline: float,
    object_format: GitObjectFormat,
) -> tuple[str, ...] | Refusal:
    reader = _AsyncGitObjectReader(
        argv=_range_git_argv("cat-file", "--batch-check")
    )
    pending: tuple[str, ...] | Refusal | None = None
    commits: list[str] = []
    seen_commits: set[str] = set()
    try:
        start_refusal = await reader.start()
        if start_refusal is not None:
            pending = start_refusal
        else:
            for remote_ref in remote_tip_oids:
                classified = await reader.classify(
                    remote_ref.oid,
                    object_format=object_format,
                    scan_deadline=deadline,
                )
                if isinstance(classified, Refusal):
                    pending = classified
                    break
                if classified.returned_oid is None:
                    if remote_ref.peeled_oid is None:
                        # Neither the remote ref object nor an authoritative
                        # peel can name a locally available commit exclusion.
                        continue
                    peeled = await reader.classify(
                        remote_ref.peeled_oid,
                        object_format=object_format,
                        scan_deadline=deadline,
                    )
                    if isinstance(peeled, Refusal):
                        pending = peeled
                        break
                    if peeled.returned_oid is None:
                        continue
                    if peeled.object_type != "commit":
                        pending = _refusal("PS-MSG-RANGE", "remote-ref-type")
                        break
                    commit_oid = peeled.returned_oid
                elif classified.object_type == "commit":
                    if remote_ref.peeled_oid is not None:
                        pending = _refusal("PS-MSG-RANGE", "remote-ref-type")
                        break
                    commit_oid = classified.returned_oid
                elif classified.object_type == "tag":
                    peeled = await reader.classify(
                        f"{remote_ref.oid}^{{commit}}",
                        object_format=object_format,
                        require_identity=False,
                        scan_deadline=deadline,
                    )
                    if isinstance(peeled, Refusal):
                        pending = peeled
                        break
                    if peeled.returned_oid is None or peeled.object_type != "commit":
                        pending = _refusal("PS-MSG-RANGE", "remote-ref-type")
                        break
                    if (
                        remote_ref.peeled_oid is not None
                        and peeled.returned_oid != remote_ref.peeled_oid
                    ):
                        pending = _refusal("PS-MSG-RANGE", "remote-ref-type")
                        break
                    commit_oid = peeled.returned_oid
                else:
                    pending = _refusal("PS-MSG-RANGE", "remote-ref-type")
                    break
                if commit_oid not in seen_commits:
                    seen_commits.add(commit_oid)
                    commits.append(commit_oid)
            if pending is None:
                pending = tuple(commits)
    except asyncio.CancelledError:
        pending = _refusal("PS-MSG-READ", "cancelled")
    except Exception:
        pending = _refusal("PS-MSG-READ", "unexpected")

    finalization = await _finalize_reader(reader)
    if (
        finalization is not None
        and finalization.failure_id == "PS-MSG-REAP"
        and reader.state is ReaderState.REAP_PENDING
    ):
        finalization = await _finalize_reader(reader)
    if finalization is not None:
        return finalization
    certificate = reader.reap_certificate
    if certificate is None or not certificate.complete:
        return _refusal("PS-MSG-REAP", "certificate")
    if pending is None:
        return _refusal("PS-MSG-READ", "unexpected")
    return pending


async def _read_parent_graph_bounded(
    argv: tuple[str, ...],
    *,
    deadline: float,
    object_format: GitObjectFormat,
) -> tuple[tuple[str, tuple[str, ...]], ...] | Refusal:
    result = await _read_git_lines_bounded(
        argv,
        byte_cap=_MAX_PARENT_GRAPH_BYTES,
        line_cap=_MAX_COMMIT_TREE_BYTES,
        deadline=deadline,
        accepted_codes=frozenset({0}),
    )
    if isinstance(result, Refusal):
        return result
    _returncode, rows = result
    if len(rows) > _MAX_COMMITS:
        return _refusal("PS-MSG-LIMIT", "count")
    parsed: list[tuple[str, tuple[str, ...]]] = []
    seen: set[str] = set()
    for row in rows:
        fields = row.split(b" ")
        if not fields or any(len(field) != object_format.hex_length for field in fields):
            return _refusal("PS-MSG-FRAME", "parent-graph")
        try:
            values = tuple(field.decode("ascii").lower() for field in fields)
        except UnicodeDecodeError:
            return _refusal("PS-MSG-FRAME", "parent-graph")
        if any(not object_format.matches(value) for value in values):
            return _refusal("PS-MSG-FRAME", "parent-graph")
        oid, parents = values[0], values[1:]
        if oid in seen:
            return _refusal("PS-MSG-FRAME", "parent-graph")
        seen.add(oid)
        parsed.append((oid, parents))
    return tuple(parsed)


def _resolve_head(timeout: float | None = None) -> str:
    object_format = _detect_git_object_format(timeout)
    return _resolve_commit("HEAD", timeout, object_format=object_format)


async def _read_git_oid_lines_bounded(
    argv: tuple[str, ...],
    *,
    count_cap: int,
    byte_cap: int,
    deadline: float,
    object_format: GitObjectFormat = _SHA1_OBJECT_FORMAT,
) -> tuple[str, ...] | Refusal:
    process_group_owner: PosixProcessGroupOwnerV1 | None = None
    direct_observation: _AsyncioDirectProcessObservation | None = None
    try:
        (
            process,
            process_group_owner,
            direct_observation,
        ) = await _create_owned_async_process(
            argv,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return _refusal("PS-MSG-SPAWN", "selection")
    if process.stdout is None:
        if not await _settle_owned_async_process(
            process, process_group_owner, direct_observation
        ):
            return _refusal("PS-MSG-REAP", "selection-child")
        return _refusal("PS-MSG-READ", "selection-pipe")

    rows: list[str] = []
    seen: set[str] = set()
    pending = bytearray()
    total_bytes = 0
    refusal: Refusal | None = None

    def accept(raw: bytes) -> Refusal | None:
        if len(raw) != object_format.hex_length:
            return _refusal("PS-MSG-FRAME", "oid")
        try:
            oid = raw.decode("ascii").lower()
        except UnicodeDecodeError:
            return _refusal("PS-MSG-FRAME", "oid")
        if not object_format.matches(oid) or oid in seen:
            return _refusal("PS-MSG-FRAME", "oid")
        if len(rows) >= count_cap:
            return _refusal("PS-MSG-LIMIT", "count")
        seen.add(oid)
        rows.append(oid)
        return None

    try:
        while refusal is None:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                refusal = _refusal("PS-MSG-READ-TIMEOUT", "deadline")
                break
            try:
                chunk = await asyncio.wait_for(
                    process.stdout.read(_READ_CHUNK_BYTES), timeout=remaining
                )
            except asyncio.TimeoutError:
                refusal = _refusal("PS-MSG-READ-TIMEOUT", "deadline")
                break
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > byte_cap:
                refusal = _refusal("PS-MSG-LIMIT", "bytes")
                break
            pending.extend(chunk)
            while refusal is None:
                newline = pending.find(b"\n")
                if newline < 0:
                    if len(pending) > object_format.hex_length:
                        refusal = _refusal("PS-MSG-FRAME", "oid")
                    break
                raw = bytes(pending[:newline])
                del pending[:newline + 1]
                refusal = accept(raw)
        if refusal is None and pending:
            refusal = accept(bytes(pending))
    except asyncio.CancelledError:
        refusal = _refusal("PS-MSG-READ", "cancelled")
    except Exception:
        refusal = _refusal("PS-MSG-READ", "selection")

    if refusal is None:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            refusal = _refusal("PS-MSG-READ-TIMEOUT", "deadline")
        else:
            try:
                await _wait_owned_async_direct(
                    process, direct_observation, remaining
                )
            except asyncio.TimeoutError:
                refusal = _refusal("PS-MSG-READ-TIMEOUT", "deadline")
            except Exception:
                refusal = _refusal("PS-MSG-READ", "selection-wait")

    if not await _settle_owned_async_process(
        process,
        process_group_owner,
        direct_observation,
        drain_readers=(process.stdout,),
    ):
        return _refusal("PS-MSG-REAP", "selection-child")
    if refusal is not None:
        return refusal
    if process.returncode != 0:
        return _refusal("PS-MSG-RANGE", "selection-child")
    return tuple(rows)


def _range_request(
    remote: str, destination: str, source: str | None
) -> RangeRequest | Refusal:
    if not destination:
        return _refusal("PS-MSG-RANGE", "destination")
    effective_source = destination if source is None else source
    if not effective_source:
        return _refusal("PS-MSG-RANGE", "source")
    return RangeRequest(remote, destination, effective_source)


async def _range_selection(
    request: RangeRequest,
    deadline: float | None = None,
) -> RangeSelection | Refusal:
    deadline = deadline if deadline is not None else time.monotonic() + _SCAN_DEADLINE_SECONDS
    try:
        remotes = _run_range_git(
            ["remote"], text=True, timeout=_remaining_seconds(deadline)
        )
    except subprocess.TimeoutExpired:
        return _refusal("PS-MSG-READ-TIMEOUT", "deadline")
    configured = [line for line in remotes.stdout.splitlines() if line]
    if remotes.returncode or request.remote not in configured:
        return _refusal("PS-MSG-RANGE", "remote")
    try:
        object_format = _detect_git_object_format(_remaining_seconds(deadline))
    except subprocess.TimeoutExpired:
        return _refusal("PS-MSG-READ-TIMEOUT", "deadline")
    except (OSError, ValueError):
        return _refusal("PS-MSG-RANGE", "object-format")
    try:
        if _graft_overlay_present(_remaining_seconds(deadline)):
            return _refusal("PS-MSG-RANGE", "graft-overlay")
    except subprocess.TimeoutExpired:
        return _refusal("PS-MSG-READ-TIMEOUT", "deadline")
    except (OSError, ValueError):
        return _refusal("PS-MSG-RANGE", "graft-overlay")
    try:
        tip = _resolve_commit(
            request.source,
            _remaining_seconds(deadline),
            object_format=object_format,
        )
    except subprocess.TimeoutExpired:
        return _refusal("PS-MSG-READ-TIMEOUT", "deadline")
    except (OSError, ValueError):
        return _refusal("PS-MSG-RANGE", "destination")
    loop_deadline = asyncio.get_running_loop().time() + max(
        0.0, deadline - time.monotonic()
    )
    push_destination = await _unique_push_destination(
        request.remote, deadline=loop_deadline
    )
    if isinstance(push_destination, Refusal):
        return push_destination
    destination_oid = await _remote_destination_oid(
        push_destination,
        request.destination,
        deadline=loop_deadline,
        object_format=object_format,
    )
    if isinstance(destination_oid, Refusal):
        return destination_oid
    if destination_oid is None:
        remote_tip_oids = await _remote_ref_tip_oids(
            push_destination,
            deadline=loop_deadline,
            object_format=object_format,
        )
        if isinstance(remote_tip_oids, Refusal):
            return remote_tip_oids
        local_commit_tips = await _local_remote_commit_tip_oids(
            remote_tip_oids,
            deadline=loop_deadline,
            object_format=object_format,
        )
        if isinstance(local_commit_tips, Refusal):
            return local_commit_tips
        exclusion = () if not local_commit_tips else ("--not", *local_commit_tips)
    else:
        exclusion = ("--not", destination_oid)
    parent_graph = await _read_parent_graph_bounded(
        _range_git_argv("rev-list", "--parents", "--topo-order", tip, *exclusion),
        deadline=asyncio.get_running_loop().time()
        + max(0.0, deadline - time.monotonic()),
        object_format=object_format,
    )
    if isinstance(parent_graph, Refusal):
        return parent_graph
    commit_ids = tuple(oid for oid, _parents in parent_graph)
    object_ids = await _read_git_oid_lines_bounded(
        _range_git_argv(
            "rev-list", "--objects", "--no-object-names", tip, *exclusion
        ),
        count_cap=_MAX_OBJECTS,
        byte_cap=object_format.list_byte_cap(_MAX_OBJECTS),
        deadline=asyncio.get_running_loop().time()
        + max(0.0, deadline - time.monotonic()),
        object_format=object_format,
    )
    if isinstance(object_ids, Refusal):
        return object_ids
    if commit_ids and not object_ids:
        return _refusal("PS-MSG-COVERAGE", "objects")
    object_set = frozenset(object_ids)
    if any(oid not in object_set for oid in commit_ids):
        return _refusal("PS-MSG-COVERAGE", "commit-object-set")
    return RangeSelection(
        remote=request.remote,
        destination=request.destination,
        source=request.source,
        tip=tip,
        expected_oids=commit_ids,
        object_oids=object_ids,
        object_format=object_format,
        destination_oid=destination_oid,
        expected_parents=parent_graph,
    )


def _parse_batch_header(
    header: bytes, expected_oid: str, expected_type: str
) -> int | Refusal:
    parsed = _parse_batch_frame_header(header, expected_oid, expected_type)
    return parsed if isinstance(parsed, Refusal) else parsed[1]


def _parse_batch_frame_header(
    header: bytes, expected_oid: str, expected_type: str | None
) -> tuple[str, int] | Refusal:
    expected = expected_oid.encode("ascii")
    if header == expected + b" missing":
        return _refusal("PS-MSG-READ", "missing")
    parts = header.split(b" ")
    if len(parts) != 3:
        return _refusal("PS-MSG-FRAME", "header")
    raw_oid, raw_type, raw_length = parts
    if raw_oid != expected:
        return _refusal("PS-MSG-FRAME", "identity")
    try:
        object_type = raw_type.decode("ascii")
    except UnicodeDecodeError:
        return _refusal("PS-MSG-FRAME", "type")
    if object_type not in {"commit", "tree", "blob"}:
        return _refusal("PS-MSG-FRAME", "type")
    if expected_type is not None and object_type != expected_type:
        return _refusal("PS-MSG-FRAME", "identity")
    try:
        length = int(raw_length)
    except ValueError:
        return _refusal("PS-MSG-FRAME", "length")
    if length < 0:
        return _refusal("PS-MSG-FRAME", "length")
    return object_type, length


def _parse_batch_check_frame(
    header: bytes,
    requested_name: str,
    object_format: GitObjectFormat,
    *,
    require_identity: bool,
) -> ObjectClassification | Refusal:
    try:
        requested = requested_name.encode("ascii")
    except UnicodeEncodeError:
        return _refusal("PS-MSG-FRAME", "batch-check-request")
    if header == requested + b" missing":
        return ObjectClassification(requested_name, None, None)
    parts = header.split(b" ")
    if len(parts) != 3:
        return _refusal("PS-MSG-FRAME", "batch-check-header")
    raw_oid, raw_type, raw_length = parts
    try:
        returned_oid = raw_oid.decode("ascii").lower()
        object_type = raw_type.decode("ascii")
        length = int(raw_length)
    except (UnicodeDecodeError, ValueError):
        return _refusal("PS-MSG-FRAME", "batch-check-header")
    if (
        not object_format.matches(returned_oid)
        or object_type not in {"commit", "tree", "blob", "tag"}
        or length < 0
    ):
        return _refusal("PS-MSG-FRAME", "batch-check-header")
    if require_identity and returned_oid != requested_name:
        return _refusal("PS-MSG-FRAME", "batch-check-identity")
    return ObjectClassification(requested_name, returned_oid, object_type)


@dataclass(frozen=True)
class _ReaderFinalizerResult:
    refusal: Refusal | None
    child: ChildObservation
    stdin: TransportObservation
    stdout: TransportObservation
    cleanup_errors: tuple[str, ...]


class _AsyncGitObjectReader:
    """One owned asynchronous `git cat-file --batch` session.

    The reader owns the child and all three pipe transitions. Every request is
    bounded by one monotonic deadline; the caller owns exactly one finalizer.
    """

    def __init__(
        self,
        *,
        argv: tuple[str, ...] = _range_git_argv("cat-file", "--batch"),
        request_timeout: float = _OBJECT_REQUEST_TIMEOUT_SECONDS,
        settle_timeout: float = OBJECT_REAP_ATTEMPT_SECONDS,
    ) -> None:
        self._argv = argv
        self._request_timeout = request_timeout
        self._settle_timeout = settle_timeout
        self._process: asyncio.subprocess.Process | None = None
        self._process_group_owner: PosixProcessGroupOwnerV1 | None = None
        self._direct_observation: _AsyncioDirectProcessObservation | None = None
        self._poisoned = False
        self._state = ReaderState.CREATED
        self._finalizer_task: asyncio.Task[_ReaderFinalizerResult] | None = None
        self._reap_certificate: ReaderReapCertificate | None = None
        self._attempts_used = 0
        self._session_id = f"reader-session:{id(self)}"

    @property
    def process(self) -> asyncio.subprocess.Process | None:
        return self._process

    @property
    def state(self) -> ReaderState:
        return self._state

    @property
    def is_finalized(self) -> bool:
        return self._state is ReaderState.REAPED

    @property
    def reap_certificate(self) -> ReaderReapCertificate | None:
        return self._reap_certificate

    async def start(self) -> Refusal | None:
        if self._process is not None or self._state is not ReaderState.CREATED:
            return _refusal("PS-MSG-READ", "reader-state")
        try:
            (
                self._process,
                self._process_group_owner,
                self._direct_observation,
            ) = await _create_owned_async_process(
                self._argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except (OSError, subprocess.SubprocessError):
            self._state = ReaderState.SPAWN_FAILED
            return _refusal("PS-MSG-SPAWN", "spawn")
        if self._process.stdin is None or self._process.stdout is None:
            self._poisoned = True
            self._state = ReaderState.REAP_PENDING
            return _refusal("PS-MSG-READ", "pipe")
        self._state = ReaderState.ACTIVE
        return None

    async def _within(self, awaitable, deadline: float):
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            close = getattr(awaitable, "close", None)
            if callable(close):
                close()
            raise asyncio.TimeoutError
        return await asyncio.wait_for(awaitable, timeout=remaining)

    async def read(
        self,
        oid: str,
        expected_type: str | None,
        *,
        scan_deadline: float | None = None,
    ) -> ObjectReadSuccess | Refusal:
        process = self._process
        if (
            self._poisoned
            or self._state is not ReaderState.ACTIVE
            or process is None
            or process.stdin is None
            or process.stdout is None
        ):
            return _refusal("PS-MSG-READ", "reader-state")
        deadline = asyncio.get_running_loop().time() + self._request_timeout
        if scan_deadline is not None:
            deadline = min(deadline, scan_deadline)
        try:
            process.stdin.write(oid.encode("ascii") + b"\n")
            await self._within(process.stdin.drain(), deadline)
            header = await self._within(process.stdout.readline(), deadline)
            if not header.endswith(b"\n"):
                self._poisoned = True
                return _refusal("PS-MSG-FRAME", "header-delimiter")
            parsed = _parse_batch_frame_header(header[:-1], oid, expected_type)
            if isinstance(parsed, Refusal):
                self._poisoned = True
                return parsed
            object_type, length = parsed
            size_cap = _MAX_BLOB_BYTES if object_type == "blob" else _MAX_COMMIT_TREE_BYTES
            if length > size_cap:
                self._poisoned = True
                return _refusal("PS-MSG-LIMIT", f"{object_type}-bytes")
            chunks: list[bytes] = []
            remaining = length
            while remaining:
                chunk = await self._within(
                    process.stdout.readexactly(min(remaining, _READ_CHUNK_BYTES)),
                    deadline,
                )
                chunks.append(chunk)
                remaining -= len(chunk)
            raw = b"".join(chunks)
            delimiter = await self._within(process.stdout.readexactly(1), deadline)
            if delimiter != b"\n":
                self._poisoned = True
                return _refusal("PS-MSG-FRAME", "record-delimiter")
            return ObjectReadSuccess(oid, oid, object_type, raw)
        except asyncio.TimeoutError:
            self._poisoned = True
            return _refusal("PS-MSG-READ-TIMEOUT", "deadline")
        except asyncio.CancelledError:
            self._poisoned = True
            return _refusal("PS-MSG-READ", "cancelled")
        except asyncio.IncompleteReadError:
            self._poisoned = True
            return _refusal("PS-MSG-READ", "short-read")
        except (BrokenPipeError, ConnectionError, OSError, ValueError, UnicodeError):
            self._poisoned = True
            return _refusal("PS-MSG-READ", "pipe")

    async def classify(
        self,
        object_name: str,
        *,
        object_format: GitObjectFormat,
        require_identity: bool = True,
        scan_deadline: float | None = None,
    ) -> ObjectClassification | Refusal:
        process = self._process
        if (
            self._poisoned
            or self._state is not ReaderState.ACTIVE
            or process is None
            or process.stdin is None
            or process.stdout is None
        ):
            return _refusal("PS-MSG-READ", "reader-state")
        try:
            encoded_name = object_name.encode("ascii")
        except UnicodeEncodeError:
            return _refusal("PS-MSG-FRAME", "batch-check-request")
        if (
            not encoded_name
            or len(encoded_name) > object_format.hex_length + len("^{commit}")
            or b"\0" in encoded_name
            or b"\n" in encoded_name
            or b"\r" in encoded_name
        ):
            return _refusal("PS-MSG-FRAME", "batch-check-request")
        deadline = asyncio.get_running_loop().time() + self._request_timeout
        if scan_deadline is not None:
            deadline = min(deadline, scan_deadline)
        try:
            process.stdin.write(encoded_name + b"\n")
            await self._within(process.stdin.drain(), deadline)
            header = await self._within(process.stdout.readline(), deadline)
            if not header.endswith(b"\n") or len(header) > 256:
                self._poisoned = True
                return _refusal("PS-MSG-FRAME", "batch-check-delimiter")
            parsed = _parse_batch_check_frame(
                header[:-1],
                object_name,
                object_format,
                require_identity=require_identity,
            )
            if isinstance(parsed, Refusal):
                self._poisoned = True
            return parsed
        except asyncio.TimeoutError:
            self._poisoned = True
            return _refusal("PS-MSG-READ-TIMEOUT", "deadline")
        except asyncio.CancelledError:
            self._poisoned = True
            return _refusal("PS-MSG-READ", "cancelled")
        except (BrokenPipeError, ConnectionError, OSError, ValueError, UnicodeError):
            self._poisoned = True
            return _refusal("PS-MSG-READ", "pipe")

    async def _wait_step(self, deadline: float, errors: list[str], phase: str) -> bool:
        process = self._process
        if process is None:
            return True
        try:
            if os.name == "nt":
                await self._within(process.wait(), deadline)
            else:
                if self._direct_observation is None:
                    errors.append(phase)
                    return False
                await self._within(
                    asyncio.shield(self._direct_observation.task), deadline
                )
            return process.returncode is not None
        except asyncio.TimeoutError:
            return False
        except Exception:
            errors.append(phase)
            return process.returncode is not None

    async def _drive_finalizer(self) -> _ReaderFinalizerResult:
        process = self._process
        loop = asyncio.get_running_loop()
        now = loop.time()
        if process is None:
            absent_child = ChildObservation("not-created", None, False, now)
            absent_transport = TransportObservation("not-created", "absent", True, None, now)
            return _ReaderFinalizerResult(None, absent_child, absent_transport, absent_transport, ())
        self._attempts_used += 1
        self._state = ReaderState.FINALIZING
        deadline = loop.time() + self._settle_timeout
        errors: list[str] = []
        child_identity = f"pid:{process.pid}"
        stdin = TransportObservation(
            "not-owned" if process.stdin is None else "owned",
            "absent" if process.stdin is None else "unobserved",
            process.stdin is None,
            None,
            loop.time(),
        )
        writer = process.stdin
        if writer is not None:
            try:
                writer.close()
                await self._within(writer.wait_closed(), deadline)
                stdin = TransportObservation("owned", "input-closed", True, None, loop.time())
            except Exception:
                closing = bool(getattr(writer, "is_closing", lambda: False)())
                errors.append("stdin-close")
                stdin = TransportObservation(
                    "owned", "input-closed" if closing else "unobserved", closing,
                    "stdin-close", loop.time(),
                )

        stdout = TransportObservation(
            "not-owned" if process.stdout is None else "owned",
            "absent" if process.stdout is None else "unobserved",
            process.stdout is None,
            None,
            loop.time(),
        )
        if os.name == "nt":
            terminal = await self._wait_step(deadline, errors, "wait")
            if not terminal:
                try:
                    process.terminate()
                except Exception:
                    errors.append("terminate")
                terminal = await self._wait_step(
                    deadline, errors, "terminate-wait"
                )
            if not terminal:
                errors.append("terminate-wait")
        terminal = await _settle_owned_async_process(
            process,
            self._process_group_owner,
            self._direct_observation,
            self._settle_timeout,
        )
        if not terminal:
            errors.append("group-settle")
        child = ChildObservation(
            child_identity,
            process.returncode,
            terminal and process.returncode is not None,
            loop.time(),
        )
        if process.stdout is not None and child.terminal_observed:
            try:
                trailing = False
                while True:
                    chunk = await self._within(
                        process.stdout.read(_READ_CHUNK_BYTES), deadline
                    )
                    if not chunk:
                        break
                    trailing = True
                if trailing:
                    errors.append("stdout-trailing")
                stdout = TransportObservation("owned", "output-eof", True, None, loop.time())
            except Exception:
                errors.append("stdout-drain")
                stdout = TransportObservation("owned", "unobserved", False, "stdout-drain", loop.time())
        if child.terminal_observed and stdin.observed and stdout.observed:
            return _ReaderFinalizerResult(None, child, stdin, stdout, tuple(errors))
        self._state = ReaderState.REAP_PENDING
        return _ReaderFinalizerResult(
            _refusal("PS-MSG-REAP", "unreaped"), child, stdin, stdout, tuple(errors)
        )

    async def finalize(self) -> Refusal | None:
        if self._state is ReaderState.REAPED:
            return None
        if self._state is ReaderState.SPAWN_FAILED:
            return None
        if self._attempts_used >= OBJECT_REAP_MAX_ATTEMPTS:
            return _refusal("PS-MSG-REAP", "unreaped")
        if self._finalizer_task is None or self._finalizer_task.done():
            self._finalizer_task = asyncio.create_task(self._drive_finalizer())
        task = self._finalizer_task
        caller_cancelled = False
        try:
            result = await asyncio.shield(task)
        except asyncio.CancelledError:
            caller_cancelled = True
            try:
                result = await asyncio.shield(task)
            except asyncio.CancelledError:
                result = await task
        task_tick = asyncio.get_running_loop().time()
        task_identity = f"task:{id(task)}"
        finalizer = FinalizerObservation(
            task_identity, task.done() and not task.cancelled(), task.cancelled(),
            task.exception() is not None if task.done() and not task.cancelled() else False,
            task_tick,
        )
        participant_max = max(
            result.child.observed_at_monotonic_tick,
            result.stdin.observed_at_monotonic_tick,
            result.stdout.observed_at_monotonic_tick,
            finalizer.observed_at_monotonic_tick,
        )
        verified_tick = max(asyncio.get_running_loop().time(), participant_max + 1e-9)
        certificate = ReaderReapCertificate(
            self._session_id, self._attempts_used, result.child.identity, task_identity,
            result.child, result.stdin, result.stdout, finalizer, result.cleanup_errors,
            verified_tick, ReaderState.REAPED,
        )
        if certificate.complete:
            self._state = ReaderState.REAPED
            self._reap_certificate = certificate
        else:
            self._state = ReaderState.REAP_PENDING
        if caller_cancelled:
            return _refusal("PS-MSG-READ", "cancelled")
        return result.refusal if self._state is not ReaderState.REAPED else None


ObjectReaderSession = _AsyncGitObjectReader


def _decode_commit_message(raw: bytes) -> DecodedMessage | Refusal:
    separator = raw.find(b"\n\n")
    if separator < 0:
        return _refusal("PS-MSG-FRAME", "commit-separator")
    headers = raw[:separator].splitlines()
    message = raw[separator + 2:]
    if len(message) > _MAX_MESSAGE_BYTES:
        return _refusal("PS-MSG-LIMIT", "message")
    declared: bytes | None = None
    for header in headers:
        if header.lower().startswith(b"encoding "):
            if declared is not None:
                return _refusal("PS-MSG-DECODE", "encoding")
            declared = header[9:].strip().lower()
    if declared not in (None, b"utf-8", b"utf8"):
        return _refusal("PS-MSG-DECODE", "encoding")
    try:
        return DecodedMessage(message.decode("utf-8", "strict"), len(message))
    except UnicodeDecodeError:
        return _refusal("PS-MSG-DECODE", "utf8")


def _decode_commit_record(
    raw: bytes,
    object_format: GitObjectFormat = _SHA1_OBJECT_FORMAT,
) -> CommitRecord | Refusal:
    decoded = _decode_commit_message(raw)
    if isinstance(decoded, Refusal):
        return decoded
    separator = raw.find(b"\n\n")
    headers = raw[:separator].splitlines()
    trees: list[str] = []
    parents: list[str] = []
    for header in headers:
        if header.startswith(b"tree "):
            target = trees
            value = header[5:]
        elif header.startswith(b"parent "):
            target = parents
            value = header[7:]
        else:
            continue
        try:
            oid = value.decode("ascii").lower()
        except UnicodeDecodeError:
            return _refusal("PS-MSG-FRAME", "commit-header")
        if not object_format.matches(oid):
            return _refusal("PS-MSG-FRAME", "commit-header")
        target.append(oid)
    if len(trees) != 1:
        return _refusal("PS-MSG-FRAME", "commit-tree")
    return CommitRecord(trees[0], tuple(parents), decoded)


def _parse_tree(
    raw: bytes,
    object_format: GitObjectFormat = _SHA1_OBJECT_FORMAT,
) -> tuple[TreeEntry, ...] | Refusal:
    entries: list[TreeEntry] = []
    offset = 0
    while offset < len(raw):
        space = raw.find(b" ", offset)
        nul = raw.find(b"\0", space + 1 if space >= 0 else offset)
        oid_end = nul + 1 + object_format.raw_length
        if space <= offset or nul <= space + 1 or oid_end > len(raw):
            return _refusal("PS-MSG-FRAME", "tree")
        mode = raw[offset:space]
        name = raw[space + 1:nul]
        raw_oid = raw[nul + 1:oid_end]
        if b"/" in name or not name:
            return _refusal("PS-MSG-FRAME", "tree-path")
        if mode in {b"100644", b"100755", b"120000"}:
            kind = "blob"
        elif mode in {b"40000", b"040000"}:
            kind = "tree"
        elif mode == b"160000":
            kind = "gitlink"
        else:
            return _refusal("PS-MSG-FRAME", "tree-mode")
        entries.append(TreeEntry(kind, name, raw_oid.hex()))
        offset = oid_end
    return tuple(entries)


def _line_limit_refusal(raw: bytes) -> Refusal | None:
    start = 0
    while True:
        end = raw.find(b"\n", start)
        if end < 0:
            return (
                _refusal("PS-MSG-LIMIT", "line-bytes")
                if len(raw) - start > _MAX_LINE_BYTES else None
            )
        if end - start > _MAX_LINE_BYTES:
            return _refusal("PS-MSG-LIMIT", "line-bytes")
        start = end + 1


def _append_findings(target: list[Finding], rows: Iterable[Finding]) -> None:
    remaining = _MAX_FINDINGS - len(target)
    if remaining > 0:
        target.extend(list(rows)[:remaining])


def _subject_set_digest(subjects: Iterable[tuple[str, bytes, str]]) -> str:
    rows = (
        _length_frame(commit.encode("ascii"))
        + _length_frame(path)
        + _length_frame(blob.encode("ascii"))
        for commit, path, blob in subjects
    )
    return _digest_frames(b"subject-set", rows)


def _path_set_digest(paths: Iterable[tuple[str, bytes]]) -> str:
    rows = (
        _length_frame(blob.encode("ascii")) + _length_frame(path)
        for blob, path in paths
    )
    return _digest_frames(b"path-set", rows)


def _confirm_tip(
    initial_tip: str,
    resolver: Callable[[float | None], str],
    timeout: float | None = None,
) -> Refusal | None:
    try:
        final_tip = resolver(timeout).lower()
    except Exception:
        return _refusal("PS-MSG-TIP-CHANGED", "destination")
    if final_tip != initial_tip:
        return _refusal("PS-MSG-TIP-CHANGED", "destination")
    return None


def _build_coverage_proof(
    expected_oids: Iterable[str],
    requested_oids: Iterable[str],
    acquired_oids: Iterable[str],
    scanned_message_oids: Iterable[str],
) -> CoverageProof | Refusal:
    expected = tuple(expected_oids)
    requested = tuple(requested_oids)
    acquired = tuple(acquired_oids)
    scanned = tuple(scanned_message_oids)
    expected_counter = Counter(expected)
    requested_counter = Counter(requested)
    acquired_counter = Counter(acquired)
    scanned_counter = Counter(scanned)
    exact = Counter({oid: 1 for oid in expected})
    if (
        not expected
        or
        expected_counter != exact
        or requested_counter != exact
        or acquired_counter != exact
        or scanned_counter != exact
        or not (len(expected) == len(requested) == len(acquired) == len(scanned))
    ):
        return _refusal("PS-MSG-COVERAGE", "multiplicity")
    coverage_digest = hashlib.sha256(
        b"publication-safety-coverage-v1\0"
        + b"\0".join(oid.encode("ascii") for oid in scanned)
    ).hexdigest()
    counter_rows = lambda value: tuple(sorted(value.items()))
    return CoverageProof(
        expected, requested, acquired, scanned,
        counter_rows(expected_counter), counter_rows(requested_counter),
        counter_rows(acquired_counter), counter_rows(scanned_counter),
        len(expected), len(requested), len(acquired), len(scanned),
        coverage_digest,
    )


def _finalize_range_outcome(
    pending: ScanOutcome,
    finalization: Refusal | None,
    certificate: ReaderReapCertificate | None = None,
) -> ScanOutcome:
    if finalization is not None:
        return ScanOutcome(
            "refusal",
            "range",
            refusal=finalization,
            selection=pending.selection,
        )
    if certificate is None:
        if pending.kind == "refusal" and pending.refusal is not None and pending.refusal.failure_id in {
            "PS-MSG-RANGE", "PS-MSG-SPAWN", "PS-MSG-COVERAGE"
        }:
            return pending
        return ScanOutcome(
            "refusal", "range",
            refusal=_refusal("PS-MSG-REAP", "certificate"),
            selection=pending.selection,
        )
    if not certificate.complete:
        return ScanOutcome(
            "refusal", "range",
            refusal=_refusal("PS-MSG-REAP", "certificate"),
            selection=pending.selection,
        )
    return replace(pending, reap_certificate=certificate)


async def _finalize_reader(reader: _AsyncGitObjectReader) -> Refusal | None:
    """Reap one owned reader without allowing cleanup errors to escape."""
    try:
        return await reader.finalize()
    except asyncio.CancelledError:
        return _refusal("PS-MSG-REAP", "cancelled")
    except Exception:
        return _refusal("PS-MSG-REAP", "unexpected")


def _tree_traversal_guard(
    *,
    deadline: float,
    frontier: int,
    visits: int,
    visited: int,
    cache_entries: int,
) -> Refusal | None:
    if asyncio.get_running_loop().time() >= deadline:
        return _refusal("PS-MSG-READ-TIMEOUT", "deadline")
    if frontier > _MAX_TREE_FRONTIER:
        return _refusal("PS-MSG-LIMIT", "tree-frontier")
    if visits > _MAX_TREE_VISITS:
        return _refusal("PS-MSG-LIMIT", "tree-visits")
    if visited > _MAX_TREE_CACHE_ENTRIES:
        return _refusal("PS-MSG-LIMIT", "tree-visited")
    if cache_entries > _MAX_TREE_CACHE_ENTRIES:
        return _refusal("PS-MSG-LIMIT", "tree-cache-count")
    return None


async def _acquire_history(
    selection: RangeSelection,
    reader: _AsyncGitObjectReader,
    find_machine_paths,
    coverage_recorder: CoverageRecorder,
    scan_deadline: float,
) -> tuple[HistoryProof, CoverageProof, tuple[Finding, ...]] | Refusal:
    commit_set = set(selection.expected_oids)
    object_types: dict[str, str] = {}
    commit_records: dict[str, CommitRecord] = {}
    tree_cache: dict[str, bytes] = {}
    blob_contents: dict[str, bytes] = {}
    findings: list[Finding] = []
    aggregate_messages = 0
    aggregate_blobs = 0
    aggregate_trees = 0

    for oid in selection.object_oids:
        if asyncio.get_running_loop().time() >= scan_deadline:
            return _refusal("PS-MSG-READ-TIMEOUT", "deadline")
        expected_type = "commit" if oid in commit_set else None
        if expected_type == "commit":
            coverage_recorder.record(CoverageEvent.REQUESTED, oid)
        result = await reader.read(
            oid, expected_type, scan_deadline=scan_deadline
        )
        if isinstance(result, Refusal):
            return result
        if result.returned_oid != oid:
            return _refusal("PS-MSG-COVERAGE", "object-identity")
        object_types[oid] = result.object_type
        if result.object_type == "commit":
            if oid not in commit_set:
                return _refusal("PS-MSG-COVERAGE", "unexpected-commit")
            coverage_recorder.record(CoverageEvent.ACQUIRED, result.returned_oid)
            record = _decode_commit_record(result.raw, selection.object_format)
            if isinstance(record, Refusal):
                return record
            aggregate_messages += record.message.raw_size
            if aggregate_messages > _MAX_AGGREGATE_MESSAGE_BYTES:
                return _refusal("PS-MSG-LIMIT", "aggregate-message-bytes")
            _append_findings(findings, _content_hits(
                record.message.text,
                oid,
                find_machine_paths,
                subject_kind="commit-message",
                max_findings=max(0, _MAX_FINDINGS - len(findings)),
            ))
            coverage_recorder.record(CoverageEvent.SCANNED, oid)
            commit_records[oid] = record
        elif result.object_type == "tree":
            aggregate_trees += len(result.raw)
            if aggregate_trees > _MAX_TREE_CACHE_BYTES:
                return _refusal("PS-MSG-LIMIT", "tree-cache-bytes")
            tree_cache[oid] = result.raw
        elif result.object_type == "blob":
            if len(blob_contents) >= _MAX_BLOBS:
                return _refusal("PS-MSG-LIMIT", "blob-count")
            aggregate_blobs += len(result.raw)
            if aggregate_blobs > _MAX_AGGREGATE_BLOB_BYTES:
                return _refusal("PS-MSG-LIMIT", "aggregate-blob-bytes")
            blob_contents[oid] = result.raw
        else:
            return _refusal("PS-MSG-FRAME", "object-type")

    if tuple(object_types) != selection.object_oids:
        return _refusal("PS-MSG-COVERAGE", "object-set")
    if set(commit_records) != commit_set:
        return _refusal("PS-MSG-COVERAGE", "commit-set")
    if selection.expected_parents:
        expected_parents = dict(selection.expected_parents)
        if set(expected_parents) != commit_set:
            return _refusal("PS-MSG-COVERAGE", "parent-graph-set")
        if any(
            commit_records[oid].parents != expected_parents[oid]
            for oid in selection.expected_oids
        ):
            return _refusal("PS-MSG-COVERAGE", "parent-graph")
    coverage = coverage_recorder.proof()
    if isinstance(coverage, Refusal):
        return coverage

    async def load_tree(oid: str) -> bytes | Refusal:
        nonlocal aggregate_trees
        guard = _tree_traversal_guard(
            deadline=scan_deadline,
            frontier=0,
            visits=0,
            visited=0,
            cache_entries=len(tree_cache),
        )
        if guard is not None:
            return guard
        cached = tree_cache.get(oid)
        if cached is not None:
            return cached
        guard = _tree_traversal_guard(
            deadline=scan_deadline,
            frontier=0,
            visits=0,
            visited=0,
            cache_entries=len(tree_cache) + 1,
        )
        if guard is not None:
            return guard
        result = await reader.read(oid, "tree", scan_deadline=scan_deadline)
        if isinstance(result, Refusal):
            return result
        aggregate_trees += len(result.raw)
        if aggregate_trees > _MAX_TREE_CACHE_BYTES:
            return _refusal("PS-MSG-LIMIT", "tree-cache-bytes")
        tree_cache[oid] = result.raw
        return result.raw

    unpublished_trees = {
        oid for oid, object_type in object_types.items() if object_type == "tree"
    }
    unpublished_blobs = set(blob_contents)
    reached_unpublished_trees: set[str] = set()
    visited_tree_ids: set[str] = set()
    tree_visits = 0
    subjects: list[tuple[str, bytes, str]] = []
    subject_set: set[tuple[str, bytes, str]] = set()
    for commit_oid in selection.expected_oids:
        guard = _tree_traversal_guard(
            deadline=scan_deadline,
            frontier=0,
            visits=tree_visits,
            visited=len(visited_tree_ids),
            cache_entries=len(tree_cache),
        )
        if guard is not None:
            return guard
        root_tree = commit_records[commit_oid].root_tree
        stack: list[tuple[str, bytes, tuple[str, ...]]] = [(root_tree, b"", ())]
        while stack:
            next_tree_oid = stack[-1][0]
            guard = _tree_traversal_guard(
                deadline=scan_deadline,
                frontier=len(stack),
                visits=tree_visits + 1,
                visited=len(visited_tree_ids) + (next_tree_oid not in visited_tree_ids),
                cache_entries=len(tree_cache),
            )
            if guard is not None:
                return guard
            tree_oid, prefix, ancestors = stack.pop()
            tree_visits += 1
            visited_tree_ids.add(tree_oid)
            if tree_oid in ancestors:
                return _refusal("PS-MSG-FRAME", "tree-cycle")
            raw_tree = await load_tree(tree_oid)
            if isinstance(raw_tree, Refusal):
                return raw_tree
            if tree_oid in unpublished_trees:
                reached_unpublished_trees.add(tree_oid)
            entries = _parse_tree(raw_tree, selection.object_format)
            if isinstance(entries, Refusal):
                return entries
            for entry in reversed(entries):
                guard = _tree_traversal_guard(
                    deadline=scan_deadline,
                    frontier=len(stack),
                    visits=tree_visits,
                    visited=len(visited_tree_ids),
                    cache_entries=len(tree_cache),
                )
                if guard is not None:
                    return guard
                path = prefix + (b"/" if prefix else b"") + entry.name
                if len(path) > _MAX_PATH_BYTES:
                    return _refusal("PS-MSG-LIMIT", "path-bytes")
                if entry.kind == "tree":
                    guard = _tree_traversal_guard(
                        deadline=scan_deadline,
                        frontier=len(stack) + 1,
                        visits=tree_visits,
                        visited=len(visited_tree_ids),
                        cache_entries=len(tree_cache),
                    )
                    if guard is not None:
                        return guard
                    stack.append((entry.oid, path, ancestors + (tree_oid,)))
                elif entry.kind == "blob" and entry.oid in unpublished_blobs:
                    subject = (commit_oid, path, entry.oid)
                    if subject in subject_set:
                        return _refusal("PS-MSG-COVERAGE", "duplicate-subject")
                    subject_set.add(subject)
                    subjects.append(subject)
                    if len(subjects) > _MAX_SUBJECTS:
                        return _refusal("PS-MSG-LIMIT", "subject-count")

    if reached_unpublished_trees != unpublished_trees:
        return _refusal("PS-MSG-COVERAGE", "tree-subjects")
    if {blob for _commit, _path, blob in subjects} != unpublished_blobs:
        return _refusal("PS-MSG-COVERAGE", "blob-subjects")
    blob_paths = {(path, blob) for _commit, path, blob in subjects}
    if len(blob_paths) > _MAX_BLOB_PATHS:
        return _refusal("PS-MSG-LIMIT", "blob-path-count")

    binary_blobs = {oid for oid, raw in blob_contents.items() if _is_binary(raw)}
    text_blobs = set(blob_contents) - binary_blobs
    for path, blob_oid in sorted(blob_paths):
        decoded_path = path.decode("utf-8", "surrogateescape")
        _append_findings(
            findings, _filename_findings(decoded_path, "history-blob")
        )
        raw = blob_contents[blob_oid]
        line_refusal = _line_limit_refusal(raw)
        if line_refusal is not None:
            return line_refusal
        _append_findings(findings, _content_hits(
            raw.decode("utf-8", "replace"),
            decoded_path,
            find_machine_paths,
            subject_kind="history-blob",
            max_findings=max(0, _MAX_FINDINGS - len(findings)),
        ))

    canonical_subjects = tuple(sorted(subjects))
    canonical_paths = tuple(sorted((blob, path) for path, blob in blob_paths))
    canonical_objects = tuple(sorted(selection.object_oids))
    canonical_blobs = tuple(sorted(blob_contents))
    proof = HistoryProof(
        selection.expected_oids,
        canonical_objects,
        canonical_blobs,
        aggregate_blobs,
        len(text_blobs),
        len(binary_blobs),
        canonical_subjects,
        canonical_paths,
        _commit_set_digest(selection.expected_oids),
        _oid_set_digest(b"object-set", canonical_objects),
        _oid_set_digest(b"blob-set", canonical_blobs),
        _subject_set_digest(canonical_subjects),
        _path_set_digest(canonical_paths),
    )
    return proof, coverage, tuple(findings)


async def _scan_range_async(
    remote: str,
    destination: str,
    find_machine_paths,
    *,
    source_revision: str | None = None,
    tip_resolver: Callable[[float | None], str] | None = None,
    reader_factory: Callable[[], _AsyncGitObjectReader] = _AsyncGitObjectReader,
    coverage_observer: Callable[[CoverageEvent, str], None] | None = None,
    coverage_fault: CoverageFaultPort | None = None,
    scan_timeout: float = _SCAN_DEADLINE_SECONDS,
) -> ScanOutcome:
    wall_deadline = time.monotonic() + scan_timeout
    request = _range_request(remote, destination, source_revision)
    if isinstance(request, Refusal):
        return ScanOutcome("refusal", "range", refusal=request)
    selection = await _range_selection(request, wall_deadline)
    if isinstance(selection, Refusal):
        return ScanOutcome("refusal", "range", refusal=selection)
    if not selection.expected_oids:
        return ScanOutcome(
            "refusal", "range",
            refusal=_refusal("PS-MSG-COVERAGE", "empty-selection"),
            selection=selection,
        )
    coverage_recorder = CoverageRecorder(
        selection.expected_oids, coverage_observer, coverage_fault
    )
    pending: ScanOutcome | None = None
    acquired: tuple[
        HistoryProof, CoverageProof, tuple[Finding, ...]
    ] | None = None
    reader: _AsyncGitObjectReader | None = None

    if selection.object_oids:
        reader = reader_factory()
        try:
            start_refusal = await reader.start()
            if start_refusal is not None:
                pending = ScanOutcome(
                    "refusal", "range", refusal=start_refusal, selection=selection
                )
            else:
                loop = asyncio.get_running_loop()
                remaining = wall_deadline - time.monotonic()
                if remaining <= 0:
                    acquisition = _refusal("PS-MSG-READ-TIMEOUT", "deadline")
                else:
                    acquisition = await _acquire_history(
                        selection,
                        reader,
                        find_machine_paths,
                        coverage_recorder,
                        loop.time() + remaining,
                    )
                if isinstance(acquisition, Refusal):
                    pending = ScanOutcome(
                        "refusal", "range", refusal=acquisition, selection=selection
                    )
                else:
                    acquired = acquisition
        except asyncio.CancelledError:
            pending = ScanOutcome(
                "refusal", "range",
                refusal=_refusal("PS-MSG-READ", "cancelled"),
                selection=selection,
            )
        except Exception:
            pending = ScanOutcome(
                "refusal", "range",
                refusal=_refusal("PS-MSG-READ", "unexpected"),
                selection=selection,
            )

    if reader is None:
        certificate = None
        finalization = None
    else:
        finalization = await _finalize_reader(reader)
        if (
            finalization is not None
            and finalization.failure_id == "PS-MSG-REAP"
            and reader.state is ReaderState.REAP_PENDING
        ):
            finalization = await _finalize_reader(reader)
        certificate = reader.reap_certificate

    if acquired is not None and finalization is None:
        history, coverage, findings = acquired
        try:
            resolver = tip_resolver or (
                lambda timeout=None: _resolve_commit(
                    request.source,
                    timeout,
                    object_format=selection.object_format,
                )
            )
            drift = _confirm_tip(
                selection.tip,
                resolver,
                max(0.001, wall_deadline - time.monotonic()),
            )
        except Exception:
            pending = ScanOutcome(
                "refusal", "range",
                refusal=_refusal("PS-MSG-READ", "unexpected"),
                selection=selection,
            )
        else:
            if drift is not None:
                pending = ScanOutcome(
                    "refusal", "range", refusal=drift, selection=selection
                )
            elif findings:
                pending = ScanOutcome(
                    "findings", "range", file_count=len(history.paths),
                    findings=tuple(findings), selection=selection,
                    coverage=coverage, history=history,
                )
            else:
                pending = ScanOutcome(
                    "clean", "range", file_count=len(history.paths),
                    selection=selection,
                    coverage=coverage, history=history,
                )

    if pending is None:
        pending = ScanOutcome(
            "refusal", "range",
            refusal=_refusal("PS-MSG-COVERAGE", "empty-selection"),
            selection=selection,
        )
    return _finalize_range_outcome(pending, finalization, certificate)


def _scan_range(
    remote: str,
    destination: str,
    find_machine_paths,
    *,
    source_revision: str | None = None,
    tip_resolver: Callable[[float | None], str] | None = None,
) -> ScanOutcome:
    try:
        return asyncio.run(_scan_range_async(
            remote,
            destination,
            find_machine_paths,
            source_revision=source_revision,
            tip_resolver=tip_resolver,
        ))
    except KeyboardInterrupt:
        return ScanOutcome(
            "refusal", "range",
            refusal=_refusal("PS-MSG-READ", "cancelled"),
        )
    except Exception:
        return ScanOutcome(
            "refusal", "range",
            refusal=_refusal("PS-MSG-READ", "unexpected"),
        )


def _encode_receipt_token(value: str) -> str:
    if not value or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("receipt token")
    return quote(value, safe="-._~", encoding="utf-8", errors="strict")


def _serialize_range_receipt_v3(
    history: HistoryProof,
    remote: str,
    destination: str,
    source: str,
    tip: str,
    *,
    object_format: GitObjectFormat = _SHA1_OBJECT_FORMAT,
) -> str:
    if not history.commit_ids or not history.object_ids:
        raise ValueError("non-empty receipt")
    if (
        history.text_blobs + history.binary_blobs != len(history.blob_ids)
        or history.blob_bytes < 0
        or not object_format.matches(tip)
    ):
        raise ValueError("receipt fields")
    receipt = RangeReceiptV3(
        len(history.commit_ids),
        history.commit_set,
        len(history.object_ids),
        history.object_set,
        len(history.blob_ids),
        history.blob_set,
        history.blob_bytes,
        history.text_blobs,
        history.binary_blobs,
        len(history.subjects),
        history.subject_set,
        len(history.paths),
        history.path_set,
        _encode_receipt_token(remote),
        _encode_receipt_token(destination),
        _encode_receipt_token(source),
        tip,
    )
    return (
        "publication-safety: clean (range, receipt=v3, "
        f"commits={receipt.commits}, "
        f"commit-set={receipt.commit_set}, messages=complete, "
        f"objects={receipt.objects}, object-set={receipt.object_set}, "
        f"blobs={receipt.blobs}, blob-set={receipt.blob_set}, "
        f"blob-bytes={receipt.blob_bytes}, text={receipt.text}, "
        f"binary={receipt.binary}, subjects={receipt.subjects}, "
        f"subject-set={receipt.subject_set}, paths={receipt.paths}, "
        f"path-set={receipt.path_set}, history=complete, "
        f"remote={receipt.remote}, dst={receipt.destination}, "
        f"src={receipt.source}, tip={receipt.tip})"
    )


def _path_files(raw_path: str) -> tuple[list[str], dict[str, bytes]]:
    source = Path(raw_path)
    paths = sorted(p for p in source.rglob("*") if p.is_file()) if source.is_dir() else [source]
    blobs: dict[str, bytes] = {}
    labels: list[str] = []
    for path in paths:
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise RuntimeError(f"could not read path content for {str(path)!r}") from exc
        label = str(path)
        labels.append(label)
        blobs[label] = raw
    return labels, blobs


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan publication content for secrets and machine-local paths."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--path")
    group.add_argument("--range", nargs=2, metavar=("REMOTE", "DST"))
    parser.add_argument("--range-source", metavar="REVISION")
    parser.add_argument("legacy_path", nargs="?")
    return parser


def _filename_findings(path: str, subject_kind: str) -> list[Finding]:
    base = Path(path).name
    locator = _safe_locator(path, subject_kind)
    if base == ".env":
        return [Finding("PS-FINDING-CONTENT", subject_kind, locator, 1, "filename-env")]
    if base.casefold() == "secret.md":
        return [Finding("PS-FINDING-CONTENT", subject_kind, locator, 1, "filename-secret")]
    return []


def _scan_content_blobs(
    mode: str,
    paths: list[str],
    blobs: dict[str, bytes],
    find_machine_paths,
) -> ScanOutcome:
    findings: list[Finding] = []
    subject_kind = "path-blob" if mode == "path" else "tracked-blob"
    for path in paths:
        findings.extend(_filename_findings(path, subject_kind))
        raw = blobs[path]
        if _is_binary(raw):
            continue
        findings.extend(_content_hits(
            raw.decode("utf-8", "replace"),
            path,
            find_machine_paths,
            subject_kind=subject_kind,
        ))
    return ScanOutcome(
        "findings" if findings else "clean",
        mode,
        file_count=len(paths),
        findings=tuple(findings),
    )


def _format_outcome(outcome: ScanOutcome) -> tuple[str, str, int]:
    if outcome.kind == "refusal":
        refusal = outcome.refusal or _refusal("PS-INPUT-REFUSAL", "unexpected")
        return (
            "",
            f"publication-safety: refusing id={refusal.failure_id} "
            f"reason={refusal.reason} phase={refusal.phase}",
            2,
        )
    if outcome.kind == "findings":
        lines: list[str] = []
        for finding in outcome.findings:
            if finding.subject_kind == "commit-message":
                lines.append(
                    f"{finding.failure_id} kind=commit-message field=message "
                    f"line={finding.line} class={finding.detector_class}"
                )
            else:
                lines.append(
                    f"{finding.failure_id} kind={finding.subject_kind} "
                    f"line={finding.line} class={finding.detector_class}"
                )
        lines.append("publication-safety scan found potential tracked-content leak markers")
        return "", "\n".join(lines), 1
    if outcome.mode == "range":
        selection = outcome.selection
        coverage = outcome.coverage
        certificate = outcome.reap_certificate
        history = outcome.history
        if (
            selection is None
            or coverage is None
            or certificate is None
            or not certificate.complete
            or history is None
        ):
            return (
                "",
                "publication-safety: refusing id=PS-INPUT-REFUSAL "
                "phase=input reason=unexpected",
                2,
            )
        if not coverage.scanned_message_oids:
            return (
                "",
                "publication-safety: refusing id=PS-MSG-COVERAGE "
                "reason=empty-selection phase=coverage",
                2,
            )
        try:
            return (
                _serialize_range_receipt_v3(
                    history,
                    selection.remote,
                    selection.destination,
                    selection.source,
                    selection.tip,
                    object_format=selection.object_format,
                ),
                "",
                0,
            )
        except (ValueError, UnicodeError):
            return (
                "",
                "publication-safety: refusing id=PS-INPUT-REFUSAL "
                "phase=input reason=receipt",
                2,
            )
    count = outcome.file_count
    noun = "file" if count == 1 else "files"
    if count == 0 and outcome.mode == "tracked":
        return "publication-safety: clean (tracked, examined 0 files -- nothing staged)", "", 0
    return f"publication-safety: clean ({outcome.mode}, examined {count} {noun})", "", 0


def _emit_outcome(outcome: ScanOutcome) -> int:
    stdout, stderr, exit_code = _format_outcome(outcome)
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)
    return exit_code


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.legacy_path and (args.path or args.range):
        _parser().error("unexpected extra path argument")
    if args.range_source is not None and not args.range:
        _parser().error("--range-source requires --range")
    script = Path(__file__).resolve()
    try:
        repo_root = _repo_root()
        os.chdir(repo_root)
        find_machine_paths = _path_finder(script)
        if args.range:
            remote, dst = args.range
            return _emit_outcome(_scan_range(
                remote,
                dst,
                find_machine_paths,
                source_revision=args.range_source,
            ))
        elif args.path or args.legacy_path:
            mode = "path"
            paths, blobs = _path_files(args.path or args.legacy_path)
        else:
            mode = "tracked"
            paths, blobs = _tracked_files()
        return _emit_outcome(_scan_content_blobs(mode, paths, blobs, find_machine_paths))
    except KeyboardInterrupt:
        print(
            "publication-safety: refusing id=PS-INPUT-REFUSAL "
            "phase=input reason=cancelled",
            file=sys.stderr,
        )
        return 2
    except RuntimeError as exc:
        if exc.args == ("not inside a git repository",):
            print(
                "publication-safety: refusing id=PS-INPUT-REFUSAL "
                "phase=input reason=not inside a git repository",
                file=sys.stderr,
            )
        else:
            print(
                "publication-safety: refusing id=PS-INPUT-REFUSAL "
                "phase=input reason=unexpected",
                file=sys.stderr,
            )
        return 2
    except Exception:
        print(
            "publication-safety: refusing id=PS-INPUT-REFUSAL "
            "phase=input reason=unexpected",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
