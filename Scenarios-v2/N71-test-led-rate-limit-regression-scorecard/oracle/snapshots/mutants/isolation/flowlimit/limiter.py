from __future__ import annotations

from .models import RateLimitDecision, RateLimitRequest


class FixedWindowLimiter:
    # MUTANT class-id=isolation: fixed reference EXCEPT the window key drops user_id,
    # so two users sharing a (tenant, route, window) consume one budget. retry_after
    # and window-boundary logic are the correct reference logic. A regression test that
    # only checks denial + retry_after (and never same-tenant/different-user isolation)
    # PASSES here -> the gate flags "isolation undetected".
    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window_seconds = window_seconds
        self._counts: dict[tuple[str, str, int], int] = {}

    def check(self, request: RateLimitRequest) -> RateLimitDecision:
        window_index = int(request.timestamp // self.window_seconds)
        key = (request.tenant_id, request.route, window_index)
        count = self._counts.get(key, 0)
        if count >= self.limit:
            window_end = (window_index + 1) * self.window_seconds
            return RateLimitDecision(False, 0, max(0.0, window_end - request.timestamp))

        count += 1
        self._counts[key] = count
        return RateLimitDecision(True, self.limit - count, 0.0)
