#!/usr/bin/env python3
"""File-reference prompt transport for Kimi Code CLI."""

from __future__ import annotations

import sys

from provider_prompt import launch


if __name__ == "__main__":
    raise SystemExit(launch("kimi", sys.argv[1:]))
