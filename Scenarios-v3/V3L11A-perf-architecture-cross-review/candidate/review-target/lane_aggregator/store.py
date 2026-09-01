import json


class LaneStore:
    """Resolves an item id to its lane using a prebuilt index.

    NOTE: __init__ reparses the whole config file and rebuilds the full lane
    index every time an instance is constructed.
    """

    def __init__(self, config_path):
        raw = _read_config(config_path)
        self._index = _build_lane_index(raw)

    def resolve_lane(self, item_id):
        return self._index.get(item_id, "unassigned")


def _read_config(config_path):
    with open(config_path, encoding="utf-8") as handle:
        return json.load(handle)


def _build_lane_index(raw):
    index = {}
    for lane, members in raw.get("lanes", {}).items():
        for member in members:
            index[member] = lane
    return index
