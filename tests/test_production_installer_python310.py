"""Python version-floor regressions for production installer entrypoints."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
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
PYTHON_310_PROBE = r'''
import builtins
import runpy
import sys
import types

def forbidden(*_args, **_kwargs):
    raise AssertionError("version preflight did not run before installer behavior")

sys.version_info = (3, 10, 0, "final", 0)
production_installer = types.ModuleType("production_installer")
production_installer.install = forbidden
sys.modules["production_installer"] = production_installer
builtins.input = forbidden
target = sys.argv[1]
sys.argv = sys.argv[1:]
runpy.run_path(target, run_name="__main__")
'''
PYTHON_310_INTERPRETER = r'''
import sys

sys.version_info = (3, 10, 0, "final", 0)
if sys.argv[1] == "-c":
    source = sys.argv[2]
    sys.argv = sys.argv[2:]
    exec(compile(source, "<string>", "exec"), {"__name__": "__main__"})
raise AssertionError("launcher executed its Python entrypoint before checking the version")
'''


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


@pytest.mark.parametrize("entrypoint", ENTRYPOINTS, ids=lambda path: path.name)
def test_python_310_fails_before_production_installer_import(entrypoint: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-c", PYTHON_310_PROBE, str(entrypoint)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.strip() == VERSION_FAILURE

@pytest.mark.parametrize("launcher", LAUNCHERS, ids=lambda path: path.name)
def test_posix_launcher_reports_python_310_floor(
    launcher: Path, tmp_path: Path
) -> None:
    bash = _find_bash()
    if bash is None:
        pytest.skip("bash is unavailable")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    runner = tmp_path / "python-310-runner.py"
    runner.write_text(PYTHON_310_INTERPRETER, encoding="utf-8")
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
        [bash, str(launcher)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.strip() == VERSION_FAILURE
