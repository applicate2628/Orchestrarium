"""Unit tests for Phase-0 harness item H6 (repeated-run variance policy + aggregator).

Run: python -m pytest Work/next-upgraded-pack/Tooling/tests/test_aggregate_cell_verdicts.py -q

Covers: each cell-verdict class on synthetic run triplets (unanimous-P/F, majority-P/F with an
explained divergent run, UNSTABLE from an unexplained divergent run, UNSTABLE from graded-score
spread, NR from insufficient scoreable runs), tiering/escalation helpers, graded-score median +
min/max aggregation, the C4 lane-abstention rule, and emission of both I5 tables (2-way provider
read, 4-way profile table) including the I6 ASSUMPTION labels on systemic-mgmt/working-audit.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

TOOLING = Path(__file__).resolve().parents[1]


def _load_module():
    path = TOOLING / "aggregate-cell-verdicts.py"
    spec = importlib.util.spec_from_file_location("aggregate_cell_verdicts", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


acv = _load_module()


def _runs(scenario_id, profile, lane, verdicts, **kwargs):
    """Build a triplet (or N-tuple) of RunRecords from a list of "P"/"F"/"NR" strings, with optional
    per-index overrides for graded_score / explanation via kwargs of lists (same length as verdicts)."""
    graded = kwargs.get("graded_scores")
    explanations = kwargs.get("explanations")
    family = kwargs.get("family")
    out = []
    for i, v in enumerate(verdicts):
        out.append(acv.RunRecord(
            scenario_id=scenario_id,
            profile=profile,
            lane=lane,
            run_index=i,
            verdict=v,
            graded_score=(graded[i] if graded else None),
            explanation=(explanations[i] if explanations else None),
            family=family,
        ))
    return out


# ---------------------------------------------------------------------------------------------------
# Cell verdict classes on synthetic run triplets

def test_unanimous_pass():
    runs = _runs("N-A", "stamina", "L05", ["P", "P", "P"])
    cell = acv.compute_cell_verdict(runs)
    assert cell.verdict == "unanimous-P"
    assert cell.resolved_pf == "P"
    assert cell.n_scoreable == 3


def test_unanimous_fail():
    runs = _runs("N-A", "stamina", "L05", ["F", "F", "F"])
    cell = acv.compute_cell_verdict(runs)
    assert cell.verdict == "unanimous-F"
    assert cell.resolved_pf == "F"


def test_majority_pass_explained_divergence():
    runs = _runs("N-B", "ultimate-depth", "L04", ["P", "P", "F"],
                  explanations=[None, None, "documented cause: transient sandbox timeout, retried clean"])
    cell = acv.compute_cell_verdict(runs)
    assert cell.verdict == "majority-P"
    assert cell.resolved_pf == "P"
    assert any("explained" in n for n in cell.notes)


def test_majority_fail_explained_divergence():
    runs = _runs("N-B", "ultimate-depth", "L04", ["F", "F", "P"],
                  explanations=[None, None, "documented cause: candidate got a lucky partial credit"])
    cell = acv.compute_cell_verdict(runs)
    assert cell.verdict == "majority-F"
    assert cell.resolved_pf == "F"


def test_unstable_unexplained_divergence():
    runs = _runs("N-C", "working-audit", "L11", ["P", "P", "F"])  # no explanation on the F run
    cell = acv.compute_cell_verdict(runs)
    assert cell.verdict == "UNSTABLE"
    assert cell.resolved_pf is None
    assert any("unexplained" in n for n in cell.notes)


def test_unstable_graded_score_spread_overrides_unanimous_pf():
    # All three runs pass discretely, but the graded scores disagree beyond threshold -- H6:
    # "UNSTABLE (unexplained 2/3 or graded-score spread beyond threshold)".
    runs = _runs("N-D", "systemic-mgmt", "L00", ["P", "P", "P"], graded_scores=[0.95, 0.55, 0.90])
    cell = acv.compute_cell_verdict(runs, graded_spread_threshold=0.15)
    assert cell.verdict == "UNSTABLE"
    assert cell.resolved_pf is None
    assert cell.graded["spread"] == pytest.approx(0.4)
    assert any("spread" in n for n in cell.notes)


def test_graded_score_spread_within_threshold_stays_unanimous():
    runs = _runs("N-D2", "systemic-mgmt", "L00", ["P", "P", "P"], graded_scores=[0.92, 0.88, 0.90])
    cell = acv.compute_cell_verdict(runs, graded_spread_threshold=0.15)
    assert cell.verdict == "unanimous-P"
    assert cell.graded["median"] == 0.90


def test_nr_insufficient_scoreable_runs():
    runs = _runs("N-E", "working-audit", "L11", ["NR", "NR", "P"])
    cell = acv.compute_cell_verdict(runs)
    assert cell.verdict == "NR"
    assert cell.resolved_pf is None
    assert cell.n_scoreable == 1


def test_nr_zero_scoreable_runs():
    runs = _runs("N-F", "working-audit", "L11", ["NR", "NR"])
    cell = acv.compute_cell_verdict(runs)
    assert cell.verdict == "NR"
    assert cell.n_scoreable == 0


# ---------------------------------------------------------------------------------------------------
# Tiering + escalation helpers

def test_classify_tier_a_for_discriminator_and_anchor_and_phase3():
    assert acv.classify_tier(is_discriminator=True, is_phase3_family=False, is_anchor_slot=False) == "A"
    assert acv.classify_tier(is_discriminator=False, is_phase3_family=True, is_anchor_slot=False) == "A"
    assert acv.classify_tier(is_discriminator=False, is_phase3_family=False, is_anchor_slot=True) == "A"


def test_classify_tier_b_default():
    assert acv.classify_tier(is_discriminator=False, is_phase3_family=False, is_anchor_slot=False) == "B"


def test_tier_b_escalates_on_non_pass():
    assert acv.needs_escalation(tier="B", first_run_verdict="F", feeds_published_lane_read=False) is True


def test_tier_b_escalates_when_feeding_published_lane():
    assert acv.needs_escalation(tier="B", first_run_verdict="P", feeds_published_lane_read=True) is True


def test_tier_b_no_escalation_when_p_and_unpublished():
    assert acv.needs_escalation(tier="B", first_run_verdict="P", feeds_published_lane_read=False) is False


def test_tier_a_never_needs_escalation_call():
    assert acv.needs_escalation(tier="A", first_run_verdict="F", feeds_published_lane_read=True) is False


# ---------------------------------------------------------------------------------------------------
# Graded-score aggregation

def test_aggregate_graded_scores_median_and_spread():
    agg = acv.aggregate_graded_scores([0.4, 0.9, 0.6])
    assert agg == {"median": 0.6, "min": 0.4, "max": 0.9, "spread": 0.5}


def test_aggregate_graded_scores_empty_is_none():
    assert acv.aggregate_graded_scores([]) is None


# ---------------------------------------------------------------------------------------------------
# C4 lane abstention rule

def _cell(scenario_id, profile, lane, verdict, resolved_pf, family=None):
    return acv.CellResult(
        scenario_id=scenario_id, family=family or scenario_id, profile=profile, lane=lane,
        verdict=verdict, resolved_pf=resolved_pf, tier="A", n_scoreable=3, graded=None,
    )


def test_lane_abstains_below_two_discriminating_families():
    # One family only, and it is not even discriminating (both profiles pass) -> ABSTAIN.
    cells = [
        _cell("N-X", "stamina", "L07", "unanimous-P", "P"),
        _cell("N-X", "ultimate-depth", "L07", "unanimous-P", "P"),
    ]
    status = acv.compute_lane_status(cells)
    assert status["L07"]["status"] == "ABSTAIN"
    assert status["L07"]["discriminating_families"] == []


def test_lane_publishable_with_two_discriminating_families():
    cells = [
        _cell("N-Y1", "stamina", "L07", "unanimous-P", "P"),
        _cell("N-Y1", "ultimate-depth", "L07", "unanimous-F", "F"),
        _cell("N-Y2", "stamina", "L07", "majority-F", "F"),
        _cell("N-Y2", "ultimate-depth", "L07", "unanimous-P", "P"),
    ]
    status = acv.compute_lane_status(cells)
    assert status["L07"]["status"] == "PUBLISHABLE"
    assert sorted(status["L07"]["discriminating_families"]) == ["N-Y1", "N-Y2"]


def test_lane_family_grouping_collapses_two_scenarios_into_one_family():
    # N98/N105-style: two scenario ids, one visual family -- must count as ONE family, not two.
    cells = [
        _cell("N98", "stamina", "L12", "unanimous-P", "P", family="visual-fam-1"),
        _cell("N105", "stamina", "L12", "unanimous-P", "P", family="visual-fam-1"),
        _cell("N98", "ultimate-depth", "L12", "unanimous-F", "F", family="visual-fam-1"),
        _cell("N105", "ultimate-depth", "L12", "unanimous-F", "F", family="visual-fam-1"),
        # a second, independent family needed to reach the >=2 threshold
        _cell("N-OTHER", "stamina", "L12", "unanimous-P", "P"),
        _cell("N-OTHER", "ultimate-depth", "L12", "unanimous-F", "F"),
    ]
    status = acv.compute_lane_status(cells)
    assert status["L12"]["stable_family_count"] == 2
    assert status["L12"]["status"] == "PUBLISHABLE"


def test_lane_eligible_profiles_excludes_owner_lane_profiles():
    # L00 owner-lane exclusion (S2): ultimate-depth is NOT eligible here, so its (only) verdict must
    # not count toward discrimination even though it disagrees with stamina.
    cells = [
        _cell("N17", "stamina", "L00", "unanimous-P", "P"),
        _cell("N17", "ultimate-depth", "L00", "unanimous-F", "F"),
        _cell("N-OTHER2", "stamina", "L00", "unanimous-P", "P"),
        _cell("N-OTHER2", "ultimate-depth", "L00", "unanimous-F", "F"),
    ]
    status = acv.compute_lane_status(
        cells, eligible_profiles={"N17": ["stamina"], "N-OTHER2": ["stamina"]})
    # Only stamina is eligible on both families -> each family has exactly one eligible resolved
    # value -> neither family discriminates -> ABSTAIN despite four raw cells disagreeing.
    assert status["L00"]["status"] == "ABSTAIN"


# ---------------------------------------------------------------------------------------------------
# I5 dual-consumer tables + I6 labels

def _build(cells):
    lane_status = acv.compute_lane_status(cells)
    four_way = acv.build_four_way_table(cells, lane_status)
    two_way = acv.build_two_way_table(four_way, lane_status)
    return lane_status, four_way, two_way


def test_four_way_table_reports_pass_fraction_per_profile():
    cells = [
        _cell("N-Y1", "systemic-mgmt", "L02", "unanimous-P", "P"),
        _cell("N-Y1", "stamina", "L02", "unanimous-P", "P"),
        _cell("N-Y1", "ultimate-depth", "L02", "unanimous-F", "F"),
        _cell("N-Y1", "working-audit", "L02", "unanimous-F", "F"),
        _cell("N-Y2", "systemic-mgmt", "L02", "unanimous-F", "F"),
        _cell("N-Y2", "stamina", "L02", "unanimous-F", "F"),
        _cell("N-Y2", "ultimate-depth", "L02", "unanimous-P", "P"),
        _cell("N-Y2", "working-audit", "L02", "unanimous-P", "P"),
    ]
    _, four_way, _ = _build(cells)
    rows_by_profile = {r["profile"]: r for r in four_way if r["lane"] == "L02"}
    assert set(rows_by_profile) == {"systemic-mgmt", "stamina", "ultimate-depth", "working-audit"}
    assert rows_by_profile["stamina"]["read"] == "1/2"
    assert rows_by_profile["ultimate-depth"]["read"] == "1/2"
    assert rows_by_profile["stamina"]["provider"] == "claude"
    assert rows_by_profile["ultimate-depth"]["provider"] == "codex"
    assert not rows_by_profile["stamina"]["abstained"]  # L02 is PUBLISHABLE (2 discriminating families)


def test_four_way_table_labels_unmeasurable_profiles_i6():
    cells = [_cell("N-Z", "systemic-mgmt", "L00", "unanimous-P", "P")]
    cells[0].telemetry_citation = "meta/telemetry.json: costUsd=0.42, wallClockMs=18300"
    _, four_way, _ = _build(cells)
    row = four_way[0]
    assert row["profile"] == "systemic-mgmt"
    assert "ASSUMPTION (UNVERIFIED)" in row["label"]
    assert "costUsd" in row["label"]


def test_four_way_table_no_label_for_measurable_profiles():
    cells = [_cell("N-Z2", "stamina", "L05", "unanimous-P", "P")]
    _, four_way, _ = _build(cells)
    assert "label" not in four_way[0]


def test_two_way_table_picks_best_profile_per_provider_and_orders():
    cells = [
        _cell("N-Y1", "systemic-mgmt", "L06", "unanimous-P", "P"),
        _cell("N-Y1", "stamina", "L06", "unanimous-F", "F"),
        _cell("N-Y1", "ultimate-depth", "L06", "unanimous-F", "F"),
        _cell("N-Y1", "working-audit", "L06", "unanimous-F", "F"),
        _cell("N-Y2", "systemic-mgmt", "L06", "unanimous-P", "P"),
        _cell("N-Y2", "stamina", "L06", "unanimous-F", "F"),
        _cell("N-Y2", "ultimate-depth", "L06", "unanimous-F", "F"),
        _cell("N-Y2", "working-audit", "L06", "unanimous-F", "F"),
    ]
    _, four_way, two_way = _build(cells)
    row = next(r for r in two_way if r["lane"] == "L06")
    # claude's best profile is systemic-mgmt (2/2) beating stamina (0/2); codex is 0/2 either profile.
    assert row["claude_representative"] == "systemic-mgmt"
    assert row["order"] == "claude > codex"
    assert row["status"] == "PUBLISHABLE"
    assert any("ASSUMPTION" in lbl for lbl in row["labels"])  # systemic-mgmt representative carries I6


def test_two_way_table_abstained_lane_is_marked():
    cells = [
        _cell("N-SOLO", "stamina", "L09", "unanimous-P", "P"),
        _cell("N-SOLO", "ultimate-depth", "L09", "unanimous-P", "P"),
    ]
    _, four_way, two_way = _build(cells)
    row = next(r for r in two_way if r["lane"] == "L09")
    assert row["status"] == "ABSTAIN"


def test_two_way_table_insufficient_data_when_a_provider_has_no_stable_cells():
    cells = [
        _cell("N-ONLY", "stamina", "L03", "unanimous-P", "P"),
    ]
    _, four_way, two_way = _build(cells)
    row = next(r for r in two_way if r["lane"] == "L03")
    assert row["order"] == "insufficient-data"


# ---------------------------------------------------------------------------------------------------
# aggregate_cells: grouping flat run records into cells end-to-end

def test_aggregate_cells_groups_by_scenario_and_profile():
    runs = (
        _runs("N-G", "stamina", "L05", ["P", "P", "P"])
        + _runs("N-G", "ultimate-depth", "L05", ["F", "F", "P"],
                explanations=[None, None, "documented cause"])
    )
    cells = acv.aggregate_cells(runs)
    by_profile = {c.profile: c for c in cells}
    assert by_profile["stamina"].verdict == "unanimous-P"
    assert by_profile["ultimate-depth"].verdict == "majority-F"
