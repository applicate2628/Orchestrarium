"""Pure source-context and memory-backed merge regressions for a leading BOM."""
from __future__ import annotations

import unittest

import test_codex_markdown_examples as examples
from installer_markdown import document_context


class MarkdownBomPreservationTests(unittest.TestCase):
    def setUp(self):
        self.harness = examples.CodexMarkdownExampleTests(methodName="runTest")
        self.harness.setUp()

    def test_bom_only_has_no_code_span(self):
        self.assertEqual(document_context("\ufeff"), ("\ufeff", []))

    def test_bom_remains_visible_outside_first_code_span(self):
        source = "\ufeff" + "`value`"
        self.assertEqual(document_context(source), ("\ufeff       ", [(1, 8)]))

    def test_active_block_still_updates_and_keeps_bom(self):
        source = "\ufeff" + self.harness.begin + "\nOLD\n" + self.harness.end + "\nUSER"
        self.assertEqual(self.harness.render(source),
                         "\ufeff" + self.harness.pack.rstrip("\n") + "\nUSER")

    def test_noninitial_bom_is_not_removed(self):
        source = "USER\n\ufeffparagraph\n`value`\n"
        visible, spans = document_context(source)
        self.assertEqual(visible[:source.index("`")], source[:source.index("`")])
        self.assertEqual(spans, [(source.index("`"), source.rindex("`") + 1)])

    def test_only_one_leading_bom_is_an_envelope(self):
        source = "\ufeff\ufeff```markdown\nUSER\n```\n"
        visible, spans = document_context(source)
        tail_visible, tail_spans = document_context(source[1:])
        # A second BOM is actual document text, not another stripped envelope.
        self.assertTrue(visible.startswith("\ufeff\ufeff"))
        self.assertNotEqual(spans, [(start + 1, end + 1) for start, end in tail_spans])


def _context_case(source):
    def test(self):
        visible, spans = document_context(source)
        prefixed_visible, prefixed_spans = document_context("\ufeff" + source)
        self.assertEqual(prefixed_visible, "\ufeff" + visible)
        self.assertEqual(prefixed_spans, [(start + 1, end + 1) for start, end in spans])
        for start, end in prefixed_spans:
            self.assertEqual(("\ufeff" + source)[start:end], source[start - 1:end - 1])
    return test


def _merge_case(fence, newline, indent):
    def test(self):
        source = ("\ufeff" + indent + fence + "markdown" + newline
                  + self.harness.begin + newline + "USER SENTINEL 😀" + newline
                  + self.harness.end + newline + indent + fence + newline
                  + "USER FOOTER\r\n")
        self.harness.assert_example_preserved(source)
    return test


for _name, _source in (
    ("fence_lf", "```markdown\n`value`\n```\n"),
    ("fence_crlf", "~~~\r\nUSER\r\n~~~\r\n"),
    ("fence_cr", "```\rUSER\r```\r"),
    ("mixed_lines", "```\r\nUSER\rTAIL\n```\r"),
    ("indented", "    `example`\n    USER\n"),
    ("inline", "Use `example` now.\n"),
    ("image", "![`example`](target)\n"),
    ("quoted", "> ```\n> USER\n> ```\n"),
    ("unclosed_fence", "```markdown\nUSER\n"),
):
    setattr(MarkdownBomPreservationTests, "test_context_" + _name, _context_case(_source))

for _name, _fence, _newline, _indent in (
    ("backtick_lf", "```", "\n", ""),
    ("tilde_lf", "~~~", "\n", ""),
    ("backtick_crlf", "```", "\r\n", ""),
    ("tilde_cr", "~~~", "\r", ""),
    ("one_space", "```", "\n", " "),
    ("three_spaces", "```", "\r\n", "   "),
):
    setattr(MarkdownBomPreservationTests, "test_merge_" + _name,
            _merge_case(_fence, _newline, _indent))


if __name__ == "__main__":
    unittest.main()
