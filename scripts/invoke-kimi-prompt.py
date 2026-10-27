#!/usr/bin/env python3
"""File-reference prompt transport for Kimi Code CLI."""

from __future__ import annotations

import sys
import os
from pathlib import Path

_RUNTIME_NAMESPACE = Path(os.path.abspath(sys.argv[0] if __name__ == "__main__" else __file__)).parent

from provider_prompt import kimi_main


if __name__ == "__main__":
    raise SystemExit(kimi_main(sys.argv[1:], runtime_namespace=_RUNTIME_NAMESPACE))
