#!/usr/bin/env python3
"""Synthetic child behaviors for process-supervision runtime tests."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _write_all(stream, payload: bytes) -> None:
    view = memoryview(payload)
    offset = 0
    while offset < len(view):
        written = stream.write(view[offset:])
        if written is None:
            written = len(view) - offset
        if written <= 0:
            raise RuntimeError("fixture write made no progress")
        offset += written
    stream.flush()


def _publish_marker_atomic(marker: str | Path, content: str) -> None:
    """Publish complete UTF-8 marker content with one same-directory replace."""

    target = Path(marker)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
        os.replace(temporary, target)
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode")
    parser.add_argument("--marker")
    parser.add_argument("--bytes", type=int, default=0)
    parser.add_argument("--sleep", type=float, default=0.0)
    parser.add_argument("--exit-code", type=int, default=0)
    parser.add_argument("--token", default="")
    args, extra = parser.parse_known_args()

    if args.mode == "argv-json":
        _write_all(sys.stdout.buffer, json.dumps(extra, ensure_ascii=False).encode("utf-8"))
    elif args.mode == "echo-stdin":
        _write_all(sys.stdout.buffer, sys.stdin.buffer.read())
    elif args.mode == "emit":
        _write_all(sys.stdout.buffer, b"O" * args.bytes)
        _write_all(sys.stderr.buffer, b"E" * args.bytes)
    elif args.mode == "marker":
        if args.marker is None:
            return 2
        token = str(os.getpid()) if args.token == "PID" else (args.token or "started")
        _publish_marker_atomic(args.marker, token)
        if args.sleep:
            time.sleep(args.sleep)
    elif args.mode == "infinite-writer":
        chunk = (args.token or "bounded-writer").encode("utf-8") * 4096
        while True:
            _write_all(sys.stdout.buffer, chunk)
    elif args.mode == "grandchild-retains-pipe":
        if args.marker is None:
            return 2
        grandchild = subprocess.Popen(
            [
                sys.executable,
                __file__,
                "marker",
                "--marker",
                args.marker,
                "--token",
                args.token or "PID",
                "--sleep",
                str(max(args.sleep, 30.0)),
            ],
            stdin=subprocess.DEVNULL,
            stdout=sys.stdout,
            stderr=sys.stderr,
            close_fds=False,
        )
        _publish_marker_atomic(args.marker, str(grandchild.pid))
    elif args.mode == "tree-hold-writer":
        if args.marker is None:
            return 2
        grandchild_marker = str(Path(args.marker).with_suffix(".grandchild"))
        child = subprocess.Popen(
            [
                sys.executable,
                __file__,
                "marker",
                "--marker",
                grandchild_marker,
                "--token",
                "PID",
                "--sleep",
                "60",
            ],
            stdin=subprocess.DEVNULL,
            stdout=sys.stdout,
            stderr=sys.stderr,
            close_fds=False,
        )
        _publish_marker_atomic(
            args.marker,
            json.dumps({"directPid": os.getpid(), "grandchildPid": child.pid}),
        )
        chunk = b"tree-last-close" * 4096
        while True:
            _write_all(sys.stdout.buffer, chunk)
    elif args.mode == "sleep":
        time.sleep(args.sleep)
    elif args.mode == "close-stdin":
        os.close(0)
        time.sleep(args.sleep)
    elif args.mode == "identity":
        _write_all(
            sys.stdout.buffer,
            json.dumps({"pid": os.getpid(), "ppid": os.getppid()}).encode("ascii"),
        )
    elif args.mode == "check-handle" and os.name == "nt":
        import ctypes

        handle = int(args.token)
        flags = ctypes.c_ulong()
        inherited = bool(ctypes.windll.kernel32.GetHandleInformation(handle, ctypes.byref(flags)))
        _write_all(sys.stdout.buffer, b"inherited" if inherited else b"not-inherited")
    else:
        return 2
    return args.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
