"""Regression tests for the work-items-archival Stop hook.

The hook fires at turn end and BLOCKS the stop when a delivered/closed work-item
is still sitting in work-items/active/ instead of being archived. It is the
structural backstop for the Recovery rule's close step (the create-but-never-
close failure that left orphans piling up in active/).

These tests assert against the universal, Claude, and Codex copies:
  (1) the three orphan signals (closure.md present, status.md `State: closed`,
      status.md whole-item-done prose) each BLOCK;
  (2) a merely-active or parked item does NOT block (false-positive guard);
  (3) phase-level "complete" / "Gate PASS" prose does NOT block (the parked
      2026-06-02-style status must stay quiet);
  (4) a SUBAGENT context (envelope carries agent_id) is NEVER blocked, even with
      an orphan present — hooks must not interfere with subagents working;
  (5) the per-stop override marker, stop_hook_active, a non-Orchestrarium cwd,
      and a malformed envelope all ALLOW (fail-open);
  (6) the hook always exits 0 (decision carried by stdout payload).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS = (
    REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "check-work-items-archival-stop.py",
    REPO_ROOT / "src.claude" / "agents" / "scripts" / "check-work-items-archival-stop.py",
    REPO_ROOT / "src.codex" / "skills" / "lead" / "scripts" / "check-work-items-archival-stop.py",
)


def make_repo(item: str | None = None, files: dict[str, str] | None = None) -> str:
    """Create a temp repo root with an optional work-items/active/<item>/."""
    root = tempfile.mkdtemp(prefix="wi-archival-")
    if item is not None:
        active = Path(root) / "work-items" / "active" / item
        active.mkdir(parents=True, exist_ok=True)
        for name, content in (files or {}).items():
            (active / name).write_text(content, encoding="utf-8")
    return root


def run_hook(
    script: Path,
    envelope: dict,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.pop("ORCHESTRARIUM_DISPATCHED_REVIEW", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(envelope, ensure_ascii=False),
        capture_output=True, text=True, encoding="utf-8",
        env=env,
    )


def blocks(p: subprocess.CompletedProcess) -> bool:
    return '"decision"' in p.stdout and '"block"' in p.stdout


class TestWorkItemsArchivalHook(unittest.TestCase):
    def assert_outcome(
        self,
        envelope: dict,
        should_block: bool,
        *,
        extra_env: dict[str, str] | None = None,
    ) -> None:
        for script in HOOKS:
            with self.subTest(pack=script.parent.parent.name):
                p = run_hook(script, envelope, extra_env)
                self.assertEqual(p.returncode, 0, p.stderr)  # always exits 0
                self.assertEqual(blocks(p), should_block, f"stdout={p.stdout!r}")

    # --- orphan signals: BLOCK -------------------------------------------------

    def test_closure_md_present_blocks(self) -> None:
        repo = make_repo("itemA", {"closure.md": "outcome: PASS", "status.md": "State: active\n"})
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=True)

    def test_status_state_closed_blocks(self) -> None:
        repo = make_repo("itemB", {"status.md": "# Status\n\nState: closed\n"})
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=True)

    def test_status_current_stage_closed_blocks(self) -> None:
        repo = make_repo("itemB2", {"status.md": "Current stage: Closed\n\nState: closed\n"})
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=True)

    def test_current_state_done_line_blocks(self) -> None:
        # The multitask-style done banner: the done word is on a state-key LINE
        # ('CURRENT STATE: DONE'), which is what makes it count (not free prose).
        repo = make_repo("itemC", {"status.md": "> **CURRENT STATE: DONE — all shipped, nothing pending** ★★★\n"})
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=True)

    def test_outcome_archived_line_blocks(self) -> None:
        repo = make_repo("itemC2", {"status.md": "Outcome: archived\n"})
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=True)

    def test_canonical_primary_task_status_bolded_key_blocks(self) -> None:
        # MAJOR regression: the CANONICAL status.md marker per
        # subagent-contracts.md is "- **Primary task status**: closed" (a
        # bullet-dash prefix, bolded key, and a "Primary task " modifier before
        # "status") -- the old regex required the key to be exactly
        # state/status/stage/outcome with no leading bullet dash and no
        # "Primary task " prefix, so this canonical, real-world form was a
        # FALSE NEGATIVE (a real orphan the hook would never catch).
        repo = make_repo("itemCanon", {"status.md": "## Current state\n\n- **Primary task status**: closed\n"})
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=True)

    def test_canonical_primary_task_status_active_does_not_block(self) -> None:
        repo = make_repo("itemCanonActive", {"status.md": "## Current state\n\n- **Primary task status**: active\n"})
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=False)

    def test_outcome_complete_when_criterion_does_not_block(self) -> None:
        # FP regression (review MAJOR): 'Outcome: complete WHEN all tests pass'
        # is a completion CRITERION, not a whole-item-done declaration.
        repo = make_repo("itemCrit", {"status.md": "State: active\n\nOutcome: complete when all tests pass\n"})
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=False)

    def test_outcome_complete_russian_kogda_criterion_does_not_block(self) -> None:
        repo = make_repo("itemCritRu", {"status.md": "State: active\n\nOutcome: done когда все тесты пройдут\n"})
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=False)

    def test_outcome_bold_emphasis_complete_when_criterion_does_not_block(self) -> None:
        # 2nd-round FP regression: markdown emphasis around the done word
        # ('**complete**') blocked the [ \t]-only exclusion from reaching
        # "when", so this criterion still false-fired the orphan block.
        repo = make_repo("itemCritBold", {"status.md": "State: active\n\nOutcome: **complete** when the deploy finishes\n"})
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=False)

    def test_outcome_comma_complete_when_criterion_does_not_block(self) -> None:
        # 2nd-round FP regression: a comma between the done word and "when"
        # also blocked the [ \t]-only exclusion.
        repo = make_repo("itemCritComma", {"status.md": "State: active\n\nOutcome: complete, when this ships\n"})
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=False)

    # --- false-positive guards: ALLOW -----------------------------------------

    def test_active_item_does_not_block(self) -> None:
        repo = make_repo("itemActive", {"status.md": "Current stage: Research\n\nState: active\n\nNext: run W1..W5\n"})
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=False)

    def test_parked_item_does_not_block(self) -> None:
        repo = make_repo("itemParked", {"status.md": "State: parked\n\nPENDING — needs the user\n"})
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=False)

    def test_phase_level_complete_does_not_block(self) -> None:
        # A status describing per-PHASE completion + 'Gate PASS' must NOT be read
        # as a whole-item-done marker (the parked 2026-06-02 audit shape).
        repo = make_repo("itemPhase", {"status.md":
            "State: active\n\n- Phase A: complete\n- Phase B: complete\n"
            "Gate PASS. all green at pause. 2 commits ahead, unpushed.\n"})
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=False)

    def test_active_nothing_pending_prose_does_not_block(self) -> None:
        # FP regression (review MAJOR): 'nothing pending' in chatty prose on an
        # ACTIVE item must not be read as whole-item-done. State line says active.
        repo = make_repo("itemNP", {"status.md":
            "Status: active\n\nNothing pending on our side, waiting for user review.\n"})
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=False)

    def test_active_phase_shipped_pushed_does_not_block(self) -> None:
        # FP regression (review MAJOR): per-phase 'shipped + pushed' prose on an
        # active multi-phase item must not block (must not nudge premature archival).
        repo = make_repo("itemSP", {"status.md":
            "State: active\n\n- Phase 1 (parser): shipped + pushed\n- Phase 2: in progress\n"})
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=False)

    def test_closed_hyphenated_state_does_not_block(self) -> None:
        # FP regression (review MINOR): 'closed-loop' must not satisfy closed-state.
        repo = make_repo("itemCL", {"status.md": "State: closed-loop controller benchmarks ongoing\n"})
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=False)

    def test_stage_value_not_starting_with_done_word_does_not_block(self) -> None:
        # FP regression: 'Current stage: Phase 2 complete' — the value does NOT
        # begin with a done word, so it is an active stage description, not done.
        repo = make_repo("itemPC", {"status.md": "Current stage: Phase 2 complete\n\nState: active\n"})
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=False)

    # --- subagent safety: ALLOW (the core invariant the user demanded) ---------

    def test_subagent_agent_id_never_blocks_even_with_orphan(self) -> None:
        repo = make_repo("itemA", {"closure.md": "x", "status.md": "State: closed\n"})
        self.assert_outcome(
            {"cwd": repo, "agent_id": "sub-123", "last_assistant_message": "done"},
            should_block=False,
        )

    def test_subagent_empty_agent_id_still_evaluates(self) -> None:
        # An empty/falsey agent_id is NOT a subagent marker -> normal evaluation.
        repo = make_repo("itemA", {"closure.md": "x"})
        self.assert_outcome({"cwd": repo, "agent_id": "", "last_assistant_message": "done"}, should_block=True)

    def test_dispatched_review_env_never_blocks_even_with_orphan(self) -> None:
        repo = make_repo("itemA", {"closure.md": "x", "status.md": "State: closed\n"})
        self.assert_outcome(
            {"cwd": repo, "last_assistant_message": "done"},
            should_block=False,
            extra_env={"ORCHESTRARIUM_DISPATCHED_REVIEW": "1"},
        )

    # --- override / loop-guard / out-of-scope / malformed: ALLOW ---------------

    def test_override_marker_allows(self) -> None:
        repo = make_repo("itemA", {"closure.md": "x"})
        self.assert_outcome(
            {"cwd": repo, "last_assistant_message": "leaving it open [acknowledge-open-work-items]"},
            should_block=False,
        )

    def test_stop_hook_active_allows(self) -> None:
        repo = make_repo("itemA", {"closure.md": "x"})
        self.assert_outcome({"cwd": repo, "stop_hook_active": True, "last_assistant_message": "done"}, should_block=False)

    def test_no_work_items_dir_allows(self) -> None:
        repo = make_repo()  # no work-items/active at all
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=False)

    def test_empty_envelope_allows(self) -> None:
        for script in HOOKS:
            with self.subTest(pack=script.parent.parent.name):
                p = run_hook(script, {})
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertFalse(blocks(p), p.stdout)

    def test_malformed_stdin_allows(self) -> None:
        for script in HOOKS:
            with self.subTest(pack=script.parent.parent.name):
                p = subprocess.run([sys.executable, str(script)], input="not json{",
                                   capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertFalse(blocks(p), p.stdout)

    # --- multiple orphans are all reported ------------------------------------

    def test_multiple_orphans_all_listed(self) -> None:
        root = tempfile.mkdtemp(prefix="wi-archival-multi-")
        for name, files in (("done1", {"closure.md": "x"}), ("done2", {"status.md": "State: closed\n"})):
            d = Path(root) / "work-items" / "active" / name
            d.mkdir(parents=True, exist_ok=True)
            for fn, c in files.items():
                (d / fn).write_text(c, encoding="utf-8")
        for script in HOOKS:
            with self.subTest(pack=script.parent.parent.name):
                p = run_hook(script, {"cwd": root, "last_assistant_message": "done"})
                self.assertTrue(blocks(p), p.stdout)
                self.assertIn("done1", p.stdout)
                self.assertIn("done2", p.stdout)

    # --- repo-boundary regression (MAJOR): nested-projects operator layout ----

    def test_repo_boundary_stops_before_parent_orphan(self) -> None:
        # This operator nests projects (Orchestrator/Orchestrarium,
        # Orchestrator/benchmarks): an orphan sitting in a PARENT directory's
        # work-items/active/ (a different, unrelated project) must not block
        # every session in every child repo. The walk must stop at the first
        # ancestor containing .git rather than climbing indefinitely.
        root = tempfile.mkdtemp(prefix="wi-archival-boundary-")
        parent_orphan = Path(root) / "work-items" / "active" / "parent-orphan"
        parent_orphan.mkdir(parents=True, exist_ok=True)
        (parent_orphan / "closure.md").write_text("outcome: PASS", encoding="utf-8")
        repo = Path(root) / "myrepo"
        (repo / ".git").mkdir(parents=True, exist_ok=True)  # repo root marker; no work-items/active of its own
        self.assert_outcome({"cwd": str(repo), "last_assistant_message": "done"}, should_block=False)

    def test_finds_active_dir_through_subdirectory_within_repo(self) -> None:
        # A cwd nested several levels inside the repo must still find
        # work-items/active/ living at the repo root (the common case) --
        # confirms the boundary fix did not regress the normal walk-up.
        root = tempfile.mkdtemp(prefix="wi-archival-subdir-")
        repo = Path(root) / "myrepo"
        (repo / ".git").mkdir(parents=True, exist_ok=True)
        active = repo / "work-items" / "active" / "itemX"
        active.mkdir(parents=True, exist_ok=True)
        (active / "closure.md").write_text("x", encoding="utf-8")
        subdir = repo / "src" / "nested"
        subdir.mkdir(parents=True, exist_ok=True)
        self.assert_outcome({"cwd": str(subdir), "last_assistant_message": "done"}, should_block=True)


def make_epic_repo(
    epic_status: str,
    children: list[str],
    *,
    active: dict[str, str] | None = None,
    archived: list[str] | None = None,
    epic_name: str = "2026-06-13-demo-epic",
) -> str:
    """Build a temp repo with work-items/epics/<epic_name>.md + child work-items.

    children: child slugs listed in the epic ## Children section.
    active: {slug: status.md text} children placed under active/ (NOT done unless
            the status text says so).
    archived: slugs placed under archive/2026-06/<slug>/ (counts as done).
    """
    root = tempfile.mkdtemp(prefix="wi-epic-")
    base = Path(root) / "work-items"
    (base / "active").mkdir(parents=True, exist_ok=True)
    epics = base / "epics"
    epics.mkdir(parents=True, exist_ok=True)
    child_lines = "\n".join(f"- {c} (active)" for c in children) or "(none yet)"
    (epics / f"{epic_name}.md").write_text(
        f"---\nstatus: {epic_status}\nepic-id: {epic_name}\nowner: $lead\n---\n"
        f"# Epic: demo\n\n## Goal\nship the thing\n\n## Children\n{child_lines}\n",
        encoding="utf-8",
    )
    for slug, text in (active or {}).items():
        d = base / "active" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "status.md").write_text(text, encoding="utf-8")
    for slug in (archived or []):
        d = base / "archive" / "2026-06" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "status.md").write_text("State: closed\n", encoding="utf-8")
    return root


def write_raw_epic(
    epic_text: str,
    *,
    archived: list[str] | None = None,
    active: dict[str, str] | None = None,
    epic_name: str = "2026-06-13-raw-epic",
) -> str:
    """Build a temp repo with a RAW epic file body (for parser edge-case tests)."""
    root = tempfile.mkdtemp(prefix="wi-epic-raw-")
    base = Path(root) / "work-items"
    (base / "active").mkdir(parents=True, exist_ok=True)
    (base / "epics").mkdir(parents=True, exist_ok=True)
    (base / "epics" / f"{epic_name}.md").write_text(epic_text, encoding="utf-8")
    for slug, text in (active or {}).items():
        d = base / "active" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "status.md").write_text(text, encoding="utf-8")
    for slug in (archived or []):
        d = base / "archive" / "2026-06" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "status.md").write_text("State: closed\n", encoding="utf-8")
    return root


class TestEpicCloseHook(unittest.TestCase):
    """B1 extension: the same Stop guard catches epic-lifecycle orphans in
    work-items/epics/ — a ready-to-close epic never closed, or a closed epic
    whose child was reopened. Fail-open when epics/ is absent or an epic is
    malformed; a 0-child epic never flags; a subagent is never blocked."""

    def assert_outcome(self, envelope: dict, should_block: bool, *, expect_in: str | None = None) -> None:
        for script in HOOKS:
            with self.subTest(pack=script.parent.parent.name):
                p = run_hook(script, envelope)
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(blocks(p), should_block, f"stdout={p.stdout!r}")
                if should_block and expect_in:
                    self.assertIn(expect_in, p.stdout)

    def test_ready_to_close_epic_blocks(self) -> None:
        # epic active, every child archived (done) -> should be closed.
        repo = make_epic_repo("active", ["c1", "c2"], archived=["c1", "c2"])
        self.assert_outcome(
            {"cwd": repo, "last_assistant_message": "done"},
            should_block=True, expect_in="2026-06-13-demo-epic",
        )

    def test_epic_with_active_children_does_not_block(self) -> None:
        repo = make_epic_repo("active", ["c1"], active={"c1": "State: active\n"})
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=False)

    def test_stale_closed_epic_blocks(self) -> None:
        # epic closed, but c2 is still active -> should reopen.
        repo = make_epic_repo("closed", ["c1", "c2"], archived=["c1"], active={"c2": "State: active\n"})
        self.assert_outcome(
            {"cwd": repo, "last_assistant_message": "done"},
            should_block=True, expect_in="reopen",
        )

    def test_fully_closed_epic_does_not_block(self) -> None:
        repo = make_epic_repo("closed", ["c1", "c2"], archived=["c1", "c2"])
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=False)

    def test_zero_child_epic_does_not_block(self) -> None:
        repo = make_epic_repo("active", [])
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=False)

    def test_subagent_never_blocks_epic_orphan(self) -> None:
        repo = make_epic_repo("active", ["c1"], archived=["c1"])
        self.assert_outcome(
            {"cwd": repo, "agent_id": "sub-9", "last_assistant_message": "done"},
            should_block=False,
        )

    def test_child_done_via_status_line_counts(self) -> None:
        # child resolved as done via its in-active status.md done-line (not archive).
        # (this child is ALSO an item-orphan, so the stop blocks; assert the epic
        #  ready-to-close reason is present too.)
        repo = make_epic_repo("active", ["c1"], active={"c1": "State: closed\n"})
        self.assert_outcome(
            {"cwd": repo, "last_assistant_message": "done"},
            should_block=True, expect_in="close it",
        )

    def test_malformed_epic_file_fails_open(self) -> None:
        # an epic file with no status: line is skipped (no crash, no flag).
        root = tempfile.mkdtemp(prefix="wi-epic-bad-")
        base = Path(root) / "work-items"
        (base / "active").mkdir(parents=True, exist_ok=True)
        (base / "epics").mkdir(parents=True, exist_ok=True)
        (base / "epics" / "junk.md").write_text("no frontmatter here\n", encoding="utf-8")
        self.assert_outcome({"cwd": root, "last_assistant_message": "done"}, should_block=False)

    # --- FP regressions (review MAJOR): _parse_epic_children over-collection ---

    def test_closed_epic_with_prose_bullet_under_children_does_not_block(self) -> None:
        # A prose note bullet (no '(active|closed)' marker) under ## Children must
        # NOT be read as a phantom child that re-opens a correctly-closed epic.
        epic = (
            "---\nstatus: closed\n---\n# Epic: demo\n\n## Children\n"
            "- c1 (closed)\n- migration follow-up tracked separately in the bug registry\n"
        )
        repo = write_raw_epic(epic, archived=["c1"])
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=False)

    def test_closed_epic_with_h3_under_children_does_not_block(self) -> None:
        # An h3 subsection under ## Children must reset the section so its bullets
        # are not collected as phantom children of a closed epic.
        epic = (
            "---\nstatus: closed\n---\n# Epic: demo\n\n## Children\n- c1 (closed)\n"
            "\n### Deferred ideas\n- some idea that is not a child work-item\n"
        )
        repo = write_raw_epic(epic, archived=["c1"])
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=False)

    def test_body_status_line_without_frontmatter_is_ignored(self) -> None:
        # A body line 'status: active' (NOT in --- frontmatter) must not be read
        # as the epic status; with no frontmatter the epic is skipped (fail-open).
        epic = "# Epic: demo\n\n## Goal\ng\n\nstatus: active\n\n## Children\n- c1 (closed)\n"
        repo = write_raw_epic(epic, archived=["c1"])
        self.assert_outcome({"cwd": repo, "last_assistant_message": "done"}, should_block=False)


if __name__ == "__main__":
    unittest.main()
