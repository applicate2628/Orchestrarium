"""No-follow rollback for a projection whose owned target was reclaimed."""
from pathlib import Path
import os
import subprocess
import sys
import pytest
from test_hook_runtime_transactions import production_installer as installer

def test_owned_projection_reclaims_after_owned_target_inverse(tmp_path):
    anchor=tmp_path/'home';anchor.mkdir()
    source=tmp_path/'source';source.mkdir();(source/'SKILL.md').write_text('Synthetic skill.\n')
    provider=anchor/'.claude';provider.mkdir()
    with pytest.raises(RuntimeError, match='forced rollback'):
        with installer._InstallTransaction([provider,anchor/'.agents'],enabled=True) as tx:
            owner=installer._CreateOnlyMutablePath(anchor,tx,dry_run=False)
            canonical=owner.create_tree(Path('.agents/skills/example'),source)
            owner.create_projection(Path('.claude/skills/example'),canonical)
            raise RuntimeError('forced rollback')
    assert provider.is_dir() and list(provider.iterdir())==[]
    assert not (anchor/'.agents').exists()


def _windows_token_snapshot(*, thread):
    import ctypes
    from ctypes import wintypes as W
    api = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentThread.restype = W.HANDLE
    kernel.GetCurrentProcess.restype = W.HANDLE
    kernel.CloseHandle.argtypes = (W.HANDLE,)
    api.OpenThreadToken.argtypes = (W.HANDLE, W.DWORD, W.BOOL, ctypes.POINTER(W.HANDLE))
    api.OpenProcessToken.argtypes = (W.HANDLE, W.DWORD, ctypes.POINTER(W.HANDLE))
    api.GetTokenInformation.argtypes = (W.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                        W.DWORD, ctypes.POINTER(W.DWORD))
    token = W.HANDLE()
    opened = (api.OpenThreadToken(kernel.GetCurrentThread(), 8, True, ctypes.byref(token))
              if thread else api.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)))
    if not opened:
        error = ctypes.get_last_error()
        if thread and error == 1008:
            return None
        raise ctypes.WinError(error)
    try:
        parts = []
        for kind in (10, 3):  # TokenStatistics/TokenId, TokenPrivileges.
            length = W.DWORD()
            api.GetTokenInformation(token, kind, None, 0, ctypes.byref(length))
            buffer = ctypes.create_string_buffer(length.value)
            assert api.GetTokenInformation(token, kind, buffer, len(buffer), ctypes.byref(length))
            parts.append(buffer.raw[:8] if kind == 10 else buffer.raw[:length.value])
        return tuple(parts)
    finally:
        assert kernel.CloseHandle(token)


@pytest.mark.skipif(os.name != 'nt', reason='native Windows token scope')
def test_symlink_privilege_restores_nested_thread_and_unchanged_process():
    before_thread = _windows_token_snapshot(thread=True)
    before_process = _windows_token_snapshot(thread=False)
    with pytest.raises(RuntimeError, match='operation failed'):
        with installer._WindowsBoundNode.symlink_privilege():
            outer = _windows_token_snapshot(thread=True)
            assert outer is not None and outer != before_thread
            assert _windows_token_snapshot(thread=False) == before_process
            with installer._WindowsBoundNode.symlink_privilege():
                assert _windows_token_snapshot(thread=True)[0] != outer[0]
                assert _windows_token_snapshot(thread=False) == before_process
            assert _windows_token_snapshot(thread=True) == outer
            raise RuntimeError('operation failed')
    assert _windows_token_snapshot(thread=True) == before_thread
    assert _windows_token_snapshot(thread=False) == before_process


@pytest.mark.skipif(os.name != 'nt', reason='native Windows fail-closed restore')
def test_failed_thread_restore_stops_child_before_caller_continues():
    script = r'''
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'scripts'))
import production_installer as m
with m._WindowsBoundNode.symlink_privilege():
    C, W, kernel, *_ = m._WindowsBoundNode._api()
    api, _ = m._WindowsBoundNode._privilege_bindings
    def refuse_restore(*args):
        C.set_last_error(5)
        return 0
    api.SetThreadToken = refuse_restore
print('UNSAFE_CALLER_CONTINUED', flush=True)
'''
    child = subprocess.run([sys.executable, '-I', '-c', script],
                           cwd=Path(__file__).resolve().parents[1],
                           capture_output=True, text=True, timeout=20)
    assert child.returncode == 70
    assert 'E_WINDOWS_TOKEN_RESTORE_FAILED' in child.stderr
    assert 'UNSAFE_CALLER_CONTINUED' not in child.stdout


def test_unneeded_symlink_privilege_never_loads_windows_api(monkeypatch):
    def forbidden(*args):
        raise AssertionError('unneeded privilege acquisition')
    monkeypatch.setattr(installer._WindowsBoundNode, '_api', forbidden)
    with installer._WindowsBoundNode.symlink_privilege(required=False):
        pass


@pytest.mark.skipif(os.name != 'nt', reason='native Windows missing privilege')
def test_symlink_privilege_cannot_grant_missing_effective_privilege():
    before_thread = _windows_token_snapshot(thread=True)
    before_process = _windows_token_snapshot(thread=False)
    with installer._WindowsBoundNode.symlink_privilege():
        C, W, kernel, *_ = installer._WindowsBoundNode._api()
        api, Privileges = installer._WindowsBoundNode._privilege_bindings
        token = W.HANDLE()
        assert api.OpenThreadToken(kernel.GetCurrentThread(), 0x28, True, C.byref(token))
        try:
            state = Privileges(); state.count = 1
            state.items[0].attributes = 4  # Remove only from this private test token.
            assert api.LookupPrivilegeValueW(None, 'SeCreateSymbolicLinkPrivilege',
                                              C.byref(state.items[0].luid))
            C.set_last_error(0)
            assert api.AdjustTokenPrivileges(token, False, C.byref(state), 0, None, None)
            assert C.get_last_error() == 0
            without_privilege = _windows_token_snapshot(thread=True)
            with pytest.raises(OSError) as raised:
                with installer._WindowsBoundNode.symlink_privilege():
                    pytest.fail('Missing privilege must not be granted')
            assert raised.value.winerror == 1300  # ERROR_NOT_ALL_ASSIGNED.
            assert _windows_token_snapshot(thread=True) == without_privilege
        finally:
            assert kernel.CloseHandle(token)
    assert _windows_token_snapshot(thread=True) == before_thread
    assert _windows_token_snapshot(thread=False) == before_process
