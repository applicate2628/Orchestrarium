"""Installed native advisory/legacy upgrade; no model or native agent launch."""
import json
import os
from pathlib import Path
import subprocess
import sys

from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]
OWNER = load_module(ROOT / "scripts/installation/ownership.py", "agy_cross_ownership")
MEMBER = "orchestrarium-machine-local-path"


def test_installed_pretool_audit_upgrade_recovery_and_preservation(tmp_path):
    project = tmp_path / "project"
    native = project / ".agents"
    native.mkdir(parents=True)
    home = tmp_path / "home"
    home.mkdir()
    env = dict(os.environ)
    env.pop("ORCHESTRARIUM_NO_HYPOTHESIS_HOOK", None)
    env.update(HOME=str(home), USERPROFILE=str(home))
    foreign = {"team": {"PreToolUse": [{"type": "command", "command": "echo team"}]}}
    hooks = native / "hooks.json"
    hooks.write_text(json.dumps(foreign))
    codex = native / "skills/codex-owned/SKILL.md"
    codex.parent.mkdir(parents=True)
    codex.write_bytes(b"Unrelated Codex skill")

    def install(*args):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/install-client.py"),
            "--client", "antigravity", "--target", str(project), "--allow-unsafe-target", *args],
            cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
        assert result.returncode == 0, result.stdout + result.stderr

    install()
    managed = native / "orchestrarium-antigravity"
    receipt = managed / OWNER.RECEIPT_NAME
    record = OWNER.decode_record(receipt.read_bytes(), "antigravity", "project")
    # Construct an explicit historical startup-only fixture from actual installed
    # bytes and the real ownership codec, not a fabricated execution receipt.
    legacy = json.loads(hooks.read_text())
    legacy.pop(MEMBER)
    hooks.write_text(json.dumps(legacy))
    record["configs"][".agents/hooks.json"]["members"].pop(MEMBER)
    retained = tmp_path / "retained-new-payloads"
    for relative in ("runtime/pre_tool_use.py", "runtime/shared/hooks/check-machine-local-path.py",
                     "runtime/shared/scripts/hook_common.py"):
        source = managed / relative
        destination = retained / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.rename(destination)
        record["files"].pop(source.relative_to(project).as_posix())
    assert set(record["files"]) == {
        ".agents/orchestrarium-antigravity/" + name for name in (
            "runtime/session_start.py", "skills/orchestrarium-lead/SKILL.md",
            "rules/orchestrarium.md", "AGENTS.antigravity.md", "AGENTS.shared.md")}
    assert set(record["configs"]) == {".agents/hooks.json", ".agents/skills.json", ".agents/rules.json"}
    assert set(record["configs"][".agents/hooks.json"]["members"]) == {"orchestrarium-session-start"}
    receipt.write_bytes(OWNER.serialize_record(record, "antigravity", "project"))
    startup = legacy["orchestrarium-session-start"]
    install()
    upgraded = json.loads(hooks.read_text())
    assert upgraded["orchestrarium-session-start"] == startup
    assert upgraded["team"] == foreign["team"]
    spec = upgraded[MEMBER]["PreToolUse"][0]
    assert spec["matcher"] == "^(write_to_file|replace_file_content)$"
    command = spec["hooks"][0]["command"]
    leak = str(Path("C:/Users") / "synthetic-operator" / "note.txt")
    unchanged = {str(p.relative_to(project)): p.read_bytes()
                 for p in project.rglob("*") if p.is_file()}

    def call(payload=None, *, raw=None):
        result = subprocess.run(command, shell=True, input=raw if raw is not None else json.dumps(payload),
            cwd=project, env=env, capture_output=True, text=True, encoding="utf-8")
        assert result.returncode == 0 and result.stderr == "", result.stderr
        return json.loads(result.stdout)

    def envelope(name, args):
        return {"toolCall": {"name": name, "args": args},
                "workspacePaths": [str(project)], "transcriptPath": str(tmp_path / "absent-transcript")}

    for name, field in (("write_to_file", "CodeContent"), ("replace_file_content", "ReplacementContent")):
        clean = envelope(name, {"TargetFile": "README.md", field: "Portable content", "Description": leak})
        assert call(clean) == {"decision": "allow"}
        warning = call(envelope(name, {"TargetFile": "README.md", field: leak}))
        assert set(warning) == {"decision", "reason"}
        assert warning["decision"] == "allow" and "machine-local-path AUDIT" in warning["reason"]
        assert call(envelope(name, {"TargetFile": ".scratch/note.txt", field: leak})) == {"decision": "allow"}
    assert call(envelope("multi_replace_file_content", {"TargetFile": "README.md", "ReplacementChunks": [leak]})) == {"decision": "allow"}
    assert call(envelope("write_to_file", {"TargetFile": "README.md", "CodeContent": [leak]})) == {"decision": "allow"}
    assert call(raw="not JSON") == {"decision": "allow"}
    # Malformed input does not poison the next independent invocation.
    assert "reason" in call(envelope("write_to_file", {"TargetFile": "README.md", "CodeContent": leak}))
    assert unchanged == {str(p.relative_to(project)): p.read_bytes()
                         for p in project.rglob("*") if p.is_file()}
    assert not (tmp_path / "absent-transcript").exists()
    install("--uninstall", "--apply")
    assert json.loads(hooks.read_text()) == foreign
    assert codex.read_bytes() == b"Unrelated Codex skill"
    assert not (managed / "runtime/pre_tool_use.py").exists()
