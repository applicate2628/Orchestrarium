"""Offline public-API-shaped fixtures. No provider import, CLI, account or model."""
import asyncio
from dataclasses import dataclass, replace
import importlib
import inspect
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sdk_execution.claude import (
    AdapterError, ClaudeReviewAdapter, ClientBinding, READ_TOOLS, OUTPUT_TOOL,
    _official_client_binding,
)
from sdk_execution.contracts import ExecutionRequest, ExecutionResult, ReviewResult

SDK_VERSION = "0.2.173"  # Synthetic fixture provenance, not production admission.


@pytest.fixture(autouse=True)
def instruction_capture_root(tmp_path, monkeypatch):
    # Exercise the real existing custody owner, with no credentials or SDK.
    root = tmp_path / "instruction-captures"
    monkeypatch.setenv("CLAUDE_PROMPTS_DIR", str(root))
    yield root
    assert not root.exists() or list(root.iterdir()) == []


def request(**changes):
    value = ExecutionRequest(
        work_item_id="item-1", provider="claude", external_dispatch_id="dispatch-1",
        external_evidence_run_id="evidence-1", artifact_id="review.md", role="architecture-reviewer",
        model="fixture-model", effort="high", cwd="/fixture/repo", account_binding="fixture-account",
        prompt="Review the admitted artifact read-only.", coordinator_binding="coordinator-1", scope=("review",),
    )
    return replace(value, **changes)


def review_payload(**changes):
    value = {"run_id": "evidence-1", "artifact_id": "review.md", "role": "architecture-reviewer", "verdict": "PASS", "findings": []}
    value.update(changes)
    return value


@dataclass
class SystemMessage:
    subtype: str
    data: dict


@dataclass
class ResultMessage:
    subtype: str = "success"
    is_error: bool = False
    session_id: str = ""
    terminal_reason: str = "completed"
    structured_output: object = None
    usage: object = None
    total_cost_usd: object = None
    model_usage: object = None
    permission_denials: object = None
    errors: object = None
    deferred_tool_use: object = None
    api_error_status: object = None
    origin: object = None


@dataclass
class AssistantMessage:
    content: list
    model: str = "fixture-model"
    parent_tool_use_id: object = None
    error: object = None
    session_id: str = ""


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict


@dataclass
class RateLimitEvent:
    rate_limit_info: dict
    uuid: str
    session_id: str


@dataclass
class ConversationResetMessage:
    new_conversation_id: str
    uuid: str
    session_id: str


@dataclass
class HookEventMessage(SystemMessage):
    hook_event_name: str = ""
    session_id: object = None
    uuid: object = None


class FakeClient:
    def __init__(self):
        self.options = None
        self.calls = []
        self.initialization = {"commands": [], "claude_code_version": "2.1.309"}
        self.init_change = {}
        self.terminal_change = {}
        self.hook_change = {}
        self.extra_messages = []
        self.include_terminal = True
        self.include_stop = True
        self.use_tool = False
        self.post_tool = True
        self.close_error = self.query_error = self.interrupt_error = self.connect_error = False
        self.before_connect = self.before_query = self.before_terminal = None
        self.hook_output = []
        self.prompt = None
        self.instructions = None

    async def connect(self):
        self.calls.append("connect")
        if self.before_connect:
            await self.before_connect()
        if self.connect_error:
            raise OSError("synthetic partial setup failure")

    async def get_server_info(self):
        self.calls.append("get_server_info")
        return self.initialization

    async def query(self, prompt, session_id="default"):
        self.calls.append("query")
        messages = [message async for message in prompt]
        assert len(messages) == 1 and messages[0]["session_id"] == session_id
        self.prompt = messages[0]
        if self.before_query:
            await self.before_query()
        if self.query_error:
            raise OSError("synthetic uncertain write")

    def hook_input(self, event="Stop", **changes):
        value = {
            "hook_event_name": event, "session_id": self.options["session_id"],
            "prompt_id": self.prompt["uuid"], "cwd": self.options["cwd"],
            "effort": {"level": self.options["effort"]}, "transcript_path": "/private/not-captured",
        }
        if event == "Stop":
            value.update(background_tasks=[], session_crons=[])
        else:
            value.update(tool_use_id="call-1", tool_name="Read", tool_input={"file_path": "/fixture/repo/a.py"})
            if event == "PostToolUse":
                value["tool_response"] = {"text": "synthetic source"}
        value.update(self.hook_change)
        value.update(changes)
        return value

    async def hook(self, event="Stop", **changes):
        data = self.hook_input(event, **changes)
        callback = self.options["hooks"][event][0]["hooks"][0]
        result = await callback(data, data.get("tool_use_id"), {})
        self.hook_output.append(result)
        return result

    async def receive_response(self):
        init = {
            "session_id": self.options["session_id"], "claude_code_version": "2.1.309",
            "model": self.options["model"], "cwd": self.options["cwd"], "permissionMode": "default",
            "tools": list(READ_TOOLS), "mcp_servers": [], "skills": [], "plugins": [],
            "apiKeySource": "none",
        }
        init.update(self.init_change)
        yield SystemMessage("init", init)
        if self.use_tool:
            yield AssistantMessage([ToolUseBlock("call-1", "Read", {"file_path": "/fixture/repo/a.py"})], session_id=self.options["session_id"])
            await self.hook("PreToolUse")
            if self.post_tool:
                await self.hook("PostToolUse")
        for message in self.extra_messages:
            yield message
        if self.include_stop:
            await self.hook()
        if self.before_terminal:
            await self.before_terminal()
        if self.include_terminal:
            value = dict(session_id=self.options["session_id"], structured_output=review_payload())
            value.update(self.terminal_change)
            yield ResultMessage(**value)

    async def interrupt(self):
        self.calls.append("interrupt")
        if self.interrupt_error:
            raise OSError("synthetic interrupt failure")

    async def disconnect(self):
        self.calls.append("disconnect")
        assert Path(self.options["extra_args"]["append-system-prompt-file"]).is_file()
        if self.close_error:
            raise OSError("synthetic disconnect failure")


def adapter(client=None, *, authority=None, authorize=None, instructions=None, verify=None, sink=None, sdk_version=SDK_VERSION):
    client = client or FakeClient()
    def factory(options):
        client.calls.append("factory")
        client.options = options
        client.instructions = Path(options["extra_args"]["append-system-prompt-file"]).read_text(encoding="utf-8")
        return ClientBinding(client, sdk_version)
    async def record(observation):
        if sink:
            value = sink(observation)
            if value is not None:
                await value
    async def current(req, phase):
        value = authority(req, phase) if authority else None
        return await value if inspect.isawaitable(value) else value
    async def tool(req, name, arguments):
        value = authorize(req, name, arguments) if authorize else None
        return await value if inspect.isawaitable(value) else value
    async def account(req, evidence):
        value = verify(req, evidence) if verify else req.account_binding
        return await value if inspect.isawaitable(value) else value
    value = ClaudeReviewAdapter(
        client_factory=factory, assert_current=current,
        authorize_tool=tool,
        load_instructions=instructions or (lambda req: "Current common governance. Current Claude-specific rules."),
        verify_account=account, record=record,
    )
    return value, client


def execute(client=None, req=None, **kwargs):
    instance, client = adapter(client, **kwargs)
    return asyncio.run(instance.execute(req or request())), client


def test_structured_success_actual_config_and_non_authority():
    captured, phases = [], []
    def verify(req, data):
        phases.append(data["phase"])
        return req.account_binding
    result, client = execute(sink=captured.append, verify=verify)
    assert result.status == result.provider_status == "completed"
    assert result.review == ReviewResult.from_dict(review_payload())
    assert result.protocol_closed and captured == list(result.observations)
    assert result.sdk_execution["adapter"] == "claude-agent-sdk"
    assert result.sdk_execution["sandboxMode"] == "tool-restricted-read-only"
    assert phases == ["before_connect", "initialize", "system_init"]
    assert result.to_tool_output()["authoritative"] is False
    assert result.to_tool_output()["process_settlement"] == "not_established"
    options = client.options
    assert options["tools"] == list(READ_TOOLS) and options["allowed_tools"] == []
    assert options["permission_mode"] == "default"
    assert options["setting_sources"] == [] and options["strict_mcp_config"]
    assert options["mcp_servers"] == {} and options["skills"] == [] and options["plugins"] == []
    assert options["fallback_model"] is options["resume"] is None
    assert options["system_prompt"]["snapshot"] is False
    assert options["system_prompt"] == {"type": "preset", "preset": "claude_code", "snapshot": False}
    assert "common governance" in client.instructions
    assert "Claude-specific" in client.instructions
    assert not Path(options["extra_args"]["append-system-prompt-file"]).exists()
    assert options["output_format"]["schema"]["properties"]["run_id"]["enum"] == ["evidence-1"]
    assert client.prompt["uuid"] == result.native_turn_id
    assert "origin" not in client.prompt  # Machine composition is not a human-origin receipt.
    assert options["session_id"] == result.native_thread_id
    assert all("/private/not-captured" not in obs.payload_json for obs in captured)
    assert ExecutionResult.from_dict(result.to_dict()) == result


def test_read_tool_uses_exact_arguments_and_current_authority():
    client = FakeClient(); client.use_tool = True
    calls = []
    result, client = execute(client, authorize=lambda req, name, args: calls.append((name, args)))
    assert result.status == "completed"
    assert calls == [("Read", {"file_path": "/fixture/repo/a.py"})]
    assert client.hook_output[0]["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_full_governance_uses_owned_file_not_windows_argv_and_preserves_native_base():
    root = Path(__file__).resolve().parents[1]
    instructions = (root / "shared/AGENTS.shared.md").read_text(encoding="utf-8")
    instructions += "\n" + (root / "src.claude/CLAUDE.md").read_text(encoding="utf-8")
    assert len(instructions.encode("utf-16-le")) // 2 > 32_767
    result, client = execute(instructions=lambda req: instructions)
    assert result.status == "completed" and client.instructions == instructions
    assert client.options["system_prompt"] == {"type": "preset", "preset": "claude_code", "snapshot": False}
    assert set(client.options["extra_args"]) == {"append-system-prompt-file"}
    path = Path(client.options["extra_args"]["append-system-prompt-file"])
    assert path.is_absolute() and not path.exists()
    # These are the only system-instruction argv inputs in the pinned producer.
    argv_options = json.dumps({key: client.options[key] for key in ("system_prompt", "extra_args")})
    assert len(argv_options.encode("utf-16-le")) // 2 < 32_767
    assert instructions not in argv_options


@pytest.mark.parametrize("phase", ["factory", "connect", "query", "disconnect"])
def test_instruction_file_owner_cleans_every_provider_failure_path(phase):
    instance, client = adapter()
    if phase == "factory":
        factory = instance._factory
        def fail_factory(options):
            factory(options)
            raise OSError("synthetic factory failure")
        instance._factory = fail_factory
    else:
        setattr(client, "close_error" if phase == "disconnect" else phase + "_error", True)
    result = asyncio.run(instance.execute(request()))
    assert result.status == "incomplete"
    assert not Path(client.options["extra_args"]["append-system-prompt-file"]).exists()
    if phase == "disconnect":
        assert result.provider_status == "completed" and result.review is not None


@pytest.mark.parametrize("phase", ["_acquire", "initialize"])
def test_instruction_file_partial_setup_reuses_existing_owner_cleanup(monkeypatch, phase):
    import provider_prompt as owner
    original = getattr(owner.RunCaptureLifecycle, phase)
    def fail_after_effect(self, *args):
        original(self, *args)
        raise OSError("synthetic partial setup")
    monkeypatch.setattr(owner.RunCaptureLifecycle, phase, fail_after_effect)
    result, client = execute()
    assert result.status == "incomplete" and result.execution_error
    assert result.cleanup_error is None and client.calls == []


def test_instruction_file_readback_mismatch_prevents_factory(monkeypatch):
    import provider_prompt as owner
    monkeypatch.setattr(owner, "_external_prompt_file_snapshot", lambda path: b"changed")
    result, client = execute()
    assert result.execution_error == "instruction_snapshot_mismatch" and client.calls == []
    assert result.cleanup_error is None


@pytest.mark.parametrize("provider_failure", [False, True])
def test_instruction_cleanup_failure_retains_terminal_review_and_other_cleanup(monkeypatch, provider_failure):
    import provider_prompt as owner
    original = owner.RunCaptureLifecycle.cleanup
    def report_failure(self):
        assert original(self).clean
        return owner.CleanupResult(("synthetic cleanup failure",))
    monkeypatch.setattr(owner.RunCaptureLifecycle, "cleanup", report_failure)
    client = FakeClient(); client.close_error = provider_failure
    result, _ = execute(client)
    assert result.status == "incomplete" and result.provider_status == "completed"
    assert result.review is not None
    expected = "protocol_close_failed," if provider_failure else ""
    assert result.cleanup_error == expected + "instruction_file_cleanup_failed"


def test_instruction_setup_and_cleanup_failures_are_both_retained(monkeypatch):
    import provider_prompt as owner
    original = owner.RunCaptureLifecycle._release_owned
    def fail_setup(self, payload):
        raise OSError("synthetic initialize failure")
    def report_cleanup_failure(self):
        assert original(self).clean
        return owner.CleanupResult(("synthetic cleanup failure",))
    monkeypatch.setattr(owner.RunCaptureLifecycle, "initialize", fail_setup)
    monkeypatch.setattr(owner.RunCaptureLifecycle, "_release_owned", report_cleanup_failure)
    result, client = execute()
    assert result.execution_error == "execution_or_interpretation_failed"
    assert result.cleanup_error == "instruction_file_cleanup_failed" and client.calls == []


def test_native_structured_output_tool_is_not_accidentally_blocked():
    client = FakeClient()
    client.init_change["tools"] = [*READ_TOOLS, OUTPUT_TOOL]
    authorized = []
    async def output():
        changes = {"tool_name": OUTPUT_TOOL, "tool_input": review_payload()}
        approved = await client.hook("PreToolUse", **changes)
        assert approved["hookSpecificOutput"]["permissionDecision"] == "allow"
        await client.hook("PostToolUse", **changes)
    client.before_terminal = output
    result, _ = execute(client, authorize=lambda req, name, args: authorized.append(name))
    assert result.status == "completed" and authorized == [OUTPUT_TOOL]


def test_native_output_tool_cannot_smuggle_unbound_data():
    client = FakeClient()
    async def output():
        denied = await client.hook("PreToolUse", tool_name=OUTPUT_TOOL, tool_input=review_payload(run_id="other-run"))
        assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"
    client.before_terminal = output
    result, _ = execute(client)
    assert result.status == "incomplete" and result.review is None


@pytest.mark.parametrize("change,error", [
    ({"model": "other"}, "observed_profile_mismatch"),
    ({"tools": ["Read", "Glob", "Grep", "Bash"]}, "observed_profile_mismatch"),
    ({"tools": None}, "observed_profile_mismatch"),
    ({"permissionMode": "bypassPermissions"}, "observed_profile_mismatch"),
    ({"mcp_servers": [{"name": "foreign", "status": "connected"}]}, "observed_profile_mismatch"),
    ({"session_id": "wrong"}, "native_session_mismatch"),
    ({"claude_code_version": "2.1.308"}, "runtime_version_metadata_mismatch"),
    ({"claude_code_version": None}, "invalid_runtime_version_metadata"),
])
def test_init_profile_drift_prevents_completion_and_interrupts(change, error):
    client = FakeClient(); client.init_change = change
    result, client = execute(client)
    assert result.status == "incomplete" and result.execution_error == error
    assert result.protocol_closed and "interrupt" in client.calls


def test_alias_is_not_guessed_to_match_canonical_model_or_pricing_identity():
    client = FakeClient(); client.init_change["model"] = "claude-opus-concrete-id"
    client.terminal_change["model_usage"] = {"opus": {"canonicalModel": "claude-opus-concrete-id"}}
    result, _ = execute(client, req=request(model="opus"))
    assert result.execution_error == "observed_profile_mismatch"
    assert result.status == "incomplete" and result.review is None


@pytest.mark.parametrize("notice", ["allowed", "allowed_warning", "rejected", "status", "compact_boundary", "future_diagnostic"])
def test_optional_information_is_retained_without_false_failure(notice):
    client = FakeClient()
    async def messages():
        session = client.options["session_id"]
        if notice in {"allowed", "allowed_warning", "rejected"}:
            client.extra_messages = [RateLimitEvent({"status": notice}, "event-1", session)]
        else:
            client.extra_messages = [SystemMessage(notice, {"session_id": session, "diagnostic": "informational"})]
    client.before_query = messages
    result, _ = execute(client)
    assert result.status == "completed"
    assert any(notice in obs.payload_json for obs in result.observations)


@pytest.mark.parametrize("event,phase", [("SessionStart", "hook_started"), ("Setup", "hook_response")])
def test_always_emitted_hook_notices_are_not_misclassified_as_unknown_messages(event, phase):
    client = FakeClient()
    async def messages():
        session = client.options["session_id"]
        client.extra_messages = [HookEventMessage(
            phase, {"session_id": session, "hook_event": event, "subtype": phase}, event, session, "event-1",
        )]
    client.before_query = messages
    result, _ = execute(client)
    assert result.status == "completed"
    assert any(obs.kind == "message/HookEventMessage" for obs in result.observations)


@pytest.mark.parametrize("kind", ["wrong_session", "malformed_rate", "reset", "profile_change"])
def test_information_handling_does_not_allow_identity_profile_or_reset_changes(kind):
    client = FakeClient()
    async def messages():
        session = client.options["session_id"]
        client.extra_messages = [{
            "wrong_session": RateLimitEvent({"status": "allowed"}, "event-1", "other-session"),
            "malformed_rate": RateLimitEvent({"status": "invented"}, "event-1", session),
            "reset": ConversationResetMessage("new", "event-1", session),
            "profile_change": SystemMessage("status", {"session_id": session, "model": "other-model"}),
        }[kind]]
    client.before_query = messages
    result, _ = execute(client)
    assert result.status == "incomplete" and result.review is None


@pytest.mark.parametrize("change,error", [
    ({"effort": {"level": "medium"}}, "observed_effort_mismatch"),
    ({"effort": None}, "missing_observed_effort"),
    ({"prompt_id": "swapped"}, "native_prompt_mismatch"),
    ({"prompt_id": None}, "missing_observed_prompt_identity"),
    ({"permission_mode": "bypassPermissions"}, "observed_permission_mismatch"),
    ({"background_tasks": [{"id": "still-running"}]}, "unsettled_session_work"),
])
def test_actual_hook_identity_effort_and_settlement_evidence(change, error):
    client = FakeClient(); client.hook_change = change
    result, _ = execute(client)
    assert result.status == "incomplete" and result.execution_error == error
    assert result.provider_status == "completed" and result.review is None
    assert result.sdk_execution["effort"] == "high"  # Configured, not fabricated observed parity.


@pytest.mark.parametrize("payload", [
    None, review_payload(run_id="wrong"), review_payload(artifact_id="wrong"),
    review_payload(role="security-reviewer"), review_payload(extra=1),
    review_payload(verdict="UNRECOGNIZED"), "GATE: PASS",
])
def test_structured_output_never_falls_back_to_prose_or_wrong_identity(payload):
    client = FakeClient(); client.terminal_change["structured_output"] = payload
    result, _ = execute(client)
    assert result.status == "incomplete" and result.provider_status == "completed"
    assert result.review is None and result.execution_error
    assert any(obs.kind == "message/ResultMessage" for obs in result.observations)


@pytest.mark.parametrize("changes", [
    {"permission_denials": ["Read"]}, {"deferred_tool_use": {"id": "pending"}},
    {"errors": ["synthetic error"]}, {"api_error_status": 429},
    {"terminal_reason": "max_turns"}, {"model_usage": {"other-model": {}}},
    {"origin": {"kind": "task-notification"}}, {"session_id": "wrong"},
])
def test_contradictory_or_incomplete_terminal_fails_closed(changes):
    client = FakeClient(); client.terminal_change = changes
    result, _ = execute(client)
    assert result.status == "incomplete" and result.review is None


def test_account_before_connection_and_after_public_init_are_verified():
    for phase, effects in [("before_connect", []), ("initialize", ["factory", "connect", "get_server_info", "disconnect"]), ("system_init", None)]:
        def verify(req, data):
            return "wrong" if data["phase"] == phase else req.account_binding
        result, client = execute(verify=verify)
        assert result.execution_error == "account_binding_mismatch"
        if effects is not None:
            assert client.calls == effects


def test_missing_instructions_do_not_connect():
    result, client = execute(instructions=lambda req: "")
    assert result.execution_error == "missing_governance_instructions" and client.calls == []


@pytest.mark.parametrize("sdk_version,runtime_version", [
    ("0.2.172", "2.1.308"), ("0.3.0", "3.0.0"), ("1.0.0rc1+fixture", "4.1.0-beta.2"),
    ("vendor/1!2.0+build", "vendor/3.0"),
])
def test_compatible_public_api_accepts_other_versions_and_preserves_actual_provenance(sdk_version, runtime_version):
    client = FakeClient()
    client.initialization["claude_code_version"] = runtime_version
    client.init_change["claude_code_version"] = runtime_version
    result, _ = execute(client, sdk_version=sdk_version)
    assert result.status == "completed"
    assert result.sdk_execution["sdkVersion"] == sdk_version
    assert result.sdk_execution["runtimeVersion"] == runtime_version


@pytest.mark.parametrize("version", [None, "", " ", "wrong runtime", "1.2\n", 3, True, "1" * 129])
def test_malformed_sdk_provenance_does_not_connect(version):
    result, client = execute(sdk_version=version)
    assert result.execution_error == "invalid_sdk_version_metadata"
    assert client.calls == ["factory", "disconnect"] and result.protocol_closed


@pytest.mark.parametrize("method", ["connect", "query", "get_server_info", "receive_response", "interrupt", "disconnect"])
def test_missing_client_api_is_rejected_before_connection(method):
    client = FakeClient()
    setattr(client, method, None)
    result, _ = execute(client)
    assert result.execution_error == "missing_required_sdk_api"
    assert client.calls == (["factory"] if method == "disconnect" else ["factory", "disconnect"])
    assert result.protocol_closed is (method != "disconnect")
    assert result.cleanup_error == ("protocol_close_failed" if method == "disconnect" else None)


def test_incompatible_client_query_signature_is_rejected_before_connection():
    client = FakeClient()
    async def no_session_id(prompt):
        pytest.fail("incompatible query must not be called")
    client.query = no_session_id
    result, _ = execute(client)
    assert result.execution_error == "incompatible_sdk_api"
    assert client.calls == ["factory", "disconnect"] and result.protocol_closed


def test_coroutine_response_instead_of_async_iterator_is_rejected_before_connection():
    client = FakeClient()
    async def incompatible_response():
        pytest.fail("incompatible response must not be called")
    client.receive_response = incompatible_response
    result, _ = execute(client)
    assert result.execution_error == "incompatible_sdk_api"
    assert client.calls == ["factory", "disconnect"] and result.protocol_closed


def test_synchronous_async_iterator_factory_is_compatible():
    client = FakeClient()
    receive = client.receive_response
    client.receive_response = lambda: receive()
    result, _ = execute(client, sdk_version="9.8.7")
    assert result.status == "completed"


@pytest.mark.parametrize("version", ["2.1.309", "wrong runtime", None])
def test_optional_initialize_runtime_metadata_is_validated_before_query(version):
    client = FakeClient()
    if version is None:
        del client.initialization["claude_code_version"]
    else:
        client.initialization["claude_code_version"] = version
    result, _ = execute(client)
    assert client.calls.count("get_server_info") == 1 and result.protocol_closed
    if version == "wrong runtime":
        assert result.execution_error == "invalid_runtime_version_metadata"
        assert "query" not in client.calls and result.sdk_execution is None
    else:
        assert result.status == "completed" and "query" in client.calls


@pytest.mark.parametrize("phase", ["start", "connect", "query", "tool"])
def test_revocation_at_each_effect_gate(phase):
    client = FakeClient(); client.use_tool = True
    def authority(req, event):
        if event == phase:
            raise PermissionError("private authority detail")
    result, client = execute(client, authority=authority)
    assert result.status == "incomplete" and result.review is None
    assert "private authority detail" not in json.dumps(result.to_dict())
    if phase == "start":
        assert client.calls == []
    elif phase == "connect":
        assert "connect" not in client.calls
    elif phase == "query":
        assert "query" not in client.calls
    else:
        assert client.hook_output[0]["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_revocation_during_async_evidence_write_prevents_query():
    revoked = False
    async def sink(observation):
        nonlocal revoked
        if observation.kind == "query/start":
            revoked = True
            await asyncio.sleep(0)
    def authority(req, phase):
        if revoked:
            raise PermissionError("admission revoked during evidence write")
    result, client = execute(authority=authority, sink=sink)
    assert result.status == "incomplete" and result.protocol_closed
    assert "query" not in client.calls


def test_exact_path_permission_denial_and_unexpected_permission_request():
    client = FakeClient(); client.use_tool = True
    def authorize(req, name, arguments):
        raise PermissionError("not this path")
    result, client = execute(client, authorize=authorize)
    assert result.execution_error == "tool_authority_failed"
    assert client.hook_output[0]["hookSpecificOutput"]["permissionDecision"] == "deny"
    client = FakeClient()
    async def permission():
        denied = await client.options["can_use_tool"]("Bash", {"command": "effect"}, None)
        assert denied["behavior"] == "deny" and denied["interrupt"]
    client.before_query = permission
    result, _ = execute(client)
    assert result.execution_error == "unexpected_permission_request"


def test_tool_results_must_be_paired_and_duplicate_calls_denied():
    client = FakeClient(); client.use_tool = True; client.post_tool = False
    result, _ = execute(client)
    assert result.execution_error == "incomplete_tool_observations"
    client = FakeClient(); client.use_tool = True
    async def duplicate():
        denied = await client.hook("PreToolUse")
        assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"
    client.before_terminal = duplicate
    result, _ = execute(client)
    assert result.execution_error == "duplicate_tool_call"


def test_ordinary_paired_read_failure_remains_evidence_not_universal_review_veto():
    client = FakeClient(); client.use_tool = True; client.post_tool = False
    async def failure():
        result = await client.hook("PostToolUseFailure", error="File not found", is_interrupt=False)
        assert result == {}
    client.before_terminal = failure
    result, _ = execute(client)
    assert result.status == "completed"
    assert any(obs.kind == "hook/PostToolUseFailure" for obs in result.observations)


def test_unpaired_tool_failure_does_not_masquerade_as_completed_read():
    client = FakeClient()
    async def failure():
        await client.hook("PostToolUseFailure", error="File not found")
    client.before_terminal = failure
    result, _ = execute(client)
    assert result.execution_error == "unknown_or_duplicate_tool_result"


def test_tool_approval_never_defaults_to_allow_when_owner_returns_non_none():
    client = FakeClient(); client.use_tool = True
    result, _ = execute(client, authorize=lambda req, name, arguments: True)
    assert result.execution_error == "invalid_tool_authority_callback"


def test_failure_retained_when_disconnect_also_fails():
    client = FakeClient(); client.close_error = True
    client.terminal_change = {"is_error": True, "subtype": "error_during_execution", "structured_output": None}
    result, _ = execute(client)
    assert result.provider_status == result.status == "failed"
    assert result.execution_error == "provider_turn_failed"
    assert result.cleanup_error == "protocol_close_failed" and not result.protocol_closed
    assert result.sdk_execution["runtimeVersion"] == "2.1.309"


def test_success_evidence_survives_cleanup_failure_without_clean_completion():
    client = FakeClient(); client.close_error = True
    result, _ = execute(client)
    assert result.provider_status == "completed" and result.status == "incomplete"
    assert result.review is not None and result.cleanup_error == "protocol_close_failed"


def test_usage_bound_failure_keeps_acquired_terminal_and_review():
    client = FakeClient(); client.terminal_change["usage"] = {"unknown_counter": "x" * 65_536}
    result, _ = execute(client)
    assert result.provider_status == "completed" and result.status == "incomplete"
    assert result.execution_error == "usage_limit_exceeded" and result.review is not None
    assert result.usage is None and result.protocol_closed


def test_missing_terminal_interrupts_and_never_replays():
    client = FakeClient(); client.include_terminal = False
    result, client = execute(client)
    assert result.execution_error == "missing_terminal_result" and result.provider_status is None
    assert client.calls.count("query") == client.calls.count("interrupt") == client.calls.count("disconnect") == 1


def test_partial_connect_failure_still_closes_and_uncertain_query_not_replayed():
    client = FakeClient(); client.connect_error = True
    result, client = execute(client)
    assert "disconnect" in client.calls and "query" not in client.calls
    client = FakeClient(); client.query_error = True; client.interrupt_error = True
    result, client = execute(client)
    assert client.calls.count("query") == 1
    assert result.execution_error == "execution_or_interpretation_failed"
    assert result.cleanup_error == "interrupt_failed" and result.protocol_closed


def test_retention_bounds_and_evidence_sink_failure_are_not_success():
    result, _ = execute(req=request(max_events=1))
    assert result.capture_error == "observation_limit_exceeded"
    result, _ = execute(req=request(max_output_bytes=1))
    assert result.capture_error == "observation_limit_exceeded" and result.observations == ()
    captured = []
    def sink(observation):
        captured.append(observation)
        if observation.kind == "message/ResultMessage":
            raise OSError("synthetic disk full")
    result, _ = execute(sink=sink)
    assert result.provider_status == "completed" and result.status == "incomplete"
    assert result.capture_error == "evidence_persistence_failed"
    assert any(obs.kind == "message/ResultMessage" for obs in result.observations)


def test_concurrent_hooks_use_ordered_backpressured_sink():
    client = FakeClient()
    seen, finished = [], []
    async def sink(observation):
        seen.append(observation.sequence)
        await asyncio.sleep(0)
        finished.append(observation.sequence)
        assert seen == finished
    async def tool_pair(call_id):
        result = await client.hook("PreToolUse", tool_use_id=call_id)
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"
        await client.hook("PostToolUse", tool_use_id=call_id)
    async def tools():
        await asyncio.gather(tool_pair("a"), tool_pair("b"))
    client.before_terminal = tools
    result, _ = execute(client, sink=sink)
    assert result.status == "completed" and seen == list(range(len(seen)))


@pytest.mark.parametrize("pause", ["current", "tool"])
@pytest.mark.parametrize("concurrent_event,error", [
    ("PreToolUse", "duplicate_tool_call"),
    ("PostToolUse", "unknown_or_duplicate_tool_result"),
])
def test_pending_tool_identity_cannot_authorize_duplicates_or_pair_early(pause, concurrent_event, error):
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        calls = {"current": 0, "tool": 0}
        client = FakeClient()

        async def gate(phase):
            calls[phase] += 1
            if pause == phase:
                entered.set()
                await release.wait()

        async def authority(_request, effect):
            if effect == "tool":
                await gate("current")

        async def authorize(_request, _name, _arguments):
            await gate("tool")

        async def concurrent_hooks():
            pending = asyncio.create_task(client.hook("PreToolUse"))
            await entered.wait()
            try:
                rejected = await client.hook(concurrent_event)
                assert rejected["continue_"] is False and rejected["stopReason"] == error
                if concurrent_event == "PreToolUse":
                    assert rejected["hookSpecificOutput"]["permissionDecision"] == "deny"
            finally:
                release.set()
            first = await pending
            assert first["hookSpecificOutput"]["permissionDecision"] == "deny"
            assert first["stopReason"] == error
            # One later post result cannot turn the rejected duplicate into a
            # completed, paired tool exchange.
            assert (await client.hook("PostToolUse"))["continue_"] is False

        client.before_terminal = concurrent_hooks
        instance, _ = adapter(client, authority=authority, authorize=authorize)
        result = await instance.execute(request())
        assert calls == {"current": 1, "tool": 1}
        assert result.status == "incomplete" and result.execution_error == error
        assert result.provider_status == "completed" and result.protocol_closed
        assert client.calls.count("disconnect") == 1
        assert not Path(client.options["extra_args"]["append-system-prompt-file"]).exists()

    asyncio.run(asyncio.wait_for(scenario(), timeout=2))


def test_missing_or_malformed_sdk_message_and_tool_output_do_not_complete():
    client = FakeClient(); client.extra_messages = [object()]
    result, _ = execute(client)
    assert result.execution_error == "invalid_sdk_payload"
    client = FakeClient(); client.use_tool = True; client.post_tool = False
    async def bad_output():
        data = client.hook_input("PostToolUse")
        del data["tool_response"]
        callback = client.options["hooks"]["PostToolUse"][0]["hooks"][0]
        await callback(data, "call-1", {})
    client.before_terminal = bad_output
    result, _ = execute(client)
    assert result.execution_error == "missing_tool_output"


def test_operation_is_single_use_and_wrong_provider_cannot_construct():
    async def scenario():
        value, client = adapter()
        with pytest.raises(AdapterError, match="unsupported_provider"):
            await value.execute(request(provider="codex"))
        assert client.calls == []
        await value.execute(request())
        with pytest.raises(AdapterError, match="operation_already_consumed"):
            await value.execute(request())
    asyncio.run(scenario())


def test_cancel_during_connect_prevents_query_and_cancellation_receipts_are_not_settlement():
    async def scenario():
        value, client = adapter()
        async def cancel_now():
            receipt = await value.cancel("dispatch-1")
            assert receipt.requested and not receipt.acknowledged
        client.before_connect = cancel_now
        result = await value.execute(request())
        assert "query" not in client.calls and result.protocol_closed
        assert result.status == "interrupted" and result.provider_status is None
        assert result.to_tool_output()["process_settlement"] == "not_established"
        assert (await value.cancel("other")).error == "unknown_run"
        assert (await value.cancel("dispatch-1")).error == "already_finished"
    asyncio.run(scenario())


def test_outer_cancellation_keeps_acquired_terminal_and_closes_once():
    async def scenario():
        value, client = adapter()
        arrived, release = asyncio.Event(), asyncio.Event()
        async def pause():
            arrived.set()
            await release.wait()
        client.before_terminal = pause
        client.terminal_change = {"terminal_reason": "aborted_streaming", "structured_output": None}
        task = asyncio.create_task(value.execute(request()))
        await arrived.wait()
        task.cancel()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        release.set()
        result = await task
        assert result.provider_status == result.status == "interrupted"
        assert client.calls.count("interrupt") == client.calls.count("disconnect") == 1
        assert result.protocol_closed
    asyncio.run(scenario())


@pytest.mark.parametrize("second_cancel_during", ["interrupt", "execution"])
def test_repeated_cancellation_keeps_owned_interrupt_execution_and_evidence(second_cancel_during):
    async def scenario():
        value, client = adapter()
        execution_started, execution_release = asyncio.Event(), asyncio.Event()
        interrupt_started, interrupt_release, interrupt_finished = asyncio.Event(), asyncio.Event(), asyncio.Event()
        async def before_terminal():
            execution_started.set()
            await execution_release.wait()
        async def interrupt():
            client.calls.append("interrupt")
            interrupt_started.set()
            await interrupt_release.wait()
            interrupt_finished.set()
        client.before_terminal = before_terminal
        client.interrupt = interrupt
        client.terminal_change = {"terminal_reason": "aborted_streaming", "structured_output": None}
        task = asyncio.create_task(value.execute(request()))
        try:
            await execution_started.wait()
            task.cancel()
            await interrupt_started.wait()
            if second_cancel_during == "execution":
                interrupt_release.set()
                await interrupt_finished.wait()
                await asyncio.sleep(0)  # Let execute switch to its owned execution wait.
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
            execution_release.set()
            await asyncio.sleep(0)
            if second_cancel_during == "interrupt":
                assert "disconnect" not in client.calls
            interrupt_release.set()
            result = await task
            assert result.status == result.provider_status == "interrupted"
            assert result.protocol_closed
            assert client.calls.count("interrupt") == client.calls.count("disconnect") == 1
            assert any(obs.kind == "message/ResultMessage" for obs in result.observations)
        finally:
            execution_release.set()
            interrupt_release.set()
            await asyncio.gather(task, return_exceptions=True)
    asyncio.run(scenario())


@pytest.fixture
def official_sdk(monkeypatch):
    import importlib.metadata
    captured = {}
    class Options:
        def __init__(self, **kwargs):
            captured.update(kwargs)
    class Client(FakeClient):
        def __init__(self, *, options):
            super().__init__()
            self.options = options
            captured["constructed"] = True
    class HookMatcher:
        def __init__(self, **kwargs):
            self.hooks = kwargs["hooks"]
    class Deny:
        def __init__(self, **kwargs):
            self.behavior = kwargs["behavior"]
    monkeypatch.setattr(importlib.metadata, "version", lambda distribution: "9.8.7")
    sdk = SimpleNamespace(
        ClaudeAgentOptions=Options, ClaudeSDKClient=Client, HookMatcher=HookMatcher,
        PermissionResultDeny=Deny,
    )
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", sdk)
    return sdk, captured


def test_lazy_public_constructor_adapts_hooks_without_connecting(official_sdk):
    sdk, captured = official_sdk
    _, fake = execute()
    binding = _official_client_binding(fake.options, cli_path="/fixture/claude")
    assert isinstance(binding.client, sdk.ClaudeSDKClient) and binding.sdk_version == "9.8.7"
    assert binding.client.calls == []
    assert captured["cli_path"] == "/fixture/claude"
    assert isinstance(captured["hooks"]["Stop"][0], sdk.HookMatcher)
    denied = asyncio.run(captured["can_use_tool"]("Bash", {}, None))
    assert denied.behavior == "deny"


@pytest.mark.parametrize("name", ["ClaudeAgentOptions", "ClaudeSDKClient", "HookMatcher", "PermissionResultDeny"])
def test_missing_constructor_api_fails_before_client_construction(official_sdk, name):
    sdk, captured = official_sdk
    delattr(sdk, name)
    _, fake = execute()
    with pytest.raises(AdapterError, match="missing_required_sdk_api"):
        _official_client_binding(fake.options, cli_path="/fixture/claude")
    assert "constructed" not in captured


def test_missing_permission_option_fails_before_client_construction(official_sdk):
    sdk, captured = official_sdk
    sdk.ClaudeAgentOptions = lambda model: None
    _, fake = execute()
    with pytest.raises(AdapterError, match="incompatible_sdk_api"):
        _official_client_binding(fake.options, cli_path="/fixture/claude")
    assert "constructed" not in captured


def test_module_import_has_no_provider_import_or_client_construction(monkeypatch):
    import builtins
    import importlib.util
    original = builtins.__import__
    def forbidden(name, *args, **kwargs):
        if name == "claude_agent_sdk" or name.startswith("claude_agent_sdk."):
            raise AssertionError("provider import on module load")
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", forbidden)
    name = "sdk_execution._offline_import_probe"
    path = Path(__file__).resolve().parents[1] / "scripts/sdk_execution/claude.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)


def claude_selection(tmp_path, **changes):
    from sdk_execution.claude import ClaudeRuntimeSelection
    value = dict(
        executable=str(tmp_path / "synthetic-claude"), executable_sha256="a" * 64,
        config_dir=str(tmp_path / "config"), auth_mode="claude-direct",
        instructions="Current common governance and Claude/project rules.",
        prompts_dir=str(tmp_path / "instructions"), work_item=str(tmp_path / "item-1"),
        ledger_max_events=100, ledger_max_bytes=1_048_576,
        job_memory_limit_bytes=256 * 1024 * 1024, expected_launch_sha256="b" * 64,
    )
    value.update(changes)
    return ClaudeRuntimeSelection(**value)


def test_explicit_claude_selection_is_strict_and_part_of_common_commitment(tmp_path):
    from sdk_execution.claude import ClaudeRuntimeSelection
    from sdk_execution.runtime import request_sha256, runtime_selection_from_dict
    selected = claude_selection(tmp_path)
    assert ClaudeRuntimeSelection.from_dict(selected.to_dict()) == selected
    assert runtime_selection_from_dict("claude", selected.to_dict()) == selected
    assert request_sha256(request(), selected) != request_sha256(request(), replace(selected, instructions="Changed rules"))
    for change in ({"unknown": True}, {"job_memory_limit_bytes": True}, {"config_dir": "relative"},
                   {"instructions": ""}, {"executable_sha256": "not-a-hash"}):
        with pytest.raises((AdapterError, TypeError)):
            ClaudeRuntimeSelection.from_dict({**selected.to_dict(), **change})


@pytest.mark.parametrize("deny", [None, "query", "tool", "account"])
def test_fixed_claude_factory_awaits_parent_policy_tool_and_account_without_threads(tmp_path, monkeypatch, deny):
    from sdk_execution import claude, runtime
    selected = claude_selection(tmp_path)
    client = FakeClient()
    client.use_tool = True
    calls, captures = [], []
    monkeypatch.setattr(runtime, "assert_current_launch", lambda *_args: None)
    monkeypatch.setattr(runtime, "prepare_environment", lambda selection, source: (
        {"CLAUDE_CONFIG_DIR": selection.config_dir, "CLAUDE_PROMPTS_DIR": selection.prompts_dir}, object(),
    ))
    monkeypatch.setattr(claude.os, "environ", {"UNRELATED_SECRET": "must-not-survive"})

    def binding(options, *, cli_path):
        assert cli_path == selected.executable
        client.options = options
        client.instructions = Path(options["extra_args"]["append-system-prompt-file"]).read_text()
        client.calls.append("factory")
        return ClientBinding(client, SDK_VERSION)

    monkeypatch.setattr(claude, "_official_client_binding", binding)

    async def scenario():
        owning_task = asyncio.current_task()

        async def authorize(value, effect, context=None):
            assert value == request()
            # Stay on the SDK event loop, never block it on run_coroutine_threadsafe.
            assert asyncio.get_running_loop() is owning_task.get_loop()
            await asyncio.sleep(0)
            calls.append((effect, context))
            if effect == deny and (deny != "tool" or context is not None):
                raise PermissionError("private parent denial")

        async def record(observation):
            captures.append(observation)

        instance = claude.create_claude_adapter(request(), SimpleNamespace(authorize=authorize, record=record), selected)
        assert client.calls == []
        assert "UNRELATED_SECRET" not in claude.os.environ
        return await instance.execute(request())

    observed = asyncio.run(scenario())
    if deny is None:
        assert observed.status == "completed"
        assert captures == list(observed.observations)
        assert client.instructions == selected.instructions
        tool_calls = [context for effect, context in calls if effect == "tool" and context is not None]
        assert tool_calls == [{"kind": "tool", "name": "Read", "arguments": {"file_path": "/fixture/repo/a.py"}}]
        account_calls = [context["evidence"]["phase"] for effect, context in calls if effect == "account"]
        assert account_calls == ["before_connect", "initialize", "system_init"]
    else:
        assert observed.status == "incomplete" and observed.review is None
        assert "private parent denial" not in json.dumps(observed.to_dict())
        if deny == "account":
            assert client.calls == []
        elif deny == "query":
            assert "query" not in client.calls
        else:
            assert client.hook_output[0]["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("deny_tool", [False, True])
def test_claude_factory_and_real_pipe_protocol_recheck_exact_parent_tool_scope(tmp_path, monkeypatch, deny_tool):
    from sdk_execution import claude, runtime, worker
    selected = claude_selection(tmp_path)
    client = FakeClient()
    client.use_tool = True
    monkeypatch.setattr(runtime, "assert_current_launch", lambda *_args: None)
    monkeypatch.setattr(runtime, "prepare_environment", lambda selection, source: (
        {"CLAUDE_CONFIG_DIR": selection.config_dir, "CLAUDE_PROMPTS_DIR": selection.prompts_dir}, object(),
    ))
    monkeypatch.setattr(claude.os, "environ", {"UNRELATED_SECRET": "must-not-survive"})
    boundary = []
    monkeypatch.setattr(worker, "verify_current_job_memory_boundary", boundary.append, raising=False)

    def binding(options, *, cli_path):
        assert cli_path == selected.executable
        client.options = options
        client.instructions = Path(options["extra_args"]["append-system-prompt-file"]).read_text()
        client.calls.append("factory")
        return ClientBinding(client, SDK_VERSION)

    monkeypatch.setattr(claude, "_official_client_binding", binding)

    async def scenario():
        stdin_read, stdin_write = claude.os.pipe()
        stdout_read, stdout_write = claude.os.pipe()
        for fd in (stdin_write, stdout_read):
            claude.os.set_blocking(fd, False)
        parent = worker._PipeFrames(stdout_read, stdin_write)
        seen, acquired = [], []

        async def receive():
            await parent.write(worker.encode_frame({
                "kind": "execute", "request": request().to_dict(), "runtime_selection": selected.to_dict(),
            }))
            while True:
                frame = worker.decode_frame(await parent.read())
                if frame["kind"] == "authority_request":
                    assert frame["request_sha256"] == worker.request_binding(request())
                    assert frame["sequence"] == len(seen)
                    seen.append(frame)
                    context = frame.get("context")
                    if context is not None:
                        assert worker.authority_context(request(), frame["effect"], context) is not None
                    allowed = not (deny_tool and context is not None and context["kind"] == "tool")
                    await parent.write(worker.encode_frame({**frame, "kind": "authority_response", "allowed": allowed}))
                elif frame["kind"] == "observation":
                    acquired.append(frame["observation"])
                elif frame["kind"] == "result":
                    return ExecutionResult.from_dict(frame["result"]), seen, acquired
                else:
                    pytest.fail("unexpected frame")

        try:
            _served, captured = await asyncio.wait_for(asyncio.gather(
                worker.serve_stdio(worker._create_runtime_adapter, stdin_fd=stdin_read, stdout_fd=stdout_write),
                receive(),
            ), timeout=3)
            return captured
        finally:
            for fd in (stdin_read, stdin_write, stdout_read, stdout_write):
                claude.os.close(fd)

    observed, requests, acquired = asyncio.run(scenario())
    assert boundary == []  # Parent owner verifies the outer Job; worker must not query an inner venv Job.
    assert acquired == [item.to_dict() for item in observed.observations]
    contexts = [frame["context"] for frame in requests if "context" in frame]
    assert any(value == {"kind": "tool", "name": "Read", "arguments": {"file_path": "/fixture/repo/a.py"}}
               for value in contexts)
    assert observed.status == ("incomplete" if deny_tool else "completed")
    assert client.hook_output[0]["hookSpecificOutput"]["permissionDecision"] == ("deny" if deny_tool else "allow")
    assert observed.protocol_closed
    assert not Path(client.options["extra_args"]["append-system-prompt-file"]).exists()


def test_cancellation_while_awaiting_parent_grant_does_not_connect():
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()

        async def authority(_value, effect):
            if effect == "connect":
                entered.set()
                await release.wait()

        instance, client = adapter(authority=authority)
        execution = asyncio.create_task(instance.execute(request()))
        await asyncio.wait_for(entered.wait(), timeout=1)
        receipt = await instance.cancel(request().run_id)
        release.set()
        observed = await asyncio.wait_for(execution, timeout=1)
        assert receipt.requested and "connect" not in client.calls
        assert observed.status == "interrupted"
        assert observed.execution_error == "cancelled_before_effect"

    asyncio.run(scenario())
