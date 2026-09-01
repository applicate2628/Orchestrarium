# N71 mutation gate (R7 / B5)

Scorer-private, immutable snapshots that let the verifier certify a candidate's mandated
regression test (`tests/test_window_regression.py`) actually **detects each required defect
class**, not just the one historical buggy baseline.

## Why (the closed confound)

The old gate ran the candidate test against a single buggy baseline. That baseline broke two
things at once (user isolation **and** retry_after), so a test that asserts only the obvious
symptom (denial + retry_after) fails the baseline and gets certified while never testing
same-tenant/different-user isolation or the window boundary. One buggy baseline certifies a
defect-missing test. The **mutant matrix** — one targeted mutant per required defect class —
closes that: a test that misses a class passes that class's mutant and is caught.

## Layout

| Path | Role |
|---|---|
| `fixed/flowlimit/` | complete correct reference package (test must PASS here) |
| `buggy/flowlimit/` | complete shipped start-state package (both defects; test must FAIL) |
| `mutants/<id>/flowlimit/limiter.py` | fixed package with EXACTLY one defect class reintroduced (overlay) |
| `reference-test/` | strong reference test — PASSES the gate (four-probe #1) |
| `probes/vacuous/` | keyword-stuffed, assertion-padded, content-free — FAILS the gate (#2) |
| `probes/decoy/` | plausible but incomplete (denial+retry_after only) — FAILS the gate (#3) |
| `MANIFEST.json` | machine-readable package name, test filename, and defect-class registry |

## Defect-class matrix

| mutant id | defect reintroduced | detected only by a test that... |
|---|---|---|
| `isolation` | key drops `user_id` (users share a tenant+route budget) | asserts a 2nd user keeps an independent budget |
| `retry-after` | denial reports the full window, not the remaining seconds | asserts the exact `retry_after` value |
| `boundary` | off-by-one buckets an exact-boundary timestamp into the previous window | asserts an exact-boundary request is allowed |

## Verdict contract

For the candidate's mandated test (read from the oracle-free exec root
`$BENCH_EXEC_ROOT`, else the bundle root):

1. **PASS-on-fixed** is a precondition. If the test does not cleanly pass on `fixed/` the
   gate is **not-satisfiable** (abstain) — never a model-quality F.
2. The test must **FAIL on `buggy/` and on every mutant**, and the failure must be the
   **expected assertion** (a failing test node raising `AssertionError`). A variant the test
   merely passes ⇒ `mutation-<id>-undetected`; a variant it only crashes on (non-assertion)
   ⇒ `mutation-<id>-not-asserted`.
3. **Collection / import / no-tests / infra failures ⇒ `not-satisfiable`**, a distinct code
   that counts as neither pass nor fail-certification.

The gate **augments** the existing static term/assert floor and hidden-behavior checks; those
remain as a floor and are never weakened.

## Isolation

Each variant runs in a fresh disposable temp root containing only the snapshot package, the
candidate test, and a result-capturing `conftest.py` — **no `oracle/` is ever on the exec
path**, honoring the Phase-0 exec-root invariant.

## Metrics consumer contract

`--metrics-out` gains a `mutation_gate` object (`status` ∈ `pass|fail|not-satisfiable`,
`reason`, `failures`, per-variant `variants`) and a top-level `gate_not_satisfiable` bool.
An aggregator should map `not-satisfiable` to a non-scoreable (NR) mutation-gate dimension,
never to F.

## Reproduce the four-probe validation

```
python verifiers/check_test_led_rate_limit.py --bundle-root . --mutation-selftest
```
Expected: `reference -> pass`, `vacuous -> fail`, `decoy -> fail`.
