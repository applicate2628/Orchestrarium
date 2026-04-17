from pathlib import Path

import yaml

from benchmarks.registry.scenario_catalog import ScenarioRecord

SCENARIO_ROOT = Path(__file__).resolve().parents[1] / "Scenarios-v2"


def load_scenarios_for_surface(surface_id: str) -> list[ScenarioRecord]:
    records: list[ScenarioRecord] = []

    for metadata_path in sorted(SCENARIO_ROOT.glob("*/scenario.yaml")):
        raw = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
        if raw.get("surface_id") != surface_id:
            continue

        records.append(
            ScenarioRecord.from_metadata(
                raw,
                bundle_root=metadata_path.parent,
            )
        )

    return records
