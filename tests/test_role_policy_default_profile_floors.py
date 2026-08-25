from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RESOLVER_PATH = ROOT / "scripts" / "resolve-agents-mode.py"


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


def test_installed_resolver_is_a_runtime_helper_while_reminder_stays_self_contained() -> None:
    installer = (ROOT / "scripts" / "production_installer.py").read_text(encoding="utf-8")
    reminder = (
        ROOT / "src.codex" / "skills" / "lead" / "scripts" / "agents-mode-reminder.py"
    ).read_text(encoding="utf-8")

    assert '"resolve-agents-mode.py",' in installer
    assert "SELF-CONTAINED first-match read" in reminder
    assert "does not import" in reminder


def test_role_migration_and_luna_docs_have_no_stale_create_only_contract() -> None:
    codex_readme = (ROOT / "src.codex" / "README.md").read_text(encoding="utf-8")
    root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    install = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
    migration_test = (ROOT / "tests" / "test_native_role_slice_a.py").read_text(
        encoding="utf-8"
    )

    for source in (codex_readme, root_readme, install):
        assert "five hash-pinned stock role payload upgrades" in source
        assert "customized payloads fail closed" in source
        assert "E_LUNA_EXECUTION_CONTAINMENT_UNAVAILABLE" in source
        assert "E_LUNA_WRITE_CONTAINMENT_UNAVAILABLE" in source
    assert "LunaExecutionContractV1" in codex_readme
    assert "ScoutFactsV1" in codex_readme
    assert "bounded-write `mechanical-worker`" not in codex_readme
    assert "only three hash-pinned old roles migrate" not in migration_test


def test_every_eligible_role_default_profile_meets_its_task_floor() -> None:
    """Native execution selects defaultProfile, so every eligibility edge must fit it."""

    policy, _ = RESOLVER.load_role_policy(ROOT)
    model_index = {value: index for index, value in enumerate(policy["modelTierOrder"])}
    effort_index = {value: index for index, value in enumerate(policy["effortOrder"])}

    for task_name, role_names in policy["taskRoleEligibility"].items():
        task = policy["taskClasses"][task_name]
        for role_name in role_names:
            profile_name = policy["roles"][role_name]["defaultProfile"]
            profile = policy["profiles"][profile_name]
            assert model_index[profile["modelTier"]] >= model_index[task["requiredModelTier"]]
            assert effort_index[profile["effort"]] >= effort_index[task["requiredEffort"]]


def test_loader_rejects_policy_when_only_nondefault_allowed_profile_meets_floor(
    tmp_path: Path,
) -> None:
    """A qualified fallback in allowedProfiles cannot authorize native default execution."""

    policy_path = tmp_path / "shared" / "role-routing-policy.v1.json"
    policy_path.parent.mkdir()
    policy = json.loads(
        (ROOT / "shared" / "role-routing-policy.v1.json").read_text(encoding="utf-8")
    )
    policy["roles"]["worker"]["defaultProfile"] = "balanced-high"
    policy["roles"]["worker"]["allowedProfiles"] = [
        "balanced-high",
        "frontier-high",
    ]
    policy_path.write_text(json.dumps(policy), encoding="utf-8")

    with pytest.raises(ValueError, match="task recovery role worker default"):
        RESOLVER.load_role_policy(tmp_path)
