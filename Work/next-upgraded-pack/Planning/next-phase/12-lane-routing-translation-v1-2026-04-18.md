Date: 2026-04-18
Owner: `$lead`
Status: `PASS`

## Purpose

This note translates the full role-complete benchmark universe into the frozen `12`-lane routing
model.

The benchmark universe remains `33` surfaces:

- `31` semantic role surfaces `R01..R31`
- `2` adapter surfaces `A01..A02`

The routing layer is narrower by design:

- owners stay out of routing lanes
- adapters stay out of semantic routing lanes
- `worker.long-autonomous` remains overlay-only until it has its own `3`-test basis

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

## Overlay-only lane

| Lane | Current status |
|---|---|
| `worker.long-autonomous` | keep as routing overlay only; there is no current dedicated benchmark surface with a real `3`-test basis |

## Validation read

| Check | Read |
|---|---|
| routing lane count | `12` |
| basis count per lane | exactly `3`, including planned `N01..N07` where needed |
| owner boundary | `R01`, `R02` excluded |
| adapter boundary | `A01`, `A02` excluded |
| UI separation | design, implementation, and visual correctness remain separate |
| architecture separation | design lane and review lane remain separate |
| security separation | `review.security` is standalone |

## Consequence

This translation note becomes the benchmark-side evidence layer for any future update to:

- `Orchestrarium/shared/agents-mode.defaults.yaml`
- `Orchestrarium/docs/agents-mode-reference.md`
- `Orchestrarium/docs/external-worker-design.md`
