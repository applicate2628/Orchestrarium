"""Pure legacy-heading regressions; reuse the memory-backed merge harness."""
from __future__ import annotations

import unittest

import test_codex_markdown_examples as examples


TAIL = "## Project policies\r\nUSER TAIL\r"
# Each row is one independently collected test, not an expanded native fixture.
CASES = (
    ("shared", "# Shared Governance\nOld\n" + TAIL, "", TAIL),
    ("codex", "# Codex Platform Rules\nOld\n" + TAIL, "", TAIL),
    ("delegation_prefix", "# Default Delegation Rule\nOld\n# Shared Governance\nOld\n" + TAIL, "", TAIL),
    ("atx_whitespace", "   #\tShared Governance ### \t\nOld\n" + TAIL, "   ", TAIL),
    ("bom", "\ufeff# Shared Governance\nOld\n" + TAIL, "\ufeff", TAIL),
    ("mixed_newlines", "\ufeffUser 😀\r\nKeep\r# Shared Governance\rOld\n" + TAIL, "\ufeffUser 😀\r\nKeep\r", TAIL),
    ("prose_substring", "Keep # Shared Governance in docs\nUSER RULE\n", None, None),
    ("longer_title", "# Shared Governance notes\nUSER RULE\n", None, None),
    ("h2", "## Shared Governance\nUSER RULE\n", None, None),
    ("blockquote", "> # Shared Governance\n> USER RULE\n", None, None),
    ("list", "- # Shared Governance\n  USER RULE\n", None, None),
    ("fenced", "```markdown\n# Shared Governance\nUSER RULE\n```\n", None, None),
    ("inline_code", "Use `# Shared Governance`\nUSER RULE\n", None, None),
    ("indented_code", "    # Shared Governance\n    USER RULE\n", None, None),
    ("setext", "Shared Governance\n=================\nUSER RULE\n", None, None),
    ("raw_policy_in_code", "# Shared Governance\nOld\n```markdown\n" + TAIL + "```\nUSER LAST", "", TAIL + "```\nUSER LAST"),
    ("legacy_eof", "# Shared Governance\nOld\n", "", ""),
    ("h3", "### Shared Governance\nUSER RULE\n", None, None),
    ("default_alone", "# Default Delegation Rule\nUSER RULE\n", None, None),
    ("emphasized_title", "# *Shared Governance*\nUSER RULE\n", None, None),
    ("linked_title", "# [Shared Governance](https://example.invalid)\nUSER RULE\n", None, None),
    ("one_space", " # Shared Governance\nOld\n" + TAIL, " ", TAIL),
    ("two_spaces", "  # Shared Governance\nOld\n" + TAIL, "  ", TAIL),
)


class CodexLegacyHeadingRecognitionTests(unittest.TestCase):
    def setUp(self):
        self.harness = examples.CodexMarkdownExampleTests(methodName="runTest")
        self.harness.setUp()

    def test_marked_path_does_not_parse_legacy_headings(self):
        def unexpected(*_args):
            self.fail("Marked replacement must not call the legacy heading parser")
        self.harness.scope["_markdown_document_h1_starts"] = unexpected
        prefix, tail = "USER PREFIX\r\n", "\rUSER TAIL"
        existing = prefix + self.harness.begin + "\nOld\n" + self.harness.end + tail
        self.assertEqual(self.harness.render(existing),
                         prefix + self.harness.pack.rstrip("\n") + tail)


def _case_test(existing, prefix, tail):
    def test(self):
        expected = (self.harness.pack + "\n" + existing if prefix is None
                    else prefix + self.harness.pack + tail)
        self.assertEqual(self.harness.render(existing).encode("utf-8"),
                         expected.encode("utf-8"))
    return test


for _name, _existing, _prefix, _tail in CASES:
    setattr(CodexLegacyHeadingRecognitionTests, "test_" + _name,
            _case_test(_existing, _prefix, _tail))


if __name__ == "__main__":
    unittest.main()
