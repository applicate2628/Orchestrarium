from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from model_routing_v2_support import (
    CATALOG,
    MODULE,
    POLICY,
    ROOT,
    _call,
    _contracts,
    _estimate,
    _load,
    _request,
    _resolve,
)

def test_optimize_requires_matching_objective_evidence_and_complete_candidate_set() -> None:
    estimates = {
        "sol-xhigh": _estimate("sol-xhigh"),
        "astra-medium": _estimate("astra-medium"),
    }
    mismatch = _resolve(
        _request(
            mode="optimize",
            objective="tokens",
            routeEvidence="measured-api-cost-to-pass",
            routeEstimates=estimates,
        )
    )
    assert mismatch["stableId"] == "E_MODEL_V2_ROUTE_EVIDENCE_OBJECTIVE_MISMATCH"

    incomplete = _resolve(
        _request(
            mode="optimize",
            objective="tokens",
            routeEvidence="measured-route-efficiency",
            routeEstimates={"astra-medium": estimates["astra-medium"]},
        )
    )
    assert incomplete["stableId"] == "E_MODEL_V2_CANDIDATE_SET_INCOMPLETE"


def test_tokens_objective_can_choose_astra_even_when_single_call_cost_is_higher() -> None:
    sol = _estimate(
        "sol-xhigh",
        primary_call=_call("sol-xhigh", uncached=100000, output=20000, elapsed=4000),
        extra_calls=[
            _call("sol-xhigh", stage="retry", uncached=100000, output=15000, elapsed=3500)
        ],
        steps=5,
        wall_time=9000,
        rework=1,
        attempted=2,
        accepted=1,
    )
    astra = _estimate(
        "astra-medium",
        primary_call=_call("astra-medium", uncached=100000, output=8000, elapsed=3000),
        steps=2,
        wall_time=3500,
    )
    result = _resolve(
        _request(
            mode="optimize",
            objective="tokens",
            routeEvidence="measured-route-efficiency",
            routeEstimates={"sol-xhigh": sol, "astra-medium": astra},
        )
    )
    assert result["status"] == "selected"
    assert result["selectedProfile"] == "astra-medium"
    assert result["objective"] == "tokens"
    assert result["metrics"]["directRetryCalls"] == 0


def test_api_cost_objective_can_keep_sol_when_complete_route_is_cheaper() -> None:
    sol = _estimate(
        "sol-xhigh",
        primary_call=_call("sol-xhigh", uncached=1000, output=100),
    )
    astra = _estimate(
        "astra-medium",
        primary_call=_call("astra-medium", uncached=1000, output=100),
    )
    result = _resolve(
        _request(
            mode="optimize",
            objective="api-cost",
            routeEvidence="measured-api-cost-to-pass",
            routeEstimates={"sol-xhigh": sol, "astra-medium": astra},
        )
    )
    assert result["selectedProfile"] == "sol-xhigh"


def test_steps_and_latency_objectives_are_separate_from_aggregate_call_time() -> None:
    sol = _estimate(
        "sol-xhigh",
        primary_call=_call("sol-xhigh", elapsed=100),
        extra_calls=[_call("sol-xhigh", stage="support", elapsed=100)],
        steps=6,
        wall_time=1000,
    )
    astra = _estimate(
        "astra-medium",
        primary_call=_call("astra-medium", elapsed=900),
        steps=2,
        wall_time=500,
    )
    by_steps = _resolve(
        _request(
            mode="optimize",
            objective="steps",
            routeEvidence="measured-route-efficiency",
            routeEstimates={"sol-xhigh": sol, "astra-medium": astra},
        )
    )
    by_latency = _resolve(
        _request(
            mode="optimize",
            objective="latency",
            routeEvidence="measured-route-efficiency",
            routeEstimates={"sol-xhigh": sol, "astra-medium": astra},
        )
    )
    assert by_steps["selectedProfile"] == "astra-medium"
    assert by_latency["selectedProfile"] == "astra-medium"
    assert by_latency["metrics"]["routeWallTimeMs"] == 500
    assert by_latency["metrics"]["aggregateCallElapsedMs"] == 1400


def test_long_context_multiplier_applies_per_call_not_to_route_total() -> None:
    module = _load()
    catalog, policy = _contracts()
    below = _call("astra-medium", uncached=272000, output=100)
    above = _call("astra-medium", uncached=272001, output=100)
    below_cost = module._call_cost(below, catalog, policy)
    above_cost = module._call_cost(above, catalog, policy)
    assert above_cost > below_cost

    split = module._call_cost(
        _call("astra-medium", uncached=150000, output=50), catalog, policy
    )
    split += module._call_cost(
        _call("astra-medium", uncached=150000, output=50), catalog, policy
    )
    combined = module._call_cost(
        _call("astra-medium", uncached=300000, output=100), catalog, policy
    )
    assert combined > split


def test_review_role_required_and_provider_independence_reported_separately() -> None:
    no_review = _estimate("astra-medium")
    no_review["calls"] = [no_review["calls"][0]]
    no_review["coordinationSteps"] = 1
    result = _resolve(
        _request(
            mode="optimize",
            objective="tokens",
            routeEvidence="measured-route-efficiency",
            routeEstimates={
                "sol-xhigh": _estimate("sol-xhigh"),
                "astra-medium": no_review,
            },
        )
    )
    assert result["stableId"] == "E_MODEL_V2_INDEPENDENT_REVIEW_REQUIRED"

    selected = _resolve(
        _request(
            mode="optimize",
            objective="tokens",
            routeEvidence="measured-route-efficiency",
            routeEstimates={
                "sol-xhigh": _estimate("sol-xhigh"),
                "astra-medium": _estimate("astra-medium"),
            },
        )
    )
    assert selected["requiresIndependentReview"] is True
    assert selected["providerIndependentReview"] is False
    assert selected["metrics"]["reviewEvidenceIndependenceGroups"] == ["openai"]


def test_estimates_must_be_comparable_and_pass_quality_floor() -> None:
    incomparable = _resolve(
        _request(
            mode="optimize",
            objective="tokens",
            routeEvidence="measured-route-efficiency",
            routeEstimates={
                "sol-xhigh": _estimate("sol-xhigh", comparison="one"),
                "astra-medium": _estimate("astra-medium", comparison="two"),
            },
        )
    )
    assert incomparable["stableId"] == "E_MODEL_V2_ESTIMATES_NOT_COMPARABLE"

    no_quality = _resolve(
        _request(
            mode="optimize",
            objective="tokens",
            routeEvidence="measured-route-efficiency",
            routeEstimates={
                "sol-xhigh": _estimate("sol-xhigh", quality=False),
                "astra-medium": _estimate("astra-medium", quality=False),
            },
        )
    )
    assert no_quality["stableId"] == "E_MODEL_V2_QUALITY_FLOOR_UNMET"


def test_retry_rework_and_acceptance_probability_affect_expected_metrics() -> None:
    estimate = _estimate(
        "astra-medium",
        extra_calls=[_call("astra-medium", stage="retry")],
        steps=4,
        rework=2,
        attempted=3,
        accepted=1,
    )
    result = _resolve(
        _request(
            mode="optimize",
            objective="tokens",
            routeEvidence="measured-route-efficiency",
            routeEstimates={
                "sol-xhigh": _estimate("sol-xhigh", attempted=1, accepted=1),
                "astra-medium": estimate,
            },
        )
    )
    astra_metrics = next(
        item["metrics"] for item in result["comparison"] if item["profile"] == "astra-medium"
    )
    assert astra_metrics["directRetryCalls"] == 1
    assert astra_metrics["expectedRetryCalls"] == {"numerator": 3, "denominator": 1}
    assert astra_metrics["directReworkCycles"] == 2
    assert astra_metrics["expectedReworkCycles"] == {"numerator": 6, "denominator": 1}


def test_bool_numeric_fields_and_malformed_contracts_fail_closed() -> None:
    bad_request = _request(requestedFanout=True)
    assert _resolve(bad_request)["stableId"] == "E_MODEL_V2_REQUEST_INVALID"

    catalog, policy = _contracts()
    broken = copy.deepcopy(catalog)
    broken["models"]["astra"]["supportedEfforts"].append("none")
    result = _resolve(_request(), catalog=broken, policy=policy)
    assert result["stableId"] == "E_MODEL_V2_CATALOG_INVALID"


def test_cli_is_deterministic_and_nonzero_on_denial(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(_request(), sort_keys=True), encoding="utf-8")
    first = subprocess.run(
        [sys.executable, "-S", str(MODULE), "--request", str(request_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    second = subprocess.run(
        [sys.executable, "-S", str(MODULE), "--request", str(request_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert first.returncode == 0
    assert first.stdout == second.stdout
    assert json.loads(first.stdout)["selectedProfile"] == "astra-medium"

    denied_path = tmp_path / "denied.json"
    denied_path.write_text(
        json.dumps(_request(availability={"astra": "unavailable", "sol": "available"})),
        encoding="utf-8",
    )
    denied = subprocess.run(
        [sys.executable, "-S", str(MODULE), "--request", str(denied_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert denied.returncode == 2
    assert json.loads(denied.stdout)["fallback"] == "none"


def test_critical_security_optimize_can_compare_astra_with_separate_safety_approval() -> None:
    estimates = {
        "sol-xhigh": _estimate(
            "sol-xhigh",
            primary_call=_call(
                "sol-xhigh",
                task="critical-security",
                role="security-reviewer",
            ),
            review_profile="sol-xhigh",
            review_role="architecture-reviewer",
        ),
        "astra-high": _estimate(
            "astra-high",
            primary_call=_call(
                "astra-high",
                task="critical-security",
                role="security-reviewer",
            ),
            review_profile="sol-xhigh",
            review_role="architecture-reviewer",
        ),
    }
    result = _resolve(
        _request(
            mode="optimize",
            taskClass="critical-security",
            role="security-reviewer",
            availability={"sol": "available", "astra": "available"},
            objective="api-cost",
            routeEvidence="measured-api-cost-to-pass",
            routeEstimates=estimates,
            allowCriticalAstra=True,
        )
    )
    assert result["status"] == "selected"
    assert len(result["comparison"]) == 2


def test_all_estimates_are_validated_even_when_quality_floor_is_false() -> None:
    malformed = {"qualityFloorSatisfied": False}
    result = _resolve(
        _request(
            mode="optimize",
            objective="tokens",
            routeEvidence="measured-route-efficiency",
            routeEstimates={
                "sol-xhigh": malformed,
                "astra-medium": _estimate("astra-medium"),
            },
        )
    )
    assert result["stableId"] == "E_MODEL_V2_ESTIMATE_INVALID"


def test_unused_approval_flags_fail_closed_outside_optimization() -> None:
    unused_max = _resolve(_request(allowMaxEffort=True))
    assert unused_max["stableId"] == "E_MODEL_V2_MAX_APPROVAL_INVALID"

    unused_critical = _resolve(
        _request(
            mode="explicit",
            taskClass="critical-security",
            role="security-reviewer",
            requestedProfile="sol-xhigh",
            routeEvidence=None,
            allowCriticalAstra=True,
        )
    )
    assert unused_critical["stableId"] == "E_MODEL_V2_CRITICAL_ASTRA_APPROVAL_INVALID"


def test_estimate_primary_call_is_bound_to_requested_task_and_role() -> None:
    forged = _estimate(
        "astra-medium",
        primary_call=_call(
            "astra-medium",
            task="exploration",
            role="explorer",
        ),
    )
    result = _resolve(
        _request(
            mode="optimize",
            objective="tokens",
            routeEvidence="measured-route-efficiency",
            routeEstimates={
                "sol-xhigh": _estimate("sol-xhigh"),
                "astra-medium": forged,
            },
        )
    )
    assert result["stableId"] == "E_MODEL_V2_ESTIMATE_INVALID"


def test_every_estimated_call_requires_known_admitted_role_profile_and_available_model() -> None:
    unknown_role = _estimate("astra-medium")
    unknown_role["calls"][1]["role"] = "invented-reviewer"
    result = _resolve(
        _request(
            mode="optimize",
            objective="tokens",
            routeEvidence="measured-route-efficiency",
            routeEstimates={
                "sol-xhigh": _estimate("sol-xhigh"),
                "astra-medium": unknown_role,
            },
        )
    )
    assert result["stableId"] == "E_MODEL_V2_ESTIMATE_INVALID"

    missing_review_model = _resolve(
        _request(
            mode="optimize",
            availability={"sol": "available", "astra": "available"},
            objective="tokens",
            routeEvidence="measured-route-efficiency",
            routeEstimates={
                "sol-xhigh": _estimate("sol-xhigh"),
                "astra-medium": _estimate("astra-medium"),
            },
        )
    )
    assert missing_review_model["stableId"] == "E_MODEL_V2_AVAILABILITY_UNKNOWN"
