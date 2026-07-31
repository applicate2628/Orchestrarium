import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "mutate-work-item.py"
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


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
    assert sorted(path.name for path in trial_root.iterdir()) == ["user-content.txt"]


def test_utc_same_instant_boundary_replay(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "utc-boundary"
    seed_active(module, root, slug)
    instant = "2026-08-01T00:00:00Z"
    closure_bytes = closure(instant).encode()

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


def test_readme_stale_recovery_guard(tmp_path: Path) -> None:
    module = load_module()
    root = tmp_path / "repo"
    slug = "stale-readme"
    seed_active(module, root, slug)
    old_readme = (root / "work-items" / "README.md").read_bytes()
    instant = "2026-07-31T10:00:00Z"

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
    assert archived.is_dir()
    assert not (root / "work-items" / "active" / slug).exists()
    validator = module._validator_module()
    assert validator.validate_work_item(archived) == []
    assert (root / "work-items" / "README.md").read_bytes() == old_readme
    try:
        module.check_readme(root)
    except module.LifecycleError as exc:
        assert exc.failure_id == "WI-README-STALE"
    else:
        raise AssertionError("stale README was accepted")
    repaired = module.refresh_readme(root)
    assert len(repaired) == 64
    assert repaired == hashlib.sha256(
        (root / "work-items" / "README.md").read_bytes()
    ).hexdigest()
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

        successor_slug = f"{category_name}-successor"
        successor_data = (
            f"status: {current_status[category_name]}\n"
            f"Reopens: {slug}\n"
        ).encode()
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
