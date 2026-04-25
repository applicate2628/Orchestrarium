def build_usage_summary(results):
    accepted = [item for item in results if item.get("accepted")]
    rejected = [item for item in results if not item.get("accepted")]
    return {
        "accepted": len(accepted),
        "rejected": len(rejected),
        "retryable": 0,
        "owners": sorted({item.get("owner", "unknown") for item in rejected}),
    }
