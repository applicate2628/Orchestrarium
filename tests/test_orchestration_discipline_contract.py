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
import re
from pathlib import Path
from policy_text_contract import identifier_present, lexical, relationships, selected_section, selected_unit

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestOwnerEquivalentExecutionContract(unittest.TestCase):
    def test_external_launch_consumers_do_not_retain_helper_monopolies(self):
        retired = {
            "src.codex/skills/lead/external-dispatch.md": (
                "is the only approved Kimi launch surface",
                "Substantive raw provider Command-Line Interface (CLI) prompt routes are unsupported: use",
                "remains the only substantive transport source",
                "engineering through the canonical fixed `kimi-code/k3` wrapper",
            ),
            "src.claude/agents/contracts/external-dispatch.md": (
                "is the only approved Kimi launch surface",
                "Substantive raw provider Command-Line Interface (CLI) prompt routes are unsupported: use",
            ),
            "src.codex/skills/review-loop/SKILL.md": (
                "Every dispatched external angle on a TRACKED work-item uses the approved thin wrapper",
            ),
            "src.claude/commands/agents-review-loop.md": (
                "each external-provider lane uses the approved thin wrapper",
            ),
            "src.claude/CLAUDE.md": (
                "Kimi is explicit-only through the approved thin wrapper",
            ),
        }
        for relative, monopolies in retired.items():
            text = (REPO_ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn("owner-equivalent launch", text)
                for monopoly in monopolies:
                    self.assertNotIn(monopoly, text)
        for relative in tuple(retired)[:2]:
            text = (REPO_ROOT / relative).read_text(encoding="utf-8")
            for preserved in (
                "exact fixed `kimi-code/k3` model", "authentication/capability controls",
                "unchanged file/stdin prompt and governance inputs", "output/resource bounds",
                "timeout/cancellation and real terminal oracle", "never a reserved wrapper frame",
                "task prompts in argv (`kimi --prompt`)",
                "independently invented `--auto` controls remain prohibited",
                "same snapshot and inclusion of the canonical governance projection",
            ):
                with self.subTest(relative=relative, preserved=preserved):
                    self.assertIn(preserved, text)

    def test_manual_equivalence_preserves_data_and_denial_guarantees(self):
        text = (REPO_ROOT / "shared/AGENTS.shared.md").read_text(encoding="utf-8")
        start = text.index("### Assistance and owner-equivalent execution (binding)")
        contract = text[start:text.index("## Artifact persistence", start)]
        for guarantee in (
            "actual inputs/preimages", "exclusive ownership",
            "serialized readers-writers", "canonical schema",
            "rollback/replay protection", "independent persisted readback",
            "owned-resource settlement every exit", "immutable launch/terminal target/role/lane/observed IDs",
            "exact obligations/typed closers", "failed attempt≠result",
            "bound source/destination/link/board pre/post bytes",
            "joint archive/active-absence/disposition/link/receipt/README readback",
            "never impersonated completion frames",
            "No new scope/host-denial bypass/retry",
            "No new scope/host-denial bypass/retry/external-only-to-native switch/corridor/model/commission weakening",
            "No new scope/host-denial bypass/retry/external-only-to-native switch/corridor/model/commission weakening/trust-publication bypass/human-review replacement",
        ):
            with self.subTest(guarantee=guarantee):
                self.assertIn(guarantee, contract)
        self.assertNotIn("only via the validated public ledger writer", text)

    def test_lifecycle_and_launch_projections_apply_one_shared_contract(self):
        for relative in (
            "src.codex/skills/lead/SKILL.md", "src.claude/skills/lead/SKILL.md",
            "src.codex/skills/lead/subagent-contracts.md",
            "src.claude/agents/contracts/subagent-contracts.md",
            "src.codex/skills/lead/external-dispatch.md",
            "src.claude/agents/contracts/external-dispatch.md",
        ):
            with self.subTest(relative=relative):
                text = (REPO_ROOT / relative).read_text(encoding="utf-8")
                self.assertIn("Assistance and owner-equivalent execution (binding)", text)
                self.assertNotIn("Lead never manually recontextualizes a bug", text)
                self.assertNotIn("a failed append stops scheduling", text)

SPINE = "shared/AGENTS.shared.md"
CLAUDE_QUICK_FIX_TEMPLATE = "src.claude/agents/team-templates/quick-fix.json"
CLAUDE_RESEARCH_TEMPLATE = "src.claude/agents/team-templates/research.json"

HANDOFF_CONTRACTS = (
    "src.codex/skills/lead/subagent-contracts.md",
    "src.claude/agents/contracts/subagent-contracts.md",
)

IMPLEMENTATION_PROFESSIONS = (
    "backend-engineer",
    "frontend-engineer",
    "qt-ui-engineer",
    "model-view-engineer",
    "data-engineer",
    "platform-engineer",
    "toolchain-engineer",
    "geometry-engineer",
    "graphics-engineer",
    "visualization-engineer",
)

IMPLEMENTATION_PROFESSION_FILES = tuple(
    path
    for role in IMPLEMENTATION_PROFESSIONS
    for path in (
        f"src.codex/skills/{role}/SKILL.md",
        f"src.claude/agents/{role}.md",
    )
)

FACT_ROUTING_FRAGMENTS = (
    "Standalone bounded fact lookup is answered inline with no artifact.",
    "defaults to one `$analyst`",
    "recovery only when continuation is needed",
    "explicitly user-named role or narrower factual domain specialist remains valid",
    "Architecture Decision Record (ADR)",
    "add `$planner` only when the user explicitly requests an execution plan",
)
SIDE_QUESTION_CONTINUITY_FRAGMENTS = (
    "answer brief questions in commentary",
    "promptly delegate eligible substantive admitted side work",
    "continue the next ready primary action in the same turn without waiting for its result",
    "existing authority, capacity, full resource surfaces, gates",
    "explicit user/manual/native holds",
)
HANDOFF_ACCEPTANCE_ECHO_FRAGMENTS = (
    "same accepted `Acceptance criteria` and `Named regression guard`",
    "guard's expected and observed result",
    "do not add a Primary Acceptance Oracle identifier, status field, ledger field, or file",
)
STATUS_ACCEPTANCE_CARRIER_FRAGMENTS = (
    "quick-fix writes the objective in `Task`",
    "criteria and guard reference in `Last result`",
    "Quality Assurance (QA) in `Next action`",
    "the oracle in `Evidence gate`",
)

# Per-gap owner inventory. Unchanged owners retain exact sentence pins;
# the selected shared-spine rows use named structural duty predicates.
# (gap-id, sentence pin or None for a structural shared duty, [owner files])
PINS = [
    # Repository-orientation Bootstrap checkpoint — both installed provider roots.
    ("orientation-a0", "**(a0) Pre-action orientation trigger**",
     ["src.codex/AGENTS.codex.md"]),
    ("orientation-step0", "0. **Repository orientation.**",
     ["src.codex/AGENTS.codex.md"]),
    ("orientation-record", "REPOSITORY ORIENTATION: scope=<repo-relative path>; status=<live|mutable|frozen|archived|deprecated|superseded|conflict>; workflow=<repo-relative entry point(s)>; protected=<repo-relative path(s)|none>; evidence=<path:line[,path:line...]>",
     [SPINE]),
    ("orientation-referral", "Apply shared **Repository orientation; Mechanism inventory before new paths**, including its exact `REPOSITORY ORIENTATION:` record and `file:line` evidence.",
     ["src.codex/AGENTS.codex.md"]),
    ("orientation-violation", "Missing/conflicting authority is `status=conflict`: no run/build/edit until the owner or user resolves it.",
     ["src.codex/AGENTS.codex.md"]),

    # P4 — spine stop-rule (Fable probe text) + operational bullet (Sol text)
    ("P4-spine", None, [SPINE]),
    ("P4-op", "**Second-cross-break stop:** If a second fix in the same session breaks a previously working neighbor, STOP all edits.",
     ["src.claude/commands/agents-bugfix.md", "src.codex/skills/bug-hunting/SKILL.md"]),

    # A5 — shared dead-lane and missing-verdict duties
    ("A5-spine", None, [SPINE]),

    # P3 — N independent roots (both bug-hunting SKILLs)
    ("P3", "When N symptoms or failing cases are reported, keep N independent root hypotheses",
     ["src.claude/skills/bug-hunting/SKILL.md", "src.codex/skills/bug-hunting/SKILL.md"]),

    # P2+P5 — oracle-anchored, absolute QA (three bullets)
    ("P2P5-letpass", "Before any run, challenge each acceptance criterion with a falsifying case and its required property; if the criterion admits the known failure or a degenerate result, return `REVISE` with that evidence to the acceptance owner instead of rewriting accepted success semantics.",
     ["src.claude/agents/qa-engineer.md", "src.codex/skills/qa-engineer/SKILL.md"]),
    ("P2P5-oracle", "Anchor expected behavior to a known-good oracle (a shipped release or independent ground truth)",
     ["src.claude/agents/qa-engineer.md", "src.codex/skills/qa-engineer/SKILL.md"]),
    ("P2P5-absolute", "Relative agreement such as ON≈OFF cannot PASS by itself.",
     ["src.claude/agents/qa-engineer.md", "src.codex/skills/qa-engineer/SKILL.md"]),

    # Batch 3 acceptance — role floors augment retained/canonical obligations.
    ("B1-S1-input", "inputs required by the canonical S1 `Receiving-side echo` in `subagent-contracts.md`",
     ["src.claude/agents/qa-engineer.md", "src.codex/skills/qa-engineer/SKILL.md"]),
    ("B1-S1-class-audit", "actual defects outside admitted scope must be reported as `out-of-scope` or `unresolved`, never `not-affected`",
     ["src.claude/agents/qa-engineer.md", "src.codex/skills/qa-engineer/SKILL.md"]),
    ("F2-receiving-classification", "actual defects outside admitted scope must be reported as `out-of-scope` or `unresolved`, never `not-affected`",
     list(HANDOFF_CONTRACTS)),
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
     ["shared/references/subagent-operating-model.md",
      "src.claude/agents/contracts/operating-model.md",
      "src.codex/skills/lead/operating-model.md"]),
    ("A2-resource-spine", None, [SPINE]),
    # A2 — Lead SKILL pointer
    ("A2-pointer", "Apply the installed operating-model parallel-isolation protocol before launch; mutating or Git-using parallel lanes require one requested, cleanup-owned worktree each.",
     ["src.claude/skills/lead/SKILL.md", "src.codex/skills/lead/SKILL.md"]),
    # A2 — hook audit owner (Codex Lead procedure + INSTALL); the root referral is tested below.
    ("A2-doc", "warns on every confidently parsed `git worktree add` except one add whose command ends with the exact `# orchestrarium:requested-isolation-worktree` marker required by the installed parallel-isolation protocol; missing, near-match, quoted, reused, or batch markers do not suppress the audit.",
     ["src.codex/skills/lead/operating-model.md", "INSTALL.md"]),
    ("A2-doc-claude", "The worktree audit recognizes only an exact trailing `# orchestrarium:requested-isolation-worktree` marker.",
     ["src.claude/CLAUDE.md"]),
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
    ("fix-class-A-ratchet", "architecture-reviewer's current evidence-based classification/reclassification contract",
     ["src.claude/agents/security-reviewer.md",
      "src.claude/agents/performance-reviewer.md",
      "src.claude/agents/ux-reviewer.md",
      "src.claude/agents/accessibility-reviewer.md",
      "src.codex/skills/security-reviewer/SKILL.md",
      "src.codex/skills/performance-reviewer/SKILL.md",
      "src.codex/skills/ux-reviewer/SKILL.md",
      "src.codex/skills/accessibility-reviewer/SKILL.md"]),
    ("fix-class-A-reclassification", "Reverse classification is permitted only by the original tagging reviewer or owning architect with cited resolution or disproof of the original trigger, a fixed owner/seam, a named guard, and no current trigger; an implementer or Lead cannot waive an actual mandatory gate.",
     ["src.claude/agents/architecture-reviewer.md",
      "src.codex/skills/architecture-reviewer/SKILL.md"]),
    ("fix-class-A-current-trigger5", "(5) current sibling investigation leaves scope, owner, or repair uncertainty unresolved;",
     ["src.claude/agents/architecture-reviewer.md",
      "src.codex/skills/architecture-reviewer/SKILL.md"]),
    ("fix-class-A-f3", "Vague unsupported doubt alone adds no new gate; missing required evidence or risk is not silently waived.",
     ["src.claude/skills/lead/SKILL.md", "src.codex/skills/lead/SKILL.md"]),
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
    ("fix-class-invariant-independent-review", None,
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
    ("A7-rule", "Before dispatch, fill `Diff-invisible invariants`, `Named regression guard`, `Dead/superseded code disposition`, and `Cleanup disposition`. For `Dead/superseded code disposition`, `none` is valid only with a one-line reason. When a change supersedes a mechanism, `none` is invalid. For `Cleanup disposition`, `preserved` requires a reason and `none` means the recipient owns no resource in that category. An implementation or review handoff with any field omitted is incomplete.",
     ["src.claude/agents/contracts/subagent-contracts.md", "src.codex/skills/lead/subagent-contracts.md"]),

    # Resource cleanup ownership — shared lifecycle invariant plus one exact field/echo in both packs.
    ("cleanup-spine", None,
     [SPINE]),
    ("cleanup-echo", "report the Cleanup disposition for owned child process trees, temp/capture paths, and isolation worktrees as `cleaned`, `preserved` with its reason, or `none`",
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

    # A9 — GitHub thread hosted-head owner rule
    ("A9", "Delegate authorized GitHub review-thread resolution to `$github-pr-review-bot`",
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

    # P8 — writer-owner + conditionally required settlement observation.
    # Architect has one universal role-contract body. Claude routing authority remains in
    # CLAUDE.md and agents/architect.md; neither surface duplicates this P8 contract.
    ("P8-architect", "For every pipeline touching shared mutable state (for example scroll, geometry, or cache), the Change-Surface Contract MUST name exactly one writer-owner. When another consumer observes or reconciles after the writer returns, the owning contract MUST expose authoritative settled state independently through an event, callback/future, versioned query, or equivalent; an ordinary synchronous return is sufficient for the sole caller. Missing the writer-owner or required settlement observation is `REVISE` at design input.",
     ["src.codex/skills/architect/SKILL.md"]),
    ("P8-reviewer", "Reject any pipeline touching shared mutable state unless the accepted design names exactly one writer-owner. When another consumer observes or reconciles after the writer returns, require independent observation of authoritative settled state through the owning contract; an event, callback/future, versioned query, or equivalent may satisfy it, while an ordinary synchronous return is sufficient for the sole caller. Verify the implementation preserves the writer-owner, required observation, and cross-surface convergence.",
     ["src.claude/agents/architecture-reviewer.md", "src.codex/skills/architecture-reviewer/SKILL.md"]),

    # Single-writer orchestration — the root main conversation owns dispatch and lifecycle
    # state; specialists return a bounded result and recommendation without advance authority.
    ("single-writer-root", "Only the root main conversation holding Lead dispatches downstream roles and writes work-item lifecycle state.",
     ["src.claude/agents/contracts/subagent-contracts.md", "src.codex/skills/lead/subagent-contracts.md"]),
    ("single-writer-ledger", "Only the root main conversation holding Lead writes `agent-runs.jsonl`:",
     ["src.claude/agents/contracts/subagent-contracts.md"]),
    ("root-owned-ledger", None, ["src.codex/skills/lead/subagent-contracts.md"]),
    ("single-writer-specialist", "A specialist completes one profession, artifact, and gate; it returns evidence plus an optional non-binding recommended next role to the root, then stops.",
     ["src.claude/agents/contracts/subagent-contracts.md", "src.codex/skills/lead/subagent-contracts.md"]),
    ("single-writer-stop", "A specialist never adopts Lead, launches a peer or downstream stage, advances the pipeline, or writes `agent-runs.jsonl`.",
     ["src.claude/agents/contracts/subagent-contracts.md", "src.codex/skills/lead/subagent-contracts.md"]),
    ("single-writer-wrapper", "The root may directly launch a configured external wrapper; no provider or leaf may recursively launch another wrapper.",
     ["src.claude/agents/contracts/subagent-contracts.md", "src.codex/skills/lead/subagent-contracts.md", "shared/references/subagent-operating-model.md"]),
    ("single-writer-spine", None,
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

    # Batch B — route-appropriate handoffs and fixed-value criteria.
    ("batch-b-hardcoding", None,
     [SPINE, "shared/external-prompt-governance.md"]),
    ("batch-b-implementation-route", "Implementation and Quality Assurance receive route-appropriate accepted artifacts; a Plan is required only when the selected route admits a Plan stage.",
     ["src.claude/agents/contracts/subagent-contracts.md", "src.codex/skills/lead/subagent-contracts.md"]),
    ("batch-b-qa-input", "Require the accepted artifact for the selected route, the implementation artifact being tested, any relevant specialist constraints, and the inputs required by the canonical S1 `Receiving-side echo` in `subagent-contracts.md`. A Plan is required only when the selected route admits a Plan stage.",
     ["src.claude/agents/qa-engineer.md", "src.codex/skills/qa-engineer/SKILL.md"]),
    ("batch-b-external-review", "Require the approved reviewable artifact (implementation, governance/control-plane change, plan, or other routed artifact) to review.",
     ["src.claude/agents/external-reviewer.md", "src.codex/skills/external-reviewer/SKILL.md"]),
    ("batch-b-analyst-taxonomy", "If a research admission gate fails without a real external prerequisite, return `REVISE` or `rejected` with the failed gate; reserve `BLOCKED` for a real external prerequisite.",
     ["src.claude/skills/analyst/SKILL.md", "src.codex/skills/analyst/SKILL.md"]),
    ("batch-b-analyst-adjacent-blocker", "If a real external prerequisite blocks the current task, return `BLOCKED:prerequisite` instead of working around it.",
     ["src.claude/skills/analyst/SKILL.md", "src.codex/skills/analyst/SKILL.md"]),
    ("batch-b-resource-free", "When no resource is selected, Cleanup disposition is `none` and no `ResourceRowV1` is required; do not invent a row.",
     ["src.claude/agents/contracts/subagent-contracts.md", "src.codex/skills/lead/subagent-contracts.md"]),
    ("batch-b-inline-alternative", "For an `inline-sufficient` finding with one dominant correction, report `material alternative: none`.",
     ["src.claude/agents/architecture-reviewer.md", "src.codex/skills/architecture-reviewer/SKILL.md"]),
    ("batch-b-planner-criteria", "Derive each acceptance criterion from the accepted contract or oracle; write it as an absolute observable assertion with the contract/oracle's value, count, order, or invariant. Do not invent literals.",
     ["src.claude/skills/planner/SKILL.md", "src.codex/skills/planner/SKILL.md"]),
]

# P7 must NOT be in the spine (synthesis D-spine-P7: spine gets ONLY P4 + A5).
SPINE_MUST_NOT_CONTAIN = [
    ("P7-not-in-spine", "stop-after-current-run intent, persist the stop across turns"),
]

DYNAMIC_ADMISSION_OWNERS = (
    "src.claude/skills/lead/SKILL.md",
    "src.codex/skills/lead/SKILL.md",
    "src.claude/agents/contracts/operating-model.md",
    "src.codex/skills/lead/operating-model.md",
    "shared/references/subagent-operating-model.md",
    "shared/references/ru/subagent-operating-model.md",
)

DYNAMIC_ADMISSION_CLAUSES = (
    "A lane is ready only when its approved inputs and external prerequisites are accepted",
    "largest useful pairwise-compatible subset",
    "priority, critical-path or unblocking value, mandatory risk coverage, marginal benefit, merge cost, and pairwise resource isolation",
    "`parallelMode: force` requires eligible refill; it does not require maximum fan-out",
    "When the runtime exposes free capacity, treat that current value as authoritative.",
    "launch one ranked candidate at a time until the runtime explicitly refuses capacity; never infer or cache a numeric concurrency cap",
    "Recompute admission after every launch and every lane-settled event.",
    "Completed, `BLOCKED`, cancelled, and parked lanes release capacity",
    "refill in the same turn unless a stop condition, human gate, integration conflict, or nonpositive marginal benefit prevents it",
    "A waiting or long-running lane does not head-of-line block independent ready work.",
    "waiting on an external prerequisite is parked or closed with a durable recovery point",
    "Integration-owner and shared integration-surface work is serialized.",
)

PLAN_CHECKPOINT_LEAD_OWNERS = (
    "src.claude/skills/lead/SKILL.md",
    "src.codex/skills/lead/SKILL.md",
)
PLAN_CHECKPOINT_PLANNER_OWNERS = (
    "src.claude/skills/planner/SKILL.md",
    "src.codex/skills/planner/SKILL.md",
)

RUSSIAN_DYNAMIC_ADMISSION_CLAUSES = (
    "Lane готова только когда её approved inputs и external prerequisites приняты",
    "largest useful pairwise-compatible subset",
    "priority, critical-path или unblocking value, mandatory risk coverage, marginal benefit, merge cost и pairwise resource isolation",
    "`parallelMode: force` требует eligible refill; это не требование maximum fan-out",
    "Если runtime показывает free capacity, считайте текущее значение authoritative.",
    "запускайте по одному ranked candidate до явного capacity refusal от runtime; никогда не выводите и не кэшируйте numeric concurrency cap",
    "Пересчитывайте admission после каждого запуска и каждого lane-settled event.",
    "Completed, `BLOCKED`, cancelled и parked lanes освобождают capacity",
    "пополняйте capacity в том же turn, если этому не мешают stop condition, human gate, integration conflict или неположительный marginal benefit",
    "Waiting или long-running lane не должна head-of-line блокировать независимую ready work.",
    "ожидающая external prerequisite, переводится в parked или closed с durable recovery point",
    "Integration-owner и работа с shared integration surface выполняются последовательно.",
)

SHARED_MODEL_EFFORT_TRUTH = (
    "Model and effort truth comes only from route-authoritative evidence; never infer "
    "either value from a role name, provider name, or requested profile. When actual "
    "runtime metadata is absent, record `unspecified by runtime`."
)

def evidence_duties(text: str) -> dict[str, bool]:
    unit = selected_unit(text, "Verification and decision discipline", "Evidence-based completion:")
    duties = relationships(unit, {
        "dead-lane-unverified": "Errored/died/limit-hit lane is UNVERIFIED: re-dispatch/report",
        "missing-verdict-rejection": "missing verdict NOT-clean (fail-closed)",
    })
    duties["dead-lane-unverified"] &= identifier_present(unit, "UNVERIFIED")
    return duties


def cleanup_duties(text: str) -> dict[str, bool]:
    unit = selected_unit(text, "Operational and environment safety", "Resource lifecycle hygiene:")
    termination = "Termination requires creator-retained process/Job handles or equivalent stable identity-bound ownership"
    return relationships(unit, {
        "all-exit-release": "Release owned resources on success/failure/cancellation/timeout",
        "retained-termination-owner": termination,
        "identifier-only-termination-refused": termination + ", never PID/ParentProcessId ancestry alone",
    })


def complete_shared_relationships(unit: str, required: dict[str, str]) -> dict[str, bool]:
    """Pin complete changed shared clauses; a weakening suffix is not the duty."""
    normalized = lexical(re.sub(r"^\s*(?:[-*]|\d+[.)]) ", "", unit))
    return {
        name: bool(re.search(
            r"(?:\A|[.;]\s+)" + re.escape(lexical(phrase)) + r"(?=$|[.;](?:\s|$))",
            normalized,
        ))
        for name, phrase in required.items()
    }


def baseline_duties(text: str) -> dict[str, bool]:
    unit = selected_unit(text, "Core delegation principles", "PASS advances;")
    duties = complete_shared_relationships(unit, {
        "producing-scope-baseline": "Verdicts bind producing scope/baseline, later independent deltas get own review",
        "independent-delta-review": "Verdicts bind producing scope/baseline, later independent deltas get own review",
        "material-upstream-invalidation": "material upstream change invalidates dependent PASS",
    })
    economy = selected_unit(text, "Core delegation principles", "Workflow economy (binding):")
    duties.update(complete_shared_relationships(economy, {
        "affected-re-review": "Re-review finding/delta only; full only new defect class/material upstream revision",
    }))
    material_clauses = [
        clause for clause in re.split(r"[.;]\s+", unit)
        if lexical(clause).startswith("material upstream change")
    ]
    duties["material-upstream-invalidation"] &= any(
        identifier_present(clause.rstrip("."), "PASS") for clause in material_clauses
    )
    return duties


def quick_fix_duties(text: str) -> dict[str, bool]:
    unit = selected_unit(text, "Core delegation principles", "quick-fix:")
    admitted = "target/steps/bounds/owner/contracts, no new dependency/risk owner, rollback/backup/oracle"
    duties = complete_shared_relationships(unit, {
        "bounded-admission": admitted,
        "minimal-recovery": "Before mutation only work-items/active/<slug>/status.md with lifecycle+4 recovery facts",
        "no-heavy-preludes": "no roadmap/brief/Research/Design/Plan/consultant/pre-review",
        "same-item-reclassification": "Failed/unclear: enrich/reclassify same item",
        "bounded-delivery": "One preflight, implement/QA, close/archive",
    })
    recovery_clauses = [
        clause for clause in re.split(r"[.;]\s+", unit)
        if lexical(clause).startswith("before mutation only")
    ]
    duties["minimal-recovery"] &= len(recovery_clauses) == 1 and identifier_present(
        recovery_clauses[0], "work-items/active/<slug>/status.md"
    )
    return duties


def stop_rule_duties(text: str) -> dict[str, bool]:
    unit = selected_unit(text, "Scope and ownership discipline", "No logic duplication / no fix layering:")
    return complete_shared_relationships(unit, {
        "second-cross-break-stop": "SECOND same-session fix breaking a working neighbor: STOP all edits",
        "owner-siblings-contract-diagnosis": "diagnose owner/siblings/shared contract",
    })


def isolation_duties(text: str) -> dict[str, bool]:
    unit = selected_unit(text, "Operational and environment safety", "Parallel resource-surface isolation:")
    return complete_shared_relationships(unit, {
        "full-overlap-surfaces": "parallel independence requires each lane's mutations disjoint from others' read/write/execute/install/copy/baseline surfaces throughout overlap",
        "conflict-serialization-or-isolation": "Otherwise serialize or use explicitly requested validated isolation",
        "safe-read-only-or-disjoint-work": "Read/read and truly disjoint work are safe",
        "observed-test-surfaces": "tests declare executed/installed/copied source/helpers as observed surfaces",
    })


def lead_dispatch_duties(text: str) -> dict[str, bool]:
    unit = selected_unit(text, "Core delegation principles", "$lead:")
    duties = complete_shared_relationships(unit, {
        "root-only-dispatch-and-lifecycle": "root main conversation alone dispatches/writes lifecycle",
        "no-specialist-or-delivery-owner": "never subagent/end-to-end coder/roadmap owner",
    })
    owner = selected_unit(text, "Core delegation principles", "$lead")
    duties["root-only-dispatch-and-lifecycle"] &= identifier_present(owner, "$lead")
    return duties


def fixed_value_duties(text: str, *, projection: bool = False) -> dict[str, bool]:
    # The generated external-prompt projection is a headingless bullet list.
    # Select its actual named bullet, not an arbitrary phrase elsewhere in it.
    section = "Provider projection" if projection else "Scope and ownership discipline"
    if projection:
        text = "# Provider projection\n" + text
    unit = selected_unit(text, section, "Anti-hardcoding and justified limits:")
    return complete_shared_relationships(unit, {
        "classify-invariants": "Before changing classify: invariants/protocol/schema may stay fixed",
        "single-owned-safe-defaults": "policy defaults need one owner/omission safety",
        "variable-input-tests": "deployment/calibration/user inputs need variability/omission tests",
    })


def independent_review_duties(text: str) -> dict[str, bool]:
    unit = selected_unit(text, "Anti-layering audit (multi-fix batch)", "Independent review:")
    clauses = {
        "nonauthoring-reviewer": "this lane supplies a substantive assessment from a nonauthoring reviewer.",
        "required-commission": "Apply the shared commission rule when that commission is required;",
        "qualified-model-preference": "prefer a different supported model selection where admissible, but missing actual identity or unproved model-family diversity alone is not a veto.",
        "task-and-host-restrictions": "Preserve any explicit task-specific engine requirement and actual host rejection or execution drift.",
    }
    duties = relationships(unit, clauses)
    # Check the complete current owner unit, not prefixes that allow exceptions
    # or an unchecked contrary sentence. Formatting remains non-semantic.
    duties["complete-owner-unit"] = lexical(unit) == lexical(" ".join(clauses.values()))
    return duties


def root_ledger_duties(text: str) -> dict[str, bool]:
    unit = selected_unit(text, "agent-runs.jsonl format", "Only the root main conversation holding Lead owns")
    clauses = {
        "root-ownership": "Only the root main conversation holding Lead owns agent-runs.jsonl.",
        "actual-root-execution": "Root records actual native and already-admitted declared direct external owner-equivalent executions;",
        "bounded-wrapper-delegation": "an actual supported tracked provider wrapper may write its own pair on Root's behalf.",
        "specialist-no-append": "Specialists never append.",
        "direct-external-contract": "Direct external execution remains under [the external-dispatch contract](external-dispatch.md);",
        "actual-wrapper-evidence": "wrapper-specific envelopes and identifiers apply only when that wrapper actually ran.",
    }
    duties = relationships(unit, clauses)
    duties["root-ownership"] &= identifier_present(unit, "agent-runs.jsonl")
    duties["complete-owner-unit"] = lexical(unit) == lexical(" ".join(clauses.values()))
    return duties


SHARED_DUTY_CHECKS = {
    "A5-spine": evidence_duties,
    "cleanup-spine": cleanup_duties,
    "cross-lane-review-baseline": baseline_duties,
    "P4-spine": stop_rule_duties,
    "A2-resource-spine": isolation_duties,
    "single-writer-spine": lead_dispatch_duties,
}


def _native_contradiction(unit: str) -> bool:
    # Refuse explicit contrary actor/action relations in the complete selected clause.
    # This is bounded lexical checking, not interpretation of arbitrary prose.
    return any(re.search(pattern, lexical(unit)) for pattern in (
        r"\bgeneric (?:fallback(?: toml)?|(?:default )?carrier) (?:binds|declares|requires|must declare) (?:a |the )?(?:fixed )?(?:model|effort|profile)\b",
        r"\b(?:every|all) (?:codex )?native (?:role )?tomls (?:must )?declare (?:a )?(?:fixed|installed default) profile\b",
        r"\bbare default calls (?:guarantee|always use) (?:the )?policy tuple\b",
        r"\brequested profile (?:proves|confirms) (?:the )?actual runtime (?:model|effort)\b",
    ))


def native_route_duties(text: str) -> dict[str, bool]:
    # Ordinary invocations use a selected explicit tuple, not the historical
    # fixed named-role route. Keep configuration, policy and runtime truth apart.
    unit = selected_unit(text, "Native Astra task-dependent route", "For ordinary native and skill-only roles,")
    requested = "The caller invokes the native host tool, records requested and resolved controls separately from actual runtime metadata"
    missing = requested + ", treats missing actual metadata as unspecified by runtime"
    duties = relationships(unit, {
        "ordinary-selectors": "For ordinary native and skill-only roles, callers first use describe_ordinary_native_role_options, then resolve_ordinary_native_dispatch",
        "task-profile-membership": "Ordinary admission requires an eligible task-role pair and exact task/role profile membership, followed by host filtering",
        "conscious-selection": "The caller evaluates task scope, uncertainty, expected cost and rework, then consciously selects and supplies both model and effort when deciding by task, including when choosing the suggestion",
        "omitted-explicit-default": "An omitted pair remains compatible and resolves to an explicit default pair",
        "tuple-validation": "Resolution checks the resulting tuple against task, role, host and configured controls",
        "generic-explicit-route": 'Each admitted ordinary invocation uses a generic spawn with fork_turns="none" and no agent_type and carries the selected profession instructions',
        "bare-default-inheritance": "A direct bare agent_type=default call without a tuple instead inherits provider subagent defaults or parent settings",
        "policy-tuple-selector": "policy-requiring callers use the ordinary selector",
        "custom-pin-no-bypass": "Omitting the type alone does not bypass higher-precedence model/effort fields in a custom default carrier",
        "custom-pin-local-conflict": "a known conflicting pin is a configuration conflict for that invocation, not universal model unavailability",
        "complete-custom-controls": "Genuine custom controls must form a complete configured tuple under existing task/role/profile and individual exact-launch Astra/Max approval",
        "partial-controls-unresolved": "partial controls remain unresolved rather than being filled from factory defaults",
        "custom-bytes-preserved": "The user owns compatible configuration bytes and descriptions, which the installer preserves without reserializing TOML",
        "full-host-discovery": "Reported model, effort, and agent-type lists must reflect the full availability actually enumerated by current host discovery, never a desired-model pre-filter that hides alternatives",
        "generic-capability-unknown": "Absent lists mean capability-unknown, while generic ordinary invocations name no required agent type",
        "selector-nonexecution": "The selector launches nothing",
        "requested-vs-actual": requested,
        "missing-actual": missing,
        "drift-refusal": missing + ", and treats host rejection or returned model/effort drift as nonauthorizing with no fallback",
    })
    duties["exact-route-identifiers"] = all(identifier_present(unit, atom) for atom in (
        "describe_ordinary_native_role_options", "resolve_ordinary_native_dispatch", "fork_turns", "agent_type", "unspecified by runtime",
    ))
    duties["no-contrary-route"] = not _native_contradiction(unit)
    return duties


def native_consumer_duties(text: str, section: str, marker: str, *, referral_only: bool = False, reference: bool = False) -> dict[str, bool]:
    unit = selected_unit(text, section, marker)
    duties = relationships(unit, {
        "actual-override-evidence": "Claim an override only when the host explicitly supports it and returned actual runtime metadata confirms the effective model and effort; otherwise record unspecified by runtime",
    })
    if referral_only:
        duties.update(relationships(unit, {
            "profile-policy-owner": "role policy owns exact profile membership and separate special-corridor/explicit-profile rules",
            "qualified-defaults": "Fixed native defaults are candidates rather than blanket authority when an explicit generic policy-admissible profile is available",
            "authoritative-referral": "For the Codex native-host path, apply Native Astra task-dependent route in the sibling operating-model.md under the installed AGENTS native-dispatch kernel; do not restate or widen that owner here",
        }))
    else:
        duties.update(relationships(unit, {
            "profile-policy-owner": (
                "Role policy owns exact profile membership and separate special-corridor/explicit-profile rules"
                if reference else "Role policy still owns every effort floor and corridor"
            ),
            "ordinary-discovery": "Ordinary discovery presents admissible choices and a default suggestion",
            "conscious-selection": (
                "The caller evaluates task fit, honors genuine current custom controls, and consciously selects and supplies both model and effort when deciding by task, including when choosing the suggestion"
                if reference else
                "Lead evaluates task scope, uncertainty, expected cost and rework and consciously selects and supplies both model and effort when deciding by task, including when choosing the suggestion"
            ),
            "omitted-explicit-default": "An omitted pair remains compatible and resolves to an explicit default pair",
            "bare-default-inheritance": "Direct bare default calls inherit provider/parent settings instead; policy-requiring callers use the selector",
            "authoritative-referral": "the installed Native Astra task-dependent route owns explicit-tuple and custom-pin conflict semantics",
        }))
    duties["actual-metadata-identifier"] = identifier_present(unit, "unspecified by runtime")
    duties["no-contrary-route"] = not _native_contradiction(unit)
    return duties

CLAUDE_MODEL_EFFORT_TRUTH = (
    "Claude internal Agent model and effort are host-selected; role definitions declare "
    "no fixed model, effort, or floor. Unless returned actual runtime metadata proves "
    "the effective values, record `unspecified by runtime`."
)

DYNAMIC_FORCE_PARITY = (
    (
        "force makes eligible-ready refill a standing instruction",
        "`force` делает пополнение `eligible-ready` lanes постоянным указанием",
    ),
    (
        "marginal benefit stays positive",
        "`marginal benefit` положителен",
    ),
    (
        "merge cost plus resource isolation permit another launch",
        "`merge cost` вместе с `resource isolation` допускают ещё один запуск",
    ),
    (
        "completed, `BLOCKED`, and parked lanes trigger refill",
        "`completed`, `BLOCKED` и `parked` lanes запускают пополнение",
    ),
    (
        "force never means always-max fan-out",
        "`force` никогда не означает `always-max` fan-out",
    ),
)

STALE_PASS_FORWARD_FIXTURE = {
    "dispatch": {
        "task_identity": "handoff-current",
        "scope": "current-scope",
        "expected_artifact": "current-result.md",
    },
    "returned_prior_pass": {
        "task_identity": "handoff-previous",
        "scope": "previous-scope",
        "expected_artifact": "previous-result.md",
        "gate": "PASS",
    },
}

ARCHIVED_SUCCESSOR_FORWARD_FIXTURE = {
    "accepted_snapshot": {
        "stable_identifier": "external-successor-001",
        "sha256": "a" * 64,
        "root": "current",
    },
    "qa_lookup": {
        "stable_identifier": "external-successor-001",
        "matches": [
            {
                "root": "archive/2026-09",
                "source_relation": "source-bug-001",
                "lifecycle": "terminal",
            }
        ],
    },
}


def codex_hook_referral_duties(text: str) -> dict[str, bool]:
    unit = selected_unit(text, "Codex hook requirements and mandatory procedure", "Mandatory read:")
    clauses = {
        "mandatory-owner-and-triggers": "Any actor, regardless of profession, who installs, upgrades, removes, or changes Codex hooks; handles hook trust or health; or diagnoses behavior based on hook contracts MUST read the Codex hook procedure in the existing Lead operating-model",
        "resolved-source-or-installed-path": "Resolve Source or installed Lead paths through existing role-path and installation contracts",
        "no-guessed-machine-path": "do not guess machine paths",
        "bounded-trigger": "Unrelated work does not require this procedure",
    }
    duties = relationships(unit, clauses)
    expected = (
        clauses["mandatory-owner-and-triggers"] + ". "
        + clauses["resolved-source-or-installed-path"] + "; "
        + clauses["no-guessed-machine-path"] + ". "
        + clauses["bounded-trigger"] + "."
    )
    # This short normative unit is closed: a correct prefix cannot license an exception.
    duties["complete-referral"] = lexical(unit) == lexical(expected)
    return duties


def codex_hook_audit_unit(text: str) -> str:
    procedure = selected_section(text, "Codex hook procedure")
    return selected_unit(procedure, "Structural enforcement (auto-installed)",
                         "Four PreToolUse audit hooks (warn-only).")


RUNTIME_OWNER_ROWS = (
    "| `$HOME/.agents/skills/` | Shared canonical installed skill tree for the current monorepo producer; "
    "`.claude/skills/` is its logical projection where the producer and actual binding establish it. "
    "Other layouts require their actual materialization owner. |",
    "| `$HOME/.agents/contracts/` | Live canonical global Codex contract surface. |",
    "| `$HOME/.codex/` | Codex configuration, hooks, native-role metadata, and retained "
    "provider-root compatibility outputs; not the canonical skills/contracts tree. |",
)


def runtime_owner_rows_present(text: str) -> dict[str, bool]:
    lines = selected_section(text, "Runtime Map").splitlines()
    return {row: lines.count(row) == 1 for row in RUNTIME_OWNER_ROWS}


class TestOrchestrationDisciplineContract(unittest.TestCase):
    _cache: dict[str, str] = {}

    def _read(self, rel: str) -> str:
        if rel not in self._cache:
            path = REPO_ROOT / rel
            self.assertTrue(path.is_file(), f"owner file missing: {rel}")
            text = path.read_text(encoding="utf-8")
            if rel == "src.claude/CLAUDE.md":
                text = self._read(SPINE) + "\n" + text
            self._cache[rel] = text
        return self._cache[rel]

    def test_shared_duty_guards_reject_distinct_evidence_cleanup_and_baseline_losses(self) -> None:
        text = self._read(SPINE)
        cases = (
            (evidence_duties, "Verification and decision discipline", "Evidence-based completion:", "dead-lane-unverified", "UNVERIFIED: re-dispatch/report", "CLEAN: no report required"),
            (evidence_duties, "Verification and decision discipline", "Evidence-based completion:", "missing-verdict-rejection", "missing verdict NOT-clean (fail-closed)", "missing verdict clean (fail-open)"),
            (cleanup_duties, "Operational and environment safety", "Resource lifecycle hygiene:", "all-exit-release", "/cancellation/timeout", "/timeout"),
            (cleanup_duties, "Operational and environment safety", "Resource lifecycle hygiene:", "all-exit-release", "/cancellation/timeout", "/cancellation"),
            (cleanup_duties, "Operational and environment safety", "Resource lifecycle hygiene:", "retained-termination-owner", "creator-retained process/Job handles or equivalent stable identity-bound ownership", "a process identifier"),
            (cleanup_duties, "Operational and environment safety", "Resource lifecycle hygiene:", "identifier-only-termination-refused", "never PID/ParentProcessId ancestry alone", "PID/ParentProcessId ancestry alone is sufficient"),
            (baseline_duties, "Core delegation principles", "PASS advances;", "producing-scope-baseline", "producing scope/baseline", "the aggregate worktree"),
            (baseline_duties, "Core delegation principles", "PASS advances;", "independent-delta-review", "later independent deltas get own review", "later independent deltas retroactively falsify earlier work"),
            (baseline_duties, "Core delegation principles", "PASS advances;", "material-upstream-invalidation", "invalidates dependent PASS", "preserves dependent PASS"),
            (baseline_duties, "Core delegation principles", "Workflow economy (binding):", "affected-re-review", "Re-review finding/delta only", "Do not re-review findings or deltas"),
            (baseline_duties, "Core delegation principles", "Workflow economy (binding):", "affected-re-review", "full only new defect class/material upstream revision", "full re-review always required"),
            (baseline_duties, "Core delegation principles", "PASS advances;", "material-upstream-invalidation", "dependent PASS", "dependent pass"),
        )
        for check, section, marker, duty, old, new in cases:
            with self.subTest(duty=duty, loss=old):
                unit = selected_unit(text, section, marker)
                self.assertEqual(unit.count(old), 1)
                self.assertFalse(check(text.replace(unit, unit.replace(old, new, 1), 1))[duty])

    def test_independent_review_guards_reject_weakened_owner_duties(self) -> None:
        for owner in ("src.codex/skills/architecture-reviewer/SKILL.md",
                      "src.claude/agents/architecture-reviewer.md"):
            text = self._read(owner)
            unit = selected_unit(text, "Anti-layering audit (multi-fix batch)", "Independent review:")
            for duty, old, new in (
                ("nonauthoring-reviewer", "nonauthoring reviewer", "authoring reviewer"),
                ("required-commission", "Apply the shared commission rule", "Ignore the shared commission rule"),
                ("qualified-model-preference", "alone is not a veto", "alone is a veto"),
                ("task-and-host-restrictions", "Preserve any explicit task-specific engine requirement", "Ignore any explicit task-specific engine requirement"),
                ("task-and-host-restrictions", "and actual host rejection or execution drift", "but ignore actual host rejection or execution drift"),
                ("complete-owner-unit", "nonauthoring reviewer.", "nonauthoring reviewer unless none is available, when the author may review."),
                ("complete-owner-unit", "execution drift.", "execution drift only when convenient."),
                ("complete-owner-unit", "execution drift.", "execution drift. The author may substitute for an independent reviewer."),
            ):
                with self.subTest(owner=owner, duty=duty, loss=old):
                    self.assertEqual(unit.count(old), 1)
                    changed = text.replace(unit, unit.replace(old, new, 1), 1)
                    self.assertFalse(independent_review_duties(changed)[duty])

    def test_root_ledger_guards_reject_weakened_owner_duties(self) -> None:
        text = self._read("src.codex/skills/lead/subagent-contracts.md")
        unit = selected_unit(text, "agent-runs.jsonl format", "Only the root main conversation holding Lead owns")
        for duty, old, new in (
            ("root-ownership", "`agent-runs.jsonl`", "`Agent-runs.jsonl`"),
            ("root-ownership", "owns `agent-runs.jsonl`", "owns all ledger files except `agent-runs.jsonl`"),
            ("actual-root-execution", "actual native and already-admitted", "guessed native and unadmitted"),
            ("bounded-wrapper-delegation", "an actual supported tracked provider wrapper", "any helper"),
            ("bounded-wrapper-delegation", "its own pair", "any pair"),
            ("specialist-no-append", "Specialists never append", "Specialists may append"),
            ("direct-external-contract", "remains under [the external-dispatch contract](external-dispatch.md)", "bypasses the external-dispatch contract"),
            ("actual-wrapper-evidence", "apply only when that wrapper actually ran", "apply even when that wrapper never ran"),
            ("complete-owner-unit", "Specialists never append.", "Specialists never append unless Root is busy."),
            ("complete-owner-unit", "that wrapper actually ran.", "that wrapper actually ran. Specialists may append on their own authority."),
        ):
            with self.subTest(duty=duty, loss=old):
                self.assertEqual(unit.count(old), 1)
                changed = text.replace(unit, unit.replace(old, new, 1), 1)
                self.assertFalse(root_ledger_duties(changed)[duty])

    def test_ledger_and_review_guards_preserve_scope_and_bounded_formatting(self) -> None:
        for owner, check, section, marker, old, new in (
            ("src.codex/skills/lead/subagent-contracts.md", root_ledger_duties,
             "agent-runs.jsonl format", "Only the root main conversation holding Lead owns",
             "Specialists never append", "Specialists may append"),
            ("src.codex/skills/architecture-reviewer/SKILL.md", independent_review_duties,
             "Anti-layering audit (multi-fix batch)", "Independent review:",
             "nonauthoring reviewer", "authoring reviewer"),
            ("src.claude/agents/architecture-reviewer.md", independent_review_duties,
             "Anti-layering audit (multi-fix batch)", "Independent review:",
             "nonauthoring reviewer", "authoring reviewer"),
        ):
            text = self._read(owner)
            unit = selected_unit(text, section, marker)
            with self.subTest(owner=owner, case="formatting"):
                formatted = unit.replace(old, "**" + old.upper().replace(" ", "  ") + "**")
                self.assertTrue(all(check(text.replace(unit, formatted, 1)).values()))
            changed = text.replace(unit, unit.replace(old, new, 1), 1)
            # Genuine phrases in unrelated sections, code examples, or example
            # subsections cannot rescue the selected owning policy unit.
            for decoy in ("\n## Unrelated policy\n", "\n```markdown\n", "\n## Example: historical policy\n"):
                with self.subTest(owner=owner, case=decoy):
                    suffix = "\n```\n" if "```" in decoy else "\n"
                    self.assertFalse(all(check(changed + decoy + unit + suffix).values()))
            for invalid in ("", text.replace(section, "Unrelated policy", 1),
                            text + "\n## " + section + "\nDuplicate\n"):
                with self.subTest(owner=owner, case="missing-or-duplicate-owner"):
                    with self.assertRaises(AssertionError):
                        check(invalid)

    def test_compact_shared_guards_reject_distinct_obligation_losses(self) -> None:
        text = self._read(SPINE)
        cases = (
            (quick_fix_duties, "Core delegation principles", "quick-fix:", "bounded-admission", "target/steps/bounds/owner/contracts", "target/steps/bounds/owner"),
            (quick_fix_duties, "Core delegation principles", "quick-fix:", "bounded-admission", "no new dependency/risk owner", "new dependency/risk owner allowed"),
            (quick_fix_duties, "Core delegation principles", "quick-fix:", "bounded-admission", "rollback/backup/oracle", "rollback/backup"),
            (quick_fix_duties, "Core delegation principles", "quick-fix:", "minimal-recovery", "Before mutation only", "After mutation also"),
            (quick_fix_duties, "Core delegation principles", "quick-fix:", "minimal-recovery", "lifecycle+4 recovery facts", "lifecycle without recovery facts"),
            (quick_fix_duties, "Core delegation principles", "quick-fix:", "minimal-recovery", "work-items/active/<slug>/status.md", "work-items/Active/<slug>/status.md"),
            (quick_fix_duties, "Core delegation principles", "quick-fix:", "no-heavy-preludes", "no roadmap/brief", "require roadmap/brief"),
            (quick_fix_duties, "Core delegation principles", "quick-fix:", "same-item-reclassification", "enrich/reclassify same item", "create a replacement item"),
            (quick_fix_duties, "Core delegation principles", "quick-fix:", "bounded-delivery", "One preflight, implement/QA, close/archive", "Repeated preflight, implement, leave open"),
            (stop_rule_duties, "Scope and ownership discipline", "No logic duplication / no fix layering:", "second-cross-break-stop", "SECOND same-session fix", "THIRD same-session fix"),
            (stop_rule_duties, "Scope and ownership discipline", "No logic duplication / no fix layering:", "second-cross-break-stop", "STOP all edits", "continue editing"),
            (stop_rule_duties, "Scope and ownership discipline", "No logic duplication / no fix layering:", "owner-siblings-contract-diagnosis", "diagnose owner/siblings/shared contract", "patch only the visible symptom"),
            (lead_dispatch_duties, "Core delegation principles", "$lead:", "root-only-dispatch-and-lifecycle", "root main conversation alone", "root and every specialist"),
            (lead_dispatch_duties, "Core delegation principles", "$lead:", "no-specialist-or-delivery-owner", "never subagent/end-to-end coder/roadmap owner", "may be subagent/end-to-end coder/roadmap owner"),
            (isolation_duties, "Operational and environment safety", "Parallel resource-surface isolation:", "full-overlap-surfaces", "throughout overlap", "only at launch"),
            (isolation_duties, "Operational and environment safety", "Parallel resource-surface isolation:", "conflict-serialization-or-isolation", "Otherwise serialize or use", "Otherwise run concurrently or use"),
            (isolation_duties, "Operational and environment safety", "Parallel resource-surface isolation:", "conflict-serialization-or-isolation", "explicitly requested validated isolation", "automatic unvalidated isolation"),
            (isolation_duties, "Operational and environment safety", "Parallel resource-surface isolation:", "safe-read-only-or-disjoint-work", "Read/read and truly disjoint work are safe", "Read/read work is prohibited"),
            (isolation_duties, "Operational and environment safety", "Parallel resource-surface isolation:", "observed-test-surfaces", "tests declare executed/installed/copied source/helpers as observed surfaces", "tests ignore executed source and helpers"),
        )
        surface_cases = tuple(
            (isolation_duties, "Operational and environment safety", "Parallel resource-surface isolation:",
             "full-overlap-surfaces", "read/write/execute/install/copy/baseline", "/".join(
                 item for item in ("read", "write", "execute", "install", "copy", "baseline") if item != surface
             ))
            for surface in ("read", "write", "execute", "install", "copy", "baseline")
        )
        for check, section, marker, duty, old, new in cases + surface_cases:
            with self.subTest(duty=duty, loss=old, replacement=new):
                unit = selected_unit(text, section, marker)
                self.assertTrue(check(text)[duty])
                self.assertEqual(unit.count(old), 1)
                changed = text.replace(unit, unit.replace(old, new, 1), 1)
                # The old complete obligation in an example must not repair its live owner.
                changed += "\n## Examples\n```markdown\n" + unit + "\n```\n"
                self.assertFalse(check(changed)[duty])


    def test_quick_fix_exact_path_cannot_come_from_another_clause(self) -> None:
        text = self._read(SPINE)
        unit = selected_unit(text, "Core delegation principles", "quick-fix:")
        path = "work-items/active/<slug>/status.md"
        self.assertEqual(unit.count(path), 1)
        changed = unit.replace(path, "work-items/Active/<slug>/status.md", 1)
        changed += " Example path: `" + path + "`."
        self.assertFalse(quick_fix_duties(text.replace(unit, changed, 1))["minimal-recovery"])


    def test_compact_shared_guards_reject_attached_weakening_suffixes(self) -> None:
        text = self._read(SPINE)
        for check, duty, phrase in (
            (quick_fix_duties, "bounded-admission", "rollback/backup/oracle"),
            (quick_fix_duties, "minimal-recovery", "with lifecycle+4 recovery facts"),
            (quick_fix_duties, "no-heavy-preludes", "no roadmap/brief/Research/Design/Plan/consultant/pre-review"),
            (baseline_duties, "producing-scope-baseline", "later independent deltas get own review"),
            (baseline_duties, "material-upstream-invalidation", "material upstream change invalidates dependent PASS"),
            (baseline_duties, "affected-re-review", "full only new defect class/material upstream revision"),
            (stop_rule_duties, "second-cross-break-stop", "STOP all edits"),
            (isolation_duties, "conflict-serialization-or-isolation", "explicitly requested validated isolation"),
            (lead_dispatch_duties, "root-only-dispatch-and-lifecycle", "root main conversation alone dispatches/writes lifecycle"),
            (fixed_value_duties, "single-owned-safe-defaults", "policy defaults need one owner/omission safety"),
        ):
            with self.subTest(duty=duty):
                self.assertTrue(check(text)[duty])
                self.assertEqual(text.count(phrase), 1)
                changed = text.replace(phrase, phrase + " only when convenient", 1)
                self.assertFalse(check(changed)[duty])


    def test_fixed_value_guards_reject_distinct_losses_in_both_owners(self) -> None:
        cases = (
            ("classify-invariants", "Before changing classify", "Change without classification"),
            ("classify-invariants", "may stay fixed", "must become variable"),
            ("single-owned-safe-defaults", "one owner/omission safety", "multiple owners/omission safety"),
            ("single-owned-safe-defaults", "one owner/omission safety", "one owner/no omission safety"),
            ("variable-input-tests", "variability/omission tests", "variability tests only"),
        )
        for owner in (SPINE, "shared/external-prompt-governance.md"):
            text = self._read(owner)
            projection = owner != SPINE
            for duty, old, new in cases:
                with self.subTest(owner=owner, duty=duty, loss=old, replacement=new):
                    self.assertTrue(fixed_value_duties(text, projection=projection)[duty])
                    self.assertEqual(text.count(old), 1)
                    changed = text.replace(old, new, 1)
                    self.assertFalse(fixed_value_duties(changed, projection=projection)[duty])


    def test_compact_guards_require_the_live_scoped_owner(self) -> None:
        text = self._read(SPINE)
        for check, section, marker in (
            (quick_fix_duties, "Core delegation principles", "quick-fix:"),
            (baseline_duties, "Core delegation principles", "PASS advances;"),
            (stop_rule_duties, "Scope and ownership discipline", "No logic duplication / no fix layering:"),
            (isolation_duties, "Operational and environment safety", "Parallel resource-surface isolation:"),
            (lead_dispatch_duties, "Core delegation principles", "$lead:"),
            (fixed_value_duties, "Scope and ownership discipline", "Anti-hardcoding and justified limits:"),
        ):
            with self.subTest(owner=marker):
                self.assertTrue(all(check(text).values()))
                unit = selected_unit(text, section, marker)
                # Preserve the label but remove the obligation from its selected unit.
                missing = text.replace(unit, "Unrelated policy.", 1)
                for decoy in ("", "\n## Examples\n" + unit,
                              "\n## Unrelated policy\n" + unit,
                              "\n```markdown\n" + unit + "\n```\n"):
                    with self.subTest(decoy=decoy[:24]):
                        try:
                            duties = check(missing + decoy)
                        except AssertionError:
                            continue
                        self.assertFalse(all(duties.values()))


    def test_native_owner_guards_reject_distinct_route_collapses(self) -> None:
        text = self._read("src.codex/skills/lead/operating-model.md")
        unit = selected_unit(text, "Native Astra task-dependent route", "For ordinary native and skill-only roles,")
        cases = (
            ("ordinary-selectors", "describe_ordinary_native_role_options", "guess_role_options"),
            ("task-profile-membership", "exact task/role profile membership", "a role label alone"),
            ("conscious-selection", "consciously selects and supplies both model and effort", "implicitly inherits model and effort"),
            ("omitted-explicit-default", "resolves to an explicit default pair", "inherits an unspecified pair"),
            ("tuple-validation", "against task, role, host and configured controls", "against task and role alone"),
            ("generic-explicit-route", "no `agent_type`", "a fixed `agent_type`"),
            ("generic-explicit-route", 'fork_turns="none"', 'fork_turns="all"'),
            ("generic-explicit-route", "carries the selected profession instructions", "omits the selected profession instructions"),
            ("bare-default-inheritance", "instead inherits provider subagent defaults or parent settings", "instead guarantees the policy tuple"),
            ("policy-tuple-selector", "policy-requiring callers use the ordinary selector", "policy-requiring callers omit the ordinary selector"),
            ("custom-pin-no-bypass", "does not bypass higher-precedence", "bypasses higher-precedence"),
            ("custom-pin-local-conflict", "not universal model unavailability", "universal model unavailability"),
            ("complete-custom-controls", "complete configured tuple", "partial configured tuple"),
            ("partial-controls-unresolved", "partial controls remain unresolved rather than being filled from factory defaults", "partial controls are filled from factory defaults"),
            ("custom-bytes-preserved", "preserves without reserializing TOML", "rewrites by reserializing TOML"),
            ("full-host-discovery", "never a desired-model pre-filter that hides alternatives", "using a desired-model pre-filter that hides alternatives"),
            ("generic-capability-unknown", "generic ordinary invocations name no required agent type", "ordinary invocations require a fixed named agent type"),
            ("selector-nonexecution", "The selector launches nothing", "The selector launches the worker"),
            ("requested-vs-actual", "requested and resolved controls separately from actual runtime metadata", "requested and resolved controls as actual runtime metadata"),
            ("missing-actual", "treats missing actual metadata as `unspecified by runtime`", "treats missing actual metadata as the requested profile"),
            ("drift-refusal", "drift as nonauthorizing with no fallback", "drift as authorizing with a fallback"),
        )
        for duty, old, new in cases:
            with self.subTest(duty=duty):
                self.assertEqual(unit.count(old), 1)
                self.assertFalse(native_route_duties(text.replace(unit, unit.replace(old, new, 1), 1))[duty])

    def test_native_consumer_checks_the_complete_referral_context(self) -> None:
        text = self._read("src.codex/skills/lead/SKILL.md")
        unit = selected_unit(text, "Parallelism rule", "Dispatch economics:")
        for duty, old, new in (
            ("qualified-defaults", "candidates rather than blanket authority", "exclusive blanket authority"),
            ("profile-policy-owner", "exact profile membership and separate special-corridor/explicit-profile rules", "selected effort settings"),
            ("actual-override-evidence", "returned actual runtime metadata confirms", "the requested profile confirms"),
            ("authoritative-referral", "apply `Native Astra task-dependent route` in the sibling `operating-model.md` under the installed AGENTS native-dispatch kernel; do not restate or widen that owner here", "apply the local default profile"),
        ):
            with self.subTest(duty=duty):
                self.assertEqual(unit.count(old), 1)
                changed = text.replace(unit, unit.replace(old, new, 1), 1)
                self.assertFalse(native_consumer_duties(changed, "Parallelism rule", "Dispatch economics:", referral_only=True)[duty])
        for contrary in (
            " The generic fallback TOML declares a fixed profile.",
            " All Codex native role TOMLs must declare a fixed profile.",
            " The requested profile proves actual runtime model and effort.",
        ):
            with self.subTest(contrary=contrary):
                # The genuine AGENTS referral and all positive duties remain present.
                changed = text.replace(unit, unit + contrary, 1)
                duties = native_consumer_duties(changed, "Parallelism rule", "Dispatch economics:", referral_only=True)
                self.assertTrue(duties["authoritative-referral"])
                self.assertFalse(duties["no-contrary-route"])
        for owner, section, marker, reference in (
            ("src.codex/skills/lead/operating-model.md", "External routing order", "Resolve the requested route before launch", False),
            ("references-codex/subagent-operating-model.md", "Codex-specific runtime notes", "Ordinary discovery presents", True),
        ):
            projected = self._read(owner)
            unit = selected_unit(projected, section, marker)
            ownership = ("exact profile membership and separate special-corridor/explicit-profile rules"
                         if reference else "every effort floor and corridor")
            for duty, old, new in (
                ("profile-policy-owner", ownership, "selected effort settings"),
                ("ordinary-discovery", "admissible choices and a default suggestion", "an obligatory fixed native role"),
                ("conscious-selection", "consciously selects and supplies both model and effort", "inherits a model and effort"),
                ("omitted-explicit-default", "resolves to an explicit default pair", "inherits an unspecified pair"),
                ("bare-default-inheritance", "Direct bare `default` calls inherit provider/parent settings instead", "Direct bare `default` calls guarantee the policy tuple instead"),
                ("authoritative-referral", "installed `Native Astra task-dependent route` owns explicit-tuple and custom-pin conflict semantics", "the local default profile owns all route semantics"),
                ("actual-override-evidence", "returned actual runtime metadata confirms", "the requested profile confirms"),
            ):
                with self.subTest(owner=owner, projected_duty=duty):
                    self.assertEqual(unit.count(old), 1)
                    changed = projected.replace(unit, unit.replace(old, new, 1), 1)
                    self.assertFalse(native_consumer_duties(changed, section, marker, reference=reference)[duty])

    def test_native_scope_and_identifiers_allow_only_bounded_formatting(self) -> None:
        text = self._read("src.codex/skills/lead/operating-model.md")
        formatted = text.replace("An omitted pair", "**AN**   OMITTED PAIR").replace("Claim an override", "CLAIM an override").replace(
            "For ordinary native and skill-only roles", "**FOR** ordinary native and skill-only   roles"
        )
        self.assertTrue(all(native_route_duties(formatted).values()))
        for missing in ("", text.replace("## Native Astra task-dependent route", "## Unrelated route"),
                        text + "\n## Native Astra task-dependent route\nDuplicate\n"):
            with self.subTest(case="missing-or-duplicate-native-owner"):
                with self.assertRaises(AssertionError):
                    native_route_duties(missing)
        shared = self._read(SPINE)
        unit = selected_unit(shared, "Verification and decision discipline", "Evidence-based completion:")
        lower_status = shared.replace(unit, unit.replace("UNVERIFIED", "unverified"), 1)
        self.assertFalse(evidence_duties(lower_status)["dead-lane-unverified"])
        for atom, invalid in (
            ("resolve_ordinary_native_dispatch", "Resolve_ordinary_native_dispatch"),
            ("default.toml", "default.toml.old"),
            ("UNVERIFIED", "UNVERIFIED—legacy"),
            ("UNVERIFIED", "**UNVERIFIED**"),
            ("UNVERIFIED", "__UNVERIFIED__"),
            ("unspecified by runtime", "unspecified  by runtime"),
        ):
            with self.subTest(case="exact-atom", atom=atom, invalid=invalid):
                self.assertTrue(identifier_present(f"`{atom}`", atom))
                self.assertFalse(identifier_present(f"`{invalid}`", atom))
        for formatted in ("`UNVERIFIED`", "**UNVERIFIED**", "_UNVERIFIED_", "__UNVERIFIED__"):
            with self.subTest(case="outer-markup", formatted=formatted):
                self.assertTrue(identifier_present(formatted, "UNVERIFIED"))
        self.assertFalse(identifier_present("", ""))

    def test_normative_sentences_present_in_every_owner(self) -> None:
        """Preserve exact owner pins and diagnose each selected structural duty."""
        for gap_id, substring, owners in PINS:
            for owner in owners:
                with self.subTest(gap=gap_id, owner=owner):
                    text = self._read(owner)
                    check = (
                        SHARED_DUTY_CHECKS.get(gap_id) if owner == SPINE else None
                    )
                    if gap_id == "batch-b-hardcoding":
                        check = lambda value: fixed_value_duties(value, projection=owner != SPINE)
                    elif gap_id == "fix-class-invariant-independent-review":
                        check = independent_review_duties
                    elif gap_id == "root-owned-ledger":
                        check = root_ledger_duties
                    if check is not None:
                        for duty, present in check(text).items():
                            with self.subTest(gap=gap_id, owner=owner, duty=duty):
                                self.assertTrue(present, f"[{gap_id}] {owner}: missing or inverted duty {duty}")
                    else:
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

    def test_implementation_prerequisite_is_route_appropriate_without_relaxing_planner(self) -> None:
        codex = self._read("src.codex/skills/lead/subagent-contracts.md")
        claude = self._read("src.claude/agents/contracts/subagent-contracts.md")
        route_rule = (
            "Implementation and Quality Assurance receive route-appropriate accepted artifacts; "
            "a Plan is required only when the selected route admits a Plan stage."
        )
        for owner, text in (
            ("src.codex/skills/lead/subagent-contracts.md", codex),
            ("src.claude/agents/contracts/subagent-contracts.md", claude),
        ):
            with self.subTest(owner=owner):
                self.assertIn(route_rule, text)
        self.assertNotIn("Use only after plan approval.", codex)
        self.assertIn(
            "## Planner\n\nUse after the required design and specialist constraints are accepted.",
            codex,
        )

    def test_dynamic_lane_ready_admission_contract_is_cross_pack_and_canonical(self) -> None:
        for owner in DYNAMIC_ADMISSION_OWNERS:
            text = self._read(owner)
            clauses = (
                RUSSIAN_DYNAMIC_ADMISSION_CLAUSES
                if owner == "shared/references/ru/subagent-operating-model.md"
                else DYNAMIC_ADMISSION_CLAUSES
            )
            for clause in clauses:
                with self.subTest(owner=owner, clause=clause):
                    self.assertIn(clause, text)

    def test_dynamic_admission_removes_fixed_caps_and_stale_sequential_claims(self) -> None:
        owners = DYNAMIC_ADMISSION_OWNERS + (
            "references-codex/subagent-operating-model.md",
            "references-claude/subagent-operating-model.md",
        )
        stale = (
            "practical limit of four",
            "top-priority four",
            "no native internal parallel skill dispatch",
            "internal Codex-role work is still orchestrated sequentially",
            "runtime default surface",
            "all MCP",
        )
        for owner in owners:
            text = self._read(owner)
            for residue in stale:
                with self.subTest(owner=owner, residue=residue):
                    self.assertNotIn(residue, text)

    def test_plan_checkpoints_prioritize_downstream_work_reduction(self) -> None:
        lead_clauses = (
            "At natural checkpoints—stage completion, changed dependencies or blockers, or material cost growth—",
            "removes, simplifies, or reuses downstream work",
            "preserve scope, quality, gates, and authority",
        )
        planner_clauses = (
            "Prioritize critical-path and concrete enabling phases by dependencies; a blocker delays only dependent phases.",
            "Apply Lead's plan-checkpoint rule",
            "total remaining verified delivery cost",
        )
        retired = "If the work item includes an admitted bug or prerequisite issue, always make that fix Phase A."

        for owner in PLAN_CHECKPOINT_LEAD_OWNERS:
            with self.subTest(owner=owner):
                text = self._read(owner)
                for clause in lead_clauses:
                    self.assertIn(clause, text)

        for owner in PLAN_CHECKPOINT_PLANNER_OWNERS:
            with self.subTest(owner=owner):
                text = self._read(owner)
                for clause in planner_clauses:
                    self.assertIn(clause, text)
                self.assertNotIn(retired, text)

    def test_model_and_effort_truth_is_provider_neutral_in_the_shared_owner(self) -> None:
        shared = self._read("shared/references/subagent-operating-model.md")
        self.assertIn(SHARED_MODEL_EFFORT_TRUTH, shared)
        self.assertNotIn("Native role definitions supply fixed installed profiles", shared)

    def test_codex_model_and_effort_truth_is_toml_and_policy_backed(self) -> None:
        """Keep explicit selection, configured controls and observed runtime truth distinct."""
        authoritative = "src.codex/skills/lead/operating-model.md"
        for duty, present in native_route_duties(self._read(authoritative)).items():
            with self.subTest(owner=authoritative, duty=duty):
                self.assertTrue(present, f"{authoritative}: missing or contradicted native route {duty}")
        consumers = (
            ("src.codex/skills/lead/SKILL.md", "Parallelism rule", "Dispatch economics:", True, False),
            ("src.codex/skills/lead/operating-model.md", "External routing order", "Resolve the requested route before launch", False, False),
            ("references-codex/subagent-operating-model.md", "Codex-specific runtime notes", "Ordinary discovery presents", False, True),
        )
        for owner, section, marker, referral_only, reference in consumers:
            for duty, present in native_consumer_duties(
                self._read(owner), section, marker, referral_only=referral_only, reference=reference
            ).items():
                with self.subTest(owner=owner, duty=duty):
                    self.assertTrue(present, f"{owner}: missing or contradicted native consumer duty {duty}")

    def test_claude_model_and_effort_truth_is_host_selected_without_role_inference(self) -> None:
        owners = (
            "src.claude/skills/lead/SKILL.md",
            "src.claude/agents/contracts/operating-model.md",
            "references-claude/subagent-operating-model.md",
        )
        stale = ("fixed installed profiles", "default effort floors")
        for owner in owners:
            text = self._read(owner)
            with self.subTest(owner=owner):
                self.assertIn(CLAUDE_MODEL_EFFORT_TRUTH, text)
                for residue in stale:
                    self.assertNotIn(residue, text)

    def test_shared_english_and_russian_force_summaries_have_semantic_parity(self) -> None:
        english = self._read("shared/references/subagent-operating-model.md")
        russian = self._read("shared/references/ru/subagent-operating-model.md")
        for english_clause, russian_clause in DYNAMIC_FORCE_PARITY:
            with self.subTest(english=english_clause, russian=russian_clause):
                self.assertIn(english_clause, english)
                self.assertIn(russian_clause, russian)

    def test_release_note_does_not_overclaim_native_execution_truth(self) -> None:
        release_notes = self._read("RELEASE_NOTES.md")
        self.assertNotIn(
            "Native role profiles and effort floors are reported as fixed execution truth",
            release_notes,
        )
        self.assertIn("route-authoritative evidence", release_notes)
        self.assertIn("`unspecified by runtime`", release_notes)

    def test_handoff_requires_fresh_exact_tool_selection_on_both_packs(self) -> None:
        owners = (
            "src.claude/agents/contracts/subagent-contracts.md",
            "src.codex/skills/lead/subagent-contracts.md",
        )
        for owner in owners:
            text = self._read(owner)
            with self.subTest(owner=owner):
                self.assertIn(
                    "<exact task-scoped tool or MCP identifier discovered immediately before this spawn, or none>",
                    text,
                )
                self.assertIn(
                    "The caller performs fresh discovery before every subagent spawn and records only the exact task-scoped identifiers selected for that run, or `none`.",
                    text,
                )
                self.assertNotIn("runtime default surface", text)
                self.assertNotIn("all MCP", text)

    def test_actionable_handoff_activation_contract_is_provider_aware(self) -> None:
        codex = self._read("src.codex/skills/lead/SKILL.md")
        self.assertIn("Treat informational delivery and task activation as distinct operations", codex)
        self.assertIn("proves only delivery, not that execution was scheduled or progress resumed", codex)
        self.assertIn("wait only after scheduling succeeds or current-running evidence exists", codex)
        self.assertIn("`collaboration.followup_task` schedules an idle agent", codex)
        self.assertIn("On other hosts, use the actual host-equivalent operations and semantics, not the Codex tool names", codex)

        generic_clause = "an informational delivery does not schedule recipient execution"
        for owner in (
            "src.claude/skills/lead/SKILL.md",
            "shared/references/subagent-operating-model.md",
        ):
            with self.subTest(owner=owner):
                text = self._read(owner)
                self.assertIn(generic_clause, text.casefold())
                self.assertIn("host's explicit follow-up task mechanism", text)
                self.assertNotIn("collaboration.send_message", text)
                self.assertNotIn("collaboration.followup_task", text)

    def test_receiving_correlation_rejects_prior_pass_forward_fixture(self) -> None:
        # Source-contract forward fixture only; this does not claim host enforcement.
        dispatch = STALE_PASS_FORWARD_FIXTURE["dispatch"]
        returned = STALE_PASS_FORWARD_FIXTURE["returned_prior_pass"]
        compared = ("task_identity", "scope", "expected_artifact")
        self.assertNotEqual(
            tuple(dispatch[key] for key in compared),
            tuple(returned[key] for key in compared),
        )
        self.assertEqual(returned["gate"], "PASS")

        for owner in HANDOFF_CONTRACTS:
            with self.subTest(owner=owner):
                text = self._read(owner)
                self.assertIn("Current-assignment correlation is part of the existing Receiving-side echo", text)
                self.assertIn("current host task identity, or the existing ledger `runId` when present", text)
                self.assertIn("together with the echoed `Scope` and `Expected artifact`", text)
                self.assertIn("Hash only declared file `Approved inputs`", text)
                self.assertIn("is stale and nonauthorizing", text)
                self.assertIn("Trivial inline work and legitimate artifactless fact lookup require neither a ledger nor an artifact nor a new field", text)
                self.assertIn("| Root main conversation | `lead` | `main` | omit |", text)
                self.assertIn("| Native specialist | `toolchain-engineer` | `internal` | omit |", text)
                self.assertIn("| External worker assigned analysis | `external-worker` | `external-worker` | `analyst` |", text)
                self.assertIn("Human artifact labels such as `Execution role` are not JSON values", text)
                self.assertIn("existing `launch`, `terminal`, or `standalone` relation", text)
                self.assertIn("Never hand-append invented `resume` or `accept` JSON", text)
                self.assertIn("preserve accepted engineering artifacts", text)
                self.assertIn("Do not invent a bypass or administrative journal", text)

        shared = self._read("shared/references/subagent-operating-model.md")
        self.assertIn("**Receiving correlation**", shared)
        self.assertIn("Trivial inline work and legitimate artifactless fact lookup require no ledger, artifact, or new field", shared)

    def test_work_item_closure_guidance_matches_lifecycle_owner(self) -> None:
        owners = (
            "src.codex/AGENTS.codex.md",
            "src.codex/skills/lead/SKILL.md",
            "src.claude/skills/lead/SKILL.md",
            "docs/work-item-execution-tracking.md",
        )
        required = (
            "nonempty `Closed`, `Outcome`, `Evidence`, and `Residual risk` fields",
            "`Closed` MUST exactly equal the requested `--terminal-instant` and use strict UTC `YYYY-MM-DDTHH:MM:SSZ`",
        )
        for owner in owners:
            with self.subTest(owner=owner):
                text = " ".join(self._read(owner).split())
                for fragment in required:
                    self.assertIn(fragment, text)

        codex = self._read("src.codex/AGENTS.codex.md")
        self.assertIn("versioned Lead/lifecycle-owner contract", codex)
        self.assertNotIn(
            "enumerating exactly all current bugs whose parsed `context` equals the item slug",
            codex,
        )

        stale_work_item_clause = (
            "It holds the final closeout record: outcome, residual risk, and archive "
            "location, and MUST carry a `Closed: <YYYY-MM-DD>` line."
        )
        for owner in (
            "src.codex/skills/lead/SKILL.md",
            "src.claude/skills/lead/SKILL.md",
        ):
            with self.subTest(owner=owner):
                self.assertNotIn(stale_work_item_clause, self._read(owner))

    def test_design_readiness_contract_is_cross_pack_and_sample_honest(self) -> None:
        for owner in (
            "src.codex/skills/architect/SKILL.md",
        ):
            with self.subTest(owner=owner):
                text = self._read(owner)
                self.assertIn("When the design creates, changes, or consumes a serialized/wire boundary", text)
                self.assertIn("before `Design PASS`, walk one producer serialization through the exact consumer signature and validation", text)
                self.assertIn("actual wire shape and codec", text)
                self.assertIn("field order only when protocol semantics require it", text)
                self.assertIn("an acyclic provenance dependency graph", text)
                self.assertIn("include one actual serialized sample", text)
                self.assertIn("explicitly proposed representative specimen", text)
                self.assertIn("Hand off a ready decision before optional prose polishing", text)

        shared = self._read("shared/references/subagent-operating-model.md")
        self.assertIn("Before Design PASS, walk one producer record through the exact consumer signature and validation", shared)
        self.assertIn("For an existing producer, use an actual serialized sample", shared)
        self.assertIn("not fake production data or runtime proof", shared)

    def test_archived_external_successor_forward_fixture_is_guidance_only(self) -> None:
        # The fixture pins the accepted source contract; no resolver or host behavior is exercised.
        accepted = ARCHIVED_SUCCESSOR_FORWARD_FIXTURE["accepted_snapshot"]
        lookup = ARCHIVED_SUCCESSOR_FORWARD_FIXTURE["qa_lookup"]
        self.assertEqual(accepted["stable_identifier"], lookup["stable_identifier"])
        self.assertEqual(accepted["root"], "current")
        self.assertEqual(len(lookup["matches"]), 1)
        self.assertEqual(lookup["matches"][0]["root"], "archive/2026-09")
        self.assertNotIn("sha256", lookup)

        for owner in (
            "src.codex/skills/qa-engineer/SKILL.md",
            "src.claude/agents/qa-engineer.md",
        ):
            with self.subTest(owner=owner):
                text = self._read(owner)
                self.assertIn("target registry owner to resolve the stable identifier across its complete physical lifecycle, current plus archive", text)
                self.assertIn("missing, unique current, unique archived, or duplicate", text)
                self.assertIn("A unique archived successor remains valid", text)
                self.assertIn("accepted successor hash freezes only the acceptance snapshot", text)
                self.assertIn("does not freeze future external record bytes", text)

        shared = self._read("shared/references/subagent-operating-model.md")
        self.assertIn("resolve the stable identifier across current and archive", shared)
        self.assertIn("accepted hash as the acceptance snapshot rather than a freeze on future external bytes", shared)

    def test_cleanup_disposition_is_one_exact_cross_pack_field(self) -> None:
        field = (
            "Cleanup disposition:\n"
            "- <owned child process trees, temp/capture paths, and isolation worktrees: "
            "`cleaned` | `preserved` + reason | `none`>"
        )
        owners = (
            "src.claude/agents/contracts/subagent-contracts.md",
            "src.codex/skills/lead/subagent-contracts.md",
        )
        for owner in owners:
            with self.subTest(owner=owner):
                text = self._read(owner)
                self.assertEqual(text.count("Cleanup disposition:"), 1)
                self.assertIn(field, text)

    def test_quick_fix_handles_the_exact_tool_update_incident(self) -> None:
        spine = self._read(SPINE)
        for duty, present in quick_fix_duties(spine).items():
            with self.subTest(duty=duty):
                self.assertTrue(present)

        claude_template = json.loads(self._read(CLAUDE_QUICK_FIX_TEMPLATE))
        self.assertFalse(claude_template["requiresLead"])
        self.assertEqual(claude_template["chain"], ["implement", "QA"])

        for owner in ("src.claude/skills/lead/SKILL.md", "src.codex/skills/lead/SKILL.md"):
            text = self._read(owner)
            self.assertLess(text.index("**Classify before full task-memory recovery**"), text.index("**Verify work-items"))
            self.assertIn("route `implementation -> QA`", text)
            self.assertIn("create the minimal `work-items/active/<slug>/status.md`", text)
        self.assertIn(
            "For `requiresLead: false` routes",
            self._read("src.claude/CLAUDE.md"),
        )
        self.assertIn("Evaluate the shared `quick-fix` predicate before invoking a process skill",
                      self._read("src.claude/CLAUDE.md"))

    def test_quick_fix_has_minimal_pre_mutation_recovery_without_heavy_preludes(self) -> None:
        spine = self._read(SPINE)
        duties = quick_fix_duties(spine)
        for duty in ("minimal-recovery", "no-heavy-preludes", "same-item-reclassification"):
            with self.subTest(duty=duty):
                self.assertTrue(duties[duty])

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

        for entrypoint in ("src.codex/AGENTS.codex.md",):
            with self.subTest(entrypoint=entrypoint):
                text = self._read(entrypoint)
                self.assertIn(
                    "no recovery file is needed unless that invocation is itself admitted as `quick-fix`",
                    text,
                )
                self.assertIn("this exception does not broaden recovery to trivial questions", text)

    def test_quick_fix_rejects_a_contract_change(self) -> None:
        spine = self._read(SPINE)
        duties = quick_fix_duties(spine)
        self.assertTrue(duties["bounded-admission"])
        self.assertTrue(duties["same-item-reclassification"])

    def test_fact_lookup_routes_by_decision_need_and_preserves_active_task_continuity(self) -> None:
        direct_role_priority = {
            "src.codex/AGENTS.codex.md": "1. User explicitly names a role: invoke it directly.",
        }
        for entrypoint in ("src.codex/AGENTS.codex.md",):
            with self.subTest(entrypoint=entrypoint):
                text = self._read(entrypoint)
                for fragment in FACT_ROUTING_FRAGMENTS + SIDE_QUESTION_CONTINUITY_FRAGMENTS:
                    self.assertTrue(
                        fragment in text,
                        f"{entrypoint}: missing routing fragment {fragment!r}",
                    )
                self.assertTrue(
                    direct_role_priority[entrypoint] in text,
                        f"{entrypoint}: explicit user role must precede default factual routing",
                    )

        claude = self._read("src.claude/CLAUDE.md")
        self.assertIn("1. Did the user explicitly name a role? → invoke that role directly.", claude)
        self.assertIn(".claude/agents/team-templates/<template>.json", claude)

        template = json.loads(self._read(CLAUDE_RESEARCH_TEMPLATE))
        roles = {role["agentType"]: role for role in template["roles"]}
        self.assertEqual(template["requiredRoles"], ["analyst"])
        self.assertEqual(template["minRoles"], 1)
        self.assertIs(roles["analyst"].get("required"), True)
        for agent_type, required_triggers in (
            ("architect", ("decision", "adr", "material alternatives")),
            ("planner", ("explicit", "execution plan")),
        ):
            with self.subTest(agent_type=agent_type):
                role = roles[agent_type]
                self.assertIsNot(role.get("required"), True)
                trigger = role.get("whenNeeded", "").lower()
                for expected in required_triggers:
                    self.assertIn(expected, trigger)
        self.assertTrue(
            "A bounded factual investigation defaults to the analyst only" in template["notes"],
            "research template must keep the bounded factual route analyst-only by default",
        )

    def test_handoff_and_status_docs_reuse_existing_acceptance_carriers(self) -> None:
        expected_staged_status = [
            "---",
            "template: staged",
            "status: active",
            "started: <YYYY-MM-DDTHH:MM:SSZ>",
            "updated: <YYYY-MM-DDTHH:MM:SSZ>",
            "---",
            "Task: <active objective>",
            "Current step: <current execution step>",
            "Last result: <accepted result or criteria/guard reference>",
            "Next action: <next implementation or QA step>",
            "Scope boundary: <approved scope and exclusions>",
            "Owner: <current artifact owner>",
            "Integration owner: <integration owner>",
            "Evidence gate: <accepted oracle and required evidence>",
        ]
        for contract in HANDOFF_CONTRACTS:
            with self.subTest(contract=contract):
                text = self._read(contract)
                for fragment in (
                    HANDOFF_ACCEPTANCE_ECHO_FRAGMENTS
                    + STATUS_ACCEPTANCE_CARRIER_FRAGMENTS
                ):
                    self.assertTrue(
                        fragment in text,
                        f"{contract}: missing handoff/status fragment {fragment!r}",
                    )
                section = text.split("### status.md format", 1)[1].split(
                    "### agent-runs.jsonl format", 1
                )[0]
                code = section.split("```markdown", 1)[1].split("```", 1)[0]
                self.assertEqual(
                    [line for line in code.splitlines() if line.strip()],
                    expected_staged_status,
                )
                legacy_fragment = (
                    "Legacy sectioned `status.md` records remain readable compatibility input"
                )
                self.assertTrue(
                    legacy_fragment in section,
                    f"{contract}: missing legacy-status compatibility statement",
                )

    def test_current_status_projections_use_scalar_fields_and_the_existing_ledger(self) -> None:
        response_heading = {
            "src.codex/skills/lead/subagent-contracts.md": "## Shared response format",
            "src.claude/agents/contracts/subagent-contracts.md": "## Response format",
        }
        for contract in HANDOFF_CONTRACTS:
            text = self._read(contract)
            interruption = text.split("No-artifact interruption rule:", 1)[1].split(
                response_heading[contract], 1
            )[0]
            with self.subTest(contract=contract):
                for field in ("Current step", "Last result", "Next action"):
                    self.assertTrue(
                        field in interruption,
                        f"{contract}: interruption recovery omits current scalar {field}",
                    )
                for retired in ("Primary task status:", "Interruption marker:"):
                    self.assertTrue(
                        retired not in interruption,
                        f"{contract}: current interruption writer still requires {retired}",
                    )
                self.assertTrue(
                    "explicit user pause" in interruption and "same-turn" in interruption,
                    f"{contract}: interruption rule loses pause authority or same-turn continuity",
                )

        for lead_skill in (
            "src.codex/skills/lead/SKILL.md",
            "src.claude/skills/lead/SKILL.md",
        ):
            dispatch_line = next(
                line
                for line in self._read(lead_skill).splitlines()
                if "**Dispatch economics**" in line
            )
            with self.subTest(lead_skill=lead_skill):
                self.assertTrue(
                    "agent-runs.jsonl" in dispatch_line,
                    f"{lead_skill}: dispatch metadata does not use the existing ledger",
                )
                self.assertTrue(
                    "status.md` Active agents" not in dispatch_line,
                    f"{lead_skill}: dispatch still mandates the legacy Active agents table",
                )

        status_command = self._read("src.claude/commands/agents-status.md")
        current_status = status_command.split("1. **Active work-items.**", 1)[1].split(
            "2. **Project policies.**", 1
        )[0]
        for fragment in (
            "Current step",
            "Last result",
            "Next action",
            "agent-runs.jsonl",
            "Legacy sectioned",
            "quick-fix four-fact",
        ):
            self.assertTrue(
                fragment in current_status,
                f"agents-status current reader missing {fragment!r}",
            )
        for retired in (
            "orchestration weight (light/full-lead",
            "Priority (if the `## Current state` block",
        ):
            self.assertTrue(
                retired not in current_status,
                f"agents-status current reader still requires {retired!r}",
            )
        dashboard = status_command.split("11. **Format.**", 1)[1]
        self.assertTrue(
            "(orchestration: <light|full-lead>)" not in dashboard,
            "agents-status dashboard still requires orchestration metadata",
        )

        resume = self._read("src.claude/commands/agents-resume.md")
        load_state = resume.split("2. **Load state.**", 1)[1].split(
            "3. **Validate.**", 1
        )[0]
        for fragment in (
            "Current step",
            "Last result",
            "Next action",
            "agent-runs.jsonl",
            "Legacy sectioned",
        ):
            self.assertTrue(
                fragment in load_state,
                f"agents-resume current reader missing {fragment!r}",
            )
        self.assertTrue(
            "Template and orchestration weight" not in load_state,
            "agents-resume current reader still requires orchestration metadata",
        )

        panel = self._read("src.claude/commands/agents-design-panel.md")
        preregistration = next(
            line for line in panel.splitlines() if "pre-register" in line
        )
        for fragment in ("agent-runs.jsonl", "Current step", "Last result", "Next action"):
            self.assertTrue(
                fragment in preregistration,
                f"design-panel preregistration missing existing carrier {fragment!r}",
            )
        self.assertTrue(
            "## Active agents" not in preregistration,
            "design-panel preregistration still requires the legacy table",
        )

        dependencies = self._read("docs/dependencies.md").split(
            "## How an edge is declared", 1
        )[1].split("## Derived views", 1)[0]
        self.assertTrue(
            "top-level optional scalar field" in dependencies,
            "dependency declaration does not name the current scalar owner",
        )
        self.assertTrue(
            "`## Current state` block" not in dependencies,
            "dependency declaration still requires the legacy section",
        )

        tracking = self._read("docs/work-item-execution-tracking.md")
        self.assertTrue(
            "Current dashboards and resume flows read staged scalar status plus `agent-runs.jsonl`" in tracking,
            "tracking guide does not define the current scalar-plus-ledger read path",
        )
        self.assertTrue(
            "orchestration weight lives in the `status.md`" not in tracking,
            "tracking guide still requires orchestration metadata",
        )

        ledger = self._read("scripts/agent-run-ledger.py")
        retired_role_rejection = ledger.split("def build_event", 1)[1].split(
            "started_at =", 1
        )[0]
        for fragment in (
            "if args.execution_role in LEGACY_EXECUTION_ROLES:",
            "raise ValueError(",
            "retired legacy value",
            "routing belongs to the selected workflow, not executionRole",
        ):
            self.assertTrue(
                fragment in retired_role_rejection,
                f"agent-run-ledger retired-role rejection missing {fragment!r}",
            )
        self.assertTrue(
            "orchestration weight belongs in status.md 'orchestration:'" not in retired_role_rejection,
            "agent-run-ledger still recommends retired orchestration metadata",
        )

    def test_codex_hook_audit_has_a_mandatory_current_owner_path(self) -> None:
        root = self._read("src.codex/AGENTS.codex.md")
        for duty, present in codex_hook_referral_duties(root).items():
            with self.subTest(duty=duty):
                self.assertTrue(present, f"Codex hook referral missing {duty}")
        audit = codex_hook_audit_unit(self._read("src.codex/skills/lead/operating-model.md"))
        pin = next(pin for gap, pin, _ in PINS if gap == "A2-doc")
        self.assertIn(pin, audit)

    def test_codex_hook_referral_rejects_lost_or_misplaced_duties(self) -> None:
        root = self._read("src.codex/AGENTS.codex.md")
        unit = selected_unit(root, "Codex hook requirements and mandatory procedure", "Mandatory read:")
        self.assertTrue(all(codex_hook_referral_duties(root).values()))
        for before, after in (
            ("Any actor, regardless of profession", "Only Lead"),
            ("or diagnoses behavior based on hook contracts ", ""),
            ("MUST read", "may optionally read"),
            ("existing Lead operating-model", "old provider guide"),
            ("existing role-path and installation contracts", "current directory"),
            ("do not guess machine paths", "guess machine paths"),
            ("Unrelated work does not require this procedure", "All work requires this procedure"),
        ):
            with self.subTest(loss=before):
                self.assertIn(before, unit)
                mutant = root.replace(unit, unit.replace(before, after, 1), 1)
                self.assertFalse(all(codex_hook_referral_duties(mutant).values()))
        required_read = "MUST read the Codex hook procedure in the existing Lead operating-model"
        for changed in (
            unit.replace(required_read, required_read + " unless the current actor is busy", 1),
            unit + " Actors may ignore this procedure.",
            unit + " Source or installed Lead paths may instead be guessed.",
            unit.replace("does not require this procedure", "does not require this procedure unless requested by Lead", 1),
        ):
            with self.subTest(case="weakening-or-contrary-addition", changed=changed):
                self.assertNotEqual(changed, unit)
                mutant = root.replace(unit, changed, 1)
                self.assertFalse(codex_hook_referral_duties(mutant)["complete-referral"])
        formatted = root.replace(unit, unit.replace(" ", "  \n"), 1)
        self.assertTrue(all(codex_hook_referral_duties(formatted).values()))
        for decoy in ("", "\n## Unrelated policy\n**Mandatory read:** " + unit,
                      "\n```markdown\n**Mandatory read:** " + unit + "\n```"):
            with self.subTest(case="missing-live-referral", decoy=decoy):
                with self.assertRaises(AssertionError):
                    codex_hook_referral_duties(root.replace("**Mandatory read:** " + unit, "", 1) + decoy)
        owner = self._read("src.codex/skills/lead/operating-model.md")
        pin = next(pin for gap, pin, _ in PINS if gap == "A2-doc")
        self.assertIn(pin, codex_hook_audit_unit(owner))
        mutant = owner.replace(pin, "audit disabled", 1) + "\n## Historical copy\n" + pin
        self.assertNotIn(pin, codex_hook_audit_unit(mutant))

    def test_runtime_owner_map_rejects_lost_boundaries_and_decoy_rows(self) -> None:
        guide = self._read("docs/new-session-guide.md")
        self.assertTrue(all(runtime_owner_rows_present(guide).values()))
        for row in RUNTIME_OWNER_ROWS:
            for decoy in ("", "\n## Historical copy\n" + row,
                          "\n```markdown\n" + row + "\n```"):
                with self.subTest(row=row, decoy=decoy):
                    mutant = guide.replace(row, "", 1) + decoy
                    self.assertFalse(runtime_owner_rows_present(mutant)[row])
        skill_row = RUNTIME_OWNER_ROWS[0]
        for before, after in (
            ("for the current monorepo producer", "for all producers"),
            ("where the producer and actual binding establish it", "unconditionally"),
            ("Other layouts require their actual materialization owner.", ""),
            ("$HOME/.agents/skills/", "$HOME/.codex/skills/"),
            (".claude/skills/", ".claude/contracts/"),
        ):
            with self.subTest(loss=before):
                self.assertIn(before, skill_row)
                mutant = guide.replace(skill_row, skill_row.replace(before, after, 1), 1)
                self.assertFalse(runtime_owner_rows_present(mutant)[skill_row])

    def test_runtime_and_tracking_docs_name_current_owners(self) -> None:
        guide = self._read("docs/new-session-guide.md")
        for runtime_row, present in runtime_owner_rows_present(guide).items():
            with self.subTest(runtime_row=runtime_row):
                self.assertTrue(
                    present,
                    f"new-session runtime map missing or duplicate row {runtime_row!r}",
                )
        retired_runtime_claim = "| `~/.agents` | Legacy or stale personal skill surface."
        self.assertTrue(
            retired_runtime_claim not in guide,
            "new-session runtime map still labels the live global .agents surface as legacy",
        )

        tracking = self._read("docs/work-item-execution-tracking.md")
        for fragment in (
            "Only the root main conversation holding Lead writes `agent-runs.jsonl`",
            "Classify new work before creating recovery state",
            "quick-fix four-fact status or the staged lifecycle owner",
            "`agent-run-ledger init` is compatibility-only",
            "not a creation path for newly admitted work",
        ):
            self.assertTrue(
                fragment in tracking,
                f"work-item tracking guide missing ownership fragment {fragment!r}",
            )

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

    def test_implementation_professions_consume_only_selected_workflow_inputs(self) -> None:
        required = (
            "Take the approved execution scope, acceptance criteria and oracle, named regression "
            "guard, applicable domain constraints, and only the artifacts required by the selected "
            "workflow. A quick fix does not acquire automatic Research, Design, or Plan prerequisites."
        )
        refusal = (
            "Refuse implementation when an artifact or risk-owner constraint required by the selected "
            "workflow is missing, stale, or outside its accepted scope; do not manufacture or waive it."
        )
        for path in IMPLEMENTATION_PROFESSION_FILES:
            with self.subTest(path=path):
                text = self._read(path)
                self.assertIn(required, text)
                self.assertIn(refusal, text)
                self.assertNotIn("Require accepted research, design", text)

    def test_implementation_professions_do_not_treat_plan_as_cross_owner_authority(self) -> None:
        for path in IMPLEMENTATION_PROFESSION_FILES:
            with self.subTest(path=path):
                text = self._read(path)
                self.assertIn(
                    "inclusion in a Plan schedules accepted work but grants no authority",
                    text,
                )
                self.assertNotIn("unless the plan explicitly includes", text)

    def test_data_profession_requires_owner_contract_and_user_authorization_for_destructive_ddl(
        self,
    ) -> None:
        data_roles = (
            "src.codex/skills/data-engineer/SKILL.md",
            "src.claude/agents/data-engineer.md",
        )
        for path in data_roles:
            with self.subTest(path=path):
                text = self._read(path)
                self.assertIn(
                    "requires an accepted migration contract from the owning architecture or data authority plus "
                    "explicit user authorization for the destructive action",
                    text,
                )
                self.assertIn("Plan inclusion alone grants no destructive authority", text)
                self.assertNotIn("requires explicit plan approval", text)


if __name__ == "__main__":
    unittest.main()
