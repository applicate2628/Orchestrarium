from benchmarks.publication.write_results import build_result_row
from benchmarks.registry.scenario_catalog import ScenarioRecord


def test_result_row_uses_record_score_profile():
    record = ScenarioRecord(
        id="S06",
        surface_id="R06",
        score_profile="owner, advisory, factual, design, planning",
        artifact_type="factual research memo",
        modality_family="repository investigation",
        bundle_root=None,
    )

    row = build_result_row(record, total_score=88)

    assert row["score_profile"] == "owner, advisory, factual, design, planning"
    assert row["weight_total"] == 100
