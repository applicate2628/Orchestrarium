#!/usr/bin/env python3
"""Regression tests for the typed-routing PreToolUse hook (AUDIT mode).

The hook (`check-typed-routing.py`, Claude-only) warns -- never blocks -- when the
orchestrator dispatches the built-in catch-all `subagent_type: general-purpose`
for work that looks like typed specialist work. AUDIT mode: on a hit, ALWAYS
exits 0 and emits one line of JSON to stdout --
`{"hookSpecificOutput":{"hookEventName":<event>,"additionalContext":<warning>}}`
-- the model-visible delivery channel (see `hook_common.emit_advisory`); silent
and exit 0 otherwise. This replaced a stderr-plus-exit-1 form measured to reach
nobody on either provider line (see
work-items/bugs/2026-07-26-mcp-reminder-uses-the-once-per-session-form-its-
sibling-calls-broken.md).

CLAUDE-ONLY BY PLATFORM SEMANTICS. The hook keys on the subagent-dispatch tool.
Codex CLI has no analogous Agent-dispatch tool (src.codex/AGENTS.codex.md records
"Codex CLI has no analogous Agent-isolation"), so there is no Codex mirror -- this
test drives only the Claude copy, unlike the cross-pack sibling audit tests.

PHASE-0 CAPTURED ENVELOPE SHAPE (runtime, pinned as REAL_AGENT_FIXTURE below).
The dispatch tool_name was UNVERIFIED at design time (assumed "Task"). It was
captured from real session transcripts (~/.claude/projects/**/*.jsonl, 1121
Agent-dispatch tool_use blocks including THIS session's live transcript): the
tool_use `name` is "Agent" (NOT "Task"), and its `input` always carries
`subagent_type` + `description` + `prompt` (plus optional
`model`/`run_in_background`/`effort`/`isolation`). Per the official Claude Code
hooks reference, the PreToolUse envelope surfaces that tool_use verbatim as
top-level `tool_name` + `tool_input` (Claude Code copies the tool call's name and
input into the envelope), alongside standard wrapper fields (`session_id`,
`transcript_path`, `cwd`, `hook_event_name`, `permission_mode`) and `agent_id`
ONLY inside a subagent context. REAL_AGENT_FIXTURE below is that complete
PreToolUse envelope, built from the real captured tool_name+tool_input and the
documented wrapper fields; it is fed as a whole envelope, so it also proves the
hook ignores the wrapper fields it does not read. (A raw stdin dump of a live
PreToolUse envelope additionally needs a temporary dispatch-matcher hook in the
active settings.json -- a live-config change not performed from this subagent
session; the envelope's read fields are independently pinned by the 1121-sample
capture, the official docs, and the fail-safe test that a wrong tool_name makes
the hook inert.)
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / "src.claude" / "agents" / "hooks" / "check-typed-routing.py"
WRAPPER = REPO_ROOT / "src.claude" / "agents" / "hooks" / "check-typed-routing.ps1"
WARNING = "[typed-routing AUDIT]"

# A complete PreToolUse envelope for an Agent dispatch: the captured tool_name
# ("Agent") + a real general-purpose tool_input shape (keys verbatim from live
# transcripts: subagent_type/description/run_in_background/prompt), wrapped in
# the documented PreToolUse envelope fields. The prompt carries specialist
# signals ("Fix", ".ps1", "installer", "hook", "audit"). Feeding the whole
# envelope also proves the hook ignores wrapper fields it does not read.
#
# The three wrapper fields below are deliberately SYNTHETIC. Their only job is
# to be present and unread, so a captured session id and a concrete machine dev
# root would be published for nothing -- which is exactly what the
# publication-safety scan caught here on 2026-07-26. Keep them placeholder-shaped:
# the test's meaning is "these fields exist and are ignored", not "these are the
# real ones".
REAL_AGENT_FIXTURE = {
    "session_id": "00000000-0000-4000-8000-000000000000",
    "transcript_path": "~/.claude/projects/<project-dir>/00000000.jsonl",
    "cwd": "C:\\Users\\<you>\\dev\\<repo>",
    "hook_event_name": "PreToolUse",
    "permission_mode": "bypassPermissions",
    "tool_name": "Agent",
    "tool_input": {
        "subagent_type": "general-purpose",
        "description": "Add missing auto-invoke blocks",
        "run_in_background": True,
        "prompt": (
            "Fix an audit finding in the Orchestrarium monorepo: wire the new "
            "hook into scripts/install-claude.ps1 and the installer."
        ),
    },
}


def run_hook(envelope: object, raw: str | None = None) -> subprocess.CompletedProcess:
    stdin = raw if raw is not None else json.dumps(envelope, ensure_ascii=False)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def dispatch(
    subagent_type: object,
    *,
    description: str = "",
    prompt: str = "",
    tool_name: str = "Agent",
    extra: dict | None = None,
) -> dict:
    tool_input: dict = {"description": description, "prompt": prompt}
    if subagent_type is not None:
        tool_input["subagent_type"] = subagent_type
    envelope = {"tool_name": tool_name, "tool_input": tool_input}
    if extra:
        envelope.update(extra)
    return envelope


def _decode_context(stdout: str) -> tuple[str, str]:
    """Parse the hookSpecificOutput envelope; returns (hookEventName, additionalContext)."""
    payload = json.loads(stdout)
    specific = payload["hookSpecificOutput"]
    return specific["hookEventName"], specific["additionalContext"]


class TypedRoutingHookTests(unittest.TestCase):
    def assert_warns(self, envelope: object, raw: str | None = None) -> None:
        p = run_hook(envelope, raw)
        # AUDIT never BLOCKS (never exit 2) and never exits 1 either -- the
        # advisory now travels via stdout JSON, not a non-zero exit.
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stderr, "")
        event_name, context = _decode_context(p.stdout)
        self.assertEqual(event_name, "PreToolUse")
        self.assertIn(WARNING, context)
        # The remedy (the typed-roster pointer + typed-role guidance) must be present.
        self.assertIn(".claude/agents/", context)
        self.assertIn("subagent_type", context)

    def assert_silent(self, envelope: object, raw: str | None = None) -> None:
        p = run_hook(envelope, raw)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, "")
        self.assertEqual(p.stderr, "")

    # (a) general-purpose + specialist-signal -> exit 1 + stderr
    def test_general_purpose_with_specialist_signal_warns(self) -> None:
        for signal in ("implement the parser", "fix the .ps1 installer",
                       "review the design", "security audit", "toolchain build"):
            with self.subTest(signal=signal):
                self.assert_warns(dispatch("general-purpose", prompt=signal))

    def test_signal_in_description_field_also_warns(self) -> None:
        self.assert_warns(dispatch("general-purpose", description="refactor the module",
                                   prompt="see attached"))

    def test_casefolded_catch_all_warns(self) -> None:
        # subagent_type is compared casefolded.
        self.assert_warns(dispatch("General-Purpose", prompt="implement the feature"))

    # (b) general-purpose + no specialist-signal -> exit 0
    def test_general_purpose_without_signal_is_silent(self) -> None:
        self.assert_silent(dispatch("general-purpose",
                                    description="Summarize the meeting notes",
                                    prompt="Read the notes and list the open questions."))

    # defect-1 regression: word-bounded stems must NOT match inside unrelated words.
    def test_substring_false_positives_are_silent(self) -> None:
        for prompt in (
            "Collect all the test fixtures and list them",   # 'fix' inside 'fixtures'
            "Preview the rendered page and summarize it",     # 'review' inside 'Preview'
            "Perform an open-ended search across the repo",   # bare verb 'perform', not 'performance'
            "Read the changelog and describe the auditory cues",  # 'audit' inside 'auditory'
            "List the designated owners in the registry",     # 'design' inside 'designated'
        ):
            with self.subTest(prompt=prompt):
                self.assert_silent(dispatch("general-purpose", prompt=prompt))

    # defect-1 regression: the real word-boundary matches must still fire.
    def test_word_boundary_true_positives_fire(self) -> None:
        for prompt in (
            "fix the .ps1",
            "implement the token bucket",
            "review this diff",
            "improve the performance of the loop",   # 'performance', not bare 'perform'
            "run the security audit",
        ):
            with self.subTest(prompt=prompt):
                self.assert_warns(dispatch("general-purpose", prompt=prompt))

    # (c) a typed subagent_type -> exit 0
    def test_typed_role_is_silent_even_with_signal(self) -> None:
        for role in ("backend-engineer", "architecture-reviewer", "toolchain-engineer",
                     "platform-engineer", "Explore"):
            with self.subTest(role=role):
                self.assert_silent(dispatch(role, prompt="implement and review the .py hook"))

    # (d) agent_id present -> exit 0 (subagent-context skip)
    def test_subagent_context_skips(self) -> None:
        self.assert_silent(dispatch("general-purpose", prompt="implement the fix",
                                    extra={"agent_id": "worker-1"}))

    # (e) malformed/absent subagent_type -> exit 0 (fail-safe)
    def test_absent_subagent_type_is_silent(self) -> None:
        self.assert_silent(dispatch(None, prompt="implement the fix"))

    def test_non_string_subagent_type_is_silent(self) -> None:
        self.assert_silent(dispatch(123, prompt="implement the fix"))

    def test_non_dict_tool_input_is_silent(self) -> None:
        self.assert_silent({"tool_name": "Agent", "tool_input": "not-a-dict"})

    # Fail-safe: a wrong/absent tool_name makes the hook inert (the design's
    # assumed "Task" would never fire -- this locks the captured "Agent" shape in).
    def test_wrong_tool_name_is_inert(self) -> None:
        for name in ("Task", "Edit", "Bash", ""):
            with self.subTest(tool_name=name):
                self.assert_silent(dispatch("general-purpose", prompt="implement the fix",
                                            tool_name=name))

    # (f) the Phase-0 REAL captured Agent envelope fixture -> exit 1
    def test_real_captured_agent_fixture_warns(self) -> None:
        self.assert_warns(REAL_AGENT_FIXTURE)

    # fail-open on malformed input
    def test_malformed_envelope_fails_open(self) -> None:
        self.assert_silent(None, raw="not json {{{")

    def test_empty_stdin_fails_open(self) -> None:
        self.assert_silent(None, raw="")


@unittest.skipIf(
    not (shutil.which("pwsh") or shutil.which("powershell")),
    "no PowerShell host (pwsh/powershell) on PATH",
)
class TypedRoutingWrapperSmokeTests(unittest.TestCase):
    """Drive the ACTUAL .ps1 entry point under every available PowerShell host
    (pwsh 7 + Windows PowerShell 5.1) -- a .py-only test would not catch a broken
    stdin pipe or a wrapper hard-coding exit 0."""

    def _interpreters(self) -> list[str]:
        return [p for p in (shutil.which("pwsh"), shutil.which("powershell")) if p]

    def _run_ps1(self, interp: str, stdin: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [interp, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(WRAPPER)],
            input=stdin, capture_output=True, text=True, encoding="utf-8",
        )

    def test_wrapper_fails_open_on_empty_and_malformed(self) -> None:
        for interp in self._interpreters():
            for stdin in ("", "not json {{{"):
                with self.subTest(interp=Path(interp).stem, stdin=stdin[:8]):
                    p = self._run_ps1(interp, stdin)
                    self.assertEqual(p.returncode, 0, p.stderr)
                    self.assertEqual(p.stdout.strip(), "")
                    self.assertEqual(p.stderr.strip(), "")

    def test_wrapper_exits_zero_and_warns_via_stdout_on_a_real_hit(self) -> None:
        payload = json.dumps(REAL_AGENT_FIXTURE, ensure_ascii=False)
        for interp in self._interpreters():
            with self.subTest(interp=Path(interp).stem):
                p = self._run_ps1(interp, payload)
                self.assertEqual(p.returncode, 0,
                                 f"expected exit 0 on a hit; stdout={p.stdout!r} stderr={p.stderr!r}")
                self.assertEqual(p.stderr, "")
                _event_name, context = _decode_context(p.stdout)
                self.assertIn(WARNING, context)


if __name__ == "__main__":
    unittest.main()
