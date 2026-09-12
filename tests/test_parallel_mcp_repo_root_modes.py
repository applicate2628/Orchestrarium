from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK = (
    ROOT
    / "src.codex"
    / "skills"
    / "lead"
    / "hooks"
    / "check-parallel-mcp-momentum.py"
)


def test_parallel_reminder_reads_project_modes_from_git_root(tmp_path: Path) -> None:
    project = tmp_path / "project"
    nested = project / "src" / "nested"
    home = tmp_path / "home"
    nested.mkdir(parents=True)
    home.mkdir()
    (project / ".git").mkdir()
    (project / "scripts").mkdir()
    (project / "scripts" / "run.py").write_text("print('run')\n", encoding="utf-8")
    config_dir = project / ".agents"
    config_dir.mkdir()
    (config_dir / ".agents-mode.yaml").write_text(
        "delegationMode: force\nparallelMode: force\n", encoding="utf-8"
    )
    envelope = {
        "hook_event_name": "PreToolUse",
        "tool_name": "exec_command",
        "tool_input": {"cmd": "python ../../scripts/run.py"},
        "cwd": str(nested),
    }
    env = os.environ.copy()
    env["USERPROFILE"] = str(home)
    env["HOME"] = str(home)

    result = subprocess.run(
        [sys.executable, "-B", str(HOOK)],
        cwd=nested,
        env=env,
        input=json.dumps(envelope),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert "parallel and MCP momentum" in payload["hookSpecificOutput"]["additionalContext"]


def test_parallel_reminder_uses_absolute_mutation_target_root_from_outside_repo(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    outside = tmp_path / "outside"
    home = tmp_path / "home"
    target = project / "src" / "app.py"
    target.parent.mkdir(parents=True)
    target.write_text("print('app')\n", encoding="utf-8")
    outside.mkdir()
    home.mkdir()
    (project / ".git").mkdir()
    config_dir = project / ".agents"
    config_dir.mkdir()
    (config_dir / ".agents-mode.yaml").write_text(
        "delegationMode: force\nparallelMode: force\n", encoding="utf-8"
    )
    envelope = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": str(target)},
        "cwd": str(outside),
    }
    env = os.environ.copy()
    env["USERPROFILE"] = str(home)
    env["HOME"] = str(home)

    result = subprocess.run(
        [sys.executable, "-B", str(HOOK)],
        cwd=outside,
        env=env,
        input=json.dumps(envelope),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout != ""
    payload = json.loads(result.stdout)
    assert payload["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert "parallel and MCP momentum" in payload["hookSpecificOutput"]["additionalContext"]
