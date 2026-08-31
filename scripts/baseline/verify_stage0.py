#!/usr/bin/env python3
"""Load the reviewed modular Stage 0 verifier without ambient import paths."""
from __future__ import annotations

import importlib.util
import os
import stat
import sys
from pathlib import Path


def _load(name: str, filename: str):
    path = Path(__file__).resolve().with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Stage 0 module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_runtime = _load("stage0_runtime", "stage0_runtime.py")


def _validate_shared_temporary_parent(path: Path, metadata) -> None:
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise _runtime.VerificationError(
            f"private temporary parent must be a real directory: {path}"
        )
    if metadata.st_uid != 0:
        raise _runtime.VerificationError(
            f"shared temporary parent must be owned by root: {path}"
        )
    if not metadata.st_mode & stat.S_ISVTX:
        raise _runtime.VerificationError(
            f"shared temporary parent must have the sticky bit set: {path}"
        )


def _safe_private_temp_parent() -> Path:
    parent = Path("/tmp")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        lexical = parent.lstat()
        descriptor = os.open(parent, flags)
    except OSError as exc:
        raise _runtime.VerificationError(
            f"cannot securely open private temporary parent {parent}: {exc}"
        ) from exc
    try:
        opened = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    _validate_shared_temporary_parent(parent, lexical)
    _validate_shared_temporary_parent(parent, opened)
    lexical_identity = (
        lexical.st_dev,
        lexical.st_ino,
        lexical.st_mode,
        lexical.st_uid,
        lexical.st_gid,
    )
    opened_identity = (
        opened.st_dev,
        opened.st_ino,
        opened.st_mode,
        opened.st_uid,
        opened.st_gid,
    )
    if lexical_identity != opened_identity:
        raise _runtime.VerificationError(
            f"private temporary parent changed while being opened: {parent}"
        )
    resolved = parent.resolve(strict=True)
    try:
        resolved_metadata = resolved.lstat()
    except OSError as exc:
        raise _runtime.VerificationError(
            f"cannot revalidate private temporary parent {resolved}: {exc}"
        ) from exc
    resolved_identity = (
        resolved_metadata.st_dev,
        resolved_metadata.st_ino,
        resolved_metadata.st_mode,
        resolved_metadata.st_uid,
        resolved_metadata.st_gid,
    )
    if resolved_identity != opened_identity:
        raise _runtime.VerificationError(
            f"private temporary parent identity changed during resolution: {parent}"
        )
    return resolved


def _install_full_suite_gates() -> None:
    existing_names = {item.name for item in _runtime.VALIDATORS}
    required_names = {"pytest-full-suite", "unittest-full-suite"}
    overlap = sorted(existing_names & required_names)
    if overlap:
        raise _runtime.VerificationError(
            f"duplicate Stage 0 full-suite validator names: {overlap}"
        )
    full_suite = (
        _runtime.ValidatorSpec(
            "pytest-full-suite",
            "python",
            (
                "-B",
                "-m",
                "pytest",
                "-q",
                "--tb=no",
                "--disable-warnings",
                "tests/",
            ),
            (
                r"(?m)^(?!.*(?:failed|error|errors)).*\b"
                r"(?:passed|skipped|xfailed|xpassed|deselected)\b.* in <VOLATILE>$"
            ),
            r"(?m)^.*\b(?:failed|error|errors)\b.* in <VOLATILE>$",
            (
                r"(?m)^(?:[.sfxXEF]+[ ]+\[[ 0-9]+%\]\n?)+",
                r"\b\d+ (?=(?:passed|failed|errors?|skipped|xfailed|xpassed|deselected|warnings?)\b)",
                r"\b\d+(?:\.\d+)?s\b",
            ),
        ),
        _runtime.ValidatorSpec(
            "unittest-full-suite",
            "python",
            (
                "-B",
                "-m",
                "unittest",
                "discover",
                "-q",
                "-s",
                "tests",
                "-p",
                "test_*.py",
            ),
            (
                r"(?ms)^Ran <VOLATILE> tests? in <VOLATILE>\n\n"
                r"OK(?: \((?:skipped|expected failures)=<VOLATILE>"
                r"(?:, (?:skipped|expected failures)=<VOLATILE>)*\))?$"
            ),
            r"(?m)^FAILED \(.*\)$",
            (
                r"(?m)(?<=^Ran )[1-9]\d*(?= tests? in )",
                r"(?<==)[1-9]\d*",
                r"\b\d+(?:\.\d+)?s\b",
            ),
        ),
    )
    _runtime.VALIDATORS = (*full_suite, *_runtime.VALIDATORS)


_install_full_suite_gates()
_evidence = _load("stage0_evidence", "stage0_evidence.py")
_evidence._private_temp_parent = _safe_private_temp_parent
_orchestrator = _load("stage0_orchestrator", "stage0_orchestrator.py")
for _module in (_runtime, _evidence, _orchestrator):
    for _name, _value in vars(_module).items():
        if not _name.startswith("__"):
            globals()[_name] = _value

# Keep the hardened owner authoritative after re-exporting the legacy module.
_private_temp_parent = _safe_private_temp_parent

if __name__ == "__main__":
    raise SystemExit(main())
