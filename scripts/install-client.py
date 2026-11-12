#!/usr/bin/env python3
"""Noninteractive client selection; the production installer owns policy."""
import argparse
from pathlib import Path
import sys

# Isolated bundled Python omits the script directory from sys.path.
# Bind only this entrypoint's own installer modules, never caller cwd.
SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from python_installer_bootstrap import ensure_supported_python

ensure_supported_python(str(Path(__file__).resolve()))
from installation.clients import CLIENTS
from production_installer import install


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--client", choices=tuple(CLIENTS), required=True)
    options, forwarded = parser.parse_known_args(sys.argv[1:] if argv is None else argv)
    return install(options.client, forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
