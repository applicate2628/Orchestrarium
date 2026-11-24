"""Fake client dictionary reuse must not rewrite captured SDK evidence."""
import asyncio
import json
import pytest
from tests.test_sdk_codex import (FakeClient, adapter, answer, event, execute,
                                  request, review_payload, successful_events)


def usage_payload():
    counts = {'inputTokens': 9, 'cachedInputTokens': 4, 'outputTokens': 3,
              'reasoningOutputTokens': 2, 'totalTokens': 12}
    return {'last': dict(counts), 'total': dict(counts)}


def test_usage_summary_uses_captured_notification_snapshot():
    usage = usage_payload()
    client = FakeClient([event('thread/tokenUsage/updated', {
        'threadId': 'thread-1', 'turnId': 'turn-1', 'tokenUsage': usage}), *successful_events()])
    calls = 0
    def mutate():
        nonlocal calls
        calls += 1
        if calls == 2:
            usage['total']['inputTokens'] = 900
    client.on_next = mutate
    result, _ = execute(client)
    captured = next(json.loads(o.payload_json)['tokenUsage'] for o in result.observations
                    if o.kind == 'thread/tokenUsage/updated')
    assert result.status == 'completed'
    assert result.usage == captured
    assert result.usage['total']['inputTokens'] == 9


@pytest.mark.parametrize('timing', ['next_event', 'evidence_sink'])
def test_mutated_completed_item_cannot_rewrite_captured_verdict(timing):
    item = answer(review_payload(verdict='REVISE'))
    client = FakeClient(successful_events(item))
    calls = 0
    def mutate_next():
        nonlocal calls
        calls += 1
        if calls == 2:
            item['text'] = json.dumps(review_payload(verdict='PASS'))
    def sink(observation):
        if observation.kind == 'item/completed':
            item['text'] = json.dumps(review_payload(verdict='PASS'))
    if timing == 'next_event':
        client.on_next = mutate_next
    result, _ = execute(client, sink=sink if timing == 'evidence_sink' else None)
    assert result.review is None
    assert result.execution_error == 'contradictory_terminal_item'
    captured = next(json.loads(o.payload_json)['item']['text'] for o in result.observations
                    if o.kind == 'item/completed')
    assert json.loads(captured)['verdict'] == 'REVISE'
    assert ('close',) in client.calls


def test_history_interpretation_uses_recorded_snapshot():
    client = FakeClient()
    item = client.history['thread']['turns'][0]['items'][0]
    item['text'] = json.dumps(review_payload(verdict='REVISE'))
    def sink(observation):
        if observation.kind == 'thread/read':
            item['text'] = json.dumps(review_payload(verdict='PASS'))
    instance, _ = adapter(client, sink=sink, resume=lambda *args: None)
    result = asyncio.run(instance.reconcile(request(), thread_id='thread-1', turn_id='turn-1'))
    assert result.status == 'completed'
    assert result.review.verdict == 'REVISE'
    assert not any(call[0] == 'turn_start' for call in client.calls)


def test_failed_turn_capture_still_interrupts_bound_started_turn():
    def sink(observation):
        if observation.kind == 'turn/start':
            raise RuntimeError('synthetic sink failure')
    result, client = execute(sink=sink)
    assert result.review is None
    assert result.capture_error == 'evidence_sink_failed'
    assert ('interrupt', 'thread-1', 'turn-1') in client.calls
    assert ('close',) in client.calls


@pytest.mark.parametrize('kind', ['initialize', 'thread/start'])
def test_setup_interprets_the_same_snapshot_as_its_evidence(kind):
    class ReusingClient(FakeClient):
        def initialize(self):
            self.initialized = super().initialize()
            return self.initialized
        def thread_start(self, params):
            self.started = super().thread_start(params)
            return self.started
    client = ReusingClient()
    def sink(observation):
        if observation.kind == kind:
            if kind == 'initialize':
                client.initialized['serverInfo']['version'] = '9.9.9'
                client.initialized['userAgent'] = 'codex/9.9.9'
            else:
                client.started['thread']['id'] = 'mutated-thread'
    result, _ = execute(client, sink=sink)
    assert result.status == 'completed'
    assert result.native_thread_id == 'thread-1'
    assert result.sdk_execution['runtimeVersion'] == '0.163.0'
