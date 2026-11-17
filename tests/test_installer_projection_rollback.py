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
    _require_existing_symlink_privilege()
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
    _require_existing_symlink_privilege()
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
    _require_existing_symlink_privilege()
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


@pytest.mark.skipif(os.name != "nt", reason="native Windows link copy")
@pytest.mark.parametrize("rollback", [False, True])
def test_owned_link_copy_preserves_reparse_bytes_and_transaction_inverse(tmp_path, rollback):
    before_thread = _windows_token_snapshot(thread=True)
    before_process = _windows_token_snapshot(thread=False)
    anchor = tmp_path / "home"
    anchor.mkdir()
    provider = anchor / ".claude"
    provider.mkdir()
    referent = tmp_path / "referent"
    referent.mkdir()
    payload = referent / "SKILL.md"
    payload.write_text("Independent user data.\n", encoding="utf-8")
    before = payload.read_bytes()
    original = provider / "source-link"
    copied = provider / "copied-link"

    def operation():
        with installer._InstallTransaction([provider], enabled=True) as tx:
            owner = installer._CreateOnlyMutablePath(anchor, tx, dry_run=False)
            owner.create_projection(Path(".claude/source-link"), referent)
            expected = tx._capture_node(original)
            assert int.from_bytes(expected.reparse_data[:4], 'little') == 0xA0000003
            received = {}
            def record(path, node):
                received[path] = node
                tx._advance(path, {path: node})
            tx._copy_owned_link(original, copied, expected, record)
            node = received[copied]
            assert node.reparse_data == expected.reparse_data
            assert node.native_proof != expected.native_proof
            assert tx._image_matches(original, {original: expected})
            assert installer._projection_resolves_to(copied, referent)
            owner._record_created(copied, "projection", None,
                                  projection_target=referent.resolve(strict=True),
                                  acquired_node=node)
            if rollback:
                raise RuntimeError("forced copied-link rollback")
            tx.commit()

    if rollback:
        with pytest.raises(RuntimeError, match="forced copied-link rollback"):
            operation()
        assert not os.path.lexists(original)
        assert not os.path.lexists(copied)
        assert list(provider.iterdir()) == []
    else:
        operation()
        assert installer._projection_resolves_to(original, referent)
        assert installer._projection_resolves_to(copied, referent)
    assert payload.read_bytes() == before
    assert _windows_token_snapshot(thread=True) == before_thread
    assert _windows_token_snapshot(thread=False) == before_process

def _require_existing_symlink_privilege():
    if os.name != "nt":
        return
    before_thread = _windows_token_snapshot(thread=True)
    before_process = _windows_token_snapshot(thread=False)
    try:
        with installer._WindowsBoundNode.symlink_privilege():
            pass
    except OSError as error:
        assert _windows_token_snapshot(thread=True) == before_thread
        assert _windows_token_snapshot(thread=False) == before_process
        if error.winerror == 1300:
            pytest.skip("Effective token has no symlink privilege; positive native path not accepted")
        raise
    assert _windows_token_snapshot(thread=True) == before_thread
    assert _windows_token_snapshot(thread=False) == before_process


@pytest.mark.skipif(os.name != "nt", reason="native Windows missing privilege")
def test_already_missing_privilege_refuses_without_token_changes():
    before_thread = _windows_token_snapshot(thread=True)
    before_process = _windows_token_snapshot(thread=False)
    try:
        with installer._WindowsBoundNode.symlink_privilege():
            pass
    except OSError as error:
        assert error.winerror == 1300
        assert _windows_token_snapshot(thread=True) == before_thread
        assert _windows_token_snapshot(thread=False) == before_process
    else:
        assert _windows_token_snapshot(thread=True) == before_thread
        assert _windows_token_snapshot(thread=False) == before_process
        pytest.skip("This token contains the privilege; negative removed-token case is separate")



@pytest.mark.parametrize("native_target, expected", [
    ("Q:" + chr(92) + "project", True),
    ("q:/project", True),
    (chr(92) * 2 + "?" + chr(92) + "R:" + chr(92) + "project", True),
    (chr(92) * 2 + "server" + chr(92) + "share", False),
    (chr(92) * 2 + "?" + chr(92) + "UNC" + chr(92) + "server" + chr(92) + "share", False),
    (chr(92) * 2 + "?" + chr(92) + "Volume{synthetic}" + chr(92), False),
    ("Q:relative", False),
    ("relative/project", False),
    ("/relative-to-drive", False),
    ("", False),
])
def test_projection_representation_uses_resolved_local_volume_only(native_target, expected):
    assert installer._windows_projection_uses_junction(native_target) is expected


@pytest.mark.parametrize("tag, expected", [
    (0xA0000003, True), (0xA000000C, False), (0x8000001B, False), (None, False),
])
def test_junction_classifier_uses_native_tag_without_python_isjunction(tag, expected, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.delattr(os.path, "isjunction", raising=False)
    path = SimpleNamespace(lstat=lambda: SimpleNamespace(st_reparse_tag=tag))
    assert installer._is_directory_junction(path) is expected


def test_junction_classifier_handles_disappearing_node():
    from types import SimpleNamespace
    def missing():
        raise FileNotFoundError("synthetic disappearance")
    assert installer._is_directory_junction(SimpleNamespace(lstat=missing)) is False


def test_same_target_junction_is_recognized_without_python_isjunction(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.delattr(os.path, "isjunction", raising=False)
    target = object()
    path = SimpleNamespace(is_symlink=lambda: False,
                           lstat=lambda: SimpleNamespace(st_reparse_tag=0xA0000003),
                           resolve=lambda strict: target)
    expected = SimpleNamespace(resolve=lambda strict: target)
    monkeypatch.setattr(os.path, "samefile", lambda first, second: first is second)
    assert installer._projection_resolves_to(path, expected)
    foreign = SimpleNamespace(resolve=lambda strict: object())
    assert not installer._projection_resolves_to(path, foreign)


@pytest.mark.skipif(os.name != "nt", reason="native Windows junction identity")
def test_junction_same_identity_changed_raw_target_is_not_disposed(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    marker = second / "user-data.txt"
    marker.write_text("Must survive refusal.", encoding="utf-8")
    link = tmp_path / "projection"
    tx = installer._InstallTransaction([tmp_path], enabled=True)
    with installer._WindowsBoundNode(first, follow=True) as first_bound:
        first_raw = installer._WindowsBoundNode.target_reparse_data(first_bound)
    with installer._WindowsBoundNode(second, follow=True) as second_bound:
        second_raw = installer._WindowsBoundNode.target_reparse_data(second_bound)
    with installer._WindowsBoundNode.create(link, directory=True) as created:
        created.set_reparse_data(first_raw)
        expected = tx._capture_node(link, bound_node=created)
        created.set_reparse_data(second_raw)
        changed = tx._capture_node(link, bound_node=created)
        assert changed.native_proof == expected.native_proof
        assert changed.reparse_data != expected.reparse_data
    assert not tx._image_matches(link, {link: expected})
    with pytest.raises(ValueError, match="E_ROLLBACK_RESTORE_BLOCKED_BY_IDENTITY"):
        tx._dispose_node(link, expected)
    assert installer._projection_resolves_to(link, second)
    assert marker.read_text(encoding="utf-8") == "Must survive refusal."


@pytest.mark.skipif(os.name != "nt", reason="native Windows target replacement")
def test_projection_inverse_never_disposes_replacement_target(tmp_path):
    anchor = tmp_path / "home"
    anchor.mkdir()
    provider = anchor / ".claude"
    provider.mkdir()
    referent = tmp_path / "referent"
    referent.mkdir()
    retained = tmp_path / "retained-original"
    marker = referent / "user-data.txt"
    with pytest.raises(RuntimeError, match="forced rollback"):
        with installer._InstallTransaction([provider], enabled=True) as tx:
            owner = installer._CreateOnlyMutablePath(anchor, tx, dry_run=False)
            owner.create_projection(Path(".claude/projection"), referent)
            referent.rename(retained)
            referent.mkdir()
            marker.write_text("Replacement user data.", encoding="utf-8")
            raise RuntimeError("forced rollback")
    assert not os.path.lexists(provider / "projection")
    assert marker.read_text(encoding="utf-8") == "Replacement user data."
    assert retained.is_dir()
