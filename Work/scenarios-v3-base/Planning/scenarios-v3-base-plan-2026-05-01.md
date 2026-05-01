Date: 2026-05-01
Owner: `$knowledge-archivist`
Status: `RUN / BINARY TIE`

## Purpose

Prepare the Scenarios-v3 base from the embedded pre-v3 RF12 line map without copying retired roots
or diagnostic debris into the new active denominator.

## Accepted Constraints

| Constraint | Decision |
|---|---|
| source basis | embedded pre-v3 RF12 line map in the v3 registry and migration map |
| active v3 roots at base creation | `0` |
| current admitted v3 roots | `1` |
| active discovery location | `Scenarios-v3/` |
| mutable design location | `Work/scenarios-v3-base/` |
| row focus | `X1` vs `X3`; `X4` final-only; `X2` closed calibration; `X5/X6` deprecated |
| first unresolved line | `L02 advisory.design-adr` |

## Work Plan

| Step | Action | Output |
|---:|---|---|
| 1 | Establish active v3 discovery boundary | `Scenarios-v3/README.md` |
| 2 | Create machine-readable registry | `Scenarios-v3/_registry/scenarios-v3-base.json` |
| 3 | Map S2 lines to v3 dispositions | `s2-to-v3-migration-map-2026-05-01.md` |
| 4 | Define admission templates | `Templates/` |
| 5 | Set live resume point | `Checkpoints/status-2026-05-01.md` |
| 6 | Update root navigation | `README.md`, `MANIFEST.md`, `AGENTS.md` |
| 7 | Admit first v3 root to pre-run boundary | `Scenarios-v3/V3L02-adr-long-horizon-source-conflict/` |

## First Wave Recommendation

| Wave | Target | Rationale |
|---|---|---|
| `V3-W1` | `V3L02-adr-long-horizon-source-conflict` | run completed; `binary tie remains` for `X1` vs `X3`, while `X2` calibration fails |

The first v3 task should avoid staged review triggers and avoid output-budget-only separation. It
should force long-horizon ADR judgment over conflicting sources, source freshness, rollback,
compatibility, rejected options, and non-claim discipline.

## Non-Goals

| Non-goal | Reason |
|---|---|
| copy all 40 v2 roots | would recreate an old denominator instead of a v3 base |
| copy RF12 diagnostic roots into active discovery | they are evidence patterns, not admitted v3 roots |
| revive old denominator table | superseded by the v3 active-discovery model |
| run models during pre-run admission | launch rows only after explicit run authorization |

## Terms and Abbreviations

- `ADR`: Architecture Decision Record.
- `RF12`: role-fit scorecard over twelve routing lines plus one owner/control line.
- `V3-W1`: first Scenarios-v3 hardening wave.
