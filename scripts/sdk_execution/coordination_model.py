"""Optional public Agents Model over one settled typed coordination worker.

This is an Orchestrarium adapter, not an upstream-provided CodexModel.
The Model never invokes execute_admitted. Native startup uses the existing exact launch/selection/authority owners.
Actual Runner and OS/platform qualification remain separate acceptance.
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass
import hashlib
import inspect
from typing import Any

from .contracts import ExecutionRequest, json_text, strict_json
from .coordination import CoordinationInferenceRequest, function_call


def normalize_input(value: object, request: CoordinationInferenceRequest) -> None:
    if type(value) is list:
        if len(value) != 1 or type(value[0]) is not dict:
            raise ValueError("history is unavailable")
        item = value[0]
        if set(item) - {"role", "content", "type"} or item.get("role") != "user" or item.get("type", "message") != "message":
            raise ValueError("unsupported response input item")
        value = item.get("content")
        if type(value) is list:
            if len(value) != 1 or type(value[0]) is not dict or set(value[0]) != {"type", "text"} or value[0]["type"] != "input_text":
                raise ValueError("only one text input is supported")
            value = value[0]["text"]
    if type(value) is not str or strict_json(value, max_bytes=16384) != {"admitted_request_id": request.admitted_request_id}:
        raise ValueError("input does not identify the admitted request")


def _semantic_schema(value: object) -> object:
    if type(value) is dict:
        return {
            k: ({name: _semantic_schema(schema) for name, schema in v.items()}
                if k == "properties" and type(v) is dict else _semantic_schema(v))
            for k, v in value.items() if k not in {"title", "description"}
        }
    if type(value) is list:
        return [_semantic_schema(v) for v in value]
    return value


def normalized_usage_kwargs(raw):
    """Map only observed total fields for this new, one-turn native thread."""
    selected = {"requests": 1}
    totals = raw.get("total") if type(raw) is dict else None
    if type(totals) is dict:
        for source, target in (("inputTokens", "input_tokens"), ("outputTokens", "output_tokens"),
                               ("totalTokens", "total_tokens")):
            value = totals.get(source)
            if type(value) is int and value >= 0:
                selected[target] = value
    return selected


def validate_call(request, system_instructions, input, model_settings, tools,
                  output_schema, handoffs, tracing, previous_response_id, conversation_id, prompt):
    normalize_input(input, request)
    if system_instructions != request.system_instructions:
        raise ValueError("unadmitted system instructions")
    if output_schema is not None or type(handoffs) is not list or handoffs or previous_response_id is not None or conversation_id is not None or prompt is not None:
        raise ValueError("schema, handoff, stored conversation and remote prompt unavailable")
    if not callable(getattr(tracing, "is_disabled", None)) or tracing.is_disabled() is not True:
        raise ValueError("tracing must be disabled")
    if not is_dataclass(model_settings):
        raise ValueError("public ModelSettings required")
    settings = {f.name: getattr(model_settings, f.name) for f in fields(model_settings)}
    if settings.get("tool_choice") != "execute_admitted" or settings.get("parallel_tool_calls") is not False:
        raise ValueError("one forced execution tool required")
    for key, value in settings.items():
        if key in {"tool_choice", "parallel_tool_calls"} or value is None:
            continue  # Public optional defaults carry no selected effect.
        if key == "response_include" and value == []:
            continue
        raise ValueError("unsupported selected ModelSettings field: " + key)
    if type(tools) is not list or len(tools) != 1:
        raise ValueError("one tool required")
    tool = tools[0]
    expected = {"type": "object", "properties": {"request_id": {"type": "string"}},
                "required": ["request_id"], "additionalProperties": False}
    if (getattr(tool, "name", None) != "execute_admitted"
        or getattr(tool, "strict_json_schema", None) is not True
        or _semantic_schema(getattr(tool, "params_json_schema", None)) != expected):
        raise ValueError("unsupported execution tool schema")


class OneCoordinationCall:
    """One-use guard and current owner checks, independent of SDK defaults."""
    def __init__(self, request, worker, authority, *, inner_request):
        if type(request) is not CoordinationInferenceRequest or not callable(worker) or not callable(authority):
            raise ValueError("explicit coordination operation and owners required")
        if (type(inner_request) is not ExecutionRequest
            or hashlib.sha256(json_text(inner_request.to_dict()).encode()).hexdigest() != request.inner_request_sha256
            or any(getattr(request, k) != getattr(inner_request, k)
                   for k in ("work_item_id", "provider", "model", "effort", "cwd",
                             "account_binding", "coordinator_binding", "scope"))
            or len({request.external_dispatch_id, request.external_evidence_run_id,
                    inner_request.external_dispatch_id, inner_request.external_evidence_run_id}) != 4
            or request.artifact_id == inner_request.artifact_id):
            raise ValueError("distinct immutable outer/inner bindings required")
        self.request, self.worker, self.authority = request, worker, authority
        self.used = False
        self.usage_evidence = None

    def current(self, phase, reservation):
        if self.authority(self.request, phase, reservation) is not None:
            raise ValueError("authority must raise on denial and return None")

    async def infer(self, *args, **kwargs):
        validate_call(self.request, *args, **kwargs)
        if self.used:
            raise ValueError("coordination inference already consumed; no retry or resume")
        self.current("outer_start", self.request.outer_budget_id)
        self.used = True  # Before any awaited effect; failures/uncertainty never retry.
        observed = await self.worker(self.request)
        from process_supervision.sdk_worker import SdkWorkerObservation
        from process_supervision.process_runner import safe_serialize_result
        if type(observed) is not SdkWorkerObservation or not observed.is_bound_to(self.request):
            raise ValueError("owned worker observation required")
        p = safe_serialize_result(observed.process)
        if (p["outcome"] != "success" or p["targetExitCode"] != 0
            or any(p[k] is not True for k in ("treeEmpty", "ownershipConfirmed", "directReaped", "resourcesClosed"))
            or p["cleanupIssueCount"] or p["cleanupUncertain"] or p["stdoutTruncated"] or p["stderrTruncated"]
            or observed.protocol_error or observed.unavailable_reason or observed.cancel):
            raise ValueError("outer operation remains unsettled or unsuccessful")
        result = observed.result
        call = function_call(result)
        self.current("outer_settled", self.request.outer_budget_id)
        self.current("inner_ready", self.request.inner_budget_id)
        self.usage_evidence = {
            "raw": strict_json(result.usage_json) if result.usage_json is not None else None,
            "completeness": "observed-payload" if result.usage_json is not None else "unknown",
        }
        return call


def create_codex_model(*, request, worker, authority, inner_request):
    """Load actual optional SDK; never substitute fake SDK classes or launch."""
    from .runtime import SdkCoordinationWorker
    if type(worker) is not SdkCoordinationWorker or worker.validate_request() != request:
        raise ValueError("qualified existing coordination worker required")
    from .coordinator import _load_agents_sdk
    sdk, _ = _load_agents_sdk()
    from agents.items import ModelResponse
    from agents.usage import Usage
    from openai.types.responses import ResponseFunctionToolCall
    from agents.tool import FunctionTool
    from agents.models.interface import ModelTracing
    # Check construction capabilities before acquiring any worker/native effect.
    inspect.signature(ModelResponse).bind(output=[], usage=Usage(requests=1), response_id=None)
    ResponseFunctionToolCall(type="function_call", name="execute_admitted",
                             arguments='{"request_id":"capability-probe"}', call_id="capability-probe")
    call = OneCoordinationCall(request, worker, authority, inner_request=inner_request)

    class CodexCoordinationModel(sdk.Model):
        async def get_response(self, system_instructions, input, model_settings, tools,
                               output_schema, handoffs, tracing, *, previous_response_id=None,
                               conversation_id=None, prompt=None):
            if (not isinstance(model_settings, sdk.ModelSettings)
                or type(tools) is not list or any(not isinstance(t, FunctionTool) for t in tools)
                or not isinstance(tracing, ModelTracing)):
                raise ValueError("actual public SDK argument types required")
            item = await call.infer(system_instructions, input, model_settings, tools,
                                    output_schema, handoffs, tracing, previous_response_id,
                                    conversation_id, prompt)
            kwargs: dict[str, Any] = {
                "output": [ResponseFunctionToolCall(**item)],
                "usage": Usage(**normalized_usage_kwargs(call.usage_evidence["raw"])), "response_id": None,
            }
            # Normalized Usage defaults are not observed zero token counts.
            # Preserve raw field presence only where the public API supports it.
            if "raw_usage" in inspect.signature(ModelResponse).parameters:
                kwargs["raw_usage"] = call.usage_evidence["raw"]
            return ModelResponse(**kwargs)

        @property
        def usage_evidence(self):
            """Observed payload/unknown status; normalized defaults are not zero evidence."""
            from .contracts import json_text
            return strict_json(json_text(call.usage_evidence)) if call.usage_evidence is not None else None

        async def stream_response(self, *args, **kwargs):
            raise ValueError("coordination streaming is unavailable before effects")
            if False:
                yield None

    return CodexCoordinationModel()
