"""Exact stock-role upgrade; customized controls stay user-owned (offline)."""
import hashlib
from pathlib import Path
import tempfile
import tomllib
import unittest

from scripts import production_installer as installer

ROOT = Path(__file__).resolve().parents[1]


class Gpt62StockRoles(unittest.TestCase):
    def test_factory_contract_registered_without_retargeting_terra_migration(self):
        pairs = installer._STOCK_NATIVE_ROLE_CONTRACT_PRIOR_PAIRS
        self.assertIn(((Path("shared/role-routing-policy.v1.json"),
                        "fafd37b08375e0d261a57edd06613ab15dcaac9075fc031bf2702b173e6f8cf7"),
                       (Path("shared/orchestrarium-role-manifest.json"),
                        "2ca416fa4fc2aa93c7fe74dc6db62273d72367a901e0ee260fce55377acb6d77")), pairs)
        self.assertEqual(pairs[-1][0][1],
                         "7a9799398a32f16b67198297af56d168d2777a2c164e0b14440538205e4c6163")

    def test_exact_old_roles_upgrade_and_customized_roles_stay_literal(self):
        sources = ROOT / "src.codex/agents"
        # These roles preserve the old Sol payload except for the model ID.
        # Other current Sol roles migrated from Terra; replacing their model ID
        # would invent an unshipped prior rather than test a supported upgrade.
        prior_sol_roles = ("architect", "architecture-reviewer",
                           "scientific-software-engineer", "security-engineer",
                           "security-reviewer")
        changed = [sources / f"{role}.toml" for role in prior_sol_roles]
        for customized in (False, True):
            with self.subTest(customized=customized), tempfile.TemporaryDirectory() as directory:
                target = Path(directory); agents = target / "agents"; agents.mkdir()
                old_bytes = {}
                for source in changed:
                    prior = source.read_bytes().replace(b'gpt-6.2-sol', b'gpt-6.1-sol')
                    self.assertIn(hashlib.sha256(prior).hexdigest(),
                                  installer._STOCK_NATIVE_ROLE_MIGRATION_SHA256[source.stem])
                    if customized:
                        prior += b"\n# User-owned customization\n"
                    old_bytes[source.name] = prior
                    (agents / source.name).write_bytes(prior)
                plan = installer._preflight_codex_native_roles(
                    ROOT, sources, agents, target / "config.toml")
                for item in plan.role_files:
                    if item.relative_path.name not in old_bytes:
                        continue
                    old = old_bytes[item.relative_path.name]
                    self.assertEqual((agents / item.relative_path).read_bytes(), old)
                    parsed = tomllib.loads(item.payload.decode())
                    self.assertEqual(parsed["model"], "gpt-6.1-sol" if customized else "gpt-6.2-sol")
                    if customized:
                        self.assertIsNone(item.accepted_prior)
                        self.assertEqual(item.payload, old)
                    else:
                        self.assertEqual(item.accepted_prior, hashlib.sha256(old).hexdigest())
                        self.assertEqual(item.payload, (sources / item.relative_path).read_bytes())


if __name__ == "__main__":
    unittest.main()
