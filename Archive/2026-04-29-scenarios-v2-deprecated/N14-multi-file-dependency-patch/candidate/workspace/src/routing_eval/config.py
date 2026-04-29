from __future__ import annotations


def resolve_provider_order(config: dict) -> list[str]:
    """Return the provider order selected by the current routing profile."""
    catalog = config.get("externalPriorityProfiles", {})
    profile_name = config.get("externalPriorityProfile") or config.get("activeProfile") or "balanced"
    profile = catalog.get(profile_name)
    if profile is None:
        return [profile_name]
    return list(profile)
