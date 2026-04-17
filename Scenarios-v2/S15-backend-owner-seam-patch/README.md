# S15 Backend Owner-Seam Patch

`S15` benchmarks `R15 $backend-engineer` on a bounded backend repair. The scored task is to fix a
bundle-local session-window builder so preview-session grants obey revocation, expiry, and
deduplication rules without widening into platform, data, API-contract, or toolchain surfaces.

## Scenario summary

The mutable backend root contains a tiny deterministic helper used by a preview-share API. Its
start state is intentionally wrong in ways that matter for backend ownership:

- revoked preview sessions still survive in the returned window
- sessions expiring exactly at the cutoff timestamp remain active
- duplicate grants for one user keep the oldest expiry instead of the newest active session

The fix must stay inside the backend-owned module and its direct test file only.

## Expected candidate work

Edit only the files listed in `scenario.yaml`:

- `candidate/backend-owned/src/backend_owned/session_window.py`
- `candidate/backend-owned/tests/test_session_window.py`

Use the immutable packet in `inputs/` to preserve the owner seam and boundary rules. The expected
local validation flow after a repair is:

1. run `python tests/test_session_window.py` from `candidate/backend-owned/`
2. run `python verifiers/run_backend_checks.py` from the bundle root
3. use `python verifiers/check_scope.py --changed-path ...` to confirm the diff stayed in bounds

## What this bundle tests

- owner-seam discipline for backend code
- revocation, expiry, and deduplication correctness
- protection against widening into platform, data, API-contract, or toolchain surfaces
- local validation behavior for an implementation-class backend bundle

## Bundle map

- `inputs/` holds the immutable task contract, boundary notes, request cases, and start-state read
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the bundle contract, expected windows, widening prohibitions, and scoring
  anchors
- `verifiers/` contains bundle-shape, start-state, completed-run, and scope checks
