"""Regression tests for SessionStart and UserPromptSubmit reminder payloads."""

from __future__ import annotations

import ast
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MCP_HOOK = REPO_ROOT / "scripts" / "universal-hooks" / "hooks" / "check-mcp-momentum.py"
MCP_POLICY = REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "mcp_continuity_policy.py"
MCP_REMINDER_PY = REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "mcp-usage-reminder.py"
TURN_ANCHOR_PY = REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "turn-anchor-reminder.py"


def run_hook(script: Path, envelope: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(envelope, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


class McpContinuityContract(unittest.TestCase):
    def test_codex_search_audit_source_is_retired(self) -> None:
        self.assertFalse(MCP_HOOK.exists(), "retired Codex audit source is still live")

    def test_one_policy_source_and_exactly_two_thin_python_consumers(self) -> None:
        self.assertTrue(MCP_POLICY.is_file(), "missing canonical MCP continuity policy")
        canon_root = REPO_ROOT / "scripts" / "universal-hooks"
        consumers: set[Path] = set()
        for candidate in (*canon_root.glob("scripts/*.py"), *canon_root.glob("hooks/*.py")):
            tree = ast.parse(candidate.read_text(encoding="utf-8"))
            if any(
                isinstance(node, ast.ImportFrom)
                and node.module == "mcp_continuity_policy"
                for node in ast.walk(tree)
            ):
                consumers.add(candidate)
        self.assertEqual(consumers, {MCP_REMINDER_PY, TURN_ANCHOR_PY})

        forbidden_restatements = (
            "[MCP / tools reminder",
            "[mcp-momentum AUDIT]",
            "CODE_INTEL_HINTS",
            "CODE_PATTERN_RE",
            "SHELL_TREE_SEARCH_RE",
            '"work-items/"',
            '".reports/"',
            '".plans/"',
            '".scratch/"',
        )
        for consumer in consumers:
            text = consumer.read_text(encoding="utf-8")
            with self.subTest(consumer=consumer.name):
                for fragment in forbidden_restatements:
                    self.assertNotIn(fragment, text)

    def test_mcp_usage_reminder_matches_policy_owned_text_and_shape(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "mcp_continuity_policy_session_start_test", MCP_POLICY
        )
        assert spec is not None and spec.loader is not None
        policy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(policy)
        for source in ("startup", "compact"):
            with self.subTest(source=source):
                python_result = run_hook(
                    MCP_REMINDER_PY, {"hookEventName": "SessionStart", "source": source}
                )
                self.assertEqual(python_result.returncode, 0, python_result.stderr)
                self.assertEqual(python_result.stderr, "")
                payload = json.loads(python_result.stdout)
                self.assertEqual(set(payload), {"hookSpecificOutput"})
                output = payload["hookSpecificOutput"]
                self.assertEqual(set(output), {"hookEventName", "additionalContext"})
                self.assertEqual(output["hookEventName"], "SessionStart")
                self.assertEqual(output["additionalContext"], policy.SESSION_START_CONTEXT)
                for marker in (
                    "discover connected MCP/tools at runtime",
                    "confirm fresh",
                    "Use another path only if refresh fails",
                ):
                    self.assertIn(marker, output["additionalContext"])


class TestTurnAnchorEmitsValidContext(unittest.TestCase):
    """The hook's whole job is to emit a UserPromptSubmit additionalContext payload every
    turn. If the JSON is malformed the harness drops it silently, so the payload shape is
    the contract."""

    def test_turn_anchor_uses_policy_owned_continuation_context_without_tool_choice(self) -> None:
        self.assertTrue(MCP_POLICY.is_file(), f"missing {MCP_POLICY}")
        spec = importlib.util.spec_from_file_location(
            "mcp_continuity_policy_turn_anchor_test", MCP_POLICY
        )
        assert spec is not None and spec.loader is not None
        policy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(policy)
        result = subprocess.run(
            [sys.executable, str(TURN_ANCHOR_PY)],
            input="",
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(context, policy.TURN_ANCHOR_CONTEXT)
        for marker in (
            "Root Lead",
            "Under the current default",
            "provider and leaf agents",
            "do not spawn or recursively launch wrappers",
            "mandatory gates",
        ):
            self.assertIn(marker, context)
        for duplicate_tool_choice in (
            "discover fitting runtime MCP/tools",
            "status/freshness",
            "sync/update/reindex",
            "reported project/index identity",
            "Use fallback only if refresh fails",
        ):
            self.assertNotIn(duplicate_tool_choice, context)

    def test_python_emits_wellformed_userpromptsubmit_context(self) -> None:
        result = subprocess.run(
            [sys.executable, str(TURN_ANCHOR_PY)],
            input="", capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, "must fail open / exit 0")
        payload = json.loads(result.stdout)
        out = payload["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "UserPromptSubmit")
        self.assertIn("Root Lead", out["additionalContext"])
        self.assertIn("provider and leaf agents", out["additionalContext"])
        self.assertIn("do not spawn or recursively launch wrappers", out["additionalContext"])

    def test_root_pre_final_decision_covers_ready_incident_and_stop_exceptions(self) -> None:
        result = subprocess.run(
            [sys.executable, str(TURN_ANCHOR_PY)],
            input="", capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        scenarios = {
            "resume after compaction or a side question": (
                "resume the current primary task after compaction or a side question",
                "Side questions, status, and clarifications are commentary; then resume",
            ),
            "terminal conditions remain exact": (
                "Stop only when it is complete, the user pauses, cancels, or stops it",
                "every remaining authorized action is concretely blocked",
            ),
            "one block does not freeze independent work": (
                "pauses only dependent work",
                "run useful independent ready work now",
            ),
            "root-only useful delegation": (
                "Delegate useful ready work by task to the matching specialist",
                "Root owns dispatch",
                "provider and leaf agents",
                "do not spawn or recursively launch wrappers",
            ),
            "scoped lanes and gates": (
                "Give each lane only needed tools and context",
                "keep mandatory gates",
            ),
            "cleanup preserves user state": (
                "settle every owned process/resource",
                "remove temporary or dead alternatives",
                "preserve pre-existing user state",
                "ambiguous ownership as a destructive-action blocker",
            ),
            "standalone questions remain terminal": (
                "A standalone question with no active task may end normally",
            ),
        }
        for scenario, fragments in scenarios.items():
            with self.subTest(scenario=scenario):
                for fragment in fragments:
                    self.assertIn(fragment, context)

    def test_policy_contexts_omit_repeated_manuals_but_keep_required_checks(self) -> None:
        spec = importlib.util.spec_from_file_location("compact_mcp_policy_test", MCP_POLICY)
        assert spec is not None and spec.loader is not None
        policy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(policy)
        combined = policy.SESSION_START_CONTEXT + "\n" + policy.TURN_ANCHOR_CONTEXT
        for removed_manual in (
            "Non-normative interface example only",
            "Non-normative workflow example",
            "Graphify follows",
            "CodeGraph follows",
            "because a once-per-session reminder is overwritten",
        ):
            self.assertNotIn(removed_manual, combined)
        for required in (
            "MCP/tools",
            "status/freshness",
            "sync/update/reindex",
            "mandatory gates",
            "preserve pre-existing user state",
        ):
            self.assertIn(required, combined)

    def test_missing_policy_dependency_fails_open(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            isolated_hook = Path(td) / TURN_ANCHOR_PY.name
            shutil.copyfile(TURN_ANCHOR_PY, isolated_hook)
            result = subprocess.run(
                [sys.executable, str(isolated_hook)],
                input="",
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_turn_anchor_never_exits_two(self) -> None:
        for stdin_text in ("", "not json", "x" * 1_000_000):
            with self.subTest(size=len(stdin_text)):
                result = subprocess.run(
                    [sys.executable, str(TURN_ANCHOR_PY)],
                    input=stdin_text,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotEqual(result.returncode, 2)
                self.assertEqual(result.stderr, "")
                payload = json.loads(result.stdout)
                self.assertEqual(
                    payload["hookSpecificOutput"]["hookEventName"],
                    "UserPromptSubmit",
                )
                result.stdout.encode("ascii")

if __name__ == "__main__":
    unittest.main()
