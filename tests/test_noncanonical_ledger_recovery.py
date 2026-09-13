import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest


ROOT = Path(__file__).resolve().parents[1]
WRITER = ROOT / "scripts" / "agent-run-ledger.py"
VALIDATOR = ROOT / "scripts" / "validate-work-item-state.py"
RECORDED_AT = "2026-09-10T12:00:00Z"
OPERATION_ID = "noncanonical-history-0001"
HISTORICAL_LINE = (
    b'{"date":"2026-09-10","lane":"example","execution_role":"analyst",'
    b'"result":"historical note"}\n'
)
TWELVE_OBJECT_HISTORY = HISTORICAL_LINE * 12
TWELVE_OBJECT_SHA256 = (
    "578616791fde12605cf2d37d25ed59ba8b7d8cd8121787fd13f93faa62516271"
)


def quick_fix_status() -> str:
    return """---
template: quick-fix
status: active
started: 2026-09-10 12:00
updated: 2026-09-10 12:00
---

- **Task**: Recover a noncanonical historical execution ledger.
- **Current step**: Exercise the lifecycle-owned recovery command.
- **Last result**: Recovery was explicitly admitted for a synthetic fixture.
- **Next action**: Run focused independent Quality Assurance.
"""


def load_validator():
    spec = importlib.util.spec_from_file_location("noncanonical_recovery_validator", VALIDATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_writer():
    spec = importlib.util.spec_from_file_location("noncanonical_recovery_writer", WRITER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def make_item(tmp_path: Path, ledger_bytes: bytes) -> Path:
    item = tmp_path / "work-items" / "active" / "noncanonical-ledger-fixture"
    item.mkdir(parents=True)
    (item / "status.md").write_text(quick_fix_status(), encoding="utf-8")
    (item / "agent-runs.jsonl").write_bytes(ledger_bytes)
    return item


def run_writer(item: Path, *arguments: str, timeout: float = 15.0) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-B", str(WRITER), "--work-item", str(item), *arguments],
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def run_recovery(
    item: Path,
    expected_sha256: str,
    *action: str,
    operation_id: str = OPERATION_ID,
    recorded_at: str = RECORDED_AT,
    timeout: float = 15.0,
) -> subprocess.CompletedProcess[str]:
    return run_writer(
        item,
        "recover-noncanonical-history",
        "--expected-ledger-sha256",
        expected_sha256,
        "--operation-id",
        operation_id,
        "--recorded-at",
        recorded_at,
        *action,
        timeout=timeout,
    )


def file_snapshot(item: Path) -> dict[str, bytes]:
    return {
        path.relative_to(item).as_posix(): path.read_bytes()
        for path in sorted(item.rglob("*"))
        if path.is_file()
    }


def history_path(item: Path, sha256: str) -> Path:
    return item / f"agent-runs.history.{sha256.lower()}.jsonl"


def load_ledger(item: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (item / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()
    ]


def assert_no_owned_temps(item: Path) -> None:
    assert list(item.glob(".agent-runs.history.*.tmp")) == []
    assert not (item / "agent-runs.jsonl.tmp").exists()
    assert not (item / "agent-runs.jsonl.lock").exists()


class _NoUnboundedReadStream:
    def __init__(self, stream, readline_sizes: list[int]) -> None:
        self._stream = stream
        self._readline_sizes = readline_sizes

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self._stream.close()

    def readline(self, size: int = -1) -> bytes:
        assert size >= 0
        self._readline_sizes.append(size)
        return self._stream.readline(size)

    def read(self, *args, **kwargs):
        raise AssertionError("noncanonical acquisition called read()")


def _read_routes_with_tiny_validator(tmp_path: Path, raw: bytes):
    writer = load_writer()
    source = tmp_path / "agent-runs.jsonl"
    history = tmp_path / "agent-runs.history.tiny.jsonl"
    source.write_bytes(raw)
    history.write_bytes(raw)
    validator = SimpleNamespace(MAX_LEDGER_LINE_BYTES=4, MAX_LEDGER_EVENTS=1)
    original_fdopen = writer.os.fdopen
    readline_sizes: list[int] = []

    def fdopen_without_read(descriptor, *args, **kwargs):
        return _NoUnboundedReadStream(
            original_fdopen(descriptor, *args, **kwargs), readline_sizes
        )

    return writer, source, history, validator, readline_sizes, fdopen_without_read


@pytest.mark.parametrize("route", ("source", "history"))
def test_noncanonical_raw_readers_reject_tiny_line_limit_without_unbounded_read(
    tmp_path: Path, route: str
) -> None:
    writer, source, history, validator, readline_sizes, fdopen_without_read = (
        _read_routes_with_tiny_validator(tmp_path, b"12345\n")
    )

    with (
        patch.object(writer, "load_validator", return_value=validator),
        patch.object(writer.os, "fdopen", side_effect=fdopen_without_read),
    ):
        with pytest.raises(writer.LedgerNoncanonicalRecoveryError) as raised:
            if route == "source":
                writer._noncanonical_read_owned_bytes(source, failure_id="DRIFT")
            else:
                writer._read_exact_history_blob(history, digest(b"12345\n"))

    assert raised.value.failure_id == (
        f"WI-LEDGER-NONCANONICAL-{'DRIFT' if route == 'source' else 'HISTORY-CONFLICT'}"
    )
    assert readline_sizes == [validator.MAX_LEDGER_LINE_BYTES + 3]


def test_noncanonical_raw_reader_rejects_tiny_blank_padding_before_aggregate_growth(
    tmp_path: Path,
) -> None:
    writer, source, _history, validator, readline_sizes, fdopen_without_read = (
        _read_routes_with_tiny_validator(tmp_path, b"\n" * 7)
    )

    with (
        patch.object(writer, "load_validator", return_value=validator),
        patch.object(writer.os, "fdopen", side_effect=fdopen_without_read),
    ):
        with pytest.raises(writer.LedgerNoncanonicalRecoveryError) as raised:
            writer._noncanonical_read_owned_bytes(source, failure_id="DRIFT")

    assert raised.value.failure_id == "WI-LEDGER-NONCANONICAL-DRIFT"
    assert readline_sizes == [validator.MAX_LEDGER_LINE_BYTES + 3] * 7


def test_noncanonical_raw_readers_preserve_ordinary_opaque_physical_bytes(
    tmp_path: Path,
) -> None:
    writer = load_writer()
    raw = b"\r\n \t\r\n{\"date\":\"2026-09-10\",\"note\":\"opaque\"}\r\nlast"
    source = tmp_path / "agent-runs.jsonl"
    history = tmp_path / "agent-runs.history.opaque.jsonl"
    source.write_bytes(raw)
    history.write_bytes(raw)

    assert writer._noncanonical_read_owned_bytes(source, failure_id="DRIFT") == raw
    assert writer._read_exact_history_blob(history, digest(raw)) == raw


def test_preflight_is_read_only_and_accepts_uppercase_digest(tmp_path: Path) -> None:
    item = make_item(tmp_path, TWELVE_OBJECT_HISTORY)
    before = file_snapshot(item)

    result = run_recovery(item, TWELVE_OBJECT_SHA256.upper())

    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: PASS recover-noncanonical-history action=preflight" in result.stdout
    assert result.stderr == ""
    assert file_snapshot(item) == before
    assert not history_path(item, TWELVE_OBJECT_SHA256).exists()
    assert_no_owned_temps(item)


def test_preflight_rejects_invalid_status_without_writing(tmp_path: Path) -> None:
    item = make_item(tmp_path, TWELVE_OBJECT_HISTORY)
    (item / "status.md").write_text("not a current status\n", encoding="utf-8")
    before = file_snapshot(item)

    result = run_recovery(item, TWELVE_OBJECT_SHA256)

    assert result.returncode == 1
    assert "WI-LEDGER-NONCANONICAL-CANDIDATE-INVALID" in result.stderr
    assert file_snapshot(item) == before
    assert_no_owned_temps(item)


def test_apply_preserves_twelve_objects_and_all_marker_authority_axes_are_false(
    tmp_path: Path,
) -> None:
    assert len(TWELVE_OBJECT_HISTORY) == 1_116
    assert digest(TWELVE_OBJECT_HISTORY) == TWELVE_OBJECT_SHA256
    item = make_item(tmp_path, TWELVE_OBJECT_HISTORY)

    result = run_recovery(
        item,
        TWELVE_OBJECT_SHA256.upper(),
        "--apply-admitted",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: PASS recover-noncanonical-history action=apply" in result.stdout
    assert result.stderr == ""
    assert history_path(item, TWELVE_OBJECT_SHA256).read_bytes() == TWELVE_OBJECT_HISTORY
    events = load_ledger(item)
    assert len(events) == 1
    marker = events[0]
    assert list(marker) == [
        "schemaVersion",
        "runId",
        "workItem",
        "role",
        "executionRole",
        "status",
        "gate",
        "scope",
        "eventKind",
        "startedAt",
        "updatedAt",
        "notes",
    ]
    assert marker == {
        "schemaVersion": 2,
        "runId": f"ledger-history-{OPERATION_ID}",
        "workItem": item.name,
        "role": "lead",
        "executionRole": "main",
        "status": "completed",
        "gate": "none",
        "scope": ["ledger-recovery:noncanonical-history-seal"],
        "eventKind": "standalone",
        "startedAt": RECORDED_AT,
        "updatedAt": RECORDED_AT,
        "notes": (
            f"opaqueHistoryPath=agent-runs.history.{TWELVE_OBJECT_SHA256}.jsonl "
            f"opaqueHistorySha256={TWELVE_OBJECT_SHA256} "
            "opaqueHistoryBytes=1116 authority=none"
        ),
    }
    validator = load_validator()
    errors: list[str] = []
    rows = validator._runtime_rows_from_events(events)
    validity = validator.derive_event_validity(rows, item, errors)
    assert errors == []
    assert len(validity) == 1 and validity[0].current_schema_valid is True
    assert asdict(validity[0].authority) == {
        "launch_eligible": False,
        "terminal_eligible": False,
        "revise_target_eligible": False,
        "closer_eligible": False,
        "artifact_evidence_eligible": False,
    }
    validated = subprocess.run(
        [sys.executable, "-B", str(VALIDATOR), "--work-item", str(item)],
        cwd=ROOT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert validated.returncode == 0, validated.stdout + validated.stderr
    assert_no_owned_temps(item)


def test_normal_append_records_launch_and_terminal_after_recovery(tmp_path: Path) -> None:
    item = make_item(tmp_path, TWELVE_OBJECT_HISTORY)
    recovered = run_recovery(item, TWELVE_OBJECT_SHA256, "--apply-admitted")
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    reviews = item / "reviews"
    reviews.mkdir()
    (reviews / "implementation.md").write_text("Gate: PASS\n", encoding="utf-8")

    launch = run_writer(
        item,
        "append",
        "--run-id",
        "canonical-launch-0001",
        "--role",
        "toolchain-engineer",
        "--execution-role",
        "internal",
        "--status",
        "running",
        "--gate",
        "none",
        "--scope",
        "noncanonical ledger recovery",
        "--event-kind",
        "launch",
        "--started-at",
        "2026-09-10T12:01:00Z",
        "--updated-at",
        "2026-09-10T12:01:00Z",
    )
    assert launch.returncode == 0, launch.stdout + launch.stderr
    terminal = run_writer(
        item,
        "append",
        "--run-id",
        "canonical-terminal-0001",
        "--role",
        "toolchain-engineer",
        "--execution-role",
        "internal",
        "--status",
        "completed",
        "--gate",
        "PASS",
        "--scope",
        "noncanonical ledger recovery",
        "--event-kind",
        "terminal",
        "--launch-run-id",
        "canonical-launch-0001",
        "--artifact",
        "reviews/implementation.md",
        "--evidence",
        "command:focused synthetic recovery test",
        "--started-at",
        "2026-09-10T12:02:00Z",
        "--updated-at",
        "2026-09-10T12:02:00Z",
    )

    assert terminal.returncode == 0, terminal.stdout + terminal.stderr
    assert [event.get("eventKind") for event in load_ledger(item)] == [
        "standalone",
        "launch",
        "terminal",
    ]
    assert history_path(item, TWELVE_OBJECT_SHA256).read_bytes() == TWELVE_OBJECT_HISTORY
    assert_no_owned_temps(item)


def test_generic_status_gate_and_single_v3_keys_remain_opaque(tmp_path: Path) -> None:
    opaque = b"".join(
        json.dumps(row, separators=(",", ":")).encode("ascii") + b"\n"
        for row in (
            {"status": "completed"},
            {"gate": "PASS"},
            {"eventId": "event-only"},
            {"operationId": "operation-only"},
            {"runId": "1234567"},
        )
    )
    item = make_item(tmp_path, opaque)

    result = run_recovery(item, digest(opaque), "--apply-admitted")

    assert result.returncode == 0, result.stdout + result.stderr
    assert history_path(item, digest(opaque)).read_bytes() == opaque
    assert_no_owned_temps(item)


@pytest.mark.parametrize(
    ("row", "failure_id"),
    (
        ({"schemaVersion": 1}, "WI-LEDGER-NONCANONICAL-CURRENT-EVENT"),
        ({"schemaVersion": 2}, "WI-LEDGER-NONCANONICAL-CURRENT-EVENT"),
        ({"schemaVersion": 3}, "WI-LEDGER-NONCANONICAL-CURRENT-EVENT"),
        ({"runId": "12345678"}, "WI-LEDGER-NONCANONICAL-IDENTITY-BEARING"),
        (
            {
                "eventId": "v3-event-0001",
                "operationId": "v3-operation-0001",
                "fingerprint": "a" * 64,
                "priorHead": "GENESIS",
            },
            "WI-LEDGER-NONCANONICAL-IDENTITY-BEARING",
        ),
    ),
)
def test_current_schema_or_valid_identity_refuses_without_mutation(
    tmp_path: Path,
    row: dict[str, object],
    failure_id: str,
) -> None:
    raw = json.dumps(row, separators=(",", ":")).encode("ascii") + b"\n"
    item = make_item(tmp_path, raw)
    before = file_snapshot(item)

    result = run_recovery(item, digest(raw), "--apply-admitted")

    assert result.returncode == 1
    assert failure_id in result.stderr
    assert file_snapshot(item) == before
    assert_no_owned_temps(item)


def test_canonical_event_and_mixed_history_refuse_without_mutation(tmp_path: Path) -> None:
    canonical = {
        "schemaVersion": 2,
        "runId": "canonical-event-0001",
        "workItem": "noncanonical-ledger-fixture",
        "role": "lead",
        "executionRole": "main",
        "status": "completed",
        "gate": "none",
        "scope": ["canonical control"],
        "eventKind": "standalone",
        "startedAt": RECORDED_AT,
        "updatedAt": RECORDED_AT,
    }
    canonical_raw = json.dumps(canonical, separators=(",", ":")).encode("ascii") + b"\n"
    for name, raw in (
        ("canonical", canonical_raw),
        ("mixed", b'{"status":"historical"}\n' + canonical_raw),
    ):
        item = make_item(tmp_path / name, raw)
        before = file_snapshot(item)
        result = run_recovery(item, digest(raw), "--apply-admitted")
        assert result.returncode == 1, name
        assert "WI-LEDGER-NONCANONICAL-CURRENT-EVENT" in result.stderr, name
        assert file_snapshot(item) == before, name
        assert_no_owned_temps(item)


@pytest.mark.parametrize(
    "raw",
    (
        b"",
        b"{\n",
        b'{"key":1,"key":2}\n',
        b"\xff\n",
    ),
    ids=("empty", "malformed-json", "duplicate-key", "invalid-utf8"),
)
def test_malformed_history_refuses_without_mutation(tmp_path: Path, raw: bytes) -> None:
    item = make_item(tmp_path, raw)
    before = file_snapshot(item)

    result = run_recovery(item, digest(raw), "--apply-admitted")

    assert result.returncode == 1
    assert "WI-LEDGER-NONCANONICAL-MALFORMED" in result.stderr
    assert file_snapshot(item) == before
    assert_no_owned_temps(item)


def test_oversized_history_refuses_without_mutation(tmp_path: Path) -> None:
    validator = load_validator()
    raw = (
        b'{"value":"'
        + (b"x" * (validator.MAX_LEDGER_LINE_CHARS + 1))
        + b'"}\n'
    )
    item = make_item(tmp_path, raw)
    before = file_snapshot(item)

    result = run_recovery(item, digest(raw), "--apply-admitted")

    assert result.returncode == 1
    assert "WI-LEDGER-NONCANONICAL-DRIFT" in result.stderr
    assert file_snapshot(item) == before
    assert_no_owned_temps(item)


def test_digest_drift_and_held_lock_refuse_without_mutation(tmp_path: Path) -> None:
    drift_item = make_item(tmp_path / "drift", TWELVE_OBJECT_HISTORY)
    drift_before = file_snapshot(drift_item)
    drift = run_recovery(drift_item, "0" * 64, "--apply-admitted")
    assert drift.returncode == 1
    assert "WI-LEDGER-NONCANONICAL-DRIFT" in drift.stderr
    assert file_snapshot(drift_item) == drift_before
    assert_no_owned_temps(drift_item)

    locked_item = make_item(tmp_path / "locked", TWELVE_OBJECT_HISTORY)
    lock = locked_item / "agent-runs.jsonl.lock"
    lock.write_text("pid=synthetic\n", encoding="utf-8")
    locked_before = file_snapshot(locked_item)
    locked = run_recovery(
        locked_item,
        TWELVE_OBJECT_SHA256,
        "--apply-admitted",
        timeout=10.0,
    )
    assert locked.returncode == 1
    assert "WI-LEDGER-NONCANONICAL-LOCKED" in locked.stderr
    assert file_snapshot(locked_item) == locked_before
    assert not history_path(locked_item, TWELVE_OBJECT_SHA256).exists()
    assert list(locked_item.glob(".agent-runs.*.tmp")) == []


def test_strict_controls_refuse_without_mutation(tmp_path: Path) -> None:
    cases = (
        ("bad-operation", {"operation_id": "bad operation"}),
        ("bad-recorded-at", {"recorded_at": "2026-09-10"}),
    )
    for name, overrides in cases:
        item = make_item(tmp_path / name, TWELVE_OBJECT_HISTORY)
        before = file_snapshot(item)
        result = run_recovery(
            item,
            TWELVE_OBJECT_SHA256,
            "--apply-admitted",
            **overrides,
        )
        assert result.returncode == 1, name
        assert file_snapshot(item) == before, name
        assert_no_owned_temps(item)

    both_item = make_item(tmp_path / "both-actions", TWELVE_OBJECT_HISTORY)
    both_before = file_snapshot(both_item)
    both = run_recovery(
        both_item,
        TWELVE_OBJECT_SHA256,
        "--apply-admitted",
        "--rollback-admitted",
    )
    assert both.returncode == 2
    assert file_snapshot(both_item) == both_before
    assert_no_owned_temps(both_item)


def test_interrupted_history_publication_replays_without_duplicate_blob(tmp_path: Path) -> None:
    item = make_item(tmp_path, TWELVE_OBJECT_HISTORY)
    interrupted = run_recovery(
        item,
        TWELVE_OBJECT_SHA256,
        "--apply-admitted",
        "--inject-failure",
        "post-history-publish",
    )
    assert interrupted.returncode == 1
    assert (item / "agent-runs.jsonl").read_bytes() == TWELVE_OBJECT_HISTORY
    assert history_path(item, TWELVE_OBJECT_SHA256).read_bytes() == TWELVE_OBJECT_HISTORY
    assert_no_owned_temps(item)

    replay = run_recovery(item, TWELVE_OBJECT_SHA256, "--apply-admitted")
    assert replay.returncode == 0, replay.stdout + replay.stderr
    assert len(list(item.glob("agent-runs.history.*.jsonl"))) == 1
    assert len(load_ledger(item)) == 1
    assert_no_owned_temps(item)


def test_indeterminate_marker_readback_is_resolved_by_exact_replay(tmp_path: Path) -> None:
    item = make_item(tmp_path, TWELVE_OBJECT_HISTORY)
    interrupted = run_recovery(
        item,
        TWELVE_OBJECT_SHA256,
        "--apply-admitted",
        "--inject-failure",
        "post-ledger-replace-readback",
    )
    assert interrupted.returncode == 1
    assert "WI-LEDGER-NONCANONICAL-READBACK-INDETERMINATE" in interrupted.stderr
    committed = (item / "agent-runs.jsonl").read_bytes()
    assert len(load_ledger(item)) == 1

    replay = run_recovery(item, TWELVE_OBJECT_SHA256, "--apply-admitted")
    assert replay.returncode == 0, replay.stdout + replay.stderr
    assert "replay=true" in replay.stdout
    assert (item / "agent-runs.jsonl").read_bytes() == committed
    assert len(list(item.glob("agent-runs.history.*.jsonl"))) == 1
    assert_no_owned_temps(item)


def test_rollback_restores_history_before_append_and_replays_exactly(tmp_path: Path) -> None:
    item = make_item(tmp_path, TWELVE_OBJECT_HISTORY)
    applied = run_recovery(item, TWELVE_OBJECT_SHA256, "--apply-admitted")
    assert applied.returncode == 0, applied.stdout + applied.stderr

    rolled_back = run_recovery(item, TWELVE_OBJECT_SHA256, "--rollback-admitted")
    assert rolled_back.returncode == 0, rolled_back.stdout + rolled_back.stderr
    assert (item / "agent-runs.jsonl").read_bytes() == TWELVE_OBJECT_HISTORY
    assert history_path(item, TWELVE_OBJECT_SHA256).read_bytes() == TWELVE_OBJECT_HISTORY
    replay = run_recovery(item, TWELVE_OBJECT_SHA256, "--rollback-admitted")
    assert replay.returncode == 0, replay.stdout + replay.stderr
    assert "replay=true" in replay.stdout
    assert (item / "agent-runs.jsonl").read_bytes() == TWELVE_OBJECT_HISTORY
    assert_no_owned_temps(item)


def test_rollback_after_normal_append_refuses_without_mutation(tmp_path: Path) -> None:
    item = make_item(tmp_path, TWELVE_OBJECT_HISTORY)
    applied = run_recovery(item, TWELVE_OBJECT_SHA256, "--apply-admitted")
    assert applied.returncode == 0, applied.stdout + applied.stderr
    appended = run_writer(
        item,
        "append",
        "--run-id",
        "post-recovery-standalone",
        "--role",
        "lead",
        "--execution-role",
        "main",
        "--status",
        "completed",
        "--gate",
        "none",
        "--scope",
        "post-recovery append",
        "--event-kind",
        "standalone",
        "--started-at",
        "2026-09-10T12:03:00Z",
        "--updated-at",
        "2026-09-10T12:03:00Z",
    )
    assert appended.returncode == 0, appended.stdout + appended.stderr
    before = file_snapshot(item)

    rollback = run_recovery(item, TWELVE_OBJECT_SHA256, "--rollback-admitted")

    assert rollback.returncode == 1
    assert "WI-LEDGER-NONCANONICAL-ROLLBACK-NOT-EMPTY" in rollback.stderr
    assert file_snapshot(item) == before
    assert_no_owned_temps(item)
