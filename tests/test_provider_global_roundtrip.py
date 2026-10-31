"""Global mode is confined to an explicit synthetic HOME, never the real user."""
from pathlib import Path
import os
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('client', ['codex', 'claude'])
def test_global_copy_update_uninstall_preserves_personal_data(tmp_path, client):
    home = tmp_path / 'synthetic-home'
    home.mkdir()
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home),
               XDG_CONFIG_HOME=str(home / 'config'),
               XDG_DATA_HOME=str(home / 'data'))
    def run(*args):
        result = subprocess.run([sys.executable, str(ROOT / 'install.py'), '--clients', client,
            '--global', *args], cwd=ROOT, env=env, capture_output=True,
            text=True, encoding='utf-8', timeout=420)
        assert result.returncode == 0, result.stdout + result.stderr
        return result
    run('--no-hypothesis-hook')
    skills = home / ('.agents' if client == 'codex' else '.claude') / 'skills'
    extra = skills / 'backend-engineer/personal.txt'
    extra.write_bytes(b'keep global user data')
    run('--no-hypothesis-hook')
    assert extra.read_bytes() == b'keep global user data'
    before = {p.relative_to(home).as_posix(): p.read_bytes()
              for p in home.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    run('--uninstall')
    assert {p.relative_to(home).as_posix(): p.read_bytes()
            for p in home.rglob('*') if p.is_file() and '__pycache__' not in p.parts} == before
    run('--uninstall', '--apply')
    assert extra.read_bytes() == b'keep global user data'
    assert not (skills / 'backend-engineer/SKILL.md').exists()
    if client == 'codex':
        assert not (home / '.codex/skills').exists()
    else:
        assert not (home / '.agents/skills').exists()
