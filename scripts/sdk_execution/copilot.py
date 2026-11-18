"""Fresh prompt-only Copilot evidence through the official Python SDK.

Source: microsoft/copilot-sdk, 3ce61458503b6b27ebd1f674a980f4d9596d9b22,
python/copilot/{client,session,_mode}.py. Source evidence is not installed/native
qualification. Explicit spawned stdio uses a preprovisioned runtime, never a
managed download. SDK cleanup is not OS process-tree settlement. The structural
Executor and fixed contained-worker factory share this protocol implementation;
canonical receiving relies on the separate creator-owned worker observation.
"""
from __future__ import annotations

import asyncio
import inspect
import math
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from types import SimpleNamespace

from ._async import drain_owned
from .contracts import CancelReceipt, ExecutionRequest, ExecutionResult, Observation, json_text, strict_json, task_schema, validate_task, review_schema, validate_review
from .receiving import scan_execution_output


class CopilotError(ValueError):
    """Closed diagnostic vocabulary; never export raw SDK exceptions."""


def _load_sdk():
    from copilot import CopilotClient, RuntimeConnection, AgentMessageSource
    from copilot.rpc import PermissionDecisionReject, PermissionDecisionApproveOnce
    from copilot.tools import Tool, ToolResult
    return SimpleNamespace(CopilotClient=CopilotClient, RuntimeConnection=RuntimeConnection,
        AgentMessageSource=AgentMessageSource, PermissionDecisionReject=PermissionDecisionReject,
        PermissionDecisionApproveOnce=PermissionDecisionApproveOnce, Tool=Tool, ToolResult=ToolResult)


@dataclass(frozen=True, slots=True)
class CopilotRuntimeSelection:
    """Nonsecret SDK transport and Host bounds; not vendor account evidence."""
    executable: str
    executable_sha256: str
    base_directory: str
    auth_mode: str
    instructions: str
    work_item: str
    ledger_max_events: int | None
    ledger_max_bytes: int | None
    job_memory_limit_bytes: int
    timeout_seconds: float
    cleanup_timeout_seconds: float
    expected_launch_sha256: str | None = None

    def __post_init__(self):
        for key in ("executable", "base_directory", "work_item"):
            value = getattr(self,key)
            if type(value) is not str or not Path(value).is_absolute():
                raise CopilotError("explicit_absolute_runtime_paths_required")
        for key in ("executable_sha256", "expected_launch_sha256"):
            value = getattr(self,key)
            if value is None and key == "expected_launch_sha256": continue
            if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}",value) is None:
                raise CopilotError("explicit_runtime_digest_required")
        budgets = (self.job_memory_limit_bytes,)
        if self.ledger_max_events is not None or self.ledger_max_bytes is not None:
            budgets += (self.ledger_max_events,self.ledger_max_bytes)
        if any(type(v) is not int or v <= 0 for v in budgets):
            raise CopilotError("explicit_positive_resource_budget_required")
        for value in (self.timeout_seconds,self.cleanup_timeout_seconds):
            if type(value) not in (int,float) or not math.isfinite(value) or value <= 0:
                raise CopilotError("copilot_explicit_deadline_required")
        if self.auth_mode != "copilot-explicit-token": raise CopilotError("copilot_explicit_auth_required")
        if type(self.instructions) is not str or not self.instructions.strip():
            raise CopilotError("missing_governance_instructions")
        import provider_prompt as owner
        owner._bounded_strict_utf8_snapshot(self.instructions.encode("utf-8"), "instructions")

    def to_dict(self): return asdict(self)

    @classmethod
    def from_dict(cls,value):
        if type(value) is not dict or set(value) != set(cls.__dataclass_fields__):
            raise CopilotError("invalid_runtime_selection_fields")
        return cls(**value)


FILE_TOOLS = {"orchestrarium_read":"Read", "orchestrarium_write":"Write", "orchestrarium_edit":"Edit"}


def validate_copilot_request(request):
    """Reuse the canonical role taxonomy, not a provider-specific profession list."""
    if (type(request) is not ExecutionRequest or request.provider != "copilot"
            or request.context_mode != "fresh"):
        raise CopilotError("copilot_request_unsupported")
    import provider_prompt as owner
    _roles, reviewers, workers, _unsupported = owner._external_role_taxonomy()
    if request.write_workspace is not None:
        if request.role not in workers or request.result_kind != "task" or request.tool_profile != "default":
            raise CopilotError("copilot_request_unsupported")
    elif (request.tool_profile != "prompt-only"
            or (request.result_kind == "task" and request.role != "consultant")
            or (request.result_kind == "review" and request.role not in reviewers)):
        raise CopilotError("copilot_request_unsupported")


class CopilotExecutor:
    """One fresh operation under a live Host permission/account/budget owner.

    The Host supplies selected credentials and environment, not an authorization
    boolean copied from the request. Token and environment never enter results.
    Missing runtime/SDK does not install, download or select an alternate route.
    """
    def __init__(self, *, runtime_path, base_directory, environment, github_token,
                 assert_current, output_context, timeout_seconds, cleanup_timeout_seconds, sdk=None, instructions="", authorize_tool=None, worker_selection=None):
        import provider_prompt as owner
        self._runtime = Path(runtime_path)
        self._base = Path(base_directory)
        if not self._runtime.is_absolute() or not self._runtime.is_file() or not self._runtime.stat().st_size:
            raise CopilotError("copilot_provisioned_runtime_required")
        if not self._base.is_absolute():
            raise CopilotError("copilot_explicit_base_directory_required")
        if type(environment) is not dict or any(type(k) is not str or type(v) is not str or not k or "\0" in k+v or "=" in k for k,v in environment.items()):
            raise CopilotError("copilot_explicit_environment_required")
        if type(github_token) is not str or not github_token.strip():
            raise CopilotError("copilot_explicit_credential_required")
        if not callable(assert_current) or any(inspect.isasyncgenfunction(v) for v in (assert_current,getattr(assert_current,"__call__",None))):
            raise CopilotError("copilot_invalid_authority")
        if type(output_context) is not owner.ProviderOutputContext:
            raise CopilotError("copilot_output_context_required")
        output_context.__post_init__()
        for value in (timeout_seconds,cleanup_timeout_seconds):
            if type(value) not in (int,float) or not math.isfinite(value) or value <= 0:
                raise CopilotError("copilot_explicit_deadline_required")
        self._identity = self._runtime_identity()
        self._environment = dict(environment)
        self._environment["COPILOT_SKIP_CLI_DOWNLOAD"] = "1"
        self._token = github_token
        self._authority = assert_current
        if type(instructions) is not str: raise CopilotError("copilot_invalid_instructions")
        self._instructions = instructions
        self._authorize_tool = authorize_tool
        self._worker_selection = worker_selection
        self._workspace_identity = None
        self._tool_calls = set()
        self._tools_closed = False
        self._tool_lock = asyncio.Lock()
        self._output = owner.ProviderOutputContext(tuple(dict.fromkeys((*output_context.needles,github_token.encode("utf-8")))))
        self._timeout, self._cleanup_timeout = timeout_seconds, cleanup_timeout_seconds
        self._sdk = sdk
        self._observed_profile = None
        self._request = self._session = self._client = None
        self._cancel_requested = False
        self._abort_task = None
        self.execution_result = None
        self._event_count = self._output_bytes = 0
        self._event_error = None
        self._observations = []

    def _runtime_identity(self):
        stat = self._runtime.stat()
        return (str(self._runtime.resolve()),stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns)

    async def _current(self, request, effect):
        try:
            unchanged = self._runtime_identity() == self._identity
        except OSError:
            unchanged = False
        if not unchanged:
            raise CopilotError("copilot_runtime_changed")
        try:
            answer = self._authority(request,effect)
            if inspect.isawaitable(answer): answer = await answer
        except Exception:
            raise CopilotError("copilot_authority_denied") from None
        if answer is not None:
            if inspect.iscoroutine(answer): answer.close()
            raise CopilotError("copilot_invalid_authority_callback")
        try:
            unchanged = self._runtime_identity() == self._identity
        except OSError:
            unchanged = False
        if not unchanged: raise CopilotError("copilot_runtime_changed")

    async def _abort(self):
        if self._session is not None:
            try:
                await asyncio.wait_for(self._session.abort(),self._cleanup_timeout)
            except Exception:
                return False
        return True

    def _request_abort(self):
        if self._session is not None and self._abort_task is None:
            self._abort_task = asyncio.create_task(self._abort())

    def _retain_content(self, content, kind):
        if not isinstance(content,str) or not content: return
        payload = json_text({"content":content})
        if any(item.payload_json == payload for item in self._observations): return
        used = sum(len(item.payload_json.encode()) for item in self._observations)
        if len(self._observations) < self._request.max_events and used + len(payload.encode()) <= self._request.max_output_bytes:
            self._observations.append(Observation(len(self._observations),kind,payload))
        else:
            self._event_error = "copilot_capture_limit"
            self._request_abort()

    def _event(self, event):
        self._event_count += 1
        kind = getattr(event,"type",None)
        kind = getattr(kind,"value",kind)
        data = getattr(event,"data",None)
        content = getattr(data,"content",None)
        delta = getattr(data,"delta_content",None)
        for text in (content,delta):
            if isinstance(text,str): self._output_bytes += len(text.encode("utf-8"))
        if self._event_count > self._request.max_events or self._output_bytes > self._request.max_output_bytes:
            self._event_error = "copilot_capture_limit"
        elif kind == "session.error":
            self._event_error = "copilot_session_failed"
        elif isinstance(kind,str) and kind.startswith("tool.execution"):
            if self._request.write_workspace is None or (getattr(data,"tool_name",None) is not None and data.tool_name not in FILE_TOOLS):
                self._event_error = "copilot_unexpected_tool"
        if not self._event_error and kind in {"assistant.message","assistant.message_delta"}:
            self._retain_content(content or delta,"copilot.assistant.message")
        if self._event_error: self._request_abort()

    async def _profile(self, request, effect):
        await self._current(request,effect)
        if self._cancel_requested: raise asyncio.CancelledError()
        profile = await self._session.rpc.model.get_current(timeout=self._timeout)
        if (getattr(profile,"model_id",None),getattr(profile,"reasoning_effort",None)) != (request.model,request.effort):
            raise CopilotError("copilot_profile_mismatch")
        self._observed_profile = (profile.model_id,profile.reasoning_effort)

    async def _authorize_file(self,name,arguments):
        from .runtime import authorize_workspace_file_tool
        if self._tools_closed or self._event_error or name not in FILE_TOOLS or type(arguments) is not dict:
            raise CopilotError("copilot_invalid_file_tool")
        arguments = dict(arguments)
        fields={"Read":{"file_path"},"Write":{"file_path","content"},"Edit":{"file_path","old_string","new_string"}}[FILE_TOOLS[name]]
        if set(arguments)!=fields or any(type(value) is not str for value in arguments.values()):
            raise CopilotError("copilot_invalid_file_arguments")
        if len(json_text(arguments).encode("utf-8")) > self._request.max_output_bytes:
            raise CopilotError("copilot_capture_limit")
        await self._current(self._request,"tool")
        if self._cancel_requested or self._tools_closed or self._event_error: raise CopilotError("copilot_cancelled")
        answer=self._authorize_tool(self._request,FILE_TOOLS[name],dict(arguments))
        if inspect.isawaitable(answer): answer=await answer
        if answer is not None: raise CopilotError("copilot_invalid_tool_authority")
        if self._cancel_requested or self._tools_closed or self._event_error: raise CopilotError("copilot_cancelled")
        authorize_workspace_file_tool(self._request,self._worker_selection,FILE_TOOLS[name],arguments,
            expected_identity=self._workspace_identity)

    def _file_tools(self,sdk):
        definitions=[]
        for name,operation in FILE_TOOLS.items():
            keys={"Read":["file_path"],"Write":["file_path","content"],"Edit":["file_path","old_string","new_string"]}[operation]
            async def handler(invocation,selected=name):
                async with self._tool_lock:
                    return await self._file_effect(sdk,selected,invocation)
            definitions.append(sdk.Tool(name=name,description="Scoped Host " + operation + " of one UTF-8 file",
                handler=handler,parameters={"type":"object","additionalProperties":False,
                    "required":keys,"properties":{key:{"type":"string"} for key in keys}},
                skip_permission=False,overrides_built_in_tool=False,idempotent=False))
        return {"available_tools":list(FILE_TOOLS),"definitions":definitions}

    async def _file_effect(self,sdk,name,invocation):
        import provider_prompt as owner
        effect_started=False
        try:
            if (invocation.tool_name != name or invocation.session_id != self._session.session_id
                    or getattr(invocation,"agent_id",None) or not invocation.tool_call_id
                    or invocation.tool_call_id in self._tool_calls):
                raise CopilotError("copilot_invalid_tool_invocation")
            self._tool_calls.add(invocation.tool_call_id)
            self._event_count += 1
            if self._event_count > self._request.max_events:
                self._event_error="copilot_capture_limit"
                self._request_abort()
                raise CopilotError("copilot_capture_limit")
            if type(invocation.arguments) is not dict: raise CopilotError("copilot_invalid_file_arguments")
            arguments=dict(invocation.arguments)
            await self._authorize_file(name,arguments)
            target=Path(arguments["file_path"])
            operation=FILE_TOOLS[name]
            limit=self._request.max_output_bytes
            text=""
            if operation in {"Read","Edit"}:
                with target.open("rb") as stream: raw=stream.read(limit+1)
                if len(raw)>limit: raise CopilotError("copilot_capture_limit")
                text=raw.decode("utf-8",errors="strict")
            if operation == "Read":
                if owner.credential_scan_terminal(self._output.needles,stdout=text.encode("utf-8"),stderr=b""):
                    raise CopilotError("copilot_file_credential_refused")
                result_text=text
            else:
                content=arguments["content"] if operation=="Write" else None
                if operation=="Edit":
                    old=arguments["old_string"]
                    if not old or text.count(old)!=1: raise CopilotError("copilot_edit_match_required")
                    content=text.replace(old,arguments["new_string"],1)
                encoded=content.encode("utf-8")
                if len(encoded)>limit: raise CopilotError("copilot_capture_limit")
                # Recheck current scope immediately before I/O, not OS-atomic confinement.
                from .runtime import authorize_workspace_file_tool
                authorize_workspace_file_tool(self._request,self._worker_selection,operation,arguments,
                    expected_identity=self._workspace_identity)
                if self._cancel_requested or self._tools_closed or self._event_error: raise CopilotError("copilot_cancelled")
                effect_started=True
                target.parent.mkdir(parents=True,exist_ok=True)
                authorize_workspace_file_tool(self._request,self._worker_selection,operation,arguments,
                    expected_identity=self._workspace_identity)
                with target.open("wb") as stream: stream.write(encoded)
                result_text="File effect completed."
            self._output_bytes += len(result_text.encode("utf-8"))
            if self._output_bytes > limit:
                self._event_error="copilot_capture_limit"
                self._request_abort()
                raise CopilotError("copilot_capture_limit")
            self._retain_content(json_text({"tool":name,"status":"completed"}),"copilot.host_tool")
            return sdk.ToolResult(text_result_for_llm=result_text,result_type="success")
        except Exception:
            if effect_started:
                self._event_error="copilot_file_effect_may_be_partial"
                self._request_abort()
            status="effect_may_be_partial" if effect_started else "effect_not_started"
            self._retain_content(json_text({"tool":name,"status":status}),"copilot.host_tool")
            return sdk.ToolResult(text_result_for_llm=status,result_type="failure",error="copilot_file_effect_failed")

    async def execute(self, request):
        validate_copilot_request(request)
        if self._request is not None:
            raise CopilotError("operation_already_consumed")
        if request.write_workspace is not None:
            from .runtime import validate_worker_custody
            if not callable(self._authorize_tool) or type(self._worker_selection) is not CopilotRuntimeSelection:
                raise CopilotError("copilot_worker_authority_required")
            self._workspace_identity = validate_worker_custody(request,self._worker_selection)
        self._request = request
        await self._current(request,"copilot_start")
        task = asyncio.create_task(self._execute(request))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            await self.cancel(request.run_id)
            return await drain_owned(task)

    async def cancel(self, run_id):
        if self._request is None or self._request.run_id != run_id:
            return CancelReceipt(run_id,False,False,error="unknown_execution")
        if self.execution_result is not None:
            return CancelReceipt(run_id,False,False,error="already_finished")
        self._cancel_requested = True
        self._request_abort()
        return CancelReceipt(run_id,True,False,error="copilot_cancellation_not_terminal_evidence")

    async def _execute(self, request):
        evidence_result = None
        error = cleanup_error = None
        provider_status = None
        session_id = None
        unsubscribe = None
        closed = False
        try:
            async with asyncio.timeout(self._timeout):
                if self._cancel_requested: raise asyncio.CancelledError()
                sdk = self._sdk or _load_sdk()
                def deny(value,invocation):
                    self._event_error = "copilot_unexpected_permission_request"
                    self._request_abort()
                    return sdk.PermissionDecisionReject(feedback="Prompt-only operation has no tool authority")
                async def permission(value,invocation):
                    if request.write_workspace is not None:
                        try:
                            if (getattr(value,"kind",None) != "custom-tool"
                                    or getattr(value,"managed_approval_required",False)
                                    or invocation.get("managed_settings_enabled",False)
                                    or invocation.get("session_id") != self._session.session_id):
                                raise CopilotError("copilot_permission_denied")
                            await self._authorize_file(getattr(value,"tool_name",None),getattr(value,"args",None))
                            return sdk.PermissionDecisionApproveOnce()
                        except Exception:
                            return sdk.PermissionDecisionReject(feedback="File effect is not admitted")
                    self._event_error = "copilot_unexpected_permission_request"
                    self._request_abort()
                    return sdk.PermissionDecisionReject(feedback="Prompt-only operation has no tool authority")
                if self._cancel_requested: raise asyncio.CancelledError()
                await self._current(request,"copilot_client_create")
                if self._cancel_requested: raise asyncio.CancelledError()
                runtime = sdk.RuntimeConnection.for_spawned_stdio(path=str(self._runtime),env=dict(self._environment),
                    working_directory=request.cwd,base_directory=str(self._base))
                self._client = sdk.CopilotClient(mode="empty",runtime=runtime,
                    github={"token":self._token,"use_logged_in_user":False})
                await self._client.start()
                if self._cancel_requested: raise asyncio.CancelledError()
                await self._current(request,"copilot_session_create")
                if self._cancel_requested: raise asyncio.CancelledError()
                self._session = await self._client.create_session(model=request.model,
                    working_directory=request.cwd,enable_config_discovery=False,
                    system_message={"mode":"append","content":self._instructions},
                    tools=self._file_tools(sdk) if request.write_workspace is not None else {"available_tools":[]},permissions={"on_request":permission if request.write_workspace is not None else deny},
                    inference={"reasoning_effort":request.effort},
                    instructions={"skip_custom_instructions":True,"on_demand_discovery":False,"directories":[]},
                    hooks={"enable_repository_hooks":False,"directories":[]},
                    skills={"enabled":False,"directories":[],"included_builtin_skills":[]},
                    mcp={"servers":{},"enable_apps":False},
                    execution={"autopilot":{"continuation_enabled":False}})
                session_id = getattr(self._session,"session_id",None)
                if not isinstance(session_id,str) or not session_id.strip() or len(session_id.encode()) > 4096:
                    raise CopilotError("copilot_session_identity_unavailable")
                unsubscribe = self._session.on(self._event)
                if self._cancel_requested: raise asyncio.CancelledError()
                await self._profile(request,"copilot_profile_before")
                if self._cancel_requested: raise asyncio.CancelledError()
                await self._current(request,"copilot_send")
                if self._cancel_requested: raise asyncio.CancelledError()
                event = await self._session.send_and_wait(request.prompt,
                    source=sdk.AgentMessageSource(request.coordinator_binding),
                    response_schema=(task_schema if request.result_kind == "task" else review_schema)(request),timeout=self._timeout)
                if event is None: raise CopilotError("copilot_terminal_unavailable")
                kind = getattr(event,"type",None)
                if getattr(kind,"value",kind) != "assistant.message": raise CopilotError("copilot_terminal_type_mismatch")
                if getattr(event,"agent_id",None): raise CopilotError("copilot_child_output_not_terminal")
                content = getattr(getattr(event,"data",None),"content",None)
                if not isinstance(content,str) or not content.strip(): raise CopilotError("copilot_terminal_unavailable")
                if len(content.encode()) > request.max_output_bytes: raise CopilotError("copilot_capture_limit")
                # Preserve bounded acquired text even when the result codec rejects it.
                self._retain_content(content,"copilot.assistant.message")
                evidence_result = (validate_task if request.result_kind == "task" else validate_review)(
                    strict_json(content,max_bytes=request.max_output_bytes),request=request)
                provider_status = "completed"
                await self._profile(request,"copilot_profile_after")
        except asyncio.CancelledError:
            self._cancel_requested = True
            error = "copilot_cancelled"
        except TimeoutError:
            error = "copilot_deadline_exceeded"
        except CopilotError as exc:
            error = str(exc)
        except Exception:
            error = "copilot_sdk_failed"
        finally:
            self._tools_closed = True
            if error or self._cancel_requested or self._event_error:
                self._request_abort()
            if self._abort_task is not None and not await drain_owned(self._abort_task):
                cleanup_error = "copilot_abort_failed"
            if unsubscribe is not None:
                try: unsubscribe()
                except Exception: cleanup_error = "copilot_unsubscribe_failed"
            for obj,method in ((self._session,"disconnect"),(self._client,"stop")):
                if obj is not None:
                    try: await asyncio.wait_for(getattr(obj,method)(),self._cleanup_timeout)
                    except Exception: cleanup_error = "copilot_cleanup_failed"
            closed = self._client is not None and cleanup_error is None
        error = error or self._event_error
        status = "interrupted" if self._cancel_requested else "completed" if evidence_result is not None and not error and not cleanup_error else "incomplete"
        metadata = None
        if self._observed_profile is not None:
            metadata = {"schemaVersion":1,"adapter":"microsoft-copilot-sdk",
                "model":self._observed_profile[0],"effort":self._observed_profile[1],
                "sandboxMode":"tool-restricted-workspace-write" if request.write_workspace is not None else "tool-restricted-read-only",
                "approvalPolicy":"deny_unadmitted" if request.write_workspace is not None else "deny_all",
                "accountBinding":request.account_binding}
        if metadata is not None and request.write_workspace is not None:
            import hashlib
            metadata["writeWorkspaceSha256"] = hashlib.sha256(request.write_workspace.encode("utf-8")).hexdigest()
        result = ExecutionResult(request,status,provider_status=provider_status,
            sdk_execution_json=json_text(metadata) if metadata is not None else None,
            native_thread_id=session_id,
            task=evidence_result if request.result_kind == "task" else None,
            review=evidence_result if request.result_kind == "review" else None,
            observations=tuple(self._observations),
            execution_error=error,cleanup_error=cleanup_error,protocol_closed=closed)
        self.execution_result = result
        # Observations are retained privately on refusal, but never returned unscanned.
        import provider_prompt as owner
        evidence = json_text({"native_thread_id":result.native_thread_id,
            "observations":[item.to_dict() for item in result.observations]})
        failure = owner.provider_output_safety_scan_terminal("copilot",self._output.needles,
            stdout=evidence.encode("utf-8"),stderr=b"")
        if failure is not None: raise CopilotError(failure)
        scan_execution_output(result,self._output)
        await self._current(request,"copilot_result")
        return result


def create_copilot_adapter(request, sink, selection):
    """Fixed contained worker factory; no installation or credential fallback."""
    import os
    from .runtime import assert_current_launch, prepare_environment, validate_admitted_request
    if request.provider != "copilot" or type(selection) is not CopilotRuntimeSelection:
        raise CopilotError("copilot_request_unsupported")
    validate_admitted_request(request, selection)
    assert_current_launch(request, selection, "worker_factory")
    environment, output_context = prepare_environment(selection, dict(os.environ))

    async def current(value, effect):
        if value != request: raise CopilotError("worker_request_binding_mismatch")
        assert_current_launch(value, selection, effect)
        await sink.authorize(value,effect)

    async def tool(value,name,arguments):
        if value != request: raise CopilotError("worker_request_binding_mismatch")
        assert_current_launch(value,selection,"tool")
        await sink.authorize(value,"tool",{"kind":"tool","name":name,"arguments":arguments})

    return CopilotExecutor(runtime_path=selection.executable,
        base_directory=selection.base_directory, environment=environment,
        github_token=environment["COPILOT_GITHUB_TOKEN"], assert_current=current,
        output_context=output_context, timeout_seconds=selection.timeout_seconds,
        cleanup_timeout_seconds=selection.cleanup_timeout_seconds,
        instructions=selection.instructions,authorize_tool=tool,worker_selection=selection)
