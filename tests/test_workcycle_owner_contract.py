"""Focused contract guard for work-cycle ownership at dispatch boundaries.

These instructions are the shipped behavior surface, so the test checks the
ordered decisions each provider must present. It does not claim that either
host enforces the recipe.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

LEAD_CONTRACTS = (
    # Both selected clients install this canonical body; the old Claude copy
    # remains a frozen migration input, not the current policy owner.
    ROOT / "src.codex" / "skills" / "lead" / "SKILL.md",
)
ARCHIVIST_CONTRACTS = (
    ROOT / "src.codex" / "skills" / "knowledge-archivist" / "SKILL.md",
    ROOT / 'adapters/claude' / "agents" / "knowledge-archivist.md",
)
SHARED_MODEL = ROOT / "shared" / "references" / "subagent-operating-model.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(path: Path, heading: str) -> str:
    text = _read(path)
    level = len(heading) - len(heading.lstrip("#"))
    match = re.search(
        rf"^{re.escape(heading)}\s*$\n(?P<body>.*?)(?=^#{{1,{level}}}\s|\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"{path}: missing {heading}"
    return re.sub(r"\s+", " ", match.group("body")).strip()


def test_lead_recipe_encodes_the_ordered_work_cycle_without_widening_admission() -> None:
    for path in LEAD_CONTRACTS:
        recipe = _section(path, "## Work-cycle ownership recipe")
        numbered = [int(value) for value in re.findall(r"(?<!\S)([1-5])\. ", recipe)]
        assert numbered == [1, 2, 3, 4, 5], path

        ordered_obligations = (
            "exactly one admitted work-item",
            "remain active concurrently",
            "create or select its own work-item before dispatch",
            "exact Root-created `launchRunId`",
            "one bounded `$knowledge-archivist` reconciliation",
        )
        offsets = [recipe.index(fragment) for fragment in ordered_obligations]
        assert offsets == sorted(offsets), path

        for field in ("`Task`", "`Scope boundary`", "`Next action`"):
            assert field in recipe, (path, field)
        assert "Standalone bounded fact lookup remains inline" in recipe, path
        assert "side question that does not become separately admitted work" in recipe, path
        assert "does not park or close" in recipe, path
        assert "not host enforcement" in recipe, path


def test_archivist_reconciles_changed_sets_through_the_lifecycle_owner() -> None:
    obligations = (
        "newly admitted, parked, or closed item",
        "delivery-wave or milestone boundary",
        "material status, ledger, or location drift",
        "stable active-item set",
        "lifecycle owner's parser and roll-up",
        "list-form `- context:`",
        "heading scan",
        "Structural `PASS` does not prove semantic currency",
    )
    for path in ARCHIVIST_CONTRACTS:
        text = _read(path)
        for obligation in obligations:
            assert obligation in text, (path, obligation)


def test_shared_recipe_is_provider_neutral_and_preserves_independent_items() -> None:
    recipe = _section(SHARED_MODEL, "#### Dispatch-boundary work-cycle recipe")
    for obligation in (
        "exactly one admitted work-item",
        "Independent authorized items may remain active concurrently",
        "Apply dispatch admission before a non-trivial provider or subagent dispatch",
        "Root uses its exact launch identity for native and direct external equivalents",
        "for an actual wrapper execution Root consumes actual IDs and persisted terminal readback without a second pair",
        "stable active-item set",
    ):
        assert obligation in recipe, obligation
    assert "Codex" not in recipe
    assert "Claude" not in recipe
