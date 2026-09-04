"""Strict catalog and policy contracts for model routing Version 2."""

from __future__ import annotations

import json
import stat
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = ROOT / "shared" / "model-catalog.v2.json"
DEFAULT_POLICY = ROOT / "shared" / "role-routing-policy.v2.json"

MAX_DOCUMENT_BYTES = 4 * 1024 * 1024
MAX_TOKENS = 10**12
MAX_COST_NANO_USD = 10**21
MAX_MILLISECONDS = 10**15
MAX_ITEMS = 10**5

CATALOG_FIELDS = {
    "schemaVersion", "catalogId", "pricing", "capabilityOrder",
    "effortOrder", "availabilityStates", "models",
}
PRICING_FIELDS = {"observedAt", "reviewBy", "channel", "unit", "longContext"}
LONG_CONTEXT_FIELDS = {
    "promptTokenThresholdExclusive", "inputAndCacheMultiplier",
    "outputMultiplier", "application",
}
RATIO_FIELDS = {"numerator", "denominator"}
MODEL_FIELDS = {
    "provider", "providerModel", "executionClass", "capability",
    "supportedEfforts", "defaultEffort", "price", "automaticFanoutLimit",
    "safetyClass", "availabilityPolicy", "evidenceIndependenceGroup",
}
PRICE_FIELDS = {"uncachedInput", "cachedInput", "cacheWrite", "output"}
POLICY_FIELDS = {
    "schemaVersion", "policyId", "catalogId", "profiles", "effortPolicy",
    "routeEvidenceClasses", "taskClasses", "roles", "taskRoleEligibility",
    "reviewRoles", "migrationAliases",
}
TASK_FIELDS = {
    "executionClass", "minimumCapability", "minimumEffortByModel",
    "comparisonProfiles", "defaultProfile", "defaultRouteEvidence",
    "routeEvidence", "requiresIndependentReview", "criticalAstraApproval",
}
ROLE_FIELDS = {"defaultProfile", "allowedProfiles"}
REQUEST_FIELDS = {
    "schemaVersion", "mode", "taskClass", "role", "availability",
    "requestedProfile", "routeEvidence", "effortEvidence",
    "allowMaxEffort", "allowCriticalAstra", "requestedFanout",
    "objective", "routeEstimates", "asOf",
}
ESTIMATE_FIELDS = {
    "qualityFloorSatisfied", "measurement", "coordinationSteps",
    "wallTimeMs", "reworkCycles", "calls",
}
MEASUREMENT_FIELDS = {
    "comparisonId", "corpusId", "observedAt", "attempted", "accepted",
}
CALL_FIELDS = {
    "stage", "taskClass", "role", "profile", "uncachedInputTokens",
    "cachedInputTokens", "cacheWriteTokens", "outputTokens",
    "toolCostNanoUsd", "elapsedMs",
}
MODES = {"policy-default", "explicit", "optimize"}
OBJECTIVES = {"api-cost", "tokens", "steps", "latency"}
OBJECTIVE_EVIDENCE = {
    "api-cost": "measured-api-cost-to-pass",
    "tokens": "measured-route-efficiency",
    "steps": "measured-route-efficiency",
    "latency": "measured-route-efficiency",
}
CALL_STAGES = {"primary", "support", "retry", "review"}


class RoutingError(ValueError):
    def __init__(self, stable_id: str, detail: str = "") -> None:
        super().__init__(detail or stable_id)
        self.stable_id = stable_id


def _exact(value: Any, fields: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == fields


def _identifier(value: Any, limit: int = 128) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= limit
        and value.strip() == value
        and "\x00" not in value
    )


def _integer(value: Any, *, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _ordinary_file(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return (
        stat.S_ISREG(metadata.st_mode)
        and not stat.S_ISLNK(metadata.st_mode)
        and not bool(
            getattr(metadata, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        )
    )


def _canonical_date(value: Any, stable_id: str) -> date:
    if not isinstance(value, str):
        raise RoutingError(stable_id, "date type")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise RoutingError(stable_id, "date syntax") from exc
    if parsed.isoformat() != value:
        raise RoutingError(stable_id, "date canonical form")
    return parsed


def _load_json(path: Path, stable_id: str) -> dict[str, Any]:
    if not _ordinary_file(path):
        raise RoutingError(stable_id, f"not an ordinary file: {path}")
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise RoutingError(stable_id, str(exc)) from exc
    if len(payload) > MAX_DOCUMENT_BYTES:
        raise RoutingError(stable_id, "document too large")
    try:
        value = json.loads(payload.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RoutingError(stable_id, str(exc)) from exc
    if not isinstance(value, dict):
        raise RoutingError(stable_id, "root must be an object")
    return value


def _ratio(value: Any, stable_id: str) -> Fraction:
    if not _exact(value, RATIO_FIELDS):
        raise RoutingError(stable_id, "ratio fields")
    numerator = value["numerator"]
    denominator = value["denominator"]
    if not _integer(numerator, minimum=1, maximum=10**9) or not _integer(
        denominator, minimum=1, maximum=10**9
    ):
        raise RoutingError(stable_id, "ratio values")
    return Fraction(numerator, denominator)


def _validate_catalog(catalog: dict[str, Any]) -> None:
    sid = "E_MODEL_V2_CATALOG_INVALID"
    if not _exact(catalog, CATALOG_FIELDS):
        raise RoutingError(sid, "catalog fields")
    if (
        catalog["schemaVersion"] != 2
        or catalog["catalogId"] != "orchestrarium.openai-model-catalog.v2"
        or catalog["capabilityOrder"] != ["balanced", "frontier", "apex"]
        or catalog["effortOrder"] != ["none", "low", "medium", "high", "xhigh", "max"]
        or catalog["availabilityStates"]
        != ["available", "unavailable", "unknown", "not-admitted"]
    ):
        raise RoutingError(sid, "catalog identity")

    pricing = catalog["pricing"]
    if not _exact(pricing, PRICING_FIELDS):
        raise RoutingError(sid, "pricing fields")
    observed = _canonical_date(pricing["observedAt"], sid)
    review_by = _canonical_date(pricing["reviewBy"], sid)
    if (
        observed > review_by
        or pricing["channel"] != "openai-api-standard"
        or pricing["unit"] != "nanoUsdPerToken"
    ):
        raise RoutingError(sid, "pricing identity")
    long_context = pricing["longContext"]
    if not _exact(long_context, LONG_CONTEXT_FIELDS):
        raise RoutingError(sid, "long-context fields")
    if (
        not _integer(
            long_context["promptTokenThresholdExclusive"],
            minimum=1,
            maximum=MAX_TOKENS,
        )
        or long_context["application"] != "per-call"
    ):
        raise RoutingError(sid, "long-context identity")
    _ratio(long_context["inputAndCacheMultiplier"], sid)
    _ratio(long_context["outputMultiplier"], sid)

    models = catalog["models"]
    if not isinstance(models, dict) or set(models) != {"luna", "terra", "sol", "astra"}:
        raise RoutingError(sid, "model set")
    provider_models: set[str] = set()
    for name, model in models.items():
        if not _exact(model, MODEL_FIELDS):
            raise RoutingError(sid, f"model fields: {name}")
        if (
            model["provider"] != "openai"
            or not _identifier(model["providerModel"])
            or model["providerModel"] in provider_models
            or model["executionClass"] not in {"mechanical", "general"}
            or model["safetyClass"] not in {"standard", "critical-capability"}
            or model["availabilityPolicy"] != "runtime-inventory"
            or not _identifier(model["evidenceIndependenceGroup"])
            or not _integer(model["automaticFanoutLimit"], minimum=1, maximum=MAX_ITEMS)
        ):
            raise RoutingError(sid, f"model identity: {name}")
        provider_models.add(model["providerModel"])
        capability = model["capability"]
        if model["executionClass"] == "mechanical":
            if capability is not None or name != "luna":
                raise RoutingError(sid, "mechanical capability")
        elif capability not in catalog["capabilityOrder"]:
            raise RoutingError(sid, "general capability")
        efforts = model["supportedEfforts"]
        if (
            not isinstance(efforts, list)
            or not efforts
            or len(efforts) != len(set(efforts))
            or any(effort not in catalog["effortOrder"] for effort in efforts)
            or model["defaultEffort"] not in efforts
        ):
            raise RoutingError(sid, f"efforts: {name}")
        if name == "astra" and "none" in efforts:
            raise RoutingError(sid, "Astra none")
        price = model["price"]
        if not _exact(price, PRICE_FIELDS) or any(
            not _integer(value, minimum=0, maximum=10**9) for value in price.values()
        ):
            raise RoutingError(sid, f"price: {name}")


def _validate_policy(policy: dict[str, Any], catalog: Mapping[str, Any]) -> None:
    sid = "E_MODEL_V2_POLICY_INVALID"
    if not _exact(policy, POLICY_FIELDS):
        raise RoutingError(sid, "policy fields")
    if (
        policy["schemaVersion"] != 2
        or policy["policyId"] != "orchestrarium.model-routing.v2"
        or policy["catalogId"] != catalog["catalogId"]
    ):
        raise RoutingError(sid, "policy identity")

    profiles = policy["profiles"]
    if not isinstance(profiles, dict) or not profiles:
        raise RoutingError(sid, "profiles")
    for name, profile in profiles.items():
        if (
            not _identifier(name)
            or not _exact(profile, {"model", "effort"})
            or profile["model"] not in catalog["models"]
            or profile["effort"] not in catalog["models"][profile["model"]]["supportedEfforts"]
        ):
            raise RoutingError(sid, f"profile: {name}")

    effort_policy = policy["effortPolicy"]
    if not _exact(effort_policy, {"maxRequiresHumanApproval", "astra"}):
        raise RoutingError(sid, "effort policy")
    if effort_policy["maxRequiresHumanApproval"] is not True:
        raise RoutingError(sid, "max approval")
    astra_effort = effort_policy["astra"]
    if not _exact(astra_effort, {"downshiftEvidence", "upshiftEvidence"}):
        raise RoutingError(sid, "Astra effort policy")
    if not isinstance(astra_effort["downshiftEvidence"], list):
        raise RoutingError(sid, "Astra downshift")
    if set(astra_effort["upshiftEvidence"]) != {"high", "xhigh"}:
        raise RoutingError(sid, "Astra upshift")

    route_classes = policy["routeEvidenceClasses"]
    if not isinstance(route_classes, dict) or any(
        not _identifier(key) or not _identifier(value)
        for key, value in route_classes.items()
    ):
        raise RoutingError(sid, "route evidence classes")

    tasks = policy["taskClasses"]
    roles = policy["roles"]
    eligibility = policy["taskRoleEligibility"]
    review_roles = policy["reviewRoles"]
    if not all(isinstance(value, dict) for value in (tasks, roles, eligibility)):
        raise RoutingError(sid, "policy maps")
    if (
        not isinstance(review_roles, list)
        or not review_roles
        or len(review_roles) != len(set(review_roles))
    ):
        raise RoutingError(sid, "review roles")

    capability_rank = {value: index for index, value in enumerate(catalog["capabilityOrder"])}
    effort_rank = {value: index for index, value in enumerate(catalog["effortOrder"])}
    for task_name, task in tasks.items():
        if not _identifier(task_name) or not _exact(task, TASK_FIELDS):
            raise RoutingError(sid, f"task: {task_name}")
        if task["executionClass"] not in {"mechanical", "general"}:
            raise RoutingError(sid, "task execution class")
        minimum_capability = task["minimumCapability"]
        if task["executionClass"] == "mechanical":
            if minimum_capability is not None:
                raise RoutingError(sid, "mechanical floor")
        elif minimum_capability not in capability_rank:
            raise RoutingError(sid, "general floor")
        comparison = task["comparisonProfiles"]
        if (
            not isinstance(comparison, list)
            or not comparison
            or len(comparison) != len(set(comparison))
            or any(profile not in profiles for profile in comparison)
            or task["defaultProfile"] not in comparison
        ):
            raise RoutingError(sid, "task profiles")
        evidence = task["routeEvidence"]
        if (
            not isinstance(evidence, list)
            or len(evidence) != len(set(evidence))
            or any(item not in route_classes for item in evidence)
            or (
                task["defaultRouteEvidence"] is not None
                and task["defaultRouteEvidence"] not in evidence
            )
        ):
            raise RoutingError(sid, "task route evidence")
        if (
            type(task["requiresIndependentReview"]) is not bool
            or type(task["criticalAstraApproval"]) is not bool
        ):
            raise RoutingError(sid, "task booleans")
        minimum_efforts = task["minimumEffortByModel"]
        if not isinstance(minimum_efforts, dict) or not minimum_efforts:
            raise RoutingError(sid, "task effort floors")
        for model_name, effort in minimum_efforts.items():
            if (
                model_name not in catalog["models"]
                or effort not in catalog["models"][model_name]["supportedEfforts"]
            ):
                raise RoutingError(sid, "task effort floor")
        for profile_name in comparison:
            profile = profiles[profile_name]
            model = catalog["models"][profile["model"]]
            if model["executionClass"] != task["executionClass"]:
                raise RoutingError(sid, "task/profile execution class")
            if profile["model"] not in minimum_efforts:
                raise RoutingError(sid, "task/profile effort floor missing")
            if effort_rank[profile["effort"]] < effort_rank[minimum_efforts[profile["model"]]]:
                raise RoutingError(sid, "task/profile effort below floor")
            if (
                minimum_capability is not None
                and capability_rank[model["capability"]] < capability_rank[minimum_capability]
            ):
                raise RoutingError(sid, "task/profile capability below floor")
        default_profile = profiles[task["defaultProfile"]]
        if default_profile["effort"] == "max":
            raise RoutingError(sid, "automatic max default")
        if task["criticalAstraApproval"] and default_profile["model"] == "astra":
            raise RoutingError(sid, "critical Astra cannot be automatic default")

    for role_name, role in roles.items():
        if not _identifier(role_name) or not _exact(role, ROLE_FIELDS):
            raise RoutingError(sid, f"role: {role_name}")
        allowed = role["allowedProfiles"]
        if (
            not isinstance(allowed, list)
            or not allowed
            or len(allowed) != len(set(allowed))
            or any(profile not in profiles for profile in allowed)
            or role["defaultProfile"] not in allowed
        ):
            raise RoutingError(sid, "role profiles")
    if any(role not in roles for role in review_roles):
        raise RoutingError(sid, "review role missing")
    if set(eligibility) != set(tasks):
        raise RoutingError(sid, "eligibility task drift")
    for task_name, eligible_roles in eligibility.items():
        if (
            not isinstance(eligible_roles, list)
            or not eligible_roles
            or len(eligible_roles) != len(set(eligible_roles))
            or any(role not in roles for role in eligible_roles)
        ):
            raise RoutingError(sid, f"eligibility: {task_name}")

    aliases = policy["migrationAliases"]
    if not isinstance(aliases, dict) or any(
        not _identifier(alias) or target not in profiles
        for alias, target in aliases.items()
    ):
        raise RoutingError(sid, "migration aliases")
    if aliases.get("apex-max") != "sol-max" or aliases.get("pinned-top-pro") != "sol-xhigh":
        raise RoutingError(sid, "legacy alias semantics")


def load_contracts(
    catalog_path: Path = DEFAULT_CATALOG,
    policy_path: Path = DEFAULT_POLICY,
) -> tuple[dict[str, Any], dict[str, Any]]:
    catalog = _load_json(Path(catalog_path), "E_MODEL_V2_CATALOG_INVALID")
    policy = _load_json(Path(policy_path), "E_MODEL_V2_POLICY_INVALID")
    _validate_catalog(catalog)
    _validate_policy(policy, catalog)
    return catalog, policy
