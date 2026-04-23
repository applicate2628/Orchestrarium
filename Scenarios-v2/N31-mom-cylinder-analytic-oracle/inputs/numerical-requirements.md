# Numerical Requirements

Implement a Method of Moments solve for the PEC cylinder EFIE.

Required method:

- use constant pulse basis functions on equal angular panels
- collocate at panel centers
- include panel arc length in the integral
- handle the weak logarithmic self-panel behavior by panel quadrature, not by dropping the diagonal
- solve the full complex linear system
- return the complex boundary density on every panel
- compute exterior total-field samples from the returned density
- compare coarse and refined segment counts for convergence

Required solver API:

```python
solve_cylinder_mom(
    radius: float,
    wavenumber: float,
    segments: int,
    incident_angle: float,
    observation_radius: float,
    sample_angles: list[float],
) -> dict
```

The returned dictionary must include:

- `radius`
- `wavenumber`
- `segments`
- `incident_angle`
- `observation_radius`
- `method`
- `panel_angles`
- `density`
- `boundary_residual_l2`
- `field_samples`
- `runtime_seconds`

Encode complex numbers in JSON-compatible objects:

```json
{"re": 1.0, "im": -0.5}
```

Disallowed shortcuts:

- do not return the analytic cylindrical-harmonic field as if it were a MoM result
- do not drop the self term or set the diagonal to zero
- do not omit the panel arc length
- do not assume `incident_angle = 0`
- do not hard-code the public radius, wavenumber, segment counts, or sample pattern
