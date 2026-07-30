#!/usr/bin/env python3
"""Interactive root installer; production choices dispatch to Python owners."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _run_production(name: str, forwarded: list[str]) -> int:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / f"install-{name}.py"), *forwarded],
        cwd=ROOT,
    ).returncode


def _run_example(name: str, forwarded: list[str]) -> int:
    if os.name == "nt":
        shell = shutil.which("pwsh") or shutil.which("powershell") or shutil.which("powershell.exe")
        if not shell:
            print(f"FAIL: PowerShell is required for the deprecated {name} example installer.", file=sys.stderr)
            return 127
        command = [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / f"install-{name}.ps1")]
    else:
        shell = shutil.which("bash")
        if not shell:
            print(f"FAIL: Bash is required for the deprecated {name} example installer.", file=sys.stderr)
            return 127
        command = [shell, str(ROOT / "scripts" / f"install-{name}.sh")]
    return subprocess.run([*command, *forwarded], cwd=ROOT).returncode


def main(argv: list[str] | None = None) -> int:
    forwarded = list(sys.argv[1:] if argv is None else argv)
    has_qwen = (ROOT / "scripts" / ("install-qwen.ps1" if os.name == "nt" else "install-qwen.sh")).is_file()
    print("What to install?")
    print("Production installs:")
    print("  1) Codex pack")
    print("  2) Claude Code")
    print("  3) Codex + Claude (default production install)")
    print("Deprecated example integrations (retained pending npm-skillpack):")
    print("  4) Gemini CLI (DEPRECATED / WEAK MODEL / NOT RECOMMENDED)")
    if has_qwen:
        print("  5) Qwen (DEPRECATED / WEAK MODEL / NOT RECOMMENDED)")
    try:
        choice = input(f"Select 1, 2, 3, 4{', or 5' if has_qwen else ''} [default: 3]: ").strip() or "3"
    except EOFError:
        print("FAIL: no selection received.", file=sys.stderr)
        return 1
    actions = {
        "1": (("production", "codex"),),
        "2": (("production", "claude"),),
        "3": (("production", "codex"), ("production", "claude")),
        "4": (("example", "gemini"),),
    }
    if has_qwen:
        actions["5"] = (("example", "qwen"),)
    if choice not in actions:
        print(f"Invalid selection: {choice}", file=sys.stderr)
        return 1
    for kind, name in actions[choice]:
        status = (
            _run_production(name, forwarded)
            if kind == "production"
            else _run_example(name, forwarded)
        )
        if status:
            return status
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
