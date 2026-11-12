"""Bounded runtime scalar admission, not a complete YAML parser."""
import json
from pathlib import Path
import runpy
import unittest
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MODULE = runpy.run_path(str(ROOT / 'scripts/validate-codex-skill-catalog-budget.py'))
PARSE = MODULE['_parse_frontmatter_scalars']

class ScalarAdmissionTests(unittest.TestCase):
    def test_unsupported_scalar_shapes_are_refused(self):
        for value in ('"unclosed', "'unclosed", '"closed" trailing', '[one, two]',
                      '{key: value}', '&anchor text', '*alias', '!tag text', '>2',
                      '|2-', '- item', '? key', ': value', 'one: two'):
            for key in ('name', 'description'):
                with self.subTest(value=value, key=key):
                    with self.assertRaises(ValueError):
                        PARSE(f'{key}: {value}', runtime_metadata=True)

    def test_supported_scalar_shapes_remain(self):
        for value, expected in (
            ('"[one, two]"', '[one, two]'), ("'{key: value}'", '{key: value}'),
            ('"hash # text" # comment', 'hash # text'),
            ('"escaped \\"quote\\""', 'escaped \\"quote\\"'),
            ("'it''s text'", "it''s text"), ('https://example.test/a', 'https://example.test/a'),
            ('-prefix', '-prefix'), ('ordinary text # comment', 'ordinary text'),
            ('>-\n  nested: prose\n  [body]', 'nested: prose [body]'),
            ('|\n  body', 'body'), ('null', ''), ('12345', '12345')):
            with self.subTest(value=value):
                self.assertEqual(PARSE('description: '+value, runtime_metadata=True)['description'], expected)

    def test_public_observation_refuses_malformed_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            skill = root / 'alpha' / 'SKILL.md'
            skill.parent.mkdir()
            for value, expected in (('"unterminated', 'binding-failure'),
                                    ('[one, two]', 'binding-failure'),
                                    ('{key: value}', 'binding-failure'),
                                    ('safe description', 'complete')):
                with self.subTest(value=value):
                    skill.write_text(f'---\nname: alpha\ndescription: {value}\n---\n', encoding='utf-8')
                    text = (f'<skills_instructions>\n- `r0` = `{root}`\n'
                            f'- alpha: {value} (file: r0/alpha/SKILL.md)\n</skills_instructions>')
                    payload = json.dumps([{'content': [{'type': 'input_text', 'text': text}]}])
                    result = MODULE['parse_runtime_prompt_input'](payload, root, root)
                    self.assertEqual(result.status, expected)

    def test_estimator_stays_tolerant(self):
        for value in ('"unclosed', '[one, two]', '{key: value}', '&anchor text', 'one: two'):
            self.assertEqual(PARSE('description: '+value)['description'], value)

if __name__ == '__main__':
    unittest.main()
