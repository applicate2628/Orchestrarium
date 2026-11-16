"""Pure refusal-path tests. No installer import or filesystem effects."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "production_installer.py"


class Unobserved:
    def __getattribute__(self, name):
        raise AssertionError("Refusal inspected an input: " + name)


class TransactionDisposalHoldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        cls.helper = next(n for n in cls.tree.body if isinstance(n, ast.FunctionDef)
                          and n.name == "_require_transaction_disposal_backend")
        cls.owner = next(n for n in cls.tree.body if isinstance(n, ast.ClassDef)
                         and n.name == "_InstallTransaction")
        cls.methods = {n.name: n for n in cls.owner.body if isinstance(n, ast.FunctionDef)}

    def load(self, platform, method=None):
        nodes = [self.helper]
        if method:
            nodes.append(self.methods[method])
        module = ast.Module(body=[ast.ImportFrom(module="__future__",
                            names=[ast.alias(name="annotations")], level=0), *nodes],
                            type_ignores=[])
        namespace = {"os": SimpleNamespace(name=platform)}
        exec(compile(ast.fix_missing_locations(module), str(SOURCE), "exec"), namespace)
        return namespace

    def test_posix_negative_gate(self):
        with self.assertRaisesRegex(ValueError, "E_EFFECT_BOUND_DISPOSAL_UNQUALIFIED"):
            self.load("posix")["_require_transaction_disposal_backend"]()

    def test_unknown_backend_refused(self):
        for platform in ("", "unknown", None):
            with self.subTest(platform=platform), self.assertRaises(ValueError):
                self.load(platform)["_require_transaction_disposal_backend"]()

    def test_windows_negative_gate_is_not_an_effect(self):
        self.assertIsNone(self.load("nt")["_require_transaction_disposal_backend"]())

    def test_node_refuses_before_observing_inputs(self):
        for value in (None, Unobserved()):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaisesRegex(ValueError, "E_EFFECT_BOUND_DISPOSAL_UNQUALIFIED"):
                    self.load("posix", "_dispose_node")["_dispose_node"](value, value, value)

    def test_image_refuses_before_iteration_or_permissions(self):
        for value in (None, Unobserved()):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaisesRegex(ValueError, "E_EFFECT_BOUND_DISPOSAL_UNQUALIFIED"):
                    self.load("posix", "_dispose_image")["_dispose_image"](value, value, value)

    def test_guard_is_first_statement_in_both_owners(self):
        expected = ast.dump(ast.parse("_require_transaction_disposal_backend()").body[0])
        for name in ("_dispose_node", "_dispose_image"):
            self.assertEqual(ast.dump(self.methods[name].body[0]), expected)

    def test_removed_posix_deletion_branch(self):
        node = self.methods["_dispose_node"]
        self.assertEqual(len(node.body), 3)  # guard, witness check, unchanged Windows branch
        self.assertEqual(ast.unparse(node.body[-1].test), "os.name == 'nt'")
        for call in (n for n in ast.walk(node) if isinstance(n, ast.Call)):
            self.assertNotIn(ast.unparse(call.func), {"os.unlink", "os.rmdir", "operation"})

    def test_image_has_no_permission_mutation_before_disposal(self):
        calls = [ast.unparse(n.func) for n in ast.walk(self.methods["_dispose_image"])
                 if isinstance(n, ast.Call)]
        self.assertNotIn("self._clear_owned_readonly", calls)
        self.assertIn("self._dispose_node", calls)


if __name__ == "__main__":
    unittest.main()
