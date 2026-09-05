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
  - symlink target is written through (link preserved, real target updated)
"""

from __future__ import annotations

import json
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path, PureWindowsPath

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_INSTALLER = REPO_ROOT / "scripts" / "install-hypothesis-hook.py"
PY_SCRIPT_PATH = REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "check-bugfix-discipline.py"
SCRIPT_PATH = str(PY_SCRIPT_PATH)
STOP_PY_SCRIPT_PATH = (
    REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "check-passive-polling-stop.py"
)
STOP_SCRIPT_PATH = str(STOP_PY_SCRIPT_PATH)
REMINDER_PY_SCRIPT_PATH = (
    REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "mcp-usage-reminder.py"
)
REMINDER_SCRIPT_PATH = str(REMINDER_PY_SCRIPT_PATH)

SPEC = importlib.util.spec_from_file_location("install_hypothesis_hook", HOOK_INSTALLER)
assert SPEC and SPEC.loader
HOOK_MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = HOOK_MODULE
SPEC.loader.exec_module(HOOK_MODULE)


def run_installer(
    target: Path,
    *extra: str,
    platform: str = "claude",
    host_os: str = "posix",
    script_path: str = str(PY_SCRIPT_PATH),
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
    ]
    cmd.extend(extra)
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
        # Claude POSIX = direct exec form (args array, no shell interpretation).
        self.assertEqual(Path(hook["command"]), Path(sys.executable))
        self.assertEqual(hook["args"], [str(PY_SCRIPT_PATH.resolve())])
        # Matcher fires on code-mutating tool calls (script self-filters on
        # bug-context from session transcript). No `if` filter anymore — the
        # decision lives inside the script, not in the hook permission rule.
        self.assertEqual(data["hooks"]["PreToolUse"][0]["matcher"], "Edit|Write|NotebookEdit|apply_patch")
        self.assertNotIn("if", hook)

    @unittest.skipUnless(os.name == "nt", "requires a native Windows Python executable")
    def test_install_claude_windows_python_exec_form(self) -> None:
        result = run_installer(
            self.target,
            host_os="windows",
            script_path=str(PY_SCRIPT_PATH),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = load_json(self.target)
        hook = data["hooks"]["PreToolUse"][0]["hooks"][0]
        self.assertEqual(Path(hook["command"]), Path(sys.executable))
        self.assertEqual(hook["args"], [str(PY_SCRIPT_PATH.resolve())])
        self.assertNotIn("bash", hook["command"])
        self.assertNotIn("powershell", hook["command"].casefold())
        self.assertNotIn("if", hook)

    def test_install_with_custom_tool_matcher(self) -> None:
        # --tool-matcher overrides the default regex for a hook that must fire
        # on a different tool set (e.g. a Bash/shell-command guard such as the
        # no-trash-in-repo hook). The default path (no --tool-matcher) stays
        # "Edit|Write|NotebookEdit|apply_patch" — covered by the empty-install
        # test above — so existing hooks are unaffected by this new option.
        result = run_installer(
            self.target,
            "--script-marker",
            "check-no-trash-in-repo",
            "--tool-matcher",
            "Bash",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = load_json(self.target)
        self.assertEqual(data["hooks"]["PreToolUse"][0]["matcher"], "Bash")

    def test_custom_matcher_coexists_with_default_matcher_hook(self) -> None:
        # A custom-matcher hook and a default-matcher hook register as two
        # separate PreToolUse entries (idempotency keys on script-marker, not
        # matcher); the default entry keeps the shared regex unchanged.
        run_installer(self.target, "--script-marker", "check-bugfix-discipline")
        run_installer(
            self.target,
            "--script-marker",
            "check-no-trash-in-repo",
            "--tool-matcher",
            "Bash",
        )
        data = load_json(self.target)
        matchers = sorted(e["matcher"] for e in data["hooks"]["PreToolUse"])
        self.assertEqual(matchers, ["Bash", "Edit|Write|NotebookEdit|apply_patch"])

    def test_install_codex_posix_shell_form(self) -> None:
        result = run_installer(self.target, platform="codex")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = load_json(self.target)
        hook = data["hooks"]["PreToolUse"][0]["hooks"][0]
        # Codex always shell form (no `args` field supported)
        self.assertNotIn("args", hook)
        self.assertIn(Path(sys.executable).name, hook["command"])
        self.assertIn(SCRIPT_PATH, hook["command"])

    def test_install_generic_posix_exec_form(self) -> None:
        result = run_installer(self.target, platform="generic")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = load_json(self.target)
        entry = data["hooks"]["PreToolUse"][0]
        hook = entry["hooks"][0]
        self.assertEqual(entry["matcher"], "Edit|Write|NotebookEdit|apply_patch")
        self.assertEqual(Path(hook["command"]), Path(sys.executable))
        self.assertEqual(hook["args"], [str(PY_SCRIPT_PATH.resolve())])
        self.assertNotIn("if", hook)

    @unittest.skipUnless(os.name == "nt", "requires a native Windows Python executable")
    def test_codex_windows_writes_direct_python_entry(self) -> None:
        result = run_installer(
            self.target,
            platform="codex",
            host_os="windows",
            script_path=str(PY_SCRIPT_PATH),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.target.exists(), "Codex+Windows must write hooks.json entry")
        data = load_json(self.target)
        hook = data["hooks"]["PreToolUse"][0]["hooks"][0]
        self.assertNotIn("args", hook)
        self.assertIn(Path(sys.executable).name.casefold(), hook["command"].casefold())
        self.assertIn(".py", hook["command"].casefold())
        self.assertIn("check-bugfix-discipline", hook["command"])
        self.assertNotIn("powershell", hook["command"].casefold())
        self.assertNotIn(".ps1", hook["command"].casefold())

    @unittest.skipUnless(os.name == "nt", "requires a native Windows Python executable")
    def test_codex_windows_rejects_unsupported_unquoted_python_path(self) -> None:
        quoted_dir = self.tmpdir / "O'Brien"
        quoted_dir.mkdir()
        python_path = quoted_dir / "check-bugfix-discipline.py"
        python_path.write_text("", encoding="utf-8")
        result = run_installer(
            self.target,
            platform="codex",
            host_os="windows",
            script_path=str(python_path),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported Windows hook command token", result.stderr)

    def test_install_sessionstart_hook_entry_shape(self) -> None:
        result = run_installer(
            self.target,
            "--hook-event",
            "SessionStart",
            "--script-marker",
            "mcp-usage-reminder",
            script_path=REMINDER_SCRIPT_PATH,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = load_json(self.target)
        entries = data["hooks"]["SessionStart"]
        self.assertEqual(len(entries), 1)
        self.assertNotIn("matcher", entries[0])
        hook = entries[0]["hooks"][0]
        self.assertEqual(Path(hook["command"]), Path(sys.executable))
        self.assertEqual(hook["args"], [str(REMINDER_PY_SCRIPT_PATH.resolve())])
        self.assertIn("mcp-usage-reminder", hook["args"][0])

    def test_install_posttooluse_hook_uses_default_matcher_for_all_platforms(self) -> None:
        for platform in ("claude", "codex", "generic"):
            with self.subTest(platform=platform):
                target = self.tmpdir / f"{platform}-default.json"
                result = run_installer(
                    target,
                    "--hook-event",
                    "PostToolUse",
                    "--script-marker",
                    "posttooluse-default",
                    platform=platform,
                    script_path=REMINDER_SCRIPT_PATH,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                entries = load_json(target)["hooks"]["PostToolUse"]
                self.assertEqual(len(entries), 1)
                self.assertEqual(entries[0]["matcher"], "Edit|Write|NotebookEdit|apply_patch")
                hook = entries[0]["hooks"][0]
                if platform == "codex":
                    self.assertNotIn("args", hook)
                    self.assertIn("mcp-usage-reminder", hook["command"])
                else:
                    self.assertEqual(Path(hook["command"]), Path(sys.executable))
                    self.assertEqual(hook["args"], [str(REMINDER_PY_SCRIPT_PATH.resolve())])

    def test_install_posttooluse_hook_uses_custom_matcher_for_all_platforms(self) -> None:
        for platform in ("claude", "codex", "generic"):
            with self.subTest(platform=platform):
                target = self.tmpdir / f"{platform}-custom.json"
                result = run_installer(
                    target,
                    "--hook-event",
                    "PostToolUse",
                    "--script-marker",
                    "posttooluse-custom",
                    "--tool-matcher",
                    "Bash",
                    platform=platform,
                    script_path=REMINDER_SCRIPT_PATH,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                entries = load_json(target)["hooks"]["PostToolUse"]
                self.assertEqual(len(entries), 1)
                self.assertEqual(entries[0]["matcher"], "Bash")

    def test_codex_windows_remove_works(self) -> None:
        # Removal must work the same way on Codex+Windows as on POSIX.
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
        # Direct Python exec form: marker lives in args[0], not in command.
        self.assertEqual(Path(our_hook["command"]), Path(sys.executable))
        self.assertIn("check-bugfix-discipline", our_hook["args"][0])
        self.assertEqual(data["hooks"]["Stop"], [{"hooks": [{"type": "command", "command": "echo stop"}]}])

    def test_install_stop_hook_entry_shape(self) -> None:
        result = run_installer(
            self.target,
            "--hook-event",
            "Stop",
            "--script-marker",
            "check-passive-polling-stop",
            script_path=STOP_SCRIPT_PATH,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = load_json(self.target)
        stop_entries = data["hooks"]["Stop"]
        self.assertEqual(len(stop_entries), 1)
        self.assertNotIn("matcher", stop_entries[0])
        hook = stop_entries[0]["hooks"][0]
        self.assertEqual(Path(hook["command"]), Path(sys.executable))
        self.assertEqual(hook["args"], [str(STOP_PY_SCRIPT_PATH.resolve())])
        self.assertIn("check-passive-polling-stop", hook["args"][0])

    def test_both_hooks_installed_without_overwrite(self) -> None:
        first = run_installer(self.target)
        second = run_installer(
            self.target,
            "--hook-event",
            "Stop",
            "--script-marker",
            "check-passive-polling-stop",
            script_path=STOP_SCRIPT_PATH,
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        data = load_json(self.target)
        self.assertEqual(len(data["hooks"]["PreToolUse"]), 1)
        self.assertEqual(len(data["hooks"]["Stop"]), 1)
        pre_hook = data["hooks"]["PreToolUse"][0]["hooks"][0]
        stop_hook = data["hooks"]["Stop"][0]["hooks"][0]
        self.assertIn("check-bugfix-discipline", pre_hook["args"][0])
        self.assertIn("check-passive-polling-stop", stop_hook["args"][0])

    def test_remove_stop_hook_preserves_pretool_hook(self) -> None:
        run_installer(self.target)
        run_installer(
            self.target,
            "--hook-event",
            "Stop",
            "--script-marker",
            "check-passive-polling-stop",
            script_path=STOP_SCRIPT_PATH,
        )
        result = run_installer(
            self.target,
            "--remove",
            "--hook-event",
            "Stop",
            "--script-marker",
            "check-passive-polling-stop",
            script_path=STOP_SCRIPT_PATH,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = load_json(self.target)
        self.assertIn("PreToolUse", data["hooks"])
        self.assertNotIn("Stop", data["hooks"])
        self.assertIn(
            "check-bugfix-discipline",
            data["hooks"]["PreToolUse"][0]["hooks"][0]["args"][0],
        )

    def test_remove_pretool_hook_preserves_stop_hook(self) -> None:
        run_installer(self.target)
        run_installer(
            self.target,
            "--hook-event",
            "Stop",
            "--script-marker",
            "check-passive-polling-stop",
            script_path=STOP_SCRIPT_PATH,
        )
        result = run_installer(self.target, "--remove")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = load_json(self.target)
        self.assertIn("Stop", data["hooks"])
        self.assertNotIn("PreToolUse", data["hooks"])
        self.assertIn(
            "check-passive-polling-stop",
            data["hooks"]["Stop"][0]["hooks"][0]["args"][0],
        )

    def test_stop_hook_idempotent_reinstall(self) -> None:
        run_installer(
            self.target,
            "--hook-event",
            "Stop",
            "--script-marker",
            "check-passive-polling-stop",
            script_path=STOP_SCRIPT_PATH,
        )
        before = self.target.read_bytes()
        result = run_installer(
            self.target,
            "--hook-event",
            "Stop",
            "--script-marker",
            "check-passive-polling-stop",
            script_path=STOP_SCRIPT_PATH,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no-op", result.stdout)
        self.assertEqual(before, self.target.read_bytes())

    def test_duplicates_collapsed_on_install(self) -> None:
        # Simulate two old-style shell-form entries (older buggy install).
        # The marker substring `check-bugfix-discipline` is what identifies
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
        # After collapse, the remaining entry uses the direct Python form.
        hook = data["hooks"]["PreToolUse"][0]["hooks"][0]
        self.assertEqual(Path(hook["command"]), Path(sys.executable))
        self.assertEqual(hook["args"], [str(PY_SCRIPT_PATH.resolve())])

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
        hook = HOOK_MODULE.build_claude_entry(
            HOOK_MODULE.HookTarget("/usr/bin/bash", (malicious,))
        )["hooks"][0]
        # Exec form: command="bash", args contains the raw malicious path as
        # a single argv element. No shell metacharacter interpretation.
        self.assertEqual(hook["command"], "/usr/bin/bash")
        self.assertEqual(hook["args"], [malicious])
        # The dangerous metacharacters must NOT appear in a shell-interpreted
        # `command` string anywhere.
        self.assertNotIn("; echo PWNED", hook["command"])

    def test_command_injection_via_unquoted_path_is_blocked_codex(self) -> None:
        # Codex shell form: shlex.quote() defends since Codex doesn't support
        # exec form. Verify the persisted shell-form command contains the
        # malicious chars only inside POSIX single-quotes.
        malicious = "/tmp/safe path; echo PWNED"
        recorded = HOOK_MODULE.build_codex_entry(
            HOOK_MODULE.HookTarget("/usr/bin/bash", (malicious,)),
            "posix",
        )["hooks"][0]["command"]
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

    def test_symlink_target_is_written_through(self) -> None:
        # The installer writes THROUGH a symlink: it updates the link's real
        # target and preserves the link itself (a synced shared-env hooks.json is
        # commonly symlinked). os.replace runs on the resolved real path so the
        # link is not clobbered with a regular file.
        real = self.tmpdir / "real-settings.json"
        real.write_text("{}", encoding="utf-8")
        link = self.tmpdir / "settings-link.json"
        try:
            os.symlink(real, link)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation not permitted in this environment")
        result = run_installer(link)
        self.assertEqual(result.returncode, 0, result.stderr)
        # The link itself is preserved...
        self.assertTrue(link.is_symlink(), "symlink must be preserved, not clobbered")
        # ...and the hook was written through to the real target file.
        data = json.loads(real.read_text(encoding="utf-8"))
        self.assertIn("hooks", data)
        self.assertTrue(
            any(data["hooks"].values()), "hook entry must be written through to the real target"
        )

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

    @unittest.skipUnless(os.name == "nt", "requires a native Windows Python executable")
    def test_codex_windows_creates_parent_directory(self) -> None:
        # Codex+Windows now writes the entry like POSIX. Verify the helper
        # creates any missing parent directory for the target file.
        nested = self.tmpdir / "new-subdir" / "hooks.json"
        result = run_installer(
            nested,
            platform="codex",
            host_os="windows",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(nested.exists(), "Codex+Windows must write the entry to target")
        self.assertTrue(nested.parent.is_dir(), "parent directory must be created")

    def test_default_runtime_registers_absolute_python_target(self) -> None:
        result = run_installer(self.target)
        self.assertEqual(result.returncode, 0, result.stderr)
        hook = load_json(self.target)["hooks"]["PreToolUse"][0]["hooks"][0]
        self.assertEqual(Path(hook["command"]), Path(sys.executable))
        self.assertEqual(hook["args"], [str(PY_SCRIPT_PATH)])
        self.assertTrue(Path(hook["command"]).is_absolute())
        self.assertTrue(Path(hook["args"][0]).is_absolute())

    def test_no_registered_entry_invokes_an_interpreter_wrapper(self) -> None:
        forbidden = ("powershell.exe", "pwsh", ".ps1", "bash", ".sh")
        for platform in ("claude", "codex"):
            python_targets = [PY_SCRIPT_PATH]
            self.assertTrue(python_targets)
            for host_os in ("posix", "windows"):
                for python_target in python_targets:
                    with self.subTest(
                        platform=platform,
                        host_os=host_os,
                        target=python_target.name,
                    ):
                        if host_os == "windows" and os.name != "nt":
                            self.skipTest("requires a native Windows Python executable")
                        target = HOOK_MODULE.resolve_hook_target(
                            str(python_target),
                            host_os,
                            platform,
                            python_executable=sys.executable,
                        )
                        entry = (
                            HOOK_MODULE.build_claude_entry(target)
                            if platform == "claude"
                            else HOOK_MODULE.build_codex_entry(target, host_os)
                        )
                        serialized = json.dumps(entry).lower()
                        self.assertFalse(
                            any(token in serialized for token in forbidden),
                            serialized,
                        )
                        self.assertTrue(Path(target.executable).is_absolute())
                        self.assertEqual(len(target.args), 1)
                        self.assertTrue(Path(target.args[0]).is_absolute())
                        self.assertTrue(Path(target.args[0]).is_file())

    def test_direct_python_preflights_before_mutation(self) -> None:
        original = b'{\n  "sentinel": true\n}\n'
        self.target.write_bytes(original)
        installer = REPO_ROOT / "scripts" / "production_installer.py"
        text = installer.read_text(encoding="utf-8")
        self.assertLess(text.index('"--validate-only"'), text.index("for marker, script, event, matcher"))

        for platform in ("claude", "codex"):
            owned = [PY_SCRIPT_PATH]
            self.assertTrue(owned)
            missing = self.tmpdir / platform / "missing-last-owned-hook.py"
            for host_os in ("posix", "windows"):
                with self.subTest(platform=platform, host_os=host_os):
                    if host_os == "windows" and os.name != "nt":
                        self.skipTest("requires a native Windows Python executable")
                    candidates = [*owned, missing]
                    with self.assertRaisesRegex(ValueError, "hook Python target"):
                        tuple(
                            HOOK_MODULE.resolve_hook_target(
                                str(candidate),
                                host_os,
                            platform,
                                python_executable=sys.executable,
                            )
                            for candidate in candidates
                        )
                    self.assertEqual(self.target.read_bytes(), original)

    def test_registered_script_arg_is_absolute(self) -> None:
        target = HOOK_MODULE.resolve_hook_target(
            str(PY_SCRIPT_PATH),
            "windows" if os.name == "nt" else "posix",
            "claude",
            python_executable=sys.executable,
        )
        self.assertTrue(Path(target.executable).is_absolute())
        self.assertEqual(len(target.args), 1)
        self.assertTrue(Path(target.args[0]).is_absolute())

    @unittest.skipUnless(os.name == "posix", "POSIX interpreter admission boundary")
    def test_windows_route_rejects_posix_interpreter_without_mutation(self) -> None:
        original = b'{"user": true}\n'
        self.target.write_bytes(original)
        result = run_installer(self.target, platform="codex", host_os="windows")
        self.assertEqual(result.returncode, 1)
        self.assertIn("real .exe, not a shim", result.stderr)
        self.assertEqual(self.target.read_bytes(), original)

    @unittest.skipUnless(os.name == "posix", "POSIX virtual-environment alias")
    def test_posix_registration_preserves_the_selected_interpreter_alias(self) -> None:
        alias = self.tmpdir / "venv-python"
        alias.symlink_to(Path(sys.executable).resolve())
        target = HOOK_MODULE.resolve_hook_target(
            str(PY_SCRIPT_PATH), "posix", "claude", python_executable=str(alias)
        )
        self.assertEqual(target.executable, str(alias))
        self.assertTrue(alias.is_symlink())

    def test_missing_python_target_fails_before_registration_mutation(self) -> None:
        original = b'{\n  "user": true\n}\n'
        self.target.write_bytes(original)
        missing = self.tmpdir / "missing" / "check-bugfix-discipline.py"
        result = run_installer(
            self.target,
            script_path=str(missing),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("hook Python target", result.stderr)
        self.assertEqual(self.target.read_bytes(), original)

    def test_invalid_python_interpreter_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "hook executable"):
            HOOK_MODULE.resolve_hook_target(
                str(PY_SCRIPT_PATH),
                "windows",
                "claude",
                python_executable=str(self.tmpdir / "missing-python.exe"),
            )

    @unittest.skipUnless(os.name == "nt", "requires a native Windows Python executable")
    def test_windows_unquoted_shape_and_unsupported_path_rejection(self) -> None:
        target = HOOK_MODULE.resolve_hook_target(
            str(PY_SCRIPT_PATH),
            "windows",
            "codex",
            python_executable=sys.executable,
        )
        entry = HOOK_MODULE.build_codex_entry(target, "windows")
        command = entry["hooks"][0]["command"]
        # Pin the exact spelling the operator verified live under both cmd.exe
        # and PowerShell: two unquoted absolute tokens with forward separators.
        # Codex hashes entry content for trust, so this byte shape is what lets
        # a reinstall match the stored trusted_hash instead of raising a modal.
        expected = (
            f"{PureWindowsPath(sys.executable).as_posix()} "
            f"{PureWindowsPath(PY_SCRIPT_PATH).as_posix()}"
        )
        self.assertEqual(command, expected)
        self.assertNotIn("\\", command)
        self.assertNotIn('"', command)
        self.assertNotIn("'", command)

        spaced_dir = self.tmpdir / "contains space"
        spaced_dir.mkdir()
        spaced_target = spaced_dir / "check-bugfix-discipline.py"
        spaced_target.write_text("", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unsupported Windows"):
            HOOK_MODULE.resolve_hook_target(
                str(spaced_target),
                "windows",
                "codex",
                python_executable=sys.executable,
            )

    def test_hook_target_layers_are_separable(self) -> None:
        synthetic = HOOK_MODULE.HookTarget(
            str(self.tmpdir / "future-hook.exe"),
            ("--sentinel",),
        )
        claude = HOOK_MODULE.build_claude_entry(synthetic)
        codex = HOOK_MODULE.build_codex_entry(synthetic, "windows")
        self.assertEqual(claude["hooks"][0]["command"], synthetic.executable)
        self.assertEqual(claude["hooks"][0]["args"], ["--sentinel"])
        self.assertEqual(
            codex["hooks"][0]["command"],
            f"{synthetic.executable} --sentinel",
        )
        self.assertNotIn("python", json.dumps((claude, codex)).lower())

    @unittest.skipUnless(os.name == "nt", "requires a native Windows Python executable")
    def test_migration_collapses_wrapper_entry_to_target_entry(self) -> None:
        old_entry = {
            "matcher": "Edit|Write|NotebookEdit|apply_patch",
            "hooks": [{
                "type": "command",
                "command": (
                    "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                    "C:/retired/check-bugfix-discipline.ps1"
                ),
            }],
        }
        self.target.write_text(
            json.dumps({"hooks": {"PreToolUse": [old_entry, old_entry]}}, indent=2),
            encoding="utf-8",
        )
        result = run_installer(
            self.target,
            platform="codex",
            host_os="windows",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        entries = load_json(self.target)["hooks"]["PreToolUse"]
        self.assertEqual(len(entries), 1)
        command = entries[0]["hooks"][0]["command"].lower()
        self.assertNotIn("powershell", command)
        self.assertIn(".py", command)

    @unittest.skipUnless(os.name == "nt", "requires a native Windows Python executable")
    def test_codex_entry_order_is_stable(self) -> None:
        first = {
            "matcher": "Bash",
            "hooks": [{"type": "command", "command": "echo user-hook"}],
        }
        wrapper = {
            "matcher": "Edit|Write|NotebookEdit|apply_patch",
            "hooks": [{
                "type": "command",
                "command": (
                    "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
                    "C:/retired/check-bugfix-discipline.ps1"
                ),
            }],
        }
        last = {
            "matcher": "Read",
            "hooks": [{"type": "command", "command": "echo user-last"}],
        }
        self.target.write_text(
            json.dumps({"hooks": {"PreToolUse": [first, wrapper, last]}}, indent=2),
            encoding="utf-8",
        )
        result = run_installer(
            self.target,
            platform="codex",
            host_os="windows",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        entries = load_json(self.target)["hooks"]["PreToolUse"]
        self.assertEqual(entries[0], first)
        self.assertEqual(entries[2], last)
        self.assertIn("check-bugfix-discipline", entries[1]["hooks"][0]["command"])

if __name__ == "__main__":
    unittest.main()
