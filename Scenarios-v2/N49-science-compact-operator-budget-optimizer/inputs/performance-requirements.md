# Performance Requirements

The verifier measures wall-clock runtime inside each solver call and compares it with candidate-reported runtime. Reporting a lower runtime than the measured wall-clock value cannot hide slow code.

The candidate should avoid dense full-spectrum eigenvalue solves for the radial Schrodinger problem. Use a selected tridiagonal method. For EM, avoid per-observation recomputation of the full system matrix.
