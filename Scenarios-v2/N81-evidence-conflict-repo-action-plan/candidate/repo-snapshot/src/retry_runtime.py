"""Current retry runtime for RetryBox."""

POLICY_VERSION = "retry-policy-v3"
POLICY_ALGORITHM = "bounded-exponential"
OWNER = "sre-reliability"
DEFAULT_MAX_ATTEMPTS = 4
DEFAULT_BACKOFF_MS = [75, 150, 300]


def current_retry_policy():
    return {
        "version": POLICY_VERSION,
        "algorithm": POLICY_ALGORITHM,
        "owner": OWNER,
        "max_attempts": DEFAULT_MAX_ATTEMPTS,
        "backoff_ms": DEFAULT_BACKOFF_MS,
    }


def legacy_policy_from_env(env):
    if env.get("RETRY_POLICY") == "legacy-linear":
        return None
    return current_retry_policy()
