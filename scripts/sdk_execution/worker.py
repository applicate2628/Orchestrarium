"""One-operation SDK worker protocol with explicit runtime composition.

The process-supervision owner must create this worker inside containment before
any provider binding can be initialized. Protocol cleanup and process settlement
are separate evidence. There is deliberately no CLI switch, environment flag or
request field that asserts qualification. The fixed runtime factory checks the
actual Job boundary and existing launch authority before provider construction.
"""

from __future__ import annotations

import asyncio
from contextlib import ExitStack
import hashlib
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any, Awaitable, Callable

if __package__ in {None, ""}:
    # Isolated Python excludes the script directory and PYTHONPATH. Import only
    # the source tree containing this fixed entry point, not the operation cwd.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from process_supervision.process_runner import ENGINE_POLL_INTERVAL_SECONDS, MAX_STDIN_BYTES
from process_supervision.windows_job import WindowsJobError
from sdk_execution.contracts import CancelReceipt, ExecutionRequest, ExecutionResult, Observation, json_text, strict_json
from sdk_execution.runtime import RuntimeBindingError
from sdk_execution.coordination import CoordinationInferenceRequest, CoordinationInferenceResult


MAX_FRAME_BYTES = MAX_STDIN_BYTES
AUTHORITY_EFFECTS = frozenset({
    "start", "client_start", "thread_start", "turn_start", "resume", "reconcile",
    "connect", "query", "tool", "account",
})


def request_binding(request: ExecutionRequest) -> str:
    return hashlib.sha256(json_text(request.to_dict()).encode("utf-8")).hexdigest()


def authority_context(request: ExecutionRequest, effect: str, context: object) -> str | None:
    """Canonical bounded exact arguments/evidence, never an inferred permission."""
    if context is None:
        if effect == "account":
            raise ValueError("account authority requires evidence context")
        return None
    if request.provider != "claude" or type(context) is not dict:
        raise ValueError("unsupported authority context")
    if effect == "tool":
        if (set(context) != {"kind", "name", "arguments"} or context["kind"] != "tool"
            or type(context["name"]) is not str or not context["name"]
            or type(context["arguments"]) is not dict):
            raise ValueError("invalid tool authority context")
    elif effect == "account":
        evidence = context.get("evidence")
        if (set(context) != {"kind", "evidence"} or context["kind"] != "account"
            or type(evidence) is not dict or set(evidence) != {"phase", "data"}
            or evidence["phase"] not in {"before_connect", "initialize", "system_init"}
            or type(evidence["data"]) is not dict):
            raise ValueError("invalid account authority context")
    else:
        raise ValueError("unexpected authority context")
    encoded = json_text(context)
    if len(encoded.encode("utf-8")) > min(request.max_output_bytes, MAX_FRAME_BYTES):
        raise ValueError("authority context exceeds operation byte budget")
    return encoded


def encode_frame(value: dict[str, Any]) -> bytes:
    payload = json.dumps(
        value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8") + b"\n"
    if len(payload) > MAX_FRAME_BYTES:
        raise ValueError("worker frame exceeds process-owner byte budget")
    return payload


def decode_frame(payload: bytes) -> dict[str, Any]:
    if (not isinstance(payload, bytes) or not payload
        or len(payload) > MAX_FRAME_BYTES or not payload.endswith(b"\n")
        or b"\n" in payload[:-1]):
        raise ValueError("invalid worker frame")
    value = strict_json(payload.decode("utf-8"), max_bytes=MAX_FRAME_BYTES)
    if not isinstance(value, dict) or not isinstance(value.get("kind"), str):
        raise ValueError("invalid worker message")
    return value


def read_execute_envelope(payload: bytes) -> tuple[ExecutionRequest, dict[str, Any] | None]:
    frame = decode_frame(payload)
    if (set(frame) not in ({"kind", "request"}, {"kind", "request", "runtime_selection"})
        or frame["kind"] not in {"execute", "infer_coordination"}):
        raise ValueError("expected one execute frame")
    if "runtime_selection" in frame and type(frame["runtime_selection"]) is not dict:
        raise ValueError("invalid worker runtime selection")
    request_type = CoordinationInferenceRequest if frame["kind"] == "infer_coordination" else ExecutionRequest
    return request_type.from_dict(frame["request"]), frame.get("runtime_selection")


async def serve_operation(
    request: ExecutionRequest,
    adapter: Any,
    read_frame: Callable[[], Awaitable[bytes]],
    write_frame: Callable[[bytes], Awaitable[None]],
    *,
    authority_sink: ObservationSink | None = None,
) -> None:
    """Exercise the protocol with an already-created adapter, not OS admission.

    Offline tests use in-memory adapters and pipes. ``serve_stdio`` supplies the
    bounded native pipe bridge without constructing an SDK or proving containment.
    """
    execution = asyncio.create_task(adapter.execute(request))
    cancel_sent = False
    terminal_emitted = False

    async def read_controls() -> None:
        nonlocal cancel_sent
        try:
            while True:
                frame = decode_frame(await read_frame())
                if frame["kind"] == "authority_response" and authority_sink is not None:
                    authority_sink.accept_authority(frame)
                    continue
                if (set(frame) != {"kind", "run_id"} or frame["kind"] != "cancel"
                    or frame["run_id"] != request.run_id):
                    raise ValueError("cancel frame does not match this operation")
                cancel_sent = True
                if authority_sink is not None:
                    authority_sink.close_authority()
                receipt = await adapter.cancel(request.run_id)
                if not isinstance(receipt, CancelReceipt) or receipt.run_id != request.run_id:
                    raise ValueError("invalid cancellation receipt")
                await write_frame(encode_frame({"kind": "cancel", "receipt": receipt.to_dict()}))
                return
        finally:
            # Close before this task yields its failure to the operation owner;
            # a queued valid reply cannot outlive a subsequent protocol failure.
            if authority_sink is not None:
                authority_sink.close_authority()

    control = asyncio.create_task(read_controls())

    async def emit_terminal(result: ExecutionResult) -> None:
        nonlocal terminal_emitted
        expected = CoordinationInferenceResult if type(request) is CoordinationInferenceRequest else ExecutionResult
        if not isinstance(result, expected) or result.request != request:
            raise ValueError("invalid execution result")
        kind = "coordination_result" if type(request) is CoordinationInferenceRequest else "result"
        payload = encode_frame({"kind": kind, "result": result.to_dict()})
        terminal_emitted = True  # A partial/failed write must never be retried.
        await write_frame(payload)

    try:
        done, _pending = await asyncio.wait(
            (execution, control), return_when=asyncio.FIRST_COMPLETED
        )
        if control in done:
            control.result()
        result = await execution
        await emit_terminal(result)
    finally:
        if authority_sink is not None:
            authority_sink.close_authority()
        control.cancel()
        await asyncio.gather(control, return_exceptions=True)
        try:
            if not execution.done():
                try:
                    if not cancel_sent:
                        await adapter.cancel(request.run_id)
                finally:
                    execution.cancel()
                    await asyncio.gather(execution, return_exceptions=True)
        finally:
            if (not terminal_emitted and execution.done() and not execution.cancelled()
                and execution.exception() is None):
                # Preserve an acquired result even when a concurrent control or
                # cleanup failure makes this worker exit non-cleanly.
                await emit_terminal(execution.result())


class _PipeFrames:
    """Borrowed, single-reader/writer nonblocking pipes; no background threads."""

    def __init__(self, stdin_fd: int, stdout_fd: int) -> None:
        self.stdin_fd = stdin_fd
        self.stdout_fd = stdout_fd
        self.pending = bytearray()
        self._write_lock = asyncio.Lock()

    async def read(self) -> bytes:
        while True:
            newline = self.pending.find(b"\n")
            if newline >= 0:
                frame = bytes(self.pending[:newline + 1])
                del self.pending[:newline + 1]
                return frame
            if len(self.pending) >= MAX_FRAME_BYTES:
                raise ValueError("worker frame exceeds process-owner byte budget")
            try:
                data = os.read(self.stdin_fd, min(65536, MAX_FRAME_BYTES - len(self.pending)))
            except BlockingIOError:
                await asyncio.sleep(ENGINE_POLL_INTERVAL_SECONDS)
                continue
            if not data:
                if self.pending:
                    raise ValueError("incomplete worker frame")
                raise EOFError("worker stdin closed")
            self.pending.extend(data)

    async def write(self, payload: bytes) -> None:
        if not payload or len(payload) > MAX_FRAME_BYTES:
            raise ValueError("invalid worker output frame")
        async with self._write_lock:
            view = memoryview(payload)
            while view:
                try:
                    count = os.write(self.stdout_fd, view)
                except BlockingIOError:
                    await asyncio.sleep(ENGINE_POLL_INTERVAL_SECONDS)
                    continue
                if count <= 0:
                    raise OSError("worker stdout made no progress")
                view = view[count:]


class ObservationSink:
    """One bounded writer, with explicit async and background-thread entrypoints."""

    def __init__(self, request: ExecutionRequest, frames: _PipeFrames) -> None:
        self._request = request
        self._frames = frames
        self._loop = asyncio.get_running_loop()
        self._loop_thread = threading.get_ident()
        self._sequence = 0
        self._payload_bytes = 0
        self._lock = asyncio.Lock()
        self._authority_lock = asyncio.Lock()
        self._authority_sequence = 0
        self._authority_pending: tuple[int, str, asyncio.Future[bool], str | None] | None = None
        self._authority_closed = False
        self._request_binding = request_binding(request)

    async def authorize(
        self, request: ExecutionRequest, effect: str, context: dict[str, Any] | None = None,
    ) -> None:
        if request != self._request or effect not in AUTHORITY_EFFECTS:
            raise RuntimeBindingError("parent_authority_binding_mismatch")
        context_json = authority_context(request, effect, context)
        async with self._authority_lock:
            if self._authority_closed:
                raise RuntimeBindingError("parent_authority_closed")
            sequence = self._authority_sequence
            decision: asyncio.Future[bool] = self._loop.create_future()
            self._authority_pending = (sequence, effect, decision, context_json)
            try:
                frame = {
                    "kind": "authority_request", "run_id": request.run_id,
                    "request_sha256": self._request_binding,
                    "sequence": sequence, "effect": effect,
                }
                if context_json is not None:
                    frame["context"] = json.loads(context_json)
                await self._frames.write(encode_frame(frame))
                if not await decision or self._authority_closed:
                    raise RuntimeBindingError("parent_authority_denied")
            finally:
                self._authority_pending = None
                self._authority_sequence += 1

    def authorize_from_thread(self, request: ExecutionRequest, effect: str) -> None:
        if threading.get_ident() == self._loop_thread:
            raise ValueError("event-loop adapters must await ObservationSink.authorize")
        asyncio.run_coroutine_threadsafe(self.authorize(request, effect), self._loop).result()

    def accept_authority(self, frame: dict[str, Any]) -> None:
        pending = self._authority_pending
        fields = {"kind", "run_id", "request_sha256", "sequence", "effect", "allowed"}
        if pending is not None and pending[3] is not None:
            fields.add("context")
        if (set(frame) != fields
            or frame["kind"] != "authority_response" or pending is None
            or self._authority_closed or pending[2].done()
            or frame["run_id"] != self._request.run_id
            or frame["request_sha256"] != self._request_binding
            or type(frame["sequence"]) is not int or frame["sequence"] != pending[0]
            or frame["effect"] != pending[1] or type(frame["allowed"]) is not bool):
            raise ValueError("invalid parent authority response")
        if authority_context(self._request, frame["effect"], frame.get("context")) != pending[3]:
            raise ValueError("parent authority response context mismatch")
        pending[2].set_result(frame["allowed"])

    def close_authority(self) -> None:
        self._authority_closed = True
        pending = self._authority_pending
        if pending is not None and not pending[2].done():
            pending[2].set_result(False)

    async def record(self, observation: Observation) -> None:
        async with self._lock:
            if not isinstance(observation, Observation) or observation.sequence != self._sequence:
                raise ValueError("worker observation sequence mismatch")
            size = len(observation.payload_json.encode("utf-8"))
            if (self._sequence >= self._request.max_events
                or size > self._request.max_output_bytes - self._payload_bytes):
                raise ValueError("worker observation budget exceeded")
            await self._frames.write(encode_frame({
                "kind": "observation", "run_id": self._request.run_id,
                "observation": observation.to_dict(),
            }))
            self._sequence += 1
            self._payload_bytes += size

    def record_from_thread(self, observation: Observation) -> None:
        if threading.get_ident() == self._loop_thread:
            raise ValueError("event-loop adapters must await ObservationSink.record")
        asyncio.run_coroutine_threadsafe(self.record(observation), self._loop).result()


async def serve_stdio(
    create_adapter: Callable[[ExecutionRequest, ObservationSink, dict[str, Any] | None], Any],
    *,
    stdin_fd: int | None = None,
    stdout_fd: int | None = None,
) -> None:
    """Serve one operation on native pipes, after creator-owned containment.

    Windows pipe nonblocking mode requires Python 3.12 or newer. Unsupported
    descriptors/modes fail before execute; no blocking-thread fallback is used.
    This owns pipe modes only, never closes caller-owned descriptors or processes.
    The outer process owner supplies the hard deadline and settlement.
    The factory is a trusted composition seam, not proof of containment. It is
    called only after request validation; main does not accept one from input.
    Async adapters await sink.record; synchronous SDK threads use
    sink.record_from_thread. Neither uses an unbounded intermediate queue.
    """
    input_fd = sys.stdin.fileno() if stdin_fd is None else stdin_fd
    output_fd = sys.stdout.fileno() if stdout_fd is None else stdout_fd
    frames = _PipeFrames(input_fd, output_fd)
    with ExitStack() as restore:
        for fd in (input_fd, output_fd):
            blocking = os.get_blocking(fd)
            os.set_blocking(fd, False)
            restore.callback(os.set_blocking, fd, blocking)
        request, selection = read_execute_envelope(await frames.read())
        sink = ObservationSink(request, frames)
        adapter = create_adapter(request, sink, selection)
        await serve_operation(request, adapter, frames.read, frames.write, authority_sink=sink)


def _create_runtime_adapter(
    request: ExecutionRequest, sink: ObservationSink, raw_selection: dict[str, Any] | None,
) -> Any:
    if raw_selection is None:
        raise RuntimeBindingError("runtime_selection_required")
    from sdk_execution.runtime import create_codex_adapter, runtime_selection_from_dict

    selection = runtime_selection_from_dict(request.provider, raw_selection)
    if request.provider == "codex":
        return create_codex_adapter(request, sink, selection)
    from sdk_execution.claude import create_claude_adapter
    return create_claude_adapter(request, sink, selection)


def main() -> int:
    """Use only the fixed, explicitly selected and owner-checked runtime factory."""
    try:
        asyncio.run(serve_stdio(_create_runtime_adapter))
    except RuntimeBindingError as error:
        reason = str(error)  # The runtime owner defines content-free stable codes.
    except WindowsJobError as error:
        reason = error.failure_id
    except (ValueError, TypeError, UnicodeError, EOFError):
        reason = "SDK-WORKER-PROTOCOL"
    except OSError:
        reason = "SDK-WORKER-IO"
    except Exception:
        reason = "SDK-WORKER-EXECUTION"
    else:
        return 0
    # Never expose runtime/account/configuration or provider exception text.
    sys.stdout.buffer.write(encode_frame({"kind": "unavailable", "reason": reason}))
    sys.stdout.buffer.flush()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
