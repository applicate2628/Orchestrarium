"""Effort floors and measurement binding for the explicit Astra selector."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'src.codex/skills/astra-routing/scripts/resolve.py'


def load():
    spec = importlib.util.spec_from_file_location('astra_effort_binding_test', PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def request(module, **changes):
    fields = dict(task_class='mathematical-research',
                  available_models=('gpt-6-astra',),
                  route_evidence='mathematics-quality-floor')
    fields.update(changes)
    return module.resolve_v1_astra_route(**fields)


@pytest.mark.parametrize(('effort', 'evidence', 'approval'), (
    ('medium', None, False), ('high', 'medium-objective-failure', False),
    ('xhigh', 'measured-xhigh-gain', False), ('max', None, True),
))
def test_cost_claim_cannot_select_an_unbound_effort(effort, evidence, approval):
    result = request(load(), route_evidence='measured-cost-to-pass',
                     astra_cost_microusd=100, legacy_cost_microusd=300,
                     requested_effort=effort, effort_evidence=evidence,
                     allow_max_effort=approval)
    assert result['status'] == 'denied'
    assert result['stableId'] == 'E_ASTRA_V1_ECONOMICS_EFFORT_REQUIRED'
    assert result['executionAuthorized'] is False


PROFILE_ARGS = {
    'medium': {},
    'high': {'effort_evidence': 'measured-high-gain'},
    'xhigh': {'effort_evidence': 'measured-xhigh-gain'},
    'max': {'allow_max_effort': True},
}


@pytest.mark.parametrize('effort', PROFILE_ARGS)
def test_matching_measurement_selects_the_exact_profile_without_authority(effort):
    result = request(load(), route_evidence='measured-cost-to-pass',
                     astra_cost_microusd=100, legacy_cost_microusd=300,
                     measured_effort=effort, requested_effort=effort,
                     **PROFILE_ARGS[effort])
    assert result['status'] == 'selected'
    assert result['costComparison'] == {
        'astraEffort': effort, 'astraCostMicroUsd': 100,
        'legacyCostMicroUsd': 300, 'savingsMicroUsd': 200,
    }
    assert result['codexFlags'][-1] == f'model_reasoning_effort={effort}'
    assert result['authorizing'] is False
    assert result['executionAuthorized'] is False
    assert result['requiresAdapterAdmission'] is True


@pytest.mark.parametrize(('measured', 'selected'), [
    (measured, selected) for measured in PROFILE_ARGS
    for selected in PROFILE_ARGS if measured != selected
])
def test_measurement_for_another_effort_cannot_be_reused(measured, selected):
    result = request(load(), route_evidence='measured-cost-to-pass',
                     astra_cost_microusd=100, legacy_cost_microusd=300,
                     measured_effort=measured, requested_effort=selected,
                     **PROFILE_ARGS[selected])
    assert result['status'] == 'denied'
    assert result['stableId'] == 'E_ASTRA_V1_ECONOMICS_EFFORT_MISMATCH'
    assert result['codexFlags'] == []


@pytest.mark.parametrize('value', ('low', 'none', 'unsupported'))
def test_measurement_effort_must_be_admitted(value):
    result = request(load(), route_evidence='measured-cost-to-pass',
                     astra_cost_microusd=100, legacy_cost_microusd=300,
                     measured_effort=value)
    assert result['stableId'] == 'E_ASTRA_V1_ECONOMICS_EFFORT_INVALID'


@pytest.mark.parametrize('value', ('', 'x' * 33, 'bad\x00value', True, 1, [], {}))
def test_malformed_measurement_effort_is_a_typed_input_denial(value):
    result = request(load(), measured_effort=value)
    assert result['stableId'] == 'E_ASTRA_V1_REQUEST_INVALID'
    assert result['codexFlags'] == []


def test_orphan_measurement_is_not_ignored():
    result = request(load(), measured_effort='medium')
    assert result['stableId'] == 'E_ASTRA_V1_ECONOMICS_INVALID'


@pytest.mark.parametrize('task,effort', (
    ('mathematical-research', 'medium'), ('critical-recovery', 'high'),
))
def test_measurement_is_bound_even_when_effort_is_a_task_default(task, effort):
    result = request(load(), task_class=task, route_evidence='measured-cost-to-pass',
                     astra_cost_microusd=100, legacy_cost_microusd=300,
                     measured_effort=effort)
    assert result['status'] == 'selected'
    assert result['effort'] == effort
    assert result['costComparison']['astraEffort'] == effort


@pytest.mark.parametrize('astra_cost', (300, 301))
def test_effort_binding_does_not_relax_strict_economic_improvement(astra_cost):
    result = request(load(), route_evidence='measured-cost-to-pass',
                     astra_cost_microusd=astra_cost, legacy_cost_microusd=300,
                     measured_effort='medium')
    assert result['stableId'] == 'E_ASTRA_V1_ECONOMICS_NOT_BETTER'


def test_measurement_does_not_replace_max_approval():
    result = request(load(), route_evidence='measured-cost-to-pass',
                     astra_cost_microusd=100, legacy_cost_microusd=300,
                     measured_effort='max', requested_effort='max')
    assert result['stableId'] == 'E_ASTRA_V1_MAX_APPROVAL_REQUIRED'


def test_cli_propagates_measurement_effort(capsys):
    import json
    module = load()
    code = module.main([
        '--task-class', 'mathematical-research', '--available-model', 'gpt-6-astra',
        '--route-evidence', 'measured-cost-to-pass', '--astra-cost-microusd', '100',
        '--legacy-cost-microusd', '300', '--measured-effort', 'medium',
    ])
    captured = capsys.readouterr()
    assert code == 0 and captured.err == ''
    assert json.loads(captured.out)['costComparison']['astraEffort'] == 'medium'
