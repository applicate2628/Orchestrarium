#!/usr/bin/env python3
"""Neutral Codex agents-mode scalar resolution support.

This leaf owns only the Codex read order and top-level scalar extraction.
Consumer entrypoints own their accepted vocabularies and resulting behavior.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path


_KEY_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")
_COMMENT_RE = re.compile(r"\s+#.*$")


def _decode_supported_scalar(value: str) -> str:
    """Decode the quoted-string subset admitted by the agents-mode normalizer."""
    value = value.strip()
    if len(value) < 2 or value[0] != value[-1] or value[0] not in {"'", '"'}:
        return value
    if value[0] == "'":
        return value[1:-1].replace("''", "'")
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return value
    return decoded if isinstance(decoded, str) else value


def resolve_scalar(
    key: str, *, cwd: Path | None = None, home: Path | None = None
) -> str:
    """Resolve one normalized scalar through Codex's first-match precedence."""
    if not isinstance(key, str) or not _KEY_NAME_RE.fullmatch(key):
        return "unresolved"

    project = Path.cwd() if cwd is None else Path(cwd)
    resolved_home = home
    if resolved_home is None:
        home_value = os.environ.get("USERPROFILE") or os.environ.get("HOME")
        resolved_home = Path(home_value) if home_value else None

    candidates = [
        project / ".agents" / ".agents-mode.yaml",
        project / ".agents" / ".agents-mode",
    ]
    if resolved_home is not None:
        resolved_home = Path(resolved_home)
        candidates.extend(
            [
                resolved_home / ".codex" / ".agents-mode.yaml",
                resolved_home / ".codex" / ".agents-mode",
                resolved_home / ".agents-mode.yaml",
            ]
        )

    prefix = f"{key}:"
    for candidate in candidates:
        try:
            if not candidate.is_file():
                continue
            text = candidate.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for raw_line in text.splitlines():
            if raw_line.startswith(prefix):
                value = _COMMENT_RE.sub("", raw_line[len(prefix) :].lstrip())
                return _decode_supported_scalar(value).strip().lower()

    return "unresolved"
