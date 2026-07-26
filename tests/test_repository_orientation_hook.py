"""Behavioral tests for the repository-orientation PreToolUse audit hook.

The hook is a process backstop, not a semantic canon detector. It warns before
risky repository-local actions when assistant-authored prose in the current
turn lacks one valid, task-scoped ``REPOSITORY ORIENTATION:`` record. It always
allows, fails open, and never scans repository prose for deprecation language.
On a hit it emits one line of JSON to stdout --
``{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"..."}}``
-- the model-visible delivery channel (see ``hook_common.emit_advisory``); always
exits 0. This replaced a stderr-plus-exit-1 form measured to reach nobody on
either provider line (see
work-items/bugs/2026-07-26-mcp-reminder-uses-the-once-per-session-form-its-
sibling-calls-broken.md).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
HOOKS = (
    ROOT / "src.claude" / "agents" / "hooks" / "check-repository-orientation.py",
    ROOT / "src.codex" / "skills" / "lead" / "hooks" / "check-repository-orientation.py",
)
WARNING = "[repository-orientation AUDIT]"
STALE_WARNING = "[repository-orientation STALE-TARGET AUDIT]"


def claude_user(text: str) -> dict:
    return {
        "type": "user",
        "message": {"role": "user", "content": [{"type": "text", "text": text}]},
    }


def claude_assistant(text: str) -> dict:
    return {
        "type": "assistant",
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }


def claude_tool_result(text: str) -> dict:
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "content": text}],
        },
    }


def codex_user(text: str) -> dict:
    return {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
        },
    }


def codex_assistant(text: str) -> dict:
    return {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": text}],
        },
    }


def codex_tool_output(text: str) -> dict:
    return {
        "type": "response_item",
        "payload": {"type": "function_call_output", "output": text},
    }


def orientation(
    *,
    scope: str = ".",
    status: str = "mutable",
    workflow: str = "scripts/run.py",
    protected: str = "Archive",
    evidence: str = "AGENTS.md:9,docs/guide.md:12",
) -> str:
    return (
        "REPOSITORY ORIENTATION: "
        f"scope={scope}; status={status}; workflow={workflow}; "
        f"protected={protected}; evidence={evidence}"
    )


def write_transcript(repo: Path, entries: list[dict]) -> Path:
    path = repo / "transcript.jsonl"
    path.write_text(
        "".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in entries),
        encoding="utf-8",
    )
    return path


def run_hook(
    script: Path,
    repo: Path,
    entries: list[dict],
    *,
    tool_name: str = "Edit",
    tool_input: dict | None = None,
    extra: dict | None = None,
) -> subprocess.CompletedProcess:
    transcript = write_transcript(repo, entries)
    envelope = {
        "cwd": str(repo),
        "transcript_path": str(transcript),
        "tool_name": tool_name,
        "tool_input": tool_input or {"file_path": str(repo / "src" / "app.py")},
    }
    if extra:
        envelope.update(extra)
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(envelope, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


class RepositoryOrientationHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / ".git").mkdir()
        (self.repo / "src").mkdir()
        (self.repo / "scripts").mkdir()
        (self.repo / "scripts" / "run.py").write_text("print('run')\n", encoding="utf-8")
        (self.repo / "AGENTS.md").write_text("governance\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def assert_warns(self, entries: list[dict], **kwargs: object) -> None:
        for script in HOOKS:
            with self.subTest(script=script):
                result = run_hook(script, self.repo, entries, **kwargs)
                # AUDIT never BLOCKS (never exit 2) and never uses a non-zero
                # exit for a hit either -- the advisory travels via stdout
                # JSON, always exit 0 (see hook_common.emit_advisory).
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                payload = json.loads(result.stdout)
                specific = payload["hookSpecificOutput"]
                self.assertEqual(specific["hookEventName"], "PreToolUse")
                self.assertIn(WARNING, specific["additionalContext"])

    def assert_silent(self, entries: list[dict], **kwargs: object) -> None:
        for script in HOOKS:
            with self.subTest(script=script):
                result = run_hook(script, self.repo, entries, **kwargs)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "")

    def test_edit_before_record_warns(self) -> None:
        self.assert_warns([claude_user("Update the implementation."), claude_assistant("I will edit it.")])

    def test_repository_runner_before_record_warns(self) -> None:
        self.assert_warns(
            [claude_user("Run the current workflow."), claude_assistant("Starting the run.")],
            tool_name="Bash",
            tool_input={"command": "python scripts/run.py"},
        )

    def test_valid_in_scope_record_is_silent_for_claude_and_codex_shapes(self) -> None:
        cases = (
            [claude_user("Update src."), claude_assistant(orientation(scope="src"))],
            [codex_user("Update src."), codex_assistant(orientation(scope="src"))],
        )
        for entries in cases:
            with self.subTest(shape=entries[0]["type"]):
                self.assert_silent(entries)

    def test_tool_output_record_cannot_satisfy_gate(self) -> None:
        cases = (
            [claude_user("Update src."), claude_tool_result(orientation(scope="src"))],
            [codex_user("Update src."), codex_tool_output(orientation(scope="src"))],
        )
        for entries in cases:
            with self.subTest(shape=entries[0]["type"]):
                self.assert_warns(entries)

    def test_scope_mismatch_warns(self) -> None:
        self.assert_warns(
            [claude_user("Update src."), claude_assistant(orientation(scope="docs"))]
        )

    def test_conflict_status_warns(self) -> None:
        self.assert_warns(
            [claude_user("Update src."), claude_assistant(orientation(scope="src", status="conflict"))]
        )

    def test_malformed_or_duplicate_records_warn(self) -> None:
        malformed = "REPOSITORY ORIENTATION: scope=src; status=mutable; workflow=scripts/run.py"
        duplicate = orientation(scope="src") + "\n" + orientation(scope="src")
        for record in (malformed, duplicate, orientation(scope="src", evidence="no-line-citation")):
            with self.subTest(record=record):
                self.assert_warns([claude_user("Update src."), claude_assistant(record)])

    def test_archived_path_gets_stronger_warning_without_historical_scope(self) -> None:
        archived = self.repo / "Archive" / "snapshot.md"
        archived.parent.mkdir()
        entries = [
            claude_user("Inspect the repository."),
            claude_assistant(orientation(scope="Archive", status="archived")),
        ]
        for script in HOOKS:
            with self.subTest(script=script):
                result = run_hook(
                    script,
                    self.repo,
                    entries,
                    tool_input={"file_path": str(archived)},
                )
                # A hit (even the stale-target-only warning) always exits 0 --
                # never a non-zero exit, never 2 (block).
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stderr, "")
                payload = json.loads(result.stdout)
                self.assertIn(STALE_WARNING, payload["hookSpecificOutput"]["additionalContext"])

    def test_archived_path_is_silent_with_matching_status_and_user_approved_scope(self) -> None:
        archived = self.repo / "Archive" / "snapshot.md"
        archived.parent.mkdir()
        prose = orientation(scope="Archive", status="archived") + (
            "\nUSER-APPROVED HISTORICAL SCOPE: edit this archived snapshot as explicitly requested."
        )
        self.assert_silent(
            [claude_user("Edit the archived snapshot."), claude_assistant(prose)],
            tool_input={"file_path": str(archived)},
        )

    def test_deprecation_words_and_legacy_segments_do_not_infer_status(self) -> None:
        legacy = self.repo / "legacy" / "module.py"
        legacy.parent.mkdir()
        prose = orientation(scope="legacy", status="mutable") + (
            "\nA README excerpt mentions deprecated and superseded examples."
        )
        self.assert_silent(
            [claude_user("Update the live legacy-named module."), claude_assistant(prose)],
            tool_input={"file_path": str(legacy)},
        )

    def test_apply_patch_targets_are_scope_checked(self) -> None:
        patch = "*** Begin Patch\n*** Update File: src/app.py\n@@\n-old\n+new\n*** End Patch"
        self.assert_warns(
            [claude_user("Update src."), claude_assistant("Applying the patch.")],
            tool_name="apply_patch",
            tool_input={"patch": patch},
        )
        self.assert_silent(
            [claude_user("Update src."), claude_assistant(orientation(scope="src"))],
            tool_name="apply_patch",
            tool_input={"patch": patch},
        )

    def test_discovery_only_shell_commands_are_silent_without_record(self) -> None:
        commands = (
            "rg --files",
            "Get-ChildItem -Force",
            "git status --short",
            "git log -1 --oneline",
            "git diff --check",
            "git show HEAD:README.md",
            "Test-Path scripts/run.py",
            "Get-Content README.md",
        )
        entries = [claude_user("Orient first."), claude_assistant("Inspecting only.")]
        for command in commands:
            with self.subTest(command=command):
                self.assert_silent(entries, tool_name="Bash", tool_input={"command": command})

    def test_exempt_artifact_write_is_silent_without_record(self) -> None:
        entries = [claude_user("Record the session."), claude_assistant("Writing the report.")]
        for segment in (".scratch", ".reports", ".plans", "work-items"):
            with self.subTest(segment=segment):
                target = self.repo / segment / "note.md"
                self.assert_silent(entries, tool_input={"file_path": str(target)})

    def test_subagent_envelope_skips(self) -> None:
        self.assert_silent(
            [claude_user("Update src."), claude_assistant("Editing now.")],
            extra={"agent_id": "worker-1"},
        )

    def test_malformed_envelope_fails_open(self) -> None:
        for script in HOOKS:
            with self.subTest(script=script):
                result = subprocess.run(
                    [sys.executable, str(script)],
                    input="{not-json",
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "")

    def test_transcript_without_genuine_user_anchor_fails_open(self) -> None:
        self.assert_silent([claude_assistant("No anchored user task exists in this tail.")])

    def test_shell_quoting_and_non_command_positions_do_not_warn(self) -> None:
        entries = [claude_user("Inspect only."), claude_assistant("No execution.")]
        commands = (
            'Write-Output "python scripts/run.py"',
            "echo 'pytest tests/'",
            "rg 'python scripts/run.py' README.md",
            "python 'scripts/run.py",  # tokenizer failure must fail open
        )
        for command in commands:
            with self.subTest(command=command):
                self.assert_silent(entries, tool_name="Bash", tool_input={"command": command})

    def test_compound_command_warns_only_when_a_real_risky_segment_exists(self) -> None:
        entries = [claude_user("Inspect then run."), claude_assistant("Proceeding.")]
        self.assert_silent(
            entries,
            tool_name="Bash",
            tool_input={"command": "rg --files; git status --short"},
        )
        self.assert_warns(
            entries,
            tool_name="Bash",
            tool_input={"command": "rg --files; python scripts/run.py"},
        )


if __name__ == "__main__":
    unittest.main()
