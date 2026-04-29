def resolve_profile(config):
    profiles = config.get("profiles", {})
    selected = config.get("activeProfile") or config.get("legacyProfile") or "default"
    return dict(profiles.get(selected, profiles.get("default", {})))
