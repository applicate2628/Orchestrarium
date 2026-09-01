# v4 Phase 1 Scoring Contract

Date: 2026-07-13
Status: `CALIBRATION`

Every scoreable candidate receives a numeric score from `0` through `100`. Components sum to 100;
their atoms receive rational relative weights and no ordinary atom is worth more than 10 points.
At least 70 component points are semantic. Missing or invalid candidate fields zero only their atoms.
There is no unconditional global floor or ceiling. A rubric may mark semantic atoms as
commitment-bearing and declare a wrong-commitment cap strictly below its partial threshold. A
present false or incompatible commitment activates that cap and the diagnostic
`FAIL-COMMITMENT` status; an omitted commitment retains ordinary partial credit. `PASS` (`80+`),
`PARTIAL` (`50..79.99`), and `FAIL` (`<50`) otherwise remain diagnostic labels only.

The hidden rubric is the single owner of expected values, weights, aliases, tolerances, matching
fields, severity weights, integrity penalties, and thresholds. Visible schemas define candidate
representation. Structured enums, identifiers, source bindings, observable case results, numeric
values with units, and location tuples carry score; narrative prose does not. Scored string
surfaces use bounded identifier, token, path, or symbol shapes rather than unrestricted prose.

Integrity events are structured. They may zero only declared owning atoms and apply declared
penalties capped at 15. A scorer or rubric fault returns `SCORER-ERROR` with no numeric score. Invalid
candidate JSON remains a scoreable candidate defect and does not masquerade as scorer failure.

The calibration-only roots are:

| Root | Mechanism focus |
|---|---|
| `V4C01-source-bound-advice` | categorical decisions, source order, source-binding F1, integrity |
| `V4C02-numeric-reasoning` | continuous numeric error, units, invariants, falsification cases |
| `V4C03-implementation-runtime` | observable behavior cases, interfaces, scope, test evidence |
| `V4C04-findings-review` | severity-weighted one-to-one finding F1, evidence, precision, actions |

These roots never enter the eventual 26-root ranking denominator.

## Terms and Abbreviations

- `F1`: harmonic mean of precision and recall.
- `SCORER-ERROR`: infrastructure or rubric failure with no model score.
- `FAIL-COMMITMENT`: a valid structured answer made a wrong present commitment and its declared
  low-band cap applied.
