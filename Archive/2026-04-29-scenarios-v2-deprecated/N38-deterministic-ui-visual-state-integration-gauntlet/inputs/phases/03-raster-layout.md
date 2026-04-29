# Phase 03 - Raster Layout

Allowed edits for this phase:

- `candidate/workspace/src/console-layout.mjs`
- `candidate/workspace/src/console-raster.mjs`
- `candidate/workspace/src/console.css`
- `candidate/workspace/implementation-ledger.json`

Repair layout and raster preview:

- `computeLayout({ width, height }, state)` returns required boxes with deterministic numeric
  geometry.
- The layout fits 320, 768, and 1280 width viewports.
- Interactive command, tab, and button boxes are at least 32 px on both axes and do not overlap.
- Compact layout stacks the raster preview below the form; desktop layout places it to the right.
- `renderRaster(spec)` preserves missing cells as background gaps.
- Use the zero-centered palette for -1, 0, 1, and 2.
- Draw alert stripe after base cells.
- Draw selected focus ring and selected center highlight after base/alert layers.
- Render the legend in negative-to-positive order.
- `exportPpm(frame)` returns valid ASCII `P3` metadata and all RGB channels.

Update the implementation ledger with phase id `03-raster-layout`, owner `visualization-engineer`,
source ids `S11` and `S12`, and stale rejection of zero-fill, reversed legend, and desktop-only
layout advice.
