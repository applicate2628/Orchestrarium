"""Fork claim/receiving/restart provenance, with no provider or native model."""
import json,hashlib
from pathlib import Path
from dataclasses import replace
import pytest
from test_sdk_durable_continuation import setup
from test_sdk_native_continuation_runtime import observed
from sdk_execution import runtime,receiving
from provider_prompt import ProviderOutputContext


def fork(req,selection,evidence):
    return runtime.prepare_received_continuation_request(req,selection,predecessor_evidence_run_id=evidence,context_mode='fork')


def claim(req,selection):
    return runtime.claim_launch(req,selection,authority=lambda *a:None,started_at='2026-10-23T10:02:00Z')


def receive(req,selection,monkeypatch,**changes):
    obs=observed(monkeypatch,req,selection,result_changes={'native_thread_id':'child-thread','native_turn_id':'child-turn',**changes})
    run=runtime.RuntimeRun(req,selection,ProviderOutputContext(()),obs)
    terminal=receiving.receive_runtime_run(run,artifact='child.json',started_at='2026-10-23T10:02:00Z',updated_at='2026-10-23T10:03:00Z')
    return terminal,json.loads((Path(selection.work_item)/'child.json').read_text())


def mutate_receipt(selection,terminal,transform):
    file=Path(selection.work_item)/terminal['artifact'];doc=json.loads(file.read_text());transform(doc['native_continuation'])
    raw=(json.dumps(doc)+'\n').encode();file.write_bytes(raw)
    ledger=Path(selection.work_item)/'agent-runs.jsonl';rows=[json.loads(l) for l in ledger.read_text().splitlines()]
    for row in rows:
        if row['runId']==terminal['runId']:row.update(artifactRevision=hashlib.sha256(raw).hexdigest(),artifactSizeBytes=len(raw))
    ledger.write_text(''.join(json.dumps(row)+'\n' for row in rows),encoding='utf-8')


def test_distinct_forks_do_not_consume_source_continuation_but_same_intent_does_not_replay(tmp_path,monkeypatch):
    req,selection,terminal=setup(tmp_path,monkeypatch);bound=fork(req,selection,terminal['runId'])
    claim(bound,selection)
    with pytest.raises(ValueError,match='existing_launch'):claim(bound,selection)
    another=replace(bound,external_dispatch_id='fork-two',external_evidence_run_id='fork-two-result',artifact_id='fork-two-artifact')
    claim(another,selection)
    continuation=replace(bound,context_mode='continuation',external_dispatch_id='continue-one',external_evidence_run_id='continue-one-result',artifact_id='continue-artifact')
    claim(continuation,selection)
    assert 'forkSourceSha256' in runtime.selected_sdk_execution(bound,selection)
    assert 'continuationSourceSha256' not in runtime.selected_sdk_execution(bound,selection)


def test_completed_fork_receipt_has_new_thread_and_derived_depth_and_is_restartable(tmp_path,monkeypatch):
    req,selection,terminal=setup(tmp_path,monkeypatch)
    assert json.loads((Path(selection.work_item)/terminal['artifact']).read_text())['native_continuation']['session_depth']==0
    bound=fork(req,selection,terminal['runId']);selected=claim(bound,selection)
    child,doc=receive(bound,selected,monkeypatch)
    assert child['status']=='completed' and child['gate']=='none' and child['authorizing'] is False
    assert doc['native_continuation']['session_depth']==1
    new=replace(req,external_dispatch_id='grandchild',external_evidence_run_id='grandchild-result',artifact_id='grandchild-artifact')
    continued=runtime.prepare_received_continuation_request(new,selection,predecessor_evidence_run_id=child['runId'])
    assert continued.native_continuation.native_thread_id=='child-thread'
    assert runtime.native_session_depth(continued,selection)==1
    branched=fork(new,selection,child['runId'])
    assert runtime.native_session_depth(branched,selection)==2


@pytest.mark.parametrize('bad',[{'native_thread_id':'fixture-thread'},{'native_turn_id':'fixture-turn'}])
def test_fork_receiving_cannot_claim_source_thread_or_old_turn_as_new(tmp_path,monkeypatch,bad):
    req,selection,terminal=setup(tmp_path,monkeypatch);bound=fork(req,selection,terminal['runId']);selected=claim(bound,selection)
    child,doc=receive(bound,selected,monkeypatch,**bad)
    assert child['status']=='blocked' and 'native_continuation' not in doc


@pytest.mark.parametrize('depth',[True,-1,1.5,'2'])
def test_depth_requires_exact_nonnegative_integer(tmp_path,monkeypatch,depth):
    req,selection,terminal=setup(tmp_path,monkeypatch)
    mutate_receipt(selection,terminal,lambda n:n.update(session_depth=depth))
    with pytest.raises(ValueError,match='session_depth'):fork(req,selection,terminal['runId'])


@pytest.mark.parametrize('legacy',[True,False])
def test_unknown_depth_propagates_without_blocking_or_false_zero(tmp_path,monkeypatch,legacy):
    req,selection,terminal=setup(tmp_path,monkeypatch)
    def change(n):
        if legacy:n.update(schema_version=1);n.pop('session_depth')
        else:n.update(session_depth=None)
    mutate_receipt(selection,terminal,change)
    bound=fork(req,selection,terminal['runId']);selected=claim(bound,selection)
    child,doc=receive(bound,selected,monkeypatch)
    assert child['status']=='completed' and doc['native_continuation']['session_depth'] is None


def test_metadata_sources_are_exclusive_and_restricted_to_consultant_readonly(tmp_path,monkeypatch):
    req,selection,terminal=setup(tmp_path,monkeypatch);bound=fork(req,selection,terminal['runId'])
    value=runtime.selected_sdk_execution(bound,selection);validator=runtime._ledger(selection)[1]
    assert validator.validate_sdk_execution(value,provider='codex',model=req.model,effort=req.effort)==value
    with pytest.raises(ValueError,match='mutually exclusive'):
        validator.validate_sdk_execution({**value,'continuationSourceSha256':'0'*64},provider='codex',model=req.model,effort=req.effort)


def test_failed_fork_retains_observed_child_without_restart_or_replay_authority(tmp_path,monkeypatch):
    req,selection,terminal=setup(tmp_path,monkeypatch)
    bound=fork(req,selection,terminal['runId']);selected=claim(bound,selection)
    child,doc=receive(bound,selected,monkeypatch,status='failed',provider_status='failed',execution_error='fixture-failure')
    assert child['status']=='blocked' and 'native_continuation' not in doc
    assert doc['observed_native_session']=={'thread_id':'child-thread','turn_id':'child-turn'}
    with pytest.raises(ValueError,match='existing_launch'):claim(bound,selection)
    new=replace(req,external_dispatch_id='later',external_evidence_run_id='later-result',artifact_id='later-artifact')
    with pytest.raises(ValueError,match='receipt_changed'):fork(new,selection,child['runId'])
