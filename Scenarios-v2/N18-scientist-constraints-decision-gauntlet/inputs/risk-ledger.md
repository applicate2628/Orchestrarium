# Risk Ledger

| Risk | Applies to | Impact | Required mitigation | Owner |
|---|---|---|---|---|
| `R1 latency regression` | `Option C` | delayed release gate | p95 latency regression test at `<= 200ms` | `$performance-engineer` |
| `R2 replay drift` | `Option C` | inconsistent source trace | replay-vs-ledger parity test at `100%` | `$reliability-engineer` |
| `R3 index corruption` | `Option C` | wrong gate decision | rebuild index from ledger and compare decisions | `$qa-engineer` |
| `R4 secret exposure` | all options | trust boundary break | synthetic fixtures only; no production secrets in prompt/cache | `$security-engineer` |
