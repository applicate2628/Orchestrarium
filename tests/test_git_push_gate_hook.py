"""Behavioral tests for the git-push publication-gate PreToolUse hook (F8).

The gate is the structural backstop for the prose-only rule "human review
before `git push` must include a leak-check of staged changes": it denies a
Bash `git push` in command position unless (a) the LAST GENUINE USER MESSAGE
carries the per-turn override `[approve-publication]` (user-side only — never
honored from assistant prose, tool calls, or tool output), or (b) the current
turn's model tool CALLS show a publication-safety scan invocation AND the last
genuine user message contains an explicit push instruction. `git push
--dry-run` is always allowed; a `git push` inside a quoted string is data, not
a command; subagent contexts (envelope `agent_id`) are allowed; everything
fails open.

Structure mirrors tests/test_bugfix_discipline_hook.py: subprocess-drive the
.py helper with a synthetic transcript + envelope, run against BOTH the Claude
and Codex pack copies.
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
    REPO_ROOT / "src.claude" / "agents" / "scripts" / "check-git-push-gate.py",
    REPO_ROOT / "src.codex" / "skills" / "lead" / "scripts" / "check-git-push-gate.py",
)


def user(text: str) -> dict:
    return {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}


def tool_result(text: str) -> dict:
    return {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": text}]}}


def assistant(text: str) -> dict:
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def assistant_tool_use(name: str, input_obj: dict) -> dict:
    return {"type": "assistant", "message": {"role": "assistant",
            "content": [{"type": "tool_use", "name": name, "input": input_obj}]}}


def run_hook(
    script: Path,
    entries: list[dict],
    command: str,
    agent_id: str | None = None,
    transcript: bool = True,
) -> subprocess.CompletedProcess:
    envelope: dict = {"tool_name": "Bash", "tool_input": {"command": command}}
    if transcript:
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
            envelope["transcript_path"] = f.name
    if agent_id:
        envelope["agent_id"] = agent_id
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(envelope, ensure_ascii=False),
        capture_output=True, text=True, encoding="utf-8",
    )


def denies(p: subprocess.CompletedProcess) -> bool:
    return '"permissionDecision"' in p.stdout and '"deny"' in p.stdout


SCAN_CALL = assistant_tool_use(
    "Bash", {"command": "bash .claude/agents/scripts/check-publication-safety.sh"}
)


class TestGitPushGate(unittest.TestCase):
    def assert_outcome(
        self,
        entries: list[dict],
        command: str,
        should_deny: bool,
        agent_id: str | None = None,
        transcript: bool = True,
    ) -> None:
        for script in HOOKS:
            with self.subTest(script=script.parent.parent.name, command=command):
                p = run_hook(script, entries, command, agent_id=agent_id, transcript=transcript)
                self.assertEqual(p.returncode, 0, p.stderr)  # hook always exits 0
                self.assertEqual(denies(p), should_deny, f"stdout={p.stdout!r}")

    # --- deny: bare push, no approval, no scan ---

    def test_bare_push_denied(self) -> None:
        self.assert_outcome(
            [user("finish the fix and commit"), assistant("done, pushing now")],
            "git push origin main",
            should_deny=True,
        )

    def test_push_chained_after_commit_denied(self) -> None:
        # The exact momentum failure the finding names: commit && push in one turn.
        self.assert_outcome(
            [user("commit the change"), assistant("committing")],
            'git add -A && git commit -m "fix" && git push',
            should_deny=True,
        )

    def test_push_with_global_option_denied(self) -> None:
        self.assert_outcome(
            [user("wrap up")],
            "git -C /repo push origin main",
            should_deny=True,
        )

    def test_mixed_dry_run_and_real_push_denied(self) -> None:
        # One dry run does not launder a second, real push in the same command.
        self.assert_outcome(
            [user("wrap up")],
            "git push --dry-run && git push origin main",
            should_deny=True,
        )

    # --- allow: user-side per-turn override marker ---

    def test_user_marker_allows(self) -> None:
        self.assert_outcome(
            [user("looks good, push it [approve-publication]"), assistant("pushing")],
            "git push origin main",
            should_deny=False,
        )

    def test_lead_sync_flow_marker_allows(self) -> None:
        # The Lead's own legitimate sync flow: explicit user approval carried in
        # the dispatch message, then a direct `git push` from Bash.
        self.assert_outcome(
            [user("Wave E approved after review — sync all branches [approve-publication]"),
             assistant("Running the branch sync now.")],
            "git push origin feat/audit-wave-e",
            should_deny=False,
        )

    def test_marker_in_assistant_prose_does_not_allow(self) -> None:
        # User-side only: the model writing the marker itself must not open the gate.
        self.assert_outcome(
            [user("finish the task"), assistant("[approve-publication] pushing now")],
            "git push origin main",
            should_deny=True,
        )

    def test_marker_in_tool_result_does_not_allow(self) -> None:
        # The marker echoed in tool output (e.g. grep of a doc that documents it)
        # must not open the gate.
        self.assert_outcome(
            [user("finish the task"), assistant("checking"),
             tool_result("INSTALL.md: the USER includes `[approve-publication]` in their message")],
            "git push origin main",
            should_deny=True,
        )

    def test_marker_in_tool_use_input_does_not_allow(self) -> None:
        # The marker inside a tool_use input (e.g. editing a doc about the marker)
        # must not open the gate.
        self.assert_outcome(
            [user("update the docs then push"),
             assistant_tool_use("Edit", {"file_path": "INSTALL.md",
                                          "new_string": "include `[approve-publication]` in your message"})],
            "git push origin main",
            should_deny=True,
        )

    # --- allow: scan evidence + explicit user push instruction ---

    def test_scan_evidence_plus_push_instruction_allows(self) -> None:
        self.assert_outcome(
            [user("run the safety check and push the branch"),
             SCAN_CALL,
             assistant("Scan clean; pushing.")],
            "git push origin main",
            should_deny=False,
        )

    def test_scan_evidence_plus_russian_push_instruction_allows(self) -> None:
        self.assert_outcome(
            [user("запушь wave E после проверки"),
             SCAN_CALL],
            "git push origin feat/audit-wave-e",
            should_deny=False,
        )

    def test_scan_evidence_without_push_instruction_denies(self) -> None:
        # The scan alone is not approval — the user never asked for a push.
        self.assert_outcome(
            [user("review the changes"), SCAN_CALL],
            "git push origin main",
            should_deny=True,
        )

    def test_push_instruction_without_scan_denies(self) -> None:
        # An instructed push still needs the leak-check first.
        self.assert_outcome(
            [user("push the branch"), assistant("pushing")],
            "git push origin main",
            should_deny=True,
        )

    def test_scan_mention_in_prose_only_does_not_allow(self) -> None:
        # Claiming the scan in prose is not running it — only a tool CALL counts.
        self.assert_outcome(
            [user("push the branch"),
             assistant("I ran check-publication-safety earlier and it was clean.")],
            "git push origin main",
            should_deny=True,
        )

    def test_scan_in_tool_result_does_not_allow(self) -> None:
        # Scanner text inside tool OUTPUT is not an invocation either.
        self.assert_outcome(
            [user("push the branch"), assistant("checking"),
             tool_result("docs mention check-publication-safety.sh here")],
            "git push origin main",
            should_deny=True,
        )

    def test_scan_before_user_message_does_not_allow(self) -> None:
        # Scan evidence is per-turn: an invocation BEFORE the last genuine user
        # message is stale and does not open the gate.
        self.assert_outcome(
            [user("first check safety"), SCAN_CALL, user("push the branch"),
             assistant("pushing")],
            "git push origin main",
            should_deny=True,
        )

    # --- allow: dry run / non-push / quoted ---

    def test_dry_run_allowed(self) -> None:
        self.assert_outcome([user("test the push")], "git push --dry-run origin main", should_deny=False)

    def test_quoted_string_push_ignored(self) -> None:
        self.assert_outcome([user("write docs")], 'echo "git push origin main"', should_deny=False)

    def test_non_push_git_command_allowed(self) -> None:
        self.assert_outcome([user("check status")], "git status && git log --oneline -3", should_deny=False)

    def test_non_git_command_allowed(self) -> None:
        self.assert_outcome([user("list files")], "ls -la", should_deny=False)

    # --- envelope handling: agent_id, fail-open ---

    def test_agent_id_allows(self) -> None:
        self.assert_outcome(
            [user("finish and push")],
            "git push origin main",
            should_deny=False,
            agent_id="subagent-123",
        )

    def test_missing_transcript_fails_open(self) -> None:
        self.assert_outcome([], "git push origin main", should_deny=False, transcript=False)

    def test_malformed_envelope_fails_open(self) -> None:
        for script in HOOKS:
            with self.subTest(script=script.parent.parent.name):
                p = subprocess.run(
                    [sys.executable, str(script)],
                    input="not json {{{",
                    capture_output=True, text=True, encoding="utf-8",
                )
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertFalse(denies(p), f"stdout={p.stdout!r}")

    def test_empty_stdin_fails_open(self) -> None:
        for script in HOOKS:
            with self.subTest(script=script.parent.parent.name):
                p = subprocess.run(
                    [sys.executable, str(script)],
                    input="",
                    capture_output=True, text=True, encoding="utf-8",
                )
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertFalse(denies(p), f"stdout={p.stdout!r}")

    def test_non_bash_tool_input_fails_open(self) -> None:
        # An Edit-shaped tool_input (no `command`) must never deny.
        for script in HOOKS:
            with self.subTest(script=script.parent.parent.name):
                envelope = {"tool_name": "Edit",
                            "tool_input": {"file_path": "x.py", "old_string": "a", "new_string": "b"}}
                p = subprocess.run(
                    [sys.executable, str(script)],
                    input=json.dumps(envelope),
                    capture_output=True, text=True, encoding="utf-8",
                )
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertFalse(denies(p), f"stdout={p.stdout!r}")

    def test_deny_payload_carries_compliance_instructions(self) -> None:
        # The deny reason must tell the model exactly how to comply.
        for script in HOOKS:
            with self.subTest(script=script.parent.parent.name):
                p = run_hook(script, [user("wrap up the task")], "git push origin main")
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertTrue(denies(p), f"stdout={p.stdout!r}")
                payload = json.loads(p.stdout)
                reason = payload["hookSpecificOutput"]["permissionDecisionReason"]
                self.assertIn("[approve-publication]", reason)
                self.assertIn("check-publication-safety", reason)
                self.assertIn("--dry-run", reason)
                self.assertIn("BACKSTOP", reason)


if __name__ == "__main__":
    unittest.main()
