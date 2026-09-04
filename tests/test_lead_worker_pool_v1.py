from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src.codex" / "skills" / "lead-worker-pool" / "scripts" / "resolve.py"


def _load():
    spec = importlib.util.spec_from_file_location("lead_worker_pool_v1_test", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _candidate(
    route_id: str,
    provider: str,
    *,
    family: str,
    status: str = "available",
    admission: str = "read-only",
    capabilities: tuple[str, ...] = ("general-engineering",),
    tools: tuple[str, ...] = (),
    model: str = "runtime-observed",
    effort: str = "runtime-default",
) -> dict[str, object]:
    return {
        "routeId": route_id,
        "provider": provider,
        "runtime": f"{provider}-cli",
        "model": model,
        "effort": effort,
        "providerFamily": family,
        "status": status,
        "admission": admission,
        "capabilities": list(capabilities),
        "tools": list(tools),
    }


def test_codex_and_claude_are_valid_lead_hosts() -> None:
    module = _load()
    for host, worker, family in (
        ("codex", "claude", "anthropic"),
        ("claude", "codex", "openai"),
    ):
        result = module.resolve_v1_worker_route(
            lead_host=host,
            assigned_role="architect",
            capability_slot="general-engineering",
            mutation_class="read-only",
            artifact_contract="architecture-note-v1",
            gate_contract="lead-verification-v1",
            candidates=[_candidate("primary", worker, family=family)],
        )
        assert result["status"] == "selected"
        assert result["leadHost"] == host
        assert result["resolvedProvider"] == worker
        assert result["authorizing"] is False
        assert result["maxDelegationDepth"] == 0


def test_unpaid_or_unconfigured_primary_falls_back_with_trace() -> None:
    module = _load()
    result = module.resolve_v1_worker_route(
        lead_host="claude",
        assigned_role="backend-engineer",
        capability_slot="general-engineering",
        mutation_class="bounded-write",
        artifact_contract="patch-v1",
        gate_contract="tests-and-lead-review-v1",
        candidates=[
            _candidate(
                "codex-sol",
                "codex",
                family="openai",
                status="not-entitled",
                admission="bounded-write",
            ),
            _candidate(
                "kimi-current",
                "kimi",
                family="moonshot",
                admission="bounded-write",
            ),
        ],
    )
    assert result["status"] == "selected"
    assert result["resolvedRouteId"] == "kimi-current"
    assert result["fallback"] == "provider-substitution"
    assert result["fallbackUsed"] is True
    assert result["fallbackTrace"] == [
        {
            "routeId": "codex-sol",
            "provider": "codex",
            "stableId": "E_WORKER_V1_NOT_ENTITLED",
            "operatorActionRequired": False,
        }
    ]


def test_candidate_order_is_policy_input_not_hardcoded_vendor_rank() -> None:
    module = _load()
    first = module.resolve_v1_worker_route(
        lead_host="codex",
        assigned_role="engineering-challenger",
        capability_slot="engineering-challenge",
        mutation_class="read-only",
        artifact_contract="challenge-report-v1",
        gate_contract="lead-verification-v1",
        candidates=[
            _candidate(
                "grok-first",
                "grok",
                family="xai",
                capabilities=("engineering-challenge",),
            ),
            _candidate(
                "kimi-second",
                "kimi",
                family="moonshot",
                capabilities=("engineering-challenge",),
            ),
        ],
    )
    second = module.resolve_v1_worker_route(
        lead_host="codex",
        assigned_role="engineering-challenger",
        capability_slot="engineering-challenge",
        mutation_class="read-only",
        artifact_contract="challenge-report-v1",
        gate_contract="lead-verification-v1",
        candidates=[
            _candidate(
                "kimi-first",
                "kimi",
                family="moonshot",
                capabilities=("engineering-challenge",),
            ),
            _candidate(
                "grok-second",
                "grok",
                family="xai",
                capabilities=("engineering-challenge",),
            ),
        ],
    )
    assert first["resolvedProvider"] == "grok"
    assert second["resolvedProvider"] == "kimi"


def test_self_provider_is_skipped_unless_explicitly_allowed() -> None:
    module = _load()
    candidates = [
        _candidate("codex-self", "codex", family="openai"),
        _candidate("claude-other", "claude", family="anthropic"),
    ]
    default = module.resolve_v1_worker_route(
        lead_host="codex",
        assigned_role="analyst",
        capability_slot="general-engineering",
        mutation_class="read-only",
        artifact_contract="analysis-v1",
        gate_contract="lead-verification-v1",
        candidates=candidates,
    )
    explicit = module.resolve_v1_worker_route(
        lead_host="codex",
        assigned_role="analyst",
        capability_slot="general-engineering",
        mutation_class="read-only",
        artifact_contract="analysis-v1",
        gate_contract="lead-verification-v1",
        candidates=candidates,
        allow_self_provider=True,
    )
    assert default["resolvedProvider"] == "claude"
    assert default["fallbackTrace"][0]["stableId"] == "E_WORKER_V1_SELF_PROVIDER_DISALLOWED"
    assert explicit["resolvedProvider"] == "codex"


def test_independent_review_excludes_author_provider_family() -> None:
    module = _load()
    result = module.resolve_v1_worker_route(
        lead_host="claude",
        assigned_role="architecture-reviewer",
        capability_slot="architecture-review",
        mutation_class="read-only",
        artifact_contract="review-findings-v1",
        gate_contract="independent-review-v1",
        candidates=[
            _candidate(
                "openai-review",
                "codex",
                family="openai",
                capabilities=("architecture-review",),
            ),
            _candidate(
                "moonshot-review",
                "kimi",
                family="moonshot",
                capabilities=("architecture-review",),
            ),
        ],
        require_independent_family=True,
        author_provider_family="openai",
    )
    assert result["resolvedProvider"] == "kimi"
    assert result["fallbackTrace"][0]["stableId"] == "E_WORKER_V1_INDEPENDENCE_REQUIRED"


def test_capability_tools_and_mutation_admission_are_hard_gates() -> None:
    module = _load()
    result = module.resolve_v1_worker_route(
        lead_host="codex",
        assigned_role="platform-engineer",
        capability_slot="long-horizon-code",
        mutation_class="bounded-write",
        artifact_contract="patch-v1",
        gate_contract="tests-and-lead-review-v1",
        required_tools=["terminal", "git"],
        candidates=[
            _candidate(
                "wrong-capability",
                "claude",
                family="anthropic",
                admission="bounded-write",
                capabilities=("visual-validation",),
                tools=("terminal", "git"),
            ),
            _candidate(
                "read-only",
                "kimi",
                family="moonshot",
                admission="read-only",
                capabilities=("long-horizon-code",),
                tools=("terminal", "git"),
            ),
            _candidate(
                "missing-tool",
                "grok",
                family="xai",
                admission="bounded-write",
                capabilities=("long-horizon-code",),
                tools=("terminal",),
            ),
            _candidate(
                "admitted",
                "claude",
                family="anthropic",
                admission="bounded-write",
                capabilities=("long-horizon-code",),
                tools=("terminal", "git"),
            ),
        ],
    )
    assert result["resolvedRouteId"] == "admitted"
    assert [row["stableId"] for row in result["fallbackTrace"]] == [
        "E_WORKER_V1_CAPABILITY_MISSING",
        "E_WORKER_V1_MUTATION_NOT_ADMITTED",
        "E_WORKER_V1_TOOLS_MISSING",
    ]


@pytest.mark.parametrize(
    ("status", "stable_id", "action"),
    (
        ("not-configured", "E_WORKER_V1_NOT_CONFIGURED", False),
        ("not-entitled", "E_WORKER_V1_NOT_ENTITLED", False),
        ("quota-exhausted", "E_WORKER_V1_QUOTA_EXHAUSTED", False),
        ("temporary-failure", "E_WORKER_V1_TEMPORARY_FAILURE", False),
        ("auth-invalid", "E_WORKER_V1_AUTH_INVALID", True),
        ("quarantined", "E_WORKER_V1_QUARANTINED", True),
        ("unavailable", "E_WORKER_V1_UNAVAILABLE", False),
        ("unknown", "E_WORKER_V1_AVAILABILITY_UNKNOWN", True),
    ),
)
def test_unavailable_states_are_explicit_and_never_hidden(
    status: str, stable_id: str, action: bool
) -> None:
    module = _load()
    result = module.resolve_v1_worker_route(
        lead_host="codex",
        assigned_role="analyst",
        capability_slot="general-engineering",
        mutation_class="read-only",
        artifact_contract="analysis-v1",
        gate_contract="lead-verification-v1",
        candidates=[
            _candidate("first", "claude", family="anthropic", status=status),
            _candidate("second", "kimi", family="moonshot"),
        ],
    )
    assert result["resolvedProvider"] == "kimi"
    assert result["fallbackTrace"][0]["stableId"] == stable_id
    assert result["fallbackTrace"][0]["operatorActionRequired"] is action
    assert result["operatorActionRequired"] is action


def test_fallback_can_be_disabled_for_an_explicit_provider_request() -> None:
    module = _load()
    result = module.resolve_v1_worker_route(
        lead_host="claude",
        assigned_role="backend-engineer",
        capability_slot="general-engineering",
        mutation_class="bounded-write",
        artifact_contract="patch-v1",
        gate_contract="tests-and-lead-review-v1",
        candidates=[
            _candidate(
                "codex-only",
                "codex",
                family="openai",
                status="quota-exhausted",
                admission="bounded-write",
            ),
            _candidate(
                "kimi-ready",
                "kimi",
                family="moonshot",
                admission="bounded-write",
            ),
        ],
        requested_provider="codex",
        allow_provider_fallback=False,
    )
    assert result["status"] == "unavailable"
    assert result["stableId"] == "E_WORKER_V1_REQUESTED_PROVIDER_UNAVAILABLE"
    assert result["resolvedProvider"] is None
    assert result["fallback"] == "none"


def test_explicit_provider_can_use_cross_vendor_fallback_when_allowed() -> None:
    module = _load()
    result = module.resolve_v1_worker_route(
        lead_host="claude",
        assigned_role="backend-engineer",
        capability_slot="general-engineering",
        mutation_class="bounded-write",
        artifact_contract="patch-v1",
        gate_contract="tests-and-lead-review-v1",
        candidates=[
            _candidate(
                "kimi-first-in-input",
                "kimi",
                family="moonshot",
                admission="bounded-write",
            ),
            _candidate(
                "codex-requested",
                "codex",
                family="openai",
                status="not-entitled",
                admission="bounded-write",
            ),
        ],
        requested_provider="codex",
        allow_provider_fallback=True,
    )
    assert result["resolvedProvider"] == "kimi"
    assert result["requestedProvider"] == "codex"
    assert result["fallbackUsed"] is True
    assert result["fallbackTrace"][0]["provider"] == "codex"


def test_no_admissible_candidate_returns_complete_nonauthorizing_failure() -> None:
    module = _load()
    result = module.resolve_v1_worker_route(
        lead_host="codex",
        assigned_role="graphics-engineer",
        capability_slot="multimodal-cad",
        mutation_class="bounded-write",
        artifact_contract="patch-v1",
        gate_contract="tests-and-lead-review-v1",
        candidates=[
            _candidate(
                "kimi-read-only",
                "kimi",
                family="moonshot",
                admission="read-only",
                capabilities=("multimodal-cad",),
            ),
            _candidate(
                "grok-down",
                "grok",
                family="xai",
                status="unavailable",
                admission="bounded-write",
                capabilities=("multimodal-cad",),
            ),
        ],
    )
    assert result["status"] == "unavailable"
    assert result["stableId"] == "E_WORKER_V1_NO_ADMISSIBLE_ROUTE"
    assert result["authorizing"] is False
    assert result["requiresLeadVerification"] is True
    assert len(result["fallbackTrace"]) == 2


def test_glm_is_rejected_in_version_one() -> None:
    module = _load()
    result = module.resolve_v1_worker_route(
        lead_host="codex",
        assigned_role="backend-engineer",
        capability_slot="long-horizon-code",
        mutation_class="read-only",
        artifact_contract="analysis-v1",
        gate_contract="lead-verification-v1",
        candidates=[
            _candidate(
                "glm-future",
                "glm",
                family="zai",
                capabilities=("long-horizon-code",),
            )
        ],
    )
    assert result["status"] == "denied"
    assert result["stableId"] == "E_WORKER_V1_PROVIDER_UNSUPPORTED"


def test_request_shape_rejects_duplicate_routes_bool_flags_and_unknown_fields() -> None:
    module = _load()
    duplicate = _candidate("dup", "claude", family="anthropic")
    result = module.resolve_v1_worker_route(
        lead_host="codex",
        assigned_role="analyst",
        capability_slot="general-engineering",
        mutation_class="read-only",
        artifact_contract="analysis-v1",
        gate_contract="lead-verification-v1",
        candidates=[duplicate, dict(duplicate)],
    )
    assert result["stableId"] == "E_WORKER_V1_REQUEST_INVALID"

    bad_flag = module.resolve_v1_worker_route(
        lead_host="codex",
        assigned_role="analyst",
        capability_slot="general-engineering",
        mutation_class="read-only",
        artifact_contract="analysis-v1",
        gate_contract="lead-verification-v1",
        candidates=[_candidate("one", "claude", family="anthropic")],
        allow_self_provider=1,
    )
    assert bad_flag["stableId"] == "E_WORKER_V1_REQUEST_INVALID"

    extra = _candidate("extra", "claude", family="anthropic")
    extra["priority"] = 1
    bad_candidate = module.resolve_v1_worker_route(
        lead_host="codex",
        assigned_role="analyst",
        capability_slot="general-engineering",
        mutation_class="read-only",
        artifact_contract="analysis-v1",
        gate_contract="lead-verification-v1",
        candidates=[extra],
    )
    assert bad_candidate["stableId"] == "E_WORKER_V1_REQUEST_INVALID"


def test_cli_is_deterministic_and_returns_nonzero_when_no_route_exists(
    tmp_path: Path,
) -> None:
    request = {
        "leadHost": "claude",
        "assignedRole": "backend-engineer",
        "capabilitySlot": "general-engineering",
        "mutationClass": "bounded-write",
        "artifactContract": "patch-v1",
        "gateContract": "tests-and-lead-review-v1",
        "candidates": [
            _candidate(
                "codex-unpaid",
                "codex",
                family="openai",
                status="not-entitled",
                admission="bounded-write",
            ),
            _candidate(
                "kimi-ready",
                "kimi",
                family="moonshot",
                admission="bounded-write",
            ),
        ],
    }
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    selected = subprocess.run(
        [sys.executable, "-S", str(MODULE), "--request", str(request_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert selected.returncode == 0
    payload = json.loads(selected.stdout)
    assert payload["resolvedProvider"] == "kimi"
    assert selected.stderr == ""

    request["candidates"][1]["status"] = "unavailable"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    unavailable = subprocess.run(
        [sys.executable, "-S", str(MODULE), "--request", str(request_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert unavailable.returncode == 2
    assert json.loads(unavailable.stdout)["stableId"] == "E_WORKER_V1_NO_ADMISSIBLE_ROUTE"


def test_missing_requested_provider_is_recorded_before_allowed_fallback() -> None:
    module = _load()
    result = module.resolve_v1_worker_route(
        lead_host="claude",
        assigned_role="backend-engineer",
        capability_slot="general-engineering",
        mutation_class="bounded-write",
        artifact_contract="patch-v1",
        gate_contract="tests-and-lead-review-v1",
        candidates=[
            _candidate(
                "kimi-ready",
                "kimi",
                family="moonshot",
                admission="bounded-write",
            )
        ],
        requested_provider="codex",
        allow_provider_fallback=True,
    )
    assert result["status"] == "selected"
    assert result["resolvedProvider"] == "kimi"
    assert result["fallbackUsed"] is True
    assert result["fallbackTrace"][0] == {
        "routeId": "requested:codex",
        "provider": "codex",
        "stableId": "E_WORKER_V1_REQUESTED_PROVIDER_MISSING",
        "operatorActionRequired": False,
    }


def test_missing_requested_provider_without_fallback_fails_with_specific_id() -> None:
    module = _load()
    result = module.resolve_v1_worker_route(
        lead_host="claude",
        assigned_role="backend-engineer",
        capability_slot="general-engineering",
        mutation_class="bounded-write",
        artifact_contract="patch-v1",
        gate_contract="tests-and-lead-review-v1",
        candidates=[
            _candidate(
                "kimi-ready",
                "kimi",
                family="moonshot",
                admission="bounded-write",
            )
        ],
        requested_provider="codex",
        allow_provider_fallback=False,
    )
    assert result["status"] == "unavailable"
    assert result["stableId"] == "E_WORKER_V1_REQUESTED_PROVIDER_MISSING"
    assert result["fallback"] == "none"
    assert result["fallbackTrace"][0]["stableId"] == "E_WORKER_V1_REQUESTED_PROVIDER_MISSING"


def test_skill_contract_is_provider_neutral_and_keeps_glm_out_of_v1() -> None:
    skill_root = ROOT / "src.codex" / "skills" / "lead-worker-pool"
    body = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    metadata = (skill_root / "agents" / "openai.yaml").read_text(encoding="utf-8")
    assert "name: lead-worker-pool" in body
    assert "Codex or Claude" in body
    assert "GLM is Version 2 only" in body
    assert "candidate order is supplied" in body.lower()
    assert "Lead Worker Pool" in metadata
    assert "gpt-5." not in body.lower()
    assert "gpt-6" not in body.lower()
    assert "grok 4" not in body.lower()
    assert "glm-5" not in body.lower()
