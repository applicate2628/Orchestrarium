from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BuildRequest:
    target: str
    profile: str
    source_hash: str
    features: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    priority: int = 0
    source: str = "unknown"
    workspace: str = "/workspace"


@dataclass
class BuildState:
    active_locks: set[str] = field(default_factory=set)
    cache: set[str] = field(default_factory=set)
    ledger: list[dict] = field(default_factory=list)
