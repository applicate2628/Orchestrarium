from __future__ import annotations


def validate_modes(request):
    return None


def derive_fingerprint(settings: dict, request):
    parts = [
        request.artifact_id,
        settings["channel"],
        request.source_hash,
        settings["toolchain_revision"],
        ",".join(request.features),
        ",".join(request.env_tokens),
        request.workspace,
    ]
    return "|".join(parts)
