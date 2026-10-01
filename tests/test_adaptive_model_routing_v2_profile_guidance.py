"""Keep normative profile owners aligned; these are not runtime admission tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

V2 = Path(__file__).resolve().parents[1] / "docs/model-routing-v2"


def _section(name: str, heading: str) -> str:
    text = (V2 / name).read_text(encoding="utf-8")
    return text.split(heading + "\n", 1)[1].split("\n## ", 1)[0]


def test_admission_guidance_places_capability_evidence_on_exact_profile():
    schema = json.loads((V2 / "adaptive-routing-contracts.v2.schema.json").read_text(encoding="utf-8"))
    entry = schema["$defs"]["modelRegistrySnapshot"]["$defs"]["runtimeEntry"]
    assert "profileEvaluations" in entry["properties"]
    assert "capabilities" not in entry["properties"]
    text = _section(
        "runtime-validation-obligations.md",
        "## 5. Policy precedence, registry, and provider admission",
    )
    assert "capability identifiers are unique per entry" not in text
    assert "capability identifiers are unique within each profile evaluation" in text
    assert "`profileEvaluationId`" in text
    assert "evaluated capabilities" in text


@pytest.mark.parametrize("name,heading", [
    ("runtime-validation-obligations.md", "## 5. Policy precedence, registry, and provider admission"),
    ("deep-review-operational-hardening.md", "## 11. Cross-record validator obligations"),
])
def test_normative_validation_guidance_binds_actual_profile_and_its_context(name, heading):
    text = _section(name, heading)
    assert "`profileEvaluationId`" in text
    for aspect in ("runtime", "effort", "task", "context"):
        assert aspect in text
    assert "](effort-profile-evidence.md" in text
