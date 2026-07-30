"""Regression tests for the work-item sentinel registry (design.md, r8).

Covers the design's named guards that are unit-testable without a live
provider CLI: G-1b, G-4, G-5, G-6 (incl. T-13's degraded-posture primary),
G-7, G-8/T-2, G-11, G-12, G-13/T-10, G-14/T-16 (SEN-0-scoped post-r8), plus
SEN-1 behavior, T-3 (subagent skip), and T-4 (determinism).

SEN-2 now uses the cross-line RESOLVE channel: a due opted-in delivery action
gets one model-visible continuation, while raw `stop_hook_active` suppresses
same-turn re-entry. The older file-count/NOTICE design remains withdrawn.

G-1 (SEN-0 verdict-equivalence) and G-2 (byte-identity of the wrapper AND the
registry module across canon + 2 pack trees) are NOT duplicated here:
  - G-1 is `tests/test_work_items_archival_hook.py` -- the pre-existing
    archival-hook suite, run unchanged against the new adapter (40 tests /
    120 subtests, all passing against this change).
  - G-2 is `tests/test_universal_hook_surfaces.py`'s glob-derived
    `filecmp.cmp(shallow=False)` gate, which picked up `workitem_sentinels.py`
    automatically the moment it landed in the canon dir (no new guard
    machinery -- design.md §5.2 / F-B10).

G-3 (Codex trust preservation) and G-9/T-11 (Claude-line cross-hook
precedence) require a LIVE provider binary and are not run as part of this
suite (they cost real API calls / require an installed CLI). Both were run
manually this session; see the implementation report for the reproduced
evidence (hash recomputation against the live installed `stop:1:0` entry, and
the two-hook Claude-line probe).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CANON_MODULE = REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "workitem_sentinels.py"
CANON_ADAPTER = REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "check-work-items-archival-stop.py"

ADAPTERS = (
    CANON_ADAPTER,
    REPO_ROOT / "src.claude" / "agents" / "scripts" / "check-work-items-archival-stop.py",
    REPO_ROOT / "src.codex" / "skills" / "lead" / "scripts" / "check-work-items-archival-stop.py",
)


def _load_sentinels():
    spec = importlib.util.spec_from_file_location("workitem_sentinels_under_test", CANON_MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sentinels = _load_sentinels()


def _git(cwd: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, env=env)


def make_git_repo() -> Path:
    root = Path(tempfile.mkdtemp(prefix="wi-sentinels-"))
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    return root


def commit_all(root: Path, message: str, iso_date: str) -> str:
    env = {
        "GIT_AUTHOR_DATE": iso_date,
        "GIT_COMMITTER_DATE": iso_date,
        # Preserve enough of the ambient environment for git to find its own
        # binaries/config on Windows; only the date vars are the point here.
        **{k: v for k, v in __import__("os").environ.items()},
    }
    _git(root, "add", "-A", env=env)
    result = _git(root, "commit", "-q", "-m", message, env=env)
    assert result.returncode == 0, result.stderr
    sha = _git(root, "rev-parse", "HEAD").stdout.strip()
    return sha


def run_adapter(script: Path, envelope: dict, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    import os

    env = os.environ.copy()
    env.pop("ORCHESTRARIUM_DISPATCHED_REVIEW", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(envelope, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


class TestSEN2DeliveryDrought(unittest.TestCase):
    """A due opted-in delivery action gets one root continuation only."""

    def _fixture(self) -> tuple[Path, Path]:
        root = Path(tempfile.mkdtemp(prefix="wi-sen2-red-"))
        (root / ".git").mkdir()
        item = root / "work-items" / "active" / "delivery-item"
        item.mkdir(parents=True)
        (item / "status.md").write_text(
            """## Current state

- **Primary task status**: active

## Delivery action

- **Primary**: true
- **Fingerprint**: delivery-core-v1
- **Class**: mutation
- **Target**: scripts/universal-hooks/scripts/workitem_sentinels.py
- **Oracle**: correlated-success

## Next action

Implement the admitted universal sentinel owner.
""",
            encoding="utf-8",
        )
        transcript = root / "transcript.jsonl"
        records = [
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "continue"}],
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "call_id": "process-1",
                    "name": "shell_command",
                    "arguments": '{"command":"review status.md"}',
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call_output",
                    "call_id": "process-1",
                    "output": "Exit code: 0\nreview complete",
                },
            },
        ]
        transcript.write_text(
            "\n".join(json.dumps(record) for record in records) + "\n",
            encoding="utf-8",
        )
        return root, transcript

    def _absent_fixture(self, task_status: str = "active") -> tuple[Path, Path]:
        root, transcript = self._fixture()
        status = root / "work-items" / "active" / "delivery-item" / "status.md"
        status.write_text(
            f"""## Current state

- **Primary task status**: {task_status}

## Next action

Continue the admitted work.
""",
            encoding="utf-8",
        )
        self._write_records(transcript, self._codex_records(
            name="apply_patch",
            arguments="*** Update File: README.md",
            output="Exit code: 0",
        ))
        return root, transcript

    def test_active_absent_blocks_once_even_with_unrelated_success(self) -> None:
        root, transcript = self._absent_fixture()
        ctx = sentinels.build_context(
            str(root),
            runtime_stop=True,
            delivery_activity=[{
                "action_class": "mutation",
                "target_ids": ["README.md"],
                "succeeded": True,
            }],
            delivery_activity_status="FOUND",
        )
        self.assertEqual(ctx["delivery_action_status"], "ABSENT")
        self.assertIsNone(ctx["delivery_action"])
        finding = sentinels._sen2_evaluate(ctx)
        self.assertIsNotNone(finding)
        self.assertEqual(finding.severity, sentinels.RESOLVE)

        first = run_adapter(
            CANON_ADAPTER,
            {"cwd": str(root), "transcript_path": str(transcript), "stop_hook_active": False},
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn('"decision": "block"', first.stdout)
        self.assertIn("SEN-2-DROUGHT", first.stdout)
        for _ in range(2):
            repeat = run_adapter(
                CANON_ADAPTER,
                {"cwd": str(root), "transcript_path": str(transcript), "stop_hook_active": True},
            )
            self.assertEqual(repeat.returncode, 0, repeat.stderr)
            self.assertNotIn('"decision": "block"', repeat.stdout)

    def test_status_text_cannot_suppress_absent_action(self) -> None:
        for task_status in ("parked", "blocked", "cancelled", "canceled", "closed", "archived"):
            with self.subTest(task_status=task_status):
                root, transcript = self._absent_fixture(task_status)
                ctx = sentinels.build_context(str(root), runtime_stop=True)
                self.assertEqual(ctx["delivery_action_status"], "ABSENT")
                result = run_adapter(
                    CANON_ADAPTER,
                    {"cwd": str(root), "transcript_path": str(transcript)},
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('"decision": "block"', result.stdout)

    def test_empty_active_directory_is_inactive(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="wi-sen2-empty-"))
        (root / ".git").mkdir()
        (root / "work-items" / "active").mkdir(parents=True)
        ctx = sentinels.build_context(str(root), runtime_stop=True)
        self.assertEqual(ctx["delivery_action_status"], "INACTIVE")
        self.assertIsNone(sentinels._sen2_evaluate(ctx))

    def test_multiple_active_directories_are_invalid(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="wi-sen2-multiple-"))
        (root / ".git").mkdir()
        active = root / "work-items" / "active"
        (active / "first").mkdir(parents=True)
        (active / "second").mkdir()
        ctx = sentinels.build_context(str(root), runtime_stop=True)
        self.assertEqual(ctx["delivery_action_status"], "INVALID")
        finding = sentinels._sen2_evaluate(ctx)
        self.assertIsNotNone(finding)
        self.assertEqual(finding.severity, sentinels.NOTICE)

    def test_one_declared_action_among_multiple_active_items_remains_valid(self) -> None:
        root, transcript = self._fixture()
        other = root / "work-items" / "active" / "research-item"
        other.mkdir()
        (other / "status.md").write_text("State: active\n", encoding="utf-8")
        self._write_records(transcript, self._codex_records(
            name="apply_patch",
            arguments="*** Update File: scripts/universal-hooks/scripts/workitem_sentinels.py",
            output="Exit code: 0",
        ))

        ctx = sentinels.build_context(str(root), runtime_stop=True)
        self.assertEqual(ctx["delivery_action_status"], "VALID")
        result = run_adapter(CANON_ADAPTER, {"cwd": str(root), "transcript_path": str(transcript)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('"decision": "block"', result.stdout)

    def test_due_root_stop_blocks_once_and_reentry_allows(self) -> None:
        root, transcript = self._fixture()
        files_before = sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file())
        first = run_adapter(
            CANON_ADAPTER,
            {"cwd": str(root), "transcript_path": str(transcript), "stop_hook_active": False},
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn('"decision": "block"', first.stdout)
        self.assertIn("SEN-2-DROUGHT", first.stdout)

        for _ in range(2):
            repeat = run_adapter(
                CANON_ADAPTER,
                {"cwd": str(root), "transcript_path": str(transcript), "stop_hook_active": True},
            )
            self.assertEqual(repeat.returncode, 0, repeat.stderr)
            self.assertNotIn('"decision": "block"', repeat.stdout)
        files_after = sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file())
        self.assertEqual(files_after, files_before)

    @staticmethod
    def _write_records(transcript: Path, records: list[dict]) -> None:
        transcript.write_text(
            "\n".join(json.dumps(record) for record in records) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _codex_records(*, name: str, arguments: object, output: str, assistant_prose: str = "") -> list[dict]:
        records: list[dict] = [
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "continue"}],
                },
            }
        ]
        if assistant_prose:
            records.append({
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": assistant_prose}],
                },
            })
        records.extend([
            {
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call",
                    "call_id": "delivery-1",
                    "name": name,
                    "input": arguments,
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call_output",
                    "call_id": "delivery-1",
                    "output": output,
                },
            },
        ])
        return records

    def test_satisfied_matching_mutation_allows(self) -> None:
        root, transcript = self._fixture()
        self._write_records(transcript, self._codex_records(
            name="apply_patch",
            arguments="*** Update File: scripts/universal-hooks/scripts/workitem_sentinels.py",
            output="Exit code: 0",
        ))
        result = run_adapter(CANON_ADAPTER, {"cwd": str(root), "transcript_path": str(transcript)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('"decision": "block"', result.stdout)
        self.assertNotIn("SEN-2-DROUGHT", result.stdout)

    def test_patch_body_target_mention_does_not_satisfy_different_patch_header(self) -> None:
        root, transcript = self._fixture()
        self._write_records(transcript, self._codex_records(
            name="apply_patch",
            arguments=(
                "*** Update File: work-items/active/delivery-item/status.md\n"
                "@@\n"
                "+- **Target**: scripts/universal-hooks/scripts/workitem_sentinels.py"
            ),
            output="Exit code: 0",
        ))
        result = run_adapter(CANON_ADAPTER, {"cwd": str(root), "transcript_path": str(transcript)})
        self.assertIn('"decision": "block"', result.stdout)
        self.assertIn("SEN-2-DROUGHT", result.stdout)

    def test_matching_failure_does_not_manufacture_progress(self) -> None:
        root, transcript = self._fixture()
        self._write_records(transcript, self._codex_records(
            name="apply_patch",
            arguments="*** Update File: scripts/universal-hooks/scripts/workitem_sentinels.py",
            output="Exit code: 1",
        ))
        result = run_adapter(CANON_ADAPTER, {"cwd": str(root), "transcript_path": str(transcript)})
        self.assertIn('"decision": "block"', result.stdout)
        self.assertIn("SEN-2-DROUGHT", result.stdout)

    def test_ambiguous_result_does_not_manufacture_progress(self) -> None:
        root, transcript = self._fixture()
        self._write_records(transcript, self._codex_records(
            name="apply_patch",
            arguments="*** Update File: scripts/universal-hooks/scripts/workitem_sentinels.py",
            output="untyped result body",
        ))
        result = run_adapter(CANON_ADAPTER, {"cwd": str(root), "transcript_path": str(transcript)})
        self.assertIn('"decision": "block"', result.stdout)
        self.assertIn("SEN-2-DROUGHT", result.stdout)

    def test_corrupt_transcript_fails_open_with_static_notice(self) -> None:
        root, transcript = self._fixture()
        transcript.write_text("not-json{\n", encoding="utf-8")
        result = run_adapter(CANON_ADAPTER, {"cwd": str(root), "transcript_path": str(transcript)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('"decision": "block"', result.stdout)
        self.assertIn("SEN-2-INPUT", result.stdout)
        self.assertNotIn(str(root), result.stdout)

    def test_assistant_prose_cannot_claim_matching_delivery(self) -> None:
        root, transcript = self._fixture()
        self._write_records(transcript, self._codex_records(
            name="shell_command",
            arguments='{"command":"review status.md"}',
            output="Exit code: 0",
            assistant_prose=(
                "apply_patch succeeded for "
                "scripts/universal-hooks/scripts/workitem_sentinels.py"
            ),
        ))
        result = run_adapter(CANON_ADAPTER, {"cwd": str(root), "transcript_path": str(transcript)})
        self.assertIn('"decision": "block"', result.stdout)
        self.assertIn("SEN-2-DROUGHT", result.stdout)

    def test_child_stop_never_blocks_due_parent_action(self) -> None:
        root, transcript = self._fixture()
        result = run_adapter(
            CANON_ADAPTER,
            {"cwd": str(root), "transcript_path": str(transcript), "agent_id": "child-1"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_verification_contract_is_input_invalid_and_shell_echo_gets_no_credit(self) -> None:
        root, transcript = self._fixture()
        status_path = root / "work-items" / "active" / "delivery-item" / "status.md"
        status_path.write_text(
            status_path.read_text(encoding="utf-8").replace(
                "- **Class**: mutation",
                "- **Class**: verification",
            ),
            encoding="utf-8",
        )
        self._write_records(transcript, self._codex_records(
            name="shell_command",
            arguments={
                "command": (
                    "Write-Output "
                    "scripts/universal-hooks/scripts/workitem_sentinels.py"
                )
            },
            output="Exit code: 0",
        ))

        result = run_adapter(CANON_ADAPTER, {"cwd": str(root), "transcript_path": str(transcript)})

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('"decision": "block"', result.stdout)
        self.assertIn("SEN-2-INPUT", result.stdout)

    def test_only_direct_semantic_mutation_target_gets_credit(self) -> None:
        target = "scripts/universal-hooks/scripts/workitem_sentinels.py"
        false_credit_calls = (
            ("shell_command", {"command": f"Write-Output {target}"}),
            ("PowerShell", {"command": f"Write-Output {target}"}),
            ("exec_command", {"cmd": f"printf {target}"}),
            ("functions.exec", {"source": f'tools.apply_patch("*** Update File: {target}")'}),
            ("mcp__untrusted__write", {"file_path": target}),
            ("Write", {"file_path": "docs/other.md", "description": target}),
            ("Write", {"file_path": "docs/other.md", "metadata": {"target": target}}),
        )
        for tool_name, tool_input in false_credit_calls:
            with self.subTest(tool=tool_name, input=tool_input):
                root, transcript = self._fixture()
                self._write_records(transcript, self._codex_records(
                    name=tool_name,
                    arguments=tool_input,
                    output="Exit code: 0",
                ))
                result = run_adapter(
                    CANON_ADAPTER,
                    {"cwd": str(root), "transcript_path": str(transcript)},
                )
                self.assertIn('"decision": "block"', result.stdout)
                self.assertIn("SEN-2-DROUGHT", result.stdout)

        for tool_name, tool_input in (
            ("Write", {"file_path": target, "content": "replacement"}),
            (
                "mcp__serena__replace_symbol_body",
                {"relative_path": target, "name_path": "_sen2_evaluate", "body": "replacement"},
            ),
        ):
            with self.subTest(tool=tool_name, semantic_target=tool_input):
                root, transcript = self._fixture()
                self._write_records(transcript, self._codex_records(
                    name=tool_name,
                    arguments=tool_input,
                    output="Exit code: 0",
                ))
                result = run_adapter(
                    CANON_ADAPTER,
                    {"cwd": str(root), "transcript_path": str(transcript)},
                )
                self.assertNotIn('"decision": "block"', result.stdout)
                self.assertNotIn("SEN-2-DROUGHT", result.stdout)

    def test_direct_mutation_without_result_remains_due(self) -> None:
        root, transcript = self._fixture()
        target = "scripts/universal-hooks/scripts/workitem_sentinels.py"
        records = self._codex_records(
            name="Write",
            arguments={"file_path": target, "content": "replacement"},
            output="Exit code: 0",
        )
        self._write_records(transcript, records[:-1])

        result = run_adapter(CANON_ADAPTER, {"cwd": str(root), "transcript_path": str(transcript)})

        self.assertIn('"decision": "block"', result.stdout)
        self.assertIn("SEN-2-DROUGHT", result.stdout)

    def test_claude_direct_mutation_requires_explicit_success(self) -> None:
        target = "scripts/universal-hooks/scripts/workitem_sentinels.py"
        for is_error, should_satisfy in ((False, True), (None, False)):
            with self.subTest(is_error=is_error):
                root, transcript = self._fixture()
                result_block = {
                    "type": "tool_result",
                    "tool_use_id": "claude-write-1",
                    "content": "done",
                }
                if is_error is not None:
                    result_block["is_error"] = is_error
                records = [
                    {
                        "type": "user",
                        "message": {"role": "user", "content": "continue"},
                    },
                    {
                        "type": "assistant",
                        "message": {
                            "role": "assistant",
                            "content": [{
                                "type": "tool_use",
                                "id": "claude-write-1",
                                "name": "Write",
                                "input": {"file_path": target, "content": "replacement"},
                            }],
                        },
                    },
                    {
                        "type": "user",
                        "message": {"role": "user", "content": [result_block]},
                    },
                ]
                self._write_records(transcript, records)

                result = run_adapter(
                    CANON_ADAPTER,
                    {"cwd": str(root), "transcript_path": str(transcript)},
                )

                self.assertEqual('"decision": "block"' not in result.stdout, should_satisfy)

    def test_canonical_blocked_status_does_not_suppress_due_action(self) -> None:
        root, transcript = self._fixture()
        status_path = root / "work-items" / "active" / "delivery-item" / "status.md"
        status_path.write_text(
            status_path.read_text(encoding="utf-8").replace(
                "- **Primary task status**: active",
                "- **Primary task status**: blocked",
            ),
            encoding="utf-8",
        )

        result = run_adapter(CANON_ADAPTER, {"cwd": str(root), "transcript_path": str(transcript)})

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"decision": "block"', result.stdout)
        self.assertIn("SEN-2-DROUGHT", result.stdout)

    def test_direct_outside_repo_transcript_capability_still_drives_due_verdict(self) -> None:
        root, fixture_transcript = self._fixture()
        outside_transcript = Path(tempfile.mktemp(prefix="sen2-host-capability-", suffix=".jsonl"))
        try:
            outside_transcript.write_text(
                fixture_transcript.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            result = run_adapter(
                CANON_ADAPTER,
                {"cwd": str(root), "transcript_path": str(outside_transcript)},
            )
        finally:
            outside_transcript.unlink(missing_ok=True)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"decision": "block"', result.stdout)
        self.assertIn("SEN-2-DROUGHT", result.stdout)


class TestSEN0MarkerScoping(unittest.TestCase):
    """G-1b / DI-1b: [acknowledge-open-work-items] in assistant prose clears
    SEN-0 ONLY -- it must not clear SEN-1 (dual-state), which is exactly the
    F-B3 defect a literal (adapter-level) migration of the marker would have
    reintroduced. (r8: SEN-2, the drought invariant this docstring originally
    also named as a thing the marker must not clear, is cut -- design.md
    §0.9.)"""

    def test_marker_clears_sen0_but_not_sen1(self) -> None:
        root = make_git_repo()
        active = root / "work-items" / "active" / "dup-slug"
        active.mkdir(parents=True)
        (active / "closure.md").write_text("outcome: PASS", encoding="utf-8")  # SEN-0 orphan
        archive = root / "work-items" / "archive" / "2026-06" / "dup-slug"
        archive.mkdir(parents=True)  # ALSO archived -> SEN-1 dual-state

        ctx = sentinels.build_context(
            str(root),
            last_assistant_message="leaving it open [acknowledge-open-work-items]",
        )
        findings = sentinels.evaluate_all(ctx)
        ids = {f.id: f.severity for f in findings}
        self.assertNotIn("SEN-0", ids, "the marker must clear SEN-0")
        self.assertIn("SEN-1", ids, "the marker must NOT clear SEN-1 (F-B3)")

    def test_marker_absent_both_fire(self) -> None:
        root = make_git_repo()
        active = root / "work-items" / "active" / "dup-slug"
        active.mkdir(parents=True)
        (active / "closure.md").write_text("outcome: PASS", encoding="utf-8")
        archive = root / "work-items" / "archive" / "2026-06" / "dup-slug"
        archive.mkdir(parents=True)

        ctx = sentinels.build_context(str(root), last_assistant_message="done")
        findings = sentinels.evaluate_all(ctx)
        ids = {f.id for f in findings}
        self.assertIn("SEN-0", ids)
        self.assertIn("SEN-1", ids)

    def test_marker_in_operators_own_message_also_clears_sen0(self) -> None:
        """F3 regression: SEN-0's marker text must also clear via the
        operator-only channel -- the §4.4a stop_hook_active escalation
        (`systemMessage`), which is the only operator-directed output this
        registry now emits (r7 removed HALT's `stopReason` entirely; r8 cut
        SEN-2, whose [approve-review-continuation] marker was this pattern's
        prior precedent) -- but the marker check used to read ONLY
        last_assistant_message, the MODEL's own reply, never the operator's.
        An operator typing the marker in their own next message must also
        clear SEN-0."""
        root = make_git_repo()
        active = root / "work-items" / "active" / "orphan"
        active.mkdir(parents=True)
        (active / "closure.md").write_text("outcome: PASS", encoding="utf-8")

        ctx = sentinels.build_context(
            str(root),
            last_assistant_message="done",  # no marker from the model
            user_message_text="ok, [acknowledge-open-work-items] proceed",
        )
        findings = sentinels.evaluate_all(ctx)
        self.assertFalse(
            any(f.id == "SEN-0" for f in findings),
            "the operator's own marker (user_message_text) must also clear SEN-0 (F3)",
        )


class TestDI4NoT2SignalOutsideDeclaredExemption(unittest.TestCase):
    """G-4: no sentinel EVALUATION path reads a T2 (model-authored) signal.
    The one declared exception (SEN-0's marker) lives inside an explicitly
    delimited block INSIDE `_sen0_evaluate`; everywhere else in an
    evaluate()-path function, reading the ledger, status.md-as-a-ledger-proxy,
    or last_assistant_message would silently reintroduce the proven defect
    (the incident's failing session called the fail-closed ledger helper 705
    times, then simply stopped).

    Scoped to actual evaluation-path function SOURCE (via `inspect.getsource`),
    not the whole file: `build_context` legitimately carries
    `last_assistant_message` as a CTX FIELD NAME (it has to be named
    something), and the module docstring legitimately NAMES these signals to
    explain why they are banned. Neither is an evaluation path."""

    BANNED_PATTERNS = ("agent-runs", "agent_run_ledger", "status.md", "last_assistant_message")

    # r8: SEN-2's evaluate()-path functions (_sen2_evaluate, _sen2_item_verdict,
    # _git_log_touching, _git_diff_tree_files_batch, _find_item_L,
    # _current_file_count, _tree_file_count) were all deleted with the
    # invariant itself (design.md §0.9) -- they no longer exist to import.
    EVALUATION_PATH_FUNCTIONS = (
        "_sen1_evaluate",
        "resolve_slug_locations",
    )

    def test_banned_signals_absent_from_evaluation_path_functions(self) -> None:
        import inspect

        for name in self.EVALUATION_PATH_FUNCTIONS:
            func = getattr(sentinels, name)
            source = inspect.getsource(func)
            for pattern in self.BANNED_PATTERNS:
                with self.subTest(function=name, pattern=pattern):
                    self.assertNotIn(pattern, source)

    def test_sen0_evaluate_confines_the_one_declared_exemption(self) -> None:
        import inspect

        source = inspect.getsource(sentinels._sen0_evaluate)
        begin = source.index("# --- BEGIN DECLARED T2 EXEMPTION")
        end = source.index("# --- END DECLARED T2 EXEMPTION") + len("# --- END DECLARED T2 EXEMPTION")
        declared_block = source[begin:end]
        outside = source[:begin] + source[end:]
        # The declared block DOES reference the one admitted T2 signal (proves
        # the block exists and is where the marker check actually lives).
        self.assertIn("last_assistant_message", declared_block)
        # Everything in _sen0_evaluate OUTSIDE that block must be clean too --
        # the detection logic itself (item/epic orphan scan) must not read a
        # T2 signal either; only the declared exemption may.
        for pattern in ("agent-runs", "agent_run_ledger"):
            with self.subTest(pattern=pattern):
                self.assertNotIn(pattern, outside)


class TestDI5NoValidatorImport(unittest.TestCase):
    """G-5: the sentinel surface never imports the 4079-line-on-a-real-repo
    document validator. Binding the always-on Stop path to it is the named
    trap (Sentinel != Validator, design.md §3.2).

    Checked via the AST's actual `import` / `from ... import` statements, not
    a whole-file text grep: the module docstring legitimately NAMES
    `check-work-items-state.py` in prose to explain why it must never be
    imported, and that mention is not the defect this guard polices."""

    BANNED_MODULE_SUBSTRINGS = ("check_work_items_state", "check-work-items-state", "validate_work_item_state", "validate-work-item-state")

    def test_no_validator_import(self) -> None:
        import ast

        tree = ast.parse(CANON_MODULE.read_text(encoding="utf-8"))
        imported_names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_names.append(node.module)
        for name in imported_names:
            for banned in self.BANNED_MODULE_SUBSTRINGS:
                with self.subTest(imported=name, banned=banned):
                    self.assertNotIn(banned, name)
        # Sanity: prove the AST walk sees real imports at all (else the test
        # would vacuously pass on a module with no imports whatsoever).
        self.assertIn("re", imported_names)


class TestDI8LedgerUntouchedAndNotAnInput(unittest.TestCase):
    """G-8: the sentinel never loads the ledger helper or reads its output.
    T-2: the anti-abandonment proof -- delete the ledger entirely from a
    fixture and assert every verdict is unchanged (the sentinel never reads it
    at all -- confirmed precisely, function-scoped, by
    TestDI4NoT2SignalOutsideDeclaredExemption)."""

    def test_sentinel_does_not_load_ledger_helper(self) -> None:
        source = CANON_MODULE.read_text(encoding="utf-8")
        self.assertNotIn("agent-run-ledger.py", source)

    def test_verdict_unchanged_with_or_without_ledger_file(self) -> None:
        root = make_git_repo()
        item = root / "work-items" / "active" / "some-item"
        item.mkdir(parents=True)
        (item / "closure.md").write_text("x", encoding="utf-8")

        ctx = sentinels.build_context(str(root))
        before = [(f.id, f.severity, f.message) for f in sentinels.evaluate_all(ctx)]

        # Simulate the incident's escape route: a well-formed ledger present...
        (item / "agent-runs.jsonl").write_text(
            json.dumps({"runId": "r1", "status": "PASS", "updatedAt": "2026-07-20T01:02:00+00:00"}) + "\n",
            encoding="utf-8",
        )
        ctx2 = sentinels.build_context(str(root))
        with_ledger = [(f.id, f.severity, f.message) for f in sentinels.evaluate_all(ctx2)]

        # ...then delete it entirely (the actual incident shape: the session
        # stopped writing to it).
        (item / "agent-runs.jsonl").unlink()
        ctx3 = sentinels.build_context(str(root))
        without_ledger = [(f.id, f.severity, f.message) for f in sentinels.evaluate_all(ctx3)]

        self.assertEqual(before, with_ledger)
        self.assertEqual(before, without_ledger)


class TestSEN1DualState(unittest.TestCase):
    def test_disk_only_dual_state_detected(self) -> None:
        root = make_git_repo()  # git present but nothing committed -> HEAD leg empty
        active = root / "work-items" / "active" / "dup"
        active.mkdir(parents=True)
        archive = root / "work-items" / "archive" / "2026-06" / "dup"
        archive.mkdir(parents=True)

        ctx = sentinels.build_context(str(root))
        self.assertEqual(ctx["legs"], "disk")
        findings = sentinels.evaluate_all(ctx)
        sen1 = [f for f in findings if f.id == "SEN-1"]
        self.assertEqual(len(sen1), 1)
        self.assertEqual(sen1[0].severity, sentinels.RESOLVE)
        self.assertIn("dup", sen1[0].message)
        # The reason must not TEACH the erasure command (FM-3 fix): it must
        # instruct re-opening, never literally suggest deleting the copy.
        self.assertNotIn("rm -rf", sen1[0].message)
        self.assertIn("archive copy", sen1[0].message)

    def test_head_leg_detects_resurrection_after_disk_copy_removed(self) -> None:
        # Reproduces the incident's own retrospective shape: the archive copy
        # was deleted from the WORKING TREE but is still present in HEAD.
        root = make_git_repo()
        active = root / "work-items" / "active" / "dup"
        active.mkdir(parents=True)
        (active / "status.md").write_text("State: active\n", encoding="utf-8")
        archive = root / "work-items" / "archive" / "2026-06" / "dup"
        archive.mkdir(parents=True)
        (archive / "status.md").write_text("State: closed\n", encoding="utf-8")
        commit_all(root, "track both copies", "2026-07-10T10:00:00+00:00")
        # Now delete the archive copy from disk only (uncommitted removal).
        import shutil

        shutil.rmtree(archive)

        ctx = sentinels.build_context(str(root))
        self.assertEqual(ctx["legs"], "both")
        findings = sentinels.evaluate_all(ctx)
        sen1 = [f for f in findings if f.id == "SEN-1"]
        self.assertEqual(len(sen1), 1, "the HEAD leg must still see the archived copy")
        self.assertIn("HEAD", sen1[0].message)

    def test_no_dual_state_no_finding(self) -> None:
        root = make_git_repo()
        active = root / "work-items" / "active" / "solo"
        active.mkdir(parents=True)
        ctx = sentinels.build_context(str(root))
        findings = sentinels.evaluate_all(ctx)
        self.assertFalse(any(f.id == "SEN-1" for f in findings))


class TestEpicArchiveLifecycle(unittest.TestCase):
    def _root(self) -> Path:
        root = make_git_repo()
        (root / "work-items" / "active").mkdir(parents=True)
        (root / "work-items" / "epics").mkdir(parents=True)
        return root

    @staticmethod
    def _write_epic(path: Path, status: str, children: tuple[str, ...] = ()) -> None:
        child_lines = "".join(f"- {slug} (active)\n" for slug in children)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"---\nstatus: {status}\n---\n# Epic\n\n## Children\n{child_lines}",
            encoding="utf-8",
        )

    def test_resolver_distinguishes_missing_active_archived_and_duplicate(self) -> None:
        root = self._root()
        epics = root / "work-items" / "epics"
        self.assertEqual(sentinels.resolve_epic_locations(epics, "e1")["state"], "missing")

        active = epics / "e1.md"
        self._write_epic(active, "active")
        self.assertEqual(sentinels.resolve_epic_locations(epics, "e1")["state"], "active")

        archived = epics / "archive" / "2026-07" / "e1.md"
        archived.parent.mkdir(parents=True)
        active.replace(archived)
        self.assertEqual(sentinels.resolve_epic_locations(epics, "e1")["state"], "archived")

        self._write_epic(active, "active")
        resolution = sentinels.resolve_epic_locations(epics, "e1")
        self.assertEqual(resolution["state"], "duplicate")
        self.assertEqual(len(resolution["locations"]), 2)

    def test_resolver_fails_closed_on_duplicate_archive_months(self) -> None:
        root = self._root()
        epics = root / "work-items" / "epics"
        for month in ("2026-06", "2026-07"):
            self._write_epic(epics / "archive" / month / "e1.md", "closed")
        resolution = sentinels.resolve_epic_locations(epics, "e1")
        self.assertEqual(resolution["state"], "duplicate")
        self.assertEqual(len(resolution["archive"]), 2)

    def test_closed_epic_in_active_root_flags_even_without_children(self) -> None:
        root = self._root()
        self._write_epic(root / "work-items" / "epics" / "e1.md", "closed")
        findings = sentinels.evaluate_all(sentinels.build_context(str(root)))
        sen0 = [finding for finding in findings if finding.id == "SEN-0"]
        self.assertEqual(len(sen0), 1)
        self.assertIn("remains in the active root", sen0[0].message)

    def test_archived_closed_epic_with_reopened_child_flags(self) -> None:
        root = self._root()
        child = root / "work-items" / "active" / "kid"
        child.mkdir()
        (child / "status.md").write_text("State: active\n", encoding="utf-8")
        self._write_epic(
            root / "work-items" / "epics" / "archive" / "2026-07" / "e1.md",
            "closed",
            ("kid",),
        )
        findings = sentinels.evaluate_all(sentinels.build_context(str(root)))
        sen0 = [finding for finding in findings if finding.id == "SEN-0"]
        self.assertEqual(len(sen0), 1)
        self.assertIn("archived epic has a child work-item that is not closed", sen0[0].message)

    def test_archived_active_epic_requires_same_operation_restore(self) -> None:
        root = self._root()
        archived = root / "work-items" / "epics" / "archive" / "2026-07" / "e1.md"
        self._write_epic(archived, "active")
        findings = sentinels.evaluate_all(sentinels.build_context(str(root)))
        sen0 = [finding for finding in findings if finding.id == "SEN-0"]
        self.assertEqual(len(sen0), 1)
        self.assertIn("restore it to the active root", sen0[0].message)

        active = root / "work-items" / "epics" / "e1.md"
        archived.replace(active)
        findings = sentinels.evaluate_all(sentinels.build_context(str(root)))
        self.assertFalse(any(finding.id == "SEN-0" for finding in findings))

    def test_duplicate_epic_locations_flag_without_selecting_a_copy(self) -> None:
        root = self._root()
        epics = root / "work-items" / "epics"
        self._write_epic(epics / "e1.md", "active")
        self._write_epic(epics / "archive" / "2026-07" / "e1.md", "closed")
        findings = sentinels.evaluate_all(sentinels.build_context(str(root)))
        sen0 = [finding for finding in findings if finding.id == "SEN-0"]
        self.assertEqual(len(sen0), 1)
        self.assertIn("resolves to multiple locations", sen0[0].message)
        self.assertIn("archive/2026-07/e1.md", sen0[0].message)


class TestF4NonMonthArchiveLayout(unittest.TestCase):
    """Regression for the archive-layout regression (design.md review-
    grounding F4): a non-month category directory one level under
    work-items/archive/ (e.g. archive/legacy/<slug>/) must be traversed
    exactly like a month directory (archive/2026-07/<slug>/). An earlier
    revision of `_disk_archive_slug_pairs` / `_git_archive_slug_pairs`
    descended only into children matching `^\\d{4}-\\d{2}$`, silently
    dropping any slug filed under a non-month category directory from BOTH
    SEN-0's epic-orphan detection and SEN-1's dual-state detection --
    verdict-equivalence-breaking against the OLD shipped hook, which globbed
    any one-level archive subdirectory (`archive_dir.glob(f"*/{slug}")`)
    regardless of its name. Present in the wild:
    `VFEM_fort/work-items/archive/clean-wave-port/`."""

    def _epic_with_child_archived_under(self, category: str, epic_status: str) -> Path:
        root = make_git_repo()
        # work-items/active/ must EXIST (even empty) or _find_active_dir
        # returns None and build_context short-circuits before ever reaching
        # epics_dir/archive_slug_paths -- the child itself lives only in
        # archive/, not active/, since it is (correctly) fully archived.
        (root / "work-items" / "active").mkdir(parents=True)
        epics = root / "work-items" / "epics"
        epic_path = epics / "e1.md" if epic_status == "active" else epics / "archive" / "2026-07" / "e1.md"
        epic_path.parent.mkdir(parents=True)
        epic_path.write_text(
            f"---\nstatus: {epic_status}\n---\n# Epic: demo\n\n## Children\n- kid (active)\n",
            encoding="utf-8",
        )
        archive = root / "work-items" / "archive" / category / "kid"
        archive.mkdir(parents=True)
        return root

    def test_active_epic_with_child_archived_under_non_month_category_flags(self) -> None:
        # Old behaviour (archive_dir.glob(f"*/{slug}")) treated "kid" as done
        # regardless of the intermediate directory's name: an active epic
        # whose only child is fully archived must be flagged to close it.
        # The month-only regression silently DROPPED this finding.
        root = self._epic_with_child_archived_under("legacy", "active")
        ctx = sentinels.build_context(str(root))
        findings = sentinels.evaluate_all(ctx)
        sen0 = [f for f in findings if f.id == "SEN-0"]
        self.assertEqual(
            len(sen0), 1,
            "a child archived under a non-month category dir must still count as done (F4) -- "
            "the guard must not be silently dropped",
        )
        self.assertIn("e1", sen0[0].message)

    def test_closed_epic_with_child_archived_under_non_month_category_does_not_flag(self) -> None:
        # A closed epic whose only child IS actually archived (done) must NOT
        # flag. The month-only regression treated "kid" as NOT done (since
        # "legacy" is not month-shaped) and produced a NEW false
        # decision:block here.
        root = self._epic_with_child_archived_under("legacy", "closed")
        ctx = sentinels.build_context(str(root))
        findings = sentinels.evaluate_all(ctx)
        sen0 = [f for f in findings if f.id == "SEN-0"]
        self.assertEqual(
            len(sen0), 0,
            "a closed epic whose child is archived under a non-month category dir must not "
            "false-fire (F4 regression: this used to wrongly emit decision:block)",
        )

    def test_sen1_dual_state_detected_under_non_month_archive_category(self) -> None:
        root = make_git_repo()
        active = root / "work-items" / "active" / "kid"
        active.mkdir(parents=True)
        archive = root / "work-items" / "archive" / "legacy" / "kid"
        archive.mkdir(parents=True)

        ctx = sentinels.build_context(str(root))
        findings = sentinels.evaluate_all(ctx)
        sen1 = [f for f in findings if f.id == "SEN-1"]
        self.assertEqual(len(sen1), 1, "a non-month archive category dir must not hide the dual-state slug (F4)")
        self.assertIn("kid", sen1[0].message)

    def test_disk_archive_slug_pairs_covers_non_month_category_and_flat(self) -> None:
        root = make_git_repo()
        archive = root / "work-items" / "archive"
        (archive / "legacy" / "kid").mkdir(parents=True)
        (archive / "2026-07" / "other").mkdir(parents=True)
        (archive / "flat-slug").mkdir(parents=True)
        pairs = dict(sentinels._disk_archive_slug_pairs(archive))
        self.assertEqual(pairs.get("kid"), "legacy/kid")
        self.assertEqual(pairs.get("other"), "2026-07/other")
        self.assertIn("flat-slug", pairs)


# r8 (design.md §0.9): TestSEN2Drought is REMOVED here, not skipped. SEN-2
# (delivery drought) was cut from this release -- T-20 measured that a bare
# `systemMessage` NOTICE does not reach the operator on the Codex line
# either, the same line the admitted incident happened on -- so every
# _sen2_evaluate / _sen2_item_verdict call this class made now targets a
# function that no longer exists. See decision
# `2026-07-26-delivery-drought-needs-a-substrate-not-a-threshold` for the
# re-proposal on a different substrate.


class TestG11ResolveSuppressedUnderStopHookActive(unittest.TestCase):
    """Every RESOLVE-tier entry, exercised with stop_hook_active: true, must
    yield NO continuation -- no `decision` field, and the adapter must not
    re-fire the model. (DI-11.)"""

    def test_sen0_resolve_suppressed_via_adapter(self) -> None:
        root = make_git_repo()
        item = root / "work-items" / "active" / "orphan"
        item.mkdir(parents=True)
        (item / "closure.md").write_text("x", encoding="utf-8")
        for script in ADAPTERS:
            with self.subTest(pack=script.parent.parent.name):
                p = run_adapter(script, {"cwd": str(root), "stop_hook_active": True, "last_assistant_message": "done"})
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertNotIn('"decision"', p.stdout)

    def test_sen1_resolve_suppressed_via_adapter(self) -> None:
        root = make_git_repo()
        active = root / "work-items" / "active" / "dup"
        active.mkdir(parents=True)
        archive = root / "work-items" / "archive" / "2026-06" / "dup"
        archive.mkdir(parents=True)
        for script in ADAPTERS:
            with self.subTest(pack=script.parent.parent.name):
                p = run_adapter(script, {"cwd": str(root), "stop_hook_active": True, "last_assistant_message": "done"})
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertNotIn('"decision"', p.stdout)


class TestG13TierEscalation(unittest.TestCase):
    """G-13/T-10/DI-12: a RESOLVE-tier finding suppressed by stop_hook_active
    additionally emits a turn-free NOTICE naming the invariant, in the SAME
    evaluation, with no `decision` field present."""

    def test_sen1_suppressed_resolve_escalates_to_notice(self) -> None:
        root = make_git_repo()
        active = root / "work-items" / "active" / "dup-esc"
        active.mkdir(parents=True)
        archive = root / "work-items" / "archive" / "2026-06" / "dup-esc"
        archive.mkdir(parents=True)
        for script in ADAPTERS:
            with self.subTest(pack=script.parent.parent.name):
                p = run_adapter(script, {"cwd": str(root), "stop_hook_active": True, "last_assistant_message": "done"})
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertNotIn('"decision"', p.stdout)
                self.assertIn('"systemMessage"', p.stdout)
                self.assertIn("SEN-1", p.stdout)
                self.assertIn("dup-esc", p.stdout)

    def test_no_stop_hook_active_no_escalation_wrapper(self) -> None:
        # Sanity: without stop_hook_active, SEN-1 emits a plain RESOLVE
        # (decision:block), not an escalation notice.
        root = make_git_repo()
        active = root / "work-items" / "active" / "dup-noesc"
        active.mkdir(parents=True)
        archive = root / "work-items" / "archive" / "2026-06" / "dup-noesc"
        archive.mkdir(parents=True)
        p = run_adapter(CANON_ADAPTER, {"cwd": str(root), "last_assistant_message": "done"})
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('"decision"', p.stdout)
        self.assertIn('"block"', p.stdout)


class TestR7NoHaltTierExists(unittest.TestCase):
    """r7 (T-14, design.md §4.4c/§1.0): the HALT tier is REMOVED, not merely
    unused. `workitem_sentinels.HALT` must not exist as a severity constant
    (so no registry entry can even construct a HALT Finding), and the
    adapter's `_build_payload` must never emit a `continue` key for any
    combination of findings -- a NOTICE, however severe its own text band,
    must reach the operator via `systemMessage` alone, exactly like any
    other NOTICE. (r8: the SEN-2 invariant this test originally drove via its
    own HARD-band finding is cut -- design.md §0.9; the test now drives the
    adapter's severity mapping with a synthetic Finding directly, since
    `_build_payload` is generic over id/severity/message and does not care
    which invariant produced them.)"""

    def test_halt_severity_constant_does_not_exist(self) -> None:
        self.assertFalse(hasattr(sentinels, "HALT"), "the HALT severity constant must be deleted, not merely unused (r7)")

    def test_notice_severity_finding_never_emits_continue_key(self) -> None:
        # Drives the adapter's severity mapping directly via a synthetic
        # NOTICE finding, independent of any specific invariant's own logic.
        adapter, adapter_dir, added = _load_adapter_module()
        try:
            notice_finding = sentinels.Finding("TEST-NOTICE", sentinels.NOTICE, "synthetic notice band=HARD")
            payload = adapter._build_payload([notice_finding], stop_hook_active=False)
        finally:
            if added:
                sys.path.remove(adapter_dir)
        self.assertIsNotNone(payload)
        self.assertNotIn("continue", payload)
        self.assertNotIn("decision", payload)
        self.assertIn("synthetic notice", payload.get("systemMessage", ""))


def _load_adapter_module():
    """Shared helper: import the canon adapter via importlib, matching the
    real runtime's bare-name sibling-module resolution (sys.path[0])."""
    adapter_dir = str(CANON_ADAPTER.parent)
    added = adapter_dir not in sys.path
    if added:
        sys.path.insert(0, adapter_dir)
    try:
        adapter_spec = importlib.util.spec_from_file_location("archival_adapter_under_test_f10", CANON_ADAPTER)
        adapter = importlib.util.module_from_spec(adapter_spec)
        adapter_spec.loader.exec_module(adapter)
        return adapter, adapter_dir, added
    except Exception:
        if added:
            sys.path.remove(adapter_dir)
        raise


class TestF10PayloadTruncation(unittest.TestCase):
    """F10: the runtime documents a 10,000-character cap on `systemMessage` /
    plain stdout. A finding's message grows with the number of items it
    reports (unbounded in item count), so the combined payload must be capped
    proactively, and the cap must degrade INFORMATIVELY -- never silently."""

    def test_short_text_untouched(self) -> None:
        adapter, adapter_dir, added = _load_adapter_module()
        try:
            text = "short and well under the cap"
            self.assertEqual(adapter._cap_payload_text(text), text)
        finally:
            if added:
                sys.path.remove(adapter_dir)

    def test_long_text_truncated_with_informative_notice(self) -> None:
        adapter, adapter_dir, added = _load_adapter_module()
        try:
            long_text = "\n".join(f"  - item{i}: droughted" for i in range(2000))
            self.assertGreater(len(long_text), adapter.MAX_PAYLOAD_CHARS)
            capped = adapter._cap_payload_text(long_text)
            self.assertLessEqual(len(capped), adapter.MAX_PAYLOAD_CHARS)
            self.assertIn("TRUNCATED", capped)
            self.assertIn(str(len(long_text)), capped, "the notice must state the ORIGINAL total length")
        finally:
            if added:
                sys.path.remove(adapter_dir)

    def test_truncation_never_splits_mid_line(self) -> None:
        adapter, adapter_dir, added = _load_adapter_module()
        try:
            long_text = "\n".join(f"line-{i:05d}-marker-free-content" for i in range(1000))
            capped = adapter._cap_payload_text(long_text)
            body = capped.split("\n\n[... TRUNCATED")[0]
            # Every line in the kept body must be a COMPLETE original line,
            # never a partial one cut mid-word.
            original_lines = set(long_text.splitlines())
            for line in body.splitlines():
                self.assertIn(line, original_lines, f"truncation split a line: {line!r}")
        finally:
            if added:
                sys.path.remove(adapter_dir)

    def test_notice_payload_capped_end_to_end(self) -> None:
        # No tier ever emits `continue` (HALT removed at r7; r8 cut SEN-2,
        # the invariant whose unbounded item-count growth this cap
        # originally guarded against -- design.md §0.9). Any NOTICE with an
        # unbounded item list still needs the same cap, so this drives the
        # adapter's mapping with a synthetic oversized NOTICE, independent of
        # which invariant produced it.
        adapter, adapter_dir, added = _load_adapter_module()
        try:
            huge_message = "\n".join(f"  - item-{i}: synthetic detail line" for i in range(2000))
            notice_finding = sentinels.Finding("TEST-NOTICE", sentinels.NOTICE, huge_message)
            payload = adapter._build_payload([notice_finding], stop_hook_active=False)
        finally:
            if added:
                sys.path.remove(adapter_dir)
        self.assertIsNotNone(payload)
        self.assertNotIn("continue", payload)
        self.assertNotIn("decision", payload)
        self.assertLessEqual(len(payload["systemMessage"]), adapter.MAX_PAYLOAD_CHARS)
        self.assertIn("TRUNCATED", payload["systemMessage"])


class TestG12CensusInventory(unittest.TestCase):
    """G-12: the census of always-on, matcher-less, repository-state hooks is
    machine-checked, not asserted in prose. Every such hook is either a
    registry entry (workitem_sentinels.REGISTRY) or a declared, tracked
    exception with a named owner."""

    # Declared tracked exception (design.md §2.2 instance A'/§14 follow-up):
    # check-scratch-valuables migrates onto a future SessionStart adapter;
    # until then it stays a hand-duplicated, independently-shipped detector.
    DECLARED_EXCEPTIONS = {
        "check-scratch-valuables": "2026-07-25-migrate-scratch-valuables-to-sentinel-registry",
    }

    def test_stop_and_sessionstart_repo_state_hooks_are_registry_or_declared(self) -> None:
        installer = (REPO_ROOT / "scripts" / "install-claude.sh").read_text(encoding="utf-8")
        # The two matcher-less, repository-state hooks this design's own
        # census names (design.md §2.1): the archival/sentinel Stop hook
        # (now the registry adapter) and check-scratch-valuables.
        self.assertIn("check-work-items-archival-stop", installer)
        self.assertIn("check-scratch-valuables", installer)
        registry_ids = {e["id"] for e in sentinels.REGISTRY}
        self.assertTrue(registry_ids, "the registry must not be empty")
        self.assertIn("check-scratch-valuables", self.DECLARED_EXCEPTIONS)


class TestT3SubagentSkip(unittest.TestCase):
    def test_agent_id_suppresses_sen1(self) -> None:
        root = make_git_repo()
        active = root / "work-items" / "active" / "dup"
        active.mkdir(parents=True)
        archive = root / "work-items" / "archive" / "2026-06" / "dup"
        archive.mkdir(parents=True)
        for script in ADAPTERS:
            with self.subTest(pack=script.parent.parent.name):
                p = run_adapter(script, {"cwd": str(root), "agent_id": "sub-1", "last_assistant_message": "done"})
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(p.stdout.strip(), "")


# r8 (post-cut cleanup): TestT4Determinism is REMOVED here, not skipped. Its
# entire premise (T-4, design.md) was proving `build_context`/`evaluate_all`
# gave byte-identical output for a fixed `--now` -- a property that mattered
# only for SEN-2's date arithmetic. Once SEN-2 was cut, an earlier pass kept
# the class alive by re-pointing it at a SEN-1 dual-state fixture that does
# not depend on `now` at all, which made the assertion trivially true (two
# identical inputs producing two identical outputs, regardless of what `now`
# was). `build_context` has since dropped the dead `now` parameter entirely
# (nothing in SEN-0/SEN-1's evaluate paths ever read `ctx["now"]`), so the
# class is deleted rather than adapted a second time to a parameter that no
# longer exists.


class TestG6SignalBudget(unittest.TestCase):
    """DI-6: zero output on a healthy repository. Run over Orchestrarium's
    OWN real work-items/ tree (T-13: the pack-default, gitignored posture --
    the primary case, not the divergent tracked layout) and a VFEM-shaped
    unhealthy fixture (T-1). (r8: the fixture originally also carried a
    droughted-item instance for SEN-2; that instance and its assertion are
    removed with the invariant -- design.md §0.9 -- leaving the dual-state
    instance alone.)"""

    def test_zero_findings_on_orchestrarium_own_tree(self) -> None:
        ctx = sentinels.build_context(str(REPO_ROOT))
        self.assertEqual(ctx["legs"], "disk", "Orchestrarium's own work-items/ is gitignored -- pack-default posture")
        findings = sentinels.evaluate_all(ctx)
        self.assertEqual(
            findings, [],
            f"unexpected findings on the pack's own healthy repo: {[(f.id, f.message) for f in findings]}",
        )

    def test_vfem_shaped_unhealthy_fixture_yields_findings(self) -> None:
        root = make_git_repo()
        # Instance C: a resurrected dual-state slug.
        active = root / "work-items" / "active" / "resurrected"
        active.mkdir(parents=True)
        (active / "status.md").write_text("State: active\n", encoding="utf-8")
        archive = root / "work-items" / "archive" / "2026-06" / "resurrected"
        archive.mkdir(parents=True)
        (archive / "status.md").write_text("State: closed\n", encoding="utf-8")

        ctx = sentinels.build_context(str(root))
        findings = sentinels.evaluate_all(ctx)
        ids = {f.id for f in findings}
        self.assertIn("SEN-1", ids)
        self.assertEqual(len(findings), 1, f"expected exactly 1 finding, got {[(f.id) for f in findings]}")


# r8 (design.md §0.9): TestG17T15DegradedMagnitudeSoundness is REMOVED here,
# not skipped. It was the executable soundness proof for SEN-2's degraded
# mode (§2.4a/F1); SEN-2 itself is cut, so both its fixture
# (`_repo_with_spiraled_item`) and its target (`_sen2_evaluate`) no longer
# exist.


class TestG14T16BoundedReverseScan(unittest.TestCase):
    """G-14 / T-16 (design.md §4.5, F2) -- the gate's own falsifier: an
    operator marker followed by many filler records must still be found by
    `hook_common.last_genuine_user_text`'s bounded REVERSE scan, at record
    counts where the OLD fixed-window read (`read_transcript_tail(path,
    100)`) would already have missed it. Parameterized at 100, 300, 1000 and
    5000 filler records (p90 real turn is 346 -- P-r6d)."""

    @staticmethod
    def _make_transcript(marker_text: str, n_filler: int) -> Path:
        lines = [json.dumps({"type": "user", "message": {"role": "user", "content": marker_text}})]
        for i in range(n_filler):
            lines.append(
                json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": f"working step {i} " * 5}]}})
            )
        tmp = Path(tempfile.mktemp(suffix=".jsonl"))
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return tmp

    def test_marker_found_beyond_the_old_100_record_window(self) -> None:
        import hook_common

        for n_filler in (100, 300, 1000, 5000):
            with self.subTest(n_filler=n_filler):
                tp = self._make_transcript("ok [approve-review-continuation] please continue", n_filler)
                try:
                    text, status = hook_common.last_genuine_user_text(str(tp), byte_cap=64 * 1024 * 1024)
                    self.assertEqual(status, "found")
                    self.assertIn("[approve-review-continuation]", text)
                    # Prove this is a REAL fix, not a redundant addition: the
                    # OLD fixed-100-line approach must NOT find it once
                    # n_filler exceeds the window.
                    if n_filler > 100:
                        old_entries = hook_common.read_transcript_tail(str(tp), 100)
                        old_entry, _old_text, _after = hook_common.last_genuine_user_message(old_entries)
                        self.assertIsNone(old_entry, f"old fixed-window approach unexpectedly found the marker at n_filler={n_filler}")
                finally:
                    tp.unlink()

    def test_byte_cap_boundary_returns_not_in_window(self) -> None:
        import hook_common

        tp = self._make_transcript("ok [approve-review-continuation] please continue", 5000)
        try:
            text, status = hook_common.last_genuine_user_text(str(tp), byte_cap=4096)
            self.assertEqual(status, "not-in-window")
            self.assertEqual(text, "")
        finally:
            tp.unlink()

    def test_end_to_end_marker_beyond_100_records_clears_sen0_via_adapter(self) -> None:
        # The full path: a real SEN-0 archival-orphan fixture, a real
        # transcript with the OPERATOR's own marker 300 filler records deep,
        # fed through the actual adapter subprocess (not build_context
        # directly) -- this is what F2 fixes, end to end.
        #
        # r8: this test originally exercised SEN-2's old
        # [approve-review-continuation] marker. The transcript reader is now
        # justified by SEN-0's F3 T1 widening instead (§0.9.4). The marker
        # used here is therefore SEN-0's own,
        # [acknowledge-open-work-items], read from the operator's channel
        # (user_message_text via last_genuine_user_text), not the model's
        # last_assistant_message -- proving the reverse scan still finds an
        # operator marker buried deep in a transcript when routed to a
        # different invariant's exemption.
        root = make_git_repo()
        item = root / "work-items" / "active" / "orphan-e2e"
        item.mkdir(parents=True)
        (item / "closure.md").write_text("outcome: PASS", encoding="utf-8")
        (item / "status.md").write_text(
            """## Delivery action

- **Primary**: true
- **Fingerprint**: sen0-marker-isolation
- **Class**: mutation
- **Target**: closure.md
- **Oracle**: correlated-success
""",
            encoding="utf-8",
        )
        tp = self._make_transcript("ok [acknowledge-open-work-items] please continue", 300)
        try:
            with tp.open("a", encoding="utf-8") as handle:
                for record in (
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "custom_tool_call",
                            "call_id": "sen0-isolation-delivery",
                            "name": "apply_patch",
                            "input": "*** Update File: closure.md",
                        },
                    },
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "custom_tool_call_output",
                            "call_id": "sen0-isolation-delivery",
                            "output": "Exit code: 0",
                        },
                    },
                ):
                    handle.write(json.dumps(record) + "\n")
            p = run_adapter(
                CANON_ADAPTER,
                {"cwd": str(root), "last_assistant_message": "done", "transcript_path": str(tp)},
            )
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(
                p.stdout.strip(), "",
                f"the operator's marker 300 records deep must clear SEN-0 via the bounded reverse scan; got {p.stdout!r}",
            )
        finally:
            tp.unlink()


# r8 (design.md §0.9): TestG15T17OverrideChannelUnavailability is REMOVED
# here, not skipped. `override-channel` belonged to SEN-2's retired
# read-status discriminator and was folded into that design's NOTICE text;
# the current SEN-2 no longer emits an `override-channel=...` token (the underlying
# hook_common.last_genuine_user_text status tuple is still returned and
# still exercised directly -- TestG14T16BoundedReverseScan.
# test_byte_cap_boundary_returns_not_in_window -- just no longer surfaced by
# name in any adapter payload).


class TestG16T18HookCommonAdditivity(unittest.TestCase):
    """G-16 / T-18 (design.md DI-13): adding `last_genuine_user_text` to
    `hook_common.py` must move NOTHING existing. `read_transcript_tail` stays
    byte-identical to what it has always been, and the four other callers'
    own suites pass unchanged."""

    def test_read_transcript_tail_source_unchanged(self) -> None:
        import inspect

        import hook_common

        source = inspect.getsource(hook_common.read_transcript_tail)
        self.assertIn("def read_transcript_tail(transcript_path: str, n: int = 100) -> list[dict]:", source)
        self.assertIn("raw.splitlines()[-n:]", source)

    def test_other_four_callers_suites_pass_unchanged(self) -> None:
        other_suites = (
            "test_bugfix_discipline_hook.py",
            "test_git_push_gate_hook.py",
            "test_passive_polling_stop.py",
            "test_repository_orientation_hook.py",
        )
        for suite in other_suites:
            path = REPO_ROOT / "tests" / suite
            if not path.is_file():
                self.fail(f"expected suite not found: {path}")
            with self.subTest(suite=suite):
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", str(path), "-q"],
                    capture_output=True, text=True, cwd=str(REPO_ROOT),
                )
                self.assertEqual(result.returncode, 0, f"{suite} failed:\n{result.stdout}\n{result.stderr}")


# r8 (design.md §0.9): TestT19DegradedTierCalibrationRegression is REMOVED
# here, not skipped. It was the executable calibration-regression proof for
# SEN-2's degraded tier's 0-false-positive claim (the corpus this docstring
# cited -- VFEM_fort's real measurement -- is the same 88/93/94-count
# correction the coordinator's r6/r7 REVISE asked for; that correction is now
# moot, since the calibration text it would have corrected shipped only in
# this deleted class and in design.md, which this role does not own).
# `_sen2_evaluate` no longer exists.


if __name__ == "__main__":
    unittest.main()
