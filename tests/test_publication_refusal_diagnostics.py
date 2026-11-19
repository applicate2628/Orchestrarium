"""Closed scanner diagnostics; real gate imports, no Git push or fixture tree."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "scripts/universal-hooks/scripts/check-git-push-gate.py"


def load_owner():
    sys.path.insert(0, str(OWNER.parent))
    try:
        spec = importlib.util.spec_from_file_location("refusal_diagnostic_gate", OWNER)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


class TestRefusalDiagnostics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate = load_owner()

    def test_generic_exact_command_with_one_final_line_boundary(self):
        import shlex
        g = self.gate
        owner = sys.modules[g.classify_generic_push.__module__]
        command = shlex.join((str(ROOT / "git"), "-C", str(ROOT), "push", "origin",
                             "HEAD:refs/heads/topic"))
        def parsed(suffix):
            return owner.parse_shell_command(command + suffix, "posix")
        plain = owner.classify_generic_push(parsed(""))
        terminal = parsed("\n")
        self.assertEqual(plain.status, "PGG-ADMISSIBLE")
        self.assertEqual(owner.classify_generic_push(terminal), plain)
        self.assertFalse(owner._is_exact_direct_literal(terminal.raw_command, terminal))
        for suffix in ("\n\n", "\r\n", " \n", "\n echo other", "; echo other"):
            with self.subTest(suffix=suffix):
                self.assertNotEqual(owner.classify_generic_push(parsed(suffix)).status, "PGG-ADMISSIBLE")

    def test_field_orders_and_line_endings(self):
        g = self.gate
        for identifier in g._ScannerRefusalDenied._IDS:
            for fields in ("reason=deadline phase=reader", "phase=reader reason=deadline"):
                for ending in ("", "\n", "\r\n"):
                    with self.subTest(identifier=identifier, fields=fields, ending=ending):
                        exc = g._ScannerRefusalDenied("PGG-SCAN-REFUSAL",
                            f"publication-safety: refusing id={identifier} {fields}{ending}")
                        self.assertEqual(exc.failure_id, "PGG-SCAN-REFUSAL")
                        self.assertEqual(g._format_scanner_refusal(exc),
                            f" Scanner diagnostic: id={identifier}." + (
                                " The bounded reader timed out; check Git object availability before retrying."
                                if identifier == "PS-MSG-READ-TIMEOUT" else ""))

    def test_redaction_and_unknown_ids(self):
        g = self.gate
        line = "publication-safety: refusing id=PS-MSG-LIMIT reason=limit phase=reader"
        for text in ("", line + "\nprivate", "private\n" + line, line + "\n" + line,
                     line + "\n\n", line + "\r", line + "\x00",
                     line.replace("PS-MSG-LIMIT", "PS-UNKNOWN"),
                     line.replace("reason=limit", "reason=/private/path"),
                     line.replace("phase=reader", "reason=reader"),
                     line.replace("reason=limit", "phase=limit"),
                     line + " extra=private"):
            with self.subTest(text=text):
                exc = g._ScannerRefusalDenied("PGG-SCAN-REFUSAL", text)
                self.assertEqual(g._format_scanner_refusal(exc), "")
                self.assertNotIn("private", repr(exc.__dict__))
        self.assertEqual(g._format_scanner_refusal(g.PrRouteDenied("PGG-SCAN-REFUSAL")), "")

    def test_correlated_refusal_keeps_failure_and_id(self):
        g = self.gate
        good = b"publication-safety: refusing id=PS-MSG-READ-TIMEOUT reason=deadline phase=reader\r\n"
        for route, prefix in (("generic", "PGG"), ("strict", "PRG")):
            for code, output, expected in ((2, good, "PS-MSG-READ-TIMEOUT"),
                    (2, good + b"private", None), (1, b"", None)):
                with self.subTest(route=route, code=code, expected=expected):
                    binding = g.PushScanBinding(route, "origin", "refs/heads/main", "1" * 40, "1" * 40)
                    interpreter = g._interpreter_identity()
                    root = g.PathComponentIdentity(".", "directory", (1,))
                    closure = g.CanonicalSourceClosure(g.SOURCE_LAYOUTS[0], root, (root,), (),
                        "a" * 64, (2,), "b" * 64, interpreter,
                        g.RootLocatorIdentity("gate.py", ".", "directory", (1,), None, ".", (1,), "gate.py", (2,)))
                    pending = g.PendingScanInvocation("invocation", "attempt", binding, closure,
                        interpreter, ("python", "-I"), object(), created_tick=time.monotonic(),
                        authorization_deadline=time.monotonic() + 10)
                    supervisor = g.ChildSupervisor(SimpleNamespace(pid=41), attempt_seconds=0.01)
                    tick = time.monotonic()
                    streams = tuple(g.GateTransportObservation(name, "owned", True, None, tick)
                        for name in ("stdin", "stdout", "stderr"))
                    certificate = g.GateSettlementCertificate(supervisor.supervisor_id, 41, code,
                        streams, (), (), 1, tick + 1e-6)
                    settlement = g.GateSettlement(g.GateSettlementState.SETTLED, certificate, True)
                    pending.child_identity = 41
                    pending.supervisor = supervisor
                    pending.settlement = settlement
                    pending.state = g.PendingState.SETTLED
                    launched = g.LaunchedScanInvocation(pending, 41, supervisor, pending.invocation_id,
                        pending.attempt_id, binding, pending.exact_argv, pending.result_slot)
                    record = g.TrustedExecutionRecord(pending, launched, pending.result_slot, True,
                        code, b"", output, settlement, closure, interpreter, "trusted")
                    with self.assertRaises(g.PrRouteDenied) as raised:
                        pending.correlate_and_consume_once(launched, (record,), closure, interpreter,
                            binding, certificate.verified_at_monotonic_tick + 1e-4)
                    exc = raised.exception
                    self.assertEqual(exc.failure_id, prefix + ("-SCAN-REFUSAL" if code == 2 else "-SCAN-FINDING"))
                    self.assertEqual(getattr(exc, "scanner_id", None), expected)
                    if code == 2:
                        self.assertIsInstance(exc, g._ScannerRefusalDenied)
                    self.assertEqual(pending.state, g.PendingState.FAILED)
                    self.assertIsNone(pending.consumption_id)
                    self.assertNotIn("private", repr(exc.__dict__))

    def test_coverage_detail_is_fixed_and_bound_to_its_typed_reason(self):
        g = self.gate
        raw = "publication-safety: refusing id=PS-MSG-COVERAGE reason=empty-selection phase=coverage"
        known = g._ScannerRefusalDenied("PGG-SCAN-REFUSAL", raw)
        self.assertIn("no new selected coverage", g._format_scanner_refusal(known))
        foreign = g._ScannerRefusalDenied("PGG-SCAN-REFUSAL", raw.replace("empty-selection", "private-reason"))
        self.assertEqual(g._format_scanner_refusal(foreign), " Scanner diagnostic: id=PS-MSG-COVERAGE.")
        wrong_stage = g._ScannerRefusalDenied("PGG-SCAN-REFUSAL", raw.replace("phase=coverage", "phase=reader"))
        self.assertEqual(g._format_scanner_refusal(wrong_stage), " Scanner diagnostic: id=PS-MSG-COVERAGE.")

    def test_native_and_tool_surfaces_still_deny(self):
        g = self.gate
        exc = g._ScannerRefusalDenied("PGG-SCAN-REFUSAL",
            "publication-safety: refusing id=PS-INPUT-REFUSAL phase=input reason=unexpected\r\n")
        errors = io.StringIO()
        with mock.patch.object(g, "_normalize_repository_workdir", side_effect=exc), contextlib.redirect_stderr(errors):
            self.assertEqual(g._native_pre_push_main(["origin", "destination"]), 2)
        self.assertIn("Stage: native-binding. Scanner diagnostic: id=PS-INPUT-REFUSAL.", errors.getvalue())
        output = io.StringIO()
        preflight = SimpleNamespace(outcome="DEFER", continuation="EVALUATE_HEAVY",
                                    failure_id=None, workdir_diagnostic=None)
        with mock.patch.object(g, "validate_preflight_result", return_value=preflight), mock.patch.object(g, "evaluate_heavy", side_effect=exc), contextlib.redirect_stdout(output):
            self.assertEqual(g.compose_gate_result(preflight), 0)
        decision = json.loads(output.getvalue())["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("Scanner diagnostic: id=PS-INPUT-REFUSAL.", decision["permissionDecisionReason"])
        self.assertNotIn("unexpected", output.getvalue() + errors.getvalue())


if __name__ == "__main__":
    unittest.main()
