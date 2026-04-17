from pathlib import Path

import yaml

ROLE_MATRIX = Path(__file__).resolve().parents[1] / "registry" / "role_matrix.yaml"


def export_role_rows() -> list[str]:
    raw = yaml.safe_load(ROLE_MATRIX.read_text(encoding="utf-8"))
    return sorted(raw["roles"])
