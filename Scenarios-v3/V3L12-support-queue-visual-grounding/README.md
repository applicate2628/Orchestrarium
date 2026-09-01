# V3L12 Support Queue Visual Grounding

`V3L12-support-queue-visual-grounding` is the F4 independent L12 raster family
(BUILD-PLAN-v2.1.md Phase 3, item F4): a second calibrated visual-review separator for L12
(`review.ui-visual-correctness`), authored so the L12 lane read no longer rests on one shared
oracle. The worker receives one support-ticket triage console screenshot and must return exact
seeded visual defects with component names, defect classes, severity labels, and approximate pixel
coordinates.

This bundle is deliberately independent of the other two L12 families:

- **N98** (`Scenarios-v2/N98-visual-regression-diff-review`) is a baseline-vs-current diff review of
  a release/incident dashboard.
- **N80** (`Scenarios-v2/N80-screenshot-grounding-review-v2`) is a single-screenshot review of a
  different release/incident dashboard. F4's oracle *shape* (exact-tuple findings,
  `pass_min_matched` 8/10, threshold 80/100, 22px tolerance, `falsePositiveTerms`,
  `requiredNonFindings`) is modeled on N80's per BUILD-PLAN-v2.1.md, but the *scene* is new: a
  support-ticket triage console, not a release/incident dashboard.
- **N21/N48** share one procedurally-rendered raster fixture (`inputs/panel-cases.json` fed through
  `visual_panel.renderer.render_panel`). F4 does not read that file and does not import
  `visual_panel.renderer`; its screenshot is drawn independently by
  `Work/next-upgraded-pack/Tooling/generate-v3l12-support-queue-assets.py`.

md5 disjointness against all four fixtures (N98 baseline/current, the preserved N105 baseline/current,
and the N21/N48 shared render, both as the raw `panel-cases.json` bytes and as the actual rendered
pixel bytes) is recorded in `Work/next-upgraded-pack/Evidence/f4-l12-raster-disjointness/manifest.json`.

## Expected Candidate Work

Edit only `candidate/answer.json`.

The result must be JSON. The verifier reads the JSON and checks:

- exactly ten returned findings, with at least the configured pass-threshold matched to seeded defects
- component and defect terms bound to the seeded oracle
- coordinates inside a 22px accepted tolerance window
- severity labels present for every finding
- no false-positive findings on intentional visual states and traps

## What This Bundle Tests

- actual screenshot grounding under dense UI context, on a scene independent of every other L12
  fixture
- small UI defect localization with calibrated pixel tolerance
- visual review without relying on DOM/source prose
- false-positive discipline on visually plausible but intentional UI states
- output discipline under a strict JSON contract

## discrimination.yaml

`target_construct`, `eligible_profiles`, and the pre-registered `expected_winner` hypothesis for the
4-profile instrument are declared in `discrimination.yaml` per BUILD-PLAN-v2.1.md item S2. The
hypothesis is registered before any target-model run against this bundle.
