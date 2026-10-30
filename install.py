#!/usr/bin/env python3
"""Interactive root installer; production choices dispatch to Python owners."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from python_installer_bootstrap import ensure_supported_python
from installation.clients import CLIENTS as CLIENT_CATALOG

ensure_supported_python(str(Path(__file__).resolve()))


def _run_production(name: str, forwarded: list[str]) -> int:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "install-client.py"), "--client", name, *forwarded],
        cwd=ROOT,
    ).returncode


CLIENTS = tuple((name, spec["label"]) for name, spec in CLIENT_CATALOG.items())


def _show_clients() -> None:
    print("Orche — choose client integrations")
    for index, (name, label) in enumerate(CLIENTS, 1):
        detected = "command detected" if shutil.which(name) else "command not detected"
        print(f"  [ ] {index}) {label} ({name}; {detected})")
    print("Detection is informational; installation does not log in or run models.")


def _run_selected(selected: tuple[str, ...], forwarded: list[str]) -> int:
    preview = any(flag in forwarded for flag in ("--dry-run", "-DryRun")) or (
        any(flag in forwarded for flag in ("--uninstall", "--materialize-legacy-skills"))
        and "--apply" not in forwarded
    )
    for index, name in enumerate(selected):
        status = _run_production(name, forwarded)
        label = ("PREVIEW COMPLETE" if preview else "COMPLETE") if status == 0 else "STOPPED"
        print(f"{name}: {label} ({status})")
        if status:
            # Exit 2 can mean partial removal or invalid arguments. The
            # operation's own report establishes which; do not invent success.
            print("See the installer report above for the result and recovery steps.")
            for pending in selected[index + 1:]:
                print(f"{pending}: NOT ATTEMPTED")
            return status  # Preserve the existing fail-fast operation order.
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Orche client selection; remaining flags go to the existing installer.",
        epilog="Use --global for your account, --dry-run for preview, or --uninstall for removal preview. "
               "For all lifecycle options: python scripts/install-client.py --client codex --help. "
               "Without --global or --target, the existing installer uses repository scope.",
        allow_abbrev=False,
    )
    parser.add_argument("--clients", nargs="+", choices=[name for name, _ in CLIENTS])
    parser.add_argument("--list-clients", action="store_true")
    options, forwarded = parser.parse_known_args(sys.argv[1:] if argv is None else argv)
    if options.list_clients:
        _show_clients()
        return 0
    if options.clients is not None:
        selected = tuple(name for name, _ in CLIENTS if name in options.clients)
        return _run_selected(selected, forwarded)
    if not sys.stdin.isatty():
        print("No interactive terminal: specify --clients codex and/or claude. Nothing applied.", file=sys.stderr)
        return 2
    _show_clients()
    try:
        choice = input("Select numbers (e.g. 1,2), a = all, q/empty = cancel: ").strip().lower()
        if choice in ("", "q"):
            return 0
        tokens = choice.replace(",", " ").split()
        if choice in ("a", "all"):
            selected = tuple(name for name, _ in CLIENTS)
        elif tokens and all(token in {"1", "2"} for token in tokens):
            selected = tuple(name for index, (name, _) in enumerate(CLIENTS, 1) if str(index) in tokens)
        else:
            print("Invalid selection. Nothing applied.", file=sys.stderr)
            return 2
        print("Selected: " + ", ".join(selected))
        print("Preview from the existing installer:")
        dry_run = any(flag in forwarded for flag in ("--dry-run", "-DryRun"))
        preview = forwarded if dry_run else [*forwarded, "--dry-run"]
        status = _run_selected(selected, preview)
        if status or dry_run:
            return status
        if input("Apply this selection? [y/N]: ").strip().lower() not in ("y", "yes"):
            return 0
        if any(flag in forwarded for flag in ("--uninstall", "--materialize-legacy-skills")) and "--apply" not in forwarded:
            forwarded = [*forwarded, "--apply"]
        return _run_selected(selected, forwarded)
    except (EOFError, KeyboardInterrupt):
        print("Cancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
