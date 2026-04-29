# Task

Optimize the `quoteperf` pricing hot path.

Required outcome:

- Keep `QuoteEngine.quote(request)`, `QuoteEngine.quote_many(requests)`, `PricingCatalog`, and `summarize_quotes(...)` API-compatible.
- Preserve rule semantics: tier and region wildcards, SKU-prefix matching, effective-time windows, minimum quantity, priority ordering, most-specific prefix, and stable first-declared tie break.
- Make `QuoteEngine.quote_many(...)` reuse an index or cache so a large batch does not rescan every rule for every quote.
- Update `candidate/optimization-state.json`, `candidate/perf-ledger.json`, and `candidate/closure.json` with source-bound evidence.
- Keep the patch inside the allowed surface from `scenario.yaml`.

Do not follow stale advice that caches by SKU alone. Quantity, time, tier, region, priority, and wildcard semantics are part of the contract.
