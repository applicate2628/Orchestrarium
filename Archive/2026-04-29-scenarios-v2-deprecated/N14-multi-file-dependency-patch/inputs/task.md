# Task

You are acting as an implementation worker on a bounded benchmark-routing patch.

## Goal

Repair `candidate/workspace/src/routing_eval/` so `build_report(config, attempts)` produces a
correct scoreable row summary across provider-route, runtime, and verifier outcomes.

## Required behavior

- Treat the plural `externalPriorityProfiles` catalog as canonical.
- Treat the singular `externalPriorityProfile` field only as a compatibility selector when no
  explicit active profile is present.
- Keep verifier failures scoreable when the verifier actually ran and produced a local failure.
- Keep route-unavailable, quota, timeout, stdin-deadlock, and missing-worker-output cases
  non-scoreable.
- Compute pass/fail denominators over scoreable rows only.
- Render non-scoreable runtime/route rows as caveats, not as model failures.
- Preserve the public owner API in `src/routing_eval/api.py`.

## Allowed output

Update only:

- `candidate/workspace/src/routing_eval/config.py`
- `candidate/workspace/src/routing_eval/status.py`
- `candidate/workspace/src/routing_eval/scorecard.py`
- `candidate/workspace/src/routing_eval/render.py`
- `candidate/workspace/tests/test_routing_eval.py`

## Disallowed behavior

- do not edit `inputs/`, `oracle/`, or `verifiers/`
- do not edit `src/routing_eval/api.py`
- do not move scoring logic into tests, report formatting only, UI chip labels, or legacy helpers
- do not special-case oracle case IDs or read oracle JSON from candidate code
- do not classify runtime/quota/route failures as model `FAIL`
