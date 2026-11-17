"""Exercise the real rollback decision with inert effects, not native disposal."""
import ast
from collections import namedtuple
from pathlib import Path
import stat
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts/production_installer.py"


class ProjectionInverseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(SOURCE.read_bytes())
        owner = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                     and n.name == "_CreateOnlyMutablePath")
        method = next(n for n in owner.body if isinstance(n, ast.FunctionDef)
                      and n.name == "rollback_created")
        transaction = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                           and n.name == "_InstallTransaction")
        image = next(n for n in transaction.body if isinstance(n, ast.FunctionDef)
                     and n.name == "_image_matches")
        image_owner = ast.ClassDef(name="_InstallTransaction", bases=[], keywords=[],
                                   body=[image], decorator_list=[])
        cls.code = compile(ast.fix_missing_locations(ast.Module(
            body=ast.parse("from __future__ import annotations").body + [image_owner, method],
            type_ignores=[])), str(SOURCE), "exec")

    def invoke(self, *, platform="posix", live=False, raw="owned-target",
               binding=True, mode=stat.S_IFLNK, recorded="owned-target"):
        calls = self.disposals = []
        def refuse():
            raise RuntimeError("E_ROLLBACK_CREATED_IDENTITY_CHANGED")
        def check(_):
            if not binding:
                refuse()
            return SimpleNamespace(st_mode=mode)
        record = SimpleNamespace(proof_key="creator", kind="projection",
            projection_target=Path("owned-target"), leaf_path=Path("projection"),
            leaf_identity=(1, 2, stat.S_IFLNK, 0), projection_data=recorded,
            native_proof=None, reparse_data=None)
        transaction = SimpleNamespace(_slice_a_created=[record],
            _dispose_node=lambda path, node: calls.append((path, node)))
        def read_target(_):
            if isinstance(raw, OSError):
                raise raw
            return raw
        node_type = namedtuple("PhysicalNode",
                               "kind python_identity data native_proof reparse_data")
        def metadata_matches(path, node):
            self.assertEqual(path, record.leaf_path)
            self.assertEqual(node.python_identity, record.leaf_identity)
            return binding and mode == record.leaf_identity[2]
        def point_matches(path, node, *, check_file_content, borrowed_opening):
            self.assertTrue(check_file_content)
            self.assertIsNone(borrowed_opening)
            self.assertEqual(path, record.leaf_path)
            self.assertEqual(node.kind, "link")
            self.assertEqual(node.native_proof, record.native_proof)
            self.assertEqual(node.reparse_data, record.reparse_data)
            return isinstance(node.data, str) and read_target(path) == node.data
        def no_follow(*args):
            self.fail("Rollback must compare the link object, not resolve its referent")
        scope = {"os": SimpleNamespace(name=platform, readlink=read_target),
                 "stat": stat, "_is_reparse_metadata": lambda _: False,
                 "_projection_resolves_to": no_follow,
                 "_PhysicalNode": node_type}
        exec(self.code, scope)
        image_owner = scope["_InstallTransaction"]
        image_owner._node_metadata_matches = staticmethod(metadata_matches)
        image_owner._point_matches = staticmethod(point_matches)
        transaction._image_matches = image_owner._image_matches
        owner = SimpleNamespace(transaction=transaction,
            _assert_created_binding=check, _rollback_identity_changed=refuse)
        scope["rollback_created"](owner, record)
        return calls

    def test_owned_posix_projection_does_not_require_live_referent(self):
        calls = self.invoke()
        self.assertEqual(calls, [(Path("projection"),
                         ("link", (1, 2, stat.S_IFLNK, 0), "owned-target", None, None))])

    def test_live_owned_posix_projection_still_qualifies(self):
        self.assertEqual(len(self.invoke(live=True)), 1)

    def test_changed_raw_target_is_not_adopted_even_if_resolution_matches(self):
        with self.assertRaisesRegex(RuntimeError, "E_ROLLBACK_CREATED_IDENTITY_CHANGED"):
            self.invoke(raw="another-spelling", live=True)
        self.assertEqual(self.disposals, [])

    def test_missing_raw_target_witness_refuses(self):
        with self.assertRaisesRegex(RuntimeError, "E_ROLLBACK_CREATED_IDENTITY_CHANGED"):
            self.invoke(recorded=None, live=True)
        self.assertEqual(self.disposals, [])

    def test_identity_drift_refuses_before_disposal(self):
        with self.assertRaisesRegex(RuntimeError, "E_ROLLBACK_CREATED_IDENTITY_CHANGED"):
            self.invoke(binding=False, live=True)
        self.assertEqual(self.disposals, [])

    def test_non_link_replacement_refuses(self):
        with self.assertRaisesRegex(RuntimeError, "E_ROLLBACK_CREATED_IDENTITY_CHANGED"):
            self.invoke(mode=stat.S_IFREG, live=True)
        self.assertEqual(self.disposals, [])

    def test_unreadable_raw_target_refuses_without_disposal(self):
        with self.assertRaisesRegex(RuntimeError, "E_ROLLBACK_CREATED_IDENTITY_CHANGED"):
            self.invoke(raw=OSError("unreadable link"))
        self.assertEqual(self.disposals, [])

    def test_windows_link_object_also_does_not_require_live_referent(self):
        self.assertEqual(len(self.invoke(platform="nt")), 1)
        self.assertEqual(len(self.invoke(platform="nt", live=True)), 1)
        with self.assertRaisesRegex(RuntimeError, "E_ROLLBACK_CREATED_IDENTITY_CHANGED"):
            self.invoke(platform="nt", raw="changed-target", live=True)
        self.assertEqual(self.disposals, [])


if __name__ == "__main__":
    unittest.main()
