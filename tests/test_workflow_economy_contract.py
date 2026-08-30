"""Regression contract for the evidence-triggered workflow economy policy."""

from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SPINE = "shared/AGENTS.shared.md"
FUNCTIONAL_FIRST_EXTRACT = "shared/references/spine/functional-first-delivery.md"
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

    def test_role_index_and_reference_provenance_remain_truthful(self) -> None:
        spine = self._read(SPINE)
        for heading in (
            "- Roadmap and orchestration:",
            "- Research, design, planning, and specialist constraints:",
            "- Implementation:",
            "- Review and verification:",
        ):
            with self.subTest(heading=heading):
                self.assertEqual(spine.count(heading), 1)
        self.assertNotIn("\nRoadmap:", spine)
        self.assertIn("Source-only/maintainer-only, NOT installed: `shared/references/`", spine)
        self.assertIn("these rules are self-sufficient", spine)

    def test_canonical_rule_keeps_evidence_gates_and_minimizes_ceremony(self) -> None:
        spine = self._read(SPINE)
        for required in (
            "**Workflow economy (binding):**",
            "Optional review needs evidence",
            "`design-decision`",
            "one final QA package of triggered mandatory risk owners",
            "Re-review only open finding/changed delta",
            "new defect class/material upstream revision",
            "Consultant and `$external-brigade` default off",
            "Kimi: explicit read-only broad research/review",
            "Grok is unavailable in 1.x",
            "Quick-fix: no pre-implementation review ceremony",
            "one canonical artifact",
            "root: one concise ledger entry",
            "progress-only artifact",
            "progress-only artifact/`REVISE`",
            "human publication/leak-check gates",
            "security-, performance-, or geometry-sensitive template",
        ):
            with self.subTest(required=required):
                self.assertIn(required, spine)

    def test_functional_first_policy_keeps_the_approved_boundaries(self) -> None:
        spine = self._read(SPINE)
        extract = self._read(FUNCTIONAL_FIRST_EXTRACT)
        for required in (
            "**Functional-first delivery (binding).**",
            "shared/references/spine/functional-first-delivery.md",
            ": detail; spine wins",
            "criteria/contracts; scenario/env/steps; success/failure; safety/cleanup; evidence/owner; source/config/env",
            "actual run records source/config/env; mock/unit≠`Functional PASS`; scope=>new ID/gates; implementation cannot revise",
            "actual run records source/config/env; mock/unit≠`Functional PASS`",
            "never expands/freezes unverified/workaround output",
            "accepted requirement/current second consumer/verified external-contract evolution)=>simplest one-owner stable/local seam",
            "architecture before implementation",
            "Needed designs/lifecycle; urgency no bypass; local correction=no ceremony",
            "confidentiality/integrity/authentication/authorization/trust/injection/untrusted-execution/data-loss/corruption/irreversible/publication=>fail closed",
            "containment/remediation only; no publication authority",
            "smallest deterministic guards+repo-required/adjacent checks+PAO",
            "Hardening=work beyond functional contract",
            "mandatory nonblocking backlog/no implementation",
            "A security-shaped label/finding does not by itself expand scope",
            "trigger-rule/evidence/invocation table",
            "ambiguity=>reviewer; else nonveto; no implementer/$lead waiver",
            "new=hypothesis+material difference+falsifier+`$lead` acceptance",
            "supersession/relabel/split/merge/derived never reset lineage/budget/gate-backlog",
            "every gate entry/exit=>frozen PAO evidence; ambiguity=>scope/veto",
            "**Publication safety unchanged.**",
            ">=2 base-model families",
            "runtime IDs; unavailable=`BLOCKED`",
            "Independently challenge premises; name accepted/rejected and better alternative+tradeoff+`Would-flip-if`",
            "sole=PAO/veto/evidence, never majority/deference",
            "delta=>members re-review",
            "optional alternatives=>backlog/no reround",
        ):
            with self.subTest(anchor=required):
                self.assertIn(required, spine)
        for required in (
            "freeze a Primary Acceptance Oracle (PAO) specification",
            "every admitted acceptance criterion and external contract",
            "exact target scenario and environment",
            "invocation and steps",
            "observable success and required failure semantics",
            "safety preconditions, cleanup, evidence markers, owner",
            "method that identifies the evaluated source, configuration, and environment snapshot",
            "actual source, configuration, and environment snapshot",
            "Mock or unit evidence cannot earn `Functional PASS`",
            "PAO specification or admitted functional scope revision revises the PAO ID",
            "invalidates the affected gates",
            "implementation alone never revises the PAO",
            "Functional-first boundary; not code-first",
            "Functional correctness and a quality architecture foundation are co-primary delivery priorities",
            "required architecture precedes implementation rather than becoming later hardening",
            "Until `Functional PASS`",
            "diagnostics, tests, architecture/design, and changes causally linked to the PAO",
            "shared or external contract, ownership boundary or stable seam, state or lifecycle owner, public API or schema",
            "proportionate architecture artifact and evidence-triggered design gate are part of functional scope",
            "accepted requirement, a current second consumer, or verified external-contract evolution",
            "simplest one-owner contract and stable extension seam",
            "if no next extension is evidenced, do not optimize for one or implement hypothetical variants",
            "minimizing total lifecycle cost across implementation, verification, rollout or rollback, coupling, and blast radius",
            "Urgency, quick delivery, or the hardening boundary never authorizes skipping the required foundation",
            "optional hardening, broad refactoring beyond those declared invariants, speculative edge cases, or unrelated review",
            "local correction that preserves those contracts and owners does not acquire an architecture ceremony",
            "Test-driven development (TDD) is allowed only for observed failure reproduction",
            "declared acceptance conditions, verified-cause isolation, safe deterministic PAO execution, or repository-required checks",
            "never replaces or expands the PAO",
            "never freezes unverified or workaround output",
            "Evidence-connected safety stop",
            "reachable confidentiality, integrity, authentication, authorization, trust-boundary, injection, untrusted-execution, data-loss, corruption, irreversible-action, or publication risk",
            "activate the existing risk owners",
            "Only containment or remediation needed to resume may proceed",
            "grants no publication authority",
            "smallest deterministic regression guards",
            "repository-required and likeliest adjacent checks",
            "rerun the PAO",
            "later relevant change invalidates the affected evidence",
            "Hardening is work beyond the declared functional contract, its proportionate evidence-triggered required architecture and extension seams",
            "Admit hardening separately only after `Functional PASS` and `Regression PASS`",
            "keep it as nonblocking backlog",
            "hypothetical variants or architecture/refactoring beyond the declared functional invariants",
            "evidence-backed accepted extension seam is hardening",
            "change to externally visible success or failure semantics is functional scope and restarts affected gates",
            "QA aggregates PAO results, regression and repository-required check results, snapshot identity, unchecked surfaces",
            "triggered-reviewer table recording each trigger rule, its evidence, and whether its reviewer was invoked",
            "mandatory reviewer is triggered only by an existing `AGENTS.md` or repository rule or clause 4 evidence",
            "ambiguity about whether such a trigger applies invokes that reviewer",
            "Only those three cited bases constitute a real, gate-bearing veto under this policy",
            "all other reviewer findings are non-veto improvements or nonblocking hardening and go to backlog",
            "Neither the implementer nor $lead may waive or backlog a real, gate-bearing veto",
            "Two failed corrections based on the same hypothesis or a materially equivalent approach forbid a third use of that approach",
            "Reset diagnosis across the root, owner, siblings, and affected surface",
            "new falsifiable approach, separately admit a prerequisite or redesign, or report a real external `BLOCKED`",
            "new hypothesis, a material difference from both failed approaches, a falsifying probe, and `$lead` acceptance of the affected surface",
            "Keep gate, correction-budget, and backlog history under one stable lineage",
            "cited supersession may correct classification, seams, or acceptance without resetting the budget",
            "Relabeling, splitting, or merging cannot erase or reset history or move an item between gate and backlog",
            "derived work inherits that history",
            "gate admission or exit under clauses 2, 4, 6, or 8 records one line of evidence against the frozen PAO ID",
            "Resolve ambiguity into PAO scope or a mandatory veto",
            "Publication safety unchanged",
            "genuinely multi-model commission only for a final candidate cross-cutting governance or design contract",
            "used by more than one workflow, owner, or module",
            "ordinary local code fixes and inline corrections that preserve the accepted contract are excluded",
            "Freeze the artifact before review",
            "at least two demonstrably different base-model families",
            "differences in role, prompt, effort, alias, or variant do not count as model diversity",
            "Record each runtime provider and model identity",
            "unavailable required diversity returns a real external `BLOCKED`",
            "synthesis records every verdict",
            "independently evaluate whether the proposal's premises, boundary, consequences, lifecycle cost, and coupling are sound",
            "user or author preference verifies intent, not technical correctness",
            "names accepted and rejected premises",
            "materially better alternative when one exists with its trade-off and `Would-flip-if`",
            "returns an evidence-based verdict",
            "resolves disagreement against the PAO, mandatory vetoes, and cited evidence rather than majority vote or deference",
            "is the sole candidate",
            "synthesis change is re-reviewed on the exact delta by each affected commission member",
            "Optional alternatives remain backlog and do not create another review round",
        ):
            with self.subTest(required=required):
                self.assertIn(required, extract)

    def test_functional_first_policy_has_one_canonical_owner(self) -> None:
        owner_marker = "**Functional-first delivery (binding).**"
        spine = self._read(SPINE)
        extract = self._read(FUNCTIONAL_FIRST_EXTRACT)
        self.assertEqual(spine.count(owner_marker), 1)
        self.assertNotIn(owner_marker, extract)
        self.assertIn("nonbinding elaboration", extract)
        self.assertIn("spine is the self-sufficient,\ncanonical binding owner", extract)
        for projection in (METHODOLOGY, *PROJECTIONS):
            with self.subTest(projection=projection):
                self.assertNotIn(owner_marker, self._read(projection))

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

    def test_codex_review_loop_defaults_to_two_explicit_standard_codex_verdicts(self) -> None:
        text = self._read("src.codex/skills/review-loop/SKILL.md")
        for required in (
            "two fresh explicit external Codex processes",
            "`externalProvider: codex`",
            "distinct attempt IDs, prompt files, and committed receipts",
            "never `auto` or Claude",
            "must not request `fast`, `priority`, or `ultrafast`",
            "explicitly user-selected approved API-key route",
            "never a fallback",
            "Kimi may be explicitly selected for the deep/wide angle",
            "failed Kimi lane remains UNVERIFIED",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)
        self.assertNotIn("`auto` resolves to Claude on the Codex line", text)

    def test_provenance_templates_keep_kimi_explicit_and_grok_unavailable(self) -> None:
        for relative in PROVENANCE_PROVIDER_TEMPLATES:
            text = self._read(relative)
            for required in (
                "kimi | grok>",
                "Kimi",
                "read-only",
                "nonauthorizing",
                "Grok remains unavailable",
                "must never be selected",
            ):
                with self.subTest(relative=relative, required=required):
                    self.assertIn(required, text)
            for forbidden in (
                "<internal | codex | claude | gemini | qwen>",
                "<internal | codex | claude | gemini | qwen | kimi | grok>",
                "Grok CLI",
                "external CLI (Grok",
            ):
                with self.subTest(relative=relative, forbidden=forbidden):
                    self.assertNotIn(forbidden, text)

    def test_substantive_prompt_policy_allows_only_the_fixed_synthetic_smoke_exception(self) -> None:
        reference = self._read("docs/agents-mode-reference.md")
        principles = self._read("shared/references/spine/delegation-principles.md")
        self.assertIn("fixed synthetic non-substantive smoke token", reference)
        self.assertNotIn("documented provider limitations", reference)
        self.assertIn("approved prompt wrapper or fail/reroute", principles)
        self.assertNotIn("An inline fallback", principles)


if __name__ == "__main__":
    unittest.main()
