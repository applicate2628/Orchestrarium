# Inputs

This directory is the immutable evidence packet for `S13`.

## Included materials

- `task.md` defines the benchmark task and required output contract
- `system-and-workload-brief.md` describes the packager stages, fixture sizes, and admitted use
  (`E1`)
- `baseline-timing-and-resource-traces.md` records cold-run and warm-run timing plus memory traces
  (`E2`)
- `bottleneck-probe-notes.md` captures stage-level profiler and resource observations (`E3`)
- `budget-envelope.md` defines the target latency and memory envelope (`E4`)
- `tradeoff-boundaries.md` states the non-negotiable boundaries and out-of-scope moves (`E5`)

The packet is intentionally specific. A generic "cache more and parallelize" answer will miss the
required budgets, the dominant bottlenecks, the measurement plan, and the tradeoff boundaries that
this scenario expects.
