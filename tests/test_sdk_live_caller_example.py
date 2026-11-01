"""Offline checks for relocation of the historically qualified Windows caller."""
from pathlib import Path
import hashlib
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
CALLER = ROOT / "examples" / "sdk" / "coordination_live_caller.py"
HISTORICAL_SHA256 = "e1a45dd690d3a3c87a6dbb4eefadfa22fd92608b2ab40f78b6c1fa945a4255a2"


def test_only_checkout_locator_differs_from_verified_original():
    source = CALLER.read_bytes()
    relocated = b'ROOT=Path(__file__).resolve().parents[2]'
    original = b'ROOT=Path(__file__).resolve().parent/"repo"'
    assert source.count(relocated) == 1
    assert hashlib.sha256(source.replace(relocated, original)).hexdigest() == HISTORICAL_SHA256
    compile(source, str(CALLER), "exec")


@pytest.mark.parametrize("mode", ["import", "help", "missing-inputs"])
def test_entrypoint_without_live_effects(mode, tmp_path):
    # A separate interpreter avoids leaking provider imports into the test suite.
    # Any child process or socket creation in the caller fails this check.
    harness = r'''
import pathlib, runpy, socket, subprocess, sys
caller, mode = sys.argv[1:]
def denied(*args, **kwargs):
    raise AssertionError("offline caller attempted a process or network effect")
subprocess.Popen = denied
class DeniedSocket(socket.socket):
    def __init__(self, *args, **kwargs):
        denied()
socket.socket = DeniedSocket
socket.create_connection = denied
sys.argv = [caller] + (["--help"] if mode == "help" else [])
if mode == "import":
    loaded = runpy.run_path(caller, run_name="caller_offline_import")
    assert loaded["ROOT"] == pathlib.Path(caller).resolve().parents[2]
else:
    try:
        runpy.run_path(caller, run_name="__main__")
    except SystemExit as exc:
        assert exc.code == (0 if mode == "help" else 2), exc.code
    else:
        raise AssertionError("argument parser did not exit")
'''
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", harness, str(CALLER), mode],
        cwd=tmp_path, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert list(tmp_path.iterdir()) == []
