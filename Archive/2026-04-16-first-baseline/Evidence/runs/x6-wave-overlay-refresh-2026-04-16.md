Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

Regenerate the `X6`-sensitive wave reading after the corrected fallback refresh under:

- `gemini-3.1-flash-lite-preview`

This file does **not** overwrite the historical `W1..W5` artifacts from 2026-04-14.
It is the corrected current overlay for the active Gemini fallback path.

## Historical preservation rule

| Rule | Meaning |
|---|---|
| keep historical wave files | the original `w1..w5` files remain provenance and stay readable as historical-at-the-time evidence |
| corrected overlay wins for current `X6` reading | when current routing or comparison logic talks about `X6`, it should use this overlay rather than the old `2.5-flash` or `3-flash-high-explicit` stop-language |

## Corrected wave overlay

| Wave | Row set | Current `X6` read | Gate decision |
|---|---|---|---|
| `W1` | `M01`, `M03`, `M04`, `M05` | all four rows now admitted on the current fallback, including the old review-sensitive row `M05` | `GO` |
| `W2` | `M02`, `M06`, `M07`, `M10` | all four rows admitted on the current fallback | `GO` |
| `W3` | `M08`, `M09` | both rows admitted; `M08` carries the host-side shell-verification caveat | `GO` |
| `W4` | `M01`, `M05`, `M08`, `M09` | the corrected fallback now clears the full historical fallback slice instead of failing on review | `GO` |
| `W5` | `M03`, `M04`, `M06`, `M07`, `M10` | the corrected fallback now has a full admitted broader-reasoning overlay | `GO` |

## What changed versus the historical `X6` story

| Historical-at-the-time read | Corrected current read |
|---|---|
| `X6` on historical `gemini-2.5-flash` stayed bounded away from review lanes | current `X6` on `gemini-3.1-flash-lite-preview` now has an admitted `M05` review row |
| `X6` stopped before `W5` from the historical `W4` gate | current `X6` now has an admitted `W5`-equivalent overlay through the refreshed `M03`, `M04`, `M06`, `M07`, `M10` rows |
| old fallback picture was incomplete and asymmetrical | current non-browser fallback picture is now complete across `M01..M10` and the active role-gap non-browser set |

## Current routing implication

| Topic | Accepted read |
|---|---|
| non-browser `X6` | no longer pending, no longer stopped before `W5`, and no longer carrying the old blanket review-ban language |
| browser `X6` | still restricted by the current strict `G08` fail and should remain described that way explicitly |
| compact tables | the current practical compact tables do not need a rank reshuffle from this overlay alone; `X6` remains the lowest current row because the browser fail and the later `G11/G14/G15` worker split still matter |

## Boundary

| Topic | Boundary |
|---|---|
| historical provenance | do not rewrite the 2026-04-14 wave files to pretend they already contained this corrected fallback evidence |
| current `X6` truth | use this overlay together with `runs/x6-corrected-fallback-refresh-2026-04-16.md` and `runs/gemini-catchup-g11-g18-2026-04-16.md` when reading the active `X6` profile |

