#!/usr/bin/env python3
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
NORMALIZATION = "utf8-strict+lf+leading-yaml-frontmatter-stripped-v1"


def canonical(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def write_inventory(path: Path, entries: list[dict[str, object]]) -> None:
    payload: dict[str, object] = {
        "schemaVersion": 2,
        "baseline": {"commitSha": "a" * 40, "repository": "x/y", "requestedRef": "a" * 40, "treeSha": "b" * 40},
        "entries": entries,
        "summary": {"surfaceCounts": {}, "trackedLeafEntries": len(entries)},
    }
    payload["inventorySha256"] = hashlib.sha256(canonical(payload).encode()).hexdigest()
    path.write_text(canonical(payload))


def entry(path: str, content: bytes, surfaces: list[str], body: bytes | None = None) -> dict[str, object]:
    record: dict[str, object] = {
        "path": path,
        "sizeBytes": len(content),
        "contentSha256": hashlib.sha256(content).hexdigest(),
        "surfaces": surfaces,
    }
    if body is not None:
        record.update({
            "skillBodyNormalization": NORMALIZATION,
            "skillBodySha256": hashlib.sha256(body).hexdigest(),
            "skillBodySizeBytes": len(body),
        })
    return record


class TargetEffectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.inventory = self.root / "inventory.json"
        self.output = self.root / "target.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def invoke(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--inventory", str(self.inventory), "--output", str(self.output), *extra],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )

    def test_duplicate_metrics_use_normalized_body_digest(self) -> None:
        body = b"# Same body\n"
        write_inventory(self.inventory, [
            entry("src.codex/skills/x/SKILL.md", b"frontmatter-a" + body, ["skill", "provider:codex"], body),
            entry("src.claude/skills/x/SKILL.md", b"frontmatter-b" + body, ["skill", "provider:claude"], body),
        ])
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        skills = json.loads(self.output.read_text())["repositoryShape"]["skillBodies"]
        self.assertEqual(skills["duplicateBodiesByDigest"], 1)
        self.assertEqual(skills["uniqueBodyDigests"], 1)
        self.assertEqual(skills["bytes"], len(body) * 2)

    def test_missing_body_contract_fails_closed(self) -> None:
        write_inventory(self.inventory, [entry("src.codex/skills/x/SKILL.md", b"x", ["skill"])])
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertIn("skillBodyNormalization", result.stderr)

    def test_semantic_digest_tampering_is_rejected(self) -> None:
        write_inventory(self.inventory, [entry("README.md", b"x", ["documentation"])])
        payload = json.loads(self.inventory.read_text())
        payload["entries"][0]["sizeBytes"] = 999
        self.inventory.write_text(canonical(payload))
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertIn("inventorySha256 mismatch", result.stderr)

    def test_check_mode_is_deterministic(self) -> None:
        write_inventory(self.inventory, [entry("README.md", b"x", ["documentation"])])
        self.assertEqual(self.invoke().returncode, 0)
        self.assertEqual(self.invoke("--check").returncode, 0)
        self.output.write_text("drift\n")
        self.assertEqual(self.invoke("--check").returncode, 1)


if __name__ == "__main__":
    unittest.main()
