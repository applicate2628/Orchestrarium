"""Typed inference evidence through the existing SDK receiving/ledger owner."""
from .contracts import json_text, strict_json
from .coordination import CoordinationInferenceRequest, CoordinationInferenceResult


def coordination_terminal_payload(request, observation, *, output_context, admitted_sdk_execution):
    from process_supervision.sdk_worker import SdkWorkerObservation
    from .receiving import _provider_owner, _require_sdk_process_settlement, scan_execution_output
    from .runtime import runtime_selection_from_dict, selected_sdk_execution
    if (type(request) is not CoordinationInferenceRequest
        or type(observation) is not SdkWorkerObservation or not observation.is_bound_to(request)
        or type(observation.result) is not CoordinationInferenceResult):
        raise ValueError("coordination worker pairing unavailable")
    result = observation.result
    scan_execution_output(result, output_context)
    process = _require_sdk_process_settlement(observation)
    if observation.runtime_selection_json is None:
        raise ValueError("coordination runtime commitment unavailable")
    selection = runtime_selection_from_dict("codex", strict_json(observation.runtime_selection_json))
    selected = selected_sdk_execution(request, selection)
    if admitted_sdk_execution != selected or selected["schemaVersion"] != 3:
        raise ValueError("coordination launch commitment mismatch")
    owner = _provider_owner()
    validator = owner._ledger_owner().load_validator()
    validator.validate_sdk_execution(selected, provider="codex", model=request.model, effort=request.effort)
    complete = (
        process.outcome == "success" and process.failure_id is None
        and process.target_exit_code == 0 and not process.timed_out and not process.cancelled
        and not process.stdout.truncated and not process.stderr.truncated
        and observation.protocol_error is None and observation.unavailable_reason is None
        and observation.cancel is None and result.status == "completed"
        and result.intent_json is not None and result.execution_error is None and result.capture_error is None
    )
    reported = result.sdk_execution
    try:
        validator.validate_sdk_execution(reported, provider="codex", model=request.model, effort=request.effort)
    except ValueError:
        complete = False
    else:
        controls = ("adapter", "model", "effort", "sandboxMode", "approvalPolicy", "accountBinding")
        if reported["schemaVersion"] != 1 or any(reported[k] != selected[k] for k in controls):
            complete = False
    content = {"operation": "coordination-inference", "evidence": result.to_tool_output(),
               "reported_sdk_configuration": reported,
               "process": {"outcome": process.outcome, "failure_id": process.failure_id,
                           "target_exit_code": process.target_exit_code}}
    # This is not a provider-review envelope or a verdict. The existing receiver
    # uses common identity/resultText fields only to bind artifact and terminal.
    payload = {
        "schema": "orchestrarium.coordination-inference.v1",
        "provider": "codex", "model": request.model, "effort": request.effort,
        "resultText": json_text(content), "status": "completed" if complete else "blocked", "gate": "none",
        "authorizing": False, "closesRunIds": [], "terminalClass": "external-nonauthorizing",
        "actualExecutionPath": "direct-external-sdk", "workItem": request.work_item_id,
        "assignedRole": "lead", "executionRole": "main", "artifactIdentity": request.artifact_id,
        "externalDispatchId": request.external_dispatch_id,
        "externalEvidenceRunId": request.external_evidence_run_id,
        "effortMappingLoss": request.effort_mapping_loss, "sdkExecution": selected,
    }
    failure = owner.provider_output_safety_scan_terminal(
        "codex", output_context.needles, stdout=json_text(payload).encode(), stderr=b"", serialized_line=False)
    if failure is not None:
        raise ValueError(failure)
    return payload
