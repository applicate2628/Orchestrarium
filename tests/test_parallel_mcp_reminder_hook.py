from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
HOOK = (
    ROOT
    / "src.codex"
    / "skills"
    / "lead"
    / "hooks"
    / "check-parallel-mcp-momentum.py"
)
REMINDER = (
    "[parallel and MCP momentum] Root Lead: if the user has not paused or parked "
    "new launches, recheck Ready before starting work; start useful compatible "
    "independent lanes without waiting and refill released capacity. Lead owns "
    "relevant MCP discovery and freshness for indexed results, and passes each "
    "lane only its needed tools and context. Keep leaves non-spawning; clean up "
    "owned stale processes, dead code, and disposable trash while preserving "
    "user or uncertain state. Advisory only: no decision, spawn, schedule, "
    "block, metering, or fan-out."
)


def _run(
    tmp_path: Path,
    config: str | None,
    *,
    envelope: object,
) -> subprocess.CompletedProcess[str]:
    project = tmp_path / "project"
    home = tmp_path / "home"
    project.mkdir()
    home.mkdir()
    (project / ".git").mkdir()
    (project / "src").mkdir()
    (project / "scripts").mkdir()
    (project / "scripts" / "run.py").write_text("print('run')\n", encoding="utf-8")
    if config is not None:
        config_dir = project / ".agents"
        config_dir.mkdir()
        (config_dir / ".agents-mode.yaml").write_text(config, encoding="utf-8")
    env = os.environ.copy()
    env["USERPROFILE"] = str(home)
    env["HOME"] = str(home)
    if isinstance(envelope, dict):
        envelope = dict(envelope)
        envelope.setdefault("cwd", str(project))
    return subprocess.run(
        [sys.executable, "-B", str(HOOK)],
        cwd=project,
        env=env,
        input=json.dumps(envelope) if not isinstance(envelope, str) else envelope,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _envelope(
    *,
    leaf: bool = False,
    tool_name: str = "apply_patch",
    tool_input: dict | None = None,
    extra: dict | None = None,
) -> dict:
    value = {
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": tool_input
        or {
            "patch": "*** Begin Patch\n*** Update File: src/app.py\n@@\n-old\n+new\n*** End Patch"
        },
    }
    if leaf:
        value["agent_id"] = "leaf-1"
    if extra:
        value.update(extra)
    return value


@pytest.mark.parametrize(
    "delegation_mode,parallel_mode",
    (("force", "force"), ("auto", "auto"), ("force", "auto"), ("auto", "force")),
)
def test_root_active_modes_emit_one_soft_additional_context(
    tmp_path: Path, delegation_mode: str, parallel_mode: str
) -> None:
    result = _run(
        tmp_path,
        f"delegationMode: {delegation_mode}\nparallelMode: {parallel_mode}\n",
        envelope=_envelope(),
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert len(result.stdout.splitlines()) == 1
    payload = json.loads(result.stdout)
    assert payload == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": REMINDER,
        }
    }
    flattened = json.dumps(payload)
    for requested_term in (
        "if the user has not paused or parked new launches",
        "owned stale processes",
        "dead code",
        "disposable trash",
        "while preserving user or uncertain state",
    ):
        assert requested_term in payload["hookSpecificOutput"]["additionalContext"]
    for blocking_field in (
        "permissionDecision",
        "permissionDecisionReason",
        '"decision"',
        "updatedInput",
    ):
        assert blocking_field not in flattened


def test_leaf_is_silent_even_when_both_modes_are_force(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        "delegationMode: force\nparallelMode: force\n",
        envelope=_envelope(leaf=True),
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


@pytest.mark.parametrize(
    "tool_name,tool_input",
    (
        ("apply_patch", {"file_path": "src/app.py"}),
        ("exec_command", {"command": "python scripts/run.py"}),
        ("Bash", {"command": "pytest tests/test_parallel_mcp_reminder_hook.py"}),
    ),
)
def test_verified_repository_work_start_classes_emit_once(
    tmp_path: Path, tool_name: str, tool_input: dict
) -> None:
    result = _run(
        tmp_path,
        "delegationMode: force\nparallelMode: force\n",
        envelope=_envelope(tool_name=tool_name, tool_input=tool_input),
    )

    assert result.returncode == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["hookSpecificOutput"]["additionalContext"] == REMINDER


@pytest.mark.parametrize(
    "tool_name,tool_input",
    (
        ("Read", {"file_path": "README.md"}),
        ("Grep", {"pattern": "Ready", "path": "."}),
        ("view_image", {"path": "screen.png"}),
        ("wait_agent", {"timeout_ms": 30000}),
        ("write_stdin", {"session_id": 1}),
        ("Stop", {}),
        ("close_agent", {"target": "lane"}),
        ("interrupt_agent", {"target": "lane"}),
        ("send_message", {"target": "lane", "message": "park"}),
        ("Bash", {"command": "Get-Content README.md"}),
        ("exec_command", {"command": "git status --short"}),
        ("exec_command", {"command": "rg --files"}),
        ("apply_patch", {"file_path": "work-items/active/item/status.md"}),
        ("apply_patch", {"file_path": ".scratch/capture.txt"}),
    ),
)
def test_read_wait_stop_and_bookkeeping_actions_are_silent(
    tmp_path: Path, tool_name: str, tool_input: dict
) -> None:
    result = _run(
        tmp_path,
        "delegationMode: force\nparallelMode: force\n",
        envelope=_envelope(tool_name=tool_name, tool_input=tool_input),
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


@pytest.mark.parametrize(
    "tool_name",
    ("Agent", "spawn_agent", "mcp__codegraph__codegraph_explore", "unknown_tool"),
)
def test_unverified_lane_start_and_unknown_tools_are_silent(
    tmp_path: Path, tool_name: str
) -> None:
    result = _run(
        tmp_path,
        "delegationMode: force\nparallelMode: force\n",
        envelope=_envelope(tool_name=tool_name, tool_input={"task": "start"}),
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_parked_user_remains_authoritative_on_an_eligible_work_start(
    tmp_path: Path,
) -> None:
    result = _run(
        tmp_path,
        "delegationMode: force\nparallelMode: force\n",
        envelope=_envelope(extra={"user_state": "parked"}),
    )

    assert result.returncode == 0
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "if the user has not paused or parked new launches" in context
    assert "Advisory only: no decision, spawn, schedule, block" in context


@pytest.mark.parametrize("source", ("resume", "compact"))
def test_eligible_work_start_remains_available_after_boundary_events(
    tmp_path: Path, source: str
) -> None:
    result = _run(
        tmp_path,
        "delegationMode: force\nparallelMode: force\n",
        envelope=_envelope(extra={"prior_session_start_source": source}),
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"] == REMINDER


@pytest.mark.parametrize(
    "config",
    (
        "delegationMode: manual\nparallelMode: force\n",
        "delegationMode: force\nparallelMode: manual\n",
        "delegationMode: force\n",
        "parallelMode: force\n",
        "delegationMode: maybe\nparallelMode: force\n",
        "delegationMode: force\nparallelMode: maybe\n",
        "DelegationMode: force\nParallelMode: force\n",
        None,
    ),
)
def test_manual_unknown_or_missing_modes_are_silent(
    tmp_path: Path, config: str | None
) -> None:
    result = _run(tmp_path, config, envelope=_envelope())

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


@pytest.mark.parametrize("envelope", ("not-json", [], None, {}, {"agent_id": "leaf"}))
def test_malformed_or_incomplete_envelope_fails_open_and_silent(
    tmp_path: Path, envelope: object
) -> None:
    result = _run(
        tmp_path,
        "delegationMode: force\nparallelMode: force\n",
        envelope=envelope,
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
