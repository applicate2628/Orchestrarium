"""Load real diagnostic declarations only, without installer effects or I/O mocks."""
import ast
import dataclasses
import errno
import hashlib
from pathlib import Path
import re
import sys
import types


def load_diagnostics():
    source = Path(__file__).resolve().parents[1] / 'scripts/production_installer.py'
    tree = ast.parse(source.read_bytes())
    names = {'_InstallFailure', '_RollbackFailureMember', '_CopySetterDiagnostic',
             '_passive_owner_storage', '_store_copy_setter_detail', '_copy_setter_detail',
             '_copy_setter_operation_errors', '_merge_copy_setter_operation_errors',
             '_retain_copy_setter_operation_errors', '_installer_failure_text'}
    nodes = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in names]
    assert {n.name for n in nodes} == names
    nodes += [n for n in tree.body if isinstance(n, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == 'SLICE_A_FAILURE_IDS' for t in n.targets)]
    module = types.ModuleType('_pure_installer_diagnostics')
    module.__dict__.update(dataclass=dataclasses.dataclass, field=dataclasses.field,
                           errno=errno, hashlib=hashlib, Path=Path, re=re)
    sys.modules[module.__name__] = module
    unit = ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module='__future__',
        names=[ast.alias(name='annotations')], level=0), *nodes], type_ignores=[]))
    exec(compile(unit, str(source)+':diagnostics-only', 'exec'), module.__dict__)
    return module

DIAGNOSTICS = load_diagnostics()
