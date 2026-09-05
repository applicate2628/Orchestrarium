"""Exercise installed pure selectors; do not launch providers or register hooks."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _run(script: Path, args=(), *, env=None, input=None):
    return subprocess.run(
        [sys.executable, str(script), *args], input=input, text=True,
        capture_output=True, encoding='utf-8', timeout=60, cwd=ROOT, env=env,
    )


@pytest.fixture(scope='module', params=[('codex', 'claude'), ('claude', 'codex')])
def installed(request, tmp_path_factory):
    home = tmp_path_factory.mktemp('routing-utility-home')
    env = {**os.environ, 'HOME': str(home), 'USERPROFILE': str(home),
           'PYTHONIOENCODING': 'utf-8'}
    project = home / 'project'
    project.mkdir()
    for host in request.param:
        result = _run(ROOT / 'scripts' / f'install-{host}.py', (
            '--target', str(project / f'.{host}'), '--allow-unsafe-target',
            '--no-hypothesis-hook',
        ), env=env)
        assert result.returncode == 0, result.stdout + result.stderr
    return project, env


def test_both_hosts_see_the_canonical_utility_files(installed):
    project, _env = installed
    for name, leaves in {
        'astra-routing': ('SKILL.md', 'agents/openai.yaml', 'scripts/resolve.py'),
        'lead-worker-routing': ('SKILL.md', 'agents/openai.yaml', 'scripts/resolve.py', 'scripts/_resolver_base.py'),
    }.items():
        for leaf in leaves:
            canonical = project / '.agents/skills' / name / leaf
            projected = project / '.claude/skills' / name / leaf
            assert canonical.read_bytes() == (ROOT / 'src.codex/skills' / name / leaf).read_bytes()
            assert projected.samefile(canonical)


def test_installed_astra_matches_the_source_decision(installed):
    project, env = installed
    args = ('--task-class', 'mathematical-research', '--available-model',
            'gpt-6-astra', '--route-evidence', 'mathematics-quality-floor')
    source = _run(ROOT / 'src.codex/skills/astra-routing/scripts/resolve.py', args, env=env)
    for host_path in ('.agents', '.claude'):
        result = _run(project / host_path / 'skills/astra-routing/scripts/resolve.py', args, env=env)
        assert source.returncode == result.returncode == 0
        assert json.loads(source.stdout) == json.loads(result.stdout)
        assert json.loads(result.stdout)['executionAuthorized'] is False


def _request(lead):
    def candidate(name, provider, family, availability, priority):
        return dict(candidateId=name, provider=provider, runtime=f'{provider}-cli',
                    providerFamily=family, model=f'{provider}-runtime-observed', effort='high',
                    priority=priority, availability=availability, maxMutationClass='read-only',
                    capabilities=['engineering-challenge'], tools=[], isolatedFromLead=True,
                    maxDelegationDepth=0, authorizing=False, evidenceSnapshotId=f'evidence-{name}')
    return dict(schemaVersion=1, dispatchId='installed-routing-test', policySnapshotId='policy-test',
                leadHost=lead, assignedRole='engineering-challenger', scopeId='scope-test',
                capabilitySlot='engineering-challenge', mutationClass='read-only', requiredTools=[],
                excludedProviderFamilies=[], artifactContract='challenge-report-v1',
                gateContract='lead-verifies-artifact-v1', candidates=[
                    candidate('unpaid', 'codex', 'openai', 'not-entitled', 1),
                    candidate('replacement', 'kimi', 'moonshot', 'available', 2),
                ])


@pytest.mark.parametrize('lead', ['codex', 'claude'])
def test_installed_worker_fallback_preserves_contract_and_nonauthority(installed, lead):
    project, env = installed
    request = _request(lead)
    payload = json.dumps(request)
    source = _run(ROOT / 'src.codex/skills/lead-worker-routing/scripts/resolve.py',
                  ('--request-file', '-'), env=env, input=payload)
    assert source.returncode == 0, source.stderr
    for host_path in ('.agents', '.claude'):
        result = _run(project / host_path / 'skills/lead-worker-routing/scripts/resolve.py',
                      ('--request-file', '-'), env=env, input=payload)
        assert result.returncode == 0, result.stderr
        record = json.loads(result.stdout)
        assert record == json.loads(source.stdout)
        assert record['selectedCandidate']['candidateId'] == 'replacement'
        assert record['fallbackApplied'] is True
        assert record['executionAuthorized'] is False and record['authorizing'] is False
        for field in ('leadHost', 'assignedRole', 'scopeId', 'artifactContract', 'gateContract'):
            assert record[field] == request[field]


def test_installed_private_core_is_not_a_second_entrypoint(installed):
    project, env = installed
    result = _run(project / '.agents/skills/lead-worker-routing/scripts/_resolver_base.py', env=env)
    assert result.returncode == 2
    assert 'E_LEAD_WORKER_V1_PRIVATE_ENTRYPOINT' in result.stdout + result.stderr
