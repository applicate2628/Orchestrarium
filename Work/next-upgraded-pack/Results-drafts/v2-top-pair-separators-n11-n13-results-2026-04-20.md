Date: 2026-04-20
Owner: `$lead`
Status: `PASS`

## Result

`E2 top-pair-separator` was materialized and run twice for `X1` and `X3`: initial gates and
hardened2 gates.

The result is still a tie.

| Row | Label | Initial E2 | Hardened2 E2 | Current read |
|---|---|---:|---:|---|
| `X1` | `gpt-5.4` | `3 / 3` | `3 / 3` | passes E2 cleanly |
| `X3` | `opus 4.7max` | `3 / 3` | `3 / 3` | passes E2 cleanly |

## Scenario Matrix

| Scenario | Purpose | `X1` | `X3` |
|---|---|---|---|
| `N11` | architecture evidence conflict ADR | `PASS` | `PASS` |
| `N12` | source-truth conflict fact memo | `PASS` | `PASS` |
| `N13` | adversarial review false-positive traps | `PASS` | `PASS` |

## Interpretation

| Question | Current answer |
|---|---|
| Can `N11..N13` rank `X1` vs `X3`? | No. Both pass all hardened gates. |
| Does this invalidate the full-v2 ranking? | No. The full expanded v2 surface still has `X3` above `X1` by completed scoreable rows. |
| What should be used for routing today? | Use the existing full-v2 and hardened core-12 reads; do not promote E2 into `externalPriorityProfiles`. |
| What is the next honest separator if needed? | Add non-binary quality/rubric scoring or a new task family instead of more keyword-only hardening. |

## Source

| Source | Role |
|---|---|
| `../Evidence/x1-x3-top-pair-separators-n11-n13-2026-04-20.md` | run roots, hardening delta, and execution evidence |
| `v2-core12-tie-hardened-results-2026-04-20.md` | reason this diagnostic overlay was needed |
