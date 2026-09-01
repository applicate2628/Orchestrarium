# v4 Per-root Verifier Contract

The per-root verifier is a thin adapter to `Tooling/v4_rubric`. It reads only the root's hidden
`oracle/rubric.json` plus the selected candidate artifact. It emits one canonical JSON report.

- candidate omissions or invalid candidate JSON: numeric score with local atom zeros;
- rubric, scorer, or input/output infrastructure fault: `SCORER-ERROR`, `score: null`, exit `2`;
- `PASS`, `PARTIAL`, `FAIL`, and `FAIL-INTEGRITY`: diagnostic status, numeric score retained, exit `0`;
- no network, model judge, wall clock, locale, filesystem-order, or provider metric inputs.

## Terms and Abbreviations

- `SCORER-ERROR`: scorer-side failure that cannot be charged to a candidate.
