"""Reject ambiguous runtime observations without starting a host."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "validate-codex-skill-catalog-budget.py"
spec = importlib.util.spec_from_file_location("catalog_json_boundary", SOURCE)
catalog = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = catalog
spec.loader.exec_module(catalog)

class RuntimeJSONTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pack = Path(self.temp.name)
        path = self.pack / "alpha" / "SKILL.md"
        path.parent.mkdir()
        path.write_text("---\nname: alpha\ndescription: public sample\n---\n", encoding="utf-8")
        self.text = json.dumps(f"<skills_instructions>\n- `r1` = `{self.pack}`\n- alpha: public sample (file: r1/alpha/SKILL.md)\n</skills_instructions>")
        self.item = '{"type":"input_text","text":' + self.text + '}'
        self.payload = '[{"content":[' + self.item + ']}]'

    def scan(self, encoded):
        return catalog.parse_runtime_prompt_input(encoded, self.pack, self.pack)

    def malformed(self, encoded):
        actual = self.scan(encoded)
        self.assertEqual((actual.status, actual.diagnostic), ("malformed", "CATALOG-RUNTIME-MALFORMED"))

    def test_complete_control(self):
        self.assertEqual(self.scan(self.payload).status, "complete")

    def test_duplicate_content(self):
        self.malformed('[{"content":[],"content":[' + self.item + ']}]')

    def test_duplicate_text(self):
        self.malformed('[{"content":[{"type":"input_text","text":"hidden","text":' + self.text + '}]}]')

    def test_duplicate_type(self):
        self.malformed('[{"content":[{"type":"output_text","type":"input_text","text":' + self.text + '}]}]')

    def test_same_value_duplicate_is_still_ambiguous(self):
        self.malformed('[{"content":[{"type":"input_text","type":"input_text","text":' + self.text + '}]}]')

    def test_escaped_duplicate_key(self):
        self.malformed(self.payload.replace('"content":', '"con\\u0074ent":[],"content":', 1))

    def test_nested_duplicate_metadata(self):
        self.malformed(self.payload.replace('"content":', '"metadata":{"id":1,"id":2},"content":', 1))

    def test_equal_keys_in_distinct_objects_are_valid(self):
        self.assertEqual(self.scan('[{"content":[]},' + self.payload[1:]).status, "complete")

    def test_valid_nested_metadata_is_unchanged(self):
        self.assertEqual(self.scan(self.payload.replace('"content":', '"metadata":{"id":1},"content":', 1)).status, "complete")

    def test_nonfinite_constants_are_not_json(self):
        for constant in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(constant=constant):
                self.malformed(self.payload.replace('"content":', '"metadata":' + constant + ',"content":', 1))

    def test_constant_words_inside_strings_are_valid(self):
        self.assertEqual(self.scan(self.payload.replace('"content":', '"metadata":"NaN Infinity -Infinity","content":', 1)).status, "complete")

    def test_malformed_json_remains_malformed(self):
        self.malformed('[')

if __name__ == "__main__":
    unittest.main()
