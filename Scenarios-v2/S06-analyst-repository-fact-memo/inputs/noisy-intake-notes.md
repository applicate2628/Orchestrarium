# Noisy Intake Notes

These notes are intentionally unverified and may conflict with the repo slice. None of them names
specific files, symbols, or line ranges — that is for you to verify from the bundle-local repo
slice.

- A teammate suspects that a legacy configuration module under the publication package still drives
  profile lookup during result writing.
- Another thread claims that an archived scenario index from the v1 pack is still read during live
  scenario collection for the requested surface.
- An operator note says a role-to-surface mapping still decides which bundle is selected for a
  requested surface ID, independent of each scenario's own metadata.
- A stale doc page allegedly documents the current runtime routing path and is supposedly the
  source of truth for how surfaces are wired today.
- One last thread admits nobody re-validated the test suite after the migration freeze, so it is
  unclear whether the tests reflect the migrated path or the pre-migration path.

Each of these themes is a lead — verify it against the repo slice or reject it.
