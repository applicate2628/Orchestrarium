# N31 MoM Cylinder Analytic Oracle

`N31` hardens the scientific/numerical lane with a computational electromagnetics task.
The worker must repair a Method of Moments solver for a two-dimensional TMz plane wave
incident on a perfectly conducting circular cylinder.

The numerical method is pulse-basis, point-matched MoM for the single-layer EFIE on the
cylinder boundary. The analytic oracle is the exact cylindrical-harmonic series for the
same PEC circular cylinder.

The verifier checks a real numerical solve:

- independent boundary residual from the candidate surface-current density
- exterior field samples against the analytic cylindrical-harmonic oracle
- convergence from coarse to refined segment counts
- hidden non-default radius, wavenumber, and incidence angle
- report and validation-note integrity
- runtime

Validation flow:

```powershell
python verifiers/check_mom_cylinder_solver.py --bundle-shape-only
python verifiers/check_mom_cylinder_solver.py --expect-start-state
python verifiers/check_mom_cylinder_solver.py
python verifiers/check_scope.py --changed-path candidate/workspace/mom_solver.py --changed-path candidate/workspace/validation-report.json --changed-path candidate/workspace/validation-notes.md
```
