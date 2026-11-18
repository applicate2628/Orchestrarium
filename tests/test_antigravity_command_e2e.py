"""Installed Bash-text audit only: commands under review are never executed."""
import json
import os
from pathlib import Path
import subprocess
import sys

from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]
OWNER = load_module(ROOT / "scripts/installation/ownership.py", "agy_command_cross_owner")
MEMBER = "orchestrarium-stray-artifact"


def test_installed_command_audit_upgrade_and_preservation(tmp_path):
    project = tmp_path / "project"
    native = project / ".agents"
    native.mkdir(parents=True)
    (project / ".git").mkdir()
    subdir = project / "subdir"
    subdir.mkdir()
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / ".git").write_text("gitdir: synthetic-not-opened")
    home = tmp_path / "home"
    home.mkdir()
    env = dict(os.environ)
    env.pop("ORCHESTRARIUM_NO_HYPOTHESIS_HOOK", None)
    env.update(HOME=str(home), USERPROFILE=str(home))
    hooks = native / "hooks.json"
    foreign = {"team": {"PreToolUse": [{"type": "command", "command": "echo team"}]}}
    hooks.write_text(json.dumps(foreign))
    codex = native / "skills/codex-owned/SKILL.md"
    codex.parent.mkdir(parents=True)
    codex.write_bytes(b"Existing Codex skill")

    def install(*args):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/install-client.py"),
            "--client", "antigravity", "--target", str(project), "--allow-unsafe-target", *args],
            cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
        assert result.returncode == 0, result.stdout + result.stderr

    install()
    managed = native / "orchestrarium-antigravity"
    receipt = managed / OWNER.RECEIPT_NAME
    record = OWNER.decode_record(receipt.read_bytes(), "antigravity", "project")
    # Explicit compatibility fixture: prior startup+write-audit shape reconstructed
    # with the real codec. This is not execution of a historical installer.
    previous = json.loads(hooks.read_text())
    previous.pop(MEMBER)
    hooks.write_text(json.dumps(previous))
    record["configs"][".agents/hooks.json"]["members"].pop(MEMBER)
    retained = tmp_path / "retained-new-payloads"
    for relative in ("runtime/command_advisory.py", "runtime/shared/hooks/check-no-trash-in-repo.py",
                     "runtime/shared/scripts/git_push_gate_preflight.py"):
        source = managed / relative
        destination = retained / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.rename(destination)
        record["files"].pop(source.relative_to(project).as_posix())
    assert len(record["files"]) == 8
    assert set(record["configs"][".agents/hooks.json"]["members"]) == {
        "orchestrarium-session-start", "orchestrarium-machine-local-path"}
    receipt.write_bytes(OWNER.serialize_record(record, "antigravity", "project"))
    install()
    upgraded = json.loads(hooks.read_text())
    assert all(upgraded[key] == value for key, value in previous.items())
    spec = upgraded[MEMBER]["PreToolUse"][0]
    assert spec["matcher"] == "^run_command$"
    registered_command = spec["hooks"][0]["command"]
    before = {str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()}

    def call(command, cwd, *, name="run_command", raw=None):
        payload = {"toolCall": {"name": name, "args": {"CommandLine": command, "Cwd": cwd}},
                   "workspacePaths": [str(project)], "transcriptPath": str(tmp_path / "absent-transcript")}
        # Only the registered Python hook is executed. command remains JSON data.
        result = subprocess.run(registered_command, shell=True,
            input=json.dumps(payload) if raw is None else raw, cwd=project, env=env,
            capture_output=True, text=True, encoding="utf-8")
        assert result.returncode == 0 and result.stderr == "", result.stderr
        output = json.loads(result.stdout)
        assert output["decision"] == "allow" and set(output) <= {"decision", "reason"}
        return output

    cases = [
        ("make > build.log", str(project), True),
        ("make > build.log", str(worktree), True),
        ("make > build.log", str(subdir), False),
        ("make > build.log", None, False),
        ("make > build.log", ".", False),
        ("make > .scratch/build.log", str(project), False),
        ("cd .scratch && make > build.log", str(project), False),
        ("gcc -o .scratch/probe probe.c", str(project), False),
        ("git worktree add ../candidate", str(subdir), True),
        ("git worktree add ../candidate # orchestrarium:requested-isolation-worktree", str(project), False),
        ("git worktree add ../candidate # orchestrarium:requested-isolation-worktre", str(project), True),
        ("git worktree list", str(project), False),
    ]
    for command, cwd, warning in cases:
        output = call(command, cwd)
        assert ("reason" in output) is warning, (command, output)
        if warning:
            assert "stray-artifact AUDIT" in output["reason"]
    assert call("make > build.log", str(project), name="unknown") == {"decision": "allow"}
    assert call([], str(project)) == {"decision": "allow"}
    assert call("ignored", str(project), raw="bad JSON") == {"decision": "allow"}
    assert before == {str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    assert not (tmp_path / "candidate").exists() and not (tmp_path / "absent-transcript").exists()
    install("--uninstall", "--apply")
    assert json.loads(hooks.read_text()) == foreign
    assert codex.read_bytes() == b"Existing Codex skill"
    assert not (managed / "runtime/command_advisory.py").exists()
