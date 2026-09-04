"""Payload-shape regression tests for warn-only PreToolUse audits.

THE BUG THIS FILE GUARDS AGAINST (work-items/bugs/2026-07-26-mcp-reminder-uses-
the-once-per-session-form-its-sibling-calls-broken.md): all six warn-only
PreToolUse audits (`check-machine-local-path`, `check-no-trash-in-repo`,
`check-stale-relation-residue`, `check-repository-orientation`, the universal
`check-mcp-momentum`, and Claude `check-typed-routing`) FIRED CORRECTLY and delivered their
warning to NOBODY -- a stderr-plus-exit-1 PreToolUse hook was measured to reach
neither the model nor a reliably-checked operator channel on either Claude Code
2.1.220 or Codex CLI 0.145.0. "The audit fired" was never the defect; DELIVERY
was. A test suite that only asserts the predicate matched (as every existing
per-hook test file did before this fix) reproduces exactly that blind spot.

This file asserts the EMITTED PAYLOAD SHAPE on a real matched finding, driven
through the actual hook subprocess (not a mock): stdout is valid JSON, its
`hookSpecificOutput.hookEventName` equals the RECEIVED event (never a
hardcoded constant -- see the event-name trap below), `additionalContext`
carries the warning text, exit code is 0, and stderr is empty.

THE EVENT-NAME TRAP. Claude Code silently discards the entire
`hookSpecificOutput` object when `hookEventName` does not match the event that
actually fired (measured: "Hook returned incorrect event name: expected
'PreToolUse' but got 'PostToolUse'"). A shared emitter that hardcodes
`"PreToolUse"` would work today (every one of these six audits happens to be
registered on PreToolUse) and silently break the moment any one of them is ever
registered on a different event. `test_hook_event_name_is_read_from_envelope_
not_hardcoded` below feeds each hook an envelope whose `hook_event_name` is
deliberately NOT "PreToolUse" and asserts the emitted `hookEventName` matches
the FED value verbatim -- the only test shape that can actually falsify a
hardcoded constant (feeding the hook's own real registered event would pass
identically whether the code reads the envelope or hardcodes the same string).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

CLAUDE_HOOKS = REPO_ROOT / "src.claude" / "agents" / "hooks"
UNIVERSAL_HOOKS = REPO_ROOT / "scripts" / "universal-hooks" / "hooks"
CODEX_HOOKS = REPO_ROOT / "src.codex" / "skills" / "lead" / "hooks"

# The five audits mirrored across all three trees, plus the Claude-only sixth
# (check-typed-routing has no Codex analogue -- there is no subagent-dispatch
# tool on that line; see test_typed_routing_hook.py's own module docstring).
SHARED_AUDIT_TREES = (CLAUDE_HOOKS, UNIVERSAL_HOOKS, CODEX_HOOKS)
CLAUDE_ONLY_TREES = (CLAUDE_HOOKS,)
MCP_AUDIT_TREES = (UNIVERSAL_HOOKS, CODEX_HOOKS)


def run_hook(script: Path, envelope: object, *, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(envelope, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def assert_payload_shape(
    case: unittest.TestCase,
    result: subprocess.CompletedProcess,
    *,
    expected_event: str,
    warning_marker: str,
) -> None:
    """The one shape check every hit-path caller in this file uses."""
    case.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
    case.assertEqual(result.stderr, "", "AUDIT mode must never write to stderr")
    case.assertTrue(result.stdout.strip(), "expected a non-empty stdout advisory")
    payload = json.loads(result.stdout)  # stdout must be valid JSON
    case.assertEqual(set(payload), {"hookSpecificOutput"}, f"unexpected top-level shape: {payload!r}")
    specific = payload["hookSpecificOutput"]
    case.assertEqual(set(specific), {"hookEventName", "additionalContext"}, f"unexpected inner shape: {specific!r}")
    case.assertIsInstance(specific["hookEventName"], str)
    case.assertIsInstance(specific["additionalContext"], str)
    case.assertEqual(specific["hookEventName"], expected_event)
    case.assertIn(warning_marker, specific["additionalContext"])


def _repo_orientation_fixture() -> tuple[Path, dict]:
    """A git-root repo + transcript with no REPOSITORY ORIENTATION: record, so
    the hit path fires (mirrors test_repository_orientation_hook.py)."""
    repo = Path(tempfile.mkdtemp())
    (repo / ".git").mkdir()
    (repo / "src").mkdir()
    entries = [
        {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "Update it."}]}},
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Editing."}]}},
    ]
    transcript = repo / "transcript.jsonl"
    transcript.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    envelope = {
        "cwd": str(repo),
        "transcript_path": str(transcript),
        "tool_name": "Edit",
        "tool_input": {"file_path": str(repo / "src" / "app.py")},
    }
    return repo, envelope


# One row per audit: (script filename, trees it lives in, envelope-builder,
# warning-marker substring). The envelope-builder takes the desired
# hook_event_name value (or None to omit the field) and an optional env dict.
def _machine_local_path_envelope(event: str | None) -> dict:
    envelope = {"tool_input": {"file_path": "README.md", "content": "see C:/" + "Users" + "/realuser/x"}}
    if event is not None:
        envelope["hook_event_name"] = event
    return envelope


def _no_trash_envelope(event: str | None) -> dict:
    envelope = {"cwd": "/tmp", "tool_input": {"command": "git worktree add ../wt"}}
    if event is not None:
        envelope["hook_event_name"] = event
    return envelope


def _stale_relation_envelope(event: str | None) -> dict:
    envelope = {"tool_input": {"file_path": "docs/live-doc.md", "content": "this is a deprecated alias for bar"}}
    if event is not None:
        envelope["hook_event_name"] = event
    return envelope


def _mcp_momentum_envelope(event: str | None) -> dict:
    envelope = {"tool_name": "Grep", "tool_input": {"pattern": "def parse_config"}}
    if event is not None:
        envelope["hook_event_name"] = event
    return envelope


def _typed_routing_envelope(event: str | None) -> dict:
    envelope = {
        "tool_name": "Agent",
        "tool_input": {
            "subagent_type": "general-purpose",
            "description": "",
            "prompt": "implement the fix",
        },
    }
    if event is not None:
        envelope["hook_event_name"] = event
    return envelope


SIMPLE_CASES = (
    ("check-machine-local-path.py", SHARED_AUDIT_TREES, _machine_local_path_envelope,
     "[machine-local-path AUDIT]", None),
    ("check-no-trash-in-repo.py", SHARED_AUDIT_TREES, _no_trash_envelope,
     "[stray-artifact AUDIT]", None),
    ("check-stale-relation-residue.py", SHARED_AUDIT_TREES, _stale_relation_envelope,
     "[stale-relation-residue AUDIT]", None),
    ("check-mcp-momentum.py", MCP_AUDIT_TREES, _mcp_momentum_envelope,
     "[mcp-momentum AUDIT]", None),
    ("check-typed-routing.py", CLAUDE_ONLY_TREES, _typed_routing_envelope,
     "[typed-routing AUDIT]", None),
)


class SimpleAuditPayloadShapeTests(unittest.TestCase):
    """The five audits whose hit path needs only a tool_input/tool_name envelope."""

    def test_default_event_name_is_pretooluse_when_envelope_omits_it(self) -> None:
        for name, trees, build, marker, env_kind in SIMPLE_CASES:
            env = None
            for tree in trees:
                script = tree / name
                with self.subTest(script=str(script.relative_to(REPO_ROOT))):
                    result = run_hook(script, build(None), env=env)
                    assert_payload_shape(self, result, expected_event="PreToolUse", warning_marker=marker)

    def test_hook_event_name_is_read_from_envelope_not_hardcoded(self) -> None:
        """THE falsifying test: feed an event name that is NOT the hook's real
        registered event (PostToolUse, never PreToolUse) and assert the emitted
        hookEventName is the FED value, not a hardcoded "PreToolUse". A hardcoded
        emitter fails this test; a pass-through emitter (hook_common.emit_advisory)
        passes it."""
        for name, trees, build, marker, env_kind in SIMPLE_CASES:
            env = None
            for tree in trees:
                script = tree / name
                with self.subTest(script=str(script.relative_to(REPO_ROOT))):
                    result = run_hook(script, build("PostToolUse"), env=env)
                    assert_payload_shape(self, result, expected_event="PostToolUse", warning_marker=marker)

    def test_stdout_is_the_only_output_channel(self) -> None:
        """Locks the channel migration itself: nothing rides on stderr any more."""
        for name, trees, build, marker, env_kind in SIMPLE_CASES:
            env = None
            for tree in trees:
                script = tree / name
                with self.subTest(script=str(script.relative_to(REPO_ROOT))):
                    result = run_hook(script, build(None), env=env)
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(result.stderr, "")
                    self.assertIn(marker, result.stdout)


class RepositoryOrientationPayloadShapeTests(unittest.TestCase):
    """check-repository-orientation needs a transcript + git root fixture, so it
    gets its own harness rather than the flat envelope-builder table above."""

    TREES = (CLAUDE_HOOKS, UNIVERSAL_HOOKS, CODEX_HOOKS)
    MARKER = "[repository-orientation AUDIT]"

    def _envelope(self, event: str | None) -> tuple[Path, dict]:
        repo, envelope = _repo_orientation_fixture()
        if event is not None:
            envelope["hook_event_name"] = event
        return repo, envelope

    def test_default_event_name_is_pretooluse_when_envelope_omits_it(self) -> None:
        for tree in self.TREES:
            script = tree / "check-repository-orientation.py"
            with self.subTest(script=str(script.relative_to(REPO_ROOT))):
                _repo, envelope = self._envelope(None)
                result = run_hook(script, envelope)
                assert_payload_shape(self, result, expected_event="PreToolUse", warning_marker=self.MARKER)

    def test_hook_event_name_is_read_from_envelope_not_hardcoded(self) -> None:
        for tree in self.TREES:
            script = tree / "check-repository-orientation.py"
            with self.subTest(script=str(script.relative_to(REPO_ROOT))):
                _repo, envelope = self._envelope("PostToolUse")
                result = run_hook(script, envelope)
                assert_payload_shape(self, result, expected_event="PostToolUse", warning_marker=self.MARKER)


if __name__ == "__main__":
    unittest.main()
