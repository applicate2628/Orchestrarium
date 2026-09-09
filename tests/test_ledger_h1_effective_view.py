#!/usr/bin/env python3
"""Synthetic tests for the receipt-gated sealed-prefix validator reader."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate-work-item-state.py"
CHECKER = ROOT / "scripts" / "check-work-items-state.py"
POLICY = "2026-08-28-ledger-h1-compatibility-boundary"
PROFILE = "sealed-active-prefix-v1"


def load_validator():
    spec = importlib.util.spec_from_file_location("ledger_h1_validator", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_checker():
    spec = importlib.util.spec_from_file_location("ledger_h1_checker", CHECKER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def domain_digest(domain: str, value: object) -> str:
    return digest(domain.encode("ascii") + b"\0" + canonical(value))


def mask(**enabled: bool) -> dict[str, bool]:
    result = {
        "launchEligible": False,
        "terminalEligible": False,
        "reviseTargetEligible": False,
        "closerEligible": False,
        "artifactEvidenceEligible": False,
    }
    result.update(enabled)
    return result


def event(run_id: str, work_item: str, **values: object) -> dict[str, object]:
    result: dict[str, object] = {
        "schemaVersion": 2,
        "runId": run_id,
        "workItem": work_item,
        "role": "analyst",
        "executionRole": "internal",
        "status": "completed",
        "gate": "none",
        "scope": ["synthetic reader fixture"],
        "startedAt": "2026-09-08T00:00:00Z",
        "updatedAt": "2026-09-08T00:00:01Z",
    }
    result.update(values)
    return result


def ledger_bytes(events: list[dict[str, object]]) -> bytes:
    return b"".join(canonical(row) + b"\n" for row in events)


def authority_view(
    ledger_path: str,
    prefix: bytes,
    events: list[dict[str, object]],
    masks: list[dict[str, bool]],
    *,
    discharged_revises: tuple[str, ...] = (),
) -> tuple[dict[str, object], dict[str, object]]:
    lines = prefix.splitlines(keepends=True)
    rows = []
    eligible_launches: list[str] = []
    settled_launches: list[str] = []
    open_revises: list[str] = []
    for ordinal, (raw_event, authority, line) in enumerate(
        zip(events, masks, lines), start=1
    ):
        run_id = raw_event["runId"]
        if authority["launchEligible"]:
            eligible_launches.append(run_id)
        if authority["terminalEligible"]:
            settled_launches.append(raw_event["launchRunId"])
        if authority["reviseTargetEligible"]:
            open_revises.append(run_id)
        rows.append(
            {
                "ledgerPath": ledger_path,
                "rawLineOrdinal": ordinal,
                "rawLineSha256": digest(line),
                "projectedEventSha256": domain_digest(
                    "orchestrarium:ledger-h1:projected-event:v1", raw_event
                ),
                "authority": authority,
                "authorityMaskSha256": domain_digest(
                    "orchestrarium:ledger-h1:authority-mask:v1", authority
                ),
            }
        )
    reduction = {
        "effectiveRowCount": len(rows),
        "eligibleLaunchRunIds": sorted(set(eligible_launches), key=lambda s: s.encode()),
        "settledLaunchRunIds": sorted(set(settled_launches), key=lambda s: s.encode()),
        "openLaunchRunIds": sorted(
            set(eligible_launches) - set(settled_launches), key=lambda s: s.encode()
        ),
        "openReviseRunIds": sorted(
            set(open_revises) - set(discharged_revises), key=lambda s: s.encode()
        ),
    }
    view = {
        "schemaVersion": 1,
        "profileId": PROFILE,
        "profileVersion": 1,
        "ledgerPath": ledger_path,
        "prefixLineCount": len(lines),
        "prefixByteLength": len(prefix),
        "prefixSha256": digest(prefix),
        "rows": rows,
        "reduction": reduction,
    }
    return view, reduction


def synthetic_artifacts(
    module,
    root: Path,
    *,
    sealed_closer_artifact: str | None = None,
    sealed_closer_is_terminal: bool = False,
):
    item_a = root / "work-items" / "active" / "reader-a"
    item_b = root / "work-items" / "active" / "reader-b"
    item_a.mkdir(parents=True)
    item_b.mkdir(parents=True)
    for name in ("target.md", "other.md"):
        (item_a / name).write_text("synthetic artifact\n", encoding="utf-8")
    a_events = [
        event("launch-a-0001", "reader-a", eventKind="launch", status="running"),
        event(
            "terminal-a-01",
            "reader-a",
            eventKind="terminal",
            launchRunId="launch-a-0001",
        ),
    ]
    if sealed_closer_is_terminal:
        a_events.append(
            event("launch-c-0001", "reader-a", eventKind="launch", status="running")
        )
    a_events.append(
        event(
            "revise-a-0001",
            "reader-a",
            gate="REVISE",
            status="revise",
            artifact="target.md",
            findingClass="correctness",
        )
    )
    if sealed_closer_artifact is not None:
        a_events.append(
            event(
                "bad-closer-a1",
                "reader-a",
                role="analyst",
                executionRole="internal",
                gate="PASS",
                artifact=sealed_closer_artifact,
                closesRunIds=["revise-a-0001"],
                evidence=[{"kind": "review", "ref": "synthetic C3 evidence"}],
                **(
                    {"eventKind": "terminal", "launchRunId": "launch-c-0001"}
                    if sealed_closer_is_terminal
                    else {}
                ),
            )
        )
    b_events = [
        event(
            "launch-b-bad1",
            "reader-b",
            eventKind="launch",
            status="running",
            launchFlags="not-an-array",
        ),
        event(
            "terminal-bad-1",
            "reader-b",
            eventKind="terminal",
            launchRunId="launch-b-bad1",
        ),
        event("launch-b-open", "reader-b", eventKind="launch", status="running"),
        event(
            "legacy-running",
            "reader-b",
            status="running",
            gate="PENDING",
            updatedAt="2026-09-01T00:00:00Z",
        ),
    ]
    a_prefix = ledger_bytes(a_events)
    b_prefix = ledger_bytes(b_events)
    paths = [
        "work-items/active/reader-a/agent-runs.jsonl",
        "work-items/active/reader-b/agent-runs.jsonl",
    ]
    a_masks = [
        mask(launchEligible=True),
        mask(terminalEligible=True),
    ]
    if sealed_closer_is_terminal:
        a_masks.append(mask(launchEligible=True))
    a_masks.append(mask(reviseTargetEligible=True, artifactEvidenceEligible=True))
    if sealed_closer_artifact is not None:
        a_masks.append(
            mask(
                terminalEligible=sealed_closer_is_terminal,
                closerEligible=True,
                artifactEvidenceEligible=True,
            )
        )
    b_masks = [mask(), mask(), mask(launchEligible=True), mask()]
    views = []
    entries = []
    for index, (path, prefix, rows, masks_) in enumerate(
        zip(paths, (a_prefix, b_prefix), (a_events, b_events), (a_masks, b_masks)),
        start=1,
    ):
        view, reduction = authority_view(
            path,
            prefix,
            rows,
            masks_,
            discharged_revises=(
                ("revise-a-0001",)
                if index == 1 and sealed_closer_artifact == "target.md"
                else ()
            ),
        )
        views.append((view, reduction))
        entries.append(
            {
                "entryId": f"synthetic-entry-{index}",
                "profileId": PROFILE,
                "profileVersion": 1,
                "workItem": "/".join(path.split("/")[:-1]),
                "ledgerPath": path,
                "prefixLineCount": len(rows),
                "prefixByteLength": len(prefix),
                "prefixSha256": digest(prefix),
                "projectedViewSha256": domain_digest(
                    "orchestrarium:ledger-h1:projected-view:v1", view
                ),
            }
        )

    identities = sorted(
        (
            f"{entry['workItem'].split('/')[-1]}\0{run_id}"
            for entry, (_view, reduction) in zip(entries, views)
            for run_id in reduction["openReviseRunIds"]
        ),
        key=lambda value: value.encode("utf-8"),
    )
    identity_payload = "\n".join(identities).encode("utf-8")
    oracle = {
        "schemaVersion": 1,
        "ledgerPrefixes": [
            {"ledgerPath": entry["ledgerPath"], "prefixSha256": entry["prefixSha256"]}
            for entry in entries
        ],
        "openReviseIdentities": identities,
    }
    manifest = {
        "schemaVersion": 2,
        "manifestId": "synthetic-h1-ledgers",
        "policyDecision": POLICY,
        "profiles": [{"profileId": PROFILE, "profileVersion": 1}],
        "entries": entries,
        "openReviseIdentitySha256": digest(identity_payload),
        "openReviseOracleSha256": domain_digest(
            "orchestrarium:ledger-h1:open-revise-oracle:v1", oracle
        ),
    }
    manifest_bytes = canonical(manifest) + b"\n"
    manifest_sha = digest(manifest_bytes)
    h1_bytes = canonical({"schemaVersion": 1, "synthetic": True}) + b"\n"
    h1_sha = digest(h1_bytes)
    ordered_ids = [entry["entryId"] for entry in entries]
    group_id = "g-" + domain_digest(
        "orchestrarium:ledger-h1:registry-group:v1",
        ["apply", POLICY, manifest_sha, h1_sha, ordered_ids],
    )
    recorded_at = "2026-09-08T00:01:00Z"
    records = []
    for index, entry in enumerate(entries, start=1):
        operation_id = "m:" + domain_digest(
            "orchestrarium:ledger-h1:activation-member:v1",
            [group_id, index, entry["entryId"]],
        )
        records.append(
            {
                "schemaVersion": 2,
                "operationId": operation_id,
                "operationGroupId": group_id,
                "groupMemberIndex": index,
                "groupMemberCount": 2,
                "state": "apply",
                "profileId": PROFILE,
                "profileVersion": 1,
                "policyDecision": POLICY,
                "manifestId": manifest["manifestId"],
                "manifestSha256": manifest_sha,
                "manifestEntryId": entry["entryId"],
                "h1ManifestPath": "work-items/decision-h1-compatibility.json",
                "h1ManifestSha256": h1_sha,
                "workItem": entry["workItem"],
                "ledgerPath": entry["ledgerPath"],
                "prefixLineCount": entry["prefixLineCount"],
                "prefixByteLength": entry["prefixByteLength"],
                "prefixSha256": entry["prefixSha256"],
                "projectedViewSha256": entry["projectedViewSha256"],
                "recordedAt": recorded_at,
            }
        )
    record_lines = [canonical(record) + b"\n" for record in records]
    registry_before = b""
    registry_after = b"".join(record_lines)
    receipt = {
        "schemaVersion": 2,
        "receiptId": "",
        "state": "apply",
        "operationGroupId": group_id,
        "policyDecision": POLICY,
        "ledgerManifestPath": "work-items/legacy-ledger-projection-manifests/synthetic-h1-ledgers.json",
        "ledgerManifestSha256": manifest_sha,
        "h1ManifestPath": "work-items/decision-h1-compatibility.json",
        "h1ManifestSha256": h1_sha,
        "memberOperationIds": [record["operationId"] for record in records],
        "memberRecordSha256": [digest(line) for line in record_lines],
        "registryBeforeSha256": digest(registry_before),
        "registryAfterSha256": digest(registry_after),
        "recordedAt": recorded_at,
    }
    receipt["receiptId"] = "r-" + domain_digest(
        "orchestrarium:ledger-h1:receipt-id:v1",
        ["apply", group_id, receipt["registryBeforeSha256"], receipt["registryAfterSha256"]],
    )
    receipt_bytes = canonical(receipt) + b"\n"
    receipt_path = f"work-items/legacy-ledger-projection-receipts/{receipt['receiptId']}.json"
    artifacts = module.LedgerCompatibilityArtifactSetV1(
        ledger_bytes_by_path={paths[0]: a_prefix, paths[1]: b_prefix},
        h1_manifest_path="work-items/decision-h1-compatibility.json",
        h1_manifest_bytes=h1_bytes,
        ledger_manifest_path=receipt["ledgerManifestPath"],
        ledger_manifest_bytes=manifest_bytes,
        registry_bytes=registry_after,
        receipt_bytes_by_path={receipt_path: receipt_bytes},
    )
    return artifacts, (item_a, item_b), (paths[0], paths[1]), views


def materialize_live_artifacts(root: Path, artifacts) -> None:
    for relative, raw in artifacts.ledger_bytes_by_path.items():
        target = root.joinpath(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    for relative, raw in (
        (artifacts.h1_manifest_path, artifacts.h1_manifest_bytes),
        (artifacts.ledger_manifest_path, artifacts.ledger_manifest_bytes),
        ("work-items/legacy-ledger-projections.jsonl", artifacts.registry_bytes),
        *artifacts.receipt_bytes_by_path.items(),
    ):
        target = root.joinpath(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)


def revoked_artifacts(module, applied):
    manifest = json.loads(applied.ledger_manifest_bytes)
    entries = manifest["entries"]
    apply_lines = applied.registry_bytes.splitlines(keepends=True)
    apply_records = [json.loads(line) for line in apply_lines]
    manifest_sha = digest(applied.ledger_manifest_bytes)
    h1_sha = digest(applied.h1_manifest_bytes)
    group_id = "g-" + domain_digest(
        "orchestrarium:ledger-h1:registry-group:v1",
        ["revoke", POLICY, manifest_sha, h1_sha, [entry["entryId"] for entry in entries]],
    )
    recorded_at = "2026-09-08T00:02:00Z"
    records = []
    for index, (entry, apply_record, apply_line) in enumerate(
        zip(entries, apply_records, apply_lines), start=1
    ):
        operation_id = "m:" + domain_digest(
            "orchestrarium:ledger-h1:activation-member:v1",
            [group_id, index, entry["entryId"]],
        )
        records.append(
            {
                **{
                    key: value
                    for key, value in apply_record.items()
                    if key
                    not in {
                        "operationId",
                        "operationGroupId",
                        "groupMemberIndex",
                        "state",
                        "recordedAt",
                    }
                },
                "operationId": operation_id,
                "operationGroupId": group_id,
                "groupMemberIndex": index,
                "state": "revoke",
                "recordedAt": recorded_at,
                "revokeOfOperationId": apply_record["operationId"],
                "revokeOfOperationGroupId": apply_record["operationGroupId"],
                "revokeOfRecordSha256": digest(apply_line),
            }
        )
    revoke_lines = [canonical(record) + b"\n" for record in records]
    registry_after = applied.registry_bytes + b"".join(revoke_lines)
    receipt = {
        "schemaVersion": 2,
        "receiptId": "",
        "state": "revoke",
        "operationGroupId": group_id,
        "policyDecision": POLICY,
        "ledgerManifestPath": applied.ledger_manifest_path,
        "ledgerManifestSha256": manifest_sha,
        "h1ManifestPath": applied.h1_manifest_path,
        "h1ManifestSha256": h1_sha,
        "memberOperationIds": [record["operationId"] for record in records],
        "memberRecordSha256": [digest(line) for line in revoke_lines],
        "registryBeforeSha256": digest(applied.registry_bytes),
        "registryAfterSha256": digest(registry_after),
        "recordedAt": recorded_at,
    }
    receipt["receiptId"] = "r-" + domain_digest(
        "orchestrarium:ledger-h1:receipt-id:v1",
        ["revoke", group_id, receipt["registryBeforeSha256"], receipt["registryAfterSha256"]],
    )
    receipt_path = f"work-items/legacy-ledger-projection-receipts/{receipt['receiptId']}.json"
    return module.LedgerCompatibilityArtifactSetV1(
        ledger_bytes_by_path=applied.ledger_bytes_by_path,
        h1_manifest_path=applied.h1_manifest_path,
        h1_manifest_bytes=applied.h1_manifest_bytes,
        ledger_manifest_path=applied.ledger_manifest_path,
        ledger_manifest_bytes=applied.ledger_manifest_bytes,
        registry_bytes=registry_after,
        receipt_bytes_by_path={
            **applied.receipt_bytes_by_path,
            receipt_path: canonical(receipt) + b"\n",
        },
    )


def closed_status() -> str:
    return """# Status

## Current state
**Primary task status**: closed

## Active agents
- none

## Completed agents
- reader complete

## Next action
Archive.
"""


class LedgerH1EffectiveViewTests(unittest.TestCase):
    def test_apply_then_linked_revoke_returns_raw_inactive_contexts(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            applied, items, paths, _expected = synthetic_artifacts(module, root)
            for relative, raw in applied.ledger_bytes_by_path.items():
                target = root.joinpath(*relative.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
            baseline = module.load_effective_ledger_view(root, items[1], paths[1])
            baseline_errors: list[str] = []
            baseline_validity = module.derive_event_validity(
                baseline.rows, items[1], baseline_errors
            )
            baseline_public_errors = module.validate_work_item(
                items[1], strict_revise=False, validate_status_file=False
            )
            active = module._load_effective_ledger_group(
                root, compatibility_artifacts=applied
            )
            self.assertTrue(all(context.view is not None for context in active.values()))

            revoked = module._load_effective_ledger_group(
                root, compatibility_artifacts=revoked_artifacts(module, applied)
            )

            self.assertEqual(set(revoked), set(paths))
            self.assertTrue(
                all(context.observation.activation_state == "revoked" for context in revoked.values())
            )
            self.assertTrue(all(context.view is None for context in revoked.values()))
            self.assertTrue(
                all(
                    row.epoch == "raw" and row.authority == module._NO_LEDGER_AUTHORITY
                    for context in revoked.values()
                    for row in context.rows
                )
            )
            raw_errors: list[str] = []
            revoked_validity = module.derive_event_validity(
                revoked[paths[1]].rows, items[1], raw_errors
            )
            self.assertEqual(raw_errors, baseline_errors)
            self.assertEqual(revoked_validity, baseline_validity)
            self.assertTrue(any("launchFlags must" in error for error in raw_errors))

            revoked_artifact_set = revoked_artifacts(module, applied)
            public_errors = module.validate_work_item(
                items[1],
                strict_revise=False,
                validate_status_file=False,
                compatibility_artifacts=revoked_artifact_set,
            )
            self.assertEqual(public_errors, baseline_public_errors)

            materialize_live_artifacts(root, revoked_artifact_set)
            live_revoked = module._load_effective_ledger_group(root)
            self.assertTrue(
                all(
                    context.observation.activation_state == "revoked"
                    for context in live_revoked.values()
                )
            )

    def test_revoke_receipt_map_and_links_fail_closed(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            applied, _items, _paths, _expected = synthetic_artifacts(module, root)
            revoked = revoked_artifacts(module, applied)
            apply_path = next(iter(applied.receipt_bytes_by_path))
            missing = module.LedgerCompatibilityArtifactSetV1(
                **{
                    **revoked.__dict__,
                    "receipt_bytes_by_path": {
                        path: raw
                        for path, raw in revoked.receipt_bytes_by_path.items()
                        if path != apply_path
                    },
                }
            )
            extra = module.LedgerCompatibilityArtifactSetV1(
                **{
                    **revoked.__dict__,
                    "receipt_bytes_by_path": {
                        **revoked.receipt_bytes_by_path,
                        "work-items/legacy-ledger-projection-receipts/extra.json": b"{}\n",
                    },
                }
            )
            lines = revoked.registry_bytes.splitlines(keepends=True)
            bad_record = json.loads(lines[2])
            bad_record["revokeOfOperationId"] = "wrong-apply-member"
            bad_link = module.LedgerCompatibilityArtifactSetV1(
                **{
                    **revoked.__dict__,
                    "registry_bytes": b"".join(
                        [*lines[:2], canonical(bad_record) + b"\n", lines[3]]
                    ),
                }
            )

            for label, artifacts in (
                ("missing", missing),
                ("extra", extra),
                ("bad-link", bad_link),
            ):
                with self.subTest(label=label):
                    contexts = module._load_effective_ledger_group(
                        root, compatibility_artifacts=artifacts
                    )
                    self.assertTrue(
                        all(
                            context.observation.activation_state == "invalid"
                            and context.view is None
                            for context in contexts.values()
                        )
                    )
    def test_participant_detection_ignores_v1_receipts_but_detects_typed_h1_partials(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipts = root / "work-items" / "legacy-ledger-projection-receipts"
            receipts.mkdir(parents=True)
            (receipts / "v1-operation.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "operationId": "v1-operation",
                        "recordSha256": "1" * 64,
                        "registryBeforeSha256": "2" * 64,
                        "registrySha256": "3" * 64,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertFalse(module._ledger_h1_live_participants_exist(root))

            partials = (
                (
                    "work-items/legacy-ledger-projection-manifests/partial.json",
                    canonical(
                        {
                            "schemaVersion": 2,
                            "policyDecision": "2026-08-28-ledger-h1-compatibility-boundary",
                        }
                    ),
                ),
                (
                    "work-items/legacy-ledger-projections.jsonl",
                    canonical(
                        {
                            "schemaVersion": 2,
                            "profileId": "sealed-active-prefix-v1",
                        }
                    )
                    + b"\n",
                ),
                (
                    "work-items/legacy-ledger-projection-receipts/partial-v2.json",
                    canonical(
                        {
                            "schemaVersion": 2,
                            "ledgerManifestPath": "work-items/legacy-ledger-projection-manifests/partial.json",
                        }
                    )
                    + b"\n",
                ),
                (
                    "work-items/decision-h1-compatibility.json",
                    b"{}\n",
                ),
            )
            for relative, raw in partials:
                with self.subTest(relative=relative):
                    partial_root = root / relative.replace("/", "_")
                    target = partial_root.joinpath(*relative.split("/"))
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(raw)
                    self.assertTrue(
                        module._ledger_h1_live_participants_exist(partial_root)
                    )

    def test_complete_candidate_projects_group_once_without_mutation(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifacts, _items, paths, expected = synthetic_artifacts(module, root)
            before = dict(artifacts.ledger_bytes_by_path)

            contexts = module._load_effective_ledger_group(
                root, compatibility_artifacts=artifacts
            )
            again = module._load_effective_ledger_group(
                root, compatibility_artifacts=artifacts
            )

            self.assertEqual(set(contexts), set(paths))
            self.assertIs(contexts[paths[0]].invocation_token, contexts[paths[1]].invocation_token)
            self.assertIsNot(contexts[paths[0]].invocation_token, again[paths[0]].invocation_token)
            self.assertEqual(contexts[paths[0]].observation.activation_state, "active")
            self.assertEqual(contexts[paths[0]].view.wire, expected[0][0])
            self.assertEqual(contexts[paths[1]].view.wire, expected[1][0])
            self.assertEqual(contexts[paths[0]].group_open_revise_ids, ("reader-a\0revise-a-0001",))
            self.assertEqual(contexts[paths[0]].group_open_launch_ids, ("launch-b-open",))
            valid_errors: list[str] = []
            validity = module.derive_event_validity(
                contexts[paths[1]].rows,
                _items[1],
                valid_errors,
                context=contexts[paths[1]],
            )
            _open_revise, open_launches = module.validate_closure(
                contexts[paths[1]].rows,
                valid_errors,
                validity=validity,
                context=contexts[paths[1]],
            )
            self.assertEqual(valid_errors, [])
            self.assertEqual([row["runId"] for row in open_launches], ["launch-b-open"])
            for wrong_context in (contexts[paths[0]], again[paths[1]]):
                bypass_errors: list[str] = []
                denied = module.derive_event_validity(
                    contexts[paths[1]].rows,
                    _items[1],
                    bypass_errors,
                    context=wrong_context,
                )
                self.assertTrue(all(not row.authority.launch_eligible for row in denied))
                self.assertTrue(any("WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS" in error for error in bypass_errors))
            with self.assertRaises(TypeError):
                contexts[paths[0]].rows[0].event["gate"] = "PASS"
            self.assertEqual(dict(artifacts.ledger_bytes_by_path), before)
            self.assertFalse(any(root.rglob("*.json")))

    def test_complete_live_artifacts_use_the_same_receipt_gated_reader(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifacts, items, paths, expected = synthetic_artifacts(module, root)
            materialize_live_artifacts(root, artifacts)

            context = module.load_effective_ledger_view(root, items[0], paths[0])

            self.assertEqual(context.observation.activation_state, "active")
            self.assertEqual(context.view.wire, expected[0][0])
            self.assertEqual(
                module.validate_work_item(
                    items[0], strict_revise=False, validate_status_file=False
                ),
                [],
            )

    def test_live_active_group_validates_transactional_candidate_suffix(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifacts, items, paths, _expected = synthetic_artifacts(module, root)
            materialize_live_artifacts(root, artifacts)
            suffix = event("suffix-valid-1", "reader-b", eventKind="standalone")
            candidate = items[1] / "agent-runs.jsonl.tmp"
            candidate.write_bytes(artifacts.ledger_bytes_by_path[paths[1]] + canonical(suffix) + b"\n")

            errors = module.validate_work_item(
                items[1],
                ledger_path=candidate,
                strict_revise=False,
                validate_status_file=False,
            )

            self.assertEqual(errors, [])

    def test_live_active_group_rejects_malformed_transactional_suffix_without_raw_fallback(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifacts, items, paths, _expected = synthetic_artifacts(module, root)
            materialize_live_artifacts(root, artifacts)
            candidate = items[1] / "agent-runs.jsonl.tmp"
            candidate.write_bytes(artifacts.ledger_bytes_by_path[paths[1]] + b"{}\n")

            errors = module.validate_work_item(
                items[1],
                ledger_path=candidate,
                strict_revise=False,
                validate_status_file=False,
            )

            self.assertTrue(any("event missing required field" in error for error in errors))
            self.assertFalse(any("launchFlags must" in error for error in errors))
            self.assertFalse(any("invalid gate 'PENDING'" in error for error in errors))

    def test_stale_running_uses_receipt_minted_context_for_sealed_prefix(self):
        module = load_validator()
        checker = load_checker()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifacts, items, _paths, _expected = synthetic_artifacts(module, root)
            materialize_live_artifacts(root, artifacts)

            errors = checker.stale_running_errors(
                items[1],
                datetime(2026, 9, 10, tzinfo=UTC),
                timedelta(hours=1),
                module,
            )

            self.assertEqual(len(errors), 1)
            self.assertIn("launch-b-open", errors[0])
            self.assertNotIn("legacy-running", "\n".join(errors))

    def test_active_status_requires_current_closure_result(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifacts, items, paths, _expected = synthetic_artifacts(module, root)
            materialize_live_artifacts(root, artifacts)
            (items[1] / "status.md").write_text(closed_status(), encoding="utf-8")
            context = module.load_effective_ledger_view(root, items[1], paths[1])
            errors: list[str] = []

            module.validate_status(items[1], context, errors)

            self.assertTrue(
                any("WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS" in error for error in errors)
            )

    def test_live_terminal_suffix_closes_status_without_using_prefix_reduction(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifacts, items, paths, _expected = synthetic_artifacts(module, root)
            materialize_live_artifacts(root, artifacts)
            (items[1] / "status.md").write_text(closed_status(), encoding="utf-8")
            ledger = items[1] / "agent-runs.jsonl"
            terminal = event(
                "terminal-b-open",
                "reader-b",
                eventKind="terminal",
                launchRunId="launch-b-open",
            )
            ledger.write_bytes(ledger.read_bytes() + canonical(terminal) + b"\n")

            self.assertEqual(
                module.validate_work_item(
                    items[1], strict_revise=False, validate_status_file=True
                ),
                [],
            )

            ledger.write_bytes(ledger.read_bytes() + b"{}\n")
            malformed = module.validate_work_item(
                items[1], strict_revise=False, validate_status_file=True
            )
            self.assertTrue(
                any("event missing required field" in error for error in malformed)
            )

    def test_receipt_digest_and_prefix_drift_are_non_authorizing(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifacts, _items, paths, _expected = synthetic_artifacts(module, root)
            receipt_path, receipt_bytes = next(iter(artifacts.receipt_bytes_by_path.items()))
            broken_receipt = copy.deepcopy(json.loads(receipt_bytes))
            broken_receipt["registryAfterSha256"] = "0" * 64
            invalid_receipt = module.LedgerCompatibilityArtifactSetV1(
                **{
                    **artifacts.__dict__,
                    "receipt_bytes_by_path": {
                        receipt_path: canonical(broken_receipt) + b"\n"
                    },
                }
            )
            contexts = module._load_effective_ledger_group(
                root, compatibility_artifacts=invalid_receipt
            )
            self.assertTrue(all(context.view is None for context in contexts.values()))
            self.assertTrue(
                all(
                    "WI-LEDGER-COMPAT-RECEIPT-INVALID" in context.observation.failure_ids
                    for context in contexts.values()
                )
            )

            changed = dict(artifacts.ledger_bytes_by_path)
            changed[paths[0]] = b" " + changed[paths[0]][1:]
            drifted = module.LedgerCompatibilityArtifactSetV1(
                **{**artifacts.__dict__, "ledger_bytes_by_path": changed}
            )
            contexts = module._load_effective_ledger_group(
                root, compatibility_artifacts=drifted
            )
            self.assertTrue(
                all(
                    "WI-LEDGER-MIGRATION-LEDGER-DRIFT" in context.observation.failure_ids
                    for context in contexts.values()
                )
            )

    def test_mask_aware_closure_keeps_ineligible_terminal_from_settling(self):
        module = load_validator()
        authority = module.LedgerAuthorityV1
        rows = (
            module.RuntimeLedgerRowV1(
                event={"runId": "launch-open", "eventKind": "launch", "gate": "none"},
                raw_line_ordinal=1,
                raw_line_sha256="1" * 64,
                raw_body_sha256="1" * 64,
                projected_event_sha256="2" * 64,
                epoch="sealed-prefix",
                authority=authority(True, False, False, False, False),
            ),
            module.RuntimeLedgerRowV1(
                event={"runId": "terminal-no", "eventKind": "terminal", "launchRunId": "launch-open", "gate": "none"},
                raw_line_ordinal=2,
                raw_line_sha256="3" * 64,
                raw_body_sha256="3" * 64,
                projected_event_sha256="4" * 64,
                epoch="sealed-prefix",
                authority=authority(False, False, False, False, False),
            ),
        )
        validity = tuple(module.LedgerEventValidityV1(False, row.authority) for row in rows)
        errors: list[str] = []
        _revise, launches = module.validate_closure(rows, errors, validity=validity)
        self.assertEqual(launches, [])
        self.assertTrue(any("WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS" in error for error in errors))

        forged_context = module.LedgerValidationContextV1(
            "work-items/active/forged/agent-runs.jsonl",
            rows,
            module.LedgerCompatibilityViewV1(
                {"ledgerPath": "work-items/active/forged/agent-runs.jsonl"},
                "5" * 64,
                {},
            ),
            module.LedgerCompatibilityObservationV1("active", (), ()),
            (),
            ("launch-open",),
            object(),
        )
        errors = []
        denied = module.derive_event_validity(
            rows, Path("forged"), errors, context=forged_context
        )
        self.assertTrue(all(not entry.authority.launch_eligible for entry in denied))
        self.assertTrue(any("WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS" in error for error in errors))

    def test_validate_work_item_rejects_mixed_candidate_inputs(self):
        module = load_validator()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifacts, items, _paths, _expected = synthetic_artifacts(module, root)
            errors = module.validate_work_item(
                items[0],
                ledger_path=items[0] / "agent-runs.jsonl",
                compatibility_artifacts=artifacts,
                validate_status_file=False,
            )
            self.assertTrue(any("WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
