# Source Conflict Notes

| Source | Status | Note |
|---|---|---|
| `S1` | current | `CustomerDirectory` owns customer lookup, missing/suspended/expired reasons, and current tick handling. |
| `S2` | current | `SubscriptionPolicy` owns tenant-disabled and feature entitlement decisions. |
| `S3` | current | `WebhookPublisher` owns timeout, retryable queued state, duplicate suppression, and publish ownership. |
| `S4` | current | `service.py` owns internal orchestration and denied-without-webhook behavior. |
| `S5` | current | `api.py` is the public facade for app callers and must not be bypassed. |
| `S6` | current | `reporting.py` owns summary counts, owners, reasons, and mixed object/dict inputs. |
| `S7` | current | `legacy_adapter.py` owns legacy event envelope migration. |
| `S8` | current | package root exports are part of the public SDK contract. |
| `S9` | current | visible tests cover smoke behavior only; hidden downstream SDK replay owns compatibility. |
| `S10` | current | review feedback is part of the re-entry contract. |
| `S11` | superseded | older docs suggest keeping legacy wrappers for one release, but the current contract forbids wrappers. |
| `S12` | superseded | a draft note suggests summary accepts only dictionaries; the current reporting contract requires mixed structured objects and dictionaries. |
