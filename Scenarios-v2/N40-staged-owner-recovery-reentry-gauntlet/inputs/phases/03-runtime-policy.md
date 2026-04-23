# Phase 03 - Runtime Policy

Allowed edits:

- `candidate/source-ledger.json`
- `candidate/runtime-policy.json`

Record runtime policy:

- run order: top-pair `X1,X3` first for `N38,N39,N40`
- calibration: `X2` after top-pair; `X5/X6` only if route health is useful
- X4: `NOT-RUN`
- quota, route failure, wrapper timeout, tool-loop, and missing summary are runtime caveats, not
  model semantic failures
- scoreable fail requires completed wrapper plus verifier/semantic failure evidence
