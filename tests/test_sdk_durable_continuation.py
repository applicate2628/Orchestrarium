"""Durable received continuation; no model, SDK import or process reconstruction."""
import json
import hashlib
from dataclasses import replace
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pytest
from test_sdk_native_continuation_runtime import fixture
from sdk_execution import runtime


def restore(req, selection, evidence='evidence-1'):
    return runtime.prepare_received_continuation_request(req, selection, predecessor_evidence_run_id=evidence)


def setup(tmp_path, monkeypatch):
    req, selection, prior, terminal = fixture(tmp_path, monkeypatch)
    return req, selection, terminal


def test_restore_without_retained_python_objects_and_claim_once(tmp_path, monkeypatch):
    req, selection, terminal = setup(tmp_path, monkeypatch)
    bound = restore(req, selection, terminal['runId'])
    assert bound.native_continuation.native_thread_id == 'fixture-thread'
    assert bound.native_continuation.native_turn_id == 'fixture-turn'
    assert bound.context_mode == 'continuation'
    selected = runtime.claim_launch(bound, selection, authority=lambda *a:None, started_at='2026-10-23T10:02:00Z')
    runtime.assert_current_launch(bound, selected, 'resume')
    other=replace(bound,external_dispatch_id='different-launch',external_evidence_run_id='different-result')
    with pytest.raises(ValueError,match='already_consumed'):
        runtime.claim_launch(other,selection,authority=lambda *a:None,started_at='2026-10-23T10:03:00Z')


def test_durable_concurrent_claims_have_one_winner(tmp_path,monkeypatch):
    req,selection,terminal=setup(tmp_path,monkeypatch)
    req=restore(req,selection,terminal['runId'])
    other=replace(req,external_dispatch_id='different-launch',external_evidence_run_id='different-result')
    def attempt(req):
        try:
            runtime.claim_launch(req,selection,authority=lambda *a:None,started_at='2026-10-23T10:03:00Z')
            return 'claimed'
        except ValueError:return 'denied'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt,[req,other]))==['claimed','denied']


@pytest.mark.parametrize('change',[{'scope':('another',)},{'account_binding':'other'},{'cwd':'D:\\other'},{'model':'other'}])
def test_restored_scope_must_match(tmp_path,monkeypatch,change):
    req,selection,terminal=setup(tmp_path,monkeypatch)
    with pytest.raises(ValueError):restore(replace(req,**change),selection,terminal['runId'])


def test_unknown_predecessor_never_launches(tmp_path,monkeypatch):
    req,selection,terminal=setup(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match='receipt_changed'):restore(req,selection,'unknown')


def test_replaced_artifact_refused_again_under_claim(tmp_path,monkeypatch):
    req,selection,terminal=setup(tmp_path,monkeypatch)
    bound=restore(req,selection,terminal['runId'])
    (Path(selection.work_item)/terminal['artifact']).write_bytes(b'changed')
    with pytest.raises(ValueError,match='artifact_changed'):
        runtime.claim_launch(bound,selection,authority=lambda *a:None,started_at='2026-10-23T10:03:00Z')


@pytest.mark.parametrize('mutation',['old','unknown-field','duplicate-key','wrong-context'])
def test_canonical_artifact_requires_complete_strict_native_receipt(tmp_path,monkeypatch,mutation):
    req,selection,terminal=setup(tmp_path,monkeypatch)
    target=Path(selection.work_item)/terminal['artifact']
    doc=json.loads(target.read_text())
    if mutation=='old':doc.pop('native_continuation')
    elif mutation=='unknown-field':doc['native_continuation']['extra']=True
    elif mutation=='wrong-context':doc['native_continuation']['context_sha256']='0'*64
    content=json.dumps(doc)
    if mutation=='duplicate-key':content=content.replace('"schema_version": 1','"schema_version": 1, "schema_version": 1')
    raw=(content+'\n').encode();target.write_bytes(raw)
    ledger=Path(selection.work_item)/'agent-runs.jsonl'
    rows=[json.loads(line) for line in ledger.read_text().splitlines()]
    for row in rows:
        if row['runId']==terminal['runId']:
            row['artifactRevision']=hashlib.sha256(raw).hexdigest();row['artifactSizeBytes']=len(raw)
    ledger.write_text(''.join(json.dumps(row)+'\n' for row in rows),encoding='utf-8')
    with pytest.raises(ValueError):restore(req,selection,terminal['runId'])


def test_fresh_python_process_restores_only_received_disk_evidence(tmp_path,monkeypatch):
    import subprocess
    import sys
    req,selection,terminal=setup(tmp_path,monkeypatch)
    program = """import sys,json
sys.path.insert(0,sys.argv[1])
from sdk_execution.contracts import ExecutionRequest
from sdk_execution.runtime import CodexRuntimeSelection,prepare_received_continuation_request
value=json.load(sys.stdin)
request=ExecutionRequest.from_dict(value['request'])
selection=CodexRuntimeSelection.from_dict(value['selection'])
bound=prepare_received_continuation_request(request,selection,predecessor_evidence_run_id=value['evidence'])
print(json.dumps(bound.native_continuation.to_dict()))
"""
    result=subprocess.run([sys.executable,'-B','-c',program,str(Path(runtime.__file__).parents[1])],
        input=json.dumps({'request':req.to_dict(),'selection':selection.to_dict(),'evidence':terminal['runId']}),
        text=True,capture_output=True,check=True)
    restored=json.loads(result.stdout)
    assert restored['native_thread_id']=='fixture-thread'
    assert restored['native_turn_id']=='fixture-turn'
    assert restored['prior_evidence_run_id']==terminal['runId']
