from __future__ import annotations

from .models import RateLimitDecision, RateLimitRequest


class FixedWindowLimiter:
    # MUTANT class-id=retry-after: fixed reference EXCEPT a denial reports the full
    # window as retry_after instead of the remaining seconds until the current window
    # ends. Isolation and window-boundary logic are the correct reference logic. A test
    # that never asserts the exact retry_after value PASSES here -> "retry-after undetected".
    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window_seconds = window_seconds
        self._counts: dict[tuple[str, str, str, int], int] = {}

    def check(self, request: RateLimitRequest) -> RateLimitDecision:
        window_index = int(request.timestamp // self.window_seconds)
        key = (request.tenant_id, request.user_id, request.route, window_index)
        count = self._counts.get(key, 0)
        if count >= self.limit:
            return RateLimitDecision(False, 0, self.window_seconds)

        count += 1
        self._counts[key] = count
        return RateLimitDecision(True, self.limit - count, 0.0)
