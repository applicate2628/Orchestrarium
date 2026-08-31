#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
path = root / "tests" / "test_orche_verifier_isolation.py"
text = path.read_text(encoding="utf-8")
start_marker = '''    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux process containment")
    def test_detached_child_cannot_rewrite_parent_captured_pytest_outcome(self) -> None:
'''
end_marker = '''    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux process containment")
    def test_parent_generated_pytest_lane_revalidates_after_each_file(self) -> None:
'''
if text.count(start_marker) != 1 or text.count(end_marker) != 1:
    raise SystemExit("review7 test markers are missing or ambiguous")
start = text.index(start_marker)
end = text.index(end_marker, start)
replacement = r'''    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux process containment")
    def test_detached_child_cannot_rewrite_parent_captured_pytest_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            log_path = root / "captured.log"
            code = (
                "import os\n"
                "print('SKIPPED [1] tests/test_skip.py:1: genuine retained skip', flush=True)\n"
                "print('===== 1 skipped in 0.01s =====', flush=True)\n"
                "try:\n"
                "    os.ftruncate(1, 0)\n"
                "except OSError:\n"
                "    pass\n"
                "print('PASSED tests/test_skip.py::test_real_skip', flush=True)\n"
                "print('===== 1 passed in 0.01s =====', flush=True)\n"
            )
            result = VERIFIER.run_isolated(
                [str(TOOLS.python), "-c", code],
                cwd=root,
                env={**os.environ},
                log_path=log_path,
                timeout_seconds=10,
                tools=TOOLS,
            )
            self.assertEqual(result.exit_code, 0)
            with self.assertRaisesRegex(
                VERIFIER.VerificationError,
                "exactly one parseable terminal summary",
            ):
                VERIFIER._pytest_zero_exit_outcome_evidence(result.log_path)

'''
path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
