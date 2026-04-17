from pathlib import Path

import yaml

ARCHIVE_INDEX = Path(__file__).resolve().parents[1] / "archive" / "scenario_index_v1.yaml"


def load_archive_rows() -> list[dict]:
    raw = yaml.safe_load(ARCHIVE_INDEX.read_text(encoding="utf-8"))
    return raw["scenarios"]
