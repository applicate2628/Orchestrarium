"""Ambiguous user settings must not be rewritten to choose the last key."""
from pathlib import Path
import pytest
from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]
OWNER = load_module(ROOT / "scripts/production_installer.py", "claude_duplicate_settings")

@pytest.mark.parametrize("raw", [
    b'{"agent":"custom","agent":"lead"}',
    b'{"other":1,"other":2}',
    b'{"permissions":{"allow":["one"],"allow":["two"]}}',
    b'{"agent":"custom","ag\\u0065nt":"lead"}',
])
def test_ambiguous_settings_are_rejected_without_change(tmp_path, raw):
    path = tmp_path / "settings.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="duplicate"):
        OWNER._load_claude_settings(path)
    assert path.read_bytes() == raw

@pytest.mark.parametrize("dry_run", [False, True])
def test_force_rejects_before_writer_is_loaded(tmp_path, monkeypatch, dry_run):
    path = tmp_path / "settings.json"
    raw = b'{"theme":"one","theme":"two"}'
    path.write_bytes(raw)
    def forbidden(*_args):
        pytest.fail("ambiguous user settings reached writer loading")
    monkeypatch.setattr(OWNER, "_load_module_from_path", forbidden)
    with pytest.raises(ValueError, match="duplicate"):
        OWNER._merge_claude_main_agent_settings(ROOT, path, "force", dry_run)
    assert path.read_bytes() == raw

def test_valid_unique_nested_settings_and_custom_agent_are_preserved(tmp_path):
    path = tmp_path / "settings.json"
    raw = b'{"agent":"custom","one":{"x":1},"two":{"x":2}}'
    path.write_bytes(raw)
    assert OWNER._load_claude_settings(path) == {"agent":"custom","one":{"x":1},"two":{"x":2}}
    assert OWNER._merge_claude_main_agent_settings(ROOT, path, "force", False) == "preserved-nonlead-agent"
    assert path.read_bytes() == raw

def test_missing_settings_still_load_as_empty(tmp_path):
    assert OWNER._load_claude_settings(tmp_path / "absent.json") == {}
