Date: 2026-05-01
Owner: `$qa-engineer`
Status: `ADMITTED`

# Scoring Anchors

| Component | Points | Required evidence |
|---|---:|---|
| decision choice | `15` | choose `boundary-owned-compatibility-adapter` with status `ADOPT` |
| source authority | `15` | exact current-source ranking with stale ADR last |
| accepted claims | `20` | all claim ids bind to required source ids and terms |
| rejected options | `20` | reject global bus, consumer shims, direct switch, and stale ADR |
| compatibility and rollback | `20` | preserve v1, add v2 behind adapter, include 90-day and rollback semantics |
| non-claim and Markdown summary | `10` | explicit non-claim ledger and human-readable ADR sections |

Pass threshold: `85 / 100`.

Scoring is graded (R4a): `check_adr_long_horizon.py` awards partial credit per component
above, sums to `100`, and passes only at `>= 85`. Each component earns present / required-terms /
source-binding fractions; a forbidden claim in `adr-long-horizon-contract.json` (`forbidden_claims`)
is an integrity violation that fails the run regardless of the numeric score. The bundle-shape
contract remains a hard floor checked before any grading.

## Terms and Abbreviations

- `ADR`: Architecture Decision Record.
