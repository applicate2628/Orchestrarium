"""Offline production-composition fixtures; no provider or SDK process is run."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import sys
import time
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sdk_execution import runtime
from sdk_execution.codex_tools import CODEX_MCP_ISOLATION_OVERRIDES
from sdk_execution.contracts import ExecutionRequest
from test_agent_run_ledger import prepare_valid_work_item


def fixture(tmp_path):
    item = prepare_valid_work_item(tmp_path)
    executable = tmp_path / "synthetic-runtime.exe"
    executable.write_bytes(b"this fixture is never executed")
    home = tmp_path / "selected-home"
    home.mkdir()
    request = ExecutionRequest(
        work_item_id=item.name, provider="codex", external_dispatch_id="runtime-dispatch",
        external_evidence_run_id="runtime-evidence", artifact_id="sha256:" + "c" * 64,
        role="qa-engineer", model="fixture-model", effort="high", cwd=str(item),
        account_binding="explicit-account", prompt="Review only the admitted scope.",
        coordinator_binding="explicit-coordinator", scope=("synthetic repository review",),
    )
    selection = runtime.CodexRuntimeSelection(
        executable=str(executable), executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
        codex_home=str(home), auth_mode="codex-auth-file", expected_account_email="fixture@example.invalid",
        work_item=str(item), ledger_max_events=100, ledger_max_bytes=1_048_576,
        job_memory_limit_bytes=256 * 1024 * 1024,
    )
    return request, selection


def claim(request, selection, authority=lambda request, effect: None):
    return runtime.claim_launch(request, selection, authority=authority, started_at="2026-10-23T10:00:00Z")


def test_strict_selection_and_request_commitment(tmp_path):
    request, selection = fixture(tmp_path)
    assert runtime.CodexRuntimeSelection.from_dict(selection.to_dict()) == selection
    digest = runtime.request_sha256(request, selection)
    assert len(digest) == 64
    assert runtime.request_sha256(request, replace(selection, expected_launch_sha256="a" * 64)) == digest
    for changed in (replace(request, prompt="Different task"), replace(request, scope=("other",)),
                    replace(request, artifact_id="other"), replace(request, account_binding="other")):
        assert runtime.request_sha256(changed, selection) != digest
    assert runtime.request_sha256(request, replace(selection, job_memory_limit_bytes=512 * 1024 * 1024)) != digest
    with pytest.raises(runtime.RuntimeBindingError):
        runtime.CodexRuntimeSelection.from_dict({**selection.to_dict(), "qualified": True})


def test_selected_profile_does_not_invent_or_select_provider_versions(tmp_path):
    request, selection = fixture(tmp_path)
    selected = runtime.selected_sdk_execution(request, selection)
    assert selected == {
        "schemaVersion": 2, "adapter": "openai-codex", "model": request.model,
        "effort": request.effort, "sandboxMode": "read-only", "approvalPolicy": "deny_all",
        "accountBinding": request.account_binding, "requestSha256": runtime.request_sha256(request, selection),
    }


def test_codex_override_selection_is_exact_immutable_and_committed(tmp_path):
    request, selection = fixture(tmp_path)
    wire = selection.to_dict()
    wire["config_overrides"] = ['model_verbosity="low"', 'web_search="disabled"', *selection.config_overrides]
    selected = runtime.CodexRuntimeSelection.from_dict(wire)
    assert selected.config_overrides == tuple(wire["config_overrides"])
    assert runtime.CodexRuntimeSelection.from_dict(json.loads(json.dumps(selected.to_dict()))) == selected
    wire["config_overrides"].append("features.apps=false")
    assert len(selected.config_overrides) == 6
    detached = selected.to_dict()
    detached["config_overrides"].clear()
    assert len(selected.config_overrides) == 6
    assert runtime.request_sha256(request, selected) != runtime.request_sha256(request, selection)
    assert runtime.request_sha256(request, selected) != runtime.request_sha256(
        request, replace(selected, config_overrides=(*reversed(selected.config_overrides), *CODEX_MCP_ISOLATION_OVERRIDES)))
    admitted = claim(request, selected)
    runtime.assert_current_launch(request, admitted, "client_start")
    with pytest.raises(runtime.RuntimeBindingError, match="changed_or_settled"):
        runtime.assert_current_launch(request, replace(admitted, config_overrides=CODEX_MCP_ISOLATION_OVERRIDES), "turn_start")


@pytest.mark.parametrize("invalid", [None, "features.apps=false", (), [None], [True], [""], [" "], ["a=\x00"]])
def test_codex_override_wire_requires_json_array_of_nonempty_strings(tmp_path, invalid):
    _, selection = fixture(tmp_path)
    with pytest.raises(runtime.RuntimeBindingError, match="invalid_codex_config_overrides"):
        runtime.CodexRuntimeSelection.from_dict({**selection.to_dict(), "config_overrides": invalid})


def test_codex_override_constructor_requires_immutable_tuple(tmp_path):
    _, selection = fixture(tmp_path)
    with pytest.raises(runtime.RuntimeBindingError, match="invalid_codex_config_overrides"):
        replace(selection, config_overrides=["features.apps=false"])


def test_existing_governance_prompt_owner_is_used(tmp_path):
    request, _ = fixture(tmp_path)
    import provider_prompt
    effective = runtime.prepare_codex_request(request)
    assert effective.prompt == provider_prompt.assemble_external_prompt(request.prompt.encode()).decode()
    assert effective.prompt.endswith(request.prompt)


def test_explicit_auth_environment_drops_ambient_inputs(tmp_path, monkeypatch):
    _, selection = fixture(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "ambient-is-not-selected")
    environment, context = runtime.prepare_environment(selection, {"PATH": "/fixture/path", "UNRELATED_SECRET": "never-forward"})
    assert environment == {"PATH": "/fixture/path", "CODEX_HOME": selection.codex_home}
    assert context.needles == ()
    with pytest.raises(runtime.RuntimeBindingError, match="selected_home_environment_mismatch"):
        runtime.prepare_environment(selection, {"CODEX_HOME": "/different"})
    with pytest.raises(runtime.RuntimeBindingError, match="selected_auth_mode_mismatch"):
        runtime.prepare_environment(selection, {"OPENAI_API_KEY": "explicit-synthetic-key"})


def test_api_key_has_mode_only_and_preserves_scan_needles(tmp_path):
    _, selection = fixture(tmp_path)
    selection = replace(selection, auth_mode="codex-api-key", expected_account_email=None)
    environment, context = runtime.prepare_environment(selection, {"OPENAI_API_KEY": "explicit-synthetic-key"})
    assert environment["OPENAI_API_KEY"] == "explicit-synthetic-key"
    assert context.needles == (b"explicit-synthetic-key",)
    with pytest.raises(runtime.RuntimeBindingError, match="not_observable"):
        replace(selection, expected_account_email="invented@example.invalid")


def test_claim_current_binding_and_refuse_replay(tmp_path):
    request, selection = fixture(tmp_path)
    admitted = claim(request, selection)
    runtime.assert_current_launch(request, admitted, "thread_start")
    events = [json.loads(line) for line in (Path(selection.work_item) / "agent-runs.jsonl").read_text().splitlines()]
    assert events[0]["sdkExecution"]["requestSha256"] == runtime.request_sha256(request, selection)
    with pytest.raises(runtime.RuntimeBindingError, match="not_replay_authority"):
        claim(request, selection)
    with pytest.raises(runtime.RuntimeBindingError, match="changed_or_settled"):
        runtime.assert_current_launch(replace(request, prompt="swapped"), admitted, "turn_start")


def test_multi_scope_launch_preserves_each_scope_entry(tmp_path):
    request, selection = fixture(tmp_path)
    request = replace(request, scope=("first review surface", "--second review surface"))
    admitted = claim(request, selection)
    runtime.assert_current_launch(request, admitted, "thread_start")
    events = [json.loads(line) for line in (Path(selection.work_item) / "agent-runs.jsonl").read_text().splitlines()]
    assert events[0]["scope"] == list(request.scope)


def test_current_runtime_file_change_refused(tmp_path):
    request, selection = fixture(tmp_path)
    admitted = claim(request, selection)
    Path(selection.executable).write_bytes(b"changed synthetic bytes")
    with pytest.raises(runtime.RuntimeBindingError, match="runtime_changed"):
        runtime.assert_current_launch(request, admitted, "client_start")


@pytest.mark.parametrize("result", [True, False, "allow"])
def test_policy_callback_is_not_a_boolean_permission_switch(tmp_path, result):
    request, selection = fixture(tmp_path)
    with pytest.raises(runtime.RuntimeBindingError, match="must_raise"):
        claim(request, selection, lambda request, effect: result)
    ledger = Path(selection.work_item) / "agent-runs.jsonl"
    assert not ledger.exists() or not ledger.read_bytes()


def test_real_factory_builds_explicit_config_without_launch(tmp_path, monkeypatch):
    request, selection = fixture(tmp_path)
    selection = replace(selection, config_overrides=("agents.enabled=false", "features.multi_agent_v2=false", *CODEX_MCP_ISOLATION_OVERRIDES))
    admitted = claim(request, selection)
    monkeypatch.setattr(runtime.os, "environ", {"CODEX_HOME": selection.codex_home, "UNRELATED_SECRET": "not-forwarded"})
    created = []
    class Config:
        def __init__(self, **kwargs):
            created.append(kwargs)
    module = types.ModuleType("openai_codex.client")
    module.CodexConfig = Config
    monkeypatch.setitem(sys.modules, "openai_codex.client", module)
    from sdk_execution import codex
    monkeypatch.setattr(codex, "_official_client_binding", lambda config, handler: (config, handler))
    grants = []
    sink = types.SimpleNamespace(record_from_thread=lambda observation: None,
                                 authorize_from_thread=lambda current, effect: grants.append((current, effect)))
    adapter = runtime.create_codex_adapter(request, sink, admitted)
    assert created == []  # Provider construction is still lazy until adapter execute.
    adapter._factory(lambda **kwargs: {"decision": "decline"})
    assert created == [{"codex_bin": selection.executable, "cwd": request.cwd,
                        "env": {"CODEX_HOME": selection.codex_home}, "config_overrides": selection.config_overrides}]
    adapter._assert_current(request, "turn_start")
    assert grants == [(request, "turn_start")]
    assert adapter._verify_account(request, {"account": {"type": "chatgpt", "email": "fixture@example.invalid"}}) == request.account_binding
    with pytest.raises(runtime.RuntimeBindingError, match="account_mismatch"):
        adapter._verify_account(request, {"account": {"type": "chatgpt", "email": "other@example.invalid"}})


@pytest.mark.parametrize("explicit_package", [False, True])
def test_parent_calls_owned_worker_with_admitted_envelope(tmp_path, monkeypatch, explicit_package):
    request, selection = fixture(tmp_path)
    selection = replace(selection, installed_hook_root=str(tmp_path / "selected package") if explicit_package else None)
    selection = replace(selection, config_overrides=("agents.enabled=false", "features.multi_agent_v2=false", *CODEX_MCP_ISOLATION_OVERRIDES))
    import provider_prompt
    from process_supervision.process_runner import ProcessRunnerV1
    from process_supervision import sdk_worker
    effects, calls, trust_calls = [], [], []
    monkeypatch.setattr(provider_prompt, "require_codex_hook_trust", lambda *args, **kwargs: trust_calls.append((args, kwargs)) or 0)
    monkeypatch.setattr(sdk_worker, "run_sdk_worker", lambda *args, **kwargs: calls.append((args, kwargs)) or "synthetic-observation")
    deadline = time.monotonic() + 60
    cancellation_probe = lambda: False
    with ProcessRunnerV1() as owner:
        result = runtime.run_codex(request, selection, owner=owner, source_environment={},
            authority=lambda request, effect: effects.append(effect), deadline_monotonic=deadline,
            cancellation_probe=cancellation_probe, started_at="2026-10-23T10:00:00Z")
    assert result.observation == "synthetic-observation"
    assert result.request.prompt != request.prompt
    assert calls[0][1]["runtime_selection"] == result.selection.to_dict()
    assert trust_calls[0][0][1:] == (
        [selection.executable, *(token for setting in selection.config_overrides for token in ("--config", setting))],
        Path(selection.codex_home), Path(request.cwd))
    assert trust_calls[0][1] == {"deadline_monotonic": deadline, "cancellation_probe": cancellation_probe,
                                  "installed_root": Path(selection.installed_hook_root) if explicit_package else None}
    assert calls[0][1]["cancellation_probe"] is cancellation_probe
    assert effects == ["sdk_prepare", "sdk_launch_admission", "sdk_launch_commit", "sdk_hook_trust", "sdk_worker_start"]


def test_parent_policy_is_rechecked_for_each_worker_effect(tmp_path, monkeypatch):
    request, selection = fixture(tmp_path)
    selection = replace(selection, config_overrides=("features.apps=false", *CODEX_MCP_ISOLATION_OVERRIDES))
    import provider_prompt
    from process_supervision.process_runner import ProcessRunnerV1
    from process_supervision import sdk_worker
    allowed = True
    effects = []
    def authority(current, effect):
        effects.append(effect)
        if not allowed:
            raise runtime.RuntimeBindingError("synthetic_policy_revoked")
    monkeypatch.setattr(provider_prompt, "require_codex_hook_trust", lambda *args, **kwargs: 0)
    def worker(owner, effective, **kwargs):
        nonlocal allowed
        assert kwargs["runtime_selection"]["config_overrides"] == list(selection.config_overrides)
        kwargs["authority"](effective, "client_start")
        allowed = False
        with pytest.raises(runtime.RuntimeBindingError, match="policy_revoked"):
            kwargs["authority"](effective, "turn_start")
        return "synthetic-denial-observation"
    monkeypatch.setattr(sdk_worker, "run_sdk_worker", worker)
    with ProcessRunnerV1() as owner:
        result = runtime.run_codex(request, selection, owner=owner, source_environment={},
            authority=authority, deadline_monotonic=time.monotonic() + 60,
            cancellation_probe=lambda: False, started_at="2026-10-23T10:00:00Z")
    assert result.observation == "synthetic-denial-observation"
    assert effects[-2:] == ["client_start", "turn_start"]


@pytest.mark.parametrize("bounded", [False, True])
@pytest.mark.parametrize("role_state", ["factory", "configured", "instructions-drift"])
def test_run_scoped_feature_overrides_preserve_role_identity(tmp_path, monkeypatch, role_state, bounded):
    """SDK launch controls must not become persistent native-role customization."""
    from test_role_policy_default_profile_floors import RESOLVER
    import provider_prompt
    from process_supervision.process_runner import ProcessRunnerV1
    from process_supervision import sdk_worker
    from sdk_execution import codex

    request, selection = fixture(tmp_path)
    home = Path(selection.codex_home)
    roles = ("architect", "architecture-reviewer")
    paths = [home / "config.toml"]
    paths[0].write_text('[features]\nplugins = true\napps = true\n', encoding="utf-8")
    for name in ("shared/role-routing-policy.v1.json",
                 "src.codex/agents/orchestrarium-role-manifest.json",
                 *(f"src.codex/agents/{role}.toml" for role in roles)):
        target = home / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
        paths.append(target)
    host = {"explicitModelControl": True, "explicitReasoningEffortControl": True}
    for role in roles:
        assert RESOLVER.describe_ordinary_native_role_options(
            role, "critical-design", host, repo_root=home)["status"] == "available"
        target = home / "src.codex/agents" / f"{role}.toml"
        if role_state == "configured":
            # Compatible settings differ from the factory bytes, not the owned
            # profession instructions. Keep valid TOML rather than duplicate tables.
            original = target.read_bytes()
            configured = original.replace(b"plugins = false", b"plugins = true").replace(
                b"apps = false", b"apps = true")
            assert configured != original
            target.write_bytes(configured)
        elif role_state == "instructions-drift":
            original = target.read_bytes()
            marker = b'developer_instructions = """'
            assert original.count(marker) == 1
            target.write_bytes(original.replace(marker, marker + b"\nChanged profession contract.\n", 1))
    before = {path: path.read_bytes() for path in paths}
    selection = replace(selection, config_overrides=(runtime.CODEX_BOUNDED_REVIEW_OVERRIDES if bounded else
        ("features.plugins=false", "features.apps=false", *CODEX_MCP_ISOLATION_OVERRIDES)))
    monkeypatch.setattr(runtime.os, "environ", {"CODEX_HOME": selection.codex_home})
    created, trust_calls = [], []

    class Config:
        def __init__(self, **kwargs):
            created.append(kwargs)

    module = types.ModuleType("openai_codex.client")
    module.CodexConfig = Config
    monkeypatch.setitem(sys.modules, "openai_codex.client", module)
    monkeypatch.setattr(codex, "_official_client_binding", lambda config, handler: (config, handler))
    monkeypatch.setattr(provider_prompt, "require_codex_hook_trust",
                        lambda *args, **kwargs: trust_calls.append(args) or 0)

    def worker(owner, effective, **kwargs):
        admitted = runtime.CodexRuntimeSelection.from_dict(kwargs["runtime_selection"])
        sink = types.SimpleNamespace(record_from_thread=lambda observation: None,
                                     authorize_from_thread=kwargs["authority"])
        adapter = runtime.create_codex_adapter(effective, sink, admitted)
        assert adapter._bounded_startup_profile is bounded
        adapter._factory(lambda **kwargs: {"decision": "decline"})
        return "offline-config-observation"

    monkeypatch.setattr(sdk_worker, "run_sdk_worker", worker)
    with ProcessRunnerV1() as owner:
        result = runtime.run_codex(
            request, selection, owner=owner, source_environment={},
            authority=lambda request, effect: None, deadline_monotonic=time.monotonic() + 60,
            cancellation_probe=lambda: False, started_at="2026-10-23T10:00:00Z")
    assert result.observation == "offline-config-observation"
    assert created == [{"codex_bin": selection.executable, "cwd": request.cwd,
                        "env": {"CODEX_HOME": selection.codex_home},
                        "config_overrides": selection.config_overrides}]
    assert trust_calls[0][1] == [selection.executable, *(token for setting in selection.config_overrides
                                                                  for token in ("--config", setting))]
    for role in roles:
        decision = RESOLVER.describe_ordinary_native_role_options(
            role, "critical-design", host, repo_root=home)
        assert decision["status"] == ("denied" if role_state == "instructions-drift" else "available")
        if role_state == "instructions-drift":
            assert decision["stableId"] == "E_ORDINARY_NATIVE_SELECTION_INVALID"
            assert decision["fallback"] == "none"
    assert {path: path.read_bytes() for path in paths} == before


def test_parent_settles_known_preworker_failure_without_fake_observation(tmp_path, monkeypatch):
    request, selection = fixture(tmp_path)
    import provider_prompt
    from process_supervision.process_runner import ProcessRunnerV1
    from process_supervision import sdk_worker
    monkeypatch.setattr(provider_prompt, "require_codex_hook_trust", lambda *args, **kwargs: 0)
    monkeypatch.setattr(sdk_worker, "run_sdk_worker", lambda *args, **kwargs: pytest.fail("cancelled operation must not start worker"))
    cancelled = False
    def authority(request, effect):
        nonlocal cancelled
        if effect == "sdk_worker_start":
            cancelled = True
    with ProcessRunnerV1() as owner:
        result = runtime.run_codex(request, selection, owner=owner, source_environment={},
            authority=authority, deadline_monotonic=time.monotonic() + 60,
            cancellation_probe=lambda: cancelled, started_at="2026-10-23T10:00:00Z")
    assert result.observation is None
    assert result.terminal["status"] == "blocked"
    assert result.terminal["sdkExecution"]["requestSha256"] == runtime.request_sha256(result.request, result.selection)
    assert "sdkVersion" not in result.terminal["sdkExecution"]
    assert "runtimeVersion" not in result.terminal["sdkExecution"]
    with pytest.raises(runtime.RuntimeBindingError, match="changed_or_settled"):
        runtime.assert_current_launch(result.request, result.selection, "turn_start")


@pytest.mark.parametrize("cancelled,deadline,expected", [
    (True, float("inf"), "cancelled_before_worker"),
    (False, 0.0, "deadline_before_worker"),
    (False, float("nan"), "invalid_operation_deadline"),
    ("not a boolean", 1000.0, "invalid_cancellation_observation"),
])
def test_cancelled_or_invalid_parent_does_not_probe_or_claim(tmp_path, monkeypatch, cancelled, deadline, expected):
    request, selection = fixture(tmp_path)
    import provider_prompt
    from process_supervision.process_runner import ProcessRunnerV1
    monkeypatch.setattr(provider_prompt, "require_codex_hook_trust", lambda *args, **kwargs: pytest.fail("must not probe"))
    with ProcessRunnerV1() as owner, pytest.raises(runtime.RuntimeBindingError, match=expected):
        runtime.run_codex(request, selection, owner=owner, source_environment={},
            authority=lambda request, effect: None, deadline_monotonic=deadline,
            cancellation_probe=lambda: cancelled, started_at="2026-10-23T10:00:00Z")
    assert not (Path(selection.work_item) / "agent-runs.jsonl").exists()


def test_existing_launch_prevents_even_the_native_trust_probe(tmp_path, monkeypatch):
    request, selection = fixture(tmp_path)
    claim(runtime.prepare_codex_request(request), selection)
    import provider_prompt
    from process_supervision.process_runner import ProcessRunnerV1
    monkeypatch.setattr(provider_prompt, "require_codex_hook_trust", lambda *args, **kwargs: pytest.fail("must not probe a prior launch"))
    with ProcessRunnerV1() as owner, pytest.raises(runtime.RuntimeBindingError, match="not_replay_authority"):
        runtime.run_codex(request, selection, owner=owner, source_environment={},
            authority=lambda request, effect: None, deadline_monotonic=time.monotonic() + 60,
            cancellation_probe=lambda: False, started_at="2026-10-23T10:00:00Z")


def test_failed_trust_probe_settles_blocked_before_worker(tmp_path, monkeypatch):
    request, selection = fixture(tmp_path)
    import provider_prompt
    from process_supervision.process_runner import ProcessRunnerV1
    from process_supervision import sdk_worker
    monkeypatch.setattr(provider_prompt, "require_codex_hook_trust", lambda *args, **kwargs: 1)
    monkeypatch.setattr(sdk_worker, "run_sdk_worker", lambda *args, **kwargs: pytest.fail("must not start worker"))
    with ProcessRunnerV1() as owner:
        result = runtime.run_codex(request, selection, owner=owner, source_environment={},
            authority=lambda request, effect: None, deadline_monotonic=time.monotonic() + 60,
            cancellation_probe=lambda: False, started_at="2026-10-23T10:00:00Z")
    assert result.terminal["status"] == "blocked"
    assert result.observation is None
    assert result.launch_error == "selected_codex_hook_trust_unavailable"


def test_runtime_verifier_uses_consistent_handle_metadata(tmp_path, monkeypatch):
    """Windows path stat and handle stat can expose different ctime values."""
    _, selection = fixture(tmp_path)
    executable = Path(selection.executable)
    original_stat = Path.stat

    def path_stat(path, *args, **kwargs):
        result = original_stat(path, *args, **kwargs)
        if path == executable:
            fields = {name: getattr(result, name) for name in dir(result) if name.startswith('st_')}
            fields['st_ctime_ns'] += 1
            return types.SimpleNamespace(**fields)
        return result

    monkeypatch.setattr(Path, 'stat', path_stat)
    runtime._verify_runtime(selection)


@pytest.mark.parametrize('field', ['st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns'])
@pytest.mark.parametrize('changed_call', [2, 3])
def test_runtime_verifier_rejects_handle_metadata_changes(tmp_path, monkeypatch, field, changed_call):
    _, selection = fixture(tmp_path)
    original_fstat = runtime.os.fstat
    calls = []

    def changed_fstat(fd):
        result = original_fstat(fd)
        calls.append(fd)
        if len(calls) == changed_call:
            fields = {name: getattr(result, name) for name in dir(result) if name.startswith('st_')}
            fields[field] += 1
            return types.SimpleNamespace(**fields)
        return result

    monkeypatch.setattr(runtime.os, 'fstat', changed_fstat)
    with pytest.raises(runtime.RuntimeBindingError, match='selected_runtime_changed'):
        runtime._verify_runtime(selection)


def test_runtime_verifier_rejects_changed_digest(tmp_path):
    _, selection = fixture(tmp_path)
    with pytest.raises(runtime.RuntimeBindingError, match='selected_runtime_changed'):
        runtime._verify_runtime(replace(selection, executable_sha256='0' * 64))


def test_codex_mcp_scope_is_immutable_and_committed(tmp_path):
    from sdk_execution.codex_tools import CodexMcpScope
    request, selection = fixture(tmp_path)
    selected = replace(selection, mcp_scope=CodexMcpScope((("Docs", ("read",)),)))
    assert runtime.request_sha256(request, selection) != runtime.request_sha256(request, selected)
    wire = selected.to_dict()
    assert wire["mcp_scope"] == {"servers": [{"name": "Docs", "tools": ["read"]}]}
    assert runtime.CodexRuntimeSelection.from_dict(wire) == selected
    wire["mcp_scope"]["servers"][0]["tools"].append("write")
    assert selected.mcp_scope.servers == (("Docs", ("read",)),)


def test_codex_isolation_overrides_are_materialized_before_claim(tmp_path):
    from sdk_execution.codex_tools import CODEX_MCP_ISOLATION_OVERRIDES
    request, selection = fixture(tmp_path)
    assert selection.config_overrides == CODEX_MCP_ISOLATION_OVERRIDES
    with pytest.raises(runtime.RuntimeBindingError, match="isolation"):
        replace(selection, config_overrides=('model_verbosity="low"',))
    selected = replace(selection, config_overrides=('model_verbosity="low"', *CODEX_MCP_ISOLATION_OVERRIDES))
    assert selected.config_overrides == ('model_verbosity="low"', *CODEX_MCP_ISOLATION_OVERRIDES)
    assert selected.to_dict()["config_overrides"] == list(selected.config_overrides)
    claimed = claim(request, selected)
    assert claimed.config_overrides == selected.config_overrides


def test_codex_wire_does_not_silently_rewrite_isolation_selection(tmp_path):
    _request, selection = fixture(tmp_path)
    wire = selection.to_dict()
    wire["config_overrides"] = []
    with pytest.raises(runtime.RuntimeBindingError, match="isolation"):
        runtime.CodexRuntimeSelection.from_dict(wire)


def test_launch_argument_builder_is_pure_and_claim_uses_exact_event(tmp_path, monkeypatch):
    request, selection = fixture(tmp_path)
    timestamp = "2026-10-23T10:00:00Z"
    ledger = Path(selection.work_item) / "agent-runs.jsonl"
    before = ledger.read_bytes() if ledger.exists() else None
    arguments = runtime.build_launch_arguments(request, selection, started_at=timestamp)
    assert (ledger.read_bytes() if ledger.exists() else None) == before
    assert arguments[-1] == "--scope=" + request.scope[0]
    import provider_prompt
    control = provider_prompt.Control(ledger=selection.work_item,
        ledger_max_events=selection.ledger_max_events, ledger_max_bytes=selection.ledger_max_bytes)
    provider_prompt.prepare_ledger_admission(control, arguments)
    assert control.resolved_ledger_budget is not None
    assert (ledger.read_bytes() if ledger.exists() else None) == before
    writer, validator, _ = runtime._ledger(selection)
    expected = writer.build_event(writer.build_parser().parse_args(arguments), validator)
    calls = []
    original = runtime.build_launch_arguments
    def builder(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)
    monkeypatch.setattr(runtime, "build_launch_arguments", builder)
    admitted = claim(request, selection)
    assert len(calls) == 1
    assert admitted.expected_launch_sha256 == writer.launch_event_sha256(expected, validator)
    with pytest.raises(runtime.RuntimeBindingError, match="existing_launch_is_not_replay_authority"):
        claim(request, selection)


@pytest.mark.parametrize("entry", ["run_codex", "run_admitted_review"])
@pytest.mark.parametrize("capture", [None, 1, 12345, 16 * 1024 * 1024])
def test_capture_budget_is_forwarded_exactly(tmp_path, monkeypatch, entry, capture):
    request, selection = fixture(tmp_path)
    import provider_prompt
    from process_supervision.process_runner import MAX_STDIN_BYTES, ProcessRunnerV1
    from process_supervision import sdk_worker
    if entry == "run_admitted_review":
        request = runtime.prepare_codex_request(request)
    calls = []
    monkeypatch.setattr(provider_prompt, "require_codex_hook_trust", lambda *args, **kwargs: 0)
    monkeypatch.setattr(sdk_worker, "run_sdk_worker", lambda *args, **kwargs: calls.append(kwargs) or "offline")
    options = {} if capture is None else {"capture_limit_bytes": capture}
    with ProcessRunnerV1() as owner:
        result = getattr(runtime, entry)(request, selection, owner=owner, source_environment={},
            authority=lambda *args: None, deadline_monotonic=time.monotonic() + 60,
            cancellation_probe=lambda: False, started_at="2026-10-23T10:00:00Z", **options)
    assert result.observation == "offline"
    assert len(calls) == 1
    assert calls[0]["capture_limit_bytes"] == (MAX_STDIN_BYTES if capture is None else capture)


@pytest.mark.parametrize("entry", ["run_codex", "run_admitted_review"])
@pytest.mark.parametrize("capture", [False, True, 0, -1, 1.0, "1024", None, 16 * 1024 * 1024 + 1])
def test_invalid_capture_budget_fails_before_effects(tmp_path, monkeypatch, entry, capture):
    request, selection = fixture(tmp_path)
    from process_supervision.process_runner import ProcessRunnerV1
    if entry == "run_admitted_review":
        request = runtime.prepare_codex_request(request)
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid capture budget reached an effect owner")
    monkeypatch.setattr(runtime, "claim_launch", forbidden)
    monkeypatch.setattr(runtime, "prepare_environment", forbidden)
    with ProcessRunnerV1() as owner:
        with pytest.raises(runtime.RuntimeBindingError, match="invalid_worker_capture_budget"):
            getattr(runtime, entry)(request, selection, owner=owner, source_environment={},
                authority=forbidden, deadline_monotonic=time.monotonic() + 60,
                cancellation_probe=lambda: False, started_at="2026-10-23T10:00:00Z",
                capture_limit_bytes=capture)


def test_omitted_ledger_caps_remain_implicit_across_interleaved_launches(tmp_path):
    request, explicit = fixture(tmp_path)
    selection = replace(explicit, ledger_max_events=None, ledger_max_bytes=None)
    assert runtime.CodexRuntimeSelection.from_dict(selection.to_dict()) == selection
    assert runtime.request_sha256(request, selection) != runtime.request_sha256(request, explicit)
    first = claim(request, selection)
    other = replace(request, external_dispatch_id="other-dispatch", external_evidence_run_id="other-evidence")
    second = claim(other, selection)
    assert first.ledger_max_events is None and first.ledger_max_bytes is None
    runtime.assert_current_launch(request, first, "client_start")
    for operation, admitted in ((request, first), (other, second)):
        terminal = runtime._settle_before_worker_failure(
            operation, admitted, started_at="2026-10-23T10:00:00Z")
        assert terminal["status"] == "blocked" and terminal["authorizing"] is False
    rows = [json.loads(line) for line in (Path(selection.work_item) / "agent-runs.jsonl").read_text().splitlines()]
    assert [row["eventKind"] for row in rows] == ["launch", "launch", "terminal", "terminal"]


@pytest.mark.parametrize("events,bytes_limit", [(None, 100), (100, None), (0, 100), (True, 100)])
def test_omitted_ledger_caps_require_a_complete_valid_pair(tmp_path, events, bytes_limit):
    _request, selection = fixture(tmp_path)
    with pytest.raises(runtime.RuntimeBindingError, match="positive_resource_budget"):
        replace(selection, ledger_max_events=events, ledger_max_bytes=bytes_limit)


@pytest.mark.parametrize("mutation", ["settle", "replace", "remove"])
def test_current_launch_rejects_ledger_capture_drift(tmp_path, monkeypatch, mutation):
    request, selection = fixture(tmp_path)
    selection = claim(request, selection)
    writer, validator, budget = runtime._ledger(selection)
    monkeypatch.setattr(runtime, "_ledger", lambda _selection: (writer, validator, budget))
    ledger = Path(selection.work_item) / "agent-runs.jsonl"
    captured = ledger.read_bytes()
    original = validator.validate_work_item
    armed = True

    def validate_then_change(*args, **kwargs):
        nonlocal armed
        errors = original(*args, **kwargs)
        if armed and kwargs.get("selected_ledger_bytes") == captured:
            armed = False
            assert not errors
            if mutation == "settle":
                runtime._settle_before_worker_failure(
                    request, selection, started_at="2026-10-23T10:00:00Z")
            elif mutation == "replace":
                replacement = ledger.with_suffix(".replacement")
                replacement.write_bytes(captured)
                replacement.replace(ledger)
            else:
                ledger.unlink()
        return errors

    monkeypatch.setattr(validator, "validate_work_item", validate_then_change)
    with pytest.raises(runtime.RuntimeBindingError, match="current_ledger_invalid"):
        runtime.assert_current_launch(request, selection, "turn_start")
    assert not armed
