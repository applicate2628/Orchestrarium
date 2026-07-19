"""Behavioral tests for the Claude prompt wrapper's commercial-auth preflight."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
BASH_WRAPPER = (
    ROOT / "src.claude" / "agents" / "scripts" / "invoke-claude-prompt.sh"
)
POWERSHELL_WRAPPER = (
    ROOT / "src.claude" / "agents" / "scripts" / "invoke-claude-prompt.ps1"
)
COMMERCIAL_AUTH_ENV = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "ORCHESTRARIUM_ALLOW_SUBSCRIPTION_CLAUDE",
)


def _bash() -> str:
    found = shutil.which("bash")
    if found and "System32" not in found:
        return found
    for candidate in (
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
    ):
        if Path(candidate).exists():
            return candidate
    return found or "bash"


def _to_posix(path: Path) -> str:
    value = str(path).replace("\\", "/")
    if len(value) > 1 and value[1] == ":":
        value = "/" + value[0].lower() + value[2:]
    return value


def _wrapper_cases() -> list[pytest.ParameterSet]:
    cases = [pytest.param("bash", _bash(), id="bash")]
    seen: set[str] = set()
    for name in ("powershell", "pwsh"):
        executable = shutil.which(name)
        if executable and executable.lower() not in seen:
            seen.add(executable.lower())
            cases.append(pytest.param("powershell", executable, id=name))
    return cases


WRAPPER_CASES = _wrapper_cases()


def _make_stub(tmp_path: Path, wrapper_kind: str) -> Path:
    if wrapper_kind == "bash":
        stub = tmp_path / "claude-stub.sh"
        stub.write_text(
            "#!/usr/bin/env bash\n"
            "cat >/dev/null\n"
            "printf 'invoked\\n' > \"$CLAUDE_STUB_MARKER\"\n"
            "printf 'GATE: PASS\\n'\n",
            encoding="utf-8",
            newline="\n",
        )
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        return stub

    stub = tmp_path / "claude-stub.ps1"
    stub.write_text(
        "param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)\n"
        "[System.IO.File]::WriteAllText(\n"
        "  $env:CLAUDE_STUB_MARKER, 'invoked', "
        "[System.Text.UTF8Encoding]::new($false))\n"
        "Write-Output 'GATE: PASS'\n"
        "exit 0\n",
        encoding="utf-8",
        newline="\n",
    )
    return stub


def _run_wrapper(
    tmp_path: Path,
    wrapper_kind: str,
    shell_executable: str,
    *,
    auth_env: dict[str, str] | None = None,
    settings_scope: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    home_dir = tmp_path / "home"
    cwd = tmp_path / "workdir"
    home_dir.mkdir()
    cwd.mkdir()
    prompt = tmp_path / "prompt.md"
    prompt.write_text("test prompt\n", encoding="utf-8", newline="\n")
    marker = tmp_path / "claude-invoked.txt"
    output_dir = tmp_path / "prompt-output"
    stub = _make_stub(tmp_path, wrapper_kind)

    if settings_scope is not None:
        settings_root = home_dir if settings_scope == "home" else cwd
        settings = settings_root / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text(
            '{\n  "apiKeyHelper": "commercial-key-helper"\n}\n',
            encoding="utf-8",
            newline="\n",
        )

    env = os.environ.copy()
    for name in COMMERCIAL_AUTH_ENV:
        env.pop(name, None)
    env.update(auth_env or {})
    env["HOME"] = _to_posix(home_dir) if wrapper_kind == "bash" else str(home_dir)
    env["USERPROFILE"] = str(home_dir)
    env["CLAUDE_BIN"] = _to_posix(stub) if wrapper_kind == "bash" else str(stub)
    env["CLAUDE_PROMPTS_DIR"] = (
        _to_posix(output_dir) if wrapper_kind == "bash" else str(output_dir)
    )
    env["CLAUDE_STUB_MARKER"] = (
        _to_posix(marker) if wrapper_kind == "bash" else str(marker)
    )

    if wrapper_kind == "bash":
        command = [
            shell_executable,
            _to_posix(BASH_WRAPPER),
            "subscription-guard",
            "--prompt-file",
            _to_posix(prompt),
        ]
    else:
        command = [
            shell_executable,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(POWERSHELL_WRAPPER),
            "subscription-guard",
            "-PromptFile",
            str(prompt),
        ]

    result = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    return result, marker, output_dir


@pytest.mark.parametrize("wrapper_kind,shell_executable", WRAPPER_CASES)
def test_subscription_only_refuses_before_prompt_write_or_claude_launch(
    tmp_path: Path, wrapper_kind: str, shell_executable: str
) -> None:
    result, marker, output_dir = _run_wrapper(
        tmp_path, wrapper_kind, shell_executable
    )

    assert result.returncode == 3, result.stdout + result.stderr
    assert result.stdout == ""
    assert "WARNING" in result.stderr
    assert (
        "automated `claude -p` under a subscription is not permitted"
        in result.stderr.lower()
    )
    assert "https://code.claude.com/docs/en/legal-and-compliance" in result.stderr
    assert "ORCHESTRARIUM_ALLOW_SUBSCRIPTION_CLAUDE=1" in result.stderr
    assert not marker.exists(), "the refused preflight must not invoke claude"
    assert not output_dir.exists(), "the refused preflight must not write prompt artifacts"


@pytest.mark.parametrize("wrapper_kind,shell_executable", WRAPPER_CASES)
@pytest.mark.parametrize(
    "auth_name,auth_value",
    [
        ("ANTHROPIC_API_KEY", "commercial-api-key"),
        ("ANTHROPIC_AUTH_TOKEN", "commercial-gateway-token"),
        ("CLAUDE_CODE_USE_BEDROCK", "YES"),
        ("CLAUDE_CODE_USE_VERTEX", "true"),
        ("ORCHESTRARIUM_ALLOW_SUBSCRIPTION_CLAUDE", "1"),
    ],
)
def test_commercial_auth_and_explicit_override_signals_pass_preflight(
    tmp_path: Path,
    wrapper_kind: str,
    shell_executable: str,
    auth_name: str,
    auth_value: str,
) -> None:
    result, marker, output_dir = _run_wrapper(
        tmp_path,
        wrapper_kind,
        shell_executable,
        auth_env={auth_name: auth_value},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert marker.read_text(encoding="utf-8").strip() == "invoked"
    assert output_dir.is_dir()
    assert "automated `claude -p` under a subscription" not in result.stderr.lower()


@pytest.mark.parametrize("wrapper_kind,shell_executable", WRAPPER_CASES)
@pytest.mark.parametrize("settings_scope", ["home", "project"])
def test_api_key_helper_settings_pass_preflight(
    tmp_path: Path,
    wrapper_kind: str,
    shell_executable: str,
    settings_scope: str,
) -> None:
    result, marker, output_dir = _run_wrapper(
        tmp_path,
        wrapper_kind,
        shell_executable,
        settings_scope=settings_scope,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert marker.read_text(encoding="utf-8").strip() == "invoked"
    assert output_dir.is_dir()
