def resolve_profile(config):
    profiles = config.get("profiles", {})
    selected = config.get("legacyProfile") or config.get("activeProfile") or "default"
    return profiles.get(selected, profiles.get("default", {}))
