from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]

PERFORMANCE_ENGINEER_CONTRACTS = (
    "src.codex/skills/performance-engineer/SKILL.md",
    "src.claude/agents/performance-engineer.md",
)


class TestRemainingRolePrerequisites(unittest.TestCase):
    def _read(self, relative: str) -> str:
        return (REPO_ROOT / relative).read_text(encoding="utf-8")

    def test_performance_engineer_consumes_only_admitted_route_artifacts(self) -> None:
        required = (
            "Consume only the artifacts required by the admitted route.",
            "Do not require accepted Research or Design artifacts unless the admitted route requires them.",
        )
        retired = "Require accepted research and design artifacts unless the task is explicitly a performance investigation."

        for relative in PERFORMANCE_ENGINEER_CONTRACTS:
            text = self._read(relative)
            with self.subTest(relative=relative):
                for marker in required:
                    self.assertIn(marker, text)
                self.assertNotIn(retired, text)

    def test_agents_test_returns_findings_in_band_until_registry_write_is_authorized(
        self,
    ) -> None:
        text = self._read("src.claude/commands/agents-test.md")

        self.assertIn(
            "return an actionable proposed finding in-band for the root or lifecycle owner",
            text,
        )
        self.assertIn("explicit dispatcher authority", text)
        self.assertIn("allowed registry path", text)
        self.assertIn("Deduplicate against tracked defects", text)
        self.assertIn("Expected negative or TDD controls are not defects", text)
        self.assertIn("Unexpected transient or flaky regressions remain findings", text)
        self.assertNotIn(
            "the QA agent must create bug files in `work-items/bugs/`",
            text,
        )
