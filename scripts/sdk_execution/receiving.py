"""SDK evidence receiving through existing provider and ledger owners.

A provider review remains nonauthorizing. Process settlement and a durable ledger
readback are required separately; this module grants no execution permission.
"""
from __future__ import annotations

import hashlib
import os
import sys
import re
from pathlib import Path, PureWindowsPath
from typing import Any

from .contracts import ExecutionRequest, ExecutionResult, json_text, strict_json


def _provider_owner():
    # This optional source-mode module is placed alongside the existing owners.
    import provider_prompt
    return provider_prompt



def scan_execution_output(result: ExecutionResult, output_context: Any) -> None:
    """Scan exactly the exported tool representation, including usage metadata."""
    owner = _provider_owner()
    if not isinstance(output_context, owner.ProviderOutputContext):
        raise ValueError("SDK output requires the existing auth-owner scan context")
    try:
        failure = owner.provider_output_safety_scan_terminal(
            result.request.provider, output_context.needles,
            stdout=json_text(result.to_tool_output()).encode("utf-8"), stderr=b"",
            serialized_line=False,
        )
    except Exception:
        failure = "E_EXTERNAL_PROVIDER_OUTPUT_SCAN_UNAVAILABLE"
    if failure is not None:
        raise ValueError(failure)


def preworker_failure_payload(run: Any) -> dict[str, object]:
    """Export a runtime-owned, already settled no-worker failure; never settle.

    Only the original RuntimeRun returned before worker invocation is eligible.
    An exception after invocation is not evidence of no worker. The integer exit
    code is a wrapper failure code, NOT an observed native process exit; cleanup
    remains conservatively incomplete without a creator-owned observation.
    """
    from .runtime import RuntimeRun, selected_sdk_execution

    if (type(run) is not RuntimeRun or run.observation is not None
            or type(run.terminal) is not dict
            or type(run.launch_error) is not str
            or re.fullmatch(r"[a-z][a-z0-9_]{0,127}", run.launch_error) is None):
        raise ValueError("SDK runtime has no settled preworker failure")
    request, selection = run.request, run.selection
    selected = selected_sdk_execution(request, selection)
    if selection.expected_launch_sha256 is None:
        raise ValueError("SDK preworker failure has no admitted launch")
    identity = {
        "provider": request.provider, "model": request.model, "effort": request.effort,
        "workItem": request.work_item_id, "assignedRole": request.role,
        "executionRole": "external-reviewer", "artifactIdentity": request.artifact_id,
        "externalDispatchId": request.external_dispatch_id,
        "externalEvidenceRunId": request.external_evidence_run_id,
        "effortMappingLoss": request.effort_mapping_loss,
        "actualExecutionPath": "direct-external-sdk", "sdkExecution": selected,
    }
    expected = {
        **identity, "eventKind": "terminal", "runId": request.external_evidence_run_id,
        "launchRunId": request.external_dispatch_id, "scope": list(request.scope),
        "status": "blocked", "gate": "none", "closesRunIds": [],
        "terminalClass": "external-nonauthorizing",
    }
    if (run.terminal.get("authorizing") is not False
            or any(run.terminal.get(key) != value for key, value in expected.items())):
        raise ValueError("SDK preworker terminal identity or outcome mismatch")
    owner = _provider_owner()
    if not isinstance(run.output_context, owner.ProviderOutputContext):
        raise ValueError("SDK output requires the existing auth-owner scan context")
    persisted = owner.read_back_external_terminal(
        owner.Control(ledger=selection.work_item, ledger_max_events=selection.ledger_max_events,
                      ledger_max_bytes=selection.ledger_max_bytes),
        request.provider, request.external_dispatch_id,
    )
    if persisted != run.terminal:
        raise ValueError("SDK preworker terminal persisted readback mismatch")
    primary = {
        "exitCode": 1, "token": "UNVERIFIED:E_SDK_PREWORKER_FAILURE",
        "status": "blocked", "gate": "none",
        "note": "SDK worker was not invoked; exit code is wrapper failure, not native exit",
    }
    payload = {
        "schema": "orchestrarium.provider-result.v3", **identity, **primary,
        "primaryOutcome": primary,
        "resultText": json_text({"workerInvoked": False, "exitCodeSource": "wrapper",
                                 "launchError": run.launch_error}),
        "cleanupStatus": "incomplete", "authorizing": False, "closesRunIds": [],
        "independentVerificationRequired": True, "terminalClass": "external-nonauthorizing",
    }
    owner._provider_result_scan_projection(payload)
    line = owner.SDK_RESULT_PREFIX + json_text(payload) + "\n"
    safety_error = owner._provider_terminal_line_safety(request.provider, run.output_context.needles, line)
    if safety_error is not None:
        raise ValueError(safety_error)
    return owner.parse_provider_result(line)


def terminal_payload(request: ExecutionRequest, observation: Any, *, output_context: Any,
                     admitted_sdk_execution: dict[str, object] | None = None) -> dict[str, object]:
    """Receive a paired adapter result and its creator-owned process observation.

    The caller must retain the pairing returned by run_sdk_worker. A deserialized
    arbitrary process receipt is not a substitute for that creator-owned return.
    """
    from process_supervision.sdk_worker import SdkWorkerObservation

    if type(observation) is not SdkWorkerObservation or not observation.is_bound_to(request):
        raise ValueError("SDK worker observation pairing unavailable")
    result, process = observation.result, observation.process
    if result is None or result.request != request or result.actual_execution_path != "direct-external-sdk":
        raise ValueError("SDK receiving identity mismatch")
    scan_execution_output(result, output_context)
    if not (
        process.event_id == "process.supervision.settled.v1"
        and process.policy_id == "sdk-worker-v1"
        and process.tree.ownership_confirmed
        and process.tree.settlement_state == "EMPTY"
        and process.tree.tree_empty and process.tree.direct_reaped
        and process.resources_closed and not process.inheritance_poisoned
        and not process.cleanup_issues and not process.cleanup_uncertain
    ):
        raise ValueError("SDK process settlement unavailable; retain captured result")
    if not result.protocol_closed or result.cleanup_error is not None:
        raise ValueError("SDK protocol cleanup unavailable; retain captured result")
    if type(process.target_exit_code) is not int:
        raise ValueError("SDK worker exit observation unavailable")
    complete = not (
        process.outcome != "success" or process.failure_id is not None
        or process.target_exit_code != 0 or process.timed_out or process.cancelled
        or process.stdout.truncated or process.stderr.truncated
        or result.status != "completed" or result.review is None
        or result.execution_error is not None or result.capture_error is not None
        or observation.protocol_error is not None
    )
    selected_config = admitted_sdk_execution if admitted_sdk_execution is not None else result.sdk_execution
    if not isinstance(selected_config, dict) or selected_config.get("accountBinding") != request.account_binding:
        raise ValueError("SDK selected account does not match admitted request")
    owner = _provider_owner()
    validator = owner._ledger_owner().load_validator()
    selected_config = validator.validate_sdk_execution(
        selected_config, provider=request.provider, model=request.model, effort=request.effort,
    )
    if "requestSha256" in selected_config:
        from .runtime import runtime_selection_from_dict, request_sha256
        retained = getattr(observation, "runtime_selection_json", None)
        if retained is None:
            raise ValueError("SDK runtime request commitment has no retained selection")
        selection = runtime_selection_from_dict(request.provider, strict_json(retained))
        if request_sha256(request, selection) != selected_config["requestSha256"]:
            raise ValueError("SDK runtime request commitment mismatch")
    if complete:
        reported = result.sdk_execution
        try:
            validator.validate_sdk_execution(
                reported, provider=request.provider, model=request.model, effort=request.effort,
            )
        except ValueError:
            # Keep malformed/missing observed metadata as blocked evidence; it
            # must not become a completed review merely because no version was
            # selected before launch.
            complete = False
        else:
            if reported["schemaVersion"] != 1 or "requestSha256" in reported:
                complete = False  # A selected commitment is not an observation.
            elif selected_config["schemaVersion"] == 1:
                # Historical rows retain their exact original binding contract.
                complete = reported == {key: value for key, value in selected_config.items() if key != "requestSha256"}
            else:
                # Compare every admitted control; version labels are observed
                # provenance rather than compatibility or admission gates.
                complete = (
                    {key: value for key, value in reported.items()
                     if key not in {"schemaVersion", "sdkVersion", "runtimeVersion"}}
                    == {key: value for key, value in selected_config.items()
                        if key not in {"schemaVersion", "requestSha256"}}
                )
    verdict = result.review.verdict if complete else "none"
    status = ("completed" if verdict == "PASS" else "revise") if complete else "blocked"
    token = f"COMPLETE:{verdict}" if complete else "UNVERIFIED:E_SDK_EXECUTION_INCOMPLETE"
    primary = {"exitCode": process.target_exit_code, "token": token,
               "status": status, "gate": verdict,
               "note": "structured SDK review evidence" if complete else "settled SDK execution was incomplete"}
    result_content = result.review.to_dict() if complete else {
        "adapter": result.to_tool_output(),
        "reported_sdk_configuration": result.sdk_execution,
        "process": {"outcome": process.outcome, "failure_id": process.failure_id,
                    "target_exit_code": process.target_exit_code,
                    "cancelled": process.cancelled, "timed_out": process.timed_out},
        "protocol_error": observation.protocol_error,
    }
    if complete and selected_config["schemaVersion"] == 2:
        # The durable artifact, whose exact bytes are bound by the terminal,
        # retains observed versions separately from selected launch controls.
        result_content = {"review": result_content, "reported_sdk_configuration": result.sdk_execution}
    payload: dict[str, object] = {
        "schema": "orchestrarium.provider-result.v3", "provider": request.provider,
        "model": request.model, "effort": request.effort,
        "resultText": json_text(result_content),
        **primary, "token": "COMPLETE:EXTERNAL_NONAUTHORIZING" if complete else token, "primaryOutcome": primary,
        "cancelled": process.cancelled, "timedOut": process.timed_out, "cleanupStatus": "complete",
        "cleanupIssueCount": 0,
        "authorizing": False, "closesRunIds": [], "independentVerificationRequired": True,
        "terminalClass": "external-nonauthorizing", "actualExecutionPath": "direct-external-sdk",
        "workItem": request.work_item_id, "assignedRole": request.role,
        "executionRole": "external-reviewer", "artifactIdentity": request.artifact_id,
        "externalDispatchId": request.external_dispatch_id,
        "externalEvidenceRunId": request.external_evidence_run_id,
        "effortMappingLoss": request.effort_mapping_loss,
        "sdkExecution": selected_config,
    }
    owner._provider_result_scan_projection(payload)
    line = owner.SDK_RESULT_PREFIX + json_text(payload) + "\n"
    if not isinstance(output_context, owner.ProviderOutputContext):
        raise ValueError("SDK output requires the existing auth-owner scan context")
    safety_error = owner._provider_terminal_line_safety(request.provider, output_context.needles, line)
    if safety_error is not None:
        raise ValueError(safety_error)
    return payload


def receive_terminal(
    work_item: Path, request: ExecutionRequest, observation: Any,
    *, artifact: str, started_at: str, updated_at: str,
    ledger_max_events: int | None, ledger_max_bytes: int | None, output_context: Any,
) -> dict[str, object]:
    """Settle an already admitted launch using the existing atomic ledger writer.

    Scope, role and SDK profile are inherited from the real launch by settle-launch.
    The independently validated readback must match this exact received result.
    No main-agent acceptance or task/review closure is performed here.
    """
    owner = _provider_owner()
    writer = owner._ledger_owner()
    validator = writer.load_validator()
    budget = (None if ledger_max_events is None and ledger_max_bytes is None
        else validator.resolve_ledger_resource_budget(ledger_max_events, ledger_max_bytes, managed=True))
    ledger = Path(work_item) / "agent-runs.jsonl"
    raw = validator.read_ledger_bytes(ledger, budget)
    errors: list[str] = []
    events = validator.load_jsonl(ledger, errors, source_bytes=raw, ledger_resource_budget=budget)
    if errors:
        raise ValueError("SDK ledger unavailable before receiving")
    launches = [event for event in events if event.get("eventKind") == "launch"
                and event.get("runId") == request.external_dispatch_id]
    if len(launches) != 1:
        raise ValueError("SDK result has no unique admitted launch")
    payload = terminal_payload(request, observation, output_context=output_context,
                               admitted_sdk_execution=launches[0].get("sdkExecution"))
    result = observation.result
    artifact_path = Path(artifact)
    if artifact_path.anchor or PureWindowsPath(artifact).anchor or ".." in artifact_path.parts:
        raise ValueError("SDK review artifact must be work-item relative")
    item_root = Path(work_item).resolve(strict=True)
    received_artifact = (item_root / artifact_path).resolve(strict=True)
    if not received_artifact.is_relative_to(item_root):
        raise ValueError("SDK review artifact is outside work item")
    expected_artifact = (str(payload["resultText"]) + "\n").encode("utf-8")
    def artifact_matches() -> bool:
        # Re-resolve the ledger locator on every check; do not trust a cached
        # symlink target. Reuse the exact expected-result size as the read bound.
        locator = item_root / artifact_path
        if locator.resolve(strict=True) != received_artifact:
            return False
        with locator.open("rb") as stream:
            content = stream.read(len(expected_artifact) + 1)
        return content == expected_artifact and locator.resolve(strict=True) == received_artifact
    if not artifact_matches():
        raise ValueError("SDK review artifact does not contain the received result")
    expected = {key: payload[key] for key in (
        "workItem", "provider", "model", "effort", "assignedRole", "artifactIdentity",
        "externalDispatchId", "externalEvidenceRunId", "effortMappingLoss",
        "actualExecutionPath", "sdkExecution",
    )}
    if len(launches) != 1 or launches[0].get("scope") != list(request.scope) or any(launches[0].get(key) != value for key, value in expected.items()):
        raise ValueError("SDK result does not match admitted launch")
    resources = ([] if budget is None else ["--ledger-max-events", str(budget.max_events),
        "--ledger-max-bytes", str(budget.max_ledger_bytes)])
    args = [
        *resources, "--work-item", str(work_item), "settle-launch",
        "--launch-run-id", request.external_dispatch_id,
        "--expected-launch-sha256", writer.launch_event_sha256(launches[0], validator),
        "--run-id", request.external_evidence_run_id,
        "--status", str(payload["status"]), "--gate", str(payload["gate"]),
        "--artifact", artifact,
        "--artifact-revision", hashlib.sha256(expected_artifact).hexdigest(),
        "--artifact-size-bytes", str(len(expected_artifact)),
        "--started-at", started_at, "--updated-at", updated_at,
        "--evidence", "command:SDK structured review and creator-owned process settlement",
    ]
    if writer.main(args, settlement_output=sys.stderr) != 0:
        raise ValueError("SDK ledger receiving failed; retain captured result")
    control = owner.Control(ledger=str(work_item), ledger_max_events=ledger_max_events,
                            ledger_max_bytes=ledger_max_bytes)
    terminal = owner.read_back_external_terminal(control, request.provider, request.external_dispatch_id)
    if not artifact_matches():
        raise ValueError("SDK review artifact locator/content changed during receiving")
    if terminal is None or any(terminal.get(key) != value for key, value in expected.items()):
        raise ValueError("SDK terminal persisted readback mismatch")
    if (terminal.get("runId"), terminal.get("status"), terminal.get("gate")) != (
        request.external_evidence_run_id, payload["status"], payload["gate"],
    ):
        raise ValueError("SDK terminal outcome readback mismatch")
    return terminal



def review_artifact_target(work_item: str | Path, artifact: str, *, must_be_new: bool = False) -> Path:
    """Read-only artifact preflight; final receipt creation still owns exclusion."""
    relative = Path(artifact)
    if not artifact or relative.anchor or PureWindowsPath(artifact).anchor or ".." in relative.parts:
        raise ValueError("SDK review artifact must be work-item relative")
    item = Path(work_item).resolve(strict=True)
    target = item / relative
    if not target.resolve(strict=False).is_relative_to(item):
        raise ValueError("SDK review artifact is outside work item")
    owner = _provider_owner()
    owner.TerminalReceiptV1._validated_path(target)
    if must_be_new:
        owner.validate_no_reparse_components(target.parent)
        if not target.parent.is_dir():
            raise ValueError("SDK review artifact parent is unavailable")
        if os.path.lexists(target):
            raise ValueError("E_EXTERNAL_TERMINAL_RECEIPT_EXISTS")
    return target


def receive_runtime_run(
    run: Any, *, artifact: str, started_at: str, updated_at: str,
) -> dict[str, object]:
    """Materialize scanned evidence with the existing receipt owner, then receive.

    An acquired result is never overwritten or reconstructed from ledger metadata.
    If receiving fails after commit, the artifact and original RuntimeRun remain
    available for explicit reconciliation; this helper does not replay execution.
    """
    from .runtime import RuntimeRun, selected_sdk_execution

    if type(run) is not RuntimeRun or run.observation is None:
        raise ValueError("SDK runtime has no acquired worker observation")
    target = review_artifact_target(run.selection.work_item, artifact)
    item = Path(run.selection.work_item).resolve(strict=True)
    # Scan the exact complete envelope before writing any provider content.
    payload = terminal_payload(
        run.request, run.observation, output_context=run.output_context,
        admitted_sdk_execution=selected_sdk_execution(run.request, run.selection),
    )
    content = (str(payload["resultText"]) + "\n").encode("utf-8")
    owner = _provider_owner()
    with owner.TerminalReceiptV1.reserve(target) as receipt:
        receipt.commit(content)
    # Windows receipt handles deny sharing. Close the writer before independent
    # reading; receiving rechecks the actual locator/content and atomic digest.
    return receive_terminal(
        item, run.request, run.observation, artifact=artifact,
        started_at=started_at, updated_at=updated_at,
        ledger_max_events=run.selection.ledger_max_events,
        ledger_max_bytes=run.selection.ledger_max_bytes,
        output_context=run.output_context,
    )
