"""Shell-tool matcher coverage remains independent of installer language."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("production_installer_matchers", ROOT / "scripts/production_installer.py")
assert spec and spec.loader
installer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = installer
spec.loader.exec_module(installer)

EXPECTED = {
    "check-no-trash-in-repo": "Edit|Write|NotebookEdit|apply_patch|Bash|PowerShell",
    "check-git-push-gate": "Bash|PowerShell",
    "check-repository-orientation": "Edit|Write|NotebookEdit|apply_patch|Bash|PowerShell|shell_command|exec_command",
}


@pytest.mark.parametrize("provider", ("codex", "claude"))
def test_shell_matchers(provider: str, tmp_path: Path) -> None:
    actual = {marker: matcher for marker, _path, _event, matcher in installer._hook_specs(provider, tmp_path)}
    for marker, matcher in EXPECTED.items():
        assert actual[marker] == matcher
