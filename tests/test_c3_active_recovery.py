#!/usr/bin/env python3
"""Synthetic active sealed-prefix C3 recovery tests."""

from __future__ import annotations

import os
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_ledger_h1_effective_view import (
    canonical,
    digest,
    load_validator,
    materialize_live_artifacts,
    synthetic_artifacts,
)


ROOT = Path(__file__).resolve().parents[1]
WRITER = ROOT / "scripts" / "agent-run-ledger.py"
CHECKER = ROOT / "scripts" / "check-work-items-state.py"


def load_checker():
    spec = __import__("importlib.util").util.spec_from_file_location(
        "c3_work_item_checker", CHECKER
    )
    assert spec and spec.loader
    module = __import__("importlib.util").util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def status_text() -> str:
    return """# Status

## Current state
**Primary task status**: open

## Active agents
- none

## Completed agents
- none

## Next action
Continue.
"""


def event_body(ledger_bytes: bytes, run_id: str) -> bytes:
    return canonical(
        next(
            row
            for row in (json.loads(line) for line in ledger_bytes.splitlines())
            if row.get("runId") == run_id
        )
    )


def recovery_command(item: Path, target_digest: str) -> list[str]:
    return [
        sys.executable,
        "-B",
        str(WRITER),
        "--work-item",
        str(item),
        "recover-invalid-closure",
        "--run-id",
        "recover-bad-closer-a1",
        "--target-run-id",
        "bad-closer-a1",
        "--target-event-sha256",
        target_digest,
        "--evidence",
        f"manual-check:bad-closer-a1 {target_digest}",
        "--started-at",
        "2026-09-09T00:00:00Z",
        "--updated-at",
        "2026-09-09T00:00:00Z",
    ]


class ActiveC3RecoveryTests(unittest.TestCase):
    def test_fresh_cli_candidate_invalidates_exact_bad_sealed_closer(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifacts, items, paths, _expected = synthetic_artifacts(
                module, root, sealed_closer_artifact="other.md"
            )
            materialize_live_artifacts(root, artifacts)
            item = items[0]
            (item / "status.md").write_text(status_text(), encoding="utf-8")
            ledger = item / "agent-runs.jsonl"
            before = ledger.read_bytes()
            body = event_body(before, "bad-closer-a1")
            command = recovery_command(item, digest(body))
            env = dict(os.environ)
            env["PYTHONDONTWRITEBYTECODE"] = "1"

            result = subprocess.run(
                command, text=True, capture_output=True, env=env
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("RESULT: PASS recover-invalid-closure", result.stdout)
            after = ledger.read_bytes()
            self.assertTrue(after.startswith(before))
            self.assertEqual(len(after.splitlines()), len(before.splitlines()) + 1)
            self.assertEqual(
                module.validate_work_item(
                    item, strict_revise=False, validate_status_file=False
                ),
                [],
            )
            strict_errors = module.validate_work_item(
                item, strict_revise=True, validate_status_file=False
            )
            self.assertTrue(
                any("open REVISE obligation: revise-a-0001" in error for error in strict_errors)
            )
            context = module.load_effective_ledger_view(root, item, paths[0])
            expected_view_sha256 = json.loads(artifacts.ledger_manifest_bytes)[
                "entries"
            ][0]["projectedViewSha256"]
            self.assertEqual(
                context.view.projected_view_sha256, expected_view_sha256
            )
            recovery_row = next(
                row
                for row in context.rows
                if row.event.get("runId") == "recover-bad-closer-a1"
            )
            validity_errors: list[str] = []
            recovery_validity = module.derive_event_validity(
                context.rows, item, validity_errors, context=context
            )[context.rows.index(recovery_row)]
            self.assertEqual(validity_errors, [])
            self.assertEqual(
                recovery_validity.authority, module._NO_LEDGER_AUTHORITY
            )

    def test_full_line_digest_and_correct_sealed_closer_are_rejected_without_append(self):
        module = load_validator()
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        for artifact, expected_error in (
            ("other.md", "target-digest-mismatch"),
            ("target.md", "target-authoritative"),
        ):
            with self.subTest(artifact=artifact), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                artifacts, items, _paths, _expected = synthetic_artifacts(
                    module, root, sealed_closer_artifact=artifact
                )
                materialize_live_artifacts(root, artifacts)
                item = items[0]
                (item / "status.md").write_text(status_text(), encoding="utf-8")
                ledger = item / "agent-runs.jsonl"
                before = ledger.read_bytes()
                body = event_body(before, "bad-closer-a1")
                supplied_digest = (
                    digest(body + b"\n") if artifact == "other.md" else digest(body)
                )

                result = subprocess.run(
                    recovery_command(item, supplied_digest),
                    text=True,
                    capture_output=True,
                    env=env,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected_error, result.stdout + result.stderr)
                self.assertEqual(ledger.read_bytes(), before)

    def test_checker_consumes_common_reduction_after_terminal_closer_recovery(self):
        module = load_validator()
        checker = load_checker()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifacts, items, paths, _expected = synthetic_artifacts(
                module,
                root,
                sealed_closer_artifact="other.md",
                sealed_closer_is_terminal=True,
            )
            path = paths[0]
            item = items[0]
            rows = artifacts.ledger_bytes_by_path[path].splitlines(keepends=True)
            closer_ordinal = next(
                index
                for index, line in enumerate(rows, start=1)
                if json.loads(line).get("runId") == "bad-closer-a1"
            )
            closer_body = rows[closer_ordinal - 1].rstrip(b"\r\n")
            recovery = {
                "schemaVersion": 2,
                "runId": "recover-terminal-closer",
                "workItem": "reader-a",
                "role": "lead",
                "executionRole": "main",
                "status": "completed",
                "gate": "none",
                "scope": ["ledger-recovery:closure-invalidation"],
                "eventKind": "closure-invalidation",
                "invalidatesRunId": "bad-closer-a1",
                "invalidatesEventSha256": digest(closer_body),
                "evidence": [
                    {
                        "kind": "manual-check",
                        "ref": f"bad-closer-a1 {digest(closer_body)}",
                    }
                ],
                "startedAt": "2026-09-09T00:00:00Z",
                "updatedAt": "2026-09-09T00:00:00Z",
            }
            ledgers = dict(artifacts.ledger_bytes_by_path)
            ledgers[path] += canonical(recovery) + b"\n"
            candidate = module.LedgerCompatibilityArtifactSetV1(
                **{**artifacts.__dict__, "ledger_bytes_by_path": ledgers}
            )
            context = module._load_effective_ledger_group(
                root, compatibility_artifacts=candidate
            )[path]

            unsettled = checker.unsettled_launch_run_ids(item, context, module)

            self.assertEqual(unsettled, {"launch-c-0001"})


if __name__ == "__main__":
    unittest.main()
