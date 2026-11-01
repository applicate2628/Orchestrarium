"""Codex inference specialization of the existing bounded transport lifecycle."""
from .codex import AdapterError, CodexReviewAdapter
from .coordination import (
    CoordinationInferenceRequest, CoordinationInferenceResult, intent_schema, validate_intent,
)


class CodexCoordinationAdapter(CodexReviewAdapter):
    async def execute(self, request):
        if type(request) is not CoordinationInferenceRequest:
            raise ValueError("coordination request required")
        return await super().execute(request)

    async def reconcile(self, *args, **kwargs):
        raise ValueError("coordination resume is unavailable before effects")

    def _output_schema(self, request):
        return intent_schema(request)

    def _parse_final(self, text, request):
        return validate_intent(text, request)

    def _check_item(self, item):
        if item.get("type") not in {"agentMessage", "reasoning", "userMessage"}:
            raise AdapterError("coordination_native_tool_item_refused")

    def _make_result(self, **values):
        return CoordinationInferenceResult(intent_json=values.pop("review"), **values)
