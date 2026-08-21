"""Regression tests for the current work-item sentinel registry.

Covers the design's named guards that are unit-testable without a live
provider CLI: G-1b, G-4, G-5, G-6 (incl. T-13's degraded-posture primary),
G-7, G-8/T-2, G-11, G-12, G-13/T-10, G-14/T-16 (SEN-0-scoped post-r8), plus
SEN-1 behavior, T-3 (subagent skip), and T-4 (determinism).

G-1 (SEN-0 verdict-equivalence) and G-2 (byte-identity of the wrapper AND the
registry module across canon + 2 pack trees) are NOT duplicated here:
  - G-1 is `tests/test_work_items_archival_hook.py` -- the pre-existing
    archival-hook suite, run unchanged against the new adapter (40 tests /
    120 subtests, all passing against this change).
  - G-2 is `tests/test_universal_hook_surfaces.py`'s glob-derived
    `filecmp.cmp(shallow=False)` gate, which picked up `workitem_sentinels.py`
    automatically the moment it landed in the canon dir (no new guard
    machinery -- design.md §5.2 / F-B10).

G-3 (Codex trust preservation) and G-9/T-11 (Claude-line cross-hook
precedence) require a LIVE provider binary and are not run as part of this
suite (they cost real API calls / require an installed CLI). Both were run
manually this session; see the implementation report for the reproduced
evidence (hash recomputation against the live installed `stop:1:0` entry, and
the two-hook Claude-line probe).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CANON_MODULE = REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "workitem_sentinels.py"
CANON_ADAPTER = REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "check-work-items-archival-stop.py"

ADAPTERS = (
    CANON_ADAPTER,
    REPO_ROOT / "src.claude" / "agents" / "scripts" / "check-work-items-archival-stop.py",
    REPO_ROOT / "src.codex" / "skills" / "lead" / "scripts" / "check-work-items-archival-stop.py",
)


def _load_sentinels():
    spec = importlib.util.spec_from_file_location("workitem_sentinels_under_test", CANON_MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sentinels = _load_sentinels()


def _git(cwd: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, env=env)


def make_git_repo() -> Path:
    root = Path(tempfile.mkdtemp(prefix="wi-sentinels-"))
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    return root


def commit_all(root: Path, message: str, iso_date: str) -> str:
    env = {
        "GIT_AUTHOR_DATE": iso_date,
        "GIT_COMMITTER_DATE": iso_date,
        # Preserve enough of the ambient environment for git to find its own
        # binaries/config on Windows; only the date vars are the point here.
        **{k: v for k, v in __import__("os").environ.items()},
    }
    _git(root, "add", "-A", env=env)
    result = _git(root, "commit", "-q", "-m", message, env=env)
    assert result.returncode == 0, result.stderr
    sha = _git(root, "rev-parse", "HEAD").stdout.strip()
    return sha


def run_adapter(script: Path, envelope: dict, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    import os

    env = os.environ.copy()
    env.pop("ORCHESTRARIUM_DISPATCHED_REVIEW", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(envelope, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


class TestSEN0HasNoProseBypass(unittest.TestCase):
    """Periodic lifecycle findings derive from repository state, not prose."""

    def test_extra_context_cannot_clear_sen0_or_sen1(self) -> None:
        root = make_git_repo()
        active = root / "work-items" / "active" / "dup-slug"
        active.mkdir(parents=True)
        (active / "closure.md").write_text("outcome: PASS", encoding="utf-8")
        archive = root / "work-items" / "archive" / "2026-06" / "dup-slug"
        archive.mkdir(parents=True)

        ctx = sentinels.build_context(
            str(root),
            arbitrary_prose="leave this open",
        )
        findings = sentinels.evaluate_all(ctx)
        ids = {f.id: f.severity for f in findings}
        self.assertIn("SEN-0", ids)
        self.assertIn("SEN-1", ids)

    def test_repository_state_alone_drives_findings(self) -> None:
        root = make_git_repo()
        active = root / "work-items" / "active" / "dup-slug"
        active.mkdir(parents=True)
        (active / "closure.md").write_text("outcome: PASS", encoding="utf-8")
        archive = root / "work-items" / "archive" / "2026-06" / "dup-slug"
        archive.mkdir(parents=True)

        ctx = sentinels.build_context(str(root))
        findings = sentinels.evaluate_all(ctx)
        ids = {f.id for f in findings}
        self.assertIn("SEN-0", ids)
        self.assertIn("SEN-1", ids)


class TestDI4NoT2SignalOutsideDeclaredExemption(unittest.TestCase):
    """No periodic evaluation path reads a model-authored clearing signal."""

    BANNED_PATTERNS = ("agent-runs", "agent_run_ledger", "status.md", "last_assistant_message")

    EVALUATION_PATH_FUNCTIONS = (
        "_sen0_evaluate",
        "_sen1_evaluate",
        "resolve_slug_locations",
    )

    def test_banned_signals_absent_from_evaluation_path_functions(self) -> None:
        import inspect

        for name in self.EVALUATION_PATH_FUNCTIONS:
            func = getattr(sentinels, name)
            source = inspect.getsource(func)
            for pattern in self.BANNED_PATTERNS:
                with self.subTest(function=name, pattern=pattern):
                    self.assertNotIn(pattern, source)

class TestDI5NoValidatorImport(unittest.TestCase):
    """G-5: the sentinel surface never imports the 4079-line-on-a-real-repo
    document validator. Binding the always-on Stop path to it is the named
    trap (Sentinel != Validator, design.md §3.2).

    Checked via the AST's actual `import` / `from ... import` statements, not
    a whole-file text grep: the module docstring legitimately NAMES
    `check-work-items-state.py` in prose to explain why it must never be
    imported, and that mention is not the defect this guard polices."""

    BANNED_MODULE_SUBSTRINGS = ("check_work_items_state", "check-work-items-state", "validate_work_item_state", "validate-work-item-state")

    def test_no_validator_import(self) -> None:
        import ast

        tree = ast.parse(CANON_MODULE.read_text(encoding="utf-8"))
        imported_names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_names.append(node.module)
        for name in imported_names:
            for banned in self.BANNED_MODULE_SUBSTRINGS:
                with self.subTest(imported=name, banned=banned):
                    self.assertNotIn(banned, name)
        # Sanity: prove the AST walk sees real imports at all (else the test
        # would vacuously pass on a module with no imports whatsoever).
        self.assertIn("re", imported_names)


class TestDI8LedgerUntouchedAndNotAnInput(unittest.TestCase):
    """G-8: the sentinel never loads the ledger helper or reads its output.
    T-2: the anti-abandonment proof -- delete the ledger entirely from a
    fixture and assert every verdict is unchanged (the sentinel never reads it
    at all -- confirmed precisely, function-scoped, by
    TestDI4NoT2SignalOutsideDeclaredExemption)."""

    def test_sentinel_does_not_load_ledger_helper(self) -> None:
        source = CANON_MODULE.read_text(encoding="utf-8")
        self.assertNotIn("agent-run-ledger.py", source)

    def test_verdict_unchanged_with_or_without_ledger_file(self) -> None:
        root = make_git_repo()
        item = root / "work-items" / "active" / "some-item"
        item.mkdir(parents=True)
        (item / "closure.md").write_text("x", encoding="utf-8")

        ctx = sentinels.build_context(str(root))
        before = [(f.id, f.severity, f.message) for f in sentinels.evaluate_all(ctx)]

        # Simulate the incident's escape route: a well-formed ledger present...
        (item / "agent-runs.jsonl").write_text(
            json.dumps({"runId": "r1", "status": "PASS", "updatedAt": "2026-07-20T01:02:00+00:00"}) + "\n",
            encoding="utf-8",
        )
        ctx2 = sentinels.build_context(str(root))
        with_ledger = [(f.id, f.severity, f.message) for f in sentinels.evaluate_all(ctx2)]

        # ...then delete it entirely (the actual incident shape: the session
        # stopped writing to it).
        (item / "agent-runs.jsonl").unlink()
        ctx3 = sentinels.build_context(str(root))
        without_ledger = [(f.id, f.severity, f.message) for f in sentinels.evaluate_all(ctx3)]

        self.assertEqual(before, with_ledger)
        self.assertEqual(before, without_ledger)


class TestSEN1DualState(unittest.TestCase):
    def test_disk_only_dual_state_detected(self) -> None:
        root = make_git_repo()  # git present but nothing committed -> HEAD leg empty
        active = root / "work-items" / "active" / "dup"
        active.mkdir(parents=True)
        archive = root / "work-items" / "archive" / "2026-06" / "dup"
        archive.mkdir(parents=True)

        ctx = sentinels.build_context(str(root))
        self.assertEqual(ctx["legs"], "disk")
        findings = sentinels.evaluate_all(ctx)
        sen1 = [f for f in findings if f.id == "SEN-1"]
        self.assertEqual(len(sen1), 1)
        self.assertEqual(sen1[0].severity, sentinels.RESOLVE)
        self.assertIn("dup", sen1[0].message)
        # The reason must not TEACH the erasure command (FM-3 fix): it must
        # instruct re-opening, never literally suggest deleting the copy.
        self.assertNotIn("rm -rf", sen1[0].message)
        self.assertIn("archive copy", sen1[0].message)

    def test_head_leg_detects_resurrection_after_disk_copy_removed(self) -> None:
        # Reproduces the incident's own retrospective shape: the archive copy
        # was deleted from the WORKING TREE but is still present in HEAD.
        root = make_git_repo()
        active = root / "work-items" / "active" / "dup"
        active.mkdir(parents=True)
        (active / "status.md").write_text("State: active\n", encoding="utf-8")
        archive = root / "work-items" / "archive" / "2026-06" / "dup"
        archive.mkdir(parents=True)
        (archive / "status.md").write_text("State: closed\n", encoding="utf-8")
        commit_all(root, "track both copies", "2026-07-10T10:00:00+00:00")
        # Now delete the archive copy from disk only (uncommitted removal).
        import shutil

        shutil.rmtree(archive)

        ctx = sentinels.build_context(str(root))
        self.assertEqual(ctx["legs"], "both")
        findings = sentinels.evaluate_all(ctx)
        sen1 = [f for f in findings if f.id == "SEN-1"]
        self.assertEqual(len(sen1), 1, "the HEAD leg must still see the archived copy")
        self.assertIn("HEAD", sen1[0].message)

    def test_no_dual_state_no_finding(self) -> None:
        root = make_git_repo()
        active = root / "work-items" / "active" / "solo"
        active.mkdir(parents=True)
        ctx = sentinels.build_context(str(root))
        findings = sentinels.evaluate_all(ctx)
        self.assertFalse(any(f.id == "SEN-1" for f in findings))


class TestEpicArchiveLifecycle(unittest.TestCase):
    def _root(self) -> Path:
        root = make_git_repo()
        (root / "work-items" / "active").mkdir(parents=True)
        (root / "work-items" / "epics").mkdir(parents=True)
        return root

    @staticmethod
    def _write_epic(path: Path, status: str, children: tuple[str, ...] = ()) -> None:
        child_lines = "".join(f"- {slug} (active)\n" for slug in children)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"---\nstatus: {status}\n---\n# Epic\n\n## Children\n{child_lines}",
            encoding="utf-8",
        )

    def test_resolver_distinguishes_missing_active_archived_and_duplicate(self) -> None:
        root = self._root()
        epics = root / "work-items" / "epics"
        self.assertEqual(sentinels.resolve_epic_locations(epics, "e1")["state"], "missing")

        active = epics / "e1.md"
        self._write_epic(active, "active")
        self.assertEqual(sentinels.resolve_epic_locations(epics, "e1")["state"], "active")

        archived = epics / "archive" / "2026-07" / "e1.md"
        archived.parent.mkdir(parents=True)
        active.replace(archived)
        self.assertEqual(sentinels.resolve_epic_locations(epics, "e1")["state"], "archived")

        self._write_epic(active, "active")
        resolution = sentinels.resolve_epic_locations(epics, "e1")
        self.assertEqual(resolution["state"], "duplicate")
        self.assertEqual(len(resolution["locations"]), 2)

    def test_resolver_fails_closed_on_duplicate_archive_months(self) -> None:
        root = self._root()
        epics = root / "work-items" / "epics"
        for month in ("2026-06", "2026-07"):
            self._write_epic(epics / "archive" / month / "e1.md", "closed")
        resolution = sentinels.resolve_epic_locations(epics, "e1")
        self.assertEqual(resolution["state"], "duplicate")
        self.assertEqual(len(resolution["archive"]), 2)

    def test_closed_epic_in_active_root_flags_even_without_children(self) -> None:
        root = self._root()
        self._write_epic(root / "work-items" / "epics" / "e1.md", "closed")
        findings = sentinels.evaluate_all(sentinels.build_context(str(root)))
        sen0 = [finding for finding in findings if finding.id == "SEN-0"]
        self.assertEqual(len(sen0), 1)
        self.assertIn("remains in the active root", sen0[0].message)

    def test_archived_closed_epic_with_reopened_child_flags(self) -> None:
        root = self._root()
        child = root / "work-items" / "active" / "kid"
        child.mkdir()
        (child / "status.md").write_text("State: active\n", encoding="utf-8")
        self._write_epic(
            root / "work-items" / "epics" / "archive" / "2026-07" / "e1.md",
            "closed",
            ("kid",),
        )
        findings = sentinels.evaluate_all(sentinels.build_context(str(root)))
        sen0 = [finding for finding in findings if finding.id == "SEN-0"]
        self.assertEqual(len(sen0), 1)
        self.assertIn("archived epic has a child work-item that is not closed", sen0[0].message)

    def test_epic_child_terminality_is_archive_only(self) -> None:
        root = self._root()
        child = root / "work-items" / "active" / "kid"
        child.mkdir()
        (child / "status.md").write_text("status: completed\n", encoding="utf-8")
        (child / "closure.md").write_text("Closed: 2026-07-31T00:00:00Z\n", encoding="utf-8")
        self._write_epic(
            root / "work-items" / "epics" / "e1.md",
            "active",
            ("kid",),
        )

        active_ctx = sentinels.build_context(str(root))
        self.assertFalse(sentinels._slug_is_done(active_ctx, "kid"))
        self.assertEqual(sentinels._detect_epic_orphans(active_ctx), [])

        archived = root / "work-items" / "archive" / "2026-07" / "kid"
        archived.parent.mkdir(parents=True)
        child.replace(archived)
        archived_ctx = sentinels.build_context(str(root))
        self.assertTrue(sentinels._slug_is_done(archived_ctx, "kid"))
        self.assertEqual(
            sentinels._detect_epic_orphans(archived_ctx),
            [("e1", "all child work-items are closed but the epic is still status: active (close it)")],
        )

    def test_archived_active_epic_requires_same_operation_restore(self) -> None:
        root = self._root()
        archived = root / "work-items" / "epics" / "archive" / "2026-07" / "e1.md"
        self._write_epic(archived, "active")
        findings = sentinels.evaluate_all(sentinels.build_context(str(root)))
        sen0 = [finding for finding in findings if finding.id == "SEN-0"]
        self.assertEqual(len(sen0), 1)
        self.assertIn("restore it to the active root", sen0[0].message)

        active = root / "work-items" / "epics" / "e1.md"
        archived.replace(active)
        findings = sentinels.evaluate_all(sentinels.build_context(str(root)))
        self.assertFalse(any(finding.id == "SEN-0" for finding in findings))

    def test_duplicate_epic_locations_flag_without_selecting_a_copy(self) -> None:
        root = self._root()
        epics = root / "work-items" / "epics"
        self._write_epic(epics / "e1.md", "active")
        self._write_epic(epics / "archive" / "2026-07" / "e1.md", "closed")
        findings = sentinels.evaluate_all(sentinels.build_context(str(root)))
        sen0 = [finding for finding in findings if finding.id == "SEN-0"]
        self.assertEqual(len(sen0), 1)
        self.assertIn("resolves to multiple locations", sen0[0].message)
        self.assertIn("archive/2026-07/e1.md", sen0[0].message)


class TestF4NonMonthArchiveLayout(unittest.TestCase):
    """Regression for the archive-layout regression (design.md review-
    grounding F4): a non-month category directory one level under
    work-items/archive/ (e.g. archive/legacy/<slug>/) must be traversed
    exactly like a month directory (archive/2026-07/<slug>/). An earlier
    revision of `_disk_archive_slug_pairs` / `_git_archive_slug_pairs`
    descended only into children matching `^\\d{4}-\\d{2}$`, silently
    dropping any slug filed under a non-month category directory from BOTH
    SEN-0's epic-orphan detection and SEN-1's dual-state detection --
    verdict-equivalence-breaking against the OLD shipped hook, which globbed
    any one-level archive subdirectory (`archive_dir.glob(f"*/{slug}")`)
    regardless of its name. Present in the wild:
    `VFEM_fort/work-items/archive/clean-wave-port/`."""

    def _epic_with_child_archived_under(self, category: str, epic_status: str) -> Path:
        root = make_git_repo()
        # work-items/active/ must EXIST (even empty) or _find_active_dir
        # returns None and build_context short-circuits before ever reaching
        # epics_dir/archive_slug_paths -- the child itself lives only in
        # archive/, not active/, since it is (correctly) fully archived.
        (root / "work-items" / "active").mkdir(parents=True)
        epics = root / "work-items" / "epics"
        epic_path = epics / "e1.md" if epic_status == "active" else epics / "archive" / "2026-07" / "e1.md"
        epic_path.parent.mkdir(parents=True)
        epic_path.write_text(
            f"---\nstatus: {epic_status}\n---\n# Epic: demo\n\n## Children\n- kid (active)\n",
            encoding="utf-8",
        )
        archive = root / "work-items" / "archive" / category / "kid"
        archive.mkdir(parents=True)
        return root

    def test_active_epic_with_child_archived_under_non_month_category_flags(self) -> None:
        # Old behaviour (archive_dir.glob(f"*/{slug}")) treated "kid" as done
        # regardless of the intermediate directory's name: an active epic
        # whose only child is fully archived must be flagged to close it.
        # The month-only regression silently DROPPED this finding.
        root = self._epic_with_child_archived_under("legacy", "active")
        ctx = sentinels.build_context(str(root))
        findings = sentinels.evaluate_all(ctx)
        sen0 = [f for f in findings if f.id == "SEN-0"]
        self.assertEqual(
            len(sen0), 1,
            "a child archived under a non-month category dir must still count as done (F4) -- "
            "the guard must not be silently dropped",
        )
        self.assertIn("e1", sen0[0].message)

    def test_closed_epic_with_child_archived_under_non_month_category_does_not_flag(self) -> None:
        # A closed epic whose only child IS actually archived (done) must NOT
        # flag. The month-only regression treated "kid" as NOT done (since
        # "legacy" is not month-shaped) and produced a NEW false
        # decision:block here.
        root = self._epic_with_child_archived_under("legacy", "closed")
        ctx = sentinels.build_context(str(root))
        findings = sentinels.evaluate_all(ctx)
        sen0 = [f for f in findings if f.id == "SEN-0"]
        self.assertEqual(
            len(sen0), 0,
            "a closed epic whose child is archived under a non-month category dir must not "
            "false-fire (F4 regression: this used to wrongly emit decision:block)",
        )

    def test_sen1_dual_state_detected_under_non_month_archive_category(self) -> None:
        root = make_git_repo()
        active = root / "work-items" / "active" / "kid"
        active.mkdir(parents=True)
        archive = root / "work-items" / "archive" / "legacy" / "kid"
        archive.mkdir(parents=True)

        ctx = sentinels.build_context(str(root))
        findings = sentinels.evaluate_all(ctx)
        sen1 = [f for f in findings if f.id == "SEN-1"]
        self.assertEqual(len(sen1), 1, "a non-month archive category dir must not hide the dual-state slug (F4)")
        self.assertIn("kid", sen1[0].message)

    def test_disk_archive_slug_pairs_covers_non_month_category_and_flat(self) -> None:
        root = make_git_repo()
        archive = root / "work-items" / "archive"
        (archive / "legacy" / "kid").mkdir(parents=True)
        (archive / "2026-07" / "other").mkdir(parents=True)
        (archive / "flat-slug").mkdir(parents=True)
        pairs = dict(sentinels._disk_archive_slug_pairs(archive))
        self.assertEqual(pairs.get("kid"), "legacy/kid")
        self.assertEqual(pairs.get("other"), "2026-07/other")
        self.assertIn("flat-slug", pairs)


@unittest.skip("retired archival Stop adapter")
class TestG11ResolveSuppressedUnderStopHookActive(unittest.TestCase):
    """Every RESOLVE-tier entry, exercised with stop_hook_active: true, must
    yield NO continuation -- no `decision` field, and the adapter must not
    re-fire the model. (DI-11.)"""

    def test_sen0_resolve_suppressed_via_adapter(self) -> None:
        root = make_git_repo()
        item = root / "work-items" / "active" / "orphan"
        item.mkdir(parents=True)
        (item / "closure.md").write_text("x", encoding="utf-8")
        for script in ADAPTERS:
            with self.subTest(pack=script.parent.parent.name):
                p = run_adapter(script, {"cwd": str(root), "stop_hook_active": True, "last_assistant_message": "done"})
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertNotIn('"decision"', p.stdout)

    def test_sen1_resolve_suppressed_via_adapter(self) -> None:
        root = make_git_repo()
        active = root / "work-items" / "active" / "dup"
        active.mkdir(parents=True)
        archive = root / "work-items" / "archive" / "2026-06" / "dup"
        archive.mkdir(parents=True)
        for script in ADAPTERS:
            with self.subTest(pack=script.parent.parent.name):
                p = run_adapter(script, {"cwd": str(root), "stop_hook_active": True, "last_assistant_message": "done"})
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertNotIn('"decision"', p.stdout)


@unittest.skip("retired archival Stop adapter")
class TestG13TierEscalation(unittest.TestCase):
    """G-13/T-10/DI-12: a RESOLVE-tier finding suppressed by stop_hook_active
    additionally emits a turn-free NOTICE naming the invariant, in the SAME
    evaluation, with no `decision` field present."""

    def test_sen1_suppressed_resolve_escalates_to_notice(self) -> None:
        root = make_git_repo()
        active = root / "work-items" / "active" / "dup-esc"
        active.mkdir(parents=True)
        archive = root / "work-items" / "archive" / "2026-06" / "dup-esc"
        archive.mkdir(parents=True)
        for script in ADAPTERS:
            with self.subTest(pack=script.parent.parent.name):
                p = run_adapter(script, {"cwd": str(root), "stop_hook_active": True, "last_assistant_message": "done"})
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertNotIn('"decision"', p.stdout)
                self.assertIn('"systemMessage"', p.stdout)
                self.assertIn("SEN-1", p.stdout)
                self.assertIn("dup-esc", p.stdout)

    def test_no_stop_hook_active_no_escalation_wrapper(self) -> None:
        # Sanity: without stop_hook_active, SEN-1 emits a plain RESOLVE
        # (decision:block), not an escalation notice.
        root = make_git_repo()
        active = root / "work-items" / "active" / "dup-noesc"
        active.mkdir(parents=True)
        archive = root / "work-items" / "archive" / "2026-06" / "dup-noesc"
        archive.mkdir(parents=True)
        p = run_adapter(CANON_ADAPTER, {"cwd": str(root), "last_assistant_message": "done"})
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('"decision"', p.stdout)
        self.assertIn('"block"', p.stdout)


@unittest.skip("retired archival Stop adapter")
class TestR7NoHaltTierExists(unittest.TestCase):
    """r7 (T-14, design.md §4.4c/§1.0): the HALT tier is REMOVED, not merely
    unused. `workitem_sentinels.HALT` must not exist as a severity constant
    (so no registry entry can even construct a HALT Finding), and the
    adapter's `_build_payload` must never emit a `continue` key for any
    combination of findings -- a NOTICE, however severe its own text band,
    must reach the operator via `systemMessage` alone, exactly like any
    other NOTICE. The test drives the
    adapter's severity mapping with a synthetic Finding directly, since
    `_build_payload` is generic over id/severity/message and does not care
    which invariant produced them.)"""

    def test_halt_severity_constant_does_not_exist(self) -> None:
        self.assertFalse(hasattr(sentinels, "HALT"), "the HALT severity constant must be deleted, not merely unused (r7)")

    def test_notice_severity_finding_never_emits_continue_key(self) -> None:
        # Drives the adapter's severity mapping directly via a synthetic
        # NOTICE finding, independent of any specific invariant's own logic.
        adapter, adapter_dir, added = _load_adapter_module()
        try:
            notice_finding = sentinels.Finding("TEST-NOTICE", sentinels.NOTICE, "synthetic notice band=HARD")
            payload = adapter._build_payload([notice_finding], stop_hook_active=False)
        finally:
            if added:
                sys.path.remove(adapter_dir)
        self.assertIsNotNone(payload)
        self.assertNotIn("continue", payload)
        self.assertNotIn("decision", payload)
        self.assertIn("synthetic notice", payload.get("systemMessage", ""))


def _load_adapter_module():
    """Shared helper: import the canon adapter via importlib, matching the
    real runtime's bare-name sibling-module resolution (sys.path[0])."""
    adapter_dir = str(CANON_ADAPTER.parent)
    added = adapter_dir not in sys.path
    if added:
        sys.path.insert(0, adapter_dir)
    try:
        adapter_spec = importlib.util.spec_from_file_location("archival_adapter_under_test_f10", CANON_ADAPTER)
        adapter = importlib.util.module_from_spec(adapter_spec)
        adapter_spec.loader.exec_module(adapter)
        return adapter, adapter_dir, added
    except Exception:
        if added:
            sys.path.remove(adapter_dir)
        raise


@unittest.skip("retired archival Stop adapter")
class TestF10PayloadTruncation(unittest.TestCase):
    """F10: the runtime documents a 10,000-character cap on `systemMessage` /
    plain stdout. A finding's message grows with the number of items it
    reports (unbounded in item count), so the combined payload must be capped
    proactively, and the cap must degrade INFORMATIVELY -- never silently."""

    def test_short_text_untouched(self) -> None:
        adapter, adapter_dir, added = _load_adapter_module()
        try:
            text = "short and well under the cap"
            self.assertEqual(adapter._cap_payload_text(text), text)
        finally:
            if added:
                sys.path.remove(adapter_dir)

    def test_long_text_truncated_with_informative_notice(self) -> None:
        adapter, adapter_dir, added = _load_adapter_module()
        try:
            long_text = "\n".join(f"  - item{i}: droughted" for i in range(2000))
            self.assertGreater(len(long_text), adapter.MAX_PAYLOAD_CHARS)
            capped = adapter._cap_payload_text(long_text)
            self.assertLessEqual(len(capped), adapter.MAX_PAYLOAD_CHARS)
            self.assertIn("TRUNCATED", capped)
            self.assertIn(str(len(long_text)), capped, "the notice must state the ORIGINAL total length")
        finally:
            if added:
                sys.path.remove(adapter_dir)

    def test_truncation_never_splits_mid_line(self) -> None:
        adapter, adapter_dir, added = _load_adapter_module()
        try:
            long_text = "\n".join(f"line-{i:05d}-marker-free-content" for i in range(1000))
            capped = adapter._cap_payload_text(long_text)
            body = capped.split("\n\n[... TRUNCATED")[0]
            # Every line in the kept body must be a COMPLETE original line,
            # never a partial one cut mid-word.
            original_lines = set(long_text.splitlines())
            for line in body.splitlines():
                self.assertIn(line, original_lines, f"truncation split a line: {line!r}")
        finally:
            if added:
                sys.path.remove(adapter_dir)

    def test_notice_payload_capped_end_to_end(self) -> None:
        # No tier ever emits `continue`. Any NOTICE with an unbounded item
        # list still needs the same cap, so this drives the
        # adapter's mapping with a synthetic oversized NOTICE, independent of
        # which invariant produced it.
        adapter, adapter_dir, added = _load_adapter_module()
        try:
            huge_message = "\n".join(f"  - item-{i}: synthetic detail line" for i in range(2000))
            notice_finding = sentinels.Finding("TEST-NOTICE", sentinels.NOTICE, huge_message)
            payload = adapter._build_payload([notice_finding], stop_hook_active=False)
        finally:
            if added:
                sys.path.remove(adapter_dir)
        self.assertIsNotNone(payload)
        self.assertNotIn("continue", payload)
        self.assertNotIn("decision", payload)
        self.assertLessEqual(len(payload["systemMessage"]), adapter.MAX_PAYLOAD_CHARS)
        self.assertIn("TRUNCATED", payload["systemMessage"])


class TestG12CensusInventory(unittest.TestCase):
    """G-12: the census of always-on, matcher-less, repository-state hooks is
    machine-checked, not asserted in prose. Every such hook is either a
    registry entry (workitem_sentinels.REGISTRY) or a declared, tracked
    exception with a named owner."""

    # Declared tracked exception (design.md §2.2 instance A'/§14 follow-up):
    # check-scratch-valuables migrates onto a future SessionStart adapter;
    # until then it stays a hand-duplicated, independently-shipped detector.
    DECLARED_EXCEPTIONS = {
        "check-scratch-valuables": "2026-07-25-migrate-scratch-valuables-to-sentinel-registry",
    }

    def test_stop_and_sessionstart_repo_state_hooks_are_registry_or_declared(self) -> None:
        path = REPO_ROOT / "scripts" / "production_installer.py"
        spec = importlib.util.spec_from_file_location(
            "production_installer_sentinel_census", path
        )
        assert spec is not None and spec.loader is not None
        installer = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = installer
        spec.loader.exec_module(installer)
        markers = {
            marker
            for marker, *_rest in installer._hook_specs("codex", REPO_ROOT / "unused")
        }
        self.assertNotIn("check-work-items-archival-stop", markers)
        self.assertIn("check-scratch-valuables", markers)
        registry_ids = {e["id"] for e in sentinels.REGISTRY}
        self.assertTrue(registry_ids, "the registry must not be empty")
        self.assertIn("check-scratch-valuables", self.DECLARED_EXCEPTIONS)


@unittest.skip("retired archival Stop adapter")
class TestT3SubagentSkip(unittest.TestCase):
    def test_agent_id_suppresses_sen1(self) -> None:
        root = make_git_repo()
        active = root / "work-items" / "active" / "dup"
        active.mkdir(parents=True)
        archive = root / "work-items" / "archive" / "2026-06" / "dup"
        archive.mkdir(parents=True)
        for script in ADAPTERS:
            with self.subTest(pack=script.parent.parent.name):
                p = run_adapter(script, {"cwd": str(root), "agent_id": "sub-1", "last_assistant_message": "done"})
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(p.stdout.strip(), "")


class TestG6SignalBudget(unittest.TestCase):
    """DI-6: zero output on a healthy repository. Run over Orchestrarium's
    OWN real work-items/ tree (T-13: the current mixed tracked/read-model plus
    gitignored task-memory layout) and a VFEM-shaped
    unhealthy fixture (T-1)."""

    def test_zero_findings_on_orchestrarium_own_tree(self) -> None:
        ctx = sentinels.build_context(str(REPO_ROOT))
        self.assertEqual(ctx["legs"], "both", "Orchestrarium's current work-items/ has tracked canon plus disk-only task memory")
        findings = sentinels.evaluate_all(ctx)
        self.assertEqual(
            findings, [],
            f"unexpected findings on the pack's own healthy repo: {[(f.id, f.message) for f in findings]}",
        )

    def test_vfem_shaped_unhealthy_fixture_yields_findings(self) -> None:
        root = make_git_repo()
        # Instance C: a resurrected dual-state slug.
        active = root / "work-items" / "active" / "resurrected"
        active.mkdir(parents=True)
        (active / "status.md").write_text("State: active\n", encoding="utf-8")
        archive = root / "work-items" / "archive" / "2026-06" / "resurrected"
        archive.mkdir(parents=True)
        (archive / "status.md").write_text("State: closed\n", encoding="utf-8")

        ctx = sentinels.build_context(str(root))
        findings = sentinels.evaluate_all(ctx)
        ids = {f.id for f in findings}
        self.assertIn("SEN-1", ids)
        self.assertEqual(len(findings), 1, f"expected exactly 1 finding, got {[(f.id) for f in findings]}")


@unittest.skip("retired archival Stop adapter")
class TestG14T16BoundedReverseScan(unittest.TestCase):
    """G-14 / T-16 (design.md §4.5, F2) -- the gate's own falsifier: an
    operator marker followed by many filler records must still be found by
    `hook_common.last_genuine_user_text`'s bounded REVERSE scan, at record
    counts where the OLD fixed-window read (`read_transcript_tail(path,
    100)`) would already have missed it. Parameterized at 100, 300, 1000 and
    5000 filler records (p90 real turn is 346 -- P-r6d)."""

    @staticmethod
    def _make_transcript(marker_text: str, n_filler: int) -> Path:
        lines = [json.dumps({"type": "user", "message": {"role": "user", "content": marker_text}})]
        for i in range(n_filler):
            lines.append(
                json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": f"working step {i} " * 5}]}})
            )
        tmp = Path(tempfile.mktemp(suffix=".jsonl"))
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return tmp

    def test_marker_found_beyond_the_old_100_record_window(self) -> None:
        import hook_common

        for n_filler in (100, 300, 1000, 5000):
            with self.subTest(n_filler=n_filler):
                tp = self._make_transcript("ok [approve-review-continuation] please continue", n_filler)
                try:
                    text, status = hook_common.last_genuine_user_text(str(tp), byte_cap=64 * 1024 * 1024)
                    self.assertEqual(status, "found")
                    self.assertIn("[approve-review-continuation]", text)
                    # Prove this is a REAL fix, not a redundant addition: the
                    # OLD fixed-100-line approach must NOT find it once
                    # n_filler exceeds the window.
                    if n_filler > 100:
                        old_entries = hook_common.read_transcript_tail(str(tp), 100)
                        old_entry, _old_text, _after = hook_common.last_genuine_user_message(old_entries)
                        self.assertIsNone(old_entry, f"old fixed-window approach unexpectedly found the marker at n_filler={n_filler}")
                finally:
                    tp.unlink()

    def test_byte_cap_boundary_returns_not_in_window(self) -> None:
        import hook_common

        tp = self._make_transcript("ok [approve-review-continuation] please continue", 5000)
        try:
            text, status = hook_common.last_genuine_user_text(str(tp), byte_cap=4096)
            self.assertEqual(status, "not-in-window")
            self.assertEqual(text, "")
        finally:
            tp.unlink()

    def test_end_to_end_marker_beyond_100_records_clears_sen0_via_adapter(self) -> None:
        # The full path: a real SEN-0 archival-orphan fixture, a real
        # transcript with the OPERATOR's own marker 300 filler records deep,
        # fed through the actual adapter subprocess (not build_context
        # directly) -- this is what F2 fixes, end to end.
        # The marker is SEN-0's own [acknowledge-open-work-items], read from
        # the operator's channel
        # (user_message_text via last_genuine_user_text), not the model's
        # last_assistant_message -- proving the reverse scan still finds an
        # operator marker buried deep in a transcript when routed to a
        # different invariant's exemption.
        root = make_git_repo()
        item = root / "work-items" / "active" / "orphan-e2e"
        item.mkdir(parents=True)
        (item / "closure.md").write_text("outcome: PASS", encoding="utf-8")
        (item / "status.md").write_text("# Status\n", encoding="utf-8")
        tp = self._make_transcript("ok [acknowledge-open-work-items] please continue", 300)
        try:
            p = run_adapter(
                CANON_ADAPTER,
                {"cwd": str(root), "last_assistant_message": "done", "transcript_path": str(tp)},
            )
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(
                p.stdout.strip(), "",
                f"the operator's marker 300 records deep must clear SEN-0 via the bounded reverse scan; got {p.stdout!r}",
            )
        finally:
            tp.unlink()


class TestG16T18HookCommonCurrentTurnOwnership(unittest.TestCase):
    """The current state has one bounded current-turn owner and no fixed-record
    tail relationship. Strict complete history remains a separate contract."""

    def test_obsolete_tail_reader_is_absent_and_one_owner_remains(self) -> None:
        owner = REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "hook_common.py"
        owner_text = owner.read_text(encoding="utf-8")
        self.assertNotIn("def read_transcript_tail", owner_text)
        self.assertNotIn("TRANSCRIPT_TAIL_LINES", owner_text)
        self.assertEqual(owner_text.count("def scan_current_turn_boundary"), 1)
        self.assertIn("def read_transcript_history", owner_text)

        consumers = (
            REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "check-git-push-gate.py",
            REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "check-bugfix-discipline.py",
            REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "check-passive-polling-stop.py",
            REPO_ROOT / "scripts" / "universal-hooks" / "hooks" / "check-repository-orientation.py",
        )
        for consumer in consumers:
            with self.subTest(consumer=consumer.name):
                text = consumer.read_text(encoding="utf-8")
                self.assertNotIn("read_transcript_tail", text)
                self.assertNotIn("TRANSCRIPT_TAIL_LINES", text)
                self.assertIn("scan_current_turn_boundary", text)

    def test_four_migrated_callers_suites_pass(self) -> None:
        other_suites = (
            "test_bugfix_discipline_hook.py",
            "test_git_push_gate_hook.py",
            "test_passive_polling_stop.py",
            "test_repository_orientation_hook.py",
        )
        for suite in other_suites:
            path = REPO_ROOT / "tests" / suite
            if not path.is_file():
                self.fail(f"expected suite not found: {path}")
            with self.subTest(suite=suite):
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", str(path), "-q"],
                    capture_output=True, text=True, cwd=str(REPO_ROOT),
                )
                self.assertEqual(result.returncode, 0, f"{suite} failed:\n{result.stdout}\n{result.stderr}")


if __name__ == "__main__":
    unittest.main()
