#!/usr/bin/env python3
"""Interactive root installer; production choices dispatch to Python owners."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if sys.version_info < (3, 11):
    print(
        "FAIL: Python 3.11 or newer is required to run the Orchestrarium installer.",
        file=sys.stderr,
    )
    raise SystemExit(2)


ROOT = Path(__file__).resolve().parent


def _run_production(name: str, forwarded: list[str]) -> int:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / f"install-{name}.py"), *forwarded],
        cwd=ROOT,
    ).returncode


def main(argv: list[str] | None = None) -> int:
    forwarded = list(sys.argv[1:] if argv is None else argv)
    print("What to install?")
    print("Production installs:")
    print("  1) Codex pack")
    print("  2) Claude Code")
    print("  3) Codex + Claude (default production install)")
    try:
        choice = input("Select 1, 2, or 3 [default: 3]: ").strip() or "3"
    except EOFError:
        print("FAIL: no selection received.", file=sys.stderr)
        return 1
    actions = {
        "1": ("codex",),
        "2": ("claude",),
        "3": ("codex", "claude"),
    }
    if choice not in actions:
        print(f"Invalid selection: {choice}", file=sys.stderr)
        return 1
    for name in actions[choice]:
        status = _run_production(name, forwarded)
        if status:
            return status
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
