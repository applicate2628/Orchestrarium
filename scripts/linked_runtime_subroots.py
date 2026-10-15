"""Identity-bound authority for explicitly trusted linked runtime subroots.

This module deliberately has no provider registry or home discovery.  Callers
declare the exact user-global logical roots they trust; all other links remain
outside this authority boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import stat


Identity = tuple[int, int, int, int]
LinkWitness = tuple[str, Identity, str, str]


def _lexical_absolute(path: Path) -> Path:
    value = os.path.abspath(os.path.expanduser(str(path)))
    if os.name == "nt" and value.startswith("\\\\?\\"):
        value = value[4:]
    return Path(os.path.normpath(value))


def _identity(path: Path) -> Identity:
    return _metadata_identity(path.lstat())


def _metadata_identity(metadata: os.stat_result) -> Identity:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        getattr(metadata, "st_file_attributes", 0),
    )


def _is_reparse(metadata: os.stat_result) -> bool:
    return bool(
        getattr(metadata, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(_lexical_absolute(left))) == os.path.normcase(
        str(_lexical_absolute(right))
    )


def _link_kind(path: Path, metadata: os.stat_result) -> str | None:
    if stat.S_ISLNK(metadata.st_mode):
        return "symlink"
    if getattr(os.path, "isjunction", lambda _path: False)(path):
        return "junction"
    if _is_reparse(metadata):
        raise ValueError("E_RUNTIME_SUBROOT_REPARSE_UNSUPPORTED")
    return None


def _link_target(link: Path, raw_target: str) -> Path:
    target = Path(raw_target)
    return _lexical_absolute(target if target.is_absolute() else link.parent / target)


def _path_walk(path: Path) -> tuple[Path, list[str]]:
    if not path.is_absolute() or not path.anchor:
        raise ValueError("E_RUNTIME_SUBROOT_TARGET_INVALID")
    return Path(path.anchor), list(path.parts[1:])


def _walk_linked_path(selected: Path, *, read_link):
    """Resolve each target completely before its saved caller continuation."""
    current, pending = _path_walk(selected)
    observations = []
    observed = {}
    active = set()
    selected_leaf = None
    remaining = len(pending)

    def observe(path, metadata):
        kind = _link_kind(path, metadata)
        raw_target = read_link(path) if kind is not None else None
        key = os.path.normcase(str(path))
        binding = (_metadata_identity(metadata), raw_target, kind)
        previous = observed.get(key)
        if previous is not None and previous != binding:
            raise ValueError("E_RUNTIME_SUBROOT_IDENTITY_CHANGED")
        observed[key] = binding
        observations.append((path, metadata, raw_target, kind))
        return key, raw_target, kind

    observe(current, current.lstat())
    frames = [(current, list(reversed(pending)), None)]
    while frames:
        current, pending, target_key = frames[-1]
        if not pending:
            frames.pop()
            if target_key is not None:
                active.remove(target_key)
            if not frames:
                return current, tuple(observations), selected_leaf or current, False
            _previous, continuation, parent_key = frames[-1]
            frames[-1] = (current, continuation, parent_key)
            continue
        candidate = current / pending.pop()
        remaining -= 1
        if remaining == 0 and selected_leaf is None:
            selected_leaf = candidate
        try:
            metadata = candidate.lstat()
        except FileNotFoundError:
            suffix = list(reversed(pending))
            for _parent, continuation, _key in reversed(frames[:-1]):
                suffix.extend(reversed(continuation))
            missing = candidate.joinpath(*suffix)
            return missing, tuple(observations), selected_leaf or missing, True
        key, raw_target, kind = observe(candidate, metadata)
        if kind is not None:
            if key in active:
                raise ValueError("E_RUNTIME_SUBROOT_TARGET_INVALID: active link cycle")
            active.add(key)
            root, target = _path_walk(_link_target(candidate, raw_target))
            observe(root, root.lstat())
            remaining += len(target)
            frames.append((root, list(reversed(target)), key))
            continue
        if remaining and not stat.S_ISDIR(metadata.st_mode):
            raise ValueError("E_RUNTIME_SUBROOT_TARGET_INVALID: parent type")
        frames[-1] = (candidate, pending, target_key)
    raise ValueError("E_RUNTIME_SUBROOT_TARGET_INVALID")


def _resolve_linked_directory(logical_root: Path) -> tuple[Path, tuple[LinkWitness, ...]]:
    """Require this traversal's terminal directory and retain every link witness."""
    def read_link(path):
        try:
            return os.readlink(path)
        except OSError as exc:
            raise ValueError("E_RUNTIME_SUBROOT_TARGET_INVALID") from exc

    try:
        resolved, observations, _leaf, missing = _walk_linked_path(
            _lexical_absolute(logical_root), read_link=read_link)
    except FileNotFoundError as exc:
        raise ValueError("E_RUNTIME_SUBROOT_TARGET_INVALID") from exc
    if missing or not stat.S_ISDIR(observations[-1][1].st_mode):
        raise ValueError("E_RUNTIME_SUBROOT_TARGET_INVALID")
    witnesses = tuple((str(path), _metadata_identity(metadata), raw_target, kind)
                      for path, metadata, raw_target, kind in observations if kind is not None)
    return resolved, witnesses


def _logical_leaf_link_kind(selected: Path) -> str | None:
    """Classify every lexical logical component before granting ordinary-root parity."""

    current, pending = _path_walk(selected)
    while pending:
        candidate = current / pending.pop(0)
        try:
            metadata = candidate.lstat()
        except FileNotFoundError:
            return None
        kind = _link_kind(candidate, metadata)
        if kind is not None:
            if candidate != selected:
                raise ValueError("E_RUNTIME_SUBROOT_SCOPE_DENIED")
            return kind
        if pending:
            if not stat.S_ISDIR(metadata.st_mode):
                return None
            current = candidate
    return None


@dataclass(frozen=True)
class LinkedRuntimeSubrootAuthority:
    """A caller-declared global link plus its immutable resolution witness."""

    logical_root: Path
    logical_identity: Identity
    resolved_root: Path
    resolved_identity: Identity
    link_chain: tuple[LinkWitness, ...]
    trusted_global_roots: tuple[Path, ...]
    allow_linked_ancestors: bool = False

    @property
    def name(self) -> str:
        return self.logical_root.name

    @classmethod
    def bind(
        cls,
        logical_root: Path,
        *,
        scope: str,
        trusted_global_roots: tuple[Path, ...],
        allow_linked_ancestors: bool = False,
    ) -> "LinkedRuntimeSubrootAuthority | None":
        selected = _lexical_absolute(logical_root)
        trusted = tuple(_lexical_absolute(path) for path in trusted_global_roots)
        is_trusted_global = scope == "global" and any(
            _same_path(selected, path) for path in trusted
        )
        if allow_linked_ancestors:
            if not is_trusted_global:
                raise ValueError("E_RUNTIME_SUBROOT_SCOPE_DENIED")
            resolved_root, link_chain = _resolve_linked_directory(selected)
            if not link_chain:
                return None
        else:
            kind = _logical_leaf_link_kind(selected)
            if kind is None:
                return None
            if not is_trusted_global:
                raise ValueError("E_RUNTIME_SUBROOT_SCOPE_DENIED")
            resolved_root, link_chain = _resolve_linked_directory(selected)
        return cls(
            logical_root=selected,
            logical_identity=_identity(selected),
            resolved_root=resolved_root,
            resolved_identity=_identity(resolved_root),
            link_chain=link_chain,
            trusted_global_roots=trusted,
            allow_linked_ancestors=allow_linked_ancestors,
        )

    def assert_current(self) -> None:
        current = self.bind(
            self.logical_root,
            scope="global",
            trusted_global_roots=self.trusted_global_roots,
            allow_linked_ancestors=self.allow_linked_ancestors,
        )
        if (
            current is None
            or current.logical_identity != self.logical_identity
            or current.resolved_root != self.resolved_root
            or current.resolved_identity != self.resolved_identity
            or current.link_chain != self.link_chain
        ):
            raise ValueError("E_RUNTIME_SUBROOT_IDENTITY_CHANGED")

    def ordinary_file(self, relative: Path) -> Path:
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("E_ROLE_POLICY_INVALID: role-leaf-type")
        self.assert_current()
        candidate = self.resolved_root
        for part in relative.parts:
            candidate = candidate / part
            try:
                metadata = candidate.lstat()
            except OSError as exc:
                raise ValueError("E_ROLE_POLICY_INVALID: role-leaf-type") from exc
            if stat.S_ISLNK(metadata.st_mode) or _is_reparse(metadata):
                raise ValueError("E_ROLE_POLICY_INVALID: role-leaf-type")
        if not stat.S_ISREG(candidate.lstat().st_mode):
            raise ValueError("E_ROLE_POLICY_INVALID: role-leaf-type")
        return candidate
