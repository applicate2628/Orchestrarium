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
SCRIPT = ROOT / "scripts" / "baseline" / "compare_capability_baseline.py"
A = "a" * 40
B = "b" * 40


def canonical(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def write_inventory(path: Path, ref: str, mapping: dict[str, str]) -> None:
    entries = [
        {"path": key, "contentSha256": value, "sizeBytes": 1, "surfaces": ["repository-content"]}
        for key, value in sorted(mapping.items())
    ]
    payload: dict[str, object] = {
        "schemaVersion": 2,
        "baseline": {"commitSha": ref, "repository": "x/y", "requestedRef": ref, "treeSha": "c" * 40},
        "entries": entries,
        "summary": {"surfaceCounts": {}, "trackedLeafEntries": len(entries)},
    }
    payload["inventorySha256"] = hashlib.sha256(canonical(payload).encode()).hexdigest()
    path.write_text(canonical(payload))


def write_dispositions(path: Path, entries: list[tuple[str, str]]) -> None:
    payload = {
        "schemaVersion": 1,
        "scope": "ORCHE-IMPL-000",
        "baselineRef": A,
        "entries": [
            {"path": item, "change": change, "reason": "reviewed", "contractIds": ["ORCHE-IMPL-000.TEST"]}
            for item, change in entries
        ],
    }
    path.write_text(canonical(payload))


class CapabilityComparatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.baseline = self.root / "baseline.json"
        self.candidate = self.root / "candidate.json"
        self.dispositions = self.root / "dispositions.json"
        self.output = self.root / "report.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def invoke(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable, str(SCRIPT),
                "--baseline-inventory", str(self.baseline),
                "--candidate-inventory", str(self.candidate),
                "--baseline-ref", A,
                "--candidate-ref", B,
                "--dispositions", str(self.dispositions),
                "--output", str(self.output),
            ],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )

    def test_all_changes_require_exact_reviewed_dispositions(self) -> None:
        write_inventory(self.baseline, A, {"same": "1" * 64, "changed": "2" * 64, "removed": "3" * 64})
        write_inventory(self.candidate, B, {"same": "1" * 64, "changed": "4" * 64, "added": "5" * 64})
        write_dispositions(self.dispositions, [("changed", "modified"), ("removed", "removed"), ("added", "added")])
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.output.read_text())["verdict"], "PASS")

    def test_unreviewed_change_blocks(self) -> None:
        write_inventory(self.baseline, A, {"x": "1" * 64})
        write_inventory(self.candidate, B, {"x": "2" * 64})
        write_dispositions(self.dispositions, [])
        result = self.invoke()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(self.output.read_text())["blockers"]["missingDispositions"], ["x"])

    def test_stale_or_wrong_disposition_blocks(self) -> None:
        write_inventory(self.baseline, A, {"x": "1" * 64})
        write_inventory(self.candidate, B, {"x": "1" * 64})
        write_dispositions(self.dispositions, [("x", "modified")])
        self.assertEqual(self.invoke().returncode, 1)
        write_inventory(self.candidate, B, {"x": "2" * 64})
        write_dispositions(self.dispositions, [("x", "added")])
        self.assertEqual(self.invoke().returncode, 1)

    def test_inventory_commit_binding_is_enforced(self) -> None:
        write_inventory(self.baseline, B, {"x": "1" * 64})
        write_inventory(self.candidate, B, {"x": "1" * 64})
        write_dispositions(self.dispositions, [])
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertIn("commit mismatch", result.stderr)


if __name__ == "__main__":
    unittest.main()
