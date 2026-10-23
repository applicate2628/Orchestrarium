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


def _run_hook(project: Path, home: Path, envelope: dict) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["USERPROFILE"] = str(home)
    env["HOME"] = str(home)
    return subprocess.run(
        [sys.executable, "-B", str(HOOK)],
        cwd=project,
        env=env,
        input=json.dumps(envelope),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _project_fixture(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "project"
    home = tmp_path / "home"
    (project / ".git").mkdir(parents=True)
    (project / ".agents").mkdir()
    (project / "scripts").mkdir()
    home.mkdir()
    (project / "scripts" / "run.py").write_text("print('run')\n", encoding="utf-8")
    (project / ".agents" / ".agents-mode.yaml").write_text(
        "delegationMode: force\nparallelMode: force\n",
        encoding="utf-8",
    )
    return project, home


def _assert_reminder(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert "parallel and MCP momentum" in payload["hookSpecificOutput"]["additionalContext"]


def test_powershell_repository_work_start_emits_parallel_reminder(tmp_path: Path) -> None:
    project, home = _project_fixture(tmp_path)
    result = _run_hook(
        project,
        home,
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "PowerShell",
            "tool_input": {"command": "python scripts/run.py"},
            "cwd": str(project),
        },
    )
    _assert_reminder(result)


def test_exec_command_cmd_repository_work_start_emits_parallel_reminder(tmp_path: Path) -> None:
    project, home = _project_fixture(tmp_path)
    result = _run_hook(
        project,
        home,
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "exec_command",
            "tool_input": {"cmd": "python scripts/run.py"},
            "cwd": str(project),
        },
    )
    _assert_reminder(result)
