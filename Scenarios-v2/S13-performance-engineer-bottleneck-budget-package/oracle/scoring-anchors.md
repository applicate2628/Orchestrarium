# Scoring Anchors

These anchors apply the `scientist, constraints` profile to `S13`.

## Strong pass signals

- the package cites `E1` through `E5` directly and uses them to justify the budgets
- `B1` through `B5` appear as explicit quantitative constraints
- `BT1` through `BT4` frame the runtime and measurement bottlenecks instead of generic slowdown
- the measurement strategy separates cold run and warm run behavior and includes `p95` plus
  `peak RSS`
- tradeoff boundaries preserve hash-manifest coverage, redaction, and deterministic replay
- the final gate decision is `REVISE`

## Partial-credit signals

- the package names the main bottlenecks but leaves one budget implicit
- the package gives latency budgets without a corresponding memory constraint
- the package mentions cold versus warm behavior but does not tie it to stage-level measurement

## Fail signals

- no explicit budgets or no quantitative bottleneck framing
- no measurement strategy, or measurement collapses cold run and warm run into one number
- drift into implementation repair, review findings, or reliability policy
- an answer that treats the workload as web or browser-bound
- a `PASS` decision despite the admitted baseline missing `B1` through `B5`
