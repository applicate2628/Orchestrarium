"""Offline Copilot fixtures that never start the native process or SDK."""
import asyncio
from dataclasses import replace
import os
import time
from types import SimpleNamespace
from unittest.mock import patch

from process_supervision import process_runner as processes
from sdk_execution import copilot, runtime
from sdk_execution.contracts import json_text
from sdk_execution.worker import ObservationSink, read_execute_envelope, serve_operation


def payload(**changes):
    values=dict(run_id='evidence',artifact_id='advice.json',role='consultant',content='Bounded advice.')
    values.update(changes)
    return values


class FakeSdk:
    def __init__(self):
        self.calls=[]; self.options=None; self.runtime=None; self.send_options=None
        self.history=[]; self.turn='native-turn'
        self.content=json_text(payload()); self.failure=None; self.cleanup_failure=None
        self.events=[]; self.permission=False; self.handler=None; self.on_send=None
        self.profile_model='selected-model'; self.profile_effort='high'
        self.rpc=SimpleNamespace(model=SimpleNamespace(get_current=self.get_current))
        self.session_id='native-session'; self.agent_id=None; self.reply_none=False
        self.RuntimeConnection=SimpleNamespace(for_spawned_stdio=self.connection)
        self.AgentMessageSource=lambda identity: SimpleNamespace(agent_id=identity)
        self.PermissionDecisionReject=lambda **kw: SimpleNamespace(kind='reject',**kw)
    def connection(self,**kwargs):
        self.calls.append('runtime'); self.runtime=kwargs; return kwargs
    def CopilotClient(self,**kwargs):
        self.calls.append('client'); self.client_options=kwargs; return self
    async def start(self):
        self.calls.append('start')
        if self.failure=='start': raise RuntimeError('private startup error')
    async def create_session(self,**kwargs):
        self.calls.append('create'); self.options=kwargs
        if self.failure=='create': raise RuntimeError('private create error')
        return self
    def on(self,handler):
        self.handler=handler
        return lambda: self.calls.append('unsubscribe')
    async def send_and_wait(self,prompt,**kwargs):
        self.calls.append('send'); self.prompt=prompt; self.send_options=kwargs
        if self.on_send: await self.on_send()
        if self.permission:
            self.permission_result=self.options['permissions']['on_request']({}, {})
        for event in self.events: self.handler(event)
        if self.failure=='send': raise RuntimeError('private send error')
        if self.failure=='timeout': raise TimeoutError()
        if self.reply_none:return None
        final=SimpleNamespace(type='assistant.message',id='message-'+self.turn,agent_id=self.agent_id,
            data=SimpleNamespace(content=self.content,turn_id=self.turn))
        if type(self).get_events is FakeSdk.get_events:
            def event(kind):
                return SimpleNamespace(type=kind,id=kind+'-'+self.turn,agent_id=None,
                    data=SimpleNamespace(turn_id=self.turn))
            self.history.extend((event('assistant.turn_start'),final,event('assistant.turn_end')))
        return final
    async def get_events(self):
        self.calls.append('history')
        return list(self.history)
    async def resume_session(self,session_id,**kwargs):
        self.calls.append('resume'); self.options=kwargs
        assert session_id==self.session_id
        assert kwargs['continue_pending_work'] is False and kwargs['allow_transcript_recovery'] is False
        return self
    async def get_current(self,*,timeout):
        self.calls.append('profile')
        return SimpleNamespace(model_id=self.profile_model,reasoning_effort=self.profile_effort,provider_id=None)
    async def abort(self):
        self.calls.append('abort')
        if self.cleanup_failure=='abort':raise RuntimeError('private abort error')
    async def disconnect(self):
        self.calls.append('disconnect')
        if self.cleanup_failure=='disconnect':raise RuntimeError('private disconnect error')
    async def stop(self):
        self.calls.append('stop')
        if self.cleanup_failure=='stop':raise RuntimeError('private stop error')


def simulate_worker_process(process_request, *, dialogue, requests, output_frames=None):
    """Exchange real protocol frames at the synthetic process boundary."""
    async def exchange():
        loop = asyncio.get_running_loop()
        controls = asyncio.Queue()
        output = asyncio.Queue()

        class Channel:
            def write_line(self, value):
                loop.call_soon_threadsafe(controls.put_nowait, value)

            def read_line(self):
                frame = asyncio.run_coroutine_threadsafe(output.get(), loop).result(timeout=30)
                if frame is None:
                    raise EOFError()
                return frame

        class Frames:
            async def write(self, value):
                if output_frames is not None:
                    output_frames.append(value)
                await output.put(value)

        async def serve():
            try:
                request, raw_selection = read_execute_envelope(await controls.get())
                requests.append(request)
                selection = runtime.runtime_selection_from_dict("copilot", raw_selection)
                frames = Frames()
                sink = ObservationSink(request, frames)
                executor = copilot.create_copilot_adapter(request, sink, selection)
                await serve_operation(request, executor, controls.get, frames.write,
                                      authority_sink=sink)
            finally:
                await output.put(None)

        worker_error, parent_error = await asyncio.gather(
            asyncio.wait_for(serve(), 30),
            asyncio.to_thread(dialogue.handler, Channel()), return_exceptions=True)
        if worker_error is not None:
            raise worker_error
        if parent_error is not None:
            raise parent_error

    # Mirror the worker environment and transport while using both protocol owners.
    environment = {row.name: row.value for row in process_request.environment}
    with patch.dict(os.environ, environment):
        asyncio.run(exchange())
    failed = processes._request_failure(process_request,
        processes.ProcessSupervisionError("PSV1-INTERNAL", "execution"), time.monotonic())
    return replace(failed, outcome="success", terminal_stage="completed",
        failure_id=None, target_exit_code=0, resources_closed=True, policy_id="sdk-worker-v1",
        tree=processes.TreeObservationV1("synthetic", True, "EMPTY", True, True, True, True))
