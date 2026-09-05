from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src.codex" / "skills" / "lead-worker-routing" / "scripts" / "resolve.py"


def _load():
    spec = importlib.util.spec_from_file_location("lead_worker_routing_v1_deep_review", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _candidate(
    *,
    provider: str = "claude",
    runtime: str | None = None,
    family: str | None = None,
) -> dict[str, object]:
    families = {
        "codex": "openai",
        "claude": "anthropic",
        "kimi": "moonshot",
        "grok": "xai",
    }
    return {
        "candidateId": "candidate-current",
        "provider": provider,
        "runtime": runtime or f"{provider}-cli",
        "providerFamily": family or families[provider],
        "model": "runtime-observed-model",
        "effort": "high",
        "priority": 1,
        "availability": "available",
        "maxMutationClass": "read-only",
        "capabilities": ["engineering-challenge"],
        "tools": [],
        "isolatedFromLead": True,
        "maxDelegationDepth": 0,
        "authorizing": False,
        "evidenceSnapshotId": "evidence-current",
    }


def _request(
    candidate: dict[str, object] | None = None,
    *,
    lead_host: str = "codex",
) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "dispatchId": "dispatch-current",
        "policySnapshotId": "policy-current",
        "leadHost": lead_host,
        "assignedRole": "architecture-reviewer",
        "scopeId": "scope-current",
        "capabilitySlot": "engineering-challenge",
        "mutationClass": "read-only",
        "requiredTools": [],
        "excludedProviderFamilies": [],
        "artifactContract": "challenge-report-v1",
        "gateContract": "lead-verifies-v1",
        "candidates": [] if candidate is None else [candidate],
    }


def test_selected_decision_binds_request_fingerprint_but_not_execution_authority() -> None:
    module = _load()
    result = module.resolve_v1_worker_route(_request(_candidate()))
    assert result["status"] == "selected"
    assert result["requestFingerprintAlgorithm"] == "sha256-canonical-json-v1"
    assert len(result["requestFingerprint"]) == 64
    assert result["requiresAdapterAdmission"] is True
    assert result["executionAuthorized"] is False


def test_request_fingerprint_is_key_order_independent_and_contract_sensitive() -> None:
    module = _load()
    request = _request(_candidate())
    reordered = dict(reversed(list(request.items())))
    assert (
        module.resolve_v1_worker_route(request)["requestFingerprint"]
        == module.resolve_v1_worker_route(reordered)["requestFingerprint"]
    )
    changed = json.loads(json.dumps(request))
    changed["artifactContract"] = "different-contract"
    assert (
        module.resolve_v1_worker_route(request)["requestFingerprint"]
        != module.resolve_v1_worker_route(changed)["requestFingerprint"]
    )


def test_invalid_request_has_no_fingerprint_or_adapter_admission_claim() -> None:
    module = _load()
    result = module.resolve_v1_worker_route({})
    assert result["status"] == "denied"
    assert result["requestFingerprint"] is None
    assert result["requiresAdapterAdmission"] is False
    assert result["executionAuthorized"] is False


def test_foreign_native_runtime_is_not_a_cross_host_worker() -> None:
    module = _load()
    result = module.resolve_v1_worker_route(
        _request(
            _candidate(provider="claude", runtime="claude-native"),
            lead_host="codex",
        )
    )
    assert result["status"] == "denied"
    assert result["rejections"] == [
        {
            "candidateId": "candidate-current",
            "stableId": "E_LEAD_WORKER_V1_NATIVE_RUNTIME_HOST_MISMATCH",
        }
    ]


def test_nonstandard_json_constants_and_excessive_shape_fail_closed() -> None:
    module = _load()
    with pytest.raises(module.InvalidJsonStructureError):
        module._parse_json('{"x":NaN}')
    deeply_nested = (
        "[" * (module.MAX_JSON_DEPTH + 1)
        + "0"
        + "]" * (module.MAX_JSON_DEPTH + 1)
    )
    with pytest.raises(module.InvalidJsonStructureError):
        module._parse_json(deeply_nested)


def test_cli_turns_parser_recursion_into_typed_json_failure(tmp_path: Path) -> None:
    request_path = tmp_path / "deep.json"
    request_path.write_text("[" * 2000 + "0" + "]" * 2000, encoding="utf-8")
    run = subprocess.run(
        [sys.executable, "-S", str(MODULE), "--request-file", str(request_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 2
    assert json.loads(run.stdout)["stableId"] == "E_LEAD_WORKER_V1_REQUEST_JSON_INVALID"
    assert run.stderr == ""


def test_symlinked_ancestor_is_rejected(tmp_path: Path) -> None:
    if not hasattr(os, "symlink"):
        pytest.skip("symlink unavailable")
    module = _load()
    real_root = tmp_path / "real"
    real_root.mkdir()
    request_path = real_root / "request.json"
    request_path.write_text(json.dumps(_request(_candidate())), encoding="utf-8")
    linked_root = tmp_path / "linked"
    try:
        linked_root.symlink_to(real_root, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(module.UnsafeRequestFileError):
        module._read_file_bytes(linked_root / "request.json")


def test_unrelated_directory_change_does_not_invalidate_safe_ancestor(
    tmp_path: Path,
) -> None:
    module = _load()
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(_request(_candidate())), encoding="utf-8")
    snapshots = module._snapshot_request_path(request_path)
    (tmp_path / "unrelated.txt").write_text("unrelated", encoding="utf-8")
    module._assert_path_snapshot(snapshots, request_path)
