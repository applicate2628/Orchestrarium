"""Windows native Codex must not be shadowed by a generic npm command shim."""
from pathlib import Path
from types import SimpleNamespace
import os
import pytest
from _module_loading_support import load_module
ROOT = Path(__file__).resolve().parents[1]
HEALTH = load_module(ROOT / 'scripts/check-hook-health.py', 'codex_command_resolution_tests')


@pytest.mark.parametrize('platform,explicit,has_native,expected', [
    ('nt', None, True, 'native'),
    ('nt', None, False, 'shim'),
    ('nt', 'selected-wrapper', True, 'selected'),
    ('posix', None, True, 'shim'),
])
def test_command_selection_preserves_explicit_choice(tmp_path, monkeypatch, platform, explicit, has_native, expected):
    native, shim, selected, shell = [tmp_path / name for name in ('codex.exe','codex.cmd','custom.py','cmd.exe')]
    for path in (native, shim, selected, shell):
        path.write_bytes(b'not executed')
    calls=[]
    def which(name):
        calls.append(name)
        if name == 'codex.exe': return str(native) if has_native else None
        if name == 'selected-wrapper': return str(selected)
        if name == 'codex': return str(shim)
        raise AssertionError(name)
    monkeypatch.setattr(HEALTH, 'os', SimpleNamespace(name=platform, environ={**os.environ,'COMSPEC':str(shell)}))
    monkeypatch.setattr(HEALTH.shutil, 'which', which)
    command=HEALTH.resolve_codex_command(explicit)
    wanted={'native':native,'shim':shim,'selected':selected}[expected]
    assert command[-1] == str(wanted.resolve())
    if explicit:
        assert calls == ['selected-wrapper']
    if platform == 'nt' and expected == 'shim':
        assert command[:4] == [str(shell.resolve()),'/d','/s','/c']
