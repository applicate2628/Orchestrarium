"""Identifier-prefix matching preserves detector semantics and terminates on long lines."""
from __future__ import annotations
import importlib.util
import itertools
import os
from pathlib import Path
import random
import subprocess
import sys
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/universal-hooks/scripts/check-publication-safety.py'


class TestIdentifierPrefix(unittest.TestCase):
    def setUp(self):
        self.enterContext(mock.patch.dict(sys.modules))
        spec = importlib.util.spec_from_file_location('_identifier_prefix_test', SOURCE)
        self.owner = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.owner
        spec.loader.exec_module(self.owner)

    @staticmethod
    def fingerprint(match):
        return None if match is None else (match.span(), match.group(0))

    def test_exhaustive_and_seeded_match_equivalence(self):
        cases = (''.join(chars) for n in range(6)
                 for chars in itertools.product('aZ0_:/!\n', repeat=n))
        rng = random.Random(77321)
        random_cases = (''.join(rng.choices('abcXYZ019_-.:/\\ !\t\r\nαé', k=rng.randrange(180)))
                        for _ in range(10000))
        for text in itertools.chain(cases, random_cases):
            self.assertEqual(self.fingerprint(self.owner._identifier_prefix_match(text)),
                             self.fingerprint(self.owner._IDENTIFIER_PREFIX.search(text)), repr(text))

    def test_complete_detector_and_assignment_coordinates_are_equivalent(self):
        rng = random.Random(991)
        prefixes = ['', 'publicKey', 'public_key.', 'AUTH_', 'abc:123', 'a:::b', '0_', 'foo::']
        prefixes += [''.join(rng.choices('aZ019_-.:/\\ !\t', k=rng.randrange(80))) for _ in range(300)]
        for prefix in prefixes:
            for token in ['Token', 'TOKEN', 'accessToken', 'token']:
                line = prefix + token + '= "abC123456789012345" # orchestrarium:public-token'
                actual = self.owner._content_hits(line, 'fixture.txt', lambda _line: ())
                actual_binary = self.owner._binary_content_hits(b'\0' + line.encode() + b'\0', 'fixture.bin', lambda _line: ())
                with mock.patch.object(self.owner, '_identifier_prefix_match', self.owner._IDENTIFIER_PREFIX.search):
                    expected = self.owner._content_hits(line, 'fixture.txt', lambda _line: ())
                    expected_binary = self.owner._binary_content_hits(b'\0' + line.encode() + b'\0', 'fixture.bin', lambda _line: ())
                self.assertEqual(actual, expected, repr(line))
                self.assertEqual(actual_binary, expected_binary, repr(line))

    def test_million_character_line_finishes_without_losing_finding(self):
        # A separate bounded child also makes the original quadratic failure
        # reproducible without wedging the test runner.
        code = '''import importlib.util,sys
s=importlib.util.spec_from_file_location("_long_identifier",sys.argv[1])
m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
line="x"*1000000+" "+"To"+"ken="+repr("abC"+"123456789012345")
assert m._content_hits(line,"fixture.txt",lambda _:())
if hasattr(m,"_identifier_prefix_match"):
 for suffix in (" ", '\\"', "::::", "::a", "\\n"):
  raw="x"*1000000+suffix
  result=m._identifier_prefix_match(raw)
  assert bool(result)==(suffix in ("::a","\\n"))
print("bounded-detector-pass")
'''
        try:
            result = subprocess.run([sys.executable, '-I', '-c', code, str(SOURCE)],
                                    capture_output=True, text=True, timeout=8)
        except subprocess.TimeoutExpired:
            self.fail('detector failed to finish its bounded long-line check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'bounded-detector-pass')
