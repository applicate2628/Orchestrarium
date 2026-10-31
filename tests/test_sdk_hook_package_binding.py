"""Explicit nonauthorizing hook package selection; no model or native process."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from test_sdk_runtime import fixture as runtime_fixture
from test_sdk_dispatch import binding
from sdk_execution import runtime, dispatch
import provider_prompt


def test_package_selection_is_part_of_immutable_request(tmp_path):
    request, selection = runtime_fixture(tmp_path)
    selected = replace(selection, installed_hook_root=str(tmp_path / 'installed lead'))
    assert runtime.CodexRuntimeSelection.from_dict(selected.to_dict()) == selected
    assert runtime.request_sha256(request, selected) != runtime.request_sha256(request, selection)


@pytest.mark.parametrize('root', ['', '.', 'relative/root', True, 0, '/bad\nroot', '/bad\x00root', '/bad\x7froot'])
def test_selection_rejects_nonabsolute_or_control_paths(tmp_path, root):
    _, selection = runtime_fixture(tmp_path)
    with pytest.raises(runtime.RuntimeBindingError): replace(selection, installed_hook_root=root)


def test_version_one_stays_closed_version_two_requires_package(tmp_path):
    path = tmp_path / 'binding.json'
    root = str(tmp_path / 'installed lead')
    for value in [dict(binding(), installedHookRoot=root), dict(binding(), schemaVersion=2),
                  dict(binding(), schemaVersion=3, installedHookRoot=root),
                  dict(binding(), schemaVersion=2, installedHookRoot='relative')]:
        path.write_text(json.dumps(value))
        with pytest.raises(dispatch.DispatchError): dispatch.read_binding(path)
    for value in [binding(), dict(binding(), schemaVersion=2, installedHookRoot=root)]:
        path.write_text(json.dumps(value))
        assert dispatch.read_binding(path) == value


def test_trust_owner_receives_exact_explicit_package_without_inference(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(provider_prompt, 'codex_hook_health_helper', lambda _: tmp_path / 'check-hook-health.py')
    monkeypatch.setattr(provider_prompt, 'run_support_command', lambda runner, args, **kwargs:
                        (calls.append(args) or SimpleNamespace(outcome='success', target_exit_code=0), b'', b''))
    for root in [None, tmp_path / 'selected package']:
        assert provider_prompt.require_codex_hook_trust(None, ['git-fixture'], tmp_path / 'custom-home', tmp_path,
                                                       installed_root=root) == 0
    assert '--installed-root' not in calls[0]
    assert calls[1][calls[1].index('--installed-root') + 1] == str(tmp_path / 'selected package')
