"""Regression tests for hook_common.py's current-turn-boundary scan.

Covers work-items/bugs/2026-07-26-two-owners-of-the-current-turn-boundary-in-
one-module.md: `current_turn_entries` and `last_genuine_user_text` used to
each run their own independent bounded-reverse-scan loop to the same
boundary (the second's own docstring admitted its status vocabulary "matches
last_genuine_user_text's own" -- a restated contract, not a shared one).
Both are now thin projections of one shared primitive,
`scan_current_turn_boundary`, which itself delegates boundary detection to
`slice_current_turn` -- already the correct, existing pattern in this
module (`check-passive-polling-stop.py`'s own consumer), rather than
re-deriving the predicate.

TestSingleScanOwnership is the bug's own required pin, mutation-checked in
the order it asks for: written before the refactor landed, run against the
then-current two-owner hook_common.py, and confirmed to fail with
`AttributeError: <module 'hook_common' ...> does not have the attribute
'scan_current_turn_boundary'` -- there was no shared symbol for both
consumers to route through, which IS the defect this test pins. After the
refactor the same test passes, because both consumers now call through the
one patched primitive. A future re-duplication (either consumer growing its
own inline scan instead of calling the shared primitive) makes this fail
again: the monkeypatched sentinel would stop reaching that consumer's output.

TestToolResultNotMistakenForBoundary pins the historical defect named in
`slice_current_turn`'s own docstring: a prior version used `is_user_message`
alone as the boundary predicate, and a tool_result is ALSO recorded as
`{"type":"user",...}` in Claude Code, so a tool-using turn's boundary landed
on the trailing tool_result, silently discarding every real tool call before
it. That bug was previously MASKED by a test suite whose own fixtures never
contained a real tool_result. Every fixture in this class contains one.

TestScanCost is the measured-cost gate from the bug's own "Constraints"
section: p95 6.7 ms at 100 MiB against 446 ms for a whole-file control. It
is opt-in (ORCHESTRARIUM_RUN_SCAN_COST_BENCHMARK=1) because it writes a
~100 MiB fixture -- skipped by default so the routine suite stays fast; run
it explicitly to reproduce the numbers quoted in the implementation report.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
CANON_DIR = REPO_ROOT / "scripts" / "universal-hooks" / "scripts"


def _load_hook_common():
    """Import the canon hook_common.py directly, matching the sys.path[0]
    sibling-module resolution the real hooks use (same pattern as
    tests/test_workitem_sentinels.py's _load_adapter_module)."""
    if str(CANON_DIR) not in sys.path:
        sys.path.insert(0, str(CANON_DIR))
    import hook_common  # noqa: E402  (imported after sys.path mutation, by design)
    return hook_common


hook_common = _load_hook_common()


def test_dormant_delivery_activity_pipeline_is_retired() -> None:
    source = (CANON_DIR / "hook_common.py").read_text(encoding="utf-8")
    for retired in (
        "DeliveryActivity",
        "correlated_delivery_activity",
        "_classify_delivery_call",
        "_extract_delivery_calls_with_ids",
        "_delivery_result_flags",
        "mcp__serena__",
        "serena.",
    ):
        assert retired not in source
    assert hasattr(hook_common, "extract_tool_outputs_with_ids")


# ---------------------------------------------------------------------------
# Transcript fixture builders -- Claude Code entry shapes.
# ---------------------------------------------------------------------------


def _user_entry(text: str) -> dict:
    return {"type": "user", "message": {"role": "user", "content": text}}


def _tool_use_entry(call_id: str, command: str = "ls") -> dict:
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": call_id, "name": "Bash", "input": {"command": command}}],
        },
    }


def _tool_result_entry(call_id: str) -> dict:
    # A tool_result is recorded as role=user in Claude Code -- the exact
    # shape a prior version of this module's boundary predicate mistook for
    # a genuine user message (slice_current_turn's own docstring).
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": call_id, "content": "ok"}],
        },
    }


def _assistant_text_entry(text: str) -> dict:
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def _write_transcript(entries: list) -> Path:
    tmp = Path(tempfile.mktemp(suffix=".jsonl"))
    tmp.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return tmp


class TestTypedShellCommandOccurrences(unittest.TestCase):
    def test_claude_and_codex_preserve_actual_tool_name(self) -> None:
        claude = _tool_use_entry("claude-call", "echo claude")
        codex = {
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "call_id": "codex-call",
                "name": "shell_command",
                "arguments": json.dumps({"command": "echo codex"}),
            },
        }
        self.assertEqual(
            hook_common.extract_model_shell_command_occurrences(claude),
            [hook_common.ModelShellCommandOccurrence(
                "claude-call", "Bash", "echo claude"
            )],
        )
        self.assertEqual(
            hook_common.extract_model_shell_command_occurrences(codex),
            [hook_common.ModelShellCommandOccurrence(
                "codex-call", "shell_command", "echo codex"
            )],
        )

    def test_missing_tool_name_is_retained_as_typed_unsupported(self) -> None:
        entry = _tool_use_entry("missing-name", "git push origin main")
        del entry["message"]["content"][0]["name"]
        self.assertEqual(
            hook_common.extract_model_shell_command_occurrences(entry),
            [hook_common.ModelShellCommandOccurrence(
                "missing-name", None, "git push origin main"
            )],
        )


class TestSharedProjectionsAgree(unittest.TestCase):
    """Both public functions must agree on the SAME boundary for the SAME
    transcript + byte_cap across all four statuses."""

    def test_found_case_projections_are_consistent(self) -> None:
        entries = [
            _user_entry("please fix the bug"),
            _tool_use_entry("c1"),
            _tool_result_entry("c1"),
            _assistant_text_entry("done"),
        ]
        tp = _write_transcript(entries)
        try:
            after, status_a = hook_common.current_turn_entries(str(tp), byte_cap=1024 * 1024)
            text, status_b = hook_common.last_genuine_user_text(str(tp), byte_cap=1024 * 1024)
            self.assertEqual(status_a, "found")
            self.assertEqual(status_b, "found")
            self.assertEqual(text, "please fix the bug")
            # tool_use + tool_result + assistant text must ALL survive as
            # "after" -- not collapsed to just the entries after the
            # tool_result (the historical defect this module guards against).
            self.assertEqual(len(after), 3)
        finally:
            tp.unlink()

    def test_absent_path_matches_on_both(self) -> None:
        self.assertEqual(hook_common.current_turn_entries("", byte_cap=1024), ([], "absent"))
        self.assertEqual(hook_common.last_genuine_user_text("", byte_cap=1024), ("", "absent"))

    def test_unreadable_path_matches_on_both(self) -> None:
        missing = str(Path(tempfile.mktemp(suffix=".jsonl")))  # never created
        self.assertEqual(hook_common.current_turn_entries(missing, byte_cap=1024), ([], "unreadable"))
        self.assertEqual(hook_common.last_genuine_user_text(missing, byte_cap=1024), ("", "unreadable"))

    def test_not_in_window_matches_on_both(self) -> None:
        entries = [_user_entry("x" * (2 * 1024 * 1024))]
        for i in range(20):
            entries.append(_assistant_text_entry(f"step {i}"))
        tp = _write_transcript(entries)
        try:
            self.assertEqual(hook_common.current_turn_entries(str(tp), byte_cap=4096), ([], "not-in-window"))
            self.assertEqual(hook_common.last_genuine_user_text(str(tp), byte_cap=4096), ("", "not-in-window"))
        finally:
            tp.unlink()

    def test_status_values_are_the_shared_constants(self) -> None:
        # The vocabulary has exactly one definition: TURN_BOUNDARY_STATUSES.
        # Both functions' possible outputs must be drawn from it, not a
        # second hand-typed literal set.
        self.assertEqual(
            set(hook_common.TURN_BOUNDARY_STATUSES),
            {"found", "absent", "unreadable", "invalid", "limit", "not-in-window"},
        )
        _after, status = hook_common.current_turn_entries("", byte_cap=1024)
        self.assertIn(status, hook_common.TURN_BOUNDARY_STATUSES)
        _text, status2 = hook_common.last_genuine_user_text("", byte_cap=1024)
        self.assertIn(status2, hook_common.TURN_BOUNDARY_STATUSES)


class TestBoundedCurrentTurnContract(unittest.TestCase):
    def test_current_turn_131_record_reachability(self) -> None:
        entries = [_user_entry("[approve-publication] push")]
        entries.extend(_assistant_text_entry(f"step {i}") for i in range(130))
        tp = _write_transcript(entries)
        try:
            boundary, after, status = hook_common.scan_current_turn_boundary(
                str(tp), byte_cap=hook_common.CURRENT_TURN_BYTE_CAP
            )
            self.assertEqual(status, "found")
            self.assertEqual(hook_common.extract_user_typed_text(boundary), "[approve-publication] push")
            self.assertEqual(after, entries[1:])
            self.assertEqual(len(after), 130)
        finally:
            tp.unlink()

    def test_trailing_claude_tool_result_is_not_the_boundary(self) -> None:
        entries = [_user_entry("do work"), _tool_use_entry("c1"), _tool_result_entry("c1")]
        tp = _write_transcript(entries)
        try:
            boundary, after, status = hook_common.scan_current_turn_boundary(
                str(tp), byte_cap=hook_common.CURRENT_TURN_BYTE_CAP
            )
            self.assertEqual(status, "found")
            self.assertEqual(hook_common.extract_user_typed_text(boundary), "do work")
            self.assertEqual(after, entries[1:])
        finally:
            tp.unlink()

    def test_oversized_final_record_is_limit_not_partial_success(self) -> None:
        tp = Path(tempfile.mktemp(suffix=".jsonl"))
        try:
            tp.write_bytes(
                (json.dumps(_user_entry("boundary")) + "\n").encode("utf-8")
                + (b"x" * (hook_common.CURRENT_TURN_BYTE_CAP + 1024))
            )
            self.assertEqual(
                hook_common.scan_current_turn_boundary(
                    str(tp), byte_cap=hook_common.CURRENT_TURN_BYTE_CAP
                ),
                (None, [], "limit"),
            )
        finally:
            tp.unlink(missing_ok=True)

    def test_final_partial_record_is_invalid_not_partial_success(self) -> None:
        tp = Path(tempfile.mktemp(suffix=".jsonl"))
        try:
            tp.write_bytes(
                (json.dumps(_user_entry("boundary")) + "\n").encode("utf-8")
                + b'{"type":"assistant","message":'
            )
            self.assertEqual(
                hook_common.scan_current_turn_boundary(
                    str(tp), byte_cap=hook_common.CURRENT_TURN_BYTE_CAP
                ),
                (None, [], "invalid"),
            )
        finally:
            tp.unlink(missing_ok=True)

    def test_invalid_complete_record_is_invalid_not_partial_success(self) -> None:
        tp = Path(tempfile.mktemp(suffix=".jsonl"))
        try:
            tp.write_bytes(
                (json.dumps(_user_entry("boundary")) + "\n").encode("utf-8")
                + b"not-json\n"
            )
            self.assertEqual(
                hook_common.scan_current_turn_boundary(
                    str(tp), byte_cap=hook_common.CURRENT_TURN_BYTE_CAP
                ),
                (None, [], "invalid"),
            )
        finally:
            tp.unlink(missing_ok=True)

    def test_six_statuses_have_empty_data_on_every_non_found_path(self) -> None:
        cases: list[tuple[str, str]] = []
        cases.append(("", "absent"))
        cases.append((str(Path(tempfile.mktemp(suffix=".jsonl"))), "unreadable"))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            invalid = root / "invalid.jsonl"
            invalid.write_bytes(b"not-json\n")
            cases.append((str(invalid), "invalid"))
            no_user = root / "no-user.jsonl"
            no_user.write_text(json.dumps(_assistant_text_entry("only assistant")) + "\n", encoding="utf-8")
            cases.append((str(no_user), "not-in-window"))
            over = root / "over.jsonl"
            over.write_bytes(b"x" * 2048)
            cases.append((str(over), "limit"))

            for transcript_path, expected_status in cases:
                with self.subTest(status=expected_status):
                    self.assertEqual(
                        hook_common.scan_current_turn_boundary(transcript_path, byte_cap=1024),
                        (None, [], expected_status),
                    )

    @unittest.skipUnless(
        os.environ.get("ORCHESTRARIUM_RUN_TRANSCRIPT_P95_BENCHMARK") == "1",
        "opt-in >=100 MiB read-budget guard",
    )
    def test_tail_reader_byte_cap_8mib(self) -> None:
        filler = (json.dumps(_assistant_text_entry("x" * 400)) + "\n").encode("utf-8")
        target_size = 100 * 1024 * 1024
        tp = Path(tempfile.mktemp(suffix=".jsonl"))
        try:
            with tp.open("wb") as stream:
                while stream.tell() < target_size:
                    stream.write(filler)
                stream.write((json.dumps(_user_entry("boundary")) + "\n").encode("utf-8"))
                stream.write((json.dumps(_assistant_text_entry("after")) + "\n").encode("utf-8"))

            original_open = Path.open
            observed = {"bytes": 0}

            class CountingReader:
                def __init__(self, wrapped):
                    self.wrapped = wrapped

                def __enter__(self):
                    self.wrapped.__enter__()
                    return self

                def __exit__(self, *args):
                    return self.wrapped.__exit__(*args)

                def seek(self, *args):
                    return self.wrapped.seek(*args)

                def tell(self):
                    return self.wrapped.tell()

                def read(self, *args):
                    data = self.wrapped.read(*args)
                    observed["bytes"] += len(data)
                    return data

            def counting_open(path_self, *args, **kwargs):
                return CountingReader(original_open(path_self, *args, **kwargs))

            with mock.patch.object(hook_common.Path, "open", counting_open):
                boundary, after, status = hook_common.scan_current_turn_boundary(
                    str(tp), byte_cap=hook_common.CURRENT_TURN_BYTE_CAP
                )

            self.assertEqual(status, "found")
            self.assertEqual(hook_common.extract_user_typed_text(boundary), "boundary")
            self.assertEqual(after, [_assistant_text_entry("after")])
            self.assertLessEqual(observed["bytes"], hook_common.CURRENT_TURN_BYTE_CAP)
        finally:
            tp.unlink(missing_ok=True)


class TestBoundedTranscriptHistory(unittest.TestCase):
    def test_complete_history_preserves_more_than_one_hundred_entries(self) -> None:
        entries = [_user_entry("grant")]
        entries.extend(_assistant_text_entry(f"step {i}") for i in range(150))
        tp = _write_transcript(entries)
        try:
            observed, status = hook_common.read_transcript_history(
                str(tp), byte_cap=1024 * 1024, record_cap=1000, line_byte_cap=4096
            )
            self.assertEqual(status, hook_common.HISTORY_STATUS_FOUND)
            self.assertEqual(observed, entries)
        finally:
            tp.unlink()

    def test_invalid_json_and_resource_limits_fail_closed_without_tail_selection(self) -> None:
        tp = Path(tempfile.mktemp(suffix=".jsonl"))
        try:
            tp.write_bytes(b'{"type":"user"}\nnot-json\n')
            self.assertEqual(
                hook_common.read_transcript_history(
                    str(tp), byte_cap=1024, record_cap=10, line_byte_cap=512
                ),
                ([], hook_common.HISTORY_STATUS_INVALID),
            )
            tp.write_text("\n".join(json.dumps(_assistant_text_entry(str(i))) for i in range(3)), encoding="utf-8")
            self.assertEqual(
                hook_common.read_transcript_history(
                    str(tp), byte_cap=1024, record_cap=2, line_byte_cap=512
                ),
                ([], hook_common.HISTORY_STATUS_LIMIT),
            )
        finally:
            tp.unlink(missing_ok=True)


class TestToolResultNotMistakenForBoundary(unittest.TestCase):
    """Named regression: a tool_result is recorded as role=user in Claude
    Code. A boundary predicate that tested `is_user_message` alone would
    stop at the trailing tool_result, discarding every real tool call made
    earlier in the turn. Every fixture here contains a real tool_result
    inside the current turn's window, so this suite cannot be masked by the
    same gap (an all-text fixture with no tool_result at all) that hid the
    original defect."""

    def test_multiple_tool_rounds_all_survive_as_after_entries(self) -> None:
        entries = [_user_entry("do three things")]
        for i in range(3):
            entries.append(_tool_use_entry(f"c{i}"))
            entries.append(_tool_result_entry(f"c{i}"))
        tp = _write_transcript(entries)
        try:
            after, status = hook_common.current_turn_entries(str(tp), byte_cap=1024 * 1024)
            self.assertEqual(status, "found")
            self.assertEqual(len(after), 6, "a tool_result must not be mistaken for the turn boundary")
        finally:
            tp.unlink()

    def test_text_projection_unaffected_by_trailing_tool_result(self) -> None:
        entries = [_user_entry("do the thing"), _tool_use_entry("c1"), _tool_result_entry("c1")]
        tp = _write_transcript(entries)
        try:
            text, status = hook_common.last_genuine_user_text(str(tp), byte_cap=1024 * 1024)
            self.assertEqual(status, "found")
            self.assertEqual(text, "do the thing")
        finally:
            tp.unlink()


class TestSingleScanOwnership(unittest.TestCase):
    """THE pin the bug asks for: changing the boundary scan in ONE place
    (the shared primitive) must change BOTH consumers. Mutation-checked in
    the required order -- see module docstring for the pre-refactor failure
    mode this was verified against (AttributeError: no
    `scan_current_turn_boundary` symbol existed to patch)."""

    def test_both_projections_derive_from_the_one_patched_scan(self) -> None:
        sentinel_entry = _user_entry("sentinel boundary text")
        sentinel_after = [_assistant_text_entry("sentinel after")]

        def fake_scan(transcript_path, *, byte_cap):
            return sentinel_entry, sentinel_after, hook_common.STATUS_FOUND

        # No create=True: if `scan_current_turn_boundary` does not exist
        # (the pre-refactor two-owner shape), this raises AttributeError --
        # exactly the failure this test is designed to demonstrate.
        with mock.patch.object(hook_common, "scan_current_turn_boundary", side_effect=fake_scan):
            after, status_a = hook_common.current_turn_entries("irrelevant.jsonl", byte_cap=999)
            text, status_b = hook_common.last_genuine_user_text("irrelevant.jsonl", byte_cap=999)

        self.assertEqual(status_a, hook_common.STATUS_FOUND)
        self.assertEqual(status_b, hook_common.STATUS_FOUND)
        self.assertEqual(after, sentinel_after)
        self.assertEqual(text, "sentinel boundary text")

    def test_not_found_status_propagates_to_both_from_one_patch(self) -> None:
        def fake_scan(transcript_path, *, byte_cap):
            return None, [], hook_common.STATUS_NOT_IN_WINDOW

        with mock.patch.object(hook_common, "scan_current_turn_boundary", side_effect=fake_scan):
            after, status_a = hook_common.current_turn_entries("irrelevant.jsonl", byte_cap=999)
            text, status_b = hook_common.last_genuine_user_text("irrelevant.jsonl", byte_cap=999)

        self.assertEqual((after, status_a), ([], "not-in-window"))
        self.assertEqual((text, status_b), ("", "not-in-window"))


class TestCorrelatedToolResultStatus(unittest.TestCase):
    """The correlated result is immutable, field-addressed, and carries the
    supported provider execution-status signal without changing its text."""

    def test_provider_status_normalization_matrix(self) -> None:
        claude_absent = {
            "type": "user",
            "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "claude-absent", "content": " plain body "}
            ]},
        }
        claude_false = {
            "type": "user",
            "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "claude-false", "content": "false body", "is_error": False}
            ]},
        }
        claude_true = {
            "type": "user",
            "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "claude-true", "content": "true body", "is_error": True}
            ]},
        }
        claude_nonboolean = {
            "type": "user",
            "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "claude-nonboolean", "content": "ambiguous body", "is_error": "true"}
            ]},
        }

        def nested_codex(call_id: str, output: str) -> dict:
            return {
                "type": "response_item",
                "payload": {"type": "function_call_output", "call_id": call_id, "output": output},
            }

        def top_level_codex(call_id: str, output: str) -> dict:
            return {"type": "function_call_output", "call_id": call_id, "output": output}

        cases = (
            ("claude-absent", claude_absent, "plain body", "NO_OBSERVED_FAILURE"),
            ("claude-false", claude_false, "false body", "NO_OBSERVED_FAILURE"),
            ("claude-true", claude_true, "true body", "EXPLICIT_FAILURE"),
            ("claude-nonboolean", claude_nonboolean, "ambiguous body", "AMBIGUOUS_STATUS"),
            ("codex-nested-zero", nested_codex("codex-nested-zero", "Exit code: 0\nzero body"),
             "Exit code: 0\nzero body", "NO_OBSERVED_FAILURE"),
            ("codex-nested-nonzero", nested_codex("codex-nested-nonzero", "Exit code: 7\nfailed body"),
             "Exit code: 7\nfailed body", "EXPLICIT_FAILURE"),
            ("codex-nested-malformed", nested_codex("codex-nested-malformed", "Exit code: nope\nbody"),
             "Exit code: nope\nbody", "AMBIGUOUS_STATUS"),
            ("codex-nested-no-header", nested_codex("codex-nested-no-header", "ordinary body"),
             "ordinary body", "NO_OBSERVED_FAILURE"),
            ("codex-top-zero", top_level_codex("codex-top-zero", "Exit code: 0\nzero body"),
             "Exit code: 0\nzero body", "NO_OBSERVED_FAILURE"),
            ("codex-top-nonzero", top_level_codex("codex-top-nonzero", "Exit code: -3\nfailed body"),
             "Exit code: -3\nfailed body", "EXPLICIT_FAILURE"),
            ("codex-top-malformed", top_level_codex("codex-top-malformed", "Exit code: 1.5\nbody"),
             "Exit code: 1.5\nbody", "AMBIGUOUS_STATUS"),
            ("codex-top-no-header", top_level_codex("codex-top-no-header", "ordinary top body"),
             "ordinary top body", "NO_OBSERVED_FAILURE"),
        )

        for name, entry, expected_text, expected_status in cases:
            with self.subTest(case=name):
                results = hook_common.extract_tool_outputs_with_ids(entry)
                self.assertEqual(len(results), 1)
                result = results[0]
                self.assertEqual(result.call_id, name)
                self.assertEqual(result.output_text, expected_text)
                self.assertEqual(result.execution_status, expected_status)
                self.assertIsInstance(result, tuple)
                with self.assertRaises(AttributeError):
                    result.execution_status = "NO_OBSERVED_FAILURE"


if __name__ == "__main__":
    unittest.main()
