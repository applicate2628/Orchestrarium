"""Regression tests for the two anti-decay hooks added 2026-07-17.

Both target the operator's report that always-on postures decay: *"постоянно забывают
использовать mcp ... потом снова сваливаются после остановок"*. The split between them
is load-bearing and was corrected by first-person evidence mid-build (see the
`reminders-decay-by-surface` work-item):

  * `turn-anchor-reminder` (UserPromptSubmit) re-anchors TURN-BOUNDARY postures — "a
    passed slice is not completion" — at the start of every turn. It fires at turn start,
    so it CANNOT reach a mid-turn failure; that is by design, not a gap.
  * `check-mcp-momentum` (PreToolUse Grep|Bash, AUDIT) fires at the mid-turn TOOL CHOICE,
    the moment MCP momentum actually lapses (~100 successful shell calls, next tool picked
    from momentum not from a rule sitting in context). It nudges ONLY on code-navigation
    shapes, ONLY when a code-intelligence MCP is actually configured, and never blocks.

These were untested when shipped — the exact gap that let the `bugfix-discipline`
isCompactSummary false positive live undetected. The bar here is the one that FP taught:
exercise the real envelope, both the fire and the silence.
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

BASH = shutil.which("bash")

REPO_ROOT = Path(__file__).resolve().parent.parent
MCP_HOOK = REPO_ROOT / "scripts" / "universal-hooks" / "hooks" / "check-mcp-momentum.py"
TURN_ANCHOR_SH = REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "turn-anchor-reminder.sh"


def run_hook(script: Path, envelope: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(envelope, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


class TestMcpMomentumDiscrimination(unittest.TestCase):
    """AUDIT hook: it must ALWAYS exit 0, and it must warn on exactly the navigation
    shapes and stay silent on everything else. A nudge that fires on every read is noise,
    and noise trains the reader to ignore the whole class."""

    def setUp(self) -> None:
        # The hook only nudges when a code-intelligence MCP is actually configured for
        # this user. Point it at a synthetic config so the test does not depend on the
        # developer's real ~/.claude.json (which may or may not have one).
        self._home = tempfile.mkdtemp()
        (Path(self._home) / ".claude.json").write_text(
            json.dumps({"mcpServers": {"codegraph": {}, "serena": {}, "time": {}}}),
            encoding="utf-8",
        )
        self._env = dict(os.environ)
        self._env["HOME"] = self._home
        self._env["USERPROFILE"] = self._home

    def _run(self, envelope: dict) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(MCP_HOOK)],
            input=json.dumps(envelope, ensure_ascii=False),
            capture_output=True, text=True, encoding="utf-8", env=self._env,
        )

    def assert_nudges(self, envelope: dict, should_nudge: bool) -> None:
        result = self._run(envelope)
        self.assertEqual(result.returncode, 0, "AUDIT hook must always exit 0")
        fired = "mcp-momentum" in result.stderr
        self.assertEqual(fired, should_nudge, result.stderr or "(no stderr)")

    def test_grep_for_a_definition_nudges(self) -> None:
        self.assert_nudges({"tool_name": "Grep", "tool_input": {"pattern": "def parse_config"}}, True)

    def test_grep_by_code_type_nudges(self) -> None:
        self.assert_nudges({"tool_name": "Grep", "tool_input": {"pattern": "handler", "type": "py"}}, True)

    def test_shell_recursive_grep_over_source_nudges(self) -> None:
        self.assert_nudges(
            {"tool_name": "Bash", "tool_input": {"command": "grep -rn 'class Foo' src/ --include=*.py"}},
            True,
        )

    def test_targeted_read_of_a_known_file_stays_silent(self) -> None:
        # A plain-word content search in one file is not a symbol hunt.
        self.assert_nudges({"tool_name": "Grep", "tool_input": {"pattern": "TODO", "path": "README.md"}}, False)

    def test_pytest_run_stays_silent(self) -> None:
        self.assert_nudges({"tool_name": "Bash", "tool_input": {"command": "python -m pytest tests/ -q"}}, False)

    def test_docs_prose_grep_stays_silent(self) -> None:
        self.assert_nudges({"tool_name": "Bash", "tool_input": {"command": "grep -rn 'installation' docs/"}}, False)

    def test_dispatched_subagent_is_never_nudged(self) -> None:
        # A subagent runs its own tool policy; the nudge is for the orchestrating session.
        self.assert_nudges(
            {"agent_id": "sub-1", "tool_name": "Grep", "tool_input": {"pattern": "def parse_config"}},
            False,
        )

    def test_no_code_intel_server_configured_stays_silent(self) -> None:
        # A nudge on a machine without a code-intelligence MCP would be a lie.
        home = tempfile.mkdtemp()
        (Path(home) / ".claude.json").write_text(
            json.dumps({"mcpServers": {"time": {}, "fetch": {}}}), encoding="utf-8"
        )
        env = dict(os.environ); env["HOME"] = home; env["USERPROFILE"] = home
        result = subprocess.run(
            [sys.executable, str(MCP_HOOK)],
            input=json.dumps({"tool_name": "Grep", "tool_input": {"pattern": "def parse_config"}}),
            capture_output=True, text=True, encoding="utf-8", env=env,
        )
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("mcp-momentum", result.stderr)

    def test_malformed_envelope_fails_open(self) -> None:
        result = subprocess.run(
            [sys.executable, str(MCP_HOOK)],
            input="not json at all", capture_output=True, text=True, encoding="utf-8", env=self._env,
        )
        self.assertEqual(result.returncode, 0)


class TestTurnAnchorEmitsValidContext(unittest.TestCase):
    """The hook's whole job is to emit a UserPromptSubmit additionalContext payload every
    turn. If the JSON is malformed the harness drops it silently, so the payload shape is
    the contract."""

    @unittest.skipUnless(BASH, "no bash on PATH; the .ps1 sibling covers Windows shells")
    def test_sh_emits_wellformed_userpromptsubmit_context(self) -> None:
        result = subprocess.run(
            [BASH, str(TURN_ANCHOR_SH)],
            input="", capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, "must fail open / exit 0")
        payload = json.loads(result.stdout)
        out = payload["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "UserPromptSubmit")
        # The anchor's load-bearing sentence must actually be present.
        self.assertIn("passed slice is not completion", out["additionalContext"])
        self.assertIn("next unchecked action", out["additionalContext"])


if __name__ == "__main__":
    unittest.main()
