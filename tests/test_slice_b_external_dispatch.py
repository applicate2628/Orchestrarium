from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RESOLVER_PATH = ROOT / "scripts" / "resolve-agents-mode.py"


def _load_resolver():
    spec = importlib.util.spec_from_file_location(
        "slice_b_external_dispatch_resolver", RESOLVER_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RESOLVER = _load_resolver()


def _canonical_sha(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def test_legacy_resolution_unchanged_and_auto_excludes_new_providers() -> None:
    schema_path = ROOT / "shared" / "agents-mode.schema.json"
    defaults_path = ROOT / "shared" / "agents-mode.defaults.yaml"
    presets_path = ROOT / "shared" / "agents-mode.presets.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    scalar = {record["name"]: record for record in schema["scalarKeys"]}

    assert schema["productionAutoProviders"] == ["codex", "claude"]
    assert schema["exampleOnlyProviders"] == ["gemini", "qwen"]
    assert schema["explicitOnlyProviders"] == ["kimi", "grok"]
    assert scalar["externalProvider"]["allowed"] == [
        "auto",
        "codex",
        "claude",
        "gemini",
        "qwen",
        "kimi",
        "grok",
    ]
    assert _canonical_sha(schema["priorityProfiles"]) == (
        "435c3646a5ff9c36bc5b4483d1a04ae7fb8f8ffde51dc5795e2c2918d22f7956"
    )
    assert hashlib.sha256(presets_path.read_bytes()).hexdigest() == (
        "221a9b4fef1cdc0bef6109dc0f4305a0344fb6b0553057ce80c628df65122077"
    )
    array_lines = "\n".join(
        line
        for line in defaults_path.read_text(encoding="utf-8").splitlines()
        if ": [" in line
    ).encode()
    assert hashlib.sha256(array_lines).hexdigest() == (
        "b44947bc07123e967c5a165a255dd23308ddd025c183ecb88cb0ec5c1f21d735"
    )
    assert "kimi" not in json.dumps(schema["priorityProfiles"])
    assert "grok" not in json.dumps(schema["priorityProfiles"])
    assert set(RESOLVER.PROVIDER_DIRS) == {"codex", "claude", "gemini", "qwen"}


@pytest.mark.parametrize("provider", ("kimi", "grok"))
@pytest.mark.parametrize(
    ("task_class", "role"),
    (
        ("exploration", "analyst"),
        ("planning", "planner"),
        ("review", "qa-engineer"),
    ),
)
def test_external_dispatch_admits_only_explicit_read_only_policy_lanes(
    provider: str, task_class: str, role: str
) -> None:
    decision = RESOLVER.resolve_external_dispatch(
        provider, task_class, role, repo_root=ROOT
    )
    expected_native_effort = "unsupported" if provider == "kimi" else "high"
    expected_loss = (
        "no-native-effort-control"
        if provider == "kimi"
        else "none"
    )

    assert decision == {
        "schemaVersion": 1,
        "status": "external-required",
        "stableId": None,
        "provider": provider,
        "taskClass": task_class,
        "role": role,
        "requiredModelTier": "balanced",
        "requiredEffort": "high",
        "mutationClass": "read-only",
        "nativeEffort": expected_native_effort,
        "effortMappingLoss": expected_loss,
        "finalAuthorizingRole": False,
        "independentVerification": True,
        "fallback": "none",
    }


@pytest.mark.parametrize("provider", ("kimi", "grok"))
@pytest.mark.parametrize(
    ("task_class", "role"),
    (
        ("micro", "mechanical-scout"),
        ("mechanical-read", "mechanical-scout"),
        ("mechanical", "mechanical-worker"),
        ("engineering", "worker"),
        ("critical-design", "architect"),
        ("critical-security", "security-reviewer"),
        ("recovery", "worker"),
        ("review", "worker"),
        ("unknown", "analyst"),
    ),
)
def test_external_dispatch_denies_every_unadmitted_task_or_role(
    provider: str, task_class: str, role: str
) -> None:
    decision = RESOLVER.resolve_external_dispatch(
        provider, task_class, role, repo_root=ROOT
    )
    assert decision["status"] == "denied"
    assert decision["stableId"] == f"E_{provider.upper()}_DISPATCH_DENIED"
    assert decision["fallback"] == "none"


def test_external_dispatch_denies_unsupported_provider_and_native_is_unchanged() -> None:
    denied = RESOLVER.resolve_external_dispatch(
        "codex", "exploration", "analyst", repo_root=ROOT
    )
    assert denied["status"] == "denied"
    assert denied["stableId"] == "E_EXTERNAL_DISPATCH_DENIED"

    assert RESOLVER.resolve_role_dispatch(
        "mechanical-read", "mechanical-scout", "enabled", repo_root=ROOT
    ) == {
        "schemaVersion": 1,
        "status": "unavailable",
        "stableId": "E_LUNA_EXECUTION_CONTAINMENT_UNAVAILABLE",
        "taskClass": "mechanical-read",
        "role": "mechanical-scout",
        "requestedProfile": "fast-high",
        "requestedModel": "gpt-5.6-luna",
        "requestedEffort": "high",
        "sandbox": "read-only",
        "fallback": "none",
        "executionContract": json.loads(
            (ROOT / "shared" / "role-routing-policy.v1.json").read_text(encoding="utf-8")
        )["mechanicalExecutionContract"],
    }


@pytest.mark.parametrize("provider", ("kimi", "grok"))
@pytest.mark.parametrize("role", ("architecture-reviewer", "security-reviewer"))
def test_external_dispatch_rejects_policy_declared_final_authorizers(
    provider: str, role: str
) -> None:
    decision = RESOLVER.resolve_external_dispatch(
        provider, "review", role, repo_root=ROOT
    )

    assert decision["status"] == "denied"
    assert decision["stableId"] == f"E_{provider.upper()}_FINAL_OWNER_DENIED"
    assert decision["finalAuthorizingRole"] is True
    assert decision["fallback"] == "none"
