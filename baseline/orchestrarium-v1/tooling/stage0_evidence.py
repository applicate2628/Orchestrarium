#!/usr/bin/env python3
from __future__ import annotations

import contextlib
from collections.abc import Callable
import ctypes
import threading
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from types import MappingProxyType

from stage0_runtime import *

_PR_SET_CHILD_SUBREAPER = 36
_PR_GET_CHILD_SUBREAPER = 37
_SUBREAPER_ENABLED = False
_LANE_LOCK = threading.Lock()
_PROCESS_POLL_SECONDS = 0.05
_PROCESS_TERM_GRACE_SECONDS = 1.0
_PROCESS_CLEANUP_TIMEOUT_SECONDS = 5.0
_PROCESS_QUIET_POLLS = 8
_PROCESS_OUTPUT_LIMIT_BYTES = 16 * 1024 * 1024
_PROCESS_OUTPUT_READ_BYTES = 64 * 1024
_PROCESS_OUTPUT_JOIN_SECONDS = 2.0
ProcessRecord = tuple[int, str, int]


@dataclass(frozen=True)
class VerificationWorkspace:
    trusted_root: Path
    lane_root: Path


@dataclass(frozen=True)
class TrustedTreeEntry:
    kind: str
    device: int
    inode: int
    mode: int
    uid: int
    gid: int
    nlink: int | None = None
    size: int | None = None
    mtime_ns: int | None = None
    ctime_ns: int | None = None
    sha256: str | None = None


@dataclass(frozen=True)
class TrustedTreeSnapshot:
    root: Path
    excluded: frozenset[str]
    entries: Mapping[str, TrustedTreeEntry]


@dataclass(frozen=True)
class PreparedFileIdentity:
    path: Path
    device: int
    inode: int
    mode: int


@dataclass(frozen=True)
class RetainedTestFile:
    inventory_path: str
    filesystem_path: str
    content_sha256: str | None = None


@dataclass(frozen=True)
class ParentGeneratedPytestResult:
    exit_code: int
    junit_path: Path
    log_paths: tuple[Path, ...]
    timed_out: bool = False


def _remove_private_temp_root(path: Path) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        path.unlink(missing_ok=True)
        return
    shutil.rmtree(path)


def _private_temp_parent() -> Path:
    parent = Path("/tmp")
    try:
        metadata = parent.lstat()
    except OSError as exc:
        raise VerificationError(f"cannot inspect private temporary parent {parent}: {exc}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise VerificationError(f"private temporary parent must be a real directory: {parent}")
    return parent.resolve(strict=True)


@contextlib.contextmanager
def verification_workspace(*, preserve_failed: bool = False):
    private_parent = _private_temp_parent()
    trusted_root = Path(
        tempfile.mkdtemp(prefix="orche-stage0-trusted-", dir=private_parent)
    ).resolve()
    lane_root = Path(
        tempfile.mkdtemp(prefix="orche-stage0-lanes-", dir=private_parent)
    ).resolve()
    os.chmod(trusted_root, 0o700)
    os.chmod(lane_root, 0o700)
    workspace = VerificationWorkspace(trusted_root=trusted_root, lane_root=lane_root)
    try:
        yield workspace
    except BaseException:
        if preserve_failed:
            print(
                "RECOVERY: failed Stage 0 trusted state preserved at "
                f"{trusted_root}; lane state at {lane_root}",
                file=sys.stderr,
            )
        else:
            _remove_private_temp_root(trusted_root)
            _remove_private_temp_root(lane_root)
        raise
    else:
        _remove_private_temp_root(trusted_root)
        _remove_private_temp_root(lane_root)


def _enable_child_subreaper() -> None:
    global _SUBREAPER_ENABLED
    if _SUBREAPER_ENABLED:
        return
    if not sys.platform.startswith("linux"):
        raise VerificationError(
            "Stage 0 process containment requires Linux child-subreaper semantics"
        )
    if not Path("/proc/self/stat").is_file():
        raise VerificationError("Stage 0 process containment requires a mounted /proc")
    libc = ctypes.CDLL(None, use_errno=True)
    prctl = getattr(libc, "prctl", None)
    if prctl is None:
        raise VerificationError("Linux C library does not expose prctl")
    if prctl(_PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) != 0:
        error = ctypes.get_errno()
        raise VerificationError(
            f"cannot enable Linux child subreaper: {os.strerror(error)}"
        )
    state = ctypes.c_int()
    if prctl(_PR_GET_CHILD_SUBREAPER, ctypes.byref(state), 0, 0, 0) != 0:
        error = ctypes.get_errno()
        raise VerificationError(
            f"cannot verify Linux child subreaper: {os.strerror(error)}"
        )
    if state.value != 1:
        raise VerificationError("Linux child subreaper did not remain enabled")
    _proc_table()
    _SUBREAPER_ENABLED = True


def _proc_table() -> dict[int, ProcessRecord]:
    table: dict[int, ProcessRecord] = {}
    try:
        entries = list(Path("/proc").iterdir())
    except OSError as exc:
        raise VerificationError(f"cannot inspect Linux /proc: {exc}") from exc
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            raw = (entry / "stat").read_bytes()
        except OSError:
            continue
        closing = raw.rfind(b") ")
        if closing < 0:
            continue
        fields = raw[closing + 2 :].split()
        if len(fields) <= 19:
            continue
        try:
            state = fields[0].decode("ascii")
            parent_pid = int(fields[1])
            start_time = int(fields[19])
            pid = int(entry.name)
        except (UnicodeDecodeError, ValueError, IndexError):
            continue
        table[pid] = (parent_pid, state, start_time)
    if os.getpid() not in table:
        raise VerificationError("cannot locate verifier process in Linux /proc")
    return table


def _direct_child_snapshot(table: Mapping[int, ProcessRecord]) -> dict[int, int]:
    verifier_pid = os.getpid()
    return {
        pid: record[2]
        for pid, record in table.items()
        if record[0] == verifier_pid
    }


def _is_preexisting_child(
    pid: int, start_time: int, preexisting: Mapping[int, int]
) -> bool:
    return preexisting.get(pid) == start_time


def _lane_processes(
    table: Mapping[int, ProcessRecord], preexisting: Mapping[int, int]
) -> dict[int, ProcessRecord]:
    verifier_pid = os.getpid()
    children: dict[int, set[int]] = {}
    for pid, (parent_pid, _state, _start_time) in table.items():
        children.setdefault(parent_pid, set()).add(pid)
    roots = {
        pid
        for pid, (parent_pid, _state, start_time) in table.items()
        if parent_pid == verifier_pid
        and not _is_preexisting_child(pid, start_time, preexisting)
    }
    seen: set[int] = set()
    stack = list(roots)
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        stack.extend(children.get(pid, set()) - seen)
    return {pid: table[pid] for pid in seen if pid in table}


def _signal_lane_processes(
    records: Mapping[int, ProcessRecord], signal_number: signal.Signals
) -> None:
    current = _proc_table()
    for pid, (_parent_pid, _state, start_time) in records.items():
        now = current.get(pid)
        if now is None or now[2] != start_time or now[1] == "Z":
            continue
        try:
            os.kill(pid, signal_number)
        except ProcessLookupError:
            pass


def _reap_new_direct_children(preexisting: Mapping[int, int]) -> None:
    verifier_pid = os.getpid()
    table = _proc_table()
    for pid, (parent_pid, _state, start_time) in table.items():
        if parent_pid != verifier_pid or _is_preexisting_child(
            pid, start_time, preexisting
        ):
            continue
        try:
            os.waitpid(pid, os.WNOHANG)
        except (ChildProcessError, ProcessLookupError):
            pass


def _cleanup_lane_descendants(preexisting: Mapping[int, int]) -> None:
    term_deadline = time.monotonic() + _PROCESS_TERM_GRACE_SECONDS
    deadline = time.monotonic() + _PROCESS_CLEANUP_TIMEOUT_SECONDS
    quiet_polls = 0
    last_live: dict[int, ProcessRecord] = {}
    while time.monotonic() < deadline:
        _reap_new_direct_children(preexisting)
        table = _proc_table()
        records = _lane_processes(table, preexisting)
        live = {pid: record for pid, record in records.items() if record[1] != "Z"}
        if not live:
            quiet_polls += 1
            if quiet_polls >= _PROCESS_QUIET_POLLS:
                _reap_new_direct_children(preexisting)
                return
            time.sleep(_PROCESS_POLL_SECONDS)
            continue
        quiet_polls = 0
        last_live = live
        signal_number = (
            signal.SIGTERM
            if time.monotonic() < term_deadline
            else signal.SIGKILL
        )
        _signal_lane_processes(live, signal_number)
        time.sleep(_PROCESS_POLL_SECONDS)
    table = _proc_table()
    survivors = {
        pid: record
        for pid, record in _lane_processes(table, preexisting).items()
        if record[1] != "Z"
    }
    remaining = sorted(survivors or last_live)
    raise VerificationError(
        f"detached lane descendants survived containment cleanup: {remaining}"
    )


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, OSError):
        return
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        try:
            os.killpg(process.pid, 0)
        except (ProcessLookupError, OSError):
            return
        time.sleep(_PROCESS_POLL_SECONDS)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except OSError:
        pass


def _fresh_regular_file(path: Path) -> tuple[object, PreparedFileIdentity]:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise VerificationError(f"cannot create fresh trusted file {path}: {exc}") from exc
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        os.close(descriptor)
        raise VerificationError(f"fresh trusted file is not a private regular file: {path}")
    return os.fdopen(descriptor, "wb"), PreparedFileIdentity(
        path=path,
        device=metadata.st_dev,
        inode=metadata.st_ino,
        mode=metadata.st_mode,
    )


def _verify_prepared_file(identity: PreparedFileIdentity, *, require_nonempty: bool = False) -> None:
    try:
        metadata = identity.path.lstat()
    except OSError as exc:
        raise VerificationError(f"trusted output disappeared: {identity.path}: {exc}") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or metadata.st_dev != identity.device
        or metadata.st_ino != identity.inode
        or stat.S_IFMT(metadata.st_mode) != stat.S_IFMT(identity.mode)
    ):
        raise VerificationError(f"trusted output path was replaced or linked: {identity.path}")
    if require_nonempty and metadata.st_size == 0:
        raise VerificationError(f"trusted output is empty: {identity.path}")


def prepare_trusted_output(path: Path) -> PreparedFileIdentity:
    handle, identity = _fresh_regular_file(path)
    handle.close()
    return identity


def _drain_process_output(
    stream,
    captured: bytearray,
    state: dict[str, object],
) -> None:
    try:
        while True:
            chunk = stream.read(_PROCESS_OUTPUT_READ_BYTES)
            if not chunk:
                return
            remaining = max(0, _PROCESS_OUTPUT_LIMIT_BYTES - len(captured))
            if remaining:
                captured.extend(chunk[:remaining])
            if len(chunk) > remaining:
                state["overflow"] = True
    except BaseException as exc:
        state["error"] = exc
    finally:
        try:
            stream.close()
        except BaseException as exc:
            state.setdefault("error", exc)


def _write_parent_captured_log(path: Path, payload: bytes) -> None:
    handle, identity = _fresh_regular_file(path)
    with handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    _verify_prepared_file(identity)


def run_isolated(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    log_path: Path,
    timeout_seconds: float,
    tools: ExternalTools | None,
) -> CommandResult:
    if timeout_seconds <= 0:
        raise VerificationError("timeout must be positive")
    if not _LANE_LOCK.acquire(blocking=False):
        raise VerificationError("concurrent Stage 0 lane execution is unsupported")
    try:
        _enable_child_subreaper()
        preexisting = _direct_child_snapshot(_proc_table())
        captured = bytearray()
        capture_state: dict[str, object] = {}
        parent_diagnostics: list[bytes] = []
        cleanup_error: VerificationError | None = None
        if tools is not None:
            tools.verify(command[0])
        try:
            process = subprocess.Popen(
                list(command),
                cwd=cwd,
                env=dict(env),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
        except FileNotFoundError as exc:
            parent_diagnostics.append(
                f"BLOCKED: command executable not found: {exc}\n".encode()
            )
            result = CommandResult(127, log_path, launch_error=str(exc))
        except OSError as exc:
            parent_diagnostics.append(
                f"BLOCKED: command launch failed: {exc}\n".encode()
            )
            result = CommandResult(126, log_path, launch_error=str(exc))
        else:
            if process.stdout is None:
                _terminate_process_group(process)
                _cleanup_lane_descendants(preexisting)
                raise VerificationError("repository process stdout pipe was not created")
            reader = threading.Thread(
                target=_drain_process_output,
                args=(process.stdout, captured, capture_state),
                name=f"orche-stage0-output-{process.pid}",
            )
            try:
                reader.start()
            except BaseException as exc:
                _terminate_process_group(process)
                if process.poll() is None:
                    process.kill()
                    process.wait()
                _cleanup_lane_descendants(preexisting)
                raise VerificationError(
                    f"cannot start repository output capture: {exc}"
                ) from exc
            timed_out = False
            try:
                try:
                    return_code = process.wait(timeout=timeout_seconds)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    return_code = 124
            finally:
                _terminate_process_group(process)
                if process.poll() is None:
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                try:
                    _cleanup_lane_descendants(preexisting)
                except VerificationError as exc:
                    cleanup_error = exc
            reader.join(timeout=_PROCESS_OUTPUT_JOIN_SECONDS)
            if reader.is_alive():
                try:
                    process.stdout.close()
                except OSError:
                    pass
                reader.join(timeout=_PROCESS_OUTPUT_JOIN_SECONDS)
            if reader.is_alive():
                capture_state["error"] = VerificationError(
                    "repository output capture did not reach end-of-file after descendant cleanup"
                )
            if timed_out:
                parent_diagnostics.append(
                    f"BLOCKED: command timed out after {timeout_seconds:g}s\n".encode()
                )
            result = CommandResult(return_code, log_path, timed_out=timed_out)

        if cleanup_error is not None:
            raise cleanup_error
        capture_error = capture_state.get("error")
        if capture_error is not None:
            if isinstance(capture_error, BaseException):
                raise VerificationError(
                    f"cannot capture repository process output: {capture_error}"
                ) from capture_error
            raise VerificationError(
                f"cannot capture repository process output: {capture_error!r}"
            )
        if capture_state.get("overflow"):
            parent_diagnostics.append(
                "BLOCKED: command output exceeded trusted capture limit of "
                f"{_PROCESS_OUTPUT_LIMIT_BYTES} bytes\n".encode()
            )
        payload = bytes(captured) + b"".join(parent_diagnostics)
        _write_parent_captured_log(log_path, payload)
        if capture_state.get("overflow"):
            raise VerificationError(
                "repository process output exceeded the trusted capture limit"
            )
        return result
    finally:
        _LANE_LOCK.release()


def _lexical_relative(root: Path, path: Path) -> str:
    absolute = Path(os.path.abspath(os.fspath(path)))
    try:
        relative = absolute.relative_to(root)
    except ValueError as exc:
        raise VerificationError(f"trusted-tree exclusion escapes root: {path}") from exc
    if not relative.parts:
        raise VerificationError("trusted-tree root itself cannot be excluded")
    return relative.as_posix()


def _hash_regular_no_follow(path: Path, metadata: os.stat_result) -> str:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise VerificationError(f"cannot open trusted regular file {path}: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        digest = hashlib.sha256()
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            digest.update(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    stable = lambda st: (
        st.st_dev,
        st.st_ino,
        st.st_mode,
        st.st_uid,
        st.st_gid,
        st.st_nlink,
        st.st_size,
        st.st_mtime_ns,
        st.st_ctime_ns,
    )
    if stable(metadata) != stable(before) or stable(before) != stable(after):
        raise VerificationError(f"trusted regular file changed while hashing: {path}")
    return digest.hexdigest()


def _scan_trusted_tree(root: Path, excluded: frozenset[str]) -> dict[str, TrustedTreeEntry]:
    try:
        root_metadata = root.lstat()
    except OSError as exc:
        raise VerificationError(f"cannot inspect trusted root {root}: {exc}") from exc
    if stat.S_ISLNK(root_metadata.st_mode) or not stat.S_ISDIR(root_metadata.st_mode):
        raise VerificationError(f"trusted root is not a real directory: {root}")
    entries: dict[str, TrustedTreeEntry] = {
        ".": TrustedTreeEntry(
            kind="directory",
            device=root_metadata.st_dev,
            inode=root_metadata.st_ino,
            mode=root_metadata.st_mode,
            uid=root_metadata.st_uid,
            gid=root_metadata.st_gid,
        )
    }

    def visit(directory: Path) -> None:
        try:
            with os.scandir(directory) as iterator:
                children = sorted(iterator, key=lambda item: item.name)
        except OSError as exc:
            raise VerificationError(f"cannot scan trusted directory {directory}: {exc}") from exc
        for child in children:
            path = Path(child.path)
            relative = path.relative_to(root).as_posix()
            if relative in excluded:
                continue
            try:
                metadata = child.stat(follow_symlinks=False)
            except OSError as exc:
                raise VerificationError(f"cannot inspect trusted entry {path}: {exc}") from exc
            if stat.S_ISLNK(metadata.st_mode):
                raise VerificationError(f"symlink is forbidden in trusted tree: {path}")
            if stat.S_ISDIR(metadata.st_mode):
                entries[relative] = TrustedTreeEntry(
                    kind="directory",
                    device=metadata.st_dev,
                    inode=metadata.st_ino,
                    mode=metadata.st_mode,
                    uid=metadata.st_uid,
                    gid=metadata.st_gid,
                )
                visit(path)
            elif stat.S_ISREG(metadata.st_mode):
                if metadata.st_nlink != 1:
                    raise VerificationError(f"hard-linked file is forbidden in trusted tree: {path}")
                entries[relative] = TrustedTreeEntry(
                    kind="file",
                    device=metadata.st_dev,
                    inode=metadata.st_ino,
                    mode=metadata.st_mode,
                    uid=metadata.st_uid,
                    gid=metadata.st_gid,
                    nlink=metadata.st_nlink,
                    size=metadata.st_size,
                    mtime_ns=metadata.st_mtime_ns,
                    ctime_ns=metadata.st_ctime_ns,
                    sha256=_hash_regular_no_follow(path, metadata),
                )
            else:
                raise VerificationError(f"unsupported entry type in trusted tree: {path}")

    visit(root)
    return entries


def _trusted_evidence_snapshot(
    trusted_root: Path, *, exclude: Iterable[Path] = ()
) -> TrustedTreeSnapshot:
    root = trusted_root.resolve(strict=True)
    excluded = frozenset(_lexical_relative(root, path) for path in exclude)
    return TrustedTreeSnapshot(
        root=root,
        excluded=excluded,
        entries=MappingProxyType(_scan_trusted_tree(root, excluded)),
    )


def _verify_protected_digests(expected: TrustedTreeSnapshot) -> None:
    actual = _scan_trusted_tree(expected.root, expected.excluded)
    before = dict(expected.entries)
    if actual == before:
        return
    before_keys = set(before)
    actual_keys = set(actual)
    added = sorted(actual_keys - before_keys)
    removed = sorted(before_keys - actual_keys)
    changed = sorted(
        path for path in before_keys & actual_keys if before[path] != actual[path]
    )
    raise VerificationError(
        "untrusted lane changed trusted-tree membership or identity: "
        f"added={added}, removed={removed}, changed={changed}"
    )


def run_repository_lane(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    log_path: Path,
    timeout_seconds: float,
    tools: ExternalTools,
    trusted_root: Path,
    mutable_paths: Iterable[Path] = (),
) -> CommandResult:
    allowed = tuple({log_path, *mutable_paths})
    snapshot = _trusted_evidence_snapshot(trusted_root, exclude=allowed)
    result = run_isolated(
        command,
        cwd=cwd,
        env=env,
        log_path=log_path,
        timeout_seconds=timeout_seconds,
        tools=tools,
    )
    tools.verify_all()
    for path in allowed:
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise VerificationError(f"mutable trusted output is not a private regular file: {path}")
    _verify_protected_digests(snapshot)
    return result


def _decode_inventory_git_path(encoded_path: str) -> bytes:
    output = bytearray()
    index = 0
    safe = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._/")
    while index < len(encoded_path):
        character = encoded_path[index]
        if character == "%":
            token = encoded_path[index + 1 : index + 3]
            if len(token) != 2 or not re.fullmatch(r"[0-9A-F]{2}", token):
                raise VerificationError(f"invalid inventory Git path: {encoded_path!r}")
            output.append(int(token, 16))
            index += 3
            continue
        value = ord(character)
        if value not in safe:
            raise VerificationError(f"non-canonical inventory Git path: {encoded_path!r}")
        output.append(value)
        index += 1
    return bytes(output)


def _load_test_inventory_entries(path: Path, *, label: str) -> dict[str, dict[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read {label} test inventory {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schemaVersion") != 2:
        raise VerificationError(f"invalid {label} test inventory schema")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise VerificationError(f"invalid {label} test inventory entries")
    result: dict[str, dict[str, object]] = {}
    for raw in entries:
        if not isinstance(raw, dict):
            raise VerificationError(f"invalid {label} test inventory entry")
        inventory_path = raw.get("path")
        if not isinstance(inventory_path, str) or not inventory_path.startswith("tests/"):
            raise VerificationError(f"invalid {label} test path: {inventory_path!r}")
        if raw.get("pathEncoding") != "git-path-percent-v1":
            raise VerificationError(
                f"invalid {label} test path encoding for {inventory_path!r}"
            )
        digest = raw.get("contentSha256")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise VerificationError(f"invalid {label} test digest for {inventory_path!r}")
        if raw.get("kind") not in {"test-file", "test-support"}:
            raise VerificationError(f"invalid {label} test kind for {inventory_path!r}")
        if inventory_path in result:
            raise VerificationError(f"duplicate {label} test path: {inventory_path}")
        result[inventory_path] = raw
    return result


def load_retained_test_files(
    baseline_inventory: Path, candidate_inventory: Path
) -> tuple[RetainedTestFile, ...]:
    baseline = _load_test_inventory_entries(baseline_inventory, label="baseline")
    candidate = _load_test_inventory_entries(candidate_inventory, label="candidate")
    missing = sorted(set(baseline) - set(candidate))
    changed = sorted(
        path
        for path in set(baseline) & set(candidate)
        if baseline[path].get("contentSha256") != candidate[path].get("contentSha256")
        or baseline[path].get("kind") != candidate[path].get("kind")
    )
    if missing or changed:
        raise VerificationBlocked(
            "baseline test sources are not retained exactly: "
            f"missing={missing}, changed={changed}"
        )
    retained: list[RetainedTestFile] = []
    for inventory_path in sorted(baseline):
        if baseline[inventory_path].get("kind") != "test-file":
            continue
        raw_path = _decode_inventory_git_path(inventory_path)
        parts = raw_path.split(b"/")
        if (
            not raw_path.startswith(b"tests/")
            or b"\x00" in raw_path
            or any(part in {b"", b".", b".."} for part in parts)
        ):
            raise VerificationError(f"unsafe retained test path: {inventory_path!r}")
        retained.append(
            RetainedTestFile(
                inventory_path=inventory_path,
                filesystem_path=os.fsdecode(raw_path),
                content_sha256=str(baseline[inventory_path]["contentSha256"]),
            )
        )
    if not retained:
        raise VerificationError("baseline test inventory contains no test files")
    return tuple(retained)


def _verify_retained_test_source(source: Path, test_file: RetainedTestFile) -> None:
    try:
        metadata = source.lstat()
    except OSError as exc:
        raise VerificationError(f"cannot inspect retained test file {source}: {exc}") from exc
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
    ):
        raise VerificationError(f"retained test path is not a private regular file: {source}")
    if test_file.content_sha256 is not None:
        digest = _hash_regular_no_follow(source, metadata)
        if digest != test_file.content_sha256:
            raise VerificationBlocked(
                "retained test source changed before or during execution: "
                f"{test_file.inventory_path}; expected={test_file.content_sha256}, actual={digest}"
            )


def _xml_safe_text(value: str) -> str:
    return "".join(
        character
        if character in {"\t", "\n", "\r"}
        or " " <= character <= "\ud7ff"
        or "\ue000" <= character <= "\ufffd"
        else "\ufffd"
        for character in value
    )


def _diagnostic_from_log(path: Path, *, limit: int = 131072) -> str:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise VerificationError(f"cannot read Pytest file log {path}: {exc}") from exc
    digest = hashlib.sha256(raw).hexdigest()
    if len(raw) > limit:
        raw = raw[-limit:]
        prefix = f"[log truncated to final {limit} bytes; sha256={digest}]\n"
    else:
        prefix = f"[log sha256={digest}]\n"
    return _xml_safe_text(prefix + raw.decode("utf-8", errors="replace"))



_PYTEST_OUTCOME_PROPERTY = "orche.pytest.outcomes.v1"
_PYTEST_OUTCOME_KEYS = ("passed", "skipped", "xfailed", "xpassed", "deselected")
_PYTEST_DIAGNOSTIC_PREFIXES = {
    "passed": "PASSED ",
    "skipped": "SKIPPED ",
    "xfailed": "XFAIL ",
    "xpassed": "XPASS ",
}
_PYTEST_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_PYTEST_TERMINAL_COUNT = re.compile(
    r"(?P<count>\d+)\s+"
    r"(?P<outcome>passed|failed|skipped|errors?|xfailed|xpassed|deselected|warnings?)\b"
)
_PYTEST_TERMINAL_DURATION = re.compile(
    r"\bin\s+\d+(?:\.\d+)?s\b"
)
_PYTEST_SKIP_DIAGNOSTIC = re.compile(
    r"^SKIPPED(?:\s+\[(?P<count>\d+)\])?\s+"
)


def _canonical_pytest_outcome_evidence(evidence: Mapping[str, object]) -> str:
    return json.dumps(
        evidence,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _pytest_skip_diagnostic_count(line: str) -> int:
    match = _PYTEST_SKIP_DIAGNOSTIC.match(line)
    if match is None:
        raise VerificationError(
            f"cannot parse Pytest skip diagnostic multiplicity: {line!r}"
        )
    count = match.group("count")
    return 1 if count is None else int(count)


def _pytest_zero_exit_outcome_evidence(path: Path) -> dict[str, object]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise VerificationError(f"cannot read Pytest file log {path}: {exc}") from exc
    text = _PYTEST_ANSI_ESCAPE.sub(
        "", raw.decode("utf-8", errors="replace")
    ).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    summaries: list[list[re.Match[str]]] = []
    for line in lines:
        if _PYTEST_TERMINAL_DURATION.search(line) is None:
            continue
        matches = list(_PYTEST_TERMINAL_COUNT.finditer(line))
        if matches:
            summaries.append(matches)
    if len(summaries) != 1:
        raise VerificationError(
            "zero-exit Pytest file log must contain exactly one terminal summary: "
            f"{path}; found={len(summaries)}"
        )
    parsed_counts: dict[str, int] = {}
    for match in summaries[0]:
        outcome = match.group("outcome")
        if outcome in {"error", "errors"}:
            outcome = "errors"
        elif outcome in {"warning", "warnings"}:
            outcome = "warnings"
        parsed_counts[outcome] = (
            parsed_counts.get(outcome, 0) + int(match.group("count"))
        )
    if parsed_counts.get("failed", 0) or parsed_counts.get("errors", 0):
        raise VerificationError(
            f"zero-exit Pytest file log reports failures or errors: {path}"
        )
    counts = {
        outcome: parsed_counts.get(outcome, 0)
        for outcome in _PYTEST_OUTCOME_KEYS
    }
    observed = sum(
        counts[outcome]
        for outcome in ("passed", "skipped", "xfailed", "xpassed")
    )
    if observed == 0:
        raise VerificationError(
            f"zero-exit Pytest file log reports no executed or skipped tests: {path}"
        )

    diagnostics: dict[str, list[str]] = {}
    for outcome, prefix in _PYTEST_DIAGNOSTIC_PREFIXES.items():
        outcome_lines = [
            _xml_safe_text(line.strip())
            for line in lines
            if line.lstrip().startswith(prefix)
        ]
        expected = counts[outcome]
        actual = (
            sum(_pytest_skip_diagnostic_count(line) for line in outcome_lines)
            if outcome == "skipped"
            else len(outcome_lines)
        )
        if actual != expected:
            raise VerificationError(
                "Pytest terminal outcome diagnostics do not match the summary: "
                f"{path}; outcome={outcome}, expected={expected}, actual={actual}"
            )
        diagnostics[outcome] = outcome_lines
    deselected = counts["deselected"]
    diagnostics["deselected"] = (
        [] if deselected == 0 else [f"{deselected} deselected"]
    )
    return {
        "schemaVersion": 1,
        "counts": counts,
        "diagnostics": diagnostics,
    }


def _write_parent_junit(
    *,
    junit_dir: Path,
    suite_name: str,
    cases: Sequence[tuple[RetainedTestFile, CommandResult]],
) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", suite_name):
        raise VerificationError(f"invalid Pytest suite name: {suite_name!r}")
    zero_exit_outcomes = {
        test_file.inventory_path: _pytest_zero_exit_outcome_evidence(result.log_path)
        for test_file, result in cases
        if result.exit_code == 0
    }
    failures = sum(result.exit_code == 1 for _test, result in cases)
    errors = sum(result.exit_code not in {0, 1} for _test, result in cases)
    skipped = sum(
        int(evidence["counts"]["skipped"]) > 0
        for evidence in zero_exit_outcomes.values()
    )
    suite = ET.Element(
        "testsuite",
        {
            "name": suite_name,
            "tests": str(len(cases)),
            "failures": str(failures),
            "errors": str(errors),
            "skipped": str(skipped),
        },
    )
    for test_file, result in cases:
        testcase = ET.SubElement(
            suite,
            "testcase",
            {
                "classname": "pytest.file",
                "name": test_file.inventory_path,
                "file": test_file.inventory_path,
            },
        )
        if result.exit_code == 1:
            failure = ET.SubElement(
                testcase,
                "failure",
                {
                    "type": "pytest.file.failure",
                    "message": "one or more tests in the file failed",
                },
            )
            failure.text = _diagnostic_from_log(result.log_path)
        elif result.exit_code != 0:
            error = ET.SubElement(
                testcase,
                "error",
                {
                    "type": "pytest.file.operational",
                    "message": f"Pytest file lane exited {result.exit_code}",
                },
            )
            error.text = _diagnostic_from_log(result.log_path)
        else:
            evidence = zero_exit_outcomes[test_file.inventory_path]
            properties = ET.SubElement(testcase, "properties")
            ET.SubElement(
                properties,
                "property",
                {
                    "name": _PYTEST_OUTCOME_PROPERTY,
                    "value": _canonical_pytest_outcome_evidence(evidence),
                },
            )
            counts = evidence["counts"]
            diagnostics = evidence["diagnostics"]
            skipped_count = int(counts["skipped"])
            if skipped_count:
                skipped_case = ET.SubElement(
                    testcase,
                    "skipped",
                    {
                        "type": "pytest.file.skipped",
                        "message": (
                            f"{skipped_count} skipped test(s) in retained file"
                        ),
                    },
                )
                skipped_case.text = "\n".join(diagnostics["skipped"])
    payload = ET.tostring(suite, encoding="utf-8", xml_declaration=True)
    junit_dir.mkdir(parents=True, exist_ok=True)
    path = junit_dir / f"{suite_name}-{uuid.uuid4().hex}.xml"
    handle, identity = _fresh_regular_file(path)
    with handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    _verify_prepared_file(identity, require_nonempty=True)
    return path


def run_parent_generated_pytest_lane(
    *,
    repo_root: Path,
    test_paths: Sequence[str] | Sequence[RetainedTestFile],
    lane_parent: Path,
    log_dir: Path,
    junit_dir: Path,
    suite_name: str,
    timeout_seconds: float,
    tools: ExternalTools,
    trusted_root: Path,
    revalidate_worktrees: Callable[[], None],
) -> ParentGeneratedPytestResult:
    repo_root = repo_root.resolve(strict=True)
    lane_parent.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    junit_dir.mkdir(parents=True, exist_ok=True)
    retained = tuple(
        item
        if isinstance(item, RetainedTestFile)
        else RetainedTestFile(inventory_path=item, filesystem_path=item)
        for item in test_paths
    )
    if not retained:
        raise VerificationError("Pytest evidence lane requires at least one test file")
    cases: list[tuple[RetainedTestFile, CommandResult]] = []
    log_paths: list[Path] = []
    for index, test_file in enumerate(retained):
        relative = Path(test_file.filesystem_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise VerificationError(f"unsafe Pytest file path: {test_file.inventory_path!r}")
        source = repo_root / relative
        _verify_retained_test_source(source, test_file)
        case_root = Path(
            tempfile.mkdtemp(prefix=f"{suite_name}-{index:04d}-", dir=lane_parent)
        )
        os.chmod(case_root, 0o700)
        log_name = hashlib.sha256(test_file.inventory_path.encode("ascii")).hexdigest()[:16]
        log_path = log_dir / f"{suite_name}-{index:04d}-{log_name}.log"
        try:
            result = run_repository_lane(
                [
                    os.fspath(tools.python),
                    "-m",
                    "pytest",
                    "--noconftest",
                    "-p",
                    "no:cacheprovider",
                    "-r",
                    "A",
                    "--tb=long",
                    os.fspath(relative),
                ],
                cwd=repo_root,
                env=build_repository_env(
                    tools=tools,
                    lane_root=case_root,
                    repo_root=repo_root,
                ),
                log_path=log_path,
                timeout_seconds=timeout_seconds,
                tools=tools,
                trusted_root=trusted_root,
            )
        finally:
            _remove_private_temp_root(case_root)
        _verify_retained_test_source(source, test_file)
        revalidate_worktrees()
        cases.append((test_file, result))
        log_paths.append(log_path)
    operational = next(
        (result.exit_code for _test, result in cases if result.exit_code not in {0, 1}),
        None,
    )
    exit_code = operational if operational is not None else int(
        any(result.exit_code == 1 for _test, result in cases)
    )
    junit_path = _write_parent_junit(
        junit_dir=junit_dir,
        suite_name=suite_name,
        cases=cases,
    )
    return ParentGeneratedPytestResult(
        exit_code=exit_code,
        junit_path=junit_path,
        log_paths=tuple(log_paths),
        timed_out=any(result.timed_out for _test, result in cases),
    )


def _safe_component(path: Path) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        path.mkdir(mode=0o700)
        return
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise VerificationError(f"unsafe output path component: {path}")


def safe_create_output_directory(candidate_root: Path, reviewed_ref: str) -> Path:
    candidate_root = candidate_root.resolve(strict=True)
    current = candidate_root
    for component in (".scratch", "orche-stage0", "reviewed-runs"):
        current = current / component
        _safe_component(current)
        resolved = current.resolve(strict=True)
        if not _inside(resolved, candidate_root):
            raise VerificationError(f"output component escapes candidate worktree: {current}")
    run_name = f"{reviewed_ref[:12]}-{uuid.uuid4().hex}"
    if not re.fullmatch(r"[0-9a-f]{12}-[0-9a-f]{32}", run_name):
        raise VerificationError("invalid generated output run name")
    output = current / run_name
    output.mkdir(mode=0o700)
    if not _inside(output.resolve(strict=True), candidate_root):
        raise VerificationError(f"output directory escapes candidate worktree: {output}")
    return output


def _git_show_bytes(
    tools: ExternalTools, env: Mapping[str, str], repo: Path, ref: str, path: str
) -> bytes:
    return bytes(_run_git(tools, env, repo, "show", f"{ref}:{path}", text=False))


def load_pin_from_commit(
    tools: ExternalTools,
    env: Mapping[str, str],
    candidate_root: Path,
    reviewed_ref: str,
) -> dict[str, object]:
    try:
        payload = json.loads(
            _git_show_bytes(tools, env, candidate_root, reviewed_ref, PIN_PATH).decode("utf-8")
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot parse reviewed baseline pin: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schemaVersion") != 6:
        raise VerificationError("reviewed baseline pin must be schemaVersion 6")
    baseline = payload.get("baseline")
    tooling = payload.get("tooling")
    if not isinstance(baseline, dict) or not isinstance(tooling, dict):
        raise VerificationError("reviewed baseline pin lacks baseline or tooling")
    for name in (
        "inventoryGenerator",
        "targetEffectGenerator",
        "pytestComparator",
        "commandComparator",
        "capabilityComparator",
        "stage0Runtime",
        "stage0Evidence",
        "stage0Orchestrator",
        "stage0Verifier",
    ):
        record = tooling.get(name)
        if not isinstance(record, dict):
            raise VerificationError(f"reviewed baseline pin lacks tooling.{name}")
        if not isinstance(record.get("path"), str):
            raise VerificationError(f"tooling.{name}.path is invalid")
        blob = record.get("gitBlobSha")
        if not isinstance(blob, str) or not OBJECT_ID.fullmatch(blob):
            raise VerificationError(f"tooling.{name}.gitBlobSha is invalid")
    return payload


def materialize_tool(
    name: str,
    *,
    pin: Mapping[str, object],
    tools: ExternalTools,
    env: Mapping[str, str],
    candidate_root: Path,
    reviewed_ref: str,
    trusted_tool_root: Path,
    sequence: int,
) -> tuple[Path, Mapping[str, object]]:
    tooling = pin["tooling"]
    assert isinstance(tooling, dict)
    record = tooling[name]
    assert isinstance(record, dict)
    path_value = record["path"]
    blob = str(record["gitBlobSha"]).lower()
    assert isinstance(path_value, str)
    tree_line = str(
        _run_git(tools, env, candidate_root, "ls-tree", reviewed_ref, "--", path_value)
    ).strip()
    parts = tree_line.split(None, 3)
    if len(parts) != 4 or parts[1] != "blob" or parts[2].lower() != blob:
        raise VerificationError(
            f"reviewed tree blob mismatch for {name}: expected={blob}, tree={tree_line!r}"
        )
    content = bytes(
        _run_git(tools, env, candidate_root, "cat-file", "blob", blob, text=False)
    )
    trusted_tool_root.mkdir(parents=True, exist_ok=True)
    destination = trusted_tool_root / f"{sequence:04d}-{name}.py"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=trusted_tool_root
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o500)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    actual_blob = (
        bytes(
            _run_git(
                tools,
                env,
                candidate_root,
                "hash-object",
                "--stdin",
                text=False,
                input_data=content,
            )
        )
        .decode("ascii")
        .strip()
        .lower()
    )
    if actual_blob != blob:
        raise VerificationError(
            f"materialized tool hash mismatch for {name}: expected={blob}, actual={actual_blob}"
        )
    return destination, record


def _invoke_frozen(
    name: str,
    arguments: Sequence[str],
    *,
    state: dict[str, int],
    pin: Mapping[str, object],
    tools: ExternalTools,
    env: Mapping[str, str],
    candidate_root: Path,
    reviewed_ref: str,
    trusted_root: Path,
    cwd: Path,
    log_path: Path,
    timeout_seconds: float,
) -> tuple[CommandResult, Mapping[str, object]]:
    state["sequence"] += 1
    script, record = materialize_tool(
        name,
        pin=pin,
        tools=tools,
        env=env,
        candidate_root=candidate_root,
        reviewed_ref=reviewed_ref,
        trusted_tool_root=trusted_root / "tools",
        sequence=state["sequence"],
    )
    expected_script_sha256 = sha256_file(script)
    result = run_isolated(
        [os.fspath(tools.python), "-I", os.fspath(script), *arguments],
        cwd=cwd,
        env=env,
        log_path=log_path,
        timeout_seconds=timeout_seconds,
        tools=tools,
    )
    if not script.is_file() or sha256_file(script) != expected_script_sha256:
        raise VerificationError(f"materialized tool changed during execution: {script}")
    return result, record


def _log_excerpt(path: Path, limit: int = 4000) -> str:
    try:
        text = path.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return ""
    return text[-limit:].strip()


def _require_result(
    result: CommandResult, *, label: str, semantic: bool = False
) -> None:
    if result.exit_code == 0:
        return
    excerpt = _log_excerpt(result.log_path)
    suffix = f"\n{excerpt}" if excerpt else ""
    if semantic and result.exit_code == 1:
        raise VerificationBlocked(f"{label} blocked by semantic evidence{suffix}")
    raise VerificationError(
        f"{label} failed operationally with exit {result.exit_code}{suffix}"
    )


def _validator_command(spec: ValidatorSpec, tools: ExternalTools) -> list[str]:
    executable = tools.python if spec.kind == "python" else tools.bash
    return [os.fspath(executable), *spec.arguments]


def _write_summary(
    trusted_root: Path,
    *,
    status: str,
    baseline_ref: str,
    candidate_ref: str,
    message: str,
) -> Path:
    path = trusted_root / "summary.json"
    path.write_text(
        _canonical_json(
            {
                "schemaVersion": 1,
                "status": status,
                "baselineRef": baseline_ref,
                "candidateRef": candidate_ref,
                "message": message,
                "trustedEvidenceLifecycle": "removed-after-copy",
            }
        ),
        encoding="utf-8",
    )
    return path


def _copy_reports(trusted_root: Path, output: Path) -> None:
    snapshot = _trusted_evidence_snapshot(trusted_root)
    allowed_prefixes = ("evidence/", "reports/", "logs/")
    allowed_exact = {"summary.json", "reviewed-dispositions.json"}
    for relative, entry in sorted(snapshot.entries.items()):
        if relative == "." or entry.kind != "file":
            continue
        if relative not in allowed_exact and not relative.startswith(allowed_prefixes):
            continue
        source = trusted_root / relative
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination, follow_symlinks=False)


__all__ = [name for name in globals() if not name.startswith("__")]
