# W3 Top-Path Synthesis

Date: 2026-04-14
Owner: `$lead`
Status: `PASS`

## Scope

Combined synthesis for the completed `W3` top-path set:

- `X3` Claude native top
- `X4` Claude secret-backed fallback
- `X1` Codex top
- `X5` Gemini top

Covered tests:

- `M08` bounded implementation micro-fix
- `M09` root-cause debugging

## Historical alignment note

This file remains a historical 2026-04-14 wave snapshot. Current routing should defer to `matrices/model-matrix-checkpoint-2026-04-15.md` and `matrices/model-only-recommendation-package-2026-04-15.md`, which integrate the later role-gap wave, the stricter current `G08` browser result, and the repinned Gemini 3 HIGH reruns.

## Aggregate provider picture

| Target | Overall picture | Current bounded verdict |
|---|---|---|
| `X1` | strongest overall on `W3`; noisy runtime envelope, but best debugging evidence and a clean minimal fix | reference top path for bounded implementation and debugging lanes |
| `X4` | strongest Claude-side `W3` path; exact micro-fix and strong debugging rerun, but broad ambient surface and high run cost remain real penalties | near-substitute to `X1`; preferred Claude-local path for `W3`-style lanes |
| `X5` | clean and disciplined; excellent micro-fix row and good debugging row, but slightly shallower than `X1` and `X4` | bounded substitute with strong cleanliness |
| `X3` | mixed but now fully admissible on `W3`; weakest micro-fix row, then a clean corrective `M09` rerun once native Claude stopped using the wrong `--bare` benchmark path | valid but still not preferred for bounded implementation or debugging from current evidence |

## Test-by-test signal

| Test | Strongest | Second | Third | Fourth | Key reason |
|---|---|---|---|---|---|
| `M08` | tie `X4/X5` | `X1` | `X3` | `X4` and `X5` both landed the exact minimal deletion; `X1` was also minimal but noisier; `X3` fixed the bug with an unnecessary reordering-plus-filter change |
| `M09` | `X1` | `X4` | `X3` | `X5` | `X1` still had the best evidence-backed root-cause memo; `X4` remained strong; `X3` cleanly recovered on the corrected native path; `X5` stayed correct but slightly shallower |

## Pairwise synthesis

### `X3↔X4`

| Field | Verdict |
|---|---|
| micro-fix quality | `X4` leads clearly |
| debugging quality | `X4` leads slightly after the corrected `X3/M09` rerun |
| operational cleanliness | `X3` has the narrower intended native surface when run without `--bare`; `X4` still carries the broader ambient envelope |
| overall pairwise verdict | `near-substitute`, favoring `X4` for `W3` lanes |
| routing implication | keep `claude` as one provider, but inside Claude still prefer `X4` over `X3` for bounded implementation or debugging lanes because `M08` remains the differentiator |

### `X1↔X4`

| Field | Verdict |
|---|---|
| micro-fix quality | slight `X4` edge |
| debugging quality | `X1` edge |
| operational cleanliness | `X4` answer envelope cleaner; `X1` runtime noisier |
| overall pairwise verdict | `near-substitute` |
| routing implication | current evidence supports `codex` slot `1` and `claude` slot `2` for bounded implementation-debug lanes, while keeping a strong Claude-local note that `X4` is the right Claude path for those lanes |

### `X1↔X5`

| Field | Verdict |
|---|---|
| micro-fix quality | near tie |
| debugging quality | `X1` leads |
| overall pairwise verdict | `near-substitute`, favoring `X1` |
| routing implication | keep `codex` ahead of `gemini` for bounded implementation-debug work |

### `X4↔X5`

| Field | Verdict |
|---|---|
| micro-fix quality | near tie |
| debugging quality | `X4` leads |
| overall pairwise verdict | `near-substitute`, favoring `X4` |
| routing implication | `gemini` remains usable, but Claude fallback stays ahead on richer debugging lanes |

## Lane-priority snapshot

| Lane or lane set | Preferred slot 1 | Preferred slot 2 | Preferred slot 3 | Confidence | Provider-local note |
|---|---|---|---|---|---|
| `worker.default-implementation` | `codex` | `claude` | `gemini` | medium | inside Claude prefer `X4`; current `X3` native path is not preferred for this lane |
| `worker.ui-surgical-patch-cleanup` | `codex` | `claude` | `gemini` | low | same current ordering as bounded implementation; visual-specific evidence is still deferred |
| `worker.systems-performance-implementation` | `codex` | `claude` | `gemini` | low | `W3` is suggestive only; keep the result provisional until `W4` fallback data exists |

## Interim recommendation

| Question | Current answer |
|---|---|
| best current path for bounded implementation micro-fixes | `X1` and `X4` are the leading pair, with `X4` strongest inside Claude and `X1` strongest overall |
| best current path for root-cause debugging | `X1` |
| best clean but lighter-weight alternative | `X5`, with `X3` now re-admitted as a valid but lower-priority native Claude option |
| should `claude` stay ahead of `codex` on these `W3` lanes | no; `W3` is the first wave that currently points to `codex` slot `1` and `claude` slot `2` on bounded implementation-debug work |
| should `X4` change provider order directly | no; it changes Claude-local path guidance first |

## Next step

Move into `W4` fallback expansion on `X2` and `X6` using `M08` and `M09`, then decide whether the model-only matrix is strong enough to write first-pass `externalPriorityProfiles` recommendations by lane.
