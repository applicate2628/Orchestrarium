Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

This artifact fixes a real readability problem in the current benchmark package:

- the compact baseline table showed the final rank,
- but it hid where `W1..W5` and `G01..G10` were actually folded in.

Use this file when the question is:

- "did we mis-score `G01..G07`?"
- "where are `W1..W5` in the final table?"
- "what evidence families actually feed each practical lane?"

This is now the **default baseline view** for the benchmark package.

## Accepted verification on `G01..G07`

| Area | Accepted read |
|---|---|
| `G01..G07` correctness | no current canon suggests a scoring mistake; the admitted role-gap wave still records `PASS` for all six original providers across `G01..G07` |
| `X6` refresh impact | the corrected `X6` refresh on 2026-04-16 did not reopen any `G01..G07` failure; it kept them all admitted under `gemini-3.1-flash-lite-preview` |
| actual problem | the compact baseline matrix compressed provenance too aggressively; the methodology became hard to read even though the underlying admitted evidence stayed consistent |

## Evidence-family legend

| Family | Meaning | Admitted row set |
|---|---|---|
| `W1` | advisory and review-heavy top-path baseline | `M01`, `M03`, `M04`, `M05` |
| `W2` | reasoning, security, performance, and resume top-path wave | `M02`, `M06`, `M07`, `M10` |
| `W3` | bounded implementation and debugging top-path wave | `M08`, `M09` |
| `W4` | fallback mechanical admissibility wave | `M01`, `M05`, `M08`, `M09` |
| `W5` | fallback reasoning expansion wave | `M03`, `M04`, `M06`, `M07`, `M10` |
| `G01` | roadmap priority and milestone triage | product and roadmap gap evidence |
| `G02` | product brief and scope clarification | intake and ambiguity-reduction evidence |
| `G03` | reliability and rollout safety | degradation and rollback evidence |
| `G04` | algorithmic or numerical proof framing | scientist-style reasoning evidence |
| `G05` | toolchain or build-break diagnosis | build and reproducibility evidence |
| `G06` | backend, data, or platform implementation | non-UI worker evidence |
| `G07` | static UI structure and patch | non-browser UI structure evidence |
| `G08` | static UI evidence triage | active non-browser UI evidence lane |
| `G09` | accessibility and UX review | review-side UI quality evidence |
| `G10` | graphics, visualization, and decorative visual review | visual reasoning evidence |
| `G11..G18` | worker-trust and hardening pack | owner discovery, continuity, persistence, and messy-worker separation |
| legacy browser note | historical current strict browser parity | auxiliary browser-runtime context only |

## Reading rule

| Rule | Meaning |
|---|---|
| `W1..W5` are not final lanes | they are execution waves over the `M` pack |
| `G01..G10` are not replacements for `W1..W5` | they extend the benchmark into missing role families |
| final lane table is synthetic | each practical lane below is a synthesis over one or more `W` waves plus zero or more `G` families |
| evidence columns are dominant supports | they show the main admitted evidence families behind the row, not a hidden arithmetic scoring formula |
| this file is the package default | if a human asks for the current baseline table, open this file first |

## Combined baseline matrix

| Итоговая линия | Основа `W` | Основа `G` / later probes | `1` | `2` | `3` | `4` | `5` | `6` | `7` |
|---|---|---|---|---|---|---|---|---|---|
| Разбор репозитория / source-of-truth | `W1:M01`, `W2:M02` | `G02` | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| ADR / архитектура / планирование | `W1:M03,M04`, `W2:M02,M10` | `G03,G04` | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| Product brief / roadmap framing | `W1:M04`, `W2:M02` | `G01,G02` | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| Security / perf / reliability / scientist-style | `W2:M06,M07`, `W1:M03` | `G03,G04` | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| Pre-PR review / QA / findings-only | `W1:M05`, `W4:M05` | `G09` | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| Accessibility / UX static review | `W1:M05` | `G08,G09` | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| Static visual / visualization review | `W1:M05` | `G10` | `opus 4.6max` | `Claude China` | `gpt-5.4` | `gpt-spark` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| Реализация фич / багфиксов | `W3:M08,M09`, `W4:M08,M09` | `G06,G07,G11` | `gpt-5.4` | `Claude China` | `gpt-spark` | `opus 4.6max` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| Systems / performance implementation | `W3:M08,M09`, `W2:M07` | `G05,G06,G15` | `gpt-5.4` | `Claude China` | `gpt-spark` | `opus 4.6max` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| Toolchain / build / project-root ownership | `W3:M09`, `W2:M10` | `G05,G12,G15,G16` | `gpt-5.4` | `gpt-spark` | `opus 4.6max` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` | `Claude China` |
| Долгий автономный messy worker-run | `W2:M10`, `W5:M10` | `G12,G13,G14,G15,G17,G18` | `opus 4.6max` | `gpt-5.4` | `gpt-spark` | `Claude China` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| UI structural modernization | `W3:M08,M09` | `G07,G08,G11,G13` | `gpt-5.4` | `Claude China` | `gpt-spark` | `opus 4.6max` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| UI surgical cleanup | `W3:M08,M09` | `G07,G11,G13` | `gpt-5.4` | `Claude China` | `gpt-spark` | `opus 4.6max` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |
| Visual / icon decorative edits | `W3:M08`, `W1:M05` | `G10` | `gpt-5.4` | `Claude China` | `gpt-spark` | `opus 4.6max` | `qwen3-max` | `gemini3.1pro` | `gemini3.1flash-lite-preview` |

## Legacy browser-runtime note

| Topic | Current note |
|---|---|
| supplemental browser evidence family | legacy browser parity artifacts from `runs/g08-browser-parity-*.md` |
| role in baseline | auxiliary runtime context only |
| current strict read | `claude` and `codex` pass current strict browser parity; current `gemini` paths fail; this should be read as browser-runtime asymmetry, not as the default UI-quality score |

## Method boundary

| Boundary | Accepted read |
|---|---|
| this file does not replace the raw run artifacts | it only makes their aggregation visible in one place |
| this file does not claim a strict numeric formula | the baseline is still an evidence-backed synthesis, not a spreadsheet score sum |
| `G01..G07` being all `PASS` does not mean they all dominate every row equally | they extend coverage and inform specific lane families |
| browser asymmetry stays explicit | the legacy browser note remains separate and is no longer folded into the primary UI rows |
