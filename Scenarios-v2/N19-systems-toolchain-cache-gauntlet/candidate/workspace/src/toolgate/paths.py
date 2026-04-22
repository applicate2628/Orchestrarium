from __future__ import annotations


def normalize_build_root(path):
    text = str(path).replace("\\", "/")
    return text.rstrip("/")
