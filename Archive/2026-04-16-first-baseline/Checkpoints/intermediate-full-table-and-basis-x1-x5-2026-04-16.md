Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

Fix an explicit intermediate checkpoint for the benchmark line:

- keep one compact full-table view across the current model surface
- define one practical **basis working variant** restricted to `X1..X5`
- freeze the basis variant for continued work while `X4` and `X5` are temporarily deferred from fresh fairness-sensitive tests because of current extreme latency or availability drag

This artifact does **not** replace the default provenance-heavy baseline:

- `benchmarks/combined-baseline-wave-gap-matrix-2026-04-16.md`

It is the operator-facing checkpoint for "what the table currently is" and "which subset we actively keep working with next."

## Model legend

| ID | Current compact label |
|---|---|
| `X1` | `gpt-5.4` |
| `X2` | `gpt-spark` |
| `X3` | `opus 4.6max` |
| `X4` | `Claude China` |
| `X5` | `gemini3.1pro` |
| `X6` | `gemini3.1flash-lite-preview` |
| `Q1` | `qwen3-max` |

## Current full compact table

| `#` | Линия | `1` | `2` | `3` | `4` | `5` | `6` | `7` |
|---|---|---|---|---|---|---|---|---|
| `1` | `W1` advisory and review-heavy top-path wave | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| `2` | `W2` reasoning, security, performance, and resume top-path wave | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| `3` | `W3` bounded implementation and debugging top-path wave | `gpt-5.4` | `Claude China` | `gpt-spark` | `opus 4.6max` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| `4` | `W4` fallback mechanical admissibility wave | `gpt-spark` | `gemini3.1flash-lite-preview` |  |  |  |  |  |
| `5` | `W5` fallback reasoning expansion wave | `gpt-spark` | `gemini3.1flash-lite-preview` |  |  |  |  |  |
| `6` | Разбор репозитория / source-of-truth | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| `7` | ADR / архитектура / планирование | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| `8` | Product brief / roadmap framing | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| `9` | Security / perf / reliability / scientist-style | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| `10` | Pre-PR review / QA / findings-only | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| `11` | Accessibility / UX static review | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| `12` | Static visual / visualization review | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| `13` | Реализация фич / багфиксов | `gpt-5.4` | `Claude China` | `gpt-spark` | `opus 4.6max` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| `14` | Systems / performance implementation | `gpt-5.4` | `Claude China` | `gpt-spark` | `opus 4.6max` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| `15` | Toolchain / build / project-root ownership | `gpt-5.4` | `gpt-spark` | `opus 4.6max` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` | `Claude China` |
| `16` | Долгий автономный messy worker-run | `opus 4.6max` | `gpt-5.4` | `gpt-spark` | `Claude China` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| `17` | UI structural modernization | `gpt-5.4` | `Claude China` | `gpt-spark` | `opus 4.6max` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| `18` | UI surgical cleanup | `gpt-5.4` | `Claude China` | `gpt-spark` | `opus 4.6max` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| `19` | Visual / icon decorative edits | `gpt-5.4` | `Claude China` | `gpt-spark` | `opus 4.6max` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| `20` | `G08` static UI evidence | `opus 4.6max` | `gpt-5.4` | `gpt-spark` | `gemini3.1flash-lite-preview` | `Claude China` | `qwen3-max` | `gemini3.1pro` |

## Basis working variant: `X1..X5`

This basis view is the active narrowed comparison surface for continued work.

Rules:

- keep only `X1`, `X2`, `X3`, `X4`, `X5`
- preserve current admitted relative order from the full table
- do **not** silently rerank because `X6` or `Q1` are removed
- treat `X4` and `X5` as **frozen on current admitted evidence** for now; fresh fairness-sensitive tests for those two rows are deferred until current latency or availability pressure drops

| `#` | Линия | `1` | `2` | `3` | `4` | `5` |
|---|---|---|---|---|---|---|
| `1` | `W1` advisory and review-heavy top-path wave | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `gemini3.1pro` |
| `2` | `W2` reasoning, security, performance, and resume top-path wave | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `gemini3.1pro` |
| `3` | `W3` bounded implementation and debugging top-path wave | `gpt-5.4` | `Claude China` | `gpt-spark` | `opus 4.6max` | `gemini3.1pro` |
| `4` | `W4` fallback mechanical admissibility wave | `gpt-spark` |  |  |  |  |
| `5` | `W5` fallback reasoning expansion wave | `gpt-spark` |  |  |  |  |
| `6` | Разбор репозитория / source-of-truth | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `gemini3.1pro` |
| `7` | ADR / архитектура / планирование | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `gemini3.1pro` |
| `8` | Product brief / roadmap framing | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `gemini3.1pro` |
| `9` | Security / perf / reliability / scientist-style | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `gemini3.1pro` |
| `10` | Pre-PR review / QA / findings-only | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `gemini3.1pro` |
| `11` | Accessibility / UX static review | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `gemini3.1pro` |
| `12` | Static visual / visualization review | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `gemini3.1pro` |
| `13` | Реализация фич / багфиксов | `gpt-5.4` | `Claude China` | `gpt-spark` | `opus 4.6max` | `gemini3.1pro` |
| `14` | Systems / performance implementation | `gpt-5.4` | `Claude China` | `gpt-spark` | `opus 4.6max` | `gemini3.1pro` |
| `15` | Toolchain / build / project-root ownership | `gpt-5.4` | `gpt-spark` | `opus 4.6max` | `gemini3.1pro` | `Claude China` |
| `16` | Долгий автономный messy worker-run | `opus 4.6max` | `gpt-5.4` | `gpt-spark` | `Claude China` | `gemini3.1pro` |
| `17` | UI structural modernization | `gpt-5.4` | `Claude China` | `gpt-spark` | `opus 4.6max` | `gemini3.1pro` |
| `18` | UI surgical cleanup | `gpt-5.4` | `Claude China` | `gpt-spark` | `opus 4.6max` | `gemini3.1pro` |
| `19` | Visual / icon decorative edits | `gpt-5.4` | `Claude China` | `gpt-spark` | `opus 4.6max` | `gemini3.1pro` |
| `20` | `G08` static UI evidence | `opus 4.6max` | `gpt-5.4` | `gpt-spark` | `Claude China` | `gemini3.1pro` |

## Deferred-latency note

| Row | Current defer reason | Defer scope |
|---|---|---|
| `X4` / `Claude China` | operator-declared extreme current latency or availability drag | future fairness-sensitive tests |
| `X5` / `gemini3.1pro` | extreme upstream responsiveness or service-side latency; even clean-laptop smoke remains slow | future fairness-sensitive tests |

## Accepted current working read

| Topic | Accepted read |
|---|---|
| full current surface | keep the 7-model full compact table above as the operator checkpoint |
| basis working set | use `X1..X5` as the narrowed working comparison surface for the next phase |
| `X4` / `X5` | freeze their current admitted placements inside the basis table; do not spend fairness-sensitive benchmark cycles on them until latency improves |
| next benchmark pressure | if we continue immediately, bias new harder probes toward the currently more responsive rows while keeping `X4` and `X5` frozen in the basis surface |
