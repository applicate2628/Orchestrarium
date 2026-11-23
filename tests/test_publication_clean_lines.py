"""Negative lexical reuse must never reuse review authority or coordinates."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("_clean_lines_scanner", ROOT / "scripts/universal-hooks/scripts/check-publication-safety.py")
scanner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = scanner
SPEC.loader.exec_module(scanner)

pytestmark = pytest.mark.usefixtures("isolated_standalone_review_modules")

class CleanLinesTests(unittest.TestCase):
    def setUp(self):
        self.policy = scanner._load_review_policy_module()

    def analyze(self, raw, cache=None, path=b"example.py", kind="history-blob"):
        return scanner.analyze_review_candidates(raw, path, subject_kind=kind, policy_module=self.policy, clean_lines=cache)

    def test_repeated_clean_line_avoids_second_detection(self):
        cache = scanner._CleanLineAnalysis()
        with mock.patch.object(scanner, "_line_observations", wraps=scanner._line_observations) as detect:
            self.analyze(b"ordinary prose\n", cache)
            first = detect.call_count
            self.analyze(b"ordinary prose\n", cache)
            self.assertEqual(first, detect.call_count)
            self.analyze(b"changed ordinary prose\n", cache)
            self.assertGreater(detect.call_count, first)

    def test_added_candidate_and_moved_coordinates_match_fresh_oracle(self):
        cache = scanner._CleanLineAnalysis()
        value = "sk-" + "q7" * 28
        candidate = ('key = "' + value + '"\n').encode()
        for raw in (b"ordinary prose\n", candidate, b"prefix\n" + candidate, b"ordinary prose\n" + candidate):
            actual = self.analyze(raw, cache)
            self.assertEqual(actual, self.analyze(raw))
            if raw != b"ordinary prose\n":
                self.assertTrue(actual["candidates"] or actual["unresolved"])

    def test_context_change_invalidates_reuse(self):
        cache = scanner._CleanLineAnalysis()
        with mock.patch.object(scanner, "_line_observations", wraps=scanner._line_observations) as detect:
            self.analyze(b"ordinary prose\n", cache)
            first = detect.call_count
            self.analyze(b"ordinary prose\n", cache, kind="commit-message")
            self.assertGreater(detect.call_count, first)
        with mock.patch.object(scanner, "_line_observations", wraps=scanner._line_observations) as changed:
            self.analyze(b"ordinary prose\n", cache, kind="commit-message")
            self.assertGreater(changed.call_count, 0)

    def test_path_exemptions_do_not_seed_clean_cache(self):
        cache = scanner._CleanLineAnalysis()
        raw = ('# credential = "' + 'sk-' + 'q7' * 28 + '"\n').encode()
        exempt = b"scripts/universal-hooks/scripts/check-publication-safety.py"
        self.analyze(raw, cache, path=exempt)
        self.assertEqual(self.analyze(raw, cache), self.analyze(raw))
        self.assertTrue(self.analyze(raw)["candidates"])

    def test_retention_is_previous_payload_only(self):
        cache = scanner._CleanLineAnalysis()
        self.analyze(b"first ordinary line\n", cache)
        self.analyze(b"second ordinary line\n", cache)
        self.assertEqual(cache.lines, {"second ordinary line"})

if __name__ == "__main__":
    unittest.main()
