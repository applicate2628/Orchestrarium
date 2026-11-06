"""Source-only selected-instruction integration contracts.

Parse source only: never import, compile, invoke or mock the installer or its
physical methods. These checks are not physical/recovery qualification.
"""
import ast
from pathlib import Path
import unittest

from test_fresh_provider_wiring import calls, contains, expression, named, shape


ROOT = Path(__file__).resolve().parents[1]


class SelectedClaudeInstructionWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse((ROOT / "scripts" / "production_installer.py").read_text(
            encoding="utf-8-sig"))

    def fn(self, name):
        return named(self.tree, name)

    def require(self, node, text):
        self.assertTrue(contains(node, text), text)

    def one(self, node, name):
        found = calls(node, name)
        self.assertEqual(len(found), 1, name)
        return found[0]

    def guard(self, node, text):
        found = [item for item in ast.walk(node)
                 if isinstance(item, ast.If) and contains(item.test, text)]
        self.assertEqual(len(found), 1, text)
        return found[0]

    def test_selection_is_explicit_repeatable_and_not_force_or_receipt_authority(self):
        parser = self.fn("_parser")
        options = [call for call in calls(parser, "add_argument")
                   if any(isinstance(arg, ast.Constant)
                          and arg.value == "--replace-claude-instruction" for arg in call.args)]
        self.assertEqual(len(options), 1)
        kw = {item.arg: ast.literal_eval(item.value) for item in options[0].keywords}
        self.assertEqual(kw["action"], "append")
        self.assertEqual(kw["default"], [])
        self.assertEqual(kw["metavar"], "PATH=SHA256")
        install = self.fn("install")
        guard = self.guard(install, 'args.replace_claude_instruction and provider != "claude"')
        self.assertTrue(any(isinstance(item, ast.Return) for item in guard.body))
        grant = next(item for item in ast.walk(install)
                     if isinstance(item, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == "instruction_grants"
                             for t in item.targets))
        self.assertIsInstance(grant.value, ast.IfExp)
        self.assertEqual(ast.unparse(grant.value.test), "args.replace_claude_instruction")
        self.assertEqual(ast.unparse(grant.value.orelse), "{}")
        self.require(grant.value.body, "tuple(args.replace_claude_instruction)")
        self.one(grant.value.body, "_claude_instruction_source_names")
        self.assertNotIn("force", ast.unparse(grant.value))
        self.assertNotIn("receipt", ast.unparse(grant.value))
        linked = self.guard(install, "instruction_grants and any(authority.name in {key.split('/')[0] for key in instruction_grants} for authority in claude_link_authorities)")
        self.assertTrue(any(isinstance(item, ast.Raise) for item in linked.body))
        self.assertLess(linked.lineno, self.one(install, "_InstallTransaction").lineno)

    def test_source_names_match_instruction_scope(self):
        names = self.fn("_claude_instruction_source_names")
        for text in ('("agents", "commands")', 'item.suffix.casefold() == ".md"',
                     '"__pycache__" not in item.relative_to(source / scope).parts',
                     'scope == "commands" or len(item.relative_to(source / scope).parts) == 1'):
            self.require(names, text)

    def test_selected_receipt_is_admitted_in_same_transaction(self):
        install = self.fn("install")
        admission = next(node for node in ast.walk(install) if isinstance(node, ast.If)
                         and shape(node.test) == shape(expression("instruction_grants")))
        self.require(admission, "transaction_paths.append(target / _PROVIDER_RECEIPT_NAME)")
        transaction = self.one(install, "_InstallTransaction")
        self.assertLess(admission.lineno, transaction.lineno)
        self.assertTrue(any(kw.arg == "track_fresh_files" and
                            contains(kw.value, "fresh_receipt is not None or bool(instruction_grants)")
                            for kw in transaction.keywords))
        prepare = self.one(install, "_prepare_selected_claude_instructions")
        self.assertEqual(ast.unparse(prepare.args[-1]), "create_only")
        self.assertLess(transaction.lineno, prepare.lineno)
        content_writes = calls(install, "_install_ui_continuity_contract")
        self.assertTrue(content_writes)
        self.assertTrue(all(prepare.lineno < call.lineno for call in content_writes))
        for name in ("_sync_tree", "_normalize_agents_mode", "_apply_canonical_skills_plan"):
            self.assertTrue(all(prepare.lineno < call.lineno for call in calls(install, name)))

    def test_preflight_binds_exact_current_source_and_receipt_before_planning(self):
        prepare = self.fn("_prepare_selected_claude_instructions")
        guard = self.guard(prepare, "not grants")
        self.assertEqual(ast.unparse(guard.body[0]), "return None")
        for text in ("_admitted_mutation_image(transaction, receipt).get(receipt)",
                     "transaction._image_file_bytes(receipt, receipt_node)",
                     "owner._file_parent_identities(receipt)",
                     "_admitted_mutation_image(transaction, path).get(path)",
                     "owner._assert_bound_file(path, before_node, parents)",
                     "hashlib.sha256(before).hexdigest() != digest",
                     "transaction._capture_node(source_path)",
                     "transaction._image_file_bytes(source_path, source_node)",
                     '_ReceiptOutcome(".claude/" + key, "file", before, after, intent="replace", adoption_sha256=digest)',
                     'item.route != "selected-replacement-proposal"'):
            self.require(prepare, text)
        plan = self.one(prepare, "_plan_receipt_changes")
        self.assertLess(calls(prepare, "_image_file_bytes")[-1].lineno, plan.lineno)
        self.assertLess(plan.lineno, self.one(prepare, "_serialize_receipt_delta").lineno)
        for writer in ("write_file", "copy_file", "create_file", "replace_exact_file"):
            self.assertEqual(calls(prepare, writer), [])

    def test_selected_sync_precedes_preservation_and_both_scopes_receive_batch(self):
        sync = self.fn("_sync_tree")
        branch = self.guard(sync, "instruction_updates is not None and key in instruction_updates.items")
        self.one(branch, "_apply_selected_claude_instruction")
        self.assertIsInstance(branch.body[-1], ast.Continue)
        self.assertLess(branch.end_lineno, self.one(sync, "_admitted_mutation_image").lineno)
        self.assertLess(branch.end_lineno, self.one(sync, "_copy_file").lineno)
        scoped = [call for call in calls(self.fn("install"), "_sync_tree")
                  if any(kw.arg == "instruction_scope" for kw in call.keywords)]
        self.assertEqual(len(scoped), 2)
        self.assertEqual({ast.literal_eval(next(kw.value for kw in call.keywords
                                               if kw.arg == "instruction_scope"))
                          for call in scoped}, {"agents", "commands"})
        for call in scoped:
            self.assertTrue(any(kw.arg == "instruction_updates" and
                                ast.unparse(kw.value) == "instruction_updates"
                                for kw in call.keywords))

    def test_apply_checks_before_write_and_records_received_after_bound_outcome(self):
        apply = self.fn("_apply_selected_claude_instruction")
        for text in ("owner is not batch.owner", "owner.linked_authority is not None",
                     "Path(os.path.abspath(source)) != selected.source",
                     "Path(os.path.abspath(path)) != selected.path", "key in batch.received"):
            self.require(apply, text)
        write = self.one(apply, "replace_exact_file")
        self.assertEqual(ast.unparse(write),
                         "owner.replace_exact_file(selected.path.relative_to(owner.anchor), selected.digest, selected.after)")
        changed = self.guard(apply, "selected.before != selected.after")
        self.assertIs(changed.body[0].value, write)
        for check in ("_image_file_bytes", "_assert_bound_file"):
            self.assertLess(self.one(apply, check).lineno, write.lineno)
        dry = self.guard(apply, "dry_run")
        self.assertIsInstance(dry.body[-1], ast.Return)
        self.assertLess(dry.end_lineno, write.lineno)
        outcome = self.one(apply, "_assert_selected_claude_instruction")
        self.assertLess(write.lineno, outcome.lineno)
        self.assertEqual(ast.unparse(apply.body[-1]), "batch.received[key] = node")
        self.assertLess(outcome.lineno, apply.body[-1].lineno)
        for name in ("_record_fresh_file", "_fresh_file_parents", "create_file"):
            self.assertEqual(calls(apply, name), [])
        bound = self.fn("_assert_selected_claude_instruction")
        self.require(bound, "owner.transaction._image_file_bytes(selected.source, selected.source_node) != selected.after")
        self.require(bound, "owner._assert_bound_file(selected.path, node, selected.parents) != selected.after")

    def test_finalizer_requires_complete_outcomes_and_merges_through_existing_codec(self):
        final = self.fn("_record_selected_claude_receipt")
        guard = self.guard(final, "not transaction.enabled or set(batch.received) != set(batch.items)")
        self.assertIsInstance(guard.body[0], ast.Raise)
        collect = self.one(final, "_fresh_provider_receipt_files")
        self.assertLess(guard.lineno, collect.lineno)
        self.require(final, "key not in selected_keys")
        self.require(final, 'batch.outcomes + tuple(_ReceiptOutcome(key, "file", None, owner._assert_fresh_file(witness), intent="create") for key, witness in fresh.items())')
        plan = self.one(final, "_plan_receipt_changes")
        self.require(final, '{item.path: ("selected-replacement-proposal" if item.intent == "replace" else "creation-proposal") for item in outcomes}')
        conflict = self.guard(final, "{item.path: item.route for item in plan.artifacts} != expected_routes")
        self.assertIsInstance(conflict.body[0], ast.Raise)
        self.require(conflict, 'ValueError("E_CLAUDE_INSTRUCTION_SELECTION_INVALID: receipt outcome conflict")')
        self.assertLess(plan.lineno, conflict.lineno)
        for name in ("_serialize_receipt_delta", "create_file", "replace_exact_file"):
            self.assertLess(conflict.end_lineno, self.one(final, name).lineno)
        self.assertEqual(calls(final, "dumps"), [])
        self.require(final, "batch.payload")
        checks = calls(final, "_assert_selected_claude_instruction")
        self.assertEqual(len(checks), 2)
        self.assertLess(checks[0].lineno, collect.lineno)
        self.assertGreater(checks[1].lineno, self.one(final, "replace_exact_file").lineno)

    def test_receipt_absence_requires_fresh_witness_existing_requires_bound_exact_writer(self):
        final = self.fn("_record_selected_claude_receipt")
        absent = self.guard(final, "batch.receipt_node is None")
        create = self.one(absent, "create_file")
        self.assertLess(self.one(absent, "_image_matches").lineno, create.lineno)
        self.require(absent, "transaction._fresh_files[start:]")
        self.require(absent, "witness.owner is owner and witness.path == batch.receipt")
        count = self.guard(absent, "len(created) != 1")
        self.assertIsInstance(count.body[0], ast.Raise)
        self.assertGreater(count.lineno, create.lineno)
        existing = ast.Module(body=absent.orelse, type_ignores=[])
        self.require(existing, "owner._assert_bound_file(batch.receipt, batch.receipt_node, batch.receipt_parents) != batch.receipt_before")
        changed = self.guard(existing, "payload != batch.receipt_before")
        replace = self.one(changed, "replace_exact_file")
        self.require(replace, "hashlib.sha256(batch.receipt_before).hexdigest()")
        self.assertLess(self.one(existing, "_assert_bound_file").lineno, replace.lineno)
        self.assertEqual(calls(final, "replace_file_atomic"), [])
        self.require(final.body[-1], "owner._assert_bound_file(batch.receipt, receipt_after, batch.receipt_parents) != payload")
        self.assertGreater(calls(final, "_assert_fresh_file")[-1].lineno, replace.lineno)

    def test_exactly_one_receipt_branch_finalizes_before_commit(self):
        install = self.fn("install")
        branch = self.guard(install, "instruction_updates is not None")
        selected = self.one(branch, "_record_selected_claude_receipt")
        self.assertIs(branch.body[0].value, selected)
        self.assertEqual(len(branch.body), 1)
        self.assertEqual(len(branch.orelse), 1)
        self.one(ast.Module(body=branch.orelse, type_ignores=[]), "_record_fresh_provider_receipt")
        commit = self.one(install, "commit")
        self.assertLess(branch.end_lineno, commit.lineno)
        scope = next(node for node in ast.walk(install) if isinstance(node, ast.With)
                     and any(ast.unparse(item.context_expr) == "transaction" for item in node.items))
        self.assertIs(scope.body[-2], branch)
        self.assertIs(scope.body[-1].value, commit)


if __name__ == "__main__":
    unittest.main()
