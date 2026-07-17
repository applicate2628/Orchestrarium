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


def compact_summary(text: str) -> dict:
    """The harness's post-compaction continuation prompt.

    role=user with real prose, so every text-shaped genuine-user test passes it --
    but no human typed it. Marked by the harness's own `isCompactSummary` flag, which
    is what the hook keys on (the preamble's wording is not ours and can change).
    """
    entry = user(text)
    entry["isCompactSummary"] = True
    return entry

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


class TestBugfixExemptPaths(unittest.TestCase):
    """Doc/report/scratch/plan/task-memory Writes are never the CODE fix the
    guard targets, so bug vocabulary in the surrounding prompt must not block
    them. Proven on a real transcript (2026-06-10): the guard fired legitimately
    on a .reports/ memo write under a bug-fix-review prompt with no override
    marker in prose. The fix exempts those path segments; code paths stay guarded."""

    # Bug-triggers present, NO override marker, NO discipline signal -> the guard
    # WOULD deny a code edit here; only the path exemption may allow it.
    BUG_ENTRIES = [
        user("Review this bug-fix plan: fix the regression, it is broken, delete the dead path, STOP-bug."),
        assistant("Reviewing the plan now."),
    ]

    def _deny(self, script: Path, tool_input: dict, tool_name: str) -> bool:
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            for e in self.BUG_ENTRIES:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
            transcript = f.name
        envelope = {"transcript_path": transcript, "tool_name": tool_name, "tool_input": tool_input}
        p = subprocess.run([sys.executable, str(script)], input=json.dumps(envelope, ensure_ascii=False),
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(p.returncode, 0, p.stderr)
        return denies(p)

    def assert_exempt(self, tool_input: dict, exempt: bool, tool_name: str = "Write") -> None:
        for script in HOOKS:
            with self.subTest(pack=script.parent.parent.name, ti=tool_input):
                self.assertEqual(self._deny(script, tool_input, tool_name), not exempt)

    def test_reports_exempt(self) -> None:
        self.assert_exempt({"file_path": ".reports/2026-06/memo.md", "content": "x"}, exempt=True)

    def test_scratch_exempt(self) -> None:
        self.assert_exempt({"file_path": ".scratch/note.md", "content": "x"}, exempt=True)

    def test_plans_exempt(self) -> None:
        self.assert_exempt({"file_path": ".plans/2026-06/p.md", "content": "x"}, exempt=True)

    def test_work_items_exempt(self) -> None:
        self.assert_exempt({"file_path": "work-items/bugs/x.md", "content": "x"}, exempt=True)

    def test_docs_exempt(self) -> None:
        self.assert_exempt({"file_path": "docs/guide.md", "content": "x"}, exempt=True)

    def test_skill_md_exempt(self) -> None:
        # Authoring a skill DEFINITION (SKILL.md) is prose/instructions, never the code fix this guard targets.
        self.assert_exempt({"file_path": "skills/my-skill/SKILL.md", "content": "x"}, exempt=True)

    def test_skill_md_absolute_skills_root_exempt(self) -> None:
        # The reported false-positive precedent: a new skill authored under the global skills root.
        self.assert_exempt(
            {"file_path": r"C:\Users\dev\.claude\skills\vak-dissertation-review\SKILL.md", "content": "x"},
            exempt=True,
        )

    def test_skill_script_still_denies_no_hole(self) -> None:
        # A skill's SCRIPT is code and stays guarded -- the SKILL.md basename exemption must not over-reach.
        self.assert_exempt({"file_path": "skills/my-skill/scripts/run.py", "content": "x"}, exempt=False)

    def test_absolute_windows_reports_exempt(self) -> None:
        self.assert_exempt({"file_path": r"Z:\fixtures\demo\.reports\2026-06\m.md", "content": "x"}, exempt=True)

    def test_notebook_path_in_scratch_exempt(self) -> None:
        # NotebookEdit carries notebook_path, not file_path.
        self.assert_exempt({"notebook_path": ".scratch/x.ipynb"}, exempt=True, tool_name="NotebookEdit")

    def test_code_py_write_still_denies_no_hole(self) -> None:
        self.assert_exempt({"file_path": "src.claude/agents/foo.py", "content": "x"}, exempt=False)

    def test_code_ts_edit_still_denies_no_hole(self) -> None:
        self.assert_exempt({"file_path": "src/app.ts", "old_string": "a", "new_string": "b"}, exempt=False, tool_name="Edit")

    def test_mydocs_substring_is_not_exempt(self) -> None:
        # 'mydocs' is NOT the '/docs/' path segment -> the file stays guarded.
        self.assert_exempt({"file_path": "src/mydocs/x.py", "content": "x"}, exempt=False)


if __name__ == "__main__":
    unittest.main()

class TestCompactSummaryIsNotAUserBugReport(unittest.TestCase):
    """The post-compaction continuation prompt drove `permissionDecision: deny` on
    unrelated edits (reproduced 2026-07-17 on a live session whose transcript carried
    21 such entries).

    It is the worst possible input to a trigger-phrase matcher, and the failure is
    self-amplifying: the harness quotes the prior session back -- file paths, error
    output, and an "Errors and fixes" section naming every defect touched -- so the
    MORE bug-fixing a session did, the more certainly the guard misfires afterwards.
    It also fires at the worst moment: right after compaction, on every edit, until
    the next human message.

    The fix must not swing the other way. Discarding the summary makes the detector
    walk back to the human's real pre-compaction message -- which IS still their last
    genuine request -- so a real bug report behind a summary must still fire. A guard
    that stops guarding is worse than one that occasionally over-fires."""

    SUMMARY = (
        "This session is being continued from a previous conversation that ran out of "
        "context. The summary below covers the earlier portion.\n"
        "Summary:\n4. Errors and fixes:\n - the assertion broke; Error: mismatch\n"
        "If you need details (like exact error messages), read the full transcript."
    )

    def assert_outcome(self, entries: list[dict], should_deny: bool) -> None:
        for script in HOOKS:
            with self.subTest(script=script.name):
                self.assertEqual(denies(run_hook(script, entries)), should_deny)

    def test_compact_summary_alone_does_not_fire(self) -> None:
        # THE reproduced false positive: the only trigger words are the harness's.
        self.assert_outcome(
            [compact_summary(self.SUMMARY), assistant("Resuming the batch.")],
            should_deny=False,
        )

    def test_real_bug_report_behind_a_compact_summary_still_fires(self) -> None:
        # The falsifier that keeps the fix honest: skipping the summary must reach the
        # human's real request, not disarm the guard.
        self.assert_outcome(
            [user("the auth timeout is broken, fix it"), assistant("ok"),
             compact_summary(self.SUMMARY), assistant("Resuming.")],
            should_deny=True,
        )

    def test_benign_request_behind_a_bug_laden_summary_does_not_fire(self) -> None:
        self.assert_outcome(
            [user("add a docstring to the parser"), assistant("ok"),
             compact_summary(self.SUMMARY), assistant("Resuming.")],
            should_deny=False,
        )

    def test_is_meta_entries_are_not_user_reports_either(self) -> None:
        # Same class, sibling flag: harness-authored user-role entries.
        entry = user("Error: broken traceback не работает")
        entry["isMeta"] = True
        self.assert_outcome([entry, assistant("Resuming.")], should_deny=False)
