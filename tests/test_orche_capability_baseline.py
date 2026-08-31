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
BASELINE_TREE = "c" * 40
CANDIDATE_TREE = "d" * 40
MANIFEST_PATH = "baseline/orchestrarium-v1/reviewed-dispositions.json"


def canonical(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def identity(value: str | tuple[str, str, str] | None):
    if value is None:
        return None
    if isinstance(value, tuple):
        git_object, mode, object_type = value
    else:
        git_object, mode, object_type = value, "100644", "blob"
    return {"gitObject": git_object, "mode": mode, "objectType": object_type}


def write_inventory(
    path: Path,
    ref: str,
    mapping: dict[str, str | tuple[str, str, str]],
    *,
    tree: str,
) -> None:
    entries = []
    for key, value in sorted(mapping.items()):
        record = identity(value)
        assert record is not None
        entries.append(
            {
                "path": key,
                "contentSha256": "f" * 64,
                "gitObject": record["gitObject"],
                "mode": record["mode"],
                "objectType": record["objectType"],
                "sizeBytes": 1,
                "surfaces": ["repository-content"],
            }
        )
    payload: dict[str, object] = {
        "schemaVersion": 2,
        "baseline": {
            "commitSha": ref,
            "repository": "x/y",
            "requestedRef": ref,
            "treeSha": tree,
        },
        "entries": entries,
        "summary": {"surfaceCounts": {}, "trackedLeafEntries": len(entries)},
    }
    payload["inventorySha256"] = hashlib.sha256(canonical(payload).encode()).hexdigest()
    path.write_text(canonical(payload), encoding="utf-8")


def write_dispositions(
    path: Path,
    entries: list[
        tuple[
            str,
            str,
            str | tuple[str, str, str] | None,
            str | tuple[str, str, str] | None,
        ]
    ],
    *,
    schema_version: int = 2,
    candidate_ref: str = B,
    candidate_tree: str = CANDIDATE_TREE,
) -> None:
    payload = {
        "schemaVersion": schema_version,
        "scope": "ORCHE-IMPL-000",
        "baselineRef": A,
        "baselineTree": BASELINE_TREE,
        "candidateRef": candidate_ref,
        "candidateTree": candidate_tree,
        "reviewEnvelope": {
            "kind": "manifest-only-child",
            "path": MANIFEST_PATH,
        },
        "entries": [
            {
                "path": item,
                "change": change,
                "reason": "reviewed",
                "contractIds": ["ORCHE-IMPL-000.TEST"],
                "expectedBaselineIdentity": identity(baseline_identity),
                "expectedCandidateIdentity": identity(candidate_identity),
            }
            for item, change, baseline_identity, candidate_identity in entries
        ],
    }
    path.write_text(canonical(payload), encoding="utf-8")


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
                sys.executable,
                str(SCRIPT),
                "--baseline-inventory",
                str(self.baseline),
                "--candidate-inventory",
                str(self.candidate),
                "--baseline-ref",
                A,
                "--candidate-ref",
                B,
                "--dispositions",
                str(self.dispositions),
                "--output",
                str(self.output),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def prepare(
        self,
        baseline_mapping: dict[str, str | tuple[str, str, str]],
        candidate_mapping: dict[str, str | tuple[str, str, str]],
    ) -> None:
        write_inventory(self.baseline, A, baseline_mapping, tree=BASELINE_TREE)
        write_inventory(self.candidate, B, candidate_mapping, tree="e" * 40)

    def test_all_changes_require_exact_reviewed_dispositions(self) -> None:
        self.prepare(
            {"same": "1" * 40, "changed": "2" * 40, "removed": "3" * 40},
            {"same": "1" * 40, "changed": "4" * 40, "added": "5" * 40},
        )
        write_dispositions(
            self.dispositions,
            [
                ("changed", "modified", "2" * 40, "4" * 40),
                ("removed", "removed", "3" * 40, None),
                ("added", "added", None, "5" * 40),
            ],
        )
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(self.output.read_text())
        self.assertEqual(report["verdict"], "PASS")
        self.assertEqual(report["candidateContentRef"], B)
        self.assertEqual(report["candidateContentTree"], CANDIDATE_TREE)

    def test_content_mode_and_object_type_are_all_capability_identity(self) -> None:
        cases = (
            (("1" * 40, "100644", "blob"), ("2" * 40, "100644", "blob")),
            (("1" * 40, "100644", "blob"), ("1" * 40, "100755", "blob")),
            (("1" * 40, "100644", "blob"), ("1" * 40, "120000", "blob")),
        )
        for baseline_record, candidate_record in cases:
            with self.subTest(candidate=candidate_record):
                self.prepare({"x": baseline_record}, {"x": candidate_record})
                write_dispositions(self.dispositions, [])
                result = self.invoke()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(
                    json.loads(self.output.read_text())["blockers"]["missingDispositions"],
                    ["x"],
                )

    def test_invalid_mode_object_type_combination_is_invalid_evidence(self) -> None:
        self.prepare({"x": ("1" * 40, "100644", "commit")}, {"x": "1" * 40})
        write_dispositions(self.dispositions, [])
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertIn("objectType", result.stderr)

    def test_unreviewed_change_blocks(self) -> None:
        self.prepare({"x": "1" * 40}, {"x": "2" * 40})
        write_dispositions(self.dispositions, [])
        result = self.invoke()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            json.loads(self.output.read_text())["blockers"]["missingDispositions"],
            ["x"],
        )

    def test_stale_or_wrong_disposition_blocks(self) -> None:
        self.prepare({"x": "1" * 40}, {"x": "1" * 40})
        write_dispositions(
            self.dispositions,
            [("x", "modified", "1" * 40, "1" * 40)],
        )
        self.assertEqual(self.invoke().returncode, 1)
        self.prepare({"x": "1" * 40}, {"x": "2" * 40})
        write_dispositions(
            self.dispositions,
            [("x", "added", "1" * 40, "2" * 40)],
        )
        self.assertEqual(self.invoke().returncode, 1)

    def test_stale_candidate_identity_blocks_even_when_change_category_matches(self) -> None:
        self.prepare({"x": "1" * 40}, {"x": "2" * 40})
        write_dispositions(
            self.dispositions,
            [("x", "modified", "1" * 40, "9" * 40)],
        )
        result = self.invoke()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(
            json.loads(self.output.read_text())["blockers"][
                "mismatchedDispositionIdentities"
            ],
            ["x"],
        )

    def test_schema_one_disposition_is_invalid_evidence(self) -> None:
        self.prepare({"x": "1" * 40}, {"x": "2" * 40})
        write_dispositions(
            self.dispositions,
            [("x", "modified", "1" * 40, "2" * 40)],
            schema_version=1,
        )
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertIn("schemaVersion 2", result.stderr)

    def test_manifest_path_is_owned_by_the_review_envelope(self) -> None:
        self.prepare(
            {"same": "1" * 40},
            {"same": "1" * 40, MANIFEST_PATH: "7" * 40},
        )
        write_dispositions(self.dispositions, [])
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.output.read_text())["verdict"], "PASS")

    def test_inventory_commit_binding_is_enforced(self) -> None:
        write_inventory(self.baseline, B, {"x": "1" * 40}, tree=BASELINE_TREE)
        write_inventory(self.candidate, B, {"x": "1" * 40}, tree="e" * 40)
        write_dispositions(self.dispositions, [])
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertIn("commit mismatch", result.stderr)


if __name__ == "__main__":
    unittest.main()
