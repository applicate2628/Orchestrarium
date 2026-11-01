"""Versioned adoption evidence is actionable, bounded and never authority by itself."""
import re
from pathlib import Path

import pytest

from test_global_nonlead_receipt import _fixture, _apply, ROOT


@pytest.mark.parametrize('name', ['lead', 'analyst'])
def test_adoption_diagnostic_round_trips_exact_selected_tree(tmp_path: Path, name: str):
    owner, source, home, skills, receipt = _fixture(tmp_path)
    _apply(owner, source, home, skills)
    receipt.unlink()
    (skills / name / 'SKILL.md').write_bytes(b'operator authored tree\n')
    before = owner._InstallTransaction._observe(skills)
    with pytest.raises((ValueError, RuntimeError)) as caught:
        owner._preflight_canonical_skills(source, skills, root=ROOT, global_install=True)
    diagnostic = owner._installer_failure_text(caught.value)
    code = 'E_CANONICAL_LEAD_ADOPTION_REQUIRED' if name == 'lead' else 'E_CANONICAL_SKILL_ADOPTION_REQUIRED'
    assert code in diagnostic
    match = re.search(r'adoption=((?:analyst=)?tree-v2:[0-9a-f]{64})(?: \||$)', diagnostic)
    assert match, diagnostic
    token = match[1]
    assert token == ('' if name == 'lead' else 'analyst=') + 'tree-v2:' + owner._tree_sha256(skills / name, ignore_runtime_cache=True)
    assert str(tmp_path) not in diagnostic and 'operator authored' not in diagnostic
    kwargs = ({'replace_unreceipted_lead_sha256': token} if name == 'lead'
              else {'replace_unreceipted_skill_sha256': (token,)})
    plan = owner._preflight_canonical_skills(source, skills, root=ROOT, global_install=True, **kwargs)
    owner._discard_canonical_skills_plan(plan)
    assert owner._InstallTransaction._observe(skills) == before
    (skills / name / 'SKILL.md').write_bytes(b'changed after diagnosis\n')
    with pytest.raises(ValueError, match='ADOPTION_MISMATCH'):
        owner._preflight_canonical_skills(source, skills, root=ROOT, global_install=True, **kwargs)


@pytest.mark.parametrize('adoption', [None, ['analyst', '1'*64], ('../private', '1'*64),
    ('analyst\nprivate', '1'*64), ('x'*129, '1'*64), ('analyst', 'PRIVATE'), ('lead', '1'*64),
    ('analyst', '1'*64, 'extra'), (object(), '1'*64)])
def test_malformed_adoption_evidence_is_not_rendered(tmp_path, adoption):
    owner = _fixture(tmp_path)[0]
    failure = owner._InstallFailure('E_CANONICAL_SKILL_ADOPTION_REQUIRED', 'migration',
                                    ValueError('PRIVATE'), adoption=adoption)
    rendered = owner._installer_failure_text(failure)
    assert 'adoption=' not in rendered
    assert 'PRIVATE' not in rendered and '../private' not in rendered


def test_adoption_requires_typed_matching_context_and_survives_recovery(tmp_path):
    owner = _fixture(tmp_path)[0]
    for code, context in [('E_CREATE_ONLY_COLLISION', 'migration'),
                          ('E_CANONICAL_SKILL_ADOPTION_REQUIRED', 'rollback')]:
        failure = owner._InstallFailure(code, context, adoption=('analyst', '1'*64))
        assert 'adoption=' not in owner._installer_failure_text(failure)
    plain = ValueError('E_CANONICAL_SKILL_ADOPTION_REQUIRED: analyst=tree-v2:' + '1'*64)
    plain._installer_adoption = ('analyst', '1'*64)
    assert 'adoption=' not in owner._installer_failure_text(plain)
    failure = owner._InstallFailure('E_CANONICAL_SKILL_ADOPTION_REQUIRED', 'migration',
                                    adoption=('analyst', '1'*64))
    rebound = failure._with_recovery_path(tmp_path / 'private-recovery')
    assert 'adoption=analyst=tree-v2:' + '1'*64 in owner._installer_failure_text(rebound)
    assert str(tmp_path) not in owner._installer_failure_text(rebound)


def test_legacy_digest_does_not_gain_strong_adoption_authority(tmp_path):
    owner, source, home, skills, receipt = _fixture(tmp_path)
    _apply(owner, source, home, skills)
    (skills / 'analyst' / 'SKILL.md').write_bytes(b'unknown custom tree')
    bare = owner._tree_sha256(skills / 'analyst', ignore_runtime_cache=True)
    with pytest.raises(ValueError, match='E_LEGACY_TREE_WITNESS_UNAVAILABLE'):
        owner._adoption_identity_v2('analyst', skills / 'analyst', bare)


def test_cause_cannot_supply_adoption_hint_to_typed_wrapper(tmp_path):
    owner = _fixture(tmp_path)[0]
    cause = ValueError('private')
    cause._installer_adoption = ('analyst', '1'*64)
    wrapper = owner._InstallFailure('E_CANONICAL_SKILL_ADOPTION_REQUIRED', 'migration', cause)
    assert 'adoption=' not in owner._installer_failure_text(wrapper)
