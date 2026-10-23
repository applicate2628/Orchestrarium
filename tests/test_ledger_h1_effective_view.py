#!/usr/bin/env python3
"""Synthetic tests for the receipt-gated sealed-prefix validator reader."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import pytest
import sys
import tempfile
import unittest
from dataclasses import replace
from unittest import mock
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


SYNTHETIC_READER_B_INVALID_LAUNCH_OBSERVATION = (
    "terminal-bad-1: launchRunId launch-b-bad1 references an invalid launch event"
)


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


def test_disjoint_metadata_admission_never_acquires_missing_member_contents(tmp_path: Path) -> None:
    """P2/P4/L3: shared entrypoints and raw omission use metadata exclusion only."""
    module = load_validator()
    root = tmp_path / "metadata-only-selection"
    artifacts, members, paths, _expected = synthetic_artifacts(
        module, root, sealed_closer_artifact="target.md",
    )
    materialize_live_artifacts(root, artifacts)
    original_member = artifacts.ledger_bytes_by_path[paths[0]]
    (members[0] / "agent-runs.jsonl").unlink()
    (members[0] / "target.md").unlink()
    (members[0] / "status.md").write_bytes(b"invalid unselected status\n")
    (members[0] / "closure.md").write_bytes(b"invalid unselected closure\n")
    ordinary = root / "work-items" / "active" / "independent-selection"
    ordinary.mkdir(parents=True)
    selected = ordinary / "agent-runs.jsonl"
    captured = ledger_bytes([event("independent-record", ordinary.name)])
    selected.write_bytes(b"{}\n")
    candidate = ordinary / "agent-runs.jsonl.tmp"
    candidate.write_bytes(b"{}\n")
    relative = selected.relative_to(root).as_posix()
    lifecycle = module.load_lifecycle_owner()
    historical_before = {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*") if p.is_file() and ordinary not in p.parents
    }
    with mock.patch.object(module, "_load_live_ledger_h1_artifacts", side_effect=AssertionError("unselected content acquisition")), \
         mock.patch.object(module, "_load_effective_ledger_group", side_effect=AssertionError("unselected group semantics")), \
         mock.patch.object(lifecycle, "resolve_work_item_ledger_location", side_effect=AssertionError("unselected physical resolution")):
        assert module.validate_work_item(
            ordinary, ledger_path=candidate, selected_ledger_bytes=captured,
            strict_revise=False, validate_status_file=False,
        ) == []
        context = module.load_effective_ledger_view(root, ordinary, relative, selected_ledger_bytes=captured)
        default_raw = module._ordinary_raw_v2_effective_context(ordinary, relative, captured)
        member_raw = module._ordinary_raw_v2_effective_context(members[0], paths[0], original_member)
    for context in (context, default_raw):
        assert context.observation.activation_state == "inactive"
        assert context.observation.diagnostics == ()
        assert context.view is None and len(context.rows) == 1
        assert context.rows[0].event["runId"] == "independent-record"
        assert not isinstance(context.invocation_token, module._LedgerInvocationTokenV1)
        assert context.group_open_revise_ids == context.group_open_launch_ids == ()
    assert member_raw.view is None and member_raw.observation.activation_state == "inactive"
    assert not isinstance(member_raw.invocation_token, module._LedgerInvocationTokenV1)
    refused = module.load_effective_ledger_view(root, members[0], paths[0])
    assert refused.observation.activation_state == "invalid"
    assert "WI-LEDGER-COMPAT-ACTIVATION-INCOMPLETE" in refused.observation.failure_ids
    assert {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*") if p.is_file() and ordinary not in p.parents
    } == historical_before


def test_metadata_partition_and_potential_members_fail_closed(tmp_path: Path) -> None:
    """P3/P4/L2: metadata descriptors cannot confer group authority or aliases."""
    module = load_validator()
    root = tmp_path / "partition-negative-controls"
    artifacts, members, paths, _expected = synthetic_artifacts(module, root)
    materialize_live_artifacts(root, artifacts)
    metadata = module._load_live_ledger_h1_metadata(root)
    partition = module._validate_ledger_h1_partition(root, metadata)
    assert isinstance(partition, module._LedgerH1PartitionV1)
    assert metadata.ledger_bytes_by_path == {}
    assert not hasattr(partition, "invocation_token") and not hasattr(partition, "view")
    assert not hasattr(partition, "rows")
    damaged = [
        replace(metadata, h1_manifest_bytes=b""),
        replace(metadata, ledger_manifest_bytes=b""),
        replace(metadata, registry_bytes=b""),
        replace(metadata, receipt_bytes_by_path={}),
    ]
    for field, value in (
        ("prefixLineCount", 0), ("prefixByteLength", 0),
        ("prefixLineCount", True), ("prefixSha256", "bad"), ("workItem", ""),
    ):
        manifest = json.loads(metadata.ledger_manifest_bytes)
        manifest["entries"][0][field] = value
        damaged.append(replace(metadata, ledger_manifest_bytes=canonical(manifest) + b"\n"))
    reversed_manifest = json.loads(metadata.ledger_manifest_bytes)
    reversed_manifest["entries"].reverse()
    damaged.append(replace(metadata, ledger_manifest_bytes=canonical(reversed_manifest) + b"\n"))
    locations = {
        path: module.load_lifecycle_owner().resolve_work_item_ledger_location(
            root, logical_work_item=path.rsplit("/", 1)[0], logical_ledger_path=path,
        ) for path in paths
    }
    locations[paths[0]] = replace(
        locations[paths[0]], physical_work_item="work-items/active/unrelated-id",
        physical_ledger_path="work-items/active/unrelated-id/agent-runs.jsonl",
    )
    damaged.append(replace(metadata, participant_locations_by_path=locations))
    for candidate in damaged:
        rejected = module._validate_ledger_h1_partition(root, candidate)
        assert isinstance(rejected, module.LedgerValidationContextV1)
        assert rejected.observation.activation_state == "invalid"
        assert rejected.observation.failure_ids and not isinstance(rejected.invocation_token, module._LedgerInvocationTokenV1)
    alias = root / "work-items" / "archive" / "2026-10" / members[0].name
    alias.mkdir(parents=True)
    (alias / "agent-runs.jsonl").write_bytes(artifacts.ledger_bytes_by_path[paths[0]])
    rejected = module.load_effective_ledger_view(root, alias, (alias / "agent-runs.jsonl").relative_to(root).as_posix())
    assert rejected.observation.activation_state == "invalid"
    assert "WI-CATEGORY-DUAL-LOCATION" in rejected.observation.failure_ids
    classification, _failure = module._classify_ledger_h1_selection(
        "work-items/active/Reader-a", "work-items/active/Reader-a/agent-runs.jsonl", partition,
    )
    assert classification == "invalid"


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
            derive_errors: list[str] = []
            closure_errors: list[str] = []
            validity = module.derive_event_validity(
                contexts[paths[1]].rows,
                _items[1],
                derive_errors,
                context=contexts[paths[1]],
            )
            _open_revise, open_launches = module.validate_closure(
                contexts[paths[1]].rows,
                closure_errors,
                validity=validity,
                context=contexts[paths[1]],
            )
            expected_observation = [SYNTHETIC_READER_B_INVALID_LAUNCH_OBSERVATION]
            self.assertEqual(derive_errors, expected_observation)
            self.assertEqual(closure_errors, expected_observation)
            self.assertFalse(validity[0].current_schema_valid)
            self.assertEqual(validity[0].authority, module._NO_LEDGER_AUTHORITY)
            self.assertTrue(validity[1].current_schema_valid)
            self.assertEqual(validity[1].authority, module._NO_LEDGER_AUTHORITY)
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

            self.assertEqual(errors, [SYNTHETIC_READER_B_INVALID_LAUNCH_OBSERVATION])

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
                [SYNTHETIC_READER_B_INVALID_LAUNCH_OBSERVATION],
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


def test_selected_observation_acquisition_tracks_active_and_revoked_h1(tmp_path):
    module = load_validator()
    for state in ("active", "revoked"):
        root = tmp_path / state
        artifacts, items, paths, _expected = synthetic_artifacts(module, root)
        if state == "revoked":
            artifacts = revoked_artifacts(module, artifacts)
        materialize_live_artifacts(root, artifacts)
        states, acquired = [], []
        errors = module.validate_work_item(items[0], strict_revise=False, validate_status_file=False, obligation_state_out=states, ledger_acquisition_complete_out=acquired)
        assert acquired == [True] and len(states) == 1
        # Existing historical field errors remain owned by the revoked reader.
        if state == "active":
            assert errors == []
        observation = module._obligations_observation(items[0], None, True, {})
        assert observation["obligations"] is not None
        assert observation["ledgerSha256"] == digest((items[0] / "agent-runs.jsonl").read_bytes())


def test_h1_observation_preserves_semantic_error_and_rejects_partial_parse(tmp_path):
    module = load_validator()
    artifacts, items, paths, _expected = synthetic_artifacts(module, tmp_path)
    materialize_live_artifacts(tmp_path, artifacts)
    ledger = items[1] / "agent-runs.jsonl"
    original = ledger.read_bytes()
    # A current object with missing semantic fields is completely acquired.
    ledger.write_bytes(original + b"{}\n")
    observation = module._obligations_observation(items[1], None, True, {})
    assert observation["result"] == "FAIL" and observation["obligations"] is not None
    assert any("event missing required field" in value for value in observation["diagnostics"])
    for suffix in (b"{bad}\n", b"\xff\n", b"{}"):
        ledger.write_bytes(original + suffix)
        observation = module._obligations_observation(items[1], None, True, {})
        assert observation["result"] == "FAIL" and observation["obligations"] is None
        assert observation["diagnostics"]


def test_frozen_h1_absence_refuses_before_selected_acquisition(tmp_path, monkeypatch):
    module = load_validator()
    for state in ("active", "revoked"):
        root = tmp_path / state
        artifacts, items, paths, _expected = synthetic_artifacts(module, root)
        if state == "revoked":
            artifacts = revoked_artifacts(module, artifacts)
        materialize_live_artifacts(root, artifacts)
        selected = items[0] / "agent-runs.jsonl"
        original = Path.read_bytes
        with monkeypatch.context() as patch:
            def forbid_selected(path):
                assert path != selected, "H1 frozen absence must not read late selected contents"
                return original(path)
            patch.setattr(Path, "read_bytes", forbid_selected)
            acquired, states = [], []
            errors = module.validate_work_item(items[0], selected_ledger_absent=True, ledger_acquisition_complete_out=acquired, obligation_state_out=states, validate_status_file=False)
        assert any("WI-LEDGER-COMPAT-ACTIVATION-INCOMPLETE" in value for value in errors)
        assert True not in acquired and states == []


def test_h1_observation_uses_captured_present_image_after_live_change(tmp_path, monkeypatch):
    module = load_validator()
    artifacts, items, paths, _expected = synthetic_artifacts(module, tmp_path)
    materialize_live_artifacts(tmp_path, artifacts)
    selected = items[0] / "agent-runs.jsonl"
    captured = selected.read_bytes()
    baseline = module._obligations_observation(items[0], None, True, {})
    assert baseline["obligations"] is not None
    original = module.validate_work_item
    def change_selected(*args, **kwargs):
        selected.write_bytes(b"{late malformed row}\n")
        return original(*args, **kwargs)
    monkeypatch.setattr(module, "validate_work_item", change_selected)
    observed = module._obligations_observation(items[0], None, True, {})
    assert observed["ledgerSha256"] == digest(captured)
    assert observed["obligations"] == baseline["obligations"]
    assert observed["result"] == baseline["result"]


def test_post_derive_report_loss_reopens_exact_target_and_keeps_availability_only_edits_accepted(tmp_path):
    def run_case(label, mutation, alias_kind="file"):
        module = load_validator()
        root = tmp_path / label
        root.mkdir()
        artifacts, items, paths, _expected = synthetic_artifacts(
            module, root, sealed_closer_artifact="target.md"
        )
        item, path = items[0], paths[0]
        target_report = item / "report.md"
        alias = item / "alias.md"
        artifact_name = "report.md"
        directory_component = mutation == "retarget-alias" and alias_kind == "directory"
        if directory_component:
            real_directory = item / "alias-target"
            real_directory.mkdir()
            target_report = real_directory / "report.md"
            alias = item / "alias-directory"
            artifact_name = alias.name + "/report.md"
        target_report.write_bytes(b"synthetic selected legacy report\n")
        if mutation == "retarget-alias":
            alias.symlink_to(target_report.parent.name if directory_component else target_report.name,
                             target_is_directory=directory_component)
            if not directory_component:
                artifact_name = alias.name
        target = event(
            "target-review", item.name, role="security-reviewer",
            eventKind="standalone", gate="REVISE", status="revise",
            artifact=artifact_name, lane="implementation", effort="xhigh",
            findingClass="security",
        )
        closer = event(
            "closer-review", item.name, role="security-reviewer",
            eventKind="standalone", gate="PASS", artifact=artifact_name,
            lane="implementation", effort="xhigh",
            closesRunIds=["target-review"],
            evidence=[{"kind": "review", "ref": "synthetic independent re-verification"}],
        )
        ledger_bytes_by_path = dict(artifacts.ledger_bytes_by_path)
        ledger_bytes_by_path[path] += ledger_bytes([target, closer])
        artifacts = replace(artifacts, ledger_bytes_by_path=ledger_bytes_by_path)
        selected = artifacts.ledger_bytes_by_path[path]
        closer_ordinal = len(selected.splitlines())
        materialize_live_artifacts(root, artifacts)
        selected_ledger = root.joinpath(*path.replace("\\", "/").split("/"))
        selected_before = selected_ledger.read_bytes()
        report_before = target_report.read_bytes()

        if mutation == "retarget-alias":
            positive_axes, positive_states = [], []
            positive_errors = module.validate_work_item(
                item, validate_status_file=False, compatibility_artifacts=artifacts,
                authority_state_out=positive_axes, obligation_state_out=positive_states,
            )
            assert positive_errors == []
            assert len(positive_axes) == len(positive_states) == 1
            assert positive_axes[0][closer_ordinal].closer_eligible is True
            assert positive_axes[0][closer_ordinal].artifact_evidence_eligible is True
            assert "target-review" not in {row.run_id for row in positive_states[0].open_revise}
            assert alias.is_symlink() and (item / artifact_name).read_bytes() == report_before
            assert target_report.read_bytes() == report_before
            assert selected_ledger.read_bytes() == selected_before

        derivation = {"calls": 0, "applied": False}
        real_derive = module.derive_event_validity

        def derive_then_change_report(*args, **kwargs):
            result = real_derive(*args, **kwargs)
            derivation["calls"] += 1
            if args[1] == item and mutation is not None and not derivation["applied"]:
                if mutation == "retarget-alias":
                    alias.unlink()
                    alias.symlink_to("missing-directory" if directory_component else "missing.md",
                                     target_is_directory=directory_component)
                elif mutation == "remove":
                    target_report.unlink()
                else:
                    target_report.write_bytes(
                        b"new bytes, same required report availability\n"
                    )
                derivation["applied"] = True
            return result

        real_assemble = module._CurrentLedgerEvaluationV1.assemble
        pure_reconstructions = []

        def reconstruct_from_prepared(current, *, public_derive):
            if not current.inputs.received:
                return real_assemble(current, public_derive=public_derive)
            pure_reconstructions.append(True)
            with mock.patch.object(module, "_validate_event_fields", side_effect=AssertionError("schema replay during final derivation")), \
                 mock.patch.object(module, "_select_artifact_locator", side_effect=AssertionError("locator reselection during final derivation")), \
                 mock.patch.object(Path, "exists", side_effect=AssertionError("filesystem query during final derivation")), \
                 mock.patch.object(Path, "read_bytes", side_effect=AssertionError("file read during final derivation")), \
                 mock.patch.object(Path, "resolve", side_effect=AssertionError("native resolution during final derivation")):
                return real_assemble(current, public_derive=public_derive)

        axes, states = [], []
        with mock.patch.object(module, "derive_event_validity", derive_then_change_report), \
             mock.patch.object(module._CurrentLedgerEvaluationV1, "assemble", reconstruct_from_prepared):
            errors = module.validate_work_item(
                item,
                validate_status_file=False,
                compatibility_artifacts=artifacts,
                authority_state_out=axes,
                obligation_state_out=states,
            )

        assert derivation["calls"] > 0
        assert derivation["applied"] is (mutation is not None)
        assert len(axes) == len(states) == 1
        closer_axes = axes[-1][closer_ordinal]
        open_revise = {row.run_id for row in states[-1].open_revise}
        assert selected_ledger.read_bytes() == selected_before
        assert selected_before == selected

        if mutation in {"remove", "retarget-alias"}:
            assert errors
            assert pure_reconstructions
            if mutation == "retarget-alias":
                assert alias.is_symlink() and not alias.exists()
                assert target_report.read_bytes() == report_before
            else:
                assert not target_report.exists()
            assert closer_axes.closer_eligible is False
            assert closer_axes.artifact_evidence_eligible is False
            assert "target-review" in open_revise
        else:
            assert errors == []
            assert target_report.exists()
            assert closer_axes.closer_eligible is True
            assert closer_axes.artifact_evidence_eligible is True
            assert "target-review" not in open_revise
            if mutation == "edit":
                assert target_report.read_bytes() != report_before
            else:
                assert target_report.read_bytes() == report_before

    for label, mutation in (
        ("unchanged-report", None),
        ("availability-only-edit", "edit"),
        ("post-derive-removal", "remove"),
        ("post-derive-alias-retarget", "retarget-alias"),
    ):
        run_case(label, mutation)
        if mutation == "retarget-alias":
            run_case(label + "-directory-component", mutation, alias_kind="directory")


# Preserved failing evidence: ARCH-SIMPLER-ISSUER-STRIP-1 (fe98049d).
def test_stripped_sealed_issuer_projections_do_not_select_raw_receiving(tmp_path):
    from types import MappingProxyType

    module = load_validator()
    artifacts, items, paths, _ = synthetic_artifacts(module, tmp_path)
    context = module.load_effective_ledger_view(
        tmp_path, items[1], paths[1], compatibility_artifacts=artifacts
    )
    selected_before = dict(artifacts.ledger_bytes_by_path)
    assert any(row.epoch == "sealed-prefix" for row in context.rows)
    errors = []
    genuine = module.derive_event_validity(context.rows, items[1], errors, context=context)
    assert errors == [SYNTHETIC_READER_B_INVALID_LAUNCH_OBSERVATION]
    assert any(row.authority.launch_eligible for row in genuine)
    stripped_rows = tuple(replace(row, **({"_current_owner": None}
        if "_current_owner" in row.__dataclass_fields__ else {})) for row in context.rows)
    token_rows = dict(context.invocation_token.rows_by_path)
    token_rows[paths[1]] = stripped_rows
    token_updates = {"rows_by_path": MappingProxyType(token_rows)}
    if "current_by_path" in context.invocation_token.__dataclass_fields__:
        token_updates["current_by_path"] = MappingProxyType({})
    stripped_token = replace(context.invocation_token, **token_updates)
    stripped = replace(context, rows=stripped_rows, invocation_token=stripped_token,
                       _current_owner=None)
    errors = []
    denied = module.derive_event_validity(stripped_rows, items[1], errors, context=stripped)
    assert len(denied) == len(stripped_rows)
    assert any("WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS" in value for value in errors)
    assert all(row.authority == module._NO_LEDGER_AUTHORITY for row in denied)
    assert dict(artifacts.ledger_bytes_by_path) == selected_before
    from collections.abc import Mapping, Sequence

    def json_values(value):
        if isinstance(value, Mapping):
            return {key: json_values(member) for key, member in value.items()}
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return [json_values(member) for member in value]
        return value

    for component in ("wire-authority", "reduction", "group-member", "array-shape"):
        root = tmp_path / component
        local_artifacts, local_items, local_paths, _ = synthetic_artifacts(module, root)
        materialize_live_artifacts(root, local_artifacts)
        native_before = {path: (root / path).read_bytes() for path in local_paths}
        local_context = module.load_effective_ledger_view(root, local_items[1], local_paths[1])
        baseline_errors = []
        baseline = module.derive_event_validity(
            local_context.rows, local_items[1], baseline_errors, context=local_context
        )
        assert baseline_errors == [SYNTHETIC_READER_B_INVALID_LAUNCH_OBSERVATION] and len(baseline) == len(local_context.rows)
        wire_before = json_values(local_context.view.wire)
        reduction_before = json_values(local_context.view.reduction)
        group_row = local_context.invocation_token.rows_by_path[local_paths[0]][0]
        group_before = json_values(group_row.event)
        retained_digest = local_context.view.projected_view_sha256
        assert domain_digest("orchestrarium:ledger-h1:projected-view:v1", wire_before) == retained_digest
        mutation_error = None
        try:
            if component == "wire-authority":
                authority = local_context.view.wire["rows"][0]["authority"]
                authority["launchEligible"] = not authority["launchEligible"]
            elif component == "reduction":
                local_context.view.reduction["openLaunchRunIds"].append("unselected-native-launch")
            elif component == "group-member":
                group_row.event["scope"].append("altered other selected group member")
            else:
                reduction = local_context.view.wire["reduction"]
                assert isinstance(reduction["openLaunchRunIds"], list)
                reduction["openLaunchRunIds"] = tuple(reduction["openLaunchRunIds"])
        except Exception as exc:  # Only collection mutation; receiving below is not caught.
            mutation_error = type(exc).__name__
        wire_after = json_values(local_context.view.wire)
        reduction_after = json_values(local_context.view.reduction)
        changed = (wire_after != wire_before or reduction_after != reduction_before
                   or json_values(group_row.event) != group_before or component == "array-shape")
        if component == "array-shape":
            # json.dumps coerces tuple to array; the receiving shape still differs.
            assert wire_after == wire_before and reduction_after == reduction_before
        errors = []
        actual = module.derive_event_validity(
            local_context.rows, local_items[1], errors, context=local_context
        )
        assert isinstance(actual, tuple) and len(actual) == len(local_context.rows)
        if changed:
            if wire_after != wire_before:
                assert domain_digest("orchestrarium:ledger-h1:projected-view:v1", wire_after) != retained_digest
            assert any("WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS" in value for value in errors)
            assert all(row.authority == module._NO_LEDGER_AUTHORITY for row in actual)
        else:
            assert errors == [SYNTHETIC_READER_B_INVALID_LAUNCH_OBSERVATION]
            assert wire_after == wire_before and reduction_after == reduction_before
        assert {path: (root / path).read_bytes() for path in local_paths} == native_before

    # Retained custody is a separate public projection from both rows and H1 wire.
    from tests.test_mixed_current_ledger_recovery import _history_fixture, _history_cli
    custody_root = tmp_path / "custody-image"
    custody_item = custody_root / "work-items/active/held-history"
    _raw, admission = _history_fixture(custody_item)
    acquired = _history_cli(custody_item, admission)
    assert acquired.returncode == 0, acquired.stdout + acquired.stderr
    custody_ledger = custody_item / "agent-runs.jsonl"
    custody_before = custody_ledger.read_bytes()
    custody_context = module.load_effective_ledger_view(
        custody_root, custody_item, "work-items/active/held-history/agent-runs.jsonl")
    assert custody_context.history_custody and custody_context.unresolved_history
    hold = custody_context.history_custody[0]
    assert isinstance(hold.event["scope"], list)
    hold.event["scope"].append("altered retained custody event")
    custody_errors = []
    with mock.patch.object(module._CurrentLedgerEvaluationV1, "receive_again",
                           side_effect=AssertionError("altered custody reached evaluation")):
        refused = module.derive_event_validity(
            custody_context.rows, custody_item, custody_errors, context=custody_context)
    assert len(refused) == len(custody_context.rows)
    assert any("WI-LEDGER-HISTORY-BINDING" in value for value in custody_errors)
    assert all(row.authority == module._NO_LEDGER_AUTHORITY for row in refused)
    assert custody_ledger.read_bytes() == custody_before


# Preserved failing evidence: CF-SIMPLE-SEC-2-FOREIGN-ISSUER-DOWNGRADE (33112a20).
def test_genuine_foreign_issued_context_cannot_lose_native_selection(tmp_path):
    first = load_validator()
    item = tmp_path / "work-items/active/native-issuer"
    item.mkdir(parents=True)
    (item / "report.md").write_bytes(b"unchanged current report\n")
    (item / "status.md").write_text(closed_status(), encoding="utf-8")
    target = event("issuer-target-review", item.name, role="security-reviewer",
                   eventKind="standalone", gate="REVISE", status="revise",
                   artifact="report.md", lane="implementation", effort="xhigh",
                   findingClass="security")
    closer = event("issuer-closer-review", item.name, role="security-reviewer",
                   eventKind="standalone", gate="PASS", artifact="report.md",
                   lane="implementation", effort="xhigh",
                   closesRunIds=[target["runId"]],
                   evidence=[{"kind": "review", "ref": "independent current re-verification"}])
    ledger = item / "agent-runs.jsonl"
    before = ledger_bytes([target, closer])
    ledger.write_bytes(before)
    selected = "work-items/active/native-issuer/agent-runs.jsonl"
    context = first.load_effective_ledger_view(tmp_path, item, selected)
    errors = []
    genuine = first.derive_event_validity(context.rows, item, errors, context=context)
    assert errors == [] and genuine[-1].authority.closer_eligible
    original_closes = list(context.rows[-1].event["closesRunIds"])
    mutation_error = None
    try:
        context.rows[-1].event["closesRunIds"].append("additional-target")
    except Exception as exc:  # Observe mutation prevention, never a receiver exception.
        mutation_error = type(exc).__name__
    altered_closes = list(context.rows[-1].event["closesRunIds"])
    if altered_closes != original_closes:
        altered_errors = []
        denied = first.derive_event_validity(context.rows, item, altered_errors, context=context)
        assert isinstance(denied, tuple) and len(denied) == len(context.rows)
        assert any("WI-LEDGER-CUSTODY-STALE-TARGET" in value for value in altered_errors)
        assert all(row.authority == first._NO_LEDGER_AUTHORITY for row in denied)
    else:
        assert altered_closes == original_closes
    assert ledger.read_bytes() == before
    # Re-enter from the real unchanged native selection, not a repaired public projection.
    context = first.load_effective_ledger_view(tmp_path, item, selected)
    unchanged_errors = []
    genuine = first.derive_event_validity(context.rows, item, unchanged_errors, context=context)
    assert unchanged_errors == [] and genuine[-1].authority.closer_eligible
    assert list(context.rows[-1].event["closesRunIds"]) == original_closes
    # The receiving codec owns malformed JSON shapes before prepared evaluation.
    for malformed in ("object-key", "cycle", "unsupported"):
        malformed_context = first.load_effective_ledger_view(tmp_path, item, selected)
        nested = malformed_context.rows[-1].event["evidence"][0]
        if malformed == "object-key":
            nested[7] = "not-a-string-key"
        elif malformed == "cycle":
            nested["cycle"] = nested
        else:
            nested["unsupported"] = object()
        malformed_errors = []
        with mock.patch.object(first._CurrentLedgerEvaluationV1, "receive_again",
                               side_effect=AssertionError("malformed projection reached evaluation")):
            denied = first.derive_event_validity(
                malformed_context.rows, item, malformed_errors, context=malformed_context)
        assert len(denied) == len(malformed_context.rows)
        assert all(row.authority == first._NO_LEDGER_AUTHORITY for row in denied)
        assert any("WI-LEDGER-CUSTODY-STALE-TARGET" in value for value in malformed_errors)
        assert ledger.read_bytes() == before
    helper_errors = []
    genuine_closure = first.validate_closure(
        context.rows, helper_errors, validity=genuine, context=context
    )
    assert genuine_closure == ([], []) and helper_errors == []
    helper_errors, genuine_pending = [], []
    genuine_inactive = first.resolve_closure_invalidations(
        context.rows, genuine, helper_errors, context=context,
        pending_closing_effects_out=genuine_pending,
    )
    assert genuine_inactive == set() and helper_errors == [] and genuine_pending == []
    helper_errors = []
    assert first.validate_status(
        item, context, helper_errors, current_open_launch_ids=()
    ) is None
    assert helper_errors == []
    other_item = tmp_path / "work-items/active/other-status-owner"
    other_item.mkdir()
    other_status = other_item / "status.md"
    other_status.write_text(closed_status(), encoding="utf-8")
    status_reads = []
    real_read_text = Path.read_text

    def observe_status_read(path, *args, **kwargs):
        if path == other_status:
            status_reads.append(path)
        return real_read_text(path, *args, **kwargs)

    wrong_item_errors = []
    with mock.patch.object(Path, "read_text", observe_status_read):
        refused_status = first.validate_status(
            other_item, context, wrong_item_errors, current_open_launch_ids=()
        )
    assert refused_status is None
    assert any("WI-LEDGER-" in value for value in wrong_item_errors)
    assert status_reads == []
    for receiver in ("derive", "reducer"):
        target_errors = []
        if receiver == "derive":
            denied = first.derive_event_validity(context.rows, other_item, target_errors, context=context)
            assert len(denied) == len(context.rows)
            assert all(row.authority == first._NO_LEDGER_AUTHORITY for row in denied)
        else:
            denied = first._reduce_effective_current_state(context.rows, other_item, target_errors, None, context=context)
            assert denied == ((), (), [], [])
        assert any("WI-LEDGER-HISTORY-BINDING: current input owner differs" in value for value in target_errors)
    assert ledger.read_bytes() == before
    # Bad argument binding must leave no borrowed invocation behind.
    with unittest.TestCase().assertRaises(TypeError):
        first.derive_event_validity(context.rows, item, [], context=context, unexpected_argument=True)
    with unittest.TestCase().assertRaises(TypeError):
        first._reduce_effective_current_state(context.rows, item, [], None, context=context,
                                               unexpected_argument=True)
    after_bad_arguments = []
    still_genuine = first.derive_event_validity(context.rows, item, after_bad_arguments, context=context)
    assert after_bad_arguments == [] and still_genuine[-1].authority.closer_eligible
    # ISSUED-SELECTION-R2-NATIVE-NEUTRAL-COLLISION: equal neutral values
    # keep value semantics when no issued context is supplied. Observe both
    # sides of a real native append before asserting the representation pair.
    fresh_rows = first._runtime_rows_from_events([target, closer])
    assert context.rows == fresh_rows
    assert all(row.epoch == "raw" and row.projection_transformation == "raw"
               and row.authority == first._NO_LEDGER_AUTHORITY for row in context.rows)
    owner = first.load_lifecycle_owner()
    real_capture = owner._capture_file_snapshot
    omitted_native_acquisitions = []

    def reject_omitted_native_capture(path, *args, **kwargs):
        if path == ledger:
            omitted_native_acquisitions.append(path)
            raise AssertionError("context=None acquired the omitted native ledger")
        return real_capture(path, *args, **kwargs)

    def value_observation(rows):
        derive_errors, reduction_errors = [], []
        with mock.patch.object(owner, "_capture_file_snapshot", reject_omitted_native_capture):
            validity = first.derive_event_validity(rows, item, derive_errors)
            reduction = first._reduce_effective_current_state(
                rows, item, reduction_errors, None, context=None)
        emitted = getattr(reduction, "context", None)
        if emitted is not None:
            assert emitted.selected_ledger_path == ""
        return (derive_errors, validity, reduction_errors, tuple(reduction))

    native_before, values_before = value_observation(context.rows), value_observation(fresh_rows)
    collision_review = {**target, "runId": "issuer-collision-new-review"}
    collision_after = before + ledger_bytes([collision_review])
    ledger.write_bytes(collision_after)
    native_after, values_after = value_observation(context.rows), value_observation(fresh_rows)
    stale_errors = []
    stale = first.derive_event_validity(context.rows, item, stale_errors, context=context)
    assert any("WI-LEDGER-CUSTODY-STALE-TARGET" in value for value in stale_errors)
    assert all(not row.authority.closer_eligible and not row.authority.artifact_evidence_eligible
               for row in stale)
    collision_states = []
    collision_errors = first.validate_work_item(item, validate_status_file=False,
        strict_revise=False, obligation_state_out=collision_states)
    assert collision_errors == [] and len(collision_states) == 1
    assert collision_review["runId"] in {row.run_id for row in collision_states[0].open_revise}
    assert omitted_native_acquisitions == []
    assert native_before == values_before, (native_before, values_before)
    assert native_after == values_after == values_before, (native_after, values_after, values_before)
    # Restore this owned fixture's exact selected image before the foreign-module arm.
    ledger.write_bytes(before)
    context = first.load_effective_ledger_view(tmp_path, item, selected)
    second = load_validator()  # same source, genuinely distinct module/classes
    assert second is not first
    new_review = {**target, "runId": "issuer-new-review"}
    after = before + ledger_bytes([new_review])
    ledger.write_bytes(after)
    errors = []
    denied = second.derive_event_validity(context.rows, item, errors, context=context)
    assert len(denied) == len(context.rows)
    assert errors
    assert all(not row.authority.closer_eligible and not row.authority.artifact_evidence_eligible
               for row in denied)
    errors = []
    result = second._reduce_effective_current_state(
        context.rows, item, errors, None, context=context
    )
    assert isinstance(result, tuple) and len(result) == 4 and errors
    assert all(not row.authority.closer_eligible and not row.authority.artifact_evidence_eligible
               for row in result[1])
    # Preserve the same genuine A RuntimeLedgerRow objects; supply no A context.
    errors = []
    rows_only_denied = second.derive_event_validity(context.rows, item, errors)
    assert isinstance(rows_only_denied, tuple) and len(rows_only_denied) == len(context.rows)
    assert errors
    assert all(not row.authority.closer_eligible and not row.authority.artifact_evidence_eligible
               for row in rows_only_denied)
    errors = []
    rows_only_result = second._reduce_effective_current_state(
        context.rows, item, errors, None, context=None
    )
    assert isinstance(rows_only_result, tuple) and len(rows_only_result) == 4 and errors
    assert all(not row.authority.closer_eligible and not row.authority.artifact_evidence_eligible
               for row in rows_only_result[1])
    states = []
    fresh_errors = second.validate_work_item(
        item, validate_status_file=False, strict_revise=False, obligation_state_out=states
    )
    assert fresh_errors == []
    assert len(states) == 1
    assert new_review["runId"] in {row.run_id for row in states[0].open_revise}
    fresh_context = second.load_effective_ledger_view(tmp_path, item, selected)
    helper_errors = []
    fresh_validity = second.derive_event_validity(
        fresh_context.rows, item, helper_errors, context=fresh_context
    )
    assert helper_errors == [] and len(fresh_validity) == len(fresh_context.rows)
    by_run_id = {row.event["runId"]: validity
                 for row, validity in zip(fresh_context.rows, fresh_validity)}
    # Use B's real typed validity for matching unchanged events, so a foreign
    # validity-class mismatch cannot masquerade as the required issuer refusal.
    helper_validity = tuple(by_run_id[row.event["runId"]] for row in context.rows)
    helper_errors = []
    denied_closure = second.validate_closure(
        context.rows, helper_errors, validity=helper_validity, context=context
    )
    assert isinstance(denied_closure, tuple) and len(denied_closure) == 2
    assert all(isinstance(part, list) for part in denied_closure)
    assert denied_closure == ([], []) and helper_errors
    helper_errors, denied_pending = [], []
    denied_inactive = second.resolve_closure_invalidations(
        context.rows, helper_validity, helper_errors, context=context,
        pending_closing_effects_out=denied_pending,
    )
    assert isinstance(denied_inactive, set) and denied_inactive == set()
    assert helper_errors and denied_pending == []
    helper_errors = []
    denied_status = second.validate_status(
        item, context, helper_errors, current_open_launch_ids=()
    )
    assert denied_status is None and helper_errors
    assert ledger.read_bytes() == after


@unittest.skipUnless(sys.platform == "win32", "calibrated CPython Windows pathname backend")
# Preserved failing evidence: CF-SIMPLE-SEC-3-PRE-ADMISSION-NATIVE-QUERY (33112a20).
def test_rejected_artifact_escape_never_queries_owned_outside_namespace(tmp_path):
    import ntpath

    outer = tmp_path / "owned-outer"
    root = outer / "l1/l2/l3/repo"
    root.mkdir(parents=True)
    module = load_validator()
    artifacts, items, paths, _ = synthetic_artifacts(module, root)
    outside = [root.parent / "outside/report.md", outer / "outside/report.md"]
    for path in outside:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"owned synthetic outside target\n")
    real = ntpath._getfinalpathname
    seen = []
    directory_reads = []
    owner = module.load_lifecycle_owner()
    real_capture = owner._capture_directory_snapshot
    real_scandir, real_listdir = os.scandir, os.listdir

    def observe_members(operation, path, *args, **kwargs):
        directory_reads.append(ntpath.normcase(ntpath.abspath(os.fsdecode(path))))
        return operation(path, *args, **kwargs)

    def observe(path):
        seen.append(ntpath.normcase(ntpath.abspath(path)))
        return real(path)

    with (mock.patch.object(ntpath, "_getfinalpathname", observe),
          mock.patch.object(os, "scandir", lambda path=".": observe_members(real_scandir, path)),
          mock.patch.object(os, "listdir", lambda path=".": observe_members(real_listdir, path)),
          mock.patch.object(owner, "_capture_directory_snapshot",
              lambda path, *args, **kwargs: observe_members(real_capture, path, *args, **kwargs))):
        # Calibrate real member acquisition, including the outside parent itself.
        list(os.scandir(outside[0].parent))
        os.listdir(outside[1].parent)
        owner._capture_directory_snapshot(outside[0].parent, failure_id="WI-TEST-DIRECTORY")
        assert {ntpath.normcase(str(path.parent)) for path in outside} <= set(directory_reads)
        (items[0] / "target.md").resolve()  # positive calibration of real backend
        assert seen
        positive = module.validate_work_item(
            items[0], validate_status_file=False, strict_revise=False,
            compatibility_artifacts=artifacts,
        )
        assert positive == []
        # A genuine repository-relative artifact uses the same public receiver.
        repository_artifact = root / "repository-report.md"
        repository_artifact.write_bytes(b"Synthetic repository-relative evidence.\n")
        legitimate = event("repository-selected-report", items[0].name, eventKind="standalone",
            gate="PASS", artifact=repository_artifact.name,
            evidence=[{"kind": "review", "ref": "owned in-bound control"}])
        legitimate_wires = dict(artifacts.ledger_bytes_by_path)
        legitimate_wires[paths[0]] += ledger_bytes([legitimate])
        assert module.validate_work_item(items[0], validate_status_file=False, strict_revise=False,
            compatibility_artifacts=replace(artifacts, ledger_bytes_by_path=legitimate_wires)) == []
        # Preserve a real owner-acquired current-history positive, not a mocked output.
        captured_root = root / "captured-control"
        captured_item = captured_root / "work-items/active/captured-item"
        captured_item.mkdir(parents=True)
        for name, raw in {"status.md": closed_status().encode(), "criteria.md": b"Current ledger required.\n",
                          "acquisition.md": b"Synthetic original history selection.\n",
                          "report.md": b"Synthetic captured report.\n",
                          "agent-runs.jsonl": ledger_bytes([event("captured-control-row", captured_item.name,
                              eventKind="standalone", gate="PASS", artifact="report.md",
                              evidence=[{"kind": "review", "ref": "captured control"}])])}.items():
            (captured_item / name).write_bytes(raw)
        directories = [captured_root, *sorted((path for path in captured_root.rglob("*") if path.is_dir()),
                                              key=lambda path: path.as_posix())]
        proofs = tuple(owner._capture_directory_snapshot(path, failure_id="WI-TEST-DIRECTORY")
                       for path in directories)
        snapshots = tuple(owner._capture_file_snapshot(path, failure_id="WI-TEST-CAPTURE")
                          for path in sorted(captured_root.rglob("*"), key=lambda path: path.as_posix())
                          if path.is_file())
        acquired = owner.AcquiredWorkItemInputV1(captured_root,
            tuple(owner.CapturedInputAssociationV1(value, value) for value in snapshots),
            tuple(owner.CapturedInputAssociationV1(value, value) for value in proofs))
        base = captured_item.relative_to(captured_root).as_posix()
        binding = module.CapturedWorkItemHistoryBindingV1(captured_root, captured_item.name,
            base + "/status.md", base, base + "/agent-runs.jsonl",
            module.HistoricalLedgerCriteriaV1(base + "/criteria.md", base + "/acquisition.md", True, "current"),
            tuple(module.CapturedHistoryFileV1(value.path.relative_to(captured_root).as_posix(), value,
                                              value.length, digest(value.data)) for value in snapshots), (),
            {proof.path.relative_to(captured_root).as_posix(): tuple(name for name, _metadata in proof.members)
             for proof in proofs}, acquired)
        captured = module.observe_captured_work_item_history(binding)
        assert captured.diagnostics == ()
        assert not captured.obligations.open_revise and not captured.obligations.open_launches
        bad = event("outside-selected-report", items[0].name, eventKind="standalone",
                    gate="PASS", artifact="../../../../outside/report.md",
                    evidence=[{"kind": "manual-check", "ref": "owned rejection fixture"}])
        selected = dict(artifacts.ledger_bytes_by_path)
        selected[paths[0]] += ledger_bytes([bad])
        candidate = replace(artifacts, ledger_bytes_by_path=selected)
        seen.clear()
        directory_reads.clear()
        errors = module.validate_work_item(
            items[0], validate_status_file=False, compatibility_artifacts=candidate
        )
    assert any("escape" in value.lower() for value in errors)
    parents = [ntpath.normcase(str(path.parent)) for path in outside]
    assert not [path for path in seen if any(path == parent or path.startswith(parent + ntpath.sep)
                                           for parent in parents)]
    root_key = ntpath.normcase(str(root))
    assert not [path for path in directory_reads
                if path != root_key and not path.startswith(root_key + ntpath.sep)]

    # The allowed alias owner must reject its outside target before querying it.
    alias = items[0] / "outside-alias.md"
    alias.symlink_to(outside[0])
    seen.clear()
    alias_errors = []
    with mock.patch.object(ntpath, "_getfinalpathname", observe):
        assert module.resolve_work_item_path(items[0], alias.name, "artifact", "outside-alias", alias_errors) is None
    assert any("escape" in value.lower() for value in alias_errors)
    assert not [path for path in seen if any(path == parent or path.startswith(parent + ntpath.sep)
                                           for parent in parents)]
    # A self-expanding directory-link cycle terminates by visited state, without a hop cap.
    cycle = items[0] / "expanding-cycle"
    cycle.symlink_to("expanding-cycle/tail", target_is_directory=True)
    cycle_errors = []
    assert module.resolve_work_item_path(items[0], cycle.name, "artifact", "cycle", cycle_errors) is None
    assert any("cycle" in value.lower() for value in cycle_errors)


def test_composite_status_consumes_parent_diagnostics_once(tmp_path):
    module = load_validator()
    item = tmp_path / "work-items/active/status-diagnostic-owner"
    item.mkdir(parents=True)
    (item / "status.md").write_text(closed_status(), encoding="utf-8")
    (item / "report.md").write_text("Owned synthetic report\n", encoding="utf-8")
    invalid = event("status-invalid-row", item.name, role="qa-engineer", eventKind="standalone",
                    gate="PASS", artifact="report.md", lane="implementation", effort="xhigh", scope=[],
                    evidence=[{"kind": "review", "ref": "independent synthetic verification"}])
    raw = ledger_bytes([invalid])
    (item / "agent-runs.jsonl").write_bytes(raw)
    disabled = module.validate_work_item(item, validate_status_file=False)
    enabled = module.validate_work_item(item, validate_status_file=True)
    assert disabled == ["status-invalid-row: scope must be a non-empty list"]
    assert enabled == disabled
    context = module.load_effective_ledger_view(tmp_path, item,
        "work-items/active/status-diagnostic-owner/agent-runs.jsonl")
    standalone = []
    assert module.validate_status(item, context, standalone, current_open_launch_ids=()) is None
    assert standalone == disabled
    assert (item / "agent-runs.jsonl").read_bytes() == raw
    for state in ("active", "revoked"):
        selected_root = tmp_path / state
        artifacts, items, _paths, _ = synthetic_artifacts(module, selected_root)
        if state == "revoked":
            artifacts = revoked_artifacts(module, artifacts)
        materialize_live_artifacts(selected_root, artifacts)
        selected_item = items[1]
        (selected_item / "status.md").write_text(closed_status(), encoding="utf-8")
        selected_ledger = selected_item / "agent-runs.jsonl"
        selected_ledger.write_bytes(selected_ledger.read_bytes() + ledger_bytes([
            event(f"status-{state}-invalid", selected_item.name, scope=[])]))
        if state == "revoked":
            # A real native pre-current V3 diagnosis belongs to admission, not
            # to replaceable current eligibility in the later receiving call.
            selected_ledger.write_bytes(selected_ledger.read_bytes() + ledger_bytes([
                event("status-revoked-v3-invalid", selected_item.name, schemaVersion=3)]))
        disabled = module.validate_work_item(selected_item, validate_status_file=False, strict_revise=False)
        enabled = module.validate_work_item(selected_item, validate_status_file=True, strict_revise=False)
        assert sum(f"status-{state}-invalid: scope must be a non-empty list" == value for value in disabled) == 1
        from collections import Counter
        status_failure = "status.md cannot be closed while ledger has running agents"
        assert isinstance(disabled, list) and isinstance(enabled, list)
        assert status_failure not in disabled
        assert Counter(enabled) == Counter([*disabled, status_failure])
        if state == "revoked":
            states = []
            actual = module.validate_work_item(selected_item, validate_status_file=False,
                strict_revise=False, obligation_state_out=states)
            previous = states[-1]._current_result
            assert actual and previous.admission_diagnostics
            receiving_errors = []
            received = previous.receive(selected_item, receiving_errors)
            assert receiving_errors == []
            assert received.admission_diagnostics == previous.admission_diagnostics
            assert received.context.observation.diagnostics == received.diagnostics
            assert received.context._current_owner.selected_input.diagnostics == received.admission_diagnostics
            assert received.context._current_owner.result.admission_diagnostics == received.admission_diagnostics
            assert received.projection_is_bound()
            received[2].append({"runId": "untrusted-admission-projection"})
            refusal_errors = []
            refused = received.with_admission((), refusal_errors)
            assert refusal_errors == [] and refused is not None
            assert any("WI-LEDGER-" in value for value in refused.diagnostics)
            assert "untrusted-admission-projection" not in {event["runId"] for event in refused[2]}
            assert all(not entry.authority.closer_eligible and not entry.authority.artifact_evidence_eligible
                       for entry in refused[1])
            assert refused.context.observation.diagnostics == refused.diagnostics and refused.projection_is_bound()



def test_raw_tuple_scope_keeps_native_failure_and_valid_neighbor(tmp_path):
    module = load_validator()
    item = tmp_path / "work-items/active/raw-admission-owner"
    item.mkdir(parents=True)
    invalid = event("tuple-invalid-row", item.name, scope=("fixture",))
    valid = event("raw-valid-launch", item.name, eventKind="launch", status="running")
    rows = [invalid, valid]
    derive_errors, reduction_errors = [], []
    validity = module.derive_event_validity(rows, item, derive_errors)
    reduction = module._reduce_effective_current_state(rows, item, reduction_errors, None, context=None)
    assert isinstance(reduction, tuple) and len(reduction) == 4
    assert derive_errors == reduction_errors == ["tuple-invalid-row: scope must be a non-empty list"]
    assert validity[0].current_schema_valid is False and validity[1].authority.launch_eligible
    assert len(reduction[1]) == 2 and reduction[1][0].current_schema_valid is False
    assert reduction[1][1].authority.launch_eligible
    assert {row["runId"] for row in reduction[3]} == {"raw-valid-launch"}
    assert type(invalid["scope"]) is tuple and invalid["scope"] == ("fixture",)


# Frozen original synthetic H1 data; production witness admission remains a separate binding.
_FROZEN_H1_SHARED_INPUT_HEX = {
    'work-items/active/golden-a/report.md': '53796e7468657469632061636365707465642061727469666163740a',
    'work-items/active/golden-a/verification.md': '53796e7468657469632064697374696e637420766572696669636174696f6e207265706f72740a',
    'work-items/decisions/2026-01-01-synthetic-legacy.md': '232053796e746865746963206c6567616379206465636973696f6e0a0a2d2069643a20323032362d30312d30312d73796e7468657469632d6c65676163790a2d207374617475733a2061636365707465640a2d206f776e65723a206172636869746563747572652d72657669657765720a0a53796e746865746963206c656761637920626f64792e0a',
    'work-items/decisions/2026-08-28-ledger-h1-compatibility-boundary.md': '2d2069643a20323032362d30382d32382d6c65646765722d68312d636f6d7061746962696c6974792d626f756e646172790a2d207374617475733a2061636365707465640a2d20646174653a20323032362d30382d32380a2d20646563696465642d62793a206172636869746563740a2d20636f6e746578743a2073796e7468657469632d7772697465720a2d20737570657273656465733a206e6f6e650a2d20737570657273656465642d62793a206e6f6e650a2d2068312d6d616e69666573743a20776f726b2d6974656d732f6465636973696f6e2d68312d636f6d7061746962696c6974792e6a736f6e0a2d2068312d626173656c696e652d7368613235363a20373032334143303434433738393341443734303443383730444245373944443638423937394642413243303133304533433546333434444542433244434132350a2d2068312d6375746f7665722d646174653a20323032362d30382d32380a0a23204465636973696f6e3a2053796e7468657469632077726974657220706f6c6963790a0a53796e74686574696320706f6c69637920626f64792e0a',
}

_FROZEN_H1_SPECIMEN_HEX = {
    'F-untyped-contradiction': {
        'ledgers': {
            'work-items/active/golden-a/agent-runs.jsonl': '7b22736368656d6156657273696f6e223a322c2272756e4964223a227461726765742d726576696577222c22776f726b4974656d223a22676f6c64656e2d61222c22726f6c65223a2271612d656e67696e656572222c22657865637574696f6e526f6c65223a22696e7465726e616c222c226576656e744b696e64223a227374616e64616c6f6e65222c22737461747573223a22726576697365222c2267617465223a22524556495345222c2273636f7065223a5b2273796e74686574696320686973746f726963616c20626f756e64617279225d2c226c616e65223a22696d706c656d656e746174696f6e222c226566666f7274223a2268696768222c22737461727465644174223a22323032362d30392d30385430303a30303a30305a222c22757064617465644174223a22323032362d30392d30385430303a30303a30315a222c226172746966616374223a227265706f72742e6d64222c2266696e64696e67436c617373223a22636f72726563746e657373227d0a7b22736368656d6156657273696f6e223a322c2272756e4964223a2277726f6e672d70726f66657373696f6e2d6c61756e6368222c22776f726b4974656d223a22676f6c64656e2d61222c22726f6c65223a226261636b656e642d656e67696e656572222c22657865637574696f6e526f6c65223a22696e7465726e616c222c226576656e744b696e64223a226c61756e6368222c22737461747573223a2272756e6e696e67222c2267617465223a226e6f6e65222c2273636f7065223a5b2273796e74686574696320686973746f726963616c20626f756e64617279225d2c226c616e65223a22696d706c656d656e746174696f6e222c226566666f7274223a2268696768222c22737461727465644174223a22323032362d30392d30385430303a30303a30305a222c22757064617465644174223a22323032362d30392d30385430303a30303a30315a227d0a7b22736368656d6156657273696f6e223a322c2272756e4964223a22636c6f73652d726576696577222c22776f726b4974656d223a22676f6c64656e2d61222c22726f6c65223a2271612d656e67696e656572222c22657865637574696f6e526f6c65223a22696e7465726e616c222c226576656e744b696e64223a227465726d696e616c222c22737461747573223a22636f6d706c65746564222c2267617465223a2250415353222c2273636f7065223a5b2273796e74686574696320686973746f726963616c20626f756e64617279225d2c226c616e65223a22696d706c656d656e746174696f6e222c226566666f7274223a2268696768222c22737461727465644174223a22323032362d30392d30385430303a30303a30305a222c22757064617465644174223a22323032362d30392d30385430303a30303a30315a222c226172746966616374223a227265706f72742e6d64222c22636c6f73657352756e496473223a5b227461726765742d726576696577225d2c2265766964656e6365223a5b7b226b696e64223a22726576696577222c22726566223a227265706f72742e6d64227d5d2c226c61756e636852756e4964223a2277726f6e672d70726f66657373696f6e2d6c61756e6368227d0a',
            'work-items/active/golden-b/agent-runs.jsonl': '7b22736368656d6156657273696f6e223a322c2272756e4964223a226f746865722d6f62736572766572222c22776f726b4974656d223a22676f6c64656e2d62222c22726f6c65223a2271612d656e67696e656572222c22657865637574696f6e526f6c65223a22696e7465726e616c222c226576656e744b696e64223a227374616e64616c6f6e65222c22737461747573223a22636f6d706c65746564222c2267617465223a226e6f6e65222c2273636f7065223a5b2273796e74686574696320686973746f726963616c20626f756e64617279225d2c226c616e65223a22696d706c656d656e746174696f6e222c226566666f7274223a2268696768222c22737461727465644174223a22323032362d30392d30385430303a30303a30305a222c22757064617465644174223a22323032362d30392d30385430303a30303a30315a227d0a',
        },
        'outputs': {
            'wire-1.json': '7b226c656467657250617468223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d612f6167656e742d72756e732e6a736f6e6c222c22707265666978427974654c656e677468223a313138302c227072656669784c696e65436f756e74223a332c22707265666978536861323536223a2239333763666630343164306134323933663832663330363336646333333037386361623539653335343566313935636138666364346332366434666130366666222c2270726f66696c654964223a227365616c65642d6163746976652d7072656669782d7631222c2270726f66696c6556657273696f6e223a312c22726564756374696f6e223a7b22656666656374697665526f77436f756e74223a332c22656c696769626c654c61756e636852756e496473223a5b2277726f6e672d70726f66657373696f6e2d6c61756e6368225d2c226f70656e4c61756e636852756e496473223a5b5d2c226f70656e52657669736552756e496473223a5b5d2c22736574746c65644c61756e636852756e496473223a5b2277726f6e672d70726f66657373696f6e2d6c61756e6368225d7d2c22726f7773223a5b7b22617574686f72697479223a7b22617274696661637445766964656e6365456c696769626c65223a747275652c22636c6f736572456c696769626c65223a66616c73652c226c61756e6368456c696769626c65223a66616c73652c22726576697365546172676574456c696769626c65223a747275652c227465726d696e616c456c696769626c65223a66616c73657d2c22617574686f726974794d61736b536861323536223a2238306435333039636238386163626335643733343863643038613062656430383763363361323065646132303530386237663466393762363733393664323637222c226c656467657250617468223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d612f6167656e742d72756e732e6a736f6e6c222c2270726f6a65637465644576656e74536861323536223a2239623635356631636531313930306134613966663964386138656137343161386434373633343638613562336333323530626465653363353864396134653935222c227261774c696e654f7264696e616c223a312c227261774c696e65536861323536223a2239333136623930626335663934653331333933346334303830626431623063316365653935343433376138376632383433656635616632393961363532383037227d2c7b22617574686f72697479223a7b22617274696661637445766964656e6365456c696769626c65223a66616c73652c22636c6f736572456c696769626c65223a66616c73652c226c61756e6368456c696769626c65223a747275652c22726576697365546172676574456c696769626c65223a66616c73652c227465726d696e616c456c696769626c65223a66616c73657d2c22617574686f726974794d61736b536861323536223a2235666261613631346436646265613135373363613662633330373332316639666663623265643663356163653432306631343632316461636538393432656166222c226c656467657250617468223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d612f6167656e742d72756e732e6a736f6e6c222c2270726f6a65637465644576656e74536861323536223a2236313633663630656466333131333631373166363132643935643665333262626336643065393135666636353435323638643139656365393533313663653635222c227261774c696e654f7264696e616c223a322c227261774c696e65536861323536223a2264326161383931333563613361393231653965663538653137666238396232623061633735373834663839373935353465616237653738373235623166373732227d2c7b22617574686f72697479223a7b22617274696661637445766964656e6365456c696769626c65223a747275652c22636c6f736572456c696769626c65223a747275652c226c61756e6368456c696769626c65223a66616c73652c22726576697365546172676574456c696769626c65223a66616c73652c227465726d696e616c456c696769626c65223a747275657d2c22617574686f726974794d61736b536861323536223a2231623933353237623139333564373431656331346137643232353464623932326561646336333834346564376663323634663831363136323139376461303039222c226c656467657250617468223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d612f6167656e742d72756e732e6a736f6e6c222c2270726f6a65637465644576656e74536861323536223a2235373934383937353266383736366362396661663531616338383233633438363565666435633963313034303030366265663935346637393132613137313331222c227261774c696e654f7264696e616c223a332c227261774c696e65536861323536223a2266373833636562623639373936303334656562623136646534616632653134333630356264366333323134373262653931363333343664323266393337656565227d5d2c22736368656d6156657273696f6e223a317d',
            'wire-2.json': '7b226c656467657250617468223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d622f6167656e742d72756e732e6a736f6e6c222c22707265666978427974654c656e677468223a3332372c227072656669784c696e65436f756e74223a312c22707265666978536861323536223a2261353663383635663936323066333235356631633833356365363136393633383935373165646639356563356561613965653537623030623136613635656233222c2270726f66696c654964223a227365616c65642d6163746976652d7072656669782d7631222c2270726f66696c6556657273696f6e223a312c22726564756374696f6e223a7b22656666656374697665526f77436f756e74223a312c22656c696769626c654c61756e636852756e496473223a5b5d2c226f70656e4c61756e636852756e496473223a5b5d2c226f70656e52657669736552756e496473223a5b5d2c22736574746c65644c61756e636852756e496473223a5b5d7d2c22726f7773223a5b7b22617574686f72697479223a7b22617274696661637445766964656e6365456c696769626c65223a66616c73652c22636c6f736572456c696769626c65223a66616c73652c226c61756e6368456c696769626c65223a66616c73652c22726576697365546172676574456c696769626c65223a66616c73652c227465726d696e616c456c696769626c65223a66616c73657d2c22617574686f726974794d61736b536861323536223a2237393034663031656432643930623934306530386637343036313438646632313466333931616537313063623762376336363430613066396130616363613261222c226c656467657250617468223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d622f6167656e742d72756e732e6a736f6e6c222c2270726f6a65637465644576656e74536861323536223a2266383536333938323338656433613562636665393835643839353535666634623764316631323266626665393765303434343236396237363466626663373635222c227261774c696e654f7264696e616c223a312c227261774c696e65536861323536223a2261353663383635663936323066333235356631633833356365363136393633383935373165646639356563356561613965653537623030623136613635656233227d5d2c22736368656d6156657273696f6e223a317d',
            'group-oracle.json': '7b226c65646765725072656669786573223a5b7b226c656467657250617468223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d612f6167656e742d72756e732e6a736f6e6c222c22707265666978536861323536223a2239333763666630343164306134323933663832663330363336646333333037386361623539653335343566313935636138666364346332366434666130366666227d2c7b226c656467657250617468223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d622f6167656e742d72756e732e6a736f6e6c222c22707265666978536861323536223a2261353663383635663936323066333235356631633833356365363136393633383935373165646639356563356561613965653537623030623136613635656233227d5d2c226f70656e5265766973654964656e746974696573223a5b5d2c22736368656d6156657273696f6e223a317d',
            'ledger-manifest.json': '7b22656e7472696573223a5b7b22656e7472794964223a2273796e7468657469632d656e7472792d31222c226c656467657250617468223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d612f6167656e742d72756e732e6a736f6e6c222c22707265666978427974654c656e677468223a313138302c227072656669784c696e65436f756e74223a332c22707265666978536861323536223a2239333763666630343164306134323933663832663330363336646333333037386361623539653335343566313935636138666364346332366434666130366666222c2270726f66696c654964223a227365616c65642d6163746976652d7072656669782d7631222c2270726f66696c6556657273696f6e223a312c2270726f6a656374656456696577536861323536223a2262373834633565646233353861383139303036643764633931306662613766386233356264646637333565306137306166613331366330383136353431646234222c22776f726b4974656d223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d61227d2c7b22656e7472794964223a2273796e7468657469632d656e7472792d32222c226c656467657250617468223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d622f6167656e742d72756e732e6a736f6e6c222c22707265666978427974654c656e677468223a3332372c227072656669784c696e65436f756e74223a312c22707265666978536861323536223a2261353663383635663936323066333235356631633833356365363136393633383935373165646639356563356561613965653537623030623136613635656233222c2270726f66696c654964223a227365616c65642d6163746976652d7072656669782d7631222c2270726f66696c6556657273696f6e223a312c2270726f6a656374656456696577536861323536223a2263613561643236303738353837326233333337343464636232306137633462633533386534363063373031383263633464626232633866313665633530646465222c22776f726b4974656d223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d62227d5d2c226d616e69666573744964223a2273796e7468657469632d626f756e646172792d676f6c64656e222c226f70656e5265766973654964656e74697479536861323536223a2265336230633434323938666331633134396166626634633839393666623932343237616534316534363439623933346361343935393931623738353262383535222c226f70656e5265766973654f7261636c65536861323536223a2231383635313132633264393336623662666466663134383136633639613333636436343139393037383638313733663931303264373139666233366633643232222c22706f6c6963794465636973696f6e223a22323032362d30382d32382d6c65646765722d68312d636f6d7061746962696c6974792d626f756e64617279222c2270726f66696c6573223a5b7b2270726f66696c654964223a227365616c65642d6163746976652d7072656669782d7631222c2270726f66696c6556657273696f6e223a317d5d2c22736368656d6156657273696f6e223a327d0a',
            'h1-manifest.json': '7b22626173656c696e65536861323536223a2237303233414330343443373839334144373430344338373044424537394444363842393739464241324330313330453343354633343444454243324443413235222c226375746f76657244617465223a22323032362d30382d3238222c22656e7472696573223a5b7b2270617468223a22323032362d30312d30312d73796e7468657469632d6c65676163792e6d64222c22736861323536223a2233333438433633374446303834344635423843433742323445433231464339373737413730334638424633393438443037363342364445394331433845454639222c227374617465223a2261646d6974746564227d5d2c22706f6c6963794465636973696f6e223a22323032362d30382d32382d6c65646765722d68312d636f6d7061746962696c6974792d626f756e64617279222c22736368656d6156657273696f6e223a317d0a',
            'registry.jsonl': '7b2267726f75704d656d626572436f756e74223a322c2267726f75704d656d626572496e646578223a312c2268314d616e696665737450617468223a22776f726b2d6974656d732f6465636973696f6e2d68312d636f6d7061746962696c6974792e6a736f6e222c2268314d616e6966657374536861323536223a2238666437643432336438363165373234646532633237626564633031356434613130373666386337313336303332623565616566336136306134616332653964222c226c656467657250617468223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d612f6167656e742d72756e732e6a736f6e6c222c226d616e6966657374456e7472794964223a2273796e7468657469632d656e7472792d31222c226d616e69666573744964223a2273796e7468657469632d626f756e646172792d676f6c64656e222c226d616e6966657374536861323536223a2232626338646433313132666464393339353263663463306332343234396331306265353432326666366137643830636537373366663162333630623537653762222c226f7065726174696f6e47726f75704964223a22672d38623634616333336663666533613265393364363834613065633561313930613434383565653030393733313966316135653939303364363437393761396335222c226f7065726174696f6e4964223a226d3a64366330306162363532323332386261383339643266373466333731316262646662303631313634613939666438323765393964613436613761363430353236222c22706f6c6963794465636973696f6e223a22323032362d30382d32382d6c65646765722d68312d636f6d7061746962696c6974792d626f756e64617279222c22707265666978427974654c656e677468223a313138302c227072656669784c696e65436f756e74223a332c22707265666978536861323536223a2239333763666630343164306134323933663832663330363336646333333037386361623539653335343566313935636138666364346332366434666130366666222c2270726f66696c654964223a227365616c65642d6163746976652d7072656669782d7631222c2270726f66696c6556657273696f6e223a312c2270726f6a656374656456696577536861323536223a2262373834633565646233353861383139303036643764633931306662613766386233356264646637333565306137306166613331366330383136353431646234222c227265636f726465644174223a22323032362d30392d30385430313a30303a30305a222c22736368656d6156657273696f6e223a322c227374617465223a226170706c79222c22776f726b4974656d223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d61227d0a7b2267726f75704d656d626572436f756e74223a322c2267726f75704d656d626572496e646578223a322c2268314d616e696665737450617468223a22776f726b2d6974656d732f6465636973696f6e2d68312d636f6d7061746962696c6974792e6a736f6e222c2268314d616e6966657374536861323536223a2238666437643432336438363165373234646532633237626564633031356434613130373666386337313336303332623565616566336136306134616332653964222c226c656467657250617468223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d622f6167656e742d72756e732e6a736f6e6c222c226d616e6966657374456e7472794964223a2273796e7468657469632d656e7472792d32222c226d616e69666573744964223a2273796e7468657469632d626f756e646172792d676f6c64656e222c226d616e6966657374536861323536223a2232626338646433313132666464393339353263663463306332343234396331306265353432326666366137643830636537373366663162333630623537653762222c226f7065726174696f6e47726f75704964223a22672d38623634616333336663666533613265393364363834613065633561313930613434383565653030393733313966316135653939303364363437393761396335222c226f7065726174696f6e4964223a226d3a39636231633961656535326639313334303537326538643931353261393361313664303461333364333833363337396261356330316563356631346537366164222c22706f6c6963794465636973696f6e223a22323032362d30382d32382d6c65646765722d68312d636f6d7061746962696c6974792d626f756e64617279222c22707265666978427974654c656e677468223a3332372c227072656669784c696e65436f756e74223a312c22707265666978536861323536223a2261353663383635663936323066333235356631633833356365363136393633383935373165646639356563356561613965653537623030623136613635656233222c2270726f66696c654964223a227365616c65642d6163746976652d7072656669782d7631222c2270726f66696c6556657273696f6e223a312c2270726f6a656374656456696577536861323536223a2263613561643236303738353837326233333337343464636232306137633462633533386534363063373031383263633464626232633866313665633530646465222c227265636f726465644174223a22323032362d30392d30385430313a30303a30305a222c22736368656d6156657273696f6e223a322c227374617465223a226170706c79222c22776f726b4974656d223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d62227d0a',
            'receipt.json': '7b2268314d616e696665737450617468223a22776f726b2d6974656d732f6465636973696f6e2d68312d636f6d7061746962696c6974792e6a736f6e222c2268314d616e6966657374536861323536223a2238666437643432336438363165373234646532633237626564633031356434613130373666386337313336303332623565616566336136306134616332653964222c226c65646765724d616e696665737450617468223a22776f726b2d6974656d732f6c65676163792d6c65646765722d70726f6a656374696f6e2d6d616e6966657374732f73796e7468657469632d626f756e646172792d676f6c64656e2e6a736f6e222c226c65646765724d616e6966657374536861323536223a2232626338646433313132666464393339353263663463306332343234396331306265353432326666366137643830636537373366663162333630623537653762222c226d656d6265724f7065726174696f6e496473223a5b226d3a64366330306162363532323332386261383339643266373466333731316262646662303631313634613939666438323765393964613436613761363430353236222c226d3a39636231633961656535326639313334303537326538643931353261393361313664303461333364333833363337396261356330316563356631346537366164225d2c226d656d6265725265636f7264536861323536223a5b2230343764376231613166373834663139653633303765636664316439666639626162663938643634643034633563336535393130336332616365646630383132222c2265363131663235323566613730336661353634313133373032333232383636336230373738643838373834656634636164393435653230653731656365346434225d2c226f7065726174696f6e47726f75704964223a22672d38623634616333336663666533613265393364363834613065633561313930613434383565653030393733313966316135653939303364363437393761396335222c22706f6c6963794465636973696f6e223a22323032362d30382d32382d6c65646765722d68312d636f6d7061746962696c6974792d626f756e64617279222c22726563656970744964223a22722d33666166626439333839663830633965636266323639623833303035313766313937396438363762303434313361396633363961373866316230383066333933222c227265636f726465644174223a22323032362d30392d30385430313a30303a30305a222c2272656769737472794166746572536861323536223a2239316333326538623064393463303563346231316130663339613038346662613131303130393563363661613439653861333137323137343864383166326639222c2272656769737472794265666f7265536861323536223a2265336230633434323938666331633134396166626634633839393666623932343237616534316534363439623933346361343935393931623738353262383535222c22736368656d6156657273696f6e223a322c227374617465223a226170706c79227d0a',
        },
    },
    '42ad-retained-invalid': {
        'ledgers': {
            'work-items/active/golden-a/agent-runs.jsonl': '7b22736368656d6156657273696f6e223a322c2272756e4964223a227461726765742d726576696577222c22776f726b4974656d223a22676f6c64656e2d61222c22726f6c65223a2271612d656e67696e656572222c22657865637574696f6e526f6c65223a22696e7465726e616c222c226576656e744b696e64223a227374616e64616c6f6e65222c22737461747573223a22726576697365222c2267617465223a22524556495345222c2273636f7065223a5b2273796e74686574696320686973746f726963616c20626f756e64617279225d2c226c616e65223a22696d706c656d656e746174696f6e222c226566666f7274223a2268696768222c22737461727465644174223a22323032362d30392d30385430303a30303a30305a222c22757064617465644174223a22323032362d30392d30385430303a30303a30315a222c226172746966616374223a227265706f72742e6d64222c2266696e64696e67436c617373223a22636f72726563746e657373227d0a7b22736368656d6156657273696f6e223a322c2272756e4964223a22636c6f73652d726576696577222c22776f726b4974656d223a22676f6c64656e2d61222c22726f6c65223a2271612d656e67696e656572222c22657865637574696f6e526f6c65223a22696e7465726e616c222c226576656e744b696e64223a227374616e64616c6f6e65222c22737461747573223a22636f6d706c65746564222c2267617465223a2250415353222c2273636f7065223a5b2273796e74686574696320686973746f726963616c20626f756e64617279225d2c226c616e65223a22696d706c656d656e746174696f6e222c226566666f7274223a2268696768222c22737461727465644174223a22323032362d30392d30385430303a30303a30305a222c22757064617465644174223a22323032362d30392d30385430303a30303a30315a222c226172746966616374223a227265706f72742e6d64222c22636c6f73657352756e496473223a5b227461726765742d726576696577225d2c2265766964656e6365223a5b7b226b696e64223a226172746966616374222c22726566223a22696e707574732f6f6c642e62696e222c22726573756c74223a227b5c226b696e645c223a5c2272657461696e65642d707265696d6167655c222c5c22736368656d6156657273696f6e5c223a317d227d5d7d0a',
            'work-items/active/golden-b/agent-runs.jsonl': '7b22736368656d6156657273696f6e223a322c2272756e4964223a226f746865722d6f62736572766572222c22776f726b4974656d223a22676f6c64656e2d62222c22726f6c65223a2271612d656e67696e656572222c22657865637574696f6e526f6c65223a22696e7465726e616c222c226576656e744b696e64223a227374616e64616c6f6e65222c22737461747573223a22636f6d706c65746564222c2267617465223a226e6f6e65222c2273636f7065223a5b2273796e74686574696320686973746f726963616c20626f756e64617279225d2c226c616e65223a22696d706c656d656e746174696f6e222c226566666f7274223a2268696768222c22737461727465644174223a22323032362d30392d30385430303a30303a30305a222c22757064617465644174223a22323032362d30392d30385430303a30303a30315a227d0a',
        },
        'outputs': {
            'wire-1.json': '7b226c656467657250617468223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d612f6167656e742d72756e732e6a736f6e6c222c22707265666978427974654c656e677468223a3837382c227072656669784c696e65436f756e74223a322c22707265666978536861323536223a2264303064366531666334663266663939633131393237613639306632346332653663656134346136626362363361666161383231363934396664613663626664222c2270726f66696c654964223a227365616c65642d6163746976652d7072656669782d7631222c2270726f66696c6556657273696f6e223a312c22726564756374696f6e223a7b22656666656374697665526f77436f756e74223a322c22656c696769626c654c61756e636852756e496473223a5b5d2c226f70656e4c61756e636852756e496473223a5b5d2c226f70656e52657669736552756e496473223a5b5d2c22736574746c65644c61756e636852756e496473223a5b5d7d2c22726f7773223a5b7b22617574686f72697479223a7b22617274696661637445766964656e6365456c696769626c65223a747275652c22636c6f736572456c696769626c65223a66616c73652c226c61756e6368456c696769626c65223a66616c73652c22726576697365546172676574456c696769626c65223a747275652c227465726d696e616c456c696769626c65223a66616c73657d2c22617574686f726974794d61736b536861323536223a2238306435333039636238386163626335643733343863643038613062656430383763363361323065646132303530386237663466393762363733393664323637222c226c656467657250617468223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d612f6167656e742d72756e732e6a736f6e6c222c2270726f6a65637465644576656e74536861323536223a2239623635356631636531313930306134613966663964386138656137343161386434373633343638613562336333323530626465653363353864396134653935222c227261774c696e654f7264696e616c223a312c227261774c696e65536861323536223a2239333136623930626335663934653331333933346334303830626431623063316365653935343433376138376632383433656635616632393961363532383037227d2c7b22617574686f72697479223a7b22617274696661637445766964656e6365456c696769626c65223a747275652c22636c6f736572456c696769626c65223a747275652c226c61756e6368456c696769626c65223a66616c73652c22726576697365546172676574456c696769626c65223a66616c73652c227465726d696e616c456c696769626c65223a66616c73657d2c22617574686f726974794d61736b536861323536223a2265633732326262613065396463343433303236623638663434353331323630353739316537396263373236666463356663376130323637656661626634633562222c226c656467657250617468223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d612f6167656e742d72756e732e6a736f6e6c222c2270726f6a65637465644576656e74536861323536223a2263383066626366643564643236613931303838376239636138356534333832323831653438396537333164343434646132303337303439633766326332396261222c227261774c696e654f7264696e616c223a322c227261774c696e65536861323536223a2264663737383539366465353730313265663665643430383333636266386263366362656465623332313963383161643931613034303362393565356332626639227d5d2c22736368656d6156657273696f6e223a317d',
            'wire-2.json': '7b226c656467657250617468223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d622f6167656e742d72756e732e6a736f6e6c222c22707265666978427974654c656e677468223a3332372c227072656669784c696e65436f756e74223a312c22707265666978536861323536223a2261353663383635663936323066333235356631633833356365363136393633383935373165646639356563356561613965653537623030623136613635656233222c2270726f66696c654964223a227365616c65642d6163746976652d7072656669782d7631222c2270726f66696c6556657273696f6e223a312c22726564756374696f6e223a7b22656666656374697665526f77436f756e74223a312c22656c696769626c654c61756e636852756e496473223a5b5d2c226f70656e4c61756e636852756e496473223a5b5d2c226f70656e52657669736552756e496473223a5b5d2c22736574746c65644c61756e636852756e496473223a5b5d7d2c22726f7773223a5b7b22617574686f72697479223a7b22617274696661637445766964656e6365456c696769626c65223a66616c73652c22636c6f736572456c696769626c65223a66616c73652c226c61756e6368456c696769626c65223a66616c73652c22726576697365546172676574456c696769626c65223a66616c73652c227465726d696e616c456c696769626c65223a66616c73657d2c22617574686f726974794d61736b536861323536223a2237393034663031656432643930623934306530386637343036313438646632313466333931616537313063623762376336363430613066396130616363613261222c226c656467657250617468223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d622f6167656e742d72756e732e6a736f6e6c222c2270726f6a65637465644576656e74536861323536223a2266383536333938323338656433613562636665393835643839353535666634623764316631323266626665393765303434343236396237363466626663373635222c227261774c696e654f7264696e616c223a312c227261774c696e65536861323536223a2261353663383635663936323066333235356631633833356365363136393633383935373165646639356563356561613965653537623030623136613635656233227d5d2c22736368656d6156657273696f6e223a317d',
            'group-oracle.json': '7b226c65646765725072656669786573223a5b7b226c656467657250617468223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d612f6167656e742d72756e732e6a736f6e6c222c22707265666978536861323536223a2264303064366531666334663266663939633131393237613639306632346332653663656134346136626362363361666161383231363934396664613663626664227d2c7b226c656467657250617468223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d622f6167656e742d72756e732e6a736f6e6c222c22707265666978536861323536223a2261353663383635663936323066333235356631633833356365363136393633383935373165646639356563356561613965653537623030623136613635656233227d5d2c226f70656e5265766973654964656e746974696573223a5b5d2c22736368656d6156657273696f6e223a317d',
            'ledger-manifest.json': '7b22656e7472696573223a5b7b22656e7472794964223a2273796e7468657469632d656e7472792d31222c226c656467657250617468223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d612f6167656e742d72756e732e6a736f6e6c222c22707265666978427974654c656e677468223a3837382c227072656669784c696e65436f756e74223a322c22707265666978536861323536223a2264303064366531666334663266663939633131393237613639306632346332653663656134346136626362363361666161383231363934396664613663626664222c2270726f66696c654964223a227365616c65642d6163746976652d7072656669782d7631222c2270726f66696c6556657273696f6e223a312c2270726f6a656374656456696577536861323536223a2238313031373263386466313966376434303338376434646337323733323566636237663436613435306565656232373439333332393433303037326363373832222c22776f726b4974656d223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d61227d2c7b22656e7472794964223a2273796e7468657469632d656e7472792d32222c226c656467657250617468223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d622f6167656e742d72756e732e6a736f6e6c222c22707265666978427974654c656e677468223a3332372c227072656669784c696e65436f756e74223a312c22707265666978536861323536223a2261353663383635663936323066333235356631633833356365363136393633383935373165646639356563356561613965653537623030623136613635656233222c2270726f66696c654964223a227365616c65642d6163746976652d7072656669782d7631222c2270726f66696c6556657273696f6e223a312c2270726f6a656374656456696577536861323536223a2263613561643236303738353837326233333337343464636232306137633462633533386534363063373031383263633464626232633866313665633530646465222c22776f726b4974656d223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d62227d5d2c226d616e69666573744964223a2273796e7468657469632d626f756e646172792d676f6c64656e222c226f70656e5265766973654964656e74697479536861323536223a2265336230633434323938666331633134396166626634633839393666623932343237616534316534363439623933346361343935393931623738353262383535222c226f70656e5265766973654f7261636c65536861323536223a2264663265333138353230613664666233306630353439343136623634666238316132633865303034333364363837656365363237653232646636313136663062222c22706f6c6963794465636973696f6e223a22323032362d30382d32382d6c65646765722d68312d636f6d7061746962696c6974792d626f756e64617279222c2270726f66696c6573223a5b7b2270726f66696c654964223a227365616c65642d6163746976652d7072656669782d7631222c2270726f66696c6556657273696f6e223a317d5d2c22736368656d6156657273696f6e223a327d0a',
            'h1-manifest.json': '7b22626173656c696e65536861323536223a2237303233414330343443373839334144373430344338373044424537394444363842393739464241324330313330453343354633343444454243324443413235222c226375746f76657244617465223a22323032362d30382d3238222c22656e7472696573223a5b7b2270617468223a22323032362d30312d30312d73796e7468657469632d6c65676163792e6d64222c22736861323536223a2233333438433633374446303834344635423843433742323445433231464339373737413730334638424633393438443037363342364445394331433845454639222c227374617465223a2261646d6974746564227d5d2c22706f6c6963794465636973696f6e223a22323032362d30382d32382d6c65646765722d68312d636f6d7061746962696c6974792d626f756e64617279222c22736368656d6156657273696f6e223a317d0a',
            'registry.jsonl': '7b2267726f75704d656d626572436f756e74223a322c2267726f75704d656d626572496e646578223a312c2268314d616e696665737450617468223a22776f726b2d6974656d732f6465636973696f6e2d68312d636f6d7061746962696c6974792e6a736f6e222c2268314d616e6966657374536861323536223a2238666437643432336438363165373234646532633237626564633031356434613130373666386337313336303332623565616566336136306134616332653964222c226c656467657250617468223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d612f6167656e742d72756e732e6a736f6e6c222c226d616e6966657374456e7472794964223a2273796e7468657469632d656e7472792d31222c226d616e69666573744964223a2273796e7468657469632d626f756e646172792d676f6c64656e222c226d616e6966657374536861323536223a2232306539313234326166633932333838343634643337353066386131616561313239633463396238643964653237613632656631646536363264326165643538222c226f7065726174696f6e47726f75704964223a22672d65626162313163643932303137303933636463646332616333303864336238633630323832623463623563636230393331353830303834326165393766643936222c226f7065726174696f6e4964223a226d3a37613264303236343064366566613065353465393061323734376139366661306139376135343437626338663336393562653938613964376564353264313138222c22706f6c6963794465636973696f6e223a22323032362d30382d32382d6c65646765722d68312d636f6d7061746962696c6974792d626f756e64617279222c22707265666978427974654c656e677468223a3837382c227072656669784c696e65436f756e74223a322c22707265666978536861323536223a2264303064366531666334663266663939633131393237613639306632346332653663656134346136626362363361666161383231363934396664613663626664222c2270726f66696c654964223a227365616c65642d6163746976652d7072656669782d7631222c2270726f66696c6556657273696f6e223a312c2270726f6a656374656456696577536861323536223a2238313031373263386466313966376434303338376434646337323733323566636237663436613435306565656232373439333332393433303037326363373832222c227265636f726465644174223a22323032362d30392d30385430313a30303a30305a222c22736368656d6156657273696f6e223a322c227374617465223a226170706c79222c22776f726b4974656d223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d61227d0a7b2267726f75704d656d626572436f756e74223a322c2267726f75704d656d626572496e646578223a322c2268314d616e696665737450617468223a22776f726b2d6974656d732f6465636973696f6e2d68312d636f6d7061746962696c6974792e6a736f6e222c2268314d616e6966657374536861323536223a2238666437643432336438363165373234646532633237626564633031356434613130373666386337313336303332623565616566336136306134616332653964222c226c656467657250617468223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d622f6167656e742d72756e732e6a736f6e6c222c226d616e6966657374456e7472794964223a2273796e7468657469632d656e7472792d32222c226d616e69666573744964223a2273796e7468657469632d626f756e646172792d676f6c64656e222c226d616e6966657374536861323536223a2232306539313234326166633932333838343634643337353066386131616561313239633463396238643964653237613632656631646536363264326165643538222c226f7065726174696f6e47726f75704964223a22672d65626162313163643932303137303933636463646332616333303864336238633630323832623463623563636230393331353830303834326165393766643936222c226f7065726174696f6e4964223a226d3a63363232366330353237663765306465313530623533643430393434373830303566383935383365643066623539366430336339643961363739653062666237222c22706f6c6963794465636973696f6e223a22323032362d30382d32382d6c65646765722d68312d636f6d7061746962696c6974792d626f756e64617279222c22707265666978427974654c656e677468223a3332372c227072656669784c696e65436f756e74223a312c22707265666978536861323536223a2261353663383635663936323066333235356631633833356365363136393633383935373165646639356563356561613965653537623030623136613635656233222c2270726f66696c654964223a227365616c65642d6163746976652d7072656669782d7631222c2270726f66696c6556657273696f6e223a312c2270726f6a656374656456696577536861323536223a2263613561643236303738353837326233333337343464636232306137633462633533386534363063373031383263633464626232633866313665633530646465222c227265636f726465644174223a22323032362d30392d30385430313a30303a30305a222c22736368656d6156657273696f6e223a322c227374617465223a226170706c79222c22776f726b4974656d223a22776f726b2d6974656d732f6163746976652f676f6c64656e2d62227d0a',
            'receipt.json': '7b2268314d616e696665737450617468223a22776f726b2d6974656d732f6465636973696f6e2d68312d636f6d7061746962696c6974792e6a736f6e222c2268314d616e6966657374536861323536223a2238666437643432336438363165373234646532633237626564633031356434613130373666386337313336303332623565616566336136306134616332653964222c226c65646765724d616e696665737450617468223a22776f726b2d6974656d732f6c65676163792d6c65646765722d70726f6a656374696f6e2d6d616e6966657374732f73796e7468657469632d626f756e646172792d676f6c64656e2e6a736f6e222c226c65646765724d616e6966657374536861323536223a2232306539313234326166633932333838343634643337353066386131616561313239633463396238643964653237613632656631646536363264326165643538222c226d656d6265724f7065726174696f6e496473223a5b226d3a37613264303236343064366566613065353465393061323734376139366661306139376135343437626338663336393562653938613964376564353264313138222c226d3a63363232366330353237663765306465313530623533643430393434373830303566383935383365643066623539366430336339643961363739653062666237225d2c226d656d6265725265636f7264536861323536223a5b2235353234313465343764383761313731666536333637643366333231386334363632663730626636393164343035376434373733636538343233633133643433222c2233636639646534306438306331653438336632373631646136663162343864333333383039333761363532653632356664343066633235323936646161363038225d2c226f7065726174696f6e47726f75704964223a22672d65626162313163643932303137303933636463646332616333303864336238633630323832623463623563636230393331353830303834326165393766643936222c22706f6c6963794465636973696f6e223a22323032362d30382d32382d6c65646765722d68312d636f6d7061746962696c6974792d626f756e64617279222c22726563656970744964223a22722d33616263356138643034326331663836613538353164653930333839326532633038643436363366326637336462386435336164646537383831333939323864222c227265636f726465644174223a22323032362d30392d30385430313a30303a30305a222c2272656769737472794166746572536861323536223a2235306166343365653661333763363866376264613333376638656466636630363662623366366264303734393930353663613537643138646166646166643630222c2272656769737472794265666f7265536861323536223a2265336230633434323938666331633134396166626634633839393666623932343237616534316534363439623933346361343935393931623738353262383535222c22736368656d6156657273696f6e223a322c227374617465223a226170706c79227d0a',
        },
    },
}

def _frozen_h1_inputs_current6a(module, root: Path, specimen: str):
    raw_specimen = _FROZEN_H1_SPECIMEN_HEX[specimen]
    inputs = {
        path: bytes.fromhex(value)
        for path, value in {
            **_FROZEN_H1_SHARED_INPUT_HEX,
            **raw_specimen["ledgers"],
        }.items()
    }
    outputs = {
        name: bytes.fromhex(value)
        for name, value in raw_specimen["outputs"].items()
    }
    wire_bytes = {}
    for name in ("wire-1.json", "wire-2.json"):
        raw = outputs[name]
        wire_bytes[json.loads(raw.decode("utf-8"))["ledgerPath"]] = raw
    ledger_manifest = json.loads(outputs["ledger-manifest.json"].decode("utf-8"))
    h1_manifest = json.loads(outputs["h1-manifest.json"].decode("utf-8"))
    receipt = json.loads(outputs["receipt.json"].decode("utf-8"))
    artifacts = module.LedgerCompatibilityArtifactSetV1(
        ledger_bytes_by_path={
            path: raw for path, raw in inputs.items()
            if path.endswith("/agent-runs.jsonl")
        },
        h1_manifest_path=receipt["h1ManifestPath"],
        h1_manifest_bytes=outputs["h1-manifest.json"],
        ledger_manifest_path=receipt["ledgerManifestPath"],
        ledger_manifest_bytes=outputs["ledger-manifest.json"],
        registry_bytes=outputs["registry.jsonl"],
        receipt_bytes_by_path={
            "work-items/legacy-ledger-projection-receipts/"
            + receipt["receiptId"] + ".json": outputs["receipt.json"]
        },
    )
    for relative, raw in inputs.items():
        target = root.joinpath(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    materialize_live_artifacts(root, artifacts)
    return artifacts, wire_bytes, ledger_manifest, h1_manifest, outputs["group-oracle.json"]


def _assert_frozen_h1_group_observation(contexts_by_path, wire_bytes, ledger_manifest, group_oracle_bytes):
    entries = {entry["ledgerPath"]: entry for entry in ledger_manifest["entries"]}
    group_oracle = json.loads(group_oracle_bytes)
    assert set(contexts_by_path) == set(wire_bytes) == set(entries)
    for path, context in contexts_by_path.items():
        assert context.observation.activation_state == "active"
        assert context.view is not None
        assert canonical(dict(context.view.wire)) == wire_bytes[path]
        assert context.view.projected_view_sha256 == entries[path]["projectedViewSha256"]
        assert domain_digest("orchestrarium:ledger-h1:projected-view:v1", dict(context.view.wire)) == entries[path]["projectedViewSha256"]
        assert set(context.invocation_token.rows_by_path) == set(entries)
        assert context.group_open_revise_ids == tuple(group_oracle["openReviseIdentities"])
        # Exact whole-wire equality includes every recorded mask and reduction.
        assert context.view.reduction == json.loads(wire_bytes[path])["reduction"]


def _assert_frozen_h1_current_split(errors, axes, states):
    assert len(axes) == len(states) == 1
    assert any("WI-LEDGER-LAUNCH-BINDING" in error for error in errors)
    assert "target-review" in {row.run_id for row in states[0].open_revise}
    assert "wrong-profession-launch" in {row.run_id for row in states[0].open_launches}
    assert axes[0][1].revise_target_eligible is True
    assert axes[0][2].launch_eligible is True
    assert axes[0][3].terminal_eligible is False
    assert axes[0][3].closer_eligible is False
    assert axes[0][3].artifact_evidence_eligible is False


def _frozen_h1_matching_current_fixture(root: Path):
    item = root / "work-items/active/matching-positive"
    item.mkdir(parents=True)
    (item / "report.md").write_bytes(b"synthetic matching commission evidence\n")
    common = {"role": "qa-engineer", "executionRole": "internal", "scope": ["report.md"],
              "lane": "implementation", "effort": "high"}
    target = event("matching-target-review", item.name, **common, eventKind="standalone",
                   gate="REVISE", status="revise", artifact="report.md", findingClass="correctness")
    launch = event("matching-launch", item.name, **common, eventKind="launch", status="running")
    terminal = event("matching-terminal", item.name, **common, eventKind="terminal", gate="PASS",
                     artifact="report.md", launchRunId=launch["runId"], closesRunIds=[target["runId"]],
                     evidence=[{"kind": "review", "ref": "report.md"}])
    fields = ("workItem", "role", "executionRole", "assignedRole", "provider", "model", "scope",
              "promptFile", "effort", "launchFlags")
    assert all((key in launch) == (key in terminal)
               and (key not in launch or launch[key] == terminal[key]) for key in fields)
    raw = ledger_bytes([target, launch, terminal])
    (item / "agent-runs.jsonl").write_bytes(raw)
    return item, raw


def _assert_frozen_h1_matching_current(errors, axes, states):
    assert errors == []
    assert len(axes) == len(states) == 1
    assert not states[0].open_revise and not states[0].open_launches
    assert axes[0][3].terminal_eligible is True
    assert axes[0][3].closer_eligible is True
    assert axes[0][3].artifact_evidence_eligible is True


def _frozen_h1_distinct_wire_cases(wire_bytes):
    selected = next(iter(wire_bytes))
    other = next(path for path in wire_bytes if path != selected)
    partial = {selected: wire_bytes[selected]}
    cases = [("omitted-member", partial)]
    noncanonical = dict(wire_bytes)
    noncanonical[other] += b" "
    cases.append(("noncanonical-wire-bytes", noncanonical))
    original = json.loads(wire_bytes[other])
    for label in ("wire-identity", "authority-mask", "reduction", "mask-digest"):
        value = copy.deepcopy(original)
        if label == "wire-identity":
            value["ledgerPath"] = "work-items/active/wrong-owner/agent-runs.jsonl"
        elif label == "authority-mask":
            mask = value["rows"][0]["authority"]
            mask["launchEligible"] = not mask["launchEligible"]
        elif label == "reduction":
            value["reduction"]["effectiveRowCount"] += 1
        else:
            value["rows"][0]["authorityMaskSha256"] = "0" * 64
        changed = dict(wire_bytes)
        changed[other] = canonical(value)
        cases.append((label, changed))
    wrong = "work-items/active/foreign-owner/agent-runs.jsonl"
    renamed = dict(wire_bytes)
    renamed[wrong] = renamed.pop(other)
    cases.append(("wrong-logical-key", renamed))
    extra = dict(wire_bytes)
    extra[wrong] = wire_bytes[other]
    cases.append(("extra-foreign-member", extra))
    unsafe = dict(wire_bytes)
    unsafe["../outside/agent-runs.jsonl"] = unsafe.pop(other)
    cases.append(("unsafe-logical-key", unsafe))
    return tuple(cases)


def _assert_frozen_h1_group_refusal(contexts_by_path, errors, axes):
    assert contexts_by_path
    assert all(context.observation.activation_state == "invalid" and context.view is None
               and context.observation.failure_ids for context in contexts_by_path.values())
    assert errors
    assert all(not any((mask.launch_eligible, mask.terminal_eligible, mask.revise_target_eligible,
                        mask.closer_eligible, mask.artifact_evidence_eligible))
               for group in axes for mask in group.values())


# Portable qualified66f observations; no active-work-item dependency.
_OWN_LAUNCH_PAIR_ROWS = [{'schemaVersion': 2, 'runId': 'own-target-revise', 'workItem': 'synthetic-own-launch', 'role': 'qa-engineer', 'executionRole': 'internal', 'status': 'revise', 'gate': 'REVISE', 'scope': ['own-launch-a', 'own-launch-b'], 'startedAt': '2026-09-08T00:00:00Z', 'updatedAt': '2026-09-08T00:00:01Z', 'assignedRole': 'qa-engineer', 'provider': 'codex', 'model': 'target-model-independent', 'promptFile': 'prompt.md', 'artifact': 'report.md', 'eventKind': 'standalone', 'lane': 'implementation', 'effort': 'high', 'findingClass': 'other'}, {'schemaVersion': 2, 'runId': 'own-launch-row', 'workItem': 'synthetic-own-launch', 'role': 'qa-engineer', 'executionRole': 'internal', 'status': 'running', 'gate': 'none', 'scope': ['own-launch-a', 'own-launch-b'], 'startedAt': '2026-09-08T00:00:00Z', 'updatedAt': '2026-09-08T00:00:01Z', 'assignedRole': 'qa-engineer', 'provider': 'codex', 'model': 'gpt-6.1-sol', 'promptFile': 'prompt.md', 'artifact': 'report.md', 'eventKind': 'launch', 'lane': 'implementation', 'effort': 'high'}, {'schemaVersion': 2, 'runId': 'own-terminal-row', 'workItem': 'synthetic-own-launch', 'role': 'qa-engineer', 'executionRole': 'internal', 'status': 'completed', 'gate': 'PASS', 'scope': ['own-launch-a', 'own-launch-b'], 'startedAt': '2026-09-08T00:00:00Z', 'updatedAt': '2026-09-08T00:00:01Z', 'assignedRole': 'qa-engineer', 'provider': 'codex', 'model': 'gpt-6.1-sol', 'promptFile': 'prompt.md', 'artifact': 'report.md', 'eventKind': 'terminal', 'launchRunId': 'own-launch-row', 'closesRunIds': ['own-target-revise'], 'lane': 'implementation', 'effort': 'high', 'evidence': [{'kind': 'review', 'ref': 'report.md'}]}]
_OWN_LAUNCH_PAIR_CASES = [['EXACT-PAIR-POSITIVE-TARGET-MODEL-DISTINCT', [], [], [True, True, True]], ['ONE-FIELD-workItem', [['own-launch-row', {'workItem': 'different-producer-item'}, []]], [], [True, True, True]], ['ONE-FIELD-role', [['own-launch-row', {'role': 'backend-engineer'}, []]], [], [True, True, True]], ['ONE-FIELD-executionRole', [['own-launch-row', {'executionRole': 'main'}, []]], [], [True, True, True]], ['ONE-FIELD-assignedRole', [['own-launch-row', {'assignedRole': 'backend-engineer'}, []]], [], [True, True, True]], ['ONE-FIELD-provider', [['own-launch-row', {'provider': 'claude'}, []]], [], [True, True, True]], ['ONE-FIELD-model', [['own-launch-row', {'model': 'synthetic-other-model'}, []]], [], [True, True, True]], ['ONE-FIELD-scope', [['own-launch-row', {'scope': ['own-launch-b', 'own-launch-a']}, []]], [], [True, True, True]], ['ONE-FIELD-promptFile', [['own-launch-row', {'promptFile': 'prompt-other.md'}, []]], [], [True, True, True]], ['ONE-FIELD-effort', [['own-launch-row', {'effort': 'medium'}, []]], [], [True, True, True]], ['ONE-FIELD-launchFlags', [['own-terminal-row', {'launchFlags': ['--model', 'gpt-6.1-sol', '-c', 'model_reasoning_effort="high"']}, []]], [], [True, True, True]], ['FIRST-NONE-TERMINAL-THEN-EXACT-PASS-DUPLICATE', [], [[2, {'schemaVersion': 2, 'runId': 'own-first-terminal', 'workItem': 'synthetic-own-launch', 'role': 'qa-engineer', 'executionRole': 'internal', 'status': 'completed', 'gate': 'none', 'scope': ['own-launch-a', 'own-launch-b'], 'startedAt': '2026-09-08T00:00:00Z', 'updatedAt': '2026-09-08T00:00:01Z', 'assignedRole': 'qa-engineer', 'provider': 'codex', 'model': 'gpt-6.1-sol', 'promptFile': 'prompt.md', 'eventKind': 'terminal', 'launchRunId': 'own-launch-row', 'lane': 'implementation', 'effort': 'high'}]], [True, True, True, True]], ['GENUINE-REVISE-IDENTITY-UNDER-PAIR-MISMATCH', [['own-launch-row', {'scope': ['own-launch-b', 'own-launch-a']}, []], ['own-terminal-row', {'status': 'revise', 'gate': 'REVISE'}, ['closesRunIds']]], [], [True, True, True]], ['OPTIONAL-BOTH-ABSENT-POSITIVE', [['own-launch-row', {}, ['assignedRole', 'model', 'promptFile']], ['own-terminal-row', {}, ['assignedRole', 'model', 'promptFile']]], [], [True, True, True]], ['OPTIONAL-ABSENCE-VS-PRESENT-EMPTY', [['own-launch-row', {}, ['model']], ['own-terminal-row', {'model': ''}, []]], [], [True, True, True]], ['REQUIRED-SCOPE-MISSING-LAUNCH', [['own-launch-row', {}, ['scope']]], [], [True, False, True]], ['REQUIRED-SCOPE-MISSING-TERMINAL', [['own-terminal-row', {}, ['scope']]], [], [True, True, False]], ['REQUIRED-SCOPE-MISSING-BOTH', [['own-launch-row', {}, ['scope']], ['own-terminal-row', {}, ['scope']]], [], [True, False, False]], ['EXACT-TYPE-LIST-VS-SCALAR-GUARD', [['own-terminal-row', {'scope': 'own-launch-a'}, []]], [], [True, True, False]], ['EXACT-TYPE-NONSTRING-PROVIDER-GUARD', [['own-terminal-row', {'provider': True}, []]], [], [True, True, False]]]
_OWN_LAUNCH_NATIVE_PROOF_ROWS = [{'schemaVersion': 2, 'runId': 'proof-target-revise', 'workItem': 'synthetic-own-launch', 'role': 'qa-engineer', 'executionRole': 'internal', 'status': 'revise', 'gate': 'REVISE', 'scope': ['own-launch-a', 'own-launch-b'], 'startedAt': '2026-09-08T00:00:00Z', 'updatedAt': '2026-09-08T00:00:01Z', 'assignedRole': 'qa-engineer', 'provider': 'codex', 'model': 'gpt-6.1-sol', 'promptFile': 'prompt.md', 'artifact': 'report.md', 'eventKind': 'standalone', 'lane': 'implementation', 'effort': 'high', 'findingClass': 'other'}, {'schemaVersion': 2, 'runId': 'proof-native-launch', 'workItem': 'synthetic-own-launch', 'role': 'external-reviewer', 'executionRole': 'external-reviewer', 'status': 'running', 'gate': 'none', 'scope': ['own-launch-a', 'own-launch-b'], 'startedAt': '2026-09-08T00:00:00Z', 'updatedAt': '2026-09-08T00:00:01Z', 'assignedRole': 'qa-engineer', 'provider': 'codex', 'model': 'gpt-6.1-sol', 'promptFile': 'prompt.md', 'artifact': 'report.md', 'eventKind': 'launch', 'lane': 'implementation', 'effort': 'high'}, {'schemaVersion': 2, 'runId': 'proof-native-evidence', 'workItem': 'synthetic-own-launch', 'role': 'external-reviewer', 'executionRole': 'external-reviewer', 'status': 'completed', 'gate': 'PASS', 'scope': ['own-launch-a', 'own-launch-b'], 'startedAt': '2026-09-08T00:00:00Z', 'updatedAt': '2026-09-08T00:00:01Z', 'assignedRole': 'qa-engineer', 'provider': 'codex', 'model': 'gpt-6.1-sol', 'promptFile': 'prompt.md', 'artifact': 'report.md', 'eventKind': 'terminal', 'launchRunId': 'proof-native-launch', 'lane': 'implementation', 'effort': 'high', 'terminalClass': 'external-nonauthorizing', 'actualExecutionPath': 'direct-external-cli', 'artifactIdentity': 'sha256:80276c35b68ea29d66bbf0909f70bf96d833e11710e20d722c038106d2e90f1b', 'authorizing': False, 'closesRunIds': [], 'evidence': [{'kind': 'review', 'ref': 'report.md'}]}, {'schemaVersion': 2, 'runId': 'proof-final-internal-closer', 'workItem': 'synthetic-own-launch', 'role': 'architecture-reviewer', 'executionRole': 'internal', 'status': 'completed', 'gate': 'PASS', 'scope': ['own-launch-a', 'own-launch-b'], 'startedAt': '2026-09-08T00:00:00Z', 'updatedAt': '2026-09-08T00:00:01Z', 'assignedRole': 'architecture-reviewer', 'provider': 'codex', 'model': 'gpt-6.1-sol', 'promptFile': 'prompt.md', 'artifact': 'report.md', 'eventKind': 'standalone', 'closesRunIds': ['proof-target-revise'], 'lane': 'implementation', 'effort': 'high', 'terminalClass': 'internal-authorizing', 'actualExecutionPath': 'internal', 'artifactIdentity': 'sha256:80276c35b68ea29d66bbf0909f70bf96d833e11710e20d722c038106d2e90f1b', 'externalEvidenceRunId': 'proof-native-evidence', 'closerRunId': 'proof-final-internal-closer', 'authorizing': True, 'targetTuple': {'workItem': 'synthetic-own-launch', 'assignedInternalRole': 'qa-engineer', 'artifactIdentity': 'sha256:80276c35b68ea29d66bbf0909f70bf96d833e11710e20d722c038106d2e90f1b'}, 'evidence': [{'kind': 'review', 'ref': 'report.md'}]}]
_OWN_LAUNCH_NATIVE_FIRST = {'schemaVersion': 2, 'runId': 'proof-native-first-none', 'workItem': 'synthetic-own-launch', 'role': 'external-reviewer', 'executionRole': 'external-reviewer', 'status': 'completed', 'gate': 'none', 'scope': ['own-launch-a', 'own-launch-b'], 'startedAt': '2026-09-08T00:00:00Z', 'updatedAt': '2026-09-08T00:00:01Z', 'assignedRole': 'qa-engineer', 'provider': 'codex', 'model': 'gpt-6.1-sol', 'promptFile': 'prompt.md', 'eventKind': 'terminal', 'launchRunId': 'proof-native-launch', 'lane': 'implementation', 'effort': 'high', 'terminalClass': 'external-nonauthorizing', 'actualExecutionPath': 'direct-external-cli', 'artifactIdentity': 'sha256:80276c35b68ea29d66bbf0909f70bf96d833e11710e20d722c038106d2e90f1b', 'authorizing': False, 'closesRunIds': []}


@pytest.mark.parametrize("case_name,edits,inserts,individual", _OWN_LAUNCH_PAIR_CASES,
                         ids=[case[0] for case in _OWN_LAUNCH_PAIR_CASES])
def test_current_own_launch_complete_qualification(tmp_path, case_name, edits, inserts, individual):
    module = load_validator()
    item = tmp_path / "work-items/active/synthetic-own-launch"
    item.mkdir(parents=True)
    (item / "report.md").write_bytes(b"Synthetic owned QA evidence; no provider execution.\n")
    (item / "prompt.md").write_bytes(b"Synthetic prompt locator only.\n")
    (item / "prompt-other.md").write_bytes(b"Another owned synthetic locator.\n")
    events = copy.deepcopy(_OWN_LAUNCH_PAIR_ROWS)
    by_id = {value["runId"]: value for value in events}
    for run_id, changed, removed in edits:
        by_id[run_id].update(changed)
        for key in removed:
            by_id[run_id].pop(key)
    for position, value in inserts:
        events.insert(position, copy.deepcopy(value))
    raw = ledger_bytes(events)
    ledger = item / "agent-runs.jsonl"
    ledger.write_bytes(raw)
    accepted = [module.validate_event(dict(value), item, set(), []) for value in events]
    assert accepted == individual
    context = module.load_effective_ledger_view(tmp_path, item,
        "work-items/active/synthetic-own-launch/agent-runs.jsonl")
    errors = []
    validity = module.derive_event_validity(context.rows, item, errors, context=context)
    reduction_errors = []
    reduction = module._reduce_effective_current_state(context.rows, item, reduction_errors, None, context=context)
    closure_errors = []
    revises, launches = module.validate_closure(context.rows, closure_errors, validity=validity, context=context)
    assert [row["runId"] for row in revises] == [row["runId"] for row in reduction[2]]
    assert [row["runId"] for row in launches] == [row["runId"] for row in reduction[3]]
    assert [entry.current_schema_valid for entry in validity] == individual
    terminal = next(entry for row, entry in zip(context.rows, validity) if row.event["runId"] == "own-terminal-row")
    open_r = {row["runId"] for row in reduction[2]}
    open_l = {row["runId"] for row in reduction[3]}
    if case_name in {"EXACT-PAIR-POSITIVE-TARGET-MODEL-DISTINCT", "OPTIONAL-BOTH-ABSENT-POSITIVE"}:
        assert errors == reduction_errors == closure_errors == []
        assert not open_r and not open_l
        assert terminal.authority.terminal_eligible and terminal.authority.closer_eligible
        assert terminal.authority.artifact_evidence_eligible
        if case_name == "EXACT-PAIR-POSITIVE-TARGET-MODEL-DISTINCT":
            neutral = module._runtime_rows_from_events(events)
            for supplied in ([True] * len(neutral), validity):
                refused = []
                assert module.validate_closure(neutral, refused, validity=supplied) == ([], [])
                assert any("WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS" in error for error in refused)
                refused = []
                assert module.resolve_closure_invalidations(neutral, supplied, refused) == set()
                assert any("WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS" in error for error in refused)
    else:
        assert not terminal.authority.terminal_eligible
        assert not terminal.authority.closer_eligible and not terminal.authority.artifact_evidence_eligible
        assert "own-target-revise" in open_r
        if case_name == "FIRST-NONE-TERMINAL-THEN-EXACT-PASS-DUPLICATE":
            settlements = [row.event["runId"] for row, entry in zip(context.rows, validity)
                           if entry.authority.terminal_eligible]
            assert settlements == ["own-first-terminal"] and not open_l
            assert any("duplicate terminal for launch" in error for error in reduction_errors)
        elif accepted[1]:
            assert "own-launch-row" in open_l
        if case_name == "GENUINE-REVISE-IDENTITY-UNDER-PAIR-MISMATCH":
            assert terminal.authority.revise_target_eligible and "own-terminal-row" in open_r
        if case_name.startswith("ONE-FIELD-"):
            field = case_name[len("ONE-FIELD-"):]
            assert any("WI-LEDGER-LAUNCH-BINDING" in error and field in error for error in reduction_errors)
    assert ledger.read_bytes() == raw


@pytest.mark.parametrize("mismatch", [False, True], ids=["independent-withholding", "actual-pair-failure"])
def test_native_recovery_uses_relation_observations_not_restricted_closer(tmp_path, mismatch):
    module = load_validator()
    item = tmp_path / "work-items/active/synthetic-own-launch"
    item.mkdir(parents=True)
    (item / "report.md").write_bytes(b"Synthetic owned QA evidence; no provider execution.\n")
    (item / "prompt.md").write_bytes(b"Synthetic prompt locator only.\n")
    rows = copy.deepcopy(_OWN_LAUNCH_PAIR_ROWS)
    if mismatch:
        rows[1]["scope"].reverse()
    body_digest = digest(canonical(rows[2]))
    rows.append({"schemaVersion": 2, "runId": "recover-own-terminal", "workItem": item.name,
        "role": "lead", "executionRole": "main", "status": "completed", "gate": "none",
        "scope": ["ledger-recovery:closure-invalidation"], "eventKind": "closure-invalidation",
        "invalidatesRunId": rows[2]["runId"], "invalidatesEventSha256": body_digest,
        "evidence": [{"kind": "manual-check", "ref": f"{rows[2]['runId']} {body_digest}"}],
        "startedAt": "2026-10-05T00:00:00Z", "updatedAt": "2026-10-05T00:00:00Z"})
    raw = ledger_bytes(rows)
    (item / "agent-runs.jsonl").write_bytes(raw)
    context = module.load_effective_ledger_view(tmp_path, item,
        "work-items/active/synthetic-own-launch/agent-runs.jsonl")
    validity = module.derive_event_validity(context.rows, item, [], context=context)
    assert validity[2].current_schema_valid and not validity[2].authority.closer_eligible
    errors, pending = [], []
    inactive = module.resolve_closure_invalidations(context.rows, validity, errors, context=context,
        pending_closing_effects_out=pending)
    if mismatch:
        assert inactive == {2} and pending == []
        assert not any("target-per-event-invalid" in error for error in errors)
    else:
        assert inactive == set() and len(pending) == 1
        assert any("target-authoritative" in error for error in errors)
        assert not any("WI-LEDGER-LAUNCH-BINDING" in error for error in errors)
    assert (item / "agent-runs.jsonl").read_bytes() == raw


@pytest.mark.parametrize("mismatch", [False, True], ids=["exact-snapshot-proof", "wrong-own-launch"])
def test_history_snapshot_proof_uses_complete_current_qualification(tmp_path, mismatch):
    from tests.test_mixed_current_ledger_recovery import (
        _history_fixture, _history_cli, _history_disposition_request,
    )

    module = load_validator()
    item = tmp_path / "work-items/active/snapshot-own-launch"
    _original, admission = _history_fixture(item, orphan_closer=True)
    applied = _history_cli(item, admission)
    assert applied.returncode == 0, applied.stdout + applied.stderr
    request = _history_disposition_request(item, admission, kind="current-evidence-covered")
    values = [json.loads(line) for line in (item / "agent-runs.jsonl").read_bytes().splitlines()]
    proof_id = request["targets"][0]["classificationRunId"]
    position = next(i for i, value in enumerate(values) if value.get("runId") == proof_id)
    terminal = values[position]
    launch = {**terminal, "runId": "snapshot-proof-own-launch", "eventKind": "launch",
              "status": "running", "gate": "none"}
    for key in ("artifact", "artifactRevision", "evidence", "closesRunIds"):
        launch.pop(key, None)
    terminal["eventKind"] = "terminal"
    terminal["launchRunId"] = launch["runId"]
    if mismatch:
        launch["scope"] = ["a different actual commission"]
    values.insert(position, launch)
    raw = ledger_bytes(values)
    (item / "agent-runs.jsonl").write_bytes(raw)
    request["expectedLedgerSha256"] = digest(raw)
    preview = _history_cli(item, request, apply=False)
    if mismatch:
        assert preview.returncode != 0, preview.stdout + preview.stderr
        assert "proof record lacks complete current launch authority" in preview.stdout + preview.stderr
        assert (item / "agent-runs.jsonl").read_bytes() == raw
        states = []
        module.validate_work_item(item, strict_revise=False, validate_status_file=False, obligation_state_out=states)
        assert states[0].unresolved_history
    else:
        assert preview.returncode == 0, preview.stdout + preview.stderr
        settled = _history_cli(item, request)
        assert settled.returncode == 0, settled.stdout + settled.stderr
        states = []
        assert module.validate_work_item(item, validate_status_file=False, obligation_state_out=states) == []
        assert states[0].unresolved_history == ()
        # Mutable report replacement keeps the proof's actual snapshot profile.
        (item / terminal["artifact"]).write_bytes(b"replaced mutable report\n")
        assert module.validate_work_item(item, validate_status_file=False) == []


@pytest.mark.parametrize("mutation", ["exact", "scope", "duplicate"])
def test_native_typed_proof_uses_complete_own_launch(tmp_path, mutation):
    module = load_validator()
    item = tmp_path / "work-items/active/synthetic-own-launch"
    item.mkdir(parents=True)
    (item / "report.md").write_bytes(b"Synthetic owned QA evidence; no provider execution.\n")
    (item / "prompt.md").write_bytes(b"Synthetic prompt locator only.\n")
    events = copy.deepcopy(_OWN_LAUNCH_NATIVE_PROOF_ROWS)
    if mutation == "scope":
        events[1]["scope"].reverse()
    elif mutation == "duplicate":
        events.insert(2, copy.deepcopy(_OWN_LAUNCH_NATIVE_FIRST))
    raw = ledger_bytes(events)
    (item / "agent-runs.jsonl").write_bytes(raw)
    assert all(module.validate_event(dict(value), item, set(), []) for value in events)
    context = module.load_effective_ledger_view(tmp_path, item,
        "work-items/active/synthetic-own-launch/agent-runs.jsonl")
    errors = []
    reduction = module._reduce_effective_current_state(context.rows, item, errors, None, context=context)
    evidence = next(entry for row, entry in zip(reduction.context.rows, reduction[1])
                    if row.event["runId"] == "proof-native-evidence")
    if mutation == "exact":
        assert errors == [] and not reduction[2] and not reduction[3]
        assert evidence.authority.terminal_eligible and evidence.authority.artifact_evidence_eligible
    else:
        assert "proof-target-revise" in {value["runId"] for value in reduction[2]}
        assert not evidence.authority.terminal_eligible and not evidence.authority.artifact_evidence_eligible
    assert (item / "agent-runs.jsonl").read_bytes() == raw


@pytest.mark.parametrize("mode", ["matching", "fresh-wrong-closing", "fresh-wrong-no-closes",
    "fresh-wrong-role-assigned-closing", "fresh-wrong-role-assigned-no-closes",
    "acquired-observation", "observation-and-malformed", "observation-and-status"])
def test_public_append_preserves_exact_matching_current_qualification(tmp_path, mode):
    from tests.test_mixed_current_ledger_recovery import minimal_staged_status, load_writer

    module = load_validator()
    item = tmp_path / "work-items/active/synthetic-own-launch"
    item.mkdir(parents=True)
    (item / "report.md").write_bytes(b"Synthetic owned QA evidence; no provider execution.\n")
    (item / "prompt.md").write_bytes(b"Synthetic prompt locator only.\n")
    (item / "status.md").write_text(minimal_staged_status(), encoding="utf-8")
    rows = copy.deepcopy(_OWN_LAUNCH_PAIR_ROWS)
    wrong_profession = mode.startswith("fresh-wrong-role-assigned")
    if wrong_profession:
        # Original290 failing witness: ordinary V2 review, not a typed resolution packet.
        rows[1].update(role="backend-engineer", assignedRole="backend-engineer")
    elif mode != "matching":
        rows[1]["scope"].reverse()
    if mode.startswith("fresh-wrong") or mode == "matching":
        previous, requested = rows[:2], rows[2]
        if mode.endswith("no-closes"):
            requested.pop("closesRunIds")
    else:
        rows[2].update(gate="REVISE", status="revise", findingClass="other")
        rows[2].pop("closesRunIds")
        previous = rows
        requested = {**rows[0], "runId": "unrelated-progress-record", "eventKind": "standalone",
                     "gate": "PASS", "status": "completed", "evidence": copy.deepcopy(rows[2]["evidence"])}
        requested.pop("findingClass")
        if mode == "observation-and-malformed":
            requested["scope"] = "not-an-array"
        if mode == "observation-and-status":
            (item / "status.md").write_text("# Missing required status sections\n", encoding="utf-8")
    if wrong_profession or mode == "matching":
        previous.append({**rows[0], "runId": "unrelated-genuine-revise", "scope": ["unrelated requirement"]})
    ledger = item / "agent-runs.jsonl"
    before = ledger_bytes(previous)
    ledger.write_bytes(before)
    if wrong_profession or mode == "matching":
        before_states = []
        module.validate_work_item(item, strict_revise=False, validate_status_file=False,
            obligation_state_out=before_states)
        assert {value.run_id for value in before_states[0].open_revise} == {
            rows[0]["runId"], "unrelated-genuine-revise"}
        assert {value.run_id for value in before_states[0].open_launches} == {rows[1]["runId"]}
        candidate_states, candidate_axes = [], []
        candidate_errors = module.validate_work_item(item, strict_revise=False, validate_status_file=False,
            selected_ledger_bytes=before + ledger_bytes([requested]),
            obligation_state_out=candidate_states, authority_state_out=candidate_axes)
        terminal_axes = candidate_axes[0][len(previous) + 1]
        assert terminal_axes.terminal_eligible == (not wrong_profession)
        assert terminal_axes.closer_eligible == (not wrong_profession and "closesRunIds" in requested)
        assert terminal_axes.artifact_evidence_eligible == (not wrong_profession)
        assert {value.run_id for value in candidate_states[0].open_revise} == (
            {rows[0]["runId"], "unrelated-genuine-revise"} if wrong_profession else {"unrelated-genuine-revise"})
        assert {value.run_id for value in candidate_states[0].open_launches} == (
            {rows[1]["runId"]} if wrong_profession else set())
        assert any("WI-LEDGER-LAUNCH-BINDING" in value for value in candidate_errors) == wrong_profession
        assert ledger.read_bytes() == before
    options = {"runId": "--run-id", "workItem": "--work-item-name", "role": "--role",
        "executionRole": "--execution-role", "status": "--status", "gate": "--gate",
        "startedAt": "--started-at", "updatedAt": "--updated-at", "assignedRole": "--assigned-role",
        "provider": "--provider", "model": "--model", "promptFile": "--prompt-file", "artifact": "--artifact",
        "eventKind": "--event-kind", "launchRunId": "--launch-run-id", "lane": "--lane", "effort": "--effort"}
    argv = [sys.executable, "-B", str(SCRIPT.with_name("agent-run-ledger.py")), "--work-item", str(item), "append"]
    for key, value in requested.items():
        if key in options:
            argv.extend([options[key], str(value)])
        elif key in {"scope", "closesRunIds", "evidence"}:
            option = {"scope": "--scope", "closesRunIds": "--closes", "evidence": "--evidence-json"}[key]
            for member in (value if isinstance(value, list) else [value]):
                argv.extend([option, json.dumps(member) if key == "evidence" else member])
    if mode == "observation-and-malformed":
        writer = load_writer()
        with pytest.raises(ValueError, match="scope"):
            writer._append_event_transaction(item, writer.load_validator(), lambda _previous: requested)
        assert ledger.read_bytes() == before
        assert not (item / "agent-runs.jsonl.tmp").exists()
        assert not (item / "agent-runs.jsonl.lock").exists()
        return
    accepted = subprocess.run(argv, capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    output = accepted.stdout + accepted.stderr
    if mode in {"matching", "acquired-observation"}:
        assert accepted.returncode == 0, output
        assert ledger.read_bytes().startswith(before)
        assert len(ledger.read_bytes().splitlines()) == len(previous) + 1
        if mode == "matching":
            matching_states = []
            assert module.validate_work_item(item, strict_revise=False, validate_status_file=False,
                obligation_state_out=matching_states) == []
            assert {value.run_id for value in matching_states[0].open_revise} == {"unrelated-genuine-revise"}
            assert not matching_states[0].open_launches
        else:
            assert output.count("OBSERVATION: WI-LEDGER-LAUNCH-BINDING") == 1, output
            states, axes = [], []
            diagnostics = module.validate_work_item(item, strict_revise=False, validate_status_file=False,
                obligation_state_out=states, authority_state_out=axes)
            assert sum("WI-LEDGER-LAUNCH-BINDING" in value for value in diagnostics) == 1
            assert not axes[0][3].terminal_eligible and not axes[0][3].closer_eligible
            assert not axes[0][3].artifact_evidence_eligible
            assert {value.run_id for value in states[0].open_revise} == {rows[0]["runId"], rows[2]["runId"]}
            assert {value.run_id for value in states[0].open_launches} == {rows[1]["runId"]}
            strict = module.validate_work_item(item, validate_status_file=False)
            assert any("open REVISE obligation" in value for value in strict)
            assert any("unsettled launch" in value for value in strict)
    else:
        assert accepted.returncode != 0, output
        assert ledger.read_bytes() == before
        if mode.startswith("fresh-wrong"):
            assert "WI-LEDGER-LAUNCH-BINDING" in output
        elif mode == "observation-and-status":
            assert "status" in output.lower()
        else:
            assert "scope" in output
        if wrong_profession:
            after_states = []
            module.validate_work_item(item, strict_revise=False, validate_status_file=False,
                obligation_state_out=after_states)
            assert {value.run_id for value in after_states[0].open_revise} == {
                rows[0]["runId"], "unrelated-genuine-revise"}
            assert {value.run_id for value in after_states[0].open_launches} == {rows[1]["runId"]}
    assert not (item / "agent-runs.jsonl.tmp").exists()
    assert not (item / "agent-runs.jsonl.lock").exists()


def _assert_joined_h1_cold_reader(root: Path, mode: str):
    module = load_validator()
    specimen = "42ad-retained-invalid" if mode == "different-wire" else "F-untyped-contradiction"
    artifacts, wires, manifest, _h1, oracle = _frozen_h1_inputs_current6a(module, root, specimen)
    before = {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    paths = tuple(wires)
    items = {path: root.joinpath(*path.split("/")[:-1]) for path in paths}
    if mode == "different-wire":
        observed = {}
        def observe_actual_codec(frame, event, value):
            if (event == "return" and frame.f_code.co_filename == str(SCRIPT)
                    and frame.f_code.co_name == "_ledger_h1_view_wire" and isinstance(value, tuple)):
                observed[value[0]["ledgerPath"]] = canonical(value[0])
        previous = sys.getprofile()
        sys.setprofile(observe_actual_codec)
        try:
            default = module.load_effective_ledger_view(root, items[paths[0]], paths[0], compatibility_artifacts=artifacts)
        finally:
            sys.setprofile(previous)
        assert default.view is None and observed
        assert domain_digest("orchestrarium:ledger-h1:projected-view:v1", json.loads(observed[paths[0]])) != manifest["entries"][0]["projectedViewSha256"]
    if mode == "negative":
        cases = [(label, candidate, {}) for label, candidate in _frozen_h1_distinct_wire_cases(wires)]
        cases.extend([("map-not-mapping", [], {}), ("wire-not-bytes", {**wires, paths[0]: "not bytes"}, {})])
        malformed = json.loads(wires[paths[0]])
        malformed["rows"][0]["authority"]["launchEligible"] = 1
        cases.append(("mask-not-boolean", {**wires, paths[0]: canonical(malformed)}, {}))
        changed_manifest = json.loads(artifacts.ledger_manifest_bytes)
        changed_manifest["entries"][0]["projectedViewSha256"] = "0" * 64
        cases.append(("manifest-commitment", wires, {"ledger_manifest_bytes": canonical(changed_manifest)}))
        receipt_path = next(iter(artifacts.receipt_bytes_by_path))
        changed_receipt = json.loads(artifacts.receipt_bytes_by_path[receipt_path])
        assert "ledgerManifestSha256" in changed_receipt
        changed_receipt["ledgerManifestSha256"] = "0" * 64
        cases.append(("receipt-commitment", wires, {"receipt_bytes_by_path": {receipt_path: canonical(changed_receipt)}}))
        ledger = artifacts.ledger_bytes_by_path[paths[0]]
        assert b"target-review" in ledger
        cases.append(("member-ledger-drift", wires, {"ledger_bytes_by_path": {
            **artifacts.ledger_bytes_by_path, paths[0]: ledger.replace(b"target-review", b"target-reviex", 1)}}))
        assert len(cases) == 15
        for label, candidate, changes in cases:
            selected = replace(artifacts, historical_wire_bytes_by_path=candidate, **changes)
            contexts = {path: module.load_effective_ledger_view(root, items[path], path, compatibility_artifacts=selected)
                        for path in paths}
            errors, axes = [], []
            for path in paths:
                errors.extend(module.validate_work_item(items[path], compatibility_artifacts=selected,
                    validate_status_file=False, authority_state_out=axes))
            _assert_frozen_h1_group_refusal(contexts, errors, axes)
            assert all(not isinstance(context.invocation_token, module._LedgerInvocationTokenV1)
                       for context in contexts.values()), label
    else:
        supplied = replace(artifacts, historical_wire_bytes_by_path=wires)
        contexts = {path: module.load_effective_ledger_view(root, items[path], path, compatibility_artifacts=supplied)
                    for path in paths}
        _assert_frozen_h1_group_observation(contexts, wires, manifest, oracle)
        if mode == "current-split":
            axes, states = [], []
            errors = module.validate_work_item(items[paths[0]], compatibility_artifacts=supplied,
                validate_status_file=False, authority_state_out=axes, obligation_state_out=states)
            _assert_frozen_h1_current_split(errors, axes, states)
            item, raw = _frozen_h1_matching_current_fixture(root / "matching")
            axes, states = [], []
            errors = module.validate_work_item(item, validate_status_file=False,
                authority_state_out=axes, obligation_state_out=states)
            _assert_frozen_h1_matching_current(errors, axes, states)
            assert (item / "agent-runs.jsonl").read_bytes() == raw
    assert {relative: (root / relative).read_bytes() for relative in before} == before
    print("JOINED_H1_COLD_OK", mode)


@pytest.mark.parametrize("mode", ["current-split", "different-wire", "negative"])
def test_supplied_original_h1_wire_current_split(tmp_path, mode):
    child = ("import importlib.util,pathlib,sys;"
             "p=pathlib.Path(sys.argv[1]);"
             "s=importlib.util.spec_from_file_location('joined_h1_cold_fixture',p);"
             "m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);"
             "m._assert_joined_h1_cold_reader(pathlib.Path(sys.argv[2]),sys.argv[3])")
    result = subprocess.run([sys.executable, "-B", "-c", child, str(Path(__file__)), str(tmp_path), mode],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert result.returncode == 0, result.stdout + result.stderr
    assert "JOINED_H1_COLD_OK " + mode in result.stdout


@pytest.mark.parametrize("failure", ["missing-result", "foreign-module-result", "wrong-item-result", "incomplete-acquisition",
    "native-selection", "semantic-selection", "missing-native", "provisional-result"])
def test_append_operation_requires_complete_bound_result(tmp_path, failure):
    from tests.test_mixed_current_ledger_recovery import minimal_staged_status, load_writer

    writer = load_writer()
    validator = writer.load_validator()
    item = tmp_path / "work-items/active/synthetic-own-launch"
    item.mkdir(parents=True)
    (item / "status.md").write_text(minimal_staged_status(), encoding="utf-8")
    (item / "report.md").write_bytes(b"Synthetic owned QA evidence; no provider execution.\n")
    (item / "prompt.md").write_bytes(b"Synthetic prompt locator only.\n")
    rows = copy.deepcopy(_OWN_LAUNCH_PAIR_ROWS)
    before = ledger_bytes(rows)
    ledger = item / "agent-runs.jsonl"
    ledger.write_bytes(before)
    requested = {**rows[0], "runId": "new-operation-record", "eventKind": "standalone",
                 "status": "completed", "gate": "none"}
    requested.pop("findingClass")
    foreign = None
    if failure in {"foreign-module-result", "wrong-item-result"}:
        other = tmp_path / "work-items/active/another-operation-item"
        other.mkdir(parents=True)
        (other / "report.md").write_bytes((item / "report.md").read_bytes())
        (other / "prompt.md").write_bytes((item / "prompt.md").read_bytes())
        (other / "status.md").write_text(minimal_staged_status(), encoding="utf-8")
        other_rows = [{**value, "workItem": other.name} for value in rows]
        (other / "agent-runs.jsonl").write_bytes(ledger_bytes(other_rows))
        source = load_validator() if failure == "foreign-module-result" else validator
        states = []
        assert source.validate_work_item(other, strict_revise=False, obligation_state_out=states) == []
        foreign = states[0]._current_result
    actual = validator.validate_work_item
    def degraded(*args, **kwargs):
        diagnostics = actual(*args, **kwargs)
        if failure == "missing-result":
            kwargs["obligation_state_out"].clear()
        elif failure == "incomplete-acquisition":
            kwargs["ledger_acquisition_complete_out"][:] = [False]
        elif failure in {"native-selection", "semantic-selection", "missing-native", "provisional-result"}:
            result = kwargs["obligation_state_out"][0]._current_result
            owner = validator._context_evaluation(result.context)
            native, semantic = owner.selected_input.rows[-1], owner.base_rows[-1]
            assert native.event is not semantic.event and native.event["scope"] is not semantic.event["scope"]
            if failure == "native-selection":
                native.event["scope"].append("changed native selection")
                assert "changed native selection" not in semantic.event["scope"]
            elif failure == "semantic-selection":
                semantic.event["scope"].append("changed semantic selection")
                assert "changed semantic selection" not in native.event["scope"]
            elif failure == "missing-native":
                owner.selected_input = replace(owner.selected_input, rows=())
            else:
                owner.result = None
        else:
            kwargs["obligation_state_out"][0] = replace(kwargs["obligation_state_out"][0], _current_result=foreign)
        return diagnostics
    with mock.patch.object(validator, "validate_work_item", side_effect=degraded):
        with pytest.raises(ValueError, match="WI-LEDGER-(?:OPERATION|CUSTODY)"):
            writer._append_event_transaction(item, validator, lambda _previous: requested)
    assert ledger.read_bytes() == before
    assert not (item / "agent-runs.jsonl.tmp").exists()
    assert not (item / "agent-runs.jsonl.lock").exists()


def test_append_operation_binds_every_actual_suffix_row(tmp_path):
    from tests.test_mixed_current_ledger_recovery import minimal_staged_status, load_writer

    writer = load_writer()
    validator = writer.load_validator()
    item = tmp_path / "work-items/active/synthetic-own-launch"
    item.mkdir(parents=True)
    (item / "status.md").write_text(minimal_staged_status(), encoding="utf-8")
    (item / "report.md").write_bytes(b"Synthetic owned QA evidence; no provider execution.\n")
    (item / "prompt.md").write_bytes(b"Synthetic prompt locator only.\n")
    rows = copy.deepcopy(_OWN_LAUNCH_PAIR_ROWS)
    before = ledger_bytes(rows)
    requested = [{**rows[0], "runId": f"suffix-operation-{i}", "eventKind": "standalone",
                  "gate": "none", "status": "completed"} for i in (1, 2)]
    for value in requested:
        value.pop("findingClass")
    candidate = before + b"".join((writer.serialize_event(value) + "\n").encode("utf-8") for value in requested)
    path = item / "agent-runs.jsonl.tmp"
    path.write_bytes(candidate)
    states, acquired = [], []
    diagnostics = validator.validate_work_item(item, ledger_path=path, strict_revise=False,
        obligation_state_out=states, ledger_acquisition_complete_out=acquired)
    assert diagnostics == []
    with pytest.raises(ValueError, match="exhaust the exact candidate suffix"):
        writer._receive_append_operation(item, validator, states, acquired, diagnostics,
                                         before, candidate, (requested[0],))
    result, positions = writer._receive_append_operation(item, validator, states, acquired, diagnostics,
                                                         before, candidate, tuple(requested))
    assert len(positions) == 2 and all(result[1][position].current_schema_valid for position in positions)
    assert path.read_bytes() == candidate


@pytest.mark.parametrize("relation", ["genuine", "known-wrong", "known-invalid", "later", "ambiguous"])
def test_admitted_preimage_keeps_raw_truth_and_requires_actual_admission(tmp_path, relation):
    from tests.test_mixed_current_ledger_recovery import _history_fixture, _history_cli

    module = load_validator()
    item = tmp_path / "work-items/active/admitted-current-basis"
    original, request = _history_fixture(item, orphan_closer=True,
        review_launch_effort=None if relation == "known-wrong" else "high")
    values = [json.loads(line) for line in original.splitlines()]
    target = values[6]
    if relation == "known-wrong":
        target["launchRunId"] = values[1]["runId"]
        assert "effort" not in values[1] and target["effort"] == "high"
    elif relation == "known-invalid":
        target["launchRunId"] = values[3]["runId"]
    elif relation in {"later", "ambiguous"}:
        launch = {**target, "runId": target["launchRunId"], "eventKind": "launch",
                  "status": "running", "gate": "none"}
        for key in ("launchRunId", "closesRunIds", "artifact", "artifactRevision", "evidence"):
            launch.pop(key, None)
        values.append(launch)
        if relation == "ambiguous":
            values.append({**launch, "runId": launch["runId"].upper()})
    if relation != "genuine":
        original = ledger_bytes(values)
        (item / "agent-runs.jsonl").write_bytes(original)
        request["expectedLedgerSha256"] = digest(original)
        for selected in request["targets"]:
            selected.update(sourcePrefixSha256=digest(original), sourcePrefixBytes=len(original),
                            physicalLineSha256=digest(ledger_bytes([values[selected["rawLineOrdinal"] - 1]])))
    raw_states, raw_axes = [], []
    module.validate_work_item(item, strict_revise=False, validate_status_file=False,
        obligation_state_out=raw_states, authority_state_out=raw_axes)
    if relation == "known-wrong":
        assert raw_axes[0][2].launch_eligible is True
    assert not raw_axes[0][7].terminal_eligible
    assert not raw_axes[0][7].closer_eligible
    assert not raw_axes[0][7].artifact_evidence_eligible
    raw_owner = module._context_evaluation(raw_states[0]._current_result.context)
    with pytest.raises(ValueError, match="WI-LEDGER-HISTORY-BINDING"):
        raw_owner.admission_preimage(original)
    applied = _history_cli(item, request)
    if applied.returncode:
        assert relation != "genuine", applied.stdout + applied.stderr
        assert (item / "agent-runs.jsonl").read_bytes() == original
        return
    # The CLI's JSON result remains parseable even when full observations exist.
    assert json.loads(applied.stdout)["applied"] is True
    states, axes = [], []
    module.validate_work_item(item, strict_revise=False, validate_status_file=False,
        obligation_state_out=states, authority_state_out=axes)
    owner = module._context_evaluation(states[0]._current_result.context)
    before = owner.admission_preimage(original)
    assert len(before) == len(values)
    assert all(entry.authority == axes[0][ordinal]
               for ordinal, entry in enumerate(before, 1))
    assert before[6].authority.terminal_eligible is False
    assert before[6].authority.closer_eligible is (relation == "genuine")
    assert before[6].authority.artifact_evidence_eligible is (relation == "genuine")
    with pytest.raises(ValueError, match="WI-LEDGER-HISTORY-BINDING"):
        owner.admission_preimage(original + b"\n")
    with pytest.raises(ValueError, match="WI-LEDGER-HISTORY-BINDING"):
        raw_owner.admission_preimage(original)


@pytest.mark.parametrize(("terminal_status", "operation"), [
    ("completed", "append"), ("cancelled", "append"),
    ("completed", "settle-launch"), ("cancelled", "settle-launch"),
])
def test_native_sealed_mismatch_custody_preserves_real_obligations(tmp_path, monkeypatch, terminal_status, operation):
    from tests.test_ledger_h1_activation_writer import load_module, h1_manifest, WRITER_SCRIPT
    from tests.test_mixed_current_ledger_recovery import load_writer, minimal_staged_status
    module = load_validator()
    original_event = event
    def mismatched_event(run_id, work_item, **values):
        value = original_event(run_id, work_item, **values)
        if run_id == "revise-a-0001":
            value.update(eventKind="terminal", launchRunId="launch-c-0001", scope=["other.md"])
        return value
    def actual_historical_view(path, prefix, events, _masks, **_kwargs):
        errors = []
        item = tmp_path.joinpath(*path.split("/")).parent
        rows = module._ledger_h1_runtime_rows(path, prefix, len(events), item, errors)
        assert errors == []
        wire, _revises, _launches = module._ledger_h1_view_wire({
            "ledgerPath": path, "prefixLineCount": len(events),
            "prefixByteLength": len(prefix), "prefixSha256": digest(prefix)}, rows)
        return wire, wire["reduction"]
    with monkeypatch.context() as local:
        local.setattr(sys.modules[__name__], "event", mismatched_event)
        local.setattr(sys.modules[__name__], "authority_view", actual_historical_view)
        artifacts, items, paths, _expected = synthetic_artifacts(module, tmp_path,
            sealed_closer_is_terminal=True)
    for path, raw in artifacts.ledger_bytes_by_path.items():
        tmp_path.joinpath(*path.split("/")).write_bytes(raw)
    lifecycle = load_module(WRITER_SCRIPT, "native_sealed_custody_owner")
    activation = lifecycle.SealedPrefixActivationRequestV1(
        h1_manifest_path=artifacts.h1_manifest_path, h1_manifest_bytes=h1_manifest(tmp_path),
        ledger_manifest_path=artifacts.ledger_manifest_path,
        ledger_manifest_bytes=artifacts.ledger_manifest_bytes,
        expected_registry_sha256=digest(b""), recorded_at="2026-09-08T01:00:00Z")
    receipt = lifecycle.apply_sealed_prefix_activation(tmp_path, activation)
    assert receipt["state"] == "apply" and receipt["replay"] is False
    item = items[0]
    (item / "status.md").write_text(minimal_staged_status(), encoding="utf-8")
    path = item / "agent-runs.jsonl"
    raw = path.read_bytes()
    def observe():
        states, acquired = [], []
        errors = module.validate_work_item(item, strict_revise=False, validate_status_file=False,
            obligation_state_out=states, ledger_acquisition_complete_out=acquired)
        assert acquired == [True] and len(states) == 1
        return errors, states[0]._current_result
    before_errors, before = observe()
    target = next(valid for row, valid in zip(before.context.rows, before[1])
                  if row.event["runId"] == "revise-a-0001")
    assert target.current_schema_valid
    axes = lambda a: (a.launch_eligible, a.terminal_eligible, a.revise_target_eligible,
                      a.closer_eligible, a.artifact_evidence_eligible)
    assert axes(target.authority) == (False, False, True, False, False)
    assert [e["runId"] for e in before[2]] == ["revise-a-0001"]
    assert [e["runId"] for e in before[3]] == ["launch-c-0001"]
    assert before.context.history_custody == ()
    wire = before.context.view
    request = {"schemaVersion": 2, "workItem": "work-items/active/reader-a",
        "expectedLedgerSha256": digest(raw), "operationId": "claim4-sealed-noncloser",
        "recordedAt": "2026-10-04T12:00:00Z", "targets": [{
            "action": "custody-invalid-history", "rawLineOrdinal": 4,
            "sourcePrefixSha256": digest(raw), "sourcePrefixBytes": len(raw),
            "physicalLineSha256": digest(raw.splitlines(keepends=True)[3])}]}
    preview = lifecycle.recover_mixed_current_ledger(tmp_path, canonical(request), apply_admitted=False)
    assert preview["applied"] is False and path.read_bytes() == raw
    applied = lifecycle.recover_mixed_current_ledger(tmp_path, canonical(request), apply_admitted=True)
    assert applied["applied"] is True and path.read_bytes().startswith(raw)
    after_errors, after = observe()
    assert before_errors == ["WI-LEDGER-LAUNCH-BINDING: revise-a-0001: own launch launch-c-0001 differs in scope"]
    assert before_errors[0] in after_errors
    assert after.context.view == wire
    assert len(after.context.history_custody) == 1
    hold = after.context.history_custody[0]
    assert hold.raw_line_ordinal == 4 and hold.raw_line_sha256 == request["targets"][0]["physicalLineSha256"]
    assert hold.disposition_run_id is None and axes(hold.authority_before) == axes(target.authority)
    target_after = next(valid for row, valid in zip(after.context.rows, after[1])
                        if row.event["runId"] == "revise-a-0001")
    assert axes(target_after.authority) == axes(target.authority)
    assert [e["runId"] for e in after[2]] == ["revise-a-0001"]
    assert [e["runId"] for e in after[3]] == ["launch-c-0001"]
    assert after.context.unresolved_history
    writer = load_writer()
    operation_args = (["append", "--event-kind", "terminal", "--role", "analyst",
        "--execution-role", "internal", "--scope", "synthetic reader fixture"]
        if operation == "append" else ["settle-launch"])
    assert writer.main(["--work-item", str(item), *operation_args,
        "--launch-run-id", "launch-c-0001", "--run-id", "truthful-neutral-result",
        "--status", terminal_status, "--gate", "none",
        "--evidence", "manual-check:actual synthetic neutral execution result",
        "--notes", "Truthful neutral result does not resolve an independent finding or historical hold.",
        "--started-at", "2026-10-04T12:00:00Z", "--updated-at", "2026-10-04T12:00:01Z"]) == 0
    _errors, neutral = observe()
    assert not neutral[3] and [e["runId"] for e in neutral[2]] == ["revise-a-0001"]
    assert neutral.context.view == wire
    neutral_target = next(valid for row, valid in zip(neutral.context.rows, neutral[1])
                          if row.event["runId"] == "revise-a-0001")
    assert neutral_target.current_schema_valid and axes(neutral_target.authority) == axes(target.authority)
    assert neutral.context.unresolved_history and len(neutral.context.history_custody) == 1
    assert axes(neutral.context.history_custody[0].authority_before) == axes(target.authority)
    assert neutral.context.history_custody[0].disposition_run_id is None
    assert path.read_bytes().startswith(raw)
