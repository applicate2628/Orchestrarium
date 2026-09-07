"""Operator effort floor is stricter than provider-supported effort values."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src.codex" / "skills" / "astra-routing" / "scripts" / "resolve.py"


def load():
    spec = importlib.util.spec_from_file_location("astra_effort_floor_test", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("evidence", [None, "migration-evaluation", "measured-sufficient"])
@pytest.mark.parametrize("task,evidence_kind", [
    ("mathematical-research", "mathematics-quality-floor"),
    ("scientific-agentic-workflow", "connected-science-workflow"),
    ("cross-system-synthesis", "cross-system-context-retention"),
    ("critical-recovery", "verified-frontier-recovery"),
])
def test_low_cannot_be_admitted_by_downshift_evidence(task, evidence_kind, evidence):
    result = load().resolve_v1_astra_route(
        task_class=task, available_models=("gpt-6-astra",),
        route_evidence=evidence_kind, requested_effort="low", effort_evidence=evidence,
    )
    assert result["status"] == "denied"
    assert result["stableId"] == "E_ASTRA_V1_EFFORT_BELOW_MINIMUM"
    assert result["effort"] is None
    assert result["codexFlags"] == []
    assert result["executionAuthorized"] is False


@pytest.mark.parametrize("effort,evidence,approval", [
    (None, None, False), ("medium", None, False),
    ("high", "measured-high-gain", False),
    ("xhigh", "measured-xhigh-gain", False),
    ("max", None, True),
])
def test_admitted_efforts_do_not_require_pointless_lower_effort_failures(effort, evidence, approval):
    result = load().resolve_v1_astra_route(
        task_class="mathematical-research", available_models=("gpt-6-astra",),
        route_evidence="mathematics-quality-floor", requested_effort=effort,
        effort_evidence=evidence, allow_max_effort=approval,
    )
    assert result["status"] == "selected"
    assert result["effort"] == (effort or "medium")
    assert result["executionAuthorized"] is False


def test_recovery_may_downshift_to_medium_but_not_below_the_floor():
    result = load().resolve_v1_astra_route(
        task_class="critical-recovery", available_models=("gpt-6-astra",),
        route_evidence="verified-frontier-recovery", requested_effort="medium",
        effort_evidence="measured-sufficient",
    )
    assert result["status"] == "selected"
    assert result["effort"] == "medium"


def test_cli_low_fails_without_launch_flags():
    result = subprocess.run([
        sys.executable, "-S", str(MODULE), "--task-class", "mathematical-research",
        "--available-model", "gpt-6-astra", "--route-evidence", "mathematics-quality-floor",
        "--effort", "low", "--effort-evidence", "migration-evaluation",
    ], capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["stableId"] == "E_ASTRA_V1_EFFORT_BELOW_MINIMUM"
    assert payload["codexFlags"] == []
    assert result.stderr == ""
