# Repo Context Memo

## Relevant boundaries

| Surface | Owner | Review implication |
|---|---|---|
| scenario bundle root | bundle-local authoring | may define its own task, oracle, and verifier assets |
| review candidate output | review bundle contract | findings report only; review targets are read-only evidence |
| publication and scoring modules | downstream results surfaces | may consume bundle metadata but should not become authoring dependencies |
| accepted design packet | upstream authority | review checks implementation against the approved claims list |

## Standards that matter here

- review bundles in `P06` stay findings-only and do not embed implementation work products
- additive fixture work should stay isolated to its new bundle root
- dependency direction should point from publication surfaces toward scenario metadata, not the
  reverse
- path-protection rules should be maintained once and referenced consistently

## Non-issues for this scenario

- an explicit empty `overlay_flags` list is required metadata, not drift
- local severity labels are acceptable bundle-local data
- repeated explanatory wording across the immutable inputs is context, not a second mutable owner
