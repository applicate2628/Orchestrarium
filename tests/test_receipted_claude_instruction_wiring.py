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
        self.assertLess(guard.end_lineno, self.one(install, "_target").lineno)
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

    def test_selected_linked_roots_refuse_before_individual_preimages(self):
        prepare = self.fn("_prepare_receipted_claude_instructions")
        linked = self.branch(prepare, 'any(key.split("/")[0] in linked_subroots for key in grants)')
        self.assertIsInstance(linked.body[0], ast.Raise)
        individual = self.one(prepare, "_prepare_selected_claude_instructions")
        self.assertLess(linked.end_lineno, individual.lineno)
        self.assertEqual(ast.unparse(individual),
                         "_prepare_selected_claude_instructions(grants, source, target, scope, owner)")

    def test_shared_preparation_keeps_old_current_byte_and_source_checks(self):
        prepare = self.fn("_prepare_selected_claude_instructions")
        check = self.branch(prepare, "hashlib.sha256(before).hexdigest() != digest")
        self.assertIsInstance(check.body[0], ast.Raise)
        self.assertLess(check.end_lineno, self.one(prepare, "_capture_selected_source").lineno)
        self.require(prepare, "owner._assert_bound_file(path, before_node, parents)")
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
        self.one(install, "_record_selected_provider_receipt")
        self.one(install, "_record_fresh_provider_receipt")
        self.assertEqual(calls(prepare, "_plan_receipt_changes"), [])

    def test_posix_hold_and_default_instruction_route_are_preserved(self):
        install = self.fn("install")
        hold = self.branch(install, 'os.name == "posix"')
        self.assertIsInstance(hold.body[-1], ast.Return)
        self.assertLess(hold.end_lineno, self.one(install, "_target").lineno)
        default = self.one(install, "_prepare_selected_claude_instructions")
        selected = self.one(install, "_prepare_receipted_claude_instructions")
        self.assertLess(default.lineno, selected.lineno)
        self.require(default, "instruction_grants")
        self.require(install, "document_grant is not None")
