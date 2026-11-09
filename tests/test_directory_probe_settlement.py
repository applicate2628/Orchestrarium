"""Real probe control flow with inert paths; no installer/native execution."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

from installer_diagnostic_test_support import DIAGNOSTICS


SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "production_installer.py"


class FalseError(Exception):
    def __bool__(self):
        return False


class UninspectableError(Exception):
    def __bool__(self):
        raise AssertionError("settlement must not inspect exception truthiness")


class DirectoryProbeSettlementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(SOURCE.read_bytes())
        names = {"_preflight_directory_move_capabilities", "_require_transaction_disposal_backend"}
        cls.nodes = [node for node in tree.body
                     if isinstance(node, ast.FunctionDef) and node.name in names]
        assert {node.name for node in cls.nodes} == names

    def invoke(self, *, primary=None, cleanup=None, posix_hold=False):
        # Every filesystem participant is a closed in-memory double. Only the
        # extracted owner and diagnostic declarations run, not installer imports.
        events = self.events = []

        class InertPath:
            def __init__(self, value):
                self.value = value

            def __truediv__(self, value):
                return InertPath(self.value + "/" + value)

            @property
            def parent(self):
                return InertPath(self.value.rsplit("/", 1)[0])

            def __hash__(self):
                return hash(self.value)

            def __eq__(self, other):
                return isinstance(other, InertPath) and self.value == other.value

            def __lt__(self, other):
                return self.value < other.value

            def __str__(self):
                return self.value

            def mkdir(self):
                events.append("mkdir")
                if primary is not None:
                    raise primary

        def acquire(**kwargs):
            events.append("acquire")
            return "/synthetic/probe"

        class InertTransaction:
            def __init__(self, paths, *, enabled):
                assert paths == [] and enabled is False
                self.moves = 0

            def _observe(self, path):
                events.append("observe")
                return {path: "inert-state"}

            def _native_publish_no_replace(self, source, destination):
                events.append("move")
                self.moves += 1
                if self.moves == 2:
                    raise FileExistsError()
                return True

            def _relocate(self, state, source, destination):
                return {destination: state[source]}

            def _image_matches(self, path, state):
                return True

            def _dispose_image(self, path, state):
                events.append("dispose")
                if posix_hold:
                    scope["_require_transaction_disposal_backend"]()
                if cleanup is not None:
                    raise cleanup

            @staticmethod
            def _binding_identity_matches(before, after):
                return before == after

        scope = {
            "Path": InertPath,
            "tempfile": SimpleNamespace(mkdtemp=acquire),
            "os": SimpleNamespace(name="posix" if posix_hold else "nt"),
            "_CreateOnlyMutablePath": SimpleNamespace(_identity=lambda path: (1, 2, 3, 4)),
            "_InstallTransaction": InertTransaction,
            "_InstallFailure": DIAGNOSTICS._InstallFailure,
        }
        future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
        module = ast.fix_missing_locations(ast.Module(body=[future, *self.nodes], type_ignores=[]))
        exec(compile(module, str(SOURCE) + ":inert-probe-only", "exec"), scope)
        plan = SimpleNamespace(skills=(SimpleNamespace(
            name="lead", accepted_prior="prior", managed_before=None),))
        return scope["_preflight_directory_move_capabilities"](plan, InertPath("/synthetic/target"))

    def assert_preserved(self, primary, cleanup):
        failure = None
        try:
            self.invoke(primary=primary, cleanup=cleanup)
        except BaseException as error:
            failure = error
        # Assert outside the exception handler: a deliberately hostile __bool__
        # must not also escape through the unittest traceback renderer on RED.
        self.assertIsInstance(failure, DIAGNOSTICS._InstallFailure)
        self.assertEqual(failure.stable_id, "E_ROLLBACK_SETTLEMENT_FAILED")
        self.assertEqual(failure.context, "capability")
        self.assertIs(failure.cause, primary)
        self.assertIs(failure.__cause__, primary)
        self.assertIs(failure.__context__, cleanup)
        self.assertEqual(str(failure.recovery_path), "/synthetic/probe")
        self.assertEqual(self.events, ["acquire", "observe", "mkdir", "dispose"])
        return failure

    def test_false_primary_is_not_replaced_by_cleanup(self):
        self.assert_preserved(FalseError("primary"), OSError("cleanup"))

    def test_primary_truthiness_is_not_executed(self):
        self.assert_preserved(UninspectableError("primary"), OSError("cleanup"))

    def test_ordinary_primary_and_secondary_are_retained(self):
        self.assert_preserved(ValueError("primary"), OSError("cleanup"))

    def test_interrupt_causes_retain_existing_typed_settlement(self):
        for primary in (KeyboardInterrupt(), SystemExit(7)):
            with self.subTest(primary=type(primary).__name__):
                self.assert_preserved(primary, OSError("cleanup"))

    def test_no_primary_selects_cleanup_without_truthiness(self):
        for cleanup in (FalseError("cleanup"), UninspectableError("cleanup")):
            with self.subTest(cleanup=type(cleanup).__name__):
                with self.assertRaises(DIAGNOSTICS._InstallFailure) as caught:
                    self.invoke(cleanup=cleanup)
                self.assertIs(caught.exception.cause, cleanup)
                self.assertIsNone(caught.exception.__cause__)
                self.assertIs(caught.exception.__context__, cleanup)
                self.assertEqual(self.events.count("dispose"), 1)

    def test_successful_cleanup_preserves_original_exception(self):
        primary = UninspectableError("primary")
        with self.assertRaises(UninspectableError) as caught:
            self.invoke(primary=primary)
        self.assertIs(caught.exception, primary)
        self.assertEqual(self.events.count("dispose"), 1)

    def test_ordinary_success_keeps_witness_and_effect_sequence(self):
        result = self.invoke()
        self.assertEqual(tuple((str(path), identity) for path, identity in result),
                         (("/synthetic/target", (1, 2, 3, 4)),))
        self.assertEqual(self.events,
                         ["acquire", "observe", "mkdir", "observe", "move",
                          "mkdir", "observe", "move", "dispose"])

    def test_posix_refusal_remains_cleanup_failure_not_backend_admission(self):
        primary = FalseError("primary")
        with self.assertRaises(DIAGNOSTICS._InstallFailure) as caught:
            self.invoke(primary=primary, posix_hold=True)
        failure = caught.exception
        self.assertIs(failure.cause, primary)
        self.assertIs(failure.__cause__, primary)
        self.assertIsInstance(failure.__context__, ValueError)
        self.assertIn("E_EFFECT_BOUND_DISPOSAL_UNQUALIFIED", str(failure.__context__))
        self.assertEqual(self.events.count("dispose"), 1)

    def test_public_diagnostic_does_not_expose_private_primary(self):
        failure = self.assert_preserved(FalseError("PRIVATE_PRIMARY"), OSError("PRIVATE_CLEANUP"))
        diagnostic = DIAGNOSTICS._installer_failure_text(failure)
        self.assertNotIn("PRIVATE_", diagnostic)
        self.assertIn("E_ROLLBACK_SETTLEMENT_FAILED", diagnostic)


if __name__ == "__main__":
    unittest.main()
