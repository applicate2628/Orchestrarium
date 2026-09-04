from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

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
    assert "maximum at any effort" in body
    assert "route evidence" in body.lower()
    assert MODULE.is_file()


@pytest.mark.parametrize(
    ("task_class", "route_evidence"),
    (
        ("mathematical-research", "mathematics-quality-floor"),
        ("scientific-agentic-workflow", "connected-science-workflow"),
        ("cross-system-synthesis", "cross-system-context-retention"),
    ),
)
def test_deep_math_science_and_cross_system_default_to_astra_medium(
    task_class: str,
    route_evidence: str,
) -> None:
    module = _load()
    result = module.resolve_v1_astra_route(
        task_class=task_class,
        available_models={"gpt-6-astra"},
        route_evidence=route_evidence,
    )
    assert result["status"] == "selected"
    assert result["model"] == "gpt-6-astra"
    assert result["effort"] == "medium"
    assert result["effortBasis"] == "task-default-medium"
    assert result["effortEvidence"] is None
    assert result["routeEvidence"] == route_evidence
    assert result["codexFlags"] == [
        "--model",
        "gpt-6-astra",
        "-c",
        "model_reasoning_effort=medium",
    ]
    assert result["requiresIndependentReview"] is True
    assert result["authorizing"] is False


def test_route_selection_evidence_is_required_and_task_specific() -> None:
    module = _load()
    missing = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models={"gpt-6-astra"},
    )
    assert missing["status"] == "denied"
    assert missing["stableId"] == "E_ASTRA_V1_ROUTE_EVIDENCE_REQUIRED"

    mismatch = module.resolve_v1_astra_route(
        task_class="scientific-agentic-workflow",
        available_models={"gpt-6-astra"},
        route_evidence="mathematics-quality-floor",
    )
    assert mismatch["stableId"] == "E_ASTRA_V1_ROUTE_EVIDENCE_MISMATCH"


def test_measured_cost_to_pass_requires_complete_strictly_better_costs() -> None:
    module = _load()
    missing = module.resolve_v1_astra_route(
        task_class="cross-system-synthesis",
        available_models={"gpt-6-astra"},
        route_evidence="measured-cost-to-pass",
    )
    assert missing["stableId"] == "E_ASTRA_V1_ECONOMICS_REQUIRED"

    not_better = module.resolve_v1_astra_route(
        task_class="cross-system-synthesis",
        available_models={"gpt-6-astra"},
        route_evidence="measured-cost-to-pass",
        astra_cost_microusd=2500,
        legacy_cost_microusd=2500,
    )
    assert not_better["stableId"] == "E_ASTRA_V1_ECONOMICS_NOT_BETTER"

    selected = module.resolve_v1_astra_route(
        task_class="cross-system-synthesis",
        available_models={"gpt-6-astra"},
        route_evidence="measured-cost-to-pass",
        astra_cost_microusd=2400,
        legacy_cost_microusd=3000,
    )
    assert selected["status"] == "selected"
    assert selected["costComparison"] == {
        "astraCostMicroUsd": 2400,
        "legacyCostMicroUsd": 3000,
        "savingsMicroUsd": 600,
    }


def test_recovery_defaults_high() -> None:
    module = _load()
    result = module.resolve_v1_astra_route(
        task_class="critical-recovery",
        available_models={"gpt-6-astra"},
        route_evidence="verified-frontier-recovery",
    )
    assert result["status"] == "selected"
    assert result["effort"] == "high"
    assert result["effortBasis"] == "task-default-high"


def test_recovery_downshift_to_medium_requires_evidence() -> None:
    module = _load()
    denied = module.resolve_v1_astra_route(
        task_class="critical-recovery",
        available_models={"gpt-6-astra"},
        route_evidence="verified-frontier-recovery",
        requested_effort="medium",
    )
    assert denied["stableId"] == "E_ASTRA_V1_EFFORT_EVIDENCE_REQUIRED"

    selected = module.resolve_v1_astra_route(
        task_class="critical-recovery",
        available_models={"gpt-6-astra"},
        route_evidence="verified-frontier-recovery",
        requested_effort="medium",
        effort_evidence="measured-sufficient",
    )
    assert selected["status"] == "selected"
    assert selected["effort"] == "medium"
    assert selected["economicsEvidence"] == "objective-recovery"


def test_effort_evidence_never_authorizes_the_route_itself() -> None:
    module = _load()
    result = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models={"gpt-6-astra"},
        requested_effort="high",
        effort_evidence="medium-objective-failure",
    )
    assert result["stableId"] == "E_ASTRA_V1_ROUTE_EVIDENCE_REQUIRED"


def test_max_requires_explicit_human_approval() -> None:
    module = _load()
    denied = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models={"gpt-6-astra"},
        route_evidence="mathematics-quality-floor",
        requested_effort="max",
    )
    assert denied["status"] == "denied"
    assert denied["stableId"] == "E_ASTRA_V1_MAX_APPROVAL_REQUIRED"

    admitted = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models={"gpt-6-astra"},
        route_evidence="mathematics-quality-floor",
        requested_effort="max",
        allow_max_effort=True,
    )
    assert admitted["status"] == "selected"
    assert admitted["effort"] == "max"
    assert admitted["effortBasis"] == "explicit-human-approval"


def test_unused_max_approval_and_astra_none_fail_closed() -> None:
    module = _load()
    orphan_approval = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models={"gpt-6-astra"},
        route_evidence="mathematics-quality-floor",
        allow_max_effort=True,
    )
    assert orphan_approval["stableId"] == "E_ASTRA_V1_MAX_APPROVAL_INVALID"

    none = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models={"gpt-6-astra"},
        route_evidence="mathematics-quality-floor",
        requested_effort="none",
    )
    assert none["stableId"] == "E_ASTRA_V1_EFFORT_UNSUPPORTED"


def test_unavailable_astra_has_no_silent_fallback() -> None:
    module = _load()
    result = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models={"gpt-5.6-sol"},
        route_evidence="mathematics-quality-floor",
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


@pytest.mark.parametrize(
    ("effort", "evidence"),
    (
        ("high", "medium-objective-failure"),
        ("xhigh", "high-objective-failure"),
    ),
)
def test_nondefault_efforts_require_matching_evidence(
    effort: str, evidence: str
) -> None:
    module = _load()
    denied = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models={"gpt-6-astra"},
        route_evidence="mathematics-quality-floor",
        requested_effort=effort,
    )
    assert denied["status"] == "denied"
    assert denied["stableId"] == "E_ASTRA_V1_EFFORT_EVIDENCE_REQUIRED"

    selected = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models={"gpt-6-astra"},
        route_evidence="mathematics-quality-floor",
        requested_effort=effort,
        effort_evidence=evidence,
    )
    assert selected["status"] == "selected"
    assert selected["effort"] == effort
    assert selected["effortEvidence"] == evidence


def test_orphan_unknown_or_unneeded_effort_evidence_is_denied() -> None:
    module = _load()
    orphan = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models={"gpt-6-astra"},
        route_evidence="mathematics-quality-floor",
        effort_evidence="measured-sufficient",
    )
    assert orphan["stableId"] == "E_ASTRA_V1_EFFORT_EVIDENCE_INVALID"

    unknown = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models={"gpt-6-astra"},
        route_evidence="mathematics-quality-floor",
        requested_effort="high",
        effort_evidence="because-hard",
    )
    assert unknown["stableId"] == "E_ASTRA_V1_EFFORT_EVIDENCE_INVALID"

    default_with_evidence = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models={"gpt-6-astra"},
        route_evidence="mathematics-quality-floor",
        requested_effort="medium",
        effort_evidence="migration-evaluation",
    )
    assert default_with_evidence["stableId"] == "E_ASTRA_V1_EFFORT_EVIDENCE_INVALID"


def test_automatic_astra_fanout_is_exactly_one() -> None:
    module = _load()
    for fanout in (0, 2, True):
        result = module.resolve_v1_astra_route(
            task_class="scientific-agentic-workflow",
            available_models={"gpt-6-astra"},
            route_evidence="connected-science-workflow",
            requested_fanout=fanout,
        )
        expected = (
            "E_ASTRA_V1_REQUEST_INVALID"
            if fanout is True
            else "E_ASTRA_V1_FANOUT_LIMIT"
        )
        assert result["status"] == "denied"
        assert result["stableId"] == expected


def test_request_shape_rejects_string_model_inventory_and_bad_types() -> None:
    module = _load()
    invalid_inventory = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models="gpt-6-astra",
        route_evidence="mathematics-quality-floor",
    )
    assert invalid_inventory["stableId"] == "E_ASTRA_V1_REQUEST_INVALID"

    invalid_approval = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models={"gpt-6-astra"},
        route_evidence="mathematics-quality-floor",
        allow_max_effort=1,
    )
    assert invalid_approval["stableId"] == "E_ASTRA_V1_REQUEST_INVALID"

    bool_cost = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models={"gpt-6-astra"},
        route_evidence="measured-cost-to-pass",
        astra_cost_microusd=True,
        legacy_cost_microusd=10,
    )
    assert bool_cost["stableId"] == "E_ASTRA_V1_REQUEST_INVALID"


def test_cli_emits_deterministic_json_and_nonzero_for_denial() -> None:
    selected = subprocess.run(
        [
            sys.executable,
            "-S",
            str(MODULE),
            "--task-class",
            "mathematical-research",
            "--available-model",
            "gpt-6-astra",
            "--route-evidence",
            "mathematics-quality-floor",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert selected.returncode == 0
    assert json.loads(selected.stdout)["effort"] == "medium"
    assert selected.stderr == ""

    denied = subprocess.run(
        [
            sys.executable,
            "-S",
            str(MODULE),
            "--task-class",
            "mathematical-research",
            "--available-model",
            "gpt-6-astra",
            "--route-evidence",
            "mathematics-quality-floor",
            "--effort",
            "xhigh",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert denied.returncode == 2
    assert json.loads(denied.stdout)["stableId"] == "E_ASTRA_V1_EFFORT_EVIDENCE_REQUIRED"


def test_provider_prompt_accepts_returned_astra_flags_when_full_repo_is_present() -> None:
    provider_prompt = ROOT / "scripts" / "provider_prompt.py"
    if not provider_prompt.is_file():
        pytest.skip("partial fixture does not include provider_prompt.py")
    spec = importlib.util.spec_from_file_location(
        "provider_prompt_astra_v1_test", provider_prompt
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    flags = ["--model", "gpt-6-astra", "-c", "model_reasoning_effort=medium"]
    frozen, model, effort = module.normalize_launch_profile("codex", flags)
    assert frozen == tuple(flags)
    assert model == "gpt-6-astra"
    assert effort == "medium"
