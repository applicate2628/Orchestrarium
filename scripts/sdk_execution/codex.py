"""Explicit read-only Codex SDK adapter, qualified only with an owned worker.

API evidence: openai/codex 83086188ae0614bd882818ff1aa23f3194962012,
published SDK/runtime 0.163.0, client.py and generated/v2_all.py verified
against the official PyPI wheel (there is no python-v0.163.0 Git tag).
This identifies inspected evidence, not a required release. Admission checks the
public API and observed behavior; actual versions are retained as provenance.
No import starts a provider. No default factory or live activation is provided.
Evidence here covers explicit operation readbacks and turn-scoped public events,
not every SDK-global diagnostic. The byte bound covers retained evidence, NOT private pipes or
queues. The process owner separately enforces operation memory and containment;
protocol closure alone never proves those resource guarantees.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import re
import threading
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from ._async import drain_owned
from .codex_tools import CodexMcpScope, CodexMcpScopeError, MAX_SERVERS
from .contracts import (
    CancelReceipt, ExecutionRequest, ExecutionResult, Observation, ReviewResult,
    json_text, review_schema, validate_review,
)


class CodexClientProtocol(Protocol):
    def start(self) -> None: ...
    def initialize(self) -> object: ...
    def account_read(self, params: dict[str, Any]) -> object: ...
    def thread_start(self, params: dict[str, Any]) -> object: ...
    def thread_resume(self, thread_id: str, params: dict[str, Any]) -> object: ...
    def thread_read(self, thread_id: str, include_turns: bool = False) -> object: ...
    def turn_start(self, thread_id: str, input_items: object, params: dict[str, Any]) -> object: ...
    def next_turn_notification(self, turn_id: str) -> object: ...
    def unregister_turn_notifications(self, turn_id: str) -> None: ...
    def turn_interrupt(self, thread_id: str, turn_id: str) -> object: ...
    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class ClientBinding:
    client: CodexClientProtocol
    sdk_version: str
    read_configuration: Callable[[dict[str, Any]], object] | None = None
    list_mcp_status: Callable[[dict[str, Any]], object] | None = None


class AdapterError(ValueError):
    """Stable error code, deliberately excluding raw exception/provider text."""


def _object(value: object) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        value = value.model_dump(by_alias=True, mode="json")
    if not isinstance(value, dict):
        raise AdapterError("invalid_sdk_payload")
    return value


def _identifier(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > 4096:
        raise AdapterError("missing_native_identity")
    return value


def _version_metadata(value: object, error: str) -> str:
    # Same provenance shape as the canonical sdkExecution ledger schema.
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/!+-]{0,127}", value) is None:
        raise AdapterError(error)
    return value


def _require_call(method: object, *args: object, **kwargs: object) -> None:
    if not callable(method):
        raise AdapterError("missing_sdk_api")
    if inspect.iscoroutinefunction(method) or inspect.isasyncgenfunction(method):
        raise AdapterError("incompatible_sdk_api")
    try:
        inspect.signature(method).bind(*args, **kwargs)
    except (TypeError, ValueError) as exc:
        raise AdapterError("incompatible_sdk_api") from exc


def _require_client_api(client: object, *, resume: bool) -> None:
    # Validate consumed call shapes, including cleanup, without invoking methods.
    calls = [
        ("start", (), {}), ("initialize", (), {}),
        ("account_read", ({"refreshToken": False},), {}),
        ("turn_interrupt", ("thread", "turn"), {}),
        ("unregister_turn_notifications", ("turn",), {}), ("close", (), {}),
    ]
    if resume:
        calls.extend([
            ("thread_resume", ("thread", {}), {}),
            ("thread_read", ("thread",), {"include_turns": True}),
        ])
    else:
        calls.extend([
            ("thread_start", ({},), {}),
            ("turn_start", ("thread", "input", {}), {}),
            ("next_turn_notification", ("turn",), {}),
        ])
    for name, args, kwargs in calls:
        _require_call(getattr(client, name, None), *args, **kwargs)


def _runtime_version(metadata: dict[str, Any]) -> str:
    server = metadata.get("serverInfo")
    if server is not None:
        if not isinstance(server, dict):
            raise AdapterError("invalid_runtime_version")
        return _version_metadata(server.get("version"), "invalid_runtime_version")
    # The public initialize response also exposes this documented version form.
    # Do not use it to hide a malformed serverInfo/version field.
    user_agent = metadata.get("userAgent")
    if not isinstance(user_agent, str) or not user_agent.strip():
        raise AdapterError("invalid_runtime_version")
    parts = user_agent.split("/", 1) if "/" in user_agent else user_agent.split(maxsplit=1)
    version = parts[1].split()[0] if len(parts) == 2 and parts[1].strip() else None
    return _version_metadata(version, "invalid_runtime_version")



def _usage(value: object) -> dict[str, Any]:
    usage = _object(value)
    required = {"inputTokens", "cachedInputTokens", "outputTokens", "reasoningOutputTokens", "totalTokens"}
    for period in ("last", "total"):
        breakdown = _object(usage.get(period))
        if not required.issubset(breakdown):
            raise AdapterError("invalid_usage")
        for name in required | ({"cacheWriteInputTokens"} if "cacheWriteInputTokens" in breakdown else set()):
            if type(breakdown[name]) is not int or breakdown[name] < 0:
                raise AdapterError("invalid_usage")
    window = usage.get("modelContextWindow")
    if window is not None and (type(window) is not int or window < 1):
        raise AdapterError("invalid_usage")
    return usage

def _official_client_binding(config: object, approval_handler: Callable[..., dict[str, Any]]) -> ClientBinding:
    """Worker-only construction seam; caller owns admission and environment.

    This helper does not launch. Production worker deliberately does not call it
    until containment, credential scope and bounded resource handling are qualified.
    Never use Codex() here: it launches immediately with a permissive handler.
    """
    from importlib.metadata import version
    from openai_codex.client import CodexClient, CodexConfig
    from openai_codex.generated.v2_all import ConfigReadResponse, ListMcpServerStatusResponse

    if not isinstance(config, CodexConfig) or config.codex_bin is None:
        raise AdapterError("explicit_runtime_required")
    if config.launch_args_override is not None:
        raise AdapterError("custom_launch_not_admitted")
    installed = _version_metadata(version("openai-codex"), "invalid_sdk_version")
    _require_call(CodexClient, config=config, approval_handler=approval_handler)
    _require_call(getattr(CodexClient, "request", None), None, "config/read", {},
                  response_model=ConfigReadResponse)
    client = CodexClient(config=config, approval_handler=approval_handler)
    return ClientBinding(client, installed,
        lambda params: client.request("config/read", params, response_model=ConfigReadResponse),
        lambda params: client.request("mcpServerStatus/list", params, response_model=ListMcpServerStatusResponse))


class CodexReviewAdapter:
    """One admitted operation, explicit dependencies, no automatic retry/replay.

    assert_current must consult existing authority and return None or raise.
    verify_account compares public account/read data with the separately admitted
    account binding, returns that nonsecret alias, and must never persist tokens.
    record retains each acquired readback/turn observation before interpretation in the existing
    owner's evidence sink. It is not a new ledger or implicit trace destination.
    """

    def __init__(
        self, *,
        client_factory: Callable[[Callable[..., dict[str, Any]]], ClientBinding],
        assert_current: Callable[[ExecutionRequest, str], None],
        verify_account: Callable[[ExecutionRequest, dict[str, Any]], str],
        record: Callable[[Observation], None],
        authorize_resume: Callable[[ExecutionRequest, str, str], None] | None = None,
        mcp_scope: CodexMcpScope = CodexMcpScope(()),
        bounded_startup_profile: bool = False,
    ) -> None:
        for callback in (client_factory, assert_current, verify_account, record):
            if not callable(callback):
                raise ValueError("explicit owner callbacks required")
        self._factory, self._assert_current = client_factory, assert_current
        self._verify_account, self._record = verify_account, record
        self._authorize_resume = authorize_resume
        if type(mcp_scope) is not CodexMcpScope:
            raise ValueError("explicit immutable Codex MCP scope required")
        self._mcp_scope = mcp_scope
        if type(bounded_startup_profile) is not bool:
            raise ValueError("explicit bounded startup profile boolean required")
        self._bounded_startup_profile = bounded_startup_profile
        self._cancel_lock = threading.Lock()
        self._lock = threading.RLock()
        self._request: ExecutionRequest | None = None
        self._client: CodexClientProtocol | None = None
        self._thread_id: str | None = None
        self._turn_id: str | None = None
        self._cancel_requested = False
        self._cancel_acknowledged = False
        self._approval_requested = False
        self._finished = False
        self._used = False

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return await self._run_async(request, None)

    async def reconcile(self, request: ExecutionRequest, *, thread_id: str, turn_id: str) -> ExecutionResult:
        """Read a bound prior turn, never replay an uncertain turn as new input."""
        thread_id, turn_id = _identifier(thread_id), _identifier(turn_id)
        if self._authorize_resume is None:
            raise AdapterError("resume_binding_owner_required")
        if self._authorize_resume(request, thread_id, turn_id) is not None:
            raise AdapterError("invalid_resume_authority_callback")
        return await self._run_async(request, (thread_id, turn_id))

    async def _run_async(self, request: ExecutionRequest, resume: tuple[str, str] | None) -> ExecutionResult:
        if not isinstance(request, ExecutionRequest) or request.provider != "codex":
            raise AdapterError("unsupported_provider")
        with self._lock:
            if self._used:
                raise AdapterError("operation_already_consumed")
            self._used, self._request = True, request
        task = asyncio.create_task(asyncio.to_thread(self._execute, request, resume))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            # Both operations remain owned even if the caller cancels repeatedly.
            # The process owner, not coroutine cancellation, enforces the deadline.
            interrupt = asyncio.create_task(self.cancel(request.run_id))
            await drain_owned(interrupt)
            return await drain_owned(task)

    def _authority(self, request: ExecutionRequest, effect: str) -> None:
        if self._assert_current(request, effect) is not None:
            raise AdapterError("invalid_authority_callback")
        with self._lock:
            if self._cancel_requested:
                raise AdapterError("cancelled_before_effect")

    def _deny_approval(self, method: str, params: dict[str, Any] | None) -> dict[str, Any]:
        # Called on SDK reader thread. Never issue a blocking RPC from here.
        with self._lock:
            self._approval_requested = True
        if method in {"item/commandExecution/requestApproval", "item/fileChange/requestApproval"}:
            return {"decision": "cancel"}
        if method == "item/permissions/requestApproval":
            return {"permissions": {}, "scope": "turn"}
        if method == "mcpServer/elicitation/request":
            return {"action": "cancel"}
        raise AdapterError("unsupported_server_request")

    async def cancel(self, run_id: str) -> CancelReceipt:
        return await asyncio.to_thread(self._cancel, run_id)

    def _cancel(self, run_id: str) -> CancelReceipt:
        with self._cancel_lock:
            return self._cancel_locked(run_id)

    def _cancel_locked(self, run_id: str) -> CancelReceipt:
        with self._lock:
            if self._request is None or self._request.run_id != run_id:
                return CancelReceipt(run_id, False, False, error="unknown_run")
            if self._finished:
                return CancelReceipt(run_id, False, False, self._thread_id, self._turn_id, "already_finished")
            self._cancel_requested = True
            client, thread_id, turn_id = self._client, self._thread_id, self._turn_id
            if self._cancel_acknowledged:
                return CancelReceipt(run_id, True, True, thread_id, turn_id)
        if client is None or thread_id is None or turn_id is None:
            return CancelReceipt(run_id, True, False, thread_id, turn_id)
        try:
            client.turn_interrupt(thread_id, turn_id)
        except Exception:
            return CancelReceipt(run_id, True, False, thread_id, turn_id, "interrupt_failed")
        with self._lock:
            self._cancel_acknowledged = True
        return CancelReceipt(run_id, True, True, thread_id, turn_id)

    def _profile(self, request: ExecutionRequest, response: dict[str, Any]) -> None:
        sandbox = response.get("sandbox")
        if (
            response.get("model") != request.model
            or response.get("modelProvider") != "openai"
            or response.get("reasoningEffort") != request.effort
            or response.get("cwd") != request.cwd
            or response.get("approvalPolicy") != "never"
            or response.get("approvalsReviewer") != "user"
            or not isinstance(sandbox, dict)
            or sandbox.get("type") != "readOnly"
            or sandbox.get("networkAccess") is not False
        ):
            raise AdapterError("observed_profile_mismatch")

    def _mcp_configuration(self, binding: ClientBinding, request: ExecutionRequest) -> dict[str, Any]:
        """Read native layered config without retaining credentials or endpoints."""
        self._authority(request, "query")
        config = _object(_object(binding.read_configuration(
            {"cwd": request.cwd, "includeLayers": False})).get("config"))
        features, agents = config.get("features"), config.get("agents")
        if (type(features) is not dict or type(agents) is not dict
                or any(features.get(name) is not False for name in ("plugins", "apps", "multi_agent_v2"))
                or agents.get("enabled") is not False):
            raise AdapterError("startup_tool_isolation_unverified")
        # Public config/read is layered/raw configuration consistency, not proof
        # of all normalized managed requirements or startup endpoint safety. The
        # Host must qualify those BEFORE native startup. Refuse missing/null as
        # well as incompatible values rather than guessing native defaults.
        if self._bounded_startup_profile and (
            features.get("memories") is not False
            or type(config.get("notify")) is not list or config["notify"] != []
            or config.get("model_provider") != "openai"
            or config.get("approvals_reviewer") != "user"
        ):
            raise AdapterError("bounded_startup_profile_unverified")
        servers = config.get("mcp_servers", {})
        if type(servers) is not dict or any(type(value) is not dict for value in servers.values()):
            raise AdapterError("invalid_mcp_configuration")
        # A selected subset may narrow existing controls, never erase a user's
        # disabled server, enabled-tools ceiling, or explicit denylist.
        for name, tools in self._mcp_scope.servers:
            server = servers.get(name)
            if type(server) is not dict or server.get("enabled", True) is not True:
                raise AdapterError("mcp_selection_not_eligible")
            for field in ("enabled_tools", "disabled_tools"):
                value = server.get(field)
                if value is not None and (type(value) is not list or any(type(tool) is not str for tool in value)):
                    raise AdapterError("invalid_mcp_configuration")
            enabled, disabled = server.get("enabled_tools"), server.get("disabled_tools") or []
            if (enabled is not None and not set(tools) <= set(enabled)) or set(tools) & set(disabled):
                raise AdapterError("mcp_selection_not_eligible")
        try:
            return self._mcp_scope.thread_overrides(tuple(servers))
        except CodexMcpScopeError:
            raise AdapterError("invalid_mcp_configuration") from None

    def _verify_mcp_inventory(self, binding: ClientBinding, request: ExecutionRequest) -> None:
        """Validate returned thread inventory and selected connections, not global data.

        Optional null fields follow the public schema. Pagination termination
        is the provider's assertion, not independent proof of exhaustive discovery.
        """
        def pages(server_name=None):
            rows, cursors, cursor = [], set(), None
            for _ in range(MAX_SERVERS + 1):
                params = {"threadId": self._thread_id, "detail": "toolsAndAuthOnly", "limit": MAX_SERVERS}
                if server_name is not None:
                    params["serverName"] = server_name
                if cursor is not None:
                    params["cursor"] = cursor
                self._authority(request, "query")
                response = _object(binding.list_mcp_status(params))
                data = response.get("data")
                if type(data) is not list or len(rows) + len(data) > MAX_SERVERS:
                    raise AdapterError("mcp_catalog_incomplete")
                rows.extend(data)
                cursor = response.get("nextCursor")
                if cursor is None:
                    return rows
                if (type(cursor) is not str or not cursor or len(cursor) > 4096
                        or cursor in cursors or not data):
                    raise AdapterError("mcp_catalog_incomplete")
                cursors.add(cursor)
            raise AdapterError("mcp_catalog_incomplete")

        try:
            self._mcp_scope.validate_inventory(pages())
            live = []
            for name, _tools in self._mcp_scope.servers:
                rows = pages(name)
                if len(rows) != 1 or type(rows[0]) is not dict or rows[0].get("name") != name:
                    raise AdapterError("mcp_catalog_incomplete")
                live.extend(rows)
            self._mcp_scope.validate_inventory(live)
        except CodexMcpScopeError:
            raise AdapterError("mcp_scope_mismatch") from None

    def _execute(self, request: ExecutionRequest, resume: tuple[str, str] | None) -> ExecutionResult:
        observations: list[Observation] = []
        total_bytes = 0
        status, review, usage = "incomplete", None, None
        execution_error = capture_error = cleanup_error = metadata_json = None
        protocol_closed = False
        client = None
        terminal_seen = False
        provider_status = None
        final_items: dict[str, dict[str, Any]] = {}
        pending_items: set[str] = set()

        def capture(kind: str, payload: dict[str, Any]) -> None:
            nonlocal total_bytes, capture_error
            encoded = json_text(payload)
            size = len(encoded.encode("utf-8"))
            if len(observations) >= request.max_events or total_bytes + size > request.max_output_bytes:
                capture_error = "observation_limit_exceeded"
                raise AdapterError(capture_error)
            observation = Observation(len(observations), kind, encoded)
            observations.append(observation)
            total_bytes += size
            try:
                self._record(observation)
            except Exception as exc:
                capture_error = "evidence_sink_failed"
                raise AdapterError(capture_error) from exc

        def accept_item(item: dict[str, Any]) -> None:
            item_id = _identifier(item.get("id"))
            if item_id in final_items:
                if final_items[item_id] != item:
                    raise AdapterError("contradictory_duplicate_item")
                return
            if item.get("type") == "fileChange":
                raise AdapterError("read_only_file_change")
            if item.get("type") == "commandExecution":
                # A completed event/history item must describe a terminal command,
                # not merely arrive inside a terminal protocol envelope.
                if item.get("status") not in ("completed", "failed", "declined"):
                    raise AdapterError("invalid_terminal_command_status")
                if item.get("status") == "completed" and type(item.get("exitCode")) is not int:
                    raise AdapterError("missing_command_exit_code")
            final_items[item_id] = item
            pending_items.discard(item_id)

        def terminal(payload: dict[str, Any]) -> None:
            nonlocal status, terminal_seen, provider_status
            if payload.get("threadId") != self._thread_id:
                raise AdapterError("native_thread_mismatch")
            turn = _object(payload.get("turn"))
            if turn.get("id") != self._turn_id:
                raise AdapterError("native_turn_mismatch")
            status = turn.get("status")
            if status not in {"completed", "failed", "interrupted"}:
                status = "incomplete"
                raise AdapterError("invalid_terminal_status")
            provider_status = status
            terminal_seen = True
            view = turn.get("itemsView")
            items = turn.get("items")
            if not isinstance(items, list):
                raise AdapterError("invalid_terminal_items")
            if resume:
                if view != "full":
                    raise AdapterError("partial_history_items")
                for item in items:
                    accept_item(_object(item))
            else:
                # Inspected producer emits summary(last agent message) or notLoaded,
                # not the full item list. Full evidence is the captured item stream.
                # bespoke_event_handling.rs:1332-1344 at the evidence commit above.
                if view not in {"full", "summary", "notLoaded"}:
                    raise AdapterError("invalid_terminal_items_view")
                if view == "notLoaded" and items:
                    raise AdapterError("contradictory_terminal_items")
                terminal_ids: set[str] = set()
                for value in items:
                    item = _object(value)
                    item_id = _identifier(item.get("id"))
                    terminal_ids.add(item_id)
                    if item_id not in final_items:
                        raise AdapterError("missing_completed_item")
                    if final_items[item_id] != item:
                        raise AdapterError("contradictory_terminal_item")
                if view == "full" and terminal_ids != final_items.keys():
                    raise AdapterError("contradictory_terminal_items")
                if status == "completed" and pending_items:
                    raise AdapterError("incomplete_item_lifecycle")
            if status == "failed":
                raise AdapterError("provider_turn_failed")
            if status == "completed" and turn.get("error") is not None:
                raise AdapterError("contradictory_terminal_error")

        try:
            self._authority(request, "start")
            binding = self._factory(self._deny_approval)
            client = binding.client
            self._client = client
            _version_metadata(binding.sdk_version, "invalid_sdk_version")
            _require_client_api(client, resume=resume is not None)
            _require_call(binding.read_configuration, {})
            _require_call(binding.list_mcp_status, {})
            self._authority(request, "client_start")
            client.start()
            initialized = _object(client.initialize())
            capture("initialize", initialized)
            runtime = _runtime_version(initialized)
            account = _object(client.account_read({"refreshToken": False}))
            if self._verify_account(request, account) != request.account_binding:
                raise AdapterError("account_binding_mismatch")
            capture("account/verified", {"accountBinding": request.account_binding})
            mcp_configuration = self._mcp_configuration(binding, request)
            settings = {
                "approvalPolicy": "never", "approvalsReviewer": "user",
                "sandbox": "read-only", "cwd": request.cwd, "model": request.model,
                "modelProvider": "openai", "config": {"model_reasoning_effort": request.effort, **mcp_configuration},
            }
            self._authority(request, "resume" if resume else "thread_start")
            started = _object(client.thread_resume(resume[0], settings) if resume else client.thread_start(settings))
            capture("thread/resume" if resume else "thread/start", started)
            self._thread_id = _identifier(_object(started.get("thread")).get("id"))
            if resume and self._thread_id != resume[0]:
                raise AdapterError("native_thread_mismatch")
            self._profile(request, started)
            self._verify_mcp_inventory(binding, request)
            capture("mcp/verified", self._mcp_scope.to_dict())
            metadata_json = json_text({
                "schemaVersion": 1, "adapter": "openai-codex", "sdkVersion": binding.sdk_version,
                "runtimeVersion": runtime, "model": request.model, "effort": request.effort,
                "sandboxMode": "read-only", "approvalPolicy": "deny_all", "accountBinding": request.account_binding,
            })
            if resume:
                self._turn_id = resume[1]
                self._authority(request, "reconcile")
                history = _object(client.thread_read(self._thread_id, include_turns=True))
                capture("thread/read", history)
                thread = _object(history.get("thread"))
                if thread.get("id") != self._thread_id:
                    raise AdapterError("incomplete_history")
                turns = [t for t in thread.get("turns", []) if isinstance(t, dict) and t.get("id") == self._turn_id]
                if len(turns) != 1:
                    raise AdapterError("prior_turn_not_reconciled")
                terminal({"threadId": self._thread_id, "turn": turns[0]})
            else:
                self._authority(request, "turn_start")
                response = _object(client.turn_start(self._thread_id, request.prompt, {
                    "approvalPolicy": "never", "approvalsReviewer": "user",
                    "cwd": request.cwd, "model": request.model, "effort": request.effort,
                    "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
                    "outputSchema": review_schema(request),
                }))
                # Public turn_start preserves events received before this response.
                self._turn_id = _identifier(_object(response.get("turn")).get("id"))
                capture("turn/start", response)
                if self._cancel_requested:
                    self._cancel(request.run_id)
                while not terminal_seen:
                    event = client.next_turn_notification(self._turn_id)
                    method = event.get("method") if isinstance(event, dict) else getattr(event, "method", None)
                    payload = event.get("payload") if isinstance(event, dict) else getattr(event, "payload", None)
                    if not isinstance(method, str):
                        raise AdapterError("invalid_notification")
                    # The SDK wraps malformed known and unknown events in its public
                    # UnknownNotification. Preserve those bytes, never infer success.
                    if hasattr(payload, "params"):
                        capture(method, _object(payload.params))
                        if method in {"turn/started", "turn/completed", "item/started", "item/completed", "thread/tokenUsage/updated", "model/rerouted"}:
                            raise AdapterError("unknown_or_invalid_notification")
                        continue
                    payload = _object(payload)
                    capture(method, payload)
                    if payload.get("threadId") != self._thread_id:
                        raise AdapterError("native_thread_mismatch")
                    if method == "turn/started":
                        if _object(payload.get("turn")).get("id") != self._turn_id:
                            raise AdapterError("native_turn_mismatch")
                    elif method != "turn/completed" and payload.get("turnId") != self._turn_id:
                        raise AdapterError("native_turn_mismatch")
                    if method == "turn/completed":
                        terminal(payload)
                    elif method == "item/started":
                        item_id = _identifier(_object(payload.get("item")).get("id"))
                        if item_id not in final_items:
                            pending_items.add(item_id)
                    elif method == "item/completed":
                        accept_item(_object(payload.get("item")))
                    elif method == "thread/tokenUsage/updated":
                        usage = _usage(payload.get("tokenUsage"))
                    elif method == "model/rerouted":
                        # This is identity evidence, not optional progress. Preserve
                        # the event, then hold any unadmitted model transition.
                        if payload.get("fromModel") != request.model or payload.get("toModel") != request.model:
                            raise AdapterError("observed_model_drift")
                    # Other public events stay captured evidence. They are not
                    # completion, command-exit, profile or permission authority.
            if self._approval_requested:
                raise AdapterError("unexpected_approval_request")
            if status == "completed":
                # Match the official SDK's final-message selection, including its
                # supported phase-less compatibility form; no prose verdict parser.
                messages = [item for item in reversed(tuple(final_items.values())) if item.get("type") == "agentMessage"]
                selected = next((item for item in messages if item.get("phase") == "final_answer"), None)
                if selected is None:
                    selected = next((item for item in messages if item.get("phase") is None), None)
                if selected is None or not isinstance(selected.get("text"), str):
                    raise AdapterError("missing_final_answer")
                review = validate_review(selected["text"], request=request)
        except Exception as exc:
            execution_error = str(exc) if isinstance(exc, AdapterError) else "execution_or_interpretation_failed"
            if execution_error == "cancelled_before_effect":
                status, execution_error = "interrupted", None
        finally:
            if client is not None:
                errors = []
                # History inspection did not start the prior turn. A failed
                # read must not implicitly cancel it; explicit caller cancel
                # still uses the separately bound cancellation operation.
                if resume is None and self._turn_id and not terminal_seen:
                    receipt = self._cancel(request.run_id)
                    if receipt.error:
                        errors.append(receipt.error)
                # Finish an in-flight native interrupt before closing its client.
                # Mark finished under the same existing cancellation lock so a
                # delayed caller cannot issue a new RPC after protocol close.
                with self._cancel_lock:
                    if self._turn_id:
                        try:
                            client.unregister_turn_notifications(self._turn_id)
                        except Exception:
                            errors.append("notification_cleanup_failed")
                    try:
                        _require_call(getattr(client, "close", None))
                        client.close()
                        protocol_closed = True
                    except Exception:
                        errors.append("protocol_close_failed")
                    with self._lock:
                        self._finished = True
                cleanup_error = ",".join(errors) if errors else None
            else:
                with self._lock:
                    self._finished = True
        if execution_error or capture_error or cleanup_error:
            status = "incomplete" if provider_status != "failed" else "failed"
        return ExecutionResult(
            request=request, status=status, provider_status=provider_status, native_thread_id=self._thread_id, native_turn_id=self._turn_id,
            sdk_execution_json=metadata_json, observations=tuple(observations), review=review,
            usage_json=json_text(usage) if usage is not None else None,
            execution_error=execution_error, capture_error=capture_error, cleanup_error=cleanup_error,
            protocol_closed=protocol_closed,
        )
