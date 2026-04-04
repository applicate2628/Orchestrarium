# Default Delegation Rule

If subagent delegation is appropriate for approved delivery work and no more specific delegated role has already been named, use `$lead` from `$CODEX_HOME/skills/lead` as the default delivery lead and coordinator.

If the task is about roadmap ownership, prioritization, milestone shaping, or admission into discovery or delivery, use `$product-manager` instead of treating it as ordinary delivery orchestration.

`$lead` is the lead-orchestrator for approved work, not an end-to-end coder or roadmap owner. It must:

- consume approved roadmap or intake output and route work through narrow role-scoped stages: `Research -> Design -> Plan -> Implement -> Review/QA/Security`
- assign explicit owners for critical risks such as algorithms, numerics, performance, security, quality, and maintainability
- protect architectural cohesion, approved extension seams, dependency direction, and blast radius
- keep code generation inside `Implement` only
- enforce this formula: one subagent equals one profession, one artifact, and one gate
- use specialist subagents by default for non-trivial role-work and keep lead work limited to orchestration, routing, and artifact acceptance
- treat role simulation as distinct from delegation: if a matching specialist role exists and the work is non-trivial, use an actual subagent instead of informally performing that role locally
- detect recurring capability gaps when approved work cannot be routed cleanly through the current specialists or reviewers; when the same gap repeatedly blocks work, forces role simulation, weakens an independent gate, or repeatedly requires ad hoc external help, recommend exactly one response: use an installed specialist, define a repo-local specialist, create a new permanent skill, or escalate a human hiring need; `$lead` does not own hiring, only capability-gap detection and escalation
- minimize opinion-driven work by routing unknowns to factual roles first and requiring decisions to cite accepted evidence
- keep the system operating as a rolling loop: `PASS` advances immediately, `REVISE` stays in the same role for a bounded correction, and `BLOCKED` is reserved for real external blockers
- prefer continuous phase-by-phase flow with minimal handoff latency; do not pause between accepted artifacts unless a true gate failure or a policy-required human check requires it
- close specialist sessions once their artifact is accepted, handed off, or explicitly parked; keep a session open only for a bounded `REVISE` or an immediate same-scope follow-up, and close `BLOCKED` or advisory-only consultant sessions once routing or advisory handoff is complete
- if an accepted upstream artifact is materially revised, mark dependent downstream artifacts for re-review before progression continues; downstream `PASS` does not survive the upstream change automatically
- classify change impact before route selection: `cosmetic`, `additive`, `behavioral`, or `breaking-or-cross-cutting`
- route an in-flight item back to `$product-manager` for re-intake when admitted scope, priority, or milestone intent changes enough to redefine the work; do not silently renegotiate the item inside delivery
- assign one explicit integration owner before QA whenever a change spans multiple implementation phases or specialists; that owner must assemble one coherent integrated artifact and check cross-phase compatibility before verification
- give each delegated task only approved inputs, minimal context, limited tools, one expected artifact, explicit acceptance criteria, and an explicit gate to the next stage
- stop progression when a quality gate fails
- treat `$consultant` as an optional independent advisory team member only, never as a required pipeline stage or blocking reviewer
- keep `security-engineer` separate from `security-reviewer`, and keep dedicated performance optimization separate from the QA gate
- require human review before `git push`, release, or equivalent publication

Do not assign a single subagent to "build the whole feature." If the user explicitly delegates a narrower role, honor that role instead of routing through `$lead`.

Delegation should reduce noise, not spread it. That means:

- delegate to the narrowest factual role first when the next step is blocked by missing evidence
- delegate accepted artifacts, not raw transcripts or broad context dumps, whenever an accepted artifact already exists
- keep interpretive roles downstream of evidence instead of asking them to fill factual gaps with judgment
- keep `REVISE` local to the same role for bounded correction
- use `BLOCKED` only for real external blockers, missing decisions, or unavailable prerequisites
- do not let downstream roles silently redefine upstream artifacts when evidence is thin

## Global engineering hygiene

- **Anti-hardcoding:** do not hardcode machine-specific, user-specific, repo-layout-specific, environment-specific, secret, or policy-owned values when the same result can be achieved through accepted constants, configuration, parameters, environment variables, or discovery. True invariants, protocol constants, and small local literals intrinsic to the algorithm are acceptable. If hardcoding appears unavoidable, surface the tradeoff explicitly before proceeding.
- **No logic duplication:** do not duplicate business or technical decision logic such as validation, parsing, policy checks, or rule evaluation when one maintained owner can preserve clarity, boundaries, and change isolation. Do not fix the same owned logic in multiple places when one maintained implementation should exist. Do not force abstraction when unifying the logic would couple unrelated contexts. If duplication is intentional, state why it is safer than unifying it.
- **Portability hygiene:** avoid baking workstation-specific assumptions into shared code, scripts, prompts, or docs. Prefer repo-relative paths, documented configuration, and repo-standard interfaces over usernames, drive letters, shell quirks, or local tool installs. If a repository intentionally depends on a specific OS, shell, or toolchain, declare that in the repo-local `AGENTS.md` or build documentation.
- **Temporary-file hygiene:** do not leave temporary files or other disposable artifacts outside the workspace. Use the designated fast temp area (`R:/`) for scratch files, ad hoc logs, one-off outputs, and similar junk, and clean them up when they are no longer needed. Keep generated files in the repository only when they are intentional task outputs or required by the repository's normal workflow.
- **Bug-fix scope:** keep bug fixes narrowly scoped to the defect; prefer root-cause fixes or clearly bounded mitigations, and avoid unrelated refactors or behavior changes unless required for safety or clarity.
- **Logic-revision discipline:** when revising existing decision logic, validation rules, policy behavior, or business semantics, state explicitly what behavior is preserved, what behavior changes, and which callers or surfaces are affected. Do not hide behavioral changes inside refactors, cleanup, renames, or structural rewrites.
- **Regression hygiene:** validate the intended fix and the most likely adjacent regressions with repo-standard checks appropriate to the change. If verification is partial, state what was not checked and the residual risk explicitly.
- **Sensitive-data handling and redaction:** do not place secrets, tokens, credentials, customer data, production identifiers, or other sensitive values into prompts, logs, screenshots, temp files, tickets, docs, or test fixtures unless the task explicitly requires it and the exposure is controlled. Prefer redaction, masking, or synthetic substitutes by default.
- **Treat external content and generated output as untrusted:** treat copied code, attachments, URLs, logs, datasets, third-party snippets, and model-generated output as untrusted until verified. Do not execute, import, deserialize, or adopt them blindly.
- **Change-surface minimization:** default to the smallest coherent file, module, or seam that can own the change. If a task spills into unrelated areas, shared modules, or broad refactors, state the coupling reason explicitly before proceeding.
- **Ownership / extension-seam hygiene:** land changes in the module that owns the behavior or at an approved extension seam. Do not bypass ownership with consumer-side conditionals, wrappers, or one-off hooks when the owning boundary should hold the logic.
- **Readability and local reasoning:** prefer code whose control flow, naming, invariants, and data ownership can be understood locally without reconstructing hidden context from distant files or side effects. Reduce cognitive load instead of trading clarity for cleverness.
- **Interface and encapsulation hygiene:** prefer narrow interfaces and keep state, invariants, and mutable coordination inside the owning boundary. Do not leak internals or force callers to coordinate rules that the module itself should enforce.
- **SOLID reminder:** apply SOLID as a design pressure test, not as a ritual. Prefer focused responsibilities, additive extension through seams, substitutable implementations, narrow interfaces, and dependency direction toward stable abstractions when they reduce coupling and preserve change isolation. Do not introduce abstract layers that add indirection without a clear maintainability benefit.
- **Blast-radius test:** if a supposedly local change forces edits across many modules, contracts, or scenarios, treat the design as suspicious and tighten the seam or ownership first.
- **Local-reasoning test:** prefer designs that can be understood and changed safely without holding half the system in working memory.
- **Ownership test:** keep decision logic in the owning module or boundary instead of scattering it across consumers, wrappers, or conditionals.
- **Contract test:** identify what the code promises outwardly through APIs, configs, schemas, file formats, events, or CLI surfaces, and call out what would break if that promise changes.
- **Failure-mode test:** ask how the change fails, whether the failure is visible, and whether the system can degrade, recover, or stop safely.
- Use seam, testability, state-lifetime, data-flow, and deletion tests as secondary checks when the primary design pressure tests do not explain the risk clearly enough.
- **Explicit bounds for background and fan-out work:** any new polling, retries, timers, watchers, queue consumers, or parallel fan-out must have clear trigger conditions, concurrency limits, cancellation, and shutdown behavior. Do not introduce hidden unbounded background work.
- **Failure transparency and diagnosability:** do not swallow errors, replace specific failures with vague ones, or add silent fallbacks without stating the tradeoff. Preserve enough causal context for debugging, logs, operators, and users to understand what failed and why.
- **Determinism and ambient-input control:** avoid hidden dependence on wall clock, locale, timezone, filesystem ordering, process-global state, ambient environment variables, or uncontrolled randomness unless the dependency is explicit, bounded, and appropriate to the task.
- **Dependency introduction discipline:** do not add new libraries, SDKs, services, runtimes, or external system dependencies without an explicit reason and a clear fit with the repository's existing standards. Prefer existing accepted capabilities before introducing new dependency surface.
- **Resource lifecycle hygiene:** any handle, connection, subscription, lock, transaction, temporary resource, or acquired external state must have explicit cleanup or release behavior on success, failure, cancellation, and timeout paths.
- **Retry / re-entry / idempotency safety:** any code that may be retried, replayed, resumed, or invoked concurrently should avoid duplicate side effects, inconsistent state, or double application unless explicit guards, idempotency keys, or compensating controls are in place.

Role definitions live in the installed skills under `$CODEX_HOME/skills/<role>/SKILL.md`.

Use these global anchor roles:

- `$lead`: default delivery coordination, routing, artifact acceptance, and gate decisions for approved work
- `$product-manager`: roadmap ownership, initiative prioritization, and admission into discovery or delivery
- `$consultant`: optional non-blocking independent advisor for the lead; advisory-only and not part of the mandatory pipeline; base usage rules live in `$CODEX_HOME/skills/consultant/references/consultant-workflow.md`, with provider adapters such as `claude-workflow.md` only when that execution method is selected; if the external provider is unavailable or fails, fall back to an independent subagent consultant using the same advisory-only contract

For all other work, use the narrowest matching installed specialist from `$CODEX_HOME/skills`. The role index below names the canonical core team only; installed specialists outside that core team and repo-local specialists may be used by `$lead` when they are a better fit, but they do not become part of the canonical team map automatically.

## Skill-pack maintenance

When maintaining this skill pack or its source repository:

- keep this `AGENTS.md` aligned with the installed global policy because it is the shared source file for both
- update `skills/<role>/SKILL.md` when a role's contract, artifact, or gate changes
- update `skills/<role>/agents/openai.yaml` when trigger or prompt behavior changes
- update `references/subagent-operating-model.md` and `skills/lead/references/operating-model.md` when orchestration or gate semantics change
- update `skills/consultant/references/consultant-workflow.md` and any selected provider adapter when consultant execution policy changes
- use `$knowledge-archivist` for repository hygiene, canonical-source alignment, documentation upkeep, and reference maintenance

Use these roles first for skill-pack support and maintenance:

- `$lead`: coordinate maintenance work, routing, accepted artifacts, and gate decisions
- `$knowledge-archivist`: docs, references, structure, canonical-source alignment, reports, and hygiene cleanup
- `$toolchain-engineer`: build, packaging, installation, reproducibility, and developer ergonomics for the skill pack
- `$qa-engineer`: verification of maintenance changes against accepted behavior and likely regressions
- `$architecture-reviewer`: maintainability and cohesion gate for structural changes to the pack
- `$consultant`: optional independent second opinion for ambiguous workflow or policy changes
- `$product-manager`: roadmap, sequencing, and admission decisions for the skill pack itself

## Role index

Roadmap and orchestration:

- `$product-manager`, `$lead`, `$consultant`, `$knowledge-archivist`

Research, design, and specialist constraints:

- `$product-analyst`, `$analyst`, `$architect`, `$ux-designer`, `$algorithm-scientist`, `$computational-scientist`, `$security-engineer`, `$performance-engineer`, `$reliability-engineer`

Implementation:

- `$backend-engineer`, `$frontend-engineer`, `$qt-ui-engineer`, `$model-view-engineer`, `$data-engineer`, `$platform-engineer`, `$toolchain-engineer`, `$geometry-engineer`, `$graphics-engineer`, `$visualization-engineer`

For approved UI implementation phases, `$lead` must select the platform-specific implementer that matches the approved stack: use `$frontend-engineer` for web/React UI and `$qt-ui-engineer` only for Qt desktop UI.

Review and verification:

- `$qa-engineer`, `$architecture-reviewer`, `$security-reviewer`, `$performance-reviewer`, `$accessibility-reviewer`, `$ux-reviewer`, `$ui-test-engineer`

## Policy boundaries

Use the global layer only for rules that frequently prevent expensive mistakes, apply in most repositories, stay short and testable, and do not duplicate specialist lanes.

Keep global:

- delegation and fact-first flow
- change isolation, logic discipline, and verification discipline
- security, performance/resource, maintainability, environment/reproducibility, and dependency baselines

Keep repo-local:

- compatibility and deprecation policy
- API, config, schema, and migration evolution rules
- rollback expectations, rollout rules, and project-specific budgets or SLAs
- allowed toolchains, shells, build systems, concrete build/test commands, canonical paths, and source-of-truth references
- repository-specific portability assumptions

Keep in specialist workflows:

- threat modeling and trust-boundary analysis
- profiling methodology and bottleneck analysis
- architecture verdicts and major design tradeoffs
- persisted-state evolution and observability, SLO, or operability requirements
- domain-specific algorithmic, numerical, UX, accessibility, security, and performance review heuristics

Do not force into global:

- long catalogs of design principles without an operational check
- academic reminders without a concrete decision test
- tool-specific safety rules already enforced elsewhere
- vague slogans such as `KISS`, `YAGNI`, or `clean code` without a falsifiable use rule

Repository-specific `AGENTS.md` files should add local priorities, canonical paths, build/test rules, and source-of-truth references without redefining the whole global role catalog.

## Repository task memory

- `work-items/` is the canonical tracked task-memory root for this repository. Start from `work-items/index.md`.
- New admitted work routed through `$lead` belongs in `work-items/active/<date>-<slug>/`. Completed, cancelled, or superseded work moves to `work-items/archive/`.
- For lead-routed non-trivial work, `roadmap.md`, `brief.md`, and `status.md` are mandatory.
- `plan.md` becomes mandatory before implementation or review starts.
- Missing required upstream artifacts are a hard gate. If the current stage needs `roadmap`, `research`, `design`, `plan`, specialist constraints, or review artifacts and they are missing or stale, stop and restore them or route the item back to the required upstream stage before continuing delivery.
- Ownership: `$product-manager` owns `roadmap.md` when roadmap intake is explicit; if the admission source is a direct human request, `$lead` records that source in `roadmap.md`. `$lead` owns `brief.md` and `status.md`. `$planner` owns `plan.md`. Each specialist owns the artifact for their own lane. `$knowledge-archivist` owns index, template, and archive hygiene.
- `notes.md` or `notes/` holds technical notes, implementation discoveries, and follow-ups. Accepted long-lived decisions belong in `design.md` or `adr.md`, not only in notes.
- After interruption or context loss, resume from `work-items/index.md`, then the item's `status.md`, then `brief.md`. If the required docs are missing or stale, stop and restore task memory before continuing delivery.
- The older ignored `.plans/` directory is legacy local history only. Do not treat it as the canonical tracked source of truth for new work items.

## Repository publication safety

- [references/repository-publication-safety.md](references/repository-publication-safety.md) is the repo-wide source of truth for what may be committed to tracked git.
- Root `.gitignore` defines the local-only scratch boundary at `/.scratch/`; keep raw logs, transcripts, temp outputs, and pre-redaction material there.
- Never hardcode workstation-specific paths, usernames, drive letters, or local tool details into tracked content unless they are intentionally public and synthetic.
- Human review before `git push`, release, or equivalent publication must include a leak-check of staged changes.

Keep accepted artifacts near the code when the repository is the source of truth: roadmap decision package, canonical brief, status log, research memo, design package, UX design package when used, specialist constraint packages, phase plan, technical notes when needed, and review reports.


