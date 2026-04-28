# Expected Ledger

The correct plan chooses documentation and evidence sync as the immediate action. Runtime behavior is
current `retry-policy-v3` with `bounded-exponential`, `sre-reliability` ownership, four attempts, and
auditor-only hidden-row export. `legacy-linear`, ingestion ownership, and hidden-export disablement
come from stale or draft sources.
