# S21 Toolchain Ownership Patch

`S21` benchmarks `R21 $toolchain-engineer` on a bounded build-and-packaging repair. The scored task
is to correct the package contract at the toolchain seam without widening into runtime source,
legacy runners, fixture roots, or platform-owned deployment surfaces.

## Scenario summary

The mutable workspace in `candidate/` contains a small package bundle whose toolchain-owned
metadata still points at `build/` outputs and carries legacy references to a runner script and a
`T29` fixture root. The runtime source is already correct. The candidate must repair the workspace
validation command, the bundle plan, and the package manifest so the package contract becomes a
clean `dist/`-based bundle again.

## Expected candidate work

Edit only the files listed in `scenario.yaml`:

- `candidate/workspace/package.json`
- `candidate/workspace/toolchain/bundle-plan.json`
- `candidate/workspace/packages/scenario-bundle/package.json`

Use the immutable task packet in `inputs/` and keep all other files unchanged. The intended local
validation route after the patch is `node toolchain/package-bundle.mjs` from
`candidate/workspace/`.

## What this bundle tests

- owner-seam discipline for toolchain work
- packaging and build-graph correctness without runtime code edits
- removal of legacy runner and `T29` fixture leakage from editable metadata only
- local validation behavior for an implementation-class bundle

## Bundle map

- `inputs/` holds the immutable task contract, ownership guidance, and failing validation snapshot
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the ground-truth patch, forbidden widening paths, and scoring anchors
- `verifiers/` contains the local bundle checker and post-run validation helper
