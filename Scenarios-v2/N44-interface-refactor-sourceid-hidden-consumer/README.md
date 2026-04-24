# N44 Interface Refactor SourceId Hidden Consumer

Refactor a small multi-module Python package from legacy ambiguous return interfaces to
structured result objects without breaking hidden consumers or public source-id traceability.

The benchmark is intentionally aimed at interface-refactor failures: incomplete call-site
migration, compatibility wrappers that keep the old API alive, lost error semantics, source IDs
that stay trapped in internal dataclasses, and hidden consumers not covered by the immutable visible
happy-path test.
