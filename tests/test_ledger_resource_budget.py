"""Declared synthetic operation-resource tests; no provider or foreign inputs."""
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_agent_run_ledger import prepare_valid_work_item


ROOT = Path(__file__).resolve().parents[1]


def owner(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'scripts' / name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fixture(tmp_path, count=4100):
    item = prepare_valid_work_item(tmp_path)
    base = dict(schemaVersion=2, workItem=item.name, role='qa-engineer',
                executionRole='internal', status='completed', gate='PASS',
                eventKind='standalone', scope=['synthetic-history-v4-4100'],
                artifact='reviews/qa.md', evidence=[{'kind': 'manual-check', 'ref': 'synthetic historical action'}],
                startedAt='2026-10-19T00:00:00Z', updatedAt='2026-10-19T00:00:00Z')
    rows = [{**base, 'runId': f'synthetic-history-v4-{n:05d}'} for n in range(count)]
    rows[-1].update(runId='synthetic-review-v4-001', status='revise', gate='REVISE', findingClass='correctness')
    raw = b''.join(json.dumps(row, separators=(',', ':')).encode() + b'\n' for row in rows)
    (item / 'agent-runs.jsonl').write_bytes(raw)
    return item, raw


def cli(item, *args):
    return subprocess.run([sys.executable, '-X', 'utf8', '-B', str(ROOT / 'scripts/agent-run-ledger.py'),
                           '--work-item', str(item), *args], cwd=ROOT,
                          text=True, capture_output=True, timeout=30)


def options(budget):
    return ['--ledger-max-events', str(budget.max_events),
            '--ledger-max-bytes', str(budget.max_ledger_bytes)]


def test_first_ordinary_native_action_terminal_replay_and_compact_observation(tmp_path):
    v = owner('validate-work-item-state.py')
    item, before = fixture(tmp_path)
    capacity = v.LedgerResourceBudgetV1(4200, len(before) + 8 * (v.MAX_LEDGER_LINE_BYTES + 2))
    demand = v.inspect_ledger_resource_demand(item / 'agent-runs.jsonl', capacity,
                                            unknown_terminal_rows=2)
    v.resolve_ledger_resource_budget(capacity.max_events, capacity.max_ledger_bytes,
                                     demand=demand, managed=True)
    budget = v.resolve_ledger_resource_budget(demand.required_events, demand.required_bytes,
                                              demand=demand, managed=True)
    launch = cli(item, *options(budget), 'append', '--run-id', 'synthetic-launch-v4-001',
                 '--role', 'backend-engineer', '--execution-role', 'internal', '--status', 'running',
                 '--gate', 'none', '--scope', 'synthetic-native-route-v4', '--event-kind', 'launch',
                 '--started-at', '2026-10-19T00:00:00Z', '--updated-at', '2026-10-19T00:00:00Z')
    assert launch.returncode == 0, launch.stderr[:1500]
    # A real finite Source-class local action, never an invented provider frame.
    action = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-c', 'assert 7 * 6 == 42'],
                            cwd=ROOT, capture_output=True, timeout=10)
    assert action.returncode == 0
    settlement = ['settle-launch', '--launch-run-id', 'synthetic-launch-v4-001',
                  '--run-id', 'synthetic-terminal-v4-001', '--status', 'completed', '--gate', 'PASS',
                  '--artifact', 'reviews/qa.md', '--evidence', 'command:synthetic finite arithmetic action exit=0',
                  '--started-at', '2026-10-19T00:01:00Z', '--updated-at', '2026-10-19T00:01:00Z']
    result = cli(item, *options(budget), *settlement)
    assert result.returncode == 0, result.stderr
    after = (item / 'agent-runs.jsonl').read_bytes()
    assert after.startswith(before) and len(after.splitlines()) == 4102
    replay = cli(item, *options(budget), *settlement)
    assert replay.returncode == 0 and 'already-settled' in replay.stdout, replay.stderr
    assert (item / 'agent-runs.jsonl').read_bytes() == after
    observation = v._obligations_observation(item, None, False, {}, ledger_resource_budget=budget)
    assert observation['result'] == 'PASS', observation
    assert observation['obligations']['openLaunches'] == []
    assert [x['runId'] for x in observation['obligations']['openRevises']] == ['synthetic-review-v4-001']
    assert 'synthetic historical action' not in json.dumps(observation)
    assert observation == v._obligations_observation(item, None, False, {}, ledger_resource_budget=budget)
    assert hashlib.sha256(after).hexdigest() == observation['ledgerSha256']
    # An independently admitted synthetic gate produces bounded intervening growth.
    gate_args = ['append', '--run-id', 'synthetic-independent-gate-v4', '--role', 'qa-engineer',
                 '--execution-role', 'internal', '--status', 'completed', '--gate', 'PASS',
                 '--event-kind', 'standalone', '--scope', 'distinct synthetic accepted gate',
                 '--artifact', 'reviews/qa.md', '--evidence', 'manual-check:separate substantive acceptance']
    gate = cli(item, *options(capacity), *gate_args)
    assert gate.returncode == 0, gate.stderr[:1500]
    # Resume uses actual growth and reselects before dispatch, without a failed default attempt.
    grown = v.inspect_ledger_resource_demand(item / 'agent-runs.jsonl', capacity, unknown_terminal_rows=2)
    assert grown.selected_events == 4103 and grown.selected_sha256 != demand.selected_sha256
    with pytest.raises(ValueError, match='WI-LEDGER-RESOURCE-INCOMPLETE'):
        v.resolve_ledger_resource_budget(budget.max_events, budget.max_ledger_bytes, demand=grown, managed=True)
    v.resolve_ledger_resource_budget(capacity.max_events, capacity.max_ledger_bytes, demand=grown, managed=True)
    valid_grown = (item / 'agent-runs.jsonl').read_bytes()
    (item / 'agent-runs.jsonl').write_bytes(valid_grown + b'{bad}\n')
    invalid = cli(item, *options(capacity), *settlement)
    assert invalid.returncode != 0 and 'invalid JSON' in invalid.stderr
    assert (item / 'agent-runs.jsonl').read_bytes() == valid_grown + b'{bad}\n'
    assert not list(item.glob('*.lock')) and not list(item.glob('*.tmp'))


def test_resource_and_late_invalid_suffix_fail_closed_even_on_settlement_noop(tmp_path):
    v = owner('validate-work-item-state.py')
    item, before = fixture(tmp_path, 3)
    ledger = item / 'agent-runs.jsonl'
    errors, complete = [], []
    assert v.load_jsonl(ledger, errors, source_bytes=before,
                       ledger_resource_budget=v.LedgerResourceBudgetV1(2, len(before)),
                       ledger_acquisition_complete_out=complete) == []
    assert complete == [False] and any('WI-LEDGER-RESOURCE-INCOMPLETE' in e for e in errors)
    assert not any('corrupt' in e for e in errors)
    ledger.write_bytes(before + b'{bad}\n' * 20)
    errors, complete = [], []
    v.load_jsonl(ledger, errors, ledger_resource_budget=v.LedgerResourceBudgetV1(4, 100000),
                 ledger_acquisition_complete_out=complete)
    assert complete == [False] and len(errors) <= 3
    assert any('invalid JSON' in e for e in errors)
    assert any('WI-LEDGER-RESOURCE-INCOMPLETE' in e for e in errors)
    assert ledger.read_bytes() == before + b'{bad}\n' * 20
    assert not list(item.glob('*.lock')) and not list(item.glob('*.tmp'))


@pytest.mark.parametrize('value', [0, -1, True, 1.5, '3'])
def test_budget_rejects_nonpositive_noninteger_and_boolean(value):
    v = owner('validate-work-item-state.py')
    with pytest.raises(ValueError, match='WI-LEDGER-RESOURCE'):
        v.LedgerResourceBudgetV1(value, 100)


def test_managed_missing_insufficient_growth_and_byte_guard(tmp_path):
    v = owner('validate-work-item-state.py')
    item, before = fixture(tmp_path, 3)
    cap = v.LedgerResourceBudgetV1(10, len(before) + 300000)
    demand = v.inspect_ledger_resource_demand(item / 'agent-runs.jsonl', cap, unknown_terminal_rows=2)
    for kwargs in ({}, {'max_events': 4, 'max_ledger_bytes': cap.max_ledger_bytes}):
        with pytest.raises(ValueError, match='WI-LEDGER-RESOURCE'):
            v.resolve_ledger_resource_budget(**kwargs, managed=True, demand=demand)
    errors, complete = [], []
    assert v.load_jsonl(item / 'agent-runs.jsonl', errors, source_bytes=before,
                       ledger_resource_budget=v.LedgerResourceBudgetV1(10, 5),
                       ledger_acquisition_complete_out=complete) == []
    assert complete == [False] and 'WI-LEDGER-RESOURCE-INCOMPLETE' in errors[0]
    with pytest.raises(ValueError, match='WI-LEDGER-RESOURCE-DRIFT'):
        v.inspect_ledger_resource_demand(item / 'agent-runs.jsonl', cap, expected_sha256='0' * 64)


def test_h1_physical_count_is_distinct_and_diagnostic_default_is_incomplete(tmp_path):
    v = owner('validate-work-item-state.py')
    item, before = fixture(tmp_path)
    errors, complete = [], []
    assert v.load_jsonl(item / 'agent-runs.jsonl', errors, source_bytes=before,
                       ledger_acquisition_complete_out=complete) == []
    assert complete == [False] and 'WI-LEDGER-RESOURCE-INCOMPLETE' in errors[-1]
    errors, complete = [], []
    v._ledger_h1_parse_lines(b'{}\n\n', 'synthetic-h1', errors,
                            ledger_resource_budget=v.LedgerResourceBudgetV1(1, 100),
                            ledger_acquisition_complete_out=complete)
    assert complete == [False] and 'WI-LEDGER-RESOURCE-INCOMPLETE' in errors[0]


def test_wrapper_admission_carries_context_and_complete_terminal_readback(tmp_path, monkeypatch, capsys):
    """Synthetic wrapper transport using actual local public support commands.

    The simulated external outcome is not external-provider functional proof.
    """
    p = owner('provider_prompt.py')
    v = owner('validate-work-item-state.py')
    item, before = fixture(tmp_path)
    cap = v.LedgerResourceBudgetV1(4200, len(before) + 400000)
    control = p.Control(ledger=str(item), ledger_max_events=cap.max_events,
                        ledger_max_bytes=cap.max_ledger_bytes)
    args = ['--work-item', str(item), 'append', '--run-id', 'synthetic-wrapper-launch-v4',
            '--role', 'external-reviewer', '--execution-role', 'external-reviewer',
            '--assigned-role', 'qa-engineer', '--provider', 'codex', '--model', 'gpt-5.6-sol',
            '--effort', 'high', '--status', 'running', '--gate', 'none',
            '--scope', 'synthetic-wrapper-transport', '--event-kind', 'launch',
            '--started-at', '2026-10-19T00:00:00Z', '--updated-at', '2026-10-19T00:00:00Z']
    selected = p.prepare_ledger_admission(control, args)
    assert (selected.max_events, selected.max_ledger_bytes) == (cap.max_events, cap.max_ledger_bytes)
    original_env = p._runner_support_environment
    monkeypatch.setattr(p, '_runner_support_environment',
                        lambda env: {**original_env(env), 'PYTHONDONTWRITEBYTECODE': '1'})
    assert Path(p.__file__).resolve().is_relative_to(ROOT)
    assert Path(sys.modules[p.ProcessRunnerV1.__module__].__file__).resolve().is_relative_to(ROOT)
    with p.ProcessRunnerV1() as runner:
        assert p.run_ledger(runner, [*p.ledger_resource_options(control), *args])
        terminal = ['--work-item', str(item), *p.ledger_resource_options(control), 'settle-launch',
                    '--launch-run-id', 'synthetic-wrapper-launch-v4', '--run-id', 'synthetic-wrapper-result-v4',
                    '--status', 'completed', '--gate', 'PASS', '--artifact', 'reviews/qa.md',
                    '--evidence', 'manual-check:declared synthetic transport result',
                    '--terminal-class', 'external-nonauthorizing', '--authorizing', 'false',
                    '--actual-execution-path', 'direct-external-cli', '--artifact-identity', 'synthetic-v4',
                    '--started-at', '2026-10-19T00:01:00Z', '--updated-at', '2026-10-19T00:01:00Z']
        assert p.run_ledger(runner, terminal)
    ledger = item / 'agent-runs.jsonl'
    after = ledger.read_bytes()
    row = p.read_back_external_terminal(control, 'codex', 'synthetic-wrapper-launch-v4')
    assert row['runId'] == 'synthetic-wrapper-result-v4'
    assert p.read_back_external_terminal(control, 'codex', 'synthetic-wrapper-launch-v4') == row
    assert ledger.read_bytes() == after and after.startswith(before)
    assert len(after.splitlines()) == 4102
    control.ledger_max_events += 1
    with pytest.raises(ValueError, match='WI-LEDGER-RESOURCE-DRIFT'):
        p.ledger_resource_options(control)
    assert p.read_back_external_terminal(control, 'codex', 'synthetic-wrapper-launch-v4') is None
    control.ledger_max_events -= 1
    terminal_bytes = after.splitlines(keepends=True)[-1]
    ledger.write_bytes(after + terminal_bytes)
    assert p.read_back_external_terminal(control, 'codex', 'synthetic-wrapper-launch-v4') is None
    conflict = cli(item, *options(cap), 'rollup', '--json')
    assert conflict.returncode != 0 and 'duplicate' in conflict.stderr.lower()
    ledger.write_bytes(after + b'{bad}\n')
    assert p.read_back_external_terminal(control, 'codex', 'synthetic-wrapper-launch-v4') is None
    result = cli(item, *options(cap), 'rollup', '--json')
    assert json.loads(result.stdout)['malformedLines'] == 1
    # Missing managed admission refuses before the first writer/host call.
    with pytest.raises(ValueError, match='WI-LEDGER-RESOURCE-MISSING'):
        p.prepare_ledger_admission(p.Control(ledger=str(item)), args)
    with p.ProcessRunnerV1() as runner:
        assert not p.run_ledger(runner, ['--work-item', str(item), 'rollup'])
    assert 'WI-LEDGER-RESOURCE-INCOMPLETE' in capsys.readouterr().err


def test_release_binding_direct_and_capture_paths_share_budget(tmp_path):
    v = owner('validate-work-item-state.py')
    m = owner('mutate-work-item.py')
    item, before = fixture(tmp_path)
    # A validly framed synthetic terminal with no retained entry refuses the
    # identity requirement only after complete acquisition in both branches.
    budget = v.LedgerResourceBudgetV1(4200, len(before) + 10000)
    for event_out in (None, []):
        with pytest.raises(m.LifecycleError, match='one exact terminal'):
            m._release_event_binding(item, 'synthetic-no-terminal', 'synthetic-entry',
                                     event_out=event_out, ledger_resource_budget=budget)
        with pytest.raises(m.LifecycleError, match='WI-LEDGER-RESOURCE-INCOMPLETE'):
            m._release_event_binding(item, 'synthetic-no-terminal', 'synthetic-entry', event_out=event_out)


def test_complete_h1_group_charges_all_participants_before_receiving(tmp_path):
    from test_ledger_h1_effective_view import synthetic_artifacts, materialize_live_artifacts
    v = owner('validate-work-item-state.py')
    artifacts, items, paths, _expected = synthetic_artifacts(v, tmp_path)
    total_bytes = sum(map(len, artifacts.ledger_bytes_by_path.values()))
    total_lines = sum(raw.count(b'\n') for raw in artifacts.ledger_bytes_by_path.values())
    budget = v.LedgerResourceBudgetV1(total_lines, total_bytes)
    contexts = v._load_effective_ledger_group(tmp_path, compatibility_artifacts=artifacts,
                                             ledger_resource_budget=budget)
    assert all(context.observation.activation_state == 'active' for context in contexts.values())
    incomplete = v._load_effective_ledger_group(
        tmp_path, compatibility_artifacts=artifacts,
        ledger_resource_budget=v.LedgerResourceBudgetV1(total_lines, total_bytes - 1))
    assert set(incomplete) == set(paths)
    assert all(context.view is None for context in incomplete.values())
    assert all('WI-LEDGER-RESOURCE-INCOMPLETE' in ' '.join(context.observation.diagnostics)
               for context in incomplete.values())
    materialize_live_artifacts(tmp_path, artifacts)
    observed = v._obligations_observation(items[0], None, False, {}, ledger_resource_budget=budget)
    assert observed['obligations'] is not None, observed
    refused = v._obligations_observation(
        items[0], None, False, {},
        ledger_resource_budget=v.LedgerResourceBudgetV1(total_lines, total_bytes - 1))
    assert refused['result'] == 'FAIL' and refused['obligations'] is None
    assert 'WI-LEDGER-RESOURCE-INCOMPLETE' in ' '.join(refused['diagnostics'])


def test_known_batch_is_finite_and_one_record_and_large_finite_allowance_is_not_io_overflow(tmp_path):
    v = owner('validate-work-item-state.py')
    item, before = fixture(tmp_path, 3)
    cap = v.LedgerResourceBudgetV1(100, 10**30)
    assert v.read_ledger_bytes(item / 'agent-runs.jsonl', cap) == before
    for rows in ((b'{}\n\n',), iter((b'{}\n',))):
        with pytest.raises(ValueError, match='WI-LEDGER-RESOURCE-INVALID'):
            v.inspect_ledger_resource_demand(item / 'agent-runs.jsonl', cap, known_row_bytes=rows)


@pytest.mark.parametrize('ending', [b'\n', b'\r\n', b''])
def test_ordinary_metadata_preserves_physical_ordinals_and_body_digest(tmp_path, ending):
    v = owner('validate-work-item-state.py')
    raw = b'{"synthetic":1}' + ending
    path = tmp_path / 'agent-runs.jsonl'
    path.write_bytes(raw)
    errors, metadata, complete = [], [], []
    events = v.load_jsonl(path, errors, metadata, ledger_resource_budget=v.LedgerResourceBudgetV1(1, len(raw)),
                         ledger_acquisition_complete_out=complete)
    assert not errors and complete == [True] and events == [{'synthetic': 1}]
    assert metadata == [{'line': 1, 'sha256': hashlib.sha256(b'{"synthetic":1}').hexdigest(), 'bytes': 15}]
    assert path.read_bytes() == raw
