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


if __name__ == "__main__":
    unittest.main()
