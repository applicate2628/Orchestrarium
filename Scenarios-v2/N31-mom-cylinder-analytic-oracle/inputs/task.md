# Task

You are acting as a computational electromagnetics specialist for a benchmark release-gate subsystem.

## Goal

Repair the Method of Moments solver and produce validation artifacts for the PEC circular-cylinder
TMz benchmark.

Update only:

- `candidate/workspace/mom_solver.py`
- `candidate/workspace/validation-report.json`
- `candidate/workspace/validation-notes.md`

## Required behavior

- solve the single-layer EFIE for a circular PEC cylinder using pulse-basis MoM
- use the outgoing Green function `i/4 H_0^(1)(kR)`
- include panel arc length in every matrix entry
- handle self panels through quadrature over the panel
- solve the complex dense linear system for the surface density
- return density values for every panel
- compute exterior field samples by integrating the returned density
- validate against the analytic cylindrical-harmonic oracle, not by returning that oracle as the solution
- show convergence from `segments = 64` to `segments = 96`
- support nonzero incidence angle and hidden geometry/wavenumber probes

## Validation report contract

`candidate/workspace/validation-report.json` must be valid JSON with this shape:

```json
{
  "method": "pulse-basis MoM for PEC cylinder TMz EFIE",
  "oracle_use": "cylindrical-harmonic series only as validation oracle",
  "cases": [
    {
      "case_id": "ka2-primary-coarse",
      "radius": 0.5,
      "wavenumber": 4.0,
      "segments": 64,
      "incident_angle": 0.35,
      "observation_radius": 2.0,
      "relative_field_error": 0.008,
      "boundary_residual_l2": 0.01,
      "runtime_seconds": 1.0
    }
  ],
  "convergence": {
    "coarse_case_id": "ka2-primary-coarse",
    "refined_case_id": "ka2-primary-refined",
    "field_error_improvement_ratio": 1.2
  }
}
```

Use actual values from the repaired solver; the numbers above are bounds, not exact required values.

## Notes contract

`candidate/workspace/validation-notes.md` must explain:

- Method of Moments
- PEC circular cylinder
- TMz EFIE
- outgoing Green function
- pulse basis and point matching
- self-panel quadrature
- complex linear system
- cylindrical-harmonic analytic oracle
- convergence
- hidden nonzero incidence angle support

## Disallowed behavior

- do not edit files outside the allowed surface
- do not edit the oracle, verifier, task, or input files
- do not hard-code the analytic field samples
- do not use the analytic cylindrical-harmonic series as the returned MoM solution
- do not drop the diagonal or self-panel contribution
- do not ignore the incident angle
- do not add dependencies beyond NumPy and SciPy, which are already available in this benchmark runtime
