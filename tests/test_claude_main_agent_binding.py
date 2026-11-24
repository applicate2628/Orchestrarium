"""Claude selects its main agent; the installer preserves operator settings."""
from __future__ import annotations

import importlib.util
import json
import subprocess
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


@pytest.mark.parametrize("invalid_agent", ([], {}, {"nested": "agent"}))
def test_claude_settings_validation_rejects_non_scalar_agent(
    tmp_path: Path, invalid_agent: object
) -> None:
    settings_path = tmp_path / "settings.json"
    before = json.dumps({"agent": invalid_agent, "theme": "dark"}).encode()
    settings_path.write_bytes(before)

    with pytest.raises(ValueError, match="agent.*scalar"):
        INSTALLER._load_claude_settings(settings_path)

    assert settings_path.read_bytes() == before


@pytest.mark.parametrize("agent", (None, "operator-agent", "lead"))
def test_synthetic_claude_install_and_reinstall_preserve_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    agent: str | None,
) -> None:
    home = tmp_path / "home"
    project = tmp_path / "project"
    settings_path = project / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    claude_path = settings_path.parent / "CLAUDE.md"
    user_preamble = "# User preamble\n\nKeep this operator-owned text.\n\n"
    claude_path.write_text(
        user_preamble + "@AGENTS.md\n"
        "<!-- BEGIN ORCHESTRARIUM CLAUDE MANAGED -->\n"
        "# Claude Code Pack\n\nold managed bytes\n"
        "<!-- END ORCHESTRARIUM CLAUDE MANAGED -->\n",
        encoding="utf-8",
    )
    settings = {
        "theme": "dark",
        "hooks": {"UserPromptSubmit": [{"hooks": [{"command": "user-hook"}]}]},
    }
    if agent is not None:
        settings["agent"] = agent
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    before_settings = settings_path.read_bytes()
    before_identity = settings_path.stat().st_ino
    before_document = claude_path.read_bytes()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("USERPROFILE", raising=False)

    arguments = [
        "--target",
        str(project),
        "--force",
        "--allow-unsafe-target",
        "--no-hypothesis-hook",
    ]
    assert INSTALLER.install("claude", [*arguments, "--dry-run"]) == 0
    assert settings_path.read_bytes() == before_settings
    assert claude_path.read_bytes() == before_document
    assert not (project / ".claude" / "agents" / "lead.md").exists()

    capsys.readouterr()
    assert INSTALLER.install("claude", arguments) == 0
    first_output = capsys.readouterr().out
    assert settings_path.read_bytes() == before_settings
    assert settings_path.stat().st_ino == before_identity
    assert (project / ".claude" / "agents" / "lead.md").is_file()
    assert (project / ".claude" / "skills" / "lead" / "SKILL.md").is_file()
    installed_claude = claude_path.read_text(encoding="utf-8")
    assert installed_claude.startswith(user_preamble)
    payload = (ROOT / 'adapters/claude' / "CLAUDE.md").read_text(encoding="utf-8")
    assert payload.startswith("@AGENTS.md\n")
    assert installed_claude[len(user_preamble):] == (
        "@AGENTS.md\n<!-- BEGIN ORCHESTRARIUM CLAUDE MANAGED -->\n"
        + payload[len("@AGENTS.md\n"):]
        + "<!-- END ORCHESTRARIUM CLAUDE MANAGED -->\n"
    )
    assert installed_claude.splitlines().count("@AGENTS.md") == 1
    assert (settings_path.parent / "AGENTS.md").read_text(encoding="utf-8") == (
        "<!-- BEGIN ORCHESTRARIUM SHARED MANAGED -->\n"
        + (ROOT / "shared" / "AGENTS.shared.md").read_text(encoding="utf-8")
        + "<!-- END ORCHESTRARIUM SHARED MANAGED -->\n"
    )
    composed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "validate-claude-md.py"),
            "--claude-md",
            str(claude_path),
            "--agents-md",
            str(settings_path.parent / "AGENTS.md"),
            # The source delta still has its independent 8192-byte cap. This
            # installed fixture additionally preserves user-owned preamble and
            # the exact ownership framing, neither part of that source delta.
            "--size-cap",
            str(8192 + len(user_preamble.encode("utf-8")) + len(
                "<!-- BEGIN ORCHESTRARIUM CLAUDE MANAGED -->\n"
                "<!-- END ORCHESTRARIUM CLAUDE MANAGED -->\n"
            )),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert composed.returncode == 0, composed.stdout + composed.stderr
    assert "WARN: Claude main agent preserved" not in first_output

    assert INSTALLER.install("claude", arguments) == 0
    assert settings_path.read_bytes() == before_settings
    assert settings_path.stat().st_ino == before_identity
    assert claude_path.read_text(encoding="utf-8") == installed_claude


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
    settings_path.write_bytes(b'{"agent":"operator-agent","theme":"dark","hooks":{}}\n')
    lead_path.write_bytes(b"old lead definition\n")
    before_settings = settings_path.read_bytes()
    before_lead = lead_path.read_bytes()
    installed_help = claude_root / "commands" / "agents-help.md"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("USERPROFILE", raising=False)
    reached_verify = False

    def refuse_after_apply(*_args, **_kwargs):
        nonlocal reached_verify
        reached_verify = True
        assert installed_help.is_file()
        assert settings_path.read_bytes() == before_settings
        return ["forced rollback"]

    monkeypatch.setattr(INSTALLER, "_verify_files", refuse_after_apply)

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

    assert reached_verify
    assert settings_path.read_bytes() == before_settings
    assert lead_path.read_bytes() == before_lead
    assert not installed_help.exists()


def test_dual_safe_lead_definition_and_current_state_documentation() -> None:
    lead_definition = (ROOT / 'adapters/claude' / "agents" / "lead.md").read_text(
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
        "adapters/claude/README.md": "initialPrompt",
        "adapters/claude/CLAUDE.md": "initialPrompt",
        "docs/provider-runtime-layouts.md": "initialPrompt",
    }
    for relative, marker in expected_current_state.items():
        assert marker in (ROOT / relative).read_text(encoding="utf-8"), relative

    claude_entrypoint = (ROOT / 'adapters/claude' / "CLAUDE.md").read_text(
        encoding="utf-8"
    )
    help_command = (ROOT / 'adapters/claude' / "commands" / "agents-help.md").read_text(
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
            "claude", ROOT / 'adapters/claude' / "agents"
        )
    )
    assert claude_specs["check-mcp-momentum"] == (
        "PreToolUse",
        "Grep|Bash|PowerShell|shell_command|exec_command",
    )
    assert claude_specs["check-typed-routing"] == ("PreToolUse", "Agent")


def test_ambiguous_unmarked_claude_legacy_body_remains_rejected() -> None:
    unknown = "@AGENTS.md\n\n# Claude Code Pack\n\nold managed bytes\n"
    source = (ROOT / 'adapters/claude/CLAUDE.md').read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="E_CLAUDE_DOC_LEGACY_AMBIGUOUS"):
        INSTALLER._render_claude_document(unknown, source[len("@AGENTS.md\n"):], claude=True)
