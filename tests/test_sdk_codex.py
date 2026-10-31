"""Offline public-API fixtures only. These never import or launch provider SDKs."""
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sdk_execution.contracts import (
    ExecutionRequest, ExecutionResult, Finding, Observation, ReviewResult, strict_json,
    validate_review,
)
from sdk_execution.codex import (
    AdapterError, ClientBinding, CodexReviewAdapter, _official_client_binding,
)
from sdk_execution.codex_tools import CodexMcpScope


def request(**changes):
    value = ExecutionRequest(
        work_item_id="item-1", provider="codex", external_dispatch_id="dispatch-1",
        external_evidence_run_id="evidence-1", artifact_id="review.md", role="architecture-reviewer",
        model="fixture-model", effort="high", cwd="/fixture/repo", account_binding="fixture-account",
        prompt="Review the admitted artifact read-only.", coordinator_binding="coordinator-1", scope=("review",),
    )
    return replace(value, **changes)


def review_payload(**changes):
    value = {"run_id": "evidence-1", "artifact_id": "review.md", "role": "architecture-reviewer", "verdict": "PASS", "findings": []}
    value.update(changes)
    return value


def answer(payload=None):
    return {"type": "agentMessage", "id": "item-1", "phase": "final_answer", "text": json.dumps(payload or review_payload())}


def command_item(**changes):
    # Official CommandExecutionThreadItem wire shape; no provider process runs.
    value = {"type": "commandExecution", "id": "command-1", "command": "read fixture",
             "commandActions": [], "cwd": "/fixture/repo", "status": "completed",
             "exitCode": 0, "aggregatedOutput": "fixture output"}
    value.update(changes)
    return value


def event(method, payload):
    return {"method": method, "payload": payload}


def completed(status="completed", items=None, **changes):
    turn = {"id": "turn-1", "status": status, "items": [answer()] if items is None else items, "itemsView": "summary" if status == "completed" else "notLoaded"}
    turn.update(changes)
    return event("turn/completed", {"threadId": "thread-1", "turn": turn})


def item_completed(item=None):
    return event("item/completed", {"threadId":"thread-1", "turnId":"turn-1", "completedAtMs":0, "item":answer() if item is None else item})


def successful_events(item=None):
    item = answer() if item is None else item
    return [item_completed(item), completed(items=[item])]


class FakeClient:
    def __init__(self, events=None):
        self.events = list(events if events is not None else successful_events())
        self.calls = []
        self.handler = None
        self.profile_change = {}
        self.close_error = False
        self.unregister_error = False
        self.version = "0.163.0"
        self.configuration = {"config": {"features": {"plugins": False, "apps": False, "multi_agent_v2": False}, "agents": {"enabled": False}, "mcp_servers": {}}}
        self.mcp_pages = {}
        self.account = {"account": {"type": "chatgpt", "email": "fixture@example.invalid"}}
        self.on_start = None
        self.on_turn = None
        self.on_next = None
        self.history = {"thread": {"id": "thread-1", "turns": [completed(itemsView="full")["payload"]["turn"]]}}

    def start(self):
        self.calls.append(("start",))
        if self.on_start:
            self.on_start()

    def initialize(self):
        return {"serverInfo": {"name": "codex", "version": self.version}, "userAgent": f"codex/{self.version}"}

    def account_read(self, params):
        self.calls.append(("account_read", params))
        return self.account

    def read_configuration(self, params):
        self.calls.append(("config/read", params))
        return self.configuration

    def list_mcp_status(self, params):
        self.calls.append(("mcpServerStatus/list", params))
        return self.mcp_pages.get((params.get("serverName"), params.get("cursor")),
                                  {"data": [], "nextCursor": None})

    def request(self, method, params, *, response_model):
        value = self.read_configuration(params) if method == "config/read" else self.list_mcp_status(params)
        return response_model.model_validate(value)

    def thread_start(self, params):
        self.calls.append(("thread_start", params))
        result = {"thread": {"id": "thread-1"}, "model": "fixture-model", "reasoningEffort": "high", "modelProvider": "openai", "cwd": "/fixture/repo", "approvalPolicy": "never", "approvalsReviewer": "user", "sandbox": {"type": "readOnly", "networkAccess": False}}
        result.update(self.profile_change)
        return result

    def thread_resume(self, thread_id, params):
        self.calls.append(("thread_resume", thread_id, params))
        return self.thread_start(params)

    def thread_read(self, thread_id, include_turns=False):
        self.calls.append(("thread_read", thread_id, include_turns))
        return self.history

    def turn_start(self, thread_id, input_items, params):
        self.calls.append(("turn_start", thread_id, input_items, params))
        if self.on_turn:
            self.on_turn()
        return {"turn": {"id": "turn-1", "status": "inProgress", "items": []}}

    def next_turn_notification(self, turn_id):
        if self.on_next:
            self.on_next()
        if not self.events:
            raise EOFError("synthetic transport closed")
        return self.events.pop(0)

    def turn_interrupt(self, thread_id, turn_id):
        self.calls.append(("interrupt", thread_id, turn_id))
        return {}

    def unregister_turn_notifications(self, turn_id):
        self.calls.append(("unregister", turn_id))
        if self.unregister_error:
            raise OSError("synthetic unregister failure")

    def close(self):
        self.calls.append(("close",))
        if self.close_error:
            raise OSError("synthetic close failure")


def adapter(client=None, authority=None, verify=None, sink=None, sdk_version="0.163.0", resume=None, mcp_scope=CodexMcpScope(()), bounded_startup_profile=False):
    client = client or FakeClient()
    def factory(handler):
        client.handler = handler
        return ClientBinding(client, sdk_version, client.read_configuration, client.list_mcp_status)
    return CodexReviewAdapter(client_factory=factory, assert_current=authority or (lambda req, effect: None), verify_account=verify or (lambda req, data: req.account_binding), record=sink or (lambda obs: None), authorize_resume=resume, mcp_scope=mcp_scope, bounded_startup_profile=bounded_startup_profile), client


def execute(client=None, **kwargs):
    instance, client = adapter(client, **kwargs)
    return asyncio.run(instance.execute(request())), client


def test_structured_success_exact_native_configuration_and_non_authority():
    captured = []
    result, client = execute(sink=captured.append)
    assert result.status == result.provider_status == "completed"
    assert result.review == ReviewResult.from_dict(review_payload())
    assert result.protocol_closed and result.usage is None
    assert result.sdk_execution["sdkVersion"] == "0.163.0"
    assert captured == list(result.observations)
    assert result.to_tool_output()["authoritative"] is False
    assert result.to_tool_output()["process_settlement"] == "not_established"
    thread = next(c[1] for c in client.calls if c[0] == "thread_start")
    turn = next(c[3] for c in client.calls if c[0] == "turn_start")
    assert thread["approvalPolicy"] == turn["approvalPolicy"] == "never"
    assert thread["approvalsReviewer"] == turn["approvalsReviewer"] == "user"
    assert thread["sandbox"] == "read-only"
    assert turn["sandboxPolicy"] == {"type": "readOnly", "networkAccess": False}
    assert turn["outputSchema"]["properties"]["run_id"]["enum"] == ["evidence-1"]
    assert all("fixture@example.invalid" not in obs.payload_json for obs in result.observations)
    assert "launchFlags" not in result.sdk_execution


@pytest.mark.parametrize("change", [
    {"model": "other"}, {"reasoningEffort": "medium"}, {"cwd": "/other"},
    {"approvalPolicy": "on-request"}, {"approvalsReviewer": "auto_review"},
    {"sandbox": {"type": "readOnly", "networkAccess": True}}, {"modelProvider": "other"},
])
def test_profile_drift_blocks_turn(change):
    client = FakeClient(); client.profile_change = change
    client.version = "1000.0.0"
    result, client = execute(client, sdk_version="999.0.0")
    assert result.execution_error == "observed_profile_mismatch"
    assert result.status == "incomplete"
    assert not any(c[0] == "turn_start" for c in client.calls)
    assert result.protocol_closed


@pytest.mark.parametrize("sdk_version,runtime_version", [
    ("0.153.0", "0.164.0"), ("1!999.1.0", "1000.2.0-dev+fixture"),
    ("1" * 128, "1000.2.0"),
])
def test_compatible_versions_are_recorded_without_release_admission(sdk_version, runtime_version):
    client = FakeClient(); client.version = runtime_version
    result, client = execute(client, sdk_version=sdk_version)
    assert result.status == result.provider_status == "completed"
    assert result.sdk_execution["sdkVersion"] == sdk_version
    assert result.sdk_execution["runtimeVersion"] == runtime_version
    assert result.review == ReviewResult.from_dict(review_payload())


@pytest.mark.parametrize("version", [None, False, 0, {}, [], "", " \t\n", " 1.0", "1.0\n", "1.0\x00", "1" * 129])
def test_malformed_runtime_version_fails_before_account_and_thread(version):
    client = FakeClient(); client.version = version
    result, client = execute(client)
    assert result.execution_error == "invalid_runtime_version"
    assert not any(c[0] in {"account_read", "thread_start", "turn_start"} for c in client.calls)
    assert result.status == "incomplete" and result.protocol_closed
    assert result.observations[0].kind == "initialize"


@pytest.mark.parametrize("version", [None, False, 0, {}, [], "", " \t\n", " 1.0", "1.0\n", "1.0\x00", "1" * 129])
def test_malformed_sdk_version_fails_before_start(version):
    result, client = execute(sdk_version=version)
    assert result.execution_error == "invalid_sdk_version"
    assert ("start",) not in client.calls
    assert result.status == "incomplete" and result.sdk_execution is None


@pytest.mark.parametrize("method", [
    "start", "initialize", "account_read", "thread_start", "turn_start", "next_turn_notification",
    "unregister_turn_notifications", "turn_interrupt", "close",
])
def test_required_public_sdk_surface_is_callable_before_start(method):
    client = FakeClient()
    setattr(client, method, None)
    result, client = execute(client, sdk_version="999.0.0")
    assert result.execution_error == "missing_sdk_api"
    assert not any(c[0] in {"start", "account_read", "thread_start", "turn_start"} for c in client.calls)
    assert result.status == "incomplete" and not result.observations


def test_absent_public_sdk_method_is_rejected_before_start(monkeypatch):
    monkeypatch.delattr(FakeClient, "account_read")
    result, client = execute()
    assert result.execution_error == "missing_sdk_api"
    assert ("start",) not in client.calls


@pytest.mark.parametrize("method,replacement", [
    ("initialize", lambda required: None),
    ("account_read", lambda: None),
    ("turn_start", lambda thread_id, input_items: None),
])
def test_changed_public_call_signature_is_rejected_before_start(method, replacement):
    client = FakeClient(); setattr(client, method, replacement)
    result, client = execute(client)
    assert result.execution_error == "incompatible_sdk_api"
    assert ("start",) not in client.calls


@pytest.mark.parametrize("method", ["turn_start", "close"])
@pytest.mark.parametrize("as_generator", [False, True])
def test_async_public_methods_are_rejected_without_unawaited_coroutines(method, as_generator, recwarn):
    import gc

    async def coroutine(*args, **kwargs):
        raise AssertionError("asynchronous SDK method must not be invoked")

    async def generator(*args, **kwargs):
        yield "asynchronous SDK method must not be invoked"

    client = FakeClient()
    setattr(client, method, generator if as_generator else coroutine)
    result, client = execute(client)
    gc.collect()
    assert result.execution_error == "incompatible_sdk_api"
    assert ("start",) not in client.calls
    assert result.protocol_closed is (method != "close")
    assert result.cleanup_error == ("protocol_close_failed" if method == "close" else None)
    assert not any(issubclass(warning.category, RuntimeWarning) for warning in recwarn)


def test_fresh_execution_does_not_require_unused_resume_api():
    client = FakeClient(); client.thread_resume = client.thread_read = None
    result, _ = execute(client)
    assert result.status == "completed"


def test_reconciliation_does_not_require_unused_turn_creation_api():
    client = FakeClient()
    client.thread_start = client.turn_start = client.next_turn_notification = None
    # FakeClient.thread_resume delegates to thread_start only as fixture reuse.
    client.thread_resume = lambda thread_id, params: FakeClient.thread_start(client, params)
    instance, _ = adapter(client, resume=lambda *args: None)
    result = asyncio.run(instance.reconcile(request(), thread_id="thread-1", turn_id="turn-1"))
    assert result.status == "completed"


@pytest.mark.parametrize("method,replacement,error", [
    ("thread_resume", None, "missing_sdk_api"),
    ("thread_read", None, "missing_sdk_api"),
    ("thread_read", lambda thread_id: None, "incompatible_sdk_api"),
])
def test_reconciliation_checks_required_api_before_start(method, replacement, error):
    client = FakeClient(); setattr(client, method, replacement)
    instance, _ = adapter(client, resume=lambda *args: None)
    result = asyncio.run(instance.reconcile(request(), thread_id="thread-1", turn_id="turn-1"))
    assert result.execution_error == error
    assert ("start",) not in client.calls


@pytest.mark.parametrize("metadata,version", [
    ({"userAgent": "codex/999.1.0 (fixture)"}, "999.1.0"),
    ({"serverInfo": None, "userAgent": "codex 999.2.0 (fixture)"}, "999.2.0"),
])
def test_documented_user_agent_version_is_provenance_when_server_info_absent(metadata, version):
    client = FakeClient(); client.initialize = lambda: metadata
    result, _ = execute(client)
    assert result.status == "completed"
    assert result.sdk_execution["runtimeVersion"] == version


@pytest.mark.parametrize("metadata", [
    {}, {"userAgent": None}, {"userAgent": 1}, {"userAgent": "codex"},
    {"userAgent": "codex/ "},
    {"serverInfo": {}, "userAgent": "codex/999.1.0"},
    {"serverInfo": "malformed", "userAgent": "codex/999.1.0"},
    {"serverInfo": {"version": ""}, "userAgent": "codex/999.1.0"},
])
def test_malformed_initialize_metadata_cannot_fall_back_to_admission(metadata):
    client = FakeClient(); client.initialize = lambda: metadata
    result, client = execute(client)
    assert result.execution_error == "invalid_runtime_version"
    assert not any(c[0] in {"account_read", "thread_start", "turn_start"} for c in client.calls)


@pytest.fixture
def official_sdk_fixture(monkeypatch):
    """Only synthetic module objects: no provider package import or execution."""
    import importlib.metadata

    fixture = SimpleNamespace(version="999.0.0", constructions=[])

    class Config:
        codex_bin = "/fixture/codex"
        launch_args_override = None

    class Client(FakeClient):
        def __init__(self, *, config, approval_handler):
            super().__init__()
            fixture.constructions.append((config, approval_handler))

    module = SimpleNamespace(CodexConfig=Config, CodexClient=Client)
    monkeypatch.setitem(sys.modules, "openai_codex", SimpleNamespace(client=module))
    monkeypatch.setitem(sys.modules, "openai_codex.client", module)

    class Response:
        @classmethod
        def model_validate(cls, value):
            return value
    generated = SimpleNamespace(ConfigReadResponse=Response, ListMcpServerStatusResponse=Response)
    monkeypatch.setitem(sys.modules, "openai_codex.generated", SimpleNamespace(v2_all=generated))
    monkeypatch.setitem(sys.modules, "openai_codex.generated.v2_all", generated)

    def version(distribution):
        assert distribution == "openai-codex"
        return fixture.version

    monkeypatch.setattr(importlib.metadata, "version", version)
    fixture.config, fixture.client_class = Config(), Client
    return fixture


def test_official_factory_records_different_version_without_launch(official_sdk_fixture):
    handler = lambda *args: {"decision": "cancel"}
    binding = _official_client_binding(official_sdk_fixture.config, handler)
    assert binding.sdk_version == "999.0.0"
    assert official_sdk_fixture.constructions == [(official_sdk_fixture.config, handler)]
    assert not binding.client.calls


def test_official_factory_rejects_changed_constructor_before_construction(official_sdk_fixture, monkeypatch):
    monkeypatch.setattr(official_sdk_fixture.client_class, "__init__", lambda self, config: None)
    with pytest.raises(AdapterError, match="incompatible_sdk_api"):
        _official_client_binding(official_sdk_fixture.config, lambda *args: {})
    assert not official_sdk_fixture.constructions


def test_official_factory_rejects_malformed_version_before_construction(official_sdk_fixture):
    official_sdk_fixture.version = " "
    with pytest.raises(AdapterError, match="invalid_sdk_version"):
        _official_client_binding(official_sdk_fixture.config, lambda *args: {})
    assert not official_sdk_fixture.constructions


def test_account_binding_requires_observed_owner_verification():
    result, client = execute(verify=lambda req, data: "other-account")
    assert result.execution_error == "account_binding_mismatch"
    assert not any(c[0] == "thread_start" for c in client.calls)


def test_current_authority_rechecked_before_turn():
    def authority(req, effect):
        if effect == "turn_start":
            raise PermissionError("revoked")
    result, client = execute(authority=authority)
    assert result.status == "incomplete"
    assert not any(c[0] == "turn_start" for c in client.calls)


@pytest.mark.parametrize("payload", [review_payload(run_id="wrong"), review_payload(findings=[{"severity":"high","path":"a.py","line":1,"message":"bug"}]), {**review_payload(), "extra": 1}, review_payload(verdict="UNKNOWN")])
def test_invalid_structured_review_keeps_native_completion(payload):
    result, _ = execute(FakeClient(successful_events(answer(payload))))
    assert result.status == "incomplete" and result.provider_status == "completed"
    assert result.review is None and result.execution_error
    assert any(o.kind == "turn/completed" for o in result.observations)


def test_failed_turn_and_cleanup_errors_are_both_retained():
    client = FakeClient([completed("failed", items=[], error={"message": "synthetic failure"})])
    client.close_error = client.unregister_error = True
    result, _ = execute(client)
    assert result.status == result.provider_status == "failed"
    assert result.execution_error == "provider_turn_failed"
    assert result.cleanup_error == "notification_cleanup_failed,protocol_close_failed"
    assert not result.protocol_closed
    assert "synthetic failure" in result.observations[-1].payload_json


def test_cleanup_failure_prevents_clean_completed_result_but_preserves_review():
    client = FakeClient(); client.close_error = True
    result, _ = execute(client)
    assert result.status == "incomplete" and result.provider_status == "completed"
    assert result.review is not None and result.cleanup_error == "protocol_close_failed"


def test_incomplete_stream_interrupts_then_closes():
    result, client = execute(FakeClient([]))
    assert result.status == "incomplete" and result.review is None
    assert any(c[0] == "interrupt" for c in client.calls)
    assert client.calls[-1] == ("close",)


def test_unknown_notification_preserved_and_rejected():
    unknown = SimpleNamespace(method="turn/completed", payload=SimpleNamespace(params={"threadId": "thread-1", "broken": True}))
    result, _ = execute(FakeClient([unknown]))
    assert result.execution_error == "unknown_or_invalid_notification"
    assert json.loads(result.observations[-1].payload_json)["broken"] is True


@pytest.mark.parametrize("mutation,error", [("threadId", "native_thread_mismatch"), ("turnId", "native_turn_mismatch")])
def test_interleaved_identity_rejected(mutation, error):
    payload = {"threadId": "thread-1", "turnId": "turn-1", "item": answer()}; payload[mutation] = "wrong"
    result, _ = execute(FakeClient([event("item/completed", payload)]))
    assert result.execution_error == error


def test_duplicate_completed_item_id_is_idempotent_but_disagreement_fails():
    payload = {"threadId": "thread-1", "turnId": "turn-1", "item": answer()}
    result, _ = execute(FakeClient([event("item/completed", payload), event("item/completed", payload), completed()]))
    assert result.status == "completed"
    bad = {**payload, "item": {**answer(), "text": "other"}}
    result, _ = execute(FakeClient([event("item/completed", payload), event("item/completed", bad)]))
    assert result.execution_error == "contradictory_duplicate_item"


def test_byte_and_event_limits_fail_without_false_success():
    for change in ({"max_output_bytes": 1}, {"max_events": 1}):
        instance, client = adapter()
        result = asyncio.run(instance.execute(request(**change)))
        assert result.capture_error == "observation_limit_exceeded"
        assert result.status == "incomplete" and result.protocol_closed


def test_evidence_sink_failure_preserves_acquired_observation_and_closes():
    def broken(obs):
        raise OSError("sink unavailable")
    result, client = execute(sink=broken)
    assert len(result.observations) == 1
    assert result.capture_error == "evidence_sink_failed" and result.protocol_closed


@pytest.mark.parametrize("method,response", [
    ("item/commandExecution/requestApproval", {"decision":"cancel"}),
    ("item/fileChange/requestApproval", {"decision":"cancel"}),
    ("item/permissions/requestApproval", {"permissions":{},"scope":"turn"}),
    ("mcpServer/elicitation/request", {"action":"cancel"}),
])
def test_all_supported_approval_callbacks_deny(method, response):
    instance, client = adapter()
    client.on_turn = lambda: client.handler(method, {})
    result = asyncio.run(instance.execute(request()))
    assert client.handler(method, {}) == response
    assert result.execution_error == "unexpected_approval_request" and result.status == "incomplete"
    with pytest.raises(AdapterError, match="unsupported_server_request"):
        client.handler("account/chatgptAuthTokens/refresh", {})


def test_cancel_and_ack_do_not_claim_settlement():
    async def scenario():
        entered, released = threading.Event(), threading.Event()
        client = FakeClient([completed("interrupted", items=[])])
        client.on_next = lambda: (entered.set(), released.wait(5))
        instance, _ = adapter(client)
        task = asyncio.create_task(instance.execute(request()))
        assert await asyncio.to_thread(entered.wait, 5)
        wrong = await instance.cancel("foreign")
        assert not wrong.requested
        receipt = await instance.cancel("dispatch-1")
        assert receipt.requested and receipt.acknowledged
        released.set()
        result = await task
        assert result.status == "interrupted" and result.review is None
        assert result.to_tool_output()["process_settlement"] == "not_established"
    asyncio.run(scenario())


def test_cancel_during_setup_prevents_turn_effect():
    async def scenario():
        entered, released = threading.Event(), threading.Event()
        client = FakeClient(); client.on_start = lambda: (entered.set(), released.wait(5))
        instance, _ = adapter(client)
        task = asyncio.create_task(instance.execute(request()))
        assert await asyncio.to_thread(entered.wait, 5)
        receipt = await instance.cancel("dispatch-1")
        assert receipt.requested and not receipt.acknowledged
        released.set(); result = await task
        assert not any(c[0] == "turn_start" for c in client.calls)
        assert result.status == "interrupted" and result.provider_status is None
    asyncio.run(scenario())


def test_reconcile_never_replays_new_turn_and_checks_bindings():
    instance, client = adapter(resume=lambda req, thread_id, turn_id: None)
    result = asyncio.run(instance.reconcile(request(), thread_id="thread-1", turn_id="turn-1"))
    assert result.status == "completed"
    assert not any(c[0] == "turn_start" for c in client.calls)
    assert ("thread_read", "thread-1", True) in client.calls
    with pytest.raises(AdapterError, match="operation_already_consumed"):
        asyncio.run(instance.execute(request()))


def test_contract_roundtrip_is_immutable_and_strict():
    result, _ = execute()
    assert ExecutionRequest.from_dict(request().to_dict()) == request()
    assert ExecutionResult.from_dict(result.to_dict()) == result
    for text in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '{"a":1e999}'):
        with pytest.raises(ValueError):
            strict_json(text)
    with pytest.raises(ValueError):
        ExecutionRequest.from_dict({**request().to_dict(), "extra": "bad"})
    with pytest.raises(ValueError):
        replace(result, status="completed", review=None)
    with pytest.raises(ValueError):
        replace(result, usage_json='{"x":"' + 'a' * 65536 + '"}')
    with pytest.raises(ValueError):
        Finding("high", "../secret", 1, "bug", "evidence")
    with pytest.raises(ValueError):
        validate_review('{"run_id":"evidence-1","run_id":"other"}')


def test_import_never_loads_provider_package():
    assert "openai_codex" not in sys.modules


def test_released_public_types_match_adapter_wire_and_event_models():
    """Pinned official source-only compatibility, never SDK client execution.

    The inspected optional source fixture is local evidence, not vendored runtime
    code. Its exact Git blob is checked before loading the generated pure models.
    """
    import hashlib
    import importlib.util
    source = Path(__file__).resolve().parents[1] / ".scratch/sdk-api-fixture/0.163.0/v2_all.py"
    if not source.exists():
        pytest.skip("pinned official generated source fixture not provisioned")
    raw = source.read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    assert blob == "0faaa9e074c4de86f9087d4e355bd1ebee42c2b9"
    spec = importlib.util.spec_from_file_location("codex_release_public_models", source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    class PublicTypedClient(FakeClient):
        def thread_start(self, params):
            module.ThreadStartParams.model_validate(params)
            response = super().thread_start(params)
            response["thread"] = {
                "id":"thread-1", "cliVersion":"0.163.0", "createdAt":0, "updatedAt":0,
                "cwd":"/fixture/repo", "ephemeral":False, "modelProvider":"openai", "preview":"fixture",
                "sessionId":"session-1", "source":"appServer", "historyMode":"legacy", "status":{"type":"idle"}, "turns":[],
            }
            return module.ThreadStartResponse.model_validate(response)

        def turn_start(self, thread_id, input_items, params):
            module.TurnStartParams.model_validate({**params, "threadId":thread_id, "input":[{"type":"text", "text":input_items}]})
            response = super().turn_start(thread_id,input_items,params)
            response["turn"]["itemsView"] = "full"
            return module.TurnStartResponse.model_validate(response)

        def next_turn_notification(self, turn_id):
            value = super().next_turn_notification(turn_id)
            model = module.TurnCompletedNotification if value["method"] == "turn/completed" else module.ItemCompletedNotification
            return SimpleNamespace(method=value["method"], payload=model.model_validate(value["payload"]))

    result, client = execute(PublicTypedClient())
    assert result.status == "completed", result.to_dict()
    assert module.ReasoningEffort.max.value == "max"
    assert module.ReadOnlySandboxPolicy(type="readOnly").model_dump(by_alias=True)["networkAccess"] is False


def test_resume_requires_fresh_owner_binding_before_start():
    instance, client = adapter()
    with pytest.raises(AdapterError, match="resume_binding_owner_required"):
        asyncio.run(instance.reconcile(request(), thread_id="thread-1", turn_id="turn-1"))
    assert not client.calls


def test_repeated_cancel_ack_does_not_send_duplicate_interrupt():
    instance, client = adapter()
    instance._request, instance._client = request(), client
    instance._thread_id, instance._turn_id = "thread-1", "turn-1"
    first = asyncio.run(instance.cancel("dispatch-1"))
    second = asyncio.run(instance.cancel("dispatch-1"))
    assert first.acknowledged and second.acknowledged
    assert len([c for c in client.calls if c[0] == "interrupt"]) == 1


def test_phase_less_final_matches_official_sdk_compatibility():
    item = answer(); item["phase"] = None
    result, _ = execute(FakeClient(successful_events(item)))
    assert result.status == "completed"


def test_usage_is_observed_nonnegative_counts_not_default_zero():
    counts = {"inputTokens":5,"cachedInputTokens":0,"outputTokens":2,"reasoningOutputTokens":1,"totalTokens":7}
    payload = {"threadId":"thread-1","turnId":"turn-1","tokenUsage":{"last":counts,"total":counts}}
    result, _ = execute(FakeClient([event("thread/tokenUsage/updated",payload), *successful_events()]))
    assert result.usage["last"]["totalTokens"] == 7
    bad = {**payload, "tokenUsage":{"last":{},"total":{}}}
    result, _ = execute(FakeClient([event("thread/tokenUsage/updated",bad)]))
    assert result.execution_error == "invalid_usage" and result.usage is None


def test_adapter_does_not_add_findings_to_verdict_policy():
    payload = review_payload(findings=[{"severity":"low","path":"a.py","line":1,"message":"Nonblocking note","evidence":"source"}])
    result, _ = execute(FakeClient(successful_events(answer(payload))))
    assert result.status == "completed" and result.review.verdict == "PASS"
    assert result.to_tool_output()["authoritative"] is False


def test_existing_cli_result_retains_native_text_without_sdk_provenance():
    req = request(provider="kimi")
    result = ExecutionResult(req, "completed", provider_status="completed",
                             actual_execution_path="direct-external-cli",
                             native_result_text="Native evidence.\nGATE: PASS", protocol_closed=True)
    assert result.review is None and result.sdk_execution is None
    assert ExecutionResult.from_dict(result.to_dict()) == result
    output = result.to_tool_output()
    assert output["actual_execution_path"] == "direct-external-cli"
    assert output["native_result_text"] == "Native evidence.\nGATE: PASS"
    assert output["authoritative"] is False and output["process_settlement"] == "not_established"


def test_result_route_and_representation_cannot_be_mislabeled():
    sdk, _ = execute()
    assert sdk.actual_execution_path == "direct-external-sdk" and sdk.native_result_text is None
    for changes in (
        {"native_result_text":"GATE: PASS"},
        {"actual_execution_path":"direct-external-cli"},
        {"actual_execution_path":"internal"},
    ):
        with pytest.raises(ValueError):
            replace(sdk, **changes)
    cli = ExecutionResult(request(provider="kimi"), "completed", provider_status="completed",
                          actual_execution_path="direct-external-cli", native_result_text="GATE: PASS", protocol_closed=True)
    for changes in (
        {"sdk_execution_json":sdk.sdk_execution_json},
        {"review":sdk.review},
        {"actual_execution_path":"direct-external-sdk"},
        {"native_result_text":None},
    ):
        with pytest.raises(ValueError):
            replace(cli, **changes)


def test_native_result_text_uses_utf8_byte_bound():
    with pytest.raises(ValueError, match="native result text"):
        ExecutionResult(request(provider="kimi", max_output_bytes=4), "incomplete",
                        actual_execution_path="direct-external-cli", native_result_text="ééé")
    result = ExecutionResult(request(provider="kimi", max_output_bytes=4), "incomplete",
                             actual_execution_path="direct-external-cli", native_result_text="éé")
    assert result.native_result_text == "éé"


@pytest.mark.parametrize("second_cancel_during", ["interrupt", "execution"])
def test_repeated_task_cancellation_drains_owned_tasks_and_retains_outcome(second_cancel_during):
    async def scenario():
        execution_entered = threading.Event()
        execution_release = threading.Event()
        interrupt_entered = threading.Event()
        interrupt_release = threading.Event()
        cancel_returned = asyncio.Event()
        captured = []

        class BlockingClient(FakeClient):
            def next_turn_notification(self, turn_id):
                execution_entered.set()
                if not execution_release.wait(5):
                    raise TimeoutError("fixture release missing")
                return super().next_turn_notification(turn_id)

            def turn_interrupt(self, thread_id, turn_id):
                interrupt_entered.set()
                if not interrupt_release.wait(5):
                    raise TimeoutError("fixture interrupt release missing")
                return super().turn_interrupt(thread_id, turn_id)

        client = BlockingClient([completed("interrupted", items=[])])
        instance, _ = adapter(client, sink=captured.append)
        original_cancel = instance.cancel

        async def observed_cancel(run_id):
            receipt = await original_cancel(run_id)
            cancel_returned.set()
            return receipt

        instance.cancel = observed_cancel
        task = asyncio.create_task(instance.execute(request()))
        try:
            assert await asyncio.to_thread(execution_entered.wait, 5)
            task.cancel()
            assert await asyncio.to_thread(interrupt_entered.wait, 5)
            if second_cancel_during == "execution":
                interrupt_release.set()
                await asyncio.wait_for(cancel_returned.wait(), 5)
            task.cancel()
            interrupt_release.set()
            execution_release.set()
            result = await asyncio.wait_for(task, 5)
            assert not task.cancelled()
            assert result.status == result.provider_status == "interrupted"
            assert result.protocol_closed and result.cleanup_error is None
            assert any(o.kind == "turn/completed" for o in result.observations)
            assert captured == list(result.observations)
            assert client.calls[-1] == ("close",)
            assert len([c for c in client.calls if c[0] == "interrupt"]) == 1
        finally:
            interrupt_release.set()
            execution_release.set()
    asyncio.run(scenario())


def test_live_summary_requires_preceding_complete_item_evidence():
    result, _ = execute(FakeClient([completed()]))
    assert result.provider_status == "completed" and result.status == "incomplete"
    assert result.execution_error == "missing_completed_item"
    assert result.review is None


def test_live_terminal_summary_must_agree_with_completed_item():
    wrong = {**answer(), "text":"different summary"}
    result, _ = execute(FakeClient([item_completed(), completed(items=[wrong])]))
    assert result.execution_error == "contradictory_terminal_item"
    assert result.provider_status == "completed" and result.status == "incomplete"


def test_completed_turn_cannot_leave_started_item_unfinished():
    pending = event("item/started", {"threadId":"thread-1", "turnId":"turn-1", "item":{"id":"pending-1"}})
    result, _ = execute(FakeClient([pending, *successful_events()]))
    assert result.execution_error == "incomplete_item_lifecycle"
    assert result.status == "incomplete"


def test_reconciliation_still_requires_full_bound_turn_history():
    instance, client = adapter(resume=lambda req, thread_id, turn_id: None)
    client.history["thread"]["turns"][0]["itemsView"] = "summary"
    result = asyncio.run(instance.reconcile(request(), thread_id="thread-1", turn_id="turn-1"))
    assert result.execution_error == "partial_history_items"
    assert result.review is None and result.status == "incomplete"


@pytest.mark.parametrize("status_fields", [{}, {"status": None}, {"status": "inProgress"}, {"status": "future"}])
def test_completed_command_requires_terminal_status(status_fields):
    item = command_item()
    del item["status"]
    item.update(status_fields)
    result, client = execute(FakeClient([item_completed(item), *successful_events()]))
    assert result.status == "incomplete" and result.review is None
    assert result.execution_error == "invalid_terminal_command_status"
    observed = next(observation for observation in result.observations if observation.kind == "item/completed")
    assert json.loads(observed.payload_json)["item"] == item
    assert result.protocol_closed and client.calls[-1] == ("close",)


def test_reconciliation_rejects_nonterminal_command_in_completed_history():
    instance, client = adapter(resume=lambda req, thread_id, turn_id: None)
    item = command_item(status="inProgress", exitCode=None)
    client.history["thread"]["turns"][0] = completed(items=[item, answer()], itemsView="full")["payload"]["turn"]
    result = asyncio.run(instance.reconcile(request(), thread_id="thread-1", turn_id="turn-1"))
    assert result.provider_status == "completed" and result.status == "incomplete"
    assert result.execution_error == "invalid_terminal_command_status" and result.review is None
    assert result.protocol_closed and not any(call[0] == "turn_start" for call in client.calls)


@pytest.mark.parametrize("exit_code", [None, "0", True])
def test_completed_command_requires_observed_integer_exit_code(exit_code):
    result, _ = execute(FakeClient([item_completed(command_item(exitCode=exit_code)), *successful_events()]))
    assert result.status == "incomplete" and result.review is None
    assert result.execution_error == "missing_command_exit_code"


@pytest.mark.parametrize("status,exit_code", [("completed", 0), ("completed", 7), ("failed", None), ("declined", None)])
def test_terminal_command_outcome_is_evidence_not_final_review_policy(status, exit_code):
    item = command_item(status=status, exitCode=exit_code)
    result, _ = execute(FakeClient([item_completed(item), *successful_events()]))
    assert result.status == result.provider_status == "completed"
    assert result.review == ReviewResult.from_dict(review_payload())
    observed = next(observation for observation in result.observations if observation.kind == "item/completed")
    assert json.loads(observed.payload_json)["item"] == item
    assert result.execution_error is None and result.protocol_closed


def test_optional_future_notifications_are_evidence_not_new_completion_gate():
    optional = SimpleNamespace(method="item/future/progress", payload=SimpleNamespace(params={"threadId":"thread-1", "turnId":"turn-1", "detail":"future"}))
    result, _ = execute(FakeClient([optional, *successful_events()]))
    assert result.status == "completed"
    assert any(o.kind == "item/future/progress" for o in result.observations)


def test_model_reroute_is_profile_evidence_not_ignored_progress():
    rerouted = event("model/rerouted", {"threadId":"thread-1", "turnId":"turn-1", "fromModel":"fixture-model", "toModel":"unadmitted-model", "reason":"fallback"})
    result, client = execute(FakeClient([rerouted, *successful_events()]))
    assert result.status == "incomplete" and result.review is None
    assert result.execution_error == "observed_model_drift"
    assert any(o.kind == "model/rerouted" for o in result.observations)
    assert any(c[0] == "interrupt" for c in client.calls)


def test_malformed_known_reroute_cannot_be_ignored():
    malformed = SimpleNamespace(method="model/rerouted", payload=SimpleNamespace(params={"threadId":"thread-1", "turnId":"turn-1"}))
    result, _ = execute(FakeClient([malformed, *successful_events()]))
    assert result.execution_error == "unknown_or_invalid_notification"
    assert result.status == "incomplete" and result.review is None


def test_owned_task_cancellation_is_not_mistaken_for_caller_cancellation():
    from sdk_execution._async import drain_owned
    async def scenario():
        task = asyncio.create_task(asyncio.sleep(0))
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await drain_owned(task)
    asyncio.run(scenario())


def test_released_client_public_signatures_match_owned_composition_without_loading_sdk():
    """Read the hash-verified published client source; never import/launch it."""
    import ast
    import hashlib
    source = Path(__file__).resolve().parents[1] / ".scratch/sdk-api-fixture/0.163.0/client.py"
    if not source.exists():
        pytest.skip("pinned official client source fixture not provisioned")
    raw = source.read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    assert blob == "5b38538c541aa17e807aecfa3d5a58c9ee76d0ff"
    tree = ast.parse(raw)
    client = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "CodexClient")
    methods = {node.name: node for node in client.body if isinstance(node, ast.FunctionDef)}
    signatures = {
        "start": ["self"], "initialize": ["self"], "close": ["self"],
        "account_read": ["self", "params"], "thread_start": ["self", "params"],
        "thread_resume": ["self", "thread_id", "params"],
        "thread_read": ["self", "thread_id", "include_turns"],
        "turn_start": ["self", "thread_id", "input_items", "params"],
        "next_turn_notification": ["self", "turn_id"],
        "unregister_turn_notifications": ["self", "turn_id"],
        "turn_interrupt": ["self", "thread_id", "turn_id"],
    }
    for name, parameters in signatures.items():
        assert [argument.arg for argument in methods[name].args.args] == parameters
    config = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "CodexConfig")
    assert {node.target.id for node in config.body if isinstance(node, ast.AnnAssign)} == {
        "codex_bin", "launch_args_override", "config_overrides", "cwd", "env",
        "client_name", "client_title", "client_version", "experimental_api",
    }
    # No new public byte-bound configuration replaces the existing process owner.
    readlines = [node for node in ast.walk(methods["_read_message"])
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                 and node.func.attr == "readline"]
    assert len(readlines) == 1 and readlines[0].args == [] and readlines[0].keywords == []


def test_provider_versions_are_not_domain_contract_constants():
    from sdk_execution import codex, contracts
    for module in (codex, contracts):
        assert not hasattr(module, "SDK_VERSION")
        assert not hasattr(module, "RUNTIME_VERSION")


@pytest.mark.parametrize("omitted", ["all", "command"])
def test_full_terminal_cannot_omit_captured_completed_items(omitted):
    command, message = command_item(), answer()
    items = [] if omitted == "all" else [message]
    result, client = execute(FakeClient([
        item_completed(command), item_completed(message),
        completed(items=items, itemsView="full"),
    ]))
    assert result.provider_status == "completed" and result.status == "incomplete"
    assert result.execution_error == "contradictory_terminal_items"
    assert result.review is None and result.protocol_closed
    assert result.observations[-1].kind == "turn/completed"
    assert json.loads(result.observations[-1].payload_json)["turn"]["items"] == items
    assert client.calls[-1] == ("close",)


@pytest.mark.parametrize("view", ["full", "summary", "notLoaded"])
def test_terminal_item_coverage_respects_declared_view(view):
    command, message = command_item(), answer()
    items = {"full": [command, message], "summary": [message], "notLoaded": []}[view]
    result, _ = execute(FakeClient([
        item_completed(command), item_completed(message),
        completed(items=items, itemsView=view),
    ]))
    assert result.status == "completed" and result.execution_error is None
    assert result.review is not None and result.protocol_closed


@pytest.mark.parametrize("failure", ["in_progress", "read_error"])
def test_reconcile_failure_does_not_implicitly_interrupt_prior_turn(failure):
    instance, client = adapter(resume=lambda *args: None)
    if failure == "in_progress":
        client.history["thread"]["turns"][0]["status"] = "inProgress"
    else:
        def broken_read(thread_id, include_turns=False):
            raise RuntimeError("fixture history read failed")
        client.thread_read = broken_read
    result = asyncio.run(instance.reconcile(request(), thread_id="thread-1", turn_id="turn-1"))
    assert result.status == "incomplete" and result.protocol_closed
    assert not any(call[0] in {"turn_start", "interrupt"} for call in client.calls)
    assert client.calls[-1] == ("close",)


def test_reconcile_explicit_caller_cancellation_keeps_bound_cancel_operation():
    instance, client = adapter(resume=lambda *args: None)
    original = client.thread_read
    receipts = []
    def cancel_during_read(thread_id, include_turns=False):
        receipts.append(asyncio.run(instance.cancel(request().run_id)))
        return original(thread_id, include_turns=include_turns)
    client.thread_read = cancel_during_read
    result = asyncio.run(instance.reconcile(request(), thread_id="thread-1", turn_id="turn-1"))
    assert receipts[0].requested and receipts[0].acknowledged
    assert [call for call in client.calls if call[0] == "interrupt"] == [("interrupt", "thread-1", "turn-1")]
    assert result.protocol_closed


def mcp_status(name, tools, status="connected", **changes):
    value = {"name": name, "tools": {tool: {"name": tool} for tool in tools},
             "runtimeStatus": status, "toolsError": None, "pluginId": None}
    value.update(changes)
    return value


def test_mcp_default_disables_ambient_servers_before_turn():
    client = FakeClient()
    client.configuration["config"]["mcp_servers"] = {"ambient": {"command": "not disclosed"}}
    client.mcp_pages[(None, None)] = {"data": [mcp_status("ambient", (), "disabled")], "nextCursor": None}
    result, client = execute(client)
    assert result.status == "completed"
    thread = next(call[1] for call in client.calls if call[0] == "thread_start")
    assert thread["config"]["mcp_servers"] == {"ambient": {"enabled": False}}
    assert all("not disclosed" not in observation.payload_json for observation in result.observations)


def test_mcp_selected_subset_requires_live_thread_connection():
    client = FakeClient()
    client.configuration["config"]["mcp_servers"] = {"Docs": {}, "other": {}}
    selected = mcp_status("Docs", ("read",))
    client.mcp_pages[(None, None)] = {"data": [selected, mcp_status("other", (), "disabled")], "nextCursor": None}
    client.mcp_pages[("Docs", None)] = {"data": [selected], "nextCursor": None}
    result, client = execute(client, mcp_scope=CodexMcpScope((("Docs", ("read",)),)))
    assert result.status == "completed"
    calls = [call[1] for call in client.calls if call[0] == "mcpServerStatus/list"]
    assert any(call.get("serverName") == "Docs" for call in calls)
    assert all(call["threadId"] == "thread-1" for call in calls)
    thread = next(call[1] for call in client.calls if call[0] == "thread_start")
    assert thread["config"]["mcp_servers"]["Docs"] == {"enabled_tools": ["read"]}


def test_mcp_ambient_extra_tool_refuses_before_turn():
    client = FakeClient()
    client.configuration["config"]["mcp_servers"] = {"ambient": {}}
    client.mcp_pages[(None, None)] = {"data": [mcp_status("ambient", ("write",))], "nextCursor": None}
    result, client = execute(client)
    assert result.execution_error == "mcp_scope_mismatch"
    assert not any(call[0] == "turn_start" for call in client.calls)


@pytest.mark.parametrize("change", [
    {"features": {"plugins": True, "apps": False, "multi_agent_v2": False}},
    {"agents": {"enabled": True}}, {"features": {}},
])
def test_mcp_startup_isolation_readback_is_required(change):
    client = FakeClient(); client.configuration["config"].update(change)
    result, client = execute(client)
    assert result.execution_error == "startup_tool_isolation_unverified"
    assert not any(call[0] in {"thread_start", "turn_start"} for call in client.calls)


@pytest.mark.parametrize("server", [{"enabled": False}, {"enabled_tools": []},
                                    {"disabled_tools": ["read"]}, {"enabled_tools": ["other"]}])
def test_mcp_selection_never_widens_inherited_denials(server):
    client = FakeClient(); client.configuration["config"]["mcp_servers"] = {"Docs": server}
    result, client = execute(client, mcp_scope=CodexMcpScope((("Docs", ("read",)),)))
    assert result.execution_error == "mcp_selection_not_eligible"
    assert not any(call[0] in {"thread_start", "turn_start"} for call in client.calls)


@pytest.mark.parametrize("page", [
    {"data": [], "nextCursor": "repeat"},
    {"data": [], "nextCursor": 1},
    {"nextCursor": None},
    {"data": "invalid", "nextCursor": None},
])
def test_mcp_incomplete_pagination_cannot_start_turn(page):
    client = FakeClient(); client.mcp_pages[(None, None)] = page
    result, client = execute(client)
    assert result.execution_error == "mcp_catalog_incomplete"
    assert not any(call[0] == "turn_start" for call in client.calls)


def test_mcp_repeated_cursor_stops_bounded_acquisition():
    client = FakeClient()
    client.mcp_pages[(None, None)] = {"data": [mcp_status("a", (), "disabled")], "nextCursor": "same"}
    client.mcp_pages[(None, "same")] = {"data": [mcp_status("b", (), "disabled")], "nextCursor": "same"}
    result, client = execute(client)
    assert result.execution_error == "mcp_catalog_incomplete"
    assert len([call for call in client.calls if call[0] == "mcpServerStatus/list"]) == 2
    assert not any(call[0] == "turn_start" for call in client.calls)


def test_mcp_cached_selected_catalog_cannot_replace_live_connection():
    client = FakeClient(); client.configuration["config"]["mcp_servers"] = {"Docs": {}}
    client.mcp_pages[(None, None)] = {"data": [mcp_status("Docs", ("read",))], "nextCursor": None}
    client.mcp_pages[("Docs", None)] = {"data": [mcp_status("Docs", ("read",), status=None)], "nextCursor": None}
    result, client = execute(client, mcp_scope=CodexMcpScope((("Docs", ("read",)),)))
    assert result.execution_error == "mcp_scope_mismatch"
    assert not any(call[0] == "turn_start" for call in client.calls)


def test_mcp_reconciliation_rechecks_scope_without_replaying_turn():
    client = FakeClient(); client.configuration["config"]["mcp_servers"] = {"unexpected": {}}
    client.mcp_pages[(None, None)] = {"data": [mcp_status("unexpected", ("write",))], "nextCursor": None}
    instance, client = adapter(client, resume=lambda *args: None)
    result = asyncio.run(instance.reconcile(request(), thread_id="thread-1", turn_id="turn-1"))
    assert result.execution_error == "mcp_scope_mismatch"
    assert not any(call[0] in {"turn_start", "interrupt", "thread_read"} for call in client.calls)


@pytest.mark.parametrize("missing", [None, "nextCursor", "toolsError", "pluginId"])
def test_mcp_typed_optional_defaults_match_public_contract(missing):
    from pydantic import BaseModel, ConfigDict, Field
    class Status(BaseModel):
        model_config = ConfigDict(populate_by_name=True)
        name: str
        tools: dict
        runtime_status: str = Field(alias="runtimeStatus")
        tools_error: str | None = Field(default=None, alias="toolsError")
        plugin_id: str | None = Field(default=None, alias="pluginId")
    class Page(BaseModel):
        model_config = ConfigDict(populate_by_name=True)
        data: list[Status]
        next_cursor: str | None = Field(default=None, alias="nextCursor")
    client = FakeClient()
    client.configuration["config"]["mcp_servers"] = {"Docs": {}}
    raw = {"data": [mcp_status("Docs", ("read",))], "nextCursor": None}
    if missing == "nextCursor":
        del raw[missing]
    elif missing is not None:
        del raw["data"][0][missing]
    page = Page.model_validate(raw)
    client.mcp_pages[(None, None)] = page
    client.mcp_pages[("Docs", None)] = page
    result, client = execute(client, mcp_scope=CodexMcpScope((("Docs", ("read",)),)))
    assert result.status == "completed" and result.execution_error is None
    assert any(call[0] == "turn_start" for call in client.calls)


def test_mcp_raw_optional_cursor_omission_matches_public_schema():
    client = FakeClient(); client.mcp_pages[(None, None)] = {"data": []}
    result, client = execute(client)
    assert result.status == "completed" and result.execution_error is None
    assert any(call[0] == "turn_start" for call in client.calls)


def bounded_configuration(client):
    config = client.configuration['config']
    config['features']['memories'] = False
    config.update(notify=[], model_provider='openai', approvals_reviewer='user')
    return config


@pytest.mark.parametrize('field,value', [
    ('memories', True), ('memories', None), ('memories', 'false'),
    ('notify', ['fixture-command']), ('notify', None), ('notify', ''),
    ('model_provider', 'other'), ('model_provider', None),
    ('approvals_reviewer', 'guardian_subagent'), ('approvals_reviewer', None),
])
def test_bounded_startup_profile_refuses_incompatible_readback_before_thread(field, value):
    client = FakeClient()
    config = bounded_configuration(client)
    (config['features'] if field == 'memories' else config)[field] = value
    result, client = execute(client, bounded_startup_profile=True)
    assert result.execution_error == 'bounded_startup_profile_unverified'
    assert not any(call[0] in {'thread_start', 'turn_start'} for call in client.calls)


@pytest.mark.parametrize('field', ['memories', 'notify', 'model_provider', 'approvals_reviewer'])
def test_bounded_startup_profile_refuses_missing_readback(field):
    client = FakeClient()
    config = bounded_configuration(client)
    del (config['features'] if field == 'memories' else config)[field]
    result, client = execute(client, bounded_startup_profile=True)
    assert result.execution_error == 'bounded_startup_profile_unverified'
    assert not any(call[0] in {'thread_start', 'turn_start'} for call in client.calls)


def test_bounded_startup_profile_accepts_explicit_raw_consistency_without_endpoint_rewrite():
    client = FakeClient()
    config = bounded_configuration(client)
    config['openai_base_url'] = 'https://fixture.invalid/owner-selected'
    result, client = execute(client, bounded_startup_profile=True)
    assert result.status == 'completed'
    thread = next(call[1] for call in client.calls if call[0] == 'thread_start')
    assert 'openai_base_url' not in thread['config']
    assert config['openai_base_url'] == 'https://fixture.invalid/owner-selected'


def test_low_level_adapter_does_not_implicitly_select_bounded_profile():
    client = FakeClient()
    config = bounded_configuration(client)
    config.update(notify=['fixture-command'], model_provider='other', approvals_reviewer='guardian_subagent')
    config['features']['memories'] = True
    result, _ = execute(client)
    assert result.status == 'completed'  # Fixture only; no native command/provider.
