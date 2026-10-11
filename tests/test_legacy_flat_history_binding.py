"""Captured history acquisition; public legacy lifecycle QA is a separate gate."""
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "legacy_binding_verdict_fixtures", ROOT / "tests/test_review_verdict_closure.py"
)
fixtures = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixtures)
v = fixtures.vws


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class CapturedHistoryBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="history-binding-test-", dir=ROOT / ".scratch")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.owner = v.load_lifecycle_owner()
        self.item = self.root / "work-items/archive/2026-07/fixture-item"
        self.item.mkdir(parents=True)
        self.source = self.root / "work-items/backlog/fixture-item.md"
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(b"# Original flat record\nStatus: delivered\n")
        (self.item / "criteria.md").write_bytes(b"Original accepted ledger and archive criteria.\n")
        (self.item / "acquisition.md").write_bytes(b"Accepted exact original history selection.\n")
        (self.item / "design.md").write_bytes(b"Original design evidence\n")
        self.closure = (
            b"Closed: 2026-07-16T10:00:01Z\nOutcome: fixture complete\n"
            b"Evidence: design.md\nResidual risk: none\n"
        )
        self.owner._validate_closure(self.closure, "2026-07-16T10:00:01Z")
        (self.item / "closure.md").write_bytes(self.closure)

    def ledger(self, *, bad=False, modern=False):
        target = fixtures._event(
            "run-lead-main-revise", role="lead", executionRole="main", gate="REVISE",
            status="revise", artifact="design.md", lane="qa", effort="medium", provider="codex",
        )
        closer = fixtures._event(
            "run-qa-lead-closer", role="qa-engineer", executionRole="internal", gate="PASS",
            artifact="design.md", lane="qa", effort="medium", provider="codex",
            closesRunIds=[target["runId"]], evidence=[{"kind": "review", "ref": "qa re-verification"}],
        )
        if modern:
            closer["reviewedRole"] = "lead"
        else:
            closer["assignedRole"] = "lead"
        if bad:
            closer["updatedAt"] = "2026-07-17T10:00:00Z"
        raw = b"\n" + b"\r\n".join(json.dumps(row).encode() for row in (target, closer)) + b"\r\n"
        (self.item / "agent-runs.jsonl").write_bytes(raw)
        return raw

    def binding(self, *, required=True, contract="archive", extra_absent=(), criteria_data=None):
        if criteria_data is None:
            (self.item / "criteria.md").write_text(
            f"Accepted original owner contract: {contract}.\n"
            f"Original ledger requirement: {'required' if required else 'not required'}.\n",
            encoding="utf-8",
            )
        else:
            (self.item / "criteria.md").write_bytes(criteria_data)
        records = []
        directories = {}
        for directory in (self.root, *(p for p in self.root.rglob("*") if p.is_dir())):
            directories[directory.relative_to(self.root).as_posix()] = tuple(sorted(p.name for p in directory.iterdir()))
        for path in self.root.rglob("*"):
            if path.is_file():
                snapshot = self.owner._capture_file_snapshot(path, failure_id="WI-TEST-CAPTURE")
                records.append(v.CapturedHistoryFileV1(
                    path.relative_to(self.root).as_posix(), snapshot, snapshot.length, sha(snapshot.data)
                ))
        base = self.item.relative_to(self.root).as_posix()
        absent = [
            f"{base}/review-artifact-custody/historical-pass", f"{base}/status.md", f"{base}/closure.md",
            "work-items/legacy-ledger-projection-manifests", "work-items/legacy-ledger-projections.jsonl",
            "work-items/legacy-ledger-historical-dispositions", "work-items/decision-h1-compatibility.json",
            *extra_absent,
        ]
        absent = [path for path in absent if not (self.root / path).exists()]
        ledger = f"{base}/agent-runs.jsonl"
        if not (self.root / ledger).exists():
            absent.append(ledger)
        for path in absent:
            self.assertFalse((self.root / path).exists(), path)
        directory_proofs = tuple(self.owner._capture_directory_snapshot(self.root / key,
                                   failure_id="WI-TEST-DIRECTORY") for key in directories)
        acquired = self.owner.AcquiredWorkItemInputV1(
            self.root,
            tuple(self.owner.CapturedInputAssociationV1(row.snapshot, row.snapshot) for row in records),
            tuple(self.owner.CapturedInputAssociationV1(proof, proof) for proof in directory_proofs),
        )
        return v.CapturedWorkItemHistoryBindingV1(
            self.root, self.item.name, self.source.relative_to(self.root).as_posix(), base, ledger,
            v.HistoricalLedgerCriteriaV1(f"{base}/criteria.md", f"{base}/acquisition.md", required, contract),
            tuple(records), tuple(absent), directories, acquired,
        )

    def relocate(self, binding):
        # Preserve exact original associations and bytes at disjoint custody
        # destinations; the new action closure is deliberately a later instant.
        archive = self.root / "work-items/archive/2026-10/fixture-item"
        archive.mkdir(parents=True, exist_ok=True)
        custody_root = Path(tempfile.mkdtemp(prefix="custody-", dir=archive))
        records = []
        for index, record in enumerate(binding.files):
            destination = custody_root / str(index) / Path(record.original_path).name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(record.snapshot.data)
            snapshot = self.owner._capture_file_snapshot(destination, failure_id="WI-TEST-CAPTURE")
            records.append(replace(record, snapshot=snapshot))
        (archive / "closure.md").write_bytes(self.closure.replace(b"2026-07-16T10:00:01Z", b"2026-10-11T00:00:00Z"))
        current_directory = self.owner._capture_directory_snapshot(custody_root, failure_id="WI-TEST-DIRECTORY")
        acquired = self.owner.AcquiredWorkItemInputV1(
            self.root,
            tuple(self.owner.CapturedInputAssociationV1(
                binding.acquired_input.files[self.root / row.original_path].original, row.snapshot
            ) for row in records),
            tuple(self.owner.CapturedInputAssociationV1(row.original, current_directory)
                  for row in binding.acquired_input.directories.values()),
        )
        # Delete only this fixture's exact creator-owned original directories.
        for path in (self.item, self.source.parent):
            self.assertTrue(path.is_relative_to(self.root))
            shutil.rmtree(path)
        return replace(binding, files=tuple(records), acquired_input=acquired)

    def test_archive_authority_and_obligations_match_before_and_after_relocation(self):
        for bad in (False, True):
            with self.subTest(bad=bad):
                raw = self.ledger(bad=bad)
                states, masks = [], []
                baseline, _, _ = v.validate_archived_ledger_obligations(
                    self.item, obligation_state_out=states, authority_state_out=masks,
                )
                original = self.binding()
                before = v.observe_captured_work_item_history(original)
                self.assertEqual(before.authority_by_raw_line, masks[-1])
                self.assertEqual(before.obligations, states[-1])
                self.assertEqual(before.ledger_sha256, sha(raw))
                self.assertTrue(before.acquisition_complete)
                self.assertEqual(bool(before.diagnostics), bad)
                self.assertTrue(all(error in before.diagnostics for error in baseline))
                self.assertEqual(bool(before.obligations.open_revise), bad)
                retained = self.relocate(original)
                after = v.observe_captured_work_item_history(retained)
                self.assertEqual(before, after)
                # Exact physical ordinals/digests survive blank lines and CRLF.
                metadata, errors = [], []
                events = v.load_jsonl(self.item / "agent-runs.jsonl", errors, metadata, raw)
                self.assertEqual([row["line"] for row in metadata], [2, 3])
                self.assertEqual([event["runId"] for event in events], ["run-lead-main-revise", "run-qa-lead-closer"])
                if bad:
                    self.assertEqual(after.obligations.open_revise[0].raw_line_ordinal, 2)
                # Restore only this owned synthetic fixture for the second arm.
                self.item.mkdir(parents=True)
                self.source.parent.mkdir(parents=True)
                for record in retained.files:
                    path = self.root / record.original_path
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(record.snapshot.data)

    def test_current_contract_does_not_gain_archive_closer_compatibility(self):
        self.ledger()
        binding = self.binding(contract="current")
        baseline_states, baseline_masks = [], []
        baseline = v.validate_work_item(
            self.item, validate_status_file=False, obligation_state_out=baseline_states,
            authority_state_out=baseline_masks,
        )
        observation = v.observe_captured_work_item_history(binding)
        self.assertTrue(any("C3-reviewed-role-fail" in error for error in observation.diagnostics))
        self.assertEqual(observation.authority_by_raw_line, baseline_masks[-1])
        self.assertEqual(observation.obligations, baseline_states[-1])
        self.assertTrue(all(error in observation.diagnostics for error in baseline))
        self.assertEqual(observation, v.observe_captured_work_item_history(self.relocate(binding)))

    def test_valid_current_contract_is_preserved(self):
        self.ledger(modern=True)
        observation = v.observe_captured_work_item_history(self.binding(contract="current"))
        self.assertEqual(observation.diagnostics, ())
        self.assertFalse(observation.obligations.open_revise)

    def test_absent_required_unknown_and_acquired_empty_are_distinct(self):
        (self.item / "closure.md").unlink()
        optional = self.binding(required=False, contract="current")
        observation = v.observe_captured_work_item_history(optional)
        self.assertEqual(observation.selection, "absent")
        self.assertEqual(observation.diagnostics, ())
        self.assertIsNone(observation.obligations)
        self.assertIsNone(observation.authority_by_raw_line)
        required = v.observe_captured_work_item_history(replace(optional, criteria=replace(optional.criteria, ledger_required=True)))
        self.assertTrue(any("missing ledger" in error for error in required.diagnostics))
        unknown = v.observe_captured_work_item_history(replace(optional, criteria=None))
        self.assertTrue(unknown.diagnostics)
        (self.item / "agent-runs.jsonl").write_bytes(b"")
        empty = v.observe_captured_work_item_history(self.binding(required=False, contract="current"))
        self.assertEqual(empty.selection, "present")
        self.assertTrue(any("ledger has no events" in error for error in empty.diagnostics))

    def test_corrupt_history_and_missing_original_closure_fail(self):
        (self.item / "agent-runs.jsonl").write_bytes(b'{"schemaVersion":2\n')
        corrupted = v.observe_captured_work_item_history(self.binding())
        self.assertTrue(corrupted.diagnostics)
        self.assertFalse(corrupted.acquisition_complete)
        self.ledger()
        (self.item / "closure.md").unlink()
        missing = self.binding()
        self.assertTrue(any("closure proof" in error for error in v.observe_captured_work_item_history(missing).diagnostics))

    def test_native_identity_and_custody_byte_drift_refuse(self):
        self.ledger()
        binding = self.binding()
        record = next(row for row in binding.files if row.original_path.endswith("/design.md"))
        record.snapshot.path.write_bytes(b"changed\n")
        self.assertTrue(any("DRIFT" in error for error in v.observe_captured_work_item_history(binding).diagnostics))
        fresh = self.binding()
        corrupt = replace(fresh, files=(replace(fresh.files[0], sha256="0" * 64), *fresh.files[1:]))
        self.assertTrue(any("CUSTODY" in error for error in v.observe_captured_work_item_history(corrupt).diagnostics))
        fresh = self.binding()
        original = next(row for row in fresh.files if row.original_path.endswith("/design.md"))
        replacement = original.snapshot.path.with_suffix(".replacement")
        replacement.write_bytes(original.snapshot.data)
        original.snapshot.path.unlink()
        replacement.replace(original.snapshot.path)
        self.assertTrue(any("DRIFT" in error for error in v.observe_captured_work_item_history(fresh).diagnostics))

    def test_real_custody_envelope_is_a_locator_and_preserves_raw_identity(self):
        raw = self.ledger()
        metadata, errors = [], []
        events = v.load_jsonl(self.item / "agent-runs.jsonl", errors, metadata, raw)
        self.assertEqual(errors, [])
        content = (self.item / "design.md").read_bytes()
        digest = sha(content)
        envelope = self.owner._historical_pass_association(raw, events[-1], 3, metadata[-1]["sha256"], digest)
        custody = self.item / "review-artifact-custody"
        (custody / "historical-pass").mkdir(parents=True)
        (custody / digest).write_bytes(content)
        association = custody / "historical-pass" / f"{metadata[-1]['sha256']}.json"
        association.write_bytes(v._canonical_projection_bytes(envelope))
        binding = self.binding()
        before = v.observe_captured_work_item_history(binding)
        self.assertEqual(before.diagnostics, ())
        retained = self.relocate(binding)
        self.assertEqual(before, v.observe_captured_work_item_history(retained))
        row = next(record for record in retained.files if record.original_path.endswith(association.name))
        altered = dict(envelope, runId="wrong-raw-identity")
        row.snapshot.path.write_bytes(v._canonical_projection_bytes(altered))
        snapshot = self.owner._capture_file_snapshot(row.snapshot.path, failure_id="WI-TEST-CAPTURE")
        corrupt_row = replace(row, snapshot=snapshot, byte_length=snapshot.length, sha256=sha(snapshot.data))
        corrupted = replace(retained, files=tuple(corrupt_row if record is row else record for record in retained.files))
        rejected = v.observe_captured_work_item_history(corrupted)
        self.assertTrue(any("CUSTODY" in error or "DRIFT" in error for error in rejected.diagnostics))

    def test_item_and_repository_targets_do_not_alias_after_old_paths_disappear(self):
        self.ledger(modern=True)
        (self.item / "proof.md").write_bytes(b"item proof\n")
        (self.root / "proof.md").write_bytes(b"repository proof\n")
        other = self.root / "proofs/proof.md"
        other.parent.mkdir()
        other.write_bytes(b"second basename proof\n")
        base = self.item.relative_to(self.root).as_posix()
        binding = self.binding(extra_absent=(f"{base}/proofs/proof.md",))
        retained = self.relocate(binding)
        for path in (self.root / "proof.md", other):
            path.unlink()
        view = v._acquire_captured_history_item(retained)
        errors = []
        selected = v.resolve_work_item_path(view, "proof.md", "artifact", "run-target-001", errors)
        second = v.resolve_work_item_path(view, "proofs/proof.md", "artifact", "run-target-002", errors)
        self.assertEqual(errors, [])
        self.assertEqual(selected.read_bytes(), b"item proof\n")
        if os.name == "nt":
            native_equivalent = v.resolve_work_item_path(view, "Proof.md", "artifact", "run-target-003", errors)
            self.assertEqual(native_equivalent.read_bytes(), b"item proof\n")
        self.assertEqual(v.repo_root_for(view).joinpath("proof.md").read_bytes(), b"repository proof\n")
        self.assertEqual(second.read_bytes(), b"second basename proof\n")
        self.assertFalse((view / "unknown.md").exists())
        with self.assertRaises(FileNotFoundError):
            (view / "unknown.md").read_bytes()

    def test_degraded_evidence_and_unsafe_original_locators_refuse(self):
        self.ledger()
        binding = self.binding()
        for value in ("../escape", "C:/escape", "directory\\file", "", ".", "file\x00"):
            with self.subTest(locator=value):
                rejected = v.observe_captured_work_item_history(replace(binding, original_ledger_path=value))
                self.assertTrue(rejected.diagnostics)
                self.assertIsNone(rejected.obligations)
        malformed = self.binding(criteria_data=b"")
        self.assertTrue(any("evidence is empty" in error for error in v.observe_captured_work_item_history(malformed).diagnostics))

    def test_actual_lifecycle_producer_under_distinct_module_name(self):
        self.ledger()
        binding = self.binding()
        spec = importlib.util.spec_from_file_location("legacy_binding_other_native_owner", ROOT / "scripts/mutate-work-item.py")
        other = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = other
        spec.loader.exec_module(other)
        records = tuple(replace(record, snapshot=other._capture_file_snapshot(
            record.snapshot.path, failure_id="WI-TEST-CAPTURE"
        )) for record in binding.files)
        self.assertNotIsInstance(records[0].snapshot, self.owner.CapturedFileSnapshot)
        self.assertEqual(v.observe_captured_work_item_history(binding),
                         v.observe_captured_work_item_history(replace(binding, files=records)))
        consumer = other._validator_module()
        actual_input = consumer.CapturedWorkItemHistoryBindingV1(
            binding.repository_root, binding.work_item, binding.original_source_path,
            binding.original_item_base, binding.original_ledger_path,
            consumer.HistoricalLedgerCriteriaV1(
                binding.criteria.criteria_reference, binding.criteria.acquisition_reference,
                binding.criteria.ledger_required, binding.criteria.owner_contract,
            ),
            tuple(consumer.CapturedHistoryFileV1(row.original_path, row.snapshot, row.byte_length, row.sha256)
                  for row in records), binding.absent_paths, binding.directory_members, binding.acquired_input,
        )
        observation = consumer.observe_captured_work_item_history(actual_input)
        expected = v.observe_captured_work_item_history(binding)
        self.assertEqual(observation.diagnostics, expected.diagnostics)
        self.assertEqual(observation.ledger_sha256, expected.ledger_sha256)
        self.assertEqual(consumer._serialize_obligations(observation.obligations),
                         v._serialize_obligations(expected.obligations))

    def test_incomplete_native_capture_and_compatibility_acquisition_fail_closed(self):
        self.ledger(modern=True)
        binding = self.binding(contract="current")
        original = binding.files[0]
        partial = replace(original.snapshot, parent_chain=replace(original.snapshot.parent_chain, participants=((None, (0, 0)),)))
        malformed = replace(binding, files=(replace(original, snapshot=partial), *binding.files[1:]))
        self.assertTrue(any("native parent capture shape" in error
                            for error in v.observe_captured_work_item_history(malformed).diagnostics))
        (self.root / "work-items/decision-h1-compatibility.json").write_bytes(b"{}\n")
        incomplete = v.observe_captured_work_item_history(self.binding(contract="current"))
        self.assertTrue(any("WI-LEDGER-COMPAT-SET-TOPOLOGY" in error for error in incomplete.diagnostics))
        self.assertIsNone(incomplete.obligations)

    def test_genuine_admitted_h1_group_preserves_rows_authority_and_obligations(self):
        spec = importlib.util.spec_from_file_location("history_binding_h1_writer_fixtures",
                                                    ROOT / "tests/test_ledger_h1_activation_writer.py")
        producer = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = producer
        spec.loader.exec_module(producer)
        with tempfile.TemporaryDirectory(prefix="history-binding-test-", dir=ROOT / ".scratch") as directory:
            root = Path(directory)
            writer, _reader, request, items, paths = producer.fixture(root)
            receipt = writer.apply_sealed_prefix_activation(root, request)
            self.assertEqual(receipt["state"], "apply")
            self.assertFalse(receipt["dryRun"])
            self.assertNotIn("synthetic", json.loads(request.h1_manifest_bytes))
            self.root, self.item = root, items[0]
            self.source = root / "evidence/reader-a.md"
            self.source.parent.mkdir()
            self.source.write_bytes(b"# Original source evidence for reader-a\n")
            (self.item / "acquisition.md").write_bytes(b"Actual public owner-admitted two-member H1 input.\n")
            baseline = v.load_effective_ledger_view(root, self.item, paths[0])
            self.assertEqual(baseline.observation.activation_state, "active")
            binding = self.binding(contract="current")
            view = v._acquire_captured_history_item(binding)
            before = v.load_effective_ledger_view(v.repo_root_for(view), view, paths[0])
            self.assertEqual(before.rows, baseline.rows)
            self.assertEqual(before.view, baseline.view)
            observed = v.observe_captured_work_item_history(binding)
            self.assertTrue(observed.acquisition_complete, observed.diagnostics)
            self.assertTrue(observed.obligations.open_revise)
            retained = self.relocate(binding)
            # Remove the other original participant and the complete old H1
            # artifacts too: only the genuine retained selection may be read.
            for path in (items[1], root / "work-items/legacy-ledger-projection-manifests",
                         root / "work-items/legacy-ledger-projection-receipts", root / "work-items/decisions"):
                shutil.rmtree(path)
            for path in (root / "work-items/decision-h1-compatibility.json", root / "work-items/legacy-ledger-projections.jsonl"):
                path.unlink()
            after_view = v._acquire_captured_history_item(retained)
            after = v.load_effective_ledger_view(v.repo_root_for(after_view), after_view, paths[0])
            self.assertEqual(before.rows, after.rows)
            self.assertEqual(before.view, after.view)
            self.assertEqual(before.group_open_revise_ids, after.group_open_revise_ids)
            self.assertEqual(before.group_open_launch_ids, after.group_open_launch_ids)
            self.assertEqual(observed, v.observe_captured_work_item_history(retained))

    def settled_archived_h1(self):
        def load(name, path):
            spec = importlib.util.spec_from_file_location(name, ROOT / path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            return module
        producer = load("binding_archived_h1_producer", "tests/test_ledger_h1_activation_writer.py")
        relocation = load("binding_archived_h1_relocation", "tests/test_h1_artifact_set_relocation.py")
        writer, _reader, items, paths, receipt = producer.archive_first_activated_h1_member(self.root)
        request = relocation.prepare_relocation_request(self.root, writer)
        writer.relocate_ledger_h1_artifact_set(self.root, request, apply=True)
        self.item = self.root / receipt["archivePath"]
        self.source = self.root / "evidence" / f"{self.item.name}.md"
        self.source.parent.mkdir()
        self.source.write_bytes(b"Original archived H1 source identity evidence\n")
        (self.item / "acquisition.md").write_bytes(b"Original owner-selected archived two-participant H1 history.\n")
        location = writer.resolve_ledger_h1_artifact_set_location(self.root, input_role="repository-root")
        self.assertEqual(location.phase, "settled-archive")
        return paths, self.root / location.physical_base / "relocation-receipt.json"

    def without_captured_files(self, binding, paths):
        omitted = {path.relative_to(self.root).as_posix() for path in paths}
        records = tuple(row for row in binding.files if row.original_path not in omitted)
        acquired = self.owner.AcquiredWorkItemInputV1(self.root,
            tuple(binding.acquired_input.files[self.root / row.original_path] for row in records),
            tuple(binding.acquired_input.directories.values()))
        return replace(binding, files=records, acquired_input=acquired)

    def test_archived_h1_observation_composes_required_supporting_acquisition(self):
        # Start from an isolated genuine public-owner fixture, retaining the
        # unrelated setUp beforeimages in their separately owned temporary root.
        with tempfile.TemporaryDirectory(prefix="history-binding-test-", dir=ROOT / ".scratch") as directory:
            self.root = Path(directory)
            paths, receipt = self.settled_archived_h1()
            binding = self.binding()
            missing = v.observe_captured_work_item_history(self.without_captured_files(binding, [receipt]))
            self.assertFalse(missing.acquisition_complete, missing.diagnostics)
            self.assertTrue(any(receipt.relative_to(self.root).as_posix() in error for error in missing.diagnostics), missing.diagnostics)
            self.assertIsNone(missing.obligations)
            original_receipt = receipt.read_bytes()
            receipt.write_bytes(b"{invalid acquired receipt bytes\n")
            corrupt = v.observe_captured_work_item_history(self.binding())
            self.assertTrue(corrupt.acquisition_complete, corrupt.diagnostics)
            self.assertTrue(corrupt.diagnostics)
            self.assertIsNone(corrupt.obligations)
            receipt.write_bytes(original_receipt)
            other_ledger = self.root / paths[1]
            other_bytes = other_ledger.read_bytes()
            other_ledger.write_bytes(b"{invalid original participant ledger\n")
            incomplete_rows = v.observe_captured_work_item_history(self.binding())
            self.assertFalse(incomplete_rows.acquisition_complete, incomplete_rows.diagnostics)
            self.assertTrue(incomplete_rows.diagnostics)
            self.assertIsNone(incomplete_rows.obligations)
            other_ledger.write_bytes(other_bytes)
            binding = self.binding()
            item = v._acquire_captured_history_item(binding)
            root = v.repo_root_for(item)
            context = v._resolve_ledger_h1_selected(root, item, binding.original_ledger_path).context
            self.assertEqual(context.observation.activation_state, "active")
            self.assertTrue(any(row.epoch == "sealed-prefix" for row in context.rows))
            expected_errors, expected_states, expected_masks = [], [], []
            _active, validity, revises, launches = v._reduce_effective_current_state(
                context.rows, item, expected_errors, None, context=context)
            v._capture_obligation_state(expected_states, context.rows, revises, launches, context.unresolved_history)
            expected_masks.append({row.raw_line_ordinal: entry.authority for row, entry in zip(context.rows, validity)})
            before = v.observe_captured_work_item_history(binding)
            self.assertTrue(before.acquisition_complete, before.diagnostics)
            self.assertEqual(before.obligations, expected_states[0])
            self.assertEqual(before.authority_by_raw_line, expected_masks[0])
            original_closed = (self.item / "closure.md").read_bytes()
            self.assertIn(b"Closed: 2026-09-10T01:00:00Z", original_closed)
            before_group = v._load_effective_ledger_group(root)
            retained = self.relocate(binding)
            # The sole remaining files are current custody; no original owner
            # path may satisfy the selected group or the observation.
            current_custody = {row.snapshot.path for row in retained.files}
            for path in tuple(self.root.rglob("*")):
                if path.is_file() and path not in current_custody:
                    path.unlink()
            selected = v._acquire_captured_history_item(retained)
            self.assertEqual((selected / "closure.md").read_bytes(), original_closed)
            after_group = v._load_effective_ledger_group(v.repo_root_for(selected))
            for path in paths:
                self.assertEqual(before_group[path].rows, after_group[path].rows)
                self.assertEqual(before_group[path].view, after_group[path].view)
            self.assertEqual(before, v.observe_captured_work_item_history(retained))

    def test_archived_nonmember_does_not_acquire_unrelated_h1_participant_ledgers(self):
        with tempfile.TemporaryDirectory(prefix="history-binding-test-", dir=ROOT / ".scratch") as directory:
            self.root = Path(directory)
            paths, _receipt = self.settled_archived_h1()
            group_item = self.item
            self.item = self.root / "work-items/archive/2026-07/fixture-item"
            self.item.mkdir(parents=True)
            self.source = self.root / "evidence/fixture-item.md"
            self.source.write_bytes(b"Original unrelated archive identity\n")
            for name, raw in (("closure.md", self.closure), ("design.md", b"Original design evidence\n"),
                              ("acquisition.md", b"Original ordinary archive requirement\n")):
                (self.item / name).write_bytes(raw)
            self.ledger(modern=True)
            baseline = v.observe_captured_work_item_history(self.binding())
            binding = self.binding()
            other_ledgers = [group_item / "agent-runs.jsonl", self.root / paths[1]]
            selected = self.without_captured_files(binding, other_ledgers)
            observed = v.observe_captured_work_item_history(selected)
            self.assertEqual(observed, baseline)
            self.assertTrue(observed.acquisition_complete, observed.diagnostics)
            self.assertEqual(observed.diagnostics, ())

    def test_native_pointer_preimage_and_transfer_reads_use_same_retained_acquisition(self):
        self.ledger(modern=True)
        payload = self.item / "retained/payload.bin"
        payload.parent.mkdir()
        payload.write_bytes(b"actual owner captured preimage\n")
        receipt = self.item / "lifecycle-transition-receipt.json"
        receipt.write_bytes(v._canonical_projection_bytes({"fixture": "actual transfer authority bytes"}) + b"\n")
        binding = self.binding(contract="current")

        def observe(selected):
            view = v._acquire_captured_history_item(selected)
            errors = []
            pointer = v.resolve_scratch_pointer(view, "retained/payload.bin", "canonicalPointer", "native-pointer-run", errors)
            self.assertEqual(errors, [])
            snapshot = v.capture_retained_preimage_payload(view, {"ref": "retained/payload.bin"},
                        {"byteCount": len(b"actual owner captured preimage\n"),
                         "sha256": sha(b"actual owner captured preimage\n")})
            root = v.repo_root_for(view)
            raw = v._read_transfer_authority_bytes(root, view / "lifecycle-transition-receipt.json", maximum_bytes=4096)
            digest = v._transfer_authority_sha256(root, view / "lifecycle-transition-receipt.json", maximum_bytes=4096)
            candidates = tuple(path.relative_to(root).as_posix() for path in v._transfer_receipt_candidates(root, errors))
            self.assertEqual(errors, [])
            return pointer.read_bytes(), snapshot.data, raw, digest, candidates

        before = observe(binding)
        retained = self.relocate(binding)
        self.assertEqual(before, observe(retained))
        row = next(row for row in retained.files if row.original_path.endswith("payload.bin"))
        replacement = row.snapshot.path.with_suffix(".replacement")
        replacement.write_bytes(row.snapshot.data)
        row.snapshot.path.unlink()
        replacement.replace(row.snapshot.path)
        self.assertTrue(any("DRIFT" in error for error in v.observe_captured_work_item_history(retained).diagnostics))

    def test_actual_owner_transfer_receipt_consumer_after_original_archive_disappears(self):
        spec = importlib.util.spec_from_file_location("history_binding_transfer_fixtures",
                                                    ROOT / "tests/test_legacy_obligation_migration.py")
        producer = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = producer
        spec.loader.exec_module(producer)
        with tempfile.TemporaryDirectory(prefix="history-binding-test-", dir=ROOT / ".scratch") as directory:
            root = Path(directory)
            fixture = producer.native_transfer_fixture(root)
            actual = producer.run_transfer(fixture)
            self.assertEqual(actual["status"], "settled")
            self.assertEqual(len(actual["obligations"]), 1)
            self.root = root
            self.item = root / actual["archivePath"]
            self.source = root / "evidence" / f"{fixture['slug']}.md"
            self.source.parent.mkdir()
            self.source.write_bytes(b"Original source identity evidence\n")
            (self.item / "acquisition.md").write_bytes(b"Actual public owner settled transfer acquisition.\n")
            binding = self.binding()

            def summary(selected):
                view = v._acquire_captured_history_item(selected)
                selected_root = v.repo_root_for(view)
                errors = []
                receipts = v._transfer_receipts(selected_root, errors)
                self.assertEqual(errors, [])
                return {operation: (path.relative_to(selected_root).as_posix(), payload,
                                    archive.relative_to(selected_root).as_posix())
                        for operation, (path, payload, archive) in receipts.items()}

            before = summary(binding)
            self.assertIn(fixture["operationId"], before)
            retained = self.relocate(binding)
            self.assertEqual(before, summary(retained))

    def test_directory_names_cannot_replace_native_member_proof(self):
        self.ledger()
        binding = self.binding()
        row = next(iter(binding.acquired_input.directories.values()))
        forged = replace(row.original, members=())
        with self.assertRaisesRegex(self.owner.LifecycleError, "not owner-native"):
            self.owner.AcquiredWorkItemInputV1(self.root,
                tuple(binding.acquired_input.files.values()),
                (self.owner.CapturedInputAssociationV1(forged, row.current),
                 *tuple(binding.acquired_input.directories.values())[1:]))
        names = dict(binding.directory_members)
        names["."] = ()
        self.assertTrue(any("native proof" in error for error in
                            v.observe_captured_work_item_history(replace(binding, directory_members=names)).diagnostics))

    def test_equal_empty_members_do_not_hide_native_directory_replacement(self):
        self.ledger()
        directory = self.item / "native-empty"
        directory.mkdir()
        binding = self.binding()
        moved = directory.with_name("native-empty-original")
        directory.rename(moved)
        directory.mkdir()
        self.assertEqual(tuple(directory.iterdir()), tuple(moved.iterdir()))
        observation = v.observe_captured_work_item_history(binding)
        self.assertTrue(any("DRIFT" in error for error in observation.diagnostics), observation.diagnostics)
        self.assertIsNone(observation.obligations)

    def test_captured_root_keeps_existing_protocol_observation_guard(self):
        self.ledger()
        binding = self.binding()
        for acquired in (None, binding.acquired_input):
            with self.assertRaisesRegex(self.owner.LifecycleError, "incompatible project topology observation context"):
                self.owner._resolve_project_root_identity(self.root, input_role="repository-root",
                    acquisition_purpose="topology-observation", acquired_input=acquired)

    def retired_owner(self):
        evidence = self.root / "evidence" / self.source.name
        evidence.parent.mkdir()
        self.source.rename(evidence)
        self.source = evidence
        source = self.root / "work-items/backlog/retired-owner/source.md"
        source.parent.mkdir()
        source.write_bytes(b"# Original never-admitted proposal\n")
        self.owner.refresh_readme(self.root, allow_marker_bootstrap=True)
        return self.owner.retire_legacy_backlog(self.root, "retired-owner",
                    b"Rejected the original proposal before admission.", "2026-07-16T10:00:01Z")

    def test_actual_retired_archive_owner_uses_complete_captured_consumer_scan(self):
        self.ledger()
        retired = self.retired_owner()
        consumer = self.root / "work-items/lessons/consumer.md"
        consumer.parent.mkdir()
        consumer.write_bytes(b"# Independent current consumer\n")
        baseline = self.owner._archived_work_item_entry(retired)
        binding = self.binding()
        before = self.owner._archived_work_item_entry(retired,
                    acquired_input=v._acquire_captured_history_item(binding))
        self.assertEqual(baseline, before)
        retained = self.relocate(binding)
        shutil.rmtree(retired)
        shutil.rmtree(consumer.parent)
        self.assertEqual(before, self.owner._archived_work_item_entry(retired,
                    acquired_input=v._acquire_captured_history_item(retained)))
        omitted = tuple(row for row in retained.files if row.original_path != consumer.relative_to(self.root).as_posix())
        incomplete = self.owner.AcquiredWorkItemInputV1(self.root,
            tuple(retained.acquired_input.files[self.root / row.original_path] for row in omitted),
            tuple(retained.acquired_input.directories.values()))
        incomplete_binding = replace(retained, files=omitted, acquired_input=incomplete)
        with self.assertRaisesRegex(self.owner.LifecycleError, "exact original file bytes were not acquired"):
            self.owner._archived_work_item_entry(retired,
                acquired_input=v._acquire_captured_history_item(incomplete_binding))

    def test_actual_retired_owner_preserves_current_consumer_guard(self):
        self.ledger()
        retired = self.retired_owner()
        consumer = self.root / "work-items/lessons/consumer.md"
        consumer.parent.mkdir()
        consumer.write_bytes(b"Current citation: work-items/backlog/retired-owner/source.md\n")
        with self.assertRaisesRegex(self.owner.LifecycleError, "mutable record retains a retired backlog path"):
            self.owner._archived_work_item_entry(retired)
        binding = self.binding()
        retained = self.relocate(binding)
        shutil.rmtree(retired)
        shutil.rmtree(consumer.parent)
        with self.assertRaisesRegex(self.owner.LifecycleError, "mutable record retains a retired backlog path"):
            self.owner._archived_work_item_entry(retired,
                acquired_input=v._acquire_captured_history_item(retained))

    def test_bound_retained_consumer_reuses_actual_custody_and_native_producer(self):
        self.ledger()
        self.retired_owner()
        item = self.root / "work-items/active/native-consumer"
        payload = item / "inputs/native-before.bin"
        payload.parent.mkdir(parents=True)
        payload.write_bytes(b"Retained original citation: work-items/backlog/retired-owner/source.md\n")
        report = item / "stewardship.md"
        report.write_bytes(b"# Original stewardship evidence\n")
        digest = sha(report.read_bytes())
        profile = {"schemaVersion": 1, "kind": "retained-preimage", "workItem": item.name,
            "purpose": "historical-only", "byteCount": payload.stat().st_size,
            "sha256": sha(payload.read_bytes()),
            "provenance": {"ref": report.name, "sha256": digest, "snapshot": f"review-artifact-custody/{digest}"}}
        event = fixtures._event("original-native-stewardship", workItem=item.name,
            role="knowledge-archivist", executionRole="internal", eventKind="standalone", gate="PASS",
            artifact=report.name, artifactRevision=digest, lane="implementation", effort="high",
            evidence=[{"kind": "artifact", "ref": "inputs/native-before.bin",
                       "result": v._canonical_projection_bytes(profile).decode()}])
        writer = self.owner._load_agent_run_ledger()
        raw = (writer.serialize_event(event) + "\n").encode()
        ledger = item / "agent-runs.jsonl"
        ledger.write_bytes(raw)
        custody = item / "review-artifact-custody"
        (custody / "historical-pass").mkdir(parents=True)
        (custody / digest).write_bytes(report.read_bytes())
        envelope = self.owner._historical_pass_association(raw, event, 1, sha(raw.rstrip(b"\n")), digest)
        (custody / "historical-pass" / f"{envelope['rawLineSha256']}.json").write_bytes(v._canonical_projection_bytes(envelope))
        self.assertTrue(self.owner._retained_preimage_consumer(payload, self.root / "work-items"))
        bad = dict(event, evidence=[dict(event["evidence"][0], result=v._canonical_projection_bytes(
                    dict(profile, purpose="current-authority")).decode())])
        ledger.write_bytes((writer.serialize_event(bad) + "\n").encode())
        self.assertFalse(self.owner._retained_preimage_consumer(payload, self.root / "work-items"))
        ledger.write_bytes(raw)
        binding = self.binding()
        selected = v._acquire_captured_history_item(binding)
        self.assertTrue(self.owner._retained_preimage_consumer(payload, self.root / "work-items",
            scan_preparation=self.owner._RetainedConsumerScanPreparation(selected)))
        retained = self.relocate(binding)
        shutil.rmtree(item)
        selected = v._acquire_captured_history_item(retained)
        self.assertTrue(self.owner._retained_preimage_consumer(payload, self.root / "work-items",
            scan_preparation=self.owner._RetainedConsumerScanPreparation(selected)))

    def test_genuine_h1_receipt_corruption_and_partial_set_refuse(self):
        spec = importlib.util.spec_from_file_location("history_binding_h1_negative_fixture",
                                                    ROOT / "tests/test_ledger_h1_activation_writer.py")
        producer = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = producer
        spec.loader.exec_module(producer)
        with tempfile.TemporaryDirectory(prefix="history-binding-test-", dir=ROOT / ".scratch") as directory:
            root = Path(directory)
            writer, _reader, request, items, _paths = producer.fixture(root)
            plan = writer.preflight_sealed_prefix_activation(root, request)
            writer.apply_sealed_prefix_activation(root, request)
            self.root, self.item = root, items[0]
            self.source = root / "evidence/reader-a.md"
            self.source.parent.mkdir()
            self.source.write_bytes(b"Original source evidence\n")
            (self.item / "acquisition.md").write_bytes(b"Actual owner admitted original H1 selection.\n")
            receipt_path = root / plan.receipt_path
            raw = receipt_path.read_bytes()
            payload = json.loads(raw)
            payload["memberRecordSha256"][0] = "0" * 64
            receipt_path.write_bytes(v._canonical_projection_bytes(payload) + b"\n")
            corrupt = v.observe_captured_work_item_history(self.binding(contract="current"))
            self.assertTrue(corrupt.diagnostics)
            self.assertIsNone(corrupt.obligations)
            receipt_path.write_bytes(raw)
            dual_base = root / "work-items/archive/2026-09/dual-owner" / self.owner.LEDGER_H1_ARTIFACT_BASE
            dual_base.mkdir(parents=True)
            for name, kind in self.owner.LEDGER_H1_RELOCATION_MEMBERS:
                source, destination = root / "work-items" / name, dual_base / name
                if kind == "directory":
                    shutil.copytree(source, destination)
                else:
                    shutil.copyfile(source, destination)
            dual = v.observe_captured_work_item_history(self.binding(contract="current"))
            self.assertTrue(any("SET-TOPOLOGY" in error for error in dual.diagnostics), dual.diagnostics)
            self.assertIsNone(dual.obligations)
            shutil.rmtree(dual_base.parent)
            (root / "work-items/legacy-ledger-projections.jsonl").unlink()
            partial = v.observe_captured_work_item_history(self.binding(contract="current"))
            self.assertTrue(any("SET-TOPOLOGY" in error for error in partial.diagnostics), partial.diagnostics)
            self.assertIsNone(partial.obligations)


if __name__ == "__main__":
    unittest.main()
