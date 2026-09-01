# Performance Requirements

The hard part is repeated RHS reuse, not merely vectorized formatting.

- `batch-ka11-angles16`: 224 panels, 16 incident angles, all solutions under 6.5 seconds.
- `batch-ka14-angles12`: 320 panels, 12 incident angles, all solutions under 9.0 seconds.
- Total measured batch runtime must stay under 13.0 seconds on the verifier host.
- The candidate should reuse LU/factorization or an equivalent multi-RHS solve instead of rebuilding
  or refactorizing the matrix for each incident angle.
