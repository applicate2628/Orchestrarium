# N85 Performance Review Runtime Budget

Optimize a quote-pricing hot path without changing its public API. The verifier uses hidden
correctness cases plus a large deterministic batch benchmark; passing requires preserving discount
semantics, making `QuoteEngine.quote_many(...)` fast enough under a measured runtime budget, and
keeping the worker transcript under the explicit performance-lane operator-output budget.
