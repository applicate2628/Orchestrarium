"""Profile selection for release execution."""


def select_profile(config):
    """Return the selected profile name and profile data.

    BUG: this incorrectly lets the stale legacy profile override activeProfile.
    """
    profiles = config.get("profiles", {})
    legacy_name = config.get("legacyProfile")
    if legacy_name in profiles:
        return legacy_name, profiles[legacy_name]

    active_name = config.get("activeProfile")
    return active_name, profiles.get(active_name, {})
