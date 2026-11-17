"""Pure diagnostic tests: no installer import or filesystem/native effects.

Copy-setter helpers are stand-ins, so this suite does not qualify their
production implementation or physical recovery/race behavior.
"""
import ast
import contextlib
import dataclasses
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "production_installer.py"


def _load_contract(source):
    tree = ast.parse(source.read_text(encoding="utf-8-sig"))
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}

    def storage(_cls, obj):
        try:
            return object.__getattribute__(obj, "__dict__")
        except (AttributeError, TypeError):
            return None

    namespace = dict(__name__=__name__, dataclass=dataclasses.dataclass,
                     field=dataclasses.field, Path=Path)
    namespace.update(
        _passive_owner_storage=storage,
        _copy_setter_detail=lambda error: getattr(error, "_copy_setter_diagnostic", None),
        _store_copy_setter_detail=lambda error, detail: setattr(error, "_copy_setter_diagnostic", detail),
        _copy_setter_operation_errors=lambda error: getattr(error, "_ops", ()),
        _merge_copy_setter_operation_errors=lambda *groups: tuple(item for group in groups for item in group),
        _retain_copy_setter_operation_errors=lambda error, operations: setattr(error, "_ops", operations),
    )
    selected = [classes["_RollbackFailureMember"], classes["_InstallFailure"]]
    for name, methods in (
        ("_InstallTransaction", {"_settlement_failure", "_receiving_failure", "_publish_retained"}),
        ("_CreateOnlyMutablePath", {"_replace_prepared", "retain_path"}),
    ):
        nodes = [node for node in classes[name].body
                 if isinstance(node, ast.FunctionDef) and node.name in methods]
        for node in nodes:
            node.decorator_list = [decorator for decorator in node.decorator_list
                                   if isinstance(decorator, ast.Name) and decorator.id == "staticmethod"]
        selected.append(ast.ClassDef(name=name, bases=[], keywords=[], body=nodes, decorator_list=[]))
    module = ast.fix_missing_locations(ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        *selected,
    ], type_ignores=[]))
    exec(compile(module, "<receiving-contract>", "exec"), namespace)
    return tuple(namespace[name] for name in (
        "_InstallTransaction", "_CreateOnlyMutablePath", "_InstallFailure", "_RollbackFailureMember"))


class ReceivingErrorsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.Transaction, cls.Owner, cls.Failure, cls.Member = _load_contract(SOURCE)

    def setUp(self):
        self.leaf, self.prepared, self.retained = map(Path, ("leaf", "prepared", "retained"))
        self.node = types.SimpleNamespace(kind="file", python_identity=(1, 2, 0, 0))
        self.origin = OSError("publication origin")
        self.primary_member = self.Member("snapshot", 1, "old-unresolved",
            "E_ROLLBACK_RESTORE_FAILED", "old", participant="effect")
        self.secondary_member = self.Member("backup", 2, "second-unresolved",
            "E_ROLLBACK_BACKUP_CLEANUP_FAILED", "second", participant="backup")

    def errors(self):
        primary = self.Failure("E_MUTABLE_PATH_POSTCONDITION", "transaction", self.origin,
            members=(self.primary_member,), recovery_path=Path("old-recovery"),
            unresolved_paths=(Path("old-unresolved"),))
        primary.__cause__ = self.origin
        primary._installer_custody = object()
        secondary = self.Failure("E_ROLLBACK_SETTLEMENT_FAILED", "transaction", OSError("receiver origin"),
            members=(self.secondary_member,), recovery_path=Path("second-recovery"),
            unresolved_paths=(Path("second-unresolved"),))
        secondary._installer_custody = object()
        return primary, secondary

    def fixture(self, stage, primary, secondary, successful=False):
        tx = self.Transaction()
        owner = self.Owner()
        owner.transaction, owner.dry_run = tx, False
        before = {} if stage == "publication" else {self.leaf: self.node}
        effect = types.SimpleNamespace(location=self.leaf, path=self.leaf,
            prepared_path=self.prepared, prepared_state=None, before=before,
            actual=dict(before), proposed={self.leaf: self.node}, retained=self.retained)
        tx.arm_replacement = mock.Mock(return_value=effect)
        tx._observe = mock.Mock(return_value={self.prepared: self.node})
        tx._relocate = mock.Mock(side_effect=lambda image, old, new: {new: self.node} if image else {})
        tx.assert_effect_current = mock.Mock()
        tx._image_matches = mock.Mock(return_value=True)
        tx._publish_retained = mock.Mock(return_value={self.leaf: self.node},
                                        side_effect=None if successful else primary)
        tx.retained_replacement = mock.Mock(side_effect=secondary)
        tx.published_replacement = mock.Mock(side_effect=secondary)
        owner._final_absence = mock.Mock()
        owner.destination = mock.Mock(return_value=self.leaf)
        call = (lambda: owner.retain_path(Path("relative"), {self.leaf: self.node})) if stage == "retain" else (
            lambda: owner._replace_prepared(self.leaf, self.prepared, effect=effect))
        return call, tx

    def capture(self, call):
        try:
            call()
        except BaseException as error:
            return error
        self.fail("Expected a failure")

    def assert_dual(self, result, primary, secondary, typed=True):
        self.assertIsInstance(result, self.Failure)
        self.assertIs(result.cause, primary)
        self.assertIs(result.__cause__, primary)
        self.assertIs(primary.__cause__, self.origin)
        self.assertTrue(any(member.cause_exception is secondary for member in result.members))
        self.assertTrue(all(member.phase in ("migration", "created", "snapshot", "backup")
                            for member in result.members))
        if typed:
            self.assertIs(result._installer_custody, primary._installer_custody)
            self.assertIsNot(result._installer_custody, secondary._installer_custody)
            self.assertIn(self.primary_member, result.members)
            self.assertIn(self.secondary_member, result.members)
            self.assertEqual(result.recovery_path, primary.recovery_path)
            self.assertTrue(set(primary.unresolved_paths + secondary.unresolved_paths +
                                (secondary.recovery_path,)) <= set(result.unresolved_paths))
            clone = result._with_recovery_path(Path("reconciled-recovery"))
            self.assertIs(clone.cause, primary)
            self.assertIs(primary.__cause__, self.origin)
            self.assertIs(clone._installer_custody, primary._installer_custody)
            self.assertIs(clone.members, result.members)
            self.assertEqual(clone.unresolved_paths, result.unresolved_paths)
            self.assertTrue(any(member.cause_exception is secondary for member in clone.members))
            self.assertEqual(clone.recovery_path, Path("reconciled-recovery"))

    def test_finally_dual_failures_and_receiving_checks(self):
        for stage in ("retention", "publication", "retain"):
            for at_check in (False, True):
                with self.subTest(stage=stage, at_check=at_check):
                    primary, secondary = self.errors()
                    call, tx = self.fixture(stage, primary, secondary)
                    if at_check:
                        tx._image_matches.side_effect = [True, secondary] if stage == "retain" else secondary
                    self.assert_dual(self.capture(call), primary, secondary)
                    self.assertEqual(tx._publish_retained.call_count, 1)

    def test_finally_receiving_file_not_found_is_not_swallowed(self):
        for stage in ("retention", "publication", "retain"):
            with self.subTest(stage=stage):
                primary, _ = self.errors()
                secondary = FileNotFoundError("receiver missing")
                call, tx = self.fixture(stage, primary, secondary)
                self.assert_dual(self.capture(call), primary, secondary, typed=False)
                self.assertEqual(tx._publish_retained.call_count, 1)

    def test_finally_plain_dual_failures(self):
        for stage in ("retention", "publication", "retain"):
            with self.subTest(stage=stage):
                primary = OSError("plain publication failure")
                primary.__cause__ = self.origin
                secondary = ValueError("plain receiving failure")
                call, tx = self.fixture(stage, primary, secondary)
                self.assert_dual(self.capture(call), primary, secondary, typed=False)
                self.assertEqual(tx._publish_retained.call_count, 1)

    def test_finally_success_keeps_receiver_primary(self):
        for stage in ("retention", "publication", "retain"):
            with self.subTest(stage=stage):
                primary, secondary = self.errors()
                call, tx = self.fixture(stage, primary, secondary, successful=True)
                self.assertIs(self.capture(call), secondary)
                self.assertEqual(tx._publish_retained.call_count, 1)

    def test_finally_success_is_unchanged(self):
        for stage in ("retention", "publication", "retain"):
            with self.subTest(stage=stage):
                call, tx = self.fixture(stage, None, None, successful=True)
                call()
                self.assertEqual(tx._publish_retained.call_count, 2 if stage == "retention" else 1)

    def native_fixture(self, primary, secondary, successful=False):
        tx = self.Transaction()
        tx._migration_selection_guard = lambda *args: contextlib.nullcontext(None)
        tx._image_matches = mock.Mock(return_value=True)
        tx._native_publish_no_replace = mock.Mock(return_value=True,
                                                 side_effect=None if successful else primary)
        tx._moved = mock.Mock(side_effect=secondary)
        tx._relocate = mock.Mock(return_value={self.retained: self.node})
        return tx, lambda: tx._publish_retained(self.leaf, self.retained,
                                                source_state={self.leaf: self.node})

    def test_native_exception_reconciliation_keeps_both(self):
        primary, secondary = self.errors()
        with mock.patch.object(Path, "lstat", return_value=types.SimpleNamespace(st_dev=1, st_ino=2)):
            tx, call = self.native_fixture(primary, secondary)
            self.assert_dual(self.capture(call), primary, secondary)
        self.assertEqual(tx._native_publish_no_replace.call_count, 1)
        self.assertEqual(tx._moved.call_count, 1)

    def test_native_receiving_file_not_found_is_not_swallowed(self):
        primary, _ = self.errors()
        secondary = FileNotFoundError("receiving missing")
        with mock.patch.object(Path, "lstat", return_value=types.SimpleNamespace(st_dev=1, st_ino=2)):
            tx, call = self.native_fixture(primary, secondary)
            self.assert_dual(self.capture(call), primary, secondary, typed=False)
        self.assertEqual(tx._native_publish_no_replace.call_count, 1)
        self.assertEqual(tx._moved.call_count, 1)

    def test_native_success_keeps_receiver_primary(self):
        primary, secondary = self.errors()
        tx, call = self.native_fixture(primary, secondary, successful=True)
        self.assertIs(self.capture(call), secondary)
        self.assertEqual(tx._native_publish_no_replace.call_count, 1)
        self.assertEqual(tx._moved.call_count, 1)

    def test_native_missing_target_keeps_publication_primary(self):
        primary, secondary = self.errors()
        with mock.patch.object(Path, "lstat", side_effect=FileNotFoundError("target absent")):
            tx, call = self.native_fixture(primary, secondary)
            self.assertIs(self.capture(call), primary)
        self.assertEqual(tx._native_publish_no_replace.call_count, 1)
        self.assertEqual(tx._moved.call_count, 0)


if __name__ == "__main__":
    if "--source" in sys.argv:
        index = sys.argv.index("--source")
        SOURCE = Path(sys.argv[index + 1])
        del sys.argv[index:index + 2]
    unittest.main()
