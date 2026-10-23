"""Exact native candidate publication at the public ledger boundary."""
import contextlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_script(relative, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def ledger_item(tmp_path):
    fixture = load_script('tests/test_agent_run_ledger.py', 'native_ledger_existing_fixture')
    writer = fixture.load_ledger_module()
    item = fixture.prepare_valid_work_item(tmp_path)
    return writer, item


def append_args(run_id):
    return ['append', '--run-id', run_id, '--role', 'qa-engineer',
            '--execution-role', 'internal', '--status', 'completed', '--gate', 'PASS',
            '--scope', 'native qualified ledger publication', '--artifact', 'reviews/qa.md',
            '--evidence', 'manual-check:own native runtime oracle',
            '--started-at', '2026-10-20T08:00:00Z', '--updated-at', '2026-10-20T08:00:01Z']


def invoke(writer, item, args):
    return writer.main(['--work-item', str(item), *args])


@pytest.mark.skipif(os.name != 'nt', reason='actual Windows retained reader oracle')
def test_public_append_publishes_under_retained_native_reader(ledger_item):
    writer, item = ledger_item
    assert invoke(writer, item, append_args('native-seed')) == 0
    path = item / 'agent-runs.jsonl'
    previous = path.read_bytes()
    owner = writer.load_validator().load_lifecycle_owner()
    descriptor = owner._open_readonly_nofollow(path)
    before = os.fstat(descriptor)
    try:
        assert invoke(writer, item, append_args('native-next')) == 0
        assert os.read(descriptor, len(previous) + 1) == previous
        assert os.fstat(descriptor).st_ino == before.st_ino
        assert path.stat().st_ino != before.st_ino
        assert path.read_bytes().startswith(previous)
        assert [json.loads(line)['runId'] for line in path.read_bytes().splitlines()] == ['native-seed', 'native-next']
        assert not (item / 'agent-runs.jsonl.tmp').exists()
    finally:
        os.close(descriptor)
    assert not (item / 'agent-runs.jsonl.lock').exists()

def pin_validator(writer, monkeypatch):
    validator = writer.load_validator()
    monkeypatch.setattr(writer, 'load_validator', lambda: validator)
    return validator, validator.load_lifecycle_owner()


def event_for(writer, validator, item, run_id='native-extra'):
    args = writer.build_parser().parse_args(['--work-item', str(item), *append_args(run_id)])
    return writer.build_event(args, validator)


def test_exact_object_one_qualifier_and_callback(ledger_item, monkeypatch):
    writer, item = ledger_item
    validator, owner = pin_validator(writer, monkeypatch)
    counts = {'qualifier': 0, 'callback': 0, 'creator': 0}
    qualified = []
    validate = validator.validate_work_item
    create = owner.LifecycleWriteTarget.create_qualified_candidate
    def inspect(item, *args, **kwargs):
        if kwargs.get('ledger_path') is not None:
            counts['qualifier'] += 1
            qualified.append(kwargs['ledger_path'].stat().st_ino)
        return validate(item, *args, **kwargs)
    def created(self, *args):
        counts['creator'] += 1
        return create(self, *args)
    def callback(): counts['callback'] += 1
    monkeypatch.setattr(validator, 'validate_work_item', inspect)
    monkeypatch.setattr(owner.LifecycleWriteTarget, 'create_qualified_candidate', created)
    assert writer._append_event_transaction(item, validator, lambda previous: event_for(writer, validator, item), before_replace=callback)
    assert counts == {'qualifier': 1, 'callback': 1, 'creator': 1}
    assert qualified == [(item / 'agent-runs.jsonl').stat().st_ino]


def launch_args():
    return ['append', '--run-id', 'late-observed-launch', '--role', 'lead', '--execution-role', 'main',
            '--status', 'running', '--gate', 'none', '--scope', 'own factual late-recording fixture',
            '--event-kind', 'launch', '--notes', 'Synthetic historical start recorded late; original preliminary persistence failed; operation ended.',
            '--started-at', '2026-10-20T08:00:00Z', '--updated-at', '2026-10-20T08:10:00Z']


def settle_args():
    return ['settle-launch', '--launch-run-id', 'late-observed-launch', '--run-id', 'late-observed-terminal',
            '--status', 'completed', '--gate', 'none', '--evidence', 'manual-check:synthetic retained original terminal receipt',
            '--notes', 'Synthetic original outcome; no past prelaunch-persistence claim.',
            '--started-at', '2026-10-20T08:01:00Z', '--updated-at', '2026-10-20T08:10:01Z']


@pytest.mark.skipif(os.name != 'nt', reason='actual Windows retained reader oracle')
def test_public_settle_and_exact_replay_skip_publication_query(ledger_item, monkeypatch):
    writer, item = ledger_item
    validator, owner = pin_validator(writer, monkeypatch)
    assert invoke(writer, item, settle_args()) == 1
    assert invoke(writer, item, launch_args()) == 0
    path = item / 'agent-runs.jsonl'
    previous = path.read_bytes()
    fd = owner._open_readonly_nofollow(path)
    try:
        assert invoke(writer, item, settle_args()) == 0
        assert os.read(fd, len(previous) + 1) == previous
    finally: os.close(fd)
    committed = path.read_bytes()
    calls = []
    def unavailable(self):
        calls.append(True)
        raise OSError(5, 'own publication query failure')
    monkeypatch.setattr(owner.LifecycleWriteTarget, '_select_qualified_backend', unavailable)
    assert invoke(writer, item, settle_args()) == 0
    assert path.read_bytes() == committed and calls == []
    with pytest.raises(OSError, match='publication query failure'):
        invoke(writer, item, append_args('query-failed-real-mutation'))
    assert calls == [True] and path.read_bytes() == committed
    assert not (item / 'agent-runs.jsonl.tmp').exists()
    assert not (item / 'agent-runs.jsonl.lock').exists()


def test_settle_requires_current_first_settlement_and_exact_request_identity(ledger_item, capsys):
    writer, item = ledger_item
    assert invoke(writer, item, launch_args()) == 0
    assert invoke(writer, item, settle_args()) == 0
    path = item / 'agent-runs.jsonl'
    committed = path.read_bytes()
    capsys.readouterr()
    second = settle_args()
    second[second.index('--run-id') + 1] = 'different-qualified-terminal'
    assert invoke(writer, item, second) == 1
    assert 'WI-LEDGER-OPERATION-EFFECT' in capsys.readouterr().err
    assert path.read_bytes() == committed
    changed = settle_args()
    changed[changed.index('--notes') + 1] = 'different outcome for the same request identity'
    assert invoke(writer, item, changed) == 1
    assert 'WI-LEDGER-SETTLE-CONFLICT' in capsys.readouterr().err
    assert path.read_bytes() == committed
    repeated = committed + committed.splitlines(keepends=True)[-1]
    path.write_bytes(repeated)
    assert invoke(writer, item, settle_args()) == 1
    assert 'WI-LEDGER-SETTLE-TARGET' in capsys.readouterr().err
    assert path.read_bytes() == repeated
    ambiguous = committed + committed.splitlines(keepends=True)[0]
    path.write_bytes(ambiguous)
    assert invoke(writer, item, settle_args()) == 1
    assert 'launch must identify one V2 launch event' in capsys.readouterr().err
    assert path.read_bytes() == ambiguous
    launch = json.loads(committed.splitlines()[0])
    del launch['scope']
    missing_metadata = (writer.serialize_event(launch) + '\n').encode('utf-8')
    path.write_bytes(missing_metadata)
    assert invoke(writer, item, settle_args()) == 1
    assert 'launch lacks immutable event metadata' in capsys.readouterr().err
    assert path.read_bytes() == missing_metadata
    assert not (item / 'agent-runs.jsonl.tmp').exists()
    assert not (item / 'agent-runs.jsonl.lock').exists()


def test_settle_exact_replay_requalifies_nonempty_request_after_proof_loss(ledger_item, monkeypatch, capsys):
    writer, item = ledger_item
    validator, owner = pin_validator(writer, monkeypatch)
    assert invoke(writer, item, launch_args()) == 0
    request = settle_args()
    request[request.index('--gate') + 1] = 'PASS'
    request += ['--artifact', 'reviews/qa.md']
    proof = item / 'reviews/qa.md'
    assert proof.is_file()
    assert invoke(writer, item, request) == 0
    path = item / 'agent-runs.jsonl'
    committed = path.read_bytes()
    received = []
    receive = writer._receive_append_operation
    def observed(*args):
        received.append((args[-3], args[-2], args[-1]))
        return receive(*args)
    def forbidden(self):
        raise AssertionError('publication backend queried during exact settlement replay')
    monkeypatch.setattr(writer, '_receive_append_operation', observed)
    monkeypatch.setattr(owner.LifecycleWriteTarget, '_select_qualified_backend', forbidden)
    assert invoke(writer, item, request) == 0
    assert path.read_bytes() == committed
    capsys.readouterr()
    proof.unlink()
    assert invoke(writer, item, request) == 1
    failure = capsys.readouterr().err
    assert 'WI-LEDGER-OPERATION-EFFECT' in failure
    assert len(received) == 2
    for previous, candidate, requested in received:
        assert previous == candidate == committed
        assert len(requested) == 1 and requested[0]['runId'] == 'late-observed-terminal'
    states, acquired = [], []
    errors = validator.validate_work_item(item, strict_revise=False, validate_status_file=False,
        obligation_state_out=states, ledger_acquisition_complete_out=acquired)
    assert errors and acquired == [True]
    assert [launch['runId'] for launch in states[0]._current_result[3]] == ['late-observed-launch']
    assert path.read_bytes() == committed
    assert not (item / 'agent-runs.jsonl.tmp').exists()
    assert not (item / 'agent-runs.jsonl.lock').exists()


@pytest.mark.parametrize(('blank', 'ending'), [
    (' \t\u00a0\u2003\u2028\u2029\n', b'\n'),
    ('\t\r\n', b'\r'),
], ids=['decoded-unicode-blank', 'lone-cr-body-digest'])
def test_public_exact_replay_preserves_canonical_raw_line_identity(ledger_item, monkeypatch, blank, ending):
    import hashlib
    writer, item = ledger_item
    validator, owner = pin_validator(writer, monkeypatch)
    assert invoke(writer, item, launch_args()) == 0
    assert invoke(writer, item, settle_args()) == 0
    path = item / 'agent-runs.jsonl'
    bodies = path.read_bytes().splitlines()
    committed = blank.encode('utf-8') + b'\n'.join(bodies) + ending
    path.write_bytes(committed)
    errors, metadata, acquired = [], [], []
    events = validator.load_jsonl(path, errors, raw_metadata=metadata,
                                 ledger_acquisition_complete_out=acquired)
    assert errors == [] and acquired == [True]
    assert [event['runId'] for event in events] == ['late-observed-launch', 'late-observed-terminal']
    assert [record['line'] for record in metadata] == [2, 3]
    digest_body = bodies[-1] + (b'\r' if ending == b'\r' else b'')
    assert metadata[-1]['sha256'] == hashlib.sha256(digest_body).hexdigest()
    def forbidden(self):
        raise AssertionError('native publication query during exact replay')
    monkeypatch.setattr(owner.LifecycleWriteTarget, '_select_qualified_backend', forbidden)
    assert invoke(writer, item, settle_args()) == 0
    assert path.read_bytes() == committed
    assert not (item / 'agent-runs.jsonl.tmp').exists()
    assert not (item / 'agent-runs.jsonl.lock').exists()


def test_recovery_public_command_under_reader_and_valid_replay_no_query(tmp_path, monkeypatch):
    fixture = load_script('tests/test_agent_run_ledger.py', 'native_recovery_fixture')
    item, previous, digest = fixture._prepare_recovery_writer_item(tmp_path)
    writer = fixture.load_ledger_module()
    validator, owner = pin_validator(writer, monkeypatch)
    args = ['recover-invalid-closure', '--run-id', 'run-writer-recovery-control',
            '--target-run-id', 'run-writer-invalid-closer', '--target-event-sha256', digest,
            '--evidence', f'manual-check:run-writer-invalid-closer {digest}',
            '--started-at', '2026-08-17T00:02:00Z', '--updated-at', '2026-08-17T00:02:00Z']
    path = item / 'agent-runs.jsonl'; fd = owner._open_readonly_nofollow(path)
    try:
        assert invoke(writer, item, args) == 0
        assert os.read(fd, len(previous) + 1) == previous
    finally: os.close(fd)
    assert path.read_bytes().startswith(previous)
    # The specialized recovery append's exact replay path retains its validator.
    committed = path.read_bytes()
    def refuse(self): raise AssertionError('publication admission on exact replay')
    monkeypatch.setattr(owner.LifecycleWriteTarget, '_select_qualified_backend', refuse)
    actual_commit = writer._commit_recovery_append
    def exact_replay(selected_item, requested, callback, marker, injection, **kwargs):
        return actual_commit(selected_item, requested, callback, marker, injection,
                             replay_detector=lambda raw: raw == committed, **kwargs)
    monkeypatch.setattr(writer, '_commit_recovery_append', exact_replay)
    assert invoke(writer, item, args) == 0
    assert path.read_bytes() == committed


def test_preexisting_candidate_is_never_truncated_or_removed(ledger_item):
    writer, item = ledger_item
    candidate = item / 'agent-runs.jsonl.tmp'; candidate.write_bytes(b'preserved foreign candidate')
    assert invoke(writer, item, append_args('candidate-collision')) == 1
    assert candidate.read_bytes() == b'preserved foreign candidate'
    assert not (item / 'agent-runs.jsonl').exists()


@pytest.mark.parametrize('drift', ['candidate-bytes', 'destination-bytes', 'destination-appeared'])
def test_callback_drift_refuses_without_requalification(ledger_item, monkeypatch, drift):
    writer, item = ledger_item
    validator, owner = pin_validator(writer, monkeypatch)
    path = item / 'agent-runs.jsonl'
    if drift != 'destination-appeared': assert invoke(writer, item, append_args('drift-seed')) == 0
    count = []; validate = validator.validate_work_item
    def qualify(*a, **kw):
        if kw.get('ledger_path') is not None: count.append(True)
        return validate(*a, **kw)
    monkeypatch.setattr(validator, 'validate_work_item', qualify)
    def callback():
        if drift == 'candidate-bytes':
            # Retained creator's own handle: same object, different bytes.
            target = publications[0]; rec = target._qualified_record
            if os.name == 'nt':
                c, _w, k, _nt, _types = target._native
                assert k.SetFilePointerEx(rec.handle, c.c_longlong(0), None, 0)
            else: os.lseek(rec.handle, 0, os.SEEK_SET)
            target._write_handle(rec.handle, b'[' + rec.qualified_bytes[1:])
        else: path.write_bytes(b'own changed destination')
    publications = []; create = owner.LifecycleWriteTarget.create_qualified_candidate
    def capture(self, *a): publications.append(self); return create(self, *a)
    monkeypatch.setattr(owner.LifecycleWriteTarget, 'create_qualified_candidate', capture)
    aborted = []
    with pytest.raises((ValueError, OSError)):
        writer._append_event_transaction(item, validator, lambda previous: event_for(writer, validator, item),
            before_replace=callback, on_abort=lambda: aborted.append(True))
    assert count == [True] and aborted == []
    assert publications[0].qualified_outcome == 'unknown'
    assert (item / 'agent-runs.jsonl.tmp').exists()
    assert not (item / 'agent-runs.jsonl.lock').exists()


@pytest.mark.skipif(os.name != 'nt', reason='native operation fault boundary')
@pytest.mark.parametrize('effect', ['no-effect', 'published-error', 'wrong-leaf', 'post-receiving-error'])
def test_native_effect_not_exception_controls_custody_cleanup(ledger_item, monkeypatch, effect):
    writer, item = ledger_item
    validator, owner = pin_validator(writer, monkeypatch)
    assert invoke(writer, item, append_args('effect-seed')) == 0
    path = item / 'agent-runs.jsonl'; previous = path.read_bytes(); calls = []
    rename = owner.LifecycleWriteTarget._windows_rename
    def injected(self, handle, leaf, **kw):
        calls.append(kw)
        if effect == 'no-effect': return
        rename(self, handle, 'wrong.bin' if effect == 'wrong-leaf' else leaf, **kw)
        if effect == 'published-error': raise OSError(5, 'own error after actual native rename')
    monkeypatch.setattr(owner.LifecycleWriteTarget, '_windows_rename', injected)
    if effect == 'post-receiving-error':
        def refused(*a): raise OSError(5, 'own post-effect receiver failure')
        monkeypatch.setattr(owner.LifecycleWriteTarget, '_receive_placement', refused)
    aborted = []
    with pytest.raises((ValueError, OSError)):
        writer._append_event_transaction(item, validator, lambda previous: event_for(writer, validator, item),
            on_abort=lambda: aborted.append(True))
    assert len(calls) == 1
    if effect == 'no-effect':
        assert path.read_bytes() == previous and aborted == [True]
    elif effect == 'wrong-leaf':
        assert path.read_bytes() == previous and aborted == []
        assert (item / 'wrong.bin').read_bytes().startswith(previous)
    else:
        assert path.read_bytes().startswith(previous) and path.read_bytes() != previous and aborted == []
    assert not (item / 'agent-runs.jsonl.tmp').exists()
    assert not (item / 'agent-runs.jsonl.lock').exists()


@pytest.mark.skipif(os.name != 'nt', reason='actual Windows ReadOnly permission oracle')
def test_readonly_target_refuses_without_backend_retry(ledger_item, monkeypatch):
    writer, item = ledger_item
    validator, owner = pin_validator(writer, monkeypatch)
    assert invoke(writer, item, append_args('readonly-seed')) == 0
    path = item / 'agent-runs.jsonl'; previous = path.read_bytes(); original_mode = path.stat().st_mode
    path.chmod(0o444)
    calls = []; rename = owner.LifecycleWriteTarget._windows_rename
    def counted(self, *a, **kw): calls.append(kw); return rename(self, *a, **kw)
    monkeypatch.setattr(owner.LifecycleWriteTarget, '_windows_rename', counted)
    try:
        with pytest.raises(OSError): invoke(writer, item, append_args('readonly-denied'))
        assert path.read_bytes() == previous and len(calls) == 1
        assert not (item / 'agent-runs.jsonl.tmp').exists()
    finally: path.chmod(original_mode)


def test_invalid_qualifier_cleans_only_owned_unchanged_candidate(ledger_item):
    writer, item = ledger_item
    args = append_args('invalid-pass'); args[args.index('--evidence'):args.index('--evidence') + 2] = []
    assert invoke(writer, item, args) == 1
    assert not (item / 'agent-runs.jsonl.tmp').exists()
    assert not (item / 'agent-runs.jsonl').exists()

@pytest.mark.skipif(os.name != 'nt', reason='Windows feature selection contract')
@pytest.mark.parametrize('observation', ['bit-clear', 'missing-export', 'query-error'])
def test_capability_query_distinguishes_absent_and_error(ledger_item, observation):
    writer, item = ledger_item
    owner = writer.load_validator().load_lifecycle_owner()
    target = owner.LifecycleWriteTarget(item / 'agent-runs.jsonl', failure_id='OWN-CAPABILITY')
    class Kernel:
        def __init__(self, actual): self.actual = actual
        def __getattr__(self, name):
            if name == 'GetVolumeInformationByHandleW':
                if observation == 'missing-export': raise AttributeError(name)
                return query
            return getattr(self.actual, name)
    def query(*args):
        if observation == 'query-error':
            import ctypes
            ctypes.set_last_error(5)
            return 0
        args[5]._obj.value = 0
        return 1
    try:
        target._acquire_existing_parents()
        c, w, k, nt, types = target._native
        target._native = c, w, Kernel(k), nt, types
        if observation == 'query-error':
            with pytest.raises(owner.LifecycleError, match='publication capability query') as failure:
                target._select_qualified_backend()
            assert failure.value.__cause__.winerror == 5
        else:
            assert target._select_qualified_backend() == ('legacy' if observation == 'bit-clear' else 'legacy-discovery-unavailable')
        assert not target._creations
    finally: target.__exit__(None, None, None)


@pytest.mark.skipif(os.name != 'nt', reason='native unsupported-operation boundary')
def test_selected_unsupported_operation_is_not_retried(ledger_item, monkeypatch):
    writer, item = ledger_item; validator, owner = pin_validator(writer, monkeypatch)
    assert invoke(writer, item, append_args('unsupported-seed')) == 0
    previous = (item / 'agent-runs.jsonl').read_bytes(); calls = []
    def unsupported(self, *a, **kw):
        calls.append(kw)
        raise OSError(50, 'own classified STATUS_NOT_SUPPORTED0xc00000bb')
    monkeypatch.setattr(owner.LifecycleWriteTarget, '_windows_rename', unsupported)
    with pytest.raises(OSError, match='STATUS_NOT_SUPPORTED'):
        invoke(writer, item, append_args('unsupported-effect'))
    assert len(calls) == 1 and calls[0]['posix_replace']
    assert (item / 'agent-runs.jsonl').read_bytes() == previous
    assert not (item / 'agent-runs.jsonl.tmp').exists()


@pytest.mark.skipif(os.name != 'nt', reason='native release failure receiving')
def test_postpublication_release_error_preserves_target_and_closes_actual_handle(ledger_item, monkeypatch):
    import ctypes
    from ctypes import wintypes
    writer, item = ledger_item; validator, owner = pin_validator(writer, monkeypatch)
    assert invoke(writer, item, append_args('release-seed')) == 0
    path = item / 'agent-runs.jsonl'; previous = path.read_bytes(); handles = []
    close = owner.LifecycleWriteTarget._close
    def close_then_report(self, handle):
        record = getattr(self, '_qualified_record', None)
        close(self, handle)
        if record is not None and handle == record.handle:
            handles.append(handle)
            raise OSError(5, 'own close outcome reporting failure after actual close')
    monkeypatch.setattr(owner.LifecycleWriteTarget, '_close', close_then_report)
    aborted = []
    with pytest.raises(ValueError, match='handle release'):
        writer._append_event_transaction(item, validator, lambda previous: event_for(writer, validator, item),
            on_abort=lambda: aborted.append(True))
    assert path.read_bytes().startswith(previous) and path.read_bytes() != previous and not aborted
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetHandleInformation.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    flags = wintypes.DWORD()
    assert len(handles) == 1 and not kernel.GetHandleInformation(handles[0], ctypes.byref(flags))
    assert not (item / 'agent-runs.jsonl.lock').exists()


def test_owner_import_refusal_leaves_no_writer_lock(ledger_item, monkeypatch):
    writer, item = ledger_item; validator = writer.load_validator()
    def unavailable(): raise RuntimeError('own lifecycle owner unavailable')
    monkeypatch.setattr(validator, 'load_lifecycle_owner', unavailable)
    with pytest.raises(RuntimeError, match='owner unavailable'):
        writer._append_event_transaction(item, validator, lambda previous: {})
    assert not (item / 'agent-runs.jsonl.lock').exists()


def test_append_reuses_held_lifecycle_transaction_without_new_lock(ledger_item, monkeypatch):
    writer, item = ledger_item; validator, owner = pin_validator(writer, monkeypatch)
    assert invoke(writer, item, append_args('nested-seed')) == 0
    root = item.parents[2]
    with owner.LifecycleTransaction(root) as transaction:
        token = owner._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
        try:
            validator = owner._validator_module()
            monkeypatch.setattr(writer, 'load_validator', lambda: validator)
            assert writer._append_event_transaction(item, validator, lambda previous: event_for(writer, validator, item, 'nested-next'))
            transaction.verify()
        finally: owner._CURRENT_LIFECYCLE_TRANSACTION.reset(token)
    assert not (item / 'agent-runs.jsonl.lock').exists()


def test_invalid_exact_replay_still_refuses_existing_state(ledger_item, monkeypatch):
    writer, item = ledger_item; validator, owner = pin_validator(writer, monkeypatch)
    path = item / 'agent-runs.jsonl'; path.write_bytes(b'{}\n')
    def forbidden(self): raise AssertionError('publication admission before invalid replay validation')
    monkeypatch.setattr(owner.LifecycleWriteTarget, '_select_qualified_backend', forbidden)
    actual_commit = writer._commit_recovery_append
    def invalid_replay(selected_item, requested, callback, marker, injection, **kwargs):
        return actual_commit(selected_item, requested, callback, marker, injection,
                             replay_detector=lambda raw: True, **kwargs)
    monkeypatch.setattr(writer, '_commit_recovery_append', invalid_replay)
    args = ['recover-invalid-closure', '--run-id', 'invalid-replay-control',
            '--target-run-id', 'missing-replay-target', '--target-event-sha256', '0' * 64,
            '--evidence', 'manual-check:missing-replay-target ' + '0' * 64,
            '--started-at', '2026-10-22T00:00:00Z', '--updated-at', '2026-10-22T00:00:00Z']
    assert invoke(writer, item, args) == 1
    assert path.read_bytes() == b'{}\n' and not (item / 'agent-runs.jsonl.tmp').exists()

@pytest.mark.skipif(os.name != 'nt', reason='native effect receiving in a held transaction')
def test_effect_then_error_still_receives_actual_transaction_projection(ledger_item, monkeypatch):
    writer, item = ledger_item; validator, owner = pin_validator(writer, monkeypatch)
    assert invoke(writer, item, append_args('projection-seed')) == 0
    rename = owner.LifecycleWriteTarget._windows_rename
    def moved_then_reported_error(self, *args, **kwargs):
        rename(self, *args, **kwargs)
        raise OSError(5, 'own native error after observed publication')
    monkeypatch.setattr(owner.LifecycleWriteTarget, '_windows_rename', moved_then_reported_error)
    with owner.LifecycleTransaction(item.parents[2]) as transaction:
        token = owner._CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
        try:
            validator = owner._validator_module()
            with pytest.raises(OSError, match='after observed publication'):
                writer._append_event_transaction(item, validator, lambda previous: event_for(writer, validator, item, 'projection-next'))
            transaction.verify()
        finally: owner._CURRENT_LIFECYCLE_TRANSACTION.reset(token)

@pytest.mark.skipif(os.name != 'nt', reason='empty Windows target is replacement, not absence')
def test_empty_existing_target_keeps_replacement_semantics(ledger_item, monkeypatch):
    writer, item = ledger_item; validator, owner = pin_validator(writer, monkeypatch)
    path = item / 'agent-runs.jsonl'; path.write_bytes(b''); fd = owner._open_readonly_nofollow(path)
    calls = []; rename = owner.LifecycleWriteTarget._windows_rename
    def counted(self, *a, **kw): calls.append(kw); return rename(self, *a, **kw)
    monkeypatch.setattr(owner.LifecycleWriteTarget, '_windows_rename', counted)
    try:
        assert invoke(writer, item, append_args('empty-replacement')) == 0
        assert os.read(fd, 1) == b''
    finally: os.close(fd)
    assert calls == [{'replace': True, 'posix_replace': True}]


@pytest.mark.skipif(os.name != 'nt', reason='classified pre-effect legacy path with actual native operation')
def test_legacy_selected_before_effect_performs_one_ordinary_replacement(ledger_item, monkeypatch):
    writer, item = ledger_item; validator, owner = pin_validator(writer, monkeypatch)
    assert invoke(writer, item, append_args('legacy-seed')) == 0
    monkeypatch.setattr(owner.LifecycleWriteTarget, '_select_qualified_backend', lambda self: 'legacy')
    calls = []; rename = owner.LifecycleWriteTarget._windows_rename
    def counted(self, *a, **kw): calls.append(kw); return rename(self, *a, **kw)
    monkeypatch.setattr(owner.LifecycleWriteTarget, '_windows_rename', counted)
    assert invoke(writer, item, append_args('legacy-next')) == 0
    assert calls == [{'replace': True, 'posix_replace': False}]


@pytest.mark.skipif(os.name != 'nt', reason='deterministically widened create-only race window')
def test_appearing_destination_at_native_boundary_is_not_overwritten(ledger_item, monkeypatch):
    writer, item = ledger_item; validator, owner = pin_validator(writer, monkeypatch)
    path = item / 'agent-runs.jsonl'; rename = owner.LifecycleWriteTarget._windows_rename; calls = []
    def interposed(self, *a, **kw):
        calls.append(kw)
        path.write_bytes(b'preserved concurrent destination')
        return rename(self, *a, **kw)
    monkeypatch.setattr(owner.LifecycleWriteTarget, '_windows_rename', interposed)
    with pytest.raises(OSError): invoke(writer, item, append_args('appeared-at-effect'))
    assert path.read_bytes() == b'preserved concurrent destination'
    assert calls == [{'replace': False, 'posix_replace': False}]
    assert (item / 'agent-runs.jsonl.tmp').exists()
    assert not (item / 'agent-runs.jsonl.lock').exists()


@pytest.mark.skipif(os.name != "nt",reason="actual native owned candidate")
@pytest.mark.parametrize("rejection",["pre-replace","qualifier"])
def test_nf_public_recovery_reports_secondary_candidate_cleanup_refusal(tmp_path, rejection):
 import io,hashlib
 from contextlib import redirect_stdout,redirect_stderr
 from unittest.mock import patch
 Q=tmp_path
 fixture=load_script('tests/test_agent_run_ledger.py','qa_current_cleanup_fixture')
 item,previous,digest=fixture._prepare_recovery_writer_item(tmp_path)
 writer=fixture.load_ledger_module();validator=writer.load_validator();owner=validator.load_lifecycle_owner()
 path=item/'agent-runs.jsonl';candidate=item/'agent-runs.jsonl.tmp';seen=[];real=owner.LifecycleWriteTarget._windows_delete
 def refuse_exact_owned_candidate(target,handle):
  rec=getattr(target,'_qualified_record',None)
  if target.path==path and rec is not None and rec.role=='ledger-candidate' and handle==rec.handle:
   seen.append((target,rec));raise OSError(5,'QA_EXACT_OWNED_CANDIDATE_DELETE_REFUSED')
  return real(target,handle)
 args=['--work-item',str(item),'recover-invalid-closure','--run-id','run-writer-recovery-control','--target-run-id','run-writer-invalid-closer','--target-event-sha256',digest,'--evidence',f'manual-check:run-writer-invalid-closer {digest}','--started-at','2026-08-17T00:02:00Z','--updated-at','2026-08-17T00:02:00Z','--inject-failure','pre-replace']
 original_validate=validator.validate_work_item
 def qualifier(*a,**kw):
  if rejection=='qualifier' and kw.get('ledger_path') is not None:
   (item/'status.md').write_text('invalid owned status\n',encoding='utf8')
  return original_validate(*a,**kw)
 output,error=io.StringIO(),io.StringIO();thrown=None;result=None
 with patch.object(validator,'validate_work_item',side_effect=qualifier),patch.object(writer,'load_validator',return_value=validator),patch.object(validator,'load_lifecycle_owner',return_value=owner),patch.object(owner.LifecycleWriteTarget,'_windows_delete',refuse_exact_owned_candidate),redirect_stdout(output),redirect_stderr(error):
  try:result=writer.main(args)
  except BaseException as exc:thrown=exc
 # Preserve the complete acquired public return/exception/streams before interpretation.
 public={'argv':args,'returncode':result,'stdout':output.getvalue(),'stderr':error.getvalue(),'exception':None if thrown is None else {'type':type(thrown).__name__,'text':str(thrown),'notes':list(getattr(thrown,'__notes__',()))}}
 (Q/'candidate-cleanup-public-result.json').write_text(json.dumps(public,indent=2))
 assert len(seen)==1,'candidate-only fault must be reached exactly once'
 target,record=seen[0]
 import ctypes
 from ctypes import wintypes
 kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.GetHandleInformation.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)];flags=wintypes.DWORD()
 handle_valid=bool(kernel.GetHandleInformation(record.handle,ctypes.byref(flags)))
 row={'item':str(item),'sourceMutator':owner.__file__,'sourceWriter':writer.__file__,'injectionCount':len(seen),'exactCandidateRole':record.role,'candidateExists':candidate.exists(),'candidateIdentity':list(owner._lifecycle_file_identity(candidate.lstat())) if candidate.exists() else None,'creatorIdentity':list(record.identity),'candidateBytes':candidate.stat().st_size if candidate.exists() else 0,'candidateSha256':hashlib.sha256(candidate.read_bytes()).hexdigest() if candidate.exists() else None,'originalLedgerUnchanged':path.read_bytes()==previous,'lockAbsent':not (item/'agent-runs.jsonl.lock').exists(),'ownerOpen':target._open,'ownerDirectories':len(target._directories),'nativeCandidateHandleValidAfterReturn':handle_valid,'creationOutcome':{'publicationOutcome':record.publication_outcome,'phase':record.phase,'finished':record.finished,'releaseAttempted':record.release_attempted,'releaseComplete':record.release_complete,'deletionAccepted':record.deletion_accepted,'disposalProof':record.disposal_proof,'secondary':[{'phase':phase,'type':type(cause).__name__,'text':str(cause)} for phase,cause in record.secondary]},'secondaryVisibleInPublicOutput':any(x in output.getvalue()+error.getvalue() for x in ('QA_EXACT_OWNED_CANDIDATE_DELETE_REFUSED','write-temp-cleanup','owned native creation closeout incomplete'))}
 (Q/'candidate-cleanup-owner-outcomes.json').write_text(json.dumps(row,indent=2))
 assert thrown is None and result==1
 if rejection=='pre-replace': assert output.getvalue().count('ledger-recovery:pre-replace-injected')==1
 else: assert 'status' in output.getvalue()
 assert row['originalLedgerUnchanged'] and row['lockAbsent'] and not row['ownerOpen'] and not row['ownerDirectories'] and not handle_valid
 assert row['secondaryVisibleInPublicOutput'],'Required secondary cleanup refusal is absent from the actual public result while the owned candidate remains'


def nf_owner_case(ledger_item, monkeypatch):
    writer, item = ledger_item
    _validator, owner = pin_validator(writer, monkeypatch)
    path = item / 'agent-runs.jsonl'
    path.write_bytes(b'owned original native bytes\n')
    original = owner._capture_file_snapshot(path, failure_id='NF-ORIGINAL')
    return owner, path, original


def nf_native_state(target, record):
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetHandleInformation.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    flags = wintypes.DWORD()
    return {'handleValid': bool(kernel.GetHandleInformation(record.handle, ctypes.byref(flags))),
            'ownerOpen': target._open, 'parentCount': len(target._directories),
            'phase': record.phase, 'finished': record.finished, 'holder': record.holder,
            'releaseAttempted': record.release_attempted, 'releaseComplete': record.release_complete,
            'deletionAccepted': record.deletion_accepted, 'outcome': record.publication_outcome,
            'secondary': [(phase, type(cause).__name__, str(cause)) for phase, cause in record.secondary]}


@pytest.mark.skipif(os.name != 'nt', reason='actual no-primary native finalization')
@pytest.mark.parametrize('fault', ['delete', 'post-delete', 'release-control'])
def test_nf_no_primary_propagates_first_actual_cause_after_finalization(ledger_item, monkeypatch, fault, tmp_path):
    owner, path, original = nf_owner_case(ledger_item, monkeypatch)
    candidate = path.with_suffix('.jsonl.tmp'); seen = []
    cause = KeyboardInterrupt('NF_RELEASE_CONTROL') if fault == 'release-control' else OSError(5, 'NF_FIRST_' + fault)
    real_close = owner.LifecycleWriteTarget._close
    def close(target, handle):
        real_close(target, handle)
        seen.append(handle)
        if fault == 'release-control' and getattr(target, '_qualified_record', None) is not None and handle == target._qualified_record.handle:
            raise cause
    monkeypatch.setattr(owner.LifecycleWriteTarget, '_close', close)
    with pytest.raises(BaseException) as raised:
        with owner.qualified_ledger_publication(path, original) as target:
            record = target.create_qualified_candidate(candidate, b'owned candidate bytes\n')
            parents = [row[1] for row in target._directories]
            if fault == 'delete':
                def refused(self, handle): raise cause
                monkeypatch.setattr(owner.LifecycleWriteTarget, '_windows_delete', refused)
            if fault == 'post-delete':
                verify = owner._verify_captured_parent_chain
                def refused(chain, failure_id):
                    if chain is record.scope and not candidate.exists(): raise cause
                    return verify(chain, failure_id)
                monkeypatch.setattr(owner, '_verify_captured_parent_chain', refused)
    actual = nf_native_state(target, record)
    actual.update(exceptionType=type(raised.value).__name__, exceptionText=str(raised.value),
                  exceptionNotes=getattr(raised.value, '__notes__', ()), candidateExists=candidate.exists(),
                  originalUnchanged=path.read_bytes() == original.data, closeAttempts=len(seen))
    (tmp_path / 'nf-no-primary.actual.json').write_text(json.dumps(actual, indent=2), encoding='utf8')
    assert raised.value is cause or raised.value.__cause__ is cause
    assert record.finished and record.release_attempted and len(seen) >= len(parents) + 1
    assert not actual['handleValid'] and not target._open and not target._directories
    assert path.read_bytes() == original.data


@pytest.mark.skipif(os.name != 'nt', reason='actual raised-primary and multiple native cleanup failures')
def test_nf_real_primary_identity_survives_disposal_candidate_and_parent_release(ledger_item, monkeypatch, tmp_path):
    owner, path, original = nf_owner_case(ledger_item, monkeypatch)
    candidate = path.with_suffix('.jsonl.tmp'); primary = ValueError('NF_REAL_PRIMARY'); closed = []
    real_close = owner.LifecycleWriteTarget._close
    def close(target, handle):
        real_close(target, handle); closed.append(handle)
        if handle in failing: raise OSError(6, 'NF_RELEASE_AFTER_REAL_CLOSE')
    def refused(self, handle): raise OSError(5, 'NF_DISPOSAL_REFUSED')
    with pytest.raises(ValueError) as raised:
        with owner.qualified_ledger_publication(path, original) as target:
            record = target.create_qualified_candidate(candidate, b'owned candidate bytes\n')
            parent_handles = [row[1] for row in target._directories]
            failing = {record.handle, parent_handles[0]}
            monkeypatch.setattr(owner.LifecycleWriteTarget, '_windows_delete', refused)
            monkeypatch.setattr(owner.LifecycleWriteTarget, '_close', close)
            raise primary
    actual = nf_native_state(target, record); actual.update(notes=getattr(primary, '__notes__', ()), closeAttempts=len(closed))
    (tmp_path / 'nf-raised.actual.json').write_text(json.dumps(actual, indent=2), encoding='utf8')
    assert raised.value is primary
    assert len(record.secondary) == 2 and set(parent_handles + [record.handle]).issubset(closed)
    assert sum('write-temp-cleanup' in note for note in primary.__notes__) == 1
    assert sum('write-target-release' in note for note in primary.__notes__) == 2
    assert not actual['handleValid'] and not target._open and not target._directories
    assert candidate.exists() and path.read_bytes() == original.data


@pytest.mark.skipif(os.name != 'nt', reason='actual unknown native settlement without primary')
@pytest.mark.parametrize('observation', ['raises', 'returns-unknown', 'diagnostic-raises'])
def test_nf_unknown_without_primary_is_visible_and_parent_release_cannot_mask_it(ledger_item, monkeypatch, observation, tmp_path):
    owner, path, original = nf_owner_case(ledger_item, monkeypatch)
    candidate = path.with_suffix('.jsonl.tmp'); cause = OSError(5, 'NF_OBSERVATION_REFUSED')
    real_close = owner.LifecycleWriteTarget._close
    def close(target, handle):
        real_close(target, handle)
        if handle == parent_handle: raise OSError(6, 'NF_PARENT_AFTER_REAL_CLOSE')
    with pytest.raises(BaseException) as raised:
        with owner.qualified_ledger_publication(path, original) as target:
            record = target.create_qualified_candidate(candidate, b'owned candidate bytes\n')
            parent_handle = target._directories[0][1]
            monkeypatch.setattr(owner.LifecycleWriteTarget, '_close', close)
            if observation == 'returns-unknown': path.write_bytes(b'changed destination\n')
            else:
                def refused(*a): raise cause
                monkeypatch.setattr(target, '_observe_qualified_placement', refused)
                if observation == 'diagnostic-raises':
                    secondary = target._creation_secondary
                    def delivery(record, primary, phase, native):
                        secondary(record, primary, phase, native)
                        raise ValueError('NF_DIAGNOSTIC_DELIVERY_REFUSED')
                    monkeypatch.setattr(target, '_creation_secondary', delivery)
    actual = nf_native_state(target, record); actual.update(exceptionType=type(raised.value).__name__,
        exceptionText=str(raised.value), notes=getattr(raised.value, '__notes__', ()), candidateExists=candidate.exists())
    (tmp_path / 'nf-unknown.actual.json').write_text(json.dumps(actual, indent=2), encoding='utf8')
    if observation == 'returns-unknown':
        assert isinstance(raised.value, owner.LifecycleError) and raised.value.failure_id == 'WI-LIFECYCLE-EFFECT'
        assert 'unknown' in str(raised.value)
    else: assert raised.value is cause or raised.value.__cause__ is cause
    assert record.publication_outcome == 'unknown' and record.phase == 'retained' and candidate.exists()
    assert not actual['handleValid'] and not target._open and not target._directories


def test_nf_main_forwards_primary_notes_once(ledger_item, monkeypatch, tmp_path):
    import io
    from contextlib import redirect_stdout, redirect_stderr
    writer, item = ledger_item; validator, _owner = pin_validator(writer, monkeypatch)
    primary = ValueError('NF_TOP_LEVEL_PRIMARY'); primary.add_note('NF_TOP_LEVEL_SECONDARY')
    def rejected(_args): raise primary
    monkeypatch.setattr(writer, 'command_init', rejected)
    output, error = io.StringIO(), io.StringIO()
    with redirect_stdout(output), redirect_stderr(error): result = invoke(writer, item, ['init'])
    actual = {'returncode': result, 'stdout': output.getvalue(), 'stderr': error.getvalue()}
    (tmp_path / 'nf-main.actual.json').write_text(json.dumps(actual, indent=2), encoding='utf8')
    assert result == 1 and not output.getvalue()
    assert error.getvalue().count('NF_TOP_LEVEL_PRIMARY') == 1 and error.getvalue().count('NF_TOP_LEVEL_SECONDARY') == 1


@pytest.mark.skipif(os.name != 'nt', reason='real public recovery exception receiving')
def test_nf_recovery_catch_forwards_actual_primary_and_cleanup_notes_once(tmp_path, monkeypatch):
    import io
    from contextlib import redirect_stdout, redirect_stderr
    fixture = load_script('tests/test_agent_run_ledger.py', 'nf_recovery_primary_fixture')
    item, previous, digest = fixture._prepare_recovery_writer_item(tmp_path)
    writer = fixture.load_ledger_module(); validator, owner = pin_validator(writer, monkeypatch)
    path = item / 'agent-runs.jsonl'; candidate = item / 'agent-runs.jsonl.tmp'; seen = []
    primary = ValueError('NF_RECOVERY_PRIMARY'); primary.add_note('NF_RECOVERY_ORIGINAL_NOTE')
    validate = validator.validate_work_item; delete = owner.LifecycleWriteTarget._windows_delete
    def reject(*args, **kwargs):
        if kwargs.get('ledger_path') is not None: raise primary
        return validate(*args, **kwargs)
    def refuse(target, handle):
        record = getattr(target, '_qualified_record', None)
        if target.path == path and record is not None and handle == record.handle:
            seen.append((target, record)); raise OSError(5, 'NF_RECOVERY_CLEANUP_REFUSED')
        return delete(target, handle)
    monkeypatch.setattr(validator, 'validate_work_item', reject)
    monkeypatch.setattr(owner.LifecycleWriteTarget, '_windows_delete', refuse)
    args = ['recover-invalid-closure', '--run-id', 'run-writer-recovery-control', '--target-run-id', 'run-writer-invalid-closer', '--target-event-sha256', digest, '--evidence', f'manual-check:run-writer-invalid-closer {digest}', '--started-at', '2026-08-17T00:02:00Z', '--updated-at', '2026-08-17T00:02:00Z']
    output, error = io.StringIO(), io.StringIO()
    with redirect_stdout(output), redirect_stderr(error): result = invoke(writer, item, args)
    actual = {'returncode': result, 'stdout': output.getvalue(), 'stderr': error.getvalue(),
              'originalUnchanged': path.read_bytes() == previous, 'candidateExists': candidate.exists(),
              'native': [nf_native_state(target, record) for target, record in seen]}
    (tmp_path / 'nf-recovery-primary.actual.json').write_text(json.dumps(actual, indent=2), encoding='utf8')
    assert result == 1 and not error.getvalue() and len(seen) == 1
    for text in ('NF_RECOVERY_PRIMARY', 'NF_RECOVERY_ORIGINAL_NOTE', 'secondary write-temp-cleanup: OSError'):
        assert output.getvalue().count(text) == 1
    assert actual['originalUnchanged'] and actual['candidateExists']
    assert len(seen[0][1].secondary) == 1 and 'NF_RECOVERY_CLEANUP_REFUSED' in str(seen[0][1].secondary[0][1])
    assert not actual['native'][0]['handleValid'] and not actual['native'][0]['ownerOpen']


@pytest.mark.skipif(os.name != 'nt', reason='native creator cleanup belongs to existing composer')
def test_nf_composer_records_each_cleanup_once_without_inventing_primary(ledger_item, monkeypatch, tmp_path):
    owner, path, original = nf_owner_case(ledger_item, monkeypatch)
    composer = owner.LifecycleOutcomeComposer(); token = owner._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.set(composer)
    real_close = owner.LifecycleWriteTarget._close
    def refuse(target, handle): raise OSError(5, 'NF_COMPOSER_DELETE_REFUSED')
    def close(target, handle):
        real_close(target, handle)
        if handle == record.handle: raise OSError(6, 'NF_COMPOSER_RELEASE_AFTER_CLOSE')
    try:
        with owner.qualified_ledger_publication(path, original) as target:
            record = target.create_qualified_candidate(path.with_suffix('.jsonl.tmp'), b'owned candidate bytes\n')
            monkeypatch.setattr(owner.LifecycleWriteTarget, '_windows_delete', refuse)
            monkeypatch.setattr(owner.LifecycleWriteTarget, '_close', close)
        bundle = composer.finalize()
        actual = nf_native_state(target, record)
        actual.update(primaryIsNone=bundle.primary is None,
                      phases=[row.phase for row in bundle.cleanup_failures],
                      occurrences={phase: len(rows) for phase, rows in composer._cleanup_occurrences.items()},
                      outwardType=type(composer.top_level(bundle)).__name__)
        (tmp_path / 'nf-composer.actual.json').write_text(json.dumps(actual, indent=2), encoding='utf8')
        assert bundle.primary is None and record.primary is None
        assert actual['occurrences'] == {'write-temp-cleanup': 1, 'write-target-release': 1}
        assert len(record.secondary) == 2 and composer.top_level(bundle) is not None
        assert not actual['handleValid'] and not target._open and not target._directories
    finally:
        owner._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.reset(token)


@pytest.mark.skipif(os.name != 'nt', reason='actual native origin and optional delivery receiving')
@pytest.mark.parametrize('origin', ['composer', 'body-composer', 'standalone', 'body-standalone', 'standalone-formatting'])
def test_native_cleanup_origin_survives_optional_delivery_and_later_release(ledger_item, monkeypatch, tmp_path, origin):
    owner, path, original = nf_owner_case(ledger_item, monkeypatch)
    candidate = path.with_suffix('.jsonl.tmp')
    native_delete = OSError(5, 'ORIGIN_NATIVE_DELETE_REFUSED')
    native_release = OSError(6, 'ORIGIN_NATIVE_RELEASE_AFTER_CLOSE')
    diagnostic = ValueError('ORIGIN_DIAGNOSTIC_DELIVERY_REFUSED')
    formatting = ValueError('ORIGIN_WRAPPING_REFUSED')
    body_primary = ValueError('ORIGIN_REAL_BODY')
    composed = origin in {'composer', 'body-composer'}
    has_body = origin.startswith('body-')
    state = {'bodyCompleted': False}; closed = []; deliveries = []
    real_close = owner.LifecycleWriteTarget._close
    real_delete = owner.LifecycleWriteTarget._windows_delete
    def refuse(target, handle):
        record = getattr(target, '_qualified_record', None)
        if target.path == path and record is not None and handle == record.handle:
            raise native_delete
        return real_delete(target, handle)
    def close(target, handle):
        real_close(target, handle); closed.append(handle)
        record = getattr(target, '_qualified_record', None)
        if record is not None and handle == record.handle: raise native_release
    def operation(_root):
        state['composer'] = owner._CURRENT_LIFECYCLE_OUTCOME_COMPOSER.get()
        with owner.qualified_ledger_publication(path, original) as target:
            record = target.create_qualified_candidate(candidate, b'owned candidate bytes\n')
            state.update(target=target, record=record, parents=[row[1] for row in target._directories])
            secondary = target._creation_secondary
            def deliver(record, primary, phase, cause):
                deliveries.append((phase, cause))
                secondary(record, primary, phase, cause)
                raise diagnostic  # Same object, two distinct acquired delivery events.
            monkeypatch.setattr(target, '_creation_secondary', deliver)
            monkeypatch.setattr(owner.LifecycleWriteTarget, '_windows_delete', refuse)
            monkeypatch.setattr(owner.LifecycleWriteTarget, '_close', close)
            if origin == 'standalone-formatting':
                def refused_wrapping(*args): raise formatting
                monkeypatch.setattr(target, '_failure', refused_wrapping)
            if has_body: raise body_primary
        state['bodyCompleted'] = True
        return 'proposed-success'
    observer = owner.LifecycleDiagnosticObserver() if composed else None
    thrown = None
    try:
        if composed:
            owner._lifecycle_participant(operation)(path.parents[3], diagnostic_observer=observer)
        else:
            operation(path.parents[3])
    except BaseException as exc:
        thrown = exc
    target, record = state['target'], state['record']
    actual = nf_native_state(target, record)
    actual.update(origin=origin, bodyCompleted=state['bodyCompleted'],
        raisedType=None if thrown is None else type(thrown).__name__,
        raisedCauseType=None if thrown is None or thrown.__cause__ is None else type(thrown.__cause__).__name__,
        notes=[] if thrown is None else list(getattr(thrown, '__notes__', ())),
        recordPrimaryIsBody=record.primary is body_primary, recordPrimaryIsNone=record.primary is None,
        originalUnchanged=path.read_bytes() == original.data, candidateExists=candidate.exists(),
        requiredHandlesAllClosed=set(state['parents'] + [record.handle]).issubset(closed),
        nativeDeleteRawOccurrences=sum(cause is native_delete for phase, cause in record.secondary),
        nativeReleaseRawOccurrences=sum(cause is native_release for phase, cause in record.secondary),
        deliveryRawOccurrences=sum(cause is diagnostic for phase, cause in record.secondary),
        formattingRawOccurrences=sum(cause is formatting for phase, cause in record.secondary),
        receiverInvocations=[phase for phase, cause in deliveries])
    if composed:
        composer = state['composer']; bundle = composer.finalize()
        actual.update(primaryKind=observer.snapshot.primaryKind, topLevelKind=observer.snapshot.topLevelKind,
            bundlePrimaryIsNone=bundle.primary is None, bundlePrimaryIsBody=bundle.primary is body_primary,
            cleanupOccurrences={phase: len(rows) for phase, rows in composer._cleanup_occurrences.items()},
            nativeComposerOccurrences={phase: sum(cause is expected for row, cause in composer._cleanup_occurrences[phase])
                for phase, expected in [('write-temp-cleanup', native_delete), ('write-target-release', native_release)]},
            deliveryComposerOccurrences={phase: sum(cause is diagnostic for row, cause in rows)
                for phase, rows in composer._cleanup_occurrences.items()})
    (tmp_path / 'native-origin.actual.json').write_text(json.dumps(actual, indent=2), encoding='utf8')
    assert actual['originalUnchanged'] and actual['candidateExists'] and actual['requiredHandlesAllClosed']
    assert not actual['handleValid'] and not actual['ownerOpen'] and actual['parentCount'] == 0
    assert actual['receiverInvocations'] == ['write-temp-cleanup', 'write-target-release']
    assert actual['nativeDeleteRawOccurrences'] == actual['nativeReleaseRawOccurrences'] == 1
    assert actual['deliveryRawOccurrences'] == 2
    assert actual['formattingRawOccurrences'] == (1 if origin == 'standalone-formatting' else 0)
    if composed:
        assert actual['nativeComposerOccurrences'] == {'write-temp-cleanup': 1, 'write-target-release': 1}
        assert actual['deliveryComposerOccurrences'] == {'write-temp-cleanup': 1, 'write-target-release': 1}
        assert actual['cleanupOccurrences'] == {'write-temp-cleanup': 2, 'write-target-release': 2}
        if has_body:
            assert thrown is body_primary and actual['bundlePrimaryIsBody'] and actual['recordPrimaryIsBody']
        else:
            assert actual['bodyCompleted'] and actual['bundlePrimaryIsNone'] and actual['recordPrimaryIsNone']
            assert actual['primaryKind'] == 'none' and actual['topLevelKind'] == 'cleanup-only'
    elif has_body:
        assert thrown is body_primary
    elif origin == 'standalone-formatting':
        assert thrown is native_delete
    else:
        assert thrown is native_delete or thrown.__cause__ is native_delete
    if not composed:
        assert sum('diagnostic delivery' in note for note in actual['notes']) == (3 if origin == 'standalone-formatting' else 2)


@pytest.mark.parametrize('callback_kind', ['missing', 'not-callable', 'none-result', 'invalid-sequence', 'failure', 'raises'])
def test_recovery_requires_selected_semantic_owner(tmp_path, callback_kind):
    fixture = load_script('tests/test_agent_run_ledger.py', 'required_semantic_owner_fixture')
    item, before, digest = fixture._prepare_recovery_writer_item(tmp_path)
    writer = fixture.load_ledger_module()
    requested = {
        'schemaVersion': 2, 'runId': 'required-semantic-owner-control', 'workItem': item.name,
        'role': 'lead', 'executionRole': 'main', 'status': 'completed', 'gate': 'none',
        'scope': ['ledger-recovery:closure-invalidation'], 'eventKind': 'closure-invalidation',
        'invalidatesRunId': 'run-writer-invalid-closer', 'invalidatesEventSha256': digest,
        'evidence': [{'kind': 'manual-check', 'ref': f'run-writer-invalid-closer {digest}'}],
        'startedAt': '2026-08-17T00:02:00Z', 'updatedAt': '2026-08-17T00:02:00Z',
    }
    def raises(*args):
        raise ValueError('WI-OWNED-SEMANTIC-REFUSAL: actual selected owner refused')
    callbacks = {'missing': None, 'not-callable': 7, 'none-result': lambda *args: None,
                 'invalid-sequence': lambda *args: [7],
                 'failure': lambda *args: ['WI-OWNED-SEMANTIC-REFUSAL: actual selected owner refused'],
                 'raises': raises}
    assert writer._commit_recovery_append(item, requested, callbacks[callback_kind],
        'own selected-owner test', None) == 1
    assert (item / 'agent-runs.jsonl').read_bytes() == before
    assert not (item / 'agent-runs.jsonl.tmp').exists()
    assert not (item / 'agent-runs.jsonl.lock').exists()


def test_manifest_scoped_public_disposition_uses_actual_candidate_without_full_item(tmp_path, monkeypatch):
    fixture = load_script('tests/test_invalid_current_suffix_disposition.py', 'selected_manifest_scope_fixture')
    writer = fixture.load_writer()
    validator, owner = pin_validator(writer, monkeypatch)
    artifacts, _unused, item, logical_path, target_line, recovery = fixture.fixture(validator, tmp_path)
    path = item / 'agent-runs.jsonl'
    before = artifacts.ledger_bytes_by_path[logical_path] + target_line
    path.write_bytes(before)
    manifest = tmp_path / 'selected-suffix-manifest.json'
    manifest.write_bytes(artifacts.ledger_manifest_bytes)
    assert not (item / 'status.md').exists()
    assert not validator._ledger_h1_live_participants_exist(tmp_path)
    captured = []
    actual_commit = writer._commit_recovery_append
    def observe_commit(selected_item, requested, callback, *args, **kwargs):
        def observe(candidate_path, previous, candidate):
            assert validator.read_ledger_bytes(candidate_path) == candidate
            captured.append((previous, candidate))
            if len(captured) == 1:
                (tmp_path / 'actual-candidate.jsonl').write_bytes(candidate)
                assert previous == before
            return callback(candidate_path, previous, candidate)
        return actual_commit(selected_item, requested, observe, *args, **kwargs)
    monkeypatch.setattr(writer, '_commit_recovery_append', observe_commit)
    argv = ['dispose-invalid-current', '--run-id', str(recovery['runId']),
        '--target-run-id', 'invalid-suffix-target', '--target-raw-line-ordinal', str(recovery['invalidatesRawLineOrdinal']),
        '--target-event-sha256', str(recovery['invalidatesEventSha256']), '--ledger-manifest', str(manifest),
        '--evidence', recovery['evidence'][0]['kind'] + ':' + recovery['evidence'][0]['ref'],
        '--started-at', '2026-10-22T00:00:00Z', '--updated-at', '2026-10-22T00:00:00Z']
    assert invoke(writer, item, argv) == 0
    committed = path.read_bytes()
    assert len(captured) == 1 and captured[0][1] == committed
    assert committed.startswith(before) and len(committed.splitlines()) == len(before.splitlines()) + 1
    assert (tmp_path / 'actual-candidate.jsonl').read_bytes() == committed
    def forbidden(self):
        raise AssertionError('native publication query during selected exact replay')
    monkeypatch.setattr(owner.LifecycleWriteTarget, '_select_qualified_backend', forbidden)
    assert invoke(writer, item, argv) == 0
    assert len(captured) == 2 and captured[1] == (committed, committed)
    assert path.read_bytes() == committed
    errors = validator.validate_work_item(item, strict_revise=False, validate_status_file=False)
    assert any('invalid-suffix-target:' in value for value in errors)
    context = validator.load_effective_ledger_view(tmp_path, item, logical_path)
    assert context.view is None and context.observation.activation_state == 'inactive'
    assert not (item / 'status.md').exists()
    assert not (item / 'agent-runs.jsonl.tmp').exists()
    assert not (item / 'agent-runs.jsonl.lock').exists()


def test_h1_public_exact_replay_uses_issued_native_identity(tmp_path, monkeypatch):
    from tests.test_mixed_current_ledger_recovery import minimal_staged_status
    producer = load_script('tests/test_ledger_h1_activation_writer.py', 'native_identity_h1_fixture')
    root = tmp_path / 'repo'
    lifecycle, _reader, request, items, paths = producer.fixture(root)
    receipt = lifecycle.apply_sealed_prefix_activation(root, request)
    assert receipt['state'] == 'apply' and receipt['replay'] is False
    writer = load_script('scripts/agent-run-ledger.py', 'native_identity_h1_writer')
    validator, owner = pin_validator(writer, monkeypatch)
    item = items[0]
    (item / 'status.md').write_text(minimal_staged_status(), encoding='utf-8')
    path = item / 'agent-runs.jsonl'
    prefix = path.read_bytes()
    before = validator.load_effective_ledger_view(root, item, paths[0])
    assert before.observation.activation_state == 'active' and before.view is not None
    assert invoke(writer, item, launch_args()) == 0
    assert invoke(writer, item, settle_args()) == 0
    committed = path.read_bytes()
    changed = committed[:-1] + b'\r\r\n'
    path.write_bytes(changed)
    states, acquired = [], []
    assert validator.validate_work_item(item, strict_revise=False, validate_status_file=False,
        obligation_state_out=states, ledger_acquisition_complete_out=acquired) == []
    assert acquired == [True]
    result = states[0]._current_result
    context = result.context
    assert context.observation.activation_state == 'active' and context.view == before.view
    native = validator._context_evaluation(context).selected_input.rows
    assert native[-1].event['runId'] == 'late-observed-terminal'
    assert native[-1].raw_line_ordinal == 5
    assert native[-1].raw_body_sha256 == context.rows[-1].raw_body_sha256
    assert result[1][-1].authority.terminal_eligible is True
    def forbidden(self):
        raise AssertionError('publication backend queried on genuine H1 replay')
    monkeypatch.setattr(owner.LifecycleWriteTarget, '_select_qualified_backend', forbidden)
    assert invoke(writer, item, settle_args()) == 0
    assert path.read_bytes() == changed and changed.startswith(prefix)
    assert not (item / 'agent-runs.jsonl.tmp').exists()
    assert not (item / 'agent-runs.jsonl.lock').exists()
