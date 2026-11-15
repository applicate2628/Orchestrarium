"""Guard lifecycle test discovery without executing the full lifecycle suite."""
import importlib.util
import inspect
from pathlib import Path
import unittest
from unittest.mock import patch

_SPEC = importlib.util.spec_from_file_location(
    "lifecycle_discovery_subject", Path(__file__).with_name("test_mutate_work_item.py")
)
SUBJECT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(SUBJECT)


class TestLifecycleDiscovery(unittest.TestCase):
    def test_unittest_adapts_every_module_test(self):
        expected = {
            name for name, value in vars(SUBJECT).items()
            if name.startswith("test_") and inspect.isfunction(value)
            and value.__module__ == SUBJECT.__name__
        }
        actual = set(unittest.defaultTestLoader.getTestCaseNames(SUBJECT._UnittestAdapter))
        self.assertTrue(expected)
        self.assertEqual(actual, expected)

    def test_pytest_does_not_collect_unittest_adapter(self):
        self.assertIs(SUBJECT._UnittestAdapter.__test__, False)

    def test_adapter_selects_original_function_and_propagates_failure(self):
        def test_example():
            pass

        method = SUBJECT._adapt_test(test_example)
        case = unittest.TestCase()
        with patch.object(SUBJECT.pytest, "main", return_value=0) as run:
            method(case)
        self.assertTrue(run.call_args.args[0][0].endswith("::test_example"))
        with patch.object(SUBJECT.pytest, "main", return_value=1):
            with self.assertRaises(AssertionError):
                method(case)
