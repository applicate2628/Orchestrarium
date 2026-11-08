"""Pure structural diagnostics, with no review-loop owner import or I/O mocks."""
from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path
import re
import unittest
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/review_loop_state.py'
PURE_FUNCTIONS = {
    '_nonempty', '_fields', '_analyze_lane_retry_chain', '_effective_lane',
    '_scout_reconciled', '_scout_metadata_errors', '_scout_amendment_history',
    'effective_scout_reconciliation', 'verdict_result_errors_v2',
    '_unstarted_round_errors', '_unstarted_close_errors', 'validate_v2', 'validate_record',
}


class ReviewLoopEnumDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(SOURCE.read_bytes())
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                     and n.name in PURE_FUNCTIONS]
        assert {n.name for n in functions} == PURE_FUNCTIONS
        constants = [n for n in tree.body if isinstance(n, ast.Assign)
                     and all(isinstance(t, ast.Name) and t.id.isupper() for t in n.targets)]
        future = ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)
        scope = {'re': re, 'json': json, 'hashlib': hashlib}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[future, *constants, *functions], type_ignores=[])),
                     'pure-review-loop-validation', 'exec'), scope)
        cls.scope = scope
        cls.validate = staticmethod(scope['validate_v2'])
        cls.record = staticmethod(scope['validate_record'])

    def fixture(self, phase='admitted', status='running'):
        revision = 'sha256:' + 'a'*64
        lanes = {lane: {'attempt_id': lane+'-1', 'artifact_revision': revision,
                        'state': 'complete' if phase == 'complete' else 'admitted'}
                 for lane in ('surgical', 'deep', 'scout')}
        if phase == 'complete':
            for lane in ('surgical', 'deep'):
                lanes[lane].update(verdict='PASS', blockers=[], rationale='Checked.',
                                   root_proven='Evidence.', scope_unchanged='Unchanged.',
                                   verification_adequate='Qualified.')
            lanes['scout'].update(findings=[], reconciliation=[])
        return {'schema_version': 2, 'loop_id': 'synthetic-loop', 'objective': 'Check.',
                'scope': 'Synthetic', 'runtime_root': 'synthetic-runtime', 'status': status,
                'operations': [], 'rounds': [{'round': 1, 'phase': phase, 'diff': 'Initial.',
                'artifact': {'kind': 'snapshot', 'revision': revision,
                             'snapshot': 'synthetic/artifact'},
                **lanes, 'lane_failures': [], 'evidence': []}]}

    def check_invalid(self, field, value, lane=None):
        data = self.fixture()
        if field == 'status':
            data[field] = value
            expected = 'status: invalid value'
        elif field == 'phase':
            data['rounds'][0][field] = value
            expected = 'rounds[0].phase: invalid value'
        else:
            data['rounds'][0][lane][field] = value
            expected = f'rounds[0].{lane}.state: invalid value'
        before = copy.deepcopy(data)
        errors = self.validate(data)
        self.assertIn(expected, errors)
        self.assertEqual(data, before)
        self.assertTrue(all(isinstance(error, str) for error in errors))
        return errors

    def test_list_and_object_status_return_existing_diagnostic(self):
        for value in ([], {}, ['running'], {'status': 'running'}):
            with self.subTest(value=value):
                self.check_invalid('status', value)

    def test_list_and_object_round_phase_return_existing_diagnostic(self):
        for value in ([], {}, ['admitted'], {'phase': 'admitted'}):
            with self.subTest(value=value):
                self.check_invalid('phase', value)

    def test_list_and_object_direct_lane_state_return_existing_diagnostic(self):
        for lane in ('surgical', 'deep', 'scout'):
            for value in ([], {}, ['admitted'], {'state': 'admitted'}):
                with self.subTest(lane=lane, value=value):
                    self.check_invalid('state', value, lane)

    def test_scalar_invalid_values_keep_their_diagnostics(self):
        for value in (None, True, False, 0, 1.5, '', 'unknown'):
            for field, lane in (('status',None), ('phase',None), ('state','deep')):
                with self.subTest(field=field,value=value):
                    self.check_invalid(field,value,lane)

    def test_multiple_invalid_fields_accumulate_without_erasing_other_errors(self):
        data=self.fixture()
        data['status']=[]; data['objective']=''; data['rounds'][0]['phase']={}
        data['rounds'][0]['deep']['state']=[]
        errors=self.validate(data)
        for expected in ('status: invalid value','objective: expected non-empty string',
                         'rounds[0].phase: invalid value','rounds[0].deep.state: invalid value'):
            self.assertIn(expected,errors)

    def test_valid_structural_records_are_unchanged_and_not_mutated(self):
        for phase in ('admitted','collecting','complete'):
            for status in ('running','converged','drift','deadlock'):
                data=self.fixture(phase,status); before=copy.deepcopy(data)
                with self.subTest(phase=phase,status=status):
                    self.assertEqual(self.validate(data),[])
                    self.assertEqual(data,before)
        # These are only structural fixtures; empty operation history is not
        # current source custody, execution provenance or project acceptance.

    def test_v2_dispatch_returns_diagnostics_without_coercing_the_record(self):
        for value in ([], {}):
            data=self.fixture();data['status']=value;before=copy.deepcopy(data)
            errors,is_v2=self.record(data,require_v2=True)
            self.assertTrue(is_v2)
            self.assertIn('status: invalid value',errors)
            self.assertEqual(data,before)

    def test_malformed_receipt_commands_are_diagnostics_not_type_errors(self):
        for command in ([], {}, ['begin'], {'command': 'begin'}, None, True, 0):
            data = self.fixture()
            data['operations'] = [{'id': 'invalid-command', 'fingerprint': 'synthetic',
                                   'receipt': {'command': command, 'round': 1}}]
            before = copy.deepcopy(data)
            with self.subTest(command=command):
                errors = self.validate(data)
                self.assertIn('operations[0].receipt.command: expected string', errors)
                self.assertEqual(data, before)

    def test_historical_receipt_command_spellings_remain_structurally_compatible(self):
        for receipt in ({'round': 1}, {'round': 1, 'command': ''},
                        {'round': 1, 'command': '   '},
                        {'round': 1, 'command': 'unknown-future-command'}):
            data = self.fixture()
            data['operations'] = [{'id': 'compatible-command', 'fingerprint': 'synthetic',
                                   'receipt': receipt}]
            before = copy.deepcopy(data)
            with self.subTest(receipt=receipt):
                self.assertEqual(self.validate(data), [])
                self.assertEqual(data, before)
        # Structural compatibility is not authority for any mutation/receipt.

    def test_unstarted_close_rejects_malformed_receipt_command_without_crashing(self):
        for command in ([], {}):
            data = self.fixture()
            data['operations'] = [{'id': 'invalid-command', 'fingerprint': 'synthetic',
                                   'receipt': {'command': command, 'round': 1}}]
            errors = self.scope['_unstarted_round_errors'](data, data['rounds'][0], data['operations'])
            self.assertIn('unstarted close has recorded round execution', errors)

    def test_cli_malformed_commands_fail_without_traceback_or_state_effect(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.git').mkdir()  # Only the owner's root marker is needed.
            state = root / '.scratch' / 'reviews' / 'synthetic' / 'state.json'
            state.parent.mkdir(parents=True)
            for command in ([], {}, None, True, 0):
                data = self.fixture()
                data['operations'] = [{'id': 'invalid-command', 'fingerprint': 'synthetic',
                                       'receipt': {'command': command, 'round': 1}}]
                before = json.dumps(data).encode()
                state.write_bytes(before)
                with self.subTest(command=command):
                    result = subprocess.run([sys.executable, '-B', str(SOURCE), 'validate',
                        '--state', str(state), '--require-v2'], cwd=root,
                        capture_output=True, text=True, timeout=15, check=False)
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertIn('operations[0].receipt.command: expected string', result.stderr)
                    self.assertNotIn('Traceback', result.stderr)
                    self.assertEqual(state.read_bytes(), before)
                    self.assertEqual(sorted(p.name for p in state.parent.iterdir()), ['state.json'])

    def test_terminal_requirement_remains_independent(self):
        self.assertIn('status: terminal state required',
                      self.validate(self.fixture(),require_terminal=True))
        self.assertEqual(self.validate(self.fixture(status='drift'),require_terminal=True),[])


if __name__ == '__main__':
    unittest.main()
