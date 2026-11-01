"""Common executor interface over the existing Kimi ACP/CLI owner.

No SDK, second transport, provider registry, ledger writer or prose-to-JSON model
call is introduced here. ``provider_prompt.launch`` retains admission, exact
launch, private-home/capture lifecycle, safety scanning and durable receiving.
Its existing Windows-only restriction is unchanged. The caller must supply an
already prepared launch whose provenance supplied the common request identities.
"""
from __future__ import annotations

import asyncio
import copy
from dataclasses import replace
from pathlib import Path
import threading
from typing import Callable

import provider_prompt as owner

from ._async import drain_owned
from .contracts import CancelReceipt, ExecutionRequest, ExecutionResult, Observation, json_text


class KimiAdapterError(ValueError):
    """Closed, non-secret adapter failure category."""


class KimiAcpAdapter:
    """One operation; existing Kimi receiving runs once inside the launch owner.

    ``assert_current`` must bind the request to current scope, account, budget and
    permissions, and return None or raise. Kimi's ACP does not expose account
    readback, so this adapter does not fabricate it. The caller supplies the real
    existing owner check, not an assertion copied from the request.

    ``record`` retains only bounded observations derived from the already-scanned
    native terminal. It is not a second receiving or ledger callback. A returned
    native result must not be submitted to the structured SDK receiving path.
    """

    def __init__(
        self, *, prevalidated: owner.PolicyBoundLaunch,
        assert_current: Callable[[ExecutionRequest, str], None],
        record: Callable[[Observation], None],
    ) -> None:
        if type(prevalidated) is not owner.PolicyBoundLaunch:
            raise KimiAdapterError("existing_kimi_launch_required")
        if not callable(assert_current) or not callable(record):
            raise KimiAdapterError("explicit_owner_callbacks_required")
        self._prepared = copy.deepcopy(prevalidated)
        self._assert_current, self._record = assert_current, record
        self._lock = threading.RLock()
        self._cancelled = threading.Event()
        self._request: ExecutionRequest | None = None
        self._operation: owner.KimiOperationBindingV1 | None = None
        self._finished = False

    def _binding(self, request: ExecutionRequest) -> None:
        prepared = self._prepared
        provenance = prepared.provenance
        if not isinstance(request, ExecutionRequest) or request.provider != "kimi" or provenance is None:
            raise KimiAdapterError("unsupported_provider_or_binding")
        expected = (
            provenance.work_item, provenance.external_dispatch_id,
            provenance.external_evidence_run_id, provenance.artifact_identity,
            provenance.assigned_internal_role, provenance.model, provenance.effort,
        )
        actual = (
            request.work_item_id, request.external_dispatch_id,
            request.external_evidence_run_id, request.artifact_id,
            request.role, request.model, request.effort,
        )
        cwd = prepared.control.kimi_capabilities.cwd or str(Path.cwd().resolve())
        if (
            actual != expected or provenance.provider != "kimi"
            or provenance.actual_execution_path != "direct-external-cli"
            or request.model != "kimi-code/k3" or request.effort not in {"high", "max"}
            or request.cwd != cwd or provenance.effort_mapping_loss != request.effort_mapping_loss
            or prepared.control.result_max_bytes > request.max_output_bytes
        ):
            raise KimiAdapterError("kimi_request_binding_mismatch")

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self._binding(request)
        with self._lock:
            if self._request is not None:
                raise KimiAdapterError("operation_already_consumed")
            self._request = request
        task = asyncio.create_task(asyncio.to_thread(self._execute, request))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            await self.cancel(request.run_id)
            # The existing owner must still settle and retain its terminal.
            return await drain_owned(task)

    async def cancel(self, run_id: str) -> CancelReceipt:
        with self._lock:
            if self._request is None or self._request.run_id != run_id:
                return CancelReceipt(run_id, False, False, error="unknown_run")
            if self._finished:
                return CancelReceipt(run_id, False, False, error="already_finished")
            self._cancelled.set()
            exchange = self._operation.exchange if self._operation is not None else None
            # ACP cancel is a notification, not an acknowledgement. Only an
            # observed cancelled prompt response can establish acknowledgement.
            acknowledged = bool(exchange is not None and exchange.cancel_sent and exchange.stop_reason == "cancelled")
            return CancelReceipt(run_id, True, acknowledged)

    def _execute(self, request: ExecutionRequest) -> ExecutionResult:
        def current(effect: str) -> None:
            self._binding(request)
            if self._assert_current(request, effect) is not None:
                raise KimiAdapterError("invalid_authority_callback")

        operation = owner.KimiOperationBindingV1(
            self._prepared, request.prompt.encode("utf-8"), current, self._cancelled.is_set,
        )
        with self._lock:
            self._operation = operation
        try:
            owner_failed = False
            try:
                code = owner.launch("kimi", [], operation=operation)
            except Exception:
                # Preserve any acquired terminal while closing the exception
                # vocabulary. Never relay provider, account or OS diagnostics.
                code, owner_failed = 1, True
            result = self._result(request, operation, code)
            return replace(
                result, status="incomplete", execution_error=result.execution_error or "kimi_owner_failed",
                cleanup_error=result.cleanup_error or "kimi_settlement_unavailable",
            ) if owner_failed else result
        finally:
            with self._lock:
                self._finished = True

    def _result(self, request: ExecutionRequest, operation: owner.KimiOperationBindingV1, code: int) -> ExecutionResult:
        exchange, process = operation.exchange, operation.process_result
        closed = bool(exchange is not None and exchange.protocol_closed)
        cleanup_error = exchange.cleanup_error if exchange is not None else None
        execution_error = capture_error = None
        native_text = None
        observations: tuple[Observation, ...] = ()
        provider_status = None
        if exchange is not None:
            provider_status = {"end_turn": "completed", "cancelled": "interrupted", "refusal": "failed"}.get(exchange.stop_reason)
        try:
            if operation.terminal_bytes is None:
                raise KimiAdapterError("terminal_result_unavailable")
            terminal = owner.parse_provider_result(operation.terminal_bytes.decode("utf-8", errors="strict"))
            provenance = self._prepared.provenance
            if provenance is None or any(terminal.get(k) != v for k, v in provenance.payload().items()):
                raise KimiAdapterError("terminal_binding_mismatch")
            value = terminal.get("resultText")
            if isinstance(value, str) and value.strip():
                if len(value.encode("utf-8")) > request.max_output_bytes:
                    raise KimiAdapterError("native_result_limit_exceeded")
                native_text = value
            if terminal.get("cleanupStatus") != "complete":
                cleanup_error = cleanup_error or "kimi_owner_cleanup_incomplete"
            if terminal.get("status") not in {"completed", "revise"}:
                execution_error = "kimi_native_result_blocked"
            payload = {
                "model": exchange.observed_model if exchange is not None else None,
                "effort": exchange.observed_effort if exchange is not None else None,
                "stopReason": exchange.stop_reason if exchange is not None and exchange.stop_reason in {
                    "end_turn", "cancelled", "refusal", "max_tokens", "max_turn_requests",
                } else None,
                "protocolClosed": closed,
                "selected": terminal.get("selected"), "observed": terminal.get("observed"),
                "nativeGate": terminal.get("gate"),
                "ownerOutcome": terminal.get("primaryOutcome"),
                "ownerStatus": terminal.get("status"),
                "childNonzeroCategory": terminal.get("childNonzeroCategory"),
                "cancelled": terminal.get("cancelled"), "timedOut": terminal.get("timedOut"),
            }
            encoded = json_text(payload)
            if len(encoded.encode("utf-8")) > request.max_output_bytes:
                raise KimiAdapterError("observation_limit_exceeded")
            observation = Observation(0, "kimi.acp.terminal", encoded)
            observations = (observation,)
            try:
                self._record(observation)
            except Exception:
                raise KimiAdapterError("evidence_sink_failed") from None
            if self._prepared.control.ledger and owner.read_back_external_terminal(
                self._prepared.control, "kimi", request.run_id, provenance,
            ) is None:
                raise KimiAdapterError("terminal_ledger_readback_failed")
        except KimiAdapterError as exc:
            capture_error = str(exc)
        except Exception:
            capture_error = "invalid_native_terminal"
        if process is None or not (
            process.resources_closed and process.tree.tree_empty and process.tree.direct_reaped
            and not process.cleanup_issues
        ):
            cleanup_error = cleanup_error or "kimi_process_settlement_unavailable"
        if code != 0:
            execution_error = execution_error or "kimi_owner_execution_failed"
        if provider_status is None:
            execution_error = execution_error or "kimi_terminal_not_completed"
        elif provider_status == "failed":
            execution_error = execution_error or "kimi_provider_refused"
        interrupted = self._cancelled.is_set() or provider_status == "interrupted"
        status = "interrupted" if interrupted else "failed" if execution_error else "incomplete"
        if provider_status == "completed" and native_text is not None and closed and not (
            execution_error or capture_error or cleanup_error or interrupted
        ):
            status = "completed"
        # The existing owner scans optional session identity with its captured
        # credential/path policy. No turn ID or account readback is invented.
        return ExecutionResult(
            request, status, provider_status=provider_status,
            actual_execution_path="direct-external-cli", native_result_text=native_text,
            native_thread_id=operation.native_session_id,
            observations=observations, execution_error=execution_error,
            capture_error=capture_error, cleanup_error=cleanup_error, protocol_closed=closed,
        )
