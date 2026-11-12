"""Published-layout packaging preserves mirrors and checks copied payload."""
import sys
from unittest.mock import patch
import pytest
from test_bundle_build import builder, small_inputs
from synthetic_bundle_support import build_synthetic_bundle

def test_missing_registered_provider_hook_refused(builder, tmp_path):
    source, runtime = small_inputs(builder, tmp_path)
    (source/"src.claude/agents/hooks/check-typed-routing.py").unlink()
    with pytest.raises(FileNotFoundError):
        builder._shared_hook_payload(source)

def test_postcopy_mirror_drift_prevents_manifest(builder, tmp_path, monkeypatch):
    source, runtime = small_inputs(builder, tmp_path)
    output = tmp_path/"output"
    copy = builder._copy_leaf
    def corrupt(src, dst):
        result = copy(src, dst)
        if str(dst).replace("\\","/").endswith("src.codex/skills/lead/scripts/check-git-push-gate.py"):
            from pathlib import Path
            path = Path(dst)
            path.write_bytes(path.read_bytes()+b"\n# injected receiving corruption\n")
        return result
    monkeypatch.setattr(builder, "_copy_leaf", corrupt)
    with pytest.raises(ValueError, match="Divergent client hook source"):
        build_synthetic_bundle(builder,source,runtime,output,target="linux-x64",release="development")
    assert not (output/"bundle.json").exists()
    assert b"injected receiving" not in (source/"src.codex/skills/lead/scripts/check-git-push-gate.py").read_bytes()

def test_manifest_import_restores_existing_module(builder,tmp_path):
    source, runtime = small_inputs(builder,tmp_path)
    sentinel = object()
    with patch.dict(sys.modules, {"_orche_bundle_hook_manifest": sentinel}):
        assert builder._shared_hook_payload(source) == []
        assert sys.modules["_orche_bundle_hook_manifest"] is sentinel
