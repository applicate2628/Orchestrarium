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
                         and shape(node.test) == shape(expression("selected_requested")))
        self.require(admission, "transaction_paths.append(target / _PROVIDER_RECEIPT_NAME)")
        transaction = self.one(install, "_InstallTransaction")
        self.assertLess(admission.lineno, transaction.lineno)
        self.assertTrue(any(kw.arg == "track_fresh_files" and
                            contains(kw.value, "fresh_receipt is not None or selected_requested")
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
        for text in ("_admitted_mutation_image(transaction, path).get(path)",
                     "owner._assert_bound_file(path, before_node, parents)",
                     "hashlib.sha256(before).hexdigest() != digest",
                     "_capture_selected_source(source / key, transaction)",
                     "selected_source.raw",
                     "_SelectedReplacement((selected_source,), path, before_node, before, after, digest, parents)",
                     '_ReceiptOutcome(".claude/" + key, "file", before, after, intent="replace", adoption_sha256=digest)'):
            self.require(prepare, text)
        capture = self.fn("_capture_selected_source")
        for text in ("Path(os.path.abspath(path))", "transaction._capture_node(path)",
                     "_SelectedSource(path, node, transaction._image_file_bytes(path, node))"):
            self.require(capture, text)
        handoff = self.one(prepare, "_prepare_selected_provider_updates")
        self.assertEqual(ast.unparse(handoff),
                         "_prepare_selected_provider_updates('claude', scope, target / _PROVIDER_RECEIPT_NAME, owner, items, tuple(outcomes))")
        self.assertLess(self.one(prepare, "_capture_selected_source").lineno, handoff.lineno)
        shared = self.fn("_prepare_selected_provider_updates")
        for text in ("_admitted_mutation_image(transaction, receipt).get(receipt)",
                     "transaction._image_file_bytes(receipt, receipt_node)",
                     "owner._file_parent_identities(receipt)",
                     'item.route != "selected-replacement-proposal"'):
            self.require(shared, text)
        plan = self.one(shared, "_plan_receipt_changes")
        self.require(plan, "provider")
        self.assertLess(self.one(shared, "_image_file_bytes").lineno, plan.lineno)
        self.assertLess(plan.lineno, self.one(shared, "_serialize_receipt_delta").lineno)
        for node in (prepare, capture, shared):
            for writer in ("write_file", "copy_file", "create_file", "replace_exact_file"):
                self.assertEqual(calls(node, writer), [])

    def test_shared_records_retain_raw_source_and_provider_identity(self):
        expected = {
            "_SelectedSource": ["path", "node", "raw"],
            "_SelectedReplacement": ["sources", "path", "before_node", "before",
                                     "after", "digest", "parents"],
            "_SelectedProviderUpdates": ["provider", "owner", "scope", "receipt",
                "receipt_node", "receipt_before", "receipt_parents",
                "receipt_parent_preimage", "items", "outcomes", "payload", "received"],
        }
        for name, fields in expected.items():
            node = self.fn(name)
            self.require(node, "dataclass(frozen=True)")
            self.assertEqual([item.target.id for item in node.body
                              if isinstance(item, ast.AnnAssign)], fields)
        error = self.fn("_selected_error")
        self.require(error, '"CLAUDE_INSTRUCTION" if provider == "claude" else "CODEX_DOCUMENT"')
        self.require(error, '"INVALID" if invalid else "DRIFT"')

    def test_selected_sync_precedes_preservation_and_both_scopes_receive_batch(self):
        sync = self.fn("_sync_tree")
        branch = self.guard(sync, "instruction_updates is not None and key in instruction_updates.items")
        self.one(branch, "_apply_selected_replacement")
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
        apply = self.fn("_apply_selected_replacement")
        for text in ("owner is not batch.owner", "owner.linked_authority is not None",
                     "tuple(Path(os.path.abspath(source)) for source in source_paths) != tuple(source.path for source in selected.sources)",
                     "Path(os.path.abspath(path)) != selected.path", "key in batch.received"):
            self.require(apply, text)
        write = self.one(apply, "replace_exact_file")
        self.assertEqual(ast.unparse(write),
                         "owner.replace_exact_file(selected.path.relative_to(owner.anchor), selected.digest, selected.after)")
        changed = self.guard(apply, "selected.before != selected.after")
        self.assertIs(changed.body[0].value, write)
        for check in ("_assert_selected_sources", "_assert_bound_file"):
            self.assertLess(self.one(apply, check).lineno, write.lineno)
        dry = self.guard(apply, "dry_run")
        self.assertIsInstance(dry.body[-1], ast.Return)
        self.assertLess(dry.end_lineno, write.lineno)
        outcome = self.one(apply, "_assert_selected_replacement")
        self.assertLess(write.lineno, outcome.lineno)
        self.assertEqual(ast.unparse(apply.body[-1]), "batch.received[key] = node")
        self.assertLess(outcome.lineno, apply.body[-1].lineno)
        for name in ("_record_fresh_file", "_fresh_file_parents", "create_file"):
            self.assertEqual(calls(apply, name), [])
        bound = self.fn("_assert_selected_replacement")
        self.require(bound, "_assert_selected_sources(selected, owner, provider)")
        sources = self.fn("_assert_selected_sources")
        self.require(sources, "selected.sources")
        self.require(sources, "owner.transaction._image_file_bytes(source.path, source.node) != source.raw")
        self.require(sources, '_selected_error(provider, "source")')
        self.require(apply, "_assert_selected_sources(selected, owner, batch.provider)")
        self.require(apply, "owner._assert_bound_file(selected.path, selected.before_node, selected.parents) != selected.before")
        self.require(apply, "_assert_selected_replacement(selected, owner, node, batch.provider)")
        self.require(bound, "owner._assert_bound_file(selected.path, node, selected.parents) != selected.after")

    def test_finalizer_requires_complete_outcomes_and_merges_through_existing_codec(self):
        final = self.fn("_record_selected_provider_receipt")
        guard = self.guard(final, "not transaction.enabled or set(batch.received) != set(batch.items)")
        self.assertIsInstance(guard.body[0], ast.Raise)
        collect = self.one(final, "_fresh_provider_receipt_files")
        self.assertEqual(ast.unparse(collect.args[0]), "batch.provider")
        self.assertLess(guard.lineno, collect.lineno)
        self.require(final, "key not in selected_keys")
        self.require(final, 'batch.outcomes + tuple(_ReceiptOutcome(key, "file", None, owner._assert_fresh_file(witness), intent="create") for key, witness in fresh.items())')
        plan = self.one(final, "_plan_receipt_changes")
        self.require(final, '{item.path: ("selected-replacement-proposal" if item.intent == "replace" else "creation-proposal") for item in outcomes}')
        conflict = self.guard(final, "{item.path: item.route for item in plan.artifacts} != expected_routes")
        self.assertIsInstance(conflict.body[0], ast.Raise)
        self.require(conflict, '_selected_error(batch.provider, "receipt outcome conflict", invalid=True)')
        self.assertLess(plan.lineno, conflict.lineno)
        for name in ("_serialize_receipt_delta", "create_file", "replace_exact_file"):
            self.assertLess(conflict.end_lineno, self.one(final, name).lineno)
        self.assertEqual(calls(final, "dumps"), [])
        self.require(final, "batch.payload")
        checks = calls(final, "_assert_selected_replacement")
        self.assertEqual(len(checks), 2)
        self.assertLess(checks[0].lineno, collect.lineno)
        self.assertGreater(checks[1].lineno, self.one(final, "replace_exact_file").lineno)

    def test_receipt_absence_requires_fresh_witness_existing_requires_bound_exact_writer(self):
        final = self.fn("_record_selected_provider_receipt")
        absent = next(node for node in final.body if isinstance(node, ast.If)
                      and contains(node.test, "batch.receipt_node is None"))
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
        readback = [node for node in final.body if isinstance(node, ast.If)
                    and contains(node.test, "batch.receipt_node is None")][-1]
        self.require(readback, "actual")
        self.require(readback, "owner._assert_fresh_file(created[0])")
        self.require(readback, "owner._assert_bound_file(batch.receipt, receipt_after, batch.receipt_parents)")
        self.require(final.body[-1], "actual != payload")
        self.assertGreater(calls(final, "_assert_fresh_file")[-1].lineno, replace.lineno)

    def test_absent_receipt_uses_parent_preimage_without_readonly_leaf_registration(self):
        prepare = self.fn("_prepare_selected_provider_updates")
        absent = self.guard(prepare, "receipt_node is None")
        self.require(absent, "_selected_receipt_parent_preimage(receipt, transaction)")
        self.require(absent, "transaction._assert_readonly_parents(receipt_parent_preimage)")
        self.assertEqual(calls(prepare, "register_readonly"), [])
        parents = self.fn("_selected_receipt_parent_preimage")
        for text in ("tuple(transaction._original)",
                     "transaction._capture_readonly_parents(receipt, covered)",
                     "parent == root or root in parent.parents",
                     "any(node != originals[0] for node in originals[1:])",
                     "parents[parent]", "originals[0]"):
            self.require(parents, text)
        self.assertEqual(calls(parents, "register_readonly"), [])
        final = self.fn("_record_selected_provider_receipt")
        branch = next(node for node in final.body if isinstance(node, ast.If)
                      and contains(node.test, "batch.receipt_node is None"))
        create = self.one(branch, "create_file")
        checks = calls(branch, "_assert_readonly_parents")
        self.assertEqual(len(checks), 2)
        self.assertLess(checks[0].lineno, create.lineno)
        self.assertGreater(checks[1].lineno, create.lineno)
        self.require(branch, "owner._assert_fresh_file(created[0]) != payload")
        self.assertEqual(calls(final, "register_readonly"), [])

    def test_exactly_one_receipt_branch_finalizes_before_commit(self):
        install = self.fn("install")
        branch = self.guard(install, "selected_updates is not None")
        selected = self.one(branch, "_record_selected_provider_receipt")
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
