# Failing Browser Observations

Observed against the bundle-local preview before any patch:

- loading shows `Working through release checks...` as plain text and does not announce progress
- filter chips inside the board are generic blocks, so the active state is visual only
- success copy says `2 checks in view` instead of the required `Showing 2 checks`
- the empty state falls back to generic copy and does not expose a reset action
- the error state keeps stale result cards visible under the failure message
- keyboard focus is not visually distinct on the board's interactive controls
