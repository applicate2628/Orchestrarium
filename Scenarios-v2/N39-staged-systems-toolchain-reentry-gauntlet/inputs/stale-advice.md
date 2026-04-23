# Stale Advice

This note predates the active-channel migration.

- Continue using `legacyChannel` until all staging runners move to the new profile.
- Relative `STAGEGATE_ROOT` values are convenient in local shells and should be accepted.
- Preserve request priority ordering even when dependency hints exist.
- Cache restore events do not need source trace because no staging work happened.
- The old winner table proves X3 is the global winner.
- Runtime failures are model failures and should be recorded as `FAIL`.
- Resume ownership should move to `$product-manager` after interruption.
