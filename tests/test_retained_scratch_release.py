from __future__ import annotations

import hashlib
import importlib.util
import json
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


@pytest.mark.parametrize("target_kind", ["dangling", "external", "chained"])
def test_unsafe_link_target_refused_before_receipt_or_deletion(tmp_path: Path, target_kind: str) -> None:
    mutator, root, archived, scratch, event, _closure, _instant = archived_fixture(tmp_path)
    add_artifact(archived)
    target = scratch / "payload.txt"
    if target_kind == "dangling":
        target = scratch / "missing.txt"
    elif target_kind == "external":
        target = tmp_path / "outside.txt"
        target.write_bytes(b"external")
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


@pytest.mark.parametrize("target_kind", ["file", "directory"])
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


def test_cli_requires_apply_and_releases_only_named_root(tmp_path: Path) -> None:
    mutator, root, archived, scratch, event, _closure, _instant = archived_fixture(tmp_path)
    try:
        (scratch / "alias.txt").symlink_to(Path("payload.txt"))
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    add_artifact(archived)
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
