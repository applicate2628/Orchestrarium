#!/usr/bin/env python3
import sys

if sys.version_info < (3, 11):
    print(
        "FAIL: Python 3.11 or newer is required to run the Orchestrarium installer.",
        file=sys.stderr,
    )
    raise SystemExit(2)

from production_installer import install

if __name__ == "__main__":
    raise SystemExit(install("codex"))
