import asyncio
import base64
import copy
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
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest


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


def run_cli_separate_streams(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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


def expanded_root_contract(auxiliary_names: tuple[str, ...]) -> dict[str, object]:
    return {
        "schema": "work-items-root-contract",
        "version": 2,
        "rootFiles": ["README.md", "root-contract.json"],
        "lifecycleRoots": [
            {"path": "active", "kind": "active-items"},
            {"path": "archive", "kind": "archived-items"},
        ],
        "registries": [
            {"path": "backlog", "kind": "flat-markdown"},
            *(
                {"path": name, "kind": "flat-markdown-with-month-archive"}
                for name in ("bugs", "decisions", "epics")
            ),
            {"path": "lessons", "kind": "flat-markdown"},
            {"path": "roadmaps", "kind": "flat-markdown-with-month-archive"},
        ],
        "auxiliaryRoots": [
            {"path": name, "kind": "flat-json"} for name in auxiliary_names
        ],
        "activeItemSubdirectories": ["notes"],
        "archiveRootFiles": ["README.md"],
        "historicalItemDirectoryExceptions": [
            "archive/2026-01/old-item/retained-evidence"
        ],
    }


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


def _unrelated_current_status_record(root: Path, kind: str) -> tuple[Path, str, str]:
    if kind == "backlog":
        path = root / "work-items" / "backlog" / "distant-candidate.md"
        status, failure = "open", "WI-CATEGORY-STATUS-INVALID"
        text = f"Task: Distant candidate.\nstatus: {status}\n"
    elif kind == "active":
        path = root / "work-items" / "active" / "alternate-active" / "status.md"
        status, failure = "unexpected-active", "WI-CATEGORY-STATUS-INVALID"
        text = f"Task: Alternate active item.\nstatus: {status}\n"
    else:
        path = root / "work-items" / "roadmaps" / "alternate-horizon.md"
        status, failure = "superseded", "WI-CATEGORY-TERMINAL-IN-CURRENT"
        text = f"Format: roadmap-v1\nstatus: {status}\n"
    write(path, text)
    return path, status, failure


@pytest.mark.parametrize("kind", ["backlog", "active", "roadmap"])
def test_local_close_projects_unrelated_current_status_diagnostics(tmp_path: Path, kind: str) -> None:
    module = load_module()
    root = tmp_path / kind
    slug = "bounded-close"
    instant = "2026-10-03T01:00:00Z"
    seed_active(module, root, slug)
    bug = seed_context_bug(root, slug, "preserved-bug")
    write_bug_dispositions(root, slug, instant, [{
        "id": bug.stem, "action": "preserve-current", "status": "open",
        "inputSha256": hashlib.sha256(bug.read_bytes()).hexdigest(),
        "reason": "Retain independent finding.", "evidence": "Synthetic accepted residual.",
    }])
    unrelated, value, failure = _unrelated_current_status_record(root, kind)
    before = {path: path.read_bytes() for path in (unrelated, bug)}

    archived = module.close_item(root, slug, closure(instant).encode(), instant)

    assert archived == root / "work-items" / "archive" / "2026-10" / slug
    assert all(path.read_bytes() == data for path, data in before.items())
    readme = root / "work-items" / "README.md"
    text = readme.read_text(encoding="utf-8")
    blockers = text.split("## Blockers\n", 1)[1].split("\n## ", 1)[0]
    source_link = unrelated.relative_to(root / "work-items").as_posix()
    assert "- [ ]" in blockers and failure in blockers and value in blockers
    assert source_link in blockers
    assert hashlib.sha256(before[unrelated]).hexdigest() in blockers
    receipt = json.loads((archived / "bug-dispositions-receipt.json").read_bytes())
    assert receipt["readmeSha256"] == hashlib.sha256(readme.read_bytes()).hexdigest()
    after = tree_file_bytes(root)
    assert module.close_item(root, slug, closure(instant).encode(), instant) == archived
    assert tree_file_bytes(root) == after
    audit = run_cli("audit", "--root", str(root))
    assert audit.returncode == 1 and failure in audit.stdout, audit.stdout
    assert tree_file_bytes(root) == after


def test_local_index_keeps_selected_candidate_and_start_strict(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "selected"
    module.create_candidate(root, "valid-seed", b"Task: Legacy candidate without status.\n")
    before = tree_file_bytes(root)
    with pytest.raises(module.LifecycleError) as created:
        module.create_candidate(root, "invalid-selected", b"status: open\nTask: Invalid candidate.\n")
    assert created.value.failure_id == "WI-README-STALE"
    assert tree_file_bytes(root) == before
    selected = root / "work-items" / "backlog" / "valid-seed.md"
    selected.write_bytes(b"status: open\nTask: Selected invalid candidate.\n")
    before = tree_file_bytes(root)
    with pytest.raises(module.LifecycleError) as started:
        module.start_item(root, "valid-seed", quick_status().encode())
    assert started.value.failure_id == "WI-CATEGORY-STATUS-INVALID"
    assert tree_file_bytes(root) == before


@pytest.mark.parametrize("status_value,failure_id", [
    ("unexpected-active", "WI-CATEGORY-STATUS-INVALID"),
    ("closed", "WI-CATEGORY-TERMINAL-IN-CURRENT"),
])
def test_local_update_refuses_invalid_selected_source(
    tmp_path: Path, status_value: str, failure_id: str,
) -> None:
    module = load_module()
    root = tmp_path / status_value
    slug = "selected-update"
    seed_active(module, root, slug)
    source = root / "work-items" / "active" / slug / "status.md"
    original = source.read_text(encoding="utf-8")
    assert "status: active\n" in original
    write(source, original.replace("status: active\n", f"status: {status_value}\n"))
    assert module._parse_fields(source.read_text(encoding="utf-8"))["status"] == status_value
    module.refresh_readme(root)
    replacement = tmp_path / "replacement.md"
    replacement.write_bytes(quick_status("Valid replacement.").encode())
    before = tree_file_bytes(root)

    result = run_cli("update", "--root", str(root), "--slug", slug, "--status-file", str(replacement))

    assert result.returncode == 1 and failure_id in result.stdout, result.stdout
    assert tree_file_bytes(root) == before


def test_local_update_accepts_valid_selected_source_with_unrelated_diagnostic(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "control"
    slug = "selected-update"
    seed_active(module, root, slug)
    unrelated, value, failure = _unrelated_current_status_record(root, "active")
    unrelated_before = unrelated.read_bytes()
    module.refresh_readme(root)
    replacement = tmp_path / "replacement.md"
    replacement.write_bytes(quick_status("Valid replacement.").encode())

    result = run_cli("update", "--root", str(root), "--slug", slug, "--status-file", str(replacement))

    assert result.returncode == 0, result.stdout
    assert (root / "work-items" / "active" / slug / "status.md").read_bytes() == replacement.read_bytes()
    assert unrelated.read_bytes() == unrelated_before
    readme = (root / "work-items" / "README.md").read_text(encoding="utf-8")
    blockers = readme.split("## Blockers\n", 1)[1].split("\n## ", 1)[0]
    assert "- [ ]" in blockers and failure in blockers and value in blockers
    assert hashlib.sha256(unrelated_before).hexdigest() in blockers


def test_local_index_omission_compatibility_and_non_v1_exclusion(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "legacy-backlog"
    write(root / "work-items" / "backlog" / "missing.md", "Task: Missing legacy status.\n")
    write(root / "work-items" / "backlog" / "empty.md", "status:\nTask: Empty legacy status.\n")
    write(root / "work-items" / "roadmaps" / "non-v1.md", "status: superseded\n")
    entries = module.collect_readme_entries(root)
    assert [entry.logical_reference for entry in entries] == ["work-item:empty", "work-item:missing"]
    assert all(entry.section == "Next actions" for entry in entries)
    for kind in ("active", "roadmap"):
        for value in (None, ""):
            case_root = tmp_path / f"{kind}-{'missing' if value is None else 'empty'}"
            source = (
                case_root / "work-items" / "active" / "record" / "status.md"
                if kind == "active" else case_root / "work-items" / "roadmaps" / "record.md"
            )
            data = ("Format: roadmap-v1\n" if kind == "roadmap" else "")
            if value is not None:
                data += "status:\n"
            write(source, data)
            module.refresh_readme(case_root, allow_marker_bootstrap=True)
            projected = module.collect_readme_entries(case_root)
            assert len(projected) == 1 and projected[0].section == "Blockers"
            before = tree_file_bytes(case_root)
            with pytest.raises(module.LifecycleError):
                module.audit(case_root)
            assert tree_file_bytes(case_root) == before


def test_local_index_direct_shadow_and_both_precomputers_agree(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "views"
    slug = "view-selected"
    instant = "2026-10-03T02:00:00Z"
    seed_active(module, root, slug)
    unrelated, _, _ = _unrelated_current_status_record(root, "backlog")
    unrelated_before = unrelated.read_bytes()
    module.refresh_readme(root)
    work_items = root / "work-items"
    source = work_items / "bugs" / "view-bug.md"
    source_after = b"status: fixed\n"
    write(source, "status: open\n")
    archive_bug = work_items / "bugs" / "archive" / "2026-10" / source.name
    predicted_bug = module._precompute_single_bug_readme_sha256(root, source, archive_bug, source_after, [])
    bug_shadow = tmp_path / "bug-shadow"
    shutil.copytree(work_items, bug_shadow / "work-items")
    shadow_source = bug_shadow / "work-items" / source.relative_to(work_items)
    shadow_target = bug_shadow / "work-items" / archive_bug.relative_to(work_items)
    shadow_source.write_bytes(source_after)
    shadow_target.parent.mkdir(parents=True)
    shadow_source.rename(shadow_target)
    assert predicted_bug == hashlib.sha256(module.render_readme_bytes(bug_shadow)).hexdigest()
    active = work_items / "active" / slug
    archive = work_items / "archive" / "2026-10" / slug
    successor = work_items / "backlog" / "view-successor.md"
    status_after = module._terminalize_status((active / "status.md").read_bytes())
    closure_after = module._stamp_schema_marker(closure(instant).encode(), "closure.md")
    successor_data = b"status: candidate\nTask: View successor.\n"
    predicted_transition = module._precompute_transition_readme_sha256(
        root, active, archive, successor, status_after, closure_after, successor_data, (),
    )
    transition_shadow = tmp_path / "transition-shadow"
    shutil.copytree(work_items, transition_shadow / "work-items")
    shadow_active = transition_shadow / "work-items" / active.relative_to(work_items)
    shadow_archive = transition_shadow / "work-items" / archive.relative_to(work_items)
    (shadow_active / "status.md").write_bytes(status_after)
    (shadow_active / "closure.md").write_bytes(closure_after)
    shadow_archive.parent.mkdir(parents=True)
    shadow_active.rename(shadow_archive)
    (transition_shadow / "work-items" / successor.relative_to(work_items)).write_bytes(successor_data)
    assert predicted_transition == hashlib.sha256(module.render_readme_bytes(transition_shadow)).hexdigest()
    assert unrelated.read_bytes() == unrelated_before


def test_local_index_keeps_uncertain_sources_and_selected_close_strict(tmp_path: Path) -> None:
    module = load_module()
    instant = "2026-10-03T03:00:00Z"
    for case in ("duplicate", "unreadable", "relation", "selected-missing", "selected-empty"):
        root = tmp_path / case
        slug = "strict-local-target"
        seed_active(module, root, slug)
        write_empty_bug_dispositions(root, slug, instant)
        unrelated = root / "work-items" / "active" / "distant-record" / "status.md"
        if case == "duplicate":
            write(unrelated, "status: unexpected-active\n")
            write(root / "work-items" / "backlog" / "distant-record.md", "status: candidate\n")
        elif case == "unreadable":
            unrelated.parent.mkdir(parents=True)
            unrelated.write_bytes(b"status: unexpected-active\n\xff")
        elif case == "relation":
            write(unrelated, "status: unexpected-active\nRoadmap: missing-roadmap\n")
        else:
            status = root / "work-items" / "active" / slug / "status.md"
            replacement = "" if case == "selected-missing" else "status:\n"
            original = status.read_text(encoding="utf-8")
            assert "status: active\n" in original
            write(status, original.replace("status: active\n", replacement))
            assert module._parse_fields(status.read_text(encoding="utf-8")).get("status") in {None, ""}
        before = tree_file_bytes(root)
        with pytest.raises((module.LifecycleError, UnicodeDecodeError)):
            module.close_item(root, slug, closure(instant).encode(), instant)
        assert tree_file_bytes(root) == before, case
        assert not (root / "work-items" / "archive" / "2026-10" / slug).exists()


def seed_fixed_bug_with_active_parent(module, root: Path, slug: str) -> tuple[Path, Path]:
    parent_slug = "fixed-bug-parent"
    seed_active(module, root, parent_slug)
    bug = seed_context_bug(root, parent_slug, slug)
    bug.write_text(
        bug.read_text(encoding="utf-8").replace("- status: open", "- status: fixed"),
        encoding="utf-8",
    )
    parent_status = root / "work-items" / "active" / parent_slug / "status.md"
    parent_status.write_bytes(
        parent_status.read_bytes()
        + f"Related: bug:{slug}\n[physical](../../bugs/{slug}.md#proof)\n".encode()
    )
    module.refresh_readme(root, allow_marker_bootstrap=True)
    return bug, parent_status


def test_archive_fixed_bug_active_parent_links_receipt_and_exact_replay(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-09-26-fixed-bug"
    instant = "2026-09-26T12:00:00Z"
    resolution = "The reported filesystem defect is fixed."
    evidence = "Focused test receipt: 9 of 9 passing."
    bug, status = seed_fixed_bug_with_active_parent(module, root, slug)
    bug_before = bug.read_bytes()
    status_before = status.read_bytes()
    ledger = status.parent / "agent-runs.jsonl"
    ledger_before = ledger.read_bytes() if ledger.exists() else None
    expected_href = f"../../bugs/archive/2026-09/{slug}.md#proof"
    command = (
        "archive-fixed-bug", "--root", str(root), "--slug", slug,
        "--terminal-instant", instant, "--resolution", resolution,
        "--evidence", evidence, "--apply",
    )

    result = run_cli(*command)

    assert result.returncode == 0, result.stdout
    assert "WI-FIXED-BUG-ARCHIVE-COMMITTED" in result.stdout
    archive = root / "work-items" / "bugs" / "archive" / "2026-09" / f"{slug}.md"
    receipt_path = archive.with_name(f"{slug}.fixed-archive-receipt.json")
    readme = root / "work-items" / "README.md"
    assert not bug.exists()
    assert archive.is_file()
    fields = module._parse_fields(archive.read_text(encoding="utf-8"))
    assert fields["id"] == slug
    assert fields["status"] == "fixed"
    assert fields["context"] == "fixed-bug-parent"
    assert fields["terminal-at"] == instant
    assert fields["resolution"] == resolution
    assert fields["evidence"] == evidence
    assert status.parent.is_dir()
    assert (ledger.read_bytes() if ledger.exists() else None) == ledger_before
    assert f"bug:{slug}".encode() in status.read_bytes()
    assert f"[{ 'physical' }]({expected_href})".encode() in status.read_bytes()
    assert f"../../bugs/{slug}.md#proof".encode() in status_before
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert set(receipt) == {
        "schemaVersion", "owner", "kind", "status", "operationId",
        "sourceReference", "sourcePath", "archivePath", "terminalInstant",
        "sourceBeforeSha256", "archivedBugSha256", "links", "readmeSha256",
    }
    assert receipt["owner"] == "mutate-work-item:fixed-bug-archive-v1"
    assert receipt["kind"] == "fixed-bug-archive-v1"
    assert receipt["status"] == "settled"
    assert receipt["sourceBeforeSha256"] == hashlib.sha256(bug_before).hexdigest()
    assert receipt["archivedBugSha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert receipt["readmeSha256"] == hashlib.sha256(readme.read_bytes()).hexdigest()
    assert receipt["links"] == [{
        "path": status.relative_to(root).as_posix(),
        "beforeSha256": hashlib.sha256(status_before).hexdigest(),
        "afterSha256": hashlib.sha256(status.read_bytes()).hexdigest(),
    }]
    before_replay = (archive.read_bytes(), status.read_bytes(), receipt_path.read_bytes(), readme.read_bytes())
    replay = run_cli(*command)
    assert replay.returncode == 0, replay.stdout
    assert (archive.read_bytes(), status.read_bytes(), receipt_path.read_bytes(), readme.read_bytes()) == before_replay


def retained_preimage_fixture(tmp_path: Path, *, text_payload: bool = False):
    """Synthetic retained-input contract; never the actual retained preimage."""
    module = load_module()
    root = tmp_path / "repo"
    bug, status = seed_fixed_bug_with_active_parent(module, root, "retained-input-probe")
    seed_active(module, root, "preimage-custodian")
    item = root / "work-items" / "active" / "preimage-custodian"
    payload = item / "inputs" / "old-guidance" / ("renamed-guide.before" if text_payload else "opaque-source.saved")
    payload.parent.mkdir(parents=True)
    href = os.path.relpath(bug, payload.parent).replace(os.sep, "/")
    data = f"Historical link: [prior]({href})\n".encode() + (b"UTF-8 history\n" if text_payload else b"\x82\x00opaque history\n")
    payload.write_bytes(data)
    report = item / "stewardship.md"
    report.write_bytes(b"Synthetic accepted custody report; not current task completion.\n")
    report_digest = hashlib.sha256(report.read_bytes()).hexdigest()
    profile = {"kind": "artifact", "ref": payload.relative_to(item).as_posix(), "result": json.dumps({
        "schemaVersion": 1, "kind": "retained-preimage", "workItem": item.name,
        "purpose": "historical-only", "byteCount": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        "provenance": {"ref": report.name, "sha256": report_digest,
                       "snapshot": f"review-artifact-custody/{report_digest}"},
    }, sort_keys=True)}
    return module, root, bug, status, item, payload, data, report, profile


def retained_preimage_cli(item: Path, script: Path, *args: str):
    """Keep every public command's complete output beside the private fixture."""
    result = subprocess.run([sys.executable, "-B", str(script), *args], cwd=ROOT,
                            capture_output=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    proof_root = item.parents[2]
    number = len(list(proof_root.glob("retained-cli-*.log")))
    (proof_root / f"retained-cli-{number}.log").write_bytes(
        result.stdout + b"\nSTDERR:\n" + result.stderr + f"\nEXIT:{result.returncode}\n".encode())
    return result


def retained_preimage_append(item: Path, profile: dict, *, role="knowledge-archivist", run_id="retained-custody-record"):
    provenance = json.loads(profile["result"])["provenance"]
    return retained_preimage_cli(item, LEDGER, "--work-item", str(item), "append", "--run-id", run_id,
                                "--role", role, "--execution-role", "internal", "--status", "completed",
                                "--gate", "PASS", "--event-kind", "standalone", "--scope", profile["ref"],
                                "--artifact", provenance["ref"], "--artifact-revision", provenance["sha256"],
                                "--evidence", f"artifact:{provenance['ref']}", "--evidence-json", json.dumps(profile))


def retained_preimage_archive_oracle(tmp_path: Path, *, text_payload: bool):
    """Removing semantic admission reproduces binary refusal or UTF-8 history rewriting."""
    module, root, bug, status, item, payload, before, report, profile = retained_preimage_fixture(tmp_path, text_payload=text_payload)
    appended = retained_preimage_append(item, profile)
    assert appended.returncode == 0, appended.stdout + appended.stderr
    result = retained_preimage_cli(item, SCRIPT, "archive-fixed-bug", "--root", str(root), "--slug", bug.stem,
                                  "--terminal-instant", "2026-10-05T00:00:00Z", "--resolution", "Synthetic verified fix.",
                                  "--evidence", "Synthetic public archive oracle.", "--apply")
    assert result.returncode == 0, result.stdout + result.stderr
    assert payload.read_bytes() == before
    assert payload.parent == item / "inputs" / "old-guidance"
    assert f"../../bugs/archive/2026-10/{bug.stem}.md#proof".encode() in status.read_bytes()
    snapshot = item / json.loads(profile["result"])["provenance"]["snapshot"]
    assert snapshot.read_bytes() == report.read_bytes()


def test_retained_preimage_public_binary_archive_preserves_exact_bytes(tmp_path: Path):
    retained_preimage_archive_oracle(tmp_path, text_payload=False)


def test_retained_preimage_public_utf8_archive_does_not_rewrite_history(tmp_path: Path):
    retained_preimage_archive_oracle(tmp_path, text_payload=True)


def test_retained_preimage_wire_refuses_nonsteward_live_path_and_bad_binding(tmp_path: Path):
    for case in ("issuer", "live", "count-type", "hash", "duplicate"):
        _module, _root, _bug, _status, item, payload, before, _report, profile = retained_preimage_fixture(tmp_path / case)
        profile = copy.deepcopy(profile)
        decoded = json.loads(profile["result"])
        role = "knowledge-archivist"
        if case == "issuer":
            role = "platform-engineer"
        elif case == "live":
            profile["ref"] = "status.md"
        elif case == "count-type":
            decoded["byteCount"] = True
        elif case == "hash":
            decoded["sha256"] = "0" * 64
        profile["result"] = json.dumps(decoded)
        if case == "duplicate":
            profile["result"] = profile["result"].replace('"purpose": "historical-only"',
                                                          '"purpose": "historical-only", "purpose": "historical-only"')
        result = retained_preimage_append(item, profile, role=role)
        assert result.returncode != 0, result.stdout + result.stderr
        assert payload.read_bytes() == before
        assert not (item / "agent-runs.jsonl").exists()
        assert not (item / "review-artifact-custody").exists()


def test_retained_preimage_selected_record_is_local_and_snapshot_exact(tmp_path: Path):
    module, root, bug, _status, item, payload, before, report, profile = retained_preimage_fixture(tmp_path)
    result = retained_preimage_append(item, profile)
    assert result.returncode == 0, result.stdout + result.stderr
    snapshot = item / json.loads(profile["result"])["provenance"]["snapshot"]
    report.unlink()
    ledger = item / "agent-runs.jsonl"
    # Declared synthetic unrelated legacy rows: not ordinary-producer recipes.
    ledger.write_bytes(ledger.read_bytes() + b'{"runId":"unrelated-old-record","schemaVersion":"obsolete","artifact":"missing.md"}\nnot-json\n')
    write(item / "review-artifact-custody" / "historical-pass" / ("e" * 64 + ".json"), "unrelated invalid association\n")
    assert module._retained_preimage_consumer(payload, root / "work-items")
    assert module._retained_preimage_consumer(snapshot, root / "work-items")
    assert module._incoming_link_result(root, {bug}, f"bug:{bug.stem}", strict_consumer_reads=True)["result"] == "unmapped"
    unknown = item / "review-artifact-custody" / ("f" * 64)
    unknown.write_bytes(b"unadmitted\x82")
    with pytest.raises(module.LifecycleError, match="cannot classify live incoming-link consumer"):
        module._incoming_link_result(root, {bug}, f"bug:{bug.stem}", strict_consumer_reads=True)
    unknown.unlink()
    assert payload.read_bytes() == before
    # Matching decoded identity remains reserved even on a schema-invalid row.
    ledger.write_bytes(ledger.read_bytes() + b'{"runId":"RETAINED-CUSTODY-RECORD","schemaVersion":"obsolete"}\n')
    assert not module._retained_preimage_consumer(payload, root / "work-items")
    with pytest.raises(module.LifecycleError, match="cannot classify live incoming-link consumer"):
        module._incoming_link_result(root, {bug}, f"bug:{bug.stem}", strict_consumer_reads=True)


class SnapshotReadProbe:
    """Observe real requested sizes without allocating a schema-ceiling buffer."""
    def __init__(self, stream, requests, after_first_read=None):
        self.stream, self.requests, self.after_first_read = stream, requests, after_first_read
        self.reads = 0

    def __enter__(self):
        self.stream.__enter__()
        return self

    def __exit__(self, *args):
        return self.stream.__exit__(*args)

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def read(self, size):
        self.requests.append(size)
        data = self.stream.read(min(size, 2 * 1024 * 1024))
        self.reads += 1
        if self.reads == 1 and self.after_first_read is not None:
            self.after_first_read()
        return data


def test_retained_consumer_acquires_validator_once_per_lazy_scan(tmp_path: Path):
    module, root, bug, _status, item, payload, before, _report, profile = retained_preimage_fixture(tmp_path)
    assert retained_preimage_append(item, profile).returncode == 0
    write(item / "inputs" / "unmatched-a.md", "Ordinary live neighbor.\n")
    write(item / "inputs" / "unmatched-b.md", "Another ordinary neighbor.\n")
    seed_active(module, root, "without-ledger")
    real_loader, real_fdopen = module._validator_module, module.os.fdopen
    loads, requests = [], []

    def counted_loader():
        loads.append(1)
        return real_loader()

    def observed_fdopen(*args, **kwargs):
        return SnapshotReadProbe(real_fdopen(*args, **kwargs), requests)

    with patch.object(module, "_validator_module", side_effect=counted_loader), \
         patch.object(module.os, "fdopen", side_effect=observed_fdopen):
        result = module._incoming_link_result(root, {bug}, f"bug:{bug.stem}", strict_consumer_reads=True)
        assert result["result"] == "unmapped"
        assert payload.read_bytes() == before
        assert len(loads) == 1
        loads.clear()
        assert module._retained_preimage_consumer(payload, root / "work-items")
        assert len(loads) == 1  # Existing direct-selector default remains usable.

    empty = tmp_path / "early-return"
    owned = empty / "work-items" / "bugs" / "owned.md"
    write(owned, "Owned input.\n")
    failure = module.LifecycleError("WI-VALIDATOR-LOAD", "Injected acquisition failure")
    with patch.object(module, "_validator_module", side_effect=failure):
        assert module._incoming_link_result(empty, {owned}, "bug:owned")["result"] == "clear"
        with pytest.raises(module.LifecycleError) as caught:
            module._incoming_link_result(root, {bug}, f"bug:{bug.stem}")
        assert caught.value is failure
        with pytest.raises(module.LifecycleError) as direct:
            module._retained_preimage_consumer(root / "work-items" / "active" / "without-ledger" / "status.md", root / "work-items")
        assert direct.value is failure  # Preserve the current acquisition point.


def test_retained_consumer_prepares_each_item_once(tmp_path: Path):
    module, root, bug, _status, item, payload, before, report, profile = retained_preimage_fixture(tmp_path)
    assert retained_preimage_append(item, profile).returncode == 0
    seed_active(module, root, "preparation-peer")
    peer = root / "work-items" / "active" / "preparation-peer"
    peer_payload = peer / profile["ref"]
    peer_payload.parent.mkdir(parents=True)
    peer_payload.write_bytes(before)
    (peer / report.name).write_bytes(report.read_bytes())
    peer_profile = {**profile, "result": json.dumps({**json.loads(profile["result"]), "workItem": peer.name})}
    assert retained_preimage_append(peer, peer_profile, run_id="peer-custody-record").returncode == 0
    for owner in (item, peer):
        write(owner / "inputs" / "ordinary-a.md", "Unmatched live input.\n")
        write(owner / "inputs" / "ordinary-b.md", "Another unmatched live input.\n")
    paths = {item / "agent-runs.jsonl", peer / "agent-runs.jsonl"}
    captures, decodes = {}, {}
    real_capture, real_loader = module._capture_file_snapshot, module._validator_module

    def counted_capture(path, **kwargs):
        if path in paths:
            captures[path] = captures.get(path, 0) + 1
        return real_capture(path, **kwargs)

    def counted_loader():
        validator = real_loader()
        real_decode = validator.load_jsonl
        def counted_decode(path, *args, **kwargs):
            # Selected-proof prefix decoding is separate, still candidate-owned.
            if path in paths and sys._getframe(1).f_code.co_name != "resolve_historical_pass_custody":
                decodes[path] = decodes.get(path, 0) + 1
            return real_decode(path, *args, **kwargs)
        validator.load_jsonl = counted_decode
        return validator

    with patch.object(module, "_capture_file_snapshot", side_effect=counted_capture), \
         patch.object(module, "_validator_module", side_effect=counted_loader):
        result = module._incoming_link_result(root, {bug}, f"bug:{bug.stem}", strict_consumer_reads=True)
    assert result["result"] == "unmapped"
    assert payload.read_bytes() == before and peer_payload.read_bytes() == before
    assert captures == {path: 1 for path in paths}
    assert decodes == {path: 1 for path in paths}


def test_retained_consumer_cached_carrier_drift_never_refreshes_approval(tmp_path: Path):
    for fault in ("growth", "content", "replacement", "parent"):
        module, root, bug, status, item, payload, before, report, profile = retained_preimage_fixture(tmp_path / fault)
        assert retained_preimage_append(item, profile).returncode == 0
        ledger = item / "agent-runs.jsonl"
        # Declared synthetic whitespace suffix; original public record/proof stays exact.
        original = ledger.read_bytes() + b" \n"
        ledger.write_bytes(original)
        observed = {path: path.read_bytes() for path in (bug, status, root / "work-items" / "README.md")}
        real_selector = module._retained_preimage_consumer
        injected = []

        def select_then_drift(consumer, work_items, **kwargs):
            result = real_selector(consumer, work_items, **kwargs)
            if consumer == ledger and not injected:
                if fault == "growth":
                    ledger.write_bytes(original + b" \n")
                elif fault == "content":
                    ledger.write_bytes(original[:-2] + b"\t\n")
                elif fault == "replacement":
                    replacement = item / "replacement-ledger.jsonl"
                    replacement.write_bytes(original)
                    os.replace(replacement, ledger)
                else:
                    item.rename(item.with_name("moved-custodian"))
                injected.append(True)
            return result

        with patch.object(module, "_retained_preimage_consumer", side_effect=select_then_drift):
            with pytest.raises(module.LifecycleError, match="cannot classify live incoming-link consumer"):
                module._incoming_link_result(root, {bug}, f"bug:{bug.stem}", strict_consumer_reads=True)
        assert injected == [True]
        assert all(path.read_bytes() == data for path, data in observed.items())
        assert (item if fault != "parent" else item.with_name("moved-custodian")).joinpath(profile["ref"]).read_bytes() == before


def test_snapshot_reads_captured_size_and_preserves_drift_refusal(tmp_path: Path):
    module = load_module()
    real_fdopen = module.os.fdopen
    original = b"captured payload"
    for fault in (None, "empty", "growth", "shrink", "rewrite", "replace", "parent"):
        folder = tmp_path / str(fault) / "parent"
        target = folder / "input.bin"
        folder.mkdir(parents=True)
        case_bytes = b"" if fault == "empty" else original
        target.write_bytes(case_bytes)
        requests = []
        mutated = []

        def drift():
            if fault == "growth":
                target.write_bytes(original + b"growing")
            elif fault == "shrink":
                target.write_bytes(original[:3])
            elif fault == "rewrite":
                target.write_bytes(b"x" * len(original))
            elif fault == "replace":
                replacement = folder / "replacement.bin"
                replacement.write_bytes(original)
                os.replace(replacement, target)
            elif fault == "parent":
                folder.rename(folder.with_name("moved-parent"))
            if fault not in (None, "empty"):
                mutated.append(True)

        def observed_fdopen(*args, **kwargs):
            return SnapshotReadProbe(real_fdopen(*args, **kwargs), requests, drift)

        # Relax only this synthetic handle's sharing to exercise content races;
        # ordinary native no-follow behavior remains covered by adjacent tests.
        capture_open = module._open_readonly_nofollow
        if fault not in (None, "empty"):
            capture_open = lambda path: os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
        with patch.object(module, "_open_readonly_nofollow", side_effect=capture_open), \
             patch.object(module.os, "fdopen", side_effect=observed_fdopen):
            if fault in (None, "empty"):
                snapshot = module._capture_file_snapshot(target, failure_id="WI-SNAPSHOT-COST", maximum_bytes=0 if fault == "empty" else 1024)
                assert snapshot.data == case_bytes
            else:
                with pytest.raises(module.LifecycleError) as caught:
                    module._capture_file_snapshot(target, failure_id="WI-SNAPSHOT-COST", maximum_bytes=1024)
                assert caught.value.failure_id == "WI-SNAPSHOT-COST"
        if fault in (None, "empty", "growth", "shrink", "rewrite"):
            assert requests == [len(case_bytes) + 1, len(case_bytes) + 1], fault
            if fault not in (None, "empty"):
                assert mutated == [True], fault
        else:
            # Windows may refuse replacement/parent moves while the file is open.
            assert 1 <= len(requests) <= 2 and all(size == len(case_bytes) + 1 for size in requests), fault


def test_retained_preimage_multiple_descriptors_keep_runtime_binding_local(tmp_path: Path):
    module, root, bug, status, item, first, original, report, profile = retained_preimage_fixture(tmp_path)
    second = item / "inputs" / "separate-source.before"
    second.write_bytes(b"Second retained historical bytes.\n")
    second_result = {**json.loads(profile["result"]), "byteCount": second.stat().st_size,
                     "sha256": hashlib.sha256(second.read_bytes()).hexdigest()}
    second_profile = {**profile, "ref": second.relative_to(item).as_posix(),
                      "result": json.dumps(second_result, sort_keys=True)}
    provenance = json.loads(profile["result"])["provenance"]
    appended = retained_preimage_cli(item, LEDGER, "--work-item", str(item), "append",
        "--run-id", "multiple-retained-record", "--role", "knowledge-archivist",
        "--execution-role", "internal", "--status", "completed", "--gate", "PASS",
        "--event-kind", "standalone", "--scope", profile["ref"], "--artifact", provenance["ref"],
        "--artifact-revision", provenance["sha256"], "--evidence", f"artifact:{provenance['ref']}",
        "--evidence-json", json.dumps(profile), "--evidence-json", json.dumps(second_profile))
    assert appended.returncode == 0, appended.stdout + appended.stderr
    ledger = item / "agent-runs.jsonl"
    snapshot = item / provenance["snapshot"]
    association = next((item / "review-artifact-custody" / "historical-pass").iterdir())
    observed = (first, ledger, report, snapshot, association, bug, status, root / "work-items" / "README.md")
    before = {path: path.read_bytes() for path in observed}
    assert module._retained_preimage_consumer(first, root / "work-items")
    second.write_bytes(second.read_bytes() + b"Changed second payload.\x82")
    assert {path: path.read_bytes() for path in observed} == before
    assert first.read_bytes() == original
    assert module._retained_preimage_consumer(first, root / "work-items")
    assert not module._retained_preimage_consumer(second, root / "work-items")
    with pytest.raises(module.LifecycleError, match="cannot classify live incoming-link consumer"):
        module._incoming_link_result(root, {bug}, f"bug:{bug.stem}", strict_consumer_reads=True)

    # Selective runtime capture never relaxes same-record descriptor schemas.
    validator = module._validator_module()
    record = json.loads(ledger.read_bytes())
    first_capture = validator.capture_retained_preimage_payload(item, profile, json.loads(profile["result"]))
    invalid_second = {**second_profile, "result": json.dumps({**second_result, "purpose": "invalid-purpose"})}
    invalid_record = {**record, "evidence": [invalid_second if row.get("ref") == second_profile["ref"] else row
                                            for row in record["evidence"]]}
    schema_errors = []
    assert not validator._validate_event(invalid_record, item, set(), schema_errors,
                                        retained_payloads={profile["ref"]: first_capture})
    assert any("WI-RETAINED-PREIMAGE" in error for error in schema_errors)

    # None and an explicit complete mapping both retain full payload checks.
    full_errors = []
    assert not validator._validate_event(record, item, set(), full_errors)
    assert any("WI-RETAINED-PREIMAGE" in error for error in full_errors)
    second_capture = validator.load_lifecycle_owner()._capture_file_snapshot(second, failure_id="WI-RETAINED-PREIMAGE")
    mapped_errors = []
    assert not validator._validate_event(record, item, set(), mapped_errors,
        retained_payloads={profile["ref"]: first_capture, second_profile["ref"]: second_capture})
    assert any("WI-RETAINED-PREIMAGE" in error for error in mapped_errors)
    refused = retained_preimage_append(item, second_profile, run_id="invalid-second-append")
    assert refused.returncode != 0
    assert {path: path.read_bytes() for path in observed} == before


def test_retained_preimage_observation_drift_refuses_before_intent(tmp_path: Path):
    for participant in ("payload", "carrier", "association", "snapshot"):
        module, root, bug, status, item, payload, _data, _report, profile = retained_preimage_fixture(tmp_path / participant)
        appended = retained_preimage_append(item, profile)
        assert appended.returncode == 0, appended.stdout + appended.stderr
        ledger = item / "agent-runs.jsonl"
        selected = {
            "payload": payload, "carrier": ledger,
            "association": next((item / "review-artifact-custody" / "historical-pass").iterdir()),
            "snapshot": item / json.loads(profile["result"])["provenance"]["snapshot"],
        }[participant]
        before = (bug.read_bytes(), status.read_bytes(), (root / "work-items" / "README.md").read_bytes())
        original = module._precompute_single_bug_readme_sha256

        def drift(*args, **kwargs):
            result = original(*args, **kwargs)
            selected.write_bytes(selected.read_bytes() + b"changed after semantic selection")
            return result

        with patch.object(module, "_precompute_single_bug_readme_sha256", side_effect=drift):
            with pytest.raises(module.LifecycleError):
                module.archive_fixed_bug(root, bug.stem, "2026-10-05T00:00:00Z", "Synthetic fix.", "Synthetic proof.")
        assert (bug.read_bytes(), status.read_bytes(), (root / "work-items" / "README.md").read_bytes()) == before
        assert not (root / "work-items" / "lifecycle-transitions").exists()
        assert not (root / "work-items" / "bugs" / "archive").exists()


def test_retained_preimage_relocated_archive_and_live_neighbor_stay_strict(tmp_path: Path):
    module, root, bug, _status, item, payload, before, report, profile = retained_preimage_fixture(tmp_path)
    assert retained_preimage_append(item, profile).returncode == 0
    report.write_bytes(b"current report pointer is replaced")
    archive = root / "work-items" / "archive" / "2026-10" / item.name
    archive.parent.mkdir(parents=True)
    item.rename(archive)  # Declared synthetic relocation; never move an actual preimage.
    relocated = archive / payload.relative_to(item)
    assert module._retained_preimage_consumer(relocated, root / "work-items")
    assert relocated.read_bytes() == before
    neighbor = archive / "inputs" / "unadmitted-neighbor"
    neighbor.write_bytes(b"unknown\x82")
    with pytest.raises(module.LifecycleError, match="cannot classify live incoming-link consumer"):
        module._incoming_link_result(root, {bug}, f"bug:{bug.stem}", strict_consumer_reads=True)
    assert module._incoming_link_result(root, {bug}, f"bug:{bug.stem}", strict_consumer_reads=True,
                                       mutable_consumers_only=True)["result"] == "unmapped"
    assert relocated.read_bytes() == before


def test_archive_fixed_bug_requires_positive_apply_and_preserves_state(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-09-26-no-apply"
    bug, status = seed_fixed_bug_with_active_parent(module, root, slug)
    before = (bug.read_bytes(), status.read_bytes())

    result = run_cli(
        "archive-fixed-bug", "--root", str(root), "--slug", slug,
        "--terminal-instant", "2026-09-26T12:00:00Z",
        "--resolution", "Fixed.", "--evidence", "Test receipt.",
    )

    assert result.returncode == 1
    assert "WI-FIXED-BUG-APPLY-REQUIRED" in result.stdout
    assert (bug.read_bytes(), status.read_bytes()) == before


def test_archive_fixed_bug_preserves_existing_evidence_and_rejects_conflicts(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-09-26-existing-evidence"
    instant = "2026-10-01T00:00:00Z"
    bug, _status = seed_fixed_bug_with_active_parent(module, root, slug)
    with bug.open("ab") as stream:
        stream.write(b"- terminal-at: 2026-10-01T00:00:00Z\n- resolution: Fixed.\n- evidence: Verified.\n")
    preserved = bug.read_bytes()
    with unittest.TestCase().assertRaises(module.LifecycleError) as conflict:
        module.archive_fixed_bug(root, slug, instant, "Different.", "Verified.")
    assert conflict.exception.failure_id == "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"
    assert bug.read_bytes() == preserved

    receipt = module.archive_fixed_bug(root, slug, instant, "Fixed.", "Verified.")

    archive = root / receipt["archivePath"]
    assert archive.read_bytes() == preserved
    assert archive.parent.name == "2026-10"


def test_archive_fixed_bug_rejects_immutable_physical_link_and_collision(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-09-26-unsafe-link"
    bug, status = seed_fixed_bug_with_active_parent(module, root, slug)
    historical = root / "work-items" / "archive" / "2026-08" / "old" / "notes.md"
    write(historical, f"[old](../../../bugs/{slug}.md)\n")
    before = (bug.read_bytes(), status.read_bytes(), historical.read_bytes())
    with unittest.TestCase().assertRaises(module.LifecycleError) as unsafe:
        module.archive_fixed_bug(root, slug, "2026-09-26T12:00:00Z", "Fixed.", "Verified.")
    assert unsafe.exception.failure_id == "WI-FIXED-BUG-LINK-INVENTORY"
    assert (bug.read_bytes(), status.read_bytes(), historical.read_bytes()) == before

    historical.unlink()
    archive = root / "work-items" / "bugs" / "archive" / "2026-09" / f"{slug}.md"
    write(archive, "unrelated archive identity\n")
    with unittest.TestCase().assertRaises(module.LifecycleError) as collision:
        module.archive_fixed_bug(root, slug, "2026-09-26T12:00:00Z", "Fixed.", "Verified.")
    assert collision.exception.failure_id == "WI-CATEGORY-DUAL-LOCATION"
    assert (bug.read_bytes(), status.read_bytes()) == before[:2]
    assert archive.read_text(encoding="utf-8") == "unrelated archive identity\n"


def test_archive_fixed_bug_precommit_restores_and_postcommit_recovers(tmp_path: Path) -> None:
    module = load_module()
    instant = "2026-09-26T12:00:00Z"
    for phase in ("F1", "F3"):
        root = tmp_path / phase
        slug = f"2026-09-26-{phase.lower()}-recovery"
        bug, status = seed_fixed_bug_with_active_parent(module, root, slug)
        readme = root / "work-items" / "README.md"
        before = (bug.read_bytes(), status.read_bytes(), readme.read_bytes())
        with unittest.TestCase().assertRaises(module.LifecycleError) as injected:
            module.archive_fixed_bug(
                root, slug, instant, "Fixed.", "Verified.", inject_failure_at=phase,
            )
        assert injected.exception.failure_id == (
            "WI-FIXED-BUG-ROLLBACK-INDETERMINATE" if phase == "F1"
            else "WI-FIXED-BUG-ROLLFORWARD-INDETERMINATE"
        )

        module._recover_all_transitions(root)

        archive = root / "work-items" / "bugs" / "archive" / "2026-09" / f"{slug}.md"
        receipt = archive.with_name(f"{slug}.fixed-archive-receipt.json")
        if phase == "F1":
            assert (bug.read_bytes(), status.read_bytes(), readme.read_bytes()) == before
            assert not archive.exists() and not receipt.exists()
        else:
            assert not bug.exists()
            assert archive.is_file() and receipt.is_file()
            assert f"../../bugs/archive/2026-09/{slug}.md#proof".encode() in status.read_bytes()
            assert module._verify_fixed_bug_archive_settlement(root, receipt)["status"] == "settled"
        intents = root / ".scratch" / "work-items-lifecycle-transitions"
        assert not list(intents.glob("*.json"))


def test_archive_fixed_bug_readme_failure_recovers_after_move(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-09-26-readme-failure"
    bug, _status = seed_fixed_bug_with_active_parent(module, root, slug)
    archive = root / "work-items" / "bugs" / "archive" / "2026-09" / f"{slug}.md"
    original_refresh = module._safe_refresh_readme
    with patch.object(module, "_safe_refresh_readme", side_effect=module.LifecycleError("WI-README-STALE", "injected")):
        with unittest.TestCase().assertRaises(module.LifecycleError) as failure:
            module.archive_fixed_bug(root, slug, "2026-09-26T12:00:00Z", "Fixed.", "Verified.")
    assert failure.exception.failure_id == "WI-FIXED-BUG-ROLLFORWARD-INDETERMINATE"
    assert not bug.exists() and archive.is_file()
    assert module._safe_refresh_readme is original_refresh
    module._recover_all_transitions(root)
    receipt = archive.with_name(f"{slug}.fixed-archive-receipt.json")
    assert module._verify_fixed_bug_archive_settlement(root, receipt)["status"] == "settled"


def test_archive_fixed_bug_recovery_errors_name_fixed_archive_not_supersession(tmp_path: Path) -> None:
    module = load_module()
    for phase, target_kind in (("F1", "link"), ("F3", "archive")):
        root = tmp_path / phase
        slug = f"2026-09-26-{phase.lower()}-diagnostic"
        _bug, status = seed_fixed_bug_with_active_parent(module, root, slug)
        with unittest.TestCase().assertRaises(module.LifecycleError):
            module.archive_fixed_bug(
                root, slug, "2026-09-26T12:00:00Z", "Fixed.", "Verified.",
                inject_failure_at=phase,
            )
        archive = root / "work-items" / "bugs" / "archive" / "2026-09" / f"{slug}.md"
        target = status if target_kind == "link" else archive
        target_before_drift = target.read_bytes()
        target.write_bytes(b"foreign mutation\n")

        with unittest.TestCase().assertRaises(module.LifecycleError) as failed_recovery:
            module._recover_all_transitions(root)

        assert failed_recovery.exception.failure_id == (
            "WI-FIXED-BUG-ROLLBACK-INDETERMINATE" if phase == "F1"
            else "WI-FIXED-BUG-ROLLFORWARD-INDETERMINATE"
        )
        assert "fixed-bug archive" in str(failed_recovery.exception)
        assert "supersession" not in str(failed_recovery.exception)
        assert target.read_bytes() == b"foreign mutation\n"
        target.write_bytes(target_before_drift)
        module._recover_all_transitions(root)
        assert not list((root / ".scratch" / "work-items-lifecycle-transitions").glob("*.json"))

    root = tmp_path / "F3-readme"
    slug = "2026-09-26-readme-diagnostic"
    bug, _status = seed_fixed_bug_with_active_parent(module, root, slug)
    with unittest.TestCase().assertRaises(module.LifecycleError):
        module.archive_fixed_bug(
            root, slug, "2026-09-26T12:00:00Z", "Fixed.", "Verified.",
            inject_failure_at="F3",
        )
    archive = root / "work-items" / "bugs" / "archive" / "2026-09" / f"{slug}.md"
    archive_before = archive.read_bytes()
    assert not bug.exists()
    with patch.object(module, "_safe_refresh_readme", return_value="0" * 64):
        with unittest.TestCase().assertRaises(module.LifecycleError) as readme_mismatch:
            module._recover_all_transitions(root)

    assert readme_mismatch.exception.failure_id == "WI-FIXED-BUG-ROLLFORWARD-INDETERMINATE"
    assert str(readme_mismatch.exception) == "fixed-bug archive README afterimage differs"
    assert archive.read_bytes() == archive_before
    assert not archive.with_name(f"{slug}.fixed-archive-receipt.json").exists()
    module._recover_all_transitions(root)
    assert not list((root / ".scratch" / "work-items-lifecycle-transitions").glob("*.json"))


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


def seed_retained_scratch_manifest(
    module,
    root: Path,
    slug: str,
    instant: str,
    *,
    leaf_name: str = "historical-evidence",
    regular_file: bool = False,
):
    seed_active(module, root, slug)
    item = root / "work-items" / "active" / slug
    retained = root / ".scratch" / "work-items" / slug / "run-001" / leaf_name
    if regular_file:
        write(retained, f"preserve {leaf_name} historical evidence\n")
    else:
        write(retained / "proof.txt", "preserve this historical evidence\n")
    pointer = item / "historical-evidence.md"
    write(pointer, f"{leaf_name}\n")
    retained_before = module._payload_digest(retained)[1]
    pointer_before = pointer.read_bytes()
    manifest = {
        "schemaVersion": 3,
        "workItem": slug,
        "closedAt": instant,
        "bugs": [],
        "evidenceRetention": [
            {
                "path": retained.relative_to(root).as_posix(),
                "disposition": "retain",
                "treeSha256": retained_before,
                "canonicalPointer": pointer.relative_to(item).as_posix(),
                "canonicalPointerSha256": hashlib.sha256(pointer_before).hexdigest(),
            }
        ],
    }
    (item / "bug-dispositions.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return item, retained, pointer, retained_before, pointer_before, manifest


def test_close_retains_declared_unmatched_scratch_evidence_root(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "retained-scratch-root"
    instant = "2026-08-11T10:00:00Z"
    item, retained, pointer, retained_before, pointer_before, manifest = seed_retained_scratch_manifest(
        module, root, slug, instant
    )

    archived = module.close_item(root, slug, closure(instant).encode(), instant)

    assert module._payload_digest(retained)[1] == retained_before
    assert archived == root / "work-items" / "archive" / "2026-08" / slug
    archived_pointer = archived / pointer.name
    assert archived_pointer.read_bytes() == pointer_before
    receipt = json.loads((archived / "bug-dispositions-receipt.json").read_text(encoding="utf-8"))
    assert receipt["evidenceRetention"] == manifest["evidenceRetention"]

    shutil.rmtree(retained.parent)
    assert module.close_item(root, slug, closure(instant).encode(), instant) == archived


def test_close_retains_declared_unmatched_regular_file_scratch_evidence(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "retained-scratch-file"
    instant = "2026-08-11T10:00:30Z"
    _item, retained, pointer, retained_before, pointer_before, manifest = seed_retained_scratch_manifest(
        module,
        root,
        slug,
        instant,
        leaf_name="receiving_probe.py",
        regular_file=True,
    )

    archived = module.close_item(root, slug, closure(instant).encode(), instant)

    assert retained.is_file()
    assert module._payload_digest(retained)[1] == retained_before
    assert (archived / pointer.name).read_bytes() == pointer_before
    receipt = json.loads((archived / "bug-dispositions-receipt.json").read_text(encoding="utf-8"))
    assert receipt["evidenceRetention"] == manifest["evidenceRetention"]
    retained.unlink()
    assert module.close_item(root, slug, closure(instant).encode(), instant) == archived


def test_close_retention_receipt_accepts_relative_repository_root(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "retained-relative-root"
    instant = "2026-08-11T10:00:45Z"
    item, retained, _pointer, retained_before, _pointer_before, manifest = seed_retained_scratch_manifest(
        module, root, slug, instant
    )
    closure_path = root / "closure.md"
    closure_path.write_text(closure(instant), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "close",
            "--root",
            ".",
            "--slug",
            slug,
            "--closure-file",
            str(closure_path),
            "--terminal-instant",
            instant,
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    archived = root / "work-items" / "archive" / "2026-08" / slug
    assert result.stdout.strip() == str(archived.resolve())
    assert module._payload_digest(retained)[1] == retained_before
    receipt = json.loads((archived / "bug-dispositions-receipt.json").read_text(encoding="utf-8"))
    assert receipt["evidenceRetention"] == manifest["evidenceRetention"]
    assert not item.exists()


def test_close_retention_receipt_preserves_unsorted_manifest_row_order(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "retained-unsorted-order"
    instant = "2026-08-11T10:01:15Z"
    item, retained, _pointer, retained_before, _pointer_before, manifest = seed_retained_scratch_manifest(
        module, root, slug, instant, leaf_name="zeta-capture"
    )
    file_leaf = root / ".scratch" / "work-items" / slug / "run-002" / "alpha_probe.py"
    write(file_leaf, "preserve alpha_probe.py historical evidence\n")
    file_pointer = item / "alpha-probe.md"
    write(file_pointer, "alpha_probe.py\n")
    manifest["evidenceRetention"].append(
        {
            "path": file_leaf.relative_to(root).as_posix(),
            "disposition": "retain",
            "treeSha256": module._payload_digest(file_leaf)[1],
            "canonicalPointer": file_pointer.relative_to(item).as_posix(),
            "canonicalPointerSha256": hashlib.sha256(file_pointer.read_bytes()).hexdigest(),
        }
    )
    (item / "bug-dispositions.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    closure_path = root / "closure.md"
    closure_path.write_text(closure(instant), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "close",
            "--root",
            ".",
            "--slug",
            slug,
            "--closure-file",
            str(closure_path),
            "--terminal-instant",
            instant,
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    archived = root / "work-items" / "archive" / "2026-08" / slug
    receipt = json.loads((archived / "bug-dispositions-receipt.json").read_text(encoding="utf-8"))
    assert receipt["evidenceRetention"] == manifest["evidenceRetention"]
    assert module._payload_digest(retained)[1] == retained_before
    assert file_leaf.read_text(encoding="utf-8") == "preserve alpha_probe.py historical evidence\n"
    file_leaf.unlink()
    shutil.rmtree(retained)
    assert module.close_item(root, slug, closure_path.read_bytes(), instant) == archived


def test_close_relative_root_rejects_undeclared_scratch_leaf(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "retained-with-undeclared-leaf"
    instant = "2026-08-11T10:01:30Z"
    item, retained, _pointer, retained_before, _pointer_before, _manifest = seed_retained_scratch_manifest(
        module, root, slug, instant
    )
    undeclared = root / ".scratch" / "work-items" / slug / "run-002" / "extra.txt"
    write(undeclared, "unclaimed evidence\n")
    undeclared_before = undeclared.read_bytes()
    closure_path = root / "closure.md"
    closure_path.write_text(closure(instant), encoding="utf-8")
    manifest_before = (item / "bug-dispositions.json").read_bytes()

    result = subprocess.run(
        [
            sys.executable, str(SCRIPT), "close", "--root", ".", "--slug", slug,
            "--closure-file", str(closure_path), "--terminal-instant", instant,
        ],
        cwd=root, text=True, capture_output=True, check=False,
    )

    assert result.returncode == 1
    assert "WI-SCRATCH-OWNERSHIP-INCOMPLETE" in result.stdout
    assert item.is_dir()
    assert (item / "bug-dispositions.json").read_bytes() == manifest_before
    assert module._payload_digest(retained)[1] == retained_before
    assert undeclared.read_bytes() == undeclared_before
    assert not (root / "work-items" / "archive" / "2026-08" / slug).exists()


def test_retained_scratch_hash_drift_and_close_rollback_preserve_active_state(tmp_path: Path) -> None:
    module = load_module()
    instant = "2026-08-11T10:01:00Z"

    drift_root = tmp_path / "drift"
    drift_slug = "retained-scratch-drift"
    drift_item, retained, _pointer, retained_before, _pointer_before, manifest = seed_retained_scratch_manifest(
        module, drift_root, drift_slug, instant
    )
    manifest["evidenceRetention"][0]["treeSha256"] = "0" * 64
    (drift_item / "bug-dispositions.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    try:
        module.close_item(drift_root, drift_slug, closure(instant).encode(), instant)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-BUG-DISPOSITIONS-DRIFT"
    else:
        raise AssertionError("retained scratch hash drift was accepted")
    assert module._payload_digest(retained)[1] == retained_before
    assert drift_item.is_dir()

    rollback_root = tmp_path / "rollback"
    rollback_slug = "retained-scratch-rollback"
    item, retained, pointer, retained_before, pointer_before, _manifest = seed_retained_scratch_manifest(
        module, rollback_root, rollback_slug, instant
    )
    try:
        module.close_item(
            rollback_root,
            rollback_slug,
            closure(instant).encode(),
            instant,
            inject_readme_failure=True,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-README-STALE"
    else:
        raise AssertionError("injected close failure did not roll back")
    assert item.is_dir()
    assert pointer.read_bytes() == pointer_before
    assert module._payload_digest(retained)[1] == retained_before
    assert not (rollback_root / "work-items" / "archive" / "2026-08" / rollback_slug).exists()


def test_retained_scratch_pointer_parent_link_is_rejected_before_archive(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "retained-pointer-parent-link"
    instant = "2026-08-11T10:02:00Z"
    item, retained, _pointer, retained_before, _pointer_before, manifest = seed_retained_scratch_manifest(
        module, root, slug, instant
    )
    external = tmp_path / "external-pointer"
    write(external / "proof.md", "historical-evidence\n")
    linked_parent = item / "linked-parent"
    try:
        os.symlink(external, linked_parent, target_is_directory=True)
    except OSError as exc:
        raise AssertionError("parent-link retention regression requires symlink support") from exc
    external_pointer = external / "proof.md"
    manifest["evidenceRetention"][0]["canonicalPointer"] = "linked-parent/proof.md"
    manifest["evidenceRetention"][0]["canonicalPointerSha256"] = hashlib.sha256(
        external_pointer.read_bytes()
    ).hexdigest()
    (item / "bug-dispositions.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")

    try:
        module.close_item(root, slug, closure(instant).encode(), instant)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-BUG-DISPOSITIONS-INVALID"
    else:
        raise AssertionError("canonical pointer escaped through a linked parent")

    assert item.is_dir()
    assert module._payload_digest(retained)[1] == retained_before
    assert external_pointer.read_text(encoding="utf-8") == "historical-evidence\n"
    assert not (root / "work-items" / "archive" / "2026-08" / slug).exists()


def test_retained_payload_digest_optional_limits_keep_legacy_golden_bytes(
    tmp_path: Path,
) -> None:
    module = load_module()
    payload = tmp_path / "payload"
    (payload / "proof.txt").parent.mkdir(parents=True, exist_ok=True)
    (payload / "proof.txt").write_bytes(b"proof\n")
    (payload / "nested").mkdir()
    (payload / "nested" / "data.bin").write_bytes(b"xy")

    assert module._payload_digest(payload) == (
        "sha256-tree-entries-v1",
        "81dfbcb39577424a703e807dd5712bdb0d3decf231edd85327e3438a48ffba5f",
    )
    legacy_file = tmp_path / "legacy-file.txt"
    legacy_file.write_bytes(b"legacy file\n")
    assert module._payload_digest(legacy_file) == (
        "sha256-file-bytes-v1",
        "2ed93b04807efb14d2186e20bb6f8c45264a32d08bd97df62316cccd6ded4894",
    )
    assert module._payload_digest(
        payload,
        limits=module.PayloadDigestLimits(
            max_files=8, max_entries=8, max_bytes=1024
        ),
    ) == module._payload_digest(payload)

    cases = (
        (module.PayloadDigestLimits(max_files=8, max_entries=1, max_bytes=1024), "entry"),
        (module.PayloadDigestLimits(max_files=1, max_entries=8, max_bytes=1024), "file"),
        (module.PayloadDigestLimits(max_files=8, max_entries=8, max_bytes=1), "byte"),
    )
    for limits, label in cases:
        try:
            module._payload_digest(payload, limits=limits)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-MIGRATION-PAYLOAD", label
        else:
            raise AssertionError(f"{label} payload limit was accepted")


def test_retained_payload_digest_limit_stops_scandir_before_preloading(tmp_path: Path) -> None:
    module = load_module()
    payload = tmp_path / "payload"
    for name in ("one.txt", "two.txt", "three.txt"):
        write(payload / name, name + "\n")

    original_scandir = module.os.scandir
    consumed: list[str] = []
    closed: list[bool] = []

    class TrackingScandir:
        def __init__(self, path) -> None:
            self._context = original_scandir(path)
            self._iterator = self._context.__enter__()
            self._track = Path(path) == payload
            self._closed = False

        def __iter__(self):
            return self

        def __next__(self):
            entry = next(self._iterator)
            if self._track:
                consumed.append(entry.name)
            return entry

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            self._closed = True
            if self._track:
                closed.append(self._closed)
            self._context.__exit__(exc_type, exc, traceback)

    with patch.object(module.os, "scandir", side_effect=TrackingScandir):
        try:
            module._payload_digest(
                payload,
                limits=module.PayloadDigestLimits(
                    max_files=8, max_entries=1, max_bytes=1024
                ),
            )
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-MIGRATION-PAYLOAD"
        else:
            raise AssertionError("bounded payload walk accepted three entries")

    assert len(consumed) == 2
    assert closed == [True]


def test_retained_evidence_limits_use_cleanup_owner_ceilings(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "retained-ceiling"
    instant = "2026-08-11T10:02:30Z"
    item, retained, _pointer, _before, _pointer_before, manifest = seed_retained_scratch_manifest(
        module, root, slug, instant
    )
    write(retained / "second-proof.txt", "second retained proof\n")
    manifest["evidenceRetention"][0]["treeSha256"] = module._payload_digest(retained)[1]

    classifier = module._scratch_classifier_module()
    with (
        patch.object(module, "_scratch_classifier_module", return_value=classifier),
        patch.object(classifier, "MAX_OWNED_TREE_FILES", 1),
    ):
        try:
            module._prepare_evidence_retention(root, item, manifest)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-SCRATCH-UNSAFE-ENTRY"
        else:
            raise AssertionError("retained evidence exceeded the cleanup owner file ceiling")


def test_retained_evidence_pointer_requires_literal_root_or_manifest_path(
    tmp_path: Path,
) -> None:
    module = load_module()
    instant = "2026-08-11T10:02:45Z"
    cases = (
        ("plain", "historical-evidence", "historical-evidence\n", True),
        ("quoted", "historical-evidence", '"historical-evidence"\n', True),
        (
            "manifest-path-with-spaces",
            "historical evidence",
            ".scratch/work-items/retained-manifest-path-with-spaces/run-001/historical evidence\n",
            True,
        ),
        ("catalog", "log", "catalog\n", False),
        ("unrelated-label", "evidence", "unrelated-evidence-label\n", False),
        ("wrong-path", "log", "wrong/path/log\n", False),
    )
    for suffix, leaf_name, pointer_text, accepted in cases:
        root = tmp_path / suffix
        slug = f"retained-{suffix}"
        item, _retained, pointer, _before, _pointer_before, manifest = seed_retained_scratch_manifest(
            module, root, slug, instant, leaf_name=leaf_name
        )
        pointer.write_text(pointer_text, encoding="utf-8")
        manifest["evidenceRetention"][0]["canonicalPointerSha256"] = hashlib.sha256(
            pointer.read_bytes()
        ).hexdigest()

        if accepted:
            plans = module._prepare_evidence_retention(root, item, manifest)
            assert len(plans) == 1, suffix
            continue
        try:
            module._prepare_evidence_retention(root, item, manifest)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-BUG-DISPOSITIONS-DRIFT", suffix
        else:
            raise AssertionError(f"false pointer reference was admitted: {suffix}")


def test_retained_evidence_pointer_snapshot_limit_fails_before_hashing(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "retained-pointer-limit"
    instant = "2026-08-11T10:03:00Z"
    item, _retained, _pointer, _before, _pointer_before, manifest = seed_retained_scratch_manifest(
        module, root, slug, instant
    )
    capture = module._capture_file_snapshot

    def capture_with_tiny_limit(path: Path, *, failure_id: str, maximum_bytes: int = 4 * 1024 * 1024):
        return capture(path, failure_id=failure_id, maximum_bytes=1)

    with patch.object(module, "_capture_file_snapshot", side_effect=capture_with_tiny_limit):
        try:
            module._prepare_evidence_retention(root, item, manifest)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-BUG-DISPOSITIONS-INVALID"
        else:
            raise AssertionError("oversized canonical pointer was admitted")


def successor_binding_bytes(
    source_slug: str,
    successor_bytes: bytes,
    operation_id: str,
    *,
    accepted_by: str = "receiving-owner",
) -> bytes:
    return (
        json.dumps(
            {
                "schemaVersion": 1,
                "operationId": operation_id,
                "sourceReference": f"bug:{source_slug}",
                "registryReference": "external-bug-registry",
                "recordReference": "bug:accepted-successor",
                "recordSha256": hashlib.sha256(successor_bytes).hexdigest(),
                "acceptedBy": accepted_by,
                "acceptedAt": "2026-09-10T08:00:00Z",
                "acceptanceEvidence": "Receiving owner accepted the current successor.",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def successor_link_inventory_bytes(
    source_slug: str,
    source_bytes: bytes,
    binding_bytes: bytes,
    operation_id: str,
    links: list[dict] | None = None,
) -> bytes:
    return (
        json.dumps(
            {
                "schemaVersion": 1,
                "owner": "mutate-work-item:current-bug-supersession-v1",
                "operationId": operation_id,
                "sourceReference": f"bug:{source_slug}",
                "sourceBugSha256": hashlib.sha256(source_bytes).hexdigest(),
                "successorBindingSha256": hashlib.sha256(binding_bytes).hexdigest(),
                "links": [] if links is None else links,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def tree_file_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def historical_pass_fixture(tmp_path: Path):
    module = load_module()
    root = tmp_path / "repo"
    slug = "historical-pass"
    seed_active(module, root, slug)
    item = root / "work-items" / "active" / slug
    original = root / ".scratch" / "approved" / "original.md"
    write(original, "Original accepted artifact bytes.\n")
    source = root / "original-copy.md"
    source.write_bytes(original.read_bytes())
    event = {
        "schemaVersion": 2, "runId": "historical-pass-001", "workItem": slug,
        "role": "qa-engineer", "executionRole": "internal", "status": "completed",
        "gate": "PASS", "scope": ["historical artifact"],
        "artifact": ".scratch/approved/original.md", "eventKind": "standalone",
        "evidence": [{"kind": "review", "ref": "Original acceptance recorded"}],
        "startedAt": "2026-09-30T00:00:00Z", "updatedAt": "2026-09-30T00:00:00Z",
    }
    raw = json.dumps(event, separators=(",", ":")).encode("utf-8")
    # Physical ordinal and CR/LF-excluding identity must survive blank lines.
    ledger_bytes = b"\n" + raw + b"\r\n"
    (item / "agent-runs.jsonl").write_bytes(ledger_bytes)
    args = (
        "retain-pass-artifact", "--root", str(root), "--slug", slug,
        "--run-id", event["runId"], "--raw-line-ordinal", "2",
        "--expected-raw-line-sha256", hashlib.sha256(raw).hexdigest(),
        "--expected-ledger-sha256", hashlib.sha256(ledger_bytes).hexdigest(),
        "--source-artifact", "original-copy.md", "--expected-original-sha256",
        hashlib.sha256(source.read_bytes()).hexdigest(),
    )
    return module, root, item, original, source, event, ledger_bytes, args


def test_historical_pass_custody_cli_restores_exact_active_and_archive_authority(tmp_path: Path) -> None:
    module, root, item, original, source, event, before, args = historical_pass_fixture(tmp_path)
    validator = module._load_agent_run_ledger().load_validator()
    baseline = []
    assert validator.validate_work_item(item, authority_state_out=baseline) == []
    original.unlink()
    assert any("artifact does not exist" in error for error in validator.validate_work_item(item))

    result = run_cli(*args, "--apply")

    assert result.returncode == 0, result.stdout
    assert "WI-PASS-CUSTODY:" in result.stdout
    assert (item / "agent-runs.jsonl").read_bytes() == before
    current = []
    assert validator.validate_work_item(item, authority_state_out=current) == []
    assert current == baseline
    # Replacement current-path bytes must not stand in for the old artifact.
    original.write_bytes(b"Replacement bytes, not the accepted artifact.\n")
    assert validator.validate_work_item(item) == []
    archive = root / "work-items" / "archive" / "2026-10" / item.name
    archive.parent.mkdir(parents=True)
    shutil.move(str(item), archive)
    archived_errors, open_revise, open_launches = validator.validate_archived_ledger_obligations(archive)
    assert (archived_errors, open_revise, open_launches) == ([], [], [])
    assert (archive / "agent-runs.jsonl").read_bytes() == before
    association = next((archive / "review-artifact-custody" / "historical-pass").iterdir())
    snapshot = archive / json.loads(association.read_bytes())["snapshot"]
    assert snapshot.read_bytes() == source.read_bytes()
    snapshot.write_bytes(b"Replacement bytes, not the accepted artifact.\n")
    assert any("WI-LEDGER-CUSTODY-SNAPSHOT-MISMATCH" in error
               for error in validator.validate_archived_ledger_obligations(archive)[0])


def test_historical_pass_custody_omitted_apply_and_rewritten_source_preserve_bytes(tmp_path: Path) -> None:
    module, root, item, original, source, event, before, args = historical_pass_fixture(tmp_path)
    original.unlink()
    untouched = tree_file_bytes(root)
    refusal = run_cli(*args)
    assert refusal.returncode != 0 and "WI-LEDGER-CUSTODY-APPLY-REQUIRED" in refusal.stdout
    assert tree_file_bytes(root) == untouched
    with unittest.TestCase().assertRaises(module.LifecycleError) as failure:
        module.retain_historical_pass_custody(
            root, item.name, event["runId"], 2, args[args.index("--expected-raw-line-sha256") + 1],
            args[args.index("--expected-ledger-sha256") + 1], "original-copy.md",
            args[args.index("--expected-original-sha256") + 1],
        )
    assert failure.exception.failure_id == "WI-LEDGER-CUSTODY-APPLY-REQUIRED"
    assert tree_file_bytes(root) == untouched
    source.write_bytes(b"Rewritten current candidate, not the original.\n")
    untouched = tree_file_bytes(root)
    refusal = run_cli(*args, "--apply")
    assert refusal.returncode != 0 and "WI-LEDGER-CUSTODY-SOURCE-DRIFT" in refusal.stdout
    assert tree_file_bytes(root) == untouched
    assert (item / "agent-runs.jsonl").read_bytes() == before


def test_historical_pass_custody_exact_replay_after_append_is_publication_free(tmp_path: Path) -> None:
    module, root, item, original, source, event, before, args = historical_pass_fixture(tmp_path)
    original.unlink()
    assert run_cli(*args, "--apply").returncode == 0
    terminal = {**event, "runId": "later-neutral-terminal", "gate": "none"}
    terminal.pop("artifact")
    (item / "agent-runs.jsonl").write_bytes(before + json.dumps(terminal).encode("utf-8") + b"\n")
    untouched = tree_file_bytes(root)
    replay = run_cli(*args, "--apply")
    assert replay.returncode == 0, replay.stdout
    assert tree_file_bytes(root) == untouched
    conflicted = list(args)
    conflicted[conflicted.index("--expected-original-sha256") + 1] = "0" * 64
    refusal = run_cli(*conflicted, "--apply")
    assert refusal.returncode != 0 and "WI-LEDGER-CUSTODY-STALE-TARGET" in refusal.stdout
    assert tree_file_bytes(root) == untouched


def test_historical_pass_custody_tampered_prefix_ordinal_and_codec_fail_closed(tmp_path: Path) -> None:
    for defect in ("ledger-prefix", "ordinal", "noncanonical-envelope"):
        module, root, item, original, source, event, before, args = historical_pass_fixture(tmp_path / defect)
        original.unlink()
        assert run_cli(*args, "--apply").returncode == 0
        validator = module._load_agent_run_ledger().load_validator()
        association = next((item / "review-artifact-custody" / "historical-pass").iterdir())
        if defect == "ledger-prefix":
            (item / "agent-runs.jsonl").write_bytes(before.replace(b"historical artifact", b"changed artifact"))
        elif defect == "ordinal":
            envelope = json.loads(association.read_bytes())
            envelope["rawLineOrdinal"] = 1
            association.write_bytes(validator._canonical_projection_bytes(envelope))
        else:
            association.write_bytes(json.dumps(json.loads(association.read_bytes()), indent=2).encode("utf-8"))
        errors = validator.validate_work_item(item)
        assert any("WI-LEDGER-CUSTODY-STALE-TARGET" in error for error in errors), (defect, errors)
        untouched = tree_file_bytes(root)
        refusal = run_cli(*args, "--apply")
        assert refusal.returncode != 0 and "WI-LEDGER-CUSTODY-STALE-TARGET" in refusal.stdout
        assert tree_file_bytes(root) == untouched


def test_historical_pass_custody_failed_publication_removes_only_new_snapshot(tmp_path: Path) -> None:
    for shared in (False, True):
        module, root, item, original, source, event, before, args = historical_pass_fixture(tmp_path / str(shared))
        original.unlink()
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if shared:
            directory = item / "review-artifact-custody"
            directory.mkdir()
            (directory / digest).write_bytes(source.read_bytes())
        untouched = tree_file_bytes(root)
        with patch.object(module, "_atomic_write", side_effect=OSError("injected publication failure")):
            with unittest.TestCase().assertRaises(OSError):
                module.retain_historical_pass_custody(
                    root, item.name, event["runId"], 2, args[args.index("--expected-raw-line-sha256") + 1],
                    hashlib.sha256(before).hexdigest(), "original-copy.md", digest, apply=True,
                )
        assert tree_file_bytes(root) == untouched
        assert not (item / "review-artifact-custody" / "historical-pass").exists()
        assert (item / "review-artifact-custody" / digest).exists() is shared


def test_historical_pass_custody_snapshot_acquisition_failure_preserves_canonical_bytes(tmp_path: Path) -> None:
    module, root, item, original, source, event, before, args = historical_pass_fixture(tmp_path)
    original.unlink()
    untouched = tree_file_bytes(root)
    ledger = module._load_agent_run_ledger()
    acquire = ledger._acquire_custody_snapshot

    def fail_after_capture(*arguments, **kwargs):
        acquire(*arguments, **kwargs)
        raise OSError("injected failure after snapshot acquisition")

    with patch.object(ledger, "_acquire_custody_snapshot", side_effect=fail_after_capture):
        with unittest.TestCase().assertRaises(OSError):
            module.retain_historical_pass_custody(
                root, item.name, event["runId"], 2, args[args.index("--expected-raw-line-sha256") + 1],
                hashlib.sha256(before).hexdigest(), "original-copy.md", hashlib.sha256(source.read_bytes()).hexdigest(),
                apply=True,
            )
    assert tree_file_bytes(root) == untouched


def test_historical_pass_custody_candidate_uses_one_captured_ledger(tmp_path: Path) -> None:
    fixture_spec = importlib.util.spec_from_file_location("captured_custody_fixtures", ROOT / "tests" / "test_agent_run_ledger.py")
    h1_fixtures = importlib.util.module_from_spec(fixture_spec)
    fixture_spec.loader.exec_module(h1_fixtures)
    for state in ("ordinary", "active", "revoked"):
        if state == "ordinary":
            module, root, item, original, source, event, raw, args = historical_pass_fixture(tmp_path / state)
            original.unlink()
            ordinal = 2
            line_sha = args[args.index("--expected-raw-line-sha256") + 1]
            validator = module._load_agent_run_ledger().load_validator()
        else:
            validator, root, item, source, raw, line, event, _path = h1_fixtures.historical_pass_h1_fixture(tmp_path / state, state)
            (item / "target.md").unlink()
            module = load_module()
            ordinal = 4
            line_sha = hashlib.sha256(line).hexdigest()
        selected = item / "agent-runs.jsonl"
        ledger = module._load_agent_run_ledger()
        capture = module._capture_file_snapshot
        resolve = validator.resolve_historical_pass_custody
        read = Path.read_bytes
        captured = []
        resolver_sources = []
        forbidden_reads = []

        def observe_capture(path, **kwargs):
            snapshot = capture(path, **kwargs)
            if path == selected:
                captured.append(snapshot)
            return snapshot

        def observe_resolver(custody_item, source_bytes, *arguments, **kwargs):
            if custody_item == item:
                resolver_sources.append(source_bytes)
            return resolve(custody_item, source_bytes, *arguments, **kwargs)

        def deny_reacquisition(path):
            if path == selected:
                forbidden_reads.append(path)
                raise OSError("selected ledger was already captured by its owner")
            return read(path)

        failure = None
        with patch.object(ledger, "load_validator", return_value=validator), \
                patch.object(module, "_capture_file_snapshot", side_effect=observe_capture), \
                patch.object(validator, "resolve_historical_pass_custody", side_effect=observe_resolver), \
                patch.object(Path, "read_bytes", deny_reacquisition):
            try:
                module.retain_historical_pass_custody(
                    root, item.name, event["runId"], ordinal, line_sha,
                    hashlib.sha256(raw).hexdigest(), "original-copy.md",
                    hashlib.sha256(read(source)).hexdigest(), apply=True,
                )
            except module.LifecycleError as exc:
                failure = exc
        assert forbidden_reads == [], (state, failure)
        assert failure is None, (state, failure)
        assert len(captured) == 1 and len(resolver_sources) == 1, (state, len(captured), len(resolver_sources))
        assert resolver_sources[0] is captured[0].data
        assert selected.read_bytes() == raw


def _active_successor_preflight_fixture(root: Path, *, leaf_count: int = 30) -> dict:
    module = load_module()
    old, new = "front-old", "front-new"
    work_items = root / "work-items"
    archive = work_items / "archive" / "2026-09" / old
    source = work_items / "active" / old
    archive.mkdir(parents=True)
    source.mkdir(parents=True)
    equal_count = leaf_count - 8
    for ordinal in range(equal_count):
        name = f"shared-{ordinal:02d}.md"
        data = f"historical evidence {ordinal}\n".encode()
        (archive / name).write_bytes(data)
        (source / name).write_bytes(data)
    archived_rows = []
    admission = json.loads(module._staged_admission_ledger_bytes(old, staged_status(old).encode()))
    for ordinal in range(29):
        row = dict(admission, runId=f"{old}-run-{ordinal:02d}")
        archived_rows.append((json.dumps(row, sort_keys=True) + "\n").encode())
    (archive / "agent-runs.jsonl").write_bytes(b"".join(archived_rows))
    (source / "agent-runs.jsonl").write_bytes(b"".join(archived_rows[:25]))
    write(archive / "status.md", "status: completed\n")
    write(archive / "closure.md", closure("2026-09-20T03:41:38Z"))
    write(archive / "bug-dispositions-receipt.json", '{"state":"committed"}\n')
    for name in (
        "architecture-adversarial-reverify.md", "design.md", "performance-review.md",
        "performance.md", "qa-reverify.md", "recovery-index-audit.md",
    ):
        write(source / name, f"later source evidence: {name}\n")
    write(source / "status.md", quick_status("A2 installed receiving remains open."))
    index_before = f"- [Front current](active/{old}/status.md)\n"
    index_after = f"- [{new} current](active/{new}/status.md)\n"
    (work_items / "index.md").write_bytes(
        ("# Compatibility\n" + index_before + "\nOther row.\n").encode()
    )
    write(
        work_items / "README.md",
        module._default_static_guide() + module.README_BEGIN + "\n" + module.README_END + "\n",
    )
    status = staged_status(old).replace(
        "Next action: Verify successor identity.",
        "Next action: Complete the open A2 installed receiving gate.",
    ).encode()
    dispositions = {
        "indexRowBefore": index_before,
        "indexRowAfter": index_after,
        "references": [],
    }
    return {
        "module": module, "old": old, "new": new, "source": source,
        "archive": archive, "status": status, "dispositions": dispositions,
    }


def test_import_active_successor_preflight_binds_all_bytes_without_writes(tmp_path: Path) -> None:
    root = tmp_path / "case"
    fixture = _active_successor_preflight_fixture(root)
    module = fixture["module"]
    before = tree_file_bytes(root / "work-items")
    assert hasattr(module, "preflight_import_active_successor")
    plan = module.preflight_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], "front-import-1",
    )
    bindings = plan["fileBindings"]
    assert len(bindings) == 30
    assert {row["sourceRelativePath"] for row in bindings} == {
        path.relative_to(fixture["source"]).as_posix()
        for path in fixture["source"].rglob("*") if path.is_file()
    }
    assert {row["sourceSha256"] for row in bindings} == {
        hashlib.sha256(path.read_bytes()).hexdigest()
        for path in fixture["source"].rglob("*") if path.is_file()
    }
    assert [row["kind"] for row in bindings].count("archive-equal") == 22
    assert [row["kind"] for row in bindings].count("archive-ledger-prefix") == 1
    assert [row["kind"] for row in bindings].count("successor-copy") == 7
    assert plan["ledgerArchivePrefix"]["lineCount"] == 25
    assert plan["ledgerArchivePrefix"]["byteCount"] == len(
        (fixture["source"] / "agent-runs.jsonl").read_bytes()
    )
    assert next(row for row in bindings if row["sourceRelativePath"] == "status.md")["targetPath"].endswith(
        "/imported-source/status.md"
    )
    assert not (root / "work-items" / "active" / fixture["new"] / "agent-runs.jsonl").exists()
    assert tree_file_bytes(root / "work-items") == before
    alternate_root = tmp_path / "different-leaf-count"
    alternate = _active_successor_preflight_fixture(alternate_root, leaf_count=11)
    alternate_plan = alternate["module"].preflight_import_active_successor(
        alternate_root, alternate["old"], alternate["new"], alternate["status"],
        alternate["dispositions"], "front-import-2",
    )
    assert len(alternate_plan["fileBindings"]) == 11
    assert [row["kind"] for row in alternate_plan["fileBindings"]].count("archive-equal") == 3


def test_import_active_successor_preflight_binds_index_and_dual_readme(tmp_path: Path) -> None:
    root = tmp_path / "case"
    fixture = _active_successor_preflight_fixture(root)
    module = fixture["module"]
    work_items = root / "work-items"
    before = tree_file_bytes(work_items)
    try:
        module.render_readme_bytes(root)
    except module.LifecycleError as error:
        assert error.failure_id == "WI-CATEGORY-DUAL-LOCATION"
    else:
        raise AssertionError("ordinary renderer admitted the dual input")
    consumer = work_items / "backlog" / "consumer.md"
    write(consumer, (
        f"status: candidate\n[Current](../active/{fixture['old']}/status.md)\n"
        f"Relation: work-item:{fixture['old']}\n"
    ))
    before = tree_file_bytes(work_items)
    fixture["dispositions"]["references"] = [{
        "consumer": "backlog/consumer.md", "kind": "physical",
        "value": f"../active/{fixture['old']}/status.md",
        "target": f"work-items/active/{fixture['new']}/status.md",
    }, {
        "consumer": "backlog/consumer.md", "kind": "logical",
        "value": f"work-item:{fixture['old']}",
        "meaning": "current-successor",
    }]
    plan = module.preflight_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], "front-import-1",
    )
    assert plan["compatibilityIndex"]["beforeSha256"] == hashlib.sha256(
        (work_items / "index.md").read_bytes()
    ).hexdigest()
    assert plan["compatibilityIndex"]["afterBytes"].endswith(
        b"\nOther row.\n"
    )
    assert plan["readme"]["beforeSha256"] == hashlib.sha256(
        (work_items / "README.md").read_bytes()
    ).hexdigest()
    assert b"active/front-new/status.md" in plan["readme"]["afterBytes"]
    assert b"archive/2026-09/front-old/closure.md" in plan["readme"]["afterBytes"]
    assert b"work-item:front-new" in base64.b64decode(plan["links"][0]["afterBase64"])
    assert plan["digest"] == hashlib.sha256(plan["canonicalBytes"]).hexdigest()
    assert tree_file_bytes(work_items) == before
    assert module.preflight_import_active_successor(
        work_items, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], "front-import-1",
    )["digest"] == plan["digest"]
    status_input = tmp_path / "successor-status.md"
    links_input = tmp_path / "successor-links.json"
    status_input.write_bytes(fixture["status"])
    links_input.write_bytes(json.dumps(fixture["dispositions"]).encode())
    argv = (
        "import-active-successor", "--root", str(root),
        "--predecessor-slug", fixture["old"],
        "--successor-slug", fixture["new"],
        "--status-file", str(status_input),
        "--links-file", str(links_input),
        "--operation-id", "front-import-1",
    )
    result = run_cli(*argv)
    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout)["digest"] == plan["digest"]
    assert tree_file_bytes(work_items) == before


def test_import_active_successor_preflight_rejects_unsafe_inputs(tmp_path: Path) -> None:
    cases = (
        ("ledger", "WI-SUCCESSOR-LEDGER-DIVERGENCE"),
        ("occupied", "WI-SUCCESSOR-IDENTITY-CONFLICT"),
        ("index", "WI-SUCCESSOR-LINK-UNMAPPED"),
        ("readme", "WI-README-MARKERS"),
        ("unclassified", "WI-SUCCESSOR-LINK-UNMAPPED"),
        ("hardlink", "WI-SUCCESSOR-IMPORT-UNSAFE-INPUT"),
        ("index_extra", "WI-SUCCESSOR-LINK-UNMAPPED"),
        ("third", "WI-SUCCESSOR-IDENTITY-CONFLICT"),
        ("projection", "WI-SUCCESSOR-LEDGER-DIVERGENCE"),
        ("escape", "WI-SUCCESSOR-LINK-UNMAPPED"),
        ("shadow", "WI-SUCCESSOR-READMODEL-INVALID"),
        ("occupied_file", "WI-SUCCESSOR-IDENTITY-CONFLICT"),
        ("third_file", "WI-SUCCESSOR-IDENTITY-CONFLICT"),
        ("malformed_disposition", "WI-SUCCESSOR-LINK-UNMAPPED"),
    )
    for case, failure_id in cases:
        root = tmp_path / case
        fixture = _active_successor_preflight_fixture(root)
        work_items = root / "work-items"
        if case == "ledger":
            with (fixture["source"] / "agent-runs.jsonl").open("ab") as stream:
                stream.write(b"not a prefix\n")
        elif case == "occupied":
            write(work_items / "active" / fixture["new"] / "status.md", "status: active\n")
        elif case == "index":
            (work_items / "index.md").write_bytes(b"# No current row\n")
        elif case == "readme":
            (work_items / "README.md").write_bytes(b"# No markers\n")
        elif case == "unclassified":
            write(work_items / "backlog" / "consumer.md",
                  f"status: candidate\n[Current](../active/{fixture['old']}/status.md)\n")
        elif case == "hardlink":
            os.link(fixture["source"] / "design.md", fixture["source"] / "linked.md")
        elif case == "index_extra":
            with (work_items / "index.md").open("ab") as stream:
                stream.write(f"- [Old evidence](active/{fixture['old']}/design.md)\n".encode())
        elif case == "third":
            write(work_items / "backlog" / f"{fixture['old']}.md", "status: candidate\n")
        elif case == "projection":
            ledger = fixture["archive"] / "agent-runs.jsonl"
            rows = ledger.read_bytes().splitlines(keepends=True)
            rows[-1] = b"{invalid json}\n"
            ledger.write_bytes(b"".join(rows))
        elif case == "escape":
            fixture["dispositions"]["indexRowAfter"] = (
                f"- [{fixture['new']} current](../outside/status.md)\n"
            )
        elif case == "shadow":
            fixture["status"] += b"Roadmap: missing-roadmap\n"
        elif case == "occupied_file":
            write(work_items / "active" / fixture["new"], "occupied\n")
        elif case == "third_file":
            write(work_items / "archive" / "2026-10" / fixture["old"], "occupied\n")
        elif case == "malformed_disposition":
            write(work_items / "backlog" / "consumer.md",
                  f"status: candidate\n[Current](../active/{fixture['old']}/status.md)\n")
            fixture["dispositions"]["references"] = [{
                "consumer": "backlog/consumer.md", "kind": "physical",
                "value": f"../active/{fixture['old']}/status.md",
                "target": [f"work-items/active/{fixture['new']}/status.md"],
            }]
        before = tree_file_bytes(work_items)
        try:
            fixture["module"].preflight_import_active_successor(
                root, fixture["old"], fixture["new"], fixture["status"],
                fixture["dispositions"], "front-import-1",
            )
        except fixture["module"].LifecycleError as error:
            assert error.failure_id == failure_id, case
        else:
            raise AssertionError(f"unsafe {case} input was admitted")
        assert tree_file_bytes(work_items) == before, case


def test_import_active_successor_preflight_keeps_valid_source_status_as_evidence(tmp_path: Path) -> None:
    root = tmp_path / "case"
    fixture = _active_successor_preflight_fixture(root)
    module = fixture["module"]
    source_status = fixture["source"] / "status.md"
    before = tree_file_bytes(root / "work-items")
    plan = module.preflight_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], "front-import-status",
    )
    binding = next(row for row in plan["fileBindings"] if row["sourceRelativePath"] == "status.md")
    assert binding["kind"] == "successor-copy"
    assert binding["targetPath"] == "work-items/active/front-new/imported-source/status.md"
    assert tree_file_bytes(root / "work-items") == before

    source_status.write_bytes((fixture["archive"] / "status.md").read_bytes())
    before = tree_file_bytes(root / "work-items")
    try:
        module.preflight_import_active_successor(
            root, fixture["old"], fixture["new"], fixture["status"],
            fixture["dispositions"], "front-import-status",
        )
    except module.LifecycleError as error:
        assert error.failure_id == "WI-CATEGORY-TERMINAL-IN-CURRENT"
    else:
        raise AssertionError("terminal source status was admitted as current")
    assert tree_file_bytes(root / "work-items") == before


def test_import_active_successor_preflight_projects_planned_consumer_bytes(tmp_path: Path) -> None:
    root = tmp_path / "case"
    fixture = _active_successor_preflight_fixture(root)
    module = fixture["module"]
    work_items = root / "work-items"
    consumer = work_items / "backlog" / "consumer.md"
    write(consumer, (
        f"status: candidate\n[Current](../active/{fixture['old']}/status.md)\n"
        f"Relation: work-item:{fixture['old']}\n"
    ))
    fixture["dispositions"]["references"] = [{
        "consumer": "backlog/consumer.md", "kind": "physical",
        "value": f"../active/{fixture['old']}/status.md",
        "target": f"work-items/active/{fixture['new']}/status.md",
    }, {
        "consumer": "backlog/consumer.md", "kind": "logical",
        "value": f"work-item:{fixture['old']}", "meaning": "current-successor",
    }]
    before = tree_file_bytes(work_items)
    plan = module.preflight_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], "front-import-links",
    )
    after_consumer = base64.b64decode(plan["links"][0]["afterBase64"])
    with tempfile.TemporaryDirectory() as directory:
        shadow_root = Path(directory)
        shadow_work_items = shadow_root / "work-items"
        shutil.copytree(work_items, shadow_work_items)
        shutil.rmtree(shadow_work_items / "active" / fixture["old"])
        shadow_status = shadow_work_items / "active" / fixture["new"] / "status.md"
        shadow_status.parent.mkdir(parents=True)
        shadow_status.write_bytes(fixture["status"])
        (shadow_work_items / "backlog" / "consumer.md").write_bytes(after_consumer)
        expected = module.render_readme_bytes(
            shadow_root, static_guide_override=module._static_guide(work_items / "README.md"),
        )
    assert plan["readme"]["afterBytes"] == expected
    assert next(row for row in plan["canonicalInputs"]
                if row["path"] == "work-items/backlog/consumer.md")["sha256"] == (
                    hashlib.sha256(after_consumer).hexdigest()
                )
    assert tree_file_bytes(work_items) == before


def test_import_active_successor_preflight_rejects_old_visible_index_label(tmp_path: Path) -> None:
    root = tmp_path / "case"
    fixture = _active_successor_preflight_fixture(root)
    module = fixture["module"]
    fixture["dispositions"]["indexRowAfter"] = (
        f"- [{fixture['old']} current](active/{fixture['new']}/status.md)\n"
    )
    before = tree_file_bytes(root / "work-items")
    try:
        module.preflight_import_active_successor(
            root, fixture["old"], fixture["new"], fixture["status"],
            fixture["dispositions"], "front-import-index",
        )
    except module.LifecycleError as error:
        assert error.failure_id == "WI-SUCCESSOR-LINK-UNMAPPED"
    else:
        raise AssertionError("old visible index label was admitted")
    assert tree_file_bytes(root / "work-items") == before


def test_import_active_successor_apply_preserves_archive_and_run_authority(tmp_path: Path) -> None:
    root = tmp_path / "candidate"
    fixture = _active_successor_preflight_fixture(root)
    module = fixture["module"]
    plan = module.preflight_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], "front-apply-1",
    )
    source_before = tree_file_bytes(fixture["source"])
    archive_before = tree_file_bytes(fixture["archive"])
    assert hasattr(module, "apply_import_active_successor")
    result = module.apply_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], "front-apply-1", plan["digest"],
    )
    successor = root / "work-items" / "active" / fixture["new"]
    receipt = root / result["receiptPath"]
    persisted = json.loads(receipt.read_bytes())
    assert result["state"] == "committed" and result["alreadySettled"] is False
    assert persisted["operationId"] == "front-apply-1"
    assert persisted["preflightDigest"] == plan["digest"]
    assert persisted["sourceTreeSha256"] == plan["sourceTreeSha256"]
    assert persisted["archiveTreeSha256"] == plan["archiveTreeSha256"]
    assert persisted["ledgerArchivePrefix"] == plan["ledgerArchivePrefix"]
    assert persisted["fileBindings"] == plan["fileBindings"]
    assert tree_file_bytes(fixture["archive"]) == archive_before
    assert not fixture["source"].exists()
    assert module.resolve_category(root, f"work-item:{fixture['old']}") == fixture["archive"]
    assert module.resolve_category(root, f"work-item:{fixture['new']}") == successor
    assert (successor / "status.md").read_bytes() == fixture["status"]
    assert not (successor / "agent-runs.jsonl").exists()
    assert not (successor / "imported-source" / "agent-runs.jsonl").exists()
    for binding in plan["fileBindings"]:
        original = source_before[binding["sourceRelativePath"]]
        target = root / binding["targetPath"]
        if binding["kind"] == "archive-ledger-prefix":
            assert target.read_bytes().startswith(original)
        else:
            assert target.read_bytes() == original
    assert (successor / "imported-source" / "status.md").read_bytes() == source_before["status.md"]
    assert (root / "work-items" / "README.md").read_bytes() == plan["readme"]["afterBytes"]
    module.check_readme(root)
    assert receipt.parent == successor
    assert not module._transition_intent_path(root, "front-apply-1").exists()
    assert not (root / ".scratch" / "work-items-lifecycle-successor-imports").exists()


def test_import_active_successor_apply_maps_index_links_and_readme(tmp_path: Path) -> None:
    root = tmp_path / "candidate"
    fixture = _active_successor_preflight_fixture(root)
    module = fixture["module"]
    work_items = root / "work-items"
    consumer = work_items / "backlog" / "consumer.md"
    write(consumer, (
        f"status: candidate\n[Current](../active/{fixture['old']}/status.md)\n"
        f"Relation: work-item:{fixture['old']}\n"
    ))
    fixture["dispositions"]["references"] = [{
        "consumer": "backlog/consumer.md", "kind": "physical",
        "value": f"../active/{fixture['old']}/status.md",
        "target": f"work-items/active/{fixture['new']}/status.md",
    }, {
        "consumer": "backlog/consumer.md", "kind": "logical",
        "value": f"work-item:{fixture['old']}", "meaning": "current-successor",
    }]
    plan = module.preflight_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], "front-apply-links",
    )
    archive_before = tree_file_bytes(fixture["archive"])
    index_before = (work_items / "index.md").read_bytes()
    status_input = tmp_path / "status.md"
    links_input = tmp_path / "links.json"
    status_input.write_bytes(fixture["status"])
    links_input.write_bytes(json.dumps(fixture["dispositions"]).encode())
    result = run_cli(
        "import-active-successor", "--root", str(root),
        "--predecessor-slug", fixture["old"],
        "--successor-slug", fixture["new"],
        "--status-file", str(status_input), "--links-file", str(links_input),
        "--operation-id", "front-apply-links", "--apply",
        "--preflight-digest", plan["digest"],
    )
    assert result.returncode == 0, result.stdout
    applied = json.loads(result.stdout)
    assert applied["state"] == "committed" and applied["alreadySettled"] is False
    assert tree_file_bytes(fixture["archive"]) == archive_before
    assert consumer.read_bytes() == base64.b64decode(plan["links"][0]["afterBase64"])
    assert b"work-item:front-new" in consumer.read_bytes()
    assert (work_items / "index.md").read_bytes() == plan["compatibilityIndex"]["afterBytes"]
    assert (work_items / "index.md").read_bytes().replace(
        fixture["dispositions"]["indexRowAfter"].encode(),
        fixture["dispositions"]["indexRowBefore"].encode(),
    ) == index_before
    assert (consumer.parent / f"../active/{fixture['new']}/status.md").resolve().is_file()
    assert (work_items / "README.md").read_bytes() == plan["readme"]["afterBytes"]
    module.check_readme(root)
    replay = module.apply_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], "front-apply-links", plan["digest"],
    )
    assert replay["state"] == "committed" and replay["alreadySettled"] is True
    try:
        module.apply_import_active_successor(
            root, fixture["old"], fixture["new"], fixture["status"] + b"changed\n",
            fixture["dispositions"], "front-apply-links", plan["digest"],
        )
    except module.LifecycleError as error:
        assert error.failure_id == "WI-SUCCESSOR-IDENTITY-CONFLICT"
    else:
        raise AssertionError("changed replay was accepted")


def test_import_active_successor_fault_recovery_and_replay(tmp_path: Path) -> None:
    checkpoints = (
        "before-source-hold", "after-source-hold", "after-successor-publish",
        "after-links-publish", "after-readme-publish", "after-receipt-publish",
    )
    for checkpoint in checkpoints:
        root = tmp_path / checkpoint
        fixture = _active_successor_preflight_fixture(root)
        module = fixture["module"]
        operation = "front-fault-1"
        plan = module.preflight_import_active_successor(
            root, fixture["old"], fixture["new"], fixture["status"],
            fixture["dispositions"], operation,
        )
        before = tree_file_bytes(root / "work-items")
        assert hasattr(module, "apply_import_active_successor")
        try:
            module.apply_import_active_successor(
                root, fixture["old"], fixture["new"], fixture["status"],
                fixture["dispositions"], operation, plan["digest"],
                inject_failure_at=checkpoint,
            )
        except module.LifecycleError as error:
            assert error.failure_id == "WI-SUCCESSOR-IMPORT-RECOVERY", checkpoint
            assert operation in str(error) and checkpoint in str(error)
        else:
            raise AssertionError(f"fault {checkpoint} reported success")
        intent_path = module._transition_intent_path(root, operation)
        if intent_path.exists():
            intent = module._load_transition_intent(root, intent_path)
            assert intent["operationId"] == operation
            if checkpoint == "after-receipt-publish":
                pending_before = tree_file_bytes(root)
                try:
                    module.apply_import_active_successor(
                        root, fixture["old"], fixture["new"], fixture["status"],
                        fixture["dispositions"], operation, plan["digest"],
                    )
                except module.LifecycleError as error:
                    assert error.failure_id == "WI-SUCCESSOR-IMPORT-RECOVERY"
                    assert operation in str(error)
                else:
                    raise AssertionError("pending committed intent replay reported success")
                assert tree_file_bytes(root) == pending_before
                assert intent_path.is_file()
            if checkpoint == "after-source-hold":
                with module.LifecycleTransaction(root):
                    try:
                        module._recover_transition(root, intent_path)
                    except module.LifecycleError as error:
                        assert error.failure_id == "WI-LIFECYCLE-LOCK-HELD"
                    else:
                        raise AssertionError("successor recovery bypassed the lifecycle lock")
            module._recover_transition(root, intent_path)
        successor = root / "work-items" / "active" / fixture["new"]
        if checkpoint == "after-receipt-publish":
            assert successor.is_dir() and not fixture["source"].exists()
            replay = module.apply_import_active_successor(
                root, fixture["old"], fixture["new"], fixture["status"],
                fixture["dispositions"], operation, plan["digest"],
            )
            assert replay["alreadySettled"] is True
            module.check_readme(root)
        else:
            assert tree_file_bytes(root / "work-items") == before, checkpoint
            assert fixture["source"].is_dir() and not successor.exists()
        assert not intent_path.exists(), checkpoint

    corrupt_root = tmp_path / "corrupt-held-source"
    corrupt_fixture = _active_successor_preflight_fixture(corrupt_root)
    corrupt_module = corrupt_fixture["module"]
    corrupt_plan = corrupt_module.preflight_import_active_successor(
        corrupt_root, corrupt_fixture["old"], corrupt_fixture["new"],
        corrupt_fixture["status"], corrupt_fixture["dispositions"], "front-corrupt-1",
    )
    try:
        corrupt_module.apply_import_active_successor(
            corrupt_root, corrupt_fixture["old"], corrupt_fixture["new"],
            corrupt_fixture["status"], corrupt_fixture["dispositions"],
            "front-corrupt-1", corrupt_plan["digest"],
            inject_failure_at="after-source-hold",
        )
    except corrupt_module.LifecycleError as error:
        assert error.failure_id == "WI-SUCCESSOR-IMPORT-RECOVERY"
    else:
        raise AssertionError("held-source interruption reported success")
    corrupt_intent_path = corrupt_module._transition_intent_path(corrupt_root, "front-corrupt-1")
    corrupt_intent = corrupt_module._load_transition_intent(corrupt_root, corrupt_intent_path)
    held_design = corrupt_root / corrupt_intent["sourceHoldPath"] / "design.md"
    held_design.write_bytes(b"corrupt held source\n")
    corrupted_before = tree_file_bytes(corrupt_root)
    try:
        corrupt_module._recover_transition(corrupt_root, corrupt_intent_path)
    except corrupt_module.LifecycleError as error:
        assert error.failure_id == "WI-SUCCESSOR-IMPORT-RECOVERY"
        assert "front-corrupt-1" in str(error)
    else:
        raise AssertionError("corrupt staging was silently recovered")
    assert tree_file_bytes(corrupt_root) == corrupted_before
    assert corrupt_intent_path.is_file()

    for surface in ("source", "archive", "consumer", "index", "readme", "digest"):
        root = tmp_path / f"drift-{surface}"
        fixture = _active_successor_preflight_fixture(root)
        module = fixture["module"]
        if surface == "consumer":
            write(root / "work-items" / "backlog" / "consumer.md",
                  f"status: candidate\n[Current](../active/{fixture['old']}/status.md)\n")
            fixture["dispositions"]["references"] = [{
                "consumer": "backlog/consumer.md", "kind": "physical",
                "value": f"../active/{fixture['old']}/status.md",
                "target": f"work-items/active/{fixture['new']}/status.md",
            }]
        plan = module.preflight_import_active_successor(
            root, fixture["old"], fixture["new"], fixture["status"],
            fixture["dispositions"], "front-drift-1",
        )
        if surface == "source":
            with (fixture["source"] / "design.md").open("ab") as stream:
                stream.write(b"drift\n")
        elif surface == "archive":
            with (fixture["archive"] / "design.md").open("ab") as stream:
                stream.write(b"drift\n")
        elif surface == "index":
            with (root / "work-items" / "index.md").open("ab") as stream:
                stream.write(b"drift\n")
        elif surface == "consumer":
            with (root / "work-items" / "backlog" / "consumer.md").open("ab") as stream:
                stream.write(b"drift\n")
        elif surface == "readme":
            with (root / "work-items" / "README.md").open("ab") as stream:
                stream.write(b"drift\n")
        before = tree_file_bytes(root / "work-items")
        try:
            module.apply_import_active_successor(
                root, fixture["old"], fixture["new"], fixture["status"],
                fixture["dispositions"], "front-drift-1",
                ("0" * 64 if surface == "digest" else plan["digest"]),
            )
        except module.LifecycleError as error:
            assert error.failure_id == "WI-SUCCESSOR-IMPORT-DRIFT", surface
        else:
            raise AssertionError(f"drifted {surface} input was applied")
        assert tree_file_bytes(root / "work-items") == before, surface
        assert not module._transition_intent_path(root, "front-drift-1").exists()


def test_import_active_successor_fault_post_receipt_corrupt_hold_replay_refuses(tmp_path: Path) -> None:
    root = tmp_path / "candidate"
    fixture = _active_successor_preflight_fixture(root)
    module = fixture["module"]
    operation = "front-post-receipt-corrupt"
    plan = module.preflight_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], operation,
    )
    try:
        module.apply_import_active_successor(
            root, fixture["old"], fixture["new"], fixture["status"],
            fixture["dispositions"], operation, plan["digest"],
            inject_failure_at="after-receipt-publish",
        )
    except module.LifecycleError as error:
        assert error.failure_id == "WI-SUCCESSOR-IMPORT-RECOVERY"
    else:
        raise AssertionError("post-receipt interruption reported success")
    intent_path = module._transition_intent_path(root, operation)
    intent = module._load_transition_intent(root, intent_path)
    held_design = root / intent["sourceHoldPath"] / "design.md"
    held_design.write_bytes(b"corrupt after receipt\n")
    pending_before = tree_file_bytes(root)
    try:
        module.apply_import_active_successor(
            root, fixture["old"], fixture["new"], fixture["status"],
            fixture["dispositions"], operation, plan["digest"],
        )
    except module.LifecycleError as error:
        assert error.failure_id == "WI-SUCCESSOR-IMPORT-RECOVERY"
        assert operation in str(error)
    else:
        raise AssertionError("corrupt held source was replayed as settled")
    assert tree_file_bytes(root) == pending_before
    assert intent_path.is_file() and held_design.read_bytes() == b"corrupt after receipt\n"


def test_import_active_successor_fault_corrupt_receipt_refuses_replay(tmp_path: Path) -> None:
    root = tmp_path / "candidate"
    fixture = _active_successor_preflight_fixture(root)
    module = fixture["module"]
    plan = module.preflight_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], "front-receipt-1",
    )
    applied = module.apply_import_active_successor(
        root, fixture["old"], fixture["new"], fixture["status"],
        fixture["dispositions"], "front-receipt-1", plan["digest"],
    )
    receipt_path = root / applied["receiptPath"]
    corrupted = json.loads(receipt_path.read_bytes())
    corrupted.pop("fileBindings")
    receipt_path.write_bytes((json.dumps(corrupted, indent=2, sort_keys=True) + "\n").encode())
    before = tree_file_bytes(root / "work-items")
    try:
        module.apply_import_active_successor(
            root, fixture["old"], fixture["new"], fixture["status"],
            fixture["dispositions"], "front-receipt-1", plan["digest"],
        )
    except module.LifecycleError as error:
        assert error.failure_id == "WI-SUCCESSOR-IMPORT-RECOVERY"
    else:
        raise AssertionError("corrupt committed receipt was replayed")
    assert tree_file_bytes(root / "work-items") == before


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


def test_supersede_current_bug_requires_exact_accepted_successor_binding_without_local_mutation(
    tmp_path: Path,
) -> None:
    operation_id = "supersede-current-bug-binding"
    for case in ("missing", "malformed", "unaccepted", "wrong-operation", "hash-drifted"):
        module = load_module()
        root = tmp_path / case
        slug = f"2026-09-10-{case}-source"
        source = seed_context_bug(root, "source-owner", slug)
        successor = root / "receiving-registry" / "accepted-successor.md"
        successor_bytes = b"id: accepted-successor\nstatus: accepted\n"
        successor.parent.mkdir(parents=True)
        successor.write_bytes(successor_bytes)
        module.refresh_readme(root, allow_marker_bootstrap=True)
        binding = successor_binding_bytes(slug, successor_bytes, operation_id)
        if case == "missing":
            supplied_binding = None
        elif case == "malformed":
            supplied_binding = b"{"
        elif case == "unaccepted":
            supplied_binding = successor_binding_bytes(
                slug, successor_bytes, operation_id, accepted_by=""
            )
        elif case == "wrong-operation":
            supplied_binding = successor_binding_bytes(
                slug, successor_bytes, operation_id + "-other"
            )
        else:
            supplied_binding = binding
            successor.write_bytes(successor_bytes + b"drift\n")
        inventory = successor_link_inventory_bytes(
            slug, source.read_bytes(), binding, operation_id
        )
        before = tree_file_bytes(root / "work-items")
        successor_before = successor.read_bytes()

        try:
            module.supersede_current_bug(
                root,
                slug,
                successor,
                supplied_binding,
                "2026-09-10T08:01:00Z",
                inventory,
                hashlib.sha256(source.read_bytes()).hexdigest(),
                hashlib.sha256(
                    (root / "work-items" / "README.md").read_bytes()
                ).hexdigest(),
                operation_id,
            )
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-BUG-SUCCESSOR-BINDING", case
        else:
            raise AssertionError(f"{case} successor binding was accepted")

        assert tree_file_bytes(root / "work-items") == before, case
        assert source.is_file(), case
        assert successor.read_bytes() == successor_before, case


def test_supersede_current_bug_rechecks_same_length_successor_bytes_before_intent(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "same-length-successor"
    slug = "2026-09-10-same-length-successor"
    operation_id = "supersede-same-length-successor"
    source = seed_context_bug(root, "source-owner", slug)
    source_before = source.read_bytes()
    successor = root / "receiving-registry" / "accepted-successor.md"
    accepted_bytes = b"id: accepted-successor\nstatus: accepted\n"
    updated_bytes = b"id: accepted-successor\nstatus: reviewed\n"
    assert len(accepted_bytes) == len(updated_bytes)
    successor.parent.mkdir(parents=True)
    successor.write_bytes(accepted_bytes)
    module.refresh_readme(root, allow_marker_bootstrap=True)
    readme = root / "work-items" / "README.md"
    binding = successor_binding_bytes(slug, accepted_bytes, operation_id)
    inventory = successor_link_inventory_bytes(
        slug, source_before, binding, operation_id
    )
    original_verify = module._verify_captured_file
    injected = False

    def update_before_final_verify(snapshot, failure_id):
        nonlocal injected
        if not injected and snapshot.path == successor:
            successor.write_bytes(updated_bytes)
            injected = True
        return original_verify(snapshot, failure_id)

    module._verify_captured_file = update_before_final_verify
    try:
        try:
            module.supersede_current_bug(
                root,
                slug,
                successor,
                binding,
                "2026-09-10T08:02:00Z",
                inventory,
                hashlib.sha256(source_before).hexdigest(),
                hashlib.sha256(readme.read_bytes()).hexdigest(),
                operation_id,
            )
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-BUG-SUCCESSOR-BINDING"
        else:
            raise AssertionError("same-length successor drift was accepted")
    finally:
        module._verify_captured_file = original_verify

    assert injected is True
    assert source.read_bytes() == source_before
    assert successor.read_bytes() == updated_bytes
    assert not list((root / "work-items" / "bugs" / "archive").glob("*/*.md"))
    assert not (
        root
        / ".scratch"
        / "work-items-lifecycle-transitions"
        / f"{operation_id}.json"
    ).exists()


def _supersede_current_bug_cli_fixture(
    module,
    root: Path,
    slug: str,
    operation_id: str,
) -> tuple[list[str], Path, Path, Path]:
    source = seed_context_bug(root, "source-owner", slug)
    successor = root / "receiving-registry" / "accepted-successor.md"
    successor_bytes = b"id: accepted-successor\nstatus: accepted\n"
    successor.parent.mkdir(parents=True)
    successor.write_bytes(successor_bytes)
    module.refresh_readme(root, allow_marker_bootstrap=True)
    readme = root / "work-items" / "README.md"
    binding = successor_binding_bytes(slug, successor_bytes, operation_id)
    binding_file = root / "input" / "successor-binding.json"
    inventory_file = root / "input" / "incoming-links.json"
    binding_file.parent.mkdir(parents=True)
    binding_file.write_bytes(binding)
    inventory_file.write_bytes(
        successor_link_inventory_bytes(
            slug, source.read_bytes(), binding, operation_id
        )
    )
    return (
        [
            "supersede-current-bug",
            "--root",
            str(root),
            "--slug",
            slug,
            "--successor-record",
            str(successor),
            "--successor-binding-file",
            str(binding_file),
            "--terminal-instant",
            "2026-09-10T08:05:00Z",
            "--incoming-links-inventory",
            str(inventory_file),
            "--expected-bug-sha256",
            hashlib.sha256(source.read_bytes()).hexdigest(),
            "--expected-readme-sha256",
            hashlib.sha256(readme.read_bytes()).hexdigest(),
            "--operation-id",
            operation_id,
            "--apply",
        ],
        source,
        binding_file,
        successor,
    )


def test_shared_bug_recovery_preserves_supersession_error_text(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-09-10-supersession-diagnostic"
    operation_id = "supersession-diagnostic"
    argv, source, binding_file, successor = _supersede_current_bug_cli_fixture(
        module, root, slug, operation_id,
    )
    with unittest.TestCase().assertRaises(module.LifecycleError):
        module.supersede_current_bug(
            root, slug, successor, binding_file.read_bytes(),
            argv[argv.index("--terminal-instant") + 1],
            (root / "input" / "incoming-links.json").read_bytes(),
            hashlib.sha256(source.read_bytes()).hexdigest(),
            hashlib.sha256((root / "work-items" / "README.md").read_bytes()).hexdigest(),
            operation_id, inject_failure_at="B1",
        )
    source_before_drift = source.read_bytes()
    source.write_bytes(b"foreign mutation\n")

    with unittest.TestCase().assertRaises(module.LifecycleError) as failed_recovery:
        module._recover_all_transitions(root)

    assert failed_recovery.exception.failure_id == "WI-BUG-SUPERSESSION-ROLLBACK-INDETERMINATE"
    assert str(failed_recovery.exception) == "bug supersession rollback identity differs"
    assert source.read_bytes() == b"foreign mutation\n"
    source.write_bytes(source_before_drift)
    module._recover_all_transitions(root)
    assert not list((root / ".scratch" / "work-items-lifecycle-transitions").glob("*.json"))


def test_supersede_current_bug_cli_projects_failure_output_without_caller_content(
    tmp_path: Path,
) -> None:
    cases = (
        (
            "duplicate-token-key",
            "SYNTHETIC_TOKEN_LIKE_sk_FAKE_6f3d9a0c",
            "duplicate",
            "WI-BUG-SUCCESSOR-BINDING: current bug supersession rejected\n",
        ),
        (
            "duplicate-log-key",
            "SYNTHETIC_RAW_LOG_2026-09-10T08_30_00Z_ERROR_5b72c1e4",
            "duplicate",
            "WI-BUG-SUCCESSOR-BINDING: current bug supersession rejected\n",
        ),
        (
            "missing-path",
            "SYNTHETIC_MACHINE_LOCAL_PATH_91e7c4ab",
            "missing",
            "WI-IO: required current bug supersession input could not be read\n",
        ),
        (
            "malformed-control",
            "SYNTHETIC_MALFORMED_CONTROL_2dc848ae",
            "malformed",
            "WI-BUG-SUCCESSOR-BINDING: current bug supersession rejected\n",
        ),
    )
    for case, sentinel, mode, expected_stdout in cases:
        module = load_module()
        root = tmp_path / case
        slug = f"2026-09-10-{case}-failure-output"
        operation_id = f"failure-output-{case}"
        argv, source, binding_file, successor = _supersede_current_bug_cli_fixture(
            module, root, slug, operation_id
        )
        if mode == "duplicate":
            valid = binding_file.read_bytes()
            binding_file.write_bytes(
                (f'{{"{sentinel}":"first","{sentinel}":"second",').encode()
                + valid[1:]
            )
        elif mode == "missing":
            missing = root / "missing-input" / sentinel / "successor-binding.json"
            argv[argv.index(str(binding_file))] = str(missing)
        else:
            binding_file.write_bytes(b"{" + sentinel.encode("ascii"))
        before = tree_file_bytes(root)

        result = run_cli_separate_streams(*argv)

        assert result.returncode == 1, case
        assert result.stdout == expected_stdout, case
        assert result.stderr == "", case
        assert sentinel not in result.stdout, case
        assert sentinel not in result.stderr, case
        assert tree_file_bytes(root) == before, case
        assert source.is_file(), case
        assert successor.is_file(), case
        assert not list((root / "work-items" / "bugs").glob("archive/*/*.md")), case
        assert not list(root.rglob("*.supersession-receipt.json")), case
        assert not (
            root
            / ".scratch"
            / "work-items-lifecycle-transitions"
            / f"{operation_id}.json"
        ).exists(), case


def test_supersede_current_bug_main_projects_unexpected_exception_and_preserves_controls(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "unexpected"
    argv, _source, _binding_file, _successor = _supersede_current_bug_cli_fixture(
        module,
        root,
        "2026-09-10-unexpected-failure-output",
        "failure-output-unexpected",
    )
    marker = "SYNTHETIC_UNEXPECTED_RUNTIME_MARKER_7c91e2"
    output = io.StringIO()
    error = io.StringIO()
    with patch.object(
        module,
        "supersede_current_bug",
        side_effect=RuntimeError(marker),
    ), redirect_stdout(output), redirect_stderr(error):
        assert module.main(argv) == 1
    assert output.getvalue() == (
        "WI-BUG-SUPERSESSION-UNEXPECTED: "
        "current bug supersession failed unexpectedly\n"
    )
    assert error.getvalue() == ""
    assert marker not in output.getvalue()
    assert "Traceback" not in output.getvalue()

    for interruption in (
        KeyboardInterrupt("synthetic keyboard interruption"),
        asyncio.CancelledError("synthetic cancellation"),
    ):
        output = io.StringIO()
        error = io.StringIO()
        with patch.object(
            module,
            "supersede_current_bug",
            side_effect=interruption,
        ), redirect_stdout(output), redirect_stderr(error):
            with unittest.TestCase().assertRaises(type(interruption)) as caught:
                module.main(argv)
        assert caught.exception is interruption
        assert output.getvalue() == ""
        assert error.getvalue() == ""

    detailed = "other command retains its detailed diagnostic"
    output = io.StringIO()
    error = io.StringIO()
    with patch.object(
        module,
        "refresh_readme",
        side_effect=module.LifecycleError("WI-README-STALE", detailed),
    ), redirect_stdout(output), redirect_stderr(error):
        assert module.main(["refresh", "--root", str(root)]) == 1
    assert output.getvalue() == f"WI-README-STALE: {detailed}\n"
    assert error.getvalue() == ""


def test_supersede_current_bug_rejects_unreadable_live_reference_consumers_without_mutation(
    tmp_path: Path,
) -> None:
    for failure_kind in ("unicode", "oserror"):
        for inventory_kind in ("zero", "partial"):
            module = load_module()
            case = f"{failure_kind}-{inventory_kind}"
            root = tmp_path / case
            slug = f"2026-09-10-unreadable-{case}"
            operation_id = f"supersede-unreadable-{case}"
            source = seed_context_bug(root, "source-owner", slug)
            source_before = source.read_bytes()
            active = root / "work-items" / "active"
            write(active / "unreadable-consumer" / "status.md", quick_status())
            unreadable = active / "unreadable-consumer" / "notes.md"
            unreadable.parent.mkdir(parents=True, exist_ok=True)
            unreadable.write_bytes(
                f"Related: bug:{slug}\n".encode("utf-8")
                + (b"\xff" if failure_kind == "unicode" else b"")
            )
            valid = active / "valid-consumer" / "notes.md"
            valid_before = f"Related: bug:{slug}\n".encode("utf-8")
            valid_after = (
                "Related: external-bug-registry#bug:accepted-successor\n"
            ).encode("utf-8")
            if inventory_kind == "partial":
                write(active / "valid-consumer" / "status.md", quick_status())
                valid.parent.mkdir(parents=True, exist_ok=True)
                valid.write_bytes(valid_before)
            successor = root / "receiving-registry" / "accepted-successor.md"
            successor_bytes = b"id: accepted-successor\nstatus: accepted\n"
            successor.parent.mkdir(parents=True)
            successor.write_bytes(successor_bytes)
            module.refresh_readme(root, allow_marker_bootstrap=True)
            readme = root / "work-items" / "README.md"
            binding = successor_binding_bytes(slug, successor_bytes, operation_id)
            links = (
                [
                    {
                        "path": valid.relative_to(root).as_posix(),
                        "beforeSha256": hashlib.sha256(valid_before).hexdigest(),
                        "afterSha256": hashlib.sha256(valid_after).hexdigest(),
                        "afterBytesBase64": base64.b64encode(valid_after).decode("ascii"),
                    }
                ]
                if inventory_kind == "partial"
                else []
            )
            inventory = successor_link_inventory_bytes(
                slug, source_before, binding, operation_id, links
            )
            work_items_before = tree_file_bytes(root / "work-items")
            successor_before = successor.read_bytes()
            original_read_bytes = Path.read_bytes

            def injected_read_bytes(path: Path) -> bytes:
                if failure_kind == "oserror" and path == unreadable:
                    raise OSError("injected unreadable live reference consumer")
                return original_read_bytes(path)

            try:
                with patch.object(Path, "read_bytes", injected_read_bytes):
                    module.supersede_current_bug(
                        root,
                        slug,
                        successor,
                        binding,
                        "2026-09-10T08:01:30Z",
                        inventory,
                        hashlib.sha256(source_before).hexdigest(),
                        hashlib.sha256(readme.read_bytes()).hexdigest(),
                        operation_id,
                    )
            except module.LifecycleError as exc:
                assert exc.failure_id == "WI-CATEGORY-MIGRATION-INVENTORY", case
            else:
                raise AssertionError(f"{case} unreadable live consumer was omitted")

            assert tree_file_bytes(root / "work-items") == work_items_before, case
            assert successor.read_bytes() == successor_before, case
            assert not (
                root
                / ".scratch"
                / "work-items-lifecycle-transitions"
                / f"{operation_id}.json"
            ).exists(), case


def test_supersede_current_bug_excludes_unreadable_archived_consumers_from_strict_inventory(
    tmp_path: Path,
) -> None:
    for failure_kind in ("unicode", "oserror"):
        module = load_module()
        root = tmp_path / failure_kind
        slug = f"2026-09-10-archived-control-{failure_kind}"
        operation_id = f"supersede-archived-control-{failure_kind}"
        source = seed_context_bug(root, "source-owner", slug)
        source_before = source.read_bytes()
        historical = (
            root
            / "work-items"
            / "archive"
            / "2026-08"
            / "unrelated-history"
        )
        write(historical / "status.md", marked_status())
        write(
            historical / "closure.md",
            marked_closure("2026-08-01T00:00:00Z"),
        )
        archived_consumer = historical / "notes.bin"
        archived_consumer.write_bytes(
            f"Historical: bug:{slug}\n".encode("utf-8")
            + (b"\xff" if failure_kind == "unicode" else b"")
        )
        archived_consumer_before = archived_consumer.read_bytes()
        successor = root / "receiving-registry" / "accepted-successor.md"
        successor_bytes = b"id: accepted-successor\nstatus: accepted\n"
        successor.parent.mkdir(parents=True)
        successor.write_bytes(successor_bytes)
        module.refresh_readme(root, allow_marker_bootstrap=True)
        readme = root / "work-items" / "README.md"
        binding = successor_binding_bytes(slug, successor_bytes, operation_id)
        inventory = successor_link_inventory_bytes(
            slug, source_before, binding, operation_id
        )
        original_read_bytes = Path.read_bytes

        def injected_read_bytes(path: Path) -> bytes:
            if failure_kind == "oserror" and path == archived_consumer:
                raise OSError("injected unreadable archived consumer")
            return original_read_bytes(path)

        with patch.object(Path, "read_bytes", injected_read_bytes):
            settled = module.supersede_current_bug(
                root,
                slug,
                successor,
                binding,
                "2026-09-10T08:01:45Z",
                inventory,
                hashlib.sha256(source_before).hexdigest(),
                hashlib.sha256(readme.read_bytes()).hexdigest(),
                operation_id,
            )

        archive = (
            root
            / "work-items"
            / "bugs"
            / "archive"
            / "2026-09"
            / f"{slug}.md"
        )
        assert settled["status"] == "settled", failure_kind
        assert not source.exists() and archive.is_file(), failure_kind
        assert archived_consumer.read_bytes() == archived_consumer_before, failure_kind
        assert successor.read_bytes() == successor_bytes, failure_kind
        assert not (
            root
            / ".scratch"
            / "work-items-lifecycle-transitions"
            / f"{operation_id}.json"
        ).exists(), failure_kind


def test_supersede_current_bug_archives_links_and_readme_in_one_recoverable_intent(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-09-10-source-bug"
    operation_id = "supersede-current-bug-success"
    terminal_instant = "2026-09-10T08:02:00Z"
    source = seed_context_bug(root, "source-owner", slug)
    source_before = source.read_bytes()
    consumer = root / "work-items" / "active" / "consumer" / "status.md"
    old_href = f"../../bugs/{slug}.md"
    successor_reference = "external-bug-registry#bug:accepted-successor"
    consumer_before = (
        quick_status("Track the source bug.")
        + f"\nRelated: bug:{slug}\n[physical]({old_href})\n"
    ).encode("utf-8")
    consumer_after = consumer_before.replace(
        f"bug:{slug}".encode("utf-8"), successor_reference.encode("utf-8")
    ).replace(old_href.encode("utf-8"), successor_reference.encode("utf-8"))
    consumer.parent.mkdir(parents=True)
    consumer.write_bytes(consumer_before)
    successor = root / "receiving-registry" / "accepted-successor.md"
    successor_bytes = b"id: accepted-successor\nstatus: accepted\n"
    successor.parent.mkdir(parents=True)
    successor.write_bytes(successor_bytes)
    module.refresh_readme(root, allow_marker_bootstrap=True)
    readme = root / "work-items" / "README.md"
    readme_before_sha256 = hashlib.sha256(readme.read_bytes()).hexdigest()
    binding = successor_binding_bytes(slug, successor_bytes, operation_id)
    inventory = successor_link_inventory_bytes(
        slug,
        source_before,
        binding,
        operation_id,
        [
            {
                "path": consumer.relative_to(root).as_posix(),
                "beforeSha256": hashlib.sha256(consumer_before).hexdigest(),
                "afterSha256": hashlib.sha256(consumer_after).hexdigest(),
                "afterBytesBase64": base64.b64encode(consumer_after).decode("ascii"),
            }
        ],
    )
    binding_file = root / "successor-binding.json"
    inventory_file = root / "incoming-links.json"
    binding_file.write_bytes(binding)
    inventory_file.write_bytes(inventory)
    successor_before = successor.read_bytes()

    result = run_cli(
        "supersede-current-bug",
        "--root",
        str(root),
        "--slug",
        slug,
        "--successor-record",
        str(successor),
        "--successor-binding-file",
        str(binding_file),
        "--terminal-instant",
        terminal_instant,
        "--incoming-links-inventory",
        str(inventory_file),
        "--expected-bug-sha256",
        hashlib.sha256(source_before).hexdigest(),
        "--expected-readme-sha256",
        readme_before_sha256,
        "--operation-id",
        operation_id,
        "--apply",
    )
    assert result.returncode == 0, result.stdout
    assert "WI-BUG-SUPERSESSION-COMMITTED" in result.stdout

    archive = (
        root
        / "work-items"
        / "bugs"
        / "archive"
        / "2026-09"
        / f"{slug}.md"
    )
    receipt_path = archive.with_name(f"{slug}.supersession-receipt.json")
    assert not source.exists()
    assert archive.is_file()
    assert consumer.read_bytes() == consumer_after
    assert successor.read_bytes() == successor_before
    fields = module._parse_fields(archive.read_text(encoding="utf-8"))
    assert fields["status"] == "superseded"
    assert fields["terminal-at"] == terminal_instant
    assert fields["resolution"] == f"Superseded by {successor_reference}."
    assert fields["evidence"] == "Receiving owner accepted the current successor."
    assert fields["successor"] == successor_reference
    assert str(successor) not in archive.read_text(encoding="utf-8")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert set(receipt) == {
        "schemaVersion",
        "owner",
        "kind",
        "status",
        "operationId",
        "terminalInstant",
        "sourceReference",
        "sourcePath",
        "archivePath",
        "archivedBugSha256",
        "successorBindingSha256",
        "successorRegistryReference",
        "successorRecordReference",
        "successorRecordSha256",
        "acceptedBy",
        "acceptedAt",
        "acceptanceEvidence",
        "incomingLinksInventorySha256",
        "links",
        "readmeSha256",
        "requestExpectedBugSha256",
        "requestExpectedReadmeSha256",
    }
    assert receipt["owner"] == "mutate-work-item:current-bug-supersession-v1"
    assert receipt["kind"] == "current-bug-supersession-v1"
    assert receipt["status"] == "settled"
    assert receipt["sourceReference"] == f"bug:{slug}"
    assert receipt["successorRegistryReference"] == "external-bug-registry"
    assert receipt["successorRecordReference"] == "bug:accepted-successor"
    assert receipt["links"] == [
        {
            "path": consumer.relative_to(root).as_posix(),
            "beforeSha256": hashlib.sha256(consumer_before).hexdigest(),
            "afterSha256": hashlib.sha256(consumer_after).hexdigest(),
        }
    ]
    assert receipt["readmeSha256"] == hashlib.sha256(readme.read_bytes()).hexdigest()
    assert not (
        root / ".scratch" / "work-items-lifecycle-transitions" / f"{operation_id}.json"
    ).exists()


def test_supersede_current_bug_replay_is_exact_and_mismatch_fails(
    tmp_path: Path,
) -> None:
    def prepare(root: Path, suffix: str) -> tuple[object, dict, bytes, bytes]:
        module = load_module()
        slug = f"2026-09-10-recovery-{suffix}"
        operation_id = f"supersede-recovery-{suffix}"
        terminal_instant = "2026-09-10T08:03:00Z"
        source = seed_context_bug(root, "source-owner", slug)
        source_before = source.read_bytes()
        consumer = root / "work-items" / "active" / f"consumer-{suffix}" / "status.md"
        successor_reference = "external-bug-registry#bug:accepted-successor"
        consumer_before = (
            quick_status("Track one source bug.") + f"\nRelated: bug:{slug}\n"
        ).encode("utf-8")
        consumer_after = consumer_before.replace(
            f"bug:{slug}".encode(), successor_reference.encode()
        )
        consumer.parent.mkdir(parents=True)
        consumer.write_bytes(consumer_before)
        successor = root / "receiving-registry" / "accepted-successor.md"
        successor_bytes = b"id: accepted-successor\nstatus: accepted\n"
        successor.parent.mkdir(parents=True)
        successor.write_bytes(successor_bytes)
        module.refresh_readme(root, allow_marker_bootstrap=True)
        readme = root / "work-items" / "README.md"
        binding = successor_binding_bytes(slug, successor_bytes, operation_id)
        inventory = successor_link_inventory_bytes(
            slug,
            source_before,
            binding,
            operation_id,
            [
                {
                    "path": consumer.relative_to(root).as_posix(),
                    "beforeSha256": hashlib.sha256(consumer_before).hexdigest(),
                    "afterSha256": hashlib.sha256(consumer_after).hexdigest(),
                    "afterBytesBase64": base64.b64encode(consumer_after).decode("ascii"),
                }
            ],
        )
        request = {
            "root": root,
            "slug": slug,
            "successor_record": successor,
            "successor_binding_data": binding,
            "terminal_instant": terminal_instant,
            "incoming_links_inventory_data": inventory,
            "expected_bug_sha256": hashlib.sha256(source_before).hexdigest(),
            "expected_readme_sha256": hashlib.sha256(readme.read_bytes()).hexdigest(),
            "operation_id": operation_id,
        }
        return module, request, consumer_after, successor_bytes

    replay_root = tmp_path / "replay"
    module, request, consumer_after, successor_bytes = prepare(replay_root, "replay")
    settled = module.supersede_current_bug(**request)
    assert settled["status"] == "settled"
    assert request["successor_record"].read_bytes() == successor_bytes
    before_replay = tree_file_bytes(replay_root / "work-items")
    missing_runtime_path = replay_root / "receiving-registry" / "not-present.md"
    replay_request = dict(request)
    replay_request["successor_record"] = missing_runtime_path
    assert module.supersede_current_bug(**replay_request) == settled
    assert tree_file_bytes(replay_root / "work-items") == before_replay

    mismatch_requests = {
        "binding": {
            "successor_binding_data": request["successor_binding_data"] + b" "
        },
        "inventory": {
            "incoming_links_inventory_data": request["incoming_links_inventory_data"]
            + b" "
        },
        "bug-hash": {"expected_bug_sha256": "0" * 64},
        "readme-hash": {"expected_readme_sha256": "1" * 64},
        "terminal": {"terminal_instant": "2026-09-10T08:04:00Z"},
        "operation": {"operation_id": request["operation_id"] + "-other"},
    }
    for case, delta in mismatch_requests.items():
        mismatched = dict(replay_request)
        mismatched.update(delta)
        try:
            module.supersede_current_bug(**mismatched)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-BUG-SUPERSESSION-SETTLEMENT-MISMATCH", case
        else:
            raise AssertionError(f"{case} replay mismatch was accepted")
        assert tree_file_bytes(replay_root / "work-items") == before_replay, case

    drift_root = tmp_path / "archive-byte-drift"
    module, request, _consumer_after, _successor_bytes = prepare(
        drift_root, "archive-byte-drift"
    )
    module.supersede_current_bug(**request)
    archived_bug = (
        drift_root
        / "work-items"
        / "bugs"
        / "archive"
        / "2026-09"
        / f"{request['slug']}.md"
    )
    archived_bug.write_bytes(b"\xff")
    drift_replay = dict(request)
    drift_replay["successor_record"] = drift_root / "missing-runtime-record.md"
    try:
        module.supersede_current_bug(**drift_replay)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-BUG-SUPERSESSION-SETTLEMENT-MISMATCH"
    else:
        raise AssertionError("non-UTF-8 archived bug drift passed replay")

    for boundary_index in range(8):
        boundary = f"B{boundary_index}"
        root = tmp_path / boundary.casefold()
        module, request, expected_consumer, successor_bytes = prepare(
            root, boundary.casefold()
        )
        try:
            module.supersede_current_bug(
                **request, inject_failure_at=boundary
            )
        except module.LifecycleError as exc:
            expected_failure = (
                "WI-BUG-SUPERSESSION-ROLLBACK-INDETERMINATE"
                if boundary_index <= 2
                else "WI-BUG-SUPERSESSION-ROLLFORWARD-INDETERMINATE"
            )
            assert exc.failure_id == expected_failure, boundary
        else:
            raise AssertionError(f"{boundary} did not interrupt settlement")

        recovered = module.supersede_current_bug(**request)
        assert recovered["status"] == "settled", boundary
        source = root / "work-items" / "bugs" / f"{request['slug']}.md"
        archive = (
            root
            / "work-items"
            / "bugs"
            / "archive"
            / "2026-09"
            / f"{request['slug']}.md"
        )
        consumer = (
            root
            / "work-items"
            / "active"
            / f"consumer-{boundary.casefold()}"
            / "status.md"
        )
        assert not source.exists() and archive.is_file(), boundary
        assert consumer.read_bytes() == expected_consumer, boundary
        assert request["successor_record"].read_bytes() == successor_bytes, boundary
        assert not (
            root
            / ".scratch"
            / "work-items-lifecycle-transitions"
            / f"{request['operation_id']}.json"
        ).exists(), boundary


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
            def validate_obligation_transfer_ownership(self, _root):
                return []

            def validate_work_item(self, _item, *, strict_revise=True):
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
        assert str(exc) == (
            "start committed canonical state; README refresh required; "
            "do not retry start; run refresh, then verify the target."
        )
    else:
        raise AssertionError("injected README failure did not abort the derived-view refresh")

    target = root / "work-items" / "active" / slug
    assert target.is_dir()
    assert not (root / "work-items" / "backlog" / f"{slug}.md").exists()
    result = run_state_validator(target)
    assert result.returncode == 0, result.stdout
    try:
        module.check_readme(root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-README-STALE"
    else:
        raise AssertionError("post-commit start unexpectedly refreshed README")
    module.refresh_readme(root)
    module.audit(root)
    assert module.resolve_category(root, f"work-item:{slug}") == target.resolve()


def test_update_and_reopen_readme_failures_share_actionable_postcommit_diagnostic(
    tmp_path: Path,
) -> None:
    module = load_module()

    update_root = tmp_path / "update"
    update_slug = "postcommit-update"
    seed_active(module, update_root, update_slug)
    updated_status = quick_status("Updated canonical task state.").encode("utf-8")
    try:
        module.update_status(
            update_root,
            update_slug,
            updated_status,
            inject_readme_failure=True,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-README-STALE"
        assert str(exc) == (
            "update committed canonical state; README refresh required; "
            "do not retry update; run refresh, then verify the target."
        )
    else:
        raise AssertionError("injected update README failure returned success")
    updated = update_root / "work-items" / "active" / update_slug / "status.md"
    assert updated.read_bytes() == updated_status
    module.refresh_readme(update_root)
    module.audit(update_root)

    reopen_root = tmp_path / "reopen"
    archived_slug = "postcommit-reopen-source"
    successor_slug = "postcommit-reopen-successor"
    seed_active(module, reopen_root, archived_slug)
    instant = "2026-07-31T13:00:00Z"
    write_empty_bug_dispositions(reopen_root, archived_slug, instant)
    archived = module.close_item(
        reopen_root,
        archived_slug,
        closure(instant).encode("utf-8"),
        instant,
    )
    successor_status = staged_status(archived_slug).encode("utf-8")
    try:
        module.reopen_item(
            reopen_root,
            archived_slug,
            successor_slug,
            successor_status,
            inject_readme_failure=True,
        )
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-README-STALE"
        assert str(exc) == (
            "reopen committed canonical state; README refresh required; "
            "do not retry reopen; run refresh, then verify the target."
        )
    else:
        raise AssertionError("injected reopen README failure returned success")
    successor = reopen_root / "work-items" / "active" / successor_slug
    assert successor.joinpath("status.md").read_bytes() == successor_status
    assert archived.is_dir()
    module.refresh_readme(reopen_root)
    module.audit(reopen_root)
    assert module.resolve_category(
        reopen_root, f"work-item:{archived_slug}"
    ) == archived.resolve()


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


def test_explicit_static_guide_reset_adopts_retained_legacy_board(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    status = root / "work-items" / "active" / "adopt-legacy" / "status.md"
    write(status, quick_status("Current legacy adoption task."))
    status_before = status.read_bytes()
    readme = root / "work-items" / "README.md"
    legacy_bytes = (
        b"# Work items\r\n\r\n"
        b"Snapshot commit: `964ee371`\r\n\r\n"
        b"## Active work\r\n\r\n"
        b"- Old lifecycle counts and clean worktree claim.\r\n"
    )
    readme.write_bytes(legacy_bytes)
    retained = status.parent / "data" / "legacy-readme.md"
    retained.parent.mkdir()
    retained.write_bytes(readme.read_bytes())
    legacy_hash = hashlib.sha256(legacy_bytes).hexdigest()
    assert retained.read_bytes() == legacy_bytes
    assert hashlib.sha256(retained.read_bytes()).hexdigest() == legacy_hash

    ordinary = run_cli("refresh", "--root", str(root))
    assert ordinary.returncode == 1
    assert "WI-README-MARKERS" in ordinary.stdout
    assert readme.read_bytes() == legacy_bytes
    assert retained.read_bytes() == legacy_bytes
    assert status.read_bytes() == status_before

    repaired = run_cli(
        "refresh",
        "--root",
        str(root),
        "--reset-static-guide",
        "--expected-readme-sha256",
        legacy_hash,
    )

    assert repaired.returncode == 0, repaired.stdout
    repaired_bytes = readme.read_bytes()
    rendered = repaired_bytes.decode("utf-8")
    begin = "<!-- BEGIN GENERATED WORK-ITEMS STATUS -->"
    end = "<!-- END GENERATED WORK-ITEMS STATUS -->"
    assert rendered.startswith(
        "# Work items\n\nRead this page for current delivery status."
    )
    assert rendered.count(begin) == 1
    assert rendered.count(end) == 1
    assert rendered.index(begin) < rendered.index(end)
    assert "Read-model: work-items-readme-v1" in rendered
    assert "Current legacy adoption task." in rendered
    assert "Snapshot commit" not in rendered
    assert "## Active work" not in rendered
    assert "Old lifecycle counts" not in rendered
    repaired_hash = hashlib.sha256(repaired_bytes).hexdigest()
    assert f"README-SHA256: {repaired_hash}" in repaired.stdout
    assert status.read_bytes() == status_before
    assert retained.read_bytes() == legacy_bytes
    assert hashlib.sha256(retained.read_bytes()).hexdigest() == legacy_hash
    assert not (root / "work-items" / "archive").exists()

    replay = run_cli(
        "refresh",
        "--root",
        str(root),
        "--reset-static-guide",
        "--expected-readme-sha256",
        legacy_hash,
    )
    assert replay.returncode == 0, replay.stdout
    assert readme.read_bytes() == repaired_bytes
    assert retained.read_bytes() == legacy_bytes
    assert status.read_bytes() == status_before

    readme.write_bytes(retained.read_bytes())
    assert readme.read_bytes() == legacy_bytes
    assert hashlib.sha256(readme.read_bytes()).hexdigest() == legacy_hash
    assert status.read_bytes() == status_before


def test_explicit_legacy_static_guide_reset_refuses_wrong_or_malformed_target(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    status = root / "work-items" / "active" / "target-guard" / "status.md"
    write(status, quick_status("Preserve canonical task data."))
    status_before = status.read_bytes()
    readme = root / "work-items" / "README.md"
    legacy_bytes = b"# Reviewed legacy board without ownership markers\n"
    readme.write_bytes(legacy_bytes)

    for expected_hash in ("0" * 64, "not-a-digest"):
        refused = run_cli(
            "refresh",
            "--root",
            str(root),
            "--reset-static-guide",
            "--expected-readme-sha256",
            expected_hash,
        )
        assert refused.returncode == 1
        assert "WI-README-REPAIR-TARGET-MISMATCH" in refused.stdout
        assert readme.read_bytes() == legacy_bytes
        assert status.read_bytes() == status_before


def test_explicit_static_guide_reset_refuses_corrupt_marker_pairs(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    status = root / "work-items" / "active" / "marker-guard" / "status.md"
    write(status, quick_status("Preserve marker ownership."))
    status_before = status.read_bytes()
    readme = root / "work-items" / "README.md"
    begin = b"<!-- BEGIN GENERATED WORK-ITEMS STATUS -->\n"
    end = b"<!-- END GENERATED WORK-ITEMS STATUS -->\n"

    for invalid in (begin, begin + begin + end, end + begin):
        readme.write_bytes(invalid)
        refused = run_cli(
            "refresh",
            "--root",
            str(root),
            "--reset-static-guide",
            "--expected-readme-sha256",
            hashlib.sha256(invalid).hexdigest(),
        )
        assert refused.returncode == 1
        assert "WI-README-MARKERS" in refused.stdout
        assert readme.read_bytes() == invalid
        assert status.read_bytes() == status_before


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


def test_expanded_root_contract_uses_generic_auxiliary_roots_across_lifecycle(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    declared = ("alpha-receipts", "zeta-receipts")
    contract = expanded_root_contract(declared)
    write(root / "work-items" / "root-contract.json", json.dumps(contract) + "\n")
    for name in declared:
        write(root / "work-items" / name / "receipt.json", "{}\n")

    slug = "expanded-topology"
    seed_active(module, root, slug)
    module.audit_categories(root)
    instant = "2026-09-01T00:00:00Z"
    write_empty_bug_dispositions(root, slug, instant)
    archived = module.close_item(root, slug, closure(instant).encode(), instant)
    successor = module.reopen_item(
        root, slug, "expanded-topology-successor", staged_status(slug).encode()
    )
    module.audit(root)
    before_refresh = (root / "work-items" / "README.md").read_bytes()
    module.refresh_readme(root)

    assert archived == root / "work-items" / "archive" / "2026-09" / slug
    assert successor == root / "work-items" / "active" / "expanded-topology-successor"
    assert (root / "work-items" / "README.md").read_bytes() == before_refresh
    assert all((root / "work-items" / name / "receipt.json").is_file() for name in declared)


def test_expanded_root_contract_accepts_pinned_reader_shape(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    contract = expanded_root_contract(("repair-receipts", "status-repair-receipts"))
    contract["rootFiles"] = [
        "README.md", "active-pipeline.md", "index.md", "root-contract.json",
        "semantic-readiness.json",
    ]
    contract["activeItemSubdirectories"] = ["constraints"]
    write(root / "work-items" / "root-contract.json", json.dumps(contract) + "\n")
    for name in ("repair-receipts", "status-repair-receipts"):
        write(root / "work-items" / name / "receipt.json", "{}\n")

    topology = module._resolve_project_topology(root)
    module.audit_categories(root)

    assert topology.auxiliary_roots == frozenset(
        {"repair-receipts", "status-repair-receipts"}
    )


def test_expanded_root_contract_rejects_invalid_envelopes_before_mutation(
    tmp_path: Path,
) -> None:
    module = load_module()
    base = expanded_root_contract(("alpha-receipts", "zeta-receipts"))
    cases: dict[str, dict[str, object]] = {}

    def changed(name: str, field: str, value: object) -> None:
        contract = copy.deepcopy(base)
        contract[field] = value
        cases[name] = contract

    changed("extra-key", "unexpected", [])
    missing = copy.deepcopy(base)
    del missing["rootFiles"]
    cases["missing-key"] = missing
    changed("boolean-version", "version", True)
    changed("wrong-auxiliary-shape", "auxiliaryRoots", {"alpha-receipts": {"kind": "flat-json"}})
    changed("unknown-nested-key", "auxiliaryRoots", [{"path": "alpha-receipts", "kind": "flat-json", "other": 1}])
    changed("unhashable-kind", "auxiliaryRoots", [{"path": "alpha-receipts", "kind": []}])
    changed("unsorted-auxiliary", "auxiliaryRoots", list(reversed(base["auxiliaryRoots"])))
    changed("duplicate-auxiliary", "auxiliaryRoots", [base["auxiliaryRoots"][0]] * 2)
    changed("wrong-auxiliary-kind", "auxiliaryRoots", [{"path": "alpha-receipts", "kind": "flat-markdown"}])
    changed("duplicate-across-sections", "auxiliaryRoots", [{"path": "backlog", "kind": "flat-json"}])
    changed("renamed-active", "lifecycleRoots", [{"path": "ongoing", "kind": "active-items"}, {"path": "archive", "kind": "archived-items"}])
    changed("missing-archive", "lifecycleRoots", [{"path": "active", "kind": "active-items"}])
    changed("unsupported-registry", "registries", [{"path": "other", "kind": "flat-markdown"}])
    changed("direct-slash", "rootFiles", ["README.md", "nested/root-contract.json", "root-contract.json"])
    changed("dot-segment", "activeItemSubdirectories", ["."])
    changed("empty-segment", "historicalItemDirectoryExceptions", ["archive//item/notes"])
    changed("traversal", "historicalItemDirectoryExceptions", ["archive/2026-01/../notes"])
    changed("backslash", "archiveRootFiles", ["back\\slash"])
    changed("drive-colon", "archiveRootFiles", ["C:drive"])
    changed("rooted", "archiveRootFiles", ["/rooted"])
    changed("shallow-exception", "historicalItemDirectoryExceptions", ["archive/2026-01/item"])
    changed("root-file-collision", "rootFiles", ["ALPHA-receipts", "README.md", "root-contract.json"])

    for name, contract in cases.items():
        root = tmp_path / name
        write(root / "work-items" / "root-contract.json", json.dumps(contract) + "\n")
        try:
            module._resolve_project_topology(root)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-ROOT-CONTRACT-INVALID", name
        else:
            raise AssertionError(f"invalid expanded contract passed: {name}")
        assert not (root / "work-items" / "README.md").exists(), name
        assert not (root / "work-items" / "active").exists(), name


def test_expanded_root_contract_reuses_auxiliary_file_and_link_guards(
    tmp_path: Path,
) -> None:
    module = load_module()
    for shape in ("file", "link"):
        root = tmp_path / shape
        contract = expanded_root_contract(("receipts",))
        write(root / "work-items" / "root-contract.json", json.dumps(contract) + "\n")
        auxiliary = root / "work-items" / "receipts"
        if shape == "file":
            write(auxiliary, "not a directory\n")
        else:
            target = tmp_path / "link-target"
            target.mkdir(exist_ok=True)
            try:
                os.symlink(target, auxiliary, target_is_directory=True)
            except OSError as exc:
                if os.name == "nt":
                    import pytest

                    pytest.skip(f"symlink creation unavailable: {exc}")
                raise
        try:
            module._resolve_project_topology(root)
        except module.LifecycleError as exc:
            assert exc.failure_id == "WI-CATEGORY-ROOT-CONTRACT-INVALID", shape
        else:
            raise AssertionError(f"expanded contract admitted auxiliary {shape}")


def test_expanded_root_contract_rejects_nested_duplicate_json_key(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    contract = json.dumps(expanded_root_contract(("receipts",)))
    contract = contract.replace(
        '"path": "receipts", "kind": "flat-json"',
        '"path": "receipts", "kind": "flat-json", "kind": "flat-json"',
    )
    write(root / "work-items" / "root-contract.json", contract + "\n")

    try:
        module._resolve_project_topology(root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-CATEGORY-ROOT-CONTRACT-INVALID"
    else:
        raise AssertionError("expanded contract admitted nested duplicate JSON key")


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


def test_migrate_legacy_v0_preserves_frozen_bytes_with_external_archive_evidence(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-08-01-superseded-v0"
    source = root / "work-items" / "decisions" / f"{slug}.md"
    source_bytes = _legacy_v0_decision_record(
        status="superseded", identity_line=f"id: {slug}"
    ).encode("utf-8")
    source.parent.mkdir(parents=True)
    source.write_bytes(source_bytes)
    digest = hashlib.sha256(source_bytes).hexdigest().upper()
    manifest = _write_decision_v0_manifest(
        root, [{"path": source.name, "sha256": digest, "state": "admitted"}]
    )
    policy = root / "work-items" / "decisions" / (
        "2026-08-18-current-decision-schema-versioned-read-compatibility.md"
    )
    policy_before = policy.read_bytes()
    baseline_before = json.loads(manifest.read_text(encoding="utf-8"))["baselineSha256"]
    archived_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inventory = root / "incoming.json"
    write(inventory, json.dumps({
        "reference": f"decision:{slug}",
        "expectedSourceSha256": digest,
        "archivedAt": archived_at,
        "rationale": "Accepted successor supersedes this historical decision.",
        "evidence": "Synthetic successor relation and review receipt.",
        "incomingLinks": [],
    }))

    archived = module.migrate_legacy(
        root, f"decision:{slug}", incoming_links_inventory=inventory
    )

    assert archived == root / "work-items" / "decisions" / "archive" / archived_at[:7] / source.name
    assert archived.read_bytes() == source_bytes
    assert not source.exists()
    assert policy.read_bytes() == policy_before
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["schemaVersion"] == 2
    assert payload["baselineSha256"] == baseline_before
    assert payload["entries"] == [{
        "path": source.name, "sha256": digest, "state": "retired",
        "archiveEvidence": {
            "archivePath": f"decisions/archive/{archived_at[:7]}/{source.name}",
            "archivedAt": archived_at,
            "rationale": "Accepted successor supersedes this historical decision.",
            "evidence": "Synthetic successor relation and review receipt.",
        },
    }]
    module.audit_categories(root)


def test_reopen_evidenced_archived_v0_uses_manifest_without_editing_archive(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-08-01-old-v0"
    source = root / "work-items" / "decisions" / f"{slug}.md"
    write(source, _legacy_v0_decision_record(status="superseded", identity_line=f"id: {slug}"))
    frozen = source.read_bytes()
    digest = hashlib.sha256(frozen).hexdigest().upper()
    _write_decision_v0_manifest(root, [{"path": source.name, "sha256": digest, "state": "admitted"}])
    instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inventory = root / "incoming.json"
    write(inventory, json.dumps({
        "reference": f"decision:{slug}", "expectedSourceSha256": digest,
        "archivedAt": instant, "rationale": "Superseded by successor.",
        "evidence": "Synthetic accepted review.", "incomingLinks": [],
    }))
    archived = module.migrate_legacy(root, f"decision:{slug}", incoming_links_inventory=inventory)
    assert module.migrate_legacy(root, f"decision:{slug}", incoming_links_inventory=inventory) == archived
    successor_slug = "2026-09-01-successor"
    successor_data = _current_decision_record(
        successor_slug, status="accepted", body=f"Reopens: {slug}\n"
    ).encode("utf-8")

    successor = module.reopen_category_record(
        root, f"decision:{slug}", successor_slug, successor_data
    )

    assert successor.read_bytes() == successor_data
    assert archived.read_bytes() == frozen


def test_migrate_legacy_v0_repairs_mutable_physical_link(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-08-01-linked-v0"
    source = root / "work-items" / "decisions" / f"{slug}.md"
    write(source, _legacy_v0_decision_record(status="superseded", identity_line=f"id: {slug}"))
    frozen = source.read_bytes()
    digest = hashlib.sha256(frozen).hexdigest().upper()
    _write_decision_v0_manifest(root, [{"path": source.name, "sha256": digest, "state": "admitted"}])
    consumer = root / "work-items" / "bugs" / "consumer.md"
    original_link = f"../decisions/{source.name}"
    write(consumer, f"[historical decision]({original_link})\n")
    instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inventory = root / "incoming.json"
    write(inventory, json.dumps({
        "reference": f"decision:{slug}", "expectedSourceSha256": digest,
        "archivedAt": instant, "rationale": "Superseded.",
        "evidence": "Synthetic review.",
        "incomingLinks": [{
            "consumer": "bugs/consumer.md", "kind": "physical", "value": original_link,
        }],
    }))

    archived = module.migrate_legacy(root, f"decision:{slug}", incoming_links_inventory=inventory)

    assert archived.read_bytes() == frozen
    assert consumer.read_text(encoding="utf-8") == (
        f"[historical decision](../decisions/archive/{instant[:7]}/{source.name})\n"
    )


def test_migrate_legacy_v0_rolls_back_after_readme_failure(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-08-01-rollback-v0"
    source = root / "work-items" / "decisions" / f"{slug}.md"
    write(source, _legacy_v0_decision_record(status="superseded", identity_line=f"id: {slug}"))
    source_before = source.read_bytes()
    digest = hashlib.sha256(source_before).hexdigest().upper()
    manifest = _write_decision_v0_manifest(
        root, [{"path": source.name, "sha256": digest, "state": "admitted"}]
    )
    consumer = root / "work-items" / "bugs" / "consumer.md"
    original_link = f"../decisions/{source.name}"
    write(consumer, f"[historical decision]({original_link})\n")
    module.refresh_readme(root, allow_marker_bootstrap=True)
    before = (manifest.read_bytes(), consumer.read_bytes(), (root / "work-items" / "README.md").read_bytes())
    instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inventory = root / "incoming.json"
    write(inventory, json.dumps({
        "reference": f"decision:{slug}", "expectedSourceSha256": digest,
        "archivedAt": instant, "rationale": "Superseded.",
        "evidence": "Synthetic review.",
        "incomingLinks": [{
            "consumer": "bugs/consumer.md", "kind": "physical", "value": original_link,
        }],
    }))
    with patch.object(module, "refresh_readme", side_effect=module.LifecycleError("WI-README-STALE", "injected")):
        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module.migrate_legacy(root, f"decision:{slug}", incoming_links_inventory=inventory)

    assert caught.exception.failure_id == "WI-README-STALE"
    assert source.read_bytes() == source_before
    assert not (root / "work-items" / "decisions" / "archive" / instant[:7] / source.name).exists()
    assert (manifest.read_bytes(), consumer.read_bytes(), (root / "work-items" / "README.md").read_bytes()) == before


def test_migrate_legacy_v0_rejects_missing_evidence_drift_and_v1_retirement(
    tmp_path: Path,
) -> None:
    module = load_module()
    slug = "2026-08-01-refused-v0"
    instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cases = (
        ("missing-manifest", "WI-DECISION-V0-MANIFEST-MISSING"),
        ("source-drift", "WI-DECISION-V0-HASH-MISMATCH"),
        ("missing-evidence", "WI-DECISION-V0-ARCHIVE-EVIDENCE"),
        ("wrong-month", "WI-DECISION-V0-ARCHIVE-EVIDENCE"),
        ("old-retirement", "WI-DECISION-V0-MANIFEST-INVALID"),
    )
    for name, failure_id in cases:
        root = tmp_path / name
        source = root / "work-items" / "decisions" / f"{slug}.md"
        write(source, _legacy_v0_decision_record(status="superseded", identity_line=f"id: {slug}"))
        frozen = source.read_bytes()
        digest = hashlib.sha256(frozen).hexdigest().upper()
        entries = [{"path": source.name, "sha256": digest, "state": "admitted"}]
        if name == "old-retirement":
            entries.insert(0, {"path": "2026-07-01-retired.md", "sha256": "A" * 64, "state": "retired"})
        manifest = None if name == "missing-manifest" else _write_decision_v0_manifest(root, entries)
        if name == "source-drift":
            source.write_bytes(frozen + b"drift")
        before_source = source.read_bytes()
        before_manifest = manifest.read_bytes() if manifest else None
        inventory = root / "incoming.json"
        write(inventory, json.dumps({
            "reference": f"decision:{slug}", "expectedSourceSha256": digest,
            "archivedAt": "2026-13-01T00:00:00Z" if name == "wrong-month" else instant,
            "rationale": "Superseded.",
            "evidence": "" if name == "missing-evidence" else "Synthetic review.",
            "incomingLinks": [],
        }))
        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module.migrate_legacy(root, f"decision:{slug}", incoming_links_inventory=inventory)
        assert caught.exception.failure_id == failure_id, name
        assert source.read_bytes() == before_source
        assert (manifest.read_bytes() if manifest else None) == before_manifest
        assert not (root / "work-items" / "decisions" / "archive").exists()


def test_migrate_legacy_v0_rejects_archived_physical_consumer_without_move(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-08-01-immutable-link-v0"
    source = root / "work-items" / "decisions" / f"{slug}.md"
    write(source, _legacy_v0_decision_record(status="superseded", identity_line=f"id: {slug}"))
    frozen = source.read_bytes()
    digest = hashlib.sha256(frozen).hexdigest().upper()
    manifest = _write_decision_v0_manifest(root, [{"path": source.name, "sha256": digest, "state": "admitted"}])
    consumer = root / "work-items" / "decisions" / "archive" / "2026-08" / "old-consumer.md"
    href = f"../../{source.name}"
    write(consumer, f"[frozen history]({href})\n")
    before = (manifest.read_bytes(), consumer.read_bytes())
    instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inventory = root / "incoming.json"
    write(inventory, json.dumps({
        "reference": f"decision:{slug}", "expectedSourceSha256": digest,
        "archivedAt": instant, "rationale": "Superseded.",
        "evidence": "Synthetic review.",
        "incomingLinks": [{
            "consumer": "decisions/archive/2026-08/old-consumer.md",
            "kind": "physical", "value": href,
        }],
    }))
    with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
        module.migrate_legacy(root, f"decision:{slug}", incoming_links_inventory=inventory)
    assert caught.exception.failure_id == "WI-LEGACY-LINK-UNMAPPED"
    assert source.read_bytes() == frozen
    assert (manifest.read_bytes(), consumer.read_bytes()) == before


def test_migrate_legacy_v0_compensates_failures_after_move_and_manifest(
    tmp_path: Path,
) -> None:
    module = load_module()
    for stage in ("manifest", "link"):
        root = tmp_path / stage
        slug = f"2026-08-01-{stage}-failure-v0"
        source = root / "work-items" / "decisions" / f"{slug}.md"
        write(source, _legacy_v0_decision_record(status="superseded", identity_line=f"id: {slug}"))
        frozen = source.read_bytes()
        digest = hashlib.sha256(frozen).hexdigest().upper()
        manifest = _write_decision_v0_manifest(
            root, [{"path": source.name, "sha256": digest, "state": "admitted"}]
        )
        consumer = root / "work-items" / "bugs" / "consumer.md"
        href = f"../decisions/{source.name}"
        write(consumer, f"[history]({href})\n")
        module.refresh_readme(root, allow_marker_bootstrap=True)
        readme = root / "work-items" / "README.md"
        before = (manifest.read_bytes(), consumer.read_bytes(), readme.read_bytes())
        instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        inventory = root / "incoming.json"
        write(inventory, json.dumps({
            "reference": f"decision:{slug}", "expectedSourceSha256": digest,
            "archivedAt": instant, "rationale": "Superseded.",
            "evidence": "Synthetic review.",
            "incomingLinks": [{"consumer": "bugs/consumer.md", "kind": "physical", "value": href}],
        }))
        fail_path = manifest if stage == "manifest" else consumer
        original_atomic_write = module._atomic_write
        failed = False

        def fail_once(path, data):
            nonlocal failed
            if Path(path) == fail_path and not failed:
                failed = True
                raise OSError(f"injected {stage} failure")
            return original_atomic_write(path, data)

        with patch.object(module, "_atomic_write", side_effect=fail_once):
            with unittest.TestCase().assertRaises(OSError):
                module.migrate_legacy(root, f"decision:{slug}", incoming_links_inventory=inventory)
        assert failed
        assert source.read_bytes() == frozen
        assert not (root / "work-items" / "decisions" / "archive" / instant[:7] / source.name).exists()
        assert (manifest.read_bytes(), consumer.read_bytes(), readme.read_bytes()) == before


def test_migrate_legacy_v0_removes_only_new_empty_archive_parents_on_failure(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-08-01-parent-cleanup-v0"
    source = root / "work-items" / "decisions" / f"{slug}.md"
    write(source, _legacy_v0_decision_record(status="superseded", identity_line=f"id: {slug}"))
    frozen = source.read_bytes()
    digest = hashlib.sha256(frozen).hexdigest().upper()
    manifest = _write_decision_v0_manifest(root, [{"path": source.name, "sha256": digest, "state": "admitted"}])
    manifest_before = manifest.read_bytes()
    instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inventory = root / "incoming.json"
    write(inventory, json.dumps({
        "reference": f"decision:{slug}", "expectedSourceSha256": digest,
        "archivedAt": instant, "rationale": "Superseded.",
        "evidence": "Synthetic review.", "incomingLinks": [],
    }))
    archive_root = root / "work-items" / "decisions" / "archive"
    archive_month_path = archive_root / instant[:7]
    original_mkdir = Path.mkdir

    def fail_after_month_creation(path, mode=0o777, parents=False, exist_ok=False):
        original_mkdir(path, mode=mode, parents=parents, exist_ok=exist_ok)
        if Path(path) == archive_month_path:
            raise OSError("injected interruption immediately after archive parent creation")

    with patch.object(Path, "mkdir", fail_after_month_creation):
        with unittest.TestCase().assertRaises(OSError):
            module.migrate_legacy(root, f"decision:{slug}", incoming_links_inventory=inventory)

    assert source.read_bytes() == frozen
    assert manifest.read_bytes() == manifest_before
    assert not archive_month_path.exists()
    assert not archive_root.exists()


def test_migrate_legacy_v0_keeps_preexisting_empty_archive_parents_on_failure(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-08-01-existing-parent-v0"
    source = root / "work-items" / "decisions" / f"{slug}.md"
    write(source, _legacy_v0_decision_record(status="superseded", identity_line=f"id: {slug}"))
    frozen = source.read_bytes()
    digest = hashlib.sha256(frozen).hexdigest().upper()
    manifest = _write_decision_v0_manifest(root, [{"path": source.name, "sha256": digest, "state": "admitted"}])
    manifest_before = manifest.read_bytes()
    instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    archive_month_path = root / "work-items" / "decisions" / "archive" / instant[:7]
    archive_month_path.mkdir(parents=True)
    inventory = root / "incoming.json"
    write(inventory, json.dumps({
        "reference": f"decision:{slug}", "expectedSourceSha256": digest,
        "archivedAt": instant, "rationale": "Superseded.",
        "evidence": "Synthetic review.", "incomingLinks": [],
    }))
    original_atomic_write = module._atomic_write
    failed = False

    def fail_manifest_once(path, data):
        nonlocal failed
        if Path(path) == manifest and not failed:
            failed = True
            raise OSError("injected manifest failure")
        return original_atomic_write(path, data)

    with patch.object(module, "_atomic_write", side_effect=fail_manifest_once):
        with unittest.TestCase().assertRaises(OSError):
            module.migrate_legacy(root, f"decision:{slug}", incoming_links_inventory=inventory)
    assert failed
    assert source.read_bytes() == frozen
    assert manifest.read_bytes() == manifest_before
    assert archive_month_path.is_dir()
    assert not any(archive_month_path.iterdir())


def test_decision_v0_v2_retirement_rejects_wrong_month_and_archive_hash(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-08-01-archive-bound-v0"
    source = root / "work-items" / "decisions" / f"{slug}.md"
    write(source, _legacy_v0_decision_record(status="superseded", identity_line=f"id: {slug}"))
    digest = hashlib.sha256(source.read_bytes()).hexdigest().upper()
    manifest = _write_decision_v0_manifest(root, [{"path": source.name, "sha256": digest, "state": "admitted"}])
    instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inventory = root / "incoming.json"
    write(inventory, json.dumps({
        "reference": f"decision:{slug}", "expectedSourceSha256": digest,
        "archivedAt": instant, "rationale": "Superseded.",
        "evidence": "Synthetic review.", "incomingLinks": [],
    }))
    archived = module.migrate_legacy(root, f"decision:{slug}", incoming_links_inventory=inventory)
    frozen_manifest = manifest.read_bytes()
    payload = json.loads(frozen_manifest)
    payload["entries"][0]["archiveEvidence"]["archivePath"] = (
        f"decisions/archive/2000-01/{source.name}"
    )
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with unittest.TestCase().assertRaises(module.LifecycleError) as wrong_month:
        module.audit_categories(root)
    assert wrong_month.exception.failure_id == "WI-DECISION-V0-MANIFEST-INVALID"
    manifest.write_bytes(frozen_manifest)
    archived.write_bytes(archived.read_bytes() + b"drift")
    with unittest.TestCase().assertRaises(module.LifecycleError) as wrong_hash:
        module.audit_categories(root)
    assert wrong_hash.exception.failure_id == "WI-DECISION-V0-HASH-MISMATCH"


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


def _legacy_h1_list_decision_record(
    slug: str,
    *,
    status: str = "accepted",
    extra_fields: tuple[tuple[str, str], ...] = (
        ("work-item", "legacy-work-item"),
        ("owner", "architecture-reviewer"),
    ),
    body: str = "Legacy H1 list-metadata decision body.\n",
) -> str:
    fields = (("id", slug), ("status", status), *extra_fields)
    prefix = "\n".join(f"- {key}: {value}" for key, value in fields)
    return f"# Decision: Legacy list metadata\n\n{prefix}\n\n{body}"


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


def test_decision_v1_first_heading_diagnostics_preserve_supported_formats_and_metadata_errors(
    tmp_path: Path,
) -> None:
    module = load_module()
    slug = "2026-08-11-first-heading-diagnostic"
    canonical = _canonical_decision_record(slug)

    h1_path = tmp_path / "h1" / f"{slug}.md"
    write(h1_path, canonical)
    assert module._validate_current_decision_record(h1_path, slug).format == "canonical-list-v1"

    h2_payload = canonical.replace(f"# Decision: {slug}\n\n", "")
    h2_path = tmp_path / "h2" / f"{slug}.md"
    write(h2_path, h2_payload)
    assert module._validate_current_decision_record(h2_path, slug).format == "canonical-list-v1"

    missing_metadata = canonical.replace("- context: schema-test\n", "")
    missing_metadata_path = tmp_path / "missing-metadata" / f"{slug}.md"
    write(missing_metadata_path, missing_metadata)
    with unittest.TestCase().assertRaises(module.LifecycleError) as metadata_caught:
        module._validate_current_decision_record(missing_metadata_path, slug)
    assert metadata_caught.exception.failure_id == "WI-DECISION-SCHEMA-INVALID"
    assert str(metadata_caught.exception) == (
        f"decision:{slug} requires one non-empty leading 'context' field"
    )

    unsupported = canonical.replace(
        f"# Decision: {slug}", "## Acceptance gate"
    )
    unsupported_path = tmp_path / "unsupported" / f"{slug}.md"
    write(unsupported_path, unsupported)
    with unittest.TestCase().assertRaises(module.LifecycleError) as unsupported_caught:
        module._validate_current_decision_record(unsupported_path, slug)
    assert unsupported_caught.exception.failure_id == "WI-DECISION-SCHEMA-INVALID"
    assert str(unsupported_caught.exception) == (
        f"decision:{slug} has unsupported first body heading at line 11: "
        "'## Acceptance gate'"
    )

    missing_heading = canonical.replace(
        f"# Decision: {slug}\n\n", "Decision title\n\n"
    ).replace("## Decision\n", "Decision body\n")
    missing_heading_path = tmp_path / "missing-heading" / f"{slug}.md"
    write(missing_heading_path, missing_heading)
    with unittest.TestCase().assertRaises(module.LifecycleError) as missing_heading_caught:
        module._validate_current_decision_record(missing_heading_path, slug)
    assert missing_heading_caught.exception.failure_id == "WI-DECISION-SCHEMA-INVALID"
    assert str(missing_heading_caught.exception) == (
        f"decision:{slug} has no body heading"
    )

    long_heading = "## " + "x" * 300
    long_payload = canonical.replace(f"# Decision: {slug}", long_heading)
    long_path = tmp_path / "long-heading" / f"{slug}.md"
    write(long_path, long_payload)
    with unittest.TestCase().assertRaises(module.LifecycleError) as long_caught:
        module._validate_current_decision_record(long_path, slug)
    message = str(long_caught.exception)
    assert long_caught.exception.failure_id == "WI-DECISION-SCHEMA-INVALID"
    assert len(message) < 300
    assert "x" * 200 not in message


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
        "schema": lambda payload: payload.update({"schemaVersion": 3}),
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


def test_decision_v0_manifest_is_repo_local_and_preflight_read_only(
    tmp_path: Path,
) -> None:
    module = load_module()
    for repo_name, slug in (("one", "2026-08-01-one"), ("two", "2026-08-02-two")):
        root = tmp_path / repo_name
        decision = root / "work-items" / "decisions" / f"{slug}.md"
        write(decision, _legacy_v0_decision_record(identity_line=f"id: {slug}"))
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
        policy = root / "work-items" / "decisions" / (
            "2026-08-18-current-decision-schema-versioned-read-compatibility.md"
        )
        protected = (decision, manifest, policy)
        before = {
            path: (path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns)
            for path in protected
        }
        with patch.object(module, "_atomic_write", side_effect=AssertionError("V0 preflight wrote")):
            assert module.audit_categories(root) == (f"decisions/{slug}.md",)
        assert {
            path: (path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns)
            for path in protected
        } == before
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


def test_decision_h1_manifest_admits_exact_heading_list_metadata(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "2026-07-18-external-owned-vcpkg-roots"
    decision = root / "work-items" / "decisions" / f"{slug}.md"
    body = "## Decision\n\nHistorical decision text remains opaque.\n"
    write(decision, _legacy_h1_list_decision_record(slug, body=body))
    decision_before = decision.read_bytes()
    manifest = _write_decision_h1_manifest(
        root,
        [
            {
                "path": decision.name,
                "sha256": hashlib.sha256(decision_before).hexdigest().upper(),
                "state": "admitted",
            }
        ],
    )
    manifest_before = manifest.read_bytes()

    assert module.audit_categories(root) == (f"decisions/{slug}.md",)
    record = module._preflight_current_decision_h1(root)[decision.name]

    assert record.format == "legacy-markdown-h1-v0"
    assert record.fields["id"] == slug
    assert record.fields["status"] == "accepted"
    assert record.raw_status == "accepted"
    assert record.admitted_current_status == "accepted"
    assert record.legacy_read_only is True
    normalized = decision.read_text(encoding="utf-8").encode("utf-8")
    assert normalized[record.body_offset :].decode("utf-8") == body
    assert decision.read_bytes() == decision_before
    assert manifest.read_bytes() == manifest_before


def test_decision_h1_list_metadata_requires_manifest_and_exact_identity_fields(
    tmp_path: Path,
) -> None:
    module = load_module()
    slug = "2026-07-18-external-owned-vcpkg-roots"
    canonical = _legacy_h1_list_decision_record(slug)

    unmanifested = tmp_path / "unmanifested"
    decision = unmanifested / "work-items" / "decisions" / f"{slug}.md"
    write(decision, canonical)
    with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
        module.audit_categories(unmanifested)
    assert caught.exception.failure_id == "WI-DECISION-H1-MANIFEST-MISSING"

    cases = {
        "missing-id": (
            canonical.replace(f"- id: {slug}\n", ""),
            "WI-DECISION-H1-SCHEMA-INVALID",
        ),
        "duplicate-id": (
            canonical.replace(f"- id: {slug}\n", f"- id: {slug}\n- id: {slug}\n"),
            "WI-DECISION-H1-FIELD-DUPLICATE",
        ),
        "wrong-id": (
            canonical.replace(f"- id: {slug}\n", "- id: 2026-07-18-wrong\n"),
            "WI-DECISION-IDENTITY-MISMATCH",
        ),
        "missing-status": (
            canonical.replace("- status: accepted\n", ""),
            "WI-DECISION-H1-STATUS-UNSUPPORTED",
        ),
        "duplicate-status": (
            canonical.replace(
                "- status: accepted\n",
                "- status: accepted\n- status: accepted\n",
            ),
            "WI-DECISION-H1-STATUS-UNSUPPORTED",
        ),
    }
    for name, (payload, failure_id) in cases.items():
        root = tmp_path / name
        current = root / "work-items" / "decisions" / f"{slug}.md"
        write(current, payload)
        before = current.read_bytes()
        manifest = _write_decision_h1_manifest(
            root,
            [
                {
                    "path": current.name,
                    "sha256": hashlib.sha256(before).hexdigest().upper(),
                    "state": "admitted",
                }
            ],
        )
        manifest_before = manifest.read_bytes()

        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module.audit_categories(root)

        assert caught.exception.failure_id == failure_id, name
        assert current.read_bytes() == before, name
        assert manifest.read_bytes() == manifest_before, name


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
            "preflight_import_active_successor",
            "apply_import_active_successor",
            "audit_categories",
            "audit",
            "write_current_identity_normalization_inventory",
            "normalize_current_identity",
            "migrate_legacy_ledger_obligation",
            "revoke_legacy_ledger_obligation",
            "archive_with_successor",
            "supersede_current_bug",
            "archive_fixed_bug",
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


def test_ledger_location_intent_discovery_bounds_file_count_before_loading(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    transition_root = root / ".scratch" / "work-items-lifecycle-transitions"
    transition_root.mkdir(parents=True)
    for index in range(1025):
        (transition_root / f"intent-{index:04d}.json").write_text("{}", encoding="utf-8")
    loaded: list[Path] = []
    original = module._ledger_location_proof_object

    def track(path: Path, **kwargs):
        loaded.append(path)
        return original(path, **kwargs)

    with patch.object(module, "_ledger_location_proof_object", side_effect=track):
        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module._matching_ledger_location_intents(
                root, root, slug="target", logical_work_item="work-items/active/target"
            )

    assert caught.exception.failure_id == "WI-LIFECYCLE-TRANSITION-INTENT-INVALID"
    assert "inventory limit" in str(caught.exception)
    assert loaded == []


def test_ledger_location_intent_discovery_bounds_each_file_before_full_read(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    transition_root = root / ".scratch" / "work-items-lifecycle-transitions"
    transition_root.mkdir(parents=True)
    oversized = transition_root / "oversized.json"
    oversized.write_bytes(b" " * (256 * 1024 + 1))
    observed_reads: list[Path] = []
    original_read_bytes = Path.read_bytes

    def track_read(path: Path) -> bytes:
        if path == oversized:
            observed_reads.append(path)
        return original_read_bytes(path)

    with patch.object(Path, "read_bytes", track_read):
        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module._matching_ledger_location_intents(
                root, root, slug="target", logical_work_item="work-items/active/target"
            )

    assert caught.exception.failure_id == "WI-LIFECYCLE-TRANSITION-INTENT-INVALID"
    assert "byte limit" in str(caught.exception)
    assert observed_reads == []

def test_ledger_location_intent_discovery_bounds_cumulative_bytes_before_loading(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    transition_root = root / ".scratch" / "work-items-lifecycle-transitions"
    transition_root.mkdir(parents=True)
    payload = b"{}" + b" " * (256 * 1024 - 2)
    for index in range(33):
        (transition_root / f"intent-{index:02d}.json").write_bytes(payload)
    loaded: list[Path] = []
    original = module._ledger_location_proof_object

    def track(path: Path, **kwargs):
        loaded.append(path)
        return original(path, **kwargs)

    with patch.object(module, "_ledger_location_proof_object", side_effect=track):
        with unittest.TestCase().assertRaises(module.LifecycleError) as caught:
            module._matching_ledger_location_intents(
                root, root, slug="target", logical_work_item="work-items/active/target"
            )

    assert caught.exception.failure_id == "WI-LIFECYCLE-TRANSITION-INTENT-INVALID"
    assert "cumulative byte limit" in str(caught.exception)
    assert loaded == []


class _UnittestAdapter(unittest.TestCase):
    """Run the module's pytest-style functions under the plan's unittest CLI."""


def _adapt_test(function):
    def method(self):
        with tempfile.TemporaryDirectory() as directory:
            function(Path(directory))

    method.__name__ = function.__name__
    return method


for _name, _function in tuple(globals().items()):
    if _name.startswith("test_") and callable(_function):
        setattr(_UnittestAdapter, _name, _adapt_test(_function))
