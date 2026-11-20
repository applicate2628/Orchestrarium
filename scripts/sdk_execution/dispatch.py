"""Explicit one-shot SDK execution bridge under the existing launch owner.

The invoking Host authorizes execution, just as for the legacy wrapper. A binding
file supplies constraints, never permission. No SDK import, subprocess, credential
change, or model call occurs on import. Receipt delivery remains provider_prompt's
owner; this module neither appends ledger rows nor accepts project review.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import secrets
import stat
import threading
import time
from typing import Any, Callable

from .contracts import ExecutionRequest, json_text, strict_json
from . import receiving, runtime


class DispatchError(ValueError):
    """Closed diagnostics deliberately omit binding/auth/provider contents."""


_BINDING_KEYS = frozenset({
    "schemaVersion", "accountBinding", "expectedAccountEmail", "coordinatorBinding",
    "scope", "artifactIdentity", "maxEvents", "jobMemoryLimitBytes",
})
_BINDING_LIMIT = 65_536
_COPILOT_STAGES = ("sdk_prepare", "sdk_launch_admission", "sdk_launch_commit", "sdk_worker_start",
    "copilot_start", "copilot_client_create", "copilot_session_create", "copilot_profile_before",
    "copilot_send", "copilot_profile_after", "copilot_result")
_CLAUDE_STAGES = ("sdk_prepare", "sdk_launch_admission", "sdk_launch_commit", "sdk_worker_start",
                  "start", "account", "connect", "account", "query", "account")
_STAGES = ("sdk_prepare", "sdk_launch_admission", "sdk_launch_commit", "sdk_hook_trust",
           "sdk_worker_start", "start", "client_start", "thread_start", "turn_start")


def _owner():
    import provider_prompt
    return provider_prompt


def _copilot_auth_snapshot(auth):
    owner = _owner()
    return (auth.mode, auth.child_environment.get(owner.COPILOT_BYOK_ENDPOINT_ENV),
        tuple(auth.child_environment.get(key) for key in owner.PROVIDER_AUTH_SECRET_ENV_KEYS_V1[auth.mode]))


def _auth_context_snapshot(auth):
    """Private selected auth controls, never a vendor identity or exported digest."""
    owner = _owner()
    if not owner.claude_programmatic_auth_mode_supported(auth.mode):
        raise DispatchError("E_CLAUDE_SDK_API_AUTH_REQUIRED")
    controls = owner.PROVIDER_AUTH_CONTROL_ENV_KEYS_V1[auth.mode]
    keys = set(owner.PROVIDER_AUTH_SECRET_ENV_KEYS_V1[auth.mode]) | {"CLAUDE_CONFIG_DIR"}
    for kind in ("scalar", "file", "directory"):
        keys.update(controls[kind])
    if controls["selector"] is not None:
        keys.add(controls["selector"])
    return auth.mode, {key: auth.child_environment[key] for key in keys if key in auth.child_environment}


def _require_claude_sdk_flags(flags):
    """Reject caller CLI semantics the prompt-only SDK route cannot preserve.

    resolved_profile appends legacy --setting-sources user itself; that suffix
    is not caller intent. SDK uses its explicit verified governance selection
    and native preset with ambient settings disabled.
    """
    index = 0
    while index < len(flags):
        flag = flags[index]
        if flag == "-p":
            index += 1
        elif flag in {"--model", "--effort", "--output-format"} and index + 1 < len(flags):
            if flag == "--output-format" and flags[index + 1] != "text":
                raise DispatchError("E_CLAUDE_SDK_FLAGS_UNSUPPORTED")
            index += 2
        else:
            raise DispatchError("E_CLAUDE_SDK_FLAGS_UNSUPPORTED")


def _text(value: object) -> bool:
    return (type(value) is str and bool(value.strip()) and len(value.encode("utf-8")) <= 4096
            and not any(ord(char) < 32 for char in value))


def read_binding(path: Path) -> dict[str, Any]:
    """Bounded strict snapshot, not an authorization token or replay handle."""
    try:
        owner = _owner()
        owner.validate_no_reparse_components(path)
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode):
            raise ValueError()
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            raw = stream.read(_BINDING_LIMIT + 1)
            after = os.fstat(stream.fileno())
        current = path.lstat()
        owner.validate_no_reparse_components(path)
        if not stat.S_ISREG(current.st_mode):
            raise ValueError()
        with path.open("rb") as stream:
            reopened = os.fstat(stream.fileno())
        # Python/Windows path stat and handle fstat expose different ctime
        # semantics. Compare ctime only between handle observations, as the
        # runtime executable owner does; retain independent path identity.
        path_identity = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)
        handle_identity = lambda value: (*path_identity(value), value.st_ctime_ns)
        if (len(raw) > _BINDING_LIMIT
            or len({path_identity(v) for v in (before, opened, after, current, reopened)}) != 1
            or len({handle_identity(v) for v in (opened, after, reopened)}) != 1):
            raise ValueError()
        value = strict_json(raw.decode("utf-8"), max_bytes=_BINDING_LIMIT)
        if type(value) is not dict or type(value.get("schemaVersion")) is not int:
            raise ValueError()
        version = value["schemaVersion"]
        expected = {1: _BINDING_KEYS, 2: _BINDING_KEYS | {"installedHookRoot"},
                    3: _BINDING_KEYS | {"installedHookRoot", "contextMode", "contextHandoff"},
                    4: _BINDING_KEYS | {"installedHookRoot", "contextMode", "contextHandoff", "writeWorkspace"},
                    5: _BINDING_KEYS | {"installedHookRoot", "contextMode", "contextHandoff", "predecessorEvidenceRunId"}}
        if version not in expected or set(value) != expected[version]:
            raise ValueError()
        if version in (3, 4):
            mode, handoff = value["contextMode"], value["contextHandoff"]
            if mode not in ("fresh", "handoff"):
                raise ValueError()
            if ((mode == "fresh" and handoff is not None) or
                (mode == "handoff" and (type(handoff) is not str or not handoff.strip()))):
                raise ValueError()
        if version == 5:
            if (value["contextMode"] not in {"continuation", "fork"} or value["contextHandoff"] is not None
                    or not _text(value["predecessorEvidenceRunId"])):
                raise ValueError()
        if version == 2 or (version in (3, 4, 5) and value["installedHookRoot"] is not None):
            selected_root = value["installedHookRoot"]
            if (type(selected_root) is not str or not selected_root or not Path(selected_root).is_absolute()
                    or any(ord(char) < 32 or ord(char) == 127 for char in selected_root)):
                raise ValueError()
        if any(not _text(value[key]) for key in ("accountBinding", "coordinatorBinding", "artifactIdentity")):
            raise ValueError()
        email = value["expectedAccountEmail"]
        if email is not None and not _text(email):
            raise ValueError()
        scope = value["scope"]
        if type(scope) is not list or not 1 <= len(scope) <= 128 or any(not _text(s) for s in scope):
            raise ValueError()
        for key, limit in (("maxEvents", 65_536), ("jobMemoryLimitBytes", 2**63 - 1)):
            if type(value[key]) is not int or not 1 <= value[key] <= limit:
                raise ValueError()
        if version == 4:
            workspace = value["writeWorkspace"]
            if (not _text(workspace) or not Path(workspace).is_absolute()
                    or str(Path(workspace)) != workspace or ".." in Path(workspace).parts):
                raise ValueError()
        return value
    except (OSError, ValueError, TypeError, UnicodeError):
        raise DispatchError("E_CODEX_SDK_BINDING_INVALID") from None


@dataclass(frozen=True)
class DispatchResult:
    terminal_bytes: bytes
    exit_code: int
    terminal: dict[str, object]


class CodexReviewDispatch:
    """One launch's constraint guard and retained evidence, not a policy store."""

    def __init__(self, prevalidated, request, selection, environment, cancellation_probe,
                 started_at, deadline, runtime_namespace=None, *, protected_paths=(), capture_root=None, auth_snapshot=None):
        self._auth_snapshot = auth_snapshot
        self.prevalidated = prevalidated
        self._runtime_namespace = runtime_namespace
        self.request = request
        self.selection = selection
        self._environment = dict(environment)
        self._cancelled = cancellation_probe
        self.started_at, self.deadline = started_at, deadline
        self.runtime_run = None
        self._interrupted_runtime = None
        self.terminal = None
        self._lock = threading.RLock()
        self._consumed = False
        self._finished = False
        self._stage = 0
        self._stages = (_STAGES[:-2] + ("fork" if request.context_mode == "fork" else "resume", "reconcile", "turn_start")
                        if request.native_continuation is not None else _STAGES)
        self._copilot_stages = _COPILOT_STAGES
        if request.provider == "copilot":
            stages = list(_COPILOT_STAGES)
            if request.native_continuation is not None:
                index = stages.index("copilot_session_create")
                stages[index:index+1] = ["copilot_session_resume", "copilot_session_history"]
            if request.result_kind == "task" and request.role == "consultant" and request.write_workspace is None:
                stages.insert(stages.index("copilot_profile_after"), "copilot_session_history")
            self._copilot_stages = tuple(stages)
        self._queries = 0
        self._controls = self._control_snapshot()
        self._artifact = prevalidated.control.ledger_artifact
        self._result_limit = prevalidated.control.result_max_bytes
        self._capture_limit = prevalidated.control.capture_max_bytes
        self._commitment = runtime.request_sha256(request, selection)
        self._protected_paths = tuple(protected_paths)
        self._capture_root = capture_root
        self._capture_identity = None
        self._workspace_identity = runtime.validate_worker_custody(request, selection)

    def _check_auth_context(self):
        if self.request.provider == "copilot":
            auth = _owner().resolve_provider_auth_configuration("copilot", dict(self._environment))
            if _copilot_auth_snapshot(auth) != self._auth_snapshot:
                raise DispatchError("E_COPILOT_SDK_AUTH_CONTEXT_CHANGED")
            return
        if self.request.provider != "claude":
            return
        if _owner()._capture_output_path("claude") != self._capture_root:
            raise DispatchError("E_CLAUDE_SDK_CAPTURE_SELECTION_CHANGED")
        auth = _owner().resolve_provider_auth_configuration("claude", dict(self._environment))
        if (not _owner().claude_programmatic_auth_mode_supported(auth.mode)
                or _auth_context_snapshot(auth) != self._auth_snapshot):
            raise DispatchError("E_CLAUDE_SDK_AUTH_CONTEXT_CHANGED")

    def _authorize_tool(self, request, name, arguments):
        # Read-only routes remain prompt-only; writes use the selected workspace owner.
        from .claude import OUTPUT_TOOL, authorize_claude_workspace_tool
        from .contracts import validate_task, validate_review
        if request != self.request:
            raise DispatchError("E_CLAUDE_SDK_TOOL_DENIED")
        self._check_auth_context()
        if request.provider == "copilot":
            if request.write_workspace is None: raise DispatchError("E_COPILOT_SDK_TOOL_DENIED")
            runtime.authorize_workspace_file_tool(request,self.selection,name,arguments,
                expected_identity=self._workspace_identity,protected_paths=self._protected_paths)
            return
        if name == OUTPUT_TOOL:
            (validate_task if request.result_kind == "task" else validate_review)(arguments, request=request)
        elif request.write_workspace is not None:
            authorize_claude_workspace_tool(request, self.selection, name, arguments,
                expected_identity=self._workspace_identity, protected_paths=self._protected_paths)
        else:
            raise DispatchError("E_CLAUDE_SDK_TOOL_DENIED")

    def _verify_auth_context(self, request, evidence):
        if (request != self.request or type(evidence) is not dict
                or set(evidence) != {"phase", "data"}
                or evidence["phase"] != {6:"before_connect", 8:"initialize", 10:"system_init"}.get(self._stage)
                or type(evidence["data"]) is not dict):
            raise DispatchError("E_CLAUDE_SDK_AUTH_CONTEXT_INVALID")
        self._check_auth_context()
        # Host-selected alias for unchanged API/cloud configuration, not an
        # observed vendor account, billing identity, or credential-chain identity.
        return request.account_binding

    def _check_write_targets(self):
        if self.request.write_workspace is None:
            return
        runtime.validate_worker_custody(self.request, self.selection, expected_identity=self._workspace_identity)
        root = Path(self.request.write_workspace)
        _require_policy_custody(root, self._runtime_namespace)
        for path in self._protected_paths:
            _require_disjoint(root, path)
        if _owner()._capture_output_path(self.request.provider) != self._capture_root:
            raise DispatchError("E_CODEX_SDK_CAPTURE_SELECTION_CHANGED")
        _require_disjoint(root, self._capture_root, directory=True)
        if self._capture_identity is not None:
            path, dev, ino = self._capture_identity
            _require_disjoint(root, path, directory=True)
            current = path.stat()
            if (current.st_dev, current.st_ino) != (dev, ino):
                raise DispatchError("E_CODEX_SDK_CAPTURE_CHANGED")

    def bind_capture_directory(self, path):
        if self.request.write_workspace is None:
            return
        if self._consumed or self._capture_identity is not None:
            raise DispatchError("E_CODEX_SDK_CAPTURE_CHANGED")
        self._check_write_targets()
        candidate = Path(path)
        _require_disjoint(Path(self.request.write_workspace), candidate, directory=True)
        if not candidate.is_dir() or not candidate.resolve().is_relative_to(self._capture_root.resolve()):
            raise DispatchError("E_CODEX_SDK_CAPTURE_CHANGED")
        current = candidate.stat()
        self._capture_identity = (candidate, current.st_dev, current.st_ino)

    def _control_snapshot(self):
        c = self.prevalidated.control
        return (str(c.ledger), c.ledger_role, c.ledger_role_explicit, c.ledger_lane,
                c.ledger_artifact, tuple(c.ledger_closes), c.ledger_max_events,
                c.ledger_max_bytes, c.timeout_secs, c.result_max_bytes, c.capture_max_bytes,
                tuple(c.provider_flags), str(c.terminal_receipt), c.user_approved_launch,
                c.task_class, json_text(c.astra_task_authorization),
                str(c.sdk_task_binding), str(c.sdk_review_binding))

    def assert_current(self, request, effect):
        with self._lock:
            cancelled = self._cancelled()
            if (not self._consumed or self._finished or type(cancelled) is not bool or cancelled
                or time.monotonic() >= self.deadline or request != self.request
                or self._control_snapshot() != self._controls
                or runtime.request_sha256(self.request, self.selection) != self._commitment):
                raise DispatchError("E_CODEX_SDK_INVOCATION_NOT_CURRENT")
            self._check_write_targets()
            self._check_auth_context()
            if self.request.write_workspace is not None and self._capture_identity is None:
                raise DispatchError("E_CODEX_SDK_CAPTURE_UNBOUND")
            owner = _owner()
            role = owner.external_role_provenance(self.prevalidated.control, request.provider)
            flags, model, effort = owner.resolved_profile(request.provider, self.prevalidated.control.provider_flags)
            if (role != self.prevalidated.role_provenance
                or (tuple(flags), model, effort) != (self.prevalidated.flags, request.model, request.effort)):
                raise DispatchError("E_CODEX_SDK_SELECTION_CHANGED")
            owner._qualify_managed_model_launch(
                request.provider, self.prevalidated, runtime_namespace=self._runtime_namespace)
            owner.ledger_resource_options(self.prevalidated.control)
            if request.provider == "copilot":
                if (effect == "tool" and request.write_workspace is not None
                        and self._stage == self._copilot_stages.index("copilot_send") + 1):
                    return  # Exact Host file arguments are checked by the tool owner.
                # Export retained evidence after any admitted adapter phase,
                # including partial/failed acquisition. This terminal-only
                # transition never authorizes a skipped native effect or replay.
                if effect == "copilot_result" and self._copilot_stages.index("copilot_start") < self._stage < len(self._copilot_stages):
                    self._stage = len(self._copilot_stages)
                    return
                if self._stage >= len(self._copilot_stages) or effect != self._copilot_stages[self._stage]:
                    raise DispatchError("E_COPILOT_SDK_EFFECT_DENIED")
                self._stage += 1
                return
            if request.provider == "claude":
                if effect == "tool" and self._stage == len(_CLAUDE_STAGES):
                    return  # Exact StructuredOutput payload is checked separately.
                if self._stage >= len(_CLAUDE_STAGES) or effect != _CLAUDE_STAGES[self._stage]:
                    raise DispatchError("E_CLAUDE_SDK_EFFECT_DENIED")
                self._stage += 1
                return
            if effect == "query":
                # Configuration/catalog reads only before the one admitted turn.
                if self._stage not in (7, 8) or self._queries >= request.max_events:
                    raise DispatchError("E_CODEX_SDK_EFFECT_DENIED")
                self._queries += 1
            elif self._stage >= len(self._stages) or effect != self._stages[self._stage]:
                raise DispatchError("E_CODEX_SDK_EFFECT_DENIED")
            else:
                self._stage += 1

    def execute(self, process_owner) -> runtime.RuntimeRun:
        with self._lock:
            if self._consumed:
                raise DispatchError("E_CODEX_SDK_OPERATION_CONSUMED")
            self._check_write_targets()
            if self.request.write_workspace is not None and self._capture_identity is None:
                raise DispatchError("E_CODEX_SDK_CAPTURE_UNBOUND")
            self._consumed = True
        try:
            execute = runtime.run_admitted_codex if self.request.provider == "codex" else runtime.run_admitted_review
            callbacks = {} if self.request.provider != "claude" else {
                "authorize_tool": self._authorize_tool, "verify_account": self._verify_auth_context}
            if self.request.provider == "copilot" and self.request.write_workspace is not None:
                callbacks = {"authorize_tool":self._authorize_tool}
            run = execute(
                self.request, self.selection, owner=process_owner,
                source_environment=dict(self._environment), authority=self.assert_current,
                deadline_monotonic=self.deadline, cancellation_probe=self._cancelled,
                started_at=self.started_at,
                capture_limit_bytes=self._capture_limit, **callbacks,
            )
            self.runtime_run = run  # Retain BEFORE materialization/readback can fail.
            return run
        except runtime.InterruptedRuntime as interrupted:
            self._interrupted_runtime = interrupted
            raise
        finally:
            with self._lock:
                self._finished = True

    @property
    def recovery_max_bytes(self) -> int:
        return self._capture_limit + 6 * self._result_limit + 65_536

    def has_interrupted_evidence(self) -> bool:
        return self._interrupted_runtime is not None

    def recovery_bytes(self) -> bytes:
        """Bounded diagnostic custody, NEVER a restorable observation or permit.

        Protocol streams may contain the full prompt and credentials: retain only
        their exact digest/length/truncation, never their bytes. Only scanned result
        data survives. The original creator-owned observation remains in memory.
        """
        interrupted = self._interrupted_runtime
        run = self.runtime_run if interrupted is None else interrupted.run
        if (type(run) is not runtime.RuntimeRun or run.request != self.request
            or runtime.request_sha256(run.request, run.selection) != self._commitment):
            raise DispatchError("E_CODEX_SDK_RECOVERY_UNAVAILABLE")
        from process_supervision.process_runner import safe_serialize_result
        from process_supervision.sdk_worker import SdkWorkerInterrupted, SdkWorkerObservation
        record = {
            "schemaVersion": 1, "kind": "sdk-diagnostic-custody",
            "externalDispatchId": self.request.external_dispatch_id,
            "externalEvidenceRunId": self.request.external_evidence_run_id,
            "requestSha256": self._commitment,
            "authorizing": False, "receiving": "not-established",
            "restorableObservation": False, "replayAuthorized": False,
            "payloadOmitted": "protocol-may-contain-prompt-or-secrets",
        }
        observation = run.observation
        if interrupted is not None:
            observation = interrupted.terminal
            if (type(observation) is not SdkWorkerInterrupted
                    or observation.request != self.request
                    or observation.result.request != self.request):
                raise DispatchError("E_CODEX_SDK_RECOVERY_UNAVAILABLE")
            record["workerObservation"] = "interrupted-after-terminal"
        elif observation is None:
            record["workerObservation"] = "unavailable"
        else:
            if type(observation) is not SdkWorkerObservation or not observation.is_bound_to(self.request):
                raise DispatchError("E_CODEX_SDK_RECOVERY_UNAVAILABLE")
            record["process"] = safe_serialize_result(observation.process)
            for name in ("stdout", "stderr"):
                raw = getattr(observation, name)
                if type(raw) is not bytes or len(raw) > self._capture_limit:
                    raise DispatchError("E_CODEX_SDK_RECOVERY_LIMIT")
                record[name] = {
                    "byteLength": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                    "truncated": getattr(observation.process, name).truncated,
                    "payloadOmitted": "protocol-may-contain-prompt-or-secrets",
                }
        if observation is not None:
            candidate = {
                "protocolError": observation.protocol_error,
                "cancel": observation.cancel.to_dict() if observation.cancel is not None else None,
                "result": None,
            }
            if observation.result is not None:
                candidate["result"] = observation.result.to_dict()
                del candidate["result"]["request"]
                # Protocol observations are not a safe provider result projection.
                del candidate["result"]["observations"]
                candidate["result"]["observationsOmitted"] = "protocol-may-contain-prompt-or-secrets"
            # Only closed local categories may survive a failed safety scan.
            # Exception text, arbitrary scanner values and payload remain private.
            safety_codes = {
                code: code for code in (
                    "E_EXTERNAL_PROVIDER_CREDENTIAL_ECHO",
                    "E_EXTERNAL_PROVIDER_MACHINE_PATH_ECHO",
                    "E_EXTERNAL_PROVIDER_OUTPUT_SCAN_UNAVAILABLE",
                )
            }
            omission_reason = "candidate_serialization_failed"
            safety_code = None
            try:
                encoded = json_text(candidate).encode("utf-8")
                omission_reason = "scan_context_unavailable"
                if not isinstance(run.output_context, _owner().ProviderOutputContext):
                    raise ValueError("scan context unavailable")
                omission_reason = "result_scan_failed"
                if observation.result is not None:
                    receiving.scan_execution_output(observation.result, run.output_context)
                omission_reason = "candidate_scan_failed"
                failure = _owner().provider_output_safety_scan_terminal(
                    self.request.provider, run.output_context.needles, stdout=encoded, stderr=b"", serialized_line=False,
                )
                if failure is not None:
                    if type(failure) is str:
                        safety_code = safety_codes.get(failure)
                    raise ValueError("unsafe diagnostic output")
                omission_reason = "prompt_check_failed"
                if json_text(self.request.prompt)[1:-1].encode("utf-8") in encoded:
                    omission_reason = "prompt_echo"
                    raise ValueError("unsafe diagnostic output")
            except Exception as exc:
                record["unsafeOutputOmitted"] = True
                record["omissionReason"] = omission_reason
                if (omission_reason in {"result_scan_failed", "candidate_scan_failed"}
                    and type(exc) is ValueError and len(exc.args) == 1 and type(exc.args[0]) is str):
                    safety_code = safety_code or safety_codes.get(exc.args[0])
                if safety_code is not None:
                    record["safetyFailureCode"] = safety_code
            else:
                record["decodedResult"] = candidate
        payload = (json_text(record) + "\n").encode("utf-8")
        # JSON escaping overhead plus bounded process/identity metadata. No silent
        # clipping: an overlarge diagnostic is unavailable, never a partial proof.
        if len(payload) > self.recovery_max_bytes:
            raise DispatchError("E_CODEX_SDK_RECOVERY_LIMIT")
        return payload

    def receive(self) -> DispatchResult:
        """After caller-verified process-owner closure, receive the retained run.

        Never retry this method after failure: retained evidence and durable state
        require explicit receiving reconciliation, not replay or a second append.
        """
        with self._lock:
            if self._control_snapshot() != self._controls:
                raise DispatchError("E_CODEX_SDK_RECEIVING_DRIFT")
            if not self._finished or self.runtime_run is None or getattr(self, "_receive_consumed", False):
                raise DispatchError("E_CODEX_SDK_RECEIVING_UNAVAILABLE")
            self._receive_consumed = True
        if self.request.write_workspace is not None:
            for path in self._protected_paths:
                _require_disjoint(Path(self.request.write_workspace), path)
            if self._capture_identity is None:
                raise DispatchError("E_CODEX_SDK_CAPTURE_UNBOUND")
            path, dev, ino = self._capture_identity
            _require_disjoint(Path(self.request.write_workspace), path, directory=True)
            current = path.stat()
            if (current.st_dev, current.st_ino) != (dev, ino):
                raise DispatchError("E_CODEX_SDK_CAPTURE_CHANGED")
        run = self.runtime_run
        if run.observation is None:
            payload = receiving.preworker_failure_payload(run)
            terminal = run.terminal
        else:
            payload = receiving.terminal_payload(
                run.request, run.observation, output_context=run.output_context,
                admitted_sdk_execution=runtime.selected_sdk_execution(run.request, run.selection),
            )
            # Bound the exact exported representation, not only SDK events.
            if len(str(payload["resultText"]).encode("utf-8")) > self._result_limit:
                raise DispatchError("E_CODEX_SDK_RESULT_LIMIT")
        owner = _owner()
        line = owner.SDK_RESULT_PREFIX + json_text(payload) + "\n"
        if len(line.encode("utf-8")) > self._capture_limit:
            raise DispatchError("E_CODEX_SDK_RECEIPT_LIMIT")
        owner.parse_provider_result(line)
        failure = owner._provider_terminal_line_safety(self.request.provider, run.output_context.needles, line)
        if failure:
            raise DispatchError(failure)
        if run.observation is not None:
            terminal = receiving.receive_runtime_run(
                run, artifact=self._artifact,
                started_at=self.started_at, updated_at=_utc_now(),
            )
        self.terminal = terminal
        if not isinstance(terminal, dict) or (
            terminal.get("runId"), terminal.get("status"), terminal.get("gate")
        ) != (self.request.external_evidence_run_id, payload["status"], payload["gate"]):
            raise DispatchError("E_CODEX_SDK_READBACK_MISMATCH")
        code = (130 if payload.get("cancelled") else 124 if payload.get("timedOut")
                else 1 if payload.get("status") == "blocked" else 0)
        return DispatchResult(line.encode("utf-8"), code, terminal)


def _require_disjoint(workspace: Path, target: Path, *, directory=False):
    """Selected namespace custody, not an OS sandbox or hostile-race guarantee."""
    _owner().validate_no_reparse_components(target)
    guarded = target.resolve(strict=False)
    if guarded.is_relative_to(workspace) or (directory and workspace.is_relative_to(guarded)):
        raise DispatchError("E_CODEX_SDK_WRITE_TARGET_OVERLAP")


def _policy_comparison_path(path: Path) -> Path:
    value = os.path.normcase(os.path.abspath(path))
    # Windows junction readlink uses extended paths. Normalize only comparison;
    # keep original paths for filesystem operations and the existing loader.
    if os.name == "nt":
        if value.startswith("\\\\?\\unc\\"):
            value = "\\\\" + value[8:]
        elif value.startswith("\\\\?\\"):
            value = value[4:]
    return Path(value)


def _require_policy_custody(workspace: Path, runtime_namespace):
    # The policy owner supports logical installations with symlink participants.
    # Protect both selected namespace and resolved companion without forbidding
    # that supported layout or executing policy bytes before checking custody.
    namespace = Path(runtime_namespace) if runtime_namespace is not None else Path(os.path.abspath(_owner().__file__)).parent
    if not namespace.is_absolute():
        raise DispatchError("E_CODEX_SDK_WRITE_POLICY_CUSTODY")
    selected = namespace / "model_routing" / "launch_policy.py"
    # Protect every link participant, not just the final target: an external
    # policy can resolve through a worker-writable intermediate directory/link.
    workspace = _policy_comparison_path(workspace)
    pending = [namespace, selected]
    seen = set()
    while pending:
        path = pending.pop()
        logical = _policy_comparison_path(path)
        if logical in seen:
            continue
        seen.add(logical)
        if logical.is_relative_to(workspace):
            raise DispatchError("E_CODEX_SDK_WRITE_POLICY_CUSTODY")
        resolved = _policy_comparison_path(path.resolve(strict=True))
        if resolved.is_relative_to(workspace):
            raise DispatchError("E_CODEX_SDK_WRITE_POLICY_CUSTODY")
        if path == namespace and workspace.is_relative_to(resolved):
            raise DispatchError("E_CODEX_SDK_WRITE_POLICY_CUSTODY")
        pending.extend(path.parents)
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or bool(getattr(metadata, "st_file_attributes", 0) & 0x400):
            target = Path(os.readlink(path))
            pending.append(target if target.is_absolute() else path.parent / target)



def _utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _prepare_dispatch(prevalidated, binding_path: Path, *, source_environment: dict[str, str],
                      cancellation_probe: Callable[[], bool],
                      runtime_namespace: Path | None = None, provider: str = "codex") -> CodexReviewDispatch:
    """Read-only preparation; canonical runtime alone claims and settles a launch."""
    if provider not in {"codex", "claude", "copilot"}:
        raise DispatchError("E_SDK_PROVIDER_UNSUPPORTED")
    prepared_at = time.monotonic()
    _require_supported_platform()
    owner = _owner()
    if type(prevalidated) is not owner.PolicyBoundLaunch or not callable(cancellation_probe):
        raise DispatchError("E_CODEX_SDK_SELECTION_INVALID")
    c = prevalidated.control
    if provider == "claude":
        _require_claude_sdk_flags(c.provider_flags)
    role = owner.external_role_provenance(c, provider)
    flags, model, effort = owner.resolved_profile(provider, c.provider_flags)
    if c.sdk_task_binding is not None and c.sdk_review_binding is not None:
        raise DispatchError("E_CODEX_SDK_SELECTION_INVALID")
    task_mode = c.sdk_task_binding is not None
    # Direct callers must retain the same rule as the public CLI entrypoint.
    owner._qualify_managed_model_launch(provider, prevalidated, runtime_namespace=runtime_namespace)
    binding = read_binding(Path(binding_path))
    if provider == "claude" and (binding.get("installedHookRoot") is not None or binding["expectedAccountEmail"] is not None
            or model in {"opus", "sonnet", "haiku"}):
        raise DispatchError("E_CLAUDE_SDK_PROMPT_ONLY_REQUIRED")
    if provider == "copilot" and ((task_mode and binding.get("writeWorkspace") is None and role.assigned_role != "consultant")
            or binding.get("contextMode", "fresh") not in {"fresh", "continuation"}
            or binding.get("installedHookRoot") is not None or binding["expectedAccountEmail"] is not None):
        raise DispatchError("E_COPILOT_SDK_PROMPT_ONLY_REQUIRED")
    write_workspace = binding.get("writeWorkspace")
    write_mode = write_workspace is not None
    continuation_mode = binding.get("contextMode") in {"continuation", "fork"}
    if continuation_mode and (provider not in {"codex", "copilot", "claude"} or not task_mode or write_mode
                              or role.assigned_role != "consultant" or role.execution_role != "consultant"
                              or (provider in {"copilot", "claude"} and binding["contextMode"] != "continuation")):
        raise DispatchError("E_CODEX_SDK_CONTINUATION_ROUTE_UNSUPPORTED")
    if write_mode and not task_mode:
        raise DispatchError("E_CODEX_SDK_REVIEW_ONLY")
    expected_role = ("external-worker" if write_mode else "consultant") if task_mode else "external-reviewer"
    if (role.execution_role != expected_role or role != prevalidated.role_provenance
        or (tuple(flags), model, effort) != (prevalidated.flags, prevalidated.model, prevalidated.effort)
        or not c.ledger or not c.ledger_artifact or c.terminal_receipt is None
        or c.ledger_lane or c.ledger_closes or prevalidated.provenance is not None):
        raise DispatchError("E_CODEX_SDK_REVIEW_ONLY")
    if write_mode:
        _require_policy_custody(Path(write_workspace), runtime_namespace)
    for index, flag in enumerate(flags):
        if flag == "--sandbox" and flags[index + 1] != ("workspace-write" if write_mode else "read-only"):
            raise DispatchError("E_CODEX_SDK_REVIEW_ONLY")
    from process_supervision.process_runner import MAX_STDIN_BYTES
    if c.capture_max_bytes > MAX_STDIN_BYTES:
        raise DispatchError("E_CODEX_SDK_CAPTURE_LIMIT")
    if type(source_environment) is not dict or any(type(k) is not str or type(v) is not str for k, v in source_environment.items()):
        raise DispatchError("E_CODEX_SDK_ENVIRONMENT_INVALID")
    item = Path(c.ledger).resolve(strict=True)
    artifact = item / c.ledger_artifact
    receipt_target = c.terminal_receipt.resolve(strict=False)
    reserved = {item / "agent-runs.jsonl", item / "agent-runs.jsonl.lock"}
    if artifact == receipt_target or artifact in reserved or receipt_target in reserved:
        raise DispatchError("E_CODEX_SDK_OUTPUT_ALIAS")
    receiving.review_artifact_target(item, c.ledger_artifact, must_be_new=True)
    cwd = Path.cwd().resolve(strict=True)
    protected_paths = ()
    capture_root = None
    if write_mode:
        if str(cwd) != write_workspace:
            raise DispatchError("E_CODEX_SDK_WRITE_WORKSPACE_MISMATCH")
        protected_paths = tuple(Path(v).absolute() for v in (binding_path, c.terminal_receipt, c.prompt_file) if v is not None)
        for path in protected_paths:
            _require_disjoint(cwd, path)
        capture_root = owner._capture_output_path(provider)
        _require_disjoint(cwd, capture_root, directory=True)
    command, _expected = owner._resolve_launch_provider_command(provider, cwd)
    if len(command) != 1 or not Path(command[0]).is_absolute():
        raise DispatchError("E_CODEX_SDK_NATIVE_EXECUTABLE_REQUIRED")
    executable = Path(command[0])
    if provider == "copilot":
        selected_path = source_environment.get("COPILOT_CLI_PATH")
        if not selected_path or not Path(selected_path).is_absolute() or Path(selected_path).resolve(strict=True) != executable.resolve(strict=True):
            raise DispatchError("E_COPILOT_SDK_RUNTIME_SELECTION_CHANGED")
    owner.validate_no_reparse_components(executable)
    digest = hashlib.sha256()
    with executable.open("rb") as stream:
        while block := stream.read(1_048_576):
            digest.update(block)
    options = owner.ledger_resource_options(c)
    source_environment = dict(source_environment)
    if provider == "claude":
        source_environment["CLAUDE_CONFIG_DIR"] = str(Path(source_environment.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude").expanduser().resolve(strict=False))
    auth = owner.resolve_provider_auth_configuration(provider, dict(source_environment))
    auth_snapshot = None
    if provider == "codex":
        home = Path(source_environment.get("CODEX_HOME") or Path.home() / ".codex").expanduser().resolve(strict=False)
        selection = runtime.CodexRuntimeSelection(
            executable=str(executable), executable_sha256=digest.hexdigest(), codex_home=str(home),
            auth_mode=auth.mode, expected_account_email=binding["expectedAccountEmail"],
            work_item=str(item), ledger_max_events=int(options[1]) if options else None,
            ledger_max_bytes=int(options[3]) if options else None,
            job_memory_limit_bytes=binding["jobMemoryLimitBytes"],
            config_overrides=runtime.CODEX_BOUNDED_REVIEW_OVERRIDES,
            installed_hook_root=binding.get("installedHookRoot"),
        )
    elif provider == "copilot":
        from .copilot import CopilotRuntimeSelection, require_supported_byok_sdk
        base = source_environment.get("COPILOT_BASE_DIRECTORY")
        if not base or not Path(base).is_absolute():
            raise DispatchError("E_COPILOT_SDK_BASE_DIRECTORY_REQUIRED")
        owner.validate_no_reparse_components(Path(base))
        if not Path(base).is_dir(): raise DispatchError("E_COPILOT_SDK_BASE_DIRECTORY_REQUIRED")
        auth_snapshot = _copilot_auth_snapshot(auth)
        endpoint = auth.child_environment.get(owner.COPILOT_BYOK_ENDPOINT_ENV)
        if endpoint is not None:
            if continuation_mode:
                raise DispatchError("E_COPILOT_BYOK_CONTINUATION_UNQUALIFIED")
            require_supported_byok_sdk()
        selection = CopilotRuntimeSelection(
            executable=str(executable), executable_sha256=digest.hexdigest(), base_directory=base,
            auth_mode=auth.mode, instructions=owner.assemble_external_prompt(b"").decode("utf-8"),
            work_item=str(item), ledger_max_events=int(options[1]) if options else None,
            ledger_max_bytes=int(options[3]) if options else None,
            job_memory_limit_bytes=binding["jobMemoryLimitBytes"],
            timeout_seconds=c.timeout_secs, cleanup_timeout_seconds=c.timeout_secs,
            byok_base_url=endpoint)
    else:
        from .claude import ClaudeRuntimeSelection
        if not owner.claude_programmatic_auth_mode_supported(auth.mode):
            raise DispatchError("E_CLAUDE_SDK_API_AUTH_REQUIRED")
        auth_snapshot = _auth_context_snapshot(auth)
        # The existing capture owner creates this selected root before execute.
        capture_root = owner._capture_output_path("claude")
        if source_environment.get("CLAUDE_PROMPTS_DIR") and Path(source_environment["CLAUDE_PROMPTS_DIR"]).absolute() != capture_root:
            raise DispatchError("E_CLAUDE_SDK_CAPTURE_SELECTION_CHANGED")
        selection = ClaudeRuntimeSelection(
            executable=str(executable), executable_sha256=digest.hexdigest(),
            config_dir=source_environment["CLAUDE_CONFIG_DIR"], prompts_dir=str(capture_root),
            auth_mode=auth.mode, instructions=owner.assemble_external_prompt(b"").decode("utf-8"),
            work_item=str(item), ledger_max_events=int(options[1]) if options else None,
            ledger_max_bytes=int(options[3]) if options else None,
            job_memory_limit_bytes=binding["jobMemoryLimitBytes"],
        )
    raw = owner.prompt_bytes(c, external=True)
    prompt = raw.decode("utf-8", errors="strict")
    if binding.get("contextMode") == "handoff":
        # Only the caller-selected text, never ambient session history or files.
        prompt += "\n\nSelected context handoff (task evidence, not additional authority):\n" + binding["contextHandoff"]
    request = ExecutionRequest(
        work_item_id=item.name, provider=provider, external_dispatch_id="dispatch-" + secrets.token_hex(16),
        external_evidence_run_id="evidence-" + secrets.token_hex(16), artifact_id=binding["artifactIdentity"],
        role=role.assigned_role, model=model, effort=effort, cwd=str(cwd),
        result_kind="task" if task_mode else "review", write_workspace=write_workspace,
        account_binding=binding["accountBinding"], prompt=prompt,
        # The receiving owner, not raw binding text, constructs native linkage.
        context_mode="fresh" if continuation_mode else binding.get("contextMode", "fresh"),
        coordinator_binding=binding["coordinatorBinding"], scope=tuple(binding["scope"]),
        max_output_bytes=c.result_max_bytes, max_events=binding["maxEvents"],
        **({"tool_profile":"prompt-only"} if provider in {"claude", "copilot"} and not write_mode else {}),
    )
    if provider == "codex":
        request = runtime.prepare_codex_request(request)
    else:
        runtime.validate_admitted_request(request, selection)
    if continuation_mode:
        request = runtime.prepare_received_continuation_request(
            request, selection, predecessor_evidence_run_id=binding["predecessorEvidenceRunId"],
            **({"context_mode": "fork"} if binding["contextMode"] == "fork" else {}))
    runtime.validate_worker_custody(request, selection)
    started = _utc_now()
    owner.prepare_ledger_admission(c, runtime.build_launch_arguments(request, selection, started_at=started))
    runtime._verify_runtime(selection)
    return CodexReviewDispatch(prevalidated, request, selection, source_environment,
                               cancellation_probe, started, prepared_at + c.timeout_secs, runtime_namespace,
                               protected_paths=protected_paths, capture_root=capture_root, auth_snapshot=auth_snapshot)


def _require_supported_platform():
    # Refuse before hook trust or worker effects, not after a provider probe.
    if os.name != "nt":
        raise DispatchError("E_CODEX_SDK_WINDOWS_ONLY")


def prepare_dispatch(prevalidated, binding_path: Path, *, source_environment: dict[str, str],
                     cancellation_probe: Callable[[], bool],
                      runtime_namespace: Path | None = None, provider: str = "codex") -> CodexReviewDispatch:
    try:
        return _prepare_dispatch(prevalidated, binding_path, source_environment=source_environment,
                                 cancellation_probe=cancellation_probe, runtime_namespace=runtime_namespace, provider=provider)
    except DispatchError:
        raise
    except (OSError, ValueError, TypeError, UnicodeError):
        raise DispatchError("E_CODEX_SDK_PREPARATION_FAILED") from None
