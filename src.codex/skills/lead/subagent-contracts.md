# Subagent Contracts

Use these templates when the lead needs a crisp handoff or a gate checklist.

## Shared handoff template

```text
Role:
Goal:
Approved inputs:
- <accepted artifact or fact>
- <accepted artifact or fact>
Allowed tools (affirmatively name repo-relevant MCP servers/skills, or state "runtime default surface"):
- <allowed tool, MCP server, skill, or "runtime default surface">
- <allowed tool, MCP server, or skill>
Scope:
- <allowed area>
Out of scope:
- <forbidden area>
Allowed change surface:
- <approved files, modules, or seams>
Must-not-break surfaces:
- <nearby but unrelated areas that need isolation or smoke coverage>
Diff-invisible invariants:
- <behavior or contract that must remain true although the diff may not expose it>
Named regression guard:
- <test/probe plus expected result that falsifies preservation>
Evidence discipline:
- <cite each decision-driving claim with an in-repo file:line, installed-dependency surface check, versioned official docs/upstream source URL, or target-environment smoke test preserved under .scratch/; otherwise label it ASSUMPTION (UNVERIFIED) with the resolving step; never use "should work", "should be fine", "probably", "likely", "I think", "based on training data", "in general", or "this pattern usually works" as a correctness-driver>
Defect-class inventory:
- <when one instance was cited: every participant to audit—parallel arms, cell/data shapes, return paths, and read-sites; otherwise "not-triggered">
Constraints:
- <constraint>
- <constraint>
Expected artifact:
- <one artifact>
Acceptance criteria:
- <criterion 1>
- <criterion 2>
Gate to next stage:
- <what must be proven>
```

Before dispatch, fill `Diff-invisible invariants` and `Named regression guard`; `none` is valid only with a one-line reason. An implementation or review handoff with either field omitted is incomplete.

`Approved inputs` identify the producing run's declared scope and accepted artifact revision when available; no new handoff field is required. Evaluate authored claims and review verdicts against the producing run's declared scope and accepted baseline: later independently owned lane deltas are reviewed in their own lane and do not retroactively falsify the earlier artifact; an actual material revision of the accepted upstream artifact still invalidates dependent `PASS` states and triggers dependent re-review.

Receiving-side echo: the returned artifact MUST (a) report the Named regression guard's actual result (expected vs observed), (b) answer each Diff-invisible invariant as verified or ASSUMPTION (UNVERIFIED), (c) when the dispatch cited a defect class, include the class audit — every enumerated participant classified fixed / not-affected. An artifact missing the echo fails the mechanical acceptance gate.

**Class-completeness trigger (mandatory):** when a reviewer, bot, or test cites one instance of a defect class, the dispatch prompt MUST direct the recipient to enumerate every participant of that class, classify each one, and fix every confirmed instance. A prompt scoped only to the named line is invalid.

**Object-axis trigger (mandatory for C1-based clean verdicts, PRE-verdict).** The class-completeness
trigger above fires AFTER a finding: "you found one — where are its siblings?" This one fires BEFORE
a clean/verified verdict that relies on a C1 single-owner-invariant assessment: "you are about to
call this clean — did you aim at the right object?" A lens can be present, sharp and
productive and still miss an entire class because it was never aimed at a second axis: a real audit
ran the split-ownership lens, found "one conceptual decision has four independent owners", and never
found the same defect in policy VALUES — it asked who owns the decision, never who owns the number.
The rule for the number already existed and was not applied.

When a clean/verified verdict relies on a C1 (single-owner-invariant) assessment, the dispatch MUST
require, and the returned artifact MUST carry, an object-axis record — one row per C1 assessment used
to support that verdict:

`| lens | primary object examined | adjacent object classes re-aimed at | decision facts proved (not a proxy) | result + evidence |`

For such a C1-reliant verdict, an absent or empty-celled record fails mechanical acceptance exactly
like the receiving-side echo; a grouped `N/A` needs a bounded one-phrase reason, never silence.
Dispatches and verdicts that do not rely on a C1 assessment owe no object-axis record. Define the adjacent axis
FUNCTIONALLY, never as a noun checklist (a closed list of nouns is the same blind lens one level
down): the representations a legitimate policy change must update together; objects under ANOTHER
owner that the operation touches; and the facts the decision actually used, not a proxy for them
("same object" is not "same state" unless identity IS the predicate).

Admission predicate for a value candidate — apply BEFORE searching, so this never becomes a literal
hunt: name (a) the policy owner who would legitimately change it, (b) the change that would trigger
it, (c) the consumers or boundary representations that MUST co-vary, and (d) the one place they would
look. A world fact, protocol constant, or algorithm-local literal fails (b) or (c) and is excluded —
that exemption is deliberate. A literal is a discovery seed, never a finding. Same-owner candidates
aggregate into ONE finding. Without co-variation it is not a single-owner defect at all — it may be
plain hardcoding, which is a different rule and a different fix.


## Artifact gate — no delegation without brief

A lead MUST NOT delegate recovery-tracked or multi-stage work until the configured task-memory item folder, if the repository uses one, contains a verified `brief.md` and full `status.md`.

- `brief.md` must have explicit scope, out-of-scope, acceptance criteria, required roles, and critical risks with owners.
- `status.md` must have a current snapshot with stage, last accepted artifact, next concrete action, and any open obligations that still block closeout.
- If either artifact is missing, stale, or incomplete, the lead restores only the lead-owned task-memory state from persisted accepted artifacts BEFORE delegating any specialist role when task memory is configured. Do not reconstruct missing specialist artifacts or factual findings from chat memory.
- This full-artifact gate is non-negotiable after routing selects recovery-tracked work. For `quick-fix`, the minimal status below is the handoff and must exist before implementer dispatch and the first repository mutation; no `brief.md` or other heavy prelude artifact is required.

### Quick-fix minimal status.md

Create `work-items/active/<slug>/status.md` with only these ordinary lifecycle fields and recovery facts:

```markdown
---
template: quick-fix
status: active
started: <YYYY-MM-DD HH:MM>
updated: <YYYY-MM-DD HH:MM>
---

- **Task**: <admitted objective>
- **Current step**: <current execution step>
- **Last result**: <last completed step or admission result>
- **Next action**: <next concrete action>
```

An admitted `quick-fix` does not add `roadmap.md`, `brief.md`, Research, Design, Plan, consultant, pre-implementation review, or a report before its first mutation. If it is re-classified, keep this work-item and enrich its recovery state to the full format below instead of creating a late unrelated item. After delivery, apply the normal immediate closure/archive rule.

### status.md format

```markdown
---
template: <template name>
orchestration: light | full-lead
started: <YYYY-MM-DD>
updated: <YYYY-MM-DD HH:MM>
---

## Current state

- **Primary task**: <one active objective, e.g. "full-impact review of current change set">
- **Primary task status**: <active | side-interrupted | parked | closed>
- **Interruption marker**: <none | INTERRUPTED(no-artifact)>
- **Stage**: <current stage name or number>
- **Main conv role**: <what main conversation is doing: orchestrating | waiting for agents | reviewing artifact | idle>
- **Last accepted artifact**: <filename or "none">
- **Open obligations before closeout**: <none | remaining required work still inside admitted scope>
- **Epic**: <parent epic slug, or none> — present only when this work-item belongs to an epic; a single bare `Epic: <slug>` line is the join key the epic roll-up reads (see the lead skill `## Epics`)
- **Depends-on**: <comma-separated work-item slugs, or none> — other work-items this one needs completed first; a single bare `Depends-on: <slug>, <slug>` line is what the derivation reads. A standing, planned inter-work-item dependency edge (distinct from the runtime `BLOCKED:*` gate verdicts). Targets are work-items only, resolved across physical `active/`, `archive/YYYY-MM/`, and `backlog/` locations (a backlog match is existence, not done). A target that resolves nowhere is folded into `blocked-by`, never treated as satisfied. The lead derives `blocked-by` (open targets) and the ready-set from these lines (see the lead skill `## Dependencies`)
- **Priority**: <high | medium | low, or none> — scheduling urgency set by `$product-manager` at admission; distinct from bug/perf SEVERITY (defect impact). A low-severity bug can still be high-priority.

## Active agents

| Agent | Role | Model/effort | Status | Launched |
| --- | --- | --- | --- | --- |
| <description> | <role> | <model/profile + effort — one-line complexity rationale> | running | <HH:MM> |

## Completed agents

| Agent | Role | Result | Artifact |
| --- | --- | --- | --- |
| <description> | <role> | PASS/REVISE/BLOCKED | <filename> |

## REVISE loop

| Field | Value |
| --- | --- |
| **Stage** | <stage name where REVISE occurred> |
| **Iteration** | <1-3, or "escalated"> |
| **Gate role** | <qa-engineer, security-reviewer, etc.> |
| **Last finding summary** | <one-line summary of what the gate found> |
| **Owner of next action** | <implementer role that must fix, or "user" if escalated> |

## Next action

<What happens next: which role to invoke, what artifact to review, or what decision to make.>
```

Legacy handling: older `status.md` files may carry `orchestrator: main | lead`. Read `main` as `orchestration: light` and `lead` as `orchestration: full-lead`; do not rewrite old files in bulk. The orchestrator is ALWAYS the main conversation (holding the Lead role) — the retired field encoded orchestration weight, not a different owner, which is why it is renamed. New/updated files write `orchestration:`.

The REVISE loop section is optional — include it only when a stage has returned REVISE and the loop is active. Remove it when the loop resolves (PASS or escalation).

### agent-runs.jsonl format

Only the root main conversation holding Lead writes `agent-runs.jsonl`: it records each launch and, after receiving and accepting the assigned artifact and evidence, its terminal outcome. A main-owned validated helper or wrapper may perform that write on the root's behalf.

The ledger is machine-readable execution state; `status.md` remains the human-readable recovery summary. A `PASS` in `status.md` is not accepted unless the corresponding ledger event has `gate: "PASS"`, `status: "completed"`, an artifact path, and at least one evidence entry.

Minimum required fields are defined by `shared/schemas/agent-runs.schema.json`: `schemaVersion`, `runId`, `workItem`, `role`, `executionRole`, `status`, `gate`, `scope`, `startedAt`, and `updatedAt`.

When `scripts/agent-run-ledger.*` or an installed equivalent is available, prefer its `append` command so the event is validated and rolled back on failure. Use its `init` command for one-time migration of legacy work items with missing status sections or ledger files. Manual JSONL append is acceptable only when no helper is available.

Before closeout, run `scripts/validate-work-item-state.* --work-item <path>` or the installed equivalent when the repository exposes one. Before broad closeout, interruption recovery, or publication review, run `scripts/check-work-items-state.* --root <repo>` or the installed equivalent to scan all active work items. Closeout is blocked while the ledger contains running agents, duplicate run IDs, missing artifacts for `PASS`, `PASS` without evidence, stale running agents, or inconsistent `BLOCKED` / `REVISE` status.

No-artifact interruption rule:
- A handoff interrupt or worker stall without an artifact does not count as a substantive REVISE artifact.
- Set `Primary task status: side-interrupted` and `Interruption marker: INTERRUPTED(no-artifact)` in `status.md` for orchestrator bookkeeping.
- Keep the stage open, and either rerun the same role with a tighter slice or route to the proper factual role.
- The lead must not synthesize the missing artifact or replace missing factual work inline.
- If the interrupted stage belongs to a full-impact review or verification pass, keep that review as the primary task until a review artifact is emitted or the user explicitly parks/cancels it.

## Shared response format

```text
1. Summary
2. Artifact
3. Risks / Unknowns
4. Recommended next role
5. Gate: PASS | REVISE | BLOCKED:<class> | RETURN(role)
```

### BLOCKED classification

| Class | Meaning | Orchestrator action |
|---|---|---|
| `BLOCKED:dependency` | Cannot proceed — missing tool, environment, access, or information that no current agent can provide | Present to user for resolution |
| `BLOCKED:prerequisite` | Discovered adjacent work that must complete first (e.g., broken adjacent module, missing migration) | File in the configured bug registry path, if the repository uses one → user decides priority → resume when resolved |

If no class is specified, treat as `BLOCKED:dependency` (conservative default).

Fact-first note:
- When a role makes a decision or recommendation, it should clearly distinguish confirmed facts, assumptions, and judgment.
- If the main gap is missing evidence, recommend the appropriate factual role instead of escalating straight into broader opinion.

Consultant exception:
- `$consultant` returns the same first four sections, but ends with `5. Advisory status: NON-BLOCKING` and `6. Continuation prompt: <ready-to-send second prompt that begins with a direct imperative to continue and names the next concrete action>`.
- The shared dispatch contract lives in `external-dispatch.md`; writes to `.agents/.agents-mode.yaml` must preserve any existing `consultantMode`, `delegationMode`, `parallelMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer`, `externalProvider`, `externalPriorityProfile`, `reserveResolver`, `externalPriorityProfiles`, `externalOpinionCounts`, `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, `externalModelMode`, `externalCodexProfile`, and `externalClaudeProfile` values, while dropping retired canonical keys during normalization.
- If the selected external consultant path is unavailable or fails, the lead must report that honestly and reroute; do not auto-downgrade into an internal consultant. An internal consultant remains valid only when `consultantMode: internal` was selected explicitly before dispatch. `consultantMode: disabled` waives consultant closeout instead of leaving a hidden blocker, and any explicitly requested or repo-policy-required consultant sweep must follow the selected consultant mode honestly.

## Shared external dispatch contract

Use `external-dispatch.md` when the routing decision prefers or explicitly selects an external adapter.

- The canonical config file is `.agents/.agents-mode.yaml`.
- Read and normalize `.agents/.agents-mode.yaml` before trusting its flags. If the local canonical file is absent, continue resolving the effective Codex overlay in this order: local legacy `.agents/.agents-mode`, pack-local global `~/.codex/.agents-mode.yaml`, pack-local global legacy `~/.codex/.agents-mode`, then shared cross-pack global `~/.agents-mode.yaml` (alongside `~/.claude.json`), before applying built-in defaults. Each key resolves to the highest layer that defines it. Comment-free, partial, or older-layout files are valid legacy input, not valid runtime output.
- Normalize whichever file supplied the effective config into the canonical `.yaml` path in the same scope, do not recreate any legacy file, and do not synthesize a local override on read alone.
- The extended schema contains `consultantMode`, `delegationMode`, `parallelMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer`, `externalProvider`, `externalPriorityProfile`, `reserveResolver`, `externalPriorityProfiles`, `externalOpinionCounts`, `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, `externalModelMode`, shared `externalCodexProfile`, and an optional `externalClaudeProfile` used for Codex-line Claude CLI profile selection.
- `consultantMode` governs `$consultant` behavior only. Allowed values: `external | internal | disabled`; default: `disabled`.
- `reserve` is a symbolic supplemental read-only candidate that may appear only in advisory/review profile orders after primary `claude`/`codex`.
- `parallelMode` governs the general orchestrator fan-out rule across internal and external helper lanes. Allowed values: `manual | auto | force`; default: `auto`.
- The preference flags govern whether eligible implement or review/QA slots route to the external adapters by default.
- The assigned role in the external handoff is a provenance/routing label, not a restriction on universality.
- Resolve external routing in this order: `role eligibility -> provider selection -> CLI availability`.
- There is no generic external adapter for owner roles such as `$product-manager` or `$lead`. If a request lands in one of those lanes, fail fast with an unsupported-route explanation instead of probing providers.
- If the external CLI is unavailable, the role is disabled at the role level and the orchestrator may reroute to another eligible internal specialist.
- `$external-worker` and `$external-reviewer` are direct external launch routes, not internal specialist subagents. Do not satisfy these roles by spawning an internal helper/agent host that then relays to another CLI.
- Any spawned internal subagent remains internal even if its prompt says to act as Gemini, Qwen, Claude, or Codex. Provider-labeled internal delegation does not satisfy an external adapter route.
- **Subagent no-spawn-and-wait rule.** A dispatched subagent is NOT re-invoked when a background child it launched (a `run_in_background` shell-out or a background agent) finishes — background-completion notifications go only to the MAIN orchestrating loop. So a subagent must never launch a background child and end its turn "waiting for the notification"; the child strands and the subagent returns an empty result (the recurring `external`-mode consultant role-confusion). A subagent has two compliant paths: complete the work synchronously in-turn (a single blocking shell-out it parses before returning), or return a result telling the orchestrating runtime to own the long-running/background step and feed the outcome back. The orchestrating runtime — which receives background-completion notifications — owns any launch that cannot finish inside one subagent turn.
- Wherever Codex is the resolved external provider, honor `externalCodexProfile` first. `default` inherits `externalModelMode`: under `runtime-default`, leave Codex on its runtime default model/profile, and under `pinned-top-pro`, start on model `gpt-5.6-sol` with `model_reasoning_effort = "xhigh"` through a supported Codex config/profile path; only an explicitly configured repo-local fully autonomous low-reasoning worker lane may retry once on `gpt-5.6-terra` after usage-limit or quota exhaustion on the primary path. `gpt-5.6-sol-max` requests model `gpt-5.6-sol` with `model_reasoning_effort = "max"` for higher-complexity/hard lanes (NOT `gpt-5.6-sol-ultra`, which spawns subagents and must never be shipped on a subagent lane). `gpt-5.6-terra` selects the balanced Codex model tier (a distinct model, `model_reasoning_effort = "high"`, not an effort downgrade) and must record unavailable or deviated if that model cannot be verified against the installed runtime. `gpt-5.6-sol-xhigh` (shipped as the default) explicitly requests model `gpt-5.6-sol` with `model_reasoning_effort = "xhigh"` via `-c model_reasoning_effort=xhigh` regardless of `externalModelMode`, and is the best-effort sibling of Claude's `opus-xhigh`; consultant lane invocations must always use `gpt-5.6-sol-xhigh` regardless of the operator-set value. Do not silently downgrade below the approved floor.
- Wherever an advisory or review profile order resolves to `reserve`, bind it through `reserveResolver` and record the concrete execution path. It is independent of the primary `claude` candidate and is not a retry, fallback, or transport swap for a failed primary Claude run.
- Treat fallback pools asymmetrically: `gpt-5.6-terra` is the balanced cheaper Codex reasoning lane (a genuine second-choice model), while `reserve` is a symbolic supplemental advisory/review candidate that may appear only after primary `claude`/`codex` in eligible profile orders.
- `externalProvider: auto` resolves through the active production priority profile, then applies explicit-only self-provider exclusion and CLI availability. Example-only providers such as Gemini and Qwen stay explicit-only and must not appear in shipped `auto` profiles.
- `parallelMode` is the general rule for whether independent helper lanes should be parallelized by judgment at all. External fan-out follows that rule instead of defining a separate global concurrency model.
- Independent external adapters may run in parallel when their scopes are disjoint, `parallelMode` permits ordinary parallel fan-out, and provider runtimes support concurrent non-interactive execution. If native internal slot limits would otherwise block more independent eligible lanes, prefer available external adapters instead of silently serializing or dropping them.
- Same-provider reuse is allowed for independent external fan-out. Do not impose a one-instance-per-provider cap when multiple admitted artifacts or disjoint slices need the same helper/provider combination.
- `externalOpinionCounts` still governs distinct-provider opinion requirements for one lane; it does not replace the general `parallelMode` rule or limit brigade-style parallel launches across different independent lanes or slices.
- When the routing decision is "launch a bounded set of external helpers together", prefer the utility skill `$external-brigade` so the brigade has one explicit plan, one ownership table, and one aggregated result surface.

## Role map

Use these current skill names in this repository:

- Treat this role map as the canonical core team only, not as an exhaustive inventory of every installed or repo-local specialist.
- If a narrower installed specialist outside the core team is a better fit for scoped work, the lead may use it.
- If the current repo or workspace defines or clearly implies a repo-local specialist, the lead may use that specialist without adding it to the canonical team map.

- roadmap ownership, milestone shaping, or prioritization maps to `$product-manager`
- `researcher` maps to `$analyst`
- product or business research maps to `$product-analyst`
- UX design for user flows, interaction states, or content hierarchy maps to `$ux-designer`
- `backend-dev` maps to `$backend-engineer`
- `frontend-dev` maps to `$frontend-engineer`
- `qa` maps to `$qa-engineer`
- `mathematical-algorithm-scientist` maps to `$algorithm-scientist`
- scientific modeling or numerical methods maps to `$computational-scientist`
- repository hygiene, documentation curation, or archival consistency maps to `$knowledge-archivist`
- graphics or rendering implementation maps to `$graphics-engineer`
- scientific or data visualization implementation maps to `$visualization-engineer`
- geometry or spatial computation implementation maps to `$geometry-engineer`
- Qt desktop UI implementation maps to `$qt-ui-engineer`
- Qt model or view implementation maps to `$model-view-engineer`
- build systems, packaging, or toolchain implementation maps to `$toolchain-engineer`

## Product Manager

Use when the task is about roadmap ownership, initiative prioritization, milestone shaping, or admission into discovery or delivery.

Return exactly:
- one roadmap decision package

Acceptance criteria:
- the priority decision, sequencing rationale, and bounded scope are explicit
- the package is ready for `$lead`, `$product-analyst`, or `$analyst`
- no architecture, implementation plan, or delivery ownership is embedded in the roadmap decision
- for new candidate approaches entering discovery, the research admission filter gates (coherence, improvement hypothesis, non-redundancy) are addressed in the package

### Minimum research admission package

When admitting a new candidate into discovery, the roadmap decision package must include:

- **Coherence statement**: what shared state or contract holds this candidate together as one unit
- **Improvement hypothesis**: which baseline it beats, on which cases, by which metric, through which mechanism
- **Non-redundancy argument**: why this is meaningfully different from prior rejects with similar failure modes
- **Expected win cases**: where the candidate is expected to succeed
- **Expected fail cases**: where it is expected to struggle
- **Evaluation metric mapping**: how the candidate's optimization objective maps to the benchmark objective
- **Shortest falsification experiment**: 2–3 cases, clear PASS/FAIL threshold, minimal tuning
- **Implementation seam**: where this lives in the repo (isolated lane, protected surfaces, minimal seam) — confirmed by `$architect` after admission

## Analyst

Use for fact-finding only.

Return exactly:
- one factual research memo

Acceptance criteria:
- every claim is tied to source evidence or direct code inspection
- assumptions and unknowns are explicit
- no recommendations are included

## Product Analyst

Use for factual product clarification before design.

Return exactly:
- one product brief

Acceptance criteria:
- scope, constraints, and open questions are evidence-backed
- the artifact stays upstream of design and delivery
- no solution decision is embedded in the brief

## Architect

Use after research is accepted.

Return exactly:
- one design package

Acceptance criteria:
- the chosen design is traceable to accepted facts and constraints
- approved extension seams, stable contracts, dependency direction, and expected blast radius are explicit
- alternatives, interfaces, failure modes, and test strategy are explicit
- no implementation code is included

## Algorithm Scientist

Use when the problem needs formal mathematical or algorithmic framing before implementation.

Return exactly:
- one algorithm note

Acceptance criteria:
- the problem statement, invariants, objectives, and assumptions are precise
- complexity, stability, or probabilistic tradeoffs are explicit
- no implementation code is included

## Computational Scientist

Use when the problem needs scientific modeling, simulation, or numerical-method framing before implementation.

Return exactly:
- one computational model package

Acceptance criteria:
- the model, assumptions, units, and state definitions are precise
- discretization, solver strategy, validation criteria, and numerical risks are explicit
- no implementation code is included

## Security Engineer

Use when the solution needs secure design constraints before planning or implementation.

Return exactly:
- one security design package

Acceptance criteria:
- threat model, trust boundaries, and required controls are explicit
- must-fix constraints are clear
- the result is ready for planning and later `security-reviewer`

## Performance Engineer

Use when the solution needs explicit performance constraints or bottleneck modeling before planning or implementation.

Return exactly:
- one performance package

Acceptance criteria:
- success metrics, budgets, and methodology are explicit
- expected or observed bottlenecks are documented
- the result is ready for planning and later `performance-reviewer`

## Reliability Engineer

Use when the solution needs explicit operability and failure-mode constraints before planning or implementation.

Return exactly:
- one reliability design package

Acceptance criteria:
- SLOs, failure modes, degradation behavior, and recovery expectations are explicit
- observability and rollout or rollback constraints are concrete
- the result is ready for planning and later implementation or review

## UX Designer

Use when approved user-facing work needs interaction design before planning and implementation.

Return exactly:
- one UX design package

Acceptance criteria:
- scoped surfaces, user flows, interaction states, and content hierarchy are explicit
- empty, loading, error, and success behavior is defined for each relevant screen or component
- usability constraints and accessibility expectations are called out
- the result is ready for planner and implementation roles without requiring them to redesign in code
- no roadmap reprioritization, architecture redesign, or implementation code is included

## Planner

Use after the required design and specialist constraints are accepted.

Return exactly:
- one delivery plan

Acceptance criteria:
- phases are small and independently checkable
- allowed change surface, must-not-break surfaces, dependencies, checks, and rollback notes are explicit
- shared or core module changes are isolated and justified explicitly
- code is not written in the plan artifact

## Knowledge Archivist

Use when the approved phase is primarily repository hygiene, documentation curation, report or plan maintenance, reference upkeep, or archival consistency.

Return exactly:
- one repository stewardship package

Acceptance criteria:
- the change stays within approved repository knowledge scope
- canonical docs, plans, reports, references, and archive locations are updated consistently
- path, link, or cross-reference checks were run or clearly reported as blocked

## Implementation Specialists

Use only after plan approval.

Return exactly:
- one implementation package

Acceptance criteria:
- changes stay inside approved scope
- changes stay inside the approved change surface or explicitly escalate a conflict
- required tests and checks were run or explicitly blocked
- design or plan conflicts are escalated instead of patched over

## External Worker

Use when approved worker-side role work should run through the external adapter for an eligible non-owner, non-review role and the handoff names `$external-worker`.

Return exactly:
- one external implementation package

Acceptance criteria:
- the handoff includes the internal worker role label being replaced; that label is provenance/routing metadata only and does not narrow the adapter
- the requested work stays inside the approved worker-side artifact contract and change surface
- the execution path is a direct external transport path; no silent fallback to `$consultant`, no internal subagent fallback, and no internal host layer pretending to be external
- any spawned internal subagent counts as internal execution, not external transport, even if the prompt assigns it a provider name or model label
- external-provider unavailability is reported as `BLOCKED:dependency` with the provider reason, and the orchestrator may reroute
- the package reports the role-appropriate artifact, explicit assumptions or risks, any relevant verification evidence, and provenance

## Toolchain Engineer

Use when the approved phase is primarily build-system, packaging, compiler, linker, preset, or reproducible-toolchain work.

Return exactly:
- one toolchain implementation package

Acceptance criteria:
- the change stays within approved toolchain scope
- build graph behavior, packaging, reproducibility, and local or CI parity remain aligned with the accepted plan
- planned build and packaging checks were run or clearly reported as blocked

## Platform Engineer

Use when the approved phase is primarily infrastructure, CI or CD, deployment, runtime platform, or developer-tooling work.

Return exactly:
- one platform implementation package

Acceptance criteria:
- the change stays within approved platform scope
- rollout or rollback notes are explicit
- platform validations were run or clearly reported as blocked

## Graphics Engineer

Use when the approved phase is primarily 2D or 3D rendering work such as render paths, shaders, materials, scene updates, asset flow, or frame behavior.

Return exactly:
- one graphics implementation package

Acceptance criteria:
- the change stays within approved graphics scope
- render-path behavior, resource lifecycle, and scene assumptions remain aligned with the accepted plan
- planned checks and relevant performance evidence were run or clearly reported as blocked

## Visualization Engineer

Use when the approved phase is primarily scientific or data visualization work such as charts, overlays, views, scales, legends, coordinate transforms, or exploration interactions.

Return exactly:
- one visualization implementation package

Acceptance criteria:
- the change stays within approved visualization scope
- visual encodings, transforms, units, and interactions remain aligned with the accepted plan
- planned checks were run or clearly reported as blocked

## Geometry Engineer

Use when the approved phase is primarily geometry or spatial-computation work such as transforms, predicates, intersections, meshing, tessellation, or spatial indexing.

Return exactly:
- one geometry implementation package

Acceptance criteria:
- the change stays within approved geometry scope
- coordinate conventions, tolerances, degeneracy handling, and edge-case behavior remain aligned with the accepted plan
- planned checks and tests were run or clearly reported as blocked

## Qt UI Engineer

Use when the approved phase is primarily Qt desktop UI work on windows, dialogs, widgets, focus, keyboard behavior, or approved theme and high-DPI handling.

Return exactly:
- one Qt UI implementation package

Acceptance criteria:
- the change stays within approved Qt UI scope
- interaction behavior, focus, and widget lifecycle remain aligned with the accepted plan
- planned checks were run or clearly reported as blocked

## Model-View Engineer

Use when the approved phase is primarily Qt model or view work such as models, proxies, delegates, selection, or large tree and table behavior.

Return exactly:
- one model or view implementation package

Acceptance criteria:
- the change stays within approved model or view scope
- index semantics, selection, sorting or filtering, and persistence behavior remain correct
- planned checks and tests were run or clearly reported as blocked

## QA Engineer

Use after implementation.

Return exactly:
- one verification report

Acceptance criteria:
- acceptance criteria are mapped to evidence
- regressions and edge cases are addressed
- nearby must-not-break surfaces from the plan are smoke-checked or explicitly blocked
- basic performance acceptance is included or explicitly blocked

## UI Test Engineer

Use when Qt desktop UI regressions need dedicated verification beyond the generic QA lane.

Return exactly:
- one Qt UI verification report

Acceptance criteria:
- interaction states, keyboard and focus behavior, and visual regressions are checked for the scoped surface
- visual evidence is included when appearance or layout changed
- blocking UI regressions are explicit and reproducible

## Independent Reviewers

Use after QA or when an explicit review gate is required.

Return exactly:
- one review report

Acceptance criteria:
- checks align with the accepted design, plan, and specialist constraints
- findings are concrete and reproducible
- approval is explicit, not implied

## Architecture Reviewer

Use when maintainability, extensibility, low coupling, or blast-radius control need an independent gate before merge or release.

Return exactly:
- one architecture and quality review report

Acceptance criteria:
- cohesion, coupling, extension-seam use, and dependency direction are checked against the accepted design
- hidden cross-cutting edits and unrelated-module churn are called out explicitly
- approval or rejection is explicit

## UX Reviewer

Use when user-facing quality needs an independent gate before merge or release.

Return exactly:
- one UX review report

Acceptance criteria:
- usability, accessibility, and flow issues are scoped and evidence-based
- blocking issues are clearly separated from optional polish
- approval or rejection is explicit

## Accessibility Reviewer

Use when keyboard access, focus order, labeling, contrast, or assistive-technology exposure need an independent gate before merge or release.

Return exactly:
- one accessibility review report

Acceptance criteria:
- accessibility findings are scoped and evidence-based
- blocking accessibility issues are separated from non-blocking improvements
- approval or rejection is explicit

## External Reviewer

Use when approved review or QA work should run through the external adapter for an eligible reviewer or QA role and the handoff names `$external-reviewer`.

Return exactly:
- one external review report

Acceptance criteria:
- the handoff includes the internal reviewer or QA role label being replaced; that label is provenance/routing metadata only and does not narrow the adapter
- the review stays review-only and does not request or require file edits
- the requested review strategy is explicit
- the execution path is external and explicit or preference-driven; no silent fallback to `$consultant` or an internal reviewer
- external-provider unavailability is reported as `BLOCKED:dependency` with the provider reason, and the orchestrator may reroute
- the report includes findings, risk surfaces, and an explicit gate decision

## Consultant

Use only when the lead wants a non-binding second opinion.

Return exactly:
- one advisory memo

Acceptance criteria:
- the memo is concise, explicit about assumptions, and advisory-only
- it does not route work or pretend to be a gate
- if it finds a real blocker, it points back to the proper specialist role

Invocation note:
- `$consultant` usage rules, toggle check, and execution paths are in `$CODEX_HOME/skills/consultant/SKILL.md`
- if the selected external consultant path fails or is unavailable, report that honestly and reroute; use an internal consultant only when `consultantMode: internal` was selected explicitly before dispatch
- `external-dispatch.md` is the shared contract for the new external adapters and the consultant config fields they share

## Role Map Notes

- external implementation through a provider maps to `$external-worker`
- external review or QA through a provider maps to `$external-reviewer`
- the assigned role in either external handoff is a provenance/routing label, not a constraint on universality
- `$consultant` remains advisory-only and is not a substitute for either external execution role
- `$external-brigade` is a utility orchestration surface for launching and aggregating a bounded parallel bundle of eligible external helpers; it is not a new specialist role in the core team map

## Interaction rules

- The orchestrating owner controls routing:
  - `$product-manager` for roadmap and intake
  - `$lead` for approved delivery work
- Only the root main conversation holding Lead dispatches downstream roles and writes work-item lifecycle state.
- A specialist completes one profession, artifact, and gate; it returns evidence plus an optional non-binding recommended next role to the root, then stops.
- A specialist never adopts Lead, launches a peer or downstream stage, advances the pipeline, or writes `agent-runs.jsonl`.
- The root may directly launch a configured external wrapper; no provider or leaf may recursively launch another wrapper.
- Subagents communicate by producing accepted artifacts for the next role, not by assigning work directly to peers.
- If a role is blocked by missing evidence, it should route back to the orchestrating owner for factual clarification instead of compensating with unsupported opinion.
- A role may request clarification, but it should route the request through the orchestrating owner unless a direct collaboration edge was explicitly approved.
- Reviewers report findings and gate outcomes; they do not directly manage implementation.
- When an upstream artifact is insufficient, return `REVISE` or `BLOCKED` instead of silently redefining the stage contract.
- External execution roles are routing adapters; they do not replace the consultant. They may replace eligible internal worker/review roles when config preference or explicit override selects them.

## Session logging

Every role — the orchestrator (the main conversation, as Lead) or a specialist — MUST write a session log to `.reports/YYYY-MM/` when the session produced a result, made a routing decision, or completed a review. See `AGENTS.md` § "Session logging rule" for the full contract and log format. Create the `YYYY-MM/` subdirectory if it does not exist. Session logs are summaries, not artifact copies.

## Structured completion report

For substantial tasks, prefer a structured closeout in the final summary:

- **Changed:** what was modified and why
- **Verified:** what was tested or checked, with evidence
- **Not verified:** what was not checked and why
- **Still open:** remaining required work to satisfy the current request, or `none`
- **Risks / follow-ups:** residual risks, deferred work, or known limitations

This is a recommended format for user-facing task completion, not a mandatory gate artifact. For pipeline handoffs, use the shared response format above.

## Gate questions

Ask these before advancing:

1. Is the artifact complete for its stage?
2. Is anything still assumed but unstated?
3. Did the stage stay within its role boundaries?
4. Are the allowed change surface and must-not-break surfaces explicit enough?
5. Is the next stage receiving only the context it truly needs?
6. Is an independent reviewer or human gate still required?
7. Is the blast radius still inside the approved change surface?
8. Is any admitted-scope obligation still open even though one sub-batch is finished?

## Terms and Abbreviations

- `agent-run-ledger.*`: helper script family that initializes legacy work-item ledger files and appends validated `agent-runs.jsonl` events.
- `agent-runs.jsonl`: JSONL execution ledger stored beside `status.md` for machine-readable work-item state.
- `check-work-items-state.*`: helper script family that checks every active work item under a repository root.
- `BLOCKED`: workflow state for a real missing dependency, prerequisite, or unavailable route.
- `CLI`: Command-Line Interface; a provider or tool invoked from a shell.
- `evidence`: concrete verification data such as a command, artifact path, review result, log summary, or observed output supporting a gate.
- `JSONL`: JSON Lines; one JSON object per line, used here for append-only execution events.
- `ledger`: append-only record of agent runs, gates, artifacts, and evidence for a work item.
- `PASS`: workflow state meaning the scoped artifact passed the relevant gate.
- `REVISE`: workflow state meaning the artifact must return to the same role for bounded correction.
- `QA`: Quality Assurance; verification work for tests, regressions, and acceptance criteria.
- `status.md`: human-readable recovery summary for the active work item.
- `WEAK MODEL / NOT RECOMMENDED`: repository classification for example-only providers excluded from production `auto` routing.
