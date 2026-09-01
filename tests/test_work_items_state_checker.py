import importlib.util
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check-work-items-state.py"
VALIDATOR = ROOT / "scripts" / "validate-work-item-state.py"
MUTATOR = ROOT / "scripts" / "mutate-work-item.py"


def run_checker(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(root), *args],
        text=True,
        capture_output=True,
    )


def write_checker_bundle(bundle_dir: Path, sentinel_source: str | None = None) -> Path:
    """Copy the checker into an isolated installed-layout fixture."""
    bundle_dir.mkdir(parents=True)
    schema_dir = bundle_dir.parent / "shared" / "schemas"
    schema_dir.mkdir(parents=True)
    shutil.copy2(
        ROOT / "shared" / "schemas" / "agent-runs.schema.json",
        schema_dir / "agent-runs.schema.json",
    )
    checker = bundle_dir / CHECKER.name
    shutil.copy2(CHECKER, checker)
    shutil.copy2(VALIDATOR, bundle_dir / VALIDATOR.name)
    shutil.copy2(MUTATOR, bundle_dir / MUTATOR.name)
    if sentinel_source is not None:
        (bundle_dir / "workitem_sentinels.py").write_text(sentinel_source, encoding="utf-8")
    return checker


def run_bundled_checker(checker: Path, root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(checker), "--root", str(root)],
        text=True,
        capture_output=True,
    )


def load_checker_module():
    spec = importlib.util.spec_from_file_location("check_work_items_state_direct", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_validator_module():
    spec = importlib.util.spec_from_file_location("work_item_validator_direct", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_false_event_validity_cannot_settle_revise_or_register_terminal():
    validator = load_validator_module()
    revise = {
        "schemaVersion": 2, "runId": "revise-001", "role": "qa-engineer",
        "executionRole": "internal", "gate": "REVISE", "status": "revise",
    }
    closer = {
        "schemaVersion": 2, "runId": "closer-001", "role": "qa-engineer",
        "executionRole": "internal", "gate": "PASS", "status": "completed",
        "closesRunIds": ["revise-001"], "eventKind": "terminal", "launchRunId": "launch-001",
    }
    launch = {"schemaVersion": 2, "runId": "launch-001", "eventKind": "launch"}
    errors: list[str] = []
    open_revise, open_launches = validator.validate_closure(
        [launch, revise, closer], errors, event_validity=[True, True, False]
    )
    assert [event["runId"] for event in open_revise] == ["revise-001"]
    assert [event["runId"] for event in open_launches] == ["launch-001"]


def test_invalid_launch_target_cannot_be_settled_by_a_valid_terminal():
    validator = load_validator_module()
    launch = {"schemaVersion": 2, "runId": "launch-001", "eventKind": "launch"}
    terminal = {
        "schemaVersion": 2, "runId": "terminal-001", "eventKind": "terminal",
        "launchRunId": "launch-001", "status": "completed", "gate": "PASS",
    }
    errors: list[str] = []

    _open_revise, open_launches = validator.validate_closure(
        [launch, terminal], errors, event_validity=[False, True]
    )

    assert [event["runId"] for event in open_launches] == ["launch-001"]


def valid_status() -> str:
    return "\n".join(
        [
            "# Status",
            "",
            "## Current state",
            "**Primary task status**: open",
            "",
            "## Active agents",
            "- none",
            "",
            "## Completed agents",
            "- none",
            "",
            "## Next action",
            "Continue.",
            "",
        ]
    )


def minimal_staged_status(**updates: str) -> str:
    fields = {
        "template": "staged",
        "status": "active",
        "started": "2026-07-31T10:00:00Z",
        "updated": "2026-07-31T10:05:00Z",
        "Task": "Keep the staged checker contract aligned.",
        "Current step": "Verify the shared status validator.",
        "Last result": "Staged work item admitted.",
        "Next action": "Run the staged checker gate.",
        "Scope boundary": "Work-item lifecycle scripts and focused tests.",
        "Owner": "toolchain-engineer",
        "Integration owner": "lead",
        "Evidence gate": "Focused and full lifecycle suites.",
    }
    fields.update(updates)
    frontmatter = [
        "---",
        f"template: {fields.pop('template')}",
        f"status: {fields.pop('status')}",
        f"started: {fields.pop('started')}",
        f"updated: {fields.pop('updated')}",
        "---",
        "",
    ]
    return "\n".join(frontmatter + [f"{key}: {value}" for key, value in fields.items()]) + "\n"


def ledger_event(**updates):
    event = {
        "schemaVersion": 1,
        "runId": "run-check-001",
        "workItem": "active-item",
        "role": "qa-engineer",
        "executionRole": "internal",
        "status": "completed",
        "gate": "PASS",
        "scope": ["tests/test_work_items_state_checker.py"],
        "artifact": "reviews/qa.md",
        "evidence": [{"kind": "command", "ref": "pytest -q"}],
        "startedAt": "2026-05-03T10:00:00Z",
        "updatedAt": "2026-05-03T10:05:00Z",
    }
    event.update(updates)
    return event


def write_valid_item(root: Path, name: str = "active-item", event: dict | None = None) -> Path:
    item = root / "work-items" / "active" / name
    (item / "reviews").mkdir(parents=True)
    (item / "status.md").write_text(valid_status(), encoding="utf-8")
    (item / "reviews" / "qa.md").write_text("PASS\n", encoding="utf-8")
    (item / "agent-runs.jsonl").write_text(json.dumps(event or ledger_event(workItem=name)) + "\n", encoding="utf-8")
    return item


def write_staged_item(
    root: Path,
    name: str = "staged-item",
    status: str | None = None,
    event: dict | None = None,
) -> Path:
    item = root / "work-items" / "active" / name
    (item / "reviews").mkdir(parents=True)
    (item / "status.md").write_text(status or minimal_staged_status(), encoding="utf-8")
    (item / "reviews" / "qa.md").write_text("PASS\n", encoding="utf-8")
    selected_event = event or ledger_event(workItem=name)
    (item / "agent-runs.jsonl").write_text(
        json.dumps(selected_event) + "\n",
        encoding="utf-8",
    )
    return item


REQUIRED_SENTINEL_STUB = """\
def resolve_epic_locations(epics_dir, slug):
    return {"state": "missing", "locations": []}
"""


def test_checker_fails_when_required_sentinel_candidates_are_missing_without_epic_link(
    tmp_path: Path,
):
    repo = tmp_path / "repo"
    checker = write_checker_bundle(tmp_path / "bundle")
    write_valid_item(repo)

    result = run_bundled_checker(checker, repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout.count("required-sentinel-dependency-unavailable") == 1
    assert "installed-sibling" in result.stdout
    assert "source-universal-hooks" in result.stdout
    assert "RESULT: FAIL" in result.stdout


def test_checker_preserves_required_sentinel_import_failure_cause(tmp_path: Path):
    repo = tmp_path / "repo"
    checker = write_checker_bundle(tmp_path / "bundle", "def broken(:\n")
    write_valid_item(repo)

    result = run_bundled_checker(checker, repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout.count("required-sentinel-dependency-unavailable") == 1
    assert "installed-sibling: SyntaxError:" in result.stdout
    assert "invalid syntax" in result.stdout


def test_checker_rejects_incomplete_required_sentinel_contract(tmp_path: Path):
    repo = tmp_path / "repo"
    checker = write_checker_bundle(
        tmp_path / "bundle",
        "def unrelated_capability():\n    return None\n",
    )
    write_valid_item(repo)

    result = run_bundled_checker(checker, repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout.count("required-sentinel-contract-mismatch") == 1
    assert "missing callable(s): resolve_epic_locations" in result.stdout


def test_checker_keeps_absent_optional_sentinel_reporting_verdict_neutral(tmp_path: Path):
    repo = tmp_path / "repo"
    checker = write_checker_bundle(tmp_path / "bundle", REQUIRED_SENTINEL_STUB)
    write_valid_item(repo)

    result = run_bundled_checker(checker, repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: PASS" in result.stdout
    assert "required-sentinel-" not in result.stdout
    assert "sentinel optional reporting unavailable: missing callable(s):" in result.stdout
    assert "build_context" in result.stdout
    assert "evaluate_all" in result.stdout


def test_checker_accepts_minimal_staged_status_and_reports_v1_next_action(tmp_path: Path):
    repo = tmp_path / "repo"
    checker = write_checker_bundle(tmp_path / "bundle", REQUIRED_SENTINEL_STUB)
    write_staged_item(repo)

    result = run_bundled_checker(checker, repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS staged-item" in result.stdout
    assert "staged-item -- Next action: Run the staged checker gate." in result.stdout
    assert "status.md missing section" not in result.stdout


def test_checker_accepts_asterisk_bullet_staged_status_fields(tmp_path: Path):
    repo = tmp_path / "repo"
    checker = write_checker_bundle(tmp_path / "bundle", REQUIRED_SENTINEL_STUB)
    status = minimal_staged_status()
    for field in (
        "Task",
        "Current step",
        "Last result",
        "Next action",
        "Scope boundary",
        "Owner",
        "Integration owner",
        "Evidence gate",
    ):
        status = status.replace(f"{field}: ", f"* {field}: ")
    write_staged_item(repo, status=status)

    result = run_bundled_checker(checker, repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS staged-item" in result.stdout
    assert "staged-item -- Next action: Run the staged checker gate." in result.stdout


def test_checker_rejects_staged_status_missing_required_v1_field(tmp_path: Path):
    repo = tmp_path / "repo"
    checker = write_checker_bundle(tmp_path / "bundle", REQUIRED_SENTINEL_STUB)
    status = minimal_staged_status()
    status = status.replace(
        "Evidence gate: Focused and full lifecycle suites.\n",
        "",
    )
    write_staged_item(repo, status=status)

    result = run_bundled_checker(checker, repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "staged status missing fields: evidence gate" in result.stdout
    assert "status.md missing section" not in result.stdout


def test_checker_preserves_open_revise_failure_on_staged_status(tmp_path: Path):
    repo = tmp_path / "repo"
    checker = write_checker_bundle(tmp_path / "bundle", REQUIRED_SENTINEL_STUB)
    revise = ledger_event(
        schemaVersion=2,
        runId="run-staged-revise-001",
        workItem="staged-item",
        status="revise",
        gate="REVISE",
        eventKind="standalone",
        lane="staged-contract",
        effort="high",
        findingClass="correctness",
    )
    write_staged_item(repo, event=revise)

    result = run_bundled_checker(checker, repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "open REVISE obligation: run-staged-revise-001" in result.stdout
    assert "status.md missing section" not in result.stdout


def test_checker_preserves_unsettled_launch_failure_on_staged_status(tmp_path: Path):
    repo = tmp_path / "repo"
    checker = write_checker_bundle(tmp_path / "bundle", REQUIRED_SENTINEL_STUB)
    launch = ledger_event(
        schemaVersion=2,
        runId="run-staged-launch-001",
        workItem="staged-item",
        status="running",
        gate="none",
        eventKind="launch",
        lane="staged-contract",
        effort="high",
        startedAt="2026-07-31T10:00:00Z",
        updatedAt="2026-07-31T10:05:00Z",
    )
    write_staged_item(repo, event=launch)

    result = run_bundled_checker(checker, repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "unsettled launch: run-staged-launch-001" in result.stdout
    assert "status.md missing section" not in result.stdout


def test_checker_keeps_failing_optional_sentinel_reporting_verdict_neutral(tmp_path: Path):
    repo = tmp_path / "repo"
    checker = write_checker_bundle(
        tmp_path / "bundle",
        REQUIRED_SENTINEL_STUB
        + """
def build_context(root):
    return {"root": root}

def evaluate_all(context):
    raise RuntimeError("optional reporting failed")
""",
    )
    write_valid_item(repo)

    result = run_bundled_checker(checker, repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: PASS" in result.stdout
    assert "required-sentinel-" not in result.stdout
    assert (
        "sentinel optional reporting failed: RuntimeError: optional reporting failed"
        in result.stdout
    )


def test_checker_preserves_required_epic_resolver_call_failure_cause(tmp_path: Path):
    repo = tmp_path / "repo"
    checker = write_checker_bundle(
        tmp_path / "bundle",
        REQUIRED_SENTINEL_STUB.replace(
            'return {"state": "missing", "locations": []}',
            'raise RuntimeError("epic resolution failed")',
        ),
    )
    item = write_valid_item(repo)
    (item / "status.md").write_text(
        valid_status().replace(
            "**Primary task status**: open",
            "**Primary task status**: open\n**Epic**: demo-epic",
        ),
        encoding="utf-8",
    )

    result = run_bundled_checker(checker, repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "epic location resolver failed: RuntimeError: epic resolution failed" in result.stdout


def test_checker_treats_unowned_markdown_sections_as_inert(tmp_path: Path):
    item = write_valid_item(tmp_path)
    baseline = run_checker(tmp_path)
    with (item / "status.md").open("a", encoding="utf-8") as handle:
        handle.write(
            "\n## Delivery action\n\n"
            "This retired heading is ordinary Markdown and carries no control meaning.\n"
        )

    with_unowned_section = run_checker(tmp_path)

    assert baseline.returncode == 0, baseline.stdout + baseline.stderr
    assert with_unowned_section.returncode == baseline.returncode
    assert with_unowned_section.stdout == baseline.stdout
    assert with_unowned_section.stderr == baseline.stderr


def test_checker_passes_when_no_active_directory_exists(tmp_path: Path):
    result = run_checker(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "no active work-items" in result.stdout


def test_checker_validates_all_active_items(tmp_path: Path):
    write_valid_item(tmp_path, "valid-item")
    bad = tmp_path / "work-items" / "active" / "bad-item"
    bad.mkdir(parents=True)
    (bad / "status.md").write_text(valid_status(), encoding="utf-8")

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert "PASS valid-item" in result.stdout
    assert "FAIL bad-item" in result.stdout
    assert "missing ledger" in result.stdout


def test_checker_rejects_unapplied_active_bug_disposition_manifest(
    tmp_path: Path,
) -> None:
    item = write_valid_item(tmp_path)
    (item / "bug-dispositions.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "workItem": item.name,
                "closedAt": "2026-08-11T10:09:00Z",
                "bugs": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert "WI-BUG-DISPOSITIONS-PENDING" in result.stdout


def test_pass_surfaces_active_items_and_denies_completion(tmp_path: Path):
    """Forcing function (bug 2026-07-18-false-completion-claim-validator-pass-conflated-with-done):
    a green RESULT must never read as 'all closed'. The checker prints every active item + its
    Next action, and the RESULT line itself says valid-state-not-completion — so a PASS cannot be
    quoted as completion while active work remains."""
    write_valid_item(tmp_path, "active-item")
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "STILL OPEN" in result.stdout
    assert "active-item -- Next action: Continue." in result.stdout
    assert "NOT completion" in result.stdout
    # and the empty case must not claim completion falsely either — it says 'no active work-items'
    empty = run_checker(tmp_path / "does-not-exist")
    assert "no active work-items" in empty.stdout
    assert "STILL OPEN" not in empty.stdout  # no items => no STILL OPEN block


def test_forcing_function_survives_non_ascii_next_action_on_narrow_console(tmp_path: Path):
    """The enumeration prints ARBITRARY status content; a non-ASCII Next action (em-dash,
    arrow) must NOT crash the report on a non-UTF-8 console. The stream-level errors=replace
    guard in main() owns this — replacing the em-dash in one string literal would not
    (fable + codex ff-review: the crash class lives in the interpolated data)."""
    item = write_valid_item(tmp_path, "unicode-item")
    (item / "status.md").write_text(
        valid_status().replace("Continue.", "Run probe 1 — then reconcile → close."),
        encoding="utf-8",
    )
    env = {**os.environ, "PYTHONIOENCODING": "cp866"}
    result = subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(tmp_path)],
        text=True, capture_output=True, encoding="cp866", errors="replace", env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr  # no UnicodeEncodeError
    assert "unicode-item" in result.stdout
    assert "STILL OPEN" in result.stdout


def test_next_actionable_heading_does_not_false_match(tmp_path: Path):
    """Exact heading match: a '## Next actionable' section must NOT be read as the
    '## Next action' section (codex ff-review — the old startswith accepted it)."""
    item = write_valid_item(tmp_path, "actionable-item")
    (item / "status.md").write_text(
        "# Status\n\n## Current state\n**Primary task status**: open\n\n"
        "## Active agents\n- none\n\n## Completed agents\n- none\n\n"
        "## Next actionable\nWRONG heading content\n\n"
        "## Next action\nCORRECT action content\n",
        encoding="utf-8",
    )
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "CORRECT action content" in result.stdout
    assert "WRONG heading content" not in result.stdout


def status_with_depends(dep_value: str) -> str:
    return valid_status().replace(
        "**Primary task status**: open",
        "**Primary task status**: open\n**Depends-on**: " + dep_value,
    )


def status_with_epic(epic_value: str) -> str:
    return valid_status().replace(
        "**Primary task status**: open",
        "**Primary task status**: open\n**Epic**: " + epic_value,
    )


def status_with_no_epic_rationale() -> str:
    return valid_status().replace(
        "**Primary task status**: open",
        "**Primary task status**: open\n**No-epic rationale**: standalone fixes",
    )


def write_item_with_status(root: Path, name: str, status_text: str) -> Path:
    item = root / "work-items" / "active" / name
    (item / "reviews").mkdir(parents=True)
    (item / "status.md").write_text(status_text, encoding="utf-8")
    (item / "reviews" / "qa.md").write_text("PASS\n", encoding="utf-8")
    (item / "agent-runs.jsonl").write_text(json.dumps(ledger_event(workItem=name)) + "\n", encoding="utf-8")
    return item


def test_relation_slug_validation_consumes_canonical_lifecycle_owner(tmp_path: Path):
    checker = load_checker_module()
    lifecycle = checker.load_lifecycle_owner()
    slug_is_valid = getattr(lifecycle, "is_valid_slug", None)
    assert callable(slug_is_valid), "lifecycle owner must publish its canonical slug predicate"
    sentinels = checker.load_required_sentinels()
    assert callable(sentinels.resolve_epic_locations), sentinels.diagnostic()

    matrix = (
        ("legacy-valid-slug", True),
        ("2026-07-19-model-ranking-aa-coding-index-v1.1", True),
        ("trailing.", False),
        ("double..dot", False),
        ("Uppercase", False),
        ("under_score", False),
        ("path/segment", False),
        ("../traversal", False),
    )
    for index, (slug, expected) in enumerate(matrix):
        try:
            lifecycle._validate_slug(slug)
        except lifecycle.LifecycleError as exc:
            assert exc.failure_id == "WI-INVALID-SLUG", slug
            mutator_accepts = False
        else:
            mutator_accepts = True
        assert mutator_accepts is expected, slug
        assert slug_is_valid(slug) is expected, slug

        case_root = tmp_path / f"case-{index}"
        status = valid_status().replace(
            "**Primary task status**: open",
            "**Primary task status**: open\n"
            f"**Depends-on**: {slug}\n"
            f"**Epic**: {slug}",
        )
        item = write_item_with_status(case_root, "relation-source", status)
        active_dir = case_root / "work-items" / "active"
        dependency_notes = checker.blocked_by_notes(
            item,
            case_root,
            lifecycle,
            slug_is_valid,
        )
        epic_notes = checker.epic_link_notes(
            item,
            active_dir,
            sentinels.resolve_epic_locations,
            slug_is_valid,
        )
        if expected:
            assert dependency_notes == [
                f"blocked-by: {slug} (unresolved Depends-on)",
                f"dangling Depends-on: {slug} (no matching work-item)"
            ], slug
            assert epic_notes and epic_notes[0].startswith(f"dangling Epic: {slug} "), slug
        else:
            assert dependency_notes == [f"invalid Depends-on: {slug}"], slug
            assert epic_notes == [f"invalid Epic: {slug}"], slug


# --- aging report (B2): informational, never a failure ----------------------

def test_aging_flags_old_item_as_info(tmp_path: Path):
    write_valid_item(tmp_path, "2026-01-01-old-item")
    result = run_checker(tmp_path, "--max-age-days", "30", "--now", "2026-06-13T00:00:00Z")
    assert result.returncode == 0, result.stdout  # aging is info, not a failure
    assert "PASS 2026-01-01-old-item" in result.stdout
    assert "info: aging" in result.stdout


def test_aging_not_flagged_for_recent_item(tmp_path: Path):
    write_valid_item(tmp_path, "2026-06-10-recent-item")
    result = run_checker(tmp_path, "--max-age-days", "30", "--now", "2026-06-13T00:00:00Z")
    assert result.returncode == 0
    assert "aging" not in result.stdout


def test_aging_disabled_by_default(tmp_path: Path):
    write_valid_item(tmp_path, "2026-01-01-old-item")
    result = run_checker(tmp_path)  # no --max-age-days -> default 0 -> disabled
    assert result.returncode == 0
    assert "aging" not in result.stdout


# --- blocker-state (B2): informational, never a failure ---------------------

def test_blocked_by_open_target_is_info_not_failure(tmp_path: Path):
    write_valid_item(tmp_path, "dep-target")  # exists, valid, not done
    write_item_with_status(tmp_path, "blocked-item", status_with_depends("dep-target"))
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout  # blocked is expected state, not a failure
    assert "info: blocked-by: dep-target" in result.stdout


def test_blocked_by_backlog_target_is_info_not_dangling(tmp_path: Path):
    backlog = tmp_path / "work-items" / "backlog"
    backlog.mkdir(parents=True)
    (backlog / "dep-target.md").write_text("status: candidate\n", encoding="utf-8")
    write_item_with_status(tmp_path, "blocked-item", status_with_depends("dep-target"))
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "info: blocked-by: dep-target (open Depends-on)" in result.stdout
    assert "dangling Depends-on: dep-target" not in result.stdout


def test_dangling_depends_on_reported(tmp_path: Path):
    write_item_with_status(tmp_path, "item-x", status_with_depends("ghost-item"))
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "blocked-by: ghost-item (unresolved Depends-on)" in result.stdout
    assert "dangling Depends-on: ghost-item" in result.stdout


def test_blocked_by_done_target_not_reported(tmp_path: Path):
    arch = tmp_path / "work-items" / "archive" / "2026-05" / "done-dep"
    arch.mkdir(parents=True)
    (arch / "status.md").write_text("State: closed\n", encoding="utf-8")
    write_item_with_status(tmp_path, "item-y", status_with_depends("done-dep"))
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "blocked-by" not in result.stdout


def test_duplicate_dependency_location_fails_closed(tmp_path: Path):
    backlog = tmp_path / "work-items" / "backlog"
    backlog.mkdir(parents=True)
    (backlog / "dep-target.md").write_text("status: candidate\n", encoding="utf-8")
    write_valid_item(tmp_path, "dep-target")
    write_item_with_status(tmp_path, "blocked-item", status_with_depends("dep-target"))
    result = run_checker(tmp_path)
    assert result.returncode == 1, result.stdout
    assert "WI-CATEGORY-DUAL-LOCATION" in result.stdout
    assert "blocked-by: dep-target (unresolved Depends-on)" in result.stdout
    assert "duplicate Depends-on: dep-target" in result.stdout


def test_depends_on_none_no_note(tmp_path: Path):
    write_item_with_status(tmp_path, "item-z", status_with_depends("none"))
    result = run_checker(tmp_path)
    assert result.returncode == 0
    assert "blocked-by" not in result.stdout
    assert "dangling" not in result.stdout


# --- epic links: unique active/archive target required -----------------------

def test_dangling_epic_reported(tmp_path: Path):
    write_item_with_status(tmp_path, "item-epic", status_with_epic("2026-06-18-missing-epic"))
    result = run_checker(tmp_path)
    assert result.returncode == 1, result.stdout
    assert "dangling Epic: 2026-06-18-missing-epic" in result.stdout


def test_existing_epic_not_reported(tmp_path: Path):
    epics = tmp_path / "work-items" / "epics"
    epics.mkdir(parents=True)
    (epics / "2026-06-18-demo.md").write_text("---\nstatus: active\n---\n", encoding="utf-8")
    write_item_with_status(tmp_path, "item-epic", status_with_epic("2026-06-18-demo"))
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "dangling Epic" not in result.stdout


def test_archived_epic_is_a_valid_link_target(tmp_path: Path):
    archived = tmp_path / "work-items" / "epics" / "archive" / "2026-06"
    archived.mkdir(parents=True)
    (archived / "2026-06-18-demo.md").write_text("---\nstatus: closed\n---\n", encoding="utf-8")
    write_item_with_status(tmp_path, "item-epic", status_with_epic("2026-06-18-demo"))
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "dangling Epic" not in result.stdout
    assert "duplicate Epic" not in result.stdout


def test_duplicate_active_and_archived_epic_is_rejected(tmp_path: Path):
    epics = tmp_path / "work-items" / "epics"
    archived = epics / "archive" / "2026-06"
    archived.mkdir(parents=True)
    (epics / "2026-06-18-demo.md").write_text("---\nstatus: active\n---\n", encoding="utf-8")
    (archived / "2026-06-18-demo.md").write_text("---\nstatus: closed\n---\n", encoding="utf-8")
    write_item_with_status(tmp_path, "item-epic", status_with_epic("2026-06-18-demo"))
    result = run_checker(tmp_path)
    assert result.returncode == 1, result.stdout
    assert "duplicate Epic: 2026-06-18-demo" in result.stdout
    assert "epics/2026-06-18-demo.md" in result.stdout
    assert "epics/archive/2026-06/2026-06-18-demo.md" in result.stdout


def test_duplicate_epic_across_archive_months_is_rejected(tmp_path: Path):
    epics = tmp_path / "work-items" / "epics" / "archive"
    for month in ("2026-05", "2026-06"):
        archived = epics / month
        archived.mkdir(parents=True)
        (archived / "2026-06-18-demo.md").write_text("---\nstatus: closed\n---\n", encoding="utf-8")
    write_item_with_status(tmp_path, "item-epic", status_with_epic("2026-06-18-demo"))
    result = run_checker(tmp_path)
    assert result.returncode == 1, result.stdout
    assert "duplicate Epic: 2026-06-18-demo" in result.stdout


def test_multiple_active_items_without_epics_surface_adoption_prompt(tmp_path: Path):
    write_valid_item(tmp_path, "item-a")
    write_valid_item(tmp_path, "item-b")
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "no work-items/epics/ directory for multiple active items" in result.stdout


def test_no_epic_rationale_suppresses_adoption_prompt(tmp_path: Path):
    write_item_with_status(tmp_path, "item-a", status_with_no_epic_rationale())
    write_valid_item(tmp_path, "item-b")
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "no work-items/epics/ directory" not in result.stdout


def test_checker_reports_stale_running_agent_when_threshold_is_enabled(tmp_path: Path):
    write_valid_item(
        tmp_path,
        "stale-item",
        ledger_event(
            runId="run-stale-001",
            workItem="stale-item",
            status="running",
            gate="none",
            artifact="",
            evidence=[],
            updatedAt="2026-05-03T08:00:00Z",
        ),
    )

    result = run_checker(tmp_path, "--stale-hours", "1", "--now", "2026-05-03T10:30:00Z")

    assert result.returncode == 1
    assert "stale running agent" in result.stdout


def test_checker_stale_check_ignores_settled_launches_but_reports_unmatched_launches(
    tmp_path: Path,
):
    item = write_valid_item(tmp_path, "stale-item")
    launch_common = {
        "schemaVersion": 2,
        "workItem": "stale-item",
        "role": "qa-engineer",
        "executionRole": "internal",
        "scope": ["tests/test_work_items_state_checker.py"],
        "artifact": "reviews/qa.md",
        "startedAt": "2026-05-03T08:00:00Z",
        "updatedAt": "2026-05-03T08:00:00Z",
        "lane": "stale-check",
    }
    settled_launch = {
        **launch_common,
        "runId": "launch-settled-001",
        "status": "running",
        "gate": "none",
        "evidence": [],
        "eventKind": "launch",
    }
    terminal = {
        **launch_common,
        "runId": "terminal-settled-001",
        "status": "completed",
        "gate": "PASS",
        "evidence": [{"kind": "command", "ref": "pytest -q"}],
        "eventKind": "terminal",
        "launchRunId": "launch-settled-001",
    }
    unmatched_launch = {
        **launch_common,
        "runId": "launch-unmatched-001",
        "status": "running",
        "gate": "none",
        "evidence": [],
        "eventKind": "launch",
    }
    (item / "agent-runs.jsonl").write_text(
        "\n".join(
            json.dumps(event) for event in (settled_launch, terminal, unmatched_launch)
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_checker(
        tmp_path,
        "--no-strict-revise",
        "--stale-hours",
        "1",
        "--now",
        "2026-05-03T10:30:00Z",
    )

    assert result.returncode == 1, result.stdout
    assert "launch-settled-001: stale running agent" not in result.stdout
    assert "launch-unmatched-001: stale running agent" in result.stdout


def test_archive_scan_propagates_security_reviewer_waiver_validity(tmp_path: Path, subtests):
    def archived_case(case_name: str, *, invalid: bool = False, legacy_waiver: bool = False):
        root = tmp_path / case_name
        item_name = f"archived-{case_name}"
        item = root / "work-items" / "archive" / "2026-07" / item_name
        (item / "reviews").mkdir(parents=True)
        (item / "reviews" / "security.md").write_text("PASS\n", encoding="utf-8")
        target_id = f"run-archive-{case_name}-target"
        waiver_id = f"run-archive-{case_name}-waiver"
        target = ledger_event(
            schemaVersion=2,
            runId=target_id,
            workItem=item_name,
            role="security-reviewer",
            executionRole="external-reviewer",
            status="revise",
            gate="REVISE",
            artifact="reviews/security.md",
            lane=f"archive-{case_name}",
            findingClass="security",
        )
        waiver = ledger_event(
            schemaVersion=1 if legacy_waiver else 2,
            runId=waiver_id,
            workItem=item_name,
            role="security-reviewer",
            executionRole="internal",
            status="completed",
            gate="WAIVED:security-reviewer",
            scope=[] if invalid else ["archive security review"],
            artifact="reviews/security.md",
            evidence=[{
                "kind": "manual-check",
                "ref": f"security-reviewer waives {target_id}",
            }],
            closesRunIds=[target_id],
        )
        (item / "agent-runs.jsonl").write_text(
            "\n".join(json.dumps(event) for event in (target, waiver)) + "\n",
            encoding="utf-8",
        )
        return run_checker(root), target_id, waiver_id

    with subtests.test(case="legal version-2 waiver"):
        result, target_id, _waiver_id = archived_case("legal")

        assert result.returncode == 0, result.stdout
        assert f"open REVISE obligation survived archival: {target_id}" not in result.stdout
        assert "archive scan clean" in result.stdout

    with subtests.test(case="invalid version-2 waiver"):
        result, target_id, waiver_id = archived_case("invalid", invalid=True)

        assert result.returncode == 1
        assert f"{waiver_id}: scope must be a non-empty list" in result.stdout
        assert f"open REVISE obligation survived archival: {target_id}" in result.stdout

    with subtests.test(case="legacy version-1 waiver"):
        result, target_id, waiver_id = archived_case("legacy", legacy_waiver=True)

        assert result.returncode == 1
        assert f"open REVISE obligation survived archival: {target_id}" in result.stdout
        assert f"{waiver_id}: field closesRunIds requires schemaVersion 2" not in result.stdout


def raw_v2_archived_review_events(item_name: str) -> tuple[dict, dict]:
    target = ledger_event(
        schemaVersion=2,
        runId="run-archive-legacy-target",
        workItem=item_name,
        role="qa-engineer",
        executionRole="internal",
        status="revise",
        gate="REVISE",
        artifact=".scratch/reviews/legacy-qa-pass.md",
        lane="archive-legacy-review",
        effort="high",
        provider="codex",
        findingClass="correctness",
    )
    closer = ledger_event(
        schemaVersion=2,
        runId="run-archive-legacy-closer",
        workItem=item_name,
        role="qa-engineer",
        executionRole="internal",
        status="completed",
        gate="PASS",
        artifact=".scratch/reviews/legacy-qa-pass.md",
        evidence=[{"kind": "review", "ref": "legacy archived review PASS"}],
        lane="archive-legacy-review",
        effort="high",
        provider="codex",
        closesRunIds=[target["runId"]],
    )
    return target, closer


def test_archive_scan_accepts_raw_v2_missing_legacy_review_pointer(tmp_path: Path) -> None:
    item_name = "archived-legacy-review-pointer"
    item = tmp_path / "work-items" / "archive" / "2026-07" / item_name
    item.mkdir(parents=True)
    target, closer = raw_v2_archived_review_events(item_name)
    ledger = item / "agent-runs.jsonl"
    ledger.write_text(
        "\n".join(json.dumps(event) for event in (target, closer)) + "\n",
        encoding="utf-8",
    )
    before = ledger.read_bytes()

    result = run_checker(tmp_path, "--telemetry")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "artifact does not exist" not in result.stdout
    assert "open REVISE obligation survived archival" not in result.stdout
    assert "archive-legacy-review-pointer-compat=1" in result.stdout
    assert ledger.read_bytes() == before


def test_archive_review_pointer_closes_only_its_named_revise(tmp_path: Path) -> None:
    validator = load_validator_module()
    item_name = "archived-legacy-review-residual"
    item = tmp_path / "work-items" / "archive" / "2026-07" / item_name
    (item / "reviews").mkdir(parents=True)
    (item / "reviews" / "parked.md").write_text("PARKED\n", encoding="utf-8")
    target, closer = raw_v2_archived_review_events(item_name)
    parked = ledger_event(
        schemaVersion=2,
        runId="run-archive-parked-residual",
        workItem=item_name,
        role="qa-engineer",
        executionRole="internal",
        status="revise",
        gate="REVISE",
        artifact="reviews/parked.md",
        lane="archive-parked-residual",
        effort="high",
        provider="codex",
        findingClass="correctness",
    )
    ledger = item / "agent-runs.jsonl"
    ledger.write_text(
        "\n".join(json.dumps(event) for event in (target, parked, closer)) + "\n",
        encoding="utf-8",
    )
    before = ledger.read_bytes()
    telemetry: dict[str, int] = {}

    errors, open_revise, open_launches = validator.validate_archived_ledger_obligations(
        item, telemetry=telemetry
    )

    assert errors == []
    assert [event["runId"] for event in open_revise] == [parked["runId"]]
    assert open_launches == []
    assert telemetry.get("archive-legacy-review-pointer-compat") == 1
    assert ledger.read_bytes() == before


def test_archive_review_pointer_compatibility_is_strictly_bounded(tmp_path: Path) -> None:
    validator = load_validator_module()
    item = tmp_path / "work-items" / "archive" / "2026-07" / "bounded-review-pointer"
    item.mkdir(parents=True)
    base = ledger_event(
        schemaVersion=2,
        runId="run-bounded-review-pointer",
        workItem=item.name,
        role="qa-engineer",
        executionRole="internal",
        status="completed",
        gate="PASS",
        artifact=".scratch/reviews/missing.md",
        evidence=[{"kind": "review", "ref": "legacy archived review PASS"}],
    )

    def derive(event: dict, transformation: str = "raw", authorizations=None):
        encoded = json.dumps(
            event, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        event_sha = hashlib.sha256(encoded).hexdigest()
        row = validator.LedgerProjectionRowV1(
            event, 1, event_sha, event_sha, transformation
        )
        errors: list[str] = []
        validity, closure_validity = validator.derive_archived_event_validity(
            [event], item, errors, authorizations or {}, rows=(row,)
        )
        return errors, validity, closure_validity

    for name, update in (
        ("repository path", {"artifact": "reviews/missing.md"}),
        ("scratch outside reviews", {"artifact": ".scratch/output/missing.md"}),
        ("reviews directory itself", {"artifact": ".scratch/reviews"}),
        ("typed scratch identity", {"scratchEvidence": []}),
    ):
        errors, validity, closure_validity = derive({**base, **update})
        assert any("artifact does not exist" in error for error in errors), name
        assert validity == [False], name
        assert closure_validity == [False], name

    for transformation in ("manifest-projected", "migration-replaced"):
        errors, validity, closure_validity = derive(base, transformation)
        assert any("artifact does not exist" in error for error in errors), transformation
        assert validity == [False], transformation
        assert closure_validity == [False], transformation

    active = tmp_path / "work-items" / "active" / "bounded-review-pointer"
    active.mkdir(parents=True)
    active_errors: list[str] = []
    assert not validator.validate_event(base, active, set(), active_errors)
    assert any("artifact does not exist" in error for error in active_errors)

    present = item / ".scratch" / "reviews" / "present.md"
    present.parent.mkdir(parents=True)
    present.write_text("present but typed identity is malformed\n", encoding="utf-8")
    existing_mismatch = {
        **base,
        "artifact": ".scratch/reviews/present.md",
        "scratchEvidence": [],
    }
    errors, validity, closure_validity = derive(existing_mismatch)
    assert any("scratchEvidence" in error for error in errors)
    assert validity == [False]
    assert closure_validity == [False]

    authorized = {**base, "artifactRevision": "a" * 64}
    encoded = json.dumps(
        authorized, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    event_sha = hashlib.sha256(encoded).hexdigest()
    authorization = validator.HistoricalArtifactAuthorization(
        1,
        event_sha,
        event_sha,
        authorized["runId"],
        authorized["artifact"],
        authorized["artifactRevision"],
    )
    errors, validity, closure_validity = derive(authorized, authorizations={1: authorization})
    assert errors == []
    assert validity == [True]
    assert closure_validity == [False]

    drifted_authorization = validator.HistoricalArtifactAuthorization(
        1,
        "0" * 64,
        event_sha,
        authorized["runId"],
        authorized["artifact"],
        authorized["artifactRevision"],
    )
    errors, validity, closure_validity = derive(
        authorized, authorizations={1: drifted_authorization}
    )
    assert any("artifact does not exist" in error for error in errors)
    assert validity == [False]
    assert closure_validity == [False]

    version_three = {"schemaVersion": 3}
    errors, validity, closure_validity = derive(version_three)
    assert errors == []
    assert validity == [False]
    assert closure_validity == [False]


def test_active_only_keeps_periodic_archive_failures_out_of_publication_scope(
    tmp_path: Path,
) -> None:
    (tmp_path / "work-items" / "active").mkdir(parents=True)
    item_name = "archived-open-revise"
    item = tmp_path / "work-items" / "archive" / "2026-07" / item_name
    (item / "reviews").mkdir(parents=True)
    (item / "reviews" / "qa.md").write_text("REVISE\n", encoding="utf-8")
    revise = ledger_event(
        schemaVersion=2,
        runId="run-archived-open-revise-001",
        workItem=item_name,
        role="qa-engineer",
        executionRole="internal",
        status="revise",
        gate="REVISE",
        artifact="reviews/qa.md",
        lane="archived-review",
        findingClass="correctness",
    )
    (item / "agent-runs.jsonl").write_text(
        json.dumps(revise) + "\n", encoding="utf-8"
    )

    periodic = run_checker(tmp_path)
    publication = run_checker(tmp_path, "--active-only")

    assert periodic.returncode == 1
    assert "open REVISE obligation survived archival" in periodic.stdout
    assert publication.returncode == 0, publication.stdout
    assert "(ARCHIVED)" not in publication.stdout
    assert "archive obligation scan skipped" in publication.stdout


def test_publication_gate_requests_active_only_work_item_scope() -> None:
    source = (ROOT / "scripts" / "check-publication-gate.py").read_text(
        encoding="utf-8"
    )

    assert '"--active-only"' in source
    assert "run: python scripts/check-work-items-state.py --active-only" in source


def test_archive_scan_keeps_skipped_legacy_positions_for_v2_closure_targets(tmp_path: Path):
    item = tmp_path / "work-items" / "archive" / "2026-07" / "archived-legacy-target"
    (item / "reviews").mkdir(parents=True)
    (item / "reviews" / "security.md").write_text("PASS\n", encoding="utf-8")
    target_id = "run-archive-legacy-target"
    target = ledger_event(
        schemaVersion=1,
        runId=target_id,
        workItem="archived-legacy-target",
        role="security-reviewer",
        executionRole="external-reviewer",
        status="revise",
        gate="REVISE",
        artifact="reviews/security.md",
        lane="archive-legacy-target",
        findingClass="security",
    )
    closer = ledger_event(
        schemaVersion=2,
        runId="run-archive-v2-closer",
        workItem="archived-legacy-target",
        role="security-reviewer",
        executionRole="internal",
        status="completed",
        gate="WAIVED:security-reviewer",
        scope=["archive security review"],
        artifact="reviews/security.md",
        evidence=[{"kind": "manual-check", "ref": f"security-reviewer waives {target_id}"}],
        closesRunIds=[target_id],
    )
    (item / "agent-runs.jsonl").write_text(
        "\n".join(json.dumps(event) for event in (target, closer)) + "\n",
        encoding="utf-8",
    )

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert "does not reference an earlier event (C1)" not in result.stdout


def test_done_predicate_twin_not_drifted():
    # The state-checker re-implements the SEN-0 archival-orphan invariant's
    # DONE_STATE regex (no shared import across the sentinel/validator
    # boundary — workitem_sentinels.py must never be imported BY the
    # validator's twin logic, only the reverse; design.md §3.2). Guard against
    # silent drift: the distinctive pattern line must appear verbatim in BOTH
    # files. As of the sentinel-registry migration
    # (2026-07-25-review-round-cap-enforcement), the regex's owning file is
    # `workitem_sentinels.py`, not `check-work-items-archival-stop.py` (now a
    # thin adapter that imports it) — the twin-check follows the regex to its
    # new home rather than the file that used to hold it.
    line = r'r"\s*\*{0,3}\s*:\s*\*{0,3}\s*(?:closed|done|complete|completed|archived)(?![\w-])"'
    sentinels = (ROOT / "src.claude" / "agents" / "scripts" / "workitem_sentinels.py").read_text(encoding="utf-8")
    checker = CHECKER.read_text(encoding="utf-8")
    assert line in sentinels, "workitem_sentinels.py DONE_STATE pattern changed — update the twin in check-work-items-state.py"
    assert line in checker, "check-work-items-state.py DONE_STATE pattern drifted from workitem_sentinels.py"


class TestArchiveOnlyDependencyTerminality(unittest.TestCase):
    def test_active_semantic_done_is_not_terminal_until_archive_move(self) -> None:
        lifecycle = load_checker_module().load_lifecycle_owner()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "work-items" / "active"
            archive = root / "work-items" / "archive"
            item = active / "dependency"
            item.mkdir(parents=True)
            (item / "status.md").write_text("status: completed\n", encoding="utf-8")
            (item / "closure.md").write_text(
                "Closed: 2026-07-31T00:00:00Z\n",
                encoding="utf-8",
            )
            self.assertEqual(
                lifecycle.work_item_dependency_state(root, "dependency"),
                "open",
            )
            archived = archive / "2026-07" / "dependency"
            archived.parent.mkdir(parents=True)
            item.replace(archived)
            self.assertEqual(
                lifecycle.work_item_dependency_state(root, "dependency"),
                "done",
            )


def test_decision_schema_failure_reaches_repository_state_checker(tmp_path: Path) -> None:
    decision = (
        tmp_path
        / "work-items"
        / "decisions"
        / "2026-08-11-schema-test.md"
    )
    decision.parent.mkdir(parents=True)
    decision.write_text(
        "---\nstatus: proposed\nnot-a-field\ndate: 2026-08-11\n---\n"
        "\n# Decision: malformed\n",
        encoding="utf-8",
    )
    entry = {
        "path": decision.name,
        "sha256": hashlib.sha256(decision.read_bytes()).hexdigest().upper(),
        "state": "admitted",
    }
    baseline = hashlib.sha256(
        f"{entry['path']}\0{entry['sha256']}\n".encode("utf-8")
    ).hexdigest().upper()
    policy_slug = "2026-08-18-current-decision-schema-versioned-read-compatibility"
    (decision.parent / f"{policy_slug}.md").write_text(
        "\n".join(
            [
                f"- id: {policy_slug}",
                "- status: accepted",
                "- date: 2026-08-18",
                "- decided-by: $architect",
                "- context: schema-test",
                "- supersedes: none",
                "- superseded-by: none",
                "- accepted-evidence: fixture",
                "- v0-manifest: work-items/decision-v0-compatibility.json",
                f"- v0-baseline-sha256: {baseline}",
                "- v0-cutover-date: 2026-08-18",
                "",
                f"# Decision: {policy_slug}",
                "",
                "## Decision",
                "Fixture policy anchor.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "work-items" / "decision-v0-compatibility.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "policyDecision": policy_slug,
                "cutoverDate": "2026-08-18",
                "baselineSha256": baseline,
                "entries": [entry],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert "WI-DECISION-V0-SCHEMA-INVALID" in result.stdout
