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
        self.assertEqual(codex_profile["default"], "gpt-6.2-sol-xhigh")
        # Only current GPT-6.2 Sol profiles belong to this external Codex enum.
        # Native task/profile selection and its other model families are separate.
        self.assertEqual(
            codex_profile["allowed"],
            [
                "default",
                "gpt-6.2-sol-high",
                "gpt-6.2-sol-xhigh",
                "gpt-6.2-sol-max",
            ],
        )
        self.assertNotIn("providers", codex_profile)

        # Per-preset assignments must correspond to each preset's intent:
        #   best-effort presets → gpt-6.2-sol-xhigh
        #   speed preset → gpt-6.2-sol-high
        #   balanced everyday presets → default (inherit externalModelMode)
        expected_per_preset = {
            "default": "gpt-6.2-sol-xhigh",
            "absolute-balance": "default",
            "external-aggressive": "default",
            "correctness-first": "gpt-6.2-sol-xhigh",
            "power-mode": "gpt-6.2-sol-xhigh",
            "max-speed": "gpt-6.2-sol-high",
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
        reference = (root / "docs/agents-mode-reference.md").read_text(encoding="utf-8")
        provider_rows = reference.split("## Provider surfaces", 1)[1].split("## ", 1)[0]
        maintenance = reference.split("## Canonical maintenance", 1)[1].split("## ", 1)[0]
        first_write = reference.split("## First-write defaults", 1)[1].split("## ", 1)[0]
        for provider, label, directory, overlay, initializer in (
            ("codex", "Codex", ".agents", "src.codex/AGENTS.codex.md", "src.codex/skills/init-project/SKILL.md"),
            ("claude", "Claude Code", ".claude", "adapters/claude/CLAUDE.md", "adapters/claude/commands/agents-init-project.md"),
        ):
            row = next(line for line in provider_rows.splitlines() if line.startswith(f"| {label} |"))
            init = (root / initializer).read_text(encoding="utf-8")
            init_read = next(line for line in init.splitlines() if line.startswith("- For decision-driving reads,"))
            overlay_lines = (root / overlay).read_text(encoding="utf-8").splitlines()
            overlay_read = next(line for line in overlay_lines if "shared cross-pack global" in line)
            layers = (
                f"`{directory}/.agents-mode.yaml`",
                f"`{directory}/.agents-mode`",
                f"`~/.{provider}/.agents-mode.yaml`",
                f"`~/.{provider}/.agents-mode`",
                "`~/.agents-mode.yaml`",
            )
            for owner, clause in (("provider reference", row.split("Decision-driving reads", 1)[1]),
                                  (overlay, overlay_read), (initializer, init_read)):
                with self.subTest(provider=provider, owner=owner):
                    self.assertTrue(all(layer in clause for layer in layers))
                    order = [clause.index(layer) for layer in layers]
                    self.assertEqual(order, sorted(order))
            with self.subTest(provider=provider, owner="first write"):
                self.assertIn("externalCodexProfile: gpt-6.2-sol-xhigh", init)
                default_row = next(line for line in first_write.splitlines() if line.startswith(f"| {label} |"))
                self.assertIn("`runtime-default` | `gpt-6.2-sol-xhigh`", default_row)
            with self.subTest(provider=provider, owner="read-only policy"):
                self.assertIn("[Canonical maintenance](#canonical-maintenance)", row)
                self.assertIn("inspection grants no write", init_read)
                self.assertNotIn("must be normalized forward", row)
        self.assertIn("Use `scripts/resolve-agents-mode.py --provider <provider> --json`", maintenance)
        self.assertIn("normalize the effective values in memory", maintenance)
        self.assertIn("must not create or modify an overlay", maintenance)
        self.assertIn("reinstall must rewrite it to the current canonical form", maintenance)
        self.assertIn("Only the authorized writer", maintenance)
        for obsolete in ("Normalize whichever file supplied", "This maintenance rewrite happens on read",
                         "Read-time normalization preserves"):
            self.assertNotIn(obsolete, maintenance)

    def test_claude_initializer_documents_order_without_authorizing_read_writes(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / 'adapters/claude/commands/agents-init-project.md').read_text(encoding="utf-8")
        rule = next(line for line in text.splitlines() if line.startswith("- For decision-driving reads,"))
        layers = (
            "`.claude/.agents-mode.yaml`", "`.claude/.agents-mode`",
            "`~/.claude/.agents-mode.yaml`", "`~/.claude/.agents-mode`",
            "`~/.agents-mode.yaml`", "built-in defaults",
        )
        positions = [rule.index(layer) for layer in layers]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("inspection grants no write to the source overlay", rule)
        self.assertIn("explicitly selected authorized project configuration", rule)

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
                "adapters/claude/commands/agents-init-project.md",
                "scripts/sync-agents-mode-docs.py",
            ]
            for relative in files:
                target = tmp_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                copy2(root / relative, target)

            codex_init = tmp_root / "src.codex" / "skills" / "init-project" / "SKILL.md"
            text = codex_init.read_text(encoding="utf-8")
            text = text.replace(
                "   externalClaudeProfile: {value}  # allowed: sonnet-high | opus-xhigh | opus-max | fable-xhigh; default: opus-xhigh",
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
