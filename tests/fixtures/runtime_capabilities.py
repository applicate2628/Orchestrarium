"""Explicit runtime capabilities shared by integration-test consumers."""
from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

import pytest


requires_windows_process_runner = pytest.mark.skipif(
    os.name != "nt",
    reason="requires the Windows ProcessRunnerV1 runtime",
)
requires_windows_kimi = pytest.mark.skipif(
    os.name != "nt",
    reason="requires the Windows Kimi transport runtime",
)


def codex_hook_host_env(
    base_env: Mapping[str, str], repo_root: str | os.PathLike[str]
) -> dict[str, str]:
    """Return an isolated environment bound to the deterministic Codex host."""

    environment = dict(base_env)
    fixture = (
        Path(repo_root).resolve()
        / "tests"
        / "fixtures"
        / "fake_codex_hooks_host.py"
    )
    environment["CODEX_BIN"] = str(fixture)
    return environment
