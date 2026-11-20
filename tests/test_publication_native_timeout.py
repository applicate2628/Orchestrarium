"""Native Windows gate timeout with a real scanner-owned Git child.

This is a controlled synchronous detector stall, not a full scanner.main or
publication run. The gate supervisor and scanner object-reader ownership are real.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "scripts/universal-hooks/scripts/check-git-push-gate.py"

CHILD = r"""
import asyncio, ctypes, importlib.util, json, os, sys, time
from ctypes import wintypes
from pathlib import Path
source = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("native_timeout_scanner", source)
scanner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = scanner
spec.loader.exec_module(scanner)
async def run():
    reader = scanner._AsyncGitObjectReader()
    refused = await reader.start()
    if refused is not None:
        raise RuntimeError(repr(refused))
    assert isinstance(reader.process, scanner._WindowsOwnedAsyncProcess)
    job = reader.process.job
    in_job = wintypes.BOOL()
    if not job._api.k32.IsProcessInJob(
        job._handles["process"], job._handles["job"], ctypes.byref(in_job)
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    print(json.dumps({"scanner_pid": os.getpid(), "scanner_ppid": os.getppid(),
                      "git_pid": reader.process.pid,
                      "reader_state": reader.state.name,
                      "windows_job": bool(in_job.value)}), flush=True)
    # Stand in for a synchronous detector that cannot yield to its deadline.
    time.sleep(60)
asyncio.run(run())
"""


def load_gate():
    sys.path.insert(0, str(OWNER.parent))
    try:
        spec = importlib.util.spec_from_file_location("native_timeout_gate", OWNER)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def process_has_exited(pid):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE only.
    if not handle:
        error = ctypes.get_last_error()
        if error == 87:  # The process no longer exists.
            return True
        raise OSError(error, "Cannot observe owned child")
    try:
        result = kernel.WaitForSingleObject(handle, 1000)
        if result not in (0, 258):
            raise OSError(ctypes.get_last_error(), "Cannot wait for owned child")
        return result == 0
    finally:
        kernel.CloseHandle(handle)


@unittest.skipUnless(os.name == "nt", "Windows Job receiving")
class NativeTimeoutTests(unittest.TestCase):
    def test_gate_timeout_closes_real_scanner_owned_git_child(self):
        gate = load_gate()
        binding = gate.PushScanBinding(
            "generic", "origin", "refs/heads/topic", "1" * 40, "1" * 40)
        interpreter = gate._interpreter_identity()
        component = gate.PathComponentIdentity(".", "directory", ())
        closure = gate.CanonicalSourceClosure(
            gate.SOURCE_LAYOUTS[0], component, (component,), (), "a" * 64, (),
            "b" * 64, interpreter,
            gate.RootLocatorIdentity("gate.py", ".", "directory", (), None,
                                     ".", (), "gate.py", ()))
        captured = gate.CapturedReviewPayload(
            gate.CapturedReviewModules(object(), object(), ()), {}, "c" * 64,
            {"status": "not-requested", "repository": None, "diagnostic": "not-needed"},
            None, False, b"", hashlib.sha256(b"").hexdigest())
        argv = (sys.executable, "-B", "-c", CHILD,
                str(OWNER.with_name("check-publication-safety.py")))
        scratch = ROOT / ".scratch"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="native-timeout-", dir=scratch) as temporary:
            subprocess.run(["git", "init", "-q", temporary], check=True)
            with mock.patch.object(gate, "SCAN_TIMEOUT_SECONDS", 3.0):
                pending = gate.PendingScanInvocation(
                    "native-timeout-invocation", "native-timeout-attempt", binding,
                    closure, interpreter, argv, object(), captured)
                launched, records = gate._run_snapshot_child(pending, b"", temporary)
            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertFalse(record.bounded_completion)
            self.assertTrue(record.settlement.complete)
            self.assertEqual(pending.state, gate.PendingState.FAILED)
            self.assertIsNone(pending.consumption_id)
            observed = json.loads(record.stdout.decode("utf-8"))
            self.assertEqual(observed["reader_state"], "ACTIVE")
            self.assertTrue(observed["windows_job"])
            # Windows venv Python can be a redirector: Popen owns the launcher,
            # while os.getpid() reports its interpreter child. Bind that actual
            # lineage instead of assuming that both identities must be equal.
            self.assertIn(launched.child_handle,
                          (observed["scanner_pid"], observed["scanner_ppid"]))
            self.assertTrue(process_has_exited(launched.child_handle))
            self.assertNotEqual(observed["scanner_pid"], observed["git_pid"])
            self.assertTrue(process_has_exited(observed["scanner_pid"]))
            self.assertTrue(process_has_exited(observed["git_pid"]))
            self.assertNotIn(b"receipt", record.stdout + record.stderr)
            with self.assertRaises(gate.PrRouteDenied):
                pending.correlate_and_consume_once(
                    launched, records, closure, interpreter, binding, time.monotonic())
            self.assertIsNone(pending.consumption_id)
            print("native timeout receiving:", observed,
                  "launcher, scanner and Git exited; incomplete scan cannot authorize")


if __name__ == "__main__":
    unittest.main()
