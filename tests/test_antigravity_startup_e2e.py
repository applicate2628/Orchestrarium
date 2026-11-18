"""Actual isolated startup installation and hook process; no Antigravity/model launch."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("scope", ["project", "global"])
def test_startup_install_update_hook_and_uninstall_preserve_neighbors(tmp_path, scope):
    project=tmp_path/"project";project.mkdir()
    home=tmp_path/"isolated-home";home.mkdir()
    anchor=project if scope=="project" else home
    native=anchor/(".agents" if scope=="project" else ".gemini/config");native.mkdir(parents=True)
    codex_skill=anchor/".agents/skills/codex-owned/SKILL.md"
    codex_skill.parent.mkdir(parents=True);codex_skill.write_bytes(b"Existing Codex skill stays unchanged.\n")
    codex_hooks=anchor/".codex/hooks.json";codex_hooks.parent.mkdir()
    codex_hooks.write_bytes(b'{"hooks":{},"user":"Codex-owned"}\n')
    codex_before={p:p.read_bytes() for p in (codex_skill,codex_hooks)}
    foreign_hook={"SessionStart":[{"type":"command","command":"echo team"}]}
    hooks=native/"hooks.json";hooks.write_text(json.dumps({"team":foreign_hook}))
    foreign_entries={"skills.json":{"path":"team-skills"},"rules.json":{"path":"team-rules"}}
    for name,entry in foreign_entries.items():
        (native/name).write_text(json.dumps({"entries":[entry]}))
    environment=dict(os.environ);environment.pop("ORCHESTRARIUM_NO_HYPOTHESIS_HOOK",None)
    environment.update(HOME=str(home), USERPROFILE=str(home), HOMEDRIVE=home.drive, HOMEPATH=str(home)[len(home.drive):])
    assert Path(environment["HOME"])==Path(environment["USERPROFILE"])==home
    assert home.is_relative_to(tmp_path) and native.is_relative_to(tmp_path)
    selected_args=["--global"] if scope=="global" else ["--target",str(project),"--allow-unsafe-target"]
    def run(*args):
        result=subprocess.run([sys.executable,str(ROOT/"scripts/install-client.py"),"--client","antigravity",
            *selected_args,*args],cwd=ROOT,env=environment,
            capture_output=True,text=True,encoding="utf-8")
        assert result.returncode==0,result.stdout+result.stderr
        return result
    before={str(p.relative_to(anchor)):p.read_bytes() for p in anchor.rglob("*") if p.is_file()}
    run("--dry-run")
    assert before=={str(p.relative_to(anchor)):p.read_bytes() for p in anchor.rglob("*") if p.is_file()}
    run()
    managed=native/"orchestrarium-antigravity"
    script=managed/"runtime/session_start.py"
    assert script.is_file() and (managed/"skills/orchestrarium-lead/SKILL.md").is_file()
    assert "trigger: always_on" in (managed/"rules/orchestrarium.md").read_text()
    data=json.loads(hooks.read_text());assert data["team"]==foreign_hook
    assert "orchestrarium-session-start" in data
    for name,entry in foreign_entries.items():
        entries=json.loads((native/name).read_text())["entries"]
        assert entry in entries and len(entries)==2
    payload={"conversationId":"fixture-session","workspacePaths":[str(project)],
             "transcriptPath":str(tmp_path/"missing-unread-transcript.jsonl")}
    command=data["orchestrarium-session-start"]["SessionStart"][0]["command"]
    output=subprocess.run(command,shell=True,input=json.dumps(payload),cwd=project,
        env=environment,capture_output=True,text=True,encoding="utf-8")
    assert output.returncode==0,output.stderr
    injected=json.loads(output.stdout)["injectSteps"]
    expected="\n\n".join((managed/name).read_text(encoding="utf-8") for name in ("AGENTS.shared.md","AGENTS.antigravity.md"))
    assert injected==[{"systemMessage":{"systemMessage":expected}}]
    assert not Path(payload["transcriptPath"]).exists()
    # Repeat/update must retain additions made after installation.
    data["team-extra"]=foreign_hook;hooks.write_text(json.dumps(data))
    custom=managed/"user-note.txt";custom.write_bytes(b"Unowned customization")
    run()
    after=json.loads(hooks.read_text());assert after["team"]==after["team-extra"]==foreign_hook
    assert codex_before=={p:p.read_bytes() for p in codex_before}
    run("--uninstall","--apply")
    after=json.loads(hooks.read_text());assert after=={"team":foreign_hook,"team-extra":foreign_hook}
    for name,entry in foreign_entries.items():assert json.loads((native/name).read_text())["entries"]==[entry]
    assert not script.exists() and not (managed/"skills/orchestrarium-lead/SKILL.md").exists()
    assert custom.read_bytes()==b"Unowned customization"
    assert codex_before=={p:p.read_bytes() for p in codex_before}
