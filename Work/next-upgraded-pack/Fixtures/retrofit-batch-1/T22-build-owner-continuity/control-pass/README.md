# G12 Worker Continuity Build

Date: 2026-04-15
Owner: `$lead`
Status: `PASS`

## Purpose

`G12` is a stronger worker-discipline probe than `G11`.

It is meant to test whether a model can:

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

- `npm test`
- `node scripts/verify-build.js`

The fixture should only be considered solved when **both** commands pass.
