import asyncio
import hashlib
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(
    os.environ.get("MUTATE_WORK_ITEM_SCRIPT", ROOT / "scripts" / "mutate-work-item.py")
)
LEDGER = ROOT / "scripts" / "agent-run-ledger.py"
STATE_VALIDATOR = ROOT / "scripts" / "validate-work-item-state.py"
FIXTURE = ROOT / "tests" / "fixtures" / "work-items-lifecycle-v1" / "five-item.json"
LIFECYCLE_SCHEMA_MARKER = "Lifecycle-schema: work-items-physical-v1"


def load_module():
    spec = importlib.util.spec_from_file_location("mutate_work_item", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def run_state_validator(work_item: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(STATE_VALIDATOR), "--work-item", str(work_item)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def run_ledger(work_item: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LEDGER), "--work-item", str(work_item), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_root_contract(root: Path, auxiliary_roots: dict[str, dict[str, str]]) -> None:
    write(
        root / "work-items" / "root-contract.json",
        json.dumps(
            {
                "schema": "work-items-root-contract",
                "version": 2,
                "auxiliaryRoots": auxiliary_roots,
            }
        )
        + "\n",
    )


def quick_status(task: str = "Complete bounded repair.") -> str:
    return f"""---
template: quick-fix
status: active
started: 2026-07-31T00:00:00Z
updated: 2026-07-31T00:00:00Z
---

- **Task**: {task}
- **Current step**: Execute the current step.
- **Last result**: Not started.
- **Next action**: Run the oracle.
"""


def staged_status(reopens: str) -> str:
    return f"""---
template: staged
status: active
started: 2026-07-31T00:00:00Z
updated: 2026-07-31T00:00:00Z
---

Task: Reopen the archived concern.
Current step: Create a successor.
Last result: Original concern was archived.
Next action: Verify successor identity.
Scope boundary: Successor only.
Owner: toolchain-engineer
Integration owner: toolchain-engineer
Evidence gate: successor test
Reopens: {reopens}
"""


def closure(instant: str) -> str:
    return f"""Closed: {instant}
Outcome: Lifecycle transition completed.
Evidence: focused unit test
Residual risk: None in fixture.
"""


def marked_status(status: str = "completed") -> str:
    return f"status: {status}\n{LIFECYCLE_SCHEMA_MARKER}\n"


def marked_closure(
    instant: str,
    *,
    evidence: str = "focused unit test",
) -> str:
    return closure(instant).replace(
        "Evidence: focused unit test",
        f"Evidence: {evidence}",
    ) + f"{LIFECYCLE_SCHEMA_MARKER}\n"


def seed_legacy_archives(root: Path) -> dict[Path, str]:
    work_items = root / "work-items"
    records = {
        work_items / "archive" / "2026-06" / "legacy-date": {
            "status.md": "template: quick-fix\nstatus: done\n",
            "closure.md": (
                "Closed: 2026-06-02\n"
                "Outcome: Date-only legacy outcome.\n"
                "Residual risk: Date-only legacy risk.\n"
            ),
        },
        work_items / "archive" / "2026-04" / "legacy-closed-on": {
            "status.md": "template: full-delivery\nstatus: closed\n",
            "closure.md": (
                "- Closed on: 2026-04-09\n"
                "- Outcome: Closed-on legacy outcome.\n"
                "- Residual risk: Closed-on legacy risk.\n"
            ),
        },
        work_items / "archive" / "2026-03" / "legacy-no-closed": {
            "status.md": "status: archived\n",
            "closure.md": (
                "Outcome: Missing-Closed legacy outcome.\n"
                "Residual risk: Missing-Closed legacy risk.\n"
            ),
        },
        work_items / "archive" / "2026-02" / "legacy-no-status": {
            "closure.md": "Outcome: Missing-status legacy outcome.\n",
        },
    }
    for item, files in records.items():
        for name, data in files.items():
            write(item / name, data)
    return {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for item, files in records.items()
        for name in files
        for path in (item / name,)
    }


def seed_active(module, root: Path, slug: str) -> None:
    source = root / "candidate.md"
    status = root / "status.md"
    write(source, f"Task: {slug}\nNext action: Start.\nupdated: 2026-07-31T00:00:00Z\n")
    write(status, quick_status(slug))
    module.create_candidate(root, slug, source.read_bytes())
    module.start_item(root, slug, status.read_bytes())


def seed_context_bug(root: Path, item_slug: str, bug_slug: str) -> Path:
    target = root / "work-items" / "bugs" / f"{bug_slug}.md"
    write(
        target,
        (
            f"# Bug: {bug_slug}\n\n"
            f"- id: {bug_slug}\n"
            f"- context: {item_slug}\n"
            "- status: open\n"
            "- severity: medium\n"
        ),
    )
    return target


def write_bug_dispositions(
    root: Path,
    item_slug: str,
    instant: str,
    rows: list[dict],
) -> Path:
    target = root / "work-items" / "active" / item_slug / "bug-dispositions.json"
    write(
        target,
        json.dumps(
            {
                "schemaVersion": 1,
                "workItem": item_slug,
                "closedAt": instant,
                "bugs": rows,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    return target


def write_empty_bug_dispositions(root: Path, item_slug: str, instant: str) -> Path:
    return write_bug_dispositions(root, item_slug, instant, [])


def test_close_requires_exact_bug_disposition_manifest(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "missing-closeout-manifest"
    seed_active(module, root, slug)
    instant = "2026-08-11T10:00:00Z"

    try:
        module.close_item(root, slug, closure(instant).encode(), instant)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-BUG-DISPOSITIONS-MISSING"
    else:
        raise AssertionError("work-item closed without bug-dispositions.json")

    assert (root / "work-items" / "active" / slug).is_dir()
    assert not (root / "work-items" / "archive" / "2026-08" / slug).exists()


def test_close_rejects_complete_invalid_bug_disposition_schema_matrix(
    tmp_path: Path,
) -> None:
    module = load_module()
    instant = "2026-08-11T10:00:30Z"

    def mutate_header(payload: dict, key: str, value) -> None:
        payload[key] = value

    def mutate_row(payload: dict, key: str, value) -> None:
        payload["bugs"][0][key] = value

    cases = (
        ("unknown-header", lambda payload: mutate_header(payload, "unexpected", True)),
        ("schema-version", lambda payload: mutate_header(payload, "schemaVersion", 2)),
        ("work-item", lambda payload: mutate_header(payload, "workItem", "another-item")),
        ("closed-at", lambda payload: mutate_header(payload, "closedAt", "2026-08-11T10:00:31Z")),
        ("bugs-type", lambda payload: mutate_header(payload, "bugs", {})),
        ("duplicate-id", lambda payload: payload["bugs"].append(dict(payload["bugs"][0]))),
        ("unsafe-id", lambda payload: mutate_row(payload, "id", "../unsafe")),
        ("unknown-row", lambda payload: mutate_row(payload, "unexpected", True)),
        ("action", lambda payload: mutate_row(payload, "action", "close-it")),
        ("digest", lambda payload: mutate_row(payload, "inputSha256", "not-a-digest")),
        ("terminal-status", lambda payload: mutate_row(payload, "status", "open")),
        ("multiline-resolution", lambda payload: mutate_row(payload, "resolution", "line one\nline two")),
        ("multiline-evidence", lambda payload: mutate_row(payload, "evidence", "line one\r\nline two")),
    )

    for suffix, mutate in cases:
        root = tmp_path / suffix
        slug = f"invalid-schema-{suffix}"
        seed_active(module, root, slug)
        bug = seed_context_bug(root, slug, f"2026-08-11-{suffix}-bug")
        before = bug.read_bytes()
        payload = {
            "schemaVersion": 1,
            "workItem": slug,
            "closedAt": instant,
            "bugs": [
                {
                    "id": bug.stem,
                    "action": "terminalize",
                    "inputSha256": hashlib.sha256(before).hexdigest(),
                    "status": "fixed",
                    "resolution": "The accepted implementation fixes this defect.",
                    "evidence": "The final regression suite passed.",
                }
            ],
        }
        mutate(payload)
        write(
            root / "work-items" / "active" / slug / "bug-dispositions.json",
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
        )

        try:
            module.close_item(root, slug, closure(instant).encode(), instant)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-BUG-DISPOSITIONS-INVALID", suffix
        else:
            raise AssertionError(f"invalid bug disposition schema passed: {suffix}")

        assert bug.read_bytes() == before, suffix
        assert (root / "work-items" / "active" / slug).is_dir(), suffix
        assert not (root / "work-items" / "archive" / "2026-08" / slug).exists(), suffix


def test_close_terminalizes_exact_context_bug_in_same_owner_transaction(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "closeout-with-bug"
    bug_slug = "2026-08-11-closeout-with-bug"
    seed_active(module, root, slug)
    bug = seed_context_bug(root, slug, bug_slug)
    instant = "2026-08-11T10:01:00Z"
    write_bug_dispositions(
        root,
        slug,
        instant,
        [
            {
                "id": bug_slug,
                "action": "terminalize",
                "inputSha256": hashlib.sha256(bug.read_bytes()).hexdigest(),
                "status": "fixed",
                "resolution": "Accepted regression suite proves the defect is fixed.",
                "evidence": "Final QA and architecture gates PASS.",
            }
        ],
    )

    archived = module.close_item(root, slug, closure(instant).encode(), instant)

    archived_bug = (
        root / "work-items" / "bugs" / "archive" / "2026-08" / f"{bug_slug}.md"
    )
    assert archived.is_dir()
    assert archived_bug.is_file()
    fields = module._parse_fields(archived_bug.read_text(encoding="utf-8"))
    assert fields["status"] == "fixed"
    assert fields["terminal-at"] == instant
    assert (archived / "bug-dispositions-receipt.json").is_file()
    assert not bug.exists()


def test_close_rejects_missing_and_extra_context_bug_dispositions(
    tmp_path: Path,
) -> None:
    module = load_module()
    instant = "2026-08-11T10:02:00Z"
    for suffix, rows in (("missing", []), ("extra", None)):
        root = tmp_path / suffix
        slug = f"exact-set-{suffix}"
        seed_active(module, root, slug)
        linked = seed_context_bug(root, slug, f"2026-08-11-{suffix}-linked")
        if rows is None:
            rows = [
                {
                    "id": f"2026-08-11-{suffix}-linked",
                    "action": "preserve-current",
                    "inputSha256": hashlib.sha256(linked.read_bytes()).hexdigest(),
                    "status": "open",
                    "reason": "The defect remains independently actionable.",
                    "evidence": "The close review explicitly preserved this bug.",
                },
                {
                    "id": f"2026-08-11-{suffix}-not-linked",
                    "action": "preserve-current",
                    "inputSha256": "0" * 64,
                    "status": "open",
                    "reason": "This row must be rejected as unrelated.",
                    "evidence": "The exact context set excludes this identity.",
                },
            ]
        write_bug_dispositions(root, slug, instant, rows)

        try:
            module.close_item(root, slug, closure(instant).encode(), instant)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-BUG-DISPOSITIONS-INCOMPLETE", suffix
        else:
            raise AssertionError(f"{suffix} bug disposition set was accepted")

        assert (root / "work-items" / "active" / slug).is_dir()
        assert linked.is_file()


def test_close_uses_exact_parsed_context_not_substring_or_prose(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "exact-context-owner"
    seed_active(module, root, slug)
    near = seed_context_bug(root, f"{slug}-suffix", "2026-08-11-near-context")
    near.write_bytes(
        near.read_bytes()
        + f"\nThis prose mentions {slug} but does not change context ownership.\n".encode()
    )
    before = near.read_bytes()
    instant = "2026-08-11T10:02:30Z"
    write_empty_bug_dispositions(root, slug, instant)

    module.close_item(root, slug, closure(instant).encode(), instant)

    assert near.read_bytes() == before
    assert not (root / "work-items" / "bugs" / "archive").exists()


def test_close_preserves_declared_current_bug_and_unrelated_bug_bytes(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "preserve-current-bug"
    seed_active(module, root, slug)
    linked = seed_context_bug(root, slug, "2026-08-11-preserved-linked")
    unrelated = seed_context_bug(root, "another-item", "2026-08-11-unrelated")
    linked_before = linked.read_bytes()
    unrelated_before = unrelated.read_bytes()
    instant = "2026-08-11T10:03:00Z"
    write_bug_dispositions(
        root,
        slug,
        instant,
        [
            {
                "id": linked.stem,
                "action": "preserve-current",
                "inputSha256": hashlib.sha256(linked_before).hexdigest(),
                "status": "open",
                "reason": "The remaining defect has a separate accepted owner.",
                "evidence": "The close review recorded the residual explicitly.",
            }
        ],
    )

    archived = module.close_item(root, slug, closure(instant).encode(), instant)

    assert linked.read_bytes() == linked_before
    assert unrelated.read_bytes() == unrelated_before
    receipt = json.loads(
        (archived / "bug-dispositions-receipt.json").read_text(encoding="utf-8")
    )
    assert receipt["bugs"][0]["action"] == "preserve-current"
    assert receipt["bugs"][0]["target"] is None
    module.audit_categories(root)


def test_close_rejects_context_bug_hash_drift_without_mutation(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "bug-hash-drift"
    seed_active(module, root, slug)
    bug = seed_context_bug(root, slug, "2026-08-11-hash-drift")
    before = bug.read_bytes()
    instant = "2026-08-11T10:04:00Z"
    write_bug_dispositions(
        root,
        slug,
        instant,
        [
            {
                "id": bug.stem,
                "action": "terminalize",
                "inputSha256": "0" * 64,
                "status": "fixed",
                "resolution": "This stale declaration must not be applied.",
                "evidence": "The input digest deliberately differs.",
            }
        ],
    )

    try:
        module.close_item(root, slug, closure(instant).encode(), instant)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-BUG-DISPOSITIONS-DRIFT"
    else:
        raise AssertionError("stale bug digest was accepted")

    assert bug.read_bytes() == before
    assert (root / "work-items" / "active" / slug).is_dir()


def test_close_rejects_non_utf8_current_bug_with_typed_failure(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "invalid-current-bug"
    seed_active(module, root, slug)
    invalid = root / "work-items" / "bugs" / "2026-08-11-invalid-utf8.md"
    invalid.parent.mkdir(parents=True, exist_ok=True)
    invalid.write_bytes(b"context: " + slug.encode() + b"\nstatus: open\n\xff")
    instant = "2026-08-11T10:04:30Z"
    write_empty_bug_dispositions(root, slug, instant)

    try:
        module.close_item(root, slug, closure(instant).encode(), instant)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-BUG-DISPOSITIONS-INVALID"
    else:
        raise AssertionError("non-UTF-8 current bug escaped typed close refusal")

    assert invalid.read_bytes().endswith(b"\xff")
    assert (root / "work-items" / "active" / slug).is_dir()


def test_terminalized_bug_preserves_crlf_line_endings(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "crlf-terminal-bug"
    seed_active(module, root, slug)
    bug = seed_context_bug(root, slug, "2026-08-11-crlf-terminal-bug")
    bug.write_bytes(bug.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    instant = "2026-08-11T10:04:45Z"
    write_bug_dispositions(
        root,
        slug,
        instant,
        [
            {
                "id": bug.stem,
                "action": "terminalize",
                "inputSha256": hashlib.sha256(bug.read_bytes()).hexdigest(),
                "status": "fixed",
                "resolution": "The defect is fixed by the accepted implementation.",
                "evidence": "The final regression suite passed.",
            }
        ],
    )

    module.close_item(root, slug, closure(instant).encode(), instant)

    archived_bug = (
        root / "work-items" / "bugs" / "archive" / "2026-08" / f"{bug.stem}.md"
    ).read_bytes()
    assert b"\r\n" in archived_bug
    assert b"\n" not in archived_bug.replace(b"\r\n", b"")


def test_close_rolls_back_bug_bytes_when_bug_archive_move_fails(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "bug-move-rollback"
    seed_active(module, root, slug)
    bug = seed_context_bug(root, slug, "2026-08-11-bug-move-rollback")
    before = bug.read_bytes()
    instant = "2026-08-11T10:05:00Z"
    write_bug_dispositions(
        root,
        slug,
        instant,
        [
            {
                "id": bug.stem,
                "action": "terminalize",
                "inputSha256": hashlib.sha256(before).hexdigest(),
                "status": "fixed",
                "resolution": "The defect is fixed by the accepted implementation.",
                "evidence": "The final regression suite passed.",
            }
        ],
    )
    original_replace = module.os.replace

    def fail_bug_move(source, target):
        if Path(source) == bug:
            raise OSError("injected bug archive move failure")
        return original_replace(source, target)

    module.os.replace = fail_bug_move
    try:
        try:
            module.close_item(root, slug, closure(instant).encode(), instant)
        except OSError as exc:
            assert "injected bug archive move failure" in str(exc)
        else:
            raise AssertionError("bug archive move failure returned success")
    finally:
        module.os.replace = original_replace

    assert bug.read_bytes() == before
    assert (root / "work-items" / "active" / slug).is_dir()
    assert not (root / "work-items" / "archive" / "2026-08" / slug).exists()


def test_close_rolls_back_all_context_bugs_after_partial_disposition(
    tmp_path: Path,
) -> None:
    module = load_module()
    for fail_after in (1, 2):
        root = tmp_path / f"repo-{fail_after}"
        slug = f"partial-bug-rollback-{fail_after}"
        seed_active(module, root, slug)
        bugs = [
            seed_context_bug(
                root, slug, f"2026-08-11-partial-{fail_after}-bug-{index}"
            )
            for index in (1, 2)
        ]
        before = {bug: bug.read_bytes() for bug in bugs}
        readme_before = (root / "work-items" / "README.md").read_bytes()
        instant = f"2026-08-11T10:06:0{fail_after}Z"
        write_bug_dispositions(
            root,
            slug,
            instant,
            [
                {
                    "id": bug.stem,
                    "action": "terminalize",
                    "inputSha256": hashlib.sha256(before[bug]).hexdigest(),
                    "status": "fixed",
                    "resolution": "The defect is fixed by the accepted implementation.",
                    "evidence": "The final regression suite passed.",
                }
                for bug in bugs
            ],
        )

        try:
            module.close_item(
                root,
                slug,
                closure(instant).encode(),
                instant,
                inject_bug_failure_after=fail_after,
            )
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-BUG-DISPOSITIONS-DRIFT", fail_after
        else:
            raise AssertionError(
                f"partial bug disposition failure {fail_after} returned success"
            )

        assert (root / "work-items" / "active" / slug).is_dir()
        assert all(bug.read_bytes() == before[bug] for bug in bugs)
        assert (root / "work-items" / "README.md").read_bytes() == readme_before
        assert not (root / "work-items" / "bugs" / "archive").exists()


def test_close_replay_verifies_bug_receipt_and_archived_bug_bytes(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "verified-close-replay"
    seed_active(module, root, slug)
    bug = seed_context_bug(root, slug, "2026-08-11-verified-replay")
    instant = "2026-08-11T10:07:00Z"
    write_bug_dispositions(
        root,
        slug,
        instant,
        [
            {
                "id": bug.stem,
                "action": "terminalize",
                "inputSha256": hashlib.sha256(bug.read_bytes()).hexdigest(),
                "status": "fixed",
                "resolution": "The defect is fixed by the accepted implementation.",
                "evidence": "The final regression suite passed.",
            }
        ],
    )
    closure_bytes = closure(instant).encode()
    archived = module.close_item(root, slug, closure_bytes, instant)
    assert module.close_item(root, slug, closure_bytes, instant) == archived
    archived_bug = (
        root / "work-items" / "bugs" / "archive" / "2026-08" / f"{bug.stem}.md"
    )
    archived_bug.write_bytes(archived_bug.read_bytes() + b"tampered\n")

    try:
        module.close_item(root, slug, closure_bytes, instant)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-IMMUTABLE-ARCHIVE"
    else:
        raise AssertionError("tampered archived bug passed replay verification")


def test_close_replay_rejects_deterministic_receipt_binding_drift(
    tmp_path: Path,
) -> None:
    module = load_module()
    mutations = {
        "source": "bugs/2026-08-11-wrong-source.md",
        "target": "bugs/archive/2026-08/2026-08-11-wrong-target.md",
        "statusBefore": "fixed",
    }
    for field, replacement in mutations.items():
        root = tmp_path / field
        slug = f"receipt-binding-{field.casefold()}"
        seed_active(module, root, slug)
        bug = seed_context_bug(root, slug, f"2026-08-11-receipt-{field.casefold()}")
        instant = "2026-08-11T10:07:30Z"
        write_bug_dispositions(
            root,
            slug,
            instant,
            [
                {
                    "id": bug.stem,
                    "action": "terminalize",
                    "inputSha256": hashlib.sha256(bug.read_bytes()).hexdigest(),
                    "status": "fixed",
                    "resolution": "The defect is fixed by the accepted implementation.",
                    "evidence": "The final regression suite passed.",
                }
            ],
        )
        closure_bytes = closure(instant).encode()
        archived = module.close_item(root, slug, closure_bytes, instant)
        receipt_path = archived / "bug-dispositions-receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["bugs"][0][field] = replacement
        receipt_path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        try:
            module.close_item(root, slug, closure_bytes, instant)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-IMMUTABLE-ARCHIVE", field
        else:
            raise AssertionError(f"tampered receipt {field} passed replay")


def test_close_replay_accepts_historical_archive_without_bug_manifest(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "historical-close-replay"
    instant = "2026-08-11T10:08:00Z"
    archived = root / "work-items" / "archive" / "2026-08" / slug
    write(archived / "status.md", marked_status())
    (archived / "closure.md").write_bytes(
        module._stamp_schema_marker(closure(instant).encode(), "closure.md")
    )
    module.refresh_readme(root)

    assert module.close_item(root, slug, closure(instant).encode(), instant) == archived
    assert not (archived / "bug-dispositions.json").exists()
    assert not (archived / "bug-dispositions-receipt.json").exists()


def test_category_audit_rejects_unapplied_active_bug_dispositions(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "pending-close-reconciliation"
    seed_active(module, root, slug)
    write_empty_bug_dispositions(root, slug, "2026-08-11T10:09:00Z")

    try:
        module.audit_categories(root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-BUG-DISPOSITIONS-PENDING"
    else:
        raise AssertionError("unapplied active bug disposition passed category audit")


def test_start_staged_publishes_valid_settled_admission_ledger(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "staged-ledger-birth"
    candidate = b"Task: publish a valid staged admission.\n"
    status = staged_status("2026-07-01-archived-concern").encode("utf-8")
    module.create_candidate(root, slug, candidate)

    target = module.start_item(root, slug, status)

    assert (target / "admission.md").read_bytes() == candidate
    assert (target / "status.md").read_bytes() == status
    lines = (target / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {
        "schemaVersion": 2,
        "runId": f"{slug}-lifecycle-start",
        "workItem": slug,
        "role": "lead",
        "executionRole": "main",
        "status": "completed",
        "gate": "none",
        "scope": ["candidate -> active lifecycle admission"],
        "startedAt": "2026-07-31T00:00:00Z",
        "updatedAt": "2026-07-31T00:00:00Z",
        "eventKind": "standalone",
    }
    result = run_state_validator(target)
    assert result.returncode == 0, result.stdout


def test_start_staged_cli_publishes_valid_admission_ledger(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    slug = "staged-ledger-cli"
    candidate = root / "candidate.md"
    status = root / "status.md"
    write(candidate, "Task: publish staged admission through the CLI.\n")
    write(status, staged_status("2026-07-01-archived-concern"))

    created = run_cli(
        "candidate", "--root", str(root), "--slug", slug, "--file", str(candidate)
    )
    started = run_cli(
        "start", "--root", str(root), "--slug", slug, "--status-file", str(status)
    )

    assert created.returncode == 0, created.stdout
    assert started.returncode == 0, started.stdout
    target = root / "work-items" / "active" / slug
    event = json.loads((target / "agent-runs.jsonl").read_text(encoding="utf-8"))
    assert event["runId"] == f"{slug}-lifecycle-start"
    result = run_state_validator(target)
    assert result.returncode == 0, result.stdout


def test_staged_start_loader_failures_use_stable_id_and_preserve_candidate(tmp_path: Path) -> None:
    cases = (
        ("construction-import", "construct", ImportError("injected construction failure")),
        ("execution-import", "execute", ImportError("injected import failure")),
        ("execution-syntax", "execute", SyntaxError("injected syntax failure")),
        ("execution-os", "execute", OSError("injected execution failure")),
    )

    for name, phase, injected in cases:
        module = load_module()
        root = tmp_path / name
        slug = f"staged-loader-{name}"
        candidate = f"Task: preserve {name} candidate bytes.\n".encode("utf-8")
        status_path = root / "status.md"
        write(status_path, staged_status("2026-07-01-archived-concern"))
        module.create_candidate(root, slug, candidate)
        backlog = root / "work-items" / "backlog" / f"{slug}.md"
        candidate_sha256 = hashlib.sha256(backlog.read_bytes()).hexdigest()
        original_from_spec = module.importlib.util.spec_from_file_location
        original_module_from_spec = module.importlib.util.module_from_spec

        class FailingLoader:
            def create_module(self, _spec):
                return None

            def exec_module(self, _loaded_module) -> None:
                raise injected

        def injected_spec(name_arg, path_arg):
            spec = original_from_spec(name_arg, path_arg)
            if name_arg == "agent_run_ledger":
                assert spec is not None
                spec.loader = FailingLoader()
            return spec

        def injected_module_from_spec(spec):
            if phase == "construct" and spec.name == "agent_run_ledger":
                raise injected
            return original_module_from_spec(spec)

        module.importlib.util.spec_from_file_location = injected_spec
        module.importlib.util.module_from_spec = injected_module_from_spec
        try:
            try:
                module._agent_run_ledger_module()
            except module.LifecycleError as exc:
                assert exc.failure_id == "WI-LEDGER-BOOTSTRAP-INVALID"
                assert exc.__cause__ is injected
            else:
                raise AssertionError(f"{name} escaped the typed ledger boundary")

            output = io.StringIO()
            with redirect_stdout(output):
                result = module.main(
                    [
                        "start",
                        "--root",
                        str(root),
                        "--slug",
                        slug,
                        "--status-file",
                        str(status_path),
                    ]
                )
        finally:
            module.importlib.util.spec_from_file_location = original_from_spec
            module.importlib.util.module_from_spec = original_module_from_spec

        assert result == 1, name
        assert "WI-LEDGER-BOOTSTRAP-INVALID" in output.getvalue(), name
        assert "Traceback" not in output.getvalue(), name
        assert hashlib.sha256(backlog.read_bytes()).hexdigest() == candidate_sha256, name
        active = root / "work-items" / "active"
        assert not (active / slug).exists(), name
        assert not list(active.glob(f".{slug}.*")) if active.exists() else True


def test_agent_run_ledger_loader_does_not_swallow_base_exception(tmp_path: Path) -> None:
    module = load_module()
    original_from_spec = module.importlib.util.spec_from_file_location
    interruption = KeyboardInterrupt("injected cancellation signal")

    class InterruptingLoader:
        def create_module(self, _spec):
            return None

        def exec_module(self, _loaded_module) -> None:
            raise interruption

    def injected_spec(name_arg, path_arg):
        spec = original_from_spec(name_arg, path_arg)
        if name_arg == "agent_run_ledger":
            assert spec is not None
            spec.loader = InterruptingLoader()
        return spec

    module.importlib.util.spec_from_file_location = injected_spec
    try:
        try:
            module._agent_run_ledger_module()
        except KeyboardInterrupt as exc:
            assert exc is interruption
        else:
            raise AssertionError("BaseException cancellation signal was swallowed")
    finally:
        module.importlib.util.spec_from_file_location = original_from_spec


def test_staged_start_ledger_failure_restores_candidate(tmp_path: Path) -> None:
    cases = ("build", "serialize", "write", "temporary-validation", "final-replace")

    for phase in cases:
        module = load_module()
        root = tmp_path / phase
        slug = f"staged-ledger-{phase}"
        candidate = f"Task: preserve {phase} candidate bytes.\n".encode("utf-8")
        status = staged_status("2026-07-01-archived-concern").encode("utf-8")
        module.create_candidate(root, slug, candidate)
        backlog = root / "work-items" / "backlog" / f"{slug}.md"
        candidate_sha256 = hashlib.sha256(backlog.read_bytes()).hexdigest()
        original_ledger_module = module._agent_run_ledger_module
        original_atomic_write = module._atomic_write
        original_validator_module = module._validator_module
        original_replace = module.os.replace
        real_ledger = original_ledger_module()

        class InjectedLedger:
            def build_event(self, args):
                if phase == "build":
                    raise ValueError("injected event build failure")
                return real_ledger.build_event(args)

            def serialize_event(self, event):
                if phase == "serialize":
                    raise ValueError("injected event serialization failure")
                return real_ledger.serialize_event(event)

        class RejectingValidator:
            def validate_work_item(self, _item):
                return ["injected temporary validation failure"]

        def injected_atomic_write(path: Path, data: bytes) -> None:
            if phase == "write" and path.name == "agent-runs.jsonl":
                raise OSError("injected ledger write failure")
            original_atomic_write(path, data)

        def injected_replace(source, target) -> None:
            if phase == "final-replace" and Path(source).is_dir():
                raise OSError("injected final replace failure")
            original_replace(source, target)

        module._agent_run_ledger_module = lambda: InjectedLedger()
        module._atomic_write = injected_atomic_write
        if phase == "temporary-validation":
            module._validator_module = lambda: RejectingValidator()
        module.os.replace = injected_replace
        try:
            try:
                module.start_item(root, slug, status)
            except (module.LifecycleError, OSError):
                pass
            else:
                raise AssertionError(f"{phase} failure did not abort staged start")
        finally:
            module._agent_run_ledger_module = original_ledger_module
            module._atomic_write = original_atomic_write
            module._validator_module = original_validator_module
            module.os.replace = original_replace

        assert hashlib.sha256(backlog.read_bytes()).hexdigest() == candidate_sha256, phase
        active = root / "work-items" / "active"
        assert not (active / slug).exists(), phase
        assert not list(active.glob(f".{slug}.*")), phase


def test_staged_bootstrap_event_allows_close_after_terminal_work(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "staged-bootstrap-close"
    candidate = b"Task: exercise staged admission through archive.\n"
    status = staged_status("2026-07-01-archived-concern").encode("utf-8")
    module.create_candidate(root, slug, candidate)
    active = module.start_item(root, slug, status)

    launch_id = "staged-real-launch-001"
    launched = run_ledger(
        active,
        "append",
        "--run-id",
        launch_id,
        "--role",
        "platform-engineer",
        "--execution-role",
        "internal",
        "--status",
        "running",
        "--gate",
        "none",
        "--scope",
        "staged lifecycle implementation",
        "--event-kind",
        "launch",
        "--started-at",
        "2026-07-31T00:01:00Z",
        "--updated-at",
        "2026-07-31T00:01:00Z",
    )
    assert launched.returncode == 0, launched.stdout
    open_validation = run_state_validator(active)
    assert open_validation.returncode == 1
    assert "unsettled launch" in open_validation.stdout

    terminal = run_ledger(
        active,
        "append",
        "--run-id",
        "staged-real-terminal-001",
        "--role",
        "platform-engineer",
        "--execution-role",
        "internal",
        "--status",
        "completed",
        "--gate",
        "none",
        "--scope",
        "staged lifecycle implementation",
        "--event-kind",
        "terminal",
        "--launch-run-id",
        launch_id,
        "--started-at",
        "2026-07-31T00:01:00Z",
        "--updated-at",
        "2026-07-31T00:02:00Z",
    )
    assert terminal.returncode == 0, terminal.stdout
    settled_validation = run_state_validator(active)
    assert settled_validation.returncode == 0, settled_validation.stdout

    instant = "2026-07-31T00:03:00Z"
    write_empty_bug_dispositions(root, slug, instant)
    archived = module.close_item(root, slug, closure(instant).encode(), instant)

    assert archived == root / "work-items" / "archive" / "2026-07" / slug
    assert run_state_validator(archived).returncode == 0
    rollup = run_ledger(archived, "rollup")
    assert rollup.returncode == 0, rollup.stdout
    assert "total runs: 3" in rollup.stdout
    assert "lead=1" in rollup.stdout
    assert "platform-engineer=2" in rollup.stdout


def test_staged_start_readme_failure_leaves_valid_canonical_item(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "staged-ledger-readme"
    candidate = b"Task: preserve canonical start on README failure.\n"
    status = staged_status("2026-07-01-archived-concern").encode("utf-8")
    module.create_candidate(root, slug, candidate)

    try:
        module.start_item(root, slug, status, inject_readme_failure=True)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-README-STALE"
    else:
        raise AssertionError("injected README failure did not abort the derived-view refresh")

    target = root / "work-items" / "active" / slug
    result = run_state_validator(target)
    assert result.returncode == 0, result.stdout


def test_start_quick_fix_preserves_ledger_free_contract(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "quick-fix-ledger-free"
    candidate = b"Task: preserve the quick-fix exception.\n"
    status = quick_status(slug).encode("utf-8")
    module.create_candidate(root, slug, candidate)

    target = module.start_item(root, slug, status)

    assert not (target / "agent-runs.jsonl").exists()
    result = run_state_validator(target)
    assert result.returncode == 0, result.stdout


def test_five_item_readme_trial(tmp_path: Path) -> None:
    trial_root = tmp_path / "trial"
    result = run_cli("trial", "--root", str(trial_root), "--fixture", str(FIXTURE))

    assert result.returncode == 0, result.stdout
    assert "TRIAL: PASS" in result.stdout
    assert "items=5" in result.stdout
    assert (
        "sections=Current focus|Next actions|Blockers|Roadmap and milestones|Recently completed"
        in result.stdout
    )
    hashes = [
        line.split("=", 1)[1]
        for line in result.stdout.splitlines()
        if line.startswith("readme_sha256_")
    ]
    assert len(hashes) == 2
    assert hashes[0] == hashes[1]
    assert all(len(value) == 64 for value in hashes)
    text = (trial_root / "work-items" / "README.md").read_text(encoding="utf-8")
    assert sum(line.startswith("- [") for line in text.splitlines()) == 5
    assert all(
        line.startswith(("- [ ]", "- [x]"))
        for line in text.splitlines()
        if line.startswith("- [")
    )
    assert "[roadmap](" in text and "[epic](" in text and "[work item](" in text


def test_trial_repeat_success_preserves_hashes(tmp_path: Path) -> None:
    trial_root = tmp_path / "repeatable-trial"
    first = run_cli("trial", "--root", str(trial_root), "--fixture", str(FIXTURE))
    readme_before = (trial_root / "work-items" / "README.md").read_bytes()
    receipt_before = (
        trial_root / ".work-items-lifecycle-v1-trial.json"
    ).read_bytes()

    second = run_cli("trial", "--root", str(trial_root), "--fixture", str(FIXTURE))

    assert first.returncode == 0, first.stdout
    assert second.returncode == 0, second.stdout
    first_hashes = [
        line.split("=", 1)[1]
        for line in first.stdout.splitlines()
        if line.startswith("readme_sha256_")
    ]
    second_hashes = [
        line.split("=", 1)[1]
        for line in second.stdout.splitlines()
        if line.startswith("readme_sha256_")
    ]
    assert first_hashes == second_hashes
    assert len(first_hashes) == 2
    assert (trial_root / "work-items" / "README.md").read_bytes() == readme_before
    assert (
        trial_root / ".work-items-lifecycle-v1-trial.json"
    ).read_bytes() == receipt_before


def test_trial_foreign_root_is_preserved_and_fails_closed(tmp_path: Path) -> None:
    trial_root = tmp_path / "foreign-root"
    foreign = trial_root / "user-content.txt"
    write(foreign, "preserve this user content\n")
    before = foreign.read_bytes()

    result = run_cli("trial", "--root", str(trial_root), "--fixture", str(FIXTURE))

    assert result.returncode == 1
    assert "WI-TRIAL-NOT-OWNED" in result.stdout
    assert foreign.read_bytes() == before
    assert sorted(path.name for path in trial_root.iterdir()) == [
        ".scratch",
        "user-content.txt",
    ]
    assert (
        trial_root / ".scratch" / "work-items-lifecycle-owner.lock"
    ).read_bytes() == b"work-items-lifecycle-owner-v1\n"


def test_utc_same_instant_boundary_replay(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "utc-boundary"
    seed_active(module, root, slug)
    instant = "2026-08-01T00:00:00Z"
    closure_bytes = closure(instant).encode()

    write_empty_bug_dispositions(root, slug, instant)
    first = module.close_item(root, slug, closure_bytes, instant)
    first_hash = hashlib.sha256((first / "closure.md").read_bytes()).hexdigest()
    original_tz = os.environ.get("TZ")
    try:
        os.environ["TZ"] = "Pacific/Honolulu"
        replay_a = module.close_item(root, slug, closure_bytes, instant)
        os.environ["TZ"] = "Pacific/Kiritimati"
        replay_b = module.close_item(root, slug, closure_bytes, instant)
    finally:
        if original_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original_tz

    expected = root / "work-items" / "archive" / "2026-08" / slug
    assert first == expected
    assert replay_a == expected and replay_b == expected
    assert hashlib.sha256((expected / "closure.md").read_bytes()).hexdigest() == first_hash
    assert not (root / "work-items" / "active" / slug).exists()
    assert len(list((root / "work-items" / "archive").glob(f"*/*{slug}"))) == 1


def test_terminalization_stamps_schema_pair_once_and_replay_is_idempotent(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "schema-stamped"
    seed_active(module, root, slug)
    active_status = root / "work-items" / "active" / slug / "status.md"
    status_before = active_status.read_bytes()
    assert status_before == (root / "status.md").read_bytes()
    module._validate_active_status_bytes(status_before)
    assert LIFECYCLE_SCHEMA_MARKER.encode() not in status_before
    instant = "2026-08-01T00:00:00Z"
    closure_input = closure(instant).encode()

    write_empty_bug_dispositions(root, slug, instant)
    archived = module.close_item(root, slug, closure_input, instant)
    status_after = (archived / "status.md").read_bytes()
    closure_after = (archived / "closure.md").read_bytes()
    hashes_after = {
        "status": hashlib.sha256(status_after).hexdigest(),
        "closure": hashlib.sha256(closure_after).hexdigest(),
    }

    assert status_after.count(LIFECYCLE_SCHEMA_MARKER.encode()) == 1
    assert closure_after.count(LIFECYCLE_SCHEMA_MARKER.encode()) == 1
    assert closure_input == closure(instant).encode()
    assert module.close_item(root, slug, closure_input, instant) == archived
    assert hashlib.sha256((archived / "status.md").read_bytes()).hexdigest() == hashes_after[
        "status"
    ]
    assert hashlib.sha256((archived / "closure.md").read_bytes()).hexdigest() == hashes_after[
        "closure"
    ]
    assert (archived / "status.md").read_bytes().count(
        LIFECYCLE_SCHEMA_MARKER.encode()
    ) == 1
    assert (archived / "closure.md").read_bytes().count(
        LIFECYCLE_SCHEMA_MARKER.encode()
    ) == 1


def test_legacy_archive_projection_is_informational_and_byte_preserving(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    before = seed_legacy_archives(root)

    module.refresh_readme(root, allow_marker_bootstrap=True)

    after = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in before
    }
    assert after == before
    entries = {
        entry.logical_reference: entry
        for entry in module.collect_readme_entries(root)
    }
    assert set(entries) == {
        "work-item:legacy-date",
        "work-item:legacy-closed-on",
        "work-item:legacy-no-closed",
        "work-item:legacy-no-status",
    }
    assert {
        entry.classification
        for entry in entries.values()
    } == {"WI-LEGACY-READ-COMPAT"}
    assert entries["work-item:legacy-date"].label == "Date-only legacy outcome."
    assert entries["work-item:legacy-closed-on"].label == "Closed-on legacy outcome."
    assert entries["work-item:legacy-no-closed"].label == "Missing-Closed legacy outcome."
    assert entries["work-item:legacy-no-status"].label == "Missing-status legacy outcome."
    readme = (root / "work-items" / "README.md").read_text(encoding="utf-8")
    assert readme.count("WI-LEGACY-READ-COMPAT") == 4
    assert "archive/2026-06/legacy-date/closure.md" in readme
    assert "archive/2026-04/legacy-closed-on/closure.md" in readme


def test_archive_schema_marker_matrix_fails_closed(tmp_path: Path) -> None:
    module = load_module()
    instant = "2026-08-01T00:00:00Z"
    canonical_status = marked_status()
    canonical_closure = marked_closure(instant)
    cases = {
        "status-only": (canonical_status, closure(instant)),
        "closure-only": ("status: completed\n", canonical_closure),
        "duplicate-status": (
            canonical_status + f"{LIFECYCLE_SCHEMA_MARKER}\n",
            canonical_closure,
        ),
        "duplicate-closure": (
            canonical_status,
            canonical_closure + f"{LIFECYCLE_SCHEMA_MARKER}\n",
        ),
        "empty-status": (
            "status: completed\nLifecycle-schema:\n",
            canonical_closure,
        ),
        "unknown-status": (
            "status: completed\nLifecycle-schema: work-items-physical-v2\n",
            canonical_closure,
        ),
        "wrong-case-status": (
            "status: completed\nLifecycle-schema: Work-Items-Physical-V1\n",
            canonical_closure,
        ),
        "wrong-case-key": (
            "status: completed\nlifecycle-schema: work-items-physical-v1\n",
            canonical_closure,
        ),
        "mismatch": (
            "status: completed\nLifecycle-schema: work-items-physical-v2\n",
            "Closed: 2026-08-01T00:00:00Z\n"
            "Outcome: mismatch\nEvidence: mismatch\nResidual risk: mismatch\n"
            "Lifecycle-schema: work-items-physical-v3\n",
        ),
    }

    for slug, (status, closure_text) in cases.items():
        root = tmp_path / slug
        item = root / "work-items" / "archive" / "2026-08" / slug
        write(item / "status.md", status)
        write(item / "closure.md", closure_text)
        try:
            module.collect_readme_entries(root)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-SCHEMA-INVALID", slug
        else:
            raise AssertionError(f"malformed schema pair downgraded to legacy: {slug}")


def test_v1_archive_pair_preserves_strict_evidence_status_and_month(
    tmp_path: Path,
) -> None:
    module = load_module()
    instant = "2026-08-01T00:00:00Z"

    valid_root = tmp_path / "valid"
    valid_item = valid_root / "work-items" / "archive" / "2026-08" / "valid-v1"
    write(valid_item / "status.md", marked_status())
    write(valid_item / "closure.md", marked_closure(instant))
    entries = module.collect_readme_entries(valid_root)
    assert len(entries) == 1
    assert entries[0].classification is None

    cases = {
        "wrong-month": (
            "2026-07",
            marked_status(),
            marked_closure(instant),
            "WI-CATEGORY-ARCHIVE-MONTH-MISMATCH",
        ),
        "date-only": (
            "2026-08",
            marked_status(),
            marked_closure("2026-08-01"),
            "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
        ),
        "missing-evidence": (
            "2026-08",
            marked_status(),
            marked_closure(instant, evidence="").replace("Evidence: \n", ""),
            "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
        ),
        "current-status": (
            "2026-08",
            marked_status("active"),
            marked_closure(instant),
            "WI-CATEGORY-CURRENT-IN-ARCHIVE",
        ),
    }
    for slug, (month, status, closure_text, failure_id) in cases.items():
        root = tmp_path / slug
        item = root / "work-items" / "archive" / month / slug
        write(item / "status.md", status)
        write(item / "closure.md", closure_text)
        try:
            module.collect_readme_entries(root)
        except module.LifecycleError as exc:
            assert exc.failure_id == failure_id, slug
        else:
            raise AssertionError(f"invalid V1 archive pair passed: {slug}")


def test_close_readme_failure_rolls_back_canonical_and_readme(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "stale-readme"
    seed_active(module, root, slug)
    old_readme = (root / "work-items" / "README.md").read_bytes()
    instant = "2026-07-31T10:00:00Z"
    write_empty_bug_dispositions(root, slug, instant)

    try:
        module.close_item(
            root,
            slug,
            closure(instant).encode(),
            instant,
            inject_readme_failure=True,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-README-STALE"
    else:
        raise AssertionError("injected README failure returned success")

    archived = root / "work-items" / "archive" / "2026-07" / slug
    active = root / "work-items" / "active" / slug
    assert active.is_dir()
    assert not archived.exists()
    validator = module._validator_module()
    assert validator.validate_work_item(active) == []
    assert (root / "work-items" / "README.md").read_bytes() == old_readme
    module.check_readme(root)


def test_category_location_matrix_guard(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    write(root / "work-items" / "decisions" / "choice.md", "status: proposed\n")
    current = module.resolve_category(root, "decision:choice")
    assert current.name == "choice.md"
    archived = root / "work-items" / "decisions" / "archive" / "2026-07" / "choice.md"
    archived.parent.mkdir(parents=True)
    shutil.move(str(current), str(archived))
    assert module.resolve_category(root, "decision:choice") == archived.resolve()
    write(root / "work-items" / "decisions" / "choice.md", "status: proposed\n")
    try:
        module.resolve_category(root, "decision:choice")
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-DUAL-LOCATION"
    else:
        raise AssertionError("dual location was selected silently")


def test_logical_link_relocation_and_legacy_inventory_guard(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "relocatable"
    seed_active(module, root, slug)
    assert module.resolve_category(root, f"work-item:{slug}").parent.name == "active"
    instant = "2026-07-31T11:00:00Z"
    write_empty_bug_dispositions(root, slug, instant)
    archived = module.close_item(root, slug, closure(instant).encode(), instant)
    assert module.resolve_category(root, f"work-item:{slug}") == archived.resolve()
    try:
        module.migrate_legacy(root, f"work-item:{slug}", incoming_links_inventory=None)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-LEGACY-LINK-UNMAPPED"
    else:
        raise AssertionError("legacy migration lacked link inventory")


def test_prewrite_failure_preserves_canonical_and_readme_bytes(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "preserved"
    seed_active(module, root, slug)
    status_before = (root / "work-items" / "active" / slug / "status.md").read_bytes()
    readme_before = (root / "work-items" / "README.md").read_bytes()
    bad_instant = "2026-07-31 12:00:00"
    try:
        module.close_item(root, slug, closure(bad_instant).encode(), bad_instant)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"
    else:
        raise AssertionError("malformed local-time instant was admitted")
    assert (root / "work-items" / "active" / slug / "status.md").read_bytes() == status_before
    assert (root / "work-items" / "README.md").read_bytes() == readme_before
    assert not (root / "work-items" / "archive").exists()

    duplicate_source = root / "duplicate.md"
    write(duplicate_source, "Task: duplicate\n")
    try:
        module.create_candidate(root, slug, duplicate_source.read_bytes())
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-DUAL-LOCATION"
    else:
        raise AssertionError("duplicate slug was admitted")
    assert (root / "work-items" / "active" / slug / "status.md").read_bytes() == status_before
    assert (root / "work-items" / "README.md").read_bytes() == readme_before


def test_missing_readme_markers_fail_before_canonical_write(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    readme = root / "work-items" / "README.md"
    write(readme, "# Human guide without generated ownership markers\n")
    before = readme.read_bytes()

    try:
        module.create_candidate(root, "marker-preflight", b"Task: preserve bytes\n")
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-README-MARKERS"
    else:
        raise AssertionError("missing README markers mutated canonical state")

    assert readme.read_bytes() == before
    assert not (root / "work-items" / "backlog" / "marker-preflight.md").exists()


def test_markerless_bootstrap_replaces_legacy_board_with_default_guide(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    write(
        root / "work-items" / "active" / "freshness" / "status.md",
        quick_status("Current freshness repair.").replace(
            "Execute the current step.",
            "Reset the stale README guide.",
        ),
    )
    readme = root / "work-items" / "README.md"
    write(
        readme,
        "# Work items\n\n"
        "Snapshot commit: `964ee371`\n\n"
        "## Active work\n\n"
        "- Old pre-implementation task text.\n\n"
        "## Archived status\n\n"
        "- Clean worktree; lifecycle counts are old.\n",
    )

    module.refresh_readme(root, allow_marker_bootstrap=True)

    rendered = readme.read_text(encoding="utf-8")
    assert rendered.startswith(module._default_static_guide())
    assert rendered.count(module.README_BEGIN) == 1
    assert rendered.count(module.README_END) == 1
    assert "Snapshot commit" not in rendered
    assert "## Active work" not in rendered
    assert "## Archived status" not in rendered
    assert "Old pre-implementation task text" not in rendered
    assert "Current freshness repair." in rendered
    assert "Reset the stale README guide." in rendered


def test_valid_human_static_guide_is_preserved_by_ordinary_refresh(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    write(
        root / "work-items" / "active" / "preserve-guide" / "status.md",
        quick_status("Preserve the human guide."),
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    readme = root / "work-items" / "README.md"
    generated = readme.read_text(encoding="utf-8")
    marker_region = generated[generated.index(module.README_BEGIN) :]
    human_guide = (
        "# Work items\n\n"
        "Read the generated board, use the lifecycle owner for updates, "
        "and open linked detail.\n\n"
    )
    write(readme, human_guide + marker_region)

    module.refresh_readme(root)

    refreshed = readme.read_text(encoding="utf-8")
    assert refreshed.startswith(human_guide)
    assert refreshed.count(module.README_BEGIN) == 1
    assert refreshed.count(module.README_END) == 1


def test_explicit_static_guide_reset_is_target_bound_and_idempotent(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    write(
        root / "work-items" / "active" / "repair-guide" / "status.md",
        quick_status("Repair the current README.").replace(
            "Execute the current step.",
            "Run the explicit static-guide repair.",
        ),
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    readme = root / "work-items" / "README.md"
    generated = readme.read_text(encoding="utf-8")
    marker_region = generated[generated.index(module.README_BEGIN) :]
    stale_prefix = (
        "# Work items\n\n"
        "Snapshot commit: `964ee371`\n\n"
        "## Active work\n\n"
        "- Old lifecycle counts and clean worktree claim.\n\n"
        "## Archived status\n\n"
    )
    write(readme, stale_prefix + marker_region)
    stale_bytes = readme.read_bytes()
    stale_hash = hashlib.sha256(stale_bytes).hexdigest()

    wrong_target = run_cli(
        "refresh",
        "--root",
        str(root),
        "--reset-static-guide",
        "--expected-readme-sha256",
        "0" * 64,
    )
    assert wrong_target.returncode == 1
    assert "WI-README-REPAIR-TARGET-MISMATCH" in wrong_target.stdout
    assert readme.read_bytes() == stale_bytes

    invalid = stale_bytes.replace(module.README_END.encode(), b"")
    readme.write_bytes(invalid)
    invalid_result = run_cli(
        "refresh",
        "--root",
        str(root),
        "--reset-static-guide",
        "--expected-readme-sha256",
        hashlib.sha256(invalid).hexdigest(),
    )
    assert invalid_result.returncode == 1
    assert "WI-README-MARKERS" in invalid_result.stdout
    assert readme.read_bytes() == invalid
    readme.write_bytes(stale_bytes)

    repaired = run_cli(
        "refresh",
        "--root",
        str(root),
        "--reset-static-guide",
        "--expected-readme-sha256",
        stale_hash,
    )
    assert repaired.returncode == 0, repaired.stdout
    repaired_bytes = readme.read_bytes()
    repaired_text = repaired_bytes.decode("utf-8")
    assert repaired_text.startswith(module._default_static_guide())
    assert repaired_text.count(module.README_BEGIN) == 1
    assert repaired_text.count(module.README_END) == 1
    assert "Snapshot commit" not in repaired_text
    assert "## Active work" not in repaired_text
    assert "## Archived status" not in repaired_text
    assert "Repair the current README." in repaired_text
    assert "Run the explicit static-guide repair." in repaired_text

    replay = run_cli(
        "refresh",
        "--root",
        str(root),
        "--reset-static-guide",
        "--expected-readme-sha256",
        stale_hash,
    )
    assert replay.returncode == 0, replay.stdout
    assert readme.read_bytes() == repaired_bytes

    current = readme.read_text(encoding="utf-8")
    current_region = current[current.index(module.README_BEGIN) :]
    valid_human_guide = "# Work items\n\nKeep this reviewed human guide.\n\n"
    write(readme, valid_human_guide + current_region)
    changed_bytes = readme.read_bytes()
    refused = run_cli(
        "refresh",
        "--root",
        str(root),
        "--reset-static-guide",
        "--expected-readme-sha256",
        stale_hash,
    )
    assert refused.returncode == 1
    assert "WI-README-REPAIR-TARGET-MISMATCH" in refused.stdout
    assert readme.read_bytes() == changed_bytes


def test_location_status_matrix_rejects_semantic_escape(tmp_path: Path) -> None:
    module = load_module()
    terminal_root = tmp_path / "terminal-root"
    write(
        terminal_root / "work-items" / "decisions" / "terminal.md",
        "status: superseded\n",
    )
    try:
        module.audit(terminal_root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-TERMINAL-IN-CURRENT"
    else:
        raise AssertionError("terminal decision remained in current root")

    current_archive = tmp_path / "current-archive"
    write(
        current_archive
        / "work-items"
        / "decisions"
        / "archive"
        / "2026-07"
        / "current.md",
        "status: proposed\n",
    )
    try:
        module.audit(current_archive)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-CURRENT-IN-ARCHIVE"
    else:
        raise AssertionError("current decision remained in archive")


def test_depends_on_remains_bare_slug_and_bypasses_generic_resolver(tmp_path: Path) -> None:
    module = load_module()
    absent = staged_status("archived-original").replace(
        "Reopens: archived-original\n",
        "Depends-on: none\n",
    )
    module._validate_active_status_bytes(absent.encode())

    bare = staged_status("archived-original").replace(
        "Reopens: archived-original\n",
        "Depends-on: first-work-item, second-work-item\n",
    )
    module._validate_active_status_bytes(bare.encode())

    qualified = bare.replace(
        "Depends-on: first-work-item, second-work-item",
        "Depends-on: decision:first-work-item",
    )
    try:
        module._validate_active_status_bytes(qualified.encode())
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-DEPENDENCY-NON-WORK-ITEM"
    else:
        raise AssertionError("Depends-on routed through the category resolver")


def test_optional_epic_none_is_ignored_by_readme_renderer(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    status = root / "work-items" / "active" / "no-epic" / "status.md"
    write(
        status,
        quick_status("Render without an epic.") + "\nRoadmap: none\nEpic: none\n",
    )

    module.refresh_readme(root, allow_marker_bootstrap=True)

    readme = (root / "work-items" / "README.md").read_text(encoding="utf-8")
    assert "[work item](active/no-epic/status.md)" in readme
    assert "[roadmap](" not in readme
    assert "[epic](" not in readme


def test_real_epic_reference_remains_strict_and_resolves_when_present(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    status = root / "work-items" / "active" / "epic-member" / "status.md"

    for unresolved in ("null", "missing-slug"):
        write(
            status,
            quick_status("Render an epic member.") + f"\nEpic: {unresolved}\n",
        )
        try:
            module.collect_readme_entries(root)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-REFERENCE-MISSING"
        else:
            raise AssertionError(f"missing real Epic reference was accepted: {unresolved}")

    write(status, quick_status("Render an epic member.") + "\nEpic: None\n")
    try:
        module.collect_readme_entries(root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-INVALID-SLUG"
    else:
        raise AssertionError("non-canonical absence spelling was accepted")

    write(root / "work-items" / "epics" / "real-epic.md", "status: active\n")
    write(status, quick_status("Render an epic member.") + "\nEpic: real-epic\n")
    entries = module.collect_readme_entries(root)

    item_entry = next(
        entry for entry in entries if entry.logical_reference == "work-item:epic-member"
    )
    assert "[epic](epics/real-epic.md)" in item_entry.detail


def test_unsettled_ledger_rejects_archive_without_mutation(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "unsettled-ledger"
    seed_active(module, root, slug)
    item = root / "work-items" / "active" / slug
    revise = {
        "schemaVersion": 2,
        "runId": "unsettled-review-run",
        "workItem": slug,
        "role": "qa-engineer",
        "executionRole": "internal",
        "status": "revise",
        "gate": "REVISE",
        "scope": ["scripts/mutate-work-item.py"],
        "artifact": "status.md",
        "evidence": [{"kind": "review", "ref": "fixture", "result": "revise"}],
        "startedAt": "2026-07-31T00:00:00Z",
        "updatedAt": "2026-07-31T00:01:00Z",
        "eventKind": "standalone",
        "findingClass": "correctness",
    }
    write(item / "agent-runs.jsonl", json.dumps(revise) + "\n")
    readme_before = (root / "work-items" / "README.md").read_bytes()
    instant = "2026-07-31T12:00:00Z"
    try:
        module.close_item(root, slug, closure(instant).encode(), instant)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-LEDGER-UNSETTLED"
    else:
        raise AssertionError("unsettled REVISE was archived")
    assert item.is_dir()
    assert not (item / "closure.md").exists()
    assert (root / "work-items" / "README.md").read_bytes() == readme_before


def test_reopen_creates_new_successor_and_preserves_archive(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "original-concern"
    seed_active(module, root, slug)
    instant = "2026-07-31T13:00:00Z"
    write_empty_bug_dispositions(root, slug, instant)
    archived = module.close_item(root, slug, closure(instant).encode(), instant)
    archive_hash = hashlib.sha256((archived / "closure.md").read_bytes()).hexdigest()
    successor = module.reopen_item(
        root, slug, "successor-concern", staged_status(slug).encode()
    )
    assert successor == root / "work-items" / "active" / "successor-concern"
    assert archived.is_dir()
    assert hashlib.sha256((archived / "closure.md").read_bytes()).hexdigest() == archive_hash
    assert module.resolve_category(root, f"work-item:{slug}") == archived.resolve()


def test_index_is_compatibility_only_and_cannot_change_render(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "trial"
    first, second = module.run_trial(root, FIXTURE)
    assert first == second
    readme = root / "work-items" / "README.md"
    before = readme.read_bytes()
    write(root / "work-items" / "index.md", "# Fabricated lifecycle truth\n")
    assert module.refresh_readme(root) == first
    assert readme.read_bytes() == before


def test_decision_promotion_supersedes_proposed_guard(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    decision = root / "work-items" / "decisions" / "physical-lifecycle-v1.md"
    write(decision, "---\nstatus: proposed\n---\n")
    before = decision.read_bytes()
    inventory = root / "incoming.json"
    write(
        inventory,
        json.dumps({"reference": "decision:physical-lifecycle-v1", "incomingLinks": []}),
    )
    try:
        module.migrate_legacy(
            root,
            "decision:physical-lifecycle-v1",
            incoming_links_inventory=inventory,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"
    else:
        raise AssertionError("a non-terminal proposed decision was promoted")
    assert decision.read_bytes() == before
    assert module.resolve_category(root, "decision:physical-lifecycle-v1") == decision.resolve()


def _terminal_record(
    category: str,
    instant: str,
    *,
    status_override: str | None = None,
) -> str:
    status = status_override or {
        "bug": "fixed",
        "decision": "dropped",
        "lesson": "archived",
        "roadmap": "archived",
        "epic": "closed",
    }[category]
    utc_field = "Closed" if category == "epic" else "Terminal-at"
    detail_field = {
        "bug": "Resolution",
        "decision": "Rationale",
        "lesson": "Disposition",
        "roadmap": "Disposition",
        "epic": "Outcome",
    }[category]
    return (
        f"status: {status}\n"
        f"{utc_field}: {instant}\n"
        f"{detail_field}: accepted terminal evidence\n"
        "Evidence: focused lifecycle test\n"
    )


def _current_decision_record(
    slug: str,
    *,
    status: str = "proposed",
    body: str = "Synthetic decision.\n",
) -> str:
    date = slug[:10]
    return (
        f"- id: {slug}\n"
        f"- status: {status}\n"
        f"- date: {date}\n"
        "- decided-by: lifecycle test\n"
        "- context: lifecycle-test\n"
        "- supersedes: none\n"
        "- superseded-by: none\n"
        "\n"
        f"# Decision: {slug}\n\n"
        f"{body}"
    )


def test_category_migration_admission_table_has_six_complete_rows(tmp_path: Path) -> None:
    module = load_module()
    rows = module.CATEGORY_ADMISSION_TABLE
    assert len(rows) == 6
    assert {row.category for row in rows} == set(module.CATEGORIES)
    for row in rows:
        assert all(
            (
                row.category,
                row.current_reader,
                row.terminal_validator,
                row.utc_field_owner,
                row.negative_fixture,
            )
        )
        assert module._admission_for(row.category) == row


def test_category_migration_missing_admission_cell_fails_closed(tmp_path: Path) -> None:
    module = load_module()
    decision = next(
        row for row in module.CATEGORY_ADMISSION_TABLE if row.category == "decision"
    )
    module.CATEGORY_ADMISSION_TABLE = tuple(
        replace(row, negative_fixture="")
        if row.category == "decision"
        else row
        for row in module.CATEGORY_ADMISSION_TABLE
    )
    assert decision.negative_fixture
    try:
        module._admission_for("decision")
    except module.LifecycleError as exc:
        assert exc.failure_id == "CATEGORY-MIGRATION-ADMISSION-GATE"
    else:
        raise AssertionError("an incomplete admission row was accepted")


def test_flat_categories_archive_replay_and_reopen_successor(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    instant = "2026-08-01T00:00:00Z"
    current_status = {
        "bug": "open",
        "decision": "proposed",
        "lesson": "open",
        "roadmap": "draft",
        "epic": "active",
    }
    for category_name in ("bug", "decision", "lesson", "roadmap", "epic"):
        category = module.CATEGORIES[category_name]
        slug = f"{category_name}-original"
        reference = f"{category_name}:{slug}"
        source = (
            root
            / "work-items"
            / category.current_root
            / f"{slug}.md"
        )
        terminal = _terminal_record(category_name, instant).encode()
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(terminal)
        inventory = root / f"{category_name}-incoming.json"
        write(inventory, json.dumps({"reference": reference, "incomingLinks": []}))

        archived = module.migrate_legacy(
            root, reference, incoming_links_inventory=inventory
        )
        archived_hash = hashlib.sha256(archived.read_bytes()).hexdigest()
        original_tz = os.environ.get("TZ")
        try:
            os.environ["TZ"] = "Pacific/Honolulu"
            replayed = module.migrate_legacy(
                root, reference, incoming_links_inventory=inventory
            )
        finally:
            if original_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = original_tz
        assert replayed == archived
        assert archived.parent.name == "2026-08"
        assert hashlib.sha256(archived.read_bytes()).hexdigest() == archived_hash

        successor_slug = (
            "2026-08-01-decision-successor"
            if category_name == "decision"
            else f"{category_name}-successor"
        )
        successor_data = (
            _current_decision_record(
                successor_slug,
                status=current_status[category_name],
                body=f"Reopens: {slug}\n",
            ).encode()
            if category_name == "decision"
            else (
                f"status: {current_status[category_name]}\n"
                f"Reopens: {slug}\n"
            ).encode()
        )
        successor = module.reopen_category_record(
            root, reference, successor_slug, successor_data
        )
        assert successor.read_bytes() == successor_data
        assert archived.read_bytes() == terminal
        assert module.resolve_category(root, reference) == archived.resolve()
    module.audit(root)


def test_every_category_terminal_status_and_missing_evidence_fixture(
    tmp_path: Path,
) -> None:
    module = load_module()
    instant = "2026-08-01T00:00:00Z"
    root = tmp_path / "repo"
    for category_name in ("bug", "decision", "lesson", "roadmap", "epic"):
        category = module.CATEGORIES[category_name]
        for status in sorted(category.terminal_statuses):
            slug = f"{category_name}-{status}"
            reference = f"{category_name}:{slug}"
            source = (
                root
                / "work-items"
                / category.current_root
                / f"{slug}.md"
            )
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(
                _terminal_record(
                    category_name,
                    instant,
                    status_override=status,
                ).encode()
            )
            inventory = root / f"incoming-{slug}.json"
            write(
                inventory,
                json.dumps({"reference": reference, "incomingLinks": []}),
            )
            archived = module.migrate_legacy(
                root,
                reference,
                incoming_links_inventory=inventory,
            )
            assert archived.parent.name == "2026-08"

        missing = _terminal_record(
            category_name,
            instant,
        ).replace("Evidence: focused lifecycle test\n", "")
        try:
            module._validate_flat_terminal(category, missing.encode())
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"
        else:
            raise AssertionError(f"{category_name} missing evidence was accepted")

    for status in sorted(module.CATEGORIES["work-item"].terminal_statuses):
        item = (
            root
            / "work-items"
            / "archive"
            / "2026-08"
            / f"work-item-{status}"
        )
        write(item / "status.md", f"status: {status}\n")
        write(item / "closure.md", closure(instant))
    module.audit_categories(root)
    try:
        module._validate_closure(
            f"Closed: {instant}\nOutcome: missing evidence\n".encode(),
            instant,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"
    else:
        raise AssertionError("work-item missing terminal evidence was accepted")


def test_all_categories_dual_location_fail_closed(tmp_path: Path) -> None:
    module = load_module()
    for category_name, category in module.CATEGORIES.items():
        root = tmp_path / category_name
        slug = "duplicate"
        if category_name == "work-item":
            write(root / "work-items" / "active" / slug / "status.md", "status: active\n")
            write(
                root / "work-items" / "archive" / "2026-07" / slug / "status.md",
                "status: completed\n",
            )
        else:
            write(
                root / "work-items" / category.current_root / f"{slug}.md",
                f"status: {next(iter(category.current_statuses))}\n",
            )
            write(
                root
                / "work-items"
                / category.current_root
                / "archive"
                / "2026-07"
                / f"{slug}.md",
                f"status: {next(iter(category.terminal_statuses))}\n",
            )
        try:
            module.audit_categories(root)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-DUAL-LOCATION"
        else:
            raise AssertionError(f"{category_name} dual location was accepted")


def test_interrupted_category_moves_preserve_current_bytes(tmp_path: Path) -> None:
    module = load_module()
    instant = "2026-07-31T23:59:59Z"

    work_root = tmp_path / "work-item"
    seed_active(module, work_root, "interrupted-work-item")
    active = work_root / "work-items" / "active" / "interrupted-work-item"
    write(active / "closure.md", closure(instant))
    work_inventory = work_root / "incoming.json"
    work_reference = "work-item:interrupted-work-item"
    write(
        work_inventory,
        json.dumps({"reference": work_reference, "incomingLinks": []}),
    )
    status_before = (active / "status.md").read_bytes()
    readme_before = (work_root / "work-items" / "README.md").read_bytes()
    original_replace = module.os.replace

    def fail_work_item_move(source, target):
        if Path(source) == active:
            raise OSError("injected directory move interruption")
        return original_replace(source, target)

    module.os.replace = fail_work_item_move
    try:
        try:
            module.migrate_legacy(
                work_root,
                work_reference,
                incoming_links_inventory=work_inventory,
            )
        except OSError as exc:
            assert "injected directory move interruption" in str(exc)
        else:
            raise AssertionError("interrupted work-item move returned success")
    finally:
        module.os.replace = original_replace
    assert active.is_dir()
    assert (active / "status.md").read_bytes() == status_before
    assert (work_root / "work-items" / "README.md").read_bytes() == readme_before

    for category_name in ("bug", "decision", "lesson", "roadmap", "epic"):
        category = module.CATEGORIES[category_name]
        root = tmp_path / category_name
        slug = f"interrupted-{category_name}"
        reference = f"{category_name}:{slug}"
        source = root / "work-items" / category.current_root / f"{slug}.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(_terminal_record(category_name, instant).encode())
        before = source.read_bytes()
        inventory = root / "incoming.json"
        write(inventory, json.dumps({"reference": reference, "incomingLinks": []}))

        def fail_flat_move(candidate, target):
            if Path(candidate) == source:
                raise OSError("injected flat move interruption")
            return original_replace(candidate, target)

        module.os.replace = fail_flat_move
        try:
            try:
                module.migrate_legacy(
                    root,
                    reference,
                    incoming_links_inventory=inventory,
                )
            except OSError as exc:
                assert "injected flat move interruption" in str(exc)
            else:
                raise AssertionError(f"interrupted {category_name} move returned success")
        finally:
            module.os.replace = original_replace
        assert source.read_bytes() == before


def test_all_category_location_status_negatives_are_exact(tmp_path: Path) -> None:
    module = load_module()
    instant = "2026-07-31T19:00:00Z"
    for category_name in ("bug", "decision", "lesson", "roadmap", "epic"):
        category = module.CATEGORIES[category_name]
        terminal_root = tmp_path / f"{category_name}-terminal-current"
        terminal = (
            terminal_root
            / "work-items"
            / category.current_root
            / "record.md"
        )
        write(terminal, _terminal_record(category_name, instant))
        try:
            module.audit_categories(terminal_root)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-TERMINAL-IN-CURRENT"
        else:
            raise AssertionError(f"{category_name} terminal current location was accepted")

        current_root = tmp_path / f"{category_name}-current-archive"
        current = (
            current_root
            / "work-items"
            / category.current_root
            / "archive"
            / "2026-07"
            / "record.md"
        )
        write(current, f"status: {next(iter(category.current_statuses))}\n")
        try:
            module.audit_categories(current_root)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-CURRENT-IN-ARCHIVE"
        else:
            raise AssertionError(f"{category_name} current archive location was accepted")


def test_work_item_archive_status_is_terminal_and_active_terminal_fails(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "terminalized-work-item"
    seed_active(module, root, slug)
    instant = "2026-07-31T20:00:00Z"
    write_empty_bug_dispositions(root, slug, instant)
    archived = module.close_item(root, slug, closure(instant).encode(), instant)
    status = module._parse_fields((archived / "status.md").read_text(encoding="utf-8"))
    assert status["status"] == "completed"
    module.audit_categories(root)

    active = root / "work-items" / "active" / "invalid-terminal"
    write(active / "status.md", "status: completed\n")
    try:
        module.audit_categories(root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-TERMINAL-IN-CURRENT"
    else:
        raise AssertionError("terminal work-item remained active")


def test_inventory_cli_exact_three_command_contract(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    source = work_items / "bugs" / "terminal-bug.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(
        _terminal_record(
            "bug",
            "2026-08-01T00:00:00Z",
            status_override="fixed",
        ).encode()
    )
    write(
        work_items / "decisions" / "consumer.md",
        "status: proposed\nRelated: bug:terminal-bug\n",
    )
    write(
        work_items / "README.md",
        "# Legacy work-items guide\n\nHuman-owned migration context.\n",
    )
    inventory = root / ".scratch" / "work-items-lifecycle-v1" / "migration-inventory.json"

    audited = run_cli(
        "audit",
        "--root",
        str(work_items),
        "--output",
        str(inventory),
    )
    assert audited.returncode == 0, audited.stdout
    assert "AUDIT: PASS" in audited.stdout
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    assert payload["schemaVersion"] == 1
    assert payload["digestAlgorithms"] == {
        "file": "sha256-file-bytes-v1",
        "directory": "sha256-tree-entries-v1",
    }
    assert len(payload["rows"]) == 1
    row = payload["rows"][0]
    assert {
        "category",
        "source",
        "target",
        "terminalInstant",
        "inputSha256",
        "digestAlgorithm",
        "incomingLinks",
        "admission",
    } <= set(row)
    assert row["category"] == "bug"
    assert row["admission"]["result"] == "admitted"
    assert row["incomingLinks"]["result"] == "logical-only"

    migrated = run_cli(
        "migrate",
        "--root",
        str(work_items),
        "--inventory",
        str(inventory),
        "--apply-admitted",
        "--render-readme",
        "--byte-check",
    )
    assert migrated.returncode == 0, migrated.stdout
    assert "MIGRATION: PASS" in migrated.stdout
    assert "readme_byte_check=PASS" in migrated.stdout
    assert "source_target_disjoint=PASS" in migrated.stdout

    verified = run_cli(
        "audit",
        "--root",
        str(work_items),
        "--verify-migration",
        str(inventory),
    )
    assert verified.returncode == 0, verified.stdout
    assert "AUDIT: PASS" in verified.stdout
    assert "migration_rows=1" in verified.stdout
    target = work_items / Path(row["target"])
    assert not source.exists()
    assert target.is_file()
    assert hashlib.sha256(target.read_bytes()).hexdigest() == row["inputSha256"]
    readme = (work_items / "README.md").read_text(encoding="utf-8")
    assert readme.startswith(load_module()._default_static_guide())
    assert "# Legacy work-items guide" not in readme
    assert "Human-owned migration context." not in readme
    assert readme.count("<!-- BEGIN GENERATED WORK-ITEMS STATUS -->") == 1
    assert readme.count("<!-- END GENERATED WORK-ITEMS STATUS -->") == 1


def test_inventory_preflight_denial_moves_no_selected_record(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    for slug in ("first", "second"):
        source = work_items / "bugs" / f"{slug}.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(
            _terminal_record(
                "bug",
                "2026-07-31T23:59:59Z",
                status_override="fixed",
            ).encode()
        )
    inventory = root / "inventory.json"
    audited = run_cli(
        "audit", "--root", str(work_items), "--output", str(inventory)
    )
    assert audited.returncode == 0, audited.stdout
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    payload["rows"][1]["admission"] = {
        "result": "denied",
        "failureId": "CATEGORY-MIGRATION-ADMISSION-GATE",
        "reason": "injected denial",
    }
    inventory.write_text(json.dumps(payload), encoding="utf-8")
    before = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (work_items / "bugs").glob("*.md")
    }

    migrated = run_cli(
        "migrate",
        "--root",
        str(work_items),
        "--inventory",
        str(inventory),
        "--apply-admitted",
        "--render-readme",
        "--byte-check",
    )
    assert migrated.returncode == 1
    assert "CATEGORY-MIGRATION-ADMISSION-GATE" in migrated.stdout
    after = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (work_items / "bugs").glob("*.md")
    }
    assert after == before
    assert not (work_items / "bugs" / "archive").exists()


def test_inventory_payload_drift_is_preflighted_before_first_move(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    for slug in ("first", "second"):
        path = work_items / "bugs" / f"{slug}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_terminal_record("bug", "2026-08-01T00:00:00Z").encode())
    inventory = root / "inventory.json"
    audited = run_cli(
        "audit", "--root", str(work_items), "--output", str(inventory)
    )
    assert audited.returncode == 0, audited.stdout
    second = work_items / "bugs" / "second.md"
    second.write_bytes(second.read_bytes() + b"Drift: after inventory\n")
    first_hash = hashlib.sha256(
        (work_items / "bugs" / "first.md").read_bytes()
    ).hexdigest()

    migrated = run_cli(
        "migrate",
        "--root",
        str(work_items),
        "--inventory",
        str(inventory),
        "--apply-admitted",
        "--render-readme",
        "--byte-check",
    )
    assert migrated.returncode == 1
    assert "WI-CATEGORY-MIGRATION-PAYLOAD" in migrated.stdout
    assert hashlib.sha256(
        (work_items / "bugs" / "first.md").read_bytes()
    ).hexdigest() == first_hash
    assert not (work_items / "bugs" / "archive").exists()


def test_inventory_unmapped_physical_link_fails_before_move(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    source = work_items / "bugs" / "linked.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(_terminal_record("bug", "2026-08-01T00:00:00Z").encode())
    write(
        work_items / "decisions" / "consumer.md",
        "status: proposed\n[physical](../bugs/linked.md)\n",
    )
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    inventory = root / "inventory.json"

    audited = run_cli(
        "audit", "--root", str(work_items), "--output", str(inventory)
    )
    assert audited.returncode == 1
    assert "WI-LEGACY-LINK-UNMAPPED" in audited.stdout
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    assert payload["rows"][0]["incomingLinks"]["result"] == "unmapped"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    assert not (work_items / "bugs" / "archive").exists()


def test_inventory_target_self_identity_is_excluded_on_replay(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    reference = "bug:self-identifying"
    source = work_items / "bugs" / "self-identifying.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(
        (
            _terminal_record("bug", "2026-08-01T00:00:00Z")
            + f"- id: self-identifying\nRelated: {reference}\n"
        ).encode()
    )
    external = work_items / "decisions" / "external-consumer.md"
    write(external, f"status: proposed\nRelated: {reference}\n")
    inventory = root / ".scratch" / "migration-inventory.json"

    audited = run_cli(
        "audit",
        "--root",
        str(work_items),
        "--output",
        str(inventory),
    )
    assert audited.returncode == 0, audited.stdout
    row = json.loads(inventory.read_text(encoding="utf-8"))["rows"][0]
    assert row["incomingLinks"] == {
        "result": "logical-only",
        "references": [
            {
                "consumer": "decisions/external-consumer.md",
                "kind": "logical",
                "value": reference,
            }
        ],
    }

    first = run_cli(*_bulk_migrate_args(work_items, inventory))
    assert first.returncode == 0, first.stdout
    replay = run_cli(*_bulk_migrate_args(work_items, inventory))
    assert replay.returncode == 0, replay.stdout
    verified = run_cli(
        "audit",
        "--root",
        str(work_items),
        "--verify-migration",
        str(inventory),
    )
    assert verified.returncode == 0, verified.stdout


def test_incoming_link_owned_path_set_does_not_hide_third_consumers(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    work_items = root / "work-items"
    reference = "bug:owned-record"
    source = work_items / "bugs" / "owned-record.md"
    target = work_items / "bugs" / "archive" / "2026-08" / "owned-record.md"
    write(source, f"Related: {reference}\n")
    write(target, f"Related: {reference}\n")
    logical = work_items / "decisions" / "logical-consumer.md"
    physical = work_items / "decisions" / "physical-consumer.md"
    write(logical, f"status: proposed\nRelated: {reference}\n")
    write(physical, "status: proposed\n[record](../bugs/owned-record.md)\n")

    result = module._incoming_link_result(
        root,
        {source, target},
        reference,
    )
    assert result["result"] == "unmapped"
    assert {
        (row["consumer"], row["kind"])
        for row in result["references"]
    } == {
        ("decisions/logical-consumer.md", "logical"),
        ("decisions/physical-consumer.md", "physical"),
    }


def test_incoming_link_inventory_normalizes_fragment_and_query_for_identity(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    work_items = root / "work-items"
    owned = work_items / "roadmaps" / "historical.md"
    write(owned, "status: archived\n")
    consumer = (
        work_items
        / "epics"
        / "archive"
        / "2026-07"
        / "closed-epic.md"
    )
    content = (
        "[fragment](../../../roadmaps/historical.md#section)\n"
        "[query](../../../roadmaps/historical.md?view=full)\n"
        "[external](https://example.invalid/roadmaps/historical.md#section)\n"
        "[mailto](mailto:historical@example.invalid)\n"
        "[anchor](#section)\n"
        "[root](/roadmaps/historical.md)\n"
    )
    write(consumer, content)

    parsed = list(module._markdown_local_links(content))
    assert parsed
    assert all(content[link.href_start : link.href_end] == link.href for link in parsed)

    result = module._incoming_link_result(root, {owned}, "roadmap:historical")

    assert result == {
        "result": "unmapped",
        "references": [
            {
                "consumer": "epics/archive/2026-07/closed-epic.md",
                "kind": "physical",
                "value": "../../../roadmaps/historical.md#section",
            },
            {
                "consumer": "epics/archive/2026-07/closed-epic.md",
                "kind": "physical",
                "value": "../../../roadmaps/historical.md?view=full",
            },
        ],
    }


def test_verify_migration_allows_logical_churn_but_rejects_physical_links(
    tmp_path: Path,
) -> None:
    for case in ("removed-logical", "added-logical", "added-physical"):
        root = tmp_path / case
        work_items = root / "work-items"
        reference = "bug:link-change"
        source = work_items / "bugs" / "link-change.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(
            _terminal_record("bug", "2026-08-01T00:00:00Z").encode()
        )
        consumer = work_items / "decisions" / "consumer.md"
        if case == "removed-logical":
            write(consumer, f"status: proposed\nRelated: {reference}\n")
        inventory = root / ".scratch" / "migration-inventory.json"
        audited = run_cli(
            "audit",
            "--root",
            str(work_items),
            "--output",
            str(inventory),
        )
        assert audited.returncode == 0, audited.stdout
        row = json.loads(inventory.read_text(encoding="utf-8"))["rows"][0]
        migrated = run_cli(*_bulk_migrate_args(work_items, inventory))
        assert migrated.returncode == 0, migrated.stdout

        if case == "removed-logical":
            write(consumer, "status: proposed\n")
        elif case == "added-logical":
            write(consumer, f"status: proposed\nRelated: {reference}\n")
        else:
            target = work_items / Path(row["target"])
            relative = os.path.relpath(target, consumer.parent).replace("\\", "/")
            write(consumer, f"status: proposed\n[record]({relative})\n")

        verified = run_cli(
            "audit",
            "--root",
            str(work_items),
            "--verify-migration",
            str(inventory),
        )
        if case == "added-physical":
            assert verified.returncode == 1, case
            assert "WI-LEGACY-LINK-UNMAPPED" in verified.stdout, case
        else:
            assert verified.returncode == 0, verified.stdout
            assert "AUDIT: PASS" in verified.stdout


def test_inventory_allows_post_inventory_implementation_artifact_logical_link(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    reference = "bug:canonical-shape"
    source = work_items / "bugs" / "canonical-shape.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(
        _terminal_record("bug", "2026-08-01T00:00:00Z").encode()
    )
    inventory = root / ".scratch" / "migration-inventory.json"
    audited = run_cli(
        "audit",
        "--root",
        str(work_items),
        "--output",
        str(inventory),
    )
    assert audited.returncode == 0, audited.stdout
    row = json.loads(inventory.read_text(encoding="utf-8"))["rows"][0]
    assert row["incomingLinks"] == {"result": "clear", "references": []}

    active = work_items / "active" / "implementation-record"
    write(active / "status.md", quick_status("Record migration implementation."))
    write(
        active / "implementation-phase2.md",
        f"# Implementation evidence\n\nFailing row: `{reference}`.\n",
    )

    migrated = run_cli(*_bulk_migrate_args(work_items, inventory))
    assert migrated.returncode == 0, migrated.stdout
    target = work_items / Path(row["target"])
    assert not source.exists()
    assert target.is_file()
    verified = run_cli(
        "audit",
        "--root",
        str(work_items),
        "--verify-migration",
        str(inventory),
    )
    assert verified.returncode == 0, verified.stdout


def test_inventory_post_inventory_physical_link_fails_before_move(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    source = work_items / "bugs" / "late-physical.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(
        _terminal_record("bug", "2026-08-01T00:00:00Z").encode()
    )
    inventory = root / ".scratch" / "migration-inventory.json"
    audited = run_cli(
        "audit",
        "--root",
        str(work_items),
        "--output",
        str(inventory),
    )
    assert audited.returncode == 0, audited.stdout
    row = json.loads(inventory.read_text(encoding="utf-8"))["rows"][0]
    consumer = work_items / "decisions" / "late-physical-consumer.md"
    write(consumer, "status: proposed\n[record](../bugs/late-physical.md)\n")

    migrated = run_cli(*_bulk_migrate_args(work_items, inventory))
    assert migrated.returncode == 1
    assert "WI-LEGACY-LINK-UNMAPPED" in migrated.stdout
    assert source.is_file()
    assert not (work_items / Path(row["target"])).exists()


def test_inventory_directory_digest_reused_by_post_audit(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    work_items = root / "work-items"
    slug = "directory-payload"
    seed_active(module, root, slug)
    instant = "2026-08-01T00:00:00Z"
    write(work_items / "active" / slug / "closure.md", closure(instant))
    inventory = root / "inventory.json"

    audited = run_cli(
        "audit", "--root", str(work_items), "--output", str(inventory)
    )
    assert audited.returncode == 0, audited.stdout
    row = json.loads(inventory.read_text(encoding="utf-8"))["rows"][0]
    assert row["digestAlgorithm"] == "sha256-tree-entries-v1"
    migrated = run_cli(
        "migrate",
        "--root",
        str(work_items),
        "--inventory",
        str(inventory),
        "--apply-admitted",
        "--render-readme",
        "--byte-check",
    )
    assert migrated.returncode == 0, migrated.stdout
    replayed = run_cli(
        "migrate",
        "--root",
        str(work_items),
        "--inventory",
        str(inventory),
        "--apply-admitted",
        "--render-readme",
        "--byte-check",
    )
    assert replayed.returncode == 0, replayed.stdout
    module.audit_categories(root)
    verified = run_cli(
        "audit",
        "--root",
        str(work_items),
        "--verify-migration",
        str(inventory),
    )
    assert verified.returncode == 0, verified.stdout


def _admitted_bug_inventory(
    root: Path,
    slugs: tuple[str, ...],
) -> tuple[Path, dict]:
    work_items = root / "work-items"
    for slug in slugs:
        source = work_items / "bugs" / f"{slug}.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(
            _terminal_record(
                "bug",
                "2026-08-01T00:00:00Z",
                status_override="fixed",
            ).encode()
        )
    inventory = root / ".scratch" / "migration-inventory.json"
    audited = run_cli(
        "audit",
        "--root",
        str(work_items),
        "--output",
        str(inventory),
    )
    assert audited.returncode == 0, audited.stdout
    return inventory, json.loads(inventory.read_text(encoding="utf-8"))


def _bulk_migrate_args(work_items: Path, inventory: Path) -> tuple[str, ...]:
    return (
        "migrate",
        "--root",
        str(work_items),
        "--inventory",
        str(inventory),
        "--apply-admitted",
        "--render-readme",
        "--byte-check",
    )


def test_inventory_post_move_renderer_failure_exact_rerun_passes(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    work_items = root / "work-items"
    inventory, payload = _admitted_bug_inventory(root, ("renderer-retry",))
    row = payload["rows"][0]
    source = work_items / Path(row["source"])
    target = work_items / Path(row["target"])
    original_refresh = module.refresh_readme

    def fail_after_moves(*_args, **_kwargs):
        raise module.LifecycleError(
            "WI-README-STALE",
            "injected renderer failure after all moves",
        )

    module.refresh_readme = fail_after_moves
    try:
        try:
            module.apply_migration_inventory(
                root,
                inventory,
                render_readme=True,
                byte_check=True,
            )
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-README-STALE"
        else:
            raise AssertionError("post-move renderer failure returned success")
    finally:
        module.refresh_readme = original_refresh

    assert not source.exists()
    assert target.is_file()
    assert hashlib.sha256(target.read_bytes()).hexdigest() == row["inputSha256"]

    rerun = run_cli(*_bulk_migrate_args(work_items, inventory))
    assert rerun.returncode == 0, rerun.stdout
    assert "MIGRATION: PASS" in rerun.stdout
    assert "migration_rows=1" in rerun.stdout
    assert not source.exists()
    assert hashlib.sha256(target.read_bytes()).hexdigest() == row["inputSha256"]


def test_inventory_all_target_replay_is_a_verified_noop(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    inventory, payload = _admitted_bug_inventory(root, ("already-settled",))
    args = _bulk_migrate_args(work_items, inventory)
    first = run_cli(*args)
    assert first.returncode == 0, first.stdout
    row = payload["rows"][0]
    target = work_items / Path(row["target"])
    target_before = target.read_bytes()
    readme_before = (work_items / "README.md").read_bytes()

    replay = run_cli(*args)
    assert replay.returncode == 0, replay.stdout
    assert "migration_rows=1" in replay.stdout
    assert target.read_bytes() == target_before
    assert (work_items / "README.md").read_bytes() == readme_before
    assert not (work_items / Path(row["source"])).exists()


def test_inventory_target_only_replay_renders_active_epic_none(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    inventory, payload = _admitted_bug_inventory(root, ("settled-with-no-epic",))
    legacy_before = seed_legacy_archives(root)
    row = payload["rows"][0]
    source = work_items / Path(row["source"])
    target = work_items / Path(row["target"])
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, target)
    write(
        work_items / "active" / "unrelated-active" / "status.md",
        quick_status("Keep rendering during replay.") + "\nEpic: none\n",
    )

    replay = run_cli(*_bulk_migrate_args(work_items, inventory))

    assert replay.returncode == 0, replay.stdout
    assert "MIGRATION: PASS" in replay.stdout
    assert not source.exists()
    assert hashlib.sha256(target.read_bytes()).hexdigest() == row["inputSha256"]
    assert {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in legacy_before
    } == legacy_before
    readme = (work_items / "README.md").read_text(encoding="utf-8")
    assert "[work item](active/unrelated-active/status.md)" in readme
    assert "[epic](" not in readme
    assert readme.count("WI-LEGACY-READ-COMPAT") == 4


def test_inventory_mixed_source_and_target_rows_resume_only_sources(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    inventory, payload = _admitted_bug_inventory(
        root,
        ("pending-row", "settled-row"),
    )
    rows = {row["reference"]: row for row in payload["rows"]}
    settled = rows["bug:settled-row"]
    settled_source = work_items / Path(settled["source"])
    settled_target = work_items / Path(settled["target"])
    settled_target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(settled_source, settled_target)
    settled_before = settled_target.read_bytes()

    resumed = run_cli(*_bulk_migrate_args(work_items, inventory))
    assert resumed.returncode == 0, resumed.stdout
    assert "migration_rows=2" in resumed.stdout
    for row in payload["rows"]:
        source = work_items / Path(row["source"])
        target = work_items / Path(row["target"])
        assert not source.exists()
        assert target.is_file()
        assert hashlib.sha256(target.read_bytes()).hexdigest() == row["inputSha256"]
    assert settled_target.read_bytes() == settled_before


def test_inventory_resume_negatives_fail_before_any_new_move(
    tmp_path: Path,
) -> None:
    for case in (
        "both",
        "neither",
        "target-hash-drift",
        "wrong-target",
        "category-mismatch",
    ):
        root = tmp_path / case
        work_items = root / "work-items"
        inventory, payload = _admitted_bug_inventory(
            root,
            ("first-pending", "second-invalid"),
        )
        first = next(
            row for row in payload["rows"] if row["reference"] == "bug:first-pending"
        )
        invalid = next(
            row for row in payload["rows"] if row["reference"] == "bug:second-invalid"
        )
        first_source = work_items / Path(first["source"])
        first_target = work_items / Path(first["target"])
        invalid_source = work_items / Path(invalid["source"])
        invalid_target = work_items / Path(invalid["target"])
        observed_invalid_target: Path | None = None

        if case == "both":
            invalid_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(invalid_source, invalid_target)
            observed_invalid_target = invalid_target
        elif case == "neither":
            invalid_source.unlink()
        elif case == "target-hash-drift":
            invalid_target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(invalid_source, invalid_target)
            invalid_target.write_bytes(invalid_target.read_bytes() + b"drift\n")
            observed_invalid_target = invalid_target
        elif case == "wrong-target":
            wrong_target = (
                work_items
                / "bugs"
                / "archive"
                / "2026-07"
                / invalid_source.name
            )
            wrong_target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(invalid_source, wrong_target)
            observed_invalid_target = wrong_target
        else:
            invalid["category"] = "decision"
            inventory.write_text(json.dumps(payload), encoding="utf-8")

        result = run_cli(*_bulk_migrate_args(work_items, inventory))
        assert result.returncode == 1, case
        assert first_source.is_file(), case
        assert not first_target.exists(), case
        if observed_invalid_target is not None:
            assert observed_invalid_target.exists(), case


def _pre_v1_terminal_record(status: str, title: str) -> bytes:
    return (
        f"---\nstatus: {status}\n---\n\n# {title}\n\n"
        "Preserved pre-V1 terminal content.\n"
    ).encode()


def _denied_terminalization_inventory(
    work_items: Path,
    inventory: Path,
) -> dict:
    audited = run_cli(
        "audit",
        "--root",
        str(work_items),
        "--output",
        str(inventory),
    )
    assert audited.returncode == 1, audited.stdout
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    assert payload["rows"]
    assert {
        row["admission"]["failureId"]
        for row in payload["rows"]
    } == {"WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"}
    return payload


def test_v1_terminalization_mixed_records_exact_evidence_and_replay(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    bug = work_items / "bugs" / "historic-bug.md"
    decision = work_items / "decisions" / "historic-decision.md"
    bug.parent.mkdir(parents=True, exist_ok=True)
    decision.parent.mkdir(parents=True, exist_ok=True)
    original = {
        bug: _pre_v1_terminal_record("fixed", "Historic bug"),
        decision: _pre_v1_terminal_record("dropped", "Historic decision"),
    }
    for path, data in original.items():
        path.write_bytes(data)
    original_hashes = {
        path: hashlib.sha256(data).hexdigest() for path, data in original.items()
    }
    inventory = root / ".scratch" / "terminalization-inventory.json"
    receipt = root / ".scratch" / "terminalization-receipt.json"
    payload = _denied_terminalization_inventory(work_items, inventory)
    assert len(payload["rows"]) == 2

    args = (
        "terminalize-v1",
        "--root",
        str(work_items),
        "--inventory",
        str(inventory),
        "--terminal-at",
        "2026-08-01T00:00:00Z",
        "--authorization-marker",
        "operator-authorized-v1-terminalization",
        "--receipt",
        str(receipt),
    )
    applied = run_cli(*args)
    assert applied.returncode == 0, applied.stdout
    assert (
        "TERMINALIZE-V1: PASS rows=2 "
        "marker=operator-authorized-v1-terminalization"
    ) in applied.stdout

    expected_details = {
        bug: (
            "Resolution: Pre-V1 terminal status `fixed` is preserved during "
            "operator-authorized V1 physical migration."
        ),
        decision: (
            "Rationale: Pre-V1 terminal status `dropped` is preserved during "
            "operator-authorized V1 physical migration."
        ),
    }
    first_bytes: dict[Path, bytes] = {}
    for path, before in original.items():
        after = path.read_bytes()
        first_bytes[path] = after
        assert after.startswith(before)
        text = after.decode()
        assert text.count("Terminal-at: 2026-08-01T00:00:00Z") == 1
        assert text.count(expected_details[path]) == 1
        assert text.splitlines().count(
            "Evidence: Historical terminal time is unknown; preserved pre-V1 "
            f"input SHA-256 `{original_hashes[path]}`; original terminal status "
            f"`{'fixed' if path == bug else 'dropped'}`; explicit "
            "operator-authorized V1 migration."
        ) == 1

    receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert receipt_payload["owner"] == "work-items-lifecycle-v1-terminalization"
    assert receipt_payload["rowCount"] == 2
    assert receipt_payload["terminalAt"] == "2026-08-01T00:00:00Z"
    assert receipt_payload["authorizationMarker"] == (
        "operator-authorized-v1-terminalization"
    )
    receipt_before = receipt.read_bytes()

    replay = run_cli(*args)
    assert replay.returncode == 0, replay.stdout
    assert "TERMINALIZE-V1: PASS rows=2 replay=true" in replay.stdout
    assert receipt.read_bytes() == receipt_before
    for path, expected in first_bytes.items():
        assert path.read_bytes() == expected

    refreshed = root / ".scratch" / "post-terminalization-inventory.json"
    audited = run_cli(
        "audit",
        "--root",
        str(work_items),
        "--output",
        str(refreshed),
    )
    assert audited.returncode == 0, audited.stdout
    refreshed_payload = json.loads(refreshed.read_text(encoding="utf-8"))
    assert len(refreshed_payload["rows"]) == 2
    assert {
        row["admission"]["result"] for row in refreshed_payload["rows"]
    } == {"admitted"}
    assert {
        row["terminalInstant"] for row in refreshed_payload["rows"]
    } == {"2026-08-01T00:00:00Z"}
    assert all("/archive/2026-08/" in row["target"] for row in refreshed_payload["rows"])


def test_v1_terminalization_rejects_invalid_authority_and_utc_without_writes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    source = work_items / "bugs" / "historic.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(_pre_v1_terminal_record("fixed", "Historic"))
    inventory = root / ".scratch" / "inventory.json"
    receipt = root / ".scratch" / "receipt.json"
    _denied_terminalization_inventory(work_items, inventory)
    before = source.read_bytes()

    invalid_utc = run_cli(
        "terminalize-v1",
        "--root",
        str(work_items),
        "--inventory",
        str(inventory),
        "--terminal-at",
        "2026-08-01T03:00:00+03:00",
        "--authorization-marker",
        "operator-authorized-v1-terminalization",
        "--receipt",
        str(receipt),
    )
    assert invalid_utc.returncode == 1
    assert "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING" in invalid_utc.stdout
    assert source.read_bytes() == before
    assert not receipt.exists()

    invalid_authority = run_cli(
        "terminalize-v1",
        "--root",
        str(work_items),
        "--inventory",
        str(inventory),
        "--terminal-at",
        "2026-08-01T00:00:00Z",
        "--authorization-marker",
        "operator-approved",
        "--receipt",
        str(receipt),
    )
    assert invalid_authority.returncode == 1
    assert "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING" in invalid_authority.stdout
    assert source.read_bytes() == before
    assert not receipt.exists()


def test_v1_terminalization_preflights_all_rows_before_first_write(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    sources = [
        work_items / "bugs" / "first.md",
        work_items / "decisions" / "second.md",
    ]
    for path, status in zip(sources, ("fixed", "dropped")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_pre_v1_terminal_record(status, path.stem))
    inventory = root / ".scratch" / "inventory.json"
    receipt = root / ".scratch" / "receipt.json"
    payload = _denied_terminalization_inventory(work_items, inventory)
    payload["rows"][1]["admission"]["failureId"] = "INJECTED-WRONG-DENIAL"
    inventory.write_text(json.dumps(payload), encoding="utf-8")
    before = {path: path.read_bytes() for path in sources}

    result = run_cli(
        "terminalize-v1",
        "--root",
        str(work_items),
        "--inventory",
        str(inventory),
        "--terminal-at",
        "2026-08-01T00:00:00Z",
        "--authorization-marker",
        "operator-authorized-v1-terminalization",
        "--receipt",
        str(receipt),
    )
    assert result.returncode == 1
    assert "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING" in result.stdout
    assert {path: path.read_bytes() for path in sources} == before
    assert not receipt.exists()


def test_v1_terminalization_rejects_hash_drift_unsupported_category_and_conflict(
    tmp_path: Path,
) -> None:
    for case in ("hash-drift", "unsupported-category", "conflicting-field"):
        root = tmp_path / case
        work_items = root / "work-items"
        source = work_items / "bugs" / "historic.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        if case == "conflicting-field":
            source.write_bytes(
                _pre_v1_terminal_record("fixed", "Historic")
                + b"\nTerminal-at: 2025-01-01T00:00:00Z\n"
            )
        else:
            source.write_bytes(_pre_v1_terminal_record("fixed", "Historic"))
        inventory = root / ".scratch" / "inventory.json"
        receipt = root / ".scratch" / "receipt.json"
        payload = _denied_terminalization_inventory(work_items, inventory)
        if case == "hash-drift":
            source.write_bytes(source.read_bytes() + b"\nDrift: after audit\n")
        elif case == "unsupported-category":
            payload["rows"][0]["category"] = "lesson"
            inventory.write_text(json.dumps(payload), encoding="utf-8")
        before = source.read_bytes()

        result = run_cli(
            "terminalize-v1",
            "--root",
            str(work_items),
            "--inventory",
            str(inventory),
            "--terminal-at",
            "2026-08-01T00:00:00Z",
            "--authorization-marker",
            "operator-authorized-v1-terminalization",
            "--receipt",
            str(receipt),
        )
        assert result.returncode == 1
        assert "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING" in result.stdout
        assert source.read_bytes() == before
        assert not receipt.exists()


def test_v1_terminalization_rejects_degenerate_authoritative_field_occurrences(
    tmp_path: Path,
) -> None:
    cases = {
        "terminal-at-empty": b"Terminal-at:\n",
        "terminal-at-duplicate": (
            b"Terminal-at: 2025-01-01T00:00:00Z\n"
            b"Terminal-at: 2025-01-02T00:00:00Z\n"
        ),
        "terminal-at-last-empty": (
            b"Terminal-at: 2025-01-01T00:00:00Z\n"
            b"Terminal-at:\n"
        ),
        "migration-evidence-empty": b"V1-Migration-Evidence:\n",
        "migration-evidence-duplicate": (
            b"V1-Migration-Evidence: first proof\n"
            b"V1-Migration-Evidence: second proof\n"
        ),
        "migration-evidence-last-empty": (
            b"V1-Migration-Evidence: first proof\n"
            b"V1-Migration-Evidence:\n"
        ),
    }
    for case, conflicting_fields in cases.items():
        root = tmp_path / case
        work_items = root / "work-items"
        sources = [
            work_items / "bugs" / "first.md",
            work_items / "decisions" / "second.md",
        ]
        sources[0].parent.mkdir(parents=True, exist_ok=True)
        sources[1].parent.mkdir(parents=True, exist_ok=True)
        sources[0].write_bytes(_pre_v1_terminal_record("fixed", "first"))
        sources[1].write_bytes(
            _pre_v1_terminal_record("dropped", "second")
            + b"\n"
            + conflicting_fields
        )
        inventory = root / ".scratch" / "inventory.json"
        receipt = root / ".scratch" / "receipt.json"
        payload = _denied_terminalization_inventory(work_items, inventory)
        assert len(payload["rows"]) == 2
        before = {path: path.read_bytes() for path in sources}

        result = run_cli(
            "terminalize-v1",
            "--root",
            str(work_items),
            "--inventory",
            str(inventory),
            "--terminal-at",
            "2026-08-01T00:00:00Z",
            "--authorization-marker",
            "operator-authorized-v1-terminalization",
            "--receipt",
            str(receipt),
        )

        assert result.returncode == 1, case
        assert "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING" in result.stdout, case
        assert {path: path.read_bytes() for path in sources} == before, case
        assert not receipt.exists(), case


def test_v1_terminalization_preserves_existing_detail_and_evidence_fields(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    work_items = root / "work-items"
    bug = work_items / "bugs" / "historic-bug.md"
    decision = work_items / "decisions" / "historic-decision.md"
    bug.parent.mkdir(parents=True, exist_ok=True)
    decision.parent.mkdir(parents=True, exist_ok=True)
    originals = {
        bug: (
            _pre_v1_terminal_record("fixed", "Historic bug")
            + b"\nResolution: Historical issue was corrected.\n"
        ),
        decision: (
            _pre_v1_terminal_record("dropped", "Historic decision")
            + b"\nEvidence: Historical decision record.\n"
        ),
    }
    for path, data in originals.items():
        path.write_bytes(data)
    hashes = {
        path: hashlib.sha256(data).hexdigest() for path, data in originals.items()
    }
    inventory = root / ".scratch" / "inventory.json"
    receipt = root / ".scratch" / "receipt.json"
    _denied_terminalization_inventory(work_items, inventory)

    result = run_cli(
        "terminalize-v1",
        "--root",
        str(work_items),
        "--inventory",
        str(inventory),
        "--terminal-at",
        "2026-08-01T00:00:00Z",
        "--authorization-marker",
        "operator-authorized-v1-terminalization",
        "--receipt",
        str(receipt),
    )
    assert result.returncode == 0, result.stdout
    for path, before in originals.items():
        after = path.read_bytes()
        assert after.startswith(before)
        text = after.decode()
        status = "fixed" if path == bug else "dropped"
        assert text.count("Terminal-at: 2026-08-01T00:00:00Z") == 1
        assert text.count(
            "V1-Migration-Evidence: Historical terminal time is unknown; "
            f"preserved pre-V1 input SHA-256 `{hashes[path]}`; original terminal "
            f"status `{status}`; explicit operator-authorized V1 migration."
        ) == 1
    bug_text = bug.read_text(encoding="utf-8")
    assert bug_text.count("Resolution: Historical issue was corrected.") == 1
    assert bug_text.count("\nResolution:") == 1
    assert bug_text.count("\nEvidence:") == 1
    decision_text = decision.read_text(encoding="utf-8")
    assert decision_text.count("Evidence: Historical decision record.") == 1
    assert decision_text.count("\nEvidence:") == 1
    assert decision_text.count("\nRationale:") == 1


def test_v1_terminalization_mid_batch_failure_rolls_back_every_byte(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    work_items = root / "work-items"
    sources = [
        work_items / "bugs" / "first.md",
        work_items / "decisions" / "second.md",
    ]
    for path, status in zip(sources, ("fixed", "dropped")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_pre_v1_terminal_record(status, path.stem))
    inventory = root / ".scratch" / "inventory.json"
    receipt = root / ".scratch" / "receipt.json"
    _denied_terminalization_inventory(work_items, inventory)
    before = {path: path.read_bytes() for path in sources}

    try:
        module.terminalize_v1_inventory(
            root,
            inventory,
            terminal_at="2026-08-01T00:00:00Z",
            authorization_marker="operator-authorized-v1-terminalization",
            receipt_path=receipt,
            inject_failure_after=1,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"
    else:
        raise AssertionError("injected mid-batch failure was not surfaced")
    assert {path: path.read_bytes() for path in sources} == before
    assert not receipt.exists()


def _seed_legacy_backlog(
    root: Path, slug: str, files: dict[str, bytes]
) -> tuple[Path, dict[str, bytes]]:
    source = root / "work-items" / "backlog" / slug
    for relative, data in files.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return source, {relative: data for relative, data in files.items()}


def test_convert_legacy_candidate_preserves_sources_hashes_and_readme(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "legacy-admitted"
    sources = {
        "brief.md": b"# Accepted brief\n\nEpic: none\nDepends-on: none\n",
        "roadmap.md": b"# Accepted roadmap\n\nPriority: medium\n",
    }
    source, before = _seed_legacy_backlog(root, slug, sources)
    module.refresh_readme(root, allow_marker_bootstrap=True)
    candidate = (
        "status: candidate\n"
        "Task: Fix the current Python completion-oracle owner.\n"
        "Next action: Reverify current scope before delivery.\n"
        "Epic: none\n"
        "Depends-on: none\n"
    ).encode()

    target = module.convert_legacy_candidate(root, slug, candidate)

    assert target == root / "work-items" / "backlog" / f"{slug}.md"
    assert target.is_file() and not source.exists()
    converted = target.read_bytes()
    assert converted.startswith(candidate)
    for relative, data in before.items():
        assert data in converted
        assert f"### `{relative}`".encode() in converted
        assert hashlib.sha256(data).hexdigest().encode() in converted
        assert f"Source byte length: `{len(data)}`".encode() in converted
    entries = [
        entry
        for entry in module.collect_readme_entries(root)
        if entry.logical_reference == f"work-item:{slug}"
    ]
    assert len(entries) == 1 and entries[0].section == "Next actions"
    module.audit(root)


def test_legacy_appendix_fields_are_non_authoritative_and_byte_safe(
    tmp_path: Path,
) -> None:
    module = load_module()
    exact_legacy = (
        b"# Accepted roadmap\n\n"
        b"- status: **ADMITTED to backlog**, not started\n"
        b"Task: legacy wording must remain evidence only\n"
    )
    candidate = (
        b"status: candidate\n"
        b"Task: Fix the current Python completion-oracle owner.\n"
        b"Next action: Reverify current scope before delivery.\n"
        b"Epic: none\n"
        b"Depends-on: none\n"
    )

    root = tmp_path / "success"
    slug = "completion-oracle-reachability"
    source, before = _seed_legacy_backlog(root, slug, {"roadmap.md": exact_legacy})
    module.refresh_readme(root, allow_marker_bootstrap=True)
    target = module.convert_legacy_candidate(root, slug, candidate)

    converted = target.read_bytes()
    assert not source.exists()
    assert exact_legacy in converted
    assert hashlib.sha256(exact_legacy).hexdigest().encode() in converted
    assert module._parse_fields(converted.decode("utf-8"))["status"] == "candidate"
    entries = [
        entry
        for entry in module.collect_readme_entries(root)
        if entry.logical_reference == f"work-item:{slug}"
    ]
    assert len(entries) == 1 and entries[0].section == "Next actions"
    assert (root / "work-items" / "README.md").read_bytes() == module.render_readme_bytes(root)

    rollback_root = tmp_path / "rollback"
    rollback_source, rollback_before = _seed_legacy_backlog(
        rollback_root, slug, {"roadmap.md": exact_legacy}
    )
    module.refresh_readme(rollback_root, allow_marker_bootstrap=True)
    readme_before = (rollback_root / "work-items" / "README.md").read_bytes()
    try:
        module.convert_legacy_candidate(
            rollback_root,
            slug,
            candidate,
            inject_readme_failure=True,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-README-STALE"
    else:
        raise AssertionError("injected legacy conversion failure returned success")
    assert rollback_source.is_dir()
    assert (rollback_source / "roadmap.md").read_bytes() == rollback_before["roadmap.md"]
    assert not (rollback_root / "work-items" / "backlog" / f"{slug}.md").exists()
    assert (rollback_root / "work-items" / "README.md").read_bytes() == readme_before


def test_field_parser_respects_fenced_markdown_boundary_and_fails_closed(
    tmp_path: Path,
) -> None:
    del tmp_path
    module = load_module()
    text = (
        "status: candidate\n"
        "Task: authoritative task\n"
        "```markdown\n"
        "status: fixed\n"
        "Task: preserved evidence\n"
        "```\n"
        "~~~text\n"
        "status: dropped\n"
        "~~~~\n"
        "Next action: deliver\n"
    )
    assert module._parse_fields(text) == {
        "status": "candidate",
        "task": "authoritative task",
        "next action": "deliver",
    }

    for malformed in (
        "status: candidate\n```markdown\nstatus: fixed\n",
        "status: candidate\n~~~text\nstatus: dropped\n````\n",
    ):
        try:
            module._parse_fields(malformed)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-MARKDOWN-INVALID"
        else:
            raise AssertionError("unterminated fenced record was accepted")


def _assert_invalid_legacy_candidate_header(
    tmp_path: Path,
    case: str,
    candidate: bytes,
) -> None:
    module = load_module()
    root = tmp_path / case
    slug = f"legacy-header-{case}"
    source, before = _seed_legacy_backlog(
        root,
        slug,
        {
            "brief.md": b"# Accepted brief\n\nPreserve exact bytes.\n",
            "roadmap.md": (
                b"# Accepted roadmap\n\n"
                b"- status: **ADMITTED to backlog**, not started\n"
            ),
        },
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    readme = root / "work-items" / "README.md"
    readme_before = readme.read_bytes()
    target = root / "work-items" / "backlog" / f"{slug}.md"

    try:
        module.convert_legacy_candidate(root, slug, candidate)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-STATUS-INVALID", case
    else:
        raise AssertionError(f"{case} canonical candidate header was accepted")

    assert source.is_dir() and not target.exists(), case
    assert {
        path.relative_to(source).as_posix(): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file()
    } == before, case
    assert readme.read_bytes() == readme_before, case
    assert not list(target.parent.glob(f".{slug}.legacy-candidate.*")), case


def test_convert_legacy_candidate_rejects_missing_canonical_status_before_write(
    tmp_path: Path,
) -> None:
    _assert_invalid_legacy_candidate_header(
        tmp_path,
        "missing-status",
        b"Task: Candidate without status.\nNext action: Reject before mutation.\n",
    )


def test_convert_legacy_candidate_rejects_duplicate_canonical_status_before_write(
    tmp_path: Path,
) -> None:
    cases = {
        "duplicate-status": (
            b"status: candidate\n"
            b"status: candidate\n"
            b"Task: Duplicate status must fail closed.\n"
            b"Next action: Reject before mutation.\n"
        ),
        "conflicting-status": (
            b"status: candidate\n"
            b"status: fixed\n"
            b"Task: Conflicting status must fail closed.\n"
            b"Next action: Reject before mutation.\n"
        ),
        "post-fence-status": (
            b"status: candidate\n"
            b"Task: Lifecycle field after evidence must fail closed.\n"
            b"```markdown\n"
            b"status: preserved evidence\n"
            b"```\n"
            b"status: fixed\n"
        ),
    }
    for case, candidate in cases.items():
        _assert_invalid_legacy_candidate_header(tmp_path, case, candidate)


def test_convert_legacy_candidate_rejects_malformed_canonical_status_before_write(
    tmp_path: Path,
) -> None:
    _assert_invalid_legacy_candidate_header(
        tmp_path,
        "malformed-status",
        (
            b"status candidate\n"
            b"Task: Malformed status must fail closed.\n"
            b"Next action: Reject before mutation.\n"
        ),
    )
    _assert_invalid_legacy_candidate_header(
        tmp_path,
        "valid-plus-malformed-status",
        (
            b"status: candidate\n"
            b"status candidate\n"
            b"Task: Additional malformed status must fail closed.\n"
            b"Next action: Reject before mutation.\n"
        ),
    )


def test_convert_legacy_candidate_accepts_one_real_canonical_header(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "valid-real-header"
    slug = "completion-oracle-reachability"
    exact_legacy = (
        b"# Accepted roadmap\n\n"
        b"- status: **ADMITTED to backlog**, not started\n"
    )
    source, _before = _seed_legacy_backlog(
        root,
        slug,
        {"roadmap.md": exact_legacy},
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    candidate = (
        b"---\n"
        b"status: candidate\n"
        b"created: 2026-07-31\n"
        b"source: legacy-backlog-conversion\n"
        b"---\n\n"
        b"# Completion-oracle reachability\n\n"
        b"Task: Correct the current completion-oracle owner.\n"
        b"Next action: Reverify admitted scope.\n"
    )

    target = module.convert_legacy_candidate(root, slug, candidate)

    converted = target.read_bytes()
    assert not source.exists() and converted.startswith(candidate)
    assert exact_legacy in converted
    assert hashlib.sha256(exact_legacy).hexdigest().encode() in converted
    assert module._parse_fields(converted.decode("utf-8"))["status"] == "candidate"
    module.audit(root)


def test_convert_legacy_candidate_does_not_add_non_status_header_policy(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "unrelated-body-content"
    slug = "legacy-unrelated-body-content"
    source, _before = _seed_legacy_backlog(
        root,
        slug,
        {"brief.md": b"# Preserved evidence\n"},
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    candidate = (
        b"status: candidate\n"
        b"Task: First retained task value.\n"
        b"Task: Second retained task value.\n"
        b"Next action: Verify the admitted status contract.\n\n"
        b"# Notes\n\n"
        b"status candidate is ordinary body text without field syntax.\n"
    )

    target = module.convert_legacy_candidate(root, slug, candidate)

    assert not source.exists() and target.read_bytes().startswith(candidate)
    assert module._parse_fields(target.read_text(encoding="utf-8"))["status"] == "candidate"
    module.audit(root)


def test_convert_legacy_candidate_accepts_safe_dotted_slug_and_keeps_header_gate(
    tmp_path: Path,
) -> None:
    module = load_module()
    slug = "2026-07-19-model-ranking-aa-coding-index-v1.1"
    candidate = (
        b"status: candidate\n"
        b"Task: Re-rank the admitted model index.\n"
        b"Next action: Verify the dotted canonical identity.\n"
    )

    root = tmp_path / "valid-dotted"
    source, before = _seed_legacy_backlog(
        root,
        slug,
        {"brief.md": b"- id: 2026-07-19-model-ranking-aa-coding-index-v1.1\n"},
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    target = module.convert_legacy_candidate(root, slug, candidate)

    assert target.name == f"{slug}.md" and not source.exists()
    assert before["brief.md"] in target.read_bytes()
    assert module.resolve_category(root, f"work-item:{slug}") == target.resolve()
    module.audit(root)

    invalid_header_root = tmp_path / "dotted-invalid-header"
    invalid_source, invalid_before = _seed_legacy_backlog(
        invalid_header_root,
        slug,
        {"brief.md": before["brief.md"]},
    )
    module.refresh_readme(invalid_header_root, allow_marker_bootstrap=True)
    readme_before = (invalid_header_root / "work-items" / "README.md").read_bytes()
    try:
        module.convert_legacy_candidate(
            invalid_header_root,
            slug,
            b"Task: Missing canonical status.\nNext action: Reject before mutation.\n",
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-STATUS-INVALID"
    else:
        raise AssertionError("dotted slug bypassed the canonical candidate-header gate")
    assert invalid_source.is_dir()
    assert (invalid_source / "brief.md").read_bytes() == invalid_before["brief.md"]
    assert not (invalid_source.parent / f"{slug}.md").exists()
    assert (invalid_header_root / "work-items" / "README.md").read_bytes() == readme_before


def test_invalid_dotted_slug_grammar_fails_before_conversion_mutation(
    tmp_path: Path,
) -> None:
    module = load_module()
    candidate = (
        b"status: candidate\n"
        b"Task: Reject unsafe identity.\n"
        b"Next action: Preserve source and README.\n"
    )
    invalid_slugs = (
        ".leading",
        "trailing.",
        "double..dot",
        "../traversal",
        "path/segment",
        r"path\segment",
        "Uppercase",
        "under_score",
        "unsafe space",
        "unsafe@char",
    )
    for index, slug in enumerate(invalid_slugs):
        root = tmp_path / f"invalid-{index}"
        sentinel_slug = f"preserved-source-{index}"
        source, _before = _seed_legacy_backlog(
            root,
            sentinel_slug,
            {"brief.md": f"preserve {slug}\n".encode()},
        )
        module.refresh_readme(root, allow_marker_bootstrap=True)
        work_items = root / "work-items"
        state_before = {
            path.relative_to(work_items).as_posix(): path.read_bytes()
            for path in work_items.rglob("*")
            if path.is_file()
        }
        try:
            module.convert_legacy_candidate(root, slug, candidate)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-INVALID-SLUG", slug
        else:
            raise AssertionError(f"unsafe dotted slug was accepted: {slug!r}")
        assert source.is_dir(), slug
        assert {
            path.relative_to(work_items).as_posix(): path.read_bytes()
            for path in work_items.rglob("*")
            if path.is_file()
        } == state_before, slug
        assert not list(source.parent.glob(f".{sentinel_slug}.legacy-candidate.*")), slug


def test_public_slug_predicate_is_the_mutation_grammar_owner(tmp_path: Path) -> None:
    del tmp_path
    module = load_module()
    for slug in (
        "a",
        "legacy-valid-",
        "2026-07-19-model-ranking-aa-coding-index-v1.1",
        "safe.dot-segment",
    ):
        assert module.is_valid_slug(slug), slug
        module._validate_slug(slug)
    for slug in (
        "",
        ".leading",
        "trailing.",
        "double..dot",
        "Uppercase",
        "under_score",
        "path/segment",
        r"path\segment",
        "../traversal",
        "unsafe@char",
    ):
        assert not module.is_valid_slug(slug), slug
        try:
            module._validate_slug(slug)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-INVALID-SLUG", slug
        else:
            raise AssertionError(f"mutation validator diverged from public predicate: {slug!r}")


def test_audit_rejects_noncanonical_physical_slug(tmp_path: Path) -> None:
    module = load_module()
    invalid_slug = "2026-06-19-arch-layering-runtime-laws-D"
    cases = {
        "backlog": lambda root: write(
            root / "work-items" / "backlog" / f"{invalid_slug}.md",
            "Status: candidate\nTask: invalid\nNext action: reject\n",
        ),
        "active": lambda root: write(
            root / "work-items" / "active" / invalid_slug / "status.md",
            quick_status(),
        ),
        "work-item-archive": lambda root: write(
            root / "work-items" / "archive" / "2026-07" / invalid_slug / "closure.md",
            "Closed: 2026-07-31\n",
        ),
        "flat-current": lambda root: write(
            root / "work-items" / "decisions" / f"{invalid_slug}.md",
            "status: accepted\n",
        ),
        "flat-archive": lambda root: write(
            root
            / "work-items"
            / "decisions"
            / "archive"
            / "2026-07"
            / f"{invalid_slug}.md",
            "status: dropped\nTerminal-at: 2026-07-31T00:00:00Z\nRationale: done\n",
        ),
    }
    for case, seed in cases.items():
        root = tmp_path / case
        seed(root)
        try:
            module.audit_categories(root)
        except module.LifecycleError as exc:
            expected = (
                "WI-INVALID-SLUG"
                if case in {"backlog", "active", "flat-current"}
                else "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"
            )
            assert exc.failure_id == expected, case
        else:
            raise AssertionError(f"audit accepted a noncanonical {case} slug")

    valid_root = tmp_path / "valid-neighbor"
    valid_slug = "2026-08-11-valid-neighbor"
    write(
        valid_root / "work-items" / "decisions" / f"{valid_slug}.md",
        _current_decision_record(valid_slug),
    )
    module.audit_categories(valid_root)


def test_audit_accepts_only_canonical_top_level_roots_and_root_files(tmp_path: Path) -> None:
    module = load_module()
    work_items = tmp_path / "work-items"
    canonical_roots = {"backlog", "active", "archive"}
    canonical_roots.update(
        category.current_root
        for category in module.CATEGORIES.values()
        if category.current_kind == "flat"
    )
    for name in canonical_roots:
        (work_items / name).mkdir(parents=True)
    write(work_items / "README.md", "# Generated view\n")
    write(work_items / "index.md", "# Compatibility view\n")

    assert module.audit_categories(tmp_path) == ()


def test_audit_rejects_unknown_top_level_directory(tmp_path: Path) -> None:
    module = load_module()
    (tmp_path / "work-items" / "unknown-category").mkdir(parents=True)

    try:
        module.audit_categories(tmp_path)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-UNKNOWN-ROOT"
        assert "unknown-category" in str(exc)
    else:
        raise AssertionError("audit accepted an unknown top-level work-items directory")


def test_no_contract_preserves_linked_repository_and_work_items_read_compatibility(
    tmp_path: Path,
) -> None:
    module = load_module()
    repository = tmp_path / "repository"
    (repository / "work-items").mkdir(parents=True)
    repository_link = tmp_path / "repository-link"
    work_items_link_repository = tmp_path / "work-items-link-repository"
    work_items_target = tmp_path / "work-items-target"
    work_items_target.mkdir()
    try:
        os.symlink(repository, repository_link, target_is_directory=True)
        work_items_link_repository.mkdir()
        os.symlink(
            work_items_target,
            work_items_link_repository / "work-items",
            target_is_directory=True,
        )
    except OSError as exc:
        if os.name == "nt":
            import pytest

            pytest.skip(f"symlink creation unavailable: {exc}")
        raise

    assert module._work_items_root(repository_link) == repository / "work-items"
    assert module._work_items_root(work_items_link_repository).resolve() == work_items_target


def test_contract_unknown_root_rejects_lifecycle_and_read_model_before_work_items_mutation(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    write_root_contract(root, {})
    (root / "work-items" / "unknown-category").mkdir()
    candidate = b"Status: candidate\nTask: reject unknown root\nNext action: none\n"

    for operation in (
        lambda: module.create_candidate(root, "unknown-root-candidate", candidate),
        lambda: module.refresh_readme(root),
        lambda: module.audit_categories(root),
    ):
        try:
            operation()
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-UNKNOWN-ROOT"
        else:
            raise AssertionError("contracted unknown root reached a lifecycle or read-model operation")
        assert not (root / "work-items" / "backlog").exists()
        assert not (root / "work-items" / "README.md").exists()


def test_unknown_root_validation_has_one_topology_owner(tmp_path: Path) -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    audit_start = source.index("def audit_categories(")
    audit_end = source.index("\ndef audit(", audit_start)
    audit_source = source[audit_start:audit_end]

    assert source.count("def assert_known_top_level_roots(") == 1
    assert source.count('"WI-CATEGORY-UNKNOWN-ROOT"') == 1
    assert "topology.assert_known_top_level_roots()" in audit_source
    assert "work_items.iterdir()" not in audit_source


def test_root_contract_topology_is_shared_by_audit_close_reopen_and_refresh(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    declared = ("repair-receipts", "status-repair-receipts")
    write_root_contract(root, {name: {"kind": "flat-json"} for name in declared})
    for name in declared:
        write(root / "work-items" / name / "receipt.json", "{}\n")

    slug = "contract-topology"
    seed_active(module, root, slug)
    module.audit_categories(root)

    instant = "2026-09-01T00:00:00Z"
    write_empty_bug_dispositions(root, slug, instant)
    archived = module.close_item(root, slug, closure(instant).encode(), instant)
    module.audit(root)
    successor = module.reopen_item(
        root,
        slug,
        "contract-topology-successor",
        staged_status(slug).encode(),
    )
    module.audit(root)
    first_readme = (root / "work-items" / "README.md").read_bytes()
    module.refresh_readme(root)

    assert archived == root / "work-items" / "archive" / "2026-09" / slug
    assert successor == root / "work-items" / "active" / "contract-topology-successor"
    assert (root / "work-items" / "README.md").read_bytes() == first_readme
    assert all((root / "work-items" / name / "receipt.json").is_file() for name in declared)


def test_root_contract_has_one_shared_documentation_owner_and_pack_pointers(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    shared = root / "shared" / "references" / "work-items-root-contract.md"
    shared_text = shared.read_text(encoding="utf-8")
    for token in (
        "ProjectTopology",
        '"version": 2',
        "auxiliaryRoots",
        "flat-json",
        "MUST NOT be redeclared",
        "non-reparse",
        "audit, close, reopen",
        "WI-CATEGORY-ROOT-CONTRACT-INVALID",
    ):
        assert token in shared_text

    pointer = "work-items-root-contract.md"
    for relative in (
        "shared/references/README.md",
        "docs/work-item-execution-tracking.md",
        "references-codex/repository-task-memory.md",
        "references-claude/repository-task-memory.md",
    ):
        assert pointer in (root / relative).read_text(encoding="utf-8")


def test_root_contract_does_not_admit_undeclared_root(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    write_root_contract(root, {"repair-receipts": {"kind": "flat-json"}})
    (root / "work-items" / "repair-receipts").mkdir()
    (root / "work-items" / "performance").mkdir()

    try:
        module.audit_categories(root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-UNKNOWN-ROOT"
        assert "performance" in str(exc)
    else:
        raise AssertionError("contract admitted an undeclared work-items root")


def test_root_contract_rejects_lifecycle_and_read_model_root_collisions(
    tmp_path: Path,
) -> None:
    module = load_module()
    reserved_roots = (
        "active",
        "archive",
        "backlog",
        "bugs",
        "decisions",
        "epics",
        "legacy-ledger-historical-dispositions",
        "lessons",
        "roadmaps",
    )

    for name in reserved_roots:
        root = tmp_path / name
        write_root_contract(root, {name: {"kind": "flat-json"}})
        try:
            module._resolve_project_topology(root)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-ROOT-CONTRACT-INVALID", name
            assert name in str(exc), name
        else:
            raise AssertionError(f"root contract admitted reserved root: {name}")


def test_root_contract_collision_fails_before_candidate_mutation(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    write_root_contract(root, {"backlog": {"kind": "flat-json"}})

    try:
        module.create_candidate(
            root,
            "collision-must-not-mutate",
            b"Status: candidate\nTask: reject collision\nNext action: none\n",
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-ROOT-CONTRACT-INVALID"
    else:
        raise AssertionError("candidate mutation accepted a colliding root contract")

    assert not (root / "work-items" / "backlog").exists()
    assert not (root / "work-items" / "README.md").exists()


def test_root_contract_rejects_generated_readme_alias_before_refresh_mutation(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    write_root_contract(root, {"readme.md": {"kind": "flat-json"}})

    try:
        module.refresh_readme(root, allow_marker_bootstrap=True)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-ROOT-CONTRACT-INVALID"
        assert "generated README" in str(exc)
    else:
        raise AssertionError("root contract admitted generated README alias")

    assert not (root / "work-items" / "README.md").exists()
    assert not (root / "work-items" / "readme.md").exists()


def test_root_contract_rejects_malformed_and_unconfined_roots(tmp_path: Path) -> None:
    module = load_module()
    cases = {
        "malformed-json": "{\n",
        "wrong-schema": json.dumps(
            {"schema": "other", "version": 2, "auxiliaryRoots": {}}
        ),
        "wrong-version": json.dumps(
            {"schema": "work-items-root-contract", "version": 1, "auxiliaryRoots": {}}
        ),
        "wrong-roots-shape": json.dumps(
            {"schema": "work-items-root-contract", "version": 2, "auxiliaryRoots": []}
        ),
        "wrong-kind": json.dumps(
            {
                "schema": "work-items-root-contract",
                "version": 2,
                "auxiliaryRoots": {"receipts": {"kind": "directory"}},
            }
        ),
        "traversal": json.dumps(
            {
                "schema": "work-items-root-contract",
                "version": 2,
                "auxiliaryRoots": {"../escape": {"kind": "flat-json"}},
            }
        ),
        "absolute-posix": json.dumps(
            {
                "schema": "work-items-root-contract",
                "version": 2,
                "auxiliaryRoots": {"/absolute": {"kind": "flat-json"}},
            }
        ),
        "absolute-windows": json.dumps(
            {
                "schema": "work-items-root-contract",
                "version": 2,
                "auxiliaryRoots": {"C:\\absolute": {"kind": "flat-json"}},
            }
        ),
    }
    for name, contract in cases.items():
        root = tmp_path / name
        write(root / "work-items" / "root-contract.json", contract + "\n")
        try:
            module.audit_categories(root)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-ROOT-CONTRACT-INVALID", name
        else:
            raise AssertionError(f"invalid root contract passed: {name}")


def test_root_contract_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    module = load_module()
    cases = {
        "schema": '{"schema":"work-items-root-contract","schema":"work-items-root-contract","version":2,"auxiliaryRoots":{}}',
        "version": '{"schema":"work-items-root-contract","version":2,"version":2,"auxiliaryRoots":{}}',
        "auxiliary-roots": '{"schema":"work-items-root-contract","version":2,"auxiliaryRoots":{},"auxiliaryRoots":{}}',
        "auxiliary-root-name": '{"schema":"work-items-root-contract","version":2,"auxiliaryRoots":{"receipts":{"kind":"flat-json"},"receipts":{"kind":"flat-json"}}}',
    }

    for name, contract in cases.items():
        root = tmp_path / name
        write(root / "work-items" / "root-contract.json", contract + "\n")
        try:
            module._resolve_project_topology(root)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-ROOT-CONTRACT-INVALID", name
        else:
            raise AssertionError(f"duplicate JSON key passed: {name}")


def test_root_contract_rejects_linked_contract_and_repository_root(tmp_path: Path) -> None:
    module = load_module()
    target_contract = tmp_path / "contract-target.json"
    write_root_contract(tmp_path / "contract-source", {})
    shutil.copyfile(
        tmp_path / "contract-source" / "work-items" / "root-contract.json",
        target_contract,
    )
    linked_contract_root = tmp_path / "linked-contract"
    (linked_contract_root / "work-items").mkdir(parents=True)
    try:
        os.symlink(target_contract, linked_contract_root / "work-items" / "root-contract.json")
    except OSError as exc:
        if os.name == "nt":
            import pytest

            pytest.skip(f"symlink creation unavailable: {exc}")
        raise
    try:
        module.audit_categories(linked_contract_root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-ROOT-CONTRACT-INVALID"
    else:
        raise AssertionError("linked root contract passed")

    linked_auxiliary_root = tmp_path / "linked-auxiliary"
    write_root_contract(
        linked_auxiliary_root,
        {"repair-receipts": {"kind": "flat-json"}},
    )
    auxiliary_target = tmp_path / "auxiliary-target"
    auxiliary_target.mkdir()
    os.symlink(
        auxiliary_target,
        linked_auxiliary_root / "work-items" / "repair-receipts",
        target_is_directory=True,
    )
    try:
        module.audit_categories(linked_auxiliary_root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-ROOT-CONTRACT-INVALID"
    else:
        raise AssertionError("linked contract-declared root passed")

    repository_target = tmp_path / "repository-target"
    write_root_contract(repository_target, {})
    repository_link = tmp_path / "repository-link"
    os.symlink(repository_target, repository_link, target_is_directory=True)
    try:
        module.audit_categories(repository_link)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-LIFECYCLE-LOCK-IDENTITY"
    else:
        raise AssertionError("linked repository root passed")


def test_noncanonical_archive_is_physical_read_compat_only(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-06-13-batchA1-decisions-deps"
    archived = root / "work-items" / "archive" / "2026-06" / slug
    write(archived / "closure.md", "Closed: 2026-06-13\nOutcome: delivered\n")
    write(archived / "status.md", "status: completed\n")
    assert module.audit_categories(root) == (
        f"archive/2026-06/{slug}",
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    result = run_cli("audit", "--root", str(root))
    assert result.returncode == 0, result.stdout
    assert f"WI-LEGACY-READ-COMPAT archive/2026-06/{slug}" in result.stdout
    try:
        module.resolve_category(root, f"work-item:{slug}")
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-INVALID-SLUG"
    else:
        raise AssertionError("legacy archive became a logical resolver alias")


def test_noncanonical_flat_archive_requires_unique_terminal_month(tmp_path: Path) -> None:
    module = load_module()
    slug = "Legacy-Decision"
    terminal = (
        "status: reverted\n"
        "Terminal-at: 2026-06-13T00:00:00Z\n"
        "Rationale: retired\n"
        "Evidence: historical decision\n"
    )
    valid_root = tmp_path / "valid"
    valid = (
        valid_root
        / "work-items"
        / "decisions"
        / "archive"
        / "2026-06"
        / f"{slug}.md"
    )
    write(valid, terminal)
    assert module.audit_categories(valid_root) == (
        f"decisions/archive/2026-06/{slug}.md",
    )
    try:
        module.resolve_category(valid_root, f"decision:{slug}")
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-INVALID-SLUG"
    else:
        raise AssertionError("noncanonical flat archive became a logical alias")

    wrong_month_root = tmp_path / "wrong-month"
    write(
        wrong_month_root
        / "work-items"
        / "decisions"
        / "archive"
        / "2026-07"
        / f"{slug}.md",
        terminal,
    )
    try:
        module.audit_categories(wrong_month_root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-ARCHIVE-MONTH-MISMATCH"
    else:
        raise AssertionError("wrong-month legacy archive was admitted")

    duplicate_root = tmp_path / "duplicate"
    for month in ("2026-06", "2026-07"):
        write(
            duplicate_root
            / "work-items"
            / "decisions"
            / "archive"
            / month
            / f"{slug}.md",
            terminal,
        )
    try:
        module.audit_categories(duplicate_root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-DUAL-LOCATION"
    else:
        raise AssertionError("duplicate legacy archive identity was admitted")


def _identity_normalization_fixture(root: Path):
    module = load_module()
    work_items = root / "work-items"
    old = "2026-06-19-arch-layering-runtime-laws-D-group-meta-C6"
    new = old.lower()
    source = work_items / "decisions" / f"{old}.md"
    write(source, _current_decision_record(old, status="accepted"))
    lineage = work_items / "decisions" / "2026-07-07-d1-amendment.md"
    write(
        lineage,
        _current_decision_record(
            "2026-07-07-d1-amendment",
            status="accepted",
            body=(
                f"Lineage: {old}; Related: decision:{old}\n"
                f"```text\nhistorical evidence: {old}\n```\n"
            ),
        ),
    )
    physical = work_items / "epics" / "current-link.md"
    write(
        physical,
        f"- id: current-link\n- status: active\n"
        f"[decision](../decisions/{old}.md?view=full#d1)\n",
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    inventory = root / ".scratch" / "identity-normalization.json"
    receipt = root / ".scratch" / "identity-normalization-receipt.json"
    module.write_current_identity_normalization_inventory(
        root, "decision", source.relative_to(root).as_posix(), new, inventory
    )
    return module, work_items, old, new, source, lineage, physical, inventory, receipt


def test_normalize_current_identity_success_links_and_replay(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    module, work_items, old, new, source, lineage, physical, inventory, receipt = _identity_normalization_fixture(root)
    target, replay = module.normalize_current_identity(
        root, "decision", source.relative_to(root).as_posix(), new, inventory, receipt
    )
    assert replay is False and not module._normalization_exact_file(source)
    assert module._normalization_exact_file(target)
    target_fields = module._parse_fields(target.read_text(encoding="utf-8"))
    assert target_fields["status"] == "accepted" and target_fields["id"] == new
    lineage_text = lineage.read_text(encoding="utf-8")
    assert f"Lineage: {new}; Related: decision:{new}" in lineage_text
    assert f"historical evidence: {old}" in lineage_text
    assert f"../decisions/{new}.md?view=full#d1" in physical.read_text(encoding="utf-8")
    assert module.resolve_category(root, f"decision:{new}") == target.resolve()
    module.audit(root)
    replay_target, replay = module.normalize_current_identity(
        root, "decision", source.relative_to(root).as_posix(), new, inventory, receipt
    )
    assert replay is True and replay_target == target


def test_normalize_current_identity_rollback_matrix(tmp_path: Path) -> None:
    for injection in ("after-rewrites", "after-move", "after-readme"):
        root = tmp_path / injection
        module, work_items, _old, new, source, _lineage, _physical, inventory, receipt = _identity_normalization_fixture(root)
        before = {path.relative_to(work_items).as_posix(): path.read_bytes() for path in work_items.rglob("*") if path.is_file()}
        try:
            module.normalize_current_identity(
                root, "decision", source.relative_to(root).as_posix(), new,
                inventory, receipt, inject_failure_at=injection,
            )
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-IDENTITY-NORMALIZE-ROLLBACK", injection
        else:
            raise AssertionError(f"injected failure settled: {injection}")
        assert {path.relative_to(work_items).as_posix(): path.read_bytes() for path in work_items.rglob("*") if path.is_file()} == before
        assert source.is_file() and not receipt.exists()


def test_normalize_current_identity_inventory_collision_and_source_gates(tmp_path: Path) -> None:
    module = load_module()
    archive_root = tmp_path / "archive-source"
    archived = archive_root / "work-items" / "decisions" / "archive" / "2026-06" / "Legacy.md"
    write(archived, "status: reverted\nTerminal-at: 2026-06-01T00:00:00Z\nRationale: done\nEvidence: test\n")
    try:
        module.write_current_identity_normalization_inventory(
            archive_root, "decision", "work-items/decisions/archive/2026-06/Legacy.md", "legacy",
            archive_root / ".scratch" / "i.json",
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-IDENTITY-NORMALIZE-SOURCE"
    else:
        raise AssertionError("archive source was admitted")

    for case in ("stale-inventory", "collision", "duplicate"):
        root = tmp_path / case
        module, work_items, _old, new, source, _lineage, _physical, inventory, receipt = _identity_normalization_fixture(root)
        if case == "stale-inventory":
            payload = json.loads(inventory.read_text(encoding="utf-8"))
            payload["rows"].pop()
            inventory.write_text(json.dumps(payload), encoding="utf-8")
        elif case == "collision":
            write(
                work_items / "decisions" / "archive" / "2026-06" / f"{new}.md",
                "status: reverted\nTerminal-at: 2026-06-01T00:00:00Z\nRationale: done\nEvidence: test\n",
            )
        else:
            write(
                work_items / "decisions" / "archive" / "2026-06" / source.name,
                "status: reverted\nTerminal-at: 2026-06-01T00:00:00Z\nRationale: done\nEvidence: test\n",
            )
        before = source.read_bytes()
        try:
            module.normalize_current_identity(
                root, "decision", source.relative_to(root).as_posix(), new, inventory, receipt
            )
        except module.LifecycleError as exc:
            expected = "WI-IDENTITY-NORMALIZE-INVENTORY" if case == "stale-inventory" else "WI-CATEGORY-DUAL-LOCATION"
            assert exc.failure_id == expected, case
        else:
            raise AssertionError(f"{case} was admitted")
        assert source.read_bytes() == before and not receipt.exists()

    non_utf = tmp_path / "non-utf8"
    module, work_items, _old, new, source, *_rest = _identity_normalization_fixture(non_utf)
    bad = work_items / "bugs" / "bad.md"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_bytes(b"\xff")
    try:
        module.write_current_identity_normalization_inventory(
            non_utf, "decision", source.relative_to(non_utf).as_posix(), new,
            non_utf / ".scratch" / "identity-normalization.json",
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-IDENTITY-NORMALIZE-INVENTORY"
    else:
        raise AssertionError("non-UTF8 current record was not fail-closed")


def test_normalize_current_identity_preserves_archive_evidence_and_rejects_mixed_replay(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "archive-physical-consumer"
    work_items = root / "work-items"
    old = "2026-08-01-Legacy-Decision"
    new = "2026-08-01-legacy-decision"
    source = work_items / "decisions" / f"{old}.md"
    write(source, _current_decision_record(old, status="accepted"))
    archived_evidence = (
        work_items / "archive" / "2026-07" / "historical-record" / "evidence.md"
    )
    write(
        archived_evidence,
        f"[historical decision](../../../decisions/{old}.md#decision)\n",
    )
    tree_before = {
        path.relative_to(work_items).as_posix(): path.read_bytes()
        for path in work_items.rglob("*")
        if path.is_file()
    }
    inventory = root / ".scratch" / "identity-normalization.json"
    try:
        module.write_current_identity_normalization_inventory(
            root,
            "decision",
            source.relative_to(root).as_posix(),
            new,
            inventory,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-IDENTITY-NORMALIZE-INVENTORY"
    else:
        raise AssertionError("immutable archive physical consumer was classified mutable")
    assert not inventory.exists()
    assert {
        path.relative_to(work_items).as_posix(): path.read_bytes()
        for path in work_items.rglob("*")
        if path.is_file()
    } == tree_before

    settled_root = tmp_path / "mixed-replay"
    (
        module,
        work_items,
        _old,
        new,
        source,
        lineage,
        _physical,
        inventory,
        receipt,
    ) = _identity_normalization_fixture(settled_root)
    target, replay = module.normalize_current_identity(
        settled_root,
        "decision",
        source.relative_to(settled_root).as_posix(),
        new,
        inventory,
        receipt,
    )
    assert replay is False and target.is_file()
    lineage.write_text(lineage.read_text(encoding="utf-8") + "drift\n", encoding="utf-8")
    try:
        module.normalize_current_identity(
            settled_root,
            "decision",
            source.relative_to(settled_root).as_posix(),
            new,
            inventory,
            receipt,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-IDENTITY-NORMALIZE-RECOVERY"
    else:
        raise AssertionError("mixed settled replay was accepted")

    source.write_text(f"id: {_old}\nstatus: accepted\n", encoding="utf-8")
    try:
        module.normalize_current_identity(
            settled_root,
            "decision",
            source.relative_to(settled_root).as_posix(),
            new,
            inventory,
            receipt,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-IDENTITY-NORMALIZE-RECOVERY"
    else:
        raise AssertionError("dual physical state with receipt was accepted")


def test_normalize_current_identity_replay_requires_complete_exact_receipt_rows(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    (
        module,
        work_items,
        _old,
        new,
        source,
        _lineage,
        _physical,
        inventory,
        receipt,
    ) = _identity_normalization_fixture(root)
    target, replay = module.normalize_current_identity(
        root,
        "decision",
        source.relative_to(root).as_posix(),
        new,
        inventory,
        receipt,
    )
    assert replay is False and target.is_file()
    canonical_receipt = json.loads(receipt.read_text(encoding="utf-8"))
    canonical_rows = canonical_receipt["rows"]
    assert len(canonical_rows) == 3

    variants = {
        "zero-of-three": [],
        "one-of-three": canonical_rows[:1],
        "two-of-three": canonical_rows[:2],
        "mixed": [
            canonical_rows[0],
            canonical_rows[1],
            {**canonical_rows[2], "afterPath": canonical_rows[1]["afterPath"]},
        ],
        "duplicate": [canonical_rows[0], canonical_rows[1], canonical_rows[1]],
        "tampered": [
            canonical_rows[0],
            {**canonical_rows[1], "afterSha256": "0" * 64},
            canonical_rows[2],
        ],
    }
    for name, rows in variants.items():
        candidate = json.loads(json.dumps(canonical_receipt))
        candidate["rows"] = rows
        receipt.write_text(json.dumps(candidate), encoding="utf-8")
        receipt_before = receipt.read_bytes()
        tree_before = {
            path.relative_to(work_items).as_posix(): path.read_bytes()
            for path in work_items.rglob("*")
            if path.is_file()
        }
        try:
            module.normalize_current_identity(
                root,
                "decision",
                source.relative_to(root).as_posix(),
                new,
                inventory,
                receipt,
            )
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-IDENTITY-NORMALIZE-RECOVERY", name
        else:
            raise AssertionError(f"incomplete/tampered receipt replayed: {name}")
        assert receipt.read_bytes() == receipt_before, name
        assert {
            path.relative_to(work_items).as_posix(): path.read_bytes()
            for path in work_items.rglob("*")
            if path.is_file()
        } == tree_before, name

    receipt.write_text(json.dumps(canonical_receipt), encoding="utf-8")
    replay_target, replay = module.normalize_current_identity(
        root,
        "decision",
        source.relative_to(root).as_posix(),
        new,
        inventory,
        receipt,
    )
    assert replay is True and replay_target == target


def test_normalize_current_identity_ignores_fenced_links_but_rewrites_live_links(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    work_items = root / "work-items"
    old = "2026-08-01-Legacy-Decision"
    new = "2026-08-01-legacy-decision"
    source = work_items / "decisions" / f"{old}.md"
    write(source, _current_decision_record(old, status="accepted"))
    current = work_items / "epics" / "current-link.md"
    write(
        current,
        f"id: current-link\nstatus: active\n"
        f"[live](../decisions/{old}.md?view=full#d1)\n"
        f"```md\n[fenced](../decisions/{old}.md?view=old#evidence)\n```\n",
    )
    archived = (
        work_items
        / "decisions"
        / "archive"
        / "2026-07"
        / "historical-evidence.md"
    )
    write(
        archived,
        "id: historical-evidence\n"
        "status: reverted\n"
        "Terminal-at: 2026-07-01T00:00:00Z\n"
        "Rationale: historical evidence\n"
        "Evidence: fenced example\n"
        f"```md\n[historical](../../{old}.md?view=old#evidence)\n```\n",
    )
    archived_before = archived.read_bytes()
    module.refresh_readme(root, allow_marker_bootstrap=True)
    inventory = root / ".scratch" / "identity-normalization.json"
    receipt = root / ".scratch" / "identity-normalization-receipt.json"
    data = module.write_current_identity_normalization_inventory(
        root,
        "decision",
        source.relative_to(root).as_posix(),
        new,
        inventory,
    )
    rows = {row["path"]: row for row in data["rows"]}
    assert rows["epics/current-link.md"]["kinds"] == ["physical-link"]
    assert "decisions/archive/2026-07/historical-evidence.md" not in rows

    target, replay = module.normalize_current_identity(
        root,
        "decision",
        source.relative_to(root).as_posix(),
        new,
        inventory,
        receipt,
    )
    assert replay is False and target.is_file()
    current_text = current.read_text(encoding="utf-8")
    assert f"[live](../decisions/{new}.md?view=full#d1)" in current_text
    assert f"[fenced](../decisions/{old}.md?view=old#evidence)" in current_text
    assert archived.read_bytes() == archived_before


def test_normalize_current_identity_rejects_invalid_paths_targets_and_reparse(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    work_items = root / "work-items"
    source = work_items / "decisions" / "Legacy.md"
    write(source, "id: Legacy\nstatus: accepted\n")
    inventory = root / ".scratch" / "identity-normalization.json"
    before = source.read_bytes()
    cases = (
        ("decisions/Legacy.md", "legacy", "WI-IDENTITY-NORMALIZE-SOURCE"),
        ("work-items/../outside.md", "legacy", "WI-IDENTITY-NORMALIZE-SOURCE"),
        (source.relative_to(root).as_posix(), "Invalid_Target", "WI-INVALID-SLUG"),
    )
    for source_arg, target_slug, expected in cases:
        try:
            module.write_current_identity_normalization_inventory(
                root, "decision", source_arg, target_slug, inventory
            )
        except module.LifecycleError as exc:
            assert exc.failure_id == expected
        else:
            raise AssertionError(f"invalid normalization input was admitted: {source_arg}")
        assert source.read_bytes() == before and not inventory.exists()

    link_root = tmp_path / "reparse"
    real = link_root / "real-work-items"
    write(real / "decisions" / "Legacy.md", "id: Legacy\nstatus: accepted\n")
    linked = link_root / "work-items"
    try:
        os.symlink(real, linked, target_is_directory=True)
    except (OSError, NotImplementedError):
        return
    try:
        module.write_current_identity_normalization_inventory(
            link_root,
            "decision",
            "work-items/decisions/Legacy.md",
            "legacy",
            link_root / ".scratch" / "identity-normalization.json",
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-IDENTITY-NORMALIZE-SOURCE"
    else:
        raise AssertionError("reparse-backed source was admitted")


def test_normalize_current_identity_cli_prepare_apply_and_replay(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    source = root / "work-items" / "decisions" / "2026-08-01-Legacy.md"
    write(
        source,
        _current_decision_record("2026-08-01-Legacy", status="accepted"),
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    inventory = root / ".scratch" / "identity-normalization.json"
    receipt = root / ".scratch" / "identity-normalization-receipt.json"
    common = (
        "normalize-current-identity",
        "--root",
        str(root),
        "--category",
        "decision",
        "--source",
        "work-items/decisions/2026-08-01-Legacy.md",
        "--target-slug",
        "2026-08-01-legacy",
        "--inventory",
        str(inventory),
    )
    prepared = run_cli(*common, "--prepare-only")
    assert prepared.returncode == 0, prepared.stdout
    assert "NORMALIZE-CURRENT-IDENTITY: INVENTORY" in prepared.stdout
    applied = run_cli(*common, "--receipt", str(receipt))
    assert applied.returncode == 0, applied.stdout
    assert "NORMALIZE-CURRENT-IDENTITY: PASS" in applied.stdout
    assert "replay=false" in applied.stdout
    replayed = run_cli(*common, "--receipt", str(receipt))
    assert replayed.returncode == 0, replayed.stdout
    assert "NORMALIZE-CURRENT-IDENTITY: PASS" in replayed.stdout
    assert "replay=true" in replayed.stdout


def test_convert_legacy_candidate_duplicate_and_failure_are_byte_rollback(
    tmp_path: Path,
) -> None:
    module = load_module()
    duplicate_root = tmp_path / "duplicate"
    slug = "legacy-duplicate"
    source, before = _seed_legacy_backlog(
        duplicate_root, slug, {"brief.md": b"preserve duplicate source\n"}
    )
    write(
        duplicate_root / "work-items" / "backlog" / f"{slug}.md",
        "Task: existing identity\nNext action: preserve\n",
    )
    module.refresh_readme(duplicate_root, allow_marker_bootstrap=True)
    readme_before = (duplicate_root / "work-items" / "README.md").read_bytes()
    try:
        module.convert_legacy_candidate(duplicate_root, slug, b"Task: replacement\n")
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-DUAL-LOCATION"
    else:
        raise AssertionError("duplicate legacy identity was converted")
    assert (source / "brief.md").read_bytes() == before["brief.md"]
    assert (duplicate_root / "work-items" / "README.md").read_bytes() == readme_before

    rollback_root = tmp_path / "rollback"
    source, before = _seed_legacy_backlog(
        rollback_root,
        slug,
        {
            "brief.md": b"preserve rollback source\n",
            "notes/design.md": b"preserve recursive rollback source\n",
        },
    )
    module.refresh_readme(rollback_root, allow_marker_bootstrap=True)
    readme_before = (rollback_root / "work-items" / "README.md").read_bytes()
    try:
        module.convert_legacy_candidate(
            rollback_root,
            slug,
            b"status: candidate\nTask: candidate\nNext action: verify\n",
            inject_readme_failure=True,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-README-STALE"
    else:
        raise AssertionError("injected conversion failure returned success")
    assert {
        path.relative_to(source).as_posix(): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file()
    } == before
    assert not (rollback_root / "work-items" / "backlog" / f"{slug}.md").exists()
    assert (rollback_root / "work-items" / "README.md").read_bytes() == readme_before
    assert not list((rollback_root / "work-items" / "backlog").glob(f".{slug}.legacy-candidate.*"))


def test_legacy_transitions_reject_physical_consumers_before_mutation(
    tmp_path: Path,
) -> None:
    module = load_module()
    slug = "legacy-linked"
    operations = (
        (
            "convert",
            lambda root: module.convert_legacy_candidate(
                root, slug, b"Task: candidate\nNext action: verify\n"
            ),
            lambda root: root / "work-items" / "backlog" / f"{slug}.md",
        ),
        (
            "retire",
            lambda root: module.retire_legacy_backlog(
                root,
                slug,
                b"Rejected before admission.\n",
                "2026-08-01T00:00:00Z",
            ),
            lambda root: root / "work-items" / "archive" / "2026-08" / slug,
        ),
    )
    for name, transition, target_for in operations:
        root = tmp_path / name
        source, before = _seed_legacy_backlog(
            root,
            slug,
            {"brief.md": b"preserve every source byte\n", "notes/design.md": b"design bytes\n"},
        )
        consumer = root / "work-items" / "bugs" / "consumer.md"
        write(
            consumer,
            f"[legacy source](../backlog/{slug}/brief.md)\nContext: work-item:{slug}\n",
        )
        module.refresh_readme(root, allow_marker_bootstrap=True)
        readme_before = (root / "work-items" / "README.md").read_bytes()

        try:
            transition(root)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-LEGACY-LINK-UNMAPPED"
        else:
            raise AssertionError(f"{name} admitted a physical consumer")

        assert {
            path.relative_to(source).as_posix(): path.read_bytes()
            for path in source.rglob("*")
            if path.is_file()
        } == before
        assert (consumer.parent / f"../backlog/{slug}/brief.md").resolve() == source / "brief.md"
        assert (root / "work-items" / "README.md").read_bytes() == readme_before
        assert not target_for(root).exists()


def test_convert_legacy_candidate_commits_before_partial_cleanup_failure(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "legacy-cleanup-commit"
    source, before = _seed_legacy_backlog(
        root,
        slug,
        {"brief.md": b"preserve brief bytes\n", "notes/design.md": b"preserve design bytes\n"},
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    original_rmtree = module.shutil.rmtree
    injected = False

    def partial_cleanup(path: Path | str, *args: object, **kwargs: object) -> None:
        nonlocal injected
        candidate = Path(path)
        if candidate.name == "source" and not injected:
            injected = True
            (candidate / "brief.md").unlink()
            raise OSError("injected partial cleanup failure")
        original_rmtree(path, *args, **kwargs)

    candidate_data = (
        b"status: candidate\n"
        b"Task: preserve complete legacy evidence\n"
        b"Next action: verify\n"
    )
    module.shutil.rmtree = partial_cleanup
    try:
        try:
            module.convert_legacy_candidate(root, slug, candidate_data)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-LEGACY-CLEANUP-AFTER-COMMIT"
            assert "state=committed" in str(exc)
        else:
            raise AssertionError("post-commit cleanup fault returned success")
    finally:
        module.shutil.rmtree = original_rmtree

    assert injected
    target = root / "work-items" / "backlog" / f"{slug}.md"
    readme = root / "work-items" / "README.md"
    converted = target.read_bytes()
    assert converted.startswith(candidate_data) and not source.exists()
    for relative, data in before.items():
        assert f"### `{relative}`".encode() in converted
        assert data in converted
        assert hashlib.sha256(data).hexdigest().encode() in converted
    assert readme.read_bytes() == module.render_readme_bytes(root)
    residues = list((root / "work-items" / "backlog").glob(f".{slug}.legacy-candidate.*"))
    assert len(residues) == 1
    marker = residues[0] / module.LEGACY_CLEANUP_FILE
    marker_payload = json.loads(marker.read_text(encoding="utf-8"))
    assert marker_payload["schemaVersion"] == module.LEGACY_CLEANUP_SCHEMA_VERSION
    assert marker_payload["owner"] == module.LEGACY_CLEANUP_OWNER
    assert marker_payload["slug"] == slug
    assert marker_payload["transactionId"] == residues[0].name
    assert marker_payload["canonicalTarget"] == f"backlog/{slug}.md"
    assert marker_payload["candidateSha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
    assert marker_payload["sourceFiles"]
    target_before = target.read_bytes()
    readme_before = readme.read_bytes()

    replay = module.convert_legacy_candidate(root, slug, candidate_data)

    assert replay == target
    assert target.read_bytes() == target_before
    assert readme.read_bytes() == readme_before
    assert not residues[0].exists()
    module.audit(root)


def test_convert_legacy_candidate_replays_final_rmdir_failure_with_sidecar_marker(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "legacy-cleanup-final-rmdir"
    source, _before = _seed_legacy_backlog(root, slug, {"brief.md": b"owned source\n"})
    module.refresh_readme(root, allow_marker_bootstrap=True)
    candidate_data = (
        b"status: candidate\n"
        b"Task: preserve final cleanup marker\n"
        b"Next action: verify\n"
    )
    backlog = root / "work-items" / "backlog"
    original_rmdir = module.Path.rmdir
    injected = False

    def fail_final_rmdir(path: Path, *args: object, **kwargs: object) -> None:
        nonlocal injected
        if (
            path.parent == backlog
            and path.name.startswith(f".{slug}.legacy-candidate.")
            and not injected
        ):
            injected = True
            raise OSError("injected final transaction rmdir failure")
        original_rmdir(path, *args, **kwargs)

    module.Path.rmdir = fail_final_rmdir
    try:
        try:
            module.convert_legacy_candidate(root, slug, candidate_data)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-LEGACY-CLEANUP-AFTER-COMMIT"
            assert "state=committed" in str(exc)
        else:
            raise AssertionError("final transaction rmdir fault returned success")
    finally:
        module.Path.rmdir = original_rmdir

    target = backlog / f"{slug}.md"
    readme = root / "work-items" / "README.md"
    residues = list(backlog.glob(f".{slug}.legacy-candidate.*"))
    assert injected and not source.exists() and len(residues) == 1
    residue = residues[0]
    sidecar = module._legacy_cleanup_sidecar(backlog, residue.name)
    assert not (residue / module.LEGACY_CLEANUP_FILE).exists()
    assert list(residue.iterdir()) == []
    sidecar_payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert sidecar_payload["transactionId"] == residue.name
    target_before = target.read_bytes()
    readme_before = readme.read_bytes()

    replay = module.convert_legacy_candidate(root, slug, candidate_data)

    assert replay == target
    assert target.read_bytes() == target_before
    assert readme.read_bytes() == readme_before
    assert not residue.exists() and not sidecar.exists()
    module.audit(root)


def test_convert_legacy_candidate_replays_sidecar_marker_unlink_failure(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "legacy-cleanup-sidecar-unlink"
    source, _before = _seed_legacy_backlog(root, slug, {"brief.md": b"owned source\n"})
    module.refresh_readme(root, allow_marker_bootstrap=True)
    candidate_data = (
        b"status: candidate\n"
        b"Task: preserve sidecar cleanup marker\n"
        b"Next action: verify\n"
    )
    backlog = root / "work-items" / "backlog"
    original_unlink = module.Path.unlink
    injected = False

    def fail_sidecar_unlink(path: Path, *args: object, **kwargs: object) -> None:
        nonlocal injected
        if (
            path.parent == backlog
            and path.name.startswith(f".legacy-candidate-cleanup.{slug}.legacy-candidate.")
            and not injected
        ):
            injected = True
            raise OSError("injected sidecar marker unlink failure")
        original_unlink(path, *args, **kwargs)

    module.Path.unlink = fail_sidecar_unlink
    try:
        try:
            module.convert_legacy_candidate(root, slug, candidate_data)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-LEGACY-CLEANUP-AFTER-COMMIT"
            assert "state=committed" in str(exc)
        else:
            raise AssertionError("sidecar marker cleanup fault returned success")
    finally:
        module.Path.unlink = original_unlink

    target = backlog / f"{slug}.md"
    readme = root / "work-items" / "README.md"
    sidecars = list(backlog.glob(f".legacy-candidate-cleanup.{slug}.legacy-candidate.*.json"))
    assert injected and not source.exists() and len(sidecars) == 1
    sidecar = sidecars[0]
    assert not list(backlog.glob(f".{slug}.legacy-candidate.*"))
    assert json.loads(sidecar.read_text(encoding="utf-8"))["slug"] == slug
    target_before = target.read_bytes()
    readme_before = readme.read_bytes()

    replay = module.convert_legacy_candidate(root, slug, candidate_data)

    assert replay == target
    assert target.read_bytes() == target_before
    assert readme.read_bytes() == readme_before
    assert not sidecar.exists()
    module.audit(root)


def test_convert_legacy_candidate_replay_rejects_unmarked_spoof_without_deletion(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "legacy-cleanup-spoof"
    source, _before = _seed_legacy_backlog(root, slug, {"brief.md": b"owned source\n"})
    module.refresh_readme(root, allow_marker_bootstrap=True)
    candidate_data = (
        b"status: candidate\n"
        b"Task: preserve cleanup ownership\n"
        b"Next action: verify\n"
    )
    target = module.convert_legacy_candidate(root, slug, candidate_data)
    assert not source.exists()
    readme = root / "work-items" / "README.md"
    target_before = target.read_bytes()
    readme_before = readme.read_bytes()
    spoof = root / "work-items" / "backlog" / f".{slug}.legacy-candidate.user-owned"
    valuable = spoof / "valuable.txt"
    valuable.parent.mkdir(parents=True)
    valuable.write_bytes(b"unowned valuable bytes\n")

    try:
        module.convert_legacy_candidate(root, slug, candidate_data)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-LEGACY-CLEANUP-REPLAY-INVALID"
    else:
        raise AssertionError("unmarked matching residue was deleted")

    assert valuable.read_bytes() == b"unowned valuable bytes\n"
    assert target.read_bytes() == target_before
    assert readme.read_bytes() == readme_before


def test_convert_legacy_candidate_replay_rejects_marker_mismatch_without_deletion(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "legacy-cleanup-marker-mismatch"
    source, _before = _seed_legacy_backlog(
        root, slug, {"brief.md": b"owned source\n", "notes/design.md": b"owned design\n"}
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    candidate_data = (
        b"status: candidate\n"
        b"Task: preserve owner marker\n"
        b"Next action: verify\n"
    )
    original_rmtree = module.shutil.rmtree
    injected = False

    def partial_cleanup(path: Path | str, *args: object, **kwargs: object) -> None:
        nonlocal injected
        candidate = Path(path)
        if candidate.name == "source" and not injected:
            injected = True
            (candidate / "brief.md").unlink()
            raise OSError("injected partial cleanup failure")
        original_rmtree(path, *args, **kwargs)

    module.shutil.rmtree = partial_cleanup
    try:
        try:
            module.convert_legacy_candidate(root, slug, candidate_data)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-LEGACY-CLEANUP-AFTER-COMMIT"
        else:
            raise AssertionError("post-commit cleanup fault returned success")
    finally:
        module.shutil.rmtree = original_rmtree

    target = root / "work-items" / "backlog" / f"{slug}.md"
    readme = root / "work-items" / "README.md"
    residue = next((root / "work-items" / "backlog").glob(f".{slug}.legacy-candidate.*"))
    marker = residue / module.LEGACY_CLEANUP_FILE
    marker_payload = json.loads(marker.read_text(encoding="utf-8"))
    marker_payload["candidateSha256"] = "0" * 64
    marker.write_text(json.dumps(marker_payload, sort_keys=True) + "\n", encoding="utf-8")
    target_before = target.read_bytes()
    readme_before = readme.read_bytes()
    residue_before = {
        path.relative_to(residue).as_posix(): path.read_bytes()
        for path in residue.rglob("*")
        if path.is_file()
    }

    try:
        module.convert_legacy_candidate(root, slug, candidate_data)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-LEGACY-CLEANUP-REPLAY-INVALID"
    else:
        raise AssertionError("mismatched owner marker was accepted")

    assert injected and not source.exists()
    assert target.read_bytes() == target_before
    assert readme.read_bytes() == readme_before
    assert {
        path.relative_to(residue).as_posix(): path.read_bytes()
        for path in residue.rglob("*")
        if path.is_file()
    } == residue_before


def test_retire_legacy_backlog_records_links_and_no_fake_active_history(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "legacy-rejected"
    source, before = _seed_legacy_backlog(
        root,
        slug,
        {"design.md": b"# Design only -- not admitted\n\nDecision: reject.\n"},
    )
    write(
        root / "work-items" / "bugs" / "consumer.md",
        f"status: open\nContext: work-item:{slug}\n",
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    instant = "2026-08-01T00:00:00Z"
    disposition = b"Rejected before admission; future components require fresh intake.\n"

    target = module.retire_legacy_backlog(root, slug, disposition, instant)

    assert target == root / "work-items" / "archive" / "2026-08" / slug
    assert not source.exists()
    assert (target / "design.md").read_bytes() == before["design.md"]
    metadata = json.loads(
        (target / "legacy-retirement.json").read_text(encoding="utf-8")
    )
    assert metadata["terminalAt"] == instant
    assert metadata["status"] == "rejected-before-admission"
    assert metadata["admissionHistory"] == "never-admitted"
    assert metadata["syntheticTransitions"] == []
    assert metadata["sourceFiles"] == [
        {
            "path": "design.md",
            "byteLength": len(before["design.md"]),
            "sha256": hashlib.sha256(before["design.md"]).hexdigest(),
        }
    ]
    assert metadata["incomingLinks"]["result"] == "logical-only"
    assert {row["kind"] for row in metadata["incomingLinks"]["references"]} == {"logical"}
    for forbidden in ("status.md", "closure.md", "admission.md", "agent-runs.jsonl"):
        assert not (target / forbidden).exists()
    entries = [
        entry
        for entry in module.collect_readme_entries(root)
        if entry.logical_reference == f"work-item:{slug}"
    ]
    assert len(entries) == 1
    assert entries[0].section == "Recently completed" and entries[0].checked
    assert entries[0].classification == "WI-LEGACY-RETIRED-BEFORE-ADMISSION"
    module.audit(root)


def test_audit_rejects_live_plain_path_to_retired_backlog_but_ignores_archive_history(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "retired-path-citation"
    _source, _before = _seed_legacy_backlog(
        root,
        slug,
        {"design.md": b"# Design only\n"},
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    target = module.retire_legacy_backlog(
        root,
        slug,
        b"Rejected before admission.\n",
        "2026-08-01T00:00:00Z",
    )
    retired_path = f"work-items/backlog/{slug}/design.md"
    archived_consumer = root / "work-items" / "decisions" / "archive" / "2026-08" / "history.md"
    write(
        archived_consumer,
        f"Historical context: work-item:{slug}; `{retired_path}`.\n",
    )
    false_positive_slug = "2026-08-01-current"
    false_positive = root / "work-items" / "decisions" / f"{false_positive_slug}.md"
    write(
        false_positive,
        _current_decision_record(
            false_positive_slug,
            body=f"Not a path: `not-{retired_path}`.\n",
        ),
    )

    assert module._incoming_link_result(
        root,
        {target},
        f"work-item:{slug}",
        literal_path_references=(retired_path,),
        mutable_consumers_only=True,
        scan_markdown_links=False,
    ) == {"result": "clear", "references": []}

    live_slug = "2026-08-01-live"
    live_consumer = root / "work-items" / "decisions" / f"{live_slug}.md"
    write(
        live_consumer,
        _current_decision_record(
            live_slug,
            body=f"Stale context: `{retired_path}`.\n",
        ),
    )
    try:
        module.audit(root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-LEGACY-RETIREMENT-INVALID"
        assert "mutable record retains a retired backlog path" in str(exc)
    else:
        raise AssertionError("live literal citation to retired backlog passed audit")


def test_retire_legacy_backlog_strict_utc_and_failure_rollback(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "legacy-retire-rollback"
    source, before = _seed_legacy_backlog(
        root, slug, {"design.md": b"preserve retirement source\n"}
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    readme_before = (root / "work-items" / "README.md").read_bytes()
    try:
        module.retire_legacy_backlog(
            root,
            slug,
            b"Rejected before admission.\n",
            "2026-08-01T03:00:00+03:00",
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"
    else:
        raise AssertionError("non-UTC retirement was admitted")
    assert (source / "design.md").read_bytes() == before["design.md"]

    try:
        module.retire_legacy_backlog(
            root,
            slug,
            b"Rejected before admission.\n",
            "2026-08-01T00:00:00Z",
            inject_readme_failure=True,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-README-STALE"
    else:
        raise AssertionError("injected retirement failure returned success")
    assert (source / "design.md").read_bytes() == before["design.md"]
    assert not (root / "work-items" / "archive").exists()
    assert (root / "work-items" / "README.md").read_bytes() == readme_before


def test_terminalize_v1_supports_every_flat_category(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    work_items = root / "work-items"
    records = {
        "bug": ("bugs", "fixed", "Terminal-at", "Resolution"),
        "decision": ("decisions", "dropped", "Terminal-at", "Rationale"),
        "lesson": ("lessons", "archived", "Terminal-at", "Disposition"),
        "roadmap": ("roadmaps", "archived", "Terminal-at", "Disposition"),
        "epic": ("epics", "closed", "Closed", "Outcome"),
    }
    for category, (directory, status, _utc_field, _detail_field) in records.items():
        write(
            work_items / directory / f"legacy-{category}.md",
            f"status: {status}\nTask: Preserve {category}.\n",
        )
    inventory = root / ".scratch" / "inventory.json"
    receipt = root / ".scratch" / "receipt.json"
    audited = run_cli(
        "audit", "--root", str(work_items), "--output", str(inventory)
    )
    assert audited.returncode == 1, audited.stdout
    assert "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING" in audited.stdout
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    assert {row["category"] for row in payload["rows"]} == set(records)
    assert {row["admission"]["result"] for row in payload["rows"]} == {"denied"}

    count, replay = module.terminalize_v1_inventory(
        root,
        inventory,
        terminal_at="2026-08-01T00:00:00Z",
        authorization_marker="operator-authorized-v1-terminalization",
        receipt_path=receipt,
    )

    assert count == len(records) and replay is False
    for category, (directory, _status, utc_field, detail_field) in records.items():
        text = (work_items / directory / f"legacy-{category}.md").read_text(
            encoding="utf-8"
        )
        assert f"{utc_field}: 2026-08-01T00:00:00Z" in text
        assert f"{detail_field}: Pre-V1 terminal status" in text
        assert text.count("V1-Migration-Evidence:") == 1
        assert text.count("Evidence:") == 2
    refreshed = root / ".scratch" / "refreshed.json"
    checked = run_cli(
        "audit", "--root", str(work_items), "--output", str(refreshed)
    )
    assert checked.returncode == 0, checked.stdout
    assert {
        row["admission"]["result"]
        for row in json.loads(refreshed.read_text(encoding="utf-8"))["rows"]
    } == {"admitted"}


def _physical_relocation_inventory(root: Path) -> tuple[Path, Path, Path, Path, dict]:
    work_items = root / "work-items"
    slug = "roadmap-decision-2026-07-27"
    target = work_items / "roadmaps" / f"{slug}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(_pre_v1_terminal_record("archived", "Historical roadmap"))
    consumer = (
        work_items
        / "epics"
        / "archive"
        / "2026-07"
        / "2026-07-27-always-on-hook-layer-fitness.md"
    )
    label = f"work-items/roadmaps/{slug}.md"
    old_href = f"../../../roadmaps/{slug}.md"
    write(consumer, f"# Closed epic\n\n[{label}]({old_href}).\n")
    inventory = root / ".scratch" / "terminalization-inventory.json"
    receipt = root / ".scratch" / "terminalization-receipt.json"
    payload = _denied_terminalization_inventory(work_items, inventory)
    row = next(row for row in payload["rows"] if row["reference"] == f"roadmap:{slug}")
    assert row["incomingLinks"] == {
        "result": "unmapped",
        "references": [
            {
                "consumer": consumer.relative_to(work_items).as_posix(),
                "kind": "physical",
                "value": old_href,
            }
        ],
    }
    row["incomingLinks"] = {
        "result": "physical-relocation",
        "references": row["incomingLinks"]["references"],
        "physicalRelocation": {
            "source": consumer.relative_to(work_items).as_posix(),
            "label": label,
            "href": old_href,
            "expectedIdentity": f"roadmap:{slug}",
            "sourceSha256": hashlib.sha256(consumer.read_bytes()).hexdigest(),
            "targetSha256": row["inputSha256"],
            "receipt": receipt.relative_to(root).as_posix(),
        },
    }
    inventory.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return inventory, receipt, consumer, target, payload


def test_exact_physical_relocation_is_admitted_then_moved_atomically(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    inventory, receipt, consumer, current_target, payload = _physical_relocation_inventory(root)
    work_items = root / "work-items"
    row = payload["rows"][0]
    consumer_before = consumer.read_bytes()
    target_before = current_target.read_bytes()

    count, replay = module.terminalize_v1_inventory(
        root,
        inventory,
        terminal_at="2026-08-01T00:00:00Z",
        authorization_marker="operator-authorized-v1-terminalization",
        receipt_path=receipt,
    )

    assert count == 1 and replay is False
    assert consumer.read_bytes() == consumer_before
    assert current_target.is_file()
    assert current_target.read_bytes().startswith(target_before)
    terminalized_target = current_target.read_bytes()

    migrated, _readme_hash = module.apply_migration_inventory(
        root,
        inventory,
        render_readme=True,
        byte_check=True,
    )

    final_target = (
        work_items
        / "roadmaps"
        / "archive"
        / "2026-08"
        / current_target.name
    )
    expected_new_href = f"../../../roadmaps/archive/2026-08/{current_target.name}"
    consumer_after = consumer.read_bytes()
    assert migrated == 1
    assert not current_target.exists() and final_target.read_bytes() == terminalized_target
    assert consumer_after == consumer_before.replace(
        row["incomingLinks"]["physicalRelocation"]["href"].encode(),
        expected_new_href.encode(),
    )
    assert (consumer.parent / expected_new_href).resolve() == final_target.resolve()
    assert module._category_locations(
        root, module.CATEGORIES["roadmap"], current_target.stem
    ) == [final_target]
    assert module.verify_migration_inventory(root, inventory) == 1
    receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
    evidence = receipt_payload["rows"][0]["physicalRelocation"]
    assert evidence["oldHref"] == row["incomingLinks"]["physicalRelocation"]["href"]
    assert evidence["newHref"] == expected_new_href
    assert evidence["finalTarget"] == final_target.relative_to(work_items).as_posix()
    assert evidence["sourceBeforeSha256"] == hashlib.sha256(consumer_before).hexdigest()
    assert evidence["sourceAfterSha256"] == hashlib.sha256(consumer_after).hexdigest()
    assert evidence["targetBeforeSha256"] == hashlib.sha256(terminalized_target).hexdigest()
    assert evidence["targetAfterSha256"] == hashlib.sha256(final_target.read_bytes()).hexdigest()


def test_physical_relocation_preserves_fragment_and_query_suffix_atomically(
    tmp_path: Path,
) -> None:
    module = load_module()
    for case, suffix in (("fragment", "#section"), ("query", "?view=full")):
        root = tmp_path / case
        inventory, receipt, consumer, current_target, payload = (
            _physical_relocation_inventory(root)
        )
        row = payload["rows"][0]
        admission = row["incomingLinks"]["physicalRelocation"]
        raw_href = admission["href"] + suffix
        consumer.write_text(
            f"# Closed epic\n\n[{admission['label']}]({raw_href}).\n",
            encoding="utf-8",
        )
        row["incomingLinks"]["references"][0]["value"] = raw_href
        admission["href"] = raw_href
        admission["sourceSha256"] = hashlib.sha256(consumer.read_bytes()).hexdigest()
        inventory.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        count, replay = module.terminalize_v1_inventory(
            root,
            inventory,
            terminal_at="2026-08-01T00:00:00Z",
            authorization_marker="operator-authorized-v1-terminalization",
            receipt_path=receipt,
        )
        assert count == 1 and replay is False, case
        migrated, _readme_hash = module.apply_migration_inventory(
            root,
            inventory,
            render_readme=True,
            byte_check=True,
        )

        final_target = (
            root
            / "work-items"
            / "roadmaps"
            / "archive"
            / "2026-08"
            / current_target.name
        )
        new_path = f"../../../roadmaps/archive/2026-08/{current_target.name}"
        new_href = new_path + suffix
        consumer_text = consumer.read_text(encoding="utf-8")
        receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
        evidence = receipt_payload["rows"][0]["physicalRelocation"]
        assert migrated == 1 and final_target.is_file(), case
        assert f"]({new_href})" in consumer_text and raw_href not in consumer_text, case
        assert evidence["oldHref"] == raw_href and evidence["newHref"] == new_href, case
        assert module.verify_migration_inventory(root, inventory) == 1, case


def test_physical_relocation_tuple_mismatches_fail_before_any_write(
    tmp_path: Path,
) -> None:
    module = load_module()
    cases = {
        "source": lambda admission: admission.__setitem__(
            "source", "epics/archive/2026-07/other.md"
        ),
        "label": lambda admission: admission.__setitem__("label", admission["label"] + "-wrong"),
        "href": lambda admission: admission.__setitem__("href", admission["href"] + "-wrong"),
        "identity": lambda admission: admission.__setitem__(
            "expectedIdentity", "roadmap:other"
        ),
        "source-hash": lambda admission: admission.__setitem__("sourceSha256", "0" * 64),
        "target-hash": lambda admission: admission.__setitem__("targetSha256", "0" * 64),
        "receipt-escape": lambda admission: admission.__setitem__("receipt", "../receipt.json"),
    }
    for case, mutate in cases.items():
        root = tmp_path / case
        inventory, receipt, consumer, target, payload = _physical_relocation_inventory(root)
        admission = payload["rows"][0]["incomingLinks"]["physicalRelocation"]
        mutate(admission)
        inventory.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        consumer_before = consumer.read_bytes()
        target_before = target.read_bytes()

        try:
            module.terminalize_v1_inventory(
                root,
                inventory,
                terminal_at="2026-08-01T00:00:00Z",
                authorization_marker="operator-authorized-v1-terminalization",
                receipt_path=receipt,
            )
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING", case
        else:
            raise AssertionError(f"{case} mismatch was admitted")

        assert consumer.read_bytes() == consumer_before, case
        assert target.read_bytes() == target_before, case
        assert not receipt.exists(), case


def test_terminalization_receipt_must_stay_under_repository_scratch(
    tmp_path: Path,
) -> None:
    module = load_module()
    for case in ("outside", "traversal", "scratch-root", "reparse"):
        root = tmp_path / f"repo-{case}"
        work_items = root / "work-items"
        source = work_items / "bugs" / "historic.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(_pre_v1_terminal_record("fixed", "Historic"))
        inventory = root / ".scratch" / "inventory.json"
        payload = _denied_terminalization_inventory(work_items, inventory)
        assert payload["rows"][0]["incomingLinks"]["result"] == "clear"
        before = source.read_bytes()
        if case == "outside":
            escaped_receipt = tmp_path / "outside" / ".scratch" / "receipt.json"
        elif case == "traversal":
            escaped_receipt = root / ".scratch" / ".." / "outside" / "receipt.json"
        elif case == "scratch-root":
            escaped_receipt = root / ".scratch"
        else:
            redirect = root / ".scratch" / "redirect"
            redirect.mkdir(parents=True)
            escaped_receipt = redirect / "receipt.json"

        original_reparse = module._terminalization_has_reparse
        if case == "reparse":
            module._terminalization_has_reparse = (
                lambda path, redirect=redirect: path == redirect or original_reparse(path)
            )
        try:
            try:
                module.terminalize_v1_inventory(
                    root,
                    inventory,
                    terminal_at="2026-08-01T00:00:00Z",
                    authorization_marker="operator-authorized-v1-terminalization",
                    receipt_path=escaped_receipt,
                )
            except module.LifecycleError as exc:
                assert exc.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING", case
            else:
                raise AssertionError(f"{case} receipt path was accepted")
        finally:
            module._terminalization_has_reparse = original_reparse

        assert source.read_bytes() == before, case
        assert not escaped_receipt.is_file(), case

    physical_root = tmp_path / "physical-admission"
    physical_receipt = physical_root / ".scratch" / "receipt.json"
    for case, relative in {
        "absolute": str(physical_receipt.resolve()),
        "traversal": ".scratch/../outside/receipt.json",
    }.items():
        try:
            module._bound_physical_receipt(physical_root, relative)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING", case
        else:
            raise AssertionError(f"physical admission accepted {case} receipt path")


def test_physical_relocation_rejects_unclosed_or_prefix_markdown_destinations(
    tmp_path: Path,
) -> None:
    module = load_module()
    for case, suffix in {
        "unterminated": "",
        "trailing": " trailing)",
        "fragment": "#section)",
        "query": "?view=full)",
        "title": ' "historic")',
    }.items():
        root = tmp_path / case
        inventory, receipt, consumer, target, payload = _physical_relocation_inventory(root)
        admission = payload["rows"][0]["incomingLinks"]["physicalRelocation"]
        consumer.write_text(
            f"[{admission['label']}]({admission['href']}{suffix}\n", encoding="utf-8"
        )
        admission["sourceSha256"] = hashlib.sha256(consumer.read_bytes()).hexdigest()
        inventory.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        try:
            module.terminalize_v1_inventory(
                root,
                inventory,
                terminal_at="2026-08-01T00:00:00Z",
                authorization_marker="operator-authorized-v1-terminalization",
                receipt_path=receipt,
            )
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING", case
        else:
            raise AssertionError(f"{case} Markdown destination was admitted")

        assert target.is_file(), case
        assert not receipt.exists(), case


def test_physical_relocation_duplicate_nonarchive_and_wrong_resolution_fail_closed(
    tmp_path: Path,
) -> None:
    module = load_module()
    for case in ("duplicate", "nonarchive", "wrong-resolution"):
        root = tmp_path / case
        inventory, receipt, consumer, target, payload = _physical_relocation_inventory(root)
        row = payload["rows"][0]
        admission = row["incomingLinks"]["physicalRelocation"]
        if case == "duplicate":
            consumer.write_bytes(consumer.read_bytes() + consumer.read_bytes().split(b"\n")[-2] + b"\n")
            row["incomingLinks"]["references"].append(
                dict(row["incomingLinks"]["references"][0])
            )
            admission["sourceSha256"] = hashlib.sha256(consumer.read_bytes()).hexdigest()
        elif case == "nonarchive":
            live_consumer = target.parents[1] / "epics" / "live-consumer.md"
            new_href = f"../roadmaps/{target.name}"
            write(live_consumer, f"[{admission['label']}]({new_href})\n")
            consumer.unlink()
            consumer = live_consumer
            row["incomingLinks"]["references"][0]["consumer"] = consumer.relative_to(
                root / "work-items"
            ).as_posix()
            row["incomingLinks"]["references"][0]["value"] = new_href
            admission["source"] = row["incomingLinks"]["references"][0]["consumer"]
            admission["href"] = new_href
            admission["sourceSha256"] = hashlib.sha256(consumer.read_bytes()).hexdigest()
        else:
            wrong = target.parent / "other.md"
            wrong.write_bytes(_pre_v1_terminal_record("archived", "Other"))
            wrong_href = f"../../../roadmaps/{wrong.name}"
            consumer.write_text(
                f"[{admission['label']}]({wrong_href})\n", encoding="utf-8"
            )
            row["incomingLinks"]["references"][0]["value"] = wrong_href
            admission["href"] = wrong_href
            admission["sourceSha256"] = hashlib.sha256(consumer.read_bytes()).hexdigest()
        inventory.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        consumer_before = consumer.read_bytes()
        target_before = target.read_bytes()

        try:
            module.terminalize_v1_inventory(
                root,
                inventory,
                terminal_at="2026-08-01T00:00:00Z",
                authorization_marker="operator-authorized-v1-terminalization",
                receipt_path=receipt,
            )
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING", case
        else:
            raise AssertionError(f"{case} physical relocation was admitted")

        assert consumer.read_bytes() == consumer_before, case
        assert target.read_bytes() == target_before, case
        assert not receipt.exists(), case


def test_physical_relocation_apply_drift_and_post_move_failure_roll_back(
    tmp_path: Path,
) -> None:
    module = load_module()
    for case in ("consumer-drift", "target-drift", "receipt-drift", "post-move"):
        root = tmp_path / case
        inventory, receipt, consumer, target, _payload = _physical_relocation_inventory(root)
        module.terminalize_v1_inventory(
            root,
            inventory,
            terminal_at="2026-08-01T00:00:00Z",
            authorization_marker="operator-authorized-v1-terminalization",
            receipt_path=receipt,
        )
        consumer_before = consumer.read_bytes()
        target_before = target.read_bytes()
        receipt_before = receipt.read_bytes()
        readme = root / "work-items" / "README.md"
        readme_before = readme.read_bytes() if readme.is_file() else None
        if case == "consumer-drift":
            consumer.write_bytes(consumer_before + b"drift\n")
        elif case == "target-drift":
            target.write_bytes(target_before + b"drift\n")
        elif case == "receipt-drift":
            receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
            receipt_payload["rows"][0]["physicalRelocation"]["label"] += "-wrong"
            receipt.write_text(json.dumps(receipt_payload), encoding="utf-8")
        original_refresh = module.refresh_readme
        if case == "post-move":
            def fail_after_move(*_args, **_kwargs):
                raise module.LifecycleError("WI-README-STALE", "injected after move")

            module.refresh_readme = fail_after_move
        try:
            try:
                module.apply_migration_inventory(
                    root,
                    inventory,
                    render_readme=True,
                    byte_check=True,
                )
            except module.LifecycleError:
                pass
            else:
                raise AssertionError(f"{case} returned success")
        finally:
            module.refresh_readme = original_refresh

        final_target = (
            root
            / "work-items"
            / "roadmaps"
            / "archive"
            / "2026-08"
            / target.name
        )
        assert target.is_file() and not final_target.exists(), case
        if case == "consumer-drift":
            assert consumer.read_bytes() == consumer_before + b"drift\n"
        else:
            assert consumer.read_bytes() == consumer_before, case
        if case == "target-drift":
            assert target.read_bytes() == target_before + b"drift\n"
        else:
            assert target.read_bytes() == target_before, case
        if case == "receipt-drift":
            assert receipt.read_bytes() != receipt_before
        else:
            assert receipt.read_bytes() == receipt_before, case
        if readme_before is None:
            assert not readme.exists(), case
        else:
            assert readme.read_bytes() == readme_before, case


def test_settled_physical_relocation_receipt_fields_are_bound_to_admission(
    tmp_path: Path,
) -> None:
    module = load_module()
    for field, replacement in {
        "expectedIdentity": "roadmap:other",
        "oldHref": "../../../roadmaps/other.md",
        "sourceBeforeSha256": "0" * 64,
        "targetBeforeSha256": "f" * 64,
    }.items():
        root = tmp_path / field
        inventory, receipt, consumer, target, _payload = _physical_relocation_inventory(root)
        module.terminalize_v1_inventory(
            root,
            inventory,
            terminal_at="2026-08-01T00:00:00Z",
            authorization_marker="operator-authorized-v1-terminalization",
            receipt_path=receipt,
        )
        module.apply_migration_inventory(
            root,
            inventory,
            render_readme=True,
            byte_check=True,
        )
        receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
        receipt_payload["rows"][0]["physicalRelocation"][field] = replacement
        receipt.write_text(json.dumps(receipt_payload), encoding="utf-8")
        consumer_before = consumer.read_bytes()
        final_target = target.parent / "archive" / "2026-08" / target.name
        target_before = final_target.read_bytes()

        try:
            module.apply_migration_inventory(
                root,
                inventory,
                render_readme=True,
                byte_check=True,
            )
        except module.LifecycleError:
            pass
        else:
            raise AssertionError(f"settled {field} drift was accepted")

        assert consumer.read_bytes() == consumer_before, field
        assert final_target.read_bytes() == target_before, field


def test_settled_physical_relocation_replay_binds_its_owner_row_in_both_orders(
    tmp_path: Path,
) -> None:
    module = load_module()
    for owner_position in ("first", "last"):
        root = tmp_path / owner_position
        inventory, receipt, consumer, target, initial_payload = (
            _physical_relocation_inventory(root)
        )
        work_items = root / "work-items"
        unrelated = work_items / "roadmaps" / "roadmap-z.md"
        unrelated.write_bytes(_pre_v1_terminal_record("archived", "Unrelated roadmap"))

        payload = _denied_terminalization_inventory(work_items, inventory)
        owner_reference = f"roadmap:{target.stem}"
        owner_row = next(
            row for row in payload["rows"] if row["reference"] == owner_reference
        )
        owner_row["incomingLinks"] = initial_payload["rows"][0]["incomingLinks"]
        unrelated_row = next(
            row for row in payload["rows"] if row["reference"] != owner_reference
        )
        payload["rows"] = (
            [owner_row, unrelated_row]
            if owner_position == "first"
            else [unrelated_row, owner_row]
        )
        inventory.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        count, replay = module.terminalize_v1_inventory(
            root,
            inventory,
            terminal_at="2026-08-01T00:00:00Z",
            authorization_marker="operator-authorized-v1-terminalization",
            receipt_path=receipt,
        )
        assert count == 2 and replay is False, owner_position

        migrated, _readme_hash = module.apply_migration_inventory(
            root,
            inventory,
            render_readme=True,
            byte_check=True,
        )
        assert migrated == 2, owner_position
        replayed, _readme_hash = module.apply_migration_inventory(
            root,
            inventory,
            render_readme=True,
            byte_check=True,
        )
        assert replayed == 2, owner_position

        final_target = target.parent / "archive" / "2026-08" / target.name
        expected_new_href = f"../../../roadmaps/archive/2026-08/{target.name}"
        assert (consumer.parent / expected_new_href).resolve() == final_target.resolve()
        assert module.verify_migration_inventory(root, inventory) == 2


def _canonical_decision_record(slug: str) -> str:
    return (
        f"- id: {slug}\n"
        "- status: proposed\n"
        "- date: 2026-08-11\n"
        "- decided-by: $architect\n"
        "- context: schema-test\n"
        "- supersedes: none\n"
        "- superseded-by: none\n"
        "- accepted-evidence: first line\n"
        "  continuation line\n"
        "\n"
        f"# Decision: {slug}\n"
        "\n"
        "## Decision\n"
        "Synthetic decision.\n"
    )


def _accepted_v0_policy_record(
    slug: str,
    baseline_sha256: str,
    *,
    manifest_path: str = "work-items/decision-v0-compatibility.json",
    cutover_date: str = "2026-08-18",
) -> str:
    return _canonical_decision_record(slug).replace(
        "- status: proposed\n",
        "- status: accepted\n",
    ).replace(
        "- date: 2026-08-11\n",
        f"- date: {slug[:10]}\n",
    ).replace(
        "\n# Decision:",
        (
            f"- v0-manifest: {manifest_path}\n"
            f"- v0-baseline-sha256: {baseline_sha256}\n"
            f"- v0-cutover-date: {cutover_date}\n"
            "\n# Decision:"
        ),
    )


def _legacy_v0_decision_record(
    *,
    status: str = "accepted",
    identity_line: str | None = None,
    extra_header: str = "",
    body: str = "Legacy decision body.\n",
) -> str:
    identity = f"{identity_line}\n" if identity_line else ""
    return f"---\nstatus: {status}\n{identity}{extra_header}---\n{body}"


def _decision_v0_baseline(entries: list[dict[str, str]]) -> str:
    payload = b"".join(
        entry["path"].encode("utf-8")
        + b"\0"
        + entry["sha256"].encode("ascii")
        + b"\n"
        for entry in sorted(entries, key=lambda row: row["path"])
    )
    return hashlib.sha256(payload).hexdigest().upper()


def _write_decision_v0_manifest(
    root: Path,
    entries: list[dict[str, str]],
    *,
    policy_slug: str = "2026-08-18-current-decision-schema-versioned-read-compatibility",
    cutover_date: str = "2026-08-18",
) -> Path:
    ordered = sorted(entries, key=lambda row: row["path"])
    baseline = _decision_v0_baseline(ordered)
    write(
        root / "work-items" / "decisions" / f"{policy_slug}.md",
        _accepted_v0_policy_record(
            policy_slug,
            baseline,
            cutover_date=cutover_date,
        ),
    )
    target = root / "work-items" / "decision-v0-compatibility.json"
    write(
        target,
        json.dumps(
            {
                "schemaVersion": 1,
                "policyDecision": policy_slug,
                "cutoverDate": cutover_date,
                "baselineSha256": baseline,
                "entries": ordered,
            },
            indent=2,
        )
        + "\n",
    )
    return target


def _legacy_h1_decision_record(
    *,
    mode: str = "plain",
    status: str = "accepted",
    status_key: str = "status",
    extra_fields: tuple[tuple[str, str], ...] = (("owner", "architect"),),
    body: str = "Legacy H1 decision body.\n",
) -> str:
    fields = ((status_key, status), *extra_fields)
    if mode == "plain":
        prefix = "\n".join(f"{key}: {value}" for key, value in fields)
    elif mode == "bold":
        prefix = "\n".join(f"- **{key}:** {value}" for key, value in fields)
    else:
        raise AssertionError(f"unsupported test H1 mode: {mode}")
    return f"# Legacy H1 decision\n\n{prefix}\n\n{body}"


def _accepted_h1_policy_record(
    slug: str,
    baseline_sha256: str,
    *,
    manifest_path: str = "work-items/decision-h1-compatibility.json",
    cutover_date: str = "2026-08-18",
) -> str:
    return _canonical_decision_record(slug).replace(
        "- status: proposed\n",
        "- status: accepted\n",
    ).replace(
        "- date: 2026-08-11\n",
        f"- date: {slug[:10]}\n",
    ).replace(
        "- supersedes: none\n",
        "- supersedes: 2026-08-18-current-decision-schema-versioned-read-compatibility\n",
    ).replace(
        "\n# Decision:",
        (
            f"- h1-manifest: {manifest_path}\n"
            f"- h1-baseline-sha256: {baseline_sha256}\n"
            f"- h1-cutover-date: {cutover_date}\n"
            "\n# Decision:"
        ),
    )


def _write_decision_h1_manifest(
    root: Path,
    entries: list[dict[str, str]],
    *,
    policy_slug: str = "2026-08-18-current-decision-schema-h1-read-compatibility",
    cutover_date: str = "2026-08-18",
) -> Path:
    ordered = sorted(entries, key=lambda row: row["path"])
    baseline = _decision_v0_baseline(ordered)
    write(
        root / "work-items" / "decisions" / f"{policy_slug}.md",
        _accepted_h1_policy_record(
            policy_slug,
            baseline,
            cutover_date=cutover_date,
        ),
    )
    target = root / "work-items" / "decision-h1-compatibility.json"
    write(
        target,
        json.dumps(
            {
                "schemaVersion": 1,
                "policyDecision": policy_slug,
                "cutoverDate": cutover_date,
                "baselineSha256": baseline,
                "entries": ordered,
            },
            indent=2,
        )
        + "\n",
    )
    return target


def test_decision_schema_rejects_noncanonical_current_records(tmp_path: Path) -> None:
    module = load_module()
    slug = "2026-08-11-schema-test"
    canonical = _canonical_decision_record(slug)
    cases = {
        "body-only-id": (
            canonical.replace(f"- id: {slug}\n", "").replace(
                "## Decision\n", f"## Decision\n- id: {slug}\n"
            ),
            "WI-DECISION-SCHEMA-INVALID",
        ),
        "proposer-is-not-decider": (
            canonical.replace("- decided-by: $architect\n", "- proposed-by: $architect\n"),
            "WI-DECISION-SCHEMA-INVALID",
        ),
        "duplicate-body-id": (
            canonical.replace("## Decision\n", f"## Decision\n- id: {slug}\n"),
            "WI-DECISION-FIELD-DUPLICATE",
        ),
        "wrong-id": (
            canonical.replace(f"- id: {slug}\n", "- id: 2026-08-11-other\n"),
            "WI-DECISION-IDENTITY-MISMATCH",
        ),
        "wrong-date": (
            canonical.replace("- date: 2026-08-11\n", "- date: 2026-08-10\n"),
            "WI-DECISION-IDENTITY-MISMATCH",
        ),
        "bare-leading-field": (
            canonical.replace("- context: schema-test\n", "context: schema-test\n"),
            "WI-DECISION-SCHEMA-INVALID",
        ),
        "decorated-leading-field": (
            canonical.replace(f"- id: {slug}\n", f"- **id**: {slug}\n"),
            "WI-DECISION-SCHEMA-INVALID",
        ),
        "uppercase-leading-field": (
            canonical.replace(f"- id: {slug}\n", f"- ID: {slug}\n"),
            "WI-DECISION-SCHEMA-INVALID",
        ),
        "empty-context": (
            canonical.replace("- context: schema-test\n", "- context:\n"),
            "WI-DECISION-SCHEMA-INVALID",
        ),
    }
    for name, (payload, failure_id) in cases.items():
        root = tmp_path / name
        write(root / "work-items" / "decisions" / f"{slug}.md", payload)
        try:
            module.audit_categories(root)
        except module.LifecycleError as exc:
            assert exc.failure_id == failure_id, (name, exc.failure_id, str(exc))
        else:
            raise AssertionError(f"noncanonical current decision passed: {name}")


def test_decision_v1_list_metadata_accepts_exact_h2_decision_body_heading(
    tmp_path: Path,
) -> None:
    module = load_module()
    slug = "2026-08-11-h2-body-heading"
    payload = _canonical_decision_record(slug).replace(
        f"# Decision: {slug}\n\n", ""
    )
    path = tmp_path / f"{slug}.md"
    write(path, payload)

    record = module._validate_current_decision_record(path, slug)

    assert record.format == "canonical-list-v1"
    assert record.body_offset == len(payload.split("## Decision\n", 1)[0].encode("utf-8"))


def test_decision_v1_list_metadata_rejects_malformed_h2_body_headings(
    tmp_path: Path,
) -> None:
    module = load_module()
    slug = "2026-08-11-h2-body-heading"
    canonical = _canonical_decision_record(slug)
    cases = {
        "wrong-title": canonical.replace(f"# Decision: {slug}", "## Notes"),
        "nested-decision": canonical.replace(f"# Decision: {slug}", "### Decision"),
        "empty-heading": canonical.replace(f"# Decision: {slug}", "## "),
        "heading-before-required-metadata": canonical.replace(
            "- context: schema-test\n", "## Decision\n\n- context: schema-test\n"
        ),
    }

    for name, payload in cases.items():
        path = tmp_path / name / f"{slug}.md"
        write(path, payload)
        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module._validate_current_decision_record(path, slug)
        assert caught.exception.failure_id == "WI-DECISION-SCHEMA-INVALID", name


def test_decision_schema_accepts_optional_multiline_and_legacy_archive(
    tmp_path: Path,
) -> None:
    module = load_module()
    slug = "2026-08-11-schema-test"
    write(
        tmp_path / "work-items" / "decisions" / f"{slug}.md",
        _canonical_decision_record(slug),
    )
    archived = (
        tmp_path
        / "work-items"
        / "decisions"
        / "archive"
        / "2026-08"
        / "legacy.md"
    )
    write(
        archived,
        "---\nstatus: dropped\n---\n\n# Decision: legacy\n\n"
        "Terminal-at: 2026-08-11T00:00:00Z\n"
        "Rationale: Historical bytes remain readable.\n"
        "Evidence: Synthetic archive fixture.\n",
    )

    assert module.audit_categories(tmp_path) == ()


def test_decision_v0_parser_accepts_closed_identity_matrix_and_preserves_v1(
    tmp_path: Path,
) -> None:
    module = load_module()
    cases = (
        (
            "2026-08-01-full-id",
            "id: 2026-08-01-full-id",
            {"id": "2026-08-01-full-id"},
        ),
        (
            "2026-08-02-undated-slug",
            "slug: undated-slug",
            {"slug": "undated-slug"},
        ),
        ("2026-08-03-no-identity", None, {}),
    )
    for slug, identity, expected_identity in cases:
        path = tmp_path / f"{slug}.md"
        write(
            path,
            _legacy_v0_decision_record(
                identity_line=identity,
                extra_header="owners:\n  - one\n  - two\n",
            ),
        )
        result = module._validate_current_decision_record(path, slug)
        assert result.format == "legacy-yaml-v0"
        assert result.raw_status == "accepted"
        assert result.admitted_current_status == "accepted"
        assert result.legacy_read_only is True
        assert result.fields["owners"] == ("one", "two")
        assert {key: result.fields[key] for key in expected_identity} == expected_identity
        assert "id" in result.fields if "id" in expected_identity else "id" not in result.fields
        assert "slug" in result.fields if "slug" in expected_identity else "slug" not in result.fields
        with unittest.TestCase().assertRaises(TypeError):
            result.fields["invented"] = "value"

    v1_slug = "2026-08-11-schema-test"
    v1_path = tmp_path / f"{v1_slug}.md"
    write(v1_path, _canonical_decision_record(v1_slug))
    v1 = module._validate_current_decision_record(v1_path, v1_slug)
    assert v1.format == "canonical-list-v1"
    assert v1.fields["id"] == v1_slug
    assert v1.raw_status == "proposed"
    assert v1.admitted_current_status == "proposed"
    assert v1.legacy_read_only is False


def test_decision_v0_parser_rejects_malformed_unknown_duplicate_and_identity(
    tmp_path: Path,
) -> None:
    module = load_module()
    slug = "2026-08-01-legacy"
    cases = {
        "unknown": ("## Decision\nstatus: accepted\n", "WI-DECISION-FORMAT-UNSUPPORTED"),
        "bom": ("\ufeff---\nstatus: accepted\n---\nbody\n", "WI-DECISION-FORMAT-UNSUPPORTED"),
        "missing-close": ("---\nstatus: accepted\nbody\n", "WI-DECISION-V0-SCHEMA-INVALID"),
        "blank-header": ("---\nstatus: accepted\n\n---\nbody\n", "WI-DECISION-V0-SCHEMA-INVALID"),
        "tab": ("---\nstatus:\taccepted\n---\nbody\n", "WI-DECISION-V0-SCHEMA-INVALID"),
        "nested": ("---\nstatus: accepted\n  child: value\n---\nbody\n", "WI-DECISION-V0-UNSUPPORTED-NESTING"),
        "empty-sequence": ("---\nstatus: accepted\nowners:\n  - \n---\nbody\n", "WI-DECISION-V0-UNSUPPORTED-NESTING"),
        "active-yaml": ("---\nstatus: &value accepted\n---\nbody\n", "WI-DECISION-V0-UNSUPPORTED-NESTING"),
        "duplicate": ("---\nstatus: accepted\nStatus: accepted\n---\nbody\n", "WI-DECISION-V0-FIELD-DUPLICATE"),
        "normalized-duplicate": ("---\nstatus: accepted\nowner name: one\nowner_name: two\n---\nbody\n", "WI-DECISION-V0-FIELD-DUPLICATE"),
        "wrong-id": ("---\nstatus: accepted\nid: 2026-08-01-other\n---\nbody\n", "WI-DECISION-IDENTITY-MISMATCH"),
        "dated-slug": (f"---\nstatus: accepted\nslug: {slug}\n---\nbody\n", "WI-DECISION-IDENTITY-MISMATCH"),
        "wrong-date": ("---\nstatus: accepted\ndate: 2026-08-02\n---\nbody\n", "WI-DECISION-DATE-MISMATCH"),
        "empty-body": ("---\nstatus: accepted\n---\n \n", "WI-DECISION-V0-SCHEMA-INVALID"),
    }
    for name, (payload, failure_id) in cases.items():
        path = tmp_path / name / f"{slug}.md"
        write(path, payload)
        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module._validate_current_decision_record(path, slug)
        assert caught.exception.failure_id == failure_id, (name, caught.exception.failure_id)

    cutover_slug = "2026-08-18-new-v0"
    cutover = tmp_path / f"{cutover_slug}.md"
    write(cutover, _legacy_v0_decision_record())
    with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
        module._validate_current_decision_record(
            cutover,
            cutover_slug,
            v0_cutover_date="2026-08-18",
        )
    assert caught.exception.failure_id == "WI-DECISION-V0-CUTOVER-VIOLATION"


def test_decision_v0_manifest_admits_frozen_53_row_inventory_without_writes(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    entries: list[dict[str, str]] = []
    identity_counts = {"id": 0, "slug": 0, "neither": 0}
    for index in range(53):
        day = 1 + index // 28
        slug = f"2026-07-{day:02d}-legacy-{index:02d}"
        if index < 2:
            identity = f"id: {slug}"
            identity_counts["id"] += 1
        elif index < 27:
            identity = f"slug: {slug[11:]}"
            identity_counts["slug"] += 1
        else:
            identity = None
            identity_counts["neither"] += 1
        path = root / "work-items" / "decisions" / f"{slug}.md"
        write(path, _legacy_v0_decision_record(identity_line=identity))
        entries.append(
            {
                "path": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest().upper(),
                "state": "admitted",
            }
        )
    manifest = _write_decision_v0_manifest(root, entries)
    before = {
        path: path.read_bytes()
        for path in (root / "work-items" / "decisions").glob("*.md")
    }
    manifest_before = manifest.read_bytes()
    with patch.object(module, "_atomic_write") as atomic_write, patch.object(
        module.os,
        "replace",
    ) as replace_file:
        admitted = module.audit_categories(root)
    assert len(admitted) == 53
    assert identity_counts == {"id": 2, "slug": 25, "neither": 26}
    assert atomic_write.call_count == 0
    assert replace_file.call_count == 0
    assert manifest.read_bytes() == manifest_before
    assert all(path.read_bytes() == data for path, data in before.items())


def test_decision_v0_manifest_fail_closed_state_matrix(tmp_path: Path) -> None:
    module = load_module()

    def seeded(name: str, *, state: str = "admitted") -> tuple[Path, Path, Path]:
        root = tmp_path / name
        slug = "2026-08-01-legacy"
        decision = root / "work-items" / "decisions" / f"{slug}.md"
        write(decision, _legacy_v0_decision_record(identity_line=f"id: {slug}"))
        entry = {
            "path": decision.name,
            "sha256": hashlib.sha256(decision.read_bytes()).hexdigest().upper(),
            "state": state,
        }
        manifest = _write_decision_v0_manifest(root, [entry])
        return root, decision, manifest

    absent_root = tmp_path / "absent"
    write(
        absent_root / "work-items" / "decisions" / "2026-08-01-legacy.md",
        _legacy_v0_decision_record(),
    )
    with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
        module.audit_categories(absent_root)
    assert caught.exception.failure_id == "WI-DECISION-V0-MANIFEST-MISSING"

    cases = [
        ("hash", "WI-DECISION-V0-HASH-MISMATCH", lambda _r, d, _m: d.write_text(d.read_text(encoding="utf-8") + "drift\n", encoding="utf-8")),
        ("delete", "WI-DECISION-V0-MANIFEST-STALE", lambda _r, d, _m: d.unlink()),
        ("convert", "WI-DECISION-V0-MANIFEST-STALE", lambda _r, d, _m: d.write_text(_canonical_decision_record(d.stem), encoding="utf-8")),
        ("retired-reappear", "WI-DECISION-V0-RETIRED-REAPPEARED", lambda _r, _d, _m: None),
    ]
    for name, failure_id, mutate in cases:
        root, decision, manifest = seeded(
            name,
            state="retired" if name == "retired-reappear" else "admitted",
        )
        before_manifest = manifest.read_bytes()
        mutate(root, decision, manifest)
        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module.audit_categories(root)
        assert caught.exception.failure_id == failure_id, (name, caught.exception.failure_id)
        assert manifest.read_bytes() == before_manifest

    retired_root, retired_decision, retired_manifest = seeded("retired", state="retired")
    retired_decision.unlink()
    retired_before = retired_manifest.read_bytes()
    assert module.audit_categories(retired_root) == ()
    assert retired_manifest.read_bytes() == retired_before

    for name in ("new", "copy", "backdated"):
        root, decision, manifest = seeded(name)
        new_name = "2026-07-01-copy.md" if name == "backdated" else f"2026-08-02-{name}.md"
        shutil.copy2(decision, decision.parent / new_name)
        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module.audit_categories(root)
        assert caught.exception.failure_id == "WI-DECISION-V0-UNADMITTED", name


def test_decision_v0_manifest_rejects_invalid_shape_anchor_and_duplicate_json(
    tmp_path: Path,
) -> None:
    module = load_module()

    def seeded(name: str) -> tuple[Path, Path]:
        root = tmp_path / name
        decision = root / "work-items" / "decisions" / "2026-08-01-legacy.md"
        write(decision, _legacy_v0_decision_record())
        manifest = _write_decision_v0_manifest(
            root,
            [
                {
                    "path": decision.name,
                    "sha256": hashlib.sha256(decision.read_bytes()).hexdigest().upper(),
                    "state": "admitted",
                }
            ],
        )
        return root, manifest

    mutations = {
        "unknown-field": lambda payload: payload.update({"extra": True}),
        "schema": lambda payload: payload.update({"schemaVersion": 2}),
        "traversal": lambda payload: payload["entries"][0].update({"path": "../legacy.md"}),
        "lower-hash": lambda payload: payload["entries"][0].update({"sha256": payload["entries"][0]["sha256"].lower()}),
        "state": lambda payload: payload["entries"][0].update({"state": "pending"}),
        "duplicate-entry": lambda payload: payload["entries"].append(dict(payload["entries"][0])),
        "unsorted-entries": lambda payload: payload["entries"].append(
            {
                "path": "2026-07-01-earlier.md",
                "sha256": "A" * 64,
                "state": "retired",
            }
        ),
    }
    for name, mutate in mutations.items():
        root, manifest = seeded(name)
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        mutate(payload)
        manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module.audit_categories(root)
        assert caught.exception.failure_id == "WI-DECISION-V0-MANIFEST-INVALID", (name, caught.exception.failure_id)

    root, manifest = seeded("duplicate-json")
    manifest.write_text(manifest.read_text(encoding="utf-8").replace('"schemaVersion": 1,', '"schemaVersion": 1,\n  "schemaVersion": 1,'), encoding="utf-8")
    with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
        module.audit_categories(root)
    assert caught.exception.failure_id == "WI-DECISION-V0-MANIFEST-INVALID"

    root, manifest = seeded("unaccepted-anchor")
    policy = root / "work-items" / "decisions" / "2026-08-18-current-decision-schema-versioned-read-compatibility.md"
    policy.write_text(policy.read_text(encoding="utf-8").replace("- status: accepted\n", "- status: proposed\n"), encoding="utf-8")
    with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
        module.audit_categories(root)
    assert caught.exception.failure_id == "WI-DECISION-V0-MANIFEST-INVALID"


def test_decision_v0_manifest_is_repo_local_and_has_no_retirement_writer(
    tmp_path: Path,
) -> None:
    module = load_module()
    for repo_name, slug in (("one", "2026-08-01-one"), ("two", "2026-08-02-two")):
        root = tmp_path / repo_name
        decision = root / "work-items" / "decisions" / f"{slug}.md"
        write(decision, _legacy_v0_decision_record(identity_line=f"id: {slug}"))
        _write_decision_v0_manifest(
            root,
            [
                {
                    "path": decision.name,
                    "sha256": hashlib.sha256(decision.read_bytes()).hexdigest().upper(),
                    "state": "admitted",
                }
            ],
        )
        assert module.audit_categories(root) == (f"decisions/{slug}.md",)
    assert not hasattr(module, "retire_decision_v0")
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "mcp-local-hub" not in source
    assert "F4AF62741FD4BEFC59AA3FEC95EDC88E995CD477B4551F53A2AFB403234A3A6F" not in source
    preflight_source = source.split("def _preflight_current_decision_v0", 1)[1].split("\ndef ", 1)[0]
    for mutation_token in ("write_text(", "write_bytes(", "os.replace(", ".unlink(", ".rename("):
        assert mutation_token not in preflight_source
    repository = Path(__file__).resolve().parents[1]
    for contract_path, no_fence_marker in (
        (repository / "docs" / "decisions.md", "NO `---` YAML fences"),
        (repository / "src.codex" / "skills" / "lead" / "SKILL.md", "no `---` fences"),
        (repository / "src.claude" / "skills" / "lead" / "SKILL.md", "no `---` fences"),
    ):
        contract = contract_path.read_text(encoding="utf-8")
        assert "list-item" in contract
        assert no_fence_marker in contract


def test_decision_h1_parser_accepts_closed_modes_and_opaque_body(tmp_path: Path) -> None:
    module = load_module()
    cases = (
        ("plain", "accepted (prefix authority)", "status", "accepted"),
        ("bold", "ACCEPTED 2026-07-01 — annotated", "status", "accepted"),
        ("bold", "proposed (deferred)", "Status", "proposed"),
    )
    for index, (mode, raw_status, status_key, admitted) in enumerate(cases):
        slug = f"2026-07-{index + 1:02d}-h1-{mode}"
        path = tmp_path / f"{slug}.md"
        body = "status: dropped\n\nBody metadata is opaque.\n"
        write(
            path,
            _legacy_h1_decision_record(
                mode=mode,
                status=raw_status,
                status_key=status_key,
                body=body,
            ),
        )
        result = module._validate_current_decision_record(path, slug)
        assert result.format == "legacy-markdown-h1-v0"
        assert result.raw_status == raw_status
        assert result.admitted_current_status == admitted
        assert result.legacy_read_only is True
        assert result.fields[status_key] == raw_status
        assert "id" not in result.fields and "slug" not in result.fields
        normalized = path.read_text(encoding="utf-8").encode("utf-8")
        assert normalized[result.body_offset :].decode("utf-8") == body
        with unittest.TestCase().assertRaises(TypeError):
            result.fields["invented"] = "value"

    cutover_slug = "2026-08-18-new-h1"
    cutover = tmp_path / f"{cutover_slug}.md"
    write(cutover, _legacy_h1_decision_record())
    with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
        module._validate_current_decision_record(
            cutover,
            cutover_slug,
            h1_cutover_date="2026-08-18",
        )
    assert caught.exception.failure_id == "WI-DECISION-H1-CUTOVER-VIOLATION"


def test_decision_h1_parser_rejects_malformed_prefix_without_fallback(tmp_path: Path) -> None:
    module = load_module()
    slug = "2026-07-01-h1-invalid"
    cases = {
        "empty-title": ("# \n\nstatus: accepted\n\nbody\n", "WI-DECISION-FORMAT-UNSUPPORTED"),
        "missing-line-two": ("# Title\nstatus: accepted\n\nbody\n", "WI-DECISION-H1-SCHEMA-INVALID"),
        "empty-body": ("# Title\n\nstatus: accepted\n\n \n", "WI-DECISION-H1-SCHEMA-INVALID"),
        "mixed-mode": ("# Title\n\nstatus: accepted\n- **owner:** one\n\nbody\n", "WI-DECISION-H1-SCHEMA-INVALID"),
        "tab": ("# Title\n\nstatus:\taccepted\n\nbody\n", "WI-DECISION-H1-SCHEMA-INVALID"),
        "indented": ("# Title\n\n status: accepted\n\nbody\n", "WI-DECISION-H1-SCHEMA-INVALID"),
        "malformed-bold": ("# Title\n\n- **status**: accepted\n\nbody\n", "WI-DECISION-H1-SCHEMA-INVALID"),
        "normalized-duplicate": ("# Title\n\nstatus: accepted\nowner name: one\nOwner_name: two\n\nbody\n", "WI-DECISION-H1-FIELD-DUPLICATE"),
        "duplicate-status": ("# Title\n\nstatus: accepted\nStatus: accepted\n\nbody\n", "WI-DECISION-H1-STATUS-UNSUPPORTED"),
        "non-first-status": ("# Title\n\nowner: one\nstatus: accepted\n\nbody\n", "WI-DECISION-H1-STATUS-UNSUPPORTED"),
        "unsupported-status": ("# Title\n\nstatus: dropped\n\nbody\n", "WI-DECISION-H1-STATUS-UNSUPPORTED"),
        "punctuated-token": ("# Title\n\nstatus: accepted, maybe\n\nbody\n", "WI-DECISION-H1-STATUS-UNSUPPORTED"),
        "body-only-status": ("# Title\n\nowner: one\n\nstatus: accepted\n", "WI-DECISION-H1-STATUS-UNSUPPORTED"),
        "bom": ("\ufeff# Title\n\nstatus: accepted\n\nbody\n", "WI-DECISION-FORMAT-UNSUPPORTED"),
    }
    for name, (payload, failure_id) in cases.items():
        path = tmp_path / name / f"{slug}.md"
        write(path, payload)
        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module._validate_current_decision_record(path, slug)
        assert caught.exception.failure_id == failure_id, (name, caught.exception.failure_id)

    invalid_utf8 = tmp_path / "invalid-utf8" / f"{slug}.md"
    invalid_utf8.parent.mkdir(parents=True)
    invalid_utf8.write_bytes(b"# Title\n\nstatus: accepted\n\nbody\xff\n")
    with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
        module._validate_current_decision_record(invalid_utf8, slug)
    assert caught.exception.failure_id == "WI-DECISION-SCHEMA-INVALID"


def test_decision_h1_manifest_admits_13_rows_deterministically_without_writes(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    entries: list[dict[str, str]] = []
    expected_statuses: dict[str, str] = {}
    decision_bytes: dict[Path, bytes] = {}
    for index in range(13):
        slug = f"2026-07-{index + 1:02d}-h1-{index:02d}"
        mode = "plain" if index < 7 else "bold"
        status = "proposed (deferred)" if index in {7, 8} else "accepted (frozen)"
        path = root / "work-items" / "decisions" / f"{slug}.md"
        write(
            path,
            _legacy_h1_decision_record(
                mode=mode,
                status=status,
                status_key="Status" if index == 12 else "status",
                body="status: dropped\n\nOpaque body.\n" if index == 6 else "Opaque body.\n",
            ),
        )
        entries.append(
            {
                "path": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest().upper(),
                "state": "admitted",
            }
        )
        expected_statuses[path.name] = "proposed" if index in {7, 8} else "accepted"
        decision_bytes[path] = path.read_bytes()
    manifest = _write_decision_h1_manifest(root, entries)
    manifest_before = manifest.read_bytes()
    original_parse_fields = module._parse_fields

    def reject_h1_loose_scan(text: str) -> dict[str, str]:
        if text.startswith("# "):
            raise AssertionError("admitted H1 reached loose whole-document field scan")
        return original_parse_fields(text)

    with patch.object(module, "_parse_fields", side_effect=reject_h1_loose_scan), patch.object(
        module,
        "_atomic_write",
    ) as atomic_write, patch.object(module.os, "replace") as replace_file:
        observed = tuple(module.audit_categories(root) for _ in range(3))
    expected = tuple(f"decisions/{name}" for name in sorted(expected_statuses))
    assert observed == (expected, expected, expected)
    admitted = module._preflight_current_decision_h1(root)
    assert {name: row.admitted_current_status for name, row in admitted.items()} == expected_statuses
    assert atomic_write.call_count == 0 and replace_file.call_count == 0
    assert manifest.read_bytes() == manifest_before
    assert all(path.read_bytes() == payload for path, payload in decision_bytes.items())


def test_decision_h1_manifest_fail_closed_state_matrix(tmp_path: Path) -> None:
    module = load_module()

    def assert_read_only_failure(root: Path, failure_id: str) -> None:
        with patch.object(module, "_atomic_write") as atomic_write, patch.object(
            module.os,
            "replace",
        ) as replace_file, unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module.audit_categories(root)
        assert caught.exception.failure_id == failure_id, caught.exception.failure_id
        assert atomic_write.call_count == 0 and replace_file.call_count == 0

    def seeded(name: str, *, state: str = "admitted", slug: str = "2026-07-01-h1") -> tuple[Path, Path, Path]:
        root = tmp_path / name
        decision = root / "work-items" / "decisions" / f"{slug}.md"
        write(decision, _legacy_h1_decision_record())
        manifest = _write_decision_h1_manifest(
            root,
            [
                {
                    "path": decision.name,
                    "sha256": hashlib.sha256(decision.read_bytes()).hexdigest().upper(),
                    "state": state,
                }
            ],
        )
        return root, decision, manifest

    missing_root = tmp_path / "missing"
    write(
        missing_root / "work-items" / "decisions" / "2026-07-01-h1.md",
        _legacy_h1_decision_record(),
    )
    assert_read_only_failure(missing_root, "WI-DECISION-H1-MANIFEST-MISSING")

    cases = (
        ("hash", "admitted", "WI-DECISION-H1-HASH-MISMATCH", lambda decision: decision.write_text(decision.read_text(encoding="utf-8") + "drift\n", encoding="utf-8")),
        ("delete", "admitted", "WI-DECISION-H1-MANIFEST-STALE", lambda decision: decision.unlink()),
        ("convert", "admitted", "WI-DECISION-H1-MANIFEST-STALE", lambda decision: decision.write_text(_canonical_decision_record(decision.stem), encoding="utf-8")),
        ("retired-reappear", "retired", "WI-DECISION-H1-RETIRED-REAPPEARED", lambda _decision: None),
    )
    for name, state, failure_id, mutate in cases:
        root, decision, manifest = seeded(name, state=state)
        manifest_before = manifest.read_bytes()
        mutate(decision)
        assert_read_only_failure(root, failure_id)
        assert manifest.read_bytes() == manifest_before

    retired_root, retired_decision, retired_manifest = seeded("retired", state="retired")
    retired_decision.unlink()
    retired_before = retired_manifest.read_bytes()
    assert module.audit_categories(retired_root) == ()
    assert retired_manifest.read_bytes() == retired_before

    for name, new_slug in (
        ("new", "2026-07-02-new"),
        ("copy", "2026-07-03-copy"),
        ("backdated", "2026-06-01-backdated"),
    ):
        root, decision, _manifest = seeded(name)
        shutil.copy2(decision, decision.parent / f"{new_slug}.md")
        assert_read_only_failure(root, "WI-DECISION-H1-UNADMITTED")

    cutover_root, _decision, _manifest = seeded(
        "cutover",
        slug="2026-08-18-cutover-h1",
    )
    assert_read_only_failure(cutover_root, "WI-DECISION-H1-CUTOVER-VIOLATION")


def test_decision_h1_manifest_rejects_invalid_shape_and_anchor(tmp_path: Path) -> None:
    module = load_module()

    def seeded(name: str) -> tuple[Path, Path]:
        root = tmp_path / name
        decision = root / "work-items" / "decisions" / "2026-07-01-h1.md"
        write(decision, _legacy_h1_decision_record())
        manifest = _write_decision_h1_manifest(
            root,
            [{"path": decision.name, "sha256": hashlib.sha256(decision.read_bytes()).hexdigest().upper(), "state": "admitted"}],
        )
        return root, manifest

    mutations = {
        "unknown-field": lambda payload: payload.update({"extra": True}),
        "schema": lambda payload: payload.update({"schemaVersion": 2}),
        "traversal": lambda payload: payload["entries"][0].update({"path": "../h1.md"}),
        "lower-hash": lambda payload: payload["entries"][0].update({"sha256": payload["entries"][0]["sha256"].lower()}),
        "state": lambda payload: payload["entries"][0].update({"state": "pending"}),
        "duplicate-entry": lambda payload: payload["entries"].append(dict(payload["entries"][0])),
        "unsorted-entries": lambda payload: payload["entries"].append(
            {"path": "2026-06-01-earlier.md", "sha256": "A" * 64, "state": "retired"}
        ),
    }
    for name, mutate in mutations.items():
        root, manifest = seeded(name)
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        mutate(payload)
        manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module.audit_categories(root)
        assert caught.exception.failure_id == "WI-DECISION-H1-MANIFEST-INVALID", name

    root, manifest = seeded("duplicate-json")
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            '"schemaVersion": 1,',
            '"schemaVersion": 1,\n  "schemaVersion": 1,',
        ),
        encoding="utf-8",
    )
    with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
        module.audit_categories(root)
    assert caught.exception.failure_id == "WI-DECISION-H1-MANIFEST-INVALID"

    root, _manifest = seeded("unaccepted-anchor")
    policy = root / "work-items" / "decisions" / "2026-08-18-current-decision-schema-h1-read-compatibility.md"
    policy.write_text(
        policy.read_text(encoding="utf-8").replace("- status: accepted\n", "- status: proposed\n"),
        encoding="utf-8",
    )
    with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
        module.audit_categories(root)
    assert caught.exception.failure_id == "WI-DECISION-H1-MANIFEST-INVALID"


def test_decision_h1_manifest_is_separate_generic_and_fail_closed(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "combined"
    v0_path = root / "work-items" / "decisions" / "2026-07-01-v0.md"
    h1_path = root / "work-items" / "decisions" / "2026-07-02-h1.md"
    write(v0_path, _legacy_v0_decision_record(identity_line=f"id: {v0_path.stem}"))
    write(h1_path, _legacy_h1_decision_record(mode="bold", status="PROPOSED later"))
    v0_manifest = _write_decision_v0_manifest(
        root,
        [{"path": v0_path.name, "sha256": hashlib.sha256(v0_path.read_bytes()).hexdigest().upper(), "state": "admitted"}],
    )
    h1_manifest = _write_decision_h1_manifest(
        root,
        [{"path": h1_path.name, "sha256": hashlib.sha256(h1_path.read_bytes()).hexdigest().upper(), "state": "admitted"}],
    )
    v0_before = v0_manifest.read_bytes()
    h1_before = h1_manifest.read_bytes()
    assert module.audit_categories(root) == (
        "decisions/2026-07-01-v0.md",
        "decisions/2026-07-02-h1.md",
    )
    assert v0_manifest.read_bytes() == v0_before
    assert h1_manifest.read_bytes() == h1_before

    payload = json.loads(h1_manifest.read_text(encoding="utf-8"))
    payload["entries"].append(dict(payload["entries"][0]))
    h1_manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
        module.audit_categories(root)
    assert caught.exception.failure_id == "WI-DECISION-H1-MANIFEST-INVALID"
    assert v0_manifest.read_bytes() == v0_before

    source = Path(module.__file__).read_text(encoding="utf-8")
    assert source.count("def _verify_current_decision_compatibility_manifest") == 1
    assert "2D873AB6EE1D6B026EEFD59879F538BA6DE8DBAB23C66646DD05FD7065D4137E" not in source
    assert "2026-06-16-hot-swap-zero-downtime-config" not in source
    assert not hasattr(module, "retire_decision_h1")
    h1_preflight = source.split("def _preflight_current_decision_h1", 1)[1].split("\ndef ", 1)[0]
    for mutation_token in ("write_text(", "write_bytes(", "os.replace(", ".unlink(", ".rename("):
        assert mutation_token not in h1_preflight


def test_decision_h1_failure_order_is_lexical_across_processes(tmp_path: Path) -> None:
    root = tmp_path / "ordered"
    entries: list[dict[str, str]] = []
    for slug, status in (
        ("2026-07-01-a-invalid", "dropped"),
        ("2026-07-02-z-invalid", "reverted"),
    ):
        path = root / "work-items" / "decisions" / f"{slug}.md"
        write(path, _legacy_h1_decision_record(status=status))
        entries.append(
            {
                "path": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest().upper(),
                "state": "admitted",
            }
        )
    _write_decision_h1_manifest(root, entries)
    observed: list[str] = []
    for seed in ("1", "7", "41", "99"):
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = seed
        process = subprocess.run(
            [sys.executable, str(SCRIPT), "audit", "--root", str(root)],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        assert process.returncode != 0
        assert "WI-DECISION-H1-STATUS-UNSUPPORTED" in process.stdout
        observed.append(process.stdout)
    assert all("2026-07-01-a-invalid" in output for output in observed)
    assert all("2026-07-02-z-invalid" not in output for output in observed)


class PartialMigrationRecoveryParserTests(unittest.TestCase):
    def _inventory_bytes(self, root: Path, *, suffix: str = "") -> bytes:
        work_items = (root / "work-items").resolve()
        return (
            "{"
            f'"digestAlgorithms":{{"directory":"sha256-tree-entries-v1","file":"sha256-file-bytes-v1"}},'
            f'"owner":"work-items-lifecycle-v1-migration",{suffix}'
            '"rows":[],"schemaVersion":1,'
            f'"workItemsRoot":{json.dumps(str(work_items))}'
            "}\n"
        ).encode("utf-8")

    def test_byte_parser_rejects_duplicate_json_keys(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = self._inventory_bytes(
                root,
                suffix='"owner":"work-items-lifecycle-v1-migration",',
            )
            with self.assertRaises(module.LifecycleError) as caught:
                module._parse_migration_inventory_bytes(root, snapshot, strict_shape=True)
            self.assertEqual(
                caught.exception.failure_id,
                "WI-CATEGORY-MIGRATION-INVENTORY",
            )

    def test_path_loader_delegates_exact_bytes_to_strict_parser(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inventory_path = root / "inventory.json"
            snapshot = self._inventory_bytes(root)
            inventory_path.write_bytes(snapshot)
            sentinel = {"parsed": True}
            with patch.object(
                module,
                "_parse_migration_inventory_bytes",
                return_value=sentinel,
            ) as parser:
                self.assertIs(
                    module._load_migration_inventory(root, inventory_path),
                    sentinel,
                )
            parser.assert_called_once_with(root, snapshot)

    def test_byte_parser_rejects_unknown_top_level_fields(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = self._inventory_bytes(root).replace(
                b'"rows":[]',
                b'"unexpected":true,"rows":[]',
            )
            with self.assertRaises(module.LifecycleError) as caught:
                module._parse_migration_inventory_bytes(root, snapshot, strict_shape=True)
            self.assertEqual(
                caught.exception.failure_id,
                "WI-CATEGORY-MIGRATION-INVENTORY",
            )


class LifecycleTransactionTests(unittest.TestCase):
    def _holder(self, root: Path, *, crash: bool = False) -> subprocess.Popen[str]:
        body = (
            "import importlib.util,os,sys;"
            "from pathlib import Path;"
            f"p=Path({str(SCRIPT)!r});"
            "s=importlib.util.spec_from_file_location('transaction_holder',p);"
            "m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;"
            "s.loader.exec_module(m);"
            "t=m.LifecycleTransaction(Path(sys.argv[1]));t.__enter__();"
            "print('LOCKED',flush=True);"
            + ("os._exit(23)" if crash else "sys.stdin.readline();t.__exit__(None,None,None)")
        )
        return subprocess.Popen(
            [sys.executable, "-c", body, str(root)],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def test_live_owner_contention_fails_closed_and_releases_after_exit(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            holder = self._holder(root)
            locked = holder.stdout.readline().strip()
            try:
                if locked == "LOCKED":
                    with self.assertRaises(module.LifecycleError) as caught:
                        with module.LifecycleTransaction(root):
                            self.fail("contending owner entered the transaction")
                    self.assertEqual(
                        caught.exception.failure_id,
                        "WI-LIFECYCLE-LOCK-HELD",
                    )
            finally:
                if holder.stdin and locked == "LOCKED":
                    holder.stdin.write("release\n")
                    holder.stdin.flush()
                stdout, stderr = holder.communicate(timeout=10)
                if holder.returncode == 0:
                    self.assertEqual(stderr, "")
            self.assertEqual(locked, "LOCKED", stderr)
            with module.LifecycleTransaction(root):
                pass

    def test_every_public_lifecycle_api_uses_the_common_transaction(self):
        module = load_module()
        expected = {
            "resolve_category",
            "work_item_dependency_state",
            "resolve_legacy_path",
            "collect_readme_entries",
            "render_readme_bytes",
            "refresh_readme",
            "reset_readme_static_guide",
            "check_readme",
            "create_candidate",
            "convert_legacy_candidate",
            "retire_legacy_backlog",
            "start_item",
            "update_status",
            "close_item",
            "reopen_item",
            "audit_categories",
            "audit",
            "write_current_identity_normalization_inventory",
            "normalize_current_identity",
            "migrate_legacy_ledger_obligation",
            "revoke_legacy_ledger_obligation",
            "archive_with_successor",
            "build_migration_inventory",
            "write_migration_inventory",
            "migrate_legacy",
            "terminalize_v1_inventory",
            "apply_migration_inventory",
            "recover_partial_migration_v1",
            "verify_migration_inventory",
            "reopen_category_record",
            "run_trial",
        }
        self.assertEqual(set(module.LIFECYCLE_PUBLIC_APIS), expected)
        for name in sorted(expected):
            with self.subTest(name=name):
                self.assertTrue(
                    getattr(
                        getattr(module, name),
                        "__lifecycle_transaction_participant__",
                        False,
                    ),
                    name,
                )

    def test_process_crash_releases_native_lock(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            holder = self._holder(root, crash=True)
            self.assertEqual(holder.stdout.readline().strip(), "LOCKED")
            stdout, stderr = holder.communicate(timeout=10)
            self.assertEqual(holder.returncode, 23, stdout + stderr)
            with module.LifecycleTransaction(root):
                pass


class PartialMigrationRecoveryBehaviorTests(unittest.TestCase):
    WORK_ITEM_ROWS = (
        (
            "work-item:2026-08-11-pr598-review-fix",
            "2026-08-11-pr598-review-fix",
            "2026-08-11T10:50:44Z",
        ),
        (
            "work-item:2026-08-11-pr600-review-fix",
            "2026-08-11-pr600-review-fix",
            "2026-08-11T10:53:49Z",
        ),
    )
    BUG_ROWS = (
        (
            "bug:2026-07-25-cleanup-aggressive-exe-extension-index-out-of-range-panic",
            "2026-07-25-cleanup-aggressive-exe-extension-index-out-of-range-panic",
        ),
        (
            "bug:2026-07-26-route-daemon-state-read-unhardened-parent-fallback-writes-hub-mcp-log",
            "2026-07-26-route-daemon-state-read-unhardened-parent-fallback-writes-hub-mcp-log",
        ),
    )

    def test_recovery_scratch_paths_reject_unreduced_reparse_participants(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "repository"
            scratch = root / ".scratch"
            scratch.mkdir(parents=True)
            inventory = scratch / "inventory.json"
            inventory.write_bytes(b"{}\n")
            receipt_parent = scratch / "receipt-target"
            receipt_parent.mkdir()
            cases = []
            try:
                inventory_link = scratch / "inventory-link.json"
                os.symlink(inventory, inventory_link)
                cases.append((root, Path(".scratch/inventory-link.json"), "inventory"))

                receipt_parent_link = scratch / "receipt-parent-link"
                os.symlink(
                    receipt_parent,
                    receipt_parent_link,
                    target_is_directory=True,
                )
                cases.append(
                    (
                        root,
                        Path(".scratch/receipt-parent-link/receipt.json"),
                        "receipt",
                    )
                )

                root_link = base / "repository-link"
                os.symlink(root, root_link, target_is_directory=True)
                cases.append((root_link, Path(".scratch/inventory.json"), "inventory"))
            except OSError as exc:
                self.skipTest(f"target environment cannot create symlinks: {exc}")

            for recovery_root, candidate, label in cases:
                with self.subTest(candidate=candidate, label=label):
                    with self.assertRaises(module.LifecycleError) as caught:
                        module._partial_recovery_bound_scratch_file(
                            recovery_root,
                            candidate,
                            label=label,
                        )
                    self.assertEqual(
                        caught.exception.failure_id,
                        "WI-PARTIAL-MIGRATION-RECOVERY-INVENTORY",
                    )

    def test_inventory_paths_reject_unreduced_root_and_target_parent_reparse(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real_work_items = root / "real-work-items"
            real_work_items.mkdir()
            work_items_link = root / "work-items-link"
            real_parent = real_work_items / "real-archive-parent"
            real_parent.mkdir()
            target_parent_link = real_work_items / "target-parent-link"
            try:
                os.symlink(real_work_items, work_items_link, target_is_directory=True)
                os.symlink(real_parent, target_parent_link, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"target environment cannot create symlinks: {exc}")

            cases = (
                (work_items_link, "incident-target"),
                (real_work_items, "target-parent-link/incident-target"),
            )
            for work_items, relative in cases:
                with self.subTest(work_items=work_items, relative=relative):
                    with self.assertRaises(module.LifecycleError) as caught:
                        module._bound_inventory_path(work_items, relative)
                    self.assertEqual(
                        caught.exception.failure_id,
                        "WI-CATEGORY-MIGRATION-INVENTORY",
                    )

    def test_status_parent_reparse_swap_after_preflight_refuses_before_any_write(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._fixture(module, root)
            real_preflight = module._partial_recovery_preflight
            real_atomic_write = module._atomic_write
            attempted_writes = []

            def swap_after_preflight(recovery_root, inventory):
                plans = real_preflight(recovery_root, inventory)
                month = root / "work-items" / "archive" / "2026-08"
                moved = month.with_name("2026-08-real")
                month.rename(moved)
                try:
                    os.symlink(moved, month, target_is_directory=True)
                except OSError as exc:
                    moved.rename(month)
                    self.skipTest(
                        f"target environment cannot create a directory symlink: {exc}"
                    )
                return plans

            def recording_atomic_write(path, data):
                attempted_writes.append(Path(path))
                return real_atomic_write(path, data)

            try:
                with patch.object(
                    module,
                    "_partial_recovery_preflight",
                    side_effect=swap_after_preflight,
                ), patch.object(
                    module,
                    "_atomic_write",
                    side_effect=recording_atomic_write,
                ):
                    with self.assertRaises(module.LifecycleError):
                        self._run(module, root, fixture)
            finally:
                month = root / "work-items" / "archive" / "2026-08"
                if month.is_symlink():
                    month.unlink()
            self.assertEqual(attempted_writes, [])

    def _fixture(self, module, root: Path):
        work_items = root / "work-items"
        work_items.mkdir(parents=True)
        module.refresh_readme(root, allow_marker_bootstrap=True)
        readme = work_items / "README.md"
        expected_readme_sha256 = hashlib.sha256(readme.read_bytes()).hexdigest()
        rows = []
        unchanged = {}
        closures = {}
        targets = {}
        for index, (reference, slug) in enumerate(self.BUG_ROWS, start=1):
            target = work_items / "bugs" / "archive" / "2026-08" / f"{slug}.md"
            write(
                target,
                "status: fixed\n"
                "Terminal-at: 2026-08-17T18:25:44Z\n"
                f"Resolution: synthetic recovery fixture {index}\n"
                "Evidence: focused recovery test\n",
            )
            algorithm, digest = module._payload_digest(target)
            unchanged[reference] = digest
            rows.append(
                {
                    "admission": {
                        "negativeFixture": "bug_terminal_evidence_missing",
                        "reader": "mutate-work-item:_category_locations",
                        "result": "admitted",
                        "utcOwner": "bug:Terminal-at",
                        "validator": "mutate-work-item:_validate_flat_terminal",
                    },
                    "category": "bug",
                    "digestAlgorithm": algorithm,
                    "incomingLinks": {"references": [], "result": "clear"},
                    "inputSha256": digest,
                    "reference": reference,
                    "source": f"bugs/{slug}.md",
                    "target": f"bugs/archive/2026-08/{slug}.md",
                    "terminalInstant": "2026-08-17T18:25:44Z",
                }
            )
        for reference, slug, instant in self.WORK_ITEM_ROWS:
            target = work_items / "archive" / "2026-08" / slug
            status = quick_status().encode("utf-8")
            closure_bytes = marked_closure(instant).encode("utf-8")
            (target / "status.md").parent.mkdir(parents=True, exist_ok=True)
            (target / "status.md").write_bytes(status)
            (target / "closure.md").write_bytes(closure_bytes)
            algorithm, before_tree = module._payload_digest(target)
            after_status = module._terminalize_status(status)
            (target / "status.md").write_bytes(after_status)
            _after_algorithm, after_tree = module._payload_digest(target)
            (target / "status.md").write_bytes(status)
            targets[reference] = module.PartialRecoveryTarget(
                reference=reference,
                inventory_tree_preimage=before_tree,
                status_preimage=hashlib.sha256(status).hexdigest(),
                status_afterimage=hashlib.sha256(after_status).hexdigest(),
                projected_tree_afterimage=after_tree,
                closure_sha256=hashlib.sha256(closure_bytes).hexdigest(),
            )
            closures[reference] = closure_bytes
            rows.append(
                {
                    "admission": {
                        "negativeFixture": "work_item_terminal_evidence_missing",
                        "reader": "mutate-work-item:_category_locations",
                        "result": "admitted",
                        "utcOwner": "closure.md:Closed",
                        "validator": "mutate-work-item:_validate_closure",
                    },
                    "category": "work-item",
                    "digestAlgorithm": algorithm,
                    "incomingLinks": {"references": [], "result": "clear"},
                    "inputSha256": before_tree,
                    "reference": reference,
                    "source": f"active/{slug}",
                    "target": f"archive/2026-08/{slug}",
                    "terminalInstant": instant,
                }
            )
        inventory = {
            "digestAlgorithms": module.MIGRATION_DIGEST_ALGORITHMS,
            "owner": module.MIGRATION_OWNER,
            "rows": sorted(rows, key=lambda row: row["reference"]),
            "schemaVersion": module.MIGRATION_SCHEMA_VERSION,
            "workItemsRoot": str(work_items.resolve()),
        }
        inventory_bytes = (
            json.dumps(inventory, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        inventory_path = root / ".scratch" / "recovery-inventory.json"
        inventory_path.parent.mkdir(exist_ok=True)
        inventory_path.write_bytes(inventory_bytes)
        return {
            "inventory": inventory_path,
            "inventory_sha256": hashlib.sha256(inventory_bytes).hexdigest(),
            "expected_readme_sha256": expected_readme_sha256,
            "receipt": root / ".scratch" / "recovery-receipt.json",
            "targets": targets,
            "unchanged": unchanged,
            "closures": closures,
            "status_preimages": {
                reference: target.status_preimage
                for reference, target in targets.items()
            },
        }

    def _run(self, module, root: Path, fixture: dict, **kwargs):
        with patch.multiple(
            module,
            PARTIAL_MIGRATION_RECOVERY_INVENTORY_SHA256=fixture[
                "inventory_sha256"
            ],
            PARTIAL_MIGRATION_RECOVERY_README_PREIMAGE_SHA256=fixture[
                "expected_readme_sha256"
            ],
            PARTIAL_MIGRATION_RECOVERY_TARGETS=fixture["targets"],
            PARTIAL_MIGRATION_RECOVERY_UNCHANGED_ROWS=fixture["unchanged"],
        ):
            return module.recover_partial_migration_v1(
                root,
                fixture["inventory"],
                expected_inventory_sha256=fixture["inventory_sha256"],
                expected_readme_sha256=fixture["expected_readme_sha256"],
                target_status_preimages=fixture["status_preimages"],
                receipt_path=fixture["receipt"],
                apply_admitted=True,
                render_readme=True,
                byte_check=True,
                **kwargs,
            )

    def test_exact_recovery_is_receipt_bound_and_idempotent(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._fixture(module, root)
            result = self._run(module, root, fixture)
            self.assertFalse(result.replay)
            self.assertEqual(result.audit, "PASS")
            self.assertEqual(
                hashlib.sha256(fixture["receipt"].read_bytes()).hexdigest().upper(),
                result.receipt_sha256,
            )
            receipt_payload = json.loads(fixture["receipt"].read_bytes())
            changed_rows = {
                row["reference"]: row
                for row in receipt_payload["rows"]
                if row["action"] == "terminalize-status"
            }
            self.assertEqual(set(changed_rows), set(fixture["targets"]))
            for reference, contract in fixture["targets"].items():
                self.assertEqual(
                    changed_rows[reference]["closureSha256"],
                    contract.closure_sha256.upper(),
                )
            self.assertEqual(
                {
                    row["action"]
                    for row in receipt_payload["rows"]
                    if row["reference"] in fixture["unchanged"]
                },
                {"none"},
            )
            for reference, contract in fixture["targets"].items():
                slug = reference.split(":", 1)[1]
                target = root / "work-items" / "archive" / "2026-08" / slug
                self.assertEqual(
                    hashlib.sha256((target / "status.md").read_bytes()).hexdigest(),
                    contract.status_afterimage,
                )
                self.assertEqual(
                    (target / "closure.md").read_bytes(),
                    fixture["closures"][reference],
                )
                self.assertFalse((root / "work-items" / "active" / slug).exists())
            self.assertEqual(
                (root / "work-items" / "README.md").read_bytes(),
                module.render_readme_bytes(root),
            )
            receipt_before = fixture["receipt"].read_bytes()
            with patch.object(
                module,
                "_atomic_write",
                wraps=module._atomic_write,
            ) as atomic_write:
                result = self._run(module, root, fixture)
            self.assertTrue(result.replay)
            atomic_write.assert_not_called()
            self.assertEqual(fixture["receipt"].read_bytes(), receipt_before)

    def test_failure_after_first_status_rolls_back_then_retry_succeeds(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._fixture(module, root)
            before = {
                reference: (
                    root
                    / "work-items"
                    / "archive"
                    / "2026-08"
                    / reference.split(":", 1)[1]
                    / "status.md"
                ).read_bytes()
                for reference in fixture["targets"]
            }
            with self.assertRaises(module.LifecycleError) as caught:
                self._run(
                    module,
                    root,
                    fixture,
                    inject_failure_at="after-status-1",
                )
            self.assertEqual(
                caught.exception.failure_id,
                "WI-PARTIAL-MIGRATION-RECOVERY-TEST-FAILPOINT",
            )
            self.assertFalse(fixture["receipt"].exists())
            for reference, expected in before.items():
                status = (
                    root
                    / "work-items"
                    / "archive"
                    / "2026-08"
                    / reference.split(":", 1)[1]
                    / "status.md"
                )
                self.assertEqual(status.read_bytes(), expected)
            self.assertEqual(self._run(module, root, fixture).audit, "PASS")

    def test_crash_afterimage_is_reentered_without_rewriting_completed_target(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._fixture(module, root)
            reference = sorted(fixture["targets"])[0]
            contract = fixture["targets"][reference]
            status = (
                root
                / "work-items"
                / "archive"
                / "2026-08"
                / reference.split(":", 1)[1]
                / "status.md"
            )
            crash_afterimage = module._terminalize_status(status.read_bytes())
            self.assertEqual(
                hashlib.sha256(crash_afterimage).hexdigest(),
                contract.status_afterimage,
            )
            status.write_bytes(crash_afterimage)
            completed_before = status.read_bytes()
            result = self._run(module, root, fixture)
            self.assertFalse(result.replay)
            self.assertEqual(status.read_bytes(), completed_before)
            self.assertEqual(self._run(module, root, fixture).replay, True)

    def test_pending_recovery_refuses_preexisting_receipt(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._fixture(module, root)
            fixture["receipt"].write_bytes(b"not-an-authorized-receipt\n")
            with self.assertRaises(module.LifecycleError) as caught:
                self._run(module, root, fixture)
            self.assertEqual(
                caught.exception.failure_id,
                "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT",
            )

    def test_incomplete_exact_prefix_pending_receipt_is_recreated_after_crash(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._fixture(module, root)
            self.assertEqual(self._run(module, root, fixture).audit, "PASS")
            exact_receipt = fixture["receipt"].read_bytes()
            fixture["receipt"].unlink()
            pending = fixture["receipt"].with_name(
                f".{fixture['receipt'].name}.pending-v1"
            )
            pending.write_bytes(exact_receipt[: len(exact_receipt) // 2])
            recovered = self._run(module, root, fixture)
            self.assertFalse(recovered.replay)
            self.assertEqual(fixture["receipt"].read_bytes(), exact_receipt)
            self.assertFalse(pending.exists())

    def test_receipt_settlement_fsyncs_parent_directory_before_success(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            fsync_modes = []
            real_fsync = module.os.fsync

            def recording_fsync(descriptor):
                fsync_modes.append(module.os.fstat(descriptor).st_mode)
                return real_fsync(descriptor)

            with patch.object(module.os, "fsync", side_effect=recording_fsync):
                self.assertTrue(
                    module._partial_recovery_settle_receipt(path, b"authorized\n")
                )
            self.assertTrue(
                any(stat.S_ISDIR(mode) for mode in fsync_modes),
                f"receipt parent directory was not fsynced: {fsync_modes!r}",
            )

    def test_receipt_directory_fsync_failure_cleans_own_link_and_retries(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            data = b"authorized\n"
            with patch.object(
                module,
                "_partial_recovery_fsync_directory",
                side_effect=module.LifecycleError(
                    "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CREATE-UNSUPPORTED",
                    "injected directory durability failure",
                ),
            ), self.assertRaises(module.LifecycleError):
                module._partial_recovery_settle_receipt(path, data)
            self.assertEqual(path.read_bytes(), data)
            self.assertFalse(path.with_name(f".{path.name}.pending-v1").exists())
            self.assertFalse(module._partial_recovery_settle_receipt(path, data))

    def test_late_receipt_conflict_cleanup_does_not_mask_primary(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            path = parent / "receipt.json"
            winner = parent / "winner.json"
            wanted = b"authorized\n"
            winner.write_bytes(wanted)
            real_directory_fsync = module._partial_recovery_fsync_directory

            def replace_after_fsync(directory_path):
                real_directory_fsync(directory_path)
                path.unlink()
                try:
                    os.symlink(winner, path)
                except OSError as exc:
                    self.skipTest(
                        f"target environment cannot create a symlink: {exc}"
                    )

            with patch.object(
                module,
                "_partial_recovery_fsync_directory",
                side_effect=replace_after_fsync,
            ), self.assertRaises(module.LifecycleError) as caught:
                module._partial_recovery_settle_receipt(path, wanted)

            self.assertEqual(
                caught.exception.failure_id,
                "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT",
            )
            self.assertTrue(path.is_symlink())
            self.assertEqual(winner.read_bytes(), wanted)

    def test_exact_receipt_symlink_race_is_conflict_not_success(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            path = parent / "receipt.json"
            winner = parent / "winner.json"
            wanted = b"authorized\n"
            winner.write_bytes(wanted)

            def racing_link(_source, destination):
                try:
                    os.symlink(winner, destination)
                except OSError as exc:
                    self.skipTest(f"target environment cannot create a symlink: {exc}")
                raise FileExistsError(destination)

            with patch.object(module.os, "link", side_effect=racing_link):
                with self.assertRaises(module.LifecycleError) as caught:
                    module._partial_recovery_settle_receipt(path, wanted)
            self.assertEqual(
                caught.exception.failure_id,
                "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT",
            )
            self.assertTrue(path.is_symlink())
            self.assertEqual(winner.read_bytes(), wanted)

    def test_closure_drift_refuses_before_status_write(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._fixture(module, root)
            reference = sorted(fixture["targets"])[0]
            slug = reference.split(":", 1)[1]
            status = root / "work-items" / "archive" / "2026-08" / slug / "status.md"
            closure_path = status.with_name("closure.md")
            before = status.read_bytes()
            closure_path.write_bytes(closure_path.read_bytes() + b"drift\n")
            with self.assertRaises(module.LifecycleError) as caught:
                self._run(module, root, fixture)
            self.assertEqual(
                caught.exception.failure_id,
                "WI-PARTIAL-MIGRATION-RECOVERY-CLOSURE",
            )
            self.assertEqual(status.read_bytes(), before)
            self.assertFalse(fixture["receipt"].exists())

    def test_same_bytes_closure_replacement_identity_refuses_before_status_write(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._fixture(module, root)
            before = {
                reference: (
                    root
                    / "work-items"
                    / "archive"
                    / "2026-08"
                    / reference.split(":", 1)[1]
                    / "status.md"
                ).read_bytes()
                for reference in fixture["targets"]
            }
            real_preflight = module._partial_recovery_preflight

            def replace_closure_identity(recovery_root, inventory):
                plans = real_preflight(recovery_root, inventory)
                closure = plans[0][0]["closure"]
                replacement = closure.with_name(".closure.identity-replacement")
                replacement.write_bytes(closure.read_bytes())
                os.replace(replacement, closure)
                return plans

            with patch.object(
                module,
                "_partial_recovery_preflight",
                side_effect=replace_closure_identity,
            ), self.assertRaises(module.LifecycleError) as caught:
                self._run(module, root, fixture)
            self.assertEqual(
                caught.exception.failure_id,
                "WI-PARTIAL-MIGRATION-RECOVERY-CLOSURE",
            )
            for reference, expected in before.items():
                status = (
                    root
                    / "work-items"
                    / "archive"
                    / "2026-08"
                    / reference.split(":", 1)[1]
                    / "status.md"
                )
                self.assertEqual(status.read_bytes(), expected)
            self.assertFalse(fixture["receipt"].exists())


class PartialMigrationRecoveryCliTests(unittest.TestCase):
    def _argv(self, root: Path) -> list[str]:
        return [
            "recover-partial-migration-v1",
            "--root",
            str(root),
            "--inventory",
            ".scratch/inventory.json",
            "--expected-inventory-sha256",
            "A" * 64,
            "--expected-readme-sha256",
            "B" * 64,
            "--target-status-preimage",
            "work-item:2026-08-11-pr598-review-fix=" + "C" * 64,
            "--target-status-preimage",
            "work-item:2026-08-11-pr600-review-fix=" + "D" * 64,
            "--receipt",
            ".scratch/recovery-receipt.json",
            "--apply-admitted",
            "--render-readme",
            "--byte-check",
        ]

    def test_parser_exposes_only_explicit_recovery_bindings(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            args = module.build_parser().parse_args(self._argv(Path(directory)))
        self.assertEqual(args.command, "recover-partial-migration-v1")
        self.assertEqual(len(args.target_status_preimage), 2)
        self.assertTrue(args.apply_admitted)
        self.assertTrue(args.render_readme)
        self.assertTrue(args.byte_check)

    def test_main_routes_exact_bindings_and_rejects_duplicate_target(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            argv = self._argv(root)
            expected = module.PartialRecoveryResult("E" * 64, "PASS", False)
            with patch.object(
                module,
                "recover_partial_migration_v1",
                return_value=expected,
            ) as recovery, redirect_stdout(io.StringIO()) as output:
                self.assertEqual(module.main(argv), 0)
            call_args, call_kwargs = recovery.call_args
            observer = call_kwargs.pop("diagnostic_observer")
            self.assertIs(type(observer), module.LifecycleDiagnosticObserver)
            self.assertEqual(call_args, (root, Path(".scratch/inventory.json")))
            self.assertEqual(
                call_kwargs,
                {
                    "expected_inventory_sha256": "A" * 64,
                    "expected_readme_sha256": "B" * 64,
                    "target_status_preimages": {
                        "work-item:2026-08-11-pr598-review-fix": "C" * 64,
                        "work-item:2026-08-11-pr600-review-fix": "D" * 64,
                    },
                    "receipt_path": Path(".scratch/recovery-receipt.json"),
                    "apply_admitted": True,
                    "render_readme": True,
                    "byte_check": True,
                },
            )
            self.assertEqual(
                output.getvalue(),
                "PARTIAL-MIGRATION-RECOVERY: PASS "
                + "receipt_sha256="
                + "E" * 64
                + " audit=PASS\n",
            )
            duplicate = argv + [
                "--target-status-preimage",
                "work-item:2026-08-11-pr598-review-fix=" + "F" * 64,
            ]
            with redirect_stdout(io.StringIO()) as error_output:
                self.assertEqual(module.main(duplicate), 1)
            self.assertIn(
                "WI-PARTIAL-MIGRATION-RECOVERY-COVERAGE",
                error_output.getvalue(),
            )

    def test_main_emits_exactly_one_committed_success_event(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            result = module.PartialRecoveryResult("E" * 64, "PASS", False)
            with patch.object(
                module,
                "recover_partial_migration_v1",
                return_value=result,
            ), redirect_stdout(io.StringIO()) as output:
                self.assertEqual(module.main(self._argv(Path(directory))), 0)
            self.assertEqual(
                output.getvalue().splitlines(),
                [
                    "PARTIAL-MIGRATION-RECOVERY: PASS "
                    + "receipt_sha256="
                    + "E" * 64
                    + " audit=PASS"
                ],
            )

    def test_outcome_composer_preserves_primary_and_exact_eight_cleanup_slots(self):
        module = load_module()
        primary = module.LifecycleError(
            "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT",
            "primary receipt conflict",
        )
        composer = module.LifecycleOutcomeComposer()
        composer.capture_primary(primary)
        for index, phase in enumerate(module.LIFECYCLE_CLEANUP_PHASES, start=1):
            composer.record_cleanup(
                phase=phase,
                failure_id="WI-PARTIAL-MIGRATION-RECOVERY-CLEANUP-FAILED",
                resource=f"resource-{index}",
                diagnostic=f"cleanup-{index}",
            )
        composer.set_rollback("incomplete")

        bundle = composer.finalize()

        self.assertIs(bundle.primary, primary)
        self.assertEqual(
            tuple(record.phase for record in bundle.cleanup_failures),
            module.LIFECYCLE_CLEANUP_PHASES,
        )
        self.assertEqual(len(bundle.cleanup_failures), 8)
        self.assertEqual(bundle.rollback, "incomplete")
        with self.assertRaises(Exception):
            bundle.cleanup_failures += ()

    def test_reusable_api_observer_preserves_control_flow_identity_and_zero_streams(self):
        module = load_module()
        primary = KeyboardInterrupt("operator cancellation")
        observer = module.LifecycleDiagnosticObserver()

        @module._lifecycle_participant
        def failing_api(root):
            composer = module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.get()
            composer.record_cleanup(
                phase="receipt-pending",
                failure_id="WI-PARTIAL-MIGRATION-RECOVERY-CLEANUP-FAILED",
                resource=".scratch/.receipt.pending-v1",
                diagnostic="pending unlink failed",
            )
            raise primary

        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            error = io.StringIO()
            with redirect_stdout(output), redirect_stderr(error):
                with self.assertRaises(KeyboardInterrupt) as caught:
                    failing_api(
                        Path(directory),
                        diagnostic_observer=observer,
                    )

        self.assertIs(caught.exception, primary)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(error.getvalue(), "")
        self.assertEqual(observer.state, "delivered")
        self.assertEqual(observer.snapshot.primaryKind, "control-flow")
        self.assertEqual(observer.snapshot.primaryType, "KeyboardInterrupt")
        self.assertEqual(observer.snapshot.topLevelKind, "control-flow-primary")
        self.assertEqual(
            tuple(record.phase for record in observer.snapshot.cleanupFailures),
            ("receipt-pending",),
        )

    def test_reusable_api_asyncio_cancelled_error_is_control_flow_and_same_object(self):
        module = load_module()
        primary = asyncio.CancelledError("cancelled")
        observer = module.LifecycleDiagnosticObserver()

        @module._lifecycle_participant
        def cancelled_api(root):
            composer = module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.get()
            composer.record_cleanup(
                phase="receipt-pending",
                failure_id="WI-PARTIAL-MIGRATION-RECOVERY-CLEANUP-FAILED",
                resource=".scratch/.receipt.pending-v1",
                diagnostic="pending unlink failed",
            )
            raise primary

        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            error = io.StringIO()
            with redirect_stdout(output), redirect_stderr(error):
                with self.assertRaises(asyncio.CancelledError) as caught:
                    cancelled_api(
                        Path(directory),
                        diagnostic_observer=observer,
                    )

        self.assertIs(caught.exception, primary)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(error.getvalue(), "")
        self.assertEqual(observer.state, "delivered")
        self.assertEqual(observer.delivery_attempts, 1)
        self.assertEqual(observer.snapshot.primaryKind, "control-flow")
        self.assertEqual(observer.snapshot.primaryType, "CancelledError")
        self.assertEqual(observer.snapshot.topLevelKind, "control-flow-primary")
        self.assertEqual(
            tuple(record.phase for record in observer.snapshot.cleanupFailures),
            ("receipt-pending",),
        )

    def test_reusable_api_observer_rejection_is_one_shot_and_non_masking(self):
        module = load_module()
        primary = module.LifecycleError("WI-TEST-PRIMARY", "primary")
        observer = module.LifecycleDiagnosticObserver(_reject_delivery=True)

        @module._lifecycle_participant
        def failing_api(root):
            raise primary

        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            error = io.StringIO()
            with redirect_stdout(output), redirect_stderr(error):
                with self.assertRaises(module.LifecycleError) as caught:
                    failing_api(
                        Path(directory),
                        diagnostic_observer=observer,
                    )

        self.assertIs(caught.exception, primary)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(error.getvalue(), "")
        self.assertEqual(observer.state, "delivery-failed")
        self.assertIsNone(observer.snapshot)
        self.assertEqual(
            observer.delivery_failure.failure_id,
            "WI-LIFECYCLE-DIAGNOSTIC-DELIVERY",
        )
        self.assertEqual(observer.delivery_attempts, 1)

    def test_reusable_api_clean_candidate_returns_silently_after_release(self):
        module = load_module()
        observer = module.LifecycleDiagnosticObserver()
        result = module.PartialRecoveryResult("E" * 64, "PASS", False)

        @module._lifecycle_participant
        def successful_api(root):
            return module.PartialRecoveryCommittedCandidate(result)

        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            error = io.StringIO()
            with redirect_stdout(output), redirect_stderr(error):
                actual = successful_api(
                    Path(directory),
                    diagnostic_observer=observer,
                )

        self.assertIs(actual, result)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(error.getvalue(), "")
        self.assertEqual(observer.state, "not-needed")
        self.assertIsNone(observer.snapshot)

    def test_reusable_api_cleanup_only_promotes_earliest_slot_after_release(self):
        module = load_module()
        observer = module.LifecycleDiagnosticObserver()

        @module._lifecycle_participant
        def cleanup_only_api(root):
            composer = module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.get()
            composer.record_cleanup(
                phase="receipt-pending",
                failure_id="WI-PARTIAL-MIGRATION-RECOVERY-CLEANUP-FAILED",
                resource=".scratch/.receipt.pending-v1",
                diagnostic="pending unlink failed",
            )
            return "proposed-success"

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(module.LifecycleError) as caught:
                cleanup_only_api(
                    Path(directory),
                    diagnostic_observer=observer,
                )

        self.assertEqual(
            caught.exception.failure_id,
            "WI-PARTIAL-MIGRATION-RECOVERY-CLEANUP-FAILED",
        )
        self.assertEqual(observer.snapshot.primaryKind, "none")
        self.assertEqual(observer.snapshot.topLevelKind, "cleanup-only")
        self.assertEqual(
            observer.snapshot.topLevelFailureId,
            "WI-PARTIAL-MIGRATION-RECOVERY-CLEANUP-FAILED",
        )

    def test_reusable_api_release_failure_preserves_existing_primary_identity(self):
        module = load_module()
        primary = module.LifecycleError("WI-TEST-PRIMARY", "primary")
        observer = module.LifecycleDiagnosticObserver()
        real_unlock = module.LifecycleTransaction._native_unlock

        def fail_after_unlock(transaction):
            real_unlock(transaction)
            raise OSError("injected release failure")

        @module._lifecycle_participant
        def failing_api(root):
            raise primary

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(
                module.LifecycleTransaction,
                "_native_unlock",
                fail_after_unlock,
            ), self.assertRaises(module.LifecycleError) as caught:
                failing_api(
                    Path(directory),
                    diagnostic_observer=observer,
                )

        self.assertIs(caught.exception, primary)
        self.assertEqual(
            tuple(record.phase for record in observer.snapshot.cleanupFailures),
            ("transaction-release",),
        )
        self.assertEqual(
            observer.snapshot.cleanupFailures[0].failureId,
            "WI-LIFECYCLE-LOCK-IDENTITY",
        )

    def test_reusable_api_rejects_subclassed_observer_before_lock_acquisition(self):
        module = load_module()

        class SubclassedObserver(module.LifecycleDiagnosticObserver):
            pass

        @module._lifecycle_participant
        def successful_api(root):
            return "unreachable"

        observer = SubclassedObserver()
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(module, "LifecycleTransaction") as transaction:
                with self.assertRaises(TypeError):
                    successful_api(
                        Path(directory),
                        diagnostic_observer=observer,
                    )
            transaction.assert_not_called()
        self.assertEqual(observer.state, "empty")

    def test_cli_root_serializes_primary_cleanup_and_summary_exactly_once(self):
        module = load_module()

        @module._lifecycle_participant
        def failing_recovery(root, *args, **kwargs):
            composer = module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.get()
            composer.record_cleanup(
                phase="receipt-pending",
                failure_id="WI-PARTIAL-MIGRATION-RECOVERY-CLEANUP-FAILED",
                resource=".scratch/.recovery-receipt.json.pending-v1",
                diagnostic="pending unlink failed",
            )
            raise module.LifecycleError(
                "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT",
                "primary receipt conflict",
            )

        expected_record = json.dumps(
            {
                "causeType": None,
                "diagnostic": "pending unlink failed",
                "failureId": "WI-PARTIAL-MIGRATION-RECOVERY-CLEANUP-FAILED",
                "index": 1,
                "phase": "receipt-pending",
                "resource": ".scratch/.recovery-receipt.json.pending-v1",
                "total": 1,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(
                module,
                "recover_partial_migration_v1",
                failing_recovery,
            ), redirect_stdout(io.StringIO()) as output:
                self.assertEqual(module.main(self._argv(Path(directory))), 1)

        self.assertEqual(
            output.getvalue().splitlines(),
            [
                "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT: "
                "primary receipt conflict",
                f"CLEANUP-FAILURE: {expected_record}",
                'CLEANUP-SUMMARY: {"count":1,"rollback":"not-needed"}',
            ],
        )

    def test_cli_root_preserves_control_flow_and_unexpected_identity_without_typed_line(self):
        module = load_module()
        for primary in (
            KeyboardInterrupt("operator cancellation"),
            RuntimeError("unexpected failure"),
        ):
            with self.subTest(primary=type(primary).__name__):

                @module._lifecycle_participant
                def failing_recovery(root, *args, **kwargs):
                    composer = module._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.get()
                    composer.record_cleanup(
                        phase="receipt-pending",
                        failure_id=(
                            "WI-PARTIAL-MIGRATION-RECOVERY-CLEANUP-FAILED"
                        ),
                        resource=".scratch/.recovery-receipt.json.pending-v1",
                        diagnostic="pending unlink failed",
                    )
                    raise primary

                with tempfile.TemporaryDirectory() as directory:
                    with patch.object(
                        module,
                        "recover_partial_migration_v1",
                        failing_recovery,
                    ), redirect_stdout(io.StringIO()) as output:
                        with self.assertRaises(BaseException) as caught:
                            module.main(self._argv(Path(directory)))

                self.assertIs(caught.exception, primary)
                lines = output.getvalue().splitlines()
                self.assertEqual(len(lines), 2)
                self.assertTrue(lines[0].startswith("CLEANUP-FAILURE: "))
                self.assertEqual(
                    lines[1],
                    'CLEANUP-SUMMARY: {"count":1,"rollback":"not-needed"}',
                )
                self.assertNotIn("WI-TEST-PRIMARY", output.getvalue())


class _UnittestAdapter(unittest.TestCase):
    """Run the module's pytest-style functions under the plan's unittest CLI."""


def _adapt_test(function):
    def method(self):
        with tempfile.TemporaryDirectory() as directory:
            # Match pytest tmp_path: native Windows short aliases are not canonical.
            function(Path(directory).resolve())

    method.__name__ = function.__name__
    return method


for _name, _function in tuple(globals().items()):
    if _name.startswith("test_") and callable(_function):
        setattr(_UnittestAdapter, _name, _adapt_test(_function))
