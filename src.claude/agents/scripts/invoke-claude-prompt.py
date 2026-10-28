#!/usr/bin/env python3
"""File-based prompt transport for Claude CLI."""

from __future__ import annotations

import sys
import os
from pathlib import Path

_RUNTIME_NAMESPACE = Path(os.path.abspath(sys.argv[0] if __name__ == "__main__" else __file__)).parent
sys.path.insert(0, str(_RUNTIME_NAMESPACE))  # Import the selected adjacent participant.

from provider_prompt import launch


if __name__ == "__main__":
    raise SystemExit(launch("claude", sys.argv[1:], runtime_namespace=_RUNTIME_NAMESPACE))
