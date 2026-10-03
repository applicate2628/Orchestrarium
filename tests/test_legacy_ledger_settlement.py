from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest


ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "scripts" / "mutate-work-item.py"


def load_owner():
    name = "mutate_work_item_for_legacy_settlement_tests"
    spec = importlib.util.spec_from_file_location(name, OWNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def legacy_event(index: int, *, gate: str = "none", status: str = "completed") -> dict:
    return {
        "schemaVersion": "1.0",
        "runId": f"legacy-run-{index:04d}",
        "workItem": "legacy-item",
        "role": "qa-engineer",
        "executionRole": "qa-engineer",
        "status": status,
        "gate": gate,
        "scope": f"legacy scope {index}",
        "artifact": None if index % 11 == 0 else "evidence.md",
        "evidence": [{"kind": "manual-check", "ref": f"legacy evidence {index}"}],
        "startedAt": "2026-08-01T00:00:00Z",
        "updatedAt": "2026-08-01T00:00:01Z",
    }


def settlement_request(ledger: bytes, settlements: list[dict]) -> bytes:
    return canonical(
        {
            "schemaVersion": 1,
            "operationId": "legacy-settlement-001",
            "recordedAt": "2026-09-20T12:00:00Z",
            "workItem": "legacy-item",
            "expectedLedgerSha256": digest(ledger),
            "profileId": "identity-ledger-v1-string",
            "profileVersion": 1,
            "settlements": settlements,
        }
    )


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def identity_record_fixture(root: Path, *, optional_fields: bool = False):
    item = root / "work-items" / "active" / "alternate-item"
    item.mkdir(parents=True)
    events = [
        {
            "runId": f"historic-observation-{index}",
            "timestamp": "2026-08-02T03:04:05Z",
            "executionRole": "data-engineer",
            "status": "completed",
            "gate": gate,
            "artifact": "missing-review.md",
            "artifactSha256": "b" * 64,
            "summary": f"Historical observation {index}: retained λ",
        }
        for index, gate in enumerate(("PASS", "REVISE", "PASS", "REVISE", "PASS"), 1)
    ]
    if optional_fields:
        events[0]["candidateRevision"] = "a" * 40
        events[0]["provenance"] = {
            "requestedProvider": "historical-provider",
            "resolvedProvider": "historical-provider",
            "actualExecutionPath": "historical-path",
            "modelProfile": "historical-model",
        }
    physical = b"".join(b"  " + canonical(event) + b"\r\n" for event in events)
    (item / "agent-runs.jsonl").write_bytes(physical)
    request = json.loads(settlement_request(physical, [
        {"targetRunId": "historic-observation-2", "disposition": "preserve-open", "evidence": []},
        {"targetRunId": "historic-observation-4", "disposition": "preserve-open", "evidence": []},
    ]))
    request.update(workItem=item.name, profileId="identity-record-v0")
    return item, physical, events, canonical(request)


def test_identity_record_preserve_open_enrollment_and_replay_conserve_bytes(tmp_path: Path) -> None:
    owner = load_owner()
    root = tmp_path / "repo"
    item, physical, events, request = identity_record_fixture(root)
    before = tree_bytes(root)

    preflight = owner.settle_legacy_ledger(root, request)

    assert preflight["applied"] is False
    assert preflight["profileId"] == "identity-record-v0"
    assert preflight["legacyRunIds"] == [event["runId"] for event in events]
    assert preflight["openObligations"] == ["historic-observation-2", "historic-observation-4"]
    assert tree_bytes(root) == before
    applied = owner.settle_legacy_ledger(root, request, apply_admitted=True)
    assert applied["applied"] is True
    assert applied["settlementRunIds"] == []
    assert (item / "agent-runs.jsonl").read_bytes() == physical
    registry = root / "work-items" / "legacy-ledger-projections.jsonl"
    assert len(registry.read_bytes().splitlines()) == 5
    after = tree_bytes(root)
    replay = owner.settle_legacy_ledger(root, request, apply_admitted=True)
    assert replay["replay"] is True
    assert tree_bytes(root) == after
    validator = owner._load_agent_run_ledger().load_validator()
    obligations = []
    assert validator.validate_work_item(
        item, strict_revise=False, validate_status_file=False,
        obligation_state_out=obligations,
    ) == []
    assert [row.run_id for row in obligations[0].open_revise] == [
        "historic-observation-2", "historic-observation-4",
    ]


def test_identity_record_optional_history_stays_inert_and_cannot_settle(tmp_path: Path) -> None:
    owner = load_owner()
    validator = owner._load_agent_run_ledger().load_validator()
    root = tmp_path / "repo"
    item, physical, events, request = identity_record_fixture(root, optional_fields=True)
    owner.settle_legacy_ledger(root, request, apply_admitted=True)
    context = validator.load_effective_ledger_view(
        root, item, "work-items/active/alternate-item/agent-runs.jsonl",
    )
    errors = []
    validity = validator.derive_event_validity(context.rows, item, errors, context=context)
    assert errors == []
    assert [dict(row.event) for row in context.rows] == events
    assert [row.epoch for row in context.rows] == ["manifest-profile"] * 5
    assert [row.authority.revise_target_eligible for row in validity] == [False, True, False, True, False]
    assert all(not row.current_schema_valid for row in validity)
    assert all(
        not mask.launch_eligible and not mask.terminal_eligible
        and not mask.closer_eligible and not mask.artifact_evidence_eligible
        for mask in (row.authority for row in validity)
    )
    assert (item / "agent-runs.jsonl").read_bytes() == physical
    refusal_root = tmp_path / "refusal-repo"
    refusal_item, _, _, refusal_request = identity_record_fixture(refusal_root)
    proof = refusal_item / "current.md"
    proof.write_bytes(b"current proof\n")
    changed = json.loads(refusal_request)
    changed["settlements"][0].update(
        disposition="satisfied-by-current-evidence",
        evidence=[{"path": "work-items/active/alternate-item/current.md", "sha256": digest(proof.read_bytes())}],
    )
    before = tree_bytes(refusal_root)
    with pytest.raises(owner.LifecycleError) as raised:
        owner.settle_legacy_ledger(refusal_root, canonical(changed), apply_admitted=True)
    assert raised.value.failure_id == "WI-LEDGER-LEGACY-PROFILE-UNSUPPORTED"
    assert tree_bytes(refusal_root) == before


def test_identity_record_generic_prefix_cannot_be_closed_without_target_profession(tmp_path: Path) -> None:
    owner = load_owner()
    validator = owner._load_agent_run_ledger().load_validator()
    root = tmp_path / "repo"
    item, _, events, _ = identity_record_fixture(root)
    proof = item / "current.md"
    proof.write_bytes(b"Fresh synthetic current review evidence.\n")
    target = {
        **events[1], "executionRole": "qa-engineer", "artifact": "current.md",
        "artifactSha256": digest(proof.read_bytes()),
    }
    closer = {
        "schemaVersion": 2, "runId": "current-qa-closer-001", "workItem": item.name,
        "role": "qa-engineer", "executionRole": "internal", "status": "completed",
        "gate": "PASS", "scope": ["fixture"], "artifact": "current.md",
        "closesRunIds": [target["runId"]],
        "evidence": [{"kind": "review", "ref": "Fresh synthetic current review evidence"}],
        "startedAt": "2026-10-03T00:00:00Z", "updatedAt": "2026-10-03T00:00:00Z",
    }
    assert "assignedRole" not in closer and "role" not in target
    suffix_errors = []
    assert validator._validate_event(closer, item, set(), suffix_errors)
    assert suffix_errors == []
    prefix = b"  " + canonical(target) + b"\r\n"
    whole = prefix + canonical(closer) + b"\n"
    ledger = item / "agent-runs.jsonl"
    ledger.write_bytes(whole)
    entry = {
        "entryId": "identity-record-v0-prefix", "profileId": "identity-record-v0",
        "profileVersion": 1, "workItem": item.relative_to(root).as_posix(),
        "ledgerPath": ledger.relative_to(root).as_posix(), "ledgerSha256": digest(whole),
        "rawLineOrdinals": [1], "rawLineSha256": [digest(prefix)],
        "projectedEvents": [target], "projectedEventSha256": [digest(canonical(target))],
    }
    manifest = {
        "schemaVersion": 1, "manifestId": "identity-record-generic-guard",
        "profiles": [{"profileId": "identity-record-v0", "profileVersion": 1}],
        "entries": [entry],
    }
    # The lifecycle owner's persistent lock belongs to fixture infrastructure,
    # so bind the ordinary transaction baseline before measuring publication.
    with owner.LifecycleTransaction(root):
        pass
    before = tree_bytes(root)

    with pytest.raises(owner.LifecycleError) as raised:
        owner.apply_legacy_ledger_projection(
            root, canonical(manifest), entry["entryId"], 1, digest(b""),
            "generic-projection-guard-001", "2026-10-03T00:00:01Z",
        )

    assert raised.value.failure_id == "WI-LEDGER-MIGRATION-CANDIDATE-INVALID"
    assert "C3-authority-fail" in str(raised.value)
    assert "open REVISE obligation" in str(raised.value)
    assert ledger.read_bytes() == whole
    assert tree_bytes(root) == before


@pytest.mark.parametrize("case", ["duplicate-id", "duplicate-key", "unknown-field", "stale-digest"])
def test_identity_record_refuses_invalid_binding_without_residue(tmp_path: Path, case: str) -> None:
    owner = load_owner()
    root = tmp_path / "repo"
    item, physical, events, request = identity_record_fixture(root)
    request_value = json.loads(request)
    if case == "duplicate-id":
        events[4]["runId"] = events[0]["runId"]
    elif case == "unknown-field":
        events[0]["role"] = "data-engineer"
    if case in {"duplicate-id", "unknown-field"}:
        physical = b"".join(canonical(event) + b"\n" for event in events)
    elif case == "duplicate-key":
        physical = physical.replace(b'"runId":', b'"runId":"duplicate-value","runId":', 1)
    (item / "agent-runs.jsonl").write_bytes(physical)
    request_value["expectedLedgerSha256"] = digest(physical) if case != "stale-digest" else "0" * 64
    before = tree_bytes(root)

    with pytest.raises(owner.LifecycleError) as raised:
        owner.settle_legacy_ledger(root, canonical(request_value), apply_admitted=True)

    expected = "WI-LEDGER-MIGRATION-LEDGER-DRIFT" if case == "stale-digest" else "WI-LEDGER-LEGACY-PROFILE-UNSUPPORTED"
    assert raised.value.failure_id == expected
    assert tree_bytes(root) == before


def satisfied_fixture(root: Path, *, operation_id: str = "legacy-settlement-001") -> tuple[Path, bytes, bytes]:
    item = root / "work-items" / "active" / "legacy-item"
    item.mkdir(parents=True)
    evidence_bytes = b"current evidence\n"
    (item / "evidence.md").write_bytes(evidence_bytes)
    events = [legacy_event(index) for index in range(1, 26)]
    events[6] = legacy_event(7, gate="REVISE", status="revise")
    ledger_bytes = b"".join(canonical(event) + b"\n" for event in events)
    ledger = item / "agent-runs.jsonl"
    ledger.write_bytes(ledger_bytes)
    request_value = json.loads(
        settlement_request(
            ledger_bytes,
            [
                {
                    "targetRunId": "legacy-run-0007",
                    "disposition": "satisfied-by-current-evidence",
                    "evidence": [
                        {
                            "path": "work-items/active/legacy-item/evidence.md",
                            "sha256": digest(evidence_bytes),
                        }
                    ],
                }
            ],
        )
    )
    request_value["operationId"] = operation_id
    return ledger, ledger_bytes, canonical(request_value)


def archived_settlement_fixture(root: Path) -> tuple[object, object, Path]:
    owner = load_owner()
    slug = "legacy-item"
    instant = "2026-09-20T12:00:00Z"
    candidate = root / "candidate.md"
    root.mkdir()
    candidate.write_bytes(
        b"Task: Settle legacy ledger.\nNext action: Start.\nupdated: 2026-09-20T11:00:00Z\n"
    )
    owner.create_candidate(root, slug, candidate.read_bytes())
    item = owner.start_item(root, slug, quick_status())
    evidence_bytes = b"current evidence\n"
    (item / "evidence.md").write_bytes(evidence_bytes)
    events = [legacy_event(index) for index in range(1, 26)]
    events[6] = legacy_event(7, gate="REVISE", status="revise")
    ledger_bytes = b"".join(canonical(event) + b"\n" for event in events)
    (item / "agent-runs.jsonl").write_bytes(ledger_bytes)
    (item / "bug-dispositions.json").write_bytes(canonical({
        "schemaVersion": 1, "workItem": slug, "closedAt": instant, "bugs": [],
    }) + b"\n")
    request = settlement_request(ledger_bytes, [{
        "targetRunId": "legacy-run-0007",
        "disposition": "satisfied-by-current-evidence",
        "evidence": [{
            "path": "work-items/active/legacy-item/evidence.md",
            "sha256": digest(evidence_bytes),
        }],
    }])
    owner.settle_legacy_ledger(root, request, apply_admitted=True)
    archived = owner.close_item(root, slug, closure(instant), instant)
    return owner, owner._load_agent_run_ledger().load_validator(), archived


def apply_archive_projection(
    owner: object, root: Path, archived: Path, *, only_target: bool = False
) -> Path:
    manifests = root / "work-items" / "legacy-ledger-projection-manifests"
    active_manifests = list(manifests.glob("*.json"))
    assert len(active_manifests) == 1
    active_manifest = active_manifests[0]
    payload = json.loads(active_manifest.read_bytes())
    payload["manifestId"] = "archive-projection-001"
    entry = payload["entries"][0]
    entry["workItem"] = archived.relative_to(root).as_posix()
    entry["ledgerPath"] = (archived / "agent-runs.jsonl").relative_to(root).as_posix()
    entry["ledgerSha256"] = digest((archived / "agent-runs.jsonl").read_bytes())
    if only_target:
        for field in (
            "rawLineOrdinals", "rawLineSha256", "projectedEvents", "projectedEventSha256"
        ):
            entry[field] = [entry[field][6]]
    registry = root / "work-items" / "legacy-ledger-projections.jsonl"
    owner.apply_legacy_ledger_projection(
        root, canonical(payload), entry["entryId"], entry["rawLineOrdinals"][0],
        digest(registry.read_bytes()), "archive-projection-apply-001",
        "2026-09-20T12:00:02Z",
    )
    return manifests / "archive-projection-001.json"


def quick_status() -> bytes:
    return b"""---
template: quick-fix
status: active
started: 2026-09-20T11:00:00Z
updated: 2026-09-20T11:00:00Z
---

- **Task**: Settle the legacy ledger.
- **Current step**: Apply the admitted settlement.
- **Last result**: Preflight passed.
- **Next action**: Close the item.
"""


def closure(instant: str) -> bytes:
    return (
        f"Closed: {instant}\n"
        "Outcome: Legacy ledger settled.\n"
        "Evidence: focused end-to-end fixture\n"
        "Residual risk: None in fixture.\n"
    ).encode("utf-8")


def test_preflight_reports_exact_legacy_population_and_existing_reducer_obligations(
    tmp_path: Path,
) -> None:
    owner = load_owner()
    root = tmp_path / "repo"
    item = root / "work-items" / "active" / "legacy-item"
    item.mkdir(parents=True)
    (item / "evidence.md").write_text("current evidence\n", encoding="utf-8")
    events = [legacy_event(index) for index in range(1, 26)]
    events[6] = legacy_event(7, gate="REVISE", status="revise")
    events[8] = legacy_event(9, gate="RETURN(provider)")
    events[10] = legacy_event(11, gate="UNVERIFIED")
    events[12] = legacy_event(13, gate="BLOCKED")
    ledger_bytes = b"".join(canonical(event) + b"\n" for event in events)
    ledger = item / "agent-runs.jsonl"
    ledger.write_bytes(ledger_bytes)
    request = settlement_request(
        ledger_bytes,
        [
            {
                "targetRunId": "legacy-run-0007",
                "disposition": "preserve-open",
                "evidence": [],
            }
        ],
    )

    result = owner.settle_legacy_ledger(root, request, apply_admitted=False)

    assert result["applied"] is False
    assert result["replay"] is False
    assert result["profileId"] == "identity-ledger-v1-string"
    assert result["legacyRunIds"] == [event["runId"] for event in events]
    assert result["openObligations"] == ["legacy-run-0007"]
    assert ledger.read_bytes() == ledger_bytes
    assert sorted(path.name for path in item.iterdir()) == [
        "agent-runs.jsonl",
        "evidence.md",
    ]
    assert sorted(path.name for path in (root / "work-items").iterdir()) == [
        "active"
    ]


def test_apply_preserves_prefix_and_run_ids_and_keeps_preserve_open_gate_bearing(
    tmp_path: Path,
) -> None:
    owner = load_owner()
    validator = owner._load_agent_run_ledger().load_validator()
    root = tmp_path / "repo"
    item = root / "work-items" / "active" / "legacy-item"
    item.mkdir(parents=True)
    evidence_path = item / "evidence.md"
    evidence_bytes = b"current evidence\n"
    evidence_path.write_bytes(evidence_bytes)
    events = [legacy_event(index) for index in range(1, 26)]
    events[2] = legacy_event(3, gate="REVISE", status="revise")
    events[6] = legacy_event(7, gate="REVISE", status="revise")
    ledger_bytes = b"".join(canonical(event) + b"\n" for event in events)
    ledger = item / "agent-runs.jsonl"
    ledger.write_bytes(ledger_bytes)
    request = settlement_request(
        ledger_bytes,
        [
            {
                "targetRunId": "legacy-run-0003",
                "disposition": "satisfied-by-current-evidence",
                "evidence": [
                    {
                        "path": "work-items/active/legacy-item/evidence.md",
                        "sha256": digest(evidence_bytes),
                    }
                ],
            },
            {
                "targetRunId": "legacy-run-0007",
                "disposition": "preserve-open",
                "evidence": [],
            },
        ],
    )

    result = owner.settle_legacy_ledger(root, request, apply_admitted=True)

    after = ledger.read_bytes()
    assert result["applied"] is True
    assert result["replay"] is False
    assert after[: len(ledger_bytes)] == ledger_bytes  # legacy_prefix_bytes_are_exact
    decoded = [json.loads(line) for line in after.splitlines()]
    assert [row["runId"] for row in decoded[:25]] == [
        row["runId"] for row in events
    ]  # legacy_run_ids_round_trip
    assert len(decoded) == 26
    settlement = decoded[-1]
    assert settlement["eventKind"] == "closure-invalidation"
    assert settlement["invalidatesRunId"] == "legacy-run-0003"
    assert settlement["gate"] == "none"
    assert settlement["startedAt"] == "2026-09-20T12:00:00Z"
    assert settlement["updatedAt"] == "2026-09-20T12:00:00Z"
    assert all(row.get("gate") != "PASS" for row in decoded[25:])
    assert decoded[2]["executionRole"] == "qa-engineer"
    obligations: list[object] = []
    errors = validator.validate_work_item(
        item,
        strict_revise=False,
        validate_status_file=False,
        obligation_state_out=obligations,
    )
    assert errors == []
    assert len(obligations) == 1
    assert [row.run_id for row in obligations[0].open_revise] == [
        "legacy-run-0007"
    ]
    close_errors = validator.validate_work_item(item, validate_status_file=False)
    assert any("open REVISE obligation: legacy-run-0007" in error for error in close_errors)


@pytest.mark.parametrize("case", ["malformed", "mixed-current"])
def test_unsupported_or_mixed_legacy_population_fails_before_mutation(
    tmp_path: Path, case: str
) -> None:
    owner = load_owner()
    root = tmp_path / "repo"
    item = root / "work-items" / "active" / "legacy-item"
    item.mkdir(parents=True)
    (item / "evidence.md").write_text("current evidence\n", encoding="utf-8")
    if case == "malformed":
        ledger_bytes = b'{"schemaVersion":"1.0"\n'
    else:
        events = [legacy_event(index) for index in range(1, 26)]
        events[12] = {
            "schemaVersion": 2,
            "runId": "current-run-0013",
            "workItem": "legacy-item",
            "role": "qa-engineer",
            "executionRole": "main",
            "status": "completed",
            "gate": "none",
            "scope": ["current scope"],
            "evidence": [],
            "startedAt": "2026-08-01T00:00:00Z",
            "updatedAt": "2026-08-01T00:00:01Z",
        }
        ledger_bytes = b"".join(canonical(event) + b"\n" for event in events)
    (item / "agent-runs.jsonl").write_bytes(ledger_bytes)
    request = settlement_request(ledger_bytes, [])
    before = tree_bytes(root)

    with pytest.raises(owner.LifecycleError) as raised:
        owner.settle_legacy_ledger(root, request, apply_admitted=True)

    assert raised.value.failure_id == "WI-LEDGER-LEGACY-PROFILE-UNSUPPORTED"
    assert tree_bytes(root) == before


def test_exact_replay_is_a_byte_identical_noop_and_changed_request_is_refused(
    tmp_path: Path,
) -> None:
    owner = load_owner()
    root = tmp_path / "repo"
    _ledger, _before, request = satisfied_fixture(root)

    first = owner.settle_legacy_ledger(root, request, apply_admitted=True)
    after_first = tree_bytes(root)
    second = owner.settle_legacy_ledger(root, request, apply_admitted=True)

    assert first["replay"] is False
    assert second["replay"] is True
    assert tree_bytes(root) == after_first
    changed = json.loads(request)
    changed["recordedAt"] = "2026-09-20T12:00:01Z"
    with pytest.raises(owner.LifecycleError) as raised:
        owner.settle_legacy_ledger(root, canonical(changed), apply_admitted=True)
    assert raised.value.failure_id == "WI-LEDGER-COMPAT-REPLAY-MISMATCH"
    assert tree_bytes(root) == after_first


@pytest.mark.parametrize(
    "boundary",
    ["after-manifest", "after-registry", "after-ledger", "after-receipt"],
)
def test_each_participant_failure_restores_exact_preimage(
    tmp_path: Path, boundary: str
) -> None:
    owner = load_owner()
    root = tmp_path / "repo"
    ledger, ledger_before, request = satisfied_fixture(
        root, operation_id=f"legacy-settlement-{boundary}"
    )

    with pytest.raises(owner.LifecycleError) as raised:
        owner.settle_legacy_ledger(
            root,
            request,
            apply_admitted=True,
            inject_failure=boundary,
        )

    assert raised.value.failure_id == "WI-LEDGER-COMPAT-COMMIT-INDETERMINATE"
    assert ledger.read_bytes() == ledger_before
    assert not (ledger.with_suffix(".jsonl.tmp")).exists()
    work_items = root / "work-items"
    assert not (work_items / "legacy-ledger-projections.jsonl").exists()
    assert not (work_items / "legacy-ledger-projection-manifests").exists()
    assert not (work_items / "legacy-ledger-projection-receipts").exists()


def test_zero_open_obligations_flow_through_ordinary_close_receipt_and_readme(
    tmp_path: Path,
) -> None:
    owner = load_owner()
    root = tmp_path / "repo"
    slug = "legacy-item"
    instant = "2026-09-20T12:00:00Z"
    candidate = root / "candidate.md"
    root.mkdir()
    candidate.write_text(
        "Task: Settle legacy ledger.\nNext action: Start.\nupdated: 2026-09-20T11:00:00Z\n",
        encoding="utf-8",
    )
    owner.create_candidate(root, slug, candidate.read_bytes())
    item = owner.start_item(root, slug, quick_status())
    evidence_bytes = b"current evidence\n"
    (item / "evidence.md").write_bytes(evidence_bytes)
    events = [legacy_event(index) for index in range(1, 26)]
    events[6] = legacy_event(7, gate="REVISE", status="revise")
    ledger_bytes = b"".join(canonical(event) + b"\n" for event in events)
    (item / "agent-runs.jsonl").write_bytes(ledger_bytes)
    request = settlement_request(
        ledger_bytes,
        [
            {
                "targetRunId": "legacy-run-0007",
                "disposition": "satisfied-by-current-evidence",
                "evidence": [
                    {
                        "path": "work-items/active/legacy-item/evidence.md",
                        "sha256": digest(evidence_bytes),
                    }
                ],
            }
        ],
    )
    (item / "bug-dispositions.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "workItem": slug,
                "closedAt": instant,
                "bugs": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    owner.settle_legacy_ledger(root, request, apply_admitted=True)
    archived = owner.close_item(root, slug, closure(instant), instant)

    assert archived == root / "work-items" / "archive" / "2026-09" / slug
    assert (archived / "bug-dispositions-receipt.json").is_file()
    readme = (root / "work-items" / "README.md").read_text(encoding="utf-8")
    assert "archive/2026-09/legacy-item" in readme


def test_archived_owner_settlement_legacy_revise_is_exact_invalidation_target(
    tmp_path: Path, monkeypatch,
) -> None:
    root = tmp_path / "repo"
    owner, validator, archived = archived_settlement_fixture(root)
    archive_before = tree_bytes(archived)
    observed = []
    original = validator.resolve_closure_invalidations

    def observe(rows, validity, errors, telemetry=None, *, context=None):
        observed.append((rows, validity))
        return original(rows, validity, errors, telemetry, context=context)

    monkeypatch.setattr(validator, "resolve_closure_invalidations", observe)
    errors, _open_revise, _open_launches = validator.validate_archived_ledger_obligations(archived)
    target = next(index for index, row in enumerate(observed[-1][0]) if row.event.get("runId") == "legacy-run-0007")
    assert observed[-1][0][target].epoch == "raw"
    assert not observed[-1][1][target].authority.revise_target_eligible
    assert any("ledger-recovery:target-ineligible legacy-run-0007" in error for error in errors)
    assert tree_bytes(archived) == archive_before

    apply_archive_projection(owner, root, archived)
    errors, open_revise, open_launches = validator.validate_archived_ledger_obligations(archived)
    rows, validity = observed[-1]
    assert rows[target].epoch == "manifest-profile"
    assert validity[target].current_schema_valid is False
    assert tuple(vars(validity[target].authority).values()) == (False, False, True, False, False)
    assert errors == []
    assert open_revise == [] and open_launches == []
    assert tree_bytes(archived) == archive_before

    wrong_digest = dict(rows[-1].event)
    wrong_digest["invalidatesEventSha256"] = "0" * 64
    altered_rows = (*rows[:-1], replace(rows[-1], event=MappingProxyType(wrong_digest)))
    digest_errors: list[str] = []
    validator.resolve_closure_invalidations(altered_rows, validity, digest_errors)
    assert any("ledger-recovery:target-digest-mismatch" in error for error in digest_errors)

    order_errors: list[str] = []
    validator.resolve_closure_invalidations(
        (rows[-1], *rows[:-1]), (validity[-1], *validity[:-1]), order_errors,
    )
    assert any("ledger-recovery:target-identity" in error for error in order_errors)


@pytest.mark.parametrize("projection", ["absent", "manifest-drift"])
def test_archived_legacy_revise_without_valid_archive_projection_stays_ineligible(
    tmp_path: Path, monkeypatch, projection: str,
) -> None:
    root = tmp_path / "repo"
    owner, validator, archived = archived_settlement_fixture(root)
    archive_before = tree_bytes(archived)
    if projection == "manifest-drift":
        manifest = apply_archive_projection(owner, root, archived)
        manifest.write_bytes(manifest.read_bytes() + b" ")
    observed = []
    original = validator.resolve_closure_invalidations

    def observe(rows, validity, errors, telemetry=None, *, context=None):
        observed.append((rows, validity))
        return original(rows, validity, errors, telemetry, context=context)

    monkeypatch.setattr(validator, "resolve_closure_invalidations", observe)
    errors, _open_revise, _open_launches = validator.validate_archived_ledger_obligations(archived)

    target = next(index for index, row in enumerate(observed[-1][0]) if row.event.get("runId") == "legacy-run-0007")
    assert observed[-1][0][target].epoch == "raw"
    assert observed[-1][1][target].current_schema_valid is False
    assert not any(vars(observed[-1][1][target].authority).values())
    assert any("ledger-recovery:target-ineligible" in error for error in errors)
    if projection == "manifest-drift":
        assert any("manifest digest mismatch" in error for error in errors)
    assert tree_bytes(archived) == archive_before


def test_archive_projection_rejects_unprojected_raw_siblings(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    owner, validator, archived = archived_settlement_fixture(root)
    before = tree_bytes(root)

    with pytest.raises(owner.LifecycleError) as raised:
        apply_archive_projection(owner, root, archived, only_target=True)

    assert raised.value.failure_id == "WI-LEDGER-MIGRATION-CANDIDATE-INVALID"
    errors, _open_revise, _open_launches = validator.validate_archived_ledger_obligations(archived)
    assert any("ledger-recovery:target-ineligible" in error for error in errors)
    assert tree_bytes(root) == before


def test_cli_is_preflight_by_default_and_applies_only_with_explicit_marker(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    ledger, ledger_before, request = satisfied_fixture(root)
    request_path = tmp_path / "settlement-request.json"
    request_path.write_bytes(request)
    base = [
        sys.executable,
        "-B",
        str(OWNER),
        "settle-legacy-ledger",
        "--root",
        str(root),
        "--request-file",
        str(request_path),
    ]

    preflight = subprocess.run(
        base, cwd=ROOT, text=True, capture_output=True, check=False
    )
    assert preflight.returncode == 0, preflight.stdout + preflight.stderr
    assert json.loads(preflight.stdout)["applied"] is False
    assert ledger.read_bytes() == ledger_before

    applied = subprocess.run(
        [*base, "--apply-admitted"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert applied.returncode == 0, applied.stdout + applied.stderr
    assert json.loads(applied.stdout)["applied"] is True
    assert ledger.read_bytes().startswith(ledger_before)


def test_public_projection_refuses_short_legacy_revise_identity_before_admission(
    tmp_path: Path,
) -> None:
    owner = load_owner()
    root = tmp_path / "repo"
    item = root / "work-items" / "active" / "legacy-item"
    item.mkdir(parents=True)
    raw = legacy_event(7, gate="REVISE", status="revise")
    raw["runId"] = "short"
    physical = canonical(raw) + b"\n"
    ledger = item / "agent-runs.jsonl"
    ledger.write_bytes(physical)
    entry = {
        "entryId": "entry-short",
        "profileId": "identity-ledger-v1-string",
        "profileVersion": 1,
        "workItem": "work-items/active/legacy-item",
        "ledgerPath": "work-items/active/legacy-item/agent-runs.jsonl",
        "ledgerSha256": digest(physical),
        "rawLineOrdinals": [1],
        "rawLineSha256": [digest(physical)],
        "projectedEvents": [raw],
        "projectedEventSha256": [digest(canonical(raw))],
    }
    manifest = canonical(
        {
            "schemaVersion": 1,
            "manifestId": "short-id-manifest",
            "profiles": [
                {
                    "profileId": "identity-ledger-v1-string",
                    "profileVersion": 1,
                }
            ],
            "entries": [entry],
        }
    )

    with pytest.raises(owner.LifecycleError) as raised:
        owner.apply_legacy_ledger_projection(
            root,
            manifest,
            "entry-short",
            1,
            digest(b""),
            "short-id-projection",
            "2026-09-20T12:00:00Z",
        )

    assert raised.value.failure_id == "WI-LEDGER-MIGRATION-CANDIDATE-INVALID"
    assert "WI-LEDGER-LEGACY-PROFILE-UNSUPPORTED" in str(raised.value)
    assert ledger.read_bytes() == physical
    work_items = root / "work-items"
    assert not (work_items / "legacy-ledger-projections.jsonl").exists()
    assert not (work_items / "legacy-ledger-projection-manifests").exists()
    assert not (work_items / "legacy-ledger-projection-receipts").exists()
