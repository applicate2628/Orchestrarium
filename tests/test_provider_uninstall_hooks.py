from copy import deepcopy
from pathlib import Path
import json
import sys
import pytest
from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]
BACKEND = load_module(ROOT / "scripts/production_installer.py", "uninstall_hook_backend")
OP = load_module(ROOT / "scripts/installation/uninstall.py", "uninstall_hook_operation")
CODEC = load_module(ROOT / "scripts/installation/ownership.py", "uninstall_hook_codec")


def fixture(tmp_path, provider):
    script = tmp_path / (".claude/agents/hooks/check-bugfix-discipline.py" if provider == "claude"
                         else ".agents/skills/lead/scripts/check-bugfix-discipline.py")
    script.parent.mkdir(parents=True)
    script.write_text("pass\n")
    if provider == "claude":
        handler = {"type": "command", "command": sys.executable, "args": [str(script)]}
    else:
        import shlex
        command = f"{Path(sys.executable).as_posix()} {script.as_posix()}" if sys.platform == "win32" else shlex.join([sys.executable, str(script)])
        handler = {"type": "command", "command": command}
    record = {"event": "PreToolUse", "marker": "check-bugfix-discipline",
              "context": {"matcher": "Bash"}, "handler": handler}
    spec = {"kind": "hooks", "handlers": [record], "agentAdded": provider == "claude"}
    foreign = {"type": "command", "command": "echo user-owned"}
    data = {"theme": "dark", "hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [deepcopy(handler)]},
        {"matcher": "Other", "hooks": [foreign]}]}}
    if provider == "claude":
        data["agent"] = "lead"
    return data, spec


@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_remove_exact_owned_hooks_preserves_foreign_groups_and_fields(tmp_path, provider):
    data, spec = fixture(tmp_path, provider)
    foreign = deepcopy(data["hooks"]["PreToolUse"][1])
    output = OP._remove_hooks(BACKEND, ROOT, data, spec, provider, "project", tmp_path, CODEC)
    after = json.loads(output)
    assert after["theme"] == "dark"
    assert after["hooks"]["PreToolUse"][0] == {"matcher": "Bash", "hooks": []}
    assert after["hooks"]["PreToolUse"][1] == foreign
    assert "agent" not in after


def test_modified_owned_hook_is_not_silently_removed(tmp_path):
    data, spec = fixture(tmp_path, "claude")
    data["hooks"]["PreToolUse"][0]["hooks"][0]["timeout"] = 42
    before = deepcopy(data)
    with pytest.raises(ValueError, match="Modified owned hook"):
        OP._remove_hooks(BACKEND, ROOT, data, spec, "claude", "project", tmp_path, CODEC)
    assert data == before


def test_changed_user_agent_is_preserved(tmp_path):
    data, spec = fixture(tmp_path, "claude")
    data["agent"] = "user-custom"
    after = json.loads(OP._remove_hooks(BACKEND, ROOT, data, spec, "claude", "project", tmp_path, CODEC))
    assert after["agent"] == "user-custom"
