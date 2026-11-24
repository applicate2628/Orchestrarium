"""Fresh received decisions recover from canonical evidence without native sessions."""
import json
from unittest.mock import patch
import pytest
from test_sdk_child_lead_authority import fixture, INSTANT
import test_sdk_persistent_child_lead as prior
from sdk_execution import runtime
from provider_prompt import ProviderOutputContext
from process_supervision.process_runner import ProcessRunnerV1

def fresh_fixture(tmp_path, monkeypatch):
    values=fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(runtime,"prepare_environment",lambda *a:({},ProviderOutputContext(())))
    return values

def candidate(*args, **kwargs):
    return prior.candidate(*args,decision_session_mode="fresh-handoff",**kwargs)

def receive(*args, **kwargs):
    with patch.object(prior,"candidate",side_effect=lambda *a,**kw: ORIGINAL(*a,decision_session_mode="fresh-handoff",**kw)):
        return prior.receive_decision(*args,**kwargs)

ORIGINAL=prior.candidate

def test_received_fresh_intent_recovers_and_blocks_new_inference_until_task_claim(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root=fresh_fixture(tmp_path,monkeypatch)
    with ProcessRunnerV1() as process:
        run,terminal,projection=receive(owner,assignment,requests,selections,process,monkeypatch)
        worker,request,_=candidate(owner,assignment,requests,selections,process,"next",projection)
        assert request.native_continuation is None
        assert owner.recover_child_decision(assignment,worker,projection)["request_id"]=="task-one"
        owner.attach_decision_worker(assignment,worker,projection)
        with pytest.raises(ValueError,match="intent_pending"):
            runtime.claim_launch(request,worker._selection,authority=owner.assert_current,started_at=INSTANT)
        runtime.claim_launch(requests["task-one"],selections["task-one"],authority=owner.assert_current,started_at=INSTANT)
        assert owner.recover_child_decision(assignment,worker,projection) is None
        with pytest.raises(ValueError,match="existing_launch"):
            runtime.claim_launch(requests["task-one"],selections["task-one"],authority=owner.assert_current,started_at=INSTANT)

def test_unknown_decision_does_not_relaunch_or_block_independent_task(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root=fresh_fixture(tmp_path,monkeypatch)
    with ProcessRunnerV1() as process:
        worker,request,projection=candidate(owner,assignment,requests,selections,process)
        owner.attach_decision_worker(assignment,worker,projection)
        runtime.claim_launch(request,worker._selection,authority=owner.assert_current,started_at=INSTANT)
        next_worker,next_request,_=candidate(owner,assignment,requests,selections,process,"next",projection)
        outcome=owner.recover_child_decision(assignment,next_worker,projection)
        assert outcome["status"]=="needs-reconciliation"
        assert outcome["decision_run_ids"]==[request.external_dispatch_id]
        owner.attach_decision_worker(assignment,next_worker,projection)
        with pytest.raises(ValueError,match="needs_reconciliation"):
            runtime.claim_launch(next_request,next_worker._selection,authority=owner.assert_current,started_at=INSTANT)
        runtime.claim_launch(requests["task-one"],selections["task-one"],authority=owner.assert_current,started_at=INSTANT)

def test_consumed_old_context_does_not_poison_new_context(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root=fresh_fixture(tmp_path,monkeypatch)
    with ProcessRunnerV1() as process:
        receive(owner,assignment,requests,selections,process,monkeypatch)
        worker,request,projection=candidate(owner,assignment,requests,selections,process,"next",max_events=8192)
        assert owner.recover_child_decision(assignment,worker,projection)["reason"]=="decision-context-changed"
        runtime.claim_launch(requests["task-one"],selections["task-one"],authority=owner.assert_current,started_at=INSTANT)
        assert owner.recover_child_decision(assignment,worker,projection) is None

def test_tampered_fresh_artifact_cannot_authorize_recovery(tmp_path,monkeypatch):
    from pathlib import Path
    owner,assignment,requests,selections,root=fresh_fixture(tmp_path,monkeypatch)
    with ProcessRunnerV1() as process:
        receive(owner,assignment,requests,selections,process,monkeypatch)
        worker,request,projection=candidate(owner,assignment,requests,selections,process,"next")
        (Path(assignment.child_work_item)/"decision-one.json").write_bytes(b"{}")
        with pytest.raises(ValueError,match="current_ledger_invalid"):
            owner.recover_child_decision(assignment,worker,projection)


def test_two_restored_hosts_recover_one_intent_and_claim_task_once(tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    owner,assignment,requests,selections,root=fresh_fixture(tmp_path,monkeypatch)
    other=runtime.ChildLeadAuthority(root_authority=owner._root_authority,root_selection=root,
        child_id=assignment.child_id,selections=selections,closure_data=owner._closure_data,
        terminal_instant=INSTANT,repository_root=tmp_path)
    with ProcessRunnerV1() as process:
        receive(owner,assignment,requests,selections,process,monkeypatch)
        for index,host in enumerate((owner,other)):
            worker,request,projection=candidate(host,assignment,requests,selections,process,"restored-"+str(index))
            assert host.recover_child_decision(assignment,worker,projection)["request_id"]=="task-one"
        barrier=Barrier(2)
        def claim(host):
            barrier.wait()
            try:
                return runtime.claim_launch(requests["task-one"],selections["task-one"],authority=host.assert_current,started_at=INSTANT)
            except Exception as exc:
                return exc
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(claim,(owner,other)))
        assert sum(not isinstance(value,Exception) for value in outcomes)==1,outcomes
        loser=next(value for value in outcomes if isinstance(value,Exception))
        assert (isinstance(loser,ValueError) or type(loser).__name__=="LifecycleError"),repr(loser)
        with pytest.raises(ValueError,match="existing_launch"):
            runtime.claim_launch(requests["task-one"],selections["task-one"],authority=other.assert_current,started_at=INSTANT)
        rows=runtime._events(selections["task-one"])[2]
        assert sum(row["runId"]==requests["task-one"].external_dispatch_id for row in rows)==1
