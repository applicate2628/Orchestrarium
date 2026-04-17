# Scoring Anchors

## Strong pass signals

- the patch stays inside the three editable toolchain files
- the validation route becomes `node toolchain/package-bundle.mjs`
- `build/` references disappear from the repaired package contract
- `main`, `bin`, `exports`, and `files` all align on `dist`
- no editable file keeps `T29` or legacy runner references

## Common misses

- fixing only the package manifest while leaving the bundle plan or workspace script stale
- editing runtime files or the validator script instead of metadata
- preserving `dist` in one file but leaving `build` in another
- pulling legacy runner or fixture paths back into the repaired metadata

## Scoring emphasis

`S21` uses the implementation profile, so correctness and scope discipline dominate. Role fidelity
depends on staying inside toolchain ownership and validating the package contract without drifting
into product-code or platform work.
