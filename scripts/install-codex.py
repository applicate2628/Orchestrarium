#!/usr/bin/env python3
import sys
from pathlib import Path

from python_installer_bootstrap import ensure_supported_python

ensure_supported_python(str(Path(__file__).resolve()))

from production_installer import install


def _normalize_compat_args(argv: list[str]) -> list[str]:
    """Map retired Kimi maintenance spelling to the non-writing diagnostic."""
    return [
        "--enroll-kimi" if arg == "--verify-kimi-enrollment" else arg
        for arg in argv
    ]


if __name__ == "__main__":
    sys.argv[1:] = _normalize_compat_args(sys.argv[1:])
    raise SystemExit(install("codex"))
