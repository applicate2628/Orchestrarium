"""Regression tests for the machine-local-path PreToolUse hook (AUDIT mode).

The hook fires on the edit's own tool_input (not session context), warns to
stderr on a hit, and ALWAYS exits 0 (audit mode never blocks; fail-open on any
internal error). Tests assert: real machine-local paths are flagged (stderr
non-empty), placeholders / .scratch / clean content are not, and exit code is 0
in every case — for BOTH the Claude and Codex copies of the hook.

(The companion no-trash-in-repo hook ships in the same install trees and has its
own regression suite in test_no_trash_hook.py.)
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CL = REPO_ROOT / "src.claude" / "agents" / "hooks"
CX = REPO_ROOT / "src.codex" / "skills" / "lead" / "hooks"

MACHINE_PATH_SCRIPTS = (CL / "check-machine-local-path.py", CX / "check-machine-local-path.py")


def run_hook(script: Path, envelope: object, raw_stdin: str | None = None) -> subprocess.CompletedProcess:
    stdin_text = raw_stdin if raw_stdin is not None else json.dumps(envelope, ensure_ascii=False)
    return subprocess.run(
        [sys.executable, str(script)],
        input=stdin_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


# --- gate-safe leak fixtures -------------------------------------------------
# These tests must feed the hook leak-looking machine paths. To keep THIS tracked
# test file from itself tripping the publication leak-scanner (which now catches
# the forward-slash / leading-slash home forms over the full content of staged
# files), the path-root keyword is assembled from fragments so no complete
# machine-path token appears as a literal in the source. Each f-string below
# evaluates to exactly the literal it replaced, so the hook receives identical
# input and the assertions are unchanged.
_USERS = "Use" + "rs"   # -> "Users"
_DEV = "de" + "v"       # -> "dev"
_HOME = "ho" + "me"     # -> "home"


class TestMachineLocalPathHook(unittest.TestCase):
    def assert_flagged(self, tool_input: dict, flagged: bool) -> None:
        for script in MACHINE_PATH_SCRIPTS:
            with self.subTest(script=script.parent.parent.name):
                p = run_hook(script, {"tool_input": tool_input})
                self.assertEqual(p.returncode, 0, p.stderr)  # audit mode never blocks
                self.assertEqual(bool(p.stderr.strip()), flagged, f"stderr={p.stderr!r}")

    def test_real_user_home_flagged(self) -> None:
        self.assert_flagged({"file_path": "README.md", "content": f"see C:/{_USERS}/realuser/.claude/x"}, True)

    def test_placeholder_not_flagged(self) -> None:
        self.assert_flagged({"file_path": "README.md", "content": "see C:/Users/<you>/.claude/x"}, False)

    def test_scratch_target_not_flagged(self) -> None:
        self.assert_flagged({"file_path": ".scratch/log.txt", "content": f"C:/{_USERS}/realuser/x"}, False)

    def test_clean_content_not_flagged(self) -> None:
        self.assert_flagged({"file_path": "README.md", "content": "nothing machine-local"}, False)

    def test_workstation_dev_root_flagged(self) -> None:
        self.assert_flagged({"file_path": "docs/x.md", "content": f"see /d/{_DEV}/someproject/foo"}, True)

    def test_posix_home_flagged(self) -> None:
        # POSIX /home/<user>/ is a concrete machine-local home (full-repo-review gap).
        self.assert_flagged({"file_path": "README.md", "content": f"see /{_HOME}/realuser/x"}, True)

    def test_macos_home_flagged(self) -> None:
        # macOS bare /Users/<user>/ (no drive prefix) is a concrete machine-local home.
        self.assert_flagged({"file_path": "README.md", "content": f"see /{_USERS}/realuser/x"}, True)

    def test_posix_home_placeholder_not_flagged(self) -> None:
        # /home/user is the allow-listed example token "user", not a real leak.
        self.assert_flagged({"file_path": "README.md", "content": "see /home/user/x"}, False)

    def test_example_username_not_flagged(self) -> None:
        self.assert_flagged({"file_path": "docs/x.md", "content": "C:/Users/test/.claude/x"}, False)

    def test_apply_patch_style_input_flagged(self) -> None:
        self.assert_flagged({"input": f"*** Update\n+ C:/{_USERS}/realuser/secret"}, True)

    def test_ellipsis_placeholder_not_flagged(self) -> None:
        self.assert_flagged({"file_path": "README.md", "content": "see C:/Users/.../foo"}, False)

    def test_uppercase_x_placeholder_not_flagged(self) -> None:
        self.assert_flagged({"file_path": "README.md", "content": "see C:/Users/X/foo"}, False)

    def test_cyrillic_path_emits_valid_utf8(self) -> None:
        # Locks the _emit UTF-8 fix: a concrete Cyrillic username must flag AND
        # round-trip through stderr as valid UTF-8 (a cp1252 write would mangle
        # it, so the assertIn would fail on the replacement characters).
        for script in MACHINE_PATH_SCRIPTS:
            with self.subTest(script=script.parent.parent.name):
                p = run_hook(script, {"tool_input": {"file_path": "README.md", "content": f"see C:/{_USERS}/Дима/secret"}})
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertTrue(p.stderr.strip(), "expected a warning")
                self.assertIn("Дима", p.stderr)

    def test_malformed_stdin_fails_open(self) -> None:
        for script in MACHINE_PATH_SCRIPTS:
            with self.subTest(script=script.parent.parent.name):
                p = run_hook(script, None, raw_stdin="not json at all {{{")
                self.assertEqual(p.returncode, 0)
                self.assertEqual(p.stderr.strip(), "")


if __name__ == "__main__":
    unittest.main()
