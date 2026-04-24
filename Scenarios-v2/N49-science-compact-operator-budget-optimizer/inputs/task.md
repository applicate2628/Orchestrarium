# Task

Repair the high-load dual physics optimizer and its staged delivery artifacts with a compact operator-facing closeout.

You are in the bundle root. Edit only:

- `candidate/stage-state.json`
- `candidate/optimization-report.json`
- `candidate/workspace/dual_physics.py`
- `candidate/workspace/perf-ledger.json`
- `candidate/workspace/validation-notes.md`

Do not edit inputs, oracle files, verifiers, candidate README, or workspace tests.

## Operator-output budget

This is a scoreable low-noise scientific optimizer lane. Keep the visible worker output in `../meta/worker-output.txt` at or below 40000 bytes.

Do not paste full solver code, raw transcripts, full matrices, long derivations, broad directory listings, or repeated test output into the visible response. The accepted closeout should report the changed files, the physics validation result, the runtime result, the staged-artifact status, and any residual risk.

## Required phases

Complete these phases in `candidate/stage-state.json`:

1. `01-diagnose-baseline`: record the seeded solver defects and baseline performance risk.
2. `02-implement-fast-solvers`: repair the EM and hydrogenic solvers.
3. `03-optimize-scale`: document scaling measurements for the high-load cases.
4. `04-closeout-report`: tie the final report and notes to the measured solver outputs.

Each phase entry must name its owner, status, source cues, affected artifacts, and visible return cue.

## Numerical requirements

The EM solver must solve TMz scattering by a PEC circular cylinder with a pulse-basis Method of Moments discretization of the EFIE using the outgoing Green function. The verifier validates boundary residuals, sampled total fields, and surface density Fourier coefficients against the analytical circular-cylinder solution.

The hydrogenic solver must solve the finite-difference radial Schrodinger equation on a uniform grid using a fast tridiagonal method. The verifier validates energy, normalized radial function, and residual against the analytical hydrogenic oracle.

Do not call analytical special-function oracles from candidate code to construct the returned answers. The verifier scans for forbidden oracle markers.

## Performance requirement

Correctness alone is insufficient. The repaired code must pass per-case runtime budgets and must write a `perf-ledger.json` containing the measured case IDs, runtime budgets, scaling notes, and the exact phase IDs.

The local smoke test is intentionally smaller than the verifier:

```powershell
python candidate/workspace/tests/test_dual_physics.py
```
