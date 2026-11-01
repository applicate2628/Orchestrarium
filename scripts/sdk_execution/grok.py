"""Dormant Grok native ACP transport; no default launch authority or activation.

Borrows ProcessDialogueChannelV1; its owner retains deadlines, bounded pipes and
OS settlement. Protocol closure is not settlement. See test_sdk_grok.py for
source-shaped fixtures; no installed release is qualified by those fixtures.
"""
from __future__ import annotations

import asyncio
from dataclasses import replace
import inspect
import threading

from ._async import drain_owned
from .contracts import CancelReceipt, ExecutionRequest, ExecutionResult, Observation, json_text, strict_json


class GrokAcpError(ValueError):
    """Closed, non-secret error vocabulary."""


class GrokAcpExchange:
    """One request sequence over an existing process-owner channel."""

    def __init__(self, *, auth_method: str | None = None, assert_current=None):
        self.auth_method = auth_method
        self.assert_current = assert_current
        self.session_id = None
        self.observed_model = self.observed_effort = None
        self.stop_reason = None
        self.protocol_closed = False
        self._next_id = 0
        self._text = ""
        self._frames = self._wire_bytes = 0
        self._permission_error = None
        self._config_options = {}
        self._configuration_ready = False
        self._cancel = threading.Event()
        self.cancel_sent = self.cancel_acknowledged = False

    def cancel(self):
        self._cancel.set()

    def _send_cancel(self, channel):
        if not self.cancel_sent:
            channel.begin_cleanup()
            self._write(channel, {"jsonrpc": "2.0", "method": "session/cancel", "params": {"sessionId": self.session_id}})
            self.cancel_sent = True

    def _write(self, channel, frame):
        payload = (json_text(frame) + "\n").encode()
        if channel.write_line(payload) != len(payload):
            raise GrokAcpError("grok_short_write")

    def _rpc(self, channel, method, params):
        if method != "session/close":
            if self._cancel.is_set():
                raise GrokAcpError("grok_cancelled_before_effect")
            if self.assert_current is not None:
                try:
                    decision = self.assert_current(self.request, method)
                except Exception:
                    raise GrokAcpError("grok_authority_denied") from None
                if decision is not None:
                    raise GrokAcpError("grok_invalid_authority_callback")
        self._next_id += 1
        identity = self._next_id
        self._write(channel, {"jsonrpc": "2.0", "id": identity, "method": method, "params": params})
        while True:
            if method == "session/prompt" and (self._cancel.is_set() or channel.cancellation_requested()):
                self._send_cancel(channel)
            try:
                line = channel.read_line()
            except Exception as exc:
                if method == "session/prompt" and not self.cancel_sent and getattr(exc, "failure_id", None) == "PSV1-CANCELLED":
                    self._send_cancel(channel)
                    continue
                raise
            self._frames += 1
            self._wire_bytes += len(line)
            if self._frames > self.request.max_events:
                raise GrokAcpError("grok_event_limit")
            if self._wire_bytes > self.request.max_output_bytes:
                raise GrokAcpError("grok_output_limit")
            if not isinstance(line, bytes) or not line.endswith(b"\n") or b"\n" in line[:-1]:
                raise GrokAcpError("grok_invalid_frame")
            frame = strict_json(line.decode(), max_bytes=self.request.max_output_bytes)
            if not isinstance(frame, dict) or frame.get("jsonrpc") != "2.0":
                raise GrokAcpError("grok_invalid_frame")
            if frame.get("method") == "session/request_permission":
                params = frame.get("params", {})
                identity_ok = type(frame.get("id")) is int or isinstance(frame.get("id"), str) and bool(frame["id"])
                if not identity_ok or params.get("sessionId") != self.session_id or method not in {"session/prompt", "session/close"}:
                    raise GrokAcpError("grok_permission_mismatch")
                options = params.get("options")
                matches = [item for item in options if isinstance(item, dict) and item.get("kind") == "reject_once"
                           and isinstance(item.get("optionId"), str) and item["optionId"]] if isinstance(options, list) else []
                valid_options = isinstance(options, list) and all(
                    isinstance(item, dict) and isinstance(item.get("optionId"), str) and item["optionId"]
                    and item.get("kind") in {"reject_once", "reject_always", "allow_once", "allow_always"}
                    for item in options)
                if valid_options:
                    valid_options = len({item["optionId"] for item in options}) == len(options)
                if not valid_options:
                    self._permission_error = "grok_invalid_permission_options"
                outcome = {"outcome": "cancelled"}
                if valid_options and len(matches) == 1 and not self._cancel.is_set() and not self.cancel_sent:
                    outcome = {"outcome": "selected", "optionId": matches[0]["optionId"]}
                self._write(channel, {"jsonrpc": "2.0", "id": frame["id"], "result": {"outcome": outcome}})
                continue
            if frame.get("method") == "session/update":
                params = frame.get("params", {})
                if params.get("sessionId") != self.session_id or "id" in frame:
                    raise GrokAcpError("grok_session_mismatch")
                update = params.get("update", {})
                if update.get("sessionUpdate") == "agent_message_chunk":
                    content = update.get("content", {})
                    if method != "session/prompt" or content.get("type") != "text" or not isinstance(content.get("text"), str):
                        raise GrokAcpError("grok_invalid_content")
                    if len(self._text.encode()) + len(content["text"].encode()) > self.request.max_output_bytes:
                        raise GrokAcpError("grok_output_limit")
                    self._text += content["text"]
                elif update.get("sessionUpdate") == "config_option_update":
                    self._config(update)
                    if self._configuration_ready and (self.observed_model, self.observed_effort) != (self.request.model, self.request.effort):
                        raise GrokAcpError("grok_config_mismatch")
                continue
            if type(frame.get("id")) is not int or frame["id"] != identity or "method" in frame:
                raise GrokAcpError("grok_response_mismatch")
            if "error" in frame or not isinstance(frame.get("result"), dict):
                raise GrokAcpError("grok_rpc_failed")
            return frame["result"]

    def _config(self, result):
        options = result.get("configOptions")
        if not isinstance(options, list) or not all(isinstance(option, dict) and isinstance(option.get("id"), str) for option in options):
            raise GrokAcpError("grok_config_unavailable")
        by_id = {option["id"]: option for option in options}
        if len(by_id) != len(options):
            raise GrokAcpError("grok_invalid_config")
        self._config_options = by_id
        self.observed_model = by_id.get("model", {}).get("currentValue")
        self.observed_effort = by_id.get("reasoning_effort", {}).get("currentValue")

    def _require_option(self, key, selected):
        option = self._config_options.get(key, {})
        options = option.get("options")
        if option.get("type") != "select" or not isinstance(options, list) or not options:
            raise GrokAcpError("grok_config_unsupported")
        if all(isinstance(item, dict) and "group" in item and isinstance(item.get("options"), list) for item in options):
            options = [child for group in options for child in group["options"]]
        if not all(isinstance(item, dict) and isinstance(item.get("value"), str) and "group" not in item for item in options):
            raise GrokAcpError("grok_invalid_config")
        values = [item["value"] for item in options]
        if len(set(values)) != len(values) or selected not in values:
            raise GrokAcpError("grok_config_unsupported")

    def run(self, request: ExecutionRequest, channel) -> ExecutionResult:
        if request.provider != "grok" or self._next_id:
            raise GrokAcpError("unsupported_or_consumed_operation")
        self.request = request
        error = None
        try:
            initialized = self._rpc(channel, "initialize", {"protocolVersion": 1, "clientCapabilities": {}})
            if type(initialized.get("protocolVersion")) is not int or initialized["protocolVersion"] != 1:
                raise GrokAcpError("grok_protocol_incompatible")
            if not isinstance(initialized.get("agentCapabilities", {}).get("sessionCapabilities", {}).get("close"), dict):
                raise GrokAcpError("grok_close_unavailable")
            methods = initialized.get("authMethods", [])
            if not isinstance(self.auth_method, str) or not self.auth_method or not isinstance(methods, list) or sum(
                isinstance(item, dict) and item.get("id") == self.auth_method for item in methods
            ) != 1:
                raise GrokAcpError("grok_auth_method_unavailable")
            self._rpc(channel, "authenticate", {"methodId": self.auth_method, "_meta": {"headless": True}})
            created = self._rpc(channel, "session/new", {"cwd": request.cwd, "mcpServers": []})
            session_id = created.get("sessionId")
            if not isinstance(session_id, str) or not session_id.strip() or len(session_id.encode()) > 4096:
                raise GrokAcpError("grok_session_unavailable")
            self.session_id = session_id
            self._config(created)
            for key, value in (("model", request.model), ("reasoning_effort", request.effort)):
                self._require_option(key, value)
                self._config(self._rpc(channel, "session/set_config_option", {"sessionId": self.session_id, "configId": key, "value": value}))
                if self._config_options.get(key, {}).get("currentValue") != value:
                    raise GrokAcpError("grok_config_mismatch")
            if (self.observed_model, self.observed_effort) != (request.model, request.effort):
                raise GrokAcpError("grok_config_mismatch")
            self._configuration_ready = True
            result = self._rpc(channel, "session/prompt", {"sessionId": self.session_id, "prompt": [{"type": "text", "text": request.prompt}]})
            stop_reason = result.get("stopReason")
            if not isinstance(stop_reason, str) or stop_reason not in {"end_turn", "cancelled", "refusal", "max_tokens", "max_turn_requests"}:
                raise GrokAcpError("grok_invalid_stop_reason")
            self.stop_reason = stop_reason
            self.cancel_acknowledged = self.cancel_sent and self.stop_reason == "cancelled"
            error = self._permission_error
        except GrokAcpError as exc:
            error = str(exc)
        except Exception:
            error = "grok_protocol_failed"
        finally:
            if self.session_id:
                try:
                    channel.begin_cleanup()
                    closed = self._rpc(channel, "session/close", {"sessionId": self.session_id})
                    meta = closed.get("_meta", {})
                    self.protocol_closed = isinstance(meta, dict) and ("x.ai/closeOutcome" not in meta or meta["x.ai/closeOutcome"] in {"closed", "notResident"})
                except Exception:
                    self.protocol_closed = False
        observation = Observation(0, "grok.acp.terminal", json_text({
            "selected": {"model": request.model, "effort": request.effort, "account": request.account_binding},
            "observed": {"model": self.observed_model, "effort": self.observed_effort, "account": None},
        }))
        observations = (observation,) if len(observation.payload_json.encode()) <= request.max_output_bytes else ()
        return ExecutionResult(request, "interrupted" if self._cancel.is_set() or self.stop_reason == "cancelled" else "incomplete", provider_status={"end_turn": "completed", "cancelled": "interrupted", "refusal": "failed"}.get(self.stop_reason),
                               actual_execution_path="direct-external-cli", native_result_text=self._text if self._text.strip() else None,
                               native_thread_id=self.session_id, observations=observations, execution_error=error,
                               capture_error=None if observations else "grok_evidence_limit",
                               protocol_closed=self.protocol_closed, cleanup_error="grok_process_settlement_unavailable")


def _require_live_grok_policy(request: ExecutionRequest) -> None:
    # ACP clientCapabilities and denial callbacks do not constrain Grok's own
    # internal tools. No qualified read-only enforcement/account binding exists.
    # This is intentionally not an activation flag or caller-supplied assertion.
    raise GrokAcpError("grok_read_only_enforcement_unavailable")


class GrokAcpAdapter:
    """Dormant executor over the existing ProcessRunner; no routing activation.

    Borrowed runner/capture ownership stays with the caller. There is no default
    launch authority, account discovery, parser premise or environment inheritance.
    Permission rejection is NOT an OS sandbox for Grok's internal tools.
    """

    def __init__(self, *, owner, process_request, auth_method, assert_current=None, output_context=None):
        self.owner = owner
        self.process_request = process_request
        self.auth_method = auth_method
        self.assert_current = assert_current
        self.output_context = output_context
        self.process_result = self.execution_result = None
        self._request = None
        self._lock = threading.Lock()
        self.exchange = GrokAcpExchange(auth_method=auth_method, assert_current=assert_current)

    async def execute(self, request):
        if self.assert_current is None:
            raise GrokAcpError("grok_execution_unavailable")
        from process_supervision.process_runner import ProcessRunnerV1, ProcessRequestV1, GrokAcpProfileV1
        import provider_prompt
        selected = self.process_request
        if (type(self.owner) is not ProcessRunnerV1 or type(selected) is not ProcessRequestV1
            or not callable(self.assert_current) or inspect.iscoroutinefunction(self.assert_current)
            or not isinstance(self.output_context, provider_prompt.ProviderOutputContext)
            or not isinstance(self.auth_method, str) or not self.auth_method
            or request.provider != "grok" or selected.cwd != request.cwd
            or selected.request_id != request.run_id
            or selected.argv != GrokAcpProfileV1.build_argv(selected.resolved_executable, request.model)
            or selected.windows_argv_profile_id != "native-parser-contract-v1"
            or selected.stdin_bytes is not None
            or selected.capture_policy.aggregate_persisted_limit > request.max_output_bytes):
            raise GrokAcpError("grok_owner_binding_mismatch")
        _require_live_grok_policy(request)
        with self._lock:
            if self._request is not None:
                raise GrokAcpError("operation_already_consumed")
            self._request = request
        task = asyncio.create_task(asyncio.to_thread(self._execute, request))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            await self.cancel(request.run_id)
            return await drain_owned(task)

    async def cancel(self, run_id):
        with self._lock:
            if self._request is None or self._request.run_id != run_id:
                return CancelReceipt(run_id, False, False, error="unknown_execution")
            if self.execution_result is not None:
                return CancelReceipt(run_id, False, False, error="already_finished")
            self.exchange.cancel()
        return CancelReceipt(run_id, True, self.exchange.cancel_acknowledged, native_thread_id=self.exchange.session_id)

    def _execute(self, request):
        from process_supervision.process_runner import ProcessDialogueV1, GrokAcpProfileV1, ProcessResultV1
        from .receiving import scan_execution_output
        try:
            decision = self.assert_current(request, "start")
        except Exception:
            raise GrokAcpError("grok_authority_denied") from None
        if decision is not None:
            raise GrokAcpError("grok_invalid_authority_callback")
        result = None
        def exchange(channel):
            nonlocal result
            result = self.exchange.run(request, channel)
        original_probe = self.process_request.cancellation_probe
        selected = replace(self.process_request, cancellation_probe=lambda: self.exchange._cancel.is_set() or bool(original_probe and original_probe()))
        try:
            process = self.owner.run(selected, dialogue=ProcessDialogueV1(GrokAcpProfileV1.protocol_id, exchange))
        except Exception:
            result = result or ExecutionResult(request, "incomplete", actual_execution_path="direct-external-cli")
            result = replace(result, execution_error=result.execution_error or "grok_process_owner_failed",
                             cleanup_error="grok_process_settlement_unavailable")
            self.execution_result = result
            scan_execution_output(result, self.output_context)
            return result
        self.process_result = process
        if type(process) is not ProcessResultV1:
            raise GrokAcpError("grok_invalid_process_result")
        if result is None:
            result = ExecutionResult(request, "incomplete", actual_execution_path="direct-external-cli",
                execution_error="grok_exchange_unavailable")
        settled = (process.resources_closed and process.tree.ownership_confirmed and process.tree.tree_empty
                   and process.tree.direct_reaped and process.tree.settlement_state == "EMPTY"
                   and process.tree.primary_thread_closed and process.tree.job_handle_closed and not process.cleanup_issues and not process.cleanup_uncertain
                   and not process.inheritance_poisoned)
        capture_error = "grok_capture_incomplete" if any(
            stream.truncated or stream.observed_bytes != stream.persisted_bytes for stream in (process.stdout, process.stderr)
        ) else result.capture_error
        process_error = "grok_process_failed" if process.failure_id or process.target_exit_code != 0 or not process.stdin.complete else None
        # No ACP account readback or durable Grok receiving owner is implemented.
        # A successful prompt/clean process is useful evidence, NOT a complete run.
        result = replace(result, cleanup_error=("grok_process_settlement_unavailable" if not settled else
                                        None if result.protocol_closed else "grok_protocol_cleanup_incomplete"),
                         capture_error=capture_error, execution_error=result.execution_error or process_error or "grok_account_readback_unavailable")
        self.execution_result = result  # Retain owner evidence even if export scanning rejects it.
        scan_execution_output(result, self.output_context)
        return result
