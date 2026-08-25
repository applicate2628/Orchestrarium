#!/usr/bin/env python3
"""Phase-1 read-side tests for manifest-bound legacy ledger projection."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate-work-item-state.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("legacy_projection_validator", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


class LegacyLedgerProjectionReadTests(unittest.TestCase):
    def _make_item(self, root: Path, *, archived: bool = False) -> tuple[Path, Path, Path]:
        item = (
            root / "work-items" / "archive" / "2026-08" / "legacy-item"
            if archived
            else root / "work-items" / "active" / "legacy-item"
        )
        item.mkdir(parents=True)
        (item / "evidence.md").write_text("verified artifact\n", encoding="utf-8")
        ledger = item / "agent-runs.jsonl"
        return item, ledger, root / "work-items"

    def _canonical_raw(self, *, gate: str = "PASS", status: str = "completed", artifact: str = "evidence.md") -> dict:
        return {
            "runId": "legacy-run-001",
            "workItem": "legacy-item",
            "role": "analyst",
            "executionRole": "lead",
            "status": status,
            "gate": gate,
            "scope": "legacy scope",
            "evidence": "legacy-proof",
            "artifact": artifact,
            "started": "2026-08-01T00:00:00Z",
            "updated": "2026-08-01T00:00:01Z",
        }

    def _projected_canonical(self, raw: dict) -> dict:
        return {
            "schemaVersion": 2,
            "runId": raw["runId"],
            "workItem": raw["workItem"],
            "role": "analyst",
            "executionRole": "main",
            "status": raw["status"],
            "gate": raw["gate"],
            "scope": [raw["scope"]],
            "evidence": [{"kind": "manual-check", "ref": raw["evidence"]}],
            "artifact": raw["artifact"],
            "startedAt": raw["started"],
            "updatedAt": raw["updated"],
        }

    def _install_apply(
        self,
        item: Path,
        ledger: Path,
        work_items: Path,
        raw_line: bytes,
        projected: dict,
        *,
        profile_id: str = "canonical-v0-shape",
        profile_version: int = 1,
        entry_id: str = "entry-001",
    ) -> None:
        ledger.write_bytes(raw_line)
        manifest_dir = work_items / "legacy-ledger-projection-manifests"
        manifest_dir.mkdir()
        relative_item = item.relative_to(work_items.parent).as_posix()
        relative_ledger = ledger.relative_to(work_items.parent).as_posix()
        manifest = {
            "schemaVersion": 1,
            "manifestId": "manifest-001",
            "profiles": [{"profileId": profile_id, "profileVersion": profile_version}],
            "entries": [{
                "entryId": entry_id,
                "profileId": profile_id,
                "profileVersion": profile_version,
                "workItem": relative_item,
                "ledgerPath": relative_ledger,
                "ledgerSha256": digest(raw_line),
                "rawLineOrdinals": [1],
                "rawLineSha256": [digest(raw_line)],
                "projectedEvents": [projected],
                "projectedEventSha256": [digest(canonical_bytes(projected))],
            }],
        }
        if profile_id == "review-summary-v0":
            manifest["entries"][0]["artifactSha256"] = digest((item / "evidence.md").read_bytes())
        manifest_bytes = canonical_bytes(manifest)
        (manifest_dir / "manifest-001.json").write_bytes(manifest_bytes)
        record = {
            "schemaVersion": 1,
            "operationId": "projection-apply-001",
            "state": "apply",
            "profileId": profile_id,
            "profileVersion": profile_version,
            "manifestId": "manifest-001",
            "manifestSha256": digest(manifest_bytes),
            "manifestEntryId": entry_id,
            "workItem": relative_item,
            "ledgerPath": relative_ledger,
            "ledgerSha256": digest(raw_line),
            "rawLineOrdinal": 1,
            "rawLineSha256": digest(raw_line),
            "projectedEvent": projected,
            "projectedEventSha256": digest(canonical_bytes(projected)),
            "recordedAt": "2026-08-01T00:00:02Z",
        }
        (work_items / "legacy-ledger-projections.jsonl").write_bytes(canonical_bytes(record) + b"\n")

    def test_canonical_apply_projects_before_strict_validation_without_changing_raw_bytes(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item, ledger, work_items = self._make_item(root)
            raw = self._canonical_raw()
            raw_line = canonical_bytes(raw) + b"\r\n"
            projected = self._projected_canonical(raw)
            self._install_apply(item, ledger, work_items, raw_line, projected)

            before = ledger.read_bytes()
            errors = module.validate_work_item(item, validate_status_file=False)

            self.assertEqual([], errors)
            self.assertEqual(before, ledger.read_bytes())

    def test_unknown_or_drifted_profile_is_rejected_without_falling_back_to_legacy_shape(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item, ledger, work_items = self._make_item(root)
            raw = self._canonical_raw()
            raw_line = canonical_bytes(raw) + b"\n"
            self._install_apply(
                item, ledger, work_items, raw_line, self._projected_canonical(raw),
                profile_id="unknown-profile",
            )

            errors = module.validate_work_item(item, validate_status_file=False)

            self.assertTrue(any("WI-LEDGER-MIGRATION-PROFILE-UNSUPPORTED" in error for error in errors))

    def test_current_malformed_v1_v2_rows_remain_invalid_without_an_admitted_projection(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item, ledger, _ = self._make_item(root)
            malformed_v1 = {
                "schemaVersion": 1, "runId": "current-v1-001", "workItem": "legacy-item",
                "role": "analyst", "executionRole": "main", "status": "completed", "gate": "none",
                "scope": "not-a-list", "startedAt": "2026-08-01T00:00:00Z", "updatedAt": "2026-08-01T00:00:01Z",
            }
            ledger.write_bytes(canonical_bytes(malformed_v1) + b"\n")

            errors = module.validate_work_item(item, validate_status_file=False)

            self.assertTrue(any("scope must be a non-empty list" in error for error in errors))

    def test_manifest_ledger_and_physical_raw_line_drift_are_all_rejected(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item, ledger, work_items = self._make_item(root)
            raw = self._canonical_raw()
            raw_line = canonical_bytes(raw) + b"\r\n"
            self._install_apply(item, ledger, work_items, raw_line, self._projected_canonical(raw))
            ledger.write_bytes(canonical_bytes(raw) + b"\n")

            errors = module.validate_work_item(item, validate_status_file=False)

            self.assertTrue(any("WI-LEDGER-MIGRATION-LEDGER-DRIFT" in error for error in errors))
            self.assertTrue(any("WI-LEDGER-MIGRATION-TARGET-DIGEST" in error for error in errors))

    def test_candidate_ledger_drift_is_rejected_from_the_selected_candidate_without_reopening_live_bytes(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item, ledger, work_items = self._make_item(root)
            raw = self._canonical_raw()
            raw_line = canonical_bytes(raw) + b"\n"
            self._install_apply(item, ledger, work_items, raw_line, self._projected_canonical(raw))
            candidate = root / "candidate-agent-runs.jsonl"
            candidate.write_bytes(canonical_bytes(raw) + b"\r\n")
            ledger.unlink()

            errors = module.validate_work_item(item, ledger_path=candidate, validate_status_file=False)

            self.assertTrue(any("WI-LEDGER-MIGRATION-LEDGER-DRIFT" in error for error in errors))
            self.assertFalse(any("missing ledger" in error for error in errors))

    def test_in_memory_projection_candidate_validates_without_live_files_or_tree_mutation(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item, ledger, work_items = self._make_item(root)
            raw = self._canonical_raw()
            raw_line = canonical_bytes(raw) + b"\n"
            self._install_apply(item, ledger, work_items, raw_line, self._projected_canonical(raw))
            manifest_dir = work_items / "legacy-ledger-projection-manifests"
            manifest_blobs = {path.name: path.read_bytes() for path in manifest_dir.iterdir()}
            registry_bytes = (work_items / "legacy-ledger-projections.jsonl").read_bytes()
            for path in manifest_dir.iterdir():
                path.unlink()
            manifest_dir.rmdir()
            (work_items / "legacy-ledger-projections.jsonl").unlink()
            before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}

            errors = module.validate_work_item(
                item,
                validate_status_file=False,
                projection_manifest_blobs=manifest_blobs,
                projection_registry_bytes=registry_bytes,
            )

            after = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
            self.assertEqual([], errors)
            self.assertEqual(before, after)

    def test_in_memory_projection_candidate_fails_closed_on_manifest_drift(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item, ledger, work_items = self._make_item(root)
            raw = self._canonical_raw()
            raw_line = canonical_bytes(raw) + b"\n"
            self._install_apply(item, ledger, work_items, raw_line, self._projected_canonical(raw))
            manifest_dir = work_items / "legacy-ledger-projection-manifests"
            manifest_blobs = {path.name: path.read_bytes() for path in manifest_dir.iterdir()}
            registry_bytes = (work_items / "legacy-ledger-projections.jsonl").read_bytes()
            manifest_blobs["manifest-001.json"] += b" "

            errors = module.validate_work_item(
                item,
                validate_status_file=False,
                projection_manifest_blobs=manifest_blobs,
                projection_registry_bytes=registry_bytes,
            )

            self.assertTrue(any("WI-LEDGER-MIGRATION-MANIFEST-INVALID" in error for error in errors))

    def test_candidate_projection_rejects_non_scalar_profile_values_without_type_error(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item, ledger, work_items = self._make_item(root)
            raw = self._canonical_raw()
            raw_line = canonical_bytes(raw) + b"\n"
            self._install_apply(item, ledger, work_items, raw_line, self._projected_canonical(raw))
            manifest_path = work_items / "legacy-ledger-projection-manifests" / "manifest-001.json"
            manifest_blobs = {manifest_path.name: manifest_path.read_bytes()}
            registry = json.loads((work_items / "legacy-ledger-projections.jsonl").read_text(encoding="utf-8"))
            registry["profileId"] = ["canonical-v0-shape"]
            registry_bytes = canonical_bytes(registry) + b"\n"

            errors = module.validate_work_item(
                item,
                validate_status_file=False,
                projection_manifest_blobs=manifest_blobs,
                projection_registry_bytes=registry_bytes,
            )

            self.assertTrue(any("WI-LEDGER-MIGRATION-PROFILE-UNSUPPORTED" in error for error in errors))

    def test_scalar_guard_matrix_rejects_unhashable_profile_and_identity_values(self):
        module = load_validator()
        profile_cases = {
            ("canonical-v0-shape", 1): [{
                "runId": "raw-role-001", "workItem": "legacy-item", "role": ["qa"],
                "executionRole": "lead", "status": "completed", "gate": "none", "scope": "scope",
                "evidence": "proof", "started": "2026-08-01T00:00:00Z", "updated": "2026-08-01T00:00:01Z",
            }],
            ("attempt-pair-v0", 1): [
                {"attemptId": "attempt-001", "state": "running", "role": ["qa"], "task": "task", "scope": "scope", "evidence": "proof", "started": "2026-08-01T00:00:00Z", "updated": "2026-08-01T00:00:00Z"},
                {"attemptId": "attempt-001", "state": "completed", "role": ["qa"], "task": "task", "scope": "scope", "evidence": "proof", "started": "2026-08-01T00:00:01Z", "updated": "2026-08-01T00:00:01Z"},
            ],
            ("review-summary-v0", 1): [{"stage": "review", "role": ["qa"], "task": "task", "artifact": "evidence.md", "result": "PASS", "timestamp": "2026-08-01T00:00:00Z"}],
        }
        for profile, raws in profile_cases.items():
            with self.subTest(profile=profile):
                errors: list[str] = []
                self.assertIsNone(module._profile_projection(profile, raws, Path("legacy-item"), {}, errors))
                self.assertTrue(any("WI-LEDGER-MIGRATION-PROFILE-UNSUPPORTED" in error for error in errors))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item, ledger, work_items = self._make_item(root)
            raw = self._canonical_raw()
            self._install_apply(item, ledger, work_items, canonical_bytes(raw) + b"\n", self._projected_canonical(raw))
            manifest_path = work_items / "legacy-ledger-projection-manifests" / "manifest-001.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["entries"][0]["entryId"] = ["entry-001"]
            manifest_path.write_bytes(canonical_bytes(manifest))
            registry_path = work_items / "legacy-ledger-projections.jsonl"
            record = json.loads(registry_path.read_text(encoding="utf-8"))
            record["manifestSha256"] = digest(manifest_path.read_bytes())
            registry_path.write_bytes(canonical_bytes(record) + b"\n")
            errors = module.validate_work_item(item, validate_status_file=False)
            self.assertTrue(any("WI-LEDGER-MIGRATION-MANIFEST-INVALID" in error for error in errors))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item, ledger, work_items = self._make_item(root)
            raw = self._canonical_raw()
            self._install_apply(item, ledger, work_items, canonical_bytes(raw) + b"\n", self._projected_canonical(raw))
            registry_path = work_items / "legacy-ledger-projections.jsonl"
            record = json.loads(registry_path.read_text(encoding="utf-8"))
            record["manifestId"] = ["manifest-001"]
            registry_path.write_bytes(canonical_bytes(record) + b"\n")
            errors = module.validate_work_item(item, validate_status_file=False)
            self.assertTrue(any("WI-LEDGER-MIGRATION-MANIFEST-INVALID" in error for error in errors))

    def test_unreferenced_invalid_manifest_entry_and_profile_still_fail_the_global_registry(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item, ledger, work_items = self._make_item(root)
            raw = self._canonical_raw()
            raw_line = canonical_bytes(raw) + b"\n"
            self._install_apply(item, ledger, work_items, raw_line, self._projected_canonical(raw))
            manifest_path = work_items / "legacy-ledger-projection-manifests" / "manifest-001.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            invalid = dict(manifest["entries"][0])
            invalid.update({"entryId": "unreferenced-invalid", "profileId": "unknown-profile"})
            manifest["entries"].append(invalid)
            manifest["profiles"].append({"profileId": "unknown-profile", "profileVersion": 1})
            manifest_path.write_bytes(canonical_bytes(manifest))
            registry_path = work_items / "legacy-ledger-projections.jsonl"
            record = json.loads(registry_path.read_text(encoding="utf-8"))
            record["manifestSha256"] = digest(manifest_path.read_bytes())
            registry_path.write_bytes(canonical_bytes(record) + b"\n")

            errors = module.validate_work_item(item, validate_status_file=False)

            self.assertTrue(any("WI-LEDGER-MIGRATION-PROFILE-UNSUPPORTED" in error for error in errors))

    def test_global_registry_ignores_valid_projection_rows_for_another_work_item(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item, ledger, work_items = self._make_item(root)
            raw = self._canonical_raw()
            raw_line = canonical_bytes(raw) + b"\n"
            self._install_apply(item, ledger, work_items, raw_line, self._projected_canonical(raw))
            other = root / "work-items" / "active" / "other-item"
            other.mkdir(parents=True)
            (other / "evidence.md").write_text("other artifact\n", encoding="utf-8")
            other_raw = {**self._canonical_raw(), "runId": "legacy-other-001", "workItem": "other-item"}
            other_line = canonical_bytes(other_raw) + b"\n"
            other_ledger = other / "agent-runs.jsonl"
            other_ledger.write_bytes(other_line)
            manifest_path = work_items / "legacy-ledger-projection-manifests" / "manifest-001.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            other_entry = dict(manifest["entries"][0])
            other_entry.update({
                "entryId": "entry-other", "workItem": "work-items/active/other-item",
                "ledgerPath": "work-items/active/other-item/agent-runs.jsonl", "ledgerSha256": digest(other_line),
                "rawLineSha256": [digest(other_line)], "projectedEvents": [self._projected_canonical(other_raw)],
                "projectedEventSha256": [digest(canonical_bytes(self._projected_canonical(other_raw)))],
            })
            manifest["entries"].append(other_entry)
            manifest_path.write_bytes(canonical_bytes(manifest))
            registry_path = work_items / "legacy-ledger-projections.jsonl"
            first_record = json.loads(registry_path.read_text(encoding="utf-8"))
            first_record["manifestSha256"] = digest(manifest_path.read_bytes())
            other_record = {**first_record, "operationId": "projection-apply-other", "manifestEntryId": "entry-other", "workItem": other_entry["workItem"], "ledgerPath": other_entry["ledgerPath"], "ledgerSha256": other_entry["ledgerSha256"], "rawLineSha256": other_entry["rawLineSha256"][0], "projectedEvent": other_entry["projectedEvents"][0], "projectedEventSha256": other_entry["projectedEventSha256"][0]}
            registry_path.write_bytes(canonical_bytes(first_record) + b"\n" + canonical_bytes(other_record) + b"\n")

            errors = module.validate_work_item(item, validate_status_file=False)

            self.assertEqual([], errors)

    def test_revoke_cannot_remove_a_different_active_raw_line(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item, ledger, work_items = self._make_item(root)
            first = self._canonical_raw()
            second = {**self._canonical_raw(), "runId": "legacy-run-002"}
            raw_lines = canonical_bytes(first) + b"\n" + canonical_bytes(second) + b"\n"
            self._install_apply(item, ledger, work_items, raw_lines, self._projected_canonical(first))
            manifest_path = work_items / "legacy-ledger-projection-manifests" / "manifest-001.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            entry = manifest["entries"][0]
            projected_second = self._projected_canonical(second)
            entry.update({
                "rawLineOrdinals": [1, 2],
                "rawLineSha256": [digest(canonical_bytes(first) + b"\n"), digest(canonical_bytes(second) + b"\n")],
                "projectedEvents": [self._projected_canonical(first), projected_second],
                "projectedEventSha256": [digest(canonical_bytes(self._projected_canonical(first))), digest(canonical_bytes(projected_second))],
                "ledgerSha256": digest(raw_lines),
            })
            manifest_path.write_bytes(canonical_bytes(manifest))
            registry_path = work_items / "legacy-ledger-projections.jsonl"
            apply_one = json.loads(registry_path.read_text(encoding="utf-8"))
            apply_one.update({"manifestSha256": digest(manifest_path.read_bytes()), "ledgerSha256": digest(raw_lines), "rawLineSha256": entry["rawLineSha256"][0]})
            apply_two = {**apply_one, "operationId": "projection-apply-002", "rawLineOrdinal": 2, "rawLineSha256": entry["rawLineSha256"][1], "projectedEvent": projected_second, "projectedEventSha256": entry["projectedEventSha256"][1]}
            revoke = {**apply_two, "operationId": "projection-revoke-001", "state": "revoke", "revokeOfOperationId": "projection-apply-001", "revokeOfRecordSha256": digest(canonical_bytes(apply_one) + b"\n")}
            registry_path.write_bytes(b"".join(canonical_bytes(row) + b"\n" for row in (apply_one, apply_two, revoke)))

            errors = module.validate_work_item(item, validate_status_file=False)

            self.assertTrue(any("WI-LEDGER-MIGRATION-TOPOLOGY" in error for error in errors))

    def test_projection_cannot_settle_revise_or_open_launches(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item, ledger, work_items = self._make_item(root)
            raw = self._canonical_raw(gate="REVISE", status="revise")
            raw_line = canonical_bytes(raw) + b"\n"
            self._install_apply(item, ledger, work_items, raw_line, self._projected_canonical(raw))

            revise_errors = module.validate_work_item(item, validate_status_file=False)
            self.assertTrue(any("open REVISE obligation" in error for error in revise_errors))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item, ledger, work_items = self._make_item(root)
            raw = self._canonical_raw(gate="none", status="running")
            raw["eventKind"] = "launch"
            raw["lane"] = "legacy-lane"
            raw_line = canonical_bytes(raw) + b"\n"
            projected = self._projected_canonical(raw)
            projected.update({"eventKind": "launch", "lane": "legacy-lane"})
            self._install_apply(item, ledger, work_items, raw_line, projected)
            launch_errors = module.validate_work_item(item, validate_status_file=False)
            self.assertTrue(any("unsettled launch" in error for error in launch_errors))

    def test_review_pass_requires_existing_exact_digest_bound_artifact(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item, ledger, work_items = self._make_item(root)
            raw = {
                "stage": "review", "role": "qa", "task": "legacy review task",
                "artifact": "evidence.md", "result": "PASS", "timestamp": "2026-08-01T00:00:00Z",
            }
            raw_line = canonical_bytes(raw) + b"\n"
            projected = {
                "schemaVersion": 2,
                "runId": "legacy-review-" + hashlib.sha256(b"legacy review task").hexdigest()[:16],
                "workItem": "legacy-item", "role": "qa-engineer", "executionRole": "main",
                "status": "completed", "gate": "PASS", "scope": ["review"],
                "evidence": [{"kind": "artifact", "ref": "evidence.md"}], "artifact": "evidence.md",
                "startedAt": "2026-08-01T00:00:00Z", "updatedAt": "2026-08-01T00:00:00Z",
            }
            self._install_apply(
                item, ledger, work_items, raw_line, projected,
                profile_id="review-summary-v0",
            )
            (item / "evidence.md").unlink()

            errors = module.validate_work_item(item, validate_status_file=False)

            self.assertTrue(any("WI-LEDGER-MIGRATION-TARGET-DIGEST" in error for error in errors))

    def test_archive_projection_keeps_archive_tree_byte_identical(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item, ledger, work_items = self._make_item(root, archived=True)
            raw = self._canonical_raw()
            raw_line = canonical_bytes(raw) + b"\n"
            self._install_apply(item, ledger, work_items, raw_line, self._projected_canonical(raw))
            before = {path.relative_to(item): path.read_bytes() for path in item.rglob("*") if path.is_file()}

            module.validate_work_item(item)

            after = {path.relative_to(item): path.read_bytes() for path in item.rglob("*") if path.is_file()}
            self.assertEqual(before, after)

    def test_irrecoverable_disposition_requires_exact_manifest_bound_archive_path_and_unknown_digest(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item, _, _ = self._make_item(root, archived=True)
            closure = item / "closure.md"
            closure.write_text("canonical outcome\n", encoding="utf-8")
            disposition = {
                "schemaVersion": 1,
                "archiveIdentity": "archive-commit-001",
                "workItem": "work-items/archive/2026-08/legacy-item",
                "missingPath": ".reports/recovery-state-admission-audit.md",
                "disposition": "irrecoverable",
                "expectedDigest": "unknown",
                "searchReceipt": "search-001",
                "survivingArtifacts": [{"path": "closure.md", "sha256": digest(closure.read_bytes())}],
                "approvedBy": "human-001",
                "approvedAt": "2026-08-01T00:00:03Z",
            }
            self.assertEqual([], module.validate_manifest_bound_irrecoverable_disposition(disposition, "archive-commit-001", item))
            wildcard = {**disposition, "missingPath": "*"}
            self.assertTrue(any("WI-LEDGER-MIGRATION-MANIFEST-INVALID" in error for error in module.validate_manifest_bound_irrecoverable_disposition(wildcard, "archive-commit-001", item)))
            self.assertTrue(any("WI-LEDGER-MIGRATION-MANIFEST-INVALID" in error for error in module.validate_manifest_bound_irrecoverable_disposition({**disposition, "archiveIdentity": ""}, "", item)))

    def test_existing_legacy_obligation_normalizations_remain_composable(self):
        module = load_validator()
        launch = {
            "schemaVersion": 2, "runId": "launch-001", "workItem": "legacy-item",
            "role": "qa-engineer", "executionRole": "main", "status": "running", "gate": "none",
            "scope": ["scope"], "startedAt": "2026-08-01T00:00:00Z", "updatedAt": "2026-08-01T00:00:00Z",
            "eventKind": "launch", "lane": "legacy-lane",
        }
        raw = {
            "schemaVersion": 2, "runId": "terminal-001", "workItem": "legacy-item",
            "role": "qa-engineer", "executionRole": "main", "status": "revise", "gate": "REVISE",
            "scope": ["scope"], "startedAt": "2026-08-01T00:00:00Z", "updatedAt": "2026-08-01T00:00:01Z",
            "eventKind": "terminal", "launchRunId": "launch-001", "findingClass": "old-class",
        }
        digest_text = digest(canonical_bytes(raw))
        replacement = {**raw, "findingClass": "legacy-unclassified"}
        control = {
            "schemaVersion": 2, "runId": "migration-001", "workItem": "legacy-item", "role": "lead",
            "executionRole": "main", "status": "completed", "gate": "none",
            "scope": ["ledger-migration:invalid-finding-class"],
            "startedAt": "2026-08-01T00:00:02Z", "updatedAt": "2026-08-01T00:00:03Z",
            "eventKind": "legacy-obligation-migration", "migrationAction": "apply",
            "normalizationKind": "invalid-finding-class", "migratesRunId": "terminal-001",
            "migratesEventSha256": digest_text, "replacementEvent": replacement,
            "evidence": [{"kind": "manual-check", "ref": f"invalid-finding-class terminal-001 {digest_text} -> legacy-unclassified"}],
        }
        effective, counters, errors = module.project_legacy_obligation_migrations(
            [launch, raw, control],
            [
                {"sha256": digest(canonical_bytes(launch))},
                {"sha256": digest_text},
                {"sha256": digest(canonical_bytes(control))},
            ],
            Path("legacy-item"),
        )
        self.assertEqual([], errors)
        self.assertEqual(1, counters["projected"])
        self.assertEqual("legacy-unclassified", effective[1]["findingClass"])

    def test_manifest_shape_projection_chains_into_both_existing_legacy_normalizations(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item, ledger, work_items = self._make_item(root)
            launch_a = {
                "schemaVersion": 2, "runId": "launch-chain-a", "workItem": "legacy-item",
                "role": "qa-engineer", "executionRole": "main", "status": "running", "gate": "none",
                "scope": ["scope"], "startedAt": "2026-08-01T00:00:00Z", "updatedAt": "2026-08-01T00:00:00Z",
                "eventKind": "launch", "lane": "chain-a",
            }
            launch_b = {**launch_a, "runId": "launch-chain-b", "lane": "chain-b"}
            raw_a = {
                "runId": "terminal-chain-a", "workItem": "legacy-item", "role": "qa-engineer",
                "executionRole": "lead", "status": "revise", "gate": "REVISE", "scope": "scope",
                "evidence": "proof-a", "artifact": "evidence.md", "started": "2026-08-01T00:00:00Z", "updated": "2026-08-01T00:00:01Z",
                "eventKind": "terminal", "launchRunId": "launch-chain-a", "findingClass": "old-class",
            }
            raw_b = {
                "runId": "terminal-chain-b", "workItem": "legacy-item", "role": "qa-engineer",
                "executionRole": "lead", "status": "revise", "gate": "REVISE", "scope": "scope",
                "evidence": "proof-b", "artifact": "evidence.md", "started": "2026-08-01T00:00:00Z", "updated": "2026-08-01T00:00:01Z",
                "eventKind": "terminal", "launchRunId": "launch-chain-b", "scratchEvidence": "legacy scratch",
            }
            projected_a = self._projected_canonical(raw_a)
            projected_a.update({"role": "qa-engineer", "eventKind": "terminal", "launchRunId": "launch-chain-a", "findingClass": "old-class"})
            projected_b = self._projected_canonical(raw_b)
            projected_b.update({"role": "qa-engineer", "eventKind": "terminal", "launchRunId": "launch-chain-b", "scratchEvidence": "legacy scratch"})
            digest_a = digest(canonical_bytes(raw_a))
            digest_b = digest(canonical_bytes(raw_b))
            replacement_a = {**projected_a, "findingClass": "legacy-unclassified"}
            replacement_b = {key: value for key, value in projected_b.items() if key != "scratchEvidence"}
            control_a = {
                "schemaVersion": 2, "runId": "migration-chain-a", "workItem": "legacy-item", "role": "lead", "executionRole": "main", "status": "completed", "gate": "none", "scope": ["ledger-migration:invalid-finding-class"], "startedAt": "2026-08-01T00:00:02Z", "updatedAt": "2026-08-01T00:00:03Z", "eventKind": "legacy-obligation-migration", "migrationAction": "apply", "normalizationKind": "invalid-finding-class", "migratesRunId": "terminal-chain-a", "migratesEventSha256": digest_a, "replacementEvent": replacement_a, "evidence": [{"kind": "manual-check", "ref": f"invalid-finding-class terminal-chain-a {digest_a} -> legacy-unclassified"}],
            }
            control_b = {
                "schemaVersion": 2, "runId": "migration-chain-b", "workItem": "legacy-item", "role": "lead", "executionRole": "main", "status": "completed", "gate": "none", "scope": ["ledger-migration:remove-string-scratch-evidence"], "startedAt": "2026-08-01T00:00:02Z", "updatedAt": "2026-08-01T00:00:03Z", "eventKind": "legacy-obligation-migration", "migrationAction": "apply", "normalizationKind": "remove-string-scratch-evidence", "migratesRunId": "terminal-chain-b", "migratesEventSha256": digest_b, "replacementEvent": replacement_b, "evidence": [{"kind": "manual-check", "ref": f"remove-string-scratch-evidence terminal-chain-b {digest_b} -> scratchEvidence absent"}],
            }
            lines = [canonical_bytes(row) + b"\n" for row in (launch_a, raw_a, launch_b, raw_b, control_a, control_b)]
            ledger_bytes = b"".join(lines)
            ledger.write_bytes(ledger_bytes)
            manifest_dir = work_items / "legacy-ledger-projection-manifests"
            manifest_dir.mkdir()
            entry_base = {
                "profileId": "canonical-v0-shape", "profileVersion": 1, "workItem": "work-items/active/legacy-item", "ledgerPath": "work-items/active/legacy-item/agent-runs.jsonl", "ledgerSha256": digest(ledger_bytes),
            }
            manifest = {"schemaVersion": 1, "manifestId": "manifest-chain", "profiles": [{"profileId": "canonical-v0-shape", "profileVersion": 1}], "entries": [
                {**entry_base, "entryId": "entry-chain-a", "rawLineOrdinals": [2], "rawLineSha256": [digest(lines[1])], "projectedEvents": [projected_a], "projectedEventSha256": [digest(canonical_bytes(projected_a))]},
                {**entry_base, "entryId": "entry-chain-b", "rawLineOrdinals": [4], "rawLineSha256": [digest(lines[3])], "projectedEvents": [projected_b], "projectedEventSha256": [digest(canonical_bytes(projected_b))]},
            ]}
            manifest_bytes = canonical_bytes(manifest)
            (manifest_dir / "manifest-chain.json").write_bytes(manifest_bytes)
            records = []
            for entry, ordinal, raw_digest, projected in ((manifest["entries"][0], 2, digest(lines[1]), projected_a), (manifest["entries"][1], 4, digest(lines[3]), projected_b)):
                records.append({"schemaVersion": 1, "operationId": f"projection-{entry['entryId']}", "state": "apply", "profileId": "canonical-v0-shape", "profileVersion": 1, "manifestId": "manifest-chain", "manifestSha256": digest(manifest_bytes), "manifestEntryId": entry["entryId"], "workItem": entry_base["workItem"], "ledgerPath": entry_base["ledgerPath"], "ledgerSha256": entry_base["ledgerSha256"], "rawLineOrdinal": ordinal, "rawLineSha256": raw_digest, "projectedEvent": projected, "projectedEventSha256": digest(canonical_bytes(projected)), "recordedAt": "2026-08-01T00:00:04Z"})
            (work_items / "legacy-ledger-projections.jsonl").write_bytes(b"".join(canonical_bytes(row) + b"\n" for row in records))
            errors: list[str] = []
            metadata: list[dict[str, object]] = []
            events = module.load_jsonl(ledger, errors, metadata, ledger_bytes)
            shaped, _, projection_errors = module.project_manifest_bound_legacy_ledger_projections(events, metadata, item, ledger, ledger_bytes)
            effective, _, migration_errors = module.project_legacy_obligation_migrations(shaped, metadata, item)

            self.assertEqual([], errors + projection_errors + migration_errors)
            self.assertEqual("legacy-unclassified", effective[1]["findingClass"])
            self.assertNotIn("scratchEvidence", effective[3])


if __name__ == "__main__":
    unittest.main()
