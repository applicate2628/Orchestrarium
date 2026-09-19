from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MUTATOR = ROOT / "scripts" / "mutate-work-item.py"
CLASSIFIER = ROOT / "scripts" / "maintenance" / "cleanup.py"
SCRATCH_FIXTURE = ROOT / "tests" / "test_scratch_evidence_lifecycle.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def retained_file_fixture(root: Path, *, slug: str = "retained-file-owner"):
    helpers = load_module(SCRATCH_FIXTURE, f"retained_file_helpers_{id(root)}")
    mutator, item, evidence_root, _before = helpers.seed_item(
        root,
        slug=slug,
        disposition="retain",
    )
    events = [
        json.loads(line)
        for line in (item / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    terminal = events[-1]
    entry = terminal["scratchEvidence"][0]
    entry["entryId"] = "receipt.json"
    entry["path"] = (
        f".scratch/work-items/{slug}/{terminal['runId']}/receipt.json"
    )
    ledger_bytes = b"".join(
        json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        + b"\n"
        for event in events
    )
    (item / "agent-runs.jsonl").write_bytes(ledger_bytes)
    (evidence_root / "payload.txt").unlink()
    evidence_root.rmdir()
    retained = evidence_root.with_name("receipt.json")
    retained_bytes = b'{"schemaVersion":1,"status":"settled"}\n'
    retained.write_bytes(retained_bytes)
    return helpers, mutator, item, retained, retained_bytes, ledger_bytes


def ledger_events(item: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (item / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()
    ]


def write_ledger(item: Path, events: list[dict]) -> bytes:
    raw = b"".join(
        json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        + b"\n"
        for event in events
    )
    (item / "agent-runs.jsonl").write_bytes(raw)
    return raw


def test_close_and_replay_preserve_regular_retained_evidence_file(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    helpers, mutator, _item, retained, retained_bytes, ledger_bytes = (
        retained_file_fixture(root)
    )
    retained_sha256 = hashlib.sha256(retained_bytes).hexdigest()
    instant = "2026-08-09T01:00:00Z"
    closure_bytes = helpers.closure(instant)

    archived = mutator.close_item(
        root, "retained-file-owner", closure_bytes, instant
    )

    assert retained.is_file()
    assert retained.read_bytes() == retained_bytes
    assert hashlib.sha256(retained.read_bytes()).hexdigest() == retained_sha256
    assert (archived / "agent-runs.jsonl").read_bytes() == ledger_bytes
    assert mutator.close_item(
        root, "retained-file-owner", closure_bytes, instant
    ) == archived
    assert retained.read_bytes() == retained_bytes


def test_root_inspection_classifies_plain_regular_file(tmp_path: Path) -> None:
    classifier = load_module(CLASSIFIER, f"retained_file_classifier_{id(tmp_path)}")
    retained = tmp_path / "receipt.json"
    retained.write_bytes(b"{}\n")

    inspection = classifier.inspect_root_no_follow(retained)

    assert inspection.exists
    assert inspection.is_regular_file
    assert not inspection.is_directory
    assert not inspection.is_link_or_reparse


@pytest.mark.parametrize(
    ("case", "failure_id"),
    (
        ("missing", "WI-SCRATCH-RETAINED-EVIDENCE-MISSING"),
        ("undeclared-sibling", "WI-SCRATCH-OWNERSHIP-INCOMPLETE"),
        ("file-tombstone", "WI-SCRATCH-UNSAFE-ENTRY"),
        ("delete-file", "WI-SCRATCH-UNSAFE-ENTRY"),
        ("special", "WI-SCRATCH-UNSAFE-ENTRY"),
    ),
)
def test_retained_file_invalid_states_fail_before_archive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    failure_id: str,
) -> None:
    root = tmp_path / case
    helpers, mutator, item, retained, retained_bytes, _ledger = retained_file_fixture(
        root,
        slug=f"retained-file-{case}",
    )
    if case == "missing":
        retained.unlink()
    elif case == "undeclared-sibling":
        (retained.parent / "undeclared.json").write_bytes(b"{}\n")
    elif case == "file-tombstone":
        events = ledger_events(item)
        entry = events[-1]["scratchEvidence"][0]
        tombstone = mutator._scratch_tombstone(
            retained,
            item.name,
            events[-1]["runId"],
            entry["entryId"],
        )
        retained.unlink()
        tombstone.write_bytes(retained_bytes)
    elif case == "delete-file":
        events = ledger_events(item)
        entry = events[-1]["scratchEvidence"][0]
        entry["disposition"] = "delete"
        entry["proof"] = {"kind": "git-object-set"}
        write_ledger(item, events)
    else:
        classifier = mutator._scratch_classifier_module()
        real_inspect = classifier.inspect_root_no_follow

        def inspect(path: Path):
            if Path(path) == retained:
                return classifier.RootInspection(
                    True,
                    False,
                    False,
                    (1, 2, 3, 4, 5),
                    False,
                )
            return real_inspect(path)

        monkeypatch.setattr(classifier, "inspect_root_no_follow", inspect)
        monkeypatch.setattr(mutator, "_scratch_classifier_module", lambda: classifier)
    before = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }

    with pytest.raises(mutator.LifecycleError) as caught:
        mutator.close_item(
            root,
            item.name,
            helpers.closure("2026-08-09T01:00:00Z"),
            "2026-08-09T01:00:00Z",
        )

    assert caught.value.failure_id == failure_id
    assert item.is_dir()
    assert {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    } == before


def test_retained_file_link_is_rejected_without_following(tmp_path: Path) -> None:
    root = tmp_path / "link"
    helpers, mutator, item, retained, retained_bytes, _ledger = retained_file_fixture(
        root,
        slug="retained-file-link",
    )
    outside = root / "outside-receipt.json"
    outside.write_bytes(retained_bytes)
    retained.unlink()
    try:
        retained.symlink_to(outside)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"target environment cannot create a file symlink: {exc}")

    with pytest.raises(mutator.LifecycleError) as caught:
        mutator.close_item(
            root,
            item.name,
            helpers.closure("2026-08-09T01:00:00Z"),
            "2026-08-09T01:00:00Z",
        )

    assert caught.value.failure_id == "WI-SCRATCH-UNSAFE-ENTRY"
    assert retained.is_symlink()
    assert outside.read_bytes() == retained_bytes


def test_readme_failure_rolls_back_close_and_preserves_retained_file(
    tmp_path: Path,
) -> None:
    root = tmp_path / "readme-rollback"
    helpers, mutator, item, retained, retained_bytes, ledger_bytes = (
        retained_file_fixture(root, slug="retained-file-readme-rollback")
    )

    with pytest.raises(mutator.LifecycleError) as caught:
        mutator.close_item(
            root,
            item.name,
            helpers.closure("2026-08-09T01:00:00Z"),
            "2026-08-09T01:00:00Z",
            inject_readme_failure=True,
        )

    assert caught.value.failure_id == "WI-README-STALE"
    assert item.is_dir()
    assert (item / "agent-runs.jsonl").read_bytes() == ledger_bytes
    assert retained.read_bytes() == retained_bytes
    assert not (root / "work-items" / "archive" / "2026-08" / item.name).exists()
