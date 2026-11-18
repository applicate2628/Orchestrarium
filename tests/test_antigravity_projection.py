"""Pure projection/ownership/native context contracts; no agent invocation."""
from pathlib import Path
import json
import pytest
from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_module(ROOT / "scripts/installation/configuration.py", "agy_config_test")
OWNER = load_module(ROOT / "scripts/installation/ownership.py", "agy_ownership_test")
HOOK = load_module(ROOT / "adapters/antigravity/runtime/session_start.py", "agy_context_test")


def selection():
    return {"kind": "json-projection", "members": {"orchestrarium-session-start": {"SessionStart": [{"type": "command", "command": "python hook.py"}]}}, "entries": []}


def test_named_hook_merge_update_remove_preserves_other_members():
    before = b'{"user-hook":{"enabled":false},"unrelated":1}'
    spec = selection()
    installed = CONFIG.json_projection(before, None, spec)
    assert json.loads(installed)["user-hook"] == {"enabled": False}
    assert CONFIG.json_projection(installed, spec, spec) == installed
    assert json.loads(CONFIG.json_projection(installed, spec, None)) == json.loads(before)


def test_modified_and_unowned_hook_not_adopted():
    spec = selection()
    installed = CONFIG.json_projection(None, None, spec)
    with pytest.raises(ValueError, match="Unowned"):
        CONFIG.json_projection(installed, None, spec)
    changed = json.loads(installed)
    changed["orchestrarium-session-start"]["enabled"] = False
    with pytest.raises(ValueError, match="Modified"):
        CONFIG.json_projection(json.dumps(changed).encode(), spec, None)


def test_discovery_preserves_unrelated_and_rejects_duplicate_ownership():
    spec = {"kind": "json-projection", "members": {}, "entries": [{"path": ".agents/orchestrarium-antigravity/skills"}]}
    before = b'{"entries":[{"path":"team-skills"}],"exclude":["unwanted"]}'
    after = CONFIG.json_projection(before, None, spec)
    assert json.loads(CONFIG.json_projection(after, spec, None)) == json.loads(before)
    duplicate = json.loads(after)
    duplicate["entries"].append(spec["entries"][0])
    with pytest.raises(ValueError, match="Ambiguous"):
        CONFIG.json_projection(json.dumps(duplicate).encode(), spec, None)


@pytest.mark.parametrize("path", [".agents/skills/lead/SKILL.md", ".codex/AGENTS.md", ".agents/user.json", ".gemini/config/orchestrarium-antigravity/a"])
def test_project_receipt_cannot_own_codex_or_global_payload(path):
    with pytest.raises(ValueError):
        OWNER.encode_record({path: "a" * 64}, "antigravity", "project")


def test_both_scopes_accept_only_selected_projection_config():
    for scope, prefix in [("project", ".agents"), ("global", ".gemini/config")]:
        OWNER.encode_record({prefix + "/orchestrarium-antigravity/AGENTS.shared.md": "a" * 64}, "antigravity", scope,
                            configs={prefix + "/hooks.json": selection()})


def test_actual_sessionstart_wire_reads_only_installed_context(tmp_path, monkeypatch, capsys):
    import io
    root = tmp_path / "pack"
    (root / "runtime").mkdir(parents=True)
    (root / "AGENTS.shared.md").write_text("shared governance", encoding="utf-8")
    (root / "AGENTS.antigravity.md").write_text("native addendum", encoding="utf-8")
    monkeypatch.setattr(HOOK, "__file__", str(root / "runtime/session_start.py"))
    monkeypatch.setattr(HOOK.sys, "stdin", io.StringIO(json.dumps({"conversationId": "test", "workspacePaths": ["untrusted", "other"], "transcriptPath": "not-opened"})))
    assert HOOK.main() == 0
    assert json.loads(capsys.readouterr().out) == {"injectSteps": [{"systemMessage": {"systemMessage": "shared governance\n\nnative addendum"}}]}


@pytest.mark.parametrize("bad", [b'[]', b'{"entries":[],"entries":[]}'])
def test_malformed_user_config_not_replaced(bad):
    with pytest.raises(ValueError):
        CONFIG.json_projection(bad, None, selection())


@pytest.mark.parametrize("path", ["team-skills", ".agents/skills", "../other", ".agents/orchestrarium-antigravity/rules"])
def test_receipt_cannot_claim_unrelated_discovery(path):
    spec = {"kind": "json-projection", "members": {}, "entries": [{"path": path}]}
    with pytest.raises(ValueError, match="outside selected"):
        OWNER.encode_record({}, "antigravity", "project", configs={".agents/skills.json": spec})
