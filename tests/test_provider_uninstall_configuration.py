from pathlib import Path
import hashlib
import pytest
from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_module(ROOT / "scripts/installation/configuration.py", "uninstall_configuration_tests")
INSTALL = load_module(ROOT / "scripts/production_installer.py", "uninstall_document_context_tests")


@pytest.mark.parametrize("kind", ["codex", "claude", "shared"])
def test_remove_only_recorded_block_preserves_surrounding_user_text(kind):
    begin, end = CONFIG.MARKERS[kind]
    block = begin + "\nowned instructions\n" + end
    text = "user prefix\n" + block + "\nuser suffix\n"
    digest = hashlib.sha256(block.encode()).hexdigest()
    assert CONFIG.remove_owned_block(text, kind, digest, INSTALL._claude_document_context) == "user prefix\n\nuser suffix\n"
    with pytest.raises(ValueError, match="Modified"):
        CONFIG.remove_owned_block(text.replace("owned instructions", "user changes"), kind, digest, INSTALL._claude_document_context)
    assert CONFIG.remove_owned_block("user only", kind, digest, INSTALL._claude_document_context) == "user only"


def test_markers_in_code_are_not_deletion_authority():
    begin, end = CONFIG.MARKERS["codex"]
    text = "```text\n" + begin + "\nexample\n" + end + "\n```\n"
    assert CONFIG.owned_block(text, "codex", INSTALL._claude_document_context) is None


def test_remove_native_role_keeps_unrelated_config_and_rejects_customizations():
    expected = {"worker": {"description": "Own worker", "config_file": "agents/worker.toml"}}
    prefix = b'model = "user-model"\n\n[features]\nmulti_agent_v2 = true\n\n'
    block = b'[agents.worker]\ndescription = "Own worker"\nconfig_file = "agents/worker.toml"\n\n'
    suffix = b'[agents.user_role]\ndescription = "User"\nconfig_file = "user.toml"\n'
    assert CONFIG.remove_native_roles(prefix + block + suffix, expected) == prefix + suffix
    assert CONFIG.remove_native_roles(prefix + suffix, expected) == prefix + suffix
    with pytest.raises(ValueError, match="Modified"):
        CONFIG.remove_native_roles(prefix + block.replace(b"Own worker", b"User edit") + suffix, expected)
    with pytest.raises(ValueError, match="Customized"):
        CONFIG.remove_native_roles(prefix + block.replace(b"description =", b"# my comment\ndescription =") + suffix, expected)


def test_remove_only_introduced_native_feature():
    source = b'model = "user-model"\n[features]\nmulti_agent_v2 = true\nplugins = false\n'
    assert CONFIG.remove_native_features(source, {"multi_agent_v2": True}) == b'model = "user-model"\n[features]\nplugins = false\n'
    assert CONFIG.remove_native_features(source, {}) == source
    changed = source.replace(b"multi_agent_v2 = true", b"multi_agent_v2 = false")
    assert CONFIG.remove_native_features(changed, {"multi_agent_v2": True}) == changed
    with pytest.raises(ValueError, match="Customized feature assignment"):
        CONFIG.remove_native_features(source.replace(b"multi_agent_v2 = true", b"multi_agent_v2 = true # user note"), {"multi_agent_v2": True})
