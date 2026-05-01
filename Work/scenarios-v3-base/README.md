Date: 2026-05-01
Owner: `$knowledge-archivist`
Status: `RUN / BINARY TIE`

# Scenarios-v3 Base Workspace

This workspace prepares Scenarios-v3 from the embedded pre-v3 RF12 line map without carrying
forward deprecated roots, nonfinal diagnostics, or raw run debris.

## Canonical Inputs

| Input | Use |
|---|---|
| `../../Scenarios-v3/_registry/scenarios-v3-base.json` | current v3 line and trigger registry |
| `Planning/s2-to-v3-migration-map-2026-05-01.md` | embedded pre-v3 RF12 line read and v3 disposition map |
| `../../Scenarios-v3/V3L02-adr-long-horizon-source-conflict/` | first admitted v3 root; run completed with `binary tie remains` |

## Workspace Layout

| Path | Use |
|---|---|
| `Planning/` | v3 base plan, migration map, and future wave specs |
| `Templates/` | task/oracle/verifier templates for admitted v3 roots |
| `Evidence/` | new v3 preparation evidence only |
| `Checkpoints/` | live v3 status and resume state |
| `Results-drafts/` | draft v3 result surfaces before release admission |

## Boundary

`Scenarios-v3/` is the active discovery root. This workspace is mutable preparation material and
does not change any released benchmark denominator by itself. `V3L02` has been run for `X1` and
`X3`; both passed, so it is not an `X1/X3` separator.

## Terms and Abbreviations

- `RF12`: role-fit scorecard over twelve routing lines plus one owner/control line.
- `pre-v3 RF12 line map`: distilled line-priority and role-fit basis embedded in this workspace.
- `v3`: Scenarios-v3 benchmark generation.
