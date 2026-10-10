"""Regression contract for the evidence-triggered workflow economy policy."""

import json
from pathlib import Path
import re
import unittest
from policy_text_contract import identifier_present, relationships, selected_section, selected_unit


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
KIMI_WORKFLOW_PROJECTIONS = (
    "src.codex/skills/lead/operating-model.md",
    "src.claude/agents/contracts/operating-model.md",
)
KIMI_EXTERNAL_DISPATCH_PROJECTIONS = (
    "src.codex/skills/lead/external-dispatch.md",
    "src.claude/agents/contracts/external-dispatch.md",
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
ARCHITECTURE_REVIEWER_PROJECTIONS = (
    "src.codex/skills/architecture-reviewer/SKILL.md",
    "src.claude/agents/architecture-reviewer.md",
)
LEAD_SKILL_PROJECTIONS = (
    "src.codex/skills/lead/SKILL.md",
    "src.claude/skills/lead/SKILL.md",
)
LEAD_ROUTING_PROJECTIONS = (
    "src.codex/skills/lead/operating-model.md",
    "src.claude/agents/contracts/operating-model.md",
)
ARCHITECT_PROJECTIONS = (
    "src.codex/skills/architect/SKILL.md",
)

PROFESSION_ROLES = (
    "algorithm-scientist", "backend-engineer", "computational-scientist",
    "data-engineer", "frontend-engineer", "geometry-engineer",
    "graphics-engineer", "model-view-engineer", "platform-engineer",
    "qt-ui-engineer", "toolchain-engineer", "visualization-engineer",
)
D3_ROLES = (
    "algorithm-scientist", "computational-scientist", "qa-engineer",
    "platform-engineer", "reliability-engineer", "toolchain-engineer",
)
A4 = "Treat generality, extensibility, low coupling, cohesion, simplicity, and efficiency as one design tradeoff."
D3 = "A machine-readable run manifest is required only when output is published, packaged, or golden; compared across environments; or an accepted scientific/performance reproducibility requirement applies."
RUNTIME_ROLE_CLAUSES = {
    "backend-engineer": "Every new or modified outbound HTTP, database, queue, cache, or RPC operation has an effective finite timeout owned at the narrowest coherent boundary—call site, shared client or driver, request or transaction context, or composition policy—plus a bounded-backoff retry or explicit no-retry decision and failure mapping. Name the timeout owner and prove inheritance; a default infinite timeout or unverified inheritance is a finding.",
    "reliability-engineer": "For every retried mutation, state the idempotency mechanism (key, dedupe, or naturally idempotent operation), maximum attempts, backoff with jitter, and the authoritative outcome the retry observes. A definitive synchronous returned result is sufficient for the sole caller. When another consumer must observe or reconcile after return, cite the writer-owner and an independently observable settled state through the owning contract—event, callback or future, versioned query, or equivalent. Do not invent an event; a retried non-idempotent mutation without a guard, or an asynchronous observer without authoritative settlement, is a finding.",
    "model-view-engineer": "Every structural mutation uses its matching `begin*`/`end*` pair. Pair `layoutChanged` with `layoutAboutToBeChanged` and required persistent-index updates; batch `dataChanged` over the minimal range and roles. Choose granular notification, layout change, or reset by model/index/view correctness first, then coherent simplicity and representative performance. Prefer granular notification when it preserves required indexes, selection/current item, and viewport without disproportionate bookkeeping. Reset is valid for radical data/structure change or when correct granular bookkeeping is materially more complex or error-prone; name invalidated current/selected items and caller recovery.",
}
RETIRED_MODEL_VIEW_RESET_RULE = "full reset is reserved for changes incremental signals cannot express"


def workflow_duties(text: str) -> dict[str, bool]:
    unit = selected_unit(text, "Core delegation principles", "Workflow economy (binding):")
    return relationships(unit, {
        "optional-review-evidence": "Optional review needs evidence",
        "design-decision-gate": "design-decision=>one gate, not standing pre-implementation gate",
        "triggered-mandatory-qa": "One final QA package of triggered mandatory risk owners",
        "scoped-rereview": "Re-review open finding/changed delta only",
        "full-review-trigger": "full only new defect class/material upstream revision",
        "optional-advice-default": "Consultant/$external-brigade default off",
        "advisory-readiness": "At readiness/decision Lead may choose Kimi",
        "unavailable-provider": "Grok unavailable in 1.x; no launch/probe",
        "quick-fix-ceremony": "Quick-fix: no pre-implementation review ceremony",
        "specialist-artifact": "Per result: one canonical specialist artifact",
        "root-ledger": "Per result: one canonical specialist artifact and one concise root ledger entry",
        "progress-only-refusal": "No progress-only artifact/REVISE while safe implementation/validation remains",
        "publication-preservation": "Never weaken human publication/leak gates",
        "domain-gate-preservation": "Never weaken human publication/leak gates or security-, performance-, geometry-sensitive template requirements",
    })


def shared_advisory_duties(text: str) -> dict[str, bool]:
    unit = selected_unit(text, "Core delegation principles", "Workflow economy (binding):")
    duties = relationships(unit, {
        "lead-optional-read-only": "At readiness/decision Lead may choose Kimi for bounded independent read-only ambiguity/options",
        "no-call-or-skip": "At readiness/decision Lead may choose Kimi for bounded independent read-only ambiguity/options, else no call/skip",
        "no-auto-gate-counter": "Kimi: not auto/gate/counter",
        "availability-evidence": "availability/quota evidence",
        "fixed-wrapper": "fixed kimi-code/k3 wrapper",
        "independent-verification": "independent verification; nonauthorizing",
    })
    duties["fixed-wrapper"] &= identifier_present(unit, "kimi-code/k3")
    return duties


def projected_advisory_duties(text: str) -> dict[str, bool]:
    unit = selected_section(text, "Workflow economy projection")
    readiness = "At a natural readiness or decision point, if a bounded independent read-only alternative view would materially reduce unresolved ambiguity or compare consequential options"
    availability = "current availability or quota claims require evidence"
    duties = relationships(unit, {
        "readiness-condition": readiness,
        "lead-optional-selection": readiness + ", Lead considers an advisory route and may explicitly select Kimi without waiting for a user reminder",
        "no-call-or-skip": "Otherwise no Kimi call or skip record is required",
        "no-auto-gate-counter": "Selection never enters auto or creates a gate or counter",
        "availability-evidence": availability,
        "fixed-wrapper": availability + ", and the existing wrapper-only fixed kimi-code/k3",
        "independent-verification": availability + ", and the existing wrapper-only fixed kimi-code/k3, independently verified, nonauthorizing",
    })
    duties["fixed-wrapper"] &= identifier_present(unit, "kimi-code/k3")
    return duties


def readability_duties(text: str) -> dict[str, bool]:
    unit = selected_unit(text, "Scope and ownership discipline", "Readability:")
    duties = relationships(unit, {
        "clear-owner-flow": "clear names/flow/invariants/ownership/abstraction",
        "conditional-separation": "separate scenario from parse/storage/transport only if mixing harms local/independent reasoning/change",
        "operations": "Operations, not pass-throughs",
        "no-forced-fragmentation": "No forced wrappers/fragmentation/length limits or atomic-invariant/measured-hot-path splits",
        "needed-reads": "Read all needed; minimize edits, not reads",
    })
    general = selected_unit(text, "Scope and ownership discipline", "General-case over local symptoms:")
    duties.update(relationships(general, {"abstraction-owner": "find the correct concept/abstraction level"}))
    return duties


def continuation_duties(text: str) -> dict[str, bool]:
    unit = selected_unit(text, "Core delegation principles", "One task across questions/updates/compaction:")
    return relationships(unit, {
        "task-free-only": "task-free questions may end, no closeout while work remains",
        "independent-continuation": "Decisions pause dependents; independent ready work continues",
        "authorized-remainder": "end only with all authorized remainder concretely blocked",
    })


def projected_continuation_duties(text: str, primary_section: str) -> dict[str, bool]:
    primary = selected_unit(text, primary_section, "For a question, status check, or clarification,")
    duties = relationships(primary, {
        "dependent-decision-only": "a required user decision pauses only dependent work; independent ready work continues; stopping requires every remaining authorized action be concretely blocked",
    })
    waiting = selected_unit(text, "Bootstrap - first action", "Wait only for an artifact or gate decision")
    duties.update(relationships(waiting, {
        "dependent-wait-only": "Wait only for an artifact or gate decision that blocks a dependent next action; independent admitted work continues",
    }))
    settling = selected_unit(text, "Bootstrap - first action", "Settle and continue:")
    accepted = "on an accepted terminal result, verify its accepted gate"
    logical = accepted + ", settle the existing ledger/status and logical phase"
    duties.update(relationships(settling, {
        "accepted-gate": accepted,
        "logical-settlement": logical,
        "supported-release-and-continue": logical + ", then apply supported host release/accounting, and execute the next admitted action",
        "no-repeat-closeout": "do not repeat verdict or polish unless evidence is incomplete",
    }))
    return duties


class TestWorkflowEconomyContract(unittest.TestCase):
    def _read(self, relative: str) -> str:
        path = REPO_ROOT / relative
        self.assertTrue(path.is_file(), f"workflow-economy owner missing: {relative}")
        return path.read_text(encoding="utf-8")

    def _section(self, relative: str, start: str, end: str) -> str:
        text = self._read(relative)
        start_offset = text.find(start)
        self.assertNotEqual(start_offset, -1, f"{relative} missing section start: {start!r}")
        end_offset = text.find(end, start_offset + len(start))
        self.assertNotEqual(end_offset, -1, f"{relative} missing section end: {end!r}")
        return text[start_offset:end_offset]

    def _assert_contract_marker(self, relative: str, text: str, marker: str) -> None:
        self.assertTrue(marker in text, f"{relative} missing contract marker: {marker!r}")

    def _assert_retired_rule_absent(self, relative: str, text: str, retired: str) -> None:
        self.assertTrue(retired not in text, f"{relative} retains retired rule: {retired!r}")

    def test_scoped_duties_accept_formatting_and_reject_wrong_locations(self) -> None:
        text = self._read(SPINE)
        formatted = text.replace("Optional review", "**OPTIONAL**   REVIEW").replace(
            "Re-review", "Re—review"
        ).replace("No forced", "_NO_    FORCED").replace(
            "## Core delegation principles", "  ## **CORE DELEGATION PRINCIPLES**"
        )
        for check in (workflow_duties, shared_advisory_duties, readability_duties, continuation_duties):
            with self.subTest(check=check.__name__, case="formatting"):
                self.assertTrue(all(check(formatted).values()))
        qualified = text.replace("At readiness/decision Lead may choose", "**AT** readiness/decision   Lead may choose")
        with self.subTest(case="intact-governing-advisory-condition"):
            self.assertTrue(shared_advisory_duties(qualified)["no-call-or-skip"])
        for malformed in ("", "## Core delegation principles\n", text.replace("## Core delegation principles", "## Unrelated"),
                          text + "\n## Core delegation principles\n- Duplicate owner\n"):
            with self.subTest(case="missing-empty-or-duplicate"):
                with self.assertRaises(AssertionError):
                    workflow_duties(malformed)
        unit = selected_unit(text, "Core delegation principles", "Workflow economy (binding):")
        with self.subTest(case="duplicate-normative-unit"):
            with self.assertRaises(AssertionError):
                workflow_duties(text.replace(unit, unit + "\n- **Workflow economy (binding):** " + unit, 1))
        clause = "One final QA package of triggered mandatory risk owners;"
        moved = text.replace(unit, unit.replace(clause, "", 1), 1) + "\n## Examples\n" + clause
        self.assertFalse(workflow_duties(moved)["triggered-mandatory-qa"])

    def test_workflow_duties_reject_distinct_loss_and_polarity_mutations(self) -> None:
        text = self._read(SPINE)
        unit = selected_unit(text, "Core delegation principles", "Workflow economy (binding):")
        cases = (
            (workflow_duties, "optional-review-evidence", "Optional review needs evidence", "Optional review needs no evidence"),
            (workflow_duties, "design-decision-gate", "not standing pre-implementation gate", "a standing pre-implementation gate"),
            (workflow_duties, "triggered-mandatory-qa", "One final QA", "One preliminary QA"),
            (workflow_duties, "triggered-mandatory-qa", "One final QA", "Optional one final QA"),
            (workflow_duties, "triggered-mandatory-qa", "One final QA", "Optional: One final QA"),
            (workflow_duties, "triggered-mandatory-qa", "One final QA", "Optionally, One final QA"),
            (workflow_duties, "triggered-mandatory-qa", "One final QA", "Not required: One final QA"),
            (workflow_duties, "triggered-mandatory-qa", "One final QA", "Informative: One final QA"),
            (workflow_duties, "triggered-mandatory-qa", "triggered mandatory risk", "mandatory risk"),
            (workflow_duties, "triggered-mandatory-qa", "triggered mandatory risk", "triggered optional risk"),
            (workflow_duties, "scoped-rereview", "open finding/changed delta only", "all findings and unchanged deltas"),
            (workflow_duties, "full-review-trigger", "full only new defect class/material upstream revision", "full on every local edit"),
            (workflow_duties, "optional-advice-default", "default off", "default on"),
            (workflow_duties, "specialist-artifact", "one canonical specialist artifact", "two canonical specialist artifacts"),
            (workflow_duties, "root-ledger", "one concise root ledger entry", "an optional root ledger entry"),
            (workflow_duties, "progress-only-refusal", "while safe implementation/validation remains", "after all implementation/validation is blocked"),
            (workflow_duties, "publication-preservation", "human publication/leak gates", "publication/leak gates"),
            (workflow_duties, "publication-preservation", "human publication/leak gates", "human publication gates"),
            (workflow_duties, "domain-gate-preservation", "security-, performance-, geometry-sensitive", "performance-, geometry-sensitive"),
            (workflow_duties, "domain-gate-preservation", "security-, performance-, geometry-sensitive", "security-, geometry-sensitive"),
            (workflow_duties, "domain-gate-preservation", "security-, performance-, geometry-sensitive", "security-, performance-sensitive"),
            (shared_advisory_duties, "lead-optional-read-only", "Lead may choose Kimi", "Lead must choose Kimi"),
            (shared_advisory_duties, "lead-optional-read-only", "bounded independent read-only", "bounded independent read-write"),
            (shared_advisory_duties, "no-call-or-skip", "else no call/skip", "else a skip record is mandatory"),
            (shared_advisory_duties, "no-auto-gate-counter", "not `auto`/gate/counter", "use `auto`/gate/counter"),
            (shared_advisory_duties, "availability-evidence", "availability/quota evidence", "availability/quota assumptions"),
            (shared_advisory_duties, "fixed-wrapper", "kimi-code/k3", "kimi-code/k4"),
            (shared_advisory_duties, "independent-verification", "independent verification; nonauthorizing", "independent verification; authorizing"),
            (shared_advisory_duties, "independent-verification", "independent verification; nonauthorizing", "self-verification; nonauthorizing"),
        )
        for check, duty, old, new in cases:
            with self.subTest(duty=duty, loss=old, changed_to=new):
                self.assertEqual(unit.count(old), 1)
                mutated = text.replace(unit, unit.replace(old, new, 1), 1)
                self.assertFalse(check(mutated)[duty], f"mutation retained {duty}")

    def test_readability_and_continuation_guards_reject_distinct_losses(self) -> None:
        text = self._read(SPINE)
        cases = (
            (readability_duties, "Scope and ownership discipline", "Readability:", "conditional-separation", "only if mixing harms", "whether or not mixing harms"),
            (readability_duties, "Scope and ownership discipline", "Readability:", "operations", "Operations, not pass-throughs", "Pass-throughs, not operations"),
            (readability_duties, "Scope and ownership discipline", "Readability:", "no-forced-fragmentation", "No forced wrappers", "Mandatory wrappers"),
            (readability_duties, "Scope and ownership discipline", "Readability:", "no-forced-fragmentation", "atomic-invariant/measured-hot-path splits", "unmeasured splits"),
            (readability_duties, "Scope and ownership discipline", "Readability:", "needed-reads", "minimize edits, not reads", "minimize reads, not edits"),
            (continuation_duties, "Core delegation principles", "One task across questions/updates/compaction:", "task-free-only", "no closeout while work remains", "closeout while work remains"),
            (continuation_duties, "Core delegation principles", "One task across questions/updates/compaction:", "independent-continuation", "independent ready work continues", "independent ready work stops"),
            (continuation_duties, "Core delegation principles", "One task across questions/updates/compaction:", "authorized-remainder", "all authorized remainder concretely blocked", "any authorized action blocked"),
        )
        for check, section, marker, duty, old, new in cases:
            with self.subTest(duty=duty, loss=old):
                unit = selected_unit(text, section, marker)
                self.assertEqual(unit.count(old), 1)
                self.assertFalse(check(text.replace(unit, unit.replace(old, new, 1), 1))[duty])
        projected = self._read(LEAD_SKILL_PROJECTIONS[0])
        unit = selected_unit(projected, "Bootstrap - first action", "Settle and continue:")
        for duty, old, new in (
            ("accepted-gate", "verify its accepted gate", "assume its gate"),
            ("logical-settlement", "ledger/status and logical phase", "ledger/status only"),
            ("supported-release-and-continue", "supported host release/accounting", "forced host termination"),
            ("no-repeat-closeout", "unless evidence is incomplete", "even when evidence is complete"),
        ):
            with self.subTest(projection=LEAD_SKILL_PROJECTIONS[0], duty=duty):
                self.assertEqual(unit.count(old), 1)
                changed = projected.replace(unit, unit.replace(old, new, 1), 1)
                self.assertFalse(projected_continuation_duties(changed, "Flow-continuity rule")[duty])

    def test_advisory_projection_rejects_lost_optional_duties(self) -> None:
        text = self._read(KIMI_WORKFLOW_PROJECTIONS[0])
        for duty, old, new in (
            ("lead-optional-selection", "may explicitly select Kimi", "must explicitly select Kimi"),
            ("no-call-or-skip", "Otherwise no Kimi call or skip record is required", "Otherwise a Kimi call or skip record is required"),
            ("availability-evidence", "current availability or quota claims require evidence", "availability and quota claims need no evidence"),
            ("fixed-wrapper", "kimi-code/k3", "kimi-code/k4"),
            ("independent-verification", "independently verified, nonauthorizing", "independently verified, authorizing"),
        ):
            with self.subTest(duty=duty):
                section = selected_section(text, "Workflow economy projection")
                self.assertEqual(section.count(old), 1)
                self.assertFalse(projected_advisory_duties(text.replace(section, section.replace(old, new, 1), 1))[duty])
        shared = self._read(SPINE)
        unit = selected_unit(shared, "Core delegation principles", "Workflow economy (binding):")
        with self.subTest(case="exact-wrapper-characters"):
            changed = shared.replace(unit, unit.replace("kimi-code/k3", "kimi—code/k3", 1), 1)
            self.assertNotIn("kimi-code/k3", selected_unit(changed, "Core delegation principles", "Workflow economy (binding):"))
            self.assertFalse(shared_advisory_duties(changed)["fixed-wrapper"])

    def test_codex_lead_routes_settled_demanding_decision_no_solve_before_next_dispatch(self) -> None:
        checkpoint = self._section(
            "src.codex/skills/lead/SKILL.md", "- **Settled no-solve checkpoint.**", "- **Capacity discovery.**"
        )
        for marker in (
            "second settled no-solve",
            "same frozen genuinely demanding decision",
            "hypotheses, methods, observed results, and unresolved claim",
            "execution from judgment",
            "task-specific domain owner and policy/host-admitted task class",
            "astra-high",
            "astra-xhigh",
            "If the decision remains genuinely demanding and no materially different sufficient Sol approach with a falsifier is evidenced, MUST request an explicit Astra profile for the next launch.",
            "original acceptance oracle",
            "quota",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, checkpoint)
        for hardcoded_domain in ("model/math", "computational-scientist", "critical-design"):
            with self.subTest(hardcoded_domain=hardcoded_domain):
                self.assertNotIn(hardcoded_domain, checkpoint)

    def test_role_alignment_keeps_coordination_and_architecture_evidence_triggered(self) -> None:
        # Source-contract proof only; independent review owns behavioral-obedience evidence.
        selected_item_rule = (
            "Resolve the selected item and its declared dependencies first. Missing/stale state blocks only "
            "an item that is selected, depended on, or in verified physical/ownership conflict; surface "
            "unrelated active-item drift without blocking ready work."
        )
        for relative in LEAD_SKILL_PROJECTIONS:
            self.assertIn(selected_item_rule, self._read(relative), relative)

        routing_rule = (
            "Resolve the template and evidence triggers first. Each listed role is a candidate; include it "
            "only when its artifact is required by accepted uncertainty, contract, or risk. Preserve mandatory "
            "security, performance, geometry, scientific, human, and publication gates."
        )
        for relative in LEAD_ROUTING_PROJECTIONS:
            text = self._read(relative)
            self.assertIn("## Routing examples", text, relative)
            self.assertIn(routing_rule, text, relative)

        applicability_rule = (
            "Apply a law only when accepted evidence triggers its concern. An existing boundary law governs "
            "use of that boundary; it does not require creating one."
        )
        seam_rule = (
            "Keep changes local to the correct owner and extend an accepted seam when it fits. Create the "
            "smallest stable seam when justified by an accepted current requirement, accepted declared future "
            "direction, concrete second consumer, evidenced domain variability, or verified external-contract "
            "evolution; a second consumer is evidence, not a prerequisite. Otherwise correct the current owner "
            "directly."
        )
        for relative in ARCHITECT_PROJECTIONS:
            text = self._read(relative)
            self.assertIn(applicability_rule, text, relative)
            self.assertIn(seam_rule, text, relative)
            self.assertIn("When the design creates, changes, or consumes a serialized/wire boundary", text, relative)
            self.assertIn("Otherwise, ordinary repo-standard run evidence suffices.", text, relative)

        for relative in ARCHITECTURE_REVIEWER_PROJECTIONS:
            text = self._read(relative)
            self.assertIn(applicability_rule, text, relative)
            self.assertIn("A non-triggered law is not a finding.", text, relative)
            self.assertIn(
                "Verify that the change stays local to the correct owner, extends an accepted seam when suitable, "
                "or creates the smallest stable seam only for an accepted current requirement, accepted declared "
                "future direction, concrete second consumer, evidenced domain variability, or verified external-contract "
                "evolution; a second consumer is evidence, not a prerequisite.",
                text,
                relative,
            )
            self.assertIn("Otherwise, ordinary repo-standard run evidence suffices.", text, relative)

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
        intro = spine.split("## Role index", 1)[0]
        normalized_intro = " ".join(re.findall(r"[a-z0-9/]+", intro.casefold()))
        self.assertIn("maintainer only", normalized_intro)
        self.assertIn("shared/references/ is not installed", normalized_intro)
        self.assertRegex(
            normalized_intro,
            r"\b(?:rules suffice|(?:these )?rules are self sufficient)\b",
        )

    def test_canonical_rule_keeps_evidence_gates_and_minimizes_ceremony(self) -> None:
        spine = self._read(SPINE)
        for duty, present in workflow_duties(spine).items():
            with self.subTest(owner=SPINE, duty=duty):
                self.assertTrue(present, f"{SPINE}: missing or inverted workflow duty {duty}")

    def test_targeted_continuation_and_abstraction_clarifications_preserve_existing_gates(self) -> None:
        spine = self._read(SPINE)
        for check in (readability_duties, continuation_duties):
            for duty, present in check(spine).items():
                with self.subTest(owner=SPINE, duty=duty):
                    self.assertTrue(present, f"{SPINE}: missing or inverted duty {duty}")
        with self.subTest(owner=SPINE, duty="no-dependent-decision-stop-override"):
            self.assertNotIn("required user decision overrides", spine)

        for relative in LEAD_SKILL_PROJECTIONS:
            text = self._read(relative)
            primary_section = "Flow-continuity rule" if relative.startswith("src.codex/") else "Primary-task lock"
            for duty, present in projected_continuation_duties(text, primary_section).items():
                with self.subTest(owner=relative, duty=duty):
                    self.assertTrue(present, f"{relative}: missing or inverted continuation duty {duty}")
            with self.subTest(owner=relative, duty="no-dependent-decision-stop-override"):
                self.assertNotIn("genuine user-required decision overrides", text, relative)

        for relative in ARCHITECTURE_REVIEWER_PROJECTIONS:
            text = self._read(relative)
            for required in (
                "Run this check only inside an already-triggered Architecture Reviewer gate; it creates no "
                "reviewer, lane, artifact, engine, or review loop.",
                "any `PILED` class maps to `REVISE`",
            ):
                with self.subTest(owner=relative, duty=required):
                    self.assertIn(required, text, relative)

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
            "accepted requirement or declared future direction/evidenced domain variability/current second consumer/verified external-contract evolution)=>simplest one-owner stable/local seam",
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

    def test_kimi_advisory_selection_is_optional_and_lead_selectable(self) -> None:
        for duty, present in shared_advisory_duties(self._read(SPINE)).items():
            with self.subTest(owner=SPINE, duty=duty):
                self.assertTrue(present, f"{SPINE}: missing or inverted advisory duty {duty}")
        for relative in KIMI_WORKFLOW_PROJECTIONS:
            for duty, present in projected_advisory_duties(self._read(relative)).items():
                with self.subTest(owner=relative, duty=duty):
                    self.assertTrue(present, f"{relative}: missing or inverted advisory duty {duty}")

    def test_profession_conditions_are_paired_and_evidence_triggered(self) -> None:
        for role in PROFESSION_ROLES:
            paths = (
                f"src.codex/skills/{role}/SKILL.md",
                f"src.claude/agents/{role}.md",
            )
            texts = tuple(self._read(path) for path in paths)
            for text in texts:
                self.assertIn(A4, text)
                self.assertIn("a second consumer is evidence, not a prerequisite", text)
                self.assertNotIn("a new variant is a plugin + thin scenario", text)
                self.assertNotIn("MOST GENERAL level its responsibility allows", text)
        for role in D3_ROLES:
            paths = (
                f"src.codex/skills/{role}/SKILL.md",
                f"src.claude/agents/{role}.md",
            )
            for path in paths:
                text = self._read(path)
                self.assertIn(D3, text)
                self.assertIn("Otherwise, ordinary repo-standard run evidence suffices.", text)
                self.assertIn("declared-absent passes", text)
                self.assertNotIn("every result-producing/golden/validation/release run emits", text)

    def test_runtime_role_conditions_project_all_accepted_clauses(self) -> None:
        for role, clause in RUNTIME_ROLE_CLAUSES.items():
            paths = (
                f"src.codex/skills/{role}/SKILL.md",
                f"src.claude/agents/{role}.md",
            )
            for path in paths:
                text = self._read(path)
                with self.subTest(path=path):
                    self.assertIn(clause, text)
                    if role == "model-view-engineer":
                        self.assertNotIn(RETIRED_MODEL_VIEW_RESET_RULE, text)

        selector = "Explicit user or Lead override may choose Kimi"
        for relative in (*KIMI_WORKFLOW_PROJECTIONS, *KIMI_EXTERNAL_DISPATCH_PROJECTIONS):
            text = self._read(relative)
            with self.subTest(relative=relative, relation="selector"):
                self.assertIn(selector, text)
                self.assertNotIn("Explicit user override may choose Kimi", text)

    def test_methodology_defers_to_the_shared_rule(self) -> None:
        methodology = self._read(METHODOLOGY)
        self.assertIn("Workflow economy is owned by `shared/AGENTS.shared.md`", methodology)

    def test_generic_review_keeps_risk_roles_conditional_and_critical_templates_strict(self) -> None:
        template = json.loads(self._read("src.claude/agents/team-templates/review.json"))
        roles = {role["agentType"]: role for role in template["roles"]}

        self.assertEqual(template["requiredRoles"], [])
        self.assertEqual(template["minRoles"], 1)
        for agent_type, triggers in (
            ("analyst", ("unresolved factual baseline", "explicitly requested factual investigation outcome")),
            ("qa-engineer", ("missing accepted verification evidence", "explicitly requested quality assurance outcome")),
            ("architecture-reviewer", ("code-quality objective",)),
            ("security-reviewer", ("authentication",)),
            ("performance-reviewer", ("hard latency",)),
            ("accessibility-reviewer", ("user-facing ui",)),
        ):
            with self.subTest(template="review", agent_type=agent_type):
                self.assertIsNot(roles[agent_type].get("required"), True)
                condition = roles[agent_type].get("whenNeeded", "").lower()
                for trigger in triggers:
                    self.assertIn(trigger, condition)
        for retired_label in ("documentation review", "project audit", "post-implementation validation"):
            with self.subTest(template="review", retired_label=retired_label):
                self.assertNotIn(
                    retired_label,
                    " ".join(role.get("whenNeeded", "").lower() for role in template["roles"]),
                )
        for marker in (
            "named by the objective",
            "triggered role",
            "missing triggered verdict",
            "critical templates",
        ):
            with self.subTest(template="review", marker=marker):
                self._assert_contract_marker("src.claude/agents/team-templates/review.json", template["notes"], marker)

    def test_provider_review_entrypoints_keep_objective_selection_and_triggered_risk_gates(self) -> None:
        codex = "src.codex/AGENTS.codex.md"
        rows = [line for line in self._read(codex).splitlines() if line.startswith("| `review` |")]
        self.assertEqual(len(rows), 1)
        for marker in ("objective-named reviewer", "evidence-triggered helpers", "when present"):
            self._assert_contract_marker(codex, rows[0], marker)

        claude = self._read("src.claude/CLAUDE.md")
        self.assertNotIn("| `review` |", claude)
        self.assertIn(".claude/agents/team-templates/", claude)
        self.assertIn("For `requiresLead: false` routes", claude)

        for relative, required_role in (
            ("src.claude/agents/team-templates/security-sensitive.json", "security-reviewer"),
            ("src.claude/agents/team-templates/performance-sensitive.json", "performance-reviewer"),
        ):
            critical = json.loads(self._read(relative))
            critical_roles = {role["agentType"]: role for role in critical["roles"]}
            with self.subTest(template=relative, agent_type=required_role):
                self.assertIn(required_role, critical["requiredRoles"])
                self.assertIs(critical_roles[required_role].get("required"), True)

    def test_review_loop_admission_is_evidence_triggered_across_provider_reviewers(self) -> None:
        required_markers = (
            "**Simple exact-delta route.**",
            "verified one-owner cause",
            "one clear falsifying oracle",
            "one independent exact-delta review",
            "without review-loop state",
            "**Mandatory review-loop triggers.**",
            "genuine complexity or ambiguity",
            "materially competing owner/seam solutions",
            "repeated review/fix failure",
            "newly discovered complexity",
            "user explicitly requests the loop",
            "**Insufficient triggers.**",
            "`design-decision` tag",
            "file count",
            "identical cross-provider projections alone",
        )
        retired_rules = (
            "existing loop-to-PASS re-verification remains mandatory",
            "requires a separate `/agents-review-loop` fix-design pass before re-implementation",
        )
        for relative in ARCHITECTURE_REVIEWER_PROJECTIONS:
            text = self._section(relative, "## REVISE routing", "## Cross-domain escalation")
            for marker in required_markers:
                with self.subTest(relative=relative, marker=marker):
                    self._assert_contract_marker(relative, text, marker)
            for retired in retired_rules:
                with self.subTest(relative=relative, retired=retired):
                    self._assert_retired_rule_absent(relative, text, retired)

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

    def test_review_loop_selects_supported_initial_routes_without_weakening_provenance(self) -> None:
        for path in ("src.codex/skills/review-loop/SKILL.md", "src.claude/agents/contracts/review-loop.md"):
            text = self._read(path)
            for required in (
                "supported initial route", "external-only selection remains external-only",
                "No route switch after a failed launch", "unspecified by runtime",
                "materially competing owner/contract/seam solutions",
                "one clear falsifying oracle", "nonauthoring",
            ):
                with self.subTest(path=path, required=required):
                    self.assertIn(required, text)
        text = self._read("src.codex/skills/review-loop/SKILL.md")
        for preserved in ("existing ordinary selector", "exact discovered task tools",
                          "strict V2 parser", "full external-nonauthorizing tuple",
                          "untrusted/potentially-sensitive resultText",
                          "must not request `fast`, `priority`, or `ultrafast`",
                          "explicitly user-selected approved API-key route", "never a fallback",
                          "Kimi may be explicitly selected for the deep/wide angle",
                          "failed Kimi lane remains UNVERIFIED"):
            self.assertIn(preserved, text)
        for retired in ("two fresh explicit external Codex processes", "never `auto` or Claude",
                        "A shipped formal loop MUST use the installed"):
            self.assertNotIn(retired, text)

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
        self.assertIn("establish the same admitted execution guarantees manually", principles)
        self.assertIn("never bypass host denial or an explicit route requirement", principles)
        self.assertNotIn("An inline fallback", principles)


if __name__ == "__main__":
    unittest.main()
