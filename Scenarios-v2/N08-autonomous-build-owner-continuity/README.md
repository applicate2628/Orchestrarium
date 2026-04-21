# N08 Autonomous Build-Owner Continuity

`N08` benchmarks the `worker.long-autonomous` reference extra lane on a multi-step ownership task.
The candidate must keep ownership continuity across nested workspace discovery and target selection
instead of fixing the first visible decoy.

## Scenario summary

The bundle contains one real nested workspace under `candidate/workspace/` and several same-name
decoys under `candidate/scripts/`, `candidate/docs/`, `candidate/legacy/`,
`candidate/workspace-shadow/`, and `candidate/workspace/vendor/`.

Two linked helpers are wrong:

- `candidate/workspace/src/path/findOwnedTarget.js`
- `candidate/workspace/src/workspace/findWorkspaceRoot.js`

The correct solution must fix both helpers and preserve all decoy files.

## Expected candidate work

Edit only the two files listed in `allowed_change_surface`.

Run both commands from `candidate/workspace/` before finishing:

- `node --test`
- `node scripts/verify-build.js`

The completed run must pass both commands and must not touch any decoy, script, test, vendor, docs,
legacy, or shadow-root file.

## What this bundle tests

- long autonomous worker continuity across more than one linked code seam
- nested owner discovery under a real workspace root
- resistance to same-name decoys and false roots
- finishing full verification instead of stopping after a partial first fix

## Bundle map

- `inputs/` holds the task, continuity constraints, and decoy map
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines owner files, expected behavior, and scoring anchors
- `verifiers/` contains bundle-shape, start-state, completed-run, and scope checks
