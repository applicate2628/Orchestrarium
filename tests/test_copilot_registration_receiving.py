"""Real isolated registration files and shell receiving, never a Copilot host."""
from pathlib import Path
import json
import os
import subprocess
import sys
import pytest
from _module_loading_support import load_module
ROOT=Path(__file__).resolve().parents[1]
WIRE=load_module(ROOT/'scripts/installation/copilot_transport.py','registration_wire')
HEALTH=load_module(ROOT/'scripts/check-hook-health.py','registration_health')

@pytest.mark.parametrize('shell,key',[(None,'command'),('powershell','powershell'),('bash','bash')])
def test_one_explicit_command_dialect(shell,key):
    doc=WIRE.render_registration('literal command',shell=shell)
    assert doc=={'version':1,'hooks':{'preToolUse':[{'type':'command',key:'literal command'}]}}

@pytest.mark.parametrize('shell',['cmd','exec','PowerShell',0,False,{},[]])
def test_unknown_dialect_refuses(shell):
    with pytest.raises(ValueError,match='COPILOT-HOOK-REGISTRATION'):
        WIRE.render_registration('literal command',shell=shell)

@pytest.mark.skipif(os.name!='nt',reason='Windows PowerShell receiving')
@pytest.mark.parametrize('status',[0,2,7])
def test_actual_workspace_json_stdin_stdout_and_exit(tmp_path,status):
    directory=tmp_path/"project space O'Brien [test]"
    hooks=directory/'.github/hooks';hooks.mkdir(parents=True)
    foreign=hooks/'user.json';foreign.write_bytes(b'{"version":1,"hooks":{}}\r\n')
    probe=directory/'probe.py'
    probe.write_text("import json,sys\np=json.load(sys.stdin)\nassert p['toolName']=='fixture_tool'\nprint(json.dumps({'permissionDecision':'deny','permissionDecisionReason':'fixture only'}))\nraise SystemExit(int(sys.argv[1]))\n")
    command=HEALTH.serialize_powershell_hook_command([sys.executable,'-I','-B',str(probe),str(status)])
    config=hooks/'orchestrarium.json'
    config.write_text(json.dumps(WIRE.render_registration(command,shell='powershell')),encoding='utf-8')
    stored=json.loads(config.read_text())
    handler=stored['hooks']['preToolUse'][0]
    assert set(handler)=={'type','powershell'}
    ps=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
    proc=subprocess.run([str(ps),'-NoProfile','-NonInteractive','-Command',handler['powershell']],input=json.dumps({'cwd':str(directory),'toolName':'fixture_tool','toolArgs':{}}),text=True,capture_output=True,cwd=directory,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
    assert proc.returncode==status,proc.stderr
    assert json.loads(proc.stdout)=={'permissionDecision':'deny','permissionDecisionReason':'fixture only'}
    assert foreign.read_bytes()==b'{"version":1,"hooks":{}}\r\n'
    assert not list(directory.rglob('*.pyc'))
