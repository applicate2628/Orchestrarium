"""Source-only receipt wiring contracts.

These assertions parse text, never import, compile, invoke or mock the installer,
its physical readers, transactions or writers. They establish source structure,
not physical correctness or rollback qualification.
"""
import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def shape(node):
    # Compare expression structure regardless of assignment/load position.
    return (ast.dump(node, include_attributes=False)
            .replace(", ctx=Store()", "").replace(", ctx=Load()", ""))


def expression(text):
    return ast.parse(text, mode="eval").body


def contains(tree, text):
    expected = shape(expression(text))
    return any(shape(node) == expected for node in ast.walk(tree))


def calls(tree, name):
    return sorted(
        (node for node in ast.walk(tree)
         if isinstance(node, ast.Call)
         and ((isinstance(node.func, ast.Attribute) and node.func.attr == name)
              or (isinstance(node.func, ast.Name) and node.func.id == name))),
        key=lambda node: (node.lineno, node.col_offset),
    )


def named(tree, name):
    matches = [node for node in tree.body
               if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == name]
    if len(matches) != 1:
        raise AssertionError(f"Expected one direct definition: {name}")
    return matches[0]


class FreshProviderWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse((ROOT / "scripts" / "production_installer.py").read_text(
            encoding="utf-8-sig"))
        cls.owner = named(cls.tree, "_CreateOnlyMutablePath")
        cls.transaction = named(cls.tree, "_InstallTransaction")

    def method(self, name):
        return named(self.owner, name)

    def require(self, tree, text):
        self.assertTrue(contains(tree, text), text)

    def one_call(self, tree, name):
        found = calls(tree, name)
        self.assertEqual(len(found), 1, name)
        return found[0]

    def test_ledger_is_opt_in_provenance_not_an_inverse_owner(self):
        init = named(self.transaction, "__init__")
        defaults = dict(zip((arg.arg for arg in init.args.kwonlyargs),
                            init.args.kw_defaults))
        self.assertEqual(shape(defaults["track_fresh_files"]), shape(expression("False")))
        self.require(init, "self._track_fresh_files")
        entries = [node for node in ast.walk(init)
                   if isinstance(node, ast.AnnAssign)
                   and shape(node.target) == shape(expression("self._fresh_files"))]
        self.assertEqual(len(entries), 1)
        self.assertEqual(shape(entries[0].value), shape(expression("[]")))
        witness = named(self.tree, "_FreshFileWitness")
        self.require(witness, "dataclass(frozen=True)")
        self.assertEqual([node.target.id for node in witness.body
                          if isinstance(node, ast.AnnAssign)],
                         ["owner", "path", "node", "parents"])
        # Only admission, successful append and the finalizer consume this ledger.
        for cls in (self.transaction, self.owner):
            users = {method.name for method in cls.body
                     if isinstance(method, ast.FunctionDef)
                     and any(isinstance(node, ast.Attribute) and node.attr == "_fresh_files"
                             for node in ast.walk(method))}
            self.assertEqual(users, {"__init__"} if cls is self.transaction
                             else {"_record_fresh_file"})

    def test_capture_rejects_disabled_dryrun_linked_and_original_files(self):
        capture = self.method("_fresh_file_parents")
        guard = next(node for node in capture.body if isinstance(node, ast.If))
        for clause in ("self.dry_run", "not transaction.enabled",
                       "not transaction._track_fresh_files",
                       "self.linked_authority is not None",
                       "any(path in image for image in transaction._original.values())"):
            self.require(guard.test, clause)
        self.assertIsInstance(guard.body[0], ast.Return)
        self.assertEqual(shape(guard.body[0].value), shape(expression("None")))
        self.require(capture, "self._file_parent_identities(path)")
        capture_shared = self.method("_file_parent_identities")
        self.require(capture_shared, "self.transaction._binding_identity_matches(self._anchor_identity, self._identity(self.anchor))")
        self.require(capture_shared, "parents.append((current, identity))")

    def test_success_append_requires_creator_and_parent_bound_readback(self):
        record = self.method("_record_fresh_file")
        first = next(node for node in record.body if isinstance(node, ast.If))
        self.require(first.test, "parents is None")
        self.assertIsInstance(first.body[0], ast.Return)
        check = self.one_call(record, "_assert_fresh_file")
        append = self.one_call(record, "append")
        self.assertLess(check.lineno, append.lineno)
        self.require(record, "_FreshFileWitness(self, path, node, parents)")
        bound = self.method("_assert_fresh_file")
        self.require(bound, "witness.owner is not self")
        self.require(bound, 'witness.node.kind != "file"')
        self.require(bound, "self._assert_bound_file(witness.path, witness.node, witness.parents)")
        shared = self.method("_assert_bound_file")
        self.require(shared, "self.transaction._binding_identity_matches(identity, self._identity(parent))")
        self.require(shared, "self.transaction._image_file_bytes(path, node)")

    def test_only_three_explicit_writer_seams_record_success(self):
        writers = {method.name for method in self.owner.body
                   if isinstance(method, ast.FunctionDef)
                   and calls(method, "_record_fresh_file")}
        self.assertEqual(writers, {"write_file", "copy_file", "create_file"})
        for name in writers:
            with self.subTest(writer=name):
                method = self.method(name)
                capture = self.one_call(method, "_fresh_file_parents")
                record = self.one_call(method, "_record_fresh_file")
                self.assertLess(capture.lineno, record.lineno)
                # Success append is a direct trailing statement, outside exception
                # handlers/finally and writer contexts, never an error callback.
                self.assertIsInstance(method.body[-2], ast.Expr)
                self.assertIs(method.body[-2].value, record)
                self.assertIsInstance(method.body[-1], ast.Return)
                dry = next(node for node in method.body if isinstance(node, ast.If)
                           and contains(node.test, "self.dry_run"))
                self.assertLess(dry.lineno, capture.lineno)
                self.assertIsInstance(dry.body[0], ast.Return)
                creators = calls(method, "create") + calls(method, "open") + calls(
                    method, "_prepare_payload_file")
                self.assertTrue(creators)
                self.assertTrue(all(capture.lineno < node.lineno for node in creators))
                if name != "create_file":
                    assignments = [node for node in method.body
                                   if isinstance(node, ast.Assign)
                                   and any(isinstance(target, ast.Name)
                                           and target.id == "fresh_parents"
                                           for target in node.targets)]
                    value = assignments[0].value
                    self.assertIsInstance(value, ast.IfExp)
                    self.require(value.test, "existing is None")
                    self.assertEqual(shape(value.orelse), shape(expression("None")))

    def test_writer_checks_precede_success_and_copy_keeps_latest_metadata_node(self):
        write = self.method("write_file")
        self.assertLess(calls(write, "_scalar_descriptor_node")[-1].lineno,
                        self.one_call(write, "_record_fresh_file").lineno)
        copy = self.method("copy_file")
        record = named(copy, "record")
        self.assertTrue(any(isinstance(node, ast.Nonlocal)
                            and node.names == ["completed_node"] for node in record.body))
        self.assertTrue(any(isinstance(node, ast.Assign)
                            and shape(node.targets[0]) == shape(expression("completed_node"))
                            and shape(node.value) == shape(expression("node"))
                            for node in record.body))
        metadata = self.one_call(copy, "_apply_copy_metadata")
        self.assertEqual(shape(metadata.args[-2]), shape(expression("record")))
        success = self.one_call(copy, "_record_fresh_file")
        self.assertLess(metadata.lineno, success.lineno)
        self.assertEqual(shape(success.args[1]), shape(expression("completed_node")))
        create = self.method("create_file")
        for check in ("_assert_regular", "_file_sha256", "_record_created"):
            self.assertLess(calls(create, check)[-1].lineno,
                            self.one_call(create, "_record_fresh_file").lineno)
        collision = next(node for node in create.body if isinstance(node, ast.If))
        self.require(collision.test, "path.exists() or path.is_symlink()")
        self.require(collision, "path.read_bytes() == payload")
        self.assertTrue(any(isinstance(node, ast.Return) for node in ast.walk(collision)))
        self.assertLess(collision.end_lineno, self.one_call(create, "_fresh_file_parents").lineno)
        self.assertEqual(calls(collision, "_record_fresh_file"), [])

    def test_candidate_only_admits_missing_leaf_without_decoding_existing_receipt(self):
        candidate = named(self.tree, "_fresh_provider_receipt_candidate")
        self.assertEqual([ast.unparse(call.func) for call in calls(candidate, "lstat")],
                         ["candidate.lstat"])
        all_calls = [node for node in ast.walk(candidate) if isinstance(node, ast.Call)]
        self.assertEqual(len(all_calls), 1)
        attempt = next(node for node in candidate.body if isinstance(node, ast.Try))
        self.assertEqual(ast.unparse(attempt.handlers[0].type), "FileNotFoundError")
        self.assertEqual(ast.unparse(attempt.handlers[0].body[0]), "return candidate")
        self.assertEqual(ast.unparse(attempt.handlers[1].type), "OSError")
        self.assertEqual(ast.unparse(attempt.handlers[1].body[0]), "return None")
        self.assertEqual(ast.unparse(candidate.body[-1]), "return None")

    def test_finalizer_filters_original_foreign_transient_and_ambiguous_witnesses(self):
        final = named(self.tree, "_record_fresh_provider_receipt")
        for text in (
            "receipt is None", "owner.dry_run", "not transaction.enabled",
            "any(receipt in image for image in transaction._original.values())",
        ):
            self.require(final, text)
        collector_call = self.one_call(final, "_fresh_provider_receipt_files")
        for guard in (node for node in final.body if isinstance(node, ast.If)
                      and node.lineno < collector_call.lineno):
            self.assertIsInstance(guard.body[0], ast.Return)
        self.assertEqual(calls(final, "replace_file_atomic"), [])
        self.assertEqual(calls(final, "replace_exact_file"), [])
        final = named(self.tree, "_fresh_provider_receipt_files")
        for text in (
            "witness.owner is not owner", "path == receipt",
            "not path.is_relative_to(owner.anchor)",
            "any(path == root or root in path.parents for root in transient)",
            "any(path in image for image in transaction._original.values())",
            "len(rows) == 1", "payload is None",
        ):
            self.require(final, text)
        self.require(final, "transaction._temporary")
        self.require(final, "transaction._migration_retention")
        for name in ("retained", "prepared_path", "quarantine"):
            self.require(final, "effect." + name)
        self.assertEqual(calls(final, "replace_file_atomic"), [])
        self.assertEqual(calls(final, "replace_exact_file"), [])
        self.require(final, 'json.loads(payload)["files"]')

    def test_publication_requires_new_witness_and_bound_exact_readback(self):
        final = named(self.tree, "_record_fresh_provider_receipt")
        create = self.one_call(final, "create_file")
        absence = self.one_call(final, "_image_matches")
        self.assertLess(absence.lineno, create.lineno)
        self.assertEqual(ast.unparse(absence), "transaction._image_matches(receipt, {})")
        self.require(final, "transaction._fresh_files[start:]")
        self.require(final, "witness.owner is owner and witness.path == receipt")
        count = next(node for node in final.body if isinstance(node, ast.If)
                     and contains(node.test, "len(created) != 1"))
        self.assertIsInstance(count.body[0], ast.Raise)
        self.assertGreater(count.lineno, create.lineno)
        checks = calls(final, "_assert_fresh_file")
        self.assertEqual(len(checks), 3)
        self.assertLess(checks[0].lineno, create.lineno)
        self.assertGreater(checks[1].lineno, create.lineno)
        self.require(final, "owner._assert_fresh_file(created[0]) != payload")
        loops = [node for node in final.body if isinstance(node, ast.For)
                 and contains(node.iter, "selected.values()")]
        self.assertEqual(len(loops), 2)
        self.assertLess(loops[0].lineno, create.lineno)
        self.assertGreater(loops[1].lineno, create.lineno)

    def test_install_admits_receipt_and_finalizes_same_transaction_before_commit(self):
        install = named(self.tree, "install")
        transaction = self.one_call(install, "_InstallTransaction")
        self.require(install, "bool(instruction_grants) or document_grant is not None or receipt_grant is not None")
        self.assertTrue(any(kw.arg == "track_fresh_files"
                            and shape(kw.value) == shape(expression("fresh_receipt is not None or selected_requested"))
                            for kw in transaction.keywords))
        admission = next(node for node in ast.walk(install)
                         if isinstance(node, ast.Assign)
                         and any(isinstance(target, ast.Name) and target.id == "fresh_receipt"
                                 for target in node.targets))
        self.assertEqual(ast.unparse(admission.value),
                         "None if args.dry_run else _fresh_provider_receipt_candidate(target)")
        self.require(install, "transaction_paths.append(fresh_receipt)")
        self.assertLess(admission.lineno, transaction.lineno)
        scope = next(node for node in ast.walk(install) if isinstance(node, ast.With)
                     and any(shape(item.context_expr) == shape(expression("transaction"))
                             for item in node.items))
        final = self.one_call(scope, "_record_fresh_provider_receipt")
        self.assertEqual(ast.unparse(final.args[-1]), "create_only")
        self.assertEqual(ast.unparse(final.args[-2]), "fresh_receipt")
        branch = scope.body[-2]
        self.assertIsInstance(branch, ast.If)
        self.require(branch.test, "selected_updates is not None")
        self.assertIs(branch.orelse[0].value, final)
        self.assertEqual(len(branch.orelse), 1)
        self.assertEqual(ast.unparse(scope.body[-1]), "transaction.commit()")
        for call in calls(scope, "_CreateOnlyMutablePath") + calls(scope, "bind_or_create_anchor"):
            if any(isinstance(arg, ast.Name) and arg.id == "transaction" for arg in call.args):
                break
        else:
            self.fail("No creator bound to the transaction")


if __name__ == "__main__":
    unittest.main()
