Date: 2026-04-20
Owner: `$lead`
Status: `PASS`

## Result

This is the current hardened weak-separator read for `X1`, `X3`, and `X5` over the core-12 lanes
that were previously tied.

This file is a targeted tiebreaker. It does not replace the full `S01..S33 + N01..N07` score table,
because the touched scenarios now use stricter contracts/verifiers.

| Row | Label | Admitted scoreable read | Timeout / incomplete | Current read |
|---|---|---:|---:|---|
| `X1` | `gpt-5.4` | `15 / 15` | `0` | tied strongest |
| `X3` | `opus 4.7max` | `15 / 15` | `0` | tied strongest |
| `X5` | `gemini3.1pro` | `12 PASS / 3 FAIL` | `0` | weaker on hardened review/security tail, but no longer timeout-pending |

## Scenario Matrix

| Scenario | Lane | `X1` | `X3` | `X5` |
|---|---|---|---|---|
| `S03` | `advisory.repo-understanding` | `PASS` | `PASS` | `PASS` |
| `S04` | `advisory.repo-understanding` | `PASS` | `PASS` | `PASS` |
| `S06` | `advisory.repo-understanding` | `PASS` | `PASS` | `PASS` |
| `S05` | `advisory.design-adr` | `PASS` | `PASS` | `PASS` |
| `S07` | `advisory.design-adr` | `PASS` | `PASS` | `PASS` |
| `S09` | `advisory.design-adr` | `PASS` | `PASS` | `PASS` |
| `S08` | `design.ui-ux-structure` | `PASS` | `PASS` | `PASS` |
| `N01` | `design.ui-ux-structure` | `PASS` | `PASS` | `PASS` |
| `N02` | `design.ui-ux-structure` | `PASS` | `PASS` | `PASS` |
| `S25` | `review.pre-pr` | `PASS` | `PASS` | `FAIL` |
| `N03` | `review.pre-pr` | `PASS` | `PASS` | `FAIL` |
| `N04` | `review.pre-pr` | `PASS` | `PASS` | `PASS` |
| `S27` | `review.security` | `PASS` | `PASS` | `PASS` |
| `N05` | `review.security` | `PASS` | `PASS` | `FAIL` |
| `N06` | `review.security` | `PASS` | `PASS` | `PASS` |

## Lane Matrix

| Lane | Basis | `X1` | `X3` | `X5` |
|---|---|---|---|---|
| `advisory.repo-understanding` | `S03`, `S04`, `S06` | `3 / 3` | `3 / 3` | `3 / 3` |
| `advisory.design-adr` | `S05`, `S07`, `S09` | `3 / 3` | `3 / 3` | `3 / 3` |
| `design.ui-ux-structure` | `S08`, `N01`, `N02` | `3 / 3` | `3 / 3` | `3 / 3` |
| `review.pre-pr` | `S25`, `N03`, `N04` | `3 / 3` | `3 / 3` | `1 PASS`, `2 FAIL` |
| `review.security` | `S27`, `N05`, `N06` | `3 / 3` | `3 / 3` | `2 PASS`, `1 FAIL` |

## Interpretation

| Question | Current answer |
|---|---|
| Can these hardened tests separate `X1`, `X3`, and `X5`? | Yes for `X5`; no for `X1` vs `X3` on this subset. |
| Where does `X5` weaken? | Hardened review gates: `review.pre-pr` and `review.security`; timeout cells are now closed into scoreable states. |
| Is `X5/N02` a normal pass? | Yes after timeout closure: normal runner wrote `summary.json` and verifier passed. |
| Is `X5/S25` a quota miss? | No. It is a real scoreable verifier failure: missing `nearby smoke` in `## Residual Risk`. |
| What changed in timeout closure? | `N02` and `N06` closed through the normal runner; `N03` closed through the normal runner as `FAIL`; `N04` and `N05` used isolated direct-prompt Gemini transport because stdin transport hung. |

## Source

| Source | Role |
|---|---|
| `../Evidence/x1-x3-x5-core12-tie-hardened-2026-04-20.md` | evidence, run roots, timeout classification, and manual verifier diagnostics |
| `../Evidence/x5-core12-timeout-closure-2026-04-20.md` | timeout closure evidence converting previous `X5` timeout cells into scoreable states |
| `v2-full-s01-s33-n01-n07-results-2026-04-18.md` | full current expanded v2 surface before targeted hardening |
