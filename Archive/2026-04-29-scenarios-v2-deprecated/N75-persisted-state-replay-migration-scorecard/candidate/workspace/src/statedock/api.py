import json

from .store import StateStore


def replay_events(events):
    store = StateStore()
    return store.replay(events)


def save_snapshot(path, snapshot):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, sort_keys=True)


def load_snapshot(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)
