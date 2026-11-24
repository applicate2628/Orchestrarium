"""Dormant MiniMax Code consumer of a caller-owned public ACP SDK connection.

Official source evidence: MiniMax-AI/minimax-code commit
 da22f11c55d4748155d7162c1030414228a00565, packages/tui/src/acp/{agent,control-state}.ts.
Model values are advertised opaque tokens; thinkingEffort is session-scoped,
permissionMode is process-scoped. Empty mcpServers does not clear ambient tools.
No raw JSON-RPC, subprocess creation, SDK spawn helper, login or default factory
is provided. The existing process owner must retain launch, limits and settlement.
Source-shaped fixtures qualify this consumer, not a live MiniMax execution path.
"""
from __future__ import annotations

import asyncio
import inspect
import threading

from ._async import drain_owned
from .contracts import CancelReceipt, ExecutionRequest, ExecutionResult, Observation, json_text


class MiniMaxAcpError(ValueError):
    """Stable non-secret error vocabulary."""


def _object(value):
    if hasattr(value, 'model_dump'):
        value = value.model_dump(by_alias=True, mode='json', exclude_none=True)
    if not isinstance(value, dict):
        raise MiniMaxAcpError('minimax_invalid_payload')
    return value


class MiniMaxAcpExchange:
    """One operation over an acquired ACP connection, never an OS process owner.

    The factory binds this object as the SDK client callback target. Public ACP
    methods use snake_case arguments and SDK responses are normalized with their
    wire aliases. Unknown client operations have no implementation/permission.
    """

    def __init__(self, *, assert_current):
        if not callable(assert_current) or inspect.iscoroutinefunction(assert_current):
            raise ValueError('explicit synchronous authority callback required')
        self.assert_current = assert_current
        self._used = False
        self._cancel = threading.Event()
        self._cancel_lock = asyncio.Lock()
        self._connection = self._request = None
        self._event_error = self._capture_error = None
        self._events = []
        self._bytes = 0
        self._text = ''
        self._configuration_ready = False
        self._phase = None
        self._setup_session_ids = set()
        self._config_options = {}
        self.session_id = None
        self.observed_model = self.observed_effort = None
        self.cancel_sent = self.cancel_acknowledged = False
        self.protocol_closed = False

    def request_cancel(self):
        self._cancel.set()

    async def cancel(self):
        self.request_cancel()
        async with self._cancel_lock:
            if self._connection is not None and self.session_id and not self.cancel_sent:
                await self._connection.cancel(session_id=self.session_id)
                self.cancel_sent = True  # A notification write is not acknowledgement.

    def _record(self, kind, value):
        encoded = json_text(_object(value))
        if len(self._events) >= self._request.max_events:
            self._capture_error = 'minimax_event_limit'
        elif self._bytes + len(encoded.encode()) > self._request.max_output_bytes:
            self._capture_error = 'minimax_output_limit'
        if self._capture_error:
            raise MiniMaxAcpError(self._capture_error)
        self._events.append(Observation(len(self._events), kind, encoded))
        self._bytes += len(encoded.encode())

    def _authority(self, effect):
        if self._cancel.is_set():
            raise MiniMaxAcpError('minimax_cancelled_before_effect')
        if self._event_error:
            raise MiniMaxAcpError(self._event_error)
        try:
            decision = self.assert_current(self._request, effect)
        except Exception:
            raise MiniMaxAcpError('minimax_authority_denied') from None
        if decision is not None:
            raise MiniMaxAcpError('minimax_invalid_authority_callback')

    async def _call(self, method, effect, **kwargs):
        self._authority(effect)
        self._phase = effect
        try:
            value = _object(await getattr(self._connection, method)(**kwargs))
        finally:
            self._phase = None
        if method == 'new_session':
            identity = value.get('sessionId')
            if not isinstance(identity, str) or not identity.strip() or len(identity.encode()) > 4096:
                raise MiniMaxAcpError('minimax_session_unavailable')
            # Preserve the acquired identity before capture can fail, for cleanup.
            self.session_id = identity
            if self._setup_session_ids - {identity}:
                self._event_error = self._event_error or 'minimax_session_mismatch'
        self._record(effect, value)
        if self._event_error:
            raise MiniMaxAcpError(self._event_error)
        return value

    def _config(self, response):
        options = response.get('configOptions')
        if not isinstance(options, list) or any(not isinstance(item, dict) or not isinstance(item.get('id'), str) for item in options):
            raise MiniMaxAcpError('minimax_config_unavailable')
        selected = {item['id']: item for item in options}
        if len(selected) != len(options):
            raise MiniMaxAcpError('minimax_invalid_config')
        self._config_options = selected
        self.observed_model = selected.get('model', {}).get('currentValue')
        self.observed_effort = selected.get('thinkingEffort', {}).get('currentValue')
        if self._configuration_ready and (self.observed_model, self.observed_effort) != (self._request.model, self._request.effort):
            raise MiniMaxAcpError('minimax_config_mismatch')

    def _require_option(self, key, value):
        option = self._config_options.get(key, {})
        options = option.get('options')
        if option.get('type') != 'select' or not isinstance(options, list) or not options:
            raise MiniMaxAcpError('minimax_config_unsupported')
        if any(not isinstance(item, dict) or not isinstance(item.get('value'), str) for item in options):
            raise MiniMaxAcpError('minimax_invalid_config')
        values = [item['value'] for item in options]
        if len(set(values)) != len(values) or value not in values:
            raise MiniMaxAcpError('minimax_config_unsupported')

    async def session_update(self, session_id, update, **kwargs):
        # SDK background handler exceptions need not fail the pending prompt;
        # latch failure explicitly and never turn it into a successful result.
        try:
            value = _object(update)
            self._record('session/update', {'sessionId': session_id, 'update': value})
            kind = value.get('sessionUpdate')
            if self.session_id is None and self._phase == 'session/new':
                if kind != 'available_commands_update':
                    raise MiniMaxAcpError('minimax_invalid_setup_update')
                if not isinstance(session_id, str) or not session_id.strip() or len(session_id.encode()) > 4096:
                    raise MiniMaxAcpError('minimax_session_mismatch')
                self._setup_session_ids.add(session_id)
                return
            if session_id != self.session_id or not self.session_id:
                raise MiniMaxAcpError('minimax_session_mismatch')
            if kind == 'config_option_update':
                self._config(value)
            elif kind == 'agent_message_chunk':
                content = value.get('content', {})
                if self._phase != 'session/prompt' or not self._configuration_ready or content.get('type') != 'text' or not isinstance(content.get('text'), str):
                    raise MiniMaxAcpError('minimax_invalid_content')
                text = content['text']
                if len(self._text.encode()) + len(text.encode()) > self._request.max_output_bytes:
                    self._capture_error = 'minimax_output_limit'
                    raise MiniMaxAcpError(self._capture_error)
                self._text += text
            elif kind not in {'agent_thought_chunk', 'user_message_chunk', 'tool_call', 'tool_call_update',
                              'plan', 'usage_update', 'available_commands_update', 'current_mode_update', 'session_info_update'}:
                raise MiniMaxAcpError('minimax_unknown_update')
        except MiniMaxAcpError as exc:
            self._event_error = self._event_error or str(exc)
        except Exception:
            self._event_error = self._event_error or 'minimax_invalid_payload'

    async def request_permission(self, session_id, tool_call, options, **kwargs):
        try:
            self._record('session/request_permission', {'sessionId': session_id,
                         'toolCall': _object(tool_call), 'options': [
                             _object(option) for option in options]})
            if session_id != self.session_id or not self.session_id:
                raise MiniMaxAcpError('minimax_session_mismatch')
            if self._phase != 'session/prompt':
                raise MiniMaxAcpError('minimax_invalid_permission_phase')
        except MiniMaxAcpError as exc:
            self._event_error = self._event_error or str(exc)
        except Exception:
            self._event_error = self._event_error or 'minimax_invalid_permission_payload'
        # Never select an allow option, open login, or change global permissionMode.
        return {'outcome': {'outcome': 'cancelled'}}

    async def run(self, request, connection):
        if not isinstance(request, ExecutionRequest) or request.provider != 'minimax':
            raise MiniMaxAcpError('unsupported_provider')
        if self._used:
            raise MiniMaxAcpError('operation_already_consumed')
        self._used = True
        self._request, self._connection = request, connection
        error = stop_reason = None
        session_closed = False
        try:
            for name in ('initialize', 'new_session', 'set_config_option', 'prompt', 'cancel', 'close_session', 'close'):
                if not callable(getattr(connection, name, None)):
                    raise MiniMaxAcpError('minimax_sdk_api_unavailable')
            initialized = await self._call('initialize', 'initialize', protocol_version=1, client_capabilities={})
            if type(initialized.get('protocolVersion')) is not int or initialized['protocolVersion'] != 1:
                raise MiniMaxAcpError('minimax_protocol_incompatible')
            if initialized.get('agentInfo', {}).get('name') != 'minimax-code':
                raise MiniMaxAcpError('minimax_agent_mismatch')
            if not isinstance(initialized.get('agentCapabilities', {}).get('sessionCapabilities', {}).get('close'), dict):
                raise MiniMaxAcpError('minimax_close_unavailable')
            # No terminal-auth capability or authenticate: login is separate.
            created = await self._call('new_session', 'session/new', cwd=request.cwd, mcp_servers=[])
            identity = created.get('sessionId')
            if not isinstance(identity, str) or not identity.strip() or len(identity.encode()) > 4096:
                raise MiniMaxAcpError('minimax_session_unavailable')
            self.session_id = identity
            self._config(created)
            for key, value in (('model', request.model), ('thinkingEffort', request.effort)):
                self._require_option(key, value)
                response = await self._call('set_config_option', 'session/set_config_option',
                                            session_id=identity, config_id=key, value=value)
                self._config(response)
                if self._config_options.get(key, {}).get('currentValue') != value:
                    raise MiniMaxAcpError('minimax_config_mismatch')
            self._configuration_ready = True
            self._config(response)
            response = await self._call('prompt', 'session/prompt', session_id=identity,
                                        prompt=[{'type': 'text', 'text': request.prompt}])
            stop_reason = response.get('stopReason')
            if stop_reason not in {'end_turn', 'cancelled', 'refusal', 'max_tokens', 'max_turn_requests'}:
                raise MiniMaxAcpError('minimax_invalid_stop_reason')
            self.cancel_acknowledged = self.cancel_sent and stop_reason == 'cancelled'
        except MiniMaxAcpError as exc:
            error = str(exc)
        except Exception:
            error = 'minimax_protocol_failed'
        finally:
            if self.session_id:
                try:
                    closed = await connection.close_session(session_id=self.session_id)
                    if closed is not None:
                        self._record('session/close', closed)
                    session_closed = True
                except Exception:
                    session_closed = False
            try:
                await connection.close()
                self.protocol_closed = session_closed
            except Exception:
                self.protocol_closed = False
        return ExecutionResult(request, 'interrupted' if self._cancel.is_set() or stop_reason == 'cancelled' else 'incomplete',
            provider_status={'end_turn': 'completed', 'cancelled': 'interrupted', 'refusal': 'failed'}.get(stop_reason),
            actual_execution_path='direct-external-cli', native_result_text=self._text if self._text.strip() else None,
            native_thread_id=self.session_id, observations=tuple(self._events), protocol_closed=self.protocol_closed,
            capture_error=self._capture_error, cleanup_error='minimax_process_settlement_unavailable',
            execution_error=error or self._event_error or 'minimax_account_readback_unavailable')


def _require_live_minimax_binding(request):
    # Empty session MCP does not clear ambient runtime tools. permissionMode is
    # process-global. Native Node/entry attestation, account/subscription readback,
    # bounded SDK connection and existing process-owner composition are unqualified.
    raise MiniMaxAcpError('minimax_live_binding_unqualified')


class MiniMaxAcpAdapter:
    """Held executor seam; the factory must not acquire anything before admission."""

    def __init__(self, *, client_factory, assert_current):
        if not callable(client_factory) or inspect.iscoroutinefunction(client_factory):
            raise ValueError('explicit synchronous connection factory required')
        self._factory = client_factory
        self.exchange = MiniMaxAcpExchange(assert_current=assert_current)
        self._request = self.execution_result = None

    async def execute(self, request):
        if not isinstance(request, ExecutionRequest) or request.provider != 'minimax':
            raise MiniMaxAcpError('unsupported_provider')
        _require_live_minimax_binding(request)
        if self._request is not None:
            raise MiniMaxAcpError('operation_already_consumed')
        self._request = request
        self.exchange._request = request
        self.exchange._authority('acquire_connection')
        connection = self._factory(self.exchange)
        if inspect.isawaitable(connection):
            if inspect.iscoroutine(connection):
                connection.close()
            raise MiniMaxAcpError('minimax_async_factory_not_supported')
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
            return CancelReceipt(run_id, True, False, error='minimax_cancel_failed', native_thread_id=self.exchange.session_id)
        return CancelReceipt(run_id, True, self.exchange.cancel_acknowledged, native_thread_id=self.exchange.session_id)
