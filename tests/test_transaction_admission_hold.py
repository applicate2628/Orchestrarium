"""Pure tests of admission refusal; no installer import or native effects."""
import ast
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "production_installer.py"


class Unobserved:
    def __getattribute__(self, name):
        raise AssertionError("Unexpected transaction observation: " + name)


class EnabledOnly:
    enabled = True
    def __getattribute__(self, name):
        if name == "enabled":
            return True
        raise AssertionError("Snapshot touched input before admission: " + name)


class TransactionAdmissionHoldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        cls.helper = next(n for n in cls.tree.body if isinstance(n, ast.FunctionDef)
                          and n.name == "_require_transaction_disposal_backend")
        cls.owner = next(n for n in cls.tree.body if isinstance(n, ast.ClassDef)
                         and n.name == "_InstallTransaction")
        cls.methods = {n.name: n for n in cls.owner.body if isinstance(n, ast.FunctionDef)}

    def load(self, platform, method):
        module = ast.Module(body=[ast.ImportFrom(module="__future__",
            names=[ast.alias(name="annotations")], level=0), self.helper, self.methods[method]],
            type_ignores=[])
        ns = {"os": SimpleNamespace(name=platform), "contextmanager": contextmanager}
        exec(compile(ast.fix_missing_locations(module), str(SOURCE), "exec"), ns)
        return ns[method]

    def test_enabled_snapshot_refuses_before_paths_and_allocation(self):
        with self.assertRaisesRegex(ValueError, "E_EFFECT_BOUND_DISPOSAL_UNQUALIFIED"):
            self.load("posix", "__enter__")(EnabledOnly())

    def test_empty_disabled_context_remains_noop(self):
        owner = SimpleNamespace(enabled=False)
        for platform in ("posix", "nt", "unknown"):
            with self.subTest(platform=platform):
                self.assertIs(self.load(platform, "__enter__")(owner), owner)

    def test_direct_scope_refuses_before_observing_transaction(self):
        with self.assertRaisesRegex(ValueError, "E_EFFECT_BOUND_DISPOSAL_UNQUALIFIED"):
            with self.load("posix", "direct_operation")(Unobserved()):
                self.fail("Unqualified scope yielded")

    def test_enabled_nested_and_disabled_direct_scopes_all_refuse(self):
        for enabled, depth in ((True, 0), (False, 0), (False, 1), (True, 1)):
            owner = SimpleNamespace(enabled=enabled, _direct_operation_depth=depth)
            with self.subTest(enabled=enabled, depth=depth), self.assertRaises(ValueError):
                with self.load("posix", "direct_operation")(owner):
                    self.fail("Unqualified scope yielded")

    def test_unknown_backend_refuses_snapshot_and_direct_scope(self):
        with self.assertRaises(ValueError):
            self.load("unknown", "__enter__")(EnabledOnly())
        with self.assertRaises(ValueError):
            with self.load("unknown", "direct_operation")(Unobserved()):
                self.fail("Unknown scope yielded")

    def test_direct_gate_precedes_fast_path(self):
        self.assertEqual(ast.unparse(self.methods["direct_operation"].body[0]),
                         "_require_transaction_disposal_backend()")

    def test_snapshot_gate_follows_only_empty_disabled_return(self):
        body = self.methods["__enter__"].body
        self.assertEqual(ast.unparse(body[0]), "if not self.enabled:\n    return self")
        self.assertEqual(ast.unparse(body[1]), "_require_transaction_disposal_backend()")
        self.assertTrue(ast.unparse(body[2]).startswith("self.paths = "))


if __name__ == "__main__":
    unittest.main()
