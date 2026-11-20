"""Per-effect reads use real authority checks, without cached ledger state."""
from test_sdk_child_lead_authority import fixture,decision_fixture
from sdk_execution import runtime
from process_supervision.process_runner import ProcessRunnerV1
from provider_prompt import ProviderOutputContext


def test_decision_effect_does_not_resolve_unrelated_task_catalog_again(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root=fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(runtime,'prepare_environment',lambda *a:({},ProviderOutputContext(())))
    with ProcessRunnerV1() as process:
        worker,projection,request=decision_fixture(owner,assignment,requests,selections,process)
        owner.attach_decision_worker(assignment,worker,projection)
        original=runtime._events; reads=[]
        def counted(selection):
            reads.append(selection.work_item)
            return original(selection)
        monkeypatch.setattr(runtime,'_events',counted)
        original_catalog=owner.child_catalog; catalogs=[]
        def catalog(current):
            catalogs.append(current.child_id)
            return original_catalog(current)
        monkeypatch.setattr(owner,'child_catalog',catalog)
        owner.assert_current(request,'diagnostic_model_effect')
        print('ACTUAL_LEDGER_READS',len(reads),'CATALOG_BUILDS',len(catalogs))
        assert len(catalogs)==1
