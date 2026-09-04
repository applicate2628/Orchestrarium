from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "model_routing" / "resolve_v2.py"
CATALOG = ROOT / "shared" / "model-catalog.v2.json"
POLICY = ROOT / "shared" / "role-routing-policy.v2.json"


def _load():
    spec = importlib.util.spec_from_file_location("model_routing_v2_test", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _contracts():
    return json.loads(CATALOG.read_text()), json.loads(POLICY.read_text())


def _request(**overrides):
    value = {
        "schemaVersion": 2,
        "mode": "policy-default",
        "taskClass": "mathematical-research",
        "role": "algorithm-scientist",
        "availability": {"terra": "available", "sol": "available", "astra": "available"},
        "requestedProfile": None,
        "routeEvidence": None,
        "effortEvidence": None,
        "allowMaxEffort": False,
        "allowCriticalAstra": False,
        "requestedFanout": 1,
        "objective": None,
        "routeEstimates": None,
        "asOf": "2026-09-04",
    }
    value.update(overrides)
    return value


def _call(
    profile: str,
    *,
    stage: str = "primary",
    task: str = "mathematical-research",
    role: str = "algorithm-scientist",
    uncached: int = 1000,
    cached: int = 0,
    cache_write: int = 0,
    output: int = 100,
    tools: int = 0,
    elapsed: int = 1000,
):
    return {
        "stage": stage,
        "taskClass": task,
        "role": role,
        "profile": profile,
        "uncachedInputTokens": uncached,
        "cachedInputTokens": cached,
        "cacheWriteTokens": cache_write,
        "outputTokens": output,
        "toolCostNanoUsd": tools,
        "elapsedMs": elapsed,
    }


def _estimate(
    profile: str,
    *,
    primary_call=None,
    review_profile: str = "terra-high",
    review_role: str = "qa-engineer",
    extra_calls=None,
    steps: int = 2,
    wall_time: int = 2000,
    rework: int = 0,
    attempted: int = 1,
    accepted: int = 1,
    quality: bool = True,
    comparison: str = "same-comparison",
    corpus: str = "same-corpus",
):
    calls = [primary_call or _call(profile)]
    calls.extend(extra_calls or [])
    calls.append(
        _call(
            review_profile,
            stage="review",
            task="review",
            role=review_role,
            uncached=100,
            output=20,
            elapsed=500,
        )
    )
    return {
        "qualityFloorSatisfied": quality,
        "measurement": {
            "comparisonId": comparison,
            "corpusId": corpus,
            "observedAt": "2026-09-04",
            "attempted": attempted,
            "accepted": accepted,
        },
        "coordinationSteps": max(steps, len(calls)),
        "wallTimeMs": wall_time,
        "reworkCycles": rework,
        "calls": calls,
    }


def _resolve(request, *, catalog=None, policy=None):
    module = _load()
    if catalog is None or policy is None:
        catalog, policy = _contracts()
    return module.resolve_model_route(request, catalog=catalog, policy=policy)
