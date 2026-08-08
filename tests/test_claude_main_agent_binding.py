"""Claude main-agent Lead binding stays explicit, reversible, and narrowly owned."""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER_PATH = ROOT / "scripts" / "production_installer.py"


def _load_installer():
    spec = importlib.util.spec_from_file_location(
        "production_installer_claude_main_agent", INSTALLER_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


INSTALLER = _load_installer()


@pytest.mark.parametrize(
    ("mode", "has_agent", "agent", "expected_agent", "outcome", "changed"),
    (
        ("force", False, None, "lead", "lead-default-written", True),
        ("FORCE", False, None, "lead", "lead-default-written", True),
        ("force", True, "lead", "lead", "lead-already-selected", False),
        ("force", True, "other", "other", "preserved-nonlead-agent", False),
        ("auto", False, None, None, "mode-preserved", False),
        ("manual", True, "lead", "lead", "mode-preserved", False),
        ("unresolved", False, None, None, "mode-unresolved", False),
    ),
)
def test_claude_main_agent_merge_matrix(
    mode: str,
    has_agent: bool,
    agent: object,
    expected_agent: object,
    outcome: str,
    changed: bool,
) -> None:
    settings: dict[str, object] = {
        "theme": "dark",
        "hooks": {"SessionStart": [{"hooks": []}]},
    }
    if has_agent:
        settings["agent"] = agent
    before = copy.deepcopy(settings)

    actual_outcome, actual_changed = INSTALLER._merge_claude_main_agent(
        settings, mode
    )

    assert (actual_outcome, actual_changed) == (outcome, changed)
    assert settings["theme"] == before["theme"]
    assert settings["hooks"] == before["hooks"]
    if expected_agent is None:
        assert "agent" not in settings
    else:
        assert settings["agent"] == expected_agent


@pytest.mark.parametrize("invalid_agent", ([], {}, {"nested": "agent"}))
def test_claude_main_agent_merge_rejects_non_scalar_agent(
    invalid_agent: object,
) -> None:
    settings = {"agent": invalid_agent, "theme": "dark"}
    before = copy.deepcopy(settings)

    with pytest.raises(ValueError, match="agent.*scalar"):
        INSTALLER._merge_claude_main_agent(settings, "force")

    assert settings == before


@pytest.mark.parametrize(
    ("mode", "agent", "expected_agent", "warning"),
    (
        ("force", None, "lead", None),
        (
            "force",
            "operator-agent",
            "operator-agent",
            "WARN: Claude main agent preserved; force lead binding not installed",
        ),
        ("auto", None, None, None),
        ("manual", "lead", "lead", None),
    ),
)
def test_synthetic_claude_install_and_reinstall_preserve_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mode: str,
    agent: str | None,
    expected_agent: str | None,
    warning: str | None,
) -> None:
    home = tmp_path / "home"
    project = tmp_path / "project"
    settings_path = project / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings = {
        "theme": "dark",
        "hooks": {"UserPromptSubmit": [{"hooks": [{"command": "user-hook"}]}]},
    }
    if agent is not None:
        settings["agent"] = agent
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    (project / ".claude" / ".agents-mode.yaml").write_text(
        f"delegationMode: {mode}\n", encoding="utf-8"
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("USERPROFILE", raising=False)

    arguments = [
        "--target",
        str(project),
        "--force",
        "--allow-unsafe-target",
        "--no-hypothesis-hook",
    ]
    assert INSTALLER.install("claude", arguments) == 0
    first_output = capsys.readouterr().out
    after_first = json.loads(settings_path.read_text(encoding="utf-8"))
    assert after_first["theme"] == "dark"
    assert after_first["hooks"] == settings["hooks"]
    if expected_agent is None:
        assert "agent" not in after_first
    else:
        assert after_first["agent"] == expected_agent
    assert (project / ".claude" / "agents" / "lead.md").is_file()
    assert (project / ".claude" / "skills" / "lead" / "SKILL.md").is_file()
    if warning is None:
        assert "WARN: Claude main agent preserved" not in first_output
    else:
        assert warning in first_output

    assert INSTALLER.install("claude", arguments) == 0
    after_second = json.loads(settings_path.read_text(encoding="utf-8"))
    assert after_second == after_first


def test_failed_claude_install_rolls_back_settings_and_lead_definition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    project = tmp_path / "project"
    claude_root = project / ".claude"
    settings_path = claude_root / "settings.json"
    lead_path = claude_root / "agents" / "lead.md"
    lead_path.parent.mkdir(parents=True)
    settings_path.write_bytes(b'{"theme":"dark","hooks":{}}\n')
    lead_path.write_bytes(b"old lead definition\n")
    (claude_root / ".agents-mode.yaml").write_text(
        "delegationMode: force\n", encoding="utf-8"
    )
    before_settings = settings_path.read_bytes()
    before_lead = lead_path.read_bytes()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("USERPROFILE", raising=False)
    monkeypatch.setattr(
        INSTALLER,
        "_verify_files",
        lambda *_args, **_kwargs: ["forced rollback"],
    )

    assert INSTALLER.install(
        "claude",
        [
            "--target",
            str(project),
            "--force",
            "--allow-unsafe-target",
            "--no-hypothesis-hook",
        ],
    ) == 1

    assert settings_path.read_bytes() == before_settings
    assert lead_path.read_bytes() == before_lead


def test_dual_safe_lead_definition_and_current_state_documentation() -> None:
    lead_definition = (ROOT / "src.claude" / "agents" / "lead.md").read_text(
        encoding="utf-8"
    )
    frontmatter, body = lead_definition.split("---", 2)[1:]
    assert "initialPrompt: /lead" in frontmatter
    assert "skills:" not in frontmatter
    assert "Gate: `BLOCKED`" in body
    assert "lead-is-a-main-conversation-role" in body
    assert "Do NOT orchestrate, do NOT implement, do NOT spawn other agents" in body
    assert "## Bootstrap" not in body

    expected_current_state = {
        "README.md": "main-agent activation",
        "INSTALL.md": "settings.json",
        "src.claude/README.md": "initialPrompt",
        "src.claude/CLAUDE.md": "initialPrompt",
        "docs/provider-runtime-layouts.md": "initialPrompt",
    }
    for relative, marker in expected_current_state.items():
        assert marker in (ROOT / relative).read_text(encoding="utf-8"), relative

    claude_entrypoint = (ROOT / "src.claude" / "CLAUDE.md").read_text(
        encoding="utf-8"
    )
    help_command = (ROOT / "src.claude" / "commands" / "agents-help.md").read_text(
        encoding="utf-8"
    )
    assert "lead` is a host-selected main agent and inline `/lead` role" in claude_entrypoint
    assert "only a stale `subagent_type: lead` dispatch is fail-closed" in claude_entrypoint
    assert "lead` is a fail-closed stub with no valid dispatch" not in claude_entrypoint
    assert "host-selected main agent / inline role; only stale subagent dispatch is fail-closed" in help_command
    assert "fail-closed stub — never spawned" not in help_command


def test_claude_main_agent_slice_preserves_mcp_and_typed_routing_contracts() -> None:
    claude_specs = dict(
        (marker, (event, matcher))
        for marker, _path, event, matcher in INSTALLER._hook_specs(
            "claude", ROOT / "src.claude" / "agents"
        )
    )
    assert claude_specs["check-mcp-momentum"] == (
        "PreToolUse",
        "Grep|Bash|PowerShell|shell_command|exec_command",
    )
    assert claude_specs["check-typed-routing"] == ("PreToolUse", "Agent")
