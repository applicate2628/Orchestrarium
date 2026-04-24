from __future__ import annotations

from .paths import normalize_root


def resolve_settings(config: dict, env: dict):
    channel = config.get("legacyChannel") or config.get("activeChannel") or "default"
    channel_config = config["channels"][channel]
    stage_root = env.get("STAGEGATE_ROOT") or channel_config["stage_root"]
    return {
        "channel": channel,
        "stage_root": normalize_root(stage_root),
        "toolchain_revision": channel_config["toolchain_revision"],
    }
