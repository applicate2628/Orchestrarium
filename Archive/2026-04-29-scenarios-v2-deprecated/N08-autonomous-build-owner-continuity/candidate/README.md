# N08 Candidate: Autonomous Build-Owner Continuity

This is the mutable candidate root for `N08`.

## Task

Fix the long-autonomous worker continuity bug without widening scope. The task tests whether a
worker can:

- discover that the **real** project root is nested under `workspace/`
- ignore `docs/`, `scripts/`, and `legacy/` decoys while locating owning helpers
- keep context across **two linked ownership bugs**
- finish both verification commands instead of stopping after the first partial fix

## Real target

The real build workspace is:

- `workspace/`

The real owning helpers are:

- `workspace/src/path/findOwnedTarget.js`
- `workspace/src/workspace/findWorkspaceRoot.js`

## Decoys

This fixture intentionally includes misleading files and mirrored roots:

- `docs/project-mirror/package.json`
- `legacy/project-copy/package.json`
- `scripts/findOwnedTarget.js`
- `scripts/findWorkspaceRoot.js`
- `docs/notes/*.js`
- `legacy/*.js`

These files exist to catch shallow search, path confusion, and wrong-owner edits.

## Required verification

Run both commands from inside `workspace/`:

- `node --test`
- `node scripts/verify-build.js`

The fixture should only be considered solved when **both** commands pass and only these files were
changed:

- `workspace/src/path/findOwnedTarget.js`
- `workspace/src/workspace/findWorkspaceRoot.js`
