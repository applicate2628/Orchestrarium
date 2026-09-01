# V4C01 Verifier Contract

The common scorer reads `oracle/rubric.json` and `candidate/advice.json`. Structured decisions,
source order, claim/source sets, actions, and case outcomes score independently. Narrative text is
ignored. A true `safe_to_execute_without_review` value zeroes only `precision.nonclaim`, applies the
declared bounded penalty, and returns `FAIL-INTEGRITY` with the numeric score retained.
List-form claims and cases must have unique logical IDs; a repeated ID returns the common
`INVALID-CANDIDATE` report with score 0 before any list-to-map scoring projection.

Scorer-side faults return `SCORER-ERROR` with no numeric score.

## Terms and Abbreviations

- `F1`: harmonic mean of precision and recall.
