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
                     for path in (b"z/real", b"a/real")
                     for blob in ("b2", "b1")]
        for row in inventory:
            assert index.add(row, "100644")
        assert not index.add(inventory[0], "100755")
        assert index.subject_count == len(inventory)
        query = "SELECT name FROM sqlite_master WHERE name='subject_path'"
        assert db.execute(query).fetchall() == []
        index.prepare_path_queries()
        assert db.execute(query).fetchall() == [("subject_path",)]
        assert list(index.path_pairs()) == sorted({r[1:] for r in inventory})
        assert list(index.owners(b"a/real", "b1")) == [("c1", "100644"), ("c2", "100644")]
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
