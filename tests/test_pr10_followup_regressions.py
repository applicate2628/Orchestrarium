from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROVIDER = ROOT / "scripts" / "provider_prompt.py"
LEDGER = ROOT / "scripts" / "agent-run-ledger.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_kimi_mcp_header_aliases_protect_carried_values() -> None:
    owner = load_module(PROVIDER, "pr10_header_alias_owner")
    selection = owner.KimiCapabilitySelectionV1(
        mcp_servers=(
            owner.KimiMcpServerV1(
                name="fixture",
                command="fixture",
                args=(
                    "--headers",
                    "Authorization: Bearer plural-header-secret",
                    "--request-header=X-Api-Key: request-header-secret",
                ),
            ),
        )
    )

    needles = set(owner._kimi_mcp_credential_needles(selection))

    assert b"plural-header-secret" in needles
    assert b"request-header-secret" in needles


def test_kimi_mcp_bare_environment_assignment_protects_value() -> None:
    owner = load_module(PROVIDER, "pr10_bare_env_owner")
    selection = owner.KimiCapabilitySelectionV1(
        mcp_servers=(
            owner.KimiMcpServerV1(
                name="fixture",
                command="fixture",
                args=("API_TOKEN=direct-secret", "PATH=/usr/bin"),
            ),
        )
    )

    needles = set(owner._kimi_mcp_credential_needles(selection))

    assert b"direct-secret" in needles
    assert b"/usr/bin" not in needles


def test_kimi_capability_snapshot_excludes_writers_before_first_fstat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = load_module(PROVIDER, "pr10_capability_exclusion_owner")
    path = tmp_path / "capabilities.json"
    path.write_text(
        json.dumps(
            {
                "v": 1,
                "tools": [],
                "mcpServers": [],
                "subagents": [],
                "permission": "reject",
                "cwd": None,
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    events: list[str] = []

    class Exclusion:
        def __enter__(self):
            events.append("enter")
            return self

        def __exit__(self, *_args):
            events.append("exit")

    monkeypatch.setattr(
        owner,
        "_kimi_capability_write_exclusion",
        lambda _descriptor: Exclusion(),
        raising=False,
    )
    original_fstat = owner.os.fstat

    def guarded_fstat(descriptor: int):
        assert events == ["enter"], "descriptor metadata was sampled before writer exclusion"
        return original_fstat(descriptor)

    monkeypatch.setattr(owner.os, "fstat", guarded_fstat)

    owner.read_kimi_capability_selection(path)

    assert events == ["enter", "exit"]


def test_noncanonical_failed_apply_retains_owned_candidate_without_unlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger, item, expected_sha256, original, marker_bytes = _noncanonical_replay_fixture(
        tmp_path, "pr10_failed_apply_retention_owner"
    )
    canonical = item / "agent-runs.jsonl"
    canonical.write_bytes(original)
    candidate = item / "agent-runs.jsonl.tmp"
    monkeypatch.setattr(
        ledger, "_validate_noncanonical_marker_candidate", lambda *_args: None
    )
    original_unlink = ledger.Path.unlink

    def forbid_candidate_unlink(path: Path, *args, **kwargs):
        if Path(path) == candidate:
            raise AssertionError("fixed candidate must not be pathname-unlinked")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(ledger.Path, "unlink", forbid_candidate_unlink)

    completed, _history = ledger._command_apply_noncanonical_history(
        item,
        expected_sha256,
        "linked-ledger-replay",
        "2026-09-10T12:00:00Z",
        ledger.load_validator(),
        "pre-ledger-replace",
    )

    assert completed is False
    assert candidate.read_bytes() == marker_bytes


def test_noncanonical_history_staging_is_validated_without_unlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = load_module(LEDGER, "pr10_history_cleanup_preservation_owner")
    history = tmp_path / "agent-runs.history.fixture.jsonl"
    staging = tmp_path / ".agent-runs.history.fixture.jsonl.tmp"
    owned = b"owned history bytes\n"
    history.write_bytes(owned)
    try:
        os.link(history, staging)
    except OSError as exc:
        pytest.skip(f"hardlink unavailable: {exc}")
    original_unlink = ledger.Path.unlink

    def forbid_staging_unlink(path: Path, *args, **kwargs):
        if Path(path) == staging:
            raise AssertionError("history staging must not be pathname-unlinked")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(ledger.Path, "unlink", forbid_staging_unlink)

    ledger._validate_owned_history_staging(history, staging)

    assert history.read_bytes() == owned
    assert staging.read_bytes() == owned
    assert history.stat().st_ino == staging.stat().st_ino


def _noncanonical_replay_fixture(tmp_path: Path, module_name: str):
    ledger = load_module(LEDGER, module_name)
    item = tmp_path / "work-items" / "active" / "noncanonical-replay"
    item.mkdir(parents=True)
    original = (
        b'{"date":"2026-09-10","lane":"example","execution_role":"analyst",'
        b'"result":"historical note"}\n'
    )
    expected_sha256 = hashlib.sha256(original).hexdigest()
    history = item / f"agent-runs.history.{expected_sha256}.jsonl"
    history.write_bytes(original)
    marker = ledger._noncanonical_history_marker(
        item,
        expected_sha256,
        original,
        "linked-ledger-replay",
        "2026-09-10T12:00:00Z",
    )
    marker_bytes = (ledger.serialize_event(marker) + "\n").encode("utf-8")
    return ledger, item, expected_sha256, original, marker_bytes


@pytest.mark.parametrize("operation", ("apply", "rollback"))
def test_noncanonical_publish_never_commits_a_swapped_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    ledger, item, expected_sha256, original, marker_bytes = _noncanonical_replay_fixture(
        tmp_path, f"pr10_publish_swap_{operation}_owner"
    )
    canonical = item / "agent-runs.jsonl"
    initial = original if operation == "apply" else marker_bytes
    canonical.write_bytes(initial)
    candidate = item / "agent-runs.jsonl.tmp"
    foreign = b"foreign candidate published at replace boundary\n"
    original_write = ledger._write_exact_staging_file
    raced = False

    def write_then_swap(path: Path, expected: bytes):
        nonlocal raced
        identity = original_write(path, expected)
        if path == candidate and not raced:
            raced = True
            replacement = candidate.with_suffix(".foreign")
            replacement.write_bytes(foreign)
            os.replace(replacement, candidate)
        return identity

    monkeypatch.setattr(ledger, "_write_exact_staging_file", write_then_swap)
    monkeypatch.setattr(
        ledger, "_validate_noncanonical_marker_candidate", lambda *_args: None
    )
    command = (
        ledger._command_apply_noncanonical_history
        if operation == "apply"
        else ledger._command_rollback_noncanonical_history
    )

    with pytest.raises(ledger.LedgerNoncanonicalRecoveryError):
        command(
            item,
            expected_sha256,
            "linked-ledger-replay",
            "2026-09-10T12:00:00Z",
            ledger.load_validator(),
            None,
        )

    assert raced is True
    assert canonical.read_bytes() == initial
