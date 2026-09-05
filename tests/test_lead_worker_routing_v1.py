from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "src.codex" / "skills" / "lead-worker-routing"
MODULE = SKILL_ROOT / "scripts" / "resolve.py"


def _load():
    spec = importlib.util.spec_from_file_location("lead_worker_routing_v1_test", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _candidate(
    candidate_id: str,
    *,
    provider: str,
    family: str,
    priority: int,
    availability: str = "available",
    capability: str = "engineering-challenge",
    max_mutation: str = "read-only",
    tools: tuple[str, ...] = (),
    isolated: bool = True,
    delegation_depth: int = 0,
    authorizing: bool = False,
    model: str | None = None,
    runtime: str | None = None,
    evidence_snapshot_id: str | None = None,
) -> dict[str, object]:
    return {
        "candidateId": candidate_id,
        "provider": provider,
        "runtime": runtime or f"{provider}-cli",
        "providerFamily": family,
        "model": model or f"{provider}-runtime-observed",
        "effort": "high",
        "priority": priority,
        "availability": availability,
        "maxMutationClass": max_mutation,
        "capabilities": [capability],
        "tools": list(tools),
        "isolatedFromLead": isolated,
        "maxDelegationDepth": delegation_depth,
        "authorizing": authorizing,
        "evidenceSnapshotId": evidence_snapshot_id or f"evidence-{candidate_id}",
    }


def _request(
    *candidates: dict[str, object],
    lead_host: str = "codex",
    capability: str = "engineering-challenge",
    mutation: str = "read-only",
    tools: tuple[str, ...] = (),
    excluded_families: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "dispatchId": "dispatch-test-1",
        "policySnapshotId": "policy-test-1",
        "leadHost": lead_host,
        "assignedRole": "engineering-challenger",
        "scopeId": "scope-test-1",
        "capabilitySlot": capability,
        "mutationClass": mutation,
        "requiredTools": list(tools),
        "excludedProviderFamilies": list(excluded_families),
        "artifactContract": "challenge-report-v1",
        "gateContract": "lead-verifies-artifact-v1",
        "candidates": list(candidates),
    }


def test_resolver_module_exists() -> None:
    assert MODULE.is_file()


def test_only_codex_or_claude_can_host_the_lead() -> None:
    module = _load()
    candidate = _candidate(
        "worker", provider="kimi", family="moonshot", priority=1
    )
    result = module.resolve_v1_worker_route(
        _request(candidate, lead_host="grok")
    )
    assert result["status"] == "denied"
    assert result["stableId"] == "E_LEAD_WORKER_V1_LEAD_HOST_UNSUPPORTED"


@pytest.mark.parametrize("lead_host", ["codex", "claude"])
def test_lead_host_is_separate_from_worker_provider_and_model(lead_host: str) -> None:
    module = _load()
    candidate = _candidate(
        "external-worker",
        provider="grok",
        family="xai",
        priority=1,
        model="grok-future-runtime-id",
    )
    result = module.resolve_v1_worker_route(_request(candidate, lead_host=lead_host))
    assert result["status"] == "selected"
    assert result["leadHost"] == lead_host
    assert result["selectedCandidate"]["provider"] == "grok"
    assert result["selectedCandidate"]["model"] == "grok-future-runtime-id"
    assert result["selectedCandidate"]["providerFamily"] == "xai"


def test_route_binds_role_scope_artifact_gate_and_policy_snapshot() -> None:
    module = _load()
    candidate = _candidate(
        "worker", provider="kimi", family="moonshot", priority=1
    )
    result = module.resolve_v1_worker_route(_request(candidate))
    assert result["status"] == "selected"
    assert result["dispatchId"] == "dispatch-test-1"
    assert result["policySnapshotId"] == "policy-test-1"
    assert result["assignedRole"] == "engineering-challenger"
    assert result["scopeId"] == "scope-test-1"
    assert result["artifactContract"] == "challenge-report-v1"
    assert result["gateContract"] == "lead-verifies-artifact-v1"
    assert result["selectedCandidate"]["evidenceSnapshotId"] == "evidence-worker"


def test_exact_request_and_candidate_shapes_fail_closed() -> None:
    module = _load()
    request = _request(_candidate("worker", provider="claude", family="anthropic", priority=1))
    request["unexpected"] = True
    result = module.resolve_v1_worker_route(request)
    assert result["status"] == "denied"
    assert result["stableId"] == "E_LEAD_WORKER_V1_REQUEST_INVALID"

    bad_candidate = _candidate("worker", provider="claude", family="anthropic", priority=1)
    bad_candidate.pop("runtime")
    result = module.resolve_v1_worker_route(_request(bad_candidate))
    assert result["stableId"] == "E_LEAD_WORKER_V1_REQUEST_INVALID"

    missing_contract = _request()
    missing_contract.pop("artifactContract")
    result = module.resolve_v1_worker_route(missing_contract)
    assert result["stableId"] == "E_LEAD_WORKER_V1_REQUEST_INVALID"


def test_provider_family_is_canonical_and_cannot_be_spoofed() -> None:
    module = _load()
    spoofed = _candidate(
        "spoofed", provider="codex", family="xai", priority=1
    )
    result = module.resolve_v1_worker_route(
        _request(spoofed, lead_host="claude")
    )
    assert result["status"] == "denied"
    assert result["rejections"] == [
        {
            "candidateId": "spoofed",
            "stableId": "E_LEAD_WORKER_V1_PROVIDER_FAMILY_MISMATCH",
        }
    ]


def test_provider_runtime_identity_cannot_be_spoofed() -> None:
    module = _load()
    spoofed = _candidate(
        "spoofed-runtime",
        provider="kimi",
        family="moonshot",
        priority=1,
        runtime="codex-cli",
    )
    result = module.resolve_v1_worker_route(_request(spoofed))
    assert result["status"] == "denied"
    assert result["rejections"] == [
        {
            "candidateId": "spoofed-runtime",
            "stableId": "E_LEAD_WORKER_V1_PROVIDER_RUNTIME_MISMATCH",
        }
    ]


def test_unhashable_json_values_fail_closed_instead_of_raising() -> None:
    module = _load()
    bad_request = _request()
    bad_request["mutationClass"] = []
    result = module.resolve_v1_worker_route(bad_request)
    assert result["stableId"] == "E_LEAD_WORKER_V1_REQUEST_INVALID"

    bad_request = _request()
    bad_request["excludedProviderFamilies"] = [[]]
    result = module.resolve_v1_worker_route(bad_request)
    assert result["stableId"] == "E_LEAD_WORKER_V1_REQUEST_INVALID"

    for field in ("availability", "maxMutationClass"):
        candidate = _candidate(
            "worker", provider="claude", family="anthropic", priority=1
        )
        candidate[field] = []
        result = module.resolve_v1_worker_route(_request(candidate))
        assert result["stableId"] == "E_LEAD_WORKER_V1_REQUEST_INVALID"


def test_glm_is_not_admitted_in_version_1() -> None:
    module = _load()
    result = module.resolve_v1_worker_route(
        _request(_candidate("glm", provider="glm", family="zai", priority=1))
    )
    assert result["status"] == "denied"
    assert result["stableId"] == "E_LEAD_WORKER_V1_NO_ADMITTED_CANDIDATE"
    assert result["rejections"] == [
        {"candidateId": "glm", "stableId": "E_LEAD_WORKER_V1_PROVIDER_NOT_ADMITTED"}
    ]


def test_unpaid_or_quota_exhausted_candidate_falls_back_explicitly() -> None:
    module = _load()
    codex = _candidate(
        "codex-first",
        provider="codex",
        family="openai",
        priority=1,
        availability="not-entitled",
    )
    kimi = _candidate("kimi-second", provider="kimi", family="moonshot", priority=2)
    result = module.resolve_v1_worker_route(_request(codex, kimi, lead_host="claude"))
    assert result["status"] == "selected"
    assert result["selectedCandidate"]["candidateId"] == "kimi-second"
    assert result["fallbackApplied"] is True
    assert result["fallbackEvents"] == [
        {
            "candidateId": "codex-first",
            "provider": "codex",
            "evidenceSnapshotId": "evidence-codex-first",
            "availability": "not-entitled",
            "stableId": "E_LEAD_WORKER_V1_CANDIDATE_NOT_ENTITLED",
            "failureClass": "availability-fallback",
        }
    ]

    codex["availability"] = "quota-exhausted"
    result = module.resolve_v1_worker_route(_request(codex, kimi, lead_host="claude"))
    assert result["fallbackEvents"][0]["stableId"] == "E_LEAD_WORKER_V1_CANDIDATE_QUOTA_EXHAUSTED"


def test_hard_provider_failure_is_visible_after_fallback() -> None:
    module = _load()
    failed = _candidate(
        "kimi-failed",
        provider="kimi",
        family="moonshot",
        priority=1,
        availability="contract-violation",
    )
    selected = _candidate(
        "grok-selected", provider="grok", family="xai", priority=2
    )
    result = module.resolve_v1_worker_route(_request(failed, selected))
    assert result["status"] == "selected"
    assert result["hardFailureObserved"] is True
    assert result["requiresOperatorAttention"] is True
    assert result["fallbackEvents"][0]["failureClass"] == "provider-hard-failure"


def test_priority_is_caller_supplied_and_ties_are_deterministic() -> None:
    module = _load()
    later_name = _candidate("z-worker", provider="claude", family="anthropic", priority=7)
    earlier_name = _candidate("a-worker", provider="grok", family="xai", priority=7)
    result = module.resolve_v1_worker_route(_request(later_name, earlier_name))
    assert result["selectedCandidate"]["candidateId"] == "a-worker"
    assert result["selectionBasis"] == "explicit-priority-available-admitted"


def test_independent_family_requirement_is_enforced() -> None:
    module = _load()
    same_family = _candidate(
        "same-family", provider="codex", family="openai", priority=1
    )
    independent = _candidate(
        "independent", provider="grok", family="xai", priority=2
    )
    result = module.resolve_v1_worker_route(
        _request(same_family, independent, excluded_families=("openai",))
    )
    assert result["status"] == "selected"
    assert result["selectedCandidate"]["candidateId"] == "independent"
    assert result["rejections"] == [
        {
            "candidateId": "same-family",
            "stableId": "E_LEAD_WORKER_V1_INDEPENDENCE_REQUIRED",
        }
    ]


def test_capability_mutation_tools_and_same_host_isolation_are_enforced() -> None:
    module = _load()
    wrong_capability = _candidate(
        "wrong-capability",
        provider="grok",
        family="xai",
        priority=1,
        capability="visual-validation",
    )
    insufficient_mutation = _candidate(
        "read-only-kimi",
        provider="kimi",
        family="moonshot",
        priority=2,
        max_mutation="read-only",
    )
    missing_tool = _candidate(
        "missing-tool",
        provider="claude",
        family="anthropic",
        priority=3,
        max_mutation="workspace-write",
    )
    same_host = _candidate(
        "recursive-host",
        provider="codex",
        family="openai",
        priority=4,
        max_mutation="workspace-write",
        tools=("terminal",),
        isolated=False,
    )
    valid = _candidate(
        "isolated-host",
        provider="codex",
        family="openai",
        priority=5,
        max_mutation="workspace-write",
        tools=("terminal",),
        isolated=True,
    )
    result = module.resolve_v1_worker_route(
        _request(
            wrong_capability,
            insufficient_mutation,
            missing_tool,
            same_host,
            valid,
            mutation="workspace-write",
            tools=("terminal",),
        )
    )
    assert result["selectedCandidate"]["candidateId"] == "isolated-host"
    assert result["rejections"] == [
        {"candidateId": "wrong-capability", "stableId": "E_LEAD_WORKER_V1_CAPABILITY_MISSING"},
        {"candidateId": "read-only-kimi", "stableId": "E_LEAD_WORKER_V1_MUTATION_NOT_ADMITTED"},
        {"candidateId": "missing-tool", "stableId": "E_LEAD_WORKER_V1_TOOL_MISSING"},
        {"candidateId": "recursive-host", "stableId": "E_LEAD_WORKER_V1_SAME_HOST_NOT_ISOLATED"},
    ]


def test_provider_metadata_cannot_grant_kimi_or_grok_write_authority() -> None:
    module = _load()
    kimi = _candidate(
        "kimi-write-claim",
        provider="kimi",
        family="moonshot",
        priority=1,
        max_mutation="workspace-write",
    )
    grok = _candidate(
        "grok-write-claim",
        provider="grok",
        family="xai",
        priority=2,
        max_mutation="workspace-write",
    )
    result = module.resolve_v1_worker_route(_request(kimi, grok, mutation="bounded-write"))
    assert result["status"] == "denied"
    assert result["rejections"] == [
        {
            "candidateId": "kimi-write-claim",
            "stableId": "E_LEAD_WORKER_V1_PROVIDER_MUTATION_CEILING",
        },
        {
            "candidateId": "grok-write-claim",
            "stableId": "E_LEAD_WORKER_V1_PROVIDER_MUTATION_CEILING",
        },
    ]


def test_worker_cannot_authorize_or_delegate() -> None:
    module = _load()
    authorizing = _candidate(
        "authorizing",
        provider="claude",
        family="anthropic",
        priority=1,
        authorizing=True,
    )
    recursive = _candidate(
        "recursive",
        provider="grok",
        family="xai",
        priority=2,
        delegation_depth=1,
    )
    result = module.resolve_v1_worker_route(_request(authorizing, recursive))
    assert result["status"] == "denied"
    assert result["rejections"] == [
        {"candidateId": "authorizing", "stableId": "E_LEAD_WORKER_V1_WORKER_AUTHORITY_FORBIDDEN"},
        {
            "candidateId": "recursive",
            "stableId": "E_LEAD_WORKER_V1_RECURSIVE_DELEGATION_FORBIDDEN",
        },
    ]


@pytest.mark.parametrize(
    ("availability", "stable_id", "failure_class"),
    [
        ("not-configured", "E_LEAD_WORKER_V1_CANDIDATE_NOT_CONFIGURED", "availability-fallback"),
        ("temporary-transport-failure", "E_LEAD_WORKER_V1_CANDIDATE_TRANSPORT_FAILURE", "availability-fallback"),
        ("unavailable", "E_LEAD_WORKER_V1_CANDIDATE_UNAVAILABLE", "availability-fallback"),
        ("auth-invalid", "E_LEAD_WORKER_V1_CANDIDATE_AUTH_INVALID", "provider-hard-failure"),
        ("contract-violation", "E_LEAD_WORKER_V1_CANDIDATE_CONTRACT_VIOLATION", "provider-hard-failure"),
    ],
)
def test_availability_failures_are_recorded_before_fallback(
    availability: str, stable_id: str, failure_class: str
) -> None:
    module = _load()
    first = _candidate(
        "first",
        provider="claude",
        family="anthropic",
        priority=1,
        availability=availability,
    )
    second = _candidate("second", provider="kimi", family="moonshot", priority=2)
    result = module.resolve_v1_worker_route(_request(first, second))
    assert result["selectedCandidate"]["candidateId"] == "second"
    assert result["fallbackEvents"][0]["stableId"] == stable_id
    assert result["fallbackEvents"][0]["failureClass"] == failure_class


def test_no_selectable_candidate_distinguishes_unavailable_from_policy_denial() -> None:
    module = _load()
    unavailable = _candidate(
        "unavailable",
        provider="claude",
        family="anthropic",
        priority=1,
        availability="quota-exhausted",
    )
    result = module.resolve_v1_worker_route(_request(unavailable))
    assert result["status"] == "unavailable"
    assert result["stableId"] == "E_LEAD_WORKER_V1_NO_AVAILABLE_CANDIDATE"
    assert result["selectedCandidate"] is None

    wrong = _candidate(
        "wrong",
        provider="claude",
        family="anthropic",
        priority=1,
        capability="visual-validation",
    )
    result = module.resolve_v1_worker_route(_request(wrong))
    assert result["status"] == "denied"
    assert result["stableId"] == "E_LEAD_WORKER_V1_NO_ADMITTED_CANDIDATE"


def test_selected_route_is_nonauthorizing_and_requires_lead_verification() -> None:
    module = _load()
    result = module.resolve_v1_worker_route(
        _request(_candidate("worker", provider="claude", family="anthropic", priority=1))
    )
    assert result["authorizing"] is False
    assert result["maxDelegationDepth"] == 0
    assert result["requiresLeadVerification"] is True
    assert result["fallbackPolicy"] == "explicit-candidate-order"


def test_cli_reads_file_or_stdin_and_is_deterministic(tmp_path: Path) -> None:
    request = _request(
        _candidate("worker", provider="claude", family="anthropic", priority=1)
    )
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    command = [sys.executable, "-S", str(MODULE), "--request-file", str(request_path)]
    first = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    second = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    assert first.returncode == 0
    assert first.stdout == second.stdout
    assert first.stderr == ""
    assert json.loads(first.stdout)["selectedCandidate"]["candidateId"] == "worker"

    stdin_run = subprocess.run(
        [sys.executable, "-S", str(MODULE), "--request-file", "-"],
        cwd=ROOT,
        input=json.dumps(request),
        text=True,
        capture_output=True,
        check=False,
    )
    assert stdin_run.returncode == 0
    assert stdin_run.stdout == first.stdout


def test_cli_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    request_path = tmp_path / "duplicate.json"
    request_path.write_text('{"schemaVersion":1,"schemaVersion":1}', encoding="utf-8")
    run = subprocess.run(
        [sys.executable, "-S", str(MODULE), "--request-file", str(request_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 2
    assert json.loads(run.stdout)["stableId"] == "E_LEAD_WORKER_V1_REQUEST_JSON_DUPLICATE_KEY"


def test_cli_rejects_symlink_request_file(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(_request()), encoding="utf-8")
    link = tmp_path / "request-link.json"
    try:
        os.symlink(request_path, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this host")
    run = subprocess.run(
        [sys.executable, "-S", str(MODULE), "--request-file", str(link)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 2
    assert json.loads(run.stdout)["stableId"] == "E_LEAD_WORKER_V1_REQUEST_FILE_UNSAFE"


def test_cli_rejects_oversized_request(tmp_path: Path) -> None:
    request_path = tmp_path / "large.json"
    request_path.write_bytes(b" " * (1024 * 1024 + 1))
    run = subprocess.run(
        [sys.executable, "-S", str(MODULE), "--request-file", str(request_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 2
    assert json.loads(run.stdout)["stableId"] == "E_LEAD_WORKER_V1_REQUEST_TOO_LARGE"


def test_cli_returns_nonzero_for_denied_or_invalid_json(tmp_path: Path) -> None:
    denied_path = tmp_path / "denied.json"
    denied_path.write_text(json.dumps(_request()), encoding="utf-8")
    denied = subprocess.run(
        [sys.executable, "-S", str(MODULE), "--request-file", str(denied_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert denied.returncode == 2
    assert json.loads(denied.stdout)["stableId"] == "E_LEAD_WORKER_V1_NO_ADMITTED_CANDIDATE"

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("{", encoding="utf-8")
    invalid = subprocess.run(
        [sys.executable, "-S", str(MODULE), "--request-file", str(invalid_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert invalid.returncode == 2
    assert json.loads(invalid.stdout)["stableId"] == "E_LEAD_WORKER_V1_REQUEST_JSON_INVALID"
    assert invalid.stderr == ""


def test_skill_metadata_and_docs_preserve_v1_boundaries() -> None:
    body = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    metadata = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
    audit = (
        ROOT / "docs" / "lead-contract-routing-audit-2026-09-04.md"
    ).read_text(encoding="utf-8")
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    assert "name: lead-worker-routing" in body
    assert "Codex or Claude" in body
    assert "GLM" in body and "Version 2" in body
    assert "does not launch" in body
    assert "artifactContract" in body and "gateContract" in body
    assert "Lead Worker Routing" in metadata
    assert "logical Lead" in audit
    assert "not-entitled" in audit
    assert "lead-contract-routing-audit-2026-09-04.md" in docs_index
    assert MODULE.is_file()
