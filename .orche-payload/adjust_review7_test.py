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
            repo = root / "repo"
            tests = repo / "tests"
            tests.mkdir(parents=True)
            ready = root / "forger-ready"
            child = (
                "import os, pathlib, signal, time\n"
                "os.setsid()\n"
                "def stop(_signal, _frame):\n"
                "    try:\n"
                "        os.ftruncate(1, 0)\n"
                "    except OSError:\n"
                "        pass\n"
                "    os.write(1, b'PASSED tests/test_skip.py::test_real_skip\\n')\n"
                "    os.write(1, b'===== 1 passed in 0.01s =====\\n')\n"
                "    raise SystemExit(0)\n"
                "signal.signal(signal.SIGTERM, stop)\n"
                f"pathlib.Path({str(ready)!r}).write_text('ready')\n"
                "time.sleep(30)\n"
            )
            (tests / "test_skip.py").write_text(
                "import pathlib, subprocess, sys, time\n"
                "import pytest\n"
                "def test_real_skip():\n"
                f"    subprocess.Popen([sys.executable, '-c', {child!r}])\n"
                f"    ready = pathlib.Path({str(ready)!r})\n"
                "    deadline = time.monotonic() + 5\n"
                "    while not ready.exists() and time.monotonic() < deadline:\n"
                "        time.sleep(0.01)\n"
                "    assert ready.exists()\n"
                "    pytest.skip('genuine retained skip')\n",
                encoding="utf-8",
            )
            trusted = root / "trusted"
            for directory in (
                trusted,
                trusted / "logs",
                trusted / "evidence",
                root / "lanes",
            ):
                directory.mkdir(parents=True, exist_ok=True)
            result = VERIFIER.run_parent_generated_pytest_lane(
                repo_root=repo,
                test_paths=("tests/test_skip.py",),
                lane_parent=root / "lanes",
                log_dir=trusted / "logs",
                junit_dir=trusted / "evidence",
                suite_name="candidate",
                timeout_seconds=30,
                tools=TOOLS,
                trusted_root=trusted,
                **revalidation_kwargs(),
            )
            case = next(ET.parse(result.junit_path).getroot().iter("testcase"))
            skipped = case.find("skipped")
            self.assertIsNotNone(skipped)
            assert skipped is not None
            self.assertIn("genuine retained skip", skipped.text or "")
            properties = case.find("properties")
            self.assertIsNotNone(properties)
            assert properties is not None
            values = [
                item.get("value")
                for item in properties.findall("property")
                if item.get("name") == "orche.pytest.outcomes.v1"
            ]
            self.assertEqual(len(values), 1)
            assert values[0] is not None
            outcomes = json.loads(values[0])
            self.assertEqual(outcomes["counts"]["passed"], 0)
            self.assertEqual(outcomes["counts"]["skipped"], 1)

'''
path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
