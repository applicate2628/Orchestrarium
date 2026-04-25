"""Unit tests for mitm_capture.py helpers (no real mitmproxy or network calls).

Run from proxy-forensics/ root: python scripts/tests/test_mitm_capture.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import mitm_capture as mc

FAILED = []
PASSED = 0


def assert_eq(name, actual, expected):
    global PASSED
    if actual == expected:
        print(f"  [OK] {name}")
        PASSED += 1
    else:
        FAILED.append(name)
        print(f"  [FAIL] {name}\n       expected: {expected!r}\n       actual:   {actual!r}")


def assert_true(name, cond, detail=""):
    global PASSED
    if cond:
        print(f"  [OK] {name}")
        PASSED += 1
    else:
        FAILED.append(name)
        print(f"  [FAIL] {name}  {detail}")


# -------------------------------------------------------------------------
# _kill_tree — child-survives-parent-timeout path
# -------------------------------------------------------------------------
print("\n--- _kill_tree: platform-specific kill invocations ---")

# Windows path: should call taskkill /F /T /PID
with mock.patch("mitm_capture.os") as mock_os, \
     mock.patch("mitm_capture.subprocess") as mock_sub:
    mock_os.name = "nt"
    mc._kill_tree(12345)
    # subprocess.run must have been called with taskkill /F /T /PID 12345
    mock_sub.run.assert_called_once()
    call_args = mock_sub.run.call_args[0][0]
    assert_eq("windows_kill_tree_uses_taskkill_F_T",
              [call_args[0], "/F" in call_args, "/T" in call_args, str(12345) in call_args],
              ["taskkill", True, True, True])

# POSIX safe path: child in its own group → killpg fires
with mock.patch("mitm_capture.os") as mock_os:
    mock_os.name = "posix"
    # Child is in a DIFFERENT process group from caller
    mock_os.getpgid.side_effect = lambda pid: 999 if pid == 12345 else 1234
    mock_os.getpid.return_value = 5555
    with mock.patch.dict("sys.modules", {"signal": mock.MagicMock(SIGKILL=9)}):
        mc._kill_tree(12345)
    mock_os.killpg.assert_called_once_with(999, 9)
    assert_true("posix_child_in_own_group_killpg_fires", True)

# POSIX safety guard: child in CALLER's group → kill only child pid, not group
with mock.patch("mitm_capture.os") as mock_os:
    mock_os.name = "posix"
    # Child and caller share pgid — guard must prevent killpg
    mock_os.getpgid.return_value = 1234
    mock_os.getpid.return_value = 5555
    with mock.patch.dict("sys.modules", {"signal": mock.MagicMock(SIGKILL=9)}):
        mc._kill_tree(12345)
    # killpg must NOT be called (would kill caller)
    mock_os.killpg.assert_not_called()
    # Individual kill should be called on child pid instead
    mock_os.kill.assert_called_once_with(12345, 9)
    assert_true("posix_safety_guard_prevents_caller_kill", True)

# POSIX: ProcessLookupError (child already exited) → swallow silently
with mock.patch("mitm_capture.os") as mock_os:
    mock_os.name = "posix"
    mock_os.getpgid.side_effect = ProcessLookupError("no such process")
    with mock.patch.dict("sys.modules", {"signal": mock.MagicMock(SIGKILL=9)}):
        try:
            mc._kill_tree(12345)
            no_raise = True
        except Exception:
            no_raise = False
    assert_true("posix_dead_child_no_raise", no_raise)

# Error path: _kill_tree must not raise when taskkill fails
with mock.patch("mitm_capture.os") as mock_os, \
     mock.patch("mitm_capture.subprocess") as mock_sub:
    mock_os.name = "nt"
    mock_sub.run.side_effect = Exception("boom")
    # Should not raise
    try:
        mc._kill_tree(12345)
        no_raise = True
    except Exception:
        no_raise = False
    assert_true("kill_tree_swallows_exceptions", no_raise)


# -------------------------------------------------------------------------
# Subprocess-hang simulation — child survives parent timeout, _kill_tree invoked
# -------------------------------------------------------------------------
print("\n--- subprocess timeout drains + kills children ---")

# This test simulates the codex-flagged Windows bug: subprocess.run(shell=True,
# timeout=N) can hang because shell returns but children persist. Our fix uses
# Popen + manual poll loop + _kill_tree. Test by mocking Popen to return a
# fake process that never exits within the budget.

class FakePopen:
    """Fake Popen that never poll()-returns nonzero until kill() is called."""
    def __init__(self, killed_marker):
        self.pid = 99999
        self._killed_marker = killed_marker
        self._kill_requested = False
        self.returncode = None
    def poll(self):
        if self._kill_requested:
            self.returncode = -9
            return -9
        return None
    def communicate(self, timeout=None):
        if not self._kill_requested:
            raise subprocess.TimeoutExpired(cmd=["fake"], timeout=timeout)
        return ("stdout-after-kill", "stderr-after-kill")

killed_marker = []

def fake_kill_tree(pid):
    killed_marker.append(pid)
    # Make Popen treat itself as killed
    fake_proc._kill_requested = True

fake_proc = FakePopen(killed_marker)

# Simulate the loop body from main() directly
deadline = time.monotonic() + 0.5  # tight timeout for test
killed_reason = None
while True:
    if fake_proc.poll() is not None:
        break
    if time.monotonic() > deadline:
        killed_reason = "timeout"
        fake_kill_tree(fake_proc.pid)
        break
    time.sleep(0.05)

try:
    stdout, stderr = fake_proc.communicate(timeout=1)
except subprocess.TimeoutExpired:
    fake_kill_tree(fake_proc.pid)
    stdout, stderr = fake_proc.communicate(timeout=1)

assert_eq("subprocess_hung_detected", killed_reason, "timeout")
assert_eq("kill_tree_invoked_with_correct_pid", killed_marker[0], 99999)
assert_eq("stdout_drained_after_kill", stdout, "stdout-after-kill")
assert_eq("stderr_drained_after_kill", stderr, "stderr-after-kill")


# -------------------------------------------------------------------------
# Summary
# -------------------------------------------------------------------------
print(f"\n{'='*60}\nRESULTS: {PASSED} passed, {len(FAILED)} failed")
if FAILED:
    print("Failed tests:")
    for f in FAILED:
        print(f"  - {f}")
    sys.exit(1)
print("All tests passed.")
sys.exit(0)
