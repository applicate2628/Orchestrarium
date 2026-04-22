from __future__ import annotations


def acquire(state, key):
    state.active_locks.add(key)


def release(state, key):
    state.active_locks.discard(key)
