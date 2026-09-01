from __future__ import annotations


def cache_key(settings, request):
    features = ",".join(request.features)
    return "|".join(
        [
            request.target,
            request.profile,
            request.source_hash,
            settings.get("toolchain", "unknown"),
            request.workspace,
            features,
        ]
    )
