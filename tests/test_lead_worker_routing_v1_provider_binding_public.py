"""Exercise known model/provider binding through the public resolver and CLI."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "src.codex/skills/lead-worker-routing/scripts/resolve.py"


def _request(provider: str, model: str) -> dict:
    families = {"codex": "openai", "claude": "anthropic", "kimi": "moonshot", "grok": "xai"}
    return {
        "schemaVersion": 1,
        "dispatchId": "dispatch-fixture",
        "policySnapshotId": "policy-fixture",
        "leadHost": "codex",
        "assignedRole": "analyst",
        "scopeId": "scope-fixture",
        "capabilitySlot": "engineering-challenge",
        "mutationClass": "read-only",
        "requiredTools": [],
        "excludedProviderFamilies": [],
        "artifactContract": "challenge-report-v1",
        "gateContract": "lead-verifies-artifact-v1",
        "candidates": [{
            "candidateId": "candidate-fixture",
            "provider": provider,
            "runtime": provider + "-cli",
            "providerFamily": families[provider],
            "model": model,
            "effort": "high",
            "priority": 1,
            "availability": "available",
            "maxMutationClass": "read-only",
            "capabilities": ["engineering-challenge"],
            "tools": [],
            "isolatedFromLead": True,
            "maxDelegationDepth": 0,
            "authorizing": False,
            "evidenceSnapshotId": "evidence-fixture",
        }],
    }


def _public():
    spec = importlib.util.spec_from_file_location("worker_public_binding_test", PUBLIC)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("model", ["gpt-6-astra", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"])
@pytest.mark.parametrize("provider", ["claude", "kimi", "grok"])
def test_public_facade_rejects_mismatch_and_binds_original_input(model, provider):
    request = _request(provider, model)
    original = copy.deepcopy(request)
    result = _public().resolve_v1_worker_route(request)
    assert result["status"] == "denied"
    assert result["rejections"][0]["stableId"] == "E_LEAD_WORKER_V1_MODEL_PROVIDER_MISMATCH"
    assert result["selectedCandidate"] is None
    assert result["executionAuthorized"] is False
    assert result["authorizing"] is False
    expected = hashlib.sha256(json.dumps(original, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest()
    assert result["requestFingerprint"] == expected
    assert request == original


@pytest.mark.parametrize("transport", ["stdin", "file"])
def test_cli_mismatch_denies_without_launching_or_disclosing_raw_errors(tmp_path, transport):
    text = json.dumps(_request("claude", "gpt-6-astra"))
    path = "-"
    if transport == "file":
        path = str(tmp_path / "request.json")
        Path(path).write_text(text, encoding="utf-8")
    result = subprocess.run([sys.executable, "-S", str(PUBLIC), "--request-file", path], input=text if transport == "stdin" else None, capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 2
    assert result.stderr == ""
    decision = json.loads(result.stdout)
    assert decision["rejections"][0]["stableId"] == "E_LEAD_WORKER_V1_MODEL_PROVIDER_MISMATCH"
    assert decision["selectedCandidate"] is None
    assert decision["executionAuthorized"] is False


def test_explicit_valid_successor_keeps_rejection_and_does_not_gain_authority():
    request = _request("claude", "gpt-6-astra")
    successor = _request("codex", "gpt-5.6-sol")["candidates"][0]
    successor.update(candidateId="successor-fixture", priority=2)
    request["candidates"].append(successor)
    result = _public().resolve_v1_worker_route(request)
    assert result["status"] == "selected"
    assert result["selectedCandidate"]["candidateId"] == "successor-fixture"
    assert result["rejections"][0]["stableId"] == "E_LEAD_WORKER_V1_MODEL_PROVIDER_MISMATCH"
    assert result["requiresAdapterAdmission"] is True
    assert result["executionAuthorized"] is False
    assert result["authorizing"] is False
