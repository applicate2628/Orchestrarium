# Oracle

The oracle material defines the ground-truth performance read for `S13`.

## Expected read

The correct package stays in the performance-engineer lane and anchors the analysis in the
supplied evidence. A strong answer writes the required budget envelope explicitly, identifies the
hash-manifest build and late archive buffering as the dominant bottlenecks, separates cold-run and
warm-run measurement, preserves redaction and deterministic replay as non-negotiable boundaries,
and leaves the package in `REVISE` because the current draft misses the admitted latency and memory
budgets.

## Included oracle files

- `performance-constraint-contract.json` provides machine-readable verifier anchors
- `expected-package-read.md` describes the expected disposition and role-correct framing
- `budget-and-bottleneck-anchors.md` lists the budget and bottleneck anchors a passing package
  should capture
- `tradeoff-boundary-anchors.md` lists the required tradeoff fences and non-goals
- `prohibited-patterns.md` lists role drift and scope-break failures
- `scoring-anchors.md` translates the scoring model into `S13`-specific pass and fail signals
