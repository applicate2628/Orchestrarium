Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This file defines the v1 scoring contract and publication model for the role-complete benchmark redesign.

It replaces the old pack-first or line-family-first publication surface with a role-first scorecard.

## V3 Full-Hardening Update

The completed `S01..S33 + N01..N07` full-v2 pass rates exposed a ceiling effect: rows such as
`40 / 40` and `39 / 40` are no longer sufficient classification evidence. Treat those rows as
`pre-v3 baseline` only until they are replaced by hardened evidence.

V3 hardening must make pass/fail depend on role-specific reasoning artifacts, not only on section
presence and keyword coverage.

| Hardening rule | Meaning |
|---|---|
| replace stale lines in place | update the current live result/evidence surfaces instead of creating parallel stale copies |
| structural ledgers over prose | require source ledgers, decision tables, trace tables, non-claim ledgers, or fix ledgers where a role can otherwise pass with generic prose |
| source binding | factual, advisory, architecture, and review outputs must bind claims to concrete sources or inspected surfaces |
| non-claim discipline | tied evidence, quota, runtime routes, and model-capability claims must stay separate from confirmed facts |
| forbidden-action checks | verifiers should name actions that must not happen, such as adapter-side lane parsing or review-role implementation |
| ceiling-effect downgrade | a clean binary sweep on weak contracts is not a winner claim; publish it as baseline until hardened rerun evidence exists |

## Score dimensions

| Dimension | Meaning |
|---|---|
| `correctness` | solved the benchmarked task correctly |
| `role_fidelity` | behaved like the target role rather than a generic assistant |
| `scope_discipline` | stayed inside the allowed surface, artifact contract, and ownership seam |
| `synthesis_quality` | structured, prioritized, and framed the output well when judgment mattered |
| `verification_cleanliness` | validated or justified without drift, noise, or false certainty |
| `runtime_cleanliness` | completed without transport, tool, or runtime pollution |

## Raw scoring scale

Each dimension is scored on a fixed `0..5` raw scale before weights are applied.

| Raw score | Meaning |
|---|---|
| `0` | absent, wrong, or contract-breaking |
| `1` | major miss with little salvageable benchmark value |
| `2` | partial result with serious errors, widening, or role drift |
| `3` | solid but incomplete or noisy pass |
| `4` | strong result with minor weakness only |
| `5` | clean benchmark-grade pass |

Weighted points are computed as:

- `dimension_points = raw_score / 5 * weight`
- `total_score = sum(dimension_points)`

This keeps every surface on a `0..100` scale while preserving the role-class weight differences.

## Weight profiles

### Fixed profiles

| Role-class profile | correctness | role_fidelity | scope_discipline | synthesis_quality | verification_cleanliness | runtime_cleanliness | Sum |
|---|---:|---:|---:|---:|---:|---:|---:|
| owner, advisory, factual, design, planning | `25` | `25` | `15` | `25` | `5` | `5` | `100` |
| scientist, constraints | `30` | `20` | `15` | `20` | `10` | `5` | `100` |
| implementation | `35` | `10` | `25` | `5` | `15` | `10` | `100` |
| review, QA | `30` | `20` | `20` | `20` | `5` | `5` | `100` |
| adapters | `10` | `5` | `20` | `0` | `20` | `45` | `100` |

### Role-to-profile mapping

| Role class in the role matrix | Uses profile |
|---|---|
| owner | owner, advisory, factual, design, planning |
| advisory | owner, advisory, factual, design, planning |
| hygiene | owner, advisory, factual, design, planning |
| factual | owner, advisory, factual, design, planning |
| design | owner, advisory, factual, design, planning |
| planning | owner, advisory, factual, design, planning |
| scientist | scientist, constraints |
| constraint | scientist, constraints |
| implementation | implementation |
| review | review, QA |
| adapter | adapters |

`$knowledge-archivist` uses the first profile because it is a source-of-truth stewardship surface, not
an implementation or review gate.

## Winner selection

Winners are published per surface using exactly this rule:

1. highest `total_score`
2. if within `3` points, compare `correctness + role_fidelity`
3. if still tied, publish both as `near-tie`
4. require one specialty follow-up scenario in the same pack for any `near-tie`

## Publication surfaces

| Surface | Purpose |
|---|---|
| role-first result table | primary human-facing ranking for semantic roles |
| scenario mapping table | tells readers which scenario bundle supports each role row |
| caveat table | records active material caveats that affect interpretation |
| adapter table | publishes `A01` and `A02` separately from semantic roles |
| overlay table | publishes overlay taxonomy and active overlay usage separately |
| pack table | operational only; not the primary human-facing result surface |

## Publication rules

| Rule | Meaning |
|---|---|
| semantic rows only in the primary table | `R01..R31` only |
| adapters published separately | `A01` and `A02` never appear inside the semantic winner table |
| overlays stay secondary | runtime, browser, quota, and transport notes do not masquerade as role wins |
| explicit quota failures are not scoreable | provider quota, rate, or usage-limit failures that prevent a clean attempt are `NOT-RUN` / `REQUEUE`, not `PASS` or `FAIL` |
| runtime timeout failures are isolated | a bounded provider/runtime hang without worker output is `TIMEOUT`; keep it separate from quota and do not convert it to `PASS` / `FAIL` without an explicit scoring decision |
| scenario mapping stays explicit | every role row points back to its supporting scenario bundle or bundles |
| legacy checkpoint stays labeled | old upgraded-pack results remain reference-only and are not republished as v2 role winners |

## Sample provider legend

Sample only. This legend illustrates format, not final ranking.

| ID | Provider |
|---|---|
| `1` | `gpt-5.4` |
| `2` | `claude-4.7max` |
| `3` | `gpt-spark` |
| `4` | `gemini-3.1pro` |
| `5` | `gemini-3.1flash-lite-preview` |

## Sample primary role-first table

Sample only. The point is that different roles can have different leaders.

| `#` | Role | `1` | `2` | `3` | `4` | `5` |
|---|---|---|---|---|---|---|
| `1` | `R01 $product-manager` | `claude-4.7max` | `gpt-5.4` | `gemini-3.1pro` |  |  |
| `2` | `R07 $architect` | `claude-4.7max` | `gpt-5.4` | `gpt-spark` |  |  |
| `3` | `R16 $frontend-engineer` | `gpt-spark` | `gpt-5.4` | `claude-4.7max` | `gemini-3.1pro` |  |
| `4` | `R21 $toolchain-engineer` | `gpt-5.4` | `claude-4.7max` | `gpt-spark` |  |  |
| `5` | `R23 $graphics-engineer` | `gemini-3.1pro` | `gpt-5.4` | `claude-4.7max` |  |  |
| `6` | `R27 $security-reviewer` | `claude-4.7max` | `gpt-5.4` | `gemini-3.1pro` |  |  |

## Sample secondary scenario-mapping table

| `#` | Role | Scenarios |
|---|---|---|
| `1` | `R01 $product-manager` | `S01` |
| `2` | `R07 $architect` | `S07` |
| `3` | `R16 $frontend-engineer` | `S16` |
| `4` | `R21 $toolchain-engineer` | `S21` |
| `5` | `R23 $graphics-engineer` | `S23` |
| `6` | `R27 $security-reviewer` | `S27` |

## Sample caveat table

| `#` | Caveat | Applies to |
|---|---|---|
| `1` | provider widened outside the allowed change surface and lost `scope_discipline` points | `R21`, `S21`, affected provider row only |
| `2` | role achieved a near-tie and requires one specialty follow-up scenario in the same pack | `R23`, `P05` |

## Sample adapter table

| `#` | Adapter | `1` | `2` | `3` | `4` | `5` |
|---|---|---|---|---|---|---|
| `1` | `A01 $external-worker` | `gpt-5.4` | `claude-4.7max` | `gemini-3.1pro` | `gpt-spark` |  |
| `2` | `A02 $external-reviewer` | `claude-4.7max` | `gpt-5.4` | `gemini-3.1pro` | `gpt-spark` |  |

## Sample overlay table

| Overlay | Meaning | Typical use |
|---|---|---|
| `O01 browser-required` | scenario genuinely requires browser execution | intrinsic web implementation such as `S16` |
| `O02 runtime-timeout` | run stalled or timed out without a semantic verdict | provider caveat only |
| `O03 quota-or-rate-limit` | provider availability reduced result confidence | provider caveat only |
| `O04 transport-pollution` | adapter route added non-contract tool or runtime noise | `A01`, `A02` evidence only |
| `O05 legacy-checkpoint-only` | old upgraded-pack evidence is being cited for historical reference only | archive checkpoint notes |

## Consequence

Any future v2 result write-up should publish:

1. a semantic role-first table
2. a scenario mapping table
3. a caveat table
4. a separate adapter table
5. a separate overlay table

Pack tables may still exist for operational reporting, but they no longer count as the main public result.
