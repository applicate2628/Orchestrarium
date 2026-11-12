"""Locate the installer-owned failed call without exposing exception text."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import production_installer as installer


@pytest.mark.parametrize('error_type', [ValueError, RuntimeError, OSError])
def test_public_terminal_exposes_only_own_install_callsite(monkeypatch, capsys, error_type):
    secret = r'C:\private\token-secret'
    def fail_parser(_provider):
        raise error_type(secret)
    monkeypatch.setattr(installer, '_parser', fail_parser)
    with pytest.raises(error_type) as caught:
        installer.install('codex')
    trace = caught.value.__traceback__
    line = None
    while trace is not None:
        if trace.tb_frame.f_code is installer.install.__code__:
            line = trace.tb_lineno
        trace = trace.tb_next
    assert line is not None
    assert installer._finish_install_result('codex', None, False, False, caught.value, None) == 1
    output = capsys.readouterr().err
    assert f'site=install-line:{line}' in output
    assert 'token-secret' not in output
    assert str(Path(installer.__file__).parent) not in output


def test_matching_filename_and_function_name_do_not_authorize_a_site():
    namespace = {}
    exec(compile('def install():\n raise ValueError("private-secret")\n',
                 installer.__file__, 'exec'), namespace)
    try:
        namespace['install']()
    except ValueError as error:
        output = installer._installer_failure_text(error)
    assert 'site=' not in output
    assert 'private-secret' not in output


def test_unraised_error_has_no_invented_site():
    assert 'site=' not in installer._installer_failure_text(ValueError('private-secret'))


def test_site_does_not_invoke_exception_string_or_traceback_override(monkeypatch):
    class Hostile(ValueError):
        def __str__(self):
            raise AssertionError('must not render error text')
        @property
        def __traceback__(self):
            raise AssertionError('must use the native exception descriptor')
    def fail_parser(_provider):
        raise Hostile('private-secret')
    monkeypatch.setattr(installer, '_parser', fail_parser)
    try:
        installer.install('codex')
    except Hostile as error:
        output = installer._installer_failure_text(error)
    assert 'site=install-line:' in output
    assert 'private-secret' not in output


def test_site_does_not_traverse_exception_causes(monkeypatch):
    def fail_parser(_provider):
        raise ValueError('private-secret')
    monkeypatch.setattr(installer, '_parser', fail_parser)
    try:
        installer.install('codex')
    except ValueError as error:
        wrapper = ValueError('unrelated')
        wrapper.__cause__ = error
    assert 'site=' not in installer._installer_failure_text(wrapper)
