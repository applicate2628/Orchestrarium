import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from shutil import copy2


class AgentsModeContractTest(unittest.TestCase):
    def test_power_mode_uses_quality_first_priority_profile(self) -> None:
        root = Path(__file__).resolve().parents[1]
        presets = json.loads(
            (root / "shared" / "agents-mode.presets.json").read_text(encoding="utf-8")
        )

        profile = presets["presets"]["power-mode"]["expansion"]["externalPriorityProfile"]

        self.assertEqual(profile, "quality-first")

    def test_codex_profile_per_preset_layout(self) -> None:
        root = Path(__file__).resolve().parents[1]
        schema = json.loads(
            (root / "shared" / "agents-mode.schema.json").read_text(encoding="utf-8")
        )
        presets = json.loads(
            (root / "shared" / "agents-mode.presets.json").read_text(encoding="utf-8")
        )

        scalars = {scalar["name"]: scalar for scalar in schema["scalarKeys"]}
        codex_profile = scalars["externalCodexProfile"]

        # Shipped default is the best-effort profile (symmetric to externalClaudeProfile: opus-max).
        self.assertEqual(codex_profile["default"], "gpt-5.5-xhigh")
        self.assertEqual(
            codex_profile["allowed"],
            ["default", "gpt-5.5-fast", "gpt-5.5-xhigh"],
        )
        self.assertNotIn("providers", codex_profile)

        # Per-preset assignments must correspond to each preset's intent:
        #   best-effort presets → gpt-5.5-xhigh
        #   speed preset → gpt-5.5-fast
        #   balanced everyday presets → default (inherit externalModelMode)
        expected_per_preset = {
            "default": "gpt-5.5-xhigh",
            "absolute-balance": "default",
            "external-aggressive": "default",
            "correctness-first": "gpt-5.5-xhigh",
            "power-mode": "gpt-5.5-xhigh",
            "max-speed": "gpt-5.5-fast",
        }
        for preset in presets["presetOrder"]:
            with self.subTest(preset=preset):
                expansion = presets["presets"][preset]["expansion"]
                self.assertEqual(
                    expansion["externalCodexProfile"],
                    expected_per_preset[preset],
                )

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
                "   externalFastProfile: {value}  # invalid drift from Codex-only scalar",
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
