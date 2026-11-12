"""The shared settings writer never publishes non-JSON numeric values."""
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


HOOK = load('hook_config_numbers', 'install-hypothesis-hook.py')
INSTALLER = load('claude_consumer_numbers', 'production_installer.py')


@pytest.mark.parametrize('value', [float('inf'), float('-inf'), float('nan')])
def test_shared_writer_refuses_nonfinite_values_without_replacing_settings(tmp_path, value):
    target = tmp_path / 'settings.json'
    before = b'{"theme":"user-owned"}\n'
    target.write_bytes(before)
    with pytest.raises(ValueError):
        HOOK.write_atomic(target, {'nested': [{'value': value}]})
    assert target.read_bytes() == before
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize('number', ['1e400', '-1e400'])
def test_actual_claude_merge_does_not_convert_valid_exponent_to_infinity(tmp_path, number):
    target = tmp_path / 'settings.json'
    before = ('{"userData":{"limit":' + number + '}}\n').encode()
    target.write_bytes(before)
    with pytest.raises(ValueError):
        INSTALLER._merge_claude_main_agent_settings(ROOT, target, 'force', False)
    assert target.read_bytes() == before
    assert list(tmp_path.iterdir()) == [target]


def test_actual_claude_merge_preserves_finite_values_strings_and_user_hooks(tmp_path):
    target = tmp_path / 'settings.json'
    settings = {'userData': {'limit': 1e308, 'small': -1e-300, 'label': 'Infinity'},
                'hooks': {'UserPromptSubmit': [{'hooks': [{'command': 'user-hook'}]}]}}
    target.write_text(json.dumps(settings), encoding='utf-8')
    assert INSTALLER._merge_claude_main_agent_settings(ROOT, target, 'force', False) == 'lead-default-written'
    assert json.loads(target.read_text(encoding='utf-8')) == {**settings, 'agent': 'lead'}
    installed = target.read_bytes()
    assert INSTALLER._merge_claude_main_agent_settings(ROOT, target, 'force', False) == 'lead-already-selected'
    assert target.read_bytes() == installed


def test_nonmutating_claude_mode_preserves_large_exponent_bytes(tmp_path):
    target = tmp_path / 'settings.json'
    before = b'{"userData":{"limit":1e400}}\n'
    target.write_bytes(before)
    assert INSTALLER._merge_claude_main_agent_settings(ROOT, target, 'auto', False) == 'mode-preserved'
    assert target.read_bytes() == before


def test_shared_encoder_preserves_existing_valid_wire_format():
    data = {'custom': '保持', 'numbers': [0, -0.0, 1e308, -1e-300, 10**40],
            'nested': {'enabled': True, 'unset': None}, 'hooks': {}}
    expected = (json.dumps(data, indent=2, ensure_ascii=False) + '\n').replace('\n', os.linesep).encode('utf-8')
    assert HOOK.encode_hook_config(data) == expected
