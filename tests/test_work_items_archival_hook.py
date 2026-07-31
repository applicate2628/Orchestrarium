"""Retirement gate for the obsolete work-items archival Stop adapter."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATHS = (
    REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "check-work-items-archival-stop.py",
    REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "check-work-items-archival-stop.sh",
    REPO_ROOT / "src.claude" / "agents" / "scripts" / "check-work-items-archival-stop.py",
    REPO_ROOT / "src.claude" / "agents" / "scripts" / "check-work-items-archival-stop.sh",
    REPO_ROOT / "src.codex" / "skills" / "lead" / "scripts" / "check-work-items-archival-stop.py",
    REPO_ROOT / "src.codex" / "skills" / "lead" / "scripts" / "check-work-items-archival-stop.sh",
)


def _load_installer():
    path = REPO_ROOT / "scripts" / "production_installer.py"
    spec = importlib.util.spec_from_file_location("production_installer_archival_retirement", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestArchivalStopAdapterRetirement(unittest.TestCase):
    def test_adapter_and_wrapper_are_absent_from_all_shipped_trees(self) -> None:
        self.assertEqual(
            [path.relative_to(REPO_ROOT).as_posix() for path in ADAPTER_PATHS if path.exists()],
            [],
        )

    def test_production_registration_has_no_archival_stop_entry(self) -> None:
        installer = _load_installer()
        for provider, expected_count in (("codex", 12), ("claude", 13)):
            specs = installer._hook_specs(provider, REPO_ROOT / "unused")
            self.assertEqual(len(specs), expected_count)
            self.assertNotIn(
                "check-work-items-archival-stop",
                {marker for marker, *_rest in specs},
            )
        self.assertEqual(
            installer.RETIRED_HOOK_SPECS,
            (("check-work-items-archival-stop", "Stop"),),
        )

    def test_upgrade_reclaim_owns_only_exact_historical_adapter_bytes(self) -> None:
        installer = _load_installer()
        expected = {
            "py": "6fd48cbfb64e0861a5f8ad6c2c011fa6ae9dfd8567b1636dc2cf6b1ab18e11a1",
            "sh": "3c5dbc2499b6694859c71b2478e49f92b9fe45369d5287ea16463bacf6f84628",
        }
        for prefix, manifest in (
            ("skills/lead/scripts", installer._CODEX_RETIRED_PS1),
            ("agents/scripts", installer._CLAUDE_RETIRED_PS1),
        ):
            self.assertEqual(
                manifest[f"{prefix}/check-work-items-archival-stop.py"],
                expected["py"],
            )
            self.assertEqual(
                manifest[f"{prefix}/check-work-items-archival-stop.sh"],
                expected["sh"],
            )


if __name__ == "__main__":
    unittest.main()
