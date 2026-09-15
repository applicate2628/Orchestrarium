import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WRITER_SCRIPT = ROOT / "scripts" / "mutate-work-item.py"
READER_FIXTURE_SCRIPT = ROOT / "tests" / "test_ledger_h1_effective_view.py"
POLICY = "2026-08-28-ledger-h1-compatibility-boundary"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def active_status(task: str) -> bytes:
    return (
        "---\n"
        "template: quick-fix\n"
        "status: active\n"
        "started: 2026-09-10T00:00:00Z\n"
        "updated: 2026-09-10T00:00:00Z\n"
        "---\n\n"
        f"- **Task**: {task}\n"
        "- **Current step**: Exercise H1 relocation.\n"
        "- **Last result**: H1 activation is complete.\n"
        "- **Next action**: Run the lifecycle oracle.\n"
    ).encode("utf-8")


def tree_state(root: Path):
    files = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and ".scratch" not in path.relative_to(root).parts
    }
    directories = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_dir() and ".scratch" not in path.relative_to(root).parts
    }
    return files, directories


def h1_manifest(root: Path) -> bytes:
    decisions = root / "work-items" / "decisions"
    decisions.mkdir(parents=True, exist_ok=True)
    legacy_slug = "2026-01-01-synthetic-legacy"
    legacy = (
        "# Synthetic legacy decision\n\n"
        f"- id: {legacy_slug}\n"
        "- status: accepted\n"
        "- owner: architecture-reviewer\n\n"
        "Synthetic legacy body.\n"
    ).encode("utf-8")
    (decisions / f"{legacy_slug}.md").write_bytes(legacy)
    entries = [
        {
            "path": f"{legacy_slug}.md",
            "sha256": digest(legacy).upper(),
            "state": "admitted",
        }
    ]
    baseline = hashlib.sha256(
        entries[0]["path"].encode("utf-8")
        + b"\0"
        + entries[0]["sha256"].encode("ascii")
        + b"\n"
    ).hexdigest().upper()
    policy = (
        f"- id: {POLICY}\n"
        "- status: accepted\n"
        "- date: 2026-08-28\n"
        "- decided-by: architect\n"
        "- context: synthetic-writer\n"
        "- supersedes: none\n"
        "- superseded-by: none\n"
        "- h1-manifest: work-items/decision-h1-compatibility.json\n"
        f"- h1-baseline-sha256: {baseline}\n"
        "- h1-cutover-date: 2026-08-28\n\n"
        "# Decision: Synthetic writer policy\n\n"
        "Synthetic policy body.\n"
    ).encode("utf-8")
    (decisions / f"{POLICY}.md").write_bytes(policy)
    return canonical(
        {
            "schemaVersion": 1,
            "policyDecision": POLICY,
            "cutoverDate": "2026-08-28",
            "baselineSha256": baseline,
            "entries": entries,
        }
    ) + b"\n"


def fixture(root: Path):
    reader_fixture = load_module(
        READER_FIXTURE_SCRIPT,
        f"ledger_h1_reader_fixture_{id(root)}",
    )
    reader = reader_fixture.load_validator()
    reader_artifacts, items, paths, _expected = reader_fixture.synthetic_artifacts(
        reader,
        root,
    )
    for relative, raw in reader_artifacts.ledger_bytes_by_path.items():
        target = root.joinpath(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    manifest = json.loads(reader_artifacts.ledger_manifest_bytes)
    h1_bytes = h1_manifest(root)
    writer = load_module(WRITER_SCRIPT, f"ledger_h1_writer_{id(root)}")
    request = writer.SealedPrefixActivationRequestV1(
        h1_manifest_path="work-items/decision-h1-compatibility.json",
        h1_manifest_bytes=h1_bytes,
        ledger_manifest_path=(
            "work-items/legacy-ledger-projection-manifests/"
            f"{manifest['manifestId']}.json"
        ),
        ledger_manifest_bytes=reader_artifacts.ledger_manifest_bytes,
        expected_registry_sha256=digest(b""),
        recorded_at="2026-09-08T01:00:00Z",
    )
    return writer, reader, request, items, paths


def ordinary_legacy_projection(
    root: Path,
    item: Path,
    ledger_bytes: bytes,
    raw_line: bytes,
    projected_event: dict,
    *,
    raw_line_ordinal: int,
    suffix: str,
) -> tuple[bytes, bytes]:
    manifest_id = f"ordinary-{suffix}"
    entry_id = f"ordinary-entry-{suffix}"
    relative_item = item.relative_to(root).as_posix()
    relative_ledger = (item / "agent-runs.jsonl").relative_to(root).as_posix()
    manifest = {
        "schemaVersion": 1,
        "manifestId": manifest_id,
        "profiles": [{"profileId": "canonical-v0-shape", "profileVersion": 1}],
        "entries": [
            {
                "entryId": entry_id,
                "profileId": "canonical-v0-shape",
                "profileVersion": 1,
                "workItem": relative_item,
                "ledgerPath": relative_ledger,
                "ledgerSha256": digest(ledger_bytes),
                "rawLineOrdinals": [raw_line_ordinal],
                "rawLineSha256": [digest(raw_line)],
                "projectedEvents": [projected_event],
                "projectedEventSha256": [digest(canonical(projected_event))],
            }
        ],
    }
    manifest_bytes = canonical(manifest)
    record = {
        "schemaVersion": 1,
        "operationId": f"ordinary-projection-{suffix}",
        "state": "apply",
        "profileId": "canonical-v0-shape",
        "profileVersion": 1,
        "manifestId": manifest_id,
        "manifestSha256": digest(manifest_bytes),
        "manifestEntryId": entry_id,
        "workItem": relative_item,
        "ledgerPath": relative_ledger,
        "ledgerSha256": digest(ledger_bytes),
        "rawLineOrdinal": raw_line_ordinal,
        "rawLineSha256": digest(raw_line),
        "projectedEvent": projected_event,
        "projectedEventSha256": digest(canonical(projected_event)),
        "recordedAt": f"2026-09-10T02:0{raw_line_ordinal}:00Z",
    }
    return manifest_bytes, canonical(record) + b"\n"


def legacy_ordinary_event(item: Path, suffix: str) -> tuple[dict, dict]:
    raw = {
        "runId": f"ordinary-legacy-{suffix}",
        "workItem": item.name,
        "role": "analysis",
        "executionRole": "lead",
        "status": "completed",
        "gate": "none",
        "scope": f"legacy ordinary {suffix}",
        "evidence": f"legacy ordinary evidence {suffix}",
        "started": f"2026-09-10T02:0{suffix}:00Z",
        "updated": f"2026-09-10T02:0{suffix}:01Z",
    }
    projected = {
        "schemaVersion": 2,
        "runId": raw["runId"],
        "workItem": item.name,
        "role": "analyst",
        "executionRole": "main",
        "status": "completed",
        "gate": "none",
        "scope": [raw["scope"]],
        "evidence": [{"kind": "manual-check", "ref": raw["evidence"]}],
        "startedAt": raw["started"],
        "updatedAt": raw["updated"],
    }
    return raw, projected


def test_apply_dry_run_receipt_last_and_exact_replay(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    writer, reader, request, _items, paths = fixture(root)
    before = tree_state(root)

    plan = writer.preflight_sealed_prefix_activation(root, request)
    dry_run = writer.apply_sealed_prefix_activation(root, request, dry_run=True)

    assert plan.state == "apply"
    assert plan.replay is False
    assert len(plan.member_operation_ids) == 2
    assert dry_run["readiness"] == "READY"
    assert dry_run["dryRun"] is True
    assert dry_run["replay"] is False
    assert dry_run["byteInventory"]
    assert tree_state(root) == before

    ledgers_before = {
        path: root.joinpath(*path.split("/")).read_bytes() for path in paths
    }
    applied = writer.apply_sealed_prefix_activation(root, request)

    assert applied["state"] == "apply"
    assert applied["dryRun"] is False
    assert applied["replay"] is False
    assert applied["receiptSha256"] == digest(plan.receipt_bytes)
    assert root.joinpath(*plan.ledger_manifest_path.split("/")).read_bytes() == request.ledger_manifest_bytes
    assert root.joinpath(*plan.h1_manifest_path.split("/")).read_bytes() == request.h1_manifest_bytes
    assert root.joinpath(*plan.receipt_path.split("/")).read_bytes() == plan.receipt_bytes
    assert {
        path: root.joinpath(*path.split("/")).read_bytes() for path in paths
    } == ledgers_before
    contexts = reader._load_effective_ledger_group(root)
    assert set(contexts) == set(paths)
    assert all(row.observation.activation_state == "active" for row in contexts.values())
    assert len({id(row.invocation_token) for row in contexts.values()}) == 1

    after = tree_state(root)
    replay = writer.apply_sealed_prefix_activation(root, request)
    assert replay["replay"] is True
    assert replay["byteInventory"] == {}
    assert tree_state(root) == after


def archive_first_activated_h1_member(root: Path):
    writer, reader, request, items, paths = fixture(root)
    for index, item in enumerate(items, start=1):
        (item / "status.md").write_bytes(active_status(f"Relocate H1 member {index}."))
    writer.apply_sealed_prefix_activation(root, request)

    source = items[0]
    terminal_instant = "2026-09-10T01:00:00Z"
    operation_id = "h1-relocation-member-a"
    successor_slug = "reader-a-successor"
    (source / "bug-dispositions.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "workItem": source.name,
                "closedAt": terminal_instant,
                "bugs": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    writer.refresh_readme(root, allow_marker_bootstrap=True)
    obligation_states = []
    source_errors = reader.validate_work_item(
        source,
        strict_revise=False,
        obligation_state_out=obligation_states,
    )
    assert source_errors == []
    assert len(obligation_states) == 1
    assert obligation_states[0].open_launches == ()
    transfer = {
        "schemaVersion": 1,
        "sourceWorkItem": source.name,
        "successorWorkItem": successor_slug,
        "expectedSourceLedgerSha256": digest((source / "agent-runs.jsonl").read_bytes()),
        "obligations": [
            {
                "runId": row.run_id,
                "rawLineOrdinal": row.raw_line_ordinal,
                "rawLineSha256": row.raw_line_sha256,
                "rawEventSha256": row.raw_event_sha256,
                "projectedEventSha256": row.projected_event_sha256,
            }
            for row in obligation_states[0].open_revise
        ],
    }
    closure = (
        f"Closed: {terminal_instant}\n"
        "Outcome: Transferred the H1 participant obligation.\n"
        "Evidence: focused two-member relocation test\n"
        "Residual risk: None in fixture.\n"
    ).encode("utf-8")
    successor = (
        "Task: Continue the H1 participant obligation.\n"
        f"Continues: {source.name}\n"
        f"Obligation-transfer: {operation_id}\n"
        "Next action: Resolve the inherited review finding.\n"
        f"updated: {terminal_instant}\n"
    ).encode("utf-8")

    receipt = writer.archive_with_successor(
        root,
        source.name,
        closure,
        terminal_instant,
        successor_slug,
        successor,
        operation_id,
        transfer["expectedSourceLedgerSha256"],
        digest((root / "work-items" / "README.md").read_bytes()),
        obligation_transfer_data=json.dumps(transfer, sort_keys=True).encode("utf-8"),
    )
    return writer, reader, items, paths, receipt


def test_archive_one_activated_h1_member_keeps_remaining_member_valid(
    tmp_path: Path,
) -> None:
    root = tmp_path / "relocation"
    _writer, reader, items, paths, receipt = archive_first_activated_h1_member(root)

    contexts = reader._load_effective_ledger_group(root)
    remaining_errors = reader.validate_work_item(items[1], strict_revise=False)
    assert set(contexts) == set(paths)
    archive = root.joinpath(*receipt["archivePath"].split("/"))
    archived_context = reader.load_effective_ledger_view(
        root,
        archive,
        f"{receipt['archivePath']}/agent-runs.jsonl",
    )
    assert archived_context.selected_ledger_path == paths[0]
    assert archived_context.view == contexts[paths[0]].view
    assert not any(
        "WI-LEDGER-COMPAT-ACTIVATION-INCOMPLETE" in error
        for error in remaining_errors
    )
    candidate = items[1] / "agent-runs.jsonl.tmp"
    candidate.write_bytes(
        (items[1] / "agent-runs.jsonl").read_bytes()
        + canonical(
            {
                "schemaVersion": 2,
                "runId": "reader-b-candidate-suffix",
                "workItem": items[1].name,
                "role": "analyst",
                "executionRole": "internal",
                "status": "completed",
                "gate": "none",
                "scope": ["H1 relocation candidate suffix"],
                "startedAt": "2026-09-10T01:01:00Z",
                "updatedAt": "2026-09-10T01:01:01Z",
            }
        )
        + b"\n"
    )
    candidate_errors = reader.validate_work_item(
        items[1], ledger_path=candidate, strict_revise=False
    )
    assert candidate_errors == remaining_errors
    candidate.write_bytes((items[1] / "agent-runs.jsonl").read_bytes() + b"{}\n")
    malformed_errors = reader.validate_work_item(
        items[1], ledger_path=candidate, strict_revise=False
    )
    assert malformed_errors
    assert not any(
        "WI-LEDGER-COMPAT-ACTIVATION-INCOMPLETE" in error
        for error in malformed_errors
    )


def test_unselected_ordinary_ledger_routes_beside_activated_h1_group(
    tmp_path: Path,
) -> None:
    root = tmp_path / "ordinary-beside-h1"
    writer, reader, request, items, paths = fixture(root)
    applied = writer.apply_sealed_prefix_activation(root, request)

    ordinary = root / "work-items" / "active" / "ordinary-reader"
    ordinary.mkdir(parents=True)
    ordinary_ledger = ordinary / "agent-runs.jsonl"
    ordinary_event = {
        "schemaVersion": 2,
        "runId": "ordinary-reader-live",
        "workItem": ordinary.name,
        "role": "analyst",
        "executionRole": "internal",
        "status": "completed",
        "gate": "none",
        "scope": ["ordinary ledger beside H1"],
        "startedAt": "2026-09-10T02:00:00Z",
        "updatedAt": "2026-09-10T02:00:01Z",
    }
    ordinary_ledger.write_bytes(canonical(ordinary_event) + b"\n")
    h1_bytes_before = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and ordinary not in path.parents
    }

    ordinary_relative = ordinary_ledger.relative_to(root).as_posix()
    context = reader.load_effective_ledger_view(
        root,
        ordinary,
        ordinary_relative,
    )
    assert context.observation.activation_state == "inactive", context.observation
    assert context.view is None
    assert len(context.rows) == 1
    assert not any(
        "WI-LEDGER-COMPAT-" in diagnostic
        for diagnostic in context.observation.diagnostics
    )

    live_errors = reader.validate_work_item(
        ordinary,
        strict_revise=False,
        validate_status_file=False,
    )
    assert live_errors == []
    ordinary_live_before = ordinary_ledger.read_bytes()
    ordinary_ledger.write_bytes(ordinary_live_before + b"{}\n")
    live_malformed_errors = reader.validate_work_item(
        ordinary,
        strict_revise=False,
        validate_status_file=False,
    )
    assert any(
        "runId" in error or "schemaVersion" in error
        for error in live_malformed_errors
    )
    assert not any(
        "WI-LEDGER-COMPAT-" in error for error in live_malformed_errors
    )
    ordinary_ledger.write_bytes(ordinary_live_before)

    candidate = ordinary / "agent-runs.jsonl.tmp"
    candidate_event = {
        **ordinary_event,
        "runId": "ordinary-reader-candidate",
        "startedAt": "2026-09-10T02:01:00Z",
        "updatedAt": "2026-09-10T02:01:01Z",
    }
    candidate.write_bytes(
        ordinary_ledger.read_bytes() + canonical(candidate_event) + b"\n"
    )
    candidate_errors = reader.validate_work_item(
        ordinary,
        ledger_path=candidate,
        strict_revise=False,
        validate_status_file=False,
    )
    assert candidate_errors == []

    manifests = root / "work-items" / "legacy-ledger-projection-manifests"
    malformed_manifest = manifests / "malformed-sibling.json"
    malformed_manifest.write_bytes(b"{}\n")
    sibling_manifest_errors = reader.validate_work_item(
        ordinary,
        ledger_path=candidate,
        strict_revise=False,
        validate_status_file=False,
    )
    assert any(
        "WI-LEDGER-MIGRATION-MANIFEST-INVALID" in error
        and "malformed-sibling.json" in error
        for error in sibling_manifest_errors
    )
    malformed_manifest.unlink()

    registry = root / "work-items" / "legacy-ledger-projections.jsonl"
    registry_before = registry.read_bytes()
    registry.write_bytes(registry_before + b"{}\n")
    sibling_registry_errors = reader.validate_work_item(
        ordinary,
        ledger_path=candidate,
        strict_revise=False,
        validate_status_file=False,
    )
    assert any(
        "WI-LEDGER-MIGRATION-MANIFEST-INVALID" in error
        and "projection registry line" in error
        for error in sibling_registry_errors
    )
    registry.write_bytes(registry_before)

    candidate.write_bytes(ordinary_ledger.read_bytes() + b"{}\n")
    malformed_errors = reader.validate_work_item(
        ordinary,
        ledger_path=candidate,
        strict_revise=False,
        validate_status_file=False,
    )
    assert malformed_errors
    assert any("runId" in error or "schemaVersion" in error for error in malformed_errors)
    assert not any("WI-LEDGER-COMPAT-" in error for error in malformed_errors)

    cross_match = reader.load_effective_ledger_view(
        root,
        ordinary,
        paths[0],
    )
    assert cross_match.observation.failure_ids == (
        "WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS",
    )
    assert {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and ordinary not in path.parents
    } == h1_bytes_before
    assert set(reader._load_effective_ledger_group(root)) == set(paths)
    assert items[0].joinpath("agent-runs.jsonl").is_file()
    assert items[1].joinpath("agent-runs.jsonl").is_file()

    contexts = reader._load_effective_ledger_group(root)
    token = next(iter(contexts.values())).invocation_token
    partition = token.h1_projection_partition
    for mutant in (
        ("unsafe/manifest.json", *partition[1:]),
        (partition[0], "0" * 64, *partition[2:]),
        (*partition[:3], "0" * 64, partition[4]),
        (*partition[:4], ((partition[4][0][0], "0" * 64), *partition[4][1:])),
        (*partition[:4], partition[4][:-1]),
        (*partition[:4], (*partition[4], partition[4][0])),
    ):
        _events, _counters, partition_errors = (
            reader.project_manifest_bound_legacy_ledger_projections(
                [ordinary_event],
                [{"line": 1}],
                ordinary,
                ordinary_ledger,
                ordinary_ledger.read_bytes(),
                validated_h1_partition=mutant,
            )
        )
        assert any("WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS" in error for error in partition_errors)
    _events, _counters, caller_errors = (
        reader.project_manifest_bound_legacy_ledger_projections(
            [ordinary_event],
            [{"line": 1}],
            ordinary,
            ordinary_ledger,
            ordinary_ledger.read_bytes(),
            manifest_blobs={},
            registry_bytes=b"",
            validated_h1_partition=partition,
        )
    )
    assert any("WI-LEDGER-COMPAT-EFFECTIVE-VIEW-BYPASS" in error for error in caller_errors)

    apply_receipt = root.joinpath(*applied["receiptPath"].split("/"))
    revoke_request = writer.SealedPrefixRevokeRequestV1(
        apply_receipt_path=applied["receiptPath"],
        apply_receipt_sha256=digest(apply_receipt.read_bytes()),
        expected_registry_sha256=digest(registry.read_bytes()),
        recorded_at="2026-09-10T03:00:00Z",
    )
    writer.revoke_sealed_prefix_activation(root, revoke_request)
    revoked_h1_before = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and ordinary not in path.parents
    }
    candidate.write_bytes(
        ordinary_ledger.read_bytes() + canonical(candidate_event) + b"\n"
    )
    revoked_errors = reader.validate_work_item(
        ordinary,
        ledger_path=candidate,
        strict_revise=False,
        validate_status_file=False,
    )
    assert revoked_errors == []
    revoked_live_errors = reader.validate_work_item(
        ordinary,
        strict_revise=False,
        validate_status_file=False,
    )
    assert revoked_live_errors == []
    ordinary_ledger.write_bytes(ordinary_live_before + b"{}\n")
    revoked_live_malformed_errors = reader.validate_work_item(
        ordinary,
        strict_revise=False,
        validate_status_file=False,
    )
    assert any(
        "runId" in error or "schemaVersion" in error
        for error in revoked_live_malformed_errors
    )
    assert not any(
        "WI-LEDGER-COMPAT-" in error
        for error in revoked_live_malformed_errors
    )
    ordinary_ledger.write_bytes(ordinary_live_before)
    assert {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and ordinary not in path.parents
    } == revoked_h1_before


def test_unselected_live_ordinary_preserves_mixed_legacy_registry_order(
    tmp_path: Path,
) -> None:
    root = tmp_path / "mixed-ordinary-beside-h1"
    writer, reader, request, _items, _paths = fixture(root)
    ordinary = root / "work-items" / "active" / "mixed-ordinary-reader"
    ordinary.mkdir(parents=True)
    ordinary_ledger = ordinary / "agent-runs.jsonl"
    raw_before, projected_before = legacy_ordinary_event(ordinary, "1")
    raw_after, projected_after = legacy_ordinary_event(ordinary, "3")
    ordinary_event = {
        "schemaVersion": 2,
        "runId": "ordinary-current-middle",
        "workItem": ordinary.name,
        "role": "analyst",
        "executionRole": "internal",
        "status": "completed",
        "gate": "none",
        "scope": ["ordinary current middle"],
        "startedAt": "2026-09-10T02:02:00Z",
        "updatedAt": "2026-09-10T02:02:01Z",
    }
    raw_before_line = canonical(raw_before) + b"\n"
    current_line = canonical(ordinary_event) + b"\n"
    raw_after_line = canonical(raw_after) + b"\n"
    ledger_bytes = raw_before_line + current_line + raw_after_line
    ordinary_ledger.write_bytes(ledger_bytes)

    before_manifest, before_record = ordinary_legacy_projection(
        root,
        ordinary,
        ledger_bytes,
        raw_before_line,
        projected_before,
        raw_line_ordinal=1,
        suffix="before",
    )
    manifests = root / "work-items" / "legacy-ledger-projection-manifests"
    manifests.mkdir(parents=True, exist_ok=True)
    (manifests / "ordinary-before.json").write_bytes(before_manifest)
    registry = root / "work-items" / "legacy-ledger-projections.jsonl"
    registry.write_bytes(before_record)
    request = replace(
        request,
        expected_registry_sha256=digest(before_record),
    )
    applied = writer.apply_sealed_prefix_activation(root, request)

    after_manifest, after_record = ordinary_legacy_projection(
        root,
        ordinary,
        ledger_bytes,
        raw_after_line,
        projected_after,
        raw_line_ordinal=3,
        suffix="after",
    )
    (manifests / "ordinary-after.json").write_bytes(after_manifest)
    with registry.open("ab") as stream:
        stream.write(after_record)

    active_h1_before = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and ordinary not in path.parents
    }
    contexts = reader._load_effective_ledger_group(root)
    assert all(
        context.observation.activation_state == "active"
        for context in contexts.values()
    )
    active_partition = next(iter(contexts.values())).invocation_token.h1_projection_partition
    assert tuple(ordinal for ordinal, _sha256 in active_partition[4]) == (2, 3)
    registry_lines = registry.read_bytes().splitlines(keepends=True)
    assert json.loads(registry_lines[0])["operationId"] == "ordinary-projection-before"
    assert json.loads(registry_lines[3])["operationId"] == "ordinary-projection-after"

    metadata: list[dict[str, object]] = []
    parse_errors: list[str] = []
    events = reader.load_jsonl(
        ordinary_ledger,
        parse_errors,
        metadata,
        ledger_bytes,
    )
    assert parse_errors == []
    projected, counters, projection_errors = (
        reader.project_manifest_bound_legacy_ledger_projections(
            events,
            metadata,
            ordinary,
            ordinary_ledger,
            ledger_bytes,
            validated_h1_partition=active_partition,
        )
    )
    assert projection_errors == []
    assert counters["manifest-apply"] == 2
    assert counters["manifest-projected"] == 2
    assert [event["runId"] for event in projected] == [
        projected_before["runId"],
        ordinary_event["runId"],
        projected_after["runId"],
    ]
    assert reader.validate_work_item(
        ordinary,
        strict_revise=False,
        validate_status_file=False,
    ) == []
    ordinary_ledger.write_bytes(ledger_bytes + b"{}\n")
    active_malformed = reader.validate_work_item(
        ordinary,
        strict_revise=False,
        validate_status_file=False,
    )
    assert any(
        "runId" in error or "schemaVersion" in error for error in active_malformed
    )
    assert not any("WI-LEDGER-COMPAT-" in error for error in active_malformed)
    ordinary_ledger.write_bytes(ledger_bytes)
    assert {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and ordinary not in path.parents
    } == active_h1_before

    apply_receipt = root.joinpath(*applied["receiptPath"].split("/"))
    writer.revoke_sealed_prefix_activation(
        root,
        writer.SealedPrefixRevokeRequestV1(
            apply_receipt_path=applied["receiptPath"],
            apply_receipt_sha256=digest(apply_receipt.read_bytes()),
            expected_registry_sha256=digest(registry.read_bytes()),
            recorded_at="2026-09-10T03:00:00Z",
        ),
    )
    revoked_h1_before = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and ordinary not in path.parents
    }
    revoked_contexts = reader._load_effective_ledger_group(root)
    assert all(
        context.observation.activation_state == "revoked"
        for context in revoked_contexts.values()
    )
    revoked_partition = next(
        iter(revoked_contexts.values())
    ).invocation_token.h1_projection_partition
    assert tuple(ordinal for ordinal, _sha256 in revoked_partition[4]) == (
        2,
        3,
        5,
        6,
    )
    revoked_projected, revoked_counters, revoked_projection_errors = (
        reader.project_manifest_bound_legacy_ledger_projections(
            events,
            metadata,
            ordinary,
            ordinary_ledger,
            ledger_bytes,
            validated_h1_partition=revoked_partition,
        )
    )
    assert revoked_projection_errors == []
    assert revoked_counters["manifest-apply"] == 2
    assert [event["runId"] for event in revoked_projected] == [
        event["runId"] for event in projected
    ]
    assert reader.validate_work_item(
        ordinary,
        strict_revise=False,
        validate_status_file=False,
    ) == []
    ordinary_ledger.write_bytes(ledger_bytes + b"{}\n")
    revoked_malformed = reader.validate_work_item(
        ordinary,
        strict_revise=False,
        validate_status_file=False,
    )
    assert any(
        "runId" in error or "schemaVersion" in error for error in revoked_malformed
    )
    assert not any("WI-LEDGER-COMPAT-" in error for error in revoked_malformed)
    ordinary_ledger.write_bytes(ledger_bytes)
    assert {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and ordinary not in path.parents
    } == revoked_h1_before


def test_h1_reader_preserves_typed_relocation_corruption_and_duplicate_diagnostics(
    tmp_path: Path,
) -> None:
    root = tmp_path / "typed-relocation-failures"
    _writer, reader, items, paths, receipt = archive_first_activated_h1_member(root)
    archive = root.joinpath(*receipt["archivePath"].split("/"))
    archived_ledger = archive / "agent-runs.jsonl"
    archived_ledger_before = archived_ledger.read_bytes()
    archived_ledger.write_bytes(archived_ledger_before + b"{}\n")

    corruption_errors = reader.validate_work_item(items[1], strict_revise=False)

    assert any(
        "WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH" in error
        and paths[0] in error
        for error in corruption_errors
    )
    assert not any(
        "WI-LEDGER-COMPAT-ACTIVATION-INCOMPLETE" in error
        for error in corruption_errors
    )
    failed_group = reader._load_effective_ledger_group(root)
    assert set(failed_group) == {paths[0]}
    assert failed_group[paths[0]].view is None
    assert failed_group[paths[0]].observation.failure_ids == (
        "WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH",
    )
    candidate = items[1] / "agent-runs.jsonl.tmp"
    candidate.write_bytes((items[1] / "agent-runs.jsonl").read_bytes())
    candidate_errors = reader.validate_work_item(
        items[1], ledger_path=candidate, strict_revise=False
    )
    assert any(
        "WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH" in error
        and paths[0] in error
        for error in candidate_errors
    )
    assert not any(
        "WI-LEDGER-COMPAT-ACTIVATION-INCOMPLETE" in error
        for error in candidate_errors
    )
    archived_ledger.write_bytes(archived_ledger_before)
    duplicate = root.joinpath(*paths[0].split("/")).parent
    duplicate.mkdir(parents=True)
    (duplicate / "agent-runs.jsonl").write_bytes(archived_ledger_before)

    duplicate_errors = reader.validate_work_item(items[1], strict_revise=False)

    assert any(
        "WI-CATEGORY-DUAL-LOCATION" in error and paths[0] in error
        for error in duplicate_errors
    )
    assert not any(
        "WI-LEDGER-COMPAT-ACTIVATION-INCOMPLETE" in error
        for error in duplicate_errors
    )


def test_h1_reader_reports_set_topology_for_missing_h1_artifacts(
    tmp_path: Path,
) -> None:
    root = tmp_path / "missing-h1-artifacts"
    item = root / "work-items" / "active" / "reader-a"
    item.mkdir(parents=True)
    (item / "agent-runs.jsonl").write_bytes(b"{}\n")
    h1 = root / "work-items" / "decision-h1-compatibility.json"
    h1.write_bytes(b"{}\n")
    logical_ledger_path = "work-items/active/reader-a/agent-runs.jsonl"

    reader_fixture = load_module(
        READER_FIXTURE_SCRIPT,
        f"missing_h1_reader_fixture_{id(root)}",
    )
    context = reader_fixture.load_validator().load_effective_ledger_view(
        root,
        item,
        logical_ledger_path,
    )

    assert context.observation.failure_ids == (
        "WI-LEDGER-COMPAT-SET-TOPOLOGY",
    )
    assert context.observation.diagnostics == (
        "WI-LEDGER-COMPAT-SET-TOPOLOGY: H1 participant location failed for work-items/decision-h1-compatibility.json",
    )


def test_archive_both_h1_members_preserves_logical_group_and_sealed_artifacts(
    tmp_path: Path,
) -> None:
    root = tmp_path / "both-archives"
    writer, reader, request, items, paths = fixture(root)
    for index, item in enumerate(items, start=1):
        (item / "status.md").write_bytes(active_status(f"Relocate H1 member {index}."))
    applied = writer.apply_sealed_prefix_activation(root, request)
    with (items[0] / "agent-runs.jsonl").open("ab") as stream:
        stream.write(
            canonical(
                {
                    "schemaVersion": 2,
                    "runId": "close-revise-a-after-seal",
                    "workItem": items[0].name,
                    "role": "analyst",
                    "executionRole": "internal",
                    "status": "completed",
                    "gate": "PASS",
                    "scope": ["target.md"],
                    "artifact": "target.md",
                    "lane": "qa",
                    "effort": "high",
                    "closesRunIds": ["revise-a-0001"],
                    "evidence": [{"kind": "artifact", "ref": "target.md"}],
                    "startedAt": "2026-09-10T02:00:00Z",
                    "updatedAt": "2026-09-10T02:00:01Z",
                }
            )
            + b"\n"
        )
    with (items[1] / "agent-runs.jsonl").open("ab") as stream:
        stream.write(
            canonical(
                {
                    "schemaVersion": 2,
                    "runId": "close-launch-b-after-seal",
                    "workItem": items[1].name,
                    "role": "analyst",
                    "executionRole": "internal",
                    "status": "completed",
                    "gate": "none",
                    "scope": ["synthetic reader fixture"],
                    "eventKind": "terminal",
                    "launchRunId": "launch-b-open",
                    "startedAt": "2026-09-10T02:00:00Z",
                    "updatedAt": "2026-09-10T02:00:01Z",
                }
            )
            + b"\n"
        )
    before_ledgers = {
        path: root.joinpath(*path.split("/")).read_bytes() for path in paths
    }
    sealed_paths = (
        request.h1_manifest_path,
        request.ledger_manifest_path,
        "work-items/legacy-ledger-projections.jsonl",
        applied["receiptPath"],
    )
    sealed_hashes = {
        path: digest(root.joinpath(*path.split("/")).read_bytes())
        for path in sealed_paths
    }
    before_contexts = reader._load_effective_ledger_group(root)
    before_views = {path: before_contexts[path].view for path in paths}

    receipts = []
    for index, (item, path) in enumerate(zip(items, paths), start=1):
        instant = f"2026-09-10T0{index + 2}:00:00Z"
        operation_id = f"h1-relocation-both-{index}"
        successor_slug = f"{item.name}-successor"
        (item / "bug-dispositions.json").write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "workItem": item.name,
                    "closedAt": instant,
                    "bugs": [],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        writer.refresh_readme(root, allow_marker_bootstrap=True)
        states = []
        errors = reader.validate_work_item(
            item, strict_revise=False, obligation_state_out=states
        )
        assert errors == []
        assert len(states) == 1
        assert states[0].open_revise == ()
        assert states[0].open_launches == ()
        ledger_sha256 = digest((item / "agent-runs.jsonl").read_bytes())
        transfer = {
            "schemaVersion": 1,
            "sourceWorkItem": item.name,
            "successorWorkItem": successor_slug,
            "expectedSourceLedgerSha256": ledger_sha256,
            "obligations": [],
        }
        successor = (
            "Task: Continue after the H1 member archive.\n"
            f"Continues: {item.name}\n"
            f"Obligation-transfer: {operation_id}\n"
            "Next action: Verify the relocated group.\n"
            f"updated: {instant}\n"
        ).encode("utf-8")
        receipts.append(
            writer.archive_with_successor(
                root,
                item.name,
                (
                    f"Closed: {instant}\n"
                    "Outcome: Archived one H1 participant.\n"
                    "Evidence: focused two-archive relocation test\n"
                    "Residual risk: None in fixture.\n"
                ).encode("utf-8"),
                instant,
                successor_slug,
                successor,
                operation_id,
                ledger_sha256,
                digest((root / "work-items" / "README.md").read_bytes()),
                obligation_transfer_data=json.dumps(transfer, sort_keys=True).encode(
                    "utf-8"
                ),
            )
        )
        assert not (root / "work-items" / "active" / item.name).exists()
        assert reader.validate_work_item(
            root.joinpath(*receipts[-1]["archivePath"].split("/")),
            strict_revise=False,
            validate_status_file=False,
        ) == []

    after_contexts = reader._load_effective_ledger_group(root)
    assert set(after_contexts) == set(paths)
    assert {path: after_contexts[path].view for path in paths} == before_views
    assert {
        path: digest(root.joinpath(*path.split("/")).read_bytes())
        for path in sealed_paths
    } == sealed_hashes
    for path, raw, receipt in zip(paths, before_ledgers.values(), receipts):
        archive_ledger = root.joinpath(
            *receipt["archivePath"].split("/"), "agent-runs.jsonl"
        )
        assert archive_ledger.read_bytes() == raw
        assert not root.joinpath(*path.split("/")).exists()


@pytest.mark.parametrize(
    ("boundary", "exact_after"),
    (
        ("after-ledger-manifest", False),
        ("after-h1-manifest", False),
        ("after-registry-readback", False),
        ("after-receipt-create", True),
    ),
)
def test_apply_failure_boundaries_are_exact_before_or_after(
    tmp_path: Path,
    boundary: str,
    exact_after: bool,
) -> None:
    root = tmp_path / boundary
    writer, reader, request, _items, paths = fixture(root)
    before = tree_state(root)

    with pytest.raises(writer.LifecycleError) as caught:
        writer.apply_sealed_prefix_activation(
            root,
            request,
            inject_failure=boundary,
        )

    assert caught.value.failure_id == "WI-LEDGER-COMPAT-COMMIT-INDETERMINATE"
    contexts = reader._load_effective_ledger_group(root)
    if exact_after:
        assert set(contexts) == set(paths)
        assert all(row.observation.activation_state == "active" for row in contexts.values())
    else:
        assert tree_state(root) == before
        assert contexts == {}


def test_revoke_is_receipt_bound_replay_safe_and_refuses_suffix(
    tmp_path: Path,
) -> None:
    root = tmp_path / "revoke"
    writer, reader, request, _items, paths = fixture(root)
    applied = writer.apply_sealed_prefix_activation(root, request)
    apply_receipt = root.joinpath(*applied["receiptPath"].split("/"))
    registry = root / "work-items" / "legacy-ledger-projections.jsonl"
    apply_registry_bytes = registry.read_bytes()
    apply_registry_sha256 = digest(apply_registry_bytes)
    registry.write_bytes(
        registry.read_bytes()
        + canonical({"operationId": "unrelated-registry-entry"})
        + b"\n"
    )
    stale_request = writer.SealedPrefixRevokeRequestV1(
        apply_receipt_path=applied["receiptPath"],
        apply_receipt_sha256=digest(apply_receipt.read_bytes()),
        expected_registry_sha256=apply_registry_sha256,
        recorded_at="2026-09-08T01:01:00Z",
    )
    stale_before = tree_state(root)
    with pytest.raises(writer.LifecycleError) as stale:
        writer.preflight_sealed_prefix_revoke(root, stale_request)
    assert stale.value.failure_id == "WI-LEDGER-MIGRATION-LEDGER-DRIFT"
    assert tree_state(root) == stale_before
    registry.write_bytes(apply_registry_bytes)

    revoke_request = writer.SealedPrefixRevokeRequestV1(
        apply_receipt_path=applied["receiptPath"],
        apply_receipt_sha256=digest(apply_receipt.read_bytes()),
        expected_registry_sha256=digest(registry.read_bytes()),
        recorded_at="2026-09-08T01:01:00Z",
    )
    before = tree_state(root)
    plan = writer.preflight_sealed_prefix_revoke(root, revoke_request)
    dry_run = writer.revoke_sealed_prefix_activation(
        root,
        revoke_request,
        dry_run=True,
    )
    assert plan.state == "revoke"
    assert dry_run["readiness"] == "READY"
    assert tree_state(root) == before

    ledgers_before = {
        path: root.joinpath(*path.split("/")).read_bytes() for path in paths
    }
    revoked = writer.revoke_sealed_prefix_activation(root, revoke_request)
    assert revoked["state"] == "revoke"
    assert revoked["replay"] is False
    assert root.joinpath(*revoked["receiptPath"].split("/")).is_file()
    assert {
        path: root.joinpath(*path.split("/")).read_bytes() for path in paths
    } == ledgers_before
    revoked_contexts = reader._load_effective_ledger_group(root)
    assert set(revoked_contexts) == set(paths)
    assert all(
        context.observation.activation_state == "revoked"
        and context.view is None
        and all(
            not any(
                (
                    row.authority.launch_eligible,
                    row.authority.terminal_eligible,
                    row.authority.revise_target_eligible,
                    row.authority.closer_eligible,
                    row.authority.artifact_evidence_eligible,
                )
            )
            for row in context.rows
        )
        for context in revoked_contexts.values()
    )
    after = tree_state(root)
    replay = writer.revoke_sealed_prefix_activation(root, revoke_request)
    assert replay["replay"] is True
    assert tree_state(root) == after
    after_revoke_request = writer.SealedPrefixRevokeRequestV1(
        apply_receipt_path=applied["receiptPath"],
        apply_receipt_sha256=digest(apply_receipt.read_bytes()),
        expected_registry_sha256=digest(registry.read_bytes()),
        recorded_at="2026-09-08T01:01:00Z",
    )
    replay_after = writer.revoke_sealed_prefix_activation(
        root,
        after_revoke_request,
    )
    assert replay_after["replay"] is True
    assert tree_state(root) == after

    suffix_root = tmp_path / "suffix"
    suffix_writer, _reader, suffix_request, _items, suffix_paths = fixture(suffix_root)
    suffix_applied = suffix_writer.apply_sealed_prefix_activation(
        suffix_root,
        suffix_request,
    )
    suffix_receipt = suffix_root.joinpath(*suffix_applied["receiptPath"].split("/"))
    suffix_registry = suffix_root / "work-items" / "legacy-ledger-projections.jsonl"
    suffix_revoke = suffix_writer.SealedPrefixRevokeRequestV1(
        apply_receipt_path=suffix_applied["receiptPath"],
        apply_receipt_sha256=digest(suffix_receipt.read_bytes()),
        expected_registry_sha256=digest(suffix_registry.read_bytes()),
        recorded_at="2026-09-08T01:01:00Z",
    )
    suffix_ledger = suffix_root.joinpath(*suffix_paths[0].split("/"))
    suffix_ledger.write_bytes(
        suffix_ledger.read_bytes()
        + canonical(
            {
                "schemaVersion": 2,
                "runId": "strict-suffix-0001",
                "workItem": "reader-a",
                "role": "analyst",
                "executionRole": "internal",
                "status": "completed",
                "gate": "none",
                "scope": ["synthetic suffix"],
                "startedAt": "2026-09-08T01:00:00Z",
                "updatedAt": "2026-09-08T01:00:01Z",
            }
        )
        + b"\n"
    )
    suffix_before = tree_state(suffix_root)
    with pytest.raises(suffix_writer.LifecycleError) as refused:
        suffix_writer.preflight_sealed_prefix_revoke(suffix_root, suffix_revoke)
    assert refused.value.failure_id == "WI-LEDGER-COMPAT-REVOKE-AFTER-SUFFIX"
    assert tree_state(suffix_root) == suffix_before


def test_cli_v2_dry_run_and_partial_or_mixed_modes_fail_before_mutation(
    tmp_path: Path,
) -> None:
    root = tmp_path / "cli"
    writer, _reader, request, _items, _paths = fixture(root)
    input_root = root / "inputs"
    input_root.mkdir()
    ledger_input = input_root / "ledger.json"
    h1_input = input_root / "h1.json"
    ledger_input.write_bytes(request.ledger_manifest_bytes)
    h1_input.write_bytes(request.h1_manifest_bytes)
    before = tree_state(root)
    common = [
        sys.executable,
        "-B",
        str(WRITER_SCRIPT),
        "apply-legacy-ledger-projection",
        "--root",
        str(root),
        "--manifest-file",
        str(ledger_input),
        "--expected-registry-sha256",
        request.expected_registry_sha256,
        "--recorded-at",
        request.recorded_at,
        "--dry-run",
    ]
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    complete = subprocess.run(
        [
            *common,
            "--ledger-manifest-path",
            request.ledger_manifest_path,
            "--h1-manifest-file",
            str(h1_input),
            "--h1-manifest-path",
            request.h1_manifest_path,
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert complete.returncode == 0, complete.stdout
    assert json.loads(complete.stdout)["readiness"] == "READY"
    assert tree_state(root) == before

    ledger_input.write_bytes(
        b'{"schemaVersion":2,' + request.ledger_manifest_bytes[1:]
    )
    duplicate = subprocess.run(
        [
            *common,
            "--ledger-manifest-path",
            request.ledger_manifest_path,
            "--h1-manifest-file",
            str(h1_input),
            "--h1-manifest-path",
            request.h1_manifest_path,
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert duplicate.returncode == 1
    assert "WI-LEDGER-MIGRATION-MANIFEST-INVALID" in duplicate.stdout
    ledger_input.write_bytes(request.ledger_manifest_bytes)
    assert tree_state(root) == before

    for extra in (
        ["--h1-manifest-file", str(h1_input)],
        [
            "--ledger-manifest-path",
            request.ledger_manifest_path,
            "--h1-manifest-file",
            str(h1_input),
            "--h1-manifest-path",
            request.h1_manifest_path,
            "--operation-id",
            "legacy-operation",
        ],
    ):
        failed = subprocess.run(
            [*common, *extra],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        assert failed.returncode == 1
        assert "WI-LEDGER-COMPAT-CLI-ARGS" in failed.stdout
        assert tree_state(root) == before
