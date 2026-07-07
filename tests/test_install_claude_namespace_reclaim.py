"""install-claude.sh reclaims the reserved `agents-` pack namespace on reinstall.

Gap 2 of work-items/bugs/2026-07-07-installer-gaps-...: the monorepo installer
previously PRESERVED any non-pack target file forever, so a renamed/removed
pack-owned command or a stale generated `agents-*` skill (left by an old
standalone-branch install — the monorepo path ships flows only as `commands/`,
never as generated skills) survived every upgrade. The fix reclaims the reserved
`agents-` namespace: a target `commands/agents-*.md` or `skills/agents-*/` dir
not in the current pack is removed; NON-namespaced user files are preserved.

The prefix IS the ownership marker (every agents-* command/flow ships under it — the
common skills in skills/ are role-named, not agents-*-prefixed), so there is no manifest.
"""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-claude.sh"


def _bash() -> str:
    """Resolve a bash that can see Windows drive paths. On Windows,
    `subprocess(["bash", ...])` may pick the System32 WSL bash, which cannot
    see `D:/...` paths (returncode 127); `shutil.which` finds the Git Bash on
    PATH instead. On Linux this is just /bin/bash."""
    found = shutil.which("bash")
    if found and "System32" not in found:
        return found
    for cand in (r"C:\Program Files\Git\bin\bash.exe",
                 r"C:\Program Files\Git\usr\bin\bash.exe"):
        if Path(cand).exists():
            return cand
    return found or "bash"


BASH = _bash()


def _run(target: Path, *extra: str) -> subprocess.CompletedProcess:
    # bash needs forward-slash paths — a Windows backslash path is mangled as
    # escape sequences (returncode 127).
    return subprocess.run(
        [BASH, INSTALLER.as_posix(), "--target", target.as_posix(),
         "--allow-unsafe-target", *extra],
        cwd=ROOT, text=True, capture_output=True,
    )


class NamespaceReclaimTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = ROOT / ".scratch" / "test-namespace-reclaim"
        if self.tmp.exists():
            shutil.rmtree(self.tmp)
        c = self.tmp / ".claude"
        (c / "commands").mkdir(parents=True)
        (c / "skills" / "agents-stale-flow").mkdir(parents=True)
        (c / "skills" / "my-custom-skill").mkdir(parents=True)
        (c / "agents").mkdir(parents=True)
        # stale pack-namespace artifacts (should be reclaimed)
        (c / "commands" / "agents-oldflow.md").write_text("stale command\n")
        (c / "skills" / "agents-stale-flow" / "SKILL.md").write_text("stale skill\n")
        # genuine user files (must be preserved)
        (c / "commands" / "my-own-command.md").write_text("user command\n")
        (c / "skills" / "my-custom-skill" / "SKILL.md").write_text("user skill\n")
        self.c = c

    def tearDown(self) -> None:
        if self.tmp.exists():
            shutil.rmtree(self.tmp)

    def test_dry_run_reports_but_mutates_nothing(self) -> None:
        r = _run(self.tmp, "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("would reclaim stale pack namespace: commands/agents-oldflow.md", r.stdout)
        self.assertIn("would reclaim stale pack namespace: skills/agents-stale-flow", r.stdout)
        # nothing removed
        self.assertTrue((self.c / "commands" / "agents-oldflow.md").exists())
        self.assertTrue((self.c / "skills" / "agents-stale-flow").exists())

    def test_real_install_reclaims_stale_preserves_user(self) -> None:
        r = _run(self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # stale pack-namespace artifacts gone
        self.assertFalse((self.c / "commands" / "agents-oldflow.md").exists(),
                         "stale agents- command should be reclaimed")
        self.assertFalse((self.c / "skills" / "agents-stale-flow").exists(),
                         "stale agents- skill dir should be reclaimed")
        # genuine user files preserved
        self.assertTrue((self.c / "commands" / "my-own-command.md").exists(),
                        "non-namespaced user command must be preserved")
        self.assertTrue((self.c / "skills" / "my-custom-skill").exists(),
                        "non-namespaced user skill must be preserved")
        # current pack flows are present (installer copied them)
        self.assertTrue((self.c / "commands" / "agents-bugfix.md").exists())


if __name__ == "__main__":
    unittest.main()
