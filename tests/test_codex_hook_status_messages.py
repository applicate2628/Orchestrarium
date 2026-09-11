from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = ROOT / "scripts" / "install-hypothesis-hook.py"
INSTALLER_PATH = ROOT / "scripts" / "production_installer.py"
SCRIPT_PATH = (
    ROOT
    / "scripts"
    / "universal-hooks"
    / "scripts"
    / "check-bugfix-discipline.py"
)

EXPECTED_STATUS_MESSAGES = {
    "agents-mode-reminder": "Load delegation mode",
    "check-bugfix-discipline": "Check fix discipline",
    "check-git-push-gate": "Check publication safety",
    "check-machine-local-path": "Check local paths",
    "check-mcp-momentum": "Check MCP tool use",
    "check-no-trash-in-repo": "Check cleanup",
    "check-parallel-mcp-momentum": "Parallel work and MCP",
    "check-passive-polling-stop": "Check task progress",
    "check-repository-orientation": "Check repository orientation",
    "check-scratch-valuables": "Check scratch recovery",
    "check-stale-relation-residue": "Check stale references",
    "mcp-usage-reminder": "Load MCP guidance",
    "turn-anchor-reminder": "Anchor active work",
}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


INSTALLER = _load(INSTALLER_PATH, "codex_hook_status_production_installer_test")


def _run_helper(target: Path, status: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-B",
            str(HELPER_PATH),
            "--target",
            str(target),
            "--platform",
            "codex",
            "--host-os",
            "windows" if sys.platform == "win32" else "posix",
            "--script-path",
            str(SCRIPT_PATH),
            "--script-marker",
            "check-bugfix-discipline",
            "--status-message",
            status,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_codex_helper_serializes_status_and_preserves_unrelated_hook_idempotently(
    tmp_path: Path,
) -> None:
    target = tmp_path / "hooks.json"
    custom_entry = {
        "matcher": "CustomTool",
        "hooks": [
            {
                "type": "command",
                "command": "custom-hook",
                "statusMessage": "Custom status",
            }
        ],
    }
    target.write_text(
        json.dumps(
            {"description": "user-owned", "hooks": {"PreToolUse": [custom_entry]}},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    first = _run_helper(target, "Check fix discipline")
    assert first.returncode == 0, first.stderr
    after_first = target.read_bytes()
    second = _run_helper(target, "Check fix discipline")
    assert second.returncode == 0, second.stderr
    assert target.read_bytes() == after_first

    data = json.loads(after_first)
    assert data["description"] == "user-owned"
    assert data["hooks"]["PreToolUse"][0] == custom_entry
    owned = data["hooks"]["PreToolUse"][1]["hooks"][0]
    assert owned["statusMessage"] == "Check fix discipline"
    assert "name" not in owned
    assert "description" not in owned


def test_every_codex_owned_registration_has_the_exact_short_status_message() -> None:
    installed_root = ROOT / "src.codex" / "skills" / "lead"
    markers = {marker for marker, *_rest in INSTALLER._hook_specs("codex", installed_root)}

    assert INSTALLER._CODEX_HOOK_STATUS_MESSAGES == EXPECTED_STATUS_MESSAGES
    assert set(INSTALLER._CODEX_HOOK_STATUS_MESSAGES) == markers
