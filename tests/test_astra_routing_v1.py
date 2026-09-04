from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODEX_ROOT = ROOT / "src.codex" / "skills" / "astra-routing"
MODULE = CODEX_ROOT / "scripts" / "resolve.py"


def _load():
    spec = importlib.util.spec_from_file_location("astra_routing_v1_test", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_skill_has_codex_metadata_and_projection_safe_provider_neutral_body() -> None:
    body = (CODEX_ROOT / "SKILL.md").read_text(encoding="utf-8")
    metadata = (CODEX_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
    assert "name: astra-routing" in body
    assert "existing approved external Codex wrapper" in body
    assert "Astra Routing" in metadata
    assert MODULE.is_file()


def test_math_science_and_cross_system_default_to_astra_medium() -> None:
    module = _load()
    for task_class in (
        "mathematical-research",
        "scientific-agentic-workflow",
        "cross-system-synthesis",
    ):
        result = module.resolve_v1_astra_route(
            task_class=task_class,
            available_models={"gpt-6-astra"},
        )
        assert result["status"] == "selected"
        assert result["model"] == "gpt-6-astra"
        assert result["effort"] == "medium"
        assert result["codexFlags"] == [
            "--model",
            "gpt-6-astra",
            "-c",
            "model_reasoning_effort=medium",
        ]


def test_recovery_defaults_high_and_max_requires_explicit_approval() -> None:
    module = _load()
    recovery = module.resolve_v1_astra_route(
        task_class="critical-recovery",
        available_models={"gpt-6-astra"},
    )
    assert recovery["effort"] == "high"

    denied = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models={"gpt-6-astra"},
        requested_effort="max",
    )
    assert denied["status"] == "denied"
    assert denied["stableId"] == "E_ASTRA_V1_MAX_APPROVAL_REQUIRED"

    admitted = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models={"gpt-6-astra"},
        requested_effort="max",
        allow_max_effort=True,
    )
    assert admitted["status"] == "selected"
    assert admitted["effort"] == "max"


def test_unavailable_astra_has_no_silent_fallback() -> None:
    module = _load()
    result = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models={"gpt-5.6-sol"},
    )
    assert result["status"] == "unavailable"
    assert result["stableId"] == "E_ASTRA_V1_UNAVAILABLE"
    assert result["fallback"] == "none"
    assert result["model"] is None
    assert result["codexFlags"] == []


def test_noneligible_work_returns_to_legacy_v1_policy() -> None:
    module = _load()
    result = module.resolve_v1_astra_route(
        task_class="engineering",
        available_models={"gpt-6-astra"},
    )
    assert result["status"] == "not-applicable"
    assert result["stableId"] == "E_ASTRA_V1_ROUTE_NOT_APPLICABLE"
    assert result["selectionBasis"] == "legacy-v1-routing"


def test_low_high_and_xhigh_require_matching_effort_evidence() -> None:
    module = _load()
    cases = (
        ("low", None, "migration-evaluation"),
        ("high", None, "medium-objective-failure"),
        ("xhigh", None, "high-objective-failure"),
    )
    for effort, _unused, evidence in cases:
        denied = module.resolve_v1_astra_route(
            task_class="mathematical-research",
            available_models={"gpt-6-astra"},
            requested_effort=effort,
        )
        assert denied["status"] == "denied"
        assert denied["stableId"] == "E_ASTRA_V1_EFFORT_EVIDENCE_REQUIRED"

        selected = module.resolve_v1_astra_route(
            task_class="mathematical-research",
            available_models={"gpt-6-astra"},
            requested_effort=effort,
            effort_evidence=evidence,
        )
        assert selected["status"] == "selected"
        assert selected["effort"] == effort
        assert selected["effortEvidence"] == evidence


def test_orphan_or_unknown_effort_evidence_is_denied() -> None:
    module = _load()
    orphan = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models={"gpt-6-astra"},
        effort_evidence="measured-sufficient",
    )
    assert orphan["stableId"] == "E_ASTRA_V1_EFFORT_EVIDENCE_INVALID"

    unknown = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models={"gpt-6-astra"},
        requested_effort="high",
        effort_evidence="because-hard",
    )
    assert unknown["stableId"] == "E_ASTRA_V1_EFFORT_EVIDENCE_INVALID"


def test_automatic_astra_fanout_is_one() -> None:
    module = _load()
    result = module.resolve_v1_astra_route(
        task_class="scientific-agentic-workflow",
        available_models={"gpt-6-astra"},
        requested_fanout=2,
    )
    assert result["status"] == "denied"
    assert result["stableId"] == "E_ASTRA_V1_FANOUT_LIMIT"
