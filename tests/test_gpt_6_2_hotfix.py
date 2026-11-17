"""Offline GPT-6.2 routing qualification; no provider calls."""
import json
from pathlib import Path
import unittest
from scripts.model_routing.launch_policy import qualify_launch
from scripts import provider_prompt

ROOT = Path(__file__).resolve().parents[1]

class GPT62Tests(unittest.TestCase):
    def test_astra_requires_agreement_at_every_admitted_effort(self):
        for model in ("gpt-6-astra", "gpt-6.2-astra"):
            for effort in ("medium", "high", "xhigh", "max"):
                with self.subTest(model=model, effort=effort):
                    self.assertEqual(qualify_launch("codex", model, effort), "individual-launch-approval-required")
                    self.assertIsNone(qualify_launch("codex", model, effort, user_approved_launch=True))

    def test_factory_profiles_use_current_generation(self):
        policy = json.loads((ROOT/"shared/role-routing-policy.v1.json").read_text())
        for name in ("frontier-medium", "frontier-high", "frontier-xhigh", "apex-max"):
            self.assertEqual(policy["profiles"][name]["codexModel"], "gpt-6.2-sol")
        for name in ("astra-medium", "astra-high", "astra-xhigh", "astra-max"):
            self.assertEqual(policy["profiles"][name]["codexModel"], "gpt-6.2-astra")

    def test_default_external_profile(self):
        _, model, effort = provider_prompt.resolved_profile("codex", [])
        self.assertEqual((model, effort), ("gpt-6.2-sol", "xhigh"))

    def test_explicit_legacy_external_profiles_remain_literal(self):
        for model in ("gpt-6.1-sol", "gpt-6-sol", "gpt-6-astra"):
            _, actual, effort = provider_prompt.resolved_profile("codex", ["--model", model, "-c", "model_reasoning_effort=high"])
            self.assertEqual((actual, effort), (model, "high"))

    def test_no_new_low_or_recursive_worker_route(self):
        for model in ("gpt-6.2-sol", "gpt-6.2-astra"):
            for effort in ("low", "ultra"):
                self.assertIsNotNone(qualify_launch("codex", model, effort, user_approved_launch=True))

if __name__ == "__main__":
    unittest.main()

class ConfigurationMigrationTests(unittest.TestCase):
    def test_legacy_profiles_migrate_same_effort_and_custom_values_survive(self):
        import importlib.util
        import sys
        path = ROOT/"scripts/normalize-agents-mode.py"
        spec = importlib.util.spec_from_file_location("gpt62_normalizer", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        default = module.ScalarMeta("gpt-6.2-sol-xhigh", "")
        for generation in ("6.1",):
            for effort in ("high", "xhigh", "max"):
                old = "gpt-" + generation + "-sol-" + effort
                for spelling in (old, '"' + old + '"', "'" + old + "'"):
                    self.assertEqual(module.render_scalar("externalCodexProfile", default,
                        {"externalCodexProfile":module.ScalarMeta(spelling, "")}),
                        ["externalCodexProfile: gpt-6.2-sol-" + effort])
        for unchanged in ("default", "gpt-6.2-sol-high", "gpt-6-sol-high", "gpt-5.6-sol-max", "custom-model-profile"):
            self.assertEqual(module.render_scalar("externalCodexProfile", default,
                {"externalCodexProfile":module.ScalarMeta(unchanged, "")}),
                ["externalCodexProfile: " + unchanged])
