
"""Model-free test for on-demand material in the ordinary native resolver."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = [
    sys.executable, "-B", str(ROOT / "scripts/resolve-agents-mode.py"),
    "--provider", "codex", "--repo-root", str(ROOT), "--task-class", "exploration",
    "--role", "analyst", "--host-controls", "explicit", "--json",
]

def call(*args):
    return json.loads(subprocess.check_output([*CLI, *args], cwd=ROOT))

def resolve(*args):
    return call("--ordinary-native-action", "resolve", "--caller-rationale",
                "Inspect the synthetic task without changes.",
                "--approved-scope-json", '{"read":true}', *args)

class NativeTaskActionTests(unittest.TestCase):
    def test_analyst_describe_lists_narrow_diagnosis_choice(self):
        actions = call("--ordinary-native-action", "describe")["taskActions"]
        self.assertEqual([x["id"] for x in actions], ["diagnose-defect"])

    def test_bug_action_delivers_exact_skill_once_and_keeps_authority(self):
        path = ROOT / "src.codex/skills/bug-hunting/SKILL.md"
        skill = path.read_bytes()
        base = resolve()
        selected = resolve("--task-action", "diagnose-defect")
        self.assertEqual(base["status"], "resolved")
        self.assertEqual(selected["status"], base["status"])
        for key in ("role", "resolvedModel", "resolvedEffort", "approvedExecutionScope", "failurePolicy"):
            self.assertEqual(selected[key], base[key])
        self.assertEqual(selected["taskContext"],
                         {"status":"attached", "skill":"bug-hunting", "sha256":hashlib.sha256(skill).hexdigest()})
        self.assertEqual(selected["invocation"]["promptPreamble"].count(skill.decode("utf-8")), 1)
        del selected["taskContext"]
        selected["invocation"]["promptPreamble"] = base["invocation"]["promptPreamble"]
        self.assertEqual(selected, base)

    def test_exploration_and_unknown_action_get_original_prompt(self):
        base = resolve()
        for action in ("overview", "unlisted-action"):
            self.assertEqual(resolve("--task-action", action), base)

    def test_missing_skill_is_reported_without_changing_invocation(self):
        import runpy
        import tempfile
        apply = runpy.run_path(str(ROOT / "scripts/resolve-agents-mode.py"))["_apply_native_task_action"]
        value = resolve()
        preamble = value["invocation"]["promptPreamble"]
        with tempfile.TemporaryDirectory() as root:
            apply(value, "diagnose-defect", Path(root))
        self.assertEqual(value["status"], "resolved")
        self.assertEqual(value["invocation"]["promptPreamble"], preamble)
        self.assertEqual(value["taskContext"], {"status":"unavailable", "skill":"bug-hunting"})

    def test_denied_launch_has_no_context_or_invocation(self):
        denied = resolve("--host-controls", "unavailable", "--task-action", "diagnose-defect")
        self.assertEqual(denied["status"], "denied")
        self.assertNotIn("taskContext", denied)
        self.assertNotIn("invocation", denied)


    def test_installed_layout_uses_only_its_own_catalog(self):
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            project, home = root / "project", root / "home"
            project.mkdir()
            skills = home / ".agents/skills"
            scripts = skills / "lead/scripts"
            shared = scripts.parent / "shared"
            scripts.mkdir(parents=True)
            shared.mkdir()
            for name in ("resolve-agents-mode.py", "linked_runtime_subroots.py"):
                shutil.copyfile(ROOT / "scripts" / name, scripts / name)
            shutil.copytree(ROOT / "scripts/model_routing", scripts / "model_routing",
                            ignore=shutil.ignore_patterns("__pycache__"))
            for name in ("role-routing-policy.v1.json", "external-role-taxonomy.v1.json"):
                shutil.copyfile(ROOT / "shared" / name, shared / name)
            shutil.copyfile(ROOT / "src.codex/agents/orchestrarium-role-manifest.json",
                            shared / "orchestrarium-role-manifest.json")
            shutil.copytree(ROOT / "src.codex/agents", home / ".codex/agents")
            for name in ("analyst", "bug-hunting"):
                (skills / name).mkdir()
                shutil.copyfile(ROOT / "src.codex/skills" / name / "SKILL.md", skills / name / "SKILL.md")
            decoy = project / ".agents/skills/bug-hunting/SKILL.md"
            decoy.parent.mkdir(parents=True)
            decoy.write_text("wrong project fixture", encoding="utf-8")
            args = [sys.executable, "-B", str(scripts / "resolve-agents-mode.py"),
                    "--provider", "codex", "--home", str(home), "--project-root", str(project),
                    "--ordinary-native-action", "resolve", "--role", "analyst", "--task-class", "exploration",
                    "--host-controls", "explicit", "--caller-rationale", "Investigate.",
                    "--approved-scope-json", '{"read":true}', "--task-action", "diagnose-defect", "--json"]
            result = json.loads(subprocess.check_output(args, cwd=project))
            self.assertEqual(result["status"], "resolved", result)
            self.assertEqual(result["taskContext"]["status"], "attached")
            self.assertNotIn("wrong project fixture", result["invocation"]["promptPreamble"])


if __name__ == "__main__":
    unittest.main()
