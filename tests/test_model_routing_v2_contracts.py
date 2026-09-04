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

def test_catalog_separates_luna_from_general_capability_and_encodes_efforts() -> None:
    catalog, _ = _contracts()
    assert catalog["capabilityOrder"] == ["balanced", "frontier", "apex"]
    assert catalog["models"]["luna"]["executionClass"] == "mechanical"
    assert catalog["models"]["luna"]["capability"] is None
    assert catalog["models"]["terra"]["capability"] == "balanced"
    assert catalog["models"]["sol"]["capability"] == "frontier"
    assert catalog["models"]["astra"]["capability"] == "apex"
    assert "none" not in catalog["models"]["astra"]["supportedEfforts"]
    assert catalog["models"]["astra"]["defaultEffort"] == "medium"


def test_catalog_prices_and_per_call_long_context_rule_are_exact() -> None:
    catalog, _ = _contracts()
    assert catalog["models"]["sol"]["price"] == {
        "uncachedInput": 4000,
        "cachedInput": 400,
        "cacheWrite": 5000,
        "output": 20000,
    }
    assert catalog["models"]["astra"]["price"] == {
        "uncachedInput": 10000,
        "cachedInput": 1000,
        "cacheWrite": 12500,
        "output": 50000,
    }
    long_context = catalog["pricing"]["longContext"]
    assert long_context["promptTokenThresholdExclusive"] == 272000
    assert long_context["application"] == "per-call"


def test_policy_preserves_v1_alias_meaning_and_rejects_automatic_max() -> None:
    catalog, policy = _contracts()
    module = _load()
    module._validate_policy(policy, catalog)
    assert policy["migrationAliases"]["apex-max"] == "sol-max"
    assert policy["migrationAliases"]["pinned-top-pro"] == "sol-xhigh"

    broken = copy.deepcopy(policy)
    broken["taskClasses"]["mathematical-research"]["defaultProfile"] = "astra-max"
    with pytest.raises(module.RoutingError) as caught:
        module._validate_policy(broken, catalog)
    assert caught.value.stable_id == "E_MODEL_V2_POLICY_INVALID"


def test_deep_math_and_connected_science_default_to_astra_medium() -> None:
    cases = (
        ("mathematical-research", "algorithm-scientist", "mathematics-quality-floor"),
        ("scientific-agentic-workflow", "computational-scientist", "connected-science-workflow"),
        ("cross-system-synthesis", "architect", "cross-system-context-retention"),
    )
    for task, role, evidence in cases:
        result = _resolve(_request(taskClass=task, role=role))
        assert result["status"] == "selected"
        assert result["selectedProfile"] == "astra-medium"
        assert result["providerModel"] == "gpt-6-astra"
        assert result["effort"] == "medium"
        assert result["routeEvidence"] == evidence
        assert result["authorizing"] is False


def test_critical_recovery_defaults_to_astra_high_and_routine_science_stays_sol() -> None:
    recovery = _resolve(
        _request(
            taskClass="critical-recovery",
            role="architect",
            availability={"sol": "available", "astra": "available"},
        )
    )
    assert recovery["selectedProfile"] == "astra-high"
    assert recovery["effort"] == "high"

    routine = _resolve(
        _request(
            taskClass="scientific-routine",
            role="computational-scientist",
            availability={"terra": "available", "sol": "available", "astra": "available"},
        )
    )
    assert routine["selectedProfile"] == "sol-high"


def test_luna_mechanical_route_is_not_part_of_general_capability_fallback() -> None:
    selected = _resolve(
        _request(
            taskClass="mechanical-read",
            role="mechanical-scout",
            availability={"luna": "available"},
        )
    )
    assert selected["model"] == "luna"
    assert selected["providerModel"] == "gpt-5.6-luna"

    unavailable = _resolve(
        _request(
            taskClass="mechanical-read",
            role="mechanical-scout",
            availability={"luna": "unavailable", "astra": "available"},
        )
    )
    assert unavailable["stableId"] == "E_MODEL_V2_MODEL_UNAVAILABLE"
    assert unavailable["fallback"] == "none"


def test_explicit_astra_effort_upshift_requires_model_local_evidence() -> None:
    denied = _resolve(
        _request(
            mode="explicit",
            requestedProfile="astra-high",
            routeEvidence="mathematics-quality-floor",
        )
    )
    assert denied["stableId"] == "E_MODEL_V2_EFFORT_EVIDENCE_REQUIRED"

    selected = _resolve(
        _request(
            mode="explicit",
            requestedProfile="astra-high",
            routeEvidence="mathematics-quality-floor",
            effortEvidence="medium-objective-failure",
        )
    )
    assert selected["status"] == "selected"
    assert selected["effort"] == "high"


def test_explicit_astra_downshift_and_max_are_gated() -> None:
    downshift = _resolve(
        _request(
            mode="explicit",
            requestedProfile="astra-low",
            routeEvidence="mathematics-quality-floor",
        )
    )
    assert downshift["stableId"] == "E_MODEL_V2_EFFORT_EVIDENCE_REQUIRED"

    selected_low = _resolve(
        _request(
            mode="explicit",
            requestedProfile="astra-low",
            routeEvidence="mathematics-quality-floor",
            effortEvidence="migration-evaluation",
        )
    )
    assert selected_low["status"] == "selected"

    denied_max = _resolve(
        _request(
            mode="explicit",
            requestedProfile="astra-max",
            routeEvidence="mathematics-quality-floor",
        )
    )
    assert denied_max["stableId"] == "E_MODEL_V2_MAX_APPROVAL_REQUIRED"

    selected_max = _resolve(
        _request(
            mode="explicit",
            requestedProfile="astra-max",
            routeEvidence="mathematics-quality-floor",
            allowMaxEffort=True,
        )
    )
    assert selected_max["status"] == "selected"


def test_legacy_apex_alias_resolves_to_sol_max_not_astra() -> None:
    result = _resolve(
        _request(
            mode="explicit",
            requestedProfile="apex-max",
            routeEvidence=None,
            allowMaxEffort=True,
        )
    )
    assert result["status"] == "selected"
    assert result["migrationAlias"] == "apex-max"
    assert result["selectedProfile"] == "sol-max"
    assert result["model"] == "sol"


def test_critical_security_astra_requires_both_safety_evidence_and_approval() -> None:
    base = _request(
        mode="explicit",
        taskClass="critical-security",
        role="security-reviewer",
        requestedProfile="astra-high",
        availability={"sol": "available", "astra": "available"},
        routeEvidence="critical-capability-approved",
    )
    denied = _resolve(base)
    assert denied["stableId"] == "E_MODEL_V2_CRITICAL_ASTRA_APPROVAL_REQUIRED"

    selected = _resolve({**base, "allowCriticalAstra": True})
    assert selected["status"] == "selected"
    assert selected["effort"] == "high"


def test_astra_fanout_above_one_fails_closed() -> None:
    result = _resolve(_request(requestedFanout=2))
    assert result["stableId"] == "E_MODEL_V2_FANOUT_LIMIT"


def test_unknown_availability_and_stale_pricing_fail_closed() -> None:
    unknown = _resolve(_request(availability={"sol": "available"}))
    assert unknown["stableId"] == "E_MODEL_V2_AVAILABILITY_UNKNOWN"

    stale = _resolve(_request(asOf="2026-09-19"))
    assert stale["stableId"] == "E_MODEL_V2_PRICING_STALE"
