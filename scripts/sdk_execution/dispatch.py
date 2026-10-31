"""Explicit one-shot Codex REVIEW bridge under the existing launch owner.

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
_STAGES = ("sdk_prepare", "sdk_launch_admission", "sdk_launch_commit", "sdk_hook_trust",
           "sdk_worker_start", "start", "client_start", "thread_start", "turn_start")


def _owner():
    import provider_prompt
    return provider_prompt


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
        if version not in (1, 2) or set(value) != (_BINDING_KEYS if version == 1 else _BINDING_KEYS | {"installedHookRoot"}):
            raise ValueError()
        if version == 2:
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
                 started_at, deadline, runtime_namespace=None):
        self.prevalidated = prevalidated
        self._runtime_namespace = runtime_namespace
        self.request = request
        self.selection = selection
        self._environment = dict(environment)
        self._cancelled = cancellation_probe
        self.started_at, self.deadline = started_at, deadline
        self.runtime_run = None
        self.terminal = None
        self._lock = threading.RLock()
        self._consumed = False
        self._finished = False
        self._stage = 0
        self._queries = 0
        self._controls = self._control_snapshot()
        self._artifact = prevalidated.control.ledger_artifact
        self._result_limit = prevalidated.control.result_max_bytes
        self._capture_limit = prevalidated.control.capture_max_bytes
        self._commitment = runtime.request_sha256(request, selection)

    def _control_snapshot(self):
        c = self.prevalidated.control
        return (str(c.ledger), c.ledger_role, c.ledger_role_explicit, c.ledger_lane,
                c.ledger_artifact, tuple(c.ledger_closes), c.ledger_max_events,
                c.ledger_max_bytes, c.timeout_secs, c.result_max_bytes, c.capture_max_bytes,
                tuple(c.provider_flags), str(c.terminal_receipt), c.user_approved_launch)

    def assert_current(self, request, effect):
        with self._lock:
            cancelled = self._cancelled()
            if (not self._consumed or self._finished or type(cancelled) is not bool or cancelled
                or time.monotonic() >= self.deadline or request != self.request
                or self._control_snapshot() != self._controls
                or runtime.request_sha256(self.request, self.selection) != self._commitment):
                raise DispatchError("E_CODEX_SDK_INVOCATION_NOT_CURRENT")
            owner = _owner()
            role = owner.external_role_provenance(self.prevalidated.control, "codex")
            flags, model, effort = owner.resolved_profile("codex", self.prevalidated.control.provider_flags)
            if (role != self.prevalidated.role_provenance
                or (tuple(flags), model, effort) != (self.prevalidated.flags, request.model, request.effort)):
                raise DispatchError("E_CODEX_SDK_SELECTION_CHANGED")
            owner._qualify_managed_model_launch(
                "codex", self.prevalidated, runtime_namespace=self._runtime_namespace)
            owner.ledger_resource_options(self.prevalidated.control)
            if effect == "query":
                # Configuration/catalog reads only before the one admitted turn.
                if self._stage not in (7, 8) or self._queries >= request.max_events:
                    raise DispatchError("E_CODEX_SDK_EFFECT_DENIED")
                self._queries += 1
            elif self._stage >= len(_STAGES) or effect != _STAGES[self._stage]:
                raise DispatchError("E_CODEX_SDK_EFFECT_DENIED")
            else:
                self._stage += 1

    def execute(self, process_owner) -> runtime.RuntimeRun:
        with self._lock:
            if self._consumed:
                raise DispatchError("E_CODEX_SDK_OPERATION_CONSUMED")
            self._consumed = True
        try:
            run = runtime.run_admitted_codex(
                self.request, self.selection, owner=process_owner,
                source_environment=dict(self._environment), authority=self.assert_current,
                deadline_monotonic=self.deadline, cancellation_probe=self._cancelled,
                started_at=self.started_at,
                capture_limit_bytes=self._capture_limit,
            )
            self.runtime_run = run  # Retain BEFORE materialization/readback can fail.
            return run
        finally:
            with self._lock:
                self._finished = True

    @property
    def recovery_max_bytes(self) -> int:
        return self._capture_limit + 6 * self._result_limit + 65_536

    def recovery_bytes(self) -> bytes:
        """Bounded diagnostic custody, NEVER a restorable observation or permit.

        Protocol streams may contain the full prompt and credentials: retain only
        their exact digest/length/truncation, never their bytes. Only scanned result
        data survives. The original creator-owned observation remains in memory.
        """
        run = self.runtime_run
        if (type(run) is not runtime.RuntimeRun or run.request != self.request
            or runtime.request_sha256(run.request, run.selection) != self._commitment):
            raise DispatchError("E_CODEX_SDK_RECOVERY_UNAVAILABLE")
        from process_supervision.process_runner import safe_serialize_result
        from process_supervision.sdk_worker import SdkWorkerObservation
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
        if observation is None:
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
            try:
                encoded = json_text(candidate).encode("utf-8")
                if observation.result is not None:
                    receiving.scan_execution_output(observation.result, run.output_context)
                if not isinstance(run.output_context, _owner().ProviderOutputContext):
                    raise ValueError("scan context unavailable")
                failure = _owner().provider_output_safety_scan_terminal(
                    "codex", run.output_context.needles, stdout=encoded, stderr=b"", serialized_line=False,
                )
                if failure is not None or json_text(self.request.prompt)[1:-1].encode("utf-8") in encoded:
                    raise ValueError("unsafe diagnostic output")
            except Exception:
                record["unsafeOutputOmitted"] = True
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
        failure = owner._provider_terminal_line_safety("codex", run.output_context.needles, line)
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


def _utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _prepare_dispatch(prevalidated, binding_path: Path, *, source_environment: dict[str, str],
                      cancellation_probe: Callable[[], bool],
                      runtime_namespace: Path | None = None) -> CodexReviewDispatch:
    """Read-only preparation; canonical runtime alone claims and settles a launch."""
    prepared_at = time.monotonic()
    _require_supported_platform()
    owner = _owner()
    if type(prevalidated) is not owner.PolicyBoundLaunch or not callable(cancellation_probe):
        raise DispatchError("E_CODEX_SDK_SELECTION_INVALID")
    c = prevalidated.control
    role = owner.external_role_provenance(c, "codex")
    flags, model, effort = owner.resolved_profile("codex", c.provider_flags)
    if (role.execution_role != "external-reviewer" or role != prevalidated.role_provenance
        or (tuple(flags), model, effort) != (prevalidated.flags, prevalidated.model, prevalidated.effort)
        or not c.ledger or not c.ledger_artifact or c.terminal_receipt is None
        or c.ledger_lane or c.ledger_closes or prevalidated.provenance is not None):
        raise DispatchError("E_CODEX_SDK_REVIEW_ONLY")
    # Direct callers must retain the same rule as the public CLI entrypoint.
    owner._qualify_managed_model_launch("codex", prevalidated, runtime_namespace=runtime_namespace)
    for index, flag in enumerate(flags):
        if flag == "--sandbox" and flags[index + 1] != "read-only":
            raise DispatchError("E_CODEX_SDK_REVIEW_ONLY")
    from process_supervision.process_runner import MAX_STDIN_BYTES
    if c.capture_max_bytes > MAX_STDIN_BYTES:
        raise DispatchError("E_CODEX_SDK_CAPTURE_LIMIT")
    if type(source_environment) is not dict or any(type(k) is not str or type(v) is not str for k, v in source_environment.items()):
        raise DispatchError("E_CODEX_SDK_ENVIRONMENT_INVALID")
    binding = read_binding(Path(binding_path))
    item = Path(c.ledger).resolve(strict=True)
    artifact = item / c.ledger_artifact
    receipt_target = c.terminal_receipt.resolve(strict=False)
    reserved = {item / "agent-runs.jsonl", item / "agent-runs.jsonl.lock"}
    if artifact == receipt_target or artifact in reserved or receipt_target in reserved:
        raise DispatchError("E_CODEX_SDK_OUTPUT_ALIAS")
    receiving.review_artifact_target(item, c.ledger_artifact, must_be_new=True)
    cwd = Path.cwd().resolve(strict=True)
    command, _expected = owner._resolve_launch_provider_command("codex", cwd)
    if len(command) != 1 or not Path(command[0]).is_absolute():
        raise DispatchError("E_CODEX_SDK_NATIVE_EXECUTABLE_REQUIRED")
    executable = Path(command[0])
    owner.validate_no_reparse_components(executable)
    digest = hashlib.sha256()
    with executable.open("rb") as stream:
        while block := stream.read(1_048_576):
            digest.update(block)
    home = Path(source_environment.get("CODEX_HOME") or Path.home() / ".codex").expanduser().resolve(strict=False)
    auth = owner.resolve_provider_auth_configuration("codex", dict(source_environment))
    options = owner.ledger_resource_options(c)
    selection = runtime.CodexRuntimeSelection(
        executable=str(executable), executable_sha256=digest.hexdigest(), codex_home=str(home),
        auth_mode=auth.mode, expected_account_email=binding["expectedAccountEmail"],
        work_item=str(item), ledger_max_events=int(options[1]) if options else None,
        ledger_max_bytes=int(options[3]) if options else None,
        job_memory_limit_bytes=binding["jobMemoryLimitBytes"],
        config_overrides=runtime.CODEX_BOUNDED_REVIEW_OVERRIDES,
        installed_hook_root=binding.get("installedHookRoot"),
    )
    raw = owner.prompt_bytes(c, external=True)
    request = runtime.prepare_codex_request(ExecutionRequest(
        work_item_id=item.name, provider="codex", external_dispatch_id="dispatch-" + secrets.token_hex(16),
        external_evidence_run_id="evidence-" + secrets.token_hex(16), artifact_id=binding["artifactIdentity"],
        role=role.assigned_role, model=model, effort=effort, cwd=str(cwd),
        account_binding=binding["accountBinding"], prompt=raw.decode("utf-8", errors="strict"),
        coordinator_binding=binding["coordinatorBinding"], scope=tuple(binding["scope"]),
        max_output_bytes=c.result_max_bytes, max_events=binding["maxEvents"],
    ))
    started = _utc_now()
    owner.prepare_ledger_admission(c, runtime.build_launch_arguments(request, selection, started_at=started))
    runtime._verify_runtime(selection)
    return CodexReviewDispatch(prevalidated, request, selection, source_environment,
                               cancellation_probe, started, prepared_at + c.timeout_secs, runtime_namespace)


def _require_supported_platform():
    # Refuse before hook trust or worker effects, not after a provider probe.
    if os.name != "nt":
        raise DispatchError("E_CODEX_SDK_WINDOWS_ONLY")


def prepare_dispatch(prevalidated, binding_path: Path, *, source_environment: dict[str, str],
                     cancellation_probe: Callable[[], bool],
                      runtime_namespace: Path | None = None) -> CodexReviewDispatch:
    try:
        return _prepare_dispatch(prevalidated, binding_path, source_environment=source_environment,
                                 cancellation_probe=cancellation_probe, runtime_namespace=runtime_namespace)
    except DispatchError:
        raise
    except (OSError, ValueError, TypeError, UnicodeError):
        raise DispatchError("E_CODEX_SDK_PREPARATION_FAILED") from None
