"""Commercial-auth fail-closed tests for the Python Claude prompt owner."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "src.claude/agents/scripts/invoke-claude-prompt.py"


def _run(tmp_path: Path, extra_env: dict[str, str] | None = None):
    fake = tmp_path / "fake-claude.py"
    fake.write_text("print('GATE: PASS')\n", encoding="utf-8")
    prompt = tmp_path / "prompt.md"
    prompt.write_text("review\n", encoding="utf-8")
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_AUTH_TOKEN",
            "CLAUDE_CODE_USE_BEDROCK",
            "CLAUDE_CODE_USE_VERTEX",
            "ORCHESTRARIUM_ALLOW_SUBSCRIPTION_CLAUDE",
        }
    }
    env.update(
        {
            "CLAUDE_BIN": str(fake),
            "CLAUDE_PROMPTS_DIR": str(tmp_path / "artifacts"),
            "HOME": str(home),
            "USERPROFILE": str(home),
        }
    )
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(WRAPPER), "auth-test", "--prompt-file", str(prompt)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


def test_subscription_only_fails_before_prompt_persistence(tmp_path: Path) -> None:
    result = _run(tmp_path)
    assert result.returncode == 3
    assert "commercial authentication" in result.stderr
    assert not (tmp_path / "artifacts").exists()


@pytest.mark.parametrize(
    "signal",
    (
        {"ANTHROPIC_" + "API_KEY": "synthetic"},
        {"ANTHROPIC_" + "AUTH_TOKEN": "synthetic"},
        {"CLAUDE_CODE_USE_BEDROCK": "1"},
        {"CLAUDE_CODE_USE_VERTEX": "true"},
        {"ORCHESTRARIUM_ALLOW_SUBSCRIPTION_CLAUDE": "1"},
    ),
)
def test_commercial_or_explicit_override_signals_launch(
    tmp_path: Path, signal: dict[str, str]
) -> None:
    result = _run(tmp_path, signal)
    assert result.returncode == 0, result.stderr


def test_api_key_helper_settings_launch(tmp_path: Path) -> None:
    home = tmp_path / "home/.claude"
    home.mkdir(parents=True)
    (home / "settings.json").write_text(
        '{"apiKeyHelper": "approved-helper"}\n', encoding="utf-8"
    )
    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr
