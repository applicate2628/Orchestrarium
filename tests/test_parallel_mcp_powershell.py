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


def test_powershell_repository_work_start_emits_parallel_reminder(tmp_path: Path) -> None:
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
    envelope = {
        "hook_event_name": "PreToolUse",
        "tool_name": "PowerShell",
        "tool_input": {"command": "python scripts/run.py"},
        "cwd": str(project),
    }
    env = os.environ.copy()
    env["USERPROFILE"] = str(home)
    env["HOME"] = str(home)

    result = subprocess.run(
        [sys.executable, "-B", str(HOOK)],
        cwd=project,
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
