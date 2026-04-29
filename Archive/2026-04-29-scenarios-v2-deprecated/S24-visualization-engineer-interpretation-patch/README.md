# S24 Visualization Engineer Interpretation Patch

`S24` benchmarks `R24 $visualization-engineer` on a bounded visualization-semantics repair. The
scored task is to correct signed anomaly interpretation, depth-axis orientation, and missing-sample
encoding in a bundle-local section-spec builder without drifting into graphics-pipeline, Qt,
model-view, scorer, or shared benchmark surfaces.

## Scenario summary

The mutable candidate root contains a tiny deterministic section-spec generator with three
start-state interpretation bugs:

- negative anomalies are encoded with warm tokens and a non-zero-centered scale
- deeper samples are placed above shallow samples by an inverted depth axis
- missing samples are backfilled as neutral cells instead of explicit gaps

The bundle uses textual visualization specs in JSON rather than screenshots, GUI fixtures, or
shared render harnesses.

## Expected candidate work

Edit only the files listed in `scenario.yaml`:

- `candidate/visualization-owned/src/visualization_owned/anomaly_section.py`
- `candidate/visualization-owned/tests/test_anomaly_section.py`

Use the immutable packet in `inputs/` to preserve interpretation semantics, encoding thresholds,
and bundle boundaries. The expected local validation flow after a repair is:

1. run `python tests/test_anomaly_section.py` from `candidate/visualization-owned/`
2. run `python verifiers/run_visualization_checks.py` from the bundle root
3. use `python verifiers/check_scope.py --changed-path ...` to confirm the diff stayed in bounds

## What this bundle tests

- signed, zero-centered visualization interpretation instead of graphics-pipeline blending
- depth-orientation and gap semantics for a scientific or data visualization surface
- scope discipline for a specialty implementation role
- validation without screenshots, Qt fixtures, model/view plumbing, or scorer edits

## Bundle map

- `inputs/` holds the immutable task contract, interpretation brief, boundary notes, start-state
  observations, and deterministic section cases
- `candidate/` is the mutable run root copied for each execution
- `oracle/` defines the bundle contract, expected encodings, widening prohibitions, and scoring
  anchors
- `verifiers/` contains bundle-shape, start-state, completed-run, and scope checks
