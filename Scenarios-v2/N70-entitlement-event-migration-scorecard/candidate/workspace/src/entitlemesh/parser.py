from __future__ import annotations

from typing import Any

from .models import EntitlementEvent


def parse_event(raw: dict[str, Any]) -> EntitlementEvent:
    """Parse legacy entitlement events.

    Known defect: schema-v2 payloads are not normalized yet.
    """

    return EntitlementEvent(
        event_id=str(raw["event_id"]),
        tenant_id=str(raw["tenant_id"]),
        principal_id=str(raw["principal_id"]),
        resource_id=str(raw["resource_id"]),
        action=str(raw["action"]),
        sequence=int(raw.get("sequence", 0)),
        plan=str(raw.get("plan", "")),
        reason=str(raw.get("reason", "")),
        replaces_event_id=raw.get("replaces_event_id"),
    )
