"""Shared prepared Codex hook fixture for fake-provider transport tests."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INSTALLER_MODULE = ROOT / "scripts" / "production_installer.py"
FAKE_CODEX_HOOKS_HOST = Path(__file__).with_name("fake_codex_hooks_host.py")


def _load_installer():
    spec = importlib.util.spec_from_file_location(
        "production_installer_codex_hook_fixture", INSTALLER_MODULE
    )
    assert spec and spec.loader
    installer = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = installer
    spec.loader.exec_module(installer)
    return installer


def prepare_codex_home(tmp_path: Path) -> Path:
    """Create the trusted hooks.json expected by the fake Codex app-server."""
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    hooks: dict[str, list[dict]] = {}
    installed_root = ROOT / "src.codex" / "skills" / "lead"
    for _marker, script, event, matcher in _load_installer()._hook_specs(
        "codex", installed_root
    ):
        entry = {"hooks": [{"type": "command", "command": f"{sys.executable} {script}"}]}
        if matcher is not None:
            entry["matcher"] = matcher
        hooks.setdefault(event, []).append(entry)
    (codex_home / "hooks.json").write_text(
        json.dumps({"hooks": hooks}), encoding="utf-8"
    )
    return codex_home
