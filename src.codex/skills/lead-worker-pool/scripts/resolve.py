#!/usr/bin/env python3
"""Resolve an interchangeable Version 1 CLI worker route without launching it."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
LEAD_HOSTS = frozenset({"codex", "claude"})
V1_PROVIDERS = frozenset({"codex", "claude", "kimi", "grok"})
MUTATION_RANK = {"read-only": 0, "bounded-write": 1}
ADMISSIONS = frozenset(MUTATION_RANK)
AVAILABILITY_STABLE_IDS = {
    "not-configured": "E_WORKER_V1_NOT_CONFIGURED",
    "not-entitled": "E_WORKER_V1_NOT_ENTITLED",
    "quota-exhausted": "E_WORKER_V1_QUOTA_EXHAUSTED",
    "temporary-failure": "E_WORKER_V1_TEMPORARY_FAILURE",
    "auth-invalid": "E_WORKER_V1_AUTH_INVALID",
    "quarantined": "E_WORKER_V1_QUARANTINED",
    "unavailable": "E_WORKER_V1_UNAVAILABLE",
    "unknown": "E_WORKER_V1_AVAILABILITY_UNKNOWN",
}
AVAILABILITY_STATES = frozenset({"available", *AVAILABILITY_STABLE_IDS})
OPERATOR_ACTION_STATES = frozenset({"auth-invalid", "quarantined", "unknown"})
CANDIDATE_FIELDS = frozenset(
    {
        "routeId",
        "provider",
        "runtime",
        "model",
        "effort",
        "providerFamily",
        "status",
        "admission",
        "capabilities",
        "tools",
    }
)
REQUEST_REQUIRED_FIELDS = frozenset(
    {
        "leadHost",
        "assignedRole",
        "capabilitySlot",
        "mutationClass",
        "artifactContract",
        "gateContract",
        "candidates",
    }
)
REQUEST_OPTIONAL_FIELDS = frozenset(
    {
        "requiredTools",
        "requestedProvider",
        "allowProviderFallback",
        "allowSelfProvider",
        "requireIndependentFamily",
        "authorProviderFamily",
    }
)
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z", re.ASCII)
MAX_CANDIDATES = 32
MAX_LIST_ITEMS = 64
MAX_REQUEST_BYTES = 1024 * 1024


def _token(value: Any) -> bool:
    return isinstance(value, str) and bool(TOKEN.fullmatch(value))


def _unique_tokens(
    value: Any, *, max_items: int = MAX_LIST_ITEMS
) -> tuple[str, ...] | None:
    if isinstance(value, (str, bytes)) or not isinstance(value, Collection):
        return None
    try:
        items = tuple(value)
    except (TypeError, ValueError):
        return None
    if len(items) > max_items or not all(_token(item) for item in items):
        return None
    if len(items) != len(set(items)):
        return None
    return items


def _base_decision(
    *,
    status: str,
    stable_id: str | None,
    lead_host: str,
    assigned_role: str,
    capability_slot: str,
    mutation_class: str,
    artifact_contract: str,
    gate_contract: str,
    requested_provider: str | None,
    candidate_order: Sequence[str],
    fallback_trace: Sequence[Mapping[str, object]],
    operator_action_required: bool,
) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": status,
        "stableId": stable_id,
        "leadHost": lead_host,
        "assignedRole": assigned_role,
        "capabilitySlot": capability_slot,
        "mutationClass": mutation_class,
        "artifactContract": artifact_contract,
        "gateContract": gate_contract,
        "requestedProvider": requested_provider,
        "candidateOrder": list(candidate_order),
        "fallbackTrace": [dict(row) for row in fallback_trace],
        "fallbackUsed": bool(fallback_trace),
        "fallback": "provider-substitution" if fallback_trace else "none",
        "operatorActionRequired": operator_action_required,
        "resolvedRouteId": None,
        "resolvedProvider": None,
        "resolvedRuntime": None,
        "resolvedModel": None,
        "resolvedEffort": None,
        "resolvedProviderFamily": None,
        "selectionBasis": (
            "requested-provider" if requested_provider else "ordered-candidate-policy"
        ),
        "requiresLeadVerification": True,
        "maxDelegationDepth": 0,
        "authorizing": False,
    }


def _denied(
    stable_id: str, *, lead_host: Any = "", **kwargs: Any
) -> dict[str, Any]:
    safe = lambda value: value if isinstance(value, str) else ""
    return _base_decision(
        status="denied",
        stable_id=stable_id,
        lead_host=safe(lead_host)[:128],
        assigned_role=safe(kwargs.get("assigned_role"))[:128],
        capability_slot=safe(kwargs.get("capability_slot"))[:128],
        mutation_class=safe(kwargs.get("mutation_class"))[:128],
        artifact_contract=safe(kwargs.get("artifact_contract"))[:128],
        gate_contract=safe(kwargs.get("gate_contract"))[:128],
        requested_provider=(
            safe(kwargs.get("requested_provider"))[:128]
            if kwargs.get("requested_provider") is not None
            else None
        ),
        candidate_order=(),
        fallback_trace=(),
        operator_action_required=False,
    )


def _validate_candidate(
    candidate: Any,
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(candidate, Mapping) or set(candidate) != CANDIDATE_FIELDS:
        return None, "E_WORKER_V1_REQUEST_INVALID"
    provider = candidate["provider"]
    if not _token(provider):
        return None, "E_WORKER_V1_REQUEST_INVALID"
    if provider not in V1_PROVIDERS:
        return None, "E_WORKER_V1_PROVIDER_UNSUPPORTED"
    scalar_fields = (
        "routeId",
        "runtime",
        "model",
        "effort",
        "providerFamily",
    )
    if not all(_token(candidate[field]) for field in scalar_fields):
        return None, "E_WORKER_V1_REQUEST_INVALID"
    if candidate["status"] not in AVAILABILITY_STATES:
        return None, "E_WORKER_V1_REQUEST_INVALID"
    if candidate["admission"] not in ADMISSIONS:
        return None, "E_WORKER_V1_REQUEST_INVALID"
    capabilities = _unique_tokens(candidate["capabilities"])
    tools = _unique_tokens(candidate["tools"])
    if capabilities is None or tools is None:
        return None, "E_WORKER_V1_REQUEST_INVALID"
    normalized = dict(candidate)
    normalized["capabilities"] = capabilities
    normalized["tools"] = tools
    return normalized, None


def _trace(
    candidate: Mapping[str, Any], stable_id: str, *, action: bool = False
) -> dict[str, object]:
    return {
        "routeId": candidate["routeId"],
        "provider": candidate["provider"],
        "stableId": stable_id,
        "operatorActionRequired": action,
    }


def resolve_v1_worker_route(
    *,
    lead_host: str,
    assigned_role: str,
    capability_slot: str,
    mutation_class: str,
    artifact_contract: str,
    gate_contract: str,
    candidates: Sequence[Mapping[str, Any]],
    required_tools: Sequence[str] = (),
    requested_provider: str | None = None,
    allow_provider_fallback: bool = True,
    allow_self_provider: bool = False,
    require_independent_family: bool = False,
    author_provider_family: str | None = None,
) -> dict[str, Any]:
    """Select one nonauthorizing CLI worker route from a caller-ranked list."""

    common = {
        "lead_host": lead_host,
        "assigned_role": assigned_role,
        "capability_slot": capability_slot,
        "mutation_class": mutation_class,
        "artifact_contract": artifact_contract,
        "gate_contract": gate_contract,
        "requested_provider": requested_provider,
    }
    scalar_valid = (
        lead_host in LEAD_HOSTS
        and _token(assigned_role)
        and _token(capability_slot)
        and mutation_class in MUTATION_RANK
        and _token(artifact_contract)
        and _token(gate_contract)
        and (requested_provider is None or requested_provider in V1_PROVIDERS)
        and type(allow_provider_fallback) is bool
        and type(allow_self_provider) is bool
        and type(require_independent_family) is bool
        and (author_provider_family is None or _token(author_provider_family))
        and (
            not require_independent_family or author_provider_family is not None
        )
    )
    tools = _unique_tokens(required_tools)
    if not scalar_valid or tools is None:
        return _denied("E_WORKER_V1_REQUEST_INVALID", **common)
    if isinstance(candidates, (str, bytes)) or not isinstance(candidates, Sequence):
        return _denied("E_WORKER_V1_REQUEST_INVALID", **common)
    if not candidates or len(candidates) > MAX_CANDIDATES:
        return _denied("E_WORKER_V1_REQUEST_INVALID", **common)

    normalized: list[dict[str, Any]] = []
    route_ids: set[str] = set()
    for candidate in candidates:
        row, stable_id = _validate_candidate(candidate)
        if stable_id is not None:
            return _denied(stable_id, **common)
        assert row is not None
        if row["routeId"] in route_ids:
            return _denied("E_WORKER_V1_REQUEST_INVALID", **common)
        route_ids.add(row["routeId"])
        normalized.append(row)

    requested_missing = False
    if requested_provider is not None:
        requested = [
            row for row in normalized if row["provider"] == requested_provider
        ]
        others = [
            row for row in normalized if row["provider"] != requested_provider
        ]
        requested_missing = not requested
        ordered = requested + (others if allow_provider_fallback else [])
    else:
        ordered = normalized

    candidate_order = [row["routeId"] for row in ordered]
    fallback_trace: list[dict[str, object]] = []
    operator_action_required = False
    if requested_missing:
        fallback_trace.append(
            {
                "routeId": f"requested:{requested_provider}",
                "provider": requested_provider,
                "stableId": "E_WORKER_V1_REQUESTED_PROVIDER_MISSING",
                "operatorActionRequired": False,
            }
        )

    for candidate in ordered:
        if candidate["provider"] == lead_host and not allow_self_provider:
            fallback_trace.append(
                _trace(candidate, "E_WORKER_V1_SELF_PROVIDER_DISALLOWED")
            )
            continue

        availability = candidate["status"]
        if availability != "available":
            action = availability in OPERATOR_ACTION_STATES
            operator_action_required = operator_action_required or action
            fallback_trace.append(
                _trace(
                    candidate,
                    AVAILABILITY_STABLE_IDS[availability],
                    action=action,
                )
            )
            continue

        if capability_slot not in candidate["capabilities"]:
            fallback_trace.append(
                _trace(candidate, "E_WORKER_V1_CAPABILITY_MISSING")
            )
            continue

        if MUTATION_RANK[candidate["admission"]] < MUTATION_RANK[mutation_class]:
            fallback_trace.append(
                _trace(candidate, "E_WORKER_V1_MUTATION_NOT_ADMITTED")
            )
            continue

        if not set(tools).issubset(candidate["tools"]):
            fallback_trace.append(
                _trace(candidate, "E_WORKER_V1_TOOLS_MISSING")
            )
            continue

        if (
            require_independent_family
            and candidate["providerFamily"] == author_provider_family
        ):
            fallback_trace.append(
                _trace(candidate, "E_WORKER_V1_INDEPENDENCE_REQUIRED")
            )
            continue

        result = _base_decision(
            status="selected",
            stable_id=None,
            lead_host=lead_host,
            assigned_role=assigned_role,
            capability_slot=capability_slot,
            mutation_class=mutation_class,
            artifact_contract=artifact_contract,
            gate_contract=gate_contract,
            requested_provider=requested_provider,
            candidate_order=candidate_order,
            fallback_trace=fallback_trace,
            operator_action_required=operator_action_required,
        )
        result.update(
            {
                "resolvedRouteId": candidate["routeId"],
                "resolvedProvider": candidate["provider"],
                "resolvedRuntime": candidate["runtime"],
                "resolvedModel": candidate["model"],
                "resolvedEffort": candidate["effort"],
                "resolvedProviderFamily": candidate["providerFamily"],
            }
        )
        return result

    explicit_without_fallback = (
        requested_provider is not None and not allow_provider_fallback
    )
    stable_id = (
        "E_WORKER_V1_REQUESTED_PROVIDER_MISSING"
        if explicit_without_fallback and requested_missing
        else "E_WORKER_V1_REQUESTED_PROVIDER_UNAVAILABLE"
        if explicit_without_fallback
        else "E_WORKER_V1_NO_ADMISSIBLE_ROUTE"
    )
    result = _base_decision(
        status="unavailable",
        stable_id=stable_id,
        lead_host=lead_host,
        assigned_role=assigned_role,
        capability_slot=capability_slot,
        mutation_class=mutation_class,
        artifact_contract=artifact_contract,
        gate_contract=gate_contract,
        requested_provider=requested_provider,
        candidate_order=candidate_order,
        fallback_trace=fallback_trace,
        operator_action_required=operator_action_required,
    )
    if explicit_without_fallback:
        result["fallbackUsed"] = False
        result["fallback"] = "none"
    return result


def _load_request(path: Path) -> dict[str, Any]:
    try:
        size = path.stat().st_size
        if size < 2 or size > MAX_REQUEST_BYTES:
            raise ValueError("request size")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("E_WORKER_V1_REQUEST_FILE_INVALID") from exc
    if not isinstance(payload, dict):
        raise ValueError("E_WORKER_V1_REQUEST_FILE_INVALID")
    fields = set(payload)
    if not REQUEST_REQUIRED_FIELDS.issubset(fields) or not fields.issubset(
        REQUEST_REQUIRED_FIELDS | REQUEST_OPTIONAL_FIELDS
    ):
        raise ValueError("E_WORKER_V1_REQUEST_FILE_INVALID")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    args = parser.parse_args(argv)
    try:
        payload = _load_request(Path(args.request))
        result = resolve_v1_worker_route(
            lead_host=payload["leadHost"],
            assigned_role=payload["assignedRole"],
            capability_slot=payload["capabilitySlot"],
            mutation_class=payload["mutationClass"],
            artifact_contract=payload["artifactContract"],
            gate_contract=payload["gateContract"],
            candidates=payload["candidates"],
            required_tools=payload.get("requiredTools", ()),
            requested_provider=payload.get("requestedProvider"),
            allow_provider_fallback=payload.get("allowProviderFallback", True),
            allow_self_provider=payload.get("allowSelfProvider", False),
            require_independent_family=payload.get(
                "requireIndependentFamily", False
            ),
            author_provider_family=payload.get("authorProviderFamily"),
        )
    except ValueError as exc:
        result = _denied(str(exc))
    json.dump(result, sys.stdout, sort_keys=True, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0 if result["status"] == "selected" else 2


if __name__ == "__main__":
    raise SystemExit(main())
