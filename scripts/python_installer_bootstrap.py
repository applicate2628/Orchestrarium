"""Re-execute installer entrypoints with a supported Python when necessary."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys


VERSION_FAILURE = (
    "FAIL: Python 3.11 or newer is required to run the Orchestrarium installer."
)
_VERSION_PROBE = (
    "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
)


def _is_current_executable(candidate: str) -> bool:
    try:
        return os.path.samefile(candidate, sys.executable)
    except (FileNotFoundError, OSError):
        return os.path.normcase(os.path.realpath(candidate)) == os.path.normcase(
            os.path.realpath(sys.executable)
        )


def ensure_supported_python(entrypoint: str) -> None:
    """Continue in-place under the first Python 3.11+ candidate."""
    if sys.version_info >= (3, 11):
        return

    for command in ("python3", "python"):
        candidate = shutil.which(command)
        if candidate is None or _is_current_executable(candidate):
            continue
        try:
            result = subprocess.run(
                [candidate, "-c", _VERSION_PROBE],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except OSError:
            continue
        if result.returncode == 0:
            try:
                os.execv(candidate, [candidate, entrypoint, *sys.argv[1:]])
            except OSError:
                continue

    print(VERSION_FAILURE, file=sys.stderr)
    raise SystemExit(2)
