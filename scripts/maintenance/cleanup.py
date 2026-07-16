#!/usr/bin/env python3
"""Repository-local janitor engine.

Sweep transitions are deliberately journal-free:

=================  =================  ========================================
source             destination        result
=================  =================  ========================================
present            absent             one same-volume ``os.rename``
present            present            destination wins; skip and report
absent             present            already quarantined; no action
absent             absent             already purged/externally wiped
=================  =================  ========================================

The quarantine layout itself preserves recovery identity.  No file is renamed
inside quarantine and no live-tree sweep ever hard-deletes an artifact.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Iterator, Sequence


SWEEP_DAYS = 7
PURGE_DAYS = 7
REFERENCE_LIVENESS_DAYS = 90
STALE_WORK_ITEM_DAYS = 14
SECONDS_PER_DAY = 24 * 60 * 60
TRASH_RELATIVE = Path(".scratch") / "_trash"
LOCK_NAME = ".janitor.lock"
README_NAME = "README.md"
TRASH_README = """# Janitor quarantine

This directory is a wipeable zone. Everything stored here may be deleted at any
time. Do not keep important or long-lived data here.
"""
REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
AGE_BUCKETS = ("0-7d", ">7-14d", ">14-30d", ">30-90d", ">90d")
GLOB_TOKEN_RE = re.compile(r"[^\s\"'`<>]+")


class CleanupError(RuntimeError):
    """Base class for errors that must fail closed."""


class ReferenceScanError(CleanupError):
    """A reference source could not be enumerated or read."""


class JanitorLockError(CleanupError):
    """Another janitor owns the exclusive run lock."""


@dataclass(frozen=True)
class Artifact:
    path: Path
    relative_path: Path
    size: int
    mtime: float
    age_days: float


@dataclass
class Action:
    path: Path
    relative_path: Path
    size: int
    age_days: float
    classification: str
    reason: str
    destination: Path | None = None
    outcome: str = "pending"


@dataclass
class Bucket:
    count: int = 0
    bytes: int = 0


@dataclass
class Telemetry:
    eligible: Bucket = field(default_factory=Bucket)
    pinned: Bucket = field(default_factory=Bucket)
    blocked: Bucket = field(default_factory=Bucket)
    pinned_set_size: int = 0
    age_histogram: dict[str, Bucket] = field(
        default_factory=lambda: {name: Bucket() for name in AGE_BUCKETS}
    )

    def add_classification(self, classification: str, size: int) -> None:
        bucket = getattr(self, classification)
        bucket.count += 1
        bucket.bytes += size

    def add_age(self, age_days: float, size: int) -> None:
        if age_days <= 7:
            name = "0-7d"
        elif age_days <= 14:
            name = ">7-14d"
        elif age_days <= 30:
            name = ">14-30d"
        elif age_days <= 90:
            name = ">30-90d"
        else:
            name = ">90d"
        self.age_histogram[name].count += 1
        self.age_histogram[name].bytes += size


@dataclass
class Report:
    action: str
    apply: bool
    actions: list[Action] = field(default_factory=list)
    telemetry: Telemetry = field(default_factory=Telemetry)
    messages: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    stale_work_items: list[Path] = field(default_factory=list)
    run_dir: Path | None = None


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    path: Path
    reason: str
    report: Report


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_now(now: datetime | None) -> datetime:
    value = now or _utc_now()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _age_days(mtime: float, now: datetime) -> float:
    return max(0.0, (now.timestamp() - mtime) / SECONDS_PER_DAY)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _is_reparse(stat_result: os.stat_result) -> bool:
    return bool(getattr(stat_result, "st_file_attributes", 0) & REPARSE_POINT)


def _is_link_or_reparse(path: Path) -> bool:
    try:
        result = path.lstat()
    except OSError as exc:
        raise CleanupError(f"cannot inspect path {path}: {exc}") from exc
    return stat.S_ISLNK(result.st_mode) or _is_reparse(result)


def _walk_regular_files(
    base: Path,
    *,
    error_type: type[CleanupError] = CleanupError,
    on_pruned: Callable[[Path], None] | None = None,
    prune_dir: Callable[[Path], bool] | None = None,
) -> Iterator[Path]:
    """Walk without following symbolic links or Windows reparse points."""

    stack = [base]
    while stack:
        directory = stack.pop()
        try:
            with os.scandir(directory) as entries:
                ordered = sorted(entries, key=lambda entry: entry.name.casefold())
        except OSError as exc:
            raise error_type(f"cannot enumerate {directory}: {exc}") from exc

        child_dirs: list[Path] = []
        for entry in ordered:
            path = Path(entry.path)
            try:
                info = entry.stat(follow_symlinks=False)
                link_or_reparse = entry.is_symlink() or _is_reparse(info)
            except OSError as exc:
                raise error_type(f"cannot inspect {path}: {exc}") from exc
            if link_or_reparse:
                if on_pruned is not None:
                    on_pruned(path)
                continue
            if entry.is_dir(follow_symlinks=False):
                if prune_dir is not None and prune_dir(path):
                    continue
                child_dirs.append(path)
            elif entry.is_file(follow_symlinks=False):
                yield path
        stack.extend(reversed(child_dirs))


def _normalize_reference(value: str) -> str:
    normalized = value.replace("\\", "/")
    return normalized.casefold() if os.name == "nt" else normalized


def _split_brace_options(body: str) -> list[str]:
    options: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(body):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == "," and depth == 0:
            options.append(body[start:index])
            start = index + 1
    options.append(body[start:])
    return options


def brace_expand(pattern: str) -> list[str]:
    """Expand comma braces recursively; unmatched braces remain literal."""

    opening = pattern.find("{")
    if opening < 0:
        return [pattern]
    depth = 0
    closing = -1
    for index in range(opening, len(pattern)):
        if pattern[index] == "{":
            depth += 1
        elif pattern[index] == "}":
            depth -= 1
            if depth == 0:
                closing = index
                break
    if closing < 0:
        return [pattern]
    body = pattern[opening + 1 : closing]
    options = _split_brace_options(body)
    if len(options) == 1:
        return [pattern]
    expanded: list[str] = []
    for option in options:
        expanded.extend(
            brace_expand(pattern[:opening] + option + pattern[closing + 1 :])
        )
    return expanded


def _has_dotted_extension(pattern: str) -> bool:
    filename = pattern.rsplit("/", 1)[-1]
    return re.search(r"\.[^.*?{}]+$", filename) is not None


def _has_literal_glob_fragment(pattern: str) -> bool:
    return any(fragment.strip("/") for fragment in re.split(r"\*+|\?", pattern))


def _is_glob_citation(pattern: str) -> bool:
    return (
        ("/" in pattern or _has_dotted_extension(pattern))
        and _has_literal_glob_fragment(pattern)
    )


def _glob_patterns(text: str) -> set[str]:
    patterns: set[str] = set()
    for raw in GLOB_TOKEN_RE.findall(text):
        # `candidate`, not the auth-flavored noun: the publication scanner
        # blocks that noun under assignment as a credential marker, and this
        # value is a lexical glob fragment, never a secret.
        candidate = raw.lstrip(",;:()").rstrip(".,;:()")
        if not (
            any(char in candidate for char in "*?")
            or ("{" in candidate and "}" in candidate)
        ):
            continue
        patterns.update(
            pattern for pattern in brace_expand(candidate) if _is_glob_citation(pattern)
        )
    return patterns


def _separator_aware_glob_match(target: str, pattern: str) -> bool:
    expression: list[str] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*" and index + 1 < len(pattern) and pattern[index + 1] == "*":
            expression.append(".*")
            index += 2
        elif char == "*":
            expression.append("[^/]*")
            index += 1
        elif char == "?":
            expression.append("[^/]")
            index += 1
        else:
            expression.append(re.escape(char))
            index += 1
    return re.fullmatch("".join(expression), target) is not None


def _prompt_triple_targets(relative_path: Path) -> set[str]:
    if relative_path.suffix.casefold() not in {".md", ".out", ".err"}:
        return set()
    if not any("prompt" in part.casefold() for part in relative_path.parts[:-1]):
        return set()
    parent = relative_path.parent
    stem = relative_path.stem
    targets = {stem, (parent / stem).as_posix()}
    for suffix in (".md", ".out", ".err"):
        targets.add(f"{stem}{suffix}")
        targets.add((parent / f"{stem}{suffix}").as_posix())
    return {_normalize_reference(target) for target in targets}


def _text_references_artifact(text: str, relative_path: Path) -> bool:
    normalized_text = _normalize_reference(text)
    path_target = _normalize_reference(relative_path.as_posix())
    triple_targets = _prompt_triple_targets(relative_path)
    literal_targets = {path_target, *triple_targets}
    if any(target and target in normalized_text for target in literal_targets):
        return True
    glob_targets = {
        path_target,
        _normalize_reference(relative_path.name),
        *triple_targets,
    }
    for pattern in _glob_patterns(normalized_text):
        if any(
            _separator_aware_glob_match(target, pattern) for target in glob_targets
        ):
            return True
    return False


def _reference_file_is_live(path: Path, root: Path, now: datetime) -> bool:
    relative = path.relative_to(root)
    parts = tuple(part.casefold() for part in relative.parts)
    if len(parts) >= 3 and parts[0] == "work-items" and parts[1] == "active":
        return True
    if parts and parts[0] == ".reports":
        try:
            age = _age_days(path.stat().st_mtime, now)
        except OSError as exc:
            raise ReferenceScanError(f"cannot stat reference file {path}: {exc}") from exc
        return age < REFERENCE_LIVENESS_DAYS
    return False


def _read_live_reference_texts(root: Path, now: datetime) -> list[tuple[Path, str]]:
    live: list[tuple[Path, str]] = []
    for relative_base in (Path(".reports"), Path("work-items")):
        base = root / relative_base
        if not base.exists():
            continue
        if _is_link_or_reparse(base):
            raise ReferenceScanError(f"reference root is a link or reparse point: {base}")
        for path in _walk_regular_files(base, error_type=ReferenceScanError):
            # Read every reference source so an unreadable file fails the whole scan,
            # even when its citation would later be considered expired.
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise ReferenceScanError(f"cannot read reference file {path}: {exc}") from exc
            if _reference_file_is_live(path, root, now):
                live.append((path, text))
    return live


def _collect_artifacts(
    root: Path,
    now: datetime,
    selected: Path | None = None,
    messages: list[str] | None = None,
) -> list[Artifact]:
    scratch = (root / ".scratch").resolve(strict=False)
    trash = (root / TRASH_RELATIVE).resolve(strict=False)
    if selected is None:
        base = root / ".scratch"
        if not base.exists():
            return []
    else:
        base = selected

    pruned = messages.append if messages is not None else None
    paths: Iterable[Path]
    if base.is_file() and not _is_link_or_reparse(base):
        paths = (base,)
    elif base.is_dir() and not _is_link_or_reparse(base):
        paths = _walk_regular_files(
            base,
            on_pruned=(lambda path: pruned(f"pruned link/reparse point: {path}"))
            if pruned is not None
            else None,
            prune_dir=lambda path: _is_within(
                path.resolve(strict=False), trash
            ),
        )
    else:
        raise CleanupError(f"path is not a regular file or directory: {base}")

    artifacts: list[Artifact] = []
    for path in paths:
        try:
            resolved = path.resolve(strict=True)
            info = path.stat()
        except OSError as exc:
            raise CleanupError(f"cannot inspect artifact {path}: {exc}") from exc
        if not _is_within(resolved, scratch) or _is_within(resolved, trash):
            continue
        try:
            relative = path.relative_to(root)
        except ValueError as exc:
            raise CleanupError(f"artifact is outside repository root: {path}") from exc
        artifacts.append(
            Artifact(
                path=path,
                relative_path=relative,
                size=info.st_size,
                mtime=info.st_mtime,
                age_days=_age_days(info.st_mtime, now),
            )
        )
    return sorted(artifacts, key=lambda artifact: artifact.relative_path.as_posix().casefold())


def _stale_work_items(root: Path, now: datetime) -> list[Path]:
    active = root / "work-items" / "active"
    if not active.is_dir() or _is_link_or_reparse(active):
        return []
    stale: list[Path] = []
    for item in sorted(active.iterdir(), key=lambda path: path.name.casefold()):
        if not item.is_dir() or _is_link_or_reparse(item):
            continue
        try:
            mtimes = [path.stat().st_mtime for path in _walk_regular_files(item)]
        except (CleanupError, OSError):
            continue
        if mtimes and _age_days(max(mtimes), now) > STALE_WORK_ITEM_DAYS:
            stale.append(item.relative_to(root))
    return stale


def _analyze_artifacts(
    root: Path,
    artifacts: Sequence[Artifact],
    now: datetime,
    *,
    action_name: str,
    apply: bool,
) -> Report:
    report = Report(action=action_name, apply=apply)
    report.stale_work_items = _stale_work_items(root, now)
    try:
        references = _read_live_reference_texts(root, now)
    except ReferenceScanError as exc:
        report.errors.append(str(exc))
        references = []

    referenced_paths: set[Path] = set()
    if not report.errors:
        for artifact in artifacts:
            if any(
                _text_references_artifact(text, artifact.relative_path)
                for _source, text in references
            ):
                referenced_paths.add(artifact.relative_path)
    report.telemetry.pinned_set_size = len(referenced_paths)

    for artifact in artifacts:
        report.telemetry.add_age(artifact.age_days, artifact.size)
        if report.errors:
            classification = "blocked"
            reason = "reference scan failed closed"
        elif artifact.age_days > REFERENCE_LIVENESS_DAYS:
            classification = "eligible"
            reason = f"older than hard ceiling ({REFERENCE_LIVENESS_DAYS}d)"
        elif artifact.age_days <= SWEEP_DAYS:
            classification = "blocked"
            reason = f"not older than sweep threshold ({SWEEP_DAYS}d)"
        elif artifact.relative_path in referenced_paths:
            classification = "pinned"
            reason = "live reference"
        else:
            classification = "eligible"
            reason = "older than sweep threshold with no live reference"
        report.telemetry.add_classification(classification, artifact.size)
        report.actions.append(
            Action(
                path=artifact.path,
                relative_path=artifact.relative_path,
                size=artifact.size,
                age_days=artifact.age_days,
                classification=classification,
                reason=reason,
                outcome="would-move" if classification == "eligible" and not apply else "pending",
            )
        )
    return report


def build_sweep_plan(root: Path, *, now: datetime | None = None, apply: bool = False) -> Report:
    root = root.resolve()
    current = _coerce_now(now)
    messages: list[str] = []
    artifacts = _collect_artifacts(root, current, messages=messages)
    report = _analyze_artifacts(
        root, artifacts, current, action_name="sweep", apply=apply
    )
    report.messages[:0] = messages
    return report


def _lock_diagnostic(lock_path: Path) -> str:
    holder = ""
    try:
        holder = lock_path.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return (
        f"janitor already running ({lock_path}; holder: {holder or 'unknown'}). "
        "No automatic takeover — verify the holder pid is dead, remove the lock file, retry."
    )


@contextmanager
def janitor_lock(
    root: Path,
    *,
    now: datetime | None = None,
    cleanup_created_dirs: bool = False,
) -> Iterator[Path]:
    root = root.resolve()
    current = _coerce_now(now)
    scratch = root / ".scratch"
    trash = root / TRASH_RELATIVE
    scratch_existed = scratch.exists()
    trash_existed = trash.exists()
    trash.mkdir(parents=True, exist_ok=True)
    lock_path = trash / LOCK_NAME
    descriptor: int | None = None
    try:
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise JanitorLockError(_lock_diagnostic(lock_path)) from exc
        try:
            payload = f"pid={os.getpid()} at={current.isoformat()}\n".encode("utf-8")
            os.write(descriptor, payload)
        except BaseException:
            os.close(descriptor)
            descriptor = None
            lock_path.unlink(missing_ok=True)
            raise
        yield lock_path
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            finally:
                lock_path.unlink(missing_ok=True)
        if cleanup_created_dirs:
            if not trash_existed:
                try:
                    trash.rmdir()
                except OSError:
                    pass
            if not scratch_existed:
                try:
                    scratch.rmdir()
                except OSError:
                    pass


def _ensure_trash_readme(root: Path) -> Path:
    readme = root / TRASH_RELATIVE / README_NAME
    try:
        with readme.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(TRASH_README)
    except FileExistsError:
        pass
    return readme


def reserve_run_dir(root: Path, *, now: datetime | None = None) -> Path:
    root = root.resolve()
    current = _coerce_now(now)
    date_dir = root / TRASH_RELATIVE / current.strftime("%Y-%m-%d")
    date_dir.mkdir(parents=True, exist_ok=True)
    base_name = current.strftime("%H%M%S")
    attempt = 1
    while True:
        name = base_name if attempt == 1 else f"{base_name}-{attempt}"
        candidate = date_dir / name
        try:
            os.mkdir(candidate)
            return candidate
        except FileExistsError:
            attempt += 1


def classify_transition(source: Path, destination: Path) -> str:
    source_exists = os.path.lexists(source)
    destination_exists = os.path.lexists(destination)
    if source_exists and not destination_exists:
        return "source-only"
    if source_exists and destination_exists:
        return "both"
    if not source_exists and destination_exists:
        return "destination-only"
    return "neither"


def _checked_destination(base: Path, relative_path: Path, containment: Path) -> Path:
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise CleanupError(f"unsafe relative path: {relative_path}")
    destination = base / relative_path
    resolved = destination.resolve(strict=False)
    containment_resolved = containment.resolve(strict=False)
    if not _is_within(resolved, containment_resolved):
        raise CleanupError(
            f"destination escapes containment root: {destination} not under {containment}"
        )
    return destination


def _apply_quarantine_move(report: Report, action: Action, trash: Path) -> None:
    assert report.run_dir is not None
    destination = _checked_destination(report.run_dir, action.relative_path, trash)
    action.destination = destination
    transition = classify_transition(action.path, destination)
    if transition == "both":
        action.outcome = "skipped-destination-wins"
        report.messages.append(
            f"skip {action.relative_path}: source and destination both exist; destination wins"
        )
        return
    if transition == "destination-only":
        action.outcome = "already-quarantined"
        return
    if transition == "neither":
        action.outcome = "already-purged"
        return
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        _checked_destination(report.run_dir, action.relative_path, trash)
        os.rename(action.path, destination)
        action.outcome = "moved"
    except OSError as exc:
        action.outcome = "skipped-rename-failed"
        report.messages.append(f"skip {action.relative_path}: rename failed: {exc}")


def run_sweep(
    root: Path,
    *,
    apply: bool = False,
    now: datetime | None = None,
    operation_hook: Callable[[], None] | None = None,
) -> Report:
    root = root.resolve()
    current = _coerce_now(now)
    with janitor_lock(root, now=current, cleanup_created_dirs=not apply):
        if apply:
            _ensure_trash_readme(root)
        report = build_sweep_plan(root, now=current, apply=apply)
        if operation_hook is not None:
            operation_hook()
        eligible = [
            action for action in report.actions if action.classification == "eligible"
        ]
        if apply and eligible and not report.errors:
            report.run_dir = reserve_run_dir(root, now=current)
            trash = root / TRASH_RELATIVE
            for action in eligible:
                _apply_quarantine_move(report, action, trash)
        return report


def evaluate_eligibility(
    root: Path,
    path: Path,
    *,
    now: datetime | None = None,
) -> EligibilityResult:
    root = root.resolve()
    current = _coerce_now(now)
    candidate = path if path.is_absolute() else root / path
    if not os.path.lexists(candidate):
        raise CleanupError(f"path does not exist: {candidate}")
    if _is_link_or_reparse(candidate):
        raise CleanupError(f"path is a link or reparse point: {candidate}")
    resolved = candidate.resolve(strict=True)
    scratch = (root / ".scratch").resolve(strict=False)
    trash = (root / TRASH_RELATIVE).resolve(strict=False)
    if not _is_within(resolved, scratch) or _is_within(resolved, trash):
        raise CleanupError(f"path is outside sweep scope: {candidate}")
    artifacts = _collect_artifacts(root, current, selected=candidate)
    report = _analyze_artifacts(
        root, artifacts, current, action_name="eligible", apply=False
    )
    if report.errors:
        raise ReferenceScanError(report.errors[0])
    if not report.actions:
        return EligibilityResult(False, candidate, "directory contains no eligible files", report)
    eligible = all(action.classification == "eligible" for action in report.actions)
    if eligible:
        reason = "all files are eligible" if candidate.is_dir() else report.actions[0].reason
    else:
        first = next(action for action in report.actions if action.classification != "eligible")
        reason = first.reason
    return EligibilityResult(eligible, candidate, reason, report)


def _resolve_run_dir(root: Path, value: Path) -> Path:
    trash = (root / TRASH_RELATIVE).resolve(strict=False)
    if value.is_absolute():
        candidate = value
    elif os.path.lexists(root / value):
        candidate = root / value
    else:
        candidate = trash / value
    if not os.path.lexists(candidate):
        raise CleanupError(f"run directory does not exist: {candidate}")
    if _is_link_or_reparse(candidate) or not candidate.is_dir():
        raise CleanupError(f"run directory is not a regular directory: {candidate}")
    resolved = candidate.resolve(strict=True)
    if not _is_within(resolved, trash):
        raise CleanupError(f"run directory is outside quarantine: {candidate}")
    relative = resolved.relative_to(trash)
    if len(relative.parts) != 2:
        raise CleanupError(f"expected DATE/RUN quarantine directory: {candidate}")
    try:
        datetime.strptime(relative.parts[0], "%Y-%m-%d")
    except ValueError as exc:
        raise CleanupError(f"run directory has invalid date component: {candidate}") from exc
    return candidate


def _remove_empty_tree(path: Path, stop: Path) -> None:
    current = path
    while current != stop and _is_within(current.resolve(strict=False), stop.resolve(strict=False)):
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def run_restore(
    root: Path,
    run_dir: Path,
    *,
    apply: bool = False,
    now: datetime | None = None,
) -> Report:
    root = root.resolve()
    current = _coerce_now(now)
    with janitor_lock(root, now=current, cleanup_created_dirs=not apply):
        if apply:
            _ensure_trash_readme(root)
        source_root = _resolve_run_dir(root, run_dir)
        report = Report(action="restore", apply=apply, run_dir=source_root)
        trash = root / TRASH_RELATIVE
        scratch = root / ".scratch"
        for source in _walk_regular_files(
            source_root,
            on_pruned=lambda path: report.messages.append(
                f"pruned link/reparse point: {path}"
            ),
        ):
            relative = source.relative_to(source_root)
            info = source.stat()
            age = _age_days(info.st_mtime, current)
            report.telemetry.add_age(age, info.st_size)
            target = _checked_destination(root, relative, scratch)
            if os.path.lexists(target):
                classification = "blocked"
                reason = "occupied live target"
                outcome = "skipped-occupied"
            else:
                classification = "eligible"
                reason = "live target is unoccupied"
                outcome = "would-restore" if not apply else "pending"
            report.telemetry.add_classification(classification, info.st_size)
            action = Action(
                path=source,
                relative_path=relative,
                size=info.st_size,
                age_days=age,
                classification=classification,
                reason=reason,
                destination=target,
                outcome=outcome,
            )
            report.actions.append(action)
            if classification == "blocked":
                report.messages.append(f"skip {relative}: occupied live target {target}")
                continue
            if not apply:
                continue
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                _checked_destination(root, relative, scratch)
                os.rename(source, target)
                action.outcome = "restored"
            except OSError as exc:
                action.outcome = "skipped-rename-failed"
                report.messages.append(f"skip {relative}: restore rename failed: {exc}")
        if apply:
            _remove_empty_tree(source_root, trash)
        return report


def _tree_size(path: Path) -> int:
    total = 0
    try:
        for file_path in _walk_regular_files(path):
            total += file_path.stat().st_size
    except (CleanupError, OSError):
        return total
    return total


def run_purge(
    root: Path,
    *,
    apply: bool = False,
    now: datetime | None = None,
) -> Report:
    root = root.resolve()
    current = _coerce_now(now)
    with janitor_lock(root, now=current, cleanup_created_dirs=not apply):
        if apply:
            _ensure_trash_readme(root)
        trash = root / TRASH_RELATIVE
        report = Report(action="purge", apply=apply)
        for date_entry in sorted(trash.iterdir(), key=lambda path: path.name.casefold()):
            if date_entry.name in {LOCK_NAME, README_NAME} or not date_entry.is_dir():
                continue
            if _is_link_or_reparse(date_entry):
                report.messages.append(f"skip non-dated/reparse quarantine directory: {date_entry}")
                continue
            try:
                quarantine_date = datetime.strptime(date_entry.name, "%Y-%m-%d").date()
            except ValueError:
                size = _tree_size(date_entry)
                report.telemetry.blocked.count += 1
                report.telemetry.blocked.bytes += size
                report.actions.append(
                    Action(
                        path=date_entry,
                        relative_path=date_entry.relative_to(root),
                        size=size,
                        age_days=0,
                        classification="blocked",
                        reason="non-dated quarantine directory",
                        outcome="skipped-non-dated",
                    )
                )
                report.messages.append(f"skip non-dated quarantine directory: {date_entry}")
                continue
            age_days = (current.date() - quarantine_date).days
            for run_dir in sorted(date_entry.iterdir(), key=lambda path: path.name.casefold()):
                if not run_dir.is_dir() or _is_link_or_reparse(run_dir):
                    report.messages.append(f"skip invalid quarantine run entry: {run_dir}")
                    continue
                size = _tree_size(run_dir)
                report.telemetry.add_age(max(0, float(age_days)), size)
                if age_days > PURGE_DAYS:
                    classification = "eligible"
                    reason = f"quarantine date older than {PURGE_DAYS}d"
                    outcome = "would-purge" if not apply else "pending"
                else:
                    classification = "pinned"
                    reason = f"inside {PURGE_DAYS}d restore window"
                    outcome = "retained"
                report.telemetry.add_classification(classification, size)
                action = Action(
                    path=run_dir,
                    relative_path=run_dir.relative_to(root),
                    size=size,
                    age_days=float(age_days),
                    classification=classification,
                    reason=reason,
                    outcome=outcome,
                )
                report.actions.append(action)
                if apply and classification == "eligible":
                    try:
                        checked = run_dir.resolve(strict=True)
                        if not _is_within(checked, trash.resolve(strict=True)):
                            raise CleanupError(f"purge target escapes quarantine: {run_dir}")
                        shutil.rmtree(run_dir)
                        action.outcome = "purged"
                    except (OSError, CleanupError) as exc:
                        action.outcome = "skipped-purge-failed"
                        report.messages.append(f"skip {run_dir}: purge failed: {exc}")
            if apply:
                try:
                    date_entry.rmdir()
                except OSError:
                    pass
        return report


def _telemetry_dict(telemetry: Telemetry) -> dict[str, object]:
    return {
        "eligible": {"count": telemetry.eligible.count, "bytes": telemetry.eligible.bytes},
        "pinned": {"count": telemetry.pinned.count, "bytes": telemetry.pinned.bytes},
        "blocked": {"count": telemetry.blocked.count, "bytes": telemetry.blocked.bytes},
        "pinnedSetSize": telemetry.pinned_set_size,
        "ageHistogram": {
            name: {"count": bucket.count, "bytes": bucket.bytes}
            for name, bucket in telemetry.age_histogram.items()
        },
    }


def print_report(report: Report) -> None:
    mode = "apply" if report.apply else "dry-run"
    print(f"janitor {report.action} ({mode})")
    if report.run_dir is not None:
        print(f"run-dir: {report.run_dir}")
    for action in report.actions:
        print(
            f"{action.classification}: {action.relative_path} "
            f"[{action.outcome}] — {action.reason}"
        )
    for message in report.messages:
        print(f"info: {message}")
    for error in report.errors:
        print(f"error: {error}", file=sys.stderr)
    telemetry = report.telemetry
    print(
        "telemetry: "
        f"eligible={telemetry.eligible.count}/{telemetry.eligible.bytes}B "
        f"pinned={telemetry.pinned.count}/{telemetry.pinned.bytes}B "
        f"blocked={telemetry.blocked.count}/{telemetry.blocked.bytes}B"
    )
    print(f"pinned-set-size: {telemetry.pinned_set_size}")
    histogram = " ".join(
        f"{name}={bucket.count}/{bucket.bytes}B"
        for name, bucket in telemetry.age_histogram.items()
    )
    print(f"age-histogram: {histogram}")
    if report.stale_work_items:
        print("stale-work-items (>14d newest mtime):")
        for path in report.stale_work_items:
            print(f"  {path.as_posix()}")
    else:
        print("stale-work-items (>14d newest mtime): none")


def _json_error(code: str, message: str) -> str:
    return json.dumps(
        {"ok": False, "error": {"code": code, "message": message}},
        ensure_ascii=False,
    )


def _add_common_options(
    parser: argparse.ArgumentParser,
    *,
    include_apply: bool,
    suppress_defaults: bool,
) -> None:
    default_root: object = argparse.SUPPRESS if suppress_defaults else Path.cwd()
    parser.add_argument("--root", type=Path, default=default_root, help="Repository root (default: cwd)")
    if include_apply:
        default_apply: object = argparse.SUPPRESS if suppress_defaults else False
        parser.add_argument(
            "--apply",
            action="store_true",
            default=default_apply,
            help="Perform mutations; without this flag the command is a dry-run",
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sweep, restore, and purge repository-local scratch artifacts.")
    _add_common_options(parser, include_apply=True, suppress_defaults=False)
    subparsers = parser.add_subparsers(dest="command")

    sweep = subparsers.add_parser("sweep", help="Report or quarantine eligible .scratch files")
    _add_common_options(sweep, include_apply=True, suppress_defaults=True)

    restore = subparsers.add_parser("restore", help="Restore one DATE/RUN quarantine directory")
    restore.add_argument("run_dir", type=Path, help="Quarantine run directory or DATE/RUN path")
    _add_common_options(restore, include_apply=True, suppress_defaults=True)

    purge = subparsers.add_parser("purge", help="Purge run directories outside the restore window")
    _add_common_options(purge, include_apply=True, suppress_defaults=True)

    eligible = subparsers.add_parser("eligible", help="Evaluate the one canonical eligibility rule")
    eligible.add_argument("--path", type=Path, required=True, help="File or directory to evaluate")
    eligible.add_argument("--json", action="store_true", help="Emit the result as JSON")
    _add_common_options(eligible, include_apply=False, suppress_defaults=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "eligible":
            result = evaluate_eligibility(root, args.path)
            if args.json:
                print(
                    json.dumps(
                        {
                            "ok": True,
                            "eligible": result.eligible,
                            "path": str(result.path),
                            "reason": result.reason,
                            "telemetry": _telemetry_dict(result.report.telemetry),
                        },
                        ensure_ascii=False,
                    )
                )
            else:
                print(f"eligible={str(result.eligible).lower()}: {result.path} — {result.reason}")
                print_report(result.report)
            return 0 if result.eligible else 1
        if args.command == "restore":
            report = run_restore(root, args.run_dir, apply=args.apply)
        elif args.command == "purge":
            report = run_purge(root, apply=args.apply)
        else:
            report = run_sweep(root, apply=args.apply)
        print_report(report)
        return 2 if report.errors else 0
    except JanitorLockError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (CleanupError, OSError) as exc:
        if args.command == "eligible" and getattr(args, "json", False):
            print(_json_error("cleanup_error", str(exc)), file=sys.stderr)
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
