# v4 Phase 1 QA Report

Date: 2026-07-13
Role: `$qa-engineer`
Verdict: `PASS`

## Acceptance Evidence

| Criterion | Evidence | Result |
|---|---|---|
| atomic 0-100 algebra; no ordinary atom above 10; semantic weight at least 70 | rubric-contract validation over all four roots; scorer unit tests | `PASS` |
| local partial credit; diagnostic-only status | unit tests for component retention, numeric interpolation, set/source F1, one-to-one finding F1, and local integrity zero | `PASS` |
| valid representation variants remain scoreable | Draft 2020-12 schema validation of reference and paraphrase/list-map variants for all roots | `PASS` |
| scorer faults never become model zero | malformed candidate is scoreable with local zeros; malformed/missing rubric returns `SCORER-ERROR`, `score: null` | `PASS` |
| four calibration-only roots complete | root-shape test checks task, visible schema, hidden rubric, reference, synthetic corpus, adapter, and verifier contract | `PASS` |
| partial-credit spread and monotonicity | mechanism harness synthetic ladders and saved machine-readable evidence | `PASS` |
| paraphrase robustness | all four differently worded/ordered valid variants equal their references | `PASS` |
| mutation locality and threshold neighborhood | one 10-point deletion changes one owning component; two-atom deletion scores 80 in every root | `PASS` |
| deterministic replay and adapter equivalence | three identical reports per synthetic answer; four per-root adapters equal the common scorer | `PASS` |
| protected surfaces | change inventory is confined to `Work/scenarios-v4-base/` plus governance session artifacts | `PASS` |

## Checks

- `python -m unittest discover -s Work/scenarios-v4-base/Tooling/tests -v`
- `python Work/scenarios-v4-base/Tooling/validate_calibration.py --json-out Work/scenarios-v4-base/Evidence/calibration-mechanism/mechanism-validation.json`
- JSON parse and Draft 2020-12 visible-schema checks through the test suite
- repository-relative path and trailing-whitespace scans over the v4 work pack

## Residual Risk

Synthetic calibration proves the scoring mechanics and mutation invariants, not discrimination on
natural model outputs. Future root authoring can still create a construct-validity, ceiling, or
schema-gaming failure even when this common scorer is correct. That risk must be resolved before
freeze with non-current blind outputs or pre-registered synthetic mutations for every ranked root.

Basic performance is accepted for this phase: the complete deterministic harness operates on small
local JSON artifacts and has no provider, network, or target-program performance budget.

## Terms and Abbreviations

- `F1`: harmonic mean of precision and recall.
- `QA`: Quality Assurance.
- `SCORER-ERROR`: scorer-side failure with no numeric candidate score.
