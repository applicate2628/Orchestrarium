#!/usr/bin/env python3
"""Fixed-sibling staged-loading entry point for the publication gate."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import stat
import sys
from pathlib import Path


_COMMON_NAME = "hook_common"
_COMMON_FILENAME = "hook_common.py"
_PREFLIGHT_NAME = "git_push_gate_preflight"
_PREFLIGHT_FILENAME = "git_push_gate_preflight.py"
_POLICY_NAME = "_orchestrarium_git_push_gate_policy"
_POLICY_FILENAME = "check-git-push-gate.py"
_FAILURE_PAYLOAD = {
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": (
            "PRG-RUNNER-UNAVAILABLE: Git-push publication gate could not load "
            "its fixed policy module. Reinstall the current pack and verify "
            "hook health before retrying publication."
        ),
    }
}


def _is_reparse(path: Path) -> bool:
    if path.is_symlink() or (
        hasattr(os.path, "isjunction") and os.path.isjunction(path)
    ):
        return True
    try:
        attributes = path.lstat().st_file_attributes
    except (AttributeError, OSError):
        return False
    marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
    return bool(attributes & marker)


def _load_fixed_sibling(runner: Path, filename: str, module_name: str):
    target = runner.parent / filename
    if _is_reparse(target) or not target.is_file():
        raise RuntimeError("module target is not a regular direct sibling")
    resolved = target.resolve(strict=True)
    if resolved.parent != runner.parent:
        raise RuntimeError("module target escaped the runner directory")

    spec = importlib.util.spec_from_file_location(module_name, resolved)
    if spec is None or spec.loader is None:
        raise RuntimeError("fixed sibling module has no loader")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


def _load_preflight():
    runner = Path(__file__).resolve(strict=True)

    # The policy cache is either the standard fixed sibling __pycache__ or no
    # cache at all. A caller-provided PYTHONPYCACHEPREFIX must not redirect the
    # publication policy to a second ambient bytecode location.
    sys.pycache_prefix = None
    _load_fixed_sibling(runner, _COMMON_FILENAME, _COMMON_NAME)
    return runner, _load_fixed_sibling(
        runner, _PREFLIGHT_FILENAME, _PREFLIGHT_NAME
    )


def _load_policy(runner: Path):
    return _load_fixed_sibling(runner, _POLICY_FILENAME, _POLICY_NAME)


def main() -> int:
    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(
            captured_stderr
        ):
            runner, preflight = _load_preflight()
            decision = preflight.validate_preflight_result(
                preflight.build_preflight_from_stdin()
            )
            if decision.outcome == "ALLOW_FINAL":
                result = 0
            else:
                policy = _load_policy(runner)
                result = policy.main(decision)
            if type(result) is not int:
                raise TypeError("policy main returned a non-integer result")
    except BaseException:
        sys.modules.pop(_POLICY_NAME, None)
        sys.modules.pop(_PREFLIGHT_NAME, None)
        print(json.dumps(_FAILURE_PAYLOAD))
        return 0

    sys.stdout.write(captured_stdout.getvalue())
    sys.stderr.write(captured_stderr.getvalue())
    return result


if __name__ == "__main__":
    raise SystemExit(main())
