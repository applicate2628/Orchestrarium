from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("production_installer_orientation", ROOT / "scripts/production_installer.py")
assert spec and spec.loader
installer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = installer
spec.loader.exec_module(installer)
MATCHER = "Edit|Write|NotebookEdit|apply_patch|Bash|PowerShell|shell_command|exec_command"


@pytest.mark.parametrize("provider", ("codex", "claude"))
def test_repository_orientation_hook_wiring(provider: str, tmp_path: Path) -> None:
    specs = {marker: (path, event, matcher) for marker, path, event, matcher in installer._hook_specs(provider, tmp_path)}
    path, event, matcher = specs["check-repository-orientation"]
    assert path.name == "check-repository-orientation.py"
    assert event == "PreToolUse"
    assert matcher == MATCHER
