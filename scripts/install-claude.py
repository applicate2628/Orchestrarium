#!/usr/bin/env python3
from pathlib import Path

from python_installer_bootstrap import ensure_supported_python

ensure_supported_python(str(Path(__file__).resolve()))

from production_installer import install

if __name__ == "__main__":
    raise SystemExit(install("claude"))
