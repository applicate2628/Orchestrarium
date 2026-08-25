#!/usr/bin/env python3
"""Create and verify a deterministic, byte-only local overlay for a Git repository."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit


SCHEMA_VERSION = 1
TRANSFER_ROOT = "_repo-transfer"
MANIFEST_PATH = f"{TRANSFER_ROOT}/manifest.json"
METADATA_NAMES = (
    f"{TRANSFER_ROOT}/git-status.bin",
    f"{TRANSFER_ROOT}/git-staged.diff",
    f"{TRANSFER_ROOT}/git-unstaged.diff",
)
DELETE_PROOF_KINDS = {"regenerate", "git-recoverable", "canonical-summary"}
WINDOWS_RESERVED = {
    "CON",
    "CONIN$",
    "CONOUT$",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{x}" for x in range(1, 10)),
    *(f"LPT{x}" for x in range(1, 10)),
}
MAX_ARCHIVE_ENTRIES = 10_000
MAX_ARCHIVE_ENTRY_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_COMPRESSION_RATIO = 100
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_JSON_DEPTH = 64
MAX_ARCHIVE_CENTRAL_DIRECTORY_BYTES = 8 * 1024 * 1024
GIT_COMMAND_TIMEOUT_SECONDS = 60


class ContractError(Exception):
    pass


class BoundRepository:
    def __init__(self, root: Path, git_executable: Path, git_executable_sha256: str) -> None:
        self.root = root
        self.git_executable = git_executable
        self.git_executable_sha256 = git_executable_sha256


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def capped_canonical_json(value: Any, error_message: str, *, final_newline: bool = False) -> bytes:
    suffix = b"\n" if final_newline else b""
    encoded = bytearray()
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    for fragment in encoder.iterencode(value):
        chunk = fragment.encode("utf-8")
        if len(encoded) + len(chunk) + len(suffix) > MAX_JSON_BYTES:
            raise ContractError(error_message)
        encoded.extend(chunk)
    encoded.extend(suffix)
    return bytes(encoded)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stream_digest(stream: Any) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        size += len(chunk)
        digest.update(chunk)
    return size, digest.hexdigest()


def sanitized_git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for key in list(environment):
        if key.startswith("GIT_"):
            environment.pop(key)
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    return environment


def base_git_configuration() -> list[str]:
    return ["-c", "core.fsmonitor=false", "-c", "diff.external="]


def _drain_stream_bounded(stream: Any, limit: int) -> tuple[bytes, bool, Exception | None]:
    captured = bytearray(limit + 1)
    size = 0
    overflow = False
    try:
        for chunk in iter(lambda: stream.read(64 * 1024), b""):
            remaining = len(captured) - size
            if remaining:
                copied = min(remaining, len(chunk))
                captured[size:size + copied] = chunk[:copied]
                size += copied
            if size > limit or len(chunk) > remaining:
                overflow = True
    except Exception as error:
        return b"", False, error
    return bytes(captured[:size]), overflow, None


def run_bounded_process(command: list[str], repository: Path | None, environment: dict[str, str]) -> subprocess.CompletedProcess[bytes]:
    try:
        process = subprocess.Popen(
            command,
            cwd=repository,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
        )
    except OSError as error:
        raise ContractError("not a git repository") from error
    assert process.stdout is not None and process.stderr is not None
    captures: list[tuple[bytes, bool, Exception | None] | None] = [None, None]

    def drain(index: int, stream: Any) -> None:
        captures[index] = _drain_stream_bounded(stream, MAX_JSON_BYTES)

    stdout_thread = threading.Thread(target=drain, args=(0, process.stdout))
    stderr_thread = threading.Thread(target=drain, args=(1, process.stderr))
    stdout_thread.start()
    stderr_thread.start()
    timed_out = False
    try:
        return_code = process.wait(timeout=GIT_COMMAND_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        return_code = process.wait()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        stdout_thread.join()
        stderr_thread.join()
        process.stdout.close()
        process.stderr.close()
    stdout_capture, stderr_capture = captures
    assert stdout_capture is not None and stderr_capture is not None
    stdout, stdout_overflow, stdout_error = stdout_capture
    stderr, stderr_overflow, stderr_error = stderr_capture
    if stdout_error is not None or stderr_error is not None:
        raise ContractError("git output capture failed")
    if timed_out:
        raise ContractError("git command timed out")
    if stdout_overflow or stderr_overflow:
        raise ContractError("git output exceeds JSON limit")
    return subprocess.CompletedProcess(command, return_code, stdout, stderr)


def local_filter_drivers(repository: Path, git_executable: Path) -> list[str]:
    command = [
        str(git_executable),
        *base_git_configuration(),
        "config",
        "--includes",
        "--name-only",
        "--get-regexp",
        "^filter\\.",
    ]
    result = run_bounded_process(command, repository, sanitized_git_environment())
    if result.returncode not in {0, 1}:
        raise ContractError(result.stderr.decode("utf-8", "replace").strip() or "not a git repository")
    drivers: set[str] = set()
    for key in result.stdout.decode("utf-8", "replace").splitlines():
        match = re.fullmatch(r"filter\.(.+)\.(?:clean|smudge|process|required)", key)
        if match:
            drivers.add(match.group(1))
    return sorted(drivers)


def run_git(repository: Path, git_executable: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    filter_configuration: list[str] = []
    for driver in local_filter_drivers(repository, git_executable):
        for setting, value in (("clean", ""), ("smudge", ""), ("process", ""), ("required", "false")):
            filter_configuration.extend(["-c", f"filter.{driver}.{setting}={value}"])
    command = [str(git_executable), *base_git_configuration(), *filter_configuration, *arguments]
    result = run_bounded_process(command, repository, sanitized_git_environment())
    if check and result.returncode:
        message = result.stderr.decode("utf-8", "replace").strip() or "not a git repository"
        raise ContractError(message)
    return result


def ordinary_absolute_file(path: Path, label: str) -> Path:
    if not path.is_absolute():
        raise ContractError(f"{label} must be an absolute path")
    absolute = Path(os.path.abspath(path))
    if not absolute.is_file():
        raise ContractError(f"{label} must be an ordinary file")
    if is_reparse_point(absolute):
        raise ContractError(f"{label} must not be a reparse point")
    return absolute


def require_git_executable(git_executable: Path, untrusted_root: Path) -> Path:
    executable = ordinary_absolute_file(git_executable, "git executable")
    root = Path(os.path.abspath(untrusted_root))
    try:
        executable.relative_to(root)
    except ValueError:
        return executable
    raise ContractError("git executable must be outside the repository")


def bind_repository(repository: Path, git_executable: Path) -> BoundRepository:
    untrusted_root = Path(os.path.abspath(repository))
    executable = require_git_executable(git_executable, untrusted_root)
    try:
        result = run_bounded_process(
            [str(executable), *base_git_configuration(), "rev-parse", "--show-toplevel"],
            untrusted_root,
            sanitized_git_environment(),
        )
        if result.returncode:
            raise ContractError(result.stderr.decode("utf-8", "replace").strip() or "not a git repository")
        root = Path(result.stdout.decode("utf-8").strip()).resolve()
        require_git_executable(executable, root)
        return BoundRepository(root, executable, sha256_file(executable))
    except (OSError, ValueError, UnicodeError) as error:
        raise ContractError("not a git repository") from error


def require_outside_repository(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return resolved
    raise ContractError(f"{label} must be outside repository")


def is_reparse_point(path: Path) -> bool:
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return True
    return path.is_symlink() or bool(attributes & 0x400)


def link_metadata(path: Path) -> tuple[str, str]:
    try:
        target = os.readlink(path)
    except OSError:
        try:
            target = str(path.resolve())
        except OSError:
            target = "<unresolved-reparse-target>"
    if path.is_symlink():
        kind = "symlink"
    elif path.is_dir():
        kind = "junction"
    else:
        kind = "reparse"
    return target, kind


def portable_path_issue(path: str) -> str | None:
    portable = PurePosixPath(path)
    if not path or portable.is_absolute():
        return "path traversal"
    for raw_segment in path.split("/"):
        segment = unicodedata.normalize("NFKC", raw_segment)
        normalized = segment.rstrip(". ")
        if not segment or segment in {".", ".."} or "/" in segment or "\\" in segment or normalized != segment:
            return "trailing dot or space"
        if portable_segment_key(segment) == ".git":
            return "reserved Git path"
        device_basename = normalized.split(".", 1)[0].upper()
        device_basename = device_basename.translate(str.maketrans({"¹": "1", "²": "2", "³": "3"}))
        if device_basename in WINDOWS_RESERVED:
            return "Windows reserved name"
        if any(ord(character) < 32 or character in '<>:"|?*' for character in segment):
            return "portable hostile segment"
    return None


def portable_path_key(path: str) -> str:
    return unicodedata.normalize("NFKC", path).casefold()


def portable_segment_key(segment: str) -> str:
    return unicodedata.normalize("NFKC", segment).casefold()


def portable_path_parts(path: str) -> tuple[str, ...]:
    return tuple(portable_segment_key(part) for part in PurePosixPath(unicodedata.normalize("NFKC", path)).parts)


def portable_path_covers(parent: tuple[str, ...], child: tuple[str, ...]) -> bool:
    return len(parent) <= len(child) and child[:len(parent)] == parent


class PortablePathTree:
    def __init__(self) -> None:
        self._root: dict[str, Any] = {"terminal": False, "children": {}}

    def add(self, path: str) -> bool:
        node = self._root
        for part in portable_path_parts(path):
            if node["terminal"]:
                return False
            node = node["children"].setdefault(part, {"terminal": False, "children": {}})
        if node["terminal"] or node["children"]:
            return False
        node["terminal"] = True
        return True


def portable_path_conflicts(paths: Iterable[str]) -> set[str]:
    ordered = sorted((portable_path_parts(path), path) for path in paths)
    conflicts: set[str] = set()
    previous_parts: tuple[str, ...] | None = None
    previous_path: str | None = None
    for parts, path in ordered:
        if previous_parts is not None and portable_path_covers(previous_parts, parts):
            conflicts.update((previous_path, path))
        previous_parts, previous_path = parts, path
    return conflicts


def is_transfer_path(path: str) -> bool:
    parts = portable_path_parts(path)
    return bool(parts) and parts[0] == portable_segment_key(TRANSFER_ROOT)


def safe_remote_url(raw_url: str) -> str:
    scp = re.match(r"^[^/@:]+@([^/:]+):(.+)$", raw_url)
    if scp:
        return f"ssh://{scp.group(1)}/{scp.group(2).lstrip('/')}"
    parsed = urlsplit(raw_url)
    if parsed.scheme.lower() in {"http", "https", "ssh"} and parsed.netloc:
        host = parsed.netloc.rsplit("@", 1)[-1]
        return urlunsplit((parsed.scheme, host, parsed.path, "", ""))
    return "<local-path>"


def nul_delimited_paths(result: subprocess.CompletedProcess[bytes]) -> set[str]:
    return {item.decode("utf-8", "surrogateescape") for item in result.stdout.split(b"\0") if item}


def remote_evidence(root: Path, git_executable: Path, head: str) -> tuple[list[dict[str, str]], dict[str, dict[str, Any]]]:
    remotes: list[dict[str, str]] = []
    evidence: dict[str, dict[str, Any]] = {}
    for name in run_git(root, git_executable, "remote").stdout.decode("utf-8").splitlines():
        raw_url = run_git(root, git_executable, "remote", "get-url", name, check=False).stdout.decode("utf-8", "replace").strip()
        reachable = False
        references = run_git(root, git_executable, "for-each-ref", "--format=%(refname)", f"refs/remotes/{name}/").stdout.decode("utf-8").splitlines()
        for reference in references:
            if run_git(root, git_executable, "merge-base", "--is-ancestor", head, reference, check=False).returncode == 0:
                reachable = True
                break
        remotes.append({"name": name, "url": safe_remote_url(raw_url)})
        evidence[name] = {"kind": "local-tracking", "headReachable": reachable}
    return remotes, evidence


def literal_pathspecs(paths: list[str]) -> list[str]:
    return [f":(literal){path}" for path in paths]


def git_metadata(root: Path, git_executable: Path, paths: list[str] | None = None) -> dict[str, bytes]:
    if paths == []:
        return {name: b"" for name in METADATA_NAMES}
    suffix = [] if paths is None else ["--", *literal_pathspecs(paths)]
    return {
        METADATA_NAMES[0]: run_git(root, git_executable, "status", "--no-renames", "--porcelain=v1", "-z", "--untracked-files=all", *suffix).stdout,
        METADATA_NAMES[1]: run_git(root, git_executable, "diff", "--no-renames", "--cached", "--binary", "--no-ext-diff", "--no-textconv", *suffix).stdout,
        METADATA_NAMES[2]: run_git(root, git_executable, "diff", "--no-renames", "--binary", "--no-ext-diff", "--no-textconv", *suffix).stdout,
    }


def walk_repository(root: Path) -> Iterable[tuple[str, Path, str]]:
    for current, directories, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        kept_directories: list[str] = []
        for name in sorted(directories):
            child = current_path / name
            relative = child.relative_to(root).as_posix()
            if name == ".git":
                continue
            if is_reparse_point(child):
                yield relative, child, "reparse"
            else:
                kept_directories.append(name)
        directories[:] = kept_directories
        for name in sorted(files):
            child = current_path / name
            if name == ".git":
                continue
            relative = child.relative_to(root).as_posix()
            yield relative, child, "reparse" if is_reparse_point(child) else "file"


def build_inventory(repository: BoundRepository) -> dict[str, Any]:
    root = repository.root
    git_executable = repository.git_executable
    index_tracked = nul_delimited_paths(run_git(root, git_executable, "ls-files", "-z"))
    head_tracked = nul_delimited_paths(run_git(root, git_executable, "ls-tree", "-r", "-z", "--name-only", "HEAD"))
    tracked = index_tracked | head_tracked
    ignored = nul_delimited_paths(run_git(root, git_executable, "ls-files", "--others", "--ignored", "--exclude-standard", "-z"))
    dirty = nul_delimited_paths(run_git(root, git_executable, "diff", "--no-renames", "--name-only", "-z", "HEAD"))
    flagged_tracked = {
        item[2:].decode("utf-8", "surrogateescape")
        for item in run_git(root, git_executable, "ls-files", "-v", "-z").stdout.split(b"\0")
        if len(item) > 2 and item[1:2] == b" " and (item[:1].islower() or item[:1].upper() == b"S")
    }
    dirty |= flagged_tracked
    head = run_git(root, git_executable, "rev-parse", "HEAD").stdout.decode("utf-8").strip()
    remotes, evidence = remote_evidence(root, git_executable, head)
    metadata_hashes = {name: sha256_bytes(data) for name, data in git_metadata(root, git_executable).items()}
    entries: list[dict[str, Any]] = []
    for relative, path, entry_type in walk_repository(root):
        git_class = "tracked" if relative in tracked else "ignored" if relative in ignored else "untracked"
        entry: dict[str, Any] = {"path": relative, "entryType": entry_type, "gitClass": git_class, "dirtyTracked": relative in dirty}
        if entry_type == "reparse":
            target, kind = link_metadata(path)
            entry.update(metadataOnly=True, linkTarget=target, linkKind=kind)
        else:
            entry.update(size=path.stat().st_size, sha256=sha256_file(path))
        if portable_path_issue(relative):
            entry.update(metadataOnly=True, hostile=True)
        entries.append(entry)
    present_paths = {entry["path"] for entry in entries}
    for relative in sorted(tracked & dirty - present_paths):
        entry = {"path": relative, "entryType": "deleted", "gitClass": "tracked", "dirtyTracked": True}
        if portable_path_issue(relative):
            entry.update(metadataOnly=True, hostile=True)
        entries.append(entry)
    colliding_paths = portable_path_conflicts(entry["path"] for entry in entries)
    for entry in entries:
        if entry["path"] in colliding_paths:
            entry.update(metadataOnly=True, hostile=True)
    entries.sort(key=lambda entry: entry["path"])
    repository_data = {"head": head, "remotes": remotes, "remoteEvidence": evidence, "gitExecutable": {"path": str(git_executable), "sha256": repository.git_executable_sha256}, "gitMetadataHashes": metadata_hashes}
    snapshot = {"entries": entries, "repository": repository_data}
    return {"schemaVersion": SCHEMA_VERSION, "repository": repository_data, "entries": entries, "snapshot": {"digest": sha256_bytes(canonical_json(snapshot))}}


def validate_json_depth(value: Any, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        raise ContractError("invalid JSON")
    if isinstance(value, dict):
        for child in value.values():
            validate_json_depth(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            validate_json_depth(child, depth + 1)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ContractError("invalid JSON")


def reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def read_json_bytes(data: bytes, label: str) -> dict[str, Any]:
    if len(data) > MAX_JSON_BYTES:
        raise ContractError(f"invalid {label}")
    try:
        def reject_duplicate_keys(items: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, item in items:
                if key in result:
                    raise ValueError("duplicate JSON key")
                result[key] = item
            return result
        value = json.loads(data.decode("utf-8"), parse_constant=reject_json_constant, object_pairs_hook=reject_duplicate_keys)
        validate_json_depth(value)
    except (UnicodeError, ValueError, RecursionError, ContractError) as error:
        raise ContractError(f"invalid {label}") from error
    if not isinstance(value, dict):
        raise ContractError(f"invalid {label}")
    return value


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            data = stream.read(MAX_JSON_BYTES + 1)
    except OSError as error:
        raise ContractError(f"invalid {label}") from error
    return read_json_bytes(data, label)


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def validate_inventory(inventory: dict[str, Any]) -> None:
    try:
        if not isinstance(inventory.get("snapshot"), dict) or not isinstance(inventory.get("repository"), dict) or not isinstance(inventory.get("entries"), list):
            raise TypeError
        expected = sha256_bytes(canonical_json({"entries": inventory["entries"], "repository": inventory["repository"]}))
    except (KeyError, TypeError, ValueError):
        raise ContractError("invalid inventory snapshot")
    repository = inventory["repository"]
    entries = inventory["entries"]
    if (
        inventory.get("schemaVersion") != SCHEMA_VERSION
        or inventory.get("snapshot", {}).get("digest") != expected
        or not isinstance(repository.get("head"), str)
        or not isinstance(repository.get("remotes"), list)
        or not isinstance(repository.get("remoteEvidence"), dict)
        or not isinstance(repository.get("gitExecutable"), dict)
        or not isinstance(repository.get("gitMetadataHashes"), dict)
    ):
        raise ContractError("inventory digest mismatch")
    for remote in repository["remotes"]:
        if not isinstance(remote, dict) or not isinstance(remote.get("name"), str) or not isinstance(remote.get("url"), str):
            raise ContractError("invalid inventory snapshot")
    for name, evidence in repository["remoteEvidence"].items():
        if not isinstance(name, str) or not isinstance(evidence, dict) or not isinstance(evidence.get("kind"), str) or not isinstance(evidence.get("headReachable"), bool):
            raise ContractError("invalid inventory snapshot")
    executable = repository["gitExecutable"]
    if not isinstance(executable.get("path"), str) or not is_sha256(executable.get("sha256")):
        raise ContractError("invalid inventory snapshot")
    if not all(isinstance(name, str) and is_sha256(digest) for name, digest in repository["gitMetadataHashes"].items()):
        raise ContractError("invalid inventory snapshot")
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str) or not isinstance(entry.get("dirtyTracked"), bool):
            raise ContractError("invalid inventory snapshot")
        if entry.get("entryType") not in {"file", "reparse", "deleted"} or entry.get("gitClass") not in {"tracked", "untracked", "ignored"}:
            raise ContractError("invalid inventory snapshot")
        if entry["entryType"] == "file" and (not isinstance(entry.get("size"), int) or entry["size"] < 0 or not is_sha256(entry.get("sha256"))):
            raise ContractError("invalid inventory snapshot")


def selection_path(root: Path, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError("selection path is invalid")
    portable = PurePosixPath(value)
    segments = value.split("/")
    if (
        "\\" in value
        or portable.is_absolute()
        or any(segment in {"", ".", ".."} or portable_segment_key(segment) == ".git" for segment in segments)
    ):
        raise ContractError(f"selection path escapes repository: {value}")
    return portable.as_posix()


def covers(parent: str, child: str) -> bool:
    return parent == child or child.startswith(parent + "/")


def covered_set_digest(entries: list[dict[str, Any]], selection: str) -> str:
    return sha256_bytes(canonical_json([entry for entry in entries if covers(selection, entry["path"])]))


def validate_selection(root: Path, inventory: dict[str, Any], selection: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(selection, dict) or selection.get("schemaVersion") != SCHEMA_VERSION or not isinstance(selection.get("inventoryDigest"), str):
        raise ContractError("invalid selection")
    if selection["inventoryDigest"] != inventory["snapshot"]["digest"]:
        raise ContractError("selection inventory digest mismatch")
    strategy = selection.get("gitStrategy")
    rows = selection.get("items")
    if not isinstance(strategy, dict) or not isinstance(rows, list):
        raise ContractError("invalid selection")
    mode = strategy.get("mode")
    if not isinstance(mode, str):
        raise ContractError("invalid selection")
    if mode == "remote-clone":
        remote = strategy.get("remote")
        expected_head = strategy.get("expectedHead")
        if not isinstance(remote, str) or not isinstance(expected_head, str):
            raise ContractError("invalid selection")
        evidence = inventory["repository"]["remoteEvidence"].get(remote)
        if expected_head != inventory["repository"]["head"]:
            raise ContractError("remote-clone expected head mismatch")
        if not isinstance(evidence, dict) or not evidence.get("headReachable"):
            raise ContractError("selected remote has no HEAD tracking evidence")
    elif mode not in {"git-bundle", "none"}:
        raise ContractError("unsupported git strategy")
    normalized: list[dict[str, Any]] = []
    selected_tree = PortablePathTree()
    for row in rows:
        if not isinstance(row, dict):
            raise ContractError("invalid selection item")
        path = selection_path(root, row.get("path"))
        disposition = row.get("disposition")
        if disposition not in {"include", "delete", "external"} or not isinstance(row.get("reason"), str) or not row["reason"].strip():
            raise ContractError("invalid selection item")
        entries = [entry for entry in inventory["entries"] if covers(path, entry["path"])]
        if not entries:
            raise ContractError(f"selection path is absent from inventory: {path}")
        if portable_path_issue(path) is not None and (
            disposition != "external" or len(entries) != 1 or entries[0]["path"] != path
        ):
            raise ContractError("reparse entries require external disposition; reparse or hostile entries require external disposition")
        if not selected_tree.add(path):
            raise ContractError("selection rows overlap")
        if is_transfer_path(path) and disposition != "external":
            raise ContractError("internal archive namespace requires external disposition")
        if disposition != "external" and any(entry.get("metadataOnly") or entry.get("hostile") for entry in entries):
            raise ContractError("reparse entries require external disposition; reparse or hostile entries require external disposition")
        expected_digest = covered_set_digest(inventory["entries"], path)
        if disposition == "external":
            receipt = row.get("receipt")
            if not isinstance(receipt, dict) or not isinstance(receipt.get("artifact"), str) or not receipt["artifact"].strip():
                raise ContractError("external receipt is required")
            if receipt.get("setSha256") != expected_digest:
                raise ContractError("external receipt setSha256 mismatch")
        if disposition == "delete":
            proof = row.get("proof")
            if not isinstance(proof, dict) or proof.get("kind") not in DELETE_PROOF_KINDS or proof.get("setSha256") != expected_digest:
                raise ContractError("delete proof setSha256 mismatch")
            if proof["kind"] == "regenerate" and (not isinstance(proof.get("command"), str) or not proof["command"].strip()):
                raise ContractError("delete proof is incomplete")
        normalized.append({**row, "path": path})
    required = [entry for entry in inventory["entries"] if entry["gitClass"] != "tracked" or entry["dirtyTracked"]]
    missing = [entry["path"] for entry in required if not any(covers(row["path"], entry["path"]) for row in normalized)]
    if missing:
        raise ContractError("unclassified local-only entries: " + ", ".join(missing))
    for entry in inventory["entries"]:
        covered_rows = [row for row in normalized if covers(row["path"], entry["path"])]
        if entry.get("metadataOnly") or entry.get("hostile"):
            if len(covered_rows) != 1 or covered_rows[0]["disposition"] != "external":
                raise ContractError("reparse entries require external disposition; reparse or hostile entries require external disposition")
    return normalized


def require_current_inventory(repository: BoundRepository, inventory: dict[str, Any], message: str = "inventory drift") -> None:
    if build_inventory(repository)["snapshot"]["digest"] != inventory["snapshot"]["digest"]:
        raise ContractError(message)


def included_entries(inventory: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [entry for entry in inventory["entries"] if any(row["disposition"] == "include" and covers(row["path"], entry["path"]) for row in rows)]


def expected_material(root: Path, git_executable: Path, inventory: dict[str, Any], rows: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, bytes]]:
    payload: dict[str, dict[str, Any]] = {}
    metadata_paths: list[str] = []
    for entry in included_entries(inventory, rows):
        if entry.get("metadataOnly") or entry.get("hostile"):
            raise ContractError("reparse entries require external disposition")
        metadata_paths.append(entry["path"])
        if entry["entryType"] == "deleted":
            continue
        source = root.joinpath(*PurePosixPath(entry["path"]).parts)
        if is_reparse_point(source) or not source.is_file():
            raise ContractError("inventory drift")
        if source.stat().st_size != entry["size"] or sha256_file(source) != entry["sha256"]:
            raise ContractError("inventory drift")
        payload[entry["path"]] = entry
    return payload, git_metadata(root, git_executable, sorted(metadata_paths))


def expected_deletions(inventory: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {"path": entry["path"]}
        for entry in included_entries(inventory, rows)
        if entry["entryType"] == "deleted"
    ]


def deterministic_zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def enforce_archive_infos(infos: Iterable[zipfile.ZipInfo]) -> None:
    entries = list(infos)
    if len(entries) > MAX_ARCHIVE_ENTRIES:
        raise ContractError("archive resource limit")
    total_size = 0
    for info in entries:
        if (
            info.file_size < 0
            or info.compress_size < 0
            or info.file_size > MAX_ARCHIVE_ENTRY_BYTES
            or (info.file_size and (not info.compress_size or info.file_size > info.compress_size * MAX_ARCHIVE_COMPRESSION_RATIO))
        ):
            raise ContractError("archive resource limit")
        total_size += info.file_size
        if total_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise ContractError("archive resource limit")


def write_file_member(archive: zipfile.ZipFile, name: str, source: Path, expected: dict[str, Any]) -> None:
    with source.open("rb") as input_stream, archive.open(deterministic_zip_info(name), "w") as output_stream:
        digest = hashlib.sha256()
        size = 0
        for chunk in iter(lambda: input_stream.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
            output_stream.write(chunk)
    if size != expected["size"] or digest.hexdigest() != expected["sha256"]:
        raise ContractError("inventory drift")


def bundle(repository: BoundRepository, inventory_path: Path, selection_path: Path, output: Path) -> None:
    root = repository.root
    output = require_outside_repository(output, root, "bundle output")
    inventory = read_json(inventory_path, "inventory")
    selection = read_json(selection_path, "selection")
    validate_inventory(inventory)
    rows = validate_selection(root, inventory, selection)
    require_current_inventory(repository, inventory)
    payload, metadata = expected_material(root, repository.git_executable, inventory, rows)
    manifest = {"schemaVersion": SCHEMA_VERSION, "inventoryDigest": inventory["snapshot"]["digest"], "selectionDigest": sha256_bytes(canonical_json(selection)), "repository": {"head": inventory["repository"]["head"], "gitExecutable": inventory["repository"]["gitExecutable"]}, "payload": [{"path": name, "size": entry["size"], "sha256": entry["sha256"]} for name, entry in sorted(payload.items())], "metadata": [{"path": name, "size": len(data), "sha256": sha256_bytes(data)} for name, data in sorted(metadata.items())], "deletions": expected_deletions(inventory, rows)}
    manifest_bytes = capped_canonical_json(manifest, "archive resource limit")
    declared_sizes = [entry["size"] for entry in payload.values()] + [len(data) for data in metadata.values()] + [len(manifest_bytes)]
    if len(declared_sizes) > MAX_ARCHIVE_ENTRIES or any(size > MAX_ARCHIVE_ENTRY_BYTES for size in declared_sizes) or sum(declared_sizes) > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
        raise ContractError("archive resource limit")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as stream:
            temporary = Path(stream.name)
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, entry in sorted(payload.items()):
                write_file_member(archive, name, root.joinpath(*PurePosixPath(name).parts), entry)
            for name, data in sorted(metadata.items()):
                archive.writestr(deterministic_zip_info(name), data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
            archive.writestr(deterministic_zip_info(MANIFEST_PATH), manifest_bytes, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
            enforce_archive_infos(archive.infolist())
        temporary.replace(output)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def validate_archive_name(name: str) -> str:
    portable = PurePosixPath(name)
    if name in {"", "."} or name.endswith("/") or name != portable.as_posix() or portable_path_issue(name):
        raise ContractError("unsafe archive entry")
    return portable.as_posix()


def preflight_archive(bundle_path: Path) -> None:
    try:
        file_size = bundle_path.stat().st_size
        tail_size = min(file_size, 22 + 0xFFFF)
        with bundle_path.open("rb") as stream:
            stream.seek(file_size - tail_size)
            tail = stream.read(tail_size)
        eocd_index = tail.rfind(b"PK\x05\x06")
        if eocd_index < 0 or eocd_index + 22 > len(tail):
            raise ContractError("invalid bundle")
        eocd_offset = file_size - tail_size + eocd_index
        disk, directory_disk, disk_entries, entries, directory_size, directory_offset, comment_size = struct.unpack_from("<HHHHIIH", tail, eocd_index + 4)
        if eocd_offset + 22 + comment_size != file_size:
            raise ContractError("invalid bundle")
        directory_boundary = eocd_offset
        zip64_required = (
            disk == 0xFFFF
            or directory_disk == 0xFFFF
            or disk_entries == 0xFFFF
            or entries == 0xFFFF
            or directory_size == 0xFFFFFFFF
            or directory_offset == 0xFFFFFFFF
        )
        locator_offset = eocd_offset - 20
        locator = b""
        if locator_offset >= 0:
            with bundle_path.open("rb") as stream:
                stream.seek(locator_offset)
                locator = stream.read(20)
        has_zip64_locator = len(locator) == 20 and locator.startswith(b"PK\x06\x07")
        if has_zip64_locator:
            signature, zip64_disk, zip64_offset, disk_count = struct.unpack("<4sIQI", locator)
            if signature != b"PK\x06\x07" or zip64_disk != 0 or disk_count != 1 or zip64_offset >= locator_offset:
                raise ContractError("invalid bundle")
            with bundle_path.open("rb") as stream:
                stream.seek(zip64_offset)
                header = stream.read(56)
            if len(header) != 56:
                raise ContractError("invalid bundle")
            signature, record_size, _, _, disk, directory_disk, disk_entries, entries, directory_size, directory_offset = struct.unpack("<4sQ2H2I4Q", header)
            if (
                signature != b"PK\x06\x06"
                or record_size < 44
                or zip64_offset + 12 + record_size > locator_offset
                or disk != 0
                or directory_disk != 0
            ):
                raise ContractError("invalid bundle")
            directory_boundary = zip64_offset
        elif zip64_required:
            raise ContractError("invalid bundle")
        elif disk != 0 or directory_disk != 0 or disk_entries != entries:
            raise ContractError("invalid bundle")
        if entries > MAX_ARCHIVE_ENTRIES or directory_size > MAX_ARCHIVE_CENTRAL_DIRECTORY_BYTES:
            raise ContractError("archive resource limit")
        if directory_offset > directory_boundary or directory_size > directory_boundary - directory_offset:
            raise ContractError("invalid bundle")
    except ContractError:
        raise
    except (OSError, struct.error, ValueError) as error:
        raise ContractError("invalid bundle") from error


def open_archive(bundle_path: Path) -> zipfile.ZipFile:
    preflight_archive(bundle_path)
    try:
        return zipfile.ZipFile(bundle_path)
    except (OSError, TypeError, ValueError, zipfile.BadZipFile, NotImplementedError) as error:
        raise ContractError("invalid bundle") from error


def read_archive(archive: zipfile.ZipFile) -> tuple[dict[str, Any], set[str], set[str]]:
    try:
        infos = archive.infolist()
        enforce_archive_infos(infos)
        archive_tree = PortablePathTree()
        names: list[str] = []
        for info in infos:
            name = validate_archive_name(info.filename)
            if not archive_tree.add(name):
                raise ContractError("archive path collision")
            names.append(name)
            mode = (info.external_attr >> 16) & 0xFFFF
            if info.flag_bits & 1:
                raise ContractError("encrypted archive entry")
            if mode and stat.S_IFMT(mode) not in {0, stat.S_IFREG}:
                raise ContractError("unsafe archive entry")
        if len(names) != len(set(names)) or MANIFEST_PATH not in names:
            raise ContractError("invalid internal manifest")
        try:
            with archive.open(MANIFEST_PATH) as stream:
                manifest = read_json_bytes(stream.read(MAX_JSON_BYTES + 1), "internal manifest")
        except (OSError, UnicodeError, ValueError, ContractError, zipfile.BadZipFile, NotImplementedError) as error:
            raise ContractError("invalid internal manifest") from error
        if (
            type(manifest.get("schemaVersion")) is not int
            or manifest.get("schemaVersion") != SCHEMA_VERSION
            or not is_sha256(manifest.get("inventoryDigest"))
            or not is_sha256(manifest.get("selectionDigest"))
            or not isinstance(manifest.get("repository"), dict)
            or not isinstance(manifest["repository"].get("head"), str)
            or not isinstance(manifest["repository"].get("gitExecutable"), dict)
            or not isinstance(manifest.get("payload"), list)
            or not isinstance(manifest.get("metadata"), list)
            or not isinstance(manifest.get("deletions"), list)
        ):
            raise ContractError("invalid internal manifest")
        payload_rows = manifest.get("payload")
        metadata_rows = manifest.get("metadata")
        expected: dict[str, dict[str, Any]] = {}
        payload_names: set[str] = set()
        metadata_names: set[str] = set()
        declared_tree = PortablePathTree()
        for entry in payload_rows:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                raise ContractError("invalid internal manifest")
            name = validate_archive_name(entry["path"])
            if is_transfer_path(name):
                raise ContractError("invalid manifest entry category")
            if name in expected or not declared_tree.add(name) or type(entry.get("size")) is not int or entry["size"] < 0 or not is_sha256(entry.get("sha256")):
                raise ContractError("invalid internal manifest")
            expected[name] = entry
            payload_names.add(name)
        for entry in metadata_rows:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                raise ContractError("invalid internal manifest")
            name = validate_archive_name(entry["path"])
            if name not in METADATA_NAMES:
                raise ContractError("invalid manifest entry category")
            if name in expected or type(entry.get("size")) is not int or entry["size"] < 0 or not is_sha256(entry.get("sha256")):
                raise ContractError("invalid internal manifest")
            expected[name] = entry
            metadata_names.add(name)
        if metadata_names != set(METADATA_NAMES):
            raise ContractError("invalid manifest entry category")
        deletions = manifest["deletions"]
        for entry in deletions:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                raise ContractError("invalid internal manifest")
            name = validate_archive_name(entry["path"])
            if is_transfer_path(name) or name in expected or not declared_tree.add(name):
                raise ContractError("invalid manifest entry category")
        if set(names) != set(expected) | {MANIFEST_PATH}:
            raise ContractError("archive entries do not match manifest")
        for name, entry in expected.items():
            with archive.open(name) as stream:
                size, digest = stream_digest(stream)
            if size != entry["size"] or digest != entry["sha256"]:
                raise ContractError("archive hash mismatch")
        return manifest, payload_names, metadata_names
    except ContractError:
        raise
    except (OSError, TypeError, ValueError, KeyError, zipfile.BadZipFile, NotImplementedError) as error:
        raise ContractError("invalid bundle") from error


def verify_payload_source(manifest: dict[str, Any], root: Path) -> int:
    mismatches = 0
    for entry in manifest["payload"]:
        relative = validate_archive_name(entry["path"])
        source = root.joinpath(*PurePosixPath(relative).parts)
        if has_reparse_ancestor(root, relative) or not source.is_file() or source.stat().st_size != entry["size"] or sha256_file(source) != entry["sha256"]:
            mismatches += 1
    for entry in manifest.get("deletions", []):
        relative = validate_archive_name(entry["path"])
        source = root.joinpath(*PurePosixPath(relative).parts)
        if has_reparse_ancestor(root, relative) or os.path.lexists(source):
            mismatches += 1
    return mismatches


def has_reparse_ancestor(root: Path, relative: str) -> bool:
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        if os.path.lexists(current) and is_reparse_point(current):
            return True
    return False


def archive_member_matches_bytes(archive: zipfile.ZipFile, name: str, expected: bytes) -> bool:
    with archive.open(name) as stream:
        size, digest = stream_digest(stream)
    return size == len(expected) and digest == sha256_bytes(expected)


def load_validated_snapshot(repository: BoundRepository, inventory_path: Path, selection_path: Path, drift_message: str) -> tuple[Path, dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    root = repository.root
    inventory = read_json(inventory_path, "inventory")
    selection = read_json(selection_path, "selection")
    validate_inventory(inventory)
    rows = validate_selection(root, inventory, selection)
    require_current_inventory(repository, inventory, drift_message)
    return root, inventory, selection, rows


def require_current_delete_entries(repository: BoundRepository, inventory: dict[str, Any], rows: list[dict[str, Any]], message: str) -> None:
    delete_paths = [row["path"] for row in rows if row["disposition"] == "delete"]
    if not delete_paths:
        return
    if build_inventory(repository)["snapshot"]["digest"] != inventory["snapshot"]["digest"]:
        raise ContractError(message)


def verify_trusted_material(archive: zipfile.ZipFile, manifest: dict[str, Any], archive_payload: set[str], archive_metadata: set[str], repository: BoundRepository, inventory: dict[str, Any], selection: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    payload, metadata = expected_material(repository.root, repository.git_executable, inventory, rows)
    if (
        manifest.get("inventoryDigest") != inventory["snapshot"]["digest"]
        or manifest.get("selectionDigest") != sha256_bytes(canonical_json(selection))
        or manifest["repository"]["head"] != inventory["repository"]["head"]
        or manifest["repository"]["gitExecutable"] != inventory["repository"]["gitExecutable"]
        or manifest.get("deletions", []) != expected_deletions(inventory, rows)
        or set(archive_payload) != set(payload)
        or set(archive_metadata) != set(metadata)
        or any(manifest_entry["size"] != payload[name]["size"] or manifest_entry["sha256"] != payload[name]["sha256"] for manifest_entry in manifest["payload"] for name in [manifest_entry["path"]])
        or any(not archive_member_matches_bytes(archive, name, data) for name, data in metadata.items())
    ):
        raise ContractError("bundle does not match trusted inventory and selection")


def cleanup_preview_from_snapshot(bundle_path: Path, repository: BoundRepository, inventory: dict[str, Any], selection: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        with open_archive(bundle_path) as archive:
            manifest, archive_payload, archive_metadata = read_archive(archive)
            verify_trusted_material(archive, manifest, archive_payload, archive_metadata, repository, inventory, selection, rows)
    except ContractError:
        raise
    except (OSError, TypeError, ValueError, KeyError, zipfile.BadZipFile, NotImplementedError) as error:
        raise ContractError("invalid bundle") from error
    require_current_delete_entries(repository, inventory, rows, "metadata snapshot mismatch")
    deletion_rows = [row for row in rows if row["disposition"] == "delete"]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "applied": False,
        "inventoryDigest": inventory["snapshot"]["digest"],
        "selectionDigest": sha256_bytes(canonical_json(selection)),
        "deletions": [row["path"] for row in deletion_rows],
        "deletionProofs": [
            {"path": row["path"], "kind": row["proof"]["kind"], "setSha256": row["proof"]["setSha256"]}
            for row in deletion_rows
        ],
    }


def verify(bundle_path: Path, inventory_path: Path | None, selection_path: Path | None, source: Path | None, git_executable: Path | None = None) -> dict[str, Any]:
    try:
        with open_archive(bundle_path) as archive:
            manifest, archive_payload, archive_metadata = read_archive(archive)
            trusted_arguments = (inventory_path, selection_path, source)
            if all(argument is None for argument in trusted_arguments):
                return {"schemaVersion": SCHEMA_VERSION, "payloadFiles": len(manifest.get("payload", [])), "mismatches": 0, "verified": True, "verificationMode": "archive-integrity"}
            if inventory_path is None and selection_path is None and source is not None:
                if git_executable is None:
                    raise ContractError("git executable is required with a source repository")
                repository = bind_repository(source, git_executable)
                mismatches = verify_payload_source(manifest, repository.root)
                return {"schemaVersion": SCHEMA_VERSION, "payloadFiles": len(manifest.get("payload", [])), "mismatches": mismatches, "verified": mismatches == 0, "verificationMode": "payload-source"}
            if any(argument is None for argument in trusted_arguments):
                raise ContractError("trusted verify requires inventory, selection, and source")
            if git_executable is None:
                raise ContractError("git executable is required with a source repository")
            repository = bind_repository(source, git_executable)
            _, inventory, selection, rows = load_validated_snapshot(repository, inventory_path, selection_path, "metadata snapshot mismatch")
            verify_trusted_material(archive, manifest, archive_payload, archive_metadata, repository, inventory, selection, rows)
            return {"schemaVersion": SCHEMA_VERSION, "payloadFiles": len(manifest.get("payload", [])), "mismatches": 0, "verified": True, "verificationMode": "trusted"}
    except ContractError:
        raise
    except (OSError, TypeError, ValueError, KeyError, zipfile.BadZipFile, NotImplementedError) as error:
        raise ContractError("invalid bundle") from error


def cleanup(repository: BoundRepository, inventory_path: Path, selection_path: Path, bundle_path: Path, apply: bool) -> dict[str, Any]:
    if apply:
        raise ContractError("cleanup is preview-only; automatic deletion is not supported")
    _, inventory, selection, rows = load_validated_snapshot(repository, inventory_path, selection_path, "metadata snapshot mismatch")
    return cleanup_preview_from_snapshot(bundle_path, repository, inventory, selection, rows)


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("inventory")
    inventory.add_argument("--repo", type=Path, required=True)
    inventory.add_argument("--git-executable", type=Path, required=True)
    inventory.add_argument("--output", type=Path, required=True)
    bundle_parser = commands.add_parser("bundle")
    bundle_parser.add_argument("--repo", type=Path, required=True)
    bundle_parser.add_argument("--git-executable", type=Path, required=True)
    bundle_parser.add_argument("--inventory", type=Path, required=True)
    bundle_parser.add_argument("--selection", type=Path, required=True)
    bundle_parser.add_argument("--output", type=Path, required=True)
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--bundle", type=Path, required=True)
    verify_parser.add_argument("--git-executable", type=Path, required=True)
    verify_parser.add_argument("--inventory", type=Path)
    verify_parser.add_argument("--selection", type=Path)
    verify_parser.add_argument("--source", type=Path)
    cleanup_parser = commands.add_parser("cleanup")
    cleanup_parser.add_argument("--repo", type=Path, required=True)
    cleanup_parser.add_argument("--git-executable", type=Path, required=True)
    cleanup_parser.add_argument("--inventory", type=Path, required=True)
    cleanup_parser.add_argument("--selection", type=Path, required=True)
    cleanup_parser.add_argument("--bundle", type=Path, required=True)
    cleanup_parser.add_argument("--apply", action="store_true")
    return parser


def main(arguments: list[str] | None = None) -> int:
    args = make_parser().parse_args(arguments)
    try:
        if args.command == "inventory":
            repository = bind_repository(args.repo, args.git_executable)
            output = require_outside_repository(args.output, repository.root, "inventory output")
            output.parent.mkdir(parents=True, exist_ok=True)
            inventory_bytes = capped_canonical_json(build_inventory(repository), "inventory output exceeds JSON limit", final_newline=True)
            output.write_bytes(inventory_bytes)
        elif args.command == "bundle":
            bundle(bind_repository(args.repo, args.git_executable), args.inventory, args.selection, args.output)
        elif args.command == "verify":
            result = verify(args.bundle, args.inventory, args.selection, args.source, args.git_executable)
            print(json.dumps(result, sort_keys=True))
            if result["mismatches"]:
                return 2
        else:
            print(json.dumps(cleanup(bind_repository(args.repo, args.git_executable), args.inventory, args.selection, args.bundle, args.apply), sort_keys=True))
    except (ContractError, OSError, ValueError) as error:
        print(str(error) or "contract error", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
