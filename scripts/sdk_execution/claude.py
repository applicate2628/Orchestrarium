"""One read-only review through the public Claude Agent SDK, never a live default.

Public API reference: anthropics/claude-agent-sdk-python
163f50ed56fa8c3fd9346148b6e56e7696794b58 (v0.2.173, bundled CLI 2.1.309).
See types.py (options, hooks, messages) and client.py (session methods).
This reference is evidence, not an installed-version requirement. Admission uses
the required public interfaces and observed execution contract, not a release pin.

The selected tool set is this review operation's scope, not a universal SDK
policy. Tool permissions are NOT OS containment. The creator's process owner
must isolate environment/account/trace destinations and settle descendants.
options.env overlays the inherited environment; it cannot establish isolation.
Module import performs no provider import, activation, retry or resume. The fixed
factory below is called only by an explicitly selected, contained worker; native
platform qualification and live-provider permission remain separate requirements.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass, fields, is_dataclass
from pathlib import Path
import inspect
import os
import re
from typing import Any, Protocol
from uuid import uuid4

from ._async import drain_owned
from .contracts import (
    CancelReceipt, ExecutionRequest, ExecutionResult, Observation, json_text,
    review_schema, validate_review,
)

READ_TOOLS = ("Read", "Glob", "Grep")
# Native JSON-schema delivery uses this synthetic output-only tool, not another
# filesystem permission. Official SDK changelog 0.3.260 (CLI 2.1.260) documents it:
# anthropics/claude-agent-sdk-typescript, 82e441ed7669834e2f33e436e4e1c3a4f660a4ca.
OUTPUT_TOOL = "StructuredOutput"
OBSERVED_TOOLS = (*READ_TOOLS, OUTPUT_TOOL)


class AdapterError(ValueError):
    """Stable error code; raw exceptions may contain credentials/provider text."""


@dataclass(frozen=True, slots=True)
class ClaudeRuntimeSelection:
    """Explicit nonsecret Claude selection, committed by the common runtime owner."""

    executable: str
    executable_sha256: str
    config_dir: str
    auth_mode: str
    instructions: str
    prompts_dir: str
    work_item: str
    ledger_max_events: int
    ledger_max_bytes: int
    job_memory_limit_bytes: int
    expected_launch_sha256: str | None = None

    def __post_init__(self) -> None:
        for name in ("executable", "config_dir", "prompts_dir", "work_item"):
            value = getattr(self, name)
            if type(value) is not str or not value or not Path(value).is_absolute():
                raise AdapterError("explicit_absolute_runtime_paths_required")
        for name in ("executable_sha256", "expected_launch_sha256"):
            value = getattr(self, name)
            if value is None and name == "expected_launch_sha256":
                continue
            if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
                raise AdapterError("explicit_runtime_digest_required")
        for name in ("ledger_max_events", "ledger_max_bytes", "job_memory_limit_bytes"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise AdapterError("explicit_positive_resource_budget_required")
        if type(self.auth_mode) is not str or not self.auth_mode:
            raise AdapterError("explicit_auth_mode_required")
        if type(self.instructions) is not str or not self.instructions.strip():
            raise AdapterError("missing_governance_instructions")
        import provider_prompt as owner
        owner._bounded_strict_utf8_snapshot(self.instructions.encode("utf-8"), "instructions")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: object) -> ClaudeRuntimeSelection:
        if type(value) is not dict or set(value) != set(cls.__dataclass_fields__):
            raise AdapterError("invalid_runtime_selection_fields")
        return cls(**value)


class ClaudeClientProtocol(Protocol):
    async def connect(self) -> None: ...
    async def get_server_info(self) -> dict[str, Any] | None: ...
    async def query(self, prompt: AsyncIterable[dict[str, Any]], session_id: str = "default") -> None: ...
    def receive_response(self) -> AsyncIterator[object]: ...
    async def interrupt(self) -> None: ...
    async def disconnect(self) -> None: ...


@dataclass(frozen=True, slots=True)
class ClientBinding:
    client: ClaudeClientProtocol
    sdk_version: str


def _version_metadata(value: object, kind: str) -> str:
    """Retain bounded version provenance without treating it as compatibility."""
    if type(value) is not str or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/!+-]{0,127}", value) is None:
        raise AdapterError("invalid_" + kind + "_version_metadata")
    return value


def _require_call(function: object, *args: Any, asynchronous: bool = False, **kwargs: Any) -> None:
    """Check the consumed public call shape without invoking provider code."""
    if not callable(function) or (asynchronous and not inspect.iscoroutinefunction(function)):
        raise AdapterError("missing_required_sdk_api")
    try:
        inspect.signature(function).bind(*args, **kwargs)
    except (TypeError, ValueError) as error:
        raise AdapterError("incompatible_sdk_api") from error


def _require_client_api(client: object, *, unbound: bool = False) -> None:
    prefix = (object(),) if unbound else ()
    for name in ("connect", "get_server_info", "interrupt", "disconnect"):
        _require_call(getattr(client, name, None), *prefix, asynchronous=True)
    _require_call(getattr(client, "query", None), *prefix, object(), session_id="probe", asynchronous=True)
    receive = getattr(client, "receive_response", None)
    _require_call(receive, *prefix)
    # async-for consumes the iterator directly, not a coroutine yielding one.
    # A synchronous iterator factory remains compatible with this public shape.
    if inspect.iscoroutinefunction(receive):
        raise AdapterError("incompatible_sdk_api")


def _public_value(value: object) -> Any:
    """Serialize public dataclass values, preserving block/message discriminants."""
    if is_dataclass(value) and not isinstance(value, type):
        return {"type": type(value).__name__, **{
            field.name: _public_value(getattr(value, field.name)) for field in fields(value)
        }}
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise AdapterError("invalid_sdk_payload")
        return {key: _public_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_public_value(item) for item in value]
    if value is None or type(value) in {str, int, float, bool}:
        return value
    raise AdapterError("invalid_sdk_payload")


def _official_client_binding(options: dict[str, Any], *, cli_path: str) -> ClientBinding:
    """Lazy construction seam for the explicitly selected worker. Does not connect.

    The caller must create the worker in qualified containment with the admitted
    environment before calling this function. No custom transport bypass is exposed.
    """
    from importlib.metadata import version

    installed = _version_metadata(version("claude-agent-sdk"), "sdk")
    if not isinstance(cli_path, str) or not cli_path.strip():
        raise AdapterError("explicit_runtime_required")
    try:
        from claude_agent_sdk import (
            ClaudeAgentOptions, ClaudeSDKClient, HookMatcher, PermissionResultDeny,
        )
    except ImportError as error:
        raise AdapterError("missing_required_sdk_api") from error

    values = dict(options)
    deny = values["can_use_tool"]
    # Validate every constructor and client method before constructing a client;
    # a newer package must not silently omit permission, isolation or hook options.
    _require_call(ClaudeAgentOptions, **(values | {"cli_path": cli_path}))
    _require_call(ClaudeSDKClient, options=object())
    _require_call(PermissionResultDeny, behavior="deny", message="probe", interrupt=True)
    for matchers in values["hooks"].values():
        for matcher in matchers:
            _require_call(HookMatcher, **matcher)
    _require_client_api(ClaudeSDKClient, unbound=True)

    async def deny_permission(name: str, arguments: dict[str, Any], context: object) -> object:
        return PermissionResultDeny(**(await deny(name, arguments, context)))

    values["can_use_tool"] = deny_permission
    values["hooks"] = {
        name: [HookMatcher(**matcher) for matcher in matchers]
        for name, matchers in values["hooks"].items()
    }
    values["cli_path"] = cli_path
    return ClientBinding(ClaudeSDKClient(options=ClaudeAgentOptions(**values)), installed)


def create_claude_adapter(request: ExecutionRequest, sink: Any, selection: ClaudeRuntimeSelection):
    """Fixed worker factory after creator-owned Job verification; never call in the parent."""
    from .runtime import assert_current_launch, prepare_environment

    if request.provider != "claude" or type(selection) is not ClaudeRuntimeSelection:
        raise AdapterError("claude_request_required")
    assert_current_launch(request, selection, "worker_factory")
    environment, _context = prepare_environment(selection, dict(os.environ))
    # The public SDK overlays env on ambient values. Clean this already-contained
    # one-operation worker using the existing auth owner before SDK construction.
    os.environ.clear()
    os.environ.update(environment)

    async def current(value: ExecutionRequest, effect: str) -> None:
        if value != request:
            raise AdapterError("worker_request_binding_mismatch")
        assert_current_launch(value, selection, effect)
        await sink.authorize(value, effect)

    async def tool(value: ExecutionRequest, name: str, arguments: dict[str, Any]) -> None:
        if value != request:
            raise AdapterError("worker_request_binding_mismatch")
        assert_current_launch(value, selection, "tool")
        await sink.authorize(value, "tool", {"kind": "tool", "name": name, "arguments": arguments})

    async def account(value: ExecutionRequest, evidence: dict[str, Any]) -> str:
        if value != request:
            raise AdapterError("worker_request_binding_mismatch")
        assert_current_launch(value, selection, "account")
        await sink.authorize(value, "account", {"kind": "account", "evidence": evidence})
        # The parent account owner, not apiKeySource/config presence, established
        # this exact admitted nonsecret alias before sending its one-use grant.
        return request.account_binding

    return ClaudeReviewAdapter(
        client_factory=lambda options: _official_client_binding(options, cli_path=selection.executable),
        assert_current=current, authorize_tool=tool,
        load_instructions=lambda _value: selection.instructions,
        verify_account=account, record=sink.record,
    )


@contextmanager
def _owned_instruction_file(instructions: str, cleanup_errors: list[str]):
    """Reuse the existing private capture owner, including partial setup cleanup.

    This is instruction transport, not another policy or temporary-file owner.
    The admitted worker environment selects the existing CLAUDE_PROMPTS_DIR.
    """
    import provider_prompt as owner

    payload = owner._bounded_strict_utf8_snapshot(instructions.encode("utf-8"), "instructions")
    lifecycle = owner.RunCaptureLifecycle()
    initialized = False
    try:
        # Retain the owner before acquisition so even partial setup is released.
        lifecycle._acquire("claude", "sdk-instructions")
        lifecycle.initialize(payload)
        initialized = True
        if owner._external_prompt_file_snapshot(lifecycle.prompt_path) != payload:
            raise AdapterError("instruction_snapshot_mismatch")
        yield str(lifecycle.prompt_path)
    finally:
        try:
            outcome = lifecycle.cleanup() if initialized else lifecycle._release_owned()
            if not outcome.clean:
                cleanup_errors.append("instruction_file_cleanup_failed")
        except Exception:
            cleanup_errors.append("instruction_file_cleanup_failed")


class ClaudeReviewAdapter:
    """Single admitted operation with explicit existing-owner dependencies.

    Awaited assert_current rechecks current admission/account/budget/scope; None means that
    the owner accepted, any other return or exception stops the effect. authorize_tool
    checks the exact tool arguments/path under that owner's current data permissions.
    Policy, tool and account callbacks all await the parent owner on the SDK loop;
    the Codex blocking-thread bridge must not be used here.
    load_instructions supplies current common governance AND Claude-specific rules;
    filesystem settings are disabled, so this payload must not omit project rules.
    The existing private capture owner transports it in an append-only system
    prompt file while preserving the native claude_code system-prompt preset.

    The first slice requires the selection owner to resolve/admit a concrete model
    identifier before building ExecutionRequest. Existing CLI profiles such as
    "opus"/"sonnet" are aliases, not canonical observed IDs. This adapter does not
    guess their mapping or claim alias-profile parity. The SDK's canonicalModel
    usage field is a pricing lookup identity, not an alias-authorization owner.

    verify_account runs before connection and again on public initialization data.
    It must establish the admitted account/billing lane using the existing owner's
    evidence, not infer account identity from apiKeySource. The SDK has no dedicated
    public account/read API. Only the verified nonsecret binding is recorded here.
    record is the existing admitted evidence sink, not a new ledger/trace destination.
    """

    def __init__(
        self, *, client_factory: Callable[[dict[str, Any]], ClientBinding],
        assert_current: Callable[[ExecutionRequest, str], Awaitable[None]],
        authorize_tool: Callable[[ExecutionRequest, str, dict[str, Any]], Awaitable[None]],
        load_instructions: Callable[[ExecutionRequest], str],
        verify_account: Callable[[ExecutionRequest, dict[str, Any]], Awaitable[str]],
        record: Callable[[Observation], Awaitable[None]],
    ) -> None:
        if any(not callable(value) for value in (
            client_factory, assert_current, authorize_tool, load_instructions, verify_account, record,
        )):
            raise ValueError("explicit owner callbacks required")
        self._factory, self._assert_current = client_factory, assert_current
        self._authorize_tool, self._instructions = authorize_tool, load_instructions
        self._verify_account, self._record = verify_account, record
        self._request: ExecutionRequest | None = None
        self._client: ClaudeClientProtocol | None = None
        self._session_id: str | None = None
        self._prompt_id: str | None = None
        self._connected = self._query_sent = self._finished = self._used = False
        self._cancel_requested = self._cancel_acknowledged = False
        self._cancel_lock = asyncio.Lock()
        self._capture_lock = asyncio.Lock()
        self._observations: list[Observation] = []
        self._bytes = 0
        self._capture_error: str | None = None
        self._hook_error: str | None = None
        self._observed_effort: str | None = None
        self._observed_prompt = False
        self._tools: dict[str, tuple[str, dict[str, Any]] | None] = {}
        self._tool_results: set[str] = set()

    async def _authority(self, effect: str) -> None:
        if self._cancel_requested:
            raise AdapterError("cancelled_before_effect")
        if await self._assert_current(self._request, effect) is not None:
            raise AdapterError("invalid_authority_callback")
        if self._cancel_requested:
            raise AdapterError("cancelled_before_effect")

    async def _capture(self, kind: str, data: dict[str, Any]) -> None:
        # SDK hook callbacks may run concurrently. Assign sequence and persist
        # under one lock, with backpressure rather than a second queue.
        async with self._capture_lock:
            if self._capture_error:
                raise AdapterError(self._capture_error)
            encoded = json_text(data)
            if (len(self._observations) >= self._request.max_events
                or self._bytes + len(encoded.encode("utf-8")) > self._request.max_output_bytes):
                self._capture_error = "observation_limit_exceeded"
                raise AdapterError(self._capture_error)
            observation = Observation(len(self._observations), kind, encoded)
            self._observations.append(observation)
            self._bytes += len(encoded.encode("utf-8"))
            try:
                await self._record(observation)
            except Exception as exc:
                self._capture_error = "evidence_persistence_failed"
                raise AdapterError(self._capture_error) from exc

    async def _account(self, phase: str, data: dict[str, Any]) -> None:
        if await self._verify_account(self._request, {"phase": phase, "data": data}) != self._request.account_binding:
            raise AdapterError("account_binding_mismatch")

    async def _deny_permission(self, _name: str, _arguments: dict[str, Any], _context: object) -> dict[str, Any]:
        self._hook_error = self._hook_error or "unexpected_permission_request"
        return {"behavior": "deny", "message": "Not admitted for this read-only review.", "interrupt": True}

    async def _hook(self, data: dict[str, Any], tool_use_id: str | None, _context: object) -> dict[str, Any]:
        event = data.get("hook_event_name") if isinstance(data, dict) else None
        try:
            if self._finished or self._hook_error:
                raise AdapterError(self._hook_error or "late_hook")
            if not isinstance(data, dict):
                raise AdapterError("invalid_hook")
            # Do not record transcript paths/account material; retain the supplied
            # tool arguments/outcomes in the owner's already-admitted evidence sink.
            payload = {key: value for key, value in data.items() if key != "transcript_path"}
            await self._capture("hook/" + str(event), _public_value(payload))
            if data.get("session_id") != self._session_id or data.get("cwd") != self._request.cwd:
                raise AdapterError("native_session_mismatch")
            if data.get("permission_mode") not in (None, "default"):
                raise AdapterError("observed_permission_mismatch")
            if data.get("prompt_id") is not None:
                if data["prompt_id"] != self._prompt_id:
                    raise AdapterError("native_prompt_mismatch")
                self._observed_prompt = True
            if data.get("effort") is not None:
                if not isinstance(data["effort"], dict) or data["effort"].get("level") != self._request.effort:
                    raise AdapterError("observed_effort_mismatch")
                self._observed_effort = data["effort"]["level"]
            if data.get("agent_id") is not None:
                raise AdapterError("unadmitted_subagent")
            if event == "Stop":
                if data.get("background_tasks") or data.get("session_crons"):
                    raise AdapterError("unsettled_session_work")
                return {}
            if event not in {"PreToolUse", "PostToolUse", "PostToolUseFailure"}:
                raise AdapterError("unsupported_hook")
            name, arguments, call_id = data.get("tool_name"), data.get("tool_input"), data.get("tool_use_id")
            if (name not in OBSERVED_TOOLS or not isinstance(arguments, dict)
                or not isinstance(call_id, str) or not call_id
                or (tool_use_id is not None and call_id != tool_use_id)):
                raise AdapterError("unadmitted_tool_call")
            if event == "PreToolUse":
                if call_id in self._tools:
                    raise AdapterError("duplicate_tool_call")
                # Reserve before either authority await. A pending call cannot
                # admit a duplicate or be paired with a premature post result.
                self._tools[call_id] = None
                await self._authority("tool")
                if name == OUTPUT_TOOL:
                    validate_review(arguments, request=self._request)
                if await self._authorize_tool(self._request, name, arguments) is not None:
                    raise AdapterError("invalid_tool_authority_callback")
                if self._cancel_requested:
                    raise AdapterError("cancelled_before_effect")
                if self._finished or self._hook_error:
                    raise AdapterError(self._hook_error or "late_hook")
                self._tools[call_id] = (name, arguments)
                return {"hookSpecificOutput": {
                    "hookEventName": "PreToolUse", "permissionDecision": "allow",
                }}
            if self._tools.get(call_id) != (name, arguments) or call_id in self._tool_results:
                raise AdapterError("unknown_or_duplicate_tool_result")
            self._tool_results.add(call_id)
            if event == "PostToolUseFailure":
                if not isinstance(data.get("error"), str) or not data["error"]:
                    raise AdapterError("missing_tool_error")
                # A paired failed read (for example, a missing path) is evidence,
                # not a policy denial or an automatic veto of the final review.
                return {}
            if "tool_response" not in data:
                raise AdapterError("missing_tool_output")
            return {}
        except Exception as exc:
            self._hook_error = self._hook_error or (str(exc) if isinstance(exc, AdapterError) else "tool_authority_failed")
            if event == "PreToolUse":
                return {"hookSpecificOutput": {
                    "hookEventName": "PreToolUse", "permissionDecision": "deny",
                    "permissionDecisionReason": self._hook_error,
                }, "continue_": False, "stopReason": self._hook_error}
            return {"continue_": False, "stopReason": self._hook_error}

    def _options(self, instruction_path: str) -> dict[str, Any]:
        return {
            "model": self._request.model, "effort": self._request.effort,
            "cwd": self._request.cwd, "session_id": self._session_id,
            "system_prompt": {"type": "preset", "preset": "claude_code", "snapshot": False},
            # The public SDK extra_args seam passes this documented native flag.
            # Claude Code CHANGELOG 2.1.281 (65823ec0034ed0aa0266bc43903fefd3ff94a327)
            # prescribes file transport for large prompts. A custom/file system
            # prompt would replace, rather than append to, the native defaults.
            "extra_args": {"append-system-prompt-file": instruction_path},
            "tools": list(READ_TOOLS), "allowed_tools": [], "permission_mode": "default",
            "disallowed_tools": ["Bash", "Write", "Edit", "NotebookEdit", "Agent", "Task", "WebFetch", "WebSearch"],
            "mcp_servers": {}, "strict_mcp_config": True, "setting_sources": [],
            "skills": [], "plugins": [], "agents": {}, "add_dirs": [],
            "fallback_model": None, "continue_conversation": False, "resume": None,
            "verbatim_prompts": True, "include_partial_messages": True,
            "max_buffer_size": self._request.max_output_bytes,
            "output_format": {"type": "json_schema", "schema": review_schema(self._request)},
            "can_use_tool": self._deny_permission,
            "hooks": {event: [{"hooks": [self._hook]}] for event in (
                "PreToolUse", "PostToolUse", "PostToolUseFailure", "Stop",
            )},
        }

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        if not isinstance(request, ExecutionRequest) or request.provider != "claude":
            raise AdapterError("unsupported_provider")
        if self._used:
            raise AdapterError("operation_already_consumed")
        self._used, self._request = True, request
        self._session_id, self._prompt_id = str(uuid4()), str(uuid4())
        task = asyncio.create_task(self._execute())
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            # Repeated caller cancellation must not cancel either owned task.
            # Coroutine cancellation is not process settlement; the existing
            # process owner enforces the deadline if the SDK cannot return.
            interrupt = asyncio.create_task(self.cancel(request.run_id))
            await drain_owned(interrupt)
            return await drain_owned(task)

    async def cancel(self, run_id: str) -> CancelReceipt:
        if self._request is None or run_id != self._request.run_id:
            return CancelReceipt(run_id, False, False, error="unknown_run")
        if self._finished:
            return CancelReceipt(run_id, False, False, self._session_id, self._prompt_id, "already_finished")
        self._cancel_requested = True
        async with self._cancel_lock:
            if self._finished:
                return CancelReceipt(run_id, False, False, self._session_id, self._prompt_id, "already_finished")
            if self._connected and self._query_sent and not self._cancel_acknowledged:
                try:
                    await self._client.interrupt()
                    self._cancel_acknowledged = True
                except Exception:
                    return CancelReceipt(run_id, True, False, self._session_id, self._prompt_id, "interrupt_failed")
        return CancelReceipt(run_id, True, self._cancel_acknowledged, self._session_id, self._prompt_id)

    async def _execute(self) -> ExecutionResult:
        request = self._request
        status, provider_status = "incomplete", None
        review = metadata = usage_json = execution_error = cleanup_error = None
        protocol_closed = terminal_seen = init_seen = False
        message_tools: set[str] = set()
        instruction_files, errors = ExitStack(), []
        try:
            await self._authority("start")
            await self._account("before_connect", {})
            instructions = self._instructions(request)
            if not isinstance(instructions, str) or not instructions.strip():
                raise AdapterError("missing_governance_instructions")
            instruction_path = instruction_files.enter_context(_owned_instruction_file(instructions, errors))
            binding = self._factory(self._options(instruction_path))
            if not isinstance(binding, ClientBinding):
                raise AdapterError("invalid_sdk_binding")
            # Retain acquired cleanup ownership even if this binding is rejected.
            # Validation below must prevent connection, not skip disconnection.
            self._client = binding.client
            sdk_version = _version_metadata(binding.sdk_version, "sdk")
            _require_client_api(binding.client)
            await self._authority("connect")
            await self._client.connect()
            self._connected = True
            info = await self._client.get_server_info()
            if not isinstance(info, dict):
                raise AdapterError("missing_initialization")
            # Optional initialize provenance, not a release allowlist. When
            # present it must agree with the mandatory system/init observation.
            initialized_version = None
            if "claude_code_version" in info:
                initialized_version = _version_metadata(info["claude_code_version"], "runtime")
            await self._account("initialize", info)
            await self._capture("account/verified", {"accountBinding": request.account_binding})
            await self._capture("query/start", {"session_id": self._session_id, "prompt_id": self._prompt_id})

            async def prompt() -> AsyncIterator[dict[str, Any]]:
                yield {"type": "user", "uuid": self._prompt_id, "session_id": self._session_id,
                       "parent_tool_use_id": None,
                       "message": {"role": "user", "content": request.prompt}}

            # Treat query write failure as uncertain. Interrupt/close without replay.
            # Evidence persistence above can yield; recheck authority after it,
            # immediately before handing the prompt to the SDK.
            await self._authority("query")
            self._query_sent = True
            await self._client.query(prompt(), session_id=self._session_id)
            if self._cancel_requested:
                await self.cancel(request.run_id)
            async for message in self._client.receive_response():
                data = _public_value(message)
                if not isinstance(data, dict):
                    raise AdapterError("invalid_sdk_message")
                kind = data.get("type")
                if kind == "ResultMessage":
                    # Retain the acquired provider terminal independently of sink,
                    # interpretation and later protocol-cleanup failures.
                    terminal_seen = True
                    if data.get("terminal_reason") in {"aborted_streaming", "aborted_tools"}:
                        provider_status = "interrupted"
                    elif data.get("is_error") is True:
                        provider_status = "failed"
                    elif data.get("is_error") is False and data.get("subtype") == "success":
                        provider_status = "completed"
                await self._capture("message/" + str(kind), data)
                if kind == "SystemMessage" and data.get("subtype") == "init":
                    init = data.get("data")
                    if init_seen or not isinstance(init, dict):
                        raise AdapterError("invalid_initialization")
                    if init.get("session_id") != self._session_id:
                        raise AdapterError("native_session_mismatch")
                    runtime_version = _version_metadata(init.get("claude_code_version"), "runtime")
                    if initialized_version is not None and initialized_version != runtime_version:
                        raise AdapterError("runtime_version_metadata_mismatch")
                    if (init.get("model") != request.model or init.get("cwd") != request.cwd
                        or init.get("permissionMode") != "default"
                        or not isinstance(init.get("tools"), list)
                        or set(init["tools"]) not in (set(READ_TOOLS), set(OBSERVED_TOOLS))
                        or init.get("mcp_servers") != [] or init.get("skills") != [] or init.get("plugins") != []):
                        raise AdapterError("observed_profile_mismatch")
                    await self._account("system_init", init)
                    init_seen = True
                    # Provenance is the actual configured transport, like CLI
                    # flags, not a fabricated observed-effort receipt. Keep it
                    # for later failed/interrupted results too. A clean result
                    # separately requires the exact public effort observation.
                    metadata = json_text({
                        "schemaVersion": 1, "adapter": "claude-agent-sdk", "sdkVersion": sdk_version,
                        "runtimeVersion": runtime_version, "model": request.model, "effort": request.effort,
                        "sandboxMode": "tool-restricted-read-only", "approvalPolicy": "deny_unadmitted",
                        "accountBinding": request.account_binding,
                    })
                elif kind == "ResultMessage":
                    if not init_seen or data.get("session_id") != self._session_id:
                        raise AdapterError("native_session_mismatch")
                    if data.get("origin") not in (None, {"kind": "human"}):
                        raise AdapterError("unadmitted_injected_turn")
                    if provider_status == "failed":
                        raise AdapterError("provider_turn_failed")
                    if provider_status == "interrupted":
                        if self._hook_error and self._hook_error != "cancelled_before_effect":
                            raise AdapterError(self._hook_error)
                        status = "interrupted"
                        break
                    if provider_status != "completed" or data.get("terminal_reason") != "completed":
                        raise AdapterError("incomplete_provider_result")
                    if (data.get("errors") or data.get("permission_denials") or data.get("deferred_tool_use")
                        or data.get("api_error_status") is not None):
                        raise AdapterError("contradictory_terminal_result")
                    if self._hook_error:
                        raise AdapterError(self._hook_error)
                    if not self._observed_prompt:
                        raise AdapterError("missing_observed_prompt_identity")
                    if self._observed_effort is None:
                        raise AdapterError("missing_observed_effort")
                    if set(self._tools) != self._tool_results or not message_tools.issubset(self._tool_results):
                        raise AdapterError("incomplete_tool_observations")
                    models = data.get("model_usage")
                    if models is not None and (not isinstance(models, dict) or set(models) != {request.model}):
                        raise AdapterError("observed_model_mismatch")
                    review = validate_review(data.get("structured_output"), request=request)
                    usage = {key: data[key] for key in ("usage", "model_usage", "total_cost_usd") if data.get(key) is not None}
                    if usage:
                        encoded_usage = json_text(usage)
                        if len(encoded_usage.encode("utf-8")) > 65_536:
                            raise AdapterError("usage_limit_exceeded")
                        usage_json = encoded_usage
                    status = "completed"
                    break
                elif kind in {"AssistantMessage", "UserMessage", "StreamEvent"}:
                    if data.get("parent_tool_use_id") is not None:
                        raise AdapterError("unadmitted_subagent")
                    if kind != "UserMessage" and data.get("session_id") != self._session_id:
                        raise AdapterError("native_session_mismatch")
                    if kind == "AssistantMessage" and (data.get("model") != request.model or data.get("error") is not None):
                        raise AdapterError("observed_model_mismatch")
                    if kind == "UserMessage" and data.get("origin") not in (None, {"kind": "human"}):
                        raise AdapterError("unadmitted_injected_turn")
                    for block in data.get("content", []) if isinstance(data.get("content"), list) else []:
                        if block.get("type") == "ToolUseBlock":
                            if block.get("name") not in OBSERVED_TOOLS or not isinstance(block.get("id"), str):
                                raise AdapterError("unadmitted_tool_call")
                            message_tools.add(block["id"])
                elif kind == "RateLimitEvent":
                    if data.get("session_id") != self._session_id:
                        raise AdapterError("native_session_mismatch")
                    info = data.get("rate_limit_info")
                    if not isinstance(info, dict) or info.get("status") not in {"allowed", "allowed_warning", "rejected"}:
                        raise AdapterError("invalid_rate_limit_event")
                    # Public informational telemetry, not a terminal. Preserve
                    # it; the native result still determines success/failure.
                elif kind in {"SystemMessage", "HookEventMessage"}:
                    notice = data.get("data")
                    if (not isinstance(data.get("subtype"), str) or not data["subtype"]
                        or not isinstance(notice, dict)):
                        raise AdapterError("invalid_system_notice")
                    if notice.get("session_id", self._session_id) != self._session_id:
                        raise AdapterError("native_session_mismatch")
                    if kind == "HookEventMessage":
                        if data.get("session_id") not in (None, self._session_id):
                            raise AdapterError("native_session_mismatch")
                        if data["subtype"] not in {"hook_started", "hook_response"}:
                            raise AdapterError("invalid_hook_notice")
                    if (notice.get("model", request.model) != request.model
                        or notice.get("cwd", request.cwd) != request.cwd
                        or notice.get("permissionMode", "default") != "default"):
                        raise AdapterError("observed_profile_mismatch")
                    # The consumed public parser leaves optional status/compaction
                    # and other metadata as SystemMessage. These do not replace
                    # init or a result. Resets/task lifecycles have distinct types
                    # and remain rejected below for this single-review operation.
                    # SessionStart/Setup HookEventMessage notices are emitted
                    # even when include_hook_events is false in the reference SDK.
                else:
                    raise AdapterError("unsupported_sdk_message")
            if not terminal_seen:
                raise AdapterError("missing_terminal_result")
        except Exception as exc:
            execution_error = str(exc) if isinstance(exc, AdapterError) else "execution_or_interpretation_failed"
            if execution_error == "cancelled_before_effect":
                status = "interrupted"
        finally:
            if self._client is not None:
                if self._query_sent and not terminal_seen:
                    receipt = await self.cancel(request.run_id)
                    if receipt.error:
                        errors.append(receipt.error)
                async with self._cancel_lock:
                    try:
                        await self._client.disconnect()
                        protocol_closed = True
                    except Exception:
                        errors.append("protocol_close_failed")
                    self._finished = True
            instruction_files.close()
            cleanup_error = ",".join(errors) if errors else None
            self._finished = True
        if (execution_error not in (None, "cancelled_before_effect")
            or self._capture_error or cleanup_error):
            status = "failed" if provider_status == "failed" else "incomplete"
        return ExecutionResult(
            request=request, status=status, provider_status=provider_status,
            native_thread_id=self._session_id, native_turn_id=self._prompt_id,
            sdk_execution_json=metadata, observations=tuple(self._observations), review=review,
            usage_json=usage_json, execution_error=execution_error,
            capture_error=self._capture_error, cleanup_error=cleanup_error, protocol_closed=protocol_closed,
        )
