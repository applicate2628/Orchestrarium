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
    assert errors == []
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
        assert baseline_errors == [] and len(baseline) == len(local_context.rows)
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
            assert errors == []
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

    def observe(path):
        seen.append(ntpath.normcase(ntpath.abspath(path)))
        return real(path)

    with mock.patch.object(ntpath, "_getfinalpathname", observe):
        (items[0] / "target.md").resolve()  # positive calibration of real backend
        assert seen
        positive = module.validate_work_item(
            items[0], validate_status_file=False, strict_revise=False,
            compatibility_artifacts=artifacts,
        )
        assert positive == []
        bad = event("outside-selected-report", items[0].name, eventKind="standalone",
                    gate="PASS", artifact="../../../../outside/report.md",
                    evidence=[{"kind": "manual-check", "ref": "owned rejection fixture"}])
        selected = dict(artifacts.ledger_bytes_by_path)
        selected[paths[0]] += ledger_bytes([bad])
        candidate = replace(artifacts, ledger_bytes_by_path=selected)
        seen.clear()
        errors = module.validate_work_item(
            items[0], validate_status_file=False, compatibility_artifacts=candidate
        )
    assert any("escape" in value.lower() for value in errors)
    prefixes = [ntpath.normcase(str(path.parent)) + ntpath.sep for path in outside]
    assert not [path for path in seen if any(path.startswith(prefix) for prefix in prefixes)]

    # The allowed alias owner must reject its outside target before querying it.
    alias = items[0] / "outside-alias.md"
    alias.symlink_to(outside[0])
    seen.clear()
    alias_errors = []
    with mock.patch.object(ntpath, "_getfinalpathname", observe):
        assert module.resolve_work_item_path(items[0], alias.name, "artifact", "outside-alias", alias_errors) is None
    assert any("escape" in value.lower() for value in alias_errors)
    assert not [path for path in seen if any(path.startswith(prefix) for prefix in prefixes)]
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
        assert enabled == [*disabled, "status.md cannot be closed while ledger has running agents"]
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
