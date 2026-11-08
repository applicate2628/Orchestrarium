"""Pure Codex document selection tests; never load an installer."""
import importlib.util
from pathlib import Path
import sys
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/installation/instruction_selection.py"
SPEC = importlib.util.spec_from_file_location("codex_selection_under_test", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
parse = MODULE.parse_codex_document_grant
ERROR = "E_CODEX_DOCUMENT_SELECTION_INVALID"
DIGEST = "0123456789abcdef" * 4


class CodexDocumentSelectionTests(unittest.TestCase):
    def invalid(self, values):
        with self.assertRaisesRegex(ValueError, "^" + ERROR + "$"):
            parse(values)

    def test_empty_tuple_is_not_a_grant(self):
        self.assertIsNone(parse(()))

    def test_exact_digest_and_character_span(self):
        self.assertEqual(parse((DIGEST + ":0:1",)), (DIGEST, (0, 1)))
        self.assertEqual(parse((DIGEST + ":12:345",)), (DIGEST, (12, 345)))
        self.assertEqual(parse(("0" * 64 + ":1:2",)), ("0" * 64, (1, 2)))

    def test_bounds_against_current_text_belong_to_common_validator(self):
        self.assertEqual(parse((DIGEST + ":100000:200000",)),
                         (DIGEST, (100000, 200000)))

    def test_repeat_is_rejected_even_when_identical(self):
        value = DIGEST + ":0:1"
        self.invalid((value, value))
        self.invalid((value, DIGEST + ":1:2"))

    def test_wrong_container_types_are_rejected(self):
        for value in (None, True, False, 0, "", [], {}, set(),
                      [DIGEST + ":0:1"], DIGEST + ":0:1"):
            with self.subTest(value=value):
                self.invalid(value)
        class TupleSubclass(tuple):
            pass
        self.invalid(TupleSubclass())

    def test_wrong_entry_types_are_rejected(self):
        for value in (None, True, False, 0, 1.0, b"x", [], {}, ()):
            with self.subTest(value=value):
                self.invalid((value,))
        class StringSubclass(str):
            pass
        self.invalid((StringSubclass(DIGEST + ":0:1"),))

    def test_digest_is_exact_lowercase_ascii_hex(self):
        for digest in ("", "a" * 63, "a" * 65, "A" * 64, "g" * 64,
                       "０" * 64, " " + DIGEST, DIGEST + "\n",
                       DIGEST[:-1] + "\x00", "sha256:" + DIGEST):
            with self.subTest(digest=digest):
                self.invalid((digest + ":0:1",))

    def test_offsets_are_canonical_ascii_decimal(self):
        for offset in ("", "-1", "+1", "00", "01", " 1", "1 ", "1\n",
                       "1\t", "1\r", "1_0", "1.0", "1e2", "0x10",
                       "١", "１", "²", "\x001", "1\u200b"):
            with self.subTest(offset=offset):
                self.invalid((DIGEST + ":" + offset + ":9",))
                self.invalid((DIGEST + ":0:" + offset,))

    def test_end_must_be_strictly_after_start(self):
        for span in ("0:0", "1:1", "2:1", "100:99"):
            with self.subTest(span=span):
                self.invalid((DIGEST + ":" + span,))

    def test_missing_and_extra_separators(self):
        for value in ("", DIGEST, DIGEST + ":0", DIGEST + ":0:1:",
                      DIGEST + "::0:1", DIGEST + "=0:1",
                      DIGEST + ":0:1\n", "\n" + DIGEST + ":0:1"):
            with self.subTest(value=value):
                self.invalid((value,))

    def test_integer_conversion_limit_has_stable_error(self):
        limit = sys.get_int_max_str_digits()
        if not limit:
            self.skipTest("Interpreter integer digit limit is disabled")
        digits = "1" * (limit + 1)
        self.invalid((DIGEST + ":" + digits + ":" + digits + "0",))
        self.invalid((DIGEST + ":0:" + digits,))

    def test_input_is_unchanged_and_result_immutable(self):
        values = (DIGEST + ":0:1",)
        result = parse(values)
        self.assertEqual(values, (DIGEST + ":0:1",))
        self.assertIs(type(result), tuple)
        self.assertIs(type(result[1]), tuple)
        self.assertIs(type(result[1][0]), int)
        self.assertEqual(parse(values), result)


if __name__ == "__main__":
    unittest.main()
