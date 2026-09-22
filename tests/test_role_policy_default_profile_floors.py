from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RESOLVER_PATH = ROOT / "scripts" / "resolve-agents-mode.py"
SKILL_ONLY_BY_TASK = {
    "exploration": {"product-analyst"},
    "planning": {"ux-designer", "consultant"},
    "critical-design": {"performance-engineer", "reliability-engineer", "consultant"},
    "engineering": {
        "frontend-engineer",
        "qt-ui-engineer",
        "model-view-engineer",
        "data-engineer",
        "toolchain-engineer",
        "geometry-engineer",
        "graphics-engineer",
        "visualization-engineer",
    },
    "review": {
        "consultant",
        "performance-reviewer",
        "accessibility-reviewer",
        "ux-reviewer",
        "ui-test-engineer",
    },
}


def _load_resolver():
    spec = importlib.util.spec_from_file_location(
        "role_policy_default_profile_floor_resolver", RESOLVER_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RESOLVER = _load_resolver()


def test_reminder_does_not_claim_the_installed_resolver_is_absent() -> None:
    source = (
        ROOT / "src.codex" / "skills" / "lead" / "scripts" / "agents-mode-reminder.py"
    ).read_text(encoding="utf-8")

    assert "is NOT shipped to install targets" not in source


def test_installed_resolver_and_sibling_scalar_helper_keep_distinct_runtime_ownership() -> None:
    installer = (ROOT / "scripts" / "production_installer.py").read_text(encoding="utf-8")
    reminder = (
        ROOT / "src.codex" / "skills" / "lead" / "scripts" / "agents-mode-reminder.py"
    ).read_text(encoding="utf-8")

    assert '"resolve-agents-mode.py",' in installer
    assert "agents_mode_runtime.py" in reminder
    assert "owns the first-match read" in reminder
    assert "from agents_mode_runtime import resolve_scalar" in reminder


def test_role_migration_and_luna_docs_have_no_stale_create_only_contract() -> None:
    codex_readme = (ROOT / "src.codex" / "README.md").read_text(encoding="utf-8")
    root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    install = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
    migration_test = (ROOT / "tests" / "test_native_role_slice_a.py").read_text(
        encoding="utf-8"
    )

    for source in (codex_readme, root_readme, install):
        assert "prior working or currently-disabled stock" in source
        assert "customized payloads fail closed" in source
        assert "native-required" in source
        assert "E_NATIVE_V2_DISABLED" in source
        assert "E_LUNA_UNAVAILABLE" in source
        assert "E_LUNA_EXECUTION_CONTAINMENT_UNAVAILABLE" not in source
        assert "E_LUNA_WRITE_CONTAINMENT_UNAVAILABLE" not in source
    assert "bounded-write `mechanical-worker`" not in codex_readme
    assert "only three hash-pinned old roles migrate" not in migration_test


def test_mechanical_defaults_meet_floors_and_ordinary_defaults_are_admissible() -> None:
    """Mechanical keeps ordinal floors; ordinary dispatch uses exact membership."""

    policy, _ = RESOLVER.load_role_policy(ROOT)
    role_catalog = {**policy["roles"], **policy["skillOnlyRoles"]}
    model_index = {value: index for index, value in enumerate(policy["modelTierOrder"])}
    effort_index = {value: index for index, value in enumerate(policy["effortOrder"])}

    for task_name, role_names in policy["taskRoleEligibility"].items():
        task = policy["taskClasses"][task_name]
        for role_name in role_names:
            profile_name = role_catalog[role_name]["defaultProfile"]
            if task_name in {"micro", "mechanical-read", "mechanical"}:
                profile = policy["profiles"][profile_name]
                assert model_index[profile["modelTier"]] >= model_index[task["requiredModelTier"]]
                assert effort_index[profile["effort"]] >= effort_index[task["requiredEffort"]]
            else:
                assert profile_name in task["admissibleProfiles"]


def test_loader_rejects_ordinary_default_outside_exact_task_membership(
    tmp_path: Path,
) -> None:
    """A role-allowed profile cannot authorize a task that omits it."""

    policy_path = tmp_path / "shared" / "role-routing-policy.v1.json"
    policy_path.parent.mkdir()
    policy = json.loads(
        (ROOT / "shared" / "role-routing-policy.v1.json").read_text(encoding="utf-8")
    )
    policy["roles"]["worker"]["defaultProfile"] = "astra-low"
    policy["roles"]["worker"]["allowedProfiles"] = [
        "astra-low",
        "astra-high",
    ]
    policy_path.write_text(json.dumps(policy), encoding="utf-8")

    with pytest.raises(ValueError, match="task recovery role worker default"):
        RESOLVER.load_role_policy(tmp_path)


def _unknown_astra_host() -> dict[str, object]:
    return {
        "explicitModelControl": True,
        "explicitReasoningEffortControl": True,
    }


def _scientific_scope() -> dict[str, object]:
    return {
        "authority": "parent-dispatcher-only",
        "allowedTools": ["functions.exec"],
        "changeSurface": ["approved numerical implementation"],
    }


def test_scientific_role_discovery_exposes_named_default_and_astra_range() -> None:
    description = RESOLVER.describe_ordinary_native_role_options(
        "scientific-software-engineer",
        "engineering",
        _unknown_astra_host(),
        repo_root=ROOT,
    )

    assert description["status"] == "available"
    assert description["defaultProfile"] == "astra-medium"
    assert description["defaultInvocation"] == {
        "mode": "named-role-default",
        "agentType": "scientific-software-engineer",
    }
    assert description["explicitInvocation"] == {
        "mode": "generic-explicit-profile",
        "omitAgentType": True,
        "forkTurns": "none",
    }
    discovered = {
        (option["model"], option["effort"], option["hostCapability"])
        for option in description["options"]
    }
    assert {
        ("gpt-6-astra", effort, "capability-unknown")
        for effort in ("low", "medium", "high", "xhigh", "max")
    } <= discovered
    assert {
        ("gpt-5.6-terra", "high", "capability-unknown"),
        ("gpt-6-sol", "high", "capability-unknown"),
        ("gpt-6-sol", "xhigh", "capability-unknown"),
        ("gpt-6-sol", "max", "capability-unknown"),
    } <= discovered
    assert all(option["useCriteria"] for option in description["options"])
    assert description["profession"]["skill"] == "$scientific-software-engineer"
    assert len(description["profession"]["skillSha256"]) == 64
    assert "$scientific-software-engineer" in description["profession"]["instructions"]


def test_ordinary_resolver_keeps_named_default_but_explicit_tuple_uses_generic_spawn() -> None:
    description = RESOLVER.describe_ordinary_native_role_options(
        "scientific-software-engineer",
        "engineering",
        _unknown_astra_host(),
        repo_root=ROOT,
    )
    scope = _scientific_scope()

    default = RESOLVER.resolve_ordinary_native_dispatch(
        description,
        caller_rationale="Use the accepted role default.",
        approved_execution_scope=scope,
    )
    explicit = RESOLVER.resolve_ordinary_native_dispatch(
        description,
        requested_model="gpt-6-astra",
        requested_effort="low",
        caller_rationale="The contract is bounded, clear, and directly testable.",
        approved_execution_scope=scope,
    )

    assert default["invocation"] == {
        "mode": "named-role-default",
        "agentType": "scientific-software-engineer",
    }
    assert default["requestedModel"] is None
    assert default["resolvedEffort"] == "medium"
    assert explicit["invocation"]["model"] == "gpt-6-astra"
    assert explicit["invocation"]["reasoningEffort"] == "low"
    assert explicit["invocation"]["forkTurns"] == "none"
    assert "agentType" not in explicit["invocation"]
    assert explicit["approvedExecutionScope"] == scope
    assert explicit["profession"] == default["profession"]
    assert explicit["failurePolicy"] == {
        "hostRejection": "E_ORDINARY_NATIVE_SELECTION_REJECTED",
        "executionDrift": "E_ORDINARY_NATIVE_EXECUTION_DRIFT",
        "missingActualMetadata": "unspecified by runtime",
    }
    assert explicit["fallback"] == "none"


def test_analyst_exploration_admits_medium_without_changing_named_default() -> None:
    host = {
        "explicitModelControl": True,
        "explicitReasoningEffortControl": True,
        "reportedModels": ["gpt-5.6-terra"],
        "reportedEfforts": ["medium", "high"],
        "reportedAgentTypes": ["analyst"],
    }
    description = RESOLVER.describe_ordinary_native_role_options(
        "analyst",
        "exploration",
        host,
        repo_root=ROOT,
    )
    scope = {
        "authority": "parent-dispatcher-only",
        "allowedTools": ["functions.exec"],
        "changeSurface": [],
    }

    assert description["status"] == "available"
    assert description["mutationClass"] == "read-only"
    assert description["defaultProfile"] == "balanced-high"
    assert description["defaultModel"] == "gpt-5.6-terra"
    assert description["defaultEffort"] == "high"
    assert [
        (option["profile"], option["model"], option["effort"])
        for option in description["options"]
    ] == [
        ("balanced-medium", "gpt-5.6-terra", "medium"),
        ("balanced-high", "gpt-5.6-terra", "high"),
    ]

    default = RESOLVER.resolve_ordinary_native_dispatch(
        description,
        caller_rationale="Use the existing analyst default for this bounded exploration.",
        approved_execution_scope=scope,
    )
    explicit = RESOLVER.resolve_ordinary_native_dispatch(
        description,
        requested_model="gpt-5.6-terra",
        requested_effort="medium",
        caller_rationale="Routine bounded classification favors moderate reasoning.",
        approved_execution_scope=scope,
    )

    assert default["resolvedProfile"] == "balanced-high"
    assert default["resolvedModel"] == "gpt-5.6-terra"
    assert default["resolvedEffort"] == "high"
    assert default["invocation"] == {
        "mode": "named-role-default",
        "agentType": "analyst",
    }
    assert explicit["status"] == "resolved"
    assert explicit["resolvedProfile"] == "balanced-medium"
    assert explicit["resolvedModel"] == "gpt-5.6-terra"
    assert explicit["resolvedEffort"] == "medium"
    assert explicit["invocation"]["mode"] == "generic-explicit-profile"
    assert explicit["invocation"]["forkTurns"] == "none"
    assert "agentType" not in explicit["invocation"]
    assert explicit["failurePolicy"] == default["failurePolicy"]
    assert explicit["fallback"] == "none"


def test_ordinary_discovery_filters_reported_host_capabilities_and_max_needs_approval() -> None:
    description = RESOLVER.describe_ordinary_native_role_options(
        "scientific-software-engineer",
        "engineering",
        {
            "explicitModelControl": True,
            "explicitReasoningEffortControl": True,
            "reportedModels": ["gpt-6-astra"],
            "reportedEfforts": ["low", "max"],
        },
        repo_root=ROOT,
    )
    assert [(option["effort"], option["hostCapability"]) for option in description["options"]] == [
        ("low", "reported"),
        ("max", "reported"),
    ]

    denied = RESOLVER.resolve_ordinary_native_dispatch(
        description,
        requested_model="gpt-6-astra",
        requested_effort="max",
        caller_rationale="Maximum effort was requested.",
        approved_execution_scope=_scientific_scope(),
    )
    admitted = RESOLVER.resolve_ordinary_native_dispatch(
        description,
        requested_model="gpt-6-astra",
        requested_effort="max",
        caller_rationale="The user explicitly approved maximum effort.",
        approved_execution_scope=_scientific_scope(),
        user_approved_max=True,
    )

    assert denied["status"] == "denied"
    assert denied["stableId"] == "E_ORDINARY_NATIVE_SELECTION_INVALID"
    assert admitted["status"] == "resolved"
    assert admitted["resolvedEffort"] == "max"


def test_every_ordinary_eligibility_edge_has_default_and_astra_options() -> None:
    policy, _ = RESOLVER.load_role_policy(ROOT)
    role_catalog = {**policy["roles"], **policy["skillOnlyRoles"]}
    for task_name, role_names in policy["taskRoleEligibility"].items():
        if task_name in {"micro", "mechanical-read", "mechanical"}:
            continue
        task = policy["taskClasses"][task_name]
        for role_name in role_names:
            role = role_catalog[role_name]
            intersection = set(role["allowedProfiles"]) & set(task["admissibleProfiles"])
            assert role["defaultProfile"] in intersection
            assert any(
                policy["profiles"][profile]["codexModel"] == "gpt-6-astra"
                for profile in intersection
            ), (task_name, role_name)


def test_empty_post_filter_options_deny_every_eligible_ordinary_role() -> None:
    policy, _ = RESOLVER.load_role_policy(ROOT)
    host = {
        "explicitModelControl": True,
        "explicitReasoningEffortControl": True,
        "reportedModels": ["host-model-not-present-in-policy"],
        "reportedEfforts": ["medium"],
    }

    for task_name, role_names in policy["taskRoleEligibility"].items():
        if task_name in {"micro", "mechanical-read", "mechanical"}:
            continue
        for role_name in role_names:
            description = RESOLVER.describe_ordinary_native_role_options(
                role_name,
                task_name,
                host,
                repo_root=ROOT,
            )
            assert description == {
                "schemaVersion": 1,
                "status": "denied",
                "stableId": "E_ORDINARY_NATIVE_SELECTION_INVALID",
                "taskClass": task_name,
                "role": role_name,
                "fallback": "none",
            }, (task_name, role_name)


def test_ordinary_native_cli_projects_explicit_host_controls_without_launching() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(RESOLVER_PATH),
            "--provider",
            "codex",
            "--repo-root",
            str(ROOT),
            "--ordinary-native-action",
            "resolve",
            "--task-class",
            "engineering",
            "--role",
            "scientific-software-engineer",
            "--host-controls",
            "explicit",
            "--requested-model",
            "gpt-6-astra",
            "--requested-effort",
            "xhigh",
            "--caller-rationale",
            "Demanding accepted implementation contract.",
            "--approved-scope-json",
            '{"authority":"parent-dispatcher-only","allowedTools":[]}',
            "--json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    decision = json.loads(result.stdout)
    assert decision["status"] == "resolved"
    assert decision["invocation"]["model"] == "gpt-6-astra"
    assert decision["invocation"]["reasoningEffort"] == "xhigh"
    assert "agentType" not in decision["invocation"]


def test_skill_only_catalog_resolves_default_and_explicit_choices_without_agent_type() -> None:
    policy, _ = RESOLVER.load_role_policy(ROOT)
    expected_roles = set().union(*SKILL_ONLY_BY_TASK.values())
    assert set(policy["skillOnlyRoles"]) == expected_roles

    description = RESOLVER.describe_ordinary_native_role_options(
        "frontend-engineer",
        "engineering",
        _unknown_astra_host(),
        repo_root=ROOT,
    )
    default = RESOLVER.resolve_ordinary_native_dispatch(
        description,
        caller_rationale="Use the policy default for this bounded UI implementation.",
        approved_execution_scope=_scientific_scope(),
    )
    explicit = RESOLVER.resolve_ordinary_native_dispatch(
        description,
        requested_model="gpt-6-astra",
        requested_effort="low",
        caller_rationale="The accepted UI change is bounded and directly testable.",
        approved_execution_scope=_scientific_scope(),
    )

    assert description["roleKind"] == "skill-only"
    assert description["defaultProfile"] == "balanced-high"
    assert description["profession"]["skill"] == "$frontend-engineer"
    assert len(description["profession"]["skillSha256"]) == 64
    assert default["resolvedModel"] == "gpt-5.6-terra"
    assert default["resolvedEffort"] == "high"
    assert default["invocation"]["model"] == "gpt-5.6-terra"
    assert default["invocation"]["reasoningEffort"] == "high"
    assert default["invocation"]["forkTurns"] == "none"
    assert "agentType" not in default["invocation"]
    assert explicit["resolvedModel"] == "gpt-6-astra"
    assert explicit["resolvedEffort"] == "low"
    assert "agentType" not in explicit["invocation"]
    assert explicit["profession"] == default["profession"]


def test_every_skill_only_role_is_task_eligible_and_uses_current_skill_metadata() -> None:
    policy, _ = RESOLVER.load_role_policy(ROOT)
    manifest = json.loads(
        (ROOT / "src.codex" / "agents" / "orchestrarium-role-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    for task_name, expected_roles in SKILL_ONLY_BY_TASK.items():
        assert expected_roles <= set(policy["taskRoleEligibility"][task_name])
        for role_name in expected_roles:
            description = RESOLVER.describe_ordinary_native_role_options(
                role_name,
                task_name,
                _unknown_astra_host(),
                repo_root=ROOT,
            )
            assert description["status"] == "available"
            assert description["roleKind"] == "skill-only"
            assert description["profession"]["skill"] == f"${role_name}"
            assert len(description["profession"]["skillSha256"]) == 64
            assert description["defaultProfile"] in {
                option["profile"] for option in description["options"]
            }
            assert role_name not in manifest["roles"]
            assert not (ROOT / "src.codex" / "agents" / f"{role_name}.toml").exists()


def test_knowledge_archivist_is_admitted_to_engineering_without_default_change() -> None:
    description = RESOLVER.describe_ordinary_native_role_options(
        "knowledge-archivist",
        "engineering",
        {
            **_unknown_astra_host(),
            "reportedAgentTypes": ["knowledge-archivist"],
        },
        repo_root=ROOT,
    )
    decision = RESOLVER.resolve_ordinary_native_dispatch(
        description,
        caller_rationale="Use the existing archivist default for bounded lifecycle mutation.",
        approved_execution_scope=_scientific_scope(),
    )

    assert description["defaultProfile"] == "balanced-medium"
    assert description["defaultAgentTypeCapability"] == "reported"
    assert decision["status"] == "resolved"
    assert decision["resolvedModel"] == "gpt-5.6-terra"
    assert decision["resolvedEffort"] == "medium"
    assert decision["invocation"]["agentType"] == "knowledge-archivist"


def test_native_named_default_denies_only_when_reported_agent_types_exclude_it() -> None:
    unknown = RESOLVER.describe_ordinary_native_role_options(
        "scientific-software-engineer",
        "engineering",
        _unknown_astra_host(),
        repo_root=ROOT,
    )
    reported = RESOLVER.describe_ordinary_native_role_options(
        "scientific-software-engineer",
        "engineering",
        {**_unknown_astra_host(), "reportedAgentTypes": ["scientific-software-engineer"]},
        repo_root=ROOT,
    )
    absent = RESOLVER.describe_ordinary_native_role_options(
        "scientific-software-engineer",
        "engineering",
        {**_unknown_astra_host(), "reportedAgentTypes": ["worker"]},
        repo_root=ROOT,
    )

    unknown_result = RESOLVER.resolve_ordinary_native_dispatch(
        unknown,
        caller_rationale="The host did not enumerate agent types.",
        approved_execution_scope=_scientific_scope(),
    )
    reported_result = RESOLVER.resolve_ordinary_native_dispatch(
        reported,
        caller_rationale="The host reported this named role.",
        approved_execution_scope=_scientific_scope(),
    )
    absent_result = RESOLVER.resolve_ordinary_native_dispatch(
        absent,
        caller_rationale="The host enumerated a list without this role.",
        approved_execution_scope=_scientific_scope(),
    )

    assert unknown["defaultAgentTypeCapability"] == "capability-unknown"
    assert reported["defaultAgentTypeCapability"] == "reported"
    assert absent["defaultAgentTypeCapability"] == "reported-absent"
    assert unknown_result["status"] == "resolved"
    assert unknown_result["hostCapability"] == "capability-unknown"
    assert reported_result["hostCapability"] == "reported"
    assert absent_result["status"] == "denied"
    assert absent_result["stableId"] == "E_ORDINARY_NATIVE_AGENT_TYPE_UNAVAILABLE"
    assert absent_result["fallback"] == "none"


def test_ordinary_native_cli_accepts_reported_agent_types() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(RESOLVER_PATH),
            "--provider",
            "codex",
            "--repo-root",
            str(ROOT),
            "--ordinary-native-action",
            "describe",
            "--task-class",
            "engineering",
            "--role",
            "scientific-software-engineer",
            "--host-controls",
            "explicit",
            "--reported-agent-type",
            "scientific-software-engineer",
            "--json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["defaultAgentTypeCapability"] == "reported"


def test_invalid_task_shape_is_typed_denial_for_native_and_skill_only_roles() -> None:
    for role_name in ("scientific-software-engineer", "frontend-engineer"):
        decision = RESOLVER.describe_ordinary_native_role_options(
            role_name,
            [],
            _unknown_astra_host(),
            repo_root=ROOT,
        )
        assert decision["status"] == "denied"
        assert decision["stableId"] == "E_ORDINARY_NATIVE_SELECTION_INVALID"
        assert decision["fallback"] == "none"
