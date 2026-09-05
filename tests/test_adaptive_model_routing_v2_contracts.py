from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "docs" / "model-routing-v2"
SCHEMA = V2 / "adaptive-routing-contracts.v2.schema.json"
EXAMPLES = V2 / "examples.v2.json"
README = V2 / "README.md"
SPEC = ROOT / "docs" / "superpowers" / "specs" / "2026-09-04-adaptive-lead-model-routing-v2-design.md"
PLAN = ROOT / "docs" / "superpowers" / "plans" / "2026-09-04-adaptive-lead-model-routing-v2-implementation.md"
AUDIT = ROOT / "docs" / "adaptive-model-routing-v2-audit-2026-09-04.md"
DOCS_INDEX = ROOT / "docs" / "README.md"


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_definition(schema: dict[str, object], name: str, instance: object) -> None:
    wrapper = {
        "$schema": schema["$schema"],
        "$defs": schema["$defs"],
        "$ref": f"#/$defs/{name}",
    }
    jsonschema.Draft202012Validator(
        wrapper, format_checker=jsonschema.FormatChecker(),
    ).validate(instance)


def test_v2_documentation_surface_exists() -> None:
    for path in (SCHEMA, EXAMPLES, README, SPEC, PLAN, AUDIT):
        assert path.is_file(), path


def test_contract_bundle_is_valid_draft_2020_12_schema() -> None:
    schema = _load(SCHEMA)
    assert isinstance(schema, dict)
    jsonschema.Draft202012Validator.check_schema(schema)
    assert set(schema["$defs"]) == {
        "leadLease",
        "modelRegistrySnapshot",
        "dispatchSpec",
        "routeRequest",
        "routeDecision",
        "workerResult",
    }


def test_all_examples_validate_against_their_contracts() -> None:
    schema = _load(SCHEMA)
    examples = _load(EXAMPLES)
    assert isinstance(schema, dict) and isinstance(examples, dict)
    mapping = {
        "leadLease": "leadLease",
        "registrySnapshot": "modelRegistrySnapshot",
        "routeRequest": "routeRequest",
        "routeDecision": "routeDecision",
        "workerResult": "workerResult",
    }
    for example_name, definition in mapping.items():
        _validate_definition(schema, definition, examples[example_name])


def test_stable_contract_does_not_hardcode_model_generation_numbers() -> None:
    forbidden = re.compile(r"(?i)\b(?:gpt|grok|glm|kimi)[-_ ]?\d")
    for path in (SCHEMA, README, SPEC):
        text = path.read_text(encoding="utf-8")
        assert forbidden.search(text) is None, path


def test_lead_is_provider_neutral_but_single_owner() -> None:
    schema = _load(SCHEMA)
    lease = schema["$defs"]["leadLease"]
    required = set(lease["required"])
    assert {"leadHostAdapterId", "leaseId", "epoch", "holderRunId", "state"} <= required
    host_schema = lease["properties"]["leadHostAdapterId"]
    assert "enum" not in host_schema


def test_dispatch_is_leaf_nonauthorizing_and_contract_bound() -> None:
    schema = _load(SCHEMA)
    dispatch = schema["$defs"]["dispatchSpec"]
    required = set(dispatch["required"])
    assert {
        "policySnapshotId",
        "registrySnapshotId",
        "evaluationSnapshotId",
        "assignedRole",
        "scopeId",
        "scopeDigest",
        "artifactContract",
        "gateContract",
        "worker",
        "maxDelegationDepth",
        "authorizing",
    } <= required
    assert dispatch["properties"]["maxDelegationDepth"]["const"] == 0
    assert dispatch["properties"]["authorizing"]["const"] is False


def test_registry_is_dynamic_and_provider_optional() -> None:
    schema = _load(SCHEMA)
    registry = schema["$defs"]["modelRegistrySnapshot"]
    entry = registry["$defs"]["runtimeEntry"]
    provider_schema = entry["properties"]["providerFamily"]
    model_schema = entry["properties"]["modelId"]
    assert "enum" not in provider_schema
    assert "enum" not in model_schema
    assert "availabilityState" in entry["required"]
    assert "admissionState" in entry["required"]


def test_selection_order_prioritizes_quality_scope_and_challenge_before_cost() -> None:
    schema = _load(SCHEMA)
    request = schema["$defs"]["routeRequest"]
    expected = [
        "hard-admissibility",
        "quality-floor",
        "scope-coverage",
        "independent-challenge",
        "evidence-quality",
        "accepted-result-cost",
        "latency",
        "stable-id",
    ]
    assert request["properties"]["selectionOrder"]["const"] == expected


def test_diversity_can_degrade_without_being_silently_claimed() -> None:
    schema = _load(SCHEMA)
    decision = schema["$defs"]["routeDecision"]
    assert set(decision["properties"]["diversityStatus"]["enum"]) == {
        "fulfilled",
        "degraded",
        "not-required",
    }
    assert "humanGateRequired" in decision["required"]
    assert decision["properties"]["authorizing"]["const"] is False


def test_docs_define_blind_proposals_cross_critique_and_empirical_arbitration() -> None:
    text = SPEC.read_text(encoding="utf-8")
    for phrase in (
        "blind proposals",
        "scope expansion",
        "cross-critique",
        "empirical arbitration",
        "marginal information gain",
        "GLM",
        "Version 2",
    ):
        assert phrase in text


def test_docs_index_links_v2_surface() -> None:
    index = DOCS_INDEX.read_text(encoding="utf-8")
    assert "model-routing-v2/README.md" in index
    assert "adaptive-model-routing-v2-audit-2026-09-04.md" in index


def test_critical_degraded_diversity_requires_human_gate() -> None:
    schema = _load(SCHEMA)
    decision = _load(EXAMPLES)["routeDecision"]
    decision["riskClass"] = "critical"
    decision["status"] = "degraded"
    decision["diversityStatus"] = "degraded"
    decision["degradationReasons"] = ["independent-family-shortfall"]
    decision["humanGateRequired"] = False
    validator = jsonschema.Draft202012Validator(
        {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": "#/$defs/routeDecision"}
    )
    assert list(validator.iter_errors(decision))
    decision["humanGateRequired"] = True
    validator.validate(decision)


def test_worker_result_cannot_claim_acceptance_or_authority() -> None:
    schema = _load(SCHEMA)
    worker = _load(EXAMPLES)["workerResult"]
    worker["accepted"] = True
    validator = jsonschema.Draft202012Validator(
        {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": "#/$defs/workerResult"}
    )
    assert list(validator.iter_errors(worker))
    worker.pop("accepted")
    worker["authorizing"] = True
    assert list(validator.iter_errors(worker))
    worker["authorizing"] = False
    worker["maxDelegationDepth"] = 1
    assert list(validator.iter_errors(worker))


def test_registry_accepts_future_model_identity_without_schema_change() -> None:
    schema = _load(SCHEMA)
    registry = _load(EXAMPLES)["registrySnapshot"]
    future = registry["entries"][0]
    future["runtimeEntryId"] = "future-vendor-current"
    future["providerAdapterId"] = "future-adapter"
    future["runtimeId"] = "future-cli"
    future["providerFamily"] = "future-vendor"
    future["lineageId"] = "future-lineage"
    future["modelId"] = "runtime-observed-future-model"
    future["availabilityState"] = "not-entitled"
    _validate_definition(schema, "modelRegistrySnapshot", registry)


def test_stable_v2_documentation_surface_avoids_model_generation_pins() -> None:
    forbidden = re.compile(r"(?i)\b(?:gpt|grok|glm|kimi)[-_ ]?\d")
    for path in (SCHEMA, README, SPEC, PLAN, AUDIT):
        assert forbidden.search(path.read_text(encoding="utf-8")) is None, path


def test_route_decision_binds_same_snapshots_as_dispatches() -> None:
    examples = _load(EXAMPLES)
    decision = examples["routeDecision"]
    keys = ("leadLeaseId", "policySnapshotId", "registrySnapshotId", "evaluationSnapshotId")
    for dispatch in decision["selectedPortfolio"]:
        assert all(dispatch[key] == decision[key] for key in keys)
        assert dispatch["maxDelegationDepth"] == 0
        assert dispatch["authorizing"] is False


@pytest.mark.parametrize("status", ["selected", "degraded"])
def test_dispatching_decision_requires_a_worker(status: str) -> None:
    schema = _load(SCHEMA)
    decision = _load(EXAMPLES)["routeDecision"]
    decision["status"] = status
    decision["selectedPortfolio"] = []
    decision["independentFamilyCount"] = 0
    decision["approachTagCount"] = 0
    with pytest.raises(jsonschema.ValidationError):
        _validate_definition(schema, "routeDecision", decision)
    decision["status"] = "blocked"
    _validate_definition(schema, "routeDecision", decision)


def test_selected_decision_cannot_hide_unresolved_contradictions() -> None:
    schema = _load(SCHEMA)
    decision = _load(EXAMPLES)["routeDecision"]
    decision["unresolvedContradictions"] = ["finding-open"]
    decision["humanGateRequired"] = True
    with pytest.raises(jsonschema.ValidationError):
        _validate_definition(schema, "routeDecision", decision)
    decision["status"] = "degraded"
    _validate_definition(schema, "routeDecision", decision)
    decision["humanGateRequired"] = False
    with pytest.raises(jsonschema.ValidationError):
        _validate_definition(schema, "routeDecision", decision)


def test_degraded_diversity_cannot_report_selected_status() -> None:
    schema = _load(SCHEMA)
    decision = _load(EXAMPLES)["routeDecision"]
    decision["diversityStatus"] = "degraded"
    decision["degradationReasons"] = ["independent-family-shortfall"]
    with pytest.raises(jsonschema.ValidationError):
        _validate_definition(schema, "routeDecision", decision)
    decision["status"] = "degraded"
    _validate_definition(schema, "routeDecision", decision)


@pytest.mark.parametrize("status", ["revise", "blocked", "failed"])
def test_worker_pass_requires_completed_execution(status: str) -> None:
    schema = _load(SCHEMA)
    worker = _load(EXAMPLES)["workerResult"]
    worker["status"] = status
    worker["gateClaim"] = "PASS"
    with pytest.raises(jsonschema.ValidationError):
        _validate_definition(schema, "workerResult", worker)
    worker["gateClaim"] = "none"
    _validate_definition(schema, "workerResult", worker)


def test_completed_worker_can_request_revision_without_claiming_pass() -> None:
    schema = _load(SCHEMA)
    worker = _load(EXAMPLES)["workerResult"]
    worker["status"] = "completed"
    for gate in ("REVISE", "BLOCKED", "advisory", "none", "PASS"):
        worker["gateClaim"] = gate
        _validate_definition(schema, "workerResult", worker)


@pytest.mark.parametrize("timestamp", [
    "not-a-timestamp", "2026-02-30T15:00:00Z", "2026-09-04T25:00:00Z",
])
def test_example_validator_enforces_calendar_formats(timestamp: str) -> None:
    schema = _load(SCHEMA)
    lease = _load(EXAMPLES)["leadLease"]
    lease["acquiredAt"] = timestamp
    with pytest.raises(jsonschema.ValidationError):
        _validate_definition(schema, "leadLease", lease)


@pytest.mark.parametrize("timestamp", [
    "2026-09-04T18:00:00+03:00", "2026-09-04t15:00:00z",
])
def test_core_timestamp_uses_the_same_utc_wire_form_as_operational_contract(
    timestamp: str,
) -> None:
    schema = _load(SCHEMA)
    lease = _load(EXAMPLES)["leadLease"]
    lease["acquiredAt"] = timestamp
    with pytest.raises(jsonschema.ValidationError):
        _validate_definition(schema, "leadLease", lease)
