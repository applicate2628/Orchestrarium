# Incident Log

Release `rf-2026-04-freeze` replayed one change after a worker crash and then produced a report from
toast notifications. The report listed a stale staging-only change as applied even though the active
profile was `prod`.

Observed facts:

| ID | Fact |
|---|---|
| `S1` | `activeProfile` is the source of truth for profile selection. |
| `S2` | `legacyProfile` is compatibility metadata and must not override `activeProfile`. |
| `S3` | per `changeId`, the highest `sequence` record wins. |
| `S4` | changes targeting environments in `blockedEnvs` must not be planned. |
| `S5` | dependencies must be applied before dependents. |
| `S6` | resume must use a stable action key independent of retry attempt. |
| `S7` | release reports must be derived from ledger/audit state, not notifications. |
