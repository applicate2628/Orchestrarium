# Task - Staged Performance Review Gate

You are reviewing a small QuotePerf optimization claim under `candidate/review-target/`.
Do not patch that package. Produce staged review artifacts only.

Current source IDs:

- `S1`: `engine._cache_key` owns pricing-cache identity; it must include every context dimension
  that can change a quote.
- `S2`: `engine.price_quote` uses `region` and `feature_flags` when computing a quote, so those
  fields are semantic.
- `S3`: `PRICE_CACHE` is a module-global cache and survives across batches, regions, and catalog
  refreshes.
- `S4`: `CATALOG_SNAPSHOTS` keeps refreshed catalog objects reachable and must be reviewed as
  retained-state risk.
- `S5`: `benchmarks/warm-run.json` is warm-cache only and cannot prove production speedup by itself.
- `S6`: `benchmarks/cold-mixed-run.json` is admissible evidence for mixed region and feature-flag
  workloads.
- `S7`: `benchmarks/memory-snapshot.json` is admissible evidence for cache-lifetime review.
- `S8`: `docs/stale-ops-assumptions.md` is stale and must be rejected.
- `S9`: JSON serialization and markdown formatting are not hot-path blockers in this fixture.
- `S10`: Decimal rounding is not the reviewed performance defect.
- `S11`: Author response decisions must preserve benchmark admissibility, owner, severity, and
  source evidence.
- `S12`: Final closeout must list exact changed review artifact paths and validation cues.

Required final artifacts:

- `candidate/review-state.json`
- `candidate/decision-adr.md`
- `candidate/findings.json`
- `candidate/response-gate.json`
- `candidate/closure.json`

Required review outcome: `REVISE`. Do not approve the optimization claim from warm-cache numbers.

The final answer should be concise. The verifier reads files, not prose.
