"""Focused guards for the active-work-item session persistence contract."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "shared" / "AGENTS.shared.md"
CORE_PROJECTIONS = (
    ROOT / "src.codex" / "skills" / "lead" / "operating-model.md",
    ROOT / "src.codex" / "skills" / "lead" / "subagent-contracts.md",
    ROOT / "src.claude" / "agents" / "contracts" / "operating-model.md",
    ROOT / "src.claude" / "agents" / "contracts" / "subagent-contracts.md",
)
VAK_PROJECTIONS = (
    ROOT / "src.codex" / "skills" / "vak-dissertation-review" / "SKILL.md",
    ROOT / "src.claude" / "skills" / "vak-dissertation-review" / "SKILL.md",
)
CURRENT_TRUTH_PROJECTIONS = (
    SHARED,
    *CORE_PROJECTIONS,
    ROOT / "docs" / "new-session-guide.md",
    ROOT / "references-claude" / "repository-task-memory.md",
    ROOT / "references-claude" / "ru" / "repository-task-memory.md",
    ROOT / "src.claude" / "agents" / "knowledge-archivist.md",
    ROOT / "src.claude" / "commands" / "agents-bugfix.md",
    ROOT / "src.claude" / "commands" / "agents-design.md",
    ROOT / "src.claude" / "commands" / "agents-implement.md",
    ROOT / "src.claude" / "commands" / "agents-perf.md",
    ROOT / "src.claude" / "commands" / "agents-refactor.md",
    ROOT / "src.claude" / "commands" / "agents-research.md",
    ROOT / "src.claude" / "commands" / "agents-review.md",
    ROOT / "src.claude" / "commands" / "agents-second-opinion.md",
    ROOT / "src.claude" / "commands" / "agents-security.md",
    ROOT / "src.claude" / "commands" / "agents-test.md",
    ROOT / "src.claude" / "skills" / "lead" / "SKILL.md",
    ROOT / "src.codex" / "skills" / "knowledge-archivist" / "SKILL.md",
    ROOT / "src.codex" / "skills" / "lead" / "SKILL.md",
    ROOT / "src.codex" / "skills" / "review-changes" / "SKILL.md",
    ROOT / "src.codex" / "skills" / "second-opinion" / "SKILL.md",
    ROOT / "references-codex" / "operating-model-diagram.md",
    ROOT / "references-claude" / "operating-model-diagram.md",
    ROOT / "references-codex" / "ru" / "operating-model-diagram.md",
    ROOT / "references-claude" / "ru" / "operating-model-diagram.md",
    *VAK_PROJECTIONS,
)
STALE_MANDATORY_CLAIMS = (
    "MUST log completed results/routing decisions/reviews in `.reports/YYYY-MM/`",
    "Session logging is mandatory for every participant",
    "Every role — the orchestrator (the main conversation, as Lead) or a specialist — MUST write a session log",
    "Every subagent MUST write a session log",
    "Every completed chain persists artifacts: canonical docs in `work-items/`, session logs in `.reports/`, plan logs in `.plans/`.",
    "Completed-artifact and session-log persistence follows completed work",
    "post-verification `.reports/` summary may record the completed route",
    "Save final report to `work-items/active/<slug>/implementation-report.md` and log to `.reports/`.",
    "write a\n   session log.",
    "Always log to `.reports/YYYY-MM/",
    "Log plan to `.plans/YYYY-MM/",
)


class SessionPersistenceContractTest(unittest.TestCase):
    def test_shared_owner_states_the_full_conditional_contract(self) -> None:
        text = SHARED.read_text(encoding="utf-8")
        for required in (
            "An active work-item is current-task `work-items/active/<slug>/`; a repository `work-items/` directory alone is not.",
            "specialists write only canonical artifacts",
            "root records concise lane result/provenance in `agent-runs.jsonl`",
            "Trivial chat/work with no recovery or preservation value writes nothing.",
            "meaningful standalone result MAY use one `.reports/YYYY-MM/` summary",
            "explicitly requested standalone plan MAY use one `.plans/YYYY-MM/` snapshot",
            "Work needing stages, recovery, or continuation is admitted as a work-item.",
            "active ledger/artifact or one standalone summary",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

    def test_codex_and_claude_core_projections_keep_active_work_item_single_writer_rule(self) -> None:
        for path in CORE_PROJECTIONS:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("work-items/active/<slug>/", text)
                self.assertIn("agent-runs.jsonl", text)
                self.assertTrue(
                    "no `.reports/` or `.plans/` duplicate" in text
                    or "do not create `.reports/` or `.plans/` duplicates" in text
                )

    def test_exact_stale_mandatory_per_lane_claims_are_absent(self) -> None:
        for path in CURRENT_TRUTH_PROJECTIONS:
            text = path.read_text(encoding="utf-8")
            for stale in STALE_MANDATORY_CLAIMS:
                with self.subTest(path=path, stale=stale):
                    self.assertNotIn(stale, text)

    def test_claude_artifact_and_registry_table_is_truthful_and_two_columns(self) -> None:
        path = ROOT / "src.claude" / "agents" / "contracts" / "operating-model.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn(
            "The registry rows name their own canonical cross-item registries and are not active-item artifact paths.",
            text,
        )
        lines = text.splitlines()
        start = lines.index("| Artifact or registry entry | Canonical path |")
        rows = []
        for line in lines[start:]:
            if rows and not line.startswith("|"):
                break
            if line.startswith("|"):
                rows.append(line)
        self.assertGreater(len(rows), 2)
        self.assertTrue(all(row.count("|") == 3 for row in rows), rows)
        self.assertNotIn("| — |", "\n".join(rows))

    def test_claude_implement_completion_uses_active_artifact_and_root_ledger(self) -> None:
        path = ROOT / "src.claude" / "commands" / "agents-implement.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("work-items/active/<slug>/implementation-report.md", text)
        self.assertIn("root records the concise lane result/provenance in `agent-runs.jsonl`", text)
        self.assertIn("Do not duplicate either in `.reports/` or `.plans/`.", text)

    def test_vak_live_pack_projection_uses_conditional_persistence(self) -> None:
        for path in VAK_PROJECTIONS:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("current task has `work-items/active/<slug>/`", text)
                self.assertIn("persist only the\n   canonical VAK artifact", text)
                self.assertIn("return concise result/provenance for the root\n   `agent-runs.jsonl`", text)
                self.assertIn("meaningful standalone VAK result MAY use one `.reports/YYYY-MM/` summary", text)
                self.assertIn("do not create a\n   `.plans/` duplicate", text)
                self.assertNotIn("write a\n   session log", text)


if __name__ == "__main__":
    unittest.main()
