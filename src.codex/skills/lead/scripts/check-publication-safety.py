#!/usr/bin/env python3
"""Fail-closed publication-safety scanner for tracked, range, and path inputs."""
from __future__ import annotations

import argparse
import asyncio
import base64
from collections import Counter
from enum import Enum
import hashlib
import importlib.util
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Iterable, Iterator
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
        and script.parents[2].name == "claude"
        and script.parents[3].name == "adapters"
    ):
        candidates.append(
            script.parents[4]
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


def _load_windows_job_module():
    module_name = "_orchestrarium_windows_job_v1"
    injected = globals().get("__injected_windows_job_module__")
    if injected is not None:
        if (
            getattr(injected, "__name__", None) != module_name
            or getattr(injected, "__file__", None)
            != "<closure>/process_supervision/windows_job.py"
            or sys.modules.get(module_name) is not injected
        ):
            raise RuntimeError("Windows Job injected contract mismatch")
        module = injected
    else:
        script = Path(__file__)
        if str(script).startswith("<closure>/"):
            raise RuntimeError("Windows Job held module unavailable")
        script = script.resolve()
        candidates = [script.parent / "process_supervision" / "windows_job.py"]
        if script.parent.name == "scripts" and script.parent.parent.name == "universal-hooks":
            candidates.append(script.parents[2] / "process_supervision" / "windows_job.py")
        elif (
            script.parents[0].name == "scripts"
            and script.parents[1].name == "lead"
            and script.parents[2].name == "skills"
            and script.parents[3].name == "src.codex"
        ):
            candidates.append(script.parents[4] / "scripts" / "process_supervision" / "windows_job.py")
        elif (
            script.parents[0].name == "scripts"
            and script.parents[1].name == "agents"
            and script.parents[2].name == "claude"
        and script.parents[3].name == "adapters"
        ):
            candidates.append(script.parents[4] / "scripts" / "process_supervision" / "windows_job.py")
        available = tuple(path for path in candidates if path.is_file())
        if len(available) != 1:
            raise RuntimeError("Windows Job helper unavailable or ambiguous")
        existing = sys.modules.get(module_name)
        if existing is not None:
            module = existing
        else:
            spec = importlib.util.spec_from_file_location(module_name, available[0])
            if spec is None or spec.loader is None:
                raise RuntimeError("Windows Job helper unavailable or ambiguous")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
            except BaseException:
                sys.modules.pop(module_name, None)
                raise
    try:
        marker = module.WINDOWS_JOB_MODULE_CONTRACT_V1
        owner_type = module.WindowsJobOwnerV1
        error_type = module.WindowsJobError
        contract = module.windows_job_module_contract_v1()
    except (AttributeError, TypeError):
        raise RuntimeError("Windows Job module contract mismatch") from None
    if (
        marker != "orchestrarium.windows-job.module.v1"
        or contract != (marker, owner_type, error_type)
        or not isinstance(owner_type, type)
        or not isinstance(error_type, type)
        or not issubclass(error_type, RuntimeError)
    ):
        raise RuntimeError("Windows Job module contract mismatch")
    return module


if os.name == "nt":
    _WINDOWS_JOB = _load_windows_job_module()
    WindowsJobOwnerV1 = _WINDOWS_JOB.WindowsJobOwnerV1
    WindowsJobError = _WINDOWS_JOB.WindowsJobError
    _WINDOWS_JOB_COORDINATOR = _WINDOWS_JOB.WindowsInheritanceCoordinatorV1()
else:
    class WindowsJobError(RuntimeError):
        """Non-Windows type placeholder for platform-neutral exception clauses."""


_SCANNER_EXEMPT_PATHS = frozenset({
    "scripts/universal-hooks/scripts/check-publication-safety.py",
    "src.codex/skills/lead/scripts/check-publication-safety.py",
    "adapters/claude/agents/scripts/check-publication-safety.py",
})
_SIMPLE_RULES = (
    (True, re.compile(r"AKIA[0-9A-Z]{16}")),
    (True, re.compile(r"ghp_[A-Za-z0-9]{36}")),
    (True, re.compile(r"sk-[A-Za-z0-9]{20,}")),
    (True, re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    (True, re.compile(r"ANTHROPIC_[A-Z_]*(?:KEY|TOKEN)[^A-Za-z0-9_]?\s*[:=]")),
    (True, re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+")),
    (True, re.compile(r"BEGIN RSA PRIVATE KEY")),
    (True, re.compile(r"BEGIN OPENSSH PRIVATE KEY")),
    (True, re.compile(r"BEGIN PRIVATE KEY")),
    (False, re.compile(r"private_key")),
    (False, re.compile(r"secret_key")),
    (True, re.compile(r"/private/var/folders/")),
    (True, re.compile(r"/var/folders/")),
    (False, re.compile(r"^Human:\s*")),
    (False, re.compile(r"^Assistant:\s*")),
    (False, re.compile(r"^\$\s+")),
    (False, re.compile(r"^>>>\s+")),
    (False, re.compile(r"\[[0-9]{2}:[0-9]{2}:[0-9]{2}\]")),
)
_BINARY_ASCII_RUN = re.compile(rb"[\x09\x20-\x7e]+")
_IDENTIFIER_PREFIX = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*(?:(?:::|[-._:/\\])[A-Za-z_][A-Za-z0-9_]*)*(?:::|[-._:/\\])?$"
)
_VALUE = r"[A-Za-z0-9_./+=-]"
_DIGIT_SHAPE = rf"(?:{_VALUE}{{5,}}[0-9]{_VALUE}*|{_VALUE}*[0-9]{_VALUE}{{5,}})"
_QUOTED = rf"""["'`!@#$%^&*?|](?:{_VALUE}{{12,}}|{_DIGIT_SHAPE})["'`!@#$%^&*?|]"""
_BARE = rf"(?:[A-Za-z0-9_+/=-]{{5,}}[0-9][A-Za-z0-9_+/=-]*|[A-Za-z0-9_+/=-]*[0-9][A-Za-z0-9_+/=-]{{5,}})"
_CALLABLE_RHS = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\s*\("
)
_PUBLIC_TOKEN_AUTH_CUE = "AUTH"
_PUBLIC_TOKEN_CREDENTIAL_CUES = (
    _PUBLIC_TOKEN_AUTH_CUE, "ACCESS", "API", "BEARER", "REFRESH", "SESSION", "OAUTH", "JWT",
    "CREDENTIAL", "SECRET", "IDENTITY", "CSRF", "PASSWORD",
)
_PUBLIC_TOKEN_ANNOTATED_LEXICAL_IDENTIFIERS = frozenset(
    {"accessibilitytoken", "authorshiptoken", "capitaltoken", "rapidtoken"}
)
_PUBLIC_TOKEN_LOWER_CREDENTIAL_STEMS = tuple(
    sorted(
        {
            *(cue.lower() for cue in _PUBLIC_TOKEN_CREDENTIAL_CUES),
            "authentication",
            "authorization",
            "authorisation",
        },
        key=lambda value: (-len(value), value),
    )
)
_PUBLIC_TOKEN_LOWER_CREDENTIAL_PREFIX_PATTERN = "|".join(
    re.escape(stem)
    for stem in _PUBLIC_TOKEN_LOWER_CREDENTIAL_STEMS
)
_PUBLIC_TOKEN_LOWER_CREDENTIAL_SUFFIX_PATTERN = "|".join(
    re.escape(stem) for stem in _PUBLIC_TOKEN_LOWER_CREDENTIAL_STEMS
)
_CONCATENATED_CREDENTIAL_TOKEN = re.compile(
    rf"(?<![A-Za-z0-9])(?P<credential_token_identifier>(?i:"
    rf"(?:(?:{_PUBLIC_TOKEN_LOWER_CREDENTIAL_PREFIX_PATTERN})[a-z0-9]*|"
    rf"[a-z0-9]*(?:{_PUBLIC_TOKEN_LOWER_CREDENTIAL_SUFFIX_PATTERN}))token))"
    rf"\s*[:=]\s*(?P<rhs_value>{_QUOTED}|{_BARE})"
)
_KEYWORDS = (
    ("password", r"password", "Password", "PASSWORD"),
    ("secret", r"secret", "Secret", "SECRET"),
    ("token", r"token", "Token", "TOKEN"),
    ("api-key", r"api[_-]?key", "ApiKey", "APIKEY"),
)
_VALUE_RULES = (("token", _CONCATENATED_CREDENTIAL_TOKEN),) + tuple(
    (
        family,
        re.compile(
            rf"(?:(?<![A-Za-z])(?i:{keyword})|(?<=[a-z]){title}|"
            rf"(?<=[A-Z]){title}|(?<=[A-Za-z]){upper})"
            rf"\s*[:=]\s*(?P<rhs_value>{_QUOTED}|{_BARE})",
        ),
    )
    for family, keyword, title, upper in _KEYWORDS
)
_VALUE_PATTERNS = tuple(pattern for _family, pattern in _VALUE_RULES)
_IDENTIFIER_COMPONENT = re.compile(
    r"[A-Z]+(?=[A-Z][a-z]|[0-9]|$)|[A-Z]?[a-z]+|[A-Z]+|[0-9]+"
)
_PUBLIC_TOKEN_ANNOTATION_SUFFIX = re.compile(
    r"[ \t,;)\]}]+(?:# orchestrarium:public-token|// orchestrarium:public-token)[ \t]*$"
)
_SCANNER_REGEX_CATALOG_LINE = re.compile(
    r"""(?P<binary_rule>\((?:True|False),\s*)?re\.compile\([rubfRUBF]*(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')\)(?(binary_rule)\)),?"""
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
# Budget base refnames and optional tag peels within the parent-graph byte cap.
_MAX_REMOTE_REFS = _MAX_PARENT_GRAPH_BYTES // (2 * _MAX_PATH_BYTES)
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
class NativePushUpdate:
    local_ref: bytes
    local_oid: str
    remote_ref: bytes
    remote_oid: str


@dataclass(frozen=True)
class NativePushRequest:
    object_format: GitObjectFormat
    repository_observation: dict
    endpoint: str
    endpoint_identity: str
    input_sha256: str
    update_set_sha256: str
    selection_sha256: str
    repository_observation_sha256: str
    updates: tuple[NativePushUpdate, ...]


@dataclass(frozen=True)
class NativePushSelection:
    request: NativePushRequest
    expected_oids: tuple[str, ...]
    object_oids: tuple[str, ...]
    object_format: GitObjectFormat
    roots: tuple[str, ...]
    expected_parents: tuple[tuple[str, tuple[str, ...]], ...] = ()


@dataclass(frozen=True)
class ScanSubject:
    kind: str
    locator: str
    raw: bytes


@dataclass(frozen=True)
class StagedEntry:
    status: str
    source_path: str | None
    destination_path: str


@dataclass(frozen=True)
class Finding:
    failure_id: str
    subject_kind: str
    locator: str
    line: int
    detector_class: str
    display_locator: str | None = None
    staged_index: int | None = None


@dataclass(frozen=True)
class Refusal:
    failure_id: str
    phase: str
    reason: str


def _refusal(failure_id: str, reason: str, *, phase: str | None = None) -> Refusal:
    return Refusal(failure_id, phase or _REFUSAL_PHASES.get(failure_id, "input"), reason)


def _review_failure_reason(exc: BaseException) -> str | None:
    message = exc.args[0] if exc.args and isinstance(exc.args[0], str) else ""
    for reason in ("review-policy", "review-evaluation", "review-receiving"):
        if message == reason or message.startswith(reason + "-"):
            return reason
    return None


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
        *,
        allow_empty: bool = False,
    ) -> None:
        self.expected_oids = tuple(expected_oids)
        self._events: dict[CoverageEvent, list[str]] = {
            event: [] for event in CoverageEvent
        }
        self._observer = observer
        self._fault_port = fault_port
        self._allow_empty = allow_empty

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
            allow_empty=self._allow_empty,
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
    mode: str = ""


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
    tag_ids: tuple[str, ...] = ()


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
    review: "ReviewedEvidence | None" = None
    native_selection: NativePushSelection | None = None


@dataclass(frozen=True)
class ReviewedEvidence:
    snapshot_id: str
    used_decisions: tuple[tuple[str, str], ...]
    applied: int
    applied_set: str
    used_token: str


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


def _windows_job_argv(argv: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    executable = shutil.which(argv[0])
    if executable is None or not os.path.isabs(executable):
        raise OSError("owned executable is unavailable")
    return (executable, *argv[1:])


def _run_windows_owned_process(
    argv: list[str], *, text: bool, timeout: float | None,
    env: dict[str, str] | None,
) -> subprocess.CompletedProcess:
    if timeout is None or timeout < 0:
        raise ValueError("Windows owned process requires a finite timeout")
    resolved = _windows_job_argv(argv)
    job = WindowsJobOwnerV1.launch(
        executable=resolved[0], argv=resolved, cwd=os.getcwd(),
        environment=env, stdin="null", stdout="pipe", stderr="pipe",
        coordinator=_WINDOWS_JOB_COORDINATOR,
    )
    streams: list[object] = []
    workers: list[threading.Thread] = []
    chunks: dict[str, list[bytes]] = {"stdout": [], "stderr": []}
    read_errors: list[BaseException] = []
    settled = False
    try:
        for name in ("stdout", "stderr"):
            fd = getattr(job, f"take_{name}_fd")()
            if fd is None:
                raise RuntimeError("owned Job output pipe unavailable")
            stream = None
            try:
                stream = os.fdopen(fd, "rb", buffering=0)
                streams.append(stream)
            except BaseException:
                if stream is None:
                    os.close(fd)
                else:
                    stream.close()
                raise

            def drain(source=stream, target=name):
                try:
                    while data := source.read(_READ_CHUNK_BYTES):
                        chunks[target].append(data)
                except BaseException as exc:
                    read_errors.append(exc)

            worker = threading.Thread(target=drain, name=f"publication-{name}")
            worker.start()
            workers.append(worker)
        deadline = time.monotonic() + timeout
        exit_code = job.wait(deadline)
        expired = exit_code is None
        cleanup_deadline = time.monotonic() + _PROCESS_TREE_CLEANUP_SECONDS
        closure = job.settle(cleanup_deadline, terminate=True)
        settled = True
        for worker in workers:
            worker.join(max(0.0, cleanup_deadline - time.monotonic()))
        if not closure.complete or any(worker.is_alive() for worker in workers) or read_errors:
            raise RuntimeError("owned Job did not settle")
        stdout = b"".join(chunks["stdout"])
        stderr = b"".join(chunks["stderr"])
        if text:
            stdout = stdout.decode("utf-8", "replace")
            stderr = stderr.decode("utf-8", "replace")
        if expired:
            raise subprocess.TimeoutExpired(argv, timeout, output=stdout, stderr=stderr)
        return subprocess.CompletedProcess(argv, exit_code, stdout, stderr)
    finally:
        if not settled:
            closure = job.close()
            if not closure.complete:
                raise RuntimeError("owned Job did not settle")
        for stream in streams:
            stream.close()
        for worker in workers:
            worker.join(_PROCESS_TREE_CLEANUP_SECONDS)


def _run_owned_process(
    argv: list[str],
    *,
    text: bool = False,
    timeout: float | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run a bounded process and settle its whole owned tree on timeout."""
    if os.name == "nt":
        return _run_windows_owned_process(argv, text=text, timeout=timeout, env=env)
    process_group_owner: PosixProcessGroupOwnerV1 | None = None
    try:
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


class _WindowsAsyncPipeReader:
    """Bounded thread-to-StreamReader bridge for a native anonymous pipe."""

    def __init__(self, fd: int, loop: asyncio.AbstractEventLoop) -> None:
        self.fd = fd
        self.loop = loop
        self.reader = asyncio.StreamReader(limit=_READ_CHUNK_BYTES)
        self.reader.set_transport(self)
        self._can_read = threading.Event()
        self._can_read.set()
        self._closed = False
        self._fd_closed = False
        self._ack_lock = threading.Lock()
        self._pending_ack: threading.Event | None = None
        self._thread = threading.Thread(target=self._pump, name="publication-pipe-read")
        self._thread.start()

    def pause_reading(self) -> None:
        self._can_read.clear()

    def resume_reading(self) -> None:
        self._can_read.set()

    def _deliver(self, data: bytes | None, error: OSError | None,
                 acknowledged: threading.Event) -> None:
        try:
            if self._closed:
                return
            if error is not None:
                self.reader.set_exception(error)
            elif data:
                self.reader.feed_data(data)
            else:
                self.reader.feed_eof()
        finally:
            acknowledged.set()

    def _pump(self) -> None:
        while not self._closed:
            self._can_read.wait()
            if self._closed:
                break
            try:
                data, error = os.read(self.fd, _READ_CHUNK_BYTES), None
            except OSError as exc:
                data, error = None, exc
            acknowledged = threading.Event()
            with self._ack_lock:
                if self._closed:
                    break
                self._pending_ack = acknowledged
            try:
                self.loop.call_soon_threadsafe(self._deliver, data, error, acknowledged)
            except RuntimeError:
                with self._ack_lock:
                    self._pending_ack = None
                break
            acknowledged.wait()
            with self._ack_lock:
                if self._pending_ack is acknowledged:
                    self._pending_ack = None
            if not data:
                break

    def close(self, deadline: float) -> bool:
        with self._ack_lock:
            self._closed = True
            pending_ack = self._pending_ack
        if pending_ack is not None:
            pending_ack.set()
        self._can_read.set()
        self._thread.join(max(0.0, deadline - time.monotonic()))
        if not self._fd_closed:
            try:
                os.close(self.fd)
            except OSError:
                return False
            self._fd_closed = True
        return not self._thread.is_alive()


class _WindowsAsyncPipeWriter:
    def __init__(self, fd: int) -> None:
        self.fd = fd
        self._pending: bytes | None = None
        self._task: asyncio.Task[None] | None = None
        self._closed = False
        self._fd_closed = False

    def write(self, data: bytes) -> None:
        if self._closed or self._pending is not None or (
            self._task is not None and not self._task.done()
        ):
            raise OSError("owned Job input pipe is unavailable")
        self._pending = bytes(data)

    def _write_all(self, data: bytes) -> None:
        view = memoryview(data)
        while view:
            written = os.write(self.fd, view)
            if written <= 0:
                raise OSError("owned Job input pipe short write")
            view = view[written:]

    async def drain(self) -> None:
        if self._pending is not None:
            data, self._pending = self._pending, None
            self._task = asyncio.create_task(asyncio.to_thread(self._write_all, data))
        if self._task is not None:
            await asyncio.shield(self._task)

    def close(self) -> None:
        self._closed = True
        self._pending = None

    def is_closing(self) -> bool:
        return self._closed

    async def wait_closed(self) -> None:
        try:
            if self._task is not None:
                await asyncio.shield(self._task)
        finally:
            if not self._fd_closed and (
                self._task is None or self._task.done()
            ):
                os.close(self.fd)
                self._fd_closed = True


class _WindowsOwnedAsyncProcess:
    """Async byte-pipe view of one creation-time Job-owned process."""

    def __init__(self, job, bridges: list[_WindowsAsyncPipeReader],
                 stdin, stdout, stderr) -> None:
        self.job = job
        self.pid = job.pid
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self._bridges = bridges

    @property
    def returncode(self) -> int | None:
        return self.job.poll()

    async def wait(self) -> int:
        while True:
            code = self.job.poll()
            if code is not None:
                return code
            await asyncio.sleep(0.01)

    def terminate(self) -> None:
        if not self.job.terminate_job():
            raise WindowsJobError("WJOB-JOB-TERMINATE", "settlement")

    def kill(self) -> None:
        self.terminate()

    async def close_io(self) -> bool:
        deadline = time.monotonic() + _PROCESS_TREE_CLEANUP_SECONDS
        closed = True
        if self.stdin is not None:
            self.stdin.close()
            try:
                await asyncio.wait_for(
                    self.stdin.wait_closed(),
                    timeout=max(0.001, deadline - time.monotonic()),
                )
            except (OSError, asyncio.TimeoutError):
                closed = False
        for bridge in self._bridges:
            if not bridge.close(deadline):
                closed = False
        return closed


async def _create_windows_owned_async_process(argv: tuple[str, ...], **kwargs):
    resolved = _windows_job_argv(argv)
    modes = {}
    for name in ("stdin", "stdout", "stderr"):
        value = kwargs.get(name, asyncio.subprocess.DEVNULL)
        if value == asyncio.subprocess.PIPE:
            modes[name] = "pipe"
        elif value == asyncio.subprocess.DEVNULL:
            modes[name] = "null"
        else:
            raise ValueError("unsupported owned Job stream policy")
    job = WindowsJobOwnerV1.launch(
        executable=resolved[0], argv=resolved, cwd=kwargs.get("cwd", os.getcwd()),
        environment=kwargs.get("env"), coordinator=_WINDOWS_JOB_COORDINATOR,
        **modes,
    )
    loop = asyncio.get_running_loop()
    bridges: list[_WindowsAsyncPipeReader] = []
    pending_bridge: _WindowsAsyncPipeReader | None = None
    stdin = stdout = stderr = None
    try:
        for name in ("stdout", "stderr"):
            if modes[name] == "null":
                continue
            fd = getattr(job, f"take_{name}_fd")()
            if fd is None:
                raise RuntimeError("owned Job output pipe unavailable")
            try:
                bridge = _WindowsAsyncPipeReader(fd, loop)
            except BaseException:
                os.close(fd)
                raise
            pending_bridge = bridge
            bridges.append(bridge)
            pending_bridge = None
            if name == "stdout":
                stdout = bridge.reader
            else:
                stderr = bridge.reader
        if modes["stdin"] == "pipe":
            fd = job.take_stdin_fd()
            if fd is None:
                raise RuntimeError("owned Job input pipe unavailable")
            try:
                stdin = _WindowsAsyncPipeWriter(fd)
            except BaseException:
                os.close(fd)
                raise
        return _WindowsOwnedAsyncProcess(job, bridges, stdin, stdout, stderr)
    except BaseException:
        job.close()
        if stdin is not None:
            stdin.close()
            await stdin.wait_closed()
        if pending_bridge is not None:
            pending_bridge.close(time.monotonic() + _PROCESS_TREE_CLEANUP_SECONDS)
        for bridge in bridges:
            bridge.close(time.monotonic() + _PROCESS_TREE_CLEANUP_SECONDS)
        raise


async def _create_owned_async_process(
    argv: tuple[str, ...],
    **kwargs,
) -> tuple[
    asyncio.subprocess.Process | _WindowsOwnedAsyncProcess,
    PosixProcessGroupOwnerV1 | None,
    _AsyncioDirectProcessObservation | None,
]:
    if os.name == "nt":
        process = await _create_windows_owned_async_process(argv, **kwargs)
        return process, None, None
    process_group_owner: PosixProcessGroupOwnerV1 | None = None
    direct_observation: _AsyncioDirectProcessObservation | None = None
    process_group_owner = await _acquire_posix_process_group_owner()
    process_kwargs = process_group_owner.popen_kwargs
    try:
        process = await asyncio.create_subprocess_exec(
            *argv, **kwargs, **process_kwargs
        )
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
    process: asyncio.subprocess.Process | _WindowsOwnedAsyncProcess,
    process_group_owner: PosixProcessGroupOwnerV1 | None,
    direct_observation: _AsyncioDirectProcessObservation | None,
    timeout_seconds: float = _PROCESS_TREE_CLEANUP_SECONDS,
    *,
    drain_readers: tuple[asyncio.StreamReader | None, ...] = (),
    close_io: bool = True,
) -> bool:
    cleanup_deadline = time.monotonic() + timeout_seconds
    if os.name == "nt":
        if not isinstance(process, _WindowsOwnedAsyncProcess):
            return False
        try:
            closure = process.job.settle(cleanup_deadline, terminate=True)
        except WindowsJobError:
            process.job.close()
            closure = None

        async def finish_io() -> bool:
            drained = True
            try:
                for reader in drain_readers:
                    if not await _drain_owned_async_reader(reader, cleanup_deadline):
                        drained = False
            finally:
                io_closed = await process.close_io() if close_io else True
            return bool(
                closure is not None and closure.complete
                and closure.direct_exit_code == process.returncode
                and drained and io_closed
            )

        finish_task = asyncio.create_task(finish_io())
        cancelled: asyncio.CancelledError | None = None
        while True:
            try:
                complete = await asyncio.shield(finish_task)
                break
            except asyncio.CancelledError as exc:
                cancelled = exc
        if cancelled is not None:
            raise cancelled
        return complete

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


@dataclass(frozen=True)
class _TextObservation:
    line: str
    line_number: int
    line_start: int
    family: str | None
    leaf_index: int
    pattern: re.Pattern[str]
    match: re.Match[str]

    @property
    def diagnostic_class(self) -> str:
        return (
            f"simple-{self.leaf_index + 1}"
            if self.family is None else f"value-{self.family}"
        )


def _text_lines(text: str) -> Iterator[tuple[int, int, str]]:
    """Keep original character coordinates across every splitlines separator."""
    offset = 0
    for number, segment in enumerate(text.splitlines(keepends=True), 1):
        pieces = segment.splitlines()
        yield number, offset, pieces[0] if pieces else ""
        offset += len(segment)


def _selected_text_lines(text: str, path: str, subject_kind: str) -> Iterator[tuple[int, int, str]]:
    scanner = _is_source_text_subject(subject_kind) and path.replace("\\", "/") in _SCANNER_EXEMPT_PATHS
    for number, offset, line in _text_lines(text):
        if not scanner or not _intentional_scanner_line(line):
            yield number, offset, line


def _matching_starts(pattern: re.Pattern[str], line: str) -> Iterator[re.Match[str]]:
    position = 0
    while position <= len(line):
        match = pattern.search(line, position)
        if match is None:
            return
        if match.end() <= match.start():
            raise RuntimeError("review-evaluation-zero-width")
        yield match
        position = match.start() + 1


def _line_observations(
    line: str,
    line_number: int,
    line_start: int,
    subject_kind: str,
    *,
    binary: bool = False,
) -> Iterator[_TextObservation]:
    for index, (binary_rule, pattern) in enumerate(_SIMPLE_RULES):
        if binary and not binary_rule:
            continue
        for match in _matching_starts(pattern, line):
            yield _TextObservation(line, line_number, line_start, None, index, pattern, match)
    for index, (family, pattern) in enumerate(_VALUE_RULES):
        for match in _matching_starts(pattern, line):
            # Callable syntax is meaningful in blob text. Retain the legacy
            # commit-message contract without granting it to new metadata.
            if (_is_source_text_subject(subject_kind) or subject_kind == "commit-message") and _is_callable_rhs(line, match):
                continue
            if binary:
                if _is_public_key_token_match(line, family, match):
                    continue
            elif _is_annotated_public_token_match(line, family, match, subject_kind):
                continue
            yield _TextObservation(line, line_number, line_start, family, index, pattern, match)


def _assignment_coordinates(observation: _TextObservation) -> tuple[int, ...] | None:
    """Reconstruct only the actual regex assignment, without parsing a language."""
    match, line = observation.match, observation.line
    if observation.family is None:
        return None
    rhs_start, rhs_end = match.span("rhs_value")
    separator_end = rhs_start
    while separator_end > match.start() and line[separator_end - 1].isspace():
        separator_end -= 1
    separator_start = separator_end - 1
    if separator_start < match.start() or line[separator_start] not in {":", "="}:
        return None
    identifier_end = separator_start
    while identifier_end > match.start() and line[identifier_end - 1].isspace():
        identifier_end -= 1
    prefix = _IDENTIFIER_PREFIX.search(line[:match.start()])
    identifier_start = prefix.start() if prefix is not None else match.start()
    if identifier_end <= identifier_start:
        return None
    return identifier_start, identifier_end, separator_start, separator_end, rhs_start, rhs_end


def _observation_key(observation: _TextObservation) -> tuple:
    assignment = _assignment_coordinates(observation)
    if observation.family is None:
        return ("simple", observation.leaf_index, observation.match.span())
    if assignment is not None:
        return ("value", observation.family, assignment)
    # An unproved assignment must remain an independent unresolved observation.
    return ("unproved", observation.leaf_index, observation.match.span())


def _build_detector_catalog(digest: Callable[[str, object], str]) -> tuple[tuple[dict, ...], dict]:
    definitions: list[dict] = []
    leaf_lookup: dict[tuple[str, int], tuple[dict, str]] = {}
    for index, (_binary, pattern) in enumerate(_SIMPLE_RULES):
        leaf = {"pattern": pattern.pattern, "flags": pattern.flags}
        leaf_id = "simple-" + digest("orchestrarium.publication-review.detector-leaf.v1", leaf)
        definition = {
            "schemaVersion": 1, "ruleId": leaf_id,
            "normalFormId": "nf-simple-match-v1", "domain": "blob-text-v1",
            "engine": "python-re-matching-starts-v1", "coordinate": "utf8-original-bytes-v1",
            "equivalence": "exact-match-v1", "leaves": [{"leafId": leaf_id, **leaf}],
            "exclusions": ["scanner-self-v1"],
        }
        detector = {"ruleId": leaf_id, "meaningSha256": digest("orchestrarium.publication-review.detector.v1", definition)}
        definitions.append(definition)
        leaf_lookup[("simple", index)] = (detector, leaf_id)
    for family in sorted({family for family, _pattern in _VALUE_RULES}):
        leaves: list[dict] = []
        indices: list[tuple[int, str]] = []
        for index, (actual_family, pattern) in enumerate(_VALUE_RULES):
            if actual_family != family:
                continue
            leaf = {"pattern": pattern.pattern, "flags": pattern.flags}
            leaf_id = "leaf-" + digest("orchestrarium.publication-review.detector-leaf.v1", leaf)
            leaves.append({"leafId": leaf_id, **leaf})
            indices.append((index, leaf_id))
        definition = {
            "schemaVersion": 1, "ruleId": f"value-{family}-v1",
            "normalFormId": "nf-value-assignment-v1", "domain": "blob-text-v1",
            "engine": "python-re-matching-starts-v1", "coordinate": "utf8-original-bytes-v1",
            "equivalence": "exact-assignment-v1", "leaves": sorted(leaves, key=lambda row: row["leafId"]),
            "exclusions": ["callable-rhs-v1", "public-token-v1", "scanner-self-v1"],
        }
        detector = {"ruleId": definition["ruleId"], "meaningSha256": digest("orchestrarium.publication-review.detector.v1", definition)}
        definitions.append(definition)
        for index, leaf_id in indices:
            leaf_lookup[("value", index)] = (detector, leaf_id)
    return tuple(sorted(definitions, key=lambda row: row["ruleId"])), leaf_lookup


def _original_byte_boundaries(raw: bytes) -> tuple[str, tuple[int, ...]]:
    text = raw.decode("utf-8", "strict")
    if text.encode("utf-8", "strict") != raw:
        raise ValueError("review-evaluation-byte-map")
    boundaries = [0]
    for scalar in text:
        boundaries.append(boundaries[-1] + len(scalar.encode("utf-8", "strict")))
    if boundaries[-1] != len(raw):
        raise ValueError("review-evaluation-byte-map")
    return text, tuple(boundaries)


def _byte_region(raw: bytes, start: int, end: int) -> dict:
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(raw):
        raise ValueError("review-evaluation-region")
    return {"startByte": start, "endByteExclusive": end, "sha256": hashlib.sha256(raw[start:end]).hexdigest()}


def _analyze_review_candidates(
    raw: bytes,
    path: str,
    *,
    subject_kind: str,
    digest: Callable[[str, object], str],
    canonical: Callable[[object], bytes],
) -> tuple[dict, ...]:
    text, boundaries = _original_byte_boundaries(raw)
    _definitions, leaves = _build_detector_catalog(digest)
    groups: dict[tuple, list[_TextObservation]] = {}
    for line_number, line_start, line in _selected_text_lines(text, path, subject_kind):
        for observation in _line_observations(line, line_number, line_start, subject_kind):
            groups.setdefault((line_start, _observation_key(observation)), []).append(observation)
    result: list[dict] = []
    for observations in groups.values():
        first = observations[0]
        detector, _leaf_id = leaves[("simple" if first.family is None else "value", first.leaf_index)]

        def region(start: int, end: int) -> dict:
            return _byte_region(raw, boundaries[first.line_start + start], boundaries[first.line_start + end])

        assignment = None
        if first.family is None:
            start, end = first.match.span()
            normal_form = "nf-simple-match-v1"
        else:
            coordinates = _assignment_coordinates(first)
            if coordinates is None:
                # Detection remains visible; no missing witness can be credited.
                result.append({"detector": detector, "candidate": None,
                               "line": first.line_number, "detectorClass": first.diagnostic_class})
                continue
            identifier_start, identifier_end, separator_start, separator_end, start, end = coordinates
            assignment = {"identifier": region(identifier_start, identifier_end),
                          "delimiter": region(separator_start, separator_end), "rhs": region(start, end)}
            normal_form = "nf-value-assignment-v1"
        candidate_region = region(start, end)
        contributors: list[dict] = []
        for observation in observations:
            _detector, leaf_id = leaves[("simple" if observation.family is None else "value", observation.leaf_index)]
            contributor = {"leafId": leaf_id, "fullMatch": region(*observation.match.span())}
            if contributor not in contributors:
                contributors.append(contributor)
        contributors.sort(key=lambda row: (row["leafId"], row["fullMatch"]["startByte"],
                                          row["fullMatch"]["endByteExclusive"], row["fullMatch"]["sha256"]))
        candidate = {"normalFormId": normal_form, **candidate_region,
                     "assignment": assignment, "contributors": contributors}
        candidate["occurrenceSha256"] = digest("orchestrarium.publication-review.occurrence.v1", {"detector": detector, **candidate})
        result.append({"detector": detector, "candidate": candidate,
                       "line": first.line_number, "detectorClass": first.diagnostic_class})
    return tuple(sorted(result, key=lambda row: (
        row["candidate"]["startByte"] if row["candidate"] is not None else -1,
        row["candidate"]["endByteExclusive"] if row["candidate"] is not None else -1,
        row["detector"]["ruleId"], canonical(row["candidate"]),
    )))


def _project_analyzed_review_candidate(
    raw: bytes, detector: dict, review_region: dict, rows: tuple[dict, ...],
) -> dict:
    if not isinstance(review_region, dict) or set(review_region) != {"startByte", "endByteExclusive", "sha256"}:
        raise ValueError("review-evaluation-region")
    if _byte_region(raw, review_region["startByte"], review_region["endByteExclusive"]) != review_region:
        raise ValueError("review-evaluation-region")
    selected: list[dict] = []
    for row in rows:
        if row["detector"] != detector:
            continue
        candidate = row["candidate"]
        if candidate is None:
            raise ValueError("review-evaluation-unproved")
        intervals = [(item["fullMatch"]["startByte"], item["fullMatch"]["endByteExclusive"])
                     for item in candidate["contributors"]]
        contained = all(review_region["startByte"] <= start < end <= review_region["endByteExclusive"]
                        for start, end in intervals)
        intersects = any(start < review_region["endByteExclusive"] and end > review_region["startByte"]
                         for start, end in intervals)
        if intersects and not contained:
            raise ValueError("review-evaluation-straddling")
        if contained:
            selected.append(candidate)
    if len(selected) != 1:
        raise ValueError("review-evaluation-unique-candidate")
    return selected[0]


def _load_review_policy_module():
    module_name = "_orchestrarium_publication_review_policy_v1"
    injection_names = (
        "__injected_review_policy_module__", "__injected_review_policy_snapshot__",
        "__injected_review_repository_observation__", "__injected_review_execution__",
    )
    present = tuple(name in globals() for name in injection_names)
    if any(present):
        if not all(present):
            raise RuntimeError("review-policy-injection")
        module = globals()[injection_names[0]]
        if (
            globals()[injection_names[3]] != "gate-captured-v1"
            or getattr(module, "__name__", None) != module_name
            or getattr(module, "__file__", None) != "<closure>/publication_review_policy.py"
            or sys.modules.get(module_name) is not module
            or getattr(module, "POLICY_MODULE_CONTRACT_ID", None)
            != "orchestrarium.publication-review-policy.module.v1"
        ):
            raise RuntimeError("review-policy-injection")
        return module
    if str(__file__).startswith("<closure>/"):
        raise RuntimeError("review-policy-injection")
    path = Path(__file__).resolve().with_name("publication_review_policy.py")
    existing = sys.modules.get(module_name)
    if existing is not None:
        if (
            getattr(existing, "__file__", None) != str(path)
            or getattr(existing, "POLICY_MODULE_CONTRACT_ID", None)
            != "orchestrarium.publication-review-policy.module.v1"
        ):
            raise RuntimeError("review-policy-module")
        return existing
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("review-policy-module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        if getattr(module, "POLICY_MODULE_CONTRACT_ID", None) != "orchestrarium.publication-review-policy.module.v1":
            raise RuntimeError("review-policy-module")
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


def detector_definitions(policy_module) -> dict[str, dict]:
    definitions, _leaves = _build_detector_catalog(policy_module.H)
    return {definition["ruleId"]: {
        "detector": {"ruleId": definition["ruleId"], "meaningSha256": policy_module.H("orchestrarium.publication-review.detector.v1", definition)},
        "definition": definition,
    } for definition in definitions}


def resolve_review_detector(diagnostic_class: str, *, policy_module) -> dict:
    _definitions, leaves = _build_detector_catalog(policy_module.H)
    for index in range(len(_SIMPLE_RULES)):
        if diagnostic_class == f"simple-{index + 1}":
            return leaves[("simple", index)][0]
    for index, (family, _pattern) in enumerate(_VALUE_RULES):
        if diagnostic_class == f"value-{family}":
            return leaves[("value", index)][0]
    raise ValueError("unknown-detector")


def analyze_review_candidates(raw: bytes, path: bytes, *, subject_kind: str, policy_module) -> dict:
    if not isinstance(raw, bytes) or not isinstance(path, bytes) or not path or b"\0" in path:
        return {"complete": False, "candidates": (), "unresolved": (),
                "refusal": _refusal("PS-INPUT-REFUSAL", "review-evaluation")}
    decoded_path = path.decode("utf-8", "surrogateescape")
    try:
        rows = _analyze_review_candidates(raw, decoded_path, subject_kind=subject_kind,
            digest=policy_module.H, canonical=policy_module.C)
    except UnicodeError:
        return {"complete": True, "candidates": (), "unresolved": tuple(_content_hits(
            raw.decode("utf-8", "replace"), decoded_path, lambda _line: (), subject_kind=subject_kind,
        )), "refusal": None}
    except (ValueError, RuntimeError):
        return {"complete": False, "candidates": (), "unresolved": (),
                "refusal": _refusal("PS-INPUT-REFUSAL", "review-evaluation")}
    candidates = tuple(row for row in rows if row["candidate"] is not None)
    unresolved = tuple(Finding(
        "PS-FINDING-COMMIT-MESSAGE" if subject_kind == "commit-message" else "PS-FINDING-CONTENT",
        subject_kind, _safe_locator(decoded_path, subject_kind), row["line"], row["detectorClass"],
    ) for row in rows if row["candidate"] is None)
    return {"complete": True, "candidates": candidates, "unresolved": unresolved, "refusal": None}


def project_review_candidate(raw: bytes, path: bytes, detector: dict, review_region: dict, *, policy_module) -> dict:
    definitions = detector_definitions(policy_module)
    if not isinstance(detector, dict) or definitions.get(detector.get("ruleId"), {}).get("detector") != detector:
        return {"status": "unrepresented", "candidate": None, "reason": "unknown-detector"}
    try:
        _original_byte_boundaries(raw)
    except (UnicodeError, ValueError):
        return {"status": "unavailable", "candidate": None, "reason": "unproved-byte-map"}
    analysis = analyze_review_candidates(raw, path, subject_kind="tracked-blob", policy_module=policy_module)
    if not analysis["complete"] or analysis["refusal"] is not None:
        return {"status": "unavailable", "candidate": None, "reason": "incomplete-evaluation"}
    if analysis["unresolved"]:
        return {"status": "unavailable", "candidate": None, "reason": "unproved-byte-map"}
    try:
        candidate = _project_analyzed_review_candidate(raw, detector, review_region, analysis["candidates"])
    except (ValueError, KeyError, TypeError) as exc:
        reason = {
            "review-evaluation-region": "invalid-region",
            "review-evaluation-straddling": "no-candidate",
            "review-evaluation-unique-candidate": "multiple-candidates",
        }.get(str(exc), "incomplete-evaluation")
        if reason == "multiple-candidates":
            count = sum(row["detector"] == detector and all(
                review_region["startByte"] <= item["fullMatch"]["startByte"] < item["fullMatch"]["endByteExclusive"] <= review_region["endByteExclusive"]
                for item in row["candidate"]["contributors"]
            ) for row in analysis["candidates"])
            reason = "no-candidate" if count == 0 else "multiple-candidates"
        return {"status": "ambiguous" if reason == "multiple-candidates" else "unrepresented", "candidate": None, "reason": reason}
    return {"status": "bound", "candidate": candidate, "reason": "none"}


def _capture_review_repository(policy_module, selected_root: Path, deadline: float) -> tuple[dict, tuple]:
    try:
        plan = policy_module.repository_query_plan(selected_root)
    except Exception as exc:
        # Missing metadata grants no credit; it is not an ordinary-clean veto.
        # Retain the actual failed acquisition beside the other caller outcomes.
        return {"status": "unavailable", "repository": None, "diagnostic": "metadata-unavailable"}, (exc,)
    rows = []
    for query in plan.queries:
        try:
            result = _run_range_git(list(query.git_args), text=False, timeout=_remaining_seconds(deadline))
        except BaseException as exc:
            failure = (
                "timeout" if isinstance(exc, (subprocess.TimeoutExpired, TimeoutError))
                else "cancelled" if isinstance(exc, (KeyboardInterrupt, asyncio.CancelledError))
                else "execution-error"
            )
            rows.append(policy_module.RepositoryQueryResultV1(
                query.key, query.git_args, None,
                getattr(exc, "stdout", None), getattr(exc, "stderr", None), False, None, failure,
            ))
            if not isinstance(exc, Exception):
                raise
            break
        raw_complete = isinstance(result.stdout, bytes) and isinstance(result.stderr, bytes)
        rows.append(policy_module.RepositoryQueryResultV1(
            query.key, query.git_args, result.returncode, result.stdout, result.stderr,
            raw_complete, True, None if raw_complete else "incomplete-capture",
        ))
        if not raw_complete or result.returncode != 0:
            break
    try:
        observation = policy_module.repository_from_query_results(plan, tuple(rows))
    except Exception as exc:
        return {"status": "unavailable", "repository": None, "diagnostic": "metadata-unavailable"}, (*rows, exc)
    return observation, tuple(rows)


class ReviewEvaluation:
    """One run's matching and application evidence; policy and Git IO stay outside."""

    def __init__(self, *, policy_module, policy_read, repository_observation: dict, execution: str):
        if execution not in {"standalone-v1", "gate-captured-v1"}:
            raise RuntimeError("review-policy-execution")
        decoded = policy_module.decode_policy_snapshot(policy_read.snapshot)
        if decoded.snapshot_id != policy_read.snapshot_id or decoded.usable_records != policy_read.usable_records:
            raise RuntimeError("review-policy-snapshot")
        self.policy = policy_module
        self.read = decoded
        self.repository_observation = repository_observation
        self.execution = execution
        self.unresolved = 0
        self._analysis: dict[tuple, dict] = {}
        self._applications: list[tuple[dict, dict, dict, dict]] = []
        self._applied_keys: set[tuple] = set()

    @property
    def repository(self) -> dict | None:
        observation = self.repository_observation
        if not isinstance(observation, dict) or set(observation) != {"status", "repository", "diagnostic"}:
            raise RuntimeError("review-policy-repository")
        if observation["status"] == "captured" and observation["diagnostic"] == "none" and isinstance(observation["repository"], dict):
            return observation["repository"]
        if observation in (
            {"status": "not-requested", "repository": None, "diagnostic": "not-needed"},
            {"status": "unavailable", "repository": None, "diagnostic": "metadata-unavailable"},
            {"status": "unavailable", "repository": None, "diagnostic": "unprovable-native-identity"},
        ):
            return None
        raise RuntimeError("review-policy-repository")

    def _authority(self, raw: bytes, subject: dict, row: dict, analysis: dict) -> tuple[dict, dict] | None:
        repository = self.repository
        if repository is None:
            return None
        # Policy's pure origin boundary check is the only source of origin credit.
        if not self.policy.origin_is_outside_repository(self.read.snapshot, repository):
            return None
        choices = []
        for record in self.read.usable_records:
            if record["repository"] != repository or subject["mode"] not in record["modes"]:
                continue
            if subject["mode"] == "range-blob-text":
                scope = record["rangeScope"]
                if scope is None or (scope["kind"] == "exact-commits" and subject["commitOid"] not in scope["commits"]):
                    continue
            for occurrence in record["occurrences"]:
                if any(occurrence[key] != subject[key] for key in (
                    "rawPathBase64", "blobOid", "blobSha256", "blobByteCount", "gitMode",
                )) or occurrence["detector"] != row["detector"] or occurrence["candidate"] != row["candidate"]:
                    continue
                if any(_byte_region(raw, context["region"]["startByte"], context["region"]["endByteExclusive"]) != context["region"]
                       for context in occurrence["contexts"]):
                    continue
                try:
                    projected = _project_analyzed_review_candidate(raw, occurrence["detector"], occurrence["reviewRegion"], analysis["candidates"])
                except (ValueError, TypeError, KeyError):
                    continue
                if projected != occurrence["candidate"]:
                    continue
                choices.append((record["id"], occurrence["id"], record["recordSha256"], record, occurrence))
        if not choices:
            return None
        selected = min(choices, key=lambda choice: choice[:3])
        return selected[3], selected[4]

    def scan_text_subject(
        self, raw: bytes, path: str, find_machine_paths, *, subject_kind: str,
        mode: str, commit_oid: str | None, raw_path: bytes, blob_oid: str, git_mode: str,
        machine_path_lines: frozenset[int] | None = None, display_locator: str | None = None,
        staged_index: int | None = None,
    ) -> list[Finding]:
        if not self.read.usable_records or self.repository is None:
            findings = _content_hits(raw.decode("utf-8", "replace"), path, find_machine_paths,
                subject_kind=subject_kind, machine_path_lines=machine_path_lines,
                display_locator=display_locator, staged_index=staged_index)
            self.unresolved += len(findings)
            return findings
        key = (raw_path, blob_oid, git_mode, subject_kind, hashlib.sha256(raw).digest())
        analysis = self._analysis.get(key)
        if analysis is None:
            analysis = analyze_review_candidates(raw, raw_path, subject_kind=subject_kind, policy_module=self.policy)
            self._analysis[key] = analysis
        if not analysis["complete"] or analysis["refusal"] is not None:
            raise RuntimeError("review-evaluation")
        repository = self.repository
        subject = {
            "repositorySha256": self.policy.H("orchestrarium.publication-review.repository.v1", repository) if repository is not None else "",
            "mode": mode, "commitOid": commit_oid,
            "rawPathBase64": base64.b64encode(raw_path).decode("ascii"), "blobOid": blob_oid,
            "blobSha256": hashlib.sha256(raw).hexdigest(), "blobByteCount": len(raw), "gitMode": git_mode,
        }
        findings = [replace(finding, display_locator=display_locator, staged_index=staged_index)
                    for finding in analysis["unresolved"]]
        locator = _safe_locator(path, subject_kind)
        for row in analysis["candidates"]:
            selected = self._authority(raw, subject, row, analysis) if git_mode in {"100644", "100755"} else None
            if selected is None:
                findings.append(Finding("PS-FINDING-CONTENT", subject_kind, locator, row["line"], row["detectorClass"], display_locator, staged_index))
                continue
            record, occurrence = selected
            binding = {"decisionId": record["id"], "occurrenceId": occurrence["id"],
                       "detector": occurrence["detector"], "reviewRegion": occurrence["reviewRegion"],
                       "candidate": occurrence["candidate"], "contexts": occurrence["contexts"],
                       "modes": record["modes"], "rangeScope": record["rangeScope"],
                       "repositorySha256": subject["repositorySha256"]}
            application = {"subject": subject, "occurrenceSha256": row["candidate"]["occurrenceSha256"],
                           "bindingSha256": self.policy.H("orchestrarium.publication-review.binding.v1", binding),
                           "decisionId": record["id"], "recordSha256": record["recordSha256"], "occurrenceId": occurrence["id"]}
            applied_key = (self.policy.C(subject), self.policy.C(row["detector"]), self.policy.C(row["candidate"]))
            if applied_key in self._applied_keys:
                raise RuntimeError("review-evaluation-duplicate")
            self._applied_keys.add(applied_key)
            self._applications.append((subject, row["candidate"], row["detector"], application))
        for number, _offset, line in _selected_text_lines(raw.decode("utf-8", "replace"), path, subject_kind):
            if (machine_path_lines is None or number in machine_path_lines) and find_machine_paths(line):
                findings.append(Finding("PS-FINDING-CONTENT", subject_kind, locator, number, "machine-path", display_locator, staged_index))
        self.unresolved += len(findings)
        return findings

    def evidence(self) -> ReviewedEvidence | None:
        if not self._applications:
            return None
        if self.unresolved:
            raise RuntimeError("review-evaluation-unresolved")
        applications = sorted(self._applications, key=lambda item: (
            item[0]["mode"], item[0]["commitOid"] or "", base64.b64decode(item[0]["rawPathBase64"], validate=True),
            item[0]["blobOid"], item[0]["gitMode"], item[1]["startByte"], item[1]["endByteExclusive"],
            item[2]["ruleId"], self.policy.C(item[1]),
        ))
        digest = self.policy.applied_set_digest(
            row for _subject, _candidate, _detector, row in applications
        )
        used = set()
        for _subject, _candidate, _detector, row in applications:
            used.add((row["decisionId"], row["recordSha256"]))
        ordered_used = tuple(sorted(used))
        token = base64.b64encode(self.policy.C([list(row) for row in ordered_used])).decode("ascii")
        return ReviewedEvidence(self.read.snapshot_id, ordered_used, len(applications), digest, token)


def _prepare_review_evaluation(selected_root: Path, deadline: float, *, need_repository: bool = True):
    policy = _load_review_policy_module()
    exchanges = []
    captured = globals().get("__injected_review_execution__") == "gate-captured-v1"
    if captured:
        policy_read = policy.decode_policy_snapshot(globals()["__injected_review_policy_snapshot__"])
        observation = globals()["__injected_review_repository_observation__"]
        execution = "gate-captured-v1"
    else:
        policy_read = policy.read_policy_snapshot(policy.resolve_trusted_origin(), selected_root)
        observation = {"status": "not-requested", "repository": None, "diagnostic": "not-needed"}
        execution = "standalone-v1"
        if policy_read.usable_records and need_repository:
            observation, exchange = _capture_review_repository(policy, selected_root, deadline)
            exchanges.append(exchange)
    evaluation = ReviewEvaluation(policy_module=policy, policy_read=policy_read,
                                  repository_observation=observation, execution=execution)
    # Force validation even when lexical evaluation subsequently has no candidates.
    evaluation.repository
    return evaluation, exchanges


def _finalize_review_evaluation(
    outcome: ScanOutcome, evaluation: ReviewEvaluation, selected_root: Path,
    deadline: float, selection_recheck: Callable[[], bool], exchanges: list,
) -> ScanOutcome:
    if outcome.kind != "clean":
        return outcome
    if evaluation.unresolved:
        return replace(outcome, kind="refusal", refusal=_refusal("PS-INPUT-REFUSAL", "review-evaluation"))
    evidence = evaluation.evidence()
    if evidence is None:
        return outcome
    if evaluation.execution == "standalone-v1":
        if not selection_recheck():
            return replace(outcome, kind="refusal", refusal=_refusal("PS-INPUT-REFUSAL", "review-receiving"))
        observation, exchange = _capture_review_repository(evaluation.policy, selected_root, deadline)
        exchanges.append(exchange)
        if observation["status"] != "captured":
            return replace(outcome, kind="refusal", refusal=_refusal("PS-INPUT-REFUSAL", "review-receiving"))
        finalization = evaluation.policy.verify_used(
            evaluation.read.snapshot, observation["repository"], [list(row) for row in evidence.used_decisions],
        )
        expected_repository = evaluation.policy.H("orchestrarium.publication-review.repository.v1", evaluation.repository)
        if (
            not isinstance(finalization, dict)
            or set(finalization) != {"inputSnapshotId", "usedList", "currentSnapshotId", "repositorySha256", "status", "reason", "resourcesSettled"}
            or finalization["status"] != "valid" or finalization["reason"] != "none"
            or finalization["resourcesSettled"] is not True
            or finalization["inputSnapshotId"] != evidence.snapshot_id
            or finalization["usedList"] != [list(row) for row in evidence.used_decisions]
            or finalization["repositorySha256"] != expected_repository
            or not isinstance(finalization["currentSnapshotId"], str)
            or re.fullmatch(r"[0-9a-f]{64}", finalization["currentSnapshotId"]) is None
        ):
            return replace(outcome, kind="refusal", refusal=_refusal("PS-INPUT-REFUSAL", "review-receiving"))
    return replace(outcome, review=evidence)


def _content_hits(
    text: str,
    path: str,
    find_machine_paths,
    *,
    subject_kind: str = "tracked-blob",
    max_findings: int | None = None,
    machine_path_lines: frozenset[int] | None = None,
    display_locator: str | None = None,
    staged_index: int | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    locator = _safe_locator(path, subject_kind)
    for line_number, line_start, line in _selected_text_lines(text, path, subject_kind):
        seen: set[tuple] = set()
        for observation in _line_observations(line, line_number, line_start, subject_kind):
            key = _observation_key(observation)
            if key in seen:
                continue
            seen.add(key)
            if max_findings is None or len(findings) < max_findings:
                findings.append(Finding(
                    "PS-FINDING-COMMIT-MESSAGE" if subject_kind == "commit-message" else "PS-FINDING-CONTENT",
                    subject_kind, locator, line_number, observation.diagnostic_class,
                    display_locator, staged_index,
                ))
        if (
            (machine_path_lines is None or line_number in machine_path_lines)
            and find_machine_paths(line)
        ):
            if max_findings is not None and len(findings) >= max_findings:
                continue
            findings.append(Finding(
                "PS-FINDING-COMMIT-MESSAGE" if subject_kind == "commit-message" else "PS-FINDING-CONTENT",
                subject_kind,
                locator,
                line_number,
                "machine-path",
                display_locator,
                staged_index,
            ))
    return findings


def _is_binary(raw: bytes) -> bool:
    return b"\0" in raw


def _is_callable_rhs(line: str, match: re.Match[str]) -> bool:
    return _CALLABLE_RHS.match(line, match.start("rhs_value")) is not None


def _is_public_token_credential_identifier(line: str, match: re.Match[str]) -> bool:
    credential_identifier = match.groupdict().get("credential_token_identifier")
    prefix = _IDENTIFIER_PREFIX.search(line[:match.start()])
    identifier_suffix = (
        credential_identifier
        if credential_identifier is not None
        else line[match.start():match.start() + len("token")]
    )
    identifier = (prefix.group(0) if prefix is not None else "") + identifier_suffix
    components = tuple(
        component_match.group(0).upper()
        for component_match in _IDENTIFIER_COMPONENT.finditer(identifier)
    )
    public_lexical_start = next(
        (
            index
            for index in range(len(components))
            if "".join(components[index:]).casefold()
            in _PUBLIC_TOKEN_ANNOTATED_LEXICAL_IDENTIFIERS
        ),
        None,
    )
    credential_components = (
        components if public_lexical_start is None else components[:public_lexical_start]
    )
    has_credential_cue = (
        credential_identifier is not None
        and credential_identifier.casefold()
        not in _PUBLIC_TOKEN_ANNOTATED_LEXICAL_IDENTIFIERS
    ) or any(
        component in _PUBLIC_TOKEN_CREDENTIAL_CUES
        or component.startswith(_PUBLIC_TOKEN_AUTH_CUE)
        for component in credential_components
    )
    return has_credential_cue


def _is_source_text_subject(subject_kind: str) -> bool:
    # Closed acquisition-owner discriminants for actual blob bodies. Metadata
    # and future unknown subjects retain ordinary detection, never source grants.
    return subject_kind in {"tracked-blob", "path-blob", "history-blob", "git-object-blob"}


def _is_annotated_public_token_match(
    line: str,
    family: str,
    match: re.Match[str],
    subject_kind: str,
) -> bool:
    if family != "token" or not _is_source_text_subject(subject_kind):
        return False
    if _is_public_token_credential_identifier(line, match):
        return False
    rhs = match.group("rhs_value")
    if len(rhs) < 2 or rhs[0] not in {"'", '"'} or rhs[-1] != rhs[0]:
        return False
    annotation_match = _PUBLIC_TOKEN_ANNOTATION_SUFFIX.fullmatch(
        line[match.end("rhs_value"):]
    )
    return annotation_match is not None


def _is_public_key_token_match(line: str, family: str, match: re.Match[str]) -> bool:
    if family != "token":
        return False
    prefix = _IDENTIFIER_PREFIX.search(line[:match.start()])
    identifier = (prefix.group(0) if prefix is not None else "") + line[
        match.start():match.start() + len("Token")
    ]
    return identifier == "publicKeyToken"


def _binary_content_hits(
    raw: bytes,
    path: str,
    find_machine_paths,
    *,
    max_findings: int | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    locator = _safe_locator(path, "history-blob")
    for line_number, raw_line in enumerate(raw.splitlines(), 1):
        for raw_run in _BINARY_ASCII_RUN.findall(raw_line):
            line = raw_run.decode("ascii")
            seen: set[tuple] = set()
            for observation in _line_observations(
                line, line_number, 0, "history-blob", binary=True
            ):
                key = _observation_key(observation)
                if key in seen:
                    continue
                seen.add(key)
                if max_findings is None or len(findings) < max_findings:
                    findings.append(Finding(
                        "PS-FINDING-CONTENT", "history-blob", locator,
                        line_number, observation.diagnostic_class,
                    ))
            if find_machine_paths(line) and (
                max_findings is None or len(findings) < max_findings
            ):
                findings.append(Finding(
                    "PS-FINDING-CONTENT",
                    "history-blob",
                    locator,
                    line_number,
                    "machine-path",
                ))
    return findings


_STAGED_HUNK_HEADER = re.compile(
    rb"^@@ -([0-9]+)(?:,([0-9]+))? \+([0-9]+)(?:,([0-9]+))? @@(?: .*)?$"
)
_STAGED_OID = re.compile(rb"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_STAGED_INDEX_ENTRY = re.compile(
    rb"(?P<mode>[0-7]{6}) (?P<oid>[0-9a-f]{40}|[0-9a-f]{64}) 0\t(?P<path>.*)\0",
    re.DOTALL,
)


def _parse_staged_entries(raw: bytes) -> tuple[StagedEntry, ...]:
    if not raw:
        return ()
    if not raw.endswith(b"\0"):
        raise RuntimeError("malformed staged name-status output")
    fields = raw[:-1].split(b"\0")
    entries: list[StagedEntry] = []
    destinations: set[str] = set()
    index = 0

    def take_path() -> str:
        nonlocal index
        if index >= len(fields) or not fields[index]:
            raise RuntimeError("malformed staged name-status output")
        value = fields[index].decode("utf-8", "surrogateescape")
        index += 1
        return value

    while index < len(fields):
        try:
            status = fields[index].decode("ascii", "strict")
        except UnicodeDecodeError as exc:
            raise RuntimeError("malformed staged name-status output") from exc
        index += 1
        if not status:
            raise RuntimeError("malformed staged name-status output")
        code = status[0]
        source_path: str | None = None
        if code in {"R", "C"}:
            score = status[1:]
            if not score.isdigit() or len(score) > 3 or int(score) > 100:
                raise RuntimeError("malformed staged rename/copy status")
            source_path = take_path()
            destination_path = take_path()
        elif code in {"A", "M"} and len(status) == 1:
            destination_path = take_path()
        elif code in {"T", "U", "X", "B"}:
            raise RuntimeError("unsupported staged status")
        else:
            raise RuntimeError("malformed staged name-status output")
        if destination_path in destinations:
            raise RuntimeError("ambiguous staged destination")
        destinations.add(destination_path)
        entries.append(StagedEntry(status, source_path, destination_path))
    return tuple(entries)


def _staged_blob_oid(revision: str) -> str:
    proc = _run_git(
        ["rev-parse", "--verify", "--end-of-options", revision],
        timeout=30,
    )
    value = proc.stdout.strip()
    if proc.returncode or _STAGED_OID.fullmatch(value) is None:
        raise RuntimeError("could not resolve staged blob")
    return value.decode("ascii")


def _staged_index_binding(path: str) -> tuple[str, str, bytes]:
    proc = _run_git(["ls-files", "--stage", "-z", "--", path], timeout=30)
    match = _STAGED_INDEX_ENTRY.fullmatch(proc.stdout)
    if (
        proc.returncode
        or match is None
        or match.group("path").decode("utf-8", "surrogateescape") != path
    ):
        raise RuntimeError("could not resolve staged index entry")
    mode = match.group("mode").decode("ascii")
    if mode not in {"100644", "100755", "120000", "160000"}:
        raise RuntimeError("unsupported staged mode")
    return mode, match.group("oid").decode("ascii"), match.group("path")


def _staged_index_entry(path: str) -> tuple[str, str]:
    mode, oid, _raw_path = _staged_index_binding(path)
    return mode, oid


def _staged_post_image(oid: str) -> bytes:
    proc = _run_git(["cat-file", "blob", oid], timeout=30)
    if proc.returncode:
        raise RuntimeError("could not read staged post-image")
    return proc.stdout


def _staged_added_line_numbers(old_oid: str, new_oid: str) -> frozenset[int]:
    if old_oid == new_oid:
        return frozenset()
    proc = _run_git(
        [
            "diff", "--text", "--unified=0", "--no-color", "--no-ext-diff",
            "--no-textconv", old_oid, new_oid,
        ],
        timeout=30,
    )
    if proc.returncode:
        raise RuntimeError("could not diff staged blobs")

    added: set[int] = set()
    old_remaining: int | None = None
    new_remaining: int | None = None
    new_line = 0
    saw_hunk = False

    def finish_hunk() -> None:
        if old_remaining not in {None, 0} or new_remaining not in {None, 0}:
            raise RuntimeError("malformed staged blob diff")

    for raw_line in proc.stdout.splitlines():
        if raw_line.startswith(b"@@"):
            finish_hunk()
            match = _STAGED_HUNK_HEADER.fullmatch(raw_line)
            if match is None:
                raise RuntimeError("malformed staged blob diff")
            old_remaining = int(match.group(2) or b"1")
            new_line = int(match.group(3))
            new_remaining = int(match.group(4) or b"1")
            saw_hunk = True
            continue
        if old_remaining is None or new_remaining is None:
            continue
        if raw_line == b"\\ No newline at end of file":
            continue
        prefix = raw_line[:1]
        if prefix == b"-" and old_remaining > 0:
            old_remaining -= 1
        elif prefix == b"+" and new_remaining > 0:
            if new_line < 1:
                raise RuntimeError("malformed staged blob diff")
            added.add(new_line)
            new_line += 1
            new_remaining -= 1
        elif prefix == b" " and old_remaining > 0 and new_remaining > 0:
            old_remaining -= 1
            new_line += 1
            new_remaining -= 1
        else:
            raise RuntimeError("malformed staged blob diff")
    finish_hunk()
    if not saw_hunk:
        raise RuntimeError("ambiguous staged blob diff")
    return frozenset(added)


def _tracked_files(*, review_bindings: dict[str, tuple[str, str, bytes]] | None = None) -> tuple[
    list[str],
    dict[str, bytes],
    dict[str, frozenset[int] | None],
]:
    names = _run_git(
        [
            "diff", "--cached", "--name-status", "-z", "--find-renames",
            "--diff-filter=ACMRTUXB", "--",
        ],
        timeout=30,
    )
    if names.returncode:
        raise RuntimeError("could not enumerate staged tracked files")
    entries = _parse_staged_entries(names.stdout)
    paths = [entry.destination_path for entry in entries]
    blobs: dict[str, bytes] = {}
    machine_path_lines: dict[str, frozenset[int] | None] = {}
    for entry in entries:
        path = entry.destination_path
        binding = _staged_index_binding(path)
        new_mode, new_oid, _raw_path = binding
        if review_bindings is not None:
            review_bindings[path] = binding
        if new_mode == "160000":
            blobs[path] = b""
            machine_path_lines[path] = frozenset()
            continue
        raw = _staged_post_image(new_oid)
        blobs[path] = raw
        code = entry.status[0]
        if code in {"A", "C"}:
            machine_path_lines[path] = None
            continue
        old_path = entry.source_path if code == "R" else path
        if old_path is None:
            raise RuntimeError("missing staged source path")
        old_oid = _staged_blob_oid(f"HEAD:{old_path}")
        if code == "R" and entry.status == "R100" and old_oid != new_oid:
            raise RuntimeError("ambiguous pure rename")
        if _is_binary(raw):
            machine_path_lines[path] = frozenset()
            continue
        selected = _staged_added_line_numbers(old_oid, new_oid)
        line_count = len(raw.decode("utf-8", "replace").splitlines())
        if any(line_number > line_count for line_number in selected):
            raise RuntimeError("staged line outside post-image")
        machine_path_lines[path] = selected
    return paths, blobs, machine_path_lines


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


def _native_json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def _native_update_documents(updates: tuple[NativePushUpdate, ...]) -> list[dict[str, str]]:
    return [{"localRefBase64": base64.b64encode(row.local_ref).decode("ascii"), "localOid": row.local_oid,
             "remoteRefBase64": base64.b64encode(row.remote_ref).decode("ascii"), "remoteOid": row.remote_oid}
            for row in updates]


def _native_push_request(payload: object) -> NativePushRequest | Refusal:
    """Decode actual callback data from the qualified agent command normal form.

    The submitting owner rejects LF in actual explicit refspec operands.
    Local source bytes are opaque; object authority comes from the local OID.
    """
    fields = {"version", "objectFormat", "repositoryObservation", "endpoint", "endpointIdentity", "inputSha256", "wireBase64"}
    if type(payload) is not dict or set(payload) != fields or type(payload["version"]) is not int or payload["version"] != 1:
        return _refusal("PS-INPUT-REFUSAL", "native-selection")
    object_format = _SUPPORTED_OBJECT_FORMATS.get(payload["objectFormat"]) if isinstance(payload["objectFormat"], str) else None
    observation, endpoint = payload["repositoryObservation"], payload["endpoint"]
    if (
        object_format is None
        or type(observation) is not dict or set(observation) != {"status", "repository", "diagnostic"}
        or observation["status"] != "captured" or observation["diagnostic"] != "none"
        or type(observation["repository"]) is not dict
        or not isinstance(endpoint, str) or not endpoint or "\0" in endpoint
        or not isinstance(payload["wireBase64"], str)
        or not isinstance(payload["inputSha256"], str) or re.fullmatch(r"[0-9a-f]{64}", payload["inputSha256"]) is None
    ):
        return _refusal("PS-INPUT-REFUSAL", "native-selection")
    try:
        endpoint_identity = "sha256:" + hashlib.sha256(_native_json_bytes(endpoint)).hexdigest()
        if payload["endpointIdentity"] != endpoint_identity:
            return _refusal("PS-INPUT-REFUSAL", "native-endpoint")
        wire = base64.b64decode(payload["wireBase64"], validate=True)
        if base64.b64encode(wire).decode("ascii") != payload["wireBase64"]:
            return _refusal("PS-INPUT-REFUSAL", "native-wire")
        if wire and not wire.endswith(b"\n"):
            return _refusal("PS-INPUT-REFUSAL", "native-wire-truncated")
        decoded: list[NativePushUpdate] = []
        raw_rows: list[bytes] = []
        destinations: set[bytes] = set()
        zero = "0" * object_format.hex_length
        for line in wire.split(b"\n")[:-1]:
            pieces = line.rsplit(b" ", 3)
            if len(pieces) != 4:
                return _refusal("PS-INPUT-REFUSAL", "native-wire")
            local_ref, raw_local_oid, remote_ref, raw_remote_oid = pieces
            local_oid, remote_oid = raw_local_oid.decode("ascii"), raw_remote_oid.decode("ascii")
            if not local_ref or b"\0" in local_ref or not _valid_remote_refname(remote_ref):
                return _refusal("PS-INPUT-REFUSAL", "native-ref")
            if any(not isinstance(oid, str) or not object_format.matches(oid) for oid in (local_oid, remote_oid)):
                return _refusal("PS-INPUT-REFUSAL", "native-oid")
            if (local_oid == zero and local_ref != b"(delete)") or remote_ref in destinations:
                return _refusal("PS-INPUT-REFUSAL", "native-update")
            destinations.add(remote_ref)
            decoded.append(NativePushUpdate(local_ref, local_oid, remote_ref, remote_oid))
            raw_rows.append(b" ".join((local_ref, local_oid.encode("ascii"), remote_ref, remote_oid.encode("ascii"))) + b"\n")
        if b"".join(raw_rows) != wire or hashlib.sha256(wire).hexdigest() != payload["inputSha256"]:
            return _refusal("PS-INPUT-REFUSAL", "native-input-digest")
        update_set = hashlib.sha256(_native_json_bytes(_native_update_documents(tuple(decoded)))).hexdigest()
        return NativePushRequest(object_format, json.loads(_native_json_bytes(observation)), endpoint, endpoint_identity,
                                 payload["inputSha256"], update_set,
                                 hashlib.sha256(_native_json_bytes(payload)).hexdigest(),
                                 hashlib.sha256(_native_json_bytes(observation)).hexdigest(), tuple(decoded))
    except (ValueError, TypeError, UnicodeError):
        return _refusal("PS-INPUT-REFUSAL", "native-selection")


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


async def _feed_selection_input(stream, data: bytes, deadline: float) -> None:
    try:
        for offset in range(0, len(data), _READ_CHUNK_BYTES):
            stream.write(data[offset:offset + _READ_CHUNK_BYTES])
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise asyncio.TimeoutError
            await asyncio.wait_for(stream.drain(), remaining)
    finally:
        stream.close()
        wait_closed = getattr(stream, "wait_closed", None)
        if callable(wait_closed):
            await wait_closed()


async def _finish_selection_input(task, deadline: float, *, cancel: bool) -> Refusal | None:
    if task is None:
        return None
    refusal = None
    try:
        if cancel:
            task.cancel()
        else:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise asyncio.TimeoutError
            await asyncio.wait_for(asyncio.shield(task), remaining)
    except asyncio.TimeoutError:
        refusal = _refusal("PS-MSG-READ-TIMEOUT", "selection-input")
    except asyncio.CancelledError:
        refusal = None if cancel else _refusal("PS-MSG-READ", "cancelled")
    except Exception:
        refusal = _refusal("PS-MSG-READ", "selection-input")
    finally:
        if not task.done():
            task.cancel()
    return refusal


async def _settle_selection_input(task, deadline: float) -> bool:
    """Join input only after its owned child is settled and can no longer block it."""
    if task is None:
        return True
    try:
        if not task.done():
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return False
            await asyncio.wait_for(asyncio.shield(task), remaining)
    except asyncio.CancelledError:
        if not task.done():
            return False
    except asyncio.TimeoutError:
        return False
    except Exception:
        # Input failure is already the primary nonauthorizing result; joining
        # a terminal failed task still proves its resource was settled.
        if not task.done():
            return False
    await asyncio.gather(task, return_exceptions=True)
    return task.done()


def _selection_reap_refusal(prior: Refusal | None, has_input: bool) -> Refusal:
    reason = "selection-child"
    if has_input and prior is not None:
        reason += f"-after-{prior.failure_id}-{prior.phase}-{prior.reason}"
    return _refusal("PS-MSG-REAP", reason)


async def _read_git_lines_bounded(
    argv: tuple[str, ...],
    *,
    byte_cap: int,
    line_cap: int,
    deadline: float,
    accepted_codes: frozenset[int],
    env: dict[str, str] | None = None,
    input_bytes: bytes | None = None,
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
            stdin=asyncio.subprocess.DEVNULL if input_bytes is None else asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=env,
        )
    except (OSError, subprocess.SubprocessError, WindowsJobError):
        return _refusal("PS-MSG-SPAWN", "selection")
    if process.stdout is None or (input_bytes is not None and process.stdin is None):
        if not await _settle_owned_async_process(
            process, process_group_owner, direct_observation
        ):
            return _refusal("PS-MSG-REAP", "selection-child")
        return _refusal("PS-MSG-READ", "selection-pipe")

    rows: list[bytes] = []
    pending = bytearray()
    total_bytes = 0
    refusal: Refusal | None = None
    input_task = None if input_bytes is None else asyncio.create_task(_feed_selection_input(process.stdin, input_bytes, deadline))
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

    input_refusal = await _finish_selection_input(input_task, deadline, cancel=refusal is not None)
    if refusal is None:
        refusal = input_refusal
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

    cleanup_deadline = asyncio.get_running_loop().time() + _PROCESS_TREE_CLEANUP_SECONDS
    child_settled = await _settle_owned_async_process(
        process,
        process_group_owner,
        direct_observation,
        drain_readers=(process.stdout,),
    )
    input_settled = await _settle_selection_input(input_task, cleanup_deadline)
    if not child_settled or not input_settled:
        return _selection_reap_refusal(refusal, input_task is not None)
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
    include_object_roots: bool = False,
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
                if include_object_roots:
                    if classified.returned_oid is not None and remote_ref.peeled_oid is not None:
                        if classified.object_type != "tag":
                            pending = _refusal("PS-MSG-RANGE", "remote-ref-type")
                            break
                        peeled = await reader.classify(
                            f"{remote_ref.oid}^{{}}", object_format=object_format,
                            require_identity=False, scan_deadline=deadline,
                        )
                        if isinstance(peeled, Refusal):
                            pending = peeled
                            break
                        if peeled.returned_oid != remote_ref.peeled_oid:
                            pending = _refusal("PS-MSG-RANGE", "remote-ref-type")
                            break
                    if classified.returned_oid is None and remote_ref.peeled_oid is not None:
                        classified = await reader.classify(remote_ref.peeled_oid, object_format=object_format, scan_deadline=deadline)
                        if isinstance(classified, Refusal):
                            pending = classified
                            break
                    if classified.returned_oid is not None and classified.returned_oid not in seen_commits:
                        seen_commits.add(classified.returned_oid)
                        commits.append(classified.returned_oid)
                    continue
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
    input_bytes: bytes | None = None,
) -> tuple[tuple[str, tuple[str, ...]], ...] | Refusal:
    result = await _read_git_lines_bounded(
        argv,
        byte_cap=_MAX_PARENT_GRAPH_BYTES,
        line_cap=_MAX_COMMIT_TREE_BYTES,
        deadline=deadline,
        accepted_codes=frozenset({0}),
        **({"input_bytes": input_bytes} if input_bytes is not None else {}),
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
    input_bytes: bytes | None = None,
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
            stdin=asyncio.subprocess.DEVNULL if input_bytes is None else asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError, WindowsJobError):
        return _refusal("PS-MSG-SPAWN", "selection")
    if process.stdout is None or (input_bytes is not None and process.stdin is None):
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
    input_task = None if input_bytes is None else asyncio.create_task(_feed_selection_input(process.stdin, input_bytes, deadline))

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

    input_refusal = await _finish_selection_input(input_task, deadline, cancel=refusal is not None)
    if refusal is None:
        refusal = input_refusal
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

    cleanup_deadline = asyncio.get_running_loop().time() + _PROCESS_TREE_CLEANUP_SECONDS
    child_settled = await _settle_owned_async_process(
        process,
        process_group_owner,
        direct_observation,
        drain_readers=(process.stdout,),
    )
    input_settled = await _settle_selection_input(input_task, cleanup_deadline)
    if not child_settled or not input_settled:
        return _selection_reap_refusal(refusal, input_task is not None)
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
    native_payload = globals().get("__injected_native_push__")
    if native_payload is not None:
        native = _native_push_request(native_payload)
        if isinstance(native, Refusal):
            return native
        return await _native_commit_range_selection(request, native, deadline)
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


async def _native_push_selection(request: NativePushRequest, deadline: float) -> NativePushSelection | Refusal:
    try:
        if _detect_git_object_format(_remaining_seconds(deadline)) != request.object_format:
            return _refusal("PS-MSG-RANGE", "object-format")
        if _graft_overlay_present(_remaining_seconds(deadline)):
            return _refusal("PS-MSG-RANGE", "graft-overlay")
    except subprocess.TimeoutExpired:
        return _refusal("PS-MSG-READ-TIMEOUT", "deadline")
    except (OSError, ValueError):
        return _refusal("PS-MSG-RANGE", "native-repository")
    zero = "0" * request.object_format.hex_length
    roots = tuple(dict.fromkeys(row.local_oid for row in request.updates if row.local_oid != zero))
    if not roots:
        return NativePushSelection(request, (), (), request.object_format, ())
    loop = asyncio.get_running_loop()
    loop_deadline = loop.time() + _remaining_seconds(deadline)
    native_old = tuple(RemoteRefTip(row.remote_ref, row.remote_oid) for row in request.updates if row.remote_oid != zero)
    exclusions = await _local_remote_commit_tip_oids(
        native_old, deadline=loop_deadline,
        object_format=request.object_format, include_object_roots=True,
    )
    if isinstance(exclusions, Refusal):
        return exclusions
    revisions = b"".join((oid.encode("ascii") + b"\n") for oid in roots)
    revisions += b"".join((b"^" + oid.encode("ascii") + b"\n") for oid in exclusions)
    parent_graph = await _read_parent_graph_bounded(
        _range_git_argv("rev-list", "--parents", "--topo-order", "--stdin"),
        deadline=loop_deadline, object_format=request.object_format, input_bytes=revisions,
    )
    if isinstance(parent_graph, Refusal):
        return parent_graph
    objects = await _read_git_oid_lines_bounded(
        _range_git_argv("rev-list", "--objects", "--no-object-names", "--stdin"),
        count_cap=_MAX_OBJECTS, byte_cap=request.object_format.list_byte_cap(_MAX_OBJECTS),
        deadline=loop_deadline, object_format=request.object_format, input_bytes=revisions,
    )
    if isinstance(objects, Refusal):
        return objects
    commits = tuple(oid for oid, _parents in parent_graph)
    if not set(commits).issubset(objects):
        return _refusal("PS-MSG-COVERAGE", "commit-object-set")
    return NativePushSelection(request, commits, objects, request.object_format, roots, parent_graph)


async def _native_commit_range_selection(
    primary: RangeRequest, request: NativePushRequest, deadline: float,
) -> RangeSelection | Refusal:
    """Union each actual update's commit graph relative to its own old OID.

    A separately advertised server is never evidence about a custom receiver.
    Unknown old objects are conservatively included instead of excluded.
    """
    object_format = request.object_format
    if _detect_git_object_format(_remaining_seconds(deadline)) != object_format or _graft_overlay_present(_remaining_seconds(deadline)):
        return _refusal("PS-MSG-RANGE", "native-repository")
    zero = "0" * object_format.hex_length
    parents: dict[str, tuple[str, ...]] = {}
    objects: set[str] = set()
    selected_primary = None
    for row in request.updates:
        if row.local_oid == zero:
            continue
        try:
            tip = _resolve_commit(row.local_oid, _remaining_seconds(deadline), object_format=object_format)
        except ValueError:
            # Trees and blobs have no V3 commit graph; V4 scans their roots.
            continue
        if selected_primary is None:
            selected_primary = (os.fsdecode(row.remote_ref), tip)
        exclusion = ()
        if row.remote_oid != zero:
            try:
                old = _resolve_commit(row.remote_oid, _remaining_seconds(deadline), object_format=object_format)
            except ValueError:
                pass
            else:
                exclusion = ("--not", old)
        loop_deadline = asyncio.get_running_loop().time() + _remaining_seconds(deadline)
        graph = await _read_parent_graph_bounded(
            _range_git_argv("rev-list", "--parents", "--topo-order", tip, *exclusion),
            deadline=loop_deadline, object_format=object_format,
        )
        if isinstance(graph, Refusal):
            return graph
        selected_objects = await _read_git_oid_lines_bounded(
            _range_git_argv("rev-list", "--objects", "--no-object-names", tip, *exclusion),
            count_cap=_MAX_OBJECTS, byte_cap=object_format.list_byte_cap(_MAX_OBJECTS),
            deadline=loop_deadline, object_format=object_format,
        )
        if isinstance(selected_objects, Refusal):
            return selected_objects
        parents.update(graph)
        objects.update(selected_objects)
        if len(parents) > _MAX_COMMITS or len(objects) > _MAX_OBJECTS:
            return _refusal("PS-MSG-LIMIT", "count")
    if selected_primary != (primary.destination, primary.source):
        return _refusal("PS-MSG-RANGE", "native-primary")
    if not set(parents).issubset(objects):
        return _refusal("PS-MSG-COVERAGE", "commit-object-set")
    return RangeSelection(primary.remote, primary.destination, primary.source,
        primary.source, tuple(parents), tuple(sorted(objects)), object_format,
        expected_parents=tuple(parents.items()))


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
    if object_type not in {"commit", "tree", "blob", "tag"}:
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
        except (OSError, subprocess.SubprocessError, WindowsJobError):
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

    async def _discard_stdout(self, deadline: float) -> tuple[bool, bool]:
        """Drain fixed chunks to EOF without retaining child output."""
        process = self._process
        if process is None or process.stdout is None:
            return True, False
        observed_data = False
        try:
            while True:
                chunk = await self._within(
                    process.stdout.read(_READ_CHUNK_BYTES), deadline
                )
                if not chunk:
                    return True, observed_data
                observed_data = True
        except (asyncio.TimeoutError, OSError, RuntimeError, ValueError):
            return False, observed_data

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
        drain_task = (
            asyncio.create_task(self._discard_stdout(deadline))
            if process.stdout is not None
            else None
        )
        terminal = await _settle_owned_async_process(
            process,
            self._process_group_owner,
            self._direct_observation,
            self._settle_timeout,
            close_io=os.name != "nt",
        )
        if not terminal:
            errors.append("group-settle")
        child = ChildObservation(
            child_identity,
            process.returncode,
            terminal and process.returncode is not None,
            loop.time(),
        )
        if drain_task is not None:
            try:
                drained, trailing = await asyncio.shield(drain_task)
                if not drained:
                    errors.append("stdout-drain")
                    stdout = TransportObservation(
                        "owned", "unobserved", False, "stdout-drain", loop.time()
                    )
                elif trailing and not self._poisoned:
                    errors.append("stdout-trailing")
                    stdout = TransportObservation(
                        "owned", "output-eof", True, None, loop.time()
                    )
                else:
                    stdout = TransportObservation(
                        "owned", "output-eof", True, None, loop.time()
                    )
            except Exception:
                if not drain_task.done():
                    drain_task.cancel()
                errors.append("stdout-drain")
                stdout = TransportObservation(
                    "owned", "unobserved", False, "stdout-drain", loop.time()
                )
        if isinstance(process, _WindowsOwnedAsyncProcess):
            if not await process.close_io():
                errors.append("pipe-close")
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


def _decode_tag_target(raw: bytes, object_format: GitObjectFormat) -> tuple[str, str] | Refusal:
    separator = raw.find(b"\n\n")
    if separator < 0:
        return _refusal("PS-MSG-FRAME", "tag-separator")
    headers = raw[:separator].split(b"\n")
    values = {key: [line[len(key) + 1:] for line in headers if line.startswith(key + b" ")]
              for key in (b"object", b"type", b"tag")}
    if any(len(rows) != 1 for rows in values.values()) or not values[b"tag"][0]:
        return _refusal("PS-MSG-FRAME", "tag-header")
    try:
        oid, kind = values[b"object"][0].decode("ascii"), values[b"type"][0].decode("ascii")
    except UnicodeDecodeError:
        return _refusal("PS-MSG-FRAME", "tag-header")
    if not object_format.matches(oid) or kind not in {"tag", "commit", "tree", "blob"}:
        return _refusal("PS-MSG-FRAME", "tag-target")
    return oid, kind


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
        entries.append(TreeEntry(kind, name, raw_oid.hex(), mode.decode("ascii")))
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
    *,
    allow_empty: bool = False,
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
        (not expected and not allow_empty)
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
            pending.mode,
            refusal=finalization,
            selection=pending.selection,
            native_selection=pending.native_selection,
        )
    if certificate is None:
        if pending.kind == "refusal" and pending.refusal is not None and pending.refusal.failure_id in {
            "PS-MSG-RANGE", "PS-MSG-SPAWN", "PS-MSG-COVERAGE"
        }:
            return pending
        return ScanOutcome(
            "refusal", pending.mode,
            refusal=_refusal("PS-MSG-REAP", "certificate"),
            selection=pending.selection,
            native_selection=pending.native_selection,
        )
    if not certificate.complete:
        return ScanOutcome(
            "refusal", pending.mode,
            refusal=_refusal("PS-MSG-REAP", "certificate"),
            selection=pending.selection,
            native_selection=pending.native_selection,
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
    selection: RangeSelection | NativePushSelection,
    reader: _AsyncGitObjectReader,
    find_machine_paths,
    coverage_recorder: CoverageRecorder,
    scan_deadline: float,
    *,
    review_evaluation: "ReviewEvaluation | None" = None,
) -> tuple[HistoryProof, CoverageProof, tuple[Finding, ...]] | Refusal:
    commit_set = set(selection.expected_oids)
    native = isinstance(selection, NativePushSelection)
    object_types: dict[str, str] = {}
    commit_records: dict[str, CommitRecord] = {}
    tag_targets: dict[str, tuple[str, str]] = {}
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
        if native or expected_type == "commit":
            coverage_recorder.record(CoverageEvent.REQUESTED, oid)
        result = await reader.read(
            oid, expected_type, scan_deadline=scan_deadline
        )
        if isinstance(result, Refusal):
            return result
        if result.returned_oid != oid:
            return _refusal("PS-MSG-COVERAGE", "object-identity")
        if native:
            actual_oid = hashlib.new(selection.object_format.name,
                                     f"{result.object_type} {len(result.raw)}\0".encode("ascii") + result.raw).hexdigest()
            if actual_oid != oid:
                return _refusal("PS-MSG-COVERAGE", "object-content-identity")
            coverage_recorder.record(CoverageEvent.ACQUIRED, oid)
        object_types[oid] = result.object_type
        if result.object_type == "commit":
            if oid not in commit_set:
                return _refusal("PS-MSG-COVERAGE", "unexpected-commit")
            if not native:
                coverage_recorder.record(CoverageEvent.ACQUIRED, result.returned_oid)
            record = _decode_commit_record(result.raw, selection.object_format)
            if isinstance(record, Refusal):
                return record
            if native:
                header = result.raw[:result.raw.find(b"\n\n")]
                line_refusal = _line_limit_refusal(header)
                if line_refusal is not None:
                    return line_refusal
                _append_findings(findings, _content_hits(
                    header.decode("utf-8", "replace"), oid, find_machine_paths,
                    subject_kind="commit-header", max_findings=max(0, _MAX_FINDINGS - len(findings)),
                ))
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
        elif native and result.object_type == "tag":
            target = _decode_tag_target(result.raw, selection.object_format)
            if isinstance(target, Refusal):
                return target
            aggregate_messages += len(result.raw)
            if aggregate_messages > _MAX_AGGREGATE_MESSAGE_BYTES:
                return _refusal("PS-MSG-LIMIT", "aggregate-message-bytes")
            line_refusal = _line_limit_refusal(result.raw)
            if line_refusal is not None:
                return line_refusal
            _append_findings(findings, _content_hits(
                result.raw.decode("utf-8", "replace"), oid, find_machine_paths,
                subject_kind="tag-object", max_findings=max(0, _MAX_FINDINGS - len(findings)),
            ))
            coverage_recorder.record(CoverageEvent.SCANNED, oid)
            tag_targets[oid] = target
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
    coverage = None
    if not native:
        coverage = coverage_recorder.proof()
        if isinstance(coverage, Refusal):
            return coverage
    target_types = dict(object_types)
    for target_oid, declared_type in tag_targets.values():
        actual_type = target_types.get(target_oid)
        if actual_type is None:
            try:
                result = _run_range_git(["cat-file", "-t", target_oid], text=True,
                                        timeout=max(0.001, scan_deadline - asyncio.get_running_loop().time()))
            except subprocess.TimeoutExpired:
                return _refusal("PS-MSG-READ-TIMEOUT", "tag-target")
            except OSError:
                return _refusal("PS-MSG-READ", "tag-target")
            if result.returncode or result.stdout.splitlines() != [declared_type]:
                return _refusal("PS-MSG-FRAME", "tag-target")
            target_types[target_oid] = declared_type
        elif actual_type != declared_type:
            return _refusal("PS-MSG-FRAME", "tag-target")

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
        if native and hashlib.new(selection.object_format.name,
                                  f"tree {len(result.raw)}\0".encode("ascii") + result.raw).hexdigest() != oid:
            return _refusal("PS-MSG-COVERAGE", "object-content-identity")
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
    subject_modes: dict[tuple[str, bytes, str], str] = {}
    subject_set: set[tuple[str, bytes, str]] = set()
    native_metadata_paths: set[tuple[str, bytes]] = set()
    tree_roots = [(oid, commit_records[oid].root_tree) for oid in selection.expected_oids]
    direct_blobs = []
    if native:
        for root in selection.roots:
            selected = root
            chain = set()
            while selected in tag_targets:
                if selected in chain:
                    return _refusal("PS-MSG-FRAME", "tag-cycle")
                chain.add(selected)
                selected = tag_targets[selected][0]
            if object_types.get(selected) == "tree":
                tree_roots.append((root, selected))
            elif object_types.get(selected) == "blob":
                direct_blobs.append((root, b"", selected))
    for commit_oid, root_tree in tree_roots:
        guard = _tree_traversal_guard(
            deadline=scan_deadline,
            frontier=0,
            visits=tree_visits,
            visited=len(visited_tree_ids),
            cache_entries=len(tree_cache),
        )
        if guard is not None:
            return guard
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
                if native and tree_oid in unpublished_trees and (tree_oid, path) not in native_metadata_paths:
                    native_metadata_paths.add((tree_oid, path))
                    decoded_path = path.decode("utf-8", "surrogateescape")
                    _append_findings(findings, _filename_findings(decoded_path, "tree-path"))
                    _append_findings(findings, _content_hits(
                        decoded_path, tree_oid, find_machine_paths, subject_kind="tree-path",
                        max_findings=max(0, _MAX_FINDINGS - len(findings)),
                    ))
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
                    subject_modes[subject] = entry.mode
                    if len(subjects) > _MAX_SUBJECTS:
                        return _refusal("PS-MSG-LIMIT", "subject-count")

    for subject in direct_blobs:
        if subject not in subject_set:
            subject_set.add(subject)
            subjects.append(subject)
            subject_modes[subject] = ""
    if reached_unpublished_trees != unpublished_trees:
        return _refusal("PS-MSG-COVERAGE", "tree-subjects")
    if {blob for _commit, _path, blob in subjects} != unpublished_blobs:
        return _refusal("PS-MSG-COVERAGE", "blob-subjects")
    blob_paths = {(path, blob) for _commit, path, blob in subjects}
    if len(blob_paths) > _MAX_BLOB_PATHS:
        return _refusal("PS-MSG-LIMIT", "blob-path-count")

    binary_blobs = {oid for oid, raw in blob_contents.items() if _is_binary(raw)}
    text_blobs = set(blob_contents) - binary_blobs
    subjects_by_path: dict[tuple[bytes, str], list[tuple[str, str]]] = {}
    if review_evaluation is not None:
        for commit_oid, raw_path, blob_oid in sorted(subjects):
            subjects_by_path.setdefault((raw_path, blob_oid), []).append(
                (commit_oid, subject_modes[(commit_oid, raw_path, blob_oid)])
            )
    for path, blob_oid in sorted(blob_paths):
        decoded_path = path.decode("utf-8", "surrogateescape")
        if not native:
            _append_findings(findings, _filename_findings(decoded_path, "history-blob"))
        raw = blob_contents[blob_oid]
        line_refusal = _line_limit_refusal(raw)
        if line_refusal is not None:
            return line_refusal
        if blob_oid in binary_blobs:
            content_findings = _binary_content_hits(
                raw,
                decoded_path,
                find_machine_paths,
                max_findings=max(0, _MAX_FINDINGS - len(findings)),
            )
        elif review_evaluation is not None:
            content_findings = []
            for commit_oid, git_mode in subjects_by_path[(path, blob_oid)]:
                if asyncio.get_running_loop().time() >= scan_deadline:
                    return _refusal("PS-MSG-READ-TIMEOUT", "deadline")
                if commit_oid not in commit_set:
                    _append_findings(content_findings, _content_hits(
                        raw.decode("utf-8", "replace"), decoded_path, find_machine_paths,
                        subject_kind="git-object-blob", max_findings=max(0, _MAX_FINDINGS - len(content_findings)),
                    ))
                    continue
                _append_findings(content_findings, review_evaluation.scan_text_subject(
                    raw, decoded_path, find_machine_paths, subject_kind="history-blob",
                    mode="range-blob-text", commit_oid=commit_oid, raw_path=path,
                    blob_oid=blob_oid, git_mode=git_mode,
                ))
        else:
            content_findings = _content_hits(
                raw.decode("utf-8", "replace"),
                decoded_path,
                find_machine_paths,
                subject_kind="history-blob",
                max_findings=max(0, _MAX_FINDINGS - len(findings)),
            )
        _append_findings(findings, content_findings)

    if native:
        for oid in selection.object_oids:
            if object_types[oid] in {"tree", "blob"}:
                coverage_recorder.record(CoverageEvent.SCANNED, oid)
        coverage = coverage_recorder.proof()
        if isinstance(coverage, Refusal):
            return coverage

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
        tuple(sorted(tag_targets)),
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
    review_evaluation: "ReviewEvaluation | None" = None,
) -> ScanOutcome:
    wall_deadline = time.monotonic() + scan_timeout
    request = _range_request(remote, destination, source_revision)
    if isinstance(request, Refusal):
        return ScanOutcome("refusal", "range", refusal=request)
    selection = await _range_selection(request, wall_deadline)
    if isinstance(selection, Refusal):
        return ScanOutcome("refusal", "range", refusal=selection)
    if not selection.expected_oids:
        return ScanOutcome("refusal", "range", refusal=_refusal("PS-MSG-COVERAGE", "empty-selection"), selection=selection)
    return await _scan_selected_history_async(
        selection, find_machine_paths, wall_deadline=wall_deadline, tip_resolver=tip_resolver,
        reader_factory=reader_factory, coverage_observer=coverage_observer, coverage_fault=coverage_fault,
        review_evaluation=review_evaluation,
    )


async def _scan_selected_history_async(
    selection: RangeSelection | NativePushSelection,
    find_machine_paths,
    *,
    wall_deadline: float,
    tip_resolver: Callable[[float | None], str] | None = None,
    reader_factory: Callable[[], _AsyncGitObjectReader] = _AsyncGitObjectReader,
    coverage_observer: Callable[[CoverageEvent, str], None] | None = None,
    coverage_fault: CoverageFaultPort | None = None,
    review_evaluation: "ReviewEvaluation | None" = None,
) -> ScanOutcome:
    native = isinstance(selection, NativePushSelection)
    mode = "native-push" if native else "range"
    selection_fields = {"native_selection": selection} if native else {"selection": selection}
    if native and not selection.object_oids:
        empty = HistoryProof((), (), (), 0, 0, 0, (), (), _commit_set_digest(()),
                             _oid_set_digest(b"object-set", ()), _oid_set_digest(b"blob-set", ()),
                             _subject_set_digest(()), _path_set_digest(()))
        coverage = _build_coverage_proof((), (), (), (), allow_empty=True)
        return ScanOutcome("clean", mode, coverage=coverage, history=empty, **selection_fields)
    coverage_recorder = CoverageRecorder(
        selection.object_oids if native else selection.expected_oids, coverage_observer, coverage_fault
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
                    "refusal", mode, refusal=start_refusal, **selection_fields
                )
            else:
                loop = asyncio.get_running_loop()
                remaining = wall_deadline - time.monotonic()
                if remaining <= 0:
                    acquisition = _refusal("PS-MSG-READ-TIMEOUT", "deadline")
                else:
                    review_arguments = (
                        {"review_evaluation": review_evaluation}
                        if review_evaluation is not None else {}
                    )
                    acquisition = await _acquire_history(
                        selection,
                        reader,
                        find_machine_paths,
                        coverage_recorder,
                        loop.time() + remaining,
                        **review_arguments,
                    )
                if isinstance(acquisition, Refusal):
                    pending = ScanOutcome(
                        "refusal", mode, refusal=acquisition, **selection_fields
                    )
                else:
                    acquired = acquisition
        except asyncio.CancelledError:
            pending = ScanOutcome(
                "refusal", mode,
                refusal=_refusal("PS-MSG-READ", "cancelled"),
                **selection_fields,
            )
        except Exception as exc:
            pending = ScanOutcome(
                "refusal", mode,
                refusal=(
                    _refusal("PS-INPUT-REFUSAL", reason)
                    if (reason := _review_failure_reason(exc)) is not None
                    else _refusal("PS-MSG-READ", "unexpected")
                ),
                **selection_fields,
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
            if native:
                drift = None
            else:
                resolver = tip_resolver or (
                    lambda timeout=None: _resolve_commit(selection.source, timeout, object_format=selection.object_format)
                )
                drift = _confirm_tip(selection.tip, resolver, max(0.001, wall_deadline - time.monotonic()))
        except Exception:
            pending = ScanOutcome(
                "refusal", mode,
                refusal=_refusal("PS-MSG-READ", "unexpected"),
                **selection_fields,
            )
        else:
            if drift is not None:
                pending = ScanOutcome(
                    "refusal", mode, refusal=drift, **selection_fields
                )
            elif findings:
                pending = ScanOutcome(
                    "findings", mode, file_count=len(history.paths),
                    findings=tuple(findings), **selection_fields,
                    coverage=coverage, history=history,
                )
            else:
                pending = ScanOutcome(
                    "clean", mode, file_count=len(history.paths),
                    **selection_fields,
                    coverage=coverage, history=history,
                )

    if pending is None:
        pending = ScanOutcome(
            "refusal", mode,
            refusal=_refusal("PS-MSG-COVERAGE", "empty-selection"),
            **selection_fields,
        )
    return _finalize_range_outcome(pending, finalization, certificate)


def _scan_range(
    remote: str,
    destination: str,
    find_machine_paths,
    *,
    source_revision: str | None = None,
    tip_resolver: Callable[[float | None], str] | None = None,
    review_evaluation: "ReviewEvaluation | None" = None,
    scan_timeout: float = _SCAN_DEADLINE_SECONDS,
) -> ScanOutcome:
    try:
        return asyncio.run(_scan_range_async(
            remote,
            destination,
            find_machine_paths,
            source_revision=source_revision,
            tip_resolver=tip_resolver,
            review_evaluation=review_evaluation,
            scan_timeout=scan_timeout,
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


async def _scan_native_push_async(
    payload: object, find_machine_paths, *,
    reader_factory: Callable[[], _AsyncGitObjectReader] = _AsyncGitObjectReader,
    coverage_observer: Callable[[CoverageEvent, str], None] | None = None,
    coverage_fault: CoverageFaultPort | None = None,
    scan_timeout: float = _SCAN_DEADLINE_SECONDS,
    review_evaluation: "ReviewEvaluation | None" = None,
) -> ScanOutcome:
    request = _native_push_request(payload)
    if isinstance(request, Refusal):
        return ScanOutcome("refusal", "native-push", refusal=request)
    deadline = time.monotonic() + scan_timeout
    try:
        root = _repo_root()
        policy = _load_review_policy_module()
        before, _exchanges = _capture_review_repository(policy, root, deadline)
        if before != request.repository_observation:
            return ScanOutcome("refusal", "native-push", refusal=_refusal("PS-INPUT-REFUSAL", "native-repository"))
        selection = await _native_push_selection(request, deadline)
        if isinstance(selection, Refusal):
            return ScanOutcome("refusal", "native-push", refusal=selection)
        outcome = await _scan_selected_history_async(
            selection, find_machine_paths, wall_deadline=deadline,
            reader_factory=reader_factory, coverage_observer=coverage_observer,
            coverage_fault=coverage_fault, review_evaluation=review_evaluation,
        )
        after, _exchanges = _capture_review_repository(policy, root, deadline)
        if after != before:
            return replace(outcome, kind="refusal", refusal=_refusal("PS-INPUT-REFUSAL", "native-repository-currentness"))
        return outcome
    except subprocess.TimeoutExpired:
        return ScanOutcome("refusal", "native-push", refusal=_refusal("PS-MSG-READ-TIMEOUT", "deadline"))
    except (OSError, ValueError, RuntimeError):
        return ScanOutcome("refusal", "native-push", refusal=_refusal("PS-INPUT-REFUSAL", "native-selection"))


def _scan_native_push(payload: object, find_machine_paths, *,
                      review_evaluation: "ReviewEvaluation | None" = None,
                      scan_timeout: float = _SCAN_DEADLINE_SECONDS) -> ScanOutcome:
    try:
        return asyncio.run(_scan_native_push_async(payload, find_machine_paths,
                           review_evaluation=review_evaluation, scan_timeout=scan_timeout))
    except KeyboardInterrupt:
        return ScanOutcome("refusal", "native-push", refusal=_refusal("PS-MSG-READ", "cancelled"))
    except Exception:
        return ScanOutcome("refusal", "native-push", refusal=_refusal("PS-MSG-READ", "unexpected"))


def _serialize_native_receipt_v4(outcome: ScanOutcome) -> str:
    selection, history, coverage = outcome.native_selection, outcome.history, outcome.coverage
    if outcome.kind != "clean" or selection is None or history is None or coverage is None:
        raise ValueError("native receipt")
    actual = _build_coverage_proof(coverage.expected_oids, coverage.requested_oids,
                                   coverage.acquired_oids, coverage.scanned_message_oids, allow_empty=True)
    if (
        isinstance(actual, Refusal) or actual != coverage
        or history.commit_ids != selection.expected_oids
        or set(coverage.expected_oids) != set(history.object_ids)
        or set(selection.object_oids) != set(history.object_ids)
        or tuple(sorted(set(history.object_ids))) != history.object_ids
        or not set(history.blob_ids).issubset(history.object_ids)
        or not set(history.tag_ids).issubset(history.object_ids)
        or history.object_set != _oid_set_digest(b"object-set", history.object_ids)
        or history.commit_set != _commit_set_digest(history.commit_ids)
        or history.blob_set != _oid_set_digest(b"blob-set", history.blob_ids)
        or history.subject_set != _subject_set_digest(history.subjects)
        or history.path_set != _path_set_digest(history.paths)
        or history.text_blobs + history.binary_blobs != len(history.blob_ids)
        or history.blob_bytes < 0
        or (history.object_ids and (outcome.reap_certificate is None or not outcome.reap_certificate.complete))
        or (not history.object_ids and outcome.reap_certificate is not None)
    ):
        raise ValueError("native coverage")
    request = selection.request
    review = outcome.review
    return _native_json_bytes({
        "kind": "publication-safety-native", "version": 4,
        "status": "clean" if review is None else "qualified",
        "objectFormat": selection.object_format.name,
        "selectionSha256": request.selection_sha256,
        "repositoryObservationSha256": request.repository_observation_sha256,
        "endpointIdentity": request.endpoint_identity, "inputSha256": request.input_sha256,
        "updateSetSha256": request.update_set_sha256, "updates": len(request.updates),
        "commits": len(history.commit_ids), "commitSetSha256": history.commit_set,
        "objects": len(history.object_ids), "objectSetSha256": history.object_set,
        "coverageKind": "objects", "coverageSha256": coverage.coverage_digest,
        "tags": len(history.tag_ids), "blobs": len(history.blob_ids), "blobSetSha256": history.blob_set,
        "blobBytes": history.blob_bytes, "text": history.text_blobs, "binary": history.binary_blobs,
        "subjects": len(history.subjects), "subjectSetSha256": history.subject_set,
        "paths": len(history.paths), "pathSetSha256": history.path_set,
        "review": None if review is None else {"snapshotId": review.snapshot_id,
            "usedDecisions": [list(row) for row in review.used_decisions], "applied": review.applied,
            "appliedSet": review.applied_set, "usedToken": review.used_token},
    }).decode("ascii")


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
    if not history.commit_ids or not history.object_ids or history.tag_ids:
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
    group.add_argument("--native-push", action="store_true")
    parser.add_argument("--range-source", metavar="REVISION")
    parser.add_argument("legacy_path", nargs="?")
    return parser


def _filename_findings(
    path: str,
    subject_kind: str,
    *,
    display_locator: str | None = None,
    staged_index: int | None = None,
) -> list[Finding]:
    base = Path(path).name
    locator = _safe_locator(path, subject_kind)
    if base == ".env":
        return [Finding(
            "PS-FINDING-CONTENT", subject_kind, locator, 1, "filename-env",
            display_locator, staged_index,
        )]
    if base.casefold() == "secret.md":
        return [Finding(
            "PS-FINDING-CONTENT", subject_kind, locator, 1, "filename-secret",
            display_locator, staged_index,
        )]
    return []


def _staged_display_locator(path: str, find_machine_paths) -> str:
    normalized = path.replace("\\", "/")
    segments = normalized.split("/")
    if (
        not normalized
        or normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized) is not None
        or any(not segment or segment in {".", ".."} for segment in segments)
        or any(ord(char) < 32 or ord(char) == 127 for char in normalized)
    ):
        return "redacted"
    if _filename_findings(normalized, "tracked-blob"):
        return "redacted"
    if _content_hits(
        normalized,
        normalized,
        find_machine_paths,
        subject_kind="commit-message",
        max_findings=1,
    ):
        return "redacted"
    try:
        return _encode_receipt_token(normalized)
    except (UnicodeError, ValueError):
        return "redacted"


def _scan_content_blobs(
    mode: str,
    paths: list[str],
    blobs: dict[str, bytes],
    find_machine_paths,
    *,
    machine_path_lines_by_path: dict[str, frozenset[int] | None] | None = None,
    review_evaluation: "ReviewEvaluation | None" = None,
    review_bindings: dict[str, tuple[str, str, bytes]] | None = None,
) -> ScanOutcome:
    findings: list[Finding] = []
    subject_kind = "path-blob" if mode == "path" else "tracked-blob"
    if machine_path_lines_by_path is not None and (
        mode != "tracked" or set(machine_path_lines_by_path) != set(paths)
    ):
        raise RuntimeError("staged machine-path selection mismatch")
    for one_based_index, path in enumerate(paths, 1):
        staged_index = one_based_index if machine_path_lines_by_path is not None else None
        display_locator = (
            _staged_display_locator(path, find_machine_paths)
            if staged_index is not None
            else None
        )
        findings.extend(_filename_findings(
            path,
            subject_kind,
            display_locator=display_locator,
            staged_index=staged_index,
        ))
        raw = blobs[path]
        if _is_binary(raw):
            continue
        content_arguments = {
            "subject_kind": subject_kind,
            "machine_path_lines": (
                machine_path_lines_by_path[path]
                if machine_path_lines_by_path is not None else None
            ),
            "display_locator": display_locator,
            "staged_index": staged_index,
        }
        if review_evaluation is not None and review_bindings is not None:
            git_mode, blob_oid, raw_path = review_bindings[path]
            findings.extend(review_evaluation.scan_text_subject(
                raw, path, find_machine_paths, **content_arguments,
                mode="staged-blob-text", commit_oid=None, raw_path=raw_path,
                blob_oid=blob_oid, git_mode=git_mode,
            ))
            continue
        findings.extend(_content_hits(
            raw.decode("utf-8", "replace"),
            path,
            find_machine_paths,
            **content_arguments,
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
                if (
                    finding.subject_kind == "tracked-blob"
                    and finding.display_locator is not None
                    and finding.staged_index is not None
                    and finding.staged_index > 0
                ):
                    lines.append(
                        f"{finding.failure_id} kind=tracked-blob "
                        f"locator={finding.display_locator} "
                        f"staged-index={finding.staged_index} "
                        f"line={finding.line} class={finding.detector_class}"
                    )
                else:
                    lines.append(
                        f"{finding.failure_id} kind={finding.subject_kind} "
                        f"line={finding.line} class={finding.detector_class}"
                    )
        lines.append("publication-safety scan found potential tracked-content leak markers")
        return "", "\n".join(lines), 1
    review_suffix = ""
    if outcome.review is not None:
        review = outcome.review
        if (
            outcome.kind != "clean" or outcome.mode not in {"tracked", "range", "native-push"}
            or type(review.applied) is not int or review.applied <= 0
            or not review.used_decisions
            or tuple(sorted(set(review.used_decisions))) != review.used_decisions
            or re.fullmatch(r"[0-9a-f]{64}", review.snapshot_id) is None
            or re.fullmatch(r"[0-9a-f]{64}", review.applied_set) is None
            or re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", review.used_token) is None
        ):
            return "", "publication-safety: refusing id=PS-INPUT-REFUSAL reason=review-policy phase=input", 2
        review_suffix = (
            f", policy-snapshot={review.snapshot_id}, used-decisions={review.used_token}, "
            f"applied={review.applied}, applied-set={review.applied_set}, "
            "unresolved=0, evaluation=complete)"
        )
    if outcome.mode == "native-push":
        try:
            return _serialize_native_receipt_v4(outcome), "", 0
        except (ValueError, TypeError, UnicodeError):
            return "", "publication-safety: refusing id=PS-INPUT-REFUSAL reason=native-receipt phase=input", 2
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
            line = _serialize_range_receipt_v3(
                history, selection.remote, selection.destination, selection.source,
                selection.tip, object_format=selection.object_format,
            )
            if review_suffix:
                line = line.replace("publication-safety: clean", "publication-safety: qualified", 1)[:-1] + review_suffix
            return (
                line,
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
    if review_suffix:
        if count <= 0:
            return "", "publication-safety: refusing id=PS-INPUT-REFUSAL reason=review-policy phase=input", 2
        return f"publication-safety: qualified (staged, examined={count}" + review_suffix, "", 0
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
    if args.legacy_path and (args.path or args.range or args.native_push):
        _parser().error("unexpected extra path argument")
    if args.range_source is not None and not args.range:
        _parser().error("--range-source requires --range")
    script = Path(__file__).resolve()
    try:
        repo_root = _repo_root()
        os.chdir(repo_root)
        find_machine_paths = _path_finder(script)
        if args.native_push:
            deadline = time.monotonic() + _SCAN_DEADLINE_SECONDS
            evaluation, exchanges = _prepare_review_evaluation(repo_root, deadline)
            payload = globals().get("__injected_native_push__")
            outcome = _scan_native_push(payload, find_machine_paths,
                                       review_evaluation=evaluation if evaluation.read.usable_records else None,
                                       scan_timeout=_remaining_seconds(deadline))

            def recheck_native() -> bool:
                request = _native_push_request(payload)
                if isinstance(request, Refusal):
                    return False
                observed, _exchange = _capture_review_repository(evaluation.policy, repo_root, deadline)
                return observed == request.repository_observation

            return _emit_outcome(_finalize_review_evaluation(outcome, evaluation, repo_root, deadline,
                                                            recheck_native, exchanges))
        if args.range:
            remote, dst = args.range
            review_deadline = time.monotonic() + _SCAN_DEADLINE_SECONDS
            review_evaluation, exchanges = _prepare_review_evaluation(repo_root, review_deadline)
            outcome = _scan_range(
                remote,
                dst,
                find_machine_paths,
                source_revision=args.range_source,
                review_evaluation=review_evaluation if review_evaluation.read.usable_records else None,
                scan_timeout=_remaining_seconds(review_deadline),
            )

            def recheck_range() -> bool:
                selection = outcome.selection
                if selection is None:
                    return False
                return _confirm_tip(selection.tip, lambda timeout=None: _resolve_commit(
                    selection.source, timeout, object_format=selection.object_format,
                ), _remaining_seconds(review_deadline)) is None

            return _emit_outcome(_finalize_review_evaluation(
                outcome, review_evaluation, repo_root, review_deadline, recheck_range, exchanges,
            ))
        elif args.path or args.legacy_path:
            mode = "path"
            paths, blobs = _path_files(args.path or args.legacy_path)
            machine_path_lines_by_path = None
            review_evaluation = None
            review_bindings = None
        else:
            mode = "tracked"
            review_bindings = {}
            paths, blobs, machine_path_lines_by_path = _tracked_files(review_bindings=review_bindings)
            review_deadline = time.monotonic() + _SCAN_DEADLINE_SECONDS
            need_repository = any(
                not _is_binary(blobs[path]) and _content_hits(
                    blobs[path].decode("utf-8", "replace"), path, lambda _line: (), max_findings=1,
                ) for path in paths
            )
            review_evaluation, exchanges = _prepare_review_evaluation(
                repo_root, review_deadline, need_repository=need_repository,
            )
        outcome = _scan_content_blobs(
            mode,
            paths,
            blobs,
            find_machine_paths,
            machine_path_lines_by_path=machine_path_lines_by_path,
            review_evaluation=(review_evaluation if review_evaluation is not None and review_evaluation.read.usable_records else None),
            review_bindings=review_bindings,
        )
        if review_evaluation is not None:
            def recheck_staged() -> bool:
                current_bindings = {}
                current_paths, current_blobs, current_lines = _tracked_files(review_bindings=current_bindings)
                return (current_paths == paths and current_bindings == review_bindings
                        and current_blobs == blobs and current_lines == machine_path_lines_by_path)

            outcome = _finalize_review_evaluation(
                outcome, review_evaluation, repo_root, review_deadline, recheck_staged, exchanges,
            )
        return _emit_outcome(outcome)
    except KeyboardInterrupt:
        print(
            "publication-safety: refusing id=PS-INPUT-REFUSAL "
            "phase=input reason=cancelled",
            file=sys.stderr,
        )
        return 2
    except RuntimeError as exc:
        review_reason = _review_failure_reason(exc)
        if review_reason is not None:
            print(
                "publication-safety: refusing id=PS-INPUT-REFUSAL "
                f"phase=input reason={review_reason}", file=sys.stderr,
            )
        elif exc.args == ("not inside a git repository",):
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
