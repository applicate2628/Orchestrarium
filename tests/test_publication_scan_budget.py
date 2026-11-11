"""The explicit full-history budget is bounded and consistent across owners."""
import ast
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts/universal-hooks/scripts'


class TestPublicationScanBudget(unittest.TestCase):
    def test_both_owners_use_identical_strict_budget_parser(self):
        functions = []
        for name in ('check-publication-safety.py', 'check-git-push-gate.py'):
            tree = ast.parse((SCRIPTS / name).read_text(encoding='utf-8'))
            function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                            and n.name == '_publication_scan_budget_seconds')
            functions.append(ast.dump(function, include_attributes=False))
            unit = ast.Module(body=[function], type_ignores=[])
            import re
            scope = {'os': os, 're': re}
            exec(compile(unit, name, 'exec'), scope)
            parse = scope['_publication_scan_budget_seconds']
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(parse(), 240.0)
            for raw, expected in [('240', 240), ('900', 900), ('3600', 3600)]:
                with self.subTest(owner=name, valid=raw), mock.patch.dict(os.environ, {'ORCHE_PUBLICATION_SCAN_SECONDS': raw}):
                    self.assertEqual(parse(), expected)
            for raw in ('', '0', '239', '3601', '999999999', '-1', '+900', '0900', '900.0', ' 900', '900 ', 'NaN', 'inf', '９００'):
                with self.subTest(owner=name, invalid=raw), mock.patch.dict(os.environ, {'ORCHE_PUBLICATION_SCAN_SECONDS': raw}):
                    with self.assertRaises(ValueError): parse()
        self.assertEqual(*functions)

    def test_real_imports_agree_on_scan_and_supervisor_budget(self):
        for raw, scan in [(None, 240), ('900', 900), ('3600', 3600)]:
            for name, variable, expected in [('check-publication-safety.py', '_SCAN_DEADLINE_SECONDS', scan),
                                             ('check-git-push-gate.py', 'SCAN_TIMEOUT_SECONDS', scan + 60)]:
                env = os.environ.copy()
                env.pop('ORCHE_PUBLICATION_SCAN_SECONDS', None)
                if raw is not None: env['ORCHE_PUBLICATION_SCAN_SECONDS'] = raw
                code = "import runpy,sys;sys.path.insert(0,sys.argv[1]);m=runpy.run_path(sys.argv[2],run_name='budget_probe');print(m[sys.argv[3]])"
                result = subprocess.run([sys.executable, '-c', code, str(SCRIPTS), str(SCRIPTS / name), variable],
                                        env=env, capture_output=True, text=True, timeout=20)
                with self.subTest(owner=name, budget=raw):
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(float(result.stdout.strip()), expected)
