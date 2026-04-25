from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EntitlementEvent:
    event_id: str
    tenant_id: str
    principal_id: str
    resource_id: str
    action: str
    sequence: int
    plan: str
    reason: str = ""
    replaces_event_id: str | None = None


@dataclass(frozen=True)
class EntitlementState:
    tenant_id: str
    principal_id: str
    resource_id: str
    allowed: bool
    plan: str
    hold_reason: str
    audit_tags: tuple[str, ...]
