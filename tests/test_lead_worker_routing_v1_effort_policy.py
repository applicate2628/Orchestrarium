"""Exact known-model effort floors do not rank unlike models by effort."""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src.codex" / "skills" / "lead-worker-routing" / "scripts" / "resolve.py"


def load():
    spec = importlib.util.spec_from_file_location("worker_effort_policy_test", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def request(model, effort, *, provider="codex", runtime=None):
    return {
        "schemaVersion": 1, "dispatchId": "dispatch-effort-1",
        "policySnapshotId": "policy-effort-1", "leadHost": "codex",
        "assignedRole": "analyst", "scopeId": "scope-1",
        "capabilitySlot": "analysis", "mutationClass": "read-only",
        "requiredTools": [], "excludedProviderFamilies": [],
        "artifactContract": "analysis-report", "gateContract": "independent-review",
        "candidates": [{
            "candidateId": "candidate-1", "provider": provider,
            "runtime": runtime or f"{provider}-cli",
            "providerFamily": {"codex": "openai", "kimi": "moonshot"}[provider],
            "model": model, "effort": effort, "priority": 1,
            "availability": "available", "maxMutationClass": "read-only",
            "capabilities": ["analysis"], "tools": [], "isolatedFromLead": True,
            "maxDelegationDepth": 0, "authorizing": False,
            "evidenceSnapshotId": "observed-1",
        }],
    }


@pytest.mark.parametrize("model,effort", [
    ("gpt-6-astra", "low"),
    ("gpt-5.6-sol", "low"), ("gpt-5.6-sol", "medium"),
    ("gpt-5.6-terra", "low"), ("gpt-5.6-terra", "medium"),
])
def test_general_route_rejects_below_operator_floor(model, effort):
    result = load().resolve_v1_worker_route(request(model, effort))
    assert result["status"] == "denied"
    assert result["rejections"][0]["stableId"] == "E_LEAD_WORKER_V1_EFFORT_BELOW_MINIMUM"
    assert result["selectedCandidate"] is None
    assert result["executionAuthorized"] is False


@pytest.mark.parametrize("model", ["gpt-6-astra", "gpt-5.6-sol", "gpt-5.6-terra"])
@pytest.mark.parametrize("effort", ["invented", "none"])
def test_known_profile_does_not_accept_arbitrary_effort_tokens(model, effort):
    result = load().resolve_v1_worker_route(request(model, effort))
    assert result["status"] == "denied"
    assert result["rejections"][0]["stableId"] == "E_LEAD_WORKER_V1_EFFORT_UNSUPPORTED"


@pytest.mark.parametrize("runtime", ["codex-cli", "codex-native"])
@pytest.mark.parametrize("effort", ["medium", "high", "xhigh", "max"])
def test_luna_must_use_its_separate_mechanical_contract(runtime, effort):
    result = load().resolve_v1_worker_route(request("gpt-5.6-luna", effort, runtime=runtime))
    assert result["status"] == "denied"
    assert result["rejections"][0]["stableId"] == "E_LEAD_WORKER_V1_MECHANICAL_ROUTE_REQUIRED"


@pytest.mark.parametrize("model,effort", [
    ("gpt-6-astra", "medium"), ("gpt-6-astra", "high"),
    ("gpt-6-astra", "xhigh"), ("gpt-6-astra", "max"),
    ("gpt-5.6-sol", "high"), ("gpt-5.6-sol", "xhigh"), ("gpt-5.6-sol", "max"),
    ("gpt-5.6-terra", "high"), ("gpt-5.6-terra", "xhigh"), ("gpt-5.6-terra", "max"),
])
def test_compatible_pair_selection_preserves_evidence_and_requires_admission(model, effort):
    values = request(model, effort)
    original = copy.deepcopy(values)
    result = load().resolve_v1_worker_route(values)
    assert result["status"] == "selected"
    assert result["selectedCandidate"] == original["candidates"][0]
    assert result["requiresAdapterAdmission"] is True
    assert result["executionAuthorized"] is False
    assert result["authorizing"] is False
    assert len(result["requestFingerprint"]) == 64
    assert values == original


def test_provider_without_effort_control_is_not_assigned_a_fictional_high():
    result = load().resolve_v1_worker_route(request("kimi-code/k3", "unsupported", provider="kimi"))
    assert result["status"] == "selected"
    assert result["selectedCandidate"]["effort"] == "unsupported"
    assert result["executionAuthorized"] is False


def test_cross_model_priority_is_not_overridden_by_effort_rank():
    values = request("gpt-6-astra", "medium")
    sol = request("gpt-5.6-sol", "xhigh")["candidates"][0]
    sol.update(candidateId="sol-2", priority=2)
    values["candidates"].append(sol)
    result = load().resolve_v1_worker_route(values)
    assert result["selectedCandidate"]["model"] == "gpt-6-astra"
    assert result["selectedCandidate"]["effort"] == "medium"


def test_invalid_pair_cannot_win_a_public_cli_selection():
    result = subprocess.run([
        sys.executable, "-S", str(MODULE), "--request-file", "-",
    ], input=json.dumps(request("gpt-5.6-sol", "medium")),
        text=True, capture_output=True, timeout=10, check=False)
    assert result.returncode == 2
    assert json.loads(result.stdout)["selectedCandidate"] is None
    assert result.stderr == ""
