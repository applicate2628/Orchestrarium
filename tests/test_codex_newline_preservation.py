"""Pure parser and memory-backed producer proof; never import the installer."""
from __future__ import annotations

import ast
import contextlib
import hashlib
import io
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "production_installer.py"
sys.path.insert(0, str(ROOT / "scripts"))
from installer_markdown import document_context


class MemoryPath(PurePosixPath):
    files = {}
    writes = []
    opens = []

    def is_file(self):
        return str(self) in self.files

    def open(self, mode, *, encoding, newline=None):
        assert mode == "r" and encoding == "utf-8"
        self.opens.append((str(self), newline))
        return io.TextIOWrapper(io.BytesIO(self.files[str(self)]),
                                encoding=encoding, newline=newline)

    def read_text(self, *, encoding):
        with self.open("r", encoding=encoding) as stream:
            return stream.read()

    def mkdir(self, *, parents, exist_ok):
        assert parents and exist_ok

    def write_text(self, content, *, encoding, newline):
        assert encoding == "utf-8" and newline == "\n"
        payload = content.encode(encoding)
        self.files[str(self)] = payload
        self.writes.append((str(self), payload))


class NewlinePreservationTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(SOURCE.read_bytes())
        names = {"_read_owned_text", "_write_owned_text", "_merge_codex_agents"}
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        self.assertEqual(len(functions), len(names))
        future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
        isolated = ast.fix_missing_locations(ast.Module(body=[future, *functions], type_ignores=[]))
        constants = {}
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in {"CODEX_BEGIN", "CODEX_END"}:
                        constants[target.id] = ast.literal_eval(node.value)
        self.scope = dict(constants, io=io, hashlib=hashlib,
                          _markdown_document_context=document_context,
                          _owned_byte_context=self.memory_context)
        exec(compile(isolated, str(SOURCE), "exec"), self.scope)
        self.root = MemoryPath("/source")
        self.source = self.root / "src.codex"
        self.target = MemoryPath("/project/AGENTS.md")
        self.begin, self.end = constants["CODEX_BEGIN"], constants["CODEX_END"]
        self.pack = (self.begin + "\n# Shared Governance\nNew shared rule.\n\n"
                     "# Codex Platform Rules\nNew Codex rule.\n" + self.end + "\n")
        MemoryPath.files = {
            "/source/shared/AGENTS.shared.md": b"# Shared Governance\nNew shared rule.\n",
            "/source/src.codex/AGENTS.codex.md": b"# Codex Platform Rules\nNew Codex rule.\n",
        }
        MemoryPath.writes = []
        MemoryPath.opens = []

    def owner(self, kind):
        if kind == "direct":
            return None
        transaction = SimpleNamespace(enabled=kind == "transaction")
        @contextlib.contextmanager
        def copy_reference(storage, node):
            # This is an in-memory payload source, not real ownership admission.
            yield object(), None
        transaction._copy_reference = copy_reference
        transaction._descriptor_bytes = lambda _descriptor, *, path: MemoryPath.files[str(path)]
        owner = SimpleNamespace(transaction=transaction, anchor=self.target.parent)
        def write_file(relative, payload, *, mode, fsync):
            self.assertIsNone(mode)
            self.assertEqual(fsync, "none")
            path = owner.anchor / relative
            MemoryPath.files[str(path)] = payload
            MemoryPath.writes.append((str(path), payload))
        owner.write_file = write_file
        return owner

    def memory_context(self, target, owner):
        # Never call the real filesystem-chain or identity implementation.
        payload = MemoryPath.files.get(str(target))
        node = None if payload is None else SimpleNamespace(data=hashlib.sha256(payload).hexdigest())
        return target, node, owner

    def seed(self, text):
        if text is None:
            MemoryPath.files.pop(str(self.target), None)
        else:
            MemoryPath.files[str(self.target)] = text.encode("utf-8")
        MemoryPath.writes.clear()

    def render(self, text, *, kind="direct", dry_run=False, project_scope=False):
        self.seed(text)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.scope["_merge_codex_agents"](
                self.root, self.source, self.target, dry_run,
                mutable_owner=self.owner(kind), project_scope=project_scope)
        return MemoryPath.files.get(str(self.target)), output.getvalue()

    def test_reader_default_keeps_normalization_for_other_callers(self):
        self.seed("one\r\ntwo\rthree\nfour")
        for kind in ("direct", "disabled", "transaction"):
            with self.subTest(kind=kind):
                self.assertEqual(self.scope["_read_owned_text"](self.target, self.owner(kind)),
                                 "one\ntwo\nthree\nfour")

    def test_reader_opt_in_preserves_original_newlines(self):
        original = "one\r\ntwo\rthree\nРусский 保留 😀"
        self.seed(original)
        for kind in ("direct", "disabled", "transaction"):
            with self.subTest(kind=kind):
                self.assertEqual(self.scope["_read_owned_text"](
                    self.target, self.owner(kind), preserve_newlines=True), original)

    def test_absent_input_is_still_absent(self):
        for kind in ("direct", "disabled", "transaction"):
            for preserve in (False, True):
                with self.subTest(kind=kind, preserve=preserve):
                    self.assertIsNone(self.scope["_read_owned_text"](
                        self.target, self.owner(kind), preserve_newlines=preserve))

    def test_foreign_document_keeps_all_original_bytes(self):
        for kind in ("direct", "disabled", "transaction"):
            for text in ("Header\r\nKeep\r\n", "Header\rKeep\r",
                         "Header\r\nKeep\rРусский\n保留 😀", ""):
                with self.subTest(kind=kind, text=text):
                    result, _ = self.render(text, kind=kind)
                    self.assertEqual(result, (self.pack + "\n" + text).encode("utf-8"))

    def test_marked_update_preserves_both_outside_slices(self):
        for kind in ("direct", "disabled", "transaction"):
            for nl in ("\n", "\r\n", "\r"):
                with self.subTest(kind=kind, nl=nl):
                    prefix = "Русский 😀" + nl + "保留" + nl
                    suffix = nl + "USER TAIL" + nl + "No final newline"
                    original = prefix + self.begin + nl + "Old" + nl + self.end + suffix
                    result, _ = self.render(original, kind=kind)
                    self.assertEqual(result, (prefix + self.pack.rstrip("\n") + suffix).encode("utf-8"))

    def test_legacy_update_preserves_exact_raw_policy_suffix(self):
        prefix = "USER PREFIX\r\nРусский\r"
        suffix = "## Project policies\r\nUSER TAIL\rLast\n"
        original = prefix + "# Shared Governance\rOld\r\n" + suffix
        for kind in ("direct", "transaction"):
            with self.subTest(kind=kind):
                self.assertEqual(self.render(original, kind=kind)[0],
                                 (prefix + self.pack + suffix).encode("utf-8"))

    def test_example_prefix_does_not_shift_real_start(self):
        for nl in ("\r\n", "\r"):
            prefix = nl.join(["Русский 😀", "```markdown", self.begin, "Example",
                              self.end, "```", "USER PREFIX", ""])
            suffix = nl + "USER TAIL" + nl
            original = prefix + self.begin + nl + "Old" + nl + self.end + suffix
            self.assertEqual(self.render(original)[0],
                             (prefix + self.pack.rstrip("\n") + suffix).encode("utf-8"))

    def test_raw_end_does_not_expand_across_hidden_end_or_second_block(self):
        suffix = "\r\n```\rUSER BETWEEN\n" + self.begin + "\rSecond\r\n" + self.end + "\rUSER LAST"
        original = self.begin + "\r\n# Shared Governance\r```markdown\nExample\r" + self.end + suffix
        self.assertEqual(self.render(original)[0],
                         (self.pack.rstrip("\n") + suffix).encode("utf-8"))

    def test_raw_legacy_policy_is_not_hidden_by_unclosed_fence(self):
        suffix = "## Project policies\r\nUSER TAIL\r"
        original = "# Shared Governance\rOld\r\n```markdown\rExample\n" + suffix
        self.assertEqual(self.render(original)[0], (self.pack + suffix).encode("utf-8"))

    def test_missing_end_does_not_write_or_change_original_bytes(self):
        original = "User\r\n" + self.begin + "\rOld\nUSER TAIL"
        self.seed(original)
        with self.assertRaisesRegex(ValueError, "E_CODEX_DOCUMENT_AMBIGUOUS"):
            self.scope["_merge_codex_agents"](self.root, self.source, self.target, False)
        self.assertEqual(MemoryPath.files[str(self.target)], original.encode("utf-8"))
        self.assertEqual(MemoryPath.writes, [])

    def test_repeat_update_is_byte_identical(self):
        original = "User\r\nРусский\r保留\n"
        for kind in ("direct", "transaction"):
            first, _ = self.render(original, kind=kind)
            second, _ = self.render(first.decode("utf-8"), kind=kind)
            self.assertEqual(first, second)

    def test_dry_run_does_not_write_or_normalize_original(self):
        original = "User\r\nKeep\rLast"
        result, _ = self.render(original, dry_run=True)
        self.assertEqual(result, original.encode("utf-8"))
        self.assertEqual(MemoryPath.writes, [])

    def test_project_warning_counts_preserved_utf8_bytes(self):
        original = "Русский\r\n😀\rKeep\n"
        result, output = self.render(original, project_scope=True)
        self.assertIn(f"rendered document: {len(result)} UTF-8 bytes", output)

    def test_parser_offsets_preserve_original_slices(self):
        for nl in ("\n", "\r\n", "\r"):
            for code in ("`INLINE`", "```markdown" + nl + "BODY" + nl + "```",
                         "    INDENTED", "[`LINK`](destination)", "![`IMAGE`](image)"):
                with self.subTest(nl=nl, code=code):
                    source = "Русский 😀" + nl + nl + code + nl + "AFTER"
                    visible, spans = document_context(source)
                    self.assertEqual(len(visible), len(source))
                    inner = code + nl if code.startswith(("    ", "```")) else code[code.index("`"):code.rindex("`") + 1]
                    start = source.index(inner)
                    self.assertEqual(spans, [(start, start + len(inner))])
                    self.assertEqual(source[spans[0][0]:spans[0][1]], inner)
                    self.assertEqual(visible.index("AFTER"), source.index("AFTER"))
                    for start, end in spans:
                        self.assertTrue(0 <= start < end <= len(source))
                        self.assertNotIn("INLINE", visible[start:end])
                    self.assertTrue(all(a[1] <= b[0] for a, b in zip(spans, spans[1:])))

    def test_multiline_code_examples_preserve_original_bytes(self):
        for nl in ("\r\n", "\r"):
            for code in (
                "`" + self.begin + nl + "example " + self.end + "`",
                "`# Shared Governance" + nl + "Example`",
                "~~~~markdown" + nl + self.begin + nl + self.end + nl + "~~~~",
                "    " + self.begin + nl + "    " + self.end,
                "> ```markdown" + nl + "> " + self.begin + nl + "> " + self.end + nl + "> ```",
            ):
                with self.subTest(nl=nl, code=code):
                    original = "\ufeffUser 😀" + nl + nl + code + nl + nl + "USER TAIL"
                    self.assertEqual(self.render(original)[0],
                                     (self.pack + "\n" + original).encode("utf-8"))


    def test_html_block_interruption_keeps_existing_commonmark_semantics(self):
        # A line-start HTML block interrupts the paragraph, so these ticks do
        # not form a committed multiline code span in the bundled dialect.
        for nl in ("\n", "\r\n", "\r"):
            prefix = "USER PREFIX" + nl + nl + "`"
            suffix = "`" + nl + "USER TAIL"
            original = prefix + self.begin + nl + self.end + suffix
            self.assertEqual(self.render(original)[0],
                             (prefix + self.pack.rstrip("\n") + suffix).encode("utf-8"))

    def test_inline_raw_end_retains_old_termination_semantics(self):
        suffix = "`\r\nOld\r" + self.end + "\r\nUSER TAIL"
        original = self.begin + "\r\nExample `" + self.end + suffix
        self.assertEqual(self.render(original)[0],
                         (self.pack.rstrip("\n") + suffix).encode("utf-8"))

    def test_invalid_utf8_still_refuses_before_writing(self):
        for kind in ("direct", "transaction"):
            for preserve in (False, True):
                with self.subTest(kind=kind, preserve=preserve):
                    MemoryPath.files[str(self.target)] = b"USER\r\n\xff"
                    with self.assertRaises(UnicodeDecodeError):
                        self.scope["_read_owned_text"](
                            self.target, self.owner(kind), preserve_newlines=preserve)
                    self.assertEqual(MemoryPath.files[str(self.target)], b"USER\r\n\xff")
                    self.assertEqual(MemoryPath.writes, [])

    def test_rendered_pack_retains_its_lf_convention(self):
        for path, payload in list(MemoryPath.files.items()):
            MemoryPath.files[path] = payload.replace(b"\n", b"\r\n")
        self.assertEqual(self.render(None)[0], self.pack.encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
