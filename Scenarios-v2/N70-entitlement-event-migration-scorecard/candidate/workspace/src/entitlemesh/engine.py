from __future__ import annotations

from .models import EntitlementState
from .parser import parse_event


def build_entitlement_snapshot(raw_events: list[dict]) -> list[EntitlementState]:
    """Build current entitlement state from grant/revoke events."""

    state: dict[tuple[str, str, str], tuple[bool, str, list[str]]] = {}

    events = sorted((parse_event(raw) for raw in raw_events), key=lambda event: event.sequence)
    for event in events:
        key = (event.tenant_id, event.principal_id, event.resource_id)
        if event.action == "grant":
            state[key] = (True, event.plan, [f"grant:{event.plan}"])
        elif event.action == "revoke":
            state[key] = (False, "", ["revoke"])

    rows = [
        EntitlementState(
            tenant_id=tenant_id,
            principal_id=principal_id,
            resource_id=resource_id,
            allowed=allowed,
            plan=plan,
            hold_reason="",
            audit_tags=tuple(tags),
        )
        for (tenant_id, principal_id, resource_id), (allowed, plan, tags) in state.items()
    ]
    return sorted(rows, key=lambda row: (row.tenant_id, row.principal_id, row.resource_id))
