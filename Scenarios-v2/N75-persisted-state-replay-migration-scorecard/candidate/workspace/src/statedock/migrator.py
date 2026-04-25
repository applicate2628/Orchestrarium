from .events import normalize_event


def migrate_events(events):
    return [normalize_event(event) for event in events]
