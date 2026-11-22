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

    def test_science_catalogue_shows_recommendation_and_relative_price_once_per_model(self):
        description = self.describe()
        rows = description["modelCatalog"]
        self.assertEqual([row["model"] for row in rows], ["gpt-6.2-astra", "gpt-6.2-sol"])
        recommended, baseline = rows
        self.assertEqual(recommended["recommendedProfile"], "astra-high")
        self.assertEqual(recommended["tiersByProfile"]["astra-high"], "apex")
        self.assertEqual(baseline["tiersByProfile"], {"frontier-xhigh": "frontier", "apex-max": "apex"})
        self.assertIsNone(baseline["recommendedProfile"])
        self.assertIn("science", recommended["strength"].lower())
        self.assertTrue(recommended["tradeoff"])
        self.assertEqual(recommended["relativePrice"]["uniform"], 4)
        self.assertEqual(baseline["relativePrice"]["uniform"], 1)
        self.assertEqual(recommended["referencePrice"]["units"], 4)
        self.assertEqual(recommended["referencePrice"]["basket"], {
            "input": 10000, "cachedInput": 0, "output": 1000,
        })
        self.assertEqual(baseline["referencePrice"]["units"], 1)
        self.assertEqual(recommended["relativePrice"]["billingBasis"], "codex-standard-credits")

    def test_catalogue_never_adds_host_filtered_model_or_changes_profiles(self):
        description = self.describe("--reported-model", "gpt-6.2-sol")
        rows = description["modelCatalog"]
        self.assertEqual([row["model"] for row in rows], ["gpt-6.2-sol"])
        self.assertEqual(rows[0]["profiles"], [option["profile"] for option in description["options"]])
        self.assertIsNone(rows[0]["recommendedProfile"])

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

    def test_reference_is_exact_provider_model_and_missing_price_is_not_zero(self):
        mod = runpy.run_path(str(RESOLVER))
        policy = json.loads((ROOT / "shared/role-routing-policy.v1.json").read_text(encoding="utf-8"))
        reference = mod["_advisory_model_reference"]
        luna = reference(policy, "codex", "gpt-6-luna")
        price = luna["relativePrice"]
        self.assertIsNone(price["uniform"])
        self.assertEqual(price["perTokenType"], {"input": 0.05, "cachedInput": 0.1, "output": 0.05})
        self.assertEqual(reference(policy, "other", "gpt-6-luna"), {
            "strength": None, "capabilitySource": None, "tradeoff": None,
            "relativePrice": None, "referencePrice": None,
        })
        policy["modelReference"]["priceBases"]["codex-standard-credits"]["rates"]["codex"]["gpt-6-luna"][0] = -1
        self.assertIsNone(reference(policy, "codex", "gpt-6-luna")["relativePrice"])

        model_reference = policy["modelReference"]
        model_reference["models"]["other"] = {"exact-id": {"referencePriceBasis": "standard-api-reference"}}
        model_reference["priceBases"]["standard-api-reference"]["rates"]["other"] = {
            "exact-id": [4, None, 20],
        }
        prices = model_reference["priceBases"]
        prices["codex-standard-credits"]["rates"]["codex"]["gpt-6.2-sol"][0] = 5e-324
        self.assertIsNone(reference(policy, "codex", "gpt-6.2-astra")["relativePrice"])
        exact = reference(policy, "other", "exact-id")
        self.assertEqual(exact["referencePrice"]["units"], 2)
        self.assertIsNone(exact["relativePrice"])


if __name__ == "__main__":
    unittest.main()
