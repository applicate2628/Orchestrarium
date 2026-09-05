"""A Windows-style checkout preserves exact role and documentation contracts."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PINNED = (
    'shared/role-routing-policy.v1.json',
    'shared/agents-mode.presets.json',
    'src.claude/CLAUDE.md',
    'references-claude/claude-md-structural-enforcement.md',
    'references-claude/ru/claude-md-structural-enforcement.md',
)


def _git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


@pytest.fixture(scope='module')
def checkout(tmp_path_factory):
    source = tmp_path_factory.mktemp('source-eol')
    target = source.parent / 'checkout-eol'
    manifest = json.loads((ROOT / 'src.codex/agents/orchestrarium-role-manifest.json').read_text())
    paths = (*PINNED, *(f'src.codex/agents/{record["relativePath"]}'
                       for record in manifest['roles'].values()))
    expected = {path: (ROOT / path).read_bytes() for path in paths}
    expected['tests/fixtures/canonical-skill-priors/example/revision/historical.py'] = b'prior\r\nbytes\r\n'
    for path, payload in expected.items():
        output = source / path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(payload)
    (source / '.gitattributes').write_bytes((ROOT / '.gitattributes').read_bytes())
    _git(source, 'init', '-q')
    _git(source, 'config', 'core.autocrlf', 'false')
    _git(source, 'add', '--all')
    _git(source, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
         'commit', '-qm', 'fixture')
    subprocess.run(['git', 'clone', '--quiet', '--no-checkout', str(source), str(target)], check=True)
    _git(target, '-c', 'core.autocrlf=true', 'checkout', '--force', 'HEAD')
    return target, expected, manifest


@pytest.mark.parametrize('path', PINNED)
def test_fixed_byte_contract_survives_windows_style_checkout(checkout, path):
    target, expected, _ = checkout
    assert hashlib.sha256((target / path).read_bytes()).digest() == hashlib.sha256(expected[path]).digest()


def test_native_role_manifest_hashes_survive_windows_style_checkout(checkout):
    target, _, manifest = checkout
    assert hashlib.sha256((target / PINNED[0]).read_bytes()).hexdigest() == manifest['policySha256']
    for record in manifest['roles'].values():
        path = target / 'src.codex/agents' / record['relativePath']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256']


def test_historical_bytes_and_unrelated_file_attributes_are_not_changed(checkout):
    target, expected, _ = checkout
    path = 'tests/fixtures/canonical-skill-priors/example/revision/historical.py'
    assert hashlib.sha256((target / path).read_bytes()).digest() == hashlib.sha256(expected[path]).digest()
    for unrelated in ('scripts/unrelated.py', 'docs/unrelated.md', 'scripts/unrelated.ps1'):
        result = _git(target, 'check-attr', 'eol', '--', unrelated).stdout.decode()
        assert result.strip().endswith(': unspecified')
