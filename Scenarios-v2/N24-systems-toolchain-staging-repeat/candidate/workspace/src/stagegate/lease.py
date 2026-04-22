from __future__ import annotations


def acquire(state, artifact_id: str):
    state.active_leases.add(artifact_id)


def release(state, artifact_id: str):
    state.active_leases.discard(artifact_id)
