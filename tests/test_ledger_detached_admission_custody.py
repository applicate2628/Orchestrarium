"""Actual detached caller boundaries and existing metadata policy, synthetic inputs."""
import json
from pathlib import Path

import pytest

from test_ledger_resource_budget import cli, owner
from test_agent_run_ledger import prepare_valid_work_item


def closed_transfer(tmp_path):
    import test_legacy_obligation_migration as transfer
    fixture = transfer.native_transfer_fixture(tmp_path)
    transfer.append_reviewer_pass(fixture['item'],
        {'targetRunId': fixture['transferObject']['obligations'][0]['runId']})
    fixture['ledgerBefore'] = (fixture['item'] / 'agent-runs.jsonl').read_bytes()
    fixture['ledgerSha'] = transfer.sha256(fixture['ledgerBefore'])
    fixture['transferObject']['expectedSourceLedgerSha256'] = fixture['ledgerSha']
    fixture['transferObject']['obligations'] = []
    fixture['transfer'] = json.dumps(fixture['transferObject'], sort_keys=True).encode()
    receipt = transfer.run_transfer(fixture)
    active = fixture['lifecycle'].start_item(tmp_path, fixture['successorSlug'],
        transfer.successor_status(fixture['slug'], fixture['operationId']))
    writer = owner('agent-run-ledger.py')
    validator = writer.load_validator()
    lifecycle = validator.load_lifecycle_owner()
    assert lifecycle._CURRENT_LIFECYCLE_TRANSACTION.get() is None
    assert validator.validate_work_item(active, strict_revise=False) == []
    return writer, validator, lifecycle, active, tmp_path / receipt['archivePath'] / 'agent-runs.jsonl'


def swap_identical(path, lifecycle):
    initial = lifecycle._capture_file_snapshot(path, failure_id='TEST-INITIAL',
        maximum_bytes=None, require_single_link=True)
    path.rename(path.with_name(path.name + '.original'))
    path.write_bytes(initial.data)
    current = lifecycle._capture_file_snapshot(path, failure_id='TEST-REPLACED',
        maximum_bytes=None, require_single_link=True)
    assert current.identity != initial.identity and current.data == initial.data


def standalone(writer, validator, item):
    arguments = writer.build_parser().parse_args(['--work-item', str(item), 'append',
        '--run-id', 'detached-custody-probe', '--role', 'analyst', '--execution-role', 'internal',
        '--status', 'completed', '--gate', 'none', '--event-kind', 'standalone',
        '--scope', 'synthetic accepted action', '--evidence', 'manual-check:synthetic action'])
    return writer.build_event(arguments, validator)


def assert_no_writer_residue(item, before):
    assert (item / 'agent-runs.jsonl').read_bytes() == before
    assert not (item / 'agent-runs.jsonl.lock').exists()
    assert not (item / 'agent-runs.jsonl.tmp').exists()


def test_detached_append_rejects_same_byte_ancestor_after_receiving(tmp_path):
    writer, validator, lifecycle, item, ancestor = closed_transfer(tmp_path)
    before = (item / 'agent-runs.jsonl').read_bytes()
    event = standalone(writer, validator, item)
    reached = []
    def replace():
        reached.append(True)
        swap_identical(ancestor, lifecycle)
    with pytest.raises(ValueError, match='WI-LEDGER-RESOURCE-DRIFT'):
        writer._append_event_transaction(item, validator, lambda previous: event, before_replace=replace)
    assert reached == [True]
    assert_no_writer_residue(item, before)


def test_detached_replay_rejects_same_byte_ancestor_after_receiving(tmp_path, monkeypatch):
    writer, validator, lifecycle, item, ancestor = closed_transfer(tmp_path)
    event = standalone(writer, validator, item)
    assert writer._append_event_transaction(item, validator, lambda previous: event) is True
    before = (item / 'agent-runs.jsonl').read_bytes()
    receive, reached = writer._receive_append_operation, []
    def receive_then_replace(*args, **kwargs):
        result = receive(*args, **kwargs)
        reached.append(True)
        swap_identical(ancestor, lifecycle)
        return result
    monkeypatch.setattr(writer, '_receive_append_operation', receive_then_replace)
    with pytest.raises(ValueError, match='WI-LEDGER-RESOURCE-DRIFT'):
        writer._append_event_transaction(item, validator, lambda previous: None,
            _replay_run_id=event['runId'])
    assert reached == [True]
    assert_no_writer_residue(item, before)


def test_detached_readback_rejects_ancestor_replacement_after_admission(tmp_path, monkeypatch):
    writer, validator, lifecycle, item, ancestor = closed_transfer(tmp_path)
    (item / 'target.md').write_text('Synthetic accepted local result.\n', encoding='utf-8')
    launch = cli(item, 'append', '--run-id', 'detached-external-launch', '--role', 'external-reviewer',
        '--execution-role', 'external-reviewer', '--assigned-role', 'qa-engineer', '--provider', 'codex',
        '--model', 'gpt-6.1-sol', '--effort', 'high', '--status', 'running', '--gate', 'none',
        '--event-kind', 'launch', '--scope', 'synthetic local transport',
        '--started-at', '2026-10-19T00:00:00Z', '--updated-at', '2026-10-19T00:00:00Z')
    assert launch.returncode == 0, launch.stdout + launch.stderr
    terminal = cli(item, 'settle-launch', '--launch-run-id', 'detached-external-launch',
        '--run-id', 'detached-external-terminal', '--status', 'completed', '--gate', 'PASS',
        '--artifact', 'target.md', '--evidence', 'manual-check:synthetic local transport',
        '--terminal-class', 'external-nonauthorizing', '--authorizing', 'false',
        '--actual-execution-path', 'direct-external-cli', '--artifact-identity', 'synthetic-detached',
        '--started-at', '2026-10-19T00:01:00Z', '--updated-at', '2026-10-19T00:01:00Z')
    assert terminal.returncode == 0, terminal.stdout + terminal.stderr
    provider = owner('provider_prompt.py')
    monkeypatch.setattr(provider, '_ledger_owner', lambda: writer)
    monkeypatch.setattr(writer, 'load_validator', lambda: validator)
    control = provider.Control(ledger=str(item))
    assert provider.read_back_external_terminal(control, 'codex', 'detached-external-launch') is not None
    before = (item / 'agent-runs.jsonl').read_bytes()
    admit, reached = lifecycle._admit_ledger_operation, []
    def admit_then_replace(*args, **kwargs):
        result = admit(*args, **kwargs)
        reached.append(True)
        swap_identical(ancestor, lifecycle)
        return result
    monkeypatch.setattr(lifecycle, '_admit_ledger_operation', admit_then_replace)
    assert provider.read_back_external_terminal(control, 'codex', 'detached-external-launch') is None
    assert reached == [True]
    assert_no_writer_residue(item, before)


def test_absent_transfer_relation_remains_required_at_detached_placement(tmp_path):
    item = prepare_valid_work_item(tmp_path)
    (item / 'agent-runs.jsonl').write_bytes(b'')
    writer = owner('agent-run-ledger.py')
    validator = writer.load_validator()
    lifecycle = validator.load_lifecycle_owner()
    status = item / 'status.md'
    assert validator._transfer_status_relation(item, []) is None
    event = standalone(writer, validator, item)
    before = (item / 'agent-runs.jsonl').read_bytes()
    with pytest.raises(ValueError, match='WI-LEDGER-RESOURCE-DRIFT'):
        writer._append_event_transaction(item, validator, lambda previous: event,
            before_replace=lambda: swap_identical(status, lifecycle))
    assert_no_writer_residue(item, before)


@pytest.mark.parametrize('changed_input', ['primary-ledger', 'status-without-transfer'])
def test_detached_staging_rechecks_original_inputs_after_candidate_cleanup(tmp_path, monkeypatch, changed_input):
    import test_legacy_obligation_migration as migration
    item, expected = migration.copied_fixture(tmp_path)
    status = item / 'status.md'
    if not status.exists():
        status.write_bytes(b'Task: Synthetic migration staging.\n')
    writer = owner('agent-run-ledger.py')
    validator = writer.load_validator()
    lifecycle = validator.load_lifecycle_owner()
    ledger = item / 'agent-runs.jsonl'
    before = ledger.read_bytes()
    arguments = (item, expected['targetRunId'], expected['targetRawSha256'], migration.sha256(before),
                 'detached-stage-probe', '2026-08-18T00:00:00Z', 'invalid-finding-class')
    assert writer.stage_legacy_obligation_migration(*arguments, _validator=validator).staged_bytes.startswith(before)
    unlink, reached = Path.unlink, []
    def cleanup_then_replace(path, *args, **kwargs):
        result = unlink(path, *args, **kwargs)
        if path.parent == item and path.name.startswith('.ledger-migration-'):
            reached.append(True)
            swap_identical(ledger if changed_input == 'primary-ledger' else status, lifecycle)
        return result
    monkeypatch.setattr(Path, 'unlink', cleanup_then_replace)
    with pytest.raises((writer.LedgerMigrationError, lifecycle.LifecycleError)) as failed:
        writer.stage_legacy_obligation_migration(*arguments, _validator=validator)
    assert reached == [True]
    assert failed.value.failure_id in {'WI-LEDGER-MIGRATION-LEDGER-DRIFT', 'WI-LEDGER-RESOURCE-DRIFT'}
    assert ledger.read_bytes() == before and not list(item.glob('.ledger-migration-*'))


@pytest.mark.parametrize('selected_status', ['primary', 'h1-participant'])
def test_status_metadata_policy_and_complete_negative_selection(tmp_path, selected_status):
    validator = owner('validate-work-item-state.py')
    lifecycle = validator.load_lifecycle_owner()
    if selected_status == 'primary':
        item = prepare_valid_work_item(tmp_path)
        ledger = item / 'agent-runs.jsonl'
        ledger.write_bytes(b'{}\n')
        status = item / 'status.md'
    else:
        from test_ledger_h1_effective_view import synthetic_artifacts, materialize_live_artifacts
        artifacts, items, paths, expected = synthetic_artifacts(validator, tmp_path)
        materialize_live_artifacts(tmp_path, artifacts)
        item, status = items[0], items[1] / 'status.md'
        ledger = item / 'agent-runs.jsonl'
    status.write_bytes(b'Task: Synthetic metadata policy.\n' + b' ' * 8192)
    budget, predicates = lifecycle._admit_ledger_operation(item, ledger, ledger.read_bytes(), validator=validator)
    assert status.stat().st_size > budget.max_ledger_bytes
    selected = [predicate for predicate in predicates if predicate.path == status]
    assert selected and all(predicate.snapshot is not None and predicate.qualify() for predicate in selected)
    status.write_bytes(b'Task: Synthetic metadata policy.\n' + b' ' * (4 * 1024 * 1024))
    with pytest.raises(lifecycle.LifecycleError):
        lifecycle._admit_ledger_operation(item, ledger, ledger.read_bytes(), validator=validator)
