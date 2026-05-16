"""Regression tests for scripts/install-hypothesis-hook.py.

Covers the cases listed in the architecture review of commit 79aa5eb:
  - install into empty file / non-existent file
  - idempotent re-install
  - preservation of user-owned keys and other hooks
  - duplicate marker entries are collapsed on install / removed on uninstall
  - --remove cleans only our entry; opt-out env var does NOT block --remove
  - ORCHESTRARIUM_NO_HYPOTHESIS_HOOK blocks install but NOT remove
  - shlex-quoted script paths defend against command injection
  - malformed-but-valid JSON (non-list entry["hooks"]) is handled without crash
  - symlink target is refused
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_INSTALLER = REPO_ROOT / "scripts" / "install-hypothesis-hook.py"
SCRIPT_PATH = "/tmp/check-hypothesis-disclosure.sh"


def run_installer(
    target: Path,
    *extra: str,
    platform: str = "claude",
    host_os: str = "posix",
    script_path: str = SCRIPT_PATH,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable,
        str(HOOK_INSTALLER),
        "--target",
        str(target),
        "--platform",
        platform,
        "--host-os",
        host_os,
        "--script-path",
        script_path,
        *extra,
    ]
    full_env = os.environ.copy()
    full_env.pop("ORCHESTRARIUM_NO_HYPOTHESIS_HOOK", None)
    if env:
        full_env.update(env)
    return subprocess.run(cmd, capture_output=True, text=True, env=full_env)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class TestInstallHypothesisHook(unittest.TestCase):

    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp(prefix="orch-hook-test-"))
        self.target = self.tmpdir / "settings.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_install_into_empty_posix_claude_exec_form(self) -> None:
        result = run_installer(self.target)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = load_json(self.target)
        pretool = data["hooks"]["PreToolUse"]
        self.assertEqual(len(pretool), 1)
        hook = pretool[0]["hooks"][0]
        # Claude POSIX = exec form (args array, no shell interpretation)
        self.assertEqual(hook["command"], "bash")
        self.assertEqual(hook["args"], [SCRIPT_PATH])
        self.assertEqual(hook["if"], "Bash(git push *)")

    def test_install_claude_windows_powershell_exec_form(self) -> None:
        ps1_path = "C:\\Users\\test\\.claude\\agents\\scripts\\check-hypothesis-disclosure.ps1"
        result = run_installer(self.target, host_os="windows", script_path=ps1_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = load_json(self.target)
        hook = data["hooks"]["PreToolUse"][0]["hooks"][0]
        # Windows-native PowerShell exec form
        self.assertEqual(hook["command"], "powershell")
        self.assertEqual(hook["args"][:4], ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File"])
        self.assertEqual(hook["args"][4], ps1_path)
        self.assertNotIn("bash", hook["command"])

    def test_install_codex_posix_shell_form(self) -> None:
        result = run_installer(self.target, platform="codex")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = load_json(self.target)
        hook = data["hooks"]["PreToolUse"][0]["hooks"][0]
        # Codex always shell form (no `args` field supported)
        self.assertNotIn("args", hook)
        self.assertIn("bash", hook["command"])
        self.assertIn(SCRIPT_PATH, hook["command"])

    def test_codex_windows_is_skipped_with_warn(self) -> None:
        # Codex+Windows is an unsupported lane (Codex's Windows hook
        # execution path is not documented). The helper must exit 0 with
        # a WARN on stderr and NOT write to the target file.
        ps1_path = "C:\\Users\\test\\.codex\\skills\\lead\\scripts\\check-hypothesis-disclosure.ps1"
        result = run_installer(self.target, platform="codex", host_os="windows", script_path=ps1_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SKIP", result.stderr)
        self.assertIn("Codex", result.stderr)
        self.assertIn("Windows", result.stderr)
        self.assertFalse(self.target.exists(), "Codex+Windows must NOT write to hooks.json")

    def test_codex_windows_remove_still_works(self) -> None:
        # Even though install is skipped on Codex+Windows, removal of a
        # previously-installed entry must still work — a user might have
        # installed when their Codex Windows lane was supported, then
        # upgraded to a version that skips Windows; --remove should still
        # clean up the legacy entry.
        existing_cmd = f"bash {SCRIPT_PATH}"
        self.target.write_text(json.dumps({
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": existing_cmd}]},
                ]
            }
        }, indent=2), encoding="utf-8")
        result = run_installer(self.target, "--remove", platform="codex", host_os="windows")
        self.assertEqual(result.returncode, 0, result.stderr)
        # File should be deleted (removal emptied it).
        self.assertFalse(self.target.exists())

    def test_idempotent_reinstall(self) -> None:
        run_installer(self.target)
        before = self.target.read_bytes()
        result = run_installer(self.target)
        self.assertEqual(result.returncode, 0)
        self.assertIn("no-op", result.stdout)
        after = self.target.read_bytes()
        self.assertEqual(before, after)

    def test_preserves_user_keys_and_other_hooks(self) -> None:
        self.target.write_text(json.dumps({
            "model": "opus",
            "theme": "dark",
            "permissions": {"allow": ["Bash"]},
            "hooks": {
                "PreToolUse": [{
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": "echo user-other-hook"}],
                }],
                "Stop": [{"hooks": [{"type": "command", "command": "echo stop"}]}],
            },
        }, indent=2), encoding="utf-8")
        result = run_installer(self.target)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = load_json(self.target)
        self.assertEqual(data["model"], "opus")
        self.assertEqual(data["theme"], "dark")
        self.assertEqual(data["permissions"], {"allow": ["Bash"]})
        self.assertEqual(len(data["hooks"]["PreToolUse"]), 2)
        self.assertEqual(data["hooks"]["PreToolUse"][0]["hooks"][0]["command"], "echo user-other-hook")
        our_hook = data["hooks"]["PreToolUse"][1]["hooks"][0]
        # Exec form: marker lives in args[0], not in command.
        self.assertEqual(our_hook["command"], "bash")
        self.assertIn("check-hypothesis-disclosure", our_hook["args"][0])
        self.assertEqual(data["hooks"]["Stop"], [{"hooks": [{"type": "command", "command": "echo stop"}]}])

    def test_duplicates_collapsed_on_install(self) -> None:
        # Simulate two old-style shell-form entries (older buggy install).
        # The marker substring `check-hypothesis-disclosure` is what identifies
        # our entries regardless of form (shell or exec), so duplicates are
        # collapsed even if one is shell form and one is exec form.
        old_cmd = f"bash {SCRIPT_PATH}"
        self.target.write_text(json.dumps({
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": old_cmd}]},
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": old_cmd + " # duplicate"}]},
                ]
            }
        }, indent=2), encoding="utf-8")
        result = run_installer(self.target)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = load_json(self.target)
        self.assertEqual(len(data["hooks"]["PreToolUse"]), 1)
        # After collapse, the remaining entry uses the new exec form.
        hook = data["hooks"]["PreToolUse"][0]["hooks"][0]
        self.assertEqual(hook["command"], "bash")
        self.assertEqual(hook["args"], [SCRIPT_PATH])

    def test_duplicates_all_removed_on_uninstall(self) -> None:
        # Old-style shell-form entries are still recognized by marker substring
        # and removed cleanly even when the current install would use exec form.
        old_cmd = f"bash {SCRIPT_PATH}"
        self.target.write_text(json.dumps({
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": old_cmd}]},
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": old_cmd + " # dup"}]},
                ]
            }
        }, indent=2), encoding="utf-8")
        result = run_installer(self.target, "--remove")
        self.assertEqual(result.returncode, 0)
        self.assertFalse(self.target.exists(), "file should be deleted when removal empties it")

    def test_opt_out_env_var_blocks_install(self) -> None:
        result = run_installer(self.target, env={"ORCHESTRARIUM_NO_HYPOTHESIS_HOOK": "1"})
        self.assertEqual(result.returncode, 0)
        self.assertIn("SKIP", result.stderr)
        self.assertFalse(self.target.exists())

    def test_opt_out_env_var_does_not_block_remove(self) -> None:
        # Install first, then try to remove with the env var set.
        run_installer(self.target)
        self.assertTrue(self.target.exists())
        result = run_installer(
            self.target, "--remove", env={"ORCHESTRARIUM_NO_HYPOTHESIS_HOOK": "1"}
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.target.exists(), "remove should succeed despite opt-out env var")

    def test_command_injection_via_unquoted_path_is_blocked_claude(self) -> None:
        # The architecture/security reviews demonstrated this with
        # '/tmp/safe path; echo PWNED'. After fix: Claude uses EXEC form
        # (args array, no shell), so the malicious string is passed as a
        # single literal argument with zero shell interpretation possible.
        malicious = "/tmp/safe path; echo PWNED"
        result = run_installer(self.target, script_path=malicious)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = load_json(self.target)
        hook = data["hooks"]["PreToolUse"][0]["hooks"][0]
        # Exec form: command="bash", args contains the raw malicious path as
        # a single argv element. No shell metacharacter interpretation.
        self.assertEqual(hook["command"], "bash")
        self.assertEqual(hook["args"], [malicious])
        # The dangerous metacharacters must NOT appear in a shell-interpreted
        # `command` string anywhere.
        self.assertNotIn("; echo PWNED", hook["command"])

    def test_command_injection_via_unquoted_path_is_blocked_codex(self) -> None:
        # Codex shell form: shlex.quote() defends since Codex doesn't support
        # exec form. Verify the persisted shell-form command contains the
        # malicious chars only inside POSIX single-quotes.
        malicious = "/tmp/safe path; echo PWNED"
        result = run_installer(self.target, platform="codex", script_path=malicious)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = load_json(self.target)
        recorded = data["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        # shlex.quote wraps it in single-quotes so bash treats it as a single
        # literal argument, not a shell metacharacter chain.
        self.assertIn("'", recorded, f"expected shlex quoting, got: {recorded}")
        self.assertNotRegex(
            recorded, r"^bash /tmp/safe path; echo PWNED$",
            "raw injection-vulnerable form must not be present"
        )

    def test_malformed_hooks_value_does_not_crash(self) -> None:
        # An entry whose "hooks" is not a list should be skipped, not crash.
        self.target.write_text(json.dumps({
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": 5},  # malformed but valid JSON
                ]
            }
        }, indent=2), encoding="utf-8")
        result = run_installer(self.target)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = load_json(self.target)
        # Our entry should have been appended despite the malformed neighbour.
        self.assertEqual(len(data["hooks"]["PreToolUse"]), 2)

    def test_symlink_target_is_refused(self) -> None:
        if os.name == "nt":
            # Creating a symlink on Windows requires SeCreateSymbolicLinkPrivilege
            # or developer mode. Skip on Windows CI.
            self.skipTest("symlink test requires elevated privileges on Windows")
        real = self.tmpdir / "real-settings.json"
        real.write_text("{}", encoding="utf-8")
        link = self.tmpdir / "settings-link.json"
        os.symlink(real, link)
        result = run_installer(link)
        self.assertNotEqual(result.returncode, 0, "symlink write should be refused")
        self.assertIn("symbolic link", result.stderr.lower())

    def test_hooks_top_level_not_a_dict_fails_closed(self) -> None:
        self.target.write_text(json.dumps({"hooks": "not-a-dict"}), encoding="utf-8")
        result = run_installer(self.target)
        self.assertEqual(result.returncode, 1)
        self.assertIn("hooks", result.stderr.lower())

    def test_invalid_json_fails_closed(self) -> None:
        self.target.write_text("this is not json", encoding="utf-8")
        result = run_installer(self.target)
        self.assertEqual(result.returncode, 1)
        self.assertIn("json", result.stderr.lower())

    def test_codex_windows_skip_does_not_load_target_file(self) -> None:
        # Regression for arch-review-4 finding: on Codex+Windows the helper
        # must exit BEFORE doing any file I/O so a missing/unreadable target
        # path or invalid JSON in target does not cause a false failure.
        # Use a deliberately bogus target path that would fail if the helper
        # tried to read or write it.
        bogus = self.tmpdir / "nonexistent-subdir-that-should-not-be-created" / "hooks.json"
        ps1_path = "C:\\Users\\test\\.codex\\skills\\lead\\scripts\\check-hypothesis-disclosure.ps1"
        result = subprocess.run(
            [
                sys.executable,
                str(HOOK_INSTALLER),
                "--target",
                str(bogus),
                "--platform",
                "codex",
                "--host-os",
                "windows",
                "--script-path",
                ps1_path,
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "ORCHESTRARIUM_NO_HYPOTHESIS_HOOK": ""},
        )
        # Must exit 0 with SKIP and must NOT create the directory or the file
        # (proves the skip happens before any FS write).
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SKIP", result.stderr)
        self.assertFalse(bogus.parent.exists(), "skip must not create directories")
        self.assertFalse(bogus.exists(), "skip must not create the target file")
        self.assertIn("json", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
