"""Official run_command envelope through the actual shared command audit."""
from pathlib import Path
import runpy
import pytest
from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = load_module(ROOT / "adapters/antigravity/runtime/command_advisory.py", "agy_command_audit_test")
POLICY = runpy.run_path(str(ROOT / "scripts/universal-hooks/hooks/check-no-trash-in-repo.py"))
OWNER = load_module(ROOT / "scripts/installation/ownership.py", "agy_command_ownership_test")


def evaluate(command, cwd, **extra):
    return ADAPTER.evaluate({"toolCall": {"name": "run_command", "args": {"CommandLine": command, "Cwd": cwd}}, **extra}, POLICY["command_advisory"])


@pytest.mark.parametrize("git_kind", ["file", "directory"])
@pytest.mark.parametrize("command", ["echo evidence > build.log", "gcc probe.c", "git worktree add sibling", "echo x > r:Tempxbuild.log"])
def test_shared_risk_warns_without_approval(tmp_path, git_kind, command):
    marker = tmp_path / ".git"
    marker.mkdir() if git_kind == "directory" else marker.touch()
    result = evaluate(command, str(tmp_path))
    assert result["decision"] == "allow"
    assert "stray-artifact AUDIT" in result["reason"]
    assert set(result) == {"decision", "reason"}
    assert not (tmp_path / "build.log").exists()


@pytest.mark.parametrize("command", ["echo x > .scratch/build.log", "cd .scratch && gcc probe.c", "gcc --version", "gcc probe.c -o .scratch/probe.o", "git worktree list", "git worktree add sibling # orchestrarium:requested-isolation-worktree"])
def test_existing_exclusions_unchanged(tmp_path, command):
    (tmp_path / ".git").mkdir()
    assert evaluate(command, str(tmp_path)) == {"decision": "allow"}


@pytest.mark.parametrize("cwd", [None, "relative", "", 42])
def test_missing_actual_cwd_never_uses_workspace_or_hook_cwd(tmp_path, monkeypatch, cwd):
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    assert evaluate("echo x > build.log", cwd, workspacePaths=[str(tmp_path)]) == {"decision": "allow"}
    assert "reason" in evaluate("git worktree add sibling", cwd)


def test_actual_subdirectory_not_workspace_root(tmp_path):
    (tmp_path / ".git").mkdir()
    sub = tmp_path / "sub"
    sub.mkdir()
    assert evaluate("echo x > build.log", str(sub), workspacePaths=[str(tmp_path)]) == {"decision": "allow"}


@pytest.mark.parametrize("payload", [None, {}, {"toolCall": []}, {"toolCall": {"name": "manage_task", "args": {"CommandLine": "git worktree add x"}}}, {"toolCall": {"name": "run_command", "args": {"CommandLine": []}}}])
def test_unknown_or_malformed_has_no_invented_command(payload):
    assert ADAPTER.evaluate(payload, POLICY["command_advisory"]) == {"decision": "allow"}


def test_owned_command_matcher_is_exact():
    spec = {"kind": "json-projection", "members": {"orchestrarium-stray-artifact": {"PreToolUse": [{"matcher": "^run_command$", "hooks": [{"type": "command", "command": "python command_advisory.py"}]}]}}, "entries": []}
    OWNER.encode_record({}, "antigravity", "project", configs={".agents/hooks.json": spec})
    spec["members"]["orchestrarium-stray-artifact"]["PreToolUse"][0]["matcher"] = "*"
    with pytest.raises(ValueError, match="matcher"):
        OWNER.encode_record({}, "antigravity", "project", configs={".agents/hooks.json": spec})
