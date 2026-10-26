"""Input-derived public admission on synthetic history; never provider execution."""
import hashlib
import json
import subprocess
import sys

import pytest

from test_ledger_resource_budget import ROOT, cli, fixture, owner


def launch(item):
    return cli(item, 'append', '--run-id', 'derived-launch', '--role', 'backend-engineer',
               '--execution-role', 'internal', '--status', 'running', '--gate', 'none',
               '--scope', 'synthetic omission admission', '--event-kind', 'launch',
               '--started-at', '2026-10-19T00:00:00Z', '--updated-at', '2026-10-19T00:00:00Z')


def test_public_omission_launch_interleaving_terminal_replay_and_observation(tmp_path):
    item, before = fixture(tmp_path)
    result = launch(item)
    assert result.returncode == 0, result.stdout + result.stderr
    independent = cli(item, 'append', '--run-id', 'derived-independent', '--role', 'analyst',
                      '--execution-role', 'internal', '--status', 'completed', '--gate', 'none',
                      '--event-kind', 'standalone', '--scope', 'independent actual synthetic action',
                      '--evidence', 'manual-check:independent admitted test action')
    assert independent.returncode == 0, independent.stdout + independent.stderr
    settlement = ['settle-launch', '--launch-run-id', 'derived-launch', '--run-id', 'derived-terminal',
                  '--status', 'completed', '--gate', 'PASS', '--artifact', 'reviews/qa.md',
                  '--evidence', 'manual-check:synthetic accepted result',
                  '--started-at', '2026-10-19T00:01:00Z', '--updated-at', '2026-10-19T00:01:00Z']
    result = cli(item, *settlement)
    assert result.returncode == 0, result.stdout + result.stderr
    ledger = item / 'agent-runs.jsonl'
    after = ledger.read_bytes()
    assert after.startswith(before) and len(after.splitlines()) == 4103
    replay = cli(item, *settlement)
    assert replay.returncode == 0 and 'already-settled' in replay.stdout, replay.stdout + replay.stderr
    assert ledger.read_bytes() == after
    observed = subprocess.run([sys.executable, '-X', 'utf8', '-B',
        str(ROOT / 'scripts/validate-work-item-state.py'), '--work-item', str(item),
        '--obligations-json', '--no-strict-revise'], cwd=ROOT, capture_output=True, text=True, timeout=30)
    payload = json.loads(observed.stdout)
    assert observed.returncode == 0, payload
    assert payload['ledgerSha256'] == hashlib.sha256(after).hexdigest()
    assert payload['obligations']['openLaunches'] == []
    ledger.write_bytes(after + b'{bad}\n')
    invalid = cli(item, *settlement)
    assert invalid.returncode != 0 and 'invalid JSON' in invalid.stderr
    assert ledger.read_bytes() == after + b'{bad}\n'
    assert not list(item.glob('*.lock')) and not list(item.glob('*.tmp'))


def test_explicit_cap_and_partial_pair_remain_refusals(tmp_path):
    item, before = fixture(tmp_path)
    for flags in (['--ledger-max-events', '4096', '--ledger-max-bytes', str(len(before) + 1000000)],
                  ['--ledger-max-events', '5000'],
                  ['--ledger-max-events', '0', '--ledger-max-bytes', '100']):
        result = cli(item, *flags, 'rollup', '--json')
        assert result.returncode != 0 and 'WI-LEDGER-RESOURCE' in result.stdout + result.stderr
        assert (item / 'agent-runs.jsonl').read_bytes() == before


def test_public_multigeneration_start_keeps_preparatory_omission(tmp_path, monkeypatch):
    import test_legacy_obligation_migration as migration
    created = []
    original = migration.transfer_fixture
    def capture(*args, **kwargs):
        value = original(*args, **kwargs)
        created.append(value)
        return value
    monkeypatch.setattr(migration, 'transfer_fixture', capture)
    migration.test_archive_with_successor_transfer_exactly_once_across_activation_close_and_retransfer(tmp_path)
    first = created[0]
    module = first['lifecycle']
    archive = tmp_path / 'work-items/archive/2026-08' / first['slug']
    previous = tmp_path / 'work-items/archive/2026-08' / first['successorSlug']
    before = {path: path.read_bytes() for item in (archive, previous)
              for path in item.iterdir() if path.is_file()}
    successor = module.start_item(tmp_path, first['successorSlug'] + '-next',
        migration.successor_status(first['successorSlug'], 'transition-transfer-op-002'))
    validator = module._validator_module()
    states, acquired = [], []
    errors = validator.validate_work_item(successor, strict_revise=False,
        obligation_state_out=states, ledger_acquisition_complete_out=acquired)
    inherited_run = first['transferObject']['obligations'][0]['runId']
    inherited_event = next(json.loads(row) for row in first['ledgerBefore'].splitlines()
                           if json.loads(row).get('runId') == inherited_run)
    expected = (f"{inherited_run}: launchRunId {inherited_event['launchRunId']} "
                'does not reference an earlier event')
    assert errors == [expected] and acquired == [True]
    assert len(states) == 1 and len(states[0].open_revise) == 1
    assert states[0].open_revise[0].obligation_id
    module.audit(tmp_path)
    assert all(path.read_bytes() == raw for path, raw in before.items())


def test_public_close_and_immutable_replay_above_diagnostic_cap(tmp_path, monkeypatch):
    from test_mutate_work_item import _seed_ordinary_ledger_close, closure
    module, root, item, instant = _seed_ordinary_ledger_close(tmp_path)
    ledger = item / 'agent-runs.jsonl'
    first = json.loads(ledger.read_bytes())
    before = b''.join(json.dumps({**first, 'runId': f'derived-close-{n}'}).encode() + b'\n'
                      for n in range(4100))
    ledger.write_bytes(before)
    original_validate = module._validate_item_before_close
    held_pairs = []
    def checked_validate(selected, *, ledger_resource_budget=None):
        held = module._CURRENT_LIFECYCLE_TRANSACTION.get().ledger_resource_budget
        assert held is not None and ledger_resource_budget is held
        held_pairs.append((held.max_events, held.max_ledger_bytes))
        return original_validate(selected, ledger_resource_budget=ledger_resource_budget)
    monkeypatch.setattr(module, '_validate_item_before_close', checked_validate)
    archive = module.close_item(root, item.name, closure(instant).encode(), instant)
    assert held_pairs == [(4100, len(before))]
    assert (archive / 'agent-runs.jsonl').read_bytes() == before
    receipt = (archive / 'lifecycle-transition-receipt.json').read_bytes()
    assert not item.exists()
    assert module.close_item(root, item.name, closure(instant).encode(), instant) == archive
    assert (archive / 'lifecycle-transition-receipt.json').read_bytes() == receipt


def test_omitted_wrapper_does_not_transport_a_guessed_pair(tmp_path):
    p = owner('provider_prompt.py')
    item, before = fixture(tmp_path)
    control = p.Control(ledger=str(item))
    args = ['--work-item', str(item), 'append', '--run-id', 'derived-wrapper-launch',
            '--role', 'backend-engineer', '--execution-role', 'internal', '--status', 'running',
            '--gate', 'none', '--scope', 'synthetic omitted wrapper transport', '--event-kind', 'launch']
    assert p.prepare_ledger_admission(control, args) is None
    assert p.ledger_resource_options(control) == []
    assert control.resolved_ledger_budget is None
    assert (item / 'agent-runs.jsonl').read_bytes() == before


def test_automatic_h1_group_counts_every_participant(tmp_path):
    from test_ledger_h1_effective_view import synthetic_artifacts
    v = owner('validate-work-item-state.py')
    artifacts, _items, paths, _expected = synthetic_artifacts(v, tmp_path)
    contexts = v._load_effective_ledger_group(tmp_path, compatibility_artifacts=artifacts)
    assert set(contexts) == set(paths)
    assert all(context.observation.activation_state == 'active' for context in contexts.values())


def test_descriptor_derived_ledger_capture_keeps_generic_capture_guard(tmp_path):
    v = owner('validate-work-item-state.py')
    m = v.load_lifecycle_owner()
    ledger = tmp_path / 'agent-runs.jsonl'
    # Selected bytes exceed the independent generic 4 MiB capture limit.
    raw = b'{"synthetic":1}\n' * 280000
    ledger.write_bytes(raw)
    assert v.read_ledger_bytes(ledger) == raw
    with pytest.raises(m.LifecycleError):
        m._capture_file_snapshot(ledger, failure_id='synthetic-generic-capture')
    with pytest.raises(m.LifecycleError):
        m._ledger_location_regular_sha256(ledger, failure_id='synthetic-generic-hash')
    assert m._ledger_location_regular_sha256(ledger, failure_id='synthetic-ledger-hash',
        ledger_input=True) == hashlib.sha256(raw).hexdigest()
    captured = m._capture_file_snapshot(ledger, failure_id='synthetic-ledger-capture', maximum_bytes=None)
    assert captured.data == raw
    ledger.write_bytes(raw[:-1] + b'x')
    with pytest.raises(m.LifecycleError):
        m._verify_captured_file(captured, 'WI-LEDGER-RESOURCE-DRIFT')


def test_first_launch_derives_two_final_rows_from_empty_acquisition(tmp_path):
    from test_agent_run_ledger import prepare_valid_work_item
    item = prepare_valid_work_item(tmp_path)
    result = launch(item)
    assert result.returncode == 0, result.stdout + result.stderr
    rows = (item / 'agent-runs.jsonl').read_bytes().splitlines()
    assert len(rows) == 1 and json.loads(rows[0])['eventKind'] == 'launch'


def test_automatic_h1_admission_binds_complete_large_group(tmp_path):
    import dataclasses
    from test_ledger_h1_effective_view import synthetic_artifacts, materialize_live_artifacts, event, ledger_bytes
    v = owner('validate-work-item-state.py')
    artifacts, items, paths, _expected = synthetic_artifacts(v, tmp_path)
    images = {path: raw + ledger_bytes([event(f'joint-{index}-{n}', items[index].name,
                   eventKind='standalone') for n in range(2100)])
              for index, (path, raw) in enumerate(artifacts.ledger_bytes_by_path.items())}
    artifacts = dataclasses.replace(artifacts, ledger_bytes_by_path=images)
    materialize_live_artifacts(tmp_path, artifacts)
    m = v.load_lifecycle_owner()
    selected = items[0] / 'agent-runs.jsonl'
    raw = selected.read_bytes()
    budget, inputs = m._admit_ledger_operation(items[0], selected, raw, validator=v)
    assert budget.max_events == sum(image.count(b'\n') for image in images.values())
    assert budget.max_events > 4096
    assert budget.max_ledger_bytes == (sum(map(len, images.values()))
        + sum(map(len, artifacts.historical_wire_bytes_by_path.values())))
    assert inputs and all(predicate.qualify() for predicate in inputs)
    (items[1] / 'agent-runs.jsonl').unlink()
    with pytest.raises(m.LifecycleError):
        m._admit_ledger_operation(items[0], selected, raw, validator=v)
    assert selected.read_bytes() == raw


def test_checker_omission_preserves_complete_history(tmp_path):
    item, before = fixture(tmp_path)
    status = item / 'status.md'
    status.write_text('Status: active\n' + status.read_text(encoding='utf-8'), encoding='utf-8')
    result = subprocess.run([sys.executable, '-X', 'utf8', '-B',
        str(ROOT / 'scripts/check-work-items-state.py'), '--root', str(tmp_path),
        '--active-only', '--no-strict-revise'], cwd=ROOT, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (item / 'agent-runs.jsonl').read_bytes() == before


def test_replay_refuses_same_size_change_after_receiving(tmp_path, monkeypatch):
    writer = owner('agent-run-ledger.py')
    v = writer.load_validator()
    item, before = fixture(tmp_path, 3)
    changed = before.replace(b'synthetic-history-v4-00000', b'synthetic-history-v4-99999', 1)
    assert len(changed) == len(before) and changed != before
    original_receive = writer._receive_append_operation
    def receive_then_change(*args, **kwargs):
        result = original_receive(*args, **kwargs)
        (item / 'agent-runs.jsonl').write_bytes(changed)
        return result
    monkeypatch.setattr(writer, '_receive_append_operation', receive_then_change)
    with pytest.raises(ValueError, match='WI-LEDGER-RESOURCE-DRIFT'):
        writer._append_event_transaction(item, v, lambda _previous: None)
    assert (item / 'agent-runs.jsonl').read_bytes() == changed
    assert not list(item.glob('*.lock')) and not list(item.glob('*.tmp'))


def test_wrapper_implicit_readback_receives_complete_h1_group(tmp_path, monkeypatch):
    from test_agent_run_ledger import valid_status
    from test_ledger_h1_effective_view import synthetic_artifacts, materialize_live_artifacts
    v = owner('validate-work-item-state.py')
    artifacts, items, _paths, _expected = synthetic_artifacts(v, tmp_path)
    materialize_live_artifacts(tmp_path, artifacts)
    item = items[0]
    (item / 'status.md').write_text('Status: active\n' + valid_status(), encoding='utf-8')
    (item / 'target.md').write_text('Synthetic local transport fixture only.\n', encoding='utf-8')
    before = (item / 'agent-runs.jsonl').read_bytes()
    launch = cli(item, 'append', '--run-id', 'synthetic-joint-wrapper-launch',
        '--role', 'external-reviewer', '--execution-role', 'external-reviewer',
        '--assigned-role', 'qa-engineer', '--provider', 'codex', '--model', 'gpt-6.1-sol',
        '--effort', 'high', '--status', 'running', '--gate', 'none', '--event-kind', 'launch',
        '--scope', 'declared synthetic local transport only',
        '--started-at', '2026-10-19T00:00:00Z', '--updated-at', '2026-10-19T00:00:00Z')
    assert launch.returncode == 0, launch.stdout + launch.stderr
    terminal = cli(item, 'settle-launch', '--launch-run-id', 'synthetic-joint-wrapper-launch',
        '--run-id', 'synthetic-joint-wrapper-terminal', '--status', 'completed', '--gate', 'PASS',
        '--artifact', 'target.md', '--evidence', 'manual-check:declared synthetic local transport only',
        '--terminal-class', 'external-nonauthorizing', '--authorizing', 'false',
        '--actual-execution-path', 'direct-external-cli', '--artifact-identity', 'synthetic-joint-wrapper',
        '--started-at', '2026-10-19T00:01:00Z', '--updated-at', '2026-10-19T00:01:00Z')
    assert terminal.returncode == 0, terminal.stdout + terminal.stderr
    p = owner('provider_prompt.py')
    received = p.read_back_external_terminal(p.Control(ledger=str(item)),
        'codex', 'synthetic-joint-wrapper-launch')
    assert received is not None and received['runId'] == 'synthetic-joint-wrapper-terminal'
    monkeypatch.chdir(tmp_path)
    relative = p.read_back_external_terminal(p.Control(ledger='work-items/active/reader-a'),
        'codex', 'synthetic-joint-wrapper-launch')
    assert relative is not None and relative['runId'] == received['runId']
    after = (item / 'agent-runs.jsonl').read_bytes()
    assert after.startswith(before) and len(after.splitlines()) == len(before.splitlines()) + 2


def test_successor_transfer_holds_source_capacity_before_preparing_effects(tmp_path, monkeypatch):
    from test_mutate_work_item import _seed_ordinary_ledger_close, closure
    module, root, item, instant = _seed_ordinary_ledger_close(tmp_path)
    ledger = item / 'agent-runs.jsonl'
    first = json.loads(ledger.read_bytes())
    before = b''.join(json.dumps({**first, 'runId': f'successor-input-{n}'}).encode() + b'\n'
                      for n in range(4100))
    ledger.write_bytes(before)
    ledger_sha = hashlib.sha256(before).hexdigest()
    readme_sha = hashlib.sha256((root / 'work-items/README.md').read_bytes()).hexdigest()
    successor = (f'Task: Continue the admitted synthetic task.\nContinues: {item.name}\n'
                 'Obligation-transfer: derived-successor-operation\nNext action: Review.\n'
                 f'updated: {instant}\n').encode()
    transfer = json.dumps({'schemaVersion': 1, 'sourceWorkItem': item.name,
        'successorWorkItem': 'derived-successor', 'expectedSourceLedgerSha256': ledger_sha,
        'obligations': []}).encode()
    original = module._prepare_obligation_transfer
    observed = []
    def checked(*args, ledger_resource_budget=None, **kwargs):
        held = module._CURRENT_LIFECYCLE_TRANSACTION.get().ledger_resource_budget
        assert held is not None and ledger_resource_budget is held
        observed.append((held.max_events, held.max_ledger_bytes))
        return original(*args, ledger_resource_budget=ledger_resource_budget, **kwargs)
    monkeypatch.setattr(module, '_prepare_obligation_transfer', checked)
    args = (root, item.name, closure(instant).encode(), instant, 'derived-successor', successor,
            'derived-successor-operation', ledger_sha, readme_sha)
    receipt = module.archive_with_successor(*args, obligation_transfer_data=transfer)
    assert observed == [(4100, len(before))]
    archive = root / receipt['archivePath']
    assert (archive / 'agent-runs.jsonl').read_bytes() == before
    assert module.archive_with_successor(*args, obligation_transfer_data=transfer) == receipt


def test_staged_start_holds_actual_serialization_before_first_effect(tmp_path, monkeypatch):
    from test_mutate_work_item import load_module, staged_status
    module = load_module()
    root = tmp_path / 'repo'
    slug = 'derived-staged-start'
    status = staged_status('2026-07-01-archived-concern').encode()
    module.create_candidate(root, slug, b'Task: Synthetic staged admission.\n')
    expected = module._staged_admission_ledger_bytes(slug, status)
    original = module._replace_lifecycle_directory
    observed = []
    def checked(*args, **kwargs):
        held = module._CURRENT_LIFECYCLE_TRANSACTION.get().ledger_resource_budget
        assert held is not None
        observed.append((held.max_events, held.max_ledger_bytes))
        return original(*args, **kwargs)
    monkeypatch.setattr(module, '_replace_lifecycle_directory', checked)
    target = module.start_item(root, slug, status)
    assert observed and all(pair == (1, len(expected)) for pair in observed)
    assert (target / 'agent-runs.jsonl').read_bytes() == expected


def test_supplied_h1_nonempty_wires_are_charged_before_admission(tmp_path):
    import dataclasses
    from test_ledger_h1_effective_view import _frozen_h1_inputs_current6a
    v = owner('validate-work-item-state.py')
    artifacts, wires, *_ = _frozen_h1_inputs_current6a(v, tmp_path, 'F-untyped-contradiction')
    artifacts = dataclasses.replace(artifacts, historical_wire_bytes_by_path=wires)
    events = sum(raw.count(b'\n') for raw in artifacts.ledger_bytes_by_path.values())
    byte_length = sum(map(len, artifacts.ledger_bytes_by_path.values())) + sum(map(len, wires.values()))
    for budget in (None, v.LedgerResourceBudgetV1(events, byte_length)):
        contexts = v._load_effective_ledger_group(tmp_path, compatibility_artifacts=artifacts,
            ledger_resource_budget=budget)
        assert contexts and all(context.view is not None for context in contexts.values())
    refused = v._load_effective_ledger_group(tmp_path, compatibility_artifacts=artifacts,
        ledger_resource_budget=v.LedgerResourceBudgetV1(events, byte_length - 1))
    assert all(context.view is None for context in refused.values())
    assert all('WI-LEDGER-RESOURCE-INCOMPLETE' in context.observation.failure_ids
               for context in refused.values())


def test_sealed_prefix_public_caps_and_one_held_complete_pair(tmp_path, monkeypatch):
    import test_ledger_h1_activation_writer as activation
    m, v, request, _items, paths = activation.fixture(tmp_path)
    before = {path.relative_to(tmp_path): path.read_bytes()
              for path in (tmp_path / 'work-items').rglob('*') if path.is_file()}
    insufficient = v.LedgerResourceBudgetV1(1, 1)
    with pytest.raises(m.LifecycleError) as apply_limit:
        m.apply_sealed_prefix_activation(tmp_path, request, ledger_resource_budget=insufficient)
    assert apply_limit.value.failure_id == 'WI-LEDGER-RESOURCE-INCOMPLETE'
    assert {path.relative_to(tmp_path): path.read_bytes()
            for path in (tmp_path / 'work-items').rglob('*') if path.is_file()} == before
    expected = (sum((tmp_path / path).read_bytes().count(b'\n') for path in paths),
                sum((tmp_path / path).stat().st_size for path in paths))
    original = m._sealed_prefix_inventory
    pairs = []
    def checked(root, plan, *, ledger_resource_budget=None):
        held = m._CURRENT_LIFECYCLE_TRANSACTION.get().ledger_resource_budget
        assert held is not None and ledger_resource_budget is held
        pairs.append((held.max_events, held.max_ledger_bytes))
        return original(root, plan, ledger_resource_budget=ledger_resource_budget)
    monkeypatch.setattr(m, '_sealed_prefix_inventory', checked)
    applied = m.apply_sealed_prefix_activation(tmp_path, request)
    receipt = tmp_path / applied['receiptPath']
    registry = tmp_path / 'work-items/legacy-ledger-projections.jsonl'
    revoke = m.SealedPrefixRevokeRequestV1(apply_receipt_path=applied['receiptPath'],
        apply_receipt_sha256=activation.digest(receipt.read_bytes()),
        expected_registry_sha256=activation.digest(registry.read_bytes()),
        recorded_at='2026-09-08T01:01:00Z')
    registry_before = registry.read_bytes()
    with pytest.raises(m.LifecycleError) as revoke_limit:
        m.revoke_sealed_prefix_activation(tmp_path, revoke, ledger_resource_budget=insufficient)
    assert revoke_limit.value.failure_id == 'WI-LEDGER-RESOURCE-INCOMPLETE'
    assert registry.read_bytes() == registry_before
    revoked = m.revoke_sealed_prefix_activation(tmp_path, revoke)
    assert revoked['state'] == 'revoke' and pairs == [expected, expected]


def _pending_scope_fixture(tmp_path, reverse=False):
    from test_mutate_work_item import load_module, seed_active, write_empty_bug_dispositions, closure, seed_context_bug
    m = load_module()
    root = tmp_path / 'repo'
    names = ('pending-a', 'pending-b', 'selected-parent')
    for name in names:
        seed_active(m, root, name)
    raw = {}
    for index, name in enumerate(names):
        item = root / 'work-items/active' / name
        for n in range(index + 2):
            result = cli(item, 'append', '--run-id', f'synthetic-{name}-{n}', '--role', 'analyst',
                '--execution-role', 'internal', '--status', 'completed', '--gate', 'none',
                '--event-kind', 'standalone', '--scope', 'synthetic independent scope preparation',
                '--evidence', 'manual-check:synthetic preparation')
            assert result.returncode == 0, result.stdout + result.stderr
        raw[name] = (item / 'agent-runs.jsonl').read_bytes()
    bug = seed_context_bug(root, names[2], 'selected-fixed-bug')
    bug.write_bytes(bug.read_bytes().replace(b'status: open', b'status: fixed'))
    m.refresh_readme(root)
    instant = '2026-10-24T00:00:00Z'
    operations = {}
    for index, name in enumerate(names[:2]):
        order = 1 - index if reverse else index
        operation = f'{order}-synthetic-{name}'
        operations[name] = operation
        successor = name + '-next'
        digest = hashlib.sha256(raw[name]).hexdigest()
        write_empty_bug_dispositions(root, name, instant)
        data = (f'Task: Continue.\nContinues: {name}\nObligation-transfer: {operation}\n'
                f'Next action: Review.\nupdated: {instant}\n').encode()
        transfer = json.dumps({'schemaVersion': 1, 'sourceWorkItem': name,
            'successorWorkItem': successor, 'expectedSourceLedgerSha256': digest, 'obligations': []}).encode()
        with pytest.raises(m.LifecycleError):
            m.archive_with_successor(root, name, closure(instant).encode(), instant,
                successor, data, operation, digest,
                hashlib.sha256((root / 'work-items/README.md').read_bytes()).hexdigest(),
                obligation_transfer_data=transfer, inject_failure_at='T0')
    intents = root / '.scratch/work-items-lifecycle-transitions'
    assert len(list(intents.glob('*.json'))) == 2
    return m, root, raw, operations, bug, instant, intents


@pytest.mark.parametrize('reverse', [False, True])
def test_independent_recovery_scopes_then_public_selected_action(tmp_path, monkeypatch, reverse):
    m, root, raw, operations, bug, instant, intents = _pending_scope_fixture(tmp_path, reverse)
    original = m.LifecycleTransaction.admit_ledger_operation
    observations = []
    def observed(self, item, **kwargs):
        result = original(self, item, **kwargs)
        observations.append((id(self), item.name, result[0].max_events, result[0].max_ledger_bytes))
        return result
    monkeypatch.setattr(m.LifecycleTransaction, 'admit_ledger_operation', observed)
    receipt = m.archive_fixed_bug(root, bug.stem, instant, 'Fixed.', 'Synthetic verification.')
    assert receipt['status'] == 'settled' and not bug.exists()
    assert (root / receipt['archivePath']).is_file()
    assert not list(intents.glob('*.json'))
    assert len({value[0] for value in observations}) == 1
    for name, count in (('pending-a', 2), ('pending-b', 3)):
        assert any(value[1:] == (name, count, len(raw[name])) for value in observations)
    assert all((root / 'work-items/active' / name / 'agent-runs.jsonl').read_bytes() == image
               for name, image in raw.items())


def test_explicit_ceiling_stays_fixed_after_prior_scope_settles(tmp_path):
    m, root, raw, operations, bug, instant, intents = _pending_scope_fixture(tmp_path)
    v = m._validator_module()
    ceiling = v.LedgerResourceBudgetV1(2, len(raw['pending-a']))
    with pytest.raises(m.LifecycleError) as failure:
        m.archive_fixed_bug(root, bug.stem, instant, 'Fixed.', 'Synthetic verification.',
            ledger_resource_budget=ceiling)
    assert failure.value.failure_id == 'WI-LEDGER-RESOURCE-INCOMPLETE'
    assert not (intents / (operations['pending-a'] + '.json')).exists()
    assert (intents / (operations['pending-b'] + '.json')).is_file()
    assert bug.is_file()
    assert all((root / 'work-items/active' / name / 'agent-runs.jsonl').read_bytes() == image
               for name, image in raw.items())


def test_failure_after_retirement_does_not_start_next_scope(tmp_path, monkeypatch):
    m, root, raw, operations, bug, instant, intents = _pending_scope_fixture(tmp_path)
    original = m._remove_lifecycle_file
    first = intents / (operations['pending-a'] + '.json')
    def retire_then_fail(path, **kwargs):
        result = original(path, **kwargs)
        if path == first and result is True:
            raise m.LifecycleError('WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE',
                'synthetic failure after actual owned retirement')
        return result
    monkeypatch.setattr(m, '_remove_lifecycle_file', retire_then_fail)
    with pytest.raises(m.LifecycleError, match='synthetic failure after actual owned retirement'):
        m.archive_fixed_bug(root, bug.stem, instant, 'Fixed.', 'Synthetic verification.')
    assert not first.exists() and (intents / (operations['pending-b'] + '.json')).is_file()
    assert bug.is_file()


def test_completed_scope_keeps_prior_integrity_observation(tmp_path, monkeypatch):
    m, root, raw, operations, bug, instant, intents = _pending_scope_fixture(tmp_path)
    guard = root / 'retained-guard.bin'
    guard.write_bytes(b'guard-one')
    original_recover = m._recover_all_transitions
    def retain_before_recovery(root, **kwargs):
        tx = m._CURRENT_LIFECYCLE_TRANSACTION.get()
        tx.observe_retained_inputs((m._capture_file_snapshot(guard, failure_id='WI-LIFECYCLE-EFFECT'),))
        return original_recover(root, **kwargs)
    monkeypatch.setattr(m, '_recover_all_transitions', retain_before_recovery)
    original_end = m.LifecycleTransaction.complete_ledger_intent_scope
    def end_then_change(self, token, retirement_result):
        original_end(self, token, retirement_result)
        if token[0].identity == ('operation', operations['pending-a']):
            assert guard in self._retained_observations
            guard.write_bytes(b'guard-two')
    monkeypatch.setattr(m.LifecycleTransaction, 'complete_ledger_intent_scope', end_then_change)
    with pytest.raises(m.LifecycleError):
        m.archive_fixed_bug(root, bug.stem, instant, 'Fixed.', 'Synthetic verification.')
    assert not (intents / (operations['pending-a'] + '.json')).exists()
    assert (intents / (operations['pending-b'] + '.json')).is_file() and bug.is_file()


@pytest.mark.parametrize('same_request', [False, True])
def test_direct_recovery_and_same_request_keep_scope_identity(tmp_path, monkeypatch, same_request):
    from test_mutate_work_item import closure
    m, root, raw, operations, bug, instant, intents = _pending_scope_fixture(tmp_path)
    operation = operations['pending-a']
    intent = json.loads((intents / (operation + '.json')).read_bytes())
    scopes, pairs = [], []
    begin = m.LifecycleTransaction.begin_ledger_admission_scope
    admit = m.LifecycleTransaction.admit_ledger_operation
    def begun(self, identity, owner):
        token = begin(self, identity, owner)
        scopes.append((id(self), identity, token[1]))
        return token
    def admitted(self, item, **kwargs):
        result = admit(self, item, **kwargs)
        pairs.append((self._ledger_admission_scope.identity, result[0].max_events,
                      result[0].max_ledger_bytes))
        return result
    monkeypatch.setattr(m.LifecycleTransaction, 'begin_ledger_admission_scope', begun)
    monkeypatch.setattr(m.LifecycleTransaction, 'admit_ledger_operation', admitted)
    if same_request:
        transfer = json.dumps({'schemaVersion': 1, 'sourceWorkItem': 'pending-a',
            'successorWorkItem': 'pending-a-next',
            'expectedSourceLedgerSha256': hashlib.sha256(raw['pending-a']).hexdigest(),
            'obligations': []}).encode()
        result = m.archive_with_successor(root, 'pending-a', closure(instant).encode(), instant,
            'pending-a-next', m._unb64(intent['successorData']), operation,
            intent['expectedLedgerSha256'], intent['expectedReadmeSha256'],
            obligation_transfer_data=transfer)
        assert result['status'] == 'settled'
    else:
        assert m.recover_transition(root, operation) is None
    assert len({row[0] for row in scopes}) == 1
    assert {row[1] for row in scopes} == {('operation', operation)}
    assert max(row[2] for row in scopes) == (2 if same_request else 1)
    assert pairs and set(pairs) == {(('operation', operation), 2, len(raw['pending-a']))}
    assert not (intents / (operation + '.json')).exists()
    assert (intents / (operations['pending-b'] + '.json')).is_file() and bug.is_file()
    for name, image in raw.items():
        item = m.resolve_category(root, 'work-item:' + name)
        assert (item / 'agent-runs.jsonl').read_bytes() == image


def _selected_transfer_capture_fixture(tmp_path):
    v = owner('validate-work-item-state.py')
    archive = tmp_path / 'work-items/archive/2026-10/origin'
    archive.mkdir(parents=True)
    ledger = archive / 'agent-runs.jsonl'
    ledger.write_bytes(b'{}\n')
    status = archive / 'status.md'
    status.write_bytes(b'Task: Synthetic capture owner.\n' + b' ' * 8192)
    relative = archive.relative_to(tmp_path).as_posix()
    digest = hashlib.sha256(ledger.read_bytes()).hexdigest()
    operation = 'synthetic-origin-operation'
    receipt = {'schemaVersion': 2, 'owner': 'mutate-work-item:archive-with-successor-v2',
               'operationId': operation, 'archivePath': relative, 'ledgerSha256': digest,
               'archiveIdentity': v.archived_ledger_identity(relative, digest),
               'migrationReceipts': [], 'obligations': []}
    (archive / 'lifecycle-transition-receipt.json').write_text(json.dumps(receipt), encoding='utf-8')
    return v, archive, ledger, status, operation


@pytest.mark.parametrize('with_inputs', [False, True])
def test_transfer_status_keeps_its_metadata_budget(tmp_path, with_inputs):
    v, archive, ledger, status, operation = _selected_transfer_capture_fixture(tmp_path)
    ledgers, authorities, errors = {}, {}, []
    selected = v._transfer_receipts(tmp_path, errors, selected_source_item=archive,
        selected_operation_id=operation, captured_ledger_bytes_out=ledgers,
        captured_authority_bytes_out=authorities)
    assert errors == [] and set(selected) == {operation}
    wire = {identity: raw for identity, raw in authorities.items()
            if identity.endswith('/lifecycle-transition-receipt.json')
            or identity.endswith('\\lifecycle-transition-receipt.json')}
    demand = v.inspect_ledger_resource_demand(ledger, None, source_bytes=ledger.read_bytes(),
        byte_participants=wire)
    budget = v.resolve_ledger_resource_budget(demand=demand)
    assert status.stat().st_size > budget.max_ledger_bytes
    inputs = v._CurrentEvidenceV1() if with_inputs else None
    errors = []
    actual = v._transfer_receipts(tmp_path, errors, selected_source_item=archive,
        selected_operation_id=operation, ledger_resource_budget=budget, _inputs=inputs)
    assert errors == [] and set(actual) == {operation}
    if inputs is not None:
        inputs.freeze_selection_keys()
        assert inputs.receive() is False and inputs.authority_qualified()
    status.write_bytes(b' ' * (4 * 1024 * 1024 + 1))
    errors = []
    refused = v._transfer_receipts(tmp_path, errors, selected_source_item=archive,
        selected_operation_id=operation, ledger_resource_budget=budget,
        _inputs=v._CurrentEvidenceV1() if with_inputs else None)
    assert refused == {} and any('transfer source status is unreadable' in error for error in errors)


@pytest.mark.parametrize('route', ['local-map-reacquire', 'empty-output-map', 'preselected'])
def test_selected_ancestor_capture_survives_identical_replacement(tmp_path, route):
    v, archive, ledger, status, operation = _selected_transfer_capture_fixture(tmp_path)
    m = v.load_lifecycle_owner()
    inputs = v._CurrentEvidenceV1()
    snapshots = None if route == 'local-map-reacquire' else {}
    original = (m._capture_file_snapshot(ledger, maximum_bytes=None,
        require_single_link=True, failure_id='TEST-CAPTURE') if route == 'preselected' else None)
    errors = []
    receipts = v._transfer_receipts(tmp_path, errors, selected_source_item=archive,
        selected_operation_id=operation, _inputs=inputs, captured_snapshots_out=snapshots,
        preselected_ledger_snapshots={str(ledger): original} if original is not None else None)
    assert errors == [] and set(receipts) == {operation}
    retained = next(predicate for predicate in inputs.selection_inputs if predicate.path == ledger)
    assert retained.snapshot is not None and retained.snapshot.require_single_link
    if snapshots is not None:
        assert snapshots[str(ledger)] is retained.snapshot
    if original is not None:
        assert retained.snapshot is original
    snapshot = retained.snapshot
    raw = ledger.read_bytes()
    ledger.rename(ledger.with_suffix('.original'))
    ledger.write_bytes(raw)
    assert m._lifecycle_file_identity(ledger.lstat()) != snapshot.identity
    if route == 'local-map-reacquire':
        reread_errors = []
        assert v._transfer_receipts(tmp_path, reread_errors, selected_source_item=archive,
            selected_operation_id=operation, _inputs=inputs)
        assert reread_errors == []
        assert retained.snapshot is snapshot
    inputs.freeze_selection_keys()
    assert inputs.receive() is True and not inputs.authority_qualified()
    assert not retained.accepted


def test_captured_transfer_ledger_exports_actual_custody_snapshot(tmp_path, monkeypatch):
    v, archive, ledger, status, operation = _selected_transfer_capture_fixture(tmp_path)
    m = v.load_lifecycle_owner()
    native_files = [m._capture_file_snapshot(path, require_single_link=True,
        failure_id='TEST-CAPTURE') for path in archive.iterdir() if path.is_file()]
    original = next(snapshot for snapshot in native_files if snapshot.path == ledger)
    custody = tmp_path / 'custody'
    custody.mkdir()
    original_directories = [m._capture_directory_snapshot(path, failure_id='TEST-CAPTURE')
        for path in [tmp_path, *[path for path in tmp_path.rglob('*') if path.is_dir()]]]
    current_path = custody / 'ancestor.jsonl'
    ledger.rename(current_path)
    current = m._capture_file_snapshot(current_path, require_single_link=True, failure_id='TEST-CAPTURE')
    directories = {snapshot.path: m._capture_directory_snapshot(snapshot.path, failure_id='TEST-CAPTURE')
                   for snapshot in original_directories}
    native = m.AcquiredWorkItemInputV1(tmp_path,
        [m.CapturedInputAssociationV1(snapshot, current if snapshot is original else snapshot)
         for snapshot in native_files],
        [m.CapturedInputAssociationV1(snapshot, directories[snapshot.path])
         for snapshot in original_directories])
    relative = archive.relative_to(tmp_path).as_posix()
    criteria = v.HistoricalLedgerCriteriaV1('synthetic-criteria', 'synthetic-acquisition', False, 'current')
    binding = v.CapturedWorkItemHistoryBindingV1(tmp_path, archive.name, relative, relative,
        relative + '/agent-runs.jsonl', criteria, (), (), {}, native)
    root = v._CapturedHistoryPath(binding, tmp_path)
    selected = root / relative / 'agent-runs.jsonl'
    snapshots = {}
    capture, observed = m._capture_file_snapshot, []
    def capture_actual(*args, **kwargs):
        result = capture(*args, **kwargs)
        if kwargs.get('acquired_input') is selected:
            observed.append(result)
        return result
    monkeypatch.setattr(m, '_capture_file_snapshot', capture_actual)
    raw = v._read_transfer_authority_bytes(root, selected, maximum_bytes=None,
        require_single_link=True, captured_snapshots_out=snapshots)
    assert raw == original.data and len(observed) == 1
    assert snapshots[str(selected)] is observed[0]
    m._verify_captured_file(snapshots[str(selected)], 'TEST-CAPTURED-RECEIVING', acquired_input=root)
    assert current.path == current_path and not ledger.exists()
