# Candidate Surface

Only these files are editable:

- `candidate/workspace/mom_solver.py`
- `candidate/workspace/validation-report.json`
- `candidate/workspace/validation-notes.md`

Run the local smoke test after editing:

```powershell
python candidate/workspace/tests/test_mom_solver.py
```

Then run the verifier from the bundle root:

```powershell
python verifiers/check_mom_cylinder_solver.py
```
