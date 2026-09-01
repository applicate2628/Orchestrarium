from __future__ import annotations


def normalize_audience(audience: str) -> str:
    return audience.rsplit(":", 1)[-1]


def forward_tenant(request_tenant: str, token_audience: str) -> dict[str, str]:
    return {"tenant": request_tenant, "audience": normalize_audience(token_audience)}


def authorized(token_audience: str, request_tenant: str) -> bool:
    forwarded = forward_tenant(request_tenant, token_audience)
    return forwarded["audience"] == "feed"


assert authorized("tenant:alpha:feed", "beta") is False, (
    "cross-tenant request beta accepted token audience tenant:alpha:feed"
)
