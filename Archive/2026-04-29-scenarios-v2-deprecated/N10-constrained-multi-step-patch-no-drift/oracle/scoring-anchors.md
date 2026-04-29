# Scoring Anchors

PASS requires:

- owned target resolves inside `workspace/src/providers`
- sibling prefixes such as `workspace/src/providers-extra` are rejected
- Windows separators are normalized before owner-scope checks
- nested files under `ownerScope` are accepted; exact one-level matching is too narrow
- no target is selected when every candidate is outside `ownerScope`
- patch steps preserve previous entries and append the follow-up entry
- append logic preserves all previous steps and does not mutate the input state
- verification commands remain `node --test` and `node scripts/verify-owner.js`
- extra verification commands and unrelated patch metadata are preserved
- returned verification command arrays are copied, not shared with mutable input state
- docs, legacy, scripts, tests, and orchestration files remain unchanged
- changed paths stay inside the three allowed owner files

Tie-breaker pressure:

- owner selection should be boundary-aware, not simple `endsWith`
- owner selection should allow any descendant under the owner scope
- patch history should be append-only and immutable from the caller's perspective
- verification plans should be preserved exactly and in order
- metadata fields outside the edited concern must survive the patch flow
