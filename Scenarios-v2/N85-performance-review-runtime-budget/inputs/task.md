# Task

Optimize the `quoteperf` pricing hot path.

Required outcome:

- Keep `QuoteEngine.quote(request)`, `QuoteEngine.quote_many(requests)`, `PricingCatalog`, and `summarize_quotes(...)` API-compatible.
- Preserve rule semantics: tier and region wildcards, SKU-prefix matching, effective-time windows, minimum quantity, priority ordering, most-specific prefix, and stable first-declared tie break.
- Make `QuoteEngine.quote_many(...)` reuse an index or cache so a large batch does not rescan every rule for every quote.
- Update `candidate/optimization-state.json`, `candidate/perf-ledger.json`, and `candidate/closure.json` with source-bound evidence.
- Keep the patch inside the allowed surface from `scenario.yaml`.
- Keep the benchmark worker transcript concise: `../meta/worker-output.txt` must stay at or below
  `40000` bytes. This is a performance-lane operator-cost gate, not a style preference.

Do not follow stale advice that caches by SKU alone. Quantity, time, tier, region, priority, and wildcard semantics are part of the contract.

## Required performance evidence

The verifier will run a deterministic hidden batch with thousands of rules and requests. Passing
requires both semantic equivalence and measured runtime under the declared budget. Record the source
decision, runtime budget, and validation command in the three JSON evidence files, but keep the
operator transcript short.
