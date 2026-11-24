"""Synthetic local-output and auth-refusal tests for the Claude prompt owner."""
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
from tests.fixtures.runtime_capabilities import requires_windows_process_runner


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / 'adapters/claude/agents/scripts/invoke-claude-prompt.py'


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
    fake.write_text(
        child_source or "import sys\nsys.stdin.buffer.read()\nprint('GATE: PASS')\n",
        encoding="utf-8",
    )
    prompt = tmp_path / "prompt.md"
    prompt.write_bytes(prompt_bytes if prompt_bytes is not None else b"review\n")
    terminal_receipt = (tmp_path / "terminal.receipt").resolve()
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith(
            ("ANTHROPIC_", "CLAUDE_", "AWS_", "GOOGLE_", "CLOUDSDK_", "GCLOUD_")
        )
        and key.upper() not in {"ORCHESTRARIUM_ALLOW_SUBSCRIPTION_CLAUDE", "CLOUD_ML_REGION"}
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
            "--terminal-receipt",
            str(terminal_receipt),
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


def test_subscription_refusal_recommends_only_admitted_credentials(
    tmp_path: Path,
) -> None:
    result = _run(tmp_path)

    assert result.returncode == 3
    assert "ANTHROPIC_API_KEY" in result.stderr
    assert "ANTHROPIC_AUTH_TOKEN" in result.stderr
    for rejected_mode in (
        "Amazon Bedrock",
        "Google Vertex AI",
        "ORCHESTRARIUM_ALLOW_SUBSCRIPTION_CLAUDE",
    ):
        assert rejected_mode not in result.stderr


@requires_windows_process_runner
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
def test_supported_auth_modes_return_nonauthorizing_local_output(
    tmp_path: Path, signal: dict[str, str]
) -> None:
    # The selected command is always the local fake; a mode flag grants no quota.
    result = _run(tmp_path, signal)
    _assert_completed_local_result(tmp_path, result)


def _assert_completed_local_result(tmp_path: Path, result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stderr
    prefix = "ORCHESTRARIUM_PROVIDER_RESULT_V2="
    assert result.stdout.startswith(prefix)
    payload = json.loads(result.stdout[len(prefix):])
    assert payload["resultText"].replace("\r\n", "\n") == "GATE: PASS\n"
    assert payload["token"] == "COMPLETE:EXTERNAL_NONAUTHORIZING"
    assert payload["primaryOutcome"]["token"] == "COMPLETE:PASS"
    assert payload["authorizing"] is False
    assert payload["closesRunIds"] == []
    assert payload["independentVerificationRequired"] is True
    assert payload["cleanupStatus"] == "complete"
    assert payload["cleanupIssueCount"] == 0
    assert payload["captureRecoveryRetained"] is False
    assert (tmp_path / "terminal.receipt").read_text(encoding="utf-8") == result.stdout
    assert list((tmp_path / "artifacts").iterdir()) == []


@requires_windows_process_runner
@pytest.mark.parametrize(
    "signal",
    (
        {"CLAUDE_CODE_USE_BEDROCK": "1"},
        {"CLAUDE_CODE_USE_VERTEX": "true"},
        {"ORCHESTRARIUM_ALLOW_SUBSCRIPTION_CLAUDE": "1"},
    ),
)
@pytest.mark.parametrize("stream", ("stdout", "stderr"))
def test_supported_modes_keep_credential_canaries_out_of_public_output(
    tmp_path: Path, signal: dict[str, str], stream: str
) -> None:
    canary = "unlisted-synthetic-credential"
    child = (
        "import sys\n"
        "sys.stdin.buffer.read()\n"
        f"sys.{stream}.write('api_key={canary}\\n')\n"
        "print('GATE: PASS')\n"
    )
    result = _run(tmp_path, signal, child_source=child)
    receipt = (tmp_path / "terminal.receipt").read_text(encoding="utf-8")
    assert canary not in result.stdout + result.stderr + receipt
    assert receipt == result.stdout
    payload = json.loads(result.stdout.split("=", 1)[1])
    if stream == "stdout":
        assert result.returncode == 1, result.stderr
        assert payload["token"] == "UNVERIFIED:E_EXTERNAL_PROVIDER_CREDENTIAL_ECHO"
        assert payload["resultText"] == ""
    else:
        # Settled stderr is private transport, never the selected public result.
        _assert_completed_local_result(tmp_path, result)
    assert payload["authorizing"] is False
    assert payload["closesRunIds"] == []
    assert payload["cleanupStatus"] == "complete"
    assert payload["captureRecoveryRetained"] is False
    assert list((tmp_path / "artifacts").iterdir()) == []


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


@requires_windows_process_runner
def test_vertex_local_output_reclaims_large_prompt_capture(tmp_path: Path) -> None:
    child = (
        "import sys\n"
        "payload=sys.stdin.buffer.read()\n"
        "assert payload\n"
        "sys.stdout.write('GATE: PASS\\n');sys.stdout.flush()\n"
    )
    for index in range(3):
        result = _run(
            tmp_path / str(index),
            {
                "CLAUDE_CODE_USE_VERTEX": "true",
            },
            child_source=child,
            prompt_bytes=b"x" * (15 * 1024 * 1024),
        )
        _assert_completed_local_result(tmp_path / str(index), result)
