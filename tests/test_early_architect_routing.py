"""Contract tests for proportional early Architect routing."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPINE = ROOT / "shared/AGENTS.shared.md"
DETAIL = ROOT / "shared/references/spine/functional-first-delivery.md"
ARCHITECT_SKILLS = (
    ROOT / "src.codex/skills/architect/SKILL.md",
    ROOT / "src.claude/skills/architect/SKILL.md",
)
LEAD_SKILLS = (
    ROOT / "src.codex/skills/lead/SKILL.md",
    ROOT / "src.claude/skills/lead/SKILL.md",
)


class TestEarlyArchitectRouting(unittest.TestCase):
    def _read(self, path: Path) -> str:
        self.assertTrue(path.is_file(), f"missing routing owner: {path.relative_to(ROOT)}")
        return path.read_text(encoding="utf-8")

    def _assert_all_contain(self, paths: tuple[Path, ...], marker: str) -> None:
        for path in paths:
            with self.subTest(path=path.relative_to(ROOT), marker=marker):
                self.assertIn(marker, self._read(path))

    def test_current_second_consumer_needing_new_seam_routes_before_implementation(self) -> None:
        spine = self._read(SPINE)
        detail = self._read(DETAIL)
        claude_architect = self._read(ARCHITECT_SKILLS[1])

        self.assertIn(
            "Unsettled structure=>`$architect`; implementer cannot invent",
            spine,
        )
        self.assertIn("architecture before implementation", spine)
        self.assertIn(
            "accepted requirement or declared future direction/evidenced domain variability/current second consumer/verified external-contract evolution",
            spine,
        )
        self.assertIn(
            "A current second consumer that needs a new seam routes to `$architect` before implementation",
            detail,
        )
        self._assert_all_contain(
            LEAD_SKILLS,
            "Before `Implement`, apply the shared `Boundary` check",
        )
        self._assert_all_contain(
            LEAD_SKILLS,
            "the implementation handoff consumes the accepted owner, seam, and protected-surface decision instead of inventing architecture",
        )
        self._assert_all_contain(
            ARCHITECT_SKILLS,
            "A bounded early decision package contains: decision, owner, seam, protected surface, any material alternative, and falsifying probe",
        )
        self._assert_all_contain(
            ARCHITECT_SKILLS,
            "For a bounded early package, the decision, owner, seam, protected surface, material-alternative disposition, and falsifying probe are explicit",
        )
        self.assertNotIn(
            "Adopting this role inline approves nothing — the `architecture-reviewer` independent gate remains a separate dispatch regardless of invocation mode.",
            claude_architect,
        )
        self.assertIn(
            "Adopting this role inline approves nothing — when the architecture-reviewer gate is triggered, it remains a separate dispatch regardless of invocation mode.",
            claude_architect,
        )

    def test_restart_cancel_persist_with_unknown_owner_routes_to_architect(self) -> None:
        detail = self._read(DETAIL)

        self.assertIn(
            "Immediately before `Implement`, check whether accepted inputs leave any structural choice unresolved",
            detail,
        )
        self.assertIn(
            "New restart, cancellation, or persistence behavior with no accepted state/lifecycle owner routes to `$architect` before implementation",
            detail,
        )
        self.assertIn(
            "Architect makes the pre-implementation design decision; Architecture Reviewer verifies implementation afterward only when triggered",
            detail,
        )
        self._assert_all_contain(
            ARCHITECT_SKILLS,
            "accepted inputs and the exact unresolved structural choice",
        )
        self._assert_all_contain(
            ARCHITECT_SKILLS,
            "use the full design package and Design Panel or review loop only when their existing complexity triggers apply",
        )

    def test_known_local_fix_stays_quick_fix_without_weakening_existing_gates(self) -> None:
        spine = self._read(SPINE)
        detail = self._read(DETAIL)

        self.assertIn("local correction=no ceremony", spine)
        self.assertIn(
            "A fix inside a known function that preserves its accepted contract stays on `quick-fix`",
            detail,
        )
        self.assertIn(
            "Model/math/units only=>domain owner, not Architect",
            spine,
        )
        self.assertIn(
            "Domain-only uncertainty about the model, mathematics, or units routes to the existing domain owner",
            detail,
        )
        self._assert_all_contain(
            ARCHITECT_SKILLS + LEAD_SKILLS,
            "Domain-only model, mathematics, or units",
        )

        for marker in (
            "security-, performance-, or geometry-sensitive template requirements",
            "confidentiality/integrity/authentication/authorization/trust/injection/untrusted-execution/data-loss/corruption/irreversible/publication=>fail closed",
            "Human approval/leak mandatory",
        ):
            with self.subTest(spine_gate=marker):
                self.assertIn(marker, spine)
        for marker in (
            "Evidence-connected safety stop",
            "activate the existing risk owners",
            "Admit hardening separately only after `Functional PASS` and `Regression PASS`",
            "Human publication approval and the leak scan remain mandatory and unchanged",
        ):
            with self.subTest(detail_gate=marker):
                self.assertIn(marker, detail)


if __name__ == "__main__":
    unittest.main()
