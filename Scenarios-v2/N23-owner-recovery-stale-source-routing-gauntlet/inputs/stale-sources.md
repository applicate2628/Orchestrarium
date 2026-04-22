# Stale And Decoy Sources

| Stale source | Trap |
|---|---|
| `ST1` | old full-v2 leaderboard says `X3 is the global winner`; this is stale and not admitted as a global routing policy |
| `ST2` | old N16 summary says `N16 proves the global winner`; N16 is diagnostic E6 only |
| `ST3` | broad calibration request says `Run X2, X5, and X6 on every scenario`; current policy keeps calibration bounded |
| `ST4` | wrong-owner note says `$product-manager owns the next step`; current task is delivery hardening, so `$lead` owns it |
| `ST5` | premature gate note says `Send the output to QA now`; QA waits until bundle, verifier, scorer, and reference pass validate |

Every stale source must be rejected explicitly in the candidate packet.
