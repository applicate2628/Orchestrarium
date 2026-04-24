from __future__ import annotations


def normalize_root(path: str) -> str:
    normalized = str(path).replace("\\", "/")
    while len(normalized) > 1 and normalized.endswith("/"):
        normalized = normalized[:-1]
    return normalized


def is_absolute_root(path: str) -> bool:
    text = str(path).replace("\\", "/")
    return text.startswith("/") or (len(text) >= 3 and text[1:3] == ":/")
