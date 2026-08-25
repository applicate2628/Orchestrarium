#!/usr/bin/env python3
"""Read-only prompt transport for the official Grok CLI."""

from __future__ import annotations

import sys

from provider_prompt import launch


if __name__ == "__main__":
    raise SystemExit(launch("grok", sys.argv[1:]))
