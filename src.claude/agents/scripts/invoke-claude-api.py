#!/usr/bin/env python3
"""Launch Claude with commercial API transport settings from ``SECRET.md``."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def usage() -> str:
    return """\
Usage:
  python .claude/agents/scripts/invoke-claude-api.py [claude args...]
  python .claude/agents/scripts/invoke-claude-api.py --print-secret-path

Environment overrides:
  CLAUDE_SECRET_FILE   Explicit SECRET.md path to use
  CLAUDE_BIN           Claude executable or absolute path to invoke
"""


def add_candidate(candidates: list[Path], value: str | os.PathLike[str] | None) -> None:
    if not value:
        return
    candidate = Path(os.path.expandvars(os.path.expanduser(str(value)))).resolve(
        strict=False
    )
    if candidate not in candidates:
        candidates.append(candidate)


def secret_candidates() -> list[Path]:
    script_dir = Path(__file__).resolve().parent
    pack_root = script_dir.parent.parent
    candidates: list[Path] = []
    add_candidate(candidates, os.environ.get("CLAUDE_SECRET_FILE"))
    add_candidate(candidates, Path.cwd() / ".claude" / "SECRET.md")
    if pack_root.name.lower() == ".claude":
        add_candidate(candidates, pack_root / "SECRET.md")
    elif pack_root.name.lower() == "src.claude":
        add_candidate(candidates, pack_root.parent / ".claude" / "SECRET.md")
    add_candidate(candidates, Path.home() / ".claude" / "SECRET.md")
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        add_candidate(candidates, Path(userprofile) / ".claude" / "SECRET.md")
    return candidates


def extract_secret_object(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8-sig")
    payload = raw.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fenced:
        payload = fenced.group(1).strip()
    elif not payload.startswith(("{", "[")):
        first = raw.find("{")
        last = raw.rfind("}")
        if first < 0 or last <= first:
            raise ValueError(f"Could not extract JSON payload from '{path}'.")
        payload = raw[first : last + 1].strip()
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise ValueError(f"'{path}' must contain a JSON object.")
    environment = parsed.get("env", parsed)
    if not isinstance(environment, dict):
        raise ValueError(f"'{path}' must contain a JSON object or an 'env' object.")
    return environment


def resolve_claude_command() -> list[str] | None:
    requested = os.environ.get("CLAUDE_BIN")
    names = [requested] if requested else ["claude", "claude.exe", "claude.cmd"]
    for name in names:
        if not name:
            continue
        candidate = Path(name).expanduser()
        resolved = str(candidate.resolve()) if candidate.is_file() else shutil.which(name)
        if not resolved:
            continue
        suffix = Path(resolved).suffix.lower()
        if suffix == ".ps1":
            powershell = (
                shutil.which("pwsh")
                or shutil.which("pwsh.exe")
                or shutil.which("powershell")
                or shutil.which("powershell.exe")
            )
            if not powershell:
                return None
            return [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                resolved,
            ]
        return [resolved]
    return None


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--help" in arguments or "-h" in arguments:
        print(usage(), end="")
        return 0
    print_path = any(
        value in {"--print-secret-path", "-PrintSecretPath"} for value in arguments
    )
    forwarded = [
        value
        for value in arguments
        if value not in {"--print-secret-path", "-PrintSecretPath"}
    ]

    candidates = secret_candidates()
    secret_path = next((path for path in candidates if path.is_file()), None)
    if secret_path is None:
        print(
            "FAIL: no Claude SECRET.md found. Checked: "
            + ", ".join(str(path) for path in candidates),
            file=sys.stderr,
        )
        return 1
    if print_path:
        print(secret_path)
        return 0

    try:
        secret_env = extract_secret_object(secret_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    required = ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN")
    missing = [key for key in required if not str(secret_env.get(key, "")).strip()]
    if missing:
        print(
            f"FAIL: SECRET.md '{secret_path}' is missing required Claude "
            f"transport keys: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1

    command = resolve_claude_command()
    if command is None:
        label = os.environ.get("CLAUDE_BIN") or "claude"
        print(
            f"FAIL: Claude executable '{label}' is not available. Set CLAUDE_BIN "
            "to an executable or absolute path if it is not on the active shell PATH.",
            file=sys.stderr,
        )
        return 1

    environment = os.environ.copy()
    for key, value in secret_env.items():
        if str(key).strip():
            environment[str(key)] = "" if value is None else str(value)
    try:
        return subprocess.run(command + forwarded, env=environment, check=False).returncode
    except OSError as exc:
        print(f"FAIL: Claude launch failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
