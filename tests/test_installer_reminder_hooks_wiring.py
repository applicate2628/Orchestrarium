from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("production_installer_reminders", ROOT / "scripts/production_installer.py")
assert spec and spec.loader
installer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = installer
spec.loader.exec_module(installer)


@pytest.mark.parametrize("provider", ("codex", "claude"))
def test_reminder_hook_wiring(provider: str, tmp_path: Path) -> None:
    specs = {marker: (path, event, matcher) for marker, path, event, matcher in installer._hook_specs(provider, tmp_path)}
    assert specs["mcp-usage-reminder"][1] == "SessionStart"
    assert specs["agents-mode-reminder"][1] == "SessionStart"
    assert specs["check-scratch-valuables"][1] == "SessionStart"
    assert specs["turn-anchor-reminder"][1] == "UserPromptSubmit"
    assert specs["check-mcp-momentum"][2] == "Grep|Bash|PowerShell|shell_command|exec_command"
