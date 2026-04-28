# N83 Interface Refactor Breakage Hunt

Refactor a small multi-module Python package from legacy ambiguous return interfaces to
structured result objects without breaking hidden consumers.

The benchmark is intentionally aimed at interface-refactor failures: incomplete call-site
migration, compatibility wrappers that keep the old API alive, lost error semantics, and tests
that only cover the visible happy path.

The hardened hidden consumer exercises a batch API that must preserve request order while
sharing router state for duplicate detection. The report contract also consumes structured
result objects, so dict-only rewrites and ledger-only migrations are scoreable failures.
