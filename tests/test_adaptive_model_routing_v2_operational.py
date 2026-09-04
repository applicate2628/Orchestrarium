from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "docs" / "model-routing-v2"
SCHEMA = V2 / "adaptive-routing-operational.v2.schema.json"
EXAMPLES = V2 / "operational-examples.v2.json"
ADDENDUM = V2 / "deep-review-operational-hardening.md"


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator(schema: dict[str, object], definition: str):
    return jsonschema.Draft202012Validator(
        {
            "$schema": schema["$schema"],
            "$defs": schema["$defs"],
            "$ref": f"#/$defs/{definition}",
        }
    )


def _validate(schema: dict[str, object], definition: str, instance: object) -> None:
    _validator(schema, definition).validate(instance)


def test_operational_hardening_surface_exists() -> None:
    for path in (SCHEMA, EXAMPLES, ADDENDUM):
        assert path.is_file(), path


def test_schema_is_valid_and_defines_operational_boundaries() -> None:
    schema = _load(SCHEMA)
    assert isinstance(schema, dict)
    jsonschema.Draft202012Validator.check_schema(schema)
    assert {
        "leadFence",
        "providerPolicy",
        "resourceBudget",
        "effortMapping",
        "writeBoundary",
        "fallbackEvent",
        "candidateRejection",
        "contradiction",
        "routeControl",
        "dispatchControl",
        "decisionControl",
        "routeOutcome",
    } <= set(schema["$defs"])


def test_all_operational_examples_validate() -> None:
    schema = _load(SCHEMA)
    examples = _load(EXAMPLES)
    mapping = {
        "routeControl": "routeControl",
        "dispatchControl": "dispatchControl",
        "writeDispatchControl": "dispatchControl",
        "decisionControl": "decisionControl",
        "routeOutcome": "routeOutcome",
    }
    for example_name, definition in mapping.items():
        _validate(schema, definition, examples[example_name])


def test_route_control_binds_effort_orchestration_data_and_budget() -> None:
    schema = _load(SCHEMA)
    route = schema["$defs"]["routeControl"]
    assert {
        "leadFence",
        "effortIntent",
        "orchestrationMode",
        "providerPolicy",
        "resourceBudget",
        "candidateSetDigest",
        "candidateSetEvidenceRef",
        "candidateSetCompleteness",
    } <= set(route["required"])
    assert set(route["properties"]["effortIntent"]["enum"]) == {
        "minimal",
        "balanced",
        "deep",
        "extended",
        "maximum",
    }


def test_provider_native_orchestration_requires_separate_admission() -> None:
    schema = _load(SCHEMA)
    route = copy.deepcopy(_load(EXAMPLES)["routeControl"])
    route["orchestrationMode"] = "provider-native"
    route["orchestrationAdmissionEvidenceRef"] = None
    assert list(_validator(schema, "routeControl").iter_errors(route))
    route["orchestrationAdmissionEvidenceRef"] = "orchestration-admission-current"
    _validate(schema, "routeControl", route)


def test_data_policy_is_not_overridden_by_model_ranking() -> None:
    schema = _load(SCHEMA)
    policy = schema["$defs"]["providerPolicy"]
    assert {
        "allowedProviderFamilies",
        "forbiddenProviderFamilies",
        "allowedRegions",
        "zeroDataRetentionRequired",
        "sensitiveSourceCodeAllowed",
        "externalWebAllowed",
        "secretMaterialIncluded",
    } <= set(policy["required"])
    assert policy["properties"]["secretMaterialIncluded"]["const"] is False


def test_resource_budget_bounds_portfolio_and_retries() -> None:
    schema = _load(SCHEMA)
    budget = schema["$defs"]["resourceBudget"]
    required = set(budget["required"])
    assert {
        "maxPortfolioSlots",
        "maxParallelDispatches",
        "maxModelCalls",
        "maxAttemptsPerSlot",
        "maxWallSeconds",
        "maxAcceptedResultCost",
    } <= required


def test_write_dispatch_requires_execution_boundary() -> None:
    schema = _load(SCHEMA)
    dispatch = copy.deepcopy(_load(EXAMPLES)["dispatchControl"])
    dispatch["mutationClass"] = "bounded-write"
    dispatch["writeBoundary"] = None
    assert list(_validator(schema, "dispatchControl").iter_errors(dispatch))

    write_dispatch = copy.deepcopy(_load(EXAMPLES)["writeDispatchControl"])
    _validate(schema, "dispatchControl", write_dispatch)
    write_dispatch["writeBoundary"] = None
    assert list(_validator(schema, "dispatchControl").iter_errors(write_dispatch))


def test_effort_mapping_cannot_silently_round_down() -> None:
    schema = _load(SCHEMA)
    mapping = schema["$defs"]["effortMapping"]
    assert set(mapping["properties"]["mappingDisposition"]["enum"]) == {
        "exact",
        "rounded-up",
        "saturated",
    }


def test_unresolved_contradiction_cannot_be_selected_without_human_gate() -> None:
    schema = _load(SCHEMA)
    decision = copy.deepcopy(_load(EXAMPLES)["decisionControl"])
    decision["status"] = "selected"
    decision["humanGateRequired"] = False
    decision["humanGateContract"] = None
    decision["contradictions"] = [
        {
            "contradictionId": "contradiction-open",
            "severity": "high",
            "targetSlotIds": ["primary"],
            "descriptionRef": "artifact-contradiction-open",
            "evidenceRefs": ["evidence-contradiction-open"],
            "status": "unresolved",
            "resolutionRef": None,
        }
    ]
    assert list(_validator(schema, "decisionControl").iter_errors(decision))

    decision["status"] = "degraded"
    decision["humanGateRequired"] = True
    decision["humanGateContract"] = "human-contradiction-gate"
    _validate(schema, "decisionControl", decision)


def test_fallback_failure_classes_have_typed_dispositions() -> None:
    schema = _load(SCHEMA)
    event = {
        "eventId": "fallback-current",
        "slotId": "primary",
        "fromRuntimeEntryId": "worker-a",
        "toRuntimeEntryId": "worker-b",
        "failureClass": "availability-fallback",
        "stableId": "E_NOT_ENTITLED",
        "evidenceRef": "availability-evidence-current",
        "disposition": "next-candidate",
        "occurredAt": "2026-09-04T16:00:00Z",
    }
    _validate(schema, "fallbackEvent", event)
    event["disposition"] = "quarantine"
    assert list(_validator(schema, "fallbackEvent").iter_errors(event))


def test_accepted_outcome_requires_quality_and_resolved_human_gate() -> None:
    schema = _load(SCHEMA)
    outcome = copy.deepcopy(_load(EXAMPLES)["routeOutcome"])
    outcome["accepted"] = True
    outcome["finalDisposition"] = "accepted"
    outcome["qualityCriteriaMet"] = False
    assert list(_validator(schema, "routeOutcome").iter_errors(outcome))

    outcome["qualityCriteriaMet"] = True
    outcome["humanGateRequired"] = True
    outcome["humanGateResolved"] = False
    assert list(_validator(schema, "routeOutcome").iter_errors(outcome))

    outcome["humanGateResolved"] = True
    _validate(schema, "routeOutcome", outcome)


def test_operational_contracts_are_generation_neutral() -> None:
    forbidden = re.compile(r"(?i)\b(?:gpt|grok|glm|kimi)[-_ ]?\d")
    for path in (SCHEMA, ADDENDUM):
        assert forbidden.search(path.read_text(encoding="utf-8")) is None, path
