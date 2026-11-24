"""Stdlib offline tests. Fake transport is not real Runner/native qualification."""
import asyncio
from dataclasses import asdict, dataclass, replace
import json
import hashlib
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sdk_execution.contracts import ExecutionRequest, ExecutionResult, json_text
from sdk_execution.coordination import (
    CoordinationInferenceRequest, CoordinationInferenceResult, coordination_payload,
    function_call, intent_schema, validate_intent,
)
from sdk_execution.coordination_codex import CodexCoordinationAdapter
from sdk_execution.coordination_model import OneCoordinationCall, normalize_input, validate_call, normalized_usage_kwargs
from sdk_execution.codex import ClientBinding, CodexReviewAdapter
from sdk_execution.worker import (
    _create_runtime_adapter, decode_frame, encode_frame, read_execute_envelope,
    request_binding, serve_operation,
)
from sdk_execution.runtime import RuntimeBindingError


def inner_request():
    return ExecutionRequest(work_item_id="fixture-item",provider="codex",external_dispatch_id="inner-dispatch",
        external_evidence_run_id="inner-evidence",artifact_id="inner-artifact",role="reviewer",
        model="fixture-model",effort="high",cwd="/fixture/repo",account_binding="fixture-account",
        prompt="Review fixture arithmetic",coordinator_binding="host-fixture",scope=("fixture scope",))


def request(**changes):
    digest=hashlib.sha256(json_text(inner_request().to_dict()).encode()).hexdigest()
    body = coordination_payload("outer-operation", "inner-request", "Only dispatch the admitted request.",digest)
    values = dict(
        work_item_id="fixture-item", provider="codex", external_dispatch_id="outer-dispatch",
        external_evidence_run_id="outer-evidence", artifact_id="outer-artifact", role="lead",
        model="fixture-model", effort="high", cwd="/fixture/repo", account_binding="fixture-account",
        prompt=body, coordinator_binding="host-fixture", scope=("fixture scope",),
        operation_id="outer-operation", admitted_request_id="inner-request",
        outer_budget_id="outer-reservation", inner_budget_id="inner-reservation",
        inner_request_sha256=digest,
        system_instructions="Only dispatch the admitted request.",
    )
    values.update(changes)
    return CoordinationInferenceRequest(**values)


def intent(r):
    return json_text({"operation_id": r.operation_id, "request_id": r.admitted_request_id,
                      "request_sha256":r.inner_request_sha256,
                      "tool": "execute_admitted", "arguments": {"request_id": r.admitted_request_id}})


@dataclass
class Settings:
    tool_choice: object = "execute_admitted"
    parallel_tool_calls: object = False
    temperature: object = None
    store: object = None
    response_include: object = None


def arguments(r):
    tool = SimpleNamespace(name="execute_admitted", strict_json_schema=True,
        params_json_schema={"type": "object", "properties": {"request_id": {"type": "string", "title": "Request Id"}},
                            "required": ["request_id"], "additionalProperties": False})
    return [r.system_instructions, [{"role": "user", "content": json_text({"admitted_request_id": r.admitted_request_id})}],
            Settings(), [tool], None, [], SimpleNamespace(is_disabled=lambda: True), None, None, None]


class Client:
    """Only in-memory public transport shapes; starts no process or provider."""
    def __init__(self, r, text=None, close_failure=False, transport_failure=None, bad_thread=False, tool=False):
        self.r=r;self.turns=0;self.closed=False;self.params=None;self.close_failure=close_failure
        self.transport_failure=transport_failure;self.events=[];self.handler=None
        item={"id":"answer", "type":"agentMessage", "phase":"final_answer", "text":intent(r) if text is None else text}
        if tool:item={"id":"command", "type":"commandExecution", "status":"completed", "exitCode":0}
        self.events=[
            {"method":"item/completed", "payload":{"threadId":"wrong" if bad_thread else "thread-1","turnId":"turn-1","item":item}},
            {"method":"turn/completed", "payload":{"threadId":"thread-1","turn":{"id":"turn-1","status":"completed","items":[item],"itemsView":"summary"}}},
        ]
    def start(self):pass
    def initialize(self):return {"serverInfo":{"name":"codex","version":"fixture"},"userAgent":"codex/fixture"}
    def account_read(self,p):
        assert p=={"refreshToken":False}
        return {"account":{"type":"chatgpt"}}
    def read_configuration(self,p):
        return {"config":{"features":{"plugins":False,"apps":False,"multi_agent_v2":False},"agents":{"enabled":False},"mcp_servers":{}}}
    def list_mcp_status(self,p):return {"data":[],"nextCursor":None}
    def thread_start(self,p):
        return {"thread":{"id":"thread-1"},"model":self.r.model,"reasoningEffort":self.r.effort,
                "modelProvider":"openai","cwd":self.r.cwd,"approvalPolicy":"never","approvalsReviewer":"user",
                "sandbox":{"type":"readOnly","networkAccess":False}}
    def turn_start(self,t,i,p):
        self.turns+=1;self.params=p
        return {"turn":{"id":"turn-1","status":"inProgress","items":[]}}
    def next_turn_notification(self,t):
        if self.transport_failure:raise self.transport_failure
        return self.events.pop(0)
    def turn_interrupt(self,t,u):return {}
    def unregister_turn_notifications(self,t):pass
    def close(self):
        self.closed=True
        if self.close_failure:raise OSError("synthetic close failure")


def adapter(client, authority=lambda *a:None):
    def factory(handler):
        client.handler=handler
        return ClientBinding(client,"fixture-sdk",client.read_configuration,client.list_mcp_status)
    return CodexCoordinationAdapter(client_factory=factory,assert_current=authority,
        verify_account=lambda r,p:r.account_binding,record=lambda o:None)


class Contracts(unittest.TestCase):
    def test_roundtrip_and_bindings(self):
        r=request();self.assertEqual(CoordinationInferenceRequest.from_dict(r.to_dict()),r)
        got,selection=read_execute_envelope(encode_frame({"kind":"infer_coordination","request":r.to_dict()}))
        self.assertEqual(got,r);self.assertIsNone(selection)
        self.assertNotEqual(request_binding(r),request_binding(replace(r,outer_budget_id="another")))
        with self.assertRaises(ValueError):
            read_execute_envelope(encode_frame({"kind":"execute","request":r.to_dict()}))

    def test_bad_intents_rejected(self):
        r=request();good=json.loads(intent(r))
        cases=["", '{"tool":"execute_admitted","tool":"execute_admitted"}', json_text({**good,"extra":0}),
               json_text({**good,"tool":"other"}),json_text({**good,"arguments":{"request_id":"wrong"}}),
               json_text({**good,"request_id":"wrong"}), '{"refusal":"no"}']
        for text in cases:
            with self.subTest(text=text), self.assertRaises((ValueError, json.JSONDecodeError)):
                validate_intent(text,r)

    def test_completed_result_validates_intent_in_constructor_and_from_dict(self):
        r=request();good=json.loads(intent(r))
        valid=CoordinationInferenceResult(r,"completed","completed",intent(r),"thread","turn",protocol_closed=True)
        cases=("{",json_text({**good,"extra":0}),json_text({**good,"tool":"other"}),
               json_text({**good,"request_id":"wrong"}))
        for text in cases:
            with self.subTest(text=text,route="constructor"),self.assertRaises(ValueError):
                CoordinationInferenceResult(r,"completed","completed",text,"thread","turn",protocol_closed=True)
            wire={**valid.to_dict(),"intent_json":text}
            with self.subTest(text=text,route="from_dict"),self.assertRaises(ValueError):
                CoordinationInferenceResult.from_dict(wire)

    def test_budgets_and_role_not_review(self):
        for changes in ({"inner_budget_id":"outer-reservation"},{"role":"external-reviewer"},{"prompt":"unbound"}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):request(**changes)
        r=request(system_instructions=None,prompt=coordination_payload("outer-operation","inner-request",None,request().inner_request_sha256))
        self.assertIsNone(r.system_instructions)

    def test_changed_inner_snapshot_refused_before_worker(self):
        async def worker(r):raise AssertionError("must not run")
        with self.assertRaisesRegex(ValueError,"distinct immutable"):
            OneCoordinationCall(request(),worker,lambda *a:None,inner_request=replace(inner_request(),prompt="changed"))

    def test_actual_ids_derive_call_not_native_id(self):
        r=request();v=CoordinationInferenceResult(r,"completed","completed",intent(r),"thread","turn",protocol_closed=True)
        call=function_call(v);self.assertNotEqual(call["call_id"],"turn")
        self.assertNotEqual(call["call_id"],function_call(replace(v,native_turn_id="other"))["call_id"])
        self.assertNotIn("output",call);self.assertNotIn("status",call)
        self.assertEqual(CoordinationInferenceResult.from_dict(v.to_dict()),v)

    def test_semantic_response_input(self):
        r=request()
        for value in (' { "admitted_request_id" : "inner-request" } ',
                      [{"type":"message","role":"user","content":[{"type":"input_text","text":'{"admitted_request_id":"inner-request"}'}]}]):
            normalize_input(value,r)
        for value in ([],[{"role":"assistant","content":"x"}],[{"role":"user","content":"x"}]*2,
                      [{"role":"user","content":[] }],'{"admitted_request_id":"inner-request","extra":1}'):
            with self.subTest(value=value),self.assertRaises(ValueError):normalize_input(value,r)

    def test_unsupported_call_semantics_before_effects(self):
        r=request();args=arguments(r);validate_call(r,*args)
        for index,value in ((0,"changed"),(2,Settings(temperature=0.5)),(3,[]),(4,object()),(5,[object()]),
                            (6,SimpleNamespace(is_disabled=lambda:False)),(7,"prior"),(8,"conversation"),(9,{})):
            bad=list(args);bad[index]=value
            with self.subTest(index=index),self.assertRaises(ValueError):validate_call(r,*bad)
        for name in ("description", "title", "extra"):
            bad=arguments(r)
            bad[3][0].params_json_schema["properties"][name]={"type":"string"}
            with self.subTest(property=name),self.assertRaises(ValueError):validate_call(r,*bad)

    def test_native_factory_rejects_missing_runtime_before_sdk_or_effect(self):
        with self.assertRaisesRegex(RuntimeBindingError,"runtime_selection_required"):
            _create_runtime_adapter(request(),None,None)

    def test_review_schema_is_unchanged(self):
        from sdk_execution.contracts import review_schema
        base=ExecutionRequest(**{k:v for k,v in request().to_dict().items() if k in ExecutionRequest.__dataclass_fields__ and k!="scope"},scope=("fixture scope",))
        self.assertEqual(CodexReviewAdapter._output_schema(None,base),review_schema(base))

    def test_usage_does_not_invent_unknown_token_fields(self):
        self.assertEqual(normalized_usage_kwargs(None),{"requests":1})
        self.assertEqual(normalized_usage_kwargs({"total":{"inputTokens":7,"outputTokens":3,"totalTokens":10}}),
                         {"requests":1,"input_tokens":7,"output_tokens":3,"total_tokens":10})
        self.assertEqual(normalized_usage_kwargs({"total":{"inputTokens":True}}),{"requests":1})

    def test_synchronous_fake_transport_intent_and_failures(self):
        # Exercises the existing synchronous protocol body, not asyncio/Runner/OS.
        r=request()
        for changes in ({},{"text":"refusal"},{"close_failure":True},{"transport_failure":TimeoutError()},
                        {"transport_failure":OSError("synthetic transport crash")},{"bad_thread":True},{"tool":True}):
            with self.subTest(changes=changes):
                client=Client(r,**changes);a=adapter(client);a._request=r;a._used=True
                v=a._execute(r,None)
                self.assertTrue(client.closed)
                if not changes:
                    self.assertEqual(v.status,"completed")
                    self.assertEqual(client.turns,1)
                    self.assertEqual(function_call(v)["name"],"execute_admitted")
                else:
                    self.assertNotEqual(v.status,"completed")
                    with self.assertRaises(ValueError):function_call(v)

    def test_synchronous_revocation_before_native_turn(self):
        r=request();client=Client(r)
        def authority(request,effect):
            if effect=="turn_start":raise PermissionError("revoked")
        a=adapter(client,authority);a._request=r;a._used=True
        v=a._execute(r,None)
        self.assertEqual(client.turns,0);self.assertTrue(client.closed)
        self.assertNotEqual(v.status,"completed")


class AsyncContracts(unittest.IsolatedAsyncioTestCase):
    async def test_fake_transport_real_intent_one_turn(self):
        r=request();client=Client(r);a=adapter(client)
        result=await a.execute(r)
        self.assertEqual(result.status,"completed");self.assertEqual(client.turns,1)
        self.assertTrue(client.closed);self.assertEqual(client.params["outputSchema"],intent_schema(r))
        self.assertEqual(function_call(result)["name"],"execute_admitted")
        self.assertEqual(client.handler("item/commandExecution/requestApproval",{}),{"decision":"cancel"})

    async def test_bad_intent_transport_close_and_identity_failures(self):
        r=request()
        cases=({"text":"refusal"},{"close_failure":True},{"transport_failure":TimeoutError()},
               {"transport_failure":OSError("synthetic worker transport crash")},{"bad_thread":True},{"tool":True})
        for changes in cases:
            with self.subTest(changes=changes):
                c=Client(r,**changes);v=await adapter(c).execute(r)
                self.assertNotEqual(v.status,"completed");self.assertTrue(c.closed)
                with self.assertRaises(ValueError):function_call(v)

    async def test_revocation_before_native_turn(self):
        r=request();c=Client(r)
        def authority(request,effect):
            if effect=="turn_start":raise PermissionError("revoked")
        v=await adapter(c,authority).execute(r)
        self.assertNotEqual(v.status,"completed");self.assertEqual(c.turns,0);self.assertTrue(c.closed)

    async def test_one_call_guard_after_uncertain_worker_failure(self):
        r=request();calls=[]
        async def worker(req):
            calls.append(req);raise TimeoutError("uncertain outer")
        call=OneCoordinationCall(r,worker,lambda *a:None,inner_request=inner_request())
        with self.assertRaises(TimeoutError):await call.infer(*arguments(r))
        with self.assertRaisesRegex(ValueError,"already consumed"):await call.infer(*arguments(r))
        self.assertEqual(len(calls),1)

    async def test_explicit_store_is_rejected_before_authority_or_worker(self):
        r=request();workers=[];phases=[]
        async def worker(req):workers.append(req);raise AssertionError("must not run")
        for selected in (False,True):
            call=OneCoordinationCall(r,worker,lambda *a:phases.append(a),inner_request=inner_request())
            args=arguments(r);args[2]=Settings(store=selected)
            with self.subTest(store=selected),self.assertRaisesRegex(ValueError,"unsupported selected ModelSettings field: store"):
                await call.infer(*args)
            self.assertFalse(call.used)
        self.assertEqual(workers,[]);self.assertEqual(phases,[])

    async def test_unselected_store_none_preserves_worker_admission(self):
        r=request();workers=[]
        async def worker(req):workers.append(req);raise TimeoutError("synthetic outer stop")
        args=arguments(r);self.assertIsNone(args[2].store)
        call=OneCoordinationCall(r,worker,lambda *a:None,inner_request=inner_request())
        with self.assertRaisesRegex(TimeoutError,"synthetic outer stop"):
            await call.infer(*args)
        self.assertEqual(workers,[r])

    async def test_outer_revocation_starts_no_worker(self):
        r=request();calls=[]
        async def worker(req):calls.append(req)
        def denied(*a):raise PermissionError("revoked")
        with self.assertRaises(PermissionError):await OneCoordinationCall(r,worker,denied,inner_request=inner_request()).infer(*arguments(r))
        self.assertEqual(calls,[])

    async def test_new_worker_terminal_is_typed_not_review(self):
        r=request();writes=[]
        class A:
            async def execute(self,req):
                return CoordinationInferenceResult(req,"completed","completed",intent(req),"thread","turn",protocol_closed=True)
        async def read():await asyncio.Event().wait()
        async def write(data):writes.append(decode_frame(data))
        await serve_operation(r,A(),read,write)
        self.assertEqual(len(writes),1);self.assertEqual(writes[0]["kind"],"coordination_result")
        self.assertNotIn("review",writes[0]["result"])


if __name__=="__main__":
    unittest.main()
