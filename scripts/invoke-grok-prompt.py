#!/usr/bin/env python3
"""Read-only prompt transport for the official Grok CLI."""

from __future__ import annotations

import sys
import os
from pathlib import Path

_RUNTIME_NAMESPACE = Path(os.path.abspath(sys.argv[0] if __name__ == "__main__" else __file__)).parent

from provider_prompt import launch


if __name__ == "__main__":
    raise SystemExit(launch("grok", sys.argv[1:], runtime_namespace=_RUNTIME_NAMESPACE))
