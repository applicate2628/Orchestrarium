from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src.claude/agents/scripts/invoke-claude-api.py"
SPEC = importlib.util.spec_from_file_location("invoke_claude_api_test", MODULE)
assert SPEC and SPEC.loader
OWNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = OWNER
SPEC.loader.exec_module(OWNER)
AUTH_TOKEN_KEY = "ANTHROPIC_AUTH_" + "TOKEN"


def _secret(path: Path) -> Path:
    path.write_text(
        '{"env":{"ANTHROPIC_BASE_URL":"https://example.invalid",'
        f'"{AUTH_TOKEN_KEY}":"synthetic"}}}}',
        encoding="utf-8",
    )
    return path


def test_repository_discovered_claude_is_rejected_before_secret_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = tmp_path / "repository"
    (repository / ".git").mkdir(parents=True)
    nested = repository / "nested" / "cwd"
    nested.mkdir(parents=True)
    executable = repository / "repo-bin" / "claude.PY"
    executable.parent.mkdir()
    executable.write_text("raise SystemExit(0)\n", encoding="utf-8")
    relative_executable = os.path.relpath(executable, nested)
    secret = _secret(tmp_path / "SECRET.md")

    monkeypatch.chdir(nested)
    monkeypatch.setenv("CLAUDE_SECRET_FILE", str(secret))
    monkeypatch.setenv("CLAUDE_BIN", "claude")
    monkeypatch.setenv("PATH", "")
    monkeypatch.setenv("PATHEXT", ".PY")
    monkeypatch.setattr(
        OWNER.shutil,
        "which",
        lambda name: relative_executable if name == "claude" else None,
    )
    monkeypatch.setattr(
        OWNER,
        "extract_secret_object",
        lambda _path: pytest.fail("secret reached"),
    )
    monkeypatch.setattr(
        OWNER.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("provider reached"),
    )

    assert OWNER.main([]) == 1
    assert "E_EXTERNAL_PROVIDER_REPOSITORY_EXECUTABLE" in capsys.readouterr().err


@pytest.mark.parametrize("discovered", (False, True))
def test_explicit_or_external_claude_executable_remains_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, discovered: bool
) -> None:
    repository = tmp_path / "repository"
    (repository / ".git").mkdir(parents=True)
    nested = repository / "nested"
    nested.mkdir()
    executable = (
        tmp_path / "external" / "claude.py"
        if discovered
        else repository / "explicit-claude.py"
    )
    executable.parent.mkdir(exist_ok=True)
    executable.write_text("raise SystemExit(0)\n", encoding="utf-8")
    secret = _secret(tmp_path / "SECRET.md")
    observed: list[tuple[list[str], dict[str, str]]] = []

    monkeypatch.chdir(nested)
    monkeypatch.setenv("CLAUDE_SECRET_FILE", str(secret))
    monkeypatch.setenv("CLAUDE_BIN", "claude" if discovered else str(executable.resolve()))
    if discovered:
        monkeypatch.setattr(OWNER.shutil, "which", lambda _name: str(executable))
    monkeypatch.setattr(
        OWNER.subprocess,
        "run",
        lambda command, *, env, check: observed.append((command, env))
        or SimpleNamespace(returncode=0),
    )

    assert OWNER.main(["--version"]) == 0
    assert observed[0][0][-2:] == [str(executable.resolve()), "--version"]
    assert observed[0][1][AUTH_TOKEN_KEY] == "synthetic"


def test_repository_discovered_powershell_host_is_rejected_before_secret_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = tmp_path / "repository"
    (repository / ".git").mkdir(parents=True)
    nested = repository / "nested"
    nested.mkdir()
    script = repository / "explicit-claude.ps1"
    script.write_text("exit 0\n", encoding="utf-8")
    host = repository / "repo-bin" / "pwsh.exe"
    host.parent.mkdir()
    host.write_bytes(b"host fixture")
    secret = _secret(tmp_path / "SECRET.md")
    relative_host = os.path.relpath(host, nested)
    calls: list[str] = []

    monkeypatch.chdir(nested)
    monkeypatch.setenv("CLAUDE_BIN", str(script.resolve()))
    monkeypatch.setenv("CLAUDE_SECRET_FILE", str(secret))
    monkeypatch.setattr(
        OWNER.shutil,
        "which",
        lambda name: relative_host if name == "pwsh" else None,
    )
    monkeypatch.setattr(
        OWNER,
        "extract_secret_object",
        lambda _path: calls.append("secret") or {},
    )
    monkeypatch.setattr(
        OWNER.subprocess,
        "run",
        lambda *_args, **_kwargs: calls.append("provider")
        or SimpleNamespace(returncode=0),
    )

    assert OWNER.main([]) == 1
    assert "E_EXTERNAL_PROVIDER_REPOSITORY_EXECUTABLE" in capsys.readouterr().err
    assert calls == []


def test_external_powershell_host_for_explicit_script_remains_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    (repository / ".git").mkdir(parents=True)
    nested = repository / "nested"
    nested.mkdir()
    script = repository / "explicit-claude.ps1"
    script.write_text("exit 0\n", encoding="utf-8")
    host = tmp_path / "external" / "pwsh.exe"
    host.parent.mkdir()
    host.write_bytes(b"host fixture")
    secret = _secret(tmp_path / "SECRET.md")
    observed: list[list[str]] = []

    monkeypatch.chdir(nested)
    monkeypatch.setenv("CLAUDE_BIN", str(script.resolve()))
    monkeypatch.setenv("CLAUDE_SECRET_FILE", str(secret))
    monkeypatch.setattr(
        OWNER.shutil,
        "which",
        lambda name: str(host) if name == "pwsh" else None,
    )
    monkeypatch.setattr(
        OWNER.subprocess,
        "run",
        lambda command, **_kwargs: observed.append(command)
        or SimpleNamespace(returncode=0),
    )

    assert OWNER.main(["--version"]) == 0
    assert observed[0][0] == str(host.resolve())
    assert observed[0][-3:] == ["-File", str(script.resolve()), "--version"]
