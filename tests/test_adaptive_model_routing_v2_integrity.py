from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "docs" / "model-routing-v2"
SCHEMA = V2 / "adaptive-routing-operational.v2.schema.json"
EXAMPLES = V2 / "operational-examples.v2.json"


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


def test_timestamp_contract_is_strict_utc() -> None:
    schema = _load(SCHEMA)
    timestamp = schema["$defs"]["timestamp"]
    assert timestamp["pattern"].endswith("Z$")
    validator = _validator(schema, "timestamp")
    assert not list(validator.iter_errors("2026-09-04T16:00:00Z"))
    assert list(validator.iter_errors("2026-09-04T19:00:00+03:00"))


def test_operational_records_have_content_identities() -> None:
    schema = _load(SCHEMA)
    expected = {
        "routeControl": {"routeControlId", "routeControlDigest"},
        "dispatchControl": {"dispatchControlId", "dispatchControlDigest"},
        "decisionControl": {"decisionControlId", "decisionControlDigest"},
        "routeOutcome": {"outcomeId", "outcomeDigest"},
        "workerResultControl": {"resultControlId", "resultControlDigest", "workerResultDigest"},
    }
    for definition, fields in expected.items():
        assert fields <= set(schema["$defs"][definition]["required"])


def test_destructive_write_requires_separate_approval() -> None:
    schema = _load(SCHEMA)
    boundary = copy.deepcopy(_load(EXAMPLES)["writeDispatchControl"]["writeBoundary"])
    assert boundary["destructiveOperationsAllowed"] is False
    assert boundary["destructiveApprovalRef"] is None
    validator = _validator(schema, "writeBoundary")
    validator.validate(boundary)

    boundary["destructiveOperationsAllowed"] = True
    boundary["destructiveApprovalRef"] = None
    assert list(validator.iter_errors(boundary))
    boundary["destructiveApprovalRef"] = "human-destructive-approval"
    validator.validate(boundary)


def test_worker_result_separates_execution_and_admitting_lead_fences() -> None:
    schema = _load(SCHEMA)
    result_schema = schema["$defs"]["workerResultControl"]
    assert {"executionLeadFence", "admittingLeadFence"} <= set(
        result_schema["required"]
    )
    assert "leadFence" not in result_schema["properties"]

    result = copy.deepcopy(_load(EXAMPLES)["workerResultControl"])
    _validator(schema, "workerResultControl").validate(result)
    assert result["executionLeadFence"] == result["admittingLeadFence"]


def test_execution_settlement_supports_process_native_and_remote_workers() -> None:
    schema = _load(SCHEMA)
    result_schema = schema["$defs"]["workerResultControl"]
    assert {
        "executionKind",
        "executionSettled",
        "processDisposition",
    } <= set(result_schema["required"])
    assert result_schema["properties"]["executionSettled"]["const"] is True
    assert "processReaped" not in result_schema["properties"]

    result = copy.deepcopy(_load(EXAMPLES)["workerResultControl"])
    validator = _validator(schema, "workerResultControl")
    result["executionKind"] = "in-process"
    result["processDisposition"] = "not-applicable"
    validator.validate(result)
    result["processDisposition"] = "reaped"
    assert list(validator.iter_errors(result))


def test_only_availability_fallback_names_automatic_next_candidate() -> None:
    schema = _load(SCHEMA)
    event = copy.deepcopy(_load(EXAMPLES)["decisionControl"]["fallbackEvents"][0])
    validator = _validator(schema, "fallbackEvent")
    validator.validate(event)

    event["failureClass"] = "provider-hard-failure"
    event["disposition"] = "operator-attention"
    assert list(validator.iter_errors(event))
    event["toRuntimeEntryId"] = None
    validator.validate(event)


def test_unneeded_human_gate_cannot_be_reported_as_resolved() -> None:
    schema = _load(SCHEMA)
    outcome = copy.deepcopy(_load(EXAMPLES)["routeOutcome"])
    outcome["humanGateRequired"] = False
    outcome["humanGateResolved"] = True
    assert list(_validator(schema, "routeOutcome").iter_errors(outcome))
