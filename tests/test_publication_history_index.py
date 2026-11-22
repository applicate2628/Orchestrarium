"""The publication coverage inventory does not depend on index build order."""
from contextlib import closing
from pathlib import Path
import runpy
import sqlite3


ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "scripts/universal-hooks/scripts/check-publication-safety.py"


def test_path_query_index_is_built_after_admission_without_changing_coverage():
    scanner = runpy.run_path(str(SCANNER))
    with closing(sqlite3.connect("")) as db:
        index = scanner["_HistoryIndex"](db)
        inventory = [(owner, path, blob) for owner in ("c2", "c1")
                     for path in (b"z/real", b"a/real", b"A/real", b"\xff/real")
                     for blob in ("b2", "b1")]
        for row in inventory:
            assert index.add(row, "100644")
        assert not index.add(inventory[0], "100755")
        assert index.subject_count == len(inventory)
        query = "SELECT name FROM sqlite_master WHERE name='subject_path'"
        assert db.execute(query).fetchall() == []
        assert db.execute("SELECT DISTINCT typeof(path) FROM subject").fetchall() == [("blob",)]
        index.prepare_path_queries()
        assert db.execute(query).fetchall() == [("subject_path",)]
        assert list(index.path_pairs()) == sorted({r[1:] for r in inventory})
        assert list(index.owners(b"a/real", "b1")) == [("c1", "100644", False), ("c2", "100644", False)]
        subjects, paths = index.seal()
        assert len(subjects) == len(inventory)
        assert len(paths) == len(set(r[1:] for r in inventory))
        assert subjects.digest == scanner["_subject_set_digest"](sorted(inventory))
        assert paths.digest == scanner["_path_set_digest"](sorted({(r[2], r[1]) for r in inventory}))



def test_deferred_index_remains_subject_to_the_existing_sqlite_deadline():
    import pytest

    scanner = runpy.run_path(str(SCANNER))
    with closing(sqlite3.connect("")) as db:
        index = scanner["_HistoryIndex"](db)
        for i in range(100):
            assert index.add((f"{i:040x}", f"file-{i}".encode(), f"{i:040x}"), "100644")
        db.set_progress_handler(lambda: 1, 1)
        with pytest.raises(sqlite3.OperationalError, match="interrupted"):
            index.prepare_path_queries()
        db.set_progress_handler(None, 0)
        assert db.execute("SELECT name FROM sqlite_master WHERE name='subject_path'").fetchone() is None


def test_coverage_seal_preserves_scan_order_and_v1_bytes():
    import hashlib

    scanner = runpy.run_path(str(SCANNER))
    a, b = "a" * 40, "b" * 40
    for expected, scanned in [((), ()), ((a,), (a,)), ((a, b), (b, a))]:
        proof = scanner["_build_coverage_proof"](
            iter(expected), iter(expected), iter(reversed(expected)), iter(scanned),
            allow_empty=True,
        )
        assert proof.scanned_message_oids == scanned
        assert proof.coverage_digest == hashlib.sha256(
            b"publication-safety-coverage-v1\0" + b"\0".join(oid.encode("ascii") for oid in scanned)
        ).hexdigest()
        counters = (
            proof.expected_counter, proof.requested_counter,
            proof.acquired_counter, proof.scanned_counter,
        )
        assert all(rows == tuple((oid, 1) for oid in sorted(expected)) for rows in counters)
        assert all(rows is counters[0] for rows in counters)


def test_blob_inventory_separates_identity_from_path_coverage():
    scanner = runpy.run_path(str(SCANNER))
    with closing(sqlite3.connect("")) as db:
        index = scanner["_HistoryIndex"](db)
        index.add_blob("b2", 24, b"binary-digest", True)
        index.add_blob("b1", 18, b"text-digest", False)
        assert index.blob_count == 2
        assert index.blob_record("b1") == (18, b"text-digest", False)
        assert index.blob_record("b2") == (24, b"binary-digest", True)
        assert list(index.recorded_blob_ids()) == ["b1", "b2"]
        assert not index.blob_coverage_complete()
        index.add(("c1", b"second", "b2"), "100644")
        assert not index.blob_coverage_complete()
        index.add(("c1", b"first", "b1"), "100644")
        index.add(("c2", b"other", "b1"), "100755")
        assert index.blob_coverage_complete()
        index.add(("c1", b"foreign", "b3"), "100644")
        assert not index.blob_coverage_complete()


def test_selection_inventory_preserves_order_and_rejects_duplicate_rows():
    scanner = runpy.run_path(str(SCANNER))
    with closing(sqlite3.connect("")) as db:
        index = scanner["_HistoryIndex"](db)
        assert index.add_selected_commit("c2", ("c1", "c0"))
        assert index.add_selected_commit("c1", ())
        assert not index.add_selected_commit("c2", ("different",))
        assert index.add_selected_object("c1")
        assert index.add_selected_object("blob")
        assert not index.add_selected_object("blob")
        assert not index.selected_commits_covered()
        assert index.add_selected_object("c2")
        assert index.selected_commits_covered()
        assert tuple(index.selected_commits()) == (("c2", ("c1", "c0")), ("c1", ()))
        assert tuple(index.selected_objects()) == ("c1", "blob", "c2")


def test_multiple_git_streams_keep_first_commit_order_and_last_parent_view():
    scanner = runpy.run_path(str(SCANNER))
    with closing(sqlite3.connect("")) as db:
        index = scanner["_HistoryIndex"](db)
        assert index.add_selected_commit("top", ("old",), stream=1)
        assert index.add_selected_commit("old", (), stream=1)
        assert index.add_selected_object("top", stream=1)
        assert index.add_selected_object("old", stream=1)
        assert index.add_selected_object("blob-z", stream=1)
        assert index.add_selected_commit("other", ("old",), stream=2)
        assert index.add_selected_commit("top", ("new", "old"), stream=2)
        assert not index.add_selected_commit("top", (), stream=2)
        assert index.add_selected_object("top", stream=2)
        assert not index.add_selected_object("top", stream=2)
        assert index.add_selected_object("other", stream=2)
        assert index.add_selected_object("blob-a", stream=2)
        assert tuple(index.selected_commits()) == (
            ("top", ("new", "old")), ("old", ()), ("other", ("old",)),
        )
        assert tuple(index.selected_objects()) == ("top", "old", "blob-z", "other", "blob-a")
        assert tuple(index.selected_objects(sorted_ids=True)) == ("blob-a", "blob-z", "old", "other", "top")
        assert index.selected_commits_covered()


def test_indexed_coverage_preserves_events_and_duplicate_refusal():
    scanner = runpy.run_path(str(SCANNER))
    with closing(sqlite3.connect("")) as db:
        index = scanner["_HistoryIndex"](db)
        event = scanner["CoverageEvent"]
        expected = ("a" * 40, "b" * 40)
        expected_events = tuple((stage, oid) for oid in reversed(expected) for stage in event)
        observed = []
        record = scanner["CoverageRecorder"](
            expected, lambda stage, oid: observed.append((stage, oid)), history_index=index,
        )
        for stage, oid in expected_events:
            record.record(stage, oid)
        assert tuple(observed) == expected_events
        assert record.proof().scanned_message_oids == tuple(reversed(expected))
        assert tuple(index.coverage_events(event.SCANNED)) == tuple(reversed(expected))
        record.record(event.SCANNED, expected[0])
        assert record.proof().failure_id == "PS-MSG-COVERAGE"
        assert tuple(index.coverage_events(event.SCANNED)) == (*reversed(expected), expected[0])


def test_receipt_coverage_matches_legacy_digest_and_rejects_missing_extra_or_duplicate():
    scanner = runpy.run_path(str(SCANNER))
    a, b, outside = ("a" * 40, "b" * 40, "c" * 40)
    event = scanner["CoverageEvent"]
    for damaged_stage in event:
        for damaged in (None, (a,), (b, a, outside), (b, a, a), (b, outside)):
            with closing(sqlite3.connect("")) as db:
                index = scanner["_HistoryIndex"](db)
                assert index.add_selected_object(a)
                assert index.add_selected_object(b)
                for stage in event:
                    rows = damaged if stage is damaged_stage and damaged is not None else (b, a)
                    for oid in rows:
                        index.record_coverage(stage, oid)
                proof = index.seal_receipt_coverage((a, b))
                if damaged is None:
                    legacy = scanner["_build_coverage_proof"]((a, b), (b, a), (b, a), (b, a))
                    assert proof.coverage_digest == legacy.coverage_digest
                    assert proof.expected_count == 2
                    assert proof.selection_set == scanner["_oid_set_digest"](b"object-set", (a, b))
                    assert index.seal_receipt_coverage((b, a)).failure_id == "PS-MSG-COVERAGE"
                else:
                    assert proof.failure_id == "PS-MSG-COVERAGE"
    with closing(sqlite3.connect("")) as db:
        index = scanner["_HistoryIndex"](db)
        assert index.seal_receipt_coverage(()).failure_id == "PS-MSG-COVERAGE"
        assert index.add_selected_object(a)
        for stage in event:
            index.record_coverage(stage, a)
        assert index.seal_receipt_coverage((a, a)).failure_id == "PS-MSG-COVERAGE"


def test_acquired_kind_keeps_actual_order_and_exact_tree_reachability():
    scanner = runpy.run_path(str(SCANNER))
    with closing(sqlite3.connect("")) as db:
        index = scanner["_HistoryIndex"](db)
        for oid in ("tree", "blob", "commit", "other-tree"):
            assert index.add_selected_object(oid)
        assert not index.record_acquired("unselected", "tree", 0)
        assert index.record_acquired("commit", "commit", 0)
        assert not index.record_acquired("commit", "tree", 1)
        assert index.record_acquired("blob", "blob", 1)
        assert index.record_acquired("tree", "tree", 2)
        assert index.record_acquired("other-tree", "tree", 3)
        assert tuple(index.acquired_oids()) == ("commit", "blob", "tree", "other-tree")
        assert tuple(index.acquired_oids(deferred=True)) == ("blob", "tree", "other-tree")
        assert index.acquired_kind("tree") == "tree"
        assert index.acquired_kind("unselected") is None
        assert not index.record_reached_tree("commit")
        assert not index.record_reached_tree("unselected")
        assert index.record_reached_tree("tree")
        assert index.record_reached_tree("tree")
        assert not index.tree_coverage_complete()
        assert index.record_reached_tree("other-tree")
        assert index.tree_coverage_complete()


def test_commit_roots_preserve_selection_order_and_graph_comparison():
    scanner = runpy.run_path(str(SCANNER))
    with closing(sqlite3.connect("")) as db:
        index = scanner["_HistoryIndex"](db)
        assert index.add_selected_commit("newer", ("second", "first"))
        assert index.add_selected_commit("older", ())
        assert index.record_commit_root("older", "root-a", ())
        assert not index.record_commit_root("older", "root-b", ())
        assert not index.record_commit_root("outside", "ignored", ())
        assert index.commit_coverage_problem(check_parents=True) == "commit-set"
        assert index.record_commit_root("newer", "root-b", ("first", "second"))
        assert index.commit_coverage_problem(check_parents=True) == "parent-graph"
        assert index.commit_coverage_problem(check_parents=False) is None
        assert tuple(index.commit_roots()) == (("newer", "root-b"), ("older", "root-a"))
    with closing(sqlite3.connect("")) as db:
        index = scanner["_HistoryIndex"](db)
        assert index.add_selected_commit("legacy", None)
        assert index.record_commit_root("legacy", "root", ())
        assert index.commit_coverage_problem(check_parents=True) == "parent-graph-set"
        assert index.commit_coverage_problem(check_parents=False) is None


def test_standalone_commit_parent_seed_matches_graph_set_contract():
    from types import SimpleNamespace

    scanner = runpy.run_path(str(SCANNER))
    for expected, problem in (
        ((("a", ("earlier",)), ("a", ()), ("b", ())), None),
        ((("a", ()),), "parent-graph-set"),
        ((("a", ()), ("b", ()), ("outside", ())), "parent-graph-set"),
    ):
        with closing(sqlite3.connect("")) as db:
            index = scanner["_HistoryIndex"](db)
            selection = SimpleNamespace(expected_oids=("b", "a"), expected_parents=expected)
            assert index.seed_standalone_commits(selection)
            assert index.record_commit_root("a", "root-a", ())
            assert index.record_commit_root("b", "root-b", ())
            assert index.commit_coverage_problem(check_parents=True) == problem
            assert tuple(index.commit_roots()) == (("b", "root-b"), ("a", "root-a"))


def test_index_returns_typed_targets_and_path_owners_in_existing_orders():
    scanner = runpy.run_path(str(SCANNER))
    with closing(sqlite3.connect("")) as db:
        index = scanner["_HistoryIndex"](db)
        assert index.add_selected_object("z-commit")
        assert index.add_selected_object("a-blob")
        assert index.add_selected_commit("z-commit", ())
        assert tuple(index.acquisition_targets()) == (("z-commit", True), ("a-blob", False))
        assert tuple(index.acquisition_targets(lexical=True)) == (("a-blob", False), ("z-commit", True))
        assert index.add(("z-commit", b"path", "a-blob"), "100644")
        assert index.add(("tag-direct", b"path", "a-blob"), "")
        index.prepare_path_queries()
        assert tuple(index.owners(b"path", "a-blob")) == (
            ("tag-direct", "", False), ("z-commit", "100644", True),
        )


def test_typed_target_pages_preserve_membership_while_acquisition_updates_rows():
    scanner = runpy.run_path(str(SCANNER))
    expected = tuple(f"{oid:040x}" for oid in range(1, 1027))
    with closing(sqlite3.connect("")) as db:
        index = scanner["_HistoryIndex"](db)
        for oid in reversed(expected):
            assert index.add_selected_object(oid)
        for oid in expected[::2]:
            assert index.add_selected_commit(oid, ())
        observed = []
        for ordinal, (oid, is_commit) in enumerate(index.acquisition_targets(lexical=True)):
            assert is_commit == (ordinal % 2 == 0)
            assert index.record_acquired(oid, "commit" if is_commit else "blob", ordinal)
            observed.append(oid)
        assert tuple(observed) == expected
        assert tuple(index.acquired_oids()) == expected
