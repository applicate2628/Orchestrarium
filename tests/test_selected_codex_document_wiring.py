"""AST-only selected Codex document wiring contracts.

Parse source without importing, compiling, executing or mocking installer
functions or physical owners. Passing proves structure, not physical lifecycle,
race safety, rollback qualification or authority to activate an installation.
"""
import ast
from pathlib import Path
import unittest

from test_fresh_provider_wiring import calls, contains, expression, named, shape


ROOT = Path(__file__).resolve().parents[1]


class SelectedCodexDocumentWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse((ROOT / "scripts" / "production_installer.py").read_text(
            encoding="utf-8-sig"))

    def definition(self, name):
        return named(self.tree, name)

    def require(self, tree, text):
        self.assertTrue(contains(tree, text), text)

    def one(self, tree, name):
        found = calls(tree, name)
        self.assertEqual(len(found), 1, name)
        return found[0]

    def branch(self, tree, test):
        found = [node for node in ast.walk(tree)
                 if isinstance(node, ast.If) and shape(node.test) == shape(expression(test))]
        self.assertEqual(len(found), 1, test)
        return found[0]

    def test_explicit_repeated_option_and_provider_only_admission(self):
        parser = self.definition("_parser")
        option = [call for call in calls(parser, "add_argument")
                  if call.args and contains(call.args[0], '"--replace-codex-document"')]
        self.assertEqual(len(option), 1)
        options = {kw.arg: ast.literal_eval(kw.value) for kw in option[0].keywords}
        self.assertEqual(options["action"], "append")
        self.assertEqual(options["default"], [])
        self.assertEqual(options["metavar"], "SHA256:START:END")
        install = self.definition("install")
        guard = self.branch(install, 'args.replace_codex_document and provider != "codex"')
        self.assertIsInstance(guard.body[-1], ast.Return)
        parse = self.one(install, "_parse_codex_document_grant")
        self.require(parse, "tuple(args.replace_codex_document)")
        self.assertLess(guard.end_lineno, parse.lineno)
        self.assertEqual(len(parse.args), 1)
        self.assertEqual(parse.keywords, [])

    def test_posix_hold_remains_before_target_resolution(self):
        install = self.definition("install")
        hold = self.branch(install, 'os.name == "posix"')
        self.assertIsInstance(hold.body[-1], ast.Return)
        self.assertLess(hold.end_lineno, self.one(install, "_target").lineno)

    def test_document_preflight_binds_destination_raw_digest_and_two_sources(self):
        prepare = self.definition("_prepare_selected_codex_document")
        for text in (
            "owner.destination(document.relative_to(owner.anchor))",
            "_admitted_mutation_image(transaction, path).get(path)",
            "owner._file_parent_identities(path)",
            "owner._assert_bound_file(path, before_node, parents)",
            "hashlib.sha256(before).hexdigest() != digest",
            '(root / "shared" / "AGENTS.shared.md", source / "AGENTS.codex.md")',
            "_capture_selected_source(path, transaction)",
            "_SelectedReplacement(sources, path, before_node, before, after, digest, parents)",
        ):
            self.require(prepare, text)
        digest = self.branch(prepare, "hashlib.sha256(before).hexdigest() != digest")
        self.assertIsInstance(digest.body[0], ast.Raise)
        self.assertLess(digest.end_lineno, self.one(prepare, "_capture_selected_source").lineno)
        capture = self.definition("_capture_selected_source")
        self.require(capture, "_SelectedSource(path, node, transaction._image_file_bytes(path, node))")

    def test_rendering_normalizes_source_text_but_keeps_raw_document_witness(self):
        prepare = self.definition("_prepare_selected_codex_document")
        self.require(prepare, 'item.raw.decode("utf-8").replace("\\r\\n", "\\n").replace("\\r", "\\n")')
        self.require(prepare, "_codex_document_payload(*texts)")
        render = self.one(prepare, "_render_selected_document")
        self.assertEqual([ast.unparse(arg) for arg in render.args],
                         ["before.decode('utf-8')", "'codex'", "payload", "_markdown_document_context"])
        self.assertEqual({kw.arg: ast.unparse(kw.value) for kw in render.keywords},
                         {"document_digest": "digest", "span": "span"})
        self.require(prepare, '"AGENTS.md" if scope == "project" else ".codex/AGENTS.md"')
        self.require(prepare, '_ReceiptOutcome(key, "block", before, after, intent="replace", adoption_sha256=digest, adoption_span=span)')
        self.one(self.definition("_prepare_codex_agents"), "_codex_document_payload")
        self.require(self.definition("_codex_document_payload"),
                     'shared_text.rstrip() + "\\n\\n" + codex_text.rstrip() + "\\n"')

    def test_receipt_plan_is_serialized_during_shared_preflight(self):
        prepare = self.definition("_prepare_selected_provider_updates")
        plan = self.one(prepare, "_plan_receipt_changes")
        serialize = self.one(prepare, "_serialize_receipt_delta")
        self.require(plan, "_plan_receipt_changes(receipt_before, provider, scope, outcomes, _markdown_document_context)")
        guard = self.branch(prepare, 'any(item.route != "selected-replacement-proposal" for item in plan.artifacts)')
        self.assertIsInstance(guard.body[0], ast.Raise)
        self.assertLess(plan.lineno, guard.lineno)
        self.assertLess(guard.end_lineno, serialize.lineno)
        for name in ("create_file", "write_file", "replace_exact_file", "bind_readonly_path"):
            self.assertEqual(calls(prepare, name), [])
        for name in ("_prepare_selected_codex_document", "_prepare_selected_claude_instructions"):
            self.one(self.definition(name), "_prepare_selected_provider_updates")

    def test_absent_receipt_parents_combine_covered_originals_and_current_outside(self):
        preimage = self.definition("_selected_receipt_parent_preimage")
        for text in (
            "tuple(transaction._original)",
            "transaction._capture_readonly_parents(receipt, covered)",
            "image.get(parent)",
            "parent == root or root in parent.parents",
            "any(node != originals[0] for node in originals[1:])",
            "parents[parent]",
            "originals[0]",
        ):
            self.require(preimage, text)
        conflict = self.branch(preimage, "any(node != originals[0] for node in originals[1:])")
        self.assertIsInstance(conflict.body[0], ast.Raise)
        # Coverage, not an empty receipt-leaf image, determines known absence.
        self.assertFalse(contains(preimage, "image.get(receipt)"))
        self.assertFalse(contains(preimage, "not image"))
        prepare = self.definition("_prepare_selected_provider_updates")
        absent = self.branch(prepare, "receipt_node is None")
        capture = self.one(absent, "_selected_receipt_parent_preimage")
        assertion = self.one(absent, "_assert_readonly_parents")
        self.assertLess(capture.lineno, assertion.lineno)
        self.assertLess(assertion.lineno, self.one(prepare, "_serialize_receipt_delta").lineno)
        self.assertEqual(calls(preimage, "bind_readonly_path"), [])

    def test_exact_apply_rejects_foreign_linked_wrong_source_target_and_duplicate(self):
        apply = self.definition("_apply_selected_replacement")
        guard = next(node for node in apply.body if isinstance(node, ast.If))
        for text in (
            "owner is not batch.owner", "owner.linked_authority is not None",
            "tuple(Path(os.path.abspath(source)) for source in source_paths) != tuple(source.path for source in selected.sources)",
            "Path(os.path.abspath(path)) != selected.path", "key in batch.received",
        ):
            self.require(guard.test, text)
        self.assertIsInstance(guard.body[0], ast.Raise)
        sources = self.one(apply, "_assert_selected_sources")
        writer = self.one(apply, "replace_exact_file")
        self.assertLess(guard.end_lineno, sources.lineno)
        self.assertLess(sources.lineno, writer.lineno)
        preimage = self.branch(apply, "owner._assert_bound_file(selected.path, selected.before_node, selected.parents) != selected.before")
        self.assertIsInstance(preimage.body[0], ast.Raise)
        self.assertLess(preimage.end_lineno, writer.lineno)
        changed = self.branch(apply, "selected.before != selected.after")
        self.assertIs(changed.body[0].value, writer)
        self.require(writer, "owner.replace_exact_file(selected.path.relative_to(owner.anchor), selected.digest, selected.after)")
        received = self.one(apply, "_assert_selected_replacement")
        self.assertLess(writer.lineno, received.lineno)
        self.assertEqual(ast.unparse(apply.body[-1]), "batch.received[key] = node")

    def test_finalizer_requires_current_sources_afterimages_and_complete_outcomes(self):
        source = self.definition("_assert_selected_sources")
        self.require(source, "owner.transaction._image_file_bytes(source.path, source.node) != source.raw")
        replacement = self.definition("_assert_selected_replacement")
        self.one(replacement, "_assert_selected_sources")
        self.require(replacement, "owner._assert_bound_file(selected.path, node, selected.parents) != selected.after")
        final = self.definition("_record_selected_provider_receipt")
        guard = self.branch(final, "not transaction.enabled or set(batch.received) != set(batch.items)")
        self.assertIsInstance(guard.body[0], ast.Raise)
        checks = calls(final, "_assert_selected_replacement")
        self.assertEqual(len(checks), 2)
        create = self.one(final, "create_file")
        self.assertLess(checks[0].lineno, create.lineno)
        self.assertGreater(checks[1].lineno, create.lineno)
        fresh = self.branch(final, "fresh")
        self.one(fresh, "_plan_receipt_changes")
        self.require(fresh, '"selected-replacement-proposal" if item.intent == "replace" else "creation-proposal"')
        self.require(fresh, "{item.path: item.route for item in plan.artifacts} != expected_routes")
        self.assertEqual(ast.unparse(fresh.orelse[0]), "payload = batch.payload")
        self.require(final, "{key: value for key, value in fresh.items() if key not in selected_keys}")

    def test_receipt_creation_reasserts_parents_absence_witness_and_readback(self):
        final = self.definition("_record_selected_provider_receipt")
        create = self.one(final, "create_file")
        parents = calls(final, "_assert_readonly_parents")
        self.assertEqual(len(parents), 3)
        self.assertLess(parents[0].lineno, create.lineno)
        self.assertTrue(all(node.lineno > create.lineno for node in parents[1:]))
        self.require(final, "not transaction._image_matches(batch.receipt, {})")
        self.require(final, "transaction._fresh_files[start:]")
        self.require(final, "witness.owner is owner and witness.path == batch.receipt")
        count = self.branch(final, "len(created) != 1")
        self.assertIsInstance(count.body[0], ast.Raise)
        self.assertGreater(count.lineno, create.lineno)
        self.require(final, "owner._assert_fresh_file(created[0]) != payload")
        self.require(final, "actual != payload")
        self.assertEqual(calls(final, "bind_readonly_path"), [])
        prepare = self.definition("_prepare_selected_provider_updates")
        for tree in (final, prepare):
            self.assertFalse(any(isinstance(node, ast.Attribute) and node.attr == "readonly_paths"
                                 for node in ast.walk(tree)))

    def test_existing_receipt_keeps_exact_bound_before_and_after(self):
        final = self.definition("_record_selected_provider_receipt")
        self.require(final, "owner._assert_bound_file(batch.receipt, batch.receipt_node, batch.receipt_parents) != batch.receipt_before")
        writer = self.one(final, "replace_exact_file")
        self.require(writer, "owner.replace_exact_file(batch.receipt.relative_to(owner.anchor), hashlib.sha256(batch.receipt_before).hexdigest(), payload)")
        self.require(final, "owner._assert_bound_file(batch.receipt, receipt_after, batch.receipt_parents)")
        self.assertEqual(calls(final, "replace_file_atomic"), [])

    def test_selection_precedes_ui_write_and_is_exclusive_with_legacy_merge(self):
        install = self.definition("install")
        prepare = self.one(install, "_prepare_selected_codex_document")
        ui_writes = calls(install, "_install_ui_continuity_contract")
        self.assertTrue(ui_writes)
        self.assertTrue(all(prepare.lineno < call.lineno for call in ui_writes))
        branch = self.branch(install, "document_grant is not None")
        apply = self.one(branch, "_apply_selected_replacement")
        self.assertEqual(calls(ast.Module(body=branch.body, type_ignores=[]), "_merge_codex_agents"), [])
        self.one(ast.Module(body=branch.orelse, type_ignores=[]), "_merge_codex_agents")
        self.assertLess(self.one(install, "_install_codex_native_roles").lineno, apply.lineno)
        self.require(apply, '(root / "shared" / "AGENTS.shared.md", source / "AGENTS.codex.md")')
        self.require(branch, '_warn_codex_project_budget(selected_updates.items[key].after.decode("utf-8"))')
        self.assertFalse(any(isinstance(node, ast.Try) for node in ast.walk(branch)))
        self.one(self.definition("_merge_codex_agents"), "_warn_codex_project_budget")
        self.require(self.definition("_warn_codex_project_budget"), "len(content.encode('utf-8'))")

    def test_one_selected_or_fresh_finalizer_and_receipt_share_transaction(self):
        install = self.definition("install")
        self.require(install, "bool(instruction_grants) or document_grant is not None")
        selected = self.branch(install, "selected_requested")
        self.require(selected, "transaction_paths.append(target / _PROVIDER_RECEIPT_NAME)")
        transaction = self.one(install, "_InstallTransaction")
        self.require(transaction, "fresh_receipt is not None or selected_requested")
        self.assertLess(selected.lineno, transaction.lineno)
        final = self.branch(install, "selected_updates is not None")
        selected_call = self.one(final, "_record_selected_provider_receipt")
        fresh_call = self.one(final, "_record_fresh_provider_receipt")
        self.assertIs(final.body[0].value, selected_call)
        self.assertIs(final.orelse[0].value, fresh_call)
        scope = next(node for node in ast.walk(install) if isinstance(node, ast.With)
                     and any(contains(item.context_expr, "transaction") for item in node.items))
        self.assertIs(scope.body[-2], final)
        self.assertEqual(ast.unparse(scope.body[-1]), "transaction.commit()")


if __name__ == "__main__":
    unittest.main()
