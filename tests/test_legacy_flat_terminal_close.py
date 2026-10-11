"""Physical legacy terminal owner oracles; Goal integration is a separate slice."""
import contextlib
import hashlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("legacy_flat_terminal_owner", ROOT / "scripts/mutate-work-item.py")
m = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = m
SPEC.loader.exec_module(m)
v = m._validator_module()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class LegacyFlatTerminalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="flat-terminal-test-", dir=ROOT / ".scratch")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.slug = "original-flat-task"
        self.source = self.root / "work-items/backlog" / f"{self.slug}.md"
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(
            b"# Original completed flat task\r\n\r\n"
            b"Original completion: 2026-09-01T10:00:00Z\r\n"
            b"Required proof: [accepted result](../../evidence/proof.md?revision=1#accepted)\r\n"
        )
        self.accepted = self.root / "evidence/acceptance.md"
        self.accepted.parent.mkdir()
        self.accepted.write_bytes(
            b"# Accepted original task facts\n"
            b"Admission: The original flat task was authorized before its recorded completion.\n"
            b"Completion: Its useful result is the exact required proof.\n"
            b"Criteria: The original task did not require an agent ledger.\n"
            b"History acquisition: Same-item source, proof, criteria and actual bounded ledger absence.\n"
        )
        (self.accepted.parent / "proof.md").write_bytes(b"# accepted\nOriginal useful result bytes.\n")
        self.instant = "2026-10-11T10:00:00Z"
        self.closure = (
            f"Closed: {self.instant}\nOutcome: Delivered the originally accepted result.\n"
            "Evidence: accepted original completion and retained required proof\nResidual risk: none\n"
        ).encode()
        self.closure_file = self.root / "closure-input.md"
        self.closure_file.write_bytes(self.closure)
        self.bug_manifest = self.root / "evidence/bug-dispositions.json"
        self.bug_manifest.write_bytes((json.dumps({"schemaVersion": 1, "workItem": self.slug,
            "closedAt": self.instant, "bugs": []}, sort_keys=True, indent=2) + "\n").encode())
        m.refresh_readme(self.root, allow_marker_bootstrap=True)

    def reference(self, path):
        raw = path.read_bytes()
        return {"path": path.relative_to(self.root).as_posix(), "byteLength": len(raw), "sha256": digest(raw)}

    def canonical_images(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes() for path in self.root.rglob("*")
                if path.is_file() and ".scratch" not in path.relative_to(self.root).parts}

    def captured_history(self, required):
        owner = v.load_lifecycle_owner()
        directories = [self.root, *(path for path in self.root.rglob("*")
                        if path.is_dir() and ".scratch" not in path.relative_to(self.root).parts)]
        records = []
        for path in self.root.rglob("*"):
            if path.is_file() and ".scratch" not in path.relative_to(self.root).parts:
                snapshot = owner._capture_file_snapshot(path, failure_id="WI-TEST-ORIGINAL-CAPTURE")
                records.append(v.CapturedHistoryFileV1(path.relative_to(self.root).as_posix(),
                              snapshot, snapshot.length, digest(snapshot.data)))
        proofs = [owner._capture_directory_snapshot(path, failure_id="WI-TEST-ORIGINAL-DIRECTORY") for path in directories]
        acquired = owner.AcquiredWorkItemInputV1(self.root,
            tuple(owner.CapturedInputAssociationV1(row.snapshot, row.snapshot) for row in records),
            tuple(owner.CapturedInputAssociationV1(proof, proof) for proof in proofs))
        ledger = self.source.parent / "agent-runs.jsonl"
        relative = ledger.relative_to(self.root).as_posix()
        absent = () if ledger.exists() else (relative,)
        criteria = self.accepted.relative_to(self.root).as_posix()
        return v.CapturedWorkItemHistoryBindingV1(self.root, self.slug,
            self.source.relative_to(self.root).as_posix(), self.source.parent.relative_to(self.root).as_posix(),
            relative, v.HistoricalLedgerCriteriaV1(criteria, criteria, required, "current"),
            tuple(records), absent,
            {proof.path.relative_to(self.root).as_posix(): tuple(name for name, _metadata in proof.members) for proof in proofs},
            acquired)

    def test_existing_flat_close_is_directory_only_and_preserves_canonical_bytes(self):
        before = self.canonical_images()
        with self.assertRaisesRegex(m.LifecycleError, "close requires one active item"):
            m.close_item(self.root, self.slug, self.closure, self.instant)
        self.assertEqual(before, self.canonical_images())
        self.assertEqual(m.work_item_dependency_state(self.root, self.slug), "open")
        self.assertEqual(m.resolve_category(self.root, f"work-item:{self.slug}"), self.source)

    def test_actual_flat_native_history_accepts_evidenced_absence_and_real_settled_rows(self):
        optional = v.observe_captured_work_item_history(self.captured_history(False))
        self.assertTrue(optional.acquisition_complete, optional.diagnostics)
        self.assertEqual(optional.selection, "absent")
        self.assertEqual(optional.diagnostics, ())
        self.assertIsNone(optional.obligations)
        self.accepted.write_bytes(self.accepted.read_bytes().replace(b"did not require", b"required"))
        writer = m._load_agent_run_ledger()
        event = {"schemaVersion": 2, "runId": "original-verification-complete", "workItem": self.slug,
            "role": "analyst", "executionRole": "internal", "eventKind": "standalone",
            "status": "completed", "gate": "PASS", "scope": ["original required proof"],
            "artifact": "../../evidence/proof.md", "lane": "implementation", "effort": "high",
            "evidence": [{"kind": "artifact", "ref": "../../evidence/proof.md"}],
            "startedAt": "2026-09-01T09:00:00Z", "updatedAt": "2026-09-01T10:00:00Z"}
        # Keep the producer's admitted artifact namespace ordinary and exact.
        proof = self.source.parent / "proof.md"
        proof.write_bytes((self.root / "evidence/proof.md").read_bytes())
        event["artifact"] = "proof.md"
        event["evidence"][0]["ref"] = "proof.md"
        raw = (writer.serialize_event(event) + "\n").encode()
        (self.source.parent / "agent-runs.jsonl").write_bytes(raw)
        settled = v.observe_captured_work_item_history(self.captured_history(True))
        self.assertTrue(settled.acquisition_complete, settled.diagnostics)
        self.assertEqual(settled.diagnostics, ())
        self.assertEqual(settled.obligations.open_revise, ())
        self.assertEqual(settled.obligations.open_launches, ())
        self.assertEqual((self.source.parent / "agent-runs.jsonl").read_bytes(), raw)

    def legacy_request(self):
        accepted = self.reference(self.accepted)
        evidence = {"schemaVersion": 1, "kind": "legacy-work-item-evidence", "operationId": "flat-terminal-001",
            "source": self.reference(self.source),
            "acceptedEvidence": {role: accepted for role in ("admission", "completion", "criteria", "historyAcquisition")},
            "historySelection": {"originalItemBase": "work-items/backlog", "originalLedgerPath": "work-items/backlog/agent-runs.jsonl",
                "ledgerRequired": False, "ownerContract": "current", "artifacts": [self.reference(self.root / "evidence/proof.md")],
                "absentPaths": ["work-items/backlog/agent-runs.jsonl"]},
            "bugDispositions": self.reference(self.bug_manifest),
            "expectedReadmeSha256": digest((self.root / "work-items/README.md").read_bytes())}
        request = self.root / "legacy-evidence.json"
        request.write_bytes((json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode())
        arguments = ["close", "--root", str(self.root), "--slug", self.slug,
            "--closure-file", str(self.closure_file), "--terminal-instant", self.instant,
            "--legacy-evidence-file", str(request)]
        return request.read_bytes(), arguments

    def test_public_legacy_close_requires_the_additive_evidence_and_apply_surface(self):
        _evidence, arguments = self.legacy_request()
        before = self.canonical_images()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(m.main(arguments), 0)
        self.assertEqual(before, self.canonical_images())
        diagnostic = io.StringIO()
        with contextlib.redirect_stdout(diagnostic), contextlib.redirect_stderr(diagnostic):
            result = m.main([*arguments, "--apply"])
        self.assertEqual(result, 0, diagnostic.getvalue())
        archive = self.root / "work-items/archive/2026-10" / self.slug
        self.assertFalse(self.source.exists())
        self.assertEqual((archive / "legacy-source" / self.source.name).read_bytes(), before[self.source.relative_to(self.root).as_posix()])
        self.assertEqual(m.resolve_category(self.root, f"work-item:{self.slug}"), archive)
        self.assertEqual(m.work_item_dependency_state(self.root, self.slug), "done")
        self.assertNotEqual((archive / "lifecycle-transition-receipt.json").read_bytes(),
                            (archive / "bug-dispositions-receipt.json").read_bytes())

    def test_public_cli_fresh_process_readers_and_historical_replay(self):
        evidence, arguments = self.legacy_request()
        # Genuine new public helper frame, no inherited native objects.
        producer = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/mutate-work-item.py"), *arguments, "--apply"],
                                  capture_output=True, text=True, timeout=240, check=False)
        self.assertEqual(producer.returncode, 0, producer.stdout + producer.stderr)
        archive = self.root / "work-items/archive/2026-10" / self.slug
        self.assertFalse(self.source.exists())
        action_bytes = (archive / m.LEGACY_COMPLETION_RECEIPT).read_bytes()
        metadata = json.loads((archive / m.LEGACY_COMPLETION_METADATA).read_bytes())
        self.assertEqual(metadata["schemaVersion"], 2)
        self.assertNotIn("identity", metadata["historyBinding"]["origin"])
        self.assertIn("evidence/proof.md", (archive / "closure.md").read_text())
        code = """import importlib.util,sys
from pathlib import Path
s=importlib.util.spec_from_file_location('public_flat_reader',sys.argv[1]);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
root=Path(sys.argv[2]);slug=sys.argv[3]
assert m.main(['resolve','--root',str(root),'--reference','work-item:'+slug])==0
assert m.work_item_dependency_state(root,slug)=='done'
assert m.resolve_legacy_path(root,'work-items/backlog/'+slug+'.md').name==slug+'.md'
m.check_readme(root)
assert m.audit(root)==(), m.audit(root)
print('FRESH_PUBLIC_READERS_OK')
"""
        reader = subprocess.run([sys.executable, "-B", "-c", code, str(ROOT / "scripts/mutate-work-item.py"),
                                 str(self.root), self.slug], capture_output=True, text=True, timeout=240, check=False)
        self.assertEqual(reader.returncode, 0, reader.stdout + reader.stderr)
        self.assertIn("FRESH_PUBLIC_READERS_OK", reader.stdout)
        board = self.root / "work-items/README.md"
        board.write_bytes(b"Lawful later guide update.\n\n" + board.read_bytes())
        m.close_item(self.root, self.slug, self.closure, self.instant, legacy_evidence_data=evidence, apply=True)
        self.assertEqual(action_bytes, (archive / m.LEGACY_COMPLETION_RECEIPT).read_bytes())
        observed = m.observe_work_item_terminal(self.root, f"work-item:{self.slug}")
        self.assertTrue(observed.acquisition_complete)
        self.assertEqual(observed.terminal_instant, self.instant)
        observed.verify()
        with self.assertRaises(m.LifecycleError):
            m.WorkItemTerminalObservation()
        altered = json.loads(evidence); altered["operationId"] = "different-operation"
        with self.assertRaisesRegex(m.LifecycleError, "replay request differs"):
            m.close_item(self.root, self.slug, self.closure, self.instant,
                         legacy_evidence_data=m._migration_receipt_bytes(altered), apply=True)
        (archive / m.LEGACY_COMPLETION_METADATA).unlink()
        with self.assertRaises(m.LifecycleError):
            m.resolve_category(self.root, f"work-item:{self.slug}")
        with self.assertRaises(m.LifecycleError):
            m.resolve_legacy_path(self.root, (archive / "closure.md").relative_to(self.root).as_posix())

    def test_board_before_action_receipt_is_pending_and_matching_reentry_recovers(self):
        evidence, _arguments = self.legacy_request()
        with self.assertRaisesRegex(m.LifecycleError, "interruption after derived board"):
            m.close_item(self.root, self.slug, self.closure, self.instant,
                         legacy_evidence_data=evidence, apply=True, inject_failure_at="after-board")
        archive = self.root / "work-items/archive/2026-10" / self.slug
        self.assertFalse(self.source.exists())
        self.assertFalse((archive / m.LEGACY_COMPLETION_RECEIPT).exists())
        for reader in (lambda: m.resolve_category(self.root, f"work-item:{self.slug}"),
                       lambda: m.work_item_dependency_state(self.root, self.slug),
                       lambda: m.render_readme_bytes(self.root)):
            with self.assertRaises(m.LifecycleError):
                reader()
        observed = m.observe_work_item_terminal(self.root, f"work-item:{self.slug}")
        self.assertFalse(observed.acquisition_complete)
        self.assertIsNone(observed.terminal_disposition)
        self.assertIsNone(observed.terminal_instant)
        self.assertTrue(any("PENDING" in diagnostic for diagnostic in observed.diagnostics))
        m.close_item(self.root, self.slug, self.closure, self.instant, legacy_evidence_data=evidence, apply=True)
        self.assertEqual(m.work_item_dependency_state(self.root, self.slug), "done")
        self.assertFalse(m._transition_intent_path(self.root, "flat-terminal-001").exists())
        m.check_readme(self.root)

    def _finalization_cut(self, cut, *, caught=False):
        evidence, _arguments = self.legacy_request()
        intent_path = m._transition_intent_path(self.root, "flat-terminal-001")
        save, remove, unlink = m._legacy_save_intent, m.LifecycleWriteTarget.remove_owned, Path.unlink
        fired = []
        def saved(path, intent):
            result = save(path, intent)
            source = next((b for b in intent["capturedBindings"] if b.get("imageIndex") is not None
                and intent["preparedImages"][b["imageIndex"]]["disposition"] == "source"), None)
            if not fired and cut == "saved-null" and source is not None and "holdPath" in source and source["holdPath"] is None:
                fired.append(cut)
                raise m.LifecycleError("WI-TEST-FINALIZATION", cut)
            return result
        def removed(owner, name, image):
            result = remove(owner, name, image)
            if cut == "remove-before-save" and name.startswith(f".{self.source.name}.") and name.endswith(".hold"):
                fired.append(cut)
                raise m.LifecycleError("WI-TEST-FINALIZATION", cut)
            return result
        def unlinked(path, *args, **kwargs):
            if cut == "last-cleanup" and path == intent_path:
                fired.append(cut)
                raise m.LifecycleError("WI-TEST-FINALIZATION", cut)
            return unlink(path, *args, **kwargs)
        m._legacy_save_intent, m.LifecycleWriteTarget.remove_owned, Path.unlink = saved, removed, unlinked
        try:
            with self.assertRaisesRegex(m.LifecycleError, cut):
                m.close_item(self.root, self.slug, self.closure, self.instant,
                    legacy_evidence_data=evidence, apply=True, inject_failure_at=None if caught else "b1-owned-fixture")
        finally:
            m._legacy_save_intent, m.LifecycleWriteTarget.remove_owned, Path.unlink = save, remove, unlink
        self.assertEqual(fired, [cut])
        return evidence, intent_path

    def _assert_finalization_recovery(self, cut):
        original = self.source.read_bytes()
        _evidence, intent_path = self._finalization_cut(cut)
        archive = self.root / "work-items/archive/2026-10" / self.slug
        immutable = {path: path.read_bytes() for path in archive.rglob("*") if path.is_file()}
        self.assertFalse(self.source.exists())
        self.assertEqual((archive / "legacy-source" / self.source.name).read_bytes(), original)
        with self.assertRaises(m.LifecycleError):
            m.work_item_dependency_state(self.root, self.slug)
        action = m.recover_transition(self.root, "flat-terminal-001")
        self.assertEqual(action["status"], "settled")
        self.assertFalse(intent_path.exists())
        self.assertFalse(self.source.exists())
        self.assertEqual(immutable, {path: path.read_bytes() for path in archive.rglob("*") if path.is_file()})
        self.assertFalse(list(self.root.rglob("*.hold")))
        self.assertFalse((self.root / ".scratch/work-items/legacy-flat-terminal").exists())
        self.assertEqual(m.resolve_category(self.root, f"work-item:{self.slug}"), archive)
        self.assertEqual(m.work_item_dependency_state(self.root, self.slug), "done")
        m.check_readme(self.root)

    def test_b1_saved_null_hold_resumes_only_finalization(self):
        self._assert_finalization_recovery("saved-null")

    def test_b1_image_observation_never_creates_namespace_and_absence_has_complete_parents(self):
        def namespace():
            return {str(p.relative_to(self.root)): (p.is_dir(), m._lifecycle_file_identity(p.lstat()))
                    for p in self.root.rglob("*")}
        before = namespace()
        missing = self.root / "missing-parent/deeper/leaf.bin"
        with self.assertRaisesRegex(m.LifecycleError, "existing-parent acquisition failed"):
            m._legacy_local_image(missing)
        self.assertEqual(namespace(), before)
        absent = self.root / "evidence/genuinely-absent.bin"
        image, parents = m._legacy_local_image(absent)
        self.assertIsNone(image)
        self.assertEqual([p["path"] for p in parents], [str(p) for p in reversed(absent.parents)])
        self.assertEqual(parents[-1]["identity"], list(m._lifecycle_file_identity(absent.parent.lstat())))
        self.assertEqual(namespace(), before)
        actual = self.root / "evidence/native-image.bin"
        actual.write_bytes(b"real native image bytes\n")
        image, parents = m._legacy_local_image(actual)
        self.assertEqual(m._unb64(image["data"]), actual.read_bytes())
        self.assertEqual(image["sha256"], digest(actual.read_bytes()).upper())
        self.assertEqual(image["identity"]["value"], list(m._lifecycle_file_identity(actual.lstat())))

    def test_b1_image_observation_drift_read_and_release_failures_are_not_absence(self):
        owners = []
        acquire, owned, read, close = (m.LifecycleWriteTarget._acquire_existing_parents,
            m.LifecycleWriteTarget.owned_image, m.LifecycleWriteTarget._read_handle, m.LifecycleWriteTarget._close)
        def retained(target):
            owners.append(target)
            return acquire(target)
        m.LifecycleWriteTarget._acquire_existing_parents = retained
        parent = self.root / "observation-parent"; parent.mkdir()
        leaf = parent / "absent.bin"
        moved = self.root / "fixture-held-parent"
        def parent_drift(target, *args, **kwargs):
            result = owned(target, *args, **kwargs)
            if target.path == leaf:
                parent.rename(moved); parent.mkdir()
            return result
        try:
            unsafe = self.root / "non-directory-parent"
            unsafe.write_bytes(b"an ordinary file cannot be a native parent\n")
            before_unsafe = tuple((str(p.relative_to(self.root)), m._lifecycle_file_identity(p.lstat()))
                                  for p in self.root.rglob("*"))
            with self.assertRaisesRegex(m.LifecycleError, "existing-parent acquisition failed"):
                m._legacy_local_image(unsafe / "leaf.bin")
            self.assertEqual(before_unsafe, tuple((str(p.relative_to(self.root)), m._lifecycle_file_identity(p.lstat()))
                                                  for p in self.root.rglob("*")))
            m.LifecycleWriteTarget.owned_image = parent_drift
            with self.assertRaisesRegex(m.LifecycleError, "existing-parent acquisition failed") as denied_parent:
                m._legacy_local_image(leaf)
            # The observed NT sharing contract prevents replacement while this
            # parent is held. Preserve that guard, expose its cause, never mint a
            # replacement or relax native access merely to force a drift fixture.
            self.assertIsInstance(denied_parent.exception.__cause__, PermissionError)
            self.assertTrue(parent.exists())
            self.assertFalse(moved.exists())
            self.assertFalse(leaf.exists())
            m.LifecycleWriteTarget.owned_image = owned
            current = parent / "present.bin"; current.write_bytes(b"present before native read\n")
            replacement = parent / "replacement.bin"; replacement.write_bytes(current.read_bytes())
            held = self.root / "fixture-held-leaf.bin"
            fired = []
            def leaf_drift(target, handle, maximum_bytes):
                result = read(target, handle, maximum_bytes)
                if target.path == current and not fired:
                    fired.append(True); current.rename(held); replacement.rename(current)
                return result
            m.LifecycleWriteTarget._read_handle = leaf_drift
            with self.assertRaisesRegex(m.LifecycleError, "changed during readback"):
                m._legacy_local_image(current)
            self.assertEqual(held.read_bytes(), current.read_bytes())
            m.LifecycleWriteTarget._read_handle = read
            def read_failure(target, handle, maximum_bytes):
                raise OSError("fixture actual read failure")
            m.LifecycleWriteTarget._read_handle = read_failure
            with self.assertRaisesRegex(m.LifecycleError, "actual read failure"):
                m._legacy_local_image(current)
            m.LifecycleWriteTarget._read_handle = read
            released = []
            def release_failure(target, handle):
                result = close(target, handle)
                if not released:
                    released.append(True)
                    raise OSError("fixture release failure after real native close")
                return result
            m.LifecycleWriteTarget._close = release_failure
            with self.assertRaisesRegex(m.LifecycleError, "handle release.*existing-parent acquisition failed.*release failure"):
                m._legacy_local_image(self.root / "another-missing-parent/leaf.bin")
        finally:
            m.LifecycleWriteTarget._acquire_existing_parents = acquire
            m.LifecycleWriteTarget.owned_image = owned
            m.LifecycleWriteTarget._read_handle = read
            m.LifecycleWriteTarget._close = close
        self.assertTrue(owners)
        self.assertTrue(all(not target._open and not target._directories for target in owners))

    def test_b1_removed_hold_before_save_resumes_only_finalization(self):
        self._assert_finalization_recovery("remove-before-save")

    def test_b1_last_cleanup_resumes_without_expired_parent_identity(self):
        self._assert_finalization_recovery("last-cleanup")

    def test_b1_caught_late_failure_keeps_primary_and_never_claims_completed_rollback(self):
        rollbacks = []
        composer_type = m.LifecycleOutcomeComposer
        original = composer_type.set_rollback
        def recorded(composer, state):
            rollbacks.append(state)
            return original(composer, state)
        composer_type.set_rollback = recorded
        try:
            _evidence, intent_path = self._finalization_cut("saved-null", caught=True)
        finally:
            composer_type.set_rollback = original
        self.assertIn("incomplete", rollbacks)
        self.assertNotIn("completed", rollbacks)
        self.assertFalse(intent_path.exists())
        self.assertFalse(self.source.exists())
        self.assertEqual(m.work_item_dependency_state(self.root, self.slug), "done")

    def test_b1_remaining_native_objects_and_incomplete_proof_never_falsely_settle(self):
        evidence, intent_path = self._finalization_cut("saved-null")
        archive = self.root / "work-items/archive/2026-10" / self.slug
        intent = json.loads(intent_path.read_bytes())
        bindings = intent["capturedBindings"]
        readme_binding = next(b for b in bindings if b.get("imageIndex") is not None
            and intent["preparedImages"][b["imageIndex"]]["disposition"] == "readme")
        hold = Path(readme_binding["holdPath"])
        receipt = archive / m.LEGACY_COMPLETION_RECEIPT

        def refusal(pattern):
            before = intent_path.read_bytes()
            with self.assertRaisesRegex(m.LifecycleError, pattern):
                m.recover_transition(self.root, "flat-terminal-001")
            self.assertEqual(intent_path.read_bytes(), before)
            with self.assertRaises(m.LifecycleError):
                m.work_item_dependency_state(self.root, self.slug)

        def replace_file(path, raw, label, pattern):
            image, _ = m._legacy_local_image(path)
            original = self.root / f"fixture-original-{label}.bin"
            preserved = self.root / f"fixture-foreign-{label}.bin"
            m._legacy_move_owned(path, original, image)
            m._atomic_write(path, raw)
            foreign, _ = m._legacy_local_image(path)
            self.assertNotEqual(foreign["identity"], image["identity"])
            refusal(pattern)
            self.assertEqual(path.read_bytes(), raw)
            m._legacy_move_owned(path, preserved, foreign)
            m._legacy_move_owned(original, path, image)
            self.assertEqual(preserved.read_bytes(), raw)

        # Each replacement keeps the original native object alive, so equal bytes
        # cannot accidentally reuse its file ID. The fixture actor reconciles its
        # own replacement; the lifecycle owner must preserve it and the intent.
        replace_file(hold, hold.read_bytes(), "hold", "owned|image|native")
        retained = archive / "legacy-source" / self.source.name
        replace_file(retained, retained.read_bytes(), "postimage", "indeterminate finalization")
        replace_file(receipt, b"{corrupt action bytes\n", "receipt", "indeterminate finalization")

        # Missing binding plus absent current leaf must not pass None == None.
        board = self.root / "work-items/README.md"
        board_image, _ = m._legacy_local_image(board)
        board_saved = self.root / "fixture-current-board.bin"
        m._legacy_move_owned(board, board_saved, board_image)
        readme_binding["postImage"] = None
        m._legacy_save_intent(intent_path, intent)
        refusal("indeterminate finalization")
        m._legacy_move_owned(board_saved, board, board_image)
        readme_binding["postImage"] = board_image
        m._legacy_save_intent(intent_path, intent)
        changed_request = json.loads(evidence)
        changed_request["expectedReadmeSha256"] = "0" * 64
        with self.assertRaisesRegex(m.LifecycleError, "pending replay request differs"):
            m.close_item(self.root, self.slug, self.closure, self.instant,
                legacy_evidence_data=json.dumps(changed_request).encode(), apply=True)

        created = next(b for b in reversed(bindings) if b["nodeKind"] == "directory"
            and b["role"] == "actually-created" and Path(b["path"]).is_relative_to(self.root / ".scratch")
            and Path(b["path"]).exists())
        parent = Path(created["path"])
        original_parent = self.root / "fixture-original-parent"
        foreign_parent = self.root / "fixture-foreign-parent"
        m._legacy_move_owned(parent, original_parent, None, directory_identity=created["identity"])
        foreign_binding = m._legacy_create_directory(parent)
        self.assertNotEqual(foreign_binding["identity"], created["identity"])
        with self.assertRaisesRegex(m.LifecycleError, "parent identity changed|stage parent changed"):
            m.recover_transition(self.root, "flat-terminal-001")
        self.assertTrue(parent.exists())
        self.assertTrue(intent_path.exists())
        m._legacy_move_owned(parent, foreign_parent, None, directory_identity=foreign_binding["identity"])
        m._legacy_move_owned(original_parent, parent, None, directory_identity=created["identity"])
        foreign_child = parent / "fixture-foreign-child.bin"
        foreign_child.write_bytes(b"fixture-owned child must survive recovery refusal\n")
        with self.assertRaises((m.LifecycleError, OSError)):
            m.recover_transition(self.root, "flat-terminal-001")
        self.assertEqual(foreign_child.read_bytes(), b"fixture-owned child must survive recovery refusal\n")
        self.assertTrue(intent_path.exists())
        foreign_child.rename(self.root / "fixture-preserved-child.bin")
        m.recover_transition(self.root, "flat-terminal-001")
        self.assertFalse(intent_path.exists())
        self.assertFalse(self.source.exists())
        self.assertEqual(m.work_item_dependency_state(self.root, self.slug), "done")
        m.check_readme(self.root)

    def test_creator_rollback_and_foreign_replacement_preserve_then_real_recovery(self):
        evidence, _arguments = self.legacy_request()
        before = self.canonical_images()
        move = m._legacy_move_owned
        def refuse_promotion(path, destination, image, **kwargs):
            if image is None:
                raise m.LifecycleError("WI-TEST-PROMOTION", "actual pre-promotion fault")
            return move(path, destination, image, **kwargs)
        m._legacy_move_owned = refuse_promotion
        try:
            with self.assertRaisesRegex(m.LifecycleError, "actual pre-promotion fault"):
                m.close_item(self.root, self.slug, self.closure, self.instant, legacy_evidence_data=evidence, apply=True)
        finally:
            m._legacy_move_owned = move
        self.assertEqual(before, self.canonical_images())
        self.assertFalse(m._transition_intent_path(self.root, "flat-terminal-001").exists())
        self.assertEqual(m.work_item_dependency_state(self.root, self.slug), "open")
        archive = self.root / "work-items/archive/2026-10" / self.slug
        retained = archive / "legacy-source" / self.source.name
        foreign = b"caller-owned replacement must be preserved\n"
        def replace_after_promotion(path, destination, image, **kwargs):
            result = move(path, destination, image, **kwargs)
            if image is None:
                m._atomic_write(retained, foreign)
            return result
        m._legacy_move_owned = replace_after_promotion
        try:
            with self.assertRaisesRegex(m.LifecycleError, "compensation"):
                m.close_item(self.root, self.slug, self.closure, self.instant, legacy_evidence_data=evidence, apply=True)
        finally:
            m._legacy_move_owned = move
        self.assertEqual(retained.read_bytes(), foreign)
        self.assertTrue(m._transition_intent_path(self.root, "flat-terminal-001").exists())
        with self.assertRaises(m.LifecycleError):
            m.work_item_dependency_state(self.root, self.slug)
        # The fixture actor reconciles its own injected object through a retained
        # native image; the lifecycle owner never removes the foreign replacement.
        foreign_image, _parents = m._legacy_local_image(retained)
        preserved = self.root / "foreign-preserved.bin"
        move(retained, preserved, foreign_image)
        action = m.recover_transition(self.root, "flat-terminal-001")
        self.assertEqual(action["status"], "settled")
        self.assertEqual(preserved.read_bytes(), foreign)
        self.assertEqual(m.work_item_dependency_state(self.root, self.slug), "done")
        m.check_readme(self.root)

    def test_real_bug_incoming_documents_and_distinct_same_basename_targets(self):
        spec = importlib.util.spec_from_file_location("flat_terminal_bug_producer", ROOT / "tests/test_mutate_work_item.py")
        producer = importlib.util.module_from_spec(spec); sys.modules[spec.name] = producer; spec.loader.exec_module(producer)
        bug = producer.seed_context_bug(self.root, self.slug, "2026-10-11-flat-bug")
        bug.write_bytes(bug.read_bytes() + f"[Source](../backlog/{self.slug}.md#accepted)\n".encode())
        bug_before = bug.read_bytes()
        manifest = {"schemaVersion": 1, "workItem": self.slug, "closedAt": self.instant, "bugs": [{
            "id": bug.stem, "action": "terminalize", "inputSha256": digest(bug_before),
            "status": "fixed", "resolution": "Accepted original resolution", "evidence": "Original proof"}]}
        self.bug_manifest.write_bytes(m._migration_receipt_bytes(manifest))
        second = self.root / "evidence/second/proof.md"; second.parent.mkdir(); second.write_bytes(b"Distinct second proof bytes\n")
        self.source.write_bytes(self.source.read_bytes() + b"[Second](../../evidence/second/proof.md#second)\n")
        document = self.root / "work-items/design.md"
        document.write_bytes((f"Logical work-item:{self.slug}\n[Source](backlog/{self.slug}.md#accepted)\n"
                              f"Literal work-items/backlog/{self.slug}.md\n").encode())
        m.refresh_readme(self.root)
        evidence, _arguments = self.legacy_request()
        payload = json.loads(evidence); payload["historySelection"]["artifacts"].append(self.reference(second))
        evidence = m._migration_receipt_bytes(payload)
        archive = m.close_item(self.root, self.slug, self.closure, self.instant, legacy_evidence_data=evidence, apply=True)
        metadata = json.loads((archive / m.LEGACY_COMPLETION_METADATA).read_bytes())
        rows = [row for row in metadata["custodyMap"] if row["originalPath"].endswith("proof.md")]
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]["preservedPath"], rows[1]["preservedPath"])
        self.assertNotEqual(rows[0]["sha256"], rows[1]["sha256"])
        for row in rows:
            self.assertEqual(digest((archive / row["preservedPath"]).read_bytes()), row["sha256"])
        final_bug = self.root / "work-items/bugs/archive/2026-10" / bug.name
        self.assertFalse(bug.exists())
        self.assertIn("legacy-source", final_bug.read_text())
        self.assertIn("legacy-source", document.read_text())
        bug_receipt = json.loads((archive / m.BUG_DISPOSITIONS_RECEIPT).read_bytes())
        self.assertEqual(bug_receipt["schemaVersion"], 1)
        self.assertEqual(bug_receipt["bugs"][0]["afterSha256"], digest(final_bug.read_bytes()))
        self.assertEqual(bug_receipt["linkMaintenance"]["consumers"][0]["authority"], "selected-terminalize")
        self.assertTrue(any("work-item:" in row["value"] for row in json.loads(
            (archive / m.LEGACY_COMPLETION_RECEIPT).read_bytes())["links"]["inventory"]["references"]))
        m.check_readme(self.root)

    def test_ordinary_close_terminalized_link_overlap_contract_remains(self):
        spec = importlib.util.spec_from_file_location("flat_terminal_ordinary_guard", ROOT / "tests/test_mutate_work_item.py")
        guard = importlib.util.module_from_spec(spec); sys.modules[spec.name] = guard; spec.loader.exec_module(guard)
        guard.test_close_terminalize_link_overlap_uses_final_consumer_location(self.root / "ordinary-guard")

    def component_settled_record(self, binding=None):
        # Explicit component data, not a public physical-close or helper frame.
        supplied_history = binding is not None
        binding = binding or self.captured_history(False)
        selected_paths = ({self.root / row.original_path for row in binding.files} if supplied_history
                          else {self.source, self.accepted, self.root / "evidence/proof.md"})
        # Recapture through the exact emitting owner, before effects. Module
        # aliases used by genuine fixture builders retain their own seal tokens.
        files = [m._capture_file_snapshot(path, failure_id="WI-COMPONENT-ORIGINAL") for path in selected_paths]
        directories = [m._capture_directory_snapshot(self.root / relative, failure_id="WI-COMPONENT-ORIGINAL")
                       for relative in binding.directory_members]
        live = m.AcquiredWorkItemInputV1(self.root,
            tuple(m.CapturedInputAssociationV1(row, row) for row in files),
            tuple(m.CapturedInputAssociationV1(row, row) for row in directories))
        cells = []
        for index, path in enumerate(sorted(selected_paths)):
            reference = self.reference(path)
            preserved = (f"legacy-source/{path.name}" if path == self.source else
                         f"history/{index}/{path.name}" if supplied_history else path.relative_to(self.root).as_posix())
            cells.append({"originalPath": reference["path"], "preservedPath": preserved,
                          "byteLength": reference["byteLength"], "sha256": reference["sha256"]})
        source = next(row for row in cells if row["originalPath"] == self.source.relative_to(self.root).as_posix())
        accepted = {}
        for role in ("admission", "completion", "criteria", "historyAcquisition"):
            locator = (binding.criteria.acquisition_reference if role == "historyAcquisition" else binding.criteria.criteria_reference)
            cell = next(row for row in cells if row["originalPath"] == locator)
            accepted[role] = {"originalPath": cell["originalPath"], "path": cell["preservedPath"],
                              "byteLength": cell["byteLength"], "sha256": cell["sha256"]}
        history = {"originalSourcePath": source["originalPath"], "originalItemBase": binding.original_item_base,
            "originalLedgerPath": binding.original_ledger_path,
            "criteria": {"criteriaReference": binding.criteria.criteria_reference,
                         "acquisitionReference": binding.criteria.acquisition_reference,
                         "ledgerRequired": binding.criteria.ledger_required, "ownerContract": binding.criteria.owner_contract},
            "absentPaths": list(binding.absent_paths)}
        proof = next((row for row in cells if row["originalPath"] == "evidence/proof.md"), None)
        required = [] if supplied_history else [{"sourcePath": source["preservedPath"], "sourceSha256": source["sha256"],
            "originalHref": "../../evidence/proof.md?revision=1#accepted", "originalTarget": "evidence/proof.md",
            "retainedTarget": proof["preservedPath"], "targetByteLength": proof["byteLength"], "targetSha256": proof["sha256"],
            "suffix": "?revision=1#accepted", "acceptanceEvidence": {key: accepted["completion"][key] for key in ("path", "byteLength", "sha256")}}]
        metadata_bytes = m._legacy_work_item_metadata_bytes(live, operation_id="component-origin-001", work_item=self.slug,
            terminal_instant=self.instant, source=source, accepted_evidence=accepted, history_binding=history,
            custody_map=cells, required_evidence_links=required)
        metadata = json.loads(metadata_bytes)
        archive = self.root / "work-items/archive/2026-10" / self.slug
        archive.mkdir(parents=True)
        for cell in cells:
            destination = archive / cell["preservedPath"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(live.files[self.root / cell["originalPath"]].original.data)
        (archive / m.LEGACY_COMPLETION_METADATA).write_bytes(metadata_bytes)
        (archive / "closure.md").write_bytes(self.closure)
        manifest = m._migration_receipt_bytes({"schemaVersion": 1, "workItem": self.slug, "closedAt": self.instant, "bugs": []})
        (archive / m.BUG_DISPOSITIONS_MANIFEST).write_bytes(manifest)
        board_hash = digest((self.root / "work-items/README.md").read_bytes())
        bug_receipt = m._bug_disposition_receipt_bytes(self.root, self.slug, self.instant, manifest, self.closure, (), board_hash)
        (archive / m.BUG_DISPOSITIONS_RECEIPT).write_bytes(bug_receipt)
        snapshots = [m._capture_file_snapshot(path, failure_id="WI-COMPONENT-CURRENT") for path in archive.rglob("*") if path.is_file()]
        action = {"schemaVersion": 1, "owner": m.LEGACY_COMPLETION_OWNER, "kind": m.LEGACY_COMPLETION_KIND,
            "status": "settled", "operationId": "component-origin-001", "workItem": self.slug, "terminalInstant": self.instant,
            "requestSha256": digest(b"explicit synthetic component record"), "metadataSha256": digest(metadata_bytes),
            "archivePath": archive.relative_to(self.root).as_posix(), "archiveMembershipSha256": m._legacy_archive_membership(snapshots, archive),
            "closureInputSha256": digest(self.closure), "closureSha256": digest(self.closure), "bugDispositionReceiptSha256": digest(bug_receipt),
            "historySelectionSha256": digest(m._projection_json(metadata["historyBinding"])),
            "links": {"inventory": {"result": "clear", "references": []}, "consumers": []},
            "readme": {"beforeSha256": board_hash, "afterSha256": board_hash},
            "provenance": {"actor": "explicit synthetic component fixture", "actualExecutionPath": "manual-equivalent",
                           "targetImplementationSha256": None, "runtimeMetadata": "unspecified by runtime"}}
        (archive / m.LEGACY_COMPLETION_RECEIPT).write_bytes(m._legacy_work_item_action_receipt_bytes(action))
        for path in selected_paths:
            path.unlink()
        for path in sorted((path for path in self.root.rglob("*") if path.is_dir() and not path.is_relative_to(archive)),
                           key=lambda path: len(path.parts), reverse=True):
            if not any(path.iterdir()):
                path.rmdir()
        return archive, metadata, action

    def test_settled_constructor_protocol_and_actual_observer_after_originals_disappear(self):
        archive, metadata, _action = self.component_settled_record()
        port = m.acquire_settled_work_item_history(self.root, f"work-item:{self.slug}")
        self.assertEqual(port.metadata["schemaVersion"], 2)
        self.assertFalse(self.source.exists())
        self.assertEqual(port.origin_entry(self.source).kind, "file")
        self.assertIsNone(port.origin_entry(self.source.parent / "agent-runs.jsonl"))
        with self.assertRaisesRegex(m.LifecycleError, "topology was not acquired"):
            port.origin_entry(self.root / ".scratch/unobserved/file")
        binding = v.bind_settled_work_item_history(port)
        observed = v.observe_captured_work_item_history(binding)
        self.assertTrue(observed.acquisition_complete, observed.diagnostics)
        self.assertEqual(observed.diagnostics, ())
        self.assertEqual(observed.selection, "absent")
        self.assertIsNone(observed.obligations)
        with self.assertRaises(m.LifecycleError):
            m.SettledWorkItemHistoryInputV1()
        copied = object.__new__(m.SettledWorkItemHistoryInputV1)
        for key in port.__dataclass_fields__:
            object.__setattr__(copied, key, getattr(port, key))
        with self.assertRaisesRegex(m.LifecycleError, "not minted for this acquisition"):
            copied.verify()
        source = port.current_snapshot(self.source)
        self.assertEqual(source.path, archive / metadata["source"]["preservedPath"])

    def test_fresh_process_origin_constructor_and_held_native_replacement(self):
        archive, metadata, _action = self.component_settled_record()
        code = """import hashlib,importlib.util,json,sys
from pathlib import Path
source=Path(sys.argv[1]);spec=importlib.util.spec_from_file_location('fresh_settled_owner',source)
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
root=Path(sys.argv[2]);port=m.acquire_settled_work_item_history(root,sys.argv[3]);v=m._validator_module()
observed=v.observe_captured_work_item_history(v.bind_settled_work_item_history(port))
assert observed.acquisition_complete and not observed.diagnostics, observed.diagnostics
assert not (root/port.metadata['source']['originalPath']).exists()
print(json.dumps({'moduleSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'metadataVersion':port.metadata['schemaVersion'],
 'selection':observed.selection,'acquisitionComplete':observed.acquisition_complete,'originalAbsent':True}))
"""
        result = subprocess.run([sys.executable, "-B", "-c", code, str(ROOT / "scripts/mutate-work-item.py"),
            str(self.root), f"work-item:{self.slug}"], capture_output=True, text=True, timeout=90, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["moduleSha256"], digest((ROOT / "scripts/mutate-work-item.py").read_bytes()))
        self.assertEqual(payload["metadataVersion"], 2)
        self.assertEqual(payload["selection"], "absent")
        self.assertTrue(payload["originalAbsent"])
        port = m.acquire_settled_work_item_history(self.root, f"work-item:{self.slug}")
        retained_source = archive / metadata["source"]["preservedPath"]
        temporary = retained_source.with_name("same-byte-native-replacement")
        temporary.write_bytes(retained_source.read_bytes())
        retained_source.unlink()
        temporary.replace(retained_source)
        with self.assertRaisesRegex(m.LifecycleError, "changed"):
            port.verify()
        current = m.acquire_settled_work_item_history(self.root, f"work-item:{self.slug}")
        current.verify()

    def test_pending_partial_tampered_origin_and_independent_reference_refuse(self):
        archive, metadata, _action = self.component_settled_record()
        expected = {"path": metadata["acceptedEvidence"]["completion"]["path"],
                    "byteLength": metadata["acceptedEvidence"]["completion"]["byteLength"], "sha256": "0" * 64}
        with self.assertRaisesRegex(m.LifecycleError, "independently bound"):
            m.acquire_settled_work_item_history(self.root, f"work-item:{self.slug}", expected_references=[expected])
        receipt = archive / m.LEGACY_COMPLETION_RECEIPT
        raw_receipt = receipt.read_bytes()
        receipt.unlink()
        with self.assertRaisesRegex(m.LifecycleError, "settlement receipt is missing"):
            m.acquire_settled_work_item_history(self.root, f"work-item:{self.slug}")
        receipt.write_bytes(raw_receipt)
        pending = m._transition_intent_path(self.root, "component-origin-001")
        pending.parent.mkdir(parents=True, exist_ok=True)
        pending.write_bytes(b"explicit component pending marker\n")
        with self.assertRaisesRegex(m.LifecycleError, "pending action"):
            m.acquire_settled_work_item_history(self.root, f"work-item:{self.slug}")
        pending.unlink()
        path = archive / m.LEGACY_COMPLETION_METADATA
        raw_metadata = path.read_bytes()
        changed = json.loads(raw_metadata)
        changed["historyBinding"]["origin"]["directories"][0]["members"] = []
        path.write_bytes(m._migration_receipt_bytes(changed))
        with self.assertRaisesRegex(m.LifecycleError, "immutable metadata differs"):
            m.acquire_settled_work_item_history(self.root, f"work-item:{self.slug}")
        path.write_bytes(raw_metadata)
        (archive / metadata["acceptedEvidence"]["criteria"]["path"]).unlink()
        with self.assertRaises(m.LifecycleError):
            m.acquire_settled_work_item_history(self.root, f"work-item:{self.slug}")

    def historical_fixture(self):
        spec = importlib.util.spec_from_file_location("settled_origin_history_fixtures",
                                                    ROOT / "tests/test_legacy_flat_history_binding.py")
        producer = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = producer
        spec.loader.exec_module(producer)
        fixture = producer.CapturedHistoryBindingTests()
        self.root = self.root / "genuine-owner-history"
        self.root.mkdir()
        fixture.root, fixture.owner = self.root, producer.v.load_lifecycle_owner()
        return fixture

    def local_binding(self, binding):
        criteria = binding.criteria
        return v.CapturedWorkItemHistoryBindingV1(binding.repository_root, binding.work_item,
            binding.original_source_path, binding.original_item_base, binding.original_ledger_path,
            v.HistoricalLedgerCriteriaV1(criteria.criteria_reference, criteria.acquisition_reference,
                                         criteria.ledger_required, criteria.owner_contract),
            tuple(v.CapturedHistoryFileV1(row.original_path, row.snapshot, row.byte_length, row.sha256)
                  for row in binding.files), binding.absent_paths, binding.directory_members, binding.acquired_input)

    def test_settled_origin_preserves_genuine_archived_h1_group_and_old_closed(self):
        fixture = self.historical_fixture()
        paths, _receipt = fixture.settled_archived_h1()
        binding = self.local_binding(fixture.binding())
        self.source, self.slug = fixture.source, binding.work_item
        original = v._acquire_captured_history_item(binding)
        original_closed = (original / "closure.md").read_bytes()
        self.assertIn(b"Closed: 2026-09-10T01:00:00Z", original_closed)
        before = v.observe_captured_work_item_history(binding)
        group_before = v._load_effective_ledger_group(v.repo_root_for(original))
        self.assertTrue(before.acquisition_complete, before.diagnostics)
        self.assertTrue(before.obligations.open_revise)
        self.component_settled_record(binding)
        for row in binding.files:
            self.assertFalse((self.root / row.original_path).exists(), row.original_path)
        port = m.acquire_settled_work_item_history(self.root, f"work-item:{self.slug}")
        settled = v.bind_settled_work_item_history(port)
        selected = v._acquire_captured_history_item(settled)
        self.assertEqual((selected / "closure.md").read_bytes(), original_closed)
        after = v.observe_captured_work_item_history(settled)
        self.assertEqual(before, after)
        group_after = v._load_effective_ledger_group(v.repo_root_for(selected))
        for path in paths:
            self.assertEqual(group_before[path].rows, group_after[path].rows)
            self.assertEqual(group_before[path].view, group_after[path].view)
        port.verify()

    def test_settled_origin_actual_transfer_and_native_retained_preimage_consumers(self):
        fixture = self.historical_fixture()
        spec = importlib.util.spec_from_file_location("settled_origin_transfer_producer",
                                                    ROOT / "tests/test_legacy_obligation_migration.py")
        producer = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = producer
        spec.loader.exec_module(producer)
        request = producer.native_transfer_fixture(self.root)
        receipt = producer.run_transfer(request)
        self.assertEqual(receipt["status"], "settled")
        fixture.item = self.root / receipt["archivePath"]
        fixture.source = self.root / "evidence" / f"{request['slug']}.md"
        fixture.source.parent.mkdir()
        fixture.source.write_bytes(b"Original transfer source identity evidence\n")
        (fixture.item / "acquisition.md").write_bytes(b"Actual public owner settled transfer acquisition\n")
        payload = fixture.item / "retained/payload.bin"
        payload.parent.mkdir()
        payload.write_bytes(b"actual retained native preimage\n")
        binding = self.local_binding(fixture.binding())
        self.source, self.slug = fixture.source, binding.work_item
        def consume(selected):
            item = v._acquire_captured_history_item(selected)
            root, errors = v.repo_root_for(item), []
            receipts = v._transfer_receipts(root, errors)
            pointer = v.resolve_scratch_pointer(item, "retained/payload.bin", "canonicalPointer", "retained-run", errors)
            self.assertEqual(errors, [])
            native = v.capture_retained_preimage_payload(item, {"ref": "retained/payload.bin"},
                {"byteCount": len(b"actual retained native preimage\n"), "sha256": digest(b"actual retained native preimage\n")})
            return ({operation: (path.relative_to(root).as_posix(), value, archive.relative_to(root).as_posix())
                     for operation, (path, value, archive) in receipts.items()}, pointer.read_bytes(), native.data, native)
        before = consume(binding)
        self.assertIn(request["operationId"], before[0])
        self.component_settled_record(binding)
        port = m.acquire_settled_work_item_history(self.root, f"work-item:{self.slug}")
        after = consume(v.bind_settled_work_item_history(port))
        self.assertEqual(before[:3], after[:3])
        self.assertEqual(after[3].path, port.current_snapshot(payload).path)
        m._verify_captured_file(after[3], failure_id="WI-COMPONENT-CURRENT", acquired_input=port)
        self.assertFalse(payload.exists())

    def test_historical_physical_link_images_and_later_consumer_edits(self):
        consumer = self.root / "work-items/design.md"
        original_path = self.source.relative_to(self.root).as_posix()
        consumer.write_bytes((f"Logical work-item:{self.slug}\n[original](backlog/{self.slug}.md#original)\n"
                              f"Literal `{original_path}`\n").encode())
        inventory = m._incoming_link_result(self.root, {self.source}, f"work-item:{self.slug}", strict_consumer_reads=True,
                                           literal_path_references=(original_path,))
        self.assertEqual(inventory["result"], "unmapped")
        before = consumer.read_bytes()
        archive, metadata, action = self.component_settled_record()
        target = archive / metadata["source"]["preservedPath"]
        after = before.replace(f"backlog/{self.slug}.md".encode(), target.relative_to(self.root / "work-items").as_posix().encode())
        action["links"] = {"inventory": inventory, "consumers": [{"path": "work-items/design.md",
            "before": m._b64(before), "after": m._b64(after), "beforeSha256": digest(before), "afterSha256": digest(after)}]}
        receipt = archive / m.LEGACY_COMPLETION_RECEIPT
        receipt.write_bytes(m._legacy_work_item_action_receipt_bytes(action))
        consumer.write_bytes(after + b"Lawful later consumer edit.\n")
        m.acquire_settled_work_item_history(self.root, f"work-item:{self.slug}").verify()
        action["links"]["consumers"][0]["afterSha256"] = "0" * 64
        receipt.write_bytes(m._legacy_work_item_action_receipt_bytes(action))
        with self.assertRaisesRegex(m.LifecycleError, "consumer images differ"):
            m.acquire_settled_work_item_history(self.root, f"work-item:{self.slug}")

    def test_settled_raw_origin_keeps_original_closer_authority(self):
        # The same historical producing fixture supplies valid and late-bad
        # counterpart bytes. Today's action closure cannot repair old authority.
        for bad in (False, True):
            with self.subTest(bad=bad):
                fixture = self.historical_fixture()
                fixture.item = self.root / "work-items/archive/2026-07/fixture-item"
                fixture.item.mkdir(parents=True)
                fixture.source = self.root / "evidence/fixture-item.md"
                fixture.source.parent.mkdir(parents=True)
                fixture.source.write_bytes(b"Original raw archive identity evidence\n")
                fixture.closure = (b"Closed: 2026-07-16T10:00:01Z\nOutcome: fixture complete\n"
                                   b"Evidence: design.md\nResidual risk: none\n")
                for name, raw in (("closure.md", fixture.closure), ("design.md", b"Original design evidence\n"),
                                  ("acquisition.md", b"Original selected historical raw acquisition\n")):
                    (fixture.item / name).write_bytes(raw)
                fixture.ledger(bad=bad)
                m.refresh_readme(self.root, allow_marker_bootstrap=True)
                binding = self.local_binding(fixture.binding())
                self.source, self.slug = fixture.source, binding.work_item
                before = v.observe_captured_work_item_history(binding)
                self.assertEqual(bool(before.obligations.open_revise), bad)
                self.component_settled_record(binding)
                port = m.acquire_settled_work_item_history(self.root, f"work-item:{self.slug}")
                after = v.observe_captured_work_item_history(v.bind_settled_work_item_history(port))
                self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
