Date: 2026-04-20
Owner: `$lead`
Status: `PASS`

## Scope

This evidence admits `N08..N10` as the materialized `worker.long-autonomous` reference extra-lane
slice.

It is intentionally separate from the core `12` routing-lane result surface:

- core live surface: `S01..S33 + N01..N07`
- extra reference lane: `E1 worker.long-autonomous`
- extra reference scenarios: `N08`, `N09`, `N10`
- `X4` is not scored here because the secret-backed Claude route is currently unavailable

## Local fixture validation

| Check | Result |
|---|---|
| `N08` bundle shape | `PASS` |
| `N08` expected broken start-state | `PASS` |
| `N08` control-pass overlay | `PASS` |
| `N09` bundle shape | `PASS` |
| `N09` expected broken start-state | `PASS` |
| `N09` control-pass overlay | `PASS` |
| `N10` bundle shape | `PASS` |
| `N10` expected broken start-state | `PASS` |
| `N10` control-pass overlay | `PASS` |

## Run roots

| Row | Root |
|---|---|
| `X1` | `benchmarks/.scratch/v2-cohort-runs/2026-04-20_00-59-01-X1-x1-n08-n10-2026-04-20/` |
| `X2` | `benchmarks/.scratch/v2-cohort-runs/2026-04-20_00-59-02-X2-x2-n08-n10-2026-04-20/` |
| `X3` | `benchmarks/.scratch/v2-cohort-runs/2026-04-20_00-59-01-X3-x3-n08-n10-2026-04-20/` |
| `X4` | `benchmarks/.scratch/v2-cohort-runs/2026-04-20_00-59-02-X4-x4-secret-n08-n10-2026-04-20/` |
| `X4` retry | `benchmarks/.scratch/v2-cohort-runs/2026-04-20_01-09-35-X4-x4-secret-n08-n10-retry1-2026-04-20/` |
| `X5` | `benchmarks/.scratch/v2-cohort-runs/2026-04-20_00-59-01-X5-x5-n08-n10-2026-04-20/` |
| `X6` | `benchmarks/.scratch/v2-cohort-runs/2026-04-20_00-59-01-X6-x6-n08-n10-2026-04-20/` |

## Extra-lane result matrix

| Row | Label | `N08` | `N09` | `N10` | Scoreable read | Notes |
|---|---|---|---|---|---|---|
| `X3` | `opus 4.7max` | `PASS` | `PASS` | `PASS` | `3 / 3` | clean extra-lane sweep |
| `X1` | `gpt-5.4` | `PASS` | `PASS` | `PASS` | `3 / 3` | clean extra-lane sweep |
| `X5` | `gemini3.1pro` | `PASS` | `PASS` | `PASS` | `3 / 3` | clean verifier read; transcript noise after completion is not a verifier failure |
| `X6` | `gemini3.1flash-lite-preview` | `PASS` | `FAIL` | `PASS` | `2 / 3` | `N09` failed the null-continuity case by returning `docs/project-mirror` instead of `null` |
| `X2` | `gpt-spark` | `FAIL` | `PASS` | `FAIL` | `1 / 3` | `N08` and `N10` produced no changed benchmark paths; output was only an acknowledgement/readiness response |
| `X4` | `Claude China` | `NOT-RUN` | `NOT-RUN` | `NOT-RUN` | `0 / 0` | both secret-backed attempts returned `502 unknown provider for model claude-opus-4-7`; excluded from scoreable denominator |

## Per-scenario verifier evidence

| Row | Scenario | Wrapper | Changed paths | Verifier read |
|---|---|---:|---:|---|
| `X1` | `N08` | `0` | `2` | `check_long_autonomous_build_owner.py=0`; `check_scope.py=0` |
| `X1` | `N09` | `0` | `1` | `check_autonomous_resume_path_recall.py=0`; `check_scope.py=0` |
| `X1` | `N10` | `0` | `3` | `check_constrained_multi_step_patch.py=0`; `check_scope.py=0` |
| `X2` | `N08` | `0` | `0` | `check_long_autonomous_build_owner.py=1`; `check_scope.py=0` |
| `X2` | `N09` | `0` | `1` | `check_autonomous_resume_path_recall.py=0`; `check_scope.py=0` |
| `X2` | `N10` | `0` | `0` | `check_constrained_multi_step_patch.py=1`; `check_scope.py=0` |
| `X3` | `N08` | `0` | `2` | `check_long_autonomous_build_owner.py=0`; `check_scope.py=0` |
| `X3` | `N09` | `0` | `1` | `check_autonomous_resume_path_recall.py=0`; `check_scope.py=0` |
| `X3` | `N10` | `0` | `3` | `check_constrained_multi_step_patch.py=0`; `check_scope.py=0` |
| `X5` | `N08` | `0` | `2` | `check_long_autonomous_build_owner.py=0`; `check_scope.py=0` |
| `X5` | `N09` | `0` | `1` | `check_autonomous_resume_path_recall.py=0`; `check_scope.py=0` |
| `X5` | `N10` | `0` | `3` | `check_constrained_multi_step_patch.py=0`; `check_scope.py=0` |
| `X6` | `N08` | `0` | `2` | `check_long_autonomous_build_owner.py=0`; `check_scope.py=0` |
| `X6` | `N09` | `0` | `1` | `check_autonomous_resume_path_recall.py=1`; `check_scope.py=0` |
| `X6` | `N10` | `0` | `3` | `check_constrained_multi_step_patch.py=0`; `check_scope.py=0` |

## X4 deferred read

`X4` must use the secret-backed Claude route. Both `N08..N10` attempts on that route produced the
same provider-side message:

```text
API Error: 502 unknown provider for model claude-opus-4-7. This is a server-side issue, usually temporary - try again in a moment.
```

Per the quota/runtime rule, this is not a model `FAIL`. It is `NOT-RUN` until the route recovers
and produces a clean attempt.

## Interpretation

| Read | Decision |
|---|---|
| extra-lane admission | `N08..N10` are real scoreable fixtures for `worker.long-autonomous` |
| core lane count | unchanged at `12` |
| extra lane count | `1` reference extra lane: `E1 worker.long-autonomous` |
| strongest extra-lane rows | `X3`, `X1`, and `X5`, each `3 / 3` |
| partial extra-lane rows | `X6` at `2 / 3`; `X2` at `1 / 3` |
| deferred row | `X4`, route unavailable, `0 / 0` scoreable |
