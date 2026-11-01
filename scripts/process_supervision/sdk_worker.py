"""SDK worker composition through the existing process owner, never a supervisor.

This candidate does not qualify SDK or OS behavior. The fixed worker entry point
requires explicit runtime selection; the creator verifies its retained outer
Job before process creation, including when Python adds a nested venv Job. Generic POSIX and Windows private-request CLI holds are
unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import inspect
import json
from pathlib import Path
from typing import Callable

from .process_runner import (
    MAX_STDIN_BYTES, CancellationProbeV1, CapturePolicyV1, EnvironmentRowV1,
    ProcessDialogueChannelV1, ProcessDialogueV1, ProcessResultV1,
    ProcessRunnerV1, ProcessSupervisionError, SdkWorkerProcessRequestV1,
    SdkWorkerWindowsProfileV1, SettlePolicyV1,
)
from sdk_execution.contracts import CancelReceipt, ExecutionRequest, ExecutionResult, Observation, json_text
from sdk_execution.coordination import CoordinationInferenceRequest, CoordinationInferenceResult
from sdk_execution.worker import AUTHORITY_EFFECTS, authority_context, decode_frame, encode_frame, request_binding


_OBSERVATION_SEAL = object()


@dataclass(frozen=True)
class SdkWorkerObservation:
    """Keep protocol evidence even when the process owner cannot settle cleanly."""

    request: ExecutionRequest = field(repr=False)
    process: ProcessResultV1
    result: ExecutionResult | CoordinationInferenceResult | None = field(repr=False)
    cancel: CancelReceipt | None
    unavailable_reason: str | None
    protocol_error: str | None
    job_memory_limit_bytes: int
    runtime_selection_json: str | None = field(repr=False)
    observations: tuple[Observation, ...] = field(repr=False)
    stdout: bytes = field(repr=False)
    stderr: bytes = field(repr=False)
    _seal: object = field(repr=False, compare=False)

    def is_bound_to(self, request: ExecutionRequest) -> bool:
        """In-process composition binding, never persisted authority or OS proof."""
        values = (
            self.request, self.process, self.result, self.cancel,
            self.unavailable_reason, self.protocol_error, self.job_memory_limit_bytes,
            self.runtime_selection_json,
            self.observations, self.stdout, self.stderr,
        )
        return (
            type(self._seal) is tuple and len(self._seal) == len(values) + 1
            and self._seal[0] is _OBSERVATION_SEAL
            and all(original is current for original, current in zip(self._seal[1:], values))
            and self.request == request
            and (self.result is None or self.result.request == request)
        )


def build_sdk_worker_request(
    owner: ProcessRunnerV1,
    request: ExecutionRequest,
    *,
    environment: tuple[EnvironmentRowV1, ...],
    deadline_monotonic: float,
    job_memory_limit_bytes: int,
    runtime_selection: dict[str, object] | None = None,
    cancellation_probe: CancellationProbeV1 | None = None,
    capture_limit_bytes: int = MAX_STDIN_BYTES,
) -> SdkWorkerProcessRequestV1:
    """No credential discovery or inherited environment; caller owns every row.

    Capture defaults to the existing owner's bounded protocol-byte budget rather
    than the provider's content-only budget, which excludes JSON framing/stderr.
    """
    if type(owner) is not ProcessRunnerV1:
        raise ValueError("existing process owner is required")
    if type(request) not in {ExecutionRequest, CoordinationInferenceRequest}:
        raise ValueError("expected SDK execution request")
    if type(environment) is not tuple or any(type(row) is not EnvironmentRowV1 for row in environment):
        raise ValueError("explicit environment rows are required")
    if type(capture_limit_bytes) is not int or not 0 < capture_limit_bytes <= MAX_STDIN_BYTES:
        raise ValueError("invalid worker capture budget")
    execute = _execute_payload(request, runtime_selection, job_memory_limit_bytes)
    cancel = encode_frame({"kind": "cancel", "run_id": request.run_id})
    if len(execute) + len(cancel) > MAX_STDIN_BYTES:
        raise ValueError("worker request leaves no cancellation-frame budget")
    argv = SdkWorkerWindowsProfileV1.build_argv()
    return SdkWorkerProcessRequestV1(
        1, argv, Path(argv[0]), request.cwd, environment, None,
        deadline_monotonic,
        CapturePolicyV1("sdk-worker-v1", capture_limit_bytes, 0, 0, min(65536, capture_limit_bytes)),
        owner.mint_memory_capture_sink(), SettlePolicyV1(5.0),
        cancellation_probe=cancellation_probe,
        windows_argv_profile_id=SdkWorkerWindowsProfileV1.profile_id,
        policy_id="sdk-worker-v1",
        job_memory_limit_bytes=job_memory_limit_bytes,
    )


def _execute_payload(
    request: ExecutionRequest, selection: dict[str, object] | None, memory_limit: int,
) -> bytes:
    kind = "infer_coordination" if type(request) is CoordinationInferenceRequest else "execute"
    frame: dict[str, object] = {"kind": kind, "request": request.to_dict()}
    if selection is not None:
        if type(selection) is not dict:
            raise ValueError("explicit worker runtime selection must be a dictionary")
        if (type(selection.get("job_memory_limit_bytes")) is not int
            or selection["job_memory_limit_bytes"] != memory_limit):
            raise ValueError("runtime and owner memory budgets differ")
        frame["runtime_selection"] = selection
    return encode_frame(frame)


def run_sdk_worker(
    owner: ProcessRunnerV1,
    request: ExecutionRequest,
    *,
    environment: tuple[EnvironmentRowV1, ...],
    deadline_monotonic: float,
    job_memory_limit_bytes: int,
    runtime_selection: dict[str, object] | None = None,
    authority: Callable[..., None] | None = None,
    cancellation_probe: CancellationProbeV1 | None = None,
    capture_limit_bytes: int = MAX_STDIN_BYTES,
) -> SdkWorkerObservation:
    """Run through the existing owner with fresh parent decisions per SDK effect.

    Ordinary policy calls receive (request, effect). Claude's exact tool/account
    checks additionally receive a bounded immutable-snapshot context copy. The
    callable is existing policy authority, not a substitute for OS containment.
    """
    if ((runtime_selection is not None and authority is None)
        or (authority is not None and (not callable(authority) or inspect.iscoroutinefunction(authority)))):
        raise ValueError("existing synchronous parent authority is required")
    if runtime_selection is not None and type(runtime_selection) is not dict:
        raise ValueError("explicit worker runtime selection must be a dictionary")
    selection_json = None if runtime_selection is None else json_text(runtime_selection)
    selection = None if selection_json is None else json.loads(selection_json)
    execute_payload = _execute_payload(request, selection, job_memory_limit_bytes)
    process_request = build_sdk_worker_request(
        owner, request, environment=environment,
        deadline_monotonic=deadline_monotonic,
        job_memory_limit_bytes=job_memory_limit_bytes,
        runtime_selection=selection,
        cancellation_probe=cancellation_probe,
        capture_limit_bytes=capture_limit_bytes,
    )
    result: ExecutionResult | None = None
    cancel: CancelReceipt | None = None
    unavailable: str | None = None
    protocol_error: str | None = None
    observations: list[Observation] = []
    observation_bytes = 0
    authority_sequence = 0
    authority_denied = False
    written_bytes = len(execute_payload)
    cancel_payload = encode_frame({"kind": "cancel", "run_id": request.run_id})
    binding = request_binding(request)

    def receive(channel: ProcessDialogueChannelV1, *, cancelling: bool = False) -> str:
        nonlocal result, cancel, unavailable, observation_bytes
        nonlocal authority_sequence, authority_denied, written_bytes
        try:
            frame = decode_frame(channel.read_line())
            kind = frame["kind"]
            if kind == "authority_request":
                fields = {"kind", "run_id", "request_sha256", "sequence", "effect"}
                if (set(frame) not in (fields, fields | {"context"})
                    or frame["run_id"] != request.run_id or frame["request_sha256"] != binding
                    or type(frame["sequence"]) is not int or frame["sequence"] != authority_sequence
                    or frame["effect"] not in AUTHORITY_EFFECTS
                    or result is not None or unavailable is not None):
                    raise ValueError("invalid worker authority request")
                if "context" in frame and frame["context"] is None:
                    raise ValueError("invalid explicit authority context")
                context = authority_context(request, frame["effect"], frame.get("context"))
                allowed = False
                if authority is not None and not cancelling and not authority_denied:
                    try:
                        decision = (authority(request, frame["effect"]) if context is None
                                    else authority(request, frame["effect"], json.loads(context)))
                        allowed = decision is None
                        if inspect.iscoroutine(decision):
                            decision.close()
                    except Exception:
                        pass  # Denial is content-free; never expose owner exceptions.
                authority_denied = authority_denied or not allowed
                response = encode_frame({**frame, "kind": "authority_response", "allowed": allowed})
                if len(response) + len(cancel_payload) > MAX_STDIN_BYTES - written_bytes:
                    raise ValueError("authority reply leaves no cancellation-frame budget")
                channel.write_line(response)
                written_bytes += len(response)
                authority_sequence += 1
            elif kind == ("coordination_result" if type(request) is CoordinationInferenceRequest else "result") and set(frame) == {"kind", "result"} and result is None:
                result_type = CoordinationInferenceResult if type(request) is CoordinationInferenceRequest else ExecutionResult
                observed = result_type.from_dict(frame["result"])
                if observed.request != request or unavailable is not None:
                    raise ValueError("worker result request mismatch")
                result = observed
                if observed.observations != tuple(observations):
                    raise ValueError("worker terminal observations differ from captured stream")
            elif kind == "observation" and set(frame) == {"kind", "run_id", "observation"}:
                observation = Observation.from_dict(frame["observation"])
                size = len(observation.payload_json.encode("utf-8"))
                if (frame["run_id"] != request.run_id or observation.sequence != len(observations)
                    or len(observations) >= request.max_events
                    or size > request.max_output_bytes - observation_bytes
                    or result is not None or unavailable is not None):
                    raise ValueError("invalid worker observation binding or budget")
                observations.append(observation)
                observation_bytes += size
            elif kind == "cancel" and set(frame) == {"kind", "receipt"} and cancel is None:
                observed_cancel = CancelReceipt.from_dict(frame["receipt"])
                if observed_cancel.run_id != request.run_id:
                    raise ValueError("worker cancellation run mismatch")
                cancel = observed_cancel
            elif kind == "unavailable" and set(frame) == {"kind", "reason"} and unavailable is None:
                if result is not None or not isinstance(frame["reason"], str) or not frame["reason"]:
                    raise ValueError("invalid worker hold")
                unavailable = frame["reason"]
            else:
                raise ValueError("unexpected worker frame")
            return kind
        except ProcessSupervisionError:
            raise
        except (ValueError, TypeError, UnicodeError, EOFError) as exc:
            raise ProcessSupervisionError(
                "PSV1-SDK-WORKER-PROTOCOL", "stdin-delivery"
            ) from exc

    def dialogue(channel: ProcessDialogueChannelV1) -> None:
        nonlocal protocol_error

        def expect_eof() -> None:
            try:
                channel.read_line()
            except EOFError:
                return
            raise ProcessSupervisionError("PSV1-SDK-WORKER-PROTOCOL", "stdin-delivery")

        def receive_terminal(*, cancelling: bool = False) -> None:
            while True:
                kind = receive(channel, cancelling=cancelling)
                if kind in {"observation", "authority_request"} or (kind == "cancel" and cancelling):
                    continue
                if kind == "cancel":
                    raise ProcessSupervisionError("PSV1-SDK-WORKER-PROTOCOL", "stdin-delivery")
                return

        try:
            channel.write_line(execute_payload)
            receive_terminal()
            expect_eof()
            if authority_denied:
                raise ProcessSupervisionError("PSV1-SDK-WORKER-AUTHORITY", "stdin-delivery")
        except ProcessSupervisionError as original:
            protocol_error = original.failure_id
            if original.failure_id not in {"PSV1-CANCELLED", "PSV1-DEADLINE"}:
                raise
            channel.begin_cleanup()
            try:
                channel.write_line(cancel_payload)
                # Observations remain bounded by the submitted operation budget.
                receive_terminal(cancelling=True)
                expect_eof()
            except (ProcessSupervisionError, OSError) as cleanup:
                # Native settlement still runs; preserve the original interrupt
                # and any terminal frame acquired before cleanup failed.
                protocol_error = (
                    cleanup.failure_id if isinstance(cleanup, ProcessSupervisionError)
                    else "PSV1-STDIN-BROKEN-PIPE"
                )
            raise original

    process = owner.run(
        process_request,
        dialogue=ProcessDialogueV1(SdkWorkerWindowsProfileV1.profile_id, dialogue),
    )
    values = (
        request, process, result, cancel, unavailable, protocol_error,
        job_memory_limit_bytes, selection_json, tuple(observations),
        process_request.capture_sink_binding.bytes_for("stdout"),
        process_request.capture_sink_binding.bytes_for("stderr"),
    )
    return SdkWorkerObservation(*values, (_OBSERVATION_SEAL, *values))
