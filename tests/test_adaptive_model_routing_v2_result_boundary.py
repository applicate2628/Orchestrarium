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


def test_lead_fence_names_the_digest_profile() -> None:
    schema = _load(SCHEMA)
    fence = schema["$defs"]["leadFence"]
    assert "digestProfileId" in fence["required"]


def test_budget_bounds_prompt_and_result_bytes() -> None:
    schema = _load(SCHEMA)
    budget = schema["$defs"]["resourceBudget"]
    assert {
        "maxPromptBytesPerDispatch",
        "maxResultBytesPerDispatch",
    } <= set(budget["required"])


def test_dispatch_binds_supervision_cancellation_and_terminal_receipt() -> None:
    schema = _load(SCHEMA)
    dispatch = schema["$defs"]["dispatchControl"]
    assert {
        "supervisionPolicyId",
        "cancellationId",
        "terminalReceiptRequired",
    } <= set(dispatch["required"])
    assert dispatch["properties"]["terminalReceiptRequired"]["const"] is True


def test_worker_result_is_bound_to_dispatch_attempt_fence_and_cleanup() -> None:
    schema = _load(SCHEMA)
    assert "workerResultControl" in schema["$defs"]
    result_schema = schema["$defs"]["workerResultControl"]
    assert {
        "dispatchId",
        "dispatchSpecDigest",
        "leadFence",
        "attemptOrdinal",
        "idempotencyKey",
        "terminalReceiptRef",
        "supervisionPolicyId",
        "cancellationId",
        "processReaped",
        "cleanupStatus",
        "contractValidated",
        "fenceDisposition",
        "outputUsable",
        "authorizing",
    } <= set(result_schema["required"])
    assert result_schema["properties"]["processReaped"]["const"] is True
    assert result_schema["properties"]["contractValidated"]["const"] is True
    assert result_schema["properties"]["authorizing"]["const"] is False

    example = copy.deepcopy(_load(EXAMPLES)["workerResultControl"])
    _validator(schema, "workerResultControl").validate(example)

    example["fenceDisposition"] = "stale-rejected"
    example["revalidationEvidenceRef"] = "stale-fence-evidence"
    example["outputUsable"] = True
    assert list(_validator(schema, "workerResultControl").iter_errors(example))


def test_route_outcome_is_routing_evidence_not_merge_authority() -> None:
    schema = _load(SCHEMA)
    outcome = schema["$defs"]["routeOutcome"]
    assert outcome["properties"]["acceptanceScope"]["const"] == "routing-evaluation"
    assert outcome["properties"]["authorizing"]["const"] is False
