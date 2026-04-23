# Task

You are acting as a computational physics specialist for a benchmark release gate.

Repair the dual physics workspace:

- `candidate/workspace/dual_physics.py`
- `candidate/workspace/validation-report.json`
- `candidate/workspace/validation-notes.md`

The final solution must numerically solve both domains:

1. TMz scattering by a PEC circular cylinder using pulse-basis Method of Moments.
2. Hydrogenic radial Schrodinger bound states using a fast finite-difference tridiagonal solver.

The analytical oracles are validation references only. Do not return analytical samples as the
numerical solution. Do not use symbolic math. Do not use analytical hydrogenic wavefunction
generators in candidate code.

Speed is scoreable. Correct but slow algorithms should lose rubric points and may fail hard runtime
caps on hidden cases. The hydrogenic Hamiltonian is tridiagonal; using a dense eigensolver is the
wrong algorithm for the target sizes.

`validation-report.json` must include:

```json
{
  "method": "dual numerical physics: MoM PEC cylinder plus tridiagonal hydrogenic radial solver",
  "oracle_use": "analytical cylindrical-harmonic and hydrogenic formulas used only for validation",
  "cases": [],
  "performance": {},
  "convergence": {}
}
```

`validation-notes.md` must mention these phrases:

- Method of Moments
- PEC circular cylinder
- TMz EFIE
- outgoing Green function
- surface density Fourier coefficients
- finite-difference radial Schrodinger
- tridiagonal Hamiltonian
- hydrogenic analytical oracle
- solver runtime
- convergence

Keep edits inside the allowed change surface from `scenario.yaml`.
