"""Pure and memory-only modified Lead SDK binding regression checks."""
import ast
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock
SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "production_installer.py"


class ModifiedLeadSdkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(SOURCE.read_bytes())

    def load(self, names, scope):
        nodes = [n for n in self.tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
        module = ast.fix_missing_locations(ast.Module(body=[
            ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)] + nodes, type_ignores=[]))
        exec(compile(module, "memory-modified-lead", "exec"), scope)
        return scope

    def setUp(self):
        self.target = Path("memory-skills")
        self.raw = b"receipt\r\n"
        self.manifest = (("SKILL.md", "a"*64), ("scripts", "directory"), ("scripts/tool.py", "b"*64))
        self.receipt = (self.raw, (1, 2, 3, 4), "old", "v2")
        self.plan = NS(lead_receipt=NS(selection=(hashlib.sha256(self.raw).hexdigest(), "current", "stage")),
                       stage=NS(digest="stage"))
        self.scope = dict(hashlib=hashlib, re=re, Path=Path, os=os,
            _LEAD_RECEIPT_NAME="receipt.json",
            _assert_lead_receipt_current=Mock(return_value=self.receipt),
            _admitted_tree_manifest=Mock(return_value=self.manifest),
            _tree_manifest_sha256=Mock(return_value="current"))
        self.load({"_selected_lead_prior_files"}, self.scope)

    def call(self):
        return self.scope["_selected_lead_prior_files"](self.plan, self.target, "transaction")

    def test_bridge_returns_exact_files_not_directories_or_subtree_permission(self):
        self.assertEqual(self.call(), {self.target/"lead/SKILL.md": "a"*64,
                                      self.target/"lead/scripts/tool.py": "b"*64})
        self.scope["_assert_lead_receipt_current"].assert_called_once_with(
            self.plan.lead_receipt, self.target/"receipt.json", "transaction")

    def test_no_selection_does_not_acquire_or_read_tree(self):
        self.plan.lead_receipt.selection = None
        self.assertEqual(self.call(), {})
        self.scope["_assert_lead_receipt_current"].assert_not_called()
        self.scope["_admitted_tree_manifest"].assert_not_called()

    def test_receipt_tree_or_stage_drift_refuses_bridge(self):
        for part in range(3):
            original = self.plan.lead_receipt.selection
            values = list(original); values[part] = "wrong"
            self.plan.lead_receipt.selection = tuple(values)
            with self.subTest(part=part), self.assertRaisesRegex(ValueError, "provider preimage drift"):
                self.call()
            self.plan.lead_receipt.selection = original

    def test_receipt_identity_failure_is_not_hidden(self):
        self.scope["_assert_lead_receipt_current"].side_effect = ValueError("receipt drift")
        with self.assertRaisesRegex(ValueError, "receipt drift"):
            self.call()

    def test_dataclass_selection_remains_optional_and_explicit(self):
        scope = self.load({"_LeadReceiptPlan"}, {"dataclass": dataclass})
        ordinary = scope["_LeadReceiptPlan"](None, "digest", "source")
        self.assertIsNone(ordinary.selection)
        selected = scope["_LeadReceiptPlan"](None, "digest", "source", selection=("a", "b", "c"))
        self.assertEqual(selected.selection, ("a", "b", "c"))

    def test_preflight_disallows_conflicting_selection(self):
        fn = next(n for n in self.tree.body if isinstance(n, ast.FunctionDef)
                  and n.name == "_preflight_canonical_skills")
        guard = next(n for n in fn.body if isinstance(n, ast.If)
                     and "replace_unreceipted_lead_sha256 is not None" in ast.unparse(n.test)
                     and "lead_selection" in ast.unparse(n.test))
        scope = dict(lead_selection=("a", "b", "c"), global_install=True,
                     member_selection=None, replace_unreceipted_lead_sha256="conflict")
        with self.assertRaisesRegex(ValueError, "conflicting selection"):
            exec(compile(ast.Module(body=[guard], type_ignores=[]), "selection-guard", "exec"), scope)

    def test_finalizer_retains_exact_receipt_checks_and_return_digest(self):
        fn = next(n for n in self.tree.body if isinstance(n, ast.FunctionDef)
                  and n.name == "_finalize_canonical_lead_receipt")
        assertions = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
                      and isinstance(n.func, ast.Name) and n.func.id == "_assert_lead_receipt_current"]
        self.assertEqual(len(assertions), 2)
        self.assertTrue(any(isinstance(n, ast.Return) and isinstance(n.value, ast.Name)
                            and n.value.id == "digest" for n in ast.walk(fn)))
        self.assertIn("_canonical_lead_expected_manifest", ast.unparse(fn))

    def test_admitted_manifest_reads_via_transaction_image(self):
        file = self.target/"lead/SKILL.md"
        node = object()
        tx = NS(enabled=True, _image_file_bytes=Mock(return_value=b"bound"))
        def stage(path, *, ignore_runtime_cache, read_file):
            self.assertTrue(ignore_runtime_cache)
            self.assertEqual(read_file(file), b"bound")
            return self.manifest
        scope = self.load({"_admitted_tree_manifest"}, dict(Path=Path, os=os,
            _admitted_mutation_image=Mock(return_value={file: node}), _stage_tree_manifest=stage))
        self.assertEqual(scope["_admitted_tree_manifest"](tx, self.target/"lead",
                                                         ignore_runtime_cache=True), self.manifest)
        tx._image_file_bytes.assert_called_once_with(file, node)


if __name__ == "__main__":
    unittest.main()
