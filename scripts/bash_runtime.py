#!/usr/bin/env python3
"""Resolve a host-native Bash, rejecting Windows Subsystem for Linux shims."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def _is_windows_wsl_bash(path: Path) -> bool:
    normalized = str(path.resolve(strict=False)).replace("/", "\\").casefold()
    windows_roots = {
        str(Path(value).resolve(strict=False)).replace("/", "\\").rstrip("\\").casefold()
        for value in (
            os.environ.get("SystemRoot"),
            os.environ.get("windir"),
            r"C:\Windows",
        )
        if value
    }
    return any(
        normalized == root or normalized.startswith(root + "\\")
        for root in windows_roots
    ) or "\\microsoft\\windowsapps\\" in normalized


def _path_applications(names: tuple[str, ...]) -> list[Path]:
    candidates: list[Path] = []
    seen: set[str] = set()
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        for name in names:
            candidate = Path(directory) / name
            key = str(candidate).casefold()
            if key in seen or not candidate.is_file():
                continue
            seen.add(key)
            candidates.append(candidate)
    return candidates


def resolve_bash() -> Path | None:
    if os.name != "nt":
        found = shutil.which("bash")
        return Path(found) if found else None

    candidates: list[Path] = []
    git = shutil.which("git")
    if git:
        git_path = Path(git).resolve()
        install_root = git_path.parent.parent
        candidates.extend(
            (
                install_root / "bin" / "bash.exe",
                install_root / "usr" / "bin" / "bash.exe",
                install_root / "usr" / "bin" / "sh.exe",
            )
        )
        if install_root.name.casefold() in {"mingw64", "mingw32", "usr"}:
            parent = install_root.parent
            candidates.extend(
                (
                    parent / "bin" / "bash.exe",
                    parent / "usr" / "bin" / "bash.exe",
                    parent / "usr" / "bin" / "sh.exe",
                )
            )
    candidates.extend(_path_applications(("bash.exe", "bash", "sh.exe", "sh")))
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(variable)
        if base:
            candidates.extend(
                (
                    Path(base) / "Git" / "bin" / "bash.exe",
                    Path(base) / "Git" / "usr" / "bin" / "bash.exe",
                )
            )
    return next(
        (
            candidate
            for candidate in candidates
            if candidate.is_file() and not _is_windows_wsl_bash(candidate)
        ),
        None,
    )


def validation_cwd(script: Path, fallback_parent_count: int) -> Path:
    """Match the retired Windows launchers' repository/runtime cwd contract."""
    git = shutil.which("git")
    if git:
        probe = subprocess.run(
            [git, "rev-parse", "--show-toplevel"],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if probe.returncode == 0 and probe.stdout.strip():
            root = Path(probe.stdout.splitlines()[0].strip())
            if root.is_dir():
                return root
    candidate = script.parent
    for _ in range(fallback_parent_count):
        candidate = candidate.parent
    return candidate
