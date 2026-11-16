"""Pure diagnostic branch tests: no installer import or filesystem owner execution."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "production_installer.py"
FAILURE = "E_ATOMIC_DIRECTORY_PUBLISH_UNSUPPORTED"


class AtomicDirectoryDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tree = ast.parse(SOURCE.read_bytes())

    def guard(self):
        transaction = next(n for n in self.tree.body
                           if isinstance(n, ast.ClassDef) and n.name == "_InstallTransaction")
        method = next(n for n in transaction.body
                      if isinstance(n, ast.FunctionDef) and n.name == "_publish_retained")
        guards = [n for n in ast.walk(method) if isinstance(n, ast.If)
                  and any(isinstance(s, ast.Raise) and isinstance(s.exc, ast.Call)
                          and isinstance(s.exc.func, ast.Name) and s.exc.func.id == "_InstallFailure"
                          and s.exc.args and isinstance(s.exc.args[0], ast.Constant)
                          and s.exc.args[0].value == FAILURE for s in n.body)]
        self.assertEqual(len(guards), 1)
        return method, guards[0]

    def test_exact_selected_prepared_directory_only(self):
        _, guard = self.guard()

        class Diagnostic(Exception):
            pass

        code = compile(ast.fix_missing_locations(ast.Module(body=[guard], type_ignores=[])),
                       "pure-atomic-refusal", "exec")
        for kind in ("directory", "file", "symlink"):
            for effect_present in (False, True):
                for selected_source in (False, True):
                    for selected_target in (False, True):
                        with self.subTest(kind=kind, effect=effect_present,
                                          source=selected_source, target=selected_target):
                            scope = {
                                "source": "prepared" if selected_source else "other",
                                "target": "destination" if selected_target else "other",
                                "effect": SimpleNamespace(prepared_path="prepared", location="destination")
                                          if effect_present else None,
                                "_InstallFailure": Diagnostic,
                            }
                            scope["before"] = {scope["source"]: SimpleNamespace(kind=kind)}
                            selected = kind == "directory" and effect_present and selected_source and selected_target
                            if selected:
                                with self.assertRaises(Diagnostic) as caught:
                                    exec(code, scope)
                                self.assertEqual(caught.exception.args, (FAILURE, "transaction"))
                            else:
                                exec(code, scope)

    def test_refusal_has_no_effect_before_existing_fallback(self):
        method, guard = self.guard()
        self.assertEqual(len(guard.body), 1)
        self.assertIsInstance(guard.body[0], ast.Raise)
        parent = next(n for n in ast.walk(method)
                      if hasattr(n, "body") and isinstance(n.body, list) and guard in n.body)
        index = parent.body.index(guard)
        following = parent.body[index + 1]
        self.assertIsInstance(following, ast.If)
        self.assertTrue(any(isinstance(n, ast.Constant)
                            and n.value == "E_ROLLBACK_RESTORE_BLOCKED_BY_IDENTITY: unsupported retained type"
                            for n in ast.walk(following)))
        self.assertTrue(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                            and n.func.attr == "_native_publish_no_replace"
                            for s in parent.body[:index] for n in ast.walk(s)))

    def test_diagnostic_is_allowlisted(self):
        assignment = next(n for n in self.tree.body if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == "SLICE_A_FAILURE_IDS"
                                  for t in n.targets))
        values = ast.literal_eval(assignment.value.args[0])
        self.assertIn(FAILURE, values)

    def test_explanation_requires_typed_matching_failure(self):
        function = next(n for n in self.tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == "_installer_failure_text")
        branches = [n for n in ast.walk(function) if isinstance(n, ast.If)
                    and any(isinstance(v, ast.Constant) and v.value == FAILURE
                            for v in ast.walk(n.test))]
        self.assertEqual(len(branches), 1)
        branch = branches[0]
        code = compile(ast.fix_missing_locations(ast.Module(body=[branch], type_ignores=[])),
                       "pure-diagnostic-explanation", "exec")
        for typed in (False, True):
            for attributes in (None, {}):
                for identity in (FAILURE, "unavailable"):
                    output = []
                    exec(code, dict(typed=typed, attributes=attributes, identity=identity, additions=output))
                    self.assertEqual(bool(output), typed and attributes is not None and identity == FAILURE)
                    if output:
                        self.assertEqual(output, [
                            "filesystem cannot safely publish a directory without replacing an existing target"])


class NativePublicationDispatchTests(unittest.TestCase):
    def setUp(self):
        import ctypes
        import os
        from unittest.mock import patch
        self.ctypes = ctypes
        self.patch = patch
        self.os = os
        tree = ast.parse(SOURCE.read_bytes())
        owner = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                     and n.name == "_InstallTransaction")
        method = next(n for n in owner.body if isinstance(n, ast.FunctionDef)
                      and n.name == "_native_publish_no_replace")
        method.decorator_list = []
        self.code = compile(ast.fix_missing_locations(ast.Module(
            body=ast.parse("from __future__ import annotations").body + [method],
            type_ignores=[])), str(SOURCE), "exec")

    def operation(self, result=0):
        calls = []
        def invoke(*args):
            calls.append(args)
            return result
        invoke.calls = calls
        return invoke

    def run_dispatch(self, runtime, *, parents=(0, 12), platform="darwin", error=0):
        scope = {"os": SimpleNamespace(name="posix", fsencode=self.os.fsencode,
                                       strerror=self.os.strerror),
                 "sys": SimpleNamespace(platform=platform)}
        exec(self.code, scope)
        with self.patch.object(self.ctypes, "CDLL", return_value=runtime), self.patch.object(
                self.ctypes, "get_errno", return_value=error):
            return scope["_native_publish_no_replace"](
                Path("source/old"), Path("destination/new"), parent_descriptors=parents)

    def test_darwin_bound_uses_exact_parents_and_basenames(self):
        bound, unbound = self.operation(), self.operation()
        self.assertTrue(self.run_dispatch(SimpleNamespace(renameatx_np=bound, renamex_np=unbound)))
        self.assertEqual(bound.calls, [(0, b"old", 12, b"new", 4)])
        self.assertEqual(unbound.calls, [])
        self.assertEqual(bound.argtypes, [self.ctypes.c_int, self.ctypes.c_char_p,
                         self.ctypes.c_int, self.ctypes.c_char_p, self.ctypes.c_uint])
        self.assertIs(bound.restype, self.ctypes.c_int)

    def test_darwin_missing_bound_does_not_fall_back(self):
        unbound = self.operation()
        self.assertFalse(self.run_dispatch(SimpleNamespace(renamex_np=unbound)))
        self.assertEqual(unbound.calls, [])

    def test_darwin_unbound_unchanged(self):
        unbound, bound = self.operation(), self.operation()
        self.assertTrue(self.run_dispatch(SimpleNamespace(renamex_np=unbound, renameatx_np=bound),
                                          parents=None))
        self.assertEqual(unbound.calls, [(self.os.fsencode(Path("source/old")),
                                         self.os.fsencode(Path("destination/new")), 4)])
        self.assertEqual(bound.calls, [])
        self.assertEqual(unbound.argtypes, [self.ctypes.c_char_p, self.ctypes.c_char_p,
                                           self.ctypes.c_uint])

    def test_native_errors_preserve_capability_boundary(self):
        import errno
        for platform, symbol in (("darwin", "renameatx_np"), ("linux", "renameat2")):
            for error in (errno.ENOSYS, errno.EINVAL, errno.ENOTSUP, errno.EOPNOTSUPP):
                with self.subTest(platform=platform, error=error):
                    runtime = SimpleNamespace(**{symbol: self.operation(-1)})
                    self.assertFalse(self.run_dispatch(runtime, platform=platform, error=error))
            for error in (errno.EEXIST, errno.EBADF, errno.EXDEV, errno.EACCES):
                with self.subTest(platform=platform, error=error):
                    runtime = SimpleNamespace(**{symbol: self.operation(-1)})
                    with self.assertRaises(OSError) as caught:
                        self.run_dispatch(runtime, platform=platform, error=error)
                    self.assertEqual(caught.exception.errno, error)

    def test_linux_bound_dispatch_unchanged(self):
        operation = self.operation()
        self.assertTrue(self.run_dispatch(SimpleNamespace(renameat2=operation), platform="linux"))
        self.assertEqual(operation.calls, [(0, b"old", 12, b"new", 1)])


if __name__ == "__main__":
    unittest.main()
