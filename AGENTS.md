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
- minimize opinion-driven work by routing unknowns to factual roles first and requiring decisions to cite accepted evidence
- keep interpretation downstream of evidence: exhaust the needed factual lane before asking design, roadmap, or reviewer roles to make tradeoff judgments
- keep the system operating as a rolling loop: `PASS` advances immediately, `REVISE` stays in the same role for a bounded correction, and `BLOCKED` is reserved for real external blockers
- prefer continuous phase-by-phase flow with minimal handoff latency; do not pause between accepted artifacts unless a true gate failure or a policy-required human check requires it
- give each delegated task only approved inputs, minimal context, limited tools, one expected artifact, explicit acceptance criteria, and an explicit gate to the next stage
- pass accepted artifacts instead of raw transcript dumps whenever an accepted artifact already exists
- require `REVISE` or `BLOCKED` when upstream evidence is insufficient; do not allow downstream roles to silently compensate with guesses or private scope renegotiation
- stop progression when a quality gate fails
- treat `$consultant` as optional advisory staff only, never as a required pipeline stage or blocking reviewer
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

Available roles:

- `$consultant` from `$CODEX_HOME/skills/consultant`: optional non-blocking external second opinion for the lead; advisory-only and not part of the mandatory pipeline; base usage rules live in `$CODEX_HOME/skills/consultant/references/external-consultant-workflow.md`, with optional provider adapters such as `claude-workflow.md` when installed
- `$lead` from `$CODEX_HOME/skills/lead`: default delivery coordination, routing, artifact acceptance, and gate decisions for approved work
- `$product-manager` from `$CODEX_HOME/skills/product-manager`: roadmap ownership, initiative prioritization, admission into discovery or delivery, and milestone scope framing
- `$analyst` from `$CODEX_HOME/skills/analyst`: read-only codebase research and factual briefs only; this is the `researcher` role from the operating model
- `$product-analyst` from `$CODEX_HOME/skills/product-analyst`: factual product and user-context briefs before design
- `$architect` from `$CODEX_HOME/skills/architect`: architecture and design packages from accepted research
- `$algorithm-scientist` from `$CODEX_HOME/skills/algorithm-scientist`: formal algorithm, math, and correctness analysis before implementation
- `$computational-scientist` from `$CODEX_HOME/skills/computational-scientist`: scientific models, physics, simulation, and numerical-method packages before planning or implementation
- `$reliability-engineer` from `$CODEX_HOME/skills/reliability-engineer`: SLOs, failure modes, degradation, observability, and recovery constraints before planning
- `$planner` from `$CODEX_HOME/skills/planner`: small gated delivery plans from accepted design
- `$knowledge-archivist` from `$CODEX_HOME/skills/knowledge-archivist`: approved repository hygiene, documentation, plan or report curation, and archival consistency phases
- `$backend-engineer` from `$CODEX_HOME/skills/backend-engineer`: approved backend implementation phases only
- `$frontend-engineer` from `$CODEX_HOME/skills/frontend-engineer`: approved frontend implementation phases only
- `$graphics-engineer` from `$CODEX_HOME/skills/graphics-engineer`: approved 2D or 3D rendering implementation phases for render paths, shaders, materials, scene updates, and frame behavior
- `$visualization-engineer` from `$CODEX_HOME/skills/visualization-engineer`: approved scientific or data-visualization implementation phases for views, overlays, scales, legends, and exploration interactions
- `$geometry-engineer` from `$CODEX_HOME/skills/geometry-engineer`: approved geometry or spatial-computation implementation phases for transforms, predicates, meshing, indexing, and robust geometric behavior
- `$qt-ui-engineer` from `$CODEX_HOME/skills/qt-ui-engineer`: approved Qt desktop UI implementation phases for widgets, dialogs, and interaction behavior
- `$model-view-engineer` from `$CODEX_HOME/skills/model-view-engineer`: approved Qt model or view implementation phases for models, proxies, delegates, and selection behavior
- `$data-engineer` from `$CODEX_HOME/skills/data-engineer`: approved data implementation phases only
- `$toolchain-engineer` from `$CODEX_HOME/skills/toolchain-engineer`: approved build-system, packaging, compiler, linker, and reproducible-toolchain implementation phases
- `$platform-engineer` from `$CODEX_HOME/skills/platform-engineer`: approved infrastructure, CI or CD, and runtime platform implementation phases
- `$security-engineer` from `$CODEX_HOME/skills/security-engineer`: threat model, required controls, and security constraints before planning or implementation
- `$performance-engineer` from `$CODEX_HOME/skills/performance-engineer`: performance budgets, bottleneck modeling, and measurement strategy before planning or critical release
- `$qa-engineer` from `$CODEX_HOME/skills/qa-engineer`: QA verdict packages with tests, edge-case coverage, and basic performance checks
- `$ui-test-engineer` from `$CODEX_HOME/skills/ui-test-engineer`: dedicated Qt UI regression verification for interaction states, focus, high-DPI, themes, and visual changes
- `$ux-reviewer` from `$CODEX_HOME/skills/ux-reviewer`: independent UX gate for usability, accessibility, and user-flow quality
- `$accessibility-reviewer` from `$CODEX_HOME/skills/accessibility-reviewer`: independent accessibility gate for keyboard access, focus order, labeling, contrast, and assistive-technology exposure
- `$performance-reviewer` from `$CODEX_HOME/skills/performance-reviewer`: independent performance gate for hard budgets, public SLA, or cost-sensitive changes
- `$security-reviewer` from `$CODEX_HOME/skills/security-reviewer`: security gate findings or approval
- `$architecture-reviewer` from `$CODEX_HOME/skills/architecture-reviewer`: maintainability, change-isolation, dependency-direction, and architecture-fit review

Keep accepted artifacts near the code when the repository is the source of truth: canonical brief, research memo, design package, specialist constraint packages, phase plan, and review reports.
