"""Source-fixture guard for the computational-scientist mode contract.

These tests constrain the shipped role instructions; they do not execute a
reviewer and therefore cannot prove provider-runtime conformance.  The owning
workflow's independent behavior audit supplies that evidence.
"""

from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ROLE_PATHS = (
    ROOT / "src.codex" / "skills" / "computational-scientist" / "SKILL.md",
    ROOT / "src.claude" / "agents" / "computational-scientist.md",
)


def _section(text: str, heading: str) -> str:
    start = text.index(f"## {heading}")
    end = text.find("\n## ", start + len(heading) + 3)
    return text[start:] if end == -1 else text[start:end]


@pytest.fixture(params=ROLE_PATHS, ids=("codex", "claude"))
def role_text(request: pytest.FixtureRequest) -> str:
    return request.param.read_text(encoding="utf-8")


def test_modeling_mode_keeps_its_existing_package_and_gate(role_text: str) -> None:
    selection = _section(role_text, "Mode selection")
    assert "Modeling mode is the default" in selection
    assert "apply unchanged" in selection
    assert "instead of the modeling-only input, artifact, and gate requirements" in selection

    assert "Return one computational model package" in _section(
        role_text, "Return exactly one artifact"
    )
    gate = _section(role_text, "Gate")
    assert "symbol table with units for every variable" in gate
    assert "No implementation code is included." in gate


def test_conformance_mode_has_complete_inputs_and_one_to_one_s4_output(
    role_text: str,
) -> None:
    review = _section(role_text, "Scientific-conformance-review mode")
    for required_input in (
        "accepted computational model artifact and revision",
        "existing numbered claims",
        "scientific implementation artifact and revision",
        "implementation evidence",
        "approved scope",
        "author and run identity",
    ):
        assert required_input in review
    assert "one scientific conformance report" in review
    assert "every upstream claim 1:1 and in its existing order" in review
    assert "`verified | failed | not-verifiable (with reason)`" in review
    assert "ends with exactly one overall `PASS | REVISE | BLOCKED` decision" in review


def test_conformance_mode_revises_unit_tolerance_drift_and_self_review(
    role_text: str,
) -> None:
    review = _section(role_text, "Scientific-conformance-review mode")
    assert "A changed unit or tolerance is a failed claim and requires `REVISE`." in review
    assert "If the conformance author or run identity matches the implementation author or run identity, return `REVISE`" in review
    assert "PASS requires every mandatory claim `verified`, no unexplained model deviation, and no self-review." in review


def test_conformance_mode_is_review_only_and_separate_from_generic_qa(
    role_text: str,
) -> None:
    review = _section(role_text, "Scientific-conformance-review mode")
    assert "independent of the Scientific Software Engineer run" in review
    assert "must not change implementation code, physics, equations, assumptions, scientific settings, units, tolerances, or the accepted model" in review
    assert "Return every required change or deviation to its existing owner." in review
    assert "Generic Quality Assurance remains a separate gate and is unchanged." in review
    assert "does not prove that a conformance reviewer ran or that provider-runtime behavior complied" in review


def test_provider_projections_share_the_same_mode_contract() -> None:
    codex, claude = (path.read_text(encoding="utf-8") for path in ROLE_PATHS)
    assert _section(codex, "Mode selection") == _section(claude, "Mode selection")
    assert _section(codex, "Scientific-conformance-review mode") == _section(
        claude, "Scientific-conformance-review mode"
    )
