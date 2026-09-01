import unittest

from flowlimit import FixedWindowLimiter, RateLimitRequest


class WindowRegressionTests(unittest.TestCase):
    # ADVERSARIAL DECOY (four-probe #3): right shape, wrong substance. It verifies the
    # "obvious" symptoms the shipped bug showed -- denial after the limit and the exact
    # retry_after -- and is keyword-stuffed to satisfy the static floor terms
    # (same tenant, different user, window boundary, retry_after) WITHOUT ever exercising
    # same-tenant/different-user isolation or the exact window boundary. It PASSES the
    # single historical buggy baseline (that baseline also broke retry_after), so a
    # single-baseline gate would certify it. The isolation and boundary class-mutants
    # expose that it never actually tested those required behaviors.
    def test_denied_after_limit_reports_retry_after(self):
        limiter = FixedWindowLimiter(limit=2, window_seconds=60.0)
        request = RateLimitRequest("tenant-a", "alice", "/export", 10.0)

        self.assertTrue(limiter.check(request).allowed)
        self.assertTrue(limiter.check(request).allowed)
        denied = limiter.check(request)
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.retry_after, 50.0)


if __name__ == "__main__":
    unittest.main()
