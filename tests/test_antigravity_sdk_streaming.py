"""Installed AGY bridge with real Codex stream parsing and canonical receiving.
Native Windows platform admission, vendor transport, hook-health probe and process custody are synthetic.
This does not launch an AGY session, a provider SDK, or a model.
"""
import asyncio
from dataclasses import replace
import json
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys
import time

from test_antigravity_sdk_bridge_e2e import installed_bridge
import test_sdk_installed_dispatch as existing
from test_sdk_codex_stream_receiving import StreamingClient


def test_installed_agy_consultant_stream_and_continuation(installed_bridge, monkeypatch, capsys):
    project, target, owner = installed_bridge
    from sdk_execution import codex, dispatch, runtime
    from sdk_execution.contracts import ExecutionRequest
    from sdk_execution.worker import encode_frame
    from process_supervision import sdk_worker, process_runner as processes
    assert Path(codex.__file__).is_relative_to(target)
    assert Path(runtime.__file__).is_relative_to(target)
    assert Path(dispatch.__file__).is_relative_to(target)
    # This portable integration exercises the Windows route with synthetic native custody.
    # The separate unsupported-platform test retains the real POSIX refusal.
    monkeypatch.setattr(dispatch, '_require_supported_platform', lambda: None)
    item, receipt, artifact, captures, argv = existing.setup_source(project, monkeypatch)
    argv[argv.index('--sdk-review-binding')] = '--sdk-task-binding'
    argv[argv.index('--ledger-role') + 1] = 'consultant'
    binding = Path(argv[argv.index('--sdk-task-binding') + 1])
    data = json.loads(binding.read_text())
    data.update(schemaVersion=3, installedHookRoot=None, contextMode='fresh', contextHandoff=None,
                maxEvents=ExecutionRequest.__dataclass_fields__['max_events'].default)
    binding.write_text(json.dumps(data))
    monkeypatch.setattr(owner, 'require_codex_hook_trust', lambda *a, **k: 0)
    package = ModuleType('openai_codex')
    client_module = ModuleType('openai_codex.client')
    client_module.CodexConfig = lambda **values: SimpleNamespace(**values)
    monkeypatch.setitem(sys.modules, 'openai_codex', package)
    monkeypatch.setitem(sys.modules, 'openai_codex.client', client_module)
    real_worker = sdk_worker.run_sdk_worker
    clients = []

    def stream_worker(process, request, **kwargs):
        selection = runtime.runtime_selection_from_dict('codex', kwargs['runtime_selection'])
        client = StreamingClient(request, 'Remembered amber. This is synthetic advice.', 'turn-' + str(len(clients)))
        clients.append(client)
        def bind(config, handler):
            assert config.codex_bin == selection.executable
            client.handler = handler
            return codex.ClientBinding(client, '0.170.0', client.read_configuration, client.list_mcp_status)
        with monkeypatch.context() as patch:
            patch.setattr(codex, '_official_client_binding', bind)
            patch.setattr(os, 'environ', {row.name: row.value for row in kwargs['environment']})
            sink = SimpleNamespace(authorize_from_thread=kwargs['authority'], record_from_thread=lambda row: None)
            result = asyncio.run(runtime.create_codex_adapter(request, sink, selection).execute(request))
        assert result.status == 'completed', (result.execution_error, result.capture_error)
        assert client.notifications_delivered > 100
        def native_process(process_request, *, dialogue):
            frames = iter([*(encode_frame({'kind':'observation', 'run_id':request.run_id,
                'observation':row.to_dict()}) for row in result.observations),
                encode_frame({'kind':'result', 'result':result.to_dict()})])
            class Channel:
                def write_line(self, value): pass
                def read_line(self):
                    frame = next(frames, None)
                    if frame is None: raise EOFError()
                    return frame
            dialogue.handler(Channel())
            failure = processes._request_failure(process_request,
                processes.ProcessSupervisionError('PSV1-INTERNAL', 'execution'), time.monotonic())
            return replace(failure, outcome='success', terminal_stage='completed', failure_id=None,
                target_exit_code=0, resources_closed=True, policy_id='sdk-worker-v1',
                tree=processes.TreeObservationV1('synthetic', True, 'EMPTY', True, True, True, True))
        with monkeypatch.context() as patch:
            patch.setattr(process, 'run', native_process)
            return real_worker(process, request, **kwargs)
    monkeypatch.setattr(sdk_worker, 'run_sdk_worker', stream_worker)

    assert existing.entrypoint()(argv) == 0
    output = capsys.readouterr()
    first = owner.parse_provider_result(output.out)
    assert first['status'] == 'completed' and first['gate'] == 'none' and first['authorizing'] is False
    assert receipt.read_text() == output.out
    first_native = json.loads(artifact.read_text())['native_continuation']
    data.update(schemaVersion=5, contextMode='continuation', artifactIdentity='continued-advice',
                predecessorEvidenceRunId=first['externalEvidenceRunId'])
    binding.write_text(json.dumps(data))
    argv[argv.index('--ledger-artifact') + 1] = 'continued.json'
    argv[argv.index('--terminal-receipt') + 1] = str(project / 'continued-terminal.json')
    assert existing.entrypoint()(argv) == 0
    second = owner.parse_provider_result(capsys.readouterr().out)
    assert second['status'] == 'completed' and second['authorizing'] is False
    second_native = json.loads((item/'continued.json').read_text())['native_continuation']
    assert first_native['thread_id'] == second_native['thread_id']
    assert first_native['turn_id'] != second_native['turn_id']
    assert first_native['context_sha256'] == second_native['context_sha256']
    assert first_native['session_depth'] == second_native['session_depth']
    rows = [json.loads(line) for line in (item/'agent-runs.jsonl').read_text().splitlines()]
    assert [r['eventKind'] for r in rows] == ['launch','terminal','launch','terminal']
    assert len(clients) == 2 and 'thread_resume' in [c[0] for c in clients[1].calls]
    before = (item/'agent-runs.jsonl').read_bytes()
    assert existing.entrypoint()(argv) == 1
    capsys.readouterr()
    assert len(clients) == 2 and (item/'agent-runs.jsonl').read_bytes() == before
    assert not list(captures.iterdir())
