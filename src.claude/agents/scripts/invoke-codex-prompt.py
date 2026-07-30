#!/usr/bin/env python3
"""File-based prompt transport for Codex CLI."""

from __future__ import annotations

import sys

from provider_prompt import launch


if __name__ == "__main__":
    raise SystemExit(launch("codex", sys.argv[1:]))
