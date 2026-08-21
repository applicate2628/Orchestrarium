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
    with pytest.raises(fixture["lifecycle"].LifecycleError) as caught:
        fixture["lifecycle"].audit(tmp_path)
    assert caught.value.failure_id == "WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE"


def test_postarchive_rollforward_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    fixture = transition_fixture(tmp_path)
    with pytest.raises(fixture["lifecycle"].LifecycleError):
        run_transition(fixture, inject="T4")
    successor = tmp_path / "work-items" / "backlog" / f"{fixture['successorSlug']}.md"
    successor.write_text("drift\n", encoding="utf-8")
    with pytest.raises(fixture["lifecycle"].LifecycleError) as caught:
        fixture["lifecycle"].audit(tmp_path)
    assert caught.value.failure_id == "WI-LIFECYCLE-TRANSITION-ROLLFORWARD-INDETERMINATE"


def test_settled_receipt_mismatch_is_fatal(tmp_path: Path) -> None:
    fixture = transition_fixture(tmp_path)
    run_transition(fixture)
    receipt = tmp_path / "work-items" / "archive" / "2026-08" / fixture["slug"] / "lifecycle-transition-receipt.json"
    payload = json.loads(receipt.read_text(encoding="utf-8")); payload["readmeSha256"] = "0" * 64
    receipt.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(fixture["lifecycle"].LifecycleError) as caught:
        run_transition(fixture)
    assert caught.value.failure_id == "WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH"


def test_audit_recovers_matching_incomplete_transition_before_membership(tmp_path: Path) -> None:
    fixture = transition_fixture(tmp_path)
    with pytest.raises(fixture["lifecycle"].LifecycleError):
        run_transition(fixture, inject="T3")
    fixture["lifecycle"].audit(tmp_path)
    assert not fixture["item"].exists()
    assert (tmp_path / "work-items" / "archive" / "2026-08" / fixture["slug"] / "lifecycle-transition-receipt.json").is_file()


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
        "migration-specific-paths": 5,
    }

    copied_files = (
        ".scratch/legacy-obligation-migration/baseline.json",
        "README.md",
        "INSTALL.md",
        "docs/work-item-execution-tracking.md",
        "shared/references/subagent-operating-model.md",
        "shared/schemas/agent-runs.schema.json",
        "scripts/agent-run-ledger.py",
        "scripts/check-work-items-state.py",
        "scripts/mutate-work-item.py",
        "scripts/solution_attempt_state.py",
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
