# Scoring Anchors

Binary gate. PASS requires ALL of:

1. Bundle shape and scenario.yaml metadata match the contract exactly.
2. Required sections present; `## Gate Decision` line is `PASS`; no disallowed marker present.
3. `## Confirmed Facts` has exactly 3 rows; each of F1-F3 matches a distinct row cited to
   `config/effective.py` at the exact line with the effective value (5 / 8000 / batch).
4. `## Mis-Cited Sources Rejected` has exactly 3 rows; each of R1-R3 (declared retry, legacy doc,
   declared profile) matches a distinct row that names the effective override as the reason.
5. `## Explicit Unknowns` has exactly 2 rows matching U1-U2.

## Why this separates near-peer strong analysts

- Citing `defaults.py` (value 3 / 2000 / interactive) fails the File and value binding -> missing fact -> FAIL.
- Not rejecting the mis-cited sources -> missing rejected row -> FAIL.
- Asserting the declared value as effective (e.g. "the effective retry limit is 3") -> disallowed marker -> FAIL.

The trap value is plausible (it is literally written in two places); only tracing the override to the
authoritative module answers correctly. This is harder than S06's distractor-file traps, which are
unrelated files rather than a plausible-but-superseded citation of the same value.
