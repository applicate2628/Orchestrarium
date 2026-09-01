import os

LANE_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "lane-config.json")

# Fixed set of known lanes. Membership is checked at most once per request.
KNOWN_LANES = ("L00", "L01", "L02", "L03", "L04", "L11")


def _read_build_stamp():
    """Read the build stamp once, at module import time."""
    stamp_path = os.path.join(os.path.dirname(__file__), "BUILD_STAMP.txt")
    if not os.path.exists(stamp_path):
        return "dev"
    with open(stamp_path, encoding="utf-8") as handle:
        return handle.read().strip()


# Evaluated once when the module is first imported, not per request.
BUILD_STAMP = _read_build_stamp()
