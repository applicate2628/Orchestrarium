#!/usr/bin/env python3
"""Pre-action route barrier for provider process launches.

No route is active in this source-only slice, so process creation and a
repository-capable first action are unreachable.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Callable


def _load_registry_owner() -> ModuleType:
    owner_path = Path(__file__).resolve().parents[1] / "route_activation_registry.py"
    spec = importlib.util.spec_from_file_location(
        "route_activation_registry_for_launcher",
        owner_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load route registry owner: {owner_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def launch_guarded(
    route_id: object,
    *,
    expected_binding: object = None,
    observed_binding: object = None,
    process_factory: Callable[..., object] | None = None,
) -> dict[str, object]:
    """Check the route before any process factory or first action is reached."""

    registry = _load_registry_owner()
    route = registry.check_route(
        route_id,
        expected_binding=expected_binding,
        observed_binding=observed_binding,
    )
    if route.get("enabled") is not True:
        return {
            "result": route["result"],
            "routeId": route["routeId"],
            "started": False,
            "firstAction": False,
        }

    # The accepted slice contains no positive route or provider composition
    # root.  Keep the parameter explicit so later work cannot insert a process
    # call before the barrier while preserving the present no-first-action law.
    del process_factory
    return {
        "result": registry.ENFORCEMENT_UNAVAILABLE,
        "routeId": route["routeId"],
        "started": False,
        "firstAction": False,
    }


__all__ = ["launch_guarded"]
