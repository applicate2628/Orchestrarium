#!/usr/bin/env python3
"""Fail-closed publication-safety scanner for tracked, range, and path inputs."""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path


SCANNER_BASENAME = "check-publication-safety.py"
_SIMPLE_PATTERNS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    re.compile(r"ANTHROPIC_[A-Z_]*(?:KEY|TOKEN)[^A-Za-z0-9_]?\s*[:=]"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"BEGIN RSA PRIVATE KEY"),
    re.compile(r"BEGIN OPENSSH PRIVATE KEY"),
    re.compile(r"BEGIN PRIVATE KEY"),
    re.compile(r"private_key"),
    re.compile(r"secret_key"),
    re.compile(r"/private/var/folders/"),
    re.compile(r"/var/folders/"),
    re.compile(r"^Human:\s*"),
    re.compile(r"^Assistant:\s*"),
    re.compile(r"^\$\s+"),
    re.compile(r"^>>>\s+"),
    re.compile(r"\[[0-9]{2}:[0-9]{2}:[0-9]{2}\]"),
)
_VALUE = r"[A-Za-z0-9_./+=-]"
_DIGIT_SHAPE = rf"(?:{_VALUE}{{5,}}[0-9]{_VALUE}*|{_VALUE}*[0-9]{_VALUE}{{5,}})"
_QUOTED = rf"""["'`!@#$%^&*?|](?:{_VALUE}{{12,}}|{_DIGIT_SHAPE})["'`!@#$%^&*?|]"""
_BARE = rf"(?:[A-Za-z0-9_+/=-]{{5,}}[0-9][A-Za-z0-9_+/=-]*|[A-Za-z0-9_+/=-]*[0-9][A-Za-z0-9_+/=-]{{5,}})"
_KEYWORDS = (
    ("password", "Password"),
    ("secret", "Secret"),
    ("token", "Token"),
    (r"api[_-]?key", "ApiKey"),
)
_VALUE_PATTERNS = tuple(
    re.compile(
        rf"(?:(?<![A-Za-z])(?i:{keyword})|(?<=[a-z]){camel})"
        rf"\s*[:=]\s*(?:{_QUOTED}|{_BARE})",
    )
    for keyword, camel in _KEYWORDS
)
_SCANNER_REGEX_CATALOG_LINE = re.compile(
    r"""re\.compile\([rubfRUBF]*(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')\),?"""
)


def _run_git(args: list[str], *, text: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
    )


def _repo_root() -> Path:
    proc = _run_git(["rev-parse", "--show-toplevel"], text=True)
    if proc.returncode:
        raise RuntimeError("not inside a git repository")
    return Path(proc.stdout.strip())


def _load_path_finder(script: Path):
    module_path = script.parent.parent / "hooks" / "check-machine-local-path.py"
    spec = importlib.util.spec_from_file_location("_publication_path_owner", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load path owner: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.find_machine_paths


def _intentional_scanner_line(line: str) -> bool:
    stripped = line.strip()
    return (
        not stripped
        or stripped.startswith("#")
        or _SCANNER_REGEX_CATALOG_LINE.fullmatch(stripped) is not None
    )


def _content_hits(text: str, path: str, find_machine_paths) -> list[str]:
    findings: list[str] = []
    scanner = Path(path).name == SCANNER_BASENAME
    for line_number, line in enumerate(text.splitlines(), 1):
        if scanner and _intentional_scanner_line(line):
            continue
        for pattern in (*_SIMPLE_PATTERNS, *_VALUE_PATTERNS):
            if pattern.search(line):
                findings.append(f"{path}:{line_number}: tracked-content marker")
                break
        machine_paths = find_machine_paths(line)
        if machine_paths:
            findings.append(
                f"{path}:{line_number}: machine-local path: {', '.join(machine_paths[:5])}"
            )
    return findings


def _is_binary(raw: bytes) -> bool:
    return b"\0" in raw


def _tracked_files() -> tuple[list[str], dict[str, bytes]]:
    names = _run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMRTUXB", "-z", "--"])
    if names.returncode:
        raise RuntimeError("could not enumerate staged tracked files")
    paths = [part.decode("utf-8", "surrogateescape") for part in names.stdout.split(b"\0") if part]
    blobs: dict[str, bytes] = {}
    for path in paths:
        proc = _run_git(["show", f":{path}"])
        if proc.returncode:
            raise RuntimeError(f"could not read staged content for {path!r}")
        blobs[path] = proc.stdout
    return paths, blobs


def _range_files(remote: str) -> tuple[str, list[str], dict[str, bytes]]:
    remotes = _run_git(["remote"], text=True)
    configured = [line for line in remotes.stdout.splitlines() if line]
    if remotes.returncode or remote not in configured:
        raise ValueError(
            f"range: argument is not a configured remote name ({len(configured)} remotes configured); refusing"
        )
    tip_proc = _run_git(["rev-parse", "HEAD"], text=True)
    if tip_proc.returncode:
        raise ValueError("range: could not resolve HEAD to a commit; refusing")
    tip = tip_proc.stdout.strip()
    names = _run_git(["log", "--format=", "--name-only", "--diff-filter=ACMRT", tip, "--not", f"--remotes={remote}"], text=True)
    if names.returncode:
        raise RuntimeError("range: could not enumerate unpublished files")
    candidates = list(dict.fromkeys(line for line in names.stdout.splitlines() if line))
    paths: list[str] = []
    blobs: dict[str, bytes] = {}
    for path in candidates:
        proc = _run_git(["show", f"{tip}:{path}"])
        if proc.returncode or _is_binary(proc.stdout):
            continue
        paths.append(path)
        blobs[path] = proc.stdout
    return tip, paths, blobs


def _path_files(raw_path: str) -> tuple[list[str], dict[str, bytes]]:
    source = Path(raw_path)
    paths = sorted(p for p in source.rglob("*") if p.is_file()) if source.is_dir() else [source]
    blobs: dict[str, bytes] = {}
    labels: list[str] = []
    for path in paths:
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise RuntimeError(f"could not read path content for {str(path)!r}") from exc
        label = str(path)
        labels.append(label)
        blobs[label] = raw
    return labels, blobs


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan publication content for secrets and machine-local paths."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--path")
    group.add_argument("--range", nargs=2, metavar=("REMOTE", "DST"))
    parser.add_argument("legacy_path", nargs="?")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.legacy_path and (args.path or args.range):
        _parser().error("unexpected extra path argument")
    script = Path(__file__).resolve()
    try:
        repo_root = _repo_root()
        os.chdir(repo_root)
        find_machine_paths = _load_path_finder(script)
        mode = "tracked"
        receipt = ""
        if args.range:
            mode = "range"
            remote, dst = args.range
            tip, paths, blobs = _range_files(remote)
            receipt = f", remote {remote}, dst {dst}, tip {tip}"
        elif args.path or args.legacy_path:
            mode = "path"
            paths, blobs = _path_files(args.path or args.legacy_path)
        else:
            paths, blobs = _tracked_files()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"publication-safety: {exc}; refusing", file=sys.stderr)
        return 2

    findings: list[str] = []
    for path in paths:
        base = Path(path).name
        if base == ".env":
            findings.append(f"{path}: blocked filename .env (staged secret/config file)")
        if base.casefold() == "secret.md":
            findings.append(f"{path}: blocked filename {base} (staged credential file; keep it untracked)")
        if _is_binary(blobs[path]):
            continue
        text = blobs[path].decode("utf-8", "replace")
        findings.extend(_content_hits(text, path, find_machine_paths))

    if findings:
        for finding in findings:
            print(finding, file=sys.stderr)
        print("publication-safety scan found potential tracked-content leak markers", file=sys.stderr)
        return 1

    count = len(paths)
    noun = "file" if count == 1 else "files"
    if count == 0 and mode == "tracked":
        print("publication-safety: clean (tracked, examined 0 files -- nothing staged)")
    elif count == 0 and mode == "range":
        print("publication-safety: clean (range, examined 0 files -- nothing to publish)")
    else:
        print(f"publication-safety: clean ({mode}, examined {count} {noun}{receipt})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
