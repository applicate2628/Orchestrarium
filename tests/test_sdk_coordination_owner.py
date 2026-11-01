"""Existing ledger/launch-owner contract tests; no provider or credential reads."""
import asyncio,copy,dataclasses,hashlib,importlib.util,json,sys,tempfile,time,unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/"scripts"))
from sdk_execution import runtime
from sdk_execution.contracts import ExecutionRequest,json_text
from sdk_execution.coordination import CoordinationInferenceRequest,CoordinationInferenceResult,coordination_payload
from sdk_execution.coordination_model import OneCoordinationCall
from sdk_execution.codex import CodexReviewAdapter,ClientBinding
from test_sdk_coordination import request,intent,arguments,inner_request,Client
from process_supervision import process_runner as processes
from process_supervision.sdk_worker import run_sdk_worker
from sdk_execution.worker import encode_frame
from sdk_execution.receiving import terminal_payload, receive_terminal, _provider_owner
from provider_prompt import ProviderOutputContext


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


class CoordinationOwner(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator=load("_coord_owner_validator",R/"scripts/validate-work-item-state.py")
        cls.writer=load("_coord_owner_writer",R/"scripts/agent-run-ledger.py")

    def selection(self):
        return runtime.CodexRuntimeSelection(
            executable=str(Path(sys.executable).resolve()),executable_sha256="a"*64,
            codex_home=str(Path(tempfile.gettempdir())/"coordination-fixture-home"),
            auth_mode="codex-auth-file",expected_account_email="fixture@example.invalid",
            work_item=str(Path(tempfile.gettempdir())/"fixture-item"),
            ledger_max_events=None,ledger_max_bytes=None,job_memory_limit_bytes=268435456,
            config_overrides=runtime.CODEX_BOUNDED_REVIEW_OVERRIDES)

    def metadata(self):
        return runtime.selected_sdk_execution(request(),self.selection())

    def test_distinct_v3_selected_operation_and_legacy_v2(self):
        r=request();s=self.selection();m=self.metadata()
        self.assertEqual(m["schemaVersion"],3)
        self.assertEqual(m["operationKind"],"coordination-inference")
        self.assertEqual(self.validator.validate_sdk_execution(m,provider="codex",model=r.model,effort=r.effort),m)
        base=ExecutionRequest(**{k:v for k,v in r.to_dict().items() if k in ExecutionRequest.__dataclass_fields__ and k!="scope"},scope=r.scope)
        old=runtime.selected_sdk_execution(base,s)
        self.assertEqual(old["schemaVersion"],2);self.assertNotIn("operationKind",old)
        self.validator.validate_sdk_execution(old,provider="codex",model=r.model,effort=r.effort)

    def test_reservation_digest_and_revision_drift_refused(self):
        r=request();m=self.metadata()
        for field in ("operationKind","innerRequestSha256","outerBudgetBinding"):
            bad=dict(m);bad.pop(field)
            with self.subTest(field=field),self.assertRaises(ValueError):
                self.validator.validate_sdk_execution(bad,provider="codex",model=r.model,effort=r.effort)
        for changes in ({"schemaVersion":2},{"innerRequestSha256":"not-a-hash"},
                        {"outerBudgetBinding":m["innerBudgetBinding"]},{"extra":"field"}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                self.validator.validate_sdk_execution({**m,**changes},provider="codex",model=r.model,effort=r.effort)

    def event(self):
        r=request();args=runtime.build_launch_arguments(r,self.selection(),started_at="2026-10-26T00:00:00Z")
        return self.writer.build_event(self.writer.build_parser().parse_args(args),self.validator)

    def test_actual_writer_builds_main_lead_launch_not_review(self):
        event=self.event();errors=[];self.validator._validate_sdk_event(event,errors)
        self.assertEqual(errors,[])
        self.assertEqual((event["role"],event["executionRole"],event["assignedRole"]),("lead","main","lead"))
        self.assertEqual(event["sdkExecution"]["operationKind"],"coordination-inference")
        self.assertEqual(event["gate"],"none")

    def test_event_cannot_claim_external_reviewer_or_verdict(self):
        event=self.event()
        for k,v in (("executionRole","external-reviewer"),("role","external-reviewer"),
                    ("assignedRole","reviewer"),("gate","PASS")):
            bad={**event,k:v};errors=[];self.validator._validate_sdk_event(bad,errors)
            self.assertTrue(errors,(k,v))

    def test_current_launch_uses_exact_writer_digest_and_actor(self):
        r=request();s=self.selection();event=self.event()
        selected=replace(s,expected_launch_sha256=self.writer.launch_event_sha256(event,self.validator))
        with patch.object(runtime,"_events",return_value=(self.writer,self.validator,[event])),patch.object(runtime,"_verify_runtime") as verify:
            runtime.assert_current_launch(r,selected,"client_start")
            verify.assert_called_once_with(selected)
        for k,v in (("executionRole","external-reviewer"),("accountBinding","changed"),("scope",["changed"])):
            bad=copy.deepcopy(event)
            if k=="accountBinding":bad["sdkExecution"][k]=v
            else:bad[k]=v
            with self.subTest(field=k),patch.object(runtime,"_events",return_value=(self.writer,self.validator,[bad])),patch.object(runtime,"_verify_runtime") as verify,self.assertRaises((ValueError,runtime.RuntimeBindingError)):
                runtime.assert_current_launch(r,selected,"client_start")
            verify.assert_not_called()

    def test_native_factory_selects_typed_adapter_after_exact_launch_only(self):
        from types import SimpleNamespace
        from provider_prompt import assemble_external_prompt
        from sdk_execution.worker import _create_runtime_adapter
        from sdk_execution.coordination_codex import CodexCoordinationAdapter
        r=request();r=replace(r,prompt=assemble_external_prompt(r.prompt.encode()).decode())
        s=self.selection()
        args=runtime.build_launch_arguments(r,s,started_at="2026-10-26T00:00:00Z")
        event=self.writer.build_event(self.writer.build_parser().parse_args(args),self.validator)
        selected=replace(s,expected_launch_sha256=self.writer.launch_event_sha256(event,self.validator))
        sink=SimpleNamespace(authorize_from_thread=lambda *a:None,record_from_thread=lambda *a:None)
        with patch.object(runtime,"_events",return_value=(self.writer,self.validator,[event])),patch.object(runtime,"_verify_runtime"),patch.object(runtime,"prepare_environment",return_value=({},None)),patch.dict(runtime.os.environ,{},clear=False):
            result=_create_runtime_adapter(r,sink,selected.to_dict())
            self.assertIsInstance(result,CodexCoordinationAdapter)
            self.assertIsNone(result._client)  # No SDK construction/start occurred.
        bad={**event,"executionRole":"external-reviewer"}
        with patch.object(runtime,"_events",return_value=(self.writer,self.validator,[bad])),patch.object(runtime,"_verify_runtime"),patch.object(runtime,"prepare_environment") as env,self.assertRaises(runtime.RuntimeBindingError):
            _create_runtime_adapter(r,sink,selected.to_dict())
        env.assert_not_called()

    def test_coordinate_hash_binds_both_budget_and_inner_snapshot(self):
        r=request();s=self.selection();first=runtime.request_sha256(r,s)
        self.assertNotEqual(first,runtime.request_sha256(replace(r,outer_budget_id="changed"),s))
        other="b"*64
        payload=coordination_payload(r.operation_id,r.admitted_request_id,r.system_instructions,other)
        self.assertNotEqual(first,runtime.request_sha256(replace(r,inner_request_sha256=other,prompt=payload),s))

    def test_subscription_and_bounded_profile_required_before_launch(self):
        # A correctly prepared governance frame is required by the original owner.
        from provider_prompt import assemble_external_prompt
        r=request();r=replace(r,prompt=assemble_external_prompt(r.prompt.encode()).decode())
        s=self.selection();runtime.validate_admitted_request(r,s)
        for bad in (replace(s,auth_mode="codex-api-key",expected_account_email=None),
                    replace(s,config_overrides=runtime.CODEX_MCP_ISOLATION_OVERRIDES)):
            with self.subTest(selection=bad),self.assertRaises(runtime.RuntimeBindingError):
                runtime.validate_admitted_request(r,bad)

    def synthetic_observation(self,*,change=None,closed=True,wire_intent=None):
        """Reuse the existing receiving fixture pattern; not OS custody proof."""
        r=request();s=self.selection()
        observed={"schemaVersion":1,"adapter":"openai-codex","sdkVersion":"fixture-sdk","runtimeVersion":"fixture-runtime",
                  "model":r.model,"effort":r.effort,"sandboxMode":"read-only","approvalPolicy":"deny_all","accountBinding":r.account_binding}
        result=CoordinationInferenceResult(
            r,"completed" if closed else "incomplete","completed",intent(r),"fixture-thread","fixture-turn",
            sdk_execution_json=json_text(observed),protocol_closed=closed,
            cleanup_error=None if closed else "protocol_close_failed")
        with processes.ProcessRunnerV1() as owner:
            def simulated_run(process_request,*,dialogue):
                wire=result.to_dict()
                if wire_intent is not None:wire["intent_json"]=wire_intent
                frames=iter([encode_frame({"kind":"coordination_result","result":wire})])
                class Channel:
                    def write_line(self,value):pass
                    def read_line(self):
                        try:return next(frames)
                        except StopIteration:raise EOFError()
                try:dialogue.handler(Channel())
                except processes.ProcessSupervisionError as exc:
                    return processes._request_failure(process_request,exc,time.monotonic())
                failed=processes._request_failure(process_request,processes.ProcessSupervisionError("PSV1-INTERNAL","execution"),time.monotonic())
                clean=replace(failed,outcome="success",terminal_stage="completed",failure_id=None,target_exit_code=0,
                    resources_closed=True,policy_id="sdk-worker-v1",
                    tree=processes.TreeObservationV1("synthetic",True,"EMPTY",True,True,True,True))
                return change(clean) if change else clean
            with patch.object(owner,"run",side_effect=simulated_run):
                return run_sdk_worker(owner,r,environment=(),deadline_monotonic=time.monotonic()+10,
                    job_memory_limit_bytes=s.job_memory_limit_bytes,runtime_selection=s.to_dict(),authority=lambda *a:None)

    def test_receiving_is_typed_and_never_review_verdict(self):
        r=request();s=self.selection();ob=self.synthetic_observation()
        payload=terminal_payload(r,ob,output_context=ProviderOutputContext(()),admitted_sdk_execution=runtime.selected_sdk_execution(r,s))
        self.assertEqual((payload["schema"],payload["executionRole"],payload["status"],payload["gate"]),
            ("orchestrarium.coordination-inference.v1","main","completed","none"))
        self.assertFalse(payload["authorizing"]);self.assertEqual(payload["closesRunIds"],[])
        self.assertNotIn("review",json.loads(payload["resultText"])["evidence"])

    def test_receiving_refuses_unsettled_and_failedclose(self):
        for change,closed in ((lambda p:replace(p,resources_closed=False),True),
                             (lambda p:replace(p,tree=replace(p.tree,tree_empty=False)),True),(None,False)):
            with self.subTest(closed=closed),self.assertRaises(ValueError):
                terminal_payload(request(),self.synthetic_observation(change=change,closed=closed),
                    output_context=ProviderOutputContext(()),admitted_sdk_execution=self.metadata())

    def test_receiving_cancelled_process_is_blocked(self):
        payload=terminal_payload(request(),self.synthetic_observation(change=lambda p:replace(p,cancelled=True)),
            output_context=ProviderOutputContext(()),admitted_sdk_execution=self.metadata())
        self.assertEqual(payload["status"],"blocked");self.assertEqual(payload["gate"],"none")

    def test_invalid_completed_wire_intent_cannot_settle_ledger_or_execute_inner(self):
        r=request();good=json.loads(intent(r));owner=_provider_owner()
        cases=("{",json_text({**good,"extra":0}),json_text({**good,"tool":"other"}),
               json_text({**good,"request_id":"wrong"}))
        for text in cases:
            with self.subTest(intent=text),tempfile.TemporaryDirectory() as tmp:
                observation=self.synthetic_observation(wire_intent=text)
                self.assertIsNone(observation.result)
                self.assertEqual(observation.protocol_error,"PSV1-SDK-WORKER-PROTOCOL")
                ledger=Path(tmp)/"agent-runs.jsonl"
                before=(json_text(self.event())+"\n").encode()
                ledger.write_bytes(before)
                with patch.object(owner,"_ledger_owner",return_value=self.writer),patch.object(self.writer,"main") as settle:
                    with self.assertRaisesRegex(ValueError,"coordination worker pairing unavailable"):
                        receive_terminal(Path(tmp),r,observation,artifact="reviews/inference.json",
                            started_at="2026-10-26T00:00:00Z",updated_at="2026-10-26T00:00:01Z",
                            ledger_max_events=None,ledger_max_bytes=None,output_context=ProviderOutputContext(()))
                    settle.assert_not_called()
                self.assertEqual(ledger.read_bytes(),before)
                self.assertFalse((Path(tmp)/"reviews/inference.json").exists())
                inner_calls=[]
                async def worker(req):return observation
                async def attempt_inner():
                    call=OneCoordinationCall(r,worker,lambda *a:None,inner_request=inner_request())
                    dispatch=await call.infer(*arguments(r))
                    inner_calls.append(dispatch)
                with self.assertRaises(ValueError):asyncio.run(attempt_inner())
                self.assertEqual(inner_calls,[])

    def test_current_authority_rechecked_between_outer_settle_and_inner(self):
        for rejected in ("outer_settled","inner_ready"):
            phases=[];worker_calls=[]
            async def worker(r):worker_calls.append(r);return self.synthetic_observation()
            def authority(r,phase,reservation):
                phases.append((phase,reservation))
                if phase==rejected:raise PermissionError("synthetic revoked")
            call=OneCoordinationCall(request(),worker,authority,inner_request=inner_request())
            with self.subTest(phase=rejected),self.assertRaises(PermissionError):
                asyncio.run(call.infer(*arguments(request())))
            self.assertEqual(len(worker_calls),1)
            self.assertEqual(phases[-1][0],rejected)
            with self.assertRaisesRegex(ValueError,"already consumed"):
                asyncio.run(call.infer(*arguments(request())))

    def test_real_legacy_review_adapter_remains_review(self):
        r=request()
        base=ExecutionRequest(**{k:v for k,v in r.to_dict().items() if k in ExecutionRequest.__dataclass_fields__ and k!="scope"},scope=r.scope)
        text=json_text({"run_id":base.external_evidence_run_id,"artifact_id":base.artifact_id,"role":base.role,"verdict":"PASS","findings":[]})
        for failed in (False,True):
            client=Client(base,text=text,close_failure=failed)
            def factory(handler):
                client.handler=handler
                return ClientBinding(client,"fixture-sdk",client.read_configuration,client.list_mcp_status)
            a=CodexReviewAdapter(client_factory=factory,assert_current=lambda *a:None,
                verify_account=lambda r,p:r.account_binding,record=lambda o:None)
            result=asyncio.run(a.execute(base))
            self.assertTrue(client.closed)
            if failed:self.assertNotEqual(result.status,"completed")
            else:self.assertEqual(result.review.verdict,"PASS");self.assertEqual(client.turns,1)

    def test_legacy_executor_rejects_coordination_before_effect(self):
        from types import SimpleNamespace
        callbacks=[]
        authority=SimpleNamespace(resolve=lambda rid:callbacks.append(rid),
                                  assert_current=lambda *a:callbacks.append(a))
        executor=runtime.SdkReviewExecutor(request_id="fixture",authority=authority,
            selection=self.selection(),process_owner=None,source_environment={},artifact="reviews/fixture.json",
            deadline_monotonic=time.monotonic()+10,cancellation_probe=lambda:False,started_at="2026-10-26T00:00:00Z")
        with self.assertRaisesRegex(runtime.RuntimeBindingError,"review_request_required"):
            asyncio.run(executor.execute(request()))
        self.assertEqual(callbacks,[])


if __name__=="__main__":unittest.main()
