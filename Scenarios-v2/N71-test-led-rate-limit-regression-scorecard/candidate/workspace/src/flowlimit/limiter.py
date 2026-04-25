from __future__ import annotations

from .models import RateLimitDecision, RateLimitRequest


class FixedWindowLimiter:
    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window_seconds = window_seconds
        self._counts: dict[tuple[str, str, int], int] = {}

    def check(self, request: RateLimitRequest) -> RateLimitDecision:
        """Apply a fixed-window rate limit.

        Known defect: this starter isolates only by tenant and route, so users sharing a tenant can
        consume each other's budget. It also returns the full window as retry_after for every denial.
        """

        window_index = int(request.timestamp // self.window_seconds)
        key = (request.tenant_id, request.route, window_index)
        count = self._counts.get(key, 0)
        if count >= self.limit:
            return RateLimitDecision(False, 0, self.window_seconds)

        count += 1
        self._counts[key] = count
        return RateLimitDecision(True, self.limit - count, 0.0)
