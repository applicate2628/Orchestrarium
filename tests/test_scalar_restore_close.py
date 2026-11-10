"""Pure scalar rollback descriptor-close regression; no installer import."""
import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def run_regression(m):
    """No filesystem writes or real descriptors; run only after review/notice.

    Required real closure: _InstallTransaction._settle_scalars,
    _InstallTransaction._settlement_failure, _InstallTransaction.__exit__, _InstallFailure,
    _RollbackFailureMember, and their existing diagnostic helpers. Prefer the
    existing safe source harness; do not import the full installer to run it.
    """
    target, backup, recovery = map(Path, ('scalar', 'beforeimage', 'recovery'))
    payload = b'before'
    node = SimpleNamespace(data=hashlib.sha256(payload).hexdigest())
    count = 0
    for case in ('typed-both', 'ordinary-both', 'primary-only', 'close-only', 'success'):
        operation = OSError('inverse write failed')
        cleanup = OSError('descriptor close failed')
        member = m._RollbackFailureMember('snapshot', 77, str(target),
            'E_ROLLBACK_RESTORE_FAILED', 'existing failure', participant='scalar',
            cause_exception=operation)
        primary = (m._InstallFailure('E_ROLLBACK_RESTORE_FAILED', 'original', operation,
                   members=(member,), recovery_path=recovery,
                   unresolved_paths=(recovery,)) if case == 'typed-both' else operation)
        custody = ((7, object()),)
        primary._installer_custody = custody
        retained = OSError('retained operation')
        m._retain_copy_setter_operation_errors(primary, (retained,))
        has_primary = case in ('typed-both', 'ordinary-both', 'primary-only')
        has_cleanup = case in ('typed-both', 'ordinary-both', 'close-only')
        entry = dict(kind='scalar', consumed=False, current_path=target,
                     path=target, origin=node, before_node=node, current_node=node,
                     operation_backup=backup, links=())
        events, seen = [], []
        def write(*args, **kwargs):
            events.append('write')
            if has_primary:
                raise primary
        def close(fd):
            assert fd == 123
            events.append('close')
            if has_cleanup:
                raise cleanup
        def settlement(error, *args, **kwargs):
            seen.append(error)
            return m._InstallTransaction._settlement_failure(error, *args, **kwargs)
        owner = SimpleNamespace(
            _entries=[entry], _backup_states={backup: {}}, _slice_a_created=[],
            _scalar_origin_consumed=lambda entry: False,
            _assert_scalar_binding=lambda entry: events.append('binding'),
            _image_matches=lambda *args: True,
            _scalar_descriptor_node=lambda *args: node,
            _write_owned_file=write, _advance=lambda *args: None,
            _settlement_failure=settlement)
        with patch.object(m.os, 'open', return_value=123) as opened, \
             patch.object(m.os, 'close', side_effect=close) as closed, \
             patch.object(Path, 'read_bytes', return_value=payload):
            paths, failures, errors = m._InstallTransaction._settle_scalars(owner, [])
        opened.assert_called_once()
        closed.assert_called_once_with(123)
        assert events[:3] == ['binding', 'write', 'close'], (case, events)
        assert entry['consumed'] is (case == 'success')
        if case == 'success':
            assert not paths and not failures and not errors and not seen
            assert events == ['binding', 'write', 'close', 'binding']
        elif case == 'primary-only':
            assert seen[-1] is primary
            assert any(f.cause_exception is primary for f in failures)
        else:
            wrapper = seen[-1]
            assert isinstance(wrapper, m._InstallFailure)
            assert wrapper.context == 'scalar-close'
            assert wrapper.cause is (primary if has_primary else cleanup)
            assert wrapper.__cause__ is (primary if has_primary else None)
            assert wrapper.recovery_path == (recovery if case == 'typed-both' else None)
            assert target in wrapper.unresolved_paths
            assert any(f.cause_exception is cleanup and f.participant == 'scalar'
                       and f.phase == 'snapshot' for f in failures)
            assert sum(f.cause_exception is cleanup for f in failures) == 1
            if has_primary:
                assert wrapper._installer_custody is custody
                assert retained in m._copy_setter_operation_errors(wrapper)
                assert any(f is member if case == 'typed-both' else f.cause_exception is primary
                           for f in failures)
            if case == 'typed-both':
                assert recovery in wrapper.unresolved_paths
                assert sum(f is member for f in failures) == 1
                assert len(failures) == 2
        expected_paths = {
            'typed-both': [target, target, recovery, target, target, target],
            'ordinary-both': [target] * 5,
            'primary-only': [target] * 2,
            'close-only': [target] * 4,
            'success': [],
        }[case]
        assert paths == expected_paths, (case, paths)
        expected_errors = ((primary,) if case == 'primary-only' else
                           (seen[-1],) if has_primary else ())
        assert len(errors) == len(expected_errors)
        assert all(actual is expected for actual, expected in zip(errors, expected_errors))
        if has_primary:
            assert retained in m._copy_setter_operation_errors(errors[0])

        # Exercise the real transaction exit aggregator with the scalar result
        # above and inert empty siblings. This is not a native rollback test.
        original = OSError('original install failure')
        original._installer_custody = custody
        aggregate_calls = []
        def scalar_result(blocked, *, entries):
            assert blocked == [] and entries == (entry,)
            aggregate_calls.append('scalar')
            return paths, failures, errors
        def associate(error, unresolved):
            assert error is original and unresolved == expected_paths
            aggregate_calls.append('custody')
        owner.enabled, owner.committed, owner._temporary = True, False, recovery
        owner._settle_effects = lambda: ([], [], ())
        owner._settle_migrated = lambda blocked: ([], [], ())
        owner._settle_scalars = scalar_result
        owner._settle_created = lambda blocked, *, records: ([], [], ())
        owner._settle_container_inverses = lambda blocked, directories: ([], True, ())
        owner._remaining_recovery = lambda: (recovery, [], [], ())
        owner._associate_custody = associate
        try:
            result = m._InstallTransaction.__exit__(owner, type(original), original, None)
        except m._InstallFailure as aggregate:
            assert case != 'success'
            assert aggregate.stable_id == 'E_ROLLBACK_SETTLEMENT_FAILED'
            assert aggregate.context == 'rollback'
            assert aggregate.cause is original and aggregate.__cause__ is original
            expected_members = tuple(reversed(failures)) if case == 'typed-both' else tuple(failures)
            assert len(aggregate.members) == len(expected_members)
            assert all(actual is expected for actual, expected in zip(aggregate.members, expected_members))
            assert aggregate.unresolved_paths == tuple(expected_paths)
            assert aggregate.recovery_path == recovery
            assert aggregate._installer_custody is custody
            expected_aggregate_errors = ((primary, seen[-1]) if case == 'ordinary-both' else expected_errors)
            actual_errors = m._copy_setter_operation_errors(aggregate)
            assert len(actual_errors) == len(expected_aggregate_errors), (case, actual_errors)
            assert all(actual is expected for actual, expected in zip(actual_errors, expected_aggregate_errors))
        else:
            assert case == 'success' and result is False
        assert aggregate_calls == ['scalar', 'custody']
        count += 1
    return count


def load_source(source_path):
    """Execute only the reviewed declaration closure from actual canonical source."""
    import ast
    import dataclasses
    import os
    import re
    import sys
    import types
    raw = Path(source_path).read_bytes()
    source = raw.decode('utf-8-sig').replace('\r\n', '\n')
    parsed = ast.parse(source)
    names = {
        '_CopySetterDiagnostic', '_RollbackFailureMember', '_InstallFailure',
        '_passive_owner_storage', '_store_copy_setter_detail', '_copy_setter_detail',
        '_copy_setter_operation_errors', '_merge_copy_setter_operation_errors',
        '_retain_copy_setter_operation_errors',
    }
    selected = [node for node in parsed.body
                if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names]
    if {node.name for node in selected} != names:
        raise ValueError('missing diagnostic closure declaration')
    owners = [node for node in parsed.body
              if isinstance(node, ast.ClassDef) and node.name == '_InstallTransaction']
    if len(owners) != 1:
        raise ValueError('transaction owner missing or ambiguous')
    owner = owners[0]
    methods = {'_settle_scalars', '_settlement_failure', '__exit__'}
    owner.body = [node for node in owner.body
                  if isinstance(node, ast.FunctionDef) and node.name in methods]
    if {node.name for node in owner.body} != methods or owner.bases or owner.decorator_list:
        raise ValueError('unexpected transaction declaration')
    selected.append(owner)
    tree = ast.Module(body=[ast.ImportFrom(module='__future__',
        names=[ast.alias(name='annotations')], level=0), *selected], type_ignores=[])
    ast.fix_missing_locations(tree)
    module = types.ModuleType('_scalar_restore_close_test')
    module.__dict__.update(dataclass=dataclasses.dataclass, field=dataclasses.field,
                           Path=Path, hashlib=hashlib, os=os, re=re)
    sys.modules[module.__name__] = module
    try:
        exec(compile(tree, str(source_path) + ':declaration-only', 'exec'), module.__dict__)
    except BaseException:
        sys.modules.pop(module.__name__, None)
        raise
    return module



def test_scalar_restore_close():
    source = Path(__file__).resolve().parents[1] / 'scripts' / 'production_installer.py'
    assert run_regression(load_source(source)) == 5


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 3:
        raise SystemExit('Usage: test_scalar_restore_close.py SOURCE EXPECTED_SHA256')
    source = Path(sys.argv[1])
    assert hashlib.sha256(source.read_bytes()).hexdigest() == sys.argv[2]
    passed = run_regression(load_source(source))
    assert hashlib.sha256(source.read_bytes()).hexdigest() == sys.argv[2]
    print(f'GREEN: {passed} canonical mocked scalar inverse close cases')
