# Inputs

This directory is the immutable evidence packet for `S12`.

## Included materials

- `task.md` defines the benchmark task and the required output contract
- `system-overview.md` gives the component map and data flow (`E1`)
- `trust-boundary-hints.md` identifies the expected boundary candidates (`E2`)
- `auth-flow-notes.md` records the planned credential and identity flow (`E3`)
- `sensitive-data-map.md` classifies the data that crosses the system (`E4`)
- `incident-observations.md` captures synthetic dry-run observations that must shape the control set
  (`E5`)

The evidence is intentionally dense. A generic "least privilege and encrypt everything" answer will
miss the specific trust boundaries, control obligations, and must-fix issues this scenario expects.
