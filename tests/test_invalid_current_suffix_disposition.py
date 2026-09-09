#!/usr/bin/env python3
"""Synthetic contract tests for append-only invalid-current suffix disposition."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from tests.test_ledger_h1_effective_view import (
    canonical,
    digest,
    load_validator,
    materialize_live_artifacts,
    synthetic_artifacts,
)


ROOT = Path(__file__).resolve().parents[1]
WRITER = ROOT / "scripts" / "agent-run-ledger.py"


def load_writer():
    spec = importlib.util.spec_from_file_location("suffix_disposition_writer", WRITER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def invalid_target(run_id: str = "invalid-suffix-target") -> dict[str, object]:
    return {
        "schemaVersion": 2,
        "runId": run_id,
        "workItem": "reader-a",
        "role": "qa-engineer",
        "executionRole": "internal",
        "status": "completed",
        "gate": "PASS",
        "scope": ["synthetic invalid suffix"],
        "eventKind": "terminal",
        "evidence": [{"kind": "unsupported", "ref": "preserved evidence"}],
        "startedAt": "2026-09-08T02:00:00Z",
        "updatedAt": "2026-09-08T02:00:01Z",
    }


def disposition(
    ordinal: int,
    target_line: bytes,
    *,
    run_id: str = "dispose-invalid-suffix",
    target_run_id: str = "invalid-suffix-target",
) -> dict[str, object]:
    target_sha = digest(target_line)
    return {
        "schemaVersion": 2,
        "runId": run_id,
        "workItem": "reader-a",
        "role": "lead",
        "executionRole": "main",
        "status": "completed",
        "gate": "none",
        "scope": ["ledger-recovery:invalid-current-nonauthorizing"],
        "eventKind": "closure-invalidation",
        "invalidationMode": "invalid-current-nonauthorizing",
        "invalidatesRawLineOrdinal": ordinal,
        "invalidatesRunId": target_run_id,
        "invalidatesEventSha256": target_sha,
        "authorizing": False,
        "evidence": [
            {
                "kind": "manual-check",
                "ref": f"approved exact target {target_run_id} {target_sha}",
            }
        ],
        "startedAt": "2026-09-08T02:01:00Z",
        "updatedAt": "2026-09-08T02:01:00Z",
    }


def fixture(module, root: Path):
    artifacts, items, paths, _expected = synthetic_artifacts(module, root)
    path = paths[0]
    target_line = canonical(invalid_target()) + b"\n"
    target_ordinal = len(artifacts.ledger_bytes_by_path[path].splitlines()) + 1
    recovery = disposition(target_ordinal, target_line)
    ledgers = dict(artifacts.ledger_bytes_by_path)
    ledgers[path] += target_line + canonical(recovery) + b"\n"
    candidate = module.LedgerCompatibilityArtifactSetV1(
        **{**artifacts.__dict__, "ledger_bytes_by_path": ledgers}
    )
    return artifacts, candidate, items[0], path, target_line, recovery


class InvalidCurrentSuffixDispositionTests(unittest.TestCase):
    def test_current_terminal_relation_diagnostics_do_not_reinterpret_sealed_prefix(self):
        module = load_validator()
        launch_event = {
            "runId": "relation-launch",
            "eventKind": "launch",
            "launchFlags": ["--model", "one"],
        }
        terminal_event = {
            "runId": "relation-terminal",
            "eventKind": "terminal",
            "launchRunId": "relation-launch",
            "launchFlags": ["--model", "two"],
        }
        launch_authority = module.LedgerAuthorityV1(True, False, False, False, False)
        terminal_authority = module._NO_LEDGER_AUTHORITY

        def rows(epoch: str):
            return (
                module.RuntimeLedgerRowV1(launch_event, 1, "1" * 64, "1" * 64, "2" * 64, epoch, launch_authority),
                module.RuntimeLedgerRowV1(terminal_event, 2, "3" * 64, "3" * 64, "4" * 64, epoch, terminal_authority),
            )

        current_rows = rows("strict-suffix")
        current_validity = (
            module.LedgerEventValidityV1(True, launch_authority),
            module.LedgerEventValidityV1(True, terminal_authority),
        )
        current_errors: list[str] = []
        module.validate_closure(
            current_rows, current_errors, validity=current_validity
        )
        self.assertTrue(
            any("launchFlags must equal" in error for error in current_errors)
        )

        sealed_rows = rows("sealed-prefix")
        sealed_validity = tuple(
            module.LedgerEventValidityV1(False, row.authority)
            for row in sealed_rows
        )
        sealed_errors: list[str] = []
        module._validate_closure_authority(
            sealed_rows, sealed_errors, validity=sealed_validity
        )
        self.assertEqual(sealed_errors, [])

        for label, target_event, target_validity, expected in (
            (
                "nonlaunch",
                {"runId": "relation-launch", "eventKind": "standalone"},
                True,
                "references a non-launch event",
            ),
            (
                "invalid-launch",
                {"runId": "relation-launch", "eventKind": "launch"},
                False,
                "references an invalid launch event",
            ),
        ):
            with self.subTest(label=label):
                current_rows = (
                    module.RuntimeLedgerRowV1(
                        target_event,
                        1,
                        "1" * 64,
                        "1" * 64,
                        "2" * 64,
                        "strict-suffix",
                        module._NO_LEDGER_AUTHORITY,
                    ),
                    module.RuntimeLedgerRowV1(
                        {
                            "runId": "relation-terminal",
                            "eventKind": "terminal",
                            "launchRunId": "relation-launch",
                        },
                        2,
                        "3" * 64,
                        "3" * 64,
                        "4" * 64,
                        "strict-suffix",
                        module._NO_LEDGER_AUTHORITY,
                    ),
                )
                validity = (
                    module.LedgerEventValidityV1(
                        target_validity, module._NO_LEDGER_AUTHORITY
                    ),
                    module.LedgerEventValidityV1(
                        True, module._NO_LEDGER_AUTHORITY
                    ),
                )
                relation_errors: list[str] = []
                module.validate_closure(
                    current_rows, relation_errors, validity=validity
                )
                self.assertTrue(
                    any(expected in error for error in relation_errors),
                    relation_errors,
                )

    def test_schema_accepts_both_closed_invalidation_modes(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifacts, _candidate, item, path, target_line, recovery = fixture(module, root)
            schema = json.loads(
                (ROOT / "shared" / "schemas" / "agent-runs.schema.json").read_text(
                    encoding="utf-8"
                )
            )
            validator = Draft202012Validator(schema)
            self.assertEqual(list(validator.iter_errors(recovery)), [])
            old = {
                **recovery,
                "runId": "old-relation-invalidation",
                "scope": ["ledger-recovery:closure-invalidation"],
            }
            old.pop("invalidationMode")
            old.pop("invalidatesRawLineOrdinal")
            old.pop("authorizing")
            self.assertEqual(list(validator.iter_errors(old)), [])

    def test_active_reader_disposes_only_exact_invalid_suffix_identity(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            baseline, candidate, item, path, target_line, recovery = fixture(module, root)
            baseline_context = module._load_effective_ledger_group(
                root, compatibility_artifacts=baseline
            )[path]

            contexts = module._load_effective_ledger_group(
                root, compatibility_artifacts=candidate
            )
            context = contexts[path]

            self.assertEqual(context.observation.activation_state, "active")
            self.assertEqual(context.view.projected_view_sha256, baseline_context.view.projected_view_sha256)
            self.assertEqual(context.view.wire, baseline_context.view.wire)
            self.assertEqual(len(context.observation.disposition_notices), 1)
            other_context = next(
                value for key, value in contexts.items() if key != path
            )
            self.assertEqual(other_context.observation.disposition_notices, ())
            notice = context.observation.disposition_notices[0]
            self.assertEqual(notice.run_id, "invalid-suffix-target")
            self.assertEqual(notice.raw_line_sha256, digest(target_line))
            self.assertEqual(notice.disposition_run_id, recovery["runId"])
            target_row = context.rows[notice.raw_line_ordinal - 1]
            disposition_row = context.rows[notice.disposition_line_ordinal - 1]
            self.assertEqual(target_row.epoch, "disposed-suffix")
            self.assertEqual(dict(target_row.event), invalid_target())
            self.assertEqual(target_row.authority, module._NO_LEDGER_AUTHORITY)
            self.assertEqual(
                disposition_row.authority, module._NO_LEDGER_AUTHORITY
            )
            validity_errors: list[str] = []
            validity = module.derive_event_validity(
                context.rows, item, validity_errors, context=context
            )
            self.assertEqual(validity_errors, [])
            self.assertEqual(
                validity[notice.disposition_line_ordinal - 1].authority,
                module._NO_LEDGER_AUTHORITY,
            )
            telemetry: dict[str, int] = {}
            self.assertEqual(
                module.validate_work_item(
                    item,
                    strict_revise=False,
                    validate_status_file=False,
                    telemetry=telemetry,
                    compatibility_artifacts=candidate,
                ),
                [],
            )
            self.assertEqual(telemetry["ledger-compat-suffix-disposed-nonauthorizing"], 1)

    def test_inactive_and_unrelated_invalid_rows_keep_current_diagnostics(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _baseline, candidate, item, path, _target_line, _recovery = fixture(module, root)
            ledger = item / "agent-runs.jsonl"
            ledger.write_bytes(candidate.ledger_bytes_by_path[path])
            inactive = module.validate_work_item(
                item, strict_revise=False, validate_status_file=False
            )
            self.assertTrue(any("invalid kind 'unsupported'" in error for error in inactive))

            ledgers = dict(candidate.ledger_bytes_by_path)
            ledgers[path] += b"{}\n"
            unrelated = module.LedgerCompatibilityArtifactSetV1(
                **{**candidate.__dict__, "ledger_bytes_by_path": ledgers}
            )
            active_errors = module.validate_work_item(
                item,
                strict_revise=False,
                validate_status_file=False,
                compatibility_artifacts=unrelated,
            )
            self.assertTrue(any("event missing required field" in error for error in active_errors))

    def test_writer_appends_once_and_default_timestamp_retry_is_idempotent(self):
        validator = load_validator()
        writer = load_writer()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifacts, _candidate, item, path, target_line, recovery = fixture(validator, root)
            ledger = item / "agent-runs.jsonl"
            ledger.write_bytes(artifacts.ledger_bytes_by_path[path] + target_line)
            manifest = root / "suffix-manifest.json"
            manifest.write_bytes(artifacts.ledger_manifest_bytes)
            before = ledger.read_bytes()
            argv = [
                "--work-item", str(item),
                "dispose-invalid-current",
                "--run-id", str(recovery["runId"]),
                "--target-run-id", "invalid-suffix-target",
                "--target-raw-line-ordinal", str(recovery["invalidatesRawLineOrdinal"]),
                "--target-event-sha256", str(recovery["invalidatesEventSha256"]),
                "--ledger-manifest", str(manifest),
                "--evidence", recovery["evidence"][0]["kind"] + ":" + recovery["evidence"][0]["ref"],
            ]
            failed_output = io.StringIO()
            with contextlib.redirect_stdout(failed_output):
                self.assertEqual(
                    writer.main([*argv, "--inject-failure", "pre-replace"]),
                    1,
                )
            self.assertEqual(ledger.read_bytes(), before)
            self.assertNotIn(
                "RESULT: PASS dispose-invalid-current", failed_output.getvalue()
            )

            first_output = io.StringIO()
            with contextlib.redirect_stdout(first_output):
                self.assertEqual(writer.main(argv), 0)
            after = ledger.read_bytes()
            self.assertTrue(after.startswith(before))
            self.assertEqual(len(after.splitlines()), len(before.splitlines()) + 1)
            self.assertIn("RESULT: PASS dispose-invalid-current", first_output.getvalue())

            replay_output = io.StringIO()
            with contextlib.redirect_stdout(replay_output):
                self.assertEqual(writer.main(argv), 0)
            self.assertEqual(ledger.read_bytes(), after)
            self.assertIn("RESULT: PASS dispose-invalid-current", replay_output.getvalue())

            raw_errors = validator.validate_work_item(
                item, strict_revise=False, validate_status_file=False
            )
            self.assertTrue(any("invalid kind 'unsupported'" in error for error in raw_errors))

    def test_candidate_rejects_wrong_hash_and_current_valid_target(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifacts, _candidate, item, path, target_line, recovery = fixture(module, root)
            ledger_bytes = artifacts.ledger_bytes_by_path[path] + target_line
            wrong_sha = "0" * 64
            wrong = {
                **recovery,
                "invalidatesEventSha256": wrong_sha,
                "evidence": [
                    {
                        "kind": "manual-check",
                        "ref": f"approved exact target invalid-suffix-target {wrong_sha}",
                    }
                ],
            }
            self.assertTrue(
                any(
                    "WI-LEDGER-COMPAT-SUFFIX-DISPOSITION-TARGET" in error
                    for error in module.validate_invalid_current_disposition_candidate(
                        item,
                        ledger_bytes,
                        wrong,
                        ledger_manifest_bytes=artifacts.ledger_manifest_bytes,
                    )
                )
            )

            mutated_line = target_line[:-2] + b" " + target_line[-1:]
            self.assertTrue(
                any(
                    "WI-LEDGER-COMPAT-SUFFIX-DISPOSITION-TARGET" in error
                    for error in module.validate_invalid_current_disposition_candidate(
                        item,
                        artifacts.ledger_bytes_by_path[path] + mutated_line,
                        recovery,
                        ledger_manifest_bytes=artifacts.ledger_manifest_bytes,
                    )
                )
            )

            valid = {
                **invalid_target("valid-suffix-target"),
                "gate": "none",
                "eventKind": "standalone",
                "evidence": [{"kind": "manual-check", "ref": "valid"}],
            }
            valid_line = canonical(valid) + b"\n"
            valid_disposition = disposition(
                len(artifacts.ledger_bytes_by_path[path].splitlines()) + 1,
                valid_line,
                target_run_id="valid-suffix-target",
            )
            self.assertTrue(
                any(
                    "WI-LEDGER-COMPAT-SUFFIX-DISPOSITION-TARGET" in error
                    for error in module.validate_invalid_current_disposition_candidate(
                        item,
                        artifacts.ledger_bytes_by_path[path] + valid_line,
                        valid_disposition,
                        ledger_manifest_bytes=artifacts.ledger_manifest_bytes,
                    )
                )
            )

    def test_writer_and_active_reader_share_forbidden_target_kinds(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifacts, _candidate, item, path, _target_line, _recovery = fixture(module, root)
            base = {
                "schemaVersion": 2,
                "workItem": "reader-a",
                "role": "lead",
                "executionRole": "main",
                "status": "completed",
                "gate": "none",
                "scope": ["synthetic forbidden target"],
                "evidence": [{"kind": "manual-check", "ref": "synthetic"}],
                "startedAt": "2026-09-08T03:00:00Z",
                "updatedAt": "2026-09-08T03:00:01Z",
            }
            forbidden = (
                {**base, "runId": "forbidden-launch", "eventKind": "launch", "status": "running"},
                {**base, "runId": "forbidden-migration", "eventKind": "legacy-obligation-migration"},
                {**base, "runId": "forbidden-disposition", "eventKind": "closure-invalidation"},
            )
            ordinal = len(artifacts.ledger_bytes_by_path[path].splitlines()) + 1
            for target in forbidden:
                with self.subTest(kind=target["eventKind"]):
                    target_line = canonical(target) + b"\n"
                    recovery = disposition(
                        ordinal,
                        target_line,
                        target_run_id=str(target["runId"]),
                    )
                    ledger_bytes = artifacts.ledger_bytes_by_path[path] + target_line
                    writer_errors = module.validate_invalid_current_disposition_candidate(
                        item,
                        ledger_bytes,
                        recovery,
                        ledger_manifest_bytes=artifacts.ledger_manifest_bytes,
                    )
                    self.assertTrue(
                        any("WI-LEDGER-COMPAT-SUFFIX-DISPOSITION-TARGET" in error for error in writer_errors)
                    )
                    ledgers = dict(artifacts.ledger_bytes_by_path)
                    ledgers[path] = ledger_bytes + canonical(recovery) + b"\n"
                    candidate = module.LedgerCompatibilityArtifactSetV1(
                        **{**artifacts.__dict__, "ledger_bytes_by_path": ledgers}
                    )
                    active = module._load_effective_ledger_group(
                        root, compatibility_artifacts=candidate
                    )
                    self.assertTrue(
                        all(context.observation.activation_state == "invalid" for context in active.values())
                    )

if __name__ == "__main__":
    unittest.main()
