"""Pure selected-document checks; no installer or physical operations."""
from pathlib import Path
import hashlib
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from installation import configuration as config
from installer_markdown import document_context


class SelectedDocumentTests(unittest.TestCase):
    def digest(self, text):
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def validate(self, text, kind, span, digest=None, context=document_context):
        return config.validate_selected_document(
            text, kind, context, document_digest=self.digest(text) if digest is None else digest,
            span=span)

    def render(self, text, kind, span, payload="New policy.\n"):
        return config.render_selected_document(
            text, kind, payload, document_context, document_digest=self.digest(text), span=span)

    def frame(self, kind="codex", body="Old\n"):
        begin, end = config.MARKERS[kind]
        return begin + "\n" + body + end

    def test_marked_kinds_preserve_exact_unicode_mixed_newlines(self):
        prefix, suffix = "User \U0001f600\r\nKeep\rLine\n", "\r\nTail\rFinal\n"
        for kind in ("codex", "claude", "shared", "copilot"):
            with self.subTest(kind=kind):
                text = prefix + self.frame(kind) + suffix
                span = (len(prefix), len(text) - len(suffix))
                self.assertEqual(self.validate(text, kind, span), span)
                result = self.render(text, kind, span)
                self.assertEqual(result, prefix + self.frame(kind, "New policy.\n") + suffix)

    def test_marked_selection_must_equal_frame(self):
        text = self.frame() + "\nTAIL\n"
        for span in ((0, len(text)), (1, len(self.frame())), (0, 3)):
            with self.assertRaises(ValueError):
                self.validate(text, "codex", span)

    def test_closed_fenced_literal_end_is_not_boundary(self):
        end = config.MARKERS["codex"][1]
        text = self.frame(body="Old\n```markdown\n" + end + "\n```\n") + "\nTAIL"
        span = (0, len(text) - len("\nTAIL"))
        self.assertEqual(self.render(text, "codex", span), self.frame(body="New policy.\n") + "\nTAIL")

    def test_malformed_multiple_reversed_and_unclosed_frames_refuse(self):
        begin, end = config.MARKERS["codex"]
        for text in (begin + "\nOld", end + "\n" + begin,
                     self.frame() + "\n" + self.frame(),
                     begin + "\n```\n" + end,
                     "# Shared Governance\n" + begin[:-1] + "\n",
                     "# Shared Governance\n" + end[:-1] + "\n"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.render(text, "codex", (0, len(text)))

    def test_hidden_start_never_acquires_frame(self):
        text = "```\n" + self.frame() + "\n```\n"
        with self.assertRaises(ValueError):
            self.validate(text, "codex", (4, len(text)-5))

    def test_raw_digest_not_normalized_or_stale(self):
        text = "# Shared Governance\r\nOld\r\n"
        for digest in (config.text_receipt_digest(text), "0" * 64, None, b"x", 4):
            with self.subTest(digest=digest), self.assertRaises(ValueError):
                config.validate_selected_document(text, "codex", document_context,
                                                  document_digest=digest, span=(0, len(text)))

    def test_types_offsets_and_crlf_splits_refuse(self):
        text = "# Shared Governance\r\nOld\r\nTAIL"
        for span in (None, [], [0, len(text)], (0,), (False, len(text)),
                     (0, True), (0.0, len(text)), (-1, len(text)),
                     (0, len(text)+1), (2, 1), (0, 0), (0, text.index("\n")),
                     (text.index("\n"), len(text)), ("0", len(text))):
            with self.subTest(span=span), self.assertRaises(ValueError):
                self.validate(text, "codex", span)
        for value in (None, b"text", 1):
            with self.assertRaises(ValueError):
                config.validate_selected_document(value, "codex", document_context,
                                                  document_digest="0"*64, span=(0, 1))

    def test_legacy_headers_keep_explicit_user_tail(self):
        for header in ("# Shared Governance", "# Codex Platform Rules\t"):
            for newline in ("\n", "\r\n", "\r"):
                prefix = "User \u2603" + newline
                selected = header + newline + "Old" + newline
                tail = "## User policy" + newline + "KEEP" + newline
                text = prefix + selected + tail
                span = (len(prefix), len(prefix + selected))
                self.assertEqual(self.validate(text, "codex", span), span)
                self.assertEqual(self.render(text, "codex", span),
                                 prefix + self.frame(body="New policy.\n") + "\n" + tail)

    def test_legacy_only_codex_and_exact_header(self):
        for kind in ("claude", "shared", "copilot", "unknown", None):
            text = "# Shared Governance\nOld\n"
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.validate(text, kind, (0, len(text)))
        for text in (" # Shared Governance\n", "# Shared Governance extra\n",
                     "# Shared GovernanceX\n", "# Unrelated\n"):
            with self.assertRaises(ValueError):
                self.validate(text, "codex", (0, len(text)))

    def test_legacy_boundary_inside_code_refuses(self):
        text = "# Shared Governance\n```\ninside\n```\nTAIL\n"
        with self.assertRaises(ValueError):
            self.validate(text, "codex", (0, text.index("inside")))
        text = "```\n# Shared Governance\nOld\n```\n"
        with self.assertRaises(ValueError):
            self.validate(text, "codex", (4, len(text)))

    def test_invalid_payload_and_unclosed_payload_fence_refuse(self):
        text = self.frame()
        for payload in ("", "no newline", "bad\0\n", "```\n",
                        config.MARKERS["claude"][0] + "\n"):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.render(text, "codex", (0, len(text)), payload)

    def test_parser_failure_propagates(self):
        text = "User `\n\n# Shared Governance\nOld\n"
        # A parser callback must remain authoritative; its ambiguity propagates.
        def refused(_text):
            raise RuntimeError("context origin unavailable")
        with self.assertRaisesRegex(RuntimeError, "context origin unavailable"):
            self.validate(text, "codex", (8, len(text)), context=refused)

    def test_final_composed_frame_is_rechecked_with_supplied_context(self):
        text = self.frame() + "\nUSER TAIL\n"
        span = (0, len(self.frame()))
        observed = []
        def changed_context(source):
            observed.append(source)
            visible, spans = document_context(source)
            if "New policy." in source and "USER TAIL" in source:
                # Exercise the final-frame invariant independently of parser
                # grammar: both original and standalone replacement are valid.
                return " " * len(source), [(0, len(source))]
            return visible, spans
        with self.assertRaisesRegex(ValueError, "Invalid selected managed document frame"):
            config.render_selected_document(
                text, "codex", "New policy.\n", changed_context,
                document_digest=self.digest(text), span=span)
        self.assertIn(self.frame(body="New policy.\n") + "\nUSER TAIL\n", observed)

    def test_suffix_marker_cannot_expand_new_frame(self):
        text = "# Shared Governance\nOld\n```\n" + self.frame() + "\n```\n"
        # The original closing fence becomes an opening fence after selection;
        # the previously hidden extra block becomes visible.
        stop = text.index(config.MARKERS["codex"][0])
        with self.assertRaises(ValueError):
            self.render(text, "codex", (0, stop))


if __name__ == "__main__":
    unittest.main()
