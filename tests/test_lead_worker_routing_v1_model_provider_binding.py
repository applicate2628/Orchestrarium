"""Known-model policy guard in the import-only V1 core; no provider launch."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/'src.codex/skills/lead-worker-routing/scripts/_resolver_base.py'


def load():
    spec=importlib.util.spec_from_file_location('worker_effort_core_test',PATH)
    assert spec and spec.loader
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def request(model, effort):
    return {
        'schemaVersion':1,'dispatchId':'dispatch-fixture','policySnapshotId':'policy-fixture',
        'leadHost':'codex','assignedRole':'analyst','scopeId':'scope-fixture',
        'capabilitySlot':'engineering-challenge','mutationClass':'read-only',
        'requiredTools':[],'excludedProviderFamilies':[],
        'artifactContract':'challenge-report-v1','gateContract':'lead-verifies-artifact-v1',
        'candidates':[{
            'candidateId':'candidate-fixture','provider':'codex','runtime':'codex-native',
            'providerFamily':'openai','model':model,'effort':effort,'priority':1,
            'availability':'available','maxMutationClass':'read-only',
            'capabilities':['engineering-challenge'],'tools':[],
            'isolatedFromLead':True,'maxDelegationDepth':0,'authorizing':False,
            'evidenceSnapshotId':'evidence-fixture',
        }],
    }


@pytest.mark.parametrize(('model','effort'), (
    ('gpt-6-astra','low'), ('gpt-6-astra','none'), ('gpt-6-astra','banana'),
    ('gpt-5.6-sol','medium'), ('gpt-5.6-sol','low'),
    ('gpt-5.6-terra','medium'), ('gpt-5.6-terra','low'),
))
def test_known_model_below_operator_effort_floor_is_rejected(model, effort):
    result=load().resolve_v1_worker_route(request(model,effort))
    assert result['status']=='denied'
    assert result['rejections'][0]['stableId']==('E_LEAD_WORKER_V1_EFFORT_UNSUPPORTED' if effort in ('none','banana') else 'E_LEAD_WORKER_V1_EFFORT_BELOW_MINIMUM')


def test_luna_cannot_enter_the_generic_general_worker_route():
    result=load().resolve_v1_worker_route(request('gpt-5.6-luna','high'))
    assert result['status']=='denied'
    assert result['rejections'][0]['stableId']=='E_LEAD_WORKER_V1_MECHANICAL_ROUTE_REQUIRED'


@pytest.mark.parametrize('model', ('gpt-6-astra', 'gpt-5.6-sol', 'gpt-5.6-terra', 'gpt-5.6-luna'))
@pytest.mark.parametrize('provider,runtime,family', [('claude','claude-cli','anthropic'), ('kimi','kimi-cli','moonshot'), ('grok','grok-cli','xai')])
def test_known_openai_model_cannot_claim_another_provider_family(model, provider, runtime, family):
    data=request(model,'high')
    data['candidates'][0].update(provider=provider,runtime=runtime,providerFamily=family)
    result=load().resolve_v1_worker_route(data)
    assert result['status']=='denied'
    assert result['rejections'][0]['stableId']=='E_LEAD_WORKER_V1_MODEL_PROVIDER_MISMATCH'


@pytest.mark.parametrize(('model','effort'), [
    (model,effort) for model,efforts in (
        ('gpt-6-astra',('medium','high','xhigh','max')),
        ('gpt-5.6-sol',('high','xhigh','max')),
        ('gpt-5.6-terra',('high','xhigh','max')),
    ) for effort in efforts
])
def test_admitted_known_profiles_remain_selection_only(model,effort):
    result=load().resolve_v1_worker_route(request(model,effort))
    assert result['status']=='selected'
    assert result['selectedCandidate']['model']==model
    assert result['selectedCandidate']['effort']==effort
    assert result['authorizing'] is False
    assert result['requiresLeadVerification'] is True
    assert result['maxDelegationDepth']==0


def test_unknown_model_is_not_mistaken_for_a_verified_known_profile():
    result=load().resolve_v1_worker_route(request('runtime-observed-future-model','vendor-effort'))
    assert result['status']=='selected'
    assert result['authorizing'] is False
    # This is deliberately not execution admission. The public facade and
    # provider adapter still own actual model/effort support and entitlements.


def test_denied_profile_does_not_hide_the_rejection_on_explicit_next_candidate():
    data=request('gpt-6-astra','low')
    next_candidate=request('gpt-5.6-sol','high')['candidates'][0]
    next_candidate.update(candidateId='next-candidate',priority=2)
    data['candidates'].append(next_candidate)
    result=load().resolve_v1_worker_route(data)
    assert result['status']=='selected'
    assert result['selectedCandidate']['model']=='gpt-5.6-sol'
    assert result['rejections'][0]['stableId']=='E_LEAD_WORKER_V1_EFFORT_BELOW_MINIMUM'
    assert result['authorizing'] is False


def test_unavailable_profile_still_has_no_implicit_candidate():
    data=request('gpt-6-astra','medium')
    data['candidates'][0]['availability']='not-entitled'
    result=load().resolve_v1_worker_route(data)
    assert result['status']=='unavailable'
    assert result['selectedCandidate'] is None


def test_private_entrypoint_stays_closed(capsys):
    import json
    assert load().main([])==2
    result=json.loads(capsys.readouterr().out)
    assert result['stableId']=='E_LEAD_WORKER_V1_PRIVATE_ENTRYPOINT'
    assert result['authorizing'] is False
