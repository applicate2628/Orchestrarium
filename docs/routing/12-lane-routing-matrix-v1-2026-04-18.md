Date: 2026-04-18
Updated: 2026-04-20
Owner: `$lead`
Status: `PASS`

## Purpose

This note freezes the canonical `12`-lane routing model as the planning baseline for
`externalPriorityProfiles`.

This is a routing-layer decision only:

- the full benchmark universe remains `33` surfaces
- the routing layer compresses those surfaces into `12` canonical lanes
- each lane has one explicit meaning, one merge rationale, and one `3`-test basis
- `worker.long-autonomous` stays outside the core `12` as a reference extra lane with a materialized `N08..N10` `3`-test basis

This note does **not** yet change `Orchestrarium/shared/agents-mode.defaults.yaml`.

## Canonical 12-lane matrix

| `#` | Lane | Meaning | 3-test basis | Merge / source |
|---|---|---|---|---|
| `1` | `advisory.repo-understanding` | repo facts, source-of-truth hygiene, evidence-backed advisory grounded in the repo | `S03`, `S04`, `S06` | consultant + archivist + analyst |
| `2` | `advisory.design-adr` | architecture design, ADR tradeoffs, product framing, phased planning | `S05`, `S07`, `S09` | product-analyst + architect + planner |
| `3` | `design.ui-ux-structure` | pre-implementation UI and UX structure, hierarchy, flow, state design, visual intent | `S08`, `N01`, `N02` | new explicit lane |
| `4` | `worker.reasoning-constraints` | formal, numerical, and security-constraint reasoning before implementation | `S10`, `S11`, `S12` | algorithm + computational + security-engineer |
| `5` | `worker.default-implementation` | ordinary backend, data, and platform implementation | `S15`, `S19`, `S20` | backend + data + platform |
| `6` | `worker.systems-performance-implementation` | systems ownership, toolchain-root work, performance-sensitive or reliability-sensitive implementation | `S13`, `S14`, `S21` | performance + reliability + toolchain |
| `7` | `worker.ui-implementation` | actual UI implementation correctness across web, Qt UI, and model/view | `S16`, `S17`, `S18` | merge current UI worker lanes |
| `8` | `worker.visual-graphics-visualization` | non-UI visual execution: geometry, rendering, graphics, visualization | `S22`, `S23`, `S24` | replace decorative visual lane |
| `9` | `review.pre-pr` | generic QA and merge-readiness review before specialty gates | `S25`, `N03`, `N04` | QA plus new generic review tests |
| `10` | `review.security` | dedicated security review and trust-boundary correctness gate | `S27`, `N05`, `N06` | new explicit lane |
| `11` | `review.performance-architecture` | architecture quality, maintainability, scalability, performance review | `S26`, `S28`, `N07` | architecture-reviewer + performance-reviewer |
| `12` | `review.ui-visual-correctness` | accessibility, UX, and UI regression correctness as one visual review gate | `S29`, `S30`, `S31` | replace vague `review.visual` |

## Reference extra lane

This lane is useful for routing policy, fallback policy, and long-running worker trust analysis, but it is
not part of the core `12` routing lanes.

| Extra | Lane | Meaning | 3-test basis | Read |
|---|---|---|---|---|
| `E1` | `worker.long-autonomous` | long autonomous worker execution across multi-step ownership, resume continuity, and no-drift implementation | `N08`, `N09`, `N10` | reference overlay only; not counted in the core `12` |

## Concern-to-lane map

| Concern | Primary lane |
|---|---|
| architecture design | `advisory.design-adr` |
| architecture review | `review.performance-architecture` |
| repo understanding | `advisory.repo-understanding` |
| UI and UX design before code | `design.ui-ux-structure` |
| UI implementation correctness | `worker.ui-implementation` |
| UI visual correctness review | `review.ui-visual-correctness` |
| generic implementation | `worker.default-implementation` |
| systems, toolchain, or perf-sensitive implementation | `worker.systems-performance-implementation` |
| graphics or visualization execution | `worker.visual-graphics-visualization` |
| generic review gate | `review.pre-pr` |
| security review gate | `review.security` |
| long autonomous worker trust | `worker.long-autonomous` extra/reference lane |

## Current lane migration

| Current lane | Decision |
|---|---|
| `advisory.repo-understanding` | keep |
| `advisory.design-adr` | keep |
| `review.pre-pr` | keep |
| `review.performance-architecture` | keep |
| `worker.default-implementation` | keep |
| `worker.systems-performance-implementation` | keep and widen |
| `worker.ui-structural-modernization` | merge into `worker.ui-implementation` |
| `worker.ui-surgical-patch-cleanup` | merge into `worker.ui-implementation` |
| `worker.visual-icon-decorative` | replace with `worker.visual-graphics-visualization` |
| `review.visual` | replace with `review.ui-visual-correctness` |
| `worker.long-autonomous` | keep as reference extra lane and overlay-only |

## Non-core routing overlay

| Overlay | Read |
|---|---|
| `worker.long-autonomous` | keep as routing overlay and reference extra lane; use `N08..N10` as its materialized basis |

## Follow-up scenarios

| New scenario | Lane |
|---|---|
| `N01` static visual hierarchy brief | `design.ui-ux-structure` |
| `N02` interaction-state flow brief | `design.ui-ux-structure` |
| `N03` generic code-review findings | `review.pre-pr` |
| `N04` regression-triage gate | `review.pre-pr` |
| `N05` secret-exposure review | `review.security` |
| `N06` authz or trust-boundary review | `review.security` |
| `N07` scalability or maintainability cross-review | `review.performance-architecture` |
| `N08` autonomous build-owner continuity | `worker.long-autonomous` extra/reference lane |
| `N09` autonomous resume and path recall | `worker.long-autonomous` extra/reference lane |
| `N10` constrained multi-step patch with no drift | `worker.long-autonomous` extra/reference lane |

## Boundary conditions

| Boundary | Read |
|---|---|
| owners | `R01` and `R02` stay outside routing lanes |
| adapters | `A01` and `A02` stay outside semantic routing lanes |
| UI split | `design.ui-ux-structure`, `worker.ui-implementation`, and `review.ui-visual-correctness` stay separate |
| architecture split | architecture design stays in `advisory.design-adr`; architecture review stays in `review.performance-architecture` |
| security split | `review.security` stays standalone |
| extra lane boundary | `worker.long-autonomous` is `E1`, not lane `13`; it does not change the core lane count |
| execution-surface boundary | core routing results remain `S01..S33 + N01..N07`; `N08..N10` are now a separate scoreable extra-lane slice |

## Next step

The next implementation step after this freeze is a documentation and config update pass that:

- updates `agents-mode-reference.md`
- updates `external-worker-design.md` if needed
- updates `shared/agents-mode.defaults.yaml`
- treats `worker.long-autonomous` as an extra/reference lane when updating profile docs
- keeps `N08..N10` reported separately from the core `12` routing-lane results
