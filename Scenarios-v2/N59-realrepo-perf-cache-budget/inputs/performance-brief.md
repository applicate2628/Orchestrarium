# Performance Brief

The production-like workload repeatedly prices quote batches against a catalog containing thousands of discount rules. The current implementation is correct for small examples but performs an `O(rule_count * quote_count)` scan in the batch path.

Target budget:

- `quote_many` must price the hidden batch within `0.70` seconds on the verifier host.
- Correctness is checked separately; a fast approximation that ignores semantic dimensions fails.
- The intended fix is an owning-boundary optimization inside `QuoteEngine` or `PricingCatalog`, not caller-side filtering in tests or reporting.
