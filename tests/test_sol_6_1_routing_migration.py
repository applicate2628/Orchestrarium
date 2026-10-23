"""Offline policy/stock-migration contract; no providers or real HOME are used.

Frozen priors are bytes from 604d7d0b29fc320f2679fc0d49dbedd776551cb7.
Time, locale, random seeds and scheduling do not affect these byte/value oracles.
"""
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import tomllib

import tempfile
import unittest
from scripts import production_installer as installer
from scripts import provider_prompt

ROOT = Path(__file__).resolve().parents[1]
PRIORS = ROOT / 'tests/fixtures/sol-6-1-priors'


def check_no_flags_codex_uses_sol_6_1_xhigh():
    flags, model, effort = provider_prompt.resolved_profile('codex', [])
    assert (model, effort) == ('gpt-6.1-sol', 'xhigh')
    assert flags == ['--model', 'gpt-6.1-sol', '-c', 'model_reasoning_effort=xhigh']


def check_live_native_defaults_preserve_efforts_except_scientific():
    policy = json.loads((ROOT/'shared/role-routing-policy.v1.json').read_text())
    for path in sorted((ROOT/'src.codex/agents').glob('*.toml')):
        prior = tomllib.loads((PRIORS/path.name).read_text())
        current = tomllib.loads(path.read_text())
        expected_model = 'gpt-6-luna' if path.stem.startswith('mechanical-') else 'gpt-6.1-sol'
        expected_effort = 'high' if path.stem == 'scientific-software-engineer' else prior['model_reasoning_effort']
        assert (current['model'],current['model_reasoning_effort']) == (expected_model,expected_effort), path.name
        profile = policy['profiles'][policy['roles'][path.stem]['defaultProfile']]
        assert (profile['codexModel'],profile['effort']) == (expected_model,expected_effort)


def check_bounded_medium_corridors_preserve_critical_floors():
    policy = json.loads((ROOT/'shared/role-routing-policy.v1.json').read_text())
    for name in ['exploration','planning','engineering']:
        assert 'frontier-medium' in policy['taskClasses'][name]['admissibleProfiles']
    for name in ['explorer','analyst','planner','worker','backend-engineer','platform-engineer','scientific-software-engineer']:
        assert 'frontier-medium' in policy['roles'][name]['allowedProfiles']
    for name in ['review','critical-design','critical-security','recovery']:
        assert 'frontier-medium' not in policy['taskClasses'][name]['admissibleProfiles']
    assert 'frontier-xhigh' in policy['roles']['explorer']['allowedProfiles']
    assert 'frontier-xhigh' in policy['taskClasses']['exploration']['admissibleProfiles']


def check_frozen_priors_are_exact_and_native_upgrade_is_admitted(tmp_path):
    digests = json.loads((PRIORS/'SHA256.json').read_text())
    agents = tmp_path/'agents'; agents.mkdir()
    for name,digest in digests.items():
        payload=(PRIORS/name).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == digest
        if name.endswith('.toml'):
            (agents/name).write_bytes(payload)
    plan = installer._preflight_codex_native_roles(ROOT,ROOT/'src.codex/agents',agents,tmp_path/'config.toml')
    changed = [item for item in plan.role_files if item.accepted_prior is not None]
    assert len(changed) == len(list(agents.glob('*.toml'))) - 2
    for item in changed:
        assert item.accepted_prior == digests[item.relative_path.name]


def check_customized_prior_fails_closed_without_mutation(tmp_path):
    agents = tmp_path/'agents'; agents.mkdir()
    customized = (PRIORS/'analyst.toml').read_bytes() + b'\n# user customization\n'
    target = agents/'analyst.toml'; target.write_bytes(customized)
    with unittest.TestCase().assertRaisesRegex(ValueError, 'E_CREATE_ONLY_COLLISION'):
        installer._preflight_codex_native_roles(ROOT,ROOT/'src.codex/agents',agents,tmp_path/'config.toml')
    assert target.read_bytes() == customized


class MigrationTests(unittest.TestCase):
    def test_defaults(self):
        check_no_flags_codex_uses_sol_6_1_xhigh()

    def test_native_profiles(self):
        check_live_native_defaults_preserve_efforts_except_scientific()

    def test_corridors(self):
        check_bounded_medium_corridors_preserve_critical_floors()

    def test_stock_upgrade(self):
        with tempfile.TemporaryDirectory() as directory:
            check_frozen_priors_are_exact_and_native_upgrade_is_admitted(Path(directory))

    def test_customization(self):
        with tempfile.TemporaryDirectory() as directory:
            check_customized_prior_fails_closed_without_mutation(Path(directory))

    def test_canonical_stock_policy_and_transport_upgrade(self):
        import tarfile
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/'skills'; target.mkdir()
            with tarfile.open(PRIORS/'canonical-skills.tar.gz') as archive:
                archive.extractall(target, filter='data')
            assert installer._tree_sha256(target/'lead', ignore_runtime_cache=True) == '0627712baff8adf6423d8cb766e5effcfa8001196e077eaf5d1b4f17e5d97a85'
            plan = installer._preflight_canonical_skills(ROOT/'src.codex/skills', target, root=ROOT)
            try:
                lead = next(s for s in plan.skills if s.name == 'lead')
                assert lead.accepted_prior == '0627712baff8adf6423d8cb766e5effcfa8001196e077eaf5d1b4f17e5d97a85'
                projection = installer._stage_claude_transport_projection(ROOT,plan.stage.path/'scripts',target/'lead/scripts')
                assert projection.accepted_prior_set == '604d7d0b'
            finally:
                installer._discard_canonical_skills_plan(plan)

    def test_old_explicit_external_profiles_stay_literal(self):
        for model in ['gpt-6-sol', 'gpt-5.6-sol']:
            for effort in ['high','xhigh','max']:
                _, actual_model, actual_effort = provider_prompt.resolved_profile('codex',['--model',model,'-c','model_reasoning_effort='+effort])
                assert (actual_model,actual_effort) == (model,effort)

    def test_native_stock_upgrade_is_idempotent_and_rolls_back(self):
        for commit in [False, True]:
            with self.subTest(commit=commit), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); agents = root/'agents'; agents.mkdir()
                before = {}
                for path in PRIORS.glob('*.toml'):
                    before[path.name] = path.read_bytes()
                    (agents/path.name).write_bytes(before[path.name])
                plan = installer._preflight_codex_native_roles(ROOT, ROOT/'src.codex/agents', agents, root/'config.toml')
                expected = nullcontext() if commit else self.assertRaisesRegex(installer._InstallFailure, "E_INSTALL_TRANSACTION_UNCOMMITTED")
                with expected, installer._InstallTransaction([agents], enabled=True) as transaction:
                    owner = installer._CreateOnlyMutablePath(root, transaction, dry_run=False)
                    installer._install_codex_native_roles(ROOT, ROOT/'src.codex/agents', agents, owner, plan=plan)
                    for path in agents.glob('*.toml'):
                        assert path.read_bytes() == (ROOT/'src.codex/agents'/path.name).read_bytes()
                    if commit:
                        transaction.commit()
                if commit:
                    again = installer._preflight_codex_native_roles(ROOT, ROOT/'src.codex/agents', agents, root/'config.toml')
                    assert all(item.accepted_prior is None for item in again.role_files)
                else:
                    assert {p.name:p.read_bytes() for p in agents.glob('*.toml')} == before

    def test_canonical_customized_policy_is_preserved(self):
        import tarfile
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/'skills'; target.mkdir()
            with tarfile.open(PRIORS/'canonical-skills.tar.gz') as archive:
                archive.extractall(target, filter='data')
            policy = target/'lead/shared/role-routing-policy.v1.json'
            customized = policy.read_bytes() + b'\n'
            policy.write_bytes(customized)
            with self.assertRaisesRegex(ValueError,'E_ACCEPTED_PRIOR_COLLISION: lead'):
                installer._preflight_canonical_skills(ROOT/'src.codex/skills', target, root=ROOT)
            assert policy.read_bytes() == customized

    def test_selector_admits_bounded_medium_and_denies_unsupported_and_max(self):
        import importlib.util
        import sys
        spec = importlib.util.spec_from_file_location('sol_migration_resolver', ROOT/'scripts/resolve-agents-mode.py')
        resolver = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = resolver
        spec.loader.exec_module(resolver)
        host = {'explicitModelControl': True, 'explicitReasoningEffortControl': True}
        scope = {'authority':'parent-dispatcher-only','allowedTools':[], 'changeSurface':['accepted bounded contract']}
        for role,task in [('explorer','exploration'),('planner','planning'),('worker','engineering'),('scientific-software-engineer','engineering')]:
            description = resolver.describe_ordinary_native_role_options(role,task,host,repo_root=ROOT)
            selected = resolver.resolve_ordinary_native_dispatch(description,requested_model='gpt-6.1-sol',requested_effort='medium',caller_rationale='Accepted bounded contract with directly testable oracle.',approved_execution_scope=scope)
            assert selected['status'] == 'resolved', selected
            assert selected['resolvedProfile'] == 'frontier-medium'
            assert selected['fallback'] == 'none'
        description = resolver.describe_ordinary_native_role_options('scientific-software-engineer','engineering',host,repo_root=ROOT)
        for model,effort in [('gpt-6.1-sol','max'),('gpt-unknown','high')]:
            result = resolver.resolve_ordinary_native_dispatch(description,requested_model=model,requested_effort=effort,caller_rationale='Explicit request.',approved_execution_scope=scope)
            assert result['status'] == 'denied'
            assert result['fallback'] == 'none'
        for role,task in [('security-reviewer','critical-security'),('architecture-reviewer','review'),('worker','recovery')]:
            description = resolver.describe_ordinary_native_role_options(role,task,host,repo_root=ROOT)
            result = resolver.resolve_ordinary_native_dispatch(description,requested_model='gpt-6.1-sol',requested_effort='medium',caller_rationale='Bounded work cannot lower this floor.',approved_execution_scope=scope)
            assert result['status'] == 'denied'
            assert result['fallback'] == 'none'

    def test_canonical_stock_upgrade_applies_and_reinstall_is_exact(self):
        import tarfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); target = root/'skills'; target.mkdir()
            with tarfile.open(PRIORS/'canonical-skills.tar.gz') as archive:
                archive.extractall(target, filter='data')
            with installer._InstallTransaction([target], enabled=True) as transaction:
                owner = installer._CreateOnlyMutablePath(root,transaction,dry_run=False)
                installer._install_canonical_skills(ROOT/'src.codex/skills',target,owner,root=ROOT)
                transaction.commit()
            assert (target/'lead/shared/role-routing-policy.v1.json').read_bytes() == (ROOT/'shared/role-routing-policy.v1.json').read_bytes()
            assert (target/'lead/shared/orchestrarium-role-manifest.json').read_bytes() == (ROOT/'src.codex/agents/orchestrarium-role-manifest.json').read_bytes()
            assert (target/'lead/scripts/provider_prompt.py').read_bytes() == (ROOT/'scripts/provider_prompt.py').read_bytes()
            plan = installer._preflight_canonical_skills(ROOT/'src.codex/skills',target,root=ROOT)
            try:
                assert all(s.accepted_prior is None and not s.accepted_prior_files for s in plan.skills)
            finally:
                installer._discard_canonical_skills_plan(plan)

    def test_external_medium_is_not_admitted_by_operator_schema(self):
        schema = json.loads((ROOT/'shared/agents-mode.schema.json').read_text())
        profile = next(row for row in schema['scalarKeys'] if row['name'] == 'externalCodexProfile')
        assert 'gpt-6.1-sol-medium' not in profile['allowed']
        assert profile['default'] == 'gpt-6.1-sol-xhigh'
        # Native bounded medium must stay available behind the role/task selector;
        # security/review/recovery negatives are asserted by the selector test above.
        check_bounded_medium_corridors_preserve_critical_floors()
