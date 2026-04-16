# W1 Top-Path Synthesis

Date: 2026-04-14
Owner: `$lead`
Status: `PASS`

## Scope

Combined synthesis for the completed runnable `W1` top-path set:

- `X3` Claude native top
- `X1` Codex top
- `X5` Gemini top

Covered tests:

- `M01` bounded factual extraction
- `M03` ADR-style architecture memo
- `M04` phased delivery plan
- `M05` findings-only bounded diff review

`X4` remains outside the ranked comparison because the repo-canonical secret-backed fallback path is still blocked in the active shell.

## Historical alignment note

This file remains a historical 2026-04-14 wave snapshot, not the current exact 6-target synthesis. Later evidence unblocked `X4`, repinned Gemini targets, and updated the working routing layer in `matrices/model-matrix-checkpoint-2026-04-15.md` and `matrices/model-only-recommendation-package-2026-04-15.md`.

## Aggregate provider picture

| Target | Overall picture | Current bounded verdict |
|---|---|---|
| `X3` | strongest across reasoning-heavy, planning-heavy, and review-heavy lanes; no material misses on the completed top-path pack | reference top path |
| `X1` | consistently close second; strong factual, architecture, planning, and review signal with slightly less depth than `X3` | near-substitute to `X3` on many non-fallback lanes |
| `X5` | clean, disciplined, and usually correct, but repeatedly narrower or more generic on higher-depth lanes | bounded substitute only outside lighter factual support |

## Test-by-test signal

| Test | Strongest | Second | Third | Key reason |
|---|---|---|---|---|
| `M01` | tie `X3/X1/X5` | tie | tie | all 3 answered correctly and stayed grounded |
| `M03` | `X3` | `X1` | `X5` | `X3` had the best ADR depth and policy framing |
| `M04` | `X3` | `X1` | `X5` | `X3` was the only path to explicitly finish remaining `W1` work before synthesis |
| `M05` | `X3` | `X1` | `X5` | `X3` had the best review depth without false positives |

## Pairwise synthesis

### `X3↔X1`

| Field | Verdict |
|---|---|
| factual work | interchangeable to near-substitute |
| design or ADR work | `X3` leads slightly |
| planning work | `X3` leads slightly |
| review work | `X3` leads slightly |
| overall pairwise verdict | `near-substitute` |
| routing implication | keep `claude` ahead of `codex` on reasoning-heavy and review-heavy lanes; `codex` remains a strong slot-2 path |

### `X3↔X5`

| Field | Verdict |
|---|---|
| factual work | interchangeable on current evidence |
| design or ADR work | `X3` leads clearly |
| planning work | `X3` leads clearly |
| review work | `X3` leads clearly |
| overall pairwise verdict | `bounded substitute only` |
| routing implication | `gemini` should not outrank `claude` on reasoning-heavy or review-heavy lanes from current evidence |

### `X1↔X5`

| Field | Verdict |
|---|---|
| factual work | interchangeable to near-substitute |
| design or ADR work | `X1` leads slightly |
| planning work | `X1` leads slightly |
| review work | `X1` leads slightly |
| overall pairwise verdict | `near-substitute` |
| routing implication | `codex` should stay ahead of `gemini` on planning-heavy and review-heavy lanes from current evidence |

## Lane-priority snapshot

| Lane or lane set | Preferred slot 1 | Preferred slot 2 | Preferred slot 3 | Confidence | Notes |
|---|---|---|---|---|---|
| `advisory.repo-understanding` | `claude` or `codex` | `codex` or `claude` | `gemini` | low | `M01` alone keeps this close; waits for `M02` and `M10` |
| `advisory.design-adr` | `claude` | `codex` | `gemini` | medium | reinforced by `M03` and `M04` |
| `planner.delivery-phasing` | `claude` | `codex` | `gemini` | medium | `M04` created the first real separation |
| `review.pre-pr` | `claude` | `codex` | `gemini` | medium | `M05` created the first review-heavy separation |
| `review.performance-architecture` | `claude` | `codex` | `gemini` | medium | supported by `M03` plus `M05`; still awaits `M07` |

## Historical `X4` note

| Field | Current state |
|---|---|
| provider status | still `claude`, not a separate provider |
| execution status in this historical wave | blocked in the then-active shell |
| later correction | later 2026-04-14 and 2026-04-15 artifacts admit `X4` as the repo-canonical Claude fallback path |
| routing effect today | keep `X4` as a provider-local Claude path note only; do not promote it into provider order |

## Interim recommendation

| Question | Current answer |
|---|---|
| best top-path model for reasoning-heavy roles | `X3` |
| strongest fallback within current runnable top-path set | `X1` as closest substitute to `X3` |
| best clean but lighter-weight option | `X5` |
| should `gemini` move above `codex` anywhere yet | no, not from current `W1` evidence |
| should `codex` overtake `claude` anywhere yet | no, not from current `W1` evidence |

## Next step

Move into `W2` on `X3`, `X1`, and `X5` with `M02`, `M06`, `M07`, and `M10`, unless the operator decides to spend one bounded retry on restoring the blocked `X4` secret-backed fallback path first.
