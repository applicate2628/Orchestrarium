#!/usr/bin/env python3
"""Bounded ownership and settlement for one private POSIX process group."""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
import math
import os
import signal
import subprocess
import sys
import threading
import time
from typing import Any


_LINUX_SUBREAPER_LOCK = threading.Lock()
_PR_SET_CHILD_SUBREAPER = 36
_PR_GET_CHILD_SUBREAPER = 37
_GRACEFUL_SETTLEMENT_SECONDS = 0.25
_DEFAULT_CLOSE_SECONDS = 5.0
POSIX_PROCESS_GROUP_MODULE_CONTRACT_V1 = (
    "orchestrarium.posix-process-group.module.v1"
)


class PosixProcessGroupError(RuntimeError):
    """Typed failure returned to a composition root for fail-closed mapping."""

    def __init__(self, failure_id: str, stage: str) -> None:
        super().__init__(f"{failure_id}: {stage}")
        self.failure_id = failure_id
        self.stage = stage


@dataclass(frozen=True)
class PosixProcessGroupClosureV1:
    """Observed terminal facts for one POSIX process-group ownership interval."""

    process_group: int | None
    group_was_present: bool
    group_absent: bool
    reaped_pids: tuple[int, ...]
    term_sent: bool
    kill_sent: bool
    prior_child_subreaper: int | None
    child_subreaper_restored: bool
    lock_released: bool

    @property
    def complete(self) -> bool:
        return (
            self.group_absent
            and self.child_subreaper_restored
            and self.lock_released
        )


class PosixProcessGroupOwnerV1:
    """Own one private POSIX group from pre-spawn acquisition through cleanup."""

    def __init__(self) -> None:
        self._linux = sys.platform.startswith("linux")
        self._lock_held = False
        self._libc: Any | None = None
        self._prior_child_subreaper: int | None = None
        self._process_group: int | None = None
        self._closure: PosixProcessGroupClosureV1 | None = None

    @classmethod
    def acquire(cls) -> "PosixProcessGroupOwnerV1":
        if os.name == "nt":
            raise PosixProcessGroupError(
                "POSIX-PROCESS-GROUP-UNAVAILABLE", "acquire"
            )
        owner = cls()
        if not owner._linux:
            return owner
        _LINUX_SUBREAPER_LOCK.acquire()
        owner._lock_held = True
        try:
            libc = ctypes.CDLL(None, use_errno=True)
            prctl = libc.prctl
            prctl.restype = ctypes.c_int
            prior = ctypes.c_int()
            if prctl(
                _PR_GET_CHILD_SUBREAPER, ctypes.byref(prior), 0, 0, 0
            ) != 0:
                raise OSError(ctypes.get_errno(), "PR_GET_CHILD_SUBREAPER")
            owner._libc = libc
            owner._prior_child_subreaper = int(prior.value)
            if prctl(_PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) != 0:
                raise OSError(ctypes.get_errno(), "PR_SET_CHILD_SUBREAPER")
        except BaseException as exc:
            try:
                owner._restore_and_release()
            except PosixProcessGroupError:
                pass
            if isinstance(exc, (AttributeError, OSError)):
                raise PosixProcessGroupError(
                    "POSIX-SUBREAPER-UNAVAILABLE", "acquire"
                ) from exc
            raise
        return owner

    @property
    def popen_kwargs(self) -> dict[str, object]:
        if self._closure is not None:
            raise PosixProcessGroupError(
                "POSIX-PROCESS-GROUP-CLOSED", "spawn"
            )
        return {"start_new_session": True}

    def bind_process_group(self, process_group: int) -> None:
        if self._closure is not None or self._process_group is not None:
            raise PosixProcessGroupError(
                "POSIX-PROCESS-GROUP-STATE", "bind"
            )
        if not isinstance(process_group, int) or isinstance(process_group, bool) or process_group <= 0:
            raise PosixProcessGroupError(
                "POSIX-PROCESS-GROUP-INVALID", "bind"
            )
        self._process_group = process_group

    @staticmethod
    def _group_exists(process_group: int) -> bool:
        try:
            os.killpg(process_group, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError as exc:
            raise PosixProcessGroupError(
                "POSIX-PROCESS-GROUP-PROBE", "settlement"
            ) from exc
        return True

    def _reap_group(
        self,
        process_group: int,
        reaped: list[int],
        direct_process: Any | None,
        deadline: float,
    ) -> None:
        if not self._linux or not self._poll_direct(direct_process):
            return
        while True:
            if time.monotonic() >= deadline:
                raise PosixProcessGroupError(
                    "POSIX-PROCESS-GROUP-REAP", "settlement"
                )
            try:
                reaped_pid, _status = os.waitpid(-process_group, os.WNOHANG)
                if reaped_pid == 0:
                    return
                reaped.append(reaped_pid)
            except ChildProcessError:
                return
            except InterruptedError:
                continue
            except OSError as exc:
                raise PosixProcessGroupError(
                    "POSIX-PROCESS-GROUP-REAP", "settlement"
                ) from exc

    @staticmethod
    def _poll_direct(direct_process: Any | None) -> bool:
        return direct_process is not None and direct_process.poll() is not None

    @staticmethod
    def _wait_direct_step(direct_process: Any | None, deadline: float) -> bool:
        if direct_process is None:
            return False
        if direct_process.poll() is not None:
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        try:
            direct_process.wait(timeout=max(0.001, min(0.05, remaining)))
        except subprocess.TimeoutExpired:
            return False
        except ChildProcessError:
            return direct_process.poll() is not None
        return direct_process.poll() is not None

    @staticmethod
    def _signal_group(process_group: int, signum: int) -> bool:
        try:
            os.killpg(process_group, signum)
        except ProcessLookupError:
            return False
        except OSError as exc:
            raise PosixProcessGroupError(
                "POSIX-PROCESS-GROUP-SIGNAL", "settlement"
            ) from exc
        return True

    def settle(
        self,
        timeout_seconds: float,
        *,
        direct_process: Any | None = None,
    ) -> PosixProcessGroupClosureV1:
        if self._closure is not None:
            return self._closure
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            error = PosixProcessGroupError(
                "POSIX-PROCESS-GROUP-BUDGET", "settlement"
            )
            if self._process_group is None:
                self.close()
            else:
                self.settle(_DEFAULT_CLOSE_SECONDS, direct_process=direct_process)
            raise error
        process_group = self._process_group
        if process_group is None:
            return self.close()

        deadline = time.monotonic() + float(timeout_seconds)
        reaped: list[int] = []
        term_sent = False
        kill_sent = False
        group_was_present = False
        group_absent = False
        pending_error: BaseException | None = None
        try:
            group_was_present = self._group_exists(process_group)
            self._reap_group(process_group, reaped, direct_process, deadline)
            if self._group_exists(process_group):
                term_sent = self._signal_group(process_group, signal.SIGTERM)
            graceful_deadline = min(
                deadline, time.monotonic() + _GRACEFUL_SETTLEMENT_SECONDS
            )
            while time.monotonic() < graceful_deadline:
                self._wait_direct_step(direct_process, graceful_deadline)
                self._reap_group(
                    process_group, reaped, direct_process, deadline
                )
                if not self._group_exists(process_group):
                    group_absent = self._poll_direct(direct_process)
                    if group_absent:
                        break
                time.sleep(0.01)
            if not group_absent and self._group_exists(process_group):
                kill_sent = self._signal_group(process_group, signal.SIGKILL)
            while not group_absent and time.monotonic() < deadline:
                self._wait_direct_step(direct_process, deadline)
                self._reap_group(
                    process_group, reaped, direct_process, deadline
                )
                group_absent = (
                    not self._group_exists(process_group)
                    and self._poll_direct(direct_process)
                )
                if not group_absent:
                    time.sleep(0.01)
            self._reap_group(process_group, reaped, direct_process, deadline)
            group_absent = (
                not self._group_exists(process_group)
                and self._poll_direct(direct_process)
            )
        except BaseException as exc:
            pending_error = exc

        restored = False
        try:
            restored = self._restore_and_release()
        except PosixProcessGroupError as exc:
            if pending_error is None:
                pending_error = exc
        self._closure = PosixProcessGroupClosureV1(
            process_group=process_group,
            group_was_present=group_was_present,
            group_absent=group_absent,
            reaped_pids=tuple(reaped),
            term_sent=term_sent,
            kill_sent=kill_sent,
            prior_child_subreaper=self._prior_child_subreaper,
            child_subreaper_restored=restored,
            lock_released=not self._lock_held,
        )
        if pending_error is not None:
            raise pending_error
        return self._closure

    def _restore_and_release(self) -> bool:
        restored = True
        try:
            if self._linux and self._libc is not None:
                assert self._prior_child_subreaper is not None
                if self._libc.prctl(
                    _PR_SET_CHILD_SUBREAPER,
                    self._prior_child_subreaper,
                    0,
                    0,
                    0,
                ) != 0:
                    restored = False
                    raise PosixProcessGroupError(
                        "POSIX-SUBREAPER-RESTORE", "close"
                    )
        finally:
            self._libc = None
            if self._lock_held:
                self._lock_held = False
                _LINUX_SUBREAPER_LOCK.release()
        return restored

    def close(self) -> PosixProcessGroupClosureV1:
        if self._closure is not None:
            return self._closure
        if self._process_group is not None:
            return self.settle(_DEFAULT_CLOSE_SECONDS)
        restored = self._restore_and_release()
        self._closure = PosixProcessGroupClosureV1(
            process_group=None,
            group_was_present=False,
            group_absent=True,
            reaped_pids=(),
            term_sent=False,
            kill_sent=False,
            prior_child_subreaper=self._prior_child_subreaper,
            child_subreaper_restored=restored,
            lock_released=not self._lock_held,
        )
        return self._closure


def posix_process_group_module_contract_v1() -> tuple[str, type, type]:
    """Return the stable in-process identity contract for equivalent copies."""

    return (
        POSIX_PROCESS_GROUP_MODULE_CONTRACT_V1,
        PosixProcessGroupOwnerV1,
        PosixProcessGroupError,
    )


__all__ = [
    "PosixProcessGroupClosureV1",
    "PosixProcessGroupError",
    "PosixProcessGroupOwnerV1",
]
