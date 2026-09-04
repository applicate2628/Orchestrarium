#!/usr/bin/env python3
"""Resolve the narrow Orchestrarium 1.x Astra route without launching it."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Collection
from typing import Any

ASTRA_MODEL = "gpt-6-astra"
EFFORTS = ("low", "medium", "high", "xhigh", "max")
EFFORT_RANK = {name: rank for rank, name in enumerate(EFFORTS)}
TASK_DEFAULTS = {
    "mathematical-research": "medium",
    "scientific-agentic-workflow": "medium",
    "cross-system-synthesis": "medium",
    "critical-recovery": "high",
}
DOWNSHIFT_EVIDENCE = {"migration-evaluation", "measured-sufficient"}
UPSHIFT_EVIDENCE = {
    "high": {"medium-objective-failure", "measured-high-gain"},
    "xhigh": {
        "high-objective-failure",
        "high-contradictory",
        "measured-xhigh-gain",
    },
}
KNOWN_EVIDENCE = DOWNSHIFT_EVIDENCE | set().union(*UPSHIFT_EVIDENCE.values())
MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}\Z", re.ASCII)


def _decision(
    status: str,
    stable_id: str | None,
    task_class: str,
    *,
    effort: str | None = None,
    selection_basis: str,
    effort_basis: str | None = None,
    effort_evidence: str | None = None,
) -> dict[str, Any]:
    selected = status == "selected"
    return {
        "schemaVersion": 1,
        "status": status,
        "stableId": stable_id,
        "taskClass": task_class,
        "routeClass": "explicit-astra-v1",
        "model": ASTRA_MODEL if selected else None,
        "providerFamily": "openai" if selected else None,
        "effort": effort if selected else None,
        "codexFlags": (
            ["--model", ASTRA_MODEL, "-c", f"model_reasoning_effort={effort}"]
            if selected
            else []
        ),
        "selectionBasis": selection_basis,
        "effortBasis": effort_basis if selected else None,
        "effortEvidence": effort_evidence if selected else None,
        "economicsObjective": "expected-cost-and-steps-to-accepted-result",
        "economicsEvidence": (
            "caller-measured"
            if selected and effort_evidence and effort_evidence.startswith("measured-")
            else "migration-evaluation"
            if selected and effort_evidence == "migration-evaluation"
            else "objective-insufficiency"
            if selected and effort_evidence
            else "policy-default"
            if selected
            else "not-evaluated"
        ),
        "fallback": "none",
        "automaticFanoutLimit": 1,
        "requiresIndependentReview": selected,
        "authorizing": False,
    }


def _valid_models(value: Any) -> bool:
    if isinstance(value, (str, bytes)) or not isinstance(value, Collection):
        return False
    try:
        items = list(value)
    except (TypeError, ValueError):
        return False
    return len(items) <= 128 and all(
        isinstance(item, str) and MODEL_ID.fullmatch(item) for item in items
    )


def _effort_basis(
    default: str,
    requested: str | None,
    evidence: str | None,
    max_approved: bool,
) -> tuple[str | None, str | None]:
    effort = requested or default
    if effort not in EFFORTS:
        return "E_ASTRA_V1_EFFORT_UNSUPPORTED", None
    if evidence is not None and evidence not in KNOWN_EVIDENCE:
        return "E_ASTRA_V1_EFFORT_EVIDENCE_INVALID", None
    if requested is None:
        return (
            ("E_ASTRA_V1_EFFORT_EVIDENCE_INVALID", None)
            if evidence is not None
            else (None, f"task-default-{default}")
        )
    if effort == "max":
        if evidence is not None:
            return "E_ASTRA_V1_EFFORT_EVIDENCE_INVALID", None
        return (
            (None, "explicit-human-approval")
            if max_approved
            else ("E_ASTRA_V1_MAX_APPROVAL_REQUIRED", None)
        )
    if effort == default:
        return (
            ("E_ASTRA_V1_EFFORT_EVIDENCE_INVALID", None)
            if evidence is not None
            else (None, f"explicit-default-{effort}")
        )
    if EFFORT_RANK[effort] < EFFORT_RANK[default]:
        allowed = DOWNSHIFT_EVIDENCE
    else:
        allowed = UPSHIFT_EVIDENCE.get(effort, set())
    return (
        (None, evidence)
        if evidence in allowed
        else ("E_ASTRA_V1_EFFORT_EVIDENCE_REQUIRED", None)
    )


def resolve_v1_astra_route(
    *,
    task_class: str,
    available_models: Collection[str],
    requested_effort: str | None = None,
    effort_evidence: str | None = None,
    allow_max_effort: bool = False,
    requested_fanout: int = 1,
) -> dict[str, Any]:
    """Return one nonauthorizing Astra route or a typed non-success decision."""

    valid = (
        isinstance(task_class, str)
        and 0 < len(task_class) <= 128
        and "\x00" not in task_class
        and _valid_models(available_models)
        and (
            requested_effort is None
            or isinstance(requested_effort, str)
            and 0 < len(requested_effort) <= 32
            and "\x00" not in requested_effort
        )
        and (
            effort_evidence is None
            or isinstance(effort_evidence, str)
            and 0 < len(effort_evidence) <= 128
            and "\x00" not in effort_evidence
        )
        and type(allow_max_effort) is bool
        and type(requested_fanout) is int
    )
    if not valid:
        safe_task = task_class if isinstance(task_class, str) else ""
        return _decision(
            "denied",
            "E_ASTRA_V1_REQUEST_INVALID",
            safe_task[:128],
            selection_basis="request-denial",
        )
    if task_class not in TASK_DEFAULTS:
        return _decision(
            "not-applicable",
            "E_ASTRA_V1_ROUTE_NOT_APPLICABLE",
            task_class,
            selection_basis="legacy-v1-routing",
        )
    if requested_fanout != 1:
        return _decision(
            "denied",
            "E_ASTRA_V1_FANOUT_LIMIT",
            task_class,
            selection_basis="policy-denial",
        )
    if ASTRA_MODEL not in set(available_models):
        return _decision(
            "unavailable",
            "E_ASTRA_V1_UNAVAILABLE",
            task_class,
            selection_basis="runtime-availability",
        )

    default = TASK_DEFAULTS[task_class]
    effort = requested_effort or default
    stable_id, basis = _effort_basis(
        default, requested_effort, effort_evidence, allow_max_effort
    )
    if stable_id:
        return _decision(
            "denied", stable_id, task_class, selection_basis="policy-denial"
        )
    return _decision(
        "selected",
        None,
        task_class,
        effort=effort,
        selection_basis="explicit-effort" if requested_effort else "task-default",
        effort_basis=basis,
        effort_evidence=effort_evidence,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-class", required=True)
    parser.add_argument("--available-model", action="append", default=[])
    parser.add_argument("--effort")
    parser.add_argument("--effort-evidence")
    parser.add_argument("--allow-max-effort", action="store_true")
    parser.add_argument("--fanout", type=int, default=1)
    args = parser.parse_args(argv)
    result = resolve_v1_astra_route(
        task_class=args.task_class,
        available_models=tuple(args.available_model),
        requested_effort=args.effort,
        effort_evidence=args.effort_evidence,
        allow_max_effort=args.allow_max_effort,
        requested_fanout=args.fanout,
    )
    json.dump(result, sys.stdout, sort_keys=True, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0 if result["status"] in {"selected", "not-applicable"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
