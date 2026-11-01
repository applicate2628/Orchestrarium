"""Actual temporary hook registration/removal, with no model execution."""
from pathlib import Path
import json
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('client', ['codex', 'claude'])
def test_hook_enabled_install_and_uninstall_keep_foreign_settings(tmp_path, client):
    project = tmp_path / 'project'
    project.mkdir()
    def run(*args):
        result = subprocess.run([sys.executable, str(ROOT / 'install.py'), '--clients', client,
            '--target', str(project), '--allow-unsafe-target', *args], cwd=ROOT,
            capture_output=True, text=True, encoding='utf-8', timeout=420)
        assert result.returncode == 0, result.stdout + result.stderr
        return result
    run()
    provider = project / ('.' + client)
    config_path = provider / ('hooks.json' if client == 'codex' else 'settings.json')
    config = json.loads(config_path.read_text(encoding='utf-8'))
    assert config.get('hooks')
    config['orche_test_foreign_setting'] = {'preserve': True}
    config_path.write_text(json.dumps(config), encoding='utf-8')
    receipt = json.loads((provider / '.orche-install.v1.json').read_text(encoding='utf-8'))
    registration = config_path.relative_to(project).as_posix()
    assert receipt['configs'][registration]['handlers']
    run('--uninstall', '--apply')
    remaining = json.loads(config_path.read_text(encoding='utf-8'))
    assert remaining['orche_test_foreign_setting'] == {'preserve': True}
    assert not any(group.get('hooks') for groups in remaining.get('hooks', {}).values() for group in groups)
