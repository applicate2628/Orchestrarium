"""Complete-route pricing and comparable estimate validation."""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Mapping

from .contracts import (
    CALL_FIELDS,
    CALL_STAGES,
    ESTIMATE_FIELDS,
    MAX_COST_NANO_USD,
    MAX_ITEMS,
    MAX_MILLISECONDS,
    MAX_TOKENS,
    MEASUREMENT_FIELDS,
    RoutingError,
    _canonical_date,
    _exact,
    _identifier,
    _integer,
    _ratio,
)

def _fraction_payload(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}



def _call_cost(
    call: Mapping[str, Any],
    catalog: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> Fraction:
    profile = policy["profiles"][call["profile"]]
    model = catalog["models"][profile["model"]]
    price = model["price"]
    prompt_tokens = (
        call["uncachedInputTokens"]
        + call["cachedInputTokens"]
        + call["cacheWriteTokens"]
    )
    long_context = catalog["pricing"]["longContext"]
    input_multiplier = Fraction(1)
    output_multiplier = Fraction(1)
    if prompt_tokens > long_context["promptTokenThresholdExclusive"]:
        input_multiplier = _ratio(
            long_context["inputAndCacheMultiplier"], "E_MODEL_V2_CATALOG_INVALID"
        )
        output_multiplier = _ratio(
            long_context["outputMultiplier"], "E_MODEL_V2_CATALOG_INVALID"
        )
    return (
        input_multiplier
        * (
            call["uncachedInputTokens"] * price["uncachedInput"]
            + call["cachedInputTokens"] * price["cachedInput"]
            + call["cacheWriteTokens"] * price["cacheWrite"]
        )
        + output_multiplier * call["outputTokens"] * price["output"]
        + call["toolCostNanoUsd"]
    )


def _validate_estimate(
    profile_name: str,
    estimate: Any,
    request: Mapping[str, Any],
    catalog: Mapping[str, Any],
    policy: Mapping[str, Any],
    task: Mapping[str, Any],
) -> tuple[dict[str, Any], tuple[str, str, str]]:
    sid = "E_MODEL_V2_ESTIMATE_INVALID"
    if not _exact(estimate, ESTIMATE_FIELDS) or type(estimate["qualityFloorSatisfied"]) is not bool:
        raise RoutingError(sid, "estimate fields")
    measurement = estimate["measurement"]
    if not _exact(measurement, MEASUREMENT_FIELDS):
        raise RoutingError(sid, "measurement fields")
    for key in ("comparisonId", "corpusId"):
        if not _identifier(measurement[key]):
            raise RoutingError(sid, key)
    observed = _canonical_date(measurement["observedAt"], sid)
    if observed > _canonical_date(request["asOf"], sid):
        raise RoutingError(sid, "future measurement")
    attempted = measurement["attempted"]
    accepted = measurement["accepted"]
    if (
        not _integer(attempted, minimum=1, maximum=MAX_ITEMS)
        or not _integer(accepted, minimum=1, maximum=attempted)
    ):
        raise RoutingError(sid, "measurement counts")
    for key, maximum in (
        ("coordinationSteps", MAX_ITEMS),
        ("wallTimeMs", MAX_MILLISECONDS),
        ("reworkCycles", MAX_ITEMS),
    ):
        if not _integer(estimate[key], minimum=0, maximum=maximum):
            raise RoutingError(sid, key)

    calls = estimate["calls"]
    if not isinstance(calls, list) or not calls or len(calls) > MAX_ITEMS:
        raise RoutingError(sid, "calls")
    if estimate["coordinationSteps"] < len(calls):
        raise RoutingError(sid, "steps below calls")
    direct_cost = Fraction(0)
    direct_tokens = 0
    aggregate_elapsed = 0
    retry_calls = 0
    primary_calls = 0
    review_calls: list[Mapping[str, Any]] = []
    for call in calls:
        if not _exact(call, CALL_FIELDS):
            raise RoutingError(sid, "call fields")
        if (
            call["stage"] not in CALL_STAGES
            or not _identifier(call["taskClass"])
            or not _identifier(call["role"])
            or call["taskClass"] not in policy["taskClasses"]
            or call["role"] not in policy["roles"]
            or call["profile"] not in policy["profiles"]
            or call["role"]
            not in policy["taskRoleEligibility"][call["taskClass"]]
            or call["profile"] not in policy["roles"][call["role"]]["allowedProfiles"]
        ):
            raise RoutingError(sid, "call identity")
        call_model = policy["profiles"][call["profile"]]["model"]
        call_availability = request["availability"].get(call_model, "unknown")
        if call_availability == "unknown":
            raise RoutingError("E_MODEL_V2_AVAILABILITY_UNKNOWN")
        if call_availability != "available":
            raise RoutingError("E_MODEL_V2_MODEL_UNAVAILABLE")
        if (
            call["stage"] == "primary"
            and call["profile"] == profile_name
            and (
                call["taskClass"] != request["taskClass"]
                or call["role"] != request["role"]
            )
        ):
            raise RoutingError(sid, "primary binding")
        for key in (
            "uncachedInputTokens", "cachedInputTokens", "cacheWriteTokens", "outputTokens"
        ):
            if not _integer(call[key], minimum=0, maximum=MAX_TOKENS):
                raise RoutingError(sid, key)
        if not _integer(call["toolCostNanoUsd"], minimum=0, maximum=MAX_COST_NANO_USD):
            raise RoutingError(sid, "tool cost")
        if not _integer(call["elapsedMs"], minimum=0, maximum=MAX_MILLISECONDS):
            raise RoutingError(sid, "elapsed")
        direct_cost += _call_cost(call, catalog, policy)
        direct_tokens += sum(
            call[key]
            for key in (
                "uncachedInputTokens", "cachedInputTokens", "cacheWriteTokens", "outputTokens"
            )
        )
        aggregate_elapsed += call["elapsedMs"]
        retry_calls += int(call["stage"] == "retry")
        primary_calls += int(call["stage"] == "primary" and call["profile"] == profile_name)
        if call["stage"] == "review":
            review_calls.append(call)
    if primary_calls != 1:
        raise RoutingError(sid, "exactly one primary call required")
    if task["requiresIndependentReview"] and not any(
        call["role"] in policy["reviewRoles"] and call["role"] != request["role"]
        for call in review_calls
    ):
        raise RoutingError("E_MODEL_V2_INDEPENDENT_REVIEW_REQUIRED")

    acceptance_multiplier = Fraction(attempted, accepted)
    expected_cost = direct_cost * acceptance_multiplier
    expected_tokens = Fraction(direct_tokens) * acceptance_multiplier
    expected_steps = Fraction(estimate["coordinationSteps"]) * acceptance_multiplier
    expected_latency = Fraction(estimate["wallTimeMs"]) * acceptance_multiplier
    expected_calls = Fraction(len(calls)) * acceptance_multiplier
    expected_retries = Fraction(retry_calls) * acceptance_multiplier
    expected_rework = Fraction(estimate["reworkCycles"]) * acceptance_multiplier

    primary_model_name = policy["profiles"][profile_name]["model"]
    primary_group = catalog["models"][primary_model_name]["evidenceIndependenceGroup"]
    review_groups = sorted(
        {
            catalog["models"][policy["profiles"][call["profile"]]["model"]][
                "evidenceIndependenceGroup"
            ]
            for call in review_calls
        }
    )
    metrics = {
        "directApiCostNanoUsd": _fraction_payload(direct_cost),
        "expectedApiCostNanoUsd": _fraction_payload(expected_cost),
        "directTotalTokens": direct_tokens,
        "expectedTotalTokens": _fraction_payload(expected_tokens),
        "directCoordinationSteps": estimate["coordinationSteps"],
        "expectedCoordinationSteps": _fraction_payload(expected_steps),
        "routeWallTimeMs": estimate["wallTimeMs"],
        "expectedWallTimeMs": _fraction_payload(expected_latency),
        "aggregateCallElapsedMs": aggregate_elapsed,
        "directModelCalls": len(calls),
        "expectedModelCalls": _fraction_payload(expected_calls),
        "directRetryCalls": retry_calls,
        "expectedRetryCalls": _fraction_payload(expected_retries),
        "directReworkCycles": estimate["reworkCycles"],
        "expectedReworkCycles": _fraction_payload(expected_rework),
        "attempted": attempted,
        "accepted": accepted,
        "primaryEvidenceIndependenceGroup": primary_group,
        "reviewEvidenceIndependenceGroups": review_groups,
        "providerIndependentReview": any(group != primary_group for group in review_groups),
    }
    comparable = (
        measurement["comparisonId"],
        measurement["corpusId"],
        measurement["observedAt"],
    )
    return metrics, comparable


def _metric_fraction(metrics: Mapping[str, Any], key: str) -> Fraction:
    value = metrics[key]
    return Fraction(value["numerator"], value["denominator"])


def _selection_key(profile: str, metrics: Mapping[str, Any], objective: str) -> tuple[Any, ...]:
    cost = _metric_fraction(metrics, "expectedApiCostNanoUsd")
    tokens = _metric_fraction(metrics, "expectedTotalTokens")
    steps = _metric_fraction(metrics, "expectedCoordinationSteps")
    latency = _metric_fraction(metrics, "expectedWallTimeMs")
    keys = {
        "api-cost": (cost, tokens, steps, latency, profile),
        "tokens": (tokens, steps, latency, cost, profile),
        "steps": (steps, latency, tokens, cost, profile),
        "latency": (latency, steps, tokens, cost, profile),
    }
    return keys[objective]
