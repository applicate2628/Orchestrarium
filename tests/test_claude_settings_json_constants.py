"""Non-JSON numeric constants must not reach Claude settings rewriting."""
from pathlib import Path
import pytest
from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]
OWNER = load_module(ROOT / 'scripts/production_installer.py', 'claude_constant_settings')

@pytest.mark.parametrize('raw', [b'{"x":NaN}', b'{"nested":[Infinity]}',
                                  b'{"nested":{"x":-Infinity}}'])
def test_constants_refused_before_writer(tmp_path, monkeypatch, raw):
    path = tmp_path / 'settings.json'
    path.write_bytes(raw)
    def forbidden(*args):
        pytest.fail('non-JSON setting reached writer loading')
    monkeypatch.setattr(OWNER, '_load_module_from_path', forbidden)
    with pytest.raises(ValueError, match='not valid JSON'):
        OWNER._merge_claude_main_agent_settings(ROOT, path, 'force', False)
    assert path.read_bytes() == raw

def test_dry_run_rejects_constants(tmp_path):
    path = tmp_path / 'settings.json'
    raw = b'{"x":NaN}'
    path.write_bytes(raw)
    with pytest.raises(ValueError, match='not valid JSON'):
        OWNER._merge_claude_main_agent_settings(ROOT, path, 'force', True)
    assert path.read_bytes() == raw

def test_constant_names_in_strings_and_finite_numbers_remain_valid(tmp_path):
    path = tmp_path / 'settings.json'
    path.write_text('{"NaN":"Infinity", "nested":["-Infinity", 2.5, 0, -4]}')
    assert OWNER._load_claude_settings(path) == {'NaN':'Infinity', 'nested':['-Infinity',2.5,0,-4]}
