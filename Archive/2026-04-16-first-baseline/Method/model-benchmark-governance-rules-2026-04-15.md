Date: 2026-04-15
Owner: `$lead`
Status: `PASS`

## Purpose

Define the operating rules for the **model benchmark-testing line** of this item.

These rules exist so benchmark work stays:

- reproducible
- readable
- incrementally comparable
- explicit about what changed and why

## Scope

These rules govern:

- benchmark result tables
- benchmark-facing documentation
- admitted benchmark evidence
- baseline checkpoints
- hardening-wave additions

They do not replace the deeper task-wide governance already stored in `design.md`, `research.md`, `status.md`, `runs/`, and `matrices/`.

## Canonical storage model

| Surface | Role |
|---|---|
| `benchmarks/` | human-facing benchmark package |
| `matrices/` | canonical ranking and comparison artifacts |
| `runs/` | canonical run syntheses, prompt contracts, scoring rubric, and run-ledger discipline |
| `fixtures/` | benchmark fixtures and probe workspaces |
| `status.md` | current stage, primary task, and next concrete move |
| `research.md` | accepted factual and methodological findings |

## Benchmark package rule

| Rule | Meaning |
|---|---|
| every active benchmark line must have a `benchmarks/` entry point | result reading should not require hopping through raw internal files |
| every benchmark package must expose results, design, and notation | a table without experiment context is not enough |
| benchmark-facing package files should point to deeper canonical artifacts, not duplicate them blindly | avoid split-brain copies |

## Required benchmark package contents

| Artifact class | Required content |
|---|---|
| results index | where to start and which tables are current |
| experiment design and notation | population, wave vocabulary, validity language, legend, and reading rules |
| hardening-wave target list | what is suspicious in the current baseline and should be challenged next |

## Baseline checkpoint rule

| Rule | Meaning |
|---|---|
| every meaningful ranking state must be frozen as an explicit baseline checkpoint | prevents silent table drift |
| a baseline checkpoint is descriptive, not eternal | it is the current read until stronger admitted evidence arrives |
| later waves must correct the baseline in a new artifact layer, not rewrite history silently | preserve provenance |

## Result-change rule

| Rule | Meaning |
|---|---|
| no rank changes on intuition alone | only admitted evidence can move the table |
| same-day provider outages do not automatically equal demotion | provider instability must stay separate unless admitted into canon as ranking evidence |
| green bounded fixtures do not automatically create broad trust | broad worker trust remains a stricter judgment layer |

## Hardening-wave rule

| Rule | Meaning |
|---|---|
| after a baseline checkpoint, do not rerun the whole matrix blindly | target the suspicious rows |
| suspicious rows are where fallback or lighter paths outrank stronger incumbents | those rows are most likely to be benchmark-soft |
| each hardening-wave probe must declare what weakness it is trying to expose | no vague “harder test” language |
| every new hardening probe must have broken-state evidence and a control-fixed pass surface before model execution begins | fixture-ready means both sides exist |

## Probe design rule

| Rule | Meaning |
|---|---|
| every probe must target one primary failure mode | avoid mixed ambiguous verdicts |
| decoys are allowed, but the owning path must still be objectively recoverable | difficulty must stay fair |
| prompts must forbid the easy invalid shortcuts | for example: exact-path hardcoding, decoy edits, or broad refactors |
| required verification commands must be explicit and minimal | every row should know what counts as green |

## UI scoring rule

| Rule | Meaning |
|---|---|
| primary UI ranking should use non-browser evidence | use static UI structure, accessibility, UX, visualization, and bounded UI-worker evidence first |
| browser automation belongs in an auxiliary lane | Playwright or browser-runtime checks may stay in canon, but they should not define the default UI ranking |
| browser failures do not automatically demote non-browser UI quality | keep browser-runtime weakness separated from static UI review and implementation evidence |

## Table-writing rule

| Rule | Meaning |
|---|---|
| use compact Markdown tables for rankings and mappings | keep benchmark reading scannable |
| normalize short labels and keep them stable inside an active wave | avoid one model having multiple names in active tables |
| if a label changes, update the active comparison-facing surfaces together | avoid mixed naming in current canon |

## Artifact update rule

When a benchmark result changes materially:

1. update the owning canonical result artifact
2. update `status.md`
3. append the accepted finding to `research.md`
4. if the change affects reading order, refresh the benchmark-facing package
5. write a session log in `.reports/`

## Provenance rule

| Rule | Meaning |
|---|---|
| historical artifacts stay historical | do not retroactively rewrite old waves to look cleaner than they were |
| corrective reruns get explicit new artifacts | preserve both the old and corrected read |
| benchmark package should surface the current read, while deeper canon preserves the path taken to get there | current usability plus historical honesty |

## Reading priority

Read benchmark artifacts in this order:

1. `benchmarks/benchmark-results-index-*.md`
2. current baseline checkpoint
3. experiment design and notation
4. hardening-wave targets
5. deeper pairwise or role-spectrum matrices only if needed

## Current application

| Current state | Meaning |
|---|---|
| first baseline checkpoint exists | current 7-model role-family read is fixed |
| next wave is hardening-focused | target rows where `gpt-spark` or `Claude China` currently outrank stronger incumbents |
| Gemini is temporarily parked as a provider-availability issue | today's instability is recorded, but not silently promoted into a permanent ranking rule |
