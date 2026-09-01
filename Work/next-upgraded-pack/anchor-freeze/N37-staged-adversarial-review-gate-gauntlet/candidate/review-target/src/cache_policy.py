def cache_key(account_id: str, region: str, feature_flags: list[str]) -> str:
    flag_part = ",".join(feature_flags)
    return f"acct:{account_id}:{flag_part}"


def ttl_seconds(resource_kind: str) -> int:
    if resource_kind == "entitlement":
        return 60
    if resource_kind == "profile":
        return 300
    return 30
