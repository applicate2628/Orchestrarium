"""Dormant MiMoCode ACP binding using only the official public Python SDK.

Source evidence, not runtime qualification: XiaomiMiMo/MiMo-Code
 e37f2c2d01460df19b31d67b8116d6c66fe33db8 (acp/agent.ts); Python ACP
 2ad204bb86111da9594bfe13f4a560249603feea (core, connection, client/router).
Connection owns framing/correlation; existing process owner owns streams, limits
and settlement. No subprocess, login, version pin, private SDK access or TS.
MiMo has no session/close; empty MCP does not remove inherited connections.
"""
from __future__ import annotations
import asyncio
import inspect
import threading
from ._async import drain_owned
from .contracts import CancelReceipt, ExecutionRequest, ExecutionResult, Observation, json_text

class MimoAcpError(ValueError):
    """Non-secret errors suitable for execution evidence."""

def _object(value):
    if hasattr(value, 'model_dump'):
        value = value.model_dump(by_alias=True, mode='json', exclude_none=True)
    if not isinstance(value, dict):
        raise MimoAcpError('mimo_invalid_payload')
    return value

class MimoAcpExchange:
    """One owned exchange; connect only to streams acquired by the process owner."""
    def __init__(self, *, assert_current):
        if not callable(assert_current) or inspect.iscoroutinefunction(assert_current):
            raise ValueError('explicit synchronous authority callback required')
        self.assert_current = assert_current
        self._used = self._ready = False
        self._request = self._connection = self._phase = None
        self._cancel = threading.Event()
        self._cancel_lock = asyncio.Lock()
        self._received = self._finished = 0
        self._drained = asyncio.Event()
        self._events, self._setup_ids = [], set()
        self._bytes, self._text = 0, ''
        self._event_error = self._capture_error = None
        self.session_id = self.observed_model = self.observed_effort = None
        self.cancel_sent = self.cancel_acknowledged = self.protocol_closed = False

    def connect(self, writer, reader):
        """Public SDK composition, no process acquisition or alternate protocol."""
        if self._connection is not None:
            raise MimoAcpError('mimo_connection_already_bound')
        from acp.core import Connection
        from acp.client.router import build_client_router
        router = build_client_router(self, use_unstable_protocol=True)
        async def handler(method, params, is_notification):
            counted = method == 'session/update' and is_notification
            try:
                return await router(method, params, is_notification)
            except BaseException:
                self._event_error = self._event_error or 'mimo_callback_failed'
                raise
            finally:
                if counted:
                    self._finished += 1
                    self._drained.set()
        self._connection = Connection(handler, writer, reader, observers=[self._observe])
        return self._connection

    def _observe(self, event):
        # Public synchronous observers run before Connection schedules callbacks.
        # Count before scheduling, so a response cannot overtake a not-yet-started
        # notification. Never let SDK observer exception suppression hide failure.
        try:
            if event.direction != 'incoming':
                return
            message = _object(event.message)
            if message.get('method') == 'session/update':
                if 'id' in message:
                    self._event_error = self._event_error or 'mimo_invalid_update_envelope'
                    return
                self._received += 1
                self._drained.clear()
        except BaseException:
            self._event_error = self._event_error or 'mimo_observer_failed'

    async def _drain_callbacks(self):
        while self._finished < self._received:
            self._drained.clear()
            await self._drained.wait()
        if self._finished != self._received:
            raise MimoAcpError('mimo_callback_accounting_failed')

    def _authority(self, effect):
        if self._cancel.is_set():
            raise MimoAcpError('mimo_cancelled_before_effect')
        if self._event_error:
            raise MimoAcpError(self._event_error)
        try:
            decision = self.assert_current(self._request, effect)
        except Exception:
            raise MimoAcpError('mimo_authority_denied') from None
        if decision is not None:
            raise MimoAcpError('mimo_invalid_authority_callback')

    def _record(self, kind, payload):
        encoded = json_text(_object(payload))
        size = len(encoded.encode())
        if len(self._events) >= self._request.max_events:
            self._capture_error = 'mimo_event_limit'
        elif self._bytes + size > self._request.max_output_bytes:
            self._capture_error = 'mimo_output_limit'
        if self._capture_error:
            raise MimoAcpError(self._capture_error)
        self._events.append(Observation(len(self._events), kind, encoded))
        self._bytes += size

    async def _call(self, method, params):
        self._authority(method)
        self._phase = method
        try:
            response = _object(await self._connection.send_request(method, params))
            if method == 'session/new':
                identity = response.get('sessionId')
                if not isinstance(identity, str) or not identity.strip() or len(identity.encode()) > 4096:
                    raise MimoAcpError('mimo_session_unavailable')
                self.session_id = identity  # Before capture/drain can fail.
            await self._drain_callbacks()
        finally:
            self._phase = None
        if self.session_id and self._setup_ids - {self.session_id}:
            self._event_error = 'mimo_session_mismatch'
        self._record(method, response)
        if self._event_error:
            raise MimoAcpError(self._event_error)
        return response

    async def session_update(self, session_id, update, **kwargs):
        try:
            value = _object(update)
            self._record('session/update', {'sessionId': session_id, 'update': value})
            kind = value.get('sessionUpdate')
            if self.session_id is None and self._phase == 'session/new':
                if kind != 'available_commands_update':
                    raise MimoAcpError('mimo_invalid_setup_update')
                if not isinstance(session_id, str) or not session_id.strip() or len(session_id.encode()) > 4096:
                    raise MimoAcpError('mimo_session_mismatch')
                self._setup_ids.add(session_id)
                return
            if session_id != self.session_id or not self.session_id:
                raise MimoAcpError('mimo_session_mismatch')
            if kind == 'agent_message_chunk':
                content = value.get('content', {})
                if self._phase != 'session/prompt' or not self._ready or content.get('type') != 'text' or not isinstance(content.get('text'), str):
                    raise MimoAcpError('mimo_invalid_content')
                self._text += content['text']  # Aggregate event byte bound covers this.
            elif kind == 'config_option_update':
                # Config metadata alone cannot establish a changed variant.
                raise MimoAcpError('mimo_unexpected_config_update')
            elif kind not in {'available_commands_update', 'agent_thought_chunk', 'user_message_chunk',
                    'tool_call', 'tool_call_update', 'plan', 'usage_update', 'current_mode_update', 'session_info_update'}:
                raise MimoAcpError('mimo_unknown_update')
        except MimoAcpError as exc:
            self._event_error = self._event_error or str(exc)
        except Exception:
            self._event_error = self._event_error or 'mimo_invalid_payload'

    async def request_permission(self, session_id, tool_call, options, **kwargs):
        try:
            self._record('session/request_permission', {'sessionId': session_id,
                'toolCall': _object(tool_call), 'options': [_object(o) for o in options]})
            if not self.session_id or session_id != self.session_id:
                raise MimoAcpError('mimo_session_mismatch')
            if self._phase != 'session/prompt':
                raise MimoAcpError('mimo_invalid_permission_phase')
        except MimoAcpError as exc:
            self._event_error = self._event_error or str(exc)
        except Exception:
            self._event_error = self._event_error or 'mimo_invalid_payload'
        return {'outcome': {'outcome': 'cancelled'}}

    def request_cancel(self):
        self._cancel.set()

    async def cancel(self):
        self.request_cancel()
        async with self._cancel_lock:
            if self._connection is not None and self.session_id and not self.cancel_sent:
                await self._connection.send_notification('session/cancel', {'sessionId': self.session_id})
                self.cancel_sent = True  # Delivery is not acknowledgement.

    async def run(self, request, connection):
        if not isinstance(request, ExecutionRequest) or request.provider != 'mimo':
            raise MimoAcpError('unsupported_provider')
        if self._used:
            raise MimoAcpError('operation_already_consumed')
        if connection is not self._connection or connection is None:
            raise MimoAcpError('mimo_unbound_connection')
        self._used = True
        self._request = request
        error = stop = None
        try:
            initialized = await self._call('initialize', {'protocolVersion': 1, 'clientCapabilities': {}})
            if type(initialized.get('protocolVersion')) is not int or initialized['protocolVersion'] != 1:
                raise MimoAcpError('mimo_protocol_incompatible')
            if initialized.get('agentInfo', {}).get('name') != 'OpenCode':
                raise MimoAcpError('mimo_agent_mismatch')
            created = await self._call('session/new', {'cwd': request.cwd, 'mcpServers': []})
            token = request.model + '/' + request.effort
            catalog = created.get('models', {}).get('availableModels')
            if (not isinstance(catalog, list) or not catalog
                    or any(not isinstance(m, dict) or not isinstance(m.get('modelId'), str)
                           or not m['modelId'].strip() for m in catalog)):
                raise MimoAcpError('mimo_model_variant_unavailable')
            model_ids = [m['modelId'] for m in catalog]
            if len(set(model_ids)) != len(model_ids) or token not in model_ids:
                raise MimoAcpError('mimo_model_variant_unavailable')
            selected = await self._call('session/set_model', {'sessionId': self.session_id, 'modelId': token})
            meta = selected.get('_meta', {}).get('opencode', {})
            variants = meta.get('availableVariants')
            if (meta.get('modelId') != request.model or meta.get('variant') != request.effort
                    or not isinstance(variants, list)
                    or any(not isinstance(v, str) or not v.strip() for v in variants)
                    or len(set(variants)) != len(variants) or request.effort not in variants):
                raise MimoAcpError('mimo_model_variant_mismatch')
            self.observed_model, self.observed_effort = request.model, request.effort
            self._ready = True
            if request.prompt.lstrip().startswith('/'):
                raise MimoAcpError('mimo_command_prompt_unsupported')
            response = await self._call('session/prompt', {'sessionId': self.session_id,
                'prompt': [{'type': 'text', 'text': request.prompt}]})
            stop = response.get('stopReason')
            if stop not in {'end_turn', 'cancelled', 'refusal', 'max_tokens', 'max_turn_requests'}:
                raise MimoAcpError('mimo_invalid_stop_reason')
            self.cancel_acknowledged = self.cancel_sent and stop == 'cancelled'
        except MimoAcpError as exc:
            error = str(exc)
        except Exception:
            error = 'mimo_protocol_failed'
        finally:
            # Transport close only. No invented session-close or process settlement.
            try:
                await drain_owned(asyncio.create_task(connection.close()))
            except Exception:
                error = error or 'mimo_connection_close_failed'
        return ExecutionResult(request, 'interrupted' if self._cancel.is_set() or stop == 'cancelled' else 'incomplete',
            provider_status={'end_turn': 'completed', 'cancelled': 'interrupted', 'refusal': 'failed'}.get(stop),
            actual_execution_path='direct-external-cli', native_result_text=self._text if self._text.strip() else None,
            native_thread_id=self.session_id, observations=tuple(self._events), capture_error=self._capture_error,
            cleanup_error='mimo_process_settlement_unavailable',
            execution_error=error or self._event_error or 'mimo_account_readback_unavailable')


def _require_live_mimo_binding(request):
    # Still missing executable/account/effective-permission/MCP and owner proof.
    raise MimoAcpError('mimo_live_binding_unqualified')

class MimoAcpAdapter:
    """Held before any factory may acquire streams or bind the SDK connection."""
    def __init__(self, *, client_factory, assert_current):
        if not callable(client_factory) or inspect.iscoroutinefunction(client_factory):
            raise ValueError('explicit synchronous connection factory required')
        self._factory = client_factory
        self.exchange = MimoAcpExchange(assert_current=assert_current)
        self._request = self.execution_result = None

    async def execute(self, request):
        if not isinstance(request, ExecutionRequest) or request.provider != 'mimo':
            raise MimoAcpError('unsupported_provider')
        _require_live_mimo_binding(request)
        if self._request is not None:
            raise MimoAcpError('operation_already_consumed')
        self._request = self.exchange._request = request
        self.exchange._authority('acquire_connection')
        connection = self._factory(self.exchange)
        if inspect.isawaitable(connection):
            if inspect.iscoroutine(connection): connection.close()
            raise MimoAcpError('mimo_async_factory_not_supported')
        task = asyncio.create_task(self.exchange.run(request, connection))
        try:
            self.execution_result = await asyncio.shield(task)
        except asyncio.CancelledError:
            await drain_owned(asyncio.create_task(self.cancel(request.run_id)))
            self.execution_result = await drain_owned(task)
        return self.execution_result

    async def cancel(self, run_id):
        if self._request is None or self._request.run_id != run_id:
            return CancelReceipt(run_id, False, False, error='unknown_execution')
        if self.execution_result is not None:
            return CancelReceipt(run_id, False, False, error='already_finished')
        try:
            await self.exchange.cancel()
        except Exception:
            return CancelReceipt(run_id, True, False, error='mimo_cancel_failed', native_thread_id=self.exchange.session_id)
        return CancelReceipt(run_id, True, self.exchange.cancel_acknowledged, native_thread_id=self.exchange.session_id)
