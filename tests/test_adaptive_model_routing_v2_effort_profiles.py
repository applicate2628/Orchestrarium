"""Draft record validation, not provider execution or evidence authentication."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
SURFACE = ROOT / 'docs/model-routing-v2'


def bundle(operational=False):
    kind = 'operational' if operational else 'contracts'
    return json.loads((SURFACE / f'adaptive-routing-{kind}.v2.schema.json').read_text(encoding="utf-8"))


def examples():
    return json.loads((SURFACE / 'examples.v2.json').read_text(encoding="utf-8"))


def validator(pointer, operational=False):
    schema = bundle(operational)
    return jsonschema.Draft202012Validator(
        {'$schema': schema['$schema'], '$defs': schema['$defs'], '$ref': pointer},
        format_checker=jsonschema.FormatChecker(),
    )


def registry_entry():
    return examples()['registrySnapshot']['entries'][0]


def test_model_wide_score_and_cost_are_not_sufficient_for_a_candidate():
    entry = registry_entry()
    if 'profileEvaluations' in entry:
        profile = entry.pop('profileEvaluations')[0]
        entry.pop('admittedExecutionClasses')
        entry['capabilities'] = profile['capabilities']
        entry['routeMetrics'] = {
            'basis': 'forecast', 'expectedAcceptedResultCost': 4,
            'expectedLatencySeconds': 200, 'evidenceSnapshotId': 'old-model-wide',
        }
    with pytest.raises(jsonschema.ValidationError):
        validator('#/$defs/modelRegistrySnapshot/$defs/runtimeEntry').validate(entry)


def test_registry_requires_profile_evidence_not_a_global_effort_rank():
    entry = bundle()['$defs']['modelRegistrySnapshot']['$defs']['runtimeEntry']
    assert 'profileEvaluations' in entry['required']
    assert 'routeMetrics' not in entry['properties']
    assert 'capabilities' not in entry['properties']


def test_dispatch_requires_an_exact_profile_evaluation_reference():
    dispatch = examples()['routeDecision']['selectedPortfolio'][0]
    dispatch['worker'].pop('profileEvaluationId', None)
    with pytest.raises(jsonschema.ValidationError):
        validator('#/$defs/dispatchSpec').validate(dispatch)


def test_worker_result_cannot_drop_the_selected_profile_evaluation():
    result = examples()['workerResult']
    result.pop('profileEvaluationId', None)
    with pytest.raises(jsonschema.ValidationError):
        validator('#/$defs/workerResult').validate(result)


def test_slot_requires_execution_class_separate_from_mutation_rights():
    slot = examples()['routeRequest']['portfolioSlots'][0]
    slot.pop('executionClass', None)
    with pytest.raises(jsonschema.ValidationError):
        validator('#/$defs/routeRequest/$defs/portfolioSlot').validate(slot)


def test_effort_mapping_requires_the_same_profile_evaluation_reference():
    mapping = {
        'effortIntent': 'deep', 'actualEffort': 'high',
        'mappingDisposition': 'exact', 'mappingEvidenceRef': 'mapping-current',
        'reasoningRequired': True, 'qualityFloorSatisfied': True,
        'qualityFloorEvidenceRef': 'quality-current',
    }
    with pytest.raises(jsonschema.ValidationError):
        validator('#/$defs/effortMapping', operational=True).validate(mapping)


def test_unknown_metrics_do_not_mean_free_or_instant():
    registry = bundle()['$defs']['modelRegistrySnapshot']['$defs']
    if 'routeMetrics' in registry:
        pointer = '#/$defs/modelRegistrySnapshot/$defs/routeMetrics'
        sample = {key: None for key in registry['routeMetrics']['required']}
        sample.update(basis='unknown', accountingCoverage='whole-route-all-attempts',
                      expectedAcceptedResultCost=0, expectedLatencySeconds=0)
    else:
        pointer = '#/$defs/modelRegistrySnapshot/$defs/runtimeEntry/properties/routeMetrics'
        sample = {'basis':'unknown','expectedAcceptedResultCost':0,
                  'expectedLatencySeconds':0,'evidenceSnapshotId':'unknown-cost'}
    with pytest.raises(jsonschema.ValidationError):
        validator(pointer).validate(sample)


def profile():
    return registry_entry()['profileEvaluations'][0]


def metrics(basis='unknown'):
    schema=bundle()['$defs']['modelRegistrySnapshot']['$defs']['routeMetrics']
    value={key:None for key in schema['required']}
    value.update(basis=basis, accountingCoverage='whole-route-all-attempts')
    return value


def metrics_validator():
    return validator('#/$defs/modelRegistrySnapshot/$defs/routeMetrics')


def test_both_schema_bundles_are_well_formed():
    for operational in (False,True):
        jsonschema.Draft202012Validator.check_schema(bundle(operational))


def test_existing_core_examples_remain_shape_valid():
    data=examples()
    names={'leadLease':'leadLease','registrySnapshot':'modelRegistrySnapshot',
           'routeRequest':'routeRequest','routeDecision':'routeDecision','workerResult':'workerResult'}
    for key,name in names.items():
        validator('#/$defs/'+name).validate(data[key])
    for dispatch in data['routeDecision']['selectedPortfolio']:
        validator('#/$defs/dispatchSpec').validate(dispatch)


def test_existing_operational_examples_remain_shape_valid():
    data=json.loads((SURFACE/'operational-examples.v2.json').read_text(encoding="utf-8"))
    for name,value in data.items():
        pointer='dispatchControl' if name=='writeDispatchControl' else name
        validator('#/$defs/'+pointer,operational=True).validate(value)


@pytest.mark.parametrize('key',('profileEvaluationId','effort','executionClass','taskClass',
                                'evaluationContext','capabilities','evidenceSnapshotId',
                                'recordedAt','expiresAt'))
def test_profile_cannot_drop_comparison_dimensions(key):
    value=profile(); value.pop(key)
    with pytest.raises(jsonschema.ValidationError):
        validator('#/$defs/modelRegistrySnapshot/$defs/profileEvaluation').validate(value)


@pytest.mark.parametrize('key',('datasetSnapshotId','harnessSnapshotId','promptPolicySnapshotId',
                                'acceptanceContractId','toolPolicySnapshotId','contextClass',
                                'billingPolicySnapshotId','routeShapeId'))
def test_profile_context_cannot_omit_an_evidence_dimension(key):
    value=profile();value['evaluationContext'].pop(key)
    with pytest.raises(jsonschema.ValidationError):
        validator('#/$defs/modelRegistrySnapshot/$defs/profileEvaluation').validate(value)


def test_runtime_supports_distinct_measured_effort_profiles():
    entry=registry_entry()
    medium=copy.deepcopy(entry['profileEvaluations'][0])
    medium['profileEvaluationId']='same-runtime-medium'
    medium['effort']='medium'
    medium['routeMetrics']['expectedAcceptedResultCost']=2
    entry['supportedEfforts']=['medium','high']
    entry['admittedEfforts']=['medium','high']
    entry['profileEvaluations'].append(medium)
    validator('#/$defs/modelRegistrySnapshot/$defs/runtimeEntry').validate(entry)
    assert entry['profileEvaluations'][0]['effort']=='high'
    assert entry['profileEvaluations'][0]['routeMetrics']['expectedAcceptedResultCost']==4


def test_unknown_metrics_have_an_explicit_valid_representation():
    metrics_validator().validate(metrics())


def test_measured_zero_success_cannot_claim_a_finite_cost_per_acceptance():
    value=metrics('measured')
    value.update(attemptedTaskCount=5,acceptedTaskCount=0,totalAttemptCost=12,
                 accountingUnit='USD',expectedAcceptedResultCost=0)
    with pytest.raises(jsonschema.ValidationError):
        metrics_validator().validate(value)
    value['expectedAcceptedResultCost']=None
    metrics_validator().validate(value)


def test_measured_cohort_has_counts_but_does_not_invent_token_breakdowns():
    value=metrics('measured')
    value.update(attemptedTaskCount=5,acceptedTaskCount=3,totalAttemptCost=12,
                 expectedAcceptedResultCost=4,accountingUnit='USD')
    metrics_validator().validate(value)
    assert value['tokenUsage'] is None


def test_measured_unknown_total_cost_cannot_claim_known_acceptance_cost():
    value=metrics('measured')
    value.update(attemptedTaskCount=5,acceptedTaskCount=3,
                 expectedAcceptedResultCost=4,accountingUnit='USD')
    with pytest.raises(jsonschema.ValidationError):
        metrics_validator().validate(value)


@pytest.mark.parametrize('key',('attemptedTaskCount','acceptedTaskCount','totalAttemptCost',
                                'modelCalls','toolCalls','reworkCycles'))
def test_forecast_does_not_fabricate_observed_counters(key):
    value=metrics('forecast');value[key]=1
    with pytest.raises(jsonschema.ValidationError):
        metrics_validator().validate(value)


def test_nonzero_cost_requires_an_accounting_unit():
    value=metrics('forecast');value['expectedAcceptedResultCost']=1
    with pytest.raises(jsonschema.ValidationError):
        metrics_validator().validate(value)
    for unit in ('USD','codex-subscription-credits'):
        value['accountingUnit']=unit
        metrics_validator().validate(value)


def test_token_normalization_keeps_reasoning_inside_total_output():
    value=metrics('measured')
    value.update(attemptedTaskCount=5,acceptedTaskCount=3,tokenUsage={
        'normalizationPolicyRef':'normalization-fixture',
        'uncachedInputTokens':30,'cacheReadInputTokens':40,'cacheWriteInputTokens':0,
        'outputTokens':20,'reasoningTokens':12,'reasoningIncludedInOutput':True,
    })
    metrics_validator().validate(value)
    value['tokenUsage']['reasoningIncludedInOutput']=False
    with pytest.raises(jsonschema.ValidationError):
        metrics_validator().validate(value)


def test_generation_names_and_global_effort_ranks_are_not_schema_policy():
    text=json.dumps(bundle())
    assert 'gpt-6-astra' not in text and 'gpt-5.6-sol' not in text
    assert 'effortOrder' not in text
    entry=registry_entry()
    entry['modelId']='future-runtime-observed-model'
    entry['supportedEfforts']=['vendor-reasoning-depth']
    entry['admittedEfforts']=['vendor-reasoning-depth']
    entry['profileEvaluations'][0]['effort']='vendor-reasoning-depth'
    validator('#/$defs/modelRegistrySnapshot/$defs/runtimeEntry').validate(entry)


def test_core_six_record_contracts_and_control_boundaries_remain():
    schema=bundle()
    assert set(schema['$defs'])=={'leadLease','modelRegistrySnapshot','dispatchSpec',
                                  'routeRequest','routeDecision','workerResult'}
    dispatch=examples()['routeDecision']['selectedPortfolio'][0]
    for change in ({'authorizing':True},{'maxDelegationDepth':1}):
        invalid=copy.deepcopy(dispatch);invalid.update(change)
        with pytest.raises(jsonschema.ValidationError):
            validator('#/$defs/dispatchSpec').validate(invalid)


def test_documentation_keeps_missing_runtime_checks_explicit():
    text=(SURFACE/'effort-profile-evidence.md').read_text(encoding="utf-8")
    assert 'Schema validation' in text
    assert 'cross-record routing validator' in text
    assert 'does not authorize' in text
    assert 'Unknown\nnumeric fields are null, never zero.' in text
