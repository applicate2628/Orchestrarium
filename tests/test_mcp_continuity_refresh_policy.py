"""Regression fixtures for the stateful MCP freshness policy."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATHS = (
    ROOT / "scripts" / "universal-hooks" / "scripts" / "mcp_continuity_policy.py",
    ROOT / "src.codex" / "skills" / "lead" / "scripts" / "mcp_continuity_policy.py",
    ROOT / "src.claude" / "agents" / "scripts" / "mcp_continuity_policy.py",
)
REFERENCE_CONTRACTS = {
    ROOT / "shared" / "references" / "mcp-continuity.md": (
        "## Stateful and indexed freshness",
        "status/freshness probe",
        "sync, update, or reindex operation",
        "confirm freshness again, then repeat the",
        "stateless or live MCP does not need a refresh",
        "stale output is not presented as current",
        "CodeGraph this is `status -> sync -> fresh status -> repeat",
    ),
    ROOT / "shared" / "references" / "ru" / "mcp-continuity.md": (
        "## Свежесть stateful и индексных MCP",
        "проверку статуса/свежести",
        "синхронизацию, обновление или переиндексацию",
        "снова подтвердить свежесть и только затем повторить",
        "MCP без сохраняемого состояния или live MCP не требует refresh",
        "устаревший вывод не представляется как актуальный",
        "CodeGraph последовательность такая: `status -> sync -> fresh status -> repeat",
    ),
}


def load_policy(path: Path, index: int):
    spec = importlib.util.spec_from_file_location(f"mcp_continuity_policy_{index}", path)
    assert spec is not None and spec.loader is not None
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)
    return policy


class StatefulMcpRefreshPolicyTests(unittest.TestCase):
    def test_english_and_russian_references_carry_the_same_freshness_contract(self) -> None:
        for path, markers in REFERENCE_CONTRACTS.items():
            with self.subTest(reference=path.relative_to(ROOT).as_posix()):
                text = path.read_text(encoding="utf-8")
                for marker in markers:
                    self.assertIn(marker, text)
        russian_reference = (ROOT / "shared" / "references" / "ru" / "mcp-continuity.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("статический или live MCP", russian_reference)

    def test_codegraph_stale_sync_fresh_repeat_query_fixture(self) -> None:
        """An indexed server must prove freshness before reusing a query result."""
        required_order = (
            "CodeGraph `status -> sync -> fresh status -> repeat query`",
            "If refresh fails, report it explicitly",
            "do not present stale output as current",
        )
        for index, path in enumerate(POLICY_PATHS):
            with self.subTest(policy=path.relative_to(ROOT).as_posix()):
                context = load_policy(path, index).SESSION_START_CONTEXT
                cursor = -1
                for token in required_order:
                    cursor = context.find(token, cursor + 1)
                    self.assertNotEqual(cursor, -1, token)

    def test_stateless_or_live_mcp_fixture_does_not_require_refresh(self) -> None:
        for index, path in enumerate(POLICY_PATHS):
            with self.subTest(policy=path.relative_to(ROOT).as_posix()):
                policy = load_policy(path, index)
                self.assertIn("Stateless or live MCPs need no refresh.", policy.SESSION_START_CONTEXT)
                self.assertIn("stateless/live MCPs are exempt.", policy.TURN_ANCHOR_CONTEXT)
                self.assertIn("fresh recheck, then repeat the query", policy.TURN_ANCHOR_CONTEXT)


if __name__ == "__main__":
    unittest.main()
