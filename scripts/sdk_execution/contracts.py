"""Small immutable, nonauthorizing executor values; no vendor SDK imports."""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, fields
from pathlib import PurePosixPath
from typing import Any


def _text(value: object, name: str, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > limit:
        raise ValueError(f"invalid {name}")
    return value


def _keys(value: object, expected: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("missing or unexpected contract fields")
    return value


def strict_json(value: str, *, max_bytes: int = 1_048_576) -> Any:
    if not isinstance(value, str) or len(value.encode("utf-8")) > max_bytes:
        raise ValueError("JSON byte limit exceeded")
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = item
        return result
    def invalid_constant(value: str) -> None:
        raise ValueError("non-finite JSON number")
    def finite_float(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("non-finite JSON number")
        return parsed
    try:
        return json.loads(value, object_pairs_hook=pairs, parse_constant=invalid_constant, parse_float=finite_float)
    except RecursionError as exc:
        raise ValueError("JSON nesting too deep") from exc


def json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    work_item_id: str
    provider: str
    external_dispatch_id: str
    external_evidence_run_id: str
    artifact_id: str
    role: str
    model: str
    effort: str
    cwd: str
    account_binding: str
    prompt: str
    coordinator_binding: str
    scope: tuple[str, ...]
    max_output_bytes: int = 1_048_576
    max_events: int = 4096

    def __post_init__(self) -> None:
        for field in fields(self):
            if field.name not in {"scope", "max_output_bytes", "max_events"}:
                _text(getattr(self, field.name), field.name, 262_144 if field.name == "prompt" else 4096)
        if self.provider not in {"codex", "claude", "kimi", "grok", "minimax", "mimo"}:
            raise ValueError("invalid provider")
        if self.external_dispatch_id == self.external_evidence_run_id:
            raise ValueError("dispatch and evidence identities must differ")
        if not isinstance(self.scope, tuple) or not 1 <= len(self.scope) <= 128:
            raise ValueError("invalid scope")
        for item in self.scope:
            _text(item, "scope item")
        for name, maximum in (("max_output_bytes", 16_777_216), ("max_events", 65_536)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError(f"invalid {name}")
        if self.effort not in {"low", "medium", "high", "xhigh", "max"}:
            raise ValueError("unsupported effort")

    @property
    def run_id(self) -> str:
        """Compatibility name for the existing dispatch identity, not a third ID."""
        return self.external_dispatch_id

    @property
    def effort_mapping_loss(self) -> str:
        return "none"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["scope"] = list(self.scope)
        return result

    @classmethod
    def from_dict(cls, value: object) -> ExecutionRequest:
        data = dict(_keys(value, {field.name for field in fields(cls)}))
        if not isinstance(data["scope"], list):
            raise ValueError("scope must be a list")
        data["scope"] = tuple(data["scope"])
        return cls(**data)


@dataclass(frozen=True, slots=True)
class Finding:
    severity: str
    path: str
    line: int
    message: str
    evidence: str

    def __post_init__(self) -> None:
        if self.severity not in {"low", "medium", "high", "critical"}:
            raise ValueError("invalid finding severity")
        for name in ("path", "message", "evidence"):
            _text(getattr(self, name), name, 16_384)
        path = PurePosixPath(self.path)
        if path.is_absolute() or ".." in path.parts or "\\" in self.path or ":" in self.path:
            raise ValueError("finding path must be repository relative")
        if type(self.line) is not int or self.line < 1:
            raise ValueError("invalid finding line")

    @classmethod
    def from_dict(cls, value: object) -> Finding:
        return cls(**_keys(value, {field.name for field in fields(cls)}))


@dataclass(frozen=True, slots=True)
class ReviewResult:
    run_id: str
    artifact_id: str
    role: str
    verdict: str
    findings: tuple[Finding, ...]

    def __post_init__(self) -> None:
        for name in ("run_id", "artifact_id", "role"):
            _text(getattr(self, name), name)
        if self.verdict not in {"PASS", "REVISE"}:
            raise ValueError("invalid review verdict")
        if not isinstance(self.findings, tuple) or len(self.findings) > 100:
            raise ValueError("invalid findings")
        if any(not isinstance(item, Finding) for item in self.findings):
            raise ValueError("invalid finding")

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["findings"] = [asdict(item) for item in self.findings]
        return result

    @classmethod
    def from_dict(cls, value: object) -> ReviewResult:
        data = dict(_keys(value, {field.name for field in fields(cls)}))
        if not isinstance(data["findings"], list):
            raise ValueError("findings must be a list")
        data["findings"] = tuple(Finding.from_dict(item) for item in data["findings"])
        return cls(**data)


def review_schema(request: ExecutionRequest) -> dict[str, Any]:
    """Native outputSchema, independently revalidated after completion."""
    return {
        "type": "object", "additionalProperties": False,
        "required": ["run_id", "artifact_id", "role", "verdict", "findings"],
        "properties": {
            "run_id": {"type": "string", "enum": [request.external_evidence_run_id]},
            "artifact_id": {"type": "string", "enum": [request.artifact_id]},
            "role": {"type": "string", "enum": [request.role]},
            "verdict": {"type": "string", "enum": ["PASS", "REVISE"]},
            "findings": {"type": "array", "maxItems": 100, "items": {
                "type": "object", "additionalProperties": False,
                "required": ["severity", "path", "line", "message", "evidence"],
                "properties": {
                    "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                    "path": {"type": "string"}, "line": {"type": "integer", "minimum": 1},
                    "message": {"type": "string"}, "evidence": {"type": "string"},
                },
            }},
        },
    }


@dataclass(frozen=True, slots=True)
class Observation:
    sequence: int
    kind: str
    payload_json: str

    def __post_init__(self) -> None:
        if type(self.sequence) is not int or self.sequence < 0:
            raise ValueError("invalid sequence")
        _text(self.kind, "observation kind", 256)
        _text(self.payload_json, "observation payload", 16_777_216)
        if not isinstance(strict_json(self.payload_json, max_bytes=16_777_216), dict):
            raise ValueError("observation payload must be object")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: object) -> Observation:
        return cls(**_keys(value, {field.name for field in fields(cls)}))


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    request: ExecutionRequest
    status: str
    provider_status: str | None = None
    actual_execution_path: str = "direct-external-sdk"
    native_result_text: str | None = None
    native_thread_id: str | None = None
    native_turn_id: str | None = None
    sdk_execution_json: str | None = None
    observations: tuple[Observation, ...] = ()
    review: ReviewResult | None = None
    usage_json: str | None = None
    execution_error: str | None = None
    capture_error: str | None = None
    cleanup_error: str | None = None
    protocol_closed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.request, ExecutionRequest):
            raise ValueError("invalid result request")
        if self.status not in {"completed", "failed", "interrupted", "incomplete"}:
            raise ValueError("invalid execution status")
        if self.provider_status not in {None, "completed", "failed", "interrupted"}:
            raise ValueError("invalid provider status")
        if self.actual_execution_path not in {"direct-external-sdk", "direct-external-cli"}:
            raise ValueError("invalid actual execution path")
        if self.native_result_text is not None:
            _text(self.native_result_text, "native result text", self.request.max_output_bytes)
        if self.review is not None and self.native_result_text is not None:
            raise ValueError("result representations are mutually exclusive")
        if self.actual_execution_path == "direct-external-cli":
            if self.sdk_execution_json is not None or self.review is not None:
                raise ValueError("CLI result must preserve native text and provenance")
        elif self.native_result_text is not None:
            raise ValueError("SDK result requires structured review")
        has_result = self.review is not None or self.native_result_text is not None
        if self.status == "completed" and (self.provider_status != "completed" or not has_result or self.execution_error or self.capture_error or self.cleanup_error or not self.protocol_closed):
            raise ValueError("completed result lacks required evidence")
        if not isinstance(self.observations, tuple) or any(not isinstance(o, Observation) for o in self.observations):
            raise ValueError("invalid observations")
        if len(self.observations) > self.request.max_events:
            raise ValueError("observation count exceeded")
        if sum(len(o.payload_json.encode("utf-8")) for o in self.observations) > self.request.max_output_bytes:
            raise ValueError("observation bytes exceeded")
        if type(self.protocol_closed) is not bool:
            raise ValueError("invalid protocol closure")
        for name in ("native_thread_id", "native_turn_id", "execution_error", "capture_error", "cleanup_error"):
            if getattr(self, name) is not None:
                _text(getattr(self, name), name)
        for name in ("sdk_execution_json", "usage_json"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not isinstance(strict_json(value, max_bytes=65_536), dict)):
                raise ValueError(f"invalid {name}")
        if self.review is not None:
            if not isinstance(self.review, ReviewResult) or (
                self.review.run_id, self.review.artifact_id, self.review.role
            ) != (self.request.external_evidence_run_id, self.request.artifact_id, self.request.role):
                raise ValueError("review identity mismatch")

    @property
    def sdk_execution(self) -> dict[str, Any] | None:
        return strict_json(self.sdk_execution_json, max_bytes=65_536) if self.sdk_execution_json else None

    @property
    def usage(self) -> dict[str, Any] | None:
        return strict_json(self.usage_json, max_bytes=65_536) if self.usage_json else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request.to_dict(), "status": self.status, "provider_status": self.provider_status,
            "actual_execution_path": self.actual_execution_path, "native_result_text": self.native_result_text,
            "native_thread_id": self.native_thread_id, "native_turn_id": self.native_turn_id,
            "sdk_execution_json": self.sdk_execution_json,
            "observations": [o.to_dict() for o in self.observations],
            "review": self.review.to_dict() if self.review else None, "usage_json": self.usage_json,
            "execution_error": self.execution_error, "capture_error": self.capture_error,
            "cleanup_error": self.cleanup_error, "protocol_closed": self.protocol_closed,
        }

    @classmethod
    def from_dict(cls, value: object) -> ExecutionResult:
        data = dict(_keys(value, {field.name for field in fields(cls)}))
        data["request"] = ExecutionRequest.from_dict(data["request"])
        if not isinstance(data["observations"], list):
            raise ValueError("observations must be a list")
        data["observations"] = tuple(Observation.from_dict(o) for o in data["observations"])
        data["review"] = ReviewResult.from_dict(data["review"]) if data["review"] is not None else None
        return cls(**data)

    def to_tool_output(self) -> dict[str, Any]:
        """External evidence, not a ledger write, accepted review, or settlement."""
        return {
            "authoritative": False, "process_settlement": "not_established",
            "actual_execution_path": self.actual_execution_path, "native_result_text": self.native_result_text,
            "run_id": self.request.run_id, "external_dispatch_id": self.request.external_dispatch_id,
            "external_evidence_run_id": self.request.external_evidence_run_id,
            "status": self.status, "provider_status": self.provider_status, "review": self.review.to_dict() if self.review else None,
            "execution_error": self.execution_error, "capture_error": self.capture_error,
            "cleanup_error": self.cleanup_error, "protocol_closed": self.protocol_closed,
            "usage": self.usage,
        }


@dataclass(frozen=True, slots=True)
class CancelReceipt:
    run_id: str
    requested: bool
    acknowledged: bool
    native_thread_id: str | None = None
    native_turn_id: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        _text(self.run_id, "run_id")
        if type(self.requested) is not bool or type(self.acknowledged) is not bool:
            raise ValueError("invalid cancellation receipt")
        if self.acknowledged and not self.requested:
            raise ValueError("unrequested acknowledgement")
        for name in ("native_thread_id", "native_turn_id", "error"):
            if getattr(self, name) is not None:
                _text(getattr(self, name), name)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: object) -> CancelReceipt:
        return cls(**_keys(value, {field.name for field in fields(cls)}))


def validate_review(payload: object, *, request: ExecutionRequest | None = None) -> ReviewResult:
    """Validate shape and, when supplied, the authoritative request binding."""
    if isinstance(payload, str):
        if len(payload.encode("utf-8")) > (request.max_output_bytes if request else 1_048_576):
            raise ValueError("review output too large")
        payload = strict_json(payload, max_bytes=request.max_output_bytes if request else 1_048_576)
    review = ReviewResult.from_dict(payload)
    if request is not None and (review.run_id, review.artifact_id, review.role) != (
        request.external_evidence_run_id, request.artifact_id, request.role
    ):
        raise ValueError("review identity mismatch")
    return review
