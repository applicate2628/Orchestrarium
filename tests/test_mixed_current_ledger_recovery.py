"""Mixed current-ledger recovery keeps physical history and typed authority separate."""

from __future__ import annotations

import hashlib
import json
import copy
import subprocess
import sys
from pathlib import Path
import pytest

from tests.test_invalid_current_suffix_disposition import disposition
from tests.test_invalid_current_suffix_disposition import load_writer
from tests.test_legacy_obligation_migration import apply_anchor, load_validator
from tests.test_legacy_obligation_migration import load_script, LIFECYCLE
from tests.test_work_item_state_validator import minimal_staged_status


def _line(event: dict) -> bytes:
    return json.dumps(event, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _mixed_candidate(item: Path) -> tuple[bytes, bytes, dict, dict]:
    item.mkdir(parents=True)
    (item / "implementation.md").write_text("# Evidence\n", encoding="utf-8")
    legacy = {
        "schemaVersion": 1, "runId": "legacy-pass-001", "workItem": item.name,
        "role": "lead", "executionRole": "main", "status": "completed",
        "gate": "PASS", "scope": ["legacy result"],
        "artifact": "implementation.md",
        "evidence": [{"kind": "artifact", "ref": "implementation.md"}],
        "startedAt": "2026-09-08T00:00:00Z", "updatedAt": "2026-09-08T00:00:00Z",
    }
    launch = {
        "schemaVersion": 2, "runId": "review-launch-001", "workItem": item.name,
        "role": "qa-engineer", "executionRole": "internal", "status": "running",
        "gate": "none", "scope": ["implementation.md"], "eventKind": "launch",
        "startedAt": "2026-09-08T00:01:00Z", "updatedAt": "2026-09-08T00:01:00Z",
    }
    revise = {
        **launch, "runId": "review-revise-001", "eventKind": "terminal",
        "status": "completed", "gate": "REVISE", "launchRunId": launch["runId"],
        "findingClass": "old-private-class", "lane": "qa", "effort": "high",
        "artifact": "implementation.md",
        "evidence": [{"kind": "artifact", "ref": "implementation.md"}],
        "updatedAt": "2026-09-08T00:02:00Z",
    }
    orphan = {
        **launch, "runId": "orphan-blocked-001", "eventKind": "terminal",
        "status": "completed", "gate": "BLOCKED", "launchRunId": "missing-launch-001",
        "updatedAt": "2026-09-08T00:03:00Z",
    }
    migration = apply_anchor(revise, _sha(_line(revise).rstrip(b"\n")),
        runId="migration-apply-001", workItem=item.name)
    recovery = disposition(5, _line(orphan), run_id="dispose-orphan-001",
        target_run_id=orphan["runId"])
    recovery["workItem"] = item.name
    before = b"".join(map(_line, (legacy, launch, revise, migration, orphan)))
    return before, before + _line(recovery), revise, orphan


def _raw_mixed_request(item: Path) -> tuple[bytes, dict]:
    _before, candidate, revise, orphan = _mixed_candidate(item)
    events = [json.loads(line) for line in candidate.splitlines()]
    raw = b"".join(map(_line, (events[0], events[1], revise, orphan)))
    request = {
        "schemaVersion": 1,
        "operationId": "mixed-recovery-001",
        "recordedAt": "2026-09-08T02:05:00Z",
        "workItem": f"work-items/active/{item.name}",
        "expectedLedgerSha256": _sha(raw),
        "targets": [
            {
                "action": "migrate-invalid-finding-class",
                "rawLineOrdinal": 3,
                "runId": revise["runId"],
                "eventBodySha256": _sha(_line(revise).rstrip(b"\n")),
                "launchRunId": revise["launchRunId"],
            },
            {
                "action": "dispose-invalid-terminal",
                "rawLineOrdinal": 4,
                "runId": orphan["runId"],
                "physicalLineSha256": _sha(_line(orphan)),
                "launchRunId": orphan["launchRunId"],
            },
        ],
    }
    (item / "agent-runs.jsonl").write_bytes(raw)
    return raw, request


def _neutral_terminal(launch: dict, **overrides) -> dict:
    terminal = {
        **launch, "runId": "neutral-terminal-001", "eventKind": "terminal",
        "launchRunId": launch["runId"], "status": "completed", "gate": "none",
        "startedAt": "2026-09-08T00:04:00Z", "updatedAt": "2026-09-08T00:04:00Z",
    }
    terminal.update(overrides)
    return terminal


def test_migrated_neutral_settlement_preserves_finding_and_authority(tmp_path: Path) -> None:
    """A migrated finding cannot count as, or prevent, one neutral settlement."""
    validator = load_validator()
    item = tmp_path / "work-items" / "active" / "mixed-item"
    _before, candidate, revise, _orphan = _mixed_candidate(item)
    events = [json.loads(line) for line in candidate.splitlines()]
    neutral = _neutral_terminal(events[1])
    ledger = item / "agent-runs.jsonl"
    ledger.write_bytes(candidate + _line(neutral))
    captured: list = []
    assert validator.validate_work_item(
        item, strict_revise=False, validate_status_file=False,
        obligation_state_out=captured,
    ) == []
    assert [row.run_id for row in captured[0].open_revise] == [revise["runId"]]
    context = validator.load_effective_ledger_view(
        tmp_path, item, f"work-items/active/{item.name}/agent-runs.jsonl",
    )
    errors: list[str] = []
    _active, validity, findings, launches = validator._reduce_effective_current_state(
        context.rows, item, errors, None, context=context,
    )
    assert errors == []
    assert launches == []
    assert [event["runId"] for event in findings] == [revise["runId"]]
    by_id = {row.event["runId"]: validity[pos].authority
             for pos, row in enumerate(context.rows)}
    assert by_id[revise["runId"]] == validator.LedgerAuthorityV1(False, False, True, False, False)
    assert by_id[neutral["runId"]] == validator.LedgerAuthorityV1(False, True, False, False, False)
    strict = validator.validate_work_item(item, validate_status_file=False)
    assert any(f"open REVISE obligation: {revise['runId']}" in error for error in strict)
    assert not any("unsettled launch" in error for error in strict)
    assert ledger.read_bytes().startswith(candidate)


@pytest.mark.parametrize("mutation", (
    "pass", "revise", "cancelled", "finding", "authorizing", "metadata",
    "duplicate", "before-migration",
))
def test_migrated_neutral_relation_rejects_other_terminals(tmp_path: Path, mutation: str) -> None:
    """Only one neutral, later, exact-launch terminal can coexist with migration."""
    validator = load_validator()
    item = tmp_path / "work-items" / "active" / "mixed-item"
    _before, candidate, _revise, _orphan = _mixed_candidate(item)
    events = [json.loads(line) for line in candidate.splitlines()]
    neutral = _neutral_terminal(events[1])
    if mutation == "pass":
        neutral.update(gate="PASS", artifact="implementation.md",
                       evidence=[{"kind": "artifact", "ref": "implementation.md"}])
    elif mutation == "revise":
        neutral.update(gate="REVISE", findingClass="correctness", lane="qa", effort="high")
    elif mutation == "cancelled":
        neutral["status"] = "cancelled"
    elif mutation == "finding":
        neutral["findingClass"] = "correctness"
    elif mutation == "authorizing":
        neutral["authorizing"] = True
    elif mutation == "metadata":
        neutral["role"] = "architecture-reviewer"
    events.append(neutral)
    if mutation == "duplicate":
        events.append({**neutral, "runId": "neutral-terminal-002"})
    elif mutation == "before-migration":
        events.insert(3, events.pop())
    raw = b"".join(map(_line, events))
    (item / "agent-runs.jsonl").write_bytes(raw)
    errors = validator.validate_work_item(item, strict_revise=False, validate_status_file=False)
    assert errors, mutation
    assert any("migration target launch" in error for error in errors), errors
    assert (item / "agent-runs.jsonl").read_bytes() == raw


def test_migrated_neutral_revoke_restores_original_diagnostic(tmp_path: Path) -> None:
    """Revocation remains valid but cannot turn invalid history into terminal authority."""
    validator = load_validator()
    item = tmp_path / "work-items" / "active" / "mixed-item"
    _before, candidate, revise, _orphan = _mixed_candidate(item)
    events = [json.loads(line) for line in candidate.splitlines()]
    apply = events[3]
    apply_sha = _sha(_line(apply).rstrip(b"\n"))
    revoke = {
        **{key: value for key, value in apply.items() if key not in {
            "migratesRunId", "migratesEventSha256", "replacementEvent", "normalizationKind",
        }},
        "runId": "migration-revoke-001", "migrationAction": "revoke",
        "revokesMigrationRunId": apply["runId"], "revokesMigrationEventSha256": apply_sha,
        "evidence": [{"kind": "manual-check", "ref": f"revoke {apply['runId']} {apply_sha}"}],
        "startedAt": "2026-09-08T00:05:00Z", "updatedAt": "2026-09-08T00:05:00Z",
    }
    raw = candidate + _line(_neutral_terminal(events[1])) + _line(revoke)
    ledger = item / "agent-runs.jsonl"
    ledger.write_bytes(raw)
    metadata: list[dict] = []
    errors: list[str] = []
    rows = validator.load_jsonl(ledger, errors, metadata)
    effective, counters, projection_errors = validator.project_legacy_obligation_migrations(rows, metadata, item)
    assert errors == projection_errors == []
    assert counters["revoke"] == 1 and counters["projected"] == 0
    assert next(row for row in effective if row["runId"] == revise["runId"]) == revise
    context = validator.load_effective_ledger_view(
        tmp_path, item, f"work-items/active/{item.name}/agent-runs.jsonl",
    )
    errors = []
    _active, validity, _findings, launches = validator._reduce_effective_current_state(
        context.rows, item, errors, None, context=context,
    )
    assert any("findingClass" in error for error in errors), errors
    assert not any("duplicate terminal" in error for error in errors), errors
    assert launches == []
    by_id = {row.event["runId"]: validity[pos].authority for pos, row in enumerate(context.rows)}
    assert by_id[revise["runId"]].terminal_eligible is False
    assert by_id["neutral-terminal-001"].terminal_eligible is True
    assert ledger.read_bytes() == raw


def test_mixed_projection_preserves_authority_and_obligations(tmp_path: Path) -> None:
    """Removing the mixed projection or giving disposed terminals authority fails."""
    validator = load_validator()
    item = tmp_path / "work-items" / "active" / "mixed-item"
    before, candidate, revise, orphan = _mixed_candidate(item)
    ledger = item / "agent-runs.jsonl"
    ledger.write_bytes(candidate)
    captured: list = []
    errors = validator.validate_work_item(
        item, strict_revise=False, validate_status_file=False,
        obligation_state_out=captured,
    )
    assert errors == []
    assert ledger.read_bytes().startswith(before)
    assert len(captured) == 1
    assert [row.run_id for row in captured[0].open_revise] == [revise["runId"]]
    assert captured[0].open_revise[0].raw_line_ordinal == 3
    assert captured[0].open_revise[0].source_kind == "migration-replaced"
    assert all(row.run_id != orphan["runId"] for row in captured[0].open_revise)
    selected = f"work-items/active/{item.name}/agent-runs.jsonl"
    context = validator.load_effective_ledger_view(tmp_path, item, selected)
    assert context.observation.diagnostics == ()
    by_id = {row.event["runId"]: row for row in context.rows}
    assert by_id[revise["runId"]].authority == validator._NO_LEDGER_AUTHORITY
    reader_errors: list[str] = []
    _active, validity, reader_revise, _launches = validator._reduce_effective_current_state(
        context.rows, item, reader_errors, None, context=context,
    )
    assert reader_errors == []
    assert [event["runId"] for event in reader_revise] == [revise["runId"]]
    identities = {row.event["runId"]: row for row in context.rows}
    revise_axes = validity[context.rows.index(identities[revise["runId"]])].authority
    orphan_axes = validity[context.rows.index(identities[orphan["runId"]])].authority
    assert revise_axes == validator.LedgerAuthorityV1(False, False, True, False, False)
    assert orphan_axes == validator._NO_LEDGER_AUTHORITY
    strict = validator.validate_work_item(item, validate_status_file=False)
    assert any(f"open REVISE obligation: {revise['runId']}" in error for error in strict)


def test_mixed_admission_refuses_ambiguous_targets_and_extra_defects(tmp_path: Path) -> None:
    """Dropping any physical-identity, disjointness, or relation check fails this test."""
    validator = load_validator()
    item = tmp_path / "work-items" / "active" / "mixed-item"
    _before, candidate, _revise, _orphan = _mixed_candidate(item)
    base = [json.loads(line) for line in candidate.splitlines()]
    cases: dict[str, list[dict]] = {}

    duplicate = copy.deepcopy(base)
    duplicate.append({**duplicate[-1], "runId": "dispose-orphan-002"})
    cases["duplicate disposition"] = duplicate

    collision = copy.deepcopy(base)
    collision[4]["runId"] = "REVIEW-REVISE-001"
    cases["casefold collision"] = collision

    v1_target = copy.deepcopy(base)
    v1_target[-1]["invalidatesRawLineOrdinal"] = 1
    cases["V1 target"] = v1_target

    control_target = copy.deepcopy(base)
    control_target[-1]["invalidatesRawLineOrdinal"] = 4
    cases["control target"] = control_target

    wrong_hash = copy.deepcopy(base)
    wrong_hash[-1]["invalidatesEventSha256"] = "0" * 64
    cases["wrong digest"] = wrong_hash

    no_launch = copy.deepcopy(base)
    no_launch[2]["launchRunId"] = "unknown-launch"
    no_launch[3]["migratesEventSha256"] = _sha(_line(no_launch[2]).rstrip(b"\n"))
    no_launch[3]["replacementEvent"]["launchRunId"] = "unknown-launch"
    no_launch[3]["evidence"][0]["ref"] = (
        f"invalid-finding-class {no_launch[2]['runId']} "
        f"{no_launch[3]['migratesEventSha256']} -> legacy-unclassified"
    )
    cases["missing migration launch"] = no_launch

    extra_defect = copy.deepcopy(base)
    extra_defect[0]["unrecognizedField"] = True
    cases["unrelated defect"] = extra_defect

    ledger = item / "agent-runs.jsonl"
    for label, events in cases.items():
        raw = b"".join(map(_line, events))
        ledger.write_bytes(raw)
        errors = validator.validate_work_item(
            item, strict_revise=False, validate_status_file=False,
        )
        assert errors, label
        assert ledger.read_bytes() == raw, label


def test_no_apply_rebinds_and_preserves_files(tmp_path: Path) -> None:
    """A no-apply that writes or trusts a stale digest or relation fails."""
    lifecycle = load_script(LIFECYCLE, "mixed_recovery_lifecycle")
    item = tmp_path / "work-items" / "active" / "mixed-item"
    raw, request = _raw_mixed_request(item)
    (item / "status.md").write_text("# Status\n", encoding="utf-8")
    status = (item / "status.md").read_bytes()
    before_names = {path.name for path in item.iterdir()}
    result = lifecycle.recover_mixed_current_ledger(
        tmp_path, _line(request), apply_admitted=False,
    )
    assert result["applied"] is False
    assert result["ledgerBeforeSha256"] == _sha(raw)
    assert result["openReviseRunIds"] == ["review-revise-001"]
    assert (item / "agent-runs.jsonl").read_bytes() == raw
    assert (item / "status.md").read_bytes() == status
    assert {path.name for path in item.iterdir()} == before_names

    request_path = tmp_path / "request.json"
    request_path.write_bytes(_line(request))
    command = subprocess.run(
        [sys.executable, "-B", str(LIFECYCLE), "recover-mixed-current-ledger",
         "--root", str(tmp_path), "--request-file", str(request_path)],
        capture_output=True, text=True, check=False,
    )
    assert command.returncode == 0, command.stdout + command.stderr
    assert json.loads(command.stdout)["applied"] is False
    assert {path.name for path in item.iterdir()} == before_names

    stale = {**request, "expectedLedgerSha256": "0" * 64}
    try:
        lifecycle.recover_mixed_current_ledger(tmp_path, _line(stale))
    except lifecycle.LifecycleError:
        pass
    else:
        raise AssertionError("stale ledger digest was admitted")
    wrong_relation = copy.deepcopy(request)
    wrong_relation["targets"][0]["launchRunId"] = "forged-launch"
    try:
        lifecycle.recover_mixed_current_ledger(tmp_path, _line(wrong_relation))
    except lifecycle.LifecycleError:
        pass
    else:
        raise AssertionError("changed launch relation was admitted")
    for target_index, digest_field in ((0, "eventBodySha256"), (1, "physicalLineSha256")):
        changed = copy.deepcopy(request)
        changed["targets"][target_index][digest_field] = "0" * 64
        with pytest.raises(lifecycle.LifecycleError):
            lifecycle.recover_mixed_current_ledger(tmp_path, _line(changed))
    assert (item / "agent-runs.jsonl").read_bytes() == raw
    assert {path.name for path in item.iterdir()} == before_names


def test_history_failure_cleanup_respects_ownership(tmp_path: Path) -> None:
    """Handled pre-append failure cannot orphan a newly owned history blob."""
    lifecycle = load_script(LIFECYCLE, "mixed_history_lifecycle")
    item = tmp_path / "work-items" / "active" / "mixed-item"
    raw, request = _raw_mixed_request(item)
    baseline = {path.name for path in item.iterdir()}
    history = item / f"agent-runs.history.{_sha(raw)}.jsonl"
    for preexisting in (False, True):
        if preexisting:
            history.write_bytes(raw)
        with pytest.raises(lifecycle.LifecycleError):
            lifecycle.recover_mixed_current_ledger(
                tmp_path, _line(request), apply_admitted=True,
                inject_failure="post-history-publish",
            )
        assert (item / "agent-runs.jsonl").read_bytes() == raw
        assert history.exists() is preexisting
        assert {path.name for path in item.iterdir()} == (
            baseline | ({history.name} if preexisting else set())
        )


def test_history_publish_then_helper_error_cleans_new_blob_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A publisher error after create-once link cannot orphan owned history."""
    for preexisting in (False, True):
        root = tmp_path / str(preexisting)
        lifecycle = load_script(LIFECYCLE, f"mixed_history_return_{preexisting}")
        item = root / "work-items" / "active" / "mixed-item"
        raw, request = _raw_mixed_request(item)
        writer = lifecycle._load_agent_run_ledger()
        history = item / f"agent-runs.history.{_sha(raw)}.jsonl"
        if preexisting:
            history.write_bytes(raw)
        publish = writer._publish_noncanonical_history_blob

        def published_then_failed(*args):
            publish(*args)
            raise OSError("injected after create-once publication before helper return")

        with monkeypatch.context() as patcher:
            patcher.setattr(writer, "_publish_noncanonical_history_blob", published_then_failed)
            with pytest.raises(lifecycle.LifecycleError):
                lifecycle.recover_mixed_current_ledger(
                    root, _line(request), apply_admitted=True,
                )
        assert (item / "agent-runs.jsonl").read_bytes() == raw
        assert not (item / "agent-runs.jsonl.tmp").exists()
        assert history.exists() is preexisting
        if preexisting:
            assert history.read_bytes() == raw


def test_crash_replay_and_receipt_reconstruction(tmp_path: Path) -> None:
    """Exact pre-append replay and post-append receipt repair never append twice."""
    lifecycle = load_script(LIFECYCLE, "mixed_replay_lifecycle")
    item = tmp_path / "work-items" / "active" / "mixed-item"
    raw, request = _raw_mixed_request(item)
    with pytest.raises(KeyboardInterrupt):
        lifecycle.recover_mixed_current_ledger(
            tmp_path, _line(request), apply_admitted=True,
            inject_failure="crash-post-history",
        )
    assert (item / "agent-runs.jsonl").read_bytes() == raw
    assert (item / f"agent-runs.history.{_sha(raw)}.jsonl").read_bytes() == raw
    first = lifecycle.recover_mixed_current_ledger(
        tmp_path, _line(request), apply_admitted=True,
    )
    assert first["applied"] is True
    candidate = (item / "agent-runs.jsonl").read_bytes()
    assert candidate.startswith(raw)
    receipt = item / f"agent-runs.mixed.{request['operationId']}.receipt.json"
    assert receipt.is_file()
    receipt.unlink()
    inspection = lifecycle.recover_mixed_current_ledger(
        tmp_path, _line(request), apply_admitted=False,
    )
    assert inspection["applied"] is False
    assert not receipt.exists()
    assert (item / "agent-runs.jsonl").read_bytes() == candidate
    replay = lifecycle.recover_mixed_current_ledger(
        tmp_path, _line(request), apply_admitted=True,
    )
    assert replay["replay"] is True
    assert (item / "agent-runs.jsonl").read_bytes() == candidate
    assert receipt.is_file()


def test_partial_suffix_or_drift_refuses(tmp_path: Path) -> None:
    """A partial or conflicting suffix is preserved for diagnosis, never truncated."""
    lifecycle = load_script(LIFECYCLE, "mixed_drift_lifecycle")
    item = tmp_path / "work-items" / "active" / "mixed-item"
    raw, request = _raw_mixed_request(item)
    lifecycle.recover_mixed_current_ledger(
        tmp_path, _line(request), apply_admitted=True,
    )
    ledger = item / "agent-runs.jsonl"
    committed = ledger.read_bytes()
    receipt = item / f"agent-runs.mixed.{request['operationId']}.receipt.json"
    assert receipt.is_file()
    for drift in (raw + committed[len(raw):].splitlines(keepends=True)[0],
                  committed + b'{"runId":"conflict"}\n'):
        ledger.write_bytes(drift)
        with pytest.raises(lifecycle.LifecycleError):
            lifecycle.recover_mixed_current_ledger(
                tmp_path, _line(request), apply_admitted=True,
            )
        assert ledger.read_bytes() == drift
    ledger.write_bytes(committed)


def test_post_publish_writer_error_preserves_committed_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A post-replace exception cannot cause cleanup of committed history."""
    lifecycle = load_script(LIFECYCLE, "mixed_post_replace_lifecycle")
    item = tmp_path / "work-items" / "active" / "mixed-item"
    raw, request = _raw_mixed_request(item)
    writer = lifecycle._load_agent_run_ledger()
    replace = writer._replace_exact_staging_file

    def published_then_failed(*args):
        replace(*args)
        raise OSError("injected post-publication readback failure")

    monkeypatch.setattr(writer, "_replace_exact_staging_file", published_then_failed)
    with pytest.raises(lifecycle.LifecycleError):
        lifecycle.recover_mixed_current_ledger(
            tmp_path, _line(request), apply_admitted=True,
        )
    ledger = item / "agent-runs.jsonl"
    committed = ledger.read_bytes()
    assert committed.startswith(raw) and committed != raw
    history = item / f"agent-runs.history.{_sha(raw)}.jsonl"
    assert history.read_bytes() == raw
    assert not (item / f"agent-runs.mixed.{request['operationId']}.receipt.json").exists()
    monkeypatch.setattr(writer, "_replace_exact_staging_file", replace)
    replay = lifecycle.recover_mixed_current_ledger(
        tmp_path, _line(request), apply_admitted=True,
    )
    assert replay["replay"] is True
    assert ledger.read_bytes() == committed


def test_valid_schema_orphan_terminal_is_disposed_without_a_launch(tmp_path: Path) -> None:
    """An individually valid orphan cannot become terminal authority."""
    lifecycle = load_script(LIFECYCLE, "mixed_orphan_lifecycle")
    item = tmp_path / "work-items" / "active" / "mixed-item"
    raw, request = _raw_mixed_request(item)
    rows = [json.loads(line) for line in raw.splitlines()]
    rows[3]["gate"] = "none"
    orphan_errors: list[str] = []
    load_validator().validate_event(rows[3], item, set(), orphan_errors)
    assert orphan_errors == []
    raw = b"".join(map(_line, rows))
    (item / "agent-runs.jsonl").write_bytes(raw)
    request["expectedLedgerSha256"] = _sha(raw)
    request["targets"][1]["physicalLineSha256"] = _sha(_line(rows[3]))
    result = lifecycle.recover_mixed_current_ledger(
        tmp_path, _line(request), apply_admitted=True,
    )
    assert result["applied"] is True
    assert result["targets"][1]["afterAuthority"] == dict.fromkeys(
        ("launchEligible", "terminalEligible", "reviseTargetEligible",
         "closerEligible", "artifactEvidenceEligible"), False,
    )


def test_mixed_orphan_only_disposition_needs_no_migration(tmp_path: Path) -> None:
    """Orphan disposal depends on mixed physical history, not another repaired row."""
    lifecycle = load_script(LIFECYCLE, "mixed_orphan_only_lifecycle")
    item = tmp_path / "work-items" / "active" / "mixed-item"
    raw, request = _raw_mixed_request(item)
    rows = [json.loads(line) for line in raw.splitlines()]
    orphan = {**rows[3], "gate": "none"}
    mixed = b"".join(map(_line, (rows[0], rows[1], orphan)))
    ledger = item / "agent-runs.jsonl"
    ledger.write_bytes(mixed)
    request["expectedLedgerSha256"] = _sha(mixed)
    request["targets"] = [{
        "action": "dispose-invalid-terminal", "rawLineOrdinal": 3,
        "runId": orphan["runId"], "physicalLineSha256": _sha(_line(orphan)),
        "launchRunId": orphan["launchRunId"],
    }]
    inspected = lifecycle.recover_mixed_current_ledger(
        tmp_path, _line(request), apply_admitted=False,
    )
    assert inspected["applied"] is False
    assert ledger.read_bytes() == mixed
    applied = lifecycle.recover_mixed_current_ledger(
        tmp_path, _line(request), apply_admitted=True,
    )
    assert applied["applied"] is True
    assert ledger.read_bytes().startswith(mixed)
    assert applied["targets"][0]["afterAuthority"] == dict.fromkeys(
        ("launchEligible", "terminalEligible", "reviseTargetEligible",
         "closerEligible", "artifactEvidenceEligible"), False,
    )

    v2_only = b"".join(map(_line, (rows[1], orphan)))
    ledger.write_bytes(v2_only)
    request["operationId"] = "mixed-orphan-v2-only-001"
    request["expectedLedgerSha256"] = _sha(v2_only)
    request["targets"][0]["rawLineOrdinal"] = 2
    with pytest.raises(lifecycle.LifecycleError):
        lifecycle.recover_mixed_current_ledger(
            tmp_path, _line(request), apply_admitted=False,
        )
    assert ledger.read_bytes() == v2_only


def test_preexisting_valid_revise_terminal_still_settles_its_launch(tmp_path: Path) -> None:
    """Conservation uses actual post-reduction terminal authority, not gate labels."""
    lifecycle = load_script(LIFECYCLE, "mixed_valid_review_lifecycle")
    item = tmp_path / "work-items" / "active" / "mixed-item"
    raw, request = _raw_mixed_request(item)
    rows = [json.loads(line) for line in raw.splitlines()]
    launch = {**rows[1], "runId": "earlier-launch-001"}
    revise = {
        **rows[2], "runId": "earlier-revise-001",
        "launchRunId": launch["runId"], "findingClass": "correctness",
    }
    raw = b"".join(map(_line, [rows[0], launch, revise, *rows[1:]]))
    (item / "agent-runs.jsonl").write_bytes(raw)
    request["expectedLedgerSha256"] = _sha(raw)
    for target in request["targets"]:
        target["rawLineOrdinal"] += 2
    result = lifecycle.recover_mixed_current_ledger(
        tmp_path, _line(request), apply_admitted=False,
    )
    assert result["applied"] is False
    assert set(result["openReviseRunIds"]) == {
        "earlier-revise-001", "review-revise-001",
    }
    assert "earlier-launch-001" in result["settledLaunchRunIds"]
    assert "earlier-launch-001" not in result["openLaunchRunIds"]


def test_ordinary_append_and_strict_close_after_recovery(tmp_path: Path) -> None:
    """A recovered current ledger stays writable while protected REVISE blocks close."""
    lifecycle = load_script(LIFECYCLE, "mixed_append_lifecycle")
    item = tmp_path / "work-items" / "active" / "mixed-item"
    raw, request = _raw_mixed_request(item)
    status = item / "status.md"
    status.write_text(minimal_staged_status(), encoding="utf-8")
    status_bytes = status.read_bytes()
    lifecycle.recover_mixed_current_ledger(
        tmp_path, _line(request), apply_admitted=True,
    )
    ledger = item / "agent-runs.jsonl"
    recovered = ledger.read_bytes()
    writer = load_writer()
    validator = writer.load_validator()
    launch = {
        "schemaVersion": 2, "runId": "fresh-launch-001", "workItem": item.name,
        "role": "qa-engineer", "executionRole": "internal", "status": "running",
        "gate": "none", "scope": ["post recovery"], "eventKind": "launch",
        "startedAt": "2026-09-08T03:00:00Z", "updatedAt": "2026-09-08T03:00:00Z",
    }
    terminal = {
        **launch, "runId": "fresh-terminal-001", "status": "completed",
        "gate": "none", "eventKind": "terminal",
        "launchRunId": launch["runId"],
        "updatedAt": "2026-09-08T03:01:00Z",
    }
    assert writer._append_event_transaction(item, validator, lambda _previous: launch)
    assert writer._append_event_transaction(item, validator, lambda _previous: terminal)
    after = ledger.read_bytes()
    assert after.startswith(recovered)
    assert (item / f"agent-runs.history.{_sha(raw)}.jsonl").read_bytes() == raw
    assert status.read_bytes() == status_bytes
    assert validator.validate_work_item(item, strict_revise=False, validate_status_file=False) == []
    strict_errors = validator.validate_work_item(item, validate_status_file=False)
    assert any("open REVISE obligation: review-revise-001" in error for error in strict_errors)


def test_mixed_candidate_reduction_is_linear(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Per-target full scans or a second candidate reduction violate this oracle."""

    def measure(count: int) -> tuple[int, int, int, int]:
        lifecycle = load_script(LIFECYCLE, f"mixed_linear_{count}")
        item = tmp_path / str(count) / "work-items" / "active" / "mixed-item"
        item.mkdir(parents=True)
        (item / "implementation.md").write_text("# Evidence\n", encoding="utf-8")
        legacy = {
            "schemaVersion": 1, "runId": "legacy-pass-001", "workItem": item.name,
            "role": "lead", "executionRole": "main", "status": "completed",
            "gate": "PASS", "scope": ["legacy result"],
            "artifact": "implementation.md",
            "evidence": [{"kind": "artifact", "ref": "implementation.md"}],
            "startedAt": "2026-09-08T00:00:00Z", "updatedAt": "2026-09-08T00:00:00Z",
        }
        events = [legacy]
        targets = []
        for number in range(count):
            launch = {
                "schemaVersion": 2, "runId": f"launch-{number:03d}",
                "workItem": item.name, "role": "qa-engineer",
                "executionRole": "internal", "status": "running", "gate": "none",
                "scope": ["implementation.md"], "eventKind": "launch",
                "startedAt": "2026-09-08T00:01:00Z", "updatedAt": "2026-09-08T00:01:00Z",
            }
            revise = {
                **launch, "runId": f"revise-{number:03d}",
                "eventKind": "terminal", "status": "completed", "gate": "REVISE",
                "launchRunId": launch["runId"], "findingClass": "old-private-class",
                "lane": "qa", "effort": "high", "artifact": "implementation.md",
                "evidence": [{"kind": "artifact", "ref": "implementation.md"}],
                "updatedAt": "2026-09-08T00:02:00Z",
            }
            blocked = {
                **launch, "runId": f"blocked-{number:03d}",
                "eventKind": "terminal", "status": "completed", "gate": "BLOCKED",
                "launchRunId": f"missing-{number:03d}",
                "updatedAt": "2026-09-08T00:03:00Z",
            }
            events.extend((launch, revise, blocked))
            targets.extend((
                {"action": "migrate-invalid-finding-class",
                 "rawLineOrdinal": len(events) - 1, "runId": revise["runId"],
                 "eventBodySha256": _sha(_line(revise).rstrip(b"\n")),
                 "launchRunId": launch["runId"]},
                {"action": "dispose-invalid-terminal",
                 "rawLineOrdinal": len(events), "runId": blocked["runId"],
                 "physicalLineSha256": _sha(_line(blocked)),
                 "launchRunId": blocked["launchRunId"]},
            ))
        raw = b"".join(map(_line, events))
        (item / "agent-runs.jsonl").write_bytes(raw)
        request = {
            "schemaVersion": 1, "operationId": f"linear-{count}",
            "recordedAt": "2026-09-08T02:05:00Z",
            "workItem": f"work-items/active/{item.name}",
            "expectedLedgerSha256": _sha(raw), "targets": targets,
        }
        writer = lifecycle._load_agent_run_ledger()
        validator = writer.load_validator()
        counters = {"row_visits": 0, "reductions": 0, "classifications": 0,
                    "relation_lookups": 0}

        class CountedEvents(list):
            def __iter__(self):
                counters["row_visits"] += len(self)
                return super().__iter__()

            def __getitem__(self, key):
                value = super().__getitem__(key)
                counters["row_visits"] += len(value) if isinstance(key, slice) else 1
                return value

        original_rows = validator._row_events
        original_validate = validator.validate_work_item
        original_relation = validator.terminal_has_valid_earlier_launch
        original_classify = lifecycle._mixed_recovery_controls

        def counted_rows(rows):
            value = original_rows(rows)
            return CountedEvents(value) if any(
                row.event.get("eventKind") == "legacy-obligation-migration" for row in rows
            ) else value

        def counted_validate(*args, **kwargs):
            counters["reductions"] += 1
            return original_validate(*args, **kwargs)

        def counted_relation(*args, **kwargs):
            counters["relation_lookups"] += 1
            return original_relation(*args, **kwargs)

        def counted_classify(*args, **kwargs):
            counters["classifications"] += 1
            return original_classify(*args, **kwargs)

        monkeypatch.setattr(validator, "_row_events", counted_rows)
        monkeypatch.setattr(validator, "validate_work_item", counted_validate)
        monkeypatch.setattr(validator, "terminal_has_valid_earlier_launch", counted_relation)
        monkeypatch.setattr(writer, "load_validator", lambda: validator)
        monkeypatch.setattr(lifecycle, "_mixed_recovery_controls", counted_classify)
        result = lifecycle.recover_mixed_current_ledger(
            item.parents[2], _line(request), apply_admitted=False,
        )
        assert result["applied"] is False
        assert len(result["targets"]) == 2 * count
        return (counters["row_visits"], counters["reductions"],
                counters["classifications"], counters["relation_lookups"])

    small = measure(12)
    large = measure(24)
    assert small[1:3] == (1, 1)
    assert large[1:3] == (1, 1)
    assert large[3] <= small[3] * 2 + 4
    assert large[0] <= small[0] * 5 // 2
