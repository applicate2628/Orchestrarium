Date: 2026-04-29
Owner: `$lead`
Status: `PASS`

## Purpose

This archive contains `Scenarios-v2` bundle roots that no longer participate in the active
benchmark surface.

The active top-level `Scenarios-v2/` set was reduced to:

- `40` canonical `full-v2-hard` score slots
- `33` retained RF12 / separator diagnostics with routing value
- `73` active top-level scenario roots total

This archive stores `54` roots that were weak, superseded, diagnostic-only with no policy impact,
or retained only as historical provenance. They should not be included in default hardening,
rerun, or ranking batches.

## Retention Rule

| Rule | Meaning |
|---|---|
| archive, do not delete | old evidence and reports may still cite these IDs |
| no default reruns | these roots are excluded from active top-level `Scenarios-v2` discovery |
| restore only by decision | move a root back only if it replaces a named active slot or becomes routing-grade evidence |

## Archived Roots

| Class | Scenario roots |
|---|---|
| extra lane / historical worker continuity | `N08`, `N09`, `N10` |
| early top-pair diagnostics now too weak | `N11`, `N12`, `N13`, `N14`, `N15` |
| superseded or lower-yield early RF evidence | `N18`, `N20`, `N33`, `N38`, `N42`, `N45`, `N52`, `N53`, `N59`, `N61` |
| tied diagnostics with no active routing change | `N64`, `N65`, `N66`, `N68`, `N75`, `N81`, `N82`, `N83`, `N84`, `N87` |
|  | `N88`, `N89`, `N90`, `N91`, `N92`, `N94` |
| superseded pre-v3 role surface | `S01`, `S02`, `S10`, `S11`, `S12`, `S13`, `S14`, `S15`, `S16`, `S17` |
|  | `S18`, `S19`, `S20`, `S21`, `S23`, `S24`, `S26`, `S31`, `S32`, `S33` |

## Active Counterpart

The current active result surface is:

- `Work/next-upgraded-pack/Results-drafts/full-v2-hard-results-current.md`
- `Work/next-upgraded-pack/Results-drafts/role-fit-scorecard-v1-2026-04-22.md`

Current canonical score remains unchanged by this archive move:

| Row | Current score |
|---|---:|
| `X3 / opus 4.7max` | `35 / 40` |
| `X1 / gpt-5.5` | `34 / 40` |
| `X4 / Claude China opus max` | `31 / 40` |
| `X5 / gemini3.1pro` | `14 / 40` |
| `X6 / flash-lite` | `13 / 40` |
| `X2 / gpt-spark` | `12 / 40` |
