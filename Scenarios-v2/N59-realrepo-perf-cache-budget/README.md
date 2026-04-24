# N59 Real-Repo Performance Cache Budget

Optimize a quote-pricing hot path without changing its public API. The verifier uses hidden correctness cases plus a large deterministic batch benchmark; passing requires preserving discount semantics and making `QuoteEngine.quote_many(...)` fast enough under a measured runtime budget.
