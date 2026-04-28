# Phase 03: Layout, Raster, And Validation

Repair responsive layout geometry, deterministic raster output, and visible tests.

Allowed changes:

- `candidate/workspace/src/console-layout.mjs`
- `candidate/workspace/src/console-raster.mjs`
- `candidate/workspace/src/console.css`
- `candidate/workspace/tests/console-contract.test.mjs`
- `candidate/workspace/implementation-ledger.json`

Requirements:

- `computeLayout()` must fit 320, 768, and 1280 width viewports.
- Interactive command, tab, and button targets must not overlap and must stay at least 32px in both dimensions.
- Compact layout stacks the raster preview below the detail form; desktop layout places it to the right.
- `renderRaster()` must preserve transparent gaps, draw alert/selection overlays after base cells, keep the zero-centered legend, and export valid ASCII `P3` PPM.
- CSS must include `:focus-visible`, `min-inline-size`, `overflow-wrap`, disabled button styling, selected option styling, and a max-width 480px media query.
- Extend the ledger with phase `03-layout-raster-validation` and cite the visible Node test.

Do not edit protected docs, inputs, oracle, verifiers, or `protected-copy.mjs`.
