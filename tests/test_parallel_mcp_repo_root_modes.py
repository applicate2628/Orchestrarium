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


@pytest.mark.parametrize(
    "tool_name,target_shape",
    (
        ("Edit", "file_path"),
        ("Write", "path"),
        ("NotebookEdit", "notebook_path"),
        ("apply_patch", "patch"),
        ("apply_patch", "command"),
        ("apply_patch", "move-command"),
    ),
)
def test_parallel_reminder_uses_cross_repository_mutation_target_modes(
    tmp_path: Path,
    tool_name: str,
    target_shape: str,
) -> None:
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    cwd = repo_a / "src"
    target = repo_b / "src" / "app.py"
    home = tmp_path / "home"
    cwd.mkdir(parents=True)
    target.parent.mkdir(parents=True)
    target.write_text("print('app')\n", encoding="utf-8")
    home.mkdir()
    for repository, modes in (
        (repo_a, "delegationMode: manual\nparallelMode: force\n"),
        (repo_b, "delegationMode: force\nparallelMode: force\n"),
    ):
        (repository / ".git").mkdir()
        config_dir = repository / ".agents"
        config_dir.mkdir()
        (config_dir / ".agents-mode.yaml").write_text(modes, encoding="utf-8")
    patch = f"*** Begin Patch\n*** Update File: {target}\n*** End Patch"
    if target_shape == "move-command":
        patch = (
            "*** Begin Patch\n"
            f"*** Update File: {repo_b / '.scratch' / 'source.md'}\n"
            f"*** Move to: {target}\n"
            "*** End Patch"
        )
    tool_input = (
        {"command" if target_shape == "move-command" else target_shape: patch}
        if target_shape in {"patch", "command"}
        or target_shape == "move-command"
        else {target_shape: str(target)}
    )
    envelope = {
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": tool_input,
        "cwd": str(cwd),
    }
    env = os.environ.copy()
    env["USERPROFILE"] = str(home)
    env["HOME"] = str(home)

    result = subprocess.run(
        [sys.executable, "-B", str(HOOK)],
        cwd=cwd,
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
    assert "parallel and MCP momentum" in payload["hookSpecificOutput"]["additionalContext"]


def test_parallel_reminder_does_not_choose_between_multi_repository_targets(
    tmp_path: Path,
) -> None:
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    cwd = repo_a / "src"
    target_a = repo_a / "src" / "a.py"
    target_b = repo_b / "src" / "b.py"
    home = tmp_path / "home"
    cwd.mkdir(parents=True)
    target_b.parent.mkdir(parents=True)
    target_a.write_text("a = 1\n", encoding="utf-8")
    target_b.write_text("b = 1\n", encoding="utf-8")
    home.mkdir()
    for repository in (repo_a, repo_b):
        (repository / ".git").mkdir()
        config_dir = repository / ".agents"
        config_dir.mkdir()
        (config_dir / ".agents-mode.yaml").write_text(
            "delegationMode: force\nparallelMode: force\n", encoding="utf-8"
        )
    envelope = {
        "hook_event_name": "PreToolUse",
        "tool_name": "apply_patch",
        "tool_input": {
            "patch": (
                f"*** Begin Patch\n*** Update File: {target_a}\n"
                f"*** Update File: {target_b}\n*** End Patch"
            )
        },
        "cwd": str(cwd),
    }
    env = os.environ.copy()
    env["USERPROFILE"] = str(home)
    env["HOME"] = str(home)

    result = subprocess.run(
        [sys.executable, "-B", str(HOOK)],
        cwd=cwd,
        env=env,
        input=json.dumps(envelope),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
