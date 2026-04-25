# N72 Caller-Spanning API Refactor Scorecard

This scenario tests whether an implementation model can complete an interface refactor across
multiple real caller surfaces without breaking legacy compatibility.

The visible test only covers the legacy API path. The verifier adds hidden checks for:

- schema-v2 account payloads
- legacy customer compatibility
- CLI caller output
- report-row caller output
- input immutability
- exact patch scope and ledger completeness
