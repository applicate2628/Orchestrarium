"""Offline wire contract; this does not admit a Copilot policy or registration."""

import importlib.util

from pathlib import Path

import sys

import pytest



PATH = Path(__file__).resolve().parents[1] / "scripts/installation/copilot_transport.py"

spec = importlib.util.spec_from_file_location("copilot_transport", PATH)

transport = importlib.util.module_from_spec(spec)

sys.modules[spec.name] = transport

spec.loader.exec_module(transport)



@pytest.mark.parametrize("shape", ["camel", "snake"])

def test_preserves_tool_semantics_and_neutral_decision(shape):

    args = {"command": "echo fixture", "unknown": ["kept"]}

    payload = {"cwd": "/fixture", "toolName": "powershell", "toolArgs": args} if shape == "camel" else {

        "cwd": "/fixture", "hook_event_name": "PreToolUse", "tool_name": "run_in_terminal", "tool_input": args}

    call = transport.read_pre_tool_use(payload, registration_event="preToolUse")

    assert call.format == shape

    assert call.cwd == "/fixture"

    assert call.arguments is args

    assert call.tool_name == payload.get("toolName", payload.get("tool_name"))

    assert transport.render_pre_tool_use(call) == {}



@pytest.mark.parametrize("payload", [

    None, [], {}, {"cwd": "/fixture", "toolName": "bash"},

    {"cwd": "/fixture", "tool_name": "Bash", "tool_input": {}, "toolArgs": {}},

    {"cwd": "/fixture", "toolName": "bash", "toolArgs": {}, "tool_name": "Bash"},

    {"cwd": "", "toolName": "bash", "toolArgs": {}},

    {"cwd": "/fixture", "toolName": "", "toolArgs": {}},

    {"cwd": "/fixture", "toolName": "bash", "toolArgs": "[]"},

    {"cwd": "/fixture", "tool_name": "Bash", "tool_input": {}, "hook_event_name": "PostToolUse"},

])

def test_unqualified_envelopes_refuse_without_echoing_data(payload):

    with pytest.raises(ValueError, match="^COPILOT-HOOK-INPUT$"):

        transport.read_pre_tool_use(payload, registration_event="preToolUse")



@pytest.mark.parametrize("shape", ["camel", "snake"])

def test_deny_uses_matching_wire_shape_and_never_allows(shape):

    payload = {"cwd": "/fixture", "toolName": "unknown", "toolArgs": {}} if shape == "camel" else {

        "cwd": "/fixture", "tool_name": "unknown", "tool_input": {}, "hook_event_name": "PreToolUse"}

    call = transport.read_pre_tool_use(payload, registration_event="preToolUse")

    result = transport.render_pre_tool_use(call, denial_reason="Policy refused.")

    if shape == "snake":

        result = result["hookSpecificOutput"]

        assert result["hookEventName"] == "PreToolUse"

    assert result["permissionDecision"] == "deny"

    assert result["permissionDecisionReason"] == "Policy refused."

    with pytest.raises(ValueError):

        transport.render_pre_tool_use(call, denial_reason="")



@pytest.mark.parametrize("event", ["PreToolUse", "postToolUse", "", None])
def test_wire_shape_does_not_select_registration_contract(event):
    payload = {"cwd": "/fixture", "tool_name": "Bash", "tool_input": {}, "hook_event_name": "PreToolUse"}
    with pytest.raises(ValueError, match="^COPILOT-HOOK-REGISTRATION$"):
        transport.read_pre_tool_use(payload, registration_event=event)


def test_dedicated_registration_has_one_shared_event_and_no_continuation():
    registration = transport.render_registration("python fixture.py")
    assert registration == {"version": 1, "hooks": {"preToolUse": [{"type": "command", "command": "python fixture.py"}]}}
    payload = {"cwd": "/fixture", "toolName": "unknown", "toolArgs": {}}
    call = transport.read_pre_tool_use(payload, registration_event=next(iter(registration["hooks"])))
    assert transport.render_pre_tool_use(call) == {}
    registration["hooks"]["preToolUse"].clear()
    assert len(transport.render_registration("python fixture.py")["hooks"]["preToolUse"]) == 1


@pytest.mark.parametrize("command", [None, "", "   ", "python\x00fixture", {}])
def test_registration_rejects_invalid_command_without_echo(command):
    with pytest.raises(ValueError, match="^COPILOT-HOOK-REGISTRATION$"):
        transport.render_registration(command)


@pytest.mark.parametrize("scope,root", [("global", ".copilot"), ("project", ".github")])
def test_dedicated_registration_uses_exact_file_ownership(monkeypatch, scope, root):
    import hashlib
    import json
    from _module_loading_support import load_module
    owner = load_module(PATH.parent / "ownership.py", "copilot_file_receipt")
    client = {"roots": (".copilot", ".github"),
              "scope_roots": {"global": (".copilot",), "project": (".github",)},
              "documents": {"global": {}, "project": {}}}
    monkeypatch.setattr(owner, "get_client", lambda _: client)
    raw = json.dumps(transport.render_registration("python fixture.py"), sort_keys=True).encode()
    digest = hashlib.sha256(raw).hexdigest()
    path = root + "/hooks/orche.json"
    receipt = owner.decode_record(owner.encode_record({path: digest}, "fixture-host", scope, configs={}), "fixture-host", scope)
    assert receipt["configs"] == {}
    assert owner.plan_file_removal(receipt, {path: digest, root + "/hooks/user.json": digest})["remove"] == (path,)
    assert owner.plan_file_removal(receipt, {path: "b" * 64})["preserve"] == (path,)
    assert owner.plan_file_removal(receipt, {})["absent"] == (path,)


def test_dedicated_registration_command_runs_literal_unicode_path(tmp_path):
    import json
    import os
    import shlex
    import subprocess
    from _module_loading_support import load_module

    directory = tmp_path / "\u4e2d\u6587 O'Brien [\u8d44\u6599] (x),@={}"
    directory.mkdir()
    probe = directory / "probe.py"
    probe.write_text("import json,sys\nfrom pathlib import Path\nprint(json.dumps({'script':str(Path(__file__).resolve()),'args':sys.argv[1:]}))\n", encoding="utf-8")
    tokens = [sys.executable, "-I", "-B", str(probe), "fixture"]
    if os.name == "nt":
        health = load_module(PATH.parents[1] / "check-hook-health.py", "copilot_native_command_health")
        command = health.serialize_windows_hook_command(tokens)
        shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        if not shell.is_file():
            pytest.skip("Windows PowerShell unavailable")
        launch = [str(shell), "-NoProfile", "-NonInteractive", "-Command",
                  json.loads(json.dumps(transport.render_registration(command)))["hooks"]["preToolUse"][0]["command"]]
    else:
        command = shlex.join(tokens)
        shell = Path("/bin/bash")
        if not shell.is_file():
            pytest.skip("Bash unavailable")
        launch = [str(shell), "--noprofile", "--norc", "-c",
                  json.loads(json.dumps(transport.render_registration(command)))["hooks"]["preToolUse"][0]["command"]]
    env = {k: v for k, v in os.environ.items() if k not in {"BASH_ENV", "ENV"}}
    result = subprocess.run(launch, cwd=directory, env=env, capture_output=True,
                            text=True, encoding="utf-8", timeout=20, check=True,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    received = json.loads(result.stdout)
    assert Path(received["script"]) == probe.resolve()
    assert received["args"] == ["fixture"]
    assert not list(directory.rglob("*.pyc"))


def test_camel_json_string_arguments_match_native_sdk_carrier():
    # Native SDK 1.0.73 pre-tool capture; identity/cwd/time are synthetic here.
    payload = {'sessionId': 'fixture-session', 'timestamp': 0, 'cwd': '/fixture', 'toolName': 'create', 'toolArgs': '{"path":"fixture-\u4e2d\u6587.txt","file_text":"fixture"}'}
    original = payload["toolArgs"]
    call = transport.read_pre_tool_use(payload, registration_event="preToolUse")
    assert call.format == "camel" and call.tool_name == "create"
    assert call.arguments == {"path": "fixture-\u4e2d\u6587.txt", "file_text": "fixture"}
    assert payload["toolArgs"] == original
    assert transport.render_pre_tool_use(call) == {}


@pytest.mark.parametrize("encoded", ["", " ", "[]", "null", "true", "1", '"nested string"',
    "{invalid", '{}{}', '{"path":"first","path":"second"}',
    '{"nested":{"path":"first","path":"second"}}', '{"value":NaN}',
    '{"value":Infinity}', '{"value":-Infinity}',
    '{"value":1e309}', '{"nested":[-1e999]}', '{"value":1.7976931348623159e308}'])
def test_camel_json_string_rejects_nonobjects_and_ambiguous_json(encoded):
    payload = {"cwd": "/fixture", "toolName": "create", "toolArgs": encoded}
    with pytest.raises(ValueError, match="^COPILOT-HOOK-INPUT$"):
        transport.read_pre_tool_use(payload, registration_event="preToolUse")


def test_snake_json_string_is_not_inferred_as_a_different_runtime_contract():
    payload = {"cwd": "/fixture", "hook_event_name": "PreToolUse", "tool_name": "create_file", "tool_input": '{}'}
    with pytest.raises(ValueError, match="^COPILOT-HOOK-INPUT$"):
        transport.read_pre_tool_use(payload, registration_event="preToolUse")


def test_native_custom_patch_uses_existing_strict_path_acquisition():
    from _module_loading_support import load_module
    common = load_module(PATH.parents[1] / "universal-hooks/scripts/hook_common.py", "copilot_patch_common")
    payload = {'sessionId': 'fixture-session', 'timestamp': 0, 'cwd': '/fixture', 'toolName': 'apply_patch', 'toolArgs': '*** Begin Patch\n*** Update File: fixture-\u4e2d\u6587.txt\n@@\n-old\n+new\n*** End Patch\n'}
    raw = payload["toolArgs"]
    call = transport.read_pre_tool_use(payload, registration_event="preToolUse")
    assert call.tool_name == "apply_patch" and call.arguments == {"input": raw}
    assert payload["toolArgs"] == raw
    acquired = common.acquire_tool_input(call.tool_name, call.arguments)
    assert acquired.raw_name == "apply_patch" and acquired.operation == "apply_patch"
    assert acquired.resolved and acquired.targets == ("fixture-\u4e2d\u6587.txt",)
    assert transport.render_pre_tool_use(call) == {}


@pytest.mark.parametrize("text", ['{"input":"not a native custom patch"}', "echo fixture", "*** Begin Patch\nmissing frame"])
def test_native_custom_patch_frame_validation_stays_with_existing_owner(text):
    from _module_loading_support import load_module
    common = load_module(PATH.parents[1] / "universal-hooks/scripts/hook_common.py", "copilot_bad_patch_common")
    call = transport.read_pre_tool_use({"cwd":"/fixture","toolName":"apply_patch","toolArgs":text},registration_event="preToolUse")
    assert call.arguments == {"input": text}
    acquired = common.acquire_tool_input(call.tool_name, call.arguments)
    assert not acquired.resolved and acquired.targets == ()


@pytest.mark.parametrize("name", ["unknown_custom", "functions.apply_patch", "Apply_Patch", "create"])
def test_native_custom_patch_is_not_a_fallback_for_unknown_string_tools(name):
    raw = "*** Begin Patch\n*** Delete File: fixture.txt\n*** End Patch\n"
    with pytest.raises(ValueError, match="^COPILOT-HOOK-INPUT$"):
        transport.read_pre_tool_use({"cwd":"/fixture","toolName":name,"toolArgs":raw},registration_event="preToolUse")


@pytest.mark.parametrize("shape", ["camel", "snake"])
@pytest.mark.parametrize("denial", [None, "Policy refused."])
def test_advisory_preserves_neutral_or_deny_without_permission_upgrade(shape, denial):
    call = transport.PreToolCall(shape, "/fixture", "create_file", {"filePath":"file.txt"})
    context = "Audit: \u4e2d\u6587 paths remain portable."
    result = transport.render_pre_tool_use(call, denial_reason=denial, additional_context=context)
    output = result if shape == "camel" else result["hookSpecificOutput"]
    assert output["additionalContext"] == context
    assert "updatedInput" not in output
    if denial is None:
        assert "permissionDecision" not in output and "permissionDecisionReason" not in output
    else:
        assert output["permissionDecision"] == "deny" and output["permissionDecisionReason"] == denial
    if shape == "snake":
        assert output["hookEventName"] == "PreToolUse"
    assert call.arguments == {"filePath":"file.txt"}


@pytest.mark.parametrize("context", ["", "  ", "bad\0context", [], {}, 3, True])
def test_invalid_advisory_refuses_without_echoing_input(context):
    call = transport.PreToolCall("camel", "/fixture", "create", {})
    with pytest.raises(ValueError, match="^COPILOT-HOOK-OUTPUT$"):
        transport.render_pre_tool_use(call, additional_context=context)


@pytest.mark.parametrize("number", ["1e308", "-1e308", "0.0", "1.7976931348623157e308"])
def test_camel_json_string_preserves_finite_numeric_arguments(number):
    import math
    payload = {"cwd": "/fixture", "toolName": "create", "toolArgs": '{"value":' + number + '}'}
    call = transport.read_pre_tool_use(payload, registration_event="preToolUse")
    assert math.isfinite(call.arguments["value"])
    assert call.arguments["value"] == float(number)
    assert payload["toolArgs"] == '{"value":' + number + '}'


@pytest.mark.parametrize("shape", ["camel", "snake"])
@pytest.mark.parametrize("number", [float("inf"), float("-inf"), float("nan")])
def test_object_carriers_reject_nested_nonfinite_numbers(shape, number):
    args = {"nested": [{"value": number}]}
    payload = {"cwd": "/fixture", "toolName": "create", "toolArgs": args} if shape == "camel" else {
        "cwd": "/fixture", "hook_event_name": "PreToolUse", "tool_name": "create", "tool_input": args}
    with pytest.raises(ValueError, match="^COPILOT-HOOK-INPUT$"):
        transport.read_pre_tool_use(payload, registration_event="preToolUse")


@pytest.mark.parametrize("shape", ["camel", "snake"])
def test_object_carriers_preserve_finite_numbers_and_identity(shape):
    args = {"nested": [1.7976931348623157e308, -1e308, 0.0]}
    payload = {"cwd": "/fixture", "toolName": "create", "toolArgs": args} if shape == "camel" else {
        "cwd": "/fixture", "hook_event_name": "PreToolUse", "tool_name": "create", "tool_input": args}
    assert transport.read_pre_tool_use(payload, registration_event="preToolUse").arguments is args

def test_object_finite_scan_handles_deep_and_shared_containers_without_recursion():
    nested = {"value": 1.25}
    for _ in range(4000):
        nested = [nested]
    args = {"first": nested, "second": nested}
    payload = {"cwd": "/fixture", "toolName": "create", "toolArgs": args}
    assert transport.read_pre_tool_use(payload, registration_event="preToolUse").arguments is args


def test_object_finite_scan_terminates_on_a_cyclic_python_object():
    args = {}
    args["self"] = args
    payload = {"cwd": "/fixture", "toolName": "create", "toolArgs": args}
    assert transport.read_pre_tool_use(payload, registration_event="preToolUse").arguments is args

@pytest.mark.parametrize("shape", ["camel", "snake"])
def test_outer_json_numeric_overflow_is_rejected_for_object_carriers(shape):
    import json
    raw = ('{"cwd":"/fixture","toolName":"create","toolArgs":{"nested":[1e309]}}'
           if shape == "camel" else
           '{"cwd":"/fixture","hook_event_name":"PreToolUse","tool_name":"create","tool_input":{"nested":[1e309]}}')
    with pytest.raises(ValueError, match="^COPILOT-HOOK-INPUT$"):
        transport.read_pre_tool_use(json.loads(raw), registration_event="preToolUse")