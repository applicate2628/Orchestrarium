# Task: Fast MoM Repeated-RHS Cylinder Solver

The starter `candidate/workspace/dual_physics.py` has a single-angle midpoint MoM cylinder solver
and a hydrogenic radial solver from earlier scientific probes. Keep the hydrogenic solver valid, but
this task's separator is the real electromagnetic batch path.

Implement `solve_cylinder_batch_mom(radius, wavenumber, segments, incident_angles, observation_radius, sample_angles)`.

Requirements:

- Solve the PEC circular-cylinder TMz EFIE numerically with Method of Moments. Do not call the
  analytical Mie-series oracle in candidate code.
- Assemble the MoM matrix once per geometry/frequency and reuse the factorization for all incident
  angles in the batch.
- Return one solution per incident angle with density coefficients/samples, boundary residual,
  field samples, and runtime metadata.
- Preserve `solve_cylinder_mom` and `solve_hydrogen_radial` correctness from the previous dual
  physics oracle.
- Update `candidate/stage-state.json`, `candidate/optimization-report.json`,
  `candidate/workspace/perf-ledger.json`, and `candidate/workspace/validation-notes.md`.
- Keep worker output under the visible operator budget: `../meta/worker-output.txt <= 40000` bytes.

The verifier checks hidden repeated-RHS MoM batches against a Mie-series analytical oracle, validates
single-case EM/hydrogen regressions, checks exact scope, and scores runtime. Passing only the visible
starter test is not enough.
