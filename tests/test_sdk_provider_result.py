"""SDK result receiving keeps historical CLI records and nonauthority separate."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def owner():
    spec = importlib.util.spec_from_file_location("sdk_result_owner", ROOT / "scripts/provider_prompt.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def payload():
    controls = {"exitCode": 0, "token": "COMPLETE:EXTERNAL_NONAUTHORIZING",
                "status": "completed", "gate": "PASS", "note": "fixture"}
    return {
        "schema": "orchestrarium.provider-result.v3", "provider": "codex",
        "model": "fixture-model", "effort": "high", "resultText": "{}",
        **controls, "primaryOutcome": controls.copy(), "cleanupStatus": "complete",
        "authorizing": False, "closesRunIds": [], "independentVerificationRequired": True,
        "terminalClass": "external-nonauthorizing", "actualExecutionPath": "direct-external-sdk",
        "workItem": "fixture-item", "assignedRole": "architecture-reviewer",
        "executionRole": "external-reviewer", "artifactIdentity": "fixture-artifact",
        "externalDispatchId": "dispatch-fixture-001", "externalEvidenceRunId": "evidence-fixture-001",
        "effortMappingLoss": "none",
        "sdkExecution": {"schemaVersion": 1, "adapter": "openai-codex",
                         "sdkVersion": "0.163.0", "runtimeVersion": "0.163.0",
                         "model": "fixture-model", "effort": "high",
                         "sandboxMode": "read-only", "approvalPolicy": "deny_all",
                         "accountBinding": "fixture-account"},
    }


def encode(module, record):
    prefix = module.SDK_RESULT_PREFIX if record.get("schema") == "orchestrarium.provider-result.v3" else module.RESULT_PREFIX
    return prefix + json.dumps(record, separators=(",", ":")) + "\n"


def test_sdk_result_round_trip_and_scan_projection():
    module = owner()
    record = payload()
    assert module.parse_provider_result(encode(module, record)) == record
    projection = module._provider_result_scan_projection(record)
    assert projection["sdkExecution"] == record["sdkExecution"]
    assert projection["artifactIdentity"] == record["artifactIdentity"]


@pytest.mark.parametrize("change", [
    {"authorizing": True}, {"closesRunIds": ["other-run"]},
    {"actualExecutionPath": "internal"}, {"actualExecutionPath": "direct-external-cli"},
    {"launchFlags": []}, {"executionRole": "internal"},
    {"externalEvidenceRunId": "dispatch-fixture-001"}, {"artifactIdentity": ""},
    {"model": "different-model"}, {"effort": "low"},
    {"schema": "orchestrarium.provider-result.v2"}, {"unknownField": "unclassified"},
])
def test_sdk_result_rejects_mismatch_and_authority_escalation(change):
    module = owner()
    record = payload()
    record.update(change)
    with pytest.raises(ValueError):
        module.parse_provider_result(encode(module, record))


def test_legacy_cli_result_needs_no_sdk_provenance():
    module = owner()
    record = payload()
    record.pop("sdkExecution")
    record["schema"] = "orchestrarium.provider-result.v2"
    record["actualExecutionPath"] = "direct-external-cli"
    assert module.parse_provider_result(encode(module, record)) == record


def test_sdk_result_requires_matching_version_prefix():
    module = owner()
    encoded = encode(module, payload()).replace(module.SDK_RESULT_PREFIX, module.RESULT_PREFIX, 1)
    with pytest.raises(ValueError, match="version prefix"):
        module.parse_provider_result(encoded)


@pytest.mark.parametrize("member", ['"provider":"other",', '"sdkExecution":null,'])
def test_sdk_duplicate_fields_are_rejected(member):
    module = owner()
    line = encode(module, payload()).replace("{", "{" + member, 1)
    with pytest.raises(ValueError, match="duplicate"):
        module.parse_provider_result(line)


@pytest.mark.parametrize("number", ["NaN", "Infinity", "1e9999"])
def test_sdk_nonfinite_fields_are_rejected(number):
    module = owner()
    line = encode(module, payload()).replace('"exitCode":0', '"exitCode":' + number, 1)
    with pytest.raises(ValueError, match="nonfinite"):
        module.parse_provider_result(line)
