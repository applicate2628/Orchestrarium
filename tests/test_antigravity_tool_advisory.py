"""Actual shared advisory policy with the official AGY native tool envelope."""
import json
from pathlib import Path
import runpy
import pytest
from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = load_module(ROOT / "adapters/antigravity/runtime/pre_tool_use.py", "agy_tool_advisory_test")
POLICY = runpy.run_path(str(ROOT / "scripts/universal-hooks/hooks/check-machine-local-path.py"))
OWNER = load_module(ROOT / "scripts/installation/ownership.py", "agy_tool_ownership_test")
CONFIG = load_module(ROOT / "scripts/installation/configuration.py", "agy_tool_config_test")


def machine_path():
    return "/".join(("", "home", "synthetic-owner", "private-project"))


def evaluate(name, args):
    return ADAPTER.evaluate({"toolCall": {"name": name, "args": args}}, POLICY["written_content_advisory"])


@pytest.mark.parametrize("name,field", list(ADAPTER.CONTENT_FIELDS.items()))
def test_actual_written_content_warns_without_permission_escalation(name, field):
    result = evaluate(name, {"TargetFile": "src/module.py", field: machine_path()})
    assert result["decision"] == "allow"
    assert "machine-local-path AUDIT" in result["reason"]
    assert set(result) == {"decision", "reason"}


@pytest.mark.parametrize("name,field", list(ADAPTER.CONTENT_FIELDS.items()))
def test_removed_text_description_and_target_are_not_written_content(name, field):
    assert evaluate(name, {"TargetFile": machine_path(), field: "portable content", "TargetContent": machine_path(),
                          "Description": machine_path(), "Instruction": machine_path()}) == {"decision": "allow"}


@pytest.mark.parametrize("target,content", [(".scratch/local.txt", None), ("docs/example.md", "$HOME/project"), ("docs/example.md", "/home/<you>/project")])
def test_shared_scratch_and_placeholder_exemptions_unchanged(target, content):
    assert evaluate("write_to_file", {"TargetFile": target, "CodeContent": machine_path() if content is None else content}) == {"decision": "allow"}


@pytest.mark.parametrize("payload", [None, {}, {"toolCall": []}, {"toolCall": {"name": [], "args": {}}},
    {"toolCall": {"name": "write_to_file", "args": {"TargetFile": "x", "CodeContent": []}}},
    {"toolCall": {"name": "multi_replace_file_content", "args": {"TargetFile": "x", "ReplacementChunks": [{"ReplacementContent": "not interpreted"}]}}}])
def test_unavailable_audit_is_not_fabricated_or_blocked(payload):
    assert ADAPTER.evaluate(payload, POLICY["written_content_advisory"]) == {"decision": "allow"}


def test_startup_receipt_remains_valid_and_upgrades_only_its_named_members():
    start = {"SessionStart": [{"type": "command", "command": "python startup.py"}]}
    audit = {"PreToolUse": [{"matcher": "^(write_to_file|replace_file_content)$", "hooks": [{"type": "command", "command": "python advisory.py"}]}]}
    old = {"kind": "json-projection", "members": {"orchestrarium-session-start": start}, "entries": []}
    new = {**old, "members": {**old["members"], "orchestrarium-machine-local-path": audit}}
    for spec in (old, new):
        OWNER.encode_record({}, "antigravity", "project", configs={".agents/hooks.json": spec})
    before = json.dumps({**old["members"], "user-hook": {"enabled": False}}).encode()
    after = CONFIG.json_projection(before, old, new)
    assert json.loads(after)["user-hook"] == {"enabled": False}
    assert json.loads(CONFIG.json_projection(after, new, None)) == {"user-hook": {"enabled": False}}


def test_receipt_cannot_expand_advisory_matcher():
    spec = {"kind": "json-projection", "members": {"orchestrarium-machine-local-path": {
        "PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "python advisory.py"}]}]}}, "entries": []}
    with pytest.raises(ValueError, match="matcher"):
        OWNER.encode_record({}, "antigravity", "project", configs={".agents/hooks.json": spec})
