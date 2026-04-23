# N36 Real-Repo Staged API Migration Gauntlet

Migrate a repo-like BillingMesh package from legacy billing/entitlement APIs to structured result
objects across four fresh worker invocations.

The benchmark is intentionally aimed at real interface/API refactor failures plus re-entry
failures: scattered service/API/reporting consumers, compatibility wrappers that keep the old API
alive, lost owner/retry/idempotency semantics, review-feedback false positives, stale-source
adoption, and closeout ledgers that do not survive a fresh final session.
