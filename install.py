#!/usr/bin/env python3
"""Interactive root installer; production choices dispatch to Python owners."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from python_installer_bootstrap import ensure_supported_python
from installation.clients import CLIENTS

ensure_supported_python(str(Path(__file__).resolve()))


def _run_production(name: str, forwarded: list[str]) -> int:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / f"install-{name}.py"), *forwarded],
        # Preserve caller cwd for project discovery and relative --target paths.
    ).returncode


def _run_selected(selected: tuple[str, ...], forwarded: list[str]) -> int:
    outcomes = dict.fromkeys(selected, "not started")
    complete = False
    exceptional_exit = False
    try:
        for name in selected:
            print(f"Starting {name} installer...", flush=True)
            outcomes[name] = "outcome unavailable"
            status = _run_production(name, forwarded)
            outcomes[name] = (
                "completed (exit 0)" if status == 0 else f"failed (exit {status})"
            )
            if status:
                return status
        complete = True
        return 0
    except BaseException:
        exceptional_exit = True
        raise
    finally:
        try:
            stream = sys.stdout if complete else sys.stderr
            print(
                "Installer summary: "
                + "; ".join(f"{name}: {outcomes[name]}" for name in selected),
                file=stream,
                flush=True,
            )
            if not complete:
                if "completed (exit 0)" in outcomes.values():
                    print("Earlier completed calls were not rolled back by this router.", file=stream)
                print(
                    "Review provider output and recovery state before retrying; "
                    "a failed or interrupted installer may have made changes.",
                    file=stream,
                    flush=True,
                )
        except BaseException:
            if not exceptional_exit:
                raise


def main(argv: list[str] | None = None) -> int:
    forwarded = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--clients", nargs="+", choices=tuple(CLIENTS))
    parser.add_argument("--list-clients", action="store_true")
    options, forwarded = parser.parse_known_args(forwarded)
    if options.list_clients:
        if options.clients is not None or forwarded:
            parser.error("--list-clients cannot be combined with installation options")
        for name, spec in CLIENTS.items():
            print(f"{name}: {spec['label']}")
        return 0
    if options.clients is not None:
        # Stable catalog order, one call per client even if listed twice.
        selected = tuple(name for name in CLIENTS if name in options.clients)
    else:
        print("What to install?")
        print("Production installs:")
        print("  1) Codex pack")
        print("  2) Claude Code")
        print("  3) Codex + Claude")
        print("  q/empty) Cancel")
        try:
            choice = input("Select 1, 2, or 3 [default: cancel]: ").strip().lower()
        except EOFError:
            print("FAIL: no selection received.", file=sys.stderr)
            return 1
        if choice in ("", "q"):
            print("Cancelled before preview.")
            return 0
        actions = {
            "1": ("codex",),
            "2": ("claude",),
            "3": ("codex", "claude"),
        }
        if choice not in actions:
            print(f"Invalid selection: {choice}", file=sys.stderr)
            return 1
        selected = actions[choice]
    if options.clients is not None:
        return _run_selected(selected, forwarded)
    # Provider owners produce the preview; this router never invents a plan.
    preview_only = any(flag in forwarded for flag in ("--dry-run", "-DryRun", "--help", "-h"))
    preview = forwarded if preview_only else [*forwarded, "--dry-run"]
    print("Preview from the existing installer:", flush=True)
    status = _run_selected(selected, preview)
    if status or preview_only:
        return status
    try:
        approved = input("Apply this selection? [y/N]: ").strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print("Cancelled before apply.", file=sys.stderr)
        return 130
    if not approved:
        print("Cancelled before apply.")
        return 0
    return _run_selected(selected, forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
