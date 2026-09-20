from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

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
