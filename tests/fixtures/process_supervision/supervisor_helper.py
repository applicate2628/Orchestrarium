#!/usr/bin/env python3
"""Run one long-lived synthetic child under ProcessRunnerV1."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("runner", type=Path)
    parser.add_argument("child", type=Path)
    parser.add_argument("marker", type=Path)
    parser.add_argument("cwd", type=Path)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("parent_death_process_runner", args.runner)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    executable = Path(sys.executable).resolve()
    argv = (
        sys.executable,
        str(args.child),
        "marker",
        "--marker",
        str(args.marker),
        "--token",
        "PID",
        "--sleep",
        "60",
    )
    environment = tuple(
        module.EnvironmentRowV1(name, os.environ[name])
        for name in ("PATH", "SYSTEMROOT", "TEMP", "TMP")
        if name in os.environ
    )
    policy = module.CapturePolicyV1(
        "parent-death-probe-v1",
        1024 * 1024,
        64 * 1024,
        128 * 1024,
        64 * 1024,
    )
    request = module.ProcessRequestV1(
        1,
        argv,
        executable,
        str(args.cwd),
        environment,
        None,
        time.monotonic() + 120,
        policy,
        module.ProcessRunnerV1().mint_memory_capture_sink(),
        module.SettlePolicyV1(5.0),
        windows_argv_profile_id="python-validator-json-echo-v1",
    )
    result = module.ProcessRunnerV1().run(request)
    return 0 if result.outcome == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
