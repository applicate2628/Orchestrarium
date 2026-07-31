from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("production_installer_sessionstart", ROOT / "scripts/production_installer.py")
assert spec and spec.loader
installer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = installer
spec.loader.exec_module(installer)


@pytest.mark.parametrize("provider,expected_count", (("codex", 12), ("claude", 13)))
def test_complete_hook_set(provider: str, expected_count: int, tmp_path: Path) -> None:
    specs = installer._hook_specs(provider, tmp_path)
    assert len(specs) == expected_count
    assert len({marker for marker, *_rest in specs}) == expected_count
    assert all(path.suffix == ".py" for _marker, path, _event, _matcher in specs)
    if provider == "claude":
        assert any(marker == "check-typed-routing" for marker, *_rest in specs)
