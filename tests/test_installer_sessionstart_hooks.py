"""Both SessionStart reminder hooks must be wired in ALL FOUR installers.

Codex fix-coherence review of the delegation-posture hook caught the exact
failure this guards against: `install-codex.ps1` declared the
`agents-mode-reminder` target-path variable but never emitted the
`install-hypothesis-hook.py … --hook-event SessionStart --script-marker
agents-mode-reminder` invocation, so `install-codex.ps1 -Global` would have
shipped only `mcp-usage-reminder` while the other three installers shipped both.
Per-platform installer wiring has no single owner (each installer hand-writes its
own hook-install block), so the invariant is enforced here: every installer must
register BOTH SessionStart markers, and neither platform can silently lag again.

Two layers:
  1. Static wiring — each of the four installer scripts contains, for BOTH
     `mcp-usage-reminder` and `agents-mode-reminder`, an install-hypothesis-hook
     invocation pairing `--hook-event SessionStart` with that `--script-marker`.
  2. Functional idempotency — installing the `agents-mode-reminder` SessionStart
     entry twice yields exactly one entry (the marker-based merge is idempotent,
     same as the other SessionStart entry).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK_INSTALLER = ROOT / "scripts" / "install-hypothesis-hook.py"

INSTALLERS = (
    ROOT / "scripts" / "install-claude.sh",
    ROOT / "scripts" / "install-claude.ps1",
    ROOT / "scripts" / "install-codex.sh",
    ROOT / "scripts" / "install-codex.ps1",
)
SESSIONSTART_MARKERS = ("mcp-usage-reminder", "agents-mode-reminder")


def _logical_lines(text: str) -> list[str]:
    """Join POSIX-shell backslash line-continuations so each install invocation
    becomes one logical line. PowerShell invocations are already single-line, so
    this is a no-op there. Then flatten remaining whitespace per line."""
    joined = re.sub(r"\\\s*\n\s*", " ", text)
    return [re.sub(r"\s+", " ", ln).strip() for ln in joined.splitlines()]


class InstallerSessionStartWiringTest(unittest.TestCase):
    def test_all_four_installers_wire_both_sessionstart_markers(self) -> None:
        for installer in INSTALLERS:
            self.assertTrue(installer.is_file(), f"missing installer {installer}")
            lines = _logical_lines(installer.read_text(encoding="utf-8"))
            for marker in SESSIONSTART_MARKERS:
                wired = any(
                    "--hook-event SessionStart" in ln
                    and f"--script-marker {marker}" in ln
                    for ln in lines
                )
                self.assertTrue(
                    wired,
                    f"{installer.name} does not wire the SessionStart hook "
                    f"'{marker}' (needs an install-hypothesis-hook invocation "
                    f"pairing --hook-event SessionStart with "
                    f"--script-marker {marker})",
                )

    def test_agents_mode_reminder_install_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "settings.json"

            def install() -> subprocess.CompletedProcess:
                return subprocess.run(
                    [
                        sys.executable,
                        str(HOOK_INSTALLER),
                        "--target",
                        str(target),
                        "--platform",
                        "claude",
                        "--host-os",
                        "posix",
                        "--hook-event",
                        "SessionStart",
                        "--script-marker",
                        "agents-mode-reminder",
                        "--script-path",
                        "/tmp/agents-mode-reminder.sh",
                    ],
                    capture_output=True,
                    text=True,
                )

            first = install()
            self.assertEqual(first.returncode, 0, first.stderr)
            second = install()
            self.assertEqual(second.returncode, 0, second.stderr)

            data = json.loads(target.read_text(encoding="utf-8"))
            session_entries = data.get("hooks", {}).get("SessionStart", [])
            matching = [
                entry
                for entry in session_entries
                for hook in entry.get("hooks", [])
                if "agents-mode-reminder" in json.dumps(hook)
            ]
            self.assertEqual(
                len(matching),
                1,
                f"expected exactly one agents-mode-reminder SessionStart entry "
                f"after two installs, got {len(matching)}: {session_entries}",
            )


if __name__ == "__main__":
    unittest.main()
