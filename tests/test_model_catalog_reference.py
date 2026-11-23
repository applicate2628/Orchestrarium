"""Model-free contract for the advisory model catalogue."""
from pathlib import Path
import json
import runpy
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
RESOLVER = ROOT / "scripts/resolve-agents-mode.py"


class ModelCatalogueTests(unittest.TestCase):
    def describe(self, *extra, role="computational-scientist", task="critical-design"):
        result = subprocess.run([
            sys.executable, "-B", str(RESOLVER), "--provider", "codex", "--repo-root", str(ROOT),
            "--host-controls", "explicit", "--task-class", task, "--role", role,
            "--ordinary-native-action", "describe", "--json", *extra,
        ], capture_output=True, check=True, encoding="utf-8")
        return json.loads(result.stdout)

    def test_default_is_a_fallback_and_catalogue_does_not_reorder_it_first(self):
        description = self.describe()
        self.assertEqual(description["defaultProfile"], "astra-high")
        self.assertIn("fallback, not a priority", description["decisionGuidance"])
        self.assertIn("justify", description["decisionGuidance"])
        rows = description["modelCatalog"]
        self.assertEqual([row["model"] for row in rows],
                         list(dict.fromkeys(row["model"] for row in description["options"])))
        for row in rows:
            self.assertFalse({"relativePrice", "referencePrice", "recommendedProfile", "profiles",
                              "tiersByProfile"} & row.keys())

    def test_catalogue_never_adds_host_filtered_models(self):
        description = self.describe("--reported-model", "gpt-6.2-sol")
        self.assertEqual([row["model"] for row in description["modelCatalog"]], ["gpt-6.2-sol"])

    def test_benchmark_uses_one_cost_unit_per_allowed_effort(self):
        description = self.describe(role="worker", task="engineering")
        basis = description["modelCatalogBenchmark"]
        self.assertEqual(basis["baseline"], {"provider": "codex", "model": "gpt-6.2-sol", "effort": "high"})
        self.assertEqual(basis["observedDate"], "2026-11-22")
        self.assertEqual(description["defaultProfile"], "frontier-high")
        rows = {row["model"]: row for row in description["modelCatalog"]}
        sol = rows["gpt-6.2-sol"]
        self.assertEqual(sol["benchmarkByProfile"]["frontier-medium"],
                         {"score": 53, "costUnits": 0.7321, "minutes": 3.6})
        self.assertEqual(sol["benchmarkByProfile"]["frontier-high"]["costUnits"], 1)
        self.assertEqual(rows["gpt-6.2-astra"]["benchmarkByProfile"]["astra-high"]["costUnits"], 3.6964)
        self.assertNotIn("luna-medium", rows["gpt-6-luna"]["benchmarkByProfile"])
        self.assertTrue(sol["benchmarkSourceUrl"].startswith("https://artificialanalysis.ai/"))
        for row in rows.values():
            eligible = {option["profile"] for option in description["options"] if option["model"] == row["model"]}
            self.assertLessEqual(set(row["benchmarkByProfile"]), eligible)
        self.assertNotIn("costUsdPerTask", json.dumps(description))

    def test_comparison_does_not_authorize_unapproved_astra_or_remove_reason(self):
        common = [
            sys.executable, "-B", str(RESOLVER), "--provider", "codex", "--repo-root", str(ROOT),
            "--host-controls", "explicit", "--task-class", "critical-design", "--role", "computational-scientist",
            "--ordinary-native-action", "resolve", "--json", "--caller-rationale", "Review scientific evidence.",
            "--approved-scope-json", '{"read":true}',
        ]
        for model, effort, stable_id in (
            ("gpt-6.2-astra", "high", None),
            ("gpt-6.2-sol", "xhigh", "E_ORDINARY_NATIVE_PREFERENCE_DEVIATION_REASON_REQUIRED"),
        ):
            with self.subTest(model=model):
                result = subprocess.run(
                    [*common, "--requested-model", model, "--requested-effort", effort],
                    capture_output=True, check=True, encoding="utf-8",
                )
                reply = json.loads(result.stdout)
                self.assertEqual(reply["status"], "denied")
                self.assertNotIn("invocation", reply)
                self.assertNotIn("modelCatalog", reply)
                if stable_id is not None:
                    self.assertEqual(reply["stableId"], stable_id)

    def test_missing_or_invalid_benchmark_is_not_a_zero_or_inferred_profile(self):
        mod = runpy.run_path(str(RESOLVER))
        policy = json.loads((ROOT / "shared/role-routing-policy.v1.json").read_text(encoding="utf-8"))
        build = mod["_advisory_model_catalog"]
        options = [{"model": "gpt-6.2-sol", "profile": "frontier-medium", "effort": "medium"}]
        self.assertIsNone(build(policy, "other", options)[1])
        options[0]["effort"] = "unknown"
        self.assertIsNone(build(policy, "codex", options)[1])
        options[0]["effort"] = "medium"
        points = policy["modelReference"]["benchmarkSnapshot"]["models"]["codex"]["gpt-6.2-sol"]["efforts"]
        points["medium"]["minutesPerTask"] = True
        self.assertIsNone(build(policy, "codex", options)[1])
        points["medium"]["minutesPerTask"] = 3.6
        snapshot = policy["modelReference"]["benchmarkSnapshot"]
        baseline = snapshot["costBaseline"]
        snapshot["costBaseline"] = {"provider": "codex", "model": "gpt-6.2-astra", "effort": "max"}
        self.assertIsNone(build(policy, "codex", options)[1])
        snapshot["costBaseline"] = {**baseline, "extra": "not in the compact contract"}
        self.assertIsNone(build(policy, "codex", options)[1])
        snapshot["costBaseline"] = baseline
        points["high"]["costUsdPerTask"] = 0
        rows, basis = build(policy, "codex", options)
        self.assertIsNone(basis)
        self.assertNotIn("benchmarkByProfile", rows[0])


if __name__ == "__main__":
    unittest.main()
