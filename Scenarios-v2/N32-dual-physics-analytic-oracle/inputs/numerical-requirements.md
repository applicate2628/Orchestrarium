# Numerical Requirements

Performance is part of the task, not an optional polish item. Implement the fastest correct
algorithm you can within NumPy/SciPy:

- vectorize geometry, quadrature, and field evaluation where practical
- precompute reusable panel geometry and quadrature nodes
- solve the dense MoM system directly only at the requested moderate sizes
- use the tridiagonal structure of the radial Schrodinger Hamiltonian
- do not build a dense radial Hamiltonian for the hydrogenic solver
- do not use symbolic math or analytical wavefunction formulas inside the candidate solver

## Required APIs

`solve_cylinder_mom(...)`:

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

Return keys:

- `domain`
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

`solve_hydrogen_radial(...)`:

```python
solve_hydrogen_radial(
    z: float,
    n: int,
    l: int,
    r_max: float,
    grid_points: int,
    sample_r: list[float],
) -> dict
```

Return keys:

- `domain`
- `z`
- `n`
- `l`
- `r_max`
- `grid_points`
- `method`
- `energy`
- `r_grid`
- `u_grid`
- `normalization`
- `residual_l2`
- `sample_values`
- `runtime_seconds`

Complex values must be encoded as `{"re": ..., "im": ...}`.
