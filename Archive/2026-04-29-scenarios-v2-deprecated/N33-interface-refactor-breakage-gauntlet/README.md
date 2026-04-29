# N33 Interface Refactor Breakage Gauntlet

Refactor a small multi-module Python package from legacy ambiguous return interfaces to
structured result objects without breaking hidden consumers.

The benchmark is intentionally aimed at interface-refactor failures: incomplete call-site
migration, compatibility wrappers that keep the old API alive, lost error semantics, and tests
that only cover the visible happy path.
