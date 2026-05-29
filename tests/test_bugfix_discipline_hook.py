"""Regression tests for the bugfix-discipline PreToolUse hook's genuine-user
detection (Task 8 false-positive fix).

The hook used to match bug-trigger phrases against the most recent role=user
transcript entry. In Claude Code, tool_result blocks and harness injections
(system-reminder, task-notification) are ALSO recorded as role=user, so a long
tool-heavy turn made the "last user message" a tool_result or notification full
of trigger words ("fix", "Error:", "broken") → the guard fired on legitimate
edits. The fix (last_genuine_user_message) skips tool_result / injected entries
and strips injected spans, so triggers match only the human's actual message.

These tests assert: (1) genuine bug reports still fire the guard; (2) trigger
words coming only from tool_result / system-reminder / task-notification do NOT
fire it; (3) a real bug report buried behind many tool_result entries is still
found (false-negative fix); (4) override marker and discipline-engaged turns
still allow. Run against BOTH the Claude and Codex copies of the hook.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS = (
    REPO_ROOT / "src.claude" / "agents" / "scripts" / "check-bugfix-discipline.py",
    REPO_ROOT / "src.codex" / "skills" / "lead" / "scripts" / "check-bugfix-discipline.py",
)


def user(text: str) -> dict:
    return {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}


def tool_result(text: str) -> dict:
    return {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": text}]}}


def assistant(text: str) -> dict:
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def codex_user(text: str) -> dict:
    # Codex rollout shape: the message is nested under `payload`, blocks are input_text.
    return {"type": "response_item", "payload": {"type": "message", "role": "user",
            "content": [{"type": "input_text", "text": text}]}}


def codex_function_call(name: str, arguments: str) -> dict:
    # Codex model tool call (the call the model makes, not its output).
    return {"type": "response_item", "payload": {"type": "function_call", "name": name, "arguments": arguments}}


def top_level_tool_output(text: str) -> dict:
    # A non-user, non-assistant tool-output entry whose text is read by the
    # extract_text top-level fallback (the override-bypass shape Codex found).
    return {"type": "function_call_output", "output": text}


def assistant_tool_use(name: str, input_obj: dict) -> dict:
    # An assistant entry whose only content is a tool_use block (e.g. an Edit
    # whose new_string contains the marker because it edits a doc about it).
    return {"type": "assistant", "message": {"role": "assistant",
            "content": [{"type": "tool_use", "name": name, "input": input_obj}]}}


def run_hook(script: Path, entries: list[dict], tool_name: str = "Edit") -> subprocess.CompletedProcess:
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
        transcript = f.name
    envelope = {"transcript_path": transcript, "tool_name": tool_name}
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(envelope, ensure_ascii=False),
        capture_output=True, text=True, encoding="utf-8",
    )


def denies(p: subprocess.CompletedProcess) -> bool:
    return '"permissionDecision"' in p.stdout and '"deny"' in p.stdout


class TestBugfixDisciplineGenuineUser(unittest.TestCase):
    def assert_outcome(self, entries: list[dict], should_deny: bool, tool_name: str = "Edit") -> None:
        for script in HOOKS:
            with self.subTest(script=script.parent.parent.name):
                p = run_hook(script, entries, tool_name)
                self.assertEqual(p.returncode, 0, p.stderr)  # hook always exits 0
                self.assertEqual(denies(p), should_deny, f"stdout={p.stdout!r}")

    def test_genuine_bug_report_fires(self) -> None:
        self.assert_outcome([user("the login page is broken, fix it"), assistant("Looking now.")], should_deny=True)

    def test_tool_result_trigger_words_do_not_fire(self) -> None:
        # Genuine user asked for a feature (no trigger); a later tool_result is
        # full of trigger words. Old hook matched the tool_result -> FP.
        self.assert_outcome(
            [user("add a CSV export button"), assistant("ok"),
             tool_result("Error: build failed; fix the broken regression traceback")],
            should_deny=False,
        )

    def test_system_reminder_pollution_does_not_fire(self) -> None:
        # The only trigger words are inside an injected system-reminder span.
        self.assert_outcome(
            [user("add a CSV export button <system-reminder>fix broken Error: traceback не работает regression</system-reminder>")],
            should_deny=False,
        )

    def test_task_notification_pollution_does_not_fire(self) -> None:
        self.assert_outcome(
            [user("rename the column to Total"),
             {"type": "user", "message": {"role": "user", "content": [
                 {"type": "text", "text": "<task-notification>review found a bug; fix broken Error:</task-notification>"}]}}],
            should_deny=False,
        )

    def test_bug_report_behind_many_tool_results_still_fires(self) -> None:
        # False-negative fix: the genuine bug report sits behind tool_results.
        entries = [user("the app crashes on startup, broken — fix it"), assistant("investigating")]
        entries += [tool_result(f"step {i} output, all fine") for i in range(8)]
        self.assert_outcome(entries, should_deny=True)

    def test_discipline_engaged_allows(self) -> None:
        self.assert_outcome(
            [user("the build is broken, fix it"),
             assistant("Capturing diagnostic data and stating my hypothesis before any edit.")],
            should_deny=False,
        )

    def test_override_marker_allows(self) -> None:
        self.assert_outcome(
            [user("fix this broken typo in the heading"),
             assistant("[skip-bugfix-discipline] this is a docs edit, not a bug fix.")],
            should_deny=False,
        )

    def test_no_genuine_user_message_allows(self) -> None:
        # All role=user entries are tool_results -> nothing genuine -> allow.
        self.assert_outcome([assistant("working"), tool_result("Error: fix broken")], should_deny=False)

    def test_codex_payload_bug_report_fires(self) -> None:
        # Real Codex transcript shape (payload/input_text) must be detected and fire.
        self.assert_outcome([codex_user("the parser is broken, fix it"), assistant("ok")], should_deny=True, tool_name="apply_patch")

    def test_codex_tool_output_is_not_a_user_message(self) -> None:
        # A Codex function_call_output full of trigger words is NOT a user message.
        codex_tool = {"type": "response_item", "payload": {"type": "function_call_output", "output": "Error: build broken; fix the regression"}}
        self.assert_outcome([codex_user("add a CSV export option"), assistant("ok"), codex_tool], should_deny=False, tool_name="apply_patch")

    def test_override_marker_in_tool_result_does_not_allow(self) -> None:
        # The marker echoed in tool output (e.g. a grep of a doc that documents
        # it) must NOT disable the guard — only the assistant's own reply can.
        # 8+ tracked repo files literally contain the marker, so this is reachable.
        self.assert_outcome(
            [user("the service is broken, fix it"), assistant("looking"),
             tool_result("CLAUDE.md line: put `[skip-bugfix-discipline]` in your message acknowledging the override")],
            should_deny=True,
        )

    def test_discipline_signal_in_tool_result_does_not_allow(self) -> None:
        # "hypothesis"/"diagnostic" inside tool output is not the model engaging
        # discipline; the guard must still fire (symmetric to the override hole).
        self.assert_outcome(
            [user("login is broken, fix it"), assistant("checking the file"),
             tool_result("the file contents mention a hypothesis and diagnostic logging plan")],
            should_deny=True,
        )

    def test_top_level_tool_output_override_does_not_allow(self) -> None:
        # The override marker echoed in a top-level (non-user) tool-output entry
        # must NOT disable the guard — Codex found this bypass (the entry is not
        # is_user_message, but extract_text reads its top-level `output`).
        self.assert_outcome(
            [user("the service is broken, fix it"), assistant("looking"),
             top_level_tool_output("grep hit: put `[skip-bugfix-discipline]` in your message")],
            should_deny=True,
        )

    def test_claude_tool_use_input_override_does_not_allow(self) -> None:
        # The marker inside a tool_use input (e.g. editing a doc that documents
        # the marker) must NOT disable the guard — only the assistant's prose can.
        self.assert_outcome(
            [user("the parser is broken, fix it"),
             assistant_tool_use("Edit", {"file_path": "CLAUDE.md",
                                          "new_string": "put `[skip-bugfix-discipline]` in your message"})],
            should_deny=True,
        )

    def test_codex_function_call_agents_bugfix_allows(self) -> None:
        # A genuine /agents-bugfix invocation via a Codex function_call is the
        # model engaging discipline -> allow (Codex found this was a false-DENY).
        self.assert_outcome(
            [codex_user("the parser is broken, fix it"),
             codex_function_call("shell", '{"command": "cat .codex/skills/agents-bugfix/SKILL.md"}')],
            should_deny=False, tool_name="apply_patch",
        )

    def test_broad_signal_in_tool_input_does_not_allow(self) -> None:
        # A broad signal word ("diagnostic"/"hypothesis") inside a tool-call
        # INPUT (e.g. editing a file that contains it) is NOT the model engaging
        # discipline — only prose or an /agents-bugfix invocation counts. The
        # guard must still fire (Codex round-3 finding).
        self.assert_outcome(
            [user("the build is broken, fix it"),
             assistant_tool_use("Edit", {"file_path": "notes.md",
                                         "new_string": "TODO: add diagnostic logging and a hypothesis section"})],
            should_deny=True,
        )

    def test_broad_signal_in_codex_function_call_args_does_not_allow(self) -> None:
        # Same, Codex shape: "diagnostic" in function_call arguments is not discipline.
        self.assert_outcome(
            [codex_user("the build is broken, fix it"),
             codex_function_call("shell", '{"command": "echo diagnostic hypothesis > notes.md"}')],
            should_deny=True, tool_name="apply_patch",
        )


if __name__ == "__main__":
    unittest.main()
