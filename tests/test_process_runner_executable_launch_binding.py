from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import os
import shutil
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "process_supervision" / "process_runner.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "process_runner_executable_launch_binding_test", RUNNER_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _request(module, owner, executable: Path, cwd: Path):
    return module.ProcessRequestV1(
        schema_version=1,
        argv=(str(executable),),
        resolved_executable=executable,
        cwd=str(cwd),
        environment=(),
        stdin_bytes=None,
        deadline_monotonic=time.monotonic() + 5.0,
        capture_policy=module.CapturePolicyV1(
            "executable-launch-binding-test-v1", 1024 * 1024, 1024, 1024, 4096
        ),
        capture_sink_binding=owner.mint_memory_capture_sink(),
        settle_policy=module.SettlePolicyV1(2.0),
    )


def _script(path: Path, marker: str) -> Path:
    path.write_text(f"#!/bin/sh\nprintf {marker}\nsleep 0.2", encoding="utf-8")
    path.chmod(0o700)
    return path










@pytest.mark.skipif(os.name != "nt", reason="real Windows share-mode lock contract")
def test_windows_launch_owner_blocks_leaf_write_delete_and_parent_rename(
    tmp_path: Path,
) -> None:
    """The locked leaf and parent chain remain stable until lifecycle cleanup."""
    module = _load_runner()
    parent = tmp_path / "locked-parent"
    parent.mkdir()
    executable = parent / "python.exe"
    shutil.copy2(Path(sys.executable).resolve(), executable)
    lifecycle = module.RunLifecycleV1(module.RunTokenV1(b"e" * 16, 1))
    launch = module._acquire_executable_launch_owner(
        executable, lifecycle, windows_api=module._WindowsKernelV1()
    )

    assert launch.binding.sha256 == hashlib.sha256(executable.read_bytes()).hexdigest()
    with pytest.raises(OSError):
        executable.open("r+b")
    with pytest.raises(OSError):
        os.replace(executable, parent / "replacement.exe")
    with pytest.raises(OSError):
        parent.rename(tmp_path / "renamed-parent")

    observation = lifecycle.finalize_once(time.monotonic() + 2.0)
    assert observation.resources_closed is True
    renamed = parent.rename(tmp_path / "renamed-parent")
    assert renamed.is_dir()


def test_public_process_wire_shapes_expose_only_the_portable_expected_pin() -> None:
    """The private launch owner stays internal; only the portable Kimi pin is public."""
    module = _load_runner()
    assert tuple(field.name for field in dataclasses.fields(module.ProcessRequestV1)) == (
        "schema_version", "argv", "resolved_executable", "cwd", "environment",
        "stdin_bytes", "deadline_monotonic", "capture_policy", "capture_sink_binding",
        "settle_policy", "cancellation_probe", "diagnostic_port",
        "windows_argv_profile_id", "request_id", "policy_id",
        "expected_executable_binding",
    )
    assert "executable_launch_owner" not in {
        field.name for field in dataclasses.fields(module.ProcessResultV1)
    }
    assert "_executable_launch_owner" not in {
        field.name for field in dataclasses.fields(module.WindowsArgvAdmissionV1)
    }


def test_registration_failure_closes_launch_object_and_preserves_typed_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A lifecycle registration fault cannot leak the just-acquired executable object."""
    module = _load_runner()
    executable = tmp_path / ("python.exe" if os.name == "nt" else "tool")
    if os.name == "nt":
        shutil.copy2(Path(sys.executable).resolve(), executable)
    else:
        _script(executable, "closed")
    lifecycle = module.RunLifecycleV1(module.RunTokenV1(b"r" * 16, 1))
    expected = module.ProcessSupervisionError("PSV1-INTERNAL", "resource-cleanup")
    monkeypatch.setattr(
        lifecycle,
        "register_resource",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(expected),
    )

    with pytest.raises(module.ProcessSupervisionError) as caught:
        module._acquire_executable_launch_owner(executable, lifecycle)

    assert caught.value is expected
    replacement = tmp_path / ("replacement.exe" if os.name == "nt" else "replacement")
    os.replace(executable, replacement)
    assert replacement.is_file()


@pytest.mark.skipif(os.name != "nt", reason="executable acquisition is Windows-only")
def test_hash_read_failure_releases_pre_registration_launch_guards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A hash/read failure releases the descriptor, lease, and Windows path locks."""
    module = _load_runner()
    executable = tmp_path / ("python.exe" if os.name == "nt" else "tool")
    if os.name == "nt":
        shutil.copy2(Path(sys.executable).resolve(), executable)
    else:
        _script(executable, "hash-failure")
    lifecycle = module.RunLifecycleV1(module.RunTokenV1(b"h" * 16, 1))
    expected = module.ProcessSupervisionError(
        "PSV1-EXECUTABLE-UNRESOLVED", "request-validation"
    )
    monkeypatch.setattr(
        module,
        "_stream_open_executable_binding",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(expected),
    )

    with pytest.raises(module.ProcessSupervisionError) as caught:
        module._acquire_executable_launch_owner(executable, lifecycle)

    assert caught.value is expected
    observation = lifecycle.finalize_once(time.monotonic() + 2.0)
    assert observation.resources_closed is True
    replacement = tmp_path / ("replacement.exe" if os.name == "nt" else "replacement")
    os.replace(executable, replacement)
    assert replacement.is_file()


@pytest.mark.skipif(os.name != "nt", reason="Windows lifecycle-owned acquisition cleanup")
def test_hash_failure_cleanup_uncertainty_is_visible_and_owner_retryable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_runner()
    executable = tmp_path / "python.exe"
    shutil.copy2(Path(sys.executable).resolve(), executable)
    lifecycle = module.RunLifecycleV1(module.RunTokenV1(b"u" * 16, 1))
    api = module._WindowsKernelV1()
    real_close = api.close
    failed = False

    def fail_once(handle: int | None) -> bool:
        nonlocal failed
        if handle and not failed:
            failed = True
            return False
        return real_close(handle)

    monkeypatch.setattr(api, "close", fail_once)
    expected = module.ProcessSupervisionError(
        "PSV1-EXECUTABLE-UNRESOLVED", "request-validation"
    )
    monkeypatch.setattr(
        module,
        "_stream_open_executable_binding",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(expected),
    )

    with pytest.raises(module.ProcessSupervisionError) as caught:
        module._acquire_executable_launch_owner(
            executable, lifecycle, windows_api=api
        )
    assert caught.value is expected

    observation = lifecycle.finalize_once(time.monotonic() + 2.0)
    assert observation.resources_closed is False
    assert "PSV1-RESOURCE-CLOSE" in observation.cleanup_issues
    resource = lifecycle._resources[-1]
    launch = resource.action.__self__
    assert launch._closed is False

    launch.close()
    assert launch._closed is True
    replacement = tmp_path / "replacement.exe"
    os.replace(executable, replacement)
    assert replacement.is_file()


@pytest.mark.skipif(os.name != "nt", reason="production ProcessRunner execution is Windows-only")
def test_backend_factory_receives_live_launch_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A supported injected backend cannot silently reopen the executable pathname."""
    module = _load_runner()
    owner = module.ProcessRunnerV1()
    executable = (
        Path(sys.executable).resolve()
        if os.name == "nt"
        else _script(tmp_path / "tool", "backend")
    )
    observed: list[object] = []

    def factory(_runner, _lifecycle):
        def backend(request, _active, _validated, launch_owner):
            observed.append(launch_owner)
            assert launch_owner._closed is False
            return module._request_failure(
                request,
                module.ProcessSupervisionError("PSV1-CANCELLED", "cancellation"),
                time.monotonic(),
                executable_identity_sha256=launch_owner.identity_sha256,
            )

        return backend

    request = _request(module, owner, executable, tmp_path)
    if os.name == "nt":
        request = dataclasses.replace(
            request, windows_argv_profile_id="python-validator-json-echo-v1"
        )
    monkeypatch.setattr(
        module.Path,
        "resolve",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("pre-owner path resolution is forbidden")
        ),
    )
    result = module.ProcessRunnerV1(backend_factory=factory).run(request)

    assert result.failure_id == "PSV1-CANCELLED"
    assert len(observed) == 1
    assert observed[0]._closed is True


def test_non_linux_posix_refuses_before_launch_owner_acquisition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unsupported POSIX platforms preserve their typed oracle failure without opening a launch object."""
    module = _load_runner()
    owner = module.ProcessRunnerV1()
    request = _request(module, owner, Path(sys.executable).resolve(), ROOT)
    acquired: list[object] = []
    monkeypatch.setattr(module.os, "name", "posix")
    monkeypatch.setattr(module.sys, "platform", "darwin")
    monkeypatch.setattr(
        module,
        "validate_process_request",
        lambda _request: module.ValidatedCwdV1(
            str(ROOT), module.CwdIdentityV1(0, 0, 0, "", 0), "0" * 64
        ),
    )
    monkeypatch.setattr(
        module,
        "_acquire_executable_launch_owner",
        lambda *_args, **_kwargs: acquired.append((_args, _kwargs)),
    )

    result = owner.run(request)

    assert result.failure_id == "PSV1-POSIX-ORACLE-UNAVAILABLE"
    assert acquired == []








def test_close_retries_only_remaining_late_parent_handle_failure(
    tmp_path: Path,
) -> None:
    module = _load_runner()
    executable = tmp_path / "tool"
    executable.write_bytes(b"owner")
    descriptor = os.open(executable, os.O_RDONLY)

    class Api:
        def __init__(self) -> None:
            self.calls: list[int] = []
            self.failed = False

        def close(self, handle: int) -> bool:
            self.calls.append(handle)
            if handle == 11 and not self.failed:
                self.failed = True
                return False
            return True

    api = Api()
    launch = module._ExecutableLaunchOwnerV1(
        path=executable,
        descriptor=descriptor,
        parent_handles=(11, 22),
        windows_api=api,
        binding=module.ExecutableBindingV1(str(executable), 0, "0" * 64),
        identity_sha256="0" * 64,
        version_sha256="0" * 64,
        resource_name="test",
    )

    with pytest.raises(OSError):
        launch.close()
    assert launch._closed is False
    assert launch.descriptor == -1
    assert launch.parent_handles == [11]

    launch.close()
    assert launch._closed is True
    assert launch.parent_handles == []
    assert api.calls == [22, 11, 11]


@pytest.mark.skipif(os.name == "nt", reason="POSIX descriptor reuse contract")
def test_close_error_never_retries_reused_fd_and_settles_other_resources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_runner()
    executable = _script(tmp_path / "tool", "fd")
    sentinel = tmp_path / "sentinel"
    sentinel.write_bytes(b"sentinel")
    descriptor = os.open(executable, os.O_RDONLY | os.O_NOFOLLOW)
    real_close = os.close
    reused: list[int] = []
    close_calls: list[int] = []

    class Api:
        def __init__(self) -> None:
            self.failed = False

        def close(self, handle: int) -> bool:
            if handle == 11 and not self.failed:
                self.failed = True
                return False
            return True

    def close_then_reuse(value: int) -> None:
        close_calls.append(value)
        real_close(value)
        replacement = os.open(sentinel, os.O_RDONLY)
        assert replacement == value
        reused.append(replacement)
        raise OSError("injected post-close error")

    monkeypatch.setattr(module.os, "close", close_then_reuse)
    launch = module._ExecutableLaunchOwnerV1(
        path=executable,
        descriptor=descriptor,
        parent_handles=(11,),
        windows_api=Api(),
        binding=module.ExecutableBindingV1(str(executable), 0, "0" * 64),
        identity_sha256="0" * 64,
        version_sha256="0" * 64,
        resource_name="test",
    )

    with pytest.raises(OSError):
        launch.close()
    assert launch.descriptor == -1
    assert launch._closed is False

    launch.close()
    assert launch._closed is True
    assert close_calls == [descriptor]
    assert os.fstat(reused[0]).st_size == len(b"sentinel")
    real_close(reused[0])
