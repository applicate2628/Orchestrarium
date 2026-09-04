#!/usr/bin/env python3
"""Resolve the narrow Orchestrarium 1.x Astra route without launching a provider."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

SCHEMA_VERSION = 1
ASTRA_MODEL = "gpt-6-astra"
SUPPORTED_EFFORTS = ("low", "medium", "high", "xhigh", "max")
TASK_DEFAULT_EFFORT = {
    "mathematical-research": "medium",
    "scientific-agentic-workflow": "medium",
    "cross-system-synthesis": "medium",
    "critical-recovery": "high",
}
LOW_EVIDENCE = frozenset({"migration-evaluation", "measured-sufficient"})
HIGH_EVIDENCE = frozenset({"medium-objective-failure", "measured-high-gain"})
XHIGH_EVIDENCE = frozenset(
    {"high-objective-failure", "high-contradictory", "measured-xhigh-gain"}
)
KNOWN_EVIDENCE = LOW_EVIDENCE | HIGH_EVIDENCE | XHIGH_EVIDENCE


def _result(
    *,
    status: str,
    stable_id: str | None,
    task_class: str,
    effort: str | None,
    selection_basis: str,
    effort_evidence: str | None = None,
) -> dict[str, Any]:
    selected = status == "selected"
    flags = (
        ["--model", ASTRA_MODEL, "-c", f"model_reasoning_effort={effort}"]
        if selected and effort is not None
        else []
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": status,
        "stableId": stable_id,
        "taskClass": task_class,
        "model": ASTRA_MODEL if selected else None,
        "effort": effort if selected else None,
        "codexFlags": flags,
        "selectionBasis": selection_basis,
        "effortEvidence": effort_evidence if selected else None,
        "fallback": "none",
        "automaticFanoutLimit": 1,
        "authorizing": False,
    }


def _effort_evidence_gate(
    *,
    task_class: str,
    requested_effort: str | None,
    effort: str,
    effort_evidence: str | None,
    allow_max_effort: bool,
) -> tuple[str | None, str | None]:
    if effort_evidence is not None and effort_evidence not in KNOWN_EVIDENCE:
        return "E_ASTRA_V1_EFFORT_EVIDENCE_INVALID", None
    if requested_effort is None:
        if effort_evidence is not None:
            return "E_ASTRA_V1_EFFORT_EVIDENCE_INVALID", None
        return None, "task-default"
    if effort == "low":
        return (
            (None, effort_evidence)
            if effort_evidence in LOW_EVIDENCE
            else ("E_ASTRA_V1_EFFORT_EVIDENCE_REQUIRED", None)
        )
    if effort == "medium":
        if effort_evidence is not None:
            return "E_ASTRA_V1_EFFORT_EVIDENCE_INVALID", None
        return None, "explicit-medium"
    if effort == "high":
        if task_class == "critical-recovery" and effort_evidence is None:
            return None, "critical-recovery-default"
        return (
            (None, effort_evidence)
            if effort_evidence in HIGH_EVIDENCE
            else ("E_ASTRA_V1_EFFORT_EVIDENCE_REQUIRED", None)
        )
    if effort == "xhigh":
        return (
            (None, effort_evidence)
            if effort_evidence in XHIGH_EVIDENCE
            else ("E_ASTRA_V1_EFFORT_EVIDENCE_REQUIRED", None)
        )
    if effort == "max":
        if not allow_max_effort:
            return "E_ASTRA_V1_MAX_APPROVAL_REQUIRED", None
        if effort_evidence is not None:
            return "E_ASTRA_V1_EFFORT_EVIDENCE_INVALID", None
        return None, "explicit-human-approval"
    return "E_ASTRA_V1_EFFORT_UNSUPPORTED", None


def resolve_v1_astra_route(
    *,
    task_class: str,
    available_models: set[str],
    requested_effort: str | None = None,
    effort_evidence: str | None = None,
    allow_max_effort: bool = False,
    requested_fanout: int = 1,
) -> dict[str, Any]:
    """Resolve one explicit Astra overlay while leaving legacy V1 routing unchanged."""

    if task_class not in TASK_DEFAULT_EFFORT:
        return _result(
            status="not-applicable",
            stable_id="E_ASTRA_V1_ROUTE_NOT_APPLICABLE",
            task_class=task_class,
            effort=None,
            selection_basis="legacy-v1-routing",
        )
    if type(requested_fanout) is not int or requested_fanout != 1:
        return _result(
            status="denied",
            stable_id="E_ASTRA_V1_FANOUT_LIMIT",
            task_class=task_class,
            effort=None,
            selection_basis="policy-denial",
        )
    if ASTRA_MODEL not in available_models:
        return _result(
            status="unavailable",
            stable_id="E_ASTRA_V1_UNAVAILABLE",
            task_class=task_class,
            effort=None,
            selection_basis="runtime-availability",
        )

    effort = requested_effort or TASK_DEFAULT_EFFORT[task_class]
    if effort not in SUPPORTED_EFFORTS:
        return _result(
            status="denied",
            stable_id="E_ASTRA_V1_EFFORT_UNSUPPORTED",
            task_class=task_class,
            effort=None,
            selection_basis="policy-denial",
        )
    stable_id, accepted_evidence = _effort_evidence_gate(
        task_class=task_class,
        requested_effort=requested_effort,
        effort=effort,
        effort_evidence=effort_evidence,
        allow_max_effort=allow_max_effort,
    )
    if stable_id is not None:
        return _result(
            status="denied",
            stable_id=stable_id,
            task_class=task_class,
            effort=None,
            selection_basis="policy-denial",
        )
    return _result(
        status="selected",
        stable_id=None,
        task_class=task_class,
        effort=effort,
        selection_basis=(
            "explicit-effort" if requested_effort is not None else "task-default"
        ),
        effort_evidence=accepted_evidence,
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
        available_models=set(args.available_model),
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
