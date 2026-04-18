ROUTING_BASIS = {
    "review.security": ("S27", "N05", "N06"),
    "review.performance-architecture": ("S26", "S28", "N07"),
}


def resolve_lane(scenario_id: str) -> str:
    for lane_name, scenario_ids in ROUTING_BASIS.items():
        if scenario_id in scenario_ids:
            return lane_name
    return "unassigned"
