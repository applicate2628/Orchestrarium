"""Commercial-auth fail-closed tests for the Python Claude prompt owner."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from tests.fixtures.provider_prompt_projection import (
    materialize_provider_prompt_runtime,
)


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "src.claude/agents/scripts/invoke-claude-prompt.py"


def _projected_wrapper(tmp_path: Path) -> Path:
    scripts = tmp_path / "claude-projection" / "agents" / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    projection_shared = scripts.parents[1] / "shared"
    projection_shared.mkdir()
    (projection_shared / "provider-prompt-projections.v1.json").write_bytes(
        (ROOT / "shared" / "provider-prompt-projections.v1.json").read_bytes()
    )
    materialize_provider_prompt_runtime(ROOT, scripts)
    (scripts / "external-prompt-governance.md").write_bytes(
        (ROOT / "shared" / "external-prompt-governance.md").read_bytes()
    )
    (scripts / "external-role-taxonomy.v1.json").write_bytes(
        (ROOT / "shared" / "external-role-taxonomy.v1.json").read_bytes()
    )
    wrapper = scripts / WRAPPER.name
    wrapper.write_bytes(WRAPPER.read_bytes())
    support = tmp_path / "scripts"
    support.mkdir(exist_ok=True)
    (support / "agent-run-ledger.py").write_bytes(
        (ROOT / "scripts" / "agent-run-ledger.py").read_bytes()
    )
    return wrapper


def _run(
    tmp_path: Path,
    extra_env: dict[str, str] | None = None,
    *,
    child_source: str | None = None,
    prompt_bytes: bytes | None = None,
):
    tmp_path.mkdir(parents=True, exist_ok=True)
    fake = tmp_path / "fake-claude.py"
    fake.write_text(child_source or "print('GATE: PASS')\n", encoding="utf-8")
    prompt = tmp_path / "prompt.md"
    prompt.write_bytes(prompt_bytes if prompt_bytes is not None else b"review\n")
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
        [
            sys.executable,
            str(_projected_wrapper(tmp_path)),
            "auth-test",
            "--prompt-file",
            str(prompt),
        ],
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


def test_api_key_helper_is_refused_without_running_helper_or_leaking_child_output(
    tmp_path: Path,
) -> None:
    leak_probe = "helper-output-probe"
    helper_marker = tmp_path / "helper-ran"
    provider_marker = tmp_path / "provider-ran"
    helper = tmp_path / "helper.py"
    helper.write_text(
        "import pathlib\n"
        f"pathlib.Path({str(helper_marker)!r}).write_text('ran', encoding='utf-8')\n"
        f"print({leak_probe!r})\n",
        encoding="utf-8",
    )
    home = tmp_path / "home/.claude"
    home.mkdir(parents=True)
    (home / "settings.json").write_text(
        json.dumps({"apiKeyHelper": f'"{sys.executable}" "{helper}"'}) + "\n",
        encoding="utf-8",
    )
    child = (
        "import pathlib\n"
        f"pathlib.Path({str(provider_marker)!r}).write_text('ran', encoding='utf-8')\n"
        f"print({leak_probe!r})\n"
        "print('GATE: PASS')\n"
    )
    result = _run(tmp_path, child_source=child)

    assert result.returncode != 0
    assert "E_EXTERNAL_PROVIDER_API_KEY_HELPER_UNSUPPORTED" in result.stderr
    assert not helper_marker.exists()
    assert not provider_marker.exists()
    assert leak_probe not in result.stdout
    assert leak_probe not in result.stderr
    assert not (tmp_path / "artifacts").exists()


@pytest.mark.parametrize(
    ("settings_text", "expected_error"),
    (
        ('{"apiKeyHelper": {}}\n', "E_EXTERNAL_PROVIDER_API_KEY_HELPER_UNSUPPORTED"),
        ('{"apiKeyHelper": ""}\n', "E_EXTERNAL_PROVIDER_API_KEY_HELPER_UNSUPPORTED"),
        ("{not-json}\n", "E_EXTERNAL_PROVIDER_CREDENTIAL_SCAN_UNAVAILABLE"),
    ),
)
def test_malformed_user_api_key_helper_fails_before_capture_or_launch(
    tmp_path: Path,
    settings_text: str,
    expected_error: str,
) -> None:
    home = tmp_path / "home/.claude"
    home.mkdir(parents=True)
    (home / "settings.json").write_text(settings_text, encoding="utf-8")

    result = _run(tmp_path)

    assert result.returncode != 0
    assert expected_error in result.stderr
    assert not (tmp_path / "artifacts").exists()


def test_project_api_key_helper_claim_does_not_authorize_automated_launch(
    tmp_path: Path,
) -> None:
    project_settings = tmp_path / ".claude"
    project_settings.mkdir()
    (project_settings / "settings.json").write_text(
        '{"apiKeyHelper": "project-controlled-helper"}\n', encoding="utf-8"
    )

    result = _run(tmp_path)

    assert result.returncode == 3
    assert "commercial authentication" in result.stderr
    assert not (tmp_path / "artifacts").exists()


def test_vertex_closed_stdin_after_terminal_is_deterministically_benign(tmp_path: Path) -> None:
    child = (
        "import os,sys,time\n"
        "sys.stdout.write('GATE: PASS\\n');sys.stdout.flush()\n"
        "os.close(0)\n"
        "time.sleep(0.2)\n"
    )
    for index in range(3):
        result = _run(
            tmp_path / str(index),
            {"CLAUDE_CODE_USE_VERTEX": "true"},
            child_source=child,
                prompt_bytes=b"x" * (15 * 1024 * 1024),
        )
        assert result.returncode == 0, result.stderr
