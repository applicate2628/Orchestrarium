"""Pure _moved metadata receiving tests; no installer import or native effects."""
import ast
import contextlib
import copy
import dataclasses
from pathlib import Path
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/production_installer.py"

@dataclasses.dataclass(frozen=True)
class Metadata:
    value: str

def load(path):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "_InstallTransaction")
    method = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == "_moved")
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        method], type_ignores=[])
    namespace = dict(replace=dataclasses.replace, os=types.SimpleNamespace())
    exec(compile(ast.fix_missing_locations(module), "<moved-only>", "exec"), namespace)
    return namespace["_moved"], namespace["os"]

def fixture(method, os_stub, failure=None):
    tx = types.SimpleNamespace()
    source, target = Path("source"), Path("target")
    a, b = source / "a", source / "b"
    da, db, other = target / "a", target / "b", Path("untouched")
    shared = types.SimpleNamespace(current=Metadata("shared"))
    untouched = types.SimpleNamespace(current=Metadata("untouched"))
    # Aliased source/destination participant preserves ordered last-write semantics.
    tx._copy_metadata = {a: shared, da: shared, db: types.SimpleNamespace(current=Metadata("b")), other: untouched}
    tx._copy_current = {a: Metadata("old-a"), b: Metadata("old-b"), other: untouched.current}
    tx._entries = [{"kind": "scalar", "current_path": a, "links": ((b, "link-node"),), "operation_backup": b}]
    tx._effects = [types.SimpleNamespace(location=a, current_path=None, actual={a: "a-node"},
        restored_state={a: "a-node"}, retained=b, retained_state={b: "b-node"},
        quarantine=None, quarantine_state=None, prepared_path=None, prepared_state=None,
        reservation_state={b: "b-node"}, retention_parent=source)]
    tx._migration_retention = {source: (Path("."), "parent-id", "directory-id", "owner")}
    tx._slice_a_created = []
    tx._slice_a_migrated = []
    tx._transition_order = 7
    trace = []
    error = OSError("observation failure")
    tx._relocate = lambda image, old, new: {new / p.relative_to(old): node for p, node in image.items()}
    def hit(stage, path):
        trace.append((stage, str(path)))
        if failure == (stage, path):
            raise error
    @contextlib.contextmanager
    def reference(path, node):
        hit("enter", path)
        try:
            yield path, node
        finally:
            hit("exit", path)
    tx._copy_reference = reference
    def fstat(descriptor):
        hit("fstat", descriptor)
        return descriptor
    os_stub.fstat = fstat
    def read(metadata, descriptor, bound):
        hit("read", descriptor)
        return Metadata(str(descriptor))
    tx._read_copy_metadata = read
    tx._advance = lambda path, state, exclude: trace.append(("advance", str(path), state))
    invoke = lambda: method(tx, source, target, {a: "a-node", b: "b-node"}, None)
    return tx, trace, error, invoke

def journal(tx):
    return copy.deepcopy({key: value for key, value in vars(tx).items()
                          if not callable(value)})

class MovedTests(unittest.TestCase):
    def failure(self, stage, path):
        method, stub = load(SOURCE)
        tx, trace, error, invoke = fixture(method, stub, (stage, path))
        before = journal(tx)
        current = tx._copy_current
        participants = [(p, p.current) for p in tx._copy_metadata.values()]
        with self.assertRaises(OSError) as caught:
            invoke()
        self.assertIs(caught.exception, error)
        self.assertIs(tx._copy_current, current)
        for participant, metadata in participants:
            self.assertIs(participant.current, metadata)
        self.assertEqual(journal(tx), before)
        self.assertFalse(any(row[0] == "advance" for row in trace))

    def test_reference_enter_failure(self):
        self.failure("enter", Path("target/a"))
    def test_fstat_failure(self):
        self.failure("fstat", Path("target/a"))
    def test_metadata_failure(self):
        self.failure("read", Path("target/a"))
    def test_reference_exit_failure(self):
        self.failure("exit", Path("target/a"))
    def test_second_metadata_failure(self):
        self.failure("read", Path("target/b"))
    def test_migration_reservation_state_relocates(self):
        method, stub = load(SOURCE)
        tx, _, _, invoke = fixture(method, stub)
        Record = dataclasses.make_dataclass("Record", [
            "leaf_path", "parent_path", "tombstone_path", "retention_parent_path",
            "prepared_path", "logical_leaf_path", "reservation_state"])
        original = Record(Path("source/a"), Path("source"), Path("source/retained"),
            Path("source"), Path("source/prepared"), None,
            {Path("source/retained"): "reservation"})
        tx._slice_a_migrated = [original]
        invoke()
        moved = tx._slice_a_migrated[0]
        self.assertEqual(moved.leaf_path, Path("target/a"))
        self.assertEqual(moved.logical_leaf_path, Path("source/a"))
        self.assertEqual(moved.reservation_state, {Path("target/retained"): "reservation"})
        self.assertEqual(original.reservation_state, {Path("source/retained"): "reservation"})

    def test_success_preserves_order_and_expected_journals(self):
        method, stub = load(SOURCE)
        tx, trace, _, invoke = fixture(method, stub)
        untouched = tx._copy_metadata[Path("untouched")].current
        invoke()
        target_a, target_b = Path("target/a"), Path("target/b")
        expected_trace = [(stage, str(path)) for path in (target_a, target_b)
                          for stage in ("enter", "fstat", "read", "exit")]
        expected_trace.extend([
            ("advance", str(Path("source")), {}),
            ("advance", str(Path("target")), {target_a: "a-node", target_b: "b-node"}),
        ])
        self.assertEqual(trace, expected_trace)
        self.assertEqual(list(tx._copy_current), [target_a, target_b, Path("untouched")])
        self.assertEqual(tx._copy_current, {
            target_a: Metadata(str(target_a)), target_b: Metadata(str(target_b)),
            Path("untouched"): untouched,
        })
        self.assertIs(tx._copy_metadata[Path("source/a")], tx._copy_metadata[target_a])
        self.assertEqual(tx._copy_metadata[target_a].current, Metadata(str(target_a)))
        self.assertEqual(tx._copy_metadata[target_b].current, Metadata(str(target_b)))
        self.assertIs(tx._copy_metadata[Path("untouched")].current, untouched)
        self.assertEqual(tx._entries, [{"kind": "scalar", "current_path": target_a,
            "links": ((target_b, "link-node"),), "operation_backup": target_b}])
        effect = tx._effects[0]
        self.assertEqual(effect.current_path, target_a)
        self.assertEqual(effect.actual, {target_a: "a-node"})
        self.assertEqual(effect.restored_state, {target_a: "a-node"})
        self.assertEqual(effect.retained, target_b)
        self.assertEqual(effect.retained_state, {target_b: "b-node"})
        self.assertEqual(effect.reservation_state, {target_b: "b-node"})
        self.assertEqual(effect.retention_parent, Path("target"))
        self.assertIsNone(effect.quarantine)
        self.assertIsNone(effect.quarantine_state)
        self.assertIsNone(effect.prepared_path)
        self.assertIsNone(effect.prepared_state)
        self.assertEqual(tx._migration_retention,
            {Path("target"): (Path("."), "parent-id", "directory-id", "owner")})
        self.assertEqual(tx._slice_a_created, [])
        self.assertEqual(tx._slice_a_migrated, [])
        self.assertEqual(tx._transition_order, 7)

if __name__ == "__main__":
    unittest.main()
