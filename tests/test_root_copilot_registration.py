"""Root route exercises the real selected-file lifecycle, never the hook command."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class RootCopilotRegistrationTests(unittest.TestCase):
    def invoke(self, cwd, *args):
        return subprocess.run([sys.executable, "-I", "-B", str(ROOT / "install.py"),
                               "--copilot-registration", *args], cwd=cwd,
                              input="", text=True, capture_output=True, timeout=60)

    def test_help_and_mixed_selection(self):
        result = self.invoke(ROOT, "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--previous", result.stdout)
        self.assertNotIn("What to install?", result.stdout)
        for args in (("--clients", "codex"), ("--list-clients",), ("--unknown",)):
            with self.subTest(args=args):
                result = self.invoke(ROOT, *args)
                self.assertEqual(result.returncode, 2)
                self.assertNotIn("Starting codex", result.stdout)

    @unittest.skipUnless(os.name == "nt", "Existing physical owner Windows acceptance")
    def test_real_relative_preview_create_update_remove(self):
        with tempfile.TemporaryDirectory(prefix="root-copilot-") as temporary:
            cwd = Path(temporary)
            project = cwd / "project with spaces"
            project.mkdir()
            sibling = project / ".github/hooks/foreign.json"
            sibling.parent.mkdir(parents=True)
            sibling.write_bytes(b"foreign bytes")
            target = sibling.with_name("orchestrarium.json")
            payloads = []
            for name in ("old", "new"):
                payload = json.dumps({"version":1,"hooks":{"preToolUse":[
                    {"type":"command","powershell":"not-executed-" + name}]}}).encode()
                (cwd / (name + ".json")).write_bytes(payload)
                payloads.append(payload)
            args = ("--project", project.name, "--desired", "old.json")
            result = self.invoke(cwd, *args)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(target.exists())
            self.assertFalse(json.loads(result.stdout)["applied"])
            result = self.invoke(cwd, *args, "--apply")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(target.read_bytes(), payloads[0])
            result = self.invoke(cwd, "--project", project.name, "--desired", "new.json", "--apply")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(target.read_bytes(), payloads[0])
            result = self.invoke(cwd, "--project", project.name, "--desired", "new.json",
                                 "--previous", "old.json", "--apply")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(target.read_bytes(), payloads[1])
            result = self.invoke(cwd, "--project", project.name, "--remove",
                                 "--previous", "new.json", "--apply")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(target.exists())
            self.assertEqual(sibling.read_bytes(), b"foreign bytes")
            self.assertEqual(sorted(p.read_bytes() for p in (project / "trash").glob("*.json")),
                             sorted(payloads))
