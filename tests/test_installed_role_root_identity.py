from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from _filesystem_fixture_support import _make_directory_junction, _make_file_symlink


ROOT = Path(__file__).resolve().parents[1]


class InstalledRootIdentityTests(unittest.TestCase):
    def test_hardlink_invocation_uses_selected_package_not_foreign_companion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home, project, foreign_dir = root / "home", root / "project", root / "foreign"
            project.mkdir()
            foreign_dir.mkdir()
            scripts = home / ".agents/skills/lead/scripts"
            shared = scripts.parent / "shared"
            scripts.mkdir(parents=True)
            shared.mkdir()
            for name in ("resolve-agents-mode.py", "linked_runtime_subroots.py"):
                shutil.copy2(ROOT / "scripts" / name, scripts / name)
            shutil.copytree(ROOT / "scripts/model_routing", scripts / "model_routing",
                            ignore=shutil.ignore_patterns("__pycache__"))
            for name in ("role-routing-policy.v1.json", "external-role-taxonomy.v1.json"):
                shutil.copy2(ROOT / "shared" / name, shared)
            shutil.copy2(ROOT / "src.codex/agents/orchestrarium-role-manifest.json", shared)
            shutil.copytree(ROOT / "src.codex/agents", home / ".codex/agents")
            selected = scripts / "resolve-agents-mode.py"
            foreign = foreign_dir / selected.name
            os.link(selected, foreign)
            poison = foreign_dir / "model_routing/launch_policy.py"
            poison.parent.mkdir()
            marker = root / "poison-executed"
            poison.write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('executed')\n", encoding="utf-8")

            def call(provider, action, executing=foreign):
                result = subprocess.run([sys.executable, "-B", str(executing), "--provider", provider,
                    "--project-root", str(project), "--home", str(home), *action, "--json"],
                    cwd=project, text=True, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)

            ordinary = ["--ordinary-native-action", "resolve", "--task-class", "engineering",
                        "--role", "worker", "--host-controls", "explicit", "--caller-rationale", "test",
                        "--approved-scope-json", '{"write":true}', "--requested-model", "gpt-6-astra",
                        "--requested-effort", "high"]
            decision = call("codex", ordinary)
            self.assertEqual(decision["status"], "denied", decision)
            self.assertEqual(decision["stableId"], "E_ORDINARY_NATIVE_SELECTION_INVALID")
            external = call("kimi", ["--resolve-external-dispatch", "--task-class", "exploration", "--role", "analyst"])
            self.assertEqual(external["status"], "denied", external)
            self.assertFalse(marker.exists())

            decision = call("codex", ordinary, selected)
            self.assertEqual(decision["configurationDiagnostic"]["reason"], "individual-launch-approval-required")

            selected_companion = scripts / "model_routing/launch_policy.py"
            selected_companion.unlink()
            missing = call("codex", ordinary, selected)
            self.assertEqual(missing["status"], "denied", missing)
            self.assertEqual(missing["stableId"], "E_ORDINARY_NATIVE_SELECTION_INVALID")
            self.assertEqual(missing["fallback"], "none")
            self.assertFalse(marker.exists())

            selected.unlink()
            _make_file_symlink(selected, foreign)
            (scripts / "linked_runtime_subroots.py").write_text(
                "from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('executed')\n",
                encoding="utf-8")
            nonordinary = call("codex", ordinary)
            self.assertEqual(nonordinary["status"], "denied", nonordinary)
            self.assertFalse(marker.exists())

    def test_installed_physical_script_retains_logical_candidate_authority(self) -> None:
        spec = importlib.util.spec_from_file_location("identity_alias_resolver", ROOT / "scripts/resolve-agents-mode.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            physical_home = base / "physical-home"
            logical_home = base / "logical-home"
            physical_home.mkdir()
            if os.name == "nt":
                _make_directory_junction(logical_home, physical_home)
            else:
                logical_home.symlink_to(physical_home, target_is_directory=True)
            scripts = physical_home / ".agents/skills/lead/scripts"
            shared = scripts.parent / "shared"
            scripts.mkdir(parents=True)
            shared.mkdir()
            for name in ("resolve-agents-mode.py", "linked_runtime_subroots.py"):
                shutil.copy2(ROOT / "scripts" / name, scripts / name)
            shutil.copytree(ROOT / "scripts/model_routing", scripts / "model_routing",
                            ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copy2(ROOT / "shared/role-routing-policy.v1.json", shared)
            shutil.copy2(ROOT / "shared/external-role-taxonomy.v1.json", shared)
            shutil.copy2(ROOT / "src.codex/agents/orchestrarium-role-manifest.json", shared)
            shutil.copytree(ROOT / "src.codex/agents", physical_home / ".codex/agents")
            logical = logical_home / ".agents/skills/lead/scripts/resolve-agents-mode.py"
            physical = scripts / "resolve-agents-mode.py"
            project = base / "project"
            project.mkdir()
            def dispatch(executing, provider, action):
                result = subprocess.run(
                    [sys.executable, "-B", str(executing), "--provider", provider,
                     "--project-root", str(project), "--home", str(logical_home), *action, "--json"],
                    cwd=project, text=True, capture_output=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)
            ordinary = ["--ordinary-native-action", "resolve", "--task-class", "engineering",
                        "--role", "worker", "--host-controls", "explicit", "--caller-rationale", "test",
                        "--approved-scope-json", '{"write":true}']
            external = ["--resolve-external-dispatch", "--task-class", "exploration", "--role", "analyst"]
            logical_decision = dispatch(logical, "codex", ordinary)
            self.assertEqual(logical_decision["status"], "resolved", logical_decision)
            self.assertEqual(dispatch(physical, "codex", ordinary), logical_decision)
            external_decision = dispatch(logical, "kimi", external)
            self.assertEqual(external_decision["status"], "external-authorized", external_decision)
            self.assertEqual(dispatch(physical, "kimi", external), external_decision)
            for executing in (logical, physical):
                lead, manifest, roles, _authority, _package = module._installed_role_dispatch_layout(executing, project, physical_home)
                self.assertEqual(lead, physical.parent.parent)
                self.assertEqual(manifest, physical.parent.parent / "shared/orchestrarium-role-manifest.json")
                self.assertTrue(os.path.samefile(roles, physical_home / ".codex/agents"))
                self.assertTrue(os.path.samefile(module._installed_external_policy_root(executing, project, physical_home), scripts.parent))
                same_home = module._installed_role_dispatch_layout(executing, logical_home, physical_home)
                self.assertTrue(os.path.samefile(same_home[2], physical_home / ".codex/agents"))
                self.assertTrue(os.path.samefile(module._installed_external_policy_root(executing, logical_home, physical_home), scripts.parent))
            other_home = base / "other-home"
            other_home.mkdir()
            foreign = base / "foreign.py"
            shutil.copy2(physical, foreign)
            for executing, home in ((physical, other_home), (foreign, physical_home)):
                with self.assertRaisesRegex(ValueError, "missing or ambiguous"):
                    module._installed_role_dispatch_layout(executing, project, home)
                with self.assertRaisesRegex(ValueError, "missing or ambiguous"):
                    module._installed_external_policy_root(executing, project, home)
            project_scripts = project / ".agents/skills/lead/scripts"
            project_scripts.mkdir(parents=True)
            _make_file_symlink(project_scripts / physical.name, physical)
            (project / ".codex/agents").mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "missing or ambiguous"):
                module._installed_role_dispatch_layout(physical, project, physical_home)
            with self.assertRaisesRegex(ValueError, "missing or ambiguous"):
                module._installed_external_policy_root(physical, project, physical_home)
            self.assertTrue(logical_home.is_junction() if os.name == "nt" else logical_home.is_symlink())

    def test_selected_package_retarget_never_executes_foreign_companions(self) -> None:
        spec = importlib.util.spec_from_file_location("identity_retarget_resolver", ROOT / "scripts/resolve-agents-mode.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original, foreign, logical = root / "original", root / "foreign", root / "selected"
            original.mkdir()
            foreign.mkdir()
            script = original / "resolve-agents-mode.py"
            shutil.copy2(ROOT / "scripts/resolve-agents-mode.py", script)
            os.link(script, foreign / script.name)
            marker = root / "poison-executed"
            payload = "from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('executed')\n"
            (foreign / "linked_runtime_subroots.py").write_text(payload, encoding="utf-8")
            (foreign / "model_routing").mkdir()
            (foreign / "model_routing/launch_policy.py").write_text(payload, encoding="utf-8")
            if os.name == "nt":
                _make_directory_junction(logical, original)
            else:
                logical.symlink_to(original, target_is_directory=True)
            package = module._SelectedCodePackage(logical / script.name)
            if os.name == "nt":
                os.rmdir(logical)
                _make_directory_junction(logical, foreign)
            else:
                logical.unlink()
                logical.symlink_to(foreign, target_is_directory=True)
            self.assertTrue(os.path.samefile(logical / script.name, script))
            with self.assertRaises(ValueError):
                module._load_model_launch_policy(package)
            with self.assertRaises(ValueError):
                module._linked_runtime_subroots_module(package)
            self.assertFalse(marker.exists())

    def test_public_dispatch_same_and_distinct_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            lead = home / ".agents/skills/lead"
            scripts = lead / "scripts"
            shared = lead / "shared"
            scripts.mkdir(parents=True)
            shared.mkdir()
            for name in ("resolve-agents-mode.py", "linked_runtime_subroots.py"):
                shutil.copy2(ROOT / "scripts" / name, scripts / name)
            shutil.copytree(ROOT / "scripts/model_routing", scripts / "model_routing",
                            ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copy2(ROOT / "shared/role-routing-policy.v1.json", shared)
            shutil.copy2(ROOT / "src.codex/agents/orchestrarium-role-manifest.json", shared)
            shutil.copytree(ROOT / "src.codex/agents", home / ".codex/agents")
            resolver = scripts / "resolve-agents-mode.py"
            project = Path(temporary) / "project"
            project.mkdir()

            def dispatch(project_root: Path, action: list[str]) -> dict:
                command = [sys.executable, "-B", str(resolver), "--provider", "codex",
                           "--project-root", str(project_root), "--home", str(home),
                           *action, "--json"]
                result = subprocess.run(command, cwd=home, text=True, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)

            ordinary = ["--ordinary-native-action", "resolve", "--task-class", "engineering",
                        "--role", "worker", "--host-controls", "explicit", "--caller-rationale",
                        "test", "--approved-scope-json", '{"write":true}']
            mechanical = ["--resolve-role-dispatch", "--task-class", "mechanical-read",
                          "--role", "mechanical-scout", "--feature-state", "enabled"]
            description = dispatch(project, ["--ordinary-native-action", "describe", "--task-class", "engineering",
                                             "--role", "worker", "--host-controls", "explicit"])
            self.assertEqual(description["status"], "available", description)
            separate = dispatch(project, ordinary)
            self.assertIn("resolvedModel", separate, separate)
            self.assertEqual((separate["resolvedModel"], separate["resolvedEffort"]),
                             ("gpt-6.1-terra", "medium"))
            same = dispatch(home, ordinary)
            self.assertEqual((same["resolvedModel"], same["resolvedEffort"]),
                             ("gpt-6.1-terra", "medium"))
            mechanical_same = dispatch(home, mechanical)
            self.assertEqual(mechanical_same["status"], "native-required")
            self.assertEqual(mechanical_same, dispatch(project, mechanical))
            alias = home / ".." / home.name
            self.assertEqual(dispatch(alias, ordinary), same)
            linked_home = Path(temporary) / "home-alias"
            if os.name == "nt":
                link = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(linked_home),
                                       str(home)], capture_output=True, text=True, timeout=30)
                self.assertEqual(link.returncode, 0, link.stderr)
            else:
                linked_home.symlink_to(home, target_is_directory=True)
            self.assertEqual(dispatch(linked_home, ordinary), same)

            roles = home / ".codex/agents"
            physical_roles = home / ".codex/roles-target"
            roles.rename(physical_roles)
            if os.name == "nt":
                link = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(roles),
                                       str(physical_roles)], capture_output=True, text=True, timeout=30)
                self.assertEqual(link.returncode, 0, link.stderr)
            else:
                roles.symlink_to(physical_roles, target_is_directory=True)
            self.assertEqual(dispatch(home, ordinary), same)
            self.assertEqual(dispatch(home, mechanical), mechanical_same)

    def test_distinct_candidate_authorities_remain_ambiguous(self) -> None:
        spec = importlib.util.spec_from_file_location("identity_resolver", ROOT / "scripts/resolve-agents-mode.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        original = module._same_path
        def candidate_collision(left: Path, right: Path) -> bool:
            return True if left == Path("resolver") else original(left, right)

        with patch.object(module, "_same_path", side_effect=candidate_collision):
            with self.assertRaisesRegex(ValueError, "missing or ambiguous"):
                module._installed_role_dispatch_layout(Path("resolver"), Path("project"), Path("home"))


if __name__ == "__main__":
    unittest.main()
