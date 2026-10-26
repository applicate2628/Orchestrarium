"""Explicit SDK composition using the existing admission and process owners.

Importing this module does not load a provider SDK, discover credentials, install
dependencies or launch anything. The operator supplies every runtime/account
selection and the existing policy owner must admit the effective request. Native
Codex configuration and instructions retain their existing owner; selecting a
home is not evidence that its complete configuration was observed or immutable.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, replace
import hashlib
import inspect
import math
import sys
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable

from process_supervision.process_runner import MAX_STDIN_BYTES

from ._async import drain_owned
from .contracts import CancelReceipt, ExecutionRequest, ExecutionResult, json_text
from .codex_tools import CODEX_MCP_ISOLATION_OVERRIDES, CodexMcpScope, CodexMcpScopeError


# Explicit bounded CLI review profile, NOT a low-level SDK/global default.
# Endpoint and managed requirements still require pre-start Host qualification.
CODEX_BOUNDED_REVIEW_OVERRIDES = (
    "features.memories=false",
    "notify=[]",
    'model_provider="openai"',
    'approvals_reviewer="user"',
    *CODEX_MCP_ISOLATION_OVERRIDES,
)


class RuntimeBindingError(ValueError):
    """Stable composition failure, without provider or credential contents."""


def _owner():
    import provider_prompt
    return provider_prompt


def _sha256(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


@dataclass(frozen=True, slots=True)
class CodexRuntimeSelection:
    """Nonsecret explicit operator selection, sent only through the owned pipe.

    API-key account/read reports the mode only. Its alias is bound by the caller's
    admission and exact auth-owner environment, not an invented observed account
    identifier. ChatGPT mode additionally compares its public account email.
    """

    executable: str
    executable_sha256: str
    codex_home: str
    auth_mode: str
    expected_account_email: str | None
    work_item: str
    ledger_max_events: int | None
    ledger_max_bytes: int | None
    job_memory_limit_bytes: int
    expected_launch_sha256: str | None = None
    config_overrides: tuple[str, ...] = CODEX_MCP_ISOLATION_OVERRIDES
    mcp_scope: CodexMcpScope = CodexMcpScope(())

    def __post_init__(self) -> None:
        for name in ("executable", "codex_home", "work_item"):
            value = getattr(self, name)
            if type(value) is not str or not value or not Path(value).is_absolute():
                raise RuntimeBindingError("explicit_absolute_runtime_paths_required")
        if not _sha256(self.executable_sha256):
            raise RuntimeBindingError("explicit_runtime_digest_required")
        if self.expected_launch_sha256 is not None and not _sha256(self.expected_launch_sha256):
            raise RuntimeBindingError("invalid_launch_digest")
        if self.auth_mode not in {"codex-api-key", "codex-auth-file"}:
            raise RuntimeBindingError("explicit_auth_mode_required")
        if self.auth_mode == "codex-auth-file":
            if type(self.expected_account_email) is not str or not self.expected_account_email.strip():
                raise RuntimeBindingError("explicit_account_email_required")
        elif self.expected_account_email is not None:
            raise RuntimeBindingError("api_key_account_identity_is_not_observable")
        # Omitted ledger caps remain omitted through each independent operation;
        # the locked ledger owner derives finite admission from selected inputs.
        budgets = ("job_memory_limit_bytes",)
        if self.ledger_max_events is not None or self.ledger_max_bytes is not None:
            budgets += ("ledger_max_events", "ledger_max_bytes")
        for name in budgets:
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise RuntimeBindingError("explicit_positive_resource_budget_required")
        # Build the effective invocation-only controls BEFORE admission. Fixed
        # review isolation is part of the immutable selection/hash sent on wire,
        # never appended by the factory after a launch was admitted.
        if type(self.config_overrides) is not tuple or any(
            type(value) is not str or not value.strip() or "\x00" in value
            for value in self.config_overrides
        ):
            raise RuntimeBindingError("invalid_codex_config_overrides")
        if self.config_overrides[-len(CODEX_MCP_ISOLATION_OVERRIDES):] != CODEX_MCP_ISOLATION_OVERRIDES:
            raise RuntimeBindingError("codex_isolation_selection_not_materialized")
        if type(self.mcp_scope) is not CodexMcpScope:
            raise RuntimeBindingError("invalid_codex_mcp_scope")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["config_overrides"] = list(self.config_overrides)
        value["mcp_scope"] = self.mcp_scope.to_dict()
        return value

    @classmethod
    def from_dict(cls, value: object) -> CodexRuntimeSelection:
        if type(value) is not dict or set(value) != set(cls.__dataclass_fields__):
            raise RuntimeBindingError("invalid_runtime_selection_fields")
        if (type(value["config_overrides"]) is not list or any(
            type(item) is not str or not item.strip() or "\x00" in item
            for item in value["config_overrides"]
        )):
            raise RuntimeBindingError("invalid_codex_config_overrides")
        overrides = tuple(value["config_overrides"])
        if overrides[-len(CODEX_MCP_ISOLATION_OVERRIDES):] != CODEX_MCP_ISOLATION_OVERRIDES:
            raise RuntimeBindingError("codex_isolation_selection_not_materialized")
        try:
            scope = CodexMcpScope.from_dict(value["mcp_scope"])
        except CodexMcpScopeError:
            raise RuntimeBindingError("invalid_codex_mcp_scope") from None
        return cls(**{**value, "config_overrides": overrides, "mcp_scope": scope})


def runtime_selection_from_dict(provider: str, value: object):
    """Decode one supported provider selection at the execution boundary."""
    if provider == "codex":
        return CodexRuntimeSelection.from_dict(value)
    if provider == "claude":
        from .claude import AdapterError, ClaudeRuntimeSelection
        try:
            return ClaudeRuntimeSelection.from_dict(value)
        except AdapterError as error:
            raise RuntimeBindingError(str(error)) from error
    raise RuntimeBindingError("unsupported_runtime_provider")


def prepare_codex_request(request: ExecutionRequest) -> ExecutionRequest:
    """Compose the trusted existing governance frame exactly once, before admission.

    The returned request, rather than the unframed task, is what the policy owner
    admits, the launch commits to and the worker executes. No native base or
    developer instructions are replaced by this integration.
    """
    if type(request) is not ExecutionRequest or request.provider != "codex":
        raise RuntimeBindingError("codex_request_required")
    return replace(request, prompt=_owner().assemble_external_prompt(request.prompt.encode("utf-8")).decode("utf-8"))


def validate_admitted_request(request: ExecutionRequest, selection: Any) -> None:
    """Check exact current common-governance input, without changing admission."""
    if type(request) is not ExecutionRequest:
        raise RuntimeBindingError("admitted_execution_request_required")
    runtime_selection_from_dict(request.provider, selection.to_dict())
    frame = _owner().assemble_external_prompt(b"").decode("utf-8")
    instructions = request.prompt if request.provider == "codex" else selection.instructions
    if not instructions.startswith(frame):
        raise RuntimeBindingError("admitted_governance_frame_required")
    if request.provider == "claude" and request.model in {"opus", "sonnet", "haiku"}:
        raise RuntimeBindingError("concrete_claude_model_required")


def request_sha256(request: ExecutionRequest, selection: Any) -> str:
    runtime = selection.to_dict()
    del runtime["expected_launch_sha256"]  # The separate launch guard must not hash itself.
    return hashlib.sha256(json_text({"request": request.to_dict(), "runtimeSelection": runtime}).encode("utf-8")).hexdigest()


def selected_sdk_execution(request: ExecutionRequest, selection: Any) -> dict[str, object]:
    """Commit selected controls, never versions that require a started runtime.

    Adapter results retain their observed version metadata separately. Version
    labels are provenance, not admission constraints or compatibility promises.
    """
    runtime_selection_from_dict(request.provider, selection.to_dict())
    if request.provider == "codex":
        adapter, sandbox, approval = "openai-codex", "read-only", "deny_all"
    elif request.provider == "claude":
        adapter, sandbox, approval = "claude-agent-sdk", "tool-restricted-read-only", "deny_unadmitted"
    else:
        raise RuntimeBindingError("unsupported_runtime_provider")
    return {
        "schemaVersion": 2, "adapter": adapter, "model": request.model, "effort": request.effort,
        "sandboxMode": sandbox, "approvalPolicy": approval,
        "accountBinding": request.account_binding, "requestSha256": request_sha256(request, selection),
    }


def prepare_environment(selection: Any, source: dict[str, str]):
    """Reuse the auth/output owners with explicit input, never os.environ fallback."""
    if type(source) is not dict or any(type(k) is not str or type(v) is not str for k, v in source.items()):
        raise RuntimeBindingError("explicit_environment_required")
    owner = _owner()
    codex = isinstance(selection, CodexRuntimeSelection)
    provider = "codex" if codex else "claude"
    runtime_selection_from_dict(provider, selection.to_dict())
    home_key = "CODEX_HOME" if codex else "CLAUDE_CONFIG_DIR"
    home = selection.codex_home if codex else selection.config_dir
    if source.get(home_key, home) != home:
        raise RuntimeBindingError("selected_home_environment_mismatch")
    owner.validate_no_reparse_components(Path(home))
    if not Path(home).is_dir():
        raise RuntimeBindingError("selected_home_unavailable")
    selected = {**source, home_key: home}
    auth = owner.resolve_provider_auth_configuration(provider, selected)
    if auth.mode != selection.auth_mode:
        raise RuntimeBindingError("selected_auth_mode_mismatch")
    environment = {**auth.child_environment, home_key: home}
    if not codex:
        owner.validate_no_reparse_components(Path(selection.prompts_dir))
        if not Path(selection.prompts_dir).is_dir():
            raise RuntimeBindingError("selected_prompts_directory_unavailable")
        environment["CLAUDE_PROMPTS_DIR"] = selection.prompts_dir
    return environment, owner.resolve_provider_output_context(auth)


def _verify_runtime(selection: Any) -> None:
    owner = _owner()
    executable = Path(selection.executable)
    owner.validate_no_reparse_components(executable)
    if not executable.is_file():
        raise RuntimeBindingError("selected_runtime_unavailable")
    digest = hashlib.sha256()
    with executable.open("rb") as stream:
        before = os.fstat(stream.fileno())
        while block := stream.read(1_048_576):
            digest.update(block)
        after = os.fstat(stream.fileno())
    # Compare handle metadata consistently: path stat may expose different ctime
    # semantics on Windows. Reopen the path to still detect replacement.
    with executable.open("rb") as current_stream:
        current = os.fstat(current_stream.fileno())
    identities = [(s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns) for s in (before, after, current)]
    if identities[0] != identities[1] or identities[0] != identities[2] or digest.hexdigest() != selection.executable_sha256:
        raise RuntimeBindingError("selected_runtime_changed")


def _ledger(selection: Any):
    writer = _owner()._ledger_owner()
    validator = writer.load_validator()
    budget = (None if selection.ledger_max_events is None and selection.ledger_max_bytes is None
        else validator.resolve_ledger_resource_budget(selection.ledger_max_events, selection.ledger_max_bytes, managed=True))
    return writer, validator, budget


def _events(selection: Any):
    writer, validator, budget = _ledger(selection)
    item = Path(selection.work_item)
    ledger = item / "agent-runs.jsonl"
    lifecycle = validator.load_lifecycle_owner()
    try:
        raw, snapshot = validator._read_ledger_image(ledger, budget)
        budget, resource_inputs = lifecycle._admit_ledger_operation(
            item, ledger, raw, ledger_resource_budget=budget, validator=validator)
        errors = validator.validate_work_item(item, selected_ledger_bytes=raw,
            strict_revise=False, ledger_resource_budget=budget)
        events = validator.load_jsonl(ledger, errors, source_bytes=raw, ledger_resource_budget=budget)
        if errors:
            raise RuntimeBindingError("current_ledger_invalid")
        # Supplied selected bytes do not themselves prove that live custody is
        # still current. Requalify the captured primary and selected participants.
        if snapshot is not None:
            lifecycle._verify_captured_file(snapshot, "WI-LEDGER-RESOURCE-DRIFT")
        if any(not predicate.qualify() for predicate in resource_inputs):
            raise RuntimeBindingError("current_ledger_invalid")
    except (OSError, ValueError, lifecycle.LifecycleError):
        raise RuntimeBindingError("current_ledger_invalid") from None
    return writer, validator, events


def assert_current_launch(request: ExecutionRequest, selection: Any, effect: str) -> None:
    """Current consistency checks, not authority manufactured by a ledger read."""
    if not isinstance(effect, str) or not effect or selection.expected_launch_sha256 is None:
        raise RuntimeBindingError("current_launch_binding_required")
    writer, validator, events = _events(selection)
    launches = [e for e in events if e.get("runId") == request.external_dispatch_id]
    if len(launches) != 1 or launches[0].get("eventKind") != "launch":
        raise RuntimeBindingError("unique_current_launch_required")
    launch = launches[0]
    expected = {
        "workItem": request.work_item_id, "provider": request.provider, "model": request.model,
        "effort": request.effort, "scope": list(request.scope), "assignedRole": request.role,
        "executionRole": "external-reviewer", "artifactIdentity": request.artifact_id,
        "externalDispatchId": request.external_dispatch_id, "externalEvidenceRunId": request.external_evidence_run_id,
        "actualExecutionPath": "direct-external-sdk", "sdkExecution": selected_sdk_execution(request, selection),
        "status": "running", "gate": "none",
    }
    if (writer.launch_event_sha256(launch, validator) != selection.expected_launch_sha256
        or any(launch.get(key) != value for key, value in expected.items())
        or any(e.get("launchRunId") == request.external_dispatch_id or e.get("runId") == request.external_evidence_run_id for e in events)):
        raise RuntimeBindingError("current_launch_changed_or_settled")
    _verify_runtime(selection)


def _require_authority(authority: Callable[[ExecutionRequest, str], None], request: ExecutionRequest, effect: str) -> None:
    if not callable(authority) or inspect.iscoroutinefunction(authority):
        raise RuntimeBindingError("existing_synchronous_policy_owner_required")
    result = authority(request, effect)
    if result is not None:
        if inspect.iscoroutine(result):
            result.close()
        raise RuntimeBindingError("policy_owner_must_raise_on_denial")


def build_launch_arguments(request: ExecutionRequest, selection: Any, *, started_at: str) -> list[str]:
    """Pure exact launch argv for the canonical ledger admission/claim owners.

    This constructs no event, performs no admission, and writes no ledger. Pass
    the result to provider_prompt.prepare_ledger_admission before execution;
    claim_launch remains the sole atomic claim/duplicate-guard owner.
    """
    arguments = ["--work-item", selection.work_item, "append", "--run-id", request.external_dispatch_id,
        "--role", "external-reviewer", "--execution-role", "external-reviewer", "--assigned-role", request.role,
        "--provider", request.provider, "--model", request.model, "--effort", request.effort,
        "--status", "running", "--gate", "none", "--event-kind", "launch",
        "--actual-execution-path", "direct-external-sdk", "--sdk-execution-json", json_text(selected_sdk_execution(request, selection)),
        "--artifact-identity", request.artifact_id, "--external-dispatch-id", request.external_dispatch_id,
        "--external-evidence-run-id", request.external_evidence_run_id, "--effort-mapping-loss", request.effort_mapping_loss,
        "--started-at", started_at, "--updated-at", started_at]
    for item in request.scope:
        arguments.append("--scope=" + item)
    return arguments


def claim_launch(request: ExecutionRequest, selection: Any, *, authority: Callable[[ExecutionRequest, str], None], started_at: str):
    """Produce one launch atomically; an unresolved prior launch is never replayed."""
    if selection.expected_launch_sha256 is not None:
        raise RuntimeBindingError("new_launch_selection_required")
    if Path(selection.work_item).name != request.work_item_id:
        raise RuntimeBindingError("work_item_binding_mismatch")
    _require_authority(authority, request, "sdk_launch_admission")
    _verify_runtime(selection)
    writer, validator, budget = _ledger(selection)
    arguments = build_launch_arguments(request, selection, started_at=started_at)
    event = writer.build_event(writer.build_parser().parse_args(arguments), validator)

    def unique(previous: str):
        errors: list[str] = []
        events = (validator.load_jsonl(Path(selection.work_item) / "agent-runs.jsonl", errors,
                  source_bytes=previous.encode("utf-8"), ledger_resource_budget=budget) if previous else [])
        if errors or any(e.get("runId") in {request.external_dispatch_id, request.external_evidence_run_id} for e in events):
            raise RuntimeBindingError("existing_launch_is_not_replay_authority")
        _require_authority(authority, request, "sdk_launch_commit")
        return event

    writer._append_event_transaction(Path(selection.work_item), validator, unique, ledger_resource_budget=budget)
    # Return known custody immediately. The parent must read back before effects;
    # a readback failure can then be settled/reported against this exact launch.
    return replace(selection, expected_launch_sha256=writer.launch_event_sha256(event, validator))


def create_codex_adapter(request: ExecutionRequest, sink: Any, selection: CodexRuntimeSelection):
    """Real worker-only factory, called after creator-verified Job containment."""
    from .codex import CodexReviewAdapter, _official_client_binding

    assert_current_launch(request, selection, "worker_factory")
    environment, _context = prepare_environment(selection, dict(os.environ))
    # The official SDK overlays config.env on os.environ.copy(). Establish the
    # auth-owner allowlist in this one-operation child before constructing it.
    os.environ.clear()
    os.environ.update(environment)

    def client_factory(approval_handler):
        from openai_codex.client import CodexConfig
        assert_current_launch(request, selection, "client_factory")
        config = CodexConfig(codex_bin=selection.executable, cwd=request.cwd, env=dict(environment),
                             config_overrides=selection.config_overrides)
        return _official_client_binding(config, approval_handler)

    def verify_account(current: ExecutionRequest, payload: dict[str, Any]) -> str:
        account = payload.get("account")
        if current != request or type(account) is not dict:
            raise RuntimeBindingError("selected_account_unavailable")
        if selection.auth_mode == "codex-auth-file":
            if account.get("type") != "chatgpt" or account.get("email") != selection.expected_account_email:
                raise RuntimeBindingError("selected_account_mismatch")
        elif account.get("type") != "apiKey":
            raise RuntimeBindingError("selected_auth_mode_mismatch")
        return request.account_binding

    def require_current(current: ExecutionRequest, effect: str) -> None:
        if current != request:
            raise RuntimeBindingError("worker_request_binding_mismatch")
        assert_current_launch(current, selection, effect)
        # Ledger consistency is not permission. The existing owned duplex channel
        # asks the original parent policy/account/budget owner before every effect.
        # Approval is consumed for this exact request/effect, never cached here.
        sink.authorize_from_thread(current, effect)

    return CodexReviewAdapter(
        client_factory=client_factory,
        assert_current=require_current,
        verify_account=verify_account, record=sink.record_from_thread,
        mcp_scope=selection.mcp_scope,
        bounded_startup_profile=selection.config_overrides == CODEX_BOUNDED_REVIEW_OVERRIDES,
    )


@dataclass(frozen=True, slots=True)
class RuntimeRun:
    """Parent-held output for the existing receiving owner, not accepted review."""

    request: ExecutionRequest
    selection: Any
    output_context: Any
    observation: Any | None
    terminal: dict[str, object] | None = None
    launch_error: str | None = None


def _settle_before_worker_failure(request: ExecutionRequest, selection: Any, *, started_at: str) -> dict[str, object]:
    """Record known no-worker failure, without inventing observed SDK metadata."""
    writer, _validator, _budget = _ledger(selection)
    from datetime import datetime, timezone
    updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    resources = ([] if _budget is None else ["--ledger-max-events", str(_budget.max_events),
        "--ledger-max-bytes", str(_budget.max_ledger_bytes)])
    args = [*resources, "--work-item", selection.work_item, "settle-launch", "--launch-run-id", request.external_dispatch_id,
        "--expected-launch-sha256", selection.expected_launch_sha256, "--run-id", request.external_evidence_run_id,
        "--status", "blocked", "--gate", "none", "--started-at", started_at, "--updated-at", updated_at,
        "--evidence", "command:SDK worker was not invoked; launch preparation failed"]
    if writer.main(args, settlement_output=sys.stderr) != 0:
        raise RuntimeBindingError("preworker_failure_settlement_unavailable")
    owner = _owner()
    terminal = owner.read_back_external_terminal(
        owner.Control(ledger=selection.work_item, ledger_max_events=selection.ledger_max_events,
                      ledger_max_bytes=selection.ledger_max_bytes), request.provider, request.external_dispatch_id)
    if terminal is None or terminal.get("status") != "blocked" or terminal.get("sdkExecution") != selected_sdk_execution(request, selection):
        raise RuntimeBindingError("preworker_failure_readback_unavailable")
    return terminal


def run_codex(
    request: ExecutionRequest,
    selection: CodexRuntimeSelection,
    *,
    owner: Any,
    source_environment: dict[str, str],
    authority: Callable[[ExecutionRequest, str], None],
    deadline_monotonic: float,
    cancellation_probe: Callable[[], bool],
    started_at: str,
    capture_limit_bytes: int = MAX_STDIN_BYTES,
) -> RuntimeRun:
    """Frame a raw Codex task, then execute through the same admitted core."""
    return run_admitted_codex(
        prepare_codex_request(request), selection, owner=owner,
        source_environment=source_environment, authority=authority,
        deadline_monotonic=deadline_monotonic, cancellation_probe=cancellation_probe,
        started_at=started_at, capture_limit_bytes=capture_limit_bytes,
    )


def run_admitted_codex(request: ExecutionRequest, selection: CodexRuntimeSelection, **options) -> RuntimeRun:
    """Execute the exact effective request already admitted by its current owner."""
    if request.provider != "codex" or type(selection) is not CodexRuntimeSelection:
        raise RuntimeBindingError("codex_request_required")
    return run_admitted_review(request, selection, **options)


def run_admitted_review(
    request: ExecutionRequest,
    selection: Any,
    *,
    owner: Any,
    source_environment: dict[str, str],
    authority: Callable[[ExecutionRequest, str], None],
    deadline_monotonic: float,
    cancellation_probe: Callable[[], bool],
    started_at: str,
    capture_limit_bytes: int = MAX_STDIN_BYTES,
    authorize_tool: Callable[[ExecutionRequest, str, dict[str, Any]], None] | None = None,
    verify_account: Callable[[ExecutionRequest, dict[str, Any]], str] | None = None,
) -> RuntimeRun:
    """Complete explicit parent launch through the fixed worker, without activation.

    The caller supplies the existing policy/account/budget owner and cancellation
    probe (for example threading.Event.is_set). Setting that probe requests native
    interrupt and OS settlement through the existing process owner. This blocking
    API must run off the caller's UI/event-loop thread. It returns captured evidence
    to the receiving owner; it never treats SDK output as accepted project review.

    Native home/project config autoload retains its existing Codex owner and hook
    trust gate. The policy callback must admit that actual selected configuration;
    this function does not pretend a home-path hash proves its complete contents.
    """
    from process_supervision.process_runner import EnvironmentRowV1, ProcessRunnerV1
    from process_supervision.sdk_worker import run_sdk_worker

    if type(capture_limit_bytes) is not int or not 0 < capture_limit_bytes <= MAX_STDIN_BYTES:
        raise RuntimeBindingError("invalid_worker_capture_budget")
    if type(owner) is not ProcessRunnerV1 or not callable(cancellation_probe):
        raise RuntimeBindingError("existing_process_owner_and_cancellation_probe_required")
    if selection.expected_launch_sha256 is not None:
        raise RuntimeBindingError("existing_launch_is_not_replay_authority")
    validate_admitted_request(request, selection)
    if request.provider == "claude":
        if any(not callable(callback) or inspect.iscoroutinefunction(callback)
               for callback in (authorize_tool, verify_account)):
            raise RuntimeBindingError("existing_claude_tool_and_account_owners_required")

    def require_live_request() -> None:
        cancelled = cancellation_probe()
        if type(cancelled) is not bool:
            raise RuntimeBindingError("invalid_cancellation_observation")
        if cancelled:
            raise RuntimeBindingError("cancelled_before_worker")
        if type(deadline_monotonic) not in {int, float} or not math.isfinite(deadline_monotonic):
            raise RuntimeBindingError("invalid_operation_deadline")
        if time.monotonic() >= deadline_monotonic:
            raise RuntimeBindingError("deadline_before_worker")

    require_live_request()
    effective = request
    _require_authority(authority, effective, "sdk_prepare")
    environment, output_context = prepare_environment(selection, source_environment)
    _verify_runtime(selection)
    require_live_request()
    admitted = claim_launch(effective, selection, authority=authority, started_at=started_at)
    try:
        # The trust probe is itself a native runtime operation. Claim first so
        # replayed launches cannot trigger even this provider startup effect.
        if request.provider == "codex":
            assert_current_launch(effective, admitted, "parent_hook_trust")
            require_live_request()
            _require_authority(authority, effective, "sdk_hook_trust")
            # The canonical hook inventory must use the same CLI override
            # layer as the SDK's subsequent app-server, not just the same home.
            command = [selection.executable]
            for override in selection.config_overrides:
                command.extend(("--config", override))
            if _owner().require_codex_hook_trust(
                owner, command, Path(selection.codex_home), Path(request.cwd),
                deadline_monotonic=deadline_monotonic, cancellation_probe=cancellation_probe,
            ) != 0:
                raise RuntimeBindingError("selected_codex_hook_trust_unavailable")
        assert_current_launch(effective, admitted, "parent_worker_start")
        _require_authority(authority, effective, "sdk_worker_start")
        require_live_request()
    except Exception as error:
        terminal = _settle_before_worker_failure(effective, admitted, started_at=started_at)
        code = str(error) if isinstance(error, RuntimeBindingError) else "preworker_preparation_failed"
        return RuntimeRun(effective, admitted, output_context, None, terminal, code)
    # Once invoked, any exception has an uncertain process/effect outcome. Never
    # manufacture a no-worker terminal or automatically retry that operation.
    def authorize_effect(current: ExecutionRequest, effect: str, context: dict[str, Any] | None = None) -> None:
        if current != effective:
            raise RuntimeBindingError("worker_request_binding_mismatch")
        require_live_request()
        assert_current_launch(current, admitted, effect)
        _require_authority(authority, current, effect)
        if context is not None:
            if request.provider != "claude" or type(context) is not dict:
                raise RuntimeBindingError("unexpected_authority_context")
            if effect == "tool" and set(context) == {"kind", "name", "arguments"} and context["kind"] == "tool":
                if type(context["name"]) is not str or type(context["arguments"]) is not dict:
                    raise RuntimeBindingError("invalid_tool_authority_context")
                if authorize_tool(current, context["name"], context["arguments"]) is not None:
                    raise RuntimeBindingError("tool_owner_must_raise_on_denial")
            elif effect == "account" and set(context) == {"kind", "evidence"} and context["kind"] == "account":
                if type(context["evidence"]) is not dict or verify_account(current, context["evidence"]) != request.account_binding:
                    raise RuntimeBindingError("selected_account_mismatch")
            else:
                raise RuntimeBindingError("unexpected_authority_context")

    observation = run_sdk_worker(
        owner, effective, environment=tuple(EnvironmentRowV1(k, v) for k, v in environment.items()),
        deadline_monotonic=deadline_monotonic, job_memory_limit_bytes=admitted.job_memory_limit_bytes,
        cancellation_probe=cancellation_probe, runtime_selection=admitted.to_dict(), authority=authorize_effect,
        capture_limit_bytes=capture_limit_bytes,
    )
    return RuntimeRun(effective, admitted, output_context, observation)


class SdkReviewExecutor:
    """One concrete coordinator tool: owned execution, receiving and ledger readback.

    This object retains acquired evidence in memory while existing owners alone
    publish artifacts and durable state. It neither stores SDK snapshots nor
    reconstructs observed SDK/process facts from selected ledger metadata. An
    existing launch requires explicit reconciliation, never a second execution.
    """

    def __init__(
        self, *, request_id: str, authority: Any, selection: Any, process_owner: Any,
        source_environment: dict[str, str], artifact: str, deadline_monotonic: float,
        cancellation_probe: Callable[[], bool], started_at: str,
        authorize_tool: Callable[[ExecutionRequest, str, dict[str, Any]], None] | None = None,
        verify_account: Callable[[ExecutionRequest, dict[str, Any]], str] | None = None,
    ) -> None:
        if not isinstance(request_id, str) or not request_id or any(
            not callable(getattr(authority, name, None)) or inspect.iscoroutinefunction(getattr(authority, name, None))
            for name in ("resolve", "assert_current")
        ):
            raise RuntimeBindingError("existing_request_authority_owner_required")
        if type(source_environment) is not dict or not callable(cancellation_probe):
            raise RuntimeBindingError("explicit_environment_and_cancellation_probe_required")
        self._request_id, self._authority, self._selection = request_id, authority, selection
        self._process_owner, self._environment = process_owner, dict(source_environment)
        self._artifact, self._deadline, self._external_cancel, self._started_at = artifact, deadline_monotonic, cancellation_probe, started_at
        self._authorize_tool, self._verify_account = authorize_tool, verify_account
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self._request: ExecutionRequest | None = None
        self.runtime_run: RuntimeRun | None = None
        self.terminal: dict[str, object] | None = None
        self.execution_result: ExecutionResult | None = None

    def validate_request(self) -> ExecutionRequest:
        """Preflight the owner-resolved input before a coordinator model effect."""
        from process_supervision.process_runner import ProcessRunnerV1
        from .receiving import review_artifact_target

        request = self._authority.resolve(self._request_id)
        validate_admitted_request(request, self._selection)
        if type(self._process_owner) is not ProcessRunnerV1:
            raise RuntimeBindingError("existing_process_owner_required")
        if type(self._deadline) not in {int, float} or not math.isfinite(self._deadline):
            raise RuntimeBindingError("invalid_operation_deadline")
        if self._cancelled():
            raise RuntimeBindingError("cancelled_before_worker")
        if time.monotonic() >= self._deadline:
            raise RuntimeBindingError("deadline_before_worker")
        if self._selection.expected_launch_sha256 is not None:
            raise RuntimeBindingError("existing_launch_is_not_replay_authority")
        review_artifact_target(self._selection.work_item, self._artifact, must_be_new=True)
        # Read-only replay preflight avoids spending a coordinator call on a
        # known occupied operation. The later atomic claim still owns exclusion.
        if os.path.lexists(Path(self._selection.work_item) / "agent-runs.jsonl"):
            _writer, _validator, events = _events(self._selection)
            if any(event.get("runId") in {request.external_dispatch_id, request.external_evidence_run_id}
                   for event in events):
                raise RuntimeBindingError("existing_launch_is_not_replay_authority")
        if request.provider == "claude" and any(
            not callable(callback) or inspect.iscoroutinefunction(callback)
            for callback in (self._authorize_tool, self._verify_account)
        ):
            raise RuntimeBindingError("existing_claude_tool_and_account_owners_required")
        return request

    def _current(self, request: ExecutionRequest, effect: str) -> None:
        if self._authority.resolve(self._request_id) != request:
            raise RuntimeBindingError("admitted_request_changed")
        _require_authority(self._authority.assert_current, request, effect)

    def _cancelled(self) -> bool:
        external = self._external_cancel()
        if type(external) is not bool:
            raise RuntimeBindingError("invalid_cancellation_observation")
        return self._cancel.is_set() or external

    def _execute(self, request: ExecutionRequest) -> ExecutionResult:
        if self.validate_request() != request:
            raise RuntimeBindingError("admitted_request_changed")
        self._current(request, "executor_start")
        run = run_admitted_review(
            request, self._selection, owner=self._process_owner,
            source_environment=self._environment, authority=self._current,
            deadline_monotonic=self._deadline, cancellation_probe=self._cancelled,
            started_at=self._started_at, authorize_tool=self._authorize_tool,
            verify_account=self._verify_account,
        )
        self.runtime_run = run  # Retain before receiving can fail.
        if run.observation is None:
            if run.terminal is None or run.terminal.get("status") != "blocked":
                raise RuntimeBindingError("runtime_result_unavailable")
            self.terminal = run.terminal
            result = ExecutionResult(request=request, status="incomplete", execution_error=run.launch_error or "preworker_failure")
        else:
            from datetime import datetime, timezone
            from .receiving import receive_runtime_run
            updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            terminal = receive_runtime_run(run, artifact=self._artifact, started_at=self._started_at, updated_at=updated_at)
            self.terminal = terminal
            result = run.observation.result
            if not isinstance(result, ExecutionResult) or result.request != request:
                raise RuntimeBindingError("runtime_result_unavailable")
            if terminal.get("status") == "blocked" and result.status == "completed":
                result = replace(result, status="incomplete", execution_error="received_execution_incomplete")
        # Scan the exact final tool-visible projection, including usage and the
        # no-worker error path. Raw evidence stays retained for reconciliation;
        # rejected content must never become coordinator output.
        from .receiving import scan_execution_output
        scan_execution_output(result, run.output_context)
        self.execution_result = result
        return result

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        with self._lock:
            if self._request is not None:
                raise RuntimeBindingError("operation_already_consumed")
            self._request = request
        task = asyncio.create_task(asyncio.to_thread(self._execute, request))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            self._cancel.set()
            return await drain_owned(task)

    async def cancel(self, run_id: str) -> CancelReceipt:
        with self._lock:
            if self._request is None or self._request.run_id != run_id:
                return CancelReceipt(run_id, False, False, error="unknown_execution")
            self._cancel.set()
        run = self.runtime_run
        observed = run.observation.cancel if run is not None and run.observation is not None else None
        return observed if observed is not None else CancelReceipt(run_id, True, False)
