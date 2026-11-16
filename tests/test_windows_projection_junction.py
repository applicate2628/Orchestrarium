"""Real source methods with inert native participants, not Windows qualification."""
import ast
from contextlib import contextmanager
import ctypes
from pathlib import Path
import stat
import struct
from types import SimpleNamespace
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "scripts/production_installer.py"


def load_methods():
    tree = ast.parse(SOURCE.read_bytes())
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in {
            "_is_directory_junction", "_projection_resolves_to"
        }:
            nodes.append(node)
        if isinstance(node, ast.ClassDef) and node.name == "_InstallTransaction":
            nodes.extend(child for child in node.body if isinstance(child, ast.FunctionDef)
                         and child.name == "_create_owned_projection")
        if isinstance(node, ast.ClassDef) and node.name == "_WindowsBoundNode":
            method = next(child for child in node.body if isinstance(child, ast.FunctionDef)
                          and child.name == "target_reparse_data")
            nodes.append(ast.ClassDef(name="NativeCodec", bases=[], keywords=[],
                                     body=[method], decorator_list=[]))
    ns = {"stat": stat, "os": SimpleNamespace(name="nt")}
    future = ast.parse("from __future__ import annotations").body
    exec(compile(ast.fix_missing_locations(ast.Module(body=future + nodes, type_ignores=[])),
                 str(SOURCE), "exec"), ns)
    return ns


class ProjectionOwnerTests(unittest.TestCase):
    def setUp(self):
        self.ns = load_methods()
        self.events, self.records, self.encodings = [], [], []
        self.source, self.target = object(), object()
        self.creator_proof, self.target_proof = object(), object()
        self.empty = SimpleNamespace(native_proof=self.creator_proof, reparse_data=None)
        self.final = SimpleNamespace(native_proof=self.creator_proof, reparse_data=b"junction")
        self.set_error = None
        self.changed_target = False
        self.wrong_follow = False
        self.capture_count = 0
        outer = self

        class Bound:
            def __init__(self, path, *, purpose="observe", follow=False):
                outer.events.append(("acquire", path, purpose, follow))
                self.path = path

            def __enter__(self):
                outer.events.append(("enter", self.path))
                return self

            def __exit__(self, *args):
                outer.events.append(("close", self.path))

            @property
            def proof(self):
                if self.path is outer.source:
                    return object() if outer.changed_target and outer.capture_count == 2 else outer.target_proof
                return object() if outer.wrong_follow else outer.target_proof

            @classmethod
            @contextmanager
            def create(cls, path, *, directory):
                outer.events.append(("create", path, directory))
                born = SimpleNamespace(creator_proof=outer.creator_proof)
                def set_data(raw):
                    outer.events.append(("set", raw))
                    if outer.set_error is not None:
                        raise outer.set_error
                born.set_reparse_data = set_data
                outer.created = born
                try:
                    yield born
                finally:
                    outer.events.append(("creator-close", path))

            @staticmethod
            def target_reparse_data(original, *, junction):
                outer.encodings.append((original.path, junction))
                return b"junction" if junction else b"symlink"

        self.ns["_WindowsBoundNode"] = Bound
        self.ns["_projection_resolves_to"] = lambda target, source: True
        def capture(target, **kwargs):
            self.capture_count += 1
            self.assertIs(target, self.target)
            self.assertIs(kwargs.get("bound_node"), self.created)
            return self.empty if self.capture_count == 1 else self.final
        def matches(target, state):
            self.events.append(("matches", target))
            return state == {self.target: self.final}
        self.owner = SimpleNamespace(_capture_node=capture, _image_matches=matches)

    def run_projection(self, **kwargs):
        return self.ns["_create_owned_projection"](
            self.owner, self.source, self.target,
            lambda path, node: self.records.append((path, node)), **kwargs)

    def test_default_uses_junction_with_same_creator_and_target_checks(self):
        self.assertIs(self.run_projection(), self.final)
        self.assertEqual(self.encodings, [(self.source, True)])
        self.assertEqual(self.records, [(self.target, self.empty), (self.target, self.final)])
        self.assertEqual(sum(event[0] == "create" for event in self.events), 1)
        self.assertEqual(sum(event[0] == "set" for event in self.events), 1)
        close = self.events.index(("creator-close", self.target))
        follow = self.events.index(("acquire", self.target, "observe", True))
        self.assertLess(close, follow)

    def test_explicit_symlink_route_remains_explicit(self):
        self.final.reparse_data = b"symlink"
        self.run_projection(junction=False)
        self.assertEqual(self.encodings, [(self.source, False)])

    def test_native_failure_is_not_retried_or_relabelled(self):
        self.set_error = OSError("native denial")
        with self.assertRaises(OSError) as raised:
            self.run_projection()
        self.assertIs(raised.exception, self.set_error)
        self.assertEqual(self.records, [(self.target, self.empty)])
        self.assertEqual(sum(event[0] == "set" for event in self.events), 1)
        self.assertEqual(sum(event[0] == "create" for event in self.events), 1)
        self.assertFalse(any(event[0] == "acquire" and event[1] is self.target for event in self.events))
        self.assertEqual(self.events[-1], ("creator-close", self.target))

    def test_wrong_creator_proof_refuses(self):
        self.final.native_proof = object()
        with self.assertRaisesRegex(ValueError, "creator metadata"):
            self.run_projection(junction=True)

    def test_wrong_reparse_image_refuses(self):
        self.final.reparse_data = b"foreign"
        with self.assertRaisesRegex(ValueError, "creator metadata"):
            self.run_projection(junction=True)

    def test_target_drift_refuses(self):
        self.changed_target = True
        with self.assertRaisesRegex(ValueError, "target drift"):
            self.run_projection(junction=True)

    def test_wrong_followed_object_refuses(self):
        self.wrong_follow = True
        with self.assertRaisesRegex(ValueError, "target identity"):
            self.run_projection(junction=True)

    def test_final_image_mismatch_refuses(self):
        self.owner._image_matches = lambda *args: False
        with self.assertRaisesRegex(ValueError, "projection postcondition"):
            self.run_projection(junction=True)

    def test_posix_private_branch_unchanged(self):
        self.ns["os"].name = "posix"
        calls = []
        target = SimpleNamespace(symlink_to=lambda *args, **kwargs: calls.append((args, kwargs)))
        node = object()
        self.owner._capture_node = lambda path: node
        self.assertIs(self.ns["_create_owned_projection"](
            self.owner, self.source, target, lambda *args: None), node)
        self.assertEqual(calls, [((self.source,), {"target_is_directory": True})])
        self.assertEqual(self.events, [])


class JunctionRecognitionTests(unittest.TestCase):
    def setUp(self):
        self.ns = load_methods()

    def path(self, tag=None, *, error=None, symlink=False):
        def lstat():
            if error:
                raise error
            return SimpleNamespace(st_reparse_tag=tag)
        return SimpleNamespace(lstat=lstat, is_symlink=lambda: symlink,
                               resolve=lambda **kwargs: "resolved")

    def test_exact_mount_point_on_python_without_isjunction(self):
        self.ns["os"].path = SimpleNamespace(samefile=lambda a, b: a == b)
        path = self.path(0xA0000003)
        self.assertTrue(self.ns["_projection_resolves_to"](path, path))

    def test_other_reparse_and_ordinary_tags_are_not_junctions(self):
        for tag in (None, 0, 0xA000000C, 0x8000001B):
            with self.subTest(tag=tag):
                self.assertFalse(self.ns["_is_directory_junction"](self.path(tag)))

    def test_missing_or_denied_leaf_is_not_junction(self):
        for error in (FileNotFoundError(), PermissionError()):
            with self.subTest(error=type(error).__name__):
                self.assertFalse(self.ns["_is_directory_junction"](self.path(error=error)))

    def test_missing_metadata_attribute_is_not_junction(self):
        self.assertFalse(self.ns["_is_directory_junction"](
            SimpleNamespace(lstat=lambda: SimpleNamespace())))

    def test_junction_support_uses_shared_recognizer_everywhere(self):
        tree = ast.parse(SOURCE.read_bytes())
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == "_is_directory_junction"]
        self.assertGreaterEqual(len(calls), 4)
        self.assertNotIn('getattr(os.path, "isjunction", lambda _path: False)', SOURCE.read_text())


class ReparseEncodingTests(unittest.TestCase):
    def test_real_codec_encodes_junction_and_explicit_symlink_layouts(self):
        for junction, tag, start in ((True, 0xA0000003, 16), (False, 0xA000000C, 20)):
            with self.subTest(junction=junction):
                codec = load_methods()["NativeCodec"]
                class UnicodeString(ctypes.Structure):
                    _fields_ = [("length", ctypes.c_uint16), ("maximum_length", ctypes.c_uint16),
                                ("buffer", ctypes.c_void_p)]
                canonical_name = "\\\\?\\C:\\synthetic\\canonical"
                substitute = "\\??\\C:\\synthetic\\canonical".encode("utf-16-le")
                kept = ctypes.create_string_buffer(substitute)
                freed, handles = [], []
                def canonical(handle, buffer, size, flags):
                    handles.append(handle)
                    if buffer is not None:
                        buffer.value = canonical_name
                        return len(canonical_name)
                    return len(canonical_name) + 1
                def convert(name, out, *args):
                    self.assertEqual(name, canonical_name)
                    out._obj.length = len(substitute)
                    out._obj.buffer = ctypes.addressof(kept)
                    return 0
                def free(out):
                    freed.append(out._obj.buffer)
                kernel = SimpleNamespace(GetFinalPathNameByHandleW=canonical)
                nt = SimpleNamespace(RtlDosPathNameToNtPathName_U_WithStatus=convert,
                                     RtlFreeUnicodeString=free)
                W = SimpleNamespace(HANDLE=ctypes.c_void_p, LPWSTR=ctypes.c_wchar_p,
                                    DWORD=ctypes.c_uint32, LPCWSTR=ctypes.c_wchar_p,
                                    LPVOID=ctypes.c_void_p)
                codec._api = lambda: (ctypes, W, kernel)
                codec._creation_bindings = (nt, None, UnicodeString)
                codec._target_bindings = None
                raw = codec.target_reparse_data(SimpleNamespace(live_handle=31), junction=junction)
                self.assertEqual(struct.unpack_from("<IHH", raw), (tag, len(raw) - 8, 0))
                offset, length, printable_offset, printable_length = struct.unpack_from("<HHHH", raw, 8)
                self.assertEqual(raw[start + offset:start + offset + length], substitute)
                self.assertEqual(raw[start + printable_offset:start + printable_offset + printable_length],
                                 canonical_name.encode("utf-16-le"))
                self.assertEqual(raw[-2:], b"\0\0")
                self.assertEqual(len(freed), 1)
                self.assertEqual(handles, [31, 31])


if __name__ == "__main__":
    unittest.main()
