#!/usr/bin/env python3
"""Fail-closed publication-safety scanner for tracked, range, and path inputs."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from enum import Enum
import hashlib
import os
import re
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import quote


SCANNER_BASENAME = "check-publication-safety.py"
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

_OID_RE = re.compile(r"[0-9a-f]{40}")
_MAX_COMMITS = 10_000
_MAX_MESSAGE_BYTES = 1_048_576
_MAX_AGGREGATE_MESSAGE_BYTES = 16_777_216
_RECEIPT_DOMAIN = b"publication-safety-range-receipt-v2"
_OBJECT_REQUEST_TIMEOUT_SECONDS = 5.0
OBJECT_REAP_ATTEMPT_SECONDS = 3.0
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
class RangeSelection:
    remote: str
    destination: str
    tip: str
    expected_oids: tuple[str, ...]
    changed_paths: tuple[str, ...]


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
            and self.verified_at_monotonic_tick > max(participant_ticks)
        )


ReapCertificate = ReaderReapCertificate


@dataclass(frozen=True)
class DecodedMessage:
    text: str
    raw_size: int


@dataclass(frozen=True)
class RangeReceiptV2:
    files: int
    commits: int
    commit_set: str
    remote: str
    destination: str
    tip: str


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


def _run_git(args: list[str], *, text: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
    )


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
) -> list[Finding]:
    findings: list[Finding] = []
    scanner = subject_kind != "commit-message" and Path(path).name == SCANNER_BASENAME
    locator = _safe_locator(path, subject_kind)
    for line_number, line in enumerate(text.splitlines(), 1):
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
                    break
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


def _canonical_commit_ids(rows: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in rows:
        oid = raw.strip().lower()
        if not _OID_RE.fullmatch(oid):
            raise ValueError("frame: malformed oid")
        if oid in seen:
            raise ValueError("frame: duplicate oid")
        seen.add(oid)
        result.append(oid)
        if len(result) > _MAX_COMMITS:
            raise ValueError("limit: commit count")
    return tuple(result)


def _commit_set_digest(commit_ids: Iterable[str]) -> str:
    canonical = [value.lower() for value in commit_ids]
    framed = _RECEIPT_DOMAIN + b"\0" + b"\0".join(
        value.encode("ascii") for value in canonical
    )
    return hashlib.sha256(framed).hexdigest()


def _resolve_head() -> str:
    proc = _run_git(["rev-parse", "--verify", "HEAD^{commit}"], text=True)
    if proc.returncode:
        raise ValueError("head")
    oid = proc.stdout.strip().lower()
    if not _OID_RE.fullmatch(oid):
        raise ValueError("head")
    return oid


def _range_selection(remote: str, destination: str) -> RangeSelection | Refusal:
    remotes = _run_git(["remote"], text=True)
    configured = [line for line in remotes.stdout.splitlines() if line]
    if remotes.returncode or remote not in configured:
        return _refusal("PS-MSG-RANGE", "remote")
    if not destination:
        return _refusal("PS-MSG-RANGE", "destination")
    try:
        tip = _resolve_head()
    except (OSError, ValueError):
        return _refusal("PS-MSG-RANGE", "head")
    commits = _run_git(
        ["rev-list", "--topo-order", tip, "--not", f"--remotes={remote}"],
        text=True,
    )
    if commits.returncode:
        return _refusal("PS-MSG-RANGE", "selection")
    try:
        commit_ids = _canonical_commit_ids(commits.stdout.splitlines())
    except ValueError as exc:
        failure_id = "PS-MSG-LIMIT" if str(exc).startswith("limit:") else "PS-MSG-FRAME"
        return _refusal(failure_id, "count" if failure_id.endswith("LIMIT") else "oid")
    paths: dict[str, None] = {}
    for oid in commit_ids:
        names = _run_git(
            ["diff-tree", "--root", "--no-commit-id", "--name-only", "-r", "-z", oid]
        )
        if names.returncode:
            return _refusal("PS-MSG-RANGE", "paths")
        for raw in names.stdout.split(b"\0"):
            if raw:
                paths[raw.decode("utf-8", "surrogateescape")] = None
    return RangeSelection(
        remote,
        destination,
        tip,
        commit_ids,
        tuple(paths),
    )


def _parse_batch_header(
    header: bytes, expected_oid: str, expected_type: str
) -> int | Refusal:
    expected = expected_oid.encode("ascii")
    if header == expected + b" missing":
        return _refusal("PS-MSG-READ", "missing")
    parts = header.split(b" ")
    if len(parts) != 3:
        return _refusal("PS-MSG-FRAME", "header")
    raw_oid, raw_type, raw_length = parts
    if raw_oid != expected or raw_type != expected_type.encode("ascii"):
        return _refusal("PS-MSG-FRAME", "identity")
    try:
        length = int(raw_length)
    except ValueError:
        return _refusal("PS-MSG-FRAME", "length")
    if length < 0:
        return _refusal("PS-MSG-FRAME", "length")
    return length


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
        argv: tuple[str, ...] = ("git", "cat-file", "--batch"),
        request_timeout: float = _OBJECT_REQUEST_TIMEOUT_SECONDS,
        settle_timeout: float = OBJECT_REAP_ATTEMPT_SECONDS,
    ) -> None:
        self._argv = argv
        self._request_timeout = request_timeout
        self._settle_timeout = settle_timeout
        self._process: asyncio.subprocess.Process | None = None
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
            self._process = await asyncio.create_subprocess_exec(
                *self._argv,
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

    async def read(self, oid: str, expected_type: str) -> ObjectReadSuccess | Refusal:
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
        try:
            process.stdin.write(oid.encode("ascii") + b"\n")
            await self._within(process.stdin.drain(), deadline)
            header = await self._within(process.stdout.readline(), deadline)
            if not header.endswith(b"\n"):
                self._poisoned = True
                return _refusal("PS-MSG-FRAME", "header-delimiter")
            length = _parse_batch_header(header[:-1], oid, expected_type)
            if isinstance(length, Refusal):
                self._poisoned = True
                return length
            raw = await self._within(process.stdout.readexactly(length), deadline)
            delimiter = await self._within(process.stdout.readexactly(1), deadline)
            if delimiter != b"\n":
                self._poisoned = True
                return _refusal("PS-MSG-FRAME", "record-delimiter")
            return ObjectReadSuccess(oid, oid, expected_type, raw)
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

    async def _wait_step(self, deadline: float, errors: list[str], phase: str) -> bool:
        process = self._process
        if process is None:
            return True
        try:
            await self._within(process.wait(), deadline)
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
        terminal = await self._wait_step(deadline, errors, "wait")
        if not terminal:
            try:
                process.terminate()
            except Exception:
                errors.append("terminate")
            terminal = await self._wait_step(deadline, errors, "terminate-wait")
        if not terminal:
            try:
                process.kill()
            except Exception:
                errors.append("kill")
            terminal = await self._wait_step(deadline, errors, "kill-wait")
        child = ChildObservation(
            child_identity,
            process.returncode,
            terminal and process.returncode is not None,
            loop.time(),
        )
        if process.stdout is not None and child.terminal_observed:
            try:
                trailing = await self._within(process.stdout.read(), deadline)
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


def _tip_blob_ids(selection: RangeSelection) -> dict[str, str] | Refusal:
    tree = _run_git(["ls-tree", "-r", "-z", "--full-tree", selection.tip])
    if tree.returncode:
        return _refusal("PS-MSG-READ", "tree")
    candidates = set(selection.changed_paths)
    result: dict[str, str] = {}
    for record in tree.stdout.split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode, object_type, raw_oid = metadata.split(b" ", 2)
            path = raw_path.decode("utf-8", "surrogateescape")
            oid = raw_oid.decode("ascii").lower()
        except (ValueError, UnicodeError):
            return _refusal("PS-MSG-FRAME", "tree")
        if path not in candidates:
            continue
        if object_type != b"blob" or not _OID_RE.fullmatch(oid) or not mode:
            return _refusal("PS-MSG-FRAME", "tree")
        result[path] = oid
    return result


def _confirm_tip(initial_tip: str, resolver: Callable[[], str] = _resolve_head) -> Refusal | None:
    try:
        final_tip = resolver().lower()
    except Exception:
        return _refusal("PS-MSG-TIP-CHANGED", "head")
    if final_tip != initial_tip:
        return _refusal("PS-MSG-TIP-CHANGED", "head")
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


async def _scan_range_async(
    remote: str,
    destination: str,
    find_machine_paths,
    *,
    head_resolver: Callable[[], str] = _resolve_head,
    reader_factory: Callable[[], _AsyncGitObjectReader] = _AsyncGitObjectReader,
    coverage_observer: Callable[[CoverageEvent, str], None] | None = None,
    coverage_fault: CoverageFaultPort | None = None,
) -> ScanOutcome:
    selection = _range_selection(remote, destination)
    if isinstance(selection, Refusal):
        return ScanOutcome("refusal", "range", refusal=selection)
    if not selection.expected_oids:
        return ScanOutcome(
            "refusal", "range",
            refusal=_refusal("PS-MSG-COVERAGE", "empty-selection"),
            selection=selection,
        )
    blob_ids = _tip_blob_ids(selection)
    if isinstance(blob_ids, Refusal):
        return ScanOutcome(
            "refusal", "range", refusal=blob_ids,
            selection=selection,
        )

    findings: list[Finding] = []
    coverage_recorder = CoverageRecorder(
        selection.expected_oids, coverage_observer, coverage_fault
    )
    aggregate = 0
    file_count = 0
    pending: ScanOutcome | None = None
    reader: _AsyncGitObjectReader | None = None

    if selection.expected_oids or blob_ids:
        reader = reader_factory()
        try:
            start_refusal = await reader.start()
            if start_refusal is not None:
                pending = ScanOutcome(
                    "refusal", "range", refusal=start_refusal, selection=selection
                )
            else:
                for oid in selection.expected_oids:
                    coverage_recorder.record(CoverageEvent.REQUESTED, oid)
                    result = await reader.read(oid, "commit")
                    if isinstance(result, Refusal):
                        pending = ScanOutcome(
                            "refusal", "range", refusal=result, selection=selection
                        )
                        break
                    coverage_recorder.record(CoverageEvent.ACQUIRED, result.returned_oid)
                    decoded = _decode_commit_message(result.raw)
                    if isinstance(decoded, Refusal):
                        pending = ScanOutcome(
                            "refusal", "range", refusal=decoded, selection=selection
                        )
                        break
                    aggregate += decoded.raw_size
                    if aggregate > _MAX_AGGREGATE_MESSAGE_BYTES:
                        pending = ScanOutcome(
                            "refusal", "range",
                            refusal=_refusal("PS-MSG-LIMIT", "aggregate"),
                            selection=selection,
                        )
                        break
                    findings.extend(_content_hits(
                        decoded.text,
                        oid,
                        find_machine_paths,
                        subject_kind="commit-message",
                    ))
                    coverage_recorder.record(CoverageEvent.SCANNED, oid)

                coverage: CoverageProof | Refusal | None = None
                if pending is None:
                    coverage = coverage_recorder.proof()
                    if isinstance(coverage, Refusal):
                        pending = ScanOutcome(
                            "refusal", "range", refusal=coverage, selection=selection
                        )

                if pending is None:
                    for path, oid in blob_ids.items():
                        result = await reader.read(oid, "blob")
                        if isinstance(result, Refusal):
                            pending = ScanOutcome(
                                "refusal", "range", refusal=result, selection=selection
                            )
                            break
                        if _is_binary(result.raw):
                            continue
                        file_count += 1
                        findings.extend(_content_hits(
                            result.raw.decode("utf-8", "replace"),
                            path,
                            find_machine_paths,
                            subject_kind="tip-blob",
                        ))

                if pending is None:
                    drift = _confirm_tip(selection.tip, head_resolver)
                    if drift is not None:
                        pending = ScanOutcome(
                            "refusal", "range", refusal=drift, selection=selection
                        )
                    elif findings:
                        pending = ScanOutcome(
                            "findings", "range", file_count=file_count,
                            findings=tuple(findings), selection=selection,
                            coverage=coverage if isinstance(coverage, CoverageProof) else None,
                        )
                    else:
                        pending = ScanOutcome(
                            "clean", "range", file_count=file_count,
                            selection=selection,
                            coverage=coverage if isinstance(coverage, CoverageProof) else None,
                        )
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

    if pending is None:
        pending = ScanOutcome(
            "refusal", "range",
            refusal=_refusal("PS-MSG-COVERAGE", "empty-selection"),
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
    return _finalize_range_outcome(pending, finalization, certificate)


def _scan_range(
    remote: str,
    destination: str,
    find_machine_paths,
    *,
    head_resolver: Callable[[], str] = _resolve_head,
) -> ScanOutcome:
    try:
        return asyncio.run(_scan_range_async(
            remote, destination, find_machine_paths, head_resolver=head_resolver
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


def _serialize_range_receipt_v2(
    files: int,
    commit_ids: Iterable[str],
    remote: str,
    destination: str,
    tip: str,
) -> str:
    commits = _canonical_commit_ids(commit_ids)
    if not commits:
        raise ValueError("non-empty receipt")
    if files < 0 or not _OID_RE.fullmatch(tip):
        raise ValueError("receipt fields")
    receipt = RangeReceiptV2(
        files,
        len(commits),
        _commit_set_digest(commits),
        _encode_receipt_token(remote),
        _encode_receipt_token(destination),
        tip,
    )
    return (
        "publication-safety: clean (range, receipt=v2, "
        f"files={receipt.files}, commits={receipt.commits}, "
        f"commit-set={receipt.commit_set}, messages=complete, "
        f"remote={receipt.remote}, dst={receipt.destination}, tip={receipt.tip})"
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
        if (
            selection is None
            or coverage is None
            or certificate is None
            or not certificate.complete
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
                _serialize_range_receipt_v2(
                    outcome.file_count,
                    coverage.scanned_message_oids,
                    selection.remote,
                    selection.destination,
                    selection.tip,
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
    script = Path(__file__).resolve()
    try:
        repo_root = _repo_root()
        os.chdir(repo_root)
        find_machine_paths = _path_finder(script)
        if args.range:
            remote, dst = args.range
            return _emit_outcome(_scan_range(remote, dst, find_machine_paths))
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
