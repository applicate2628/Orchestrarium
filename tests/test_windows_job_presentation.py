"""Initial window presentation does not change Job ownership or settlement."""
from __future__ import annotations
import ctypes
import importlib
import inspect
import json
import os
from pathlib import Path
import sys
import time
import typing
import pytest

WINDOWS = pytest.mark.skipif(os.name != "nt", reason="native Windows presentation")


def test_public_presentation_contract_is_additive():
    job = importlib.import_module("scripts.process_supervision.windows_job")
    parameter = inspect.signature(job.WindowsJobOwnerV1.launch).parameters["presentation"]
    assert parameter.default == "default"
    assert typing.get_args(typing.get_type_hints(job.WindowsJobOwnerV1.launch)["presentation"]) == ("default", "hidden")
    assert job.windows_job_module_contract_v1() == (
        job.WINDOWS_JOB_MODULE_CONTRACT_V1, job.WindowsJobOwnerV1, job.WindowsJobError)


@pytest.mark.skipif(os.name == "nt", reason="non-Windows availability contract")
def test_hidden_option_does_not_claim_nonwindows_support():
    job = importlib.import_module("scripts.process_supervision.windows_job")
    with pytest.raises(job.WindowsJobError) as caught:
        job.WindowsJobOwnerV1.launch(executable=sys.executable, argv=(sys.executable,),
                                    cwd=None, environment=None, presentation="hidden")
    assert caught.value.failure_id == "WJOB-UNAVAILABLE"


@WINDOWS
@pytest.mark.parametrize("presentation", [None, False, True, 0, "visible", "HIDDEN"])
def test_invalid_presentation_refuses_before_native_allocation(presentation):
    job = importlib.import_module("scripts.process_supervision.windows_job")
    with pytest.raises(job.WindowsJobError) as caught:
        job.WindowsJobOwnerV1.launch(
            executable=sys.executable, argv=(sys.executable, "-c", "pass"),
            cwd=None, environment=None, presentation=presentation, api=object())
    assert (caught.value.failure_id, caught.value.stage) == ("WJOB-REQUEST", "launch")


@WINDOWS
@pytest.mark.parametrize("selection", ["omitted", "default", "hidden"])
def test_startup_presentation_preserves_creation_contract(tmp_path, monkeypatch, selection):
    job = importlib.import_module("scripts.process_supervision.windows_job")
    api = job.WindowsKernelV1()
    observed = []
    def refuse_creation(*args):
        startup = ctypes.cast(args[8], ctypes.POINTER(job.STARTUPINFOEXW)).contents
        info = startup.StartupInfo
        observed.append((info.dwFlags, info.wShowWindow))
        assert info.cb == ctypes.sizeof(job.STARTUPINFOEXW)
        assert info.hStdInput and info.hStdOutput and info.hStdError
        assert startup.lpAttributeList
        assert args[4] is True
        assert args[5] == (api.CREATE_SUSPENDED | api.CREATE_UNICODE_ENVIRONMENT | api.EXTENDED_STARTUPINFO_PRESENT)
        return False
    monkeypatch.setattr(api.k32, "CreateProcessW", refuse_creation)
    options = {} if selection == "omitted" else {"presentation": selection}
    with pytest.raises(job.WindowsJobError) as caught:
        job.WindowsJobOwnerV1.launch(executable=sys.executable,
            argv=(sys.executable, "-c", "pass"), cwd=str(tmp_path),
            environment={}, api=api, **options)
    assert caught.value.failure_id == "WJOB-PROCESS-CREATE"
    assert caught.value.windows_job_closure.complete
    assert observed == [(api.STARTF_USESTDHANDLES | (1 if selection == "hidden" else 0), 0)]


@WINDOWS
def test_hidden_presentation_reaches_child_after_pre_resume_gate(tmp_path):
    job = importlib.import_module("scripts.process_supervision.windows_job")
    marker = tmp_path / "first-instruction.txt"
    checked = []
    def before_resume():
        checked.append(True)
        assert not marker.exists()
    code = (
        "import ctypes,json,sys\nfrom pathlib import Path\n"
        "Path(sys.argv[4]).write_text('ran',encoding='ascii')\n"
        "buffer=ctypes.create_string_buffer(int(sys.argv[1]))\n"
        "kernel=ctypes.WinDLL('kernel32',use_last_error=True)\n"
        "kernel.GetStartupInfoW.argtypes=[ctypes.c_void_p]\n"
        "kernel.GetStartupInfoW.restype=None\n"
        "kernel.GetStartupInfoW(ctypes.byref(buffer))\n"
        "flags=ctypes.c_uint32.from_buffer(buffer,int(sys.argv[2])).value\n"
        "show=ctypes.c_uint16.from_buffer(buffer,int(sys.argv[3])).value\n"
        "print(json.dumps({'flags':flags,'show':show}))\n"
    )
    process = job.WindowsJobOwnerV1.launch(executable=sys.executable,
        argv=(sys.executable, "-I", "-B", "-c", code,
              str(ctypes.sizeof(job.STARTUPINFOW)), str(job.STARTUPINFOW.dwFlags.offset),
              str(job.STARTUPINFOW.wShowWindow.offset), str(marker)),
        cwd=str(tmp_path), environment=dict(os.environ), stdin="null", stderr="null",
        presentation="hidden", before_resume=before_resume)
    fd = process.take_stdout_fd()
    try:
        assert checked == [True]
        assert fd is not None
        assert process.wait(time.monotonic() + 5) == 0
        output = b""
        while chunk := os.read(fd, 4096):
            output += chunk
        value = json.loads(output)
        assert value["flags"] & 0x101 == 0x101
        assert value["show"] == 0
        assert marker.read_text() == "ran"
        closure = process.settle(time.monotonic() + 5)
        assert closure.complete and closure.direct_reaped and closure.active_zero
        assert closure.handles_closed
    finally:
        if fd is not None:
            os.close(fd)
        process.close()


@WINDOWS
def test_hidden_pre_resume_failure_never_runs_child_and_settles(tmp_path):
    job = importlib.import_module("scripts.process_supervision.windows_job")
    marker = tmp_path / "must-not-exist.txt"
    def refuse():
        assert not marker.exists()
        raise RuntimeError("synthetic-pre-resume")
    code = "from pathlib import Path;import sys;Path(sys.argv[1]).write_text('unexpected')"
    with pytest.raises(RuntimeError, match="synthetic-pre-resume") as caught:
        job.WindowsJobOwnerV1.launch(executable=sys.executable,
            argv=(sys.executable, "-I", "-B", "-c", code, str(marker)),
            cwd=str(tmp_path), environment=dict(os.environ),
            presentation="hidden", before_resume=refuse)
    assert caught.value.windows_job_closure.complete
    assert not marker.exists()


@WINDOWS
@pytest.mark.parametrize("presentation", ["default", "hidden"])
def test_gate_observer_error_after_creation_settles_without_resume(tmp_path, presentation):
    job = importlib.import_module("scripts.process_supervision.windows_job")
    marker = tmp_path / "must-not-run.txt"
    def observe(create):
        assert create()
        assert not marker.exists()
        raise RuntimeError("synthetic-create-observer")
    code = "from pathlib import Path;import sys;Path(sys.argv[1]).write_text('unexpected')"
    with pytest.raises(RuntimeError, match="synthetic-create-observer") as caught:
        job.WindowsJobOwnerV1.launch(executable=sys.executable,
            argv=(sys.executable, "-I", "-B", "-c", code, str(marker)),
            cwd=str(tmp_path), environment={}, presentation=presentation, create_gate=observe)
    assert caught.value.windows_job_closure.complete
    assert not marker.exists()


@WINDOWS
@pytest.mark.parametrize("presentation", ["default", "hidden"])
def test_real_creation_error_preserves_settlement(tmp_path, presentation):
    job = importlib.import_module("scripts.process_supervision.windows_job")
    absent = str(tmp_path / "nonexistent-child.exe")
    with pytest.raises(job.WindowsJobError) as caught:
        job.WindowsJobOwnerV1.launch(executable=absent, argv=(absent,),
            cwd=str(tmp_path), environment={}, presentation=presentation)
    assert caught.value.failure_id == "WJOB-PROCESS-CREATE"
    assert caught.value.windows_job_closure.complete
