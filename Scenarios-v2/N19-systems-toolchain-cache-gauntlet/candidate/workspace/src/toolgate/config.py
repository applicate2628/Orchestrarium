from __future__ import annotations

from .paths import normalize_build_root


def resolve_settings(config, env):
    profile_name = config.get("legacyProfile") or config.get("activeProfile") or "default"
    profiles = config.get("profiles", {})
    profile = dict(profiles.get(profile_name, {}))
    build_root = env.get("BUILDGATE_BUILD_ROOT") or profile.get("build_root") or "build"
    profile["name"] = profile_name
    profile["build_root"] = normalize_build_root(build_root)
    profile["toolchain"] = profile.get("toolchain", "unknown")
    return profile
