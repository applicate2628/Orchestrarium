from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESOLVER_PATH = ROOT / "scripts" / "resolve-agents-mode.py"


def _load_resolver():
    spec = importlib.util.spec_from_file_location(
        "consultant_profile_ranking_resolver", RESOLVER_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RESOLVER = _load_resolver()
HOST = {
    "explicitModelControl": True,
    "explicitReasoningEffortControl": True,
}
SCOPE = {
    "authority": "parent-dispatcher-only",
    "allowedTools": ["functions.exec"],
    "changeSurface": ["consultant advisory selection"],
}


def _describe(task_class: str) -> dict[str, object]:
    return RESOLVER.describe_ordinary_native_role_options(
        "consultant", task_class, HOST, repo_root=ROOT
    )


def _resolve(description: dict[str, object], **selection: object) -> dict[str, object]:
    return RESOLVER.resolve_ordinary_native_dispatch(
        description,
        caller_rationale="Select a sufficient nonauthorizing Consultant profile.",
        approved_execution_scope=SCOPE,
        **selection,
    )


def test_omitted_consultant_choice_uses_frontier_high_and_reports_model_tier() -> None:
    description = _describe("planning")

    assert description["status"] == "available"
    assert description["roleKind"] == "skill-only"
    assert description["mutationClass"] == "read-only"
    assert description["defaultProfile"] == "frontier-high"
    assert description["defaultModel"] == "gpt-5.6-sol"
    assert description["defaultEffort"] == "high"
    assert description["profession"]["skill"] == "$consultant"
    assert all("modelTier" in option for option in description["options"])

    decision = _resolve(description)

    assert decision["status"] == "resolved"
    assert decision["modelTier"] == "frontier"
    assert decision["resolvedProfile"] == "frontier-high"
    assert decision["resolvedModel"] == "gpt-5.6-sol"
    assert decision["resolvedEffort"] == "high"
    assert decision["invocation"] == {
        "mode": "generic-explicit-profile",
        "forkTurns": "none",
        "model": "gpt-5.6-sol",
        "reasoningEffort": "high",
        "professionSkill": "$consultant",
        "promptPreamble": description["profession"]["instructions"],
    }
    assert decision["fallback"] == "none"


def test_explicit_consultant_choice_wins_but_partial_and_unapproved_max_deny() -> None:
    description = _describe("review")

    balanced = _resolve(
        description,
        requested_model="gpt-5.6-terra",
        requested_effort="high",
    )
    xhigh = _resolve(
        description,
        requested_model="gpt-5.6-sol",
        requested_effort="xhigh",
    )
    partial = _resolve(description, requested_model="gpt-5.6-terra")
    unapproved_max = _resolve(
        description,
        requested_model="gpt-5.6-sol",
        requested_effort="max",
    )
    approved_max = _resolve(
        description,
        requested_model="gpt-5.6-sol",
        requested_effort="max",
        user_approved_max=True,
    )

    assert (balanced["resolvedProfile"], balanced["modelTier"]) == (
        "balanced-high",
        "balanced",
    )
    assert (xhigh["resolvedProfile"], xhigh["modelTier"]) == (
        "frontier-xhigh",
        "frontier",
    )
    assert partial["stableId"] == "E_ORDINARY_NATIVE_SELECTION_INVALID"
    assert unapproved_max["stableId"] == "E_ORDINARY_NATIVE_SELECTION_INVALID"
    assert (approved_max["resolvedProfile"], approved_max["modelTier"]) == (
        "apex-max",
        "apex",
    )


def test_consultant_task_intersections_are_policy_owned() -> None:
    expected = {
        "planning": [
            "balanced-high",
            "frontier-high",
            "frontier-xhigh",
            "apex-max",
            "astra-medium",
            "astra-high",
            "astra-xhigh",
            "astra-max",
        ],
        "review": [
            "balanced-high",
            "frontier-high",
            "frontier-xhigh",
            "apex-max",
            "astra-medium",
            "astra-high",
            "astra-xhigh",
            "astra-max",
        ],
        "critical-design": [
            "frontier-high",
            "frontier-xhigh",
            "apex-max",
            "astra-high",
            "astra-xhigh",
            "astra-max",
        ],
    }

    for task_class, expected_profiles in expected.items():
        description = _describe(task_class)
        assert [option["profile"] for option in description["options"]] == expected_profiles

    denied = _describe("exploration")
    assert denied["status"] == "denied"
    assert denied["fallback"] == "none"
