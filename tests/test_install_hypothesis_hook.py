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


def run_installer(target: Path, *extra: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable,
        str(HOOK_INSTALLER),
        "--target",
        str(target),
        "--platform",
        "claude",
        "--script-path",
        SCRIPT_PATH,
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

    def test_install_into_empty(self) -> None:
        result = run_installer(self.target)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = load_json(self.target)
        pretool = data["hooks"]["PreToolUse"]
        self.assertEqual(len(pretool), 1)
        cmd = pretool[0]["hooks"][0]["command"]
        self.assertIn("check-hypothesis-disclosure", cmd)
        self.assertIn("bash", cmd)

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
        self.assertIn("check-hypothesis-disclosure", data["hooks"]["PreToolUse"][1]["hooks"][0]["command"])
        self.assertEqual(data["hooks"]["Stop"], [{"hooks": [{"type": "command", "command": "echo stop"}]}])

    def test_duplicates_collapsed_on_install(self) -> None:
        # Simulate an earlier buggy install that left two of our entries.
        cmd = f"bash {SCRIPT_PATH}"
        self.target.write_text(json.dumps({
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": cmd}]},
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": cmd + " # duplicate"}]},
                ]
            }
        }, indent=2), encoding="utf-8")
        result = run_installer(self.target)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = load_json(self.target)
        self.assertEqual(len(data["hooks"]["PreToolUse"]), 1)

    def test_duplicates_all_removed_on_uninstall(self) -> None:
        cmd = f"bash {SCRIPT_PATH}"
        self.target.write_text(json.dumps({
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": cmd}]},
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": cmd + " # dup"}]},
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

    def test_command_injection_via_unquoted_path_is_blocked(self) -> None:
        # The architecture/security reviews demonstrated this with
        # '/tmp/safe path; echo PWNED'. After fix: shlex-quoted into JSON.
        malicious = "/tmp/safe path; echo PWNED"
        cmd = [
            sys.executable, str(HOOK_INSTALLER),
            "--target", str(self.target),
            "--platform", "claude",
            "--script-path", malicious,
        ]
        env = os.environ.copy()
        env.pop("ORCHESTRARIUM_NO_HYPOTHESIS_HOOK", None)
        subprocess.run(cmd, check=True, env=env, capture_output=True, text=True)
        data = load_json(self.target)
        recorded = data["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        # The command-injection chars must be inside single-quotes (shlex.quote).
        # Bash treats `'...; echo PWNED'` as a single literal argument to `bash`,
        # not as a shell metacharacter chain.
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


if __name__ == "__main__":
    unittest.main()
