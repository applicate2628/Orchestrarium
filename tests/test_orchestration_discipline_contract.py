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

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SPINE = "shared/AGENTS.shared.md"

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
    # (RELEASE_NOTES.md :153) that the global install carries no repo-specific dev
    # tooling — this pin deliberately does NOT assert the validator is installed.
    ("A5b-run", "hardening invariants 7-8 (failed-lane-is-unverified, fail-closed aggregation);",
     ["src.claude/commands/agents-review-loop.md", "src.codex/skills/review-loop/SKILL.md"]),

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
    ("A7-rule", "Before dispatch, fill `Diff-invisible invariants` and `Named regression guard`; `none` is valid only with a one-line reason.",
     ["src.claude/agents/contracts/subagent-contracts.md", "src.codex/skills/lead/subagent-contracts.md"]),

    # A3 — index sync on every active-item state change (row + bullet; case differs, use common substring)
    ("A3", "active-item state change (create, resume, stage transition, park, close, archive)",
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


if __name__ == "__main__":
    unittest.main()
