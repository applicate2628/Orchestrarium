import copy
import hashlib
import importlib.util
import inspect
import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate-work-item-state.py"
LEDGER = ROOT / "scripts" / "agent-run-ledger.py"
LIFECYCLE = ROOT / "scripts" / "mutate-work-item.py"
FIXTURE = ROOT / "tests" / "fixtures" / "agent-run-ledger" / "legacy-obligation-migration-v2"


def load_validator():
    spec = importlib.util.spec_from_file_location("legacy_obligation_validator", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run_script(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(path), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_directory_link(link: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    link.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
        assert result.returncode == 0, result.stdout
    else:
        link.symlink_to(target, target_is_directory=True)


def staged_fixture(tmp_path: Path, *, operation_id: str = "migration-op-001"):
    item, expected = copied_fixture(tmp_path)
    ledger = load_script(LEDGER, f"migration_ledger_{operation_id}_{id(item)}")
    before = (item / "agent-runs.jsonl").read_bytes()
    result = ledger.stage_invalid_finding_class_migration(
        item,
        expected["targetRunId"],
        expected["targetRawSha256"],
        sha256(before),
        operation_id,
        "2026-08-18T00:00:00Z",
    )
    return item, expected, ledger, before, result


def committed_fixture(tmp_path: Path, *, operation_id: str = "migration-op-001"):
    item, expected = copied_fixture(tmp_path)
    lifecycle = load_script(LIFECYCLE, f"migration_lifecycle_{operation_id}_{id(item)}")
    before = (item / "agent-runs.jsonl").read_bytes()
    result = lifecycle.migrate_legacy_ledger_obligation(
        tmp_path,
        item.name,
        expected["targetRunId"],
        expected["targetRawSha256"],
        sha256(before),
        operation_id,
        "2026-08-18T00:00:00Z",
    )
    return item, expected, lifecycle, before, result


def append_reviewer_pass(item: Path, expected: dict) -> None:
    ledger_owner = load_script(LEDGER, f"reviewer_pass_ledger_{id(item)}")
    ledger_path = item / "agent-runs.jsonl"
    work_item = json.loads(ledger_path.read_text(encoding="utf-8").splitlines()[0])["workItem"]
    launch = {
        "schemaVersion": 2, "runId": "migration-review-r1", "workItem": work_item,
        "role": "toolchain-engineer", "executionRole": "internal", "status": "running", "gate": "none",
        "scope": ["implementation.md"], "eventKind": "launch",
        "startedAt": "2026-08-18T00:01:00Z", "updatedAt": "2026-08-18T00:01:00Z",
    }
    terminal = {
        **launch, "runId": "migration-review-r1-terminal", "status": "completed", "gate": "PASS",
        "eventKind": "terminal", "launchRunId": launch["runId"], "closesRunIds": [expected["targetRunId"]],
        "artifact": "implementation.md", "artifactRevision": "a" * 64, "lane": "implementation", "effort": "high",
        "evidence": [{"kind": "artifact", "ref": "implementation.md"}],
        "startedAt": "2026-08-18T00:02:00Z", "updatedAt": "2026-08-18T00:02:00Z",
    }
    with ledger_path.open("ab") as stream:
        stream.write((ledger_owner.serialize_event(launch) + "\n").encode())
        stream.write((ledger_owner.serialize_event(terminal) + "\n").encode())


def transition_fixture(tmp_path: Path):
    item, expected, lifecycle, _, migration = committed_fixture(tmp_path)
    ledger_path = item / "agent-runs.jsonl"
    append_reviewer_pass(item, expected)
    instant = "2026-08-18T00:03:00Z"
    (item / "bug-dispositions.json").write_text(json.dumps({
        "schemaVersion": 1, "workItem": item.name, "closedAt": instant, "bugs": []
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    closure_file = tmp_path / "closure-input.md"
    closure_file.write_text(
        f"Closed: {instant}\nOutcome: Migrated legacy obligation settled.\nEvidence: focused integration test\nResidual risk: None in fixture.\n",
        encoding="utf-8",
    )
    successor_file = tmp_path / "successor-input.md"
    successor_file.write_text(
        "Task: Resume model ranking after explicit reprioritization.\nNext action: Await Orchestrator 2.0 specification.\nupdated: 2026-08-18T00:03:00Z\n",
        encoding="utf-8",
    )
    lifecycle.refresh_readme(tmp_path)
    readme = tmp_path / "work-items" / "README.md"
    return {
        "root": tmp_path, "item": item, "slug": item.name, "lifecycle": lifecycle,
        "closure": closure_file.read_bytes(), "instant": instant,
        "successorSlug": f"{item.name}-successor", "successor": successor_file.read_bytes(),
        "operationId": "transition-op-001", "ledgerSha": sha256(ledger_path.read_bytes()),
        "readmeSha": sha256(readme.read_bytes()), "migration": migration,
    }


def run_transition(fixture: dict, *, inject: str | None = None):
    return fixture["lifecycle"].archive_with_successor(
        fixture["root"], fixture["slug"], fixture["closure"], fixture["instant"],
        fixture["successorSlug"], fixture["successor"], fixture["operationId"],
        fixture["ledgerSha"], fixture["readmeSha"], inject_failure_at=inject,
    )


def transfer_fixture(tmp_path: Path):
    item, expected, lifecycle, _, migration = committed_fixture(tmp_path)
    ledger_path = item / "agent-runs.jsonl"
    ledger_before = ledger_path.read_bytes()
    instant = "2026-08-18T00:03:00Z"
    (item / "bug-dispositions.json").write_text(json.dumps({
        "schemaVersion": 1, "workItem": item.name, "closedAt": instant, "bugs": []
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lifecycle.refresh_readme(tmp_path)
    validator = load_validator()
    metadata: list[dict[str, object]] = []
    errors: list[str] = []
    raw_events = validator.load_jsonl(ledger_path, errors, metadata, ledger_before)
    assert errors == []
    effective_events, _, projection_errors = validator.project_legacy_obligation_migrations(
        raw_events, metadata, item
    )
    assert projection_errors == []
    raw_position = next(
        position for position, event in enumerate(raw_events)
        if event.get("runId") == expected["targetRunId"]
    )
    raw_event = raw_events[raw_position]
    projected_event = next(
        event for event in effective_events
        if event.get("runId") == expected["targetRunId"]
    )
    successor_slug = f"{item.name}-successor"
    operation_id = "transition-transfer-op-001"
    transfer = {
        "schemaVersion": 1,
        "sourceWorkItem": item.name,
        "successorWorkItem": successor_slug,
        "expectedSourceLedgerSha256": sha256(ledger_before),
        "obligations": [{
            "runId": expected["targetRunId"],
            "rawLineOrdinal": metadata[raw_position]["line"],
            "rawLineSha256": metadata[raw_position]["sha256"],
            "rawEventSha256": sha256(json.dumps(
                raw_event, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            ).encode("utf-8")),
            "projectedEventSha256": sha256(json.dumps(
                projected_event, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            ).encode("utf-8")),
        }],
    }
    closure = (
        f"Closed: {instant}\n"
        "Outcome: Transferred the unresolved obligation.\n"
        "Evidence: focused transfer integration test\n"
        "Residual risk: None in fixture.\n"
    ).encode("utf-8")
    successor = (
        "Task: Continue the transferred obligation.\n"
        f"Continues: {item.name}\n"
        f"Obligation-transfer: {operation_id}\n"
        "Next action: Resolve the inherited review finding.\n"
        "updated: 2026-08-18T00:03:00Z\n"
    ).encode("utf-8")
    return {
        "root": tmp_path,
        "item": item,
        "slug": item.name,
        "lifecycle": lifecycle,
        "closure": closure,
        "instant": instant,
        "successorSlug": successor_slug,
        "successor": successor,
        "operationId": operation_id,
        "ledgerSha": sha256(ledger_before),
        "ledgerBefore": ledger_before,
        "readmeSha": sha256((tmp_path / "work-items" / "README.md").read_bytes()),
        "migration": migration,
        "transfer": json.dumps(transfer, sort_keys=True).encode("utf-8"),
        "transferObject": transfer,
    }


def two_migration_transfer_fixture(tmp_path: Path):
    item, expected = copied_fixture(tmp_path)
    ledger_path = item / "agent-runs.jsonl"
    initial = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
    ]
    second_launch = copy.deepcopy(initial[0])
    second_launch["runId"] = "toolchain-luna-profile-floor-20260812-r2"
    second_terminal = copy.deepcopy(initial[1])
    second_terminal["runId"] = "toolchain-luna-profile-floor-20260812-r2-terminal"
    second_terminal["launchRunId"] = second_launch["runId"]
    second_launch_raw = json.dumps(
        second_launch, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    second_terminal_raw = json.dumps(
        second_terminal, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    with ledger_path.open("ab") as stream:
        stream.write(second_launch_raw + b"\n")
        stream.write(second_terminal_raw + b"\n")

    lifecycle = load_script(LIFECYCLE, f"two_migration_transfer_{id(item)}")
    first_before = ledger_path.read_bytes()
    lifecycle.migrate_legacy_ledger_obligation(
        tmp_path,
        item.name,
        expected["targetRunId"],
        expected["targetRawSha256"],
        sha256(first_before),
        "migration-op-001",
        "2026-08-18T00:00:00Z",
    )
    second_before = ledger_path.read_bytes()
    lifecycle.migrate_legacy_ledger_obligation(
        tmp_path,
        item.name,
        second_terminal["runId"],
        sha256(second_terminal_raw),
        sha256(second_before),
        "migration-op-002",
        "2026-08-18T00:00:01Z",
    )
    ledger_before = ledger_path.read_bytes()
    open_rows = lifecycle._inspect_transfer_obligations(tmp_path, item)
    assert [row.source_kind for row in open_rows] == [
        "migration-replaced",
        "migration-replaced",
    ]
    instant = "2026-08-18T00:03:00Z"
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
    lifecycle.refresh_readme(tmp_path)
    successor_slug = f"{item.name}-successor"
    operation_id = "transition-transfer-two-migrations"
    successor = (
        "Task: Continue both transferred obligations.\n"
        f"Continues: {item.name}\n"
        f"Obligation-transfer: {operation_id}\n"
        "Next action: Resolve both inherited review findings.\n"
        f"updated: {instant}\n"
    ).encode("utf-8")
    transfer = {
        "schemaVersion": 1,
        "sourceWorkItem": item.name,
        "successorWorkItem": successor_slug,
        "expectedSourceLedgerSha256": sha256(ledger_before),
        "obligations": [
            {
                "runId": row.run_id,
                "rawLineOrdinal": row.raw_line_ordinal,
                "rawLineSha256": row.raw_line_sha256,
                "rawEventSha256": row.raw_event_sha256,
                "projectedEventSha256": row.projected_event_sha256,
            }
            for row in open_rows
        ],
    }
    receipt_paths = sorted((item / "ledger-migration-receipts").glob("*.json"))
    archive_prefix = f"work-items/archive/2026-08/{item.name}"
    return {
        "root": tmp_path,
        "item": item,
        "slug": item.name,
        "lifecycle": lifecycle,
        "closure": (
            f"Closed: {instant}\n"
            "Outcome: Transferred two unresolved obligations.\n"
            "Evidence: focused plural migration receipt test\n"
            "Residual risk: None in fixture.\n"
        ).encode("utf-8"),
        "instant": instant,
        "successorSlug": successor_slug,
        "successor": successor,
        "operationId": operation_id,
        "ledgerSha": sha256(ledger_before),
        "ledgerBefore": ledger_before,
        "readmeSha": sha256((tmp_path / "work-items" / "README.md").read_bytes()),
        "transfer": json.dumps(transfer, sort_keys=True).encode("utf-8"),
        "transferObject": transfer,
        "migrationReceipts": [
            {
                "path": (
                    f"{archive_prefix}/ledger-migration-receipts/{path.name}"
                ),
                "sha256": sha256(path.read_bytes()),
            }
            for path in receipt_paths
        ],
    }


def native_transfer_fixture(tmp_path: Path):
    item, expected = copied_fixture(tmp_path)
    lifecycle = load_script(LIFECYCLE, f"native_transfer_{id(item)}")
    ledger_path = item / "agent-runs.jsonl"
    native_events = [
        json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()
    ]
    native_events[1]["findingClass"] = "correctness"
    ledger_path.write_bytes(b"".join(
        json.dumps(event, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n"
        for event in native_events
    ))
    ledger_before = ledger_path.read_bytes()
    instant = "2026-08-18T00:03:00Z"
    (item / "bug-dispositions.json").write_text(json.dumps({
        "schemaVersion": 1, "workItem": item.name, "closedAt": instant, "bugs": []
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lifecycle.refresh_readme(tmp_path)
    metadata: list[dict[str, object]] = []
    errors: list[str] = []
    raw_events = load_validator().load_jsonl(ledger_path, errors, metadata, ledger_before)
    assert errors == []
    raw_position = next(
        position for position, event in enumerate(raw_events)
        if event.get("runId") == expected["targetRunId"]
    )
    raw_event = raw_events[raw_position]
    successor_slug = f"{item.name}-native-successor"
    operation_id = "transition-native-transfer-op-001"
    transfer = {
        "schemaVersion": 1,
        "sourceWorkItem": item.name,
        "successorWorkItem": successor_slug,
        "expectedSourceLedgerSha256": sha256(ledger_before),
        "obligations": [{
            "runId": expected["targetRunId"],
            "rawLineOrdinal": metadata[raw_position]["line"],
            "rawLineSha256": metadata[raw_position]["sha256"],
            "rawEventSha256": sha256(json.dumps(
                raw_event, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            ).encode("utf-8")),
            "projectedEventSha256": sha256(json.dumps(
                raw_event, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            ).encode("utf-8")),
        }],
    }
    successor = (
        "Task: Continue the native obligation.\n"
        f"Continues: {item.name}\n"
        f"Obligation-transfer: {operation_id}\n"
        "Next action: Resolve the inherited review finding.\n"
        f"updated: {instant}\n"
    ).encode("utf-8")
    return {
        "root": tmp_path,
        "item": item,
        "slug": item.name,
        "lifecycle": lifecycle,
        "closure": (
            f"Closed: {instant}\n"
            "Outcome: Transferred the native obligation.\n"
            "Evidence: focused native transfer test\n"
            "Residual risk: None in fixture.\n"
        ).encode("utf-8"),
        "instant": instant,
        "successorSlug": successor_slug,
        "successor": successor,
        "operationId": operation_id,
        "ledgerSha": sha256(ledger_before),
        "ledgerBefore": ledger_before,
        "readmeSha": sha256((tmp_path / "work-items" / "README.md").read_bytes()),
        "transfer": json.dumps(transfer, sort_keys=True).encode("utf-8"),
        "transferObject": transfer,
    }


def run_transfer(fixture: dict, *, inject: str | None = None):
    return fixture["lifecycle"].archive_with_successor(
        fixture["root"], fixture["slug"], fixture["closure"], fixture["instant"],
        fixture["successorSlug"], fixture["successor"], fixture["operationId"],
        fixture["ledgerSha"], fixture["readmeSha"],
        obligation_transfer_data=fixture["transfer"], inject_failure_at=inject,
    )


@pytest.mark.parametrize(
    ("boundary", "expected_phase"),
    (
        ("T0", "active-intent"),
        ("T1", "active-intent"),
        ("T2", "active-intent"),
        ("T3", "moved-intent"),
        ("T4", "moved-intent"),
        ("T5", "moved-intent"),
        ("T6", "settled-archive"),
        ("T7", "settled-archive"),
        ("T8", "settled-archive"),
        ("T9", "settled-archive"),
        (None, "settled-archive"),
    ),
)
def test_ledger_location_resolver_covers_archive_transition_states(
    tmp_path: Path,
    boundary: str | None,
    expected_phase: str,
) -> None:
    fixture = transfer_fixture(tmp_path)
    if boundary is None:
        run_transfer(fixture)
    else:
        with pytest.raises(fixture["lifecycle"].LifecycleError):
            run_transfer(fixture, inject=boundary)
    logical_work_item = f"work-items/active/{fixture['slug']}"
    logical_ledger_path = f"{logical_work_item}/agent-runs.jsonl"

    resolved = fixture["lifecycle"].resolve_work_item_ledger_location(
        tmp_path,
        logical_work_item=logical_work_item,
        logical_ledger_path=logical_ledger_path,
    )

    assert resolved.phase == expected_phase
    assert resolved.logical_work_item == logical_work_item
    assert resolved.logical_ledger_path == logical_ledger_path
    assert resolved.ledger_sha256 == fixture["ledgerSha"]
    assert resolved.operation_id == fixture["operationId"]
    assert resolved.provenance_path is not None
    assert resolved.provenance_sha256 is not None
    physical = tmp_path.joinpath(*resolved.physical_ledger_path.split("/"))
    assert physical.read_bytes() == fixture["ledgerBefore"]
    assert (tmp_path / logical_ledger_path).exists() == expected_phase.startswith(
        "active"
    )


def test_ledger_location_resolver_returns_plain_active_without_provenance(
    tmp_path: Path,
) -> None:
    fixture = transfer_fixture(tmp_path)
    logical_work_item = f"work-items/active/{fixture['slug']}"
    logical_ledger_path = f"{logical_work_item}/agent-runs.jsonl"
    before = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    resolved = fixture["lifecycle"].resolve_work_item_ledger_location(
        tmp_path,
        logical_work_item=logical_work_item,
        logical_ledger_path=logical_ledger_path,
    )

    assert resolved.phase == "active"
    assert resolved.physical_work_item == logical_work_item
    assert resolved.physical_ledger_path == logical_ledger_path
    assert resolved.ledger_sha256 == fixture["ledgerSha"]
    assert resolved.operation_id is None
    assert resolved.provenance_path is None
    assert resolved.provenance_sha256 is None
    assert {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    } == before


def test_ledger_location_resolver_accepts_v1_settled_receipt(tmp_path: Path) -> None:
    fixture = transition_fixture(tmp_path)
    receipt = run_transition(fixture)
    logical_work_item = f"work-items/active/{fixture['slug']}"

    resolved = fixture["lifecycle"].resolve_work_item_ledger_location(
        tmp_path,
        logical_work_item=logical_work_item,
        logical_ledger_path=f"{logical_work_item}/agent-runs.jsonl",
    )

    assert receipt["schemaVersion"] == 1
    assert resolved.phase == "settled-archive"
    assert resolved.operation_id == fixture["operationId"]
    assert resolved.ledger_sha256 == fixture["ledgerSha"]


def test_ledger_location_settlement_survives_normal_successor_and_readme_changes(
    tmp_path: Path,
) -> None:
    fixture = transfer_fixture(tmp_path)
    run_transfer(fixture)
    logical_work_item = f"work-items/active/{fixture['slug']}"
    logical_ledger_path = f"{logical_work_item}/agent-runs.jsonl"
    before = fixture["lifecycle"].resolve_work_item_ledger_location(
        tmp_path,
        logical_work_item=logical_work_item,
        logical_ledger_path=logical_ledger_path,
    )

    fixture["lifecycle"].start_item(
        tmp_path,
        fixture["successorSlug"],
        successor_status(fixture["slug"], fixture["operationId"]),
    )
    after = fixture["lifecycle"].resolve_work_item_ledger_location(
        tmp_path,
        logical_work_item=logical_work_item,
        logical_ledger_path=logical_ledger_path,
    )

    assert after == before


@pytest.mark.parametrize(
    ("drift", "failure_id"),
    (
        ("ledger", "WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH"),
        ("receipt-duplicate-key", "WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH"),
        ("missing-receipt", "WI-LEDGER-COMPAT-ACTIVATION-INCOMPLETE"),
        ("active-copy", "WI-CATEGORY-DUAL-LOCATION"),
    ),
)
def test_ledger_location_settlement_drift_fails_closed(
    tmp_path: Path,
    drift: str,
    failure_id: str,
) -> None:
    fixture = transfer_fixture(tmp_path)
    receipt = run_transfer(fixture)
    archive = tmp_path.joinpath(*receipt["archivePath"].split("/"))
    receipt_path = archive / "lifecycle-transition-receipt.json"
    if drift == "ledger":
        (archive / "agent-runs.jsonl").write_bytes(
            (archive / "agent-runs.jsonl").read_bytes() + b"{}\n"
        )
    elif drift == "receipt-duplicate-key":
        receipt_path.write_bytes(
            b'{"schemaVersion":2,' + receipt_path.read_bytes()[1:]
        )
    elif drift == "missing-receipt":
        receipt_path.unlink()
    else:
        active = tmp_path / "work-items" / "active" / fixture["slug"]
        active.mkdir(parents=True)
        (active / "agent-runs.jsonl").write_bytes(fixture["ledgerBefore"])
    logical_work_item = f"work-items/active/{fixture['slug']}"

    with pytest.raises(fixture["lifecycle"].LifecycleError) as caught:
        fixture["lifecycle"].resolve_work_item_ledger_location(
            tmp_path,
            logical_work_item=logical_work_item,
            logical_ledger_path=f"{logical_work_item}/agent-runs.jsonl",
        )

    assert caught.value.failure_id == failure_id


def test_ledger_location_intent_and_settlement_must_agree(tmp_path: Path) -> None:
    fixture = transfer_fixture(tmp_path)
    with pytest.raises(fixture["lifecycle"].LifecycleError):
        run_transfer(fixture, inject="T6")
    intent_path = (
        tmp_path
        / ".scratch"
        / "work-items-lifecycle-transitions"
        / f"{fixture['operationId']}.json"
    )
    intent = json.loads(intent_path.read_bytes())
    intent["expectedReadmeSha256"] = "0" * 64
    intent_path.write_text(
        json.dumps(intent, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    logical_work_item = f"work-items/active/{fixture['slug']}"

    with pytest.raises(fixture["lifecycle"].LifecycleError) as caught:
        fixture["lifecycle"].resolve_work_item_ledger_location(
            tmp_path,
            logical_work_item=logical_work_item,
            logical_ledger_path=f"{logical_work_item}/agent-runs.jsonl",
        )

    assert caught.value.failure_id == "WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH"


def test_ledger_location_moved_intent_rejects_invalid_after_image_type(
    tmp_path: Path,
) -> None:
    fixture = transfer_fixture(tmp_path)
    with pytest.raises(fixture["lifecycle"].LifecycleError):
        run_transfer(fixture, inject="T3")
    intent_path = (
        tmp_path
        / ".scratch"
        / "work-items-lifecycle-transitions"
        / f"{fixture['operationId']}.json"
    )
    intent = json.loads(intent_path.read_bytes())
    intent["statusAfter"] = 7
    intent_path.write_text(
        json.dumps(intent, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    logical_work_item = f"work-items/active/{fixture['slug']}"

    with pytest.raises(fixture["lifecycle"].LifecycleError) as caught:
        fixture["lifecycle"].resolve_work_item_ledger_location(
            tmp_path,
            logical_work_item=logical_work_item,
            logical_ledger_path=f"{logical_work_item}/agent-runs.jsonl",
        )

    assert caught.value.failure_id == "WI-LIFECYCLE-TRANSITION-INTENT-INVALID"


def test_ledger_location_rejects_archive_reparse(tmp_path: Path) -> None:
    fixture = transfer_fixture(tmp_path)
    receipt = run_transfer(fixture)
    archive = tmp_path.joinpath(*receipt["archivePath"].split("/"))
    real_archive = archive.with_name(f"{archive.name}-real")
    archive.rename(real_archive)
    try:
        make_directory_link(archive, real_archive)
    except (OSError, AssertionError) as exc:
        pytest.skip(f"target environment cannot create a directory link: {exc}")
    logical_work_item = f"work-items/active/{fixture['slug']}"

    with pytest.raises(fixture["lifecycle"].LifecycleError):
        fixture["lifecycle"].resolve_work_item_ledger_location(
            tmp_path,
            logical_work_item=logical_work_item,
            logical_ledger_path=f"{logical_work_item}/agent-runs.jsonl",
        )


def successor_status(source_slug: str, operation_id: str) -> bytes:
    return (
        "---\n"
        "template: staged\n"
        "status: active\n"
        "started: 2026-08-18T00:04:00Z\n"
        "updated: 2026-08-18T00:04:00Z\n"
        "---\n\n"
        "Task: Resolve the inherited obligation.\n"
        "Current step: Re-verify the inherited finding.\n"
        "Last result: Successor accepted.\n"
        "Next action: Run the lifecycle oracle.\n"
        "Scope boundary: Successor fixture only.\n"
        "Owner: qa-engineer\n"
        "Integration owner: lead\n"
        "Evidence gate: focused transfer test\n"
        f"Continues: {source_slug}\n"
        f"Obligation-transfer: {operation_id}\n"
    ).encode("utf-8")


def without_transfer_relations(data: bytes) -> bytes:
    return b"".join(
        line
        for line in data.splitlines(keepends=True)
        if not line.startswith((b"Continues:", b"Obligation-transfer:"))
    )


def append_successor_closer(item: Path, target_run_id: str) -> None:
    ledger_owner = load_script(LEDGER, f"successor_closer_{id(item)}")
    ledger_path = item / "agent-runs.jsonl"
    launch = {
        "schemaVersion": 2,
        "runId": "successor-review-r1",
        "workItem": item.name,
        "role": "toolchain-engineer",
        "executionRole": "internal",
        "status": "running",
        "gate": "none",
        "scope": ["implementation.md"],
        "eventKind": "launch",
        "startedAt": "2026-08-18T00:04:10Z",
        "updatedAt": "2026-08-18T00:04:10Z",
    }
    terminal = {
        **launch,
        "runId": "successor-review-r1-terminal",
        "status": "completed",
        "gate": "PASS",
        "eventKind": "terminal",
        "launchRunId": launch["runId"],
        "closesRunIds": [target_run_id],
        "artifact": "implementation.md",
        "artifactRevision": "b" * 64,
        "lane": "implementation",
        "effort": "high",
        "evidence": [{"kind": "artifact", "ref": "implementation.md"}],
        "startedAt": "2026-08-18T00:04:20Z",
        "updatedAt": "2026-08-18T00:04:20Z",
    }
    (item / "implementation.md").write_text("# Successor verification\n", encoding="utf-8")
    with ledger_path.open("ab") as stream:
        stream.write((ledger_owner.serialize_event(launch) + "\n").encode("utf-8"))
        stream.write((ledger_owner.serialize_event(terminal) + "\n").encode("utf-8"))


def copied_fixture(tmp_path: Path) -> tuple[Path, dict]:
    item = tmp_path / "work-items" / "active" / "legacy-obligation-migration-v2"
    shutil.copytree(FIXTURE, item)
    return item, json.loads((item / "expected.json").read_text(encoding="utf-8"))


def loaded(item: Path, validator):
    metadata: list[dict[str, object]] = []
    errors: list[str] = []
    events = validator.load_jsonl(item / "agent-runs.jsonl", errors, metadata)
    assert errors == []
    return events, metadata


def apply_anchor(target: dict, digest: str, **overrides) -> dict:
    anchor = {
        "schemaVersion": 2,
        "runId": "ledger-migration-apply-001",
        "workItem": target["workItem"],
        "role": "lead",
        "executionRole": "main",
        "status": "completed",
        "gate": "none",
        "scope": ["ledger-migration:invalid-finding-class"],
        "eventKind": "legacy-obligation-migration",
        "migrationAction": "apply",
        "migratesRunId": target["runId"],
        "migratesEventSha256": digest,
        "replacementEvent": {**target, "findingClass": "legacy-unclassified"},
        "evidence": [{"kind": "manual-check", "ref": f"invalid-finding-class {target['runId']} {digest} -> legacy-unclassified"}],
        "startedAt": "2026-08-18T00:00:00Z",
        "updatedAt": "2026-08-18T00:00:00Z",
    }
    anchor.update(overrides)
    return anchor


def project(item: Path, validator, events: list[dict], metadata: list[dict[str, object]]):
    return validator.project_legacy_obligation_migrations(events, metadata, item)


def test_migration_anchor_schema_is_closed(tmp_path: Path) -> None:
    item, _ = copied_fixture(tmp_path)
    validator = load_validator()
    events, metadata = loaded(item, validator)
    schema = json.loads((ROOT / "shared" / "schemas" / "agent-runs.schema.json").read_text(encoding="utf-8"))
    anchor = apply_anchor(events[1], str(metadata[1]["sha256"]))
    assert list(Draft202012Validator(schema).iter_errors(anchor)) == []
    assert list(Draft202012Validator(schema).iter_errors({**anchor, "unexpected": True}))
    malformed = dict(anchor)
    for key in ("workItem", "startedAt", "updatedAt", "evidence"):
        malformed.pop(key)
    malformed["unexpectedAttackerField"] = True
    effective, _, projection_errors = project(
        item, validator, events + [malformed], metadata + [{"sha256": sha256(json.dumps(malformed, separators=(",", ":")).encode())}]
    )
    assert projection_errors
    assert effective[1]["findingClass"] == "inline-sufficient"


def test_migration_projection_is_inert_without_anchor(tmp_path: Path) -> None:
    item, _ = copied_fixture(tmp_path)
    validator = load_validator()
    events, metadata = loaded(item, validator)
    effective, counters, errors = project(item, validator, events, metadata)
    assert effective == events
    assert counters == {"raw": 2, "apply": 0, "revoke": 0, "projected": 0}
    assert errors == []


def test_migration_refuses_any_v3_ledger(tmp_path: Path) -> None:
    item, _ = copied_fixture(tmp_path)
    validator = load_validator()
    events, metadata = loaded(item, validator)
    events.append(apply_anchor(events[1], str(metadata[1]["sha256"])))
    events.append({"schemaVersion": 3})
    effective, _, errors = project(item, validator, events, metadata + [{}, {}])
    assert effective == events
    assert errors == ["WI-LEDGER-MIGRATION-V3-UNSUPPORTED"]


def test_recovery_mechanisms_cannot_target_each_other(tmp_path: Path) -> None:
    item, _ = copied_fixture(tmp_path)
    validator = load_validator()
    events, metadata = loaded(item, validator)
    control = apply_anchor(events[1], str(metadata[1]["sha256"]), eventKind="closure-invalidation")
    events.append(control)
    _, _, errors = project(item, validator, events, metadata + [{}])
    assert any("migration control" in error for error in errors)
    apply = apply_anchor(events[1], str(metadata[1]["sha256"]))
    revoke = {
        **apply,
        "runId": "ledger-migration-revoke-malformed",
        "migrationAction": "revoke",
        "revokesMigrationRunId": apply["runId"],
        "revokesMigrationEventSha256": sha256(json.dumps(apply, separators=(",", ":")).encode()),
    }
    for key in ("migratesRunId", "migratesEventSha256", "replacementEvent", "evidence"):
        revoke.pop(key, None)
    effective, _, revoke_errors = project(
        item,
        validator,
        events[:2] + [apply, revoke],
        metadata + [
            {"sha256": sha256(json.dumps(apply, separators=(",", ":")).encode())},
            {"sha256": sha256(json.dumps(revoke, separators=(",", ":")).encode())},
        ],
    )
    assert revoke_errors
    assert effective[1]["findingClass"] == "legacy-unclassified"


def test_position_projection_preserves_terminal_and_existing_discharge(tmp_path: Path) -> None:
    item, _ = copied_fixture(tmp_path)
    validator = load_validator()
    events, metadata = loaded(item, validator)
    anchor = apply_anchor(events[1], str(metadata[1]["sha256"]))
    effective, counters, errors = project(item, validator, events + [anchor], metadata + [{}])
    assert errors == []
    assert [event["runId"] for event in effective] == [event["runId"] for event in events]
    assert effective[1]["eventKind"] == "terminal"
    assert effective[1]["launchRunId"] == events[1]["launchRunId"]
    assert counters["projected"] == 1


def test_model_like_projection_remains_open_revise(tmp_path: Path) -> None:
    item, expected = copied_fixture(tmp_path)
    validator = load_validator()
    events, metadata = loaded(item, validator)
    effective, _, errors = project(item, validator, events + [apply_anchor(events[1], str(metadata[1]["sha256"]))], metadata + [{}])
    validity = validator.derive_event_validity(effective, item, errors)
    open_revise, _ = validator.validate_closure(effective, errors, event_validity=validity)
    assert errors == []
    assert len(open_revise) == expected["openRevise"]


def test_legacy_unclassified_is_distinct_and_protected(tmp_path: Path) -> None:
    validator = load_validator()
    assert "legacy-unclassified" in validator.FINDING_CLASSES
    assert "legacy-unclassified" in validator.PROTECTED_CLASSES
    assert "legacy-unclassified" not in {"security", "publication-safety"}
    target = {
        "schemaVersion": 2, "runId": "legacy-target-001", "role": "qa-engineer",
        "executionRole": "external-reviewer", "status": "revise", "gate": "REVISE",
        "scope": ["fixture"], "artifact": "implementation.md", "lane": "implementation",
        "effort": "high", "provider": "codex", "findingClass": "legacy-unclassified",
    }
    ordinary = {
        **target, "runId": "ordinary-closer-001", "executionRole": "internal",
        "status": "completed", "gate": "PASS", "closesRunIds": [target["runId"]],
    }
    security = {
        **ordinary, "runId": "security-closer-001", "role": "security-reviewer",
        "assignedRole": "security-reviewer", "gate": "WAIVED:security-reviewer",
    }
    user = {**ordinary, "runId": "user-closer-001", "gate": "WAIVED:user"}
    for closer in (ordinary, security):
        errors: list[str] = []
        open_revise, _ = validator.validate_closure([target, closer], errors, event_validity=[True, True])
        assert errors == []
        assert open_revise == []
    errors = []
    validator.validate_closure([target, user], errors, event_validity=[True, True])
    assert any("cannot discharge finding" in error for error in errors)


def test_migration_rejects_target_identity_matrix(tmp_path: Path) -> None:
    item, _ = copied_fixture(tmp_path)
    validator = load_validator()
    events, metadata = loaded(item, validator)
    for key, value in (("migratesRunId", "missing-target"), ("migratesEventSha256", "0" * 64)):
        _, _, errors = project(item, validator, events + [apply_anchor(events[1], str(metadata[1]["sha256"]), **{key: value})], metadata + [{}])
        assert errors


def test_migration_rejects_nonclass_defect_matrix(tmp_path: Path) -> None:
    item, _ = copied_fixture(tmp_path)
    validator = load_validator()
    events, metadata = loaded(item, validator)
    broken = {**events[1], "artifact": "../escape.md"}
    anchor = apply_anchor(broken, str(metadata[1]["sha256"]))
    _, _, errors = project(item, validator, events[:1] + [broken, anchor], metadata + [{}, {}])
    assert errors


def test_migration_rejects_malformed_duplicate_and_missing_fields(tmp_path: Path) -> None:
    item, _ = copied_fixture(tmp_path)
    validator = load_validator()
    events, metadata = loaded(item, validator)
    duplicate = {**events[1], "runId": events[0]["runId"]}
    missing = dict(events[1]); missing.pop("scope")
    for target in (duplicate, missing):
        _, _, errors = project(item, validator, events[:1] + [target, apply_anchor(target, str(metadata[1]["sha256"]))], metadata + [{}, {}])
        assert errors
    second = {**events[1], "runId": "second-invalid-target"}
    second_raw = json.dumps(second, separators=(",", ":")).encode()
    first_anchor = apply_anchor(events[1], str(metadata[1]["sha256"]), runId="duplicate-migration-anchor")
    second_anchor = apply_anchor(second, sha256(second_raw), runId="duplicate-migration-anchor")
    _, counters, duplicate_errors = project(
        item,
        validator,
        events + [second, first_anchor, second_anchor],
        metadata + [
            {"sha256": sha256(second_raw)},
            {"sha256": sha256(json.dumps(first_anchor, separators=(",", ":")).encode())},
            {"sha256": sha256(json.dumps(second_anchor, separators=(",", ":")).encode())},
        ],
    )
    assert duplicate_errors
    assert counters["projected"] == 0
    ordinary_collision = apply_anchor(
        events[1],
        str(metadata[1]["sha256"]),
        runId=events[0]["runId"],
    )
    effective, counters, collision_errors = project(
        item,
        validator,
        events + [ordinary_collision],
        metadata + [
            {"sha256": sha256(json.dumps(ordinary_collision, separators=(",", ":")).encode())}
        ],
    )
    assert any("duplicate runId" in error for error in collision_errors)
    assert counters["projected"] == 0
    assert effective == events + [ordinary_collision]


def test_migration_rejects_scratch_evidence_type_defect(tmp_path: Path) -> None:
    item, _ = copied_fixture(tmp_path)
    validator = load_validator()
    events, metadata = loaded(item, validator)
    target = {**events[1], "scratchEvidence": "not-an-array"}
    _, _, errors = project(item, validator, events[:1] + [target, apply_anchor(target, str(metadata[1]["sha256"]))], metadata + [{}, {}])
    assert errors


def test_migration_rejects_unsafe_artifact_and_evidence(tmp_path: Path) -> None:
    item, _ = copied_fixture(tmp_path)
    validator = load_validator()
    events, metadata = loaded(item, validator)
    target = {**events[1], "artifact": "../../outside.md", "evidence": [{"kind": "unknown", "ref": "bad"}]}
    _, _, errors = project(item, validator, events[:1] + [target, apply_anchor(target, str(metadata[1]["sha256"]))], metadata + [{}, {}])
    assert errors


def test_migration_replacement_must_differ_only_in_finding_class(tmp_path: Path) -> None:
    item, _ = copied_fixture(tmp_path)
    validator = load_validator()
    events, metadata = loaded(item, validator)
    anchor = apply_anchor(events[1], str(metadata[1]["sha256"]))
    anchor["replacementEvent"]["role"] = "qa-engineer"
    _, _, errors = project(item, validator, events + [anchor], metadata + [{}])
    assert errors


def test_unrelated_invalid_event_remains_fatal_beside_valid_anchor(tmp_path: Path) -> None:
    item, _ = copied_fixture(tmp_path)
    validator = load_validator()
    events, metadata = loaded(item, validator)
    unrelated = {**events[0], "runId": "unrelated-invalid-event", "findingClass": "bad"}
    effective, _, errors = project(item, validator, events + [unrelated, apply_anchor(events[1], str(metadata[1]["sha256"]))], metadata + [{}, {}])
    assert errors == []
    assert any("invalid findingClass" in message for message in validator.validate_work_item(item, ledger_path=item / "agent-runs.jsonl", strict_revise=False, validate_status_file=False))
    assert effective[1]["findingClass"] == "legacy-unclassified"


def test_rendered_error_text_cannot_control_migration_authority(tmp_path: Path) -> None:
    item, _ = copied_fixture(tmp_path)
    validator = load_validator()
    events, metadata = loaded(item, validator)
    target = {**events[1], "findingClass": "correctness", "notes": "invalid findingClass inline-sufficient"}
    _, _, errors = project(item, validator, events[:1] + [target, apply_anchor(target, str(metadata[1]["sha256"]))], metadata + [{}, {}])
    assert errors


def test_stage_apply_is_prefix_preserving_and_rollup_counts_anchor(tmp_path: Path) -> None:
    item, expected, _, before, result = staged_fixture(tmp_path)
    assert result.staged_bytes.startswith(before)
    assert result.staged_bytes[len(before):].count(b"\n") == 1
    assert len(result.staged_bytes) == result.receipt_facts["afterLedgerBytes"]
    assert result.receipt_facts["beforeLedgerSha256"] == sha256(before)
    candidate = item / "candidate.jsonl"
    candidate.write_bytes(result.staged_bytes)
    validator = load_validator()
    errors: list[str] = []
    metadata: list[dict[str, object]] = []
    events = validator.load_jsonl(candidate, errors, metadata)
    effective, counters, projection_errors = validator.project_legacy_obligation_migrations(events, metadata, item)
    assert errors == projection_errors == []
    assert counters == {"raw": 3, "apply": 1, "revoke": 0, "projected": 1}
    assert effective[1]["runId"] == expected["targetRunId"]


def test_stage_apply_rejects_target_and_ledger_digest_drift(tmp_path: Path) -> None:
    item, expected = copied_fixture(tmp_path)
    ledger = load_script(LEDGER, "migration_ledger_drift")
    before = (item / "agent-runs.jsonl").read_bytes()
    cases = (("0" * 64, sha256(before), "WI-LEDGER-MIGRATION-TARGET-DIGEST"),
             (expected["targetRawSha256"], "0" * 64, "WI-LEDGER-MIGRATION-LEDGER-DRIFT"))
    for target_digest, ledger_digest, failure_id in cases:
        with pytest.raises(ledger.LedgerMigrationError) as caught:
            ledger.stage_invalid_finding_class_migration(item, expected["targetRunId"], target_digest, ledger_digest, "migration-op-drift", "2026-08-18T00:00:00Z")
        assert caught.value.failure_id == failure_id


def test_stage_apply_rejects_wrong_version_gate_valid_class_and_controls(tmp_path: Path) -> None:
    ledger = load_script(LEDGER, "migration_ledger_ineligible")
    mutations = (("schemaVersion", 3, "WI-LEDGER-MIGRATION-V3-UNSUPPORTED"),
                 ("gate", "PASS", "WI-LEDGER-MIGRATION-TARGET-INELIGIBLE"),
                 ("findingClass", "correctness", "WI-LEDGER-MIGRATION-DEFECT-CLASS"),
                 ("eventKind", "closure-invalidation", "WI-LEDGER-MIGRATION-TARGET-INELIGIBLE"))
    for index, (key, value, failure_id) in enumerate(mutations):
        item, expected = copied_fixture(tmp_path / str(index))
        lines = (item / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()
        target = json.loads(lines[1]); target[key] = value
        lines[1] = json.dumps(target, separators=(",", ":"))
        data = ("\n".join(lines) + "\n").encode()
        (item / "agent-runs.jsonl").write_bytes(data)
        with pytest.raises(ledger.LedgerMigrationError) as caught:
            ledger.stage_invalid_finding_class_migration(item, expected["targetRunId"], sha256(lines[1].encode()), sha256(data), f"migration-op-{index}", "2026-08-18T00:00:00Z")
        assert caught.value.failure_id == failure_id
    item, expected = copied_fixture(tmp_path / "missing-finding-class")
    lines = (item / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()
    target = json.loads(lines[1]); target.pop("findingClass")
    lines[1] = json.dumps(target, separators=(",", ":"))
    data = ("\n".join(lines) + "\n").encode()
    (item / "agent-runs.jsonl").write_bytes(data)
    with pytest.raises(ledger.LedgerMigrationError) as caught:
        ledger.stage_invalid_finding_class_migration(
            item, expected["targetRunId"], sha256(lines[1].encode()), sha256(data),
            "migration-op-missing-class", "2026-08-18T00:00:00Z",
        )
    assert caught.value.failure_id == "WI-LEDGER-MIGRATION-DEFECT-CLASS"


def test_stage_apply_rejects_duplicate_chain_cycle_and_repeat(tmp_path: Path) -> None:
    item, expected, ledger, _, result = staged_fixture(tmp_path)
    (item / "agent-runs.jsonl").write_bytes(result.staged_bytes)
    with pytest.raises(ledger.LedgerMigrationError) as caught:
        ledger.stage_invalid_finding_class_migration(item, expected["targetRunId"], expected["targetRawSha256"], sha256(result.staged_bytes), "migration-op-002", "2026-08-18T00:00:01Z")
    assert caught.value.failure_id == "WI-LEDGER-MIGRATION-TOPOLOGY"


def test_ordinary_writer_cannot_emit_legacy_unclassified(tmp_path: Path) -> None:
    item, _ = copied_fixture(tmp_path)
    result = run_script(LEDGER, "--work-item", str(item), "append", "--role", "qa-engineer", "--execution-role", "internal", "--status", "revise", "--gate", "REVISE", "--scope", "fixture", "--finding-class", "legacy-unclassified")
    assert result.returncode != 0


def test_caller_cannot_supply_replacement_or_class() -> None:
    ledger = load_script(LEDGER, "migration_ledger_signature")
    parameters = inspect.signature(ledger.stage_invalid_finding_class_migration).parameters
    assert "replacement" not in parameters
    assert "replacement_event" not in parameters
    assert "finding_class" not in parameters


def test_agent_run_ledger_has_no_public_migration_cli() -> None:
    result = run_script(LEDGER, "--help")
    assert result.returncode == 0
    assert "migrate-legacy-ledger-obligation" not in result.stdout
    assert "revoke-legacy-ledger-obligation" not in result.stdout


def test_lifecycle_apply_idempotent_and_operation_conflict(tmp_path: Path) -> None:
    item, expected, lifecycle, _, first = committed_fixture(tmp_path)
    after = (item / "agent-runs.jsonl").read_bytes()
    second = lifecycle.migrate_legacy_ledger_obligation(tmp_path, item.name, expected["targetRunId"], expected["targetRawSha256"], first["beforeLedgerSha256"], "migration-op-001", "2026-08-18T00:00:00Z")
    assert second == first
    assert (item / "agent-runs.jsonl").read_bytes() == after
    receipt = item / "ledger-migration-receipts" / "migration-op-001.json"
    receipt_before = receipt.read_bytes()
    append_reviewer_pass(item, expected)
    after_reviewer = (item / "agent-runs.jsonl").read_bytes()
    later = lifecycle.migrate_legacy_ledger_obligation(tmp_path, item.name, expected["targetRunId"], expected["targetRawSha256"], first["beforeLedgerSha256"], "migration-op-001", "2026-08-18T00:00:00Z")
    assert later == first
    assert receipt.read_bytes() == receipt_before
    assert not list(receipt.parent.glob("*.conflict-*"))
    assert (item / "agent-runs.jsonl").read_bytes() == after_reviewer
    with pytest.raises(lifecycle.LifecycleError):
        lifecycle.migrate_legacy_ledger_obligation(tmp_path, item.name, expected["targetRunId"], expected["targetRawSha256"], first["beforeLedgerSha256"], "migration-op-conflict", "2026-08-18T00:00:00Z")


def test_lifecycle_contention_uses_existing_lock_failure(tmp_path: Path) -> None:
    item, expected = copied_fixture(tmp_path)
    lifecycle = load_script(LIFECYCLE, "migration_lifecycle_lock")
    before = (item / "agent-runs.jsonl").read_bytes()
    class Held:
        def __init__(self, _root): pass
        def __enter__(self): raise lifecycle.LifecycleError("WI-LIFECYCLE-LOCK-HELD", "held")
    with patch.object(lifecycle, "LifecycleTransaction", Held), pytest.raises(lifecycle.LifecycleError) as caught:
        lifecycle.migrate_legacy_ledger_obligation(tmp_path, item.name, expected["targetRunId"], expected["targetRawSha256"], sha256(before), "migration-op-lock", "2026-08-18T00:00:00Z")
    assert caught.value.failure_id == "WI-LIFECYCLE-LOCK-HELD"
    item, expected, lifecycle, _, applied = committed_fixture(tmp_path / "shared-ledger-lock")
    ledger_owner = lifecycle._load_agent_run_ledger()
    ledger_path = item / "agent-runs.jsonl"
    before = ledger_path.read_bytes()
    with ledger_owner.ledger_write_lock(item), patch.object(ledger_owner.time, "sleep", lambda _delay: None):
        with pytest.raises(lifecycle.LifecycleError) as caught:
            lifecycle.revoke_legacy_ledger_obligation(
                tmp_path / "shared-ledger-lock", item.name, applied["anchorRunId"],
                applied["anchorEventSha256"], sha256(before), "locked-revoke",
                "2026-08-18T00:00:03Z",
            )
    assert caught.value.failure_id == "WI-LIFECYCLE-LOCK-HELD"
    assert ledger_path.read_bytes() == before
    appended = run_script(
        LEDGER, "--work-item", str(item), "append", "--run-id", "concurrent-event-001",
        "--role", "analyst", "--execution-role", "internal", "--status", "completed",
        "--gate", "none", "--scope", "concurrent", "--event-kind", "standalone",
        "--started-at", "2026-08-18T00:00:04Z", "--updated-at", "2026-08-18T00:00:04Z",
    )
    assert appended.returncode == 0
    after_append = ledger_path.read_bytes()
    with pytest.raises(lifecycle.LifecycleError) as caught:
        lifecycle.revoke_legacy_ledger_obligation(
            tmp_path / "shared-ledger-lock", item.name, applied["anchorRunId"],
            applied["anchorEventSha256"], sha256(before), "ordered-revoke",
            "2026-08-18T00:00:05Z",
        )
    assert caught.value.failure_id == "WI-LEDGER-MIGRATION-LEDGER-DRIFT"
    assert ledger_path.read_bytes() == after_append
    lifecycle.revoke_legacy_ledger_obligation(
        tmp_path / "shared-ledger-lock", item.name, applied["anchorRunId"],
        applied["anchorEventSha256"], sha256(after_append), "ordered-revoke",
        "2026-08-18T00:00:05Z",
    )
    assert b'"runId":"concurrent-event-001"' in ledger_path.read_bytes()
    assert b'"migrationAction":"revoke"' in ledger_path.read_bytes()


def test_lifecycle_commit_indeterminate_fails_closed(tmp_path: Path) -> None:
    item, expected = copied_fixture(tmp_path)
    lifecycle = load_script(LIFECYCLE, "migration_lifecycle_indeterminate")
    before = (item / "agent-runs.jsonl").read_bytes()
    with pytest.raises(lifecycle.LifecycleError) as caught:
        lifecycle.migrate_legacy_ledger_obligation(tmp_path, item.name, expected["targetRunId"], expected["targetRawSha256"], sha256(before), "migration-op-indeterminate", "2026-08-18T00:00:00Z", inject_failure="post-replace-corrupt")
    assert caught.value.failure_id == "WI-LEDGER-MIGRATION-COMMIT-INDETERMINATE"


def test_crash_after_anchor_before_receipt_recovers_committed(tmp_path: Path) -> None:
    item, expected = copied_fixture(tmp_path)
    lifecycle = load_script(LIFECYCLE, "migration_lifecycle_crash")
    before = (item / "agent-runs.jsonl").read_bytes()
    with pytest.raises(lifecycle.LifecycleError):
        lifecycle.migrate_legacy_ledger_obligation(tmp_path, item.name, expected["targetRunId"], expected["targetRawSha256"], sha256(before), "migration-op-crash", "2026-08-18T00:00:00Z", inject_failure="after-anchor")
    anchored = (item / "agent-runs.jsonl").read_bytes()
    assert anchored.count(b'"eventKind":"legacy-obligation-migration"') == 1
    result = lifecycle.migrate_legacy_ledger_obligation(tmp_path, item.name, expected["targetRunId"], expected["targetRawSha256"], sha256(before), "migration-op-crash", "2026-08-18T00:00:00Z")
    assert result["status"] == "committed"
    assert (item / "agent-runs.jsonl").read_bytes() == anchored
    safe_receipt = item / "ledger-migration-receipts"
    shutil.rmtree(safe_receipt)
    escaped = tmp_path / "escaped-receipts"
    make_directory_link(safe_receipt, escaped)
    with pytest.raises(lifecycle.LifecycleError):
        lifecycle.migrate_legacy_ledger_obligation(tmp_path, item.name, expected["targetRunId"], expected["targetRawSha256"], sha256(before), "migration-op-crash", "2026-08-18T00:00:00Z")
    assert not (escaped / "migration-op-crash.json").exists()


def test_missing_or_conflicting_receipt_reconciles_from_anchor(tmp_path: Path) -> None:
    item, expected, lifecycle, _, result = committed_fixture(tmp_path)
    receipt = item / "ledger-migration-receipts" / "migration-op-001.json"
    receipt.write_text('{"wrong":true}\n', encoding="utf-8")
    replay = lifecycle.migrate_legacy_ledger_obligation(tmp_path, item.name, expected["targetRunId"], expected["targetRawSha256"], result["beforeLedgerSha256"], "migration-op-001", "2026-08-18T00:00:00Z")
    assert json.loads(receipt.read_text(encoding="utf-8")) == replay
    assert list(receipt.parent.glob("migration-op-001.json.conflict-*"))
    bad_item, bad_expected = copied_fixture(tmp_path / "malformed-control")
    raw = (bad_item / "agent-runs.jsonl").read_bytes()
    target = json.loads(raw.decode("utf-8").splitlines()[1])
    malformed = apply_anchor(target, bad_expected["targetRawSha256"], runId="ledger-migration-malformed-op")
    malformed["role"] = "qa-engineer"
    malformed["executionRole"] = "internal"
    malformed.pop("evidence")
    with (bad_item / "agent-runs.jsonl").open("ab") as stream:
        stream.write((json.dumps(malformed, separators=(",", ":")) + "\n").encode())
    before_receipts = list(bad_item.glob("ledger-migration-receipts/*"))
    with pytest.raises(lifecycle.LifecycleError):
        lifecycle.migrate_legacy_ledger_obligation(
            tmp_path / "malformed-control", bad_item.name, bad_expected["targetRunId"],
            bad_expected["targetRawSha256"], sha256(raw), "malformed-op", "2026-08-18T00:00:00Z",
        )
    assert list(bad_item.glob("ledger-migration-receipts/*")) == before_receipts


def test_revoke_before_archive_restores_original_diagnostic(tmp_path: Path) -> None:
    item, _, lifecycle, _, result = committed_fixture(tmp_path)
    ledger_before_revoke = (item / "agent-runs.jsonl").read_bytes()
    revoked = lifecycle.revoke_legacy_ledger_obligation(tmp_path, item.name, result["anchorRunId"], result["anchorEventSha256"], sha256(ledger_before_revoke), "migration-revoke-001", "2026-08-18T00:00:02Z")
    validator = load_validator(); errors: list[str] = []; metadata: list[dict[str, object]] = []
    events = validator.load_jsonl(item / "agent-runs.jsonl", errors, metadata)
    effective, counters, projection_errors = validator.project_legacy_obligation_migrations(events, metadata, item)
    assert errors == projection_errors == []
    assert counters["revoke"] == 1
    assert effective[1]["findingClass"] == "inline-sufficient"
    assert revoked["status"] == "revoked"


def test_revoke_after_transition_is_frozen(tmp_path: Path) -> None:
    item, _, lifecycle, _, result = committed_fixture(tmp_path)
    (item / "lifecycle-transition-receipt.json").write_text('{"status":"intent"}\n', encoding="utf-8")
    data = (item / "agent-runs.jsonl").read_bytes()
    with pytest.raises(lifecycle.LifecycleError) as caught:
        lifecycle.revoke_legacy_ledger_obligation(tmp_path, item.name, result["anchorRunId"], result["anchorEventSha256"], sha256(data), "migration-revoke-frozen", "2026-08-18T00:00:02Z")
    assert caught.value.failure_id == "WI-LEDGER-MIGRATION-REVOCATION-FROZEN"
    pending = transition_fixture(tmp_path / "pending")
    with pytest.raises(pending["lifecycle"].LifecycleError):
        run_transition(pending, inject="T0")
    pending_ledger = pending["item"] / "agent-runs.jsonl"
    pending_before = pending_ledger.read_bytes()
    with pytest.raises(pending["lifecycle"].LifecycleError) as caught:
        pending["lifecycle"].revoke_legacy_ledger_obligation(
            pending["root"], pending["slug"], pending["migration"]["anchorRunId"],
            pending["migration"]["anchorEventSha256"], sha256(pending_before),
            "pending-revoke", "2026-08-18T00:02:30Z",
        )
    assert caught.value.failure_id == "WI-LEDGER-MIGRATION-REVOCATION-FROZEN"
    assert pending_ledger.read_bytes() == pending_before
    settled = transition_fixture(tmp_path / "settled")
    run_transition(settled)
    with pytest.raises(settled["lifecycle"].LifecycleError) as caught:
        settled["lifecycle"].revoke_legacy_ledger_obligation(
            settled["root"], settled["slug"], settled["migration"]["anchorRunId"],
            settled["migration"]["anchorEventSha256"], settled["ledgerSha"],
            "late-revoke", "2026-08-18T00:04:00Z",
        )
    assert caught.value.failure_id == "WI-LEDGER-MIGRATION-REVOCATION-FROZEN"
def test_archive_with_successor_crash_matrix(tmp_path: Path, capsys) -> None:
    for boundary in (f"T{i}" for i in range(10)):
        fixture = transition_fixture(tmp_path / boundary)
        with pytest.raises(fixture["lifecycle"].LifecycleError):
            run_transition(fixture, inject=boundary)
        receipt_at_boundary = fixture["item"] / "bug-dispositions-receipt.json"
        if boundary == "T2":
            assert receipt_at_boundary.is_file()
        if boundary in {"T0", "T1"}:
            assert not receipt_at_boundary.exists()
        fresh = load_script(LIFECYCLE, f"transition_recovery_{boundary}")
        fixture["lifecycle"] = fresh
        if boundary in {"T0", "T1", "T2"}:
            fresh._recover_all_transitions(fixture["root"])
            assert fixture["item"].is_dir()
            assert not (fixture["root"] / "work-items" / "backlog" / f"{fixture['successorSlug']}.md").exists()
        result = run_transition(fixture)
        assert result["status"] == "settled"
        archive = fixture["root"] / "work-items" / "archive" / "2026-08" / fixture["slug"]
        successor = fixture["root"] / "work-items" / "backlog" / f"{fixture['successorSlug']}.md"
        assert archive.is_dir() and successor.is_file()
    print("10/10 boundaries converged")
    assert "10/10 boundaries converged" in capsys.readouterr().out
    print("10/10 boundaries converged")


def test_archive_successor_order_and_exact_settled_receipt(tmp_path: Path) -> None:
    fixture = transition_fixture(tmp_path)
    result = run_transition(fixture)
    archive = tmp_path / "work-items" / "archive" / "2026-08" / fixture["slug"]
    receipt = json.loads((archive / "lifecycle-transition-receipt.json").read_text(encoding="utf-8"))
    assert result == receipt
    assert receipt["archivePath"].startswith("work-items/archive/")
    assert receipt["successorPath"].startswith("work-items/backlog/")
    assert receipt["successorSha256"] == sha256(fixture["successor"])


def test_transition_intent_corruption_fails_closed(tmp_path: Path) -> None:
    fixture = transition_fixture(tmp_path)
    intent = tmp_path / ".scratch" / "work-items-lifecycle-transitions" / "transition-op-001.json"
    intent.parent.mkdir(parents=True); intent.write_text('{"broken":true}\n', encoding="utf-8")
    with pytest.raises(fixture["lifecycle"].LifecycleError) as caught:
        fixture["lifecycle"].audit(tmp_path)
    assert caught.value.failure_id == "WI-LIFECYCLE-TRANSITION-INTENT-INVALID"
    linked = transition_fixture(tmp_path / "linked")
    staging = linked["root"] / ".scratch" / "work-items-lifecycle-transitions"
    escaped = linked["root"] / "escaped-intents"
    make_directory_link(staging, escaped)
    with pytest.raises(linked["lifecycle"].LifecycleError):
        run_transition(linked, inject="T0")
    assert not (escaped / "transition-op-001.json").exists()
    for name, link_path in (
        ("archive", lambda f: f["root"] / "work-items" / "archive" / "2026-08"),
        ("backlog", lambda f: f["root"] / "work-items" / "backlog"),
    ):
        fixture = transition_fixture(tmp_path / f"linked-{name}")
        link = link_path(fixture)
        if link.exists():
            shutil.rmtree(link)
        escaped_output = fixture["root"] / f"escaped-{name}"
        make_directory_link(link, escaped_output)
        with pytest.raises(fixture["lifecycle"].LifecycleError):
            run_transition(fixture)
        assert not any(escaped_output.iterdir())


def test_prearchive_before_image_restore_indeterminate_fails_closed(tmp_path: Path) -> None:
    fixture = transition_fixture(tmp_path)
    with pytest.raises(fixture["lifecycle"].LifecycleError):
        run_transition(fixture, inject="T1")
    (fixture["item"] / "status.md").write_text("external drift\n", encoding="utf-8")
    result = run_script(
        LIFECYCLE,
        "recover-transition",
        "--root", str(tmp_path),
        "--operation-id", fixture["operationId"],
        "--apply",
    )
    assert result.returncode == 1
    assert "WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE" in result.stdout


def test_postarchive_rollforward_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    fixture = transition_fixture(tmp_path)
    with pytest.raises(fixture["lifecycle"].LifecycleError):
        run_transition(fixture, inject="T4")
    successor = tmp_path / "work-items" / "backlog" / f"{fixture['successorSlug']}.md"
    successor.write_text("drift\n", encoding="utf-8")
    result = run_script(
        LIFECYCLE,
        "recover-transition",
        "--root", str(tmp_path),
        "--operation-id", fixture["operationId"],
        "--apply",
    )
    assert result.returncode == 1
    assert "WI-LIFECYCLE-TRANSITION-ROLLFORWARD-INDETERMINATE" in result.stdout


def test_settled_receipt_mismatch_is_fatal(tmp_path: Path) -> None:
    fixture = transition_fixture(tmp_path)
    run_transition(fixture)
    receipt = tmp_path / "work-items" / "archive" / "2026-08" / fixture["slug"] / "lifecycle-transition-receipt.json"
    payload = json.loads(receipt.read_text(encoding="utf-8")); payload["readmeSha256"] = "0" * 64
    receipt.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(fixture["lifecycle"].LifecycleError) as caught:
        run_transition(fixture)
    assert caught.value.failure_id == "WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH"


def test_audit_requires_explicit_recovery_before_membership(tmp_path: Path) -> None:
    fixture = transition_fixture(tmp_path)
    with pytest.raises(fixture["lifecycle"].LifecycleError):
        run_transition(fixture, inject="T3")

    def tree_state() -> tuple[dict[str, bytes], tuple[str, ...]]:
        files = {
            path.relative_to(tmp_path).as_posix(): path.read_bytes()
            for path in tmp_path.rglob("*")
            if path.is_file()
        }
        directories = tuple(
            sorted(
                path.relative_to(tmp_path).as_posix()
                for path in tmp_path.rglob("*")
                if path.is_dir()
            )
        )
        return files, directories

    before = tree_state()
    with pytest.raises(fixture["lifecycle"].LifecycleError) as caught:
        fixture["lifecycle"].audit(tmp_path)
    assert caught.value.failure_id == "WI-LIFECYCLE-TRANSITION-RECOVERY-REQUIRED"
    assert str(caught.value) == (
        "pending lifecycle transition(s): transition-op-001; run: "
        "recover-transition --root <repo> --operation-id transition-op-001 --apply"
    )
    assert tree_state() == before

    for args in (
        (
            "recover-transition", "--root", str(tmp_path),
            "--operation-id", fixture["operationId"],
        ),
        (
            "recover-transition", "--root", str(tmp_path),
            "--operation-id", "wrong-transition-operation", "--apply",
        ),
    ):
        result = run_script(LIFECYCLE, *args)
        assert result.returncode == 1
        assert tree_state() == before

    recovered = run_script(
        LIFECYCLE,
        "recover-transition",
        "--root", str(tmp_path),
        "--operation-id", fixture["operationId"],
        "--apply",
    )
    assert recovered.returncode == 0, recovered.stdout
    assert "outcome=settled" in recovered.stdout
    assert "next=audit" in recovered.stdout
    assert not fixture["item"].exists()
    assert (tmp_path / "work-items" / "archive" / "2026-08" / fixture["slug"] / "lifecycle-transition-receipt.json").is_file()
    fixture["lifecycle"].audit(tmp_path)


def test_recover_transition_cli_rolls_back_exact_precommit_intent(tmp_path: Path) -> None:
    fixture = transition_fixture(tmp_path)
    with pytest.raises(fixture["lifecycle"].LifecycleError):
        run_transition(fixture, inject="T0")
    with pytest.raises(fixture["lifecycle"].LifecycleError) as pending:
        fixture["lifecycle"].audit(tmp_path)
    assert pending.value.failure_id == "WI-LIFECYCLE-TRANSITION-RECOVERY-REQUIRED"

    recovered = run_script(
        LIFECYCLE,
        "recover-transition",
        "--root", str(tmp_path),
        "--operation-id", fixture["operationId"],
        "--apply",
    )

    assert recovered.returncode == 0, recovered.stdout
    assert "outcome=rolled-back" in recovered.stdout
    assert "next=audit" in recovered.stdout
    assert fixture["item"].is_dir()
    assert not (
        tmp_path
        / ".scratch"
        / "work-items-lifecycle-transitions"
        / f"{fixture['operationId']}.json"
    ).exists()
    with pytest.raises(fixture["lifecycle"].LifecycleError) as after_recovery:
        fixture["lifecycle"].audit(tmp_path)
    assert after_recovery.value.failure_id == "WI-BUG-DISPOSITIONS-PENDING"


def test_recover_transition_rejects_intent_operation_mismatch_without_mutation(
    tmp_path: Path,
) -> None:
    fixture = transition_fixture(tmp_path)
    with pytest.raises(fixture["lifecycle"].LifecycleError):
        run_transition(fixture, inject="T3")
    intent_path = (
        tmp_path
        / ".scratch"
        / "work-items-lifecycle-transitions"
        / f"{fixture['operationId']}.json"
    )
    intent = json.loads(intent_path.read_bytes())
    intent["operationId"] = "different-transition-operation"
    intent_path.write_text(
        json.dumps(intent, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    before = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    recovered = run_script(
        LIFECYCLE,
        "recover-transition",
        "--root", str(tmp_path),
        "--operation-id", fixture["operationId"],
        "--apply",
    )

    assert recovered.returncode == 1
    assert "WI-LIFECYCLE-TRANSITION-INTENT-INVALID" in recovered.stdout
    assert {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    } == before


def test_archive_with_successor_replay_is_idempotent_and_hash_bound(tmp_path: Path) -> None:
    fixture = transition_fixture(tmp_path)
    first = run_transition(fixture)
    paths = [path for path in (tmp_path / "work-items").rglob("*") if path.is_file()]
    before = {path.relative_to(tmp_path).as_posix(): sha256(path.read_bytes()) for path in paths}
    second = run_transition(fixture)
    after = {path.relative_to(tmp_path).as_posix(): sha256(path.read_bytes()) for path in paths}
    assert first == second
    assert before == after
    changed_closure = fixture["closure"].replace(b"Outcome: Migrated", b"Outcome: Different")
    changed_time = "2026-08-18T00:03:01Z"
    changed_time_closure = fixture["closure"].replace(fixture["instant"].encode(), changed_time.encode())
    mismatch_cases = (
        {"successor_slug": fixture["successorSlug"] + "-other"},
        {"closure_data": changed_closure},
        {"successor_data": fixture["successor"] + b"changed\n"},
        {"terminal_instant": changed_time, "closure_data": changed_time_closure},
        {"expected_ledger_sha256": "0" * 64},
        {"expected_readme_sha256": "0" * 64},
    )
    base = {
        "root": fixture["root"], "slug": fixture["slug"], "closure_data": fixture["closure"],
        "terminal_instant": fixture["instant"], "successor_slug": fixture["successorSlug"],
        "successor_data": fixture["successor"], "operation_id": fixture["operationId"],
        "expected_ledger_sha256": fixture["ledgerSha"], "expected_readme_sha256": fixture["readmeSha"],
    }
    for overrides in mismatch_cases:
        with pytest.raises(fixture["lifecycle"].LifecycleError) as caught:
            fixture["lifecycle"].archive_with_successor(**{**base, **overrides})
        assert caught.value.failure_id == "WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH"
    assert {path.relative_to(tmp_path).as_posix(): sha256(path.read_bytes()) for path in paths} == before


@pytest.mark.parametrize("transfer", (False, True), ids=("ordinary", "transfer"))
@pytest.mark.parametrize("first_case", ("lower", "upper", "mixed"))
@pytest.mark.parametrize("replay_case", ("lower", "upper", "mixed"))
def test_archive_with_successor_hash_case_matrix_is_canonical_on_first_commit_and_replay(
    tmp_path: Path,
    transfer: bool,
    first_case: str,
    replay_case: str,
) -> None:
    fixture = transfer_fixture(tmp_path) if transfer else transition_fixture(tmp_path)
    runner = run_transfer if transfer else run_transition
    canonical_ledger = fixture["ledgerSha"]
    canonical_readme = fixture["readmeSha"]

    def digest_case(value: str, case: str) -> str:
        if case == "lower":
            return value
        if case == "upper":
            return value.upper()
        letters_seen = 0
        result = []
        for character in value:
            if character.isalpha():
                letters_seen += 1
                character = character.upper() if letters_seen % 2 else character
            result.append(character)
        mixed = "".join(result)
        assert any(character.isupper() for character in mixed)
        assert any(character.islower() for character in mixed)
        return mixed

    fixture["ledgerSha"] = digest_case(canonical_ledger, first_case)
    fixture["readmeSha"] = digest_case(canonical_readme, first_case)
    first = runner(fixture)

    assert first["requestExpectedLedgerSha256"] == canonical_ledger
    assert first["requestExpectedReadmeSha256"] == canonical_readme

    fixture["ledgerSha"] = digest_case(canonical_ledger, replay_case)
    fixture["readmeSha"] = digest_case(canonical_readme, replay_case)
    assert runner(fixture) == first


@pytest.mark.parametrize(
    ("field", "invalid_kind", "first_failure_id"),
    (
        ("ledgerSha", "different", "WI-LEDGER-MIGRATION-LEDGER-DRIFT"),
        ("readmeSha", "different", "WI-README-STALE"),
        ("ledgerSha", "nonhex", "WI-LEDGER-MIGRATION-LEDGER-DRIFT"),
        ("readmeSha", "whitespace", "WI-README-STALE"),
        ("ledgerSha", "unicode-ligature", "WI-LEDGER-MIGRATION-LEDGER-DRIFT"),
        ("readmeSha", "wrong-type", "WI-README-STALE"),
    ),
)
def test_archive_with_successor_hash_case_normalization_preserves_invalid_and_mismatch_refusal(
    tmp_path: Path,
    field: str,
    invalid_kind: str,
    first_failure_id: str,
) -> None:
    def invalid_value(canonical: str) -> object:
        if invalid_kind == "different":
            replacement = "0" if canonical[0] != "0" else "1"
            return replacement + canonical[1:]
        if invalid_kind == "nonhex":
            return "g" * 64
        if invalid_kind == "whitespace":
            return f" {canonical}"
        if invalid_kind == "unicode-ligature":
            return "\ufb00" * 32
        return None

    first_fixture = transition_fixture(tmp_path / "first")
    first_before = {
        path.relative_to(first_fixture["root"]).as_posix(): path.read_bytes()
        for path in first_fixture["root"].rglob("*")
        if path.is_file()
    }
    first_fixture[field] = invalid_value(first_fixture[field])
    with pytest.raises(first_fixture["lifecycle"].LifecycleError) as first_caught:
        run_transition(first_fixture)
    assert first_caught.value.failure_id == first_failure_id
    assert {
        path.relative_to(first_fixture["root"]).as_posix(): path.read_bytes()
        for path in first_fixture["root"].rglob("*")
        if path.is_file()
    } == first_before

    replay_fixture = transition_fixture(tmp_path / "replay")
    run_transition(replay_fixture)
    replay_before = {
        path.relative_to(replay_fixture["root"]).as_posix(): path.read_bytes()
        for path in replay_fixture["root"].rglob("*")
        if path.is_file()
    }
    replay_fixture[field] = invalid_value(replay_fixture[field])
    with pytest.raises(replay_fixture["lifecycle"].LifecycleError) as replay_caught:
        run_transition(replay_fixture)
    assert replay_caught.value.failure_id == "WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH"
    assert {
        path.relative_to(replay_fixture["root"]).as_posix(): path.read_bytes()
        for path in replay_fixture["root"].rglob("*")
        if path.is_file()
    } == replay_before


def test_archive_with_successor_transfer_exactly_once_across_activation_close_and_retransfer(
    tmp_path: Path,
) -> None:
    fixture = transfer_fixture(tmp_path)

    receipt = run_transfer(fixture)

    archive = tmp_path / "work-items" / "archive" / "2026-08" / fixture["slug"]
    successor = tmp_path / "work-items" / "backlog" / f"{fixture['successorSlug']}.md"
    assert receipt["schemaVersion"] == 2
    assert receipt["owner"] == "mutate-work-item:archive-with-successor-v2"
    assert receipt["transferInputSha256"] == sha256(fixture["transfer"])
    assert len(receipt["obligations"]) == 1
    assert receipt["obligations"][0]["runId"] == fixture["transferObject"]["obligations"][0]["runId"]
    assert receipt["obligations"][0]["obligationId"]
    assert receipt["obligations"][0]["predecessorOperationId"] is None
    assert (archive / "agent-runs.jsonl").read_bytes() == fixture["ledgerBefore"]
    assert successor.read_bytes() == fixture["successor"]

    incomplete_status = successor_status(fixture["slug"], fixture["operationId"]).replace(
        f"Obligation-transfer: {fixture['operationId']}\n".encode("utf-8"), b""
    )
    with pytest.raises(fixture["lifecycle"].LifecycleError) as caught:
        fixture["lifecycle"].start_item(
            fixture["root"], fixture["successorSlug"], incomplete_status
        )
    assert caught.value.failure_id == "WI-OBLIGATION-TRANSFER-OWNER"
    assert successor.is_file()

    active_successor = fixture["lifecycle"].start_item(
        fixture["root"],
        fixture["successorSlug"],
        successor_status(fixture["slug"], fixture["operationId"]),
    )
    states: list[object] = []
    errors = load_validator().validate_work_item(
        active_successor, strict_revise=False, obligation_state_out=states
    )
    assert errors == []
    assert len(states) == 1
    assert [row.run_id for row in states[0].open_revise] == [
        fixture["transferObject"]["obligations"][0]["runId"]
    ]
    assert [row.obligation_id for row in states[0].open_revise] == [
        receipt["obligations"][0]["obligationId"]
    ]

    second_operation = "transition-transfer-op-002"
    second_successor_slug = f"{fixture['successorSlug']}-next"
    second_inherited = states[0].open_revise[0]
    second_transfer = json.dumps({
        "schemaVersion": 1,
        "sourceWorkItem": fixture["successorSlug"],
        "successorWorkItem": second_successor_slug,
        "expectedSourceLedgerSha256": sha256((active_successor / "agent-runs.jsonl").read_bytes()),
        "obligations": [{
            "runId": second_inherited.run_id,
            "rawLineOrdinal": second_inherited.raw_line_ordinal,
            "rawLineSha256": second_inherited.raw_line_sha256,
            "rawEventSha256": second_inherited.raw_event_sha256,
            "projectedEventSha256": second_inherited.projected_event_sha256,
        }],
    }, sort_keys=True).encode("utf-8")
    second_instant = "2026-08-18T00:05:00Z"
    (active_successor / "bug-dispositions.json").write_text(json.dumps({
        "schemaVersion": 1,
        "workItem": fixture["successorSlug"],
        "closedAt": second_instant,
        "bugs": [],
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    fixture["lifecycle"].refresh_readme(fixture["root"])
    second_ledger_sha = sha256((active_successor / "agent-runs.jsonl").read_bytes())
    second_readme_sha = sha256((fixture["root"] / "work-items" / "README.md").read_bytes())
    second_successor = (
        "Task: Continue the inherited obligation once more.\n"
        f"Continues: {fixture['successorSlug']}\n"
        f"Obligation-transfer: {second_operation}\n"
        "Next action: Resolve the inherited review finding.\n"
        f"updated: {second_instant}\n"
    ).encode("utf-8")
    second_closure = (
        f"Closed: {second_instant}\n"
        "Outcome: Re-transferred the unresolved obligation.\n"
        "Evidence: focused re-transfer integration test\n"
        "Residual risk: None in fixture.\n"
    ).encode("utf-8")

    second_receipt = fixture["lifecycle"].archive_with_successor(
        fixture["root"], fixture["successorSlug"], second_closure, second_instant,
        second_successor_slug, second_successor, second_operation,
        second_ledger_sha, second_readme_sha,
        obligation_transfer_data=second_transfer,
    )

    assert second_receipt["obligations"][0]["obligationId"] == receipt["obligations"][0]["obligationId"]
    assert second_receipt["obligations"][0]["predecessorOperationId"] == fixture["operationId"]
    assert fixture["transferObject"]["obligations"][0]["runId"].encode("utf-8") not in (
        fixture["root"] / "work-items" / "archive" / "2026-08" /
        fixture["successorSlug"] / "agent-runs.jsonl"
    ).read_bytes()
    fixture["lifecycle"].audit(fixture["root"])

    close_fixture = transfer_fixture(tmp_path / "close")
    close_receipt = run_transfer(close_fixture)
    close_active = close_fixture["lifecycle"].start_item(
        close_fixture["root"],
        close_fixture["successorSlug"],
        successor_status(close_fixture["slug"], close_fixture["operationId"]),
    )
    append_successor_closer(
        close_active, close_receipt["obligations"][0]["runId"]
    )
    close_instant = "2026-08-18T00:06:00Z"
    (close_active / "bug-dispositions.json").write_text(json.dumps({
        "schemaVersion": 1,
        "workItem": close_fixture["successorSlug"],
        "closedAt": close_instant,
        "bugs": [],
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    close_fixture["lifecycle"].refresh_readme(close_fixture["root"])
    closed = close_fixture["lifecycle"].close_item(
        close_fixture["root"],
        close_fixture["successorSlug"],
        (
            f"Closed: {close_instant}\n"
            "Outcome: Closed the inherited obligation.\n"
            "Evidence: focused successor close test\n"
            "Residual risk: None in fixture.\n"
        ).encode("utf-8"),
        close_instant,
    )
    assert closed.is_dir()
    successor_events = [
        json.loads(line)
        for line in (closed / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert all(
        event.get("runId") != close_receipt["obligations"][0]["runId"]
        for event in successor_events
    )
    close_fixture["lifecycle"].audit(close_fixture["root"])


def test_transfer_endpoint_relation_is_required_before_successor_start(
    tmp_path: Path,
) -> None:
    fixture = transfer_fixture(tmp_path)
    run_transfer(fixture)
    backlog = (
        fixture["root"]
        / "work-items"
        / "backlog"
        / f"{fixture['successorSlug']}.md"
    )
    relationless_backlog = without_transfer_relations(backlog.read_bytes())
    backlog.write_bytes(relationless_backlog)
    fixture["lifecycle"].refresh_readme(fixture["root"])

    errors = load_validator().validate_obligation_transfer_ownership(
        fixture["root"]
    )
    assert any(
        error.startswith("WI-OBLIGATION-TRANSFER-OWNER:")
        and "current owner relation differs" in error
        for error in errors
    )
    try:
        fixture["lifecycle"].start_item(
            fixture["root"],
            fixture["successorSlug"],
            without_transfer_relations(
                successor_status(fixture["slug"], fixture["operationId"])
            ),
        )
    except fixture["lifecycle"].LifecycleError as exc:
        assert exc.failure_id == "WI-OBLIGATION-TRANSFER-OWNER"
    else:
        raise AssertionError("relationless transfer successor was started")
    assert backlog.read_bytes() == relationless_backlog
    assert not (
        fixture["root"] / "work-items" / "active" / fixture["successorSlug"]
    ).exists()


def test_transfer_receipt_leaf_link_is_rejected_before_authority_read(
    tmp_path: Path,
) -> None:
    fixture = transfer_fixture(tmp_path)
    receipt = run_transfer(fixture)
    archive = fixture["root"].joinpath(*receipt["archivePath"].split("/"))
    receipt_path = archive / "lifecycle-transition-receipt.json"
    receipt_bytes = receipt_path.read_bytes()
    external = fixture["root"] / "outside-physical-archive" / "receipt.json"
    external.parent.mkdir()
    external.write_bytes(receipt_bytes)
    receipt_path.unlink()
    try:
        receipt_path.symlink_to(external)
    except OSError as exc:
        receipt_path.write_bytes(receipt_bytes)
        pytest.skip(f"target environment cannot create a file link: {exc}")

    errors = load_validator().validate_obligation_transfer_ownership(
        fixture["root"]
    )

    assert any(
        error.startswith("WI-OBLIGATION-TRANSFER-OWNER:")
        and "link or reparse point" in error
        for error in errors
    )
    receipt_path.unlink()
    assert external.read_bytes() == receipt_bytes


def test_archive_with_successor_transfer_rejects_coverage_owner_and_drift_matrix_without_mutation(
    tmp_path: Path,
) -> None:
    cases = (
        ("missing", "WI-OBLIGATION-TRANSFER-COVERAGE"),
        ("duplicate", "WI-OBLIGATION-TRANSFER-COVERAGE"),
        ("raw-drift", "WI-OBLIGATION-TRANSFER-DRIFT"),
        ("projected-drift", "WI-OBLIGATION-TRANSFER-DRIFT"),
    )
    for name, expected_failure in cases:
        fixture = transfer_fixture(tmp_path / name)
        payload = json.loads(fixture["transfer"])
        if name == "missing":
            payload["obligations"] = []
        elif name == "duplicate":
            payload["obligations"].append(dict(payload["obligations"][0]))
        elif name == "raw-drift":
            payload["obligations"][0]["rawEventSha256"] = "0" * 64
        else:
            payload["obligations"][0]["projectedEventSha256"] = "0" * 64
        fixture["transfer"] = json.dumps(payload, sort_keys=True).encode("utf-8")
        before = {
            path.relative_to(fixture["root"]).as_posix(): sha256(path.read_bytes())
            for path in (fixture["root"] / "work-items").rglob("*")
            if path.is_file()
        }

        with pytest.raises(fixture["lifecycle"].LifecycleError) as caught:
            run_transfer(fixture)

        after = {
            path.relative_to(fixture["root"]).as_posix(): sha256(path.read_bytes())
            for path in (fixture["root"] / "work-items").rglob("*")
            if path.is_file()
        }
        assert caught.value.failure_id == expected_failure
        assert after == before

    terminal = transfer_fixture(tmp_path / "terminal-owner")
    terminal_receipt = run_transfer(terminal)
    terminal_backlog = (
        terminal["root"] / "work-items" / "backlog" / f"{terminal['successorSlug']}.md"
    )
    terminal_owner = (
        terminal["root"] / "work-items" / "archive" / "2026-08" /
        terminal["successorSlug"]
    )
    terminal_owner.mkdir(parents=True)
    shutil.move(str(terminal_backlog), str(terminal_owner / "admission.md"))
    (terminal_owner / "status.md").write_bytes(
        successor_status(terminal["slug"], terminal["operationId"])
    )
    terminal_errors = load_validator().validate_obligation_transfer_ownership(
        terminal["root"]
    )
    assert any(
        "WI-OBLIGATION-TRANSFER-OWNER" in error and "terminal owner" in error
        for error in terminal_errors
    )

    def add_fabricated_receipt(
        fixture: dict,
        base_receipt: dict,
        operation_id: str,
        predecessor_operation_id: str,
        successor_slug: str,
    ) -> None:
        validator = load_validator()
        archive = (
            fixture["root"] / "work-items" / "archive" / "2026-09" / operation_id
        )
        archive.mkdir(parents=True)
        ledger_bytes = b'{"fixture":"transfer-owner"}\n'
        (archive / "agent-runs.jsonl").write_bytes(ledger_bytes)
        archive_relative = archive.relative_to(fixture["root"]).as_posix()
        row = dict(base_receipt["obligations"][0])
        row["predecessorOperationId"] = predecessor_operation_id
        payload = {
            **base_receipt,
            "operationId": operation_id,
            "workItem": fixture["successorSlug"],
            "requestSuccessorSlug": successor_slug,
            "successorPath": f"work-items/backlog/{successor_slug}.md",
            "archivePath": archive_relative,
            "ledgerSha256": sha256(ledger_bytes),
            "archiveIdentity": validator.archived_ledger_identity(
                archive_relative, sha256(ledger_bytes)
            ),
            "predecessorOperationId": predecessor_operation_id,
            "obligations": [row],
        }
        (archive / "lifecycle-transition-receipt.json").write_text(
            json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8"
        )

    branch = transfer_fixture(tmp_path / "branch")
    branch_receipt = run_transfer(branch)
    add_fabricated_receipt(
        branch, branch_receipt, "branch-op-a", branch["operationId"], "branch-a"
    )
    add_fabricated_receipt(
        branch, branch_receipt, "branch-op-b", branch["operationId"], "branch-b"
    )
    branch_errors = load_validator().validate_obligation_transfer_ownership(branch["root"])
    assert any("WI-OBLIGATION-TRANSFER-OWNER" in error and "branches" in error for error in branch_errors)

    duplicate = transfer_fixture(tmp_path / "duplicate-owner")
    run_transfer(duplicate)
    duplicate_path = (
        duplicate["root"] / "work-items" / "archive" / "2026-08" /
        duplicate["slug"] / "lifecycle-transition-receipt.json"
    )
    duplicate_payload = json.loads(duplicate_path.read_text(encoding="utf-8"))
    duplicate_payload["obligations"].append(dict(duplicate_payload["obligations"][0]))
    duplicate_path.write_text(json.dumps(duplicate_payload, sort_keys=True) + "\n", encoding="utf-8")
    duplicate_errors = load_validator().validate_obligation_transfer_ownership(duplicate["root"])
    assert any("WI-OBLIGATION-TRANSFER-OWNER" in error and "duplicate" in error for error in duplicate_errors)

    cycle = transfer_fixture(tmp_path / "cycle")
    cycle_receipt = run_transfer(cycle)
    add_fabricated_receipt(cycle, cycle_receipt, "cycle-op-a", "cycle-op-b", "cycle-a")
    add_fabricated_receipt(cycle, cycle_receipt, "cycle-op-b", "cycle-op-a", "cycle-b")
    cycle_errors = load_validator().validate_obligation_transfer_ownership(cycle["root"])
    assert any("WI-OBLIGATION-TRANSFER-OWNER" in error and "cycle" in error for error in cycle_errors)


def test_archive_with_successor_transfer_preserves_ledger_bytes_crash_recovery_and_replay(
    tmp_path: Path,
) -> None:
    for boundary in (f"T{index}" for index in range(10)):
        fixture = transfer_fixture(tmp_path / boundary)
        with pytest.raises(fixture["lifecycle"].LifecycleError):
            run_transfer(fixture, inject=boundary)
        fresh = load_script(LIFECYCLE, f"transfer_recovery_{boundary}")
        fixture["lifecycle"] = fresh
        if boundary in {"T0", "T1", "T2"}:
            fresh._recover_all_transitions(fixture["root"])
            assert fixture["item"].is_dir()
        first = run_transfer(fixture)
        archive = (
            fixture["root"] / "work-items" / "archive" / "2026-08" / fixture["slug"]
        )
        assert (archive / "agent-runs.jsonl").read_bytes() == fixture["ledgerBefore"]
        before = {
            path.relative_to(fixture["root"]).as_posix(): sha256(path.read_bytes())
            for path in (fixture["root"] / "work-items").rglob("*")
            if path.is_file()
        }
        second = run_transfer(fixture)
        after = {
            path.relative_to(fixture["root"]).as_posix(): sha256(path.read_bytes())
            for path in (fixture["root"] / "work-items").rglob("*")
            if path.is_file()
        }
        assert second == first
        assert after == before

        changed = dict(json.loads(fixture["transfer"]))
        changed["obligations"] = []
        fixture["transfer"] = json.dumps(changed, sort_keys=True).encode("utf-8")
        with pytest.raises(fresh.LifecycleError) as caught:
            run_transfer(fixture)
        assert caught.value.failure_id == "WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH"


def test_archive_with_successor_binds_exact_two_migration_receipts_and_replays(
    tmp_path: Path,
) -> None:
    fixture = two_migration_transfer_fixture(tmp_path)

    receipt = run_transfer(fixture)
    replay = run_transfer(fixture)

    assert receipt["migrationReceipts"] == fixture["migrationReceipts"]
    assert "migrationReceiptSha256" not in receipt
    assert replay == receipt
    archive = tmp_path / "work-items" / "archive" / "2026-08" / fixture["slug"]
    assert sorted(
        path.name
        for path in (archive / "ledger-migration-receipts").glob("*.json")
    ) == ["migration-op-001.json", "migration-op-002.json"]


@pytest.mark.parametrize(
    "case",
    ("missing", "extra", "duplicate-target", "content-drift"),
)
def test_archive_with_successor_rejects_nonexact_migration_receipt_set_before_intent(
    tmp_path: Path,
    case: str,
) -> None:
    fixture = two_migration_transfer_fixture(tmp_path)
    receipt_root = fixture["item"] / "ledger-migration-receipts"
    receipts = sorted(receipt_root.glob("*.json"))
    if case == "missing":
        receipts[0].unlink()
    elif case == "extra":
        (receipt_root / "extra.json").write_bytes(receipts[0].read_bytes())
    else:
        payload = json.loads(receipts[1].read_bytes())
        if case == "duplicate-target":
            first = json.loads(receipts[0].read_bytes())
            payload["targetRunId"] = first["targetRunId"]
            payload["replacementEventSha256"] = first["replacementEventSha256"]
        else:
            payload["recordedAt"] = "2026-08-18T00:00:02Z"
        receipts[1].write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    before = {
        path.relative_to(fixture["root"]).as_posix(): sha256(path.read_bytes())
        for path in (fixture["root"] / "work-items").rglob("*")
        if path.is_file()
    }

    with pytest.raises(fixture["lifecycle"].LifecycleError) as rejected:
        run_transfer(fixture)

    after = {
        path.relative_to(fixture["root"]).as_posix(): sha256(path.read_bytes())
        for path in (fixture["root"] / "work-items").rglob("*")
        if path.is_file()
    }
    assert rejected.value.failure_id == "WI-LEDGER-MIGRATION-RECEIPT-MISMATCH"
    assert after == before
    assert not (
        fixture["root"]
        / ".scratch"
        / "work-items-lifecycle-transitions"
        / f"{fixture['operationId']}.json"
    ).exists()


def test_archive_with_successor_replays_exact_legacy_singular_transfer_receipt(
    tmp_path: Path,
) -> None:
    fixture = transfer_fixture(tmp_path)
    current = run_transfer(fixture)
    receipt_path = (
        fixture["root"]
        / "work-items"
        / "archive"
        / "2026-08"
        / fixture["slug"]
        / "lifecycle-transition-receipt.json"
    )
    migration_rows = current.pop("migrationReceipts")
    assert len(migration_rows) == 1
    current["migrationReceiptSha256"] = migration_rows[0]["sha256"]
    legacy_bytes = (
        json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    receipt_path.write_bytes(legacy_bytes)

    replay = run_transfer(fixture)

    assert replay == current
    assert receipt_path.read_bytes() == legacy_bytes


def test_archive_with_successor_transfer_accepts_zero_migration_receipts_for_native_open_revise(
    tmp_path: Path,
) -> None:
    fixture = native_transfer_fixture(tmp_path)

    receipt = run_transfer(fixture)

    assert receipt["schemaVersion"] == 2
    assert receipt["migrationReceipts"] == []
    assert "migrationReceiptSha256" not in receipt
    assert len(receipt["obligations"]) == 1
    archive = tmp_path / "work-items" / "archive" / "2026-08" / fixture["slug"]
    assert not (archive / "ledger-migration-receipts").exists()
    assert (archive / "agent-runs.jsonl").read_bytes() == fixture["ledgerBefore"]


def test_archive_with_successor_transfer_cli_binds_optional_input_file(tmp_path: Path) -> None:
    fixture = native_transfer_fixture(tmp_path)
    closure_file = tmp_path / "closure-transfer.md"
    successor_file = tmp_path / "successor-transfer.md"
    transfer_file = tmp_path / "obligation-transfer.json"
    closure_file.write_bytes(fixture["closure"])
    successor_file.write_bytes(fixture["successor"])
    transfer_file.write_bytes(fixture["transfer"])

    result = run_script(
        LIFECYCLE,
        "archive-with-successor",
        "--root", str(tmp_path),
        "--slug", fixture["slug"],
        "--closure-file", str(closure_file),
        "--terminal-instant", fixture["instant"],
        "--successor-slug", fixture["successorSlug"],
        "--successor-file", str(successor_file),
        "--operation-id", fixture["operationId"],
        "--expected-ledger-sha256", fixture["ledgerSha"],
        "--expected-readme-sha256", fixture["readmeSha"],
        "--obligation-transfer-file", str(transfer_file),
    )

    assert result.returncode == 0, result.stdout
    assert "WI-LIFECYCLE-TRANSITION-COMMITTED" in result.stdout
    receipt_path = (
        tmp_path / "work-items" / "archive" / "2026-08" / fixture["slug"] /
        "lifecycle-transition-receipt.json"
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["transferInputSha256"] == sha256(fixture["transfer"])
def test_checker_enforces_migration_schema_runbook_fixture_and_pointer_parity(tmp_path: Path) -> None:
    checker = load_script(
        ROOT / "scripts" / "check-agent-run-ledger-contract.py",
        "migration_contract_checker",
    )
    telemetry = checker.check_legacy_migration_contract(ROOT)
    assert telemetry["fixture-target-bytes"] == 704
    assert telemetry["fixture-target-digest"] == 1
    assert telemetry["canonical-command-blocks"] == 3
    assert telemetry["failure-ids"] >= 16

    copied = (
        "shared/schemas/agent-runs.schema.json",
        "scripts/validate-work-item-state.py",
        "scripts/agent-run-ledger.py",
        "scripts/mutate-work-item.py",
        "docs/work-item-execution-tracking.md",
        "README.md",
        "INSTALL.md",
        "shared/references/subagent-operating-model.md",
        "tests/fixtures/legacy-obligation-migration/baseline.json",
        "tests/fixtures/agent-run-ledger/legacy-obligation-migration-v2/agent-runs.jsonl",
        "tests/fixtures/agent-run-ledger/legacy-obligation-migration-v2/expected.json",
    )
    for relative in copied:
        source = ROOT / relative
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    checker.check_legacy_migration_contract(tmp_path)
    runbook = tmp_path / "docs" / "work-item-execution-tracking.md"
    original = runbook.read_bytes()
    runbook.write_bytes(
        original
        + b"\n```powershell\npython scripts/mutate-work-item.py migrate-legacy-ledger-obligation\n```\n"
    )
    with pytest.raises(AssertionError, match="exactly one"):
        checker.check_legacy_migration_contract(tmp_path)
    runbook.write_bytes(original)

    ledger = (
        tmp_path
        / "tests"
        / "fixtures"
        / "agent-run-ledger"
        / "legacy-obligation-migration-v2"
        / "agent-runs.jsonl"
    )
    raw = ledger.read_bytes()
    ledger.write_bytes(raw.replace(b'"inline-sufficient"', b'"inline-sufficienx"', 1))
    with pytest.raises(AssertionError, match="digest"):
        checker.check_legacy_migration_contract(tmp_path)


def test_rollup_exposes_raw_and_effective_migration_counts(tmp_path: Path) -> None:
    checker = load_script(
        ROOT / "scripts" / "check-agent-run-ledger-contract.py",
        "migration_telemetry_checker",
    )
    telemetry = checker.check_legacy_migration_contract(ROOT)
    assert telemetry["apply-accepted"] == 1
    assert telemetry["apply-refused"] >= 1
    assert telemetry["apply-idempotent"] == 1
    assert telemetry["apply-revoked"] == 1
    assert telemetry["projected-events"] == 1

    item, _, lifecycle, _, applied = committed_fixture(tmp_path)
    validator = load_validator()
    counters: dict[str, int] = {}
    assert validator.validate_work_item(
        item,
        strict_revise=False,
        telemetry=counters,
    ) == []
    assert counters["ledger-migration-raw"] == 3
    assert counters["ledger-migration-apply"] == 1
    assert counters["ledger-migration-revoke"] == 0
    assert counters["ledger-migration-projected"] == 1

    errors: list[str] = []
    metadata: list[dict[str, object]] = []
    events = validator.load_jsonl(item / "agent-runs.jsonl", errors, metadata)
    effective, projection, projection_errors = validator.project_legacy_obligation_migrations(
        events, metadata, item
    )
    assert errors == projection_errors == []
    assert projection == {"raw": 3, "apply": 1, "revoke": 0, "projected": 1}
    assert sum(event.get("findingClass") == "legacy-unclassified" for event in effective) == 1
    assert sum(event.get("findingClass") == "security" for event in effective) == 0

    ledger_path = item / "agent-runs.jsonl"
    before_revoke = ledger_path.read_bytes()
    lifecycle.revoke_legacy_ledger_obligation(
        tmp_path,
        item.name,
        applied["anchorRunId"],
        applied["anchorEventSha256"],
        sha256(before_revoke),
        "migration-revoke-telemetry",
        "2026-08-18T00:00:03Z",
    )
    revoked_telemetry: dict[str, int] = {}
    validator.validate_work_item(
        item,
        strict_revise=False,
        telemetry=revoked_telemetry,
    )
    assert revoked_telemetry["ledger-migration-raw"] == 4
    assert revoked_telemetry["ledger-migration-apply"] == 1
    assert revoked_telemetry["ledger-migration-revoke"] == 1
    assert revoked_telemetry["ledger-migration-projected"] == 0


def test_path_scoped_diff_guard_excludes_protected_surfaces(tmp_path: Path) -> None:
    checker = load_script(
        ROOT / "scripts" / "check-agent-run-ledger-contract.py",
        "migration_diff_guard_checker",
    )
    telemetry = checker.check_legacy_migration_diff_guard(ROOT)
    assert telemetry == {
        "baseline-manifest": 1,
        "protected-hashes": 1,
        "fixture-files": 4,
        "migration-specific-paths": 6,
    }

    copied_files = (
        "tests/fixtures/legacy-obligation-migration/baseline.json",
        "README.md",
        "INSTALL.md",
        "docs/work-item-execution-tracking.md",
        "shared/references/subagent-operating-model.md",
        "shared/schemas/agent-runs.schema.json",
        "scripts/agent-run-ledger.py",
        "scripts/check-work-items-state.py",
        "scripts/mutate-work-item.py",
        "scripts/solution_attempt/reducer.py",
        "scripts/universal-hooks/scripts/workitem_sentinels.py",
        "scripts/validate-work-item-state.py",
        "tests/test_agent_run_ledger.py",
        "tests/test_legacy_obligation_migration.py",
    )
    for relative in copied_files:
        source = ROOT / relative
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for fixture_name in ("closure-invalidation-v2", "legacy-obligation-migration-v2"):
        shutil.copytree(
            ROOT / "tests" / "fixtures" / "agent-run-ledger" / fixture_name,
            tmp_path / "tests" / "fixtures" / "agent-run-ledger" / fixture_name,
        )

    protected = tmp_path / "tests" / "test_agent_run_ledger.py"
    protected.write_bytes(protected.read_bytes() + b"\n# injected protected drift\n")
    result = run_script(
        ROOT / "scripts" / "check-agent-run-ledger-contract.py",
        "--root",
        str(tmp_path),
    )
    assert result.returncode != 0, result.stdout
    assert "protected migration sibling" in result.stdout
