from config.defaults import RETRY_LIMIT as _DECLARED_RETRY

# Effective configuration actually used by the batch pipeline. These overrides are the
# authoritative effective values; they replace the declared defaults for the batch profile.
EFFECTIVE_RETRY_LIMIT = 5
EFFECTIVE_TIMEOUT_MS = 8000
EFFECTIVE_PROFILE = "batch"


def effective_config():
    return {
        "retry_limit": EFFECTIVE_RETRY_LIMIT,
        "timeout_ms": EFFECTIVE_TIMEOUT_MS,
        "profile": EFFECTIVE_PROFILE,
    }
