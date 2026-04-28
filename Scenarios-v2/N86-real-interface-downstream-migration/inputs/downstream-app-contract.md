# Downstream Public-App Contract

The hidden downstream app is intentionally outside the package's internal module graph. It imports
only `billingmesh` and uses root-level public exports.

Required public exports:

- `AccountDirectory`
- `EntitlementPolicy`
- `UsagePublisher`
- `AccountLookup`
- `EntitlementDecision`
- `PublishResult`
- `handle_usage_event`
- `process_usage_request`
- `build_usage_summary`

The downstream app depends on structured dataclass result objects, not legacy booleans, strings, or
dict-only shims. `dataclasses.asdict` must preserve `owner`, `reason`, retryability, usage id, and
source ids. Reporting must consume structured result objects without forcing callers to convert them
to dictionaries first.

The hidden cases preserve the same semantic boundary as the visible task: denied events do not
publish, timeout publishes become retryable queued results, duplicate usage ids do not republish,
and source/owner attribution remains visible to downstream consumers.
