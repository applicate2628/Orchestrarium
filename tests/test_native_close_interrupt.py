"""Declaration-only Windows descriptor settlement; no native APIs or handles."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest
from test_scalar_restore_close import load_source

def load_exit():
    source = Path(__file__).resolve().parents[1] / "scripts/production_installer.py"
    m = load_source(source)
    tree = ast.parse(source.read_text(encoding="utf-8-sig"))
    owner, = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "_WindowsBoundNode"]
    method, = [n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == "__exit__"]
    code = ast.Module(body=[method], type_ignores=[])
    ast.fix_missing_locations(code)
    exec(compile(code, str(source) + ":exit-only", "exec"), m.__dict__)
    return m, m.__dict__["__exit__"]

@pytest.mark.parametrize("cleanup_type", [OSError, RuntimeError, KeyboardInterrupt, SystemExit])
@pytest.mark.parametrize("primary_kind", ["ordinary", "typed", "stored", "none"])
def test_native_descriptor_close_retains_primary(cleanup_type, primary_kind):
    m, exit_owner = load_exit()
    operation = ValueError("operation")
    primary = operation
    if primary_kind == "typed":
        primary = m._InstallFailure("E_ROLLBACK_RESTORE_FAILED", "original", operation,
            recovery_path=Path("original-recovery"))
    if primary_kind == "none":
        primary = None
    cleanup = cleanup_type("close")
    kernel = SimpleNamespace(CloseHandle=Mock())
    owner = SimpleNamespace(descriptor=123, handle=None, path=Path("bound"),
        settlement_primary=primary if primary_kind == "stored" else None,
        _api=lambda: (None, None, kernel))
    passed_primary = None if primary_kind == "stored" else primary
    with patch.object(m.os, "close", side_effect=cleanup) as close:
        with pytest.raises(BaseException) as caught:
            exit_owner(owner, type(passed_primary), passed_primary, None)
    close.assert_called_once_with(123)
    kernel.CloseHandle.assert_not_called()
    assert owner.descriptor == 123  # uncertain close is not asserted complete or retried
    error = caught.value
    assert isinstance(error, m._InstallFailure)
    assert error.cause is (primary if primary is not None else cleanup)
    assert error.__cause__ is primary
    assert error.recovery_path == Path("bound")
    assert len(error.members) == 1
    assert error.members[0].cause_exception is cleanup

def test_success_settles_descriptor_once():
    m, exit_owner = load_exit()
    owner = SimpleNamespace(descriptor=123, handle=None, settlement_primary=None,
        path=Path("bound"), _api=lambda: (None, None, SimpleNamespace()))
    with patch.object(m.os, "close") as close:
        assert exit_owner(owner, None, None, None) is False
    close.assert_called_once_with(123)
    assert owner.descriptor is None
