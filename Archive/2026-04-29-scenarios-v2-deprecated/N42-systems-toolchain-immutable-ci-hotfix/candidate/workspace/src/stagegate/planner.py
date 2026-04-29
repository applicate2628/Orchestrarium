from __future__ import annotations


def build_plan(settings: dict, requests):
    return sorted(requests, key=lambda request: request.priority, reverse=True)
