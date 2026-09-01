# Scoring Anchors

Binary gate. PASS requires ALL of:

1. Bundle shape and scenario.yaml metadata match the contract exactly.
2. The four required sections are present; `## Gate Decision` contains `REVISE`.
3. The findings table header matches exactly and the row count is exactly 4.
4. Every row's Category and Severity are in the allowed sets; Line is an integer.
5. Each of F1-F4 matches a DISTINCT row (file + acceptable line + exact severity + category term +
   title keyword + all required evidence terms).
6. No row Title matches a forbidden trap (D1/D2/D3).
7. `## False Positives Avoided` names `known_lanes`, `backoff`, and `build stamp`.
8. No prohibited snippet (`ship it`, `looks fine`, `lgtm`) appears.

## Why this separates near-peer strong reviewers

- Missing F2 (the quadratic hidden in the comprehension) -> row count 3 or a missing required finding -> FAIL.
- Flagging a decoy (tuple->set, import read, backoff) -> forbidden match or wrong count -> FAIL.
- Reporting F1 without tracing into store.py (no `config`/rebuild evidence) -> F1 row does not match -> FAIL.
- Padding with a real-but-out-of-scope style nit -> row count 5 -> FAIL.

A top reviewer lands exactly 4 real findings and rejects exactly 3 decoys; a near-peer reviewer trips
one of the gates above. Difficulty alone is not the discriminator; the exact-set + trap discipline is.
