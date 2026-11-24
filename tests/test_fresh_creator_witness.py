"""Memory-only creator-provenance tests; not physical installer acceptance."""
import ast
from dataclasses import dataclass, FrozenInstanceError
from pathlib import Path, PurePosixPath
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "production_installer.py"


class FreshCreatorWitnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(SOURCE.read_bytes())
        owner = next(n for n in cls.tree.body if isinstance(n, ast.ClassDef)
                     and n.name == "_CreateOnlyMutablePath")
        names = {"_fresh_file_parents", "_file_parent_identities",
                 "_assert_fresh_file", "_assert_bound_file", "_record_fresh_file"}
        methods = [n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name in names]
        if {n.name for n in methods} != names:
            raise AssertionError("Missing creator provenance methods")
        witness = next(n for n in cls.tree.body if isinstance(n, ast.ClassDef)
                       and n.name == "_FreshFileWitness")
        shell = ast.ClassDef(name="MemoryOwner", bases=[], keywords=[], body=methods,
                             decorator_list=[])
        module = ast.fix_missing_locations(ast.Module(body=[
            ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
            witness, shell], type_ignores=[]))
        scope = {"dataclass": dataclass, "stat": stat}
        exec(compile(module, "isolated-creator-provenance", "exec"), scope)
        cls.Owner = scope["MemoryOwner"]
        cls.Witness = scope["_FreshFileWitness"]

    def setUp(self):
        self.owner = self.Owner()
        self.owner.anchor = PurePosixPath("root")
        self.path = self.owner.anchor / "payload" / "item"
        self.identity = (1, 2, stat.S_IFDIR | 0o755, 4)
        self.owner._anchor_identity = self.identity
        self.owner._identity = Mock(return_value=self.identity)
        self.owner.destination = Mock(side_effect=lambda p: self.owner.anchor / p)
        self.owner.dry_run = False
        self.owner.linked_authority = None
        self.owner.transaction = SimpleNamespace(
            enabled=True, _track_fresh_files=True, _original={}, _fresh_files=[],
            _binding_identity_matches=lambda a, b: a == b,
            _image_file_bytes=Mock(return_value=b"payload"))
        self.node = SimpleNamespace(kind="file")
        self.parents = ((self.path.parent, self.identity),
                        (self.owner.anchor, self.identity))

    def test_capture_records_parent_chain_and_validates_anchor(self):
        self.assertEqual(self.owner._fresh_file_parents(self.path), self.parents)
        self.owner.destination.assert_called_once_with(self.path.relative_to(self.owner.anchor))

    def test_tracking_exclusions_do_not_observe_parents(self):
        for target, name, value in (
            (self.owner, "dry_run", True),
            (self.owner.transaction, "enabled", False),
            (self.owner.transaction, "_track_fresh_files", False),
            (self.owner, "linked_authority", object()),
            (self.owner.transaction, "_original", {"snapshot": {self.path: self.node}}),
        ):
            with self.subTest(name=name):
                previous = getattr(target, name)
                setattr(target, name, value)
                self.owner._identity.reset_mock()
                self.assertIsNone(self.owner._fresh_file_parents(self.path))
                self.owner._identity.assert_not_called()
                setattr(target, name, previous)

    def test_anchor_drift_refuses_capture(self):
        self.owner._anchor_identity = (9, 2, stat.S_IFDIR, 4)
        with self.assertRaisesRegex(ValueError, "creator anchor"):
            self.owner._fresh_file_parents(self.path)

    def test_nondirectory_parent_refuses_capture(self):
        self.owner._identity.side_effect = [self.identity, (1, 2, stat.S_IFREG, 4)]
        with self.assertRaisesRegex(ValueError, "creator parent"):
            self.owner._fresh_file_parents(self.path)

    def test_success_appends_exact_frozen_witness_after_validation(self):
        self.owner._record_fresh_file(self.path, self.node, self.parents)
        witness, = self.owner.transaction._fresh_files
        self.assertIs(witness.owner, self.owner)
        self.assertIs(witness.node, self.node)
        self.assertEqual(witness.parents, self.parents)
        self.owner.transaction._image_file_bytes.assert_called_once_with(self.path, self.node)
        with self.assertRaises(FrozenInstanceError):
            witness.path = self.path.parent

    def test_no_tracking_does_not_read_or_record(self):
        self.owner._record_fresh_file(self.path, self.node, None)
        self.assertEqual(self.owner.transaction._fresh_files, [])
        self.owner.transaction._image_file_bytes.assert_not_called()

    def test_parent_drift_never_appends_or_reads_content(self):
        self.owner._identity.return_value = (8, 2, stat.S_IFDIR, 4)
        with self.assertRaisesRegex(ValueError, "creator parents"):
            self.owner._record_fresh_file(self.path, self.node, self.parents)
        self.assertEqual(self.owner.transaction._fresh_files, [])
        self.owner.transaction._image_file_bytes.assert_not_called()

    def test_content_failure_never_appends(self):
        self.owner.transaction._image_file_bytes.side_effect = ValueError("content drift")
        with self.assertRaisesRegex(ValueError, "content drift"):
            self.owner._record_fresh_file(self.path, self.node, self.parents)
        self.assertEqual(self.owner.transaction._fresh_files, [])

    def test_foreign_owner_or_nonfile_witness_is_rejected(self):
        for owner, node in ((object(), self.node),
                            (self.owner, SimpleNamespace(kind="directory"))):
            with self.subTest(owner=owner, node=node):
                witness = self.Witness(owner, self.path, node, self.parents)
                with self.assertRaisesRegex(ValueError, "creator witness"):
                    self.owner._assert_fresh_file(witness)
        self.owner.transaction._image_file_bytes.assert_not_called()




if __name__ == "__main__":
    unittest.main()
