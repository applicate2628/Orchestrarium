from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "process_supervision" / "process_runner.py"
CHILD = ROOT / "tests" / "fixtures" / "process_supervision" / "child_helper.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("process_runner_cli_test", RUNNER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _header(runner, nonce: bytes, argv: tuple[str, ...], stdin: bytes, *, request_id: str = "a" * 32):
    executable = Path(sys.executable).resolve()
    return {
        "schema": "orchestrarium.process-request.v1",
        "requestId": request_id,
        "parentPid": os.getpid(),
        "parentStartMarker": runner.get_process_start_marker(os.getpid()),
        "capabilitySha256": "0" * 64,
        "argv": [str(executable), *argv[1:]],
        "windowsArgvProfileId": (
            "python-validator-json-echo-v1" if os.name == "nt" else None
        ),
        "cwd": str(ROOT),
        "environment": [
            {"name": name, "value": os.environ[name]}
            for name in ("PATH", "SYSTEMROOT", "TEMP", "TMP")
            if name in os.environ
        ],
        "stdinSha256": hashlib.sha256(stdin).hexdigest(),
        "policyId": "cli-bounded-v1",
        "deadlineMilliseconds": 10_000,
        "nonAuthorizing": True,
        "claimDirectoryIdentitySha256": "0" * 64,
    }


def _invoke_cli(request_file: Path, nonce: bytes) -> subprocess.CompletedProcess[str]:
    runner = _load_runner()
    directory_digest = runner.claim_directory_identity_sha256(
        str(request_file.parent)
    )
    capability_payload = (
        b"unread-windows-capability"
        if os.name == "nt"
        else runner.encode_capability_binding(nonce, directory_digest)
    )
    if os.name == "nt":
        import msvcrt

        read_fd, write_fd = os.pipe()
        os.set_inheritable(read_fd, True)
        handle = msvcrt.get_osfhandle(read_fd)
        startup = subprocess.STARTUPINFO()
        startup.lpAttributeList = {"handle_list": [handle]}
        process = subprocess.Popen(
            [sys.executable, str(RUNNER_PATH), "--request-file", str(request_file), "--capability-handle", str(handle)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            close_fds=True,
            startupinfo=startup,
        )
        os.close(read_fd)
    else:
        read_fd, write_fd = os.pipe()
        process = subprocess.Popen(
            [sys.executable, str(RUNNER_PATH), "--request-file", str(request_file), "--capability-handle", str(read_fd)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            close_fds=True,
            pass_fds=(read_fd,),
        )
        os.close(read_fd)
    os.write(write_fd, capability_payload)
    os.close(write_fd)
    stdout, stderr = process.communicate(timeout=20.0)
    return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)


def _private_request(tmp_path: Path, runner, header, stdin: bytes, nonce: bytes) -> Path:
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    path = directory / "request.ready"
    header = dict(header)
    directory_digest = runner.claim_directory_identity_sha256(str(directory))
    header["claimDirectoryIdentitySha256"] = directory_digest
    header["capabilitySha256"] = runner.capability_binding_sha256(
        nonce, directory_digest
    )
    path.write_bytes(runner.encode_request_bundle(header, stdin))
    if os.name != "nt":
        path.chmod(0o600)
    return path


@pytest.mark.skipif(os.name == "nt", reason="Windows generic CLI unavailable")
def test_cli_wrong_capability_denies_before_target_marker(tmp_path: Path) -> None:
    """A mismatched capability digest cannot create the target process."""
    runner = _load_runner()
    nonce = b"n" * 32
    marker = tmp_path / "forbidden-marker.txt"
    argv = (sys.executable, str(CHILD), "marker", "--marker", str(marker))
    path = _private_request(tmp_path, runner, _header(runner, nonce, argv, b""), b"", nonce)
    result = _invoke_cli(path, b"x" * 32)
    assert result.returncode == 2
    safe = json.loads(result.stdout)
    assert safe["failureId"] == "PSV1-REQUEST-INVALID"
    assert safe["authorizing"] is False
    assert not marker.exists()


@pytest.mark.skipif(os.name == "nt", reason="Windows generic CLI unavailable")
def test_cli_parent_start_identity_mismatch_denies(tmp_path: Path) -> None:
    """A copied request bound to another parent start marker cannot launch."""
    runner = _load_runner()
    nonce = b"p" * 32
    argv = (sys.executable, str(CHILD), "identity")
    header = _header(runner, nonce, argv, b"")
    header["parentStartMarker"] = "0"
    path = _private_request(tmp_path, runner, header, b"", nonce)
    result = _invoke_cli(path, nonce)
    assert result.returncode == 2
    assert json.loads(result.stdout)["failureId"] == "PSV1-REQUEST-INVALID"


@pytest.mark.skipif(os.name == "nt", reason="Windows generic CLI unavailable")
def test_cli_rejects_unknown_sink_or_policy_override_field(tmp_path: Path) -> None:
    """The CLI cannot accept a caller sink path or free numeric capture override."""
    runner = _load_runner()
    nonce = b"s" * 32
    argv = (sys.executable, str(CHILD), "identity")
    header = _header(runner, nonce, argv, b"")
    header["sinkPath"] = str(tmp_path / "attacker.log")
    path = _private_request(tmp_path, runner, header, b"", nonce)
    result = _invoke_cli(path, nonce)
    assert result.returncode == 2
    assert json.loads(result.stdout)["failureId"] == "PSV1-REQUEST-INVALID"


@pytest.mark.skipif(os.name != "nt", reason="Windows-only unavailable branch")
def test_windows_cli_is_safe_unavailable_before_file_access(tmp_path: Path) -> None:
    result = _invoke_cli(tmp_path / "missing.ready", b"x" * 32)
    assert result.returncode == 2
    safe = json.loads(result.stdout)
    assert safe["failureId"] == "PSV1-CLI-PRIVATE-DIRECTORY-UNAVAILABLE"
    assert safe["resourcesClosed"] is True
