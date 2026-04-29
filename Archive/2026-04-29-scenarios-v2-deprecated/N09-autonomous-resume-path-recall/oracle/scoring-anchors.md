# Scoring Anchors

PASS requires:

- `previousRoot` wins when still present in the manifest root list
- `previousRoot` is normalized before validity checks
- neutral follow-up directories do not force root drift
- stale `previousRoot` values are rejected when absent from the manifest list
- current concrete roots win after the previous root disappears
- prior real edit evidence is used only after previous and current roots are unavailable
- docs and legacy mirrors are never used as fallback roots when no real continuity signal exists
- docs and legacy mirrors stay unchanged
- alternate real roots still work
- changed paths stay inside the one allowed owner file

Tie-breaker pressure:

- prefer accepted continuity over recency of touched files
- avoid docs and legacy mirror fallbacks even when they have package manifests
- normalize Windows separators and trailing separators
- return `null` rather than guessing from mirror-only evidence
