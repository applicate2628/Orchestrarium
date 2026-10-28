"""Claude installation preserves unowned stale namespace entries and instructions."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-claude.py"


def _run(target: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-B", str(INSTALLER), "--target", str(target),
         "--allow-unsafe-target", *extra],
        cwd=ROOT, text=True, capture_output=True,
    )


class NamespaceReclaimTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="claude-preserve-test-")
        self.addCleanup(self.temporary.cleanup)
        self.tmp = Path(self.temporary.name)
        c = self.tmp / ".claude"
        (c / "commands").mkdir(parents=True)
        (c / "skills" / "agents-stale-flow").mkdir(parents=True)
        (c / "skills" / "my-custom-skill").mkdir(parents=True)
        (c / "agents").mkdir(parents=True)
        # A namespace prefix does not establish stock ownership.
        (c / "commands" / "agents-oldflow.md").write_bytes(b"stale command\n")
        (c / "skills" / "agents-stale-flow" / "SKILL.md").write_bytes(b"stale skill\n")
        # genuine user files (must be preserved)
        (c / "commands" / "my-own-command.md").write_text("user command\n")
        (c / "skills" / "my-custom-skill" / "SKILL.md").write_text("user skill\n")
        self.agent_custom = b"---\nname: custom\nextra: retained\n---\nuser agent body\n"
        self.command_custom = b"---\nname: command\n---\nuser command body\n"
        (c / "agents" / "analyst.md").write_bytes(self.agent_custom)
        (c / "commands" / "agents-bugfix.md").write_bytes(self.command_custom)
        self.c = c

    def test_dry_run_reports_but_mutates_nothing(self) -> None:
        r = _run(self.tmp, "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Preserved unowned stale instruction; not removed: commands/agents-oldflow.md", r.stdout)
        self.assertIn("Preserved unowned stale instruction; not removed: skills/agents-stale-flow", r.stdout)
        # nothing removed
        self.assertTrue((self.c / "commands" / "agents-oldflow.md").exists())
        self.assertTrue((self.c / "skills" / "agents-stale-flow").exists())

    def test_real_install_and_rerun_preserve_user(self) -> None:
        r = _run(self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(b"stale command\n", (self.c / "commands" / "agents-oldflow.md").read_bytes())
        self.assertEqual(b"stale skill\n", (self.c / "skills" / "agents-stale-flow" / "SKILL.md").read_bytes())
        # genuine user files preserved
        self.assertTrue((self.c / "commands" / "my-own-command.md").exists(),
                        "non-namespaced user command must be preserved")
        self.assertTrue((self.c / "skills" / "my-custom-skill").exists(),
                        "non-namespaced user skill must be preserved")
        self.assertIn("Preserved custom instruction; not updated", r.stdout)
        self.assertEqual(self.agent_custom, (self.c / "agents" / "analyst.md").read_bytes())
        self.assertEqual(self.command_custom, (self.c / "commands" / "agents-bugfix.md").read_bytes())
        self.assertTrue((self.c / "commands" / "agents-design.md").is_file())
        again = _run(self.tmp)
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual(self.agent_custom, (self.c / "agents" / "analyst.md").read_bytes())
        self.assertEqual(self.command_custom, (self.c / "commands" / "agents-bugfix.md").read_bytes())


if __name__ == "__main__":
    unittest.main()
