Date: 2026-04-15
Owner: `$lead`
Status: `PASS`

## Purpose

This artifact explains the current benchmark design, notation, and reading rules for the result tables.

## Experiment scope

| Axis | Current scope |
|---|---|
| primary track | model-only benchmark |
| active population | `X1..X6` plus `Q1` |
| current baseline | first practical 7-model role-family checkpoint |
| deferred track | MCP-impact |

## Model population

| ID | Short label | Meaning |
|---|---|---|
| `X1` | `gpt-5.4` | Codex top |
| `X2` | `gpt-spark` | Codex fallback |
| `X3` | `opus 4.6max` | native Claude top |
| `X4` | `Claude China` | repo-canonical secret-backed Claude path |
| `X5` | `gemini3.1pro` | Gemini top |
| `X6` | `gemini3.1flash-lite-preview` | Gemini fallback |
| `Q1` | `qwen3-max` | current admitted Qwen path |

## Test families

### Model-only pack

| Test | Main role pressure |
|---|---|
| `M01` | factual extraction with file refs |
| `M02` | source-of-truth reconciliation |
| `M03` | ADR / tradeoff reasoning |
| `M04` | phased planning |
| `M05` | findings-only review |
| `M06` | security reasoning |
| `M07` | performance reasoning |
| `M08` | bounded micro-fix |
| `M09` | root-cause debugging |
| `M10` | resume / continuity discipline |

### Role-gap and worker-trust pack

| Family | Meaning |
|---|---|
| `G01..G10` | role-gap expansion beyond the original `M01..M10` core |
| `G08` | supplemental browser-runtime / Playwright note, not part of primary UI scoring |
| `G11` | bounded worker path-discovery |
| `G12` | continuity decay + build owner discovery |
| `G13` | path recall after prior edits |
| `G14` | multi-step worker persistence |
| `G15` | messy worker ownership quality separation |

## Wave vocabulary

| Wave | Meaning |
|---|---|
| `W1` | advisory / review-heavy baseline reading |
| `W2` | top-path reasoning and planning wave |
| `W3` | bounded implementation / debugging wave |
| `W4` | fallback mechanical admissibility wave |
| `W5` | fallback reasoning expansion wave |

## Scoring and validity

| Term | Meaning |
|---|---|
| `PASS` | admitted result |
| `REVISE` | artifact is materially weaker or brittle and needs correction before admission |
| `BLOCKED` | external blocker, not benchmark failure |
| `Invalid` | run excluded by hard validity gates |
| `Borderline` | run is scorable but penalized |

## Pairwise legend

Used mainly in `matrices/full-model-comparison-matrix-2026-04-15.md`.

| Marker | Meaning |
|---|---|
| `INT` | interchangeable |
| `NS` | near-substitute |
| `BS` | bounded substitute only |
| `NS/split` | near-substitute overall, but winner depends on lane family |
| `BS/split` | bounded-only substitution overall, with lane-dependent edge |
| `direct` | verdict comes from direct admitted comparison evidence |
| `composite` | verdict is synthesized from multiple admitted artifacts |

## Reading rules

| Rule | Meaning |
|---|---|
| baseline before pairwise | read the baseline checkpoint table first, then the pairwise matrix |
| role-spectrum over compressed lane table | use the fuller role-spectrum artifact when the question is about real roles, not compressed routing lanes |
| primary UI before browser note | read static UI, a11y, UX, and visualization rows from non-browser evidence first; use `G08` only for browser-runtime questions |
| broad trust is stricter than green fixture passes | a model can pass bounded fixtures and still stay outside the broad real-project trust tier |
| provider outage is not auto-demotion | same-day runtime instability must not silently become a permanent ranking verdict |

## Current methodological boundary

| Boundary | Current accepted read |
|---|---|
| broad trust | only `gpt-5.4` and `opus 4.6max` are broadly trusted for messy real-project execution |
| `Claude China` | useful and often strong, but still bounded rather than broadly trusted |
| `gpt-spark` | strongest current overflow worker path, but still not in the broad-trust tier |
| browser evidence | `G08` remains useful, but it is now treated as supplemental browser-runtime evidence instead of primary UI scoring |
| next benchmark move | harder probes against the surprising rows, not broad reruns of the same soft lanes |
