#!/usr/bin/env python3
"""Private selection core for provider-neutral Orchestrarium Version 1 routing.

This module is import-only. The supported command-line entrypoint is resolve.py,
which adds request fingerprinting, native-host binding, strict JSON parsing, and
safe request-file handling before delegating to this selection core.
"""

from __future__ import annotations

import json
import re
import sys

REQUEST_FIELDS = frozenset(
    {
        "schemaVersion",
        "dispatchId",
        "policySnapshotId",
        "leadHost",
        "assignedRole",
        "scopeId",
        "capabilitySlot",
        "mutationClass",
        "requiredTools",
        "excludedProviderFamilies",
        "artifactContract",
        "gateContract",
        "candidates",
    }
)
CANDIDATE_FIELDS = frozenset(
    {
        "candidateId",
        "provider",
        "runtime",
        "providerFamily",
        "model",
        "effort",
        "priority",
        "availability",
        "maxMutationClass",
        "capabilities",
        "tools",
        "isolatedFromLead",
        "maxDelegationDepth",
        "authorizing",
        "evidenceSnapshotId",
    }
)
LEAD_HOSTS = frozenset({"codex", "claude"})
V1_PROVIDERS = frozenset({"codex", "claude", "kimi", "grok"})
PROVIDER_FAMILIES = {
    "codex": "openai",
    "claude": "anthropic",
    "kimi": "moonshot",
    "grok": "xai",
}
PROVIDER_RUNTIMES = {
    "codex": frozenset({"codex-cli", "codex-native"}),
    "claude": frozenset({"claude-cli", "claude-native"}),
    "kimi": frozenset({"kimi-cli"}),
    "grok": frozenset({"grok-cli"}),
}
MUTATION_CLASSES = ("read-only", "bounded-write", "workspace-write")
MUTATION_RANK = {name: index for index, name in enumerate(MUTATION_CLASSES)}
PROVIDER_MUTATION_CEILING = {
    "codex": "workspace-write",
    "claude": "workspace-write",
    "kimi": "read-only",
    "grok": "read-only",
}
AVAILABILITY_IDS = {
    "not-configured": "E_LEAD_WORKER_V1_CANDIDATE_NOT_CONFIGURED",
    "not-entitled": "E_LEAD_WORKER_V1_CANDIDATE_NOT_ENTITLED",
    "quota-exhausted": "E_LEAD_WORKER_V1_CANDIDATE_QUOTA_EXHAUSTED",
    "temporary-transport-failure": "E_LEAD_WORKER_V1_CANDIDATE_TRANSPORT_FAILURE",
    "auth-invalid": "E_LEAD_WORKER_V1_CANDIDATE_AUTH_INVALID",
    "contract-violation": "E_LEAD_WORKER_V1_CANDIDATE_CONTRACT_VIOLATION",
    "unavailable": "E_LEAD_WORKER_V1_CANDIDATE_UNAVAILABLE",
}
AVAILABILITY_FAILURE_CLASS = {
    "not-configured": "availability-fallback",
    "not-entitled": "availability-fallback",
    "quota-exhausted": "availability-fallback",
    "temporary-transport-failure": "availability-fallback",
    "unavailable": "availability-fallback",
    "auth-invalid": "provider-hard-failure",
    "contract-violation": "provider-hard-failure",
}
AVAILABILITIES = frozenset({"available", *AVAILABILITY_IDS})
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z", re.ASCII)
MAX_CANDIDATES = 128
MAX_PRIORITY = 2**31 - 1
MAX_REQUEST_BYTES = 1024 * 1024
PRIVATE_ENTRYPOINT_STABLE_ID = "E_LEAD_WORKER_V1_PRIVATE_ENTRYPOINT"
# These are operator floors for exact known models, not a capability ordering.
CODEX_EFFORT_ORDER = ("low", "medium", "high", "xhigh", "max")
CODEX_MODEL_EFFORT_FLOORS = {
    "gpt-6-astra": "medium",
    "gpt-5.6-sol": "high",
    "gpt-5.6-terra": "high",
}


def _request_context(request: object) -> dict[str, object | None]:
    fields = (
        "dispatchId",
        "policySnapshotId",
        "leadHost",
        "assignedRole",
        "scopeId",
        "capabilitySlot",
        "mutationClass",
        "artifactContract",
        "gateContract",
    )
    source = request if isinstance(request, dict) else {}
    context: dict[str, object | None] = {}
    for field in fields:
        value = source.get(field)
        context[field] = value if _is_token(value) else None
    tools = source.get("requiredTools")
    excluded = source.get("excludedProviderFamilies")
    context["requiredTools"] = sorted(tools) if _valid_string_list(tools) else []
    context["excludedProviderFamilies"] = (
        sorted(excluded) if _valid_string_list(excluded) else []
    )
    return context


def _decision(
    *,
    status: str,
    stable_id: str | None,
    context: dict[str, object | None],
    selected_candidate: dict[str, object] | None = None,
    fallback_events: list[dict[str, object]] | None = None,
    rejections: list[dict[str, str]] | None = None,
    selection_basis: str,
) -> dict[str, object]:
    selected = status == "selected"
    events = fallback_events or []
    hard_failure = any(
        event.get("failureClass") == "provider-hard-failure" for event in events
    )
    return {
        "schemaVersion": 1,
        "status": status,
        "stableId": stable_id,
        "dispatchId": context["dispatchId"],
        "policySnapshotId": context["policySnapshotId"],
        "leadHost": context["leadHost"],
        "assignedRole": context["assignedRole"],
        "scopeId": context["scopeId"],
        "capabilitySlot": context["capabilitySlot"],
        "mutationClass": context["mutationClass"],
        "requiredTools": context["requiredTools"],
        "excludedProviderFamilies": context["excludedProviderFamilies"],
        "artifactContract": context["artifactContract"],
        "gateContract": context["gateContract"],
        "selectedCandidate": selected_candidate if selected else None,
        "fallbackApplied": selected and bool(events),
        "fallbackEvents": events,
        "rejections": rejections or [],
        "selectionBasis": selection_basis,
        "fallbackPolicy": "explicit-candidate-order",
        "hardFailureObserved": hard_failure,
        "requiresOperatorAttention": hard_failure,
        "requiresLeadVerification": selected,
        "maxDelegationDepth": 0,
        "authorizing": False,
    }


def _invalid_request(request: object, stable_id: str) -> dict[str, object]:
    return _decision(
        status="denied",
        stable_id=stable_id,
        context=_request_context(request),
        selection_basis="request-denial",
    )


def _is_token(value: object) -> bool:
    return isinstance(value, str) and bool(TOKEN.fullmatch(value))


def _valid_string_list(value: object, *, maximum: int = 128) -> bool:
    if not isinstance(value, list) or len(value) > maximum:
        return False
    if not all(_is_token(item) for item in value):
        return False
    return len(value) == len(set(value))


def _valid_candidate(candidate: object) -> bool:
    if not isinstance(candidate, dict) or set(candidate) != CANDIDATE_FIELDS:
        return False
    if not all(
        _is_token(candidate[field])
        for field in (
            "candidateId",
            "provider",
            "runtime",
            "providerFamily",
            "model",
            "effort",
            "evidenceSnapshotId",
        )
    ):
        return False
    priority = candidate["priority"]
    if type(priority) is not int or not 0 <= priority <= MAX_PRIORITY:
        return False
    if (
        not _is_token(candidate["availability"])
        or candidate["availability"] not in AVAILABILITIES
    ):
        return False
    if (
        not _is_token(candidate["maxMutationClass"])
        or candidate["maxMutationClass"] not in MUTATION_RANK
    ):
        return False
    if not _valid_string_list(candidate["capabilities"]):
        return False
    if not _valid_string_list(candidate["tools"]):
        return False
    if type(candidate["isolatedFromLead"]) is not bool:
        return False
    delegation_depth = candidate["maxDelegationDepth"]
    if type(delegation_depth) is not int or delegation_depth < 0:
        return False
    return type(candidate["authorizing"]) is bool


def _normalize_candidate(candidate: dict[str, object]) -> dict[str, object]:
    return {
        "candidateId": candidate["candidateId"],
        "provider": candidate["provider"],
        "runtime": candidate["runtime"],
        "providerFamily": candidate["providerFamily"],
        "model": candidate["model"],
        "effort": candidate["effort"],
        "priority": candidate["priority"],
        "availability": candidate["availability"],
        "maxMutationClass": candidate["maxMutationClass"],
        "capabilities": sorted(candidate["capabilities"]),
        "tools": sorted(candidate["tools"]),
        "isolatedFromLead": candidate["isolatedFromLead"],
        "maxDelegationDepth": candidate["maxDelegationDepth"],
        "authorizing": candidate["authorizing"],
        "evidenceSnapshotId": candidate["evidenceSnapshotId"],
    }


def _validate_request(request: object) -> bool:
    if not isinstance(request, dict) or set(request) != REQUEST_FIELDS:
        return False
    if type(request["schemaVersion"]) is not int or request["schemaVersion"] != 1:
        return False
    if not all(
        _is_token(request[field])
        for field in (
            "dispatchId",
            "policySnapshotId",
            "leadHost",
            "assignedRole",
            "scopeId",
            "capabilitySlot",
            "artifactContract",
            "gateContract",
        )
    ):
        return False
    if (
        not _is_token(request["mutationClass"])
        or request["mutationClass"] not in MUTATION_RANK
    ):
        return False
    if not _valid_string_list(request["requiredTools"]):
        return False
    if not _valid_string_list(request["excludedProviderFamilies"]):
        return False
    candidates = request["candidates"]
    if not isinstance(candidates, list) or len(candidates) > MAX_CANDIDATES:
        return False
    if not all(_valid_candidate(candidate) for candidate in candidates):
        return False
    identities = [candidate["candidateId"] for candidate in candidates]
    return len(identities) == len(set(identities))


def _policy_rejection(
    candidate: dict[str, object],
    *,
    lead_host: str,
    capability_slot: str,
    mutation_class: str,
    required_tools: set[str],
    excluded_provider_families: set[str],
) -> str | None:
    provider = candidate["provider"]
    if provider not in V1_PROVIDERS:
        return "E_LEAD_WORKER_V1_PROVIDER_NOT_ADMITTED"
    if candidate["providerFamily"] != PROVIDER_FAMILIES[provider]:
        return "E_LEAD_WORKER_V1_PROVIDER_FAMILY_MISMATCH"
    if candidate["runtime"] not in PROVIDER_RUNTIMES[provider]:
        return "E_LEAD_WORKER_V1_PROVIDER_RUNTIME_MISMATCH"
    if candidate["providerFamily"] in excluded_provider_families:
        return "E_LEAD_WORKER_V1_INDEPENDENCE_REQUIRED"
    if candidate["authorizing"]:
        return "E_LEAD_WORKER_V1_WORKER_AUTHORITY_FORBIDDEN"
    if candidate["maxDelegationDepth"] != 0:
        return "E_LEAD_WORKER_V1_RECURSIVE_DELEGATION_FORBIDDEN"
    if capability_slot not in candidate["capabilities"]:
        return "E_LEAD_WORKER_V1_CAPABILITY_MISSING"

    # Exact known model identities cannot be re-labelled as another provider.
    if provider != "codex" and (
        candidate["model"] in CODEX_MODEL_EFFORT_FLOORS
        or candidate["model"] == "gpt-5.6-luna"
    ):
        return "E_LEAD_WORKER_V1_MODEL_PROVIDER_MISMATCH"
    if provider == "codex":
        if candidate["model"] == "gpt-5.6-luna":
            # Luna is native-only under its separate exact mechanical contract.
            return "E_LEAD_WORKER_V1_MECHANICAL_ROUTE_REQUIRED"
        minimum = CODEX_MODEL_EFFORT_FLOORS.get(candidate["model"])
        if minimum is not None:
            effort = candidate["effort"]
            if effort not in CODEX_EFFORT_ORDER:
                return "E_LEAD_WORKER_V1_EFFORT_UNSUPPORTED"
            if CODEX_EFFORT_ORDER.index(effort) < CODEX_EFFORT_ORDER.index(minimum):
                return "E_LEAD_WORKER_V1_EFFORT_BELOW_MINIMUM"

    declared_mutation = candidate["maxMutationClass"]
    provider_ceiling = PROVIDER_MUTATION_CEILING[provider]
    if MUTATION_RANK[declared_mutation] > MUTATION_RANK[provider_ceiling]:
        return "E_LEAD_WORKER_V1_PROVIDER_MUTATION_CEILING"
    if MUTATION_RANK[declared_mutation] < MUTATION_RANK[mutation_class]:
        return "E_LEAD_WORKER_V1_MUTATION_NOT_ADMITTED"
    if not required_tools.issubset(set(candidate["tools"])):
        return "E_LEAD_WORKER_V1_TOOL_MISSING"
    if provider == lead_host and not candidate["isolatedFromLead"]:
        return "E_LEAD_WORKER_V1_SAME_HOST_NOT_ISOLATED"
    return None


def resolve_v1_worker_route(request: dict[str, object]) -> dict[str, object]:
    """Return one exact nonauthorizing worker route or a typed decision."""

    context = _request_context(request)
    if not _validate_request(request):
        return _invalid_request(request, "E_LEAD_WORKER_V1_REQUEST_INVALID")

    lead_host = request["leadHost"]
    capability_slot = request["capabilitySlot"]
    mutation_class = request["mutationClass"]
    if lead_host not in LEAD_HOSTS:
        return _decision(
            status="denied",
            stable_id="E_LEAD_WORKER_V1_LEAD_HOST_UNSUPPORTED",
            context=context,
            selection_basis="lead-host-denial",
        )

    candidates = sorted(
        (_normalize_candidate(candidate) for candidate in request["candidates"]),
        key=lambda item: (item["priority"], item["candidateId"]),
    )
    required_tools = set(request["requiredTools"])
    excluded_provider_families = set(request["excludedProviderFamilies"])
    rejections: list[dict[str, str]] = []
    fallback_events: list[dict[str, object]] = []

    for candidate in candidates:
        rejection = _policy_rejection(
            candidate,
            lead_host=lead_host,
            capability_slot=capability_slot,
            mutation_class=mutation_class,
            required_tools=required_tools,
            excluded_provider_families=excluded_provider_families,
        )
        if rejection is not None:
            rejections.append(
                {"candidateId": str(candidate["candidateId"]), "stableId": rejection}
            )
            continue

        availability = candidate["availability"]
        if availability != "available":
            fallback_events.append(
                {
                    "candidateId": candidate["candidateId"],
                    "provider": candidate["provider"],
                    "evidenceSnapshotId": candidate["evidenceSnapshotId"],
                    "availability": availability,
                    "stableId": AVAILABILITY_IDS[availability],
                    "failureClass": AVAILABILITY_FAILURE_CLASS[availability],
                }
            )
            continue

        return _decision(
            status="selected",
            stable_id=None,
            context=context,
            selected_candidate=candidate,
            fallback_events=fallback_events,
            rejections=rejections,
            selection_basis="explicit-priority-available-admitted",
        )

    if fallback_events:
        return _decision(
            status="unavailable",
            stable_id="E_LEAD_WORKER_V1_NO_AVAILABLE_CANDIDATE",
            context=context,
            fallback_events=fallback_events,
            rejections=rejections,
            selection_basis="explicit-candidates-unavailable",
        )
    return _decision(
        status="denied",
        stable_id="E_LEAD_WORKER_V1_NO_ADMITTED_CANDIDATE",
        context=context,
        rejections=rejections,
        selection_basis="explicit-candidates-policy-denial",
    )


def main(argv: list[str] | None = None) -> int:
    """Fail closed when the private core is invoked as a CLI."""

    del argv
    result = _invalid_request({}, PRIVATE_ENTRYPOINT_STABLE_ID)
    json.dump(result, sys.stdout, sort_keys=True, separators=(",", ":"))
    sys.stdout.write("\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
