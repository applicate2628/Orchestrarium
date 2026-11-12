"""Reuse the actual canonical command advisory without executing input commands."""
import json
from pathlib import Path
import subprocess
import sys
from unittest import mock
import pytest
from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "scripts/copilot-pre-tool-use.py"
ADAPTER = load_module(ENTRY, "copilot_shared_advisory_adapter")

@pytest.mark.parametrize("name,args,expected", [
    ("bash", {"command":"git worktree add should-not-exist"}, True),
    ("powershell", {"command":"git worktree add should-not-exist"}, True),
    ("exec_command", {"cmd":"git worktree add should-not-exist"}, True),
    ("shell_command", {"command":"git worktree list"}, False),
    ("bash", {"command":"git worktree add should-not-exist # orchestrarium:requested-isolation-worktree"}, False),
    ("bash", {"command":"gcc -c main.c"}, True),
    ("bash", {"command":"gcc -c main.c -o .scratch/main.o"}, False),
    ("bash", {"command":"echo x > build.log"}, True),
    ("bash", {"command":"echo x > .scratch/build.log"}, False),
    ("bash", {"command":"echo x", "cmd":"git worktree add should-not-exist"}, False),
    ("run_in_terminal", {"command":"git worktree add should-not-exist"}, False),
])
@pytest.mark.parametrize("shape", ["camel", "snake"])
def test_actual_canonical_command_advisory(tmp_path,name,args,expected,shape):
    (tmp_path / ".git").mkdir()
    payload = ({"cwd":str(tmp_path),"toolName":name,"toolArgs":json.dumps(args)} if shape=="camel"
               else {"cwd":str(tmp_path),"tool_name":name,"tool_input":args,"hook_event_name":"PreToolUse"})
    result = subprocess.run([sys.executable,"-I","-B",str(ENTRY)],
                            input=json.dumps(payload).encode(),cwd=tmp_path,
                            capture_output=True,timeout=20)
    assert result.returncode == 0,result.stderr
    output = json.loads(result.stdout)
    if expected:
        body = output if shape=="camel" else output["hookSpecificOutput"]
        assert "[stray-artifact AUDIT]" in body["additionalContext"]
        assert "permissionDecision" not in body
    else:
        assert output == {}
    assert sorted(p.name for p in tmp_path.iterdir()) == [".git"]

def test_exact_raw_carrier_forwarding_and_fixed_owner():
    args={"command":"git worktree add example","description":"retained metadata"}
    call=ADAPTER.wire.PreToolCall("camel","fixture-cwd","tools.bash",args)
    response={"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"canonical advisory"}}
    with mock.patch.object(ADAPTER.subprocess,"run",return_value=subprocess.CompletedProcess([],0,json.dumps(response).encode(),b"")) as run:
        assert ADAPTER.command_advisory(call)=="canonical advisory"
    argv=run.call_args.args[0]
    assert argv==[sys.executable,"-I","-B",str(ROOT/"scripts/universal-hooks/hooks/check-no-trash-in-repo.py")]
    envelope=json.loads(run.call_args.kwargs["input"])
    assert envelope=={"hook_event_name":"PreToolUse","cwd":"fixture-cwd","tool_name":"tools.bash","tool_input":args}
    assert "shell" not in run.call_args.kwargs

@pytest.mark.parametrize("output", [
    b'{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}',
    b'{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny"}}',
    b'{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"wrong"}}',
    b'[]',b'[{}]',b'{"hookSpecificOutput":{},"hookSpecificOutput":{}}',b'garbage',
])
def test_unexpected_output_never_becomes_permission(output,capsys):
    call=ADAPTER.wire.PreToolCall("camel","fixture-cwd","bash",{"command":"echo x"})
    with mock.patch.object(ADAPTER.subprocess,"run",return_value=subprocess.CompletedProcess([],0,output,b"")):
        assert ADAPTER.command_advisory(call) is None
    assert "unavailable" in capsys.readouterr().err

@pytest.mark.parametrize("error", [OSError("synthetic"), subprocess.TimeoutExpired("fixed-owner",10)])
def test_advisory_failure_keeps_canonical_nonblocking_posture(error,capsys):
    call=ADAPTER.wire.PreToolCall("camel","fixture-cwd","bash",{"command":"echo x"})
    with mock.patch.object(ADAPTER.subprocess,"run",side_effect=error):
        assert ADAPTER.command_advisory(call) is None
    assert "unavailable" in capsys.readouterr().err

@pytest.mark.parametrize("error", [ValueError("synthetic"), OSError("synthetic")])
def test_acquisition_failure_is_neutral(error, capsys):
    call=ADAPTER.wire.PreToolCall("camel","fixture-cwd","bash",{"command":"echo x"})
    with mock.patch.object(ADAPTER.wire,"acquire_pre_tool_input",side_effect=error):
        assert ADAPTER.command_advisory(call) is None
    assert "unavailable" in capsys.readouterr().err

def test_missing_shared_dependency_is_neutral(capsys):
    call=ADAPTER.wire.PreToolCall("camel","fixture-cwd","bash",{"command":"echo x"})
    with mock.patch.dict(sys.modules, {"hook_common": None}):
        assert ADAPTER.command_advisory(call) is None
    assert "unavailable" in capsys.readouterr().err
