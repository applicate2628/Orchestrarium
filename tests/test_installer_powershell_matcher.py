"""Installer wiring contract: PowerShell is a matched tool for the Windows
shell-command-sensitive PreToolUse audit/gate hooks.

BLOCKER (strong-model audit): the `--tool-matcher` regexes for
`check-no-trash-in-repo`, `check-git-push-gate`, and `check-repository-orientation`
omitted `PowerShell` -- this Windows operator's PRIMARY shell -- so a `git
worktree add` or `git push` run via the PowerShell tool never reached these
hooks; only a `Bash` tool call did. `check-repository-orientation` already had
its own installer-wiring test (test_installer_repository_orientation_hook.py);
this file covers the other two hooks, which had no installer-wiring test at
all, plus a combined assertion that all three now include PowerShell in all
four production installers.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLERS = (
    ROOT / "scripts" / "install-claude.sh",
    ROOT / "scripts" / "install-claude.ps1",
    ROOT / "scripts" / "install-codex.sh",
    ROOT / "scripts" / "install-codex.ps1",
)

# marker -> exact matcher string every installer must register it with.
EXPECTED_MATCHERS = {
    "check-no-trash-in-repo": "Edit|Write|NotebookEdit|apply_patch|Bash|PowerShell",
    "check-git-push-gate": "Bash|PowerShell",
    "check-repository-orientation": "Edit|Write|NotebookEdit|apply_patch|Bash|PowerShell|shell_command|exec_command",
}


def logical_lines(text: str) -> list[str]:
    joined = re.sub(r"\\\s*\n\s*", " ", text)
    return [re.sub(r"\s+", " ", line).strip() for line in joined.splitlines()]


class InstallerPowerShellMatcherTest(unittest.TestCase):
    def test_all_four_installers_include_powershell_for_shell_sensitive_hooks(self) -> None:
        for installer in INSTALLERS:
            self.assertTrue(installer.is_file(), f"missing installer {installer}")
            lines = logical_lines(installer.read_text(encoding="utf-8"))
            for marker, matcher in EXPECTED_MATCHERS.items():
                with self.subTest(installer=installer.name, marker=marker):
                    wired = any(
                        f"--script-marker {marker}" in line and f'--tool-matcher "{matcher}"' in line
                        for line in lines
                    )
                    self.assertTrue(
                        wired,
                        f"{installer.name} does not register {marker} with "
                        f"tool-matcher including PowerShell (expected {matcher!r})",
                    )


if __name__ == "__main__":
    unittest.main()
