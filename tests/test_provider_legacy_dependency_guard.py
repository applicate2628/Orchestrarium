"""Converting links alone does not complete a legacy shared-runtime upgrade."""
from pathlib import Path
import hashlib,json
import pytest
from _module_loading_support import load_module
ROOT=Path(__file__).resolve().parents[1]
INSTALL=load_module(ROOT/'scripts/production_installer.py','legacy_dependency_guard')
CODEC=load_module(ROOT/'scripts/installation/ownership.py','legacy_dependency_codec')


def peer(root, *, current=False):
    files={}
    for name in ('.claude/agents/scripts/provider_prompt.py',
                 '.claude/skills/lead/scripts/provider_prompt.py',
                 '.claude/agents/shared/provider-prompt-projections.v1.json'):
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'fixture owned bytes')
        files[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    if current:
        (root/'.claude/.orche-install.v1.json').write_bytes(CODEC.encode_record(files,'claude','project',configs={}))


def check(root):
    return INSTALL._require_provider_copy_isolation(ROOT,'codex','target',root/'.codex',root)


def test_materialized_legacy_transport_requires_full_selected_update(tmp_path):
    peer(tmp_path)
    with pytest.raises(INSTALL._InstallFailure,match='E_SHARED_LAYOUT_MIGRATION_REQUIRED'):
        check(tmp_path)


def test_completed_independent_peer_does_not_block_codex(tmp_path):
    peer(tmp_path,current=True)
    check(tmp_path)


def test_old_record_without_layout_marker_is_not_independence_proof(tmp_path):
    peer(tmp_path,current=True)
    p=tmp_path/'.claude/.orche-install.v1.json';data=json.loads(p.read_bytes());data.pop('layout',None);p.write_text(json.dumps(data))
    with pytest.raises(INSTALL._InstallFailure,match='E_SHARED_LAYOUT_MIGRATION_REQUIRED'):
        check(tmp_path)


def test_independent_peer_customization_does_not_block_another_client(tmp_path):
    peer(tmp_path,current=True)
    (tmp_path/'.claude/agents/scripts/provider_prompt.py').write_bytes(b'user customized their independent client')
    check(tmp_path)


def test_layout_refusal_has_safe_actionable_public_id(tmp_path):
    peer(tmp_path)
    with pytest.raises(INSTALL._InstallFailure) as caught:
        check(tmp_path)
    text=INSTALL._installer_failure_text(caught.value)
    assert text.startswith('E_SHARED_LAYOUT_MIGRATION_REQUIRED |')
    assert 'context=migration' in text
    assert str(tmp_path) not in text
