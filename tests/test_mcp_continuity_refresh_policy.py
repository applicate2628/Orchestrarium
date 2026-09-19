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
        "reported project/index identity matches the selected root",
        "known omitted coverage is reported",
        "own supported entrypoint, help, and version",
        "not a per-call version check",
        "explicitly non-normative workflow example",
        "CodeGraph uses",
        "this name never selects a tool",
    ),
    ROOT / "shared" / "references" / "ru" / "mcp-continuity.md": (
        "## Свежесть stateful и индексных MCP",
        "проверку статуса/свежести",
        "синхронизацию, обновление или переиндексацию",
        "снова подтвердить свежесть и только затем повторить",
        "MCP без сохраняемого состояния или live MCP не требует refresh",
        "устаревший вывод не представляется как актуальный",
        "сообщаемая инструментом идентичность проекта/индекса совпадает с выбранным корнем",
        "сообщается об известном пропущенном покрытии",
        "собственные поддерживаемые entrypoint, help и version",
        "не является проверкой version при каждом вызове",
        "ненормативный пример workflow",
        "для CodeGraph это",
        "это имя никогда не выбирает инструмент",
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

    def test_stateful_or_indexed_mcp_fixture_requires_freshness_before_repeat(self) -> None:
        """Stateful or indexed evidence must refresh before its query is reused."""
        required_session_context = (
            "Before using stateful or indexed repository evidence",
            "check status/freshness; when stale or pending, sync/update/reindex, confirm fresh, and repeat the intended query.",
            "Never present stale evidence.",
            "reported project/index identity matches the selected root",
            "Report known omitted coverage.",
            "When instructions conflict with an installed tool, inspect its own supported entrypoint/help/version; do not invent or reimplement its pipeline.",
            "This is not a per-call version check.",
            "Use another path only if refresh fails, the tool is unavailable, the user forbids it, or an explicit resource bound is exceeded; state why.",
            "Stateless or live tools need no refresh.",
        )
        required_turn_context = (
            "After repository, project, branch, worktree, or indexed-input changes, check status/freshness, sync/update/reindex stale state, confirm fresh, and retry.",
            "reported project/index identity matches the selected root",
            "report known omitted coverage",
            "inspect its own supported entrypoint/help/version",
            "not a per-call version check",
            "Use fallback only if refresh fails, the tool is unavailable, the user forbids it, or an explicit resource bound is exceeded; state why and never use stale evidence.",
        )
        canonical_contexts = None
        for index, path in enumerate(POLICY_PATHS):
            with self.subTest(policy=path.relative_to(ROOT).as_posix()):
                policy = load_policy(path, index)
                contexts = (policy.SESSION_START_CONTEXT, policy.TURN_ANCHOR_CONTEXT)
                if canonical_contexts is None:
                    canonical_contexts = contexts
                else:
                    self.assertEqual(contexts, canonical_contexts)
                for marker in required_session_context:
                    self.assertIn(marker, policy.SESSION_START_CONTEXT)
                for marker in required_turn_context:
                    self.assertIn(marker, policy.TURN_ANCHOR_CONTEXT)


if __name__ == "__main__":
    unittest.main()
