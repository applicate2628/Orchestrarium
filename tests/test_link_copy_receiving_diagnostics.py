"""Real link-copy owner and diagnostics with inert Win32 participants only."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace
import unittest

from installer_diagnostic_test_support import DIAGNOSTICS

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "production_installer.py"


class UninspectableError(Exception):
    def __bool__(self):
        raise AssertionError("exception truthiness is not an operation")


class LinkCopyReceivingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(SOURCE.read_bytes())
        owner = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                     and n.name == "_InstallTransaction")
        names = {"_copy_owned_link", "_settlement_failure"}
        cls.methods = [n for n in owner.body
                       if isinstance(n, ast.FunctionDef) and n.name in names]
        assert {n.name for n in cls.methods} == names
        native = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                      and n.name == "_WindowsBoundNode")
        cls.methods.append(next(n for n in native.body if isinstance(n, ast.FunctionDef)
                                and n.name == "__exit__"))

    def invoke(self, *, setter=None, receiving=None, stage="capture", drift=False,
               close_error=None, platform="nt"):
        events = self.events = []
        records = self.records = []
        source, target = Path("synthetic/source"), Path("synthetic/target")
        self.target = target
        proof = object()
        initial = SimpleNamespace(native_proof=proof, data="empty")
        actual = SimpleNamespace(native_proof=object() if drift else proof, data="link")
        expected = SimpleNamespace(native_proof=proof, data="synthetic/link-target")
        self.initial, self.actual = initial, actual

        class Bound:
            def __init__(self, created):
                self.created = created
                self.proof = proof

            def __enter__(self):
                events.append("creator-enter" if self.created else "source-enter")
                return self

            def __exit__(self, kind, error, traceback):
                events.append("creator-exit" if self.created else "source-exit")
                if self.created and close_error is not None:
                    native = SimpleNamespace(descriptor=None, handle=19, path=target,
                        settlement_primary=None, _api=lambda: (
                            SimpleNamespace(get_last_error=lambda: 6, WinError=lambda code: close_error),
                            None, SimpleNamespace(CloseHandle=lambda handle: False)))
                    return scope["__exit__"](native, kind, error, traceback)
                return False

            def basic(self):
                return SimpleNamespace(attributes=16)

            def reparse_data(self):
                events.append("reparse-read")
                return b"synthetic-reparse"

            def set_reparse_data(self, data):
                assert data == b"synthetic-reparse"
                events.append("set")
                if setter is not None:
                    raise setter

        class Native:
            def __new__(cls, path, *, purpose):
                assert path == source and purpose == "observe"
                return Bound(False)

            @staticmethod
            def create(path, *, directory):
                assert path == target and directory is True
                return Bound(True)

        def capture(path, **kwargs):
            assert path == target
            events.append("capture")
            if events.count("capture") == 1:
                return initial
            if stage == "capture" and receiving is not None:
                raise receiving
            return actual

        def record(path, node):
            assert path == target
            events.append("record")
            if events.count("record") == 2 and stage == "record" and receiving is not None:
                raise receiving
            records.append(node)

        def image_matches(path, image):
            assert path == source and image == {source: expected}
            events.append("source-check")
            return True

        scope = dict(vars(DIAGNOSTICS))
        scope.update(os=SimpleNamespace(name=platform), stat=SimpleNamespace(FILE_ATTRIBUTE_DIRECTORY=16),
                     hashlib=hashlib, _WindowsBoundNode=Native)
        future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
        unit = ast.fix_missing_locations(ast.Module(body=[future, *self.methods], type_ignores=[]))
        exec(compile(unit, str(SOURCE) + ":inert-link-copy", "exec"), scope)
        owner = SimpleNamespace(_image_matches=image_matches, _capture_node=capture,
                                _settlement_failure=scope["_settlement_failure"])
        return scope["_copy_owned_link"](owner, source, target, expected, record)

    def caught(self, **kwargs):
        failure = None
        try:
            self.invoke(**kwargs)
        except BaseException as error:
            failure = error
        return failure

    def test_setter_and_capture_failures_keep_both_original_objects(self):
        primary = DIAGNOSTICS._InstallFailure(
            "E_NATIVE_PROJECTION_SET_FAILED", "projection-set",
            OSError(22, "PRIVATE_SETTER", "PRIVATE_PATH"))
        secondary = OSError(13, "PRIVATE_CAPTURE", "PRIVATE_PATH")
        failure = self.caught(setter=primary, receiving=secondary)
        self.assertIsInstance(failure, DIAGNOSTICS._InstallFailure)
        self.assertIs(failure.cause, primary)
        self.assertIs(failure.__cause__, primary)
        self.assertIs(failure.__context__, secondary)
        self.assertIs(failure.members[0].cause_exception, primary)
        self.assertIs(failure.members[-1].cause_exception, secondary)
        self.assertIn(self.target, failure.unresolved_paths)
        self.assertEqual(failure.recovery_path, self.target)
        self.assertEqual(self.records, [self.initial])
        self.assertEqual(self.events[-1], "creator-exit")
        rendered = DIAGNOSTICS._installer_failure_text(failure)
        self.assertIn("E_NATIVE_PROJECTION_SET_FAILED", rendered)
        self.assertIn("errno:22", rendered)
        self.assertIn("errno:13", rendered)
        self.assertNotIn("PRIVATE", rendered)

    def test_record_failure_retains_primary_without_inspecting_truthiness(self):
        primary, secondary = UninspectableError("setter"), RuntimeError("record")
        failure = self.caught(setter=primary, receiving=secondary, stage="record")
        self.assertIsInstance(failure, DIAGNOSTICS._InstallFailure)
        self.assertIs(failure.cause, primary)
        self.assertIs(failure.__cause__, primary)
        self.assertIs(failure.members[-1].cause_exception, secondary)
        self.assertEqual(self.events.count("record"), 2)
        self.assertEqual(self.records, [self.initial])

    def test_identity_refusal_retains_setter_failure(self):
        primary = OSError(22, "setter")
        failure = self.caught(setter=primary, drift=True)
        self.assertIsInstance(failure, DIAGNOSTICS._InstallFailure)
        self.assertIs(failure.cause, primary)
        self.assertIsInstance(failure.members[-1].cause_exception, ValueError)
        self.assertIn("link creator drift", str(failure.members[-1].cause_exception))
        self.assertEqual(self.events.count("record"), 1)

    def test_typed_recovery_and_members_survive_receiving_failure(self):
        member = DIAGNOSTICS._RollbackFailureMember(
            "backup", 7, "synthetic/prior", "E_ROLLBACK_BACKUP_CLEANUP_FAILED",
            "prior", participant="backup")
        primary = DIAGNOSTICS._InstallFailure(
            "E_ROLLBACK_SETTLEMENT_FAILED", "projection-set", OSError(22, "setter"),
            members=(member,), recovery_path=Path("synthetic/recovery"),
            unresolved_paths=(Path("synthetic/prior"),))
        secondary = OSError(13, "capture")
        failure = self.caught(setter=primary, receiving=secondary)
        self.assertIsInstance(failure, DIAGNOSTICS._InstallFailure)
        self.assertIs(failure.cause, primary)
        self.assertIs(failure.members[0], member)
        self.assertEqual(failure.recovery_path, primary.recovery_path)
        self.assertIn(Path("synthetic/prior"), failure.unresolved_paths)

    def test_setter_failure_after_successful_receiving_remains_original(self):
        primary = OSError(22, "setter")
        self.assertIs(self.caught(setter=primary), primary)
        self.assertEqual(self.records, [self.initial, self.actual])
        self.assertEqual(self.events.count("set"), 1)
        self.assertEqual(self.events[-1], "creator-exit")

    def test_receiving_only_failure_remains_original(self):
        for stage in ("capture", "record"):
            with self.subTest(stage=stage):
                secondary = OSError(13, stage)
                self.assertIs(self.caught(receiving=secondary, stage=stage), secondary)
                self.assertEqual(self.events.count("set"), 1)
                self.assertEqual(self.events[-1], "creator-exit")

    def test_interrupt_originals_are_retained_on_double_failure(self):
        for primary in (KeyboardInterrupt(), SystemExit(7)):
            with self.subTest(kind=type(primary).__name__):
                secondary = OSError(13, "capture")
                failure = self.caught(setter=primary, receiving=secondary)
                self.assertIsInstance(failure, DIAGNOSTICS._InstallFailure)
                self.assertIs(failure.cause, primary)
                self.assertIs(failure.__cause__, primary)
                self.assertIs(failure.members[-1].cause_exception, secondary)

    def test_typed_receiving_keeps_members_custody_and_retained_errors(self):
        primary = DIAGNOSTICS._InstallFailure(
            "E_NATIVE_PROJECTION_SET_FAILED", "projection-set", OSError(22, "setter"))
        member = DIAGNOSTICS._RollbackFailureMember(
            "backup", 9, "synthetic/receiving", "E_ROLLBACK_BACKUP_CLEANUP_FAILED",
            "receiving", participant="backup")
        secondary = DIAGNOSTICS._InstallFailure(
            "E_ROLLBACK_SETTLEMENT_FAILED", "creator-capture", OSError(13, "capture"),
            members=(member,), unresolved_paths=(Path("synthetic/receiving"),))
        custody, original_error, receiving_error = object(), OSError(5, "original"), OSError(6, "receiving")
        primary._installer_custody = custody
        DIAGNOSTICS._retain_copy_setter_operation_errors(primary, (original_error,))
        DIAGNOSTICS._retain_copy_setter_operation_errors(secondary, (receiving_error,))
        failure = self.caught(setter=primary, receiving=secondary)
        self.assertIsInstance(failure, DIAGNOSTICS._InstallFailure)
        self.assertIs(failure.cause, primary)
        self.assertIs(failure.__context__, secondary)
        self.assertIs(failure.members[-1], member)
        self.assertIn(Path("synthetic/receiving"), failure.unresolved_paths)
        self.assertIs(failure._installer_custody, custody)
        retained = DIAGNOSTICS._copy_setter_operation_errors(failure)
        self.assertTrue(any(error is original_error for error in retained))
        self.assertTrue(any(error is secondary for error in retained))
        self.assertEqual(DIAGNOSTICS._copy_setter_operation_errors(secondary), (receiving_error,))

    def test_native_close_wrapper_retains_the_double_failure_chain(self):
        primary, receiving, closing = OSError(22, "setter"), OSError(13, "capture"), OSError(6, "close")
        failure = self.caught(setter=primary, receiving=receiving, close_error=closing)
        self.assertIsInstance(failure, DIAGNOSTICS._InstallFailure)
        self.assertEqual(failure.context, "native-close")
        self.assertIs(failure.members[0].cause_exception, closing)
        self.assertIs(failure.__cause__, failure.cause)
        inner = failure.cause
        self.assertIsInstance(inner, DIAGNOSTICS._InstallFailure)
        self.assertIs(inner.cause, primary)
        self.assertIs(inner.__cause__, primary)
        self.assertIs(inner.members[-1].cause_exception, receiving)
        self.assertEqual(inner.recovery_path, self.target)
        self.assertEqual(self.events.count("set"), 1)
        self.assertEqual(self.events.count("creator-exit"), 1)

    def test_success_keeps_receiving_and_source_checks(self):
        self.assertIsNone(self.invoke())
        self.assertEqual(self.records, [self.initial, self.actual])
        self.assertEqual(self.events, [
            "source-check", "source-enter", "reparse-read", "source-exit",
            "creator-enter", "capture", "record", "set", "capture", "record",
            "reparse-read", "creator-exit", "source-check"])

if __name__ == "__main__":
    unittest.main()
