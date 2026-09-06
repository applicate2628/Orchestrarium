"""Reproduce historical Git archive bytes, independent of checkout preferences."""
from __future__ import annotations

import subprocess
from pathlib import Path


def archive_revision(root: Path, revision: str, *paths: str) -> bytes:
    """Archive a historical source tree without the caller's CRLF conversion."""
    return subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf",
         "archive", "--format=tar", revision, *paths],
        cwd=root, check=True, capture_output=True, timeout=90,
    ).stdout
