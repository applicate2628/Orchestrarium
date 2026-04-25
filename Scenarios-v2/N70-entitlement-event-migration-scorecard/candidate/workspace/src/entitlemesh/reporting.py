from __future__ import annotations

from .models import EntitlementState


def summarize_snapshot(rows: list[EntitlementState]) -> dict:
    """Return a compact summary for operators."""

    allowed = sum(1 for row in rows if row.allowed)
    denied = len(rows) - allowed
    return {
        "total": len(rows),
        "allowed": allowed,
        "denied": denied,
    }
