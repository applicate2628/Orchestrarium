"""Closed coordination-inference contract; never a review or tool executor."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import hashlib
from typing import Any

from .contracts import ExecutionRequest, Observation, json_text, strict_json


def _text(value: object) -> str:
    if type(value) is not str or not value.strip() or len(value.encode()) > 4096:
        raise ValueError("invalid coordination identity")
    return value


@dataclass(frozen=True, slots=True)
class CoordinationInferenceRequest(ExecutionRequest):
    operation_id: str = ""
    admitted_request_id: str = ""
    outer_budget_id: str = ""
    inner_budget_id: str = ""
    inner_request_sha256: str = ""
    system_instructions: str | None = None

    def __post_init__(self) -> None:
        # Validate base fields as the exact existing type; its validator iterates
        # dataclass fields and must not mistake new optional metadata for text.
        ExecutionRequest(**{f.name: getattr(self, f.name) for f in fields(ExecutionRequest)})
        if self.provider != "codex" or self.role != "lead":
            raise ValueError("explicit Codex coordination operation required")
        for value in (self.operation_id, self.admitted_request_id,
                      self.outer_budget_id, self.inner_budget_id):
            _text(value)
        if self.outer_budget_id == self.inner_budget_id:
            raise ValueError("outer and inner turn reservations must differ")
        if (type(self.inner_request_sha256) is not str or len(self.inner_request_sha256) != 64
            or any(c not in "0123456789abcdef" for c in self.inner_request_sha256)):
            raise ValueError("immutable inner request digest required")
        if self.system_instructions is not None:
            _text(self.system_instructions)
        # Prompt is composed and admitted by the Host, not changed by Model.
        if not self.prompt.endswith(self.inference_payload):
            raise ValueError("admitted prompt does not bind coordination input")

    @property
    def inference_payload(self) -> str:
        return coordination_payload(self.operation_id, self.admitted_request_id,
                                    self.system_instructions, self.inner_request_sha256)

    @classmethod
    def from_dict(cls, value: object) -> CoordinationInferenceRequest:
        if type(value) is not dict or set(value) != {f.name for f in fields(cls)}:
            raise ValueError("invalid coordination request fields")
        if type(value["scope"]) is not list:
            raise ValueError("invalid coordination scope")
        return cls(**{**value, "scope": tuple(value["scope"])})


def coordination_payload(operation_id, request_id, system_instructions, inner_request_sha256):
    """Host composes this before admission; Model never modifies the prompt."""
    return json_text({
        "operation_id": operation_id, "system_instructions": system_instructions,
        "input": {"admitted_request_id": request_id}, "only_tool": "execute_admitted",
        "request_sha256": inner_request_sha256,
        "instruction": "Return one dispatch intent matching the schema. Do not execute any tool.",
    })


def intent_schema(request: CoordinationInferenceRequest) -> dict[str, Any]:
    return {
        "type": "object", "additionalProperties": False,
        "required": ["operation_id", "request_id", "request_sha256", "tool", "arguments"],
        "properties": {
            "operation_id": {"type": "string", "const": request.operation_id},
            "request_id": {"type": "string", "const": request.admitted_request_id},
            "request_sha256": {"type": "string", "const": request.inner_request_sha256},
            "tool": {"type": "string", "const": "execute_admitted"},
            "arguments": {
                "type": "object", "additionalProperties": False,
                "required": ["request_id"],
                "properties": {"request_id": {"type": "string", "const": request.admitted_request_id}},
            },
        },
    }


def validate_intent(text: str, request: CoordinationInferenceRequest) -> str:
    value = strict_json(text, max_bytes=min(request.max_output_bytes, 16384))
    expected = {"operation_id": request.operation_id, "request_id": request.admitted_request_id,
                "request_sha256": request.inner_request_sha256,
                "tool": "execute_admitted", "arguments": {"request_id": request.admitted_request_id}}
    if value != expected or type(value) is not dict:
        raise ValueError("refused or mismatched coordination intent")
    return json_text(value)


@dataclass(frozen=True, slots=True)
class CoordinationInferenceResult:
    request: CoordinationInferenceRequest
    status: str
    provider_status: str | None = None
    intent_json: str | None = None
    native_thread_id: str | None = None
    native_turn_id: str | None = None
    sdk_execution_json: str | None = None
    observations: tuple[Observation, ...] = ()
    usage_json: str | None = None
    execution_error: str | None = None
    capture_error: str | None = None
    cleanup_error: str | None = None
    protocol_closed: bool = False

    def __post_init__(self) -> None:
        if type(self.request) is not CoordinationInferenceRequest:
            raise ValueError("coordination request required")
        if self.status not in {"completed", "failed", "interrupted", "incomplete"}:
            raise ValueError("invalid coordination terminal status")
        if self.provider_status not in {None, "completed", "failed", "interrupted"}:
            raise ValueError("invalid provider status")
        if type(self.protocol_closed) is not bool:
            raise ValueError("invalid protocol closure")
        if type(self.observations) is not tuple or any(type(o) is not Observation for o in self.observations):
            raise ValueError("invalid coordination observations")
        if (len(self.observations) > self.request.max_events
            or sum(len(o.payload_json.encode()) for o in self.observations) > self.request.max_output_bytes):
            raise ValueError("coordination observation budget exceeded")
        for name in ("native_thread_id", "native_turn_id", "execution_error", "capture_error", "cleanup_error"):
            if getattr(self, name) is not None:
                _text(getattr(self, name))
        for name in ("sdk_execution_json", "usage_json"):
            value = getattr(self, name)
            if value is not None and type(strict_json(value, max_bytes=65536)) is not dict:
                raise ValueError("invalid coordination metadata")
        if self.intent_json is not None:
            validate_intent(self.intent_json, self.request)
        if self.status == "completed" and (
            self.provider_status != "completed" or self.intent_json is None
            or not self.native_thread_id or not self.native_turn_id or not self.protocol_closed
            or self.execution_error or self.capture_error or self.cleanup_error
        ):
            raise ValueError("coordination completion lacks terminal/protocol evidence")

    @property
    def sdk_execution(self):
        return strict_json(self.sdk_execution_json) if self.sdk_execution_json is not None else None

    @property
    def usage(self):
        return strict_json(self.usage_json) if self.usage_json is not None else None

    def to_tool_output(self):
        return {
            "authoritative": False, "operation": "coordination-inference",
            "status": self.status, "provider_status": self.provider_status,
            "operation_id": self.request.operation_id,
            "request_id": self.request.admitted_request_id,
            "request_sha256": self.request.inner_request_sha256,
            "intent": strict_json(self.intent_json) if self.intent_json is not None else None,
            "native_thread_id": self.native_thread_id, "native_turn_id": self.native_turn_id,
            "usage": self.usage, "usage_completeness": "observed-payload" if self.usage_json is not None else "unknown",
            "execution_error": self.execution_error, "capture_error": self.capture_error,
            "cleanup_error": self.cleanup_error, "protocol_closed": self.protocol_closed,
        }

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["request"] = self.request.to_dict()
        value["observations"] = [o.to_dict() for o in self.observations]
        return value

    @classmethod
    def from_dict(cls, value: object) -> CoordinationInferenceResult:
        if type(value) is not dict or set(value) != {f.name for f in fields(cls)}:
            raise ValueError("invalid coordination result fields")
        if type(value["observations"]) is not list:
            raise ValueError("invalid observations")
        return cls(**{**value, "request": CoordinationInferenceRequest.from_dict(value["request"]),
                      "observations": tuple(Observation.from_dict(o) for o in value["observations"])})


def function_call(result: CoordinationInferenceResult) -> dict[str, str]:
    """Pure translation of acquired intent, not native/process authority."""
    if type(result) is not CoordinationInferenceResult or result.status != "completed":
        raise ValueError("completed observed intent required")
    intent = validate_intent(result.intent_json, result.request)
    digest = hashlib.sha256(json_text({
        "request": result.request.to_dict(), "thread": result.native_thread_id,
        "turn": result.native_turn_id, "intent": intent,
    }).encode()).hexdigest()
    return {"type": "function_call", "name": "execute_admitted",
            "arguments": json_text({"request_id": result.request.admitted_request_id}),
            "call_id": "orchestrarium_coord_" + digest}
