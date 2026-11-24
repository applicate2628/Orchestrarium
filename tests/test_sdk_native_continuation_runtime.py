"""Retained native continuation evidence and atomic same-ledger claim; offline."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from test_sdk_runtime import fixture as base
from test_sdk_claude_consultant_receiving import observed
from sdk_execution import runtime, receiving
from provider_prompt import ProviderOutputContext


def fixture(tmp_path,monkeypatch):
    req,selection=base(tmp_path)
    req=runtime.prepare_codex_request(replace(req,role='consultant',result_kind='task'))
    selected=runtime.claim_launch(req,selection,authority=lambda *a:None,started_at='2026-10-23T10:00:00Z')
    obs=observed(monkeypatch,req,selected)
    run=runtime.RuntimeRun(req,selected,ProviderOutputContext(()),obs)
    terminal=receiving.receive_runtime_run(run,artifact='prior.json',started_at='2026-10-23T10:00:00Z',updated_at='2026-10-23T10:01:00Z')
    new=replace(req,external_dispatch_id='next-dispatch',external_evidence_run_id='next-evidence',artifact_id='next-artifact',prompt=req.prompt+'\nContinue with this new task.')
    return new,selection,run,terminal


def prepare(tmp_path,monkeypatch):
    new,selection,run,terminal=fixture(tmp_path,monkeypatch)
    return runtime.prepare_continuation_request(new,selection,run,terminal),selection,run,terminal


def claim(req,selection,run,terminal):
    return runtime.claim_launch(req,selection,authority=lambda *a:None,started_at='2026-10-23T10:02:00Z',previous_run=run,previous_terminal=terminal)


def test_derived_real_observed_ids_and_atomic_prior_consumption(tmp_path,monkeypatch):
    req,selection,run,terminal=prepare(tmp_path,monkeypatch)
    assert req.native_continuation.native_thread_id==run.observation.result.native_thread_id
    assert req.context_mode=='continuation'
    admitted=claim(req,selection,run,terminal)
    runtime.assert_current_launch(req,admitted,'resume')
    other=replace(req,external_dispatch_id='other-dispatch',external_evidence_run_id='other-evidence',artifact_id='other-artifact')
    with pytest.raises(ValueError,match='already_consumed'):claim(other,selection,run,terminal)


def test_two_distinct_successors_compete_under_existing_ledger_transaction(tmp_path,monkeypatch):
    req,selection,run,terminal=prepare(tmp_path,monkeypatch)
    other=replace(req,external_dispatch_id='other-dispatch',external_evidence_run_id='other-evidence',artifact_id='other-artifact')
    def attempt(value):
        try:claim(value,selection,run,terminal);return 'claimed'
        except ValueError:return 'denied'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,[req,other]))
    assert sorted(results)==['claimed','denied']


@pytest.mark.parametrize('change',[{'account_binding':'other'},{'scope':('other',)},{'model':'other'}])
def test_continuation_cannot_change_selected_context(tmp_path,monkeypatch,change):
    new,selection,run,terminal=fixture(tmp_path,monkeypatch)
    with pytest.raises(ValueError):runtime.prepare_continuation_request(replace(new,**change),selection,run,terminal)


def test_artifact_changed_after_preparation_blocks_atomic_claim(tmp_path,monkeypatch):
    req,selection,run,terminal=prepare(tmp_path,monkeypatch)
    (Path(selection.work_item)/'prior.json').write_bytes(b'changed')
    with pytest.raises(ValueError):claim(req,selection,run,terminal)


def test_raw_linkage_cannot_override_durable_received_native_identity(tmp_path,monkeypatch):
    req,selection,run,terminal=prepare(tmp_path,monkeypatch)
    forged=replace(req,native_continuation=replace(req.native_continuation,native_thread_id='invented-thread'))
    with pytest.raises(ValueError,match='observed_binding_mismatch'):claim(forged,selection,None,None)


def test_receipt_copy_cannot_change_prior_status(tmp_path,monkeypatch):
    new,selection,run,terminal=fixture(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match='receipt_changed'):
        runtime.prepare_continuation_request(new,selection,run,{**terminal,'status':'blocked'})


@pytest.mark.parametrize('forgery',['result','selection'])
def test_retained_predecessor_cannot_be_forged(tmp_path,monkeypatch,forgery):
    new,selection,run,terminal=fixture(tmp_path,monkeypatch)
    if forgery=='result':
        run=replace(run,observation=replace(run.observation,result=replace(run.observation.result,native_thread_id='invented-thread')))
    else:
        run=replace(run,selection=replace(run.selection,codex_home=str(tmp_path/'another-home')))
    with pytest.raises(ValueError):runtime.prepare_continuation_request(new,selection,run,terminal)
