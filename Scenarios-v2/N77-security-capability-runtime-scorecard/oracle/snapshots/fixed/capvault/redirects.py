from __future__ import annotations

from urllib.parse import unquote, urlparse


DEFAULT_RETURN_URL = "https://files.example.com/downloads/"


def sanitize_return_url(url: str) -> str:
    if "\r" in url or "\n" in url or "\\" in url:
        return DEFAULT_RETURN_URL
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return DEFAULT_RETURN_URL
    if parsed.username or parsed.password:
        return DEFAULT_RETURN_URL
    if parsed.hostname != "files.example.com":
        return DEFAULT_RETURN_URL
    path = unquote(parsed.path)
    if "\\" in path or "\r" in path or "\n" in path or not path.startswith("/downloads/"):
        return DEFAULT_RETURN_URL
    if "\r" in unquote(parsed.query) or "\n" in unquote(parsed.query):
        return DEFAULT_RETURN_URL
    return url
