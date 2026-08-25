#!/usr/bin/env python3
"""Writer-side regression tests for manifest-bound legacy ledger projection."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "mutate-work-item.py"


def load_writer():
    spec = importlib.util.spec_from_file_location("legacy_projection_writer", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


class LegacyLedgerProjectionWriterTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, bytes, bytes]:
        item = root / "work-items" / "active" / "legacy-item"
        item.mkdir(parents=True)
        raw = {
            "runId": "legacy-run-001", "workItem": "legacy-item", "role": "analyst",
            "executionRole": "lead", "status": "completed", "gate": "PASS",
            "scope": "legacy scope", "evidence": "legacy-proof", "artifact": "evidence.md",
            "started": "2026-08-01T00:00:00Z", "updated": "2026-08-01T00:00:01Z",
        }
        raw_line = canonical(raw) + b"\n"
        (item / "agent-runs.jsonl").write_bytes(raw_line)
        (item / "evidence.md").write_text("verified artifact\n", encoding="utf-8")
        projected = {
            "schemaVersion": 2, "runId": raw["runId"], "workItem": raw["workItem"],
            "role": "analyst", "executionRole": "main", "status": "completed", "gate": "PASS",
            "scope": [raw["scope"]], "evidence": [{"kind": "manual-check", "ref": raw["evidence"]}],
            "artifact": "evidence.md", "startedAt": raw["started"], "updatedAt": raw["updated"],
        }
        manifest = {
            "schemaVersion": 1, "manifestId": "manifest-001",
            "profiles": [{"profileId": "canonical-v0-shape", "profileVersion": 1}],
            "entries": [{
                "entryId": "entry-001", "profileId": "canonical-v0-shape", "profileVersion": 1,
                "workItem": "work-items/active/legacy-item",
                "ledgerPath": "work-items/active/legacy-item/agent-runs.jsonl",
                "ledgerSha256": sha(raw_line), "rawLineOrdinals": [1],
                "rawLineSha256": [sha(raw_line)], "projectedEvents": [projected],
                "projectedEventSha256": [sha(canonical(projected))],
            }],
        }
        return item, raw_line, canonical(manifest)

    @staticmethod
    def _apply(module, root: Path, manifest: bytes, *, operation: str = "projection-apply-001", expected: str | None = None, dry_run: bool = False, inject_failure: str | None = None):
        return module.apply_legacy_ledger_projection(
            root, manifest, "entry-001", 1,
            sha(b"") if expected is None else expected, operation,
            "2026-08-01T00:00:02Z", dry_run=dry_run, inject_failure=inject_failure,
        )

    def test_dry_run_has_empty_byte_inventory_and_creates_no_lock_or_temp(self):
        module = load_writer()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item, ledger_before, manifest = self._fixture(root)
            before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            result = self._apply(module, root, manifest, dry_run=True)
            after = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            self.assertTrue(result["dryRun"])
            self.assertEqual({}, result["byteInventory"])
            self.assertEqual(before, after)
            self.assertEqual(ledger_before, (item / "agent-runs.jsonl").read_bytes())
            self.assertFalse((root / ".scratch").exists())

    def test_manifest_create_exact_replay_and_collision_are_fail_closed(self):
        module = load_writer()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _item, _ledger, manifest = self._fixture(root)
            first = self._apply(module, root, manifest)
            second = self._apply(module, root, manifest)
            self.assertFalse(first["replay"])
            self.assertTrue(second["replay"])
            manifest_path = root / "work-items" / "legacy-ledger-projection-manifests" / "manifest-001.json"
            self.assertEqual(manifest, manifest_path.read_bytes())
            altered = json.loads(manifest)
            altered["entries"][0]["entryId"] = "entry-other"
            with self.assertRaises(module.LifecycleError) as caught:
                self._apply(module, root, canonical(altered), operation="projection-apply-002")
            self.assertEqual("WI-LEDGER-MIGRATION-MANIFEST-INVALID", caught.exception.failure_id)

    def test_registry_cas_operation_conflict_and_ledger_immutability(self):
        module = load_writer()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item, ledger_before, manifest = self._fixture(root)
            registry = root / "work-items" / "legacy-ledger-projections.jsonl"
            with self.assertRaises(module.LifecycleError) as drift:
                self._apply(module, root, manifest, expected="0" * 64)
            self.assertEqual("WI-LEDGER-MIGRATION-LEDGER-DRIFT", drift.exception.failure_id)
            self._apply(module, root, manifest)
            registry_before = registry.read_bytes()
            with self.assertRaises(module.LifecycleError) as collision:
                self._apply(module, root, manifest, expected=sha(registry_before), operation="PROJECTION-APPLY-001")
            self.assertEqual("WI-LEDGER-MIGRATION-TOPOLOGY", collision.exception.failure_id)
            self.assertEqual(ledger_before, (item / "agent-runs.jsonl").read_bytes())
            self.assertEqual(registry_before, registry.read_bytes())

    def test_revoke_binds_exact_apply_and_refuses_double_partial_or_dependent_settlement(self):
        module = load_writer()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item, ledger_before, manifest = self._fixture(root)
            apply = self._apply(module, root, manifest)
            registry = root / "work-items" / "legacy-ledger-projections.jsonl"
            apply_hash = apply["recordSha256"]
            revoked = module.revoke_legacy_ledger_projection(
                root, "projection-apply-001", apply_hash, sha(registry.read_bytes()),
                "projection-revoke-001", "2026-08-01T00:00:03Z",
            )
            self.assertFalse(revoked["replay"])
            replayed = module.revoke_legacy_ledger_projection(
                root, "projection-apply-001", apply_hash, sha(registry.read_bytes()),
                "projection-revoke-001", "2026-08-01T00:00:03Z",
            )
            self.assertTrue(replayed["replay"])
            with self.assertRaises(module.LifecycleError) as double:
                module.revoke_legacy_ledger_projection(
                    root, "projection-apply-001", apply_hash,
                    sha(registry.read_bytes()), "projection-revoke-002", "2026-08-01T00:00:04Z",
                )
            self.assertEqual("WI-LEDGER-MIGRATION-TOPOLOGY", double.exception.failure_id)
            self.assertEqual(ledger_before, (item / "agent-runs.jsonl").read_bytes())

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _item, _ledger, manifest = self._fixture(root)
            # One entry with two raw lines cannot be partially applied/settled.
            second = json.loads(manifest)
            entry = second["entries"][0]
            entry["rawLineOrdinals"] = [1, 2]
            entry["rawLineSha256"] = [entry["rawLineSha256"][0], entry["rawLineSha256"][0]]
            entry["projectedEvents"] *= 2
            entry["projectedEventSha256"] *= 2
            with self.assertRaises(module.LifecycleError) as partial:
                self._apply(module, root, canonical(second), operation="projection-apply-003")
            self.assertEqual("WI-LEDGER-MIGRATION-TARGET-DIGEST", partial.exception.failure_id)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _item, _ledger, manifest = self._fixture(root)
            apply = self._apply(module, root, manifest)
            registry = root / "work-items" / "legacy-ledger-projections.jsonl"
            future = json.loads(registry.read_bytes())
            future["operationId"] = "projection-future-001"
            registry.write_bytes(registry.read_bytes() + canonical(future) + b"\n")
            with self.assertRaises(module.LifecycleError) as dependent:
                module.revoke_legacy_ledger_projection(
                    root, "projection-apply-001", apply["recordSha256"],
                    sha(registry.read_bytes()), "projection-revoke-003", "2026-08-01T00:00:05Z",
                )
            self.assertEqual("WI-LEDGER-MIGRATION-TOPOLOGY", dependent.exception.failure_id)

    def test_commit_reconciles_exact_after_and_refuses_indeterminate_bytes(self):
        module = load_writer()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _item, _ledger, manifest = self._fixture(root)
            with self.assertRaises(module.LifecycleError) as after:
                self._apply(module, root, manifest, inject_failure="after-registry")
            self.assertEqual("WI-LEDGER-MIGRATION-COMMIT-INDETERMINATE", after.exception.failure_id)
            replay = self._apply(module, root, manifest)
            self.assertTrue(replay["replay"])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _item, _ledger, manifest = self._fixture(root)
            with self.assertRaises(module.LifecycleError) as neither:
                self._apply(module, root, manifest, inject_failure="corrupt-registry")
            self.assertEqual("WI-LEDGER-MIGRATION-COMMIT-INDETERMINATE", neither.exception.failure_id)

    def test_multi_row_apply_and_revoke_settle_the_full_entry_or_nothing(self):
        module = load_writer()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item = root / "work-items" / "active" / "legacy-item"
            item.mkdir(parents=True)
            first = {"attemptId": "pair-001", "state": "running", "role": "analysis", "task": "pair", "scope": "first scope", "evidence": "first-proof", "started": "2026-08-01T00:00:00Z", "updated": "2026-08-01T00:00:00Z"}
            second = {**first, "state": "completed", "scope": "second scope", "evidence": "second-proof", "updated": "2026-08-01T00:00:01Z"}
            first_line, second_line = canonical(first) + b"\n", canonical(second) + b"\n"
            ledger = first_line + second_line
            (item / "agent-runs.jsonl").write_bytes(ledger)
            projected = [
                {"schemaVersion": 2, "runId": "legacy-attempt-pair-001-start", "workItem": "legacy-item", "role": "analyst", "executionRole": "main", "status": "running", "gate": "none", "scope": [first["scope"]], "evidence": [{"kind": "manual-check", "ref": first["evidence"]}], "startedAt": first["started"], "updatedAt": first["updated"]},
                {"schemaVersion": 2, "runId": "legacy-attempt-pair-001-outcome", "workItem": "legacy-item", "role": "analyst", "executionRole": "main", "status": "completed", "gate": "none", "scope": [second["scope"]], "evidence": [{"kind": "manual-check", "ref": second["evidence"]}], "startedAt": second["started"], "updatedAt": second["updated"]},
            ]
            entry = {"entryId": "entry-001", "profileId": "attempt-pair-v0", "profileVersion": 1, "workItem": "work-items/active/legacy-item", "ledgerPath": "work-items/active/legacy-item/agent-runs.jsonl", "ledgerSha256": sha(ledger), "rawLineOrdinals": [1, 2], "rawLineSha256": [sha(first_line), sha(second_line)], "projectedEvents": projected, "projectedEventSha256": [sha(canonical(row)) for row in projected]}
            manifest_bytes = canonical({"schemaVersion": 1, "manifestId": "manifest-pair", "profiles": [{"profileId": "attempt-pair-v0", "profileVersion": 1}], "entries": [entry]})
            apply = module.apply_legacy_ledger_projection(
                root, manifest_bytes, "entry-001", 2, sha(b""), "multi-apply", "2026-08-01T00:00:02Z"
            )
            self.assertEqual(2, len(apply["recordSha256"]))
            registry = root / "work-items" / "legacy-ledger-projections.jsonl"
            apply_records = [json.loads(line) for line in registry.read_bytes().splitlines()]
            self.assertEqual(2, len(apply_records))
            self.assertTrue(all(record["schemaVersion"] == 2 for record in apply_records))
            self.assertEqual(["multi-apply", "multi-apply"], [record["operationGroupId"] for record in apply_records])
            self.assertEqual([1, 2], [record["groupMemberIndex"] for record in apply_records])
            self.assertEqual([2, 2], [record["groupMemberCount"] for record in apply_records])
            self.assertNotEqual(apply_records[1]["operationId"], "multi-apply.2")
            revoked = module.revoke_legacy_ledger_projection(
                root, "multi-apply", apply["recordSha256"], sha(registry.read_bytes()),
                "multi-revoke", "2026-08-01T00:00:03Z",
            )
            self.assertEqual(2, len(revoked["recordSha256"]))
            self.assertEqual(4, len(registry.read_bytes().splitlines()))
            replay = module.revoke_legacy_ledger_projection(
                root, "multi-apply", apply["recordSha256"], apply["registrySha256"],
                "multi-revoke", "2026-08-01T00:00:03Z",
            )
            self.assertTrue(replay["replay"])

    def test_receipt_replay_stays_bound_to_its_prefix_after_later_independent_append(self):
        module = load_writer()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item, first_line, manifest_bytes = self._fixture(root)
            manifest = json.loads(manifest_bytes)
            second_item = root / "work-items" / "active" / "other-item"
            second_item.mkdir(parents=True)
            second = {**json.loads(first_line), "runId": "legacy-run-002", "workItem": "other-item", "scope": "second scope", "evidence": "second-proof"}
            second_line = canonical(second) + b"\n"
            (second_item / "agent-runs.jsonl").write_bytes(second_line)
            (second_item / "evidence.md").write_text("verified artifact\n", encoding="utf-8")
            projected_second = {
                "schemaVersion": 2, "runId": second["runId"], "workItem": second["workItem"],
                "role": "analyst", "executionRole": "main", "status": "completed", "gate": "PASS",
                "scope": [second["scope"]], "evidence": [{"kind": "manual-check", "ref": second["evidence"]}],
                "artifact": "evidence.md", "startedAt": second["started"], "updatedAt": second["updated"],
            }
            base = manifest["entries"][0]
            second_entry = {**base, "entryId": "entry-002", "workItem": "work-items/active/other-item", "ledgerPath": "work-items/active/other-item/agent-runs.jsonl", "ledgerSha256": sha(second_line), "rawLineOrdinals": [1], "rawLineSha256": [sha(second_line)], "projectedEvents": [projected_second], "projectedEventSha256": [sha(canonical(projected_second))]}
            manifest["entries"].append(second_entry)
            manifest_bytes = canonical(manifest)
            first_apply = module.apply_legacy_ledger_projection(
                root, manifest_bytes, "entry-001", 1, sha(b""), "first-apply", "2026-08-01T00:00:02Z"
            )
            registry = root / "work-items" / "legacy-ledger-projections.jsonl"
            module.apply_legacy_ledger_projection(
                root, manifest_bytes, "entry-002", 1, sha(registry.read_bytes()), "second-apply", "2026-08-01T00:00:03Z"
            )
            receipt = root / "work-items" / "legacy-ledger-projection-receipts" / "first-apply.json"
            stable_before = receipt.read_bytes()
            replay = module.apply_legacy_ledger_projection(
                root, manifest_bytes, "entry-001", 1, sha(b""), "first-apply", "2026-08-01T00:00:02Z"
            )
            self.assertTrue(replay["replay"])
            self.assertEqual(first_apply["registrySha256"], replay["registrySha256"])
            self.assertEqual(stable_before, receipt.read_bytes())

    def test_writer_rejects_precommit_failure_partial_group_and_ambiguous_roots(self):
        module = load_writer()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _item, _ledger, manifest = self._fixture(root)
            with self.assertRaises(module.LifecycleError) as interrupted:
                self._apply(module, root, manifest, inject_failure="before-registry")
            self.assertEqual("WI-LEDGER-MIGRATION-COMMIT-INDETERMINATE", interrupted.exception.failure_id)
            self.assertFalse((root / "work-items" / "legacy-ledger-projections.jsonl").exists())
            self.assertFalse((root / "work-items" / "legacy-ledger-projection-manifests").exists())

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _item, _ledger, manifest = self._fixture(root)
            with self.assertRaises(module.LifecycleError) as dual_root:
                self._apply(module, root / "work-items", manifest)
            self.assertEqual("WI-LEDGER-MIGRATION-TARGET-IDENTITY", dual_root.exception.failure_id)
            escaped = json.loads(manifest)
            escaped["entries"][0]["workItem"] = "../escape"
            with self.assertRaises(module.LifecycleError) as path_escape:
                self._apply(module, root, canonical(escaped), operation="path-escape")
            self.assertEqual("WI-LEDGER-MIGRATION-TARGET-IDENTITY", path_escape.exception.failure_id)

    def test_projection_dead_schemas_are_absent(self):
        self.assertFalse((ROOT / "shared" / "schemas" / "legacy-ledger-projection-manifest.schema.json").exists())
        self.assertFalse((ROOT / "shared" / "schemas" / "legacy-ledger-historical-disposition.schema.json").exists())

    def test_output_sink_rejects_existing_link_leaves_before_content_or_temp_creation(self):
        module = load_writer()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            canary = root / "external-canary.json"
            canary.write_bytes(b"external-canary\n")
            for target_name in ("manifest.json", "receipt.json", "disposition.json"):
                with self.subTest(target_name=target_name):
                    target = root / "owned" / target_name
                    target.parent.mkdir(exist_ok=True)
                    try:
                        target.symlink_to(canary, target_is_directory=False)
                    except OSError as exc:
                        self.fail(f"host cannot create required file link fixture: {exc}")
                    before = canary.read_bytes()
                    with self.assertRaises(module.LifecycleError) as rejected:
                        module._projection_create_or_exact(target, b"owned bytes\n", "WI-TEST-SINK")
                    self.assertEqual("WI-TEST-SINK", rejected.exception.failure_id)
                    self.assertEqual(before, canary.read_bytes())
                    self.assertEqual([], list(target.parent.glob(f".{target.name}.*.tmp")))

    def test_output_sink_rejects_linked_parent_before_target_probe_or_write(self):
        module = load_writer()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            external = root / "external-parent"
            external.mkdir()
            parent = root / "owned-alias"
            try:
                parent.symlink_to(external, target_is_directory=True)
            except OSError as exc:
                self.fail(f"host cannot create required directory link fixture: {exc}")
            target = parent / "receipt.json"
            with self.assertRaises(module.LifecycleError) as rejected:
                module._projection_create_or_exact(target, b"owned bytes\n", "WI-TEST-SINK")
            self.assertEqual("WI-TEST-SINK", rejected.exception.failure_id)
            self.assertFalse((external / "receipt.json").exists())

    def test_lock_contention_and_exact_historical_disposition(self):
        module = load_writer()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _item, _ledger, manifest = self._fixture(root)
            with module.LifecycleTransaction(root):
                with self.assertRaises(module.LifecycleError) as held:
                    self._apply(module, root, manifest)
            self.assertEqual("WI-LIFECYCLE-LOCK-HELD", held.exception.failure_id)

            archived = root / "work-items" / "archive" / "2026-08" / "legacy-item"
            archived.mkdir(parents=True)
            (archived / "closure.md").write_text("Closed: 2026-08-01T00:00:00Z\n", encoding="utf-8")
            (archived / "lifecycle-transition-receipt.json").write_bytes(
                canonical({"operationId": "archive-commit-001"})
            )
            disposition = {
                "schemaVersion": 1, "archiveIdentity": "archive-commit-001",
                "workItem": "work-items/archive/2026-08/legacy-item",
                "missingPath": ".reports/recovery-state-admission-audit.md", "disposition": "irrecoverable",
                "expectedDigest": "unknown", "searchReceipt": "search-001",
                "survivingArtifacts": [{"path": "closure.md", "sha256": sha((archived / "closure.md").read_bytes())}],
                "approvedBy": "human-001", "approvedAt": "2026-08-01T00:00:03Z",
            }
            first = module.write_legacy_ledger_irrecoverable_disposition(root, canonical(disposition))
            second = module.write_legacy_ledger_irrecoverable_disposition(root, canonical(disposition))
            self.assertFalse(first["replay"])
            self.assertTrue(second["replay"])
            for mutation in (
                {**disposition, "missingPath": "*"},
                {**disposition, "archiveIdentity": "wrong-archive"},
                {**disposition, "survivingArtifacts": [{"path": "closure.md", "sha256": "0" * 64}]},
            ):
                with self.subTest(mutation=mutation):
                    with self.assertRaises(module.LifecycleError) as invalid:
                        module.write_legacy_ledger_irrecoverable_disposition(root, canonical(mutation))
                    self.assertIn(invalid.exception.failure_id, {"WI-LEDGER-MIGRATION-MANIFEST-INVALID", "WI-LEDGER-MIGRATION-TARGET-DIGEST", "WI-LEDGER-MIGRATION-TARGET-IDENTITY"})


if __name__ == "__main__":
    unittest.main()
