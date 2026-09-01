from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Ack:
    revision: int


@dataclass
class State:
    dirty: bool = False
    pending_revision: int | None = None
    last_ack: int | None = None


def apply_ack(state: State, ack: Ack) -> None:
    state.dirty = False
    state.pending_revision = None
    state.last_ack = ack.revision


state = State(dirty=True, pending_revision=40)
state.pending_revision = 41
state.dirty = True
apply_ack(state, Ack(revision=40))

assert state.dirty is True, (
    "stale ack for revision 40 cleared dirty state for pending revision 41"
)
