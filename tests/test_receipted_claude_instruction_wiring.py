"""AST contracts for explicit receipt-selected current instruction migration.

Never import, execute or mock the installer or physical owner. These tests do
not establish historical authority, physical replacement or recovery safety.
"""
import ast
from pathlib import Path
import unittest

from test_fresh_provider_wiring import calls, contains, expression, named, shape

ROOT = Path(__file__).resolve().parents[1]


class ReceiptedClaudeInstructionWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse((ROOT / "scripts/production_installer.py").read_bytes())

    def fn(self, name):
        return named(self.tree, name)

    def require(self, node, text):
        self.assertTrue(contains(node, text), text)

    def one(self, node, name):
        found = calls(node, name)
        self.assertEqual(len(found), 1, name)
        return found[0]

    def branch(self, node, text):
        found = [item for item in ast.walk(node)
                 if isinstance(item, ast.If) and shape(item.test) == shape(expression(text))]
        self.assertEqual(len(found), 1, text)
        return found[0]

    def test_receipt_selection_is_explicit_strict_and_mutually_exclusive(self):
        options = [call for call in calls(self.fn("_parser"), "add_argument")
                   if call.args and contains(call.args[0], '"--replace-claude-receipted-instructions"')]
        self.assertEqual(len(options), 1)
        kw = {item.arg: ast.literal_eval(item.value) for item in options[0].keywords}
        self.assertEqual((kw["action"], kw["default"], kw["metavar"]),
                         ("append", [], "RECEIPT_SHA256"))
        self.assertIn("not historical ownership", kw["help"])
        install = self.fn("install")
        guard = self.branch(install, 'args.replace_claude_receipted_instructions and (provider != "claude" or args.replace_claude_instruction)')
        self.assertIsInstance(guard.body[-1], ast.Return)
        parse = self.one(install, "_parse_claude_receipt_grant")
        self.require(parse, "tuple(args.replace_claude_receipted_instructions)")
        targets = calls(install, "_target")
        self.assertTrue(targets)
        self.assertTrue(all(guard.end_lineno < call.lineno for call in targets))
        self.assertLess(guard.end_lineno, parse.lineno)
        self.assertNotIn("force", ast.unparse(parse))

    def test_same_receipt_is_admitted_before_preparation_and_content_writes(self):
        install = self.fn("install")
        self.require(install, "bool(instruction_grants) or document_grant is not None or receipt_grant is not None")
        admit = self.branch(install, "selected_requested")
        self.require(admit, "transaction_paths.append(target / _PROVIDER_RECEIPT_NAME)")
        prepare = self.one(install, "_prepare_receipted_claude_instructions")
        self.assertLess(admit.lineno, self.one(install, "_InstallTransaction").lineno)
        self.assertLess(self.one(install, "_InstallTransaction").lineno, prepare.lineno)
        for name in ("_install_ui_continuity_contract", "_sync_tree",
                     "_normalize_agents_mode", "_apply_canonical_skills_plan"):
            found = calls(install, name)
            self.assertTrue(found)
            self.assertTrue(all(prepare.lineno < call.lineno for call in found), name)
        branch = self.branch(install, "receipt_grant is not None")
        self.assertEqual(ast.unparse(branch.body[0].targets[0]), "instruction_updates")
        self.require(prepare, "create_only")
        self.require(prepare, "tuple(authority.name for authority in claude_link_authorities)")

    def test_receipt_selection_binds_raw_input_node_and_parents(self):
        prepare = self.fn("_prepare_receipted_claude_instructions")
        for text in ("owner.destination((target / _PROVIDER_RECEIPT_NAME).relative_to(owner.anchor))",
                     "_admitted_mutation_image(transaction, receipt).get(receipt)",
                     "owner._file_parent_identities(receipt)",
                     "owner._assert_bound_file(receipt, node, parents)"):
            self.require(prepare, text)
        select = self.one(prepare, "_claude_instruction_grants_from_receipt")
        self.require(select, "before")
        self.require(select, "receipt_digest")
        self.require(select, "scope")
        self.one(select, "_claude_instruction_source_names")
        self.assertLess(calls(prepare, "_assert_bound_file")[0].lineno, select.lineno)
        self.assertEqual(calls(prepare, "read_bytes"), [])

    def test_selected_linked_roots_require_physical_owner_before_preimages(self):
        prepare = self.fn("_prepare_receipted_claude_instructions")
        linked = self.branch(prepare, 'any(key.split("/")[0] in linked_subroots and key.split("/")[0] not in (instruction_owners or {}) for key in grants)')
        self.assertIsInstance(linked.body[0], ast.Raise)
        individual = self.one(prepare, "_prepare_selected_claude_instructions")
        self.assertLess(linked.end_lineno, individual.lineno)
        self.assertEqual(ast.unparse(individual),
                         "_prepare_selected_claude_instructions(grants, source, target, scope, owner, instruction_owners=instruction_owners)")

    def test_shared_preparation_keeps_old_current_byte_and_source_checks(self):
        prepare = self.fn("_prepare_selected_claude_instructions")
        check = self.branch(prepare, "hashlib.sha256(before).hexdigest() != digest")
        self.assertIsInstance(check.body[0], ast.Raise)
        self.assertLess(check.end_lineno, self.one(prepare, "_capture_selected_source").lineno)
        self.require(prepare, "physical_owner._assert_bound_file(path, before_node, parents)")
        self.require(prepare, '_ReceiptOutcome(".claude/" + key, "file", before, after, intent="replace", adoption_sha256=digest)')
        self.one(prepare, "_prepare_selected_provider_updates")

    def test_preparer_must_return_same_receipt_binding_and_recheck_before_return(self):
        prepare = self.fn("_prepare_receipted_claude_instructions")
        binding = self.branch(prepare, "batch is None or batch.receipt != receipt or batch.receipt_node != node or batch.receipt_before != before or batch.receipt_parents != parents")
        self.assertIsInstance(binding.body[0], ast.Raise)
        self.assertLess(self.one(prepare, "_prepare_selected_claude_instructions").lineno, binding.lineno)
        current = self.branch(prepare, "owner._assert_bound_file(receipt, node, parents) != before")
        self.assertIsInstance(current.body[0], ast.Raise)
        self.assertLess(binding.end_lineno, current.lineno)
        self.assertEqual(ast.unparse(prepare.body[-1]), "return batch")
        self.assertLess(current.end_lineno, prepare.body[-1].lineno)

    def test_no_new_effects_authority_or_receipt_owner_are_introduced(self):
        prepare = self.fn("_prepare_receipted_claude_instructions")
        for name in ("create_file", "write_file", "copy_file", "replace_exact_file",
                     "serialize_delta", "decode_record", "encode_record",
                     "bind_readonly_path", "register_readonly", "commit"):
            self.assertEqual(calls(prepare, name), [], name)
        install = self.fn("install")
        scopes = [node for node in ast.walk(install) if isinstance(node, ast.With)
                  and any(shape(item.context_expr) == shape(expression("transaction"))
                          for item in node.items)]
        self.assertEqual(len(scopes), 1)
        scope = scopes[0]
        final = self.one(scope, "_record_provider_install")
        self.assertEqual([ast.unparse(arg) for arg in final.args[5:8]],
                         ["transaction", "create_only", "ownership_before"])
        self.assertEqual({item.arg: ast.unparse(item.value) for item in final.keywords}
                         ["selected_updates"], "selected_updates")
        self.assertIs(scope.body[-2].value, final)
        self.assertEqual(ast.unparse(scope.body[-1]), "transaction.commit()")
        self.assertEqual(calls(install, "_record_selected_provider_receipt"), [])
        self.assertEqual(calls(install, "_record_fresh_provider_receipt"), [])
        finalizer = self.fn("_record_provider_install")
        for body in (finalizer, self.fn("_provider_payload_bindings"),
                     self.fn("_provider_payload_path")):
            for name in ("_InstallTransaction", "_CreateOnlyMutablePath", "bind_or_create_anchor",
                         "bind_readonly_path", "register_readonly", "bind", "resolve", "_target"):
                self.assertEqual(calls(body, name), [], name)
        for binding in ("batch.owner is not owner", "batch.provider != provider",
                        "batch.scope != scope", "batch.receipt != target / codec.RECEIPT_NAME",
                        "set(batch.received) != set(batch.items)"):
            self.require(finalizer, binding)
        publication = self.one(finalizer, "replace_exact_file")
        self.assertEqual(ast.unparse(publication),
                         "owner.replace_exact_file(relative, hashlib.sha256(selected_updates.receipt_before).hexdigest(), payload)")
        checks = calls(finalizer, "_assert_selected_replacement")
        self.assertEqual(len(checks), 2)
        self.assertLess(checks[0].lineno, publication.lineno)
        self.assertLess(publication.lineno, checks[1].lineno)
        self.assertEqual(calls(prepare, "_plan_receipt_changes"), [])

    def test_owner_platform_admission_and_default_instruction_route_are_preserved(self):
        install = self.fn("install")
        owner = named(self.fn("_InstallTransaction"), "__enter__")
        disabled = self.branch(owner, "not self.enabled")
        self.assertIsInstance(disabled.body[-1], ast.Return)
        guard = self.one(owner, "_require_transaction_disposal_backend")
        self.assertEqual(shape(owner.body[1]), shape(ast.Expr(value=guard)))
        self.assertLess(guard.lineno, self.one(owner, "_allocate_owned_directory").lineno)
        default = self.one(install, "_prepare_selected_claude_instructions")
        selected = self.one(install, "_prepare_receipted_claude_instructions")
        self.assertLess(default.lineno, selected.lineno)
        self.require(default, "instruction_grants")
        self.require(install, "document_grant is not None")
