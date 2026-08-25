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


MAX_LINK_DEPTH = 64
Identity = tuple[int, int, int, int]
LinkWitness = tuple[str, Identity, str, str]


def _lexical_absolute(path: Path) -> Path:
    value = os.path.abspath(os.path.expanduser(str(path)))
    if os.name == "nt" and value.startswith("\\\\?\\"):
        value = value[4:]
    return Path(os.path.normpath(value))


def _identity(path: Path) -> Identity:
    metadata = path.lstat()
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


def _resolve_linked_directory(logical_root: Path) -> tuple[Path, tuple[LinkWitness, ...]]:
    """Follow only the declared root's chain and require an ordinary directory."""

    selected = _lexical_absolute(logical_root)
    current, pending = _path_walk(selected)
    witnesses: list[LinkWitness] = []
    seen: set[str] = set()
    while pending:
        candidate = current / pending.pop(0)
        try:
            metadata = candidate.lstat()
        except FileNotFoundError as exc:
            raise ValueError("E_RUNTIME_SUBROOT_TARGET_INVALID") from exc
        kind = _link_kind(candidate, metadata)
        if kind is not None:
            if len(witnesses) >= MAX_LINK_DEPTH:
                raise ValueError("E_RUNTIME_SUBROOT_TARGET_INVALID")
            key = os.path.normcase(str(candidate))
            if key in seen:
                raise ValueError("E_RUNTIME_SUBROOT_TARGET_INVALID")
            seen.add(key)
            try:
                raw_target = os.readlink(candidate)
            except OSError as exc:
                raise ValueError("E_RUNTIME_SUBROOT_TARGET_INVALID") from exc
            witnesses.append((str(candidate), _identity(candidate), raw_target, kind))
            current, pending = _path_walk(
                _link_target(candidate, raw_target).joinpath(*pending)
            )
            continue
        if pending:
            if not stat.S_ISDIR(metadata.st_mode):
                raise ValueError("E_RUNTIME_SUBROOT_TARGET_INVALID")
            current = candidate
            continue
        if not stat.S_ISDIR(metadata.st_mode):
            raise ValueError("E_RUNTIME_SUBROOT_TARGET_INVALID")
        return candidate, tuple(witnesses)
    raise ValueError("E_RUNTIME_SUBROOT_TARGET_INVALID")


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
    ) -> "LinkedRuntimeSubrootAuthority | None":
        selected = _lexical_absolute(logical_root)
        kind = _logical_leaf_link_kind(selected)
        if kind is None:
            return None
        trusted = tuple(_lexical_absolute(path) for path in trusted_global_roots)
        if scope != "global" or not any(_same_path(selected, path) for path in trusted):
            raise ValueError("E_RUNTIME_SUBROOT_SCOPE_DENIED")
        resolved_root, link_chain = _resolve_linked_directory(selected)
        return cls(
            logical_root=selected,
            logical_identity=_identity(selected),
            resolved_root=resolved_root,
            resolved_identity=_identity(resolved_root),
            link_chain=link_chain,
            trusted_global_roots=trusted,
        )

    def assert_current(self) -> None:
        current = self.bind(
            self.logical_root,
            scope="global",
            trusted_global_roots=self.trusted_global_roots,
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
