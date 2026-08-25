#!/usr/bin/env python3
"""Single synchronous owner for the work-items physical lifecycle V1.

The reusable API raises ``LifecycleError``.  Only ``main`` translates a failure
into a process exit code.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import contextvars
import errno
import functools
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import threading
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Iterable


README_BEGIN = "<!-- BEGIN GENERATED WORK-ITEMS STATUS -->"
README_END = "<!-- END GENERATED WORK-ITEMS STATUS -->"
TRIAL_OWNER = "work-items-lifecycle-v1-trial"
TRIAL_MARKER = ".work-items-lifecycle-v1-trial.json"
MIGRATION_OWNER = "work-items-lifecycle-v1-migration"
MIGRATION_SCHEMA_VERSION = 1
MIGRATION_DIGEST_ALGORITHMS = {
    "file": "sha256-file-bytes-v1",
    "directory": "sha256-tree-entries-v1",
}
V1_TERMINALIZATION_OWNER = "work-items-lifecycle-v1-terminalization"
V1_TERMINALIZATION_SCHEMA_VERSION = 2
V1_TERMINALIZATION_AUTHORIZATION = "operator-authorized-v1-terminalization"
V1_TERMINALIZATION_FAILURE = "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING"
LEGACY_RETIREMENT_OWNER = "work-items-lifecycle-v1-legacy-retirement"
LEGACY_RETIREMENT_SCHEMA_VERSION = 1
LEGACY_RETIREMENT_FILE = "legacy-retirement.json"
LEGACY_CLEANUP_OWNER = "work-items-lifecycle-v1-legacy-candidate-cleanup"
LEGACY_CLEANUP_SCHEMA_VERSION = 1
LEGACY_CLEANUP_FILE = "legacy-candidate-cleanup.json"
CURRENT_IDENTITY_NORMALIZATION_OWNER = "work-items-lifecycle-v1-current-identity-normalization"
CURRENT_IDENTITY_NORMALIZATION_SCHEMA_VERSION = 1
WORK_ITEM_SCHEMA_KEY = "Lifecycle-schema"
WORK_ITEM_SCHEMA_VALUE = "work-items-physical-v1"
WORK_ITEM_SCHEMA_MARKER = f"{WORK_ITEM_SCHEMA_KEY}: {WORK_ITEM_SCHEMA_VALUE}"
LEGACY_READ_CLASSIFICATION = "WI-LEGACY-READ-COMPAT"
README_SECTIONS = (
    "Current focus",
    "Next actions",
    "Blockers",
    "Roadmap and milestones",
    "Recently completed",
)
UTC_INSTANT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)*$")
OPTIONAL_RELATION_ABSENCE_MARKERS = frozenset({"none"})
FIELD_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\*\*)?([A-Za-z][A-Za-z0-9 -]*?)(?:\*\*)?\s*:\s*(.*?)\s*$"
)
DECISION_REQUIRED_FIELDS = (
    "id",
    "status",
    "date",
    "decided-by",
    "context",
    "supersedes",
    "superseded-by",
)
DECISION_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DECISION_LIST_FIELD_RE = re.compile(r"^- ([a-z][a-z0-9-]*):\s*(.*?)\s*$")
DECISION_V0_KEY_RE = re.compile(r"^([A-Za-z][A-Za-z0-9 _-]*):(?: (.*))?$")
DECISION_V0_ACTIVE_VALUE_PREFIXES = ("&", "*", "!", "[", "{", "|", ">")
DECISION_V0_MANIFEST = "decision-v0-compatibility.json"
DECISION_V0_MANIFEST_SCHEMA_VERSION = 1
DECISION_H1_PLAIN_FIELD_RE = re.compile(r"^([A-Za-z][A-Za-z0-9 _-]*): (.+)$")
DECISION_H1_BOLD_FIELD_RE = re.compile(r"^- \*\*([A-Za-z][A-Za-z0-9 _-]*):\*\* (.+)$")
DECISION_H1_MANIFEST = "decision-h1-compatibility.json"
DECISION_H1_MANIFEST_SCHEMA_VERSION = 1
DECISION_FORMAT_V1 = "canonical-list-v1"
DECISION_FORMAT_V0 = "legacy-yaml-v0"
DECISION_FORMAT_H1 = "legacy-markdown-h1-v0"
FENCED_CODE_OPEN_RE = re.compile(
    r"^ {0,3}(?P<fence>`{3,}|~{3,})(?P<info>[^\r\n]*)$"
)
WORK_ITEM_SCHEMA_OCCURRENCE_RE = re.compile(
    r"^\s*(?:-\s*)?(?:\*\*)?(lifecycle-schema)(?:\*\*)?\s*:\s*(.*?)\s*$",
    re.IGNORECASE,
)


class LifecycleError(RuntimeError):
    def __init__(self, failure_id: str, message: str):
        super().__init__(message)
        self.failure_id = failure_id


_AGENT_RUN_LEDGER_MODULE = None


def _load_agent_run_ledger():
    global _AGENT_RUN_LEDGER_MODULE
    if _AGENT_RUN_LEDGER_MODULE is not None:
        return _AGENT_RUN_LEDGER_MODULE
    path = Path(__file__).with_name("agent-run-ledger.py")
    spec = importlib.util.spec_from_file_location("work_item_agent_run_ledger", path)
    if spec is None or spec.loader is None:
        raise LifecycleError("WI-LEDGER-MIGRATION-CANDIDATE-INVALID", "ledger staging owner is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _AGENT_RUN_LEDGER_MODULE = module
    return module


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


LIFECYCLE_CLEANUP_PHASES = (
    "receipt-final",
    "receipt-pending",
    "rollback-parent-chain",
    "rollback-readme",
    "rollback-status:work-item:2026-08-11-pr600-review-fix",
    "rollback-status:work-item:2026-08-11-pr598-review-fix",
    "rollback-postcheck",
    "transaction-release",
)


def _lifecycle_sanitize_diagnostic(value: object) -> str:
    diagnostic = " ".join(str(value).split())[:512]
    diagnostic = re.sub(
        r"(?i)\b[A-Z]:[\\/][^\s;]+",
        "<redacted-path>",
        diagnostic,
    )
    return diagnostic


@dataclass(frozen=True)
class LifecycleCleanupFailure:
    phase: str
    failure_id: str
    resource: str | None
    diagnostic: str
    cause_type: str | None


@dataclass(frozen=True)
class LifecycleOutcomeBundle:
    result: object | None
    primary: BaseException | None
    cleanup_failures: tuple[LifecycleCleanupFailure, ...]
    rollback: str


@dataclass(frozen=True)
class LifecycleDiagnosticCleanupFailure:
    phase: str
    failureId: str
    resource: str | None
    diagnostic: str
    causeType: str | None


@dataclass(frozen=True)
class LifecycleDiagnosticBundle:
    primaryKind: str
    primaryFailureId: str | None
    primaryType: str | None
    topLevelKind: str
    topLevelFailureId: str | None
    rollback: str
    cleanupFailures: tuple[LifecycleDiagnosticCleanupFailure, ...]


@dataclass(frozen=True)
class LifecycleDiagnosticDeliveryFailure:
    failure_id: str
    diagnostic: str


class LifecycleOutcomeComposer:
    """Transport-neutral owner of one primary and the fixed cleanup slots."""

    def __init__(self):
        self._result: object | None = None
        self._primary: BaseException | None = None
        self._cleanup: dict[str, LifecycleCleanupFailure] = {}
        self._rollback = "not-needed"

    def propose_result(self, result: object) -> None:
        self._result = result

    def capture_primary(self, primary: BaseException) -> None:
        if self._primary is None:
            self._primary = primary

    def record_cleanup(
        self,
        *,
        phase: str,
        failure_id: str,
        resource: str | None,
        diagnostic: object,
        cause: BaseException | None = None,
    ) -> None:
        if phase not in LIFECYCLE_CLEANUP_PHASES:
            raise ValueError(f"unknown lifecycle cleanup phase: {phase}")
        if phase in self._cleanup:
            raise ValueError(f"lifecycle cleanup phase already recorded: {phase}")
        self._cleanup[phase] = LifecycleCleanupFailure(
            phase=phase,
            failure_id=failure_id,
            resource=resource,
            diagnostic=_lifecycle_sanitize_diagnostic(diagnostic),
            cause_type=type(cause).__name__ if cause is not None else None,
        )

    def set_rollback(self, rollback: str) -> None:
        if rollback not in {"not-needed", "completed", "incomplete"}:
            raise ValueError(f"invalid rollback state: {rollback}")
        self._rollback = rollback

    def finalize(self) -> LifecycleOutcomeBundle:
        cleanup = tuple(
            self._cleanup[phase]
            for phase in LIFECYCLE_CLEANUP_PHASES
            if phase in self._cleanup
        )
        return LifecycleOutcomeBundle(
            result=self._result,
            primary=self._primary,
            cleanup_failures=cleanup,
            rollback=self._rollback,
        )

    @staticmethod
    def top_level(bundle: LifecycleOutcomeBundle) -> BaseException | None:
        if bundle.primary is not None:
            return bundle.primary
        if bundle.cleanup_failures:
            cleanup = bundle.cleanup_failures[0]
            return LifecycleError(cleanup.failure_id, cleanup.diagnostic)
        return None


def _lifecycle_diagnostic_bundle(
    bundle: LifecycleOutcomeBundle,
) -> LifecycleDiagnosticBundle:
    primary = bundle.primary
    if primary is None:
        primary_kind = "none"
        primary_failure_id = None
        primary_type = None
    elif isinstance(primary, LifecycleError):
        primary_kind = "typed"
        primary_failure_id = primary.failure_id
        primary_type = type(primary).__name__
    elif isinstance(
        primary,
        (asyncio.CancelledError, KeyboardInterrupt, SystemExit, GeneratorExit),
    ):
        primary_kind = "control-flow"
        primary_failure_id = None
        primary_type = type(primary).__name__
    else:
        primary_kind = "unexpected"
        primary_failure_id = None
        primary_type = type(primary).__name__
    if primary is not None:
        top_level_kind = f"{primary_kind}-primary"
        top_level_failure_id = primary_failure_id
    elif bundle.cleanup_failures:
        top_level_kind = "cleanup-only"
        top_level_failure_id = bundle.cleanup_failures[0].failure_id
    else:
        top_level_kind = "result"
        top_level_failure_id = None
    return LifecycleDiagnosticBundle(
        primaryKind=primary_kind,
        primaryFailureId=primary_failure_id,
        primaryType=primary_type,
        topLevelKind=top_level_kind,
        topLevelFailureId=top_level_failure_id,
        rollback=bundle.rollback,
        cleanupFailures=tuple(
            LifecycleDiagnosticCleanupFailure(
                phase=record.phase,
                failureId=record.failure_id,
                resource=record.resource,
                diagnostic=record.diagnostic,
                causeType=record.cause_type,
            )
            for record in bundle.cleanup_failures
        ),
    )


class LifecycleDiagnosticObserver:
    """Concrete invocation-scoped one-shot structured diagnostic mailbox."""

    def __init__(self, *, _reject_delivery: bool = False):
        self._mutex = threading.Lock()
        self._state = "empty"
        self._correlation = None
        self._snapshot = None
        self._delivery_failure = None
        self._delivery_attempts = 0
        self._reject_delivery = bool(_reject_delivery)

    @property
    def state(self) -> str:
        with self._mutex:
            return self._state

    @property
    def snapshot(self) -> LifecycleDiagnosticBundle | None:
        with self._mutex:
            return self._snapshot

    @property
    def delivery_failure(self) -> LifecycleDiagnosticDeliveryFailure | None:
        with self._mutex:
            return self._delivery_failure

    @property
    def delivery_attempts(self) -> int:
        with self._mutex:
            return self._delivery_attempts

    def _claim(self) -> object:
        with self._mutex:
            if self._state != "empty":
                raise TypeError("diagnostic_observer must be empty")
            correlation = object()
            self._correlation = correlation
            self._state = "claimed"
            return correlation

    def _deliver(
        self,
        correlation: object,
        bundle: LifecycleOutcomeBundle,
    ) -> bool:
        with self._mutex:
            if self._state != "claimed":
                return False
            self._delivery_attempts += 1
            if correlation is not self._correlation or self._reject_delivery:
                self._state = "delivery-failed"
                self._delivery_failure = LifecycleDiagnosticDeliveryFailure(
                    failure_id="WI-LIFECYCLE-DIAGNOSTIC-DELIVERY",
                    diagnostic="lifecycle diagnostic delivery was rejected",
                )
                self._correlation = None
                return False
            self._snapshot = _lifecycle_diagnostic_bundle(bundle)
            self._state = "delivered"
            self._correlation = None
            return True

    def _mark_not_needed(self, correlation: object) -> bool:
        with self._mutex:
            if self._state != "claimed" or correlation is not self._correlation:
                return False
            self._state = "not-needed"
            self._correlation = None
            return True


LIFECYCLE_LOCK_BYTES = b"work-items-lifecycle-owner-v1\n"
LIFECYCLE_LOCK_RELATIVE = Path(".scratch") / "work-items-lifecycle-owner.lock"


def _lifecycle_file_identity(info: os.stat_result) -> tuple[int, int]:
    return info.st_dev, info.st_ino


def _lifecycle_path_has_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    return path.is_symlink() or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _lifecycle_unresolved_absolute(path: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else Path.cwd() / path


def _lifecycle_reject_unreduced_reparse(
    path: Path,
    *,
    failure_id: str,
    message: str,
) -> None:
    """Inspect every caller-supplied path participant without resolving links."""
    candidate = _lifecycle_unresolved_absolute(path)
    cursor = Path(candidate.anchor)
    for part in candidate.parts[1:]:
        if part in {"", "."}:
            continue
        if part == "..":
            cursor = cursor.parent
            continue
        cursor /= part
        try:
            info = cursor.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise LifecycleError(failure_id, message) from exc
        if stat.S_ISLNK(info.st_mode) or bool(
            getattr(info, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        ):
            raise LifecycleError(failure_id, message)


class LifecycleTransaction:
    """One fail-fast native lock for a repository's physical lifecycle."""

    def __init__(self, root: Path):
        _lifecycle_reject_unreduced_reparse(
            root,
            failure_id="WI-LIFECYCLE-LOCK-IDENTITY",
            message="lifecycle root or parent is a link or reparse point",
        )
        resolved = root.resolve()
        self.repository_root = resolved.parent if resolved.name == "work-items" else resolved
        self.path = self.repository_root / LIFECYCLE_LOCK_RELATIVE
        self._file = None
        self._identity: tuple[int, int] | None = None
        self._locked = False

    def _ensure_lock_file(self) -> None:
        scratch = self.path.parent
        scratch.mkdir(parents=True, exist_ok=True)
        if _lifecycle_path_has_reparse(scratch):
            raise LifecycleError(
                "WI-LIFECYCLE-LOCK-IDENTITY",
                "lifecycle lock parent is a link or reparse point",
            )
        if self.path.exists():
            if _lifecycle_path_has_reparse(self.path) or not self.path.is_file():
                raise LifecycleError(
                    "WI-LIFECYCLE-LOCK-IDENTITY",
                    "lifecycle lock path is not a regular non-reparse file",
                )
            return
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".work-items-lifecycle-owner.lock.init-",
            dir=scratch,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as stream:
                stream.write(LIFECYCLE_LOCK_BYTES)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, self.path)
            except FileExistsError:
                pass
            except OSError as exc:
                raise LifecycleError(
                    "WI-LIFECYCLE-LOCK-UNSUPPORTED",
                    "filesystem cannot atomically initialize lifecycle lock",
                ) from exc
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def _native_lock(self) -> None:
        assert self._file is not None
        try:
            if os.name == "nt":
                import msvcrt

                self._file.seek(0)
                msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK, errno.EPERM}:
                raise LifecycleError(
                    "WI-LIFECYCLE-LOCK-HELD",
                    "another lifecycle owner holds the transaction lock",
                ) from exc
            raise LifecycleError(
                "WI-LIFECYCLE-LOCK-UNSUPPORTED",
                "native non-blocking lifecycle locking is unavailable",
            ) from exc
        self._locked = True

    def _native_unlock(self) -> None:
        assert self._file is not None
        if os.name == "nt":
            import msvcrt

            self._file.seek(0)
            msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        self._locked = False

    def verify(self) -> None:
        if not self._locked or self._file is None or self._identity is None:
            raise LifecycleError(
                "WI-LIFECYCLE-LOCK-IDENTITY",
                "lifecycle transaction is not held",
            )
        try:
            handle = os.fstat(self._file.fileno())
            current = self.path.stat()
        except OSError as exc:
            raise LifecycleError(
                "WI-LIFECYCLE-LOCK-IDENTITY",
                "lifecycle lock identity cannot be revalidated",
            ) from exc
        if (
            _lifecycle_file_identity(handle) != self._identity
            or _lifecycle_file_identity(current) != self._identity
            or handle.st_size != len(LIFECYCLE_LOCK_BYTES)
            or _lifecycle_path_has_reparse(self.path)
        ):
            raise LifecycleError(
                "WI-LIFECYCLE-LOCK-IDENTITY",
                "lifecycle lock handle/path identity changed",
            )

    def __enter__(self) -> "LifecycleTransaction":
        self._ensure_lock_file()
        flags = os.O_RDWR | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(self.path, flags)
            self._file = os.fdopen(descriptor, "r+b", closefd=True)
            self._native_lock()
            handle = os.fstat(self._file.fileno())
            self._identity = _lifecycle_file_identity(handle)
            self.verify()
            self._file.seek(0)
            if self._file.read() != LIFECYCLE_LOCK_BYTES:
                raise LifecycleError(
                    "WI-LIFECYCLE-LOCK-IDENTITY",
                    "lifecycle lock bytes differ",
                )
            return self
        except BaseException:
            if self._file is not None:
                if self._locked:
                    try:
                        self._native_unlock()
                    except OSError:
                        pass
                self._file.close()
                self._file = None
            raise

    def __exit__(self, exc_type, exc, traceback) -> bool:
        release_error: BaseException | None = None
        try:
            self.verify()
            self._native_unlock()
        except BaseException as candidate:
            release_error = candidate
        finally:
            if self._file is not None:
                self._file.close()
                self._file = None
        if release_error is not None:
            if isinstance(release_error, LifecycleError):
                raise release_error
            raise LifecycleError(
                "WI-LIFECYCLE-LOCK-IDENTITY",
                "lifecycle lock release failed",
            ) from release_error
        return False


_CURRENT_LIFECYCLE_TRANSACTION: contextvars.ContextVar[
    LifecycleTransaction | None
] = contextvars.ContextVar("work_items_lifecycle_transaction", default=None)
_CURRENT_LIFECYCLE_OUTCOME_COMPOSER: contextvars.ContextVar[
    LifecycleOutcomeComposer | None
] = contextvars.ContextVar("work_items_lifecycle_outcome_composer", default=None)


def _lifecycle_participant(function):
    @functools.wraps(function)
    def wrapper(root: Path, *args, **kwargs):
        diagnostic_observer = kwargs.pop("diagnostic_observer", None)
        if diagnostic_observer is not None and type(diagnostic_observer) is not LifecycleDiagnosticObserver:
            raise TypeError(
                "diagnostic_observer must be an exact LifecycleDiagnosticObserver"
            )
        current = _CURRENT_LIFECYCLE_TRANSACTION.get()
        current_composer = _CURRENT_LIFECYCLE_OUTCOME_COMPOSER.get()
        if current is not None:
            if diagnostic_observer is not None:
                raise TypeError("nested lifecycle calls cannot claim a second observer")
            if current_composer is None:
                raise LifecycleError(
                    "WI-LIFECYCLE-LOCK-IDENTITY",
                    "nested lifecycle call has no outcome composer",
                )
            _lifecycle_reject_unreduced_reparse(
                Path(root),
                failure_id="WI-LIFECYCLE-LOCK-IDENTITY",
                message="lifecycle root or parent is a link or reparse point",
            )
            resolved = Path(root).resolve()
            repository_root = resolved.parent if resolved.name == "work-items" else resolved
            if current.repository_root != repository_root:
                raise LifecycleError(
                    "WI-LIFECYCLE-LOCK-IDENTITY",
                    "nested lifecycle call targets a different repository",
                )
            current.verify()
            return function(root, *args, **kwargs)

        correlation = (
            diagnostic_observer._claim()
            if diagnostic_observer is not None
            else None
        )
        composer = LifecycleOutcomeComposer()
        transaction = None
        transaction_token = None
        composer_token = _CURRENT_LIFECYCLE_OUTCOME_COMPOSER.set(composer)
        entered = False
        try:
            _lifecycle_reject_unreduced_reparse(
                Path(root),
                failure_id="WI-LIFECYCLE-LOCK-IDENTITY",
                message="lifecycle root or parent is a link or reparse point",
            )
            transaction = LifecycleTransaction(Path(root))
            transaction.__enter__()
            entered = True
            transaction_token = _CURRENT_LIFECYCLE_TRANSACTION.set(transaction)
            try:
                composer.propose_result(function(root, *args, **kwargs))
            except BaseException as exc:
                composer.capture_primary(exc)
        except BaseException as exc:
            composer.capture_primary(exc)
        finally:
            if transaction_token is not None:
                _CURRENT_LIFECYCLE_TRANSACTION.reset(transaction_token)
            if entered and transaction is not None:
                try:
                    transaction.__exit__(None, None, None)
                except BaseException as exc:
                    composer.record_cleanup(
                        phase="transaction-release",
                        failure_id="WI-LIFECYCLE-LOCK-IDENTITY",
                        resource=".scratch/work-items-lifecycle-owner.lock",
                        diagnostic="lifecycle transaction release failed",
                        cause=exc,
                    )
            _CURRENT_LIFECYCLE_OUTCOME_COMPOSER.reset(composer_token)

        bundle = composer.finalize()
        top_level = composer.top_level(bundle)
        if diagnostic_observer is not None:
            if top_level is None:
                diagnostic_observer._mark_not_needed(correlation)
            else:
                diagnostic_observer._deliver(correlation, bundle)
        if top_level is not None:
            raise top_level
        result = bundle.result
        if isinstance(result, PartialRecoveryCommittedCandidate):
            return result.result
        return result

    wrapper.__lifecycle_transaction_participant__ = True
    return wrapper


@dataclass(frozen=True)
class Category:
    name: str
    current_root: str
    current_kind: str
    current_statuses: frozenset[str]
    terminal_statuses: frozenset[str]


CATEGORIES = {
    "work-item": Category(
        "work-item",
        "",
        "work-item",
        frozenset({"candidate", "active", "blocked"}),
        frozenset({"closed", "cancelled", "completed"}),
    ),
    "bug": Category(
        "bug",
        "bugs",
        "flat",
        frozenset({"open", "triaged", "accepted"}),
        frozenset({"fixed", "resolved", "refuted", "superseded", "closed"}),
    ),
    "decision": Category(
        "decision",
        "decisions",
        "flat",
        frozenset({"proposed", "accepted"}),
        frozenset({"dropped", "superseded", "reverted", "no-longer-governing"}),
    ),
    "lesson": Category(
        "lesson",
        "lessons",
        "flat",
        frozenset({"open", "applied"}),
        frozenset({"dropped", "superseded", "archived"}),
    ),
    "roadmap": Category(
        "roadmap",
        "roadmaps",
        "flat",
        frozenset({"draft", "active"}),
        frozenset({"superseded", "archived"}),
    ),
    "epic": Category(
        "epic",
        "epics",
        "flat",
        frozenset({"active"}),
        frozenset({"closed", "cancelled", "archived"}),
    ),
}
CATEGORY_ALIASES = {
    "work-items": "work-item",
    "workitem": "work-item",
    "bugs": "bug",
    "decisions": "decision",
    "lessons": "lesson",
    "roadmaps": "roadmap",
    "epics": "epic",
}


@dataclass
class ReadmeEntry:
    section: str
    logical_reference: str
    label: str
    link: Path
    checked: bool
    detail: str = ""
    source_paths: list[Path] = field(default_factory=list)
    classification: str | None = None


@dataclass(frozen=True)
class CategoryAdmission:
    category: str
    current_reader: str
    terminal_validator: str
    utc_field_owner: str
    negative_fixture: str
    utc_field: str
    detail_field: str
    evidence_field: str


@dataclass(frozen=True)
class ScratchDisposition:
    original: Path
    tombstone: Path
    disposition: str
    proof: dict | None
    canonical_pointer: Path
    snapshot: object | None


BUG_DISPOSITIONS_MANIFEST = "bug-dispositions.json"
BUG_DISPOSITIONS_RECEIPT = "bug-dispositions-receipt.json"
BUG_DISPOSITIONS_SCHEMA_VERSION = 1
BUG_DISPOSITIONS_OWNER = "mutate-work-item:close-item-bug-dispositions-v1"
SHA256_RE = re.compile(r"[0-9a-f]{64}")
BUG_DISPOSITION_ACTIONS = {"terminalize", "preserve-current"}
BUG_DISPOSITION_TEXT_LIMIT = 2048


@dataclass(frozen=True)
class BugDispositionPlan:
    bug_id: str
    action: str
    source: Path
    target: Path | None
    before: bytes
    after: bytes
    status_before: str
    status_after: str


@dataclass(frozen=True)
class PartialRecoveryTarget:
    reference: str
    inventory_tree_preimage: str
    status_preimage: str
    status_afterimage: str
    projected_tree_afterimage: str
    closure_sha256: str


@dataclass(frozen=True)
class PartialRecoveryResult:
    receipt_sha256: str
    audit: str
    replay: bool


@dataclass(frozen=True)
class PartialRecoveryCommittedCandidate:
    result: PartialRecoveryResult


@dataclass(frozen=True)
class CapturedPathParentChain:
    participants: tuple[tuple[Path, tuple[int, int]], ...]


@dataclass(frozen=True)
class CapturedFileSnapshot:
    path: Path
    identity: tuple[int, int]
    length: int
    data: bytes
    parent_chain: CapturedPathParentChain


PARTIAL_MIGRATION_RECOVERY_INVENTORY_SHA256 = (
    "909A56FDBE1EC62A7D28B76D7FC682F1618B5956CCA501E525E89C3BC19E622C"
)
PARTIAL_MIGRATION_RECOVERY_README_PREIMAGE_SHA256 = (
    "37AFA08CF7DEC3ECF3A37324A1CABF093CB12C52152A576FDE11F5889E0076C8"
)
PARTIAL_MIGRATION_RECOVERY_TARGETS = {
    "work-item:2026-08-11-pr598-review-fix": PartialRecoveryTarget(
        reference="work-item:2026-08-11-pr598-review-fix",
        inventory_tree_preimage="D952DAEE21E51353687631ED179AA9EFDF0B1B562AF6344996FCDF3FCFB01C25",
        status_preimage="0E6032B6DCE98B4AA2D4F320FB0935C98802966AB4256E81DFB2150EB0FEB263",
        status_afterimage="D9FEB4DA7C0654845B83607EBC62BC065C3C96A0252DEA439AFAAB2E777EA190",
        projected_tree_afterimage="996F678C1F87898EFFE46EF9DFF413C6CA47A827AD398724224B03D5FD840E7B",
        closure_sha256="577777AAA5690F61D454503102321EBD101C2D5BDBEFADF9CF075CCCC645EDE7",
    ),
    "work-item:2026-08-11-pr600-review-fix": PartialRecoveryTarget(
        reference="work-item:2026-08-11-pr600-review-fix",
        inventory_tree_preimage="8391722DFCD41A5C177D88D73FBE2DE7AD2DE1C0BB07D526DF7354DCD16D4D80",
        status_preimage="FBAB061063D35B03425E54EADB17EA3630606FE7B00EECEBC44361A02677FB14",
        status_afterimage="0F1987414B50461CC5F810DA7BF28458054A5D34ED9B7D8DE25A64BBBB678749",
        projected_tree_afterimage="5E67E1A549CD60A2BC67887631B5C3AA9F17E0AC8D78262EE335E959F2FF06BD",
        closure_sha256="30FA23A908E529D763A63A07FB69BF748692BC0BA1A2606D34EE718630F89998",
    ),
}
PARTIAL_MIGRATION_RECOVERY_UNCHANGED_ROWS = {
    "bug:2026-07-25-cleanup-aggressive-exe-extension-index-out-of-range-panic": (
        "ABCA21DC053115D00C0AB7C830204E9DE440A08A53486ABE52F9873044839CCE"
    ),
    "bug:2026-07-26-route-daemon-state-read-unhardened-parent-fallback-writes-hub-mcp-log": (
        "D2DD54B20F24CE36B572F3BF7108B5CFC60974971D22AC3B47DD1BD24F517ABF"
    ),
}


def _work_items_root(root: Path) -> Path:
    root = root.resolve()
    return root if root.name == "work-items" else root / "work-items"


def is_valid_slug(slug: str) -> bool:
    """Return whether *slug* satisfies the canonical lifecycle identity grammar."""
    return isinstance(slug, str) and SLUG_RE.fullmatch(slug) is not None


def _validate_slug(slug: str) -> None:
    if not is_valid_slug(slug):
        raise LifecycleError("WI-INVALID-SLUG", f"invalid bare slug: {slug!r}")


def _authoritative_markdown_lines(text: str) -> Iterable[tuple[int, str]]:
    """Yield positioned Markdown lines that can own lifecycle fields.

    Fenced code is evidence/content, not record metadata.  Reject an opened
    fence without a valid close so malformed Markdown cannot silently widen or
    shrink the authoritative field surface.
    """
    fence_char: str | None = None
    fence_length = 0
    for line_number, line in enumerate(text.splitlines(), start=1):
        if fence_char is not None:
            closing = re.fullmatch(
                rf" {{0,3}}{re.escape(fence_char)}{{{fence_length},}}[ \t]*",
                line,
            )
            if closing:
                fence_char = None
                fence_length = 0
            continue

        opening = FENCED_CODE_OPEN_RE.fullmatch(line)
        if opening:
            fence = opening.group("fence")
            info = opening.group("info")
            if fence[0] == "`" and "`" in info:
                yield line_number, line
                continue
            fence_char = fence[0]
            fence_length = len(fence)
            continue
        yield line_number, line

    if fence_char is not None:
        raise LifecycleError(
            "WI-CATEGORY-MARKDOWN-INVALID",
            "unterminated fenced code block in lifecycle record",
        )


def _authoritative_field_occurrences(
    text: str,
) -> tuple[tuple[int, str, str, str], ...]:
    occurrences: list[tuple[int, str, str, str]] = []
    for line_number, line in _authoritative_markdown_lines(text):
        match = FIELD_RE.fullmatch(line)
        if match:
            occurrences.append(
                (
                    line_number,
                    match.group(1).strip().casefold(),
                    match.group(2).strip(),
                    line,
                )
            )
    return tuple(occurrences)


def _parse_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for _line_number, name, value, _line in _authoritative_field_occurrences(text):
        fields[name] = value
    return fields


@dataclass(frozen=True)
class CurrentDecisionRecord:
    format: str
    fields: Mapping[str, str | tuple[str, ...]]
    raw_status: str
    admitted_current_status: str | None
    body_offset: int
    legacy_read_only: bool


@dataclass(frozen=True)
class DecisionCompatibilityProfile:
    label: str
    format: str
    manifest_name: str
    manifest_schema_version: int
    anchor_manifest_field: str
    anchor_baseline_field: str
    anchor_cutover_field: str
    manifest_missing_failure_id: str
    manifest_invalid_failure_id: str
    unadmitted_failure_id: str
    manifest_stale_failure_id: str
    hash_mismatch_failure_id: str
    retired_reappeared_failure_id: str
    validate_record: Callable[[Path, str, str], CurrentDecisionRecord]


def _read_current_decision_text(path: Path, slug: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise LifecycleError(
            "WI-DECISION-SCHEMA-INVALID",
            f"decision:{slug} must be UTF-8",
        ) from exc


def _current_decision_format(text: str, slug: str) -> str:
    lines = text.splitlines()
    first = lines[0] if lines else ""
    if first.startswith("- "):
        return DECISION_FORMAT_V1
    if first == "---":
        return DECISION_FORMAT_V0
    if first.startswith("# ") and first[2:].strip():
        return DECISION_FORMAT_H1
    raise LifecycleError(
        "WI-DECISION-FORMAT-UNSUPPORTED",
        f"decision:{slug} has an unsupported first-line format",
    )


def _decision_filename_date_suffix(slug: str) -> tuple[str, str]:
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})-(.+)", slug)
    if match is None:
        raise LifecycleError(
            "WI-DECISION-IDENTITY-MISMATCH",
            f"decision:{slug} requires a dated filename with a non-empty suffix",
        )
    date_value, suffix = match.groups()
    try:
        parsed = datetime.strptime(date_value, "%Y-%m-%d")
    except ValueError as exc:
        raise LifecycleError(
            "WI-DECISION-IDENTITY-MISMATCH",
            f"decision:{slug} has an invalid filename date",
        ) from exc
    if parsed.strftime("%Y-%m-%d") != date_value:
        raise LifecycleError(
            "WI-DECISION-IDENTITY-MISMATCH",
            f"decision:{slug} has an invalid filename date",
        )
    return date_value, suffix


def _immutable_decision_fields(
    fields: dict[str, str | tuple[str, ...]],
) -> Mapping[str, str | tuple[str, ...]]:
    return MappingProxyType(dict(fields))


def _validate_current_decision_v1(text: str, slug: str) -> CurrentDecisionRecord:
    lines = text.splitlines()
    heading_index = next(
        (index for index, line in enumerate(lines) if line.startswith("#")),
        None,
    )
    if heading_index is None or not (
        re.match(r"^#\s+\S", lines[heading_index])
        or lines[heading_index] == "## Decision"
    ):
        raise LifecycleError(
            "WI-DECISION-SCHEMA-INVALID",
            f"decision:{slug} requires leading list metadata before its first body heading",
        )

    leading_occurrences: dict[str, tuple[int, str]] = {}
    previous_field = False
    for line_number, line in enumerate(lines[:heading_index], start=1):
        if not line.strip():
            previous_field = False
            continue
        match = DECISION_LIST_FIELD_RE.fullmatch(line)
        if match:
            name = match.group(1).strip().casefold()
            if name in leading_occurrences:
                raise LifecycleError(
                    "WI-DECISION-FIELD-DUPLICATE",
                    f"decision:{slug} duplicates leading field '{name}'",
                )
            leading_occurrences[name] = (line_number, match.group(2).strip())
            previous_field = True
            continue
        if FIELD_RE.fullmatch(line):
            raise LifecycleError(
                "WI-DECISION-SCHEMA-INVALID",
                f"decision:{slug} has a non-list metadata field at line {line_number}",
            )
        if line[:1].isspace() and previous_field:
            continue
        previous_field = False

    occurrences = _authoritative_field_occurrences(text)
    for required in DECISION_REQUIRED_FIELDS:
        matches = [
            (line_number, value)
            for line_number, name, value, _line in occurrences
            if name == required
        ]
        if len(matches) > 1:
            raise LifecycleError(
                "WI-DECISION-FIELD-DUPLICATE",
                f"decision:{slug} duplicates required field '{required}'",
            )
        leading = leading_occurrences.get(required)
        if len(matches) != 1 or leading is None or matches[0][0] != leading[0] or not leading[1]:
            raise LifecycleError(
                "WI-DECISION-SCHEMA-INVALID",
                f"decision:{slug} requires one non-empty leading '{required}' field",
            )

    fields = {name: value for name, (_line_number, value) in leading_occurrences.items()}
    if fields["id"] != slug:
        raise LifecycleError(
            "WI-DECISION-IDENTITY-MISMATCH",
            f"decision:{slug} id does not match its filename",
        )
    date_value = fields["date"]
    try:
        parsed_date = datetime.strptime(date_value, "%Y-%m-%d")
    except ValueError as exc:
        raise LifecycleError(
            "WI-DECISION-IDENTITY-MISMATCH",
            f"decision:{slug} date must be a real YYYY-MM-DD value",
        ) from exc
    if (
        not DECISION_DATE_RE.fullmatch(date_value)
        or parsed_date.strftime("%Y-%m-%d") != date_value
        or not slug.startswith(f"{date_value}-")
    ):
        raise LifecycleError(
            "WI-DECISION-IDENTITY-MISMATCH",
            f"decision:{slug} date does not match its filename prefix",
        )
    if fields["status"] not in CATEGORIES["decision"].current_statuses:
        raise LifecycleError(
            "WI-DECISION-SCHEMA-INVALID",
            f"decision:{slug} has unsupported current status '{fields['status']}'",
        )
    raw_lines = text.splitlines(keepends=True)
    body_offset = len("".join(raw_lines[:heading_index]).encode("utf-8"))
    return CurrentDecisionRecord(
        format=DECISION_FORMAT_V1,
        fields=_immutable_decision_fields(fields),
        raw_status=fields["status"],
        admitted_current_status=fields["status"],
        body_offset=body_offset,
        legacy_read_only=False,
    )


def _normalize_decision_v0_key(key: str) -> str:
    return re.sub(r"[ _-]+", "-", key.casefold())


def _reject_decision_v0_active_value(slug: str, line_number: int, value: str) -> None:
    if value.startswith(DECISION_V0_ACTIVE_VALUE_PREFIXES):
        raise LifecycleError(
            "WI-DECISION-V0-UNSUPPORTED-NESTING",
            f"decision:{slug} has an active YAML value at line {line_number}",
        )


def _validate_current_decision_v0(
    text: str,
    slug: str,
    *,
    v0_cutover_date: str | None,
) -> CurrentDecisionRecord:
    logical_lines = text.splitlines()
    closing_index = next(
        (index for index, line in enumerate(logical_lines[1:], start=1) if line == "---"),
        None,
    )
    if closing_index is None:
        raise LifecycleError(
            "WI-DECISION-V0-SCHEMA-INVALID",
            f"decision:{slug} has no exact closing frontmatter delimiter",
        )
    header = logical_lines[1:closing_index]
    if not header:
        raise LifecycleError(
            "WI-DECISION-V0-SCHEMA-INVALID",
            f"decision:{slug} has an empty V0 header",
        )
    body = "\n".join(logical_lines[closing_index + 1 :])
    if not body.strip():
        raise LifecycleError(
            "WI-DECISION-V0-SCHEMA-INVALID",
            f"decision:{slug} has an empty V0 body",
        )

    fields: dict[str, str | tuple[str, ...]] = {}
    normalized_keys: dict[str, str] = {}
    pending_sequence_key: str | None = None
    sequence_values: list[str] = []

    def finish_pending(line_number: int) -> None:
        nonlocal pending_sequence_key, sequence_values
        if pending_sequence_key is None:
            return
        if not sequence_values:
            raise LifecycleError(
                "WI-DECISION-V0-SCHEMA-INVALID",
                f"decision:{slug} has an empty sequence field before line {line_number}",
            )
        fields[pending_sequence_key] = tuple(sequence_values)
        pending_sequence_key = None
        sequence_values = []

    for line_number, line in enumerate(header, start=2):
        if not line or "\t" in line:
            raise LifecycleError(
                "WI-DECISION-V0-SCHEMA-INVALID",
                f"decision:{slug} has a blank or tab-bearing header line {line_number}",
            )
        if line.startswith("  - "):
            value = line[4:]
            if pending_sequence_key is None or not value:
                raise LifecycleError(
                    "WI-DECISION-V0-UNSUPPORTED-NESTING",
                    f"decision:{slug} has an unsupported sequence at line {line_number}",
                )
            _reject_decision_v0_active_value(slug, line_number, value)
            sequence_values.append(value)
            continue
        if line.startswith("- "):
            raise LifecycleError(
                "WI-DECISION-V0-SCHEMA-INVALID",
                f"decision:{slug} has a V1 list field inside V0 at line {line_number}",
            )
        if line[:1].isspace():
            raise LifecycleError(
                "WI-DECISION-V0-UNSUPPORTED-NESTING",
                f"decision:{slug} has unsupported indentation at line {line_number}",
            )
        finish_pending(line_number)
        match = DECISION_V0_KEY_RE.fullmatch(line)
        if match is None:
            raise LifecycleError(
                "WI-DECISION-V0-SCHEMA-INVALID",
                f"decision:{slug} has an invalid V0 field at line {line_number}",
            )
        key = match.group(1)
        if key != key.strip():
            raise LifecycleError(
                "WI-DECISION-V0-SCHEMA-INVALID",
                f"decision:{slug} has an invalid V0 key at line {line_number}",
            )
        normalized = _normalize_decision_v0_key(key)
        if normalized in normalized_keys:
            raise LifecycleError(
                "WI-DECISION-V0-FIELD-DUPLICATE",
                f"decision:{slug} duplicates V0 key '{key}' at line {line_number}",
            )
        normalized_keys[normalized] = key
        value = match.group(2)
        if value is None or value == "":
            pending_sequence_key = key
            sequence_values = []
            continue
        if value.startswith(" "):
            raise LifecycleError(
                "WI-DECISION-V0-SCHEMA-INVALID",
                f"decision:{slug} has an invalid scalar at line {line_number}",
            )
        _reject_decision_v0_active_value(slug, line_number, value)
        fields[key] = value
    finish_pending(closing_index + 1)

    raw_status = fields.get("status")
    if not isinstance(raw_status, str) or not raw_status:
        raise LifecycleError(
            "WI-DECISION-V0-SCHEMA-INVALID",
            f"decision:{slug} requires one non-empty exact status field",
        )
    filename_date, suffix = _decision_filename_date_suffix(slug)
    identity = fields.get("id")
    if identity is not None and identity != slug:
        raise LifecycleError(
            "WI-DECISION-IDENTITY-MISMATCH",
            f"decision:{slug} V0 id does not match its full filename stem",
        )
    legacy_slug = fields.get("slug")
    if legacy_slug is not None and legacy_slug != suffix:
        raise LifecycleError(
            "WI-DECISION-IDENTITY-MISMATCH",
            f"decision:{slug} V0 slug does not match its undated filename suffix",
        )
    date_value = fields.get("date")
    if date_value is not None and date_value != filename_date:
        raise LifecycleError(
            "WI-DECISION-DATE-MISMATCH",
            f"decision:{slug} V0 date does not match its filename",
        )
    if v0_cutover_date is not None:
        try:
            cutover = datetime.strptime(v0_cutover_date, "%Y-%m-%d")
        except ValueError as exc:
            raise LifecycleError(
                "WI-DECISION-V0-MANIFEST-INVALID",
                "decision V0 manifest has an invalid cutover date",
            ) from exc
        if cutover.strftime("%Y-%m-%d") != v0_cutover_date:
            raise LifecycleError(
                "WI-DECISION-V0-MANIFEST-INVALID",
                "decision V0 manifest has an invalid cutover date",
            )
        if filename_date >= v0_cutover_date:
            raise LifecycleError(
                "WI-DECISION-V0-CUTOVER-VIOLATION",
                f"decision:{slug} V0 date is on or after the cutover",
            )

    raw_lines = text.splitlines(keepends=True)
    body_offset = len("".join(raw_lines[: closing_index + 1]).encode("utf-8"))
    admitted = raw_status if raw_status in CATEGORIES["decision"].current_statuses else None
    return CurrentDecisionRecord(
        format=DECISION_FORMAT_V0,
        fields=_immutable_decision_fields(fields),
        raw_status=raw_status,
        admitted_current_status=admitted,
        body_offset=body_offset,
        legacy_read_only=True,
    )


def _normalize_decision_h1_key(key: str) -> str:
    return re.sub(r"[ _-]+", "-", key.casefold())


def _validate_current_decision_h1(
    text: str,
    slug: str,
    *,
    h1_cutover_date: str | None,
) -> CurrentDecisionRecord:
    logical_lines = text.splitlines()
    if len(logical_lines) < 4 or logical_lines[1] != "":
        raise LifecycleError(
            "WI-DECISION-H1-SCHEMA-INVALID",
            f"decision:{slug} requires an exact blank line 2",
        )
    if logical_lines[2] == "":
        raise LifecycleError(
            "WI-DECISION-H1-STATUS-UNSUPPORTED",
            f"decision:{slug} requires status as its first H1 prefix field",
        )
    prefix_end = next(
        (index for index, line in enumerate(logical_lines[3:], start=3) if line == ""),
        None,
    )
    if prefix_end is None:
        raise LifecycleError(
            "WI-DECISION-H1-SCHEMA-INVALID",
            f"decision:{slug} has no exact H1 prefix terminator",
        )
    body = "\n".join(logical_lines[prefix_end + 1 :])
    if not body.strip():
        raise LifecycleError(
            "WI-DECISION-H1-SCHEMA-INVALID",
            f"decision:{slug} has an empty H1 body",
        )

    first = logical_lines[2]
    if DECISION_H1_PLAIN_FIELD_RE.fullmatch(first):
        field_re = DECISION_H1_PLAIN_FIELD_RE
    elif DECISION_H1_BOLD_FIELD_RE.fullmatch(first):
        field_re = DECISION_H1_BOLD_FIELD_RE
    else:
        raise LifecycleError(
            "WI-DECISION-H1-SCHEMA-INVALID",
            f"decision:{slug} has an invalid H1 status field at line 3",
        )

    fields: dict[str, str] = {}
    normalized_keys: dict[str, str] = {}
    raw_status: str | None = None
    for index, line in enumerate(logical_lines[2:prefix_end], start=3):
        if "\t" in line or not line or line[:1].isspace():
            raise LifecycleError(
                "WI-DECISION-H1-SCHEMA-INVALID",
                f"decision:{slug} has an invalid H1 prefix line {index}",
            )
        match = field_re.fullmatch(line)
        if match is None:
            raise LifecycleError(
                "WI-DECISION-H1-SCHEMA-INVALID",
                f"decision:{slug} mixes or malforms H1 prefix mode at line {index}",
            )
        key, value = match.groups()
        normalized = _normalize_decision_h1_key(key)
        if normalized in normalized_keys:
            failure_id = (
                "WI-DECISION-H1-STATUS-UNSUPPORTED"
                if normalized == "status"
                else "WI-DECISION-H1-FIELD-DUPLICATE"
            )
            raise LifecycleError(
                failure_id,
                f"decision:{slug} duplicates H1 key '{key}' at line {index}",
            )
        normalized_keys[normalized] = key
        fields[key] = value
        if index == 3:
            if normalized != "status":
                raise LifecycleError(
                    "WI-DECISION-H1-STATUS-UNSUPPORTED",
                    f"decision:{slug} requires status as its first H1 prefix field",
                )
            raw_status = value

    if raw_status is None or len([key for key in normalized_keys if key == "status"]) != 1:
        raise LifecycleError(
            "WI-DECISION-H1-STATUS-UNSUPPORTED",
            f"decision:{slug} requires exactly one first H1 status field",
        )
    status_word = re.match(r"^([A-Za-z]+)(?:\s|$)", raw_status)
    admitted = status_word.group(1).casefold() if status_word else ""
    if admitted not in {"accepted", "proposed"}:
        raise LifecycleError(
            "WI-DECISION-H1-STATUS-UNSUPPORTED",
            f"decision:{slug} has an unsupported H1 status token",
        )

    filename_date, _suffix = _decision_filename_date_suffix(slug)
    if h1_cutover_date is not None:
        try:
            cutover = datetime.strptime(h1_cutover_date, "%Y-%m-%d")
        except ValueError as exc:
            raise LifecycleError(
                "WI-DECISION-H1-MANIFEST-INVALID",
                "decision H1 manifest has an invalid cutover date",
            ) from exc
        if cutover.strftime("%Y-%m-%d") != h1_cutover_date:
            raise LifecycleError(
                "WI-DECISION-H1-MANIFEST-INVALID",
                "decision H1 manifest has an invalid cutover date",
            )
        if filename_date >= h1_cutover_date:
            raise LifecycleError(
                "WI-DECISION-H1-CUTOVER-VIOLATION",
                f"decision:{slug} H1 date is on or after the cutover",
            )

    raw_lines = text.splitlines(keepends=True)
    body_offset = len("".join(raw_lines[: prefix_end + 1]).encode("utf-8"))
    return CurrentDecisionRecord(
        format=DECISION_FORMAT_H1,
        fields=_immutable_decision_fields(fields),
        raw_status=raw_status,
        admitted_current_status=admitted,
        body_offset=body_offset,
        legacy_read_only=True,
    )


def _validate_current_decision_record(
    path: Path,
    slug: str,
    *,
    v0_cutover_date: str | None = None,
    h1_cutover_date: str | None = None,
) -> CurrentDecisionRecord:
    text = _read_current_decision_text(path, slug)
    selected = _current_decision_format(text, slug)
    if selected == DECISION_FORMAT_V1:
        return _validate_current_decision_v1(text, slug)
    if selected == DECISION_FORMAT_V0:
        return _validate_current_decision_v0(
            text,
            slug,
            v0_cutover_date=v0_cutover_date,
        )
    return _validate_current_decision_h1(
        text,
        slug,
        h1_cutover_date=h1_cutover_date,
    )


class _DecisionCompatibilityManifestDuplicateKey(ValueError):
    pass


def _decision_compatibility_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DecisionCompatibilityManifestDuplicateKey(key)
        result[key] = value
    return result


def _decision_compatibility_baseline_digest(entries: list[dict[str, str]]) -> str:
    payload = b"".join(
        entry["path"].encode("utf-8")
        + b"\0"
        + entry["sha256"].encode("ascii")
        + b"\n"
        for entry in entries
    )
    return hashlib.sha256(payload).hexdigest().upper()


def _validate_current_decision_v0_manifest_record(
    path: Path,
    slug: str,
    cutover_date: str,
) -> CurrentDecisionRecord:
    return _validate_current_decision_record(
        path,
        slug,
        v0_cutover_date=cutover_date,
    )


def _validate_current_decision_h1_manifest_record(
    path: Path,
    slug: str,
    cutover_date: str,
) -> CurrentDecisionRecord:
    return _validate_current_decision_record(
        path,
        slug,
        h1_cutover_date=cutover_date,
    )


def _verify_current_decision_compatibility_manifest(
    root: Path,
    profile: DecisionCompatibilityProfile,
) -> dict[str, CurrentDecisionRecord]:
    def manifest_invalid(message: str) -> LifecycleError:
        return LifecycleError(profile.manifest_invalid_failure_id, message)

    work_items = _work_items_root(root)
    decisions = work_items / CATEGORIES["decision"].current_root
    current_paths = sorted(decisions.glob("*.md"), key=lambda path: path.name)
    formats: dict[str, str] = {}
    for path in current_paths:
        text = _read_current_decision_text(path, path.stem)
        try:
            formats[path.name] = _current_decision_format(text, path.stem)
        except LifecycleError as exc:
            if exc.failure_id != "WI-DECISION-FORMAT-UNSUPPORTED":
                raise
            formats[path.name] = "other"
    discovered = tuple(
        name for name, selected in formats.items() if selected == profile.format
    )
    manifest_path = work_items / profile.manifest_name
    if not manifest_path.is_file():
        if discovered:
            raise LifecycleError(
                profile.manifest_missing_failure_id,
                f"current {profile.label} decision requires work-items/{profile.manifest_name}",
            )
        return {}
    try:
        payload = json.loads(
            manifest_path.read_text(encoding="utf-8"),
            object_pairs_hook=_decision_compatibility_json_object,
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        _DecisionCompatibilityManifestDuplicateKey,
    ) as exc:
        raise manifest_invalid(
            f"decision {profile.label} manifest is not strict UTF-8 JSON"
        ) from exc
    if not isinstance(payload, dict) or set(payload) != {
        "schemaVersion",
        "policyDecision",
        "cutoverDate",
        "baselineSha256",
        "entries",
    }:
        raise manifest_invalid(
            f"decision {profile.label} manifest has an invalid top-level shape"
        )
    if (
        type(payload["schemaVersion"]) is not int
        or payload["schemaVersion"] != profile.manifest_schema_version
    ):
        raise manifest_invalid(
            f"decision {profile.label} manifest has an unsupported schemaVersion"
        )
    policy_slug = payload["policyDecision"]
    cutover_date = payload["cutoverDate"]
    baseline_sha256 = payload["baselineSha256"]
    raw_entries = payload["entries"]
    if (
        not isinstance(policy_slug, str)
        or not is_valid_slug(policy_slug)
        or not isinstance(cutover_date, str)
        or not DECISION_DATE_RE.fullmatch(cutover_date)
        or not isinstance(baseline_sha256, str)
        or not re.fullmatch(r"[0-9A-F]{64}", baseline_sha256)
        or not isinstance(raw_entries, list)
        or not raw_entries
    ):
        raise manifest_invalid(
            f"decision {profile.label} manifest has invalid scalar fields"
        )
    try:
        cutover = datetime.strptime(cutover_date, "%Y-%m-%d")
    except ValueError as exc:
        raise manifest_invalid(
            f"decision {profile.label} manifest cutoverDate is invalid"
        ) from exc
    if cutover.strftime("%Y-%m-%d") != cutover_date:
        raise manifest_invalid(
            f"decision {profile.label} manifest cutoverDate is invalid"
        )

    entries: list[dict[str, str]] = []
    for index, raw_entry in enumerate(raw_entries):
        if not isinstance(raw_entry, dict) or set(raw_entry) != {"path", "sha256", "state"}:
            raise manifest_invalid(
                f"decision {profile.label} manifest entry {index} has invalid shape"
            )
        name = raw_entry["path"]
        digest = raw_entry["sha256"]
        state = raw_entry["state"]
        if (
            not isinstance(name, str)
            or not name.endswith(".md")
            or Path(name).name != name
            or "/" in name
            or "\\" in name
            or not is_valid_slug(Path(name).stem)
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9A-F]{64}", digest)
            or state not in {"admitted", "retired"}
        ):
            raise manifest_invalid(
                f"decision {profile.label} manifest entry {index} is invalid"
            )
        entries.append({"path": name, "sha256": digest, "state": state})
    names = [entry["path"] for entry in entries]
    if names != sorted(names) or len(names) != len(set(names)):
        raise manifest_invalid(
            f"decision {profile.label} manifest entries must be sorted and unique"
        )
    if _decision_compatibility_baseline_digest(entries) != baseline_sha256:
        raise manifest_invalid(
            f"decision {profile.label} manifest baseline digest does not match its rows"
        )

    anchor_path = decisions / f"{policy_slug}.md"
    if not anchor_path.is_file() or formats.get(anchor_path.name) != DECISION_FORMAT_V1:
        raise manifest_invalid(
            f"decision {profile.label} manifest policy anchor is not a current V1 record"
        )
    try:
        anchor = _validate_current_decision_record(anchor_path, policy_slug)
    except LifecycleError as exc:
        raise manifest_invalid(
            f"decision {profile.label} manifest policy anchor is invalid"
        ) from exc
    expected_manifest = f"work-items/{profile.manifest_name}"
    if (
        anchor.raw_status != "accepted"
        or anchor.fields.get(profile.anchor_manifest_field) != expected_manifest
        or anchor.fields.get(profile.anchor_baseline_field) != baseline_sha256
        or anchor.fields.get(profile.anchor_cutover_field) != cutover_date
    ):
        raise manifest_invalid(
            f"decision {profile.label} manifest policy anchor does not match"
        )

    by_name = {entry["path"]: entry for entry in entries}
    for name in discovered:
        entry = by_name.get(name)
        if entry is None:
            raise LifecycleError(
                profile.unadmitted_failure_id,
                f"decisions/{name} is not in the frozen {profile.label} manifest",
            )
        if entry["state"] == "retired":
            raise LifecycleError(
                profile.retired_reappeared_failure_id,
                f"retired decisions/{name} reappeared as {profile.label}",
            )

    admitted: dict[str, CurrentDecisionRecord] = {}
    for entry in entries:
        name = entry["path"]
        path = decisions / name
        selected = formats.get(name)
        if entry["state"] == "retired":
            if selected is None or selected == DECISION_FORMAT_V1:
                continue
            raise LifecycleError(
                profile.manifest_stale_failure_id,
                f"retired decisions/{name} is neither absent nor V1",
            )
        if selected is None or selected != profile.format:
            raise LifecycleError(
                profile.manifest_stale_failure_id,
                f"admitted decisions/{name} is missing or no longer {profile.label}",
            )
        actual_digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        if actual_digest != entry["sha256"]:
            raise LifecycleError(
                profile.hash_mismatch_failure_id,
                f"admitted decisions/{name} differs from its frozen SHA-256",
            )
        admitted[name] = profile.validate_record(path, path.stem, cutover_date)
    return admitted


def _preflight_current_decision_v0(root: Path) -> dict[str, CurrentDecisionRecord]:
    return _verify_current_decision_compatibility_manifest(
        root,
        DecisionCompatibilityProfile(
            label="V0",
            format=DECISION_FORMAT_V0,
            manifest_name=DECISION_V0_MANIFEST,
            manifest_schema_version=DECISION_V0_MANIFEST_SCHEMA_VERSION,
            anchor_manifest_field="v0-manifest",
            anchor_baseline_field="v0-baseline-sha256",
            anchor_cutover_field="v0-cutover-date",
            manifest_missing_failure_id="WI-DECISION-V0-MANIFEST-MISSING",
            manifest_invalid_failure_id="WI-DECISION-V0-MANIFEST-INVALID",
            unadmitted_failure_id="WI-DECISION-V0-UNADMITTED",
            manifest_stale_failure_id="WI-DECISION-V0-MANIFEST-STALE",
            hash_mismatch_failure_id="WI-DECISION-V0-HASH-MISMATCH",
            retired_reappeared_failure_id="WI-DECISION-V0-RETIRED-REAPPEARED",
            validate_record=_validate_current_decision_v0_manifest_record,
        ),
    )


def _preflight_current_decision_h1(root: Path) -> dict[str, CurrentDecisionRecord]:
    return _verify_current_decision_compatibility_manifest(
        root,
        DecisionCompatibilityProfile(
            label="H1",
            format=DECISION_FORMAT_H1,
            manifest_name=DECISION_H1_MANIFEST,
            manifest_schema_version=DECISION_H1_MANIFEST_SCHEMA_VERSION,
            anchor_manifest_field="h1-manifest",
            anchor_baseline_field="h1-baseline-sha256",
            anchor_cutover_field="h1-cutover-date",
            manifest_missing_failure_id="WI-DECISION-H1-MANIFEST-MISSING",
            manifest_invalid_failure_id="WI-DECISION-H1-MANIFEST-INVALID",
            unadmitted_failure_id="WI-DECISION-H1-UNADMITTED",
            manifest_stale_failure_id="WI-DECISION-H1-MANIFEST-STALE",
            hash_mismatch_failure_id="WI-DECISION-H1-HASH-MISMATCH",
            retired_reappeared_failure_id="WI-DECISION-H1-RETIRED-REAPPEARED",
            validate_record=_validate_current_decision_h1_manifest_record,
        ),
    )


def _validate_canonical_candidate_header(data: bytes) -> None:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LifecycleError(
            "WI-CATEGORY-STATUS-INVALID",
            "canonical candidate header must be UTF-8",
        ) from exc

    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        closing = next(
            (index for index, line in enumerate(lines[1:], start=2) if line.strip() == "---"),
            None,
        )
        if closing is None:
            raise LifecycleError(
                "WI-CATEGORY-STATUS-INVALID",
                "canonical candidate frontmatter is unterminated",
            )
        header_start, header_end = 2, closing - 1
        malformed_header_end = header_end
    else:
        header_start, header_end = 1, 0
        for line_number, line in enumerate(lines, start=1):
            if not FIELD_RE.fullmatch(line):
                break
            header_end = line_number
        malformed_header_end = 0
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                break
            malformed_header_end = line_number

    occurrences = _authoritative_field_occurrences(text)
    statuses = [
        (line_number, value)
        for line_number, name, value, _line in occurrences
        if name == "status"
    ]
    malformed_status = any(
        re.match(
            r"^\s*(?:-\s*)?(?:\*\*)?status(?:\*\*)?(?:\s|$)",
            line,
            re.IGNORECASE,
        )
        and not FIELD_RE.fullmatch(line)
        for line_number, line in _authoritative_markdown_lines(text)
        if header_start <= line_number <= malformed_header_end
    )
    if (
        malformed_status
        or len(statuses) != 1
        or not (header_start <= statuses[0][0] <= header_end)
        or statuses[0][1] != "candidate"
    ):
        raise LifecycleError(
            "WI-CATEGORY-STATUS-INVALID",
            "canonical candidate header requires exactly one 'status: candidate' field",
        )


def _terminalization_authoritative_field_occurrences(
    text: str, utc_field: str = "Terminal-at"
) -> tuple[str, ...]:
    authoritative = {utc_field.casefold(), "v1-migration-evidence"}
    occurrences: list[str] = []
    for _line_number, line in _authoritative_markdown_lines(text):
        match = FIELD_RE.fullmatch(line)
        if match:
            name = match.group(1).strip().casefold()
            if name in authoritative:
                occurrences.append(name)
    return tuple(occurrences)


def _schema_marker_occurrences(data: bytes, member: str) -> tuple[tuple[str, str, str], ...]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LifecycleError(
            "WI-CATEGORY-SCHEMA-INVALID",
            f"{member} schema marker source must be UTF-8",
        ) from exc
    occurrences: list[tuple[str, str, str]] = []
    for _line_number, line in _authoritative_markdown_lines(text):
        match = WORK_ITEM_SCHEMA_OCCURRENCE_RE.fullmatch(line)
        if match:
            occurrences.append((line, match.group(1), match.group(2)))
    return tuple(occurrences)


def _require_canonical_schema_marker(
    occurrences: tuple[tuple[str, str, str], ...],
    member: str,
) -> None:
    if len(occurrences) != 1 or occurrences[0] != (
        WORK_ITEM_SCHEMA_MARKER,
        WORK_ITEM_SCHEMA_KEY,
        WORK_ITEM_SCHEMA_VALUE,
    ):
        raise LifecycleError(
            "WI-CATEGORY-SCHEMA-INVALID",
            f"{member} must contain exactly one canonical {WORK_ITEM_SCHEMA_MARKER!r}",
        )


def _stamp_schema_marker(data: bytes, member: str) -> bytes:
    occurrences = _schema_marker_occurrences(data, member)
    if occurrences:
        _require_canonical_schema_marker(occurrences, member)
        return data
    separator = b"" if data.endswith(b"\n") else b"\n"
    return data + separator + WORK_ITEM_SCHEMA_MARKER.encode("utf-8") + b"\n"


def _optional_relation_values(
    value: str | None,
    *,
    comma_separated: bool,
) -> tuple[str, ...]:
    if value is None:
        return ()
    normalized = value.strip()
    if (
        not normalized
        or normalized in OPTIONAL_RELATION_ABSENCE_MARKERS
    ):
        return ()
    if comma_separated:
        return tuple(part.strip() for part in normalized.split(","))
    return (normalized,)


def _strict_utc(value: str) -> datetime:
    if not UTC_INSTANT_RE.fullmatch(value):
        raise LifecycleError(
            "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
            f"terminal instant must be strict UTC YYYY-MM-DDTHH:MM:SSZ: {value!r}",
        )
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise LifecycleError(
            "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
            f"invalid terminal instant: {value!r}",
        ) from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise LifecycleError(
            "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
            f"non-canonical terminal instant: {value!r}",
        )
    return parsed


def archive_month(terminal_instant: str) -> str:
    return _strict_utc(terminal_instant).strftime("%Y-%m")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        temp_path = None
        if path.read_bytes() != data:
            raise LifecycleError("WI-ATOMIC-BYTE-CHECK", f"byte check failed: {path}")
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass


def _canonical_category(reference: str) -> tuple[Category, str]:
    if reference.count(":") != 1:
        raise LifecycleError(
            "WI-REFERENCE-INVALID",
            f"reference must be category-qualified as <category>:<bare-slug>: {reference!r}",
        )
    category_name, slug = reference.split(":", 1)
    category_name = CATEGORY_ALIASES.get(category_name, category_name)
    category = CATEGORIES.get(category_name)
    if category is None:
        raise LifecycleError("WI-REFERENCE-INVALID", f"unknown category: {category_name!r}")
    _validate_slug(slug)
    return category, slug


def _category_locations(root: Path, category: Category, slug: str) -> list[Path]:
    work_items = _work_items_root(root)
    locations: list[Path] = []
    if category.current_kind == "work-item":
        backlog = work_items / "backlog" / f"{slug}.md"
        active = work_items / "active" / slug
        if backlog.is_file():
            locations.append(backlog)
        if active.is_dir():
            locations.append(active)
        archive = work_items / "archive"
        if archive.is_dir():
            locations.extend(
                sorted(
                    month / slug
                    for month in archive.iterdir()
                    if month.is_dir() and (month / slug).is_dir()
                )
            )
    else:
        current = work_items / category.current_root / f"{slug}.md"
        if current.is_file():
            locations.append(current)
        archive = work_items / category.current_root / "archive"
        if archive.is_dir():
            locations.extend(
                sorted(
                    month / f"{slug}.md"
                    for month in archive.iterdir()
                    if month.is_dir() and (month / f"{slug}.md").is_file()
                )
            )
    return locations


def resolve_category(root: Path, reference: str) -> Path:
    category, slug = _canonical_category(reference)
    locations = _category_locations(root, category, slug)
    if len(locations) > 1:
        raise LifecycleError(
            "WI-CATEGORY-DUAL-LOCATION",
            f"{reference} has {len(locations)} physical locations",
        )
    if not locations:
        raise LifecycleError("WI-REFERENCE-MISSING", f"no physical location for {reference}")
    return locations[0].resolve()


def work_item_dependency_state(root: Path, slug: str) -> str:
    """Resolve one dependency through the lifecycle owner.

    Physical location owns the state: backlog and active records are open,
    while only a dated archive record is done. Missing and duplicate identities
    retain ``resolve_category``'s stable fail-closed errors.
    """
    location = resolve_category(root, f"work-item:{slug}")
    archive = (_work_items_root(root) / "archive").resolve()
    return "done" if archive in location.parents else "open"


def resolve_legacy_path(root: Path, legacy_path: str) -> Path:
    candidate = Path(legacy_path)
    if candidate.is_absolute():
        raise LifecycleError("WI-REFERENCE-INVALID", "legacy path must be relative")
    repo_root = _work_items_root(root).parent.resolve()
    resolved = (repo_root / candidate).resolve()
    if resolved != repo_root and repo_root not in resolved.parents:
        raise LifecycleError("WI-REFERENCE-INVALID", "legacy path escapes repository")
    if not resolved.exists():
        raise LifecycleError(
            "WI-LEGACY-LINK-UNMAPPED",
            f"legacy path is absent and has no incoming-link inventory: {legacy_path}",
        )
    return resolved


def _relative_link(work_items: Path, path: Path) -> str:
    return Path(os.path.relpath(path, work_items)).as_posix()


def _status_entry(root: Path, item: Path) -> ReadmeEntry:
    status_path = item / "status.md"
    if not status_path.is_file():
        raise LifecycleError("WI-CATEGORY-STATUS-MISSING", f"missing status.md: {item}")
    text = status_path.read_text(encoding="utf-8")
    fields = _parse_fields(text)
    status = fields.get("status", "")
    if status in CATEGORIES["work-item"].terminal_statuses:
        raise LifecycleError(
            "WI-CATEGORY-TERMINAL-IN-CURRENT",
            f"terminal work-item remains active: {item.name}",
        )
    if status not in {"active", "blocked"}:
        raise LifecycleError(
            "WI-CATEGORY-STATUS-INVALID", f"active work-item has invalid status {status!r}: {item}"
        )
    section = "Blockers" if status == "blocked" or fields.get("blocker") else "Current focus"
    label = fields.get("task") or item.name
    detail = fields.get("blocker", "") if section == "Blockers" else fields.get("current step", "")
    entry = ReadmeEntry(
        section,
        f"work-item:{item.name}",
        label,
        status_path,
        False,
        detail,
        [status_path],
    )
    progressive: list[str] = []
    for field_name, category in (("roadmap", "roadmap"), ("epic", "epic")):
        related_values = _optional_relation_values(
            fields.get(field_name),
            comma_separated=False,
        )
        if not related_values:
            continue
        related_slug = related_values[0]
        _validate_slug(related_slug)
        related = resolve_category(root, f"{category}:{related_slug}")
        entry.source_paths.append(related)
        progressive.append(
            f"[{field_name}]({_relative_link(_work_items_root(root), related)})"
        )
    progressive.append(f"[work item]({_relative_link(_work_items_root(root), status_path)})")
    suffix = " → ".join(progressive)
    entry.detail = " — ".join(part for part in (entry.detail, suffix) if part)
    return entry


def _legacy_retirement_entry(item: Path, metadata: Path) -> ReadmeEntry:
    try:
        payload = json.loads(metadata.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LifecycleError(
            "WI-LEGACY-RETIREMENT-INVALID",
            f"invalid legacy retirement metadata: {metadata}",
        ) from exc
    expected_scalars = {
        "schemaVersion": LEGACY_RETIREMENT_SCHEMA_VERSION,
        "owner": LEGACY_RETIREMENT_OWNER,
        "kind": "legacy-backlog-retirement",
        "slug": item.name,
        "status": "rejected-before-admission",
        "admissionHistory": "never-admitted",
    }
    if not isinstance(payload, dict) or any(
        payload.get(key) != value for key, value in expected_scalars.items()
    ):
        raise LifecycleError(
            "WI-LEGACY-RETIREMENT-INVALID",
            f"legacy retirement identity differs: {item}",
        )
    terminal_at = payload.get("terminalAt")
    if not isinstance(terminal_at, str):
        raise LifecycleError(
            "WI-LEGACY-RETIREMENT-INVALID", f"missing terminalAt: {metadata}"
        )
    _strict_utc(terminal_at)
    if archive_month(terminal_at) != item.parent.name:
        raise LifecycleError(
            "WI-CATEGORY-ARCHIVE-MONTH-MISMATCH",
            f"{item.name} belongs in archive/{archive_month(terminal_at)}",
        )
    disposition = payload.get("productDisposition")
    if not isinstance(disposition, str) or not disposition.strip():
        raise LifecycleError(
            "WI-LEGACY-RETIREMENT-INVALID",
            f"missing product disposition: {metadata}",
        )
    if payload.get("syntheticTransitions") != []:
        raise LifecycleError(
            "WI-LEGACY-RETIREMENT-INVALID",
            f"legacy retirement must not synthesize lifecycle transitions: {metadata}",
        )
    incoming = payload.get("incomingLinks")
    try:
        _validate_incoming_link_snapshot(f"work-item:{item.name}", incoming, label="stored")
    except LifecycleError as exc:
        raise LifecycleError(
            "WI-LEGACY-RETIREMENT-INVALID",
            f"invalid incoming-link inventory: {metadata}",
        ) from exc
    rows = payload.get("sourceFiles")
    if not isinstance(rows, list) or not rows:
        raise LifecycleError(
            "WI-LEGACY-RETIREMENT-INVALID", f"missing source file inventory: {metadata}"
        )
    sources: list[Path] = [metadata]
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise LifecycleError(
                "WI-LEGACY-RETIREMENT-INVALID", f"invalid source row: {metadata}"
            )
        relative = row.get("path")
        if not isinstance(relative, str) or relative in seen:
            raise LifecycleError(
                "WI-LEGACY-RETIREMENT-INVALID", f"duplicate source path: {metadata}"
            )
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts or relative == LEGACY_RETIREMENT_FILE:
            raise LifecycleError(
                "WI-LEGACY-RETIREMENT-INVALID", f"unsafe source path: {relative!r}"
            )
        source = item / candidate
        if source.is_symlink() or not source.is_file():
            raise LifecycleError(
                "WI-LEGACY-RETIREMENT-INVALID", f"missing source payload: {relative}"
            )
        data = source.read_bytes()
        if (
            row.get("byteLength") != len(data)
            or row.get("sha256") != hashlib.sha256(data).hexdigest()
        ):
            raise LifecycleError(
                "WI-LEGACY-RETIREMENT-INVALID", f"source digest differs: {relative}"
            )
        seen.add(relative)
        sources.append(source)
    actual = {
        path.relative_to(item).as_posix()
        for path in item.rglob("*")
        if path.is_file() and path != metadata
    }
    if actual != seen:
        raise LifecycleError(
            "WI-LEGACY-RETIREMENT-INVALID",
            f"source inventory does not cover the retirement payload: {item}",
        )
    # Retirement is immutable, but its former backlog paths must not remain in
    # mutable records.  The stored inventory is evidence from the transition;
    # this fresh owner-level scan catches a later plain-text citation that the
    # original Markdown/link scanner could not see.  Archived consumers are
    # historical evidence and intentionally do not participate.
    work_items = item.parents[2]
    current_incoming = _incoming_link_result(
        work_items.parent,
        sources,
        f"work-item:{item.name}",
        literal_path_references=(
            f"{work_items.name}/backlog/{item.name}/{relative}"
            for relative in seen
        ),
        mutable_consumers_only=True,
        scan_markdown_links=False,
    )
    try:
        _validate_incoming_link_snapshot(
            f"work-item:{item.name}", current_incoming, label="current"
        )
    except LifecycleError as exc:
        raise LifecycleError(
            "WI-LEGACY-RETIREMENT-INVALID",
            f"mutable record retains a retired backlog path: {item}",
        ) from exc
    return ReadmeEntry(
        "Recently completed",
        f"work-item:{item.name}",
        f"Rejected before admission: {item.name}",
        metadata,
        True,
        disposition.strip().splitlines()[0],
        sources,
        "WI-LEGACY-RETIRED-BEFORE-ADMISSION",
    )


def _archived_work_item_entry(item: Path) -> ReadmeEntry:
    retirement = item / LEGACY_RETIREMENT_FILE
    if retirement.is_file():
        if (item / "status.md").exists() or (item / "closure.md").exists():
            raise LifecycleError(
                "WI-LEGACY-RETIREMENT-INVALID",
                f"direct legacy retirement must not carry active/closure history: {item}",
            )
        return _legacy_retirement_entry(item, retirement)
    closure = item / "closure.md"
    if not closure.is_file():
        raise LifecycleError(
            "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
            f"archived work-item lacks closure.md: {item}",
        )
    status = item / "status.md"
    closure_data = closure.read_bytes()
    status_data = status.read_bytes() if status.is_file() else b""
    closure_markers = _schema_marker_occurrences(closure_data, "closure.md")
    status_markers = _schema_marker_occurrences(status_data, "status.md")
    fields = _parse_fields(closure_data.decode("utf-8"))
    sources = [closure]
    if status.is_file():
        sources.append(status)

    if not closure_markers and not status_markers:
        return ReadmeEntry(
            "Recently completed",
            f"work-item:{item.name}",
            fields.get("outcome") or item.name,
            closure,
            True,
            fields.get("residual risk", ""),
            sources,
            LEGACY_READ_CLASSIFICATION,
        )

    _require_canonical_schema_marker(status_markers, "status.md")
    _require_canonical_schema_marker(closure_markers, "closure.md")
    closed = fields.get("closed", "")
    _validate_closure(closure_data, closed)
    expected_month = archive_month(closed)
    if expected_month != item.parent.name:
        raise LifecycleError(
            "WI-CATEGORY-ARCHIVE-MONTH-MISMATCH",
            f"{item.name} belongs in archive/{expected_month}, not {item.parent.name}",
        )
    status_fields = _parse_fields(status_data.decode("utf-8"))
    status_value = status_fields.get("status", "")
    if status_value in CATEGORIES["work-item"].current_statuses:
        raise LifecycleError(
            "WI-CATEGORY-CURRENT-IN-ARCHIVE",
            f"work-item:{item.name} has current status in archive",
        )
    if status_value not in CATEGORIES["work-item"].terminal_statuses:
        raise LifecycleError(
            "WI-CATEGORY-STATUS-INVALID",
            f"work-item:{item.name} has invalid archived V1 status {status_value!r}",
        )
    return ReadmeEntry(
        "Recently completed",
        f"work-item:{item.name}",
        fields.get("outcome") or item.name,
        closure,
        True,
        fields.get("residual risk", ""),
        sources,
    )


def collect_readme_entries(root: Path) -> list[ReadmeEntry]:
    work_items = _work_items_root(root)
    entries: list[ReadmeEntry] = []

    backlog = work_items / "backlog"
    if backlog.is_dir():
        for path in sorted(backlog.glob("*.md")):
            fields = _parse_fields(path.read_text(encoding="utf-8"))
            status = fields.get("status")
            if status and status != "candidate":
                failure = (
                    "WI-CATEGORY-TERMINAL-IN-CURRENT"
                    if status in CATEGORIES["work-item"].terminal_statuses
                    else "WI-CATEGORY-STATUS-INVALID"
                )
                raise LifecycleError(
                    failure,
                    f"backlog work-item has invalid current status {status!r}: {path.stem}",
                )
            entries.append(
                ReadmeEntry(
                    "Next actions",
                    f"work-item:{path.stem}",
                    fields.get("task") or path.stem,
                    path,
                    False,
                    fields.get("next action", ""),
                    [path],
                )
            )

    active = work_items / "active"
    if active.is_dir():
        for item in sorted(path for path in active.iterdir() if path.is_dir()):
            entries.append(_status_entry(root, item))

    roadmaps = work_items / "roadmaps"
    if roadmaps.is_dir():
        for path in sorted(roadmaps.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            fields = _parse_fields(text)
            if fields.get("format") != "roadmap-v1":
                continue
            status = fields.get("status", "")
            if status not in {"draft", "active"}:
                raise LifecycleError(
                    "WI-CATEGORY-TERMINAL-IN-CURRENT",
                    f"terminal V1 roadmap remains current: {path.stem}",
                )
            entries.append(
                ReadmeEntry(
                    "Roadmap and milestones",
                    f"roadmap:{path.stem}",
                    fields.get("milestones-or-horizon") or path.stem,
                    path,
                    False,
                    fields.get("order", ""),
                    [path],
                )
            )

    archive = work_items / "archive"
    if archive.is_dir():
        archived: list[ReadmeEntry] = []
        for month in sorted((path for path in archive.iterdir() if path.is_dir()), reverse=True):
            for item in sorted((path for path in month.iterdir() if path.is_dir()), reverse=True):
                archived.append(_archived_work_item_entry(item))
        entries.extend(archived)

    seen: set[str] = set()
    for entry in entries:
        if entry.logical_reference in seen:
            raise LifecycleError(
                "WI-CATEGORY-DUAL-LOCATION",
                f"duplicate README logical reference: {entry.logical_reference}",
            )
        seen.add(entry.logical_reference)
    order = {section: index for index, section in enumerate(README_SECTIONS)}
    return sorted(entries, key=lambda entry: (order[entry.section], entry.logical_reference))


def _input_digest(entries: Iterable[ReadmeEntry], work_items: Path) -> str:
    inputs: dict[str, bytes] = {}
    for entry in entries:
        for path in entry.source_paths:
            logical_path = _relative_link(work_items, path)
            inputs[logical_path] = path.read_bytes()
    digest = hashlib.sha256()
    for logical_path, data in sorted(inputs.items()):
        encoded = logical_path.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def _canonical_timestamp(entries: Iterable[ReadmeEntry]) -> str:
    instants: list[str] = []
    for entry in entries:
        for path in entry.source_paths:
            if path.name == LEGACY_RETIREMENT_FILE:
                try:
                    value = json.loads(path.read_text(encoding="utf-8")).get("terminalAt")
                except (OSError, UnicodeError, json.JSONDecodeError, AttributeError) as exc:
                    raise LifecycleError(
                        "WI-LEGACY-RETIREMENT-INVALID",
                        f"cannot read terminal instant: {path}",
                    ) from exc
                if isinstance(value, str) and UTC_INSTANT_RE.fullmatch(value):
                    _strict_utc(value)
                    instants.append(value)
                continue
            fields = _parse_fields(path.read_text(encoding="utf-8"))
            for key in ("updated", "closed", "terminal-at"):
                value = fields.get(key)
                if value and UTC_INSTANT_RE.fullmatch(value):
                    _strict_utc(value)
                    instants.append(value)
    return max(instants, default="none")


def _default_static_guide() -> str:
    return (
        "# Work items\n\n"
        "Read this page for current delivery status. Make lifecycle changes through "
        "`scripts/mutate-work-item.py`, then follow the generated links for detail.\n\n"
    )


def _static_guide(readme: Path, *, allow_marker_bootstrap: bool = False) -> str:
    if not readme.exists():
        return _default_static_guide()
    text = readme.read_text(encoding="utf-8")
    begin_count = text.count(README_BEGIN)
    end_count = text.count(README_END)
    if allow_marker_bootstrap and begin_count == 0 and end_count == 0:
        return _default_static_guide()
    if begin_count != 1 or end_count != 1 or text.index(README_BEGIN) > text.index(README_END):
        raise LifecycleError(
            "WI-README-MARKERS",
            "existing README must contain exactly one ordered generated marker pair",
        )
    return text[: text.index(README_BEGIN)].rstrip() + "\n\n"


def render_readme_bytes(
    root: Path,
    *,
    allow_marker_bootstrap: bool = False,
    static_guide_override: str | None = None,
) -> bytes:
    work_items = _work_items_root(root)
    entries = collect_readme_entries(root)
    lines = [
        README_BEGIN,
        "Read-model: work-items-readme-v1",
        "Ordered sources: backlog|active|roadmaps|archive",
        f"Canonical changes through: {_canonical_timestamp(entries)}",
        f"Canonical input digest: sha256:{_input_digest(entries, work_items)}",
        "",
    ]
    by_section = {section: [] for section in README_SECTIONS}
    for entry in entries:
        by_section[entry.section].append(entry)
    for section in README_SECTIONS:
        lines.extend((f"## {section}", ""))
        for entry in by_section[section]:
            marker = "x" if entry.checked else " "
            link = _relative_link(work_items, entry.link)
            detail_parts = [
                part for part in (entry.detail, entry.classification) if part
            ]
            detail = f" — {' — '.join(detail_parts)}" if detail_parts else ""
            lines.append(f"- [{marker}] [{entry.label}]({link}){detail}")
        lines.append("")
    lines.append(README_END)
    static_guide = (
        static_guide_override
        if static_guide_override is not None
        else _static_guide(
            work_items / "README.md",
            allow_marker_bootstrap=allow_marker_bootstrap,
        )
    )
    return (
        static_guide
        + "\n".join(lines)
        + "\n"
    ).encode("utf-8")


def refresh_readme(root: Path, *, allow_marker_bootstrap: bool = False) -> str:
    work_items = _work_items_root(root)
    expected = render_readme_bytes(
        root,
        allow_marker_bootstrap=allow_marker_bootstrap,
    )
    readme = work_items / "README.md"
    _atomic_write(readme, expected)
    observed = render_readme_bytes(root)
    if observed != expected or readme.read_bytes() != expected:
        raise LifecycleError("WI-README-STALE", "README byte verification failed")
    return hashlib.sha256(expected).hexdigest()


def reset_readme_static_guide(root: Path, expected_readme_sha256: str) -> str:
    if not re.fullmatch(r"[0-9A-Fa-f]{64}", expected_readme_sha256):
        raise LifecycleError(
            "WI-README-REPAIR-TARGET-MISMATCH",
            "expected README SHA-256 must be exactly 64 hexadecimal characters",
        )
    work_items = _work_items_root(root)
    readme = work_items / "README.md"
    if not readme.is_file():
        raise LifecycleError(
            "WI-README-MARKERS",
            "static-guide repair requires an existing marker-owned README",
        )
    _static_guide(readme)
    current = readme.read_bytes()
    desired = render_readme_bytes(
        root,
        static_guide_override=_default_static_guide(),
    )
    current_hash = hashlib.sha256(current).hexdigest()
    expected_hash = expected_readme_sha256.casefold()
    if current_hash != expected_hash:
        if current == desired:
            return current_hash
        raise LifecycleError(
            "WI-README-REPAIR-TARGET-MISMATCH",
            "README bytes differ from the explicitly targeted repair input",
        )
    if current == desired:
        return current_hash
    _atomic_write(readme, desired)
    observed = render_readme_bytes(root)
    if observed != desired or readme.read_bytes() != desired:
        raise LifecycleError(
            "WI-README-STALE",
            "README static-guide repair failed complete-byte verification",
        )
    return hashlib.sha256(desired).hexdigest()


def check_readme(root: Path) -> None:
    readme = _work_items_root(root) / "README.md"
    if not readme.is_file() or readme.read_bytes() != render_readme_bytes(root):
        raise LifecycleError("WI-README-STALE", "README does not match canonical inputs")


def _preflight_readme(root: Path) -> None:
    """Validate current canonical inputs and README marker ownership before mutation."""

    render_readme_bytes(root)


def _preflight_readme_markers(root: Path) -> None:
    """Validate README ownership when the current tree is intentionally terminal."""

    _static_guide(_work_items_root(root) / "README.md")


def _validator_module():
    path = Path(__file__).with_name("validate-work-item-state.py")
    spec = importlib.util.spec_from_file_location("work_item_state_validator", path)
    if spec is None or spec.loader is None:
        raise LifecycleError("WI-VALIDATOR-LOAD", f"cannot load validator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scratch_classifier_module():
    path = Path(__file__).with_name("maintenance") / "cleanup.py"
    spec = importlib.util.spec_from_file_location("scratch_evidence_classifier", path)
    if spec is None or spec.loader is None:
        raise LifecycleError("WI-SCRATCH-CLASSIFIER-LOAD", f"cannot load classifier: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _agent_run_ledger_module():
    path = Path(__file__).with_name("agent-run-ledger.py")
    try:
        spec = importlib.util.spec_from_file_location("agent_run_ledger", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"no import specification or loader for {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as exc:
        raise LifecycleError(
            "WI-LEDGER-BOOTSTRAP-INVALID",
            f"cannot load ledger helper {path}: {exc}",
        ) from exc


def _staged_admission_ledger_bytes(slug: str, status_data: bytes) -> bytes:
    """Build the settled Lead admission event from the already-validated status."""

    started_at = _parse_fields(status_data.decode("utf-8"))["started"]
    ledger = _agent_run_ledger_module()
    args = argparse.Namespace(
        work_item=Path(slug),
        run_id=f"{slug}-lifecycle-start",
        work_item_name=slug,
        role="lead",
        execution_role="main",
        assigned_role=None,
        provider=None,
        model=None,
        status="completed",
        gate="none",
        scope=["candidate -> active lifecycle admission"],
        prompt_file=None,
        artifact=None,
        evidence=None,
        evidence_json=None,
        started_at=started_at,
        updated_at=started_at,
        notes=None,
        event_kind="standalone",
        launch_run_id=None,
        closes=None,
        artifact_revision=None,
        lane=None,
        effort=None,
        finding_class=None,
    )
    try:
        event = ledger.build_event(args)
        return (ledger.serialize_event(event) + "\n").encode("utf-8")
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise LifecycleError("WI-LEDGER-BOOTSTRAP-INVALID", str(exc)) from exc


def _validate_active_status_bytes(data: bytes) -> None:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LifecycleError("WI-CATEGORY-STATUS-INVALID", "status must be UTF-8") from exc
    fields = _parse_fields(text)
    if fields.get("status") not in {"active", "blocked"}:
        raise LifecycleError(
            "WI-CATEGORY-STATUS-INVALID", "active status must be active or blocked"
        )
    template = fields.get("template")
    if template == "quick-fix":
        errors: list[str] = []
        _validator_module().validate_quick_fix_status(text, errors)
        if errors:
            raise LifecycleError("WI-CATEGORY-STATUS-INVALID", "; ".join(errors))
        return
    if template != "staged":
        raise LifecycleError(
            "WI-CATEGORY-STATUS-INVALID", "V1 status template must be quick-fix or staged"
        )
    required = {
        "started",
        "updated",
        "task",
        "current step",
        "last result",
        "next action",
        "scope boundary",
        "owner",
        "integration owner",
        "evidence gate",
    }
    missing = sorted(required - set(fields))
    if missing:
        raise LifecycleError(
            "WI-CATEGORY-STATUS-INVALID", f"staged status missing fields: {', '.join(missing)}"
        )
    for slug in _optional_relation_values(
        fields.get("depends-on"),
        comma_separated=True,
    ):
        if ":" in slug:
            raise LifecycleError(
                "WI-DEPENDENCY-NON-WORK-ITEM",
                "Depends-on accepts bare work-item slugs only",
            )
        _validate_slug(slug)


def create_candidate(root: Path, slug: str, data: bytes, *, inject_readme_failure: bool = False) -> Path:
    _validate_slug(slug)
    work_items = _work_items_root(root)
    if _category_locations(root, CATEGORIES["work-item"], slug):
        raise LifecycleError("WI-CATEGORY-DUAL-LOCATION", f"slug already exists: {slug}")
    _preflight_readme(root)
    target = work_items / "backlog" / f"{slug}.md"
    _atomic_write(target, data)
    if inject_readme_failure:
        raise LifecycleError("WI-README-STALE", "injected failure after canonical success")
    try:
        refresh_readme(root)
    except LifecycleError as exc:
        if exc.failure_id == "WI-README-STALE":
            raise
        raise LifecycleError("WI-README-STALE", str(exc)) from exc
    return target


def _legacy_backlog_source(root: Path, slug: str) -> Path:
    _validate_slug(slug)
    locations = _category_locations(root, CATEGORIES["work-item"], slug)
    if locations:
        raise LifecycleError(
            "WI-CATEGORY-DUAL-LOCATION", f"canonical work-item identity already exists: {slug}"
        )
    source = _work_items_root(root) / "backlog" / slug
    if source.is_symlink() or not source.is_dir():
        raise LifecycleError(
            "WI-INVALID-TARGET", f"legacy backlog folder is missing: {slug}"
        )
    return source


def _legacy_source_rows(source: Path) -> list[tuple[str, bytes, str]]:
    rows: list[tuple[str, bytes, str]] = []
    for path in sorted(source.rglob("*"), key=lambda item: item.relative_to(source).as_posix()):
        if path.is_symlink():
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-PAYLOAD", f"symbolic-link source is not admitted: {path}"
            )
        if path.is_dir():
            continue
        if not path.is_file():
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-PAYLOAD", f"unsupported legacy source: {path}"
            )
        relative = path.relative_to(source).as_posix()
        if relative == LEGACY_RETIREMENT_FILE:
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-PAYLOAD",
                f"legacy source uses reserved owner metadata name: {relative}",
            )
        data = path.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-PAYLOAD", f"legacy source is not UTF-8 text: {path}"
            ) from exc
        rows.append((relative, data, text))
    if not rows:
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-PAYLOAD", f"legacy backlog folder is empty: {source}"
        )
    return rows


def _candidate_with_legacy_appendices(
    candidate_data: bytes,
    rows: Iterable[tuple[str, bytes, str]],
) -> bytes:
    try:
        candidate_data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-PAYLOAD", "candidate input must be UTF-8 text"
        ) from exc
    result = bytearray(candidate_data)
    if not result.endswith(b"\n"):
        result.extend(b"\n")
    result.extend(b"\n## Preserved legacy source appendices\n")
    for relative, data, text in rows:
        longest = max((len(match.group(0)) for match in re.finditer(r"`+", text)), default=0)
        fence = "`" * max(3, longest + 1)
        header = (
            f"\n### `{relative}`\n\n"
            f"Source SHA-256: `{hashlib.sha256(data).hexdigest()}`\n\n"
            f"Source byte length: `{len(data)}`\n\n"
            f"{fence}markdown\n"
        ).encode("utf-8")
        result.extend(header)
        result.extend(data)
        if not data.endswith(b"\n"):
            result.extend(b"\n")
        result.extend(f"{fence}\n".encode("utf-8"))
    return bytes(result)


def _restore_readme_snapshot(readme: Path, before: bytes | None) -> None:
    if before is None:
        readme.unlink(missing_ok=True)
    else:
        _atomic_write(readme, before)


def _preflight_legacy_transition_admission(
    root: Path,
    source: Path,
    reference: str,
) -> dict:
    """Reject a legacy transition before it can orphan a physical consumer."""
    incoming = _incoming_link_result(root, {source}, reference)
    _validate_incoming_link_snapshot(reference, incoming, label="legacy transition")
    return incoming


def _legacy_cleanup_metadata(
    slug: str,
    target: Path,
    transaction: Path,
    converted: bytes,
    rows: Iterable[tuple[str, bytes, str]],
) -> bytes:
    payload = {
        "schemaVersion": LEGACY_CLEANUP_SCHEMA_VERSION,
        "owner": LEGACY_CLEANUP_OWNER,
        "slug": slug,
        "transactionId": transaction.name,
        "canonicalTarget": f"{target.parent.name}/{target.name}",
        "candidateSha256": hashlib.sha256(converted).hexdigest(),
        "sourceFiles": [
            {
                "path": relative,
                "byteLength": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
            for relative, data, _text in rows
        ],
    }
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _legacy_cleanup_sidecar(backlog: Path, transaction_id: str) -> Path:
    return backlog / f".legacy-candidate-cleanup.{transaction_id.removeprefix('.')}.json"


def _validated_legacy_cleanup_residue(
    backlog: Path, slug: str, target: Path
) -> tuple[Path | None, Path, str]:
    prefix = f".{slug}.legacy-candidate."
    parent = backlog.resolve()
    residues = sorted(path for path in backlog.glob(f"{prefix}*") if path.name.startswith(prefix))
    if len(residues) > 1:
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"committed cleanup requires exactly one owned residue for {slug}, found {len(residues)}",
        )
    residue = residues[0] if residues else None
    if residue is not None and (
        residue.is_symlink() or not residue.is_dir() or residue.resolve().parent != parent
    ):
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"unsafe committed-cleanup residue for {slug}: {residue}",
        )
    sidecar_prefix = f".legacy-candidate-cleanup.{slug}.legacy-candidate."
    sidecars = sorted(backlog.glob(f"{sidecar_prefix}*.json"))
    markers = list(sidecars)
    if residue is not None:
        embedded_marker = residue / LEGACY_CLEANUP_FILE
        if embedded_marker.exists() or embedded_marker.is_symlink():
            markers.append(embedded_marker)
    if len(markers) != 1:
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"committed cleanup requires exactly one owner marker for {slug}, found {len(markers)}",
        )
    marker = markers[0]
    if marker.is_symlink() or not marker.is_file() or marker.resolve().parent not in {parent, residue}:
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"unsafe owner cleanup marker for {slug}: {marker}",
        )
    if marker.parent == backlog:
        transaction_id = "." + marker.name.removeprefix(".legacy-candidate-cleanup.").removesuffix(
            ".json"
        )
    elif residue is not None and marker.parent == residue:
        transaction_id = residue.name
    else:
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"owner cleanup marker has no transaction parent for {slug}: {marker}",
        )
    if not transaction_id.startswith(prefix) or (residue is not None and transaction_id != residue.name):
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"owner cleanup marker transaction differs from residue for {slug}: {marker}",
        )
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"invalid owner cleanup marker for {slug}: {marker}",
        ) from exc
    expected = {
        "schemaVersion": LEGACY_CLEANUP_SCHEMA_VERSION,
        "owner": LEGACY_CLEANUP_OWNER,
        "slug": slug,
        "transactionId": transaction_id,
        "canonicalTarget": f"{target.parent.name}/{target.name}",
        "candidateSha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    }
    if not isinstance(payload, dict) or any(payload.get(key) != value for key, value in expected.items()):
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"owner cleanup marker differs from committed candidate for {slug}",
        )
    candidate_text = target.read_text(encoding="utf-8")
    rows = payload.get("sourceFiles")
    if not isinstance(rows, list) or not rows:
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"owner cleanup marker has no source inventory for {slug}",
        )
    expected_files: dict[str, tuple[int, str]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise LifecycleError(
                "WI-LEGACY-CLEANUP-REPLAY-INVALID",
                f"owner cleanup marker has invalid source row for {slug}",
            )
        relative = row["path"]
        candidate = Path(relative)
        byte_length = row.get("byteLength")
        digest = row.get("sha256")
        if (
            candidate.is_absolute()
            or ".." in candidate.parts
            or not relative
            or relative in expected_files
            or not isinstance(byte_length, int)
            or byte_length < 0
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
        ):
            raise LifecycleError(
                "WI-LEGACY-CLEANUP-REPLAY-INVALID",
                f"owner cleanup marker source inventory is invalid for {slug}",
            )
        expected_files[relative] = (byte_length, digest)
        source_identity = (
            f"### `{relative}`\n\n"
            f"Source SHA-256: `{digest}`\n\n"
            f"Source byte length: `{byte_length}`\n\n"
        )
        if source_identity not in candidate_text:
            raise LifecycleError(
                "WI-LEGACY-CLEANUP-REPLAY-INVALID",
                f"owner cleanup marker source identity is not committed for {slug}: {relative}",
            )
    source_root = residue / "source" if residue is not None else None
    actual_files: set[str] = set()
    if residue is not None:
        for path in residue.rglob("*"):
            if path.is_symlink() or not (path.is_dir() or path.is_file()):
                raise LifecycleError(
                    "WI-LEGACY-CLEANUP-REPLAY-INVALID",
                    f"owner cleanup residue contains unsafe path for {slug}: {path}",
                )
            if path == marker:
                continue
            try:
                relative = path.relative_to(source_root).as_posix()
            except ValueError as exc:
                raise LifecycleError(
                    "WI-LEGACY-CLEANUP-REPLAY-INVALID",
                    f"owner cleanup residue contains unowned path for {slug}: {path}",
                ) from exc
            if path.is_dir():
                continue
            expected_file = expected_files.get(relative)
            data = path.read_bytes()
            if expected_file is None or expected_file != (len(data), hashlib.sha256(data).hexdigest()):
                raise LifecycleError(
                    "WI-LEGACY-CLEANUP-REPLAY-INVALID",
                    f"owner cleanup residue source differs for {slug}: {relative}",
                )
            actual_files.add(relative)
    if not actual_files <= expected_files.keys():
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"owner cleanup residue has unowned files for {slug}",
        )
    return residue, marker, transaction_id


def _finish_committed_legacy_cleanup(
    backlog: Path,
    residue: Path | None,
    marker: Path,
    transaction_id: str,
) -> None:
    if residue is not None:
        source = residue / "source"
        if source.exists():
            shutil.rmtree(source)
        sidecar = _legacy_cleanup_sidecar(backlog, transaction_id)
        if marker.parent == residue:
            os.replace(marker, sidecar)
            marker = sidecar
        residue.rmdir()
    marker.unlink()


def _committed_cleanup_failure(target: Path, residue: Path, cause: BaseException) -> LifecycleError:
    return LifecycleError(
        "WI-LEGACY-CLEANUP-AFTER-COMMIT",
        f"state=committed target={target} residue={residue}: {cause}",
    )


def _replay_legacy_candidate_cleanup(root: Path, slug: str, candidate_data: bytes) -> Path | None:
    """Remove exactly one safe residue without replaying a committed conversion."""

    work_items = _work_items_root(root)
    backlog = work_items / "backlog"
    source = backlog / slug
    target = backlog / f"{slug}.md"
    if source.exists() or not target.is_file():
        return None
    canonical = _category_locations(root, CATEGORIES["work-item"], slug)
    if canonical != [target]:
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"committed cleanup has ambiguous canonical identity for {slug}",
        )
    candidate_prefix = candidate_data if candidate_data.endswith(b"\n") else candidate_data + b"\n"
    if not target.read_bytes().startswith(candidate_prefix + b"\n## Preserved legacy source appendices\n"):
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"committed cleanup target does not match requested conversion input: {target}",
        )
    check_readme(root)
    residue, marker, transaction_id = _validated_legacy_cleanup_residue(backlog, slug, target)
    target_before = target.read_bytes()
    readme = work_items / "README.md"
    readme_before = readme.read_bytes()
    try:
        _finish_committed_legacy_cleanup(backlog, residue, marker, transaction_id)
    except OSError as exc:
        raise _committed_cleanup_failure(target, residue, exc) from exc
    if (residue is not None and residue.exists()) or marker.exists() or target.read_bytes() != target_before or readme.read_bytes() != readme_before:
        raise LifecycleError(
            "WI-LEGACY-CLEANUP-REPLAY-INVALID",
            f"committed cleanup replay changed canonical state for {slug}",
        )
    return target


def convert_legacy_candidate(
    root: Path,
    slug: str,
    candidate_data: bytes,
    *,
    inject_readme_failure: bool = False,
) -> Path:
    _validate_slug(slug)
    replay = _replay_legacy_candidate_cleanup(root, slug, candidate_data)
    if replay is not None:
        return replay
    source = _legacy_backlog_source(root, slug)
    _preflight_legacy_transition_admission(root, source, f"work-item:{slug}")
    rows = _legacy_source_rows(source)
    _validate_canonical_candidate_header(candidate_data)
    converted = _candidate_with_legacy_appendices(candidate_data, rows)
    _preflight_readme(root)
    work_items = _work_items_root(root)
    readme = work_items / "README.md"
    readme_before = readme.read_bytes() if readme.is_file() else None
    target = work_items / "backlog" / f"{slug}.md"
    transaction = Path(tempfile.mkdtemp(prefix=f".{slug}.legacy-candidate.", dir=target.parent))
    staged_source = transaction / "source"
    staged_candidate = transaction / target.name
    cleanup_marker = transaction / LEGACY_CLEANUP_FILE
    committed = False
    try:
        _atomic_write(staged_candidate, converted)
        _atomic_write(
            cleanup_marker,
            _legacy_cleanup_metadata(slug, target, transaction, converted, rows),
        )
        os.replace(source, staged_source)
        os.replace(staged_candidate, target)
        if inject_readme_failure:
            raise LifecycleError("WI-README-STALE", "injected legacy conversion failure")
        refresh_readme(root)
        if source.exists() or target.read_bytes() != converted:
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-PAYLOAD", "legacy candidate byte verification failed"
            )
        check_readme(root)
        # The flat candidate, regenerated read-model, and byte check form the
        # irreversible commit point. Its appendices carry every staged legacy
        # byte, so disposal of the no-longer-authoritative transaction copy
        # cannot roll this committed transition back.
        committed = True
        try:
            _finish_committed_legacy_cleanup(target.parent, transaction, cleanup_marker, transaction.name)
        except OSError as exc:
            raise _committed_cleanup_failure(target, transaction, exc) from exc
    except BaseException:
        if not committed:
            if target.exists():
                target.unlink()
            if staged_source.exists() and not source.exists():
                os.replace(staged_source, source)
            _restore_readme_snapshot(readme, readme_before)
            if staged_candidate.exists():
                staged_candidate.unlink()
            cleanup_marker.unlink(missing_ok=True)
            transaction.rmdir()
        raise
    return target


def retire_legacy_backlog(
    root: Path,
    slug: str,
    disposition_data: bytes,
    terminal_instant: str,
    *,
    inject_readme_failure: bool = False,
) -> Path:
    source = _legacy_backlog_source(root, slug)
    reference = f"work-item:{slug}"
    incoming = _preflight_legacy_transition_admission(root, source, reference)
    rows = _legacy_source_rows(source)
    try:
        disposition = disposition_data.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise LifecycleError(
            "WI-LEGACY-RETIREMENT-INVALID", "product disposition must be UTF-8 text"
        ) from exc
    if not disposition:
        raise LifecycleError(
            "WI-LEGACY-RETIREMENT-INVALID", "product disposition must not be empty"
        )
    month = archive_month(terminal_instant)
    _preflight_readme(root)
    work_items = _work_items_root(root)
    metadata_payload = {
        "schemaVersion": LEGACY_RETIREMENT_SCHEMA_VERSION,
        "owner": LEGACY_RETIREMENT_OWNER,
        "kind": "legacy-backlog-retirement",
        "slug": slug,
        "status": "rejected-before-admission",
        "terminalAt": terminal_instant,
        "productDisposition": disposition,
        "admissionHistory": "never-admitted",
        "syntheticTransitions": [],
        "sourceFiles": [
            {
                "path": relative,
                "byteLength": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
            for relative, data, _text in rows
        ],
        "incomingLinks": incoming,
    }
    metadata_data = (
        json.dumps(metadata_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    readme = work_items / "README.md"
    readme_before = readme.read_bytes() if readme.is_file() else None
    archive = work_items / "archive"
    month_dir = archive / month
    target = month_dir / slug
    if target.exists():
        raise LifecycleError("WI-CATEGORY-DUAL-LOCATION", f"archive target exists: {target}")
    transaction = Path(tempfile.mkdtemp(prefix=f".{slug}.legacy-retire.", dir=source.parent))
    staged_source = transaction / "source"
    created_archive = not archive.exists()
    created_month = not month_dir.exists()
    try:
        os.replace(source, staged_source)
        _atomic_write(staged_source / LEGACY_RETIREMENT_FILE, metadata_data)
        month_dir.mkdir(parents=True, exist_ok=True)
        os.replace(staged_source, target)
        if inject_readme_failure:
            raise LifecycleError("WI-README-STALE", "injected legacy retirement failure")
        refresh_readme(root)
        _legacy_retirement_entry(target, target / LEGACY_RETIREMENT_FILE)
    except BaseException:
        if target.exists() and not staged_source.exists():
            os.replace(target, staged_source)
        (staged_source / LEGACY_RETIREMENT_FILE).unlink(missing_ok=True)
        if staged_source.exists() and not source.exists():
            os.replace(staged_source, source)
        _restore_readme_snapshot(readme, readme_before)
        if created_month and month_dir.is_dir() and not any(month_dir.iterdir()):
            month_dir.rmdir()
        if created_archive and archive.is_dir() and not any(archive.iterdir()):
            archive.rmdir()
        raise
    finally:
        shutil.rmtree(transaction, ignore_errors=True)
    return target


def start_item(root: Path, slug: str, status_data: bytes, *, inject_readme_failure: bool = False) -> Path:
    _validate_slug(slug)
    _validate_active_status_bytes(status_data)
    is_staged = _parse_fields(status_data.decode("utf-8")).get("template") == "staged"
    admission_ledger = _staged_admission_ledger_bytes(slug, status_data) if is_staged else None
    work_items = _work_items_root(root)
    locations = _category_locations(root, CATEGORIES["work-item"], slug)
    backlog = work_items / "backlog" / f"{slug}.md"
    if locations != [backlog]:
        failure = "WI-CATEGORY-DUAL-LOCATION" if len(locations) > 1 else "WI-INVALID-TARGET"
        raise LifecycleError(failure, f"start requires exactly one backlog candidate: {slug}")
    _preflight_readme(root)
    active_parent = work_items / "active"
    active_parent.mkdir(parents=True, exist_ok=True)
    target = active_parent / slug
    temp = Path(tempfile.mkdtemp(prefix=f".{slug}.", dir=active_parent))
    moved_candidate = temp / "admission.md"
    committed = False
    try:
        os.replace(backlog, moved_candidate)
        _atomic_write(temp / "status.md", status_data)
        if admission_ledger is not None:
            _atomic_write(temp / "agent-runs.jsonl", admission_ledger)
            errors = _validator_module().validate_work_item(temp)
            if errors:
                raise LifecycleError("WI-LEDGER-BOOTSTRAP-INVALID", "; ".join(errors))
        os.replace(temp, target)
        committed = True
    finally:
        if not committed:
            if moved_candidate.exists() and not backlog.exists():
                backlog.parent.mkdir(parents=True, exist_ok=True)
                os.replace(moved_candidate, backlog)
            shutil.rmtree(temp, ignore_errors=True)
    if inject_readme_failure:
        raise LifecycleError("WI-README-STALE", "injected failure after canonical success")
    try:
        refresh_readme(root)
    except LifecycleError as exc:
        raise LifecycleError("WI-README-STALE", str(exc)) from exc
    return target


def update_status(root: Path, slug: str, status_data: bytes, *, inject_readme_failure: bool = False) -> Path:
    _validate_active_status_bytes(status_data)
    target = resolve_category(root, f"work-item:{slug}")
    if target.parent.name != "active" or not target.is_dir():
        raise LifecycleError("WI-INVALID-TARGET", "status update requires an active work-item")
    _preflight_readme(root)
    status = target / "status.md"
    _atomic_write(status, status_data)
    if inject_readme_failure:
        raise LifecycleError("WI-README-STALE", "injected failure after canonical success")
    try:
        refresh_readme(root)
    except LifecycleError as exc:
        raise LifecycleError("WI-README-STALE", str(exc)) from exc
    return status


def _validate_closure(data: bytes, terminal_instant: str) -> None:
    try:
        fields = _parse_fields(data.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise LifecycleError("WI-CATEGORY-TERMINAL-EVIDENCE-MISSING", "closure must be UTF-8") from exc
    required = {"closed", "outcome", "evidence", "residual risk"}
    missing = sorted(key for key in required if not fields.get(key))
    if missing:
        raise LifecycleError(
            "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
            f"closure missing fields: {', '.join(missing)}",
        )
    if fields["closed"] != terminal_instant:
        raise LifecycleError(
            "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
            "closure Closed does not match requested terminal instant",
        )
    _strict_utc(fields["closed"])


def _terminalize_status(data: bytes) -> bytes:
    if _schema_marker_occurrences(data, "status.md"):
        raise LifecycleError(
            "WI-CATEGORY-SCHEMA-INVALID",
            "active status must not contain a lifecycle schema marker",
        )
    text = data.decode("utf-8")
    replaced, count = re.subn(
        r"(?im)^(\s*status\s*:\s*)(active|blocked)\s*$",
        r"\1completed",
        text,
        count=1,
    )
    if count != 1:
        raise LifecycleError(
            "WI-CATEGORY-STATUS-INVALID",
            "active V1 status has no single active/blocked status field",
        )
    return _stamp_schema_marker(replaced.encode("utf-8"), "status.md")


SCRATCH_REGENERATION_MARKER = (
    "Scratch evidence: regeneration-only; all load-bearing observations retained."
)


def _scratch_tombstone(original: Path, slug: str, run_id: str, entry_id: str) -> Path:
    name = _validator_module().scratch_tombstone_name(slug, run_id, entry_id)
    return original.with_name(name)


def _classify_scratch_entry(classifier, path: Path, root: Path):
    try:
        return classifier.classify_owned_tree(path, root)
    except classifier.OwnedTreeClassificationError as exc:
        failure = {
            "SCRATCH-INVENTORY-UNSAFE": "WI-SCRATCH-UNSAFE-ENTRY",
            "SCRATCH-INVENTORY-DRIFT": "WI-SCRATCH-IDENTITY-DRIFT",
        }.get(exc.failure_id, "WI-SCRATCH-PROOF-FAILED")
        raise LifecycleError(failure, str(exc)) from exc


def _verify_scratch_proof(
    snapshot,
    proof: dict,
    canonical_pointer: Path,
) -> None:
    kind = proof["kind"]
    if kind == "git-object-set":
        if not snapshot.git_check_complete or not snapshot.all_git_recoverable:
            raise LifecycleError(
                "WI-SCRATCH-PROOF-FAILED",
                "scratch bytes are not completely recoverable from the repository object store",
            )
        return
    if kind != "accepted-artifact":
        raise LifecycleError("WI-SCRATCH-PROOF-FAILED", f"unsupported proof kind: {kind!r}")
    try:
        artifact = canonical_pointer.read_bytes()
    except OSError as exc:
        raise LifecycleError(
            "WI-SCRATCH-PROOF-FAILED", "accepted artifact is unreadable"
        ) from exc
    if hashlib.sha256(artifact).hexdigest() != proof["artifactSha256"]:
        raise LifecycleError("WI-SCRATCH-PROOF-FAILED", "accepted artifact digest differs")
    try:
        text = artifact.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LifecycleError(
            "WI-SCRATCH-PROOF-FAILED", "accepted artifact is not UTF-8"
        ) from exc
    if SCRATCH_REGENERATION_MARKER not in text:
        raise LifecycleError(
            "WI-SCRATCH-PROOF-FAILED", "accepted artifact lacks the regeneration marker"
        )


def _relocate_scratch_pointer(root: Path, pointer: Path) -> Path:
    if pointer.is_file():
        return pointer
    try:
        relative = pointer.relative_to(root)
    except ValueError:
        return pointer
    parts = relative.parts
    if len(parts) < 4 or parts[:2] != ("work-items", "active"):
        return pointer
    locations = _category_locations(root, CATEGORIES["work-item"], parts[2])
    archived = [path for path in locations if "archive" in path.parts]
    return archived[0].joinpath(*parts[3:]) if len(archived) == 1 else pointer


def _scratch_namespace_entries(owner_root: Path) -> tuple[set[Path], set[Path]]:
    """Return present original/tombstone leaf roots without following links."""

    classifier = _scratch_classifier_module()
    try:
        inspection = classifier.inspect_owned_namespace(owner_root)
    except LifecycleError:
        raise
    except (OSError, classifier.OwnedTreeClassificationError) as exc:
        raise LifecycleError("WI-SCRATCH-UNSAFE-ENTRY", str(exc)) from exc
    return set(inspection.originals), set(inspection.tombstones)


def _scratch_disposition_plan(
    root: Path,
    item: Path,
    *,
    archived: bool,
) -> tuple[ScratchDisposition, ...]:
    ledger = item / "agent-runs.jsonl"
    owner_root = root / ".scratch" / "work-items" / item.name
    classifier = _scratch_classifier_module()
    try:
        owner_inspection = classifier.inspect_root_no_follow(owner_root)
    except classifier.OwnedTreeClassificationError as exc:
        raise LifecycleError("WI-SCRATCH-UNSAFE-ENTRY", str(exc)) from exc
    if not ledger.exists():
        if owner_inspection.exists:
            raise LifecycleError(
                "WI-SCRATCH-OWNERSHIP-INCOMPLETE",
                "canonical scratch namespace exists without a terminal owner declaration",
            )
        return ()

    validator = _validator_module()
    errors: list[str] = []
    raw_metadata: list[dict[str, object]] = []
    events = validator.load_jsonl(ledger, errors, raw_metadata)
    effective_events, _migration_counts, projection_errors = validator.project_legacy_obligation_migrations(
        events, raw_metadata, item
    )
    errors.extend(projection_errors)
    for event in effective_events:
        entries = event.get("scratchEvidence")
        if entries is not None and (
            not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries)
        ):
            errors.append(f"{event.get('runId')}: scratchEvidence must be a list of objects")
    validator.validate_scratch_ownership(effective_events, item, errors)
    if errors:
        raise LifecycleError("WI-LEDGER-UNSETTLED", "; ".join(errors))
    recorded: list[tuple[str, dict]] = []
    for event in effective_events:
        for entry in event.get("scratchEvidence", []):
            recorded.append((event["runId"], entry))
    if not recorded:
        if owner_inspection.exists:
            raise LifecycleError(
                "WI-SCRATCH-OWNERSHIP-INCOMPLETE",
                "canonical scratch namespace exists without a terminal owner declaration",
            )
        return ()

    originals_present, tombstones_present = _scratch_namespace_entries(owner_root)
    expected_originals: set[Path] = set()
    expected_tombstones: set[Path] = set()
    plans: list[ScratchDisposition] = []
    for run_id, entry in recorded:
        original = root / Path(entry["path"])
        tombstone = _scratch_tombstone(original, item.name, run_id, entry["entryId"])
        expected_originals.add(original)
        expected_tombstones.add(tombstone)
        original_exists = original in originals_present
        tombstone_exists = tombstone in tombstones_present
        if original_exists and tombstone_exists:
            raise LifecycleError(
                "WI-SCRATCH-DISPOSITION-CONFLICT",
                f"both original and tombstone exist for {entry['path']}",
            )
        if entry["disposition"] == "retain" and (tombstone_exists or not original_exists):
            raise LifecycleError(
                "WI-SCRATCH-RETAINED-EVIDENCE-MISSING",
                f"retained scratch evidence is missing or tombstoned: {entry['path']}",
            )
        if not original_exists and not tombstone_exists:
            if not archived:
                raise LifecycleError(
                    "WI-SCRATCH-OWNERSHIP-INCOMPLETE",
                    f"declared scratch evidence is missing: {entry['path']}",
                )
            if entry["disposition"] == "delete":
                continue
        pointer_errors: list[str] = []
        pointer = validator.resolve_scratch_pointer(
            item,
            entry["canonicalPointer"],
            "scratchEvidence.canonicalPointer",
            run_id,
            pointer_errors,
        )
        if pointer is None or pointer_errors:
            raise LifecycleError(
                "WI-SCRATCH-POINTER-OUTSIDE-ITEM",
                "; ".join(pointer_errors) or "missing canonical pointer",
            )
        if entry["disposition"] == "retain":
            try:
                retained = classifier.inspect_root_no_follow(original)
            except classifier.OwnedTreeClassificationError as exc:
                raise LifecycleError("WI-SCRATCH-RETAINED-EVIDENCE-MISSING", str(exc)) from exc
            if not retained.exists or retained.is_link_or_reparse or not retained.is_directory:
                raise LifecycleError(
                    "WI-SCRATCH-RETAINED-EVIDENCE-MISSING",
                    f"retained scratch root is unavailable: {entry['path']}",
                )
            snapshot = None
            proof = None
        else:
            source = tombstone if tombstone_exists else original
            snapshot = _classify_scratch_entry(classifier, source, root)
            proof = entry["proof"]
            _verify_scratch_proof(snapshot, proof, pointer)
        plans.append(
            ScratchDisposition(
                original=original,
                tombstone=tombstone,
                disposition=entry["disposition"],
                proof=proof,
                canonical_pointer=pointer,
                snapshot=snapshot,
            )
        )

    if originals_present - expected_originals or tombstones_present - expected_tombstones:
        raise LifecycleError(
            "WI-SCRATCH-OWNERSHIP-INCOMPLETE",
            "scratch namespace contains an undeclared evidence root",
        )
    return tuple(plans)


def _remove_scratch_tree(tree_root: Path) -> None:
    """Remove one already-proven tree without following links or reparses."""

    classifier = _scratch_classifier_module()
    directories: list[Path] = []
    stack = [tree_root]
    while stack:
        directory = stack.pop()
        inspection = classifier.inspect_root_no_follow(directory)
        if not inspection.exists or inspection.is_link_or_reparse or not inspection.is_directory:
            raise OSError(f"unsafe directory during removal: {directory.name}")
        directories.append(directory)
        with os.scandir(directory) as entries:
            children = list(entries)
        for entry in children:
            child = classifier.inspect_root_no_follow(Path(entry.path))
            if child.is_link_or_reparse:
                raise OSError(f"unsafe link or reparse during removal: {entry.name}")
            if child.is_directory:
                stack.append(Path(entry.path))
            elif child.exists and stat.S_ISREG(os.lstat(entry.path).st_mode):
                Path(entry.path).unlink()
            else:
                raise OSError(f"unsafe non-regular entry during removal: {entry.name}")
    for directory in reversed(directories):
        directory.rmdir()


def _settle_scratch_dispositions(root: Path, plans: tuple[ScratchDisposition, ...]) -> None:
    classifier = _scratch_classifier_module()
    for plan in plans:
        if plan.disposition == "retain":
            continue
        try:
            original_state = classifier.inspect_root_no_follow(plan.original)
            tombstone_state = classifier.inspect_root_no_follow(plan.tombstone)
        except classifier.OwnedTreeClassificationError as exc:
            raise LifecycleError("WI-SCRATCH-DISPOSITION-PENDING", str(exc)) from exc
        if original_state.exists and tombstone_state.exists:
            raise LifecycleError(
                "WI-SCRATCH-DISPOSITION-CONFLICT", "both original and tombstone exist"
            )
        source = plan.tombstone if tombstone_state.exists else plan.original
        source_state = tombstone_state if tombstone_state.exists else original_state
        if not source_state.exists:
            continue
        if source_state.is_link_or_reparse or not source_state.is_directory:
            raise LifecycleError(
                "WI-SCRATCH-DISPOSITION-PENDING",
                "scratch root changed to an unsafe identity after preflight",
            )
        try:
            snapshot = classifier.classify_owned_tree(source, root)
            if plan.snapshot is None or not classifier.identity_matches(snapshot, plan.snapshot):
                raise LifecycleError(
                    "WI-SCRATCH-DISPOSITION-PENDING", "scratch identity drifted after preflight"
                )
            canonical_pointer = _relocate_scratch_pointer(root, plan.canonical_pointer)
            assert plan.proof is not None
            _verify_scratch_proof(snapshot, plan.proof, canonical_pointer)
            if source == plan.original:
                os.replace(plan.original, plan.tombstone)
            tombstone_snapshot = classifier.classify_owned_tree(plan.tombstone, root)
            if not classifier.identity_matches(tombstone_snapshot, plan.snapshot):
                raise LifecycleError(
                    "WI-SCRATCH-DISPOSITION-PENDING", "scratch identity drifted after tombstone"
                )
            _verify_scratch_proof(tombstone_snapshot, plan.proof, canonical_pointer)
            _remove_scratch_tree(plan.tombstone)
        except LifecycleError:
            raise
        except (OSError, classifier.OwnedTreeClassificationError) as exc:
            raise LifecycleError(
                "WI-SCRATCH-DISPOSITION-PENDING",
                f"archived item retains retryable scratch disposition: {exc}",
            ) from exc


def _validate_item_before_close(item: Path) -> None:
    validator = _validator_module()
    ledger = item / "agent-runs.jsonl"
    status_text = (item / "status.md").read_text(encoding="utf-8")
    v1_staged = _parse_fields(status_text).get("template") == "staged"
    if ledger.exists():
        errors = validator.validate_work_item(
            item,
            validate_status_file=not v1_staged,
        )
        if v1_staged:
            _validate_active_status_bytes(status_text.encode("utf-8"))
    else:
        errors = []
        validator.validate_status(item, [], errors)
        if v1_staged:
            errors = []
            _validate_active_status_bytes(status_text.encode("utf-8"))
    if errors:
        raise LifecycleError("WI-LEDGER-UNSETTLED", "; ".join(errors))


def _bug_disposition_fail(failure_id: str, message: str) -> LifecycleError:
    return LifecycleError(failure_id, message)


def _single_line_manifest_text(row: dict, key: str) -> str:
    value = row.get(key)
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > BUG_DISPOSITION_TEXT_LIMIT
        or "\n" in value
        or "\r" in value
    ):
        raise _bug_disposition_fail(
            "WI-BUG-DISPOSITIONS-INVALID",
            f"bug disposition {key} must be one non-empty bounded line",
        )
    return value.strip()


def _load_bug_disposition_manifest(
    item: Path,
    slug: str,
    terminal_instant: str,
) -> tuple[Path, bytes, dict]:
    manifest = item / BUG_DISPOSITIONS_MANIFEST
    if manifest.is_symlink() or not manifest.is_file():
        raise _bug_disposition_fail(
            "WI-BUG-DISPOSITIONS-MISSING",
            f"active work-item requires {BUG_DISPOSITIONS_MANIFEST}: {slug}",
        )
    try:
        data = manifest.read_bytes()
        payload = json.loads(data.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _bug_disposition_fail(
            "WI-BUG-DISPOSITIONS-INVALID",
            f"invalid {BUG_DISPOSITIONS_MANIFEST}: {slug}",
        ) from exc
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schemaVersion", "workItem", "closedAt", "bugs"}
        or payload.get("schemaVersion") != BUG_DISPOSITIONS_SCHEMA_VERSION
        or payload.get("workItem") != slug
        or payload.get("closedAt") != terminal_instant
        or not isinstance(payload.get("bugs"), list)
    ):
        raise _bug_disposition_fail(
            "WI-BUG-DISPOSITIONS-INVALID",
            f"bug disposition manifest header differs: {slug}",
        )
    return manifest, data, payload


def _context_bug_files(root: Path, slug: str) -> dict[str, Path]:
    bug_root = _work_items_root(root) / CATEGORIES["bug"].current_root
    result: dict[str, Path] = {}
    if not bug_root.is_dir():
        return result
    for path in sorted(bug_root.glob("*.md")):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise _bug_disposition_fail(
                "WI-BUG-DISPOSITIONS-INVALID",
                f"current bug record is not readable UTF-8: {path.name}",
            ) from exc
        fields = _parse_fields(text)
        if fields.get("context") != slug:
            continue
        _validate_slug(path.stem)
        if path.stem in result:
            raise _bug_disposition_fail(
                "WI-BUG-DISPOSITIONS-INCOMPLETE",
                f"duplicate context-linked bug identity: {path.stem}",
            )
        result[path.stem] = path
    return result


def _terminal_bug_bytes(
    before: bytes,
    *,
    current_status: str,
    terminal_status: str,
    terminal_instant: str,
    resolution: str,
    evidence: str,
) -> bytes:
    try:
        text = before.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _bug_disposition_fail(
            "WI-BUG-DISPOSITIONS-INVALID", "bug record is not UTF-8"
        ) from exc
    fields = _parse_fields(text)
    if fields.get("status") != current_status:
        raise _bug_disposition_fail(
            "WI-BUG-DISPOSITIONS-DRIFT", "bug status changed after preflight"
        )
    if any(fields.get(key) for key in ("terminal-at", "resolution", "evidence")):
        raise _bug_disposition_fail(
            "WI-BUG-DISPOSITIONS-INVALID",
            "current bug already carries terminal evidence",
        )
    replaced, count = re.subn(
        r"(?im)^(\s*(?:-\s*)?status\s*:\s*)[^\r\n]+(?=\r?$)",
        rf"\g<1>{terminal_status}",
        text,
        count=1,
    )
    if count != 1:
        raise _bug_disposition_fail(
            "WI-BUG-DISPOSITIONS-INVALID", "bug requires one status field"
        )
    newline = "\r\n" if "\r\n" in text and text.count("\n") == text.count("\r\n") else "\n"
    separator = "" if replaced.endswith("\n") else newline
    return (
        replaced
        + separator
        + newline
        + f"Terminal-at: {terminal_instant}{newline}"
        + f"Resolution: {resolution}{newline}"
        + f"Evidence: {evidence}{newline}"
    ).encode("utf-8")


def _prepare_bug_dispositions(
    root: Path,
    item: Path,
    slug: str,
    terminal_instant: str,
) -> tuple[Path, bytes, tuple[BugDispositionPlan, ...]]:
    manifest, manifest_data, payload = _load_bug_disposition_manifest(
        item, slug, terminal_instant
    )
    linked = _context_bug_files(root, slug)
    rows = payload["bugs"]
    ids = [row.get("id") for row in rows if isinstance(row, dict)]
    if (
        len(ids) != len(rows)
        or any(not isinstance(value, str) or not is_valid_slug(value) for value in ids)
        or len(set(ids)) != len(ids)
    ):
        raise _bug_disposition_fail(
            "WI-BUG-DISPOSITIONS-INVALID",
            "bug disposition ids must be unique canonical slugs",
        )
    if set(ids) != set(linked):
        missing = sorted(set(linked) - set(ids))
        extra = sorted(set(ids) - set(linked))
        raise _bug_disposition_fail(
            "WI-BUG-DISPOSITIONS-INCOMPLETE",
            f"bug disposition set differs (missing={missing}, extra={extra})",
        )
    plans: list[BugDispositionPlan] = []
    bug_category = CATEGORIES["bug"]
    for row in rows:
        assert isinstance(row, dict)
        bug_id = row["id"]
        action = row.get("action")
        if action not in BUG_DISPOSITION_ACTIONS:
            raise _bug_disposition_fail(
                "WI-BUG-DISPOSITIONS-INVALID", f"invalid bug action: {action!r}"
            )
        expected_fields = (
            {"id", "action", "inputSha256", "status", "resolution", "evidence"}
            if action == "terminalize"
            else {"id", "action", "inputSha256", "status", "reason", "evidence"}
        )
        if set(row) != expected_fields:
            raise _bug_disposition_fail(
                "WI-BUG-DISPOSITIONS-INVALID",
                f"bug disposition fields differ: {bug_id}",
            )
        source = linked[bug_id]
        before = source.read_bytes()
        digest = row.get("inputSha256")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise _bug_disposition_fail(
                "WI-BUG-DISPOSITIONS-INVALID", f"invalid inputSha256: {bug_id}"
            )
        if hashlib.sha256(before).hexdigest() != digest:
            raise _bug_disposition_fail(
                "WI-BUG-DISPOSITIONS-DRIFT", f"bug bytes changed: {bug_id}"
            )
        try:
            fields = _parse_fields(before.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise _bug_disposition_fail(
                "WI-BUG-DISPOSITIONS-INVALID",
                f"current bug record is not UTF-8: {bug_id}",
            ) from exc
        current_status = fields.get("status", "")
        if current_status not in bug_category.current_statuses:
            raise _bug_disposition_fail(
                "WI-BUG-DISPOSITIONS-DRIFT",
                f"bug is not current: {bug_id} ({current_status!r})",
            )
        desired_status = row.get("status")
        _single_line_manifest_text(row, "evidence")
        if action == "preserve-current":
            if desired_status != current_status:
                raise _bug_disposition_fail(
                    "WI-BUG-DISPOSITIONS-INVALID",
                    f"preserve-current status differs: {bug_id}",
                )
            _single_line_manifest_text(row, "reason")
            target = None
            after = before
        else:
            if desired_status not in bug_category.terminal_statuses:
                raise _bug_disposition_fail(
                    "WI-BUG-DISPOSITIONS-INVALID",
                    f"terminal bug status is invalid: {bug_id}",
                )
            resolution = _single_line_manifest_text(row, "resolution")
            evidence = _single_line_manifest_text(row, "evidence")
            after = _terminal_bug_bytes(
                before,
                current_status=current_status,
                terminal_status=desired_status,
                terminal_instant=terminal_instant,
                resolution=resolution,
                evidence=evidence,
            )
            _validate_flat_terminal(bug_category, after)
            target = (
                _work_items_root(root)
                / bug_category.current_root
                / "archive"
                / archive_month(terminal_instant)
                / source.name
            )
            if target.exists():
                raise _bug_disposition_fail(
                    "WI-BUG-DISPOSITIONS-DRIFT",
                    f"bug archive target already exists: {bug_id}",
                )
        plans.append(
            BugDispositionPlan(
                bug_id=bug_id,
                action=action,
                source=source,
                target=target,
                before=before,
                after=after,
                status_before=current_status,
                status_after=desired_status,
            )
        )
    return manifest, manifest_data, tuple(sorted(plans, key=lambda plan: plan.bug_id))


def _bug_disposition_receipt_bytes(
    root: Path,
    slug: str,
    terminal_instant: str,
    manifest_data: bytes,
    closure_data: bytes,
    plans: tuple[BugDispositionPlan, ...],
    readme_sha256: str,
) -> bytes:
    payload = {
        "schemaVersion": BUG_DISPOSITIONS_SCHEMA_VERSION,
        "owner": BUG_DISPOSITIONS_OWNER,
        "workItem": slug,
        "closedAt": terminal_instant,
        "manifestSha256": hashlib.sha256(manifest_data).hexdigest(),
        "closureSha256": hashlib.sha256(closure_data).hexdigest(),
        "readmeSha256": readme_sha256,
        "bugs": [
            {
                "id": plan.bug_id,
                "action": plan.action,
                "statusBefore": plan.status_before,
                "statusAfter": plan.status_after,
                "beforeSha256": hashlib.sha256(plan.before).hexdigest(),
                "afterSha256": hashlib.sha256(plan.after).hexdigest(),
                "source": plan.source.relative_to(_work_items_root(root)).as_posix(),
                "target": (
                    plan.target.relative_to(_work_items_root(root)).as_posix()
                    if plan.target is not None
                    else None
                ),
            }
            for plan in plans
        ],
    }
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _verify_archived_bug_dispositions(
    root: Path,
    archived: Path,
    closure_data: bytes,
    terminal_instant: str,
) -> None:
    slug = archived.name
    try:
        _manifest, manifest_data, manifest = _load_bug_disposition_manifest(
            archived, slug, terminal_instant
        )
    except LifecycleError as exc:
        raise _bug_disposition_fail(
            "WI-IMMUTABLE-ARCHIVE",
            f"archived bug disposition manifest differs: {slug}",
        ) from exc
    receipt_path = archived / BUG_DISPOSITIONS_RECEIPT
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise _bug_disposition_fail(
            "WI-IMMUTABLE-ARCHIVE",
            f"archived work-item lacks {BUG_DISPOSITIONS_RECEIPT}: {slug}",
        )
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _bug_disposition_fail(
            "WI-IMMUTABLE-ARCHIVE", f"invalid bug disposition receipt: {slug}"
        ) from exc
    expected_keys = {
        "schemaVersion",
        "owner",
        "workItem",
        "closedAt",
        "manifestSha256",
        "closureSha256",
        "readmeSha256",
        "bugs",
    }
    if (
        not isinstance(receipt, dict)
        or set(receipt) != expected_keys
        or receipt.get("schemaVersion") != BUG_DISPOSITIONS_SCHEMA_VERSION
        or receipt.get("owner") != BUG_DISPOSITIONS_OWNER
        or receipt.get("workItem") != slug
        or receipt.get("closedAt") != terminal_instant
        or receipt.get("manifestSha256") != hashlib.sha256(manifest_data).hexdigest()
        or receipt.get("closureSha256") != hashlib.sha256(closure_data).hexdigest()
        or not isinstance(receipt.get("readmeSha256"), str)
        or not SHA256_RE.fullmatch(receipt["readmeSha256"])
        or not isinstance(receipt.get("bugs"), list)
    ):
        raise _bug_disposition_fail(
            "WI-IMMUTABLE-ARCHIVE", f"bug disposition receipt binding differs: {slug}"
        )
    rows = manifest["bugs"]
    if len(receipt["bugs"]) != len(rows):
        raise _bug_disposition_fail(
            "WI-IMMUTABLE-ARCHIVE", f"bug disposition receipt count differs: {slug}"
        )
    by_id = {
        row.get("id"): row for row in receipt["bugs"] if isinstance(row, dict)
    }
    if set(by_id) != {row.get("id") for row in rows if isinstance(row, dict)}:
        raise _bug_disposition_fail(
            "WI-IMMUTABLE-ARCHIVE", f"bug disposition receipt ids differ: {slug}"
        )
    work_items = _work_items_root(root)
    for decision in rows:
        if not isinstance(decision, dict):
            raise _bug_disposition_fail(
                "WI-IMMUTABLE-ARCHIVE", f"invalid archived decision row: {slug}"
            )
        result = by_id[decision["id"]]
        required_result_keys = {
            "id",
            "action",
            "statusBefore",
            "statusAfter",
            "beforeSha256",
            "afterSha256",
            "source",
            "target",
        }
        if (
            set(result) != required_result_keys
            or result.get("id") != decision["id"]
            or result.get("action") != decision["action"]
            or result.get("beforeSha256") != decision["inputSha256"]
            or result.get("statusAfter") != decision["status"]
            or result.get("statusBefore") not in CATEGORIES["bug"].current_statuses
            or result.get("source") != f"bugs/{decision['id']}.md"
            or not isinstance(result.get("afterSha256"), str)
            or not SHA256_RE.fullmatch(result["afterSha256"])
        ):
            raise _bug_disposition_fail(
                "WI-IMMUTABLE-ARCHIVE",
                f"archived bug disposition row differs: {decision['id']}",
            )
        if decision["action"] == "terminalize":
            target_relative = result.get("target")
            expected_target = (
                f"bugs/archive/{archive_month(terminal_instant)}/{decision['id']}.md"
            )
            if target_relative != expected_target:
                raise _bug_disposition_fail(
                    "WI-IMMUTABLE-ARCHIVE",
                    f"terminal bug target differs: {decision['id']}",
                )
            assert isinstance(target_relative, str)
            target = _terminalization_bound_path(
                work_items, target_relative, label="archived bug disposition target"
            )
            current = work_items / CATEGORIES["bug"].current_root / f"{decision['id']}.md"
            if (
                not target.is_file()
                or current.exists()
                or hashlib.sha256(target.read_bytes()).hexdigest()
                != result["afterSha256"]
            ):
                raise _bug_disposition_fail(
                    "WI-IMMUTABLE-ARCHIVE",
                    f"terminal bug archive differs: {decision['id']}",
                )
            _validate_flat_terminal(CATEGORIES["bug"], target.read_bytes())
        elif (
            result.get("target") is not None
            or result.get("statusBefore") != decision["status"]
            or result.get("afterSha256") != decision["inputSha256"]
        ):
            raise _bug_disposition_fail(
                "WI-IMMUTABLE-ARCHIVE",
                f"preserved bug receipt differs: {decision['id']}",
            )


def _mkdir_parents_tracked(path: Path, created: list[Path]) -> None:
    missing: list[Path] = []
    cursor = path
    while not cursor.exists():
        missing.append(cursor)
        cursor = cursor.parent
    for directory in reversed(missing):
        directory.mkdir()
        created.append(directory)


def close_item(
    root: Path,
    slug: str,
    closure_data: bytes,
    terminal_instant: str,
    *,
    inject_readme_failure: bool = False,
    inject_bug_failure_after: int | None = None,
) -> Path:
    _validate_slug(slug)
    month = archive_month(terminal_instant)
    _validate_closure(closure_data, terminal_instant)
    archived_closure_data = _stamp_schema_marker(closure_data, "closure.md")
    work_items = _work_items_root(root)
    locations = _category_locations(root, CATEGORIES["work-item"], slug)
    if len(locations) > 1:
        raise LifecycleError("WI-CATEGORY-DUAL-LOCATION", f"duplicate slug: {slug}")
    if len(locations) == 1 and "archive" in locations[0].parts:
        archived = locations[0]
        _archived_work_item_entry(archived)
        existing = archived / "closure.md"
        if (
            not existing.is_file()
            or existing.read_bytes() != archived_closure_data
            or archived.parent.name != month
        ):
            raise LifecycleError("WI-IMMUTABLE-ARCHIVE", f"archived identity differs: {slug}")
        manifest_present = (archived / BUG_DISPOSITIONS_MANIFEST).exists()
        receipt_present = (archived / BUG_DISPOSITIONS_RECEIPT).exists()
        if manifest_present or receipt_present:
            _verify_archived_bug_dispositions(
                root, archived, archived_closure_data, terminal_instant
            )
        scratch_plan = _scratch_disposition_plan(root, archived, archived=True)
        if inject_readme_failure:
            raise LifecycleError("WI-README-STALE", "injected failure after canonical success")
        refresh_readme(root)
        _settle_scratch_dispositions(root, scratch_plan)
        return archived
    active = work_items / "active" / slug
    if locations != [active]:
        raise LifecycleError("WI-INVALID-TARGET", f"close requires one active item: {slug}")
    _validate_item_before_close(active)
    scratch_plan = _scratch_disposition_plan(root, active, archived=False)
    _manifest, manifest_data, bug_plans = _prepare_bug_dispositions(
        root, active, slug, terminal_instant
    )
    _preflight_readme(root)
    closure_path = active / "closure.md"
    prior_closure = closure_path.read_bytes() if closure_path.exists() else None
    status_path = active / "status.md"
    prior_status = status_path.read_bytes()
    target = work_items / "archive" / month / slug
    readme = work_items / "README.md"
    readme_existed = readme.is_file()
    readme_before = readme.read_bytes() if readme_existed else b""
    created_dirs: list[Path] = []
    touched_bugs: list[BugDispositionPlan] = []
    item_moved = False
    receipt_path = target / BUG_DISPOSITIONS_RECEIPT
    try:
        for index, plan in enumerate(bug_plans, start=1):
            if plan.action != "terminalize":
                continue
            if plan.source.read_bytes() != plan.before or plan.target is None:
                raise _bug_disposition_fail(
                    "WI-BUG-DISPOSITIONS-DRIFT",
                    f"bug changed after preflight: {plan.bug_id}",
                )
            touched_bugs.append(plan)
            _atomic_write(plan.source, plan.after)
            _mkdir_parents_tracked(plan.target.parent, created_dirs)
            os.replace(plan.source, plan.target)
            if inject_bug_failure_after == index:
                raise _bug_disposition_fail(
                    "WI-BUG-DISPOSITIONS-DRIFT",
                    f"injected bug disposition failure after row {index}",
                )
        _atomic_write(closure_path, archived_closure_data)
        _atomic_write(status_path, _terminalize_status(prior_status))
        _mkdir_parents_tracked(target.parent, created_dirs)
        os.replace(active, target)
        item_moved = True
        if inject_readme_failure:
            raise LifecycleError("WI-README-STALE", "injected failure after canonical success")
        readme_sha256 = refresh_readme(root)
        receipt_data = _bug_disposition_receipt_bytes(
            root,
            slug,
            terminal_instant,
            manifest_data,
            archived_closure_data,
            bug_plans,
            readme_sha256,
        )
        _atomic_write(receipt_path, receipt_data)
        _verify_archived_bug_dispositions(
            root, target, archived_closure_data, terminal_instant
        )
    except BaseException as exc:
        rollback_failures: list[str] = []

        def attempt(label: str, action) -> None:
            try:
                action()
            except BaseException as rollback_exc:
                rollback_failures.append(f"{label}: {rollback_exc}")

        if receipt_path.exists():
            attempt("remove receipt", receipt_path.unlink)
        if item_moved and target.exists() and not active.exists():
            attempt("restore active item", lambda: os.replace(target, active))
        if active.is_dir():
            restored_closure = active / "closure.md"
            restored_status = active / "status.md"
            if prior_closure is None:
                if restored_closure.exists():
                    attempt("remove closure", restored_closure.unlink)
            else:
                attempt(
                    "restore closure",
                    lambda: _atomic_write(restored_closure, prior_closure),
                )
            attempt("restore status", lambda: _atomic_write(restored_status, prior_status))
        else:
            rollback_failures.append("restore active item: active directory is unavailable")
        for plan in reversed(touched_bugs):
            assert plan.target is not None
            if plan.target.exists() and not plan.source.exists():
                attempt(
                    f"restore bug location {plan.bug_id}",
                    lambda plan=plan: os.replace(plan.target, plan.source),
                )
            if plan.source.exists():
                attempt(
                    f"restore bug bytes {plan.bug_id}",
                    lambda plan=plan: _atomic_write(plan.source, plan.before),
                )
            else:
                rollback_failures.append(
                    f"restore bug bytes {plan.bug_id}: current source is unavailable"
                )
        if readme_existed:
            attempt("restore README", lambda: _atomic_write(readme, readme_before))
        elif readme.exists():
            attempt("remove generated README", readme.unlink)
        for directory in reversed(created_dirs):
            try:
                directory.rmdir()
            except OSError:
                pass
        if rollback_failures:
            raise _bug_disposition_fail(
                "WI-BUG-DISPOSITIONS-ROLLBACK",
                "bug disposition rollback failed: " + "; ".join(rollback_failures),
            ) from exc
        raise
    _settle_scratch_dispositions(root, scratch_plan)
    return target


def reopen_item(
    root: Path,
    archived_slug: str,
    successor_slug: str,
    status_data: bytes,
    *,
    inject_readme_failure: bool = False,
) -> Path:
    archived = resolve_category(root, f"work-item:{archived_slug}")
    if "archive" not in archived.parts:
        raise LifecycleError("WI-INVALID-TARGET", "reopen source must be archived")
    _validate_slug(successor_slug)
    _validate_active_status_bytes(status_data)
    fields = _parse_fields(status_data.decode("utf-8"))
    if fields.get("reopens") != archived_slug:
        raise LifecycleError(
            "WI-CATEGORY-STATUS-INVALID",
            f"successor must declare Reopens: {archived_slug}",
        )
    if _category_locations(root, CATEGORIES["work-item"], successor_slug):
        raise LifecycleError("WI-CATEGORY-DUAL-LOCATION", "successor slug already exists")
    _preflight_readme(root)
    active_parent = _work_items_root(root) / "active"
    active_parent.mkdir(parents=True, exist_ok=True)
    target = active_parent / successor_slug
    temp = Path(tempfile.mkdtemp(prefix=f".{successor_slug}.", dir=active_parent))
    committed = False
    try:
        _atomic_write(temp / "status.md", status_data)
        os.replace(temp, target)
        committed = True
    finally:
        if not committed:
            shutil.rmtree(temp, ignore_errors=True)
    if inject_readme_failure:
        raise LifecycleError("WI-README-STALE", "injected failure after canonical success")
    try:
        refresh_readme(root)
    except LifecycleError as exc:
        raise LifecycleError("WI-README-STALE", str(exc)) from exc
    return target


def audit_categories(root: Path) -> tuple[str, ...]:
    work_items = _work_items_root(root)
    allowed_roots = {"backlog", "active", "archive"}
    allowed_roots.update(
        category.current_root
        for category in CATEGORIES.values()
        if category.current_kind == "flat"
    )
    if work_items.is_dir():
        unknown_roots = sorted(
            path.name
            for path in work_items.iterdir()
            if path.is_dir() and path.name not in allowed_roots
        )
        if unknown_roots:
            noun = "directory" if len(unknown_roots) == 1 else "directories"
            raise LifecycleError(
                "WI-CATEGORY-UNKNOWN-ROOT",
                f"unknown top-level work-items {noun}: " + ", ".join(unknown_roots),
            )
    decision_v0_records = _preflight_current_decision_v0(root)
    decision_h1_records = _preflight_current_decision_h1(root)
    legacy_read_compatible: list[str] = []
    for category in CATEGORIES.values():
        slugs: set[str] = set()
        if category.current_kind == "work-item":
            slugs.update(path.stem for path in (work_items / "backlog").glob("*.md"))
            slugs.update(path.name for path in (work_items / "active").glob("*") if path.is_dir())
            archive = work_items / "archive"
        else:
            current = work_items / category.current_root
            slugs.update(path.stem for path in current.glob("*.md"))
            archive = current / "archive"
        if archive.is_dir():
            for month in archive.iterdir():
                if not month.is_dir():
                    continue
                if category.current_kind == "work-item":
                    slugs.update(path.name for path in month.iterdir() if path.is_dir())
                else:
                    slugs.update(path.stem for path in month.glob("*.md"))
        for slug in sorted(slugs):
            locations = _category_locations(root, category, slug)
            if len(locations) > 1:
                raise LifecycleError(
                    "WI-CATEGORY-DUAL-LOCATION",
                    f"{category.name}:{slug} has {len(locations)} locations",
                )
            if not is_valid_slug(slug):
                if len(locations) != 1 or "archive" not in locations[0].parts:
                    _validate_slug(slug)
                legacy = locations[0]
                if category.name == "work-item":
                    entry = _archived_work_item_entry(legacy)
                    if entry.classification == LEGACY_READ_CLASSIFICATION:
                        fields = _parse_fields((legacy / "closure.md").read_text(encoding="utf-8"))
                        closed = fields.get("closed", "")
                        if not closed or not fields.get("outcome"):
                            raise LifecycleError(
                                "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
                                f"legacy archive lacks terminal evidence: {legacy}",
                            )
                        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", closed) or closed[:7] != legacy.parent.name:
                            raise LifecycleError(
                                "WI-CATEGORY-ARCHIVE-MONTH-MISMATCH",
                                f"{category.name}:{slug} does not match archive month",
                            )
                else:
                    instant = _validate_flat_terminal(category, legacy.read_bytes())
                    if legacy.parent.name != archive_month(instant):
                        raise LifecycleError(
                            "WI-CATEGORY-ARCHIVE-MONTH-MISMATCH",
                            f"{category.name}:{slug} belongs in archive/{archive_month(instant)}",
                        )
                legacy_read_compatible.append(
                    legacy.relative_to(work_items).as_posix()
                )
                continue
            if category.current_kind == "flat" and locations:
                path = locations[0]
                archived = "archive" in path.parts
                decision_v0 = (
                    decision_v0_records.get(path.name)
                    if category.name == "decision" and not archived
                    else None
                )
                decision_h1 = (
                    decision_h1_records.get(path.name)
                    if category.name == "decision" and not archived
                    else None
                )
                if decision_v0 is not None:
                    status = decision_v0.raw_status
                elif decision_h1 is not None:
                    status = decision_h1.admitted_current_status or ""
                else:
                    fields = _parse_fields(path.read_text(encoding="utf-8"))
                    status = fields.get("status", "")
                if archived and status in category.current_statuses:
                    raise LifecycleError(
                        "WI-CATEGORY-CURRENT-IN-ARCHIVE",
                        f"{category.name}:{slug} has current status in archive",
                    )
                if not archived and status in category.terminal_statuses:
                    raise LifecycleError(
                        "WI-CATEGORY-TERMINAL-IN-CURRENT",
                        f"{category.name}:{slug} has terminal status in current root",
                    )
                if (
                    category.name == "decision"
                    and not archived
                    and status in category.current_statuses
                ):
                    decision = decision_v0 or decision_h1 or _validate_current_decision_record(path, slug)
                    if decision.format in {DECISION_FORMAT_V0, DECISION_FORMAT_H1}:
                        legacy_read_compatible.append(
                            path.relative_to(work_items).as_posix()
                        )

    active = work_items / "active"
    if active.is_dir():
        for item in sorted(path for path in active.iterdir() if path.is_dir()):
            if (item / BUG_DISPOSITIONS_MANIFEST).exists():
                raise LifecycleError(
                    "WI-BUG-DISPOSITIONS-PENDING",
                    f"work-item:{item.name} has an unapplied bug disposition manifest",
                )
            fields = _parse_fields((item / "status.md").read_text(encoding="utf-8"))
            if fields.get("status") in CATEGORIES["work-item"].terminal_statuses:
                raise LifecycleError(
                    "WI-CATEGORY-TERMINAL-IN-CURRENT",
                    f"work-item:{item.name} has terminal status in active/",
                )
    archive_root = work_items / "archive"
    if archive_root.is_dir():
        for month in sorted(path for path in archive_root.iterdir() if path.is_dir()):
            for item in sorted(path for path in month.iterdir() if path.is_dir()):
                manifest = item / BUG_DISPOSITIONS_MANIFEST
                receipt = item / BUG_DISPOSITIONS_RECEIPT
                if not manifest.exists() and not receipt.exists():
                    continue
                closure = item / "closure.md"
                if not closure.is_file():
                    raise LifecycleError(
                        "WI-IMMUTABLE-ARCHIVE",
                        f"archived disposition owner lacks closure: {item.name}",
                    )
                closure_data = closure.read_bytes()
                fields = _parse_fields(closure_data.decode("utf-8"))
                _verify_archived_bug_dispositions(
                    root, item, closure_data, fields.get("closed", "")
                )
    return tuple(sorted(legacy_read_compatible))


def audit(root: Path) -> tuple[str, ...]:
    _recover_all_transitions(root)
    legacy_read_compatible = audit_categories(root)
    check_readme(root)
    return legacy_read_compatible


def _active_migration_item(root: Path, slug: str) -> Path:
    _validate_slug(slug)
    item = _work_items_root(root) / "active" / slug
    if not item.is_dir() or _lifecycle_path_has_reparse(item):
        raise LifecycleError("WI-INVALID-TARGET", f"active work item is missing or unsafe: {slug}")
    return item


def _repository_root_for_item(item: Path) -> Path:
    for parent in (item, *item.parents):
        if parent.name == "work-items":
            return parent.parent
    raise LifecycleError("WI-INVALID-TARGET", "path is not owned by a work-items root")


def _require_lifecycle_mutation_path(root: Path, path: Path, *, failure_id: str) -> Path:
    path = _lifecycle_unresolved_absolute(path)
    _lifecycle_reject_unreduced_reparse(
        path, failure_id=failure_id, message="lifecycle mutation path contains a link or reparse point"
    )
    repository = _lifecycle_unresolved_absolute(Path(root))
    _lifecycle_reject_unreduced_reparse(
        repository, failure_id=failure_id, message="repository root contains a link or reparse point"
    )
    repository = repository.resolve()
    candidate = path.resolve(strict=False)
    try:
        candidate.relative_to(repository)
    except ValueError as exc:
        raise LifecycleError(failure_id, "lifecycle mutation path escapes repository") from exc
    return path


def _migration_receipt_bytes(facts: dict) -> bytes:
    return (json.dumps(facts, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _reconcile_migration_receipt(item: Path, facts: dict) -> None:
    root = _repository_root_for_item(item)
    receipt = item / "ledger-migration-receipts" / f"{facts['operationId']}.json"
    receipt = _require_lifecycle_mutation_path(
        root, receipt, failure_id="WI-LEDGER-MIGRATION-RECEIPT-MISMATCH"
    )
    wanted = _migration_receipt_bytes(facts)
    if receipt.exists():
        current = receipt.read_bytes()
        if current == wanted:
            return
        quarantine = receipt.with_name(f"{receipt.name}.conflict-{_sha256_bytes(current)[:16]}")
        quarantine = _require_lifecycle_mutation_path(
            root, quarantine, failure_id="WI-LEDGER-MIGRATION-RECEIPT-MISMATCH"
        )
        if quarantine.exists() and quarantine.read_bytes() != current:
            raise LifecycleError("WI-LEDGER-MIGRATION-RECEIPT-MISMATCH", "receipt quarantine conflicts")
        if not quarantine.exists():
            os.replace(receipt, quarantine)
    _atomic_write(receipt, wanted)
    if receipt.read_bytes() != wanted:
        raise LifecycleError("WI-LEDGER-MIGRATION-RECEIPT-MISMATCH", "receipt readback differs")


def _committed_migration_facts(
    item: Path,
    *,
    target_run_id: str,
    target_event_sha256: str,
    expected_before_sha256: str,
    operation_id: str,
    normalization_kind: str,
) -> dict | None:
    ledger_owner = _load_agent_run_ledger()
    ledger_path = item / "agent-runs.jsonl"
    root = _repository_root_for_item(item)
    ledger_path = _require_lifecycle_mutation_path(
        root, ledger_path, failure_id="WI-LEDGER-MIGRATION-TOPOLOGY"
    )
    data = ledger_path.read_bytes()
    raw_lines = data.splitlines(keepends=True)
    validator = ledger_owner.load_validator()
    parse_errors: list[str] = []
    metadata: list[dict[str, object]] = []
    events = validator.load_jsonl(ledger_path, parse_errors, metadata)
    if parse_errors:
        raise LifecycleError("WI-LEDGER-MIGRATION-TOPOLOGY", "; ".join(parse_errors))
    _effective, _counters, projection_errors = validator.project_legacy_obligation_migrations(
        events, metadata, item
    )
    if projection_errors:
        raise LifecycleError("WI-LEDGER-MIGRATION-TOPOLOGY", "; ".join(projection_errors))
    for index, raw in enumerate(raw_lines):
        text = raw.rstrip(b"\r\n")
        try:
            event = json.loads(text.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            continue
        if event.get("runId") != f"ledger-migration-{operation_id}":
            continue
        control_errors: list[str] = []
        validator.validate_event(event, item, set(), control_errors)
        if control_errors:
            raise LifecycleError("WI-LEDGER-MIGRATION-TOPOLOGY", "; ".join(control_errors))
        if (
            event.get("eventKind") != "legacy-obligation-migration"
            or event.get("migrationAction") != "apply"
            or event.get("normalizationKind", "invalid-finding-class") != normalization_kind
            or event.get("migratesRunId") != target_run_id
            or event.get("migratesEventSha256") != target_event_sha256
        ):
            raise LifecycleError("WI-LEDGER-MIGRATION-TOPOLOGY", "operation id is bound to different inputs")
        before = b"".join(raw_lines[:index])
        if _sha256_bytes(before) != expected_before_sha256:
            raise LifecycleError("WI-LEDGER-MIGRATION-TOPOLOGY", "committed operation has a different before digest")
        replacement = event.get("replacementEvent")
        if not isinstance(replacement, dict):
            raise LifecycleError("WI-LEDGER-MIGRATION-TOPOLOGY", "committed anchor replacement is missing")
        target = next(
            (
                candidate for candidate, candidate_metadata in zip(events[:index], metadata[:index])
                if candidate.get("runId") == target_run_id
                and candidate_metadata.get("sha256") == target_event_sha256
            ),
            None,
        )
        if target is None:
            raise LifecycleError("WI-LEDGER-MIGRATION-TARGET-IDENTITY", "committed target no longer resolves")
        finding_class = target.get("findingClass") if normalization_kind == "remove-string-scratch-evidence" else "legacy-unclassified"
        diagnostic_id = (
            validator.LEDGER_EVENT_SCRATCH_EVIDENCE_INVALID
            if normalization_kind == "remove-string-scratch-evidence"
            else "LEDGER-EVENT-FINDING-CLASS-INVALID"
        )
        committed_after = b"".join(raw_lines[: index + 1])
        facts = {
            "schemaVersion": 1,
            "status": "committed",
            "operationId": operation_id,
            "targetRunId": target_run_id,
            "targetEventSha256": target_event_sha256,
            "anchorRunId": event["runId"],
            "anchorEventSha256": _sha256_bytes(text),
            "beforeLedgerBytes": len(before),
            "beforeLedgerSha256": _sha256_bytes(before),
            "afterLedgerBytes": len(committed_after),
            "afterLedgerSha256": _sha256_bytes(committed_after),
            "replacementEventSha256": _sha256_bytes(ledger_owner.serialize_event(replacement).encode("utf-8")),
            "normalizationKind": normalization_kind,
            "diagnosticId": diagnostic_id,
            "sourcePath": f"work-items/active/{item.name}/agent-runs.jsonl",
            "receiptPath": f"work-items/active/{item.name}/ledger-migration-receipts/{operation_id}.json",
            "recordedAt": event["startedAt"],
        }
        if finding_class is not None:
            facts["findingClass"] = finding_class
        return facts
    return None


def _migrate_legacy_ledger_obligation_locked(
    root: Path,
    slug: str,
    target_run_id: str,
    target_event_sha256: str,
    expected_ledger_sha256: str,
    operation_id: str,
    recorded_at: str,
    normalization_kind: str,
    *,
    inject_failure: str | None = None,
) -> dict:
    item = _active_migration_item(root, slug)
    committed = _committed_migration_facts(
        item,
        target_run_id=target_run_id,
        target_event_sha256=target_event_sha256,
        expected_before_sha256=expected_ledger_sha256,
        operation_id=operation_id,
        normalization_kind=normalization_kind,
    )
    if committed is not None:
        _reconcile_migration_receipt(item, committed)
        return committed
    ledger_owner = _load_agent_run_ledger()
    try:
        staged = ledger_owner.stage_legacy_obligation_migration(
            item,
            target_run_id,
            target_event_sha256,
            expected_ledger_sha256,
            operation_id,
            recorded_at,
            normalization_kind,
        )
    except ledger_owner.LedgerMigrationError as exc:
        raise LifecycleError(exc.failure_id, str(exc)) from exc
    ledger_path = item / "agent-runs.jsonl"
    ledger_path = _require_lifecycle_mutation_path(
        root, ledger_path, failure_id="WI-LEDGER-MIGRATION-COMMIT-INDETERMINATE"
    )
    _atomic_write(ledger_path, staged.staged_bytes)
    if inject_failure == "post-replace-corrupt":
        ledger_path.write_bytes(staged.staged_bytes + b"corrupt")
    try:
        actual = ledger_path.read_bytes()
    except OSError as exc:
        raise LifecycleError("WI-LEDGER-MIGRATION-COMMIT-INDETERMINATE", "ledger readback failed") from exc
    if _sha256_bytes(actual) != staged.receipt_facts["afterLedgerSha256"]:
        raise LifecycleError("WI-LEDGER-MIGRATION-COMMIT-INDETERMINATE", "ledger is neither exact before nor exact after")
    if inject_failure == "after-anchor":
        raise LifecycleError("WI-LEDGER-MIGRATION-COMMIT-INDETERMINATE", "injected crash after anchor")
    _reconcile_migration_receipt(item, staged.receipt_facts)
    return staged.receipt_facts


def migrate_legacy_ledger_obligation(
    root: Path,
    slug: str,
    target_run_id: str,
    target_event_sha256: str,
    expected_ledger_sha256: str,
    operation_id: str,
    recorded_at: str,
    *,
    normalization_kind: str = "invalid-finding-class",
    inject_failure: str | None = None,
) -> dict:
    item = _active_migration_item(root, slug)
    ledger_owner = _load_agent_run_ledger()
    try:
        with ledger_owner.ledger_write_lock(item):
            return _migrate_legacy_ledger_obligation_locked(
                root, slug, target_run_id, target_event_sha256,
                expected_ledger_sha256, operation_id, recorded_at,
                normalization_kind,
                inject_failure=inject_failure,
            )
    except ledger_owner.LedgerWriteLockError as exc:
        raise LifecycleError("WI-LIFECYCLE-LOCK-HELD", str(exc)) from exc


def _revoke_legacy_ledger_obligation_locked(
    root: Path,
    slug: str,
    apply_run_id: str,
    apply_event_sha256: str,
    expected_ledger_sha256: str,
    operation_id: str,
    recorded_at: str,
) -> dict:
    item = _active_migration_item(root, slug)
    if (item / "lifecycle-transition-receipt.json").exists() or any(
        item.glob("lifecycle-transition-*.json")
    ):
        raise LifecycleError("WI-LEDGER-MIGRATION-REVOCATION-FROZEN", "physical transition has started")
    ledger_owner = _load_agent_run_ledger()
    ledger_owner._strict_migration_inputs(operation_id, recorded_at)
    ledger_path = item / "agent-runs.jsonl"
    ledger_path = _require_lifecycle_mutation_path(
        root, ledger_path, failure_id="WI-LEDGER-MIGRATION-COMMIT-INDETERMINATE"
    )
    before = ledger_path.read_bytes()
    if _sha256_bytes(before) != expected_ledger_sha256:
        raise LifecycleError("WI-LEDGER-MIGRATION-LEDGER-DRIFT", "ledger digest changed")
    validator = ledger_owner.load_validator()
    errors: list[str] = []
    metadata: list[dict[str, object]] = []
    events = validator.load_jsonl(ledger_path, errors, metadata)
    positions = [i for i, event in enumerate(events) if event.get("runId") == apply_run_id]
    if len(positions) != 1:
        raise LifecycleError("WI-LEDGER-MIGRATION-TARGET-IDENTITY", "apply anchor is missing or non-unique")
    pos = positions[0]
    apply_event = events[pos]
    if (
        apply_event.get("eventKind") != "legacy-obligation-migration"
        or apply_event.get("migrationAction") != "apply"
        or metadata[pos].get("sha256") != apply_event_sha256
    ):
        raise LifecycleError("WI-LEDGER-MIGRATION-TARGET-DIGEST", "apply anchor digest changed")
    if any(event.get("eventKind") == "legacy-obligation-migration" and event.get("migrationAction") == "revoke" and event.get("revokesMigrationRunId") == apply_run_id for event in events):
        raise LifecycleError("WI-LEDGER-MIGRATION-TOPOLOGY", "apply already revoked")
    normalization_kind = apply_event.get("normalizationKind", "invalid-finding-class")
    row = validator.LEGACY_MIGRATION_NORMALIZATIONS.get(normalization_kind)
    if row is None:
        raise LifecycleError("WI-LEDGER-MIGRATION-NORMALIZATION-KIND", "apply normalization kind is not closed")
    revoke = {
        "schemaVersion": 2,
        "runId": f"ledger-migration-{operation_id}",
        "workItem": apply_event["workItem"],
        "role": "lead",
        "executionRole": "main",
        "status": "completed",
        "gate": "none",
        "scope": row["scope"],
        "eventKind": "legacy-obligation-migration",
        "migrationAction": "revoke",
        "revokesMigrationRunId": apply_run_id,
        "revokesMigrationEventSha256": apply_event_sha256,
        "evidence": [{"kind": "manual-check", "ref": f"revoke {apply_run_id} {apply_event_sha256}"}],
        "startedAt": recorded_at,
        "updatedAt": recorded_at,
    }
    line = ledger_owner.serialize_event(revoke).encode("utf-8") + b"\n"
    candidate = before + (b"" if before.endswith(b"\n") else b"\n") + line
    temporary = item / ".ledger-revoke-candidate.jsonl"
    try:
        temporary.write_bytes(candidate)
        parse_errors: list[str] = []
        candidate_metadata: list[dict[str, object]] = []
        candidate_events = validator.load_jsonl(temporary, parse_errors, candidate_metadata)
        control_errors: list[str] = []
        validator.validate_event(revoke, item, {str(event.get("runId", "")).casefold() for event in events}, control_errors)
        _effective, _counters, projection_errors = validator.project_legacy_obligation_migrations(
            candidate_events, candidate_metadata, item
        )
        candidate_errors = parse_errors + control_errors + projection_errors
    finally:
        temporary.unlink(missing_ok=True)
    if candidate_errors:
        raise LifecycleError("WI-LEDGER-MIGRATION-CANDIDATE-INVALID", "; ".join(candidate_errors))
    _atomic_write(ledger_path, candidate)
    return {
        "schemaVersion": 1,
        "status": "revoked",
        "operationId": operation_id,
        "applyRunId": apply_run_id,
        "applyEventSha256": apply_event_sha256,
        "afterLedgerSha256": _sha256_bytes(candidate),
        "recordedAt": recorded_at,
    }


def revoke_legacy_ledger_obligation(
    root: Path,
    slug: str,
    apply_run_id: str,
    apply_event_sha256: str,
    expected_ledger_sha256: str,
    operation_id: str,
    recorded_at: str,
) -> dict:
    _validate_slug(slug)
    repository = Path(root).resolve()
    if repository.name == "work-items":
        repository = repository.parent
    transition_root = repository / ".scratch" / "work-items-lifecycle-transitions"
    if transition_root.is_dir():
        _lifecycle_reject_unreduced_reparse(
            transition_root,
            failure_id="WI-LEDGER-MIGRATION-REVOCATION-FROZEN",
            message="transition staging root is a link or reparse point",
        )
        for intent_path in sorted(transition_root.glob("*.json")):
            intent = _load_transition_intent(root, intent_path)
            if intent.get("slug") == slug:
                raise LifecycleError(
                    "WI-LEDGER-MIGRATION-REVOCATION-FROZEN",
                    "physical transition intent already exists",
                )
    locations = _category_locations(root, CATEGORIES["work-item"], slug)
    if any("archive" in path.parts for path in locations):
        raise LifecycleError(
            "WI-LEDGER-MIGRATION-REVOCATION-FROZEN",
            "work item is already archived",
        )
    item = _active_migration_item(root, slug)
    ledger_owner = _load_agent_run_ledger()
    try:
        with ledger_owner.ledger_write_lock(item):
            return _revoke_legacy_ledger_obligation_locked(
                root, slug, apply_run_id, apply_event_sha256,
                expected_ledger_sha256, operation_id, recorded_at,
            )
    except ledger_owner.LedgerWriteLockError as exc:
        raise LifecycleError("WI-LIFECYCLE-LOCK-HELD", str(exc)) from exc


TRANSITION_OWNER = "mutate-work-item:archive-with-successor-v1"
TRANSITION_INTENT_FIELDS = {
    "schemaVersion", "owner", "status", "operationId", "slug", "terminalInstant",
    "activePath", "archivePath", "successorPath", "expectedLedgerSha256",
    "expectedReadmeSha256", "statusBefore", "statusAfter", "closureBefore",
    "closureAfter", "successorData", "manifestData", "migrationReceiptPath", "bugs",
    "closureInputSha256", "successorSlug", "finalReadmeSha256",
    "bugReceiptBefore", "bugReceiptAfter",
}


def _b64(data: bytes | None) -> str | None:
    return None if data is None else base64.b64encode(data).decode("ascii")


def _unb64(value: str | None) -> bytes | None:
    if value is None:
        return None
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-INTENT-INVALID", "invalid intent byte image") from exc


def _transition_intent_path(root: Path, operation_id: str) -> Path:
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", operation_id, re.ASCII) is None:
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-INTENT-INVALID", "invalid transition operation id")
    repository = Path(root).resolve()
    if repository.name == "work-items":
        repository = repository.parent
    return repository / ".scratch" / "work-items-lifecycle-transitions" / f"{operation_id}.json"


def _transition_fsync_directory(path: Path) -> None:
    descriptor = None
    native_handle = None
    try:
        if os.name == "nt":
            import ctypes
            import ctypes.wintypes
            import msvcrt

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            create_file = kernel32.CreateFileW
            create_file.argtypes = [
                ctypes.wintypes.LPCWSTR, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD,
                ctypes.wintypes.LPVOID, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD,
                ctypes.wintypes.HANDLE,
            ]
            create_file.restype = ctypes.wintypes.HANDLE
            native_handle = create_file(
                str(path), 0x40000000, 0x00000001 | 0x00000002 | 0x00000004,
                None, 3, 0x02000000 | 0x00200000, None,
            )
            if native_handle == ctypes.wintypes.HANDLE(-1).value:
                native_handle = None
                raise OSError(ctypes.get_last_error(), "cannot open transition directory")
            descriptor = msvcrt.open_osfhandle(native_handle, os.O_RDWR)
            native_handle = None
        else:
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise OSError(errno.ENOTDIR, "transition parent is not a directory")
        os.fsync(descriptor)
    except OSError as exc:
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-INTENT-INVALID", "transition directory cannot be durably synced") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        elif native_handle is not None:
            import ctypes
            ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(native_handle)


def _intent_path(root: Path, relative: str) -> Path:
    pure = Path(relative)
    if pure.is_absolute() or ".." in pure.parts:
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-INTENT-INVALID", "intent path is not repository-relative")
    repository = Path(root).resolve()
    if repository.name == "work-items":
        repository = repository.parent
    path = repository.joinpath(*pure.parts)
    return _require_lifecycle_mutation_path(
        repository, path, failure_id="WI-LIFECYCLE-TRANSITION-INTENT-INVALID"
    )


def _load_transition_intent(root: Path, path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-INTENT-INVALID", "transition intent is unreadable") from exc
    if (
        not isinstance(payload, dict)
        or set(payload) != TRANSITION_INTENT_FIELDS
        or payload.get("schemaVersion") != 1
        or payload.get("owner") != TRANSITION_OWNER
        or payload.get("status") != "intent"
        or not isinstance(payload.get("bugs"), list)
    ):
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-INTENT-INVALID", "transition intent shape differs")
    for key in ("activePath", "archivePath", "successorPath", "migrationReceiptPath"):
        _intent_path(root, payload[key])
    return payload


def _transition_bug_plans(root: Path, intent: dict) -> tuple[BugDispositionPlan, ...]:
    plans = []
    for row in intent["bugs"]:
        if not isinstance(row, dict) or set(row) != {
            "id", "action", "source", "target", "before", "after", "statusBefore", "statusAfter"
        }:
            raise LifecycleError("WI-LIFECYCLE-TRANSITION-INTENT-INVALID", "transition bug image differs")
        plans.append(BugDispositionPlan(
            bug_id=row["id"], action=row["action"], source=_intent_path(root, row["source"]),
            target=_intent_path(root, row["target"]) if row["target"] is not None else None,
            before=_unb64(row["before"]) or b"", after=_unb64(row["after"]) or b"",
            status_before=row["statusBefore"], status_after=row["statusAfter"],
        ))
    return tuple(plans)


def _settlement_payload(root: Path, intent: dict, readme_sha256: str) -> dict:
    archive = _intent_path(root, intent["archivePath"])
    successor = _intent_path(root, intent["successorPath"])
    bug_receipt = archive / BUG_DISPOSITIONS_RECEIPT
    migration_receipt = archive / "ledger-migration-receipts" / Path(intent["migrationReceiptPath"]).name
    bug_receipt = _require_lifecycle_mutation_path(
        root, bug_receipt, failure_id="WI-LIFECYCLE-TRANSITION-ROLLFORWARD-INDETERMINATE"
    )
    migration_receipt = _require_lifecycle_mutation_path(
        root, migration_receipt, failure_id="WI-LIFECYCLE-TRANSITION-ROLLFORWARD-INDETERMINATE"
    )
    return {
        "schemaVersion": 1,
        "owner": TRANSITION_OWNER,
        "status": "settled",
        "operationId": intent["operationId"],
        "workItem": intent["slug"],
        "terminalInstant": intent["terminalInstant"],
        "archivePath": intent["archivePath"],
        "successorPath": intent["successorPath"],
        "successorSha256": _sha256_bytes(successor.read_bytes()),
        "ledgerSha256": _sha256_bytes((archive / "agent-runs.jsonl").read_bytes()),
        "statusSha256": _sha256_bytes((archive / "status.md").read_bytes()),
        "closureSha256": _sha256_bytes((archive / "closure.md").read_bytes()),
        "bugDispositionReceiptSha256": _sha256_bytes(bug_receipt.read_bytes()),
        "migrationReceiptSha256": _sha256_bytes(migration_receipt.read_bytes()),
        "readmeSha256": readme_sha256,
        "requestClosureSha256": intent["closureInputSha256"],
        "requestSuccessorSlug": intent["successorSlug"],
        "requestSuccessorSha256": _sha256_bytes(_unb64(intent["successorData"]) or b""),
        "requestTerminalInstant": intent["terminalInstant"],
        "requestExpectedLedgerSha256": intent["expectedLedgerSha256"],
        "requestExpectedReadmeSha256": intent["expectedReadmeSha256"],
    }


def _safe_refresh_readme(root: Path) -> str:
    readme = _work_items_root(root) / "README.md"
    _require_lifecycle_mutation_path(root, readme, failure_id="WI-README-STALE")
    digest = refresh_readme(root)
    readme = _require_lifecycle_mutation_path(root, readme, failure_id="WI-README-STALE")
    if not readme.is_file() or _lifecycle_path_has_reparse(readme) or _sha256_bytes(readme.read_bytes()) != digest:
        raise LifecycleError("WI-README-STALE", "README identity or digest changed")
    return digest


def _precompute_transition_readme_sha256(
    root: Path,
    active: Path,
    archive: Path,
    successor: Path,
    status_after: bytes,
    closure_after: bytes,
    successor_data: bytes,
    plans: tuple[BugDispositionPlan, ...],
) -> str:
    work_items = _work_items_root(root)
    static_guide = _static_guide(work_items / "README.md")
    with tempfile.TemporaryDirectory(prefix="work-items-transition-readme-") as directory:
        shadow_root = Path(directory)
        shadow_work_items = shadow_root / "work-items"
        shutil.copytree(work_items, shadow_work_items, symlinks=True)

        def shadow(path: Path) -> Path:
            return shadow_work_items / path.relative_to(work_items)

        shadow_active = shadow(active)
        shadow_archive = shadow(archive)
        _atomic_write(shadow_active / "status.md", status_after)
        _atomic_write(shadow_active / "closure.md", closure_after)
        for plan in plans:
            source = shadow(plan.source)
            if plan.action == "terminalize":
                assert plan.target is not None
                target = shadow(plan.target)
                _atomic_write(source, plan.after)
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(source, target)
        shadow_archive.parent.mkdir(parents=True, exist_ok=True)
        os.replace(shadow_active, shadow_archive)
        _atomic_write(shadow(successor), successor_data)
        transaction_token = _CURRENT_LIFECYCLE_TRANSACTION.set(None)
        composer_token = _CURRENT_LIFECYCLE_OUTCOME_COMPOSER.set(None)
        try:
            rendered = render_readme_bytes(
                shadow_root, static_guide_override=static_guide
            )
        finally:
            _CURRENT_LIFECYCLE_OUTCOME_COMPOSER.reset(composer_token)
            _CURRENT_LIFECYCLE_TRANSACTION.reset(transaction_token)
        return _sha256_bytes(rendered)


def _verify_settlement(root: Path, receipt: Path, expected: dict | None = None) -> dict:
    receipt = _require_lifecycle_mutation_path(
        root, receipt, failure_id="WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH"
    )
    try:
        payload = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH", "settled receipt is unreadable") from exc
    if not isinstance(payload, dict) or payload.get("status") != "settled" or payload.get("owner") != TRANSITION_OWNER:
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH", "settled receipt shape differs")
    archive = _intent_path(root, payload["archivePath"])
    successor = _intent_path(root, payload["successorPath"])
    readme_path = _require_lifecycle_mutation_path(
        root, _work_items_root(root) / "README.md",
        failure_id="WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH",
    )
    bug_receipt_path = _require_lifecycle_mutation_path(
        root, archive / BUG_DISPOSITIONS_RECEIPT,
        failure_id="WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH",
    )
    physical = {
        "successorSha256": _sha256_bytes(successor.read_bytes()),
        "ledgerSha256": _sha256_bytes((archive / "agent-runs.jsonl").read_bytes()),
        "statusSha256": _sha256_bytes((archive / "status.md").read_bytes()),
        "closureSha256": _sha256_bytes((archive / "closure.md").read_bytes()),
        "bugDispositionReceiptSha256": _sha256_bytes(bug_receipt_path.read_bytes()),
        "readmeSha256": _sha256_bytes(readme_path.read_bytes()),
    }
    migration_receipts = sorted((archive / "ledger-migration-receipts").glob("*.json"))
    if len(migration_receipts) != 1:
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH", "migration receipt cardinality differs")
    migration_receipt_path = _require_lifecycle_mutation_path(
        root, migration_receipts[0],
        failure_id="WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH",
    )
    physical["migrationReceiptSha256"] = _sha256_bytes(migration_receipt_path.read_bytes())
    if any(payload.get(key) != value for key, value in physical.items()):
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH", "settled receipt hashes differ")
    if expected is not None and payload != expected:
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH", "settled receipt content differs")
    return payload


def _recover_transition(root: Path, intent_path: Path, *, inject_failure_at: str | None = None) -> dict | None:
    intent = _load_transition_intent(root, intent_path)
    active = _intent_path(root, intent["activePath"])
    archive = _intent_path(root, intent["archivePath"])
    successor = _intent_path(root, intent["successorPath"])
    status_before = _unb64(intent["statusBefore"]) or b""
    status_after = _unb64(intent["statusAfter"]) or b""
    closure_before = _unb64(intent["closureBefore"])
    closure_after = _unb64(intent["closureAfter"]) or b""
    bug_receipt_before = _unb64(intent["bugReceiptBefore"])
    bug_receipt_after = _unb64(intent["bugReceiptAfter"]) or b""
    plans = _transition_bug_plans(root, intent)
    if active.is_dir():
        status = _require_lifecycle_mutation_path(
            root, active / "status.md",
            failure_id="WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE",
        )
        closure = _require_lifecycle_mutation_path(
            root, active / "closure.md",
            failure_id="WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE",
        )
        bug_receipt = _require_lifecycle_mutation_path(
            root, active / BUG_DISPOSITIONS_RECEIPT,
            failure_id="WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE",
        )
        current_status = status.read_bytes() if status.exists() else None
        current_closure = closure.read_bytes() if closure.exists() else None
        if current_status not in {status_before, status_after} or current_closure not in {closure_before, closure_after}:
            raise LifecycleError("WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE", "active before-image cannot be proven")
        for plan in plans:
            current = plan.source if plan.source.exists() else plan.target
            if current is None or not current.exists() or current.read_bytes() not in {plan.before, plan.after}:
                raise LifecycleError("WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE", f"bug before-image differs: {plan.bug_id}")
            if plan.target is not None and plan.target.exists() and not plan.source.exists():
                plan.source.parent.mkdir(parents=True, exist_ok=True)
                os.replace(plan.target, plan.source)
            _atomic_write(plan.source, plan.before)
        current_bug_receipt = bug_receipt.read_bytes() if bug_receipt.exists() else None
        if current_bug_receipt not in {bug_receipt_before, bug_receipt_after}:
            raise LifecycleError("WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE", "bug receipt before-image differs")
        _atomic_write(status, status_before)
        if closure_before is None:
            _require_lifecycle_mutation_path(
                root, closure, failure_id="WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE"
            )
            closure.unlink(missing_ok=True)
        else:
            _atomic_write(closure, closure_before)
        if bug_receipt_before is None:
            _require_lifecycle_mutation_path(
                root, bug_receipt, failure_id="WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE"
            )
            bug_receipt.unlink(missing_ok=True)
        else:
            _atomic_write(bug_receipt, bug_receipt_before)
        if successor.exists():
            if successor.read_bytes() != (_unb64(intent["successorData"]) or b""):
                raise LifecycleError("WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE", "unexpected successor bytes")
            successor.unlink()
        _require_lifecycle_mutation_path(
            root, intent_path, failure_id="WI-LIFECYCLE-TRANSITION-INTENT-INVALID"
        )
        intent_path.unlink()
        return None
    if not archive.is_dir():
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-INTENT-INVALID", "intent has neither active nor archive identity")
    if (archive / "status.md").read_bytes() != status_after or (archive / "closure.md").read_bytes() != closure_after:
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-ROLLFORWARD-INDETERMINATE", "archive identity differs")
    successor_data = _unb64(intent["successorData"]) or b""
    if successor.exists():
        if successor.read_bytes() != successor_data:
            raise LifecycleError("WI-LIFECYCLE-TRANSITION-ROLLFORWARD-INDETERMINATE", "successor bytes differ")
    else:
        _atomic_write(successor, successor_data)
    if inject_failure_at == "T4":
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-ROLLFORWARD-INDETERMINATE", "injected T4")
    archived_bug_receipt = archive / BUG_DISPOSITIONS_RECEIPT
    archived_bug_receipt = _require_lifecycle_mutation_path(
        root, archived_bug_receipt,
        failure_id="WI-LIFECYCLE-TRANSITION-ROLLFORWARD-INDETERMINATE",
    )
    if not archived_bug_receipt.is_file() or archived_bug_receipt.read_bytes() != bug_receipt_after:
        raise LifecycleError(
            "WI-LIFECYCLE-TRANSITION-ROLLFORWARD-INDETERMINATE",
            "pre-archive bug receipt is missing or changed",
        )
    readme_sha = _safe_refresh_readme(root)
    if readme_sha != intent["finalReadmeSha256"]:
        raise LifecycleError(
            "WI-LIFECYCLE-TRANSITION-ROLLFORWARD-INDETERMINATE",
            "precomputed README digest differs after roll-forward",
        )
    if inject_failure_at == "T5":
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-ROLLFORWARD-INDETERMINATE", "injected T5")
    settlement = _settlement_payload(root, intent, readme_sha)
    receipt_path = archive / "lifecycle-transition-receipt.json"
    receipt_bytes = _migration_receipt_bytes(settlement)
    if receipt_path.exists() and receipt_path.read_bytes() != receipt_bytes:
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH", "settled receipt differs")
    receipt_path = _require_lifecycle_mutation_path(
        root, receipt_path,
        failure_id="WI-LIFECYCLE-TRANSITION-ROLLFORWARD-INDETERMINATE",
    )
    _atomic_write(receipt_path, receipt_bytes)
    _transition_fsync_directory(receipt_path.parent)
    if inject_failure_at == "T6":
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-ROLLFORWARD-INDETERMINATE", "injected T6")
    _verify_settlement(root, receipt_path, settlement)
    if inject_failure_at == "T7":
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-ROLLFORWARD-INDETERMINATE", "injected T7")
    _require_lifecycle_mutation_path(
        root, intent_path, failure_id="WI-LIFECYCLE-TRANSITION-INTENT-INVALID"
    )
    intent_path.unlink(missing_ok=True)
    if inject_failure_at in {"T8", "T9"}:
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-ROLLFORWARD-INDETERMINATE", f"injected {inject_failure_at}")
    return settlement


def _recover_all_transitions(root: Path) -> None:
    repository = Path(root).resolve()
    if repository.name == "work-items":
        repository = repository.parent
    directory = repository / ".scratch" / "work-items-lifecycle-transitions"
    if not directory.exists():
        return
    if not directory.is_dir() or _lifecycle_path_has_reparse(directory):
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-INTENT-INVALID", "transition staging root is unsafe")
    for intent_path in sorted(directory.glob("*.json")):
        _recover_transition(root, intent_path)


def archive_with_successor(
    root: Path,
    slug: str,
    closure_data: bytes,
    terminal_instant: str,
    successor_slug: str,
    successor_data: bytes,
    operation_id: str,
    expected_ledger_sha256: str,
    expected_readme_sha256: str,
    *,
    inject_failure_at: str | None = None,
) -> dict:
    _validate_slug(slug)
    _validate_slug(successor_slug)
    month = archive_month(terminal_instant)
    _validate_closure(closure_data, terminal_instant)
    work_items = _work_items_root(root)
    archive = work_items / "archive" / month / slug
    settled_path = archive / "lifecycle-transition-receipt.json"
    settled_path = _require_lifecycle_mutation_path(
        root, settled_path, failure_id="WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH"
    )
    if settled_path.is_file():
        payload = _verify_settlement(root, settled_path)
        if (
            payload.get("operationId") != operation_id
            or payload.get("workItem") != slug
            or payload.get("requestClosureSha256") != _sha256_bytes(closure_data)
            or payload.get("requestSuccessorSlug") != successor_slug
            or payload.get("requestSuccessorSha256") != _sha256_bytes(successor_data)
            or payload.get("requestTerminalInstant") != terminal_instant
            or payload.get("requestExpectedLedgerSha256") != expected_ledger_sha256
            or payload.get("requestExpectedReadmeSha256") != expected_readme_sha256
        ):
            raise LifecycleError("WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH", "replay inputs differ")
        return payload
    intent_path = _transition_intent_path(root, operation_id)
    if intent_path.exists():
        recovered = _recover_transition(root, intent_path, inject_failure_at=inject_failure_at)
        if recovered is not None:
            return recovered
    active = _active_migration_item(root, slug)
    ledger = active / "agent-runs.jsonl"
    if _sha256_bytes(ledger.read_bytes()) != expected_ledger_sha256:
        raise LifecycleError("WI-LEDGER-MIGRATION-LEDGER-DRIFT", "transition ledger digest changed")
    readme = work_items / "README.md"
    readme = _require_lifecycle_mutation_path(root, readme, failure_id="WI-README-STALE")
    if not readme.is_file() or _sha256_bytes(readme.read_bytes()) != expected_readme_sha256:
        raise LifecycleError("WI-README-STALE", "transition README digest changed")
    archive = _require_lifecycle_mutation_path(
        root, archive, failure_id="WI-LIFECYCLE-TRANSITION-INTENT-INVALID"
    )
    successor_preflight = _require_lifecycle_mutation_path(
        root, work_items / "backlog" / f"{successor_slug}.md",
        failure_id="WI-LIFECYCLE-TRANSITION-INTENT-INVALID",
    )
    if archive.exists() or successor_preflight.exists():
        raise LifecycleError("WI-CATEGORY-DUAL-LOCATION", "archive or successor already exists")
    _validate_item_before_close(active)
    _manifest, manifest_data, bug_plans = _prepare_bug_dispositions(root, active, slug, terminal_instant)
    migration_receipts = sorted((active / "ledger-migration-receipts").glob("*.json"))
    if len(migration_receipts) != 1:
        raise LifecycleError("WI-LEDGER-MIGRATION-RECEIPT-MISMATCH", "one migration receipt is required")
    migration_receipts[0] = _require_lifecycle_mutation_path(
        root, migration_receipts[0], failure_id="WI-LEDGER-MIGRATION-RECEIPT-MISMATCH"
    )
    archived_closure = _stamp_schema_marker(closure_data, "closure.md")
    status = active / "status.md"
    prior_status = status.read_bytes()
    status_after = _terminalize_status(prior_status)
    prior_closure = (active / "closure.md").read_bytes() if (active / "closure.md").exists() else None
    relative = lambda path: path.relative_to(Path(root).resolve()).as_posix()
    successor_path = work_items / "backlog" / f"{successor_slug}.md"
    final_readme_sha = _precompute_transition_readme_sha256(
        root, active, archive, successor_path, status_after, archived_closure,
        successor_data, bug_plans,
    )
    bug_receipt_path = active / BUG_DISPOSITIONS_RECEIPT
    bug_receipt_path = _require_lifecycle_mutation_path(
        root, bug_receipt_path, failure_id="WI-LIFECYCLE-TRANSITION-INTENT-INVALID"
    )
    if bug_receipt_path.exists():
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-INTENT-INVALID", "active bug receipt already exists")
    bug_receipt_after = _bug_disposition_receipt_bytes(
        root, slug, terminal_instant, manifest_data, archived_closure, bug_plans, final_readme_sha
    )
    intent = {
        "schemaVersion": 1, "owner": TRANSITION_OWNER, "status": "intent",
        "operationId": operation_id, "slug": slug, "terminalInstant": terminal_instant,
        "activePath": relative(active), "archivePath": relative(archive),
        "successorPath": relative(successor_path),
        "expectedLedgerSha256": expected_ledger_sha256, "expectedReadmeSha256": expected_readme_sha256,
        "statusBefore": _b64(prior_status), "statusAfter": _b64(status_after),
        "closureBefore": _b64(prior_closure), "closureAfter": _b64(archived_closure),
        "successorData": _b64(successor_data), "manifestData": _b64(manifest_data),
        "migrationReceiptPath": relative(migration_receipts[0]),
        "closureInputSha256": _sha256_bytes(closure_data),
        "successorSlug": successor_slug,
        "finalReadmeSha256": final_readme_sha,
        "bugReceiptBefore": None,
        "bugReceiptAfter": _b64(bug_receipt_after),
        "bugs": [{
            "id": plan.bug_id, "action": plan.action, "source": relative(plan.source),
            "target": relative(plan.target) if plan.target is not None else None,
            "before": _b64(plan.before), "after": _b64(plan.after),
            "statusBefore": plan.status_before, "statusAfter": plan.status_after,
        } for plan in bug_plans],
    }
    intent_path = _require_lifecycle_mutation_path(
        root, intent_path, failure_id="WI-LIFECYCLE-TRANSITION-INTENT-INVALID"
    )
    _atomic_write(intent_path, _migration_receipt_bytes(intent))
    _transition_fsync_directory(intent_path.parent)
    if inject_failure_at == "T0":
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE", "injected T0")
    for plan in bug_plans:
        plan_source = _require_lifecycle_mutation_path(
            root, plan.source,
            failure_id="WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE",
        )
        plan_target = None
        if plan.target is not None:
            plan_target = _require_lifecycle_mutation_path(
                root, plan.target,
                failure_id="WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE",
            )
        if plan.action == "terminalize":
            _atomic_write(plan_source, plan.after)
            assert plan_target is not None
            plan_target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(plan_source, plan_target)
    closure_path = _require_lifecycle_mutation_path(
        root, active / "closure.md",
        failure_id="WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE",
    )
    _atomic_write(closure_path, archived_closure)
    _atomic_write(status, status_after)
    if inject_failure_at == "T1":
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE", "injected T1")
    _atomic_write(bug_receipt_path, bug_receipt_after)
    _transition_fsync_directory(bug_receipt_path.parent)
    if inject_failure_at == "T2":
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE", "injected T2")
    archive.parent.mkdir(parents=True, exist_ok=True)
    os.replace(active, archive)
    if inject_failure_at == "T3":
        raise LifecycleError("WI-LIFECYCLE-TRANSITION-ROLLFORWARD-INDETERMINATE", "injected T3")
    return _recover_transition(root, intent_path, inject_failure_at=inject_failure_at)


def _validate_flat_terminal(category: Category, data: bytes) -> str:
    try:
        fields = _parse_fields(data.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise LifecycleError(
            "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING", "terminal record must be UTF-8"
        ) from exc
    status = fields.get("status", "")
    if status not in category.terminal_statuses:
        raise LifecycleError(
            "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
            f"{category.name} status {status!r} is not terminal",
        )
    admission = _admission_for(category.name)
    utc_field = admission.utc_field.casefold()
    evidence_fields = (
        admission.detail_field.casefold(),
        admission.evidence_field.casefold(),
    )
    missing = [name for name in (utc_field, *evidence_fields) if not fields.get(name)]
    if missing:
        raise LifecycleError(
            "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
            f"{category.name} terminal record missing: {', '.join(missing)}",
        )
    _strict_utc(fields[utc_field])
    return fields[utc_field]


def _normalization_fail(failure_id: str, message: str) -> LifecycleError:
    return LifecycleError(failure_id, message)


def _normalization_bound_source(
    root: Path, category: Category, relative: str, *, must_exist: bool = True
) -> Path:
    work_items = _work_items_root(root)
    relative_path = Path(relative)
    if (
        relative_path.is_absolute()
        or len(relative_path.parts) < 2
        or relative_path.parts[0] != "work-items"
    ):
        raise _normalization_fail(
            "WI-IDENTITY-NORMALIZE-SOURCE",
            "normalization source must be repository-relative under work-items",
        )
    within_work_items = Path(*relative_path.parts[1:]).as_posix()
    requested = work_items.resolve() / Path(within_work_items)
    try:
        resolved = _terminalization_bound_path(
            work_items, within_work_items, label="normalization source"
        )
    except LifecycleError as exc:
        raise _normalization_fail("WI-IDENTITY-NORMALIZE-SOURCE", str(exc)) from exc
    source = requested
    expected_parent = (work_items / category.current_root).resolve()
    if (
        category.current_kind != "flat"
        or source.parent.resolve() != expected_parent
        or source.resolve() != resolved
        or source.suffix != ".md"
        or (must_exist and not source.is_file())
    ):
        raise _normalization_fail(
            "WI-IDENTITY-NORMALIZE-SOURCE",
            "normalization source must be one mutable flat record in its category current root",
        )
    return source


def _normalization_scratch_path(root: Path, path: Path, *, label: str) -> Path:
    try:
        return _bound_repository_scratch_path(root, path, label=label, allow_absolute=True)
    except LifecycleError as exc:
        raise _normalization_fail("WI-IDENTITY-NORMALIZE-INVENTORY", str(exc)) from exc


def _normalization_exact_file(path: Path) -> bool:
    return path.parent.is_dir() and any(
        child.name == path.name and child.is_file() for child in path.parent.iterdir()
    )


def _normalization_current_files(work_items: Path) -> list[Path]:
    files: set[Path] = set((work_items / "backlog").glob("*.md"))
    files.update(path / "status.md" for path in (work_items / "active").glob("*") if path.is_dir())
    for category in CATEGORIES.values():
        if category.current_kind == "flat":
            files.update((work_items / category.current_root).glob("*.md"))
    return sorted(path for path in files if path.is_file())


def _normalization_authoritative_line_numbers(text: str) -> frozenset[int]:
    return frozenset(
        line_number for line_number, _line in _authoritative_markdown_lines(text)
    )


def _normalization_replace_id(text: str, old_slug: str, new_slug: str) -> tuple[str, int]:
    authoritative = _normalization_authoritative_line_numbers(text)
    lines = text.splitlines(keepends=True)
    count = 0
    for index, line in enumerate(lines, start=1):
        if index not in authoritative:
            continue
        body = line.rstrip("\r\n")
        ending = line[len(body) :]
        match = FIELD_RE.fullmatch(body)
        if not (
            match
            and match.group(1).strip().casefold() == "id"
            and match.group(2).strip() == old_slug
        ):
            continue
        value_start, value_end = match.span(2)
        raw_value = match.group(2)
        leading = len(raw_value) - len(raw_value.lstrip())
        trailing = len(raw_value) - len(raw_value.rstrip())
        replacement = raw_value[:leading] + new_slug
        if trailing:
            replacement += raw_value[len(raw_value) - trailing :]
        lines[index - 1] = body[:value_start] + replacement + body[value_end:] + ending
        count += 1
    return "".join(lines), count


def _normalization_replace_live_mentions(
    text: str, old_slug: str, new_slug: str
) -> tuple[str, int]:
    """Rewrite live current-record mentions but preserve fenced evidence bytes."""
    authoritative = _normalization_authoritative_line_numbers(text)
    lines = text.splitlines(keepends=True)
    count = 0
    for index, line in enumerate(lines, start=1):
        if index not in authoritative:
            continue
        count += line.count(old_slug)
        lines[index - 1] = line.replace(old_slug, new_slug)
    return "".join(lines), count


def _normalization_authoritative_markdown_links(
    text: str,
) -> Iterable[MarkdownLocalLink]:
    """Yield normalization links only from lifecycle-authoritative Markdown lines."""
    authoritative = _normalization_authoritative_line_numbers(text)
    for link in _markdown_local_links(text):
        line_number = text.count("\n", 0, link.href_start) + 1
        if line_number in authoritative:
            yield link


def _normalization_snapshot(
    root: Path,
    category: Category,
    source: Path,
    target_slug: str,
) -> tuple[dict, dict[Path, bytes]]:
    work_items = _work_items_root(root)
    old_slug = source.stem
    target = work_items / category.current_root / f"{target_slug}.md"
    planned: dict[Path, bytes] = {}
    kinds: dict[Path, set[str]] = {}

    current_files = frozenset(_normalization_current_files(work_items))
    markdown_files = sorted(
        path for path in work_items.rglob("*.md") if path.name != "README.md"
    )
    for path in markdown_files:
        try:
            before = path.read_bytes()
            text = before.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise _normalization_fail(
                "WI-IDENTITY-NORMALIZE-INVENTORY",
                f"cannot classify Markdown consumer: {path}",
            ) from exc

        physical_replacements: list[tuple[int, int, str]] = []
        for link in _normalization_authoritative_markdown_links(text):
            href_parts = _local_markdown_href_parts(link.href)
            if href_parts is None:
                continue
            filesystem_href, suffix = href_parts
            if (path.parent / filesystem_href).resolve() != source.resolve():
                continue
            if path not in current_files:
                raise _normalization_fail(
                    "WI-IDENTITY-NORMALIZE-INVENTORY",
                    f"physical consumer is not mutable current state: {path}",
                )
            new_href = Path(os.path.relpath(target, path.parent)).as_posix() + suffix
            physical_replacements.append((link.href_start, link.href_end, new_href))
        if physical_replacements:
            for start, end, value in reversed(physical_replacements):
                text = text[:start] + value + text[end:]
            kinds.setdefault(path, set()).add("physical-link")

        if path not in current_files:
            continue
        after = text
        if path == source:
            after, count = _normalization_replace_id(after, old_slug, target_slug)
            if count != 1:
                raise _normalization_fail(
                    "WI-IDENTITY-NORMALIZE-INVENTORY",
                    "source must contain exactly one authoritative id matching its physical slug",
                )
            kinds.setdefault(path, set()).add("authoritative-id")
        after, live_count = _normalization_replace_live_mentions(
            after, old_slug, target_slug
        )
        if live_count:
            kinds.setdefault(path, set()).add("live-reference")
        if after.encode("utf-8") != before:
            planned[path] = after.encode("utf-8")

    if source not in planned:
        raise _normalization_fail(
            "WI-IDENTITY-NORMALIZE-INVENTORY", "normalization source produced no identity change"
        )
    rows = []
    for path in sorted(planned):
        before = path.read_bytes()
        after = planned[path]
        rows.append(
            {
                "path": path.relative_to(work_items).as_posix(),
                "kinds": sorted(kinds[path]),
                "beforeSha256": hashlib.sha256(before).hexdigest(),
                "afterSha256": hashlib.sha256(after).hexdigest(),
            }
        )
    inventory = {
        "schemaVersion": CURRENT_IDENTITY_NORMALIZATION_SCHEMA_VERSION,
        "owner": CURRENT_IDENTITY_NORMALIZATION_OWNER,
        "workItemsRoot": str(work_items.resolve()),
        "category": category.name,
        "source": source.relative_to(work_items.parent).as_posix(),
        "targetSlug": target_slug,
        "oldIdentity": f"{category.name}:{old_slug}",
        "newIdentity": f"{category.name}:{target_slug}",
        "rows": rows,
    }
    return inventory, planned


def write_current_identity_normalization_inventory(
    root: Path,
    category_name: str,
    source_relative: str,
    target_slug: str,
    inventory_path: Path,
) -> dict:
    category = CATEGORIES.get(CATEGORY_ALIASES.get(category_name, category_name))
    if category is None:
        raise LifecycleError("WI-REFERENCE-INVALID", f"unknown category: {category_name!r}")
    _validate_slug(target_slug)
    source = _normalization_bound_source(root, category, source_relative)
    if is_valid_slug(source.stem):
        raise _normalization_fail(
            "WI-IDENTITY-NORMALIZE-SOURCE", "source identity is already canonical"
        )
    fields = _parse_fields(source.read_text(encoding="utf-8"))
    if fields.get("status", "") not in category.current_statuses:
        raise _normalization_fail(
            "WI-IDENTITY-NORMALIZE-SOURCE", "source does not carry a current admitted status"
        )
    inventory, _planned = _normalization_snapshot(root, category, source, target_slug)
    destination = _normalization_scratch_path(root, inventory_path, label="normalization inventory")
    _atomic_write(destination, (json.dumps(inventory, indent=2, sort_keys=True) + "\n").encode())
    return inventory


def _normalization_expected_receipt_rows(
    root: Path,
    category: Category,
    inventory: object,
    source: Path,
    target: Path,
) -> list[dict[str, str]]:
    """Derive the one complete receipt row sequence from the canonical inventory."""
    work_items = _work_items_root(root)
    source_repo_relative = source.relative_to(work_items.parent).as_posix()
    source_work_items_relative = source.relative_to(work_items).as_posix()
    target_work_items_relative = target.relative_to(work_items).as_posix()
    if (
        not isinstance(inventory, dict)
        or inventory.get("schemaVersion")
        != CURRENT_IDENTITY_NORMALIZATION_SCHEMA_VERSION
        or inventory.get("owner") != CURRENT_IDENTITY_NORMALIZATION_OWNER
        or inventory.get("workItemsRoot") != str(work_items.resolve())
        or inventory.get("category") != category.name
        or inventory.get("source") != source_repo_relative
        or inventory.get("targetSlug") != target.stem
        or not isinstance(inventory.get("rows"), list)
    ):
        raise _normalization_fail(
            "WI-IDENTITY-NORMALIZE-RECOVERY",
            "normalization inventory binding differs during replay",
        )

    expected: list[dict[str, str]] = []
    before_paths: set[str] = set()
    after_paths: set[str] = set()
    digest_re = re.compile(r"^[0-9a-f]{64}$")
    for row in inventory["rows"]:
        if (
            not isinstance(row, dict)
            or set(row) != {"path", "kinds", "beforeSha256", "afterSha256"}
            or not isinstance(row.get("path"), str)
            or not isinstance(row.get("kinds"), list)
            or not all(isinstance(kind, str) for kind in row["kinds"])
            or not isinstance(row.get("beforeSha256"), str)
            or not digest_re.fullmatch(row["beforeSha256"])
            or not isinstance(row.get("afterSha256"), str)
            or not digest_re.fullmatch(row["afterSha256"])
        ):
            raise _normalization_fail(
                "WI-IDENTITY-NORMALIZE-RECOVERY",
                "normalization inventory row is invalid during replay",
            )
        before_path = row["path"]
        try:
            _terminalization_bound_path(
                work_items, before_path, label="normalization receipt preimage"
            )
        except LifecycleError as exc:
            raise _normalization_fail(
                "WI-IDENTITY-NORMALIZE-RECOVERY", str(exc)
            ) from exc
        after_path = (
            target_work_items_relative
            if before_path == source_work_items_relative
            else before_path
        )
        if before_path in before_paths or after_path in after_paths:
            raise _normalization_fail(
                "WI-IDENTITY-NORMALIZE-RECOVERY",
                "normalization inventory rows are duplicated or collide",
            )
        before_paths.add(before_path)
        after_paths.add(after_path)
        expected.append(
            {
                "beforePath": before_path,
                "afterPath": after_path,
                "beforeSha256": row["beforeSha256"],
                "afterSha256": row["afterSha256"],
            }
        )
    if source_work_items_relative not in before_paths:
        raise _normalization_fail(
            "WI-IDENTITY-NORMALIZE-RECOVERY",
            "normalization inventory omits the authoritative source row",
        )
    return expected


def _normalization_replay(
    root: Path,
    category: Category,
    inventory_bytes: bytes,
    receipt: Path,
    source: Path,
    target: Path,
) -> bool:
    if not receipt.is_file() or _normalization_exact_file(source) or not _normalization_exact_file(target):
        return False
    try:
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        inventory = json.loads(inventory_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _normalization_fail("WI-IDENTITY-NORMALIZE-RECOVERY", "invalid normalization receipt") from exc
    work_items = _work_items_root(root)
    if (
        not isinstance(payload, dict)
        or payload.get("schemaVersion") != CURRENT_IDENTITY_NORMALIZATION_SCHEMA_VERSION
        or payload.get("owner") != CURRENT_IDENTITY_NORMALIZATION_OWNER
        or payload.get("inventorySha256") != hashlib.sha256(inventory_bytes).hexdigest()
        or payload.get("source") != source.relative_to(work_items.parent).as_posix()
        or payload.get("target") != target.relative_to(work_items).as_posix()
        or not isinstance(payload.get("rows"), list)
    ):
        raise _normalization_fail("WI-IDENTITY-NORMALIZE-RECOVERY", "normalization receipt binding differs")
    expected_rows = _normalization_expected_receipt_rows(
        root, category, inventory, source, target
    )
    if payload["rows"] != expected_rows:
        raise _normalization_fail(
            "WI-IDENTITY-NORMALIZE-RECOVERY",
            "normalization receipt row set is incomplete, duplicated, or tampered",
        )
    for row in expected_rows:
        path = _terminalization_bound_path(work_items, row["afterPath"], label="normalization replay")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row.get("afterSha256"):
            raise _normalization_fail("WI-IDENTITY-NORMALIZE-RECOVERY", "normalization settled bytes differ")
    readme = work_items / "README.md"
    if not readme.is_file() or hashlib.sha256(readme.read_bytes()).hexdigest() != payload.get("readmeSha256"):
        raise _normalization_fail("WI-IDENTITY-NORMALIZE-RECOVERY", "normalization README differs")
    return True


def normalize_current_identity(
    root: Path,
    category_name: str,
    source_relative: str,
    target_slug: str,
    inventory_path: Path,
    receipt_path: Path,
    *,
    inject_failure_at: str | None = None,
) -> tuple[Path, bool]:
    category = CATEGORIES.get(CATEGORY_ALIASES.get(category_name, category_name))
    if category is None:
        raise LifecycleError("WI-REFERENCE-INVALID", f"unknown category: {category_name!r}")
    _validate_slug(target_slug)
    work_items = _work_items_root(root)
    source = _normalization_bound_source(root, category, source_relative, must_exist=False)
    target = work_items / category.current_root / f"{target_slug}.md"
    inventory_file = _normalization_scratch_path(root, inventory_path, label="normalization inventory")
    receipt = _normalization_scratch_path(root, receipt_path, label="normalization receipt")
    try:
        inventory_bytes = inventory_file.read_bytes()
        inventory = json.loads(inventory_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _normalization_fail("WI-IDENTITY-NORMALIZE-INVENTORY", "invalid normalization inventory") from exc
    if not _normalization_exact_file(source):
        if _normalization_replay(
            root, category, inventory_bytes, receipt, source, target
        ):
            return target, True
        raise _normalization_fail(
            "WI-IDENTITY-NORMALIZE-RECOVERY", "source is absent without a complete settled receipt"
        )
    if receipt.exists():
        raise _normalization_fail(
            "WI-IDENTITY-NORMALIZE-RECOVERY",
            "receipt exists while legacy source is still present",
        )
    if is_valid_slug(source.stem):
        raise _normalization_fail("WI-IDENTITY-NORMALIZE-SOURCE", "source identity is already canonical")
    locations = _category_locations(root, category, source.stem)
    if locations != [source]:
        raise LifecycleError("WI-CATEGORY-DUAL-LOCATION", "source identity is not physically unique")
    fields = _parse_fields(source.read_text(encoding="utf-8"))
    if fields.get("status", "") not in category.current_statuses:
        raise _normalization_fail(
            "WI-IDENTITY-NORMALIZE-SOURCE", "source does not carry a current admitted status"
        )
    target_locations = _category_locations(root, category, target_slug)
    if _normalization_exact_file(target) or any(
        not (location.is_file() and os.path.samefile(location, source))
        for location in target_locations
    ):
        raise LifecycleError("WI-CATEGORY-DUAL-LOCATION", "normalization target already exists")
    expected, planned = _normalization_snapshot(root, category, source, target_slug)
    if inventory != expected:
        raise _normalization_fail(
            "WI-IDENTITY-NORMALIZE-INVENTORY", "inventory is incomplete, stale, or differently classified"
        )
    readme = work_items / "README.md"
    readme_before = readme.read_bytes() if readme.is_file() else None
    preimages = {path: path.read_bytes() for path in planned}
    inventory_sha = hashlib.sha256(inventory_bytes).hexdigest()
    moved = False
    move_temp: Path | None = None
    try:
        for path in sorted(planned):
            _atomic_write(path, planned[path])
        if inject_failure_at == "after-rewrites":
            raise RuntimeError("injected normalization failure after rewrites")
        temp_dir = Path(tempfile.mkdtemp(prefix=f".{target_slug}.normalize.", dir=source.parent))
        move_temp = temp_dir / source.name
        os.replace(source, move_temp)
        os.replace(move_temp, target)
        temp_dir.rmdir()
        move_temp = None
        moved = True
        if inject_failure_at == "after-move":
            raise RuntimeError("injected normalization failure after move")
        readme_sha = refresh_readme(root)
        if inject_failure_at == "after-readme":
            raise RuntimeError("injected normalization failure after README")
        resolved = resolve_category(root, f"{category.name}:{target_slug}")
        if resolved != target.resolve() or _normalization_exact_file(source) or not _normalization_exact_file(target):
            raise RuntimeError("normalization final identity check failed")
        for path, after in planned.items():
            final_path = target if path == source else path
            if (
                not final_path.is_file()
                or hashlib.sha256(final_path.read_bytes()).hexdigest()
                != hashlib.sha256(after).hexdigest()
            ):
                raise RuntimeError(
                    f"normalization final byte check failed: {final_path}"
                )
        audit(root)
        rows = _normalization_expected_receipt_rows(
            root, category, inventory, source, target
        )
        payload = {
            "schemaVersion": CURRENT_IDENTITY_NORMALIZATION_SCHEMA_VERSION,
            "owner": CURRENT_IDENTITY_NORMALIZATION_OWNER,
            "inventorySha256": inventory_sha,
            "source": source_relative,
            "target": target.relative_to(work_items).as_posix(),
            "readmeSha256": readme_sha,
            "rows": rows,
        }
        _atomic_write(receipt, (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode())
        if not _normalization_replay(
            root, category, inventory_bytes, receipt, source, target
        ):
            raise RuntimeError("normalization settled receipt verification failed")
        return target, False
    except BaseException as exc:
        try:
            if move_temp is not None and move_temp.exists():
                os.replace(move_temp, source)
                move_temp.parent.rmdir()
            elif moved and _normalization_exact_file(target) and not _normalization_exact_file(source):
                temp_dir = Path(tempfile.mkdtemp(prefix=f".{source.stem}.rollback.", dir=source.parent))
                rollback_temp = temp_dir / target.name
                os.replace(target, rollback_temp)
                os.replace(rollback_temp, source)
                temp_dir.rmdir()
            for path, before in preimages.items():
                _atomic_write(path, before)
            if readme_before is None:
                if readme.exists():
                    readme.unlink()
            else:
                _atomic_write(readme, readme_before)
            if receipt.exists():
                receipt.unlink()
        except BaseException as rollback_exc:
            raise _normalization_fail(
                "WI-IDENTITY-NORMALIZE-ROLLBACK", f"rollback failed: {rollback_exc}"
            ) from exc
        raise _normalization_fail("WI-IDENTITY-NORMALIZE-ROLLBACK", str(exc)) from exc


CATEGORY_ADMISSION_TABLE = (
    CategoryAdmission(
        "work-item",
        "mutate-work-item:_category_locations",
        "mutate-work-item:_validate_closure",
        "closure.md:Closed",
        "work_item_terminal_evidence_missing",
        "Closed",
        "Outcome",
        "Evidence",
    ),
    CategoryAdmission(
        "bug",
        "mutate-work-item:_category_locations",
        "mutate-work-item:_validate_flat_terminal",
        "bug:Terminal-at",
        "bug_terminal_evidence_missing",
        "Terminal-at",
        "Resolution",
        "Evidence",
    ),
    CategoryAdmission(
        "decision",
        "mutate-work-item:_category_locations",
        "mutate-work-item:_validate_flat_terminal",
        "decision:Terminal-at",
        "decision_terminal_evidence_missing",
        "Terminal-at",
        "Rationale",
        "Evidence",
    ),
    CategoryAdmission(
        "lesson",
        "mutate-work-item:_category_locations",
        "mutate-work-item:_validate_flat_terminal",
        "lesson:Terminal-at",
        "lesson_terminal_evidence_missing",
        "Terminal-at",
        "Disposition",
        "Evidence",
    ),
    CategoryAdmission(
        "roadmap",
        "mutate-work-item:_category_locations",
        "mutate-work-item:_validate_flat_terminal",
        "roadmap:Terminal-at",
        "roadmap_terminal_evidence_missing",
        "Terminal-at",
        "Disposition",
        "Evidence",
    ),
    CategoryAdmission(
        "epic",
        "mutate-work-item:_category_locations",
        "mutate-work-item:_validate_flat_terminal",
        "epic:Closed",
        "epic_terminal_evidence_missing",
        "Closed",
        "Outcome",
        "Evidence",
    ),
)


def _admission_for(category_name: str) -> CategoryAdmission:
    rows = [row for row in CATEGORY_ADMISSION_TABLE if row.category == category_name]
    if len(CATEGORY_ADMISSION_TABLE) != 6 or len(rows) != 1:
        raise LifecycleError(
            "CATEGORY-MIGRATION-ADMISSION-GATE",
            f"category admission table is incomplete or duplicated: {category_name}",
        )
    row = rows[0]
    if not all(
        (
            row.category,
            row.current_reader,
            row.terminal_validator,
            row.utc_field_owner,
            row.negative_fixture,
            row.utc_field,
            row.detail_field,
            row.evidence_field,
        )
    ):
        raise LifecycleError(
            "CATEGORY-MIGRATION-ADMISSION-GATE",
            f"category admission row has a missing cell: {category_name}",
        )
    return row


def _move_terminal_category(root: Path, reference: str) -> Path:
    category, slug = _canonical_category(reference)
    _admission_for(category.name)
    locations = _category_locations(root, category, slug)
    if len(locations) > 1:
        raise LifecycleError("WI-CATEGORY-DUAL-LOCATION", f"duplicate slug: {reference}")
    if len(locations) != 1:
        raise LifecycleError("WI-INVALID-TARGET", f"missing category record: {reference}")
    source = locations[0]
    if category.name == "work-item":
        closure = source / "closure.md"
        if not closure.is_file():
            raise LifecycleError(
                "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING", "work-item lacks closure.md"
            )
        if "archive" in source.parts:
            _archived_work_item_entry(source)
            refresh_readme(root)
            return source
        fields = _parse_fields(closure.read_text(encoding="utf-8"))
        instant = fields.get("closed", "")
        closure_data = closure.read_bytes()
        _validate_closure(closure_data, instant)
        terminal_closure = _stamp_schema_marker(closure_data, "closure.md")
        target = _work_items_root(root) / "archive" / archive_month(instant) / slug
        if not source.is_dir() or source.parent.name != "active":
            raise LifecycleError("WI-INVALID-TARGET", "work-item migration requires active/")
        _validate_item_before_close(source)
        status = source / "status.md"
        terminal_status = _terminalize_status(status.read_bytes())
    else:
        instant = _validate_flat_terminal(category, source.read_bytes())
        target = (
            _work_items_root(root)
            / category.current_root
            / "archive"
            / archive_month(instant)
            / source.name
        )
        if "archive" in source.parts:
            if source != target:
                raise LifecycleError(
                    "WI-CATEGORY-ARCHIVE-MONTH-MISMATCH",
                    f"{reference} is not in archive/{archive_month(instant)}",
                )
            refresh_readme(root)
            return source
    _preflight_readme_markers(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise LifecycleError("WI-CATEGORY-DUAL-LOCATION", f"archive target exists: {target}")
    if category.name == "work-item":
        prior_status = status.read_bytes()
        prior_closure = closure.read_bytes()
        _atomic_write(status, terminal_status)
        _atomic_write(closure, terminal_closure)
    try:
        os.replace(source, target)
    except BaseException:
        if category.name == "work-item":
            _atomic_write(status, prior_status)
            _atomic_write(closure, prior_closure)
        raise
    try:
        refresh_readme(root)
    except LifecycleError as exc:
        raise LifecycleError("WI-README-STALE", str(exc)) from exc
    return target


def migrate_legacy(
    root: Path, reference: str, *, incoming_links_inventory: Path | None
) -> Path:
    category, _slug = _canonical_category(reference)
    _admission_for(category.name)
    if incoming_links_inventory is None or not incoming_links_inventory.is_file():
        raise LifecycleError(
            "WI-LEGACY-LINK-UNMAPPED",
            f"legacy move requires an incoming-link inventory: {reference}",
        )
    try:
        inventory = json.loads(incoming_links_inventory.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleError("WI-LEGACY-LINK-UNMAPPED", "invalid incoming-link inventory") from exc
    if not isinstance(inventory, dict) or inventory.get("reference") != reference:
        raise LifecycleError(
            "WI-LEGACY-LINK-UNMAPPED", "incoming-link inventory is not target-bound"
        )
    return _move_terminal_category(root, reference)


def _payload_digest(path: Path) -> tuple[str, str]:
    if path.is_symlink():
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-PAYLOAD",
            f"symbolic-link payload is not admitted: {path}",
        )
    if path.is_file():
        return (
            MIGRATION_DIGEST_ALGORITHMS["file"],
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
    if not path.is_dir():
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-PAYLOAD",
            f"payload is not a file or directory: {path}",
        )
    digest = hashlib.sha256()
    digest.update(b"sha256-tree-entries-v1\0")
    for entry in sorted(path.rglob("*"), key=lambda item: item.relative_to(path).as_posix()):
        if entry.is_symlink():
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-PAYLOAD",
                f"symbolic-link tree entry is not admitted: {entry}",
            )
        relative = entry.relative_to(path).as_posix().encode("utf-8")
        if entry.is_dir():
            digest.update(b"D")
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
        elif entry.is_file():
            data = entry.read_bytes()
            digest.update(b"F")
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
            digest.update(len(data).to_bytes(8, "big"))
            digest.update(data)
        else:
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-PAYLOAD",
                f"unsupported tree entry: {entry}",
            )
    return MIGRATION_DIGEST_ALGORITHMS["directory"], digest.hexdigest()


def _selected_migration_records(root: Path) -> list[tuple[Category, str, Path]]:
    work_items = _work_items_root(root)
    selected: list[tuple[Category, str, Path]] = []
    active = work_items / "active"
    if active.is_dir():
        for item in sorted(path for path in active.iterdir() if path.is_dir()):
            status = item / "status.md"
            fields = (
                _parse_fields(status.read_text(encoding="utf-8", errors="replace"))
                if status.is_file()
                else {}
            )
            if (item / "closure.md").is_file() or fields.get("status") in CATEGORIES[
                "work-item"
            ].terminal_statuses:
                selected.append((CATEGORIES["work-item"], item.name, item))
    for category in CATEGORIES.values():
        if category.current_kind != "flat":
            continue
        current = work_items / category.current_root
        if not current.is_dir():
            continue
        for path in sorted(current.glob("*.md")):
            fields = _parse_fields(path.read_text(encoding="utf-8", errors="replace"))
            if fields.get("status") in category.terminal_statuses:
                selected.append((category, path.stem, path))
    return sorted(selected, key=lambda item: (item[0].name, item[1]))


def _planned_migration_target(
    root: Path,
    category: Category,
    slug: str,
    source: Path,
) -> tuple[str, Path]:
    locations = _category_locations(root, category, slug)
    if locations != [source]:
        failure = "WI-CATEGORY-DUAL-LOCATION" if len(locations) > 1 else "WI-INVALID-TARGET"
        raise LifecycleError(
            failure,
            f"{category.name}:{slug} does not resolve to its selected source",
        )
    return _validated_migration_payload_target(root, category, slug, source)


def _validated_migration_payload_target(
    root: Path,
    category: Category,
    slug: str,
    payload: Path,
) -> tuple[str, Path]:
    if category.name == "work-item":
        closure = payload / "closure.md"
        if not closure.is_file():
            raise LifecycleError(
                "WI-CATEGORY-TERMINAL-EVIDENCE-MISSING",
                f"work-item:{slug} lacks closure.md",
            )
        fields = _parse_fields(closure.read_text(encoding="utf-8"))
        instant = fields.get("closed", "")
        _validate_closure(closure.read_bytes(), instant)
        _validate_item_before_close(payload)
        target = _work_items_root(root) / "archive" / archive_month(instant) / slug
    else:
        instant = _validate_flat_terminal(category, payload.read_bytes())
        target = (
            _work_items_root(root)
            / category.current_root
            / "archive"
            / archive_month(instant)
            / f"{slug}.md"
        )
    return instant, target


MARKDOWN_LINK_RE = re.compile(
    r"\[(?P<label>[^\]\r\n]+)\]\(\s*(?:<(?P<angle>[^<>()\s\r\n]+)>|(?P<bare>[^()\s\r\n]+))\s*\)"
)


@dataclass(frozen=True)
class MarkdownLocalLink:
    label: str
    href: str
    href_start: int
    href_end: int


def _markdown_local_links(text: str) -> Iterable[MarkdownLocalLink]:
    """Yield only complete, closed, local Markdown link destinations."""
    for match in MARKDOWN_LINK_RE.finditer(text):
        href = match.group("angle") or match.group("bare")
        yield MarkdownLocalLink(
            label=match.group("label"),
            href=href,
            href_start=match.start("angle") if match.group("angle") is not None else match.start("bare"),
            href_end=match.end("angle") if match.group("angle") is not None else match.end("bare"),
        )


URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def _local_markdown_href_parts(href: str) -> tuple[str, str] | None:
    """Split one local href into filesystem identity and preserved suffix."""
    if (
        not href
        or href.startswith(("#", "/", "\\"))
        or URI_SCHEME_RE.match(href)
    ):
        return None
    suffix_offsets = [offset for marker in ("#", "?") if (offset := href.find(marker)) >= 0]
    split_at = min(suffix_offsets) if suffix_offsets else len(href)
    filesystem_identity = href[:split_at]
    if not filesystem_identity:
        return None
    return filesystem_identity, href[split_at:]


def _markdown_href_resolves(base: Path, href: str, expected: Path) -> bool:
    parts = _local_markdown_href_parts(href)
    return parts is not None and (base / parts[0]).resolve() == expected.resolve()


def _incoming_link_result(
    root: Path,
    owned_paths: Iterable[Path],
    reference: str,
    *,
    literal_path_references: Iterable[str] = (),
    mutable_consumers_only: bool = False,
    scan_markdown_links: bool = True,
) -> dict:
    work_items = _work_items_root(root)
    physical: list[dict[str, str]] = []
    logical: list[dict[str, str]] = []
    owned_resolved = frozenset(path.resolve() for path in owned_paths)
    if not owned_resolved:
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-INVENTORY",
            f"incoming-link scan has no owned paths for {reference}",
        )
    literal_paths = tuple(sorted(set(literal_path_references)))
    if any(not path or path.startswith(("/", "\\")) for path in literal_paths):
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-INVENTORY",
            f"incoming-link scan has invalid literal path for {reference}",
        )
    literal_patterns = tuple(
        (
            literal_path,
            re.compile(
                rf"(?<![A-Za-z0-9_.\\/-]){re.escape(literal_path).replace('/', r'[\\/]')}(?![A-Za-z0-9_.\\/-])"
            ),
        )
        for literal_path in literal_paths
    )

    def belongs_to_owned(path: Path) -> bool:
        return any(
            path == owned or owned in path.parents
            for owned in owned_resolved
        )

    for consumer in sorted(path for path in work_items.rglob("*") if path.is_file()):
        if consumer.name in {"README.md", "index.md"}:
            continue
        consumer_resolved = consumer.resolve()
        if belongs_to_owned(consumer_resolved):
            continue
        try:
            consumer_bytes = consumer.read_bytes()
            text = consumer_bytes.decode("utf-8")
        except (OSError, UnicodeError):
            continue
        consumer_rel = consumer.relative_to(work_items).as_posix()
        if mutable_consumers_only and "archive" in Path(consumer_rel).parts:
            continue
        if reference in text:
            logical.append(
                {"consumer": consumer_rel, "kind": "logical", "value": reference}
            )
        if scan_markdown_links:
            for link in _markdown_local_links(text):
                raw = link.href
                href_parts = _local_markdown_href_parts(raw)
                if href_parts is None:
                    continue
                candidate = (consumer.parent / href_parts[0]).resolve()
                if belongs_to_owned(candidate):
                    physical.append(
                        {
                            "consumer": consumer_rel,
                            "kind": "physical",
                            "value": raw,
                        }
                    )
        for literal_path, literal_pattern in literal_patterns:
            if literal_pattern.search(text):
                physical.append(
                    {
                        "consumer": consumer_rel,
                        "kind": "physical",
                        "value": literal_path,
                    }
                )
    references = sorted(
        physical + logical,
        key=lambda item: (item["consumer"], item["kind"], item["value"]),
    )
    if physical:
        result = "unmapped"
    elif logical:
        result = "logical-only"
    else:
        result = "clear"
    return {"result": result, "references": references}


def _validate_incoming_link_snapshot(reference: str, snapshot: dict, *, label: str) -> None:
    if not isinstance(snapshot, dict):
        raise LifecycleError(
            "WI-LEGACY-LINK-UNMAPPED",
            f"{label} incoming-link inventory is invalid for {reference}",
        )
    result = snapshot.get("result")
    links = snapshot.get("references")
    if result not in {"clear", "logical-only"} or not isinstance(links, list):
        raise LifecycleError(
            "WI-LEGACY-LINK-UNMAPPED",
            f"{label} incoming links are not logical-only for {reference}",
        )
    expected_result = "logical-only" if links else "clear"
    if result != expected_result:
        raise LifecycleError(
            "WI-LEGACY-LINK-UNMAPPED",
            f"{label} incoming-link result differs from its rows for {reference}",
        )
    seen: set[tuple[str, str, str]] = set()
    for link in links:
        if (
            not isinstance(link, dict)
            or not isinstance(link.get("consumer"), str)
            or link.get("kind") != "logical"
            or link.get("value") != reference
        ):
            raise LifecycleError(
                "WI-LEGACY-LINK-UNMAPPED",
                f"{label} incoming link is not category-qualified logical for {reference}",
            )
        identity = (link["consumer"], link["kind"], link["value"])
        if identity in seen:
            raise LifecycleError(
                "WI-LEGACY-LINK-UNMAPPED",
                f"{label} incoming-link inventory repeats a row for {reference}",
            )
        seen.add(identity)


def _validate_incoming_link_compatibility(
    root: Path,
    reference: str,
    planned: dict,
    current: dict,
    *,
    resolved_location: Path,
) -> None:
    for label, snapshot in (("planned", planned), ("current", current)):
        _validate_incoming_link_snapshot(reference, snapshot, label=label)
    try:
        resolved = resolve_category(root, reference)
    except LifecycleError as exc:
        raise LifecycleError(
            "WI-LEGACY-LINK-UNMAPPED",
            f"logical reference does not resolve uniquely: {reference}",
        ) from exc
    if resolved != resolved_location.resolve():
        raise LifecycleError(
            "WI-LEGACY-LINK-UNMAPPED",
            f"logical reference resolves outside the migration payload: {reference}",
        )


def build_migration_inventory(root: Path) -> dict:
    work_items = _work_items_root(root)
    rows: list[dict] = []
    for category, slug, source in _selected_migration_records(root):
        reference = f"{category.name}:{slug}"
        algorithm, input_hash = _payload_digest(source)
        admission_row = _admission_for(category.name)
        row = {
            "reference": reference,
            "category": category.name,
            "source": source.relative_to(work_items).as_posix(),
            "target": None,
            "terminalInstant": None,
            "inputSha256": input_hash,
            "digestAlgorithm": algorithm,
            "incomingLinks": None,
            "admission": {
                "result": "admitted",
                "reader": admission_row.current_reader,
                "validator": admission_row.terminal_validator,
                "utcOwner": admission_row.utc_field_owner,
                "negativeFixture": admission_row.negative_fixture,
            },
        }
        try:
            instant, target = _planned_migration_target(
                root, category, slug, source
            )
            row["terminalInstant"] = instant
            row["target"] = target.relative_to(work_items).as_posix()
        except LifecycleError as exc:
            row["admission"] = {
                "result": "denied",
                "failureId": exc.failure_id,
                "reason": str(exc),
            }
        owned_paths = {source}
        if row["target"] is not None:
            owned_paths.add(work_items / Path(row["target"]))
        row["incomingLinks"] = _incoming_link_result(
            root,
            owned_paths,
            reference,
        )
        rows.append(row)
    return {
        "schemaVersion": MIGRATION_SCHEMA_VERSION,
        "owner": MIGRATION_OWNER,
        "workItemsRoot": str(work_items.resolve()),
        "digestAlgorithms": dict(MIGRATION_DIGEST_ALGORITHMS),
        "rows": rows,
    }


def write_migration_inventory(root: Path, output: Path) -> dict:
    _static_guide(
        _work_items_root(root) / "README.md",
        allow_marker_bootstrap=True,
    )
    inventory = build_migration_inventory(root)
    _atomic_write(
        output,
        (json.dumps(inventory, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    for row in inventory["rows"]:
        admission = row["admission"]
        if admission.get("result") != "admitted":
            raise LifecycleError(
                admission.get("failureId", "CATEGORY-MIGRATION-ADMISSION-GATE"),
                admission.get("reason", f"unadmitted row: {row['reference']}"),
            )
        if row["incomingLinks"].get("result") == "unmapped":
            raise LifecycleError(
                "WI-LEGACY-LINK-UNMAPPED",
                f"physical incoming links remain for {row['reference']}",
            )
    return inventory


def _reject_duplicate_json_pairs(pairs: list[tuple[str, object]]) -> dict:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-INVENTORY",
                f"migration inventory repeats JSON key: {key}",
            )
        value[key] = item
    return value


def _capture_path_parent_chain(
    path: Path,
    failure_id: str,
) -> CapturedPathParentChain:
    parent = _lifecycle_unresolved_absolute(path).parent
    cursor = Path(parent.anchor)
    participants = []
    try:
        root_info = cursor.lstat()
        if stat.S_ISLNK(root_info.st_mode) or bool(
            getattr(root_info, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        ):
            raise OSError("path root is a link or reparse point")
        participants.append((cursor, _lifecycle_file_identity(root_info)))
        for part in parent.parts[1:]:
            if part in {"", "."}:
                continue
            if part == "..":
                cursor = cursor.parent
                continue
            cursor /= part
            info = cursor.lstat()
            if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or bool(
                getattr(info, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            ):
                raise OSError("path parent is not a regular non-reparse directory")
            participants.append((cursor, _lifecycle_file_identity(info)))
    except OSError as exc:
        raise LifecycleError(failure_id, "file parent chain cannot be captured") from exc
    return CapturedPathParentChain(tuple(participants))


def _verify_captured_parent_chain(
    chain: CapturedPathParentChain,
    failure_id: str,
) -> None:
    try:
        for path, identity in chain.participants:
            info = path.lstat()
            if (
                not stat.S_ISDIR(info.st_mode)
                or stat.S_ISLNK(info.st_mode)
                or bool(
                    getattr(info, "st_file_attributes", 0)
                    & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
                )
                or _lifecycle_file_identity(info) != identity
            ):
                raise OSError("captured parent identity changed")
    except OSError as exc:
        raise LifecycleError(failure_id, "captured file parent chain changed") from exc


def _open_readonly_nofollow(path: Path) -> int:
    if os.name != "nt":
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        if not nofollow:
            raise OSError(errno.ENOTSUP, "no-follow file open is unavailable")
        return os.open(path, os.O_RDONLY | nofollow)

    import ctypes
    import ctypes.wintypes
    import msvcrt

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        ctypes.wintypes.LPCWSTR,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.LPVOID,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.HANDLE,
    ]
    create_file.restype = ctypes.wintypes.HANDLE
    native_handle = create_file(
        str(path),
        0x80000000,  # GENERIC_READ
        0x00000001 | 0x00000002 | 0x00000004,
        None,
        3,  # OPEN_EXISTING
        0x00200000,  # FILE_FLAG_OPEN_REPARSE_POINT
        None,
    )
    if native_handle == ctypes.wintypes.HANDLE(-1).value:
        raise OSError(ctypes.get_last_error(), "cannot open file without following links")
    try:
        return msvcrt.open_osfhandle(
            native_handle,
            os.O_RDONLY | getattr(os, "O_BINARY", 0),
        )
    except BaseException:
        kernel32.CloseHandle(native_handle)
        raise


def _capture_file_snapshot(
    path: Path,
    *,
    failure_id: str,
    maximum_bytes: int = 4 * 1024 * 1024,
) -> CapturedFileSnapshot:
    parent_chain = _capture_path_parent_chain(path, failure_id)
    try:
        if _lifecycle_path_has_reparse(path):
            raise OSError("path is a link or reparse point")
        descriptor = _open_readonly_nofollow(path)
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            before = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(before.st_mode)
                or bool(
                    getattr(before, "st_file_attributes", 0)
                    & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
                )
                or before.st_size > maximum_bytes
            ):
                raise OSError("snapshot is not a bounded regular file")
            data = stream.read(maximum_bytes + 1)
            after = os.fstat(stream.fileno())
        current = path.lstat()
    except OSError as exc:
        raise LifecycleError(failure_id, "file snapshot identity cannot be captured") from exc
    identity = _lifecycle_file_identity(before)
    if (
        len(data) > maximum_bytes
        or len(data) != before.st_size
        or before.st_size != after.st_size
        or _lifecycle_file_identity(after) != identity
        or _lifecycle_file_identity(current) != identity
        or stat.S_ISLNK(current.st_mode)
        or bool(
            getattr(current, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        )
        or _lifecycle_path_has_reparse(path)
    ):
        raise LifecycleError(failure_id, "file snapshot changed during capture")
    _verify_captured_parent_chain(parent_chain, failure_id)
    return CapturedFileSnapshot(path, identity, len(data), data, parent_chain)


def _verify_captured_file(snapshot: CapturedFileSnapshot, failure_id: str) -> None:
    _verify_captured_parent_chain(snapshot.parent_chain, failure_id)
    try:
        current = snapshot.path.lstat()
    except OSError as exc:
        raise LifecycleError(failure_id, "captured file path is no longer available") from exc
    if (
        _lifecycle_path_has_reparse(snapshot.path)
        or stat.S_ISLNK(current.st_mode)
        or bool(
            getattr(current, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        )
        or _lifecycle_file_identity(current) != snapshot.identity
        or current.st_size != snapshot.length
    ):
        raise LifecycleError(failure_id, "captured file path identity changed")


def _parse_migration_inventory_bytes(
    root: Path,
    snapshot: bytes,
    *,
    strict_shape: bool = False,
) -> dict:
    try:
        inventory = json.loads(
            snapshot.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_pairs,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-INVENTORY",
            "migration inventory is not strict UTF-8 JSON",
        ) from exc
    work_items = _work_items_root(root)
    if (
        not isinstance(inventory, dict)
        or (
            strict_shape
            and set(inventory)
            != {
                "digestAlgorithms",
                "owner",
                "rows",
                "schemaVersion",
                "workItemsRoot",
            }
        )
        or inventory.get("schemaVersion") != MIGRATION_SCHEMA_VERSION
        or inventory.get("owner") != MIGRATION_OWNER
        or inventory.get("workItemsRoot") != str(work_items.resolve())
        or inventory.get("digestAlgorithms") != MIGRATION_DIGEST_ALGORITHMS
        or not isinstance(inventory.get("rows"), list)
    ):
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-INVENTORY",
            "migration inventory schema or target binding differs",
        )
    allowed_row_fields = {
        "admission",
        "category",
        "digestAlgorithm",
        "incomingLinks",
        "inputSha256",
        "reference",
        "source",
        "target",
        "terminalInstant",
    }
    allowed_admission_fields = {
        "negativeFixture",
        "reader",
        "result",
        "utcOwner",
        "validator",
    }
    if strict_shape:
        for row in inventory["rows"]:
            if (
                not isinstance(row, dict)
                or set(row) != allowed_row_fields
                or not isinstance(row.get("admission"), dict)
                or set(row["admission"]) != allowed_admission_fields
                or not isinstance(row.get("incomingLinks"), dict)
                or not set(row["incomingLinks"]).issubset(
                    {"physicalRelocation", "references", "result"}
                )
            ):
                raise LifecycleError(
                    "WI-CATEGORY-MIGRATION-INVENTORY",
                    "migration inventory row shape differs",
                )
    return inventory


def _load_migration_inventory(root: Path, inventory_path: Path) -> dict:
    snapshot = _capture_file_snapshot(
        inventory_path,
        failure_id="WI-CATEGORY-MIGRATION-INVENTORY",
    )
    return _parse_migration_inventory_bytes(root, snapshot.data)


def _terminalization_fail(message: str) -> LifecycleError:
    return LifecycleError(V1_TERMINALIZATION_FAILURE, message)


def _terminalization_has_reparse(path: Path) -> bool:
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError as exc:
        raise _terminalization_fail(f"cannot inspect terminalization path: {path}") from exc
    return path.is_symlink() or bool(
        attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _terminalization_bound_path(
    work_items: Path,
    relative: str,
    *,
    label: str,
) -> Path:
    if not isinstance(relative, str) or not relative:
        raise _terminalization_fail(f"{label} path is missing")
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise _terminalization_fail(f"{label} path escapes work-items: {relative!r}")
    root = work_items.resolve()
    cursor = work_items
    if _terminalization_has_reparse(cursor):
        raise _terminalization_fail(f"work-items root is a link or reparse point: {cursor}")
    for part in relative_path.parts:
        cursor = cursor / part
        if cursor.exists() or cursor.is_symlink():
            if _terminalization_has_reparse(cursor):
                raise _terminalization_fail(
                    f"{label} path contains a link or reparse point: {cursor}"
                )
    resolved = cursor.resolve()
    if resolved != root and root not in resolved.parents:
        raise _terminalization_fail(f"{label} path escapes work-items: {relative!r}")
    return resolved


def _bound_repository_scratch_path(
    root: Path,
    path: str | Path,
    *,
    label: str,
    allow_absolute: bool,
) -> Path:
    candidate = Path(path) if isinstance(path, (str, Path)) else Path()
    if not candidate.parts or ".." in candidate.parts:
        raise _terminalization_fail(f"{label} path is unsafe")
    repo_root = _work_items_root(root).parent.resolve()
    if candidate.is_absolute():
        if not allow_absolute:
            raise _terminalization_fail(f"{label} path must be repository-relative")
        try:
            relative = candidate.relative_to(repo_root)
        except ValueError as exc:
            raise _terminalization_fail(f"{label} path escapes the repository") from exc
    else:
        relative = candidate
    if len(relative.parts) < 2 or relative.parts[0] != ".scratch":
        raise _terminalization_fail(f"{label} must be a file under repository .scratch")
    if _terminalization_has_reparse(repo_root):
        raise _terminalization_fail(f"repository root is a link or reparse point: {repo_root}")
    cursor = repo_root
    for part in relative.parts:
        cursor = cursor / part
        if (cursor.exists() or cursor.is_symlink()) and _terminalization_has_reparse(cursor):
            raise _terminalization_fail(
                f"{label} path contains a link or reparse point: {cursor}"
            )
    resolved = cursor.resolve()
    scratch = (repo_root / ".scratch").resolve()
    if resolved == scratch or scratch not in resolved.parents:
        raise _terminalization_fail(f"{label} escapes repository .scratch")
    return resolved


def _bound_physical_receipt(root: Path, relative: str) -> Path:
    return _bound_repository_scratch_path(
        root,
        relative,
        label="physical-relocation receipt",
        allow_absolute=False,
    )


def _physical_relocation_admission(
    root: Path,
    reference: str,
    incoming: object,
    *,
    receipt_path: Path | None = None,
) -> tuple[list[dict], dict | None]:
    if not isinstance(incoming, dict) or not isinstance(incoming.get("references"), list):
        raise _terminalization_fail(f"incoming-link inventory is invalid for {reference}")
    links = incoming["references"]
    physical: list[dict] = []
    logical: list[dict] = []
    for link in links:
        if (
            not isinstance(link, dict)
            or not isinstance(link.get("consumer"), str)
            or not isinstance(link.get("value"), str)
        ):
            raise _terminalization_fail(f"incoming-link row is invalid for {reference}")
        if link.get("kind") == "physical":
            physical.append(link)
        elif link.get("kind") == "logical" and link["value"] == reference:
            logical.append(link)
        else:
            raise _terminalization_fail(f"incoming-link kind or identity differs for {reference}")
    if not physical:
        expected_result = "logical-only" if logical else "clear"
        if incoming.get("result") != expected_result or "physicalRelocation" in incoming:
            raise _terminalization_fail(
                f"incoming-link result differs from its rows for {reference}"
            )
        return links, None
    if len(physical) != 1 or logical or incoming.get("result") != "physical-relocation":
        raise _terminalization_fail(
            f"physical relocation requires one exact incoming link for {reference}"
        )
    admission = incoming.get("physicalRelocation")
    required = {
        "source",
        "label",
        "href",
        "expectedIdentity",
        "sourceSha256",
        "targetSha256",
        "receipt",
    }
    if not isinstance(admission, dict) or set(admission) != required:
        raise _terminalization_fail(
            f"physical-relocation admission shape differs for {reference}"
        )
    source_relative = admission.get("source")
    source_parts = Path(source_relative).parts if isinstance(source_relative, str) else ()
    if (
        source_relative != physical[0]["consumer"]
        or admission.get("href") != physical[0]["value"]
        or admission.get("expectedIdentity") != reference
        or not isinstance(admission.get("label"), str)
        or not admission["label"]
        or not re.fullmatch(r"[0-9a-f]{64}", str(admission.get("sourceSha256", "")))
        or not re.fullmatch(r"[0-9a-f]{64}", str(admission.get("targetSha256", "")))
        or len(source_parts) < 4
        or source_parts[-3] != "archive"
        or not re.fullmatch(r"\d{4}-\d{2}", source_parts[-2])
    ):
        raise _terminalization_fail(
            f"physical-relocation tuple differs for {reference}"
        )
    bound_receipt = _bound_physical_receipt(root, admission["receipt"])
    if receipt_path is not None and bound_receipt != receipt_path.resolve():
        raise _terminalization_fail(
            f"physical-relocation receipt binding differs for {reference}"
        )
    return links, admission


def _plan_v1_link_relocations(
    root: Path,
    planned: list[dict],
    terminal_at: str,
    receipt_path: Path,
) -> tuple[list[dict], list[dict]]:
    work_items = _work_items_root(root)
    admissions: list[tuple[dict, dict]] = []
    for item in planned:
        _links, admission = _physical_relocation_admission(
            root,
            item["reference"],
            item["incomingLinks"],
            receipt_path=receipt_path,
        )
        if admission is not None:
            admissions.append((item, admission))
    if len(admissions) > 1:
        raise _terminalization_fail("only one exact physical relocation is admitted")
    consumer_plans: list[dict] = []
    receipt_links: list[dict] = []
    for item, admission in admissions:
        consumer_relative = admission["source"]
        consumer = _terminalization_bound_path(
            work_items, consumer_relative, label="physical-link consumer"
        )
        if consumer.suffix.casefold() != ".md" or not consumer.is_file():
            raise _terminalization_fail(
                f"physical-link consumer is not a Markdown file: {consumer_relative}"
            )
        if consumer == item["source"]:
            raise _terminalization_fail(
                f"physical-link consumer is also moving: {consumer_relative}"
            )
        before = consumer.read_bytes()
        before_sha256 = hashlib.sha256(before).hexdigest()
        if admission["sourceSha256"] != before_sha256:
            raise _terminalization_fail(
                f"physical-link consumer hash changed: {consumer_relative}"
            )
        if admission["targetSha256"] != item["beforeSha256"]:
            raise _terminalization_fail(
                f"physical-link target hash changed: {item['reference']}"
            )
        try:
            text = before.decode("utf-8")
        except UnicodeError as exc:
            raise _terminalization_fail(
                f"physical-link consumer is not UTF-8 Markdown: {consumer_relative}"
            ) from exc

        matches = [
            link
            for link in _markdown_local_links(text)
            if link.label == admission["label"] and link.href == admission["href"]
        ]
        if len(matches) != 1:
            raise _terminalization_fail(
                f"physical Markdown tuple is missing or duplicated: {consumer_relative}"
            )
        href_parts = _local_markdown_href_parts(admission["href"])
        if href_parts is None or not _markdown_href_resolves(
            consumer.parent, admission["href"], item["source"]
        ):
            raise _terminalization_fail(
                f"physical Markdown href resolves outside expected identity: {consumer_relative}"
            )
        new_path = Path(os.path.relpath(item["target"], consumer.parent)).as_posix()
        new_href = new_path + href_parts[1]
        if not _markdown_href_resolves(consumer.parent, new_href, item["target"]):
            raise _terminalization_fail(
                f"relocated href does not resolve to target: {consumer_relative}"
            )
        after_text = (
            text[:matches[0].href_start]
            + new_href
            + text[matches[0].href_end:]
        )
        after = after_text.encode("utf-8")
        after_sha256 = hashlib.sha256(after).hexdigest()
        consumer_plans.append(
            {
                "consumer": consumer,
                "consumerRelative": consumer_relative,
                "before": before,
                "beforeSha256": before_sha256,
                "after": after,
                "afterSha256": after_sha256,
            }
        )
        receipt_links.append(
            {
                "source": consumer_relative,
                "label": admission["label"],
                "oldHref": admission["href"],
                "newHref": new_href,
                "expectedIdentity": item["reference"],
                "finalTarget": item["targetRelative"],
                "sourceBeforeSha256": before_sha256,
                "sourceAfterSha256": None,
                "targetBeforeSha256": item["afterSha256"],
                "targetAfterSha256": None,
                "terminalAt": terminal_at,
            }
        )
    return consumer_plans, receipt_links


def _expected_physical_relocation_receipt(
    root: Path,
    reference: str,
    admission: dict,
    source: Path,
    target: Path,
    target_before_sha256: str,
    terminal_at: str,
    *,
    settled: bool,
) -> dict:
    """Derive the one receipt relation allowed by an admitted physical link."""
    work_items = _work_items_root(root)
    consumer_relative = admission["source"]
    consumer = _terminalization_bound_path(
        work_items, consumer_relative, label="physical-link consumer"
    )
    if not consumer.is_file():
        raise _terminalization_fail(
            f"physical-link consumer is missing: {consumer_relative}"
        )
    href_parts = _local_markdown_href_parts(admission["href"])
    if href_parts is None:
        raise _terminalization_fail(
            f"physical Markdown href is not local: {consumer_relative}"
        )
    expected_href = Path(os.path.relpath(target, consumer.parent)).as_posix() + href_parts[1]
    current_href = expected_href if settled else admission["href"]
    resolved_target = target if settled else source
    try:
        current = consumer.read_bytes()
        text = current.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise _terminalization_fail(
            f"physical-link consumer is not UTF-8 Markdown: {consumer_relative}"
        ) from exc
    matches = [
        link
        for link in _markdown_local_links(text)
        if link.label == admission["label"]
        and link.href == current_href
        and _markdown_href_resolves(consumer.parent, link.href, resolved_target)
    ]
    if len(matches) != 1:
        raise _terminalization_fail(
            f"physical Markdown tuple is missing or duplicated: {consumer_relative}"
        )
    if settled:
        link = matches[0]
        source_before = hashlib.sha256(
            (
                text[:link.href_start]
                + admission["href"]
                + text[link.href_end:]
            ).encode("utf-8")
        ).hexdigest()
        source_after: str | None = hashlib.sha256(current).hexdigest()
        target_after: str | None = hashlib.sha256(target.read_bytes()).hexdigest()
    else:
        source_before = hashlib.sha256(current).hexdigest()
        source_after = None
        target_after = None
    payload = target if settled else source
    if (
        source_before != admission["sourceSha256"]
        or hashlib.sha256(payload.read_bytes()).hexdigest() != target_before_sha256
        or (settled and target_after != target_before_sha256)
    ):
        raise _terminalization_fail(
            f"physical-relocation evidence differs for {reference}"
        )
    return {
        "source": consumer_relative,
        "label": admission["label"],
        "oldHref": admission["href"],
        "newHref": expected_href,
        "expectedIdentity": reference,
        "finalTarget": target.relative_to(work_items).as_posix(),
        "sourceBeforeSha256": source_before,
        "sourceAfterSha256": source_after,
        "targetBeforeSha256": target_before_sha256,
        "targetAfterSha256": target_after,
        "terminalAt": terminal_at,
    }


def _terminalization_receipt_path(root: Path, path: Path) -> Path:
    return _bound_repository_scratch_path(
        root,
        path,
        label="terminalization receipt",
        allow_absolute=True,
    )


def _terminalization_replay(
    root: Path,
    inventory: dict,
    inventory_sha256: str,
    terminal_at: str,
    authorization_marker: str,
    receipt_path: Path,
) -> tuple[int, bool] | None:
    if not receipt_path.exists():
        return None
    if not receipt_path.is_file():
        raise _terminalization_fail(
            f"terminalization receipt is not a file: {receipt_path}"
        )
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _terminalization_fail(
            f"existing terminalization receipt is invalid: {receipt_path}"
        ) from exc
    work_items = _work_items_root(root)
    expected_header = {
        "schemaVersion": V1_TERMINALIZATION_SCHEMA_VERSION,
        "owner": V1_TERMINALIZATION_OWNER,
        "workItemsRoot": str(work_items.resolve()),
        "inventorySha256": inventory_sha256,
        "terminalAt": terminal_at,
        "authorizationMarker": authorization_marker,
        "rowCount": len(inventory["rows"]),
        "linkCount": sum(
            1
            for inventory_row in inventory["rows"]
            if isinstance(inventory_row, dict)
            for link in (inventory_row.get("incomingLinks") or {}).get("references", [])
            if isinstance(link, dict) and link.get("kind") == "physical"
        ),
    }
    if not isinstance(receipt, dict) or any(
        receipt.get(key) != value for key, value in expected_header.items()
    ):
        raise _terminalization_fail(
            "existing terminalization receipt does not match this exact operation"
        )
    receipt_rows = receipt.get("rows")
    if not isinstance(receipt_rows, list) or len(receipt_rows) != len(
        inventory["rows"]
    ):
        raise _terminalization_fail(
            "existing terminalization receipt row set differs"
        )
    inventory_references = sorted(
        row.get("reference") for row in inventory["rows"] if isinstance(row, dict)
    )
    receipt_references = sorted(
        row.get("reference") for row in receipt_rows if isinstance(row, dict)
    )
    if inventory_references != receipt_references:
        raise _terminalization_fail(
            "existing terminalization receipt references differ"
        )
    inventory_by_reference = {
        row.get("reference"): row for row in inventory["rows"] if isinstance(row, dict)
    }
    receipt_pairs: set[tuple[str, str]] = set()
    for row in receipt_rows:
        if not isinstance(row, dict):
            raise _terminalization_fail(
                "existing terminalization receipt contains an invalid row"
            )
        inventory_row = inventory_by_reference.get(row.get("reference"))
        if not isinstance(inventory_row, dict):
            raise _terminalization_fail(
                f"terminalization receipt has no inventory row: {row.get('reference')}"
            )
        source = _terminalization_bound_path(
            work_items, row.get("source"), label="receipt source"
        )
        target = _terminalization_bound_path(
            work_items, row.get("target"), label="receipt target"
        )
        category, slug = _canonical_category(row["reference"])
        expected_target = (
            work_items
            / category.current_root
            / "archive"
            / archive_month(terminal_at)
            / f"{slug}.md"
        ).resolve()
        source_exists = source.is_file()
        target_exists = target.is_file()
        payload = source if source_exists else target
        if (
            row.get("source") != inventory_row.get("source")
            or row.get("beforeSha256") != inventory_row.get("inputSha256")
            or source_exists == target_exists
            or target != expected_target
            or row.get("afterSha256")
            != hashlib.sha256(payload.read_bytes()).hexdigest()
            or _category_locations(root, category, slug) != [payload]
        ):
            raise _terminalization_fail(
                f"terminalized payload differs from receipt: {row.get('reference')}"
            )
        receipt_pairs.add((row["source"], row["target"]))
    receipt_link_rows = [
        (receipt_row, receipt_row["physicalRelocation"])
        for receipt_row in receipt_rows
        if isinstance(receipt_row, dict)
        and isinstance(receipt_row.get("physicalRelocation"), dict)
    ]
    if len(receipt_link_rows) != expected_header["linkCount"]:
        raise _terminalization_fail("existing terminalization receipt link set differs")
    seen_link_rows: set[tuple[str, str, str, str]] = set()
    for owner_row, link in receipt_link_rows:
        if not isinstance(link, dict) or link.get("terminalAt") != terminal_at:
            raise _terminalization_fail("existing terminalization receipt link row is invalid")
        consumer = _terminalization_bound_path(
            work_items, link.get("source"), label="receipt link consumer"
        )
        new_target = _terminalization_bound_path(
            work_items, link.get("finalTarget"), label="receipt new target"
        )
        before_sha256 = link.get("sourceBeforeSha256")
        after_sha256 = link.get("sourceAfterSha256")
        target_before_sha256 = link.get("targetBeforeSha256")
        target_after_sha256 = link.get("targetAfterSha256")
        old_href = link.get("oldHref")
        new_href = link.get("newHref")
        label = link.get("label")
        identity = link.get("expectedIdentity")
        old_target_relative = next(
            (
                old
                for old, new in receipt_pairs
                if new == link.get("finalTarget")
            ),
            None,
        )
        old_target = (
            _terminalization_bound_path(
                work_items, old_target_relative, label="receipt old target"
            )
            if old_target_relative is not None
            else None
        )
        pending = old_target is not None and old_target.is_file() and not new_target.exists()
        settled = old_target is not None and not old_target.exists() and new_target.is_file()
        if (
            old_target is None
            or not isinstance(before_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", before_sha256)
            or not isinstance(target_before_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", target_before_sha256)
            or (pending and (after_sha256 is not None or target_after_sha256 is not None))
            or (
                settled
                and (
                    not isinstance(after_sha256, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", after_sha256)
                    or not isinstance(target_after_sha256, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", target_after_sha256)
                    or hashlib.sha256(new_target.read_bytes()).hexdigest()
                    != target_after_sha256
                )
            )
            or not isinstance(old_href, str)
            or not isinstance(new_href, str)
            or not isinstance(label, str)
            or not isinstance(identity, str)
            or not (pending or settled)
            or not consumer.is_file()
            or hashlib.sha256(consumer.read_bytes()).hexdigest()
            != (before_sha256 if pending else after_sha256)
        ):
            raise _terminalization_fail(
                f"terminalized link differs from receipt: {link.get('source')}"
            )
        key = (link["source"], old_href, new_href, link["finalTarget"])
        if key in seen_link_rows:
            raise _terminalization_fail("terminalization receipt repeats a physical link")
        seen_link_rows.add(key)
        try:
            text = consumer.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise _terminalization_fail(
                f"terminalized link consumer is unreadable: {link.get('source')}"
            ) from exc
        expected_href = old_href if pending else new_href
        expected_target = old_target if pending else new_target
        resolved_matches = [
            link
            for link in _markdown_local_links(text)
            if link.label == label
            and link.href == expected_href
            and _markdown_href_resolves(consumer.parent, link.href, expected_target)
        ]
        if len(resolved_matches) != 1:
            raise _terminalization_fail(
                f"terminalized Markdown href is missing: {link.get('source')}"
            )
        owner_reference = owner_row["reference"]
        owner_inventory_row = inventory_by_reference[owner_reference]
        _links, admission = _physical_relocation_admission(
            root,
            owner_reference,
            owner_inventory_row.get("incomingLinks"),
            receipt_path=receipt_path,
        )
        if admission is None or link != _expected_physical_relocation_receipt(
            root,
            owner_reference,
            admission,
            old_target,
            new_target,
            owner_row["afterSha256"],
            terminal_at,
            settled=settled,
        ):
            raise _terminalization_fail(
                f"terminalized physical-relocation receipt differs: {link.get('source')}"
            )
    return len(receipt_rows), True


def _preflight_v1_terminalization_rows(
    root: Path,
    inventory: dict,
    terminal_at: str,
    receipt_path: Path,
) -> tuple[list[dict], list[dict], list[dict]]:
    _strict_utc(terminal_at)
    work_items = _work_items_root(root)
    planned: list[dict] = []
    seen_sources: set[Path] = set()
    seen_targets: set[Path] = set()
    for row in inventory["rows"]:
        if not isinstance(row, dict):
            raise _terminalization_fail("terminalization inventory row is not an object")
        category_name = row.get("category")
        try:
            category, slug = _canonical_category(row.get("reference", ""))
        except LifecycleError as exc:
            raise _terminalization_fail(str(exc)) from exc
        if category.current_kind != "flat":
            raise _terminalization_fail(
                f"unsupported V1 terminalization category: {category_name!r}"
            )
        admission_row = _admission_for(category.name)
        if category.name != category_name:
            raise _terminalization_fail(
                f"category tuple differs for {row.get('reference')}"
            )
        admission = row.get("admission")
        if (
            not isinstance(admission, dict)
            or admission.get("result") != "denied"
            or admission.get("failureId") != V1_TERMINALIZATION_FAILURE
        ):
            raise _terminalization_fail(
                f"row is not denied solely for missing terminal evidence: "
                f"{row.get('reference')}"
            )
        incoming = row.get("incomingLinks")
        _incoming_rows, physical_relocation = _physical_relocation_admission(
            root,
            row["reference"],
            incoming,
            receipt_path=receipt_path,
        )
        if row.get("target") is not None or row.get("terminalInstant") is not None:
            raise _terminalization_fail(
                f"denied row already has a target or terminal instant: "
                f"{row.get('reference')}"
            )
        source = _terminalization_bound_path(
            work_items, row.get("source"), label="terminalization source"
        )
        expected_source = (
            work_items / category.current_root / f"{slug}.md"
        ).resolve()
        if source != expected_source or source in seen_sources:
            raise _terminalization_fail(
                f"source binding is ambiguous for {row.get('reference')}"
            )
        seen_sources.add(source)
        try:
            locations = _category_locations(root, category, slug)
        except OSError as exc:
            raise _terminalization_fail(
                f"cannot resolve locations for {row.get('reference')}"
            ) from exc
        if locations != [source] or not source.is_file():
            raise _terminalization_fail(
                f"current location is ambiguous for {row.get('reference')}"
            )
        target_relative = (
            Path(category.current_root)
            / "archive"
            / archive_month(terminal_at)
            / source.name
        ).as_posix()
        target = _terminalization_bound_path(
            work_items, target_relative, label="terminalization target"
        )
        if target in seen_targets or target.exists():
            raise _terminalization_fail(
                f"terminalization target is ambiguous for {row.get('reference')}"
            )
        seen_targets.add(target)
        if row.get("digestAlgorithm") != MIGRATION_DIGEST_ALGORITHMS["file"]:
            raise _terminalization_fail(
                f"unsupported digest algorithm for {row.get('reference')}"
            )
        before = source.read_bytes()
        before_sha256 = hashlib.sha256(before).hexdigest()
        if row.get("inputSha256") != before_sha256:
            raise _terminalization_fail(
                f"input payload hash changed for {row.get('reference')}"
            )
        try:
            text = before.decode("utf-8")
        except UnicodeError as exc:
            raise _terminalization_fail(
                f"terminal record is not UTF-8: {row.get('reference')}"
            ) from exc
        fields = _parse_fields(text)
        status = fields.get("status", "")
        if status not in category.terminal_statuses:
            raise _terminalization_fail(
                f"current status is not terminal for {row.get('reference')}: "
                f"{status!r}"
            )
        detail_field = admission_row.detail_field
        conflicting = tuple(
            dict.fromkeys(
                _terminalization_authoritative_field_occurrences(
                    text, admission_row.utc_field
                )
            )
        )
        if conflicting:
            raise _terminalization_fail(
                f"authoritative terminal field already exists for "
                f"{row.get('reference')}: {', '.join(conflicting)}"
            )
        current_links = _incoming_link_result(
            root,
            {source},
            row["reference"],
        )
        expected_current_links = (
            {
                "result": "unmapped",
                "references": incoming["references"],
            }
            if physical_relocation is not None
            else incoming
        )
        if current_links != expected_current_links:
            raise _terminalization_fail(
                f"incoming-link inventory changed for {row.get('reference')}"
            )
        separator = b"\n" if before.endswith(b"\n") else b"\n\n"
        proof = (
            "Historical terminal time is unknown; preserved pre-V1 input "
            f"SHA-256 `{before_sha256}`; original terminal status `{status}`; "
            "explicit operator-authorized V1 migration."
        )
        appended_lines = [f"{admission_row.utc_field}: {terminal_at}"]
        if not fields.get(detail_field.casefold()):
            appended_lines.append(
                f"{detail_field}: Pre-V1 terminal status `{status}` is preserved "
                "during operator-authorized V1 physical migration."
            )
        if not fields.get(admission_row.evidence_field.casefold()):
            appended_lines.append(f"{admission_row.evidence_field}: {proof}")
        appended_lines.append(f"V1-Migration-Evidence: {proof}")
        appended = ("\n".join(appended_lines) + "\n").encode("utf-8")
        after = before + separator + appended
        planned.append(
            {
                "reference": row["reference"],
                "sourceRelative": row["source"],
                "source": source,
                "targetRelative": target_relative,
                "target": target,
                "category": category,
                "slug": slug,
                "incomingLinks": incoming,
                "status": status,
                "before": before,
                "beforeSha256": before_sha256,
                "after": after,
                "afterSha256": hashlib.sha256(after).hexdigest(),
            }
        )
    planned = sorted(planned, key=lambda item: item["reference"])
    source_set = {item["source"] for item in planned}
    target_set = {item["target"] for item in planned}
    if source_set & target_set:
        raise _terminalization_fail("terminalization source and target sets overlap")
    consumers, receipt_links = _plan_v1_link_relocations(
        root, planned, terminal_at, receipt_path
    )
    return planned, consumers, receipt_links


def terminalize_v1_inventory(
    root: Path,
    inventory_path: Path,
    *,
    terminal_at: str,
    authorization_marker: str,
    receipt_path: Path,
    inject_failure_after: int | None = None,
) -> tuple[int, bool]:
    """Add V1 evidence and preserve exact relocation admission; never move records."""
    if authorization_marker != V1_TERMINALIZATION_AUTHORIZATION:
        raise _terminalization_fail(
            "explicit operator-authorized V1 terminalization marker is required"
        )
    _strict_utc(terminal_at)
    receipt = _terminalization_receipt_path(root, receipt_path)
    try:
        inventory_bytes = inventory_path.read_bytes()
        inventory = _load_migration_inventory(root, inventory_path)
    except LifecycleError as exc:
        raise _terminalization_fail(str(exc)) from exc
    except OSError as exc:
        raise _terminalization_fail(
            f"cannot read terminalization inventory: {inventory_path}"
        ) from exc
    inventory_sha256 = hashlib.sha256(inventory_bytes).hexdigest()
    replay = _terminalization_replay(
        root,
        inventory,
        inventory_sha256,
        terminal_at,
        authorization_marker,
        receipt,
    )
    if replay is not None:
        return replay
    planned, consumers, receipt_links = _preflight_v1_terminalization_rows(
        root, inventory, terminal_at, receipt
    )
    links_by_identity = {
        link["expectedIdentity"]: link for link in receipt_links
    }
    receipt_payload = {
        "schemaVersion": V1_TERMINALIZATION_SCHEMA_VERSION,
        "owner": V1_TERMINALIZATION_OWNER,
        "workItemsRoot": str(_work_items_root(root).resolve()),
        "inventorySha256": inventory_sha256,
        "terminalAt": terminal_at,
        "authorizationMarker": authorization_marker,
        "rowCount": len(planned),
        "linkCount": len(receipt_links),
        "rows": [
            {
                "reference": item["reference"],
                "source": item["sourceRelative"],
                "target": item["targetRelative"],
                "terminalAt": terminal_at,
                "originalStatus": item["status"],
                "beforeSha256": item["beforeSha256"],
                "afterSha256": item["afterSha256"],
                **(
                    {"physicalRelocation": links_by_identity[item["reference"]]}
                    if item["reference"] in links_by_identity
                    else {}
                ),
            }
            for item in planned
        ],
    }
    receipt_bytes = (
        json.dumps(receipt_payload, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    mutated_items: list[dict] = []
    try:
        for index, item in enumerate(planned, start=1):
            if item["source"].read_bytes() != item["before"]:
                raise _terminalization_fail(
                    f"payload changed after preflight: {item['reference']}"
                )
            _atomic_write(item["source"], item["after"])
            mutated_items.append(item)
            if inject_failure_after == index:
                raise _terminalization_fail(
                    f"injected terminalization failure after row {index}"
                )
        _atomic_write(receipt, receipt_bytes)
        for consumer in consumers:
            if consumer["consumer"].read_bytes() != consumer["before"]:
                raise _terminalization_fail(
                    f"terminalization rewrote consumer: {consumer['consumerRelative']}"
                )
        for item in planned:
            if (
                not item["source"].is_file()
                or item["target"].exists()
                or item["source"].read_bytes() != item["after"]
                or _category_locations(root, item["category"], item["slug"])
                != [item["source"]]
            ):
                raise _terminalization_fail(
                    f"terminalization identity check failed: {item['reference']}"
                )
    except Exception as exc:
        rollback_failures: list[str] = []
        for item in reversed(mutated_items):
            try:
                _atomic_write(item["source"], item["before"])
            except Exception as rollback_exc:
                rollback_failures.append(
                    f"{item['reference']}: {rollback_exc}"
                )
        if receipt.exists():
            try:
                receipt.unlink()
            except OSError as rollback_exc:
                rollback_failures.append(f"receipt: {rollback_exc}")
        if rollback_failures:
            raise _terminalization_fail(
                "terminalization rollback failed: " + "; ".join(rollback_failures)
            ) from exc
        if isinstance(exc, LifecycleError):
            raise
        raise _terminalization_fail(
            f"terminalization transaction failed: {exc}"
        ) from exc
    return len(planned), False


def _bound_inventory_path(work_items: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-INVENTORY", "inventory path is missing"
        )
    unresolved_root = _lifecycle_unresolved_absolute(work_items)
    unresolved_path = unresolved_root / Path(relative)
    _lifecycle_reject_unreduced_reparse(
        unresolved_root,
        failure_id="WI-CATEGORY-MIGRATION-INVENTORY",
        message="work-items root or parent contains a link or reparse point",
    )
    _lifecycle_reject_unreduced_reparse(
        unresolved_path,
        failure_id="WI-CATEGORY-MIGRATION-INVENTORY",
        message=f"inventory path contains a link or reparse point: {relative}",
    )
    root = Path(os.path.abspath(unresolved_root))
    path = Path(os.path.abspath(unresolved_path))
    if path != root and root not in path.parents:
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-INVENTORY",
            f"inventory path escapes work-items: {relative}",
        )
    return path


def _terminalization_receipt_for_migration(
    root: Path,
    inventory_path: Path,
    inventory: dict,
) -> tuple[Path, bytes, dict]:
    admissions = [
        row["incomingLinks"]["physicalRelocation"]
        for row in inventory["rows"]
        if isinstance(row, dict)
        and isinstance(row.get("incomingLinks"), dict)
        and isinstance(row["incomingLinks"].get("physicalRelocation"), dict)
    ]
    if len(admissions) != 1:
        raise LifecycleError(
            "WI-LEGACY-LINK-UNMAPPED",
            "migration requires exactly one physical-relocation admission",
        )
    receipt_path = _bound_physical_receipt(root, admissions[0].get("receipt"))
    try:
        receipt_bytes = receipt_path.read_bytes()
        receipt = json.loads(receipt_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-INVENTORY",
            f"physical-relocation receipt is invalid: {receipt_path}",
        ) from exc
    inventory_sha256 = hashlib.sha256(inventory_path.read_bytes()).hexdigest()
    work_items = _work_items_root(root)
    if (
        not isinstance(receipt, dict)
        or receipt.get("schemaVersion") != V1_TERMINALIZATION_SCHEMA_VERSION
        or receipt.get("owner") != V1_TERMINALIZATION_OWNER
        or receipt.get("workItemsRoot") != str(work_items.resolve())
        or receipt.get("inventorySha256") != inventory_sha256
        or receipt.get("authorizationMarker") != V1_TERMINALIZATION_AUTHORIZATION
        or receipt.get("rowCount") != len(inventory["rows"])
        or receipt.get("linkCount") != 1
        or not isinstance(receipt.get("rows"), list)
        or len(receipt["rows"]) != len(inventory["rows"])
        or not isinstance(receipt.get("terminalAt"), str)
    ):
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-INVENTORY",
            "physical-relocation receipt binding differs",
        )
    _strict_utc(receipt["terminalAt"])
    return receipt_path, receipt_bytes, receipt


def _preflight_terminalized_inventory_rows(
    root: Path,
    inventory_path: Path,
    inventory: dict,
) -> tuple[list[dict], list[dict], Path, bytes, dict]:
    work_items = _work_items_root(root)
    receipt_path, receipt_bytes, receipt = _terminalization_receipt_for_migration(
        root, inventory_path, inventory
    )
    replay = _terminalization_replay(
        root,
        inventory,
        hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
        receipt["terminalAt"],
        V1_TERMINALIZATION_AUTHORIZATION,
        receipt_path,
    )
    if replay is None:
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-INVENTORY", "terminalization receipt is missing"
        )
    receipt_rows = {row.get("reference"): row for row in receipt["rows"] if isinstance(row, dict)}
    if len(receipt_rows) != len(inventory["rows"]):
        raise LifecycleError(
            "WI-CATEGORY-MIGRATION-INVENTORY", "terminalization receipt repeats a row"
        )
    plans: list[dict] = []
    consumers: list[dict] = []
    seen_sources: set[Path] = set()
    seen_targets: set[Path] = set()
    for row in inventory["rows"]:
        reference = row.get("reference") if isinstance(row, dict) else None
        receipt_row = receipt_rows.get(reference)
        admission = row.get("admission") if isinstance(row, dict) else None
        if (
            not isinstance(row, dict)
            or not isinstance(receipt_row, dict)
            or not isinstance(admission, dict)
            or admission.get("result") != "denied"
            or admission.get("failureId") != V1_TERMINALIZATION_FAILURE
        ):
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-INVENTORY",
                f"terminalized inventory row is invalid: {reference}",
            )
        category, slug = _canonical_category(reference)
        if row.get("category") != category.name:
            raise LifecycleError(
                "CATEGORY-MIGRATION-ADMISSION-GATE",
                f"category tuple differs for {reference}",
            )
        source = _bound_inventory_path(work_items, row.get("source"))
        target = _bound_inventory_path(work_items, receipt_row.get("target"))
        if source in seen_sources or target in seen_targets:
            raise LifecycleError(
                "WI-CATEGORY-DUAL-LOCATION", "terminalized inventory repeats a source or target"
            )
        seen_sources.add(source)
        seen_targets.add(target)
        source_exists = source.is_file()
        target_exists = target.is_file()
        if source_exists == target_exists:
            raise LifecycleError(
                "WI-CATEGORY-DUAL-LOCATION", f"terminalized location differs for {reference}"
            )
        payload = source if source_exists else target
        payload_sha256 = hashlib.sha256(payload.read_bytes()).hexdigest()
        if (
            receipt_row.get("source") != row.get("source")
            or receipt_row.get("beforeSha256") != row.get("inputSha256")
            or receipt_row.get("afterSha256") != payload_sha256
            or receipt_row.get("terminalAt") != receipt["terminalAt"]
        ):
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-PAYLOAD", f"terminalized payload changed for {reference}"
            )
        instant, expected_target = _validated_migration_payload_target(
            root, category, slug, payload
        )
        if instant != receipt["terminalAt"] or target != expected_target.resolve():
            raise LifecycleError(
                "WI-CATEGORY-ARCHIVE-MONTH-MISMATCH", f"terminalized target differs for {reference}"
            )
        if _category_locations(root, category, slug) != [payload]:
            raise LifecycleError(
                "WI-CATEGORY-DUAL-LOCATION", f"terminalized identity differs for {reference}"
            )
        incoming = row.get("incomingLinks")
        _links, physical = _physical_relocation_admission(
            root, reference, incoming, receipt_path=receipt_path
        )
        plan = {
            "row": row,
            "reference": reference,
            "category": category,
            "slug": slug,
            "source": source,
            "target": target,
            "pending": source_exists,
            "beforeSha256": receipt_row["afterSha256"],
            "receiptRow": receipt_row,
        }
        if physical is None:
            current_links = _incoming_link_result(root, {source, target}, reference)
            _validate_incoming_link_compatibility(
                root,
                reference,
                incoming,
                current_links,
                resolved_location=payload,
            )
        elif source_exists:
            planned_consumers, planned_links = _plan_v1_link_relocations(
                root,
                [
                    {
                        "reference": reference,
                        "sourceRelative": row["source"],
                        "source": source,
                        "targetRelative": receipt_row["target"],
                        "target": target,
                        "incomingLinks": incoming,
                        "beforeSha256": row["inputSha256"],
                        "afterSha256": receipt_row["afterSha256"],
                    }
                ],
                receipt["terminalAt"],
                receipt_path,
            )
            if planned_links != [receipt_row.get("physicalRelocation")]:
                raise LifecycleError(
                    "WI-LEGACY-LINK-UNMAPPED",
                    f"physical-relocation receipt differs for {reference}",
                )
            consumers.extend(planned_consumers)
        plans.append(plan)
    source_set = {plan["source"] for plan in plans}
    target_set = {plan["target"] for plan in plans}
    if source_set & target_set:
        raise LifecycleError("WI-CATEGORY-DUAL-LOCATION", "source and target sets overlap")
    return sorted(plans, key=lambda plan: plan["reference"]), consumers, receipt_path, receipt_bytes, receipt


def _preflight_inventory_rows(
    root: Path,
    inventory: dict,
) -> list[tuple[dict, Path, Path, bool]]:
    work_items = _work_items_root(root)
    planned: list[tuple[dict, Path, Path, bool]] = []
    seen_sources: set[Path] = set()
    seen_targets: set[Path] = set()
    for row in inventory["rows"]:
        if not isinstance(row, dict):
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-INVENTORY", "inventory row is not an object"
            )
        admission = row.get("admission")
        if not isinstance(admission, dict) or admission.get("result") != "admitted":
            raise LifecycleError(
                (admission or {}).get(
                    "failureId", "CATEGORY-MIGRATION-ADMISSION-GATE"
                ),
                (admission or {}).get("reason", "inventory row is not admitted"),
            )
        incoming = row.get("incomingLinks")
        if not isinstance(incoming, dict) or incoming.get("result") not in {
            "clear",
            "logical-only",
        }:
            raise LifecycleError(
                "WI-LEGACY-LINK-UNMAPPED",
                f"incoming links are not mapped for {row.get('reference')}",
            )
        category, slug = _canonical_category(row.get("reference", ""))
        if row.get("category") != category.name:
            raise LifecycleError(
                "CATEGORY-MIGRATION-ADMISSION-GATE",
                f"category tuple differs for {row.get('reference')}",
            )
        source = _bound_inventory_path(work_items, row.get("source"))
        target = _bound_inventory_path(work_items, row.get("target"))
        if source in seen_sources or target in seen_targets:
            raise LifecycleError(
                "WI-CATEGORY-DUAL-LOCATION", "inventory repeats a source or target"
            )
        seen_sources.add(source)
        seen_targets.add(target)
        source_exists = source.exists()
        target_exists = target.exists()
        if source_exists == target_exists:
            raise LifecycleError(
                "WI-CATEGORY-DUAL-LOCATION",
                f"pre-migration location differs for {row.get('reference')}",
            )
        payload = source if source_exists else target
        locations = _category_locations(root, category, slug)
        if locations != [payload]:
            raise LifecycleError(
                "WI-CATEGORY-DUAL-LOCATION",
                f"resolved location differs for {row.get('reference')}",
            )
        algorithm, digest = _payload_digest(payload)
        if (
            row.get("digestAlgorithm") != algorithm
            or row.get("inputSha256") != digest
        ):
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-PAYLOAD",
                f"migration payload changed for {row.get('reference')}",
            )
        instant, expected_target = _validated_migration_payload_target(
            root, category, slug, payload
        )
        if (
            row.get("terminalInstant") != instant
            or target != expected_target.resolve()
        ):
            raise LifecycleError(
                "WI-CATEGORY-ARCHIVE-MONTH-MISMATCH",
                f"planned target differs for {row.get('reference')}",
            )
        current_links = _incoming_link_result(
            root,
            {source, target},
            row["reference"],
        )
        _validate_incoming_link_compatibility(
            root,
            row["reference"],
            incoming,
            current_links,
            resolved_location=payload,
        )
        planned.append((row, source, target, source_exists))
    source_set = {source for _row, source, _target, _pending in planned}
    target_set = {target for _row, _source, target, _pending in planned}
    if source_set & target_set:
        raise LifecycleError(
            "WI-CATEGORY-DUAL-LOCATION", "source and target sets overlap"
        )
    return sorted(planned, key=lambda item: item[0]["reference"])


def apply_migration_inventory(
    root: Path,
    inventory_path: Path,
    *,
    render_readme: bool,
    byte_check: bool,
) -> tuple[int, str | None]:
    inventory = _load_migration_inventory(root, inventory_path)
    has_physical_relocation = any(
        isinstance(row, dict)
        and isinstance(row.get("incomingLinks"), dict)
        and isinstance(row["incomingLinks"].get("physicalRelocation"), dict)
        for row in inventory["rows"]
    )
    if has_physical_relocation:
        plans, consumers, receipt_path, receipt_before, receipt_payload = (
            _preflight_terminalized_inventory_rows(root, inventory_path, inventory)
        )
        work_items = _work_items_root(root)
        readme = work_items / "README.md"
        readme_before = readme.read_bytes() if readme.is_file() else None
        written_consumers: list[dict] = []
        moved: list[dict] = []
        created_directories: set[Path] = set()
        try:
            for consumer in consumers:
                if consumer["consumer"].read_bytes() != consumer["before"]:
                    raise LifecycleError(
                        "WI-LEGACY-LINK-UNMAPPED",
                        f"consumer changed after preflight: {consumer['consumerRelative']}",
                    )
                _atomic_write(consumer["consumer"], consumer["after"])
                written_consumers.append(consumer)
            for plan in plans:
                if not plan["pending"]:
                    continue
                if (
                    not plan["source"].is_file()
                    or plan["target"].exists()
                    or hashlib.sha256(plan["source"].read_bytes()).hexdigest()
                    != plan["beforeSha256"]
                ):
                    raise LifecycleError(
                        "WI-CATEGORY-MIGRATION-PAYLOAD",
                        f"payload changed after preflight: {plan['reference']}",
                    )
                cursor = plan["target"].parent
                while cursor != work_items and not cursor.exists():
                    created_directories.add(cursor)
                    cursor = cursor.parent
                plan["target"].parent.mkdir(parents=True, exist_ok=True)
                os.replace(plan["source"], plan["target"])
                moved.append(plan)
            readme_hash: str | None = None
            if render_readme:
                readme_hash = refresh_readme(root, allow_marker_bootstrap=True)
            if byte_check and (
                not readme.is_file() or readme.read_bytes() != render_readme_bytes(root)
            ):
                raise LifecycleError(
                    "WI-README-STALE", "README differs from an immediate fresh render"
                )
            for plan in plans:
                if (
                    plan["source"].exists()
                    or not plan["target"].is_file()
                    or hashlib.sha256(plan["target"].read_bytes()).hexdigest()
                    != plan["beforeSha256"]
                    or _category_locations(root, plan["category"], plan["slug"])
                    != [plan["target"]]
                ):
                    raise LifecycleError(
                        "WI-CATEGORY-DUAL-LOCATION",
                        f"migration identity check failed: {plan['reference']}",
                    )
            consumers_by_source = {
                consumer["consumerRelative"]: consumer for consumer in consumers
            }
            for row in receipt_payload["rows"]:
                evidence = row.get("physicalRelocation")
                if not isinstance(evidence, dict):
                    continue
                consumer = consumers_by_source.get(evidence.get("source"))
                if consumer is None:
                    if not isinstance(evidence.get("sourceAfterSha256"), str):
                        raise LifecycleError(
                            "WI-LEGACY-LINK-UNMAPPED",
                            "settled physical relocation lacks receipt evidence",
                        )
                    continue
                if (
                    consumer["consumer"].read_bytes() != consumer["after"]
                    or not _markdown_href_resolves(
                        consumer["consumer"].parent,
                        evidence["newHref"],
                        _bound_inventory_path(work_items, evidence["finalTarget"]),
                    )
                ):
                    raise LifecycleError(
                        "WI-LEGACY-LINK-UNMAPPED",
                        "migrated Markdown href does not resolve to final target",
                    )
                evidence["sourceAfterSha256"] = consumer["afterSha256"]
                final_target = _bound_inventory_path(work_items, evidence["finalTarget"])
                evidence["targetAfterSha256"] = hashlib.sha256(
                    final_target.read_bytes()
                ).hexdigest()
            _atomic_write(
                receipt_path,
                (json.dumps(receipt_payload, indent=2, sort_keys=True) + "\n").encode(
                    "utf-8"
                ),
            )
            return len(plans), readme_hash
        except Exception as exc:
            rollback_failures: list[str] = []
            for plan in reversed(moved):
                try:
                    if plan["target"].exists() and not plan["source"].exists():
                        plan["source"].parent.mkdir(parents=True, exist_ok=True)
                        os.replace(plan["target"], plan["source"])
                except Exception as rollback_exc:
                    rollback_failures.append(
                        f"{plan['reference']}: {rollback_exc}"
                    )
            for consumer in reversed(written_consumers):
                try:
                    _atomic_write(consumer["consumer"], consumer["before"])
                except Exception as rollback_exc:
                    rollback_failures.append(
                        f"{consumer['consumerRelative']}: {rollback_exc}"
                    )
            try:
                _restore_readme_snapshot(readme, readme_before)
            except Exception as rollback_exc:
                rollback_failures.append(f"README: {rollback_exc}")
            try:
                _atomic_write(receipt_path, receipt_before)
            except Exception as rollback_exc:
                rollback_failures.append(f"receipt: {rollback_exc}")
            for directory in sorted(
                created_directories, key=lambda path: len(path.parts), reverse=True
            ):
                try:
                    if directory.is_dir() and not any(directory.iterdir()):
                        directory.rmdir()
                except OSError as rollback_exc:
                    rollback_failures.append(f"directory {directory}: {rollback_exc}")
            if rollback_failures:
                raise LifecycleError(
                    "WI-CATEGORY-MIGRATION-INVENTORY",
                    "physical-relocation rollback failed: " + "; ".join(rollback_failures),
                ) from exc
            if isinstance(exc, LifecycleError):
                raise
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-INVENTORY",
                f"physical-relocation transaction failed: {exc}",
            ) from exc
    planned = _preflight_inventory_rows(root, inventory)
    for _row, source, target, pending in planned:
        if not pending:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, target)
    readme_hash: str | None = None
    if render_readme:
        readme_hash = refresh_readme(root, allow_marker_bootstrap=True)
    if byte_check:
        readme = _work_items_root(root) / "README.md"
        if not readme.is_file() or readme.read_bytes() != render_readme_bytes(root):
            raise LifecycleError(
                "WI-README-STALE", "README differs from an immediate fresh render"
            )
    for _row, source, target, _pending in planned:
        if source.exists() or not target.exists():
            raise LifecycleError(
                "WI-CATEGORY-DUAL-LOCATION",
                "source-target disjointness failed after migration",
            )
    return len(planned), readme_hash


def _partial_recovery_fail(failure_id: str, message: str) -> LifecycleError:
    return LifecycleError(failure_id, f"partial-migration-recovery: {message}")


def _partial_recovery_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _partial_recovery_bound_scratch_file(
    root: Path,
    path: Path,
    *,
    label: str,
) -> Path:
    unresolved_root = _lifecycle_unresolved_absolute(root)
    repository_root = (
        unresolved_root.parent
        if unresolved_root.name == "work-items"
        else unresolved_root
    )
    candidate = path if path.is_absolute() else repository_root / path
    _lifecycle_reject_unreduced_reparse(
        unresolved_root,
        failure_id="WI-PARTIAL-MIGRATION-RECOVERY-INVENTORY",
        message=f"{label} root or parent contains a link or reparse point",
    )
    _lifecycle_reject_unreduced_reparse(
        repository_root / "work-items",
        failure_id="WI-PARTIAL-MIGRATION-RECOVERY-INVENTORY",
        message=f"{label} work-items root contains a link or reparse point",
    )
    _lifecycle_reject_unreduced_reparse(
        candidate,
        failure_id="WI-PARTIAL-MIGRATION-RECOVERY-INVENTORY",
        message=f"{label} contains a link or reparse point",
    )
    repository_root = Path(os.path.abspath(repository_root))
    candidate = Path(os.path.abspath(candidate))
    try:
        relative = candidate.relative_to(repository_root)
    except ValueError as exc:
        raise _partial_recovery_fail(
            "WI-PARTIAL-MIGRATION-RECOVERY-INVENTORY",
            f"{label} escapes the repository",
        ) from exc
    if len(relative.parts) < 2 or relative.parts[0] != ".scratch":
        raise _partial_recovery_fail(
            "WI-PARTIAL-MIGRATION-RECOVERY-INVENTORY",
            f"{label} must be a file under repository .scratch",
        )
    return repository_root / relative


def _partial_recovery_expected_paths(
    work_items: Path,
    reference: str,
) -> tuple[str, str, Path, Path]:
    category, slug = _canonical_category(reference)
    if category.name == "work-item":
        source_relative = f"active/{slug}"
        target_relative = f"archive/2026-08/{slug}"
    elif category.name == "bug":
        source_relative = f"bugs/{slug}.md"
        target_relative = f"bugs/archive/2026-08/{slug}.md"
    else:
        raise _partial_recovery_fail(
            "WI-PARTIAL-MIGRATION-RECOVERY-COVERAGE",
            f"unsupported incident reference: {reference}",
        )
    return (
        source_relative,
        target_relative,
        _bound_inventory_path(work_items, source_relative),
        _bound_inventory_path(work_items, target_relative),
    )


def _partial_recovery_validate_target_path(path: Path, failure_id: str) -> None:
    cursor = path
    while True:
        if (cursor.exists() or cursor.is_symlink()) and _lifecycle_path_has_reparse(cursor):
            raise _partial_recovery_fail(failure_id, "target path contains a reparse point")
        if cursor.parent == cursor:
            break
        cursor = cursor.parent


def _partial_recovery_preflight(
    root: Path,
    inventory: dict,
) -> tuple[list[dict], list[dict]]:
    work_items = _work_items_root(root)
    rows = inventory["rows"]
    expected_references = set(PARTIAL_MIGRATION_RECOVERY_TARGETS) | set(
        PARTIAL_MIGRATION_RECOVERY_UNCHANGED_ROWS
    )
    references = [row.get("reference") for row in rows]
    if len(rows) != 4 or len(set(references)) != 4 or set(references) != expected_references:
        raise _partial_recovery_fail(
            "WI-PARTIAL-MIGRATION-RECOVERY-COVERAGE",
            "inventory candidate set is not the exact admitted four-row incident",
        )
    status_plans: list[dict] = []
    unchanged_plans: list[dict] = []
    for row in sorted(rows, key=lambda item: item["reference"]):
        reference = row["reference"]
        source_relative, target_relative, source, target = (
            _partial_recovery_expected_paths(work_items, reference)
        )
        category, _slug = _canonical_category(reference)
        expected_digest = (
            PARTIAL_MIGRATION_RECOVERY_TARGETS[reference].inventory_tree_preimage
            if reference in PARTIAL_MIGRATION_RECOVERY_TARGETS
            else PARTIAL_MIGRATION_RECOVERY_UNCHANGED_ROWS[reference]
        )
        if (
            row.get("category") != category.name
            or row.get("source") != source_relative
            or row.get("target") != target_relative
            or str(row.get("inputSha256", "")).upper() != expected_digest.upper()
            or row.get("admission", {}).get("result") != "admitted"
            or not isinstance(row.get("terminalInstant"), str)
            or archive_month(row["terminalInstant"]) != "2026-08"
            or source.exists()
            or not target.exists()
        ):
            raise _partial_recovery_fail(
                "WI-PARTIAL-MIGRATION-RECOVERY-COVERAGE",
                f"inventory row or source/target relation differs: {reference}",
            )
        _partial_recovery_validate_target_path(
            target,
            "WI-PARTIAL-MIGRATION-RECOVERY-PREIMAGE",
        )
        algorithm, current_digest = _payload_digest(target)
        if algorithm != row.get("digestAlgorithm"):
            raise _partial_recovery_fail(
                "WI-PARTIAL-MIGRATION-RECOVERY-PREIMAGE",
                f"target digest algorithm differs: {reference}",
            )
        if reference not in PARTIAL_MIGRATION_RECOVERY_TARGETS:
            if current_digest.upper() != expected_digest.upper():
                raise _partial_recovery_fail(
                    "WI-PARTIAL-MIGRATION-RECOVERY-PREIMAGE",
                    f"unchanged target bytes differ: {reference}",
                )
            _validate_flat_terminal(category, target.read_bytes())
            unchanged_plans.append(
                {
                    "reference": reference,
                    "row": row,
                    "source": source,
                    "target": target,
                    "digest": current_digest.upper(),
                }
            )
            continue
        contract = PARTIAL_MIGRATION_RECOVERY_TARGETS[reference]
        status_path = target / "status.md"
        closure_path = target / "closure.md"
        if not status_path.is_file() or not closure_path.is_file():
            raise _partial_recovery_fail(
                "WI-PARTIAL-MIGRATION-RECOVERY-CLOSURE",
                f"status or closure is missing: {reference}",
            )
        _partial_recovery_validate_target_path(
            status_path,
            "WI-PARTIAL-MIGRATION-RECOVERY-PREIMAGE",
        )
        _partial_recovery_validate_target_path(
            closure_path,
            "WI-PARTIAL-MIGRATION-RECOVERY-CLOSURE",
        )
        status_snapshot = _capture_file_snapshot(
            status_path,
            failure_id="WI-PARTIAL-MIGRATION-RECOVERY-PREIMAGE",
        )
        closure_snapshot = _capture_file_snapshot(
            closure_path,
            failure_id="WI-PARTIAL-MIGRATION-RECOVERY-CLOSURE",
        )
        status_before = status_snapshot.data
        closure_before = closure_snapshot.data
        if _partial_recovery_sha256(closure_before) != contract.closure_sha256.upper():
            raise _partial_recovery_fail(
                "WI-PARTIAL-MIGRATION-RECOVERY-CLOSURE",
                f"closure hash differs: {reference}",
            )
        occurrences = _schema_marker_occurrences(closure_before, "closure.md")
        if len(occurrences) != 1 or occurrences[0] != (
            WORK_ITEM_SCHEMA_MARKER,
            WORK_ITEM_SCHEMA_KEY,
            WORK_ITEM_SCHEMA_VALUE,
        ):
            raise _partial_recovery_fail(
                "WI-PARTIAL-MIGRATION-RECOVERY-CLOSURE",
                f"closure lifecycle marker differs: {reference}",
            )
        _validate_closure(closure_before, row["terminalInstant"])
        status_digest = _partial_recovery_sha256(status_before)
        if status_digest == contract.status_preimage.upper():
            if current_digest.upper() != contract.inventory_tree_preimage.upper():
                raise _partial_recovery_fail(
                    "WI-PARTIAL-MIGRATION-RECOVERY-PREIMAGE",
                    f"target tree preimage differs: {reference}",
                )
            status_after = _terminalize_status(status_before)
            if _partial_recovery_sha256(status_after) != contract.status_afterimage.upper():
                raise _partial_recovery_fail(
                    "WI-PARTIAL-MIGRATION-RECOVERY-PREIMAGE",
                    f"canonical status projection differs: {reference}",
                )
            pending = True
        elif status_digest == contract.status_afterimage.upper():
            if current_digest.upper() != contract.projected_tree_afterimage.upper():
                raise _partial_recovery_fail(
                    "WI-PARTIAL-MIGRATION-RECOVERY-PREIMAGE",
                    f"target tree afterimage differs: {reference}",
                )
            _require_canonical_schema_marker(
                _schema_marker_occurrences(status_before, "status.md"),
                "status.md",
            )
            status_after = status_before
            pending = False
        else:
            raise _partial_recovery_fail(
                "WI-PARTIAL-MIGRATION-RECOVERY-PREIMAGE",
                f"status is neither admitted preimage nor deterministic afterimage: {reference}",
            )
        status_plans.append(
            {
                "reference": reference,
                "row": row,
                "source": source,
                "target": target,
                "status": status_path,
                "closure": closure_path,
                "status_before": status_before,
                "status_after": status_after,
                "closure_before": closure_before,
                "status_snapshot": status_snapshot,
                "closure_snapshot": closure_snapshot,
                "pending": pending,
                "contract": contract,
            }
        )
    return status_plans, unchanged_plans


def _partial_recovery_receipt_bytes(
    inventory_sha256: str,
    readme_before_sha256: str,
    readme_after_sha256: str,
    status_plans: list[dict],
    unchanged_plans: list[dict],
) -> bytes:
    rows = []
    for plan in sorted(status_plans, key=lambda item: item["reference"]):
        contract = plan["contract"]
        rows.append(
            {
                "action": "terminalize-status",
                "closureSha256": contract.closure_sha256.upper(),
                "finalTreeSha256": contract.projected_tree_afterimage.upper(),
                "inputTreeSha256": contract.inventory_tree_preimage.upper(),
                "reference": plan["reference"],
                "source": plan["row"]["source"],
                "statusAfterSha256": contract.status_afterimage.upper(),
                "statusBeforeSha256": contract.status_preimage.upper(),
                "target": plan["row"]["target"],
            }
        )
    for plan in sorted(unchanged_plans, key=lambda item: item["reference"]):
        rows.append(
            {
                "action": "none",
                "finalTreeSha256": plan["digest"].upper(),
                "inputTreeSha256": plan["digest"].upper(),
                "reference": plan["reference"],
                "source": plan["row"]["source"],
                "target": plan["row"]["target"],
            }
        )
    payload = {
        "audit": "PASS",
        "inventoryRowCount": 4,
        "inventorySha256": inventory_sha256.upper(),
        "operationId": "recover-partial-migration-v1:909A56",
        "owner": "work-items-lifecycle-v1-partial-migration-recovery",
        "readmeAfterSha256": readme_after_sha256.upper(),
        "readmeBeforeSha256": readme_before_sha256.upper(),
        "rows": sorted(rows, key=lambda row: row["reference"]),
        "schemaVersion": 1,
    }
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _partial_recovery_fsync_directory(path: Path) -> None:
    _lifecycle_reject_unreduced_reparse(
        path,
        failure_id="WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CREATE-UNSUPPORTED",
        message="recovery receipt parent contains a link or reparse point",
    )
    descriptor = None
    native_handle = None
    try:
        if os.name == "nt":
            import ctypes
            import ctypes.wintypes
            import msvcrt

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            create_file = kernel32.CreateFileW
            create_file.argtypes = [
                ctypes.wintypes.LPCWSTR,
                ctypes.wintypes.DWORD,
                ctypes.wintypes.DWORD,
                ctypes.wintypes.LPVOID,
                ctypes.wintypes.DWORD,
                ctypes.wintypes.DWORD,
                ctypes.wintypes.HANDLE,
            ]
            create_file.restype = ctypes.wintypes.HANDLE
            native_handle = create_file(
                str(path),
                0x40000000,  # GENERIC_WRITE
                0x00000001 | 0x00000002 | 0x00000004,
                None,
                3,  # OPEN_EXISTING
                0x02000000 | 0x00200000,
                None,
            )
            if native_handle == ctypes.wintypes.HANDLE(-1).value:
                native_handle = None
                raise OSError(ctypes.get_last_error(), "cannot open receipt directory")
            descriptor = msvcrt.open_osfhandle(native_handle, os.O_RDWR)
            native_handle = None
        else:
            flags = os.O_RDONLY
            flags |= getattr(os, "O_DIRECTORY", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(path, flags)
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise OSError(errno.ENOTDIR, "receipt parent is not a directory")
        os.fsync(descriptor)
    except OSError as exc:
        raise _partial_recovery_fail(
            "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CREATE-UNSUPPORTED",
            "filesystem cannot durably settle the recovery receipt directory",
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        elif native_handle is not None:
            import ctypes

            ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(native_handle)


def _partial_recovery_exact_receipt_snapshot(
    path: Path,
    data: bytes,
) -> CapturedFileSnapshot | None:
    failure_id = "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT"
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise _partial_recovery_fail(
            failure_id,
            "final recovery receipt identity is ambiguous",
        ) from exc
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or bool(
            getattr(info, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        )
    ):
        raise _partial_recovery_fail(
            failure_id,
            "final recovery receipt is a link, reparse point, or non-regular file",
        )
    try:
        snapshot = _capture_file_snapshot(path, failure_id=failure_id)
    except LifecycleError as exc:
        raise _partial_recovery_fail(
            failure_id,
            "final recovery receipt identity cannot be proven",
        ) from exc
    if snapshot.data != data:
        raise _partial_recovery_fail(failure_id, "final recovery receipt differs")
    return snapshot


def _partial_recovery_settle_receipt(path: Path, data: bytes) -> bool:
    if _partial_recovery_exact_receipt_snapshot(path, data) is not None:
        return False
    pending = path.with_name(f".{path.name}.pending-v1")
    pending_created = False
    linked_here = False
    linked_identity = None
    if pending.exists():
        pending_snapshot = _capture_file_snapshot(
            pending,
            failure_id="WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT",
        )
        if pending_snapshot.data == data:
            pass
        elif (
            pending_snapshot.length < len(data)
            and data.startswith(pending_snapshot.data)
        ):
            _verify_captured_file(
                pending_snapshot,
                "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT",
            )
            pending.unlink()
            _atomic_write(pending, data)
            pending_created = True
        else:
            raise _partial_recovery_fail(
                "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT",
                "pending recovery receipt differs",
            )
    else:
        _atomic_write(pending, data)
        pending_created = True
    pending_snapshot = _capture_file_snapshot(
        pending,
        failure_id="WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT",
    )
    if pending_snapshot.data != data:
        raise _partial_recovery_fail(
            "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT",
            "prepared pending recovery receipt differs",
        )
    final_snapshot = None
    try:
        try:
            os.link(pending, path)
            linked_here = True
            final_snapshot = _partial_recovery_exact_receipt_snapshot(path, data)
            if final_snapshot is None or final_snapshot.identity != pending_snapshot.identity:
                raise _partial_recovery_fail(
                    "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT",
                    "created final recovery receipt identity differs from pending",
                )
            linked_identity = final_snapshot.identity
        except FileExistsError:
            final_snapshot = _partial_recovery_exact_receipt_snapshot(path, data)
            if final_snapshot is None:
                raise _partial_recovery_fail(
                    "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT",
                    "concurrent final recovery receipt disappeared",
                )
        except OSError as exc:
            raise _partial_recovery_fail(
                "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CREATE-UNSUPPORTED",
                "filesystem cannot atomically create the final receipt",
            ) from exc
        _partial_recovery_fsync_directory(path.parent)
        verified_final = _partial_recovery_exact_receipt_snapshot(path, data)
        if (
            final_snapshot is None
            or verified_final is None
            or verified_final.identity != final_snapshot.identity
        ):
            raise _partial_recovery_fail(
                "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT",
                "final recovery receipt reread identity differs",
            )
        try:
            pending.unlink()
        except FileNotFoundError:
            pass
        return True
    except BaseException as exc:
        composer = _CURRENT_LIFECYCLE_OUTCOME_COMPOSER.get()
        if composer is not None:
            composer.capture_primary(exc)
        if linked_here:
            try:
                current = path.lstat()
                if (
                    linked_identity is None
                    or _lifecycle_file_identity(current) != linked_identity
                    or stat.S_ISLNK(current.st_mode)
                    or bool(
                        getattr(current, "st_file_attributes", 0)
                        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
                    )
                    or _capture_file_snapshot(
                        path,
                        failure_id=(
                            "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT"
                        ),
                    ).data
                    != data
                ):
                    raise OSError("final recovery receipt identity changed")
            except (OSError, LifecycleError) as cleanup_exc:
                if composer is not None:
                    composer.record_cleanup(
                        phase="receipt-final",
                        failure_id=(
                            "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT"
                        ),
                        resource=f".scratch/{path.name}",
                        diagnostic="final receipt ownership changed during cleanup",
                        cause=cleanup_exc,
                    )
        if pending_created:
            try:
                current_pending = pending.lstat()
                if (
                    _lifecycle_file_identity(current_pending)
                    != pending_snapshot.identity
                    or stat.S_ISLNK(current_pending.st_mode)
                    or bool(
                        getattr(current_pending, "st_file_attributes", 0)
                        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
                    )
                    or pending.read_bytes() != data
                ):
                    raise OSError("pending recovery receipt identity changed")
                pending.unlink()
            except FileNotFoundError:
                pass
            except OSError as cleanup_exc:
                if composer is not None:
                    composer.record_cleanup(
                        phase="receipt-pending",
                        failure_id=(
                            "WI-PARTIAL-MIGRATION-RECOVERY-CLEANUP-FAILED"
                        ),
                        resource=f".scratch/{pending.name}",
                        diagnostic="pending receipt cleanup failed",
                        cause=cleanup_exc,
                    )
        raise


def _partial_recovery_verify_owned_parent_chains(
    status_plans: list[dict],
    readme_snapshot: CapturedFileSnapshot,
) -> None:
    failure_id = "WI-PARTIAL-MIGRATION-RECOVERY-CONCURRENT-DRIFT"
    for plan in status_plans:
        _verify_captured_parent_chain(plan["status_snapshot"].parent_chain, failure_id)
        _verify_captured_parent_chain(plan["closure_snapshot"].parent_chain, failure_id)
    _verify_captured_parent_chain(readme_snapshot.parent_chain, failure_id)


def recover_partial_migration_v1(
    root: Path,
    inventory_path: Path,
    *,
    expected_inventory_sha256: str,
    expected_readme_sha256: str,
    target_status_preimages: dict[str, str],
    receipt_path: Path,
    apply_admitted: bool,
    render_readme: bool,
    byte_check: bool,
    inject_failure_at: str | None = None,
) -> PartialRecoveryResult:
    transaction = _CURRENT_LIFECYCLE_TRANSACTION.get()
    if transaction is None:
        raise _partial_recovery_fail(
            "WI-LIFECYCLE-LOCK-IDENTITY",
            "recovery core requires the common lifecycle transaction",
        )
    if not (apply_admitted and render_readme and byte_check):
        raise _partial_recovery_fail(
            "WI-PARTIAL-MIGRATION-RECOVERY-COVERAGE",
            "recovery requires --apply-admitted, --render-readme, and --byte-check",
        )
    expected_statuses = {
        reference: contract.status_preimage.upper()
        for reference, contract in PARTIAL_MIGRATION_RECOVERY_TARGETS.items()
    }
    supplied_statuses = {
        str(reference): str(digest).upper()
        for reference, digest in target_status_preimages.items()
    }
    if (
        expected_inventory_sha256.upper()
        != PARTIAL_MIGRATION_RECOVERY_INVENTORY_SHA256.upper()
        or expected_readme_sha256.upper()
        != PARTIAL_MIGRATION_RECOVERY_README_PREIMAGE_SHA256.upper()
        or supplied_statuses != expected_statuses
    ):
        raise _partial_recovery_fail(
            "WI-PARTIAL-MIGRATION-RECOVERY-COVERAGE",
            "CLI bindings differ from the exact admitted incident",
        )
    inventory_path = _partial_recovery_bound_scratch_file(
        root,
        inventory_path,
        label="inventory",
    )
    receipt_path = _partial_recovery_bound_scratch_file(
        root,
        receipt_path,
        label="receipt",
    )
    transaction.verify()
    captured_inventory = _capture_file_snapshot(
        inventory_path,
        failure_id="WI-PARTIAL-MIGRATION-RECOVERY-INVENTORY",
    )
    inventory_sha256 = _partial_recovery_sha256(captured_inventory.data)
    if inventory_sha256 != PARTIAL_MIGRATION_RECOVERY_INVENTORY_SHA256.upper():
        raise _partial_recovery_fail(
            "WI-PARTIAL-MIGRATION-RECOVERY-INVENTORY",
            "captured inventory SHA-256 differs",
        )
    inventory = _parse_migration_inventory_bytes(
        root,
        captured_inventory.data,
        strict_shape=True,
    )
    status_plans, unchanged_plans = _partial_recovery_preflight(root, inventory)
    readme = _work_items_root(root) / "README.md"
    if not readme.is_file() or _lifecycle_path_has_reparse(readme):
        raise _partial_recovery_fail(
            "WI-PARTIAL-MIGRATION-RECOVERY-README-PREIMAGE",
            "README is missing or noncanonical",
        )
    readme_snapshot = _capture_file_snapshot(
        readme,
        failure_id="WI-PARTIAL-MIGRATION-RECOVERY-README-PREIMAGE",
    )
    readme_before = readme_snapshot.data
    readme_before_sha256 = _partial_recovery_sha256(readme_before)
    any_pending = any(plan["pending"] for plan in status_plans)
    if any_pending and readme_before_sha256 != expected_readme_sha256.upper():
        raise _partial_recovery_fail(
            "WI-PARTIAL-MIGRATION-RECOVERY-README-PREIMAGE",
            "README does not equal the explicit preimage",
        )
    if any_pending:
        try:
            receipt_path.lstat()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise _partial_recovery_fail(
                "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT",
                "final receipt identity is ambiguous while status rows remain pending",
            ) from exc
        else:
            raise _partial_recovery_fail(
                "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT",
                "a final receipt exists while status rows remain pending",
            )

    written_statuses: list[dict] = []
    readme_written = False
    final_receipt_created = False
    receipt_bytes: bytes | None = None
    try:
        _partial_recovery_verify_owned_parent_chains(status_plans, readme_snapshot)
        for index, plan in enumerate(status_plans, start=1):
            if not plan["pending"]:
                continue
            transaction.verify()
            _verify_captured_file(
                captured_inventory,
                "WI-PARTIAL-MIGRATION-RECOVERY-INVENTORY",
            )
            _verify_captured_file(
                plan["status_snapshot"],
                "WI-PARTIAL-MIGRATION-RECOVERY-PREIMAGE",
            )
            _verify_captured_file(
                plan["closure_snapshot"],
                "WI-PARTIAL-MIGRATION-RECOVERY-CLOSURE",
            )
            current_status = plan["status"].read_bytes()
            current_closure = plan["closure"].read_bytes()
            _algorithm, current_tree = _payload_digest(plan["target"])
            if (
                current_status != plan["status_before"]
                or current_closure != plan["closure_before"]
                or current_tree.upper()
                != plan["contract"].inventory_tree_preimage.upper()
            ):
                raise _partial_recovery_fail(
                    "WI-PARTIAL-MIGRATION-RECOVERY-CONCURRENT-DRIFT",
                    f"target changed after preflight: {plan['reference']}",
                )
            _verify_captured_parent_chain(
                plan["status_snapshot"].parent_chain,
                "WI-PARTIAL-MIGRATION-RECOVERY-CONCURRENT-DRIFT",
            )
            _verify_captured_parent_chain(
                plan["closure_snapshot"].parent_chain,
                "WI-PARTIAL-MIGRATION-RECOVERY-CONCURRENT-DRIFT",
            )
            _atomic_write(plan["status"], plan["status_after"])
            written_statuses.append(plan)
            _verify_captured_file(
                plan["closure_snapshot"],
                "WI-PARTIAL-MIGRATION-RECOVERY-CLOSURE",
            )
            _algorithm, after_tree = _payload_digest(plan["target"])
            if (
                plan["status"].read_bytes() != plan["status_after"]
                or plan["closure"].read_bytes() != plan["closure_before"]
                or after_tree.upper()
                != plan["contract"].projected_tree_afterimage.upper()
            ):
                raise _partial_recovery_fail(
                    "WI-PARTIAL-MIGRATION-RECOVERY-CONCURRENT-DRIFT",
                    f"target afterimage differs: {plan['reference']}",
                )
            if inject_failure_at == f"after-status-{index}":
                raise _partial_recovery_fail(
                    "WI-PARTIAL-MIGRATION-RECOVERY-TEST-FAILPOINT",
                    inject_failure_at,
                )

        transaction.verify()
        _verify_captured_file(
            captured_inventory,
            "WI-PARTIAL-MIGRATION-RECOVERY-INVENTORY",
        )
        _verify_captured_file(
            readme_snapshot,
            "WI-PARTIAL-MIGRATION-RECOVERY-README-PREIMAGE",
        )
        final_readme = render_readme_bytes(root)
        final_readme_sha256 = _partial_recovery_sha256(final_readme)
        current_readme = readme.read_bytes()
        if current_readme != final_readme and current_readme == readme_before:
            _partial_recovery_verify_owned_parent_chains(status_plans, readme_snapshot)
            _atomic_write(readme, final_readme)
            readme_written = True
        elif current_readme != final_readme:
            raise _partial_recovery_fail(
                "WI-PARTIAL-MIGRATION-RECOVERY-CONCURRENT-DRIFT",
                "README changed after preflight",
            )
        if readme.read_bytes() != render_readme_bytes(root):
            raise _partial_recovery_fail(
                "WI-PARTIAL-MIGRATION-RECOVERY-CONCURRENT-DRIFT",
                "README differs from a fresh render",
            )
        if inject_failure_at == "after-readme":
            raise _partial_recovery_fail(
                "WI-PARTIAL-MIGRATION-RECOVERY-TEST-FAILPOINT",
                inject_failure_at,
            )
        _partial_recovery_verify_owned_parent_chains(status_plans, readme_snapshot)
        for plan in status_plans:
            _verify_captured_file(
                plan["closure_snapshot"],
                "WI-PARTIAL-MIGRATION-RECOVERY-CLOSURE",
            )
            _algorithm, digest = _payload_digest(plan["target"])
            if (
                _partial_recovery_sha256(plan["status"].read_bytes())
                != plan["contract"].status_afterimage.upper()
                or _partial_recovery_sha256(plan["closure"].read_bytes())
                != plan["contract"].closure_sha256.upper()
                or digest.upper()
                != plan["contract"].projected_tree_afterimage.upper()
            ):
                raise _partial_recovery_fail(
                    "WI-PARTIAL-MIGRATION-RECOVERY-CONCURRENT-DRIFT",
                    f"final target verification differs: {plan['reference']}",
                )
        for plan in unchanged_plans:
            _algorithm, digest = _payload_digest(plan["target"])
            if digest.upper() != plan["digest"].upper():
                raise _partial_recovery_fail(
                    "WI-PARTIAL-MIGRATION-RECOVERY-CONCURRENT-DRIFT",
                    f"unchanged target drifted: {plan['reference']}",
                )
        audit(root)
        receipt_bytes = _partial_recovery_receipt_bytes(
            inventory_sha256,
            expected_readme_sha256,
            final_readme_sha256,
            status_plans,
            unchanged_plans,
        )
        _partial_recovery_exact_receipt_snapshot(receipt_path, receipt_bytes)
        transaction.verify()
        final_receipt_created = _partial_recovery_settle_receipt(
            receipt_path,
            receipt_bytes,
        )
        transaction.verify()
        committed_receipt = _partial_recovery_exact_receipt_snapshot(
            receipt_path,
            receipt_bytes,
        )
        if committed_receipt is None:
            raise _partial_recovery_fail(
                "WI-PARTIAL-MIGRATION-RECOVERY-RECEIPT-CONFLICT",
                "committed receipt is absent",
            )
        _partial_recovery_verify_owned_parent_chains(status_plans, readme_snapshot)
        return PartialRecoveryCommittedCandidate(
            PartialRecoveryResult(
                receipt_sha256=_partial_recovery_sha256(receipt_bytes),
                audit="PASS",
                replay=not any_pending and not final_receipt_created,
            )
        )
    except BaseException as exc:
        composer = _CURRENT_LIFECYCLE_OUTCOME_COMPOSER.get()
        if composer is not None:
            composer.capture_primary(exc)
        exact_final_receipt = False
        if receipt_bytes is not None:
            try:
                exact_final_receipt = (
                    _partial_recovery_exact_receipt_snapshot(
                        receipt_path,
                        receipt_bytes,
                    )
                    is not None
                )
            except LifecycleError:
                exact_final_receipt = False
        if final_receipt_created or exact_final_receipt:
            raise
        rollback_failed = False
        rollback_parents_valid = True
        if written_statuses or readme_written:
            try:
                _partial_recovery_verify_owned_parent_chains(
                    status_plans,
                    readme_snapshot,
                )
            except BaseException as rollback_exc:
                rollback_parents_valid = False
                rollback_failed = True
                if composer is not None:
                    composer.record_cleanup(
                        phase="rollback-parent-chain",
                        failure_id="WI-PARTIAL-MIGRATION-RECOVERY-ROLLBACK-FAILED",
                        resource="work-items",
                        diagnostic="rollback parent-chain verification failed",
                        cause=rollback_exc,
                    )
        if readme_written and rollback_parents_valid:
            try:
                _verify_captured_parent_chain(
                    readme_snapshot.parent_chain,
                    "WI-PARTIAL-MIGRATION-RECOVERY-ROLLBACK-FAILED",
                )
                if readme.read_bytes() == final_readme:
                    _verify_captured_parent_chain(
                        readme_snapshot.parent_chain,
                        "WI-PARTIAL-MIGRATION-RECOVERY-ROLLBACK-FAILED",
                    )
                    _atomic_write(readme, readme_before)
                else:
                    raise OSError("README afterimage changed")
            except BaseException as rollback_exc:
                rollback_failed = True
                if composer is not None:
                    composer.record_cleanup(
                        phase="rollback-readme",
                        failure_id="WI-PARTIAL-MIGRATION-RECOVERY-ROLLBACK-FAILED",
                        resource="work-items/README.md",
                        diagnostic="README rollback failed",
                        cause=rollback_exc,
                    )
        for plan in reversed(written_statuses) if rollback_parents_valid else ():
            try:
                _verify_captured_parent_chain(
                    plan["status_snapshot"].parent_chain,
                    "WI-PARTIAL-MIGRATION-RECOVERY-ROLLBACK-FAILED",
                )
                _verify_captured_parent_chain(
                    plan["closure_snapshot"].parent_chain,
                    "WI-PARTIAL-MIGRATION-RECOVERY-ROLLBACK-FAILED",
                )
                if plan["status"].read_bytes() == plan["status_after"]:
                    _verify_captured_parent_chain(
                        plan["status_snapshot"].parent_chain,
                        "WI-PARTIAL-MIGRATION-RECOVERY-ROLLBACK-FAILED",
                    )
                    _atomic_write(plan["status"], plan["status_before"])
                else:
                    raise OSError("status afterimage changed")
            except BaseException as rollback_exc:
                rollback_failed = True
                if composer is not None:
                    composer.record_cleanup(
                        phase=f"rollback-status:{plan['reference']}",
                        failure_id="WI-PARTIAL-MIGRATION-RECOVERY-ROLLBACK-FAILED",
                        resource=str(plan["row"]["target"]) + "/status.md",
                        diagnostic=f"status rollback failed for {plan['reference']}",
                        cause=rollback_exc,
                    )
        if rollback_parents_valid and (written_statuses or readme_written):
            try:
                _partial_recovery_verify_owned_parent_chains(
                    status_plans,
                    readme_snapshot,
                )
            except BaseException as rollback_exc:
                rollback_failed = True
                if composer is not None:
                    composer.record_cleanup(
                        phase="rollback-postcheck",
                        failure_id="WI-PARTIAL-MIGRATION-RECOVERY-ROLLBACK-FAILED",
                        resource="work-items",
                        diagnostic="rollback postcheck failed",
                        cause=rollback_exc,
                    )
        if composer is not None and (written_statuses or readme_written):
            composer.set_rollback("incomplete" if rollback_failed else "completed")
        raise


def verify_migration_inventory(root: Path, inventory_path: Path) -> int:
    inventory = _load_migration_inventory(root, inventory_path)
    work_items = _work_items_root(root)
    if any(
        isinstance(row, dict)
        and isinstance(row.get("incomingLinks"), dict)
        and isinstance(row["incomingLinks"].get("physicalRelocation"), dict)
        for row in inventory["rows"]
    ):
        plans, _consumers, _receipt_path, _receipt_bytes, _receipt = (
            _preflight_terminalized_inventory_rows(root, inventory_path, inventory)
        )
        for plan in plans:
            if (
                plan["pending"]
                or not plan["target"].is_file()
                or plan["source"].exists()
                or hashlib.sha256(plan["target"].read_bytes()).hexdigest()
                != plan["beforeSha256"]
                or _category_locations(root, plan["category"], plan["slug"])
                != [plan["target"]]
            ):
                raise LifecycleError(
                    "WI-CATEGORY-DUAL-LOCATION",
                    f"settled physical relocation differs for {plan['reference']}",
                )
        check_readme(root)
        return len(plans)
    for row in inventory["rows"]:
        source = _bound_inventory_path(work_items, row.get("source"))
        target = _bound_inventory_path(work_items, row.get("target"))
        if source.exists() or not target.exists():
            raise LifecycleError(
                "WI-CATEGORY-DUAL-LOCATION",
                f"source/target state differs for {row.get('reference')}",
            )
        algorithm, digest = _payload_digest(target)
        if (
            algorithm != row.get("digestAlgorithm")
            or digest != row.get("inputSha256")
        ):
            raise LifecycleError(
                "WI-CATEGORY-MIGRATION-PAYLOAD",
                f"target payload hash differs for {row.get('reference')}",
            )
        category, _slug = _canonical_category(row.get("reference", ""))
        if row.get("category") != category.name:
            raise LifecycleError(
                "CATEGORY-MIGRATION-ADMISSION-GATE",
                f"category tuple differs for {row.get('reference')}",
            )
        instant = row.get("terminalInstant")
        if target.parent.name != archive_month(instant):
            raise LifecycleError(
                "WI-CATEGORY-ARCHIVE-MONTH-MISMATCH",
                f"target month differs for {row.get('reference')}",
            )
        if resolve_category(root, row["reference"]) != target:
            raise LifecycleError(
                "WI-LEGACY-LINK-UNMAPPED",
                f"logical reference does not resolve to target: {row['reference']}",
            )
        current_links = _incoming_link_result(
            root,
            {source, target},
            row["reference"],
        )
        _validate_incoming_link_compatibility(
            root,
            row["reference"],
            row.get("incomingLinks"),
            current_links,
            resolved_location=target,
        )
    check_readme(root)
    return len(inventory["rows"])


def reopen_category_record(
    root: Path,
    archived_reference: str,
    successor_slug: str,
    current_data: bytes,
) -> Path:
    category, archived_slug = _canonical_category(archived_reference)
    _admission_for(category.name)
    if category.name == "work-item":
        return reopen_item(root, archived_slug, successor_slug, current_data)
    archived = resolve_category(root, archived_reference)
    if "archive" not in archived.parts:
        raise LifecycleError("WI-INVALID-TARGET", "reopen source must be archived")
    _validate_flat_terminal(category, archived.read_bytes())
    _validate_slug(successor_slug)
    if _category_locations(root, category, successor_slug):
        raise LifecycleError("WI-CATEGORY-DUAL-LOCATION", "successor slug already exists")
    try:
        text = current_data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LifecycleError("WI-CATEGORY-STATUS-INVALID", "successor must be UTF-8") from exc
    fields = _parse_fields(text)
    if fields.get("status") not in category.current_statuses:
        raise LifecycleError(
            "WI-CATEGORY-STATUS-INVALID",
            f"{category.name} successor status must be current",
        )
    if fields.get("reopens") != archived_slug:
        raise LifecycleError(
            "WI-CATEGORY-STATUS-INVALID",
            f"successor must declare Reopens: {archived_slug}",
        )
    _preflight_readme(root)
    target = _work_items_root(root) / category.current_root / f"{successor_slug}.md"
    _atomic_write(target, current_data)
    try:
        refresh_readme(root)
    except LifecycleError as exc:
        raise LifecycleError("WI-README-STALE", str(exc)) from exc
    return target


def _fixture_status(item: dict) -> str:
    return (
        "---\n"
        "template: staged\n"
        f"status: {item['status']}\n"
        "started: 2026-07-31T00:00:00Z\n"
        f"updated: {item['updated']}\n"
        "---\n\n"
        f"Task: {item['task']}\n"
        f"Current step: {item.get('currentStep', 'Continue.')}\n"
        "Last result: Fixture materialized.\n"
        f"Next action: {item.get('nextAction', 'Continue.')}\n"
        "Scope boundary: Trial fixture only.\n"
        "Owner: toolchain-engineer\n"
        "Integration owner: toolchain-engineer\n"
        "Evidence gate: five-item trial\n"
        + (f"Blocker: {item['blocker']}\n" if item.get("blocker") else "")
        + (f"Roadmap: {item['roadmap']}\n" if item.get("roadmap") else "")
        + (f"Epic: {item['epic']}\n" if item.get("epic") else "")
    )


def _trial_expected_files(fixture: dict) -> set[str]:
    expected = {
        "work-items/README.md",
    }
    supporting_epics = fixture.get("supportingEpics", [])
    if not isinstance(supporting_epics, list):
        raise LifecycleError("WI-TRIAL-FIXTURE", "supportingEpics must be a list")
    for epic in supporting_epics:
        if not isinstance(epic, dict) or not isinstance(epic.get("slug"), str):
            raise LifecycleError("WI-TRIAL-FIXTURE", "supporting epic requires a slug")
        _validate_slug(epic["slug"])
        expected.add(f"work-items/epics/{epic['slug']}.md")

    items = fixture.get("items")
    if not isinstance(items, list) or len(items) != 5:
        raise LifecycleError("WI-TRIAL-FIXTURE", "fixture must contain exactly five items")
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("slug"), str):
            raise LifecycleError("WI-TRIAL-FIXTURE", "trial item requires a slug")
        slug = item["slug"]
        _validate_slug(slug)
        kind = item.get("kind")
        if kind in {"active", "blocked"}:
            expected.add(f"work-items/active/{slug}/status.md")
        elif kind == "backlog":
            expected.add(f"work-items/backlog/{slug}.md")
        elif kind == "roadmap":
            expected.add(f"work-items/roadmaps/{slug}.md")
        elif kind == "archived":
            closed = item.get("closed")
            if not isinstance(closed, str):
                raise LifecycleError("WI-TRIAL-FIXTURE", "archived item requires Closed")
            expected.add(
                f"work-items/archive/{archive_month(closed)}/{slug}/closure.md"
            )
        else:
            raise LifecycleError("WI-TRIAL-FIXTURE", f"unknown trial kind: {kind}")
    return expected


def _trial_expected_directories(files: set[str]) -> set[str]:
    directories: set[str] = set()
    for value in files:
        parent = Path(value).parent
        while parent != Path("."):
            directories.add(parent.as_posix())
            parent = parent.parent
    return directories


def _trial_tree(root: Path) -> tuple[dict[str, str], set[str]]:
    files: dict[str, str] = {}
    directories: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if relative in {".scratch", LIFECYCLE_LOCK_RELATIVE.as_posix()}:
            continue
        if path.is_symlink():
            raise LifecycleError(
                "WI-TRIAL-NOT-OWNED",
                f"trial root contains an unowned symbolic link: {relative}",
            )
        if path.is_dir():
            directories.add(relative)
        elif path.is_file():
            if relative == TRIAL_MARKER:
                continue
            files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            raise LifecycleError(
                "WI-TRIAL-NOT-OWNED",
                f"trial root contains an unsupported entry: {relative}",
            )
    return files, directories


def _trial_root_has_payload(root: Path) -> bool:
    if not root.exists():
        return False
    for path in root.iterdir():
        if path.name != ".scratch":
            return True
        if _lifecycle_path_has_reparse(path) or not path.is_dir():
            return True
        for child in path.iterdir():
            if child.name != LIFECYCLE_LOCK_RELATIVE.name:
                return True
    return False


def _prove_completed_trial(
    root: Path,
    fixture_bytes: bytes,
    expected_files: set[str],
) -> None:
    marker_path = root / TRIAL_MARKER
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleError(
            "WI-TRIAL-NOT-OWNED",
            f"non-empty trial root lacks a valid ownership receipt: {root}",
        ) from exc
    expected_keys = {
        "schemaVersion",
        "owner",
        "fixtureSha256",
        "files",
        "directories",
    }
    if not isinstance(marker, dict) or set(marker) != expected_keys:
        raise LifecycleError("WI-TRIAL-NOT-OWNED", "trial ownership receipt shape differs")
    fixture_hash = hashlib.sha256(fixture_bytes).hexdigest()
    expected_directories = _trial_expected_directories(expected_files)
    if (
        marker.get("schemaVersion") != 1
        or marker.get("owner") != TRIAL_OWNER
        or marker.get("fixtureSha256") != fixture_hash
        or set(marker.get("files", {})) != expected_files
        or set(marker.get("directories", [])) != expected_directories
    ):
        raise LifecycleError(
            "WI-TRIAL-NOT-OWNED",
            "trial ownership receipt is not target-bound to this exact fixture/output",
        )
    actual_files, actual_directories = _trial_tree(root)
    if actual_files != marker["files"] or actual_directories != expected_directories:
        raise LifecycleError(
            "WI-TRIAL-NOT-OWNED",
            "trial root bytes or membership differ from the completed ownership receipt",
        )


def _write_trial_receipt(
    root: Path,
    fixture_bytes: bytes,
    expected_files: set[str],
) -> None:
    actual_files, actual_directories = _trial_tree(root)
    expected_directories = _trial_expected_directories(expected_files)
    if set(actual_files) != expected_files or actual_directories != expected_directories:
        raise LifecycleError(
            "WI-TRIAL-OUTPUT",
            "trial output membership differs from the owned five-item manifest",
        )
    receipt = {
        "schemaVersion": 1,
        "owner": TRIAL_OWNER,
        "fixtureSha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "files": actual_files,
        "directories": sorted(actual_directories),
    }
    _atomic_write(
        root / TRIAL_MARKER,
        (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )


def run_trial(root: Path, fixture_path: Path) -> tuple[str, str]:
    fixture_bytes = fixture_path.read_bytes()
    fixture = json.loads(fixture_bytes.decode("utf-8"))
    if not isinstance(fixture, dict):
        raise LifecycleError("WI-TRIAL-FIXTURE", "fixture must be an object")
    expected_files = _trial_expected_files(fixture)
    if _trial_root_has_payload(root):
        _prove_completed_trial(root, fixture_bytes, expected_files)
    root.mkdir(parents=True, exist_ok=True)
    items = fixture.get("items")
    assert isinstance(items, list)
    work_items = _work_items_root(root)
    for epic in fixture.get("supportingEpics", []):
        _atomic_write(
            work_items / "epics" / f"{epic['slug']}.md",
            (
                "---\n"
                "status: active\n"
                f"updated: {epic['updated']}\n"
                "---\n\n"
                f"# {epic['title']}\n"
            ).encode("utf-8"),
        )
    for item in items:
        kind = item["kind"]
        slug = item["slug"]
        _validate_slug(slug)
        if kind in {"active", "blocked"}:
            _atomic_write(
                work_items / "active" / slug / "status.md",
                _fixture_status(item).encode("utf-8"),
            )
        elif kind == "backlog":
            _atomic_write(
                work_items / "backlog" / f"{slug}.md",
                (
                    f"Task: {item['task']}\n"
                    f"Next action: {item['nextAction']}\n"
                    f"updated: {item['updated']}\n"
                ).encode("utf-8"),
            )
        elif kind == "roadmap":
            _atomic_write(
                work_items / "roadmaps" / f"{slug}.md",
                (
                    "format: roadmap-v1\n"
                    "status: active\n"
                    "owner: product-manager\n"
                    f"outcomes: {item['outcomes']}\n"
                    f"order: {item['order']}\n"
                    f"milestones-or-horizon: {item['milestone']}\n"
                    "review-trigger: trial completion\n"
                    "retention: archive monthly\n"
                    f"updated: {item['updated']}\n"
                ).encode("utf-8"),
            )
        elif kind == "archived":
            _atomic_write(
                work_items
                / "archive"
                / archive_month(item["closed"])
                / slug
                / "closure.md",
                (
                    f"Closed: {item['closed']}\n"
                    f"Outcome: {item['outcome']}\n"
                    "Evidence: five-item trial\n"
                    f"Residual risk: {item['residualRisk']}\n"
                ).encode("utf-8"),
            )
        else:
            raise LifecycleError("WI-TRIAL-FIXTURE", f"unknown trial kind: {kind}")
    first = refresh_readme(root)
    first_bytes = (work_items / "README.md").read_bytes()
    second = refresh_readme(root)
    second_bytes = (work_items / "README.md").read_bytes()
    if first != second or first_bytes != second_bytes:
        raise LifecycleError("WI-README-NONDETERMINISTIC", "repeat render differs")
    text = second_bytes.decode("utf-8")
    checkbox_lines = [line for line in text.splitlines() if line.startswith("- [")]
    if len(checkbox_lines) != 5 or any(
        not (line.startswith("- [ ]") or line.startswith("- [x]")) for line in checkbox_lines
    ):
        raise LifecycleError("WI-TRIAL-COUNT", "trial did not render five canonical checkboxes")
    positions = [text.index(f"## {section}") for section in README_SECTIONS]
    if positions != sorted(positions):
        raise LifecycleError("WI-TRIAL-SECTIONS", "README section order differs")
    if not all(token in text for token in ("[roadmap](", "[epic](", "[work item](")):
        raise LifecycleError("WI-TRIAL-LINKS", "progressive links are incomplete")
    _write_trial_receipt(root, fixture_bytes, expected_files)
    return first, second


LEGACY_PROJECTION_MANIFEST_DIR = "legacy-ledger-projection-manifests"
LEGACY_PROJECTION_REGISTRY = "legacy-ledger-projections.jsonl"
LEGACY_PROJECTION_RECEIPTS = "legacy-ledger-projection-receipts"
LEGACY_HISTORICAL_DISPOSITIONS = "legacy-ledger-historical-dispositions"
_PROJECTION_OPERATION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", re.ASCII)


def _projection_fail(failure_id: str, message: str) -> None:
    raise LifecycleError(failure_id, message)


def _projection_object(data: bytes, label: str) -> dict:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _projection_fail("WI-LEDGER-MIGRATION-MANIFEST-INVALID", f"{label} is not one JSON object")
        raise AssertionError from exc
    if not isinstance(value, dict):
        _projection_fail("WI-LEDGER-MIGRATION-MANIFEST-INVALID", f"{label} is not one JSON object")
    return value


def _projection_json(data: dict) -> bytes:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _projection_operation(operation_id: str, recorded_at: str) -> None:
    if _PROJECTION_OPERATION_RE.fullmatch(operation_id) is None:
        _projection_fail("WI-LEDGER-MIGRATION-TARGET-IDENTITY", "projection operation id is not bounded")
    _load_agent_run_ledger()._strict_migration_inputs(operation_id, recorded_at)


def _projection_paths(root: Path) -> tuple[Path, Path, Path, Path]:
    work_items = _work_items_root(root)
    repository = work_items.parent
    manifests = _require_lifecycle_mutation_path(repository, work_items / LEGACY_PROJECTION_MANIFEST_DIR, failure_id="WI-LEDGER-MIGRATION-MANIFEST-INVALID")
    registry = _require_lifecycle_mutation_path(repository, work_items / LEGACY_PROJECTION_REGISTRY, failure_id="WI-LEDGER-MIGRATION-COMMIT-INDETERMINATE")
    receipts = _require_lifecycle_mutation_path(repository, work_items / LEGACY_PROJECTION_RECEIPTS, failure_id="WI-LEDGER-MIGRATION-RECEIPT-MISMATCH")
    dispositions = _require_lifecycle_mutation_path(repository, work_items / LEGACY_HISTORICAL_DISPOSITIONS, failure_id="WI-LEDGER-MIGRATION-MANIFEST-INVALID")
    return manifests, registry, receipts, dispositions


def _projection_manifest_blobs(root: Path, manifests: Path, manifest_id: str, supplied: bytes) -> dict[str, bytes]:
    blobs: dict[str, bytes] = {}
    validator = _load_agent_run_ledger().load_validator()
    try:
        manifest_id = validator.confine_legacy_projection_identifier(
            manifest_id, failure_id="WI-LEDGER-MIGRATION-MANIFEST-INVALID"
        )
    except ValueError as exc:
        _projection_fail("WI-LEDGER-MIGRATION-MANIFEST-INVALID", f"projection manifest id is unsafe: {exc}")
        raise AssertionError from exc
    if manifests.exists():
        if not manifests.is_dir() or _lifecycle_path_has_reparse(manifests):
            _projection_fail("WI-LEDGER-MIGRATION-MANIFEST-INVALID", "projection manifest directory is unsafe")
        for path in manifests.iterdir():
            if path.suffix != ".json" or _lifecycle_path_has_reparse(path):
                _projection_fail("WI-LEDGER-MIGRATION-MANIFEST-INVALID", "projection manifest directory has unsafe member")
            try:
                safe = validator.confine_legacy_projection_path(
                    root, f"work-items/{LEGACY_PROJECTION_MANIFEST_DIR}/{path.name}",
                    prefix=("work-items", LEGACY_PROJECTION_MANIFEST_DIR), leaf_kind="file",
                    failure_id="WI-LEDGER-MIGRATION-MANIFEST-INVALID",
                )
            except ValueError as exc:
                _projection_fail("WI-LEDGER-MIGRATION-MANIFEST-INVALID", f"projection manifest member is unsafe: {exc}")
                raise AssertionError from exc
            blobs[safe.name] = safe.read_bytes()
    name = f"{manifest_id}.json"
    current = blobs.get(name)
    if current is not None and current != supplied:
        _projection_fail("WI-LEDGER-MIGRATION-MANIFEST-INVALID", "create-only manifest bytes differ")
    blobs[name] = supplied
    return blobs


def _projection_registry_records(data: bytes) -> list[tuple[dict, bytes]]:
    records: list[tuple[dict, bytes]] = []
    for ordinal, line in enumerate(data.splitlines(keepends=True), start=1):
        record = _projection_object(line.rstrip(b"\r\n"), f"registry line {ordinal}")
        records.append((record, line))
    return records


def _projection_entry(manifest: dict, entry_id: str, raw_ordinal: int, root: Path) -> dict:
    manifest_id = manifest.get("manifestId")
    if not isinstance(manifest_id, str) or _PROJECTION_OPERATION_RE.fullmatch(manifest_id) is None:
        _projection_fail("WI-LEDGER-MIGRATION-MANIFEST-INVALID", "manifest id is invalid")
    entries = [entry for entry in manifest.get("entries", []) if isinstance(entry, dict) and entry.get("entryId") == entry_id]
    if len(entries) != 1 or not isinstance(raw_ordinal, int):
        _projection_fail("WI-LEDGER-MIGRATION-TARGET-IDENTITY", "manifest entry or raw ordinal is not unique")
    entry = entries[0]
    required = {"entryId", "profileId", "profileVersion", "workItem", "ledgerPath", "ledgerSha256", "rawLineOrdinals", "rawLineSha256", "projectedEvents", "projectedEventSha256"}
    if (
        not required <= set(entry)
        or set(entry) - (required | {"artifactSha256"})
        or not all(isinstance(entry[key], list) for key in ("rawLineOrdinals", "rawLineSha256", "projectedEvents", "projectedEventSha256"))
    ):
        _projection_fail("WI-LEDGER-MIGRATION-MANIFEST-INVALID", "manifest entry shape is incomplete")
    ordinals = entry["rawLineOrdinals"]
    raw_digests = entry["rawLineSha256"]
    projected_events = entry["projectedEvents"]
    projected_digests = entry["projectedEventSha256"]
    if (
        not ordinals
        or not (len(ordinals) == len(raw_digests) == len(projected_events) == len(projected_digests))
        or any(not isinstance(value, int) or value < 1 for value in ordinals)
        or len(set(ordinals)) != len(ordinals)
        or any(not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None for value in (*raw_digests, *projected_digests))
        or any(not isinstance(value, dict) for value in projected_events)
    ):
        _projection_fail("WI-LEDGER-MIGRATION-MANIFEST-INVALID", "manifest entry bindings are not one unique parallel set")
    try:
        index = entry["rawLineOrdinals"].index(raw_ordinal)
        raw_digest = entry["rawLineSha256"][index]
        projected = entry["projectedEvents"][index]
        projected_digest = entry["projectedEventSha256"][index]
    except (ValueError, IndexError):
        _projection_fail("WI-LEDGER-MIGRATION-TARGET-IDENTITY", "raw ordinal is not bound by the manifest entry")
    if (
        not isinstance(entry.get("entryId"), str)
        or not isinstance(entry.get("profileId"), str)
        or not isinstance(entry.get("profileVersion"), int)
        or entry["profileVersion"] < 1
        or not all(isinstance(value, str) for value in (entry["workItem"], entry["ledgerPath"], entry["ledgerSha256"], raw_digest, projected_digest))
        or re.fullmatch(r"[0-9a-f]{64}", entry["ledgerSha256"]) is None
        or not isinstance(projected, dict)
    ):
        _projection_fail("WI-LEDGER-MIGRATION-MANIFEST-INVALID", "manifest entry value types are invalid")
    def controlled_path(value: str, label: str) -> Path:
        try:
            return _load_agent_run_ledger().load_validator().confine_legacy_projection_path(
                root, value, prefix=("work-items",), failure_id="WI-LEDGER-MIGRATION-TARGET-IDENTITY"
            )
        except ValueError as exc:
            _projection_fail("WI-LEDGER-MIGRATION-TARGET-IDENTITY", f"{label} is unsafe: {exc}")
            raise AssertionError from exc

    item = controlled_path(entry["workItem"], "manifest work item")
    ledger = controlled_path(entry["ledgerPath"], "manifest ledger")
    item_parts = entry["workItem"].split("/")
    if (
        len(item_parts) != 3
        or item_parts[:2] != ["work-items", "active"]
        or _PROJECTION_OPERATION_RE.fullmatch(item_parts[2]) is None
        or not item.is_dir() or _lifecycle_path_has_reparse(item)
        or ledger != item / "agent-runs.jsonl" or not ledger.is_file() or _lifecycle_path_has_reparse(ledger)
    ):
        _projection_fail("WI-LEDGER-MIGRATION-TARGET-IDENTITY", "manifest target is not one safe active work-item ledger")
    ledger_bytes = ledger.read_bytes()
    lines = ledger_bytes.splitlines(keepends=True)
    if _sha256_bytes(ledger_bytes) != entry["ledgerSha256"]:
        _projection_fail("WI-LEDGER-MIGRATION-LEDGER-DRIFT", "manifest ledger digest differs")
    for bound_ordinal, bound_digest, bound_projected, bound_projected_digest in zip(
        ordinals, raw_digests, projected_events, projected_digests
    ):
        if bound_ordinal > len(lines) or _sha256_bytes(lines[bound_ordinal - 1]) != bound_digest:
            _projection_fail("WI-LEDGER-MIGRATION-TARGET-DIGEST", "manifest raw line digest differs")
        if _sha256_bytes(_projection_json(bound_projected)) != bound_projected_digest:
            _projection_fail("WI-LEDGER-MIGRATION-TARGET-DIGEST", "manifest projected event digest differs")
    return {**entry, "_item": item, "_ledger": ledger, "_ledgerBytes": ledger_bytes, "_rawDigest": raw_digest, "_projected": projected, "_projectedDigest": projected_digest}


def _projection_record(manifest: dict, manifest_bytes: bytes, entry_id: str, raw_ordinal: int, operation_group_id: str, group_member_index: int, group_member_count: int, recorded_at: str, root: Path) -> dict:
    entry = _projection_entry(manifest, entry_id, raw_ordinal, root)
    operation_id = _projection_group_ids(operation_group_id, group_member_count)[group_member_index - 1]
    return {
        "schemaVersion": 2, "operationId": operation_id, "operationGroupId": operation_group_id,
        "groupMemberIndex": group_member_index, "groupMemberCount": group_member_count, "state": "apply",
        "profileId": entry["profileId"], "profileVersion": entry["profileVersion"],
        "manifestId": manifest["manifestId"], "manifestSha256": _sha256_bytes(manifest_bytes),
        "manifestEntryId": entry_id, "workItem": entry["workItem"], "ledgerPath": entry["ledgerPath"],
        "ledgerSha256": entry["ledgerSha256"], "rawLineOrdinal": raw_ordinal,
        "rawLineSha256": entry["_rawDigest"], "projectedEvent": entry["_projected"],
        "projectedEventSha256": entry["_projectedDigest"], "recordedAt": recorded_at,
    }


def _projection_confine_output_sink(path: Path, failure_id: str) -> tuple[Path, bool]:
    """Return one ordinary direct-child output sink before any content probe/write.

    Pre-existing links/reparse leaves are rejected through lstat.  This is a
    deterministic preflight only; hostile same-user rename races remain outside
    the existing lifecycle-lock claim.
    """
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    try:
        parent_info = parent.lstat()
    except OSError as exc:
        raise LifecycleError(failure_id, "projection output parent is unavailable") from exc
    if _lifecycle_path_has_reparse(parent) or not stat.S_ISDIR(parent_info.st_mode):
        _projection_fail(failure_id, "projection output parent is unsafe")
    if path.parent != parent or path.name in {"", ".", ".."}:
        _projection_fail(failure_id, "projection output is not one direct child")
    try:
        info = path.lstat()
    except FileNotFoundError:
        return path, False
    except OSError as exc:
        raise LifecycleError(failure_id, "projection output leaf is unavailable") from exc
    if _lifecycle_path_has_reparse(path) or not stat.S_ISREG(info.st_mode):
        _projection_fail(failure_id, "projection output leaf is unsafe")
    return path, True


def _projection_create_or_exact(path: Path, data: bytes, failure_id: str) -> bool:
    path, replay = _projection_confine_output_sink(path, failure_id)
    if replay:
        if path.read_bytes() != data:
            _projection_fail(failure_id, "create-only target differs after write")
        return True
    temporary: Path | None = None
    try:
        descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            path, replay = _projection_confine_output_sink(path, failure_id)
            if not replay:
                _projection_fail(failure_id, "projection output disappeared during create-only write")
        except OSError as exc:
            raise LifecycleError(failure_id, "atomic create-only write is unavailable") from exc
        path, _replay = _projection_confine_output_sink(path, failure_id)
        if path.read_bytes() != data:
            _projection_fail(failure_id, "create-only target differs after write")
        return replay
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _projection_reconcile_receipt(receipts: Path, facts: dict) -> None:
    try:
        operation_id = _load_agent_run_ledger().load_validator().confine_legacy_projection_identifier(
            facts.get("operationId"), failure_id="WI-LEDGER-MIGRATION-RECEIPT-MISMATCH"
        )
    except ValueError as exc:
        _projection_fail("WI-LEDGER-MIGRATION-RECEIPT-MISMATCH", f"projection receipt identifier is unsafe: {exc}")
        raise AssertionError from exc
    path = receipts / f"{operation_id}.json"
    _projection_create_or_exact(path, (json.dumps(facts, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"), "WI-LEDGER-MIGRATION-RECEIPT-MISMATCH")


def _projection_candidate_errors(entry: dict, manifests: dict[str, bytes], registry_bytes: bytes) -> list[str]:
    validator = _load_agent_run_ledger().load_validator()
    return validator.validate_work_item(
        entry["_item"], validate_status_file=False,
        projection_manifest_blobs=manifests,
        projection_registry_bytes=registry_bytes,
    )


def _projection_group_ids(operation_id: str, count: int) -> list[str]:
    if count < 1:
        _projection_fail("WI-LEDGER-MIGRATION-TOPOLOGY", "projection group count must be positive")
    values = [operation_id] if count == 1 else [
        "m:" + _sha256_bytes(
            json.dumps([operation_id, index, count], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )
        for index in range(1, count + 1)
    ]
    if any(len(value) > 128 for value in values):
        _projection_fail("WI-LEDGER-MIGRATION-TARGET-IDENTITY", "derived projection member id exceeds its bounded grammar")
    return values


def _projection_group_facts(
    operation_id: str,
    lines: list[bytes],
    registry_before: bytes,
    registry_prefix: bytes,
) -> dict:
    record_hashes = [_sha256_bytes(line) for line in lines]
    return {
        "schemaVersion": 1,
        "operationId": operation_id,
        "recordSha256": record_hashes[0] if len(record_hashes) == 1 else record_hashes,
        "registryBeforeSha256": _sha256_bytes(registry_before),
        "registrySha256": _sha256_bytes(registry_prefix),
    }


def _projection_existing_group(
    records: list[tuple[dict, bytes]], child_ids: list[str], lines: list[bytes]
) -> tuple[bytes, bytes] | None:
    """Return exact before/after prefixes for one persisted append group.

    Receipt facts are derived from the durable prefix ending at this group, not
    from the current whole registry.  This keeps replays byte-stable after a
    later independent append.
    """
    positions: list[int] = []
    for child_id, expected_line in zip(child_ids, lines):
        matched = [index for index, (record, _physical) in enumerate(records) if record.get("operationId") == child_id]
        if len(matched) > 1:
            _projection_fail("WI-LEDGER-MIGRATION-TOPOLOGY", "projection operation id is duplicated")
        if not matched:
            return None
        index = matched[0]
        if records[index][1] != expected_line:
            _projection_fail("WI-LEDGER-MIGRATION-TOPOLOGY", "projection operation group differs from its exact inputs")
        positions.append(index)
    if positions != list(range(positions[0], positions[0] + len(positions))):
        _projection_fail("WI-LEDGER-MIGRATION-TOPOLOGY", "projection operation group is non-contiguous")
    before = b"".join(physical for _record, physical in records[:positions[0]])
    after = b"".join(physical for _record, physical in records[:positions[-1] + 1])
    return before, after


def _projection_require_replay_anchor(expected_registry_sha256: str, group_before: bytes, current_registry: bytes) -> None:
    """One replay rule for singleton and v2 groups, independent of later appends."""
    accepted = {_sha256_bytes(group_before), _sha256_bytes(current_registry)}
    if expected_registry_sha256 not in accepted:
        _projection_fail("WI-LEDGER-MIGRATION-LEDGER-DRIFT", "replay expected registry digest differs from durable anchors")


def _apply_legacy_ledger_projection_locked(root: Path, manifest_bytes: bytes, entry_id: str, raw_ordinal: int, expected_registry_sha256: str, operation_id: str, recorded_at: str, *, inject_failure: str | None = None) -> dict:
    _projection_operation(operation_id, recorded_at)
    manifests_path, registry_path, receipts, _dispositions = _projection_paths(root)
    manifest = _projection_object(manifest_bytes, "manifest")
    manifest_id = manifest.get("manifestId")
    if not isinstance(manifest_id, str) or _PROJECTION_OPERATION_RE.fullmatch(manifest_id) is None:
        _projection_fail("WI-LEDGER-MIGRATION-MANIFEST-INVALID", "manifest id is required")
    manifests = _projection_manifest_blobs(Path(root).resolve(), manifests_path, manifest_id, manifest_bytes)
    before = registry_path.read_bytes() if registry_path.exists() else b""
    if registry_path.exists() and (not registry_path.is_file() or _lifecycle_path_has_reparse(registry_path)):
        _projection_fail("WI-LEDGER-MIGRATION-COMMIT-INDETERMINATE", "projection registry is unsafe")
    configured_entries = [row for row in manifest.get("entries", []) if isinstance(row, dict) and row.get("entryId") == entry_id]
    if len(configured_entries) != 1 or not configured_entries[0].get("rawLineOrdinals"):
        _projection_fail("WI-LEDGER-MIGRATION-TARGET-IDENTITY", "manifest entry is unavailable")
    repository = Path(root).resolve()
    if repository.name == "work-items" or _lifecycle_path_has_reparse(repository / "work-items"):
        _projection_fail("WI-LEDGER-MIGRATION-TARGET-IDENTITY", "projection writer requires one ordinary repository root")
    seed = _projection_entry(manifest, entry_id, raw_ordinal, repository)
    ordinals = seed["rawLineOrdinals"]
    child_ids = _projection_group_ids(operation_id, len(ordinals))
    records = [
        _projection_record(manifest, manifest_bytes, entry_id, ordinal, operation_id, index, len(ordinals), recorded_at, repository)
        for index, ordinal in enumerate(ordinals, start=1)
    ]
    lines = [_projection_json(record) + b"\n" for record in records]
    registry_records = _projection_registry_records(before)
    persisted = _projection_existing_group(registry_records, child_ids, lines)
    if persisted is not None:
        persisted_before, persisted_after = persisted
        _projection_require_replay_anchor(expected_registry_sha256, persisted_before, before)
        _projection_create_or_exact(manifests_path / f"{manifest_id}.json", manifest_bytes, "WI-LEDGER-MIGRATION-MANIFEST-INVALID")
        facts = _projection_group_facts(operation_id, lines, persisted_before, persisted_after)
        _projection_reconcile_receipt(receipts, facts)
        return {**facts, "replay": True}
    existing_ids = {record.get("operationId") for record, _physical in registry_records}
    if any(child_id in existing_ids for child_id in child_ids):
        _projection_fail("WI-LEDGER-MIGRATION-TOPOLOGY", "projection operation group is partial")
    if any(
        isinstance(existing_id, str)
        and existing_id.casefold() == child_id.casefold()
        and existing_id != child_id
        for existing_id in existing_ids
        for child_id in child_ids
    ):
        _projection_fail("WI-LEDGER-MIGRATION-TOPOLOGY", "projection operation id collides case-insensitively")
    if _sha256_bytes(before) != expected_registry_sha256:
        _projection_fail("WI-LEDGER-MIGRATION-LEDGER-DRIFT", "projection registry digest changed")
    candidate = before + b"".join(lines)
    errors = _projection_candidate_errors(seed, manifests, candidate)
    if errors:
        _projection_fail("WI-LEDGER-MIGRATION-CANDIDATE-INVALID", "; ".join(errors))
    if inject_failure == "before-registry":
        _projection_fail("WI-LEDGER-MIGRATION-COMMIT-INDETERMINATE", "injected interruption before registry commit")
    try:
        _atomic_write(registry_path, candidate)
        if inject_failure == "corrupt-registry":
            registry_path.write_bytes(candidate + b"corrupt")
        actual = registry_path.read_bytes()
    except OSError as exc:
        raise LifecycleError("WI-LEDGER-MIGRATION-COMMIT-INDETERMINATE", "projection registry readback failed") from exc
    if actual != candidate:
        if actual == before:
            _projection_fail("WI-LEDGER-MIGRATION-COMMIT-INDETERMINATE", "projection registry remains exact before image")
        _projection_fail("WI-LEDGER-MIGRATION-COMMIT-INDETERMINATE", "projection registry is neither exact before nor after")
    if inject_failure == "after-registry":
        _projection_fail("WI-LEDGER-MIGRATION-COMMIT-INDETERMINATE", "injected interruption after registry commit")
    _projection_create_or_exact(manifests_path / f"{manifest_id}.json", manifest_bytes, "WI-LEDGER-MIGRATION-MANIFEST-INVALID")
    facts = _projection_group_facts(operation_id, lines, before, candidate)
    _projection_reconcile_receipt(receipts, facts)
    return {**facts, "replay": False}


_apply_legacy_ledger_projection_transaction = _lifecycle_participant(_apply_legacy_ledger_projection_locked)


def apply_legacy_ledger_projection(root: Path, manifest_bytes: bytes, entry_id: str, raw_ordinal: int, expected_registry_sha256: str, operation_id: str, recorded_at: str, *, dry_run: bool = False, inject_failure: str | None = None) -> dict:
    if dry_run:
        _projection_operation(operation_id, recorded_at)
        manifest = _projection_object(manifest_bytes, "manifest")
        entry = _projection_entry(manifest, entry_id, raw_ordinal, Path(root).resolve())
        child_ids = _projection_group_ids(operation_id, len(entry["rawLineOrdinals"]))
        return {"schemaVersion": 1, "dryRun": True, "byteInventory": {}, "operationIds": child_ids}
    return _apply_legacy_ledger_projection_transaction(root, manifest_bytes, entry_id, raw_ordinal, expected_registry_sha256, operation_id, recorded_at, inject_failure=inject_failure)


def _projection_active_records(records: list[tuple[dict, bytes]]) -> dict[str, tuple[dict, bytes]]:
    """Reduce exact apply/revoke lines without granting the registry new authority."""
    active: dict[str, tuple[dict, bytes]] = {}
    for record, physical in records:
        operation = record.get("operationId")
        if not isinstance(operation, str):
            _projection_fail("WI-LEDGER-MIGRATION-TOPOLOGY", "registry operation id is invalid")
        if record.get("state") == "apply":
            if operation in active:
                _projection_fail("WI-LEDGER-MIGRATION-TOPOLOGY", "registry apply operation id is duplicated")
            active[operation] = (record, physical)
        elif record.get("state") == "revoke":
            target = record.get("revokeOfOperationId")
            if not isinstance(target, str) or target not in active:
                _projection_fail("WI-LEDGER-MIGRATION-TOPOLOGY", "registry revoke lacks one earlier active apply")
            if record.get("revokeOfRecordSha256") != _sha256_bytes(active[target][1]):
                _projection_fail("WI-LEDGER-MIGRATION-TARGET-DIGEST", "registry revoke does not bind exact apply bytes")
            active.pop(target)
        else:
            _projection_fail("WI-LEDGER-MIGRATION-TOPOLOGY", "registry state is not apply or revoke")
    return active


def _projection_digest_list(value: object, expected_count: int) -> list[str]:
    values = [value] if isinstance(value, str) else value
    if (
        not isinstance(values, list)
        or len(values) != expected_count
        or any(not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None for digest in values)
    ):
        _projection_fail("WI-LEDGER-MIGRATION-TARGET-DIGEST", "revoke must bind every exact apply record digest")
    return values


def _projection_cli_record_digests(value: str) -> str | list[str]:
    """Accept the scalar legacy form or one JSON array for an atomic row group."""
    if not value.startswith("["):
        return value
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        _projection_fail("WI-LEDGER-MIGRATION-TARGET-DIGEST", "record digest group is not valid JSON")
    if not isinstance(parsed, list):
        _projection_fail("WI-LEDGER-MIGRATION-TARGET-DIGEST", "record digest group is not an array")
    return parsed


def _revoke_legacy_ledger_projection_locked(root: Path, apply_operation_id: str, apply_record_sha256: str | list[str], expected_registry_sha256: str, operation_id: str, recorded_at: str) -> dict:
    _projection_operation(operation_id, recorded_at)
    manifests_path, registry_path, receipts, _dispositions = _projection_paths(root)
    repository = Path(root).resolve()
    if repository.name == "work-items" or _lifecycle_path_has_reparse(repository / "work-items"):
        _projection_fail("WI-LEDGER-MIGRATION-TARGET-IDENTITY", "projection writer requires one ordinary repository root")
    if not registry_path.is_file() or _lifecycle_path_has_reparse(registry_path):
        _projection_fail("WI-LEDGER-MIGRATION-TARGET-IDENTITY", "projection registry is unavailable")
    before = registry_path.read_bytes()
    records = _projection_registry_records(before)
    matching = [
        (index, record, physical) for index, (record, physical) in enumerate(records)
        if record.get("operationGroupId", record.get("operationId")) == apply_operation_id
    ]
    if matching:
        target_index, target_record, _physical = matching[0]
    else:
        _projection_fail("WI-LEDGER-MIGRATION-TARGET-IDENTITY", "revoke target apply operation is unavailable")
    if target_record.get("state") != "apply":
        _projection_fail("WI-LEDGER-MIGRATION-TOPOLOGY", "revoke target is not an apply record")
    validator = _load_agent_run_ledger().load_validator()
    try:
        manifest_id = validator.confine_legacy_projection_identifier(
            target_record.get("manifestId"), failure_id="WI-LEDGER-MIGRATION-MANIFEST-INVALID"
        )
        manifest_path = validator.confine_legacy_projection_path(
            repository, f"work-items/{LEGACY_PROJECTION_MANIFEST_DIR}/{manifest_id}.json",
            prefix=("work-items", LEGACY_PROJECTION_MANIFEST_DIR), leaf_kind="file",
            failure_id="WI-LEDGER-MIGRATION-MANIFEST-INVALID",
        )
    except ValueError as exc:
        _projection_fail("WI-LEDGER-MIGRATION-MANIFEST-INVALID", f"target manifest is unsafe: {exc}")
        raise AssertionError from exc
    manifest_bytes = manifest_path.read_bytes()
    manifest = _projection_object(manifest_bytes, "target manifest")
    entry = _projection_entry(manifest, target_record["manifestEntryId"], target_record["rawLineOrdinal"], repository)
    child_ids = _projection_group_ids(apply_operation_id, len(entry["rawLineOrdinals"]))
    apply_lines: list[bytes] = []
    apply_records: list[dict] = []
    apply_indices: list[int] = []
    for child_id, raw_ordinal in zip(child_ids, entry["rawLineOrdinals"]):
        matches = [(index, record, physical) for index, (record, physical) in enumerate(records) if record.get("operationId") == child_id]
        if len(matches) != 1 or matches[0][1].get("state") != "apply" or matches[0][1].get("rawLineOrdinal") != raw_ordinal:
            _projection_fail("WI-LEDGER-MIGRATION-TOPOLOGY", "revoke target apply group is partial or differs")
        apply_indices.append(matches[0][0])
        apply_lines.append(matches[0][2])
        apply_records.append(matches[0][1])
    if apply_indices != list(range(apply_indices[0], apply_indices[0] + len(apply_indices))):
        _projection_fail("WI-LEDGER-MIGRATION-TOPOLOGY", "revoke target apply group is non-contiguous")
    supplied_digests = _projection_digest_list(apply_record_sha256, len(apply_lines))
    if supplied_digests != [_sha256_bytes(line) for line in apply_lines]:
        _projection_fail("WI-LEDGER-MIGRATION-TARGET-DIGEST", "revoke target does not bind exact apply group bytes")
    revoke_ids = _projection_group_ids(operation_id, len(child_ids))
    revokes = []
    for member_index, (revoke_id, apply_id, apply_line, apply_record) in enumerate(zip(revoke_ids, child_ids, apply_lines, apply_records), start=1):
        revokes.append({
            **{key: apply_record[key] for key in ("schemaVersion", "profileId", "profileVersion", "manifestId", "manifestSha256", "manifestEntryId", "workItem", "ledgerPath", "ledgerSha256", "rawLineOrdinal", "rawLineSha256", "projectedEvent", "projectedEventSha256")},
            "operationGroupId": operation_id, "groupMemberIndex": member_index, "groupMemberCount": len(revoke_ids),
            "operationId": revoke_id, "state": "revoke", "recordedAt": recorded_at,
            "revokeOfOperationId": apply_id, "revokeOfOperationGroupId": apply_operation_id, "revokeOfRecordSha256": _sha256_bytes(apply_line),
        })
    revoke_lines = [_projection_json(record) + b"\n" for record in revokes]
    persisted = _projection_existing_group(records, revoke_ids, revoke_lines)
    if persisted is not None:
        persisted_before, persisted_after = persisted
        _projection_require_replay_anchor(expected_registry_sha256, persisted_before, before)
        facts = _projection_group_facts(operation_id, revoke_lines, persisted_before, persisted_after)
        _projection_reconcile_receipt(receipts, facts)
        return {**facts, "replay": True}
    active = _projection_active_records(records)
    if any(child_id not in active for child_id in child_ids):
        _projection_fail("WI-LEDGER-MIGRATION-TOPOLOGY", "apply group is already revoked or partially active")
    for later, _physical in records[apply_indices[-1] + 1:]:
        if (
            later.get("manifestId") == target_record["manifestId"]
            and later.get("manifestEntryId") == target_record["manifestEntryId"]
            and later.get("state") in {"apply", "revoke"}
        ):
            _projection_fail("WI-LEDGER-MIGRATION-TOPOLOGY", "revoke is blocked by a later dependent entry operation")
    existing_ids = {record.get("operationId") for record, _physical in records}
    if any(revoke_id in existing_ids for revoke_id in revoke_ids):
        _projection_fail("WI-LEDGER-MIGRATION-TOPOLOGY", "revoke operation group is partial")
    if _sha256_bytes(before) != expected_registry_sha256:
        _projection_fail("WI-LEDGER-MIGRATION-LEDGER-DRIFT", "projection registry digest changed")
    candidate = before + b"".join(revoke_lines)
    manifests = _projection_manifest_blobs(repository, manifests_path, manifest["manifestId"], manifest_bytes)
    baseline = b"".join(physical for index, (_record, physical) in enumerate(records) if index not in set(apply_indices))
    baseline_errors = _projection_candidate_errors(entry, manifests, baseline)
    candidate_errors = _projection_candidate_errors(entry, manifests, candidate)
    if Counter(candidate_errors) != Counter(baseline_errors):
        _projection_fail("WI-LEDGER-MIGRATION-CANDIDATE-INVALID", "; ".join(candidate_errors))
    try:
        _atomic_write(registry_path, candidate)
        actual = registry_path.read_bytes()
    except OSError as exc:
        raise LifecycleError("WI-LEDGER-MIGRATION-COMMIT-INDETERMINATE", "projection revoke registry readback failed") from exc
    if actual != candidate:
        _projection_fail("WI-LEDGER-MIGRATION-COMMIT-INDETERMINATE", "projection revoke registry readback differs")
    facts = _projection_group_facts(operation_id, revoke_lines, before, candidate)
    _projection_reconcile_receipt(receipts, facts)
    return {**facts, "replay": False}


_revoke_legacy_ledger_projection_transaction = _lifecycle_participant(_revoke_legacy_ledger_projection_locked)


def revoke_legacy_ledger_projection(root: Path, apply_operation_id: str, apply_record_sha256: str | list[str], expected_registry_sha256: str, operation_id: str, recorded_at: str) -> dict:
    return _revoke_legacy_ledger_projection_transaction(root, apply_operation_id, apply_record_sha256, expected_registry_sha256, operation_id, recorded_at)


def _write_legacy_ledger_irrecoverable_disposition_locked(root: Path, disposition_bytes: bytes) -> dict:
    _manifests, _registry, _receipts, dispositions = _projection_paths(root)
    disposition = _projection_object(disposition_bytes, "irrecoverable disposition")
    work_item = disposition.get("workItem")
    archive_identity = disposition.get("archiveIdentity")
    if not isinstance(work_item, str) or not isinstance(archive_identity, str):
        _projection_fail("WI-LEDGER-MIGRATION-MANIFEST-INVALID", "irrecoverable disposition lacks exact identity")
    validator = _load_agent_run_ledger().load_validator()
    repository = Path(root).resolve()
    try:
        validator.confine_legacy_projection_identifier(
            archive_identity, failure_id="WI-LEDGER-MIGRATION-TARGET-IDENTITY"
        )
        archive = validator.confine_legacy_projection_path(
            repository, work_item, prefix=("work-items", "archive"), leaf_kind="directory",
            failure_id="WI-LEDGER-MIGRATION-TARGET-IDENTITY",
        )
    except ValueError as exc:
        _projection_fail("WI-LEDGER-MIGRATION-TARGET-IDENTITY", f"irrecoverable disposition target is unsafe: {exc}")
        raise AssertionError from exc
    errors = validator.validate_manifest_bound_irrecoverable_disposition(disposition, archive_identity, archive)
    if errors:
        _projection_fail("WI-LEDGER-MIGRATION-MANIFEST-INVALID", "; ".join(errors))
    try:
        receipt = validator.confine_legacy_projection_path(
            repository, f"{work_item}/lifecycle-transition-receipt.json",
            prefix=("work-items", "archive"), leaf_kind="file",
            failure_id="WI-LEDGER-MIGRATION-TARGET-IDENTITY",
        )
    except ValueError as exc:
        _projection_fail("WI-LEDGER-MIGRATION-TARGET-IDENTITY", f"archive transition receipt is unsafe: {exc}")
        raise AssertionError from exc
    try:
        observed = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LifecycleError("WI-LEDGER-MIGRATION-TARGET-IDENTITY", "archive identity receipt is unavailable") from exc
    if not isinstance(observed, dict) or observed.get("operationId") != archive_identity:
        _projection_fail("WI-LEDGER-MIGRATION-TARGET-IDENTITY", "archive identity differs")
    try:
        archive_identity = validator.confine_legacy_projection_identifier(
            archive_identity, failure_id="WI-LEDGER-MIGRATION-TARGET-IDENTITY"
        )
    except ValueError as exc:
        _projection_fail("WI-LEDGER-MIGRATION-TARGET-IDENTITY", f"disposition output identifier is unsafe: {exc}")
        raise AssertionError from exc
    target = dispositions / f"{archive_identity}.json"
    replay = _projection_create_or_exact(target, disposition_bytes, "WI-LEDGER-MIGRATION-MANIFEST-INVALID")
    return {"schemaVersion": 1, "archiveIdentity": archive_identity, "replay": replay}


_write_legacy_ledger_irrecoverable_disposition_transaction = _lifecycle_participant(_write_legacy_ledger_irrecoverable_disposition_locked)


def write_legacy_ledger_irrecoverable_disposition(root: Path, disposition_bytes: bytes) -> dict:
    return _write_legacy_ledger_irrecoverable_disposition_transaction(root, disposition_bytes)


def _read_arg_file(path: str) -> bytes:
    return Path(path).read_bytes()


def _add_root(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default=".", help="Repository or work-items root")


def _add_injection(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--inject-readme-failure",
        choices=("after-canonical",),
        help=argparse.SUPPRESS,
    )


def _parse_partial_recovery_status_bindings(values: list[str]) -> dict[str, str]:
    bindings: dict[str, str] = {}
    for value in values:
        if value.count("=") != 1:
            raise _partial_recovery_fail(
                "WI-PARTIAL-MIGRATION-RECOVERY-COVERAGE",
                "target status preimage must be <reference>=<sha256>",
            )
        reference, digest = value.split("=", 1)
        if (
            reference in bindings
            or reference not in PARTIAL_MIGRATION_RECOVERY_TARGETS
            or not re.fullmatch(r"[0-9A-Fa-f]{64}", digest)
        ):
            raise _partial_recovery_fail(
                "WI-PARTIAL-MIGRATION-RECOVERY-COVERAGE",
                "target status preimage bindings differ from the exact incident",
            )
        bindings[reference] = digest.upper()
    if set(bindings) != set(PARTIAL_MIGRATION_RECOVERY_TARGETS):
        raise _partial_recovery_fail(
            "WI-PARTIAL-MIGRATION-RECOVERY-COVERAGE",
            "both exact incident target status preimages are required",
        )
    return bindings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("candidate", "start", "update", "close", "reopen"):
        command = sub.add_parser(name)
        _add_root(command)
        _add_injection(command)
        command.add_argument("--slug", required=True)
        if name == "candidate":
            command.add_argument("--file", required=True)
        elif name in {"start", "update"}:
            command.add_argument("--status-file", required=True)
        elif name == "close":
            command.add_argument("--closure-file", required=True)
            command.add_argument("--terminal-instant", required=True)
        else:
            command.add_argument("--successor-slug", required=True)
            command.add_argument("--status-file", required=True)
    convert_legacy = sub.add_parser("convert-legacy-candidate")
    _add_root(convert_legacy)
    _add_injection(convert_legacy)
    convert_legacy.add_argument("--slug", required=True)
    convert_legacy.add_argument("--file", required=True)
    retire_legacy = sub.add_parser("retire-legacy-backlog")
    _add_root(retire_legacy)
    _add_injection(retire_legacy)
    retire_legacy.add_argument("--slug", required=True)
    retire_legacy.add_argument("--disposition-file", required=True)
    retire_legacy.add_argument("--terminal-instant", required=True)
    refresh = sub.add_parser("refresh")
    _add_root(refresh)
    refresh.add_argument("--reset-static-guide", action="store_true")
    refresh.add_argument("--expected-readme-sha256")
    resolve = sub.add_parser("resolve")
    _add_root(resolve)
    target = resolve.add_mutually_exclusive_group(required=True)
    target.add_argument("--reference")
    target.add_argument("--legacy-path")
    audit_parser = sub.add_parser("audit")
    _add_root(audit_parser)
    audit_mode = audit_parser.add_mutually_exclusive_group()
    audit_mode.add_argument("--output")
    audit_mode.add_argument("--verify-migration")
    migrate = sub.add_parser("migrate")
    _add_root(migrate)
    migrate_mode = migrate.add_mutually_exclusive_group(required=True)
    migrate_mode.add_argument("--reference")
    migrate_mode.add_argument("--inventory")
    migrate.add_argument("--incoming-links-inventory")
    migrate.add_argument("--apply-admitted", action="store_true")
    migrate.add_argument("--render-readme", action="store_true")
    migrate.add_argument("--byte-check", action="store_true")
    terminalize = sub.add_parser("terminalize-v1")
    _add_root(terminalize)
    terminalize.add_argument("--inventory", required=True)
    terminalize.add_argument("--terminal-at", required=True)
    terminalize.add_argument("--authorization-marker", required=True)
    terminalize.add_argument("--receipt", required=True)
    recovery = sub.add_parser("recover-partial-migration-v1")
    _add_root(recovery)
    recovery.add_argument("--inventory", required=True)
    recovery.add_argument("--expected-inventory-sha256", required=True)
    recovery.add_argument("--expected-readme-sha256", required=True)
    recovery.add_argument(
        "--target-status-preimage",
        action="append",
        required=True,
        help="Exact <reference>=<sha256> incident status preimage; repeat twice",
    )
    recovery.add_argument("--receipt", required=True)
    recovery.add_argument("--apply-admitted", action="store_true")
    recovery.add_argument("--render-readme", action="store_true")
    recovery.add_argument("--byte-check", action="store_true")
    normalize = sub.add_parser(
        "normalize-current-identity",
        help="Atomically replace one noncanonical current flat-record identity",
    )
    _add_root(normalize)
    normalize.add_argument("--category", required=True, help="Lifecycle category")
    normalize.add_argument(
        "--source",
        required=True,
        help="Repository-relative source path under work-items/",
    )
    normalize.add_argument(
        "--target-slug", required=True, help="Canonical replacement slug"
    )
    normalize.add_argument(
        "--inventory", required=True, help="Repository .scratch/ inventory path"
    )
    normalize.add_argument(
        "--receipt", help="Repository .scratch/ settled receipt path"
    )
    normalize.add_argument(
        "--prepare-only",
        action="store_true",
        help="Write the exact byte-bound inventory without mutating work-items",
    )
    normalize.add_argument(
        "--inject-failure-at",
        choices=("after-rewrites", "after-move", "after-readme"),
        help=argparse.SUPPRESS,
    )
    apply_legacy = sub.add_parser("migrate-legacy-ledger-obligation")
    _add_root(apply_legacy)
    apply_legacy.add_argument("--slug", required=True)
    apply_legacy.add_argument("--target-run-id", required=True)
    apply_legacy.add_argument("--target-event-sha256", required=True)
    apply_legacy.add_argument("--expected-ledger-sha256", required=True)
    apply_legacy.add_argument("--operation-id", required=True)
    apply_legacy.add_argument("--recorded-at", required=True)
    apply_legacy.add_argument(
        "--normalization-kind",
        choices=("invalid-finding-class", "remove-string-scratch-evidence"),
        default="invalid-finding-class",
    )
    apply_legacy.add_argument(
        "--inject-failure",
        choices=("after-anchor", "post-replace-corrupt"),
        help=argparse.SUPPRESS,
    )
    revoke_legacy = sub.add_parser("revoke-legacy-ledger-obligation")
    _add_root(revoke_legacy)
    revoke_legacy.add_argument("--slug", required=True)
    revoke_legacy.add_argument("--apply-run-id", required=True)
    revoke_legacy.add_argument("--apply-event-sha256", required=True)
    revoke_legacy.add_argument("--expected-ledger-sha256", required=True)
    revoke_legacy.add_argument("--operation-id", required=True)
    revoke_legacy.add_argument("--recorded-at", required=True)
    projection_apply = sub.add_parser("apply-legacy-ledger-projection")
    _add_root(projection_apply)
    projection_apply.add_argument("--manifest-file", required=True)
    projection_apply.add_argument("--manifest-entry-id", required=True)
    projection_apply.add_argument("--raw-line-ordinal", required=True, type=int)
    projection_apply.add_argument("--expected-registry-sha256", required=True)
    projection_apply.add_argument("--operation-id", required=True)
    projection_apply.add_argument("--recorded-at", required=True)
    projection_apply.add_argument("--dry-run", action="store_true")
    projection_revoke = sub.add_parser("revoke-legacy-ledger-projection")
    _add_root(projection_revoke)
    projection_revoke.add_argument("--apply-operation-id", required=True)
    projection_revoke.add_argument("--apply-record-sha256", required=True)
    projection_revoke.add_argument("--expected-registry-sha256", required=True)
    projection_revoke.add_argument("--operation-id", required=True)
    projection_revoke.add_argument("--recorded-at", required=True)
    projection_disposition = sub.add_parser("write-legacy-ledger-irrecoverable-disposition")
    _add_root(projection_disposition)
    projection_disposition.add_argument("--disposition-file", required=True)
    archive_successor = sub.add_parser("archive-with-successor")
    _add_root(archive_successor)
    archive_successor.add_argument("--slug", required=True)
    archive_successor.add_argument("--closure-file", required=True)
    archive_successor.add_argument("--terminal-instant", required=True)
    archive_successor.add_argument("--successor-slug", required=True)
    archive_successor.add_argument("--successor-file", required=True)
    archive_successor.add_argument("--operation-id", required=True)
    archive_successor.add_argument("--expected-ledger-sha256", required=True)
    archive_successor.add_argument("--expected-readme-sha256", required=True)
    archive_successor.add_argument(
        "--inject-failure-at", choices=tuple(f"T{i}" for i in range(10)), help=argparse.SUPPRESS
    )
    trial = sub.add_parser("trial")
    _add_root(trial)
    trial.add_argument("--fixture", required=True)
    return parser


def _emit_lifecycle_cleanup_diagnostics(
    observer: LifecycleDiagnosticObserver | None,
) -> None:
    if observer is None or observer.state != "delivered":
        return
    bundle = observer.snapshot
    if bundle is None or not bundle.cleanupFailures:
        return
    total = len(bundle.cleanupFailures)
    for index, record in enumerate(bundle.cleanupFailures, start=1):
        payload = {
            "causeType": record.causeType,
            "diagnostic": record.diagnostic,
            "failureId": record.failureId,
            "index": index,
            "phase": record.phase,
            "resource": record.resource,
            "total": total,
        }
        print(
            "CLEANUP-FAILURE: "
            + json.dumps(payload, sort_keys=True, separators=(",", ":"))
        )
    print(
        "CLEANUP-SUMMARY: "
        + json.dumps(
            {"count": total, "rollback": bundle.rollback},
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root)
    lifecycle_diagnostic_observer = None
    try:
        if args.command == "candidate":
            result = create_candidate(
                root,
                args.slug,
                _read_arg_file(args.file),
                inject_readme_failure=bool(args.inject_readme_failure),
            )
            print(result)
        elif args.command == "convert-legacy-candidate":
            result = convert_legacy_candidate(
                root,
                args.slug,
                _read_arg_file(args.file),
                inject_readme_failure=bool(args.inject_readme_failure),
            )
            print(result)
        elif args.command == "retire-legacy-backlog":
            result = retire_legacy_backlog(
                root,
                args.slug,
                _read_arg_file(args.disposition_file),
                args.terminal_instant,
                inject_readme_failure=bool(args.inject_readme_failure),
            )
            print(result)
        elif args.command == "start":
            result = start_item(
                root,
                args.slug,
                _read_arg_file(args.status_file),
                inject_readme_failure=bool(args.inject_readme_failure),
            )
            print(result)
        elif args.command == "update":
            result = update_status(
                root,
                args.slug,
                _read_arg_file(args.status_file),
                inject_readme_failure=bool(args.inject_readme_failure),
            )
            print(result)
        elif args.command == "close":
            result = close_item(
                root,
                args.slug,
                _read_arg_file(args.closure_file),
                args.terminal_instant,
                inject_readme_failure=bool(args.inject_readme_failure),
            )
            print(result)
        elif args.command == "reopen":
            result = reopen_item(
                root,
                args.slug,
                args.successor_slug,
                _read_arg_file(args.status_file),
                inject_readme_failure=bool(args.inject_readme_failure),
            )
            print(result)
        elif args.command == "refresh":
            if args.reset_static_guide:
                if not args.expected_readme_sha256:
                    raise LifecycleError(
                        "WI-README-REPAIR-TARGET-MISMATCH",
                        "--reset-static-guide requires --expected-readme-sha256",
                    )
                readme_hash = reset_readme_static_guide(
                    root,
                    args.expected_readme_sha256,
                )
            else:
                if args.expected_readme_sha256:
                    raise LifecycleError(
                        "WI-README-REPAIR-TARGET-MISMATCH",
                        "--expected-readme-sha256 requires --reset-static-guide",
                    )
                readme_hash = refresh_readme(root)
            print(f"README-SHA256: {readme_hash}")
        elif args.command == "resolve":
            if args.reference:
                print(resolve_category(root, args.reference))
            else:
                print(f"WI-LEGACY-READ-COMPAT {resolve_legacy_path(root, args.legacy_path)}")
        elif args.command == "audit":
            if args.output:
                inventory = write_migration_inventory(root, Path(args.output))
                print(f"migration_rows={len(inventory['rows'])}")
            elif args.verify_migration:
                rows = verify_migration_inventory(
                    root, Path(args.verify_migration)
                )
                print(f"migration_rows={rows}")
            else:
                for legacy_path in audit(root):
                    print(f"{LEGACY_READ_CLASSIFICATION} {legacy_path}")
            print("AUDIT: PASS")
        elif args.command == "migrate":
            if args.inventory:
                if not (
                    args.apply_admitted
                    and args.render_readme
                    and args.byte_check
                ):
                    raise LifecycleError(
                        "WI-CATEGORY-MIGRATION-INVENTORY",
                        "inventory migration requires --apply-admitted, "
                        "--render-readme, and --byte-check",
                    )
                rows, readme_hash = apply_migration_inventory(
                    root,
                    Path(args.inventory),
                    render_readme=args.render_readme,
                    byte_check=args.byte_check,
                )
                print("MIGRATION: PASS")
                print(f"migration_rows={rows}")
                print("readme_byte_check=PASS")
                print("source_target_disjoint=PASS")
                if readme_hash:
                    print(f"readme_sha256={readme_hash}")
            else:
                if args.apply_admitted or args.render_readme or args.byte_check:
                    raise LifecycleError(
                        "WI-CATEGORY-MIGRATION-INVENTORY",
                        "bulk migration flags require --inventory",
                    )
                migrate_legacy(
                    root,
                    args.reference,
                    incoming_links_inventory=(
                        Path(args.incoming_links_inventory)
                        if args.incoming_links_inventory
                        else None
                    ),
                )
        elif args.command == "terminalize-v1":
            rows, replay = terminalize_v1_inventory(
                root,
                Path(args.inventory),
                terminal_at=args.terminal_at,
                authorization_marker=args.authorization_marker,
                receipt_path=Path(args.receipt),
            )
            if replay:
                print(f"TERMINALIZE-V1: PASS rows={rows} replay=true")
            else:
                print(
                    f"TERMINALIZE-V1: PASS rows={rows} "
                    f"marker={args.authorization_marker}"
                )
        elif args.command == "recover-partial-migration-v1":
            lifecycle_diagnostic_observer = LifecycleDiagnosticObserver()
            result = recover_partial_migration_v1(
                root,
                Path(args.inventory),
                expected_inventory_sha256=args.expected_inventory_sha256,
                expected_readme_sha256=args.expected_readme_sha256,
                target_status_preimages=_parse_partial_recovery_status_bindings(
                    args.target_status_preimage
                ),
                receipt_path=Path(args.receipt),
                apply_admitted=args.apply_admitted,
                render_readme=args.render_readme,
                byte_check=args.byte_check,
                diagnostic_observer=lifecycle_diagnostic_observer,
            )
            print(
                "PARTIAL-MIGRATION-RECOVERY: PASS "
                f"receipt_sha256={result.receipt_sha256} "
                f"audit={result.audit}"
            )
        elif args.command == "normalize-current-identity":
            if args.prepare_only:
                if args.receipt:
                    raise LifecycleError(
                        "WI-IDENTITY-NORMALIZE-INVENTORY",
                        "--prepare-only does not accept --receipt",
                    )
                inventory = write_current_identity_normalization_inventory(
                    root,
                    args.category,
                    args.source,
                    args.target_slug,
                    Path(args.inventory),
                )
                print(f"NORMALIZE-CURRENT-IDENTITY: INVENTORY rows={len(inventory['rows'])}")
            else:
                if not args.receipt:
                    raise LifecycleError(
                        "WI-IDENTITY-NORMALIZE-INVENTORY",
                        "normalization apply requires --receipt",
                    )
                target, replay = normalize_current_identity(
                    root,
                    args.category,
                    args.source,
                    args.target_slug,
                    Path(args.inventory),
                    Path(args.receipt),
                    inject_failure_at=args.inject_failure_at,
                )
                print(
                    "NORMALIZE-CURRENT-IDENTITY: PASS "
                    f"target={target} replay={'true' if replay else 'false'}"
                )
        elif args.command == "migrate-legacy-ledger-obligation":
            result = migrate_legacy_ledger_obligation(
                root,
                args.slug,
                args.target_run_id,
                args.target_event_sha256,
                args.expected_ledger_sha256,
                args.operation_id,
                args.recorded_at,
                normalization_kind=args.normalization_kind,
                inject_failure=args.inject_failure,
            )
            print(
                "WI-LEDGER-MIGRATION-COMMITTED "
                f"operation={result['operationId']} after={result['afterLedgerSha256']}"
            )
        elif args.command == "revoke-legacy-ledger-obligation":
            result = revoke_legacy_ledger_obligation(
                root,
                args.slug,
                args.apply_run_id,
                args.apply_event_sha256,
                args.expected_ledger_sha256,
                args.operation_id,
                args.recorded_at,
            )
            print(
                "WI-LEDGER-MIGRATION-REVOKED "
                f"operation={result['operationId']} after={result['afterLedgerSha256']}"
            )
        elif args.command == "apply-legacy-ledger-projection":
            result = apply_legacy_ledger_projection(
                root, _read_arg_file(args.manifest_file), args.manifest_entry_id,
                args.raw_line_ordinal, args.expected_registry_sha256,
                args.operation_id, args.recorded_at, dry_run=args.dry_run,
            )
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        elif args.command == "revoke-legacy-ledger-projection":
            result = revoke_legacy_ledger_projection(
                root, args.apply_operation_id, _projection_cli_record_digests(args.apply_record_sha256),
                args.expected_registry_sha256, args.operation_id, args.recorded_at,
            )
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        elif args.command == "write-legacy-ledger-irrecoverable-disposition":
            result = write_legacy_ledger_irrecoverable_disposition(
                root, _read_arg_file(args.disposition_file),
            )
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        elif args.command == "archive-with-successor":
            result = archive_with_successor(
                root,
                args.slug,
                _read_arg_file(args.closure_file),
                args.terminal_instant,
                args.successor_slug,
                _read_arg_file(args.successor_file),
                args.operation_id,
                args.expected_ledger_sha256,
                args.expected_readme_sha256,
                inject_failure_at=args.inject_failure_at,
            )
            print(
                "WI-LIFECYCLE-TRANSITION-COMMITTED "
                f"operation={result['operationId']} readme={result['readmeSha256']}"
            )
        elif args.command == "trial":
            first, second = run_trial(root, Path(args.fixture))
            print("TRIAL: PASS")
            print("items=5")
            print(f"sections={'|'.join(README_SECTIONS)}")
            print(f"readme_sha256_1={first}")
            print(f"readme_sha256_2={second}")
        return 0
    except LifecycleError as exc:
        print(f"{exc.failure_id}: {exc}")
        _emit_lifecycle_cleanup_diagnostics(lifecycle_diagnostic_observer)
        return 1
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"WI-IO: {exc}")
        _emit_lifecycle_cleanup_diagnostics(lifecycle_diagnostic_observer)
        return 1
    except BaseException:
        _emit_lifecycle_cleanup_diagnostics(lifecycle_diagnostic_observer)
        raise


LIFECYCLE_PUBLIC_APIS = (
    "resolve_category",
    "work_item_dependency_state",
    "resolve_legacy_path",
    "collect_readme_entries",
    "render_readme_bytes",
    "refresh_readme",
    "reset_readme_static_guide",
    "check_readme",
    "create_candidate",
    "convert_legacy_candidate",
    "retire_legacy_backlog",
    "start_item",
    "update_status",
    "close_item",
    "reopen_item",
    "audit_categories",
    "audit",
    "write_current_identity_normalization_inventory",
    "normalize_current_identity",
    "migrate_legacy_ledger_obligation",
    "revoke_legacy_ledger_obligation",
    "archive_with_successor",
    "build_migration_inventory",
    "write_migration_inventory",
    "migrate_legacy",
    "terminalize_v1_inventory",
    "apply_migration_inventory",
    "recover_partial_migration_v1",
    "verify_migration_inventory",
    "reopen_category_record",
    "run_trial",
)
for _lifecycle_api_name in LIFECYCLE_PUBLIC_APIS:
    globals()[_lifecycle_api_name] = _lifecycle_participant(
        globals()[_lifecycle_api_name]
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
