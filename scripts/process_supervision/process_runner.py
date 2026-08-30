#!/usr/bin/env python3
"""Bounded, consumer-neutral process supervision.

The reusable surface returns typed results and never terminates its caller.
The command-line entry point is deliberately nonauthorizing and accepts only a
private, capability-bound ProcessRequestFileV1 bundle.
"""

from __future__ import annotations

import argparse
import ctypes
import dataclasses
import errno
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import shlex
import stat
import struct
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence


SCHEMA_VERSION = 1
SETTLED_EVENT_ID = "process.supervision.settled.v1"
REQUEST_SCHEMA = "orchestrarium.process-request.v1"
REQUEST_MAGIC = b"OPSRQV1\0"
CAPABILITY_MAGIC = b"OPCAPV1\0"
MAX_ARGV_COUNT = 1024
MAX_ARG_BYTES = 32 * 1024
MAX_ARGV_BYTES = 128 * 1024
MAX_ENVIRONMENT_COUNT = 128
MAX_ENVIRONMENT_NAME_BYTES = 128
MAX_ENVIRONMENT_VALUE_BYTES = 64 * 1024
MAX_ENVIRONMENT_BYTES = 128 * 1024
MAX_STDIN_BYTES = 16 * 1024 * 1024
MAX_JSON_HEADER_BYTES = 512 * 1024
MAX_REQUEST_BUNDLE_BYTES = 17_301_556
MAX_WINDOWS_COMMAND_LINE_UNITS = 32_766
MAX_WINDOWS_ENVIRONMENT_UNITS = 32_767
MAX_PATH_BYTES = 32 * 1024
MAX_REGISTRY_TOKEN_BYTES = 128
MAX_CAPTURE_BYTES = 256 * 1024 * 1024
ENGINE_POLL_INTERVAL_SECONDS = 0.05
RUNNER_CLOSE_TIMEOUT_SECONDS = 5.0
MAX_IO_WORKERS = 3
MAX_RUN_COUNTER = (1 << 64) - 1

FAILURE_IDS = frozenset(
    {
        "PSV1-REQUEST-INVALID",
        "PSV1-EXECUTABLE-UNRESOLVED",
        "PSV1-ARGV-CODEC-UNSUPPORTED",
        "PSV1-ARGV-ATTESTATION",
        "PSV1-HANDLE-INHERITANCE",
        "PSV1-INHERITANCE-POISONED",
        "PSV1-ATTRIBUTE-LIST",
        "PSV1-PROCESS-CREATE",
        "PSV1-TREE-VERIFICATION",
        "PSV1-PROCESS-RESUME",
        "PSV1-JOB-TERMINATE",
        "PSV1-STDIN-SHORT-WRITE",
        "PSV1-STDIN-BROKEN-PIPE",
        "PSV1-CAPTURE-LIMIT",
        "PSV1-CAPTURE-IO",
        "PSV1-DEADLINE",
        "PSV1-DEADLINE-COMPOSITION",
        "PSV1-CANCELLED",
        "PSV1-TREE-SETTLEMENT",
        "PSV1-POSIX-ORACLE-UNAVAILABLE",
        "PSV1-WORKER-LIMIT",
        "PSV1-RUNNER-CLOSED",
        "PSV1-RUNNER-CLOSE-INCOMPLETE",
        "PSV1-CLI-CLAIM",
        "PSV1-CLI-CAPABILITY",
        "PSV1-CLI-PRIVATE-DIRECTORY-UNAVAILABLE",
        "PSV1-DESCRIPTOR-OWNERSHIP",
        "PSV1-RESOURCE-CLOSE",
        "PSV1-INTERNAL",
    }
)
TERMINAL_STAGES = frozenset(
    {
        "request-validation",
        "handle-preparation",
        "process-create",
        "tree-verification",
        "process-resume",
        "stdin-delivery",
        "execution",
        "capture-limit",
        "deadline",
        "cancellation",
        "tree-settlement",
        "resource-cleanup",
        "completed",
    }
)
_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_LOWER_HEX_32 = re.compile(r"[0-9a-f]{32}\Z")
_LOWER_HEX_64 = re.compile(r"[0-9a-f]{64}\Z")
_WINDOWS_SHELL_HOSTS = frozenset(
    {"cmd.exe", "powershell.exe", "pwsh.exe", "wscript.exe", "cscript.exe"}
)
_POSIX_SHELL_HOSTS = frozenset({"sh", "bash", "dash", "zsh", "fish", "ksh", "csh"})
_WINDOWS_ARGV_PROFILES = frozenset(
    {
        "python-hook-health-v1",
        "python-validator-json-echo-v1",
        "git-rev-parse-sq-quote-v1",
        "repository-transfer-git-v1",
    }
)


class KimiWindowsProfileV1:
    """The sole owner of the sealed Windows Kimi bundle grammar."""

    profile_id = "kimi-sealed-bundle-text-v1"
    probe_profile_id = "kimi-metadata-probe-v2"
    model = "kimi-code/k3"
    constant_prompt = "Review the sealed bundle and return only the requested result."
    argv_shape = (
        "--agent-file", None,
        "--skills-dir", None,
        "--model", model,
        "--output-format", "text",
        "--prompt", constant_prompt,
    )
    agent_frontmatter = (
        b"---\n"
        b"name: orchestrarium-bundle-reviewer\n"
        b"description: Reviews only the context bundled in this file\n"
        b"tools: []\n"
        b"subagents: []\n"
        b"---\n\n"
    )

    @classmethod
    def build_args(cls, agent_file: Path, skills_dir: Path) -> list[str]:
        arguments = list(cls.argv_shape)
        arguments[1] = str(agent_file.resolve(strict=True))
        arguments[3] = str(skills_dir.resolve(strict=True))
        return arguments

    @classmethod
    def matches_argv(cls, argv: Sequence[str]) -> bool:
        values = argv[1:]
        return len(values) == len(cls.argv_shape) and all(
            expected is None or actual == expected
            for actual, expected in zip(values, cls.argv_shape, strict=True)
        )


_WINDOWS_ARGV_PROFILES = _WINDOWS_ARGV_PROFILES | frozenset(
    {KimiWindowsProfileV1.profile_id, KimiWindowsProfileV1.probe_profile_id}
)


def _is_kimi_executable_profile(profile_id: str | None) -> bool:
    return profile_id in {
        KimiWindowsProfileV1.profile_id,
        KimiWindowsProfileV1.probe_profile_id,
    }
_WINDOWS_INTERNAL_PROBE_CAPTURE_BYTES = 64 * 1024
_WINDOWS_ARGV_PROBE_CANARIES = (
    "",
    "plain",
    "two words",
    'quote"inside',
    'backslashes\\before"quote',
    "C:\\path with space\\",
    "Москва-测试",
)
_PYTHON_ARGV_ECHO_HELPER = (
    "import json,sys;"
    "sys.stdout.buffer.write(json.dumps(sys.argv[1:],ensure_ascii=False,"
    "separators=(',',':')).encode('utf-8'))"
)


class ProcessSupervisionError(ValueError):
    """Typed operational error carrying only stable public discriminators."""

    def __init__(self, failure_id: str, terminal_stage: str):
        if failure_id not in FAILURE_IDS:
            failure_id = "PSV1-INTERNAL"
        if terminal_stage not in TERMINAL_STAGES:
            terminal_stage = "execution"
        self.failure_id = failure_id
        self.terminal_stage = terminal_stage
        super().__init__(f"{failure_id}:{terminal_stage}")


class _WindowsArgvProbeFailure(ProcessSupervisionError):
    def __init__(self, result: ProcessResultV1) -> None:
        self.result = result
        super().__init__(
            result.failure_id or "PSV1-ARGV-ATTESTATION",
            result.terminal_stage,
        )


@dataclass(frozen=True)
class EnvironmentRowV1:
    name: str
    value: str


@dataclass(frozen=True)
class CapturePolicyV1:
    policy_id: str
    aggregate_persisted_limit: int
    prefix_limit_per_stream: int
    tail_limit_per_stream: int
    chunk_size: int


@dataclass(frozen=True)
class RepositoryTransferCapturePolicyV1(CapturePolicyV1):
    per_stream_persisted_limit: int


@dataclass(frozen=True)
class SettlePolicyV1:
    timeout_seconds: float


_WINDOWS_ARGV_ADMISSION_SEAL = object()
_WINDOWS_ARGV_CHILD_EVIDENCE_SEAL = object()
_WINDOWS_INTERNAL_PROBE_ADMISSION_SEAL = object()


@dataclass(frozen=True)
class WindowsArgvAdmissionV1:
    schema_version: int
    run_token_sha256: str
    profile_id: str
    codec: str
    resolved_executable_identity: str
    resolved_executable_version: str
    actual_argv_sha256: str
    actual_argv_shape_sha256: str
    probe_kind: str
    probe_requested_argv_sha256: str
    probe_observed_argv_sha256: str
    expires_at_monotonic: float
    status: str
    _seal: object = field(repr=False, compare=False)
    _child_evidence_seal: object = field(repr=False, compare=False)
    prompt_file_canonical: str | None = None
    prompt_file_identity: str | None = None
    prompt_file_sha256: str | None = None
    executable_binding: "ExecutableBindingV1 | None" = None


@dataclass(frozen=True)
class ExecutableBindingV1:
    """Immutable evidence for the exact object admitted to OS process creation."""

    path: str
    size: int
    sha256: str
    device: int = 0
    inode: int = 0
    mode: int = 0
    mtime_ns: int = 0


def _expected_executable_binding_matches(
    expected: object, live: ExecutableBindingV1
) -> bool:
    """Compare the enrolled portable pin with the live OS-object evidence."""

    if type(expected) is not ExecutableBindingV1:
        return False
    try:
        expected_path = Path(expected.path)
        return (
            expected_path.is_absolute()
            and os.path.normcase(os.path.abspath(expected_path))
            == os.path.normcase(live.path)
            and expected.size == live.size
            and hmac.compare_digest(expected.sha256, live.sha256)
        )
    except (OSError, TypeError, ValueError):
        return False


@dataclass(frozen=True)
class WindowsInternalProbeAdmissionV1:
    schema_version: int
    run_token_sha256: str
    profile_id: str
    purpose: str
    request_sha256: str
    resolved_executable_identity: str
    expires_at_monotonic: float
    _seal: object = field(repr=False, compare=False)


class CancellationProbeV1(Protocol):
    def __call__(self) -> bool: ...


class DiagnosticPortV1(Protocol):
    def emit(self, event_id: str, fields: Mapping[str, object]) -> None: ...


class CaptureSinkV1(Protocol):
    def write(self, stream: str, data: bytes) -> int: ...

    def close(self) -> None: ...

    def reference_digest(self, stream: str) -> str | None: ...


class BoundedMemoryCaptureSinkV1:
    """Bounded in-memory sink intended for tests and small composition roots."""

    def __init__(self) -> None:
        self._streams = {"stdout": bytearray(), "stderr": bytearray()}
        self._closed = False
        self._lock = threading.Lock()

    def write(self, stream: str, data: bytes) -> int:
        with self._lock:
            if self._closed or stream not in self._streams:
                raise OSError("sink unavailable")
            self._streams[stream].extend(data)
            return len(data)

    def close(self) -> None:
        with self._lock:
            self._closed = True

    def bytes_for(self, stream: str) -> bytes:
        with self._lock:
            return bytes(self._streams[stream])

    def reference_digest(self, stream: str) -> str | None:
        with self._lock:
            return hashlib.sha256(bytes(self._streams[stream])).hexdigest()


HOOK_HEALTH_STDERR_LIMIT_BYTES = 4097


class HookHealthSpoolCaptureSinkV1:
    """Exact hook-health sink: unbounded stdout spool plus bounded stderr wire."""

    def __init__(self, stdout_spool: Any) -> None:
        self._stdout_spool = stdout_spool
        self._stderr = bytearray()
        self._digests = {
            "stdout": hashlib.sha256(),
            "stderr": hashlib.sha256(),
        }
        self._closed = False
        self._lock = threading.Lock()
        self._capability: HookHealthCapabilityV1 | None = None

    def _bind_capability(
        self, capability: "HookHealthCapabilityV1", seal: object
    ) -> None:
        if seal is not _HOOK_HEALTH_CAPABILITY_SEAL or self._capability is not None:
            raise ProcessSupervisionError(
                "PSV1-REQUEST-INVALID", "request-validation"
            )
        self._capability = capability

    def write(self, stream: str, data: bytes) -> int:
        capability = self._capability
        if capability is None:
            raise OSError("hook-health capability unavailable")
        capability.verify_sink(self, require_consumed=True)
        with self._lock:
            if self._closed or stream not in self._digests:
                raise OSError("sink unavailable")
            if stream == "stdout":
                written = self._stdout_spool.write(data)
                if written != len(data):
                    raise OSError("short stdout spool write")
            else:
                if len(self._stderr) + len(data) > HOOK_HEALTH_STDERR_LIMIT_BYTES:
                    raise OSError("stderr probe exceeded sink contract")
                self._stderr.extend(data)
                written = len(data)
            self._digests[stream].update(data)
            return written

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._stdout_spool.flush()
                self._closed = True

    def bytes_for(self, stream: str) -> bytes:
        with self._lock:
            if stream != "stderr":
                raise ValueError("hook-health stdout is spool-backed")
            return bytes(self._stderr)

    def reference_digest(self, stream: str) -> str | None:
        with self._lock:
            return self._digests[stream].hexdigest()


_SINK_BINDING_SEAL = object()
_HOOK_HEALTH_CAPABILITY_SEAL = object()


def _hook_spool_identity(spool: Any) -> tuple[object, ...]:
    descriptor = spool.fileno()
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode):
        raise ProcessSupervisionError(
            "PSV1-REQUEST-INVALID", "request-validation"
        )
    return (
        os.path.normcase(os.path.abspath(os.fspath(spool.name))),
        descriptor,
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        getattr(metadata, "st_file_attributes", 0),
    )


class HookHealthCapabilityV1:
    """One-use exact-request authority for the hook-health spool corridor."""

    def __init__(
        self,
        request_sha256: str,
        sink: HookHealthSpoolCaptureSinkV1,
        spool_identity: tuple[object, ...],
        seal: object,
    ) -> None:
        if seal is not _HOOK_HEALTH_CAPABILITY_SEAL:
            raise ProcessSupervisionError(
                "PSV1-REQUEST-INVALID", "request-validation"
            )
        self._request_sha256 = request_sha256
        self._sink = sink
        self._spool_identity = spool_identity
        self._consumed = False
        self._lock = threading.Lock()

    @property
    def consumed(self) -> bool:
        with self._lock:
            return self._consumed

    def consume(
        self,
        request: "ProcessRequestV1",
        executable_identity_sha256: str | None = None,
    ) -> None:
        actual = _hook_health_request_sha256(
            request, executable_identity_sha256
        )
        binding = request.capture_sink_binding
        if (
            type(binding) is not CaptureSinkBindingV1
            or binding._sink is not self._sink
            or _hook_spool_identity(self._sink._stdout_spool)
            != self._spool_identity
        ):
            raise ProcessSupervisionError(
                "PSV1-REQUEST-INVALID", "request-validation"
            )
        with self._lock:
            if self._consumed or not hmac.compare_digest(
                self._request_sha256, actual
            ):
                raise ProcessSupervisionError(
                    "PSV1-REQUEST-INVALID", "request-validation"
                )
            self._consumed = True

    def verify_sink(
        self,
        sink: HookHealthSpoolCaptureSinkV1,
        *,
        require_consumed: bool,
    ) -> None:
        with self._lock:
            valid = (
                sink is self._sink
                and (self._consumed or not require_consumed)
                and _hook_spool_identity(sink._stdout_spool)
                == self._spool_identity
            )
        if not valid:
            raise OSError("hook-health sink capability mismatch")


@dataclass(frozen=True)
class CaptureSinkBindingV1:
    _sink_id: str
    _sink: BoundedMemoryCaptureSinkV1 | HookHealthSpoolCaptureSinkV1
    _seal: object
    _hook_health_capability: HookHealthCapabilityV1 | None = None

    def write(self, stream: str, data: bytes) -> int:
        return self._sink.write(stream, data)

    def close(self) -> None:
        self._sink.close()

    def bytes_for(self, stream: str) -> bytes:
        return self._sink.bytes_for(stream)

    def reference_digest(self, stream: str) -> str | None:
        return self._sink.reference_digest(stream)


MemoryCaptureSinkV1 = BoundedMemoryCaptureSinkV1


@dataclass(frozen=True)
class CwdIdentityV1:
    device: int
    inode: int
    mode: int
    owner: str
    attributes: int


@dataclass(frozen=True)
class ValidatedCwdV1:
    canonical_absolute: str
    identity: CwdIdentityV1
    executable_identity_sha256: str


@dataclass(frozen=True)
class ProcessRequestV1:
    schema_version: int
    argv: tuple[str, ...]
    resolved_executable: Path
    cwd: str
    environment: tuple[EnvironmentRowV1, ...]
    stdin_bytes: bytes | None
    deadline_monotonic: float
    capture_policy: CapturePolicyV1
    capture_sink_binding: CaptureSinkBindingV1
    settle_policy: SettlePolicyV1
    cancellation_probe: CancellationProbeV1 | None = None
    diagnostic_port: DiagnosticPortV1 | None = None
    windows_argv_profile_id: str | None = None
    request_id: str | None = None
    policy_id: str | None = None
    expected_executable_binding: ExecutableBindingV1 | None = None


def _hook_script_binding(path: Path) -> dict[str, object]:
    resolved = path.resolve(strict=True)
    metadata = resolved.stat()
    content = resolved.read_bytes()
    return {
        "path": os.path.normcase(str(resolved)),
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "mode": metadata.st_mode,
        "attributes": getattr(metadata, "st_file_attributes", 0),
        "size": metadata.st_size,
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _hook_health_request_sha256(
    request: ProcessRequestV1,
    executable_identity_sha256: str | None = None,
) -> str:
    if len(request.argv) < 2:
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    payload = {
        "schemaVersion": request.schema_version,
        "argv": list(request.argv),
        "resolvedExecutableIdentity": (
            executable_identity_sha256
            if executable_identity_sha256 is not None
            else resolve_executable_identity(request.resolved_executable)
        ),
        "cwd": os.path.abspath(request.cwd),
        "environment": [
            {"name": row.name, "value": row.value} for row in request.environment
        ],
        "stdin": request.stdin_bytes,
        "deadlineMonotonicHex": request.deadline_monotonic.hex(),
        "capturePolicy": dataclasses.asdict(request.capture_policy),
        "settlePolicy": dataclasses.asdict(request.settle_policy),
        "windowsArgvProfileId": request.windows_argv_profile_id,
        "requestId": request.request_id,
        "policyId": request.policy_id,
        "hookScript": _hook_script_binding(Path(request.argv[1])),
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class StdinObservationV1:
    expected_bytes: int
    written_bytes: int
    complete: bool


@dataclass(frozen=True)
class StreamObservationV1:
    observed_bytes: int
    persisted_bytes: int
    truncated: bool
    prefix_bytes: bytes
    tail_bytes: bytes
    digest: str
    sink_reference: str | None


@dataclass(frozen=True)
class TreeObservationV1:
    backend: str
    ownership_confirmed: bool
    settlement_state: str
    tree_empty: bool
    direct_reaped: bool
    primary_thread_closed: bool
    job_handle_closed: bool


@dataclass(frozen=True)
class ProcessResultV1:
    schema_version: int
    event_id: str
    outcome: str
    terminal_stage: str
    failure_id: str | None
    resolved_executable: str
    executable_identity_sha256: str
    argv_sha256: str
    argv_count: int
    target_exit_code: int | None
    timed_out: bool
    cancelled: bool
    duration_seconds: float
    stdin: StdinObservationV1
    stdout: StreamObservationV1
    stderr: StreamObservationV1
    tree: TreeObservationV1
    resources_closed: bool
    inheritance_poisoned: bool
    cleanup_issues: tuple[str, ...]
    run_token_sha256: str = ""
    private_artifact_retained: bool = False
    cleanup_uncertain: bool = False
    request_sha256: str | None = None
    policy_id: str | None = None


@dataclass(frozen=True)
class FinalizerObservationV1:
    state: str
    resources_closed: bool
    cleanup_issues: tuple[str, ...]


@dataclass(frozen=True)
class RunTokenV1:
    runner_nonce: bytes
    counter: int

    def __post_init__(self) -> None:
        if len(self.runner_nonce) != 16 or not 1 <= self.counter <= MAX_RUN_COUNTER:
            raise ValueError("invalid run token")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(
            self.runner_nonce + self.counter.to_bytes(8, "big")
        ).hexdigest()


@dataclass(frozen=True)
class RunnerCloseResultV1:
    outcome: str
    failure_id: str | None
    settled_run_token_sha256: tuple[str, ...]
    unsettled_run_token_sha256: tuple[str, ...]


@dataclass
class _LifecycleResourceV1:
    name: str
    action: Callable[[float], None]
    state: str = "OWNED"


class RunLifecycleV1:
    """Sole per-run cancellation, worker, resource, and finalization owner."""

    def __init__(self, run_id: RunTokenV1) -> None:
        self.token = run_id
        self._cancel = threading.Event()
        self._settled = threading.Event()
        self._condition = threading.Condition(threading.RLock())
        self._resources: list[_LifecycleResourceV1] = []
        self._workers: set[str] = set()
        self._state = "not-started"
        self._observation = FinalizerObservationV1("not-started", False, ())

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    @property
    def worker_count(self) -> int:
        with self._condition:
            return len(self._workers)

    @property
    def resource_count(self) -> int:
        with self._condition:
            return len(self._resources)

    @property
    def resource_names(self) -> tuple[str, ...]:
        with self._condition:
            return tuple(resource.name for resource in self._resources)

    def has_resource(self, name: str) -> bool:
        with self._condition:
            return any(resource.name == name for resource in self._resources)

    def resource_state(self, name: str) -> str:
        with self._condition:
            resource = next(item for item in self._resources if item.name == name)
            return resource.state

    @property
    def observation(self) -> FinalizerObservationV1:
        with self._condition:
            return self._observation

    def request_cancel(self) -> None:
        self._cancel.set()

    def register_worker(self, name: str) -> None:
        with self._condition:
            if self._state != "not-started" or name in self._workers:
                raise ProcessSupervisionError("PSV1-WORKER-LIMIT", "execution")
            if len(self._workers) >= MAX_IO_WORKERS:
                raise ProcessSupervisionError("PSV1-WORKER-LIMIT", "execution")
            self._workers.add(name)

    def release_worker(self, name: str) -> None:
        with self._condition:
            self._workers.discard(name)

    def register_resource(
        self, name: str, action: Callable[[float], None]
    ) -> None:
        with self._condition:
            if self._state != "not-started" or any(
                resource.name == name for resource in self._resources
            ):
                raise ProcessSupervisionError("PSV1-INTERNAL", "resource-cleanup")
            self._resources.append(_LifecycleResourceV1(name, action))

    def transfer_resource(
        self,
        name: str,
        action: Callable[[float], None],
        *,
        state: str,
    ) -> None:
        if state not in {"HANDLE_OWNED", "FD_OWNED", "OWNED"}:
            raise ProcessSupervisionError("PSV1-INTERNAL", "resource-cleanup")
        with self._condition:
            resource = next(item for item in self._resources if item.name == name)
            if resource.state not in {"OWNED", "HANDLE_OWNED"}:
                raise ProcessSupervisionError("PSV1-DESCRIPTOR-OWNERSHIP", "resource-cleanup")
            resource.action = action
            resource.state = state

    def mark_resource_uncertain(self, name: str) -> None:
        with self._condition:
            resource = next(item for item in self._resources if item.name == name)
            resource.state = "CLOSE_UNCERTAIN"
            issues = (*self._observation.cleanup_issues, "PSV1-DESCRIPTOR-OWNERSHIP")
            self._observation = FinalizerObservationV1(
                self._observation.state, False, tuple(dict.fromkeys(issues))
            )

    def close_resource(self, name: str, deadline: float) -> bool:
        with self._condition:
            resource = next(
                (item for item in reversed(self._resources) if item.name == name),
                None,
            )
            if resource is None or resource.state == "CLOSED":
                return True
            if resource.state == "CLOSE_UNCERTAIN":
                return False
            resource.state = "CLOSING"
        remaining = max(0.0, deadline - time.monotonic())
        try:
            resource.action(remaining)
            with self._condition:
                resource.state = "CLOSED"
            return True
        except BaseException:
            with self._condition:
                resource.state = "CLOSE_UNCERTAIN"
                issues = (*self._observation.cleanup_issues, "PSV1-RESOURCE-CLOSE")
                self._observation = FinalizerObservationV1(
                    self._observation.state,
                    False,
                    tuple(dict.fromkeys(issues)),
                )
            return False

    def finalize_once(self, deadline: float) -> FinalizerObservationV1:
        with self._condition:
            if self._state in {"complete", "incomplete"}:
                return self._observation
            if self._state == "running":
                while self._state == "running" and time.monotonic() < deadline:
                    self._condition.wait(max(0.0, deadline - time.monotonic()))
                return self._observation
            self._state = "running"
        issues = list(self._observation.cleanup_issues)
        for resource in tuple(reversed(self._resources)):
            if resource.state == "CLOSED":
                continue
            if resource.state == "CLOSE_UNCERTAIN":
                issues.append("PSV1-DESCRIPTOR-OWNERSHIP")
                continue
            if time.monotonic() >= deadline:
                issues.append("PSV1-RUNNER-CLOSE-INCOMPLETE")
                continue
            if not self.close_resource(resource.name, deadline):
                issues.append("PSV1-RESOURCE-CLOSE")
        complete = not issues
        with self._condition:
            self._state = "complete" if complete else "incomplete"
            self._observation = FinalizerObservationV1(
                self._state,
                complete,
                tuple(dict.fromkeys(issues)),
            )
            self._condition.notify_all()
            return self._observation

    def mark_settled(self) -> None:
        self._settled.set()

    def wait_settled(self, deadline: float) -> bool:
        return self._settled.wait(max(0.0, deadline - time.monotonic()))


class FinalizerV1:
    """One-shot reverse-order cleanup owner."""

    def __init__(self, actions: Iterable[Callable[[], None]] = ()) -> None:
        self._lifecycle = RunLifecycleV1(RunTokenV1(b"\0" * 16, 1))
        for index, action in enumerate(actions):
            self._lifecycle.register_resource(
                f"compat-{index}", lambda _remaining, action=action: action()
            )

    @property
    def observation(self) -> FinalizerObservationV1:
        return self._lifecycle.observation

    def finalize_once(self) -> FinalizerObservationV1:
        return self._lifecycle.finalize_once(time.monotonic() + 5.0)




class _StreamAccumulatorV1:
    def __init__(self, prefix_limit: int, tail_limit: int) -> None:
        self.observed = 0
        self.persisted = 0
        self.truncated = False
        self.prefix = bytearray()
        self.tail = bytearray()
        self.digest = hashlib.sha256()
        self.prefix_limit = prefix_limit
        self.tail_limit = tail_limit

    def observe(self, data: bytes) -> None:
        self.observed += len(data)

    def persist(self, data: bytes) -> None:
        if not data:
            return
        self.persisted += len(data)
        self.digest.update(data)
        needed = max(0, self.prefix_limit - len(self.prefix))
        if needed:
            self.prefix.extend(data[:needed])
        if self.tail_limit:
            if len(data) >= self.tail_limit:
                self.tail[:] = data[-self.tail_limit :]
            else:
                overflow = max(0, len(self.tail) + len(data) - self.tail_limit)
                if overflow:
                    del self.tail[:overflow]
                self.tail.extend(data)


class BoundedCaptureV1:
    """Thread-safe aggregate bounded capture with per-stream diagnostics."""

    def __init__(self, policy: CapturePolicyV1, sink: CaptureSinkV1 | None = None) -> None:
        validate_capture_policy(policy)
        self.policy = policy
        self.sink = sink
        self._streams = {
            name: _StreamAccumulatorV1(
                policy.prefix_limit_per_stream, policy.tail_limit_per_stream
            )
            for name in ("stdout", "stderr")
        }
        self._persisted = 0
        self._limit_crossed = False
        self._io_failed = False
        self._lock = threading.Lock()

    @property
    def limit_crossed(self) -> bool:
        with self._lock:
            return self._limit_crossed

    @property
    def io_failed(self) -> bool:
        with self._lock:
            return self._io_failed

    def feed(self, stream: str, data: bytes) -> None:
        if stream not in self._streams or not isinstance(data, bytes):
            raise ProcessSupervisionError("PSV1-CAPTURE-IO", "execution")
        with self._lock:
            target = self._streams[stream]
            target.observe(data)
            hook_stdout = (
                type(self.sink) is CaptureSinkBindingV1
                and self.sink._sink_id == "hook-health-spool-v1"
                and self.sink._hook_health_capability is not None
                and self.sink._hook_health_capability.consumed
                and stream == "stdout"
            )
            remaining = self.policy.aggregate_persisted_limit - self._persisted
            per_stream_limit = getattr(
                self.policy, "per_stream_persisted_limit", None
            )
            if per_stream_limit is not None:
                remaining = min(remaining, per_stream_limit - target.persisted)
            accepted = data if hook_stdout else data[: max(0, remaining)]
            if accepted:
                try:
                    if self.sink is not None:
                        written = self.sink.write(stream, accepted)
                        if written != len(accepted):
                            raise OSError("short capture sink write")
                except BaseException:
                    self._io_failed = True
                    return
                target.persist(accepted)
                if not hook_stdout:
                    self._persisted += len(accepted)
            if len(accepted) != len(data):
                target.truncated = True
                self._limit_crossed = True

    def snapshot(self) -> dict[str, StreamObservationV1]:
        with self._lock:
            return {
                name: StreamObservationV1(
                    observed_bytes=item.observed,
                    persisted_bytes=item.persisted,
                    truncated=item.truncated,
                    prefix_bytes=bytes(item.prefix),
                    tail_bytes=bytes(item.tail),
                    digest=item.digest.hexdigest(),
                    sink_reference=(
                        self.sink.reference_digest(name) if self.sink is not None else None
                    ),
                )
                for name, item in self._streams.items()
            }


def write_all_bytes(data: bytes, write: Callable[[memoryview], int]) -> int:
    """Deliver every byte or raise a stable short-write/broken-pipe failure."""

    view = memoryview(data)
    offset = 0
    while offset < len(view):
        try:
            written = write(view[offset:])
        except (BrokenPipeError, ConnectionResetError, OSError) as exc:
            if isinstance(exc, OSError) and exc.errno not in {
                None,
                errno.EPIPE,
                errno.ECONNRESET,
                errno.EBADF,
            }:
                raise
            raise ProcessSupervisionError(
                "PSV1-STDIN-BROKEN-PIPE", "stdin-delivery"
            ) from exc
        if not isinstance(written, int) or written <= 0:
            raise ProcessSupervisionError(
                "PSV1-STDIN-SHORT-WRITE", "stdin-delivery"
            )
        offset += written
    return offset


def serialize_msvcrt_argv(argv: Sequence[str]) -> str:
    return subprocess.list2cmdline(tuple(argv))


def _windows_argv_roundtrip(argv: Sequence[str]) -> tuple[str, ...]:
    if os.name != "nt":
        raise ProcessSupervisionError("PSV1-ARGV-ATTESTATION", "request-validation")
    from ctypes import wintypes

    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    command_line_to_argv = shell32.CommandLineToArgvW
    command_line_to_argv.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    command_line_to_argv.restype = ctypes.POINTER(wintypes.LPWSTR)
    local_free = kernel32.LocalFree
    local_free.argtypes = [ctypes.c_void_p]
    local_free.restype = ctypes.c_void_p
    count = ctypes.c_int()
    parsed = command_line_to_argv(serialize_msvcrt_argv(argv), ctypes.byref(count))
    if not parsed:
        raise ProcessSupervisionError("PSV1-ARGV-ATTESTATION", "request-validation")
    try:
        return tuple(parsed[index] for index in range(count.value))
    finally:
        local_free(parsed)


def _json_argv_sha256(argv: Sequence[str]) -> str:
    return hashlib.sha256(
        json.dumps(list(argv), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _is_reparse(metadata: os.stat_result) -> bool:
    return bool(getattr(metadata, "st_file_attributes", 0) & 0x400)


def _windows_owner_digest(path: Path) -> str:
    from ctypes import wintypes

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_named = advapi32.GetNamedSecurityInfoW
    get_named.argtypes = [
        wintypes.LPWSTR,
        ctypes.c_int,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    get_named.restype = wintypes.DWORD
    open_process_identity = advapi32.OpenProcessToken
    open_process_identity.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    open_process_identity.restype = wintypes.BOOL
    read_process_identity = advapi32.GetTokenInformation
    read_process_identity.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    read_process_identity.restype = wintypes.BOOL
    equal_sid = advapi32.EqualSid
    equal_sid.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    equal_sid.restype = wintypes.BOOL
    sid_length = advapi32.GetLengthSid
    sid_length.argtypes = [ctypes.c_void_p]
    sid_length.restype = wintypes.DWORD
    close = kernel32.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    local_free = kernel32.LocalFree
    local_free.argtypes = [ctypes.c_void_p]
    local_free.restype = ctypes.c_void_p
    owner_sid = ctypes.c_void_p()
    descriptor = ctypes.c_void_p()
    status = get_named(str(path), 1, 1, ctypes.byref(owner_sid), None, None, None, ctypes.byref(descriptor))
    if status != 0 or not owner_sid.value:
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    token = wintypes.HANDLE()
    try:
        if not open_process_identity(
            kernel32.GetCurrentProcess(), 0x0008, ctypes.byref(token)
        ):
            raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
        needed = wintypes.DWORD()
        read_process_identity(token, 1, None, 0, ctypes.byref(needed))
        if not needed.value:
            raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
        buffer = ctypes.create_string_buffer(needed.value)
        if not read_process_identity(token, 1, buffer, needed, ctypes.byref(needed)):
            raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
        token_sid = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0]
        if not equal_sid(owner_sid, token_sid):
            raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
        length = sid_length(owner_sid)
        if not length:
            raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
        return hashlib.sha256(ctypes.string_at(owner_sid, length)).hexdigest()
    finally:
        if token:
            close(token)
        if descriptor:
            local_free(descriptor)


def bind_cwd_identity(path: str) -> CwdIdentityV1:
    try:
        if not isinstance(path, str):
            raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
        path_text = path
        if "\0" in path_text or len(path_text.encode("utf-8")) > MAX_PATH_BYTES:
            raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
        absolute = Path(os.path.abspath(path))
        if not absolute.is_absolute():
            raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
        chain = tuple(reversed((absolute, *absolute.parents)))
        for component in chain:
            metadata = component.lstat()
            if stat.S_ISLNK(metadata.st_mode) or _is_reparse(metadata):
                raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
        metadata = absolute.stat()
        if not stat.S_ISDIR(metadata.st_mode):
            raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
        if os.name == "nt":
            owner = _windows_owner_digest(absolute)
        else:
            if metadata.st_uid != os.geteuid() or metadata.st_mode & 0o022:
                raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
            owner = str(metadata.st_uid)
        return CwdIdentityV1(
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_mode,
            owner,
            getattr(metadata, "st_file_attributes", 0),
        )
    except ProcessSupervisionError:
        raise
    except (OSError, ValueError, UnicodeError) as exc:
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation") from exc


def _stream_executable_binding(path: Path) -> tuple[str, str]:
    try:
        absolute = Path(path)
        if not absolute.is_absolute():
            raise OSError("not absolute")
        metadata = absolute.stat()
        leaf = absolute.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_ISLNK(leaf.st_mode)
            or _is_reparse(leaf)
        ):
            raise OSError("not ordinary executable")
        digest = hashlib.sha256()
        with absolute.open("rb") as stream:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        digest.update(struct.pack(">QQ", metadata.st_size, metadata.st_mtime_ns & ((1 << 64) - 1)))
        identity = digest.hexdigest()
        if absolute.resolve() == Path(sys.executable).resolve():
            version_source = (
                f"python:{sys.version_info.major}.{sys.version_info.minor}."
                f"{sys.version_info.micro}:{identity}"
            )
        else:
            version_source = f"native:{identity}"
        version = hashlib.sha256(version_source.encode("ascii")).hexdigest()
        return identity, version
    except (OSError, ValueError, OverflowError, UnicodeError) as exc:
        raise ProcessSupervisionError(
            "PSV1-EXECUTABLE-UNRESOLVED", "request-validation"
        ) from exc


def resolve_executable_identity(path: Path) -> str:
    return _stream_executable_binding(path)[0]


def resolve_executable_version(path: Path) -> str:
    return _stream_executable_binding(path)[1]


def _kimi_bundle_file_binding(
    request: ProcessRequestV1, *, failure_id: str
) -> tuple[str, str, str]:
    def reject() -> ProcessSupervisionError:
        return ProcessSupervisionError(failure_id, "request-validation")

    try:
        argv = request.argv
        if not KimiWindowsProfileV1.matches_argv(argv):
            raise reject()
        raw_path = argv[2]
        if not raw_path or "\x00" in raw_path:
            raise reject()
        prompt = Path(raw_path)
        normalized = Path(os.path.abspath(prompt))
        if (
            not prompt.is_absolute()
            or os.path.normcase(str(normalized)) != os.path.normcase(raw_path)
        ):
            raise reject()
        root = Path(os.path.abspath(request.cwd))
        bind_cwd_identity(str(root))
        try:
            relative = normalized.relative_to(root)
        except ValueError as exc:
            raise reject() from exc
        if not relative.parts:
            raise reject()
        for component in reversed((normalized, *normalized.parents)):
            metadata = component.lstat()
            if stat.S_ISLNK(metadata.st_mode) or _is_reparse(metadata):
                raise reject()
            if component == root:
                break
        else:
            raise reject()
        before = normalized.lstat()
        if not stat.S_ISREG(before.st_mode):
            raise reject()
        descriptor = os.open(
            normalized,
            os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino, opened.st_mode) != (
                before.st_dev,
                before.st_ino,
                before.st_mode,
            ):
                raise reject()
            digest = hashlib.sha256()
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        finally:
            os.close(descriptor)
        content = normalized.read_bytes()
        if not content.startswith(KimiWindowsProfileV1.agent_frontmatter) or b"${" in content:
            raise reject()
        skills = Path(argv[4])
        if not skills.is_absolute() or Path(os.path.abspath(skills)) != skills or not skills.is_dir() or any(skills.iterdir()):
            raise reject()
        try:
            skills.relative_to(root)
        except ValueError as exc:
            raise reject() from exc
        identity = hashlib.sha256(
            struct.pack(
                ">QQQQQ",
                opened.st_dev & ((1 << 64) - 1),
                opened.st_ino & ((1 << 64) - 1),
                opened.st_mode & ((1 << 64) - 1),
                opened.st_size & ((1 << 64) - 1),
                opened.st_mtime_ns & ((1 << 64) - 1),
            )
        ).hexdigest()
        return str(normalized), identity, digest.hexdigest()
    except ProcessSupervisionError:
        raise
    except (OSError, ValueError, OverflowError, UnicodeError) as exc:
        raise reject() from exc


def _argv_shape_sha256(argv: Sequence[str]) -> str:
    shapes: list[tuple[str, ...]] = []
    for index, item in enumerate(argv):
        classes: list[str] = ["argv0" if index == 0 else "argument"]
        if not item:
            classes.append("empty")
        if any(character.isspace() for character in item):
            classes.append("whitespace")
        if '"' in item:
            classes.append("quote")
        if '\\"' in item:
            classes.append("backslash-before-quote")
        if item.endswith("\\"):
            classes.append("trailing-backslash")
        if any(ord(character) > 127 for character in item):
            classes.append("non-ascii")
        if "/" in item or "\\" in item or (len(item) >= 2 and item[1] == ":"):
            classes.append("path-like")
        shapes.append(tuple(classes))
    encoded = json.dumps(shapes, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _probe_environment_rows(
    rows: Sequence[EnvironmentRowV1],
) -> tuple[EnvironmentRowV1, ...]:
    allowed = {
        "LANG", "LC_ALL", "PATH", "PATHEXT", "PYTHONIOENCODING",
        "SYSTEMROOT", "TEMP", "TMP", "TMPDIR", "WINDIR",
    }
    return tuple(
        sorted(
            (row for row in rows if row.name.upper() in allowed),
            key=lambda row: row.name.casefold(),
        )
    )


def _internal_probe_request_sha256(
    request: ProcessRequestV1,
    profile_id: str,
    purpose: str,
    executable_identity_sha256: str | None = None,
) -> str:
    payload = {
        "schemaVersion": request.schema_version,
        "profileId": profile_id,
        "purpose": purpose,
        "argv": list(request.argv),
        "resolvedExecutableIdentity": (
            executable_identity_sha256
            if executable_identity_sha256 is not None
            else resolve_executable_identity(request.resolved_executable)
        ),
        "cwd": request.cwd,
        "environment": [
            {"name": row.name, "value": row.value} for row in request.environment
        ],
        "stdin": None if request.stdin_bytes is None else "present",
        "deadlineMonotonicHex": request.deadline_monotonic.hex(),
        "capturePolicy": dataclasses.asdict(request.capture_policy),
        "settlePolicy": dataclasses.asdict(request.settle_policy),
        "windowsArgvProfileId": request.windows_argv_profile_id,
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class WindowsArgvAdmissionOwnerV1:
    """Runner-owned issuer and consumer of same-run Windows argv evidence."""

    def __init__(
        self,
        seal: object,
        run_internal_probe: Callable[
            [RunLifecycleV1, ProcessRequestV1, WindowsInternalProbeAdmissionV1],
            ProcessResultV1,
        ],
    ) -> None:
        if seal is not _WINDOWS_ARGV_ADMISSION_SEAL:
            raise ProcessSupervisionError(
                "PSV1-ARGV-ATTESTATION", "request-validation"
            )
        self._seal = seal
        self._run_internal_probe = run_internal_probe
        self._consumed_run_tokens: set[str] = set()
        self._consumed_internal: set[tuple[str, str]] = set()
        self._lock = threading.Lock()

    def _probe_request(
        self,
        lifecycle: RunLifecycleV1,
        request: ProcessRequestV1,
        executable: Path,
        profile_id: str,
        purpose: str,
        argv: tuple[str, ...],
        executable_identity_sha256: str,
    ) -> tuple[ProcessRequestV1, WindowsInternalProbeAdmissionV1]:
        if lifecycle.cancelled or request.deadline_monotonic <= time.monotonic():
            raise ProcessSupervisionError("PSV1-DEADLINE", "deadline")
        sink = CaptureSinkBindingV1(
            "bounded-memory-v1", BoundedMemoryCaptureSinkV1(), _SINK_BINDING_SEAL
        )
        remaining = max(0.001, request.deadline_monotonic - time.monotonic())
        probe_request = ProcessRequestV1(
            schema_version=1,
            argv=argv,
            resolved_executable=executable,
            cwd=request.cwd,
            environment=_probe_environment_rows(request.environment),
            stdin_bytes=None,
            deadline_monotonic=request.deadline_monotonic,
            capture_policy=CapturePolicyV1(
                "windows-internal-argv-probe-v1",
                _WINDOWS_INTERNAL_PROBE_CAPTURE_BYTES,
                _WINDOWS_INTERNAL_PROBE_CAPTURE_BYTES,
                0,
                16 * 1024,
            ),
            capture_sink_binding=sink,
            settle_policy=SettlePolicyV1(min(5.0, remaining)),
            windows_argv_profile_id=None,
        )
        admission = WindowsInternalProbeAdmissionV1(
            1,
            lifecycle.token.sha256,
            profile_id,
            purpose,
            _internal_probe_request_sha256(
                probe_request,
                profile_id,
                purpose,
                executable_identity_sha256,
            ),
            executable_identity_sha256,
            request.deadline_monotonic,
            _WINDOWS_INTERNAL_PROBE_ADMISSION_SEAL,
        )
        return probe_request, admission

    def _execute_probe(
        self,
        lifecycle: RunLifecycleV1,
        probe_request: ProcessRequestV1,
        admission: WindowsInternalProbeAdmissionV1,
    ) -> bytes:
        result = self._run_internal_probe(lifecycle, probe_request, admission)
        if (
            result.failure_id is not None
            or result.outcome != "success"
            or result.target_exit_code != 0
            or not result.tree.tree_empty
            or not result.resources_closed
            or result.cleanup_uncertain
            or result.stdout.truncated
            or result.stderr.truncated
        ):
            raise _WindowsArgvProbeFailure(result)
        if time.monotonic() >= probe_request.deadline_monotonic:
            raise ProcessSupervisionError("PSV1-DEADLINE", "deadline")
        return probe_request.capture_sink_binding.bytes_for("stdout")

    def _python_probe(
        self,
        lifecycle: RunLifecycleV1,
        request: ProcessRequestV1,
        executable: Path,
        executable_launch_owner: "_ExecutableLaunchOwnerV1",
    ) -> tuple[str, str, str]:
        if os.path.normcase(os.path.abspath(executable)) != os.path.normcase(
            os.path.abspath(sys.executable)
        ):
            raise ProcessSupervisionError(
                "PSV1-ARGV-ATTESTATION", "request-validation"
            )
        probe = (
            str(executable),
            "-I",
            "-c",
            _PYTHON_ARGV_ECHO_HELPER,
            *_WINDOWS_ARGV_PROBE_CANARIES,
        )
        if len(serialize_msvcrt_argv(probe).encode("utf-16-le")) // 2 > MAX_WINDOWS_COMMAND_LINE_UNITS:
            raise ProcessSupervisionError(
                "PSV1-ARGV-ATTESTATION", "request-validation"
            )
        probe_request, admission = self._probe_request(
            request=request,
            lifecycle=lifecycle,
            executable=executable,
            profile_id="python-validator-json-echo-v1",
            purpose="python-json-argv-echo-v1",
            argv=probe,
            executable_identity_sha256=executable_launch_owner.identity_sha256,
        )
        try:
            stdout = self._execute_probe(lifecycle, probe_request, admission)
        except BaseException:
            lifecycle.close_resource(
                executable_launch_owner.resource_name,
                time.monotonic() + RUNNER_CLOSE_TIMEOUT_SECONDS,
            )
            raise
        try:
            observed_tail = json.loads(stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProcessSupervisionError(
                "PSV1-ARGV-ATTESTATION", "request-validation"
            ) from exc
        if (
            not isinstance(observed_tail, list)
            or not all(isinstance(item, str) for item in observed_tail)
        ):
            raise ProcessSupervisionError(
                "PSV1-ARGV-ATTESTATION", "request-validation"
            )
        requested_argv = (request.argv[0], *_WINDOWS_ARGV_PROBE_CANARIES)
        observed = (request.argv[0], *observed_tail)
        return (
            "python-json-argv-echo-v1",
            _json_argv_sha256(requested_argv),
            _json_argv_sha256(observed),
        )

    def _git_probe(
        self,
        lifecycle: RunLifecycleV1,
        request: ProcessRequestV1,
        executable: Path,
        executable_launch_owner: "_ExecutableLaunchOwnerV1",
    ) -> tuple[str, str, str]:
        if executable.name.casefold() not in {"git", "git.exe"}:
            raise ProcessSupervisionError(
                "PSV1-ARGV-ATTESTATION", "request-validation"
            )
        probe = (
            str(executable),
            "rev-parse",
            "--sq-quote",
            "--",
            *_WINDOWS_ARGV_PROBE_CANARIES,
        )
        if len(serialize_msvcrt_argv(probe).encode("utf-16-le")) // 2 > MAX_WINDOWS_COMMAND_LINE_UNITS:
            raise ProcessSupervisionError(
                "PSV1-ARGV-ATTESTATION", "request-validation"
            )
        probe_request, admission = self._probe_request(
            request=request,
            lifecycle=lifecycle,
            executable=executable,
            profile_id="git-rev-parse-sq-quote-v1",
            purpose="git-rev-parse-sq-quote-v1",
            argv=probe,
            executable_identity_sha256=executable_launch_owner.identity_sha256,
        )
        try:
            stdout = self._execute_probe(lifecycle, probe_request, admission)
        except BaseException:
            lifecycle.close_resource(
                executable_launch_owner.resource_name,
                time.monotonic() + RUNNER_CLOSE_TIMEOUT_SECONDS,
            )
            raise
        try:
            parsed = tuple(shlex.split(stdout.decode("utf-8"), posix=True))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ProcessSupervisionError(
                "PSV1-ARGV-ATTESTATION", "request-validation"
            ) from exc
        if not parsed or parsed[0] != "--":
            raise ProcessSupervisionError(
                "PSV1-ARGV-ATTESTATION", "request-validation"
            )
        requested_argv = (request.argv[0], *_WINDOWS_ARGV_PROBE_CANARIES)
        observed = (request.argv[0], *parsed[1:])
        return (
            "git-rev-parse-sq-quote-v1",
            _json_argv_sha256(requested_argv),
            _json_argv_sha256(observed),
        )

    def admit(
        self,
        lifecycle: RunLifecycleV1,
        request: ProcessRequestV1,
        executable_launch_owner: "_ExecutableLaunchOwnerV1",
    ) -> WindowsArgvAdmissionV1:
        profile_id = request.windows_argv_profile_id
        if profile_id not in _WINDOWS_ARGV_PROFILES:
            raise ProcessSupervisionError(
                "PSV1-ARGV-CODEC-UNSUPPORTED", "request-validation"
            )
        executable = Path(request.resolved_executable)
        launch_owner = executable_launch_owner
        prompt_binding: tuple[str, str, str] | None = None
        executable_binding: ExecutableBindingV1 | None = None
        if _is_kimi_executable_profile(profile_id):
            if profile_id == KimiWindowsProfileV1.profile_id:
                prompt_binding = _kimi_bundle_file_binding(
                    request, failure_id="PSV1-ARGV-CODEC-UNSUPPORTED"
                )
            if executable.name.casefold() != "kimi.exe":
                raise ProcessSupervisionError(
                    "PSV1-EXECUTABLE-UNRESOLVED", "request-validation"
                )
            executable_binding = launch_owner.binding
            if not _expected_executable_binding_matches(
                request.expected_executable_binding, executable_binding
            ):
                raise ProcessSupervisionError(
                    "PSV1-EXECUTABLE-UNRESOLVED", "request-validation"
                )
            identity = executable_binding.sha256
            version = hashlib.sha256(
                f"kimi-release:{executable_binding.size}:{identity}".encode("ascii")
            ).hexdigest()
        else:
            identity = launch_owner.identity_sha256
            version = launch_owner.version_sha256
        if profile_id == "python-hook-health-v1":
            if (
                executable.resolve() != Path(sys.executable).resolve()
                or len(request.argv) < 2
                or not Path(request.argv[1]).is_absolute()
                or Path(request.argv[1]).name != "check-hook-health.py"
                or not Path(request.argv[1]).is_file()
            ):
                raise ProcessSupervisionError(
                    "PSV1-ARGV-CODEC-UNSUPPORTED", "request-validation"
                )
            probe_kind, requested, observed = self._python_probe(
                lifecycle, request, executable, launch_owner
            )
        elif profile_id == "python-validator-json-echo-v1":
            probe_kind, requested, observed = self._python_probe(
                lifecycle, request, executable, launch_owner
            )
        elif profile_id == "git-rev-parse-sq-quote-v1":
            probe_kind, requested, observed = self._git_probe(
                lifecycle, request, executable, launch_owner
            )
        elif profile_id == "repository-transfer-git-v1":
            probe_kind, requested, observed = self._git_probe(
                lifecycle, request, executable, launch_owner
            )
        elif profile_id == KimiWindowsProfileV1.profile_id:
            if _windows_argv_roundtrip(request.argv) != request.argv:
                raise ProcessSupervisionError(
                    "PSV1-ARGV-ATTESTATION", "request-validation"
                )
            probe_kind = "kimi-sealed-bundle-v1"
            requested = observed = _json_argv_sha256(request.argv)
        elif profile_id == KimiWindowsProfileV1.probe_profile_id:
            if (
                request.argv not in {
                    (str(executable), "--version"),
                    (str(executable), "--help"),
                }
                or _windows_argv_roundtrip(request.argv) != request.argv
            ):
                raise ProcessSupervisionError(
                    "PSV1-ARGV-ATTESTATION", "request-validation"
                )
            probe_kind = "kimi-metadata-probe-v2"
            requested = observed = _json_argv_sha256(request.argv)
        else:
            raise ProcessSupervisionError(
                "PSV1-ARGV-CODEC-UNSUPPORTED", "request-validation"
            )
        if not hmac.compare_digest(requested, observed):
            raise ProcessSupervisionError(
                "PSV1-ARGV-ATTESTATION", "request-validation"
            )
        expires = request.deadline_monotonic
        return WindowsArgvAdmissionV1(
            1,
            lifecycle.token.sha256,
            profile_id,
            "msvcrt-v1",
            identity,
            version,
            _json_argv_sha256(request.argv),
            _argv_shape_sha256(request.argv),
            probe_kind,
            requested,
            observed,
            expires,
            "pass",
            _WINDOWS_ARGV_ADMISSION_SEAL,
            _WINDOWS_ARGV_CHILD_EVIDENCE_SEAL,
            *(prompt_binding or (None, None, None)),
            executable_binding,
        )

    def consume(
        self,
        lifecycle: RunLifecycleV1,
        request: ProcessRequestV1,
        admission: WindowsArgvAdmissionV1,
        launch_owner: "_ExecutableLaunchOwnerV1",
    ) -> None:
        executable = Path(request.resolved_executable)
        if (
            launch_owner._closed
            or os.path.normcase(str(launch_owner.path))
            != os.path.normcase(os.path.abspath(executable))
        ):
            raise ProcessSupervisionError(
                "PSV1-ARGV-ATTESTATION", "request-validation"
            )
        executable_binding = (
            launch_owner.binding if _is_kimi_executable_profile(admission.profile_id) else None
        )
        if executable_binding is not None:
            identity = executable_binding.sha256
            version = hashlib.sha256(
                f"kimi-release:{executable_binding.size}:{identity}".encode("ascii")
            ).hexdigest()
        else:
            identity = launch_owner.identity_sha256
            version = launch_owner.version_sha256
        prompt_binding = (
            _kimi_bundle_file_binding(request, failure_id="PSV1-ARGV-ATTESTATION")
            if admission.profile_id == KimiWindowsProfileV1.profile_id
            else (None, None, None)
        )
        valid = (
            type(admission) is WindowsArgvAdmissionV1
            and admission._seal is _WINDOWS_ARGV_ADMISSION_SEAL
            and admission._child_evidence_seal is _WINDOWS_ARGV_CHILD_EVIDENCE_SEAL
            and admission.schema_version == 1
            and admission.run_token_sha256 == lifecycle.token.sha256
            and admission.profile_id == request.windows_argv_profile_id
            and admission.codec == "msvcrt-v1"
            and admission.resolved_executable_identity == identity
            and admission.resolved_executable_version == version
            and admission.executable_binding == executable_binding
            and (
                _expected_executable_binding_matches(
                    request.expected_executable_binding, executable_binding
                )
                if executable_binding is not None
                else request.expected_executable_binding is None
            )
            and admission.actual_argv_sha256 == _json_argv_sha256(request.argv)
            and admission.actual_argv_shape_sha256 == _argv_shape_sha256(request.argv)
            and admission.probe_requested_argv_sha256
            == admission.probe_observed_argv_sha256
            and admission.status == "pass"
            and (
                admission.prompt_file_canonical,
                admission.prompt_file_identity,
                admission.prompt_file_sha256,
            )
            == prompt_binding
        )
        if not valid:
            raise ProcessSupervisionError(
                "PSV1-ARGV-ATTESTATION", "request-validation"
            )
        if admission.expires_at_monotonic < time.monotonic():
            raise ProcessSupervisionError("PSV1-DEADLINE", "deadline")
        with self._lock:
            if admission.run_token_sha256 in self._consumed_run_tokens:
                raise ProcessSupervisionError(
                    "PSV1-ARGV-ATTESTATION", "request-validation"
                )
            self._consumed_run_tokens.add(admission.run_token_sha256)

    def _consume_internal(
        self,
        lifecycle: RunLifecycleV1,
        request: ProcessRequestV1,
        admission: WindowsInternalProbeAdmissionV1,
        executable_launch_owner: "_ExecutableLaunchOwnerV1",
    ) -> None:
        valid_profiles = {
            "python-validator-json-echo-v1": "python-json-argv-echo-v1",
            "git-rev-parse-sq-quote-v1": "git-rev-parse-sq-quote-v1",
        }
        valid = (
            type(admission) is WindowsInternalProbeAdmissionV1
            and admission._seal is _WINDOWS_INTERNAL_PROBE_ADMISSION_SEAL
            and admission.schema_version == 1
            and admission.run_token_sha256 == lifecycle.token.sha256
            and valid_profiles.get(admission.profile_id) == admission.purpose
            and admission.request_sha256
            == _internal_probe_request_sha256(
                request,
                admission.profile_id,
                admission.purpose,
                executable_launch_owner.identity_sha256,
            )
            and admission.resolved_executable_identity
            == executable_launch_owner.identity_sha256
            and not executable_launch_owner._closed
            and admission.expires_at_monotonic == request.deadline_monotonic
            and admission.expires_at_monotonic > time.monotonic()
            and request.stdin_bytes is None
            and request.windows_argv_profile_id is None
        )
        if not valid:
            raise ProcessSupervisionError(
                "PSV1-ARGV-CODEC-UNSUPPORTED", "request-validation"
            )
        key = (admission.run_token_sha256, admission.purpose)
        with self._lock:
            if key in self._consumed_internal:
                raise ProcessSupervisionError(
                    "PSV1-ARGV-CODEC-UNSUPPORTED", "request-validation"
                )
            self._consumed_internal.add(key)


class WindowsCreateOwnerV1:
    """The sole Windows process-create seam; admission is consumed first."""

    def __init__(
        self,
        admission_owner: WindowsArgvAdmissionOwnerV1,
        request: ProcessRequestV1,
        create_process: Callable[[], object],
        executable_launch_owner: "_ExecutableLaunchOwnerV1",
    ) -> None:
        self._admission_owner = admission_owner
        self._request = request
        self._create_process = create_process
        self._executable_launch_owner = executable_launch_owner

    def create_internal_probe(
        self,
        lifecycle: RunLifecycleV1,
        admission: WindowsInternalProbeAdmissionV1,
        executable_launch_owner: "_ExecutableLaunchOwnerV1",
    ) -> object:
        self._admission_owner._consume_internal(
            lifecycle, self._request, admission, executable_launch_owner
        )
        return self._create_process()

    def create_task(
        self,
        lifecycle: RunLifecycleV1,
        request: ProcessRequestV1,
        admission: WindowsArgvAdmissionV1,
    ) -> object:
        self._admission_owner.consume(
            lifecycle,
            request,
            admission,
            self._executable_launch_owner,
        )
        return self._create_process()


def validate_capture_policy(policy: CapturePolicyV1) -> None:
    token = policy.policy_id
    transfer_limit = getattr(policy, "per_stream_persisted_limit", None)
    if (
        not isinstance(token, str)
        or not token
        or len(token.encode("ascii", "ignore")) != len(token)
        or len(token) > MAX_REGISTRY_TOKEN_BYTES
        or not 0 <= policy.aggregate_persisted_limit <= MAX_CAPTURE_BYTES
        or not 0 <= policy.prefix_limit_per_stream <= policy.aggregate_persisted_limit
        or not 0 <= policy.tail_limit_per_stream <= policy.aggregate_persisted_limit
        or not 1 <= policy.chunk_size <= 64 * 1024
        or (
            isinstance(policy, RepositoryTransferCapturePolicyV1)
            and (
                not isinstance(transfer_limit, int)
                or not 0 < transfer_limit <= policy.aggregate_persisted_limit
                or policy.prefix_limit_per_stream != transfer_limit
                or policy.tail_limit_per_stream != 0
            )
        )
    ):
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")


def hook_health_capture_policy() -> CapturePolicyV1:
    return CapturePolicyV1(
        "hook-health-spool-v1",
        HOOK_HEALTH_STDERR_LIMIT_BYTES,
        0,
        0,
        64 * 1024,
    )


def _validate_environment(rows: Sequence[EnvironmentRowV1]) -> None:
    if len(rows) > MAX_ENVIRONMENT_COUNT:
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    seen: set[str] = set()
    total = 0
    for row in rows:
        if not isinstance(row, EnvironmentRowV1) or not _ENV_NAME.fullmatch(row.name):
            raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
        name_bytes = row.name.encode("utf-8")
        value_bytes = row.value.encode("utf-8")
        if (
            "\0" in row.value
            or len(name_bytes) > MAX_ENVIRONMENT_NAME_BYTES
            or len(value_bytes) > MAX_ENVIRONMENT_VALUE_BYTES
        ):
            raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
        key = row.name.casefold() if os.name == "nt" else row.name
        if key in seen:
            raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
        seen.add(key)
        total += len(name_bytes) + 1 + len(value_bytes) + 1
    if total > MAX_ENVIRONMENT_BYTES:
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")


def _validate_request_shape_before_executable_acquisition(
    request: ProcessRequestV1,
) -> None:
    if not isinstance(request, ProcessRequestV1) or request.schema_version != 1:
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    if not 1 <= len(request.argv) <= MAX_ARGV_COUNT:
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    aggregate = 0
    for item in request.argv:
        if not isinstance(item, str) or "\0" in item:
            raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
        encoded = item.encode("utf-8")
        if len(encoded) > MAX_ARG_BYTES:
            raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
        aggregate += len(encoded) + 1
    if aggregate > MAX_ARGV_BYTES:
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")


def validate_process_request(
    request: ProcessRequestV1,
    executable_launch_owner: "_ExecutableLaunchOwnerV1 | None" = None,
    *,
    argv_executable_prevalidated: bool = False,
) -> ValidatedCwdV1:
    _validate_request_shape_before_executable_acquisition(request)
    executable = Path(request.resolved_executable)
    if not executable.is_absolute():
        raise ProcessSupervisionError("PSV1-EXECUTABLE-UNRESOLVED", "request-validation")
    try:
        argv_executable = Path(request.argv[0])
        if (
            not argv_executable.is_absolute()
            or (
                not argv_executable_prevalidated
                and argv_executable.resolve() != executable.resolve()
            )
            or (
                executable_launch_owner is not None
                and os.path.normcase(str(executable_launch_owner.path))
                != os.path.normcase(os.path.abspath(executable))
            )
        ):
            raise ProcessSupervisionError("PSV1-EXECUTABLE-UNRESOLVED", "request-validation")
    except (OSError, ValueError) as exc:
        raise ProcessSupervisionError("PSV1-EXECUTABLE-UNRESOLVED", "request-validation") from exc
    expected_binding = request.expected_executable_binding
    if expected_binding is not None and (
        not _is_kimi_executable_profile(request.windows_argv_profile_id)
        or executable_launch_owner is None
        or not _expected_executable_binding_matches(
            expected_binding, executable_launch_owner.binding
        )
    ):
        raise ProcessSupervisionError(
            "PSV1-EXECUTABLE-UNRESOLVED", "request-validation"
        )
    executable_identity = (
        executable_launch_owner.identity_sha256
        if executable_launch_owner is not None
        else resolve_executable_identity(executable)
    )
    suffix = executable.suffix.casefold()
    basename = executable.name.casefold()
    if os.name == "nt":
        if suffix in {".bat", ".cmd", ".ps1", ".sh"} or basename in _WINDOWS_SHELL_HOSTS:
            raise ProcessSupervisionError("PSV1-ARGV-CODEC-UNSUPPORTED", "request-validation")
        if request.windows_argv_profile_id not in _WINDOWS_ARGV_PROFILES:
            raise ProcessSupervisionError("PSV1-ARGV-CODEC-UNSUPPORTED", "request-validation")
        command = serialize_msvcrt_argv(request.argv)
        if len(command.encode("utf-16-le")) // 2 > MAX_WINDOWS_COMMAND_LINE_UNITS:
            raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    elif basename in _POSIX_SHELL_HOSTS:
        raise ProcessSupervisionError("PSV1-ARGV-CODEC-UNSUPPORTED", "request-validation")
    _validate_environment(request.environment)
    if request.stdin_bytes is not None and (
        not isinstance(request.stdin_bytes, bytes) or len(request.stdin_bytes) > MAX_STDIN_BYTES
    ):
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    if not isinstance(request.deadline_monotonic, (int, float)) or not math.isfinite(request.deadline_monotonic):
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    if request.deadline_monotonic <= time.monotonic():
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    validate_capture_policy(request.capture_policy)
    binding = request.capture_sink_binding
    memory_binding = (
        type(binding) is CaptureSinkBindingV1
        and getattr(binding, "_seal", None) is _SINK_BINDING_SEAL
        and getattr(binding, "_sink_id", None) == "bounded-memory-v1"
        and type(getattr(binding, "_sink", None)) is BoundedMemoryCaptureSinkV1
    )
    hook_binding = (
        type(binding) is CaptureSinkBindingV1
        and getattr(binding, "_seal", None) is _SINK_BINDING_SEAL
        and getattr(binding, "_sink_id", None) == "hook-health-spool-v1"
        and type(getattr(binding, "_sink", None)) is HookHealthSpoolCaptureSinkV1
        and request.capture_policy == hook_health_capture_policy()
        and type(getattr(binding, "_hook_health_capability", None))
        is HookHealthCapabilityV1
    )
    if hook_binding:
        binding._hook_health_capability.consume(
            request,
            (
                executable_launch_owner.identity_sha256
                if executable_launch_owner is not None
                else None
            ),
        )
    if not memory_binding and not hook_binding:
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    if (
        not isinstance(request.settle_policy, SettlePolicyV1)
        or not 0 < request.settle_policy.timeout_seconds <= 5.0
    ):
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    if not isinstance(request.cwd, str):
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    canonical = os.path.abspath(request.cwd)
    cwd_identity = bind_cwd_identity(canonical)
    return ValidatedCwdV1(canonical, cwd_identity, executable_identity)


def _empty_stream() -> StreamObservationV1:
    return StreamObservationV1(0, 0, False, b"", b"", hashlib.sha256().hexdigest(), None)


def _request_failure(
    request: ProcessRequestV1,
    error: ProcessSupervisionError,
    started: float,
    *,
    executable_identity_sha256: str | None = None,
) -> ProcessResultV1:
    argv = request.argv if isinstance(request, ProcessRequestV1) else ()
    executable = os.fspath(request.resolved_executable) if isinstance(request, ProcessRequestV1) else ""
    executable_identity = executable_identity_sha256
    if executable_identity is None:
        executable_identity = hashlib.sha256(b"").hexdigest()
    tree = (
        TreeObservationV1("none", False, "AMBIGUOUS", False, True, True, True)
        if error.failure_id == "PSV1-POSIX-ORACLE-UNAVAILABLE"
        else TreeObservationV1("none", False, "EMPTY", True, True, True, True)
    )
    return ProcessResultV1(
        1,
        SETTLED_EVENT_ID,
        "supervisor-failure",
        error.terminal_stage,
        error.failure_id,
        executable,
        executable_identity,
        _json_argv_sha256(argv),
        len(argv),
        None,
        error.failure_id == "PSV1-DEADLINE"
        and error.terminal_stage == "deadline",
        False,
        max(0.0, time.monotonic() - started),
        StdinObservationV1(len(request.stdin_bytes or b""), 0, not request.stdin_bytes),
        _empty_stream(),
        _empty_stream(),
        tree,
        True,
        False,
        (),
        policy_id=getattr(request.capture_policy, "policy_id", None),
    )


class WindowsInheritanceCoordinatorV1:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self._poisoned = False

    @property
    def poisoned(self) -> bool:
        return self._poisoned

    def poison(self) -> None:
        self._poisoned = True


if os.name == "nt":
    from ctypes import wintypes

    ULONG_PTR = wintypes.WPARAM
    SIZE_T = ctypes.c_size_t

    class SECURITY_ATTRIBUTES(ctypes.Structure):
        _fields_ = [
            ("nLength", wintypes.DWORD),
            ("lpSecurityDescriptor", ctypes.c_void_p),
            ("bInheritHandle", wintypes.BOOL),
        ]

    class STARTUPINFOW(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("lpReserved", wintypes.LPWSTR),
            ("lpDesktop", wintypes.LPWSTR),
            ("lpTitle", wintypes.LPWSTR),
            ("dwX", wintypes.DWORD),
            ("dwY", wintypes.DWORD),
            ("dwXSize", wintypes.DWORD),
            ("dwYSize", wintypes.DWORD),
            ("dwXCountChars", wintypes.DWORD),
            ("dwYCountChars", wintypes.DWORD),
            ("dwFillAttribute", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("wShowWindow", wintypes.WORD),
            ("cbReserved2", wintypes.WORD),
            ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)),
            ("hStdInput", wintypes.HANDLE),
            ("hStdOutput", wintypes.HANDLE),
            ("hStdError", wintypes.HANDLE),
        ]

    class STARTUPINFOEXW(ctypes.Structure):
        _fields_ = [("StartupInfo", STARTUPINFOW), ("lpAttributeList", ctypes.c_void_p)]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("hProcess", wintypes.HANDLE),
            ("hThread", wintypes.HANDLE),
            ("dwProcessId", wintypes.DWORD),
            ("dwThreadId", wintypes.DWORD),
        ]

    class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", SIZE_T),
            ("MaximumWorkingSetSize", SIZE_T),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ULONG_PTR),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
        )]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", SIZE_T),
            ("JobMemoryLimit", SIZE_T),
            ("PeakProcessMemoryUsed", SIZE_T),
            ("PeakJobMemoryUsed", SIZE_T),
        ]

    class JOBOBJECT_BASIC_ACCOUNTING_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("TotalUserTime", ctypes.c_longlong),
            ("TotalKernelTime", ctypes.c_longlong),
            ("ThisPeriodTotalUserTime", ctypes.c_longlong),
            ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
            ("TotalPageFaultCount", wintypes.DWORD),
            ("TotalProcesses", wintypes.DWORD),
            ("ActiveProcesses", wintypes.DWORD),
            ("TotalTerminatedProcesses", wintypes.DWORD),
        ]


def windows_abi_layout() -> dict[str, int]:
    if os.name != "nt":
        raise ProcessSupervisionError("PSV1-ATTRIBUTE-LIST", "handle-preparation")
    return {
        "pointerBits": ctypes.sizeof(ctypes.c_void_p) * 8,
        "startupInfoSize": ctypes.sizeof(STARTUPINFOW),
        "startupInfoExSize": ctypes.sizeof(STARTUPINFOEXW),
        "processInformationSize": ctypes.sizeof(PROCESS_INFORMATION),
        "jobExtendedLimitSize": ctypes.sizeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION),
    }


class _WindowsKernelV1:
    WAIT_OBJECT_0 = 0
    WAIT_TIMEOUT = 258
    INFINITE = 0xFFFFFFFF
    HANDLE_FLAG_INHERIT = 1
    STARTF_USESTDHANDLES = 0x100
    CREATE_SUSPENDED = 0x4
    CREATE_UNICODE_ENVIRONMENT = 0x400
    EXTENDED_STARTUPINFO_PRESENT = 0x80000
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
    PROC_THREAD_ATTRIBUTE_HANDLE_LIST = 0x00020002
    PROC_THREAD_ATTRIBUTE_JOB_LIST = 0x0002000D
    STILL_ACTIVE = 259
    GENERIC_READ = 0x80000000
    FILE_READ_ATTRIBUTES = 0x00000080
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    OPEN_EXISTING = 3
    FILE_ATTRIBUTE_NORMAL = 0x00000080
    FILE_ATTRIBUTE_DIRECTORY = 0x00000010
    FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
    FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    def __init__(self) -> None:
        self.k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._bind()

    def _bind(self) -> None:
        k = self.k32
        k.CreatePipe.argtypes = [ctypes.POINTER(wintypes.HANDLE), ctypes.POINTER(wintypes.HANDLE), ctypes.POINTER(SECURITY_ATTRIBUTES), wintypes.DWORD]
        k.CreatePipe.restype = wintypes.BOOL
        k.SetHandleInformation.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]
        k.SetHandleInformation.restype = wintypes.BOOL
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.CloseHandle.restype = wintypes.BOOL
        k.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        k.CreateJobObjectW.restype = wintypes.HANDLE
        k.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        k.SetInformationJobObject.restype = wintypes.BOOL
        k.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        k.QueryInformationJobObject.restype = wintypes.BOOL
        k.InitializeProcThreadAttributeList.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(SIZE_T)]
        k.InitializeProcThreadAttributeList.restype = wintypes.BOOL
        k.UpdateProcThreadAttribute.argtypes = [ctypes.c_void_p, wintypes.DWORD, SIZE_T, ctypes.c_void_p, SIZE_T, ctypes.c_void_p, ctypes.c_void_p]
        k.UpdateProcThreadAttribute.restype = wintypes.BOOL
        k.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
        k.DeleteProcThreadAttributeList.restype = None
        k.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(STARTUPINFOW), ctypes.POINTER(PROCESS_INFORMATION)]
        k.CreateProcessW.restype = wintypes.BOOL
        k.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        k.CreateFileW.restype = wintypes.HANDLE
        k.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(BY_HANDLE_FILE_INFORMATION)]
        k.GetFileInformationByHandle.restype = wintypes.BOOL
        k.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
        k.IsProcessInJob.restype = wintypes.BOOL
        k.ResumeThread.argtypes = [wintypes.HANDLE]
        k.ResumeThread.restype = wintypes.DWORD
        k.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        k.TerminateJobObject.restype = wintypes.BOOL
        k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k.WaitForSingleObject.restype = wintypes.DWORD
        k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        k.GetExitCodeProcess.restype = wintypes.BOOL

    def close(self, handle: int | None) -> bool:
        return not handle or bool(self.k32.CloseHandle(handle))

    def open_guarded_path(self, path: Path, *, directory: bool) -> int:
        desired = self.FILE_READ_ATTRIBUTES if directory else self.GENERIC_READ
        share = self.FILE_SHARE_READ | (self.FILE_SHARE_WRITE if directory else 0)
        flags = self.FILE_FLAG_OPEN_REPARSE_POINT | (
            self.FILE_FLAG_BACKUP_SEMANTICS if directory else self.FILE_ATTRIBUTE_NORMAL
        )
        handle = self.k32.CreateFileW(
            str(path), desired, share, None, self.OPEN_EXISTING, flags, None
        )
        if not handle or handle == self.INVALID_HANDLE_VALUE:
            raise ctypes.WinError(ctypes.get_last_error())
        return int(handle)

    def guarded_path_information(self, handle: int) -> "BY_HANDLE_FILE_INFORMATION":
        info = BY_HANDLE_FILE_INFORMATION()
        if not self.k32.GetFileInformationByHandle(handle, ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        return info


def _stream_open_executable_binding(
    path: Path, descriptor: int
) -> tuple[ExecutableBindingV1, str, str]:
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise OSError("not ordinary executable")
        os.lseek(descriptor, 0, os.SEEK_SET)
        content_digest = hashlib.sha256()
        identity_digest = hashlib.sha256()
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            content_digest.update(chunk)
            identity_digest.update(chunk)
        after = os.fstat(descriptor)
        before_key = (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_size,
            before.st_mtime_ns,
        )
        after_key = (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_size,
            after.st_mtime_ns,
        )
        if before_key != after_key:
            raise OSError("executable changed while hashing")
        identity_digest.update(
            struct.pack(
                ">QQ",
                before.st_size & ((1 << 64) - 1),
                before.st_mtime_ns & ((1 << 64) - 1),
            )
        )
        identity = identity_digest.hexdigest()
        absolute = Path(path)
        if os.path.normcase(str(absolute)) == os.path.normcase(
            os.path.abspath(sys.executable)
        ):
            version_source = (
                f"python:{sys.version_info.major}.{sys.version_info.minor}."
                f"{sys.version_info.micro}:{identity}"
            )
        else:
            version_source = f"native:{identity}"
        binding = ExecutableBindingV1(
            str(absolute),
            before.st_size,
            content_digest.hexdigest(),
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_mtime_ns,
        )
        return binding, identity, hashlib.sha256(version_source.encode("ascii")).hexdigest()
    except (OSError, ValueError, OverflowError, UnicodeError) as exc:
        raise ProcessSupervisionError(
            "PSV1-EXECUTABLE-UNRESOLVED", "request-validation"
        ) from exc


class _ExecutableLaunchOwnerV1:
    """Own the admitted executable object and every guard until OS creation."""

    def __init__(
        self,
        *,
        path: Path,
        resource_name: str,
        descriptor: int = -1,
        parent_handles: tuple[int, ...] = (),
        windows_api: _WindowsKernelV1 | None = None,
        binding: ExecutableBindingV1 | None = None,
        identity_sha256: str = "",
        version_sha256: str = "",
    ) -> None:
        self.path = path
        self.descriptor = descriptor
        self.parent_handles = list(parent_handles)
        self.leaf_handle: int | None = None
        self.windows_api = windows_api
        self.binding = binding
        self.identity_sha256 = identity_sha256
        self.version_sha256 = version_sha256
        self.resource_name = resource_name
        self._closed = False
        self._lock = threading.Lock()

    def close(self, _remaining: float = 0.0) -> None:
        with self._lock:
            if self._closed:
                return
            errors: list[BaseException] = []
            if self.descriptor >= 0:
                descriptor = self.descriptor
                self.descriptor = -1
                try:
                    os.close(descriptor)
                except BaseException as exc:
                    errors.append(exc)
            if self.windows_api is not None:
                if self.leaf_handle is not None:
                    if self.windows_api.close(self.leaf_handle):
                        self.leaf_handle = None
                    else:
                        errors.append(OSError("CloseHandle failed"))
                for index in range(len(self.parent_handles) - 1, -1, -1):
                    handle = self.parent_handles[index]
                    if self.windows_api.close(handle):
                        self.parent_handles.pop(index)
                    else:
                        errors.append(OSError("CloseHandle failed"))
            self._closed = (
                self.descriptor < 0
                and self.leaf_handle is None
                and not self.parent_handles
            )
            if errors:
                raise OSError("executable launch owner cleanup failed") from errors[0]


def _acquire_executable_launch_owner(
    path: Path,
    lifecycle: RunLifecycleV1,
    *,
    windows_api: _WindowsKernelV1 | None = None,
    resource_name: str = "executable-launch:task",
) -> _ExecutableLaunchOwnerV1:
    absolute = Path(os.path.abspath(path))
    if not Path(path).is_absolute() or os.path.normcase(str(absolute)) != os.path.normcase(
        str(path)
    ):
        raise ProcessSupervisionError(
            "PSV1-EXECUTABLE-UNRESOLVED", "request-validation"
        )
    owner = _ExecutableLaunchOwnerV1(
        path=absolute,
        resource_name=resource_name,
        windows_api=windows_api,
    )
    lifecycle.register_resource(resource_name, owner.close)
    try:
        if os.name == "nt":
            import msvcrt

            api = windows_api or _WindowsKernelV1()
            owner.windows_api = api
            for component in reversed((absolute.parent, *absolute.parent.parents)):
                metadata = component.lstat()
                if stat.S_ISLNK(metadata.st_mode) or _is_reparse(metadata):
                    raise OSError("executable parent reparse")
                handle = api.open_guarded_path(component, directory=True)
                owner.parent_handles.append(handle)
                info = api.guarded_path_information(handle)
                if (
                    not info.dwFileAttributes & api.FILE_ATTRIBUTE_DIRECTORY
                    or info.dwFileAttributes & api.FILE_ATTRIBUTE_REPARSE_POINT
                ):
                    raise OSError("executable parent identity")
            leaf = absolute.lstat()
            if stat.S_ISLNK(leaf.st_mode) or _is_reparse(leaf):
                raise OSError("executable reparse")
            owner.leaf_handle = api.open_guarded_path(absolute, directory=False)
            info = api.guarded_path_information(owner.leaf_handle)
            if (
                info.dwFileAttributes & api.FILE_ATTRIBUTE_DIRECTORY
                or info.dwFileAttributes & api.FILE_ATTRIBUTE_REPARSE_POINT
            ):
                raise OSError("executable identity")
            descriptor = msvcrt.open_osfhandle(
                owner.leaf_handle, os.O_RDONLY | getattr(os, "O_BINARY", 0)
            )
            owner.descriptor = descriptor
            owner.leaf_handle = None
        else:
            raise ProcessSupervisionError(
                "PSV1-POSIX-ORACLE-UNAVAILABLE", "request-validation"
            )
        binding, identity, version = _stream_open_executable_binding(
            absolute, owner.descriptor
        )
        owner.binding = binding
        owner.identity_sha256 = identity
        owner.version_sha256 = version
        return owner
    except BaseException as exc:
        if isinstance(exc, ProcessSupervisionError):
            raise
        if isinstance(exc, (OSError, ValueError, OverflowError, UnicodeError)):
            raise ProcessSupervisionError(
                "PSV1-EXECUTABLE-UNRESOLVED", "request-validation"
            ) from exc
        raise


def _environment_mapping(request: ProcessRequestV1) -> dict[str, str]:
    return {row.name: row.value for row in request.environment}


def _convert_windows_handle_to_fd(
    handle: int,
    flags: int,
    lifecycle: RunLifecycleV1,
    resource_name: str,
    *,
    converter: Callable[[int, int], int] | None = None,
    handle_closer: Callable[[int], bool] | None = None,
) -> int:
    if converter is None:
        import msvcrt

        converter = msvcrt.open_osfhandle
    if handle_closer is None:
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle_closer = lambda value: bool(kernel32.CloseHandle(value))

    def close_handle(_remaining: float) -> None:
        if not handle_closer(handle):
            raise OSError("CloseHandle failed")

    if not lifecycle.has_resource(resource_name):
        lifecycle.register_resource(resource_name, close_handle)
    try:
        descriptor = converter(handle, flags)
    except OSError as exc:
        try:
            handle_closer(handle)
        finally:
            lifecycle.mark_resource_uncertain(resource_name)
        raise ProcessSupervisionError(
            "PSV1-DESCRIPTOR-OWNERSHIP", "handle-preparation"
        ) from exc
    try:
        lifecycle.transfer_resource(
            resource_name,
            lambda _remaining: os.close(descriptor),
            state="FD_OWNED",
        )
    except BaseException:
        lifecycle.mark_resource_uncertain(resource_name)
        raise
    return descriptor

def _windows_environment_block(request: ProcessRequestV1) -> ctypes.Array[Any]:
    rows = sorted(request.environment, key=lambda row: row.name.casefold())
    text = "\0".join(f"{row.name}={row.value}" for row in rows) + "\0\0"
    if len(text) > MAX_WINDOWS_ENVIRONMENT_UNITS:
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    return ctypes.create_unicode_buffer(text)


def _reader_fd(
    fd: int,
    stream: str,
    capture: BoundedCaptureV1,
    chunk_size: int,
    issues: list[str],
    lifecycle: RunLifecycleV1 | None = None,
    resource_name: str | None = None,
) -> None:
    try:
        while True:
            data = os.read(fd, chunk_size)
            if not data:
                return
            capture.feed(stream, data)
    except BaseException:
        issues.append("PSV1-CAPTURE-IO")
    finally:
        if lifecycle is not None and resource_name is not None:
            if not lifecycle.close_resource(
                resource_name, time.monotonic() + RUNNER_CLOSE_TIMEOUT_SECONDS
            ):
                issues.append("PSV1-DESCRIPTOR-OWNERSHIP")
        else:
            try:
                os.close(fd)
            except OSError:
                issues.append("PSV1-RESOURCE-CLOSE")


def _writer_fd(
    fd: int,
    payload: bytes,
    observation: dict[str, object],
    issues: list[str],
    lifecycle: RunLifecycleV1 | None = None,
    resource_name: str | None = None,
) -> None:
    try:
        written = write_all_bytes(payload, lambda view: os.write(fd, view))
        observation.update(written=written, complete=True)
    except ProcessSupervisionError as exc:
        observation.update(failure=exc.failure_id, written=observation.get("written", 0), complete=False)
    except BaseException:
        observation.update(failure="PSV1-STDIN-BROKEN-PIPE", complete=False)
    finally:
        if lifecycle is not None and resource_name is not None:
            if not lifecycle.close_resource(
                resource_name, time.monotonic() + RUNNER_CLOSE_TIMEOUT_SECONDS
            ):
                issues.append("PSV1-DESCRIPTOR-OWNERSHIP")
        else:
            try:
                os.close(fd)
            except OSError:
                issues.append("PSV1-RESOURCE-CLOSE")


def _result_from_parts(
    request: ProcessRequestV1,
    started: float,
    *,
    executable_identity_sha256: str,
    backend: str,
    capture: BoundedCaptureV1,
    stdin_state: Mapping[str, object],
    exit_code: int | None,
    failure_id: str | None,
    stage: str,
    timed_out: bool,
    cancelled: bool,
    ownership_confirmed: bool,
    settlement_state: str,
    direct_reaped: bool,
    primary_thread_closed: bool,
    job_handle_closed: bool,
    resources_closed: bool,
    poisoned: bool,
    cleanup_issues: Sequence[str],
) -> ProcessResultV1:
    streams = capture.snapshot()
    if failure_id is None and (
        capture.limit_crossed or any(stream.truncated for stream in streams.values())
    ):
        failure_id = "PSV1-CAPTURE-LIMIT"
        stage = "capture-limit"
    if failure_id:
        outcome = "supervisor-failure"
    elif exit_code == 0:
        outcome = "success"
    else:
        outcome = "child-failure"
    if cleanup_issues and outcome == "success":
        outcome = "supervisor-failure"
        failure_id = "PSV1-RESOURCE-CLOSE"
        stage = "resource-cleanup"
    return ProcessResultV1(
        1,
        SETTLED_EVENT_ID,
        outcome,
        stage,
        failure_id,
        os.fspath(request.resolved_executable),
        executable_identity_sha256,
        _json_argv_sha256(request.argv),
        len(request.argv),
        exit_code,
        timed_out,
        cancelled,
        max(0.0, time.monotonic() - started),
        StdinObservationV1(
            len(request.stdin_bytes or b""),
            int(stdin_state.get("written", 0)),
            bool(stdin_state.get("complete", not request.stdin_bytes)),
        ),
        streams["stdout"],
        streams["stderr"],
        TreeObservationV1(
            backend,
            ownership_confirmed,
            settlement_state,
            settlement_state == "EMPTY",
            direct_reaped,
            primary_thread_closed,
            job_handle_closed,
        ),
        resources_closed,
        poisoned,
        tuple(cleanup_issues),
        policy_id=request.capture_policy.policy_id,
    )


class _WindowsBackendV1:
    def __init__(
        self,
        coordinator: WindowsInheritanceCoordinatorV1,
        admission_owner: WindowsArgvAdmissionOwnerV1,
        api: _WindowsKernelV1 | None = None,
    ) -> None:
        self.coordinator = coordinator
        self.admission_owner = admission_owner
        self.api = api or _WindowsKernelV1()

    def run(
        self,
        request: ProcessRequestV1,
        lifecycle: RunLifecycleV1,
        validated_cwd: ValidatedCwdV1,
        executable_launch_owner: "_ExecutableLaunchOwnerV1",
        admission: WindowsArgvAdmissionV1 | None = None,
        internal_probe_admission: WindowsInternalProbeAdmissionV1 | None = None,
    ) -> ProcessResultV1:
        import msvcrt

        if (admission is None) == (internal_probe_admission is None):
            raise ProcessSupervisionError(
                "PSV1-ARGV-CODEC-UNSUPPORTED", "request-validation"
            )
        internal_probe = internal_probe_admission is not None
        handle_prefix = "windows-probe-handle:" if internal_probe else "windows-handle:"
        backend_resource_name = (
            "windows-probe-backend" if internal_probe else "windows-backend"
        )
        worker_prefix = "windows-probe-worker:" if internal_probe else ""

        def phase_deadline(now: float | None = None) -> float:
            current = time.monotonic() if now is None else now
            deadline = current + request.settle_policy.timeout_seconds
            return min(deadline, request.deadline_monotonic) if internal_probe else deadline

        started = time.monotonic()
        k = self.api.k32
        handles: dict[str, int | None] = {name: None for name in (
            "stdin_child", "stdin_parent", "stdout_child", "stdout_parent",
            "stderr_child", "stderr_parent", "job", "process", "thread",
        )}
        attr_buffer: ctypes.Array[Any] | None = None
        attr_initialized = False
        capture = BoundedCaptureV1(
            request.capture_policy, request.capture_sink_binding
        )
        issues: list[str] = []
        stdin_state: dict[str, object] = {"written": 0, "complete": not request.stdin_bytes}
        failure_id: str | None = None
        stage = "completed"
        timed_out = False
        cancelled = False
        ownership_confirmed = False
        direct_reaped = False
        primary_thread_closed = False
        job_handle_closed = False
        settlement = "AMBIGUOUS"
        exit_code: int | None = None
        reader_threads: list[threading.Thread] = []
        writer_thread: threading.Thread | None = None
        process_created = False
        job_terminate_failed = False

        def register_handle(name: str, handle: int) -> None:
            handles[name] = handle
            resource_name = f"{handle_prefix}{name}"

            def close_owned_handle(_remaining: float) -> None:
                current = handles.get(name)
                if current is None:
                    return
                closed = self.api.close(current)
                handles[name] = None
                if not closed:
                    raise OSError("CloseHandle failed")

            lifecycle.register_resource(resource_name, close_owned_handle)

        def close_handle(name: str) -> None:
            nonlocal primary_thread_closed, job_handle_closed
            resource_name = f"{handle_prefix}{name}"
            if lifecycle.has_resource(resource_name):
                if not lifecycle.close_resource(
                    resource_name,
                    time.monotonic() + RUNNER_CLOSE_TIMEOUT_SECONDS,
                ):
                    issues.append("PSV1-DESCRIPTOR-OWNERSHIP")
            if name == "thread" and (
                not lifecycle.has_resource(resource_name)
                or lifecycle.resource_state(resource_name) == "CLOSED"
            ):
                primary_thread_closed = True
            elif name == "job" and (
                not lifecycle.has_resource(resource_name)
                or lifecycle.resource_state(resource_name) == "CLOSED"
            ):
                job_handle_closed = True

        def terminate_job() -> bool:
            if handles["job"]:
                return bool(k.TerminateJobObject(handles["job"], 1))
            return True

        def last_close_after_terminate_failure() -> None:
            nonlocal failure_id, stage, settlement, job_terminate_failed
            job_terminate_failed = True
            failure_id = "PSV1-JOB-TERMINATE"
            stage = "tree-settlement"
            settlement = "AMBIGUOUS"
            if handles["job"]:
                accounting = JOBOBJECT_BASIC_ACCOUNTING_INFORMATION()
                returned = wintypes.DWORD()
                k.QueryInformationJobObject(
                    handles["job"],
                    1,
                    ctypes.byref(accounting),
                    ctypes.sizeof(accounting),
                    ctypes.byref(returned),
                )
                close_handle("job")

        def cleanup_windows_backend(remaining: float) -> None:
            before = len(issues)
            deadline = time.monotonic() + remaining
            named_threads = [
                *(("stdout", thread) for thread in reader_threads[:1]),
                *(("stderr", thread) for thread in reader_threads[1:2]),
            ]
            if writer_thread is not None:
                named_threads.append(("stdin", writer_thread))
            for name, thread in named_threads:
                thread.join(max(0.0, deadline - time.monotonic()))
                if thread.is_alive():
                    issues.append("PSV1-RESOURCE-CLOSE")
                else:
                    lifecycle.release_worker(f"{worker_prefix}{name}")
            for name in (
                "thread",
                "process",
                "stdin_child",
                "stdin_parent",
                "stdout_child",
                "stdout_parent",
                "stderr_child",
                "stderr_parent",
            ):
                close_handle(name)
            if attr_initialized and attr_buffer is not None:
                try:
                    k.DeleteProcThreadAttributeList(
                        ctypes.cast(attr_buffer, ctypes.c_void_p)
                    )
                except BaseException:
                    issues.append("PSV1-RESOURCE-CLOSE")
            close_handle("job")
            if len(issues) != before:
                raise OSError("windows backend cleanup incomplete")

        lifecycle.register_resource(backend_resource_name, cleanup_windows_backend)

        try:
            if self.coordinator.poisoned:
                raise ProcessSupervisionError("PSV1-INHERITANCE-POISONED", "handle-preparation")
            sa = SECURITY_ATTRIBUTES(ctypes.sizeof(SECURITY_ATTRIBUTES), None, False)
            pairs = (
                ("stdin_child", "stdin_parent"),
                ("stdout_parent", "stdout_child"),
                ("stderr_parent", "stderr_child"),
            )
            for read_name, write_name in pairs:
                read = wintypes.HANDLE()
                write = wintypes.HANDLE()
                if not k.CreatePipe(ctypes.byref(read), ctypes.byref(write), ctypes.byref(sa), 0):
                    raise ProcessSupervisionError("PSV1-HANDLE-INHERITANCE", "handle-preparation")
                register_handle(read_name, read.value)
                register_handle(write_name, write.value)
            job = k.CreateJobObjectW(None, None)
            if not job:
                raise ProcessSupervisionError("PSV1-ATTRIBUTE-LIST", "handle-preparation")
            register_handle("job", job)
            limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            limits.BasicLimitInformation.LimitFlags = self.api.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not k.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise ProcessSupervisionError("PSV1-ATTRIBUTE-LIST", "handle-preparation")
            size = SIZE_T()
            k.InitializeProcThreadAttributeList(None, 2, 0, ctypes.byref(size))
            if not size.value:
                raise ProcessSupervisionError("PSV1-ATTRIBUTE-LIST", "handle-preparation")
            attr_buffer = ctypes.create_string_buffer(size.value)
            attr_pointer = ctypes.cast(attr_buffer, ctypes.c_void_p)
            if not k.InitializeProcThreadAttributeList(attr_pointer, 2, 0, ctypes.byref(size)):
                raise ProcessSupervisionError("PSV1-ATTRIBUTE-LIST", "handle-preparation")
            attr_initialized = True
            job_value = wintypes.HANDLE(job)
            if not k.UpdateProcThreadAttribute(
                attr_pointer, 0, self.api.PROC_THREAD_ATTRIBUTE_JOB_LIST,
                ctypes.byref(job_value), ctypes.sizeof(job_value), None, None,
            ):
                raise ProcessSupervisionError("PSV1-ATTRIBUTE-LIST", "handle-preparation")
            child_handles = (wintypes.HANDLE * 3)(
                handles["stdin_child"], handles["stdout_child"], handles["stderr_child"]
            )
            if not k.UpdateProcThreadAttribute(
                attr_pointer, 0, self.api.PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
                child_handles, ctypes.sizeof(child_handles), None, None,
            ):
                raise ProcessSupervisionError("PSV1-ATTRIBUTE-LIST", "handle-preparation")
            startup = STARTUPINFOEXW()
            startup.StartupInfo.cb = ctypes.sizeof(startup)
            startup.StartupInfo.dwFlags = self.api.STARTF_USESTDHANDLES
            startup.StartupInfo.hStdInput = handles["stdin_child"]
            startup.StartupInfo.hStdOutput = handles["stdout_child"]
            startup.StartupInfo.hStdError = handles["stderr_child"]
            startup.lpAttributeList = attr_pointer
            info = PROCESS_INFORMATION()
            command = ctypes.create_unicode_buffer(serialize_msvcrt_argv(request.argv))
            environment = _windows_environment_block(request)
            child_names = ("stdin_child", "stdout_child", "stderr_child")
            with self.coordinator.lock:
                if self.coordinator.poisoned:
                    raise ProcessSupervisionError("PSV1-INHERITANCE-POISONED", "handle-preparation")
                enabled: list[str] = []
                try:
                    for name in child_names:
                        if not k.SetHandleInformation(handles[name], self.api.HANDLE_FLAG_INHERIT, self.api.HANDLE_FLAG_INHERIT):
                            raise ProcessSupervisionError("PSV1-HANDLE-INHERITANCE", "handle-preparation")
                        enabled.append(name)
                    create_owner = WindowsCreateOwnerV1(
                        self.admission_owner,
                        request,
                        lambda: k.CreateProcessW(
                            str(request.resolved_executable), command, None, None, True,
                            self.api.CREATE_SUSPENDED | self.api.CREATE_UNICODE_ENVIRONMENT | self.api.EXTENDED_STARTUPINFO_PRESENT,
                            environment, validated_cwd.canonical_absolute, ctypes.byref(startup.StartupInfo), ctypes.byref(info),
                        ),
                        executable_launch_owner,
                    )
                    created = (
                        create_owner.create_internal_probe(
                            lifecycle,
                            internal_probe_admission,
                            executable_launch_owner,
                        )
                        if internal_probe_admission is not None
                        else create_owner.create_task(
                            lifecycle, request, admission
                        )
                    )
                    if not created:
                        raise ProcessSupervisionError("PSV1-PROCESS-CREATE", "process-create")
                    register_handle("process", info.hProcess)
                    register_handle("thread", info.hThread)
                    process_created = True
                    if not lifecycle.close_resource(
                        executable_launch_owner.resource_name,
                        time.monotonic() + RUNNER_CLOSE_TIMEOUT_SECONDS,
                    ):
                        raise ProcessSupervisionError(
                            "PSV1-RESOURCE-CLOSE", "resource-cleanup"
                        )
                finally:
                    restoration_ok = True
                    for name in enabled:
                        if not k.SetHandleInformation(handles[name], self.api.HANDLE_FLAG_INHERIT, 0):
                            restoration_ok = False
                    if not restoration_ok:
                        self.coordinator.poison()
                        if process_created:
                            if not terminate_job():
                                last_close_after_terminate_failure()
                        failure_id = "PSV1-INHERITANCE-POISONED"
                        stage = "handle-preparation"
            for name in child_names:
                close_handle(name)
            if failure_id:
                raise ProcessSupervisionError(failure_id, stage)
            in_job = wintypes.BOOL()
            if not k.IsProcessInJob(handles["process"], handles["job"], ctypes.byref(in_job)) or not in_job.value:
                raise ProcessSupervisionError("PSV1-TREE-VERIFICATION", "tree-verification")
            ownership_confirmed = True
            if request.diagnostic_port is not None:
                request.diagnostic_port.emit(
                    "process.supervision.windows.job-verified.v1",
                    {"ownershipConfirmed": True},
                )
            resume = k.ResumeThread(handles["thread"])
            if resume != 1:
                raise ProcessSupervisionError("PSV1-PROCESS-RESUME", "process-resume")
            close_handle("thread")
            def convert_parent(name: str, flags: int) -> tuple[int, str]:
                handle = handles[name]
                assert handle is not None
                resource_name = f"{handle_prefix}{name}"
                try:
                    descriptor = _convert_windows_handle_to_fd(
                        handle,
                        flags,
                        lifecycle,
                        resource_name,
                        converter=msvcrt.open_osfhandle,
                        handle_closer=self.api.close,
                    )
                    return descriptor, resource_name
                finally:
                    handles[name] = None

            stdin_fd, stdin_resource = convert_parent(
                "stdin_parent", os.O_WRONLY | os.O_BINARY
            )
            stdout_fd, stdout_resource = convert_parent(
                "stdout_parent", os.O_RDONLY | os.O_BINARY
            )
            stderr_fd, stderr_resource = convert_parent(
                "stderr_parent", os.O_RDONLY | os.O_BINARY
            )
            for fd, name, resource_name in (
                (stdout_fd, "stdout", stdout_resource),
                (stderr_fd, "stderr", stderr_resource),
            ):
                lifecycle.register_worker(f"{worker_prefix}{name}")
                thread = threading.Thread(
                    target=_reader_fd,
                    args=(
                        fd,
                        name,
                        capture,
                        request.capture_policy.chunk_size,
                        issues,
                        lifecycle,
                        resource_name,
                    ),
                    daemon=True,
                )
                thread.start()
                reader_threads.append(thread)
            lifecycle.register_worker(f"{worker_prefix}stdin")
            writer_thread = threading.Thread(
                target=_writer_fd,
                args=(
                    stdin_fd,
                    request.stdin_bytes or b"",
                    stdin_state,
                    issues,
                    lifecycle,
                    stdin_resource,
                ),
                daemon=True,
            )
            writer_thread.start()
            settle_deadline: float | None = None
            while True:
                wait = k.WaitForSingleObject(
                    handles["process"],
                    max(1, int(ENGINE_POLL_INTERVAL_SECONDS * 1000)),
                )
                now = time.monotonic()
                wait_failed = wait == self.api.INFINITE
                if wait_failed:
                    failure_id, stage = "PSV1-INTERNAL", "execution"
                elif capture.limit_crossed:
                    failure_id, stage = "PSV1-CAPTURE-LIMIT", "capture-limit"
                elif capture.io_failed or "PSV1-CAPTURE-IO" in issues:
                    failure_id, stage = "PSV1-CAPTURE-IO", "execution"
                elif stdin_state.get("failure"):
                    failure_id, stage = str(stdin_state["failure"]), "stdin-delivery"
                elif lifecycle.cancelled or (
                    request.cancellation_probe is not None
                    and request.cancellation_probe()
                ):
                    failure_id, stage, cancelled = "PSV1-CANCELLED", "cancellation", True
                elif now >= request.deadline_monotonic:
                    failure_id, stage, timed_out = "PSV1-DEADLINE", "deadline", True
                if failure_id:
                    if not terminate_job():
                        last_close_after_terminate_failure()
                        break
                if wait_failed:
                    break
                if wait == self.api.WAIT_OBJECT_0:
                    direct_reaped = True
                    if all(not thread.is_alive() for thread in reader_threads):
                        break
                    if settle_deadline is None:
                        settle_deadline = phase_deadline(now)
                    elif now >= settle_deadline:
                        if failure_id is None:
                            failure_id, stage = "PSV1-TREE-SETTLEMENT", "tree-settlement"
                        if not terminate_job():
                            last_close_after_terminate_failure()
                            break
                if failure_id and k.WaitForSingleObject(handles["process"], 0) == self.api.WAIT_OBJECT_0:
                    direct_reaped = True
                    break
            code = wintypes.DWORD()
            reap_until = phase_deadline()
            while time.monotonic() <= reap_until:
                if not k.GetExitCodeProcess(handles["process"], ctypes.byref(code)):
                    break
                if code.value != self.api.STILL_ACTIVE:
                    direct_reaped = True
                    exit_code = ctypes.c_int32(code.value).value
                    break
                time.sleep(ENGINE_POLL_INTERVAL_SECONDS)
            for name, thread in zip(("stdout", "stderr"), reader_threads):
                thread.join(max(0.0, phase_deadline() - time.monotonic()))
                if not thread.is_alive():
                    lifecycle.release_worker(f"{worker_prefix}{name}")
            if writer_thread is not None:
                writer_thread.join(max(0.0, phase_deadline() - time.monotonic()))
                if not writer_thread.is_alive():
                    lifecycle.release_worker(f"{worker_prefix}stdin")
            if any(thread.is_alive() for thread in reader_threads) or (writer_thread and writer_thread.is_alive()):
                issues.append("PSV1-RESOURCE-CLOSE")
            if not job_terminate_failed and handles["job"]:
                accounting = JOBOBJECT_BASIC_ACCOUNTING_INFORMATION()
                returned = wintypes.DWORD()
                settle_until = phase_deadline()
                while True:
                    if not k.QueryInformationJobObject(handles["job"], 1, ctypes.byref(accounting), ctypes.sizeof(accounting), ctypes.byref(returned)):
                        settlement = "AMBIGUOUS"
                        if failure_id is None:
                            failure_id, stage = "PSV1-TREE-SETTLEMENT", "tree-settlement"
                        break
                    if accounting.ActiveProcesses == 0:
                        settlement = "EMPTY"
                        break
                    if time.monotonic() >= settle_until:
                        settlement = "NONEMPTY"
                        if not terminate_job():
                            last_close_after_terminate_failure()
                        if failure_id is None:
                            failure_id, stage = "PSV1-TREE-SETTLEMENT", "tree-settlement"
                        break
                    time.sleep(ENGINE_POLL_INTERVAL_SECONDS)
        except ProcessSupervisionError as exc:
            if failure_id is None:
                failure_id, stage = exc.failure_id, exc.terminal_stage
            if (
                exc.failure_id == "PSV1-DEADLINE"
                and exc.terminal_stage == "deadline"
            ):
                timed_out = True
            if not terminate_job():
                last_close_after_terminate_failure()
            if handles["process"]:
                k.WaitForSingleObject(
                    handles["process"],
                    max(0, int((phase_deadline() - time.monotonic()) * 1000)),
                )
                direct_reaped = True
            if handles["job"]:
                accounting = JOBOBJECT_BASIC_ACCOUNTING_INFORMATION()
                returned = wintypes.DWORD()
                settle_until = phase_deadline()
                while time.monotonic() <= settle_until:
                    if not k.QueryInformationJobObject(
                        handles["job"],
                        1,
                        ctypes.byref(accounting),
                        ctypes.sizeof(accounting),
                        ctypes.byref(returned),
                    ):
                        break
                    if accounting.ActiveProcesses == 0:
                        settlement = "EMPTY"
                        break
                    time.sleep(ENGINE_POLL_INTERVAL_SECONDS)
        except BaseException:
            if not terminate_job():
                last_close_after_terminate_failure()
            raise
        if internal_probe:
            if not lifecycle.close_resource(backend_resource_name, phase_deadline()):
                issues.append("PSV1-RESOURCE-CLOSE")
            finalization = lifecycle.observation
        else:
            finalization = lifecycle.finalize_once(phase_deadline())
        issues.extend(finalization.cleanup_issues)
        resources_closed = not any(handles.values()) and not issues
        if settlement == "AMBIGUOUS" and direct_reaped and ownership_confirmed and not failure_id:
            failure_id, stage = "PSV1-TREE-SETTLEMENT", "tree-settlement"
        return _result_from_parts(
            request, started,
            executable_identity_sha256=validated_cwd.executable_identity_sha256,
            backend="windows-job-v1", capture=capture,
            stdin_state=stdin_state, exit_code=exit_code, failure_id=failure_id,
            stage=stage, timed_out=timed_out, cancelled=cancelled,
            ownership_confirmed=ownership_confirmed, settlement_state=settlement,
            direct_reaped=direct_reaped, primary_thread_closed=primary_thread_closed,
            job_handle_closed=job_handle_closed, resources_closed=resources_closed,
            poisoned=self.coordinator.poisoned, cleanup_issues=issues,
        )


def _linux_proc_identity(pid: int) -> tuple[int, int, int]:
    raw = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
    close = raw.rfind(")")
    fields = raw[close + 2 :].split()
    return int(fields[2]), int(fields[3]), int(fields[19])




class ProcessRunnerV1:
    """Composition-root-owned runner with one Windows inheritance coordinator."""

    def __init__(
        self,
        *,
        backend_factory: Callable[..., Callable[[ProcessRequestV1], ProcessResultV1]] | None = None,
        windows_api: _WindowsKernelV1 | None = None,
    ) -> None:
        self.windows_inheritance_coordinator = WindowsInheritanceCoordinatorV1()
        self.windows_argv_admission_owner = WindowsArgvAdmissionOwnerV1(
            _WINDOWS_ARGV_ADMISSION_SEAL,
            self._run_internal_windows_probe,
        )
        self._backend_factory = backend_factory
        self._windows_api = windows_api
        self._closed = False
        self._runner_nonce = secrets.token_bytes(16)
        self._next_counter = 0
        self._active: dict[RunTokenV1, RunLifecycleV1] = {}
        self._consumed_request_ids: set[str] = set()
        self._lock = threading.Lock()

    def __enter__(self) -> "ProcessRunnerV1":
        return self

    def mint_memory_capture_sink(self) -> CaptureSinkBindingV1:
        return CaptureSinkBindingV1(
            "bounded-memory-v1", BoundedMemoryCaptureSinkV1(), _SINK_BINDING_SEAL
        )

    def build_repository_transfer_git_request(
        self,
        *,
        argv: tuple[str, ...],
        resolved_executable: Path,
        cwd: str,
        environment: tuple[EnvironmentRowV1, ...],
        deadline_seconds: float = 60.0,
        capture_limit_bytes: int,
    ) -> tuple[ProcessRequestV1, CaptureSinkBindingV1]:
        """Build the sealed request used by the repository-transfer Git adapter."""

        executable = Path(resolved_executable)
        canonical_cwd = os.path.abspath(cwd)
        try:
            if (
                executable.name.casefold() not in {"git", "git.exe"}
                or not executable.is_absolute()
                or not argv
                or Path(argv[0]).resolve(strict=True) != executable.resolve(strict=True)
                or Path(os.path.realpath(canonical_cwd)) != Path(canonical_cwd)
                or not Path(canonical_cwd).is_dir()
                or not isinstance(deadline_seconds, (int, float))
                or not 0 < deadline_seconds <= 60.0
                or not isinstance(capture_limit_bytes, int)
                or not 0 < capture_limit_bytes <= MAX_CAPTURE_BYTES // 2
            ):
                raise ProcessSupervisionError(
                    "PSV1-REQUEST-INVALID", "request-validation"
                )
            bind_cwd_identity(canonical_cwd)
        except ProcessSupervisionError:
            raise
        except (OSError, RuntimeError, ValueError) as exc:
            raise ProcessSupervisionError(
                "PSV1-REQUEST-INVALID", "request-validation"
            ) from exc
        sink = self.mint_memory_capture_sink()
        request = ProcessRequestV1(
            schema_version=1,
            argv=argv,
            resolved_executable=executable,
            cwd=canonical_cwd,
            environment=environment,
            stdin_bytes=None,
            deadline_monotonic=time.monotonic() + float(deadline_seconds),
            capture_policy=RepositoryTransferCapturePolicyV1(
                "repository-transfer-git-v1",
                capture_limit_bytes * 2,
                capture_limit_bytes,
                0,
                64 * 1024,
                capture_limit_bytes,
            ),
            capture_sink_binding=sink,
            settle_policy=SettlePolicyV1(5.0),
            windows_argv_profile_id=(
                "repository-transfer-git-v1" if os.name == "nt" else None
            ),
            policy_id="repository-transfer-git-v1",
        )
        return request, sink

    def build_hook_health_request(
        self,
        *,
        argv: tuple[str, ...],
        resolved_executable: Path,
        cwd: str,
        environment: tuple[EnvironmentRowV1, ...],
        deadline_monotonic: float,
        settle_timeout_seconds: float,
        stdout_spool: Any,
        trusted_script: Path,
    ) -> ProcessRequestV1:
        if len(argv) < 2:
            raise ProcessSupervisionError(
                "PSV1-REQUEST-INVALID", "request-validation"
            )
        candidate_binding = _hook_script_binding(Path(argv[1]))
        trusted_binding = _hook_script_binding(trusted_script)
        if not hmac.compare_digest(
            str(candidate_binding["sha256"]), str(trusted_binding["sha256"])
        ):
            raise ProcessSupervisionError(
                "PSV1-REQUEST-INVALID", "request-validation"
            )
        binding = CaptureSinkBindingV1(
            "hook-health-spool-v1",
            HookHealthSpoolCaptureSinkV1(stdout_spool),
            _SINK_BINDING_SEAL,
        )
        request = ProcessRequestV1(
            schema_version=1,
            argv=argv,
            resolved_executable=resolved_executable,
            cwd=cwd,
            environment=environment,
            stdin_bytes=None,
            deadline_monotonic=deadline_monotonic,
            capture_policy=hook_health_capture_policy(),
            capture_sink_binding=binding,
            settle_policy=SettlePolicyV1(settle_timeout_seconds),
            windows_argv_profile_id=(
                "python-hook-health-v1" if os.name == "nt" else None
            ),
            policy_id="hook-health-v1",
        )
        sink = binding._sink
        assert type(sink) is HookHealthSpoolCaptureSinkV1
        capability = HookHealthCapabilityV1(
            _hook_health_request_sha256(request),
            sink,
            _hook_spool_identity(stdout_spool),
            _HOOK_HEALTH_CAPABILITY_SEAL,
        )
        sink._bind_capability(capability, _HOOK_HEALTH_CAPABILITY_SEAL)
        binding = dataclasses.replace(
            binding, _hook_health_capability=capability
        )
        return dataclasses.replace(request, capture_sink_binding=binding)

    def _run_internal_windows_probe(
        self,
        lifecycle: RunLifecycleV1,
        request: ProcessRequestV1,
        admission: WindowsInternalProbeAdmissionV1,
    ) -> ProcessResultV1:
        if os.name != "nt":
            raise ProcessSupervisionError(
                "PSV1-ARGV-CODEC-UNSUPPORTED", "request-validation"
            )
        sink_resource = "windows-probe-capture-sink"
        lifecycle.register_resource(
            sink_resource,
            lambda _remaining: request.capture_sink_binding.close(),
        )
        executable_launch_owner = _acquire_executable_launch_owner(
            request.resolved_executable,
            lifecycle,
            windows_api=self._windows_api,
            resource_name=(
                f"executable-launch:probe:{admission.purpose}"
            ),
        )
        canonical = os.path.abspath(request.cwd)
        validated_cwd = ValidatedCwdV1(
            canonical,
            bind_cwd_identity(canonical),
            executable_launch_owner.identity_sha256,
        )
        result = _WindowsBackendV1(
            self.windows_inheritance_coordinator,
            self.windows_argv_admission_owner,
            self._windows_api,
        ).run(
            request,
            lifecycle,
            validated_cwd,
            executable_launch_owner,
            internal_probe_admission=admission,
        )
        sink_closed = lifecycle.close_resource(
            sink_resource, request.deadline_monotonic
        )
        probe_resources_closed = all(
            lifecycle.resource_state(name) == "CLOSED"
            for name in lifecycle.resource_names
            if name.startswith("windows-probe-")
        )
        return dataclasses.replace(
            result,
            resources_closed=(
                result.resources_closed and sink_closed and probe_resources_closed
            ),
            cleanup_uncertain=(
                result.cleanup_uncertain
                or not sink_closed
                or not probe_resources_closed
            ),
        )

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _begin_lifecycle(self) -> RunLifecycleV1:
        with self._lock:
            if self._closed or self._next_counter >= MAX_RUN_COUNTER:
                self._closed = True
                raise ProcessSupervisionError("PSV1-RUNNER-CLOSED", "request-validation")
            self._next_counter += 1
            run_id = RunTokenV1(self._runner_nonce, self._next_counter)
            lifecycle = RunLifecycleV1(run_id)
            self._active[run_id] = lifecycle
            return lifecycle

    def _release_lifecycle(self, lifecycle: RunLifecycleV1) -> None:
        lifecycle.mark_settled()
        with self._lock:
            self._active.pop(lifecycle.token, None)

    def close(self) -> RunnerCloseResultV1:
        deadline = time.monotonic() + RUNNER_CLOSE_TIMEOUT_SECONDS
        with self._lock:
            self._closed = True
            active = tuple(self._active.values())
        for lifecycle in active:
            lifecycle.request_cancel()
        settled: list[str] = []
        unsettled: list[str] = []
        for lifecycle in active:
            if lifecycle.wait_settled(deadline):
                settled.append(lifecycle.token.sha256)
                continue
            lifecycle.finalize_once(deadline)
            if lifecycle.wait_settled(deadline):
                settled.append(lifecycle.token.sha256)
            else:
                unsettled.append(lifecycle.token.sha256)
        return RunnerCloseResultV1(
            "closed" if not unsettled else "failed-unsettled",
            None if not unsettled else "PSV1-RUNNER-CLOSE-INCOMPLETE",
            tuple(settled),
            tuple(unsettled),
        )

    def run(
        self,
        request: ProcessRequestV1,
        *,
        lifecycle: RunLifecycleV1 | None = None,
    ) -> ProcessResultV1:
        started = time.monotonic()
        owned_lifecycle = lifecycle
        if owned_lifecycle is None:
            try:
                owned_lifecycle = self._begin_lifecycle()
            except ProcessSupervisionError as exc:
                return _request_failure(request, exc, started)
        validated_cwd: ValidatedCwdV1 | None = None
        executable_launch_owner: _ExecutableLaunchOwnerV1 | None = None
        try:
            if not isinstance(request, ProcessRequestV1):
                raise ProcessSupervisionError(
                    "PSV1-REQUEST-INVALID", "request-validation"
                )
            _validate_request_shape_before_executable_acquisition(request)
            if os.name != "nt":
                raise ProcessSupervisionError(
                    "PSV1-POSIX-ORACLE-UNAVAILABLE", "request-validation"
                )
            try:
                argv_executable = Path(request.argv[0])
                request_executable = Path(request.resolved_executable)
                if (
                    not argv_executable.is_absolute()
                    or not request_executable.is_absolute()
                    or os.path.normcase(os.path.abspath(argv_executable))
                    != os.path.normcase(os.path.abspath(request_executable))
                ):
                    raise ProcessSupervisionError(
                        "PSV1-EXECUTABLE-UNRESOLVED", "request-validation"
                    )
            except (IndexError, OSError, ValueError) as exc:
                raise ProcessSupervisionError(
                    "PSV1-EXECUTABLE-UNRESOLVED", "request-validation"
                ) from exc
            executable_launch_owner = _acquire_executable_launch_owner(
                request.resolved_executable,
                owned_lifecycle,
                windows_api=self._windows_api,
            )
            validated_cwd = validate_process_request(
                request,
                executable_launch_owner,
                argv_executable_prevalidated=True,
            )
            if os.name == "nt":
                admission = self.windows_argv_admission_owner.admit(
                    owned_lifecycle, request, executable_launch_owner
                )
            else:
                admission = None
        except _WindowsArgvProbeFailure as exc:
            observation = owned_lifecycle.finalize_once(
                min(
                    request.deadline_monotonic,
                    time.monotonic() + RUNNER_CLOSE_TIMEOUT_SECONDS,
                )
            )
            result = dataclasses.replace(
                exc.result,
                executable_identity_sha256=(
                    validated_cwd.executable_identity_sha256
                    if validated_cwd is not None
                    else exc.result.executable_identity_sha256
                ),
                run_token_sha256=owned_lifecycle.token.sha256,
                cleanup_issues=tuple(
                    dict.fromkeys(
                        (*exc.result.cleanup_issues, *observation.cleanup_issues)
                    )
                ),
                resources_closed=(
                    exc.result.resources_closed and observation.resources_closed
                ),
                cleanup_uncertain=(
                    exc.result.cleanup_uncertain or not observation.resources_closed
                ),
            )
            self._release_lifecycle(owned_lifecycle)
            return result
        except ProcessSupervisionError as exc:
            result = _request_failure(
                request,
                exc,
                started,
                executable_identity_sha256=(
                    validated_cwd.executable_identity_sha256
                    if validated_cwd is not None
                    else None
                ),
            )
            observation = owned_lifecycle.finalize_once(
                time.monotonic() + RUNNER_CLOSE_TIMEOUT_SECONDS
            )
            result = dataclasses.replace(
                result,
                cleanup_issues=tuple(
                    dict.fromkeys(
                        (*result.cleanup_issues, *observation.cleanup_issues)
                    )
                ),
                resources_closed=(
                    result.resources_closed and observation.resources_closed
                ),
                cleanup_uncertain=(
                    result.cleanup_uncertain or not observation.resources_closed
                ),
            )
            self._release_lifecycle(owned_lifecycle)
            return dataclasses.replace(
                result, run_token_sha256=owned_lifecycle.token.sha256
            )
        duplicate_request_id = False
        with self._lock:
            if request.request_id is not None:
                if request.request_id in self._consumed_request_ids:
                    duplicate_request_id = True
                else:
                    self._consumed_request_ids.add(request.request_id)
        if duplicate_request_id:
            result = _request_failure(
                request,
                ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation"),
                started,
                executable_identity_sha256=validated_cwd.executable_identity_sha256,
            )
            owned_lifecycle.finalize_once(
                time.monotonic() + RUNNER_CLOSE_TIMEOUT_SECONDS
            )
            self._release_lifecycle(owned_lifecycle)
            return dataclasses.replace(
                result, run_token_sha256=owned_lifecycle.token.sha256
            )
        try:
            owned_lifecycle.register_resource(
                "capture-sink",
                lambda _remaining: request.capture_sink_binding.close(),
            )
        except ProcessSupervisionError:
            pass
        try:
            if (
                bind_cwd_identity(validated_cwd.canonical_absolute)
                != validated_cwd.identity
            ):
                raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
            if self._backend_factory is not None:
                backend = self._backend_factory(self, owned_lifecycle)
                assert executable_launch_owner is not None
                result = backend(
                    request,
                    owned_lifecycle,
                    validated_cwd,
                    executable_launch_owner,
                )
            else:
                assert admission is not None
                assert executable_launch_owner is not None
                result = _WindowsBackendV1(
                    self.windows_inheritance_coordinator,
                    self.windows_argv_admission_owner,
                    self._windows_api,
                ).run(
                    request,
                    owned_lifecycle,
                    validated_cwd,
                    executable_launch_owner,
                    admission,
                )
        except ProcessSupervisionError as exc:
            result = _request_failure(
                request,
                exc,
                started,
                executable_identity_sha256=validated_cwd.executable_identity_sha256,
            )
            if exc.failure_id == "PSV1-CANCELLED":
                result = dataclasses.replace(result, cancelled=True)
        except (OSError, TimeoutError, subprocess.TimeoutExpired):
            result = _request_failure(
                request,
                ProcessSupervisionError("PSV1-INTERNAL", "execution"),
                started,
                executable_identity_sha256=validated_cwd.executable_identity_sha256,
            )
        except BaseException:
            owned_lifecycle.finalize_once(
                time.monotonic() + RUNNER_CLOSE_TIMEOUT_SECONDS
            )
            self._release_lifecycle(owned_lifecycle)
            raise
        observation = owned_lifecycle.finalize_once(
            time.monotonic() + RUNNER_CLOSE_TIMEOUT_SECONDS
        )
        if observation.cleanup_issues and result.outcome == "success":
            result = dataclasses.replace(
                result,
                outcome="supervisor-failure",
                terminal_stage="resource-cleanup",
                failure_id="PSV1-RESOURCE-CLOSE",
                resources_closed=False,
                cleanup_issues=observation.cleanup_issues,
            )
        result = dataclasses.replace(
            result,
            run_token_sha256=owned_lifecycle.token.sha256,
            cleanup_issues=tuple(
                dict.fromkeys((*result.cleanup_issues, *observation.cleanup_issues))
            ),
            resources_closed=result.resources_closed and observation.resources_closed,
            cleanup_uncertain=(
                result.cleanup_uncertain or not observation.resources_closed
            ),
        )
        self._release_lifecycle(owned_lifecycle)
        return result


_SAFE_KEYS = frozenset(
    {
        "schemaVersion", "eventId", "outcome", "terminalStage", "failureId",
        "executableIdentitySha256", "argvSha256", "argvCount", "targetExitCode",
        "timedOut", "cancelled", "durationMilliseconds", "stdinExpectedBytes",
        "stdinWrittenBytes", "stdinComplete", "stdoutObservedBytes",
        "stdoutPersistedBytes", "stdoutTruncated", "stdoutSha256",
        "stderrObservedBytes", "stderrPersistedBytes", "stderrTruncated",
        "stderrSha256", "treeBackend", "ownershipConfirmed", "settlementState",
        "treeEmpty", "directReaped", "primaryThreadClosed", "jobHandleClosed",
        "resourcesClosed", "inheritancePoisoned", "cleanupIssueIds",
        "cleanupIssueCount", "runTokenSha256", "privateArtifactRetained",
        "cleanupUncertain", "requestSha256", "policyId", "authorizing",
        "closesRunIds", "terminalClass",
    }
)


def _safe_token(value: str | None) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or len(value) > MAX_REGISTRY_TOKEN_BYTES
        or any(ord(char) < 0x20 or ord(char) > 0x7E for char in value)
    ):
        raise ProcessSupervisionError("PSV1-INTERNAL", "resource-cleanup")
    return value


def safe_serialize_result(result: ProcessResultV1) -> dict[str, object]:
    if not isinstance(result, ProcessResultV1):
        raise ProcessSupervisionError("PSV1-INTERNAL", "resource-cleanup")
    payload: dict[str, object] = {
        "schemaVersion": result.schema_version,
        "eventId": _safe_token(result.event_id),
        "outcome": _safe_token(result.outcome),
        "terminalStage": _safe_token(result.terminal_stage),
        "failureId": _safe_token(result.failure_id),
        "executableIdentitySha256": result.executable_identity_sha256,
        "argvSha256": result.argv_sha256,
        "argvCount": result.argv_count,
        "targetExitCode": result.target_exit_code,
        "timedOut": result.timed_out,
        "cancelled": result.cancelled,
        "durationMilliseconds": max(0, round(result.duration_seconds * 1000)),
        "stdinExpectedBytes": result.stdin.expected_bytes,
        "stdinWrittenBytes": result.stdin.written_bytes,
        "stdinComplete": result.stdin.complete,
        "stdoutObservedBytes": result.stdout.observed_bytes,
        "stdoutPersistedBytes": result.stdout.persisted_bytes,
        "stdoutTruncated": result.stdout.truncated,
        "stdoutSha256": result.stdout.digest,
        "stderrObservedBytes": result.stderr.observed_bytes,
        "stderrPersistedBytes": result.stderr.persisted_bytes,
        "stderrTruncated": result.stderr.truncated,
        "stderrSha256": result.stderr.digest,
        "treeBackend": _safe_token(result.tree.backend),
        "ownershipConfirmed": result.tree.ownership_confirmed,
        "settlementState": _safe_token(result.tree.settlement_state),
        "treeEmpty": result.tree.tree_empty,
        "directReaped": result.tree.direct_reaped,
        "primaryThreadClosed": result.tree.primary_thread_closed,
        "jobHandleClosed": result.tree.job_handle_closed,
        "resourcesClosed": result.resources_closed,
        "inheritancePoisoned": result.inheritance_poisoned,
        "cleanupIssueIds": [_safe_token(item) for item in result.cleanup_issues],
        "cleanupIssueCount": len(result.cleanup_issues),
        "runTokenSha256": result.run_token_sha256,
        "privateArtifactRetained": result.private_artifact_retained,
        "cleanupUncertain": result.cleanup_uncertain,
        "requestSha256": result.request_sha256,
        "policyId": _safe_token(result.policy_id),
        "authorizing": False,
        "closesRunIds": [],
        "terminalClass": "process-observation-nonauthorizing",
    }
    if set(payload) != _SAFE_KEYS:
        raise ProcessSupervisionError("PSV1-INTERNAL", "resource-cleanup")
    return payload


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
        result[key] = value
    return result


@dataclass(frozen=True)
class DecodedRequestBundleV1:
    header: dict[str, Any]
    stdin_bytes: bytes
    request_sha256: str


@dataclass(frozen=True)
class CapabilityBindingV1:
    nonce: bytes
    claim_directory_identity_sha256: str


def encode_capability_binding(
    nonce: bytes, claim_directory_identity_sha256: str
) -> bytes:
    if (
        len(nonce) != 32
        or not _LOWER_HEX_64.fullmatch(claim_directory_identity_sha256)
    ):
        raise ProcessSupervisionError(
            "PSV1-CLI-CAPABILITY", "request-validation"
        )
    header = json.dumps(
        {
            "schemaVersion": 1,
            "platform": "posix-private-directory-v1",
            "claimDirectoryIdentitySha256": claim_directory_identity_sha256,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    body = CAPABILITY_MAGIC + struct.pack(">I", len(header)) + header + nonce
    return body + hashlib.sha256(body).digest()


def decode_capability_binding(
    payload: bytes, *, platform: str
) -> CapabilityBindingV1:
    if platform != "posix":
        raise ProcessSupervisionError(
            "PSV1-CLI-PRIVATE-DIRECTORY-UNAVAILABLE", "request-validation"
        )
    if len(payload) < 8 + 4 + 2 + 32 + 32 or payload[:8] != CAPABILITY_MAGIC:
        raise ProcessSupervisionError(
            "PSV1-CLI-CAPABILITY", "request-validation"
        )
    header_size = struct.unpack(">I", payload[8:12])[0]
    digest_offset = 12 + header_size + 32
    if header_size > 1024 or digest_offset + 32 != len(payload):
        raise ProcessSupervisionError(
            "PSV1-CLI-CAPABILITY", "request-validation"
        )
    if not hmac.compare_digest(
        hashlib.sha256(payload[:digest_offset]).digest(), payload[digest_offset:]
    ):
        raise ProcessSupervisionError(
            "PSV1-CLI-CAPABILITY", "request-validation"
        )
    try:
        header = json.loads(
            payload[12 : 12 + header_size].decode("utf-8"),
            object_pairs_hook=_strict_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ProcessSupervisionError) as exc:
        raise ProcessSupervisionError(
            "PSV1-CLI-CAPABILITY", "request-validation"
        ) from exc
    expected_platform = "posix-private-directory-v1"
    if not isinstance(header, dict) or set(header) != {
        "schemaVersion",
        "platform",
        "claimDirectoryIdentitySha256",
    }:
        raise ProcessSupervisionError(
            "PSV1-CLI-CAPABILITY", "request-validation"
        )
    directory_digest = header.get("claimDirectoryIdentitySha256")
    if (
        header.get("schemaVersion") != 1
        or header.get("platform") != expected_platform
        or not isinstance(directory_digest, str)
        or not _LOWER_HEX_64.fullmatch(directory_digest)
    ):
        raise ProcessSupervisionError(
            "PSV1-CLI-CAPABILITY", "request-validation"
        )
    return CapabilityBindingV1(
        payload[12 + header_size : digest_offset], directory_digest
    )


@dataclass(frozen=True)
class ClaimedRequestV1:
    claimed_path: Path
    descriptor: int
    expected_size: int
    claim_directory_identity_sha256: str


def claim_directory_identity_sha256(path: str) -> str:
    if not isinstance(path, str):
        raise ProcessSupervisionError("PSV1-CLI-CLAIM", "request-validation")
    canonical = os.path.abspath(path)
    identity = bind_cwd_identity(canonical)
    if os.name != "nt" and stat.S_IMODE(os.stat(canonical).st_mode) != 0o700:
        raise ProcessSupervisionError("PSV1-CLI-CLAIM", "request-validation")
    payload = json.dumps(
        {
            "canonical": canonical,
            "device": identity.device,
            "inode": identity.inode,
            "mode": identity.mode,
            "owner": identity.owner,
            "attributes": identity.attributes,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def capability_binding_sha256(nonce: bytes, directory_digest: str) -> str:
    if len(nonce) != 32 or not _LOWER_HEX_64.fullmatch(directory_digest):
        raise ProcessSupervisionError("PSV1-CLI-CAPABILITY", "request-validation")
    return hashlib.sha256(nonce + bytes.fromhex(directory_digest)).hexdigest()


def validate_claim_directory_binding(
    declared_digest: str,
    observed_digest: str,
    capability_digest: str,
    nonce: bytes,
) -> bool:
    return (
        isinstance(declared_digest, str)
        and isinstance(observed_digest, str)
        and hmac.compare_digest(declared_digest, observed_digest)
        and hmac.compare_digest(
            capability_binding_sha256(nonce, observed_digest), capability_digest
        )
    )


def decode_request_bundle(bundle: bytes) -> DecodedRequestBundleV1:
    if not isinstance(bundle, bytes) or len(bundle) > MAX_REQUEST_BUNDLE_BYTES or len(bundle) < 52:
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    if bundle[:8] != REQUEST_MAGIC:
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    header_size = struct.unpack(">I", bundle[8:12])[0]
    if header_size > MAX_JSON_HEADER_BYTES:
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    stdin_size_offset = 12 + header_size
    if stdin_size_offset + 8 + 32 > len(bundle):
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    stdin_size = struct.unpack(">Q", bundle[stdin_size_offset : stdin_size_offset + 8])[0]
    if stdin_size > MAX_STDIN_BYTES:
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    digest_offset = stdin_size_offset + 8 + stdin_size
    if digest_offset + 32 != len(bundle):
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    expected = hashlib.sha256(bundle[:digest_offset]).digest()
    if not hmac.compare_digest(expected, bundle[digest_offset:]):
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    try:
        header = json.loads(
            bundle[12:stdin_size_offset].decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()),
        )
    except ProcessSupervisionError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation") from exc
    if not isinstance(header, dict):
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    return DecodedRequestBundleV1(
        header,
        bundle[stdin_size_offset + 8 : digest_offset],
        hashlib.sha256(bundle).hexdigest(),
    )


def encode_request_bundle(header: Mapping[str, object], stdin_bytes: bytes) -> bytes:
    try:
        encoded = json.dumps(header, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation") from exc
    if len(encoded) > MAX_JSON_HEADER_BYTES or len(stdin_bytes) > MAX_STDIN_BYTES:
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    body = REQUEST_MAGIC + struct.pack(">I", len(encoded)) + encoded + struct.pack(">Q", len(stdin_bytes)) + stdin_bytes
    return body + hashlib.sha256(body).digest()


_HEADER_KEYS = frozenset(
    {
        "schema", "requestId", "parentPid", "parentStartMarker",
        "capabilitySha256", "argv", "windowsArgvProfileId", "cwd",
        "environment", "stdinSha256",
        "policyId", "deadlineMilliseconds", "nonAuthorizing",
        "claimDirectoryIdentitySha256",
    }
)


def get_process_start_marker(pid: int) -> str:
    if not isinstance(pid, int) or pid <= 0:
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    if os.name != "nt":
        try:
            _pgid, _sid, start = _linux_proc_identity(pid)
            return str(start)
        except (OSError, ValueError, IndexError) as exc:
            raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation") from exc
    from ctypes import wintypes

    class FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME)]
    k32.GetProcessTimes.restype = wintypes.BOOL
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = k32.OpenProcess(0x0400, False, pid)
    if not handle:
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    try:
        creation, exit_time, kernel, user = FILETIME(), FILETIME(), FILETIME(), FILETIME()
        if not k32.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_time), ctypes.byref(kernel), ctypes.byref(user)):
            raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
        return str((creation.dwHighDateTime << 32) | creation.dwLowDateTime)
    finally:
        k32.CloseHandle(handle)


def _decode_cli_cwd(value: object) -> str:
    if not isinstance(value, str):
        raise ProcessSupervisionError(
            "PSV1-REQUEST-INVALID", "request-validation"
        )
    return value


def _cli_capture_policy() -> CapturePolicyV1:
    return CapturePolicyV1(
        "cli-bounded-v1", 1024 * 1024, 64 * 1024, 128 * 1024, 64 * 1024,
    )


def _header_to_request(
    decoded: DecodedRequestBundleV1,
    capability: CapabilityBindingV1,
    claim_directory_digest: str,
    owner: ProcessRunnerV1,
) -> ProcessRequestV1:
    header = decoded.header
    if set(header) != _HEADER_KEYS or header.get("schema") != REQUEST_SCHEMA:
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    request_id = header.get("requestId")
    capability_digest = header.get("capabilitySha256")
    stdin_digest = header.get("stdinSha256")
    deadline_ms = header.get("deadlineMilliseconds")
    if (
        not isinstance(request_id, str) or not _LOWER_HEX_32.fullmatch(request_id)
        or not isinstance(capability_digest, str) or not _LOWER_HEX_64.fullmatch(capability_digest)
        or not validate_claim_directory_binding(
            str(header.get("claimDirectoryIdentitySha256")),
            claim_directory_digest,
            capability_digest,
            capability.nonce,
        )
        or not isinstance(stdin_digest, str) or not _LOWER_HEX_64.fullmatch(stdin_digest)
        or not hmac.compare_digest(hashlib.sha256(decoded.stdin_bytes).hexdigest(), stdin_digest)
        or header.get("policyId") != "cli-bounded-v1"
        or header.get("nonAuthorizing") is not True
        or isinstance(deadline_ms, bool) or not isinstance(deadline_ms, int)
        or not 1 <= deadline_ms <= 86_400_000
        or header.get("parentPid") != os.getppid()
        or header.get("parentStartMarker") != get_process_start_marker(os.getppid())
    ):
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    argv = header.get("argv")
    environment = header.get("environment")
    if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    if not isinstance(environment, list):
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    rows: list[EnvironmentRowV1] = []
    for row in environment:
        if not isinstance(row, dict) or set(row) != {"name", "value"} or not isinstance(row["name"], str) or not isinstance(row["value"], str):
            raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
        rows.append(EnvironmentRowV1(row["name"], row["value"]))
    resolved = Path(argv[0]) if argv else Path()
    return ProcessRequestV1(
        1, tuple(argv), resolved, _decode_cli_cwd(header.get("cwd")), tuple(rows),
        decoded.stdin_bytes, time.monotonic() + deadline_ms / 1000.0,
        _cli_capture_policy(), owner.mint_memory_capture_sink(), SettlePolicyV1(5.0),
        windows_argv_profile_id=header.get("windowsArgvProfileId"),
        request_id=request_id, policy_id="cli-bounded-v1",
    )


def _read_capability(
    handle_number: int, lifecycle: RunLifecycleV1
) -> CapabilityBindingV1:
    if handle_number < 0:
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    if os.name == "nt":
        import msvcrt
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        def close_handle(_remaining: float) -> None:
            if not kernel32.CloseHandle(handle_number):
                raise ctypes.WinError(ctypes.get_last_error())

        lifecycle.register_resource("cli-capability", close_handle)
        try:
            fd = msvcrt.open_osfhandle(
                handle_number, os.O_RDONLY | os.O_BINARY
            )
        except OSError as exc:
            raise ProcessSupervisionError(
                "PSV1-CLI-CAPABILITY", "request-validation"
            ) from exc
        lifecycle.transfer_resource(
            "cli-capability",
            lambda _remaining: os.close(fd),
            state="FD_OWNED",
        )
    else:
        fd = handle_number
        lifecycle.register_resource(
            "cli-capability", lambda _remaining: os.close(fd)
        )
        lifecycle.transfer_resource(
            "cli-capability",
            lambda _remaining: os.close(fd),
            state="FD_OWNED",
        )
    chunks = []
    remaining = 2049
    try:
        while remaining:
            chunk = os.read(fd, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
    except OSError as exc:
        raise ProcessSupervisionError(
            "PSV1-CLI-CAPABILITY", "request-validation"
        ) from exc
    value = b"".join(chunks)
    if not lifecycle.close_resource("cli-capability", time.monotonic() + 1.0):
        raise ProcessSupervisionError(
            "PSV1-CLI-CAPABILITY", "request-validation"
        )
    return decode_capability_binding(
        value, platform="windows" if os.name == "nt" else "posix"
    )


def _open_claim_descriptor(path: Path) -> int:
    if os.name != "nt":
        return os.open(
            path,
            os.O_RDONLY
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
        )
    import msvcrt
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    handle = create_file(
        str(path),
        0x80000000,
        0x00000001 | 0x00000002 | 0x00000004,
        None,
        3,
        0x00000080 | 0x00200000,
        None,
    )
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        kernel32.CloseHandle(handle)
        raise


def _validate_posix_private_metadata(
    directory_metadata: object,
    request_metadata: object,
    effective_uid: int,
) -> None:
    if (
        getattr(directory_metadata, "st_uid", None) != effective_uid
        or not stat.S_ISDIR(getattr(directory_metadata, "st_mode", 0))
        or stat.S_IMODE(getattr(directory_metadata, "st_mode", 0)) != 0o700
        or getattr(request_metadata, "st_uid", None) != effective_uid
        or not stat.S_ISREG(getattr(request_metadata, "st_mode", 0))
        or stat.S_IMODE(getattr(request_metadata, "st_mode", 0)) != 0o600
    ):
        raise ProcessSupervisionError("PSV1-CLI-CLAIM", "request-validation")


def _claim_request_file(
    path: Path,
    lifecycle: RunLifecycleV1,
    *,
    fault_stage: str | None = None,
) -> ClaimedRequestV1:
    path = Path(path)
    parent = bind_cwd_identity(str(path.parent))

    def fault(stage: str) -> None:
        if fault_stage == stage:
            raise ProcessSupervisionError("PSV1-CLI-CLAIM", "request-validation")

    descriptor = -1
    claimed = path.with_name(f".{path.name}.claimed-{os.getpid()}")
    directory_digest = claim_directory_identity_sha256(str(path.parent))

    def cleanup_paths(_remaining: float) -> None:
        failures = []
        for candidate in (claimed, path):
            try:
                candidate.unlink(missing_ok=True)
            except OSError:
                failures.append(candidate)
        if failures:
            raise OSError("private request cleanup")

    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode) or _is_reparse(before):
            raise ProcessSupervisionError("PSV1-CLI-CLAIM", "request-validation")
        if os.name != "nt":
            _validate_posix_private_metadata(
                path.parent.stat(), before, os.geteuid()
            )
        descriptor = _open_claim_descriptor(path)
        lifecycle.register_resource("cli-request-paths", cleanup_paths)
        lifecycle.register_resource(
            "cli-request-descriptor",
            lambda _remaining: os.close(descriptor),
        )
        fault("after-open")
        opened = os.fstat(descriptor)
        fault("after-first-fstat")
        if (
            not stat.S_ISREG(opened.st_mode)
            or (before.st_dev, before.st_ino, before.st_mode, before.st_size)
            != (opened.st_dev, opened.st_ino, opened.st_mode, opened.st_size)
            or opened.st_size > MAX_REQUEST_BUNDLE_BYTES
        ):
            raise ProcessSupervisionError("PSV1-CLI-CLAIM", "request-validation")
        fault("after-register")
        os.replace(path, claimed)
        fault("after-rename")
        if bind_cwd_identity(str(claimed.parent)) != parent:
            raise ProcessSupervisionError("PSV1-CLI-CLAIM", "request-validation")
        after = os.fstat(descriptor)
        fault("after-second-fstat")
        if (
            (opened.st_dev, opened.st_ino, opened.st_mode, opened.st_size)
            != (after.st_dev, after.st_ino, after.st_mode, after.st_size)
        ):
            raise ProcessSupervisionError("PSV1-CLI-CLAIM", "request-validation")
        return ClaimedRequestV1(
            claimed, descriptor, opened.st_size, directory_digest
        )
    except ProcessSupervisionError:
        raise
    except OSError as exc:
        raise ProcessSupervisionError("PSV1-CLI-CLAIM", "request-validation") from exc


def _read_claimed_request(
    claim: ClaimedRequestV1,
    *,
    fault_stage: str | None = None,
) -> bytes:
    chunks: list[bytes] = []
    remaining = MAX_REQUEST_BUNDLE_BYTES + 1
    try:
        while remaining:
            chunk = os.read(claim.descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
            if fault_stage == "during-read":
                raise ProcessSupervisionError(
                    "PSV1-CLI-CLAIM", "request-validation"
                )
        if fault_stage == "after-eof":
            raise ProcessSupervisionError("PSV1-CLI-CLAIM", "request-validation")
        payload = b"".join(chunks)
        if (
            len(payload) != claim.expected_size
            or len(payload) > MAX_REQUEST_BUNDLE_BYTES
        ):
            raise ProcessSupervisionError("PSV1-CLI-CLAIM", "request-validation")
        return payload
    except ProcessSupervisionError:
        raise
    except OSError as exc:
        raise ProcessSupervisionError("PSV1-CLI-CLAIM", "request-validation") from exc


def _safe_cli_failure(
    error: ProcessSupervisionError,
    observation: FinalizerObservationV1 | None = None,
    *,
    private_artifact_retained: bool = False,
) -> dict[str, object]:
    issues = observation.cleanup_issues if observation is not None else ()
    cleanup_uncertain = (
        observation is None
        or not observation.resources_closed
        or private_artifact_retained
    )
    return {
        "schemaVersion": 1,
        "eventId": SETTLED_EVENT_ID,
        "outcome": "supervisor-failure",
        "terminalStage": error.terminal_stage,
        "failureId": error.failure_id,
        "resourcesClosed": not cleanup_uncertain,
        "cleanupUncertain": cleanup_uncertain,
        "privateArtifactRetained": private_artifact_retained,
        "cleanupIssueIds": list(issues),
        "cleanupIssueCount": len(issues),
        "authorizing": False,
        "closesRunIds": [],
        "terminalClass": "process-observation-nonauthorizing",
    }


def _consume_request_id(
    directory: Path,
    request_id: str,
    request_sha256: str,
    lifecycle: RunLifecycleV1,
) -> None:
    """Create one private non-secret tombstone so a copied bundle cannot replay."""

    if not _LOWER_HEX_32.fullmatch(request_id) or not _LOWER_HEX_64.fullmatch(request_sha256):
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation")
    tombstone = directory / f".process-request-consumed-{request_id}"
    state = {"committed": False}

    def cleanup_uncommitted(_remaining: float) -> None:
        if not state["committed"]:
            tombstone.unlink(missing_ok=True)

    lifecycle.register_resource("cli-tombstone-uncommitted", cleanup_uncommitted)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(tombstone, flags, 0o600)
    except FileExistsError as exc:
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation") from exc
    except OSError as exc:
        raise ProcessSupervisionError("PSV1-REQUEST-INVALID", "request-validation") from exc
    lifecycle.register_resource(
        "cli-tombstone-descriptor", lambda _remaining: os.close(descriptor)
    )
    write_all_bytes(
        request_sha256.encode("ascii"), lambda view: os.write(descriptor, view)
    )
    if not lifecycle.close_resource(
        "cli-tombstone-descriptor", time.monotonic() + 1.0
    ):
        raise ProcessSupervisionError(
            "PSV1-RESOURCE-CLOSE", "resource-cleanup"
        )
    state["committed"] = True


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-file", type=Path, required=True)
    parser.add_argument("--capability-handle", type=int, required=True)
    args = parser.parse_args(argv)
    if os.name == "nt":
        error = ProcessSupervisionError(
            "PSV1-CLI-PRIVATE-DIRECTORY-UNAVAILABLE",
            "request-validation",
        )
        observation = FinalizerObservationV1("complete", True, ())
        print(
            json.dumps(
                _safe_cli_failure(error, observation),
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    owner = ProcessRunnerV1()
    lifecycle: RunLifecycleV1 | None = None
    handed_to_run = False
    try:
        lifecycle = owner._begin_lifecycle()
        claim = _claim_request_file(args.request_file, lifecycle)
        capability = _read_capability(args.capability_handle, lifecycle)
        if not hmac.compare_digest(
            capability.claim_directory_identity_sha256,
            claim.claim_directory_identity_sha256,
        ):
            raise ProcessSupervisionError(
                "PSV1-CLI-CAPABILITY", "request-validation"
            )
        payload = _read_claimed_request(claim)
        decoded = decode_request_bundle(payload)
        request = _header_to_request(
            decoded,
            capability,
            claim.claim_directory_identity_sha256,
            owner,
        )
        assert request.request_id is not None
        _consume_request_id(
            claim.claimed_path.parent,
            request.request_id,
            decoded.request_sha256,
            lifecycle,
        )
        handed_to_run = True
        result = owner.run(request, lifecycle=lifecycle)
        result = dataclasses.replace(result, request_sha256=decoded.request_sha256)
        print(json.dumps(safe_serialize_result(result), sort_keys=True, separators=(",", ":")))
        return 0 if result.outcome in {"success", "child-failure"} else 1
    except (ProcessSupervisionError, OSError) as raw:
        exc = (
            raw
            if isinstance(raw, ProcessSupervisionError)
            else ProcessSupervisionError("PSV1-CLI-CLAIM", "request-validation")
        )
        observation = None
        if lifecycle is not None and not handed_to_run:
            observation = lifecycle.finalize_once(
                time.monotonic() + RUNNER_CLOSE_TIMEOUT_SECONDS
            )
            owner._release_lifecycle(lifecycle)
        retained = args.request_file.exists() or any(
            args.request_file.parent.glob(f".{args.request_file.name}.claimed-*")
        )
        print(
            json.dumps(
                _safe_cli_failure(
                    exc,
                    observation,
                    private_artifact_retained=retained,
                ),
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    except BaseException:
        if lifecycle is not None and not handed_to_run:
            lifecycle.finalize_once(time.monotonic() + RUNNER_CLOSE_TIMEOUT_SECONDS)
            owner._release_lifecycle(lifecycle)
        raise


__all__ = [
    "BoundedCaptureV1",
    "BoundedMemoryCaptureSinkV1",
    "CapabilityBindingV1",
    "CapturePolicyV1",
    "CaptureSinkBindingV1",
    "ClaimedRequestV1",
    "CwdIdentityV1",
    "DecodedRequestBundleV1",
    "EnvironmentRowV1",
    "FinalizerV1",
    "HOOK_HEALTH_STDERR_LIMIT_BYTES",
    "HookHealthSpoolCaptureSinkV1",
    "MemoryCaptureSinkV1",
    "ProcessRequestV1",
    "ProcessResultV1",
    "ProcessRunnerV1",
    "ProcessSupervisionError",
    "RepositoryTransferCapturePolicyV1",
    "SettlePolicyV1",
    "RunLifecycleV1",
    "RunnerCloseResultV1",
    "RunTokenV1",
    "WindowsArgvAdmissionOwnerV1",
    "WindowsArgvAdmissionV1",
    "KimiWindowsProfileV1",
    "WindowsCreateOwnerV1",
    "WindowsInheritanceCoordinatorV1",
    "ValidatedCwdV1",
    "bind_cwd_identity",
    "capability_binding_sha256",
    "claim_directory_identity_sha256",
    "decode_request_bundle",
    "decode_capability_binding",
    "encode_capability_binding",
    "encode_request_bundle",
    "get_process_start_marker",
    "hook_health_capture_policy",
    "resolve_executable_identity",
    "resolve_executable_version",
    "safe_serialize_result",
    "serialize_msvcrt_argv",
    "validate_process_request",
    "validate_claim_directory_binding",
    "windows_abi_layout",
    "write_all_bytes",
]


if __name__ == "__main__":
    raise SystemExit(main())
