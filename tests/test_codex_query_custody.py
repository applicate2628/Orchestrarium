"""Deterministic POSIX query-custody regressions; no external host or model."""
import importlib.util
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

class QueryCustodyTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("query_custody_health", ROOT / "scripts/check-hook-health.py")
        self.health = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.health
        spec.loader.exec_module(self.health)
        self.events = []
        events = self.events
        class Input(io.BytesIO):
            def close(self):
                events.append("stdin-close")
                super().close()
        self.process = SimpleNamespace(
            pid=321, stdin=Input(), stdout=io.BytesIO(b'{"id":1,"result":{}}\n{"id":2,"result":{"data":[]}}\n'),
            stderr=io.BytesIO(), returncode=None)
        self.process.poll = lambda: self.process.returncode
        def wait(timeout=None):
            events.append("direct-wait")
            self.process.returncode = 0
            return 0
        self.process.wait = wait
        self.process.terminate = lambda: events.append("terminate")
        self.process.kill = lambda: events.append("kill")
        self.closure = SimpleNamespace(complete=True)
        self.owner = SimpleNamespace(popen_kwargs={"start_new_session": True},
            bind_process_group=lambda pid: events.append(("bind", pid)),
            settle=lambda *a, **kw: self.settle(), close=lambda: events.append("close-owner"))
        self.owner_type = SimpleNamespace(acquire=lambda: self.owner)
        self.captured = {}
    def settle(self):
        self.events.append("settle")
        return self.closure
    def invoke(self):
        def popen(*a, **kw):
            self.captured.update(kw)
            return self.process
        with patch.object(self.health, "_load_posix_process_group_module",
                          return_value=SimpleNamespace(PosixProcessGroupOwnerV1=self.owner_type), create=True), \
             patch.object(self.health.subprocess, "Popen", side_effect=popen), \
             patch.object(self.health, "os", SimpleNamespace(name="posix", environ=os.environ)):
            return self.health._codex_hooks_list(codex_command=[str(Path(sys.executable).resolve())],
                codex_home=ROOT, query_cwd=ROOT)
    def test_private_group_and_eof_before_wait(self):
        self.assertEqual(self.invoke(), [])
        self.assertTrue(self.captured.get("start_new_session"))
        self.assertLess(self.events.index("stdin-close"), self.events.index("direct-wait"))
        self.assertIn(("bind", 321), self.events)
        self.assertIn("settle", self.events)
    def test_incomplete_group_cannot_return_inventory(self):
        self.closure.complete = False
        with self.assertRaisesRegex(ValueError, "CODEX_HOOK_LIST_CLEANUP"):
            self.invoke()
    def test_interrupted_bind_reconciles_same_created_group(self):
        for after_assignment in (False, True):
            with self.subTest(after_assignment=after_assignment):
                self.setUp()
                calls = []
                bound = []
                def bind(pid):
                    calls.append(pid)
                    if after_assignment or len(calls) > 1:
                        bound[:] = [pid]
                    if len(calls) == 1:
                        raise KeyboardInterrupt
                self.owner.bind_process_group = bind
                def settle(*args, **kwargs):
                    self.assertEqual(bound, [321])
                    self.events.append("settle")
                    return self.closure
                self.owner.settle = settle
                with self.assertRaises(KeyboardInterrupt):
                    self.invoke()
                self.assertEqual(calls, [321, 321])
                self.assertIn("settle", self.events)

    def test_group_bind_repeats_only_same_valid_open_identity(self):
        module = self.health._load_posix_process_group_module()
        owner = module.PosixProcessGroupOwnerV1()
        owner.bind_process_group(321)
        owner.bind_process_group(321)
        for value in (True, 0, -1, "321", 322):
            with self.assertRaises(module.PosixProcessGroupError):
                owner.bind_process_group(value)
        owner._closure = object()  # No process was created by this pure state test.
        with self.assertRaises(module.PosixProcessGroupError):
            owner.bind_process_group(321)

    def test_cached_old_owner_refuses_before_spawn(self):
        module = self.health._load_posix_process_group_module()
        command = [str(Path(sys.executable).resolve())]
        with patch.object(module, "POSIX_PROCESS_GROUP_IDEMPOTENT_BIND_V1", False), \
             patch.object(self.health, "os", SimpleNamespace(name="posix", environ=os.environ)), \
             patch.object(self.health.subprocess, "Popen") as popen:
            with self.assertRaisesRegex(RuntimeError, "identity-mismatch"):
                self.health._codex_hooks_list(codex_command=command, codex_home=ROOT, query_cwd=ROOT)
            popen.assert_not_called()

    def test_failed_rebind_still_settles_acquired_group(self):
        calls = []
        def bind(pid):
            calls.append(pid)
            if len(calls) == 2:
                raise RuntimeError("injected rebind failure")
        self.owner.bind_process_group = bind
        with self.assertRaisesRegex(ValueError, "CODEX_HOOK_LIST_CLEANUP"):
            self.invoke()
        self.assertIn("settle", self.events)

    def test_cancellation_settles_group_without_success(self):
        class CancelInput(io.BytesIO):
            def write(self, value):
                raise KeyboardInterrupt
        self.process.stdin = CancelInput()
        with self.assertRaises(KeyboardInterrupt):
            self.invoke()
        self.assertIn("settle", self.events)
        self.assertTrue(self.process.stdin.closed)

    def test_settlement_exception_prevents_success(self):
        def refuse(*args, **kwargs):
            raise RuntimeError("synthetic settlement failure")
        self.owner.settle = refuse
        with self.assertRaisesRegex(ValueError, "CODEX_HOOK_LIST_CLEANUP") as caught:
            self.invoke()
        self.assertIsInstance(caught.exception.__cause__, RuntimeError)
        self.assertEqual(len(caught.exception.cleanup_errors), 1)

    def test_cleanup_error_keeps_primary_cause(self):
        self.process.stdout = io.BytesIO(b'{"id":1,"error":{}}\n')
        self.closure.complete = False
        with self.assertRaisesRegex(ValueError, "CODEX_HOOK_LIST_CLEANUP") as caught:
            self.invoke()
        self.assertIsNotNone(caught.exception.__cause__)
        self.assertIn("PROTOCOL_ERROR", str(caught.exception.__cause__))

if __name__ == "__main__":
    unittest.main()
