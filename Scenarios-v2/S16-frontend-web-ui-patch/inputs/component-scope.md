# Component Scope

## Editable owner seam

- `src/dashboard.js` owns the board markup for loading, success, empty, and error states
- `src/ui-copy.js` owns the state-specific copy used by the board
- `src/dashboard.css` owns the board and control styling

## Read-only support files

- `src/main.js` wires the browser preview shell and event delegation
- `src/fixtures.js` provides the preview state data and filter labels
- `scripts/static-server.mjs` serves the bundle-local preview
- `scripts/verify-ui-contract.mjs` performs the local machine validation
- `tests/browser-checklist.md` captures the manual browser expectations

Changing the support files is out of scope. The intended fix lives inside the frontend UI owner seam
only.
