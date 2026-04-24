# Visual Layout Contract

The UI layout and raster preview are deterministic:

- `computeLayout({ width, height }, state)` returns `{ boxes: [...] }`
- every box has `id`, `role`, `x`, `y`, `width`, and `height`
- required boxes: `command-palette`, `record-tabs`, `detail-form`, `raster-preview`,
  `save-button`, `discard-button`
- boxes must stay inside 320, 768, and 1280 width viewports
- interactive boxes (`command`, `tab`, `button`) must be at least 32 px on both axes
- interactive boxes must not overlap each other
- at desktop width, the raster preview is to the right of the detail form
- at compact width, the raster preview stacks below the detail form

Raster rules:

- missing cells stay as the background gap color
- alert stripe is drawn after base cells
- selected focus ring and selected center highlight are drawn after alert/base layers
- legend values render in negative-to-positive order using the zero-centered palette
- `exportPpm(frame)` returns `P3`, `width height`, `255`, then all RGB channels
