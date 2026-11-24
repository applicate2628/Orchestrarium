"""AGY's installed transport binds only its own ordinary helper cohort."""
from pathlib import Path
import pytest
from test_provider_owned_ledger_binding import package
from test_provider_prompt_relocation import _load_owner

@pytest.mark.parametrize('global_scope', [False, True])
def test_agy_owns_cohort_and_held_binding_detects_drift(tmp_path, monkeypatch, global_scope):
    base = tmp_path / 'selected'
    home = base if global_scope else tmp_path / 'home'
    home.mkdir(parents=True, exist_ok=True)
    own = base / ('.gemini/config/orchestrarium-antigravity' if global_scope else '.agents/orchestrarium-antigravity')
    other = base / '.agents/skills/lead'
    package(own); package(other)
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: home))
    module = _load_owner(own / 'scripts/provider_prompt.py', 'agy_scope_' + str(global_scope))
    held = module._ledger_helper_binding()
    assert held is not None
    assert held.helper.samefile(own / 'scripts/agent-run-ledger.py')
    held.assert_current()
    member = own / 'scripts/agent-run-ledger.py'
    member.write_bytes(b'# changed current helper\n')
    with pytest.raises((OSError, RuntimeError, ValueError)):
        held.assert_current()
    assert module._ledger_helper_binding() is not None
    member.unlink()
    assert module._ledger_helper_binding() is None
    assert (other / 'scripts/agent-run-ledger.py').exists()


def test_agy_global_scope_is_actual_home_not_arbitrary_suffix(tmp_path, monkeypatch):
    own = tmp_path / 'not-home/.gemini/config/orchestrarium-antigravity'
    package(own)
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path / 'home'))
    module = _load_owner(own / 'scripts/provider_prompt.py', 'agy_wrong_home')
    assert module._ledger_helper_binding() is None
