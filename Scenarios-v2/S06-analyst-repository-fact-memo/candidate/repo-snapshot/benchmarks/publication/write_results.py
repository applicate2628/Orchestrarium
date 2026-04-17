from benchmarks.registry.score_profiles import get_profile


def build_result_row(record, total_score: int) -> dict[str, object]:
    weights = get_profile(record.score_profile)
    return {
        "scenario_id": record.id,
        "surface_id": record.surface_id,
        "score_profile": record.score_profile,
        "artifact_type": record.artifact_type,
        "weight_total": sum(weights.values()),
        "total_score": total_score,
    }
