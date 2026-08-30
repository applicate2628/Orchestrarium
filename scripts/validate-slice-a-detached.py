#!/usr/bin/env python3
"""Validate Slice A in one supervised detached Git worktree."""

from __future__ import annotations

import argparse
import ast
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import time
from typing import Any

if __name__ == "__main__":
    from process_supervision.process_runner import (
        EnvironmentRowV1,
        ProcessRequestV1,
        ProcessRunnerV1,
        SettlePolicyV1,
    )
    from skill_pack_validator_runtime import ValidatorCapturePolicyV1
else:
    from scripts.process_supervision.process_runner import (
        EnvironmentRowV1,
        ProcessRequestV1,
        ProcessRunnerV1,
        SettlePolicyV1,
    )
    from scripts.skill_pack_validator_runtime import ValidatorCapturePolicyV1


TERMINAL_MANIFEST_NAME = "slice-a-validation-result-v1.json"
BASELINE_DESTINATION = Path(".scratch/legacy-obligation-migration/baseline.json")
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SHA256 = re.compile(r"^[0-9A-Fa-f]{64}$")
_ENV_ALLOWLIST = (
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "HOME",
)
_PYTHON_LINE_CITATION = re.compile(
    r"(?<![A-Za-z0-9_./-])([A-Za-z0-9_./-]+\.py):\d+"
)
_PYTHON_SYMBOL_CITATION = re.compile(
    r"([A-Za-z0-9_./-]+\.py)::(?:\{([^}]+)\}|([A-Za-z_][A-Za-z0-9_.]*))"
)
_GIT_TIMEOUT_SECONDS = 120.0
_SETTLEMENT_TIMEOUT_SECONDS = 5.0
_ORCHESTRATION_TIMEOUT_SECONDS = 2.0
_MAX_RECEIPT_BYTES = 64 * 1024


@dataclass(frozen=True)
class GitResultV1:
    args: tuple[str, ...]
    returncode: int
    stdout: bytes
    stderr: bytes


@dataclass(frozen=True)
class SliceACommand:
    name: str
    argv: tuple[str, ...]
    timeout_seconds: float

    def __post_init__(self) -> None:
        if not _NAME.fullmatch(self.name):
            raise ValueError(f"invalid Slice-A command name: {self.name!r}")
        if (
            not self.argv
            or not isinstance(self.argv[0], str)
            or not self.argv[0]
            or any(not isinstance(value, str) for value in self.argv)
            or not 0 < self.timeout_seconds <= 1800
        ):
            raise ValueError(f"invalid Slice-A command contract: {self.name}")


@dataclass(frozen=True)
class ChildReceipt:
    schemaVersion: int
    name: str
    argv: tuple[str, ...]
    cwd: str
    environmentKeys: tuple[str, ...]
    timeoutSeconds: float
    outcome: str
    terminalStage: str
    failureId: str | None
    exitCode: int | None
    timedOut: bool
    cancelled: bool
    reaped: bool
    durationSeconds: float
    stdoutObservedBytes: int
    stdoutPersistedBytes: int
    stdoutTruncated: bool
    stdoutSha256: str
    stderrObservedBytes: int
    stderrPersistedBytes: int
    stderrTruncated: bool
    stderrSha256: str
    treeBackend: str
    ownershipConfirmed: bool
    settlementState: str
    treeEmpty: bool
    resourcesClosed: bool
    authorizing: bool = False


@dataclass
class WorktreeAcquisitionOwnership:
    target_path: Path
    add_attempted: bool = False
    path_present: bool = False
    registration_present: bool = False


@dataclass(frozen=True)
class CleanupOutcome:
    worktree_removed: bool
    registration_removed: bool
    failures: tuple[str, ...]
    recovery_path: str | None
    path_present: bool = False
    registration_present: bool = False
    attempts: tuple[str, ...] = ()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_relative(value: str) -> str:
    candidate = PurePosixPath(value.replace("\\", "/"))
    if (
        not value
        or candidate.is_absolute()
        or ".." in candidate.parts
        or candidate.parts[0].casefold() == ".git"
        or candidate.as_posix() in {".", ""}
    ):
        raise ValueError(f"unsafe relative path: {value!r}")
    return candidate.as_posix()


def _resolved_argv(argv: tuple[str, ...]) -> tuple[Path, tuple[str, ...]]:
    first = Path(argv[0])
    if first.is_absolute():
        executable = first.resolve()
        actual_argv = (str(executable), *argv[1:])
    else:
        located = shutil.which(argv[0])
        if located is None:
            raise ValueError(f"executable is unavailable: {argv[0]}")
        executable = Path(located).resolve()
        actual_argv = (str(executable), *argv[1:])
    if not executable.is_file():
        raise ValueError(f"executable is not an ordinary file: {argv[0]}")
    return executable, actual_argv


def _windows_argv_profile_id(executable: Path) -> str | None:
    if os.name != "nt":
        return None
    if executable.resolve() == Path(sys.executable).resolve():
        return "python-validator-json-echo-v1"
    if executable.name.casefold() in {"git", "git.exe"}:
        return "git-rev-parse-sq-quote-v1"
    return None


def _run_process(
    runner: ProcessRunnerV1,
    argv: tuple[str, ...],
    cwd: Path,
    timeout_seconds: float,
    *,
    outer_deadline_monotonic: float | None = None,
):
    executable, actual_argv = _resolved_argv(argv)
    environment = _child_environment()
    capture_policy = ValidatorCapturePolicyV1().to_capture_policy()
    sink = runner.mint_memory_capture_sink()
    deadline = time.monotonic() + timeout_seconds
    if outer_deadline_monotonic is not None:
        deadline = min(deadline, outer_deadline_monotonic)
    request = ProcessRequestV1(
        schema_version=1,
        argv=actual_argv,
        resolved_executable=executable,
        cwd=str(Path(cwd).resolve()),
        environment=tuple(
            EnvironmentRowV1(name, value) for name, value in environment.items()
        ),
        stdin_bytes=None,
        deadline_monotonic=deadline,
        capture_policy=capture_policy,
        capture_sink_binding=sink,
        settle_policy=SettlePolicyV1(_SETTLEMENT_TIMEOUT_SECONDS),
        windows_argv_profile_id=_windows_argv_profile_id(executable),
        policy_id=capture_policy.policy_id,
    )
    result = runner.run(request)
    return actual_argv, environment, sink, result


def _git(
    runner: ProcessRunnerV1,
    repo_root: Path,
    *args: str,
    check: bool = True,
) -> GitResultV1:
    argv, _environment, sink, supervision = _run_process(
        runner,
        ("git", "-C", str(repo_root), *args),
        repo_root,
        _GIT_TIMEOUT_SECONDS,
    )
    returncode = supervision.target_exit_code
    if returncode is None or (
        returncode == 0
        and (
            supervision.failure_id is not None
            or not supervision.tree.tree_empty
            or not supervision.resources_closed
        )
    ):
        returncode = -1
    result = GitResultV1(
        tuple(argv),
        returncode,
        sink.bytes_for("stdout"),
        sink.bytes_for("stderr"),
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: "
            + result.stderr.decode("utf-8", errors="replace")[:2048]
        )
    return result


def _status(runner: ProcessRunnerV1, repo_root: Path) -> dict[str, str]:
    payload = _git(
        runner,
        repo_root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
    ).stdout
    fields = payload.split(b"\0")
    result: dict[str, str] = {}
    index = 0
    while index < len(fields) and fields[index]:
        entry = fields[index]
        if len(entry) < 4 or entry[2:3] != b" ":
            raise ValueError("unsupported Git status record")
        state = entry[:2].decode("ascii", errors="strict")
        path = _safe_relative(entry[3:].decode("utf-8", errors="strict"))
        if "R" in state or "C" in state:
            raise ValueError(f"renamed/copied overlay path is unsupported: {path}")
        if path in result:
            raise ValueError(f"duplicate Git status path: {path}")
        result[path] = state
        index += 1
    return result


def _ordinary_file(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return (
        stat.S_ISREG(metadata.st_mode)
        and not stat.S_ISLNK(metadata.st_mode)
        and not bool(
            getattr(metadata, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        )
    )


def _python_symbols(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    symbols: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.add(node.name)
            if isinstance(node, ast.ClassDef):
                symbols.update(
                    f"{node.name}.{child.name}"
                    for child in node.body
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                )
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            symbols.update(
                target.id for target in targets if isinstance(target, ast.Name)
            )
    return symbols


def _validate_design_currency(repo_root: Path, design_path: Path) -> None:
    """Validate active owner terminology and every live Python symbol citation."""

    text = design_path.read_text(encoding="utf-8")
    section = ""
    historical_sections = {
        "### Superseded paragraphs",
        "## Alternatives rejected",
    }
    obsolete_owner_tokens = (
        "_PostMaterializationMutationPlan",
        "post-materialization plan",
        "planned/unplanned",
        "post-tree plan",
    )
    citation_lines: list[str] = []
    slice_b = False
    for line in text.splitlines():
        if line.startswith("#"):
            section = line.strip()
            if section.startswith("### B"):
                slice_b = True
            elif section.startswith("## "):
                slice_b = False
        supersession_sentence = "is superseded" in line.casefold()
        if section not in historical_sections and not supersession_sentence and any(
            token.casefold() in line.casefold() for token in obsolete_owner_tokens
        ):
            raise ValueError(
                "E_SLICE_A_VALIDATION_INCOMPLETE: active obsolete writer owner terminology"
            )
        live_line = (
            section not in historical_sections
            and not supersession_sentence
            and not slice_b
        )
        if live_line and _PYTHON_LINE_CITATION.search(line):
            raise ValueError(
                "E_SLICE_A_VALIDATION_INCOMPLETE: live numeric Python citation"
            )
        if live_line:
            citation_lines.append(line)

    for line in citation_lines:
        for match in _PYTHON_SYMBOL_CITATION.finditer(line):
            relative = _safe_relative(match.group(1))
            if relative == "file.py":
                continue
            source = repo_root / Path(relative)
            if not _ordinary_file(source):
                candidates = [
                    candidate
                    for candidate in repo_root.rglob(Path(relative).name)
                    if _ordinary_file(candidate)
                    and not {
                        ".git",
                        ".scratch",
                        "work-items",
                        ".reports",
                        ".plans",
                    }.intersection(candidate.relative_to(repo_root).parts)
                ]
                if len(candidates) != 1:
                    raise ValueError(
                        f"E_SLICE_A_VALIDATION_INCOMPLETE: ambiguous cited source {relative}"
                    )
                source = candidates[0]
            names = (
                tuple(item.strip() for item in match.group(2).split(","))
                if match.group(2) is not None
                else (match.group(3),)
            )
            current_symbols = _python_symbols(source)
            missing = tuple(
                name for name in names if not name or name not in current_symbols
            )
            deletion_contract = (
                "| simplify/delete |" in line.casefold()
                or (
                    "remove" in line.casefold()
                    and "zero-caller" in line.casefold()
                    and "find neither" in line.casefold()
                )
            )
            if missing and deletion_contract and set(missing) == set(names):
                continue
            if missing:
                raise ValueError(
                    "E_SLICE_A_VALIDATION_INCOMPLETE: unresolved Python symbol citation "
                    f"{relative}::{','.join(name or '<empty>' for name in names)}"
                )


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    if path.exists() or temporary.exists():
        raise FileExistsError(f"refusing to replace evidence: {path}")
    encoded = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


def _atomic_publish(path: Path, payload: dict[str, Any]) -> Path:
    _atomic_json(path, payload)
    return path


def _overlay_manifest(
    runner: ProcessRunnerV1,
    repo_root: Path,
    admitted_paths: tuple[str, ...],
    excluded_paths: tuple[str, ...],
    ignored_untracked_paths: tuple[str, ...],
) -> tuple[
    str,
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
]:
    admitted = tuple(_safe_relative(path) for path in admitted_paths)
    excluded = tuple(_safe_relative(path) for path in excluded_paths)
    ignored = tuple(_safe_relative(path) for path in ignored_untracked_paths)
    if (
        len(set(admitted)) != len(admitted)
        or len(set(excluded)) != len(excluded)
        or len(set(ignored)) != len(ignored)
    ):
        raise ValueError("duplicate admitted/excluded path")
    if (
        set(admitted) & set(excluded)
        or set(admitted) & set(ignored)
        or set(excluded) & set(ignored)
    ):
        raise ValueError("path has multiple admission classes")
    status = _status(runner, repo_root)
    classified = set(admitted) | set(excluded) | set(ignored)
    if set(status) != classified:
        raise ValueError(
            "unclassified dirty paths: "
            f"missing={sorted(classified - set(status))} "
            f"extra={sorted(set(status) - classified)}"
        )
    head = _git(runner, repo_root, "rev-parse", "HEAD").stdout.decode("ascii").strip()
    overlay: list[dict[str, Any]] = []
    for relative in admitted:
        source = repo_root / Path(relative)
        deleted = "D" in status[relative]
        head_present = (
            _git(
                runner,
                repo_root,
                "cat-file",
                "-e",
                f"HEAD:{relative}",
                check=False,
            ).returncode
            == 0
        )
        if deleted:
            if source.exists() or source.is_symlink():
                raise ValueError(f"deleted overlay path still exists: {relative}")
            overlay.append(
                {
                    "path": relative,
                    "operation": "delete",
                    "sha256": None,
                    "headPresent": head_present,
                }
            )
        else:
            if not _ordinary_file(source):
                raise ValueError(f"overlay source is not an ordinary file: {relative}")
            overlay.append(
                {
                    "path": relative,
                    "operation": "write",
                    "sha256": _sha256(source),
                    "headPresent": head_present,
                }
            )
    exclusions: list[dict[str, Any]] = []
    for relative in excluded:
        head_blob = _git(runner, repo_root, "show", f"HEAD:{relative}").stdout
        exclusions.append(
            {
                "path": relative,
                "headSha256": hashlib.sha256(head_blob).hexdigest(),
            }
        )
    ignored_records: list[dict[str, Any]] = []
    for relative in ignored:
        if status[relative] != "??":
            raise ValueError(f"excluded-untracked path is not untracked: {relative}")
        ignored_records.append({"path": relative, "status": "??"})
    return head, tuple(overlay), tuple(exclusions), tuple(ignored_records)


def _materialize_inputs(
    runner: ProcessRunnerV1,
    repo_root: Path,
    worktree: Path,
    head: str,
    overlay: tuple[dict[str, Any], ...],
    exclusions: tuple[dict[str, Any], ...],
    ignored_untracked: tuple[dict[str, Any], ...],
    baseline_path: Path,
    baseline_sha256: str,
) -> tuple[str, ...]:
    if not worktree.joinpath(".git").is_file():
        raise ValueError("detached worktree .git file is missing")
    actual_head = _git(runner, worktree, "rev-parse", "HEAD").stdout.decode("ascii").strip()
    if actual_head != head:
        raise ValueError("detached worktree HEAD drifted")
    for record in overlay:
        destination = worktree / Path(record["path"])
        if record["operation"] == "delete":
            if destination.is_dir():
                raise ValueError(f"overlay deletion targets directory: {record['path']}")
            destination.unlink(missing_ok=True)
        else:
            source = repo_root / Path(record["path"])
            if _sha256(source) != record["sha256"]:
                raise ValueError(f"overlay source drifted: {record['path']}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            if _sha256(destination) != record["sha256"]:
                raise ValueError(f"overlay destination drifted: {record['path']}")
    for record in exclusions:
        destination = worktree / Path(record["path"])
        if not _ordinary_file(destination) or _sha256(destination) != record["headSha256"]:
            raise ValueError(f"excluded path is not HEAD-exact: {record['path']}")
    for record in ignored_untracked:
        destination = worktree / Path(record["path"])
        if destination.exists() or destination.is_symlink():
            raise ValueError(
                f"excluded-untracked path reached detached worktree: {record['path']}"
            )
    if not _ordinary_file(baseline_path) or _sha256(baseline_path) != baseline_sha256.lower():
        raise ValueError("declared scratch baseline is missing or drifted")
    baseline_target = worktree / BASELINE_DESTINATION
    baseline_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(baseline_path, baseline_target)
    if _sha256(baseline_target) != baseline_sha256.lower():
        raise ValueError("worktree scratch baseline drifted")

    shell_paths = tuple(
        _safe_relative(item.decode("utf-8", errors="strict"))
        for item in _git(
            runner, worktree, "ls-files", "-z", "--", "*.sh"
        ).stdout.split(b"\0")
        if item
    )
    if not shell_paths or any(not _ordinary_file(worktree / path) for path in shell_paths):
        raise ValueError("tracked shell census is missing or incomplete")
    dirty = set(_status(runner, worktree))
    expected_dirty = {record["path"] for record in overlay}
    if dirty != expected_dirty:
        raise ValueError(
            f"worktree overlay census drifted: expected={sorted(expected_dirty)} actual={sorted(dirty)}"
        )
    return shell_paths


def _child_environment() -> dict[str, str]:
    environment = {
        key: os.environ[key]
        for key in _ENV_ALLOWLIST
        if key in os.environ and os.environ[key]
    }
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def _run_child(
    runner: ProcessRunnerV1,
    command: SliceACommand,
    worktree: Path,
    attempts_dir: Path,
    ordinal: int,
    *,
    outer_deadline_monotonic: float | None = None,
) -> ChildReceipt:
    prefix = f"{ordinal:02d}-{command.name}"
    receipt_path = attempts_dir / f"{prefix}.receipt.json"
    argv, environment, _sink, result = _run_process(
        runner,
        command.argv,
        worktree,
        command.timeout_seconds,
        outer_deadline_monotonic=outer_deadline_monotonic,
    )
    receipt = ChildReceipt(
        schemaVersion=2,
        name=command.name,
        argv=argv,
        cwd=".",
        environmentKeys=tuple(sorted(environment)),
        timeoutSeconds=command.timeout_seconds,
        outcome=result.outcome,
        terminalStage=result.terminal_stage,
        failureId=result.failure_id,
        exitCode=result.target_exit_code,
        timedOut=result.timed_out,
        cancelled=result.cancelled,
        reaped=result.tree.direct_reaped,
        durationSeconds=round(result.duration_seconds, 6),
        stdoutObservedBytes=result.stdout.observed_bytes,
        stdoutPersistedBytes=result.stdout.persisted_bytes,
        stdoutTruncated=result.stdout.truncated,
        stdoutSha256=result.stdout.digest,
        stderrObservedBytes=result.stderr.observed_bytes,
        stderrPersistedBytes=result.stderr.persisted_bytes,
        stderrTruncated=result.stderr.truncated,
        stderrSha256=result.stderr.digest,
        treeBackend=result.tree.backend,
        ownershipConfirmed=result.tree.ownership_confirmed,
        settlementState=result.tree.settlement_state,
        treeEmpty=result.tree.tree_empty,
        resourcesClosed=result.resources_closed,
    )
    _atomic_json(receipt_path, _receipt_payload(receipt))
    return receipt


def _receipt_payload(receipt: ChildReceipt) -> dict[str, Any]:
    payload = asdict(receipt)
    payload["argv"] = list(receipt.argv)
    payload["environmentKeys"] = list(receipt.environmentKeys)
    return payload


def _strict_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"duplicate receipt key: {key}")
        payload[key] = value
    return payload


def _read_receipt(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        encoded = stream.read(_MAX_RECEIPT_BYTES + 1)
    if len(encoded) > _MAX_RECEIPT_BYTES:
        raise ValueError("receipt exceeds bounded size")
    try:
        payload = json.loads(
            encoded.decode("utf-8"), object_pairs_hook=_strict_json_object
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("receipt is not strict UTF-8 JSON") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schemaVersion") not in {1, 2}
        or payload.get("authorizing") is not False
    ):
        raise ValueError("receipt contract is unsupported")
    return payload


def _receipt_summary(receipt: ChildReceipt | dict[str, Any]) -> dict[str, Any]:
    payload = _receipt_payload(receipt) if isinstance(receipt, ChildReceipt) else receipt
    argv = payload.get("argv")
    if not isinstance(argv, list) or any(not isinstance(item, str) for item in argv):
        raise ValueError("receipt argv is invalid")
    argv_sha256 = hashlib.sha256(
        json.dumps(
            argv, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    schema_version = payload["schemaVersion"]
    summary = {
        "schemaVersion": schema_version,
        "legacy": schema_version == 1,
        "currentEvidence": schema_version == 2,
        "name": payload.get("name"),
        "argvSha256": argv_sha256,
        "timeoutSeconds": payload.get("timeoutSeconds"),
        "exitCode": payload.get("exitCode"),
        "timedOut": payload.get("timedOut"),
        "cancelled": payload.get("cancelled"),
        "reaped": payload.get("reaped"),
        "durationSeconds": payload.get("durationSeconds"),
        "stdoutSha256": payload.get("stdoutSha256"),
        "stderrSha256": payload.get("stderrSha256"),
        "authorizing": False,
    }
    if schema_version == 2:
        summary.update(
            {
                "outcome": payload.get("outcome"),
                "terminalStage": payload.get("terminalStage"),
                "failureId": payload.get("failureId"),
                "stdoutObservedBytes": payload.get("stdoutObservedBytes"),
                "stdoutPersistedBytes": payload.get("stdoutPersistedBytes"),
                "stdoutTruncated": payload.get("stdoutTruncated"),
                "stderrObservedBytes": payload.get("stderrObservedBytes"),
                "stderrPersistedBytes": payload.get("stderrPersistedBytes"),
                "stderrTruncated": payload.get("stderrTruncated"),
                "treeBackend": payload.get("treeBackend"),
                "ownershipConfirmed": payload.get("ownershipConfirmed"),
                "settlementState": payload.get("settlementState"),
                "treeEmpty": payload.get("treeEmpty"),
                "resourcesClosed": payload.get("resourcesClosed"),
            }
        )
    return summary


def _reason_code(value: str | None) -> str | None:
    if value is None:
        return None
    head = value.split(":", 1)[0]
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", head).strip("-")
    return (normalized or "unspecified")[:128]


def _worktree_registration_present(
    runner: ProcessRunnerV1, repo_root: Path, worktree: Path
) -> bool:
    listing = _git(
        runner, repo_root, "worktree", "list", "--porcelain", check=False
    )
    if listing.returncode != 0:
        raise OSError(
            "worktree-list:"
            + listing.stderr.decode("utf-8", errors="replace")[:1024]
        )
    expected = os.path.normcase(os.path.abspath(worktree))
    for raw_line in listing.stdout.decode("utf-8", errors="strict").splitlines():
        if not raw_line.startswith("worktree "):
            continue
        candidate = os.path.normcase(os.path.abspath(raw_line[9:]))
        if candidate == expected:
            return True
    return False


def _partial_worktree_path_present(worktree: Path) -> bool:
    return os.path.lexists(worktree)


def _remove_partial_worktree_path(repo_root: Path, worktree: Path) -> None:
    workspace = Path(os.path.abspath(repo_root.parent))
    parent = Path(os.path.abspath(worktree.parent))
    direct_owned = (
        parent == workspace
        and worktree.name.startswith(".orchestrarium-slice-a-worktree-")
    )
    nested_owned = (
        Path(os.path.abspath(worktree.parent.parent)) == workspace
        and worktree.parent.name.startswith(".orchestrarium-slice-a-worktree-")
        and worktree.name in {"baseline", "candidate"}
    )
    if not (direct_owned or nested_owned):
        raise OSError("partial worktree path is outside the owned workspace child")
    metadata = worktree.lstat()
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or bool(
            getattr(metadata, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        )
        or (hasattr(os.path, "isjunction") and os.path.isjunction(worktree))
    ):
        raise OSError("partial worktree root is not an ordinary directory")
    pending = [worktree]
    while pending:
        current = pending.pop()
        with os.scandir(current) as entries:
            for entry in entries:
                child = Path(entry.path)
                child_metadata = entry.stat(follow_symlinks=False)
                if (
                    stat.S_ISLNK(child_metadata.st_mode)
                    or bool(
                        getattr(child_metadata, "st_file_attributes", 0)
                        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
                    )
                    or (hasattr(os.path, "isjunction") and os.path.isjunction(child))
                ):
                    raise OSError("partial worktree contains reparse indirection")
                if stat.S_ISDIR(child_metadata.st_mode):
                    pending.append(child)
                elif not stat.S_ISREG(child_metadata.st_mode):
                    raise OSError("partial worktree contains unsupported object type")
    shutil.rmtree(worktree)


def _remove_external_root(repo_root: Path, external_root: Path) -> tuple[str, ...]:
    workspace = Path(os.path.abspath(repo_root.parent))
    if (
        Path(os.path.abspath(external_root.parent)) != workspace
        or not external_root.name.startswith(".orchestrarium-slice-a-worktree-")
    ):
        return ("external-root-outside-owned-workspace",)
    if not os.path.lexists(external_root):
        return ()
    try:
        metadata = external_root.lstat()
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or bool(
                getattr(metadata, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            )
            or (hasattr(os.path, "isjunction") and os.path.isjunction(external_root))
        ):
            return ("external-root-not-ordinary-directory",)
        _remove_partial_worktree_path(repo_root, external_root)
    except OSError as exc:
        return (f"external-root-remove:{exc}",)
    return ()


def _remove_worktree(
    runner: ProcessRunnerV1, repo_root: Path, worktree: Path
) -> CleanupOutcome:
    failures: list[str] = []
    result = _git(
        runner,
        repo_root,
        "worktree",
        "remove",
        "--force",
        str(worktree),
        check=False,
    )
    if result.returncode != 0:
        failures.append(
            "worktree-remove:"
            + result.stderr.decode("utf-8", errors="replace")[:1024]
        )
    try:
        registered = _worktree_registration_present(runner, repo_root, worktree)
    except (OSError, UnicodeDecodeError) as exc:
        failures.append(str(exc))
        registered = True
    if registered:
        failures.append("worktree-registration-remains")
    path_present = _partial_worktree_path_present(worktree)
    if path_present:
        failures.append("worktree-path-remains")
    return CleanupOutcome(
        worktree_removed=not path_present,
        registration_removed=not registered,
        failures=tuple(failures),
        recovery_path=str(worktree) if failures else None,
        path_present=path_present,
        registration_present=registered,
        attempts=("git-worktree-remove",),
    )


def _settle_worktree_acquisition(
    runner: ProcessRunnerV1,
    repo_root: Path,
    ownership: WorktreeAcquisitionOwnership,
) -> CleanupOutcome:
    """Observe and settle path/registration independently after every add attempt."""

    failures: list[str] = []
    attempts: list[str] = []
    ownership.path_present = _partial_worktree_path_present(ownership.target_path)
    try:
        ownership.registration_present = _worktree_registration_present(
            runner, repo_root, ownership.target_path
        )
    except (OSError, UnicodeDecodeError) as exc:
        ownership.registration_present = True
        failures.append(str(exc))

    if ownership.registration_present:
        attempts.append("git-worktree-remove")
        removed = _remove_worktree(runner, repo_root, ownership.target_path)
        failures.extend(removed.failures)
        ownership.path_present = _partial_worktree_path_present(ownership.target_path)
        try:
            ownership.registration_present = _worktree_registration_present(
                runner, repo_root, ownership.target_path
            )
        except (OSError, UnicodeDecodeError) as exc:
            ownership.registration_present = True
            failures.append(str(exc))

    if ownership.path_present and not ownership.registration_present:
        attempts.append("partial-path-remove")
        try:
            _remove_partial_worktree_path(repo_root, ownership.target_path)
        except (OSError, ValueError) as exc:
            failures.append(f"partial-path-remove:{exc}")

    ownership.path_present = _partial_worktree_path_present(ownership.target_path)
    try:
        ownership.registration_present = _worktree_registration_present(
            runner, repo_root, ownership.target_path
        )
    except (OSError, UnicodeDecodeError) as exc:
        ownership.registration_present = True
        failures.append(str(exc))
    if ownership.path_present and "worktree-path-remains" not in failures:
        failures.append("worktree-path-remains")
    if ownership.registration_present and "worktree-registration-remains" not in failures:
        failures.append("worktree-registration-remains")
    return CleanupOutcome(
        worktree_removed=not ownership.path_present,
        registration_removed=not ownership.registration_present,
        failures=tuple(failures),
        recovery_path=(
            str(ownership.target_path)
            if ownership.path_present or ownership.registration_present or failures
            else None
        ),
        path_present=ownership.path_present,
        registration_present=ownership.registration_present,
        attempts=tuple(attempts),
    )


def _required_outer_budget_seconds(commands: tuple[SliceACommand, ...]) -> float:
    return (
        sum(
            command.timeout_seconds + _SETTLEMENT_TIMEOUT_SECONDS
            for command in commands
        )
        + _ORCHESTRATION_TIMEOUT_SECONDS
    )


def validate_slice_a(
    *,
    repo_root: Path,
    run_dir: Path,
    admitted_paths: tuple[str, ...],
    excluded_paths: tuple[str, ...],
    baseline_path: Path,
    baseline_sha256: str,
    commands: tuple[SliceACommand, ...],
    validation_scope: str,
    design_path: Path | None = None,
    design_sha256: str | None = None,
    ignored_untracked_paths: tuple[str, ...] = (),
) -> Path | None:
    """Run the narrow Slice-A lifecycle and publish only after cleanup settles."""

    repo_root = Path(repo_root).resolve()
    run_dir = Path(run_dir).resolve()
    baseline_path = Path(baseline_path).resolve()
    if validation_scope not in {
        "slice-a-final",
        "platform-final-correction-a",
        "unit-fixture",
    }:
        raise ValueError("unsupported Slice-A validation scope")
    if not _SHA256.fullmatch(baseline_sha256):
        raise ValueError("baseline SHA-256 is invalid")
    if validation_scope != "unit-fixture":
        if design_path is None or design_sha256 is None or not _SHA256.fullmatch(design_sha256):
            raise ValueError("declared design artifact and SHA-256 are required")
        design_path = Path(design_path).resolve()
        if not _ordinary_file(design_path) or _sha256(design_path) != design_sha256.lower():
            raise ValueError("declared design artifact is missing or drifted")
        _validate_design_currency(repo_root, design_path)
    scratch_root = repo_root / ".scratch"
    try:
        run_dir.relative_to(scratch_root)
    except ValueError as exc:
        raise ValueError("run directory must be below repository .scratch") from exc
    terminal_path = run_dir / TERMINAL_MANIFEST_NAME
    if terminal_path.exists():
        raise FileExistsError(f"terminal manifest already exists: {terminal_path}")
    run_dir.mkdir(parents=True, exist_ok=True)
    attempts_dir = run_dir / "attempts"
    attempts_dir.mkdir()
    worktree_key = hashlib.sha256(str(run_dir).encode("utf-8")).hexdigest()[:16]
    external_root = (
        repo_root.parent / f".orchestrarium-slice-a-worktree-{worktree_key}"
    )
    worktree = external_root / "candidate"
    if os.path.lexists(external_root):
        raise FileExistsError(f"detached worktree root already exists: {external_root}")
    acquisition = WorktreeAcquisitionOwnership(worktree)
    runner = ProcessRunnerV1()

    head = ""
    overlay: tuple[dict[str, Any], ...] = ()
    exclusions: tuple[dict[str, Any], ...] = ()
    ignored_untracked: tuple[dict[str, Any], ...] = ()
    shell_paths: tuple[str, ...] = ()
    receipts: list[dict[str, Any]] = []
    incomplete_reason: str | None = None
    original_cause: str | None = None
    pending: BaseException | None = None
    cleanup = CleanupOutcome(True, True, (), None)
    try:
        head, overlay, exclusions, ignored_untracked = _overlay_manifest(
            runner,
            repo_root,
            admitted_paths,
            excluded_paths,
            ignored_untracked_paths,
        )
        external_root.mkdir(parents=True)
        acquisition.add_attempted = True
        add = _git(
            runner,
            repo_root,
            "worktree",
            "add",
            "--detach",
            str(worktree),
            head,
            check=False,
        )
        if add.returncode != 0:
            raise RuntimeError(
                "worktree-add:"
                + add.stderr.decode("utf-8", errors="replace")[:1024]
            )
        shell_paths = _materialize_inputs(
            runner,
            repo_root,
            worktree,
            head,
            overlay,
            exclusions,
            ignored_untracked,
            baseline_path,
            baseline_sha256.lower(),
        )
        outer_deadline = time.monotonic() + _required_outer_budget_seconds(commands)
        for ordinal, command in enumerate(commands, 1):
            receipt = _run_child(
                runner,
                command,
                worktree,
                attempts_dir,
                ordinal,
                outer_deadline_monotonic=outer_deadline,
            )
            if receipt is None:
                incomplete_reason = f"missing-receipt:{command.name}"
                break
            receipt_path = attempts_dir / f"{ordinal:02d}-{command.name}.receipt.json"
            persisted_receipt = _read_receipt(receipt_path)
            if (
                persisted_receipt.get("schemaVersion") != 2
                or persisted_receipt != _receipt_payload(receipt)
            ):
                raise ValueError(f"receipt drifted: {command.name}")
            receipts.append(persisted_receipt)
            if (
                persisted_receipt.get("outcome") != "success"
                or persisted_receipt.get("failureId") is not None
                or persisted_receipt.get("exitCode") != 0
                or persisted_receipt.get("timedOut") is not False
                or persisted_receipt.get("cancelled") is not False
                or persisted_receipt.get("reaped") is not True
                or persisted_receipt.get("settlementState") != "EMPTY"
                or persisted_receipt.get("treeEmpty") is not True
                or persisted_receipt.get("resourcesClosed") is not True
            ):
                incomplete_reason = f"child-incomplete:{command.name}"
                break
        if incomplete_reason is None:
            final_status = set(_status(runner, worktree))
            expected_status = {record["path"] for record in overlay}
            if final_status != expected_status:
                incomplete_reason = "final-worktree-status-drift"
    except (OSError, RuntimeError, ValueError) as exc:
        incomplete_reason = f"collection:{type(exc).__name__}:{str(exc)[:1024]}"
        original_cause = incomplete_reason
        _atomic_json(
            attempts_dir / "supervisor-error.json",
            {
                "schemaVersion": 1,
                "authorizing": False,
                "stableId": "E_SLICE_A_VALIDATION_INCOMPLETE",
                "cause": incomplete_reason,
            },
        )
    except BaseException as exc:
        pending = exc
        original_cause = f"{type(exc).__name__}:{str(exc)[:1024]}"
    finally:
        if acquisition.add_attempted:
            cleanup = _settle_worktree_acquisition(runner, repo_root, acquisition)

    cleanup_failures = list(cleanup.failures)
    cleanup_attempts = list(cleanup.attempts)
    recovery_path = cleanup.recovery_path
    if not cleanup.path_present and not cleanup.registration_present:
        root_failures = _remove_external_root(repo_root, external_root)
        cleanup_attempts.append("external-root-remove")
        cleanup_failures.extend(root_failures)
        if root_failures:
            recovery_path = str(external_root)
    runner_close = runner.close()
    if runner_close.outcome != "closed":
        cleanup_failures.append(
            f"process-runner-close:{runner_close.failure_id or 'unknown'}"
        )
    cleanup = CleanupOutcome(
        worktree_removed=cleanup.worktree_removed,
        registration_removed=cleanup.registration_removed,
        failures=tuple(cleanup_failures),
        recovery_path=recovery_path,
        path_present=cleanup.path_present,
        registration_present=cleanup.registration_present,
        attempts=tuple(cleanup_attempts),
    )

    if cleanup.failures:
        payload = {
            "schemaVersion": 1,
            "scope": validation_scope,
            "result": "NON_PASS",
            "stableId": "E_SLICE_A_VALIDATION_CLEANUP_FAILED",
            "authorizing": False,
            "publishedAfterCleanup": True,
            "sourceHead": head or None,
            "designSha256": design_sha256.lower() if design_sha256 else None,
            "recoveryPath": cleanup.recovery_path,
            "originalCause": _reason_code(original_cause),
            "cleanup": {
                "worktreeRemoved": cleanup.worktree_removed,
                "registrationRemoved": cleanup.registration_removed,
                "pathPresent": cleanup.path_present,
                "registrationPresent": cleanup.registration_present,
                "attempts": list(cleanup.attempts),
                "failures": [_reason_code(value) for value in cleanup.failures],
            },
            "receipts": [_receipt_summary(receipt) for receipt in receipts],
            "incompleteReason": _reason_code(incomplete_reason),
        }
        manifest_path = _atomic_publish(terminal_path, payload)
        if pending is not None:
            raise pending
        return manifest_path
    if pending is not None:
        raise pending
    if incomplete_reason is not None:
        return None

    payload = {
        "schemaVersion": 1,
        "scope": validation_scope,
        "result": "PASS",
        "stableId": None,
        "authorizing": False,
        "publishedAfterCleanup": True,
        "sourceHead": head,
        "designSha256": design_sha256.lower() if design_sha256 else None,
        "recoveryPath": None,
        "overlay": list(overlay),
            "excludedHeadExact": list(exclusions),
            "excludedUntracked": list(ignored_untracked),
        "baseline": {
            "path": BASELINE_DESTINATION.as_posix(),
            "sha256": baseline_sha256.lower(),
        },
        "shellCensus": list(shell_paths),
        "cleanup": {
            "worktreeRemoved": cleanup.worktree_removed,
            "registrationRemoved": cleanup.registration_removed,
            "pathPresent": cleanup.path_present,
            "registrationPresent": cleanup.registration_present,
            "attempts": list(cleanup.attempts),
            "failures": [],
        },
        "receipts": [_receipt_summary(receipt) for receipt in receipts],
        "incompleteReason": None,
    }
    return _atomic_publish(terminal_path, payload)


def _platform_commands() -> tuple[SliceACommand, ...]:
    python = sys.executable
    git = shutil.which("git")
    if git is None:
        raise ValueError("Git executable is unavailable")
    if os.name == "nt":
        bash_path = Path(git).resolve().parent.parent / "bin" / "bash.exe"
        if not _ordinary_file(bash_path):
            raise ValueError("Git Bash executable is unavailable")
        bash = str(bash_path)
    else:
        bash = shutil.which("bash")
        if bash is None:
            raise ValueError("Bash executable is unavailable")
    commands = (
        SliceACommand(
            "final-correction-guards",
            (
                python,
                "-m",
                "pytest",
                "tests/test_native_luna_corridor.py",
                "tests/test_slice_a_detached_validation.py",
                "tests/test_slice_a_design_currency.py",
                "-q",
            ),
            1800,
        ),
        SliceACommand(
            "f1-f6",
            (
                python,
                "-m",
                "pytest",
                "tests/test_native_role_slice_a.py",
                "tests/test_hook_health.py",
                "tests/test_hook_runtime_installers.py",
                "tests/test_hook_runtime_transactions.py",
                "-q",
            ),
            1800,
        ),
        SliceACommand(
            "entrypoints",
            (python, "-m", "pytest", "tests/test_python_production_entrypoints.py", "-q", "-rs"),
            600,
        ),
        SliceACommand(
            "protected-agents-mode",
            (
                python,
                "-m",
                "pytest",
                "tests/test_resolve_agents_mode.py",
                "tests/test_normalize_agents_mode_contract.py",
                "tests/test_agents_mode_installer_regression.py",
                "tests/test_agents_mode_docs_sync.py",
                "tests/test_agents_mode_contract.py",
                "-q",
            ),
            600,
        ),
        SliceACommand(
            "installer-regression",
            (python, "scripts/validate-agents-mode-installers.py", "--root", "."),
            600,
        ),
        SliceACommand(
            "codex-pack",
            (bash, "src.codex/skills/lead/scripts/validate-skill-pack.sh"),
            600,
        ),
        SliceACommand(
            "claude-pack",
            (bash, "src.claude/agents/scripts/validate-skill-pack.sh"),
            600,
        ),
        SliceACommand(
            "compile",
            (python, "-m", "compileall", "-q", "scripts", "src.codex", "src.claude"),
            120,
        ),
        SliceACommand(
            "diff-check",
            ("git", "diff", "--check"),
            120,
        ),
    )
    return commands


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--admit", action="append", required=True)
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--ignore-untracked", action="append", default=[])
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--baseline-sha256", required=True)
    parser.add_argument("--design", required=True)
    parser.add_argument("--design-sha256", required=True)
    parser.add_argument("--platform-only", action="store_true")
    args = parser.parse_args()
    try:
        manifest = validate_slice_a(
            repo_root=Path(args.repo_root),
            run_dir=Path(args.run_dir),
            admitted_paths=tuple(args.admit),
            excluded_paths=tuple(args.exclude),
            ignored_untracked_paths=tuple(args.ignore_untracked),
            baseline_path=Path(args.baseline),
            baseline_sha256=args.baseline_sha256,
            commands=_platform_commands(),
            validation_scope=(
                "platform-final-correction-a"
                if args.platform_only
                else "slice-a-final"
            ),
            design_path=Path(args.design),
            design_sha256=args.design_sha256,
        )
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"E_SLICE_A_VALIDATION_INCOMPLETE: {exc}", file=sys.stderr)
        return 1
    if manifest is None:
        print("E_SLICE_A_VALIDATION_INCOMPLETE: no terminal manifest", file=sys.stderr)
        return 1
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    print(str(manifest))
    return 0 if payload["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
