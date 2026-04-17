# S20 Platform Engineer Observability Patch

`S20` benchmarks `R20 $platform-engineer` on a bounded observability repair. The scored task is to
correct bundle-local collector and deployment config so the release telemetry contract becomes
coherent again without widening into backend code, toolchain ownership, shared runners, provider
routing, or results surfaces.

## Scenario summary

The mutable candidate root contains a small platform-owned observability workspace whose start state
still points at legacy endpoints and scrape settings:

- the collector scrapes `/healthz` instead of `/metrics`
- the metrics pipeline skips the `resource` processor before batching
- both the collector and the deployment still point at legacy OTLP endpoints
- platform resource attributes still identify the release as `control-plane`
- the deployment annotation and resource attributes no longer match the admitted staging contract

## Expected candidate work

Edit only the files listed in `scenario.yaml`:

- `candidate/platform-owned/observability/collector-config.yaml`
- `candidate/platform-owned/deploy/release-api-observability.yaml`

Use the immutable packet in `inputs/` and keep all other files unchanged. The intended local
validation route after the patch is `python scripts/validate_observability_patch.py` from
`candidate/platform-owned/`.

## What this bundle tests

- platform-owned observability and deployment wiring rather than backend instrumentation work
- config repair through the owning seam instead of edits to runners, routing, or stale summaries
- bounded implementation discipline for a general platform role
- authorable local validation for a config patch bundle

## Bundle map

- `inputs/` holds the immutable task contract, owner map, observability targets, and failing notes
- `candidate/` is the mutable run root copied for each execution
- `oracle/` defines the required repair shape, forbidden widening paths, and scoring anchors
- `verifiers/` contains bundle-shape, start-state, completed-run, and scope checks
