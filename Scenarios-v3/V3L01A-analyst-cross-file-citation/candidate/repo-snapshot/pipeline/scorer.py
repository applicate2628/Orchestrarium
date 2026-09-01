from config.effective import effective_config


def run_scorer(batch):
    # The scorer uses the EFFECTIVE config (overrides), never the declared defaults directly.
    config = effective_config()
    return _score(batch, retries=config["retry_limit"], timeout=config["timeout_ms"])


def _score(batch, retries, timeout):
    scored = []
    for item in batch:
        scored.append({"id": item["id"], "retries": retries, "timeout": timeout})
    return scored
