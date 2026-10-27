from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts import production_installer as installer

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("explicit_effort_resolver", ROOT / "scripts/resolve-agents-mode.py")
resolver = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = resolver
spec.loader.exec_module(resolver)
HOST = {"explicitModelControl": True, "explicitReasoningEffortControl": True}
SCOPE = {"read": True}


class ExplicitSelectionTests(unittest.TestCase):
    def describe(self, role="qa-engineer", task="review", host=HOST):
        result = resolver.describe_ordinary_native_role_options(role, task, host, repo_root=ROOT)
        self.assertEqual(result["status"], "available", result)
        return result

    def select(self, desc, model=None, effort=None, rationale="routine", **kwargs):
        return resolver.resolve_ordinary_native_dispatch(desc, requested_model=model,
            requested_effort=effort, caller_rationale=rationale, approved_execution_scope=SCOPE, **kwargs)

    def test_exact_prior_pair_requires_unmodified_pair_and_tree(self):
        fixture = ROOT / "tests/fixtures/native-luna-policy-priors/ordinary-escalation-previous"
        with tempfile.TemporaryDirectory() as directory:
            installed, current = (Path(directory) / name for name in ("installed", "current"))
            for root in (installed, current):
                (root / "shared").mkdir(parents=True)
                (root / "retained").write_bytes(b"same unrelated content")
            names = ("role-routing-policy.v1.json", "orchestrarium-role-manifest.json")
            for name in names:
                (installed / "shared" / name).write_bytes((fixture / name).read_bytes())
            (current / "shared" / names[0]).write_bytes((ROOT / "shared" / names[0]).read_bytes())
            (current / "shared" / names[1]).write_bytes((ROOT / "src.codex/agents" / names[1]).read_bytes())
            stage = SimpleNamespace(path=current, digest=installer._tree_sha256(current, ignore_runtime_cache=True))
            expected = installer._STOCK_NATIVE_ROLE_CONTRACT_PRIOR_PAIRS[-2]
            self.assertEqual(installer._exact_stock_native_role_contract_prior_pair(installed, stage), expected)
            (installed / "shared" / names[0]).write_bytes((fixture / names[0]).read_bytes() + b" ")
            self.assertEqual(installer._exact_stock_native_role_contract_prior_pair(installed, stage), ())
            (installed / "shared" / names[0]).write_bytes((fixture / names[0]).read_bytes())
            (installed / "retained").write_bytes(b"custom unrelated content")
            self.assertEqual(installer._exact_stock_native_role_contract_prior_pair(installed, stage), ())

    def test_admitted_ordinary_escalations_are_explicit_and_do_not_fallback(self):
        policy = json.loads((ROOT / "shared/role-routing-policy.v1.json").read_text())
        roles = {**policy["roles"], **policy["skillOnlyRoles"]}
        for task, names in policy["taskRoleEligibility"].items():
            admissible = set(policy["taskClasses"][task].get("admissibleProfiles", ()))
            for role in names:
                if role in ("mechanical-scout", "mechanical-worker"):
                    continue
                allowed = set(roles[role]["allowedProfiles"]) & admissible
                if not any(p.startswith("terra-6.1-") for p in allowed):
                    continue
                description = self.describe(role, task)
                for profile in ("frontier-high", "frontier-xhigh"):
                    if profile not in admissible:
                        continue
                    self.assertIn(profile, allowed, (role, task))
                    effort = policy["profiles"][profile]["effort"]
                    result = self.select(description, "gpt-6.1-sol", effort)
                    self.assertEqual((result["status"], result["resolvedModel"], result["resolvedEffort"], result["fallback"]),
                                     ("resolved", "gpt-6.1-sol", effort, "none"), (role, task, result))
                    self.assertEqual(result["invocation"]["mode"], "generic-explicit-profile")
                if "luna-high" in allowed:
                    self.assertIn("terra-6.1-high", allowed, (role, task))
                    for profile in ("terra-6.1-medium", "terra-6.1-high"):
                        if profile not in allowed:
                            continue
                        result = self.select(description, "gpt-6.1-terra", policy["profiles"][profile]["effort"])
                        self.assertEqual((result["status"], result["fallback"]), ("resolved", "none"), (role, task, result))
        desc = self.describe("backend-engineer", "engineering")
        for model, effort in (("gpt-6-astra", "high"), ("gpt-6.1-terra", "max"), ("gpt-unknown", "high")):
            result = self.select(desc, model, effort)
            self.assertEqual((result["status"], result["fallback"]), ("denied", "none"))
        for task, role in (("mechanical-read", "mechanical-scout"), ("mechanical", "mechanical-worker")):
            decision = resolver.resolve_role_dispatch(task, role, "disabled", repo_root=ROOT)
            self.assertEqual((decision["status"], decision["fallback"]), ("unavailable", "none"))
        ordinary = self.describe("backend-engineer", "engineering")
        self.assertEqual(self.select(ordinary, "gpt-6.1-terra", "high")["status"], "resolved")

    def test_omitted_choice_uses_recommendation_and_partial_pair_is_denied(self):
        desc = self.describe()
        for rationale in ("routine", "complex, select extra high"):
            result = self.select(desc, rationale=rationale)
            self.assertEqual((result["resolvedModel"], result["resolvedEffort"]),
                             (desc["defaultModel"], desc["defaultEffort"]))
            self.assertEqual(result["invocation"]["mode"], "generic-explicit-profile")
            for model, effort in (("gpt-6.1-terra", None), (None, "high")):
                result = self.select(desc, model, effort, rationale)
                self.assertEqual(result["status"], "denied")
        legacy = json.loads(json.dumps(desc))
        self.assertEqual(self.select(legacy)["status"], "denied")
        self.assertEqual(self.select(legacy, "gpt-6.1-terra", "high")["status"], "denied")

    def test_exact_choices_controls_floors_and_approval(self):
        desc = self.describe()
        for effort in ("high", "xhigh"):
            result = self.select(desc, "gpt-6.1-terra", effort)
            self.assertEqual((result["resolvedModel"], result["resolvedEffort"]), ("gpt-6.1-terra", effort))
            self.assertEqual(result["invocation"]["mode"], "generic-explicit-profile")
        self.assertEqual(self.select(desc, "gpt-6.1-terra", "low")["status"], "denied")
        self.assertEqual(self.select(desc, "gpt-6-luna", "medium")["status"], "denied")
        no_controls = self.describe(host={"explicitModelControl": False, "explicitReasoningEffortControl": False})
        self.assertEqual(self.select(no_controls, "gpt-6.1-terra", "high")["stableId"], "E_ORDINARY_NATIVE_CONTROLS_UNAVAILABLE")
        filtered = self.describe(host={**HOST, "reportedModels": ["gpt-6.1-sol"], "reportedEfforts": ["high"]})
        self.assertEqual(self.select(filtered, "gpt-6.1-terra", "high")["status"], "denied")
        for model, effort in (("gpt-6-astra", "high"), ("gpt-6.1-terra", "max")):
            self.assertEqual(self.select(desc, model, effort)["status"], "denied")
            self.assertEqual(self.select(desc, model, effort, user_approved_launch=True)["status"], "resolved")
        science = self.describe("scientific-software-engineer", "engineering")
        self.assertEqual(science["defaultModel"], "gpt-6.1-sol")
        self.assertEqual(self.select(science, "gpt-6.1-sol", "high")["status"], "resolved")
        engineering = self.describe("backend-engineer", "engineering")
        self.assertEqual(self.select(engineering, "gpt-6-luna", "high")["status"], "resolved")

    def test_configured_carrier_and_role_tuples_are_complete_and_binding(self):
        with tempfile.TemporaryDirectory(prefix="ordinary-controls-") as directory:
            roles = Path(directory)
            for name in ("default.toml", "backend-engineer.toml"):
                shutil.copy2(ROOT / "src.codex/agents" / name, roles / name)
            carrier_path = roles / "default.toml"
            role_path = roles / "backend-engineer.toml"
            carrier_base, role_base = carrier_path.read_bytes(), role_path.read_bytes()
            manifest = ROOT / "src.codex/agents/orchestrarium-role-manifest.json"

            def describe():
                result = resolver._describe_ordinary_native_role_options_in_layout(
                    "backend-engineer", "engineering", HOST, repo_root=ROOT,
                    manifest_path=manifest, role_root=roles)
                self.assertEqual(result["status"], "available", result)
                return result

            for controls, expected in (
                (b"", "resolved"),
                (b'model = "gpt-6.1-terra"\n', "denied"),
                (b'model_reasoning_effort = "medium"\n', "denied"),
                (b'model = "gpt-6.1-terra"\nmodel_reasoning_effort = "medium"\n', "resolved"),
                (b'model = "gpt-6.1-sol"\nmodel_reasoning_effort = "high"\n', "denied"),
            ):
                with self.subTest(carrier=controls):
                    carrier_path.write_bytes(controls + carrier_base)
                    desc = describe()
                    for model, effort in ((None, None), ("gpt-6.1-terra", "medium")):
                        result = self.select(desc, model, effort)
                        self.assertEqual(result["status"], expected, result)
                        if controls and (b"model =" not in controls or b"model_reasoning_effort =" not in controls):
                            self.assertEqual(result["configurationDiagnostic"]["reason"], "incomplete-configured-tuple")
                            self.assertEqual(desc["configurationProvenance"]["genericProfileCompatibility"]["terra-6.1-medium"], "conflict")

            carrier_path.write_bytes(carrier_base)
            for missing in (b'model = "gpt-6.1-terra"\n', b'model_reasoning_effort = "medium"\n'):
                with self.subTest(role_missing=missing):
                    role_path.write_bytes(role_base.replace(missing, b"", 1))
                    desc = describe()
                    for model, effort in ((None, None), ("gpt-6.1-terra", "medium")):
                        result = self.select(desc, model, effort)
                        self.assertEqual(result["status"], "denied", result)
                        self.assertEqual(result["configurationDiagnostic"]["stage"], "inherited-control-unresolved")

            role_path.write_bytes(role_base.replace(b'model_reasoning_effort = "medium"', b'model_reasoning_effort = "high"', 1))
            desc = describe()
            self.assertEqual(self.select(desc)["resolvedEffort"], "high")
            self.assertEqual(self.select(desc, "gpt-6.1-terra", "high")["status"], "resolved")
            self.assertEqual(self.select(desc, "gpt-6.1-terra", "medium")["status"], "denied")
            role_path.write_bytes(role_base.replace(b'model_reasoning_effort = "medium"', b'model_reasoning_effort = "low"', 1))
            desc = describe()
            for model, effort in ((None, None), ("gpt-6.1-terra", "medium")):
                result = self.select(desc, model, effort)
                self.assertEqual(result["status"], "denied", result)
                self.assertEqual(result["configurationDiagnostic"]["reason"], "configured-tuple-not-admitted")

    def test_role_with_no_controls_uses_task_default_and_allows_explicit_choices(self):
        with tempfile.TemporaryDirectory(prefix="ordinary-zero-controls-") as directory:
            roles = Path(directory)
            shutil.copy2(ROOT / "src.codex/agents/default.toml", roles / "default.toml")
            manifest = ROOT / "src.codex/agents/orchestrarium-role-manifest.json"
            for role, task, expected in (
                ("backend-engineer", "engineering", ("gpt-6.1-terra", "medium")),
                ("worker", "recovery", ("gpt-6.1-sol", "high")),
            ):
                with self.subTest(role=role, task=task):
                    content = (ROOT / "src.codex/agents" / (role + ".toml")).read_bytes()
                    content = content.replace(b'model = "gpt-6.1-terra"\n', b"", 1)
                    content = content.replace(b'model_reasoning_effort = "medium"\n', b"", 1)
                    (roles / (role + ".toml")).write_bytes(content)
                    desc = resolver._describe_ordinary_native_role_options_in_layout(
                        role, task, HOST, repo_root=ROOT, manifest_path=manifest, role_root=roles)
                    self.assertEqual(desc["status"], "available", desc)
                    self.assertIsNone(desc["defaultConfigurationError"])
                    default = self.select(desc)
                    self.assertEqual((default["resolvedModel"], default["resolvedEffort"]), expected)
                    for model, effort in (("gpt-6.1-terra", "medium"), ("gpt-6.1-sol", "high")):
                        self.assertEqual(self.select(desc, model, effort)["status"], "resolved")

    def test_installed_cli_foreign_home_and_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); home = base / "home"; project = base / "project"; foreign = base / "foreign"
            scripts = home / ".agents/skills/lead/scripts"; shared = scripts.parent / "shared"
            scripts.mkdir(parents=True); shared.mkdir(); project.mkdir(); foreign.mkdir()
            for name in ("resolve-agents-mode.py", "linked_runtime_subroots.py"):
                shutil.copy2(ROOT / "scripts" / name, scripts / name)
            shutil.copytree(ROOT / "scripts/model_routing", scripts / "model_routing", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copy2(ROOT / "shared/role-routing-policy.v1.json", shared)
            shutil.copy2(ROOT / "src.codex/agents/orchestrarium-role-manifest.json", shared)
            shutil.copytree(ROOT / "src.codex/agents", home / ".codex/agents")
            role = home / ".codex/agents/qa-engineer.toml"
            role.write_text(role.read_text().replace('model_reasoning_effort = "high"', 'model_reasoning_effort = "xhigh"'))
            common = [sys.executable, "-B", str(scripts / "resolve-agents-mode.py"), "--provider", "codex", "--project-root", str(project), "--home", str(home), "--task-class", "review", "--role", "qa-engineer", "--host-controls", "explicit", "--json"]
            def call(*args):
                run = subprocess.run(common + list(args), cwd=foreign, capture_output=True, text=True, timeout=30)
                self.assertEqual(run.returncode, 0, run.stderr)
                return json.loads(run.stdout)
            desc = call("--ordinary-native-action", "describe")
            self.assertEqual((desc["defaultModel"], desc["defaultEffort"]), ("gpt-6.1-terra", "xhigh"))
            args = ("--ordinary-native-action", "resolve", "--caller-rationale", "chosen explicitly", "--approved-scope-json", '{"read":true}')
            default = call(*args)
            self.assertEqual((default["resolvedModel"], default["resolvedEffort"]), ("gpt-6.1-terra", "xhigh"))
            self.assertEqual(default["invocation"]["mode"], "generic-explicit-profile")
            selected = call(*args, "--requested-model", desc["defaultModel"], "--requested-effort", desc["defaultEffort"])
            self.assertEqual((selected["resolvedModel"], selected["resolvedEffort"]), ("gpt-6.1-terra", "xhigh"))
            carrier = home / ".codex/agents/default.toml"
            carrier.write_text('model = "gpt-6.1-sol"\n' + carrier.read_text())
            conflict = call(*args, "--requested-model", desc["defaultModel"], "--requested-effort", desc["defaultEffort"])
            self.assertEqual(conflict["configurationDiagnostic"]["stage"], "configured-carrier-conflict")
            self.assertEqual(conflict["fallback"], "none")


if __name__ == "__main__":
    unittest.main()
