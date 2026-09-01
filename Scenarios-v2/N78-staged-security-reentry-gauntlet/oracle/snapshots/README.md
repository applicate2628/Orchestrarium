# N78 staged-security-reentry mutation gate (R7 / B5)

Scorer-private, immutable snapshots that let the verifier certify the candidate's mandated
security regression test (`tests/test_security_regression.py`) actually **detects each
required defect class**, not just the one historical buggy baseline.

## Why (the named confound)

The shipped reference test is named `test_tamper_...` but **never mutates or forges a token** —
it catches the buggy baseline only via user-binding and audit-fingerprint. Against a single
buggy baseline (all defects present at once) it looks like it "detects the bug", so a test
that never actually verifies signature integrity or tenant/resource binding gets certified.
The **mutant matrix** — one targeted mutant per required defect class — closes that hole: the
`integrity`, `tenant-binding`, and `resource-binding` mutants expose exactly what that test
never tested. (The shipped weak test is preserved verbatim as `probes/decoy/` and FAILS the
gate on precisely those three classes.)

## Layout

| Path | Role |
|---|---|
| `fixed/capvault/` | complete correct reference package (test must PASS here) |
| `buggy/capvault/` | complete shipped start-state package (test must FAIL) |
| `mutants/<id>/capvault/<file>` | fixed package with EXACTLY one defect class reintroduced (overlay) |
| `reference-test/` | strong reference test covering all classes — PASSES the gate (#1) |
| `probes/vacuous/` | keyword-stuffed, assertion-padded, content-free — FAILS the gate (#2) |
| `probes/decoy/` | the SHIPPED "tamper"-named test that never forges — FAILS the gate (#3) |
| `MANIFEST.json` | machine-readable package name, test filename, and defect-class registry |

## Defect-class matrix

| mutant id | file | defect reintroduced | detected only by a test that... |
|---|---|---|---|
| `integrity` | `tokens.py` | HMAC signature + alg enforcement removed | forges the token (flip signature bytes / tamper an UNBOUND field like `exp` / submit `alg:none`) and asserts denial — a "tamper" that only mutates a *bound* field is masked by binding and does NOT count |
| `tenant-binding` | `tokens.py` | token tenant no longer bound to expected tenant | authorizes a valid token against a different `expected_tenant` and asserts denial |
| `user-binding` | `tokens.py` | token user no longer bound to expected user | authorizes a valid token against a different `expected_user` and asserts denial |
| `resource-binding` | `tokens.py` | token resource no longer bound to expected resource | authorizes a valid token against a different `expected_resource` and asserts denial |
| `replay` | `tokens.py` | consumed nonces neither recorded nor rejected | authorizes the same token twice with a shared `used_nonces` set and asserts the 2nd is denied |
| `redirect` | `redirects.py` | exact-host check weakened to a substring test | sanitizes a host-suffix / userinfo redirect trap and asserts the fail-closed default |
| `audit-leak` | `audit.py` | audit leaks the raw token and omits the fingerprint | asserts the audit text has a fingerprint and does not contain the raw token/secret |

The `integrity` mutant keeps binding, expiry, and replay intact, so it is caught by an
`alg:none` attack OR by forging the signature / tampering `exp` — honoring the task's
"token tampering OR alg:none" while forcing a real integrity attack rather than a binding test
disguised as a tamper test.

## Verdict contract

For the candidate's mandated test (read from the oracle-free exec root `$BENCH_EXEC_ROOT`,
else the bundle root):

1. **PASS-on-fixed** is a precondition; otherwise the gate is **not-satisfiable** (abstain).
2. The test must **FAIL on `buggy/` and every mutant** via the **expected assertion**
   (a failing node raising `AssertionError`): passes ⇒ `mutation-<id>-undetected`;
   crashes without an assertion ⇒ `mutation-<id>-not-asserted`.
3. **Collection / import / no-tests / infra failures ⇒ `not-satisfiable`** — neither pass nor
   fail-certification.

The gate **augments** the existing static term/assert floor and the hidden runtime exploit
oracle; those remain as a floor and are never weakened.

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
python verifiers/check_security_capability_runtime.py --bundle-root . --mutation-selftest
```
Expected: `reference -> pass`, `vacuous -> fail`, `decoy -> fail`.
