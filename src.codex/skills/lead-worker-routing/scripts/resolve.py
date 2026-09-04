#!/usr/bin/env python3
"""Resolve one provider-neutral Orchestrarium Version 1 worker route."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUEST_FIELDS = frozenset(
    {
        "schemaVersion",
        "leadHost",
        "capabilitySlot",
        "mutationClass",
        "requiredTools",
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
AVAILABILITIES = frozenset({"available", *AVAILABILITY_IDS})
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z", re.ASCII)
MAX_CANDIDATES = 128
MAX_PRIORITY = 2**31 - 1
MAX_REQUEST_BYTES = 1024 * 1024


def _decision(
    *,
    status: str,
    stable_id: str | None,
    lead_host: str | None,
    capability_slot: str | None,
    mutation_class: str | None,
    selected_candidate: dict[str, object] | None = None,
    fallback_events: list[dict[str, object]] | None = None,
    rejections: list[dict[str, str]] | None = None,
    selection_basis: str,
) -> dict[str, object]:
    selected = status == "selected"
    events = fallback_events or []
    return {
        "schemaVersion": 1,
        "status": status,
        "stableId": stable_id,
        "leadHost": lead_host,
        "capabilitySlot": capability_slot,
        "mutationClass": mutation_class,
        "selectedCandidate": selected_candidate if selected else None,
        "fallbackApplied": selected and bool(events),
        "fallbackEvents": events,
        "rejections": rejections or [],
        "selectionBasis": selection_basis,
        "fallbackPolicy": "explicit-candidate-order",
        "requiresLeadVerification": selected,
        "maxDelegationDepth": 0,
        "authorizing": False,
    }


def _invalid_request(request: object, stable_id: str) -> dict[str, object]:
    lead_host = request.get("leadHost") if isinstance(request, dict) else None
    capability = request.get("capabilitySlot") if isinstance(request, dict) else None
    mutation = request.get("mutationClass") if isinstance(request, dict) else None
    return _decision(
        status="denied",
        stable_id=stable_id,
        lead_host=lead_host if isinstance(lead_host, str) else None,
        capability_slot=capability if isinstance(capability, str) else None,
        mutation_class=mutation if isinstance(mutation, str) else None,
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
    }


def _validate_request(request: object) -> bool:
    if not isinstance(request, dict) or set(request) != REQUEST_FIELDS:
        return False
    if type(request["schemaVersion"]) is not int or request["schemaVersion"] != 1:
        return False
    if not _is_token(request["leadHost"]):
        return False
    if not _is_token(request["capabilitySlot"]):
        return False
    if (
        not _is_token(request["mutationClass"])
        or request["mutationClass"] not in MUTATION_RANK
    ):
        return False
    if not _valid_string_list(request["requiredTools"]):
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
) -> str | None:
    provider = candidate["provider"]
    if provider not in V1_PROVIDERS:
        return "E_LEAD_WORKER_V1_PROVIDER_NOT_ADMITTED"
    if candidate["providerFamily"] != PROVIDER_FAMILIES[provider]:
        return "E_LEAD_WORKER_V1_PROVIDER_FAMILY_MISMATCH"
    if candidate["authorizing"]:
        return "E_LEAD_WORKER_V1_WORKER_AUTHORITY_FORBIDDEN"
    if candidate["maxDelegationDepth"] != 0:
        return "E_LEAD_WORKER_V1_RECURSIVE_DELEGATION_FORBIDDEN"
    if capability_slot not in candidate["capabilities"]:
        return "E_LEAD_WORKER_V1_CAPABILITY_MISSING"

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

    if not _validate_request(request):
        return _invalid_request(request, "E_LEAD_WORKER_V1_REQUEST_INVALID")

    lead_host = request["leadHost"]
    capability_slot = request["capabilitySlot"]
    mutation_class = request["mutationClass"]
    if lead_host not in LEAD_HOSTS:
        return _decision(
            status="denied",
            stable_id="E_LEAD_WORKER_V1_LEAD_HOST_UNSUPPORTED",
            lead_host=lead_host,
            capability_slot=capability_slot,
            mutation_class=mutation_class,
            selection_basis="lead-host-denial",
        )

    candidates = sorted(
        (_normalize_candidate(candidate) for candidate in request["candidates"]),
        key=lambda item: (item["priority"], item["candidateId"]),
    )
    required_tools = set(request["requiredTools"])
    rejections: list[dict[str, str]] = []
    fallback_events: list[dict[str, object]] = []

    for candidate in candidates:
        rejection = _policy_rejection(
            candidate,
            lead_host=lead_host,
            capability_slot=capability_slot,
            mutation_class=mutation_class,
            required_tools=required_tools,
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
                    "availability": availability,
                    "stableId": AVAILABILITY_IDS[availability],
                }
            )
            continue

        return _decision(
            status="selected",
            stable_id=None,
            lead_host=lead_host,
            capability_slot=capability_slot,
            mutation_class=mutation_class,
            selected_candidate=candidate,
            fallback_events=fallback_events,
            rejections=rejections,
            selection_basis="explicit-priority-available-admitted",
        )

    if fallback_events:
        return _decision(
            status="unavailable",
            stable_id="E_LEAD_WORKER_V1_NO_AVAILABLE_CANDIDATE",
            lead_host=lead_host,
            capability_slot=capability_slot,
            mutation_class=mutation_class,
            fallback_events=fallback_events,
            rejections=rejections,
            selection_basis="explicit-candidates-unavailable",
        )
    return _decision(
        status="denied",
        stable_id="E_LEAD_WORKER_V1_NO_ADMITTED_CANDIDATE",
        lead_host=lead_host,
        capability_slot=capability_slot,
        mutation_class=mutation_class,
        rejections=rejections,
        selection_basis="explicit-candidates-policy-denial",
    )


def _read_request(path: str) -> object:
    if path == "-":
        text = sys.stdin.read(MAX_REQUEST_BYTES + 1)
    else:
        with Path(path).open("r", encoding="utf-8", newline="") as handle:
            text = handle.read(MAX_REQUEST_BYTES + 1)
    if len(text.encode("utf-8")) > MAX_REQUEST_BYTES:
        raise ValueError("request too large")
    return json.loads(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-file", required=True)
    args = parser.parse_args(argv)
    try:
        request = _read_request(args.request_file)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        result = _invalid_request({}, "E_LEAD_WORKER_V1_REQUEST_JSON_INVALID")
    else:
        result = resolve_v1_worker_route(request)
    json.dump(result, sys.stdout, sort_keys=True, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0 if result["status"] == "selected" else 2


if __name__ == "__main__":
    raise SystemExit(main())
