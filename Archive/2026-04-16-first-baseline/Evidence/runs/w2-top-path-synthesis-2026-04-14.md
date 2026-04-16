# W2 Top-Path Synthesis

Date: 2026-04-14
Owner: `$lead`
Status: `PASS`

## Scope

Combined synthesis for the completed `W2` top-path set:

- `X3` Claude native top
- `X4` Claude secret-backed fallback
- `X1` Codex top
- `X5` Gemini top

Covered tests:

- `M02` canonical-source conflict reconciliation
- `M06` security or threat memo
- `M07` performance memo
- `M10` resume and stale-context rejection

## Historical alignment note

This file remains a historical 2026-04-14 wave snapshot. Current routing should defer to `matrices/model-matrix-checkpoint-2026-04-15.md` and `matrices/model-only-recommendation-package-2026-04-15.md`, which incorporate the admitted role-gap wave, the stricter current `G08` browser result, and the repinned Gemini 3 HIGH reruns.

Execution caveats that remain part of the accepted evidence:

| Target | Caveat | Accepted handling |
|---|---|---|
| `X3` | PowerShell multiline-argument delivery silently degraded into greeting-only non-fixture answers in a pre-canonical probe | admitted `W2` rows use stdin/file delivery and the pre-canonical raw probe stays scratch-only evidence |
| `X4` | much broader ambient init surface than `X3`; `M07` run crossed the provisional per-run cost ceiling | keep `X4` as Claude provider-local fallback note only, not as a provider-order promotion |
| `X1` | launcher line still precedes the JSONL answer envelope | admitted as light noise because the answer remained cleanly extractable and no MCP was enabled |
| `X5` | intended isolated helper path hit auth bootstrap instability | admitted `W2` rows use direct current-config Gemini headless JSON; `tools.totalCalls = 0` and `gemini mcp list` was empty at capture time |

## Aggregate provider picture

| Target | Overall picture | Current bounded verdict |
|---|---|---|
| `X3` | strongest and cleanest across reconciliation, security, performance-methodology, and orchestration-resume lanes | reference top path |
| `X4` | semantically near-parity to `X3`, but materially broader ambient surface and higher runtime variance keep it fallback-only | near-substitute with provider-local fallback caveat |
| `X1` | strong slot-2 path; especially competitive on explicit resume discipline and still solid on security and performance memo quality | strong near-substitute to `X3` on many non-Claude lanes |
| `X5` | clean and correct, but repeatedly terser and less deep on `W2` reasoning-heavy work | bounded substitute only |

## Test-by-test signal

| Test | Strongest | Second | Third | Fourth | Key reason |
|---|---|---|---|---|---|
| `M02` | `X3` | `X4` | `X1` | `X5` | `X3` was the cleanest and most explicit on source-of-truth governance; `X4` was semantically near-identical |
| `M06` | `X3` | `X4` | `X1` | `X5` | `X3` best separated provider identity, transport path, and ambient-surface confounds |
| `M07` | `X3` | `X1` | `X4` | `X5` | `X3` had the best measurement protocol; `X1` was the best non-Claude answer; `X4` was strong but its own run overran the provisional ceiling |
| `M10` | `X1` | `X3` | `X4` | `X5` | `X1` was sharpest on explicit resume sequencing and stale-context rejection |

## Pairwise synthesis

### `X3↔X4`

| Field | Verdict |
|---|---|
| same conclusions | yes on all four `W2` tests |
| better grounded | `X3` |
| better structured | `X3` |
| deeper reasoning | `X3` by a small margin |
| cleaner output | `X3` |
| safer default | `X3` |
| overall pairwise verdict | `near-substitute` |
| routing implication | keep `claude` provider order unchanged; inside Claude prefer native `X3` first and record `X4` only as the provider-local secret-backed fallback path |

### `X3↔X1`

| Field | Verdict |
|---|---|
| source-of-truth and security work | `X3` leads slightly |
| performance-methodology work | `X3` leads |
| orchestration-resume work | `X1` leads slightly |
| overall pairwise verdict | `near-substitute` |
| routing implication | keep `claude` ahead of `codex` on reasoning-heavy advisory lanes; `codex` remains the best current slot-2 provider path |

### `X3↔X5`

| Field | Verdict |
|---|---|
| basic correctness | usually aligned |
| depth and grounding | `X3` leads clearly |
| structure and cleanliness | tie to slight `X3` lead |
| overall pairwise verdict | `bounded substitute only` |
| routing implication | `gemini` should not outrank `claude` on security, performance, orchestration, or higher-depth advisory lanes from current evidence |

### `X1↔X5`

| Field | Verdict |
|---|---|
| source-of-truth work | `X1` leads |
| security and performance memos | `X1` leads clearly |
| resume discipline | `X1` leads clearly |
| overall pairwise verdict | `near-substitute`, favoring `X1` |
| routing implication | keep `codex` ahead of `gemini` on the current advisory and review-adjacent lanes |

## Lane-priority snapshot

| Lane or lane set | Preferred slot 1 | Preferred slot 2 | Preferred slot 3 | Confidence | Provider-local note |
|---|---|---|---|---|---|
| `advisory.repo-continuity` | `claude` | `codex` | `gemini` | medium | inside Claude, `X3` first and `X4` fallback only |
| `advisory.security-transport` | `claude` | `codex` | `gemini` | medium | `X4` is semantically strong but remains a broader-envelope Claude path |
| `advisory.performance-benchmarking` | `claude` | `codex` | `gemini` | medium | `X4` performance guidance is usable, but its own run variance keeps it fallback-only |
| `lead.resume-orchestration` | `claude` | `codex` | `gemini` | medium | `X1` was best on `M10`, but current total evidence still keeps `claude` slot 1 overall |

## Interim recommendation

| Question | Current answer |
|---|---|
| best top-path model for `W2` reasoning-heavy advisory lanes | `X3` |
| best current fallback inside Claude | `X4`, but only as a provider-local fallback note |
| best non-Claude substitute | `X1` |
| best clean but lighter-weight option | `X5` |
| should provider order change from `claude > codex > gemini` after `W2` | no |
| should `X4` alter provider order directly | no |

## Next step

Move into `W3` on `X3`, `X4`, `X1`, and `X5` with `M08` and `M09`, then decide whether the top-path matrix is strong enough to justify fallback expansion into `W4`.
