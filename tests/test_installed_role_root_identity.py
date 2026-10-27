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


ROOT = Path(__file__).resolve().parents[1]


class InstalledRootIdentityTests(unittest.TestCase):
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
