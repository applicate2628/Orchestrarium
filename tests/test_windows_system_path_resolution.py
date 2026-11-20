import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import bash_runtime as bash
spec = importlib.util.spec_from_file_location("health", Path(__file__).resolve().parents[1] / "scripts/check-hook-health.py")
health = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = health
spec.loader.exec_module(health)
class PathTests(unittest.TestCase):
    def test_actual_windows_root_without_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "windows-on-other-volume"
            with patch.dict(os.environ, {}, clear=True), patch.object(bash, "_system_windows_directory", return_value=str(root), create=True):
                self.assertTrue(bash._is_windows_wsl_bash(root / "System32/bash.exe"))
                self.assertFalse(bash._is_windows_wsl_bash(Path(tmp) / "Git/bin/bash.exe"))
    def test_cmd_fallback_and_explicit_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            codex = folder / "codex.cmd"; codex.touch()
            system = folder / "System32"; system.mkdir()
            cmd = system / "cmd.exe"; cmd.touch()
            override = folder / "custom.exe"; override.touch()
            with patch.object(health, "os", SimpleNamespace(name="nt", environ={})), patch.object(health.shutil, "which", return_value=str(codex)), patch.object(health, "_system_command_processor", return_value=cmd, create=True):
                self.assertEqual(health.resolve_codex_command("codex")[0], str(cmd.resolve()))
                health.os.environ["COMSPEC"] = str(override)
                self.assertEqual(health.resolve_codex_command("codex")[0], str(override.resolve()))
    def test_missing_system_processor_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex = Path(tmp) / "codex.bat"
            codex.touch()
            with patch.object(health, "os", SimpleNamespace(name="nt", environ={})), patch.object(health.shutil, "which", return_value=str(codex)), patch.object(health, "_system_command_processor", return_value=None):
                with self.assertRaisesRegex(ValueError, "command processor is unavailable"):
                    health.resolve_codex_command("codex")
    def test_windowsapps_still_rejected(self):
        self.assertTrue(bash._is_windows_wsl_bash(Path("Microsoft/WindowsApps/bash.exe")))
    def test_failed_windows_lookup_does_not_manufacture_a_default(self):
        import ctypes
        kernel = SimpleNamespace(GetSystemDirectoryW=lambda *_: 0, GetSystemWindowsDirectoryW=lambda *args: args[1])
        with patch.object(ctypes, "windll", SimpleNamespace(kernel32=kernel), create=True), patch.object(bash, "os", SimpleNamespace(name="nt")):
            self.assertIsNone(health._system_command_processor())
            self.assertIsNone(bash._system_windows_directory())

    def test_resolve_bash_refuses_candidates_without_windows_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "System32/bash.exe"
            candidate.parent.mkdir()
            candidate.touch()
            with patch.object(bash, "os", SimpleNamespace(name="nt", environ={})), patch.object(bash, "_system_windows_directory", return_value=None), patch.object(bash.shutil, "which", return_value=None), patch.object(bash, "_path_applications", return_value=[candidate]):
                self.assertIsNone(bash.resolve_bash())
