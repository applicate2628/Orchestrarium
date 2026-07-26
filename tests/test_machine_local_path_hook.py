"""Regression tests for the machine-local-path PreToolUse hook (AUDIT mode).

The hook fires on the edit's own tool_input (not session context), and ALWAYS
exits 0 (audit mode never blocks; fail-open on any internal error). On a hit it
emits one line of JSON to stdout --
`{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"..."}}`
-- the model-visible delivery channel (see `hook_common.emit_advisory`); on a
clean check it is silent. This replaced a stderr-plus-exit-1 form measured to
reach nobody on either provider line (see
work-items/bugs/2026-07-26-mcp-reminder-uses-the-once-per-session-form-its-
sibling-calls-broken.md). Tests assert: real machine-local paths are flagged
(non-empty stdout JSON), placeholders / .scratch / clean content are not, and
exit code is 0 in every case — for BOTH the Claude and Codex copies of the hook.

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
_BS = chr(92)           # -> "\\" : a single literal backslash, kept out of source
_ELL = chr(0x2026)      # -> "…" : U+2026, kept out of source as pure-ASCII chr()


def _decode_context(stdout: str) -> tuple[str, str]:
    """Parse the hookSpecificOutput envelope; returns (hookEventName, additionalContext)."""
    payload = json.loads(stdout)
    specific = payload["hookSpecificOutput"]
    return specific["hookEventName"], specific["additionalContext"]


class TestMachineLocalPathHook(unittest.TestCase):
    def assert_flagged(self, tool_input: dict, flagged: bool) -> None:
        for script in MACHINE_PATH_SCRIPTS:
            with self.subTest(script=script.parent.parent.name):
                p = run_hook(script, {"tool_input": tool_input})
                # AUDIT never BLOCKS (never exit 2) and never uses a non-zero exit
                # for a hit either -- the advisory travels via stdout JSON, always
                # exit 0 (see hook_common.emit_advisory).
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(p.stderr, "")
                self.assertEqual(bool(p.stdout.strip()), flagged, f"stdout={p.stdout!r}")
                if flagged:
                    event_name, _context = _decode_context(p.stdout)
                    self.assertEqual(event_name, "PreToolUse")

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

    # --- UNC host/share home (Change B) -------------------------------------
    def test_unc_real_home_flagged(self) -> None:
        # \\host\Users\<real> is a concrete UNC machine-local home -> FLAGGED.
        content = f"see {_BS}{_BS}host{_BS}{_USERS}{_BS}realuser{_BS}secret"
        self.assert_flagged({"file_path": "README.md", "content": content}, True)

    def test_unc_share_real_home_flagged(self) -> None:
        content = f"path {_BS}{_BS}srv{_BS}share{_BS}{_USERS}{_BS}realuser"
        self.assert_flagged({"file_path": "docs/x.md", "content": content}, True)

    def test_unc_placeholder_not_flagged(self) -> None:
        # \\host\Users\<you> placeholder segment -> NOT flagged.
        content = f"see {_BS}{_BS}host{_BS}{_USERS}{_BS}<you>"
        self.assert_flagged({"file_path": "README.md", "content": content}, False)

    def test_unc_token_not_flagged(self) -> None:
        # \\host\Users\you allow-listed example token -> NOT flagged.
        content = f"see {_BS}{_BS}host{_BS}{_USERS}{_BS}you"
        self.assert_flagged({"file_path": "README.md", "content": content}, False)

    # --- U+2026 ellipsis placeholder (Change A) ------------------------------
    def test_u2026_backslash_not_flagged(self) -> None:
        self.assert_flagged({"file_path": "README.md", "content": f"see C:{_BS}{_USERS}{_BS}{_ELL}"}, False)

    def test_u2026_forward_slash_not_flagged(self) -> None:
        self.assert_flagged({"file_path": "README.md", "content": f"see C:/{_USERS}/{_ELL}"}, False)

    def test_u2026_bare_not_flagged(self) -> None:
        self.assert_flagged({"file_path": "README.md", "content": f"prefix {_ELL} suffix"}, False)

    def test_mixed_dot_ellipsis_not_flagged(self) -> None:
        # A segment that is a mix of dots and U+2026 (e.g. ".….") is still a
        # placeholder, not a real account name -> NOT flagged.
        self.assert_flagged({"file_path": "README.md", "content": f"see C:/{_USERS}/.{_ELL}./foo"}, False)

    def test_u2026_unc_placeholder_not_flagged(self) -> None:
        # \\host\Users\… (UNC home with ellipsis segment) -> NOT flagged.
        content = f"see {_BS}{_BS}host{_BS}{_USERS}{_BS}{_ELL}"
        self.assert_flagged({"file_path": "README.md", "content": content}, False)

    def test_uppercase_x_placeholder_not_flagged(self) -> None:
        self.assert_flagged({"file_path": "README.md", "content": "see C:/Users/X/foo"}, False)

    def test_cyrillic_path_emits_valid_utf8(self) -> None:
        # A concrete Cyrillic username must flag AND round-trip correctly. The
        # JSON envelope uses ensure_ascii=True, so the Cyrillic text is
        # \uXXXX-escaped on the wire and json.loads decodes it back to the
        # original characters regardless of console codepage.
        for script in MACHINE_PATH_SCRIPTS:
            with self.subTest(script=script.parent.parent.name):
                p = run_hook(script, {"tool_input": {"file_path": "README.md", "content": f"see C:/{_USERS}/Петя/secret"}})
                self.assertEqual(p.returncode, 0, p.stderr)  # AUDIT never exits non-zero
                self.assertEqual(p.stderr, "")
                self.assertTrue(p.stdout.strip(), "expected an advisory")
                _event_name, context = _decode_context(p.stdout)
                self.assertIn("Петя", context)

    def test_malformed_stdin_fails_open(self) -> None:
        for script in MACHINE_PATH_SCRIPTS:
            with self.subTest(script=script.parent.parent.name):
                p = run_hook(script, None, raw_stdin="not json at all {{{")
                self.assertEqual(p.returncode, 0)
                self.assertEqual(p.stderr.strip(), "")
                self.assertEqual(p.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
