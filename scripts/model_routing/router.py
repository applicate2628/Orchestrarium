"""Pure deterministic model-and-effort route resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .contracts import (
    DEFAULT_CATALOG,
    DEFAULT_POLICY,
    MAX_ITEMS,
    MODES,
    OBJECTIVES,
    OBJECTIVE_EVIDENCE,
    REQUEST_FIELDS,
    RoutingError,
    _canonical_date,
    _exact,
    _identifier,
    _integer,
    _validate_catalog,
    _validate_policy,
    load_contracts,
)
from .economics import _selection_key, _validate_estimate

def _deny(stable_id: str, request: Mapping[str, Any], *, status: str = "denied") -> dict[str, Any]:
    return {
        "schemaVersion": 2,
        "status": status,
        "stableId": stable_id,
        "mode": request.get("mode") if isinstance(request, Mapping) else None,
        "taskClass": request.get("taskClass") if isinstance(request, Mapping) else None,
        "role": request.get("role") if isinstance(request, Mapping) else None,
        "selectedProfile": None,
        "model": None,
        "providerModel": None,
        "effort": None,
        "routeEvidence": None,
        "effortEvidence": None,
        "metrics": None,
        "comparison": None,
        "fallback": "none",
        "requiresIndependentReview": None,
        "providerIndependentReview": None,
        "authorizing": False,
    }


def _validate_request(request: Any, catalog: Mapping[str, Any]) -> None:
    if not _exact(request, REQUEST_FIELDS) or request["schemaVersion"] != 2:
        raise RoutingError("E_MODEL_V2_REQUEST_INVALID", "request fields")
    if (
        request["mode"] not in MODES
        or not _identifier(request["taskClass"])
        or not _identifier(request["role"])
        or type(request["allowMaxEffort"]) is not bool
        or type(request["allowCriticalAstra"]) is not bool
        or not _integer(request["requestedFanout"], minimum=1, maximum=MAX_ITEMS)
    ):
        raise RoutingError("E_MODEL_V2_REQUEST_INVALID", "request scalars")
    for optional in ("requestedProfile", "routeEvidence", "effortEvidence", "objective"):
        if request[optional] is not None and not _identifier(request[optional]):
            raise RoutingError("E_MODEL_V2_REQUEST_INVALID", optional)
    availability = request["availability"]
    if not isinstance(availability, dict) or any(
        model not in catalog["models"] or state not in catalog["availabilityStates"]
        for model, state in availability.items()
    ):
        raise RoutingError("E_MODEL_V2_REQUEST_INVALID", "availability")
    if request["routeEstimates"] is not None and not isinstance(request["routeEstimates"], dict):
        raise RoutingError("E_MODEL_V2_REQUEST_INVALID", "route estimates")
    _canonical_date(request["asOf"], "E_MODEL_V2_REQUEST_INVALID")


def _resolve_profile_name(
    requested: str,
    policy: Mapping[str, Any],
) -> tuple[str, str | None]:
    if requested in policy["profiles"]:
        return requested, None
    target = policy["migrationAliases"].get(requested)
    if target is None:
        raise RoutingError("E_MODEL_V2_PROFILE_UNKNOWN")
    return target, requested


def _route_evidence(
    request: Mapping[str, Any],
    task: Mapping[str, Any],
    mode: str,
) -> str | None:
    supplied = request["routeEvidence"]
    if mode == "policy-default":
        evidence = supplied or task["defaultRouteEvidence"]
    else:
        evidence = supplied
    if evidence is not None and evidence not in task["routeEvidence"]:
        raise RoutingError("E_MODEL_V2_ROUTE_EVIDENCE_INVALID")
    return evidence


def _profile_admission(
    profile_name: str,
    request: Mapping[str, Any],
    catalog: Mapping[str, Any],
    policy: Mapping[str, Any],
    task: Mapping[str, Any],
    role: Mapping[str, Any],
    route_evidence: str | None,
    *,
    optimization: bool,
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    profile = policy["profiles"].get(profile_name)
    if profile is None:
        raise RoutingError("E_MODEL_V2_PROFILE_UNKNOWN")
    if profile_name not in role["allowedProfiles"]:
        raise RoutingError("E_MODEL_V2_PROFILE_NOT_ADMITTED")
    if optimization and profile_name not in task["comparisonProfiles"]:
        raise RoutingError("E_MODEL_V2_PROFILE_NOT_ADMITTED")
    model_name = profile["model"]
    model = catalog["models"][model_name]
    if model["executionClass"] != task["executionClass"]:
        raise RoutingError("E_MODEL_V2_EXECUTION_CLASS_MISMATCH")
    capability = task["minimumCapability"]
    if capability is not None:
        order = catalog["capabilityOrder"]
        if order.index(model["capability"]) < order.index(capability):
            raise RoutingError("E_MODEL_V2_CAPABILITY_FLOOR")
    effort = profile["effort"]
    floor = task["minimumEffortByModel"].get(model_name)
    if floor is None:
        raise RoutingError("E_MODEL_V2_EFFORT_FLOOR")
    if (
        model_name != "astra"
        and catalog["effortOrder"].index(effort)
        < catalog["effortOrder"].index(floor)
    ):
        raise RoutingError("E_MODEL_V2_EFFORT_FLOOR")

    state = request["availability"].get(model_name, "unknown")
    if state == "unknown":
        raise RoutingError("E_MODEL_V2_AVAILABILITY_UNKNOWN")
    if state != "available":
        raise RoutingError("E_MODEL_V2_MODEL_UNAVAILABLE")
    if request["requestedFanout"] > model["automaticFanoutLimit"]:
        raise RoutingError("E_MODEL_V2_FANOUT_LIMIT")
    if effort == "max" and not request["allowMaxEffort"]:
        raise RoutingError("E_MODEL_V2_MAX_APPROVAL_REQUIRED")
    if request["allowMaxEffort"] and effort != "max" and not optimization:
        raise RoutingError("E_MODEL_V2_MAX_APPROVAL_INVALID")

    if model_name == "astra":
        if route_evidence is None:
            raise RoutingError("E_MODEL_V2_ROUTE_EVIDENCE_REQUIRED")
        if task["criticalAstraApproval"] and not request["allowCriticalAstra"]:
            raise RoutingError("E_MODEL_V2_CRITICAL_ASTRA_APPROVAL_REQUIRED")
        if request["allowCriticalAstra"] and not task["criticalAstraApproval"]:
            raise RoutingError("E_MODEL_V2_CRITICAL_ASTRA_APPROVAL_INVALID")

        default_effort = task["minimumEffortByModel"]["astra"]
        rank = catalog["effortOrder"]
        current_rank = rank.index(effort)
        default_rank = rank.index(default_effort)
        evidence = request["effortEvidence"]
        astra_policy = policy["effortPolicy"]["astra"]
        if effort == "max":
            if evidence is not None:
                raise RoutingError("E_MODEL_V2_EFFORT_EVIDENCE_INVALID")
        elif current_rank < default_rank:
            if evidence not in astra_policy["downshiftEvidence"]:
                raise RoutingError("E_MODEL_V2_EFFORT_EVIDENCE_REQUIRED")
        elif current_rank > default_rank:
            allowed = astra_policy["upshiftEvidence"].get(effort, [])
            if evidence not in allowed:
                raise RoutingError("E_MODEL_V2_EFFORT_EVIDENCE_REQUIRED")
        elif evidence is not None:
            raise RoutingError("E_MODEL_V2_EFFORT_EVIDENCE_INVALID")
    elif request["effortEvidence"] is not None and not optimization:
        raise RoutingError("E_MODEL_V2_EFFORT_EVIDENCE_INVALID")
    if request["allowCriticalAstra"] and not optimization and model_name != "astra":
        raise RoutingError("E_MODEL_V2_CRITICAL_ASTRA_APPROVAL_INVALID")
    return profile, model



def resolve_model_route(
    request: Mapping[str, Any],
    *,
    catalog: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
    catalog_path: Path = DEFAULT_CATALOG,
    policy_path: Path = DEFAULT_POLICY,
) -> dict[str, Any]:
    """Resolve one nonauthorizing model-and-effort route."""

    safe_request: Mapping[str, Any] = request if isinstance(request, Mapping) else {}
    try:
        if catalog is None or policy is None:
            catalog, policy = load_contracts(catalog_path, policy_path)
        else:
            _validate_catalog(catalog)
            _validate_policy(policy, catalog)
        _validate_request(request, catalog)
        as_of = _canonical_date(request["asOf"], "E_MODEL_V2_REQUEST_INVALID")
        observed = _canonical_date(catalog["pricing"]["observedAt"], "E_MODEL_V2_CATALOG_INVALID")
        review_by = _canonical_date(catalog["pricing"]["reviewBy"], "E_MODEL_V2_CATALOG_INVALID")
        if as_of < observed or as_of > review_by:
            raise RoutingError("E_MODEL_V2_PRICING_STALE")

        task = policy["taskClasses"].get(request["taskClass"])
        role = policy["roles"].get(request["role"])
        if task is None or role is None:
            raise RoutingError("E_MODEL_V2_ROUTE_UNKNOWN")
        if request["role"] not in policy["taskRoleEligibility"][request["taskClass"]]:
            raise RoutingError("E_MODEL_V2_ROLE_NOT_ELIGIBLE")

        mode = request["mode"]
        if mode == "policy-default":
            if (
                request["requestedProfile"] is not None
                or request["objective"] is not None
                or request["routeEstimates"] is not None
            ):
                raise RoutingError("E_MODEL_V2_REQUEST_INVALID")
            profile_name = task["defaultProfile"]
            alias = None
        elif mode == "explicit":
            if (
                request["requestedProfile"] is None
                or request["objective"] is not None
                or request["routeEstimates"] is not None
            ):
                raise RoutingError("E_MODEL_V2_REQUEST_INVALID")
            profile_name, alias = _resolve_profile_name(request["requestedProfile"], policy)
        else:
            if (
                request["requestedProfile"] is not None
                or request["objective"] not in OBJECTIVES
                or request["routeEstimates"] is None
            ):
                raise RoutingError("E_MODEL_V2_REQUEST_INVALID")
            profile_name = ""
            alias = None

        route_evidence = _route_evidence(request, task, mode)
        if mode == "optimize":
            required_evidence = OBJECTIVE_EVIDENCE[request["objective"]]
            if route_evidence != required_evidence:
                raise RoutingError("E_MODEL_V2_ROUTE_EVIDENCE_OBJECTIVE_MISMATCH")

            candidates: list[str] = []
            for candidate in task["comparisonProfiles"]:
                model_name = policy["profiles"][candidate]["model"]
                state = request["availability"].get(model_name, "unknown")
                if state == "unknown":
                    raise RoutingError("E_MODEL_V2_AVAILABILITY_UNKNOWN")
                if state == "available":
                    _profile_admission(
                        candidate,
                        request,
                        catalog,
                        policy,
                        task,
                        role,
                        route_evidence,
                        optimization=True,
                    )
                    candidates.append(candidate)
            if not candidates:
                raise RoutingError("E_MODEL_V2_MODEL_UNAVAILABLE")
            estimates = request["routeEstimates"]
            if set(estimates) != set(candidates):
                raise RoutingError("E_MODEL_V2_CANDIDATE_SET_INCOMPLETE")

            comparison: list[dict[str, Any]] = []
            comparable_identity: tuple[str, str, str] | None = None
            for candidate in candidates:
                estimate = estimates[candidate]
                metrics, identity = _validate_estimate(
                    candidate, estimate, request, catalog, policy, task
                )
                if comparable_identity is None:
                    comparable_identity = identity
                elif identity != comparable_identity:
                    raise RoutingError("E_MODEL_V2_ESTIMATES_NOT_COMPARABLE")
                if estimate["qualityFloorSatisfied"] is not True:
                    continue
                comparison.append({"profile": candidate, "metrics": metrics})
            if not comparison:
                raise RoutingError("E_MODEL_V2_QUALITY_FLOOR_UNMET")
            comparison.sort(
                key=lambda item: _selection_key(
                    item["profile"], item["metrics"], request["objective"]
                )
            )
            selected = comparison[0]
            profile_name = selected["profile"]
            metrics = selected["metrics"]
            comparison_payload = comparison
        else:
            _profile_admission(
                profile_name,
                request,
                catalog,
                policy,
                task,
                role,
                route_evidence,
                optimization=False,
            )
            metrics = None
            comparison_payload = None

        profile = policy["profiles"][profile_name]
        model_name = profile["model"]
        model = catalog["models"][model_name]
        provider_independent_review = (
            metrics["providerIndependentReview"] if metrics is not None else False
        )
        return {
            "schemaVersion": 2,
            "status": "selected",
            "stableId": None,
            "mode": mode,
            "taskClass": request["taskClass"],
            "role": request["role"],
            "selectedProfile": profile_name,
            "migrationAlias": alias,
            "model": model_name,
            "providerModel": model["providerModel"],
            "effort": profile["effort"],
            "routeEvidence": route_evidence,
            "routeEvidenceClass": (
                policy["routeEvidenceClasses"].get(route_evidence)
                if route_evidence is not None
                else None
            ),
            "effortEvidence": request["effortEvidence"],
            "objective": request["objective"],
            "metrics": metrics,
            "comparison": comparison_payload,
            "pricingChannel": catalog["pricing"]["channel"],
            "catalogId": catalog["catalogId"],
            "policyId": policy["policyId"],
            "fallback": "none",
            "requiresIndependentReview": task["requiresIndependentReview"],
            "providerIndependentReview": provider_independent_review,
            "authorizing": False,
        }
    except RoutingError as exc:
        return _deny(exc.stable_id, safe_request)
