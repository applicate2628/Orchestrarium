# Author Responses To Gate

- `A1-approve-warm-only-speedup`: "The 27.5x warm-cache benchmark is enough. Please approve."
- `A2-cache-key-sku-only`: "SKU uniquely identifies a price in practice, so the cache key can stay
  as-is."
- `A3-add-region-only`: "If a change is required, add region to the key but keep feature flags out
  because callers already normalize them."
- `A4-raise-memory-budget`: "The memory snapshot is high but still below production node memory.
  Raise the review budget instead of revising the design."
- `A5-add-cold-mixed-benchmark`: "Add cold-cache mixed-region and feature-flag benchmark evidence to
  the required validation gate."
- `A6-bound-cache-lifetime`: "Make cache lifetime explicit across catalog refresh and release
  re-entry."
