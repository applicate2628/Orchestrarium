#!/usr/bin/env python3
"""Tests for the Stage 0 target-effect baseline generator."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "baseline" / "build_target_effect_baseline.py"


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def inventory_payload() -> dict[str, object]:
    entries = [
        {
            "path": "AGENTS.md",
            "sizeBytes": 10,
            "contentSha256": "a" * 64,
            "surfaces": ["documentation", "governance"],
        },
        {
            "path": "shared/AGENTS.shared.md",
            "sizeBytes": 15,
            "contentSha256": "f" * 64,
            "surfaces": ["documentation", "governance", "shared-source"],
        },
        {
            "path": "shared/agents-mode.schema.json",
            "sizeBytes": 20,
            "contentSha256": "b" * 64,
            "surfaces": ["configuration", "shared-source"],
        },
        {
            "path": "shared/references/cross-pack-reconciliation.md",
            "sizeBytes": 30,
            "contentSha256": "c" * 64,
            "surfaces": ["documentation", "shared-source"],
        },
        {
            "path": "src.codex/skills/architect/SKILL.md",
            "sizeBytes": 40,
            "contentSha256": "d" * 64,
            "surfaces": ["provider-pack", "provider:codex", "skill"],
        },
        {
            "path": "src.claude/skills/architect/SKILL.md",
            "sizeBytes": 40,
            "contentSha256": "d" * 64,
            "surfaces": ["provider-pack", "provider:claude", "skill"],
        },
        {
            "path": "src.qwen/QWEN.md",
            "sizeBytes": 25,
            "contentSha256": "8" * 64,
            "surfaces": ["documentation", "provider-pack", "provider:qwen"],
        },
        {
            "path": "tests/test_alpha.py",
            "sizeBytes": 50,
            "contentSha256": "e" * 64,
            "surfaces": ["script", "test"],
        },
        {
            "path": "tests/test_registry_governance_reconciliation_contract.py",
            "sizeBytes": 60,
            "contentSha256": "9" * 64,
            "surfaces": ["script", "test"],
        },
    ]
    payload: dict[str, object] = {
        "schemaVersion": 1,
        "baseline": {
            "commitSha": "1" * 40,
            "repository": "example/orche",
            "requestedRef": "baseline",
            "treeSha": "2" * 40,
        },
        "entries": entries,
        "summary": {"trackedLeafEntries": len(entries), "surfaceCounts": {}},
    }
    payload["inventorySha256"] = hashlib.sha256(
        canonical_json(payload).encode("utf-8")
    ).hexdigest()
    return payload


class TargetEffectBaselineTests(unittest.TestCase):
    def run_script(
        self, inventory: Path, output: Path, *extra: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--inventory",
                str(inventory),
                "--output",
                str(output),
                *extra,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_measures_repository_shape_and_keeps_runtime_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inventory = root / "capability.json"
            output = root / "target.json"
            inventory.write_text(canonical_json(inventory_payload()), encoding="utf-8")
            result = self.run_script(inventory, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))

            self.assertEqual(payload["repositoryShape"]["trackedLeafEntries"], 9)
            self.assertEqual(payload["repositoryShape"]["trackedBytes"], 290)
            self.assertEqual(payload["repositoryShape"]["providerPackCount"], 3)
            self.assertEqual(
                payload["repositoryShape"]["skillBodies"],
                {
                    "bytes": 80,
                    "duplicateBodiesByDigest": 1,
                    "total": 2,
                    "uniqueContentDigests": 1,
                },
            )
            self.assertEqual(
                [
                    item["path"]
                    for item in payload["repositoryShape"]["instructionEntrypoints"]
                ],
                ["AGENTS.md", "shared/AGENTS.shared.md", "src.qwen/QWEN.md"],
            )
            self.assertEqual(
                payload["repositoryShape"]["legacySettingsStack"]["paths"],
                ["shared/agents-mode.schema.json"],
            )
            self.assertEqual(
                payload["repositoryShape"]["manualReconciliationArtifacts"]["paths"],
                ["shared/references/cross-pack-reconciliation.md"],
            )
            self.assertIsNone(
                payload["runtimeMeasurements"]["alwaysLoadedPromptTokens"]
            )
            self.assertEqual(
                payload["runtimeMeasurements"]["status"],
                "MEASUREMENT_PENDING_RUNTIME_INSTRUMENTATION",
            )

    def test_rejects_valid_json_when_declared_semantic_digest_no_longer_matches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inventory = root / "capability.json"
            output = root / "target.json"
            payload = inventory_payload()
            entries = payload["entries"]
            assert isinstance(entries, list)
            assert isinstance(entries[0], dict)
            entries[0]["sizeBytes"] = 11
            inventory.write_text(canonical_json(payload), encoding="utf-8")

            result = self.run_script(inventory, output)

            self.assertEqual(result.returncode, 2)
            self.assertIn("inventorySha256 mismatch", result.stderr)
            self.assertFalse(output.exists())

    def test_rejects_valid_json_with_non_object_top_level_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inventory = root / "capability.json"
            output = root / "target.json"
            inventory.write_text("[]\n", encoding="utf-8")

            result = self.run_script(inventory, output)

            self.assertEqual(result.returncode, 2)
            self.assertIn("top level must be an object", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(output.exists())

    def test_output_is_deterministic_and_check_detects_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inventory = root / "capability.json"
            output = root / "target.json"
            inventory.write_text(canonical_json(inventory_payload()), encoding="utf-8")
            first = self.run_script(inventory, output)
            self.assertEqual(first.returncode, 0, first.stderr)
            first_bytes = output.read_bytes()
            second = self.run_script(inventory, output)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(first_bytes, output.read_bytes())

            checked = self.run_script(inventory, output, "--check")
            self.assertEqual(checked.returncode, 0, checked.stderr)
            output.write_text("{}\n", encoding="utf-8")
            drift = self.run_script(inventory, output, "--check")
            self.assertEqual(drift.returncode, 1)
            self.assertIn("DRIFT", drift.stderr)


if __name__ == "__main__":
    unittest.main()
