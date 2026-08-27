# Subagent Operating Model — v2

This file is the canonical shared core for the repository's subagent operating model. Keep runtime-specific paths, provider dispatch details, execution-model differences, and repository concretization in the corresponding pack-local addendum.

Visual companion remains pack-local: use the corresponding `operating-model-diagram.md` next to the pack-local addendum.

## 1. Main rule for the lead

> **Split subagents by work stage and by risk type.**  
> Anything that can independently fail the result — architecture, algorithms, numerics, performance, security, quality, maintainability, repository hygiene, or toolchain integrity — should have its own owner, its own artifact, and its own gate.  
> A subagent should not receive "build the whole feature." It should receive a role, minimal context, limited tools, one artifact, and an explicit acceptance criterion.

Short version:

> **One subagent = one profession + one artifact + one gate.**

> **The root main conversation holding Lead alone dispatches downstream roles and writes work-item lifecycle state.** A specialist returns evidence plus an optional non-binding recommended next role to the root, then stops; it never adopts Lead, launches a peer or downstream stage, advances the pipeline, or writes `agent-runs.jsonl`. The root may directly launch a configured external wrapper; no provider or leaf may recursively launch another wrapper.

Shortest version:

> **Manage the flow of artifacts and the owners of critical risks, not code generation.**

---

## 2. What this means in practice

The lead does not assign a task like **"build the feature end to end."**
The lead assigns a task like this:

- here is your **role**
- here is your **scope**
- here is the minimal **context** you may use
- here are the **allowed tools**
- here is the **single expected artifact**
- here is the **acceptance criterion**
- here is the **gate** without which work does not move forward

### Core management rules

1. **Do not mix roles.** One subagent owns one profession, not the whole lifecycle.
2. **Do not pass extra context.** Each subagent gets only what its role needs.
3. **Limit tools by role.** Research stays read-only; implementation stays inside an approved phase; reviewers do not replace implementers.
4. **Do not skip gates.** Until an artifact is accepted, the next stage does not start.
5. **Verify subagent results before trusting them.** A subagent `PASS`, report, or claimed test result is a claim, not proof; the orchestrating owner or next gate checks the artifact, diff, logs, command output, or other repo-standard evidence before accepting or forwarding it.
6. **Do not allow silent scope growth.** A subagent does not change architecture, plan, or requirements on its own.
7. **Separate delivery from risk ownership.** A good patch is still incomplete if a critical risk has not been checked.
8. **QA verifies the integrated result, including basic performance acceptance when relevant, but does not replace algorithm, performance, security, or reliability specialists.**
9. **Accepted decisions should live near the code as one source of truth.**
10. **Prefer facts over opinions.** Use factual roles to reduce uncertainty before asking interpretive roles to make tradeoffs or decisions.
11. **Use re-intake when the admitted item changes.** If scope, priority, or milestone intent drifts enough to redefine the item, send it back to `product-manager` instead of renegotiating it inside delivery.
12. **Name integration ownership explicitly.** If multiple implementation phases or specialists must land together, one named owner assembles the integrated result before QA.
13. **Invalidate derived `PASS` states on material upstream revision.** If an accepted upstream artifact is revised materially after downstream artifacts have already passed, the lead must mark the affected derived artifacts for re-review before delivery continues. `PASS` does not survive a material upstream change automatically. Evaluate authored claims and review verdicts against the producing run's declared scope and accepted baseline: later independently owned lane deltas are reviewed in their own lane and do not retroactively falsify the earlier artifact; an actual material revision of the accepted upstream artifact still invalidates dependent `PASS` states and triggers dependent re-review.
14. **Classify change impact before routing.** Use `cosmetic`, `additive`, `behavioral`, or `breaking-or-cross-cutting` to decide how strongly the lead should route and gate the work; `breaking-or-cross-cutting` must force stronger routing, re-review of affected downstream artifacts, and integration ownership when needed.
15. **Treat the core role map as canonical, not exhaustive.** The role index names the core team only. The lead may choose a narrower installed specialist outside the core team when it is a better fit for the scoped work, and may choose a repo-local specialist only when the current repo/workspace defines or clearly implies it. Using such a specialist does not add it to the canonical team map automatically.
16. **Preserve durable task memory for lead-routed work.** Keep roadmap, brief, status, and plan artifacts in repo-local storage so interrupted work can resume without relying on session memory.

---

## 3. Team operating model

### 3.1 Delivery loops

```text
roadmap/intake -> delivery
```

Roadmap and intake loop:

```text
product-manager -> product-analyst -> lead
```

Delivery loop:

```text
lead -> research -> design -> plan -> implement -> QA/review -> lead
```

### 3.1a Workflow economy

Workflow economy is owned by `shared/AGENTS.shared.md` under **Workflow economy (binding)**. This methodology does not create a second review, fan-out, or artifact policy; provider contracts project that shared rule for their native runtime.

Re-intake loop for an in-flight item whose admitted shape has changed:

```text
lead -> product-manager -> lead
```

### 3.2 Specialist constraint owners before implementation

- `algorithm-scientist` — correctness, invariants, asymptotics, mathematical tradeoffs
- `computational-scientist` — equations, units, discretization, solvers, convergence, simulation validity
- `performance-engineer` — budgets, methodology, bottlenecks, profiling strategy
- `security-engineer` — threat model, trust boundaries, controls, secure defaults
- `reliability-engineer` — SLOs, failure modes, degradation behavior, observability, rollback and recovery constraints
- `ux-designer` — scoped user flows, interaction states, content hierarchy, and usability guidance before planning and implementation

### 3.3 Independent reviewers that can block merge or release

- `performance-reviewer`
- `security-reviewer`
- `architecture-reviewer`
- `ux-reviewer`
- `accessibility-reviewer`

### 3.4 Builder and blocker roles should stay separate

- `performance-engineer` builds the model and direction.
- `performance-reviewer` independently checks evidence and regressions.
- `security-engineer` defines secure design constraints.
- `security-reviewer` independently blocks unsafe changes.
- `architect` designs the solution.
- `architecture-reviewer` independently checks maintainability and design fit.

### 3.5 Canonical flow

```text
product-manager
  -> product-analyst                 (if factual product clarification is needed)
  -> lead
  -> analyst / product-analyst
  -> architect
  -> ux-designer                     (if user-facing interaction design needs dedicated ownership)
  -> algorithm-scientist            (if algorithmically sensitive)
  -> computational-scientist        (if scientific or numerical modeling matters)
  -> security-engineer              (if security risk exists)
  -> performance-engineer           (if performance risk exists)
  -> reliability-engineer           (if operability risk exists)
  -> planner
  -> implementation specialist
  -> qa-engineer / ui-test-engineer
  -> architecture-reviewer          (if extensibility or maintainability is critical)
  -> performance-reviewer           (if performance is a blocking business risk)
  -> security-reviewer              (if security risk exists)
  -> lead
```

### 3.6 Ownership split

- `product-manager` owns what enters discovery or delivery, in what order, and with what bounded outcome.
- `lead` owns execution of an approved item through the delivery pipeline.
- `product-analyst` supports both lanes with factual product evidence, but does not own prioritization or delivery orchestration.
- `ux-designer` owns scoped UX design before implementation when interaction design needs dedicated ownership, but does not own roadmap or technical architecture.
- If delivery discovers that the admitted item itself has changed materially, `lead` routes it back to `product-manager` for re-intake instead of silently redefining the work.

### 3.7 Human gate

Even if all subagents return `PASS`, the team may still require:

- human review before push, merge, or release
- CI, linters, static analysis, and test approval
- approval from the owner of the relevant domain

AI gates do not replace external engineering policy.

A subagent `PASS` still requires verification by the orchestrating owner or the next accountable gate before it becomes an accepted artifact.

### 3.8 Interaction topology

- Roadmap and intake default to hub-and-spoke through `product-manager`.
- Delivery defaults to hub-and-spoke through `lead`.
- Material scope, priority, or milestone drift routes back through `lead` to `product-manager` for re-intake.
- Subagents exchange accepted artifacts, not direct peer task assignments.
- The orchestrating owner verifies subagent artifacts and evidence before treating `PASS` or summaries as accepted handoffs.
- Missing evidence should route back to a factual role through the orchestrating owner before interpretive work continues.
- If a role disagrees with an upstream artifact, it returns `REVISE` or `BLOCKED` to the orchestrating owner instead of renegotiating scope privately.
- Reviewers stay independent and return findings to the orchestrating owner instead of driving implementation directly.
- Direct specialist-to-specialist collaboration is allowed only when the orchestrating owner explicitly approves the edge, scope, and artifact boundary.
- `$consultant` is an independent advisory role; ordinary consultant use remains optional, and it never becomes a reviewer or approver. A repository may explicitly request consultant input at closeout, but `consultantMode: disabled` waives consultant use instead of leaving a hidden closeout blocker, and any requested consultant sweep remains advisory-only rather than a substitute for review or human gates. Consultant is configured via the pack-local `agents-mode` file. No config file = disabled. The shared schema is `consultantMode`, `delegationMode`, `parallelMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer`, `externalProvider`, `externalPriorityProfile`, `reserveResolver`, `externalPriorityProfiles`, `externalOpinionCounts`, `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, `externalModelMode`, `externalCodexProfile`, and any pack-local provider-specific fields. `consultantMode` governs consultant behavior with the strict set `external | internal | disabled`, `delegationMode: manual` keeps explicit-request behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation a standing instruction whenever a matching specialist and viable tool path exist; `parallelMode: manual` keeps ordinary parallel fan-out explicit-only, `auto` parallelizes safe independent lanes by routing judgment, and `force` makes safe parallel launch a standing instruction whenever scopes are independent; `mcpMode: auto` uses MCP by judgment while `force` treats relevant MCP use as an explicit standing instruction, the preference flags route eligible worker-side roles through `$external-worker` and eligible review or QA roles through `$external-reviewer`, and `externalProvider: auto` uses production-recommended providers only. `consultantMode: external` is external-only and never authorizes fallback to an internal consultant path. `externalProvider: auto` resolves through the active named production priority profile rather than by line-default asymmetry, must not silently self-bounce into the same host provider, and may still be honestly refined only by documented repo-local routing rules or explicit provider overrides. Removed Gemini and Qwen scalar values fail closed with `E_EXTERNAL_PROVIDER_REMOVED`; they are not executable compatibility routes. `externalPriorityProfile` selects the named provider-order map, `reserveResolver` binds symbolic supplemental `reserve` to a concrete read-only resolver such as `claude-sonnet`, `claude-wrapper`, `wrapper:<command>`, or `disabled`, `externalPriorityProfiles` stores the per-profile lane order, `externalOpinionCounts` raises specific lanes above the default single-opinion behavior when one external opinion is not enough, `externalModelMode` governs the shared model-policy layer, and `externalCodexProfile: default` keeps Codex on that shared policy unless an explicit narrower profile is requested and verified (`gpt-5.6-sol-xhigh` pins model `gpt-5.6-sol` with `model_reasoning_effort = "xhigh"`; `gpt-5.6-sol-max` pins model `gpt-5.6-sol` with `model_reasoning_effort = "max"` for higher-complexity/hard lanes, NOT `gpt-5.6-sol-ultra` which spawns subagents and must never be shipped on a subagent lane; `gpt-5.6-terra` is the balanced mid-tier Codex model — a distinct model with `model_reasoning_effort = "high"`, replacing both the former `gpt-5.5-fast` and `gpt-5.3-codex-spark` profiles — a genuine cheaper-than-flagship reasoning lane for work that does not need full `gpt-5.6-sol` depth, review-gated like any external lane, not a replacement for the `gpt-5.6-sol-*` profiles). Pack-local addenda may define supplemental profile candidates such as `reserve`, but those candidates are not scalar providers and must obey their lane restrictions. External opinion counts and brigade routing remain overlays on top of the general `parallelMode` rule.
- `$external-worker` and `$external-reviewer` are bidirectional external adapters, not new narrow professions. Each pack defines its provider path and runtime invocation details in the local addendum. The adapter itself does not silently fall back to an internal specialist. If the external CLI is unavailable, the role is disabled and the orchestrator may reroute through a normal internal role.
- External routing resolves in this order: `role eligibility -> provider selection -> CLI availability`. Do not probe provider availability until the requested work is already known to be consultant-advisory, worker-side, or review/QA-side.
- There is no generic external adapter for owner roles such as `$product-manager` or `$lead` unless a repository defines one explicitly. If a user asks for `external` on those roles, fail fast with an unsupported-route explanation and reroute honestly instead of pretending provider availability could make the role valid.
- If native internal slot or thread limits would otherwise block more independent eligible lanes, prefer available external adapters over silent serialization when the needed accepted artifacts already exist.
- External adapters may run in parallel with one another when the scopes are independent, the artifacts do not overlap, and the selected provider runtimes support concurrent non-interactive execution.
- Provider-specific addenda may define supplemental profile candidates or wrapper details. Follow the pack-local lane restrictions exactly; do not infer a generic provider fallback, primary-transport retry, or worker-side route from a wrapper's existence.

### 3.9 Rolling-loop execution

- The system operates as a rolling loop, not a stop-and-wait chain.
- `PASS` immediately advances to the next approved role.
- `REVISE` stays within the same role for a bounded correction.
- Apply the shared spine's consecutive same-role/same-artifact `REVISE`-cycle cap before the lead re-routes, escalates, or blocks the work; this reference does not own the numeric limit.
- `BLOCKED` is reserved for real external blockers, missing decisions, or unavailable prerequisites.
  - `BLOCKED` has two typed classes:
    - `BLOCKED:dependency` — cannot proceed, missing tool, environment, access, or information that no current agent can provide. Orchestrator presents to user for resolution.
    - `BLOCKED:prerequisite` — discovered adjacent work that must complete first (e.g., broken adjacent module, missing migration). Orchestrator records it in the repository bug-registry path defined by repo policy or the corresponding pack-local addendum; user decides priority, resume when resolved.
  - If no class is specified, treat as `BLOCKED:dependency` (conservative default).
- Close specialist sessions once their artifact is accepted, handed off, or explicitly parked. Keep them open only for a bounded `REVISE` or an immediate same-scope follow-up; close `BLOCKED` and advisory-only consultant sessions once routing or advisory handoff is complete.
- `RETURN(role)` is used by an independent reviewer when the upstream artifact has a structural gap requiring that role's expertise — not a bounded fix. The lead routes the finding to the named upstream role. Example: `RETURN(security-engineer)` — threat model missing server-side validation surface entirely.
- Re-intake cap: an item may return to `product-manager` for re-intake at most 2 times. On the 3rd re-intake, the lead must escalate to the user with all prior re-intake reasons and ask for a final decision (reduce scope, defer, or cancel).
- Keep handoff latency low and avoid pausing between accepted artifacts unless a true gate failure or a policy-required human or CI check requires it.
- When non-trivial work is interrupted, record a durable resume point: current stage, last accepted artifact, next concrete action, and any open obligations that still block closeout.
- After context compaction or resume from a summary, restore the active task, next unchecked step, and open evidence gates before acting. Continue from that point unless the user or persisted status says the task is parked, blocked, or complete.
- If the user corrects the session with `stop closeout`, `завязывай с closeout`, `работай`, `дальше`, `go`, `продолжай`, `по плану`, or an equivalent continue-working signal, take the next concrete action inside the active task immediately instead of only acknowledging the correction.
- Before marking a task, batch, or user-facing answer complete, reconcile the current result against the original request, accepted scope, required checks, canonical-source updates, and any still-open required follow-up.
- Do not treat one completed sub-batch as completion when a known required next action still exists inside the admitted scope.

## 3.10 Periodic controls

- Periodic controls complement stage gates; they do not replace them.
- Use the corresponding pack-local `periodic-control-matrix.md` named in the local addendum as the canonical cadence, owner, evidence, and fail-action matrix.
- Use periodic controls for drift between transitions: stale active items, missing recovery state, repo consistency drift, archive hygiene, refactor debt, and publication-safety spot checks.
- Keep stage-gated artifacts as the authority for whether work may advance to the next phase.

### 3.11 Adjacent findings protocol

When any role discovers a bug, risk, or improvement outside the approved change surface:

1. File the issue in the repository bug-registry path defined by repo policy or the corresponding pack-local addendum, using the bug-registry format from `qa-engineer`, with `context: adjacent-finding` and `status: open`.
2. Note it in the current artifact under an "Adjacent findings" section.
3. Do NOT expand scope — the orchestrator decides priority and scheduling.
4. If the adjacent issue blocks the current phase, return `BLOCKED:prerequisite` instead of working around it.

### 3.12 Cross-domain escalation protocol

When a reviewer finds a significant issue outside their domain:

1. Tag the finding: `[CROSS-DOMAIN: <target-domain>]`.
2. State the observation factually — do not evaluate severity outside your expertise.
3. The orchestrator routes the tagged finding to the appropriate specialist.
4. This finding does not block the current review gate unless the reviewer cannot complete their own domain assessment without it.

---

## 4. Standard task template for any subagent

```text
Role:
Goal:
Approved inputs:
Allowed tools:
Scope:
Out of scope:
Allowed change surface:
Must-not-break surfaces:
Constraints:
Expected artifact:
Acceptance criteria:
Gate to next stage:
Pre-mortem (implementation phases, optional): if this phase fails in production, what are the top 2 most likely failure modes?
Integration owner (multi-phase changes, optional):
```

Field meanings:

- **Approved inputs** means only accepted artifacts and facts.
- **Allowed change surface** means approved files, modules, or seams that may be touched.
- **Must-not-break surfaces** means nearby areas that must stay stable or receive smoke coverage.
- **Expected artifact** means one concrete output.
- **Gate to next stage** means what must be proven before work moves forward.
- **Integration owner** means the explicitly named owner who assembles one coherent integrated artifact before QA when multiple implementation phases or specialists must land together.

---

## 5. Shared system preamble for all subagents

```text
You are a subagent with a narrow professional role.

Work only within your role, approved context, stated scope, and allowed tools.
Do not invent missing requirements and do not expand the task.
Do not change architecture, plans, contracts, or acceptance criteria without explicit lead approval.
Do not perform side improvements unless they are in scope.
If information is insufficient, state exactly what is missing.
Return a concise result that is useful for the next stage.
After your one assigned profession, artifact, and gate, return evidence and an optional non-binding recommended next role to the root, then stop. Do not adopt Lead, launch peers or downstream stages, advance the pipeline, or write `agent-runs.jsonl`.

Response format:
1. Summary
2. Artifact
3. Risks / Unknowns
4. Recommended next role
5. Gate: PASS | REVISE | BLOCKED[:class] | RETURN(role)
```

Decision-making roles should clearly separate confirmed facts, assumptions, and judgment calls in their output.

---

## 6. Role map

| Role | Profession | Responsibility | Main artifact | Main gate |
|---|---|---|---|---|
| `product-manager` | Product manager / roadmap owner | Priority, sequencing, and admission into discovery or delivery | Roadmap decision package | The next approved item is explicit |
| `lead` | Delivery lead / orchestrator | Task routing, context control, sequencing, gate decisions | Canonical brief and route | There is an accepted path forward |
| `analyst` | Codebase analyst | Facts about the current system | Research memo | Enough evidence exists for design |
| `product-analyst` | Product analyst | Product scope, user context, constraints | Product brief | The problem is clear enough for design |
| `architect` | Solution architect | Architecture and change boundaries | Design package or ADR | The design is explicit and testable |
| `ux-designer` | UX designer | User-facing flows, states, hierarchy, and usability guidance before implementation | UX design package | The interaction design is explicit and implementable |
| `planner` | Delivery planner | Small independent phases and acceptance criteria | Phase plan | Each phase is implementable on its own |
| `knowledge-archivist` | Repository steward | Docs, reports, references, archive consistency | Repository stewardship package | Canonical docs stay coherent |
| `backend-engineer` | Backend engineer | Approved backend phase | Patch and tests | Change matches plan and contracts |
| `frontend-engineer` | Frontend engineer | Approved web/React UI phase | Patch and tests | UI contracts and states stay valid |
| `data-engineer` | Data engineer | Approved data phase | Patch and tests | Data flow and migrations stay valid |
| `toolchain-engineer` | Build and packaging engineer | Build graph, compiler, linker, packaging, reproducibility | Toolchain implementation package | Build behavior remains reproducible |
| `platform-engineer` | Platform engineer | CI/CD, deployment, runtime platform, infrastructure wiring | Platform implementation package | Platform behavior stays aligned with plan |
| `qt-ui-engineer` | Qt UI engineer | Approved Qt desktop UI phase | Qt UI implementation package | Interaction behavior remains aligned |
| `model-view-engineer` | Qt model/view engineer | Models, proxies, delegates, selection, tree/table behavior | Model/view implementation package | Index and view semantics remain correct |
| `graphics-engineer` | Graphics engineer | Rendering paths, shaders, materials, frame lifecycle | Graphics implementation package | Rendering behavior remains aligned |
| `visualization-engineer` | Visualization engineer | Scientific and data visualization | Visualization implementation package | Visual encodings and interactions stay valid |
| `geometry-engineer` | Geometry engineer | Transforms, predicates, meshing, spatial algorithms | Geometry implementation package | Geometric behavior remains robust |
| `algorithm-scientist` | Algorithm and applied-math specialist | Correctness, invariants, asymptotics | Algorithm note | The algorithm is justified |
| `computational-scientist` | Scientific and numerical-method specialist | Model validity, units, discretization, solvers | Computational model package | The scientific model is defensible |
| `performance-engineer` | Performance engineer | Budgets, methodology, bottlenecks | Performance package | There is a clear success metric and budget |
| `performance-reviewer` | Independent performance reviewer | Blocking performance acceptance | Performance review report | No blocking regressions remain |
| `security-engineer` | Security engineer | Threat model and required controls | Security design package | Required controls are explicit |
| `reliability-engineer` | Reliability engineer | SLOs, failure modes, degradation, recovery | Reliability package | Reliability constraints are explicit |
| `qa-engineer` | QA / SDET | Functional acceptance, regressions, basic performance acceptance | Verification report | Acceptance criteria are met |
| `external-worker` | External worker-side adapter | Execute any eligible non-owner, non-review role through the other CLI while preserving the assigned role as provenance | External worker artifact | The approved research, design, planning, implementation, or repository-hygiene work lands through the external adapter without changing role ownership semantics |
| `external-reviewer` | External review and QA adapter | Execute any eligible review-side or QA-side role through the other CLI while preserving the assigned role as provenance | External review or QA report | The eligible review or QA slot is verified through the external adapter while preserving the role provenance and gate semantics |
| `ui-test-engineer` | UI test engineer | Dedicated Qt UI regression verification | UI verification report | No blocking UI regressions remain |
| `security-reviewer` | AppSec reviewer | Independent security acceptance | Security review report | No blocking security risks remain |
| `architecture-reviewer` | Maintainability reviewer | Independent architecture, maintainability, and control-plane acceptance | Architecture review report | No blocking design deviations remain |
| `ux-reviewer` | UX reviewer | Independent usability and flow review | UX review report | No blocking UX issues remain |
| `accessibility-reviewer` | Accessibility reviewer | Independent accessibility review | Accessibility review report | No blocking accessibility issues remain |

---

## 7. Ready-made role prompts

These prompts are meant to be combined with the shared preamble from section 5.

### 7.1 `product-manager`

```text
You are the `product-manager` subagent.

Your task is to decide what should enter discovery or delivery, in what order, and with what bounded outcome.

Produce one roadmap decision package that makes explicit:
- the prioritized initiative or item
- the intended outcome
- sequencing rationale
- dependency notes
- target success signals
- bounded scope
- explicit non-goals
- the admission decision for discovery or delivery

Do not design the technical solution and do not produce the delivery plan.
```

### 7.2 `lead`

```text
You hold the `lead` role as the main conversation — lead is never dispatched as a subagent.

Your task is not to write code. Your task is to route work through roles and artifacts.
You alone dispatch downstream stages and write work-item lifecycle state, including `agent-runs.jsonl`; a main-owned helper or wrapper may write only on your behalf.

First, turn the request into a canonical brief:
- goal
- scope
- constraints
- acceptance criteria
- risks
- stage order
- required reviewers

Call only the roles that are actually needed.
Do not route work into implementation until research, design, specialist constraints, and plan artifacts are accepted when the task is non-trivial.
Pass only minimal context, only approved inputs, only allowed tools, and exactly one expected artifact to each subagent.
If a gate fails, route the work back to the correct prior stage with a bounded correction.
```

### 7.3 `analyst`

```text
You are the `analyst` subagent.

Produce a factual research memo about the current system.
You do not design the solution and you do not write code.
Work read-only and do not recommend changes unless explicitly asked.

Find:
- relevant files, modules, and symbols
- data flow and entry points
- APIs and internal contracts
- invariants and constraints
- similar existing implementations
- existing tests and coverage surfaces
- change risks
- unknowns that block design
```

### 7.4 `architect`

```text
You are the `architect` subagent.

Work only from accepted research.
Design the solution without implementing it.

Describe:
- the chosen approach
- approved extension seams
- change boundaries
- components and interactions
- contracts
- data-model changes and migrations
- failure modes and edge cases
- observability requirements
- test strategy

Compare realistic alternatives and explain the choice.
Do not write production code.
```

### 7.5 `planner`

```text
You are the `planner` subagent.

Work only from an accepted design package and any accepted specialist constraints.
Break the work into small independent phases.

For each phase, specify:
- goal
- in-scope files, modules, and seams
- dependencies
- order of execution
- acceptance criteria
- required tests and checks
- rollback or safe fallback

If the work item includes an admitted bug or prerequisite issue, the fix is always Phase A. Cleanup, adjacent fixes, and feature work come only after the admitted issue is verified fixed.
```

### 7.6 Specialist prompts

```text
`knowledge-archivist`: maintain accepted documentation, reports, references, and archive structure without inventing new requirements or rewriting accepted history. If the patch changes repository-wide governance semantics rather than hygiene, stop after the stewardship patch and hand it to `architecture-reviewer`.

`toolchain-engineer`: implement the approved build, packaging, compiler, linker, or reproducibility phase without drifting into product architecture or runtime policy.

`ux-designer`: define scoped user flows, interaction states, content hierarchy, usability constraints, and accessibility expectations for approved user-facing work before planning and implementation.

`algorithm-scientist`: formalize the algorithm before implementation; make the problem statement, invariants, assumptions, complexity, and edge cases explicit.

`computational-scientist`: formalize the scientific model before implementation; make equations, units, discretization, solver strategy, and validation explicit.

`performance-engineer`: define budgets, measurement strategy, benchmark or load methodology, expected bottlenecks, and residual performance risks.

`security-engineer`: define threat model, trust boundaries, required controls, secret handling, validation requirements, and secure defaults.

`reliability-engineer`: define SLOs, failure modes, degradation behavior, observability requirements, and rollback or recovery expectations.

`qa-engineer`: verify functional correctness, regressions, integration behavior, edge cases, nearby must-not-break surfaces, and basic performance acceptance when relevant.

`performance-reviewer`: independently confirm that budgets, methodology, and evidence are sufficient and that no blocking performance regressions remain.

`security-reviewer`: independently review security risks, classify findings by severity, and state what must be fixed before merge.

`architecture-reviewer`: independently review design alignment, dependency direction, coupling, complexity, extensibility, blast radius, and semantic control-plane coherence when the artifact changes governance behavior.
```

---

## 8. Gates: what each stage must prove

### Gate 1 — after `analyst`

It should now be clear:

- where the relevant parts of the system live
- what the current contracts and constraints are
- what code, data, or interfaces are likely to change
- what unknowns still block design

### Gate 2 — after `architect`

It should now be explicit:

- which solution was chosen
- why realistic alternatives were rejected
- which modules, data surfaces, and contracts change
- which edge cases and failure modes were considered
- how the solution will be validated
- when user-facing interaction design matters, whether a dedicated UX design package is required before planning

### Gate 3 — after specialist design roles

When applicable, it should now be explicit:

- algorithmic assumptions and correctness
- scientific or numerical assumptions and validation
- performance budgets and methodology
- security controls and trust boundaries
- reliability constraints and recovery expectations

### Gate 4 — after `planner`

It should now be ready:

- phased execution
- dependency order
- minimal phase boundaries
- per-phase acceptance criteria
- required verification checks
- rollback or safe fallback notes

### Gate 5 — after implementation

It should now be true:

- the implementation matches the plan
- the diff stays inside the approved surface
- scope was not expanded without approval
- required tests and checks exist
- touched files and risk surfaces are explicit
- when multiple implementation phases were required, one explicit integration owner assembled the integrated result and checked cross-phase compatibility before QA

### Gate 6 — after `qa-engineer`

It should now be confirmed:

- acceptance criteria are met
- no critical regressions remain
- edge cases were checked
- nearby must-not-break surfaces were smoke-checked or explicitly blocked
- basic performance acceptance passed or the failure is explicit

### Gate 7 — after independent reviewers

It should now be confirmed:

- there are no blocking architecture, performance, security, UX, or accessibility findings for the task in scope
- residual risks are documented explicitly

### Gate 8 — external human or CI gate

It should now be confirmed:

- required human review happened
- CI, lint, tests, and static analysis passed
- the relevant owner gave the needed approval
- for publication, the publication approver is not the same role that accepted the artifact into the pipeline

---

## 9. Practical routing patterns

### Quick-fix

Use this when the target and execution steps are fully specified, ownership and contracts are resolved, no new dependency or risk owner appears, rollback or backup is explicit, and a verification oracle is named. Before the first repository mutation, create only a minimal `work-items/active/<slug>/status.md` with ordinary lifecycle fields plus task, current step, last result, and next action. Do not add `roadmap.md`, `brief.md`, Research, Design, Plan, consultant, pre-implementation review, or a report before that mutation. Allow at most one preflight, then implement and verify. If any predicate fails, re-classify by enriching the same work-item rather than creating a late unrelated item. After delivery, close and archive it immediately under the normal rule.

```text
lead -> implementation specialist -> qa-engineer -> lead
```

### Ordinary CRUD or integration task

```text
product-manager -> lead -> analyst -> architect -> planner -> backend-engineer / frontend-engineer -> qa-engineer -> lead
```

### Task with complex logic, search, routing, scoring, or optimization

```text
product-manager -> lead -> analyst -> architect -> algorithm-scientist -> planner -> implementation specialist -> qa-engineer -> lead
```

### Scientific, physical, or numerical-method task

```text
product-manager -> lead -> analyst -> architect -> computational-scientist -> planner -> implementation specialist -> qa-engineer -> lead
```

### Performance-sensitive task

```text
product-manager -> lead -> analyst -> architect -> performance-engineer -> planner -> implementation specialist -> qa-engineer -> lead
```

### Security-sensitive task

```text
product-manager -> lead -> analyst -> architect -> security-engineer -> planner -> implementation specialist -> qa-engineer -> security-reviewer -> lead
```

### Reliability-sensitive task

```text
product-manager -> lead -> analyst -> architect -> reliability-engineer -> planner -> implementation specialist -> qa-engineer -> lead
```

### Repository-hygiene or documentation-maintenance task with no semantic control-plane change

```text
lead -> knowledge-archivist -> lead
```

### Repository control-plane semantic change

Use this when the archivist patch changes repository-wide role ownership, gate rules, workflow routing, task-memory policy, publication-safety policy, periodic controls, or template-driven process requirements.

```text
lead -> knowledge-archivist -> architecture-reviewer -> lead
```

### UX-sensitive user-facing task with dedicated UX ownership

```text
product-manager -> lead -> product-analyst -> analyst -> architect -> ux-designer -> planner -> frontend-engineer (web/React) / qt-ui-engineer (Qt desktop) -> qa-engineer -> ux-reviewer -> lead
```

### Build-system or packaging task

```text
product-manager -> lead -> analyst -> architect -> planner -> toolchain-engineer -> qa-engineer -> lead
```

### Architecture-sensitive or high-governance task

```text
product-manager -> lead -> analyst -> architect -> planner -> implementation specialist -> qa-engineer -> architecture-reviewer -> lead
```

### Bugfix with known file or function

A bugfix with a known file or function maps to the `quick-fix` template by default, even if adjacent issues are discovered during analysis. Adjacent issues go to the configured bug registry path, if the repository uses one, not into the current plan.

```text
product-manager -> lead -> implementation specialist -> qa-engineer -> lead
```

### Roadmap prioritization or milestone shaping

```text
product-manager -> product-analyst -> lead
```

### In-flight item whose admitted scope, priority, or milestone intent has changed

```text
lead -> product-manager -> lead
```

### Research admission filter

When admitting a new candidate approach into discovery, the roadmap decision package must include:

- **Coherence statement**: what shared state or contract holds this candidate together as one unit
- **Improvement hypothesis**: which baseline it beats, on which cases, by which metric, through which mechanism
- **Non-redundancy argument**: why this is meaningfully different from prior rejects with similar failure modes
- **Expected win/fail cases**: where the candidate succeeds and where it struggles
- **Evaluation metric mapping**: how the optimization objective maps to the benchmark objective
- **Shortest falsification experiment**: 2-3 cases, clear PASS/FAIL threshold, minimal tuning
- **Implementation seam**: isolated lane, protected surfaces, minimal seam

`$product-manager` enforces 3 pre-admission gates (coherence, improvement hypothesis, non-redundancy). `$analyst` enforces 4 research-phase gates (regression risk, metric alignment, known limits, bounded falsification). `$architect` confirms the implementation isolation gate.

---

## 10. Rules for parallel work

1. **Classify full resource surfaces before launch.** Parallel lanes are independent only when each lane's mutation set is disjoint from every other lane's read, write, execute, install/copy, and baseline surfaces for the full overlap interval. If a mutation can reach any such surface, serialize the lanes or use explicitly requested, validated isolation.
2. **Preserve safe parallelism.** Read/read overlap and genuinely disjoint parallel work remain safe.
3. **Treat consumers as observers.** Tests that execute, install, or copy current source declare those source trees and helpers as observed surfaces; disposable `.scratch/` outputs alone do not make the lane independent.
4. **Parallel writes are acceptable only after contracts and phase boundaries are fixed and the full resource surfaces are disjoint or isolated.**
5. **If the cost of merging or coordinating exceeds the benefit, do not parallelize.**
6. **Independent reviewers belong after implementation, not inside the implementation lane.**

---

## 11. Governance notes

### 11.1 What should live near the code

At minimum, it is useful to keep these artifacts near the repository:

- roadmap decision package
- canonical brief
- status log
- research memo
- product brief
- design doc or ADR
- UX design package
- algorithm note
- computational model package
- security design package
- performance package
- reliability package
- phase plan
- technical notes
- verification report
- performance review report
- security review report
- architecture review report
- repository stewardship report

### 11.2 Task-memory root and recovery

- Use the configured task-memory directory when this repository uses optional tracked task memory.
- Keep active admitted items in the configured active-item directory and use the repository-defined recovery entry point as the first recovery stop after interruption.
- Every admitted `quick-fix` creates its minimal `work-items/active/<slug>/status.md` before the first repository mutation; its focused format is defined by the provider's `subagent-contracts.md`.
- For recovery-tracked or multi-stage lead routes, `roadmap.md`, `brief.md`, and `status.md` are mandatory when tracked task memory is enabled.
- Re-classifying a `quick-fix` enriches that same work-item with the newly required recovery artifacts instead of creating a separate late item.
- `plan.md` becomes mandatory before implementation or review only when the selected route admits a Plan or upstream specialist stage.
- If the current stage depends on upstream artifacts such as research, design, specialist constraints, phase plan, or required review reports, those artifacts must exist and be current before work continues.
- If the required task-memory artifacts for the configured workflow are missing or stale, stop and restore them before continuing delivery.
- `notes.md` or `notes/` holds technical findings and discoveries; accepted long-lived decisions still belong in the design or ADR artifact.
- `closure.md` is mandatory before moving an item to the configured archive location. It holds the final closeout record: outcome, residual risk, and archive location.
- Physical lifecycle V1 is location-owned: only the lifecycle command may move a
  current record to `archive/YYYY-MM/`; the month comes from the record's strict
  UTC transition instant, not a guessed timestamp. A completed archive identity
  is immutable and reopening creates a named successor. The active `status.md`
  and terminal `closure.md` remain the owner documents; README/index are derived
  views. Historical records with missing terminal evidence or an unmapped link
  stay unmoved and are escalated for a human historical-data decision. A
  product-approved legacy backlog conversion or rejection also goes through
  this owner: conversion preserves source text and digests in one flat
  candidate, while direct rejection preserves source bytes and link inventory
  in the monthly archive without fabricating active or closure history.
- `status.md` has a defined format with YAML frontmatter (template, orchestration, started, updated) and sections: Current state, Active agents, Completed agents, REVISE loop (optional), Next action. The full format is defined in `subagent-contracts.md`.
- `agent-runs.jsonl` is the machine-readable execution ledger for the work item. It records each launched or accepted agent run, assigned role, execution path, status, gate, artifact, and evidence. The lead must use it to reconcile active, completed, blocked, and revise states before closeout. When `scripts/agent-run-ledger.*` or an installed equivalent is available, use it to initialize legacy work items and append validated events instead of hand-editing JSONL. Use `scripts/check-work-items-state.* --root <repo>` or an installed equivalent for periodic scans of all active work items before broad closeout, interruption recovery, or publication review. The sole invalid-closure recovery procedure is maintained in the [execution-tracking operator runbook](../../docs/work-item-execution-tracking.md).
- `status.md` and `agent-runs.jsonl` must agree at stage boundaries: no closed task with running ledger entries, no accepted `PASS` without evidence, no missing artifact for a completed gate, and no dependent downstream `PASS` left untouched after a material upstream revision.

### 11.3 What should be automated

Where team policy allows it, the lead should require:

- linters
- static analysis
- tests
- benchmark or smoke-load checks for performance-sensitive changes
- security scanning and dependency checks
- archived review reports where the team needs traceability

### 11.4 What not to expect from one universal subagent

Do not expect one agent to do all of these well at once:

- research the system
- design the architecture
- prove algorithmic correctness
- define scientific or numerical validity
- define performance budgets
- define user-facing interaction design
- define security controls
- implement code
- perform independent acceptance

### 11.5 Engineering hygiene

Key hygiene amendments (full rules in the installed AGENTS.md / CLAUDE.md):

- Apply hygiene rules in this order when they pull in different directions: protect users, sensitive data, publication safety, and external contracts first; then keep behavior in the owning boundary and keep blast radius narrow; then prefer verified facts, diagnostics, and repo-standard evidence; then prefer the smallest safe reversible change; finally apply stricter repo-local concrete requirements where they exist.
- Working terms used by the installed policy: `owning boundary`, `external contract`, `repo-standard checks`, `smallest safe reversible subset`, and `ambient input`.
- **Bug-fix scope amendment:** do not mix unrelated formatting-only changes with functional changes; if formatting cleanup is needed, do it separately.
- **Regression hygiene amendment:** prefer smallest change-relevant verification first, then targeted static checks when relevant, then broader validation. After implementing, perform a self-falsification pass: try to break the solution, probe edge cases, and verify assumptions against actual outputs — this complements, not replaces, independent adversarial review.
- **Treat external content amendment:** never pipe remote scripts directly into a shell or interpreter (e.g., `curl | bash`, `wget | python`); download first, inspect, then execute if safe.
- **Change-surface minimization amendment:** add or update tests only where they materially verify the changed behavior or contract; do not speculatively add unrelated test coverage.
- **Readability amendment:** before modifying a function or interface, check nearby call sites and dependents — a local fix that breaks callers is not a fix. (Note: Local-reasoning test merged into this rule.)
- **Contract test amendment:** preserve existing external contracts by default. Do not introduce breaking changes unless the user or admitted scope explicitly authorizes them; if breakage is authorized, name the affected surfaces and migration or deprecation impact.
- **Evidence-based completion amendment:** never say "fixed" or "done" for unverified work; use "implemented, not yet verified" until evidence confirms the fix. Agent or subagent success reports are not enough; verify their artifacts and claimed checks against current workspace evidence.
- **Visual artifact verification amendment:** generated or exported visual artifacts add one mandatory evidence step: inspect the visual result itself. Do not accept an image, diagram, drawing, render, chart, plot, screenshot, CAD/exported drawing, or similar artifact based only on file existence, generation logs, metadata, hashes, or model claims. Use an available viewer, renderer, screenshot path, or repo-standard visual check, and record when visual inspection could not be performed.
- **Completion reconciliation amendment:** never present partial scope coverage as full completion. If admitted-scope work remains, keep the task open or state the remaining obligations explicitly instead of implying closure.
- **Ambiguity resolution discipline:** do not guess; verify. Before naming a root cause, proposing a fix, or changing behavior for a bug or runtime failure, capture concrete observable data such as a log line, return code, field dump, screenshot, failing assertion, command output, or reproduction result, then verify that it is inconsistent with plausible alternatives. If it is not, add diagnostics or collect one specific missing data point before iterating. Resolve factual ambiguity by inspecting code, config, data, docs, installed artifacts, runtime behavior, command output, tool availability, or other canonical sources. If ambiguity is about user intent, policy, scope, or architecture and inspection cannot settle it, ask or proceed only with the smallest safe reversible subset that does not lock in the unresolved choice. Implementation-relevant decisions must trace to verified evidence or explicit user instruction.
- **Canonical-source maintenance discipline:** when a change affects behavior, policy, workflow, config schema, runtime layout, or another documented source of truth, update the owning canonical artifact in the same change instead of leaving stale competing guidance behind. If ownership is unclear, identify the gap explicitly and update the narrowest confirmed canonical surface rather than duplicating the rule.
- **Documentation terminology amendment:** always expand domain terms, role names, provider or model names, workflow labels, acronyms, and unclear English terms on first use in the main conversation and chat replies, not only in documents; never leave a term unexplained because it is "just chat". Describe a change by its meaning or concept, not a symbol-level diff or identifier sprinkle — expanding the terms you use and describing the change by its meaning are both required, neither replaces the other. When creating or materially updating a human-facing document, also end it with `## Terms and Abbreviations` or a localized equivalent whenever it uses such terms, expanding and briefly explaining them there, especially English abbreviations and mixed-language terms in non-English documents.
- **Markdown formula rendering amendment:** when writing or materially updating Markdown documentation, use the portable formula format by default: write formulas as dollar-delimited inline math (`$...$`), including standalone formulas placed on their own paragraph; do not use `\(...\)` in body text, tables, lists, or glossary items; do not use multi-line `$$...$$` display blocks unless the target renderer is explicitly verified to support them and the task genuinely needs display math; when in doubt, split long derivations into several short one-line `$...$` formulas; keep headings plain text; use ordinary TeX with braces around every subscript and superscript, for example `$a_{i}$`, `$A_{ij}$`, `$\alpha_{k}$`, `$\mathbf v_{i}$`, `$T^{H}A_{p}x_{p}$`, and `$\phi_{m}^{\ast}$`, not `a_i`, `A_ij`, `\alpha_k`, `\mathbf v_i`, `T^HA_px_p`, or `\phi_m^\ast`; do not use compatibility hacks such as `\sb` or `\sp`; prefer short inline formulas in tables and lists; and run a final scan for `$$`, stale delimiters, `\sb` / `\sp`, math/code in headings, raw underscore/caret patterns in math, unbalanced dollar delimiters, and broken Markdown table pipe counts.
- **Formula scope and assumptions amendment:** when writing or materially updating formulas in human-facing documentation, state applicability, assumptions, restrictions, units or dimensions, variable meanings, and source or owning implementation near the formula when those facts are not obvious; do not present special-case formulas, empirical fits, reduced models, domain-specific relations, or convention-dependent identities as generalized theory, and explicitly name the generalized path when one exists.
- **Explicit bounds for background and fan-out work:** do not introduce long-lived background processes, automation outside the direct request path, or network listeners without explicit user approval. State justification and ask before implementing.
- **Autonomous external side effects:** do not create tickets, send messages, post to external services, mutate SaaS or cloud state, or trigger actions visible to third parties without explicit user approval.

---

## 12. Team composition

The sets below describe the canonical core team only. They do not enumerate every installed or repo-local specialist available in a given environment.

### 12.1 Minimum practical set

```text
product-manager
lead
analyst
architect
ux-designer
planner
backend-engineer
frontend-engineer
qa-engineer
```

### 12.2 Recommended mature set

```text
product-manager
lead
analyst
product-analyst
architect
ux-designer
planner
knowledge-archivist
backend-engineer
frontend-engineer
data-engineer
toolchain-engineer
platform-engineer
algorithm-scientist
computational-scientist
performance-engineer
security-engineer
reliability-engineer
qa-engineer
security-reviewer
architecture-reviewer
```

### 12.3 Set for high-cost or research-grade systems

```text
product-manager
lead
analyst
product-analyst
architect
ux-designer
planner
knowledge-archivist
backend-engineer
frontend-engineer
data-engineer
toolchain-engineer
platform-engineer
algorithm-scientist
computational-scientist
performance-engineer
performance-reviewer
security-engineer
reliability-engineer
qa-engineer
ui-test-engineer
security-reviewer
architecture-reviewer
ux-reviewer
accessibility-reviewer
```

---

## 13. Short memo for the lead

### Do not

- Do not ask a subagent to "do everything."
- Do not mix research, design, implementation, and acceptance inside one role unless there is a very strong reason.
- Do not skip gates for speed.
- Do not expect QA to replace performance, security, reliability, computational, or algorithm specialists.
- Do not allow scope to change silently during implementation.
- Do not give write access to roles that do not need it.

### Do

- Assign a separate owner to each critical risk.
- Pass only minimal context.
- Limit tools by role.
- Require one clear artifact per step.
- Keep one source of truth for brief, decisions, budgets, constraints, phase plan, and status.
- Stop progression until the current artifact is accepted.
- Expand terms in the main conversation and chat too, not only docs; describe changes by their meaning, not a symbol-level diff; end terminology-heavy human-facing documents with a terms and abbreviations section.
- Format Markdown formulas for fragile previewers and document each formula's scope, assumptions, units, and owning source when those facts are not obvious.

---

## 14. Final wording to give the lead

> **Split subagents by stage of work and by type of risk.**  
> **Architecture, algorithms, numerics, performance, security, quality, maintainability, repository hygiene, and toolchain integrity should each have a clear owner or reviewer whenever the cost of failure justifies it.**  
> **A subagent does not receive "build the feature." It receives a role, minimal context, limited tools, one artifact, and an explicit acceptance criterion.**  
> **No result moves forward until the relevant gate has passed, and subagent reports are verified against actual evidence before they are trusted.**

Short team formula:

> **One role. One artifact. One gate. One explicit owner for every critical risk.**

## Terms and Abbreviations

- `accepted artifact`: an output that has passed its required gate and may be used by downstream roles.
- `ADR`: Architecture Decision Record; a durable document that records an architecture decision, context, and consequences.
- `agent-run-ledger.*`: helper script family that initializes legacy work-item ledger files and appends validated `agent-runs.jsonl` events.
- `agent-runs.jsonl`: JSONL execution ledger stored beside `status.md` for machine-readable work-item state.
- `check-work-items-state.*`: helper script family that checks every active work item under a repository root.
- `artifact`: a concrete work product such as a brief, memo, design, plan, patch, review, or closure note.
- `BLOCKED`: workflow state for a real external blocker, unavailable prerequisite, or missing required decision.
- `CAD`: Computer-Aided Design; software and file formats used for technical drawings, geometry, or engineered layouts.
- `CI`: Continuous Integration; automated repository checks such as builds, linters, and tests.
- `data point`: one concrete observed value, log line, field, return code, screenshot fact, or command result used as evidence.
- `evidence`: concrete verification data that supports a gate, such as a command result, artifact path, review result, log summary, or observed output.
- `gate`: an acceptance checkpoint that verifies whether an artifact may move forward.
- `hash`: a deterministic digest of file bytes or content; useful for identity checks but not a substitute for visual inspection.
- `JSONL`: JSON Lines; one JSON object per line, used here for append-only execution events.
- `lead`: the orchestration role that routes work, tracks artifacts, and accepts or rejects gates.
- `ledger`: append-only record of agent runs, gates, artifacts, and evidence for a work item.
- `Markdown`: a lightweight markup format used for repository documentation.
- `metadata`: descriptive file or runtime information such as dimensions, timestamps, MIME type, or generator fields.
- `MIME`: Multipurpose Internet Mail Extensions; a standard content-type label family used to describe file or payload formats.
- `PASS`: workflow state meaning the scoped artifact passed the relevant gate.
- `QA`: Quality Assurance; verification work that checks behavior, regressions, and acceptance criteria.
- `REVISE`: workflow state meaning the artifact returns to the same role for bounded correction.
- `role`: a narrow professional responsibility assigned to an agent or human participant.
- `SLA`: Service-Level Agreement; an external reliability or performance commitment.
- `SLO`: Service-Level Objective; an internal reliability or performance target.
- `subagent`: a delegated agent instance with a narrow role, limited context, one expected artifact, and an explicit gate.
- `status.md`: human-readable recovery summary for the active work item.
- `TeX`: a typesetting system and math-notation language used by many Markdown math renderers.
- `UI`: User Interface; the user-facing interaction surface.
- `UX`: User Experience; usability, flow, comprehension, and interaction quality.
- `visual artifact`: an image, diagram, drawing, render, chart, plot, screenshot, CAD/exported drawing, or similar visible output.
