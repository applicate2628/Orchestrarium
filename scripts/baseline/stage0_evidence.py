#!/usr/bin/env python3
from stage0_runtime import *
def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except OSError:
        return
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            return
        except OSError:
            return
        time.sleep(0.05)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except OSError:
        pass

def run_isolated(command: Sequence[str], *, cwd: Path, env: Mapping[str, str], log_path: Path, timeout_seconds: float) -> CommandResult:
    if timeout_seconds <= 0:
        raise VerificationError('timeout must be positive')
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open('wb') as log:
        try:
            process = subprocess.Popen(list(command), cwd=cwd, env=dict(env), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        except FileNotFoundError as exc:
            log.write(f'BLOCKED: command executable not found: {exc}\n'.encode())
            return CommandResult(127, log_path, launch_error=str(exc))
        except OSError as exc:
            log.write(f'BLOCKED: command launch failed: {exc}\n'.encode())
            return CommandResult(126, log_path, launch_error=str(exc))
        timed_out = False
        try:
            return_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            return_code = 124
            log.write(f'BLOCKED: command timed out after {timeout_seconds:g}s\n'.encode())
        finally:
            _terminate_process_group(process)
            if process.poll() is None:
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        log.flush()
        os.fsync(log.fileno())
    return CommandResult(return_code, log_path, timed_out=timed_out)

def _safe_component(path: Path) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        path.mkdir(mode=448)
        return
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise VerificationError(f'unsafe output path component: {path}')

def safe_create_output_directory(candidate_root: Path, reviewed_ref: str) -> Path:
    candidate_root = candidate_root.resolve(strict=True)
    current = candidate_root
    for component in ('.scratch', 'orche-stage0', 'reviewed-runs'):
        current = current / component
        _safe_component(current)
        resolved = current.resolve(strict=True)
        if not _inside(resolved, candidate_root):
            raise VerificationError(f'output component escapes candidate worktree: {current}')
    run_name = f'{reviewed_ref[:12]}-{uuid.uuid4().hex}'
    if not re.fullmatch('[0-9a-f]{12}-[0-9a-f]{32}', run_name):
        raise VerificationError('invalid generated output run name')
    output = current / run_name
    output.mkdir(mode=448)
    if not _inside(output.resolve(strict=True), candidate_root):
        raise VerificationError(f'output directory escapes candidate worktree: {output}')
    return output

def _git_show_bytes(tools: ExternalTools, env: Mapping[str, str], repo: Path, ref: str, path: str) -> bytes:
    return bytes(_run_git(tools, env, repo, 'show', f'{ref}:{path}', text=False))

def load_pin_from_commit(tools: ExternalTools, env: Mapping[str, str], candidate_root: Path, reviewed_ref: str) -> dict[str, object]:
    try:
        payload = json.loads(_git_show_bytes(tools, env, candidate_root, reviewed_ref, PIN_PATH).decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f'cannot parse reviewed baseline pin: {exc}') from exc
    if not isinstance(payload, dict) or payload.get('schemaVersion') != 6:
        raise VerificationError('reviewed baseline pin must be schemaVersion 6')
    baseline = payload.get('baseline')
    tooling = payload.get('tooling')
    if not isinstance(baseline, dict) or not isinstance(tooling, dict):
        raise VerificationError('reviewed baseline pin lacks baseline or tooling')
    for name in ('inventoryGenerator', 'targetEffectGenerator', 'pytestComparator', 'commandComparator', 'capabilityComparator', 'stage0Runtime', 'stage0Evidence', 'stage0Orchestrator', 'stage0Verifier'):
        record = tooling.get(name)
        if not isinstance(record, dict):
            raise VerificationError(f'reviewed baseline pin lacks tooling.{name}')
        if not isinstance(record.get('path'), str):
            raise VerificationError(f'tooling.{name}.path is invalid')
        blob = record.get('gitBlobSha')
        if not isinstance(blob, str) or not OBJECT_ID.fullmatch(blob):
            raise VerificationError(f'tooling.{name}.gitBlobSha is invalid')
    return payload

def materialize_tool(name: str, *, pin: Mapping[str, object], tools: ExternalTools, env: Mapping[str, str], candidate_root: Path, reviewed_ref: str, trusted_tool_root: Path, sequence: int) -> tuple[Path, Mapping[str, object]]:
    tooling = pin['tooling']
    assert isinstance(tooling, dict)
    record = tooling[name]
    assert isinstance(record, dict)
    path_value = record['path']
    blob = str(record['gitBlobSha']).lower()
    assert isinstance(path_value, str)
    tree_line = str(_run_git(tools, env, candidate_root, 'ls-tree', reviewed_ref, '--', path_value)).strip()
    parts = tree_line.split(None, 3)
    if len(parts) != 4 or parts[1] != 'blob' or parts[2].lower() != blob:
        raise VerificationError(f'reviewed tree blob mismatch for {name}: expected={blob}, tree={tree_line!r}')
    content = bytes(_run_git(tools, env, candidate_root, 'cat-file', 'blob', blob, text=False))
    trusted_tool_root.mkdir(parents=True, exist_ok=True)
    destination = trusted_tool_root / f'{sequence:04d}-{name}.py'
    descriptor, temporary_name = tempfile.mkstemp(prefix=f'.{destination.name}.', dir=trusted_tool_root)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 320)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    actual_blob = bytes(_run_git(tools, env, candidate_root, 'hash-object', '--stdin', text=False, input_data=content)).decode('ascii').strip().lower()
    if actual_blob != blob:
        raise VerificationError(f'materialized tool hash mismatch for {name}: expected={blob}, actual={actual_blob}')
    return (destination, record)

def _protected_digests(paths: Iterable[Path]) -> dict[Path, str]:
    return {path: sha256_file(path) for path in paths if path.is_file()}

def _verify_protected_digests(expected: Mapping[Path, str]) -> None:
    for path, digest in expected.items():
        if not path.is_file() or sha256_file(path) != digest:
            raise VerificationError(f'candidate lane modified trusted evidence: {path}')

def _trusted_evidence_snapshot(trusted_root: Path, *, exclude: Iterable[Path]=()) -> dict[Path, str]:
    excluded = {path.resolve(strict=False) for path in exclude}
    candidates: list[Path] = []
    for name in ('summary.json', 'reviewed-dispositions.json'):
        candidates.append(trusted_root / name)
    for directory_name in ('evidence', 'reports', 'logs'):
        directory = trusted_root / directory_name
        if directory.is_dir():
            candidates.extend(directory.rglob('*'))
    return {path: sha256_file(path) for path in candidates if path.is_file() and path.resolve(strict=False) not in excluded}

def _invoke_frozen(name: str, arguments: Sequence[str], *, state: dict[str, int], pin: Mapping[str, object], tools: ExternalTools, env: Mapping[str, str], candidate_root: Path, reviewed_ref: str, trusted_root: Path, cwd: Path, log_path: Path, timeout_seconds: float) -> tuple[CommandResult, Mapping[str, object]]:
    state['sequence'] += 1
    script, record = materialize_tool(name, pin=pin, tools=tools, env=env, candidate_root=candidate_root, reviewed_ref=reviewed_ref, trusted_tool_root=trusted_root / 'tools', sequence=state['sequence'])
    expected_script_sha256 = sha256_file(script)
    result = run_isolated([os.fspath(tools.python), '-I', os.fspath(script), *arguments], cwd=cwd, env=env, log_path=log_path, timeout_seconds=timeout_seconds)
    if not script.is_file() or sha256_file(script) != expected_script_sha256:
        raise VerificationError(f'materialized tool changed during execution: {script}')
    return (result, record)

def _require_result(result: CommandResult, *, label: str, semantic: bool=False) -> None:
    if result.exit_code == 0:
        return
    if semantic and result.exit_code == 1:
        raise VerificationBlocked(f'{label} blocked; see {result.log_path}')
    raise VerificationError(f'{label} failed operationally with exit {result.exit_code}; see {result.log_path}')

def _validator_command(spec: ValidatorSpec, tools: ExternalTools) -> list[str]:
    executable = tools.python if spec.kind == 'python' else tools.bash
    return [os.fspath(executable), *spec.arguments]

def _write_summary(trusted_root: Path, *, status: str, baseline_ref: str, candidate_ref: str, message: str) -> Path:
    path = trusted_root / 'summary.json'
    path.write_text(_canonical_json({'schemaVersion': 1, 'status': status, 'baselineRef': baseline_ref, 'candidateRef': candidate_ref, 'message': message, 'trustedEvidenceRoot': os.fspath(trusted_root)}), encoding='utf-8')
    return path

def _copy_reports(trusted_root: Path, output: Path) -> None:
    sources: list[Path] = []
    for name in ('summary.json', 'reviewed-dispositions.json'):
        source = trusted_root / name
        if source.is_file():
            sources.append(source)
    for directory_name in ('evidence', 'reports', 'logs'):
        directory = trusted_root / directory_name
        if directory.is_dir():
            sources.extend((path for path in directory.rglob('*') if path.is_file()))
    for source in sorted(set(sources)):
        relative = source.relative_to(trusted_root)
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

__all__ = [name for name in globals() if not name.startswith("__")]
