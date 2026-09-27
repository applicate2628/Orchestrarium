#!/usr/bin/env python3
"""Synthetic contract tests for append-only invalid-current suffix disposition."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import subprocess
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
    def test_raw_v2_refuses_casefold_colliding_target_and_keeps_sibling_diagnostic(self):
        validator = load_validator()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            item = root / "work-items" / "active" / "reader-a"
            item.mkdir(parents=True)
            target = {
                "schemaVersion": 2, "runId": "Target-Case", "workItem": "reader-a",
                "role": "qa-engineer", "executionRole": "internal",
                "status": "completed", "gate": "BLOCKED", "scope": ["synthetic"],
                "eventKind": "terminal", "launchRunId": "synthetic-launch",
                "startedAt": "2026-09-08T02:00:00Z",
                "updatedAt": "2026-09-08T02:00:01Z",
            }
            sibling = {
                **target, "runId": "target-case", "gate": "none",
                "eventKind": "standalone",
            }
            sibling.pop("launchRunId")
            target_line = canonical(target) + b"\n"
            before = target_line + canonical(sibling) + b"\n"
            recovery = disposition(1, target_line, target_run_id="Target-Case")
            candidate = before + canonical(recovery) + b"\n"
            errors = validator.validate_invalid_current_disposition_candidate(
                item, candidate, recovery, expected_ledger_sha256=digest(before),
            )
            self.assertTrue(any("runId identity differs" in error for error in errors), errors)

            ledger = item / "agent-runs.jsonl"
            ledger.write_bytes(candidate)
            selected = "work-items/active/reader-a/agent-runs.jsonl"
            context = validator.load_effective_ledger_view(root, item, selected)
            reader_errors = list(context.observation.diagnostics)
            validator._reduce_effective_current_state(
                context.rows, item, reader_errors, None, context=context
            )
            work_item_errors = validator.validate_work_item(
                item, validate_status_file=False, strict_revise=False
            )
            for observed in (reader_errors, work_item_errors):
                self.assertTrue(any("duplicate runId: target-case" in error for error in observed), observed)

    def test_raw_v2_public_loader_and_validator_converge_across_growth_and_forgery(self):
        validator = load_validator()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            item = root / "work-items" / "active" / "reader-a"
            item.mkdir(parents=True)
            launch = {
                "schemaVersion": 2, "runId": "synthetic-launch", "workItem": "reader-a",
                "role": "qa-engineer", "executionRole": "internal",
                "status": "running", "gate": "none", "scope": ["synthetic"],
                "eventKind": "launch", "startedAt": "2026-09-08T02:00:00Z",
                "updatedAt": "2026-09-08T02:00:00Z",
            }
            target = {
                **launch, "runId": "synthetic-terminal", "status": "completed",
                "gate": "BLOCKED", "eventKind": "terminal",
                "launchRunId": "synthetic-launch",
                "updatedAt": "2026-09-08T02:00:01Z",
            }
            unrelated = {
                **launch, "runId": "unrelated-row", "status": "completed",
                "eventKind": "standalone", "unrelatedField": True,
            }
            target_line = canonical(target) + b"\n"
            before = canonical(launch) + b"\n" + target_line + canonical(unrelated) + b"\n"
            ledger = item / "agent-runs.jsonl"
            ledger.write_bytes(before)
            selected = "work-items/active/reader-a/agent-runs.jsonl"

            def snapshot():
                context = validator.load_effective_ledger_view(root, item, selected)
                reader_errors = list(context.observation.diagnostics)
                _active, validity, _revise, launches = validator._reduce_effective_current_state(
                    context.rows, item, reader_errors, None, context=context
                )
                work_item_errors = validator.validate_work_item(
                    item, validate_status_file=False, strict_revise=False
                )
                return context, reader_errors, work_item_errors, validity, launches

            baseline = snapshot()
            for observed in (baseline[1], baseline[2]):
                self.assertTrue(any("invalid gate 'BLOCKED'" in error for error in observed), observed)
                self.assertIn("unexpected field: unrelatedField", observed)

            recovery = disposition(2, target_line, target_run_id="synthetic-terminal")
            command = [
                sys.executable, "-B", str(WRITER), "--work-item", str(item),
                "dispose-invalid-current", "--run-id", str(recovery["runId"]),
                "--target-run-id", "synthetic-terminal",
                "--target-raw-line-ordinal", "2",
                "--target-event-sha256", digest(target_line),
                "--expected-ledger-sha256", digest(before),
                "--evidence", "manual-check:" + recovery["evidence"][0]["ref"],
                "--started-at", str(recovery["startedAt"]),
                "--updated-at", str(recovery["updatedAt"]),
            ]
            applied = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
            disposed = ledger.read_bytes()
            later_valid = {**launch, "runId": "later-valid-row", "status": "completed", "eventKind": "standalone"}
            for stage, raw in (
                ("disposed", disposed),
                ("later-append", disposed + canonical(later_valid) + b"\n"),
            ):
                with self.subTest(stage=stage):
                    ledger.write_bytes(raw)
                    context, reader_errors, work_item_errors, validity, launches = snapshot()
                    self.assertIsNone(context.view)
                    self.assertEqual(context.rows[1].epoch, "disposed-raw")
                    self.assertEqual(context.rows[1].authority, validator._NO_LEDGER_AUTHORITY)
                    self.assertEqual(validity[1].authority, validator._NO_LEDGER_AUTHORITY)
                    self.assertIn("synthetic-launch", {row["runId"] for row in launches})
                    for observed in (reader_errors, work_item_errors):
                        self.assertFalse(any("synthetic-terminal:" in error for error in observed), observed)
                        self.assertIn("unexpected field: unrelatedField", observed)

            forged = {**recovery, "invalidatesEventSha256": "0" * 64}
            forged["evidence"] = [{
                "kind": "manual-check", "ref": f"synthetic-terminal {'0' * 64} approved",
            }]
            ledger.write_bytes(before + canonical(forged) + b"\n")
            context, reader_errors, work_item_errors, _validity, _launches = snapshot()
            for observed in (reader_errors, work_item_errors):
                self.assertTrue(any("DISPOSITION-TARGET" in error for error in observed), observed)
                self.assertTrue(any("synthetic-terminal: invalid gate 'BLOCKED'" in error for error in observed), observed)

    def test_raw_v2_completed_blocked_terminal_appends_nonauthorizing_disposition(self):
        validator = load_validator()
        with tempfile.TemporaryDirectory() as td:
            item = Path(td) / "work-items" / "active" / "reader-a"
            item.mkdir(parents=True)
            launch = {
                "schemaVersion": 2,
                "runId": "synthetic-launch",
                "workItem": "reader-a",
                "role": "qa-engineer",
                "executionRole": "internal",
                "status": "running",
                "gate": "none",
                "scope": ["synthetic launch"],
                "eventKind": "launch",
                "startedAt": "2026-09-08T02:00:00Z",
                "updatedAt": "2026-09-08T02:00:00Z",
            }
            target = {
                **launch,
                "runId": "synthetic-invalid-terminal",
                "status": "completed",
                "gate": "BLOCKED",
                "eventKind": "terminal",
                "launchRunId": "synthetic-launch",
                "updatedAt": "2026-09-08T02:00:01Z",
            }
            isolated_errors: list[str] = []
            validator._validate_event(target, item, set(), isolated_errors)
            self.assertEqual(
                isolated_errors,
                [
                    "synthetic-invalid-terminal: invalid gate 'BLOCKED'",
                    "synthetic-invalid-terminal: BLOCKED gate requires blocked status",
                ],
            )
            launch_line = canonical(launch) + b"\n"
            target_line = canonical(target) + b"\n"
            before = launch_line + target_line
            ledger = item / "agent-runs.jsonl"
            ledger.write_bytes(before)
            baseline = validator.validate_work_item(
                item, validate_status_file=False, strict_revise=False
            )
            for error in isolated_errors:
                self.assertIn(error, baseline)
            expected_sha = hashlib.sha256(before).hexdigest()
            target_sha = hashlib.sha256(target_line).hexdigest()
            command = [
                sys.executable, "-B", str(WRITER), "--work-item", str(item),
                "dispose-invalid-current", "--run-id", "synthetic-disposition",
                "--target-run-id", "synthetic-invalid-terminal",
                "--target-raw-line-ordinal", "2",
                "--target-event-sha256", target_sha,
                "--expected-ledger-sha256", expected_sha,
                "--evidence", f"manual-check:synthetic-invalid-terminal {target_sha} approved",
                "--started-at", "2026-09-08T02:01:00Z",
                "--updated-at", "2026-09-08T02:01:00Z",
            ]
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            after = ledger.read_bytes()
            self.assertTrue(after.startswith(before))
            self.assertEqual(len(after.splitlines()), 3)
            errors = validator.validate_work_item(
                item, validate_status_file=False, strict_revise=False
            )
            for error in isolated_errors:
                self.assertNotIn(error, errors)
            strict_errors = validator.validate_work_item(
                item, validate_status_file=False, strict_revise=True
            )
            self.assertTrue(
                any("unsettled launch: synthetic-launch" in error for error in strict_errors),
                strict_errors,
            )
            replay = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(replay.returncode, 0, replay.stdout + replay.stderr)
            self.assertEqual(ledger.read_bytes(), after)
            drift = subprocess.run(
                [*command[:command.index("--expected-ledger-sha256") + 1], "0" * 64,
                 *command[command.index("--evidence"):]],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(drift.returncode, 1, drift.stdout + drift.stderr)
            self.assertEqual(ledger.read_bytes(), after)

    def test_raw_v2_qualification_and_unrelated_errors_share_one_target_predicate(self):
        validator = load_validator()
        with tempfile.TemporaryDirectory() as td:
            item = Path(td) / "work-items" / "active" / "reader-a"
            item.mkdir(parents=True)
            target = {
                "schemaVersion": 2,
                "runId": "qualified-invalid-terminal",
                "workItem": "reader-a",
                "role": "qa-engineer",
                "executionRole": "internal",
                "status": "completed",
                "gate": "BLOCKED:prerequisite",
                "scope": ["synthetic qualified terminal"],
                "eventKind": "terminal",
                "launchRunId": "synthetic-launch",
                "startedAt": "2026-09-08T02:00:00Z",
                "updatedAt": "2026-09-08T02:00:01Z",
            }
            target_line = canonical(target) + b"\n"
            recovery = disposition(1, target_line, target_run_id="qualified-invalid-terminal")

            def candidate_errors(event: dict[str, object]) -> tuple[str, ...]:
                line = canonical(event) + b"\n"
                bound = {**recovery, "invalidatesEventSha256": digest(line)}
                bound["evidence"] = [{
                    "kind": "manual-check",
                    "ref": f"qualified-invalid-terminal {digest(line)} approved",
                }]
                return validator.validate_invalid_current_disposition_candidate(
                    item, line + canonical(bound) + b"\n", bound,
                    expected_ledger_sha256=digest(line),
                )

            isolated: list[str] = []
            validator._validate_event(target, item, set(), isolated)
            self.assertEqual(
                isolated,
                ["qualified-invalid-terminal: BLOCKED gate requires blocked status"],
            )
            self.assertEqual(candidate_errors(target), ())
            unrelated = {**target, "unexpectedField": True}
            self.assertTrue(any("unrelated per-event errors" in error for error in candidate_errors(unrelated)))
            valid = {**target, "status": "blocked"}
            self.assertTrue(any("current-schema valid" in error for error in candidate_errors(valid)))
            control = {**target, "eventKind": "launch"}
            self.assertTrue(any("control/lifecycle kind" in error for error in candidate_errors(control)))
            non_v2 = {**target, "schemaVersion": 1}
            self.assertTrue(any("entirely V2" in error for error in candidate_errors(non_v2)))
            malformed = b'{"schemaVersion":2,"schemaVersion":2}\n'
            malformed_errors = validator.validate_invalid_current_disposition_candidate(
                item, malformed, recovery, expected_ledger_sha256=digest(malformed)
            )
            self.assertTrue(any("duplicate" in error for error in malformed_errors), malformed_errors)

            wrong_ordinal = {**recovery, "invalidatesRawLineOrdinal": 2}
            self.assertTrue(any("target ordinal" in error for error in
                validator.validate_invalid_current_disposition_candidate(
                    item, target_line + canonical(wrong_ordinal) + b"\n",
                    wrong_ordinal, expected_ledger_sha256=digest(target_line),
                )
            ))
            first = target_line + canonical(recovery) + b"\n"
            second = {**recovery, "runId": "second-disposition"}
            conflict_errors = validator.validate_invalid_current_disposition_candidate(
                item, first + canonical(second) + b"\n", second,
                expected_ledger_sha256=digest(first),
            )
            self.assertTrue(any("DISPOSITION-CONFLICT" in error for error in conflict_errors), conflict_errors)

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
