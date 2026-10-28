#!/usr/bin/env python3
"""Technical publication backstop for an actual supported Git push.

Root owns genuine human review and approval of the specific publication. This
hook does not interpret chat consent. It qualifies the real repository, source,
remote endpoint and destination; runs one fresh complete range scan through its
existing captured implementation and policy; and rechecks the technical target.
A missing transcript, review marker, consent index or GitHub PR API is irrelevant.
Actual host restrictions and server/Git authorization remain independent.
"""
from __future__ import annotations

import base64
import binascii
import json
import hashlib
import os
import re
import secrets
import shlex
import shutil
import stat
import subprocess
import sys
import threading
import time
import types
from dataclasses import (
    dataclass,
    field,
    replace,
)
from enum import (
    Enum,
)
from pathlib import (
    Path,
)
from typing import (
    Callable,
    NamedTuple,
)
from urllib.parse import (
    quote,
    unquote_to_bytes,
    urlsplit,
)


PUBLICATION_GATE_REVISION = "G-technical-publication-scan-20261027"

from git_push_gate_preflight import (
    PUBLICATION_PREFLIGHT_REVISION,
    PreflightResult,
    WorkdirDiagnostic,
    validate_preflight_result,
    validate_workdir_diagnostic,
    build_preflight_from_stdin,
    absolute_literal_root_context,
    literal_direct_command,
    PrRouteDenied,
    classify_generic_push,
    NATIVE_PUBLICATION_HOOK,
    git_prefix_configuration,
    native_push_invocation,
    native_push_refspecs,
)


PROCESS_OUTPUT_BYTE_CAP = 256 * 1024
PROCESS_TIMEOUT_SECONDS = 8.0
ORACLE_TIMEOUT_SECONDS = 45.0
SCAN_SNAPSHOT_BYTE_CAP = 1024 * 1024
SCAN_OUTPUT_BYTE_CAP = 256 * 1024
SCAN_TIMEOUT_SECONDS = 300.0
SCAN_SETTLEMENT_ATTEMPT_SECONDS = 3.0
SCAN_SETTLEMENT_MAX_ENTRIES = 2


@dataclass(frozen=True)
class GitObjectFormat:
    name: str
    hex_length: int
    oid_re: re.Pattern[str]

    def matches(self, value: str) -> bool:
        return self.oid_re.fullmatch(value) is not None


_SHA1_OBJECT_FORMAT = GitObjectFormat(
    "sha1", 40, re.compile(r"[0-9a-fA-F]{40}")
)
_SHA256_OBJECT_FORMAT = GitObjectFormat(
    "sha256", 64, re.compile(r"[0-9a-fA-F]{64}")
)
_SUPPORTED_OBJECT_FORMATS = {
    value.name: value for value in (_SHA1_OBJECT_FORMAT, _SHA256_OBJECT_FORMAT)
}
_LOWERCASE_OID_PATTERN = r"(?:[0-9a-f]{40}|[0-9a-f]{64})"
SCAN_DENIAL_REASONS = {
    "PGG-SCAN-PROVENANCE": "The canonical gate-owned range scanner could not be established.",
    "PRG-SCAN-PROVENANCE": "The canonical gate-owned range scanner could not be established.",
    "PGG-SCAN-IDENTITY-DRIFT": "The trusted scanner boundary changed during evaluation.",
    "PRG-SCAN-IDENTITY-DRIFT": "The trusted scanner boundary changed during evaluation.",
    "PGG-SCAN-EXECUTION": "The canonical range scanner did not complete and reap within its fixed bounds.",
    "PRG-SCAN-EXECUTION": "The canonical range scanner did not complete and reap within its fixed bounds.",
    "PGG-SCAN-FINDING": "The canonical range scanner reported a redacted publication-safety finding.",
    "PRG-SCAN-FINDING": "The canonical range scanner reported a redacted publication-safety finding.",
    "PGG-SCAN-REFUSAL": "The canonical range scanner returned a typed fail-closed refusal.",
    "PRG-SCAN-REFUSAL": "The canonical range scanner returned a typed fail-closed refusal.",
    "PGG-SCAN-CORRELATION": "The trusted scanner result did not match its exact pending invocation.",
    "PRG-SCAN-CORRELATION": "The trusted scanner result did not match its exact pending invocation.",
}


def _detect_git_object_format(
    repository_workdir: str,
    git_exe: str,
    failure_id: str,
    *,
    deadline: float | None = None,
) -> GitObjectFormat:
    active_deadline = deadline or (time.monotonic() + ORACLE_TIMEOUT_SECONDS)
    _, output = _run_text(
        [git_exe, "rev-parse", "--show-object-format"],
        active_deadline,
        failure_id,
        repository_workdir,
    )
    rows = output.splitlines()
    if len(rows) != 1:
        raise PrRouteDenied(failure_id)
    object_format = _SUPPORTED_OBJECT_FORMATS.get(rows[0])
    if object_format is None:
        raise PrRouteDenied(failure_id)
    return object_format


class ProcessResult(NamedTuple):
    returncode: int
    stdout: bytes
    stderr: bytes


class PushScanBinding(NamedTuple):
    route: str
    remote: str
    destination: str
    source_oid: str
    head_oid: str


@dataclass(frozen=True)
class NativePushInput:
    """The actual Git callback inputs, never reconstructed from ref names."""

    remote_name: str
    endpoint: str
    wire: bytes


@dataclass(frozen=True)
class NativePushScanBinding:
    object_format: str
    endpoint_identity: str
    input_sha256: str
    selection_sha256: str
    repository_observation_sha256: str
    route: str = field(init=False, default="generic")


def _native_canonical_bytes(value: object) -> bytes:
    """Native argv may contain surrogates; preserve them with JSON escaping."""
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("ascii")


def _native_endpoint_identity(endpoint: str) -> str:
    encoded = json.dumps(endpoint, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class InterpreterIdentity(NamedTuple):
    absolute_resolved_path: str
    file_identity: tuple[int, ...]


TrustedInterpreterIdentity = InterpreterIdentity


@dataclass(frozen=True)
class SourceNode:
    role: str
    expected_path: str
    file_identity: tuple[int, ...]
    link_count: int
    size: int
    sha256: str
    source: bytes


@dataclass(frozen=True)
class SourceLayout:
    name: str
    gate_suffix: tuple[str, ...]
    trust_root_up: int
    role_paths: tuple[tuple[str, str], ...]


SOURCE_ROLE_ORDER = (
    "gate", "hook_common", "classifier", "posix_helper", "windows_job",
    "scanner", "publication_review_policy", "linked_runtime_subroots",
)


SOURCE_LAYOUTS = (
    SourceLayout(
        "universal", ("scripts", "universal-hooks", "scripts", "check-git-push-gate.py"), 2,
        (
            ("gate", "universal-hooks/scripts/check-git-push-gate.py"),
            ("hook_common", "universal-hooks/scripts/hook_common.py"),
            ("classifier", "universal-hooks/hooks/check-machine-local-path.py"),
            ("posix_helper", "process_supervision/posix_process_group.py"),
            ("windows_job", "process_supervision/windows_job.py"),
            ("scanner", "universal-hooks/scripts/check-publication-safety.py"),
            ("publication_review_policy", "universal-hooks/scripts/publication_review_policy.py"),
            ("linked_runtime_subroots", "linked_runtime_subroots.py"),
        ),
    ),
    SourceLayout(
        "codex-source", ("src.codex", "skills", "lead", "scripts", "check-git-push-gate.py"), 4,
        (
            ("gate", "src.codex/skills/lead/scripts/check-git-push-gate.py"),
            ("hook_common", "src.codex/skills/lead/scripts/hook_common.py"),
            ("classifier", "src.codex/skills/lead/hooks/check-machine-local-path.py"),
            ("posix_helper", "scripts/process_supervision/posix_process_group.py"),
            ("windows_job", "scripts/process_supervision/windows_job.py"),
            ("scanner", "src.codex/skills/lead/scripts/check-publication-safety.py"),
            ("publication_review_policy", "src.codex/skills/lead/scripts/publication_review_policy.py"),
            ("linked_runtime_subroots", "scripts/linked_runtime_subroots.py"),
        ),
    ),
    SourceLayout(
        "claude-source", ("src.claude", "agents", "scripts", "check-git-push-gate.py"), 3,
        (
            ("gate", "src.claude/agents/scripts/check-git-push-gate.py"),
            ("hook_common", "src.claude/agents/scripts/hook_common.py"),
            ("classifier", "src.claude/agents/hooks/check-machine-local-path.py"),
            ("posix_helper", "scripts/process_supervision/posix_process_group.py"),
            ("windows_job", "scripts/process_supervision/windows_job.py"),
            ("scanner", "src.claude/agents/scripts/check-publication-safety.py"),
            ("publication_review_policy", "src.claude/agents/scripts/publication_review_policy.py"),
            ("linked_runtime_subroots", "scripts/linked_runtime_subroots.py"),
        ),
    ),
    SourceLayout(
        "component", ("scripts", "check-git-push-gate.py"), 1,
        (
            ("gate", "scripts/check-git-push-gate.py"),
            ("hook_common", "scripts/hook_common.py"),
            ("classifier", "hooks/check-machine-local-path.py"),
            ("posix_helper", "scripts/process_supervision/posix_process_group.py"),
            ("windows_job", "scripts/process_supervision/windows_job.py"),
            ("scanner", "scripts/check-publication-safety.py"),
            ("publication_review_policy", "scripts/publication_review_policy.py"),
            ("linked_runtime_subroots", "scripts/linked_runtime_subroots.py"),
        ),
    ),
)


@dataclass(frozen=True)
class PathComponentIdentity:
    root_relative_name: str
    kind: str
    identity: tuple[int, ...]


@dataclass(frozen=True)
class RootLocatorIdentity:
    logical_gate: str
    logical_root: str
    kind: str
    locator_identity: tuple[int, ...]
    raw_target: str | None
    physical_root: str
    physical_root_identity: tuple[int, ...]
    physical_gate: str
    gate_identity: tuple[int, ...]


@dataclass(frozen=True)
class CanonicalSourceClosure:
    layout: SourceLayout
    trust_root: PathComponentIdentity
    components: tuple[PathComponentIdentity, ...]
    nodes: tuple[SourceNode, ...]
    digest: str
    gate_identity: tuple[int, ...]
    bootstrap_digest: str
    interpreter_identity: InterpreterIdentity
    root_locator: RootLocatorIdentity


@dataclass(frozen=True)
class CapturedReviewModules:
    policy_module: object
    linked_module: object
    registered: tuple[tuple[str, object], ...]


@dataclass(frozen=True)
class CapturedReviewPayload:
    modules: CapturedReviewModules
    snapshot: object
    snapshot_id: str
    repository_observation: object
    repository: object | None
    origin_is_outside_repository: bool
    payload_bytes: bytes
    payload_sha256: str

    @property
    def policy_module(self) -> object:
        return self.modules.policy_module

    def __post_init__(self) -> None:
        if re.fullmatch(r"[0-9a-f]{64}", self.snapshot_id) is None:
            raise ValueError("review-snapshot-id")
        if type(self.payload_bytes) is not bytes:
            raise ValueError("review-payload-bytes")
        if hashlib.sha256(self.payload_bytes).hexdigest() != self.payload_sha256:
            raise ValueError("review-payload-digest")


class PendingState(str, Enum):
    PREPARED = "prepared"
    CHILD_OWNED = "child-owned"
    SETTLING = "settling"
    SETTLED = "settled"
    CORRELATED = "correlated"
    CONSUMED = "consumed"
    FAILED = "failed"


@dataclass(eq=False)
class PendingScanInvocation:
    invocation_id: str
    attempt_id: str
    binding: PushScanBinding | NativePushScanBinding
    closure: CanonicalSourceClosure | None
    interpreter_identity: InterpreterIdentity
    exact_argv: tuple[str, ...]
    result_slot: object
    captured_review: CapturedReviewPayload | None = None
    created_tick: float = field(default_factory=time.monotonic)
    authorization_deadline: float | None = None
    state: PendingState = field(init=False, default=PendingState.PREPARED)
    child_identity: int | None = field(init=False, default=None)
    supervisor: object | None = field(init=False, default=None)
    settlement: object | None = field(init=False, default=None)
    closure_fresh_tick: float | None = field(init=False, default=None)
    binding_fresh_tick: float | None = field(init=False, default=None)
    correlation_id: str | None = field(init=False, default=None)
    consumption_id: str | None = field(init=False, default=None)
    _transition_lock: threading.Lock = field(init=False, repr=False, default_factory=threading.Lock)
    _identity_sealed: bool = field(init=False, repr=False, default=False)

    def __setattr__(self, name, value):
        if getattr(self, "_identity_sealed", False) and name in {
            "invocation_id", "attempt_id", "binding", "closure",
            "interpreter_identity", "exact_argv", "result_slot",
            "captured_review",
            "created_tick", "authorization_deadline",
        }:
            raise AttributeError("pending invocation identity is immutable")
        object.__setattr__(self, name, value)

    def __post_init__(self) -> None:
        if self.authorization_deadline is None:
            self.authorization_deadline = (
                self.created_tick + SCAN_TIMEOUT_SECONDS
                + SCAN_SETTLEMENT_ATTEMPT_SECONDS * SCAN_SETTLEMENT_MAX_ENTRIES
            )
        self._identity_sealed = True

    def __copy__(self):
        raise TypeError("pending invocation is non-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("pending invocation is non-copyable")

    def correlate_and_consume_once(
        self,
        launched: "LaunchedScanInvocation",
        records: tuple["TrustedExecutionRecord", ...],
        closure_after: CanonicalSourceClosure,
        interpreter_after: InterpreterIdentity,
        binding_after: PushScanBinding | NativePushScanBinding,
        freshness_tick: float,
        *,
        finalize_review: Callable[
            ["QualifiedPublicationEvidence"], tuple[dict, list[list[str]]]
        ] | None = None,
    ) -> "ConsumedAuthoritativeEvidence":
        prefix = "PGG" if self.binding.route == "generic" else "PRG"
        with self._transition_lock:
            if self.state is PendingState.CONSUMED:
                raise PrRouteDenied(prefix + "-RECEIPT-USED")
            if (
                self.state is not PendingState.SETTLED
                or time.monotonic() > float(self.authorization_deadline)
                or len(records) != 1
            ):
                self.state = PendingState.FAILED
                raise PrRouteDenied(prefix + "-SCAN-CORRELATION")
            execution = records[0]
            supervisor = launched.supervisor_token
            settlement = self.settlement
            certificate = (
                settlement.certificate if isinstance(settlement, GateSettlement) else None
            )
            actual_pid = getattr(getattr(supervisor, "process", None), "pid", None)
            if (
                launched.pending is not self
                or launched.invocation_id != self.invocation_id
                or launched.attempt_id != self.attempt_id
                or launched.binding != self.binding
                or launched.exact_argv != self.exact_argv
                or launched.result_slot is not self.result_slot
                or execution.pending is not self
                or execution.launched is not launched
                or execution.result_slot is not self.result_slot
                or supervisor is not self.supervisor
                or not isinstance(supervisor, ChildSupervisor)
                or launched.child_handle != self.child_identity
                or actual_pid != self.child_identity
                or supervisor.child_identity != self.child_identity
                or execution.settlement is not settlement
                or not isinstance(settlement, GateSettlement)
                or not settlement.complete
                or not settlement.execution_eligible
                or certificate is None
                or certificate.supervisor_id != supervisor.supervisor_id
                or certificate.child_identity != self.child_identity
                or closure_after != self.closure
                or execution.closure_after != closure_after
                or interpreter_after != self.interpreter_identity
                or execution.interpreter_identity_after != interpreter_after
                or execution.provenance_verdict != "trusted"
                or binding_after != self.binding
                or freshness_tick <= certificate.verified_at_monotonic_tick
            ):
                self.state = PendingState.FAILED
                raise PrRouteDenied(prefix + "-SCAN-CORRELATION")
            self.closure_fresh_tick = freshness_tick
            self.binding_fresh_tick = freshness_tick
            self.correlation_id = secrets.token_hex(16)
            self.state = PendingState.CORRELATED
            review_finalization = None
            review_used_list = None
            try:
                if not execution.bounded_completion:
                    raise PrRouteDenied(prefix + "-SCAN-EXECUTION")
                combined = execution.stdout + execution.stderr
                try:
                    text = combined.decode("utf-8", errors="strict")
                except UnicodeDecodeError:
                    raise PrRouteDenied(prefix + "-SCAN-EXECUTION") from None
                parsed = parse_publication_safety_observation(text)
                if execution.exit_code == 1:
                    raise PrRouteDenied(prefix + "-SCAN-FINDING")
                if execution.exit_code == 2:
                    raise PrRouteDenied(prefix + "-SCAN-REFUSAL")
                if execution.exit_code != 0:
                    raise PrRouteDenied(prefix + "-SCAN-EXECUTION")
                receipt = parsed.receipt
                if isinstance(self.binding, NativePushScanBinding):
                    if parsed.kind not in {"valid-v4", "qualified-v4"} or not isinstance(receipt, NativePushReceiptV4):
                        raise PrRouteDenied("PGG-NATIVE-RECEIPT-VERSION")
                    _verify_native_receipt_binding(receipt, self.binding)
                else:
                    if parsed.kind not in {"valid-v3", "qualified-v3"} or not isinstance(receipt, RangeReceiptV3):
                        mismatch = "PGG-RANGE-RECEIPT-VERSION" if prefix == "PGG" else "PRG-RECEIPT-MISMATCH"
                        raise PrRouteDenied(mismatch)
                    if (receipt.remote, receipt.destination) != (
                        self.binding.remote, self.binding.destination
                    ):
                        mismatch = "PGG-RANGE-BINDING" if prefix == "PGG" else "PRG-RECEIPT-MISMATCH"
                        raise PrRouteDenied(mismatch)
                    if (
                        receipt.source != self.binding.source_oid
                        or receipt.tip != self.binding.source_oid
                        or (self.binding.route != "generic" and self.binding.source_oid != self.binding.head_oid)
                    ):
                        mismatch = "PGG-RANGE-TIP-BINDING" if prefix == "PGG" else "PRG-RECEIPT-MISMATCH"
                        raise PrRouteDenied(mismatch)
                if parsed.kind in {"qualified-v3", "qualified-v4"}:
                    qualification = parsed.qualification
                    captured_review = self.captured_review
                    if (
                        execution.stderr
                        or qualification is None
                        or captured_review is None
                        or not captured_review.origin_is_outside_repository
                        or qualification.policy_snapshot_id != captured_review.snapshot_id
                        or not callable(finalize_review)
                    ):
                        raise PrRouteDenied(prefix + "-SCAN-CORRELATION")
                    finalized = finalize_review(qualification)
                    if type(finalized) is not tuple or len(finalized) != 2:
                        raise PrRouteDenied(prefix + "-SCAN-CORRELATION")
                    review_finalization, review_used_list = finalized
                    finalization_keys = {
                        "inputSnapshotId", "usedList", "currentSnapshotId",
                        "repositorySha256", "status", "reason", "resourcesSettled",
                    }
                    if (
                        type(review_finalization) is not dict
                        or set(review_finalization) != finalization_keys
                        or review_finalization.get("inputSnapshotId") != captured_review.snapshot_id
                        or type(review_used_list) is not list
                        or any(
                            type(row) is not list
                            or len(row) != 2
                            or type(row[0]) is not str
                            or type(row[1]) is not str
                            for row in review_used_list
                        )
                        or review_finalization.get("usedList") != review_used_list
                        or review_finalization.get("status") != "valid"
                        or review_finalization.get("reason") != "none"
                        or review_finalization.get("resourcesSettled") is not True
                    ):
                        raise PrRouteDenied(prefix + "-SCAN-CORRELATION")
                if time.monotonic() > float(self.authorization_deadline):
                    raise PrRouteDenied(prefix + "-SCAN-CORRELATION")
            except BaseException:
                self.state = PendingState.FAILED
                raise
            self.consumption_id = secrets.token_hex(16)
            self.state = PendingState.CONSUMED
            return ConsumedAuthoritativeEvidence(
                self.invocation_id, self.binding, parsed, self.consumption_id, execution,
                review_finalization,
            )


class LaunchedScanInvocation(NamedTuple):
    pending: PendingScanInvocation
    child_handle: int
    supervisor_token: object
    invocation_id: str
    attempt_id: str
    binding: PushScanBinding | NativePushScanBinding
    exact_argv: tuple[str, ...]
    result_slot: object


@dataclass(frozen=True)
class TrustedExecutionRecord:
    pending: PendingScanInvocation
    launched: LaunchedScanInvocation
    result_slot: object
    bounded_completion: bool
    exit_code: int
    stdout: bytes
    stderr: bytes
    settlement: object
    closure_after: CanonicalSourceClosure
    interpreter_identity_after: InterpreterIdentity
    provenance_verdict: str


# R2 public names remain aliases of the single lifecycle types.


class RangeReceiptV3(NamedTuple):
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


class QualifiedPublicationEvidence(NamedTuple):
    policy_snapshot_id: str
    used_decisions_b64: str
    applied: int
    applied_set: str
    examined: int | None = None


class NativePushReceiptV4(NamedTuple):
    object_format: str
    endpoint_identity: str
    input_sha256: str
    update_set_sha256: str
    selection_sha256: str
    repository_observation_sha256: str
    updates: int
    commits: int
    commit_set: str
    objects: int
    object_set: str
    coverage: str
    tags: int
    blobs: int
    blob_set: str
    blob_bytes: int
    text: int
    binary: int
    subjects: int
    subject_set: str
    paths: int
    path_set: str


def _verify_native_receipt_binding(receipt: NativePushReceiptV4, binding: NativePushScanBinding) -> None:
    if (
        receipt.object_format != binding.object_format
        or receipt.endpoint_identity != binding.endpoint_identity
        or receipt.input_sha256 != binding.input_sha256
        or receipt.selection_sha256 != binding.selection_sha256
        or receipt.repository_observation_sha256 != binding.repository_observation_sha256
    ):
        raise PrRouteDenied("PGG-NATIVE-RECEIPT-BINDING")


class PublicationSafetyObservation(NamedTuple):
    kind: str
    receipt: RangeReceiptV3 | NativePushReceiptV4 | None
    qualification: QualifiedPublicationEvidence | None = None


class ConsumedAuthoritativeEvidence(NamedTuple):
    invocation_id: str
    binding: PushScanBinding | NativePushScanBinding
    parsed_outcome: PublicationSafetyObservation
    consumption_id: str
    execution: TrustedExecutionRecord | None = None
    review_finalization: dict | None = None


# Decode only the result of the gate-owned scanner child.


SCAN_CLEAN_TRACKED_REGEX = re.compile(
    r"^publication-safety:\s*clean\s*\(\s*tracked\s*,\s*examined\s+([1-9]\d*)\s+files?\s*\)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

SCAN_FAILURE_MARKER_REGEX = re.compile(
    r"publication-safety scan found potential tracked-content leak markers",
    re.IGNORECASE,
)

SCAN_CLEAN_RANGE_REGEX = re.compile(
    r"^publication-safety:\s*clean\s*\(\s*range\s*,\s*examined\s+(?P<count>[1-9]\d*)\s+files?\s*,"
    rf"\s*remote\s+(?P<remote>\S+)\s*,\s*dst\s+(?P<dst>\S+)\s*,\s*tip\s+(?P<tip>{_LOWERCASE_OID_PATTERN})\s*\)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

SCAN_CLEAN_RANGE_V3_REGEX = re.compile(
    r"^publication-safety: clean \(range, receipt=v3, "
    r"commits=(?P<commits>[1-9]\d*), "
    r"commit-set=(?P<commit_set>[0-9a-f]{64}), messages=complete, "
    r"objects=(?P<objects>[1-9]\d*), object-set=(?P<object_set>[0-9a-f]{64}), "
    r"blobs=(?P<blobs>0|[1-9]\d*), blob-set=(?P<blob_set>[0-9a-f]{64}), "
    r"blob-bytes=(?P<blob_bytes>0|[1-9]\d*), text=(?P<text>0|[1-9]\d*), "
    r"binary=(?P<binary>0|[1-9]\d*), subjects=(?P<subjects>0|[1-9]\d*), "
    r"subject-set=(?P<subject_set>[0-9a-f]{64}), paths=(?P<paths>0|[1-9]\d*), "
    r"path-set=(?P<path_set>[0-9a-f]{64}), history=complete, "
    r"remote=(?P<remote>[A-Za-z0-9._~%-]+), "
    r"dst=(?P<dst>[A-Za-z0-9._~%-]+), "
    rf"src=(?P<src>[A-Za-z0-9._~%-]+), tip=(?P<tip>{_LOWERCASE_OID_PATTERN})\)$",
    re.MULTILINE,
)
SCAN_QUALIFIED_STAGED_REGEX = re.compile(
    r"\Apublication-safety: qualified \(staged, "
    r"examined=(?P<examined>0|[1-9][0-9]*), "
    r"policy-snapshot=(?P<policy_snapshot>[0-9a-f]{64}), "
    r"used-decisions=(?P<used_decisions>[A-Za-z0-9+/]+={0,2}), "
    r"applied=(?P<applied>[1-9][0-9]*), "
    r"applied-set=(?P<applied_set>[0-9a-f]{64}), "
    r"unresolved=0, evaluation=complete\)\n\Z"
)
SCAN_QUALIFIED_RANGE_V3_REGEX = re.compile(
    r"\Apublication-safety: qualified \(range, receipt=v3, "
    r"commits=(?P<commits>[1-9][0-9]*), "
    r"commit-set=(?P<commit_set>[0-9a-f]{64}), messages=complete, "
    r"objects=(?P<objects>[1-9][0-9]*), "
    r"object-set=(?P<object_set>[0-9a-f]{64}), "
    r"blobs=(?P<blobs>0|[1-9][0-9]*), "
    r"blob-set=(?P<blob_set>[0-9a-f]{64}), "
    r"blob-bytes=(?P<blob_bytes>0|[1-9][0-9]*), "
    r"text=(?P<text>0|[1-9][0-9]*), "
    r"binary=(?P<binary>0|[1-9][0-9]*), "
    r"subjects=(?P<subjects>0|[1-9][0-9]*), "
    r"subject-set=(?P<subject_set>[0-9a-f]{64}), "
    r"paths=(?P<paths>0|[1-9][0-9]*), "
    r"path-set=(?P<path_set>[0-9a-f]{64}), history=complete, "
    r"remote=(?P<remote>[A-Za-z0-9._~%-]+), "
    r"dst=(?P<dst>[A-Za-z0-9._~%-]+), "
    r"src=(?P<src>[A-Za-z0-9._~%-]+), "
    rf"tip=(?P<tip>{_LOWERCASE_OID_PATTERN}), "
    r"policy-snapshot=(?P<policy_snapshot>[0-9a-f]{64}), "
    r"used-decisions=(?P<used_decisions>[A-Za-z0-9+/]+={0,2}), "
    r"applied=(?P<applied>[1-9][0-9]*), "
    r"applied-set=(?P<applied_set>[0-9a-f]{64}), "
    r"unresolved=0, evaluation=complete\)\n\Z"
)
SCAN_CLEAN_PATH_REGEX = re.compile(
    r"^publication-safety:\s*clean\s*\(\s*path\s*,\s*examined\s+\d+\s+files?[^\r\n]*\)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
SCAN_TYPED_FAILURE_REGEX = re.compile(
    r"\bPS-(?:FINDING-(?:CONTENT|COMMIT-MESSAGE)|MSG-[A-Z-]+|INPUT-REFUSAL)\b"
)

def _decode_canonical_receipt_token(token: str) -> str | None:
    if not token:
        return None
    try:
        value = unquote_to_bytes(token).decode("utf-8", "strict")
    except (UnicodeDecodeError, ValueError):
        return None
    if not value or any(ord(char) < 32 or ord(char) == 127 for char in value):
        return None
    if quote(value, safe="-._~", encoding="utf-8", errors="strict") != token:
        return None
    return value


def _valid_used_decisions_b64(value: str) -> bool:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        return False
    return bool(decoded) and base64.b64encode(decoded).decode("ascii") == value


def _parse_native_publication_observation(text: str) -> PublicationSafetyObservation:
    """Read the single V4 frame produced by this invocation's captured child."""
    try:
        value = _strict_json(text, dict, "PGG-SCAN-CORRELATION")
    except (PrRouteDenied, ValueError, TypeError):
        return PublicationSafetyObservation("malformed", None)
    counts = ("updates", "commits", "objects", "tags", "blobs", "blobBytes", "text", "binary", "subjects", "paths")
    digests = (
        "inputSha256", "updateSetSha256", "selectionSha256", "repositoryObservationSha256",
        "commitSetSha256", "objectSetSha256", "coverageSha256", "blobSetSha256",
        "subjectSetSha256", "pathSetSha256",
    )
    if (
        set(value) != {
            "kind", "version", "status", "coverageKind", "objectFormat", "endpointIdentity", "review",
            *counts, *digests,
        }
        or value.get("kind") != "publication-safety-native"
        or type(value.get("version")) is not int or value["version"] != 4
        or value.get("status") not in {"clean", "qualified"}
        or value.get("coverageKind") != "objects"
        or value.get("objectFormat") not in _SUPPORTED_OBJECT_FORMATS
        or type(value.get("endpointIdentity")) is not str
        or re.fullmatch(r"sha256:[0-9a-f]{64}", value["endpointIdentity"]) is None
        or any(type(value.get(key)) is not int or value[key] < 0 for key in counts)
        or any(type(value.get(key)) is not str or re.fullmatch(r"[0-9a-f]{64}", value[key]) is None for key in digests)
    ):
        return PublicationSafetyObservation("malformed", None)
    if (
        value["commits"] + value["tags"] + value["blobs"] > value["objects"]
        or value["text"] + value["binary"] != value["blobs"]
        or (value["objects"] > 0 and value["updates"] == 0)
        or (value["objects"] == 0 and any(value[key] != 0 for key in counts if key != "updates"))
        or (value["blobs"] == 0 and any(value[key] != 0 for key in ("blobBytes", "text", "binary", "paths")))
        or value["paths"] > value["subjects"]
        or value["blobs"] > value["subjects"]
    ):
        return PublicationSafetyObservation("malformed", None)
    qualification = None
    review = value["review"]
    if value["status"] == "qualified":
        if (
            type(review) is not dict
            or set(review) != {"snapshotId", "usedDecisions", "applied", "appliedSet", "usedToken"}
            or type(review.get("snapshotId")) is not str
            or re.fullmatch(r"[0-9a-f]{64}", review["snapshotId"]) is None
            or type(review.get("applied")) is not int or review["applied"] <= 0
            or type(review.get("appliedSet")) is not str
            or re.fullmatch(r"[0-9a-f]{64}", review["appliedSet"]) is None
            or type(review.get("usedToken")) is not str
            or not _valid_used_decisions_b64(review["usedToken"])
            or type(review.get("usedDecisions")) is not list
        ):
            return PublicationSafetyObservation("malformed", None)
        try:
            used_bytes = base64.b64decode(review["usedToken"], validate=True)
            used = _strict_json(used_bytes.decode("ascii"), list, "PGG-SCAN-CORRELATION")
        except (ValueError, PrRouteDenied, UnicodeError, binascii.Error):
            return PublicationSafetyObservation("malformed", None)
        if (
            not used or any(
                type(row) is not list or len(row) != 2
                or type(row[0]) is not str or not row[0]
                or type(row[1]) is not str or re.fullmatch(r"[0-9a-f]{64}", row[1]) is None
                for row in used
            )
            or used != [list(row) for row in sorted(set(tuple(row) for row in used))]
            or used != review["usedDecisions"] or _native_canonical_bytes(used) != used_bytes
        ):
            return PublicationSafetyObservation("malformed", None)
        if value["objects"] == 0 or value["text"] == 0 or value["blobBytes"] == 0:
            return PublicationSafetyObservation("malformed", None)
        qualification = QualifiedPublicationEvidence(
            review["snapshotId"], review["usedToken"], review["applied"], review["appliedSet"],
        )
    elif review is not None:
        return PublicationSafetyObservation("malformed", None)
    receipt = NativePushReceiptV4(
        value["objectFormat"], value["endpointIdentity"], value["inputSha256"],
        value["updateSetSha256"], value["selectionSha256"], value["repositoryObservationSha256"],
        value["updates"], value["commits"], value["commitSetSha256"], value["objects"],
        value["objectSetSha256"], value["coverageSha256"], value["tags"], value["blobs"],
        value["blobSetSha256"], value["blobBytes"], value["text"], value["binary"],
        value["subjects"], value["subjectSetSha256"], value["paths"], value["pathSetSha256"],
    )
    return PublicationSafetyObservation("qualified-v4" if qualification else "valid-v4", receipt, qualification)


def parse_publication_safety_observation(text: str) -> PublicationSafetyObservation:
    text = text.replace("\r\n", "\n")
    if "\r" in text:
        return PublicationSafetyObservation("malformed", None)
    if text.lstrip().startswith("{"):
        return _parse_native_publication_observation(text)
    if "publication-safety: qualified" in text:
        staged = SCAN_QUALIFIED_STAGED_REGEX.fullmatch(text)
        if staged is not None:
            used_decisions = staged.group("used_decisions")
            examined = int(staged.group("examined"))
            if examined == 0 or not _valid_used_decisions_b64(used_decisions):
                return PublicationSafetyObservation("malformed", None)
            return PublicationSafetyObservation(
                "qualified-staged", None,
                QualifiedPublicationEvidence(
                    staged.group("policy_snapshot"), used_decisions,
                    int(staged.group("applied")), staged.group("applied_set"),
                    examined,
                ),
            )

        qualified = SCAN_QUALIFIED_RANGE_V3_REGEX.fullmatch(text)
        if qualified is None:
            return PublicationSafetyObservation("malformed", None)
        used_decisions = qualified.group("used_decisions")
        if not _valid_used_decisions_b64(used_decisions):
            return PublicationSafetyObservation("malformed", None)
        # Route the shared V3 graph/count/selection invariants through the
        # existing parser. The qualified spelling changes disposition evidence,
        # not the range receipt or its graph contract.
        v3_text = (
            "publication-safety: clean (range, receipt=v3, "
            f"commits={qualified.group('commits')}, "
            f"commit-set={qualified.group('commit_set')}, messages=complete, "
            f"objects={qualified.group('objects')}, "
            f"object-set={qualified.group('object_set')}, "
            f"blobs={qualified.group('blobs')}, "
            f"blob-set={qualified.group('blob_set')}, "
            f"blob-bytes={qualified.group('blob_bytes')}, "
            f"text={qualified.group('text')}, "
            f"binary={qualified.group('binary')}, "
            f"subjects={qualified.group('subjects')}, "
            f"subject-set={qualified.group('subject_set')}, "
            f"paths={qualified.group('paths')}, "
            f"path-set={qualified.group('path_set')}, history=complete, "
            f"remote={qualified.group('remote')}, "
            f"dst={qualified.group('dst')}, "
            f"src={qualified.group('src')}, "
            f"tip={qualified.group('tip')})\n"
        )
        parsed_v3 = parse_publication_safety_observation(v3_text)
        if parsed_v3.kind != "valid-v3" or parsed_v3.receipt is None:
            return PublicationSafetyObservation("malformed", None)
        if parsed_v3.receipt.text <= 0 or parsed_v3.receipt.blob_bytes <= 0:
            return PublicationSafetyObservation("malformed", None)
        return PublicationSafetyObservation(
            "qualified-v3", parsed_v3.receipt,
            QualifiedPublicationEvidence(
                qualified.group("policy_snapshot"), used_decisions,
                int(qualified.group("applied")), qualified.group("applied_set"),
            ),
        )

    v3_matches = list(SCAN_CLEAN_RANGE_V3_REGEX.finditer(text))
    clean_lines = [
        line for line in text.splitlines()
        if line.startswith("publication-safety: clean (")
    ]
    has_failure = bool(
        SCAN_FAILURE_MARKER_REGEX.search(text) or SCAN_TYPED_FAILURE_REGEX.search(text)
    )
    if len(v3_matches) == 1 and len(clean_lines) == 1 and not has_failure:
        match = v3_matches[0]
        remote = _decode_canonical_receipt_token(match.group("remote"))
        destination = _decode_canonical_receipt_token(match.group("dst"))
        source = _decode_canonical_receipt_token(match.group("src"))
        if remote is None or destination is None or source is None:
            return PublicationSafetyObservation("malformed", None)
        counts = {
            name: int(match.group(name))
            for name in (
                "commits", "objects", "blobs", "blob_bytes", "text",
                "binary", "subjects", "paths",
            )
        }
        if (
            counts["commits"] > counts["objects"]
            or counts["blobs"] > counts["objects"]
            or counts["text"] + counts["binary"] != counts["blobs"]
            or (
                counts["blobs"] == 0
                and any(counts[name] != 0 for name in (
                    "blob_bytes", "text", "binary", "subjects", "paths"
                ))
            )
            or (
                counts["blobs"] > 0
                and not (
                    counts["subjects"] >= counts["paths"] >= counts["blobs"]
                )
            )
        ):
            return PublicationSafetyObservation("malformed", None)
        return PublicationSafetyObservation(
            "valid-v3",
            RangeReceiptV3(
                counts["commits"],
                match.group("commit_set"),
                counts["objects"],
                match.group("object_set"),
                counts["blobs"],
                match.group("blob_set"),
                counts["blob_bytes"],
                counts["text"],
                counts["binary"],
                counts["subjects"],
                match.group("subject_set"),
                counts["paths"],
                match.group("path_set"),
                remote,
                destination,
                source,
                match.group("tip"),
            ),
        )
    if v3_matches or "publication-safety: clean (range, receipt=v3" in text:
        return PublicationSafetyObservation("malformed", None)
    if "publication-safety: clean (range, receipt=v2" in text:
        return (
            PublicationSafetyObservation("legacy-nonauthorizing", None)
            if len(clean_lines) == 1 and not has_failure
            else PublicationSafetyObservation("malformed", None)
        )
    if (
        SCAN_CLEAN_TRACKED_REGEX.search(text)
        or SCAN_CLEAN_RANGE_REGEX.search(text)
        or SCAN_CLEAN_PATH_REGEX.search(text)
    ):
        return PublicationSafetyObservation("legacy-nonauthorizing", None)
    if clean_lines or has_failure:
        return PublicationSafetyObservation("malformed", None)
    return PublicationSafetyObservation("none", None)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _resolve_executable(name: str, repository_root: str) -> str | None:
    candidate = shutil.which(name)
    if not candidate:
        return None
    try:
        resolved = Path(candidate).resolve(strict=True)
        workspace = Path(repository_root).resolve(strict=True)
    except Exception:
        return None
    if not resolved.is_file() or _is_within(resolved, workspace):
        return None
    return str(resolved)


def _bind_literal_executable_identity(
    literal_executable: str, resolved_git: str, failure_id: str,
) -> None:
    try:
        executable_path = Path(literal_executable).resolve(strict=True)
        resolved_path = Path(resolved_git).resolve(strict=True)
        same_identity = executable_path.is_file() and resolved_path.is_file() and os.path.samefile(
            executable_path, resolved_path
        )
    except Exception:
        same_identity = False
    if not same_identity:
        raise PrRouteDenied(failure_id)


_PROCESS_FAILURE_KINDS = frozenset({
    "spawn-oserror", "deadline", "output-overflow", "reader-loss", "wait-timeout",
    "pipe-unavailable", "execution-error", "cleanup", "cancelled", "exit-code",
})
def _retain_process_failure(error: BaseException, outcome: dict, kind: str, *, native_error: BaseException | None = None, control_origin: str = "unknown") -> None:
    """Keep the existing five-key outcome and only safe failure categories."""
    native_error = error if native_error is None else native_error
    try:
        setattr(error, "publication_gate_process_outcome", outcome)
        # Creator branch provenance is independent of the diagnostic trigger.
        # A later true primary may legitimately retain an earlier trigger kind.
        setattr(error, "publication_gate_process_control_origin", control_origin)
        setattr(error, "publication_gate_process_failure", {
            "kind": kind,
            "errno": getattr(native_error, "errno", None) if type(getattr(native_error, "errno", None)) is int else None,
            "winerror": getattr(native_error, "winerror", None) if type(getattr(native_error, "winerror", None)) is int else None,
        })
    except BaseException as capture_failure:
        raise error from capture_failure


def _safe_process_failure(error: BaseException) -> tuple[dict, dict] | None:
    metadata = getattr(error, "publication_gate_process_failure", None)
    outcome = getattr(error, "publication_gate_process_outcome", None)
    if (type(metadata) is not dict or set(metadata) != {"kind", "errno", "winerror"}
            or type(metadata["kind"]) is not str or metadata["kind"] not in _PROCESS_FAILURE_KINDS
            or any(value is not None and type(value) is not int for key, value in metadata.items() if key != "kind")
            or type(outcome) is not dict or set(outcome) != {"returncode", "stdout", "stderr", "complete", "resourcesSettled"}
            or outcome["returncode"] is not None and type(outcome["returncode"]) is not int
            or type(outcome["complete"]) is not bool or type(outcome["resourcesSettled"]) is not bool):
        return None
    return metadata, outcome


def _run_process(
    argv: list[str], timeout: float, repository_workdir: str
) -> ProcessResult | None:
    env = os.environ.copy()
    env.pop("GH_REPO", None)
    env["GH_PROMPT_DISABLED"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=repository_workdir,
        )
    except OSError as error:
        _retain_process_failure(error, {
            "returncode": None, "stdout": b"", "stderr": b"",
            "complete": False, "resourcesSettled": True,
        }, "spawn-oserror", control_origin="former-none")
        raise

    stdout = bytearray()
    stderr = bytearray()
    overflow = threading.Event()
    output_lock = threading.Lock()
    reader_failures: list[BaseException] = []

    def drain(stream, destination: bytearray) -> None:
        try:
            while not overflow.is_set():
                chunk = stream.read(8192)
                if not chunk:
                    return
                with output_lock:
                    if len(destination) + len(chunk) > PROCESS_OUTPUT_BYTE_CAP:
                        overflow.set()
                        return
                    destination.extend(chunk)
        except BaseException as exc:
            with output_lock:
                reader_failures.append(exc)
            overflow.set()

    started: list[threading.Thread] = []
    primary_failure: BaseException | None = None
    primary_traceback = None
    cleanup_failures: list[BaseException] = []
    failed = False
    operational_kind: str | None = None
    if process.stdout is None or process.stderr is None:
        primary_failure = RuntimeError("process output pipe unavailable")
        primary_traceback = primary_failure.__traceback__
        readers = ()
        failed = True
        operational_kind = "pipe-unavailable"
    else:
        readers = (
            threading.Thread(target=drain, args=(process.stdout, stdout), daemon=True),
            threading.Thread(target=drain, args=(process.stderr, stderr), daemon=True),
        )
    deadline = time.monotonic() + max(0.0, timeout)
    try:
        for reader in readers:
            reader.start()
            started.append(reader)
        while process.poll() is None:
            if overflow.is_set() or time.monotonic() >= deadline:
                operational_kind = ("reader-loss" if reader_failures else "output-overflow") if overflow.is_set() else "deadline"
                failed = True
                break
            time.sleep(0.01)
    except BaseException as exc:
        primary_failure = exc
        primary_traceback = exc.__traceback__
        failed = True

    termination_attempted = False
    termination_succeeded = False

    def request_termination() -> bool:
        nonlocal termination_attempted, termination_succeeded
        if termination_attempted:
            return termination_succeeded
        termination_attempted = True
        try:
            if process.poll() is not None:
                termination_succeeded = True
                return True
            process.kill()
            termination_succeeded = True
            return True
        except ProcessLookupError:
            termination_succeeded = True
            return True
        except BaseException as exc:
            cleanup_failures.append(exc)
            try:
                termination_succeeded = process.poll() is not None
            except BaseException as observe_exc:
                cleanup_failures.append(observe_exc)
                termination_succeeded = False
            return termination_succeeded

    def wait_for_owned_child() -> None:
        nonlocal failed, primary_failure, primary_traceback, operational_kind
        if termination_attempted and not termination_succeeded:
            return
        try:
            if termination_attempted:
                process.wait()
            else:
                process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            failed = True
            operational_kind = "wait-timeout"
            if request_termination():
                try:
                    process.wait()
                except BaseException as exc:
                    cleanup_failures.append(exc)
        except BaseException as exc:
            if primary_failure is None:
                primary_failure = exc
                primary_traceback = exc.__traceback__
            if request_termination():
                try:
                    process.wait()
                except BaseException as cleanup_exc:
                    cleanup_failures.append(cleanup_exc)
            else:
                cleanup_failures.append(exc)

    if failed or overflow.is_set():
        request_termination()
    wait_for_owned_child()

    for reader in started:
        try:
            reader.join(timeout=1.0)
        except BaseException as exc:
            if primary_failure is None:
                primary_failure = exc
                primary_traceback = exc.__traceback__
            cleanup_failures.append(exc)

    live_readers: list[threading.Thread] = []
    for reader in started:
        try:
            if reader.is_alive():
                live_readers.append(reader)
        except BaseException as exc:
            if primary_failure is None:
                primary_failure = exc
                primary_traceback = exc.__traceback__
            cleanup_failures.append(exc)

    if live_readers:
        failed = True
        operational_kind = "reader-loss"
        for stream in (process.stdout, process.stderr):
            if stream is None:
                continue
            try:
                if not stream.closed:
                    stream.close()
            except BaseException as exc:
                cleanup_failures.append(exc)
        for reader in live_readers:
            try:
                reader.join(timeout=1.0)
            except BaseException as exc:
                if primary_failure is None:
                    primary_failure = exc
                    primary_traceback = exc.__traceback__
                cleanup_failures.append(exc)

    for stream in (process.stdout, process.stderr):
        if stream is None:
            continue
        try:
            if not stream.closed:
                stream.close()
        except BaseException as exc:
            cleanup_failures.append(exc)

    unsettled = False
    try:
        unsettled = (
            process.returncode is None
            or any(reader.is_alive() for reader in started)
            or any(stream is not None and not stream.closed for stream in (
                process.stdout, process.stderr
            ))
        )
    except BaseException as exc:
        cleanup_failures.append(exc)
        unsettled = True

    if unsettled:
        cleanup_failures.append(RuntimeError("process resources remain unsettled"))

    def retain_outcome(error: BaseException, kind: str, control_origin: str) -> None:
        outcome = {
            "returncode": process.returncode,
            "stdout": bytes(stdout),
            "stderr": bytes(stderr),
            "complete": False,
            "resourcesSettled": not unsettled,
        }
        try:
            native_error = (reader_failures[0] if kind == "reader-loss" and reader_failures
                            else cleanup_failures[0] if kind == "cleanup" and cleanup_failures else error)
            _retain_process_failure(error, outcome, kind, native_error=native_error, control_origin=control_origin)
            if unsettled:
                setattr(error, "publication_gate_owned_process", process)
                setattr(error, "publication_gate_owned_readers", tuple(started))
                setattr(error, "publication_gate_owned_streams", (process.stdout, process.stderr))
        except BaseException as capture_failure:
            raise error from capture_failure

    if primary_failure is not None:
        retain_outcome(primary_failure, "cancelled" if isinstance(primary_failure, (KeyboardInterrupt, SystemExit))
                       else operational_kind or "execution-error", "primary")
        if cleanup_failures:
            raise primary_failure.with_traceback(primary_traceback) from cleanup_failures[0]
        raise primary_failure.with_traceback(primary_traceback)
    if cleanup_failures:
        failure = RuntimeError("process cleanup failed")
        retain_outcome(failure, "cleanup", "cleanup")
        raise failure from cleanup_failures[0]
    if unsettled:
        raise RuntimeError("process resources remain unsettled")
    if failed or overflow.is_set() or reader_failures:
        failure = RuntimeError("process operational failure")
        retain_outcome(failure, "reader-loss" if reader_failures else operational_kind or "output-overflow", "former-none")
        if reader_failures:
            raise failure from reader_failures[0]
        raise failure
    return ProcessResult(process.returncode, bytes(stdout), bytes(stderr))


_SCAN_BOOTSTRAP = r'''import base64,builtins,hashlib,json,re,sys,types
def no_duplicates(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise ValueError("duplicate payload member")
        result[key]=value
    return result
def exact_object(value, keys, label):
    if type(value) is not dict or set(value)!=set(keys):
        raise ValueError(label)
    return value
bundle=json.loads(sys.stdin.buffer.read().decode("ascii"),object_pairs_hook=no_duplicates)
if type(bundle) is not dict or type(bundle.get("payloadVersion")) is not int or bundle["payloadVersion"] not in (1,2):
    raise ValueError("payload version")
native_mode=bundle["payloadVersion"]==2
exact_object(bundle,("payloadVersion","sources","review","nativePush") if native_mode else ("payloadVersion","sources","review"),"payload shape")
roles=("hook_common","classifier","posix_helper","windows_job","scanner","publication_review_policy","linked_runtime_subroots")
encoded_sources=exact_object(bundle["sources"],roles,"source roles")
sources={}
for key,value in encoded_sources.items():
    if type(value) is not str: raise ValueError("source encoding")
    raw=base64.b64decode(value,validate=True)
    if base64.b64encode(raw).decode("ascii")!=value: raise ValueError("source encoding")
    sources[key]=raw
review=exact_object(bundle["review"],("schemaVersion","repositoryObservation","snapshot","snapshotId"),"review shape")
if type(review["schemaVersion"]) is not int or review["schemaVersion"]!=1:
    raise ValueError("review version")
if type(review["snapshotId"]) is not str or re.fullmatch(r"[0-9a-f]{64}",review["snapshotId"]) is None:
    raise ValueError("snapshot id")
snapshot=exact_object(review["snapshot"],("schemaVersion","status","origin","rawBase64","rawSha256","diagnostic"),"snapshot shape")
if type(snapshot["schemaVersion"]) is not int or snapshot["schemaVersion"]!=1:
    raise ValueError("snapshot version")
if snapshot["status"]=="captured":
    if snapshot["origin"] is None or type(snapshot["rawBase64"]) is not str or type(snapshot["rawSha256"]) is not str or snapshot["diagnostic"]!="none":
        raise ValueError("captured snapshot shape")
    raw_policy=base64.b64decode(snapshot["rawBase64"],validate=True)
    if base64.b64encode(raw_policy).decode("ascii")!=snapshot["rawBase64"] or hashlib.sha256(raw_policy).hexdigest()!=snapshot["rawSha256"]:
        raise ValueError("captured snapshot bytes")
elif snapshot["status"] in ("absent","unavailable"):
    if snapshot["rawBase64"] is not None or snapshot["rawSha256"] is not None or snapshot["diagnostic"] in (None,"none"):
        raise ValueError("uncaptured snapshot shape")
else:
    raise ValueError("snapshot status")
observation=exact_object(review["repositoryObservation"],("status","repository","diagnostic"),"repository observation shape")
if observation["status"]=="captured":
    repo=exact_object(observation["repository"],("kind","objectFormat","commonGit","worktreeGit","worktreeRoot"),"repository shape")
    for name in ("commonGit","worktreeGit","worktreeRoot"):
        exact_object(repo[name],("pathEncoding","pathBase64","device","inode"),"native directory shape")
    if observation["diagnostic"]!="none": raise ValueError("repository observation diagnostic")
elif observation["status"] in ("not-requested","unavailable"):
    if observation["repository"] is not None: raise ValueError("unobserved repository")
    expected_diagnostic="not-needed" if observation["status"]=="not-requested" else "metadata-unavailable"
    if observation["diagnostic"]!=expected_diagnostic and not (observation["status"]=="unavailable" and observation["diagnostic"]=="unprovable-native-identity"):
        raise ValueError("repository observation diagnostic")
else:
    raise ValueError("repository observation status")
if native_mode:
    native=exact_object(bundle["nativePush"],("version","objectFormat","repositoryObservation","endpoint","endpointIdentity","inputSha256","wireBase64"),"native push shape")
    if type(native["version"]) is not int or native["version"]!=1 or native["repositoryObservation"]!=observation or observation["status"]!="captured":
        raise ValueError("native repository binding")
    if native["objectFormat"]!=observation["repository"]["objectFormat"] or type(native["endpoint"]) is not str or type(native["wireBase64"]) is not str:
        raise ValueError("native push binding")
    wire=base64.b64decode(native["wireBase64"],validate=True)
    if base64.b64encode(wire).decode("ascii")!=native["wireBase64"] or hashlib.sha256(wire).hexdigest()!=native["inputSha256"]:
        raise ValueError("native wire binding")
allowed=set(sys.stdlib_module_names)|{"hook_common","_orchestrarium_publication_review_policy_v1","_orchestrarium_linked_runtime_subroots_v1"}
original_import=builtins.__import__
def guarded_import(name,globals=None,locals=None,fromlist=(),level=0):
    if not level and name.split(".",1)[0] not in allowed:
        raise ImportError("non-standard import denied")
    return original_import(name,globals,locals,fromlist,level)
builtins.__import__=guarded_import
common=types.ModuleType("hook_common")
common.__file__="<closure>/hook_common.py"
sys.modules["hook_common"]=common
exec(compile(sources["hook_common"],common.__file__,"exec"),common.__dict__,common.__dict__)
classifier={"__name__":"_publication_path_owner","__file__":"<closure>/check-machine-local-path.py","__package__":None,"__cached__":None}
exec(compile(sources["classifier"],classifier["__file__"],"exec"),classifier,classifier)
finder=classifier.get("find_machine_paths")
if not callable(finder):
    raise RuntimeError("classifier contract")
posix_helper_name="_orchestrarium_posix_process_group_v1"
posix_helper=types.ModuleType(posix_helper_name)
posix_helper.__file__="<closure>/process_supervision/posix_process_group.py"
sys.modules[posix_helper_name]=posix_helper
exec(compile(sources["posix_helper"],posix_helper.__file__,"exec"),posix_helper.__dict__,posix_helper.__dict__)
windows_job_name="_orchestrarium_windows_job_v1"
windows_job=types.ModuleType(windows_job_name)
windows_job.__file__="<closure>/process_supervision/windows_job.py"
sys.modules[windows_job_name]=windows_job
exec(compile(sources["windows_job"],windows_job.__file__,"exec"),windows_job.__dict__,windows_job.__dict__)
linked_name="_orchestrarium_linked_runtime_subroots_v1"
linked=types.ModuleType(linked_name)
linked.__file__="<closure>/linked_runtime_subroots.py"
sys.modules[linked_name]=linked
exec(compile(sources["linked_runtime_subroots"],linked.__file__,"exec"),linked.__dict__,linked.__dict__)
policy_name="_orchestrarium_publication_review_policy_v1"
policy=types.ModuleType(policy_name)
policy.__file__="<closure>/publication_review_policy.py"
sys.modules[policy_name]=policy
exec(compile(sources["publication_review_policy"],policy.__file__,"exec"),policy.__dict__,policy.__dict__)
if sys.modules.get(linked_name) is not linked or linked.__name__!=linked_name or linked.__file__!="<closure>/linked_runtime_subroots.py":
    raise RuntimeError("linked module identity")
if sys.modules.get(policy_name) is not policy or policy.__name__!=policy_name or policy.__file__!="<closure>/publication_review_policy.py" or getattr(policy,"POLICY_MODULE_CONTRACT_ID",None)!="orchestrarium.publication-review-policy.module.v1":
    raise RuntimeError("policy module identity")
if getattr(policy,"POLICY_MODULE_KEY",None)!=policy_name or getattr(policy,"POLICY_INJECTION_KEY",None)!="__injected_review_policy_module__":
    raise RuntimeError("policy injection contract")
if policy.H("orchestrarium.publication-review.snapshot.v1",snapshot)!=review["snapshotId"]:
    raise RuntimeError("snapshot id")
if len(sys.argv)<3 or sys.argv[1]!="--gate-git-executable":
    raise RuntimeError("git executable contract")
if native_mode and not (sys.argv[3:]==["--native-push"] or (len(sys.argv[3:])==5 and sys.argv[3]=="--range" and sys.argv[6]=="--range-source")):
    raise RuntimeError("native scanner mode")
git_executable=sys.argv[2]
scanner_path="<closure>/check-publication-safety.py"
scanner={"__name__":"__main__","__file__":scanner_path,"__package__":None,"__cached__":None,"__injected_find_machine_paths__":finder,"__injected_git_executable__":git_executable,"__injected_posix_process_group_module__":posix_helper,"__injected_windows_job_module__":windows_job,"__injected_review_policy_snapshot__":snapshot,"__injected_review_repository_observation__":observation,"__injected_review_execution__":"gate-captured-v1"}
scanner[policy.POLICY_INJECTION_KEY]=policy
if native_mode: scanner["__injected_native_push__"]=native
sys.argv=[scanner_path,*sys.argv[3:]]
exec(compile(sources["scanner"],scanner_path,"exec"),scanner,scanner)
'''


def _stat_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        int(value.st_dev), int(value.st_ino), int(value.st_mode),
        int(value.st_nlink), int(value.st_size),
        int(getattr(value, "st_mtime_ns", int(value.st_mtime * 1_000_000_000))),
    )


def _is_link_or_reparse(value: os.stat_result) -> bool:
    attributes = int(getattr(value, "st_file_attributes", 0))
    return stat.S_ISLNK(value.st_mode) or bool(attributes & 0x400)


def _regular_identity(path: Path, *, single_link: bool) -> tuple[int, ...]:
    value = os.lstat(path)
    if _is_link_or_reparse(value) or not stat.S_ISREG(value.st_mode):
        raise ValueError("object-kind")
    if single_link and value.st_nlink != 1:
        raise ValueError("link-count")
    return _stat_identity(value)


def _directory_identity(value: os.stat_result) -> tuple[int, ...]:
    if _is_link_or_reparse(value) or not stat.S_ISDIR(value.st_mode):
        raise ValueError("parent-kind")
    return _stat_identity(value)


def _directory_generation(path: Path) -> tuple[int, ...]:
    return _directory_identity(os.lstat(path))


def _interpreter_identity() -> TrustedInterpreterIdentity:
    raw = Path(sys.executable)
    if not raw.is_absolute():
        raise ValueError("interpreter-path")
    resolved = raw.resolve(strict=True)
    identity = _regular_identity(resolved, single_link=False)
    return TrustedInterpreterIdentity(str(resolved), identity)


def _close_owned_descriptors(fds: list[int]) -> tuple[tuple[int, BaseException], ...]:
    failures: list[tuple[int, BaseException]] = []
    for fd in reversed(tuple(dict.fromkeys(fds))):
        try:
            os.close(fd)
        except BaseException as exc:
            failures.append((fd, exc))
        else:
            while fd in fds:
                fds.remove(fd)
    return tuple(failures)


def _raise_capture_primary(
    primary: BaseException,
    traceback,
    cleanup_failures: tuple[tuple[int, BaseException], ...],
) -> None:
    if cleanup_failures:
        try:
            setattr(primary, "publication_gate_descriptor_cleanup_failures", cleanup_failures)
        except BaseException as retain_error:
            cleanup_failures = (*cleanup_failures, (-1, retain_error))
        raise primary.with_traceback(traceback) from cleanup_failures[0][1]
    raise primary.with_traceback(traceback)


def _open_owned_descriptor(open_descriptor: Callable[[], int], owned_fds: list[int] | None) -> int:
    descriptor: int | None = None
    try:
        descriptor = open_descriptor()
        if owned_fds is not None and descriptor not in owned_fds:
            owned_fds.append(descriptor)
        return descriptor
    except BaseException as primary:
        traceback = primary.__traceback__
        failures: tuple[tuple[int, BaseException], ...] = ()
        if descriptor is not None and (
            owned_fds is None or descriptor not in owned_fds
        ):
            failures = _close_owned_descriptors([descriptor])
        _raise_capture_primary(primary, traceback, failures)


def _open_windows_path(
    path: Path, *, directory: bool, owned_fds: list[int] | None = None,
) -> int:
    import ctypes
    import msvcrt
    from ctypes import wintypes

    create_file = ctypes.WinDLL("kernel32", use_last_error=True).CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    desired_access = 0 if directory else 0x80000000
    share_mode = 0x00000001 | (0x00000002 | 0x00000004 if directory else 0)
    flags = 0x00200000 | (0x02000000 if directory else 0x00000080)
    invalid = ctypes.c_void_p(-1).value
    handle = None
    descriptor: int | None = None
    native_handle_owned = False
    transfer_in_progress = False
    try:
        handle = create_file(str(path), desired_access, share_mode, None, 3, flags, None)
        if handle in (None, invalid):
            raise OSError(ctypes.get_last_error(), "CreateFileW")
        native_handle_owned = True
        transfer_in_progress = True
        descriptor = msvcrt.open_osfhandle(
            int(handle), os.O_RDONLY | getattr(os, "O_BINARY", 0)
        )
        transfer_in_progress = False
        native_handle_owned = False
        if owned_fds is not None:
            owned_fds.append(descriptor)
        return descriptor
    except BaseException as primary:
        traceback = primary.__traceback__
        cleanup_failures: list[tuple[int, BaseException]] = []
        if descriptor is not None and (
            owned_fds is None or descriptor not in owned_fds
        ):
            cleanup_failures.extend(_close_owned_descriptors([descriptor]))
        if transfer_in_progress and handle not in (None, invalid):
            try:
                setattr(primary, "publication_gate_native_handle_outcome", {
                    "handle": int(handle),
                    "ownership": "uncertain-during-crt-transfer",
                    "closeAttempted": False,
                })
            except BaseException as retain_error:
                cleanup_failures.append((int(handle), retain_error))
        elif native_handle_owned:
            try:
                closed = ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(handle)
                if not closed:
                    cleanup_failures.append((int(handle), OSError(
                        ctypes.get_last_error(), "CloseHandle"
                    )))
            except BaseException as cleanup_error:
                cleanup_failures.append((int(handle), cleanup_error))
        _raise_capture_primary(primary, traceback, tuple(cleanup_failures))


def _open_windows_source(path: Path, *, owned_fds: list[int] | None = None) -> int:
    return _open_windows_path(path, directory=False, owned_fds=owned_fds)


def _capture_directory(
    path: Path, *, owned_fds: list[int] | None = None,
) -> tuple[int, tuple[int, ...]]:
    path_identity = _directory_generation(path)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if os.name == "posix":
        nofollow = getattr(os, "O_NOFOLLOW", None)
        directory_flag = getattr(os, "O_DIRECTORY", None)
        if nofollow is None or directory_flag is None:
            raise ValueError("directory-open-unavailable")
        flags |= nofollow | directory_flag
    fd = _open_owned_descriptor(
        lambda: (
            _open_windows_path(path, directory=True, owned_fds=owned_fds)
            if os.name == "nt"
            else os.open(path, flags)
        ),
        owned_fds,
    )
    try:
        opened_identity = _directory_identity(os.fstat(fd))
        if opened_identity != path_identity:
            raise ValueError("directory-open-identity")
        return fd, opened_identity
    except BaseException as primary:
        traceback = primary.__traceback__
        failures = (
            () if owned_fds is not None and fd in owned_fds
            else _close_owned_descriptors([fd])
        )
        _raise_capture_primary(primary, traceback, failures)


def _capture_source_node(
    path: Path, role: str, *, owned_fds: list[int] | None = None,
) -> tuple[int, SourceNode]:
    path_identity = _regular_identity(path, single_link=True)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if os.name == "posix":
        if nofollow is None:
            raise ValueError("nofollow-unavailable")
        flags |= nofollow
    fd = _open_owned_descriptor(
        lambda: (
            _open_windows_source(path, owned_fds=owned_fds)
            if os.name == "nt"
            else os.open(path, flags)
        ),
        owned_fds,
    )
    try:
        opened = os.fstat(fd)
        opened_identity = _stat_identity(opened)
        if (
            _is_link_or_reparse(opened)
            or not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or opened_identity != path_identity
        ):
            raise ValueError("open-identity")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, min(65_536, SCAN_SNAPSHOT_BYTE_CAP + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > SCAN_SNAPSHOT_BYTE_CAP:
                raise ValueError("snapshot-limit")
        source = b"".join(chunks)
        if len(source) != opened.st_size:
            raise ValueError("snapshot-size")
        return fd, SourceNode(
            role, str(path), opened_identity,
            int(opened.st_nlink), len(source), hashlib.sha256(source).hexdigest(), source,
        )
    except BaseException as primary:
        traceback = primary.__traceback__
        failures = (
            () if owned_fds is not None and fd in owned_fds
            else _close_owned_descriptors([fd])
        )
        _raise_capture_primary(primary, traceback, failures)


def _capture_interpreter_handle(
    identity: InterpreterIdentity,
    *, owned_fds: list[int] | None = None,
) -> int:
    path = Path(identity.absolute_resolved_path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if os.name == "posix":
        if nofollow is None:
            raise ValueError("nofollow-unavailable")
        flags |= nofollow
    fd = _open_owned_descriptor(
        lambda: (
            _open_windows_source(path, owned_fds=owned_fds)
            if os.name == "nt"
            else os.open(path, flags)
        ),
        owned_fds,
    )
    try:
        opened = os.fstat(fd)
        opened_identity = _stat_identity(opened)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened_identity[:2] != identity.file_identity[:2]
            or opened_identity[3:] != identity.file_identity[3:]
        ):
            raise ValueError("interpreter-open-identity")
        return fd
    except BaseException as primary:
        traceback = primary.__traceback__
        failures = (
            () if owned_fds is not None and fd in owned_fds
            else _close_owned_descriptors([fd])
        )
        _raise_capture_primary(primary, traceback, failures)


def _layout_for_gate(gate: Path) -> tuple[SourceLayout, Path]:
    parts = gate.parts
    # Source packs overlap the generic component suffix. Pick the longest
    # declared exact suffix, and refuse ties instead of resolving by table order.
    matches = tuple(
        layout for layout in SOURCE_LAYOUTS
        if len(parts) >= len(layout.gate_suffix)
        and tuple(parts[-len(layout.gate_suffix):]) == layout.gate_suffix
    )
    if not matches:
        raise ValueError("layout")
    longest = max(len(layout.gate_suffix) for layout in matches)
    selected = tuple(layout for layout in matches if len(layout.gate_suffix) == longest)
    if len(selected) != 1:
        raise ValueError("layout-ambiguous")
    layout = selected[0]
    trust_root = gate.parent
    for _index in range(layout.trust_root_up):
        trust_root = trust_root.parent
    return layout, trust_root


def _observe_root_locator(
    gate: Path, layout: SourceLayout, logical_root: Path,
) -> RootLocatorIdentity:
    value = os.lstat(logical_root)
    raw_target = None
    if _is_link_or_reparse(value):
        tag = int(getattr(value, "st_reparse_tag", 0))
        if os.name == "nt":
            if tag == stat.IO_REPARSE_TAG_SYMLINK:
                kind = "symlink"
            elif tag == stat.IO_REPARSE_TAG_MOUNT_POINT:
                kind = "junction"
            else:
                raise ValueError("root-locator-kind")
        elif stat.S_ISLNK(value.st_mode):
            kind = "symlink"
        else:
            raise ValueError("root-locator-kind")
        raw_target = os.readlink(logical_root)
    else:
        _directory_identity(value)
        kind = "directory"
    # Only the selected root is resolved. Fixed descendants are acquired with
    # the ordinary/no-follow owners, so in-component links remain observable.
    physical_root = logical_root.resolve(strict=True)
    physical_gate = physical_root / layout.role_paths[0][1]
    root_identity = _directory_generation(physical_root)
    if _directory_identity(os.stat(logical_root)) != root_identity:
        raise ValueError("root-terminal-identity")
    gate_identity = _regular_identity(gate, single_link=True)
    if _regular_identity(physical_gate, single_link=True) != gate_identity:
        raise ValueError("logical-gate-identity")
    return RootLocatorIdentity(
        str(gate), str(logical_root), kind, _stat_identity(value), raw_target,
        str(physical_root), root_identity, str(physical_gate), gate_identity,
    )


def _component_paths(trust_root: Path, paths: tuple[Path, ...]) -> tuple[tuple[str, Path], ...]:
    observed: dict[str, Path] = {".": trust_root}
    for path in paths:
        relative = path.relative_to(trust_root)
        cursor = trust_root
        for part in relative.parts[:-1]:
            cursor = cursor / part
            name = cursor.relative_to(trust_root).as_posix()
            observed[name] = cursor
    return tuple((name, observed[name]) for name in sorted(observed))


def _capture_path_components(
    trust_root: Path, paths: tuple[Path, ...], *, owned_fds: list[int] | None = None,
) -> tuple[tuple[int, ...], tuple[PathComponentIdentity, ...]]:
    fds = owned_fds if owned_fds is not None else []
    components: list[PathComponentIdentity] = []
    by_name: dict[str, int] = {}
    try:
        for name, path in _component_paths(trust_root, paths):
            if name == "." or os.name != "posix":
                fd, identity = _capture_directory(path, owned_fds=fds)
            else:
                parent_name, _separator, basename = name.rpartition("/")
                parent_fd = by_name[parent_name or "."]
                expected_identity = _directory_generation(path)
                flags = (
                    os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
                    | getattr(os, "O_NOFOLLOW") | getattr(os, "O_DIRECTORY")
                )
                fd = _open_owned_descriptor(
                    lambda: os.open(basename, flags, dir_fd=parent_fd), fds
                )
                identity = _directory_identity(os.fstat(fd))
                named_identity = _directory_identity(os.stat(
                    basename, dir_fd=parent_fd, follow_symlinks=False
                ))
                if identity != expected_identity or named_identity != identity:
                    raise ValueError("directory-open-identity")
            by_name[name] = fd
            components.append(PathComponentIdentity(name, "directory", identity))
        return tuple(fds), tuple(components)
    except BaseException as primary:
        if owned_fds is not None:
            raise
        traceback = primary.__traceback__
        cleanup_failures = _close_owned_descriptors(fds)
        _raise_capture_primary(primary, traceback, cleanup_failures)


def _capture_source_closure() -> tuple[tuple[int, ...], CanonicalSourceClosure]:
    gate = Path(os.path.abspath(__file__))
    layout, logical_root = _layout_for_gate(gate)
    locator = _observe_root_locator(gate, layout, logical_root)
    trust_root_path = Path(locator.physical_root)
    paths = tuple((role, trust_root_path / name) for role, name in layout.role_paths)
    fds: list[int] = []
    nodes: list[SourceNode] = []
    try:
        component_paths = tuple(path for _role, path in paths)
        component_fds, components = _capture_path_components(
            trust_root_path, component_paths, owned_fds=fds
        )
        for role, path in paths:
            fd, node = _capture_source_node(path, role, owned_fds=fds)
            nodes.append(node)
        bootstrap_digest = hashlib.sha256(_SCAN_BOOTSTRAP.encode("utf-8")).hexdigest()
        interpreter_identity = _interpreter_identity()
        _capture_interpreter_handle(interpreter_identity, owned_fds=fds)
        if (
            components[0].identity != locator.physical_root_identity
            or nodes[0].file_identity != locator.gate_identity
            or _observe_root_locator(gate, layout, logical_root) != locator
        ):
            raise ValueError("root-locator-capture-drift")
        digest_owner = hashlib.sha256(b"publication-safety-closure-v3\0")
        digest_owner.update(layout.name.encode("ascii") + b"\0")
        digest_owner.update(json.dumps(
            (layout.role_paths, tuple(getattr(locator, name) for name in locator.__dataclass_fields__)),
            ensure_ascii=True, separators=(",", ":"),
        ).encode("ascii"))
        digest_owner.update(bootstrap_digest.encode("ascii"))
        for component in components:
            digest_owner.update(b"\0" + component.root_relative_name.encode("utf-8") + b"\0")
            digest_owner.update(repr(component.identity).encode("ascii"))
        for node in nodes:
            digest_owner.update(b"\0" + node.role.encode("ascii") + b"\0")
            digest_owner.update(node.sha256.encode("ascii"))
        trust_root = components[0]
        gate_identity = nodes[0].file_identity
        return tuple(fds), CanonicalSourceClosure(
            layout, trust_root, components, tuple(nodes), digest_owner.hexdigest(),
            gate_identity, bootstrap_digest, interpreter_identity, locator,
        )
    except BaseException as primary:
        traceback = primary.__traceback__
        cleanup_failures = _close_owned_descriptors(fds)
        _raise_capture_primary(primary, traceback, cleanup_failures)


def _recheck_source_closure(
    fds: tuple[int, ...], before: CanonicalSourceClosure,
) -> CanonicalSourceClosure:
    component_count = len(before.components)
    if len(fds) != component_count + len(before.nodes) + 1:
        raise ValueError("closure-cardinality")
    component_fds = fds[:component_count]
    node_fds = fds[component_count:component_count + len(before.nodes)]
    interpreter_fd = fds[-1]
    gate = Path(os.path.abspath(__file__))
    layout, logical_root = _layout_for_gate(gate)
    if layout != before.layout:
        raise ValueError("layout-drift")
    locator = _observe_root_locator(gate, layout, logical_root)
    if locator != before.root_locator:
        raise ValueError("root-locator-drift")
    trust_root_path = Path(locator.physical_root)
    paths = tuple(trust_root_path / name for _role, name in layout.role_paths)
    if (
        tuple(node.role for node in before.nodes) != tuple(role for role, _name in layout.role_paths)
        or tuple(node.expected_path for node in before.nodes) != tuple(map(str, paths))
        or before.trust_root != before.components[0]
        or before.trust_root.identity != locator.physical_root_identity
        or before.gate_identity != locator.gate_identity
    ):
        raise ValueError("component-relation-drift")
    current_component_paths = _component_paths(
        trust_root_path, paths
    )
    if tuple(name for name, _path in current_component_paths) != tuple(
        component.root_relative_name for component in before.components
    ):
        raise ValueError("component-cardinality-drift")
    component_fd_by_name = {
        component.root_relative_name: fd
        for fd, component in zip(component_fds, before.components, strict=True)
    }
    for fd, component, (name, path) in zip(
        component_fds, before.components, current_component_paths, strict=True
    ):
        opened_identity = _directory_identity(os.fstat(fd))
        if os.name == "posix" and name != ".":
            parent_name, _separator, basename = name.rpartition("/")
            live_identity = _directory_identity(os.stat(
                basename,
                dir_fd=component_fd_by_name[parent_name or "."],
                follow_symlinks=False,
            ))
        else:
            live_identity = _directory_generation(path)
        if (
            opened_identity != component.identity
            or live_identity != opened_identity
        ):
            raise ValueError("component-drift")
    for fd, node in zip(node_fds, before.nodes, strict=True):
        path = Path(node.expected_path)
        opened = os.fstat(fd)
        opened_identity = _stat_identity(opened)
        if (
            opened_identity != node.file_identity
            or opened.st_nlink != 1
            or _regular_identity(path, single_link=True) != opened_identity
        ):
            raise ValueError("identity-drift")
        os.lseek(fd, 0, os.SEEK_SET)
        source = b""
        while len(source) <= SCAN_SNAPSHOT_BYTE_CAP:
            chunk = os.read(fd, min(65_536, SCAN_SNAPSHOT_BYTE_CAP + 1 - len(source)))
            if not chunk:
                break
            source += chunk
        if source != node.source or hashlib.sha256(source).hexdigest() != node.sha256:
            raise ValueError("source-drift")
    interpreter_opened = os.fstat(interpreter_fd)
    interpreter_opened_identity = _stat_identity(interpreter_opened)
    if (
        not stat.S_ISREG(interpreter_opened.st_mode)
        or interpreter_opened_identity[:2] != before.interpreter_identity.file_identity[:2]
        or interpreter_opened_identity[3:] != before.interpreter_identity.file_identity[3:]
        or _interpreter_identity() != before.interpreter_identity
    ):
        raise ValueError("interpreter-drift")
    if (
        _regular_identity(gate, single_link=True)
        != before.gate_identity
        or hashlib.sha256(_SCAN_BOOTSTRAP.encode("utf-8")).hexdigest()
        != before.bootstrap_digest
    ):
        raise ValueError("gate-drift")
    if _observe_root_locator(gate, layout, logical_root) != locator:
        raise ValueError("root-locator-recheck-drift")
    return before


def _closure_payload(
    closure: CanonicalSourceClosure,
    review_document: object,
    canonical_bytes: object,
    *,
    native_push: dict | None = None,
) -> bytes:
    if tuple(node.role for node in closure.nodes) != SOURCE_ROLE_ORDER:
        raise ValueError("source-role-closure")
    if type(review_document) is not dict or set(review_document) != {
        "schemaVersion", "repositoryObservation", "snapshot", "snapshotId",
    }:
        raise ValueError("review-payload-shape")
    if type(review_document.get("schemaVersion")) is not int or review_document["schemaVersion"] != 1:
        raise ValueError("review-payload-version")
    if re.fullmatch(r"[0-9a-f]{64}", review_document.get("snapshotId", "")) is None:
        raise ValueError("review-snapshot-id")
    snapshot = review_document.get("snapshot")
    if type(snapshot) is not dict or set(snapshot) != {
        "schemaVersion", "status", "origin", "rawBase64", "rawSha256", "diagnostic",
    }:
        raise ValueError("review-snapshot-shape")
    repository_observation = review_document.get("repositoryObservation")
    if type(repository_observation) is not dict or set(repository_observation) != {
        "status", "repository", "diagnostic",
    }:
        raise ValueError("review-repository-observation-shape")
    sources = {
        node.role: base64.b64encode(node.source).decode("ascii")
        for node in closure.nodes if node.role != "gate"
    }
    if len(sources) != 7 or tuple(sources) != SOURCE_ROLE_ORDER[1:]:
        raise ValueError("source-role-cardinality")
    encoder = canonical_bytes
    if not callable(encoder):
        raise ValueError("policy-canonical-encoder")
    bundle = {
        "payloadVersion": 1 if native_push is None else 2,
        "sources": sources,
        "review": review_document,
    }
    if native_push is not None:
        if (
            type(native_push) is not dict
            or native_push.get("repositoryObservation") != repository_observation
            or repository_observation.get("status") != "captured"
        ):
            raise ValueError("native-review-repository-binding")
        bundle["nativePush"] = native_push
    payload = encoder(bundle) if native_push is None else _native_canonical_bytes(bundle)
    if type(payload) is not bytes or not payload.isascii():
        raise ValueError("canonical-payload-bytes")
    return payload


REPOSITORY_QUERY_ORDER = ("topLevel", "commonGit", "worktreeGit", "objectFormat")
REPOSITORY_QUERY_SUFFIXES = {
    "topLevel": ("--show-toplevel",),
    "commonGit": ("--path-format=absolute", "--git-common-dir"),
    "worktreeGit": ("--absolute-git-dir",),
    "objectFormat": ("--show-object-format",),
}


def _capture_repository_observation(
    policy_module: object,
    selected_root: Path,
    git_executable: str,
) -> dict:
    plan = policy_module.repository_query_plan(selected_root)
    if (
        type(plan) is not policy_module.RepositoryQueryPlanV1
        or plan.root != selected_root
    ):
        raise ValueError("repository-query-plan")
    queries = plan.queries
    if type(queries) is not tuple or len(queries) != len(REPOSITORY_QUERY_ORDER):
        raise ValueError("repository-query-cardinality")
    prefix = ("--no-optional-locks", "-C", str(selected_root), "rev-parse")
    results = []
    deadline = time.monotonic() + ORACLE_TIMEOUT_SECONDS
    for index, (query, key) in enumerate(zip(queries, REPOSITORY_QUERY_ORDER)):
        expected_args = (*prefix, *REPOSITORY_QUERY_SUFFIXES[key])
        if (
            type(query) is not policy_module.RepositoryQueryV1
            or query.key != key
            or type(query.git_args) is not tuple
            or query.git_args != expected_args
        ):
            raise ValueError("repository-query-contract")
        timeout = max(0.0, deadline - time.monotonic())
        try:
            outcome = _run_process(
                [git_executable, *query.git_args], timeout, str(plan.root)
            )
        except BaseException as primary:
            categorized = _safe_process_failure(primary)
            if (categorized is not None
                    and getattr(primary, "publication_gate_process_control_origin", None) == "former-none"):
                _metadata, process_outcome = categorized
                results.append(policy_module.RepositoryQueryResultV1(
                    key, query.git_args, process_outcome["returncode"],
                    process_outcome["stdout"], process_outcome["stderr"],
                    False, process_outcome["resourcesSettled"],
                    "execution-error" if process_outcome["resourcesSettled"] else "unsettled",
                ))
                continue
            process_outcome = getattr(
                primary, "publication_gate_process_outcome", None
            )
            if type(process_outcome) is dict and set(process_outcome) == {
                "returncode", "stdout", "stderr", "complete", "resourcesSettled",
            }:
                failure_kind = (
                    "unsettled"
                    if process_outcome["resourcesSettled"] is not True
                    else "cancelled"
                    if isinstance(primary, KeyboardInterrupt)
                    else "execution-error"
                )
                results.append(policy_module.RepositoryQueryResultV1(
                    key, query.git_args, process_outcome["returncode"],
                    process_outcome["stdout"], process_outcome["stderr"],
                    False, process_outcome["resourcesSettled"], failure_kind,
                ))
            try:
                setattr(primary, "publication_review_query_plan", plan)
                setattr(primary, "publication_review_query_results", tuple(results))
                setattr(primary, "publication_review_query_index", index)
            except BaseException as capture_failure:
                raise primary from capture_failure
            raise
        if outcome is None:
            result = policy_module.RepositoryQueryResultV1(
                key, query.git_args, None, None, None,
                False, True, "none-result",
            )
        else:
            if (
                type(outcome) is not ProcessResult
                or type(outcome.returncode) is not int
                or type(outcome.stdout) is not bytes
                or type(outcome.stderr) is not bytes
            ):
                raise ValueError("repository-query-outcome")
            result = policy_module.RepositoryQueryResultV1(
                key, query.git_args, outcome.returncode, outcome.stdout,
                outcome.stderr, True, True,
                None if outcome.returncode == 0 else "execution-error",
            )
        results.append(result)
    observation = policy_module.repository_from_query_results(plan, tuple(results))
    if type(observation) is not dict or set(observation) != {
        "status", "repository", "diagnostic",
    }:
        raise ValueError("repository-observation")
    return observation


def _capture_review_payload(
    modules: CapturedReviewModules,
    closure: CanonicalSourceClosure,
    selected_root: Path,
    git_executable: str,
    *,
    require_repository: bool = False,
) -> CapturedReviewPayload:
    policy_module = modules.policy_module
    if (
        sys.modules.get("_orchestrarium_publication_review_policy_v1")
        is not policy_module
        or getattr(policy_module, "POLICY_MODULE_CONTRACT_ID", None)
        != "orchestrarium.publication-review-policy.module.v1"
    ):
        raise ValueError("policy-module-identity")
    origin = policy_module.resolve_trusted_origin()
    policy_read = policy_module.read_policy_snapshot(origin, selected_root)
    if type(policy_read) is not policy_module.PolicyReadV1:
        raise ValueError("policy-read-result")
    snapshot = policy_read.snapshot
    snapshot_id = policy_read.snapshot_id
    if (
        type(snapshot) is not dict
        or type(policy_read.usable_records) is not tuple
        or type(policy_read.issues) is not tuple
        or policy_module.H(
            "orchestrarium.publication-review.snapshot.v1", snapshot
        ) != snapshot_id
    ):
        raise ValueError("policy-snapshot-result")

    if policy_read.usable_records or require_repository:
        repository_observation = _capture_repository_observation(
            policy_module, selected_root, git_executable
        )
    else:
        repository_observation = {
            "status": "not-requested",
            "repository": None,
            "diagnostic": "not-needed",
        }
    repository = repository_observation["repository"]
    origin_is_outside = False
    if repository_observation["status"] == "captured":
        origin_is_outside = policy_module.origin_is_outside_repository(
            snapshot, repository
        )
        if type(origin_is_outside) is not bool:
            raise ValueError("policy-origin-exclusion")

    review_document = {
        "schemaVersion": 1,
        "repositoryObservation": repository_observation,
        "snapshot": snapshot,
        "snapshotId": snapshot_id,
    }
    payload = _closure_payload(closure, review_document, policy_module.C)
    return CapturedReviewPayload(
        modules, snapshot, snapshot_id, repository_observation, repository,
        origin_is_outside, payload, hashlib.sha256(payload).hexdigest(),
    )


def _decode_used_decisions(
    policy_module: object,
    encoded: str,
    failure_id: str,
) -> list[list[str]]:
    try:
        raw = base64.b64decode(encoded, validate=True)
        if base64.b64encode(raw).decode("ascii") != encoded:
            raise ValueError("used-list base64")
        value = _strict_json(raw.decode("ascii", errors="strict"), list, failure_id)
    except PrRouteDenied:
        raise
    except Exception:
        raise PrRouteDenied(failure_id) from None
    if (
        type(value) is not list
        or not value
        or any(
            type(row) is not list
            or len(row) != 2
            or type(row[0]) is not str
            or type(row[1]) is not str
            for row in value
        )
    ):
        raise PrRouteDenied(failure_id)
    if policy_module.C(value) != raw:
        raise PrRouteDenied(failure_id)
    return value


def _verify_used_review_currentness(
    captured_review: CapturedReviewPayload,
    qualification: QualifiedPublicationEvidence,
    repository_workdir: str,
    git_executable: str,
    failure_id: str,
    *,
    additional_reviews: tuple[tuple[CapturedReviewPayload, QualifiedPublicationEvidence], ...] = (),
) -> tuple[dict, list[list[str]]]:
    policy_module = captured_review.policy_module
    reviews = ((captured_review, qualification), *additional_reviews)
    # verify_used compares this first core to its one final selected origin.
    # Matching every input core here binds all snapshots to that same origin
    # without equating policy contents or acquiring another policy snapshot.
    origin_core = policy_module._origin_core_from_snapshot(captured_review.snapshot)
    used_by_id: dict[str, str] = {}
    for reviewed, qualified in reviews:
        if (reviewed.repository is None
            or reviewed.repository != captured_review.repository
            or not reviewed.origin_is_outside_repository
            or qualified.policy_snapshot_id != reviewed.snapshot_id):
            raise PrRouteDenied(failure_id)
        if policy_module._origin_core_from_snapshot(reviewed.snapshot) != origin_core:
            raise PrRouteDenied(failure_id)
        used = _decode_used_decisions(policy_module, qualified.used_decisions_b64, failure_id)
        ids = [row[0] for row in used]
        if ids != sorted(set(ids)):
            raise PrRouteDenied(failure_id)
        for decision_id, record_sha in used:
            if decision_id in used_by_id and used_by_id[decision_id] != record_sha:
                raise PrRouteDenied(failure_id)
            used_by_id[decision_id] = record_sha
    used_list = [[decision_id, used_by_id[decision_id]] for decision_id in sorted(used_by_id)]
    fresh_observation = _capture_repository_observation(
        policy_module, Path(repository_workdir), git_executable
    )
    if fresh_observation["status"] != "captured":
        raise PrRouteDenied(failure_id)
    fresh_repository = fresh_observation["repository"]
    if any(not policy_module.origin_is_outside_repository(reviewed.snapshot, fresh_repository)
           for reviewed, _qualified in reviews):
        raise PrRouteDenied(failure_id)
    finalization = policy_module.verify_used(
        captured_review.snapshot, fresh_repository, used_list
    )
    finalization_keys = {
        "inputSnapshotId", "usedList", "currentSnapshotId", "repositorySha256",
        "status", "reason", "resourcesSettled",
    }
    if (
        type(finalization) is not dict
        or set(finalization) != finalization_keys
        or finalization["inputSnapshotId"] != captured_review.snapshot_id
        or finalization["usedList"] != used_list
        or type(finalization["currentSnapshotId"]) is not str
        or re.fullmatch(r"[0-9a-f]{64}", finalization["currentSnapshotId"]) is None
        or finalization["repositorySha256"]
        != policy_module.H(
            "orchestrarium.publication-review.repository.v1",
            captured_review.repository,
        )
        or finalization["status"] != "valid"
        or finalization["reason"] != "none"
        or finalization["resourcesSettled"] is not True
    ):
        raise PrRouteDenied(failure_id)
    return finalization, used_list


def _release_captured_review_modules(modules: CapturedReviewModules) -> None:
    failures = []
    for name, module in reversed(modules.registered):
        if sys.modules.get(name) is not module:
            failures.append(name)
            continue
        del sys.modules[name]
    if failures:
        raise ValueError("captured-module-settlement")


def _load_captured_review_modules(
    closure: CanonicalSourceClosure,
) -> CapturedReviewModules:
    if tuple(node.role for node in closure.nodes) != SOURCE_ROLE_ORDER:
        raise ValueError("source-role-closure")
    source_by_role = {node.role: node.source for node in closure.nodes}
    if set(source_by_role) != set(SOURCE_ROLE_ORDER):
        raise ValueError("source-role-cardinality")
    linked_name = "_orchestrarium_linked_runtime_subroots_v1"
    policy_name = "_orchestrarium_publication_review_policy_v1"
    if linked_name in sys.modules or policy_name in sys.modules:
        raise ValueError("captured-module-slot")
    registered: list[tuple[str, object]] = []
    try:
        linked = types.ModuleType(linked_name)
        linked.__file__ = "<closure>/linked_runtime_subroots.py"
        sys.modules[linked_name] = linked
        registered.append((linked_name, linked))
        exec(
            compile(source_by_role["linked_runtime_subroots"], linked.__file__, "exec"),
            linked.__dict__, linked.__dict__,
        )
        if sys.modules.get(linked_name) is not linked:
            raise ValueError("linked-module-identity")

        policy = types.ModuleType(policy_name)
        policy.__file__ = "<closure>/publication_review_policy.py"
        sys.modules[policy_name] = policy
        registered.append((policy_name, policy))
        exec(
            compile(source_by_role["publication_review_policy"], policy.__file__, "exec"),
            policy.__dict__, policy.__dict__,
        )
        if (
            sys.modules.get(policy_name) is not policy
            or getattr(policy, "POLICY_MODULE_CONTRACT_ID", None)
            != "orchestrarium.publication-review-policy.module.v1"
            or getattr(policy, "POLICY_MODULE_KEY", None) != policy_name
            or getattr(policy, "POLICY_INJECTION_KEY", None)
            != "__injected_review_policy_module__"
        ):
            raise ValueError("policy-module-identity")
        return CapturedReviewModules(policy, linked, tuple(registered))
    except BaseException as primary:
        if registered:
            try:
                _release_captured_review_modules(
                    CapturedReviewModules(
                        sys.modules.get(policy_name),
                        sys.modules.get(linked_name),
                        tuple(registered),
                    )
                )
            except BaseException as cleanup:
                raise primary from cleanup
        raise


class GateSettlementState(str, Enum):
    SETTLED = "settled"
    FAILED_UNSETTLED = "failed-unsettled"


@dataclass(frozen=True)
class GateTransportObservation:
    name: str
    ownership: str
    closed_observed: bool
    failure_phase: str | None
    observed_at_monotonic_tick: float


@dataclass(frozen=True)
class GateWorkerObservation:
    worker_identity: int
    start: str
    terminal: str
    observed_at_monotonic_tick: float


@dataclass(frozen=True)
class GateSettlementCertificate:
    supervisor_id: str
    child_identity: int
    observed_return_code: int | None
    streams: tuple[GateTransportObservation, ...]
    workers: tuple[GateWorkerObservation, ...]
    operation_errors: tuple[str, ...]
    attempts_used: int
    verified_at_monotonic_tick: float

    @property
    def complete(self) -> bool:
        ticks = tuple(row.observed_at_monotonic_tick for row in self.streams + self.workers)
        return (
            self.observed_return_code is not None
            and type(self.child_identity) is int
            and self.child_identity > 0
            and 1 <= self.attempts_used <= SCAN_SETTLEMENT_MAX_ENTRIES
            and all(row.ownership != "owned" or row.closed_observed for row in self.streams)
            and all(row.terminal in {"not-started", "joined"} for row in self.workers)
            and (not ticks or self.verified_at_monotonic_tick > max(ticks))
        )


@dataclass(frozen=True)
class GateSettlement:
    state: GateSettlementState
    certificate: GateSettlementCertificate | None
    execution_eligible: bool

    @property
    def complete(self) -> bool:
        return (
            self.state is GateSettlementState.SETTLED
            and self.certificate is not None
            and self.certificate.complete
        )


@dataclass
class _OwnedWorker:
    worker: threading.Thread
    start: str = "not-started"
    name: str = "worker"


class ChildSupervisor:
    """Single immediate owner for a launched scanner child and its workers."""

    def __init__(
        self, process=None, *, attempt_seconds: float = SCAN_SETTLEMENT_ATTEMPT_SECONDS,
    ) -> None:
        self.process = None
        self.supervisor_id = f"supervisor:{id(self)}"
        self.child_identity: int | None = None
        self.workers: list[_OwnedWorker] = []
        self._attempt_seconds = attempt_seconds
        self._attempts_used = 0
        self._operation_errors: list[str] = []
        self._operation_failures: list[tuple[str, BaseException]] = []
        self._settlement: GateSettlement | None = None
        if process is not None:
            self.adopt_process(process)

    def _record_operation_failure(self, name: str, failure: BaseException) -> None:
        self._operation_errors.append(name)
        self._operation_failures.append((name, failure))

    def adopt_process(self, process) -> None:
        if self.process is not None:
            raise RuntimeError("child supervisor already owns a process")
        self.process = process
        self.child_identity = int(process.pid)

    def start_worker(self, worker: threading.Thread, *, name: str = "worker") -> None:
        owned = _OwnedWorker(worker, "starting", name)
        self.workers.append(owned)
        try:
            worker.start()
            owned.start = "started"
        except BaseException as exc:
            self._record_operation_failure("worker-start", exc)
            raise

    @property
    def settled(self) -> bool:
        return self._settlement is not None and self._settlement.complete

    @property
    def settlement(self) -> GateSettlement | None:
        return self._settlement

    def _remaining(self, deadline: float) -> float:
        return max(0.0, deadline - time.monotonic())

    def settle(self) -> GateSettlement:
        if self._settlement is not None and self._settlement.complete:
            return self._settlement
        if self.process is None:
            return GateSettlement(GateSettlementState.FAILED_UNSETTLED, None, False)
        if self._attempts_used >= SCAN_SETTLEMENT_MAX_ENTRIES:
            return self._settlement or GateSettlement(
                GateSettlementState.FAILED_UNSETTLED, None, False
            )
        self._attempts_used += 1
        deadline = time.monotonic() + self._attempt_seconds
        process = self.process
        return_code: int | None = None
        try:
            return_code = process.poll()
        except BaseException as exc:
            self._record_operation_failure("poll", exc)
        if return_code is None:
            try:
                process.terminate()
            except BaseException as exc:
                self._record_operation_failure("terminate", exc)
            try:
                return_code = process.wait(timeout=self._remaining(deadline))
            except BaseException as exc:
                self._record_operation_failure("wait", exc)
                try:
                    return_code = process.poll()
                except BaseException as poll_exc:
                    self._record_operation_failure("post-wait-poll", poll_exc)
            if return_code is None:
                try:
                    process.kill()
                except BaseException as exc:
                    self._record_operation_failure("kill", exc)
                try:
                    return_code = process.wait(timeout=self._remaining(deadline))
                except BaseException as exc:
                    self._record_operation_failure("kill-wait", exc)
        try:
            observed_return_code = process.poll()
            if observed_return_code is not None:
                return_code = observed_return_code
        except BaseException as exc:
            self._record_operation_failure("final-poll", exc)

        worker_rows: list[GateWorkerObservation] = []
        worker_terminals: dict[str, list[str]] = {}
        for owned in self.workers:
            worker = owned.worker
            terminal = "unobserved"
            if owned.start == "not-started":
                terminal = "not-started"
            elif owned.start in {"starting", "started"}:
                try:
                    alive = worker.is_alive()
                except BaseException as exc:
                    self._record_operation_failure("worker-observe", exc)
                    alive = None
                if alive is True:
                    try:
                        worker.join(timeout=self._remaining(deadline))
                    except BaseException as exc:
                        self._record_operation_failure("worker-join", exc)
                    try:
                        alive = worker.is_alive()
                    except BaseException as exc:
                        self._record_operation_failure("worker-observe", exc)
                        alive = None
                if alive is True:
                    terminal = "live"
                elif alive is False:
                    if owned.start == "started":
                        terminal = "joined"
                    else:
                        try:
                            if worker.ident is None and worker.native_id is None:
                                terminal = "unobserved"
                            else:
                                terminal = "joined"
                        except BaseException as exc:
                            self._record_operation_failure("worker-identity", exc)
                            terminal = "unobserved"
                elif owned.start == "starting":
                    terminal = "unobserved"
            worker_terminals.setdefault(owned.name, []).append(terminal)
            worker_rows.append(GateWorkerObservation(id(worker), owned.start, terminal, time.monotonic()))

        process_reaped = return_code is not None
        workers_terminal = all(
            row.terminal in {"not-started", "joined"} for row in worker_rows
        )
        stream_rows: list[GateTransportObservation] = []
        stream_values: list[tuple[str, object | None]] = []
        for name in ("stdin", "stdout", "stderr"):
            try:
                stream_values.append((name, getattr(process, name)))
            except BaseException as exc:
                self._record_operation_failure(name + "-observe", exc)
                stream_values.append((name, None))
        can_close_streams = process_reaped and workers_terminal
        for name, stream in stream_values:
            if stream is None:
                # A missing standard pipe is an actual observation, not an
                # unowned participant invented by the supervisor.
                stream_rows.append(GateTransportObservation(
                    name, "absent", True, None, time.monotonic()
                ))
                continue
            try:
                already_closed = bool(stream.closed)
            except BaseException as exc:
                already_closed = False
                self._record_operation_failure(name + "-observe", exc)
            if already_closed:
                stream_rows.append(GateTransportObservation(
                    name, "owned", True, None, time.monotonic()
                ))
                continue
            if not can_close_streams:
                reason = "process-unreaped" if not process_reaped else "worker-unsettled"
                stream_rows.append(GateTransportObservation(
                    name, "owned", False, reason, time.monotonic()
                ))
                continue
            try:
                stream.close()
            except BaseException as exc:
                self._record_operation_failure(name + "-close", exc)
            try:
                closed = bool(stream.closed)
            except BaseException as exc:
                closed = False
                self._record_operation_failure(name + "-observe", exc)
            stream_rows.append(GateTransportObservation(
                name, "owned", closed, None if closed else name + "-close",
                time.monotonic(),
            ))

        participant_ticks = tuple(row.observed_at_monotonic_tick for row in stream_rows + worker_rows)
        verified = max(time.monotonic(), (max(participant_ticks) + 1e-9) if participant_ticks else 0.0)
        certificate = GateSettlementCertificate(
            self.supervisor_id, self.child_identity, return_code,
            tuple(stream_rows), tuple(worker_rows), tuple(self._operation_errors),
            self._attempts_used, verified,
        )
        state = GateSettlementState.SETTLED if certificate.complete else GateSettlementState.FAILED_UNSETTLED
        self._settlement = GateSettlement(
            state, certificate, certificate.complete and not certificate.operation_errors
        )
        return self._settlement


def _run_snapshot_child(
    pending: PendingScanInvocation, payload: bytes, repository_workdir: str,
) -> tuple[LaunchedScanInvocation, tuple[TrustedExecutionRecord, ...]]:
    prefix = "PGG" if pending.binding.route == "generic" else "PRG"
    captured_review = pending.captured_review
    if (
        captured_review is None
        or type(payload) is not bytes
        or payload != captured_review.payload_bytes
        or hashlib.sha256(payload).hexdigest() != captured_review.payload_sha256
    ):
        raise PrRouteDenied(prefix + "-SCAN-CORRELATION")
    supervisor = ChildSupervisor()
    process = None
    launched: LaunchedScanInvocation | None = None
    settlement: GateSettlement | None = None
    output = {"stdout": bytearray(), "stderr": bytearray()}
    overflow = threading.Event()
    output_lock = threading.Lock()
    reader_failures: list[BaseException] = []
    feeder_failures: list[BaseException] = []
    bounded = False
    primary_failure: BaseException | None = None
    primary_traceback = None
    settlement_failures: list[BaseException] = []

    def retain_child_outcome(primary: BaseException) -> None:
        actual_streams = []
        if process is not None:
            for name in ("stdin", "stdout", "stderr"):
                try:
                    actual_streams.append(getattr(process, name, None))
                except BaseException as exc:
                    settlement_failures.append(exc)
                    actual_streams.append(None)
        actual_workers = tuple(
            {"name": owned.name, "start": owned.start, "worker": owned.worker}
            for owned in supervisor.workers
        )
        try:
            actual_return_code = None if process is None else process.returncode
        except BaseException as exc:
            settlement_failures.append(exc)
            actual_return_code = None
        outcome = {
            "childIdentity": supervisor.child_identity,
            "returnCode": actual_return_code,
            "stdout": bytes(output["stdout"]),
            "stderr": bytes(output["stderr"]),
            "boundedCompletion": bounded,
            "settlement": settlement,
            "readerFailures": tuple(reader_failures),
            "feederFailures": tuple(feeder_failures),
            "settlementFailures": tuple(settlement_failures),
            "operationFailures": tuple(supervisor._operation_failures),
            "workers": actual_workers,
            "streams": tuple(actual_streams),
            "process": process,
            "supervisor": supervisor,
        }
        try:
            setattr(primary, "publication_gate_child_outcome", outcome)
        except BaseException as retain_error:
            settlement_failures.append(retain_error)
            outcome["settlementFailures"] = tuple(settlement_failures)
            try:
                setattr(primary, "publication_gate_child_outcome", outcome)
            except BaseException:
                pass

    def drain(name: str, stream) -> None:
        try:
            while not overflow.is_set():
                chunk = stream.read(8192)
                if not chunk:
                    return
                with output_lock:
                    total = len(output["stdout"]) + len(output["stderr"])
                    if total + len(chunk) > SCAN_OUTPUT_BYTE_CAP:
                        overflow.set()
                        return
                    output[name].extend(chunk)
        except BaseException as exc:
            reader_failures.append(exc)
            overflow.set()

    def feed() -> None:
        try:
            assert process.stdin is not None
            process.stdin.write(payload)
            process.stdin.close()
        except BaseException as exc:
            feeder_failures.append(exc)

    try:
        process = subprocess.Popen(
            list(pending.exact_argv), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, shell=False,
            cwd=repository_workdir,
        )
        supervisor.adopt_process(process)
        launched = LaunchedScanInvocation(
            pending, process.pid, supervisor, pending.invocation_id,
            pending.attempt_id, pending.binding, pending.exact_argv,
            pending.result_slot,
        )
        with pending._transition_lock:
            if pending.state is not PendingState.PREPARED:
                pending.state = PendingState.FAILED
                raise PrRouteDenied(prefix + "-SCAN-CORRELATION")
            pending.child_identity = process.pid
            pending.supervisor = supervisor
            pending.state = PendingState.CHILD_OWNED
        if process.stdout is None or process.stderr is None or process.stdin is None:
            raise RuntimeError("scanner child pipe unavailable")
        workers = (
            ("stdin", lambda: threading.Thread(target=feed)),
            ("stdout", lambda: threading.Thread(target=drain, args=("stdout", process.stdout))),
            ("stderr", lambda: threading.Thread(target=drain, args=("stderr", process.stderr))),
        )
        for name, construct in workers:
            worker = construct()
            supervisor.start_worker(worker, name=name)
        deadline = time.monotonic() + SCAN_TIMEOUT_SECONDS
        while True:
            return_code = process.poll()
            if return_code is not None:
                bounded = not overflow.is_set()
                break
            if overflow.is_set() or time.monotonic() >= deadline:
                break
            time.sleep(0.01)
    except BaseException as exc:
        primary_failure = exc
        primary_traceback = exc.__traceback__
    finally:
        if process is not None:
            if supervisor.process is None:
                try:
                    # The Popen object has already been acquired by this
                    # invocation. If the first adoption was interrupted, bind
                    # that exact object back to the same owner before any
                    # settlement attempt; do not rely on a successful return
                    # from the interrupted handoff.
                    supervisor.process = process
                    supervisor.child_identity = int(process.pid)
                except BaseException as exc:
                    settlement_failures.append(exc)
            if supervisor.process is process and supervisor.child_identity is None:
                try:
                    supervisor.child_identity = int(process.pid)
                except BaseException as exc:
                    settlement_failures.append(exc)
            try:
                with pending._transition_lock:
                    if pending.state is PendingState.CHILD_OWNED:
                        pending.state = PendingState.SETTLING
            except BaseException as exc:
                settlement_failures.append(exc)
            for _index in range(SCAN_SETTLEMENT_MAX_ENTRIES):
                try:
                    settlement = supervisor.settle()
                except BaseException as exc:
                    settlement_failures.append(exc)
                    continue
                if settlement.complete:
                    break
            try:
                with pending._transition_lock:
                    pending.settlement = settlement
                    if pending.state in {PendingState.CHILD_OWNED, PendingState.SETTLING}:
                        pending.state = (
                            PendingState.SETTLED
                            if (
                                primary_failure is None
                                and not reader_failures
                                and not feeder_failures
                                and not settlement_failures
                                and isinstance(settlement, GateSettlement)
                                and settlement.complete
                                and settlement.execution_eligible
                                and bounded
                                and not overflow.is_set()
                            )
                            else PendingState.FAILED
                        )
            except BaseException as exc:
                settlement_failures.append(exc)
                try:
                    with pending._transition_lock:
                        pending.state = PendingState.FAILED
                except BaseException as state_error:
                    settlement_failures.append(state_error)
        else:
            try:
                with pending._transition_lock:
                    if pending.state is PendingState.PREPARED:
                        pending.state = PendingState.FAILED
            except BaseException as exc:
                settlement_failures.append(exc)

    if process is None:
        if primary_failure is not None:
            if isinstance(primary_failure, OSError):
                raise PrRouteDenied(prefix + "-SCAN-EXECUTION") from primary_failure
            raise primary_failure.with_traceback(primary_traceback)
        raise PrRouteDenied(prefix + "-SCAN-EXECUTION")

    if primary_failure is None and reader_failures:
        primary_failure = reader_failures[0]
        primary_traceback = primary_failure.__traceback__
    if primary_failure is None and feeder_failures:
        primary_failure = feeder_failures[0]
        primary_traceback = primary_failure.__traceback__
    if primary_failure is None and settlement_failures:
        primary_failure = settlement_failures[0]
        primary_traceback = primary_failure.__traceback__

    if primary_failure is None and (
        not isinstance(settlement, GateSettlement)
        or not settlement.complete
        or not settlement.execution_eligible
    ):
        primary_failure = PrRouteDenied(prefix + "-SCAN-EXECUTION")
        primary_traceback = primary_failure.__traceback__
    if primary_failure is not None:
        retain_child_outcome(primary_failure)
        try:
            setattr(primary_failure, "publication_gate_child_settlement_failures", tuple(settlement_failures))
        except BaseException:
            pass
        if isinstance(primary_failure, PrRouteDenied):
            raise primary_failure.with_traceback(primary_traceback)
        if isinstance(primary_failure, Exception):
            raise PrRouteDenied(prefix + "-SCAN-EXECUTION") from primary_failure
        raise primary_failure.with_traceback(primary_traceback)
    if launched is None or not isinstance(settlement, GateSettlement):
        raise PrRouteDenied(prefix + "-SCAN-CORRELATION")

    execution = TrustedExecutionRecord(
        pending, launched, pending.result_slot,
        bounded,
        process.returncode if process.returncode is not None else -1,
        bytes(output["stdout"]), bytes(output["stderr"]), settlement,
        pending.closure, pending.interpreter_identity, "pending",
    )
    return launched, (execution,)


def _refresh_scan_binding(
    binding: PushScanBinding, repository_workdir: str, git_exe: str
) -> PushScanBinding:
    return _resolve_generic_scan_binding(
        binding.remote, binding.destination, binding.source_oid,
        repository_workdir, git_exe,
    )


def _native_push_selection(
    native: NativePushInput, observation: dict, canonical_bytes: Callable[[object], bytes],
) -> tuple[dict, NativePushScanBinding]:
    """Bind opaque actual bytes; the captured scanner is the sole wire decoder."""
    if (
        type(native) is not NativePushInput
        or type(native.remote_name) is not str or not native.remote_name or "\x00" in native.remote_name
        or type(native.endpoint) is not str or not native.endpoint or "\x00" in native.endpoint
        or type(native.wire) is not bytes
        or type(observation) is not dict or observation.get("status") != "captured"
        or type(observation.get("repository")) is not dict
    ):
        raise PrRouteDenied("PGG-NATIVE-INPUT")
    object_format = _SUPPORTED_OBJECT_FORMATS.get(observation["repository"].get("objectFormat"))
    if object_format is None:
        raise PrRouteDenied("PGG-NATIVE-INPUT")
    request = {
        "version": 1, "objectFormat": object_format.name,
        "repositoryObservation": observation, "endpoint": native.endpoint,
        "endpointIdentity": _native_endpoint_identity(native.endpoint),
        "inputSha256": hashlib.sha256(native.wire).hexdigest(),
        "wireBase64": base64.b64encode(native.wire).decode("ascii"),
    }
    binding = NativePushScanBinding(
        object_format.name, request["endpointIdentity"], request["inputSha256"],
        hashlib.sha256(_native_canonical_bytes(request)).hexdigest(),
        hashlib.sha256(canonical_bytes(observation)).hexdigest(),
    )
    return request, binding


def _run_authoritative_scan(
    binding: PushScanBinding | NativePushInput, repository_workdir: str, git_exe: str,
    *, native_input: NativePushInput | None = None,
) -> ConsumedAuthoritativeEvidence:
    native_objects = isinstance(binding, NativePushInput)
    native = binding if native_objects else native_input
    prefix = "PGG" if native is not None or binding.route == "generic" else "PRG"
    fds: tuple[int, ...] = ()
    modules: CapturedReviewModules | None = None
    primary_failure: BaseException | None = None
    try:
        try:
            fds, closure_before = _capture_source_closure()
            interpreter_before = _interpreter_identity()
            if closure_before.interpreter_identity != interpreter_before:
                raise ValueError("interpreter-capture")
            modules = _load_captured_review_modules(closure_before)
            captured_review = _capture_review_payload(
                modules, closure_before, Path(repository_workdir), git_exe,
                **({"require_repository": True} if native is not None else {}),
            )
            if native is not None:
                request, native_binding = _native_push_selection(
                    native, captured_review.repository_observation, modules.policy_module.C,
                )
                if native_objects:
                    binding = native_binding
                document = _strict_json(captured_review.payload_bytes.decode("ascii"), dict, "PGG-SCAN-PROVENANCE")["review"]
                payload = _closure_payload(closure_before, document, modules.policy_module.C, native_push=request)
                captured_review = replace(captured_review, payload_bytes=payload, payload_sha256=hashlib.sha256(payload).hexdigest())
        except PrRouteDenied:
            raise
        except Exception as exc:
            if hasattr(exc, "publication_review_query_results"):
                raise PrRouteDenied(prefix + "-SCAN-EXECUTION") from exc
            raise PrRouteDenied(prefix + "-SCAN-PROVENANCE") from None
        invocation_id = secrets.token_hex(32)
        attempt_id = secrets.token_hex(16)
        scan_arguments = ("--native-push",) if native_objects else (
            "--range", binding.remote, binding.destination, "--range-source", binding.source_oid,
        )
        argv = (
            interpreter_before.absolute_resolved_path, "-I", "-c", _SCAN_BOOTSTRAP,
            "--gate-git-executable", git_exe,
            *scan_arguments,
        )
        pending = PendingScanInvocation(
            invocation_id, attempt_id, binding, closure_before,
            interpreter_before, argv, object(), captured_review,
        )
        launched, records = _run_snapshot_child(
            pending, captured_review.payload_bytes, repository_workdir
        )
        try:
            closure_after = _recheck_source_closure(fds, closure_before)
            interpreter_after = _interpreter_identity()
        except Exception:
            raise PrRouteDenied(prefix + "-SCAN-IDENTITY-DRIFT") from None
        if interpreter_after != interpreter_before:
            raise PrRouteDenied(prefix + "-SCAN-IDENTITY-DRIFT")
        records = tuple(replace(record,
            closure_after=closure_after,
            interpreter_identity_after=interpreter_after,
            provenance_verdict="trusted",
        ) for record in records)
        try:
            if native is not None:
                observation_after = _capture_repository_observation(
                    modules.policy_module, Path(repository_workdir), git_exe,
                )
                if observation_after != captured_review.repository_observation:
                    raise PrRouteDenied("PGG-TARGET-CURRENTNESS")
                _request_after, native_binding_after = _native_push_selection(native, observation_after, modules.policy_module.C)
                if _request_after != request:
                    raise PrRouteDenied("PGG-TARGET-CURRENTNESS")
                binding_after = native_binding_after if native_objects else _refresh_scan_binding(binding, repository_workdir, git_exe)
            else:
                binding_after = _refresh_scan_binding(binding, repository_workdir, git_exe)
        except PrRouteDenied:
            raise
        except Exception:
            mismatch = "PGG-RANGE-TIP-BINDING" if prefix == "PGG" else "PRG-RECEIPT-MISMATCH"
            raise PrRouteDenied(mismatch) from None
        settlement = pending.settlement
        certificate_tick = (
            settlement.certificate.verified_at_monotonic_tick
            if isinstance(settlement, GateSettlement) and settlement.certificate is not None
            else 0.0
        )
        freshness_tick = max(time.monotonic(), certificate_tick + 1e-9)

        def finalize_review(
            qualification: QualifiedPublicationEvidence,
        ) -> tuple[dict, list[list[str]]]:
            return _verify_used_review_currentness(
                captured_review,
                qualification,
                repository_workdir,
                git_exe,
                prefix + "-SCAN-REFUSAL",
            )

        return pending.correlate_and_consume_once(
            launched, records, closure_after, interpreter_after,
            binding_after, freshness_tick,
            finalize_review=finalize_review,
        )
    except BaseException as exc:
        primary_failure = exc
        raise
    finally:
        cleanup_failures: list[BaseException] = []
        if modules is not None:
            try:
                _release_captured_review_modules(modules)
            except BaseException as exc:
                cleanup_failures.append(exc)
        for fd in fds:
            try:
                os.close(fd)
            except BaseException as exc:
                cleanup_failures.append(exc)
        if cleanup_failures:
            if primary_failure is not None:
                try:
                    setattr(
                        primary_failure,
                        "publication_gate_finalization_cleanup_failures",
                        tuple(cleanup_failures),
                    )
                except BaseException:
                    pass
                raise primary_failure from cleanup_failures[0]
            failure = PrRouteDenied(prefix + "-SCAN-PROVENANCE")
            try:
                setattr(
                    failure,
                    "publication_gate_finalization_cleanup_failures",
                    tuple(cleanup_failures),
                )
            except BaseException:
                pass
            raise failure from cleanup_failures[0]


def _run_text(
    argv: list[str],
    deadline: float,
    failure_id: str,
    repository_workdir: str,
    *,
    accepted_codes: tuple[int, ...] = (0,),
    workdir_diagnostic: WorkdirDiagnostic | None = None,
) -> tuple[int, str]:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise PrRouteDenied(failure_id, workdir_diagnostic=(
            workdir_diagnostic._replace(check="deadline") if workdir_diagnostic else None
        ))
    try:
        result = _run_process(argv, remaining, repository_workdir)
    except Exception as primary:
        categorized = _safe_process_failure(primary)
        if categorized is None:
            raise
        denied = PrRouteDenied(failure_id, workdir_diagnostic=(
            workdir_diagnostic._replace(check="process-result") if workdir_diagnostic else None
        ))
        denied.publication_gate_process_failure, denied.publication_gate_process_outcome = categorized
        raise denied from primary
    if result is None or result.returncode not in accepted_codes:
        denied = PrRouteDenied(failure_id, workdir_diagnostic=(
            workdir_diagnostic._replace(check="process-result") if workdir_diagnostic else None
        ))
        if result is not None:
            _retain_process_failure(denied, {
                "returncode": result.returncode, "stdout": result.stdout,
                "stderr": result.stderr, "complete": type(result.stdout) is bytes and type(result.stderr) is bytes,
                "resourcesSettled": True,
            }, "exit-code")
        raise denied
    try:
        return result.returncode, result.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise PrRouteDenied(failure_id, workdir_diagnostic=(
            workdir_diagnostic._replace(check="decode") if workdir_diagnostic else None
        )) from None


def _normalize_repository_workdir(
    repository_workdir: str, *, subject: str = "invocation", source: str = "unacquired",
) -> str:
    stage = {
        "authorization": "authorization-normalization", "literal": "literal-normalization",
    }.get(subject, "invocation-qualification")
    diagnostic = WorkdirDiagnostic.from_value(stage, "non-string", subject, source, repository_workdir)
    if type(repository_workdir) is not str or not repository_workdir:
        raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=diagnostic._replace(
            check="non-string" if type(repository_workdir) is not str else "empty",
        ))
    check = "resolve-failed"
    try:
        candidate = Path(repository_workdir)
        if not candidate.is_absolute():
            raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=diagnostic._replace(check="relative"))
        selected = candidate.resolve(strict=True)
        if not selected.is_dir():
            raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=diagnostic._replace(check="not-directory"))
        if os.path.normcase(str(selected)) != os.path.normcase(repository_workdir):
            raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=diagnostic._replace(check="canonical-mismatch"))
        # Case folding may make a reparse alias look like the selected root.
        # Require every lexical component to remain an ordinary directory.
        check = "ordinary-directory"
        for count in range(1, len(candidate.parts) + 1):
            _directory_generation(Path(*candidate.parts[:count]))
    except (OSError, RuntimeError, ValueError):
        raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=diagnostic._replace(check=check)) from None
    return str(selected)


def _prepare_selected_repository_workdir(
    literal_context: tuple[str, str] | None,
    repository_workdir: str,
    repository_workdir_source: str,
) -> str | None:
    """Qualify the selected E and preserve only P-proved literal absence."""
    source = repository_workdir_source if (
        type(repository_workdir_source) is str and repository_workdir_source in {"tool", "envelope"}
    ) else "unacquired"
    diagnostic = WorkdirDiagnostic.from_value(
        "invocation-qualification", "selected-types", "invocation", source, repository_workdir,
    )
    if (
        type(repository_workdir) is not str
        or type(repository_workdir_source) is not str
    ):
        raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=diagnostic)
    if literal_context is not None and (
        type(literal_context) is not tuple
        or len(literal_context) != 2
        or any(type(value) is not str for value in literal_context)
        or any(not value or "\x00" in value for value in literal_context)
        or not Path(literal_context[0]).is_absolute()
        or not Path(literal_context[1]).is_absolute()
    ):
        raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=WorkdirDiagnostic.from_value(
            "invocation-qualification", "literal-context", "literal", "literal", literal_context,
        ))
    if repository_workdir_source in {"tool", "envelope"}:
        return _normalize_repository_workdir(repository_workdir, source=repository_workdir_source)
    if (
        repository_workdir_source == ""
        and repository_workdir == ""
        and literal_context is not None
    ):
        return None
    raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=diagnostic._replace(check="selection-source"))


def _prove_repository_root(
    repository_workdir: str, git_exe: str, *, subject: str = "repository", source: str = "derived-repository",
) -> str:
    selected = Path(repository_workdir)
    diagnostic = WorkdirDiagnostic(
        "repository-root-proof", "root-output", subject, source, "string",
    )
    _, top_text = _run_text(
        [git_exe, "rev-parse", "--show-toplevel"],
        time.monotonic() + PROCESS_TIMEOUT_SECONDS,
        "PRG-WORKDIR-INVALID",
        repository_workdir,
        workdir_diagnostic=diagnostic,
    )
    rows = top_text.splitlines()
    if len(rows) != 1:
        raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=diagnostic)
    try:
        top = Path(rows[0]).resolve(strict=True)
    except (OSError, RuntimeError):
        raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=diagnostic._replace(check="resolve-failed")) from None
    if top != selected:
        raise PrRouteDenied("PRG-WORKDIR-INVALID", workdir_diagnostic=diagnostic._replace(check="root-mismatch"))
    return repository_workdir


def _strict_json(text: str, expected_type: type, failure_id: str):
    def no_duplicates(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON key")
            value[key] = item
        return value

    try:
        parsed = json.loads(text, object_pairs_hook=no_duplicates)
    except (json.JSONDecodeError, ValueError):
        raise PrRouteDenied(failure_id) from None
    if not isinstance(parsed, expected_type):
        raise PrRouteDenied(failure_id)
    return parsed


def _resolve_generic_scan_binding(
    remote: str, destination: str, source: str, repository_workdir: str,
    git_exe: str,
) -> PushScanBinding:
    if not source:
        raise PrRouteDenied("PGG-RANGE-TIP-BINDING")
    object_format = _detect_git_object_format(
        repository_workdir, git_exe, "PGG-RANGE-TIP-BINDING"
    )
    source_proc = subprocess.run(
        [git_exe, "rev-parse", "--verify", source],
        capture_output=True, text=True, encoding="utf-8", errors="strict",
        cwd=repository_workdir,
    )
    source_rows = source_proc.stdout.splitlines()
    if (
        source_proc.returncode
        or len(source_rows) != 1
        or not object_format.matches(source_rows[0])
    ):
        raise PrRouteDenied("PGG-RANGE-TIP-BINDING")
    source_oid = source_rows[0].lower()
    type_proc = subprocess.run(
        [git_exe, "cat-file", "-t", source_oid],
        capture_output=True, text=True, encoding="utf-8", errors="strict",
        cwd=repository_workdir,
    )
    if type_proc.returncode or type_proc.stdout.strip() != "commit":
        raise PrRouteDenied("PGG-RANGE-TIP-BINDING")
    head_proc = subprocess.run(
        [git_exe, "rev-parse", "--verify", "HEAD^{commit}"],
        capture_output=True, text=True, encoding="utf-8", errors="strict",
        cwd=repository_workdir,
    )
    head_rows = head_proc.stdout.splitlines()
    if (
        head_proc.returncode
        or len(head_rows) != 1
        or not object_format.matches(head_rows[0])
    ):
        raise PrRouteDenied("PGG-RANGE-TIP-BINDING")
    return PushScanBinding(
        "generic", remote, destination, source_oid, head_rows[0].lower()
    )


def native_git_config_arguments() -> tuple[str, ...]:
    """Explicit per-command registration; the caller chooses the actual push."""
    interpreter = _interpreter_identity().absolute_resolved_path
    entry = os.path.abspath(__file__)
    _regular_identity(Path(entry), single_link=True)
    command = shlex.join((interpreter, entry, "--git-pre-push"))
    prefix = f"hook.{NATIVE_PUBLICATION_HOOK}."
    return tuple(argument for assignment in (
        prefix + "command=" + command,
        prefix + "event=", prefix + "event=pre-push",
        prefix + "enabled=true", prefix + "parallel=false",
    ) for argument in ("-c", assignment))


def _native_configuration_query(
    git_exe: str, prefix: tuple[str, ...], cwd: str, arguments: tuple[str, ...],
    *, accepted: tuple[int, ...] = (0,),
) -> ProcessResult:
    result = _run_process([git_exe, *prefix, *arguments], PROCESS_TIMEOUT_SECONDS, cwd)
    if result is None or result.returncode not in accepted:
        raise PrRouteDenied("PGG-NATIVE-CONFIGURATION")
    return result


def _native_config_values(git_exe: str, prefix: tuple[str, ...], cwd: str, key: str, *, boolean: bool = False) -> tuple[bytes, ...]:
    options = ("--type=bool",) if boolean else ()
    result = _native_configuration_query(
        git_exe, prefix, cwd, ("config", "--null", *options, "--get-all", key), accepted=(0, 1),
    )
    if result.returncode == 1:
        if result.stdout:
            raise PrRouteDenied("PGG-NATIVE-CONFIGURATION")
        return ()
    if not result.stdout.endswith(b"\0"):
        raise PrRouteDenied("PGG-NATIVE-CONFIGURATION")
    return tuple(result.stdout[:-1].split(b"\0"))


def _qualify_native_recursion(push, git_exe: str, cwd: str) -> None:
    mode = None
    for occurrence in push.push_option_occurrences:
        if occurrence.spelling == "--no-recurse-submodules":
            mode = "no"
        elif occurrence.spelling == "--recurse-submodules":
            index = occurrence.consumed_value_index
            if index is None or not 0 <= index < len(push.post_subcommand_tokens):
                raise PrRouteDenied("PGG-NATIVE-CONFIGURATION")
            value = push.post_subcommand_tokens[index]
            mode = value.partition("=")[2] if value.startswith("--recurse-submodules=") else value
    if mode is None:
        values = _native_config_values(git_exe, push.git_global_options, cwd, "push.recurseSubmodules")
        if values:
            try:
                mode = values[-1].decode("ascii")
            except UnicodeError:
                raise PrRouteDenied("PGG-NATIVE-CONFIGURATION") from None
        else:
            recursive = _native_config_values(git_exe, push.git_global_options, cwd, "submodule.recurse", boolean=True)
            mode = "on-demand" if recursive and recursive[-1] == b"true" else "no"
    if mode in {"on-demand", "only"}:
        # Native command configuration is inherited, but a child's event may
        # be disabled. Parent qualification is not proof of that transport.
        raise PrRouteDenied("PGG-NATIVE-RECURSION-UNQUALIFIED")
    if mode not in {"no", "check"}:
        raise PrRouteDenied("PGG-NATIVE-CONFIGURATION")


class _NativeEntryDenied(PrRouteDenied):
    """Retain only the fixed, non-sensitive native-entry decision stage."""

    _STAGES = frozenset({"invocation-unqualified", "command-mismatch", "registration-event-mismatch"})

    def __init__(self, stage: str) -> None:
        if stage not in self._STAGES:
            raise ValueError("invalid native-entry diagnostic stage")
        super().__init__("PGG-NATIVE-ENTRY-REQUIRED")
        self.stage = stage


def _qualify_native_push_command(preflight: PreflightResult) -> bool:
    push = native_push_invocation(preflight.parsed) if preflight.parsed is not None else None
    if push is None:
        raise _NativeEntryDenied("invocation-unqualified")
    verification = [row.spelling for row in push.push_option_occurrences if row.spelling in {"--verify", "--no-verify"}]
    if verification and verification[-1] == "--no-verify":
        raise PrRouteDenied("PGG-NATIVE-DISABLED")
    literal_context = absolute_literal_root_context(preflight.parsed)
    selected = _prepare_selected_repository_workdir(
        literal_context, preflight.repository_workdir, preflight.repository_workdir_source,
    )
    cwd = selected or (literal_context[1] if literal_context is not None else None)
    if cwd is None:
        raise PrRouteDenied("PRG-WORKDIR-INVALID")
    git_exe = _resolve_executable("git", cwd)
    if git_exe is None:
        raise PrRouteDenied("PGG-NATIVE-CONFIGURATION")
    if push.executable != Path(push.executable).name or Path(push.executable).is_absolute():
        literal_executable = push.executable if Path(push.executable).is_absolute() else str(Path(cwd) / push.executable)
        _bind_literal_executable_identity(literal_executable, git_exe, "PGG-EXECUTABLE-MISMATCH")
    interpreter_before = _interpreter_identity()
    entry = Path(os.path.abspath(__file__))
    entry_before = _regular_identity(entry, single_link=True)
    expected = shlex.join((interpreter_before.absolute_resolved_path, str(entry), "--git-pre-push"))
    own_prefix = f"hook.{NATIVE_PUBLICATION_HOOK}."
    supplied = git_prefix_configuration(push)
    own = [(key, value) for key, value in supplied if key.startswith(own_prefix)]
    events = [value for key, value in own if key == own_prefix + "event"]
    if not any(key == own_prefix + "command" and value == expected for key, value in own):
        raise _NativeEntryDenied("command-mismatch")
    if not events or "" not in events or events[len(events) - 1 - events[::-1].index(""):] != ["", "pre-push"]:
        raise _NativeEntryDenied("registration-event-mismatch")
    commands = _native_config_values(git_exe, push.git_global_options, cwd, own_prefix + "command")
    if not commands or any(value != os.fsencode(expected) for value in commands):
        raise PrRouteDenied("PGG-NATIVE-COLLISION")
    enabled = _native_config_values(git_exe, push.git_global_options, cwd, own_prefix + "enabled", boolean=True)
    if any(value != b"true" for value in enabled):
        raise PrRouteDenied("PGG-NATIVE-DISABLED")
    parallel = _native_config_values(git_exe, push.git_global_options, cwd, own_prefix + "parallel", boolean=True)
    if not parallel or parallel[-1] != b"false":
        # Qualify our selected registration's output/scheduling contract;
        # other hooks' jobs and parallel settings retain their Git semantics.
        raise PrRouteDenied("PGG-NATIVE-CONFIGURATION")
    all_events = _native_config_values(git_exe, push.git_global_options, cwd, own_prefix + "event")
    if any(value not in {b"", b"pre-push"} for value in all_events):
        raise PrRouteDenied("PGG-NATIVE-COLLISION")
    hooks = _native_configuration_query(
        git_exe, push.git_global_options, cwd, ("hook", "list", "-z", "--show-scope", "pre-push"),
    ).stdout
    if not hooks.endswith(b"\0") or hooks[:-1].split(b"\0").count(b"command\t" + NATIVE_PUBLICATION_HOOK.encode("ascii")) != 1:
        raise PrRouteDenied("PGG-NATIVE-DISABLED")
    repository = _native_configuration_query(
        git_exe, push.git_global_options, cwd, ("rev-parse", "--show-toplevel"),
    ).stdout
    if not repository.endswith(b"\n") or b"\0" in repository:
        raise PrRouteDenied("PGG-NATIVE-CONFIGURATION")
    _normalize_repository_workdir(os.fsdecode(repository[:-1]), source="native-git")
    object_format_result = _native_configuration_query(
        git_exe, push.git_global_options, cwd, ("rev-parse", "--show-object-format"),
    ).stdout
    if object_format_result not in {b"sha1\n", b"sha256\n"}:
        raise PrRouteDenied("PGG-NATIVE-CONFIGURATION")
    try:
        object_format = _SUPPORTED_OBJECT_FORMATS[object_format_result.decode("ascii").removesuffix("\n")]
    except (KeyError, UnicodeError):
        raise PrRouteDenied("PGG-NATIVE-CONFIGURATION") from None
    native_push_refspecs(push, object_format.hex_length)
    _qualify_native_recursion(push, git_exe, cwd)
    if entry_before != _regular_identity(entry, single_link=True) or interpreter_before != _interpreter_identity():
        raise PrRouteDenied("PGG-SCAN-IDENTITY-DRIFT")
    return True


def evaluate_heavy(preflight: PreflightResult) -> bool:
    """Qualify the native owner; Git supplies its actual ranges at pre-push."""
    validate_preflight_result(preflight)
    if (preflight.generic_decision.status == "PGG-COMPOUND-CONTEXT"
        and native_push_invocation(preflight.parsed) is None):
        raise PrRouteDenied("PGG-COMPOUND-CONTEXT")
    _qualify_native_push_command(preflight)
    return True


def _format_process_failure(error: BaseException) -> str:
    selected = _safe_process_failure(error)
    if selected is None:
        return ""
    metadata, outcome = selected
    def number(value):
        return "none" if value is None else str(value)
    return (
        f"Process diagnostics: kind={metadata['kind']}; exit={number(outcome['returncode'])}; "
        f"errno={number(metadata['errno'])}; winerror={number(metadata['winerror'])}; "
        f"complete={str(outcome['complete']).lower()}; resources-settled={str(outcome['resourcesSettled']).lower()}."
    )


def _format_compound_context_diagnostic(result: PreflightResult) -> str:
    """Expose only closed parser facts; revision labels are not attestations."""
    parsed = result.parsed
    if parsed is None:
        return (
            f"Command context: gate={PUBLICATION_GATE_REVISION}; "
            f"preflight={PUBLICATION_PREFLIGHT_REVISION}; branch=UNAVAILABLE; "
            "operation=UNAVAILABLE; dialect=UNAVAILABLE; commands=UNAVAILABLE; "
            "effective=UNAVAILABLE; eligible=UNAVAILABLE; literal=UNAVAILABLE."
        )
    projection = parsed.effective_publications
    counts = (len(parsed.commands), len(projection.records), len(projection.eligible_direct_generic))
    branch = "UNAVAILABLE"
    if classify_generic_push(parsed).status == "PGG-COMPOUND-CONTEXT":
        branch = "cardinality" if counts != (1, 1, 1) else "shell-boundary"
    dialect = parsed.dialect if parsed.dialect in {"posix", "powershell"} else "UNAVAILABLE"
    # The validated preflight does not retain the incoming tool operation.
    # Never guess it from command text, dialect or a native handler label.
    return (
        f"Command context: gate={PUBLICATION_GATE_REVISION}; "
        f"preflight={PUBLICATION_PREFLIGHT_REVISION}; branch={branch}; "
        f"operation=UNAVAILABLE; dialect={dialect}; commands={counts[0]}; "
        f"effective={counts[1]}; eligible={counts[2]}; "
        f"literal={str(literal_direct_command(parsed) is not None).lower()}."
    )


def compose_gate_result(preflight: PreflightResult) -> int:
    """Compose technical scan qualification; never attest human consent."""
    try:
        result = validate_preflight_result(preflight)
    except Exception:
        result = PreflightResult("DEFER", "PFP-DENY-INTERNAL", "RENDER_DENY")
    if result.outcome == "ALLOW_FINAL" or (
        result.outcome == "ABSTAIN" and result.continuation == "NONE"
    ):
        return 0
    failure_id = result.failure_id or "PRG-INTERNAL"
    workdir_diagnostic = result.workdir_diagnostic
    process_diagnostic = ""
    native_entry_stage = None
    if result.continuation == "EVALUATE_HEAVY":
        try:
            if evaluate_heavy(result):
                return 0
        except PrRouteDenied as exc:
            failure_id = exc.failure_id
            workdir_diagnostic = exc.workdir_diagnostic
            process_diagnostic = _format_process_failure(exc)
            if type(exc) is _NativeEntryDenied and exc.stage in _NativeEntryDenied._STAGES:
                native_entry_stage = exc.stage
        except Exception:
            failure_id = "PRG-INTERNAL"
    reasons = {
        **SCAN_DENIAL_REASONS,
        "PRG-INTERNAL": "The publication check did not complete; resolve its technical failure before retrying.",
        "PRG-WORKDIR-INVALID": "Use one explicit absolute repository root for the push tool call.",
        "PGG-COMPOUND-CONTEXT": "Run one direct push as a solitary shell command.",
        "PGG-LEXICAL-NORMALIZATION": "Use one literal unnormalized push command.",
        "PGG-OPTION-ARITY": "Use complete documented push options.",
        "PGG-PARSE-UNCERTAIN": "Provide an unambiguous command in the actual tool dialect.",
        "PGG-REPOSITORY-REDIRECT": "Use the selected repository without unsupported command-local redirection.",
        "PGG-ENV-PREFIX": "Run the push without an environment-assignment prefix.",
        "PGG-GIT-GLOBAL-OPTION": "Use the supported direct push command form.",
        "PGG-EXECUTABLE-MISMATCH": "Use the Git executable selected for this repository.",
        "PGG-PUSH-OPTION": "Use only supported output-only push options.",
        "PGG-REMOTE-CARDINALITY": "Name exactly one remote and one refspec.",
        "PGG-REFSPEC-CARDINALITY": "Name exactly one remote and one refspec.",
        "PGG-DESTINATION-SHAPE": "Use a refspec with a non-empty full branch destination.",
        "PGG-RANGE-BINDING": "Resolve the actual remote and destination for this push.",
        "PGG-RANGE-TIP-BINDING": "Select one unambiguous source commit and current HEAD for the scan.",
        "PGG-TARGET-IDENTITY": "Resolve the actual repository identity and single push endpoint.",
        "PGG-TARGET-CURRENTNESS": "The repository, endpoint or source changed during the check; qualify this push again.",
        "PGG-RANGE-RECEIPT-VERSION": "The gate requires its own fresh complete version-3 range result.",
        "PGG-NATIVE-ENTRY-REQUIRED": "Use the verified command-scoped native pre-push registration so Git supplies the actual object set to the scanner.",
        "PGG-NATIVE-CONFIGURATION": "The effective native hook configuration could not be qualified for this invocation.",
        "PGG-NATIVE-COLLISION": "The selected native hook name conflicts with an existing command or event; preserve that configuration.",
        "PGG-NATIVE-DISABLED": "This invocation disables or bypasses its required native publication scan.",
        "PGG-NATIVE-RECURSION-UNQUALIFIED": "This recursive push may transfer child repositories whose native scan is not yet qualified; qualify those child contexts before submitting it.",
        "PGG-NATIVE-REFSPEC-UNQUALIFIED": "This invocation requires explicit refspec operands; configured/default expansion remains unqualified and the command was not rewritten.",
        "PGG-NATIVE-REFSPEC-LF": "An explicit refspec contains a line feed, which makes Git's native callback ambiguous; the command was not submitted.",
        "PGG-NATIVE-INPUT": "The actual native pre-push selection could not be received completely.",
        "PGG-NATIVE-RECEIPT-VERSION": "Native transfer requires its own fresh complete version-4 result; a commit-only receipt is not full-set evidence.",
        "PGG-NATIVE-RECEIPT-BINDING": "The scanner result does not match this exact native selection and repository.",
    }
    if failure_id not in reasons:
        failure_id = "PRG-INTERNAL"
    reason = f"{failure_id}: {reasons[failure_id]}"
    if failure_id == "PGG-NATIVE-ENTRY-REQUIRED" and native_entry_stage is not None:
        reason += f" Native-entry diagnostic: stage={native_entry_stage}."
    if failure_id == "PGG-COMPOUND-CONTEXT":
        reason += " " + _format_compound_context_diagnostic(result)
    if failure_id == "PRG-WORKDIR-INVALID" and workdir_diagnostic is not None:
        try:
            diagnostic = validate_workdir_diagnostic(workdir_diagnostic)
        except (TypeError, ValueError):
            diagnostic = None
        if diagnostic is not None:
            reason += (
                f" Workdir diagnostics: stage={diagnostic.stage}; check={diagnostic.check}; "
                f"subject={diagnostic.subject}; source={diagnostic.source}; "
                f"value-kind={diagnostic.value_kind}."
            )
    if process_diagnostic:
        reason += " " + process_diagnostic
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    return 0


def _native_callback_currentness(native: NativePushInput, root: str, git_exe: str) -> tuple[bytes, ...]:
    """Keep HEAD, actual source operands and the selected endpoint current."""
    if native.wire and not native.wire.endswith(b"\n"):
        raise PrRouteDenied("PGG-NATIVE-INPUT")
    observations = [_native_configuration_query(git_exe, (), root,
        ("rev-parse", "--verify", "HEAD^{commit}")).stdout]
    for row in native.wire.split(b"\n")[:-1]:
        fields = row.rsplit(b" ", 3)
        if len(fields) != 4:
            raise PrRouteDenied("PGG-NATIVE-INPUT")
        if fields[0] == b"(delete)":
            continue
        source = _native_configuration_query(git_exe, (), root,
            ("rev-parse", "--verify", "--end-of-options", os.fsdecode(fields[0]))).stdout
        if source != fields[1] + b"\n":
            raise PrRouteDenied("PGG-TARGET-CURRENTNESS")
        observations.append(source)
    endpoint = _native_configuration_query(git_exe, (), root,
        ("remote", "get-url", "--push", "--all", native.remote_name), accepted=(0, 2, 128))
    if endpoint.returncode == 0:
        if endpoint.stdout != os.fsencode(native.endpoint) + b"\n":
            raise PrRouteDenied("PGG-TARGET-CURRENTNESS")
        observations.append(endpoint.stdout)
    elif native.remote_name != native.endpoint:
        raise PrRouteDenied("PGG-TARGET-CURRENTNESS")
    return tuple(observations)


def _native_pre_push_main(arguments: list[str]) -> int:
    """Git owns invocation and transfer; any failure here stops this callback."""
    try:
        if len(arguments) != 2:
            raise PrRouteDenied("PGG-NATIVE-INPUT")
        selected = _normalize_repository_workdir(os.getcwd(), source="native-git")
        git_exe = _resolve_executable("git", selected)
        if git_exe is None:
            raise PrRouteDenied("PGG-NATIVE-INPUT")
        root = _prove_repository_root(selected, git_exe, source="native-git")
        native = NativePushInput(arguments[0], arguments[1], sys.stdin.buffer.read())
        # V3 exposes its exact remote token in both argv and its public receipt.
        # Named remotes keep their private endpoint in captured stdin, but a
        # credential-bearing literal cannot satisfy that unchanged wire safely.
        remote_url = urlsplit(native.remote_name)
        if remote_url.username is not None or remote_url.password is not None:
            raise PrRouteDenied("PGG-TARGET-IDENTITY")
        current = _native_callback_currentness(native, root, git_exe)
        # The V3 wire remains the ordinary range receipt. Its captured scanner
        # selects the union from these same native bytes, not a remote probe.
        primary = None
        for row in native.wire.split(b"\n")[:-1]:
            fields = row.rsplit(b" ", 3)
            if len(fields) != 4:
                raise PrRouteDenied("PGG-NATIVE-INPUT")
            source = fields[1].decode("ascii")
            if source and set(source) == {"0"}:
                continue
            result = _native_configuration_query(git_exe, (), root,
                ("rev-parse", "--verify", "--end-of-options", source + "^{commit}"), accepted=(0, 128))
            if result.returncode == 0:
                primary = _resolve_generic_scan_binding(native.remote_name,
                    os.fsdecode(fields[2]), result.stdout.decode("ascii").strip(), root, git_exe)
                break
        if primary is None:
            # V4 still owns annotations and other actual roots even when the
            # mandatory nonempty commit graph cannot qualify publication.
            evidence = _run_authoritative_scan(native, root, git_exe)
            raise PrRouteDenied("PGG-RANGE-RECEIPT-VERSION")
        range_evidence = _run_authoritative_scan(primary, root, git_exe, native_input=native)
        if (range_evidence.parsed_outcome.kind not in {"valid-v3", "qualified-v3"}
            or range_evidence.execution is None or range_evidence.binding != primary):
            raise PrRouteDenied("PGG-RANGE-RECEIPT-VERSION")
        if _native_callback_currentness(native, root, git_exe) != current:
            raise PrRouteDenied("PGG-TARGET-CURRENTNESS")
        evidence = _run_authoritative_scan(native, root, git_exe)
        if (
            evidence.parsed_outcome.kind not in {"valid-v4", "qualified-v4"}
            or evidence.execution is None
            or not isinstance(evidence.binding, NativePushScanBinding)
        ):
            raise PrRouteDenied("PGG-NATIVE-RECEIPT-VERSION")
        if _native_callback_currentness(native, root, git_exe) != current:
            raise PrRouteDenied("PGG-TARGET-CURRENTNESS")
        if (evidence.execution.closure_after != range_evidence.execution.closure_after
            or evidence.execution.pending.captured_review.repository_observation
                != range_evidence.execution.pending.captured_review.repository_observation):
            raise PrRouteDenied("PGG-SCAN-IDENTITY-DRIFT")
        qualified_scans = tuple(result for result in (range_evidence, evidence)
            if result.parsed_outcome.kind in {"qualified-v3", "qualified-v4"})
        if qualified_scans:
            # Both scans' exact used decisions share one final policy capture.
            # Neither scanner result keeps the other's used authority current.
            # Both scan owners settled their module slots; acquire the same
            # captured code for this final use and settle it on every exit.
            modules = _load_captured_review_modules(range_evidence.execution.closure_after)
            try:
                first, *remaining = qualified_scans
                finalization, _used = _verify_used_review_currentness(
                    replace(first.execution.pending.captured_review, modules=modules),
                    first.parsed_outcome.qualification,
                    root, git_exe, "PGG-SCAN-REFUSAL",
                    additional_reviews=tuple((result.execution.pending.captured_review,
                        result.parsed_outcome.qualification) for result in remaining),
                )
            finally:
                _release_captured_review_modules(modules)
        # Display only the validated receipts. The private native payload,
        # including a named remote's endpoint credentials, is never printed.
        sys.stdout.write(range_evidence.execution.stdout.decode("utf-8", errors="strict"))
        sys.stdout.write(evidence.execution.stdout.decode("utf-8", errors="strict"))
        return 0
    except PrRouteDenied as exc:
        print(f"{exc.failure_id}: Native publication scan did not qualify this transfer.", file=sys.stderr)
        return 2
    except Exception:
        print("PGG-SCAN-EXECUTION: Native publication scan did not complete.", file=sys.stderr)
        return 2


def main(preflight: PreflightResult | None = None) -> int:
    if preflight is None and len(sys.argv) > 1 and sys.argv[1] == "--git-pre-push":
        return _native_pre_push_main(sys.argv[2:])
    try:
        result = (
            build_preflight_from_stdin()
            if preflight is None
            else validate_preflight_result(preflight)
        )
    except Exception:
        result = PreflightResult("DEFER", "PFP-DENY-INTERNAL", "RENDER_DENY")
    return compose_gate_result(result)


if __name__ == "__main__":
    raise SystemExit(main())
