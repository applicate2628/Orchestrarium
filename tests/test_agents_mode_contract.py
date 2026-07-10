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

        # Shipped default is the best-effort profile (symmetric to externalClaudeProfile: opus-xhigh).
        self.assertEqual(codex_profile["default"], "gpt-5.6-sol-xhigh")
        # gpt-5.5 -> gpt-5.6-sol/luna migration: gpt-5.5-fast and gpt-5.3-codex-spark
        # were both retired in favor of the single gpt-5.6-luna fast/volume tier, and
        # gpt-5.6-sol-max was added for higher-complexity/hard lanes. Keep this list in
        # sync with shared/agents-mode.schema.json externalCodexProfile.allowed.
        self.assertEqual(
            codex_profile["allowed"],
            ["default", "gpt-5.6-sol-xhigh", "gpt-5.6-sol-max", "gpt-5.6-luna"],
        )
        self.assertNotIn("providers", codex_profile)

        # Per-preset assignments must correspond to each preset's intent:
        #   best-effort presets → gpt-5.6-sol-xhigh
        #   speed preset → gpt-5.6-luna
        #   balanced everyday presets → default (inherit externalModelMode)
        expected_per_preset = {
            "default": "gpt-5.6-sol-xhigh",
            "absolute-balance": "default",
            "external-aggressive": "default",
            "correctness-first": "gpt-5.6-sol-xhigh",
            "power-mode": "gpt-5.6-sol-xhigh",
            "max-speed": "gpt-5.6-luna",
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

    def test_runtime_docs_include_full_read_order(self) -> None:
        root = Path(__file__).resolve().parents[1]
        expectations = {
            "src.codex/AGENTS.codex.md": [
                "local legacy `.agents/.agents-mode`",
                "pack-local global legacy `~/.codex/.agents-mode`",
                "shared cross-pack global `~/.agents-mode.yaml`",
            ],
            "src.claude/CLAUDE.md": [
                "local legacy `.claude/.agents-mode`",
                "pack-local global legacy `~/.claude/.agents-mode`",
                "shared cross-pack global `~/.agents-mode.yaml`",
            ],
            "src.codex/skills/init-project/SKILL.md": [
                "global legacy `~/.codex/.agents-mode`, then the shared cross-pack global",
                "externalCodexProfile: gpt-5.6-sol-xhigh",
            ],
            "src.claude/commands/agents-init-project.md": [
                "global legacy `~/.claude/.agents-mode`, then the shared cross-pack global",
                "externalCodexProfile: gpt-5.6-sol-xhigh",
            ],
            "docs/agents-mode-reference.md": [
                "Use `scripts/resolve-agents-mode.py --provider <provider> --json`",
                "| Codex | `disabled` | `auto` | `auto` | `auto` | `false` | `false` | `auto` | `claude-sonnet` | `neutral` | `neutral` | `runtime-default` | `gpt-5.6-sol-xhigh`",
                "| Claude Code | `disabled` | `auto` | `auto` | `auto` | `false` | `false` | `auto` | `claude-sonnet` | `neutral` | `neutral` | `runtime-default` | `gpt-5.6-sol-xhigh`",
            ],
        }
        for relative, snippets in expectations.items():
            text = (root / relative).read_text(encoding="utf-8")
            for snippet in snippets:
                with self.subTest(relative=relative, snippet=snippet):
                    self.assertIn(snippet, text)

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
                "   externalClaudeProfile: {value}  # allowed: sonnet-high | opus-xhigh | opus-max; default: opus-xhigh",
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
