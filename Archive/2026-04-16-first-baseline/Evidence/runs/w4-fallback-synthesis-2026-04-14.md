# W4 Fallback Synthesis

Date: 2026-04-14
Owner: `$lead`
Status: `PASS`

## Scope

Completed synthesis for the full `W4` fallback set:

- `X2` Codex fallback (`gpt-5.3-codex-spark`)
- `X6` Gemini fallback (`gemini-2.5-flash`)

Covered tests:

- `M01` bounded factual extraction
- `M05` findings-only review
- `M08` bounded implementation micro-fix
- `M09` root-cause debugging

## Historical alignment note

This file remains a historical 2026-04-14 fallback-wave snapshot. Later Gemini 3 HIGH reruns materially strengthened `X6` on the non-browser slice, so the old stop-before-`W5` language below must be read as historical-at-the-time rather than as the current routing rule.

## Aggregate fallback picture

| Target | Overall picture | Current bounded verdict |
|---|---|---|
| `X2` | strong fallback across all `W4` rows; heavy runtime-noise penalty, but no admitted answer failure | near-substitute to `X1` for factual, review, and bounded mechanical lanes; eligible for `W5` |
| `X6` | mixed fallback in the historical `gemini-2.5-flash` batch; clean factual row and admissible mechanical rows, but review failed twice on a clean surface | historical bounded substitute only for factual and bounded mechanical lanes; later Gemini 3 HIGH evidence supersedes the old stop-before-`W5` rule |

## Test-by-test signal

| Test | Stronger fallback | Weaker fallback | Key reason |
|---|---|---|---|
| `M01` | `X2` slight edge | `X6` | both were valid and exact; `X2` gave slightly richer routing phrasing while `X6` stayed cleaner operationally |
| `M05` | `X2` | `X6` | `X2` found the real contract regressions and stayed usefully specific; `X6` failed twice with duplicate, generic findings on a clean surface |
| `M08` | `X2` slight edge | `X6` | both landed the right minimal deletion; `X2` was more explicit about why the fix was minimal, while `X6` had tool misses and noisy verification output |
| `M09` | `X2` | `X6` | both identified the real root cause; `X2` was more evidence-rich and concrete, while `X6` stayed correct but shallower |

## Pairwise synthesis

### `X1↔X2`

| Field | Verdict |
|---|---|
| factual extraction | near parity |
| review quality | `X1` cleaner, but `X2` remains admissible and useful |
| implementation / debugging | `X1` still cleaner; `X2` stays viable despite runtime noise |
| overall pairwise verdict | `near-substitute` |
| routing implication | Codex fallback is now admissible for overflow factual, review, and bounded mechanical lanes; continue to prefer `X1` when available |

### `X5↔X6`

| Field | Verdict |
|---|---|
| factual extraction | near parity |
| review quality | `X6` fails; `X5` remains clearly ahead |
| implementation / debugging | `X6` is usable but lighter and shallower |
| overall pairwise verdict | `bounded substitute only` |
| routing implication | Gemini fallback may be used for factual and bounded mechanical overflow, but should stay out of review lanes |

### `X2↔X6`

| Field | Verdict |
|---|---|
| factual extraction | both admissible; slight `X2` edge |
| review quality | `X2` clearly ahead |
| implementation / debugging | `X2` ahead |
| overall pairwise verdict | `bounded substitute only`, favoring `X2` |
| routing implication | when only fallback paths remain, prefer Codex fallback before Gemini fallback for non-trivial overflow lanes |

## Lane-priority snapshot

| Lane or lane set | Codex fallback guidance | Gemini fallback guidance | Confidence |
|---|---|---|---|
| `analyst.factual-extraction` | `X2` admitted | `X6` admitted as a lighter last-resort fallback | medium |
| `review.findings-only` | `X2` admitted | do not use `X6` from current evidence | high |
| `worker.default-implementation` | `X2` admitted | `X6` admitted only for bounded mechanical patches | medium |
| `worker.root-cause-debugging` | `X2` admitted | `X6` admitted, but with lower expected depth | medium |

## W5 gate decision

| Target | W5 decision | Reason |
|---|---|---|
| `X2` | `proceed` | passed all `W4` rows; main penalty is runtime noise, not answer invalidity |
| `X6` | `stop` | this was the correct decision from the historical `gemini-2.5-flash` evidence, but it is no longer the current exact-target rule after the later Gemini 3 HIGH reruns |

## Interim recommendation

| Question | Current answer |
|---|---|
| strongest current fallback overall | `X2` |
| safest factual-only fallback | `X2`, with `X6` still usable as lighter overflow |
| should Gemini fallback be allowed on review lanes from this historical wave alone | no |
| should Codex fallback advance into broader reasoning tests | yes |
| should Gemini fallback advance into `W5` right now from this historical wave alone | no |

## Next step

Write the first-pass full 6-target model matrix, then continue into `W5` for `X2` only unless later evidence justifies reopening `X6`.
