#!/usr/bin/env python3
"""Fail-closed persistent-operation boundary for solution-attempt events.

The current delivery intentionally installs no active route and therefore
performs no live ledger write.  The function consumes the semantic reducer's
decision and the route owner's decision; it does not recreate either policy.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


STATE_INVALID = "SOL-E001-STATE-INVALID"
ENFORCEMENT_UNAVAILABLE = "SOL-E007-ENFORCEMENT-UNAVAILABLE"


def _load_reducer_owner() -> ModuleType:
    owner_path = (
        Path(__file__).resolve().parents[1] / "solution_attempt" / "reducer.py"
    )
    spec = importlib.util.spec_from_file_location(
        "solution_attempt_reducer_for_store",
        owner_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load solution-attempt owner: {owner_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _denial(result: str) -> dict[str, object]:
    return {"result": result, "committed": False, "head": None}


def commit_operation(
    *,
    ledger_path: str | Path,
    reduction: object,
    route_check: object,
) -> dict[str, object]:
    """Consume reducer and route decisions without mutating live bytes.

    ``ledger_path`` is part of the future sole-writer boundary but is never
    opened in this disabled-only slice.  A semantic denial is preserved; an
    otherwise committable reducer decision is denied by the route owner.
    """

    del ledger_path
    if not isinstance(reduction, dict):
        return _denial(STATE_INVALID)
    result = reduction.get("result")
    if not isinstance(result, str):
        return _denial(STATE_INVALID)

    reducer = _load_reducer_owner()
    committable_results = {reducer.OK, reducer.CLASS_REJECTED}
    if reduction.get("changed") is not True or result not in committable_results:
        return _denial(result)

    if not isinstance(route_check, dict):
        return _denial(ENFORCEMENT_UNAVAILABLE)
    if route_check.get("enabled") is not True:
        return _denial(ENFORCEMENT_UNAVAILABLE)

    # No activation writer or positive route record exists in this slice.
    # Refuse even a caller-forged mapping rather than growing a hidden write
    # path before the separately reviewed activation transaction exists.
    return _denial(ENFORCEMENT_UNAVAILABLE)


__all__ = ["commit_operation"]
