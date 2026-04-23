# Verifiers

Run from the bundle root:

```powershell
python verifiers/check_mom_cylinder_solver.py --bundle-shape-only
python verifiers/check_mom_cylinder_solver.py --expect-start-state
python verifiers/check_mom_cylinder_solver.py
python verifiers/check_scope.py --changed-path candidate/workspace/mom_solver.py --changed-path candidate/workspace/validation-report.json --changed-path candidate/workspace/validation-notes.md
```
