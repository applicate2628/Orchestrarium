"""Direct regression coverage for immutable archived-ledger dispositions."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check-work-items-state.py"
VALIDATOR = ROOT / "scripts" / "validate-work-item-state.py"


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_validator():
    spec = importlib.util.spec_from_file_location("historical_disposition_validator", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_archived_fixture(root: Path) -> tuple[Path, dict]:
    item = root / "work-items" / "archive" / "2026-08" / "archived-artifact"
    item.mkdir(parents=True)
    recovered = b"recovered historical artifact\n"
    artifact_sha = sha(recovered)
    event = {
        "schemaVersion": 2,
        "runId": "archive-artifact-pass-001",
        "workItem": item.name,
        "role": "qa-engineer",
        "executionRole": "main",
        "status": "completed",
        "gate": "PASS",
        "scope": ["archived evidence"],
        "artifact": "missing-evidence.md",
        "artifactRevision": artifact_sha,
        "evidence": [{"kind": "manual-check", "ref": "historical evidence"}],
        "startedAt": "2026-08-01T00:00:00Z",
        "updatedAt": "2026-08-01T00:00:01Z",
    }
    raw = canonical(event)
    ledger = raw + b"\n"
    (item / "agent-runs.jsonl").write_bytes(ledger)
    work_item = item.relative_to(root).as_posix()
    disposition = {
        "schemaVersion": 2,
        "archiveIdentity": sha(
            b"orchestrarium-archive-v1\0" + work_item.encode("utf-8") + b"\0" + sha(ledger).encode("ascii")
        ),
        "workItem": work_item,
        "ledgerSha256": sha(ledger),
        "rawLineOrdinal": 1,
        "rawLineSha256": sha(raw),
        "runId": event["runId"],
        "eventSha256": sha(canonical(event)),
        "missingPath": event["artifact"],
        "artifactRevisionSha256": artifact_sha,
        "state": "content-recovered",
        "contentBytesBase64": base64.b64encode(recovered).decode("ascii"),
        "contentBytesSha256": artifact_sha,
    }
    disposition["dispositionId"] = sha(
        b"orchestrarium-historical-artifact-disposition-v2\0"
        + b"\0".join(str(disposition[key]).encode("utf-8") for key in (
            "archiveIdentity", "rawLineOrdinal", "rawLineSha256", "eventSha256", "missingPath",
            "artifactRevisionSha256",
        ))
    )
    return item, disposition


def write_disposition(root: Path, disposition: dict, *, filename: str | None = None) -> Path:
    directory = root / "work-items" / "legacy-ledger-historical-dispositions"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (filename or f"{disposition['dispositionId']}.json")
    target.write_bytes(canonical(disposition))
    return target


def active_item(root: Path) -> Path:
    item = root / "work-items" / "active" / "active-control"
    (item / "reviews").mkdir(parents=True)
    (item / "status.md").write_text(
        "# Status\n\n## Current state\n**Primary task status**: open\n\n## Active agents\n- none\n"
        "\n## Completed agents\n- none\n\n## Next action\nContinue.\n",
        encoding="utf-8",
    )
    (item / "reviews" / "qa.md").write_text("PASS\n", encoding="utf-8")
    event = {
        "schemaVersion": 1, "runId": "active-control-pass-001", "workItem": item.name,
        "role": "qa-engineer", "executionRole": "internal", "status": "completed", "gate": "PASS",
        "scope": ["state-checker regression"], "artifact": "reviews/qa.md",
        "evidence": [{"kind": "command", "ref": "pytest -q"}],
        "startedAt": "2026-08-01T00:00:00Z", "updatedAt": "2026-08-01T00:00:01Z",
    }
    (item / "agent-runs.jsonl").write_bytes(canonical(event) + b"\n")
    return item


def test_reader_rejects_reparse_storage_and_duplicate_authorization(tmp_path: Path) -> None:
    validator = load_validator()

    item, disposition = make_archived_fixture(tmp_path / "directory-link")
    external = tmp_path / "external-dispositions"
    external.mkdir()
    directory = item.parents[2] / "legacy-ledger-historical-dispositions"
    try:
        os.symlink(external, directory, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink fixture unavailable: {exc}")
    errors, _revise, _launches = validator.validate_archived_ledger_obligations(item)
    assert any("historical artifact disposition directory is unsafe" in error for error in errors)

    item, disposition = make_archived_fixture(tmp_path / "leaf-link")
    external_leaf = tmp_path / "external-leaf.json"
    external_leaf.write_bytes(canonical(disposition))
    directory = tmp_path / "leaf-link" / "work-items" / "legacy-ledger-historical-dispositions"
    directory.mkdir(parents=True)
    try:
        os.symlink(external_leaf, directory / f"{disposition['dispositionId']}.json")
    except OSError as exc:
        pytest.skip(f"symlink fixture unavailable: {exc}")
    errors, _revise, _launches = validator.validate_archived_ledger_obligations(item)
    assert any("historical artifact disposition path is unsafe" in error for error in errors)

    root = tmp_path / "duplicate"
    item, disposition = make_archived_fixture(root)
    first = "1" * 64
    second = "2" * 64
    write_disposition(root, {"schemaVersion": 2, "dispositionId": first, "workItem": disposition["workItem"]}, filename=f"{first}.json")
    write_disposition(root, {"schemaVersion": 2, "dispositionId": second, "workItem": disposition["workItem"]}, filename=f"{second}.json")
    authorization = validator.HistoricalArtifactAuthorization(1, "a" * 64, "b" * 64, "run-001", "missing.md", "c" * 64)
    ledger = item / "agent-runs.jsonl"
    metadata: list[dict[str, object]] = []
    events = validator.load_jsonl(ledger, [], metadata)
    with mock.patch.object(validator, "validate_historical_artifact_disposition_v2", return_value=(authorization, [])):
        _authorized, errors = validator.authorized_historical_missing_artifacts(item, ledger.read_bytes(), events, metadata)
    assert any("more than one disposition authorizes one missing artifact" in error for error in errors)


def test_reader_rejects_exact_count_and_file_size_caps(tmp_path: Path) -> None:
    validator = load_validator()
    item, _disposition = make_archived_fixture(tmp_path / "count-cap")
    directory = tmp_path / "count-cap" / "work-items" / "legacy-ledger-historical-dispositions"
    directory.mkdir(parents=True)
    for number in range(validator._HISTORICAL_DISPOSITION_MAX_FILES + 1):
        (directory / f"{number:04}.json").write_bytes(b"{}")
    errors, _revise, _launches = validator.validate_archived_ledger_obligations(item)
    assert any("directory exceeds resource cap" in error for error in errors)

    item, disposition = make_archived_fixture(tmp_path / "bytes-cap")
    target = write_disposition(tmp_path / "bytes-cap", disposition)
    target.write_bytes(b"x" * (validator._HISTORICAL_DISPOSITION_MAX_BYTES + 1))
    errors, _revise, _launches = validator.validate_archived_ledger_obligations(item)
    assert any("disposition exceeds resource cap" in error for error in errors)


def test_checker_accepts_v2_disposition_without_mutating_archive_or_active_ledger(tmp_path: Path) -> None:
    archive, disposition = make_archived_fixture(tmp_path)
    write_disposition(tmp_path, disposition)
    active = active_item(tmp_path)
    archive_before = (archive / "agent-runs.jsonl").read_bytes()
    active_before = (active / "agent-runs.jsonl").read_bytes()

    result = subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(tmp_path)], text=True, capture_output=True, check=False
    )

    assert result.returncode == 0, result.stdout
    assert "WI-CATEGORY-UNKNOWN-ROOT" not in result.stdout
    assert archive_before == (archive / "agent-runs.jsonl").read_bytes()
    assert active_before == (active / "agent-runs.jsonl").read_bytes()


def test_disposition_authorization_follows_physical_line_across_blank_rows(tmp_path: Path) -> None:
    validator = load_validator()
    item = tmp_path / "work-items" / "archive" / "2026-08" / "physical-lines"
    item.mkdir(parents=True)
    (item / "present.md").write_text("present\n", encoding="utf-8")
    present = {
        "schemaVersion": 2, "runId": "physical-present-001", "workItem": item.name,
        "role": "qa-engineer", "executionRole": "main", "status": "completed", "gate": "PASS",
        "scope": ["physical identity"], "artifact": "present.md",
        "artifactRevision": sha((item / "present.md").read_bytes()),
        "evidence": [{"kind": "manual-check", "ref": "present"}],
        "startedAt": "2026-08-01T00:00:00Z", "updatedAt": "2026-08-01T00:00:01Z",
    }
    recovered = b"recovered\n"
    missing = {
        **present, "runId": "physical-missing-001", "artifact": "missing.md",
        "artifactRevision": sha(recovered),
        "evidence": [{"kind": "manual-check", "ref": "missing"}],
    }
    present_raw, missing_raw = canonical(present), canonical(missing)
    ledger_bytes = present_raw + b"\n\n" + missing_raw + b"\n"
    (item / "agent-runs.jsonl").write_bytes(ledger_bytes)
    work_item = item.relative_to(tmp_path).as_posix()
    disposition = {
        "schemaVersion": 2,
        "archiveIdentity": sha(b"orchestrarium-archive-v1\0" + work_item.encode() + b"\0" + sha(ledger_bytes).encode()),
        "workItem": work_item, "ledgerSha256": sha(ledger_bytes), "rawLineOrdinal": 3,
        "rawLineSha256": sha(missing_raw), "runId": missing["runId"],
        "eventSha256": sha(canonical(missing)), "missingPath": "missing.md",
        "artifactRevisionSha256": missing["artifactRevision"], "state": "content-recovered",
        "contentBytesBase64": base64.b64encode(recovered).decode("ascii"),
        "contentBytesSha256": sha(recovered),
    }
    disposition["dispositionId"] = sha(
        b"orchestrarium-historical-artifact-disposition-v2\0" + b"\0".join(
            str(disposition[key]).encode() for key in (
                "archiveIdentity", "rawLineOrdinal", "rawLineSha256", "eventSha256",
                "missingPath", "artifactRevisionSha256",
            )
        )
    )
    write_disposition(tmp_path, disposition)

    errors, _revise, _launches = validator.validate_archived_ledger_obligations(item)

    assert errors == []


def test_archived_authorization_refuses_missing_or_misaligned_row_envelopes(tmp_path: Path) -> None:
    validator = load_validator()
    item, disposition = make_archived_fixture(tmp_path)
    ledger = item / "agent-runs.jsonl"
    metadata: list[dict[str, object]] = []
    events = validator.load_jsonl(ledger, [], metadata)
    authorization = validator.HistoricalArtifactAuthorization(
        disposition["rawLineOrdinal"], disposition["rawLineSha256"],
        disposition["eventSha256"], disposition["runId"], disposition["missingPath"],
        disposition["artifactRevisionSha256"],
    )
    errors: list[str] = []

    validity, closure_validity = validator.derive_archived_event_validity(
        events, item, errors, {disposition["rawLineOrdinal"]: authorization}, rows=()
    )

    assert any("archived validity rows differ from effective events" in error for error in errors)
    assert validity == [False]
    assert closure_validity == [False]
