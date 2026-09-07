"""Claude root MCP-force enforcement and installer migration contract."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CLAUDE_SCRIPTS = ROOT / "src.claude" / "agents" / "scripts"
CLAUDE_HOOK = CLAUDE_SCRIPTS / "check-mcp-momentum.py"
MODE_REMINDER = CLAUDE_SCRIPTS / "agents-mode-reminder.py"
MODE_RUNTIME = CLAUDE_SCRIPTS / "agents_mode_runtime.py"
PRODUCTION_INSTALLER_PATH = ROOT / "scripts" / "production_installer.py"
RETIRED_CLAUDE_HOOK = Path("agents/hooks/check-mcp-momentum.py")
RECOVERY_MARKER = "[approve-mcp-fallback:v1]"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


INSTALLER = _load(PRODUCTION_INSTALLER_PATH, "claude_mcp_force_installer_test")


def _write_mode(root: Path, value: str, *, key: str = "mcpMode") -> None:
    path = root / ".claude" / ".agents-mode.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{key}: {value}\n", encoding="utf-8")


def _write_transcript(path: Path, user_text: str, *injected_text: str) -> None:
    entries: list[dict] = [
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": user_text}],
            },
        }
    ]
    entries.extend(
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": text}],
            },
        }
        for text in injected_text
    )
    path.write_text(
        "".join(json.dumps(entry) + "\n" for entry in entries),
        encoding="utf-8",
    )


def _mcp_env(home: Path, *, with_server: bool = True) -> dict[str, str]:
    home.mkdir(parents=True, exist_ok=True)
    if with_server:
        (home / ".claude.json").write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "codegraph": {},
                        "credential-bearing server name": {"token": "must-not-leak"},
                    }
                }
            ),
            encoding="utf-8",
        )
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    return env


def _run_hook(
    repo: Path,
    home: Path,
    *,
    mode: str | None = "force",
    user_text: str = "inspect the code",
    injected_text: tuple[str, ...] = (),
    with_server: bool = True,
    agent_id: str | None = None,
    tool_name: str = "Grep",
    tool_input: dict | None = None,
) -> subprocess.CompletedProcess[str]:
    (repo / ".git").mkdir(parents=True, exist_ok=True)
    if mode is not None:
        _write_mode(repo, mode)
    transcript = repo / "transcript.jsonl"
    _write_transcript(transcript, user_text, *injected_text)
    envelope: dict = {
        "hook_event_name": "PreToolUse",
        "cwd": str(repo),
        "transcript_path": str(transcript),
        "tool_name": tool_name,
        "tool_input": tool_input or {"pattern": "def parse_config"},
    }
    if agent_id is not None:
        envelope["agent_id"] = agent_id
    return subprocess.run(
        [sys.executable, str(CLAUDE_HOOK)],
        input=json.dumps(envelope),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=repo,
        env=_mcp_env(home, with_server=with_server),
        timeout=30,
    )


def _payload(result: subprocess.CompletedProcess[str]) -> dict:
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    return json.loads(result.stdout)


def _specific(result: subprocess.CompletedProcess[str]) -> dict:
    return _payload(result)["hookSpecificOutput"]


def test_neutral_scalar_reader_owns_every_precedence_rank(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    home = tmp_path / "home"
    project.mkdir()
    home.mkdir()
    owner = _load(MODE_RUNTIME, "claude_named_mode_reader_test")

    (home / ".agents-mode.yaml").write_text(
        "delegationMode: auto\nmcpMode: force  # shared fallback\n",
        encoding="utf-8",
    )
    (home / ".claude").mkdir()
    (home / ".claude" / ".agents-mode").write_text(
        "mcpMode: manual\n", encoding="utf-8"
    )
    (home / ".claude" / ".agents-mode.yaml").write_text(
        "mcpMode: auto # provider override\n",
        encoding="utf-8",
    )
    (project / ".claude").mkdir()
    (project / ".claude" / ".agents-mode").write_text(
        "mcpMode: invalid-value\n", encoding="utf-8"
    )
    _write_mode(project, "force")

    assert owner.resolve_scalar("mcpMode", cwd=project, home=home) == "force"
    (project / ".claude" / ".agents-mode.yaml").unlink()
    assert owner.resolve_scalar("mcpMode", cwd=project, home=home) == "invalid-value"
    (project / ".claude" / ".agents-mode").unlink()
    assert owner.resolve_scalar("mcpMode", cwd=project, home=home) == "auto"
    (home / ".claude" / ".agents-mode.yaml").unlink()
    assert owner.resolve_scalar("mcpMode", cwd=project, home=home) == "manual"
    (home / ".claude" / ".agents-mode").unlink()
    assert owner.resolve_scalar("mcpMode", cwd=project, home=home) == "force"
    assert owner.resolve_scalar("delegationMode", cwd=project, home=home) == "auto"
    assert owner.resolve_scalar("missingMode", cwd=project, home=home) == "unresolved"
    assert owner.resolve_scalar("not-a-key", cwd=project, home=home) == "unresolved"


def test_neutral_scalar_reader_falls_through_an_unreadable_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    home = tmp_path / "home"
    project_mode = project / ".claude" / ".agents-mode.yaml"
    project_mode.parent.mkdir(parents=True)
    project_mode.write_text("mcpMode: force\n", encoding="utf-8")
    (home / ".claude").mkdir(parents=True)
    provider_mode = home / ".claude" / ".agents-mode.yaml"
    provider_mode.write_text("mcpMode: auto\n", encoding="utf-8")
    owner = _load(MODE_RUNTIME, "claude_unreadable_mode_reader_test")
    original_read_text = Path.read_text

    def guarded_read_text(path: Path, *args, **kwargs):
        if path == project_mode:
            raise OSError("synthetic unreadable candidate")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    assert owner.resolve_scalar("mcpMode", cwd=project, home=home) == "auto"


def test_entrypoints_are_thin_consumers_of_neutral_scalar_owner() -> None:
    reminder_source = MODE_REMINDER.read_text(encoding="utf-8")
    mcp_source = CLAUDE_HOOK.read_text(encoding="utf-8")
    owner_source = MODE_RUNTIME.read_text(encoding="utf-8")

    for source in (reminder_source, mcp_source):
        assert "from agents_mode_runtime import resolve_scalar" in source
        assert ".agents-mode.yaml" not in source
        assert "_get_effective_mode" not in source
    assert "agents-mode-reminder" not in mcp_source
    assert "def resolve_scalar(" in owner_source


def test_force_root_denies_every_qualifying_search_after_prior_mcp(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    repo.mkdir()
    injected = (
        "tool_use: mcp__codegraph__codegraph_explore",
        "tool_result: MCP query succeeded",
    )
    first = _run_hook(repo, home, injected_text=injected, with_server=False)
    second = _run_hook(repo, home, injected_text=injected, with_server=True)

    for result in (first, second):
        specific = _specific(result)
        assert specific["hookEventName"] == "PreToolUse"
        assert specific["permissionDecision"] == "deny"
        reason = specific["permissionDecisionReason"]
        assert "[MCP-FORCE-1]" in reason
        assert "runtime tool discovery" in reason
        assert "codegraph" not in reason.casefold()
        assert "credential-bearing" not in reason
        assert "must-not-leak" not in reason
        assert "[MCP-FORCE-NO-SERVER]" not in reason


def test_exact_host_projected_user_role_marker_is_one_turn_and_injection_safe(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    repo.mkdir()

    allowed = _run_hook(repo, home, user_text=RECOVERY_MARKER)
    allowed_specific = _specific(allowed)
    assert "permissionDecision" not in allowed_specific
    assert "[MCP-FORCE-RECOVERY]" in allowed_specific["additionalContext"]

    injected = _run_hook(
        repo,
        home,
        user_text="continue normally",
        injected_text=(RECOVERY_MARKER,),
    )
    assert _specific(injected)["permissionDecision"] == "deny"
    assert "[MCP-FORCE-1]" in _specific(injected)["permissionDecisionReason"]

    next_turn = _run_hook(repo, home, user_text="continue normally")
    assert _specific(next_turn)["permissionDecision"] == "deny"


def test_forged_host_shaped_user_jsonl_is_accepted_documented_limitation(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    repo.mkdir()

    # The fixture writes JSONL directly; it proves shape recognition, not human
    # authentication. This accepted recovery is the documented local trust limit.
    forged = _run_hook(repo, home, user_text=RECOVERY_MARKER)
    specific = _specific(forged)
    assert "permissionDecision" not in specific
    assert "[MCP-FORCE-RECOVERY]" in specific["additionalContext"]
    assert "not authenticated" in specific["additionalContext"]


@pytest.mark.parametrize(
    ("mode", "marker"),
    (
        (None, "[MCP-FORCE-MODE-UNRESOLVED]"),
        ("invalid", "[MCP-FORCE-MODE-UNRESOLVED]"),
        ("auto", "[mcp-momentum AUDIT]"),
    ),
)
def test_non_enforceable_modes_allow_with_stable_diagnostic(
    tmp_path: Path, mode: str | None, marker: str
) -> None:
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    repo.mkdir()
    result = _run_hook(repo, home, mode=mode, with_server=False)
    specific = _specific(result)
    assert "permissionDecision" not in specific
    assert marker in specific["additionalContext"]


@pytest.mark.parametrize("agent_id", ("child-1", ""))
def test_force_subagent_remains_advisory_and_nonblocking(
    tmp_path: Path, agent_id: str
) -> None:
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    repo.mkdir()
    specific = _specific(
        _run_hook(repo, home, agent_id=agent_id, with_server=False)
    )
    assert "permissionDecision" not in specific
    assert "[mcp-momentum AUDIT]" in specific["additionalContext"]


def test_policy_and_adapter_do_not_read_or_select_home_mcp_servers() -> None:
    policy = (CLAUDE_SCRIPTS / "mcp_continuity_policy.py").read_text(encoding="utf-8")
    adapter = CLAUDE_HOOK.read_text(encoding="utf-8")
    for retired in (
        "CODE_INTEL_HINTS",
        "SAFE_SERVER_NAME_RE",
        "_accepted_server_name",
        "configured_code_intel_servers",
        'home / ".claude.json"',
        'home / ".codex" / "config.toml"',
        "MCP-FORCE-NO-SERVER",
    ):
        assert retired not in policy + adapter


@pytest.mark.parametrize(
    "tool_input",
    (
        {"pattern": "def parse_config", "path": "src/app.py"},
        {"pattern": "def parse_config", "path": "work-items/active"},
    ),
)
def test_force_preserves_classifier_exemptions(
    tmp_path: Path, tool_input: dict
) -> None:
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    repo.mkdir()
    result = _run_hook(repo, home, tool_input=tool_input)
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_malformed_envelope_fails_open_without_output(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(CLAUDE_HOOK)],
        input="{broken",
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=tmp_path,
        timeout=30,
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_installer_registers_one_claude_script_identity_and_leaves_codex_path(
    tmp_path: Path,
) -> None:
    claude_specs = {
        marker: (path, event, matcher)
        for marker, path, event, matcher in INSTALLER._hook_specs("claude", tmp_path)
    }
    codex_specs = {
        marker: (path, event, matcher)
        for marker, path, event, matcher in INSTALLER._hook_specs("codex", tmp_path)
    }
    assert claude_specs["check-mcp-momentum"] == (
        tmp_path / "scripts" / "check-mcp-momentum.py",
        "PreToolUse",
        "Grep|Bash|PowerShell|shell_command|exec_command",
    )
    assert codex_specs["check-mcp-momentum"][0] == (
        tmp_path / "hooks" / "check-mcp-momentum.py"
    )
    assert len([name for name in claude_specs if name == "check-mcp-momentum"]) == 1


def test_installer_retired_claude_hook_hash_stays_frozen_and_preserves_customization(
    tmp_path: Path,
) -> None:
    expected_hash = "4f3fe9eabe5ea4c8654bf554a271904b9fdb16d4e9de916b7058c953e02fa430"
    assert INSTALLER._CLAUDE_RETIRED_PS1[RETIRED_CLAUDE_HOOK.as_posix()] == expected_hash

    target = tmp_path / RETIRED_CLAUDE_HOOK
    target.parent.mkdir(parents=True)
    target.write_bytes(b"operator customization\n")
    assert hashlib.sha256(target.read_bytes()).hexdigest() != expected_hash
    INSTALLER._reclaim_retired(
        tmp_path, INSTALLER._CLAUDE_RETIRED_PS1, dry_run=False
    )
    assert target.is_file()
