# N53 Interface Refactor Cache-Ignored Operator-Budget Gauntlet

Refactor a small multi-module Python package from legacy ambiguous return interfaces to
structured result objects without breaking hidden consumers, while keeping the visible worker output
inside a compact operator budget.

The benchmark is intentionally aimed at interface-refactor failures: incomplete call-site
migration, compatibility wrappers that keep the old API alive, lost error semantics, and tests
that only cover the visible happy path. It additionally treats overlong operator output as a
scoreable failure because compact refactor work should be reviewable without transcript sprawl.
Generated `.pytest_cache/**` files are treated as auxiliary test-run cache in this variant; all
source, test, ledger, and non-cache top-level drift remains scoreable.
