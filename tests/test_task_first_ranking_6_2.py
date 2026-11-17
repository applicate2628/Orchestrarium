"""Offline ranking and stock upgrade acceptance; no model runs."""
import hashlib
import json
from pathlib import Path
import tempfile
import tomllib
import unittest
from scripts import production_installer as installer

ROOT = Path(__file__).resolve().parents[1]
PRIORS = ROOT / "tests/fixtures/native-luna-policy-priors/ranking-6-2-previous"


class RankingTests(unittest.TestCase):
    def test_factory_ranking_and_native_manifest(self):
        policy = json.loads((ROOT / "shared/role-routing-policy.v1.json").read_bytes())
        manifest = installer._source_codex_role_manifest(ROOT, ROOT / "src.codex/agents")
        expected = {
            "mechanical-scout": "luna-xhigh", "mechanical-worker": "luna-xhigh",
            "explorer": "terra-6.1-high", "knowledge-archivist": "terra-6.1-high",
            "worker": "frontier-high", "backend-engineer": "frontier-high",
            "platform-engineer": "frontier-high", "scientific-software-engineer": "frontier-high",
            "algorithm-scientist": "astra-high", "computational-scientist": "astra-high",
        }
        for role, profile in expected.items():
            self.assertEqual(policy["roles"][role]["defaultProfile"], profile)
            self.assertIn(role, manifest["roles"])
        for role in ("architect", "architecture-reviewer", "security-engineer", "security-reviewer"):
            self.assertIn("astra-high", policy["roles"][role]["allowedProfiles"])
            self.assertIn("astra-xhigh", policy["roles"][role]["allowedProfiles"])

    def test_exact_previous_stock_migrates_but_custom_controls_survive(self):
        (ROOT / ".test-tmp").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".test-tmp") as directory:
            home = Path(directory)
            agents = home / "agents"
            agents.mkdir()
            for prior in PRIORS.glob("*.toml"):
                (agents / prior.name).write_bytes(prior.read_bytes())
            custom = agents / "explorer.toml"
            customized = custom.read_bytes().replace(b'model_reasoning_effort = "medium"',
                                                     b'model_reasoning_effort = "xhigh"') + b"\n# user tuning\n"
            custom.write_bytes(customized)
            plan = installer._preflight_codex_native_roles(ROOT, ROOT / "src.codex/agents",
                                                           agents, home / "config.toml")
            by_name = {item.relative_path.name: item for item in plan.role_files}
            self.assertEqual(by_name["explorer.toml"].payload, customized)
            self.assertTrue(by_name["explorer.toml"].configured)
            for prior in PRIORS.glob("*.toml"):
                if prior.name == "explorer.toml":
                    continue
                record = by_name[prior.name]
                self.assertEqual(record.accepted_prior, hashlib.sha256(prior.read_bytes()).hexdigest())
                self.assertEqual(record.payload, (ROOT / "src.codex/agents" / prior.name).read_bytes())

    def test_prior_contract_pair_is_recognized(self):
        pair = ((Path("shared/role-routing-policy.v1.json"),
                 hashlib.sha256((PRIORS / "role-routing-policy.v1.json").read_bytes()).hexdigest()),
                (Path("shared/orchestrarium-role-manifest.json"),
                 hashlib.sha256((PRIORS / "orchestrarium-role-manifest.json").read_bytes()).hexdigest()))
        self.assertIn(pair, installer._STOCK_NATIVE_ROLE_CONTRACT_PRIOR_PAIRS)


if __name__ == "__main__":
    unittest.main()
