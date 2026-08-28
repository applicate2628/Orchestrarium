#!/usr/bin/env python3
"""Launch Claude with commercial API transport settings from ``SECRET.md``."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
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


E_EXTERNAL_PROVIDER_REPOSITORY_EXECUTABLE = "E_EXTERNAL_PROVIDER_REPOSITORY_EXECUTABLE"


@dataclass(frozen=True)
class ResolvedClaudeCommand:
    command: tuple[str, ...]
    target: Path
    provenance: str
    path_discovered_targets: tuple[Path, ...]


def resolve_claude_command() -> ResolvedClaudeCommand | None:
    # This standalone installed wrapper cannot import the independently
    # projected provider_prompt.py owner. Keep this small contract aligned.
    requested = os.environ.get("CLAUDE_BIN")
    names = [requested] if requested else ["claude", "claude.exe", "claude.cmd"]
    for name in names:
        if not name:
            continue
        candidate = Path(name).expanduser()
        provenance = (
            "explicit-absolute-binding"
            if requested is not None and candidate.is_absolute()
            else "path-discovery"
        )
        discovered = candidate if provenance == "explicit-absolute-binding" else shutil.which(name)
        if not discovered:
            continue
        try:
            target = Path(discovered).resolve(strict=True)
        except OSError:
            continue
        if not target.is_file():
            continue
        path_discovered_targets = (target,) if provenance == "path-discovery" else ()
        suffix = target.suffix.lower()
        if suffix == ".ps1":
            powershell = (
                shutil.which("pwsh")
                or shutil.which("pwsh.exe")
                or shutil.which("powershell")
                or shutil.which("powershell.exe")
            )
            if not powershell:
                return None
            try:
                powershell_target = Path(powershell).resolve(strict=True)
            except OSError:
                return None
            if not powershell_target.is_file():
                return None
            command = (
                str(powershell_target),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(target),
            )
            path_discovered_targets += (powershell_target,)
        elif suffix == ".py":
            command = (sys.executable, str(target))
        else:
            command = (str(target),)
        return ResolvedClaudeCommand(
            command, target, provenance, path_discovered_targets
        )
    return None


def _physical_repository_root(query_cwd: Path) -> Path | None:
    physical_cwd = query_cwd.resolve(strict=True)
    for candidate in (physical_cwd, *physical_cwd.parents):
        if os.path.lexists(candidate / ".git"):
            return candidate
    return None


def _reject_repository_path_discovery(
    resolution: ResolvedClaudeCommand, query_cwd: Path
) -> None:
    repository_root = _physical_repository_root(query_cwd)
    if repository_root is None:
        return
    for target in resolution.path_discovered_targets:
        try:
            target.relative_to(repository_root)
        except ValueError:
            continue
        raise ValueError(
            f"{E_EXTERNAL_PROVIDER_REPOSITORY_EXECUTABLE}: "
            "PATH-discovered provider executable is inside the active repository"
        )


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
        query_cwd = Path.cwd().resolve(strict=True)
        resolution = resolve_claude_command()
        if resolution is None:
            label = os.environ.get("CLAUDE_BIN") or "claude"
            print(
                f"FAIL: Claude executable '{label}' is not available. Set CLAUDE_BIN "
                "to an executable or absolute path if it is not on the active shell PATH.",
                file=sys.stderr,
            )
            return 1
        _reject_repository_path_discovery(resolution, query_cwd)
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

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

    environment = os.environ.copy()
    for key, value in secret_env.items():
        if str(key).strip():
            environment[str(key)] = "" if value is None else str(value)
    try:
        return subprocess.run(
            list(resolution.command) + forwarded, env=environment, check=False
        ).returncode
    except OSError as exc:
        print(f"FAIL: Claude launch failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
