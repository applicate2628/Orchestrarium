Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

This is the first archived benchmark baseline snapshot.

It preserves the admitted benchmark state as it existed on 2026-04-16, including:

- full and short result tables
- checkpoint and method documents needed to interpret those tables
- admitted evidence syntheses
- provider wrapper and helper tooling referenced by the archive

## Snapshot layout

| Path | Purpose |
|---|---|
| `Results/` | frozen result surfaces |
| `Method/` | benchmark design, notation, governance, and benchmark-policy docs |
| `Checkpoints/` | combined baselines, intermediate checkpoints, status, and research context |
| `Evidence/runs/` | admitted run syntheses that support the snapshot |
| `Tooling/provider-mcp-templates/` | provider wrapper scripts and helper files referenced by the benchmark record |

## Immutability note

This snapshot should be treated as archived baseline state.

New upgraded packs should not mutate this package.
If future evidence changes the accepted ranking, archive that as a new dated snapshot instead.
