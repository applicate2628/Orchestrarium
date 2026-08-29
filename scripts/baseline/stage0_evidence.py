#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import ctypes
import threading
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
        cleanup_error: VerificationError | None = None
        log, log_identity = _fresh_regular_file(log_path)
        with log:
            if tools is not None:
                tools.verify(command[0])
            try:
                process = subprocess.Popen(
                    list(command),
                    cwd=cwd,
                    env=dict(env),
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            except FileNotFoundError as exc:
                log.write(f"BLOCKED: command executable not found: {exc}\n".encode())
                log.flush()
                os.fsync(log.fileno())
                result = CommandResult(127, log_path, launch_error=str(exc))
            except OSError as exc:
                log.write(f"BLOCKED: command launch failed: {exc}\n".encode())
                log.flush()
                os.fsync(log.fileno())
                result = CommandResult(126, log_path, launch_error=str(exc))
            else:
                timed_out = False
                try:
                    try:
                        return_code = process.wait(timeout=timeout_seconds)
                    except subprocess.TimeoutExpired:
                        timed_out = True
                        return_code = 124
                        log.write(
                            f"BLOCKED: command timed out after {timeout_seconds:g}s\n".encode()
                        )
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
                        log.write(f"BLOCKED: {exc}\n".encode())
                log.flush()
                os.fsync(log.fileno())
                result = CommandResult(return_code, log_path, timed_out=timed_out)
        _verify_prepared_file(log_identity)
        if cleanup_error is not None:
            raise cleanup_error
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
