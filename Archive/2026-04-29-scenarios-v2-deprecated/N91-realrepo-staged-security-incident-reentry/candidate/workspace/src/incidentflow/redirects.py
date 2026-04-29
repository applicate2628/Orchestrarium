from urllib.parse import urlparse


DEFAULT_RETURN_URL = "https://exports.example.com/downloads/"


def sanitize_return_url(url: str, *, default: str = DEFAULT_RETURN_URL) -> str:
    parsed = urlparse(url)
    if "exports.example.com" in parsed.netloc and parsed.path.startswith("/downloads/"):
        return url
    return default
