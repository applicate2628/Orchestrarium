import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from shutil import copy2

from _module_loading_support import load_module


ROOT = Path(__file__).resolve().parents[1]
SYNC = load_module(ROOT / "scripts/sync-agents-mode-docs.py", "agents_mode_docs_sync")
CONTRACT_SURFACES = (
    "shared/agents-mode.schema.json",
    "shared/agents-mode.presets.json",
    SYNC.REFERENCE_DOC,
    *SYNC.INIT_SURFACES.values(),
)


class AgentsModeDocsSyncTest(unittest.TestCase):
    def test_docs_sync_check_passes(self) -> None:
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                str(root / "scripts" / "sync-agents-mode-docs.py"),
                "--root",
                str(root),
                "--check",
            ],
            cwd=root,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS: agents-mode docs are synced", result.stdout)

    def test_docs_sync_write_repairs_generated_surfaces(self) -> None:
        root = Path(__file__).resolve().parents[1]

        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            for relative in CONTRACT_SURFACES:
                target = tmp_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                copy2(root / relative, target)

            reference = tmp_root / SYNC.REFERENCE_DOC
            reference.write_text(
                reference.read_text(encoding="utf-8").replace(
                    "| `power-mode` | hardest-task maximum result |",
                    "| `power-mode` | stale role |",
                    1,
                ),
                encoding="utf-8",
            )
            codex_init = tmp_root / SYNC.INIT_SURFACES["codex"]
            codex_init.write_text(
                codex_init.read_text(encoding="utf-8").replace(
                    "consultantMode: {value}",
                    "externalProvider: {value}",
                    1,
                ),
                encoding="utf-8",
            )

            check_before = subprocess.run(
                [
                    sys.executable,
                    str(root / "scripts" / "sync-agents-mode-docs.py"),
                    "--root",
                    str(tmp_root),
                    "--check",
                ],
                cwd=root,
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(check_before.returncode, 0)

            write_result = subprocess.run(
                [
                    sys.executable,
                    str(root / "scripts" / "sync-agents-mode-docs.py"),
                    "--root",
                    str(tmp_root),
                    "--write",
                ],
                cwd=root,
                text=True,
                capture_output=True,
            )
            self.assertEqual(write_result.returncode, 0, write_result.stdout + write_result.stderr)

            check_after = subprocess.run(
                [
                    sys.executable,
                    str(root / "scripts" / "sync-agents-mode-docs.py"),
                    "--root",
                    str(tmp_root),
                    "--check",
                ],
                cwd=root,
                text=True,
                capture_output=True,
            )
            self.assertEqual(check_after.returncode, 0, check_after.stdout + check_after.stderr)


if __name__ == "__main__":
    unittest.main()
