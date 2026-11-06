"""Pure receipt-manifest qualification; no installer or physical logic executes.

Only two AST-isolated pure functions are compiled. Finalizer assertions inspect
syntax and do not establish transaction, filesystem, or installation behavior.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "production_installer.py"
PURE_NAMES = {"_canonical_lead_expected_manifest", "_tree_manifest_sha256"}


def _source_tree():
    return ast.parse(SOURCE.read_bytes())


def _function(tree, name):
    return next(node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == name)


def _calls(node, name):
    return [item for item in ast.walk(node)
            if isinstance(item, ast.Call)
            and ((isinstance(item.func, ast.Name) and item.func.id == name)
                 or (isinstance(item.func, ast.Attribute)
                     and item.func.attr == name))]


class ExpectedLeadManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = _source_tree()
        nodes = [_function(tree, name) for name in sorted(PURE_NAMES)]
        module = ast.fix_missing_locations(ast.Module(body=[
            ast.ImportFrom(module="__future__",
                           names=[ast.alias(name="annotations")], level=0),
            *nodes,
        ], type_ignores=[]))
        scope = {"hashlib": hashlib, "json": json}
        exec(compile(module, "<pure-receipt-manifest>", "exec"), scope)
        cls.expected = staticmethod(scope["_canonical_lead_expected_manifest"])
        cls.digest = staticmethod(scope["_tree_manifest_sha256"])

    def test_unchanged_manifest_is_sorted_tuple(self):
        manifest = (("z/file", "z"), ("a/file", "a"))
        self.assertEqual(self.expected(manifest, PurePosixPath("/skills/lead")),
                         (("a/file", "a"), ("z/file", "z")))

    def test_empty_manifest(self):
        self.assertEqual(self.expected((), PurePosixPath("/skills/lead")), ())

    def test_bound_inside_removal_only(self):
        lead = PurePosixPath("/skills/lead")
        manifest = (("keep", "k"), ("scripts/retired.py", "r"))
        self.assertEqual(self.expected(
            manifest, lead, ((lead / "scripts/retired.py", "r"),)),
            (("keep", "k"),))

    def test_outside_removals_are_ignored(self):
        lead = PurePosixPath("/skills/lead")
        manifest = (("keep", "k"),)
        reclaimed = ((PurePosixPath("/other/keep"), "wrong"),
                     (PurePosixPath("/skills/lead-other/keep"), "wrong"))
        self.assertEqual(self.expected(manifest, lead, reclaimed), manifest)

    def test_wrong_digest_refused(self):
        lead = PurePosixPath("/skills/lead")
        with self.assertRaisesRegex(
                ValueError, "^E_MUTABLE_PATH_POSTCONDITION: unbound Lead reclamation$"):
            self.expected((("retired", "right"),), lead,
                          ((lead / "retired", "wrong"),))

    def test_missing_member_refused(self):
        lead = PurePosixPath("/skills/lead")
        with self.assertRaisesRegex(ValueError, "unbound Lead reclamation"):
            self.expected((("keep", "k"),), lead, ((lead / "missing", "x"),))

    def test_duplicate_removal_refused(self):
        lead = PurePosixPath("/skills/lead")
        removal = (lead / "retired", "r")
        with self.assertRaisesRegex(ValueError, "unbound Lead reclamation"):
            self.expected((("retired", "r"),), lead, (removal, removal))

    def test_success_does_not_modify_inputs(self):
        lead = PurePosixPath("/skills/lead")
        manifest = [["z", "z"], ["retired", "r"], ["a", "a"]]
        reclaimed = [(lead / "retired", "r")]
        snapshot = [row[:] for row in manifest]
        removals = reclaimed[:]
        self.expected(manifest, lead, reclaimed)
        self.assertEqual(manifest, snapshot)
        self.assertEqual(reclaimed, removals)

    def test_refusal_does_not_modify_inputs(self):
        lead = PurePosixPath("/skills/lead")
        manifest = [["first", "f"], ["keep", "k"]]
        reclaimed = [(lead / "first", "f"), (lead / "absent", "x")]
        snapshot = [row[:] for row in manifest]
        removals = reclaimed[:]
        with self.assertRaises(ValueError):
            self.expected(manifest, lead, reclaimed)
        self.assertEqual(manifest, snapshot)
        self.assertEqual(reclaimed, removals)

    def test_windows_relative_keys_use_forward_slashes(self):
        lead = PureWindowsPath("Q:/synthetic/skills/lead")
        self.assertEqual(self.expected(
            (("scripts/retired.py", "r"), ("keep", "k")), lead,
            ((lead / "scripts" / "retired.py", "r"),
             (PureWindowsPath("R:/elsewhere/keep"), "wrong"))),
            (("keep", "k"),))

    def test_path_flavors_preserve_their_case_rules(self):
        windows = PureWindowsPath("Q:/synthetic/Lead")
        self.assertEqual(self.expected(
            (("old", "r"),), windows,
            ((PureWindowsPath("q:/SYNTHETIC/lead/old"), "r"),)), ())
        posix = PurePosixPath("/synthetic/Lead")
        self.assertEqual(self.expected(
            (("old", "r"),), posix,
            ((PurePosixPath("/synthetic/lead/old"), "r"),)),
            (("old", "r"),))

    def test_digest_uses_existing_tagged_json_encoding(self):
        for members in ((), (("a", "a" * 64),),
                        (("nested/\u00e9", "b" * 64), ("z", "c" * 64))):
            with self.subTest(members=members):
                encoded = json.dumps(
                    ["orchestrarium.tree-manifest.sha256.v2", members],
                    ensure_ascii=True, separators=(",", ":")).encode("ascii")
                self.assertEqual(self.digest(members),
                                 hashlib.sha256(encoded).hexdigest())

    def test_digest_preserves_member_order_and_boundaries(self):
        first = (("a", "bc"), ("d", "ef"))
        self.assertNotEqual(self.digest(first), self.digest(tuple(reversed(first))))
        self.assertNotEqual(self.digest((("a", "bc"),)),
                            self.digest((("ab", "c"),)))


class FinalizerStaticWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = _function(_source_tree(), "_finalize_canonical_lead_receipt")

    def test_dry_run_returns_before_manifest_work(self):
        executable = [n for n in self.node.body
                      if not (isinstance(n, ast.Expr)
                              and isinstance(n.value, ast.Constant))]
        first = executable[0]
        self.assertIsInstance(first, ast.If)
        self.assertEqual(ast.unparse(first.test), "owner.dry_run")
        self.assertIsInstance(first.body[0], ast.Return)

    def test_expected_manifest_uses_pure_helper(self):
        calls = _calls(self.node, "_canonical_lead_expected_manifest")
        self.assertEqual(len(calls), 1)
        self.assertEqual([ast.unparse(arg) for arg in calls[0].args],
                         ["plan.stage.manifest", "lead", "reclaimed"])

    def test_enabled_transaction_selects_image_and_owned_reader(self):
        branches = [n for n in ast.walk(self.node)
                    if isinstance(n, ast.If)
                    and "enabled" in ast.unparse(n.test)]
        self.assertEqual(len(branches), 1)
        branch = branches[0]
        self.assertEqual(ast.unparse(branch.test), "owner.transaction.enabled")
        self.assertEqual(len(_calls(self.node, "_admitted_mutation_image")), 1)
        self.assertEqual(len(_calls(self.node, "_image_file_bytes")), 1)
        self.assertEqual(len(_calls(branch, "_admitted_mutation_image")), 1)
        self.assertEqual(len(_calls(branch, "_image_file_bytes")), 1)
        callback = next(n for n in ast.walk(branch) if isinstance(n, ast.Lambda))
        self.assertEqual(ast.unparse(callback.body),
                         "owner.transaction._image_file_bytes(member, image.get(member))")
        image_call = _calls(branch, "_admitted_mutation_image")[0]
        self.assertEqual([ast.unparse(arg) for arg in image_call.args],
                         ["owner.transaction", "storage_lead"])
        assignments = [n for n in self.node.body if isinstance(n, ast.Assign)]
        storage = next(n for n in assignments
                       if any(isinstance(t, ast.Name) and t.id == "storage_lead"
                              for t in n.targets))
        self.assertEqual(ast.unparse(storage.value), "Path(os.path.abspath(lead))")
        default = next(n for n in assignments
                       if any(isinstance(t, ast.Name) and t.id == "read_file"
                              for t in n.targets))
        self.assertIsNone(ast.literal_eval(default.value))
        self.assertLess(default.lineno, branch.lineno)
        scan = _calls(self.node, "_stage_tree_manifest")[0]
        self.assertEqual(ast.unparse(scan.args[0]), "storage_lead")
        self.assertEqual(ast.unparse(next(
            kw.value for kw in scan.keywords if kw.arg == "read_file")), "read_file")
        self.assertGreater(scan.lineno, branch.end_lineno)

    def test_actual_manifest_is_compared_and_hashed_once(self):
        hashes = _calls(self.node, "_tree_manifest_sha256")
        self.assertEqual(len(hashes), 1)
        self.assertEqual(len(hashes[0].args), 1)
        actual = hashes[0].args[0]
        self.assertIsInstance(actual, ast.Name)
        self.assertEqual(actual.id, "actual")
        comparisons = [n for n in ast.walk(self.node)
                       if isinstance(n, ast.Compare)
                       and any(isinstance(op, ast.NotEq) for op in n.ops)
                       and any(isinstance(v, ast.Name) and v.id == actual.id
                               for v in [n.left, *n.comparators])]
        self.assertEqual(len(comparisons), 1)
        self.assertLess(comparisons[0].lineno, hashes[0].lineno)
        self.assertEqual(_calls(self.node, "_tree_sha256"), [])
        scans = _calls(self.node, "_stage_tree_manifest")
        self.assertEqual(len(scans), 1)
        assignment = next(n for n in self.node.body
                          if isinstance(n, ast.Assign) and n.value is scans[0])
        self.assertEqual([ast.unparse(t) for t in assignment.targets], ["actual"])
        for scan in scans:
            keywords = {kw.arg: kw.value for kw in scan.keywords}
            self.assertEqual(ast.literal_eval(keywords["ignore_runtime_cache"]), True)

    def test_receipt_writer_tail_is_retained(self):
        for name in ("_lead_receipt_bytes", "_read_lead_receipt",
                     "create_file", "replace_exact_file"):
            self.assertEqual(len(_calls(self.node, name)), 1, name)
        text = ast.unparse(self.node)
        self.assertIn("prior_receipt = plan.lead_receipt.observed", text)
        self.assertIn("relative = target.relative_to(owner.anchor) / _LEAD_RECEIPT_NAME", text)
        self.assertIn("owner.create_file(relative, payload)", text)
        self.assertIn(
            "owner.replace_exact_file(relative, hashlib.sha256(prior_receipt[0]).hexdigest(), payload)",
            text)


if __name__ == "__main__":
    unittest.main()
