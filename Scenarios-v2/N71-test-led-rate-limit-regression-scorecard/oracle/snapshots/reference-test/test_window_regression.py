import unittest

from flowlimit import FixedWindowLimiter, RateLimitRequest


class WindowRegressionTests(unittest.TestCase):
    def test_same_tenant_different_users_have_independent_budget_and_retry_after(self):
        limiter = FixedWindowLimiter(limit=2, window_seconds=60.0)

        same_tenant_alice = RateLimitRequest("tenant-a", "alice", "/export", 10.0)
        same_tenant_bob = RateLimitRequest("tenant-a", "bob", "/export", 12.0)

        self.assertTrue(limiter.check(same_tenant_alice).allowed)
        self.assertTrue(limiter.check(same_tenant_alice).allowed)
        denied = limiter.check(same_tenant_alice)
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.retry_after, 50.0)

        self.assertTrue(limiter.check(same_tenant_bob).allowed)
        boundary = RateLimitRequest("tenant-a", "alice", "/export", 60.0)
        self.assertTrue(limiter.check(boundary).allowed)


if __name__ == "__main__":
    unittest.main()
