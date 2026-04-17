# Candidate Root

This is the mutable run root copied per execution.

The start state is intentionally broken in the editable browser UI files. The preview shell and
fixtures are already present, but the board still uses non-semantic filter controls, incomplete
state messaging, stale error content, and missing keyboard-focus treatment.

## Editable files

- `workspace/src/dashboard.js`
- `workspace/src/ui-copy.js`
- `workspace/src/dashboard.css`

## Read-only context inside the candidate root

- `workspace/package.json`
- `workspace/index.html`
- `workspace/src/main.js`
- `workspace/src/fixtures.js`
- `workspace/scripts/`
- `workspace/tests/`

After the patch, the intended local validation route is `node scripts/verify-ui-contract.mjs` from
`candidate/workspace/`. The browser preview route is `node scripts/static-server.mjs`.
