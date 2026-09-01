#!/usr/bin/env python3
"""File-reference prompt transport for Kimi Code CLI."""

from __future__ import annotations

import sys

from provider_prompt import kimi_main


if __name__ == "__main__":
    raise SystemExit(kimi_main(sys.argv[1:]))
