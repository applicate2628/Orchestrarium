"""Regression tests for the dispatch-time invariant registry
(`dispatch_sentinels.py`) -- the round-depth observer.

Design: work-items/active/2026-07-26-registry-bug-sweep/
design-round-cap-observer.md. Covers the design's Test Strategy §10 items
1-5, 7-9 that are unit-testable against the registry module directly (item 6
"adapter co-existence" and item 7 "advisory event name" are adapter-level and
live in tests/test_typed_routing_hook.py instead, which drives the actual
check-typed-routing.py subprocess; item 10 "mirror parity" is the pre-existing
tests/test_universal_hook_surfaces.py, unchanged by this module since it is
declared PACK_ONLY_HOOKS, not canon-mirrored).

CLAUDE-ONLY, SINGLE-TREE. `dispatch_sentinels.py` lives only at
`src.claude/agents/hooks/dispatch_sentinels.py` -- no canon copy, no Codex
mirror (see `scripts/universal_hooks_manifest.py`'s `PACK_ONLY_HOOKS`). This
test drives that one file directly via `importlib`, the same pattern
`tests/test_workitem_sentinels.py`'s `_load_sentinels()` uses for its own
canon module.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "src.claude" / "agents" / "hooks" / "dispatch_sentinels.py"


def _load_dispatch_sentinels():
    spec = importlib.util.spec_from_file_location("dispatch_sentinels_under_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dispatch_sentinels = _load_dispatch_sentinels()


# ---------------------------------------------------------------------------
# Transcript fixture builders -- Claude Code entry shapes only (this module
# is Claude-only; it never reads a Codex rollout).
# ---------------------------------------------------------------------------


def _user_entry(text: str) -> dict:
    return {"type": "user", "message": {"role": "user", "content": text}}


def _tool_result_entry(call_id: str) -> dict:
    # A tool_result is recorded as role=user in Claude Code -- DI-6's own
    # named regression: this must NOT be counted as an Agent dispatch, and
    # must NOT be mistaken for a new turn boundary either.
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": call_id, "content": "ok"}],
        },
    }


def _agent_dispatch_entry(subagent_type: str, call_id: str) -> dict:
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": call_id,
                    "name": "Agent",
                    "input": {
                        "subagent_type": subagent_type,
                        "description": "d",
                        "prompt": "p",
                    },
                }
            ],
        },
    }


def _compact_summary_entry() -> dict:
    # DI-7: the harness's post-compaction continuation prompt is recorded
    # role=user with real prose -- it must never be read as a turn boundary.
    return {
        "type": "user",
        "isCompactSummary": True,
        "message": {"role": "user", "content": "prior session summary: fixed bug, error, broken"},
    }


def _write_transcript(entries: list[dict]) -> Path:
    tmp = Path(tempfile.mktemp(suffix=".jsonl"))
    tmp.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return tmp


def _transcript_with_prior_dispatches(
    role: str, n_prior: int, *, boundary_text: str = "hello", interleave: dict | None = None
) -> Path:
    """A transcript whose boundary is `boundary_text`, followed by `n_prior`
    Agent dispatches of `role` (each paired with its own tool_result, per
    DI-6), optionally interleaved with `interleave` dispatches of a SECOND
    role at the given positions (used by the key-isolation test)."""
    entries = [_user_entry(boundary_text)]
    for i in range(n_prior):
        entries.append(_agent_dispatch_entry(role, f"c-{role}-{i}"))
        entries.append(_tool_result_entry(f"c-{role}-{i}"))
        if interleave and i in interleave:
            other_role = interleave[i]
            entries.append(_agent_dispatch_entry(other_role, f"c-{other_role}-{i}"))
            entries.append(_tool_result_entry(f"c-{other_role}-{i}"))
    return _write_transcript(entries)


def _envelope(role: str, transcript_path: Path | str) -> dict:
    return {
        "tool_name": "Agent",
        "tool_input": {"subagent_type": role, "description": "d", "prompt": "p"},
        "transcript_path": str(transcript_path),
    }


def _findings_for(role: str, n_prior: int, **kwargs) -> list:
    tp = _transcript_with_prior_dispatches(role, n_prior, **kwargs)
    try:
        ctx = dispatch_sentinels.build_context(_envelope(role, tp))
        return dispatch_sentinels.evaluate_all(ctx, event="PreToolUse")
    finally:
        tp.unlink()


class TestDepthCountingP4Policy(unittest.TestCase):
    """Test Strategy §10 item 1. The design's own vocabulary uses "depth" to
    mean the TOTAL dispatch count including the pending one (Terms:
    "P4 fires at depth 4, 8, 16, 32"; §3.4's example: "...dispatched X 7
    times; this is dispatch 8" fires). `n_prior` here is prior-count only
    (this module's own `depth` variable); `n_prior + 1` is the design's
    "depth"/"dispatch number" -- the quantity actually compared to P4's
    checkpoints."""

    def test_silent_below_and_between_checkpoints(self) -> None:
        # design-total-depth 1, 3, 5, 6, 7 (n_prior 0, 2, 4, 5, 6) must all
        # be silent -- explicitly including "assert silence at 5/6/7" from
        # §10 item 1 (the gap P4 is chosen specifically to stay quiet
        # through).
        for n_prior in (0, 2, 4, 5, 6):
            with self.subTest(n_prior=n_prior, design_depth=n_prior + 1):
                findings = _findings_for("architecture-reviewer", n_prior)
                self.assertEqual(findings, [], f"unexpected fire at design-depth {n_prior + 1}")

    def test_fires_at_4_8_16(self) -> None:
        # §10 item 1's exact three fire points.
        for n_prior in (3, 7, 15):
            with self.subTest(n_prior=n_prior, design_depth=n_prior + 1):
                findings = _findings_for("architecture-reviewer", n_prior)
                self.assertEqual(len(findings), 1, f"expected exactly one fire at design-depth {n_prior + 1}")
                self.assertEqual(findings[0].id, "SEN-D1")
                self.assertEqual(findings[0].severity, dispatch_sentinels.ADVISORY)

    def test_extrapolation_beyond_32_is_this_implementations_own_choice(self) -> None:
        # design.md's own four-transcript corpus never measured past depth
        # 23 (session D's max), so firing at 64 is THIS IMPLEMENTATION'S
        # extrapolation of the stated doubling pattern (4, 8, 16, 32, ...),
        # not independently measured by the design. Pinned here so a future
        # reader sees the assumption is deliberate and tested, not silent.
        findings_31 = _findings_for("architecture-reviewer", 31)  # design-depth 32 -> fire
        findings_32 = _findings_for("architecture-reviewer", 32)  # design-depth 33 -> silent
        findings_63 = _findings_for("architecture-reviewer", 63)  # design-depth 64 -> fire (extrapolated)
        self.assertEqual(len(findings_31), 1)
        self.assertEqual(findings_32, [])
        self.assertEqual(len(findings_63), 1)

    def test_message_names_count_and_cites_the_shipped_cap(self) -> None:
        findings = _findings_for("architecture-reviewer", 7)  # design-depth 8, the reported incident
        self.assertEqual(len(findings), 1)
        message = findings[0].message
        self.assertIn("[round-depth AUDIT]", message)
        self.assertIn("architecture-reviewer", message)
        self.assertIn("7 times", message)
        self.assertIn("dispatch 8", message)
        self.assertIn("review-loop.md:45", message)
        self.assertIn("5 past the cap", message)  # 8 - CITED_ROUND_CAP(3) = 5, matches design.md §3.4's own example


class TestTurnBoundaryCorrectness(unittest.TestCase):
    """Test Strategy §10 item 2: DI-6 (tool_result is not a boundary, and is
    not miscounted as a dispatch) and DI-7 (isCompactSummary is skipped as a
    boundary candidate)."""

    def test_tool_results_do_not_zero_or_double_the_count(self) -> None:
        # 7 prior dispatches, each paired with its own tool_result (role=user
        # in Claude Code) -> design-depth must read 8 (this pending dispatch
        # is the 8th), NOT 0 (tool_result wrongly read as the boundary) and
        # NOT 16 (tool_result wrongly counted as a second dispatch).
        findings = _findings_for("qa-engineer", 7)
        self.assertEqual(len(findings), 1)
        self.assertIn("dispatch 8", findings[0].message)

    def test_compact_summary_is_not_read_as_a_new_boundary(self) -> None:
        tp = _transcript_with_prior_dispatches("qa-engineer", 0, boundary_text="ok real boundary")
        text = tp.read_text(encoding="utf-8")
        # Splice a compact-summary entry directly after the real boundary,
        # then re-append 7 dispatches after IT -- if the compact summary were
        # wrongly treated as the boundary, everything before it (nothing,
        # here) would still be seen, but if it were wrongly treated as
        # NON-skippable ordinary content that's fine; the real regression
        # this guards is the OPPOSITE hazard already fixed in hook_common
        # (isCompactSummary swallowed as if genuine) -- reconstruct fully to
        # be explicit rather than relying on splicing order.
        tp.unlink()
        entries = [_user_entry("ok real boundary"), _compact_summary_entry()]
        for i in range(7):
            entries.append(_agent_dispatch_entry("qa-engineer", f"c{i}"))
            entries.append(_tool_result_entry(f"c{i}"))
        tp2 = _write_transcript(entries)
        try:
            ctx = dispatch_sentinels.build_context(_envelope("qa-engineer", tp2))
            self.assertEqual(ctx["entries_status"], "found")
            findings = dispatch_sentinels.evaluate_all(ctx, event="PreToolUse")
            self.assertEqual(len(findings), 1, "the 7 dispatches after the compact-summary entry must still be counted")
            self.assertIn("dispatch 8", findings[0].message)
        finally:
            tp2.unlink()


class TestKeyIsolation(unittest.TestCase):
    """Test Strategy §10 item 3: two roles interleaved to depth 3 each ->
    silent; one role to depth 4 -> fires once. Guards against the
    mega-cluster failure design.md §0.3 measured for a text-derived key --
    this key must never blur two DIFFERENT subagent_types together."""

    def test_two_roles_each_at_three_stay_silent(self) -> None:
        # 2 PRIOR dispatches of each role -> design-depth 3 for either role's
        # NEXT (pending) dispatch -> below the P4 threshold (4) -> silent.
        entries = [_user_entry("hello")]
        for i in range(2):
            entries.append(_agent_dispatch_entry("backend-engineer", f"be{i}"))
            entries.append(_tool_result_entry(f"be{i}"))
            entries.append(_agent_dispatch_entry("architecture-reviewer", f"ar{i}"))
            entries.append(_tool_result_entry(f"ar{i}"))
        tp = _write_transcript(entries)
        try:
            for role in ("backend-engineer", "architecture-reviewer"):
                with self.subTest(role=role):
                    ctx = dispatch_sentinels.build_context(_envelope(role, tp))
                    findings = dispatch_sentinels.evaluate_all(ctx, event="PreToolUse")
                    self.assertEqual(findings, [], f"{role} at design-depth 3 should stay silent")
        finally:
            tp.unlink()

    def test_one_role_reaching_four_fires_the_other_stays_silent(self) -> None:
        # backend-engineer: 3 PRIOR dispatches -> its NEXT (pending) dispatch
        # is design-depth 4 -> FIRES. architecture-reviewer: 2 PRIOR
        # dispatches interleaved -> its own next dispatch is design-depth 3
        # -> stays silent. The two counts must never blend into one shared
        # bucket (the mega-cluster failure design.md §0.3 measured for a
        # text-derived key).
        entries = [_user_entry("hello")]
        for i in range(3):
            entries.append(_agent_dispatch_entry("backend-engineer", f"be{i}"))
            entries.append(_tool_result_entry(f"be{i}"))
            if i < 2:
                entries.append(_agent_dispatch_entry("architecture-reviewer", f"ar{i}"))
                entries.append(_tool_result_entry(f"ar{i}"))
        tp = _write_transcript(entries)
        try:
            ctx_be = dispatch_sentinels.build_context(_envelope("backend-engineer", tp))
            findings_be = dispatch_sentinels.evaluate_all(ctx_be, event="PreToolUse")
            self.assertEqual(len(findings_be), 1)
            self.assertIn("dispatch 4", findings_be[0].message)  # 3 prior -> design-depth 4 -> FIRES

            ctx_ar = dispatch_sentinels.build_context(_envelope("architecture-reviewer", tp))
            findings_ar = dispatch_sentinels.evaluate_all(ctx_ar, event="PreToolUse")
            self.assertEqual(findings_ar, [])  # 2 prior -> design-depth 3 -> silent
        finally:
            tp.unlink()


class TestInertPaths(unittest.TestCase):
    """Test Strategy §10 item 4: absent / unreadable / not-in-window ->
    no output, regardless of what the (unreachable) transcript would have
    counted."""

    def test_absent_transcript_path_is_inert(self) -> None:
        ctx = dispatch_sentinels.build_context(
            {"tool_name": "Agent", "tool_input": {"subagent_type": "backend-engineer"}}
        )
        self.assertEqual(ctx["entries_status"], "absent")
        self.assertEqual(dispatch_sentinels.evaluate_all(ctx, event="PreToolUse"), [])

    def test_unreadable_transcript_path_is_inert(self) -> None:
        ctx = dispatch_sentinels.build_context(
            _envelope("backend-engineer", "/definitely/does/not/exist/anywhere.jsonl")
        )
        self.assertEqual(ctx["entries_status"], "unreadable")
        self.assertEqual(dispatch_sentinels.evaluate_all(ctx, event="PreToolUse"), [])

    def test_boundary_beyond_byte_cap_is_inert_not_a_false_fire(self) -> None:
        # A huge filler block BEFORE the boundary pushes it outside a tiny
        # byte_cap. Rather than call build_context (which uses the module's
        # own 8 MiB constant), call current_turn_entries directly with a
        # deliberately tiny cap to prove the "not-in-window" status alone
        # suppresses SEN-D1, matching §3.6's safe-direction requirement.
        import hook_common

        entries = [_user_entry("x" * (2 * 1024 * 1024))]  # 2 MiB filler before the boundary
        for i in range(8):
            entries.append(_agent_dispatch_entry("backend-engineer", f"c{i}"))
            entries.append(_tool_result_entry(f"c{i}"))
        tp = _write_transcript(entries)
        try:
            turn_entries, status = hook_common.current_turn_entries(str(tp), byte_cap=4096)
            self.assertEqual(status, "not-in-window")
            self.assertEqual(turn_entries, [])
            ctx = {"subagent_type": "backend-engineer", "turn_entries": turn_entries, "entries_status": status}
            self.assertEqual(dispatch_sentinels.evaluate_all(ctx, event="PreToolUse"), [])
        finally:
            tp.unlink()

    def test_no_subagent_type_is_inert(self) -> None:
        ctx = dispatch_sentinels.build_context({"tool_name": "Agent", "tool_input": {}})
        self.assertIsNone(ctx["subagent_type"])
        self.assertEqual(dispatch_sentinels.evaluate_all(ctx, event="PreToolUse"), [])


class TestFailOpenPerEntry(unittest.TestCase):
    """Test Strategy §10 item 5 / DI-2: an exception inside one registry
    entry's evaluate() must not crash evaluate_all or suppress a sibling
    entry's finding."""

    def test_broken_entry_does_not_suppress_a_working_sibling(self) -> None:
        def _boom(_ctx: dict):
            raise RuntimeError("boom")

        def _ok(_ctx: dict):
            return dispatch_sentinels.Finding("SIB-OK", dispatch_sentinels.ADVISORY, "sibling fired")

        fake_registry = (
            {"id": "BROKEN", "event": "PreToolUse", "scope": "test", "evaluate": _boom, "exemptions": "none"},
            {"id": "SIB-OK", "event": "PreToolUse", "scope": "test", "evaluate": _ok, "exemptions": "none"},
        )
        original = dispatch_sentinels.REGISTRY
        dispatch_sentinels.REGISTRY = fake_registry
        try:
            findings = dispatch_sentinels.evaluate_all({}, event="PreToolUse")
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].id, "SIB-OK")
        finally:
            dispatch_sentinels.REGISTRY = original


class TestLatencyAndReaderChoice(unittest.TestCase):
    """Test Strategy §10 item 8 / DI-8: the blocking PreToolUse path must
    never call read_transcript_tail (whole-file read, the filed perf bug),
    and must stay well under the runtime's own hook-timeout budget even
    against a large synthetic transcript."""

    def test_module_never_references_read_transcript_tail(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("read_transcript_tail", source)

    def test_bounded_read_respects_io_cap_on_a_large_transcript(self) -> None:
        # Check the actual I/O budget, not scheduler latency on a shared runner.
        # The owner now reads one bounded suffix, not the former doubling scan.
        cap = dispatch_sentinels.TURN_ENTRIES_BYTE_CAP
        real_open = Path.open
        reads = []

        class BudgetedReader:
            def __init__(self, stream):
                self.stream = stream

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return self.stream.__exit__(*args)

            def seek(self, *args):
                return self.stream.seek(*args)

            def tell(self):
                return self.stream.tell()

            def read(self, size=-1):
                if size < 0 or sum(reads) + size > cap:
                    raise AssertionError("transcript read exceeds the aggregate byte cap")
                data = self.stream.read(size)
                reads.append(len(data))
                return data

        with tempfile.TemporaryDirectory(prefix="dispatch-io-budget-") as directory:
            transcript = Path(directory) / "transcript.jsonl"
            filler = (json.dumps({"type": "assistant", "message": {
                "role": "assistant", "content": [{"type": "text", "text": "x" * 900}]
            }}) + "\n").encode("utf-8")
            target_bytes = 100 * 1024 * 1024
            with transcript.open("wb") as stream:
                for _ in range(target_bytes // len(filler) + 1):
                    stream.write(filler)
                stream.write((json.dumps(_user_entry("boundary")) + "\n").encode())
                for i in range(7):
                    for entry in (_agent_dispatch_entry("backend-engineer", f"c{i}"),
                                  _tool_result_entry(f"c{i}")):
                        stream.write((json.dumps(entry) + "\n").encode())
            self.assertGreaterEqual(transcript.stat().st_size, target_bytes)

            def observed_open(path, *args, **kwargs):
                stream = real_open(path, *args, **kwargs)
                return BudgetedReader(stream) if path == transcript else stream

            with mock.patch.object(Path, "open", new=observed_open):
                ctx = dispatch_sentinels.build_context(_envelope("backend-engineer", transcript))
            self.assertEqual(ctx["entries_status"], "found")
            self.assertEqual(len(dispatch_sentinels.evaluate_all(ctx, event="PreToolUse")), 1)
            self.assertTrue(reads, "fixture must exercise real bounded file reads")
            self.assertLessEqual(sum(reads), cap)


class TestEncoding(unittest.TestCase):
    """Test Strategy §10 item 9 / DI-10: a Cyrillic turn boundary must not
    break boundary detection or the depth count that follows it."""

    def test_cyrillic_boundary_resolves_and_depth_counts_correctly(self) -> None:
        tp = _transcript_with_prior_dispatches(
            "backend-engineer", 7, boundary_text="Привет, продолжай работу над ошибкой"
        )
        try:
            ctx = dispatch_sentinels.build_context(_envelope("backend-engineer", tp))
            self.assertEqual(ctx["entries_status"], "found")
            findings = dispatch_sentinels.evaluate_all(ctx, event="PreToolUse")
            self.assertEqual(len(findings), 1)
            self.assertIn("dispatch 8", findings[0].message)
        finally:
            tp.unlink()


class TestSecurityPosture(unittest.TestCase):
    """§9's stated posture: read-only, no subprocess/network, no transcript
    content in the advisory text -- only a role name, two integers, and a
    fixed citation."""

    def test_no_subprocess_or_network_imports(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        for banned in ("subprocess", "socket", "urllib", "requests"):
            self.assertNotIn(banned, source)

    def test_advisory_never_echoes_transcript_prose(self) -> None:
        tp = _transcript_with_prior_dispatches(
            "backend-engineer", 7, boundary_text="SECRET-MARKER-should-never-leak-into-advisory"
        )
        try:
            ctx = dispatch_sentinels.build_context(_envelope("backend-engineer", tp))
            findings = dispatch_sentinels.evaluate_all(ctx, event="PreToolUse")
            self.assertEqual(len(findings), 1)
            self.assertNotIn("SECRET-MARKER", findings[0].message)
        finally:
            tp.unlink()


if __name__ == "__main__":
    unittest.main()
