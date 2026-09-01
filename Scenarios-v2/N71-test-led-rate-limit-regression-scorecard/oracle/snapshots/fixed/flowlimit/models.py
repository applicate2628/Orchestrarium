from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitRequest:
    tenant_id: str
    user_id: str
    route: str
    timestamp: float


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after: float
