"""Scoped routing/recovery source contracts, not runtime or semantic proof.

Check the approved inline clauses together with their already-composed shared
owners. Mutation cases cover known losses and polarity/scope boundaries.
"""
from pathlib import Path
import re
import unittest

from policy_text_contract import identifier_present, lexical, relationships, selected_section, selected_unit

ROOT = Path(__file__).resolve().parents[1]
CODEX = "src.codex/AGENTS.codex.md"
SHARED = "shared/AGENTS.shared.md"

# Each relationship must occur in its own policy unit, not another section,
# an example, a disconnected keyword, or a negated sentence prefix.
CLAUSES = {
    "chain-owner": ("Template routing", "The main session", (
        "The main session owns every chain, invokes its specialists in order and passes accepted artifacts downstream",
        "Light routes do not require the full `$lead` skill",
        "heavy routes activate it for work-items, risk owners, integration and gates",
        "Never spawn `$lead`",
        "Explicit `$lead` use and `delegationMode: auto|force` change coordination, not template admission or artifact requirements",
    )),
    "classification": ("Template routing", "Classify the task", (
        "Classify the task, choose the narrowest matching workflow shape, and re-classify immediately if scope widens",
    )),
    "factual-additive": ("Template routing", "In factual work,", (
        "In factual work, a decision, ADR or material alternatives adds `$architect`",
        "add `$planner` only when the user explicitly requests an execution plan",
    )),
    "continuity-referral": ("Template routing", "Apply shared", (
        "Apply shared Primary-task continuity and side work, including same-turn primary progress and all authority, capacity, resource and hold constraints",
        "This is governance, not a new provider runtime guarantee",
    )),
    "impact-review": ("Template routing", "Use `$review-changes`", (
        "Use `$review-changes` for a direct full repository impact review of recent changes: current local diff or specified target plus wider affected surfaces, unchanged dependents and adjacent logic",
        "A bugfix with a known file or function stays on `quick-fix` by default",
        "log adjacent issues in the configured bug registry instead of widening the plan",
    )),
    "quick-fix-referral": ("Recovery rule", "Apply the shared", (
        "Apply the shared `quick-fix` rule",
        "Its four minimal recovery facts are task, current step, last result and next action",
        "Re-classification enriches the same work-item",
        "delivery closes and archives immediately under the normal rule",
    )),
    "heavy-recovery": ("Recovery rule", "The main session", (
        "The main session owns heavier or multi-stage recovery in the configured task-memory directory",
        "heavy routes above run the full pipeline with `$lead` active",
    )),
    "stage-recovery": ("Recovery rule", "Main-conversation routes", (
        "Main-conversation routes needing continuation save recovery after each accepted stage: `status.md` (template, current stage, next role) plus the accepted artifact",
        "One-Analyst factual work needs recovery only for continuation",
        "A decision/ADR route records Analyst's accepted artifact before Architect, and Planner only for a requested execution plan",
    )),
    "closure-fields": ("Recovery rule", "Close a main-conversation-managed item", (
        "Close a main-conversation-managed item when delivered, parked, cancelled or reprioritized",
        "delivered-but-active is an orphan",
        "Lead writes `closure.md` with nonempty `Closed`, `Outcome`, `Evidence` and `Residual risk`",
        "`Closed` exactly matches `--terminal-instant` in strict UTC `YYYY-MM-DDTHH:MM:SSZ`",
    )),
    "closure-owner": ("Recovery rule", "Close a main-conversation-managed item", (
        "Lead writes `bug-dispositions.json` under the versioned Lead/lifecycle-owner contract for bug selection, recontextualization, transition and receipts",
        "apply shared Physical lifecycle V1 for the rollback-safe disposition/archive/receipt/README transaction and pending-close rules",
        "Routine single-item mechanics may run inline",
        "multi-item or drifted state routes to `$knowledge-archivist`",
        "`work-items/index.md` remains compatibility-only",
        "Keep-worthy lessons go to `work-items/lessons/`",
    )),
    "epics": ("Recovery rule", "Epics:", (
        "when several work-items serve one initiative, group them as an epic",
        "active `work-items/epics/<date>-<slug>.md`",
        "after all children close and the goal is met, the lifecycle owner archives it at `work-items/epics/archive/<YYYY-MM>/<slug>.md`, reconciles physical roots and regenerates `work-items/README.md`",
        "Each child's `status.md` has one bare `Epic: <slug>` line",
        "progress derives only from archive location",
        "Distinguish unique active, unique archived, missing and duplicate lookup",
        "duplicates fail closed",
        "`$product-manager` admits",
        "`$lead` links, rolls up and decides closure",
        "`$knowledge-archivist` owns location mechanics",
    )),
    "dependencies-decisions": ("Recovery rule", "A work-item needing", (
        "A work-item needing prior work declares `Depends-on: <slug>, <slug>` (work-item slugs) in `status.md`, a standing planned dependency edge distinct from runtime `BLOCKED:*` verdicts",
        "Lead derives blocked-by/ready",
        "Durable cross-cutting architecture decisions go in flat `work-items/decisions/<date>-<slug>.md`, `status: proposed|accepted|dropped|superseded|reverted`, referenced from `design.md` rather than buried there",
    )),
    "direct-exception": ("Recovery rule", "A direct single-specialist", (
        "A direct single-specialist invocation needs no recovery file unless itself admitted as `quick-fix`",
        "this does not broaden recovery to trivial questions",
    )),
    "role-selection": ("Role resolution paths", "Roles and utilities", (
        "Roles and utilities live in `.agents/skills/<name>/SKILL.md` for repo-local installs or `$HOME/.agents/skills/<name>/SKILL.md` globally",
        "Use the skill/custom-agent overlay matching the assigned role",
        "For other work, use the narrowest matching installed specialist, including non-core or repo-local specialists",
        "Utility skills may be invoked directly when their workflow fits",
        "The shared role index lists the core team, not an exhaustive catalog",
    )),
    "utilities": ("Role resolution paths", "Use `$init-project`", (
        "Use `$init-project` to initialize root `AGENTS.md` project policies and `.agents/.agents-mode.yaml` for a new Codex project",
        "Use `$external-brigade` to launch a bounded set of independent external helpers together instead of ad hoc orchestration",
    )),
    "provider-boundaries": ("Role resolution paths", "`$external-worker` and", (
        "`$external-worker` and `$external-reviewer` are bidirectional adapters, not Consultant aliases",
        "Both use `auto | codex | claude | kimi | grok`",
        "production `auto` uses only Codex/Claude, Kimi is explicit-only through fixed `kimi-code/k3`, results stay independently verified and nonauthorizing, and Grok is unavailable in 1.x",
    )),
    "worker-capabilities": ("Role resolution paths", "Worker:", (
        "eligible non-owner, non-review roles",
        "Kimi uses the canonical file-prompt wrapper",
        "validated capability files may select scoped worker tools only for `engineering` and a taxonomy-mapped `external-worker` profession",
    )),
    "reviewer-capabilities": ("Role resolution paths", "Reviewer:", (
        "eligible review/QA roles",
        "Explicit Kimi supports policy-admitted read-only exploration, research, planning or review",
        "Omitted capability files leave tools, Model Context Protocol servers and subagents empty with permission `reject`",
        "validated files may select read tools/servers",
    )),
}

ROUTES = (
    "User explicitly names a role: invoke it directly.",
    "Roadmap, prioritization or milestone shaping: `$product-manager`.",
    "Standalone bounded fact lookup: answer inline, no artifact.",
    "Non-trivial factual investigation without a decision: one `$analyst` by default; an explicitly named role or narrower factual domain specialist remains valid.",
    "Decision, Architecture Decision Record (ADR), or material alternatives without implementation: light `research`, `$analyst` then `$architect`; add `$planner` only for an explicitly requested execution plan.",
    "PR review, quality gate or post-implementation validation without new code: light `review`, objective-named reviewer plus only evidence-triggered helpers; order present helpers as research → QA → review.",
    "Task satisfies the shared `quick-fix` predicate: light `quick-fix`, implementer then `$qa-engineer`.",
    "Auth, trust boundaries, credentials or vulnerabilities: heavy `security-sensitive`, with `$security-engineer` and `$security-reviewer` mandatory.",
    "Hard performance budgets, service-level agreements or latency targets: heavy `performance-sensitive`, with `$performance-engineer` and `$performance-reviewer` mandatory.",
    "Spatial computation, transforms, meshing or geometry: heavy `geometry-review`, with `$computational-scientist` and `$architecture-reviewer` mandatory.",
    "Multiple risk domains: heavy `combined-critical`, with all risk owners and reviewers.",
    "Otherwise: heavy `full-delivery`, full pipeline coordinated with `$lead` active.",
)


def codex_duties(text):
    duties = {}
    for name, (heading, marker, clauses) in CLAUSES.items():
        unit = selected_unit(text, heading, marker)
        duties[name] = all(relationships(unit, {str(i): clause for i, clause in enumerate(clauses)}).values())
        duties[name] &= all(identifier_present(unit, identifier)
                            for clause in clauses for identifier in re.findall(r"`([^`]+)`", clause))
    body = selected_section(text, "Template routing")
    rows = re.findall(r"^(\d+)\. (.+)$", body, re.M)
    duties["ordered-routes"] = rows == [(str(i), row) for i, row in enumerate(ROUTES, 1)]
    duties["no-first-match"] = not re.search(r"first[- ]match", lexical(body))
    return duties


def shared_duties(text):
    continuity = selected_unit(text, "Core delegation principles", "Primary-task continuity and side work (binding).")
    lifecycle = selected_section(text, "Physical lifecycle V1")
    quick = selected_unit(text, "Core delegation principles", "quick-fix:")
    return {
        "quick-fix-owner": all(relationships(quick, {
            "minimal": "Before mutation only work-items/active/<slug>/status.md with lifecycle+4 recovery facts",
            "ceremony": "no roadmap/brief/Research/Design/Plan/consultant/pre-review",
            "reclassification": "Failed/unclear: enrich/reclassify same item",
            "delivery": "One preflight, implement/QA, close/archive",
        }).values()) and identifier_present(quick, "work-items/active/<slug>/status.md"),
        "continuity-owner": all(relationships(continuity, {str(i): phrase for i, phrase in enumerate((
            "For brief questions/status/clarifications, answer in commentary and take the next ready primary action in the same turn",
            "Without another reminder, promptly delegate substantive admitted side work to matching non-spawning specialists under existing delegation/parallel authority when capacity, full resource surfaces and gates permit",
            "then continue ready primary work in the same turn without waiting for the side result or silently promoting it",
            "Preserve resources/capacity needed by ready primary work",
            "Explicit user stop/pause/cancel/reprioritization wins", "PAUSED holds Goal work until its user/native owner resumes it",
        ))}).values()),
        "lifecycle-owner": all(relationships(lifecycle, {str(i): phrase for i, phrase in enumerate((
            "Only lifecycle owner applies dispositions/recontextualization/archive/bug-dispositions-receipt.json/README in one rollback-safe transaction",
            "active manifest pending", "Missing admission/terminal evidence/unique location/logical links fails closed",
        ))}).values()),
    }


class CodexRoutingInstructionKernelTests(unittest.TestCase):
    def setUp(self):
        self.codex = (ROOT / CODEX).read_text(encoding="utf-8")
        self.shared = (ROOT / SHARED).read_text(encoding="utf-8")

    def test_inline_obligations(self):
        for duty, present in codex_duties(self.codex).items():
            with self.subTest(duty=duty):
                self.assertTrue(present)

    def test_referrals_have_composed_shared_owners(self):
        for duty, present in shared_duties(self.shared).items():
            with self.subTest(duty=duty):
                self.assertTrue(present)

    def test_each_clause_rejects_deletion_and_negated_prefix(self):
        for duty, (heading, marker, clauses) in CLAUSES.items():
            unit = selected_unit(self.codex, heading, marker)
            for clause in clauses:
                # Preserve exact source formatting when locating the normalized clause.
                normalized = lexical(unit)
                self.assertIn(lexical(clause), normalized)
                for changed in (normalized.replace(lexical(clause), "omitted", 1),
                                normalized.replace(lexical(clause), "do not " + lexical(clause), 1)):
                    with self.subTest(duty=duty, clause=clause, changed=changed):
                        self.assertFalse(relationships(changed, {duty: clause})[duty])

    def test_known_scope_timing_and_capability_regressions_fail(self):
        mutations = (
            ("stage-recovery", "save recovery after each accepted stage", "save recovery at delivery"),
            ("factual-additive", "In factual work,", "In factual work without implementation,"),
            ("factual-additive", "add `$planner` only when", "add `$planner` whenever"),
            ("chain-owner", "Never spawn `$lead`", "Spawn `$lead`"),
            ("closure-fields", "`Closed` exactly matches", "`Closed` approximately matches"),
            ("epics", "one bare `Epic: <slug>` line", "one optional `Epic: <slug>` line"),
            ("epics", "progress derives only from archive location", "progress derives from status labels"),
            ("dependencies-decisions", "(work-item slugs)", "(arbitrary labels)"),
            ("role-selection", ".agents/skills/<name>/SKILL.md", ".agents/skills/<name>/skill.md"),
            ("direct-exception", "unless itself admitted as `quick-fix`", "even if admitted as `quick-fix`"),
            ("worker-capabilities", "only for `engineering` and", "for `engineering` or"),
            ("reviewer-capabilities", "empty with permission `reject`", "enabled with permission `allow`"),
            ("reviewer-capabilities", "may select read tools/servers", "may select write tools/servers"),
        )
        for duty, old, new in mutations:
            with self.subTest(duty=duty):
                self.assertGreaterEqual(self.codex.count(old), 1)
                changed = self.codex.replace(old, new, 1)
                try:
                    result = codex_duties(changed)[duty]
                except AssertionError:
                    result = False
                self.assertFalse(result)

    def test_route_order_and_mandatory_pairs_cannot_drift(self):
        for i, row in enumerate(ROUTES, 1):
            with self.subTest(route=i):
                changed = self.codex.replace(f"{i}. {row}", f"{i}. Omitted route.", 1)
                self.assertFalse(codex_duties(changed)["ordered-routes"])
        changed = self.codex.replace("Decision tree:", "Decision tree: use first-match routing.", 1)
        self.assertFalse(codex_duties(changed)["no-first-match"])

    def test_other_sections_and_examples_cannot_supply_missing_obligations(self):
        for duty in ("stage-recovery", "factual-additive", "worker-capabilities", "reviewer-capabilities"):
            heading, marker, _ = CLAUSES[duty]
            unit = selected_unit(self.codex, heading, marker)
            # Keep the selected unit, but move its operative tail outside the owner.
            prefix = unit.split(" ", 1)[0]
            changed = self.codex.replace(unit, prefix + " omitted", 1)
            for extra in ("\n## Unrelated\n" + unit, "\n## Examples\n" + unit, "\n```markdown\n" + unit + "\n```\n"):
                with self.subTest(duty=duty, extra=extra):
                    try:
                        result = codex_duties(changed + extra)[duty]
                    except AssertionError:
                        result = False
                    self.assertFalse(result)

    def test_missing_or_inverted_shared_owner_cannot_be_replaced_by_referral(self):
        for duty, old, new in (
            ("quick-fix-owner", "Before mutation only", "After mutation also"),
            ("continuity-owner", "then continue ready primary work in the same turn", "then pause ready primary work"),
            ("continuity-owner", "Explicit user stop/pause/cancel/reprioritization wins", "Ignore user stop/pause/cancel/reprioritization"),
            ("lifecycle-owner", "Only lifecycle owner applies", "Anyone applies"),
            ("lifecycle-owner", "active manifest pending", "active manifest complete"),
        ):
            with self.subTest(duty=duty, old=old):
                self.assertEqual(self.shared.count(old), 1)
                self.assertFalse(shared_duties(self.shared.replace(old, new, 1))[duty])


if __name__ == "__main__":
    unittest.main()
