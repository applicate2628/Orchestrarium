from benchmarks.runner.collect_scenarios import SCENARIO_ROOT, load_scenarios_for_surface


def test_loader_targets_v2_root():
    assert SCENARIO_ROOT.name == "Scenarios-v2"


def test_loader_returns_only_matching_surface():
    records = load_scenarios_for_surface("R06")
    assert [record.id for record in records] == ["S06"]


def test_archive_index_is_not_the_runtime_root():
    assert "archive" not in str(SCENARIO_ROOT)
