# Non-Browser Boundary

`S17` is a Qt desktop UI scenario.

## In scope

- Qt-Widgets-style dialog code
- focus policy, tab order, keyboard handling, and local dialog reuse behavior
- direct UI verification material stored beside the dialog module

## Out of scope

- browser or DOM execution
- HTML, CSS, React, or Playwright changes
- Qt model/view plumbing or proxy-model fixes
- geometry, rendering, backend, platform, or scorer semantics

If a candidate answer starts talking about browser overlays, page focus traps, or web ARIA fixes,
it is solving the wrong scenario.
