import unittest

from flowlimit import FixedWindowLimiter, RateLimitRequest


class VisibleRateLimitTests(unittest.TestCase):
    def test_single_user_window_limit(self):
        limiter = FixedWindowLimiter(limit=2, window_seconds=60.0)
        request = RateLimitRequest("tenant-visible", "user-visible", "/exports", 10.0)

        self.assertTrue(limiter.check(request).allowed)
        self.assertTrue(limiter.check(request).allowed)
        denied = limiter.check(request)

        self.assertFalse(denied.allowed)
        self.assertEqual(denied.remaining, 0)
