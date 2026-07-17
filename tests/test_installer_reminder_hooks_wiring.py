"""Installer wiring for `turn-anchor-reminder` (UserPromptSubmit) and
`check-mcp-momentum` (PreToolUse, AUDIT).

MAJOR (strong-model audit): both hooks ship byte-identically into the canon
(`scripts/universal-hooks/{scripts,hooks}/`) and both production packs
(`src.claude/agents/`, `src.codex/skills/lead/`), and both are exercised by
`tests/test_universal_reminder_hooks.py` -- but no installer registered either
one into `settings.json` (Claude) or `hooks.json` (Codex), so a fresh install
never actually wired them up. This mirrors the pattern in
`test_installer_sessionstart_hooks.py`: static wiring is enforced here because
per-platform installer wiring has no single owner (each installer hand-writes
its own hook-install block) and nothing else would catch a platform silently
lagging.

`turn-anchor-reminder` fires at TURN START (its failure moment is the turn
boundary, not the tool choice) -> UserPromptSubmit.
`check-mcp-momentum` fires at the TOOL CHOICE (its failure moment is mid-turn
momentum overriding a rule sitting in context) -> PreToolUse, matched on
Grep|Bash (the only tool_name shapes its own code-navigation detector
recognizes).
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


def _logical_lines(text: str) -> list[str]:
    """Join POSIX-shell backslash line-continuations so each install invocation
    becomes one logical line. PowerShell invocations are already single-line, so
    this is a no-op there. Then flatten remaining whitespace per line."""
    joined = re.sub(r"\\\s*\n\s*", " ", text)
    return [re.sub(r"\s+", " ", ln).strip() for ln in joined.splitlines()]


class InstallerReminderHooksWiringTest(unittest.TestCase):
    def test_all_four_installers_wire_turn_anchor_reminder_on_userpromptsubmit(self) -> None:
        for installer in INSTALLERS:
            self.assertTrue(installer.is_file(), f"missing installer {installer}")
            lines = _logical_lines(installer.read_text(encoding="utf-8"))
            wired = any(
                "--hook-event UserPromptSubmit" in ln
                and "--script-marker turn-anchor-reminder" in ln
                for ln in lines
            )
            self.assertTrue(
                wired,
                f"{installer.name} does not wire turn-anchor-reminder on "
                f"UserPromptSubmit (needs an install-hypothesis-hook invocation "
                f"pairing --hook-event UserPromptSubmit with "
                f"--script-marker turn-anchor-reminder)",
            )

    def test_all_four_installers_wire_check_mcp_momentum_on_pretooluse(self) -> None:
        for installer in INSTALLERS:
            self.assertTrue(installer.is_file(), f"missing installer {installer}")
            lines = _logical_lines(installer.read_text(encoding="utf-8"))
            wired = any(
                "--script-marker check-mcp-momentum" in ln
                and '--tool-matcher "Grep|Bash"' in ln
                # PreToolUse is the install-hypothesis-hook default hook-event
                # (no --hook-event flag needed), unlike the Stop/SessionStart/
                # UserPromptSubmit entries which must name their event explicitly.
                and "--hook-event" not in ln
                for ln in lines
            )
            self.assertTrue(
                wired,
                f"{installer.name} does not wire check-mcp-momentum on PreToolUse "
                f"with tool-matcher Grep|Bash",
            )


if __name__ == "__main__":
    unittest.main()
