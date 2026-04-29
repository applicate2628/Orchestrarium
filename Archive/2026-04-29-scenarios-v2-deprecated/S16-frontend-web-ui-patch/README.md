# S16 Frontend Web UI Patch

`S16` benchmarks `R16 $frontend-engineer` on a bounded browser UI repair. The scored task is to
patch a bundle-local release board so its loading, success, empty, and error states become
accessible and locally verifiable without widening into backend, Qt, platform, or scorer surfaces.

## Scenario summary

The mutable workspace in `candidate/` contains a small browser-capable release-readiness board. The
preview wiring, fixtures, and local verification scripts are already present, but the editable UI
files still render broken state messaging, non-semantic filter controls, stale error content, and
missing keyboard-focus treatment.

## Expected candidate work

Edit only the files listed in `scenario.yaml`:

- `candidate/workspace/src/dashboard.js`
- `candidate/workspace/src/ui-copy.js`
- `candidate/workspace/src/dashboard.css`

Use the immutable task packet in `inputs/` and keep all other files unchanged. The intended local
validation route after the patch is `node scripts/verify-ui-contract.mjs` from
`candidate/workspace/`, and the browser preview route is `node scripts/static-server.mjs`.

## What this bundle tests

- bounded frontend ownership on a web-only UI patch
- user-visible loading, success, empty, and error state repair
- accessibility-sensitive labels, live regions, pressed states, and focus treatment
- local verification discipline for an implementation-class browser bundle

## Bundle map

- `inputs/` holds the immutable task contract, UI-state requirements, and failing browser notes
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the ground-truth UI contract, forbidden widening paths, and scoring anchors
- `verifiers/` contains the local bundle checker and post-run validation helper
