"""Windows filename-derived execute bits are not an object identity change."""
import ast
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest


def matcher(platform):
    source = Path(__file__).resolve().parents[1] / 'scripts/production_installer.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == '_InstallTransaction')
    method = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == '_binding_identity_matches')
    method.decorator_list = []
    namespace = {'os': SimpleNamespace(name=platform), 'stat': stat}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace[method.name]


@pytest.mark.parametrize('reverse', [False, True])
def test_windows_regular_file_accepts_only_synthetic_execute_projection(reverse):
    bound = (17, 43, stat.S_IFREG | 0o666, 32)
    lexical = (17, 43, stat.S_IFREG | 0o777, 32)
    assert matcher('nt')(*( (lexical, bound) if reverse else (bound, lexical) ))


@pytest.mark.parametrize('observed', [
    (18, 43, stat.S_IFREG | 0o777, 32),
    (17, 44, stat.S_IFREG | 0o777, 32),
    (17, 43, stat.S_IFREG | 0o555, 33),
    (17, 43, stat.S_IFREG | 0o555, 32),
    (17, 43, stat.S_IFREG | 0o777, 0),
    (17, 43, stat.S_IFREG | 0o777, 32 | stat.FILE_ATTRIBUTE_REPARSE_POINT),
    (17, 43, stat.S_IFDIR | 0o777, 32),
    (17, 43, stat.S_IFLNK | 0o777, 32),
])
def test_windows_projection_keeps_identity_type_attributes_and_write_bits(observed):
    assert not matcher('nt')((17, 43, stat.S_IFREG | 0o666, 32), observed)


def test_posix_execute_bits_remain_significant():
    assert not matcher('posix')((17, 43, stat.S_IFREG | 0o666, 0),
                                (17, 43, stat.S_IFREG | 0o777, 0))


def test_windows_reparse_execute_bits_remain_significant():
    attrs = 32 | stat.FILE_ATTRIBUTE_REPARSE_POINT
    assert not matcher('nt')((17, 43, stat.S_IFREG | 0o666, attrs),
                             (17, 43, stat.S_IFREG | 0o777, attrs))


def test_permission_transition_keeps_directory_mode_and_attributes_exact():
    check = matcher('nt')
    before = (17, 43, stat.S_IFDIR | 0o777, 16)
    assert check(before, before, exact_permissions=True)
    assert not check(before, (17, 43, stat.S_IFDIR | 0o555, 17), exact_permissions=True)
    assert not check(before, (17, 43, stat.S_IFDIR | 0o777, 17), exact_permissions=True)


def test_permission_transition_still_accepts_regular_file_execute_projection():
    assert matcher('nt')((17, 43, stat.S_IFREG | 0o666, 32),
                         (17, 43, stat.S_IFREG | 0o777, 32), exact_permissions=True)


@pytest.mark.parametrize('fault', [None, 'native-id', 'readonly-not-set'])
def test_chmod_producer_preserves_bound_representation_after_verified_readback(fault):
    source = Path(__file__).resolve().parents[1] / 'scripts/production_installer.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == '_InstallTransaction')
    owner.body = [n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name in
                  {'_binding_identity_matches', '_chmod_identity', '_chmod_owned'}]
    current = [(17, 43, stat.S_IFREG | 0o777, 32)]
    class Bound:
        proof = 'foreign' if fault == 'native-id' else 'native'
        def __init__(self, *_args, **_kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_args): pass
        def set_readonly(self, readonly):
            assert readonly
            if fault != 'readonly-not-set':
                current[0] = (17, 43, stat.S_IFREG | 0o555, 33)
    namespace = {'os': SimpleNamespace(name='nt'), 'stat': stat, 'Path': Path,
                 '_NativeNodeProof': object, '_WindowsBoundNode': Bound,
                 '_CreateOnlyMutablePath': SimpleNamespace(_identity=lambda _path: current[0])}
    exec(compile(ast.Module(body=[owner], type_ignores=[]), str(source), 'exec'), namespace)
    call = namespace['_InstallTransaction']._chmod_owned
    before = (17, 43, stat.S_IFREG | 0o666, 32)
    if fault:
        with pytest.raises(ValueError, match='native identity|permission transition'):
            call(Path('sample.exe'), before, 0o444, native_proof='native')
    else:
        assert call(Path('sample.exe'), before, 0o444, native_proof='native') == (
            17, 43, stat.S_IFREG | 0o444, 33)
