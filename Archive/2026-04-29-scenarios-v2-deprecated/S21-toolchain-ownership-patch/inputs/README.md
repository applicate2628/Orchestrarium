# Inputs

This directory is the immutable packet for the `S21` toolchain scenario. It provides the scoped
implementation task, the owner map, and the package contract the candidate must satisfy.

## Included materials

- `task.md` defines the benchmark task and the allowed edit surface
- `owner-map.md` separates toolchain-owned files from runtime and legacy reference material
- `expected-artifact-contract.md` describes the repaired package contract
- `failing-validation.md` records the starting validation failures
- `legacy-reference-note.md` explains how prior `T29` ideas may be referenced without becoming the
  canonical scenario identity

These inputs are toolchain-specific. A generic implementation answer that widens into application
code, platform deployment, or legacy fixture editing should lose scope-discipline points.
