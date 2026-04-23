# N35 Staged Interface Migration Re-entry Gauntlet

Refactor a small multi-module Python package from legacy ambiguous return interfaces to
structured result objects across four fresh worker invocations.

The benchmark is intentionally aimed at interface-refactor failures plus re-entry failures:
incomplete call-site migration, compatibility wrappers that keep the old API alive, lost error
semantics, review-feedback false positives, stale-source adoption, and closeout ledgers that do
not survive a fresh final session.
