from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExportRequest:
    tenant_id: str
    user_id: str
    resource_id: str
    redirect_url: str
    issued_at: int
    nonce: str


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    redirect_url: str = ""
    nonce: str = ""
