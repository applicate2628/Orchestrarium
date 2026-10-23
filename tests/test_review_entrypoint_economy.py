from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]

REVIEW_ENTRYPOINTS = (
    "src.codex/skills/review-changes/SKILL.md",
    "src.claude/commands/agents-review.md",
)


class TestReviewEntrypointEconomy(unittest.TestCase):
    def _read(self, relative: str) -> str:
        return (REPO_ROOT / relative).read_text(encoding="utf-8")

    def test_review_entrypoints_select_the_objective_reviewer_before_triggered_helpers(
        self,
    ) -> None:
        required = (
            "First identify the reviewer required by the review objective",
            "Add a factual or research helper only when required evidence is missing",
            "Add a Quality Assurance (QA) helper only when the objective needs test, regression, or fix-completeness evidence",
            "Add an Architecture Reviewer only when the objective is architectural or verified architecture or maintainability risk requires that gate",
            "research -> QA -> review",
        )
        retired = (
            "$analyst` -> QA lane -> reviewer lane",
            "Run `$analyst` first",
            "always run **Architecture reviewer**",
            "Always invoke `$architecture-reviewer`",
        )

        for relative in REVIEW_ENTRYPOINTS:
            text = self._read(relative)
            with self.subTest(relative=relative):
                for marker in required:
                    self.assertIn(marker, text)
                for marker in retired:
                    self.assertNotIn(marker, text)

    def test_review_entrypoints_explain_narrow_qa_architecture_and_research_scenarios(
        self,
    ) -> None:
        scenarios = (
            "Narrow QA-only objective:",
            "Architecture objective:",
            "Research needed:",
        )

        for relative in REVIEW_ENTRYPOINTS:
            text = self._read(relative)
            with self.subTest(relative=relative):
                for marker in scenarios:
                    self.assertIn(marker, text)
                self.assertIn("do not add Analyst or Architecture review", text)
                self.assertIn("the Architecture Reviewer is the objective reviewer", text)
                self.assertIn("admit an Analyst to collect those facts before the downstream QA or review verdict", text)

    def test_review_entrypoints_preserve_the_existing_anti_layering_trigger(self) -> None:
        marker = (
            "When the existing multi-fix anti-layering trigger applies, its Architecture Reviewer lane "
            "and distinct-engine audit remain mandatory"
        )
        for relative in REVIEW_ENTRYPOINTS:
            with self.subTest(relative=relative):
                self.assertIn(marker, self._read(relative))

    def test_authorized_thread_resolution_is_delegated_to_the_hosted_state_owner(
        self,
    ) -> None:
        required = (
            "Delegate authorized GitHub review-thread resolution to `$github-pr-review-bot`",
            "refresh the pull request's hosted `headRefOid`",
            "resolve only that exact authorized thread",
            "Thread resolution does not establish a clean bot result or `PASS`",
            "does not trigger a new review, start Continuous Integration (CI), or grant merge or publication authority",
        )
        retired = (
            "fix commit is on `HEAD`",
            "verify the bot's current verdict is `PASS`",
        )

        for relative in REVIEW_ENTRYPOINTS:
            text = self._read(relative)
            with self.subTest(relative=relative):
                for marker in required:
                    self.assertIn(marker, text)
                for marker in retired:
                    self.assertNotIn(marker, text)

    def test_review_entrypoints_remain_read_only_outside_the_authorized_owner_handoff(
        self,
    ) -> None:
        marker = (
            "The review entry point remains read-only; the delegated GitHub action is allowed only "
            "with explicit user authorization or existing standing authorization for that pull request"
        )
        for relative in REVIEW_ENTRYPOINTS:
            with self.subTest(relative=relative):
                self.assertIn(marker, self._read(relative))


if __name__ == "__main__":
    unittest.main()
