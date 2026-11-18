"""Fresh prompt-only Copilot Consultant through the official Python SDK.

Source: microsoft/copilot-sdk, 3ce61458503b6b27ebd1f674a980f4d9596d9b22,
python/copilot/{client,session,_mode}.py. Source evidence is not installed/native
qualification. Explicit spawned stdio uses a preprovisioned runtime, never a
managed download. SDK cleanup is not OS process-tree settlement. This structural
Executor is usable by AgentsCoordinator, not a CLI or canonical receiving route.
"""
from __future__ import annotations

import asyncio
import inspect
import math
from pathlib import Path
from types import SimpleNamespace

from ._async import drain_owned
from .contracts import CancelReceipt, ExecutionRequest, ExecutionResult, Observation, json_text, strict_json, task_schema, validate_task
from .receiving import scan_execution_output


class CopilotError(ValueError):
    """Closed diagnostic vocabulary; never export raw SDK exceptions."""


def _load_sdk():
    from copilot import CopilotClient, RuntimeConnection, AgentMessageSource
    from copilot.rpc import PermissionDecisionReject
    return SimpleNamespace(CopilotClient=CopilotClient, RuntimeConnection=RuntimeConnection,
        AgentMessageSource=AgentMessageSource, PermissionDecisionReject=PermissionDecisionReject)


class CopilotExecutor:
    """One fresh operation under a live Host permission/account/budget owner.

    The Host supplies selected credentials and environment, not an authorization
    boolean copied from the request. Token and environment never enter results.
    Missing runtime/SDK does not install, download or select an alternate route.
    """
    def __init__(self, *, runtime_path, base_directory, environment, github_token,
                 assert_current, output_context, timeout_seconds, cleanup_timeout_seconds, sdk=None):
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
        if not callable(assert_current) or any(inspect.iscoroutinefunction(v) or inspect.isasyncgenfunction(v) for v in (assert_current,getattr(assert_current,"__call__",None))):
            raise CopilotError("copilot_synchronous_authority_required")
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
        self._output = owner.ProviderOutputContext(tuple(dict.fromkeys((*output_context.needles,github_token.encode("utf-8")))))
        self._timeout, self._cleanup_timeout = timeout_seconds, cleanup_timeout_seconds
        self._sdk = sdk
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

    def _current(self, request, effect):
        try:
            unchanged = self._runtime_identity() == self._identity
        except OSError:
            unchanged = False
        if not unchanged:
            raise CopilotError("copilot_runtime_changed")
        try:
            answer = self._authority(request,effect)
        except Exception:
            raise CopilotError("copilot_authority_denied") from None
        if answer is not None:
            if inspect.iscoroutine(answer): answer.close()
            raise CopilotError("copilot_invalid_authority_callback")

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
            self._event_error = "copilot_unexpected_tool"
        if not self._event_error and kind in {"assistant.message","assistant.message_delta"}:
            self._retain_content(content or delta,"copilot.assistant.message")
        if self._event_error: self._request_abort()

    async def _profile(self, request, effect):
        self._current(request,effect)
        profile = await self._session.rpc.model.get_current(timeout=self._timeout)
        if (getattr(profile,"model_id",None),getattr(profile,"reasoning_effort",None)) != (request.model,request.effort):
            raise CopilotError("copilot_profile_mismatch")

    async def execute(self, request):
        if (type(request) is not ExecutionRequest or request.provider != "copilot"
            or request.role != "consultant" or request.result_kind != "task"
            or request.tool_profile != "prompt-only" or request.context_mode != "fresh"
            or request.write_workspace is not None):
            raise CopilotError("copilot_request_unsupported")
        if self._request is not None:
            raise CopilotError("operation_already_consumed")
        self._current(request,"copilot_start")
        self._request = request
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
        task_result = None
        error = cleanup_error = None
        provider_status = None
        session_id = None
        unsubscribe = None
        closed = False
        try:
            async with asyncio.timeout(self._timeout):
                if self._cancel_requested: raise asyncio.CancelledError()
                sdk = self._sdk or _load_sdk()
                def deny(_request,_invocation):
                    self._event_error = "copilot_unexpected_permission_request"
                    self._request_abort()
                    return sdk.PermissionDecisionReject(feedback="Prompt-only operation has no tool authority")
                if self._cancel_requested: raise asyncio.CancelledError()
                self._current(request,"copilot_client_create")
                runtime = sdk.RuntimeConnection.for_spawned_stdio(path=str(self._runtime),env=dict(self._environment),
                    working_directory=request.cwd,base_directory=str(self._base))
                self._client = sdk.CopilotClient(mode="empty",runtime=runtime,
                    github={"token":self._token,"use_logged_in_user":False})
                await self._client.start()
                if self._cancel_requested: raise asyncio.CancelledError()
                self._current(request,"copilot_session_create")
                self._session = await self._client.create_session(model=request.model,
                    working_directory=request.cwd,enable_config_discovery=False,
                    tools={"available_tools":[]},permissions={"on_request":deny},
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
                self._current(request,"copilot_send")
                event = await self._session.send_and_wait(request.prompt,
                    source=sdk.AgentMessageSource(request.coordinator_binding),
                    response_schema=task_schema(request),timeout=self._timeout)
                if event is None: raise CopilotError("copilot_terminal_unavailable")
                kind = getattr(event,"type",None)
                if getattr(kind,"value",kind) != "assistant.message": raise CopilotError("copilot_terminal_type_mismatch")
                if getattr(event,"agent_id",None): raise CopilotError("copilot_child_output_not_terminal")
                content = getattr(getattr(event,"data",None),"content",None)
                if not isinstance(content,str) or not content.strip(): raise CopilotError("copilot_terminal_unavailable")
                if len(content.encode()) > request.max_output_bytes: raise CopilotError("copilot_capture_limit")
                # Preserve bounded acquired text even when the task codec rejects it.
                self._retain_content(content,"copilot.assistant.message")
                task_result = validate_task(strict_json(content,max_bytes=request.max_output_bytes),request=request)
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
        status = "interrupted" if self._cancel_requested else "completed" if task_result is not None and not error and not cleanup_error else "incomplete"
        result = ExecutionResult(request,status,provider_status=provider_status,
            native_thread_id=session_id,task=task_result,observations=tuple(self._observations),
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
        self._current(request,"copilot_result")
        return result
