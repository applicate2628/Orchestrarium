"""Target-scoped source guidance, not proof of runtime instruction loading."""
from pathlib import Path
import re

import pytest

from policy_text_contract import relationships, selected_section, selected_unit

ROOT = Path(__file__).resolve().parents[1]
SPINE = ROOT / "shared/AGENTS.shared.md"
REFERENCE = ROOT / "shared/references/repository-source-hygiene.md"
SECTION = "Scope and ownership discipline"
OWNER = "Repository orientation; Mechanism inventory before new paths:"
REQUIRED = {
    "target_discovery": (
        "For every additional directory or repository touched, including parallel "
        "assignments, first discover/read the applicable AGENTS.md chain and "
        "host-supported overrides under Context handoff economy"
    ),
    "subtree_scope": "deeper rules apply only to their subtree",
    "no_implicit_reload": (
        "Do not assume the original cwd's loaded instructions cover other work "
        "areas or that a shell directory change reloads them"
    ),
    "receiver_bound_reuse": (
        "Reuse unchanged guidance within the same scope only when present in "
        "the receiver's actual context"
    ),
    "trusted_missing_context": (
        "supply missing or uncertain target instructions through the existing "
        "trusted input path before relying on them, without expanding permissions"
    ),
}


def _check(source: str) -> None:
    unit = selected_unit(source, SECTION, OWNER)
    result = relationships(unit, REQUIRED)
    assert all(result.values()), result


def test_orientation_requires_target_scoped_instruction_discovery() -> None:
    source = SPINE.read_text(encoding="utf-8")
    _check(source)
    unit = selected_unit(source, SECTION, OWNER)
    assert not re.search(r"[A-Za-z]:[\\/]", unit)
    assert "bug inbox" not in unit.casefold()


@pytest.mark.parametrize("requirement", REQUIRED)
def test_missing_or_negated_target_duty_cannot_be_rescued_elsewhere(requirement: str) -> None:
    source = SPINE.read_text(encoding="utf-8")
    _check(source)
    unit = selected_unit(source, SECTION, OWNER)
    phrase = REQUIRED[requirement]
    for replacement in ("This duty is unavailable", "Do not " + phrase, "Optional example only: " + phrase):
        mutated = unit.replace(phrase, replacement, 1)
        assert mutated != unit
        outside = "\n\n## Historical example\n\n" + phrase + "\n"
        with pytest.raises(AssertionError):
            _check(source.replace(unit, mutated, 1) + outside)


def test_example_cannot_replace_the_binding_orientation_owner() -> None:
    source = SPINE.read_text(encoding="utf-8")
    _check(source)
    unit = selected_unit(source, SECTION, OWNER)
    with pytest.raises(AssertionError):
        _check(source.replace(unit, "\n```text\n" + unit + "\n```\n", 1))


def test_reference_keeps_discovery_with_orientation_and_current_handoff_owner() -> None:
    section = selected_section(REFERENCE.read_text(encoding="utf-8"),
                               "Instruction scope across work areas")
    for required in (
        "Repository orientation; Mechanism inventory before new paths",
        "every additional directory/repository, including parallel assignments",
        "Context handoff economy",
        "receiver's actual context",
        "existing trusted input path",
        "does not expand permissions",
        "not a guarantee of automatic host loading",
    ):
        assert required in section
