from __future__ import annotations


DEFAULT_RETURN_URL = "https://files.example.com/downloads/"


def sanitize_return_url(url: str) -> str:
    if url.startswith(DEFAULT_RETURN_URL):
        return url
    return DEFAULT_RETURN_URL
