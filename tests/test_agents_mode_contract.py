import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from shutil import copy2


class AgentsModeContractTest(unittest.TestCase):
    def test_shared_contract_validator_passes(self) -> None:
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                str(root / "scripts" / "validate-agents-mode-contract.py"),
                "--root",
                str(root),
            ],
            cwd=root,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS: agents-mode contract validated", result.stdout)

    def test_validator_rejects_init_canonical_shape_drift(self) -> None:
        root = Path(__file__).resolve().parents[1]

        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            files = [
                "shared/agents-mode.schema.json",
                "shared/agents-mode.presets.json",
                "shared/agents-mode.defaults.yaml",
                "docs/agents-mode-reference.md",
                "src.codex/skills/init-project/SKILL.md",
                "src.claude/commands/agents-init-project.md",
                "src.gemini/skills/init-project/SKILL.md",
                "src.qwen/skills/init-project/SKILL.md",
                "scripts/sync-agents-mode-docs.py",
            ]
            for relative in files:
                target = tmp_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                copy2(root / relative, target)

            codex_init = tmp_root / "src.codex" / "skills" / "init-project" / "SKILL.md"
            text = codex_init.read_text(encoding="utf-8")
            text = text.replace(
                "   externalClaudeProfile: {value}  # allowed: sonnet-high | opus-max; default: opus-max",
                "   externalCodexProfile: {value}  # invalid drift from Codex-only scalar",
                1,
            )
            codex_init.write_text(text, encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(root / "scripts" / "validate-agents-mode-contract.py"),
                    "--root",
                    str(tmp_root),
                ],
                cwd=root,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("src.codex", result.stderr)


if __name__ == "__main__":
    unittest.main()
