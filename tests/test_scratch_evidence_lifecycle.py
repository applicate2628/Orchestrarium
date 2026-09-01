from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MUTATOR = ROOT / "scripts" / "mutate-work-item.py"
VALIDATOR = ROOT / "scripts" / "validate-work-item-state.py"
CLASSIFIER = ROOT / "scripts" / "maintenance" / "cleanup.py"
LIFECYCLE_SCHEMA_MARKER = "Lifecycle-schema: work-items-physical-v1"
REGENERATION_MARKER = (
    "Scratch evidence: regeneration-only; all load-bearing observations retained."
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def quick_status() -> str:
    return """---
template: quick-fix
status: active
started: 2026-08-09T00:00:00Z
updated: 2026-08-09T00:00:00Z
---

- **Task**: Exercise scratch disposition.
- **Current step**: Close the item.
- **Last result**: Evidence is terminal.
- **Next action**: Run the lifecycle owner.
"""


def closure(instant: str) -> bytes:
    return (
        f"Closed: {instant}\n"
        "Outcome: Scratch disposition completed.\n"
        "Evidence: focused lifecycle test\n"
        "Residual risk: Same-user final-syscall races remain.\n"
    ).encode("utf-8")


def ledger_events(
    slug: str,
    entry_id: str,
    *,
    disposition: str,
    proof: dict | None,
    artifact_sha: str,
) -> tuple[list[dict], str]:
    launch_id = "platform-launch-0001"
    terminal_id = "platform-terminal-0001"
    if proof and proof.get("kind") == "accepted-artifact":
        proof = {
            **proof,
            "artifactSha256": artifact_sha,
        }
    path = f".scratch/work-items/{slug}/{terminal_id}/{entry_id}"
    launch = {
        "schemaVersion": 2,
        "runId": launch_id,
        "workItem": slug,
        "role": "platform-engineer",
        "executionRole": "internal",
        "status": "running",
        "gate": "none",
        "scope": ["scratch evidence lifecycle"],
        "startedAt": "2026-08-09T00:00:00Z",
        "updatedAt": "2026-08-09T00:00:00Z",
        "eventKind": "launch",
    }
    scratch_entry = {
        "entryId": entry_id,
        "path": path,
        "disposition": disposition,
        "reason": "Owned terminal fixture.",
        "canonicalPointer": "implementation.md",
    }
    if proof is not None:
        scratch_entry["proof"] = proof
    terminal = {
        "schemaVersion": 2,
        "runId": terminal_id,
        "workItem": slug,
        "role": "platform-engineer",
        "executionRole": "internal",
        "status": "completed",
        "gate": "PASS",
        "scope": ["scratch evidence lifecycle"],
        "artifact": "implementation.md",
        "evidence": [{"kind": "artifact", "ref": "implementation.md"}],
        "startedAt": "2026-08-09T00:00:00Z",
        "updatedAt": "2026-08-09T00:01:00Z",
        "eventKind": "terminal",
        "launchRunId": launch_id,
        "scratchEvidence": [scratch_entry],
    }
    return [launch, terminal], path


def seed_item(
    root: Path,
    *,
    slug: str = "scratch-owner",
    disposition: str = "delete",
    proof_kind: str = "git-object-set",
    content: str = "recoverable scratch bytes\n",
) -> tuple[object, Path, Path, bytes]:
    mutator = load_module(MUTATOR, f"mutator_{slug}_{id(root)}")
    item = root / "work-items" / "active" / slug
    write(item / "status.md", quick_status())
    write(
        item / "bug-dispositions.json",
        json.dumps(
            {
                "schemaVersion": 1,
                "workItem": slug,
                "closedAt": "2026-08-09T01:00:00Z",
                "bugs": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    artifact_text = f"# Implementation\n\n{REGENERATION_MARKER}\n"
    write(item / "implementation.md", artifact_text)
    proof = None if disposition == "retain" else {"kind": proof_kind}
    if proof is not None and proof_kind == "accepted-artifact":
        write(root / "scripts" / "reproduce.py", "print('reproduce')\n")
        proof.update(
            {
                "producer": "scripts/reproduce.py",
                "reproduce": "python scripts/reproduce.py",
            }
        )
    events, relative = ledger_events(
        slug,
        "entry-a",
        disposition=disposition,
        proof=proof,
        artifact_sha=hashlib.sha256((item / "implementation.md").read_bytes()).hexdigest(),
    )
    write(
        item / "agent-runs.jsonl",
        "".join(json.dumps(event, separators=(",", ":")) + "\n" for event in events),
    )
    evidence_root = root / Path(relative)
    write(evidence_root / "payload.txt", content)
    if proof_kind == "git-object-set":
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        seeded = subprocess.run(
            ["git", "-C", str(root), "hash-object", "-w", str(evidence_root / "payload.txt")],
            check=True,
            capture_output=True,
            text=True,
        )
        assert seeded.stdout.strip()
    mutator.refresh_readme(root, allow_marker_bootstrap=True)
    return mutator, item, evidence_root, (evidence_root / "payload.txt").read_bytes()


def test_classifier_is_link_safe_pure_and_git_complete(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    mutator, _item, evidence_root, before = seed_item(root)
    classifier = load_module(CLASSIFIER, "scratch_classifier")

    snapshot = classifier.classify_owned_tree(evidence_root, root)

    assert snapshot.file_count == 1
    assert snapshot.all_git_recoverable
    assert (evidence_root / "payload.txt").read_bytes() == before
    assert not list(evidence_root.parent.glob(".*.orchestrarium-delete-*"))
    assert mutator is not None


def test_close_deletes_only_proven_owned_root_after_archive_and_readme(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    mutator, _item, evidence_root, _before = seed_item(root)
    instant = "2026-08-09T01:00:00Z"

    archived = mutator.close_item(root, "scratch-owner", closure(instant), instant)

    assert archived == root / "work-items" / "archive" / "2026-08" / "scratch-owner"
    assert not evidence_root.exists()
    assert not list(evidence_root.parent.glob(".*.orchestrarium-delete-*"))
    assert "scratch-owner" in (root / "work-items" / "README.md").read_text(encoding="utf-8")


def test_close_retain_is_a_noop_and_requires_existing_pointer(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    mutator, _item, evidence_root, before = seed_item(root, disposition="retain")
    instant = "2026-08-09T01:00:00Z"

    archived = mutator.close_item(root, "scratch-owner", closure(instant), instant)

    assert archived.is_dir()
    assert (evidence_root / "payload.txt").read_bytes() == before


def test_retain_checks_only_root_metadata_and_same_item_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    mutator, _item, evidence_root, before = seed_item(root, disposition="retain")
    write(evidence_root / "unique.txt", "not recoverable from Git")
    outside = root / "outside.txt"
    write(outside, "outside")
    try:
        (evidence_root / "nested-link").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable")

    classifier = mutator._scratch_classifier_module()
    monkeypatch.setattr(
        classifier,
        "classify_owned_tree",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("retain must not traverse or classify contents")
        ),
    )
    monkeypatch.setattr(mutator, "_scratch_classifier_module", lambda: classifier)

    archived = mutator.close_item(
        root,
        "scratch-owner",
        closure("2026-08-09T01:00:00Z"),
        "2026-08-09T01:00:00Z",
    )

    assert archived.is_dir()
    assert (evidence_root / "payload.txt").read_bytes() == before
    assert (evidence_root / "unique.txt").is_file()
    assert (evidence_root / "nested-link").is_symlink()


def test_readme_failure_rolls_back_archive_and_never_starts_scratch_deletion(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    mutator, _item, evidence_root, before = seed_item(root)
    instant = "2026-08-09T01:00:00Z"

    with pytest.raises(mutator.LifecycleError) as raised:
        mutator.close_item(
            root,
            "scratch-owner",
            closure(instant),
            instant,
            inject_readme_failure=True,
        )

    assert raised.value.failure_id == "WI-README-STALE"
    assert (evidence_root / "payload.txt").read_bytes() == before
    assert not list(evidence_root.parent.glob(".*.orchestrarium-delete-*"))
    assert (root / "work-items" / "active" / "scratch-owner").is_dir()
    assert not (root / "work-items" / "archive" / "2026-08" / "scratch-owner").exists()


def test_post_archive_removal_failure_is_pending_and_replay_resumes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    mutator, _item, evidence_root, _before = seed_item(root)
    instant = "2026-08-09T01:00:00Z"
    real_remove = mutator._remove_scratch_tree

    def fail_remove(_path: Path) -> None:
        raise OSError("injected removal failure")

    mutator._remove_scratch_tree = fail_remove
    try:
        with pytest.raises(mutator.LifecycleError) as raised:
            mutator.close_item(root, "scratch-owner", closure(instant), instant)
    finally:
        mutator._remove_scratch_tree = real_remove

    assert raised.value.failure_id == "WI-SCRATCH-DISPOSITION-PENDING"
    assert not evidence_root.exists()
    tombstones = list(evidence_root.parent.glob(".*.orchestrarium-delete-*"))
    assert len(tombstones) == 1

    archived = mutator.close_item(root, "scratch-owner", closure(instant), instant)
    assert archived.is_dir()
    assert not tombstones[0].exists()


def test_identity_drift_after_archive_is_pending_without_deletion(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    mutator, _item, evidence_root, _before = seed_item(root)
    instant = "2026-08-09T01:00:00Z"
    real_refresh = mutator.refresh_readme

    def refresh_then_drift(refresh_root: Path, **kwargs) -> str:
        result = real_refresh(refresh_root, **kwargs)
        with (evidence_root / "payload.txt").open("a", encoding="utf-8") as stream:
            stream.write("drift\n")
        return result

    mutator.refresh_readme = refresh_then_drift
    with pytest.raises(mutator.LifecycleError) as raised:
        mutator.close_item(root, "scratch-owner", closure(instant), instant)

    assert raised.value.failure_id == "WI-SCRATCH-DISPOSITION-PENDING"
    assert evidence_root.is_dir()
    assert (root / "work-items" / "archive" / "2026-08" / "scratch-owner").is_dir()


def test_dangling_root_link_after_archive_is_pending_not_completed(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    mutator, _item, evidence_root, _before = seed_item(root)
    instant = "2026-08-09T01:00:00Z"
    real_refresh = mutator.refresh_readme
    backup = evidence_root.with_name("entry-backup")

    def refresh_then_swap(refresh_root: Path, **kwargs) -> str:
        result = real_refresh(refresh_root, **kwargs)
        evidence_root.rename(backup)
        evidence_root.symlink_to(root / "missing-target", target_is_directory=True)
        return result

    mutator.refresh_readme = refresh_then_swap
    with pytest.raises(mutator.LifecycleError) as raised:
        mutator.close_item(root, "scratch-owner", closure(instant), instant)

    assert raised.value.failure_id == "WI-SCRATCH-DISPOSITION-PENDING"
    assert evidence_root.is_symlink()
    assert (backup / "payload.txt").is_file()


def test_original_and_tombstone_conflict_fails_closed_on_replay(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    mutator, _item, evidence_root, _before = seed_item(root)
    instant = "2026-08-09T01:00:00Z"
    real_remove = mutator._remove_scratch_tree
    mutator._remove_scratch_tree = lambda _path: (_ for _ in ()).throw(OSError("stop"))
    try:
        with pytest.raises(mutator.LifecycleError):
            mutator.close_item(root, "scratch-owner", closure(instant), instant)
    finally:
        mutator._remove_scratch_tree = real_remove
    write(evidence_root / "foreign.txt", "foreign")

    with pytest.raises(mutator.LifecycleError) as raised:
        mutator.close_item(root, "scratch-owner", closure(instant), instant)

    assert raised.value.failure_id == "WI-SCRATCH-DISPOSITION-CONFLICT"
    assert evidence_root.is_dir()


def test_unproven_or_unsafe_delete_fails_before_archive(tmp_path: Path) -> None:
    for case in ("unique", "link"):
        root = tmp_path / case
        mutator, item, evidence_root, before = seed_item(root)
        if case == "unique":
            write(evidence_root / "unique.txt", "not in git")
        else:
            outside = root / "outside.txt"
            write(outside, "outside")
            try:
                (evidence_root / "unsafe-link").symlink_to(outside)
            except (OSError, NotImplementedError):
                pytest.skip("symlinks are unavailable")

        with pytest.raises(mutator.LifecycleError) as raised:
            mutator.close_item(
                root,
                "scratch-owner",
                closure("2026-08-09T01:00:00Z"),
                "2026-08-09T01:00:00Z",
            )

        assert raised.value.failure_id in {"WI-SCRATCH-PROOF-FAILED", "WI-SCRATCH-UNSAFE-ENTRY"}
        assert item.is_dir()
        assert (evidence_root / "payload.txt").read_bytes() == before
        assert not (root / "work-items" / "archive").exists()


def test_accepted_artifact_proof_checks_hash_marker_and_producer(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    mutator, item, evidence_root, _before = seed_item(root, proof_kind="accepted-artifact")
    instant = "2026-08-09T01:00:00Z"

    archived = mutator.close_item(root, "scratch-owner", closure(instant), instant)
    assert archived.is_dir()
    assert not evidence_root.exists()

    stale_root = tmp_path / "stale"
    stale_mutator, stale_item, stale_evidence, stale_before = seed_item(
        stale_root, proof_kind="accepted-artifact"
    )
    with (stale_item / "implementation.md").open("a", encoding="utf-8") as stream:
        stream.write("drift\n")
    with pytest.raises(stale_mutator.LifecycleError) as raised:
        stale_mutator.close_item(
            stale_root, "scratch-owner", closure(instant), instant
        )
    assert raised.value.failure_id == "WI-SCRATCH-PROOF-FAILED"
    assert (stale_evidence / "payload.txt").read_bytes() == stale_before


def test_namespace_coverage_and_legacy_compatibility(tmp_path: Path) -> None:
    root = tmp_path / "covered"
    mutator, item, evidence_root, before = seed_item(root)
    write(evidence_root.parent / "unclaimed" / "payload.txt", "unclaimed")
    instant = "2026-08-09T01:00:00Z"
    with pytest.raises(mutator.LifecycleError) as raised:
        mutator.close_item(root, "scratch-owner", closure(instant), instant)
    assert raised.value.failure_id == "WI-SCRATCH-OWNERSHIP-INCOMPLETE"
    assert item.is_dir()
    assert (evidence_root / "payload.txt").read_bytes() == before

    legacy_root = tmp_path / "legacy"
    legacy = load_module(MUTATOR, "legacy_mutator")
    legacy_item = legacy_root / "work-items" / "active" / "legacy-item"
    write(legacy_item / "status.md", quick_status())
    write(
        legacy_item / "bug-dispositions.json",
        json.dumps(
            {
                "schemaVersion": 1,
                "workItem": "legacy-item",
                "closedAt": instant,
                "bugs": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    legacy.refresh_readme(legacy_root, allow_marker_bootstrap=True)
    archived = legacy.close_item(
        legacy_root,
        "legacy-item",
        closure(instant),
        instant,
    )
    assert archived.is_dir()
    assert LIFECYCLE_SCHEMA_MARKER in (archived / "status.md").read_text(encoding="utf-8")


def test_undeclared_canonical_namespace_blocks_close(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    mutator = load_module(MUTATOR, "undeclared_namespace_mutator")
    item = root / "work-items" / "active" / "legacy-item"
    write(item / "status.md", quick_status())
    historical_scratch = root / ".scratch" / "work-items" / "legacy-item" / "historical"
    write(historical_scratch / "keep.txt", "unowned bytes")
    mutator.refresh_readme(root, allow_marker_bootstrap=True)

    with pytest.raises(mutator.LifecycleError) as raised:
        mutator.close_item(
            root,
            "legacy-item",
            closure("2026-08-09T01:00:00Z"),
            "2026-08-09T01:00:00Z",
        )

    assert raised.value.failure_id == "WI-SCRATCH-OWNERSHIP-INCOMPLETE"
    assert item.is_dir()
    assert (historical_scratch / "keep.txt").read_text(encoding="utf-8") == "unowned bytes"


@pytest.mark.parametrize(
    "pointer",
    (
        "../../../../README.md",
        "work-items/active/sibling/implementation.md",
        "C:/absolute/implementation.md",
    ),
)
def test_scratch_pointer_must_be_inside_exact_item(tmp_path: Path, pointer: str) -> None:
    root = tmp_path / "repo"
    mutator, item, evidence_root, before = seed_item(root, proof_kind="accepted-artifact")
    write(root / "README.md", f"{REGENERATION_MARKER}\n")
    write(root / "work-items" / "active" / "sibling" / "implementation.md", REGENERATION_MARKER)
    events = [json.loads(line) for line in (item / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()]
    events[-1]["scratchEvidence"][0]["canonicalPointer"] = pointer
    (item / "agent-runs.jsonl").write_text(
        "".join(json.dumps(event, separators=(",", ":")) + "\n" for event in events),
        encoding="utf-8",
    )

    with pytest.raises(mutator.LifecycleError) as raised:
        mutator.close_item(
            root,
            "scratch-owner",
            closure("2026-08-09T01:00:00Z"),
            "2026-08-09T01:00:00Z",
        )

    assert "WI-SCRATCH-POINTER-OUTSIDE-ITEM" in str(raised.value)
    assert item.is_dir()
    assert (evidence_root / "payload.txt").read_bytes() == before


def test_ledger_uniqueness_is_casefolded_across_events(tmp_path: Path) -> None:
    validator = load_module(VALIDATOR, "casefold_scratch_validator")
    root = tmp_path / "repo"
    _mutator, item, _evidence_root, _before = seed_item(root, disposition="retain")
    events = validator.load_jsonl(item / "agent-runs.jsonl", [])
    duplicate = json.loads(json.dumps(events[-1]))
    duplicate["runId"] = duplicate["runId"].upper()
    duplicate["launchRunId"] = events[0]["runId"]
    write(
        item / "agent-runs.jsonl",
        "".join(json.dumps(event, separators=(",", ":")) + "\n" for event in [*events, duplicate]),
    )

    errors = validator.validate_work_item(item)

    assert any("duplicate runId" in error for error in errors), errors
    assert any("WI-SCRATCH-OWNERSHIP-CONFLICT" in error for error in errors), errors


@pytest.mark.parametrize(
    "lines",
    (
        [],
        ["{a} blob 1"],
        ["{a} blob 1", "{b} blob 2", "{b} blob 2"],
        ["{a} tree 1", "{b} blob 2"],
        ["{a} blob nope", "{b} missing"],
        ["{c} blob 1", "{b} missing"],
    ),
)
def test_git_blob_batch_proof_requires_exact_well_formed_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, lines: list[str]
) -> None:
    classifier = load_module(CLASSIFIER, f"git_batch_{len(lines)}_{id(lines)}")
    a, b, c = "a" * 40, "b" * 40, "c" * 40

    class Result:
        returncode = 0
        stdout = "\n".join(line.format(a=a, b=b, c=c) for line in lines)

    monkeypatch.setattr(classifier.subprocess, "run", lambda *_args, **_kwargs: Result())

    assert classifier.inspect_git_object_set(tmp_path, {a, b}) is None


def test_git_blob_batch_proof_accepts_exact_blob_and_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    classifier = load_module(CLASSIFIER, "git_batch_valid")
    a, b = "a" * 40, "b" * 40

    class Result:
        returncode = 0
        stdout = f"{a} blob 12\n{b} missing\n"

    monkeypatch.setattr(classifier.subprocess, "run", lambda *_args, **_kwargs: Result())

    assert classifier.inspect_git_object_set(tmp_path, {a, b}) == {b}


def test_classifier_exposes_public_lifecycle_api() -> None:
    classifier = load_module(CLASSIFIER, "public_classifier_api")
    for name in (
        "inspect_owned_namespace",
        "inspect_root_no_follow",
        "classify_owned_tree",
        "identity_matches",
    ):
        assert callable(getattr(classifier, name))


def test_scratch_evidence_schema_is_bounded_and_terminal_only(tmp_path: Path) -> None:
    validator = load_module(VALIDATOR, "scratch_validator")
    root = tmp_path / "repo"
    _mutator, item, _evidence_root, _before = seed_item(root)
    events = validator.load_jsonl(item / "agent-runs.jsonl", [])
    terminal = events[-1]

    assert validator.validate_work_item(item) == []
    for mutation, expected in (
        ({"eventKind": "standalone"}, "scratchEvidence requires eventKind terminal"),
        ({"scratchEvidence": []}, "scratchEvidence must be a non-empty bounded list"),
        (
            {"scratchEvidence": terminal["scratchEvidence"] * (validator.MAX_SCRATCH_EVIDENCE_ENTRIES + 1)},
            "scratchEvidence must be a non-empty bounded list",
        ),
    ):
        candidate = dict(terminal)
        candidate.update(mutation)
        candidate_errors: list[str] = []
        validator.validate_event(candidate, item, set(), candidate_errors)
        assert any(expected in error for error in candidate_errors), candidate_errors

    wrong_path = json.loads(json.dumps(terminal))
    wrong_path["scratchEvidence"][0]["path"] = ".scratch/work-items/other/run/entry"
    wrong_path_errors: list[str] = []
    validator.validate_event(wrong_path, item, set(), wrong_path_errors)
    assert any("exact owner namespace" in error for error in wrong_path_errors)

    ledger = item / "duplicate.jsonl"
    ledger.write_text('{"runId":"one","runId":"two"}\n', encoding="utf-8")
    parser_errors: list[str] = []
    assert validator.load_jsonl(ledger, parser_errors) == []
    assert any("duplicate JSON key" in error for error in parser_errors)

    schema = json.loads((ROOT / "shared" / "schemas" / "agent-runs.schema.json").read_text(encoding="utf-8"))
    assert schema["properties"]["scratchEvidence"]["maxItems"] == validator.MAX_SCRATCH_EVIDENCE_ENTRIES
    scratch_condition = next(
        condition
        for condition in schema["allOf"]
        if condition.get("if", {}).get("required") == ["scratchEvidence"]
    )
    assert scratch_condition["if"]["required"] == ["scratchEvidence"]
    assert scratch_condition["then"]["properties"]["eventKind"] == {"const": "terminal"}


def test_schema_owns_parser_and_scratch_bounds(tmp_path: Path) -> None:
    validator = load_module(VALIDATOR, "schema_owned_bounds_validator")
    schema = validator.AGENT_RUN_SCHEMA
    scratch = schema["properties"]["scratchEvidence"]
    properties = scratch["items"]["properties"]

    assert validator.MAX_LEDGER_LINE_CHARS == schema["x-orchestrarium-jsonl"]["maxLineChars"]
    assert validator.MAX_LEDGER_EVENTS == schema["x-orchestrarium-jsonl"]["maxEvents"]
    assert validator.MAX_JSON_NESTING_DEPTH == schema["x-orchestrarium-jsonl"]["maxNestingDepth"]
    assert (
        validator.MAX_SCRATCH_EVIDENCE_JSON_BYTES
        == scratch["x-orchestrarium-maxRawUtf8Bytes"]
    )
    assert validator.MAX_SCRATCH_PATH_LENGTH == properties["path"]["maxLength"]
    assert validator.MAX_SCRATCH_PRODUCER_LENGTH == 512

    root = tmp_path / "repo"
    _mutator, item, _evidence_root, _before = seed_item(root, proof_kind="accepted-artifact")
    terminal = validator.load_jsonl(item / "agent-runs.jsonl", [])[-1]
    terminal["scratchEvidence"][0]["proof"]["producer"] = "p" * 513
    errors: list[str] = []
    validator.validate_event(terminal, item, set(), errors)
    assert any("producer exceeds maximum length 512" in error for error in errors), errors


def test_jsonl_reader_streams_and_strict_decoder_rejects_nested_duplicate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    validator = load_module(VALIDATOR, "streaming_strict_validator")
    ledger = tmp_path / "events.jsonl"
    ledger.write_text('{"runId":"run-valid","nested":{"key":1,"key":2}}\n', encoding="utf-8")

    monkeypatch.setattr(
        Path,
        "read_text",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("load_jsonl must stream through an open file")
        ),
    )
    errors: list[str] = []
    assert validator.load_jsonl(ledger, errors) == []
    assert any("duplicate JSON key: key" in error for error in errors), errors
