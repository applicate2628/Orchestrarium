from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRATCH_FIXTURE = ROOT / "tests" / "test_scratch_evidence_lifecycle.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def archived_fixture(tmp_path: Path):
    helpers = load_module(SCRATCH_FIXTURE, f"release_fixture_{id(tmp_path)}")
    root = tmp_path / "repo"
    mutator, item, scratch, _ = helpers.seed_item(root, disposition="retain")
    instant = "2026-08-09T01:00:00Z"
    closure = helpers.closure(instant)
    archived = mutator.close_item(root, item.name, closure, instant)
    event = json.loads((archived / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    return mutator, root, archived, scratch, event, closure, instant


def terminal_hash(archived: Path) -> str:
    import hashlib
    return hashlib.sha256((archived / "agent-runs.jsonl").read_bytes().splitlines()[-1]).hexdigest()


def test_release_one_plain_retained_directory_keeps_archive_and_replays(tmp_path: Path) -> None:
    mutator, root, archived, scratch, event, closure, instant = archived_fixture(tmp_path)
    original_archive = {
        path.relative_to(archived): path.read_bytes()
        for path in archived.rglob("*") if path.is_file()
    }
    artifact = archived / "accepted-evidence.md"
    artifact.write_bytes(b"Accepted: payload reproduced from canonical evidence.\n")

    receipt = mutator.release_retained_scratch(
        root,
        archived.name,
        terminal_run_id=event["runId"],
        expected_event_sha256=terminal_hash(archived),
        entry_id=event["scratchEvidence"][0]["entryId"],
        artifact="accepted-evidence.md",
        rationale="The named payload was independently reproduced and accepted.",
        apply=True,
    )

    assert receipt.is_file()
    assert not scratch.exists()
    assert mutator.close_item(root, archived.name, closure, instant) == archived
    assert {path: (archived / path).read_bytes() for path in original_archive} == original_archive


def release(mutator, root: Path, archived: Path, event: dict, **kwargs):
    return mutator.release_retained_scratch(
        root,
        archived.name,
        terminal_run_id=event["runId"],
        expected_event_sha256=terminal_hash(archived),
        entry_id=event["scratchEvidence"][0]["entryId"],
        artifact="accepted-evidence.md",
        rationale="The exact source payload and target custody were independently accepted.",
        apply=True,
        **kwargs,
    )


def add_artifact(archived: Path) -> None:
    (archived / "accepted-evidence.md").write_bytes(b"Accepted canonical evidence.\n")


def test_release_plain_file_root_and_replay(tmp_path: Path) -> None:
    helpers = load_module(ROOT / "tests" / "test_retained_scratch_file_lifecycle.py", f"file_fixture_{id(tmp_path)}")
    root = tmp_path / "repo"
    scratch_helpers, mutator, item, scratch, before, _ledger = helpers.retained_file_fixture(root)
    instant = "2026-08-09T01:00:00Z"
    closure = scratch_helpers.closure(instant)
    archived = mutator.close_item(root, item.name, closure, instant)
    event = json.loads((archived / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    add_artifact(archived)

    receipt = release(mutator, root, archived, event)

    assert receipt.is_file() and not scratch.exists()
    assert mutator.close_item(root, item.name, closure, instant) == archived
    assert before == b'{"schemaVersion":1,"status":"settled"}\n'


@pytest.mark.parametrize("absolute", [False, True])
def test_release_link_metadata_without_following_internal_target(tmp_path: Path, absolute: bool) -> None:
    mutator, root, archived, scratch, event, closure, instant = archived_fixture(tmp_path)
    target = scratch / "payload.txt"
    link = scratch / "alias.txt"
    try:
        link.symlink_to(target if absolute else Path("payload.txt"))
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    add_artifact(archived)

    receipt = release(mutator, root, archived, event)

    assert not scratch.exists() and not link.exists()
    rows = json.loads(receipt.read_text(encoding="utf-8"))["inventory"]
    assert [row["kind"] for row in rows].count("symlink") == 1
    assert mutator.close_item(root, archived.name, closure, instant) == archived


@pytest.mark.parametrize("target_kind", ["external", "chained", "malformed"])
def test_unsafe_link_target_refused_before_receipt_or_deletion(tmp_path: Path, target_kind: str) -> None:
    mutator, root, archived, scratch, event, _closure, _instant = archived_fixture(tmp_path)
    add_artifact(archived)
    target = scratch / "payload.txt"
    if target_kind == "external":
        target = tmp_path / "outside.txt"
        target.write_bytes(b"external")
    elif target_kind == "malformed":
        if os.name != "nt":
            pytest.skip("Windows reserved path contract")
        target = root / "missing-parent" / "invalid:target"
    elif target_kind == "chained":
        try:
            (scratch / "other-link").symlink_to(target)
        except (OSError, NotImplementedError) as exc:
            pytest.skip(f"symlink unavailable: {exc}")
        target = scratch / "other-link"
    try:
        (scratch / "alias.txt").symlink_to(target)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable: {exc}")

    with pytest.raises(mutator.LifecycleError):
        release(mutator, root, archived, event)

    assert scratch.is_dir() and (scratch / "payload.txt").is_file()
    assert not (archived / "retained-scratch-releases").exists()


@pytest.mark.parametrize("phase", ["after-receipt", "after-rename", "after-first-file-unlink", "after-first-link-unlink", "after-final-removal"])
def test_release_crash_replays_exact_surviving_subset(tmp_path: Path, phase: str) -> None:
    mutator, root, archived, scratch, event, closure, instant = archived_fixture(tmp_path)
    (scratch / "second.txt").write_bytes(b"second")
    try:
        (scratch / "alias.txt").symlink_to(Path("payload.txt"))
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    add_artifact(archived)

    with pytest.raises(mutator.LifecycleError, match="injected"):
        release(mutator, root, archived, event, inject_failure_at=phase)
    assert (archived / "retained-scratch-releases").is_dir()

    receipt = release(mutator, root, archived, event)

    assert receipt.is_file() and not scratch.exists()
    assert mutator.close_item(root, archived.name, closure, instant) == archived


def test_changed_survivor_and_receipt_drift_block_replay(tmp_path: Path) -> None:
    mutator, root, archived, scratch, event, _closure, _instant = archived_fixture(tmp_path)
    add_artifact(archived)
    with pytest.raises(mutator.LifecycleError):
        release(mutator, root, archived, event, inject_failure_at="after-receipt")
    (scratch / "payload.txt").write_bytes(b"drift")

    with pytest.raises(mutator.LifecycleError):
        release(mutator, root, archived, event)
    assert scratch.is_dir()


def test_no_receipt_missing_retain_still_fails(tmp_path: Path) -> None:
    mutator, root, archived, scratch, _event, closure, instant = archived_fixture(tmp_path)
    (scratch / "payload.txt").unlink()
    scratch.rmdir()

    with pytest.raises(mutator.LifecycleError) as caught:
        mutator.close_item(root, archived.name, closure, instant)

    assert caught.value.failure_id == "WI-SCRATCH-RETAINED-EVIDENCE-MISSING"


def test_receipt_and_artifact_drift_refuse_missing_root_replay(tmp_path: Path) -> None:
    mutator, root, archived, scratch, event, closure, instant = archived_fixture(tmp_path)
    add_artifact(archived)
    receipt = release(mutator, root, archived, event)
    assert not scratch.exists()
    original = receipt.read_bytes()
    (archived / "accepted-evidence.md").write_bytes(b"changed\n")
    with pytest.raises(mutator.LifecycleError):
        mutator.close_item(root, archived.name, closure, instant)
    add_artifact(archived)
    data = json.loads(original)
    data["sourcePath"] = data["sourcePath"] + "-other"
    receipt.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(mutator.LifecycleError):
        mutator.close_item(root, archived.name, closure, instant)


def test_partial_tombstone_addition_or_changed_survivor_blocks_retry(tmp_path: Path) -> None:
    mutator, root, archived, scratch, event, _closure, _instant = archived_fixture(tmp_path)
    (scratch / "second.txt").write_bytes(b"second")
    add_artifact(archived)
    with pytest.raises(mutator.LifecycleError, match="injected"):
        release(mutator, root, archived, event, inject_failure_at="after-first-file-unlink")
    tombstone = mutator._scratch_tombstone(
        scratch, archived.name, event["runId"], event["scratchEvidence"][0]["entryId"]
    )
    survivors = list(tombstone.glob("*.txt"))
    assert len(survivors) == 1
    survivor = survivors[0]
    before = survivor.read_bytes()
    survivor.write_bytes(b"changed")
    with pytest.raises(mutator.LifecycleError):
        release(mutator, root, archived, event)
    survivor.write_bytes(before)
    (tombstone / "addition.txt").write_bytes(b"unrecorded")
    with pytest.raises(mutator.LifecycleError):
        release(mutator, root, archived, event)
    assert (tombstone / "addition.txt").read_bytes() == b"unrecorded"


def test_repository_target_in_same_archive_is_bound_and_never_deleted(tmp_path: Path) -> None:
    mutator, root, archived, scratch, event, closure, instant = archived_fixture(tmp_path)
    target = archived / "durable-target.txt"
    target.write_bytes(b"durable")
    link = scratch / "durable-link.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    add_artifact(archived)
    target_before = target.read_bytes()

    receipt = release(mutator, root, archived, event)

    assert not scratch.exists() and target.read_bytes() == target_before
    link_row = next(row for row in json.loads(receipt.read_text(encoding="utf-8"))["inventory"] if row["kind"] == "symlink")
    assert link_row["targetClass"] == "repository"
    assert link_row["targetSha256"] == "54dab9eb6d3204a0b42800148196ed4785d258f980432579b62ef0d9db0207b8"
    target.write_bytes(b"drift")
    with pytest.raises(mutator.LifecycleError):
        mutator.close_item(root, archived.name, closure, instant)


def test_repository_target_becoming_link_cannot_be_followed_on_retry(tmp_path: Path) -> None:
    mutator, root, archived, scratch, event, _closure, _instant = archived_fixture(tmp_path)
    target = archived / "durable-target.txt"
    target.write_bytes(b"durable")
    try:
        (scratch / "durable-link.txt").symlink_to(target)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    add_artifact(archived)
    with pytest.raises(mutator.LifecycleError, match="injected"):
        release(mutator, root, archived, event, inject_failure_at="after-receipt")
    target.unlink()
    foreign = tmp_path / "foreign.txt"
    foreign.write_bytes(b"foreign protected")
    target.symlink_to(foreign)

    with pytest.raises(mutator.LifecycleError):
        release(mutator, root, archived, event)

    assert scratch.is_dir() and foreign.read_bytes() == b"foreign protected"


def test_wrong_terminal_event_hash_refused_without_receipt(tmp_path: Path) -> None:
    mutator, root, archived, scratch, event, _closure, _instant = archived_fixture(tmp_path)
    add_artifact(archived)
    with pytest.raises(mutator.LifecycleError):
        mutator.release_retained_scratch(
            root, archived.name, terminal_run_id=event["runId"],
            expected_event_sha256="0" * 64,
            entry_id=event["scratchEvidence"][0]["entryId"],
            artifact="accepted-evidence.md", rationale="Accepted synthetic evidence.", apply=True,
        )
    assert scratch.is_dir() and not (archived / "retained-scratch-releases").exists()


def test_undurable_repository_link_target_refused(tmp_path: Path) -> None:
    mutator, root, archived, scratch, event, _closure, _instant = archived_fixture(tmp_path)
    target = root / "not-archived.txt"
    target.write_bytes(b"volatile")
    try:
        (scratch / "volatile-link.txt").symlink_to(target)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    add_artifact(archived)
    with pytest.raises(mutator.LifecycleError):
        release(mutator, root, archived, event)
    assert scratch.is_dir() and target.read_bytes() == b"volatile"


def test_internal_directory_link_uses_bounded_target_content_digest(tmp_path: Path) -> None:
    mutator, root, archived, scratch, event, closure, instant = archived_fixture(tmp_path)
    target = scratch / "nested"
    target.mkdir()
    (target / "needed.txt").write_bytes(b"needed")
    try:
        (scratch / "nested-alias").symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"directory symlink unavailable: {exc}")
    add_artifact(archived)

    receipt = release(mutator, root, archived, event)

    link_row = next(row for row in json.loads(receipt.read_text(encoding="utf-8"))["inventory"] if row["kind"] == "symlink")
    assert link_row["targetKind"] == "directory"
    assert not scratch.exists()
    assert mutator.close_item(root, archived.name, closure, instant) == archived


def test_outside_archive_file_target_can_be_promoted_by_exact_canonical_artifact(tmp_path: Path) -> None:
    mutator, root, archived, scratch, event, closure, instant = archived_fixture(tmp_path)
    target = root / "otherwise-volatile.txt"
    target.write_bytes(b"payload promoted exactly")
    try:
        (scratch / "promoted-link.txt").symlink_to(target)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    (archived / "accepted-evidence.md").write_bytes(target.read_bytes())

    receipt = release(mutator, root, archived, event)

    row = next(row for row in json.loads(receipt.read_text(encoding="utf-8"))["inventory"] if row["kind"] == "symlink")
    assert row["targetCustody"] == "artifact"
    target.unlink()
    assert mutator.close_item(root, archived.name, closure, instant) == archived


def test_tampered_receipt_cannot_smuggle_absolute_target_path(tmp_path: Path) -> None:
    mutator, root, archived, scratch, event, closure, instant = archived_fixture(tmp_path)
    try:
        (scratch / "alias.txt").symlink_to(Path("payload.txt"))
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    add_artifact(archived)
    receipt = release(mutator, root, archived, event)
    data = json.loads(receipt.read_text(encoding="utf-8"))
    row = next(row for row in data["inventory"] if row["kind"] == "symlink")
    row["targetPath"] = "C:/foreign.txt"
    import hashlib
    data["inventorySha256"] = hashlib.sha256(json.dumps(data["inventory"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    receipt.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(mutator.LifecycleError):
        mutator.close_item(root, archived.name, closure, instant)


@pytest.mark.parametrize("target_kind", ["file", "directory", "absent-contradiction"])
def test_source_absent_replay_rejects_in_root_target_not_in_full_inventory(
    tmp_path: Path, target_kind: str,
) -> None:
    mutator, root, archived, scratch, event, closure, instant = archived_fixture(tmp_path)
    target = scratch / "payload.txt"
    if target_kind == "directory":
        target = scratch / "nested"
        target.mkdir()
        (target / "needed.txt").write_bytes(b"needed")
    try:
        (scratch / "alias").symlink_to(target, target_is_directory=target_kind == "directory")
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    add_artifact(archived)
    receipt = release(mutator, root, archived, event)
    assert not scratch.exists()
    data = json.loads(receipt.read_text(encoding="utf-8"))
    row = next(row for row in data["inventory"] if row["kind"] == "symlink")
    if target_kind == "absent-contradiction":
        row["targetKind"] = "absent"
        row["targetCustody"] = "no-content"
        del row["targetSha256"]
    else:
        row["targetPath"] = (scratch / "nonexistent").relative_to(root).as_posix()
    data["inventorySha256"] = hashlib.sha256(
        json.dumps(data["inventory"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    receipt.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(mutator.LifecycleError):
        mutator.close_item(root, archived.name, closure, instant)


@pytest.mark.parametrize("failure_at", ["serialize", "publish"])
def test_receipt_prepublication_failure_leaves_no_partial_final_and_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_at: str,
) -> None:
    mutator, root, archived, scratch, event, closure, instant = archived_fixture(tmp_path)
    add_artifact(archived)
    archive_before = {
        path.relative_to(archived): path.read_bytes()
        for path in archived.rglob("*") if path.is_file()
    }
    final = mutator._release_receipt_path(
        archived, event["runId"], event["scratchEvidence"][0]["entryId"]
    )
    with monkeypatch.context() as patch:
        if failure_at == "serialize":
            real_dumps = mutator.json.dumps

            def fail_receipt_serialization(value, *args, **kwargs):
                if isinstance(value, dict) and "inventory" in value and "artifact" in value:
                    raise OSError("injected receipt serialization failure")
                return real_dumps(value, *args, **kwargs)

            patch.setattr(mutator.json, "dumps", fail_receipt_serialization)
        else:
            real_link = mutator.os.link

            def fail_receipt_publication(source, target, *args, **kwargs):
                if Path(target) == final:
                    raise OSError("injected receipt publication failure")
                return real_link(source, target, *args, **kwargs)

            patch.setattr(mutator.os, "link", fail_receipt_publication)
        with pytest.raises(mutator.LifecycleError):
            release(mutator, root, archived, event)

    assert scratch.is_dir() and (scratch / "payload.txt").is_file()
    assert not final.exists()
    assert not list(final.parent.glob(f".{final.name}.*.tmp"))
    assert {path: (archived / path).read_bytes() for path in archive_before} == archive_before
    assert release(mutator, root, archived, event) == final
    assert mutator.close_item(root, archived.name, closure, instant) == archived


@pytest.mark.parametrize("stage_kind", ["complete", "partial"])
def test_prelink_crash_stage_is_reconciled_or_blocks_without_removal(
    tmp_path: Path, stage_kind: str,
) -> None:
    mutator, root, archived, scratch, event, closure, instant = archived_fixture(tmp_path)
    add_artifact(archived)
    with pytest.raises(mutator.LifecycleError, match="injected"):
        release(mutator, root, archived, event, inject_failure_at="after-receipt")
    final = mutator._release_receipt_path(
        archived, event["runId"], event["scratchEvidence"][0]["entryId"]
    )
    stage = final.parent / f".{final.name}.crash.tmp"
    stage.write_bytes(final.read_bytes() if stage_kind == "complete" else b"{")
    final.unlink()
    assert scratch.is_dir() and not final.exists()

    if stage_kind == "partial":
        with pytest.raises(mutator.LifecycleError):
            release(mutator, root, archived, event)
        assert stage.read_bytes() == b"{" and scratch.is_dir() and not final.exists()
    else:
        assert release(mutator, root, archived, event) == final
        assert not stage.exists() and not scratch.exists()
        assert mutator.close_item(root, archived.name, closure, instant) == archived


@pytest.mark.parametrize("entry_path", ["release-retry", "archived-close-replay"])
def test_postlink_crash_pair_reconciles_before_strict_receipt_read(
    tmp_path: Path, entry_path: str,
) -> None:
    mutator, root, archived, scratch, event, closure, instant = archived_fixture(tmp_path)
    add_artifact(archived)
    with pytest.raises(mutator.LifecycleError, match="injected"):
        release(mutator, root, archived, event, inject_failure_at="after-receipt")
    final = mutator._release_receipt_path(
        archived, event["runId"], event["scratchEvidence"][0]["entryId"]
    )
    stage = final.parent / f".{final.name}.postlink.tmp"
    mutator.os.link(final, stage)
    assert final.stat().st_nlink == 2 and stage.stat().st_ino == final.stat().st_ino
    assert scratch.is_dir()

    if entry_path == "release-retry":
        assert release(mutator, root, archived, event) == final
    else:
        assert mutator.close_item(root, archived.name, closure, instant) == archived

    assert final.is_file() and final.stat().st_nlink == 1
    assert not stage.exists() and not scratch.exists()


def test_postlink_stage_with_different_inode_refuses_without_unlink(
    tmp_path: Path,
) -> None:
    mutator, root, archived, scratch, event, _closure, _instant = archived_fixture(tmp_path)
    add_artifact(archived)
    with pytest.raises(mutator.LifecycleError, match="injected"):
        release(mutator, root, archived, event, inject_failure_at="after-receipt")
    final = mutator._release_receipt_path(
        archived, event["runId"], event["scratchEvidence"][0]["entryId"]
    )
    stage = final.parent / f".{final.name}.collision.tmp"
    stage.write_bytes(final.read_bytes())
    assert stage.stat().st_ino != final.stat().st_ino

    with pytest.raises(mutator.LifecycleError):
        release(mutator, root, archived, event)

    assert final.is_file() and stage.is_file() and scratch.is_dir()


@pytest.mark.parametrize("source_kind", ["live-link", "readonly", "absent-directory"])
def test_cli_requires_apply_and_releases_only_named_root(tmp_path: Path, source_kind: str) -> None:
    if source_kind == "readonly" and os.name != "nt":
        pytest.skip("Windows ReadOnly unlink contract")
    mutator, root, archived, scratch, event, closure, instant = archived_fixture(tmp_path)
    target = root / "missing-parent" / "missing-directory" if source_kind == "absent-directory" else Path("payload.txt")
    try:
        (scratch / "alias.txt").symlink_to(target, target_is_directory=source_kind == "absent-directory")
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    add_artifact(archived)
    neighbor = root / "untouched.txt"
    neighbor.write_bytes(b"untouched")
    before_neighbor = neighbor.stat(), neighbor.read_bytes()
    if source_kind == "readonly":
        nested = scratch / "nested"
        nested.mkdir()
        (nested / "second.txt").write_bytes(b"second readonly")
        for leaf in (scratch / "payload.txt", nested / "second.txt"):
            leaf.chmod(stat.S_IREAD)
    command = [
        sys.executable, str(ROOT / "scripts" / "mutate-work-item.py"),
        "release-retained-scratch", "--root", ".", "--slug", archived.name,
        "--terminal-run-id", event["runId"], "--expected-event-sha256", terminal_hash(archived),
        "--entry-id", event["scratchEvidence"][0]["entryId"],
        "--artifact", "accepted-evidence.md", "--rationale", "Accepted synthetic evidence.",
    ]
    refused = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=20)
    assert refused.returncode != 0 and scratch.is_dir()
    applied = subprocess.run([*command, "--apply"], cwd=root, capture_output=True, text=True, timeout=20)
    assert applied.returncode == 0, applied.stderr
    assert not scratch.exists()
    replayed = subprocess.run([*command, "--apply"], cwd=root, capture_output=True, text=True, timeout=20)
    assert replayed.returncode == 0, replayed.stderr
    assert mutator.close_item(root, archived.name, closure, instant) == archived
    assert (neighbor.stat(), neighbor.read_bytes()) == before_neighbor
    if source_kind == "absent-directory":
        assert not (root / "missing-parent").exists()
        receipt = next((archived / "retained-scratch-releases").glob("*.json"))
        row = next(row for row in json.loads(receipt.read_text(encoding="utf-8"))["inventory"] if row["kind"] == "symlink")
        assert row["targetKind"] == "absent" and row["targetCustody"] == "no-content"
        assert "targetSha256" not in row


@pytest.mark.skipif(os.name != "nt", reason="Windows ReadOnly unlink contract")
def test_ordinary_disposition_uses_same_readonly_unlink(tmp_path: Path) -> None:
    helpers = load_module(SCRATCH_FIXTURE, f"readonly_disposition_{id(tmp_path)}")
    root = tmp_path / "repo"
    mutator, item, scratch, _ = helpers.seed_item(root)
    (scratch / "payload.txt").chmod(stat.S_IREAD)
    instant = "2026-08-09T01:00:00Z"
    archived = mutator.close_item(root, item.name, helpers.closure(instant), instant)
    assert archived.is_dir() and not scratch.exists()
    assert mutator.close_item(root, item.name, helpers.closure(instant), instant) == archived


@pytest.mark.skipif(os.name != "nt", reason="Windows ReadOnly unlink contract")
def test_readonly_retry_failure_restores_attribute_and_preserves_bytes(tmp_path: Path, monkeypatch) -> None:
    mutator, root, archived, scratch, event, _closure, _instant = archived_fixture(tmp_path)
    add_artifact(archived)
    leaf = scratch / "payload.txt"
    leaf.chmod(stat.S_IREAD)
    before = leaf.stat(), leaf.read_bytes()
    original_unlink = Path.unlink
    attempts = []

    def denied(path, *args, **kwargs):
        if path.name == "payload.txt":
            attempts.append(path.stat().st_file_attributes)
            raise PermissionError("denied retry")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", denied)
    with pytest.raises(mutator.LifecycleError, match="denied retry"):
        release(mutator, root, archived, event)
    tombstone = next(scratch.parent.glob(".*.orchestrarium-delete-*"))
    retained = tombstone / "payload.txt"
    assert len(attempts) == 2
    assert attempts[0] & stat.FILE_ATTRIBUTE_READONLY
    assert not attempts[1] & stat.FILE_ATTRIBUTE_READONLY
    after = retained.stat()
    assert (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_file_attributes) == (
        before[0].st_dev, before[0].st_ino, before[0].st_size, before[0].st_mtime_ns, before[0].st_file_attributes,
    )
    assert retained.read_bytes() == before[1]


@pytest.mark.skipif(os.name != "nt", reason="Windows ReadOnly unlink contract")
@pytest.mark.parametrize("leaf_kind", ["writable", "hardlinked-readonly"])
def test_permission_denial_does_not_clear_unowned_or_writable_attributes(tmp_path: Path, monkeypatch, leaf_kind: str) -> None:
    mutator, root, archived, scratch, event, _closure, _instant = archived_fixture(tmp_path)
    add_artifact(archived)
    leaf = scratch / "payload.txt"
    alias = root / "foreign-alias.txt"
    if leaf_kind == "hardlinked-readonly":
        os.link(leaf, alias)
        leaf.chmod(stat.S_IREAD)
    before = leaf.stat().st_file_attributes, leaf.read_bytes()
    original_unlink = Path.unlink

    def denied(path, *args, **kwargs):
        if path.name == "payload.txt":
            raise PermissionError("unchanged access denial")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", denied)
    with pytest.raises(mutator.LifecycleError, match="unchanged access denial"):
        release(mutator, root, archived, event)
    retained = next(scratch.parent.glob(".*.orchestrarium-delete-*")) / "payload.txt"
    assert (retained.stat().st_file_attributes, retained.read_bytes()) == before
    if alias.exists():
        assert (alias.stat().st_file_attributes, alias.read_bytes()) == before


@pytest.mark.parametrize("obstacle", ["live", "reparse-prefix", "denied-prefix"])
def test_absent_target_replay_refuses_live_reparse_or_unreadable_prefix(tmp_path: Path, monkeypatch, obstacle: str) -> None:
    mutator, root, archived, scratch, event, _closure, _instant = archived_fixture(tmp_path)
    add_artifact(archived)
    prefix = root / "missing-parent"
    target = prefix / "target"
    try:
        (scratch / "dangling").symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    with pytest.raises(mutator.LifecycleError, match="injected"):
        release(mutator, root, archived, event, inject_failure_at="after-receipt")
    if obstacle == "live":
        target.mkdir(parents=True)
        (target / "untouched.txt").write_bytes(b"target bytes")
    elif obstacle == "reparse-prefix":
        other = root / "other"
        other.mkdir()
        prefix.symlink_to(other, target_is_directory=True)
    else:
        original_lstat = Path.lstat

        def denied(path, *args, **kwargs):
            if path == prefix:
                raise PermissionError("unreadable target prefix")
            return original_lstat(path, *args, **kwargs)

        monkeypatch.setattr(Path, "lstat", denied)
    with pytest.raises(mutator.LifecycleError):
        release(mutator, root, archived, event)
    assert scratch.is_dir() and (scratch / "dangling").is_symlink()
    if obstacle == "live":
        assert (target / "untouched.txt").read_bytes() == b"target bytes"
    elif obstacle == "reparse-prefix":
        assert prefix.is_symlink() and list(other.iterdir()) == []


@pytest.mark.parametrize("malformation", ["content-hash", "live-custody", "noncanonical-path"])
def test_absent_receipt_variant_rejects_malformed_rows(tmp_path: Path, malformation: str) -> None:
    mutator, root, archived, scratch, event, _closure, _instant = archived_fixture(tmp_path)
    add_artifact(archived)
    try:
        (scratch / "dangling").symlink_to(root / "missing" / "target", target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    with pytest.raises(mutator.LifecycleError, match="injected"):
        release(mutator, root, archived, event, inject_failure_at="after-receipt")
    receipt = next((archived / "retained-scratch-releases").glob("*.json"))
    body = json.loads(receipt.read_text(encoding="utf-8"))
    row = next(row for row in body["inventory"] if row["kind"] == "symlink")
    if malformation == "content-hash":
        row["targetSha256"] = "0" * 64
    elif malformation == "live-custody":
        row["targetCustody"] = "archive-target"
    else:
        row["targetPath"] = "."
    body["inventorySha256"] = hashlib.sha256(json.dumps(body["inventory"], sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    receipt.write_text(json.dumps(body, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    with pytest.raises(mutator.LifecycleError, match="inventory is malformed"):
        release(mutator, root, archived, event)
    assert scratch.is_dir() and (scratch / "dangling").is_symlink()


def test_inside_absent_link_partial_tombstone_rechecks_before_unlink(tmp_path: Path, monkeypatch) -> None:
    mutator, root, archived, scratch, event, closure, instant = archived_fixture(tmp_path)
    add_artifact(archived)
    try:
        (scratch / "dangling").symlink_to(Path("missing") / "target", target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    with pytest.raises(mutator.LifecycleError, match="injected"):
        release(mutator, root, archived, event, inject_failure_at="after-rename")
    tombstone = next(scratch.parent.glob(".*.orchestrarium-delete-*"))
    original_verify = mutator._verify_release_targets

    def target_appears(*args, **kwargs):
        if kwargs.get("surviving_root") is not None:
            (tombstone / "missing" / "target").mkdir(parents=True)
        return original_verify(*args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(mutator, "_verify_release_targets", target_appears)
        with pytest.raises(mutator.LifecycleError, match="became live"):
            release(mutator, root, archived, event)
    assert (tombstone / "dangling").is_symlink() and (tombstone / "payload.txt").is_file()
    (tombstone / "missing" / "target").rmdir()
    (tombstone / "missing").rmdir()
    assert release(mutator, root, archived, event).is_file()
    assert not tombstone.exists()
    assert mutator.close_item(root, archived.name, closure, instant) == archived


def prior_disposal_fixture(tmp_path: Path):
    """The synthetic operator has reviewed this exact completed action mapping."""
    helpers = load_module(SCRATCH_FIXTURE, f"prior_disposal_fixture_{id(tmp_path)}")
    root = tmp_path / "repo"
    mutator, item, scratch, _payload = helpers.seed_item(root, disposition="retain")
    raw = (item / "agent-runs.jsonl").read_bytes().splitlines()[-1]
    event = json.loads(raw)
    entry = event["scratchEvidence"][0]
    (scratch / "payload.txt").unlink()
    scratch.rmdir()
    (item / "completed-action.md").write_text(
        f"The reviewed synthetic action removed only {entry['path']}; canonical observations remain.\n",
        encoding="utf-8",
    )
    (item / "reviewed-admission.md").write_text(
        f"The synthetic operator reviewed and accepted this exact {event['runId']}/{entry['entryId']} action mapping.\n",
        encoding="utf-8",
    )
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    request = {
        "schemaVersion": 1, "mode": "accepted-prior-disposal", "workItem": item.name,
        "recordedAt": "2026-08-09T00:20:00Z", "subjects": [{
            "runId": event["runId"], "entryId": entry["entryId"],
            "eventSha256": hashlib.sha256(raw).hexdigest(), "sourcePath": entry["path"],
            "canonicalPointer": entry["canonicalPointer"],
            "canonicalPointerSha256": digest(item / entry["canonicalPointer"]),
            "actionEvidence": [{"artifact": "completed-action.md", "sha256": digest(item / "completed-action.md"),
                                "actionFrom": "2026-08-09T00:10:00Z", "actionThrough": "2026-08-09T00:10:01Z"}],
            "admissionEvidence": {"artifact": "reviewed-admission.md", "sha256": digest(item / "reviewed-admission.md")},
            "rationale": "Reviewed exact completed disposal preserves canonical observations; raw recovery is not certified.",
        }],
    }
    request_file = tmp_path / "reviewed-request.json"
    request_file.write_text(json.dumps(request), encoding="utf-8")
    return helpers, mutator, root, item, scratch, event, request, request_file


def reconciliation_cli(root: Path, item: Path, request_file: Path, *, apply=True):
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts" / "mutate-work-item.py"),
         "reconcile-retained-scratch", "--root", str(root), "--slug", item.name,
         "--request-file", str(request_file), *(["--apply"] if apply else [])],
        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30,
    )


def test_reconcile_prior_disposal_public_cli_preserves_history_and_replays(tmp_path: Path):
    helpers, mutator, root, item, scratch, event, request, request_file = prior_disposal_fixture(tmp_path)
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    refused = reconciliation_cli(root, item, request_file, apply=False)
    assert refused.returncode == 1 and "WI-SCRATCH-RECONCILIATION-APPLY-REQUIRED" in refused.stdout
    assert {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before
    applied = reconciliation_cli(root, item, request_file)
    assert applied.returncode == 0, applied.stdout + applied.stderr
    path = mutator._release_receipt_path(item, event["runId"], event["scratchEvidence"][0]["entryId"])
    receipt_bytes = path.read_bytes()
    receipt = json.loads(receipt_bytes)
    assert receipt["schemaVersion"] == 2 and receipt["mode"] == "accepted-prior-disposal"
    assert receipt["rawRecovery"] == "not-certified" and receipt["evidenceScope"] == "canonical-observations"
    assert not {"inventory", "inventorySha256", "archive"} & set(receipt)
    after = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert set(after) - set(before) == {path.relative_to(root)}
    assert {p: after[p] for p in before} == before and not scratch.exists()
    replay = reconciliation_cli(root, item, request_file)
    assert replay.returncode == 0, replay.stdout + replay.stderr
    assert path.read_bytes() == receipt_bytes
    assert mutator._scratch_disposition_plan(root, item, archived=False)[0].disposition == "completed-disposal"
    instant = "2026-08-09T01:00:00Z"
    closure_file = tmp_path / "closure-input.md"
    closure_file.write_bytes(helpers.closure(instant))
    argv = [sys.executable, "-B", str(ROOT / "scripts/mutate-work-item.py"), "close", "--root", str(root),
            "--slug", item.name, "--closure-file", str(closure_file), "--terminal-instant", instant]
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    for _ in range(2):
        closed = subprocess.run(argv, cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
        assert closed.returncode == 0, closed.stdout + closed.stderr
    archived = root / "work-items/archive/2026-08" / item.name
    assert (archived / "agent-runs.jsonl").read_bytes() == before[item.relative_to(root) / "agent-runs.jsonl"]
    assert mutator._release_receipt_path(archived, receipt["runId"], receipt["entryId"]).read_bytes() == receipt_bytes
    assert not scratch.exists()
    before_reverse = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    reverse = subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts/mutate-work-item.py"), "release-retained-scratch",
         "--root", str(root), "--slug", archived.name, "--terminal-run-id", receipt["runId"],
         "--expected-event-sha256", receipt["eventSha256"], "--entry-id", receipt["entryId"],
         "--artifact", receipt["canonicalPointer"], "--rationale", "Reviewed synthetic reverse-mode refusal.", "--apply"],
        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30,
    )
    assert reverse.returncode == 1
    assert reverse.stdout == "WI-SCRATCH-RELEASE-RECEIPT: live-inventory release requires a Version 1 receipt\n"
    assert reverse.stderr == ""
    assert {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before_reverse
    assert (archived / "agent-runs.jsonl").read_bytes() == before[item.relative_to(root) / "agent-runs.jsonl"]
    assert mutator._release_receipt_path(archived, receipt["runId"], receipt["entryId"]).read_bytes() == receipt_bytes
    assert not scratch.exists()
    print("PRIOR_DISPOSAL_PUBLIC_CHANNEL", applied.stdout.strip(), "close/replay exits=0; ledger/pointers unchanged")
    print("PRIOR_DISPOSAL_REVERSE_MODE", reverse.stdout.strip(), "exit=1; no traceback; all filesystem bytes unchanged")


@pytest.mark.parametrize("fault", [
    "raw-event", "path", "pointer", "action", "admission", "unknown-subject", "duplicate",
    "cross-item", "inventory", "mode", "empty", "default-version", "duplicate-json", "backdated",
])
def test_reconciliation_rejects_unbound_or_malformed_requests(tmp_path: Path, fault: str):
    _helpers, _mutator, root, item, scratch, _event, request, request_file = prior_disposal_fixture(tmp_path)
    subject = request["subjects"][0]
    if fault == "raw-event": subject["eventSha256"] = "0" * 64
    elif fault == "path": subject["sourcePath"] += "-other"
    elif fault == "pointer": subject["canonicalPointerSha256"] = "0" * 64
    elif fault == "action": subject["actionEvidence"][0]["sha256"] = "0" * 64
    elif fault == "admission": (item / "reviewed-admission.md").unlink()
    elif fault == "unknown-subject": subject["entryId"] = "unproved-entry"
    elif fault == "duplicate": request["subjects"].append(dict(subject))
    elif fault == "cross-item": request["workItem"] = "other-item"
    elif fault == "inventory": subject["inventory"] = []
    elif fault == "mode": request["mode"] = "unrecognized"
    elif fault == "empty": request["subjects"] = []
    elif fault == "default-version": request["schemaVersion"] = False
    elif fault == "backdated": request["recordedAt"] = subject["actionEvidence"][0]["actionThrough"]
    encoded = json.dumps(request)
    if fault == "duplicate-json": encoded = encoded.replace('"schemaVersion": 1', '"schemaVersion": 1, "schemaVersion": 1', 1)
    request_file.write_text(encoded, encoding="utf-8")
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    result = reconciliation_cli(root, item, request_file)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "WI-SCRATCH-" in result.stdout
    assert {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before
    assert not scratch.exists() and not (item / "retained-scratch-releases").exists()


@pytest.mark.parametrize("state", ["original", "tombstone"])
def test_reconciliation_preserves_present_or_tombstoned_data(tmp_path: Path, state: str):
    _helpers, mutator, root, item, scratch, event, _request, request_file = prior_disposal_fixture(tmp_path)
    entry = event["scratchEvidence"][0]
    present = scratch if state == "original" else mutator._scratch_tombstone(scratch, item.name, event["runId"], entry["entryId"])
    present.write_bytes(b"newly present bytes must remain")
    result = reconciliation_cli(root, item, request_file)
    assert result.returncode == 1 and "WI-SCRATCH-RECONCILIATION-DRIFT" in result.stdout
    assert present.read_bytes() == b"newly present bytes must remain"
    assert not (item / "retained-scratch-releases").exists()


@pytest.mark.parametrize("fault", ["entry-pin", "mode", "stage", "pointer-drift"])
def test_reconciliation_receipt_and_proof_drift_never_replace_prior_bytes(tmp_path: Path, fault: str):
    _helpers, mutator, root, item, scratch, event, _request, request_file = prior_disposal_fixture(tmp_path)
    assert reconciliation_cli(root, item, request_file).returncode == 0
    path = mutator._release_receipt_path(item, event["runId"], event["scratchEvidence"][0]["entryId"])
    receipt = json.loads(path.read_bytes())
    if fault == "entry-pin": receipt["entrySha256"] = "0" * 64; path.write_text(json.dumps(receipt), encoding="utf-8")
    elif fault == "mode": receipt["mode"] = "unknown"; path.write_text(json.dumps(receipt), encoding="utf-8")
    elif fault == "stage": path.with_name(f".{path.name}.foreign.tmp").write_bytes(b"partial metadata")
    elif fault == "pointer-drift": (item / "implementation.md").write_bytes(b"changed canonical observations")
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    refused = reconciliation_cli(root, item, request_file)
    assert refused.returncode == 1, refused.stdout + refused.stderr
    with pytest.raises(mutator.LifecycleError):
        mutator._scratch_disposition_plan(root, item, archived=False)
    assert {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before
    assert not scratch.exists()


def add_second_retained_subject(root, item, event, request, request_file):
    entry = {**event["scratchEvidence"][0], "entryId": "entry-b"}
    entry["path"] = str(Path(entry["path"]).with_name("entry-b")).replace("\\", "/")
    event["scratchEvidence"].append(entry)
    ledger = item / "agent-runs.jsonl"
    lines = ledger.read_bytes().splitlines()
    lines[-1] = json.dumps(event, separators=(",", ":")).encode()
    ledger.write_bytes(b"\n".join(lines) + b"\n")
    scratch = root / entry["path"]
    scratch.mkdir(); (scratch / "payload.txt").write_bytes(b"second reviewed synthetic payload")
    (scratch / "payload.txt").unlink(); scratch.rmdir()
    subject = json.loads(json.dumps(request["subjects"][0]))
    subject.update(entryId=entry["entryId"], sourcePath=entry["path"])
    request["subjects"].append(subject)
    (item / "completed-action.md").write_text("The operator reviewed both exact synthetic completed removals.\n", encoding="utf-8")
    (item / "reviewed-admission.md").write_text("Both requested run/entry mappings were explicitly reviewed by the synthetic operator.\n", encoding="utf-8")
    for row in request["subjects"]:
        row["eventSha256"] = hashlib.sha256(lines[-1]).hexdigest()
        row["actionEvidence"][0]["sha256"] = hashlib.sha256((item / "completed-action.md").read_bytes()).hexdigest()
        row["admissionEvidence"]["sha256"] = hashlib.sha256((item / "reviewed-admission.md").read_bytes()).hexdigest()
    request_file.write_text(json.dumps(request), encoding="utf-8")


def test_reconciliation_batch_failure_rolls_back_only_new_metadata(tmp_path: Path, monkeypatch):
    _helpers, mutator, root, item, _scratch, event, request, request_file = prior_disposal_fixture(tmp_path)
    add_second_retained_subject(root, item, event, request, request_file)
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    real_publish = mutator._publish_release_receipt
    calls = 0
    def fail_second(path, encoded, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2: raise OSError("injected second metadata publication failure")
        return real_publish(path, encoded, **kwargs)
    monkeypatch.setattr(mutator, "_publish_release_receipt", fail_second)
    with pytest.raises(OSError, match="second metadata publication"):
        mutator.reconcile_retained_scratch(root, item.name, request_file, apply=True)
    assert calls == 2
    assert {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before
    assert not (item / "retained-scratch-releases").exists()


@pytest.mark.parametrize("change", ["reappearance", "proof-drift"])
def test_completed_disposal_rechecks_before_and_after_archive_without_deletion(tmp_path: Path, monkeypatch, change: str):
    helpers, mutator, root, item, scratch, _event, _request, request_file = prior_disposal_fixture(tmp_path)
    assert reconciliation_cli(root, item, request_file).returncode == 0
    instant = "2026-08-09T01:00:00Z"
    if change == "reappearance":
        prepare = mutator._prepare_bug_dispositions
        def prepare_then_reappear(*args, **kwargs):
            result = prepare(*args, **kwargs)
            scratch.write_bytes(b"late unrelated payload")
            return result
        monkeypatch.setattr(mutator, "_prepare_bug_dispositions", prepare_then_reappear)
    else:
        refresh = mutator.refresh_readme
        def refresh_then_drift(*args, **kwargs):
            result = refresh(*args, **kwargs)
            archived = root / "work-items/archive/2026-08" / item.name
            (archived / "implementation.md").write_bytes(b"late changed canonical observations")
            return result
        monkeypatch.setattr(mutator, "refresh_readme", refresh_then_drift)
    with pytest.raises(mutator.LifecycleError, match="completed-disposal|reviewed evidence"):
        mutator.close_item(root, item.name, helpers.closure(instant), instant)
    if change == "reappearance":
        assert scratch.read_bytes() == b"late unrelated payload" and item.is_dir()
    else:
        assert (root / "work-items/archive/2026-08" / item.name / "implementation.md").read_bytes() == b"late changed canonical observations"
        assert not scratch.exists()


def test_reconciliation_preserves_unselected_missing_retention_and_open_launch(tmp_path: Path):
    helpers, mutator, root, item, scratch, event, request, request_file = prior_disposal_fixture(tmp_path)
    add_second_retained_subject(root, item, event, request, request_file)
    request["subjects"].pop()
    request_file.write_text(json.dumps(request), encoding="utf-8")
    applied = reconciliation_cli(root, item, request_file)
    assert applied.returncode == 0, applied.stdout + applied.stderr
    with pytest.raises(mutator.LifecycleError, match="retained scratch evidence is missing"):
        mutator._scratch_disposition_plan(root, item, archived=False)
    ledger = item / "agent-runs.jsonl"
    original_rows = ledger.read_bytes()
    launch = json.loads(original_rows.splitlines()[0]); launch["runId"] = "unrelated-open-launch"
    ledger.write_bytes(original_rows + json.dumps(launch).encode() + b"\n")
    assert reconciliation_cli(root, item, request_file).returncode == 0
    assert ledger.read_bytes().startswith(original_rows)
    with pytest.raises(mutator.LifecycleError, match="WI-LEDGER-UNSETTLED|launch"):
        mutator.close_item(root, item.name, helpers.closure("2026-08-09T01:00:00Z"), "2026-08-09T01:00:00Z")
    assert item.is_dir() and not scratch.exists()
