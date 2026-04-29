from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StageRequest:
    artifact_id: str
    channel: str
    source_hash: str
    features: tuple[str, ...] = ()
    env_tokens: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    priority: int = 0
    source: str = "unknown"
    workspace: str = "/workspace"


@dataclass
class StageState:
    active_leases: set[str] = field(default_factory=set)
    cache: set[str] = field(default_factory=set)
    ledger: list[dict] = field(default_factory=list)
