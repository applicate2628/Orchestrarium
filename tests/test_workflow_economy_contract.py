"""Regression contract for the evidence-triggered workflow economy policy."""

from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SPINE = "shared/AGENTS.shared.md"
METHODOLOGY = "shared/references/subagent-operating-model.md"
PROJECTIONS = (
    "src.codex/skills/lead/operating-model.md",
    "src.claude/agents/contracts/operating-model.md",
    "src.codex/skills/review-loop/SKILL.md",
    "src.claude/agents/contracts/review-loop.md",
    "src.codex/skills/external-brigade/SKILL.md",
    "src.claude/commands/agents-external-brigade.md",
    "src.codex/skills/lead/subagent-contracts.md",
    "src.claude/agents/contracts/subagent-contracts.md",
)

DEAD_CODE_DISPOSITION_FIELD = "Dead/superseded code disposition:"
DEAD_CODE_DISPOSITION_REQUIREMENT = "When a change supersedes a mechanism, `none` is invalid."
DEAD_CODE_DISPOSITION_ECHO = "Dead/superseded code disposition result"
DEAD_CODE_DISPOSITION_QA_GATE = "cannot return `PASS` until it verifies the disposition field against the diff"

EXTERNAL_PROMPT_CONSUMERS = (
    "src.codex/skills/lead/external-dispatch.md",
    "src.codex/skills/consultant/SKILL.md",
    "src.codex/skills/external-worker/SKILL.md",
    "src.codex/skills/external-reviewer/SKILL.md",
    "src.codex/skills/review-loop/SKILL.md",
    "src.codex/skills/design-panel/SKILL.md",
    "src.claude/CLAUDE.md",
    "src.claude/agents/contracts/external-dispatch.md",
    "src.claude/agents/consultant.md",
    "src.claude/agents/external-worker.md",
    "src.claude/agents/external-reviewer.md",
    "src.claude/agents/contracts/review-loop.md",
    "src.claude/agents/contracts/design-panel.md",
    "src.claude/commands/agents-review-loop.md",
    "src.claude/commands/agents-design-panel.md",
    "docs/external-worker-design.md",
    "docs/agents-mode-reference.md",
    "shared/references/spine/verification-and-decision-discipline.md",
    "shared/references/review-loop-methodology.md",
)
RETIRED_PROMPT_RELATIONS = (
    "ships no primary-run prompt wrappers",
    "transport-neutral probe",
    "sibling `.out` / `.err` capture",
    "captured output file",
    "two commands around the run",
    "gate parsed from the artifact's final `GATE:` line",
    "the inline chain the fallback",
    "invoke-codex-prompt.ps1",
    "invoke-claude-prompt.ps1",
    "invoke-claude-api.ps1",
    "prompt / .out / .err paths",
    "until the schema grows a dedicated path field",
    "reviewer's `.out` prose",
)
PROVENANCE_PROVIDER_TEMPLATES = (
    "src.codex/skills/lead/external-dispatch.md",
    "src.codex/skills/consultant/SKILL.md",
    "src.claude/agents/contracts/external-dispatch.md",
)


class TestWorkflowEconomyContract(unittest.TestCase):
    def _read(self, relative: str) -> str:
        path = REPO_ROOT / relative
        self.assertTrue(path.is_file(), f"workflow-economy owner missing: {relative}")
        return path.read_text(encoding="utf-8")

    def test_canonical_rule_keeps_evidence_gates_and_minimizes_ceremony(self) -> None:
        spine = self._read(SPINE)
        for required in (
            "**Workflow economy (binding):**",
            "Optional review is evidence-triggered only",
            "`design-decision`",
            "one final QA package with only the relevant mandatory risk owners",
            "Re-review only the exact open finding and its changed delta",
            "new defect class or a material upstream revision",
            "Consultant and `$external-brigade` are off by default",
            "Kimi/Grok remain policy classifiers/examples, unavailable and disabled in 1.x, and never selectable, execution, or provenance providers",
            "quick-fix has no pre-implementation review ceremony",
            "one canonical artifact",
            "concise root ledger",
            "progress-only artifact",
            "progress-only `REVISE`",
            "human publication and leak-check gate",
            "security-, performance-, or geometry-sensitive template",
        ):
            with self.subTest(required=required):
                self.assertIn(required, spine)

    def test_provider_projections_point_to_the_single_shared_rule(self) -> None:
        for projection in PROJECTIONS:
            with self.subTest(projection=projection):
                self.assertIn(
                    "Workflow economy projection",
                    self._read(projection),
                    "provider surface must project the shared rule without a second policy owner",
                )

    def test_methodology_defers_to_the_shared_rule(self) -> None:
        methodology = self._read(METHODOLOGY)
        self.assertIn("Workflow economy is owned by `shared/AGENTS.shared.md`", methodology)

    def test_dead_code_disposition_markers_fail_closed_if_removed(self) -> None:
        """Catches a handoff or QA surface that silently drops dead-code disposition."""

        required_markers = {
            "shared/AGENTS.shared.md": (
                "**Directory-level entity separation:**",
                "**Trash hygiene and archival:**",
            ),
            "shared/external-prompt-governance.md": (
                "**Directory-level entity separation:**",
                "**Trash hygiene and archival:**",
            ),
            "src.codex/skills/lead/subagent-contracts.md": (
                DEAD_CODE_DISPOSITION_FIELD,
                DEAD_CODE_DISPOSITION_REQUIREMENT,
                DEAD_CODE_DISPOSITION_ECHO,
            ),
            "src.claude/agents/contracts/subagent-contracts.md": (
                DEAD_CODE_DISPOSITION_FIELD,
                DEAD_CODE_DISPOSITION_REQUIREMENT,
                DEAD_CODE_DISPOSITION_ECHO,
            ),
            "src.codex/skills/qa-engineer/SKILL.md": (DEAD_CODE_DISPOSITION_QA_GATE,),
            "src.claude/agents/qa-engineer.md": (DEAD_CODE_DISPOSITION_QA_GATE,),
            "src.codex/skills/lead/scripts/validate-skill-pack.py": (
                DEAD_CODE_DISPOSITION_FIELD,
                DEAD_CODE_DISPOSITION_QA_GATE,
            ),
            "src.claude/agents/scripts/validate-skill-pack.py": (
                DEAD_CODE_DISPOSITION_FIELD,
                DEAD_CODE_DISPOSITION_QA_GATE,
            ),
        }
        for relative, markers in required_markers.items():
            text = self._read(relative)
            for marker in markers:
                with self.subTest(relative=relative, marker=marker):
                    self.assertIn(marker, text)

    def test_external_prompt_consumers_retain_only_the_wrapper_contract(self) -> None:
        """A consumer cannot revive a raw route, sidecar capture, or local V2 parser."""

        for relative in EXTERNAL_PROMPT_CONSUMERS:
            text = self._read(relative)
            with self.subTest(relative=relative, relation="wrapper boundary"):
                self.assertIn("approved thin wrapper", text)
            for required in (
                "strict V2 parser",
                "full external-nonauthorizing tuple",
                "untrusted/potentially-sensitive resultText",
            ):
                with self.subTest(relative=relative, required=required):
                    self.assertIn(required, text)
            for retired in RETIRED_PROMPT_RELATIONS:
                with self.subTest(relative=relative, retired=retired):
                    self.assertNotIn(retired, text)

    def test_russian_review_loop_mirror_keeps_wrapper_results_separate_from_the_ledger(self) -> None:
        text = self._read("shared/references/ru/review-loop-methodology.md")
        self.assertIn("`resultText`", text)
        self.assertNotIn("Проза `.out` ревьюера", text)
        self.assertNotIn("обёртка `--ledger`", text)

    def test_provenance_templates_exclude_unavailable_policy_classifiers(self) -> None:
        for relative in PROVENANCE_PROVIDER_TEMPLATES:
            text = self._read(relative)
            with self.subTest(relative=relative, field="requested provider"):
                self.assertIn(
                    "<internal | codex | claude | gemini | qwen>",
                    text,
                )
            for forbidden in (
                "<internal | codex | claude | gemini | qwen | kimi | grok>",
                "Kimi CLI",
                "Grok CLI",
                "external CLI (Kimi",
                "external CLI (Grok",
            ):
                with self.subTest(relative=relative, forbidden=forbidden):
                    self.assertNotIn(forbidden, text)
            with self.subTest(relative=relative, boundary="disabled non-provenance"):
                self.assertIn("never select, resolve, execute, or record either as a provenance provider", text)

    def test_substantive_prompt_policy_allows_only_the_fixed_synthetic_smoke_exception(self) -> None:
        reference = self._read("docs/agents-mode-reference.md")
        principles = self._read("shared/references/spine/delegation-principles.md")
        self.assertIn("fixed synthetic non-substantive smoke token", reference)
        self.assertNotIn("documented provider limitations", reference)
        self.assertIn("approved prompt wrapper or fail/reroute", principles)
        self.assertNotIn("An inline fallback", principles)


if __name__ == "__main__":
    unittest.main()
