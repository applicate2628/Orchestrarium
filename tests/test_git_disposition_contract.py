"""Source-contract checks for the Lead Git-disposition checkpoint.

The scenario labels below pin the accepted instruction in both provider packs;
they are text-contract checks, not proof of agent runtime behavior.
"""

from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
LEAD_SKILLS = (
    "src.codex/skills/lead/SKILL.md",
    "src.claude/skills/lead/SKILL.md",
)
CHECKPOINT_POLICY_SURFACES = (
    "shared/AGENTS.shared.md",
    *LEAD_SKILLS,
    "src.codex/skills/lead/operating-model.md",
    "src.claude/agents/contracts/operating-model.md",
)
ROLLBACK_SAFETY_SURFACES = (
    "shared/AGENTS.shared.md",
    "src.codex/AGENTS.codex.md",
    "shared/references/spine/verification-and-decision-discipline.md",
)
RULE_LABEL = "**Git disposition checkpoint:**"

SCENARIO_FRAGMENTS = {
    "user-stop": (
        "the user explicitly parks it",
        "preserved state and a concrete resume point",
    ),
    "missing-approval": (
        "Missing approval is reported once",
        "blocks only dependent actions",
        "independent ready work continues",
    ),
    "rescue-route": (
        "offline or dirty rescue",
        "never forces publication when rescue was explicitly chosen",
    ),
    "same-repository-non-ancestor-fallback": (
        "Treat positive exact commit reachability as identity-preserving settlement evidence.",
        "Otherwise compare the intended target's patch/tree/content; non-ancestry alone cannot prove absence.",
    ),
    "scope-and-authority-negative-controls": (
        "Do not automatically admit unrelated open pull requests or backlog 2.0",
        "grants no authority",
        "creates no approval marker",
        "non-ancestry alone cannot prove absence",
    ),
}


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _rule(text: str) -> str:
    matches = [line for line in text.splitlines() if RULE_LABEL in line]
    if len(matches) != 1:
        raise AssertionError(
            f"expected exactly one {RULE_LABEL!r} rule, found {len(matches)}"
        )
    return matches[0]


class GitDispositionContractTests(unittest.TestCase):
    def test_provider_packs_project_one_identical_rule(self) -> None:
        rules = [_rule(_read(path)) for path in LEAD_SKILLS]

        self.assertEqual(rules[0], rules[1])

    def test_rule_covers_required_scenarios_and_negative_controls(self) -> None:
        for path in LEAD_SKILLS:
            rule = _rule(_read(path))
            for scenario, fragments in SCENARIO_FRAGMENTS.items():
                with self.subTest(path=path, scenario=scenario):
                    for fragment in fragments:
                        self.assertIn(fragment, rule)

    def test_open_gate_blocks_only_dependent_checkpoint_work(self) -> None:
        full_projection = (
            "Lead creates a timely local Git commit checkpoint",
            "coherent and separable",
            "staging only that scope",
            "Any open gate blocks its dependent changes",
            "unrelated ready work and eligible checkpoints continue",
            "neither completion nor publication",
            "Human review, leak checking, and explicit publication authority still govern push and release",
        )
        compact_shared_projection = (
            "Lead creates a timely local Git commit checkpoint",
            "coherent and separable",
            "staging only that scope",
            "An open gate blocks dependent changes, not unrelated ready work or eligible checkpoints",
            "neither completion nor publication",
            "Human review, leak checking, and explicit publication authority still govern push/release",
        )
        for path in CHECKPOINT_POLICY_SURFACES:
            text = _read(path)
            required = full_projection
            if path == "shared/AGENTS.shared.md" and all(
                fragment in text for fragment in compact_shared_projection
            ):
                required = compact_shared_projection
            with self.subTest(path=path):
                for fragment in required:
                    self.assertIn(fragment, text)
                self.assertNotIn(
                    "Do not begin install validation, commit, push, publication",
                    text,
                )
                self.assertNotIn(
                    "while primary review/verification is open, no install validation/commit/push/publication",
                    text,
                )

    def test_shared_rule_preserves_continuation_and_no_false_completion_tail(self) -> None:
        shared = _read("shared/AGENTS.shared.md")
        self.assertIn(
            "A passed plan/work-item slice is not goal completion: record it, reopen the plan, "
            "continue the next item or state its blocker. No final/\"what next?\" with known work",
            shared,
        )

    def test_destructive_history_rewrite_requires_preservation_preconditions(self) -> None:
        required = (
            "explicit user authority",
            "fresh dirty/index census",
            "preservation of every unrelated working-tree byte and staged change",
            "`git reset --hard HEAD~N`",
            "no other work depends on them",
            "nondestructive, reversible route",
        )
        for path in ROLLBACK_SAFETY_SURFACES:
            with self.subTest(path=path):
                text = _read(path)
                for fragment in required:
                    self.assertIn(fragment, text)


if __name__ == "__main__":
    unittest.main()
