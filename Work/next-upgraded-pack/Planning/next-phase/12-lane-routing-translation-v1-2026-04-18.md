Date: 2026-04-18
Updated: 2026-04-24
Owner: `$lead`
Status: `PASS`

## Purpose

This note translates the full role-complete benchmark universe into the frozen `12`-lane routing
model.

2026-04-24 update: `Results-drafts/full-v2-hard-results-current.md` is now the current canonical
hardened `/40` surface for this lane model. The older `S01..S33 + N01..N07` full-v2 table remains
only a pre-v3 ceiling-effect baseline.

The benchmark universe remains `33` surfaces:

- `31` semantic role surfaces `R01..R31`
- `2` adapter surfaces `A01..A02`

The routing layer is narrower by design:

- owners stay out of routing lanes
- adapters stay out of semantic routing lanes
- `worker.long-autonomous` remains outside the core `12` and is tracked as a reference extra lane with a materialized `N08..N10` basis
- `top-pair-separator` remains outside routing as a diagnostic overlay for separating tied top rows after core lanes stop discriminating

## Canonical routing lanes

| `#` | Lane | Basis |
|---|---|---|
| `1` | `advisory.repo-understanding` | `S03`, `S04`, `S06` |
| `2` | `advisory.design-adr` | `S05`, `S07`, `S09` |
| `3` | `design.ui-ux-structure` | `S08`, `N01`, `N02` |
| `4` | `worker.reasoning-constraints` | `S10`, `S11`, `S12` |
| `5` | `worker.default-implementation` | `S15`, `S19`, `S20` |
| `6` | `worker.systems-performance-implementation` | `S13`, `S14`, `S21` |
| `7` | `worker.ui-implementation` | `S16`, `S17`, `S18` |
| `8` | `worker.visual-graphics-visualization` | `S22`, `S23`, `S24` |
| `9` | `review.pre-pr` | `S25`, `N03`, `N04` |
| `10` | `review.security` | `S27`, `N05`, `N06` |
| `11` | `review.performance-architecture` | `S26`, `S28`, `N07` |
| `12` | `review.ui-visual-correctness` | `S29`, `S30`, `S31` |

## Reference extra lane

| Extra | Lane | Basis | Current scoreability |
|---|---|---|---|
| `E1` | `worker.long-autonomous` | `N08`, `N09`, `N10` | materialized extra-lane basis, reported separately from the core `12` lanes |
| `E2` | `top-pair-separator` | `N11`, `N12`, `N13` | materialized diagnostic overlay; initial and hardened2 runs tied `X1` and `X3` at `3 / 3` |

## Surface-to-lane translation

| Surface | Role | Routing disposition |
|---|---|---|
| `R01` | `$product-manager` | excluded from routing lanes as owner |
| `R02` | `$lead` | excluded from routing lanes as owner |
| `R03` | `$consultant` | `advisory.repo-understanding` |
| `R04` | `$knowledge-archivist` | `advisory.repo-understanding` |
| `R05` | `$product-analyst` | `advisory.design-adr` |
| `R06` | `$analyst` | `advisory.repo-understanding` |
| `R07` | `$architect` | `advisory.design-adr` |
| `R08` | `$ux-designer` | `design.ui-ux-structure` |
| `R09` | `$planner` | `advisory.design-adr` |
| `R10` | `$algorithm-scientist` | `worker.reasoning-constraints` |
| `R11` | `$computational-scientist` | `worker.reasoning-constraints` |
| `R12` | `$security-engineer` | `worker.reasoning-constraints` |
| `R13` | `$performance-engineer` | `worker.systems-performance-implementation` |
| `R14` | `$reliability-engineer` | `worker.systems-performance-implementation` |
| `R15` | `$backend-engineer` | `worker.default-implementation` |
| `R16` | `$frontend-engineer` | `worker.ui-implementation` |
| `R17` | `$qt-ui-engineer` | `worker.ui-implementation` |
| `R18` | `$model-view-engineer` | `worker.ui-implementation` |
| `R19` | `$data-engineer` | `worker.default-implementation` |
| `R20` | `$platform-engineer` | `worker.default-implementation` |
| `R21` | `$toolchain-engineer` | `worker.systems-performance-implementation` |
| `R22` | `$geometry-engineer` | `worker.visual-graphics-visualization` |
| `R23` | `$graphics-engineer` | `worker.visual-graphics-visualization` |
| `R24` | `$visualization-engineer` | `worker.visual-graphics-visualization` |
| `R25` | `$qa-engineer` | `review.pre-pr` |
| `R26` | `$architecture-reviewer` | `review.performance-architecture` |
| `R27` | `$security-reviewer` | `review.security` |
| `R28` | `$performance-reviewer` | `review.performance-architecture` |
| `R29` | `$accessibility-reviewer` | `review.ui-visual-correctness` |
| `R30` | `$ux-reviewer` | `review.ui-visual-correctness` |
| `R31` | `$ui-test-engineer` | `review.ui-visual-correctness` |
| `A01` | `$external-worker` | excluded from semantic routing lanes as adapter |
| `A02` | `$external-reviewer` | excluded from semantic routing lanes as adapter |

## Missing planned scenarios required for an honest `12 x 3`

| Planned scenario | Lane | Reason |
|---|---|---|
| `N01` | `design.ui-ux-structure` | `S08` alone is too thin for the full UI and UX design lane |
| `N02` | `design.ui-ux-structure` | needed to separate state-flow reasoning from static structure |
| `N03` | `review.pre-pr` | needed so generic review is not only a QA verdict lane |
| `N04` | `review.pre-pr` | needed to measure generic regression-triage quality |
| `N05` | `review.security` | needed so security review is not single-scenario fragile |
| `N06` | `review.security` | needed to pressure authz and trust-boundary review specifically |
| `N07` | `review.performance-architecture` | needed so architecture and performance review has a third independent slice |

## Extra-lane scenarios

| Planned scenario | Lane | Reason |
|---|---|---|
| `N08` | `worker.long-autonomous` | tests autonomous ownership continuity when the work requires nested owner discovery and multiple accepted steps |
| `N09` | `worker.long-autonomous` | tests resume behavior, path recall, and not restarting or dropping admitted scope after interruption |
| `N10` | `worker.long-autonomous` | tests constrained multi-step patch execution with no unrelated churn or contract drift |
| `N11` | `top-pair-separator` | tests conflict-aware ADR quality when evidence, ownership, and migration constraints pull in different directions |
| `N12` | `top-pair-separator` | tests factual source-of-truth hygiene when docs, config, and result evidence disagree |
| `N13` | `top-pair-separator` | tests adversarial review precision with must-find defects placed beside false-positive traps |

## Overlay lane

| Lane | Current status |
|---|---|
| `worker.long-autonomous` | keep as reference extra lane and routing overlay; `N08..N10` are materialized and scoreable as a separate extra-lane slice |
| `top-pair-separator` | diagnostic-only overlay for `X1` vs `X3`; not a routing lane and not eligible for `externalPriorityProfiles` until promoted by a separate decision |

## Validation read

| Check | Read |
|---|---|
| routing lane count | `12` |
| reference extra lanes | `2`: `worker.long-autonomous`, `top-pair-separator` |
| basis count per lane | exactly `3`, including planned `N01..N07` where needed |
| extra-lane basis count | `6` materialized tests split as `E1=N08..N10` and `E2=N11..N13` |
| owner boundary | `R01`, `R02` excluded |
| adapter boundary | `A01`, `A02` excluded |
| UI separation | design, implementation, and visual correctness remain separate |
| architecture separation | design lane and review lane remain separate |
| security separation | `review.security` is standalone |
| execution boundary | `full-v2-hard-results-current.md` is the current hardened `/40` execution surface; the legacy `S01..S33 + N01..N07` table is pre-v3 baseline only; `N08..N10` remain separate `E1` evidence and `N11..N13` remain diagnostic `E2` tiebreaker evidence |

## Consequence

This translation note becomes the benchmark-side evidence layer for any future update to:

- `Orchestrarium/shared/agents-mode.defaults.yaml`
- `Orchestrarium/docs/agents-mode-reference.md`
- `Orchestrarium/docs/external-worker-design.md`
