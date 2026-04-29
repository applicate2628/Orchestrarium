# Review Feedback To Resolve

| id | Direction | Expected decision |
|---|---|---|
| R1-keep-legacy-wrapper | Keep old wrapper names for one release. | reject |
| R2-public-root-exports | Export all migrated APIs and dataclasses from package roots. | accept |
| R3-denied-no-delivery | Rejected route decisions must not reach the plugin transport. | accept |
| R4-timeout-duplicate-idempotency | Timeouts stay retryable and duplicate event IDs do not republish. | accept |
| R5-legacy-envelope-migration | Legacy v1 envelopes must migrate without mutation or source loss. | accept |
| R6-stale-cli-stdout | CLI stdout plus exit code is enough for automation. | reject |
| R7-owner-boundary | Keep routing, SDK, plugin, and CLI ownership in their packages. | accept |
