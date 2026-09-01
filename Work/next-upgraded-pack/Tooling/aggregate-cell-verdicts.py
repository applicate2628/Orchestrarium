#!/usr/bin/env python3
"""Repeated-run variance policy + cell-verdict aggregator (Phase-0 harness item H6, BUILD-PLAN-v2.1).

A **cell** is scenario x profile. Each cell is run a tiered number of times (Tier A: every
lane-feeding discriminator + every new Phase-3 family + every anchor slot -> 3 repeats always
provisioned; Tier B: historically all-P stable slots -> 1 screening repeat, auto-escalated to 3 on
any non-P result or when the cell feeds a published lane read). This module does not run anything or
decide *how many* repeats to schedule up front -- `classify_tier` / `needs_escalation` are the
scheduling-facing helpers a runner calls before/after dispatch; `compute_cell_verdict` consumes
whatever repeat records it is actually given (post-retry) and reduces them to one of four verdicts:

  * `unanimous-P` / `unanimous-F` -- all scoreable runs agree (the 3/3 case).
  * `majority-P` / `majority-F`   -- 2-of-3 agree AND the divergent run carries a documented
    explanation (an NR-with-cause, a flagged infra fault, etc.); an unexplained divergent run is
    UNSTABLE instead.
  * `UNSTABLE`                    -- an unexplained divergent run, OR a P/F-agreeing cell whose
    graded-score spread exceeds the pre-registered threshold (agreement on the discrete label is
    not itself proof of a stable underlying score).
  * `NR`                          -- fewer than 2 scoreable runs after the caller's one retry
    (verifier crash, quota, route failure, or a Tier-B screen that was never escalated).

I5 (dual-consumer output): `build_four_way_table` emits the profile-native read (systemic-mgmt /
stamina / ultimate-depth / working-audit per lane, over STABLE cells only); `build_two_way_table`
derives the shipped-surface-compatible claude-vs-codex read from it, per lane, by picking each
provider's own best-scoring profile in that lane as its representative -- one aggregator, two
tables, same provenance, per I5's "no per-lane consuming surface yet" for the 4-way side.

I6 (honest measurability labels): `systemic-mgmt` and `working-audit` are not cleanly P/F-measurable
[synthesis]; every table row for those two profiles carries an `ASSUMPTION (UNVERIFIED)`-class label
plus whatever telemetry citation the caller supplied. No pretend-clean P/F.

C4 lane rule (I5's publishability gate): a lane publishes only when >=2 of its scenario "families"
(a family may span more than one scenario id -- e.g. two visual-diff variants of one fixture) are
BOTH stable (>=1 stable cell) AND discriminating (their eligible profiles' resolved verdicts are not
unanimous). Fewer than 2 such families -> the lane ABSTAINs; both I5 tables still report the raw
numbers for diagnostics, tagged `abstained: true` / `status: ABSTAIN`.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

# S1 profile-registry echo (BUILD-PLAN Phase 1 canonical tokens, Terms and Abbreviations: "Profiles").
# Provider ownership is fixed policy (claude hosts systemic-mgmt/stamina, codex hosts
# ultimate-depth/working-audit), not a per-bundle configurable, so it is safe to hardcode here rather
# than depend on the (separately-built, not a dependency of H6) profiles.yaml model-id registry.
PROFILE_PROVIDER: dict[str, str] = {
    "systemic-mgmt": "claude",
    "stamina": "claude",
    "ultimate-depth": "codex",
    "working-audit": "codex",
}
PROFILES: tuple[str, ...] = tuple(PROFILE_PROVIDER)
CLAUDE_PROFILES: tuple[str, ...] = tuple(p for p, prov in PROFILE_PROVIDER.items() if prov == "claude")
CODEX_PROFILES: tuple[str, ...] = tuple(p for p, prov in PROFILE_PROVIDER.items() if prov == "codex")

# I6 -- profiles whose P/F attribution is not cleanly measurable; every read involving them carries
# an ASSUMPTION (UNVERIFIED)-class label plus a telemetry citation.
UNMEASURABLE_PROFILES: frozenset[str] = frozenset({"systemic-mgmt", "working-audit"})

STABLE_VERDICTS: frozenset[str] = frozenset({"unanimous-P", "unanimous-F", "majority-P", "majority-F"})
DEFAULT_GRADED_SPREAD_THRESHOLD = 0.15


@dataclass(frozen=True)
class RunRecord:
    """One repeat of a cell (scenario x profile). Field names loosely mirror the H4 summary.json
    shape this module is designed to sit downstream of: `verdict` is the verifier P/F/NR read,
    `graded_score` an optional 0..1 partial score, `explanation` a documented-cause note for a
    divergent run, `telemetry_citation` an I6 evidence pointer, `family` an optional scenario-family
    grouping key (defaults to `scenario_id` when one scenario is its own family)."""

    scenario_id: str
    profile: str
    lane: str
    run_index: int
    verdict: str  # "P" | "F" | "NR"
    graded_score: float | None = None
    explanation: str | None = None
    family: str | None = None
    telemetry_citation: str | None = None

    @property
    def resolved_family(self) -> str:
        return self.family or self.scenario_id

    @property
    def scoreable(self) -> bool:
        return self.verdict in ("P", "F")


@dataclass
class CellResult:
    scenario_id: str
    family: str
    profile: str
    lane: str
    verdict: str  # unanimous-P | unanimous-F | majority-P | majority-F | UNSTABLE | NR
    resolved_pf: str | None  # "P" | "F" | None for UNSTABLE / NR
    tier: str  # "A" | "B" -- descriptive only; set by the caller, never derived from run outcomes
    n_scoreable: int
    graded: dict | None  # {"median":.., "min":.., "max":.., "spread":..} or None
    telemetry_citation: str | None = None
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------------------------------
# Tiering + escalation (H6 policy, scheduling-facing helpers)

def classify_tier(*, is_discriminator: bool, is_phase3_family: bool, is_anchor_slot: bool) -> str:
    """Tier A: every lane-feeding discriminator + every new Phase-3 family + every anchor slot ->
    always provisioned at 3 repeats. Tier B: everything else (historically all-P stable slots)."""
    return "A" if (is_discriminator or is_phase3_family or is_anchor_slot) else "B"


def needs_escalation(*, tier: str, first_run_verdict: str, feeds_published_lane_read: bool) -> bool:
    """Tier B's 1-repeat screen auto-escalates to 3 on any non-P result or when the cell feeds a
    published lane read. Tier A cells are already provisioned at 3 and never need this call."""
    if tier != "B":
        return False
    return first_run_verdict != "P" or feeds_published_lane_read


# ---------------------------------------------------------------------------------------------------
# Cell verdict (H6 policy)

def aggregate_graded_scores(scores: Sequence[float]) -> dict | None:
    """Graded scores aggregate as median with min/max spread reported (H6)."""
    if not scores:
        return None
    lo, hi = min(scores), max(scores)
    return {"median": statistics.median(scores), "min": lo, "max": hi, "spread": hi - lo}


def compute_cell_verdict(
    runs: Sequence[RunRecord],
    *,
    tier: str = "A",
    graded_spread_threshold: float = DEFAULT_GRADED_SPREAD_THRESHOLD,
) -> CellResult:
    """Reduce a cell's repeat records to one verdict. `runs` must all share the same
    (scenario_id, profile, lane); this is the aggregation unit H6 calls a cell."""
    if not runs:
        raise ValueError("compute_cell_verdict requires at least one run record")
    scenario_id = runs[0].scenario_id
    profile = runs[0].profile
    lane = runs[0].lane
    family = runs[0].resolved_family
    citation = next((r.telemetry_citation for r in runs if r.telemetry_citation), None)

    scoreable = [r for r in runs if r.scoreable]
    graded = aggregate_graded_scores([r.graded_score for r in runs if r.graded_score is not None])
    notes: list[str] = []

    # NR: fewer than 2 scoreable runs after (the caller's) one retry -- the aggregator does not
    # retry itself, it evaluates the count of the record set it was handed.
    if len(scoreable) < 2:
        return CellResult(scenario_id, family, profile, lane, "NR", None, tier, len(scoreable),
                           graded, citation, notes=["fewer than 2 scoreable runs"])

    pass_count = sum(1 for r in scoreable if r.verdict == "P")
    fail_count = len(scoreable) - pass_count
    total = len(scoreable)

    if total >= 3:
        if pass_count == total or fail_count == total:
            base = "unanimous-P" if pass_count == total else "unanimous-F"
            resolved: str | None = "P" if pass_count == total else "F"
        else:
            majority_pf = "P" if pass_count > fail_count else "F"
            minority_runs = [r for r in scoreable if r.verdict != majority_pf]
            unexplained = [r for r in minority_runs if not r.explanation]
            if unexplained:
                base = "UNSTABLE"
                resolved = None
                notes.append("unexplained divergent run(s): "
                              + ", ".join(f"run {r.run_index}" for r in unexplained))
            else:
                base = f"majority-{majority_pf}"
                resolved = majority_pf
                notes.append("divergent run(s) explained: "
                              + "; ".join(f"run {r.run_index}: {r.explanation}" for r in minority_runs))
    else:
        # total == 2 (a Tier-B screen with exactly one escalation repeat landed, or a retry topped up
        # to exactly 2). H6 names no "2/2 unanimous" bucket -- agreement reads as majority-P/F
        # (screening-tier, short of a 3rd confirming run); disagreement has no derivable majority and
        # is UNSTABLE either way.
        if pass_count == fail_count:
            base = "UNSTABLE"
            resolved = None
            divergent_explained = all(r.explanation for r in scoreable)
            notes.append("2-run split" + (" (explained, still short of a 3rd confirming run)"
                                           if divergent_explained else " (unexplained)"))
        else:
            majority_pf = "P" if pass_count > fail_count else "F"
            base = f"majority-{majority_pf}"
            resolved = majority_pf
            notes.append("2-of-2 agreement (screening tier, not yet 3-repeat confirmed)")

    # Graded-score-spread override: a unanimous/majority P/F read is still UNSTABLE if the graded
    # score spread exceeds threshold -- discrete-label agreement does not prove score stability.
    if base != "UNSTABLE" and graded is not None and graded["spread"] > graded_spread_threshold:
        notes.append(f"graded-score spread {graded['spread']:.3f} exceeds threshold "
                      f"{graded_spread_threshold}")
        base = "UNSTABLE"
        resolved = None

    return CellResult(scenario_id, family, profile, lane, base, resolved, tier, total, graded,
                       citation, notes)


def aggregate_cells(
    runs: Iterable[RunRecord],
    *,
    tiers: dict[tuple[str, str], str] | None = None,
    graded_spread_threshold: float = DEFAULT_GRADED_SPREAD_THRESHOLD,
) -> list[CellResult]:
    """Group flat run records into cells (scenario_id, profile) and reduce each to a CellResult.
    `tiers` optionally maps (scenario_id, profile) -> "A"/"B"; cells absent from the map default to
    Tier A (the safe default -- treat as needing the full 3-repeat confirmation)."""
    tiers = tiers or {}
    by_cell: dict[tuple[str, str], list[RunRecord]] = {}
    for r in runs:
        by_cell.setdefault((r.scenario_id, r.profile), []).append(r)
    results = []
    for (scenario_id, profile), cell_runs in sorted(by_cell.items()):
        tier = tiers.get((scenario_id, profile), "A")
        results.append(compute_cell_verdict(cell_runs, tier=tier,
                                             graded_spread_threshold=graded_spread_threshold))
    return results


# ---------------------------------------------------------------------------------------------------
# C4 lane publishability (>=2 stable independent discriminating families, else ABSTAIN)

def compute_lane_status(
    cells: Sequence[CellResult],
    *,
    eligible_profiles: dict[str, Sequence[str]] | None = None,
) -> dict[str, dict]:
    """eligible_profiles maps scenario_id -> allowed profile tokens (S2 discrimination.yaml echo,
    e.g. the L00 owner-lane Terra/Luna exclusion); a scenario absent from the map is eligible on all
    four profiles. Returns lane -> {status, stable_family_count, discriminating_families}."""
    eligible_profiles = eligible_profiles or {}
    by_lane: dict[str, list[CellResult]] = {}
    for c in cells:
        by_lane.setdefault(c.lane, []).append(c)

    status: dict[str, dict] = {}
    for lane, lane_cells in by_lane.items():
        by_family: dict[str, list[CellResult]] = {}
        for c in lane_cells:
            by_family.setdefault(c.family, []).append(c)

        discriminating_families = []
        stable_family_count = 0
        for fam, fam_cells in by_family.items():
            stable_in_family = [
                c for c in fam_cells
                if c.verdict in STABLE_VERDICTS
                and c.profile in set(eligible_profiles.get(c.scenario_id, PROFILES))
            ]
            if not stable_in_family:
                continue
            stable_family_count += 1
            if len({c.resolved_pf for c in stable_in_family}) > 1:
                discriminating_families.append(fam)

        publishable = len(discriminating_families) >= 2
        status[lane] = {
            "status": "PUBLISHABLE" if publishable else "ABSTAIN",
            "stable_family_count": stable_family_count,
            "discriminating_families": sorted(discriminating_families),
        }
    return status


# ---------------------------------------------------------------------------------------------------
# I5 dual-consumer output

def _i6_label(profile: str, telemetry_citation: str | None) -> str | None:
    if profile not in UNMEASURABLE_PROFILES:
        return None
    citation = telemetry_citation or "no telemetry citation on record"
    return (f"ASSUMPTION (UNVERIFIED) -- {profile} attribution is not cleanly P/F-measurable (I6); "
            f"telemetry: {citation}")


def build_four_way_table(cells: Sequence[CellResult], lane_status: dict[str, dict]) -> list[dict]:
    """4-way profile table (I5-b): per lane, per profile, pass fraction over STABLE cells only. No
    per-lane consuming surface exists for this table yet (I5) -- it is built ahead of a future
    per-lane-model-config surface."""
    by_lane_profile: dict[tuple[str, str], list[CellResult]] = {}
    for c in cells:
        by_lane_profile.setdefault((c.lane, c.profile), []).append(c)

    rows = []
    for (lane, profile), lane_profile_cells in sorted(by_lane_profile.items()):
        stable = [c for c in lane_profile_cells if c.verdict in STABLE_VERDICTS]
        passed = sum(1 for c in stable if c.resolved_pf == "P")
        citation = next((c.telemetry_citation for c in lane_profile_cells if c.telemetry_citation), None)
        row = {
            "lane": lane,
            "profile": profile,
            "provider": PROFILE_PROVIDER[profile],
            "stable": len(stable),
            "total": len(lane_profile_cells),
            "passed": passed,
            "read": f"{passed}/{len(stable)}" if stable else "NR",
            "abstained": lane_status.get(lane, {}).get("status") != "PUBLISHABLE",
        }
        label = _i6_label(profile, citation)
        if label:
            row["label"] = label
        rows.append(row)
    return rows


def build_two_way_table(four_way_rows: Sequence[dict], lane_status: dict[str, dict]) -> list[dict]:
    """2-way provider read (I5-a): the real shipped consumer's shape (`Shipped Production Profiles`,
    routing-evidence claude-vs-codex order). Per lane, each provider's own best-scoring profile in
    that lane (by the 4-way read) represents the provider; the two representatives are compared."""
    by_lane: dict[str, list[dict]] = {}
    for row in four_way_rows:
        by_lane.setdefault(row["lane"], []).append(row)

    def _best(lane_rows: list[dict], provider: str) -> dict | None:
        candidates = [r for r in lane_rows if r["provider"] == provider and r["stable"] > 0]
        if not candidates:
            return None
        return max(candidates, key=lambda r: (r["passed"] / r["stable"], r["profile"]))

    rows = []
    for lane, lane_rows in sorted(by_lane.items()):
        claude_rep = _best(lane_rows, "claude")
        codex_rep = _best(lane_rows, "codex")
        row: dict = {"lane": lane, "status": lane_status.get(lane, {}).get("status", "ABSTAIN")}
        if claude_rep is None or codex_rep is None:
            row["order"] = "insufficient-data"
        else:
            claude_frac = claude_rep["passed"] / claude_rep["stable"]
            codex_frac = codex_rep["passed"] / codex_rep["stable"]
            row["claude_representative"] = claude_rep["profile"]
            row["codex_representative"] = codex_rep["profile"]
            if claude_frac > codex_frac:
                row["order"] = "claude > codex"
            elif codex_frac > claude_frac:
                row["order"] = "codex > claude"
            else:
                row["order"] = "near-tie"
            labels = [r["label"] for r in (claude_rep, codex_rep) if r.get("label")]
            if labels:
                row["labels"] = labels
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------------------------------
# CLI (JSON in, JSON reports out) -- integration point for the runner (H1) once it lands.

def _run_record_from_dict(d: dict) -> RunRecord:
    return RunRecord(
        scenario_id=d["scenario_id"],
        profile=d["profile"],
        lane=d["lane"],
        run_index=d["run_index"],
        verdict=d["verdict"],
        graded_score=d.get("graded_score"),
        explanation=d.get("explanation"),
        family=d.get("family"),
        telemetry_citation=d.get("telemetry_citation"),
    )


def run(runs_path: Path, out_dir: Path, *, eligible_profiles_path: Path | None = None,
        tiers_path: Path | None = None) -> int:
    raw = json.loads(runs_path.read_text(encoding="utf-8"))
    runs = [_run_record_from_dict(d) for d in raw]

    tiers = None
    if tiers_path and tiers_path.is_file():
        tiers = {tuple(k.split("::", 1)): v for k, v in
                 json.loads(tiers_path.read_text(encoding="utf-8")).items()}

    eligible = None
    if eligible_profiles_path and eligible_profiles_path.is_file():
        eligible = json.loads(eligible_profiles_path.read_text(encoding="utf-8"))

    cells = aggregate_cells(runs, tiers=tiers)
    lane_status = compute_lane_status(cells, eligible_profiles=eligible)
    four_way = build_four_way_table(cells, lane_status)
    two_way = build_two_way_table(four_way, lane_status)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "cell-verdicts.json").write_text(
        json.dumps([c.__dict__ for c in cells], indent=2, default=str), encoding="utf-8")
    (out_dir / "lane-status.json").write_text(json.dumps(lane_status, indent=2), encoding="utf-8")
    (out_dir / "four-way-profile-table.json").write_text(json.dumps(four_way, indent=2), encoding="utf-8")
    (out_dir / "two-way-provider-table.json").write_text(json.dumps(two_way, indent=2), encoding="utf-8")
    print(f"AGGREGATE-OK: {len(cells)} cells -> {out_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Aggregate repeated-run cell verdicts into the I5 tables.")
    ap.add_argument("--runs", type=Path, required=True, help="JSON list of run records")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--eligible-profiles", type=Path, default=None,
                     help="JSON: scenario_id -> [profile, ...] (S2 discrimination.yaml echo)")
    ap.add_argument("--tiers", type=Path, default=None,
                     help='JSON: "scenario_id::profile" -> "A"|"B"')
    args = ap.parse_args(argv)
    return run(args.runs, args.out_dir, eligible_profiles_path=args.eligible_profiles,
               tiers_path=args.tiers)


if __name__ == "__main__":
    raise SystemExit(main())
