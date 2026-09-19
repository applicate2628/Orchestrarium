from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "mutate-work-item.py"


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def active_status(task: str) -> bytes:
    return (
        "---\n"
        "template: quick-fix\n"
        "status: active\n"
        "started: 2026-09-10T11:00:00Z\n"
        "updated: 2026-09-10T11:00:00Z\n"
        "---\n\n"
        f"- **Task**: {task}\n"
        "- **Current step**: Close the admitted item.\n"
        "- **Last result**: Implementation is complete.\n"
        "- **Next action**: Run the close oracle.\n"
    ).encode("utf-8")


def closure(instant: str) -> bytes:
    return (
        f"Closed: {instant}\n"
        "Outcome: Closed through the placeholder-context transaction.\n"
        "Evidence: focused placeholder close test\n"
        "Residual risk: None in fixture.\n"
    ).encode("utf-8")


def seed_active(module, root: Path, slug: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    candidate = root / "candidate.md"
    candidate.write_bytes(
        f"Task: {slug}\nNext action: Start.\nupdated: 2026-09-10T11:00:00Z\n".encode(
            "utf-8"
        )
    )
    module.create_candidate(root, slug, candidate.read_bytes())
    module.start_item(root, slug, active_status(slug))
    return root / "work-items" / "active" / slug


def seed_bug(root: Path, *, bug_id: str, context: str) -> Path:
    bug = root / "work-items" / "bugs" / f"{bug_id}.md"
    write(
        bug,
        (
            f"# Bug: {bug_id}\n\n"
            f"- id: {bug_id}\n"
            f"- context: {context}\n"
            "- status: open\n"
            "- severity: high\n"
        ),
    )
    return bug


def terminalize_row(bug: Path, *, context_before: str, context_after: str) -> dict:
    return {
        "id": bug.stem,
        "action": "terminalize",
        "inputSha256": hashlib.sha256(bug.read_bytes()).hexdigest(),
        "status": "fixed",
        "resolution": "The accepted implementation resolved the blocker.",
        "evidence": "The focused placeholder close test passed.",
        "contextBefore": context_before,
        "contextAfter": context_after,
    }


def preserve_row(bug: Path, *, context: str) -> dict:
    return {
        "id": bug.stem,
        "action": "preserve-current",
        "inputSha256": hashlib.sha256(bug.read_bytes()).hexdigest(),
        "status": "open",
        "reason": "The exact-context bug remains independently actionable.",
        "evidence": "The close owner explicitly preserved this current bug.",
        "contextBefore": context,
        "contextAfter": context,
    }


def write_manifest(item: Path, *, instant: str, rows: list[dict], version: int = 2) -> bytes:
    raw = (
        json.dumps(
            {
                "schemaVersion": version,
                "workItem": item.name,
                "closedAt": instant,
                "bugs": rows,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    (item / "bug-dispositions.json").write_bytes(raw)
    return raw


def tree_file_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize("placeholder", ("adjacent-finding", "standalone"))
def test_close_terminalizes_selected_placeholder_and_preserves_unselected(
    tmp_path: Path,
    placeholder: str,
) -> None:
    module = load_module(f"placeholder_close_{placeholder}_{id(tmp_path)}")
    root = tmp_path / placeholder
    slug = f"placeholder-owner-{placeholder}"
    item = seed_active(module, root, slug)
    selected = seed_bug(
        root,
        bug_id=f"2026-09-10-selected-{placeholder}",
        context=placeholder,
    )
    other_placeholder = "standalone" if placeholder == "adjacent-finding" else "adjacent-finding"
    unselected = seed_bug(
        root,
        bug_id=f"2026-09-10-unselected-{placeholder}",
        context=other_placeholder,
    )
    unselected_before = unselected.read_bytes()
    instant = "2026-09-10T11:05:00Z"
    manifest_before = write_manifest(
        item,
        instant=instant,
        rows=[
            terminalize_row(
                selected,
                context_before=placeholder,
                context_after=slug,
            )
        ],
    )
    closure_bytes = closure(instant)

    archived = module.close_item(root, slug, closure_bytes, instant)

    archived_bug = (
        root
        / "work-items"
        / "bugs"
        / "archive"
        / "2026-09"
        / selected.name
    )
    fields = module._parse_fields(archived_bug.read_text(encoding="utf-8"))
    assert fields["context"] == slug
    assert fields["status"] == "fixed"
    assert not selected.exists()
    assert unselected.read_bytes() == unselected_before
    assert (archived / "bug-dispositions.json").read_bytes() == manifest_before
    receipt = json.loads(
        (archived / "bug-dispositions-receipt.json").read_text(encoding="utf-8")
    )
    assert receipt["schemaVersion"] == 2
    assert receipt["owner"] == module.BUG_DISPOSITIONS_OWNER
    assert receipt["bugs"][0]["contextBefore"] == placeholder
    assert receipt["bugs"][0]["contextAfter"] == slug
    assert module.close_item(root, slug, closure_bytes, instant) == archived


def test_close_v2_requires_all_exact_context_bugs_and_only_selected_placeholders(
    tmp_path: Path,
) -> None:
    module = load_module(f"placeholder_close_mixed_{id(tmp_path)}")
    root = tmp_path / "mixed"
    slug = "placeholder-owner-mixed"
    item = seed_active(module, root, slug)
    exact = seed_bug(root, bug_id="2026-09-10-exact-current", context=slug)
    selected = seed_bug(
        root,
        bug_id="2026-09-10-selected-adjacent",
        context="adjacent-finding",
    )
    unselected = seed_bug(
        root,
        bug_id="2026-09-10-unselected-standalone",
        context="standalone",
    )
    exact_before = exact.read_bytes()
    unselected_before = unselected.read_bytes()
    instant = "2026-09-10T11:06:00Z"
    write_manifest(
        item,
        instant=instant,
        rows=[
            preserve_row(exact, context=slug),
            terminalize_row(
                selected,
                context_before="adjacent-finding",
                context_after=slug,
            ),
        ],
    )

    archived = module.close_item(root, slug, closure(instant), instant)

    assert exact.read_bytes() == exact_before
    assert unselected.read_bytes() == unselected_before
    assert not selected.exists()
    receipt = json.loads(
        (archived / "bug-dispositions-receipt.json").read_text(encoding="utf-8")
    )
    by_id = {row["id"]: row for row in receipt["bugs"]}
    assert by_id[exact.stem]["action"] == "preserve-current"
    assert by_id[exact.stem]["contextBefore"] == slug
    assert by_id[exact.stem]["contextAfter"] == slug
    assert by_id[selected.stem]["contextBefore"] == "adjacent-finding"
    assert by_id[selected.stem]["contextAfter"] == slug


@pytest.mark.parametrize(
    ("case", "failure_id"),
    (
        ("duplicate", "WI-BUG-DISPOSITIONS-INVALID"),
        ("duplicate-context", "WI-BUG-DISPOSITIONS-INVALID"),
        ("placeholder-preserve", "WI-BUG-DISPOSITIONS-INVALID"),
        ("context-before", "WI-BUG-DISPOSITIONS-DRIFT"),
        ("context-after", "WI-BUG-DISPOSITIONS-INVALID"),
        ("input-hash", "WI-BUG-DISPOSITIONS-DRIFT"),
        ("terminal-evidence", "WI-BUG-DISPOSITIONS-INVALID"),
    ),
)
def test_close_v2_rejects_invalid_placeholder_selection_without_mutation(
    tmp_path: Path,
    case: str,
    failure_id: str,
) -> None:
    module = load_module(f"placeholder_close_invalid_{case}_{id(tmp_path)}")
    root = tmp_path / case
    slug = f"placeholder-owner-invalid-{case}"
    item = seed_active(module, root, slug)
    bug = seed_bug(
        root,
        bug_id=f"2026-09-10-invalid-{case}",
        context="adjacent-finding",
    )
    if case == "duplicate-context":
        bug.write_bytes(bug.read_bytes() + b"- context: standalone\n")
    elif case == "terminal-evidence":
        bug.write_bytes(bug.read_bytes() + b"\nResolution: stale terminal evidence\n")
    row = terminalize_row(
        bug,
        context_before="adjacent-finding",
        context_after=slug,
    )
    rows = [row]
    if case == "duplicate":
        rows.append(dict(row))
    elif case == "placeholder-preserve":
        row = preserve_row(bug, context="adjacent-finding")
        row["contextAfter"] = slug
        rows = [row]
    elif case == "context-before":
        row["contextBefore"] = "standalone"
    elif case == "context-after":
        row["contextAfter"] = "another-owner"
    elif case == "input-hash":
        row["inputSha256"] = "0" * 64
    instant = "2026-09-10T11:07:00Z"
    write_manifest(item, instant=instant, rows=rows)
    before = tree_file_bytes(root)

    with pytest.raises(module.LifecycleError) as caught:
        module.close_item(root, slug, closure(instant), instant)

    assert caught.value.failure_id == failure_id
    assert tree_file_bytes(root) == before


def test_close_v2_rolls_back_original_placeholder_bytes_and_context(
    tmp_path: Path,
) -> None:
    module = load_module(f"placeholder_close_rollback_{id(tmp_path)}")
    root = tmp_path / "rollback"
    slug = "placeholder-owner-rollback"
    item = seed_active(module, root, slug)
    bugs = [
        seed_bug(
            root,
            bug_id=f"2026-09-10-placeholder-rollback-{index}",
            context=context,
        )
        for index, context in enumerate(("adjacent-finding", "standalone"), start=1)
    ]
    before = {bug: bug.read_bytes() for bug in bugs}
    instant = "2026-09-10T11:08:00Z"
    write_manifest(
        item,
        instant=instant,
        rows=[
            terminalize_row(
                bug,
                context_before=("adjacent-finding", "standalone")[index],
                context_after=slug,
            )
            for index, bug in enumerate(bugs)
        ],
    )

    with pytest.raises(module.LifecycleError) as caught:
        module.close_item(
            root,
            slug,
            closure(instant),
            instant,
            inject_bug_failure_after=1,
        )

    assert caught.value.failure_id == "WI-BUG-DISPOSITIONS-DRIFT"
    assert item.is_dir()
    assert all(bug.read_bytes() == before[bug] for bug in bugs)
    assert not (root / "work-items" / "bugs" / "archive").exists()


def test_close_v2_replay_rejects_context_receipt_drift(tmp_path: Path) -> None:
    module = load_module(f"placeholder_close_replay_{id(tmp_path)}")
    root = tmp_path / "replay"
    slug = "placeholder-owner-replay"
    item = seed_active(module, root, slug)
    bug = seed_bug(
        root,
        bug_id="2026-09-10-placeholder-replay",
        context="standalone",
    )
    instant = "2026-09-10T11:09:00Z"
    write_manifest(
        item,
        instant=instant,
        rows=[
            terminalize_row(
                bug,
                context_before="standalone",
                context_after=slug,
            )
        ],
    )
    closure_bytes = closure(instant)
    archived = module.close_item(root, slug, closure_bytes, instant)
    receipt_path = archived / "bug-dispositions-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["bugs"][0]["contextBefore"] = "adjacent-finding"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    with pytest.raises(module.LifecycleError) as caught:
        module.close_item(root, slug, closure_bytes, instant)

    assert caught.value.failure_id == "WI-IMMUTABLE-ARCHIVE"
    manifest_path = archived / "bug-dispositions.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["bugs"][0]["contextBefore"] = "another-owner"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    receipt["bugs"][0]["contextBefore"] = "another-owner"
    receipt["manifestSha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    with pytest.raises(module.LifecycleError) as coherent:
        module.close_item(root, slug, closure_bytes, instant)

    assert coherent.value.failure_id == "WI-IMMUTABLE-ARCHIVE"


def test_close_v1_exact_context_wire_remains_unchanged(tmp_path: Path) -> None:
    module = load_module(f"placeholder_close_v1_{id(tmp_path)}")
    root = tmp_path / "v1"
    slug = "placeholder-owner-v1"
    item = seed_active(module, root, slug)
    bug = seed_bug(root, bug_id="2026-09-10-v1-exact", context=slug)
    instant = "2026-09-10T11:10:00Z"
    row = terminalize_row(bug, context_before=slug, context_after=slug)
    row.pop("contextBefore")
    row.pop("contextAfter")
    write_manifest(item, instant=instant, rows=[row], version=1)

    archived = module.close_item(root, slug, closure(instant), instant)

    receipt = json.loads(
        (archived / "bug-dispositions-receipt.json").read_text(encoding="utf-8")
    )
    assert receipt["schemaVersion"] == 1
    assert "contextBefore" not in receipt["bugs"][0]
    assert "contextAfter" not in receipt["bugs"][0]
    archived_bug = root / "work-items" / "bugs" / "archive" / "2026-09" / bug.name
    assert module._parse_fields(archived_bug.read_text(encoding="utf-8"))["context"] == slug


def test_placeholder_schema_is_not_admitted_by_shared_archive_preflight(
    tmp_path: Path,
) -> None:
    module = load_module(f"placeholder_close_archive_control_{id(tmp_path)}")
    root = tmp_path / "archive-control"
    slug = "placeholder-owner-archive-control"
    item = seed_active(module, root, slug)
    bug = seed_bug(
        root,
        bug_id="2026-09-10-placeholder-archive-control",
        context="adjacent-finding",
    )
    instant = "2026-09-10T11:11:00Z"
    write_manifest(
        item,
        instant=instant,
        rows=[
            terminalize_row(
                bug,
                context_before="adjacent-finding",
                context_after=slug,
            )
        ],
    )

    with pytest.raises(module.LifecycleError) as caught:
        module._prepare_bug_dispositions(root, item, slug, instant)

    assert caught.value.failure_id == "WI-BUG-DISPOSITIONS-INVALID"
