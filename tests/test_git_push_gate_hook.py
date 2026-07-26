"""Behavioral tests for the git-push publication-gate PreToolUse hook (F8).

The gate is the structural backstop for the prose-only rule "human review
before `git push` must include a leak-check of staged changes": it denies a
Bash `git push` in command position unless (a) the LAST GENUINE USER MESSAGE
carries the per-turn override `[approve-publication]` (user-side only — never
honored from assistant prose, tool calls, or tool output), or (b) the current
turn's model tool CALLS show a publication-safety scan invocation AND that
SAME invocation's OWN tool OUTPUT this turn — correlated by call identity,
never by mere co-occurrence in the turn — reports a clean, non-empty,
`tracked`-mode result (2026-07-26 hardening — branch (b) now keys on a
CORRELATED result, not merely invocation, and not an uncorrelated result
appearing anywhere in the turn; see check-git-push-gate.py's module docstring,
work-items/backlog/2026-07-25-push-gate-blind-to-scan-result/brief.md §11.5
D1-D3/S6, and the adversarial-gate correction that found the first cut of this
hardening joined two independent haystacks instead of correlating) AND the
last genuine user message contains an explicit push instruction. `git push
--dry-run` is always allowed; a `git push` inside a quoted string is data, not
a command; subagent contexts (envelope `agent_id`) are allowed; everything
fails open.

Fixture id/call_id fields matter here, not just cosmetically: every
call/result PAIR meant to represent one real invocation shares the SAME
`tool_id`/`call_id` (mirroring the real Claude `tool_use.id` /
`tool_result.tool_use_id` and Codex `function_call`/`function_call_output`
`call_id` correlation, verified against real transcripts on this
installation), and every "unrelated tool" fixture deliberately uses a
DIFFERENT id so a test can prove the gate does not correlate by content alone.

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


def tool_result(text: str, tool_id: str = "toolu_default") -> dict:
    return {"type": "user", "message": {"role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tool_id, "content": text}]}}


def assistant(text: str) -> dict:
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def assistant_tool_use(name: str, input_obj: dict, tool_id: str = "toolu_default") -> dict:
    return {"type": "assistant", "message": {"role": "assistant",
            "content": [{"type": "tool_use", "id": tool_id, "name": name, "input": input_obj}]}}


def codex_function_call(name: str, arguments: str, call_id: str = "call_default") -> dict:
    return {"type": "response_item",
            "payload": {"type": "function_call", "call_id": call_id, "name": name, "arguments": arguments}}


def codex_function_call_output(text: str, call_id: str = "call_default") -> dict:
    return {"type": "response_item",
            "payload": {"type": "function_call_output", "call_id": call_id, "output": text}}


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
    "Bash", {"command": "bash .claude/agents/scripts/check-publication-safety.sh"}, tool_id="toolu_scan"
)

SCAN_CALL_PATH_MODE = assistant_tool_use(
    "Bash", {"command": "bash .claude/agents/scripts/check-publication-safety.sh --path ./fixture"},
    tool_id="toolu_scan_path",
)

CODEX_SCAN_CALL = codex_function_call(
    "shell", '{"command": "bash .codex/skills/lead/scripts/check-publication-safety.sh"}',
    call_id="call_scan",
)

# The scanner's own self-reported RESULT text (check-publication-safety.sh,
# 2026-07-26 hardening) -- these are what check-git-push-gate.py's
# SCAN_CLEAN_TRACKED_REGEX actually matches against tool OUTPUT, never a call.
# Each carries the SAME tool_id/call_id as the invocation it is the real
# answer to (see SCAN_CALL / SCAN_CALL_PATH_MODE / CODEX_SCAN_CALL above) --
# that shared id is the correlation the 2026-07-26 adversarial-gate finding
# proved was missing when these were two independently-matched haystacks.
SCAN_RESULT_CLEAN_TRACKED = tool_result(
    "publication-safety: clean (tracked, examined 3 files)", tool_id="toolu_scan"
)
SCAN_RESULT_CLEAN_TRACKED_SINGULAR = tool_result(
    "publication-safety: clean (tracked, examined 1 file)", tool_id="toolu_scan"
)
SCAN_RESULT_CLEAN_EMPTY = tool_result(
    "publication-safety: clean (tracked, examined 0 files -- nothing staged)", tool_id="toolu_scan"
)
SCAN_RESULT_CLEAN_PATH_MODE = tool_result(
    "publication-safety: clean (path, examined 1 file)", tool_id="toolu_scan_path"
)
SCAN_RESULT_FAIL = tool_result(
    "publication-safety scan found potential tracked-content leak markers", tool_id="toolu_scan"
)

CODEX_SCAN_RESULT_CLEAN_TRACKED = codex_function_call_output(
    "publication-safety: clean (tracked, examined 2 files)", call_id="call_scan"
)

# --- "different source" fixtures: an UNRELATED tool call/result pair, with
# its OWN distinct id, whose result happens to quote the scanner's exact
# clean-result text. `tests/test_git_push_gate_hook.py` (this very file)
# literally contains that string a few lines above, which is precisely why an
# innocent `Read` of it is a realistic, not contrived, bypass attempt for an
# uncorrelated gate -- and exactly the shape the adversarial gate reproduced
# live against the shipped (pre-correlation) hook.

READ_CALL_UNRELATED = assistant_tool_use(
    "Read", {"file_path": "tests/test_git_push_gate_hook.py"}, tool_id="toolu_read"
)
READ_RESULT_WITH_CLEAN_TEXT = tool_result(
    "     1\tSCAN_RESULT_CLEAN_TRACKED = tool_result(\n"
    '     2\t    "publication-safety: clean (tracked, examined 3 files)", tool_id="toolu_scan"\n',
    tool_id="toolu_read",
)

UNRELATED_GREP_CALL = assistant_tool_use(
    "Bash", {"command": "git grep -n TODO"}, tool_id="toolu_grep"
)
UNRELATED_GREP_RESULT = tool_result("no matches", tool_id="toolu_grep")


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

    # --- allow: scan evidence (invocation AND clean non-empty result) + explicit user push instruction ---

    def test_scan_evidence_plus_push_instruction_allows(self) -> None:
        self.assert_outcome(
            [user("run the safety check and push the branch"),
             SCAN_CALL, SCAN_RESULT_CLEAN_TRACKED,
             assistant("Scan clean; pushing.")],
            "git push origin main",
            should_deny=False,
        )

    def test_scan_evidence_plus_russian_push_instruction_allows(self) -> None:
        self.assert_outcome(
            [user("запушь wave E после проверки"),
             SCAN_CALL, SCAN_RESULT_CLEAN_TRACKED],
            "git push origin feat/audit-wave-e",
            should_deny=False,
        )

    def test_scan_evidence_singular_file_count_allows(self) -> None:
        # The scanner's grammar-correct singular ("1 file") must match too --
        # the regex requires `files?`, not a hardcoded plural.
        self.assert_outcome(
            [user("push the branch"),
             SCAN_CALL, SCAN_RESULT_CLEAN_TRACKED_SINGULAR],
            "git push origin main",
            should_deny=False,
        )

    def test_scan_evidence_without_push_instruction_denies(self) -> None:
        # The scan alone is not approval — the user never asked for a push.
        self.assert_outcome(
            [user("review the changes"), SCAN_CALL, SCAN_RESULT_CLEAN_TRACKED],
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

    # --- deny: RESULT-blind regressions (2026-07-26 hardening) ---
    # These are the core of this hardening: invocation ALONE (the pre-fix
    # behavior) must no longer be sufficient. Each test below reproduces a
    # scenario that the pre-fix gate allowed and the post-fix gate must deny.

    def test_scan_invoked_but_no_result_denies(self) -> None:
        # The scan was called but never reported back (e.g. still running, or
        # its output was never captured in this turn). Pre-fix, invocation
        # alone opened the gate here; post-fix it must not.
        self.assert_outcome(
            [user("run the safety check and push the branch"), SCAN_CALL],
            "git push origin main",
            should_deny=True,
        )

    def test_scan_invoked_and_examines_empty_set_denies(self) -> None:
        # THE LIVE FAILURE (2026-07-25/26): after a commit, the staged index
        # equals HEAD, so a scan run at push time examines NOTHING and exits
        # clean. Pre-fix this opened the gate (an empty scan read as a pass).
        # Post-fix, an examined-count of 0 must never satisfy branch (b).
        self.assert_outcome(
            [user("push the branch"), SCAN_CALL, SCAN_RESULT_CLEAN_EMPTY],
            "git push origin main",
            should_deny=True,
        )

    def test_scan_invoked_and_fails_denies(self) -> None:
        # The scan ran and found a leak (exit 1). Pre-fix this ALSO opened the
        # gate (invocation alone was sufficient, regardless of outcome) --
        # this is probe4_failing_scan_still_allows's Scenario A.
        self.assert_outcome(
            [user("push the branch"), SCAN_CALL, SCAN_RESULT_FAIL],
            "git push origin main",
            should_deny=True,
        )

    def test_path_mode_clean_result_does_not_allow(self) -> None:
        # A `--path` fixture-testing invocation reports scan MODE "path", not
        # "tracked" -- it scans arbitrary content unrelated to what is staged
        # and must never launder as gate evidence, however clean it reports.
        self.assert_outcome(
            [user("push the branch"), SCAN_CALL_PATH_MODE, SCAN_RESULT_CLEAN_PATH_MODE],
            "git push origin main",
            should_deny=True,
        )

    def test_clean_result_without_matching_call_does_not_allow(self) -> None:
        # The clean-result marker appearing in tool output with NO matching
        # scan invocation this turn (e.g. echoed from a stale earlier run, or
        # injected some other way) must not open the gate on its own -- both
        # the call AND the result are required.
        self.assert_outcome(
            [user("push the branch"), assistant("checking"), SCAN_RESULT_CLEAN_TRACKED],
            "git push origin main",
            should_deny=True,
        )

    def test_codex_shape_scan_evidence_allows(self) -> None:
        # S4: the Codex function_call / function_call_output transcript shape
        # must be covered by the same result-keyed mechanism, not just Claude's
        # tool_use / tool_result shape.
        self.assert_outcome(
            [user("push the branch"), CODEX_SCAN_CALL, CODEX_SCAN_RESULT_CLEAN_TRACKED],
            "git push origin main",
            should_deny=False,
        )

    def test_codex_shape_scan_invoked_but_no_result_denies(self) -> None:
        self.assert_outcome(
            [user("push the branch"), CODEX_SCAN_CALL],
            "git push origin main",
            should_deny=True,
        )

    # --- deny: CORRELATION regressions (2026-07-26 adversarial-gate finding) ---
    # The first cut of the result-keyed hardening built the call-evidence and
    # the result-evidence as two INDEPENDENT strings, `\n`-joined across every
    # entry in the turn, then checked each string against its own regex
    # anywhere in it. That is not correlation: a scan invocation anywhere in
    # the turn plus a clean-shaped line from ANY tool's output anywhere in the
    # turn satisfied it, even when no scan ever produced that line. Every test
    # below pairs a real (or absent) scan invocation with a clean-result STRING
    # that comes from a DIFFERENT tool call (a different id) and asserts DENY --
    # the exact shape id-correlation must reject and haystack-joining allowed.

    def test_scan_invoked_but_clean_line_comes_from_a_different_tool_call_denies(self) -> None:
        # THE CORRELATION DEFECT, minimal form (adversarial gate's core
        # finding): a real scan invocation exists this turn (id=toolu_scan) but
        # NEVER gets its own answering result. A wholly unrelated Read
        # (id=toolu_read) of this very test file -- which literally contains
        # the clean-result string as fixture data -- produces a result that
        # LOOKS clean. Uncorrelated matching (two independent haystacks) let
        # this ALLOW; id-correlated matching must DENY, because the Read's
        # tool_result carries the Read's OWN id, never the scan's.
        self.assert_outcome(
            [user("push the branch"),
             SCAN_CALL,  # invoked, but no result with id=toolu_scan follows
             READ_CALL_UNRELATED, READ_RESULT_WITH_CLEAN_TEXT],
            "git push origin main",
            should_deny=True,
        )

    def test_empty_index_scan_plus_unrelated_clean_read_denies(self) -> None:
        # Reproduces the adversarial gate's row 1 exactly: the scan genuinely
        # ran and examined nothing (correlated to its OWN result, correctly
        # denying on its own merits -- see test_scan_invoked_and_examines_
        # empty_set_denies), PLUS an unrelated Read whose OWN result happens to
        # quote the clean-marker string must not launder a pass via a second,
        # uncorrelated match.
        self.assert_outcome(
            [user("push the branch"),
             SCAN_CALL, SCAN_RESULT_CLEAN_EMPTY,  # real scan, correlated, examined 0
             READ_CALL_UNRELATED, READ_RESULT_WITH_CLEAN_TEXT],
            "git push origin main",
            should_deny=True,
        )

    def test_path_mode_scan_plus_unrelated_clean_tracked_read_denies(self) -> None:
        # Reproduces the adversarial gate's row 2 exactly: a real `--path`
        # scan ran and correctly self-reported mode "path" (correlated,
        # correctly denying on its own merits), PLUS an unrelated Read whose
        # OWN result quotes a "tracked"-tagged clean line must not launder a
        # pass -- the path/tracked distinction is defeated entirely by
        # uncorrelated matching, which this proves id-correlation closes.
        self.assert_outcome(
            [user("push the branch"),
             SCAN_CALL_PATH_MODE, SCAN_RESULT_CLEAN_PATH_MODE,  # real scan, path mode, correlated
             READ_CALL_UNRELATED, READ_RESULT_WITH_CLEAN_TEXT],
            "git push origin main",
            should_deny=True,
        )

    def test_unrelated_command_plus_clean_text_elsewhere_denies(self) -> None:
        # Reproduces the adversarial gate's row 3 exactly: "one git grep, no
        # scanner executed at all." Neither tool call in this turn invokes the
        # scanner; the clean-marker string appears only in a Read result whose
        # id matches nothing that ever ran the scanner.
        self.assert_outcome(
            [user("push the branch"),
             UNRELATED_GREP_CALL, UNRELATED_GREP_RESULT,
             READ_CALL_UNRELATED, READ_RESULT_WITH_CLEAN_TEXT],
            "git push origin main",
            should_deny=True,
        )

    def test_codex_shape_scan_invoked_but_clean_output_from_different_call_id_denies(self) -> None:
        # S4 companion to the correlation regression: the same defect, Codex
        # function_call / function_call_output shape. A real scan invocation
        # (call_id="call_scan") gets no matching output; an unrelated call
        # (call_id="call_other") produces output quoting the clean line.
        self.assert_outcome(
            [user("push the branch"),
             CODEX_SCAN_CALL,  # invoked, but no output with call_id="call_scan" follows
             codex_function_call("shell", '{"command": "cat notes.md"}', call_id="call_other"),
             codex_function_call_output(
                 "notes.md contains: publication-safety: clean (tracked, examined 3 files)",
                 call_id="call_other",
             )],
            "git push origin main",
            should_deny=True,
        )

    def test_missing_id_field_denies_rather_than_falling_back_to_text_match(self) -> None:
        # THE QUESTION A CORRELATION FIX MUST ANSWER SAFELY: if a transcript
        # entry carries no correlatable id at all (a future runtime field
        # rename, or a shape this code does not recognize), does the gate
        # deny (safe -- the correlated-evidence path is simply unreachable)
        # or silently fall back to matching by text content alone (unsafe --
        # this is exactly what reintroduces Finding 1)? This test builds a
        # tool_use with NO "id" key and a tool_result with NO "tool_use_id"
        # key -- neither hook_common extractor can produce a call_id for
        # either (extract_model_tool_calls_with_ids / extract_tool_outputs_
        # with_ids both skip an id-less item entirely, never fabricate one),
        # so this call is never added to scan_call_ids and this result can
        # never correlate to anything, regardless of what either's text says.
        # There is no text-matching fallback anywhere in this code path to
        # fall back TO -- the joined-haystack functions were deleted, not
        # kept as a secondary path -- so the only possible outcome is DENY.
        no_id_call = {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Bash",
             "input": {"command": "bash .claude/agents/scripts/check-publication-safety.sh"}}
            # deliberately NO "id" key
        ]}}
        no_id_result = {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "content": "publication-safety: clean (tracked, examined 3 files)"}
            # deliberately NO "tool_use_id" key
        ]}}
        self.assert_outcome(
            [user("push the branch"), no_id_call, no_id_result],
            "git push origin main",
            should_deny=True,
        )

    # --- deny: MENTION-vs-EXECUTION + compound-command regressions (second
    # adversarial-gate finding, 2026-07-26). The first correlation fix keyed
    # scan-CALL detection off a plain substring regex over the call's
    # flattened text, which is satisfied by a command that merely NAMES the
    # scanner as an argument to something else, exactly as readily as one
    # that actually runs it. Two concrete vectors were reproduced live
    # against real historical transcripts on this machine: a `grep`/`ls`/
    # `Test-Path` mention (never runs the scanner) and a compound command
    # that runs the REAL scanner alongside an unrelated sibling command in
    # the SAME call, whose merged stdout can carry a sibling's own real
    # output past the clean-result regex even though only the sibling
    # produced matching text. Both are now closed by find_scan_script_
    # executions (execution-only, never mention) plus the solo-segment rule
    # in _command_is_solely_scan_execution.

    def test_grep_naming_the_scanner_as_a_target_path_does_not_allow(self) -> None:
        # THE EXACT DEFECT, reproduced: a `grep` command whose TARGET PATH
        # happens to be the scanner's own file (a routine "where is the
        # scanner" search, not an execution) paired with a REAL grep result
        # that legitimately contains a clean-shaped line lifted from this
        # repo's own text. Under mention-based detection this ALLOWed with
        # no scan ever having run; execution-based detection must DENY.
        mention_call = assistant_tool_use(
            "Bash",
            {"command": 'grep -rn "examined" tests/test_git_push_gate_hook.py '
                        'scripts/universal-hooks/scripts/check-publication-safety.sh'},
            tool_id="toolu_mention",
        )
        mention_result = tool_result(
            "publication-safety: clean (tracked, examined 42 files)", tool_id="toolu_mention"
        )
        self.assert_outcome(
            [user("push the branch"), mention_call, mention_result],
            "git push origin main",
            should_deny=True,
        )

    def test_ls_naming_the_command_file_does_not_allow(self) -> None:
        # Real historical pattern found on this machine's own transcripts:
        # `ls` checking whether the scanner/command files EXIST. A pure
        # existence check, never an execution.
        mention_call = assistant_tool_use(
            "Bash",
            {"command": "ls -la ~/.claude/commands/agents-check-safety.md "
                        ".claude/commands/agents-check-safety.md"},
            tool_id="toolu_ls",
        )
        mention_result = tool_result(
            "publication-safety: clean (tracked, examined 3 files)", tool_id="toolu_ls"
        )
        self.assert_outcome(
            [user("push the branch"), mention_call, mention_result],
            "git push origin main",
            should_deny=True,
        )

    def test_compound_command_scan_plus_sibling_grep_in_one_call_does_not_allow(self) -> None:
        # THE COMPOUND-COMMAND DEFECT: a REAL, correctly-zero-file scan
        # (which must deny on its own -- work-items/bugs/2026-07-25-push-
        # gate-keys-on-scan-invocation-not-result.md) chained with an
        # unrelated `grep` in the SAME call. The grep's own real output
        # (matching content that pre-exists in this repo) lands in the SAME
        # correlated tool result as the scan's own real (empty) output. The
        # solo-segment rule must reject the WHOLE call as scan evidence,
        # because there is no way to attribute which line came from which
        # command once the shell has merged their stdout.
        compound_call = assistant_tool_use(
            "Bash",
            {"command": "bash .claude/agents/scripts/check-publication-safety.sh; "
                        "grep -rn 'examined' tests"},
            tool_id="toolu_compound",
        )
        compound_result = tool_result(
            "publication-safety: clean (tracked, examined 0 files)\n"
            "tests/test_git_push_gate_hook.py:1:    "
            "'publication-safety: clean (tracked, examined 42 files)',",
            tool_id="toolu_compound",
        )
        self.assert_outcome(
            [user("push the branch"), compound_call, compound_result],
            "git push origin main",
            should_deny=True,
        )

    def test_newline_separated_compound_scan_does_not_allow(self) -> None:
        # THE NEWLINE-SEPARATOR DEFECT (2026-07-26, second adversarial-gate
        # finding on this same hardening): `shlex(..., whitespace_split=True)`
        # treats `\n` as ordinary whitespace, not a separator, by default --
        # so the exact compound-command attack the solo-segment rule exists
        # to block succeeds verbatim when the sibling command is spelled with
        # a real newline instead of `;`. Multi-line Bash commands are routine
        # (the model batches several commands into one tool call), so this is
        # accident-class, not a contrived edge case. Verbatim shape from
        # work-items/bugs/2026-07-26-push-gate-never-fires-on-a-multi-line-
        # push-command.md: a real, correctly-zero-file scan, a bare newline,
        # then an unrelated `grep` whose own real output satisfies the
        # clean-result regex -- must DENY exactly like the `;`-separated form
        # above, not ALLOW.
        newline_compound_call = assistant_tool_use(
            "Bash",
            {"command": "bash .claude/agents/scripts/check-publication-safety.sh\n"
                        "grep -rn 'examined' tests"},
            tool_id="toolu_newline_compound",
        )
        newline_compound_result = tool_result(
            "publication-safety: clean (tracked, examined 0 files)\n"
            "tests/test_git_push_gate_hook.py:1:    "
            "'publication-safety: clean (tracked, examined 42 files)',",
            tool_id="toolu_newline_compound",
        )
        self.assert_outcome(
            [user("push the branch"), newline_compound_call, newline_compound_result],
            "git push origin main",
            should_deny=True,
        )

    def test_multiline_publish_sequence_is_still_detected_as_a_push(self) -> None:
        # THE OTHER HALF OF THE SAME ROOT CAUSE (2026-07-26, pre-existing,
        # confirmed present before this hardening even started): the same
        # newline-swallowing bug meant `find_git_push_invocations` never saw
        # `git push` in command position when it was the LAST of several
        # newline-separated lines in one Bash call -- the whole multi-line
        # command collapsed into ONE segment whose first word is `cd`, so the
        # segment was rejected outright before the `push` tokens buried later
        # in it were ever reached. This is the CANONICAL publish flow (cd,
        # add, commit, push) written as one multi-line tool call -- exactly
        # what a model produces when it batches a publication sequence into a
        # single call -- and the gate must still deny it (no scan, no
        # marker), not silently allow it as if no `git push` were present at
        # all. Verbatim shape from work-items/bugs/2026-07-26-push-gate-
        # never-fires-on-a-multi-line-push-command.md.
        self.assert_outcome(
            [user("commit and push")],
            "cd /repo\ngit add -A\ngit commit -m x\ngit push origin main",
            should_deny=True,
        )

    def test_powershell_file_pointing_at_an_unrelated_script_does_not_allow(self) -> None:
        # A PowerShell `-File` invocation of something OTHER than the
        # scanner must not be credited just because a clean-shaped line
        # happens to share its call id.
        ps_call = assistant_tool_use(
            "Bash", {"command": "powershell -File some_other_script.ps1"}, tool_id="toolu_ps_other"
        )
        ps_result = tool_result(
            "publication-safety: clean (tracked, examined 5 files)", tool_id="toolu_ps_other"
        )
        self.assert_outcome(
            [user("push the branch"), ps_call, ps_result],
            "git push origin main",
            should_deny=True,
        )

    # --- allow: legitimate scan-EXECUTION shapes must still open the gate,
    # proving the mention-vs-execution / solo-segment hardening did not
    # break real invocation forms (2026-07-26). ---

    def test_powershell_file_flag_running_the_real_scanner_allows(self) -> None:
        # The documented Windows fallback in agents-check-safety.md step
        # "Rules": `powershell -ExecutionPolicy Bypass -File
        # .../check-publication-safety.ps1`. Must keep working.
        ps_call = assistant_tool_use(
            "Bash",
            {"command": "powershell -ExecutionPolicy Bypass -File "
                        ".claude/agents/scripts/check-publication-safety.ps1"},
            tool_id="toolu_ps_file",
        )
        ps_result = tool_result(
            "publication-safety: clean (tracked, examined 5 files)", tool_id="toolu_ps_file"
        )
        self.assert_outcome(
            [user("push the branch"), ps_call, ps_result],
            "git push origin main",
            should_deny=False,
        )

    def test_powershell_command_flag_running_the_real_scanner_allows(self) -> None:
        # `-Command` carries a nested command STRING as its own value; this
        # must be re-tokenized and re-scanned (recursively, same parser),
        # not matched by a plain substring the way the old regex would have.
        ps_call = assistant_tool_use(
            "Bash",
            {"command": "powershell -Command \"& '.claude/agents/scripts/"
                        "check-publication-safety.ps1'\""},
            tool_id="toolu_ps_cmd",
        )
        ps_result = tool_result(
            "publication-safety: clean (tracked, examined 5 files)", tool_id="toolu_ps_cmd"
        )
        self.assert_outcome(
            [user("push the branch"), ps_call, ps_result],
            "git push origin main",
            should_deny=False,
        )

    def test_direct_exec_of_the_scanner_allows(self) -> None:
        # `./check-publication-safety.sh` with no interpreter prefix at all.
        direct_call = assistant_tool_use(
            "Bash", {"command": "./check-publication-safety.sh"}, tool_id="toolu_direct"
        )
        direct_result = tool_result(
            "publication-safety: clean (tracked, examined 2 files)", tool_id="toolu_direct"
        )
        self.assert_outcome(
            [user("push the branch"), direct_call, direct_result],
            "git push origin main",
            should_deny=False,
        )

    def test_codex_real_shell_command_name_still_allows(self) -> None:
        # Real Codex archived sessions on this machine use
        # `name: "shell_command"` for the shell tool, NOT the `"shell"` name
        # this module's own test fixtures elsewhere assume -- verified
        # against 65 real `function_call` entries, 2026-07-26. The
        # execution detector must not depend on that name at all.
        real_name_call = codex_function_call(
            "shell_command",
            '{"command": "bash .codex/skills/lead/scripts/check-publication-safety.sh"}',
            call_id="call_real_name",
        )
        real_name_result = codex_function_call_output(
            "publication-safety: clean (tracked, examined 4 files)", call_id="call_real_name"
        )
        self.assert_outcome(
            [user("push the branch"), real_name_call, real_name_result],
            "git push origin main",
            should_deny=False,
        )

    def test_codex_mention_only_grep_does_not_allow(self) -> None:
        # Codex-shape counterpart to the mention-only regression above: the
        # `arguments.command` string names the scanner as a grep target,
        # never runs it.
        mention_call = codex_function_call(
            "shell_command",
            '{"command": "grep -rn examined tests/ check-publication-safety.sh"}',
            call_id="call_mention",
        )
        mention_result = codex_function_call_output(
            "publication-safety: clean (tracked, examined 3 files)", call_id="call_mention"
        )
        self.assert_outcome(
            [user("push the branch"), mention_call, mention_result],
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
