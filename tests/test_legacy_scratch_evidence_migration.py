import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "agent-run-ledger" / "legacy-obligation-migration-v2"
KIND = "remove-string-scratch-evidence"
SCOPE = ["ledger-migration:remove-string-scratch-evidence"]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _line(event: dict) -> bytes:
    return json.dumps(event, separators=(",", ":")).encode()


def _item(tmp_path: Path, *, blocked: bool = False):
    item = tmp_path / "work-items" / "active" / "scratch-migration"
    shutil.copytree(FIXTURE, item)
    launch, terminal = [json.loads(line) for line in (item / "agent-runs.jsonl").read_text().splitlines()]
    target = {
        **terminal,
        "findingClass": "performance",
        "scratchEvidence": "legacy-pointer",
        **({"status": "blocked", "gate": "BLOCKED:prerequisite"} if blocked else {}),
    }
    (item / "agent-runs.jsonl").write_bytes(_line(launch) + b"\n" + _line(target) + b"\n")
    return item, target, _sha(_line(target))


def _apply(target: dict, digest: str, run_id: str = "ledger-migration-scratch-apply") -> dict:
    return {
        "schemaVersion": 2, "runId": run_id, "workItem": target["workItem"],
        "role": "lead", "executionRole": "main", "status": "completed", "gate": "none",
        "scope": SCOPE, "eventKind": "legacy-obligation-migration", "migrationAction": "apply",
        "normalizationKind": KIND, "migratesRunId": target["runId"], "migratesEventSha256": digest,
        "replacementEvent": {key: value for key, value in target.items() if key != "scratchEvidence"},
        "evidence": [{"kind": "manual-check", "ref": f"{KIND} {target['runId']} {digest} -> scratchEvidence absent"}],
        "startedAt": "2026-08-21T00:00:00Z", "updatedAt": "2026-08-21T00:00:00Z",
    }


def _events(validator, item: Path):
    errors, metadata = [], []
    events = validator.load_jsonl(item / "agent-runs.jsonl", errors, metadata)
    assert errors == []
    return events, metadata


def test_scratch_stager_has_one_closed_remove_only_wire(tmp_path: Path) -> None:
    item, target, digest = _item(tmp_path)
    ledger = _load(ROOT / "scripts" / "agent-run-ledger.py", f"scratch_ledger_{id(item)}")
    staged = ledger.stage_legacy_scratch_evidence_migration(
        item, target["runId"], digest, _sha((item / "agent-runs.jsonl").read_bytes()), "scratch-op", "2026-08-21T00:00:00Z"
    )
    anchor = json.loads(staged.staged_bytes.splitlines()[-1])
    assert anchor["normalizationKind"] == KIND
    assert anchor["scope"] == SCOPE
    assert anchor["replacementEvent"] == {key: value for key, value in target.items() if key != "scratchEvidence"}
    assert staged.receipt_facts["normalizationKind"] == KIND
    no_class_item, no_class_target, no_class_digest = _item(tmp_path / "no-class")
    no_class_target.pop("findingClass")
    launch = json.loads((no_class_item / "agent-runs.jsonl").read_text().splitlines()[0])
    (no_class_item / "agent-runs.jsonl").write_bytes(_line(launch) + b"\n" + _line(no_class_target) + b"\n")
    no_class = ledger.stage_legacy_scratch_evidence_migration(
        no_class_item, no_class_target["runId"], _sha(_line(no_class_target)),
        _sha((no_class_item / "agent-runs.jsonl").read_bytes()), "scratch-no-class", "2026-08-21T00:00:01Z"
    )
    assert "findingClass" not in no_class.receipt_facts


def test_scratch_projection_is_remove_only_and_non_string_or_second_defect_is_fatal(tmp_path: Path) -> None:
    item, target, digest = _item(tmp_path)
    validator = _load(ROOT / "scripts" / "validate-work-item-state.py", f"scratch_validator_{id(item)}")
    events, metadata = _events(validator, item)
    anchor = _apply(target, digest)
    effective, counters, errors = validator.project_legacy_obligation_migrations(events + [anchor], metadata + [{"sha256": _sha(_line(anchor))}], item)
    assert errors == []
    assert effective[1] == {key: value for key, value in target.items() if key != "scratchEvidence"}
    assert counters == {"raw": 3, "apply": 1, "revoke": 0, "projected": 1}
    bad_launch = {**target, "launchRunId": "missing-launch"}
    bad_anchor = _apply(bad_launch, _sha(_line(bad_launch)), "ledger-migration-bad-launch")
    _, _, errors = validator.project_legacy_obligation_migrations(
        events[:1] + [bad_launch, bad_anchor],
        metadata[:1] + [{"sha256": _sha(_line(bad_launch))}, {"sha256": _sha(_line(bad_anchor))}],
        item,
    )
    assert errors
    for value in (None, [], {}, 1, True):
        bad_target = {**target, "scratchEvidence": value}
        bad_anchor = _apply(bad_target, _sha(_line(bad_target)), f"ledger-migration-{type(value).__name__}")
        _, _, errors = validator.project_legacy_obligation_migrations(events[:1] + [bad_target, bad_anchor], metadata[:1] + [{"sha256": _sha(_line(bad_target))}, {"sha256": _sha(_line(bad_anchor))}], item)
        assert errors
    second = {**target, "artifact": "../escape.md"}
    second_anchor = _apply(second, _sha(_line(second)), "ledger-migration-second-defect")
    _, _, errors = validator.project_legacy_obligation_migrations(events[:1] + [second, second_anchor], metadata[:1] + [{"sha256": _sha(_line(second))}, {"sha256": _sha(_line(second_anchor))}], item)
    assert errors


def test_scratch_revoke_derives_scope_and_restores_raw_target(tmp_path: Path) -> None:
    item, target, digest = _item(tmp_path, blocked=True)
    lifecycle = _load(ROOT / "scripts" / "mutate-work-item.py", f"scratch_lifecycle_{id(item)}")
    before = (item / "agent-runs.jsonl").read_bytes()
    applied = lifecycle.migrate_legacy_ledger_obligation(
        tmp_path, item.name, target["runId"], digest, _sha(before), "scratch-apply", "2026-08-21T00:00:00Z", normalization_kind=KIND
    )
    replay = lifecycle.migrate_legacy_ledger_obligation(
        tmp_path, item.name, target["runId"], digest, _sha(before), "scratch-apply", "2026-08-21T00:00:00Z", normalization_kind=KIND
    )
    assert replay["findingClass"] == "performance"
    assert replay["diagnosticId"] == "LEDGER-EVENT-SCRATCH-EVIDENCE-INVALID"
    assert lifecycle._scratch_disposition_plan(tmp_path, item, archived=False) == ()
    revoked = lifecycle.revoke_legacy_ledger_obligation(
        tmp_path, item.name, applied["anchorRunId"], applied["anchorEventSha256"], _sha((item / "agent-runs.jsonl").read_bytes()), "scratch-revoke", "2026-08-21T00:00:01Z"
    )
    assert revoked["status"] == "revoked"
    revoke = json.loads((item / "agent-runs.jsonl").read_text().splitlines()[-1])
    assert revoke["scope"] == SCOPE and "normalizationKind" not in revoke
    validator = _load(ROOT / "scripts" / "validate-work-item-state.py", f"scratch_revoke_{id(item)}")
    events, metadata = _events(validator, item)
    effective, counters, errors = validator.project_legacy_obligation_migrations(events, metadata, item)
    assert errors == [] and effective[1]["scratchEvidence"] == "legacy-pointer"
    assert counters == {"raw": 4, "apply": 1, "revoke": 1, "projected": 0}
    with pytest.raises(lifecycle.LifecycleError) as caught:
        lifecycle._scratch_disposition_plan(tmp_path, item, archived=False)
    assert caught.value.failure_id == "WI-LEDGER-UNSETTLED"


def test_scratch_wire_rejects_unknown_kind_scope_evidence_and_cross_kind_revoke(tmp_path: Path) -> None:
    item, target, digest = _item(tmp_path)
    validator = _load(ROOT / "scripts" / "validate-work-item-state.py", f"scratch_wire_{id(item)}")
    events, metadata = _events(validator, item)
    for override in ({"normalizationKind": "patch-anything"}, {"scope": ["ledger-migration:invalid-finding-class"]}, {"evidence": [{"kind": "manual-check", "ref": "wrong"}]}):
        anchor = _apply(target, digest, f"ledger-migration-wire-{len(override)}")
        anchor.update(override)
        _, _, errors = validator.project_legacy_obligation_migrations(events + [anchor], metadata + [{"sha256": _sha(_line(anchor))}], item)
        assert errors


def test_checker_and_runbook_reject_removed_scratch_contract_tokens(tmp_path: Path) -> None:
    checker = _load(ROOT / "scripts" / "check-agent-run-ledger-contract.py", f"scratch_checker_{id(tmp_path)}")
    assert "WI-LEDGER-MIGRATION-NORMALIZATION-KIND" in checker.MIGRATION_FAILURE_IDS
    for relative in (
        "shared/schemas/agent-runs.schema.json",
        "scripts/validate-work-item-state.py",
        "scripts/agent-run-ledger.py",
        "scripts/mutate-work-item.py",
        "docs/work-item-execution-tracking.md",
        "README.md",
        "INSTALL.md",
        "shared/references/subagent-operating-model.md",
    ):
        source, target = ROOT / relative, tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    shutil.copytree(FIXTURE, tmp_path / "tests" / "fixtures" / "agent-run-ledger" / FIXTURE.name)
    checker.check_legacy_migration_contract(tmp_path)
    runbook = tmp_path / "docs" / "work-item-execution-tracking.md"
    runbook.write_text(runbook.read_text(encoding="utf-8").replace("remove-string-scratch-evidence", "removed-token"), encoding="utf-8")
    with pytest.raises(AssertionError):
        checker.check_legacy_migration_contract(tmp_path)
