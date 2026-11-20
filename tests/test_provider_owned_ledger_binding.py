"""Each installed client binds only its own ordinary ledger-helper cohort."""
from pathlib import Path
import pytest
from test_provider_prompt_relocation import _load_owner
ROOT=Path(__file__).resolve().parents[1]
MEMBERS=('scripts/agent-run-ledger.py','scripts/validate-work-item-state.py',
         'scripts/mutate-work-item.py','scripts/solution_attempt/reducer.py',
         'shared/schemas/agent-runs.schema.json')


def package(root):
    for name in MEMBERS:
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(b'# ordinary fixture member\n')
    for name in ('provider_prompt.py','linked_runtime_subroots.py'):
        (root/'scripts'/name).write_bytes((ROOT/'scripts'/name).read_bytes())


@pytest.mark.parametrize('global_scope',[False,True])
@pytest.mark.parametrize('entry',['canonical','transport'])
def test_claude_uses_own_cohort_even_with_codex_present(tmp_path,monkeypatch,global_scope,entry):
    base=tmp_path/'scope'; own=base/'.claude/skills/lead'; other=base/'.agents/skills/lead'
    package(own);package(other)
    peer=base/'.claude/agents/scripts/provider_prompt.py';peer.parent.mkdir(parents=True)
    peer.write_bytes((ROOT/'scripts/provider_prompt.py').read_bytes())
    home=base if global_scope else tmp_path/'other-home';home.mkdir(exist_ok=True)
    monkeypatch.setattr(Path,'home',classmethod(lambda cls:home))
    selected=own/'scripts/provider_prompt.py' if entry=='canonical' else peer
    module=_load_owner(selected,'owned_ledger_'+entry+'_'+str(global_scope))
    binding=module._ledger_helper_binding()
    assert binding is not None
    assert binding.helper.samefile(own/'scripts/agent-run-ledger.py')
    assert not binding.helper.samefile(other/'scripts/agent-run-ledger.py')
    binding.assert_current()
    (own/'scripts/agent-run-ledger.py').unlink()
    assert module.ledger_helper() is None, 'Missing own helper must not select another client'

@pytest.mark.parametrize('entry', ['canonical', 'transport'])
def test_global_same_client_linked_skills_root(tmp_path, monkeypatch, entry):
    from test_legacy_obligation_migration import make_directory_link
    base = tmp_path / 'home'
    backing = tmp_path / 'owned-skills'
    package(backing / 'lead')
    peer = base / '.claude/agents/scripts/provider_prompt.py'
    peer.parent.mkdir(parents=True)
    peer.write_bytes((ROOT / 'scripts/provider_prompt.py').read_bytes())
    logical = base / '.claude/skills'
    make_directory_link(logical, backing)
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: base))
    selected = logical / 'lead/scripts/provider_prompt.py' if entry == 'canonical' else peer
    module = _load_owner(selected, 'same_client_linked_' + entry)
    binding = module._ledger_helper_binding()
    assert binding is not None
    assert binding.helper == backing / 'lead/scripts/agent-run-ledger.py'
    binding.assert_current()
