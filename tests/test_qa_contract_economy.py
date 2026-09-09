from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]

QA_AND_REVIEWER_CONTRACTS = (
    "src.codex/skills/qa-engineer/SKILL.md",
    "src.claude/agents/qa-engineer.md",
    "src.codex/skills/security-reviewer/SKILL.md",
    "src.claude/agents/security-reviewer.md",
    "src.codex/skills/performance-reviewer/SKILL.md",
    "src.claude/agents/performance-reviewer.md",
    "src.codex/skills/ux-reviewer/SKILL.md",
    "src.claude/agents/ux-reviewer.md",
    "src.codex/skills/accessibility-reviewer/SKILL.md",
    "src.claude/agents/accessibility-reviewer.md",
)

REGISTRY_WRITER_CONTRACTS = (
    "src.codex/skills/analyst/SKILL.md",
    "src.claude/skills/analyst/SKILL.md",
    "src.codex/skills/qa-engineer/SKILL.md",
    "src.claude/agents/qa-engineer.md",
    "src.codex/skills/security-reviewer/SKILL.md",
    "src.claude/agents/security-reviewer.md",
    "src.codex/skills/performance-reviewer/SKILL.md",
    "src.claude/agents/performance-reviewer.md",
    "src.codex/skills/accessibility-reviewer/SKILL.md",
    "src.claude/agents/accessibility-reviewer.md",
)

DESIGN_ROUTING_CONTRACTS = {
    "src.codex/skills/security-reviewer/SKILL.md": ("`security-engineer`",),
    "src.claude/agents/security-reviewer.md": ("`security-engineer`",),
    "src.codex/skills/performance-reviewer/SKILL.md": ("`performance-engineer`",),
    "src.claude/agents/performance-reviewer.md": ("`performance-engineer`",),
    "src.codex/skills/ux-reviewer/SKILL.md": ("`$ux-designer`", "`$architect`"),
    "src.claude/agents/ux-reviewer.md": ("`$ux-designer`", "`$architect`"),
    "src.codex/skills/accessibility-reviewer/SKILL.md": (
        "`$ux-designer`",
        "`$architect`",
    ),
    "src.claude/agents/accessibility-reviewer.md": (
        "`$ux-designer`",
        "`$architect`",
    ),
}

PERFORMANCE_REVIEWER_CONTRACTS = (
    "src.codex/skills/performance-reviewer/SKILL.md",
    "src.claude/agents/performance-reviewer.md",
)


class TestQAContractEconomy(unittest.TestCase):
    def _read(self, relative: str) -> str:
        return (REPO_ROOT / relative).read_text(encoding="utf-8")

    def test_missing_mandatory_integration_check_blocks_pass_but_optional_check_is_residual(
        self,
    ) -> None:
        required = (
            "accepted mandatory gate criterion",
            "prevents `PASS`",
            "Continue every accepted mandatory check that remains runnable",
            "optional non-gate check",
            "residual risk",
            "does not add or promote any check",
        )

        for relative in QA_AND_REVIEWER_CONTRACTS:
            text = self._read(relative)
            with self.subTest(relative=relative):
                for marker in required:
                    self.assertIn(marker, text)

    def test_read_only_finding_is_returned_in_band_until_registry_write_is_authorized(
        self,
    ) -> None:
        required = (
            "proposed registry record",
            "in-band in the returned artifact for the root or lifecycle owner",
            "explicitly grants registry-write authority",
            "sandbox permits that path",
            "narrow canonical-artifact exception",
            "does not otherwise broaden this role's write posture",
        )
        retired = (
            "Always write bug files before returning",
            "When the gate decision is `REVISE` or `BLOCKED`, create or update the issue",
            "On `REVISE` or `BLOCKED`, file each finding",
        )

        for relative in REGISTRY_WRITER_CONTRACTS:
            text = self._read(relative)
            with self.subTest(relative=relative):
                for marker in required:
                    self.assertIn(marker, text)
                for marker in retired:
                    self.assertNotIn(marker, text)

    def test_design_decision_label_routes_to_owner_without_forcing_a_review_loop(
        self,
    ) -> None:
        required = (
            "architecture-reviewer's `Simple exact-delta route`, `Mandatory review-loop triggers`, and `Insufficient triggers`",
            "tag alone does not trigger the loop",
            "genuine complexity or ambiguity",
            "materially competing owner/seam solutions",
            "repeated review/fix failure",
            "user explicitly requests the loop",
        )

        for relative, owner_markers in DESIGN_ROUTING_CONTRACTS.items():
            text = self._read(relative)
            with self.subTest(relative=relative):
                for marker in (*required, *owner_markers):
                    self.assertIn(marker, text)
                self.assertNotIn(
                    "requires a separate `/agents-review-loop` fix-design pass",
                    text,
                )

    def test_performance_review_accepts_p99_with_repetitions_and_iqr_but_not_mean_only(
        self,
    ) -> None:
        required = (
            "accepted metric and percentile",
            "p99",
            "does not create an additional p95 requirement",
            "repetition count",
            "warm-up",
            "steady state",
            "dispersion",
            "interquartile range (IQR)",
            "environment",
            "A mean alone cannot pass a latency budget",
        )

        for relative in PERFORMANCE_REVIEWER_CONTRACTS:
            text = self._read(relative)
            with self.subTest(relative=relative):
                for marker in required:
                    self.assertIn(marker, text)
                self.assertNotIn("p50 and p95 percentiles at minimum", text)


if __name__ == "__main__":
    unittest.main()
