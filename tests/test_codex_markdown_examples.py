"""Exercise only in-memory merge selection with the real bundled Markdown parser."""
from __future__ import annotations

import ast
import contextlib
import io
from pathlib import Path, PurePosixPath
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "production_installer.py"
sys.path.insert(0, str(ROOT / "scripts"))
from installer_markdown import document_context
from installation.document_outcomes import render_documents


class MemoryPath(PurePosixPath):
    texts = {}

    def read_text(self, *, encoding):
        assert encoding == "utf-8"
        return self.texts[str(self)]


class CodexMarkdownExampleTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(SOURCE.read_bytes())
        names = {"_merge_codex_agents", "_render_codex_document", "_codex_document_payload", "_warn_codex_project_budget", "_prepare_codex_agents"}
        functions = [node for node in tree.body
                     if isinstance(node, ast.FunctionDef) and node.name in names]
        self.assertEqual(len(functions), len(names))
        future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
        isolated = ast.fix_missing_locations(ast.Module(body=[future, *functions], type_ignores=[]))
        constants = {}
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in {"CODEX_BEGIN", "CODEX_END"}:
                        constants[target.id] = ast.literal_eval(node.value)
        self.existing = None
        self.writes = []
        self.scope = dict(constants,
                          _render_document_outcomes=render_documents,
                          _markdown_document_context=document_context,
                          _read_owned_text=lambda *_args, preserve_newlines: self.existing,
                          _write_owned_text=lambda *args: self.writes.append(args))
        exec(compile(isolated, str(SOURCE), "exec"), self.scope)
        self.merge = self.scope["_merge_codex_agents"]
        self.root = MemoryPath("/source")
        self.source = self.root / "src.codex"
        self.target = MemoryPath("/synthetic-project/AGENTS.md")
        MemoryPath.texts = {"/source/shared/AGENTS.shared.md": "# Shared Governance\nNew shared rule.\n",
                            "/source/src.codex/AGENTS.codex.md": "# Codex Platform Rules\nNew Codex rule.\n"}
        self.begin = constants["CODEX_BEGIN"]
        self.end = constants["CODEX_END"]
        self.pack = (self.begin + "\n# Shared Governance\nNew shared rule.\n\n"
                     "# Codex Platform Rules\nNew Codex rule.\n" + self.end + "\n")

    def render(self, existing, *, dry_run=False):
        self.existing = existing
        self.writes.clear()
        with contextlib.redirect_stdout(io.StringIO()):
            self.merge(self.root, self.source, self.target, dry_run)
        if dry_run:
            self.assertEqual(self.writes, [])
            return None
        self.assertEqual(len(self.writes), 1)
        target, content, owner = self.writes[0]
        self.assertEqual(target, self.target)
        self.assertIsNone(owner)
        return content

    def assert_example_preserved(self, existing):
        self.assertEqual(self.render(existing), self.pack + "\n" + existing)

    def test_fenced_marker_examples_are_preserved(self):
        for fence in ("```", "~~~~"):
            with self.subTest(fence=fence):
                example = ("# My project\nПравило 保留\n" + fence + "markdown\n"
                           + self.begin + "\nExample text.\n" + self.end + "\n"
                           + fence + "\nKeep this footer.\n")
                self.assert_example_preserved(example)

    def test_indented_marker_examples_are_preserved(self):
        example = ("# Project\n\n    " + self.begin + "\n    Example text.\n    "
                   + self.end + "\n\nUser footer.\n")
        self.assert_example_preserved(example)

    def test_inline_marker_examples_are_preserved(self):
        example = "Use `" + self.begin + "` and `" + self.end + "` as examples.\n"
        self.assert_example_preserved(example)

    def test_fenced_legacy_headings_are_preserved(self):
        for heading in ("# Shared Governance", "# Codex Platform Rules"):
            with self.subTest(heading=heading):
                self.assert_example_preserved(
                    "# Project\n\n```markdown\n" + heading
                    + "\nExample rule.\n## Project policies\nExample policy.\n```\nUser footer.\n")

    def test_inline_legacy_heading_is_preserved(self):
        self.assert_example_preserved("The heading `# Shared Governance` is only an example.\n")

    def test_real_marked_block_after_fenced_example_is_updated(self):
        example = "```markdown\n" + self.begin + "\nExample.\n" + self.end + "\n```\n"
        old = self.begin + "\nOld managed rule.\n" + self.end
        tail = "\n## Project policies\nKeep mine.\n"
        self.assertEqual(self.render(example + old + tail),
                         example + self.pack.rstrip("\n") + tail)

    def test_ordinary_marked_update_remains_compatible(self):
        prefix = "# User header\nKeep the header.\n"
        old = self.begin + "\nOld managed rule.\n" + self.end
        tail = "\n## Project policies\nKeep mine.\n"
        self.assertEqual(self.render(prefix + old + tail),
                         prefix + self.pack.rstrip("\n") + tail)

    def test_ordinary_legacy_update_remains_compatible(self):
        for heading in ("# Shared Governance", "# Codex Platform Rules"):
            with self.subTest(heading=heading):
                prefix = "# User preface\nKeep this preface.\n"
                tail = "## Project policies\nKeep mine.\n"
                self.assertEqual(self.render(prefix + heading + "\nOld factory rule.\n" + tail),
                                 prefix + self.pack + tail)

    def test_legacy_start_ignores_examples_without_expanding_raw_end(self):
        prefix = "```markdown\n# Shared Governance\nExample only.\n```\n"
        old = "# Shared Governance\nOld factory rule.\n\n```markdown\n"
        # A receipt-free legacy selector must not skip its old raw boundary
        # and expand the replaced extent, even when that boundary is code.
        tail = ("## Project policies\nExample only.\n```\nOld factory tail.\n"
                "## Project policies\nKeep mine.\n")
        self.assertEqual(self.render(prefix + old + tail), prefix + self.pack + tail)

    def test_unclosed_fence_in_active_block_preserves_user_tail(self):
        original = (self.begin + "\n# Shared Governance\nOld managed rule.\n"
                    + "```markdown\nUnclosed example.\n" + self.end
                    + "\n## Project policies\nUSER TAIL KEEP\n")
        self.assertEqual(self.render(original), self.pack.rstrip("\n")
                         + "\n## Project policies\nUSER TAIL KEEP\n")

    def test_incomplete_active_marker_never_enters_legacy_replacement(self):
        for marker in (self.begin, self.end):
            with self.subTest(marker=marker):
                original = marker + "\n# Shared Governance\nUSER TAIL KEEP\n"
                with self.assertRaisesRegex(ValueError, "E_CODEX_DOCUMENT_AMBIGUOUS"):
                    self.render(original)
                self.assertEqual(self.writes, [])

    def test_incomplete_marker_only_in_code_remains_an_example(self):
        self.assert_example_preserved("```markdown\n" + self.begin + "\n```\nKeep mine.\n")

    def test_masked_first_end_does_not_merge_two_real_blocks(self):
        tail = ("\n```\nUSER BETWEEN KEEP\n" + self.begin
                + "\nSecond body\n" + self.end + "\nUSER LAST KEEP\n")
        original = (self.begin + "\n# Shared Governance\n```markdown\nExample\n"
                    + self.end + tail)
        self.assertEqual(self.render(original), self.pack.rstrip("\n") + tail)

    def test_unclosed_legacy_fence_does_not_hide_raw_policy_boundary(self):
        original = ("# Shared Governance\nOld body\n```markdown\nExample\n"
                    "## Project policies\nUSER TAIL KEEP\n")
        self.assertEqual(self.render(original), self.pack
                         + "## Project policies\nUSER TAIL KEEP\n")

    def test_inline_end_keeps_the_existing_termination_limit(self):
        # This proves compatibility, not correct ownership or a complete
        # Markdown-aware frame. The old raw END still limits replacement.
        tail = "`\nOld\n" + self.end + "\nUSER TAIL KEEP\n"
        original = self.begin + "\nExample `" + self.end + tail
        self.assertEqual(self.render(original), self.pack.rstrip("\n") + tail)

    def test_two_complete_blocks_keep_second_block(self):
        tail = ("\nUSER BETWEEN KEEP\n" + self.begin
                + "\nSecond body\n" + self.end + "\nUSER LAST KEEP\n")
        original = self.begin + "\nFirst body\n" + self.end + tail
        self.assertEqual(self.render(original), self.pack.rstrip("\n") + tail)

    def test_end_only_before_selected_begin_refuses_without_write(self):
        original = self.end + "\nKeep this.\n" + self.begin + "\nUSER TAIL KEEP\n"
        with self.assertRaisesRegex(ValueError, "E_CODEX_DOCUMENT_AMBIGUOUS"):
            self.render(original)
        self.assertEqual(self.writes, [])

    def test_dry_run_does_not_call_writer(self):
        self.render("```\n" + self.begin + "\nExample.\n" + self.end + "\n```\n",
                    dry_run=True)

    def test_parser_refusal_is_not_suppressed_or_written(self):
        def refuse(_text):
            raise RuntimeError("synthetic parser refusal")
        self.scope["_markdown_document_context"] = refuse
        with self.assertRaisesRegex(RuntimeError, "synthetic parser refusal"):
            self.render("User text.\n")
        self.assertEqual(self.writes, [])

    def test_missing_document_does_not_require_parsing(self):
        def unexpected(_text):
            self.fail("An absent document has no examples to classify")
        self.scope["_markdown_document_context"] = unexpected
        self.assertEqual(self.render(None), self.pack)


if __name__ == "__main__":
    unittest.main()
