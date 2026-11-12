"""Unclaimed marked documents are user content, not automatic update authority.

These tests execute the actual merge functions with memory-backed paths. They
are a regression witness, not native installer/transaction receiving evidence.
"""
import unittest
import contextlib
import io

import test_codex_markdown_examples as examples


class UnclaimedMarkedDocumentTests(unittest.TestCase):
    def merge(self, original, *, dry_run=False):
        harness = examples.CodexMarkdownExampleTests("runTest")
        harness.setUp()
        harness.existing = original
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            harness.merge(harness.root, harness.source, harness.target, dry_run)
        return harness, output.getvalue()

    def test_unclaimed_marked_user_text_is_preserved(self):
        for newline in ("\n", "\r\n", "\r"):
            with self.subTest(newline=newline):
                harness = examples.CodexMarkdownExampleTests("runTest")
                harness.setUp()
                original = newline.join(("USER PREFIX", harness.begin,
                                         "USER AUTHORED RULE KEEP", harness.end,
                                         "USER SUFFIX", ""))
                observed, output = self.merge(original)
                self.assertEqual(observed.existing, original)
                self.assertEqual(observed.writes, [])
                self.assertIn("document preserved", output)
                self.assertIn("--replace-codex-document", output)

    def test_exact_existing_payload_is_unchanged(self):
        harness = examples.CodexMarkdownExampleTests("runTest")
        harness.setUp()
        original = "USER PREFIX\r\n" + harness.pack.rstrip("\n") + "\rUSER SUFFIX"
        observed, output = self.merge(original)
        self.assertEqual(observed.existing, original)
        self.assertEqual(observed.writes, [])
        self.assertEqual(output, "")

    def test_fresh_and_unmarked_plain_document_still_install(self):
        for original in (None, "# My rules\nKEEP\n"):
            observed, _ = self.merge(original)
            self.assertEqual(len(observed.writes), 1)
            if original is not None:
                self.assertTrue(observed.writes[0][1].endswith(original))

    def test_preview_does_not_propose_unclaimed_frame_replacement(self):
        harness = examples.CodexMarkdownExampleTests("runTest")
        harness.setUp()
        original = harness.begin + "\nPRIVATE RULE\n" + harness.end
        observed, output = self.merge(original, dry_run=True)
        self.assertEqual(observed.writes, [])
        self.assertIn("document preserved", output)
        self.assertNotIn("would merge", output)
        self.assertNotIn("PRIVATE RULE", output)


if __name__ == "__main__":
    unittest.main()
