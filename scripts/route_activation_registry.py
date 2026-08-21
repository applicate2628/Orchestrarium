#!/usr/bin/env python3
"""Disabled-by-default route catalog for solution-attempt operations.

This source-only slice deliberately has no activation writer.  Catalog
presence is not activation: every query returns the stable enforcement denial,
including a query whose supplied binding bytes match.
"""

from __future__ import annotations

import re


ENFORCEMENT_UNAVAILABLE = "SOL-E007-ENFORCEMENT-UNAVAILABLE"
ROUTE_IDS = (
    "claude.native-agent",
    "claude.external.codex",
    "claude.external.claude",
    "codex.native-subagent",
    "codex.root",
    "codex.external.codex",
    "codex.external.claude",
)
_ROUTE_SET = frozenset(ROUTE_IDS)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.ASCII)


def _is_digest(value: object) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


def check_route(
    route_id: object,
    *,
    expected_binding: object = None,
    observed_binding: object = None,
) -> dict[str, object]:
    """Return a non-authorizing decision for one closed-catalog route.

    Binding equality is reported only as diagnostic state.  It cannot activate
    a route, issue a receipt, or become a check-then-use authorization.
    """

    known_route = isinstance(route_id, str) and route_id in _ROUTE_SET
    binding_matches = (
        known_route
        and _is_digest(expected_binding)
        and _is_digest(observed_binding)
        and expected_binding == observed_binding
    )
    return {
        "routeId": route_id if isinstance(route_id, str) else "",
        "enabled": False,
        "bindingMatches": bool(binding_matches),
        "result": ENFORCEMENT_UNAVAILABLE,
    }


__all__ = ["ENFORCEMENT_UNAVAILABLE", "ROUTE_IDS", "check_route"]
