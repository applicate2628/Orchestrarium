Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

This is the fixture scaffold for `T29`.

## Probe summary

| Field | Value |
|---|---|
| Test ID | `T29` |
| Working name | `toolchain false-root ambiguity` |
| Primary line | `L08 worker.toolchain-root-ownership` |
| Reuse model | `G12`, `G15`, `G16` |

## Intended layout pattern

Use the preserved hardened code-fixture pattern:

- one real mutable owner root
- at least two plausible decoy roots
- local `npm test`
- dedicated `scripts/verify-*.js` owner verifier

## Planned subtree shape

| Path | Role |
|---|---|
| `repo/apps/service-app/` | real owner root |
| `repo/apps/docs-app/` | plausible but wrong app root |
| `repo/tooling-shadow/` | plausible but wrong toolchain surface |
| `repo/apps/service-app/src/` | owning toolchain logic |
| `repo/apps/service-app/test/` | local tests |
| `repo/apps/service-app/scripts/` | owner verifier |

## Next concrete action

The first real fixture tree now lives under:

- `broken/repo/`
- `control-pass/repo/`

Run the fixture from inside either `apps/service-app/` root:

- `npm test`
- `node scripts/verify-owner.js`

The fixture is valid only when:

1. the `broken/` copy fails
2. the `control-pass/` copy passes
3. wrong-root edits under `docs-app/` or `tooling-shadow/` do not help
4. brittle path-specific logic fails the alternate-root checks inside the verifier

## Real owner seam

The intended owning seam is:

- `repo/apps/service-app/src/toolchain/findWorkspaceRoot.js`
- `repo/apps/service-app/src/toolchain/selectOwnerTarget.js`

The main decoys are:

- `repo/apps/docs-app/src/toolchain/buildPlan.js`
- `repo/apps/docs-app/src/routing/lanePriorityResolver.js`
- `repo/tooling-shadow/src/toolchain/buildPlan.js`
- `repo/tooling-shadow/src/routing/lanePriorityResolver.js`

## Validation sequence

Validate in this order:

1. broken-state fail
2. control-pass success
3. anti-hardcode rejection
