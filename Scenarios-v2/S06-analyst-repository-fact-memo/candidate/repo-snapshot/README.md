# Repo Snapshot

This is a bounded, read-only repository slice for `S06`.

- Paths are intentionally bundle-local so scored runs do not depend on the surrounding workspace.
- The slice includes both live code and stale-looking artifacts so the analyst must distinguish
  runtime behavior from legacy reference material.
- Not every upstream caller is included. Explicit unknowns are expected where the slice ends.
