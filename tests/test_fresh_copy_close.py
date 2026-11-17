"""Ten pure AST/mock copy close contracts; no installer import or native I/O."""
import ast
import contextlib
import dataclasses
import hashlib
import io
import json
import stat
import shutil
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "production_installer.py"
text = SOURCE.read_text(encoding="utf-8-sig")
tree = ast.parse(text)
names = {"_CopySetterDiagnostic", "_RollbackFailureMember", "_InstallFailure",
         "_passive_owner_storage", "_store_copy_setter_detail", "_copy_setter_detail",
         "_copy_setter_operation_errors", "_merge_copy_setter_operation_errors",
         "_retain_copy_setter_operation_errors"}
nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
assert {n.name for n in nodes} == names
module = types.ModuleType("fresh_copy_types")
sys.modules[module.__name__] = module
module.__dict__.update(dataclass=dataclasses.dataclass, field=dataclasses.field, Path=Path,
                       contextmanager=contextlib.contextmanager)
exec(compile(ast.fix_missing_locations(ast.Module(
    body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)] + nodes,
    type_ignores=[])), "<real-failure-types>", "exec"), module.__dict__)
Failure = module._InstallFailure
Member = module._RollbackFailureMember
owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "_CreateOnlyMutablePath")
method = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == "copy_file")
callback = next(n for n in ast.walk(method) if isinstance(n, ast.FunctionDef) and n.name == "close_outgoing")
branch = next(n for n in ast.walk(method) if isinstance(n, ast.If) and callback in n.body)
assert ast.unparse(branch.test) == "existing is None"
assert isinstance(branch.body[0], ast.Assign) and ast.unparse(branch.body[0].value).startswith("os.open(")
assert branch.body[1] is callback
assert ast.unparse(branch.body[2]) == "resources.push(close_outgoing)"
assert ast.unparse(branch.body[3]) == "target_bound = None"
assert "self.transaction._capture_node" in ast.unparse(branch.body[4])
method.decorator_list = []
seam = ast.Module(body=[method], type_ignores=[])

transaction = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "_InstallTransaction")
tx_nodes = []
for name in ("_copy_close_failure", "_copy_reference", "_acquire_copy_metadata", "_settlement_failure"):
    node = next(n for n in transaction.body if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = [d for d in node.decorator_list if not isinstance(d, ast.Name) or d.id != "staticmethod"]
    tx_nodes.append(node)
exec(compile(ast.fix_missing_locations(ast.Module(body=[
    ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)] + tx_nodes,
    type_ignores=[])), "<copy-descriptor-methods>", "exec"), module.__dict__)
module._InstallTransaction = types.SimpleNamespace(**{n.name: module.__dict__[n.name] for n in tx_nodes})

class FalseyError(RuntimeError):
    def __bool__(self):
        return False

class FreshCopyCloseTests(unittest.TestCase):
    def invoke(self, primary=None, cleanup=None, source_cleanup=None):
        events = []
        def close(fd):
            events.append(("outgoing-close", fd) if fd == 19 else ("incoming-close",))
            selected = cleanup if fd == 19 else source_cleanup
            if selected is not None:
                raise selected
        closer = Mock(side_effect=close)
        path, source = Path("declared-copy"), Path("source")
        desired = object()
        expected = types.SimpleNamespace(kind="file", data=hashlib.sha256(b"payload").hexdigest(),
                                         python_identity=(1, 2, 0o100644, 0), native_proof=None)
        empty = types.SimpleNamespace(kind="file", data=hashlib.sha256(b"").hexdigest(),
                                      python_identity=expected.python_identity, native_proof=None)
        participant = types.SimpleNamespace(current=None, unknown=False, origin=None, before=None, created_origin=None)
        def write(*args, **kwargs):
            events.append(("copy-body",))
            if primary is not None:
                raise primary
            args[3](path, expected)
            return expected
        tx = types.SimpleNamespace(
            _copy_metadata={path: participant}, _expected={path: {}}, _copy_current={},
            _assert_copy_metadata=Mock(), _capture_node=Mock(side_effect=[expected, empty]),
            _image_matches=Mock(return_value=True), _same_origin=Mock(return_value=True), _advance=Mock(),
            _copy_reference=module._copy_reference, _read_copy_metadata=Mock(return_value=desired),
            _write_owned_file=write, _descriptor_bytes=Mock(return_value=b"payload"),
            _apply_copy_metadata=Mock(side_effect=lambda *a, **kw: events.append(("metadata-apply",))))
        owner = types.SimpleNamespace(transaction=tx, dry_run=False, destination=Mock(return_value=path),
            _ensure_parent=Mock(), _fresh_file_parents=Mock(return_value=()),
            _record_fresh_file=Mock(side_effect=lambda *a: events.append(("fresh-record",))))
        os_stub = types.SimpleNamespace(name="posix", O_RDONLY=0, O_RDWR=2, O_CREAT=64, O_EXCL=128, O_NOFOLLOW=256,
            open=Mock(side_effect=[18, 19]), close=closer,
            fstat=Mock(return_value=types.SimpleNamespace(st_dev=1, st_ino=2, st_mode=0o100644)),
            read=Mock(return_value=b""), path=types.SimpleNamespace(abspath=lambda p: str(p)))
        module.os = os_stub
        ns = dict(module.__dict__, os=os_stub, Path=Path, ExitStack=contextlib.ExitStack,
                  hashlib=hashlib, stat=stat, shutil=shutil)
        exec(compile(ast.fix_missing_locations(seam), "<full-copy-file>", "exec"), ns)
        caught = None
        try:
            ns["copy_file"](owner, path, source)
        except BaseException as error:
            caught = error
        self.assertEqual(os_stub.open.call_count, 2)
        self.assertEqual(os_stub.open.call_args_list[1].args, (path, 2 | 64 | 128 | 256, 0o666))
        self.assertEqual([call.args for call in closer.call_args_list], [(19,), (18,)])
        return caught, events

    def check_failure(self, error, primary, cleanup, path="declared-copy"):
        self.assertIs(type(error), Failure)
        self.assertEqual((error.stable_id, error.context), ("E_ROLLBACK_SETTLEMENT_FAILED", "copy-close"))
        self.assertIs(error.cause, primary if primary is not None else cleanup)
        self.assertIs(error.__cause__, primary)
        prior = primary.members if isinstance(primary, Failure) else ()
        self.assertEqual(len(error.members), len(prior) + 1)
        for actual, original in zip(error.members, prior):
            self.assertIs(actual, original)
        member = error.members[-1]
        self.assertIs(type(member), Member)
        self.assertEqual((member.phase, member.ordinal, member.path, member.participant),
                         ("backup", -1, path, "backup"))
        self.assertEqual(member.stable_id, "E_ROLLBACK_BACKUP_CLEANUP_FAILED")
        self.assertEqual(member.cause, str(cleanup))
        self.assertIs(member.cause_exception, cleanup)

    def test_success_close_once_before_metadata(self):
        error, events = self.invoke()
        self.assertIsNone(error)
        self.assertEqual(events, [("copy-body",), ("outgoing-close", 19), ("metadata-apply",),
                                  ("incoming-close",), ("fresh-record",)])

    def test_primary_identity_with_successful_close(self):
        primary = BaseException("copy cancelled")
        error, events = self.invoke(primary)
        self.assertIs(error, primary)
        self.assertEqual(events, [("copy-body",), ("outgoing-close", 19), ("incoming-close",)])

    def test_close_only_typed_failure(self):
        cleanup = OSError(5, "close failed")
        error, events = self.invoke(cleanup=cleanup)
        self.check_failure(error, None, cleanup)
        self.assertEqual(events, [("copy-body",), ("outgoing-close", 19), ("incoming-close",)])

    def test_primary_and_close_preserve_both(self):
        primary, cleanup = OSError(5, "copy read failed"), OSError(5, "close failed")
        error, events = self.invoke(primary, cleanup)
        self.check_failure(error, primary, cleanup)
        self.assertEqual(events, [("copy-body",), ("outgoing-close", 19), ("incoming-close",)])

    def test_falsey_primary_not_replaced(self):
        primary, cleanup = FalseyError("copy failed"), OSError(5, "close failed")
        error, _ = self.invoke(primary, cleanup)
        self.check_failure(error, primary, cleanup)

    def test_typed_primary_and_recovery_clone_keep_owned_data(self):
        operation = OSError(5, "setter failure")
        diagnostic = module._CopySetterDiagnostic("copy", "forward", "operation", 1,
            True, False, True, True, (), ("mtime_ns",), (), (), ((1, 2, 3), (4, 5, 6), (None, None, None)),
            "declared-copy")
        module._store_copy_setter_detail(operation, diagnostic)
        custody = object()
        operation._installer_custody = custody
        member = Member("snapshot", 7, "held", "E_ROLLBACK_SETTLEMENT_FAILED", "typed source",
                        cause_exception=operation)
        primary = Failure("E_ROLLBACK_SETTLEMENT_FAILED", "file-copy", operation,
            members=(member,), recovery_path=Path("original-recovery"), unresolved_paths=(Path("held"),),
            retained_errors=(operation,))
        cleanup, source_cleanup = OSError(5, "target close failed"), OSError(5, "source close failed")
        error, events = self.invoke(primary, cleanup, source_cleanup)
        target_failure = error.cause
        self.check_failure(target_failure, primary, cleanup)
        self.check_failure(error, target_failure, source_cleanup, path="source")
        self.assertEqual(events, [("copy-body",), ("outgoing-close", 19), ("incoming-close",)])
        clone = error._with_recovery_path(Path("new-recovery"))
        for selected in (error, clone):
            self.assertIs(selected.cause, target_failure)
            self.assertIs(selected.cause.cause, primary)
            self.assertIs(selected.cause.members[0], member)
            self.assertEqual(selected.cause.recovery_path, Path("original-recovery"))
            self.assertEqual(selected.cause.unresolved_paths, (Path("held"),))
            self.assertIs(module._copy_setter_detail(selected), diagnostic)
            self.assertIs(selected._installer_custody, custody)
            self.assertIs(module._copy_setter_operation_errors(selected)[0], operation)
            self.assertIs(selected.members[0], member)
            self.assertIs(selected.members[1].cause_exception, cleanup)
            self.assertIs(selected.members[2].cause_exception, source_cleanup)
            self.assertEqual(selected.unresolved_paths, (Path("held"),))
        self.assertEqual(error.recovery_path, Path("original-recovery"))
        self.assertIs(clone.members, error.members)
        self.assertEqual(clone.recovery_path, Path("new-recovery"))


    def reference_fixture(self, primary=None, cleanup=None):
        path = Path("source")
        metadata = types.SimpleNamespace(st_dev=1, st_ino=2, st_mode=0o100644)
        expected = types.SimpleNamespace(python_identity=(1, 2, 0o100644, 0), native_proof=None)
        close = Mock(side_effect=cleanup)
        module.os = types.SimpleNamespace(name="posix", O_RDONLY=0, O_RDWR=2, O_NOFOLLOW=256,
            open=Mock(return_value=18), fstat=Mock(return_value=metadata), close=close)
        caught = None
        try:
            with module._copy_reference(path, expected):
                if primary is not None:
                    raise primary
        except BaseException as error:
            caught = error
        close.assert_called_once_with(18)
        return caught

    def test_source_falsey_primary_close(self):
        primary, cleanup = FalseyError("source body"), OSError(5, "source close")
        error = self.reference_fixture(primary, cleanup)
        self.assertIs(error.cause, primary)
        self.assertIs(error.__cause__, primary)
        self.assertIs(error.members[-1].cause_exception, cleanup)

    def metadata_fixture(self, primary=None, cleanup=None):
        path, before, image = Path("metadata-target"), object(), object()
        metadata = types.SimpleNamespace(st_dev=1, st_ino=2, st_mode=0o100644)
        participant = types.SimpleNamespace(before=before, current=before)
        tx = types.SimpleNamespace(_copy_metadata={path: participant}, _copy_current={path: before},
            _read_copy_metadata=Mock(return_value=image, side_effect=primary))
        close = Mock(side_effect=cleanup)
        module.os = types.SimpleNamespace(O_RDONLY=0, O_NOFOLLOW=256,
            open=Mock(return_value=20), fstat=Mock(return_value=metadata), close=close)
        caught = None
        try:
            module._acquire_copy_metadata(tx, path, metadata, None, None)
        except BaseException as error:
            caught = error
        close.assert_called_once_with(20)
        if caught is not None:
            self.assertIs(participant.before, before)
            self.assertIs(participant.current, before)
            self.assertIs(tx._copy_current[path], before)
        else:
            self.assertIs(participant.before, image)
            self.assertIs(participant.current, image)
            self.assertIs(tx._copy_current[path], image)
        return caught

    def test_metadata_success(self):
        self.assertIsNone(self.metadata_fixture())

    def test_metadata_baseexception_clean_close(self):
        primary = BaseException("metadata cancelled")
        self.assertIs(self.metadata_fixture(primary), primary)

    def test_metadata_typed_falsey_primary_and_close(self):
        class FalseyFailure(Failure):
            def __bool__(self):
                return False
        original = OSError(5, "original")
        member = Member("snapshot", 2, "held", "E_ROLLBACK_SETTLEMENT_FAILED", "prior")
        primary = FalseyFailure("E_ROLLBACK_SETTLEMENT_FAILED", "file-copy", original,
            members=(member,), recovery_path=Path("recovery"), unresolved_paths=(Path("held"),),
            retained_errors=(original,))
        custody = object()
        primary._installer_custody = custody
        module._store_copy_setter_detail(primary, ())
        cleanup = OSError(5, "metadata close")
        error = self.metadata_fixture(primary, cleanup)
        self.assertEqual(error.context, "copy-metadata-close")
        for selected in (error, error._with_recovery_path(Path("new-recovery"))):
            self.assertIs(selected.cause, primary)
            self.assertIs(selected.members[0], member)
            self.assertIs(selected.members[1].cause_exception, cleanup)
            self.assertEqual(selected.unresolved_paths, (Path("held"),))
            self.assertIs(selected._installer_custody, custody)
            self.assertEqual(module._copy_setter_detail(selected), ())
            self.assertIs(module._copy_setter_operation_errors(selected)[0], original)
        self.assertEqual(error.recovery_path, Path("recovery"))
        self.assertIs(error.__cause__, primary)

if __name__ == "__main__":
    unittest.main()
