"""Sparse migration does not choose new preferences or rewrite files directly."""
from pathlib import Path
import importlib.util
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pre52_sparse_normalizer", ROOT / "scripts/normalize-agents-mode.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


@pytest.mark.parametrize("leaf", [".agents-mode.yaml", ".agents-mode"])
def test_absence_and_sparse_bytes_are_unchanged(tmp_path, leaf):
    path = tmp_path / leaf
    assert module.migrate_overlay(path) is None
    assert not path.exists()
    original = b"# Preserve formatting\r\nexternalPriorityProfiles:\r\n  custom:\r\n    review.pre-pr: [codex]\r\nmcpMode: force"
    path.write_bytes(original)
    assert module.migrate_overlay(path) == original == path.read_bytes()


@pytest.mark.parametrize("legacy", [b"disabled", b"'disabled'", b'"DISABLED"'])
def test_legacy_reserve_disable_never_replaces_an_explicit_key(tmp_path, legacy):
    path = tmp_path / ".agents-mode"
    old = b"# Existing decision\r\nexternalClaudeApiMode : " + legacy + b" # explanation\r\n"
    path.write_bytes(old)
    assert module.migrate_overlay(path) == b"# Existing decision\r\nreserveResolver : disabled # explanation\r\n"
    assert path.read_bytes() == old
    explicit = b"reserveResolver : claude-wrapper\r\n" + old
    path.write_bytes(explicit)
    assert module.migrate_overlay(path) == explicit == path.read_bytes()


@pytest.mark.parametrize("provider", [b"gemini", b"'qwen'"])
def test_removed_provider_refuses_without_writing(tmp_path, provider):
    path = tmp_path / ".agents-mode.yaml"
    prior = b"externalProvider : " + provider + b"\n"
    path.write_bytes(prior)
    with pytest.raises(ValueError, match="E_EXTERNAL_PROVIDER_REMOVED"):
        module.migrate_overlay(path)
    assert path.read_bytes() == prior
