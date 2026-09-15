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


def test_noncanonical_cleanup_never_unlinks_a_swapped_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = load_module(LEDGER, "pr10_cleanup_swap_owner")
    candidate = tmp_path / "agent-runs.jsonl.tmp"
    candidate.write_bytes(b"owned staging bytes\n")
    identity = ledger._noncanonical_file_identity(candidate.stat())
    foreign = b"foreign replacement\n"
    original_unlink = ledger.Path.unlink
    raced = False

    def racing_unlink(path: Path, *args, **kwargs):
        nonlocal raced
        if Path(path) == candidate and not raced:
            raced = True
            replacement = candidate.with_suffix(".foreign")
            replacement.write_bytes(foreign)
            os.replace(replacement, candidate)
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(ledger.Path, "unlink", racing_unlink)

    ledger._cleanup_exact_staging_file(candidate, identity)

    assert candidate.read_bytes() == foreign


def test_noncanonical_history_cleanup_never_unlinks_a_swapped_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = load_module(LEDGER, "pr10_history_cleanup_swap_owner")
    history = tmp_path / "agent-runs.history.fixture.jsonl"
    staging = tmp_path / ".agent-runs.history.fixture.jsonl.tmp"
    history.write_bytes(b"owned history bytes\n")
    try:
        os.link(history, staging)
    except OSError as exc:
        pytest.skip(f"hardlink unavailable: {exc}")
    foreign = b"foreign replacement\n"
    original_unlink = ledger.Path.unlink
    raced = False

    def racing_unlink(path: Path, *args, **kwargs):
        nonlocal raced
        if Path(path) == staging and not raced:
            raced = True
            replacement = staging.with_suffix(".foreign")
            replacement.write_bytes(foreign)
            os.replace(replacement, staging)
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(ledger.Path, "unlink", racing_unlink)

    ledger._cleanup_owned_history_staging(history, staging)

    assert staging.read_bytes() == foreign
    assert history.read_bytes() == b"owned history bytes\n"


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
    original_replace = ledger.os.replace
    raced = False

    def racing_replace(source, destination):
        nonlocal raced
        if Path(source) == candidate and Path(destination) == canonical and not raced:
            raced = True
            replacement = candidate.with_suffix(".foreign")
            replacement.write_bytes(foreign)
            original_replace(replacement, candidate)
        return original_replace(source, destination)

    monkeypatch.setattr(ledger.os, "replace", racing_replace)
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
