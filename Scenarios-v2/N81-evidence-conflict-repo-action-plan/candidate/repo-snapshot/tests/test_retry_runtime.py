from src.export_plan import export_visibility
from src.retry_runtime import current_retry_policy, legacy_policy_from_env


def test_current_policy_is_v3_bounded_exponential():
    policy = current_retry_policy()
    assert policy["version"] == "retry-policy-v3"
    assert policy["algorithm"] == "bounded-exponential"
    assert policy["owner"] == "sre-reliability"
    assert policy["max_attempts"] == 4
    assert policy["backoff_ms"] == [75, 150, 300]


def test_legacy_linear_env_does_not_enable_rollback():
    assert legacy_policy_from_env({"RETRY_POLICY": "legacy-linear"}) is None


def test_auditor_can_export_hidden_rows():
    assert export_visibility("auditor", include_hidden=True) == "visible-and-hidden"


def test_non_auditor_hidden_request_stays_visible_only():
    assert export_visibility("customer", include_hidden=True) == "visible-only"
