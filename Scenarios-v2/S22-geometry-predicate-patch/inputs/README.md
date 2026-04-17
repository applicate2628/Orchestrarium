# Inputs

This directory is the immutable packet for `S22`. It defines the task contract, the deterministic
failing cases, and the geometry-specific invariants that the candidate must preserve.

## Included materials

- `task.md` defines the benchmark task and the allowed output surface
- `failing-cases.json` captures the three deterministic start-state failures with expected outcomes
- `coordinate-system-notes.md` fixes the coordinate convention and tolerance intent
- `intended-invariants.md` lists the geometric behaviors that must survive the patch

The inputs are intentionally specialty-specific. A generic implementation answer that ignores
tolerance scaling, degeneracy handling, or geometry ownership should lose correctness or scope
points.
