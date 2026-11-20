"""Focused source contracts plus deterministic numerical fixture seeds.

These checks are not evidence that any provider followed the role instructions.
"""

from pathlib import Path


SKILLS = Path(__file__).resolve().parents[1] / "src.codex" / "skills"


def skill(role: str) -> str:
    return (SKILLS / role / "SKILL.md").read_text(encoding="utf-8")


def test_algorithm_names_algebra_and_conditioning():
    text = skill("algorithm-scientist")
    assert "unsigned bitwise XOR" in text
    assert "every permitted intermediate" in text
    assert "problem conditioning" in text and "backward error" in text
    assert "The int64 reduction is exactly associative" not in text


def test_computational_science_pairs_evidence_with_the_claim_it_can_verify():
    text = skill("computational-scientist")
    assert "Code verification" in text and "Solution verification" in text
    assert "Physical validation" in text and "independent measurements" in text
    assert "Cross-code agreement is supporting evidence" in text
    assert "wrong evidence class" in text


def test_scientific_software_oracle_rejects_a_plausible_defect():
    text = skill("scientific-software-engineer")
    assert "oracle sensitivity" in text
    assert "deliberate wrong sign" in text
    assert "directional Taylor check" in text


def test_geometry_separates_predicates_constructions_and_physical_tolerance():
    text = skill("geometry-engineer")
    assert "certified sign" in text
    assert "constructed coordinates" in text
    assert "physical or snapping tolerance" in text
    assert "as exact arithmetic or epsilon tolerance" not in text


def test_graphics_checks_resource_lifetime_beyond_one_frame():
    text = skill("graphics-engineer")
    assert "synchronization validation" in text
    assert "deferred presentation" in text
    assert "tail frame time" in text


def test_visualization_checks_task_truth_and_non_color_path():
    text = skill("visualization-engineer")
    assert "data-domain oracle" in text
    assert "without relying on color alone" in text
    assert "A screenshot is not a data oracle" in text


def test_vak_norm_download_and_reviews_do_not_assume_authority():
    text = skill("vak-dissertation-review")
    norms = (SKILLS / "vak-dissertation-review/references/vak-norms.md").read_text(
        encoding="utf-8"
    )
    assert "degree type" in norms and "effective date" in norms
    assert "Typical threshold" not in norms and "действ. ред." not in norms
    assert "permission-scoped reviewer" in text and "readiness remains unverified" in text
    assert "only when DOCX output is requested" in text


def test_near_collinear_orientation_fixture_exposes_roundoff():
    n = 2**27
    assert n * n - (n + 1) * (n - 1) == 1
    assert float(n) * float(n) - float(n + 1) * float(n - 1) == 0
