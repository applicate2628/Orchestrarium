Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

This brief defines the next upgraded benchmark pack after the first archived baseline.

The next phase is no longer just a narrow suspicious-row hardening wave.
Its job is to normalize the benchmark system itself.

## Main objective

Build a role-aligned upgraded benchmark pack that does four things together:

1. unify the atomic benchmark tests under one shared contract
2. unify the naming surface so there is no mixed `M/G/W` operational vocabulary
3. apply hardening expectations to every active test family, not only a few suspicious rows
4. re-cut benchmark lines so they map to Orchestrator roles or role families, where one line may be supported by several tests
5. reduce regular execution to a smaller steady-state core pack while keeping the full registry for provenance

## Current baseline assumption

| Topic | Current accepted read |
|---|---|
| frozen archive surface | `Archive/2026-04-16-first-baseline/` stays unchanged until a new pack is admitted |
| active mutable workspace | `Work/next-upgraded-pack/` is the only place where redesign and reruns should happen |
| current narrowed basis | `X1..X5` remains the working comparison surface |
| active execution cohort | `X1`, `X2`, `X3` |
| frozen rows | `X4` and `X5` stay frozen on current admitted evidence while latency or availability remains bad |
| evidence-first rule | redesign first, evidence second, interpretation third, archive only after admission |

## Why this phase exists

| Current problem | Why it must be fixed now |
|---|---|
| current lines mix roles, test modalities, and historical wave artifacts | the ranking surface is harder to interpret than it should be |
| `W4` and `W5` still look like ordinary rows in some views | they are really fallback overlays, not full-lane comparisons |
| hardening is uneven across legacy and newer tests | some rows are pressured by robust probes while others are still flattered by softer tasks |
| mixed `M`, `G`, and `W` naming is harder to operate than it needs to be | the upgraded pack should present one clean naming surface |
| several current lines are too granular and UI-specific | they should be merged into role-aligned lines with multiple supporting tests |
| some lines still measure one test more than one role | future packs need role-family lines backed by several tests, not one row per probe |
| the future full registry is larger than what should run every time | steady-state execution needs a smaller core pack and an explicit extended tier |

## Phase hypotheses

| ID | Hypothesis |
|---|---|
| `H1` | current benchmark lines will become easier to trust once they are aligned to Orchestrator roles instead of mixed historical row types |
| `H2` | `W4` and `W5` should survive only as overlays, not as first-class practical work lines |
| `H3` | every active test family still needs a shared hardening contract: true-owner checks, anti-hardcode, anti-drift, and distractor pressure |
| `H4` | one unified `T`-series for tests plus `L`-series for lines and `O`-series for overlays will be easier to operate than legacy `M/G/W` naming |
| `H5` | merged role lines backed by multiple tests will produce a more stable ranking surface than the current row-per-slice approach |
| `H6` | the upgraded pack should challenge `X1`, `X2`, and `X3` first without forcing fairness-sensitive reruns for currently frozen rows |

## In-scope work

| Scope | Meaning |
|---|---|
| unified test contract | define one common benchmark-fixture contract across legacy and new tests |
| unified naming taxonomy | define one clean naming layer for tests, lines, and overlays |
| full hardening program | assign a hardening path for every active test family and migrated legacy surface |
| role-line redesign | propose merged practical lines aligned to Orchestrator roles or role families |
| core execution pack design | define the smaller steady-state run surface and separate it from the full registry |
| overlay cleanup | move fallback-only and modality-only surfaces out of the main line taxonomy |
| upgraded fixture design | design new harder probes where current test coverage is too soft or too narrow |

## Out of scope

| Out of scope | Reason |
|---|---|
| full matrix rerun immediately | redesign should land before large rerun cost is paid |
| archive mutation | archive remains frozen until upgraded evidence is admitted |
| fairness-sensitive reruns for `X4` and `X5` | they remain operationally frozen for now |
| browser-first UI methodology | UI should stay non-browser by default unless a supplemental runtime note is explicitly needed |

## Required outputs

| Output | Destination |
|---|---|
| revised phase brief | `Planning/next-phase/phase-brief-2026-04-16.md` |
| naming and taxonomy rule | `Planning/next-phase/benchmark-taxonomy-and-naming-2026-04-16.md` |
| role-line consolidation map | `Planning/next-phase/role-line-unification-2026-04-16.md` |
| steady-state core execution pack | `Planning/next-phase/core-execution-pack-2026-04-17.md` |
| full hardening program | `Planning/next-phase/test-hardening-program-2026-04-16.md` |
| upgraded fixture backlog | existing backlog plus new role-aligned fixture proposals |
| execution plan | future admitted run order after the redesign is accepted |

## Expected line model direction

The upgraded pack should prefer these principles:

| Rule | Meaning |
|---|---|
| one line equals one role family | lines should be interpretable through Orchestrator roles |
| one line may use several tests | a line is a synthesis surface, not a single probe |
| tests are evidence, not lines | atomic tests should converge to one `T` series feeding the lines rather than replacing them |
| registry stays fuller than routine execution | a smaller steady-state core pack should sit on top of the full registry |
| overlays stay separate | fallback overlays, browser notes, and other modality-specific slices should not masquerade as ordinary role lines |
| merge where roles match | multiple current rows may collapse into one role-aligned line if they test the same role family |
| one clean naming surface | upgraded-pack docs should prefer `T`, `L`, and `O`, with legacy aliases shown only when needed |

## Recommended execution order

| Step | Focus |
|---|---|
| `1` | normalize the benchmark taxonomy: tests, lines, overlays, and archived syntheses |
| `2` | define the unified `T/L/O` naming system and migration notes |
| `3` | define the merged role-aligned line set |
| `4` | define the full hardening program across all active test families |
| `5` | design upgraded fixtures against the new contract |
| `6` | run the active cohort on the redesigned pack |
| `7` | update mutable checkpoints and results drafts |
| `8` | archive only after admitted evidence exists |
