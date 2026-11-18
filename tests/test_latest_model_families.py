"""Latest confirmed family policy, offline only; historical records stay readable."""
import hashlib
import json
from pathlib import Path
import unittest
from scripts.model_routing.launch_policy import CURRENT_CODEX_FAMILY_MODELS, qualify_launch
from scripts import production_installer as installer

ROOT = Path(__file__).resolve().parents[1]

class LatestFamiliesTests(unittest.TestCase):
    def test_current_policy_has_only_latest_confirmed_families(self):
        policy = json.loads((ROOT / "shared/role-routing-policy.v1.json").read_bytes())
        self.assertEqual({p["codexModel"] for p in policy["profiles"].values()}, CURRENT_CODEX_FAMILY_MODELS)
        for group in ("roles", "skillOnlyRoles"):
            for role in policy[group].values():
                self.assertIn(role["defaultProfile"], role["allowedProfiles"])
                self.assertTrue(set(role["allowedProfiles"]) <= set(policy["profiles"]))
        for task, roles in policy["taskRoleEligibility"].items():
            admitted = policy["taskClasses"][task].get("admissibleProfiles")
            for name in roles:
                role = {**policy["roles"], **policy["skillOnlyRoles"]}[name]
                default = role.get("taskDefaultProfiles", {}).get(task, role["defaultProfile"])
                if admitted is not None:
                    self.assertIn(default, admitted)
                    self.assertTrue(set(admitted) & set(role["allowedProfiles"]))

    def test_old_or_unconfirmed_generation_cannot_be_approved_back_in(self):
        retired = ("gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "GPT-5.6-sol", "gpt-5.4", "gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol",
                   "gpt-6-sol", "gpt-6.1-sol", "gpt-6-astra", "gpt-6.1-astra", "gpt-6.2-terra")
        for model in retired:
            for effort in ("medium", "high", "xhigh", "max"):
                with self.subTest(model=model, effort=effort):
                    self.assertEqual(qualify_launch("codex", model, effort,
                        user_approved_launch=True, user_approved_max=True), "model-generation-not-admitted")

    def test_latest_models_and_other_providers_keep_boundaries(self):
        for model in CURRENT_CODEX_FAMILY_MODELS:
            self.assertIsNone(qualify_launch("codex", model, "high", user_approved_launch=True))
            self.assertIsNotNone(qualify_launch("codex", model, "low", user_approved_launch=True))
            self.assertEqual(qualify_launch("codex", model, "max"), "individual-launch-approval-required")
        self.assertIsNone(qualify_launch("kimi", "gpt-5.6-sol", "high"))
        self.assertIsNone(qualify_launch("codex", "custom-model", "high"))

    def test_external_schema_offers_only_current_explicit_models(self):
        schema = json.loads((ROOT / "shared/agents-mode.schema.json").read_bytes())
        # Resolve the schema owner rather than parsing documentation examples.
        field = next(v for v in schema["scalarKeys"] if v["name"] == "externalCodexProfile")
        self.assertEqual(set(field["allowed"]), {"default", "gpt-6.2-sol-high", "gpt-6.2-sol-xhigh", "gpt-6.2-sol-max"})

    def test_managed_wrapper_rejects_retired_model_before_execution(self):
        from scripts import provider_prompt
        control = provider_prompt.Control()
        control.user_approved_launch = True
        for model in ("gpt-5.6-terra", "gpt-6-sol", "gpt-6-astra"):
            selected = provider_prompt.PolicyBoundLaunch(
                control, "audit", (), model, "high",
                provider_prompt.ExternalRoleProvenance("qa-engineer", "external-reviewer"), None)
            with self.assertRaisesRegex(ValueError, "model-generation-not-admitted"):
                provider_prompt._qualify_managed_model_launch("codex", selected)

    def test_direct_and_assigned_external_lanes_reject_low(self):
        from scripts import provider_prompt
        control = provider_prompt.Control()
        control.user_approved_launch = True
        for assigned in ("none", "qa-engineer"):
            for model in CURRENT_CODEX_FAMILY_MODELS:
                selected = provider_prompt.PolicyBoundLaunch(
                    control, "audit", (), model, "low",
                    provider_prompt.ExternalRoleProvenance(assigned, "external-reviewer"), None)
                with self.assertRaisesRegex(ValueError, "low-not-admitted"):
                    provider_prompt._qualify_managed_model_launch("codex", selected)
        # Existing direct-user non-Low behavior remains unchanged.
        selected = provider_prompt.PolicyBoundLaunch(
            control, "audit", (), "custom-model", "medium",
            provider_prompt.ExternalRoleProvenance("none", "external-reviewer"), None)
        provider_prompt._qualify_managed_model_launch("codex", selected)

    def test_native_discovery_excludes_retired_choices(self):
        import importlib.util
        import sys
        spec = importlib.util.spec_from_file_location("latest_families_resolver", ROOT / "scripts/resolve-agents-mode.py")
        resolver = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = resolver
        spec.loader.exec_module(resolver)
        policy = json.loads((ROOT / "shared/role-routing-policy.v1.json").read_bytes())
        for task, roles in policy["taskRoleEligibility"].items():
            if task in {"micro", "mechanical-read", "mechanical"}:
                continue
            for role in roles:
                result = resolver.describe_ordinary_native_role_options(role, task,
                    {"explicitModelControl": True, "explicitReasoningEffortControl": True}, repo_root=ROOT)
                self.assertEqual(result["status"], "available", (role, task, result))
                self.assertTrue(all(o["model"] in CURRENT_CODEX_FAMILY_MODELS for o in result["options"]))
                rejected = resolver.resolve_ordinary_native_dispatch(result,
                    requested_model="gpt-5.6-sol", requested_effort="xhigh",
                    caller_rationale="retired negative", approved_execution_scope={"read": True}, user_approved_launch=True)
                self.assertEqual(rejected["status"], "denied", (role, task, rejected))

    def test_removing_low_preserves_other_profiles_defaults_and_task_eligibility(self):
        policy = json.loads((ROOT / "shared/role-routing-policy.v1.json").read_bytes())
        prior_dir = ROOT / "tests/fixtures/native-luna-policy-priors/no-low-previous"
        prior = json.loads((prior_dir / "role-routing-policy.v1.json").read_bytes())
        self.assertEqual(policy["profiles"], {k: v for k, v in prior["profiles"].items() if v["effort"] != "low"})
        self.assertEqual(policy["taskRoleEligibility"], prior["taskRoleEligibility"])
        for catalog in ("roles", "skillOnlyRoles"):
            for name, role in policy[catalog].items():
                self.assertEqual(role["defaultProfile"], prior[catalog][name]["defaultProfile"])
                self.assertEqual(role["allowedProfiles"],
                    [x for x in prior[catalog][name]["allowedProfiles"] if x != "astra-low"])
        pair = tuple((Path("shared") / name, hashlib.sha256((prior_dir / name).read_bytes()).hexdigest())
                     for name in ("role-routing-policy.v1.json", "orchestrarium-role-manifest.json"))
        self.assertIn(pair, installer._STOCK_NATIVE_ROLE_CONTRACT_PRIOR_PAIRS)

    def test_low_absent_from_catalogue_and_rejected_for_all_current_families(self):
        policy = json.loads((ROOT / "shared/role-routing-policy.v1.json").read_bytes())
        self.assertNotIn("low", policy["effortOrder"])
        self.assertTrue(all(p["effort"] != "low" for p in policy["profiles"].values()))
        self.assertTrue(all(t["requiredEffort"] != "low" for t in policy["taskClasses"].values()))
        for model in CURRENT_CODEX_FAMILY_MODELS:
            self.assertEqual(qualify_launch("codex", model, "low",
                user_approved_launch=True, user_approved_max=True), "low-not-admitted")
        for provider in ("claude", "kimi", "custom"):
            self.assertEqual(qualify_launch(provider, "custom", "low",
                user_approved_launch=True), "low-not-admitted")
        for effort in ("medium", "high", "xhigh", "max"):
            self.assertIsNone(qualify_launch("codex", "gpt-6.2-sol", effort,
                user_approved_launch=True, user_approved_max=True))

    def test_prior_stock_pair_preserved_for_safe_install_migration(self):
        prior = ROOT / "tests/fixtures/native-luna-policy-priors/latest-family-previous"
        pair = tuple((Path("shared") / name, hashlib.sha256((prior / name).read_bytes()).hexdigest())
                     for name in ("role-routing-policy.v1.json", "orchestrarium-role-manifest.json"))
        self.assertIn(pair, installer._STOCK_NATIVE_ROLE_CONTRACT_PRIOR_PAIRS)
        installer._source_codex_role_manifest(ROOT, ROOT / "src.codex/agents")

if __name__ == "__main__":
    unittest.main()
