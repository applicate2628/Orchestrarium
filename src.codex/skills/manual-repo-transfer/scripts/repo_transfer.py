#!/usr/bin/env python3
"""Create and verify a deterministic, byte-only local overlay for a Git repository."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import json
import math
import ntpath
import os
import re
import secrets
import selectors
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import time
import threading
import unicodedata
import zipfile
from contextlib import contextmanager
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
GIT_PROCESS_CLEANUP_SECONDS = 2
TRANSFER_REPOSITORY_BOUNDARY_INVALID = "TRANSFER-REPOSITORY-BOUNDARY-INVALID"
TRANSFER_GIT_BINDING_INVALID = "TRANSFER-GIT-BINDING-INVALID"
TRANSFER_GIT_ROOT_MISMATCH = "TRANSFER-GIT-ROOT-MISMATCH"
TRANSFER_GIT_BINDING_DRIFT = "TRANSFER-GIT-BINDING-DRIFT"
TRANSFER_PATH_ENCODING_INVALID = "TRANSFER-PATH-ENCODING-INVALID"
TRANSFER_HOSTILE_PATH_EXTERNAL_REQUIRED = "TRANSFER-HOSTILE-PATH-EXTERNAL-REQUIRED"
TRANSFER_OUTPUT_EXISTS = "TRANSFER-OUTPUT-EXISTS"
TRANSFER_OUTPUT_TYPE_INVALID = "TRANSFER-OUTPUT-TYPE-INVALID"
TRANSFER_OUTPUT_PATH_INVALID = "TRANSFER-OUTPUT-PATH-INVALID"
TRANSFER_OUTPUT_IDENTITY_DRIFT = "TRANSFER-OUTPUT-IDENTITY-DRIFT"
TRANSFER_OUTPUT_PUBLISH_FAILED = "TRANSFER-OUTPUT-PUBLISH-FAILED"
TRANSFER_ARCHIVE_BOUNDARY_INVALID = "TRANSFER-ARCHIVE-BOUNDARY-INVALID"
TRANSFER_ARCHIVE_BINDING_INVALID = "TRANSFER-ARCHIVE-BINDING-INVALID"
TRANSFER_ARCHIVE_IDENTITY_DRIFT = "TRANSFER-ARCHIVE-IDENTITY-DRIFT"
TRANSFER_ARCHIVE_CLOSE_FAILED = "TRANSFER-ARCHIVE-CLOSE-FAILED"
TRANSFER_INPUT_BINDING_INVALID = "TRANSFER-INPUT-BINDING-INVALID"
TRANSFER_INPUT_IDENTITY_DRIFT = "TRANSFER-INPUT-IDENTITY-DRIFT"
TRANSFER_INPUT_CLOSE_FAILED = "TRANSFER-INPUT-CLOSE-FAILED"


_PROCESS_RUNNER_MODULE: Any | None = None
_LINUX_SUBREAPER_LOCK = threading.RLock()
_PR_SET_CHILD_SUBREAPER = 36
_PR_GET_CHILD_SUBREAPER = 37


class ContractError(Exception):
    pass


class _LinuxSubreaperError(Exception):
    pass


class _LinuxChildSubreaper:
    """Temporarily adopt only this executor's orphaned Linux process-group children."""

    def __init__(self) -> None:
        self._active = False
        self._locked = False
        self._libc: Any | None = None
        self._prior = 0

    def start(self) -> None:
        if not sys.platform.startswith("linux"):
            return
        _LINUX_SUBREAPER_LOCK.acquire()
        self._locked = True
        try:
            libc = ctypes.CDLL(None, use_errno=True)
            prctl = libc.prctl
            prctl.restype = ctypes.c_int
            prior = ctypes.c_int()
            if prctl(_PR_GET_CHILD_SUBREAPER, ctypes.byref(prior), 0, 0, 0) != 0:
                raise OSError(ctypes.get_errno(), "PR_GET_CHILD_SUBREAPER")
            if prctl(_PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) != 0:
                raise OSError(ctypes.get_errno(), "PR_SET_CHILD_SUBREAPER")
            self._libc = libc
            self._prior = prior.value
            self._active = True
        except (AttributeError, OSError) as error:
            self.close()
            raise _LinuxSubreaperError("Linux child subreaper is unavailable") from error

    def reap_process_group(self, process_group: int) -> None:
        if not self._active:
            return
        try:
            while True:
                reaped_pid, _status = os.waitpid(-process_group, os.WNOHANG)
                if reaped_pid == 0:
                    return
        except ChildProcessError:
            return
        except OSError as error:
            raise _LinuxSubreaperError("Linux child subreaper reap failed") from error

    def close(self) -> None:
        try:
            if self._active:
                assert self._libc is not None
                if self._libc.prctl(_PR_SET_CHILD_SUBREAPER, self._prior, 0, 0, 0) != 0:
                    raise _LinuxSubreaperError("Linux child subreaper restore failed")
        finally:
            self._active = False
            if self._locked:
                self._locked = False
                _LINUX_SUBREAPER_LOCK.release()


class BoundRepository:
    def __init__(
        self,
        root: Path,
        git_executable: Path,
        git_executable_sha256: str,
        git_executable_identity: tuple[int, ...] | None = None,
        git_executable_content_sha256: str | None = None,
    ) -> None:
        self.root = root
        self.git_executable = git_executable
        self.git_executable_sha256 = git_executable_sha256
        self.git_executable_identity = git_executable_identity
        self.git_executable_content_sha256 = (
            git_executable_content_sha256 or git_executable_sha256
        )


class OutputBinding:
    def __init__(
        self,
        path: Path,
        parent_identity: tuple[int, ...],
        destination_identity: tuple[int, ...] | None,
    ) -> None:
        self.path = path
        self.parent_identity = parent_identity
        self.destination_identity = destination_identity


class BoundArchiveStream:
    """One held archive leaf exposed as the only stream consumed by ZIP code."""

    def __init__(self, raw: Any, session: "BoundArchiveSession") -> None:
        self.raw = raw
        self.session = session

    @property
    def closed(self) -> bool:
        return bool(self.raw.closed)

    @property
    def eof(self) -> int:
        return self.session.eof

    def read_exact_at(
        self,
        offset: int,
        size: int,
        *,
        cap: int,
        allowed_lengths: set[int] | None = None,
    ) -> bytes:
        return self.session.read_exact_at(
            offset, size, cap=cap, allowed_lengths=allowed_lengths
        )

    def read(self, size: int = -1) -> bytes:
        return self.raw.read(size)

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        return self.raw.seek(offset, whence)

    def tell(self) -> int:
        return self.raw.tell()

    def seekable(self) -> bool:
        return self.raw.seekable()

    def readable(self) -> bool:
        return self.raw.readable()

    def fileno(self) -> int:
        return self.raw.fileno()

    def close(self) -> None:
        self.raw.close()


class TrackedArchiveMember:
    def __init__(self, member: Any, session: "BoundArchiveSession") -> None:
        self.member = member
        self.session = session
        self.was_closed = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self.member, name)

    def __enter__(self) -> "TrackedArchiveMember":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def __iter__(self) -> Any:
        return iter(self.member)

    def read(self, size: int = -1) -> bytes:
        return self.member.read(size)

    def close(self) -> None:
        if self.was_closed:
            return
        self.was_closed = True
        try:
            self.member.close()
        finally:
            self.session.members.discard(self)


class BoundArchiveZipFile:
    def __init__(self, stream: BoundArchiveStream, session: "BoundArchiveSession") -> None:
        self.session = session
        self.archive = zipfile.ZipFile(stream)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.archive, name)

    @property
    def fp(self) -> Any:
        return self.archive.fp

    def open(self, name: Any, mode: str = "r", pwd: bytes | None = None, *, force_zip64: bool = False) -> Any:
        member = self.archive.open(name, mode, pwd, force_zip64=force_zip64)
        tracked = TrackedArchiveMember(member, self.session)
        self.session.members.add(tracked)
        return tracked

    def close(self) -> None:
        self.archive.close()


def conditional_utf8(fragment: str) -> bytes:
    encoded = bytearray()
    ordinary: list[str] = []
    for character in fragment:
        codepoint = ord(character)
        if 0xDC80 <= codepoint <= 0xDCFF:
            if ordinary:
                encoded.extend("".join(ordinary).encode("utf-8"))
                ordinary.clear()
            encoded.extend(f"\\u{codepoint:04x}".encode("ascii"))
        elif 0xD800 <= codepoint <= 0xDFFF:
            raise ContractError(TRANSFER_PATH_ENCODING_INVALID)
        else:
            ordinary.append(character)
    if ordinary:
        encoded.extend("".join(ordinary).encode("utf-8"))
    return bytes(encoded)


def canonical_json_chunks(value: Any) -> Iterable[bytes]:
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    for fragment in encoder.iterencode(value):
        yield conditional_utf8(fragment)


def canonical_json(value: Any) -> bytes:
    return b"".join(canonical_json_chunks(value))


def capped_canonical_json(value: Any, error_message: str, *, final_newline: bool = False) -> bytes:
    suffix = b"\n" if final_newline else b""
    encoded = bytearray()
    for chunk in canonical_json_chunks(value):
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
    admitted = {
        "ALL_PROXY",
        "COMSPEC",
        "HOME",
        "HOMEDRIVE",
        "HOMEPATH",
        "HTTPS_PROXY",
        "HTTP_PROXY",
        "LANG",
        "LC_ALL",
        "NO_PROXY",
        "PATH",
        "PATHEXT",
        "SSH_AUTH_SOCK",
        "SSL_CERT_DIR",
        "SSL_CERT_FILE",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "TMPDIR",
        "USERPROFILE",
        "WINDIR",
    }
    environment: dict[str, str] = {}
    seen: set[str] = set()
    for key, value in sorted(os.environ.items(), key=lambda item: item[0].casefold()):
        canonical = key.upper()
        if canonical in admitted and canonical not in seen:
            environment[canonical if os.name == "nt" else key] = value
            seen.add(canonical)
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    return environment


def base_git_configuration() -> list[str]:
    return ["-c", "core.fsmonitor=false", "-c", "diff.external="]


def _process_runner_projection() -> tuple[Path, Path]:
    skill = Path(__file__).resolve().parent.parent
    skills = skill.parent
    if skill.name != "manual-repo-transfer" or skills.name != "skills":
        raise ContractError("repository transfer process runner is unavailable")
    if skills.parent.name == "src.codex":
        root = skills.parent.parent
        runner = root / "scripts" / "process_supervision" / "process_runner.py"
        manifest = root / "shared" / "provider-prompt-projections.v1.json"
    else:
        lead = skills / "lead"
        runner = lead / "scripts" / "process_supervision" / "process_runner.py"
        manifest = lead / "shared" / "provider-prompt-projections.v1.json"
    return runner, manifest


def _load_process_runner() -> Any:
    global _PROCESS_RUNNER_MODULE
    if _PROCESS_RUNNER_MODULE is not None:
        return _PROCESS_RUNNER_MODULE
    runner, manifest = _process_runner_projection()
    try:
        record = json.loads(manifest.read_text(encoding="utf-8"))["files"][
            "process_supervision/process_runner.py"
        ]
        if (
            record.get("destination")
            != "scripts/process_supervision/process_runner.py"
            or sha256_file(runner) != record.get("sha256")
        ):
            raise ContractError("repository transfer process runner projection drift")
        name = "_orchestrarium_repository_transfer_process_runner"
        spec = importlib.util.spec_from_file_location(name, runner)
        if spec is None or spec.loader is None:
            raise ContractError("repository transfer process runner is unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(name, None)
            raise
        _PROCESS_RUNNER_MODULE = module
        return module
    except ContractError:
        raise
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ContractError("repository transfer process runner is unavailable") from error


def _run_process_runner_git_process(command: list[str], repository: Path | None, environment: dict[str, str]) -> subprocess.CompletedProcess[bytes]:
    owner: Any | None = None
    try:
        runner_module = _load_process_runner()
        owner = runner_module.ProcessRunnerV1()
        request, sink = owner.build_repository_transfer_git_request(
            argv=tuple(command),
            resolved_executable=Path(command[0]),
            cwd=str(repository),
            environment=tuple(
                runner_module.EnvironmentRowV1(name, value)
                for name, value in sorted(
                    environment.items(), key=lambda item: item[0].casefold()
                )
            ),
            deadline_seconds=GIT_COMMAND_TIMEOUT_SECONDS,
            capture_limit_bytes=MAX_JSON_BYTES,
        )
        result = owner.run(request)
        stdout = sink.bytes_for("stdout")
        stderr = sink.bytes_for("stderr")
    except ContractError:
        raise
    except (OSError, TypeError, ValueError) as error:
        raise ContractError("not a git repository") from error
    finally:
        if owner is not None:
            owner.close()
    if result.failure_id == "PSV1-DEADLINE" or result.timed_out:
        raise ContractError("git command timed out")
    if result.failure_id == "PSV1-CAPTURE-LIMIT":
        raise ContractError("git output exceeds JSON limit")
    if result.failure_id == "PSV1-CAPTURE-IO":
        raise ContractError("git output capture failed")
    if result.failure_id is not None:
        raise ContractError(f"git process supervision failed: {result.failure_id}")
    if not result.tree.tree_empty or not result.resources_closed:
        raise ContractError("not a git repository")
    completed = subprocess.CompletedProcess(
        command, result.target_exit_code or 0, stdout, stderr
    )
    completed.executable_identity_sha256 = result.executable_identity_sha256
    return completed


def _posix_process_group_exists(process_group: int) -> bool:
    try:
        os.killpg(process_group, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _settle_posix_git_process(
    process: subprocess.Popen[bytes], subreaper: _LinuxChildSubreaper
) -> bool:
    process_group = process.pid
    deadline = time.monotonic() + GIT_PROCESS_CLEANUP_SECONDS
    try:
        if _posix_process_group_exists(process_group):
            try:
                os.killpg(process_group, signal.SIGTERM)
            except ProcessLookupError:
                pass
        graceful_deadline = min(deadline, time.monotonic() + 0.25)
        while (
            _posix_process_group_exists(process_group)
            and time.monotonic() < graceful_deadline
        ):
            process.poll()
            time.sleep(0.01)
        if _posix_process_group_exists(process_group):
            try:
                os.killpg(process_group, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process.poll() is None:
            try:
                process.wait(timeout=max(0.0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                return False
        while _posix_process_group_exists(process_group) and time.monotonic() < deadline:
            subreaper.reap_process_group(process_group)
            time.sleep(0.01)
        subreaper.reap_process_group(process_group)
        return not _posix_process_group_exists(process_group)
    except (OSError, ValueError, _LinuxSubreaperError):
        return False


def _run_posix_git_process(command: list[str], repository: Path | None, environment: dict[str, str]) -> subprocess.CompletedProcess[bytes]:
    subreaper = _LinuxChildSubreaper()
    try:
        if not command or not Path(command[0]).is_absolute():
            raise OSError("Git executable is not absolute")
        subreaper.start()
        process = subprocess.Popen(
            command,
            executable=command[0],
            cwd=repository,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            shell=False,
            start_new_session=True,
            close_fds=True,
            bufsize=0,
        )
    except _LinuxSubreaperError as error:
        subreaper.close()
        raise ContractError("git process containment is unavailable") from error
    except OSError as error:
        try:
            subreaper.close()
        except _LinuxSubreaperError as cleanup_error:
            raise ContractError("git process containment cleanup failed") from cleanup_error
        raise ContractError("not a git repository") from error
    assert process.stdout is not None and process.stderr is not None
    streams = {process.stdout: "stdout", process.stderr: "stderr"}
    captures = {"stdout": bytearray(), "stderr": bytearray()}
    selector = selectors.DefaultSelector()
    overflow = False
    capture_error = False
    timed_out = False
    leftover_tree = False
    interrupted: BaseException | None = None
    containment_cleanup_error = False
    deadline = time.monotonic() + GIT_COMMAND_TIMEOUT_SECONDS
    try:
        for stream in streams:
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, streams[stream])
        while selector.get_map() or process.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            events = selector.select(min(0.05, remaining))
            for key, _ in events:
                try:
                    chunk = os.read(key.fd, 64 * 1024)
                except BlockingIOError:
                    continue
                except OSError:
                    capture_error = True
                    break
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                captured = captures[key.data]
                available = MAX_JSON_BYTES + 1 - len(captured)
                if available > 0:
                    captured.extend(chunk[:available])
                if len(captured) > MAX_JSON_BYTES or len(chunk) > available:
                    overflow = True
                    break
            if overflow or capture_error:
                break
            if process.poll() is not None and _posix_process_group_exists(process.pid):
                leftover_tree = True
                break
    except BaseException as error:
        interrupted = error
    finally:
        tree_empty = _settle_posix_git_process(process, subreaper)
        cleanup_deadline = time.monotonic() + GIT_PROCESS_CLEANUP_SECONDS
        while selector.get_map() and time.monotonic() < cleanup_deadline:
            try:
                events = selector.select(0.05)
                if not events and not tree_empty:
                    continue
                for key, _ in events:
                    try:
                        chunk = os.read(key.fd, 64 * 1024)
                    except BlockingIOError:
                        continue
                    except OSError:
                        capture_error = True
                        selector.unregister(key.fileobj)
                        continue
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    captured = captures[key.data]
                    available = MAX_JSON_BYTES + 1 - len(captured)
                    if available > 0:
                        captured.extend(chunk[:available])
                    if len(captured) > MAX_JSON_BYTES or len(chunk) > available:
                        overflow = True
            except (OSError, ValueError):
                capture_error = True
                break
        if selector.get_map():
            capture_error = True
        selector.close()
        for stream in streams:
            try:
                stream.close()
            except OSError:
                capture_error = True
        try:
            subreaper.close()
        except _LinuxSubreaperError:
            containment_cleanup_error = True
    if interrupted is not None:
        raise interrupted
    if containment_cleanup_error:
        raise ContractError("git process containment cleanup failed")
    if timed_out:
        raise ContractError("git command timed out")
    if overflow:
        raise ContractError("git output exceeds JSON limit")
    if capture_error:
        raise ContractError("git output capture failed")
    if leftover_tree or not tree_empty:
        raise ContractError("git process tree did not settle")
    completed = subprocess.CompletedProcess(
        command,
        process.returncode if process.returncode is not None else -signal.SIGKILL,
        bytes(captures["stdout"]),
        bytes(captures["stderr"]),
    )
    completed.executable_identity_sha256 = _load_process_runner().resolve_executable_identity(
        Path(command[0])
    )
    return completed


def run_bounded_process(command: list[str], repository: Path | None, environment: dict[str, str]) -> subprocess.CompletedProcess[bytes]:
    if os.name == "posix":
        return _run_posix_git_process(command, repository, environment)
    return _run_process_runner_git_process(command, repository, environment)


def local_filter_drivers(repository: BoundRepository) -> list[str]:
    command = [
        str(repository.git_executable),
        *base_git_configuration(),
        "config",
        "--includes",
        "--name-only",
        "--get-regexp",
        "^filter\\.",
    ]
    result = run_bound_git_process(repository, command)
    if result.returncode not in {0, 1}:
        raise ContractError(result.stderr.decode("utf-8", "replace").strip() or "not a git repository")
    drivers: set[str] = set()
    for key in result.stdout.decode("utf-8", "replace").splitlines():
        match = re.fullmatch(r"filter\.(.+)\.(?:clean|smudge|process|required)", key)
        if match:
            drivers.add(match.group(1))
    return sorted(drivers)


def run_git(repository: BoundRepository, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    filter_configuration: list[str] = []
    for driver in local_filter_drivers(repository):
        for setting, value in (("clean", ""), ("smudge", ""), ("process", ""), ("required", "false")):
            filter_configuration.extend(["-c", f"filter.{driver}.{setting}={value}"])
    command = [str(repository.git_executable), *base_git_configuration(), *filter_configuration, *arguments]
    result = run_bound_git_process(repository, command)
    if check and result.returncode:
        message = result.stderr.decode("utf-8", "replace").strip() or "not a git repository"
        raise ContractError(message)
    return result


def path_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def path_is_within(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath((path_key(path), path_key(root))) == path_key(root)
    except ValueError:
        return False


def valid_git_marker(root: Path) -> bool:
    marker = root / ".git"
    if not os.path.lexists(marker) or is_reparse_point(marker):
        return False
    try:
        metadata = marker.lstat()
        if stat.S_ISDIR(metadata.st_mode):
            return True
        if not stat.S_ISREG(metadata.st_mode):
            return False
        data = marker.read_bytes()
        match = re.fullmatch(rb"gitdir: ([^\x00\r\n]+)\r?\n?", data)
        if match is None:
            return False
        git_directory = Path(os.fsdecode(match.group(1)))
        if not git_directory.is_absolute():
            git_directory = root / git_directory
        physical = Path(os.path.realpath(git_directory))
        return physical.is_dir() and not is_reparse_point(physical)
    except (OSError, ValueError):
        return False


def physical_repository_root(repository: Path) -> Path:
    try:
        start = Path(os.path.realpath(Path(os.path.abspath(repository))))
        if not start.is_dir():
            raise ContractError(TRANSFER_REPOSITORY_BOUNDARY_INVALID)
        current = start
        while True:
            marker = current / ".git"
            if os.path.lexists(marker):
                if not valid_git_marker(current):
                    raise ContractError(TRANSFER_REPOSITORY_BOUNDARY_INVALID)
                return current
            if current.parent == current:
                raise ContractError(TRANSFER_REPOSITORY_BOUNDARY_INVALID)
            current = current.parent
    except ContractError:
        raise
    except (OSError, ValueError) as error:
        raise ContractError(TRANSFER_REPOSITORY_BOUNDARY_INVALID) from error


def git_file_identity(path: Path) -> tuple[int, ...]:
    metadata = path.stat()
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
        getattr(metadata, "st_file_attributes", 0),
    )


def bind_git_executable(
    git_executable: Path, root: Path
) -> tuple[Path, tuple[int, ...], str, str]:
    try:
        if not git_executable.is_absolute():
            raise ContractError(TRANSFER_GIT_BINDING_INVALID)
        absolute = Path(os.path.abspath(git_executable))
        physical = Path(os.path.realpath(absolute))
        if path_key(absolute) != path_key(physical) or is_reparse_point(absolute):
            raise ContractError(TRANSFER_GIT_BINDING_INVALID)
        metadata = physical.lstat()
        if not stat.S_ISREG(metadata.st_mode) or path_is_within(physical, root):
            raise ContractError(TRANSFER_GIT_BINDING_INVALID)
        identity = git_file_identity(physical)
        content_digest = sha256_file(physical)
        runner_digest = _load_process_runner().resolve_executable_identity(physical)
        if git_file_identity(physical) != identity:
            raise ContractError(TRANSFER_GIT_BINDING_INVALID)
        return physical, identity, runner_digest, content_digest
    except ContractError:
        raise
    except (OSError, ValueError, RuntimeError) as error:
        raise ContractError(TRANSFER_GIT_BINDING_INVALID) from error


def require_current_git_binding(repository: BoundRepository) -> None:
    try:
        executable, identity, runner_digest, content_digest = bind_git_executable(
            repository.git_executable, repository.root
        )
        if (
            executable != repository.git_executable
            or repository.git_executable_identity is None
            or identity != repository.git_executable_identity
            or runner_digest != repository.git_executable_sha256
            or content_digest != repository.git_executable_content_sha256
        ):
            raise ContractError(TRANSFER_GIT_BINDING_DRIFT)
    except ContractError as error:
        if str(error) == TRANSFER_GIT_BINDING_DRIFT:
            raise
        raise ContractError(TRANSFER_GIT_BINDING_DRIFT) from error


def run_bound_git_process(repository: BoundRepository, command: list[str]) -> subprocess.CompletedProcess[bytes]:
    require_current_git_binding(repository)
    result = run_bounded_process(command, repository.root, sanitized_git_environment())
    if (
        getattr(result, "executable_identity_sha256", None)
        != repository.git_executable_sha256
    ):
        raise ContractError(TRANSFER_GIT_BINDING_DRIFT)
    require_current_git_binding(repository)
    return result


def bind_repository(repository: Path, git_executable: Path) -> BoundRepository:
    root = physical_repository_root(repository)
    executable, identity, runner_digest, content_digest = bind_git_executable(
        git_executable, root
    )
    bound = BoundRepository(
        root, executable, runner_digest, identity, content_digest
    )
    result = run_bound_git_process(
        bound,
        [str(executable), *base_git_configuration(), "rev-parse", "--show-toplevel"],
    )
    if result.returncode:
        raise ContractError(TRANSFER_REPOSITORY_BOUNDARY_INVALID)
    try:
        reported_root = Path(os.path.realpath(Path(result.stdout.decode("utf-8", "surrogateescape").strip())))
    except (OSError, ValueError, UnicodeError) as error:
        raise ContractError(TRANSFER_GIT_ROOT_MISMATCH) from error
    if path_key(reported_root) != path_key(root):
        raise ContractError(TRANSFER_GIT_ROOT_MISMATCH)
    return bound


def _output_metadata_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
        getattr(metadata, "st_file_attributes", 0),
    )


def _output_identity(path: Path) -> tuple[int, ...]:
    return _output_metadata_identity(path.lstat())


def _directory_metadata_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        getattr(metadata, "st_file_attributes", 0),
    )


def _directory_identity(path: Path) -> tuple[int, ...]:
    return _directory_metadata_identity(path.lstat())


def _require_ordinary_directory(path: Path) -> tuple[int, ...]:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise ContractError(TRANSFER_OUTPUT_PATH_INVALID) from error
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or bool(getattr(metadata, "st_file_attributes", 0) & 0x400)
    ):
        raise ContractError(TRANSFER_OUTPUT_PATH_INVALID)
    return _directory_identity(path)


def _prepare_output_parent(parent: Path) -> tuple[int, ...]:
    absolute = Path(os.path.abspath(parent))
    missing: list[Path] = []
    cursor = absolute
    while not os.path.lexists(cursor):
        missing.append(cursor)
        if cursor.parent == cursor:
            raise ContractError(TRANSFER_OUTPUT_PATH_INVALID)
        cursor = cursor.parent
    chain = tuple(reversed((cursor, *cursor.parents)))
    for component in chain:
        _require_ordinary_directory(component)
    for component in reversed(missing):
        try:
            component.mkdir()
        except FileExistsError:
            pass
        except OSError as error:
            raise ContractError(TRANSFER_OUTPUT_PATH_INVALID) from error
        _require_ordinary_directory(component)
    return _require_ordinary_directory(absolute)


def bind_output(path: Path, root: Path, *, force: bool) -> OutputBinding:
    try:
        output = Path(os.path.abspath(path))
        if path_is_within(output, root):
            raise ContractError(TRANSFER_OUTPUT_PATH_INVALID)
        parent_identity = _prepare_output_parent(output.parent)
        physical_parent = Path(os.path.realpath(output.parent))
        if path_is_within(physical_parent, root):
            raise ContractError(TRANSFER_OUTPUT_PATH_INVALID)
        destination_identity: tuple[int, ...] | None = None
        if os.path.lexists(output):
            metadata = output.lstat()
            if (
                not stat.S_ISREG(metadata.st_mode)
                or stat.S_ISLNK(metadata.st_mode)
                or bool(getattr(metadata, "st_file_attributes", 0) & 0x400)
            ):
                raise ContractError(TRANSFER_OUTPUT_TYPE_INVALID)
            destination_identity = _output_identity(output)
            if not force:
                raise ContractError(TRANSFER_OUTPUT_EXISTS)
        return OutputBinding(output, parent_identity, destination_identity)
    except ContractError:
        raise
    except (OSError, RuntimeError, ValueError) as error:
        raise ContractError(TRANSFER_OUTPUT_PATH_INVALID) from error


def _acquire_output_parent(
    binding: OutputBinding,
    owner: "_OrdinaryFileAcquisitionOwner",
) -> int:
    if os.name == "nt":
        handle = _windows_open_ordinary_path(
            binding.path.parent,
            directory=True,
            options=_OUTPUT_FILE_OPTIONS,
            owner=owner,
            share_write=True,
        )
        if _require_ordinary_directory(binding.path.parent) != binding.parent_identity:
            raise ContractError(TRANSFER_OUTPUT_IDENTITY_DRIFT)
        return handle
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_DIRECTORY", 0)
    )
    descriptor = os.open(binding.path.parent, flags)
    owner.take_fd(descriptor)
    metadata = os.fstat(descriptor)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or _directory_metadata_identity(metadata) != binding.parent_identity
    ):
        raise ContractError(TRANSFER_OUTPUT_IDENTITY_DRIFT)
    return descriptor


def _new_output_temporary(
    binding: OutputBinding,
    parent: int,
    owner: "_OrdinaryFileAcquisitionOwner",
) -> tuple[Path, tuple[int, ...]]:
    if os.name == "nt":
        descriptor, name = tempfile.mkstemp(
            prefix=f".{binding.path.name}.", suffix=".tmp", dir=binding.path.parent
        )
        temporary = Path(name)
    else:
        flags = (
            os.O_RDWR
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        for _attempt in range(128):
            basename = f".{binding.path.name}.{secrets.token_hex(8)}.tmp"
            try:
                descriptor = os.open(basename, flags, 0o600, dir_fd=parent)
                break
            except FileExistsError:
                continue
        else:
            raise OSError("unable to reserve output temporary")
        temporary = binding.path.parent / basename
    owner.take_fd(descriptor)
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode):
        raise ContractError(TRANSFER_OUTPUT_PUBLISH_FAILED)
    return temporary, _temporary_name_identity(metadata)


def _temporary_name_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        stat.S_IFMT(metadata.st_mode),
        getattr(metadata, "st_file_attributes", 0),
    )


@contextmanager
def _bound_output_temporary(binding: OutputBinding) -> Iterable[Any]:
    errors = _OUTPUT_FILE_OPTIONS.errors
    parent_owner = _OrdinaryFileAcquisitionOwner(errors)
    temporary_owner = _OrdinaryFileAcquisitionOwner(errors)
    parent: int | None = None
    temporary: Path | None = None
    temporary_identity: tuple[int, ...] | None = None
    primary: BaseException | None = None
    try:
        parent = _acquire_output_parent(binding, parent_owner)
        temporary, temporary_identity = _new_output_temporary(
            binding, parent, temporary_owner
        )
        temporary_owner.fd_to_stream("w+b", buffering=-1)
        assert temporary_owner.stream is not None
        stream = temporary_owner.stream
        yield stream
        stream.flush()
        os.fsync(stream.fileno())
        if _temporary_name_identity(os.fstat(stream.fileno())) != temporary_identity:
            raise ContractError(TRANSFER_OUTPUT_IDENTITY_DRIFT)
        temporary_owner.rollback(ContractError(TRANSFER_OUTPUT_PUBLISH_FAILED))
        publish_output(binding, temporary, temporary_identity, parent)
    except BaseException as error:
        primary = (
            error
            if isinstance(error, ContractError)
            else ContractError(TRANSFER_OUTPUT_PUBLISH_FAILED)
        )
        if primary is error:
            raise
        raise primary from error
    finally:
        cleanup_primary = primary or ContractError(TRANSFER_OUTPUT_PUBLISH_FAILED)
        cleanup_error: BaseException | None = None
        try:
            temporary_owner.rollback(cleanup_primary)
        except BaseException as error:
            cleanup_error = error
        try:
            if temporary is not None and temporary_identity is not None:
                _cleanup_output_temporary(temporary, temporary_identity, parent)
        except BaseException as error:
            cleanup_error = cleanup_error or error
        try:
            parent_owner.rollback(cleanup_error or cleanup_primary)
        except BaseException as error:
            cleanup_error = error
        if cleanup_error is not None:
            raise cleanup_error


def _output_named_metadata(path: Path, parent: int | None) -> os.stat_result:
    if os.name != "nt":
        if parent is None:
            raise ContractError(TRANSFER_OUTPUT_PUBLISH_FAILED)
        return os.stat(path.name, dir_fd=parent, follow_symlinks=False)
    return path.lstat()


def _cleanup_output_temporary(
    temporary: Path,
    expected_identity: tuple[int, ...],
    parent: int | None,
) -> None:
    try:
        current = _temporary_name_identity(_output_named_metadata(temporary, parent))
    except FileNotFoundError:
        return
    except OSError as error:
        raise ContractError(TRANSFER_OUTPUT_PUBLISH_FAILED) from error
    if current != expected_identity:
        return
    try:
        if os.name == "nt":
            temporary.unlink()
        else:
            assert parent is not None
            os.unlink(temporary.name, dir_fd=parent)
    except FileNotFoundError:
        return
    except OSError as error:
        raise ContractError(TRANSFER_OUTPUT_PUBLISH_FAILED) from error


def _fsync_output_parent(parent: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def publish_output(
    binding: OutputBinding,
    temporary: Path,
    temporary_identity: tuple[int, ...] | None = None,
    parent: int | None = None,
) -> None:
    try:
        if (
            temporary_identity is not None
            and _temporary_name_identity(_output_named_metadata(temporary, parent))
            != temporary_identity
        ):
            raise ContractError(TRANSFER_OUTPUT_IDENTITY_DRIFT)
        if _require_ordinary_directory(binding.path.parent) != binding.parent_identity:
            raise ContractError(TRANSFER_OUTPUT_IDENTITY_DRIFT)
        if binding.destination_identity is None:
            try:
                metadata = _output_named_metadata(binding.path, parent)
            except FileNotFoundError:
                metadata = None
            if metadata is not None:
                if (
                    not stat.S_ISREG(metadata.st_mode)
                    or stat.S_ISLNK(metadata.st_mode)
                    or bool(getattr(metadata, "st_file_attributes", 0) & 0x400)
                ):
                    raise ContractError(TRANSFER_OUTPUT_TYPE_INVALID)
                raise ContractError(TRANSFER_OUTPUT_EXISTS)
            try:
                if os.name == "nt":
                    os.link(temporary, binding.path)
                else:
                    assert parent is not None
                    os.link(
                        temporary.name,
                        binding.path.name,
                        src_dir_fd=parent,
                        dst_dir_fd=parent,
                        follow_symlinks=False,
                    )
            except FileExistsError as error:
                raise ContractError(TRANSFER_OUTPUT_EXISTS) from error
            except OSError as error:
                raise ContractError(TRANSFER_OUTPUT_PUBLISH_FAILED) from error
            if os.name == "nt":
                temporary.unlink()
            else:
                os.unlink(temporary.name, dir_fd=parent)
        else:
            try:
                metadata = _output_named_metadata(binding.path, parent)
            except FileNotFoundError:
                raise ContractError(TRANSFER_OUTPUT_IDENTITY_DRIFT)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or stat.S_ISLNK(metadata.st_mode)
                or bool(getattr(metadata, "st_file_attributes", 0) & 0x400)
                or _output_metadata_identity(metadata) != binding.destination_identity
            ):
                raise ContractError(TRANSFER_OUTPUT_IDENTITY_DRIFT)
            if os.name == "nt":
                os.replace(temporary, binding.path)
            else:
                os.replace(
                    temporary.name,
                    binding.path.name,
                    src_dir_fd=parent,
                    dst_dir_fd=parent,
                )
        metadata = _output_named_metadata(binding.path, parent)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or bool(getattr(metadata, "st_file_attributes", 0) & 0x400)
        ):
            raise ContractError(TRANSFER_OUTPUT_PUBLISH_FAILED)
        if _require_ordinary_directory(binding.path.parent) != binding.parent_identity:
            raise ContractError(TRANSFER_OUTPUT_IDENTITY_DRIFT)
        if os.name == "nt":
            _fsync_output_parent(binding.path.parent)
        else:
            assert parent is not None
            os.fsync(parent)
    except OSError as error:
        raise ContractError(TRANSFER_OUTPUT_PUBLISH_FAILED) from error


def publish_output_bytes(binding: OutputBinding, payload: bytes) -> None:
    with _bound_output_temporary(binding) as stream:
        stream.write(payload)


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
    if path_has_surrogateescape(path):
        return "non-UTF-8 path encoding"
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


def path_has_surrogateescape(path: str) -> bool:
    found = False
    for character in path:
        codepoint = ord(character)
        if 0xDC80 <= codepoint <= 0xDCFF:
            found = True
        elif 0xD800 <= codepoint <= 0xDFFF:
            raise ContractError(TRANSFER_PATH_ENCODING_INVALID)
    return found


def portable_path_key(path: str) -> str:
    return unicodedata.normalize("NFKC", path).casefold()


def portable_segment_key(segment: str) -> str:
    return unicodedata.normalize("NFKC", segment).casefold()


def portable_path_parts(path: str) -> tuple[str, ...]:
    return tuple(portable_segment_key(part) for part in PurePosixPath(unicodedata.normalize("NFKC", path)).parts)


class PortablePathTree:
    def __init__(self) -> None:
        self._root = self._new_node()

    @staticmethod
    def _new_node() -> dict[str, Any]:
        return {
            "terminal": False,
            "terminalCount": 0,
            "paths": set(),
            "children": {},
        }

    def add(self, path: str) -> bool:
        node = self._root
        for part in portable_path_parts(path):
            if node["terminal"]:
                return False
            node = node["children"].setdefault(part, self._new_node())
        if node["terminal"] or node["children"]:
            return False
        node["terminal"] = True
        return True

    def record(self, path: str) -> None:
        node = self._root
        for part in portable_path_parts(path):
            node = node["children"].setdefault(part, self._new_node())
        node["terminal"] = True
        node["terminalCount"] += 1
        node["paths"].add(path)

    def conflicts(self) -> set[str]:
        conflicts: set[str] = set()
        subtree_terminals: dict[int, bool] = {}
        stack: list[tuple[dict[str, Any], bool, bool]] = [
            (self._root, False, False)
        ]
        while stack:
            node, ancestor_is_terminal, expanded = stack.pop()
            current_is_terminal = bool(node["terminal"])
            children = tuple(node["children"].values())
            if not expanded:
                stack.append((node, ancestor_is_terminal, True))
                child_ancestor = ancestor_is_terminal or current_is_terminal
                for child in reversed(children):
                    stack.append((child, child_ancestor, False))
                continue
            descendant_is_terminal = False
            for child in children:
                descendant_is_terminal = (
                    subtree_terminals.pop(id(child)) or descendant_is_terminal
                )
            if current_is_terminal and (
                ancestor_is_terminal
                or descendant_is_terminal
                or node["terminalCount"] > 1
                or len(node["paths"]) > 1
            ):
                conflicts.update(node["paths"])
            subtree_terminals[id(node)] = (
                current_is_terminal or descendant_is_terminal
            )
        return conflicts


def portable_path_conflicts(paths: Iterable[str]) -> set[str]:
    tree = PortablePathTree()
    for path in paths:
        tree.record(path)
    return tree.conflicts()


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


def repository_history(repository: BoundRepository) -> tuple[str, str | None]:
    resolved = run_git(repository, "rev-parse", "--verify", "--quiet", "HEAD", check=False)
    if resolved.returncode == 0:
        head = resolved.stdout.decode("utf-8").strip()
        if not head:
            raise ContractError("invalid HEAD state")
        return "committed", head
    symbolic = run_git(repository, "symbolic-ref", "--quiet", "HEAD", check=False)
    if symbolic.returncode != 0 or not symbolic.stdout.strip():
        raise ContractError("invalid HEAD state")
    current_ref = symbolic.stdout.decode("utf-8").strip()
    existing_ref = run_git(repository, "show-ref", "--verify", "--quiet", current_ref, check=False)
    if existing_ref.returncode == 1:
        return "unborn", None
    raise ContractError("invalid HEAD state")


def document_history_state(repository: Any) -> str:
    if not isinstance(repository, dict):
        raise ContractError("invalid repository history state")
    history_state = repository.get("historyState")
    head = repository.get("head")
    if "historyState" not in repository and isinstance(head, str):
        return "committed"
    if history_state == "committed" and isinstance(head, str):
        return "committed"
    if history_state == "unborn" and head is None:
        return "unborn"
    raise ContractError("invalid repository history state")


def remote_evidence(repository: BoundRepository, head: str | None) -> tuple[list[dict[str, str]], dict[str, dict[str, Any]]]:
    remotes: list[dict[str, str]] = []
    evidence: dict[str, dict[str, Any]] = {}
    for name in run_git(repository, "remote").stdout.decode("utf-8").splitlines():
        raw_url = run_git(repository, "remote", "get-url", name, check=False).stdout.decode("utf-8", "replace").strip()
        reachable = False
        references = run_git(repository, "for-each-ref", "--format=%(refname)", f"refs/remotes/{name}/").stdout.decode("utf-8").splitlines()
        if head is not None:
            for reference in references:
                if run_git(repository, "merge-base", "--is-ancestor", head, reference, check=False).returncode == 0:
                    reachable = True
                    break
        remotes.append({"name": name, "url": safe_remote_url(raw_url)})
        evidence[name] = {"kind": "local-tracking", "headReachable": reachable}
    return remotes, evidence


def literal_pathspecs(paths: list[str]) -> list[str]:
    return [f":(literal){path}" for path in paths]


def git_metadata(repository: BoundRepository, paths: list[str] | None = None) -> dict[str, bytes]:
    if paths == []:
        return {name: b"" for name in METADATA_NAMES}
    suffix = [] if paths is None else ["--", *literal_pathspecs(paths)]
    return {
        METADATA_NAMES[0]: run_git(repository, "status", "--no-renames", "--porcelain=v1", "-z", "--untracked-files=all", *suffix).stdout,
        METADATA_NAMES[1]: run_git(repository, "diff", "--no-renames", "--cached", "--binary", "--no-ext-diff", "--no-textconv", *suffix).stdout,
        METADATA_NAMES[2]: run_git(repository, "diff", "--no-renames", "--binary", "--no-ext-diff", "--no-textconv", *suffix).stdout,
    }


def walk_repository(root: Path) -> Iterable[tuple[str, Path, str]]:
    def traversal_error(error: OSError) -> None:
        raise ContractError("repository traversal failed") from error

    def classify(child: Path, relative: str) -> str:
        try:
            metadata = child.lstat()
        except OSError as error:
            raise ContractError(f"repository entry is unreadable: {relative}") from error
        attributes = getattr(metadata, "st_file_attributes", 0) or 0
        if stat.S_ISLNK(metadata.st_mode) or attributes & 0x400:
            return "reparse"
        if stat.S_ISDIR(metadata.st_mode):
            return "directory"
        if stat.S_ISREG(metadata.st_mode):
            return "file"
        raise ContractError(f"unsupported repository entry: {relative}")

    for current, directories, files in os.walk(
        root,
        topdown=True,
        followlinks=False,
        onerror=traversal_error,
    ):
        current_path = Path(current)
        kept_directories: list[str] = []
        for name in sorted(set(directories) | set(files)):
            child = current_path / name
            relative = child.relative_to(root).as_posix()
            if name == ".git":
                if current_path == root:
                    continue
                raise ContractError(f"unsupported repository entry: {relative}")
            entry_type = classify(child, relative)
            if entry_type == "directory":
                kept_directories.append(name)
            else:
                yield relative, child, entry_type
        directories[:] = kept_directories


def build_inventory(repository: BoundRepository) -> dict[str, Any]:
    root = repository.root
    history_state, head = repository_history(repository)
    index_tracked = nul_delimited_paths(run_git(repository, "ls-files", "-z"))
    head_tracked = set() if head is None else nul_delimited_paths(run_git(repository, "ls-tree", "-r", "-z", "--name-only", head))
    tracked = index_tracked | head_tracked
    ignored = nul_delimited_paths(run_git(repository, "ls-files", "--others", "--ignored", "--exclude-standard", "-z"))
    dirty = nul_delimited_paths(run_git(repository, "diff", "--no-renames", "--cached", "--name-only", "-z"))
    dirty |= nul_delimited_paths(run_git(repository, "diff", "--no-renames", "--name-only", "-z"))
    flagged_tracked = {
        item[2:].decode("utf-8", "surrogateescape")
        for item in run_git(repository, "ls-files", "-v", "-z").stdout.split(b"\0")
        if len(item) > 2 and item[1:2] == b" " and (item[:1].islower() or item[:1].upper() == b"S")
    }
    dirty |= flagged_tracked
    remotes, evidence = remote_evidence(repository, head)
    metadata_hashes = {name: sha256_bytes(data) for name, data in git_metadata(repository).items()}
    entries: list[dict[str, Any]] = []
    for relative, path, entry_type in walk_repository(root):
        git_class = "tracked" if relative in tracked else "ignored" if relative in ignored else "untracked"
        entry: dict[str, Any] = {"path": relative, "entryType": entry_type, "gitClass": git_class, "dirtyTracked": relative in dirty}
        if entry_type == "reparse":
            target, kind = link_metadata(path)
            entry.update(metadataOnly=True, linkTarget=target, linkKind=kind)
        else:
            size, digest = inventory_regular_file(path)
            entry.update(size=size, sha256=digest)
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
    repository_data = {"historyState": history_state, "head": head, "remotes": remotes, "remoteEvidence": evidence, "gitExecutable": {"path": str(repository.git_executable), "sha256": repository.git_executable_content_sha256}, "gitMetadataHashes": metadata_hashes}
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
    with BoundOrdinaryInputSession(path) as bound_input:
        data = bound_input.read_bounded(MAX_JSON_BYTES, label)
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
    try:
        document_history_state(repository)
    except ContractError as error:
        raise ContractError("invalid inventory snapshot") from error
    if (
        inventory.get("schemaVersion") != SCHEMA_VERSION
        or inventory.get("snapshot", {}).get("digest") != expected
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
        if path_has_surrogateescape(entry["path"]) and (
            entry.get("hostile") is not True or entry.get("metadataOnly") is not True
        ):
            raise ContractError("invalid inventory snapshot")
        if entry.get("entryType") not in {"file", "reparse", "deleted"} or entry.get("gitClass") not in {"tracked", "untracked", "ignored"}:
            raise ContractError("invalid inventory snapshot")
        if entry["entryType"] == "file" and (not isinstance(entry.get("size"), int) or entry["size"] < 0 or not is_sha256(entry.get("sha256"))):
            raise ContractError("invalid inventory snapshot")


def selection_path(root: Path, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError("selection path is invalid")
    path_has_surrogateescape(value)
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
    history_state = document_history_state(inventory["repository"])
    if history_state == "unborn" and mode != "none":
        raise ContractError("unborn repositories require git strategy none")
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
        surrogate_entries = [entry for entry in entries if path_has_surrogateescape(entry["path"])]
        if surrogate_entries and (
            disposition != "external"
            or len(entries) != 1
            or entries[0]["path"] != path
        ):
            raise ContractError(TRANSFER_HOSTILE_PATH_EXTERNAL_REQUIRED)
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
            if history_state == "unborn" and proof["kind"] == "git-recoverable":
                raise ContractError("unborn repository has no verified Git history")
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
                if path_has_surrogateescape(entry["path"]):
                    raise ContractError(TRANSFER_HOSTILE_PATH_EXTERNAL_REQUIRED)
                raise ContractError("reparse entries require external disposition; reparse or hostile entries require external disposition")
    return normalized


def require_current_inventory(repository: BoundRepository, inventory: dict[str, Any], message: str = "inventory drift") -> None:
    if build_inventory(repository)["snapshot"]["digest"] != inventory["snapshot"]["digest"]:
        raise ContractError(message)


def included_entries(inventory: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [entry for entry in inventory["entries"] if any(row["disposition"] == "include" and covers(row["path"], entry["path"]) for row in rows)]


def expected_material(repository: BoundRepository, inventory: dict[str, Any], rows: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, bytes]]:
    payload: dict[str, dict[str, Any]] = {}
    metadata_paths: list[str] = []
    for entry in included_entries(inventory, rows):
        if entry.get("metadataOnly") or entry.get("hostile"):
            if path_has_surrogateescape(entry["path"]):
                raise ContractError(TRANSFER_HOSTILE_PATH_EXTERNAL_REQUIRED)
            raise ContractError("reparse entries require external disposition")
        metadata_paths.append(entry["path"])
        if entry["entryType"] == "deleted":
            continue
        payload[entry["path"]] = entry
    return payload, git_metadata(repository, sorted(metadata_paths))


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


def write_file_member(
    archive: zipfile.ZipFile,
    name: str,
    input_session: "BoundPayloadInputSession",
    expected: dict[str, Any],
) -> None:
    with archive.open(deterministic_zip_info(name), "w") as output_stream:
        consume_payload(input_session, expected, output_stream)


def consume_payload(
    input_session: "BoundPayloadInputSession",
    expected: dict[str, Any],
    output_stream: Any | None = None,
) -> None:
    input_session.consume_census(
        expected["size"],
        expected_sha256=expected["sha256"],
        output_stream=output_stream,
    )


def bundle(repository: BoundRepository, inventory_path: Path, selection_path: Path, output: Path, *, force: bool = False) -> None:
    root = repository.root
    output_binding = bind_output(output, root, force=force)
    inventory = read_json(inventory_path, "inventory")
    selection = read_json(selection_path, "selection")
    validate_inventory(inventory)
    rows = validate_selection(root, inventory, selection)
    require_current_inventory(repository, inventory)
    payload, metadata = expected_material(repository, inventory, rows)
    manifest = {"schemaVersion": SCHEMA_VERSION, "inventoryDigest": inventory["snapshot"]["digest"], "selectionDigest": sha256_bytes(canonical_json(selection)), "repository": {"historyState": document_history_state(inventory["repository"]), "head": inventory["repository"]["head"], "gitExecutable": inventory["repository"]["gitExecutable"]}, "payload": [{"path": name, "size": entry["size"], "sha256": entry["sha256"]} for name, entry in sorted(payload.items())], "metadata": [{"path": name, "size": len(data), "sha256": sha256_bytes(data)} for name, data in sorted(metadata.items())], "deletions": expected_deletions(inventory, rows)}
    manifest_bytes = capped_canonical_json(manifest, "archive resource limit")
    declared_sizes = [entry["size"] for entry in payload.values()] + [len(data) for data in metadata.values()] + [len(manifest_bytes)]
    if len(declared_sizes) > MAX_ARCHIVE_ENTRIES or any(size > MAX_ARCHIVE_ENTRY_BYTES for size in declared_sizes) or sum(declared_sizes) > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
        raise ContractError("archive resource limit")
    with _bound_output_temporary(output_binding) as temporary_stream:
        with zipfile.ZipFile(temporary_stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, entry in sorted(payload.items()):
                source = root.joinpath(*PurePosixPath(name).parts)
                with BoundPayloadInputSession(source) as input_session:
                    write_file_member(archive, name, input_session, entry)
            for name, data in sorted(metadata.items()):
                archive.writestr(deterministic_zip_info(name), data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
            archive.writestr(deterministic_zip_info(MANIFEST_PATH), manifest_bytes, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
            enforce_archive_infos(archive.infolist())


def validate_archive_name(name: str) -> str:
    if path_has_surrogateescape(name):
        raise ContractError(TRANSFER_HOSTILE_PATH_EXTERNAL_REQUIRED)
    portable = PurePosixPath(name)
    if name in {"", "."} or name.endswith("/") or name != portable.as_posix() or portable_path_issue(name):
        raise ContractError("unsafe archive entry")
    return portable.as_posix()


def _posix_handle_identity(descriptor: int, *, include_change_stamp: bool) -> tuple[int, ...]:
    metadata = os.fstat(descriptor)
    base = (metadata.st_dev, metadata.st_ino, metadata.st_mode)
    if not include_change_stamp:
        return base
    return (
        *base,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _windows_kernel32() -> Any:
    import ctypes

    return ctypes.WinDLL("kernel32", use_last_error=True)


_WINDOWS_DOS_DEVICE_BASENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "CLOCK$",
    "CONIN$",
    "CONOUT$",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
    *(f"COM{index}" for index in "¹²³"),
    *(f"LPT{index}" for index in "¹²³"),
}
class _OrdinaryFileErrors:
    __slots__ = ("binding", "drift", "close")

    def __init__(self, *, binding: str, drift: str, close: str) -> None:
        self.binding = binding
        self.drift = drift
        self.close = close


class _OrdinaryFileOptions:
    __slots__ = ("errors", "posix_nonblocking")

    def __init__(
        self,
        *,
        errors: _OrdinaryFileErrors,
        posix_nonblocking: bool,
    ) -> None:
        self.errors = errors
        self.posix_nonblocking = posix_nonblocking


_ARCHIVE_FILE_OPTIONS = _OrdinaryFileOptions(
    errors=_OrdinaryFileErrors(
        binding=TRANSFER_ARCHIVE_BINDING_INVALID,
        drift=TRANSFER_ARCHIVE_IDENTITY_DRIFT,
        close=TRANSFER_ARCHIVE_CLOSE_FAILED,
    ),
    posix_nonblocking=False,
)
_OUTPUT_FILE_OPTIONS = _OrdinaryFileOptions(
    errors=_OrdinaryFileErrors(
        binding=TRANSFER_OUTPUT_IDENTITY_DRIFT,
        drift=TRANSFER_OUTPUT_IDENTITY_DRIFT,
        close=TRANSFER_OUTPUT_PUBLISH_FAILED,
    ),
    posix_nonblocking=False,
)
_INPUT_FILE_OPTIONS = _OrdinaryFileOptions(
    errors=_OrdinaryFileErrors(
        binding=TRANSFER_INPUT_BINDING_INVALID,
        drift=TRANSFER_INPUT_IDENTITY_DRIFT,
        close=TRANSFER_INPUT_CLOSE_FAILED,
    ),
    posix_nonblocking=True,
)
_PAYLOAD_FILE_OPTIONS = _OrdinaryFileOptions(
    errors=_OrdinaryFileErrors(
        binding="inventory drift",
        drift="inventory drift",
        close="inventory drift",
    ),
    posix_nonblocking=True,
)


def _validate_windows_ordinary_path_text(
    value: str,
    *,
    absolute: bool,
    options: _OrdinaryFileOptions,
) -> None:
    errors = options.errors
    normalized = value.replace("/", "\\")
    folded = normalized.casefold()
    if "\0" in normalized or folded.startswith(
        ("\\\\?\\", "\\\\.\\", "\\??\\", "\\\\??\\")
    ):
        raise ContractError(errors.binding)

    components: list[str]
    if normalized.startswith("\\\\"):
        parts = normalized[2:].split("\\")
        if len(parts) < 2 or not parts[0] or not parts[1] or any(
            not component for component in parts
        ):
            raise ContractError(errors.binding)
        components = parts
    elif normalized.startswith("\\"):
        raise ContractError(errors.binding)
    elif re.match(r"^[A-Za-z]:", normalized):
        if len(normalized) < 3 or normalized[2] != "\\":
            raise ContractError(errors.binding)
        if ":" in normalized[2:]:
            raise ContractError(errors.binding)
        components = [
            component for component in normalized[3:].split("\\") if component
        ]
    else:
        if absolute or ":" in normalized:
            raise ContractError(errors.binding)
        components = [component for component in normalized.split("\\") if component]

    for component in components:
        if (
            component.endswith((".", " "))
            or ":" in component
            or component.split(".", 1)[0].upper() in _WINDOWS_DOS_DEVICE_BASENAMES
        ):
            raise ContractError(errors.binding)


def _canonical_windows_ordinary_path(
    raw_path: str | os.PathLike[str],
    options: _OrdinaryFileOptions,
) -> Path:
    errors = options.errors
    try:
        lexical = os.fspath(raw_path)
        if not isinstance(lexical, str) or not lexical:
            raise ContractError(errors.binding)
        _validate_windows_ordinary_path_text(
            lexical,
            absolute=False,
            options=options,
        )
        normalized = lexical.replace("/", "\\")
        canonical = (
            ntpath.normpath(normalized)
            if normalized.startswith("\\\\")
            else ntpath.abspath(normalized)
        )
        _validate_windows_ordinary_path_text(
            canonical,
            absolute=True,
            options=options,
        )
        drive, tail = ntpath.splitdrive(canonical)
        if drive.startswith("\\\\"):
            if not tail.startswith("\\"):
                raise ContractError(errors.binding)
        elif not re.fullmatch(r"[A-Za-z]:", drive) or not tail.startswith("\\"):
            raise ContractError(errors.binding)
        return Path(canonical)
    except ContractError:
        raise
    except (OSError, TypeError, ValueError) as error:
        raise ContractError(errors.binding) from error


class _OrdinaryFileAcquisitionOwner:
    def __init__(self, errors: _OrdinaryFileErrors) -> None:
        self.errors = errors
        self.state = "none"
        self.windows_handle: int | None = None
        self.fd: int | None = None
        self.stream: Any | None = None

    def _require_none(self) -> None:
        if self.state != "none":
            raise ContractError(self.errors.binding)

    def take_windows_handle(self, handle: int) -> None:
        self._require_none()
        self.windows_handle = handle
        self.state = "windows-handle"

    def take_fd(self, descriptor: int) -> None:
        self._require_none()
        self.fd = descriptor
        self.state = "fd"

    def windows_handle_to_fd(self, flags: int) -> None:
        import msvcrt

        if self.state != "windows-handle" or self.windows_handle is None:
            raise ContractError(self.errors.binding)
        descriptor = msvcrt.open_osfhandle(self.windows_handle, flags)
        self.windows_handle = None
        self.fd = descriptor
        self.state = "fd"

    def fd_to_stream(self, mode: str = "rb", *, buffering: int = 0) -> None:
        if self.state != "fd" or self.fd is None:
            raise ContractError(self.errors.binding)
        stream = os.fdopen(self.fd, mode, buffering=buffering)
        self.fd = None
        self.stream = stream
        self.state = "stream"

    def release_windows_handle(self) -> int:
        if self.state != "windows-handle" or self.windows_handle is None:
            raise ContractError(self.errors.binding)
        handle = self.windows_handle
        self.windows_handle = None
        self.state = "none"
        return handle

    def release_stream(self) -> Any:
        if self.state != "stream" or self.stream is None:
            raise ContractError(self.errors.binding)
        stream = self.stream
        self.stream = None
        self.state = "none"
        return stream

    def rollback(self, primary: BaseException) -> None:
        state = self.state
        handle = self.windows_handle
        descriptor = self.fd
        stream = self.stream
        self.state = "none"
        self.windows_handle = None
        self.fd = None
        self.stream = None
        try:
            if state == "stream" and stream is not None:
                stream.close()
            elif state == "fd" and descriptor is not None:
                os.close(descriptor)
            elif state == "windows-handle" and handle is not None:
                _windows_close_handle(handle)
        except BaseException:
            raise ContractError(self.errors.close) from primary


def _windows_close_handle(handle: int) -> None:
    import ctypes
    from ctypes import wintypes

    if not handle:
        return
    close_handle = _windows_kernel32().CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL
    if not close_handle(ctypes.c_void_p(handle)):
        raise OSError(ctypes.get_last_error(), "CloseHandle failed")


def _windows_open_ordinary_path(
    path: Path,
    *,
    directory: bool,
    options: _OrdinaryFileOptions,
    owner: _OrdinaryFileAcquisitionOwner | None = None,
    share_write: bool = False,
) -> int:
    import ctypes
    from ctypes import wintypes

    errors = options.errors
    if share_write and options is not _OUTPUT_FILE_OPTIONS:
        raise ContractError(errors.binding)
    acquisition = owner or _OrdinaryFileAcquisitionOwner(errors)
    if acquisition.errors is not errors:
        raise ContractError(errors.binding)
    acquisition._require_none()
    try:
        kernel32 = _windows_kernel32()
        create_file = kernel32.CreateFileW
        create_file.argtypes = (
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        )
        create_file.restype = wintypes.HANDLE
        desired_access = 0x00000001 | 0x00000080 if directory else 0x80000000
        flags = 0x00200000 | (0x02000000 if directory else 0x08000000)
        share_mode = 0x00000001 | (0x00000002 if share_write else 0)
        handle = create_file(
            str(path), desired_access, share_mode, None, 3, flags, None
        )
        invalid = ctypes.c_void_p(-1).value
        value = int(handle) if handle else 0
        if not value or value == invalid:
            error = ctypes.get_last_error()
            raise OSError(error, os.strerror(error), str(path))
        acquisition.take_windows_handle(value)
        set_handle_information = kernel32.SetHandleInformation
        set_handle_information.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.DWORD,
        )
        set_handle_information.restype = wintypes.BOOL
        if not set_handle_information(
            ctypes.c_void_p(value), 0x00000001, 0
        ):
            raise OSError(ctypes.get_last_error(), "SetHandleInformation failed")
        identity = _windows_handle_identity(value, include_change_stamp=False)
        attributes = identity[3]
        if attributes & 0x00000400:
            raise ContractError(errors.binding)
        is_directory = bool(attributes & 0x00000010)
        if is_directory != directory:
            raise ContractError(errors.binding)
        return (
            value
            if owner is not None
            else acquisition.release_windows_handle()
        )
    except BaseException as error:
        primary = (
            error
            if isinstance(error, ContractError)
            and str(error) == errors.binding
            else ContractError(errors.binding)
        )
        acquisition.rollback(primary)
        if primary is error:
            raise
        raise primary from error


def _windows_handle_identity(handle: int, *, include_change_stamp: bool) -> tuple[int, ...]:
    import ctypes
    from ctypes import wintypes

    class ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("attributes", wintypes.DWORD),
            ("creation", wintypes.FILETIME),
            ("access", wintypes.FILETIME),
            ("write", wintypes.FILETIME),
            ("volume", wintypes.DWORD),
            ("size_high", wintypes.DWORD),
            ("size_low", wintypes.DWORD),
            ("links", wintypes.DWORD),
            ("index_high", wintypes.DWORD),
            ("index_low", wintypes.DWORD),
        ]

    information = ByHandleFileInformation()
    get_information = _windows_kernel32().GetFileInformationByHandle
    get_information.argtypes = (wintypes.HANDLE, ctypes.POINTER(ByHandleFileInformation))
    get_information.restype = wintypes.BOOL
    if not get_information(
        ctypes.c_void_p(handle), ctypes.byref(information)
    ):
        raise OSError(ctypes.get_last_error(), "GetFileInformationByHandle failed")
    base = (
        int(information.volume),
        (int(information.index_high) << 32) | int(information.index_low),
        int(information.links),
        int(information.attributes),
    )
    if not include_change_stamp:
        return base
    return (
        *base,
        (int(information.size_high) << 32) | int(information.size_low),
        (int(information.write.dwHighDateTime) << 32)
        | int(information.write.dwLowDateTime),
    )


def _posix_ordinary_open_flags(
    options: _OrdinaryFileOptions,
    *,
    directory: bool,
) -> int:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    if options.posix_nonblocking:
        flags |= getattr(os, "O_NONBLOCK", 0)
    if directory:
        flags |= getattr(os, "O_DIRECTORY", 0)
    return flags


class _BoundOrdinaryFileCore:
    def __init__(
        self,
        path: Path,
        options: _OrdinaryFileOptions,
    ) -> None:
        self.options = options
        self.errors = options.errors
        try:
            self.path = (
                _canonical_windows_ordinary_path(path, options)
                if os.name == "nt"
                else Path(os.path.abspath(path))
            )
        except (ContractError, OSError, TypeError, ValueError) as error:
            if isinstance(error, ContractError) and str(error) == self.errors.binding:
                raise
            raise ContractError(self.errors.binding) from error
        self.parent_handles: list[int] = []
        self.parent_identities: list[tuple[int, ...]] = []
        self.raw_stream: Any | None = None
        self.leaf_identity: tuple[int, ...] | None = None
        self.eof = 0
        self.closed = False
        try:
            self._open_bound_leaf()
        except BaseException as error:
            try:
                self.close(validate=False)
            except BaseException as cleanup_error:
                raise cleanup_error from error
            raise

    def _open_bound_leaf(self) -> None:
        try:
            if not self.path.is_absolute() or not self.path.name:
                raise ContractError(self.errors.binding)
            if os.name == "nt":
                self._open_windows_leaf()
            else:
                self._open_posix_leaf()
        except ContractError as error:
            if str(error) in {self.errors.binding, self.errors.close}:
                raise
            raise ContractError(self.errors.binding) from error
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            raise ContractError(self.errors.binding) from error

    def _open_posix_leaf(self) -> None:
        flags = _posix_ordinary_open_flags(self.options, directory=False)
        directory_flags = _posix_ordinary_open_flags(
            self.options,
            directory=True,
        )
        anchor = Path(self.path.anchor)
        descriptor = os.open(anchor, directory_flags)
        self.parent_handles.append(descriptor)
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise ContractError(self.errors.binding)
        self.parent_identities.append(
            _posix_handle_identity(descriptor, include_change_stamp=False)
        )
        relative_parent = self.path.parent.relative_to(anchor)
        for component in relative_parent.parts:
            descriptor = os.open(component, directory_flags, dir_fd=descriptor)
            self.parent_handles.append(descriptor)
            if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
                raise ContractError(self.errors.binding)
            self.parent_identities.append(
                _posix_handle_identity(descriptor, include_change_stamp=False)
            )
        acquisition = _OrdinaryFileAcquisitionOwner(self.errors)
        try:
            descriptor = os.open(
                self.path.name, flags, dir_fd=self.parent_handles[-1]
            )
            acquisition.take_fd(descriptor)
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise ContractError(self.errors.binding)
            acquisition.fd_to_stream()
            self.raw_stream = acquisition.release_stream()
            self.leaf_identity = _posix_handle_identity(
                self.raw_stream.fileno(), include_change_stamp=True
            )
            self.eof = metadata.st_size
        except BaseException as error:
            primary = (
                error
                if isinstance(error, ContractError)
                and str(error) in {self.errors.binding, self.errors.close}
                else ContractError(self.errors.binding)
            )
            acquisition.rollback(primary)
            if primary is error:
                raise
            raise primary from error

    def _open_windows_leaf(self) -> None:
        import msvcrt

        chain: list[Path] = []
        cursor = self.path.parent
        while True:
            chain.append(cursor)
            if cursor.parent == cursor:
                break
            cursor = cursor.parent
        for component in reversed(chain):
            handle = _windows_open_ordinary_path(
                component,
                directory=True,
                options=self.options,
            )
            self.parent_handles.append(handle)
            self.parent_identities.append(
                _windows_handle_identity(handle, include_change_stamp=False)
            )
        acquisition = _OrdinaryFileAcquisitionOwner(self.errors)
        try:
            _windows_open_ordinary_path(
                self.path,
                directory=False,
                options=self.options,
                owner=acquisition,
            )
            acquisition.windows_handle_to_fd(
                os.O_RDONLY
                | getattr(os, "O_BINARY", 0)
                | getattr(os, "O_NOINHERIT", 0),
            )
            acquisition.fd_to_stream()
            self.raw_stream = acquisition.release_stream()
            current_handle = msvcrt.get_osfhandle(self.raw_stream.fileno())
            self.leaf_identity = _windows_handle_identity(
                current_handle, include_change_stamp=True
            )
            self.eof = self.leaf_identity[4]
        except BaseException as error:
            primary = (
                error
                if isinstance(error, ContractError)
                and str(error) in {self.errors.binding, self.errors.close}
                else ContractError(self.errors.binding)
            )
            acquisition.rollback(primary)
            if primary is error:
                raise
            raise primary from error

    def _current_leaf_identity(self) -> tuple[int, ...]:
        if self.raw_stream is None:
            raise ContractError(self.errors.drift)
        if os.name == "nt":
            import msvcrt

            return _windows_handle_identity(
                msvcrt.get_osfhandle(self.raw_stream.fileno()),
                include_change_stamp=True,
            )
        return _posix_handle_identity(
            self.raw_stream.fileno(), include_change_stamp=True
        )

    def _require_parent_identities(self) -> None:
        for handle, expected in zip(
            self.parent_handles, self.parent_identities, strict=True
        ):
            current = (
                _windows_handle_identity(handle, include_change_stamp=False)
                if os.name == "nt"
                else _posix_handle_identity(handle, include_change_stamp=False)
            )
            if current != expected:
                raise ContractError(self.errors.drift)

    def _require_name_binding(self) -> None:
        if os.name == "nt":
            handle = _windows_open_ordinary_path(
                self.path,
                directory=False,
                options=self.options,
            )
            try:
                current = _windows_handle_identity(
                    handle, include_change_stamp=True
                )
            finally:
                _windows_close_handle(handle)
        else:
            flags = _posix_ordinary_open_flags(self.options, directory=False)
            descriptor = os.open(
                self.path.name, flags, dir_fd=self.parent_handles[-1]
            )
            try:
                metadata = os.fstat(descriptor)
                if not stat.S_ISREG(metadata.st_mode):
                    raise ContractError(self.errors.drift)
                current = _posix_handle_identity(
                    descriptor, include_change_stamp=True
                )
            finally:
                os.close(descriptor)
        if current != self.leaf_identity:
            raise ContractError(self.errors.drift)

    def require_stable(self) -> None:
        try:
            if self._current_leaf_identity() != self.leaf_identity:
                raise ContractError(self.errors.drift)
            self._require_parent_identities()
            self._require_name_binding()
        except ContractError:
            raise
        except (OSError, RuntimeError, ValueError) as error:
            raise ContractError(self.errors.drift) from error

    def close(self, *, validate: bool = True) -> None:
        if self.closed:
            return
        self.closed = True
        failed = False
        if validate and self.raw_stream is not None:
            try:
                self.require_stable()
            except BaseException:
                failed = True
                drift = sys.exc_info()[1]
            else:
                drift = None
        else:
            drift = None
        if self.raw_stream is not None:
            try:
                self.raw_stream.close()
            except BaseException:
                failed = True
        for handle in reversed(self.parent_handles):
            try:
                if os.name == "nt":
                    _windows_close_handle(handle)
                else:
                    os.close(handle)
            except BaseException:
                failed = True
        self.parent_handles.clear()
        if drift is not None:
            raise drift
        if failed:
            raise ContractError(self.errors.close)


class BoundArchiveSession(_BoundOrdinaryFileCore):
    def __init__(self, bundle_path: Path) -> None:
        self.stream: Any | None = None
        self.archive: BoundArchiveZipFile | None = None
        self.members: set[TrackedArchiveMember] = set()
        super().__init__(bundle_path, _ARCHIVE_FILE_OPTIONS)
        try:
            assert self.raw_stream is not None
            self.stream = BoundArchiveStream(self.raw_stream, self)
            layout = preflight_archive(self.stream)
            self.require_stable()
            self.archive = BoundArchiveZipFile(self.stream, self)
            validate_archive_boundaries(self.archive, layout)
            self.require_stable()
        except BaseException as error:
            try:
                self.close(validate=False)
            except BaseException as cleanup_error:
                raise cleanup_error from error
            raise

    def close(self, *, validate: bool = True) -> None:
        if self.closed:
            return
        failed = False
        for member in tuple(self.members):
            try:
                member.close()
            except BaseException:
                failed = True
        if self.archive is not None:
            try:
                self.archive.close()
            except BaseException:
                failed = True
        drift: BaseException | None = None
        try:
            super().close(validate=validate)
        except ContractError as error:
            if str(error) == TRANSFER_ARCHIVE_IDENTITY_DRIFT:
                drift = error
            else:
                failed = True
        if drift is not None:
            raise drift
        if failed:
            raise ContractError(TRANSFER_ARCHIVE_CLOSE_FAILED)

    def read_exact_at(
        self,
        offset: int,
        size: int,
        *,
        cap: int,
        allowed_lengths: set[int] | None = None,
    ) -> bytes:
        if (
            type(offset) is not int
            or type(size) is not int
            or type(cap) is not int
            or offset < 0
            or size < 0
            or cap < 0
            or size > cap
            or offset > self.eof
            or size > self.eof - offset
            or (allowed_lengths is not None and size not in allowed_lengths)
        ):
            raise ContractError(TRANSFER_ARCHIVE_BOUNDARY_INVALID)
        if self.stream is None:
            raise ContractError(TRANSFER_ARCHIVE_BOUNDARY_INVALID)
        self.stream.seek(offset)
        data = self.stream.read(size)
        if len(data) != size:
            raise ContractError(TRANSFER_ARCHIVE_BOUNDARY_INVALID)
        return data

    def __enter__(self) -> BoundArchiveZipFile:
        if self.archive is None or self.closed:
            raise ContractError(TRANSFER_ARCHIVE_BINDING_INVALID)
        return self.archive

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close(validate=True)


class BoundOrdinaryInputSession(_BoundOrdinaryFileCore):
    """One no-follow ordinary input held stable from classification through parse."""

    def __init__(self, input_path: Path) -> None:
        super().__init__(input_path, _INPUT_FILE_OPTIONS)

    def read_bounded(self, cap: int, label: str) -> bytes:
        if (
            type(cap) is not int
            or cap < 0
            or self.raw_stream is None
            or self.eof > cap
        ):
            raise ContractError(f"invalid {label}")
        try:
            data = self.raw_stream.read(cap + 1)
        except OSError as error:
            raise ContractError(TRANSFER_INPUT_IDENTITY_DRIFT) from error
        if len(data) != self.eof:
            raise ContractError(TRANSFER_INPUT_IDENTITY_DRIFT)
        self.require_stable()
        return data

    def __enter__(self) -> "BoundOrdinaryInputSession":
        if self.raw_stream is None or self.closed:
            raise ContractError(TRANSFER_INPUT_BINDING_INVALID)
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close(validate=True)


class BoundPayloadInputSession(_BoundOrdinaryFileCore):
    """One selected payload leaf held from classification through ZIP emission."""

    def __init__(self, input_path: Path) -> None:
        super().__init__(input_path, _PAYLOAD_FILE_OPTIONS)

    def consume_census(
        self,
        expected_size: int,
        *,
        expected_sha256: str | None = None,
        output_stream: Any | None = None,
    ) -> tuple[int, str]:
        if (
            self.raw_stream is None
            or type(expected_size) is not int
            or expected_size < 0
            or self.eof != expected_size
        ):
            raise ContractError("inventory drift")
        self.require_stable()
        digest = hashlib.sha256()
        size = 0
        remaining = expected_size + 1
        while remaining:
            try:
                chunk = self.raw_stream.read(min(1024 * 1024, remaining))
            except OSError as error:
                raise ContractError("inventory drift") from error
            if not chunk:
                break
            size += len(chunk)
            if size > expected_size:
                raise ContractError("inventory drift")
            digest.update(chunk)
            if output_stream is not None:
                output_stream.write(chunk)
            remaining -= len(chunk)
        self.require_stable()
        current_sha256 = digest.hexdigest()
        if size != expected_size or (
            expected_sha256 is not None and current_sha256 != expected_sha256
        ):
            raise ContractError("inventory drift")
        return size, current_sha256

    def __enter__(self) -> "BoundPayloadInputSession":
        if self.raw_stream is None or self.closed:
            raise ContractError("inventory drift")
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close(validate=True)


def inventory_regular_file(path: Path) -> tuple[int, str]:
    with BoundPayloadInputSession(path) as input_session:
        return input_session.consume_census(input_session.eof)


def preflight_archive(stream: BoundArchiveStream) -> dict[str, int]:
    try:
        file_size = stream.eof
        tail_size = min(file_size, 22 + 0xFFFF)
        tail = stream.read_exact_at(
            file_size - tail_size, tail_size, cap=22 + 0xFFFF
        )
        eocd_index = tail.rfind(b"PK\x05\x06")
        if eocd_index < 0 or eocd_index + 22 > len(tail):
            raise ContractError("invalid bundle")
        eocd_offset = file_size - tail_size + eocd_index
        disk, directory_disk, disk_entries, entries, directory_size, directory_offset, comment_size = struct.unpack_from("<HHHHIIH", tail, eocd_index + 4)
        if comment_size != 0 or eocd_offset + 22 != file_size:
            raise ContractError(TRANSFER_ARCHIVE_BOUNDARY_INVALID)
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
        locator = (
            stream.read_exact_at(locator_offset, 20, cap=20, allowed_lengths={20})
            if locator_offset >= 0
            else b""
        )
        has_zip64_locator = len(locator) == 20 and locator.startswith(b"PK\x06\x07")
        if has_zip64_locator:
            signature, zip64_disk, zip64_offset, disk_count = struct.unpack("<4sIQI", locator)
            if signature != b"PK\x06\x07" or zip64_disk != 0 or disk_count != 1 or zip64_offset >= locator_offset:
                raise ContractError("invalid bundle")
            header = stream.read_exact_at(
                zip64_offset, 56, cap=56, allowed_lengths={56}
            )
            if len(header) != 56:
                raise ContractError("invalid bundle")
            signature, record_size, _, _, disk, directory_disk, disk_entries, entries, directory_size, directory_offset = struct.unpack("<4sQ2H2I4Q", header)
            if (
                signature != b"PK\x06\x06"
                or record_size < 44
                or zip64_offset + 12 + record_size != locator_offset
                or disk != 0
                or directory_disk != 0
                or disk_entries != entries
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
        if directory_offset + directory_size != directory_boundary:
            raise ContractError(TRANSFER_ARCHIVE_BOUNDARY_INVALID)
        return {
            "directoryOffset": directory_offset,
            "directorySize": directory_size,
            "entries": entries,
        }
    except ContractError:
        raise
    except (OSError, struct.error, ValueError) as error:
        raise ContractError("invalid bundle") from error


def validate_archive_boundaries(archive: BoundArchiveZipFile, layout: dict[str, int]) -> None:
    """Require every archive byte to belong to one canonical ZIP region."""
    try:
        infos = archive.infolist()
        directory_offset = layout["directoryOffset"]
        directory_end = directory_offset + layout["directorySize"]
        if len(infos) != layout["entries"] or archive.start_dir != directory_offset:
            raise ContractError(TRANSFER_ARCHIVE_BOUNDARY_INVALID)
        stream = archive.fp
        if stream is None or not hasattr(stream, "read_exact_at"):
            raise ContractError(TRANSFER_ARCHIVE_BOUNDARY_INVALID)

        cursor = directory_offset
        for info in infos:
            header = stream.read_exact_at(
                cursor, 46, cap=46, allowed_lengths={46}
            )
            if header[:4] != b"PK\x01\x02":
                raise ContractError(TRANSFER_ARCHIVE_BOUNDARY_INVALID)
            name_size, extra_size, comment_size = struct.unpack_from("<HHH", header, 28)
            disk_start = struct.unpack_from("<H", header, 34)[0]
            local_offset = struct.unpack_from("<I", header, 42)[0]
            record_end = cursor + 46 + name_size + extra_size + comment_size
            if (
                record_end > directory_end
                or disk_start not in {0, 0xFFFF}
                or (local_offset != 0xFFFFFFFF and local_offset != info.header_offset)
            ):
                raise ContractError(TRANSFER_ARCHIVE_BOUNDARY_INVALID)
            cursor = record_end
        if cursor != directory_end:
            raise ContractError(TRANSFER_ARCHIVE_BOUNDARY_INVALID)

        ordered = sorted(infos, key=lambda item: item.header_offset)
        if ordered and ordered[0].header_offset != 0:
            raise ContractError(TRANSFER_ARCHIVE_BOUNDARY_INVALID)
        if len({info.header_offset for info in ordered}) != len(ordered):
            raise ContractError(TRANSFER_ARCHIVE_BOUNDARY_INVALID)
        for index, info in enumerate(ordered):
            region_end = (
                ordered[index + 1].header_offset
                if index + 1 < len(ordered)
                else directory_offset
            )
            header = stream.read_exact_at(
                info.header_offset, 30, cap=30, allowed_lengths={30}
            )
            if header[:4] != b"PK\x03\x04":
                raise ContractError(TRANSFER_ARCHIVE_BOUNDARY_INVALID)
            flags = struct.unpack_from("<H", header, 6)[0]
            compression = struct.unpack_from("<H", header, 8)[0]
            crc = struct.unpack_from("<I", header, 14)[0]
            compressed_size = struct.unpack_from("<I", header, 18)[0]
            uncompressed_size = struct.unpack_from("<I", header, 22)[0]
            name_size, extra_size = struct.unpack_from("<HH", header, 26)
            data_start = info.header_offset + 30 + name_size + extra_size
            data_end = data_start + info.compress_size
            if (
                flags != info.flag_bits
                or compression != info.compress_type
                or data_start > region_end
                or data_end > region_end
            ):
                raise ContractError(TRANSFER_ARCHIVE_BOUNDARY_INVALID)
            trailing_size = region_end - data_end
            if flags & 0x08:
                descriptor = stream.read_exact_at(
                    data_end,
                    trailing_size,
                    cap=24,
                    allowed_lengths={12, 16, 20, 24},
                )
                if trailing_size == 16 and descriptor[:4] == b"PK\x07\x08":
                    descriptor_crc, descriptor_compressed, descriptor_size = struct.unpack_from("<III", descriptor, 4)
                elif trailing_size == 12:
                    descriptor_crc, descriptor_compressed, descriptor_size = struct.unpack("<III", descriptor)
                elif trailing_size == 24 and descriptor[:4] == b"PK\x07\x08":
                    descriptor_crc, descriptor_compressed, descriptor_size = struct.unpack_from("<IQQ", descriptor, 4)
                elif trailing_size == 20:
                    descriptor_crc, descriptor_compressed, descriptor_size = struct.unpack("<IQQ", descriptor)
                else:
                    raise ContractError(TRANSFER_ARCHIVE_BOUNDARY_INVALID)
                if (
                    descriptor_crc != info.CRC
                    or descriptor_compressed != info.compress_size
                    or descriptor_size != info.file_size
                ):
                    raise ContractError(TRANSFER_ARCHIVE_BOUNDARY_INVALID)
            elif trailing_size != 0:
                raise ContractError(TRANSFER_ARCHIVE_BOUNDARY_INVALID)
            elif (
                crc != info.CRC
                or (compressed_size != 0xFFFFFFFF and compressed_size != info.compress_size)
                or (uncompressed_size != 0xFFFFFFFF and uncompressed_size != info.file_size)
            ):
                raise ContractError(TRANSFER_ARCHIVE_BOUNDARY_INVALID)
    except ContractError:
        raise
    except (OSError, KeyError, struct.error, TypeError, ValueError) as error:
        raise ContractError(TRANSFER_ARCHIVE_BOUNDARY_INVALID) from error


def open_archive(bundle_path: Path) -> BoundArchiveSession:
    try:
        return BoundArchiveSession(bundle_path)
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
        try:
            document_history_state(manifest.get("repository", {}))
        except ContractError as error:
            raise ContractError("invalid internal manifest") from error
        if (
            type(manifest.get("schemaVersion")) is not int
            or manifest.get("schemaVersion") != SCHEMA_VERSION
            or not is_sha256(manifest.get("inventoryDigest"))
            or not is_sha256(manifest.get("selectionDigest"))
            or not isinstance(manifest.get("repository"), dict)
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
        if has_reparse_ancestor(root, relative):
            mismatches += 1
            continue
        try:
            with BoundPayloadInputSession(source) as input_session:
                consume_payload(input_session, entry)
        except ContractError:
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
    payload, metadata = expected_material(repository, inventory, rows)
    if (
        manifest.get("inventoryDigest") != inventory["snapshot"]["digest"]
        or manifest.get("selectionDigest") != sha256_bytes(canonical_json(selection))
        or document_history_state(manifest["repository"]) != document_history_state(inventory["repository"])
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
    inventory.add_argument("--force", action="store_true")
    bundle_parser = commands.add_parser("bundle")
    bundle_parser.add_argument("--repo", type=Path, required=True)
    bundle_parser.add_argument("--git-executable", type=Path, required=True)
    bundle_parser.add_argument("--inventory", type=Path, required=True)
    bundle_parser.add_argument("--selection", type=Path, required=True)
    bundle_parser.add_argument("--output", type=Path, required=True)
    bundle_parser.add_argument("--force", action="store_true")
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--bundle", type=Path, required=True)
    verify_parser.add_argument("--git-executable", type=Path)
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
            output = bind_output(args.output, repository.root, force=args.force)
            inventory_bytes = capped_canonical_json(build_inventory(repository), "inventory output exceeds JSON limit", final_newline=True)
            publish_output_bytes(output, inventory_bytes)
        elif args.command == "bundle":
            bundle(
                bind_repository(args.repo, args.git_executable),
                args.inventory,
                args.selection,
                args.output,
                force=args.force,
            )
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
