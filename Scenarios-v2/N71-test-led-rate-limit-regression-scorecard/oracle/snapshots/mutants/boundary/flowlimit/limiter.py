from __future__ import annotations

from .models import RateLimitDecision, RateLimitRequest


class FixedWindowLimiter:
    # MUTANT class-id=boundary: fixed reference EXCEPT an off-by-one at the window edge,
    # so a request whose timestamp lands exactly on a window boundary is bucketed into the
    # PREVIOUS window instead of opening the new one. Isolation and retry_after logic are
    # the correct reference logic; the only observable difference is at the exact boundary.
    # A test that never exercises the exact-boundary timestamp PASSES here -> "boundary undetected".
    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window_seconds = window_seconds
        self._counts: dict[tuple[str, str, str, int], int] = {}

    def check(self, request: RateLimitRequest) -> RateLimitDecision:
        raw = request.timestamp / self.window_seconds
        window_index = int(raw)
        if raw == int(raw) and request.timestamp > 0:
            window_index -= 1
        key = (request.tenant_id, request.user_id, request.route, window_index)
        count = self._counts.get(key, 0)
        if count >= self.limit:
            window_end = (window_index + 1) * self.window_seconds
            return RateLimitDecision(False, 0, max(0.0, window_end - request.timestamp))

        count += 1
        self._counts[key] = count
        return RateLimitDecision(True, self.limit - count, 0.0)
