from __future__ import annotations

from .cache import cache_key


def build_plan(settings, requests):
    plan = []
    for request in sorted(requests, key=lambda item: (-item.priority, item.target)):
        key = cache_key(settings, request)
        plan.append(
            {
                "target": request.target,
                "profile": request.profile,
                "build_root": settings["build_root"],
                "cache_key": key,
                "source": request.source,
                "request": request,
            }
        )
    return plan
