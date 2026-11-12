"""PowerShell hook invocation must retain native blocking exit status."""
from pathlib import Path
import os
import subprocess
import sys
import pytest
from _module_loading_support import load_module
ROOT = Path(__file__).resolve().parents[1]
health = load_module(ROOT / "scripts/check-hook-health.py", "copilot_exit_health")

def test_powershell_exit_wrapper_reuses_literal_serializer():
    tokens = [r"C:\Python\python.exe", "-I", "-B", r"C:\hook dir\hook.py"]
    base = health.serialize_windows_hook_command(tokens)
    assert health.serialize_powershell_hook_command(tokens) == "$LASTEXITCODE = 1; " + base + "; exit $LASTEXITCODE"
    with pytest.raises(ValueError):
        health.serialize_powershell_hook_command([])

@pytest.mark.skipif(os.name != "nt", reason="native PowerShell exit-code propagation")
@pytest.mark.parametrize("code", [0, 2, 7])
def test_native_powershell_preserves_hook_exit_code(tmp_path, code):
    probe = tmp_path / "exit.py"
    probe.write_text("import sys; raise SystemExit(int(sys.argv[1]))\n", encoding="utf-8")
    command = health.serialize_powershell_hook_command([sys.executable, "-I", "-B", str(probe), str(code)])
    shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    result = subprocess.run([str(shell), "-NoProfile", "-NonInteractive", "-Command", command], capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == code, result.stderr

@pytest.mark.skipif(os.name != "nt", reason="native PowerShell invocation failure")
def test_missing_process_does_not_inherit_a_stale_success(tmp_path):
    command = health.serialize_powershell_hook_command([str(tmp_path / "absent.exe")])
    shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    result = subprocess.run([str(shell), "-NoProfile", "-NonInteractive", "-Command", "$LASTEXITCODE = 0; " + command], capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode != 0
