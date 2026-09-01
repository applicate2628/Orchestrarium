import json
from pathlib import Path

from routing_matrix.lane_basis import ROUTING_BASIS, resolve_lane
from routing_matrix.lane_catalog import ROUTE_GROUPS

HISTORY = []


def parse_simple_yaml(path: Path) -> dict:
    data = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        data[key.strip()] = raw_value.strip().strip('"')
    return data


def collect_lane_members(scenarios_root: Path, lane_name: str) -> list[dict]:
    members = []
    for scenario_dir in scenarios_root.iterdir():
        scenario_path = scenario_dir / "scenario.yaml"
        if not scenario_path.exists():
            continue
        metadata = parse_simple_yaml(scenario_path)
        if resolve_lane(metadata["id"]) == lane_name:
            members.append(metadata)
    return members


def build_lane_cards(scenarios_root: Path) -> list[dict]:
    cards = []
    for group in ROUTE_GROUPS:
        members = collect_lane_members(scenarios_root, group["lane"])
        cards.append(
            {
                "lane": group["lane"],
                "label": group["label"],
                "basis_count": len(ROUTING_BASIS[group["lane"]]),
                "snapshot": json.dumps(members),
            }
        )
    return cards


def record_snapshot(cards: list[dict]) -> list[str]:
    HISTORY.append(json.dumps(cards))
    return HISTORY
