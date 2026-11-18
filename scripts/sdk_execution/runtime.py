"""Explicit SDK composition using the existing admission and process owners.

Importing this module does not load a provider SDK, discover credentials, install
dependencies or launch anything. The operator supplies every runtime/account
selection and the existing policy owner must admit the effective request. Native
Codex configuration and instructions retain their existing owner; selecting a
home is not evidence that its complete configuration was observed or immutable.
"""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
import hashlib
import json
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
from .coordination import CoordinationInferenceRequest, CoordinationInferenceResult
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
    installed_hook_root: str | None = None

    def __post_init__(self) -> None:
        if self.installed_hook_root is not None and (
            type(self.installed_hook_root) is not str or not self.installed_hook_root
            or not Path(self.installed_hook_root).is_absolute()
            or any(ord(char) < 32 or ord(char) == 127 for char in self.installed_hook_root)
        ):
            raise RuntimeBindingError("invalid_installed_hook_root")
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
    if provider == "copilot":
        from .copilot import CopilotError, CopilotRuntimeSelection
        try:
            return CopilotRuntimeSelection.from_dict(value)
        except CopilotError as error:
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


def _worker_authority_roots(provider="codex") -> tuple[Path, ...]:
    """Loaded code/data installations, not ambient credential values."""
    import importlib.util
    roots = [Path(__file__).absolute().parents[2], Path(__file__).resolve().parents[2],
             Path(sys.executable).parent,
             Path(sys.prefix), Path(sys.base_prefix)]
    # Top-level discovery does not import or launch the provider package.
    spec = importlib.util.find_spec({"codex": "openai_codex", "claude": "claude_agent_sdk"}[provider])
    if spec is not None:
        if spec.origin and spec.origin not in {"built-in", "frozen"}:
            roots.append(Path(spec.origin).parent)
        roots.extend(Path(p) for p in (spec.submodule_search_locations or ()))
    return tuple(roots)


def validate_worker_custody(request: ExecutionRequest, selection: Any, *, expected_identity=None):
    """Check selected path custody, not OS isolation or arbitrary file effects.

    Returned identity may be retained by this operation's existing effect owner.
    Public receipt/capture targets require their separate dispatcher check.
    """
    if request.write_workspace is None:
        return None
    from .claude import ClaudeRuntimeSelection
    expected = {"codex": CodexRuntimeSelection, "claude": ClaudeRuntimeSelection}.get(request.provider)
    if type(selection) is not expected:
        raise RuntimeBindingError("worker_runtime_selection_required")
    execution_role(request)
    owner = _owner()
    try:
        root = Path(request.write_workspace)
        owner.validate_no_reparse_components(root)
        resolved = root.resolve(strict=True)
        if (not root.is_dir() or request.cwd != request.write_workspace
                or os.path.normcase(str(resolved)) != os.path.normcase(request.write_workspace)):
            raise ValueError("noncanonical workspace")
        protected = [Path(selection.work_item), Path(selection.executable).parent,
                     *(_worker_authority_roots() if request.provider == "codex" else _worker_authority_roots("claude"))]
        if request.provider == "codex":
            protected.append(Path(selection.codex_home))
            if selection.installed_hook_root is not None:
                protected.append(Path(selection.installed_hook_root))
        else:
            protected.extend((Path(selection.config_dir), Path(selection.prompts_dir)))
        for path in protected:
            owner.validate_no_reparse_components(path)
            guarded = path.resolve(strict=False)
            if resolved.is_relative_to(guarded) or guarded.is_relative_to(resolved):
                raise RuntimeBindingError("worker_workspace_overlaps_protected_state")
        stat = root.stat()
        identity = (os.path.normcase(str(resolved)), stat.st_dev, stat.st_ino)
        if expected_identity is not None and identity != expected_identity:
            raise RuntimeBindingError("worker_workspace_identity_changed")
        return identity
    except RuntimeBindingError:
        raise
    except (OSError, ValueError, ImportError):
        raise RuntimeBindingError("worker_workspace_custody_unavailable") from None


def _require_runtime_result_route(request: ExecutionRequest) -> None:
    # Evidence/admission compatibility is separate from enabling a live factory.
    if request.provider == "copilot":
        from .copilot import validate_copilot_request
        validate_copilot_request(request)
    if request.provider == "claude" and request.result_kind == "task":
        _roles, _reviewers, workers, _unsupported = _owner()._external_role_taxonomy()
        if (type(request) is not ExecutionRequest or
                (request.role not in workers if request.write_workspace is not None else request.role != "consultant")):
            raise RuntimeBindingError("claude_consultant_task_request_required")
    if request.provider == "claude" and request.tool_profile == "prompt-only" and request.result_kind == "review":
        _roles, reviewers, _workers, _unsupported = _owner()._external_role_taxonomy()
        if type(request) is not ExecutionRequest or request.role not in reviewers:
            raise RuntimeBindingError("claude_prompt_only_reviewer_required")


def _require_task_auth_route(request: ExecutionRequest, selection: Any) -> None:
    if request.provider == "claude" and (request.result_kind == "task" or request.tool_profile == "prompt-only"):
        if not _owner().claude_programmatic_auth_mode_supported(selection.auth_mode):
            raise RuntimeBindingError("claude_programmatic_auth_mode_required")


def validate_admitted_request(request: ExecutionRequest, selection: Any) -> None:
    """Check exact current common-governance input, without changing admission."""
    if type(request) not in {ExecutionRequest, CoordinationInferenceRequest}:
        raise RuntimeBindingError("admitted_execution_request_required")
    _require_runtime_result_route(request)
    if request.write_workspace is not None:
        validate_worker_custody(request, selection)
    if type(request) is CoordinationInferenceRequest:
        if (selection.auth_mode != "codex-auth-file"
            or selection.config_overrides != CODEX_BOUNDED_REVIEW_OVERRIDES
            or selection.mcp_scope.servers):
            raise RuntimeBindingError("bounded_subscription_coordination_selection_required")
    runtime_selection_from_dict(request.provider, selection.to_dict())
    _require_task_auth_route(request, selection)
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
    _require_runtime_result_route(request)
    if request.write_workspace is not None:
        validate_worker_custody(request, selection)
    runtime_selection_from_dict(request.provider, selection.to_dict())
    _require_task_auth_route(request, selection)
    if request.provider == "codex":
        adapter, sandbox, approval = "openai-codex", ("workspace-write" if request.write_workspace is not None else "read-only"), "deny_all"
    elif request.provider == "claude":
        adapter, sandbox, approval = "claude-agent-sdk", ("tool-restricted-workspace-write" if request.write_workspace is not None else "tool-restricted-read-only"), "deny_unadmitted"
    elif request.provider == "copilot":
        adapter, sandbox, approval = "microsoft-copilot-sdk", "tool-restricted-read-only", "deny_all"
    else:
        raise RuntimeBindingError("unsupported_runtime_provider")
    value = {
        "schemaVersion": 2, "adapter": adapter, "model": request.model, "effort": request.effort,
        "sandboxMode": sandbox, "approvalPolicy": approval,
        "accountBinding": request.account_binding, "requestSha256": request_sha256(request, selection),
    }
    if request.write_workspace is not None:
        value["writeWorkspaceSha256"] = hashlib.sha256(request.write_workspace.encode("utf-8")).hexdigest()
    if request.native_continuation is not None:
        value["forkSourceSha256" if request.context_mode == "fork" else "continuationSourceSha256"] = request.native_continuation.source_sha256
    if type(request) is CoordinationInferenceRequest:
        value.update(schemaVersion=3, operationKind="coordination-inference",
                     innerRequestSha256=request.inner_request_sha256,
                     outerBudgetBinding=request.outer_budget_id, innerBudgetBinding=request.inner_budget_id)
        if request.child_choice_json is not None:
            from .coordination import child_choice_sha256
            value.pop("innerRequestSha256")
            value.update(schemaVersion=5, operationKind="scoped-child-coordination",
                         childChoiceSha256=child_choice_sha256(request.child_choice_json))
            if request.decision_session_mode == "native-persistent":
                value.update(decisionSessionMode="native-persistent",childAssignmentSha256=json.loads(request.child_choice_json)["assignment_sha256"])
    return value


def prepare_environment(selection: Any, source: dict[str, str]):
    """Reuse the auth/output owners with explicit input, never os.environ fallback."""
    if type(source) is not dict or any(type(k) is not str or type(v) is not str for k, v in source.items()):
        raise RuntimeBindingError("explicit_environment_required")
    owner = _owner()
    from .copilot import CopilotRuntimeSelection
    if type(selection) is CopilotRuntimeSelection:
        runtime_selection_from_dict("copilot", selection.to_dict())
        home = Path(selection.base_directory)
        owner.validate_no_reparse_components(home)
        if not home.is_dir(): raise RuntimeBindingError("selected_home_unavailable")
        auth = owner.resolve_provider_auth_configuration("copilot", source)
        if auth.mode != selection.auth_mode: raise RuntimeBindingError("selected_auth_mode_mismatch")
        return dict(auth.child_environment), owner.resolve_provider_output_context(auth)
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
    validate_worker_custody(request, selection)
    writer, validator, events = _events(selection)
    launches = [e for e in events if e.get("runId") == request.external_dispatch_id]
    if len(launches) != 1 or launches[0].get("eventKind") != "launch":
        raise RuntimeBindingError("unique_current_launch_required")
    launch = launches[0]
    expected = {
        "workItem": request.work_item_id, "provider": request.provider, "model": request.model,
        "effort": request.effort, "scope": list(request.scope), "assignedRole": request.role,
        "executionRole": execution_role(request), "artifactIdentity": request.artifact_id,
        "externalDispatchId": request.external_dispatch_id, "externalEvidenceRunId": request.external_evidence_run_id,
        "actualExecutionPath": "direct-external-sdk", "sdkExecution": selected_sdk_execution(request, selection),
        "status": "running", "gate": "none",
    }
    if type(request) is CoordinationInferenceRequest:
        expected["role"] = "lead"
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


def execution_role(request: ExecutionRequest) -> str:
    """Project provenance for the already validated operation, not permission."""
    _require_runtime_result_route(request)
    if request.write_workspace is not None:
        if type(request) is not ExecutionRequest or request.provider not in {"codex", "claude"} or request.result_kind != "task":
            raise RuntimeBindingError("worker_task_request_required")
        _roles, _reviewers, workers, _unsupported = _owner()._external_role_taxonomy()
        if request.role not in workers:
            raise RuntimeBindingError("worker_role_required")
        return "external-worker"
    if type(request) is CoordinationInferenceRequest:
        return "main"
    if type(request) is not ExecutionRequest:
        raise RuntimeBindingError("admitted_execution_request_required")
    return "consultant" if request.result_kind == "task" else "external-reviewer"


def build_launch_arguments(request: ExecutionRequest, selection: Any, *, started_at: str) -> list[str]:
    """Pure exact launch argv for the canonical ledger admission/claim owners.

    This constructs no event, performs no admission, and writes no ledger. Pass
    the result to provider_prompt.prepare_ledger_admission before execution;
    claim_launch remains the sole atomic claim/duplicate-guard owner.
    """
    selected_role = execution_role(request)
    actor_role = "lead" if selected_role == "main" else selected_role
    arguments = ["--work-item", selection.work_item, "append", "--run-id", request.external_dispatch_id,
        "--role", actor_role, "--execution-role", selected_role, "--assigned-role", request.role,
        "--provider", request.provider, "--model", request.model, "--effort", request.effort,
        "--status", "running", "--gate", "none", "--event-kind", "launch",
        "--actual-execution-path", "direct-external-sdk", "--sdk-execution-json", json_text(selected_sdk_execution(request, selection)),
        "--artifact-identity", request.artifact_id, "--external-dispatch-id", request.external_dispatch_id,
        "--external-evidence-run-id", request.external_evidence_run_id, "--effort-mapping-loss", request.effort_mapping_loss,
        "--started-at", started_at, "--updated-at", started_at]
    for item in request.scope:
        arguments.append("--scope=" + item)
    return arguments


def claim_launch(request: ExecutionRequest, selection: Any, *, authority: Callable[[ExecutionRequest, str], None], started_at: str, previous_run=None, previous_terminal=None):
    """Produce one launch atomically; an unresolved prior launch is never replayed."""
    if selection.expected_launch_sha256 is not None:
        raise RuntimeBindingError("new_launch_selection_required")
    if Path(selection.work_item).name != request.work_item_id:
        raise RuntimeBindingError("work_item_binding_mismatch")
    validate_worker_custody(request, selection)
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
        if type(request) is CoordinationInferenceRequest and request.decision_session_mode=="native-persistent":
            anchor=json.loads(request.child_choice_json)["assignment_sha256"]
            prior=[e for e in events if e.get("eventKind")=="launch" and e.get("sdkExecution",{}).get("childAssignmentSha256")==anchor]
            if request.native_continuation is None and prior:
                raise RuntimeBindingError("child_native_session_already_started")
        if request.native_continuation is not None:
            _validate_continuation(request, selection, previous_run, previous_terminal, events=events)
            source = request.native_continuation.source_sha256
            if request.context_mode == "continuation" and any(e.get("eventKind") == "launch" and e.get("sdkExecution", {}).get("continuationSourceSha256") == source for e in events):
                raise RuntimeBindingError("continuation_predecessor_already_consumed")
        _require_authority(authority, request, "sdk_launch_commit")
        return event

    writer._append_event_transaction(Path(selection.work_item), validator, unique, ledger_resource_budget=budget)
    # Return known custody immediately. The parent must read back before effects;
    # a readback failure can then be settled/reported against this exact launch.
    return replace(selection, expected_launch_sha256=writer.launch_event_sha256(event, validator))


def create_codex_adapter(request: ExecutionRequest, sink: Any, selection: CodexRuntimeSelection):
    """Real worker-only factory, called after creator-verified Job containment."""
    from .codex import CodexConsultantAdapter, CodexReviewAdapter, CodexWorkerAdapter, _official_client_binding
    if request.result_kind == "task":
        validate_admitted_request(request, selection)
    adapter_type = (CodexWorkerAdapter if request.write_workspace is not None else
                    CodexConsultantAdapter if request.result_kind == "task" else CodexReviewAdapter)
    workspace_identity = validate_worker_custody(request, selection)
    if type(request) is CoordinationInferenceRequest:
        validate_admitted_request(request, selection)
        from .coordination_codex import CodexCoordinationAdapter
        adapter_type = CodexCoordinationAdapter

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
        validate_worker_custody(current, selection, expected_identity=workspace_identity)
        assert_current_launch(current, selection, effect)
        # Ledger consistency is not permission. The existing owned duplex channel
        # asks the original parent policy/account/budget owner before every effect.
        # Approval is consumed for this exact request/effect, never cached here.
        sink.authorize_from_thread(current, effect)

    return adapter_type(
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


_CONTINUATION_CONTEXT_FIELDS = ("work_item_id", "provider", "role", "model", "effort", "cwd",
    "account_binding", "coordinator_binding", "scope", "write_workspace", "tool_profile")


def continuation_context_sha256(request, selection):
    """Consistency commitment, not account identity or permission to launch."""
    controls = {name: getattr(request, name) for name in _CONTINUATION_CONTEXT_FIELDS}
    if type(request) is CoordinationInferenceRequest:
        controls.update(decision_session_mode=request.decision_session_mode,
            assignment_sha256=json.loads(request.child_choice_json)["assignment_sha256"],
            system_instructions=request.system_instructions,
            governance_prefix=request.prompt[:-len(request.inference_payload)])
    runtime = selection.to_dict()
    runtime.pop("expected_launch_sha256", None)
    return hashlib.sha256(json_text({"controls": controls, "runtime": runtime}).encode()).hexdigest()


def _received_native_context(request, selection, predecessor_evidence_run_id, *, events=None, with_document=False):
    """Read an already received artifact; do not reconstruct a process observation."""
    from .contracts import NativeContinuation, strict_json
    from .receiving import review_artifact_target
    validate_admitted_request(request, selection)
    coordination = type(request) is CoordinationInferenceRequest and request.child_choice_json is not None and request.decision_session_mode == "native-persistent"
    if (request.provider != "codex" or (not coordination and (request.role != "consultant" or request.result_kind != "task"))
            or request.write_workspace is not None or selection.expected_launch_sha256 is not None):
        raise RuntimeBindingError("received_continuation_predecessor_required")
    if events is None:
        _writer, _validator, events = _events(selection)
    terminals = [e for e in events if e.get("runId") == predecessor_evidence_run_id]
    if len(terminals) != 1:
        raise RuntimeBindingError("continuation_receipt_changed")
    terminal = terminals[0]
    launches = [e for e in events if e.get("runId") == terminal.get("launchRunId")]
    if len(launches) != 1:
        raise RuntimeBindingError("continuation_receipt_changed")
    launch = launches[0]
    expected = {"workItem": request.work_item_id, "provider": "codex", "model": request.model,
        "effort": request.effort, "scope": list(request.scope), "assignedRole": "lead" if coordination else "consultant",
        "executionRole": "main" if coordination else "consultant", "actualExecutionPath": "direct-external-sdk"}
    selected = launch.get("sdkExecution")
    if (launch.get("eventKind") != "launch" or terminal.get("eventKind") != "terminal"
            or terminal.get("status") != "completed" or terminal.get("gate") != "none"
            or any(launch.get(k) != v or terminal.get(k) != v for k,v in expected.items())
            or type(selected) is not dict or selected.get("schemaVersion") != (5 if coordination else 2)
            or not _sha256(selected.get("requestSha256")) or terminal.get("sdkExecution") != selected
            or launch.get("externalEvidenceRunId") != predecessor_evidence_run_id
            or terminal.get("externalEvidenceRunId") != predecessor_evidence_run_id
            or launch.get("externalDispatchId") != launch.get("runId")
            or terminal.get("externalDispatchId") != launch.get("runId")
            or terminal.get("artifactIdentity") != launch.get("artifactIdentity")):
        raise RuntimeBindingError("continuation_receipt_changed")
    if ({request.external_dispatch_id, request.external_evidence_run_id} & {launch["runId"], terminal["runId"]}
            or request.artifact_id == terminal.get("artifactIdentity")):
        raise RuntimeBindingError("continuation_requires_new_operation")
    size = terminal.get("artifactSizeBytes")
    if type(size) is not int or size <= 0 or not _sha256(terminal.get("artifactRevision")):
        raise RuntimeBindingError("continuation_artifact_changed")
    artifact = review_artifact_target(selection.work_item, terminal.get("artifact", ""))
    resolved = artifact.resolve(strict=True)
    # The existing validated receipt supplies the exact read bound, not a new cap.
    with artifact.open("rb") as stream:
        identity = os.fstat(stream.fileno())
        if identity.st_size != size:
            raise RuntimeBindingError("continuation_artifact_changed")
        content = stream.read(size + 1)
        current = artifact.stat()
    if (len(content) != size or artifact.resolve(strict=True) != resolved
            or (identity.st_dev, identity.st_ino) != (current.st_dev, current.st_ino)
            or hashlib.sha256(content).hexdigest() != terminal["artifactRevision"]):
        raise RuntimeBindingError("continuation_artifact_changed")
    document = strict_json(content.decode("utf-8"), max_bytes=size)
    document_keys = ({"operation","evidence","process","reported_sdk_configuration","native_continuation"} if coordination
        else {"task","reported_sdk_configuration","native_continuation"})
    if coordination and type(document) is dict and "child_proposal" in document:document_keys.add("child_proposal")
    if type(document) is not dict or set(document) != document_keys:
        raise RuntimeBindingError("continuation_durable_provenance_required")
    native = document["native_continuation"]
    keys = {"schema_version", "thread_id", "turn_id", "context_sha256"}
    if (type(native) is not dict or type(native.get("schema_version")) is not int
            or native["schema_version"] not in {1, 2}
            or set(native) != (keys if native["schema_version"] == 1 else keys | {"session_depth"})
            or native["context_sha256"] != continuation_context_sha256(request, selection)):
        raise RuntimeBindingError("continuation_scope_changed")
    depth = native.get("session_depth")
    if depth is not None and (type(depth) is not int or depth < 0):
        raise RuntimeBindingError("invalid_native_session_depth")
    reported = document["reported_sdk_configuration"]
    selected_only={"schemaVersion", "requestSha256"}
    if coordination:
        selected_only.update({"operationKind","childChoiceSha256","outerBudgetBinding","innerBudgetBinding","decisionSessionMode","childAssignmentSha256"})
        if (selected.get("decisionSessionMode")!="native-persistent" or selected.get("childAssignmentSha256")!=json.loads(request.child_choice_json)["assignment_sha256"]
            or document["operation"]!="scoped-child-coordination"):
            raise RuntimeBindingError("continuation_scope_changed")
    if (type(reported) is not dict or reported.get("schemaVersion") != 1
            or {k:v for k,v in reported.items() if k not in {"schemaVersion", "sdkVersion", "runtimeVersion"}}
            != {k:v for k,v in selected.items() if k not in selected_only}):
        raise RuntimeBindingError("continuation_receipt_changed")
    source=NativeContinuation(launch["runId"], terminal["runId"], selected["requestSha256"], native["thread_id"], native["turn_id"])
    return (source,depth,document,terminal) if with_document else (source,depth)


def _received_continuation_source(request, selection, predecessor_evidence_run_id, *, events=None):
    return _received_native_context(request, selection, predecessor_evidence_run_id, events=events)[0]


def native_session_depth(request, selection):
    """Observed Orchestrarium session lineage, not provider subagent depth."""
    if request.native_continuation is None:
        return 0
    source, depth = _received_native_context(request, replace(selection, expected_launch_sha256=None),
        request.native_continuation.prior_evidence_run_id)
    if source != request.native_continuation:
        raise RuntimeBindingError("continuation_observed_binding_mismatch")
    return None if depth is None else depth + (1 if request.context_mode == "fork" else 0)


def prepare_received_continuation_request(request, selection, *, predecessor_evidence_run_id, context_mode="continuation"):
    """Prepare a new task from durable received evidence, without model effects."""
    if context_mode not in {"continuation", "fork"}:
        raise RuntimeBindingError("invalid_native_context_mode")
    source = _received_continuation_source(request, selection, predecessor_evidence_run_id)
    return replace(request, context_mode=context_mode, native_continuation=source)


def _validate_continuation(request, selection, previous_run, previous_terminal, *, events=None):
    """Consume retained or durable received evidence, never an unverified session ID."""
    from .contracts import NativeContinuation
    from .receiving import terminal_payload, review_artifact_target
    if previous_run is None and previous_terminal is None:
        expected = _received_continuation_source(request, selection,
            request.native_continuation.prior_evidence_run_id, events=events)
        if request.native_continuation != expected:
            raise RuntimeBindingError("continuation_observed_binding_mismatch")
        return expected
    if type(previous_run) is not RuntimeRun or type(previous_terminal) is not dict:
        raise RuntimeBindingError("received_continuation_predecessor_required")
    prior = previous_run.request
    if (prior.provider != "codex" or prior.result_kind != "task" or prior.role != "consultant"
            or prior.write_workspace is not None or previous_run.observation is None):
        raise RuntimeBindingError("continuation_predecessor_kind_mismatch")
    for name in _CONTINUATION_CONTEXT_FIELDS:
        if getattr(request, name) != getattr(prior, name):
            raise RuntimeBindingError("continuation_scope_changed")
    left, right = selection.to_dict(), previous_run.selection.to_dict()
    left.pop("expected_launch_sha256", None); right.pop("expected_launch_sha256", None)
    if left != right or selection.expected_launch_sha256 is not None:
        raise RuntimeBindingError("continuation_selection_changed")
    if ({request.external_dispatch_id, request.external_evidence_run_id} & {prior.external_dispatch_id, prior.external_evidence_run_id}
            or request.artifact_id == prior.artifact_id):
        raise RuntimeBindingError("continuation_requires_new_operation")
    selected = selected_sdk_execution(prior, previous_run.selection)
    payload = terminal_payload(prior, previous_run.observation, output_context=previous_run.output_context, admitted_sdk_execution=selected)
    result = previous_run.observation.result
    if payload["status"] != "completed" or not result.native_thread_id or not result.native_turn_id:
        raise RuntimeBindingError("continuation_predecessor_not_completed")
    expected = NativeContinuation(prior.external_dispatch_id, prior.external_evidence_run_id,
        selected["requestSha256"], result.native_thread_id, result.native_turn_id)
    if request.native_continuation != expected:
        raise RuntimeBindingError("continuation_observed_binding_mismatch")
    if events is None:
        _writer, _validator, events = _events(previous_run.selection)
    terminals = [e for e in events if e.get("runId") == prior.external_evidence_run_id and e.get("launchRunId") == prior.external_dispatch_id]
    launches = [e for e in events if e.get("runId") == prior.external_dispatch_id and e.get("eventKind") == "launch"]
    if (len(terminals) != 1 or terminals[0] != previous_terminal or len(launches) != 1
            or launches[0].get("sdkExecution") != selected or previous_terminal.get("sdkExecution") != selected
            or previous_terminal.get("status") != "completed" or previous_terminal.get("gate") != "none"):
        raise RuntimeBindingError("continuation_receipt_changed")
    artifact = review_artifact_target(selection.work_item, previous_terminal["artifact"])
    content = (payload["resultText"] + "\n").encode()
    resolved = artifact.resolve(strict=True)
    with artifact.open("rb") as stream:
        identity = os.fstat(stream.fileno())
        observed = stream.read(len(content) + 1)
        current = artifact.stat()
    if (observed != content or artifact.resolve(strict=True) != resolved
            or (identity.st_dev, identity.st_ino) != (current.st_dev, current.st_ino)
            or previous_terminal.get("artifactRevision") != hashlib.sha256(content).hexdigest()
            or previous_terminal.get("artifactSizeBytes") != len(content)):
        raise RuntimeBindingError("continuation_artifact_changed")
    return expected


def prepare_continuation_request(request, selection, previous_run, previous_terminal):
    """Bind a new admitted Consultant task to one actually received native turn."""
    from .contracts import NativeContinuation
    if type(previous_run) is not RuntimeRun or previous_run.observation is None or previous_run.observation.result is None:
        raise RuntimeBindingError("received_continuation_predecessor_required")
    prior, result = previous_run.request, previous_run.observation.result
    bound = replace(request, context_mode="continuation", native_continuation=NativeContinuation(
        prior.external_dispatch_id, prior.external_evidence_run_id,
        request_sha256(prior, previous_run.selection), result.native_thread_id, result.native_turn_id))
    _validate_continuation(bound, selection, previous_run, previous_terminal)
    return bound


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
    previous_run=None, previous_terminal=None,
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
    if request.native_continuation is not None:
        _validate_continuation(request, selection, previous_run, previous_terminal)
    workspace_identity = validate_worker_custody(request, selection)
    if request.provider == "claude":
        if any(not callable(callback) or inspect.iscoroutinefunction(callback)
               for callback in (authorize_tool, verify_account)):
            raise RuntimeBindingError("existing_claude_tool_and_account_owners_required")

    def require_live_request() -> None:
        validate_worker_custody(request, selection, expected_identity=workspace_identity)
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
    admitted = claim_launch(effective, selection, authority=authority, started_at=started_at, previous_run=previous_run, previous_terminal=previous_terminal)
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
                installed_root=Path(selection.installed_hook_root) if selection.installed_hook_root is not None else None,
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
        validate_worker_custody(current, admitted, expected_identity=workspace_identity)
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

    _operation_request_type = ExecutionRequest

    def __init__(
        self, *, request_id: str, authority: Any, selection: Any, process_owner: Any,
        source_environment: dict[str, str], artifact: str, deadline_monotonic: float,
        cancellation_probe: Callable[[], bool], started_at: str,
        authorize_tool: Callable[[ExecutionRequest, str, dict[str, Any]], None] | None = None,
        verify_account: Callable[[ExecutionRequest, dict[str, Any]], str] | None = None,
        previous_run=None, previous_terminal=None,
    ) -> None:
        if not isinstance(request_id, str) or not request_id or any(
            not callable(getattr(authority, name, None)) or inspect.iscoroutinefunction(getattr(authority, name, None))
            for name in ("resolve", "assert_current")
        ):
            raise RuntimeBindingError("existing_request_authority_owner_required")
        if type(source_environment) is not dict or not callable(cancellation_probe):
            raise RuntimeBindingError("explicit_environment_and_cancellation_probe_required")
        self._previous_run, self._previous_terminal = previous_run, previous_terminal
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
        if type(request) is not self._operation_request_type:
            raise RuntimeBindingError("executor_operation_kind_mismatch")
        validate_admitted_request(request, self._selection)
        if request.native_continuation is not None:
            _validate_continuation(request, self._selection, self._previous_run, self._previous_terminal)
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
            **({"previous_run": self._previous_run, "previous_terminal": self._previous_terminal} if request.native_continuation is not None else {}),
        )
        self.runtime_run = run  # Retain before receiving can fail.
        if run.observation is None:
            if run.terminal is None or run.terminal.get("status") != "blocked":
                raise RuntimeBindingError("runtime_result_unavailable")
            self.terminal = run.terminal
            result_type = CoordinationInferenceResult if type(request) is CoordinationInferenceRequest else ExecutionResult
            result = result_type(request=request, status="incomplete", execution_error=run.launch_error or "preworker_failure")
        else:
            from datetime import datetime, timezone
            from .receiving import receive_runtime_run
            updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            terminal = receive_runtime_run(run, artifact=self._artifact, started_at=self._started_at, updated_at=updated_at)
            self.terminal = terminal
            result = run.observation.result
            result_type = CoordinationInferenceResult if type(request) is CoordinationInferenceRequest else ExecutionResult
            if not isinstance(result, result_type) or result.request != request:
                raise RuntimeBindingError("runtime_result_unavailable")
            if terminal.get("status") == "blocked" and result.status == "completed":
                result = replace(result, status="incomplete", execution_error="received_execution_incomplete")
        # Scan the exact final tool-visible projection, including usage and the
        # no-worker error path. Raw evidence stays retained for reconciliation;
        # rejected content must never become coordinator output.
        from .receiving import scan_execution_output
        scan_execution_output(result, run.output_context)
        # Receiving preserves historical execution evidence, not permission to
        # apply it now. Reconsult the existing owner before exposing the result.
        # On denial the retained run/terminal stay intact; no automatic replay.
        self._current(request, "executor_result")
        self.execution_result = result
        return result

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Preserve the existing review Executor protocol, including its result type."""
        if type(request) is not ExecutionRequest:
            raise RuntimeBindingError("review_request_required")
        result = await self._execute_operation(request)
        if not isinstance(result, ExecutionResult):
            raise RuntimeBindingError("review_result_required")
        return result

    async def _execute_operation(self, request):
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


class SdkCoordinationWorker(SdkReviewExecutor):
    """Same concrete execution/receiving owner; return only persisted outer evidence."""
    _operation_request_type = CoordinationInferenceRequest

    async def __call__(self, request):
        if type(request) is not CoordinationInferenceRequest:
            raise RuntimeBindingError("coordination_request_required")
        result = await self._execute_operation(request)
        # Draining retains acquired evidence; it must not turn caller cancellation
        # into authority to dispatch the inner operation.
        if self._cancelled():
            raise asyncio.CancelledError()
        if (type(result) is not CoordinationInferenceResult or result.status != "completed"
            or self.runtime_run is None or self.runtime_run.observation is None
            or self.terminal is None or self.terminal.get("status") != "completed"
            or self.terminal.get("gate") != "none" or self.terminal.get("executionRole") != "main"
            or self.terminal.get("authorizing") is not False or self.terminal.get("closesRunIds") != []):
            raise RuntimeBindingError("coordination_receiving_unverified")
        return self.runtime_run.observation


@dataclass(frozen=True, slots=True)
class ChildLeadAssignment:
    """Root-published scoped task authority, not a model-generated grant."""
    child_id: str
    coordinator_binding: str
    child_work_item: str
    scope: tuple[str, ...]
    catalog: tuple[tuple[str, str], ...]
    required_request_ids: tuple[str, ...]
    lifecycle_permissions: tuple[str, ...]
    task_depth: int
    parent_child_id: str | None
    max_task_depth: int | None
    assignment_sha256: str
    decision_runtime_sha256: str
    decision_session_mode: str = "fresh-handoff"
    goal: str | None = None
    context: str | None = None

    @property
    def request_ids(self):
        return tuple(row[0] for row in self.catalog)


def _child_assignment_document(assignment):
    return {"schemaVersion": 1, **({"goal":assignment.goal,"context":assignment.context} if assignment.goal is not None else {}), **{name:getattr(assignment,name) for name in (
        "child_id", "coordinator_binding", "child_work_item", "scope", "catalog",
        "required_request_ids", "lifecycle_permissions", "task_depth", "parent_child_id", "max_task_depth", "decision_runtime_sha256", "decision_session_mode")}}


def _child_record(writer, validator, selection, *, run_id, artifact, content, scope, cancelled=False, instant):
    argv=["--work-item",selection.work_item,"append","--run-id",run_id,"--role","lead","--execution-role","main",
          "--status","completed","--gate","none","--event-kind","standalone",
          "--artifact",artifact,"--artifact-revision",hashlib.sha256(content).hexdigest(),
          "--artifact-size-bytes",str(len(content)),"--scope="+scope,
          "--evidence","command:Host scoped child-Lead revocation" if cancelled else "command:Root admitted scoped child-Lead assignment",
          "--started-at",instant,"--updated-at",instant]
    return writer.build_event(writer.build_parser().parse_args(argv),validator)


def _load_child_assignment(selection, child_id, *, events=None, seen=(), allow_cancelled=False):
    from .contracts import strict_json
    from .receiving import review_artifact_target
    if type(child_id) is not str or not child_id:
        raise RuntimeBindingError('child_assignment_invalid')
    if child_id in seen:
        raise RuntimeBindingError("child_assignment_cycle")
    if events is None:
        _,_,events=_events(selection)
    rows=[row for row in events if row.get("runId")==child_id]
    if len(rows)!=1:
        raise RuntimeBindingError("child_assignment_unavailable")
    row=rows[0]
    if any(row.get(k)!=v for k,v in {"role":"lead","eventKind":"standalone","status":"completed","gate":"none"}.items()):
        raise RuntimeBindingError("child_assignment_not_root_grant")
    size=row.get("artifactSizeBytes")
    if type(size) is not int or size<=0 or not _sha256(row.get("artifactRevision")):
        raise RuntimeBindingError("child_assignment_receipt_invalid")
    path=review_artifact_target(selection.work_item,row.get("artifact",""))
    with path.open('rb') as stream:
        before=os.fstat(stream.fileno())
        if before.st_size!=size:raise RuntimeBindingError("child_assignment_changed")
        raw=stream.read(size+1)
    after=path.stat()
    if len(raw)!=size or (before.st_dev,before.st_ino)!=(after.st_dev,after.st_ino) or hashlib.sha256(raw).hexdigest()!=row['artifactRevision']:
        raise RuntimeBindingError("child_assignment_changed")
    doc=strict_json(raw.decode(),max_bytes=size)
    expected={"schemaVersion","child_id","coordinator_binding","child_work_item","scope","catalog","required_request_ids","lifecycle_permissions","task_depth","parent_child_id","max_task_depth","decision_runtime_sha256"}
    if type(doc) is dict and "decision_session_mode" in doc:
        expected.add("decision_session_mode")
    if type(doc) is dict and "goal" in doc:expected.update({"goal","context"})
    if type(doc) is not dict or set(doc)!=expected or type(doc['schemaVersion']) is not int or doc['schemaVersion']!=1 or doc['child_id']!=child_id:
        raise RuntimeBindingError("child_assignment_invalid")
    if (any(type(doc[n]) is not str or not doc[n].strip() for n in ('child_id','coordinator_binding','child_work_item'))
        or not Path(doc['child_work_item']).is_absolute()
        or any(type(doc[n]) is not list for n in ('scope','catalog','required_request_ids','lifecycle_permissions'))
        or any(type(x) is not str or not x for n in ('scope','required_request_ids','lifecycle_permissions') for x in doc[n])
        or any(type(x) is not list or len(x)!=2 or type(x[0]) is not str or not x[0] or not _sha256(x[1]) for x in doc['catalog'])):
        raise RuntimeBindingError("child_assignment_invalid")
    if doc.get('decision_session_mode','fresh-handoff') not in {'fresh-handoff','native-persistent'}:raise RuntimeBindingError('child_session_mode_invalid')
    if not _sha256(doc['decision_runtime_sha256']):raise RuntimeBindingError('child_decision_runtime_invalid')
    if 'goal' in doc and (type(doc['goal']) is not str or not doc['goal'].strip()
        or (doc['context'] is not None and type(doc['context']) is not str)):
        raise RuntimeBindingError('child_goal_invalid')
    ids=[x[0] for x in doc['catalog']]
    if ((not ids and (not doc.get('goal') or not doc['scope'])) or len(set(ids))!=len(ids) or not set(doc['required_request_ids'])<=set(ids)
        or not set(doc['lifecycle_permissions'])<={'delegate','finish','cancel','delegate-child'}
        or type(doc['task_depth']) is not int or doc['task_depth']<1
        or (doc['max_task_depth'] is not None and (type(doc['max_task_depth']) is not int or doc['max_task_depth']<doc['task_depth']))):
        raise RuntimeBindingError("child_assignment_invalid")
    parent_id=doc['parent_child_id']
    if parent_id is None:
        if doc['task_depth']!=1:raise RuntimeBindingError("child_depth_not_derived")
    else:
        parent=_load_child_assignment(selection,parent_id,events=events,seen=(*seen,child_id),allow_cancelled=allow_cancelled)
        if ('delegate-child' not in parent.lifecycle_permissions or doc['task_depth']!=parent.task_depth+1
            or not set(doc['scope'])<=set(parent.scope)
            or (parent.max_task_depth is not None and (doc['max_task_depth'] is None or doc['max_task_depth']>parent.max_task_depth))):
            raise RuntimeBindingError("child_parent_scope_changed")
    if not allow_cancelled and any(e.get('runId')==child_id+'-cancel' for e in events):
        raise RuntimeBindingError("child_assignment_cancelled")
    return ChildLeadAssignment(child_id,doc['coordinator_binding'],doc['child_work_item'],tuple(doc['scope']),
        tuple(tuple(x) for x in doc['catalog']),tuple(doc['required_request_ids']),tuple(doc['lifecycle_permissions']),
        doc['task_depth'],parent_id,doc['max_task_depth'],row['artifactRevision'],doc['decision_runtime_sha256'],doc.get('decision_session_mode','fresh-handoff'),doc.get('goal'),doc.get('context'))


def publish_child_assignment(*, root_selection, root_authority, selections, child_id, coordinator_binding,
        scope, required_request_ids, lifecycle_permissions, artifact, started_at, parent_child_id=None, max_task_depth=None, decision_selection=None, decision_session_mode="fresh-handoff", child_work_item=None, goal=None, context=None):
    """Root publishes scope and goal, optionally with an initial admitted catalog."""
    from .receiving import review_artifact_target
    if not isinstance(selections,Mapping) or not isinstance(child_id,str) or not child_id:
        raise RuntimeBindingError("child_catalog_invalid")
    if (goal is not None and (type(goal) is not str or not goal.strip())) or (context is not None and (goal is None or type(context) is not str)):
        raise RuntimeBindingError("child_goal_invalid")
    if not selections and (child_work_item is None or goal is None or not scope):
        raise RuntimeBindingError("empty_child_goal_and_work_item_required")
    catalog=[];child_item=None
    if child_work_item is not None:
        explicit_child=Path(child_work_item)
        if not explicit_child.is_absolute():raise RuntimeBindingError("child_work_item_absolute_required")
        child_item=str(explicit_child.resolve(strict=True))
    for request_id,selection in selections.items():
        request=root_authority.resolve(request_id)
        validate_admitted_request(request,selection)
        _require_authority(root_authority.assert_current,request,'child_assignment')
        if (request.coordinator_binding!=coordinator_binding or not set(request.scope)<=set(scope)
            or (child_item is not None and selection.work_item!=child_item)):
            raise RuntimeBindingError("child_catalog_scope_mismatch")
        child_item=selection.work_item
        catalog.append((request_id,request_sha256(request,selection)))
    root=Path(root_selection.work_item).resolve(strict=True);child=Path(child_item).resolve(strict=True)
    if root==child or root.is_relative_to(child) or child.is_relative_to(root):
        raise RuntimeBindingError("child_work_item_requires_separate_scope")
    writer,validator,budget=_ledger(root_selection)
    # Parent lineage is read from root-owned evidence, never a supplied depth.
    parent=_load_child_assignment(root_selection,parent_child_id) if parent_child_id is not None else None
    depth=1 if parent is None else parent.task_depth+1
    if parent is not None and max_task_depth is None:max_task_depth=parent.max_task_depth
    if decision_selection is None:
        decision_selection=replace(root_selection,work_item=str(child),expected_launch_sha256=None,config_overrides=CODEX_BOUNDED_REVIEW_OVERRIDES)
    if (type(decision_selection) is not CodexRuntimeSelection or decision_selection.work_item!=str(child)
        or decision_selection.expected_launch_sha256 is not None or decision_selection.config_overrides!=CODEX_BOUNDED_REVIEW_OVERRIDES):
        raise RuntimeBindingError('child_decision_runtime_invalid')
    decision_digest=hashlib.sha256(json_text(decision_selection.to_dict()).encode()).hexdigest()
    value=ChildLeadAssignment(child_id,coordinator_binding,str(child),tuple(scope),tuple(catalog),tuple(required_request_ids),
        tuple(lifecycle_permissions),depth,parent_child_id,max_task_depth,'',decision_digest,decision_session_mode,goal,context)
    content=(json_text(_child_assignment_document(value))+'\n').encode()
    target=review_artifact_target(root_selection.work_item,artifact,must_be_new=True)
    with _owner().TerminalReceiptV1.reserve(target) as receipt:receipt.commit(content)
    marker='child-lead:'+str(child)
    event=_child_record(writer,validator,root_selection,run_id=child_id,artifact=artifact,content=content,scope=marker,instant=started_at)
    def append(previous):
        errors=[];events=validator.load_jsonl(root/'agent-runs.jsonl',errors,source_bytes=previous.encode(),ledger_resource_budget=budget) if previous else []
        if errors or any(e.get('runId')==child_id or e.get('scope')==[marker] for e in events):
            raise RuntimeBindingError("child_scope_already_assigned")
        # Validate the complete prospective grant and parent under the same lock.
        _load_child_assignment(root_selection,child_id,events=[*events,event])
        for request_id in selections:
            _require_authority(root_authority.assert_current,root_authority.resolve(request_id),'child_assignment_commit')
        return event
    writer._append_event_transaction(root,validator,append,ledger_resource_budget=budget)
    return _load_child_assignment(root_selection,child_id)


def _child_artifact_document(selection,row):
    from .contracts import strict_json
    from .receiving import review_artifact_target
    size=row.get("artifactSizeBytes")
    if type(size) is not int or size<=0 or not _sha256(row.get("artifactRevision")):
        raise RuntimeBindingError("child_receipt_invalid")
    path=review_artifact_target(selection.work_item,row.get("artifact",""))
    with path.open("rb") as stream:
        before=os.fstat(stream.fileno())
        if before.st_size!=size:raise RuntimeBindingError("child_receipt_changed")
        raw=stream.read(size+1)
    after=path.stat()
    if len(raw)!=size or (before.st_dev,before.st_ino)!=(after.st_dev,after.st_ino) or hashlib.sha256(raw).hexdigest()!=row["artifactRevision"]:
        raise RuntimeBindingError("child_receipt_changed")
    return strict_json(raw.decode(),max_bytes=size)


def _decode_child_registration(value,digest):
    if type(value) is not dict or set(value)!={"schemaVersion","request","selection"} or type(value["schemaVersion"]) is not int or value["schemaVersion"]!=1:
        raise RuntimeBindingError("child_registration_invalid")
    request=ExecutionRequest.from_dict(value["request"])
    selection=runtime_selection_from_dict(request.provider,value["selection"])
    if selection.expected_launch_sha256 is not None or request_sha256(request,selection)!=digest:
        raise RuntimeBindingError("child_registration_changed")
    return request,selection


def _child_admission_document(authority,assignment,proposal_id):
    identity=hashlib.sha256(json_text([assignment.assignment_sha256,proposal_id]).encode()).hexdigest()
    rows=[row for row in _events(authority._root_selection)[2] if row.get("runId")=="child-admission-"+identity]
    if len(rows)!=1:raise RuntimeBindingError("child_registration_not_received")
    return _child_artifact_document(authority._root_selection,rows[0])


def publish_child_task_admission(*,authority,proposal_id,accepted,artifact,started_at,
        request_id=None,selection=None,required=True,registration=None):
    """Trusted Root publishes its concrete admission, not a model permission."""
    from .receiving import review_artifact_target
    if type(authority) is not ChildLeadAuthority or type(accepted) is not bool or type(required) is not bool:
        raise RuntimeBindingError("child_task_admission_invalid")
    assignment=authority.resolve_child(authority._child_id)
    authority.assert_child_current(assignment,"child_task_admission")
    proposal=authority.proposal_results(assignment).get(proposal_id)
    if proposal is None:raise RuntimeBindingError("child_proposal_unavailable")
    digest=None
    if accepted:
        if type(request_id) is not str or not request_id:raise RuntimeBindingError("child_task_admission_invalid")
        request=authority._root_authority.resolve(request_id)
        validate_admitted_request(request,selection)
        _require_authority(authority._root_authority.assert_current,request,"child_task_admission")
        if (selection.work_item!=assignment.child_work_item or request.coordinator_binding!=assignment.coordinator_binding
            or not set(request.scope)<=set(assignment.scope) or not set(request.scope)<=set(proposal["proposal"]["scope"])):
            raise RuntimeBindingError("child_task_scope_mismatch")
        digest=request_sha256(request,selection)
        if request_id in dict(assignment.catalog):raise RuntimeBindingError("child_task_already_assigned")
    elif request_id is not None or selection is not None:
        raise RuntimeBindingError("child_rejection_has_request")
    doc={"schemaVersion":1,"assignment_sha256":assignment.assignment_sha256,"proposal_id":proposal_id,
        "proposal_sha256":hashlib.sha256(json_text(proposal["proposal"]).encode()).hexdigest(),
        "source_evidence_id":proposal["source_evidence_id"],"status":"accepted" if accepted else "rejected",
        "request_id":request_id,"request_sha256":digest,"required":required if accepted else False}
    if registration is not None:
        if not accepted:raise RuntimeBindingError("child_registration_requires_acceptance")
        if type(authority._root_authority) is not RootTaskRegistry or authority._root_authority._scan(request,selection)!=registration:
            raise RuntimeBindingError("child_registry_owner_mismatch")
        registered_request,registered_selection=_decode_child_registration(registration,digest)
        if registered_request!=request or registered_selection!=selection:raise RuntimeBindingError("child_registration_changed")
        doc["registration"]=registration
    if proposal["status"]!="pending":
        if _child_admission_document(authority,assignment,proposal_id)!=doc:raise RuntimeBindingError("child_proposal_already_decided")
        return proposal
    root_selection=authority._root_selection
    content=(json_text(doc)+"\n").encode()
    target=review_artifact_target(root_selection.work_item,artifact)
    if not os.path.lexists(target):
        with _owner().TerminalReceiptV1.reserve(target) as receipt:receipt.commit(content)
    # Reconcile only exact currently admitted bytes; never overwrite an orphan.
    expected_artifact={"artifact":artifact,"artifactSizeBytes":len(content),"artifactRevision":hashlib.sha256(content).hexdigest()}
    if _child_artifact_document(root_selection,expected_artifact)!=doc:raise RuntimeBindingError("child_admission_artifact_changed")
    writer,validator,budget=_ledger(root_selection)
    identity=hashlib.sha256(json_text([assignment.assignment_sha256,proposal_id]).encode()).hexdigest()
    event=_child_record(writer,validator,root_selection,run_id="child-admission-"+identity,
        artifact=artifact,content=content,scope="child-task-admission:"+assignment.assignment_sha256,instant=started_at)
    def append(previous):
        errors=[];rows=validator.load_jsonl(Path(root_selection.work_item)/"agent-runs.jsonl",errors,source_bytes=previous.encode(),ledger_resource_budget=budget)
        if errors:raise RuntimeBindingError("child_ledger_invalid")
        _load_child_assignment(root_selection,assignment.child_id,events=rows)
        if _child_artifact_document(root_selection,expected_artifact)!=doc:raise RuntimeBindingError("child_admission_artifact_changed")
        prior=authority._proposal_results(assignment,root_events=rows).get(proposal_id)
        if prior is None or prior["status"]!="pending" or prior["proposal"]!=proposal["proposal"]:
            raise RuntimeBindingError("child_proposal_already_decided")
        if accepted:
            current=authority._root_authority.resolve(request_id)
            if request_sha256(current,selection)!=digest:raise RuntimeBindingError("child_task_admission_changed")
            _require_authority(authority._root_authority.assert_current,current,"child_task_admission_commit")
            if any(v["status"]=="accepted" and v["request_id"]==request_id for v in authority._proposal_results(assignment,root_events=rows).values()):
                raise RuntimeBindingError("child_task_already_assigned")
        return event
    try:
        writer._append_event_transaction(Path(root_selection.work_item),validator,append,ledger_resource_budget=budget)
    except Exception:
        # A lost acknowledgement is not a second admission. Read canonical outcome.
        current=authority.proposal_results(assignment).get(proposal_id)
        if current is None or current["status"]=="pending" or _child_admission_document(authority,assignment,proposal_id)!=doc:raise
        return current
    return authority.proposal_results(assignment)[proposal_id]


class RootTaskRegistry:
    """Exact explicit Root decisions; live permission remains with the Host owner."""
    def __init__(self,*,root_authority,root_selection,source_environment):
        self._root_authority=root_authority;self._root_selection=root_selection
        self._environment=dict(source_environment);self._entries={};self._prepared={};self._admission_active=set();self._lock=threading.RLock()

    def resolve(self,request_id):
        if request_id in self._entries:return self._entries[request_id][2]
        if request_id in self._prepared:
            if request_id not in self._admission_active:raise RuntimeBindingError("child_registration_not_received")
            return self._prepared[request_id][2]
        return self._root_authority.resolve(request_id)

    def assert_current(self,request,effect):
        entries=[entry for entry in self._entries.values() if entry[2]==request]
        pending=[key for key,entry in self._prepared.items() if entry[2]==request]
        if entries:
            authority,proposal_id,_request,selection=entries[0]
            assignment=_load_child_assignment(self._root_selection,authority._child_id)
            outcome=authority.proposal_results(assignment).get(proposal_id)
            doc=_child_admission_document(authority,assignment,proposal_id)
            if (outcome is None or outcome["status"]!="accepted" or "registration" not in doc
                or _decode_child_registration(doc["registration"],doc["request_sha256"])!=(request,selection)):
                raise RuntimeBindingError("child_registration_changed")
        elif pending and (effect not in {"child_task_admission","child_task_admission_commit"} or not any(key in self._admission_active for key in pending)):
            raise RuntimeBindingError("child_registration_not_received")
        _require_authority(self._root_authority.assert_current,request,effect)

    def _check_owner(self,authority):
        if type(authority) is not ChildLeadAuthority or authority._root_authority is not self or authority._root_selection!=self._root_selection:
            raise RuntimeBindingError("child_registry_owner_mismatch")

    def _scan(self,request,selection):
        _environment,context=prepare_environment(selection,self._environment)
        value={"schemaVersion":1,"request":request.to_dict(),"selection":selection.to_dict()}
        # Root source may legitimately contain machine paths. Reuse only the
        # credential detector, never persist the environment or secret needles.
        failure=_owner().credential_scan_terminal(context.needles,stdout=json_text(value).encode(),stderr=b"")
        if failure is not None:raise RuntimeBindingError(failure)
        return value

    def admit(self,authority,proposal_id,request,selection,*,artifact,started_at,required=True):
        self._check_owner(authority)
        if type(required) is not bool:raise RuntimeBindingError("child_registration_invalid")
        with self._lock:
            assignment=_load_child_assignment(self._root_selection,authority._child_id)
            outcome=authority.proposal_results(assignment).get(proposal_id)
            if outcome is None:raise RuntimeBindingError("child_proposal_unavailable")
            identity=hashlib.sha256(json_text([assignment.assignment_sha256,proposal_id,outcome["source_evidence_id"],outcome["proposal"]]).encode()).hexdigest()
            request_id="root-task-"+identity
            request=replace(request,external_dispatch_id="dispatch-"+identity,external_evidence_run_id="evidence-"+identity)
            if type(request) is not ExecutionRequest or selection.expected_launch_sha256 is not None:
                raise RuntimeBindingError("child_registration_invalid")
            # A committed outcome is read before any new materialization attempt.
            if outcome["status"]!="pending":
                doc=_child_admission_document(authority,assignment,proposal_id)
                if (outcome["status"]!="accepted" or doc["required"]!=required or doc["request_id"]!=request_id or "registration" not in doc
                    or _decode_child_registration(doc["registration"],doc["request_sha256"])!=(request,selection)):
                    raise RuntimeBindingError("child_registration_conflict")
                _require_authority(self._root_authority.assert_current,request,"child_registration_restore")
                self._entries[request_id]=(authority,proposal_id,request,selection)
                return outcome
            validate_admitted_request(request,selection)
            _require_authority(self._root_authority.assert_current,request,"child_registration_admission")
            registration=self._scan(request,selection)
            entry=(authority,proposal_id,request,selection)
            if request_id in self._prepared and self._prepared[request_id][1:]!=entry[1:]:raise RuntimeBindingError("child_registration_conflict")
            self._prepared[request_id]=entry
            self._admission_active.add(request_id)
            try:
                outcome=publish_child_task_admission(authority=authority,proposal_id=proposal_id,accepted=True,
                    request_id=request_id,selection=selection,artifact=artifact,started_at=started_at,required=required,registration=registration)
                self._entries[request_id]=entry
                self._prepared.pop(request_id,None)
                return outcome
            finally:
                self._admission_active.discard(request_id)

    def restore(self,authority):
        self._check_owner(authority)
        assignment=authority.resolve_child(authority._child_id)
        restored={};unavailable={}
        for proposal_id,outcome in authority.proposal_results(assignment).items():
            if outcome["status"]!="accepted":continue
            doc=_child_admission_document(authority,assignment,proposal_id)
            if "registration" not in doc:continue  # Legacy caller-owned requests remain caller-owned.
            request,selection=_decode_child_registration(doc["registration"],doc["request_sha256"])
            request_id=doc["request_id"]
            try:
                _load_child_assignment(self._root_selection,authority._child_id)
                validate_admitted_request(request,selection)
                _require_authority(self._root_authority.assert_current,request,"child_registration_restore")
                self._scan(request,selection)
            except Exception:
                unavailable[request_id]="current_registration_authority_unavailable"
                continue
            self._entries[request_id]=(authority,proposal_id,request,selection)
            restored[request_id]=selection
        return {"selections":restored,"unavailable":unavailable}


class ChildLeadAuthority:
    """Scoped facade over existing Root admission, runtime, ledger and lifecycle."""
    def __init__(self, *, root_authority, root_selection, child_id, selections,
                 closure_data, terminal_instant, repository_root):
        self._root_authority,self._root_selection,self._child_id=root_authority,root_selection,child_id
        self._selections=dict(selections);self._executors=None;self._decision_workers={};self._decision_requests={};self._executor_requests={}
        self._closure_data,self._terminal_instant=closure_data,terminal_instant
        self._repository_root=Path(repository_root).resolve(strict=True)
        self.cancellation_receipts={}
        assignment=self.resolve_child(child_id)
        if not set(assignment.request_ids)<=set(self._selections)<=set(dict(self.child_catalog(assignment))):raise RuntimeBindingError('child_catalog_mismatch')
        lifecycle=_ledger(self._root_selection)[1].load_lifecycle_owner()
        category,slug=lifecycle._canonical_category('work-item:'+Path(assignment.child_work_item).name)
        expected=lifecycle._work_items_root(self._repository_root)/'active'/slug
        if expected.resolve()!=Path(assignment.child_work_item).resolve():
            raise RuntimeBindingError('child_repository_identity_mismatch')

    def _proposal_results(self,assignment,*,root_events=None):
        from .coordination import validate_task_proposal
        result={}
        # Completed received decisions are the pending-data owner in both modes.
        selection=replace(self._root_selection,work_item=assignment.child_work_item)
        _,item=self._actual_item(assignment)
        selection=replace(selection,work_item=str(item))
        if os.path.lexists(item/"agent-runs.jsonl"):
            _,_,events=_events(selection)
            for row in events:
                selected=row.get("sdkExecution",{})
                if (row.get("eventKind")!="terminal" or row.get("status")!="completed"
                    or selected.get("schemaVersion")!=5 or selected.get("operationKind")!="scoped-child-coordination"):
                    continue
                doc=_child_artifact_document(selection,row)
                binding=doc.get("child_proposal")
                if binding is None:continue
                if type(binding) is not dict or set(binding)!={"assignment_sha256","proposal"}:
                    raise RuntimeBindingError("child_proposal_receipt_invalid")
                if binding["assignment_sha256"]!=assignment.assignment_sha256:continue
                proposal=validate_task_proposal(binding["proposal"])
                intent=doc.get("evidence",{}).get("intent",{})
                launches=[e for e in events if e.get("runId")==row.get("launchRunId")]
                if (len(launches)!=1 or launches[0].get("sdkExecution")!=selected
                    or row.get("executionRole")!="main" or row.get("assignedRole")!="lead" or row.get("gate")!="none"
                    or row.get("authorizing") is not False or row.get("closesRunIds")!=[]
                    or intent.get("action")!="propose" or intent.get("proposal")!=proposal
                    or intent.get("child_choice_sha256")!=selected.get("childChoiceSha256")):
                    raise RuntimeBindingError("child_proposal_receipt_invalid")
                key=proposal["proposal_id"]
                if key in result:
                    # The first canonical append owns the identity. Later model
                    # data cannot replace it or veto unrelated admitted work.
                    if result[key]["proposal"]!=proposal:
                        result[key].setdefault("rejected_duplicates",[]).append({"source_evidence_id":row["runId"],
                            "proposal_sha256":hashlib.sha256(json_text(proposal).encode()).hexdigest(),"reason":"proposal_identity_reused"})
                    continue
                result[key]={"proposal":proposal,"status":"pending","request_id":None,"required":False,
                    "source_evidence_id":row["runId"],"admission":None}
        if root_events is None:root_events=_events(self._root_selection)[2]
        for row in root_events:
            if row.get("scope")!=["child-task-admission:"+assignment.assignment_sha256]:continue
            doc=_child_artifact_document(self._root_selection,row)
            fields={"schemaVersion","assignment_sha256","proposal_id","proposal_sha256","source_evidence_id","status","request_id","request_sha256","required"}
            if type(doc) is dict and "registration" in doc:fields.add("registration")
            if (type(doc) is not dict or set(doc)!=fields or type(doc["schemaVersion"]) is not int or doc["schemaVersion"]!=1
                or doc["assignment_sha256"]!=assignment.assignment_sha256 or type(doc["proposal_id"]) is not str
                or type(doc["status"]) is not str or doc["status"] not in {"accepted","rejected"}
                or type(doc["required"]) is not bool
                or any(row.get(k)!=v for k,v in {"role":"lead","eventKind":"standalone","status":"completed","gate":"none"}.items())):
                raise RuntimeBindingError("child_task_admission_invalid")
            prior=result.get(doc["proposal_id"])
            if (prior is None or prior["status"]!="pending" or doc["source_evidence_id"]!=prior["source_evidence_id"]
                or doc["proposal_sha256"]!=hashlib.sha256(json_text(prior["proposal"]).encode()).hexdigest()):
                raise RuntimeBindingError("child_task_admission_unbound")
            if doc["status"]=="accepted":
                if type(doc["request_id"]) is not str or not doc["request_id"] or not _sha256(doc["request_sha256"]):
                    raise RuntimeBindingError("child_task_admission_invalid")
            elif doc["request_id"] is not None or doc["request_sha256"] is not None or doc["required"]:
                raise RuntimeBindingError("child_task_admission_invalid")
            if "registration" in doc:
                if doc["status"]!="accepted":raise RuntimeBindingError("child_registration_requires_acceptance")
                _decode_child_registration(doc["registration"],doc["request_sha256"])
            public_doc={key:value for key,value in doc.items() if key!="registration"}
            result[doc["proposal_id"]]={**prior,"status":doc["status"],"request_id":doc["request_id"],"required":doc["required"],"admission":public_doc}
        return result

    def proposal_results(self,assignment):
        if assignment!=self.resolve_child(assignment.child_id):raise RuntimeBindingError("child_assignment_changed")
        return self._proposal_results(assignment)

    def child_catalog(self,assignment):
        rows=list(assignment.catalog)
        rows.extend((v["request_id"],v["admission"]["request_sha256"]) for v in self.proposal_results(assignment).values() if v["status"]=="accepted")
        if len({r[0] for r in rows})!=len(rows):raise RuntimeBindingError("child_task_identity_reused")
        return tuple(rows)

    def child_bound_request_ids(self,assignment):
        # Availability is not permission: the full canonical catalog stays required.
        return tuple(key for key,_digest in self.child_catalog(assignment) if key in self._selections)

    def child_required_request_ids(self,assignment):
        return (*assignment.required_request_ids,*(v["request_id"] for v in self.proposal_results(assignment).values() if v["status"]=="accepted" and v["required"]))

    def submit_child_proposal(self,assignment,worker,proposal):
        # Receiving already durably recorded this data; no second pending store.
        self.assert_child_current(assignment,"child_proposal")
        found=self.proposal_results(assignment).get(proposal["proposal_id"])
        if found is None:raise RuntimeBindingError("child_proposal_not_received")
        if found["proposal"]!=proposal and not any(row["proposal_sha256"]==hashlib.sha256(json_text(proposal).encode()).hexdigest()
                for row in found.get("rejected_duplicates",[])):
            raise RuntimeBindingError("child_proposal_not_received")
        return found

    def resolve_child(self,child_id):
        if child_id!=self._child_id:raise RuntimeBindingError('another_child_assignment')
        return _load_child_assignment(self._root_selection,child_id,allow_cancelled=True)

    def _actual_item(self,assignment):
        lifecycle=_ledger(self._root_selection)[1].load_lifecycle_owner()
        item=lifecycle.resolve_category(self._repository_root,'work-item:'+Path(assignment.child_work_item).name)
        return lifecycle,Path(item)

    def assert_child_current(self,assignment,effect):
        if assignment!=_load_child_assignment(self._root_selection,assignment.child_id):raise RuntimeBindingError('child_assignment_changed')
        _,item=self._actual_item(assignment)
        if effect not in {'finish','recovery','result'} and item.resolve()!=Path(assignment.child_work_item).resolve():
            raise RuntimeBindingError('child_work_item_not_active')
        catalog=dict(self.child_catalog(assignment))
        for request_id in self._selections:
            request=self._root_authority.resolve(request_id)
            selection=self._selections[request_id]
            if (selection.work_item!=assignment.child_work_item or request.coordinator_binding!=assignment.coordinator_binding
                or not set(request.scope)<=set(assignment.scope)
                or request_sha256(request,selection)!=catalog[request_id]):
                raise RuntimeBindingError('child_catalog_changed')
            _require_authority(self._root_authority.assert_current,request,effect)

    def resolve(self,request_id):
        assignment=_load_child_assignment(self._root_selection,self._child_id)
        if request_id in self._decision_workers:
            current=self._root_authority.resolve(request_id)
            if current!=self._decision_requests[request_id]:raise RuntimeBindingError('child_decision_changed')
            return current
        catalog=dict(self.child_catalog(assignment))
        if request_id not in catalog:raise RuntimeBindingError('unassigned_child_request')
        if request_id not in self._selections:raise RuntimeBindingError('child_catalog_refresh_required')
        request=self._root_authority.resolve(request_id)
        if request_sha256(request,self._selections[request_id])!=catalog[request_id]:
            raise RuntimeBindingError('child_catalog_changed')
        return request

    def assert_current(self,request,effect):
        assignment=self.resolve_child(self._child_id)
        self.assert_child_current(assignment,effect)
        if type(request) is CoordinationInferenceRequest:
            admitted=any(self.resolve(i)==request for i in self._decision_workers)
            _require_authority(self._root_authority.assert_current,request,effect)
            if effect=="sdk_launch_commit" and request.decision_session_mode=="native-persistent":
                worker=next(w for key,w in self._decision_workers.items() if self._decision_requests[key]==request)
                tip=self._persistent_decision_tip(assignment,request,worker._selection)
                if tip is not None:
                    source,document,_terminal=tip
                    if request.native_continuation!=source:raise RuntimeBindingError("child_native_tip_changed")
                    intent=document["evidence"]["intent"]
                    if intent["action"]=="propose":
                        if intent["proposal"]["proposal_id"] not in self.proposal_results(assignment):raise RuntimeBindingError("child_received_intent_pending")
                    elif intent["action"]!="execute" or intent["request_id"] not in self.attempted_requests(assignment):
                        raise RuntimeBindingError("child_received_intent_pending")
        else:
            admitted=any(self.resolve(i)==request for i in self._selections)
        if 'delegate' not in assignment.lifecycle_permissions or not admitted:
            raise RuntimeBindingError('child_delegation_not_admitted')

    def attach_executors(self,executors):
        if self._executors is not None:raise RuntimeBindingError('child_executors_already_bound')
        assignment=self.resolve_child(self._child_id)
        if set(executors)!=set(self._selections):raise RuntimeBindingError('child_executor_catalog_mismatch')
        for key,value in executors.items():
            if type(value) is not SdkReviewExecutor or value._authority is not self or value._selection!=self._selections[key] or value._request_id!=key:
                raise RuntimeBindingError('child_executor_authority_mismatch')
        self._executor_requests={key:self.resolve(key) for key in executors}
        self._executors=dict(executors)

    def completed_requests(self,assignment):
        self.assert_child_current(assignment,'recovery')
        _,item=self._actual_item(assignment);result={}
        for key,selection in self._selections.items():
            if not os.path.lexists(item/'agent-runs.jsonl'):continue
            _,_,events=_events(replace(selection,work_item=str(item)))
            request=self.resolve(key)
            selected=selected_sdk_execution(request,selection)
            launches=[e for e in events if e.get('runId')==request.external_dispatch_id]
            terminals=[e for e in events if e.get('runId')==request.external_evidence_run_id]
            if len(launches)==1 and len(terminals)==1:
                expected={'workItem':request.work_item_id,'provider':request.provider,'model':request.model,
                    'effort':request.effort,'scope':list(request.scope),'assignedRole':request.role,
                    'executionRole':execution_role(request),'artifactIdentity':request.artifact_id,
                    'externalDispatchId':request.external_dispatch_id,'externalEvidenceRunId':request.external_evidence_run_id,
                    'actualExecutionPath':'direct-external-sdk','sdkExecution':selected}
                if any(row.get(k)!=v for row in (launches[0],terminals[0]) for k,v in expected.items()):
                    raise RuntimeBindingError('child_result_binding_changed')
                terminal=terminals[0]
                if terminal.get('authorizing') is not False or terminal.get('closesRunIds')!=[]:
                    raise RuntimeBindingError('child_result_authority_changed')
                if (terminal.get('eventKind')=='terminal' and terminal.get('launchRunId')==launches[0]['runId']
                    and terminal.get('status')=='completed' and terminal.get('gate') in {'none','PASS'}
                    and terminal.get('sdkExecution')==selected and launches[0].get('sdkExecution')==selected):result[key]=terminal
        return result

    def received_context(self,assignment):
        from .contracts import strict_json
        from .receiving import review_artifact_target
        _,item=self._actual_item(assignment);result={}
        for key,row in self.completed_requests(assignment).items():
            path=review_artifact_target(item,row['artifact']);size=row['artifactSizeBytes']
            with path.open('rb') as stream:
                st=os.fstat(stream.fileno())
                if st.st_size!=size:raise RuntimeBindingError('child_result_artifact_changed')
                raw=stream.read(size+1)
            after=path.stat()
            if (st.st_dev,st.st_ino)!=(after.st_dev,after.st_ino) or len(raw)!=size or hashlib.sha256(raw).hexdigest()!=row['artifactRevision']:
                raise RuntimeBindingError('child_result_artifact_changed')
            result[key]={'terminal':row,'artifact':strict_json(raw.decode(),max_bytes=size)}
        return result

    def _persistent_decision_tip(self,assignment,request,selection):
        """Follow the unique received native chain, never a timestamp or a seal clone."""
        if not os.path.lexists(Path(selection.work_item)/'agent-runs.jsonl'):return None
        _,_,events=_events(selection)
        launches=[row for row in events if row.get('eventKind')=='launch'
            and row.get('sdkExecution',{}).get('childAssignmentSha256')==assignment.assignment_sha256]
        if not launches:return None
        first=[row for row in launches if 'continuationSourceSha256' not in row['sdkExecution']]
        if len(first)!=1:raise RuntimeBindingError('child_native_chain_invalid')
        current=first[0];visited=set()
        while True:
            if current['runId'] in visited:raise RuntimeBindingError('child_native_chain_invalid')
            visited.add(current['runId'])
            source,_depth,document,terminal=_received_native_context(request,selection,current['externalEvidenceRunId'],events=events,with_document=True)
            next_rows=[row for row in launches if row['sdkExecution'].get('continuationSourceSha256')==source.source_sha256]
            if not next_rows:
                if len(visited)!=len(launches):raise RuntimeBindingError('child_native_chain_invalid')
                return source,document,terminal
            if len(next_rows)!=1:raise RuntimeBindingError('child_native_chain_invalid')
            current=next_rows[0]

    def prepare_child_decision(self,assignment,request,selection):
        """Bind a new Host-admitted turn to received context without starting it."""
        self.assert_child_current(assignment,'child_decision_prepare')
        if request.decision_session_mode!=assignment.decision_session_mode:
            raise RuntimeBindingError('child_session_mode_changed')
        projection=json.loads(request.child_choice_json)
        if projection.get("goal")!=assignment.goal or projection.get("context")!=assignment.context:
            raise RuntimeBindingError("child_goal_changed")
        if projection["assignment_sha256"]!=assignment.assignment_sha256:
            raise RuntimeBindingError("child_decision_assignment_changed")
        if hashlib.sha256(json_text(selection.to_dict()).encode()).hexdigest()!=assignment.decision_runtime_sha256:
            raise RuntimeBindingError('child_decision_runtime_not_admitted')
        if assignment.decision_session_mode=='fresh-handoff':return request
        tip=self._persistent_decision_tip(assignment,request,selection)
        if tip is None:
            if request.native_continuation is not None:raise RuntimeBindingError('child_native_source_unavailable')
            return request
        return replace(request,context_mode='continuation',native_continuation=tip[0])

    def recover_child_decision(self,assignment,worker,projection):
        """Return only a current canonical pending intent, never a native observation."""
        if assignment.decision_session_mode!='native-persistent':return None
        if type(worker) is not SdkCoordinationWorker or worker._authority is not self:
            raise RuntimeBindingError('child_decision_authority_mismatch')
        request=self._root_authority.resolve(worker._request_id)
        self.validate_decision(assignment,request,projection)
        if hashlib.sha256(json_text(worker._selection.to_dict()).encode()).hexdigest()!=assignment.decision_runtime_sha256:
            raise RuntimeBindingError('child_decision_runtime_not_admitted')
        tip=self._persistent_decision_tip(assignment,request,worker._selection)
        if tip is None:return None
        source,document,terminal=tip
        if request.native_continuation!=source:raise RuntimeBindingError('child_native_tip_changed')
        from .coordination import child_choice_sha256
        evidence=document['evidence'];intent=evidence['intent']
        if (type(intent) is not dict or set(intent)-{'proposal'}!={'operation_id','child_choice_sha256','action','request_id'}
            or intent['operation_id']!=evidence.get('operation_id')
            or intent['child_choice_sha256']!=terminal['sdkExecution']['childChoiceSha256']):
            raise RuntimeBindingError('child_received_intent_invalid')
        if intent['action']=='execute':
            if intent['request_id'] not in dict(self.child_catalog(assignment)):raise RuntimeBindingError('child_received_intent_invalid')
            if intent['request_id'] in self.attempted_requests(assignment):return None
        elif intent['action']=='propose':
            if intent.get('proposal',{}).get('proposal_id') in self.proposal_results(assignment):return None
            raise RuntimeBindingError('child_proposal_not_received')
        elif intent['action'] not in {'finish','cancel'} or intent['request_id'] is not None:
            raise RuntimeBindingError('child_received_intent_invalid')
        _,context=prepare_environment(worker._selection,worker._environment)
        failure=_owner().provider_output_safety_scan_terminal('codex',context.needles,
            stdout=json_text({'terminal':terminal,'artifact':document}).encode(),stderr=b'',serialized_line=False)
        if failure is not None:raise RuntimeBindingError(failure)
        return intent

    def attach_decision_worker(self,assignment,worker,choice_json):
        if (type(worker) is not SdkCoordinationWorker or worker._authority is not self
            or Path(worker._selection.work_item).resolve()!=Path(assignment.child_work_item).resolve()):
            raise RuntimeBindingError('child_decision_authority_mismatch')
        if hashlib.sha256(json_text(worker._selection.to_dict()).encode()).hexdigest()!=assignment.decision_runtime_sha256:
            raise RuntimeBindingError('child_decision_runtime_not_admitted')
        request=self._root_authority.resolve(worker._request_id)
        self.validate_decision(assignment,request,choice_json)
        validate_admitted_request(request,worker._selection)
        previous=self._decision_workers.get(worker._request_id)
        if previous is not None and previous is not worker:raise RuntimeBindingError('child_decision_already_bound')
        _,context=prepare_environment(worker._selection,worker._environment)
        projection=json.loads(choice_json)
        handoff=json_text({key:projection[key] for key in ("received_results","unavailable_results","proposal_results") if key in projection})
        failure=_owner().provider_output_safety_scan_terminal(request.provider,context.needles,stdout=handoff.encode(),stderr=b"",serialized_line=False)
        if failure is not None:raise RuntimeBindingError(failure)
        self._decision_workers[worker._request_id]=worker
        self._decision_requests[worker._request_id]=request

    def attempted_requests(self,assignment):
        self.assert_child_current(assignment,'recovery')
        _,item=self._actual_item(assignment);result={}
        for key,selection in self._selections.items():
            if not os.path.lexists(item/'agent-runs.jsonl'):continue
            _,_,events=_events(replace(selection,work_item=str(item)))
            request=self.resolve(key);selected=selected_sdk_execution(request,selection)
            rows=[e for e in events if e.get('runId') in {request.external_dispatch_id,request.external_evidence_run_id}]
            if rows:
                if any(e.get('sdkExecution')!=selected for e in rows):raise RuntimeBindingError('child_attempt_changed')
                result[key]={'events':rows}
        return result

    def validate_decision(self,assignment,request,choice_json):
        from .coordination import validate_child_choice
        choice=validate_child_choice(choice_json)
        if choice.get("goal")!=assignment.goal or choice.get("context")!=assignment.context:
            raise RuntimeBindingError("child_goal_changed")
        if choice["assignment_sha256"]!=assignment.assignment_sha256 or request.admitted_request_id!=assignment.child_id:
            raise RuntimeBindingError("child_decision_assignment_changed")
        self.assert_child_current(assignment,'child_model')
        if (type(request) is not CoordinationInferenceRequest or request.child_choice_json!=choice_json
            or request.work_item_id!=Path(assignment.child_work_item).name
            or request.coordinator_binding!=assignment.coordinator_binding or not set(request.scope)<=set(assignment.scope)
            or request.decision_session_mode!=assignment.decision_session_mode):
            raise RuntimeBindingError('child_decision_scope_mismatch')
        _require_authority(self._root_authority.assert_current,request,'child_model')

    def receive_child_result(self,assignment):
        self.assert_child_current(assignment,'finish')
        if 'finish' not in assignment.lifecycle_permissions:raise RuntimeBindingError('child_finish_not_admitted')
        if not set(self.child_required_request_ids(assignment))<=self.completed_requests(assignment).keys():
            raise RuntimeBindingError('child_required_results_pending')
        if any(v['status']=='pending' for v in self.proposal_results(assignment).values()):raise RuntimeBindingError('child_proposals_pending')
        self.received_context(assignment)
        lifecycle,item=self._actual_item(assignment)
        # Existing close owns all gates, open launches, artifacts, dispositions,
        # atomic archive and recovery. This facade cannot waive any prerequisite.
        return lifecycle.close_item(self._repository_root,item.name,self._closure_data,self._terminal_instant)

    async def cancel_child(self,assignment):
        # Immutable grant remains readable after revocation so draining is retryable.
        if assignment!=self.resolve_child(assignment.child_id):raise RuntimeBindingError('child_assignment_changed')
        if 'cancel' not in assignment.lifecycle_permissions:raise RuntimeBindingError('child_cancel_not_admitted')
        writer,validator,budget=_ledger(self._root_selection)
        _,_,events=_events(self._root_selection)
        if not any(e.get('runId')==assignment.child_id+'-cancel' for e in events):
            # Ancestor revocation removes delegation authority, not the ability
            # to stop this already admitted subtree. Immutable scope was checked above.
            self._actual_item(assignment)
            grant=next(e for e in events if e.get('runId')==assignment.child_id)
            from .receiving import review_artifact_target
            path=review_artifact_target(self._root_selection.work_item,grant['artifact'])
            with path.open('rb') as stream:content=stream.read(grant['artifactSizeBytes']+1)
            if len(content)!=grant['artifactSizeBytes'] or hashlib.sha256(content).hexdigest()!=grant['artifactRevision']:
                raise RuntimeBindingError('child_assignment_changed')
            row=_child_record(writer,validator,self._root_selection,run_id=assignment.child_id+'-cancel',artifact=grant['artifact'],content=content,
                scope='child-lead:'+assignment.child_work_item,cancelled=True,instant=self._terminal_instant)
            def append(previous):
                errors=[];rows=validator.load_jsonl(Path(self._root_selection.work_item)/'agent-runs.jsonl',errors,source_bytes=previous.encode(),ledger_resource_budget=budget)
                if errors:raise RuntimeBindingError('child_ledger_invalid')
                if any(e.get('runId')==row['runId'] for e in rows):raise RuntimeBindingError('child_already_cancelled')
                _load_child_assignment(self._root_selection,assignment.child_id,events=rows,allow_cancelled=True)
                return row
            try:
                writer._append_event_transaction(Path(self._root_selection.work_item),validator,append,ledger_resource_budget=budget)
            except RuntimeBindingError as error:
                if str(error)!='child_already_cancelled':raise
                matching=[e for e in _events(self._root_selection)[2] if e.get('runId')==row['runId']]
                if matching!=[row]:raise RuntimeBindingError('child_revocation_changed')
        for key,executor in {**(self._executors or {}),**self._decision_workers}.items():
            try:
                self.cancellation_receipts[key]=await executor.cancel({**self._executor_requests,**self._decision_requests}[key].run_id)
            except Exception:
                self.cancellation_receipts[key]={'requested':True,'acknowledged':False,'error':'cancel_owner_failed'}
        return {'status':'revoked','receipts':dict(self.cancellation_receipts)}
