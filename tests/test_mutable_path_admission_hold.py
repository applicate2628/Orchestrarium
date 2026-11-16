"""Pure entry refusal tests; no native owner acquisition or effects."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "production_installer.py"
NAMES = {"_ensure_directory_path", "bind_or_create_anchor", "migrate_exact_file",
         "create_projection", "rollback_migrated"}


class Unobserved:
    def __getattribute__(self, name):
        raise AssertionError("Entry observed input before refusal: " + name)


class MutablePathAdmissionHoldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        cls.helper = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                          and n.name == "_require_transaction_disposal_backend")
        owner = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                     and n.name == "_CreateOnlyMutablePath")
        cls.methods = {n.name: n for n in owner.body
                       if isinstance(n, ast.FunctionDef) and n.name in NAMES}
        cls.extracted = ast.ClassDef(name="_CreateOnlyMutablePath", bases=[],
            keywords=[], body=list(cls.methods.values()), decorator_list=[])

    def load(self, platform="posix"):
        module = ast.Module(body=[ast.ImportFrom(module="__future__",
            names=[ast.alias(name="annotations")], level=0), self.helper, self.extracted],
            type_ignores=[])
        ns = {"os": SimpleNamespace(name=platform)}
        exec(compile(ast.fix_missing_locations(module), str(SOURCE), "exec"), ns)
        return ns["_CreateOnlyMutablePath"]

    def refuse(self, name, platform="posix"):
        owner = self.load(platform)
        value = Unobserved()
        with self.assertRaisesRegex(ValueError, "E_EFFECT_BOUND_DISPOSAL_UNQUALIFIED"):
            if name == "bind_or_create_anchor":
                owner.bind_or_create_anchor(value, value, admitted_parent=value,
                                            parent_state=value, dry_run=True)
            elif name == "migrate_exact_file":
                owner.migrate_exact_file(value, value, value, value)
            elif name == "create_projection":
                owner.create_projection(value, value, value)
            else:
                getattr(owner, name)(value, value)

    def test_directory_before_existence_or_creation(self):
        self.refuse("_ensure_directory_path")

    def test_anchor_before_paths_or_dry_run(self):
        self.refuse("bind_or_create_anchor")

    def test_migration_before_selection_or_staging(self):
        self.refuse("migrate_exact_file")

    def test_projection_before_noop_or_dry_run(self):
        self.refuse("create_projection")

    def test_rollback_before_record_or_publish(self):
        self.refuse("rollback_migrated")

    def test_unknown_backend_refuses_all_entries(self):
        for name in sorted(NAMES):
            with self.subTest(name=name):
                self.refuse(name, "unknown")

    def test_gate_first_executable_without_new_recovery_context(self):
        self.assertEqual(set(self.methods), NAMES)
        for name, method in self.methods.items():
            body = method.body
            if isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                body = body[1:]
            self.assertEqual(ast.unparse(body[0]), "_require_transaction_disposal_backend()")
            self.assertNotIn("_InstallTransaction.direct_writer",
                             [ast.unparse(d) for d in method.decorator_list])


if __name__ == "__main__":
    unittest.main()
