#!/usr/bin/env python3
"""One-shot active completion watcher for an external provider dispatch.

The watcher preserves the established terminal protocol:

* ``0`` DONE
* ``69`` DEAD
* ``75`` STALL
* ``77`` FILTERED
* ``124`` TIMEOUT
* ``2`` usage error

Both POSIX-style long options and the retired PowerShell entrypoint's exact
``-Out``/``-Err`` spellings are accepted during migration.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
import time
from pathlib import Path

FILTER_TAIL_BYTES = 8192
STILL_ACTIVE = 259


class UsageParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(2, f"FAIL: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = UsageParser(
        usage=(
            "%(prog)s --out <out-path> [--err <err-path>] "
            "[--lastmsg <lastmsg-path>] [--commit-base <sha>] "
            "[--pid-file <path>] [--stall-secs <seconds>] "
            "[--max-secs <seconds>] [--poll-secs <seconds>]"
        )
    )
    parser.add_argument("--out", "-Out", required=True)
    parser.add_argument("--err", "-Err")
    parser.add_argument("--lastmsg", "-LastMsg")
    parser.add_argument("--commit-base", "-CommitBase")
    parser.add_argument("--pid-file", "-PidFile")
    parser.add_argument("--stall-secs", "-StallSecs", type=int, default=2700)
    parser.add_argument("--max-secs", "-MaxSecs", type=int, default=3600)
    parser.add_argument("--poll-secs", "-PollSecs", type=float, default=25.0)
    return parser


def file_bytes(path: str | None) -> int:
    if not path:
        return 0
    try:
        candidate = Path(path)
        return candidate.stat().st_size if candidate.is_file() else 0
    except OSError:
        return 0


def current_head() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            check=False,
            text=True,
        )
        return completed.stdout.strip() if completed.returncode == 0 else ""
    except OSError:
        return ""


def contains_filter_marker(path: str | None) -> bool:
    if not path:
        return False
    try:
        with Path(path).open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(max(0, size - FILTER_TAIL_BYTES), os.SEEK_SET)
            tail = stream.read(FILTER_TAIL_BYTES).decode("utf-8", errors="replace")
    except OSError:
        return False
    lowered = tail.lower()
    return "flag" in lowered and "cybersecurit" in lowered


def _posix_start_marker(pid: int) -> str | None:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return None
    close = raw.rfind(") ")
    if close < 0:
        return None
    fields = raw[close + 2 :].split()
    return fields[19] if len(fields) >= 20 else None


def _windows_process_state(pid: int) -> tuple[str, str | None]:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    process_query_limited_information = 0x1000
    synchronize = 0x00100000
    handle = kernel32.OpenProcess(
        process_query_limited_information | synchronize, False, pid
    )
    if not handle:
        error = ctypes.get_last_error()
        if error in {5}:  # Access denied proves existence but not inspectability.
            return "alive", None
        return "dead", None
    try:
        exit_code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return "alive", None
        if exit_code.value != STILL_ACTIVE:
            return "dead", None

        creation = ctypes.c_ulonglong()
        exit_time = ctypes.c_ulonglong()
        kernel = ctypes.c_ulonglong()
        user = ctypes.c_ulonglong()
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            return "alive", None
        return "alive", str(creation.value)
    finally:
        kernel32.CloseHandle(handle)


def process_state(pid: int) -> tuple[str, str | None]:
    if os.name == "nt":
        return _windows_process_state(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return "dead", None
    except PermissionError:
        return "alive", None
    except OSError:
        return "dead", None
    return "alive", _posix_start_marker(pid)


def pid_file_status(path: str | None) -> str:
    if not path:
        return "unknown"
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return "unknown"
    pid: int | None = None
    expected_start: str | None = None
    for line in lines:
        if line.startswith("pid=") and line[4:].isdigit():
            pid = int(line[4:])
        elif line.startswith("start="):
            expected_start = line[6:]
    if pid is None:
        return "unknown"
    state, actual_start = process_state(pid)
    if state == "dead":
        return "dead"
    if expected_start and actual_start and expected_start != actual_start:
        return "dead"
    return "alive"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.stall_secs < 0 or args.max_secs < 0 or args.poll_secs < 0:
        print("FAIL: timing values must be non-negative", file=sys.stderr)
        return 2

    started = time.monotonic()
    while True:
        lastmsg_size = file_bytes(args.lastmsg)
        if lastmsg_size:
            print(f"DONE lastmsg={lastmsg_size}")
            return 0

        out_size = file_bytes(args.out)
        if out_size:
            print(f"DONE out={out_size}")
            return 0

        if args.commit_base:
            head = current_head()
            if head and head != args.commit_base:
                print(f"DONE committed={head}")
                return 0

        if args.err and contains_filter_marker(args.err):
            print(
                f"FILTERED err={args.err} "
                "reason=provider-cybersecurity-content-filter "
                "action=redispatch-different-model-do-not-reword"
            )
            return 77

        if args.pid_file and pid_file_status(args.pid_file) == "dead":
            print(f"DEAD pid-file={args.pid_file}")
            return 69

        if args.err:
            try:
                err_path = Path(args.err)
                if err_path.is_file():
                    idle = int(time.time() - err_path.stat().st_mtime)
                    if idle > args.stall_secs:
                        print(f"STALL err-idle={idle}")
                        return 75
            except OSError:
                pass

        if int(time.monotonic() - started) >= args.max_secs:
            print(f"TIMEOUT max={args.max_secs}")
            return 124

        time.sleep(max(0.001, args.poll_secs))


if __name__ == "__main__":
    raise SystemExit(main())
