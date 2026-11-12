"""Snapshot currency failures identify the rejected side without relaxing checks."""
import ast
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import production_installer as installer


def current_check(failure):
    source_file = Path(__file__).resolve().parents[1] / 'scripts/production_installer.py'
    tree = ast.parse(source_file.read_text(encoding='utf-8'))
    owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == '_InstallTransaction')
    construct = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == '_construct_exclusive_tree')
    current = next(n for n in construct.body if isinstance(n, ast.FunctionDef) and n.name == 'current')
    calls = []
    def identity(path):
        calls.append(path + '-root')
        return 2 if failure == path + '-root' else 1
    def image(path, expected):
        calls.append(path + '-image')
        assert expected == {path: 'captured-image'} or path == 'target'
        return failure != path + '-image'
    namespace = {'_InstallFailure': installer._InstallFailure,
                 'effect': None, 'source': 'source', 'target': 'target',
                 'actual': {'target': SimpleNamespace(python_identity=1)},
                 'before': {'source': SimpleNamespace(python_identity=1)},
                 'source_witness': {'source': 'captured-image'},
                 '_CreateOnlyMutablePath': SimpleNamespace(_identity=identity),
                 'self': SimpleNamespace(_binding_identity_matches=lambda a, b: a == b,
                                         _image_matches=image)}
    exec(compile(ast.Module(body=[current], type_ignores=[]), str(source_file), 'exec'), namespace)
    return namespace['current'], calls


@pytest.mark.parametrize('failure', ['target-root', 'source-root', 'target-image', 'source-image'])
def test_currency_failure_identifies_exact_side_and_keeps_short_circuit_order(failure):
    check, calls = current_check(failure)
    with pytest.raises(installer._InstallFailure) as caught:
        check(complete=True)
    rendered = installer._installer_failure_text(caught.value)
    assert 'E_ROLLBACK_RESTORE_BLOCKED_BY_IDENTITY' in rendered
    assert 'context=construction-' + failure in rendered
    assert 'cause=identity-check-failed' in rendered
    order = ['target-root', 'source-root', 'target-image', 'source-image']
    assert calls == order[:order.index(failure) + 1]


def test_partial_check_does_not_read_images():
    check, calls = current_check('source-image')
    check()
    assert calls == ['target-root', 'source-root']


def test_complete_check_still_checks_both_images():
    check, calls = current_check(None)
    check(complete=True)
    assert calls == ['target-root', 'source-root', 'target-image', 'source-image']


def test_diagnostic_does_not_render_paths_or_exception_payload():
    secret = r'C:\private\token-secret'
    error = installer._InstallFailure('E_ROLLBACK_RESTORE_BLOCKED_BY_IDENTITY',
                                      'construction-source-image', ValueError(secret))
    rendered = installer._installer_failure_text(error)
    assert secret not in rendered
    assert 'token-secret' not in rendered
    assert 'context=construction-source-image' in rendered
