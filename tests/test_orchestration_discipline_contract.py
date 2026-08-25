"""Contract tests for the orchestration-discipline-gaps batch.

Each admitted gap (P2/P3/P4/P5/P7/P8, A2/A3/A5/A5b/A7/A8/A9/A11/A12/A13) lands its
exact normative sentence in an INSTALLED Claude owner surface AND its Codex mirror,
so the two packs cannot drift. This test pins those normative sentences by exact
substring against the source-tree owner files. It checks STRUCTURE (the sentence is
present in every owner it must be in) — not semantics.

The spine (`shared/AGENTS.shared.md`) is merged verbatim into both installed
`AGENTS.md` files, so its two additions (P4, A5) are pinned once here.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SPINE = "shared/AGENTS.shared.md"
CLAUDE_QUICK_FIX_TEMPLATE = "src.claude/agents/team-templates/quick-fix.json"

# --- per-gap normative substrings and the owner files that MUST contain them ---
# (gap-id, substring, [owner files])
PINS = [
    # Repository-orientation Bootstrap checkpoint — both installed provider roots.
    ("orientation-a0", "**(a0) Pre-action orientation trigger**",
     ["src.claude/CLAUDE.md", "src.codex/AGENTS.codex.md"]),
    ("orientation-step0", "0. **Repository orientation.**",
     ["src.claude/CLAUDE.md", "src.codex/AGENTS.codex.md"]),
    ("orientation-record", "REPOSITORY ORIENTATION: scope=<repo-relative path>; status=<live|mutable|frozen|archived|deprecated|superseded|conflict>; workflow=<repo-relative entry point(s)>; protected=<repo-relative path(s)|none>; evidence=<path:line[,path:line...]>",
     ["src.claude/CLAUDE.md", "src.codex/AGENTS.codex.md"]),
    ("orientation-violation", "Treating missing or conflicting orientation as permission to proceed.",
     ["src.claude/CLAUDE.md", "src.codex/AGENTS.codex.md"]),

    # P4 — spine stop-rule (Fable probe text) + operational bullet (Sol text)
    ("P4-spine", "Stop-rule: a SECOND fix in one session that breaks a previously-working neighbor", [SPINE]),
    ("P4-op", "**Second-cross-break stop:** If a second fix in the same session breaks a previously working neighbor, STOP all edits.",
     ["src.claude/commands/agents-bugfix.md", "src.codex/skills/bug-hunting/SKILL.md"]),

    # A5 — spine dead-lane / fail-closed sentence
    ("A5-spine", "An errored/died/limit-hit lane is UNVERIFIED", [SPINE]),

    # P3 — N independent roots (both bug-hunting SKILLs)
    ("P3", "When N symptoms or failing cases are reported, keep N independent root hypotheses",
     ["src.claude/skills/bug-hunting/SKILL.md", "src.codex/skills/bug-hunting/SKILL.md"]),

    # P2+P5 — oracle-anchored, absolute QA (three bullets)
    ("P2P5-letpass", "Before any run, write `What would this criterion let pass?` for each acceptance criterion",
     ["src.claude/agents/qa-engineer.md", "src.codex/skills/qa-engineer/SKILL.md"]),
    ("P2P5-oracle", "Anchor expected behavior to a known-good oracle (a shipped release or independent ground truth)",
     ["src.claude/agents/qa-engineer.md", "src.codex/skills/qa-engineer/SKILL.md"]),
    ("P2P5-absolute", "Relative agreement such as ON≈OFF cannot PASS by itself.",
     ["src.claude/agents/qa-engineer.md", "src.codex/skills/qa-engineer/SKILL.md"]),

    # Batch 3 acceptance — role floors augment retained/canonical obligations.
    ("B1-S1-input", "inputs required by the canonical S1 `Receiving-side echo` in `subagent-contracts.md`",
     ["src.claude/agents/qa-engineer.md", "src.codex/skills/qa-engineer/SKILL.md"]),
    ("B1-S1-class-audit", "when the dispatch cited a defect class, the verification report classifies every enumerated participant as `fixed` or `not-affected`.",
     ["src.claude/agents/qa-engineer.md", "src.codex/skills/qa-engineer/SKILL.md"]),
    ("B2-qt-delete-later", "`QObject` deletion uses `deleteLater()` invoked on the object's owning thread; never `delete` a `QObject` with pending events or from a foreign thread",
     ["src.claude/agents/qt-ui-engineer.md", "src.codex/skills/qt-ui-engineer/SKILL.md"]),
    ("B3-model-view-settled-signals", "Model/view-specific settled-signal evidence names the applicable signal—`dataChanged`, `rowsInserted`, or `modelReset`",
     ["src.claude/agents/model-view-engineer.md", "src.codex/skills/model-view-engineer/SKILL.md"]),
    ("B4-geometry-retained-rule", "Prefer explicit treatment of tolerances, degeneracies, and coordinate conventions over implicit behavior.",
     ["src.claude/agents/geometry-engineer.md", "src.codex/skills/geometry-engineer/SKILL.md"]),
    ("B5-visualization-retained-frame", "Make units, color-scale choices, coordinate transforms, and aggregation assumptions explicit.",
     ["src.claude/agents/visualization-engineer.md", "src.codex/skills/visualization-engineer/SKILL.md"]),

    # A2 — parallel-isolation protocol + marker (both operating-models)
    ("A2-declare", "**Declare each requested isolation worktree.**",
     ["src.claude/agents/contracts/operating-model.md", "src.codex/skills/lead/operating-model.md"]),
    ("A2-marker", "# orchestrarium:requested-isolation-worktree",
     ["src.claude/agents/contracts/operating-model.md", "src.codex/skills/lead/operating-model.md"]),
    ("A2-resource-surface", "Parallel lanes are independent only when each lane's mutation set is disjoint from every other lane's read, write, execute, install/copy, and baseline surfaces for the full overlap interval. If a mutation can reach any such surface, serialize the lanes or use explicitly requested, validated isolation.",
     ["shared/references/subagent-operating-model.md", SPINE,
      "src.claude/agents/contracts/operating-model.md",
      "src.codex/skills/lead/operating-model.md"]),
    # A2 — Lead SKILL pointer
    ("A2-pointer", "Apply the installed operating-model parallel-isolation protocol before launch; mutating or Git-using parallel lanes require one requested, cleanup-owned worktree each.",
     ["src.claude/skills/lead/SKILL.md", "src.codex/skills/lead/SKILL.md"]),
    # A2 — hook doc discriminator sentence (installed provider roots + INSTALL)
    ("A2-doc", "warns on every confidently parsed `git worktree add` except one add whose command ends with the exact `# orchestrarium:requested-isolation-worktree` marker required by the installed parallel-isolation protocol; missing, near-match, quoted, reused, or batch markers do not suppress the audit.",
     ["src.claude/CLAUDE.md", "src.codex/AGENTS.codex.md", "INSTALL.md"]),
    # A2 — hook marker constant present in BOTH hook copies
    ("A2-hook-const", 'REQUESTED_ISOLATION_MARKER = "# orchestrarium:requested-isolation-worktree"',
     ["src.claude/agents/hooks/check-no-trash-in-repo.py", "src.codex/skills/lead/hooks/check-no-trash-in-repo.py"]),

    # A5b — hardening invariants 7 and 8 (both review-loop bindings)
    ("A5b-inv7", "**Failed lane is unverified.** Any expected lane that errors, dies, or hits a time/token/usage limit is UNVERIFIED.",
     ["src.claude/agents/contracts/review-loop.md", "src.codex/skills/review-loop/SKILL.md"]),
    ("A5b-inv8", "**Fail-closed aggregation.** A missing/null sub-verdict or findings payload is NOT-clean.",
     ["src.claude/agents/contracts/review-loop.md", "src.codex/skills/review-loop/SKILL.md"]),
    # A5b — invariants-7-8-are-the-runtime-enforcement step (command + codex skill);
    # the validator itself stays dev/CI-only, per the recorded operator directive
    # (RELEASE_NOTES.md, the 2026-06-03 entry "Kept the review-loop ledger validator
    # repo/dev-only — not installed to the global.") that the global install carries no
    # repo-specific dev tooling — this pin deliberately does NOT assert the validator is
    # installed. Cited by stable title, not line number: RELEASE_NOTES.md is append-at-top,
    # so every line number below an insertion point rots on the next release (this comment
    # previously said ":153", which had drifted to :281 by 2026-07-25).
    ("A5b-run", "hardening invariants 7-8 (failed-lane-is-unverified, fail-closed aggregation);",
     ["src.claude/commands/agents-review-loop.md", "src.codex/skills/review-loop/SKILL.md"]),

    # Decision C — reviewer fix-class triage and HOW→VERIFY independence.
    ("fix-class-A-field", "`fix-class: {inline-sufficient | design-decision}`",
     ["src.claude/agents/architecture-reviewer.md",
      "src.codex/skills/architecture-reviewer/SKILL.md",
      "src.claude/agents/security-reviewer.md",
      "src.claude/agents/performance-reviewer.md",
      "src.claude/agents/ux-reviewer.md",
      "src.claude/agents/accessibility-reviewer.md",
      "src.codex/skills/security-reviewer/SKILL.md",
      "src.codex/skills/performance-reviewer/SKILL.md",
      "src.codex/skills/ux-reviewer/SKILL.md",
      "src.codex/skills/accessibility-reviewer/SKILL.md"]),
    ("fix-class-A-advisory", "inline HOW stays advisory (non-binding)",
     ["src.claude/agents/architecture-reviewer.md",
      "src.codex/skills/architecture-reviewer/SKILL.md",
      "src.claude/agents/security-reviewer.md",
      "src.claude/agents/performance-reviewer.md",
      "src.claude/agents/ux-reviewer.md",
      "src.claude/agents/accessibility-reviewer.md",
      "src.codex/skills/security-reviewer/SKILL.md",
      "src.codex/skills/performance-reviewer/SKILL.md",
      "src.codex/skills/ux-reviewer/SKILL.md",
      "src.codex/skills/accessibility-reviewer/SKILL.md"]),
    ("fix-class-A-ratchet", "escalate-only one-way ratchet: inline-sufficient may be reclassified to design-decision, never the reverse",
     ["src.claude/agents/architecture-reviewer.md",
      "src.codex/skills/architecture-reviewer/SKILL.md",
      "src.claude/agents/security-reviewer.md",
      "src.claude/agents/performance-reviewer.md",
      "src.claude/agents/ux-reviewer.md",
      "src.claude/agents/accessibility-reviewer.md",
      "src.codex/skills/security-reviewer/SKILL.md",
      "src.codex/skills/performance-reviewer/SKILL.md",
      "src.codex/skills/ux-reviewer/SKILL.md",
      "src.codex/skills/accessibility-reviewer/SKILL.md"]),
    ("fix-class-A-independence", "HOW→VERIFY independence: VERIFY(F) owner/engine ≠ HOW(F) author",
     ["src.claude/agents/contracts/review-loop.md",
      "src.codex/skills/review-loop/SKILL.md",
      "shared/references/review-loop-methodology.md"]),
    ("fix-class-A-authorexcl", "Author-exclusion for design-class (`fix-class: design-decision`) fixes",
     ["src.claude/agents/contracts/review-loop.md",
      "src.codex/skills/review-loop/SKILL.md",
      "shared/references/review-loop-methodology.md"]),
    ("fix-class-invariant-WHAT", "The WHAT (defect class, failure scenario, severity, evidence, `file:line`) stays the gate-bearing object;",
     ["src.claude/agents/architecture-reviewer.md",
      "src.codex/skills/architecture-reviewer/SKILL.md"]),
    ("fix-class-invariant-S4", "The canonical S4 per-claim verdict vocabulary is `verified` | `failed` | `not-verifiable (with reason)`.",
     ["src.claude/agents/architecture-reviewer.md",
      "src.codex/skills/architecture-reviewer/SKILL.md"]),
    ("fix-class-invariant-loop-to-PASS", "**Loop-to-PASS is the gate, not a preference:**",
     ["src.claude/agents/contracts/review-loop.md",
      "src.codex/skills/review-loop/SKILL.md"]),
    ("fix-class-invariant-distinct-engine", "**Distinct engine:** this lane runs on an engine distinct from the batch's author/implementer",
     ["src.claude/agents/architecture-reviewer.md",
      "src.codex/skills/architecture-reviewer/SKILL.md"]),

    # A8 — defect-class dispatch (both subagent-contracts)
    ("A8-field", "Defect-class inventory:",
     ["src.claude/agents/contracts/subagent-contracts.md", "src.codex/skills/lead/subagent-contracts.md"]),
    ("A8-rule", "**Class-completeness trigger (mandatory):** when a reviewer, bot, or test cites one instance of a defect class",
     ["src.claude/agents/contracts/subagent-contracts.md", "src.codex/skills/lead/subagent-contracts.md"]),

    # A7 — diff-invisible invariants + named regression guard (both subagent-contracts)
    ("A7-inv", "Diff-invisible invariants:",
     ["src.claude/agents/contracts/subagent-contracts.md", "src.codex/skills/lead/subagent-contracts.md"]),
    ("A7-guard", "Named regression guard:",
     ["src.claude/agents/contracts/subagent-contracts.md", "src.codex/skills/lead/subagent-contracts.md"]),
    ("A7-rule", "Before dispatch, fill `Diff-invisible invariants`, `Named regression guard`, and `Dead/superseded code disposition`; `none` is valid only with a one-line reason. When a change supersedes a mechanism, `none` is invalid. An implementation or review handoff with any field omitted is incomplete.",
     ["src.claude/agents/contracts/subagent-contracts.md", "src.codex/skills/lead/subagent-contracts.md"]),

    # A9 — object-axis re-aim trigger (both subagent-contracts); the 2448-char block was a
    # hand-maintained byte-identical mirror with NO drift gate, unlike its five pinned A8/A7
    # siblings. These two pins freeze cross-pack parity AND the deliberate C1-only scope
    # (f1445ce0 narrowed it off the universal form) against a one-pack edit or a re-broadening.
    ("A9-trigger", "**Object-axis trigger (mandatory for C1-based clean verdicts, PRE-verdict).**",
     ["src.claude/agents/contracts/subagent-contracts.md", "src.codex/skills/lead/subagent-contracts.md"]),
    ("A9-scope", "Dispatches and verdicts that do not rely on a C1 assessment owe no object-axis record.",
     ["src.claude/agents/contracts/subagent-contracts.md", "src.codex/skills/lead/subagent-contracts.md"]),

    # A3 — physical-state reconciliation on every lifecycle state change (row + bullet)
    ("A3", "lifecycle state change (create, resume, stage transition, park, close, archive)",
     ["src.claude/agents/contracts/operating-model.md", "src.codex/skills/lead/operating-model.md"]),

    # A9 — GitHub thread HEAD + API rule
    ("A9", "When the user authorizes GitHub review-thread resolution, resolve a thread only after the fix commit is on `HEAD`",
     ["src.claude/commands/agents-review.md", "src.codex/skills/review-changes/SKILL.md"]),

    # A11 — mechanical Lead acceptance
    ("A11", "Lead acceptance is a mechanical completeness gate: confirm the required artifact exists, required fields/evidence are present, approved edits are in place, and configured state/ledger agrees.",
     ["src.claude/skills/lead/SKILL.md", "src.codex/skills/lead/SKILL.md"]),

    # A12 — explicit model/effort per launch
    ("A12", "Every provider-backed run MUST carry the resolved model/profile and effort as explicit launch flags in that invocation, even when they equal configured defaults; never rely on provider config defaults.",
     ["src.claude/agents/contracts/external-dispatch.md", "src.codex/skills/lead/external-dispatch.md"]),

    # P7 — persisted stop-after-current-run (Lead SKILL ONLY, both packs)
    ("P7", "For stop-after-current-run intent, persist the stop across turns, allow only the in-flight run to finish, then stop before any new action.",
     ["src.claude/skills/lead/SKILL.md", "src.codex/skills/lead/SKILL.md"]),

    # A13 — preserve launched runs + choose effort before launch
    ("A13", "Once a provider or subagent run is launched, a later preference change to effort, model, or framing applies to the next dispatch.",
     ["src.claude/agents/contracts/operating-model.md", "src.codex/skills/lead/operating-model.md"]),

    # P8 — writer-owner + settled event (architect return + reviewer gate).
    # The Claude pointer targets skills/architect/SKILL.md (not agents/architect.md): the
    # roles-as-skills curated subset made architect a dual role-skill, and the full role
    # contract — including this P8 sentence — moved into the skill; agents/architect.md is
    # now a thin delegate wrapper that loads the skill. This matches the codex pointer shape,
    # which already targeted skills/architect/SKILL.md.
    ("P8-architect", "the Change-Surface Contract MUST name exactly one writer-owner and one downstream-observable `settled/committed` event. Missing either is `REVISE` at design input.",
     ["src.claude/skills/architect/SKILL.md", "src.codex/skills/architect/SKILL.md"]),
    ("P8-reviewer", "Reject any pipeline touching shared mutable state unless the accepted design names exactly one writer-owner and a downstream-observable `settled/committed` event, and the implementation preserves both.",
     ["src.claude/agents/architecture-reviewer.md", "src.codex/skills/architecture-reviewer/SKILL.md"]),

    # Single-writer orchestration — the root main conversation owns dispatch and lifecycle
    # state; specialists return a bounded result and recommendation without advance authority.
    ("single-writer-root", "Only the root main conversation holding Lead dispatches downstream roles and writes work-item lifecycle state.",
     ["src.claude/agents/contracts/subagent-contracts.md", "src.codex/skills/lead/subagent-contracts.md"]),
    ("single-writer-ledger", "Only the root main conversation holding Lead writes `agent-runs.jsonl`:",
     ["src.claude/agents/contracts/subagent-contracts.md", "src.codex/skills/lead/subagent-contracts.md"]),
    ("single-writer-specialist", "A specialist completes one profession, artifact, and gate; it returns evidence plus an optional non-binding recommended next role to the root, then stops.",
     ["src.claude/agents/contracts/subagent-contracts.md", "src.codex/skills/lead/subagent-contracts.md"]),
    ("single-writer-stop", "A specialist never adopts Lead, launches a peer or downstream stage, advances the pipeline, or writes `agent-runs.jsonl`.",
     ["src.claude/agents/contracts/subagent-contracts.md", "src.codex/skills/lead/subagent-contracts.md"]),
    ("single-writer-wrapper", "The root may directly launch a configured external wrapper; no provider or leaf may recursively launch another wrapper.",
     ["src.claude/agents/contracts/subagent-contracts.md", "src.codex/skills/lead/subagent-contracts.md", "shared/references/subagent-operating-model.md"]),
    ("single-writer-spine", "$lead` is the root main conversation's sole downstream dispatcher and lifecycle writer",
     [SPINE]),
    ("single-writer-shared", "The root main conversation holding Lead alone dispatches downstream roles and writes work-item lifecycle state.",
     ["shared/references/subagent-operating-model.md"]),

    # Review baselines belong to the producing run, not the aggregate worktree.
    ("cross-lane-review-baseline", "Evaluate authored claims and review verdicts against the producing run's declared scope and accepted baseline: later independently owned lane deltas are reviewed in their own lane and do not retroactively falsify the earlier artifact; an actual material revision of the accepted upstream artifact still invalidates dependent `PASS` states and triggers dependent re-review.",
     ["shared/references/subagent-operating-model.md",
      SPINE,
      "src.claude/agents/contracts/subagent-contracts.md",
      "src.codex/skills/lead/subagent-contracts.md",
      "src.claude/agents/architecture-reviewer.md",
      "src.codex/skills/architecture-reviewer/SKILL.md"]),
]

# P7 must NOT be in the spine (synthesis D-spine-P7: spine gets ONLY P4 + A5).
SPINE_MUST_NOT_CONTAIN = [
    ("P7-not-in-spine", "stop-after-current-run intent, persist the stop across turns"),
]


class TestOrchestrationDisciplineContract(unittest.TestCase):
    _cache: dict[str, str] = {}

    def _read(self, rel: str) -> str:
        if rel not in self._cache:
            path = REPO_ROOT / rel
            self.assertTrue(path.is_file(), f"owner file missing: {rel}")
            self._cache[rel] = path.read_text(encoding="utf-8")
        return self._cache[rel]

    def test_normative_sentences_present_in_every_owner(self) -> None:
        for gap_id, substring, owners in PINS:
            for owner in owners:
                with self.subTest(gap=gap_id, owner=owner):
                    text = self._read(owner)
                    self.assertIn(
                        substring, text,
                        f"[{gap_id}] normative sentence missing from {owner}",
                    )

    def test_p7_not_in_spine(self) -> None:
        spine = self._read(SPINE)
        for gap_id, substring in SPINE_MUST_NOT_CONTAIN:
            with self.subTest(gap=gap_id):
                self.assertNotIn(
                    substring, spine,
                    f"[{gap_id}] {substring!r} must NOT be in the spine (P7 is Lead-file-only)",
                )

    def test_quick_fix_handles_the_exact_tool_update_incident(self) -> None:
        spine = self._read(SPINE)
        for clause in (
            "target+steps",
            "bounds",
            "ownership/contracts",
            "no new dependency/risk owner",
            "rollback/backup",
            "oracle",
        ):
            self.assertIn(clause, spine)

        claude_template = json.loads(self._read(CLAUDE_QUICK_FIX_TEMPLATE))
        self.assertFalse(claude_template["requiresLead"])
        self.assertEqual(claude_template["chain"], ["implement", "QA"])

        for owner in ("src.claude/skills/lead/SKILL.md", "src.codex/skills/lead/SKILL.md"):
            text = self._read(owner)
            self.assertLess(text.index("**Classify before full task-memory recovery**"), text.index("**Verify work-items"))
            self.assertIn("route `implementation -> QA`", text)
            self.assertIn("create the minimal `work-items/active/<slug>/status.md`", text)
        self.assertIn("For recovery-tracked `requiresLead: false` chains with 2+ stages (`research`, `review`)",
                      self._read("src.claude/CLAUDE.md"))
        self.assertIn("Evaluate the shared `quick-fix` predicate before invoking a process skill",
                      self._read("src.claude/CLAUDE.md"))

    def test_quick_fix_has_minimal_pre_mutation_recovery_without_heavy_preludes(self) -> None:
        spine = self._read(SPINE)
        self.assertIn(
            "Before mutation create only `work-items/active/<slug>/status.md`",
            spine,
        )
        self.assertIn(
            "Failed/unclear => re-classify/enrich same item",
            spine,
        )

        installed_mirrors = (
            "AGENTS.md",
            "src.codex/AGENTS.codex.md",
            "src.claude/CLAUDE.md",
            "src.codex/skills/lead/SKILL.md",
            "src.claude/skills/lead/SKILL.md",
            "src.codex/skills/lead/subagent-contracts.md",
            "src.claude/agents/contracts/subagent-contracts.md",
        )
        legacy_no_memory_wording = (
            "no task-memory artifact is created",
            "does not enter local task memory unless re-classified",
            "do not enter task-memory recovery",
            "record one line in the current session",
        )
        for owner in installed_mirrors:
            with self.subTest(owner=owner):
                text = self._read(owner)
                self.assertIn("work-items/active/<slug>/status.md", text)
                for legacy in legacy_no_memory_wording:
                    self.assertNotIn(legacy, text)

        expected_minimal_status = [
            "---",
            "template: quick-fix",
            "status: active",
            "started: <YYYY-MM-DD HH:MM>",
            "updated: <YYYY-MM-DD HH:MM>",
            "---",
            "- **Task**: <admitted objective>",
            "- **Current step**: <current execution step>",
            "- **Last result**: <last completed step or admission result>",
            "- **Next action**: <next concrete action>",
        ]
        contracts = (
            "src.codex/skills/lead/subagent-contracts.md",
            "src.claude/agents/contracts/subagent-contracts.md",
        )
        for contract in contracts:
            with self.subTest(contract=contract):
                text = self._read(contract)
                section = text.split("### Quick-fix minimal status.md", 1)[1].split(
                    "### status.md format", 1
                )[0]
                code = section.split("```markdown", 1)[1].split("```", 1)[0]
                self.assertEqual(
                    [line for line in code.splitlines() if line.strip()],
                    expected_minimal_status,
                )
                self.assertIn("keep this work-item and enrich its recovery state", section)
                self.assertIn(
                    "does not add `roadmap.md`, `brief.md`, Research, Design, Plan, consultant, "
                    "pre-implementation review, or a report before its first mutation",
                    section,
                )

        claude_template = json.loads(self._read(CLAUDE_QUICK_FIX_TEMPLATE))
        self.assertIn("minimal quick-fix status.md before the first repository mutation", claude_template["notes"])
        self.assertIn("re-classification enriches the same work-item", claude_template["notes"])
        for role in claude_template["roles"]:
            with self.subTest(role=role):
                self.assertNotEqual(role["agentType"], "analyst")
                self.assertNotEqual(role["agentType"], "consultant")
                self.assertNotIn(
                    role["stage"].lower(),
                    {"research", "design", "plan", "pre-implementation review"},
                )

        for entrypoint in ("src.codex/AGENTS.codex.md", "src.claude/CLAUDE.md"):
            with self.subTest(entrypoint=entrypoint):
                text = self._read(entrypoint)
                self.assertIn(
                    "no recovery file is needed unless that invocation is itself admitted as `quick-fix`",
                    text,
                )
                self.assertIn("this exception does not broaden recovery to trivial questions", text)

    def test_quick_fix_rejects_a_contract_change(self) -> None:
        spine = self._read(SPINE)
        self.assertIn("ownership/contracts", spine)
        self.assertIn("Failed/unclear => re-classify/enrich same item", spine)

    def test_live_shared_references_do_not_restore_the_retired_fast_lane(self) -> None:
        owners = (
            "shared/references/workflow-strategy-comparison.md",
            "shared/references/ru/workflow-strategy-comparison.md",
            "shared/references/spine/delegation-principles.md",
            "shared/references/spine/governance-glossary.md",
            "src.codex/skills/lead/operating-model.md",
            "src.claude/CLAUDE.md",
            "src.claude/agents/team-templates/quick-fix.json",
        )
        for owner in owners:
            with self.subTest(owner=owner):
                text = self._read(owner)
                self.assertNotIn("additive fast lane", text.lower())
                self.assertNotIn("fast lane", text.lower())
                self.assertIn("quick-fix", text.lower())
        self.assertIn(
            "additive impact alone does not admit `quick-fix`",
            self._read("shared/references/workflow-strategy-comparison.md"),
        )


if __name__ == "__main__":
    unittest.main()
