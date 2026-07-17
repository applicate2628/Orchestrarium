"""Installer wiring contract for the repository-orientation audit hook."""

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
MATCHER = "Edit|Write|NotebookEdit|apply_patch|Bash|PowerShell|shell_command|exec_command"


def logical_lines(text: str) -> list[str]:
    joined = re.sub(r"\\\s*\n\s*", " ", text)
    return [re.sub(r"\s+", " ", line).strip() for line in joined.splitlines()]


class InstallerRepositoryOrientationHookTest(unittest.TestCase):
    def test_production_installers_register_warn_only_pretool_hook(self) -> None:
        for installer in INSTALLERS:
            lines = logical_lines(installer.read_text(encoding="utf-8"))
            with self.subTest(installer=installer.name):
                self.assertTrue(
                    any(
                        "--script-marker check-repository-orientation" in line
                        and f'--tool-matcher "{MATCHER}"' in line
                        for line in lines
                    ),
                    f"{installer.name} does not register check-repository-orientation with {MATCHER}",
                )


if __name__ == "__main__":
    unittest.main()
