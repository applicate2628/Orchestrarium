#!/usr/bin/env python3
"""Neutral Claude agents-mode scalar resolution support.

This leaf owns only the provider read order and top-level scalar extraction.
Consumer entrypoints own their accepted vocabularies and resulting behavior.
"""

from __future__ import annotations

import os
import re
from pathlib import Path


_KEY_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")
_COMMENT_RE = re.compile(r"\s+#.*$")


def resolve_scalar(
    key: str, *, cwd: Path | None = None, home: Path | None = None
) -> str:
    """Resolve one normalized scalar through Claude's first-match precedence."""
    if not isinstance(key, str) or not _KEY_NAME_RE.fullmatch(key):
        return "unresolved"

    project = Path.cwd() if cwd is None else Path(cwd)
    resolved_home = home
    if resolved_home is None:
        home_value = os.environ.get("USERPROFILE") or os.environ.get("HOME")
        resolved_home = Path(home_value) if home_value else None

    candidates = [
        project / ".claude" / ".agents-mode.yaml",
        project / ".claude" / ".agents-mode",
    ]
    if resolved_home is not None:
        resolved_home = Path(resolved_home)
        candidates.extend(
            [
                resolved_home / ".claude" / ".agents-mode.yaml",
                resolved_home / ".claude" / ".agents-mode",
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
                return value.strip().lower()

    return "unresolved"
