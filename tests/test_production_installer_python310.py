"""Python version-floor regressions for production installer entrypoints."""
from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINTS = (
    ROOT / "install.py",
    ROOT / "scripts" / "install-codex.py",
    ROOT / "scripts" / "install-claude.py",
)
LAUNCHERS = (
    ROOT / "install.sh",
    ROOT / "scripts" / "install-codex.sh",
    ROOT / "scripts" / "install-claude.sh",
)
VERSION_FAILURE = "FAIL: Python 3.11 or newer is required to run the Orchestrarium installer."


class _ExecCalled(Exception):
    pass


def _bootstrap_module():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    return importlib.import_module("python_installer_bootstrap")


def test_old_python_skips_unsupported_python3_and_reexecs_valid_python(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap = _bootstrap_module()
    supported_python = sys.executable
    real_run = subprocess.run
    probes: list[list[str]] = []
    exec_call: list[object] = []
    candidates = {"python3": "/tools/python3", "python": supported_python}

    monkeypatch.setattr(bootstrap.sys, "version_info", (3, 10, 0))
    monkeypatch.setattr(bootstrap.sys, "executable", "/tools/current-python")
    monkeypatch.setattr(bootstrap.sys, "argv", ["installer.py", "--flag", "two words"])
    monkeypatch.setattr(bootstrap.shutil, "which", candidates.get)

    def probe(command: list[str], **kwargs: object) -> types.SimpleNamespace:
        assert "stdin" not in kwargs
        probes.append(command)
        if command[0] == supported_python:
            return real_run(command, **kwargs)
        return types.SimpleNamespace(returncode=1)

    def execv(executable: str, argv: list[str]) -> None:
        exec_call.extend((executable, argv))
        raise _ExecCalled

    monkeypatch.setattr(bootstrap.subprocess, "run", probe)
    monkeypatch.setattr(bootstrap.os, "execv", execv)

    with pytest.raises(_ExecCalled):
        bootstrap.ensure_supported_python("/repo/install.py")

    assert [command[0] for command in probes] == ["/tools/python3", supported_python]
    assert exec_call == [
        supported_python,
        [supported_python, "/repo/install.py", "--flag", "two words"],
    ]


def test_supported_python_does_not_probe_or_exec(monkeypatch: pytest.MonkeyPatch) -> None:
    bootstrap = _bootstrap_module()

    monkeypatch.setattr(bootstrap.sys, "version_info", (3, 11, 0))
    monkeypatch.setattr(
        bootstrap.shutil,
        "which",
        lambda _name: (_ for _ in ()).throw(AssertionError("candidate probe ran")),
    )
    monkeypatch.setattr(
        bootstrap.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("version probe ran")),
    )
    monkeypatch.setattr(
        bootstrap.os,
        "execv",
        lambda *_args: (_ for _ in ()).throw(AssertionError("exec ran")),
    )

    bootstrap.ensure_supported_python("/repo/install.py")


def test_old_python_without_valid_candidate_fails_stably(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    bootstrap = _bootstrap_module()
    candidates = {"python3": "/tools/current-python", "python": "/tools/python"}
    probes: list[str] = []

    monkeypatch.setattr(bootstrap.sys, "version_info", (3, 10, 0))
    monkeypatch.setattr(bootstrap.sys, "executable", "/tools/current-python")
    monkeypatch.setattr(bootstrap.shutil, "which", candidates.get)
    monkeypatch.setattr(
        bootstrap.subprocess,
        "run",
        lambda command, **_kwargs: (
            probes.append(command[0]) or types.SimpleNamespace(returncode=1)
        ),
    )
    monkeypatch.setattr(
        bootstrap.os,
        "execv",
        lambda *_args: (_ for _ in ()).throw(AssertionError("exec ran")),
    )

    with pytest.raises(SystemExit) as error:
        bootstrap.ensure_supported_python("/repo/install.py")

    assert error.value.code == 2
    assert probes == ["/tools/python"]
    assert capsys.readouterr() == ("", VERSION_FAILURE + "\n")


@pytest.mark.parametrize("entrypoint", ENTRYPOINTS, ids=lambda path: path.name)
def test_entrypoint_bootstraps_before_version_failure_or_production_import(
    entrypoint: Path,
) -> None:
    probe = r'''
import builtins
import runpy
import sys
import types

def forbidden(*_args, **_kwargs):
    raise AssertionError("production behavior ran before the bootstrap")

def bootstrap(target):
    print(target)
    raise SystemExit(73)

sys.version_info = (3, 10, 0, "final", 0)
module = types.ModuleType("python_installer_bootstrap")
module.ensure_supported_python = bootstrap
sys.modules["python_installer_bootstrap"] = module
production_installer = types.ModuleType("production_installer")
production_installer.install = forbidden
sys.modules["production_installer"] = production_installer
builtins.input = forbidden
target = sys.argv[1]
sys.argv = sys.argv[1:]
runpy.run_path(target, run_name="__main__")
'''
    result = subprocess.run(
        [sys.executable, "-c", probe, str(entrypoint)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 73
    assert result.stdout.strip() == str(entrypoint)
    assert result.stderr == ""


@pytest.mark.parametrize("launcher", LAUNCHERS, ids=lambda path: path.name)
def test_posix_launcher_execs_first_python_with_exact_target_argv_and_stdin(
    launcher: Path, tmp_path: Path
) -> None:
    bash = _find_bash()
    if bash is None:
        pytest.skip("bash is unavailable")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    runner = tmp_path / "capture-launch.py"
    runner.write_text(
        "import json, sys\n"
        "print(json.dumps(sys.argv[1:]))\n"
        "print(sys.stdin.read(), end='')\n",
        encoding="utf-8",
    )
    fake_python = fake_bin / "python3"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        'exec "$PYTHON_COMPAT_REAL" "$PYTHON_COMPAT_RUNNER" "$@"\n',
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join((str(fake_bin), env.get("PATH", "")))
    env["PYTHON_COMPAT_REAL"] = sys.executable
    env["PYTHON_COMPAT_RUNNER"] = str(runner)

    result = subprocess.run(
        [bash, str(launcher), "--flag", "two words"],
        cwd=ROOT,
        env=env,
        input="stdin-payload",
        text=True,
        capture_output=True,
        check=False,
    )

    expected_target = launcher.with_suffix(".py")
    assert result.returncode == 0
    lines = result.stdout.splitlines()
    launched = json.loads(lines[0])
    assert Path(launched[0]) == expected_target
    assert launched[1:] == ["--flag", "two words"]
    assert "\n".join(lines[1:]) == "stdin-payload"
    assert result.stderr == ""


def _find_bash() -> str | None:
    bash = shutil.which("bash")
    if os.name != "nt":
        return bash
    git = shutil.which("git")
    if git is not None:
        git_bash = Path(git).resolve().parents[1] / "bin" / "bash.exe"
        if git_bash.is_file():
            return str(git_bash)
    return None
