#!/usr/bin/env python3
import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path


RECOVERY_RUNBOOK_TOKENS = (
    "recover-invalid-closure",
    "invalidatesRunId",
    "invalidatesEventSha256",
    "target-per-event-invalid",
    "RESULT: PASS recover-invalid-closure",
    "store-commit/readback",
    "replacement",
)
RECOVERY_POINTERS = {
    "README.md": "docs/work-item-execution-tracking.md",
    "INSTALL.md": "docs/work-item-execution-tracking.md",
    "shared/references/subagent-operating-model.md": "../../docs/work-item-execution-tracking.md",
}

MIGRATION_FIXTURE_SHA256 = "b088887c251c465095d74e7886752798f68f1de41bcdf12ab04294b5ad2d7a3a"
MIGRATION_FIXTURE_BYTES = 704
MIGRATION_COMMANDS = (
    "migrate-legacy-ledger-obligation",
    "revoke-legacy-ledger-obligation",
    "archive-with-successor",
)
MIGRATION_FAILURE_IDS = (
    "WI-LEDGER-MIGRATION-TARGET-IDENTITY",
    "WI-LEDGER-MIGRATION-TARGET-DIGEST",
    "WI-LEDGER-MIGRATION-LEDGER-DRIFT",
    "WI-LEDGER-MIGRATION-TARGET-INELIGIBLE",
    "WI-LEDGER-MIGRATION-DEFECT-CLASS",
    "WI-LEDGER-MIGRATION-NORMALIZATION-KIND",
    "WI-LEDGER-MIGRATION-REPLACEMENT-MISMATCH",
    "WI-LEDGER-MIGRATION-V3-UNSUPPORTED",
    "WI-LEDGER-MIGRATION-TOPOLOGY",
    "WI-LIFECYCLE-LOCK-HELD",
    "WI-LEDGER-MIGRATION-CANDIDATE-INVALID",
    "WI-LEDGER-MIGRATION-COMMIT-INDETERMINATE",
    "WI-LEDGER-MIGRATION-RECEIPT-MISMATCH",
    "WI-LIFECYCLE-TRANSITION-INTENT-INVALID",
    "WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE",
    "WI-LIFECYCLE-TRANSITION-ROLLFORWARD-INDETERMINATE",
    "WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH",
    "WI-LEDGER-MIGRATION-REVOCATION-FROZEN",
)
MIGRATION_RECEIPT_FIELDS = (
    "operationId",
    "targetRunId",
    "targetEventSha256",
    "anchorRunId",
    "anchorEventSha256",
    "beforeLedgerBytes",
    "beforeLedgerSha256",
    "afterLedgerBytes",
    "afterLedgerSha256",
    "replacementEventSha256",
    "normalizationKind",
    "findingClass",
    "diagnosticId",
    "sourcePath",
    "receiptPath",
    "recordedAt",
)
MIGRATION_POINTER_FORBIDDEN_TOKENS = (*MIGRATION_COMMANDS, *MIGRATION_FAILURE_IDS)
MIGRATION_BASELINE_SHA256 = "f6baf1f60f9838b13f69488b4f17b6a37bbe7d2c2372c4eec8c2503508f6ec76"
MIGRATION_ALLOWED_BASELINE_DRIFT = {
    "shared/schemas/agent-runs.schema.json",
    "scripts/validate-work-item-state.py",
    "scripts/agent-run-ledger.py",
    "scripts/mutate-work-item.py",
    "scripts/check-agent-run-ledger-contract.py",
    "tests/test_work_item_state_validator.py",
    "tests/test_mutate_work_item.py",
    "docs/work-item-execution-tracking.md",
}
MIGRATION_ACCEPTED_CURRENT_BYTES = {
    "tests/test_agent_run_ledger.py": "e11b56562d1e14b85c6966a392352fa90935a62a943e561934557d9ae311bf75",
}


# Legacy status shape: older work items carry `orchestrator: main | lead`. Kept as a
# labeled legacy fixture (the validator does not rewrite old files). STATUS_TEXT_CANONICAL
# below covers the current `orchestration: light | full-lead` field so both are exercised.
STATUS_TEXT = """---
template: full-delivery
orchestrator: lead
started: 2026-05-03
updated: 2026-05-03 14:24
---

## Current state

- **Primary task**: validate agent run ledger
- **Primary task status**: active
- **Interruption marker**: none
- **Stage**: QA
- **Main conv role**: reviewing artifact
- **Last accepted artifact**: reviews/qa.md
- **Open obligations before closeout**: none

## Active agents

| Agent | Role | Status | Launched |
| --- | --- | --- | --- |

## Completed agents

| Agent | Role | Result | Artifact |
| --- | --- | --- | --- |
| qa-001 | qa-engineer | PASS | reviews/qa.md |

## Next action

Close the stage after publication gate.
"""

# Canonical status shape: current field is `orchestration: light | full-lead`.
STATUS_TEXT_CANONICAL = STATUS_TEXT.replace("orchestrator: lead", "orchestration: full-lead")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"script must be loadable: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _command_blocks(runbook: str, command: str) -> list[str]:
    return [
        block
        for index, block in enumerate(runbook.split("```"))
        if index % 2 == 1 and command in block
    ]


def check_legacy_migration_contract(root: Path) -> dict[str, int]:
    """Bind the one typed legacy-obligation migration across its live owners."""
    schema_path = root / "shared" / "schemas" / "agent-runs.schema.json"
    validator_path = root / "scripts" / "validate-work-item-state.py"
    writer_path = root / "scripts" / "agent-run-ledger.py"
    lifecycle_path = root / "scripts" / "mutate-work-item.py"
    runbook_path = root / "docs" / "work-item-execution-tracking.md"
    fixture = root / "tests" / "fixtures" / "agent-run-ledger" / "legacy-obligation-migration-v2"

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    props = schema["properties"]
    require(
        "legacy-obligation-migration" in props["eventKind"]["enum"],
        "schema must expose the migration event kind",
    )
    require(
        set(props["migrationAction"]["enum"]) == {"apply", "revoke"},
        "schema must expose the closed apply/revoke discriminator",
    )
    require(
        "legacy-unclassified" in props["findingClass"]["enum"],
        "schema must expose the truthful legacy-unclassified class",
    )
    schema_text = schema_path.read_text(encoding="utf-8")
    for token in (
        "migratesRunId",
        "migratesEventSha256",
        "revokesMigrationRunId",
        "revokesMigrationEventSha256",
        "replacementEvent",
        "normalizationKind",
        "ledger-migration:invalid-finding-class",
        "ledger-migration:remove-string-scratch-evidence",
    ):
        require(token in schema_text, f"migration schema is missing {token!r}")

    expected = json.loads((fixture / "expected.json").read_text(encoding="utf-8"))
    raw_lines = (fixture / "agent-runs.jsonl").read_bytes().splitlines()
    targets = [line for line in raw_lines if json.loads(line).get("runId") == expected["targetRunId"]]
    require(len(targets) == 1, "migration fixture must contain one exact target")
    target = targets[0]
    require(len(target) == MIGRATION_FIXTURE_BYTES, "migration fixture target byte count drifted")
    require(
        hashlib.sha256(target).hexdigest() == MIGRATION_FIXTURE_SHA256 == expected["targetRawSha256"],
        "migration fixture target digest drifted",
    )

    validator_text = validator_path.read_text(encoding="utf-8")
    writer_text = writer_path.read_text(encoding="utf-8")
    lifecycle_text = lifecycle_path.read_text(encoding="utf-8")
    for token in (
        "project_legacy_obligation_migrations",
        "LEDGER-EVENT-FINDING-CLASS-INVALID",
        "LEDGER-EVENT-SCRATCH-EVIDENCE-INVALID",
        "migration_terminal_launch_relation_error",
        '"raw": len(events)',
        '"apply": 0',
        '"revoke": 0',
        '"projected": 0',
        "PROTECTED_CLASSES",
        "legacy-unclassified",
    ):
        require(token in validator_text, f"migration reader/projection is missing {token!r}")
    for token in (
        "stage_invalid_finding_class_migration",
        "stage_legacy_scratch_evidence_migration",
        "remove-string-scratch-evidence",
        "legacy-obligation-migration",
        "legacy-unclassified",
        *MIGRATION_RECEIPT_FIELDS,
    ):
        require(token in writer_text, f"migration staging owner is missing {token!r}")
    for token in (
        *MIGRATION_COMMANDS,
        "WI-LEDGER-MIGRATION-COMMITTED",
        "WI-LEDGER-MIGRATION-REVOKED",
        "remove-string-scratch-evidence",
        "WI-LIFECYCLE-TRANSITION-COMMITTED",
        "lifecycle-transition-receipt.json",
        "status\": \"settled",
    ):
        require(token in lifecycle_text, f"migration lifecycle owner is missing {token!r}")

    writer_help = subprocess.run(
        [sys.executable, str(writer_path), "--help"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    require(writer_help.returncode == 0, "ledger helper --help must pass")
    for command in MIGRATION_COMMANDS[:2]:
        require(command not in writer_help.stdout, f"ledger helper must not expose {command}")
    lifecycle_help = subprocess.run(
        [sys.executable, str(lifecycle_path), "--help"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    require(lifecycle_help.returncode == 0, "lifecycle helper --help must pass")
    for command in MIGRATION_COMMANDS:
        require(command in lifecycle_help.stdout, f"lifecycle helper must expose {command}")

    runbook = runbook_path.read_text(encoding="utf-8")
    for command in MIGRATION_COMMANDS:
        require(
            len(_command_blocks(runbook, command)) == 1,
            f"migration runbook must own exactly one {command} command block",
        )
    for token in (
        "legacy-unclassified",
        "remove-string-scratch-evidence",
        "normalizationKind",
        "raw events",
        "effective projection",
        "first use",
        "forward-only",
        "p95",
        "architecture-pattern",
        *MIGRATION_RECEIPT_FIELDS,
        *MIGRATION_FAILURE_IDS,
    ):
        require(token in runbook, f"migration runbook is missing {token!r}")
    for relative, pointer in RECOVERY_POINTERS.items():
        text = (root / relative).read_text(encoding="utf-8")
        require(pointer in text, f"{relative} must point to the canonical execution-tracking runbook")
        for token in MIGRATION_POINTER_FORBIDDEN_TOKENS:
            require(token not in text, f"{relative} must not duplicate migration procedure token {token!r}")

    validator = _load_script(validator_path, f"legacy_contract_validator_{id(root)}")
    ledger_owner = _load_script(writer_path, f"legacy_contract_ledger_{id(root)}")
    lifecycle = _load_script(lifecycle_path, f"legacy_contract_lifecycle_{id(root)}")
    telemetry = {
        "fixture-target-bytes": len(target),
        "fixture-target-digest": 1,
        "canonical-command-blocks": len(MIGRATION_COMMANDS),
        "failure-ids": len(MIGRATION_FAILURE_IDS),
        "apply-accepted": 0,
        "apply-refused": 0,
        "apply-idempotent": 0,
        "apply-revoked": 0,
        "projected-events": 0,
    }
    with tempfile.TemporaryDirectory() as tmp:
        repository = Path(tmp)
        item = repository / "work-items" / "active" / fixture.name
        item.mkdir(parents=True)
        for source in fixture.iterdir():
            if source.is_file():
                (item / source.name).write_bytes(source.read_bytes())
        before = (item / "agent-runs.jsonl").read_bytes()
        before_sha = hashlib.sha256(before).hexdigest()
        staged = ledger_owner.stage_invalid_finding_class_migration(
            item,
            expected["targetRunId"],
            expected["targetRawSha256"],
            before_sha,
            "contract-check-apply",
            "2026-08-18T00:00:00Z",
        )
        telemetry["apply-accepted"] = 1
        try:
            ledger_owner.stage_invalid_finding_class_migration(
                item,
                expected["targetRunId"],
                "0" * 64,
                before_sha,
                "contract-check-refused",
                "2026-08-18T00:00:00Z",
            )
        except ledger_owner.LedgerMigrationError as exc:
            require(exc.failure_id == "WI-LEDGER-MIGRATION-TARGET-DIGEST", "refusal ID drifted")
            telemetry["apply-refused"] = 1
        else:
            raise AssertionError("wrong target digest must be refused")

        candidate = item / "candidate.jsonl"
        candidate.write_bytes(staged.staged_bytes)
        parse_errors: list[str] = []
        raw_metadata: list[dict[str, object]] = []
        events = validator.load_jsonl(candidate, parse_errors, raw_metadata)
        effective, counters, projection_errors = validator.project_legacy_obligation_migrations(
            events, raw_metadata, item
        )
        require(parse_errors == projection_errors == [], "migration fixture projection must pass")
        require(counters == {"raw": 3, "apply": 1, "revoke": 0, "projected": 1}, "projection counters drifted")
        require(
            sum(event.get("findingClass") == "legacy-unclassified" for event in effective) == 1,
            "effective projection must contain one legacy-unclassified event",
        )
        require(
            sum(event.get("findingClass") == "security" for event in effective) == 0,
            "legacy-unclassified must not enter the security bucket",
        )
        telemetry["projected-events"] = counters["projected"]

        first = lifecycle.migrate_legacy_ledger_obligation(
            repository,
            item.name,
            expected["targetRunId"],
            expected["targetRawSha256"],
            before_sha,
            "contract-check-apply",
            "2026-08-18T00:00:00Z",
        )
        replay = lifecycle.migrate_legacy_ledger_obligation(
            repository,
            item.name,
            expected["targetRunId"],
            expected["targetRawSha256"],
            before_sha,
            "contract-check-apply",
            "2026-08-18T00:00:00Z",
        )
        require(first == replay, "migration apply replay must be idempotent")
        telemetry["apply-idempotent"] = 1
        ledger_data = (item / "agent-runs.jsonl").read_bytes()
        revoked = lifecycle.revoke_legacy_ledger_obligation(
            repository,
            item.name,
            first["anchorRunId"],
            first["anchorEventSha256"],
            hashlib.sha256(ledger_data).hexdigest(),
            "contract-check-revoke",
            "2026-08-18T00:00:01Z",
        )
        require(revoked.get("status") == "revoked", "migration revoke result drifted")
        telemetry["apply-revoked"] = 1

        scratch_item = repository / "work-items" / "active" / "legacy-scratch-contract"
        scratch_item.mkdir(parents=True)
        for source in fixture.iterdir():
            if source.is_file() and source.name != "agent-runs.jsonl":
                (scratch_item / source.name).write_bytes(source.read_bytes())
        launch, old_target = [json.loads(line) for line in (fixture / "agent-runs.jsonl").read_bytes().splitlines()]
        launch["workItem"] = scratch_item.name
        scratch_target = {
            **old_target,
            "workItem": scratch_item.name,
            "findingClass": "performance",
            "status": "blocked",
            "gate": "BLOCKED:prerequisite",
            "scratchEvidence": "legacy-pointer",
        }
        scratch_data = (
            json.dumps(launch, separators=(",", ":")).encode() + b"\n"
            + json.dumps(scratch_target, separators=(",", ":")).encode() + b"\n"
        )
        (scratch_item / "agent-runs.jsonl").write_bytes(scratch_data)
        scratch_digest = hashlib.sha256(json.dumps(scratch_target, separators=(",", ":")).encode()).hexdigest()
        scratch_before = hashlib.sha256(scratch_data).hexdigest()
        scratch_staged = ledger_owner.stage_legacy_scratch_evidence_migration(
            scratch_item, scratch_target["runId"], scratch_digest, scratch_before,
            "contract-check-scratch", "2026-08-21T00:00:00Z",
        )
        scratch_anchor = json.loads(scratch_staged.staged_bytes.splitlines()[-1])
        require(
            scratch_anchor.get("normalizationKind") == "remove-string-scratch-evidence"
            and scratch_anchor.get("scope") == ["ledger-migration:remove-string-scratch-evidence"],
            "scratch apply wire drifted",
        )
        bad_launch = {**scratch_target, "launchRunId": "missing-launch"}
        (scratch_item / "agent-runs.jsonl").write_bytes(
            json.dumps(launch, separators=(",", ":")).encode() + b"\n"
            + json.dumps(bad_launch, separators=(",", ":")).encode() + b"\n"
        )
        try:
            ledger_owner.stage_legacy_scratch_evidence_migration(
                scratch_item, bad_launch["runId"],
                hashlib.sha256(json.dumps(bad_launch, separators=(",", ":")).encode()).hexdigest(),
                hashlib.sha256((scratch_item / "agent-runs.jsonl").read_bytes()).hexdigest(),
                "contract-check-bad-launch", "2026-08-21T00:00:00Z",
            )
        except ledger_owner.LedgerMigrationError as exc:
            require(exc.failure_id == "WI-LEDGER-MIGRATION-TARGET-INELIGIBLE", "scratch launch refusal drifted")
        else:
            raise AssertionError("scratch target without a valid launch must be refused")
        scratch_target.pop("findingClass")
        scratch_data = (
            json.dumps(launch, separators=(",", ":")).encode() + b"\n"
            + json.dumps(scratch_target, separators=(",", ":")).encode() + b"\n"
        )
        (scratch_item / "agent-runs.jsonl").write_bytes(scratch_data)
        scratch_digest = hashlib.sha256(json.dumps(scratch_target, separators=(",", ":")).encode()).hexdigest()
        scratch_before = hashlib.sha256(scratch_data).hexdigest()
        try:
            lifecycle.migrate_legacy_ledger_obligation(
                repository, scratch_item.name, scratch_target["runId"], scratch_digest,
                scratch_before, "contract-check-scratch", "2026-08-21T00:00:00Z",
                normalization_kind="remove-string-scratch-evidence", inject_failure="after-anchor",
            )
        except lifecycle.LifecycleError as exc:
            require(exc.failure_id == "WI-LEDGER-MIGRATION-COMMIT-INDETERMINATE", "scratch crash discriminator drifted")
        else:
            raise AssertionError("scratch crash injection must stop after the anchor")
        scratch_first = lifecycle.migrate_legacy_ledger_obligation(
            repository, scratch_item.name, scratch_target["runId"], scratch_digest,
            scratch_before, "contract-check-scratch", "2026-08-21T00:00:00Z",
            normalization_kind="remove-string-scratch-evidence",
        )
        require(
            scratch_first.get("normalizationKind") == "remove-string-scratch-evidence"
            and scratch_first.get("diagnosticId") == "LEDGER-EVENT-SCRATCH-EVIDENCE-INVALID"
            and "findingClass" not in scratch_first,
            "scratch receipt reconstruction drifted",
        )
        scratch_revoked = lifecycle.revoke_legacy_ledger_obligation(
            repository, scratch_item.name, scratch_first["anchorRunId"], scratch_first["anchorEventSha256"],
            hashlib.sha256((scratch_item / "agent-runs.jsonl").read_bytes()).hexdigest(),
            "contract-check-scratch-revoke", "2026-08-21T00:00:01Z",
        )
        require(scratch_revoked.get("status") == "revoked", "scratch revoke drifted")
    return telemetry


def check_legacy_migration_diff_guard(root: Path) -> dict[str, int]:
    """Reconcile the Phase 0 byte boundary without blaming admitted later phases."""
    baseline_path = root / "tests" / "fixtures" / "legacy-obligation-migration" / "baseline.json"
    baseline_bytes = baseline_path.read_bytes()
    require(
        hashlib.sha256(baseline_bytes).hexdigest() == MIGRATION_BASELINE_SHA256,
        "migration Phase 0 baseline manifest drifted",
    )
    baseline = json.loads(baseline_bytes.decode("utf-8"))
    rows = [
        *baseline["allowedProductionFiles"],
        *baseline["allowedExistingTestExpectations"],
        *baseline["protectedDirtySiblings"],
    ]
    for row in rows:
        relative = row["path"]
        accepted = MIGRATION_ACCEPTED_CURRENT_BYTES.get(relative)
        if accepted is not None:
            path = root / relative
            require(path.is_file(), f"protected migration sibling is missing: {relative}")
            require(
                hashlib.sha256(path.read_bytes()).hexdigest() == accepted,
                f"protected migration sibling hash drifted: {relative}",
            )
            continue
        if relative in MIGRATION_ALLOWED_BASELINE_DRIFT:
            continue
        path = root / relative
        require(path.is_file(), f"protected migration sibling is missing: {relative}")
        data = path.read_bytes()
        require(len(data) == row["bytes"], f"protected migration sibling size drifted: {relative}")
        require(
            hashlib.sha256(data).hexdigest() == row["sha256"],
            f"protected migration sibling hash drifted: {relative}",
        )

    fixture = root / "tests" / "fixtures" / "agent-run-ledger" / "legacy-obligation-migration-v2"
    fixture_files = sorted(path.name for path in fixture.iterdir() if path.is_file())
    require(
        fixture_files == ["agent-runs.jsonl", "expected.json", "implementation.md", "status.md"],
        "migration fixture path set drifted",
    )
    migration_paths = [
        root / "tests" / "test_legacy_obligation_migration.py",
        baseline_path,
    ] + [
        fixture / name for name in fixture_files
    ]
    require(all(path.is_file() for path in migration_paths), "migration-specific path is missing")
    return {
        "baseline-manifest": 1,
        "protected-hashes": 1,
        "fixture-files": len(fixture_files),
        "migration-specific-paths": len(migration_paths),
    }


def ledger_event(**updates: object) -> dict[str, object]:
    event: dict[str, object] = {
        "schemaVersion": 1,
        "runId": "2026-05-03T14-20-00Z-qa-001",
        "workItem": "agent-execution-tracking",
        "role": "qa-engineer",
        "executionRole": "internal",
        "status": "completed",
        "gate": "PASS",
        "scope": ["scripts/validate-work-item-state.py"],
        "artifact": "reviews/qa.md",
        "evidence": [{"kind": "command", "ref": "pytest -q", "result": "passed"}],
        "startedAt": "2026-05-03T14:20:00Z",
        "updatedAt": "2026-05-03T14:24:00Z",
    }
    event.update(updates)
    return event


def solution_capsule() -> dict[str, object]:
    return {
        "version": 1,
        "declarationSetId": "declaration-one",
        "objects": [
            {
                "decisionObjectId": "object-one",
                "mutationSurfaces": ["scripts/example.py"],
                "solutionClasses": ["class-one"],
                "initialClassId": "class-one",
                "initialAttemptId": "attempt-one",
                "guardIds": [
                    "mutation-surface-subset",
                    "no-new-dependency",
                    "no-new-contract-risk-owner",
                    "forbidden-mechanism-tag",
                    "required-oracle",
                    "item-specific-stop",
                ],
            }
        ],
        "baseline": "b" * 64,
        "author": "accepted-admission-run",
    }


def v3_event(**updates: object) -> dict[str, object]:
    event: dict[str, object] = {
        "schemaVersion": 3,
        "eventId": "event-bootstrap-0001",
        "operationId": "bootstrap-0001",
        "fingerprint": "1" * 64,
        "priorHead": "GENESIS",
        "recordedAt": "2026-08-13T07:30:00Z",
        "eventType": "solution-bootstrap",
        "payload": {"capsule": solution_capsule()},
    }
    event.update(updates)
    return event


def check_schema(root: Path) -> None:
    schema_path = root / "shared" / "schemas" / "agent-runs.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    props = schema["properties"]
    evidence_items = props["evidence"]["items"]
    owner_path = root / "scripts" / "solution_attempt" / "reducer.py"
    spec = importlib.util.spec_from_file_location("solution_attempt_reducer_contract_check", owner_path)
    require(spec is not None and spec.loader is not None, "V3 reducer owner must be loadable")
    owner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owner)

    require(schema.get("additionalProperties") is False, "schema must reject top-level extra fields")
    require(props["runId"].get("minLength") == 8, "schema must require runId minLength 8")
    require(props["startedAt"].get("minLength") == 10, "schema must require startedAt minLength 10")
    require(props["updatedAt"].get("minLength") == 10, "schema must require updatedAt minLength 10")
    require(evidence_items.get("additionalProperties") is False, "schema must reject extra evidence fields")
    require(set(evidence_items.get("required", [])) == {"kind", "ref"}, "schema must require evidence kind/ref")
    require(
        set(props["schemaVersion"].get("enum", [])) == {1, 2, 3},
        "schema must expose the expand-only V1/V2/V3 reader set",
    )
    require(
        schema["x-orchestrarium-jsonl"].get("maxLineBytes") == 131072,
        "schema must carry an explicit raw UTF-8 ledger-line bound",
    )
    require(
        {"eventId", "operationId", "fingerprint", "priorHead", "recordedAt", "eventType", "payload"}
        <= set(props),
        "schema must expose every canonical V3 control field",
    )
    require(
        set(props["eventType"].get("enum", [])) == set(owner.EVENT_TYPES),
        "schema and reducer must share one exact closed V3 event discriminator",
    )

    # Exactly ONE main-conversation identity on the wire: "main". The retired
    # orchestrator main|lead duality must not resurface as two owner-shaped enum
    # values (one owner split across two rollup audit buckets); "lead" survives
    # only as the validator's documented legacy READ-mapping, never in the enum.
    execution_roles = set(props["executionRole"].get("enum", []))
    require(
        "main" in execution_roles and "lead" not in execution_roles,
        "schema must model exactly one main-conversation identity ('main' in the "
        "executionRole enum, 'lead' absent — legacy 'lead' reads map to 'main')",
    )

    event_kinds = set(props["eventKind"].get("enum", []))
    require("closure-invalidation" in event_kinds, "schema must expose closure-invalidation")
    require(
        {"invalidatesRunId", "invalidatesEventSha256"} <= set(props),
        "schema must expose both closure-invalidation identity fields",
    )


def check_recovery_documentation(root: Path) -> None:
    runbook_path = root / "docs" / "work-item-execution-tracking.md"
    runbook = runbook_path.read_text(encoding="utf-8")
    for token in RECOVERY_RUNBOOK_TOKENS:
        require(token in runbook, f"recovery runbook must contain exact token {token!r}")

    recovery_blocks = [
        block
        for index, block in enumerate(runbook.split("```"))
        if index % 2 == 1 and "recover-invalid-closure" in block
    ]
    require(
        len(recovery_blocks) == 1,
        "recovery runbook must own exactly one recover-invalid-closure command block",
    )

    forbidden_pointer_tokens = (
        "recover-invalid-closure",
        "invalidatesRunId",
        "invalidatesEventSha256",
        "RESULT: PASS recover-invalid-closure",
        "store-commit/readback",
    )
    for relative, pointer in RECOVERY_POINTERS.items():
        text = (root / relative).read_text(encoding="utf-8")
        require(pointer in text, f"{relative} must point to the canonical execution-tracking runbook")
        for token in forbidden_pointer_tokens:
            require(token not in text, f"{relative} must not duplicate recovery procedure token {token!r}")


def check_recovery_fixture_and_runtime(root: Path) -> None:
    fixture = root / "tests" / "fixtures" / "agent-run-ledger" / "closure-invalidation-v2"
    expected = json.loads((fixture / "expected.json").read_text(encoding="utf-8"))
    raw_lines = (fixture / "agent-runs.jsonl").read_bytes().splitlines()
    target_matches = [
        line
        for line in raw_lines
        if json.loads(line).get("runId") == expected["targetRunId"]
    ]
    require(len(target_matches) == 1, "fixture must contain one exact target runId")
    require(
        hashlib.sha256(target_matches[0]).hexdigest() == expected["targetEventSha256"],
        "fixture target digest must bind exact raw line bytes",
    )
    recovery_matches = [
        json.loads(line)
        for line in raw_lines
        if json.loads(line).get("runId") == expected["recoveryRunId"]
    ]
    require(len(recovery_matches) == 1, "fixture must contain one exact recovery runId")
    require(
        recovery_matches[0].get("invalidatesRunId") == expected["targetRunId"]
        and recovery_matches[0].get("invalidatesEventSha256") == expected["targetEventSha256"],
        "fixture recovery event must bind the expected target identity and digest",
    )

    validator = root / "scripts" / "validate-work-item-state.py"
    validation = subprocess.run(
        [sys.executable, str(validator), "--work-item", str(fixture)],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    require(validation.returncode == 0, f"recovery fixture must validate:\n{validation.stdout}")
    require("RESULT: PASS" in validation.stdout, "recovery fixture validator must emit RESULT: PASS")

    writer_path = root / "scripts" / "agent-run-ledger.py"
    writer = writer_path.read_text(encoding="utf-8")
    validator_text = validator.read_text(encoding="utf-8")
    for token in ("recover-invalid-closure", "RESULT: PASS recover-invalid-closure"):
        require(token in writer, f"writer must expose exact recovery contract token {token!r}")
    for token in ("closure-invalidation", "invalidatesRunId", "invalidatesEventSha256", "ledger-recovery:target-per-event-invalid"):
        require(token in validator_text, f"validator must expose exact recovery contract token {token!r}")

    rollup = subprocess.run(
        [sys.executable, str(writer_path), "--work-item", str(fixture), "rollup", "--json"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    require(rollup.returncode == 0, f"recovery fixture rollup must pass:\n{rollup.stdout}")
    summary = json.loads(rollup.stdout)
    require(summary.get("items") == 1, "recovery fixture rollup must contain one item")
    require(summary.get("totalRuns") == len(raw_lines), "recovery fixture rollup must retain every raw event")
    require(summary.get("malformedLines") == 0, "recovery fixture rollup must contain no malformed line")


def run_validator_case(root: Path, base: Path, name: str, event: dict[str, object], expect_pass: bool, fragments: tuple[str, ...] = (), status_text: str = STATUS_TEXT) -> None:
    item = base / name
    validator = root / "scripts" / "validate-work-item-state.py"
    (item / "reviews").mkdir(parents=True)
    (item / "status.md").write_text(status_text, encoding="utf-8")
    (item / "reviews" / "qa.md").write_text("# QA\n\nGate: PASS\n", encoding="utf-8")
    (item / "agent-runs.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(validator), "--work-item", str(item)],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if expect_pass and proc.returncode != 0:
        raise AssertionError(f"{name} should pass:\n{proc.stdout}")
    if not expect_pass and proc.returncode == 0:
        raise AssertionError(f"{name} should fail:\n{proc.stdout}")
    for fragment in fragments:
        require(fragment in proc.stdout, f"{name} output missed {fragment!r}:\n{proc.stdout}")


def check_validator(root: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        run_validator_case(root, base, "valid", ledger_event(), True)
        run_validator_case(
            root,
            base,
            "canonical-orchestration",
            ledger_event(),
            True,
            status_text=STATUS_TEXT_CANONICAL,
        )
        # Legacy read-mapping: a pre-2026-07-11 ledger line with executionRole
        # "lead" still validates (it reads as "main" — same owner, one identity).
        run_validator_case(
            root,
            base,
            "legacy-execution-role-lead-reads",
            ledger_event(executionRole="lead"),
            True,
        )
        # ...but the mapping is not a general escape hatch: a value outside the
        # canonical enum and the legacy map still fails.
        run_validator_case(
            root,
            base,
            "unknown-execution-role-fails",
            ledger_event(executionRole="foo"),
            False,
            ("invalid executionRole",),
        )
        # And the canonical single main-conversation identity validates.
        run_validator_case(
            root,
            base,
            "main-execution-role",
            ledger_event(executionRole="main"),
            True,
        )
        run_validator_case(
            root,
            base,
            "extra-evidence-field",
            ledger_event(evidence=[{"kind": "command", "ref": "pytest -q", "extra": "unexpected"}]),
            False,
            ("unexpected field",),
        )
        run_validator_case(
            root,
            base,
            "short-required-strings",
            ledger_event(runId="x", startedAt="1", updatedAt="2"),
            False,
            (
                "runId must be at least 8 characters",
                "startedAt must be at least 10 characters",
                "updatedAt must be at least 10 characters",
            ),
        )
        run_validator_case(root, base, "valid-v3-bootstrap", v3_event(), True)
        run_validator_case(
            root,
            base,
            "v3-bad-fingerprint",
            v3_event(fingerprint="not-a-digest"),
            False,
            ("fingerprint must be 64 lowercase hex characters",),
        )
        run_validator_case(
            root,
            base,
            "v3-extra-field",
            v3_event(unexpected="field"),
            False,
            ("unexpected V3 field",),
        )


def check_periodic_checker(root: Path) -> None:
    checker = root / "scripts" / "check-work-items-state.py"
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        item = base / "work-items" / "active" / "valid"
        (item / "reviews").mkdir(parents=True)
        (item / "status.md").write_text(STATUS_TEXT, encoding="utf-8")
        (item / "reviews" / "qa.md").write_text("# QA\n\nGate: PASS\n", encoding="utf-8")
        (item / "agent-runs.jsonl").write_text(json.dumps(ledger_event(workItem="valid")) + "\n", encoding="utf-8")

        proc = subprocess.run(
            [sys.executable, str(checker), "--root", str(base), "--stale-hours", "24", "--now", "2026-05-03T15:00:00Z"],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if proc.returncode != 0:
            raise AssertionError(f"periodic checker should pass:\n{proc.stdout}")
        require("RESULT: PASS" in proc.stdout, f"periodic checker output missed pass result:\n{proc.stdout}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Orchestrarium repository root")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    check_schema(root)
    check_validator(root)
    check_periodic_checker(root)
    check_recovery_fixture_and_runtime(root)
    check_recovery_documentation(root)
    check_legacy_migration_contract(root)
    check_legacy_migration_diff_guard(root)
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
