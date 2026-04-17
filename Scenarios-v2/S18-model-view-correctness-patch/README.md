# S18 Model-View Correctness Patch

`S18` benchmarks `R18 $model-view-engineer` on a bounded model/view repair. The scored task is to
fix a bundle-local selection-model helper so filtering, proxy ordering, and fallback selection stay
correct without drifting into Qt UI, graphics, visualization, or scorer surfaces.

## Scenario summary

The mutable model/view root contains a tiny deterministic projection helper with three start-state
bugs:

- hidden rows still appear in the visible model
- proxy ordering ignores row priority and falls back to source order
- when the selected source row is hidden, the detail pane keeps the stale source selection instead
  of falling back to the first visible row

The fix must stay inside the model/view-owned module and its direct test file only.

## Expected candidate work

Edit only the files listed in `scenario.yaml`:

- `candidate/model-view-owned/src/model_view_owned/selection_model.py`
- `candidate/model-view-owned/tests/test_selection_model.py`

Use the immutable packet in `inputs/` to preserve the model/view seam and bundle boundaries. The
expected local validation flow after a repair is:

1. run `python tests/test_selection_model.py` from `candidate/model-view-owned/`
2. run `python verifiers/run_model_view_checks.py` from the bundle root
3. use `python verifiers/check_scope.py --changed-path ...` to confirm the diff stayed in bounds

## What this bundle tests

- model/view filtering and proxy-order discipline
- fallback selection and detail synchronization correctness
- protection against widening into Qt UI, graphics, visualization, or scorer surfaces
- local validation behavior for a specialty implementation bundle

## Bundle map

- `inputs/` holds the immutable task contract, case packet, and start-state read
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the bundle contract, expected view states, widening prohibitions, and scoring
  anchors
- `verifiers/` contains bundle-shape, start-state, completed-run, and scope checks
