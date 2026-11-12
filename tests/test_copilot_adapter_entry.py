"""Actual adapter stdin/out; no native host or model."""
from pathlib import Path
import json
import subprocess
import sys
import pytest
from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "scripts/copilot-pre-tool-use.py"
REG = load_module(ROOT / "scripts/installation/copilot_registration.py", "adapter_registration")

# Synthetic detector inputs only: these are never filesystem destinations and
# are unrelated to any user's workstation. Build the deliberate positive
# examples from named segments instead of embedding machine-local provenance.
SYNTHETIC_HOME = "/".join(("C:", "Users", "alice"))
SYNTHETIC_CONFIG = SYNTHETIC_HOME + "/config"
SYNTHETIC_DEV = "/".join(("D:", "dev", "private", "code"))
SYNTHETIC_POSIX = "/".join(("", "home", "alice", "work"))

def invoke(payload):
    return subprocess.run([sys.executable, "-I", "-B", str(ENTRY)], input=payload,
                          capture_output=True, timeout=20)

@pytest.mark.parametrize("name,args,hit", [
    ("create", {"path":"src/a.txt","content":SYNTHETIC_CONFIG}, True),
    ("create_file", {"filePath":"src/a.txt","content":SYNTHETIC_DEV}, True),
    ("replace_string_in_file", {"filePath":"a","newString":SYNTHETIC_POSIX}, True),
    ("create", {"path":".scratch/a","content":SYNTHETIC_CONFIG}, False),
    ("create", {"path":"a","content":"C:/Users/<you>/config"}, False),
    ("create", {"path":"a","content":"plain"}, False),
    ("unknown", {"command":SYNTHETIC_HOME}, False),
])
@pytest.mark.parametrize("shape", ["camel", "snake"])
def test_real_adapter(name,args,hit,shape):
    payload = ({"cwd":str(ROOT),"toolName":name,"toolArgs":json.dumps(args)} if shape=="camel"
               else {"cwd":str(ROOT),"tool_name":name,"tool_input":args,"hook_event_name":"PreToolUse"})
    result = invoke(json.dumps(payload).encode())
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    if hit:
        body = output if shape=="camel" else output["hookSpecificOutput"]
        assert "machine-local-path AUDIT" in body["additionalContext"]
        assert "permissionDecision" not in body
        assert b"alice" not in result.stdout
    else:
        assert output == {}

@pytest.mark.parametrize("payload", [
    b"{}", b'{"cwd":"x","toolName":"a","toolName":"b","toolArgs":{}}',
    b'{"cwd":"x","toolName":"a","toolArgs":{"x":NaN}}', b"["*20000,
    b"x"*(1024*1024+1), b"\xff",
])
def test_invalid_input(payload):
    result = invoke(payload)
    assert result.returncode == 2
    assert result.stdout == b""
    assert b"Traceback" not in result.stderr

def test_generator_missing_payload_and_absolute_refused(tmp_path):
    for path in (tmp_path, Path("../outside")):
        with pytest.raises(ValueError):
            REG.bundled_advisory(tmp_path, path)
    with pytest.raises(OSError):
        REG.bundled_advisory(tmp_path, Path("absent"))


@pytest.mark.parametrize("label", ["smart\u2019quote", "line\u2028break"])
def test_generator_shell_quote_boundaries(tmp_path,label):
    bundle=tmp_path/label
    for name in ("python/python.exe", "app/scripts/copilot-pre-tool-use.py",
                 "app/scripts/installation/copilot_transport.py",
                 "app/scripts/universal-hooks/hooks/check-machine-local-path.py",
                 "app/scripts/universal-hooks/scripts/hook_common.py"):
        path=bundle/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b"fixture")
    with pytest.raises(ValueError,match="COPILOT-BUNDLE-PATH"):
        REG.bundled_advisory(tmp_path,Path(label))


def test_generator_literal_relative_command(tmp_path):
    label = "bundle O'Brien [test]"
    for name in ("python/python.exe", "app/scripts/copilot-pre-tool-use.py",
                 "app/scripts/installation/copilot_transport.py",
                 "app/scripts/universal-hooks/hooks/check-machine-local-path.py",
                 "app/scripts/universal-hooks/scripts/hook_common.py"):
        path=tmp_path/label/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b"fixture")
    result = json.loads(REG.bundled_advisory(tmp_path,Path(label)))
    command = result["hooks"]["preToolUse"][0]["powershell"]
    assert "Set-Location -LiteralPath ([Environment]::CurrentDirectory) -ErrorAction Stop" in command
    assert "& './bundle O''Brien [test]/python/python.exe' '-I' '-B'" in command
    assert command.endswith("; exit $LASTEXITCODE")
    assert str(tmp_path) not in command
