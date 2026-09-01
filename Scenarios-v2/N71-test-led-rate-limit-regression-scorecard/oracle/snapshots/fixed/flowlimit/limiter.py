from __future__ import annotations

from .models import RateLimitDecision, RateLimitRequest


class FixedWindowLimiter:
    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window_seconds = window_seconds
        self._counts: dict[tuple[str, str, int], int] = {}

    def check(self, request: RateLimitRequest) -> RateLimitDecision:
        """Apply a fixed-window rate limit.

        Apply the limit independently per tenant, user, route, and fixed window.
        """

        window_index = int(request.timestamp // self.window_seconds)
        key = (request.tenant_id, request.user_id, request.route, window_index)
        count = self._counts.get(key, 0)
        if count >= self.limit:
            window_end = (window_index + 1) * self.window_seconds
            return RateLimitDecision(False, 0, max(0.0, window_end - request.timestamp))

        count += 1
        self._counts[key] = count
        return RateLimitDecision(True, self.limit - count, 0.0)
