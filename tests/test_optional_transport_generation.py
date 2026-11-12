"""Real canonical owner update preserves an unselected whole peer generation.

Uses the existing Windows transaction fixture; this test creates no new
reconciliation authority and deliberately leaves required-peer upgrades blocked.
"""
import hashlib
import json
from pathlib import Path
import pytest

from test_modified_lead_selection import ROOT, state, _plan, _apply, _bytes_tree


@pytest.mark.parametrize('extra_count', [1, 21, 1000])
def test_codex_update_preserves_complete_receipted_peer_generation(state, extra_count):
    peer = state.home / '.claude' / 'agents'
    scripts = peer / 'scripts'
    shared = peer / 'shared'
    scripts.mkdir(parents=True)
    shared.mkdir()
    manifest = json.loads((ROOT / 'shared/provider-prompt-projections.v1.json').read_bytes())
    receipt_files = {}
    for index, (name, entry) in enumerate(manifest['files'].items()):
        # Different complete generation, not a permission to replace overlaps.
        content = f'# Prior generation member {index}\n'.encode()
        path = scripts / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        entry['sha256'] = hashlib.sha256(content).hexdigest()
        receipt_files['.claude/agents/scripts/' + name] = entry['sha256']
    for index in range(extra_count):
        name = f'extension_modules/feature_{index}.py'
        content = f'# Retained member {index}\n'.encode()
        path = scripts / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        manifest['files'][name] = {'source': 'scripts/' + name,
                                   'destination': 'scripts/' + name, 'sha256': digest}
        receipt_files['.claude/agents/scripts/' + name] = digest
    manifest_path = shared / 'provider-prompt-projections.v1.json'
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    receipt_files['.claude/agents/shared/provider-prompt-projections.v1.json'] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    receipt = state.home / '.claude/.orche-install.v1.json'
    receipt.write_text(json.dumps({'schema': 'orche.provider-install.v1', 'provider': 'claude',
                                  'scope': 'global', 'layout': 'provider-owned-copies-v1',
                                  'files': receipt_files}), encoding='utf-8')
    (peer / 'operator-note.txt').write_bytes(b'Not owned by the transport manifest.\n')
    before = _bytes_tree(state.home / '.claude')
    identities = {path: (path.stat().st_dev, path.stat().st_ino)
                  for path in (state.home / '.claude').rglob('*') if path.is_file()}
    source_skill = state.source / 'lead/SKILL.md'
    source_skill.write_bytes(source_skill.read_bytes() + b'\n<!-- synthetic canonical update -->\n')
    old_canonical = (state.lead / 'SKILL.md').read_bytes()
    scanner = state.lead / 'scripts/check-publication-safety.py'
    scanner.write_bytes(scanner.read_bytes() + b'\n# Synthetic prior scanner generation.\n')
    old_scanner = scanner.read_bytes()
    state.receipt.write_bytes(state.installer._lead_receipt_bytes(
        state.installer._tree_sha256(state.lead, ignore_runtime_cache=True)))
    with _plan(state, selection=(), claude_transport_root=scripts, claude_transport_optional=True) as plan:
        assert plan.transport_stage is None
        _apply(state, plan)
    assert (state.lead / 'SKILL.md').read_bytes() != old_canonical
    assert scanner.read_bytes() != old_scanner
    assert json.loads(state.receipt.read_bytes())['treeSha256'] == state.installer._tree_sha256(state.lead, ignore_runtime_cache=True)
    assert _bytes_tree(state.home / '.claude') == before
    assert all((path.stat().st_dev, path.stat().st_ino) == identity
               for path, identity in identities.items())


@pytest.mark.parametrize('peer_present', [False, True])
def test_optional_peer_reporting_is_truthful_and_clears_apply_ownership(peer_present, capsys):
    """Execute the exact existing no-stage branch, not a rewritten installer."""
    import ast
    from types import SimpleNamespace
    tree = ast.parse((ROOT / 'scripts/production_installer.py').read_text())
    branches = [node for node in ast.walk(tree)
                if isinstance(node, ast.If)
                and ast.unparse(node.test) == 'canonical_plan.transport_stage is None']
    assert len(branches) == 1
    namespace = {'canonical_plan': SimpleNamespace(transport_stage=None),
                 'owned_peer_transport_root': Path('peer') if peer_present else None,
                 'owned_peer_transport_authority': object() if peer_present else None}
    exec(compile(ast.Module(body=[branches[0]], type_ignores=[]), '<optional-peer-branch>', 'exec'), namespace)
    message = capsys.readouterr().out
    assert ('preserved, not updated' in message) is peer_present
    assert namespace['owned_peer_transport_root'] is None
    assert namespace['owned_peer_transport_authority'] is None
